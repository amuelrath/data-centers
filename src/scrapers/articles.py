import asyncio
import logging
import math

from gnews import GNews
from playwright.async_api import Page as AsyncPage
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
        remaining_urls = self._load_tasks()

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
        try:
            await page.goto(url, wait_until="domcontentloaded")

            # get the real url from the redirect
            if "news.google.com" in page.url:
                redirected = await self._wait_for_redirect(
                    page, timeout_ms=self.settings.playwright.timeout_ms
                )
                if not redirected:
                    logger.debug(f"Redirect never completed, still on {page.url}")
                    return

            if page.url == "chrome-error://chromewebdata/":
                logger.debug(f"Chrome Error: Skipping {url}")
                return

            # use gnews to parse content...
            # seems to be more reliable
            gnews = GNews()
            article_text = gnews.get_full_article(page.url)["text"]

            if article_text is None:
                # try again later
                logger.debug(f"No text. Skipping {url}")
                return

            if self._is_flagged_as_bot(article_text):
                self.writer.write(
                    ArticleError(
                        rss_url=url, decoded_url=page.url, error="flagged"
                    ).model_dump()
                )
                return

            # data was good: write
            self.writer.write(
                ArticleSuccess(
                    text=article_text,
                    rss_url=url,
                    decoded_url=page.url,
                ).model_dump()
            )
            return
        finally:
            await page.close()

    def _load_tasks(self) -> list[str]:
        validated = [
            HeadlineAdapter.validate_python(d) for d in self.writer.load_remaining()
        ]
        remaining_headlines = [s for s in validated if isinstance(s, HeadlineSuccess)]
        remaining_urls = {str(h.rss_url) for h in remaining_headlines}
        skipped = {e.slug for e in validated if isinstance(e, HeadlineError)}

        if skipped:
            logger.info(f"Skipping {len(skipped)} articles with prior errors.")

        if len(remaining_urls) == 0:
            logger.info("Nothing to scrape.")
            return []
        else:
            num_completed = len(self.writer.load_completed_keys())
            print(f"\nFound {num_completed} existing articles!")
            print(f"{len(remaining_urls)} articles left to scrape!")

        return list(remaining_urls)

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
    async def _wait_for_redirect(page: AsyncPage, timeout_ms: int) -> bool:
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
