import logging
import math
from typing import Any

from gnews import GNews
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
    HeadlineError,
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
            range(0, len(remaining_urls), self.settings.batch.size),
            total=math.ceil(len(remaining_urls) / self.settings.batch.size),
            desc="Articles: Processing Batch",
            disable=not self.settings.show_progress,
        ):
            batch = remaining_urls[i : i + self.settings.batch.size]
            await async_gather_bounded(
                items=batch,
                coro_fn=self._scrape_one,
                max_concurrency=self.settings.playwright.max_concurrency,
            )
        return None

    async def _scrape_one(self, url: str):
        page = await self.new_page()
        await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=self.settings.playwright.timeout_ms
            * 2,  # some sites can be very slow
        )

        # get the real url from the redirect
        if "news.google.com" in page.url:
            redirected = await self._wait_for_redirect(
                page, timeout_ms=self.settings.playwright.timeout_ms * 2
            )
            if not redirected:
                logger.debug(f"Redirect never completed, still on {page.url}")
                return await page.close()

        if page.url == "chrome-error://chromewebdata/":
            logger.debug(f"Chrome Error: Skipping {url}")
            return await page.close()

        # use gnews to parse content...
        # seems to be more reliable
        gnews = GNews()
        article_text = gnews.get_full_article(page.url)["text"]

        if article_text is None:
            # try again later
            logger.debug(f"No text. Skipping {url}")
            return await page.close()

        if self._is_flagged_as_bot(article_text):
            self.writer.write(
                ArticleError(
                    slug=article.slug,
                    rss_url=article.rss_url,
                    decoded_url=page.url,
                    error="flagged",
                )
                    rss_url=url, decoded_url=page.url, error="flagged"
                ).model_dump()
            )
            return await page.close()

        return self.writer.write(
        # data was good: write
        self.writer.write(
            ArticleSuccess(
                text=article_text,
                rss_url=url,
                decoded_url=page.url,
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

    @staticmethod
    async def _wait_for_redirect(page: AsyncPage, timeout_ms: int = 15_000) -> bool:
        """
        Polls page.url until it's no longer on news.google.com, or timeout.
        Returns True if redirect completed, False if timed out.
        """
        import time

        start = time.monotonic()
        while (time.monotonic() - start) * 1000 < timeout_ms:
            if "news.google.com" not in page.url:
                return True
            await asyncio.sleep(0.1)
        return "news.google.com" not in page.url  # final check
