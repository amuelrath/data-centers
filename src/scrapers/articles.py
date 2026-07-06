import logging
import math
from typing import Any

import trafilatura
from playwright.async_api import Page as AsyncPage
from playwright.async_api import Request as AsyncRequest
from playwright.async_api import Route as AsyncRoute
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from tqdm.auto import tqdm

from config import ArticleScraperConfig
from models import (
    ArticleError,
    ArticleSuccess,
    HeadlineAdapter,
    HeadlineSuccess,
)
from scrapers.base import BaseAsyncScraper
from utils import JsonlCheckpointWriter, async_gather_bounded
from utils.constants import BOT_FLAGS, COOKIE_BANNER_REMOVE_SCRIPT
from utils.parsers import extract_clean_text

logger = logging.getLogger(__name__)

# stop trafilatura et al. from flooding the logs.
for name in ("trafilatura", "readability", "htmldate", "urllib3", "charset_normalizer"):
    logging.getLogger(name).setLevel(logging.CRITICAL + 1)


class ArticleScraper(BaseAsyncScraper):
    def __init__(
        self, writer: JsonlCheckpointWriter, config: ArticleScraperConfig | None = None
    ):
        self.settings = config or ArticleScraperConfig()
        super().__init__(config=self.settings.playwright)
        self.writer = writer

    async def scrape_all(self):
        remaining_articles = [
            HeadlineAdapter.validate_python(a) for a in self.writer.load_remaining()
        ]
        if len(remaining_articles) == 0:
            logger.info("Nothing to scrape.")
            return
        else:
            num_completed = len(self.writer.load_completed_keys())
            print(f"Found {num_completed} existing articles!")
            logger.info(f"Found {len(remaining_articles)} existing articles!")

            print(f"{len(remaining_articles)} articles left to scrape!")
            logger.info(f"{len(remaining_articles)} articles left to scrape")

        for i in tqdm(
            range(0, len(remaining_articles), self.settings.batch.size),
            total=math.ceil(len(remaining_articles) / self.settings.batch.size),
            desc="Articles: Processing Batch",
            disable=not self.settings.show_progress,
        ):
            batch = remaining_articles[i : i + self.settings.batch.size]
            await self._dispatch_batch(batch)

    async def _dispatch_batch(self, batch: list[dict[str, Any]]) -> None:
        """
        Orchestrates scraping of a batch of articles.

        :param batch: Multiple rows of output from NewsScraper.
        :return: None
        """
        # get the articles and save
        await async_gather_bounded(
            items=batch,
            coro_fn=self._scrape_one,
            max_concurrency=self.settings.playwright.max_concurrency,
        )

        return None

    async def _scrape_one(self, article: HeadlineSuccess) -> None:
        """
        Validates article data and writes article text
        scraped from the site.

        If navigation fails, will not save anything so they can be
        retried in future runs.

        :param article: One row of output from NewsScraper
        :return: None
        """

        page = await self.new_page()
        await page.route("**/*", self._block_resources)

        try:
            await page.goto(article.rss_url, wait_until="domcontentloaded")
            await page.wait_for_load_state("domcontentloaded")
            html_content = await page.content()
        except PlaywrightTimeoutError:
            logger.warning(f"Timed out while waiting for {page.url}!")
            return self.writer.write(
                ArticleError(
                    slug=article.slug,
                    rss_url=article.rss_url,
                    decoded_url=page.url,
                    error="timeout",
                ).model_dump()
            )
        except Exception as e:
            logger.error(f"Unhandled Exception: {e}!")
            return None

        article_text = extract_clean_text(
            trafilatura.extract(
                html_content,
                favor_precision=True,
                include_formatting=False,
                include_comments=False,
                include_tables=False,
                include_links=False,
                include_images=False,
            )
        )

        if self._is_flagged_as_bot(article_text):
            return self.writer.write(
                ArticleError(
                    slug=article.slug,
                    rss_url=article.rss_url,
                    decoded_url=page.url,
                    error="flagged",
                )
            )

        return self.writer.write(
            ArticleSuccess(
                slug=article.slug,
                title=article.title,
                text=article_text,
                rss_url=article.rss_url,
                decoded_url=page.url,
                published=article.published,
                source=article.source,
            ).model_dump()
        )

    @staticmethod
    async def _block_resources(route: AsyncRoute, request: AsyncRequest) -> None:
        if request.resource_type in ["image", "media", "font", "stylesheet"]:
            await route.abort()
        else:
            await route.continue_()

    @staticmethod
    async def _remove_cookie_banner(page: AsyncPage) -> None:
        """
        Tries to remove the cookie banner.
        Cookie banners interfere with trafilatura extraction.

        :param page: The Playwright ``Page`` object.
        :return: None
        """

        await page.evaluate(COOKIE_BANNER_REMOVE_SCRIPT)

        return None

    @staticmethod
    def _is_flagged_as_bot(txt: str | None) -> bool:
        """
        Returns True if text looks like it is a security check.
        """

        if not txt:
            return False

        lowered = txt.lower()
        return any(flag in lowered for flag in BOT_FLAGS)
