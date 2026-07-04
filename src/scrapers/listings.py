import logging

from playwright.async_api import Page as AsyncPage
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from config import PlaywrightScraperConfig
from scrapers.base import BaseAsyncScraper
from utils import JsonlCheckpointWriter, async_gather_bounded
from utils.parsers import extract_listing, extract_map_button

logger = logging.getLogger(__name__)


class ListingScraper(BaseAsyncScraper):
    """
    Scrapes datacenter listings on datacenters.com

    Usage::

        async with ListingScraper(writer, config, urls_path="urls.jsonl") as scraper:
            await scraper.scrape_all()
    """

    def __init__(
        self,
        writer: JsonlCheckpointWriter,
        config: PlaywrightScraperConfig | None = None,
    ):
        super().__init__(config or PlaywrightScraperConfig())
        self.writer = writer

    async def scrape_all(self):
        logger.info("Scraping all listings...")
        remaining_urls = self.writer.load_remaining_keys()
        logger.info(f"Found {len(remaining_urls)} listings to scrape!")

        # nothing left to scrape
        if len(remaining_urls) == 0:
            logger.info("Nothing to scrape.")
            return

        logger.debug("Dispatching scrapers...")
        await async_gather_bounded(
            items=remaining_urls,
            coro_fn=self._scrape_one,
            max_concurrency=self.config.max_concurrency,
        )

        logger.info("Done scraping all listings!")

    async def _scrape_one(self, url: str) -> dict[str, str | None] | None:
        """
        Scrapes and writes one listing.

        :param url: The URL of the listing.
        :return: None
        :raise: PlaywrightTimeoutError
        """
        page = await self.new_page()
        await page.goto(url)
        await self._click_map_tab(page)

        try:
            extracted_listing = await extract_listing(page)
        except PlaywrightTimeoutError:
            logger.warning(f"Timed out while scraping listing {url}!")
            return None
        finally:
            await page.close()

        # save the listing
        self.writer.write(extracted_listing)

        return None

    @staticmethod
    async def _click_map_tab(page: AsyncPage) -> None:
        """
        Clicks the map tab so that extractable location data and other details
        get loaded.

        :param page: The Playwright ``Page`` object.
        :return: None
        """

        map_button = await extract_map_button(page)
        await map_button.click()

        return None
