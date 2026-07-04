import logging
import math
import re
import sys
from typing import Any

import trafilatura
from models import ArticleModel
from playwright.async_api import Page as AsyncPage
from playwright.async_api import Request as AsyncRequest
from playwright.async_api import Route as AsyncRoute
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from pydantic import ValidationError
from scrapers.base import BaseAsyncScraper
from tqdm.auto import tqdm
from utils import JsonlCheckpointWriter, async_gather_bounded, sleep_norm
from utils.constants import BOT_FLAGS, COOKIE_BANNER_REMOVE_SCRIPT
from utils.parsers import extract_clean_text

from config import ArticleScraperConfig
from exceptions import RateLimitedError

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
        remaining_articles = self.writer.load_remaining()
        logger.info(f"Found {len(remaining_articles)} articles to scrape!")

        if len(remaining_articles) == 0:
            logger.info("Nothing to scrape.")
            return

        for i in tqdm(
            range(0, len(remaining_articles), self.settings.batch.size),
            total=math.ceil(len(remaining_articles) / self.settings.batch.size),
            desc="Articles: Processing Batch",
            disable=not self.settings.show_progress,
            position=0,
        ):
            batch = remaining_articles[i : i + self.settings.batch.size]
            blocked = await self._dispatch_batch(batch)

            if blocked:
                # stop trying to scrape
                logger.error("Possibly rate limited!!")
                print("You may have been rate limited by Google!")
                sys.exit(1)

            # sleep to avoid hammering Google RSS
            sleep_norm(
                self.settings.batch.sleep_s_base,
                self.settings.batch.jitter_s_mu,
                self.settings.batch.jitter_s_sigma,
            )

    async def _dispatch_batch(self, batch: list[dict[str, Any]]) -> bool:
        """
        Orchestrates scraping of a batch of articles.

        :param batch: Multiple rows of output from RssScraper.
        :return: True if a block is detected during this batch.
        """
        blocked = False

        def on_error(_, exc):
            nonlocal blocked
            if isinstance(exc, RateLimitedError):
                blocked = True

        # get the articles and save
        await async_gather_bounded(
            items=batch,
            coro_fn=self._scrape_one,
            max_concurrency=self.settings.playwright.max_concurrency,
            on_error=on_error,
        )

        return blocked

    async def _scrape_one(self, article: dict[str, Any]) -> None:
        """
        Validates article data and writes article content
        and decoded_url scraped from the site.

        If navigation fails, will not save anything so they can be
        retried in future runs.

        :param article: One row of output from RssScraper
        :return: None
        """
        try:
            article = ArticleModel.model_validate(article)

            # ensure that this isn't an article to skip
            if article.error:
                return None

        except ValidationError as e:
            logger.error(f"Failed to validate article data {e}")
            return None

        page = await self.new_page()
        await page.route("**/*", self._block_resources)
        await page.goto(article.rss_url, wait_until="domcontentloaded")

        try:
            # wait for the redirect to the actual site
            # this can be a source of rate limiting, as we still have to
            # ask Google to give us the real article URL
            await page.wait_for_url(
                lambda u: "news.google.com" not in u,
                timeout=self.config.timeout_ms * 2,  # this can take a while...
            )

        except PlaywrightTimeoutError:
            logger.debug(f"Timed out while trying to navigate to {article.rss_url}!")
            return None

        # if the page is fully loaded but we never left news.google.com,
        # Google refused to redirect us: treat this as a rate limit signal
        await page.wait_for_load_state("load")
        if "news.google.com" in page.url:
            raise RateLimitedError(f"Google refused to redirect for {article.rss_url}!")

        try:
            await page.wait_for_load_state("domcontentloaded")
            html_content = await page.content()
            decoded_url = page.url
        except PlaywrightTimeoutError:
            logger.warning(f"Timed out while waiting for {page.url}!")
            return self._finalize(article, error="timeout")
        except Exception as e:
            logger.error(f"Unhandled Exception: {e}!")
            return self._finalize(article, error="unknown")

        article_content = extract_clean_text(
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

        if self._is_flagged_as_bot(article_content):
            return self._finalize(article, error="flagged", decoded_url=decoded_url)

        if self._is_top_n_list(article_content):
            logger.debug(f"Top N list. Skipping article: {article.decoded_url}!")
            return self._finalize(article, error="topn", decoded_url=decoded_url)

        return self._finalize(article, content=article_content, decoded_url=decoded_url)

    def _finalize(
        self,
        article: ArticleModel,
        *,
        error: str | None = None,
        content: str | None = None,
        decoded_url: str | None = None,
    ) -> None:
        """
        Applies final field updates to an article and writes it out.
        """

        if error is not None:
            article.error = error
        if content is not None:
            article.content = content
        if decoded_url is not None:
            article.decoded_url = decoded_url

        self.writer.write(article.model_dump())
        return None

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
    def _is_top_n_list(txt: str) -> bool:
        """
        Returns True if the text contains something like
        'Top N'
        """

        # countdown list articles are not super useful
        # difficult to disambiguate projects discussed.
        # they are prevalent enough to specifically remove them
        if not txt:
            return False

        return bool(re.search(r"\btop\s*\d+\b", txt, re.IGNORECASE))
