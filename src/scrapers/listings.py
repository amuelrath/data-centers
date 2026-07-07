import logging

from playwright.async_api import Page as AsyncPage
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from config import PlaywrightScraperConfig
from models import ProjectError
from scrapers.base import BaseAsyncScraper
from utils import JsonlCheckpointWriter, async_gather_bounded
from utils.parsers import extract_is_404, extract_listing, extract_map_button

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
        remaining_urls = self._load_tasks()

        logger.debug("Dispatching scrapers...")
        await async_gather_bounded(
            items=remaining_urls,
            coro_fn=self._scrape_one,
            max_concurrency=self.config.max_concurrency,
            show_progress=self.config.show_progress,
            desc="Scraping Listings",
        )

        logger.info("Done scraping all listings!")
        return None

    async def _scrape_one(self, url: str) -> None:
        """
        Scrapes and writes one listing.

        :param url: The URL of the listing.
        :return: None
        """
        page = await self.new_page()
        await page.goto(url)
        slug = url.split(".com/")[1]

        if await extract_is_404(page):
            logger.debug(f"404 Found. Skipping listing {url}.")
            # add it to the projects.jsonl so we don't try it again
            self.writer.write(
                ProjectError(slug=slug, listing_url=url, error="404").model_dump()
            )
            return None

        await self._click_map_tab(page)

        try:
            project = await extract_listing(page)
        except PlaywrightTimeoutError:
            logger.warning(f"Timed out while scraping listing {url}!")
            # do write. we can try again.
            return None
        finally:
            await page.close()

        # save the listing
        return self.writer.write(project.model_dump())

    def _load_tasks(self) -> list[str]:
        remaining_urls = self.writer.load_remaining_keys()
        if len(remaining_urls) == 0:
            logger.info("Nothing to scrape.")
            return []
        else:
            num_completed = len(self.writer.load_completed_keys())
            print(f"Found {len(num_completed)} existing listings!")
            print(f"{len(remaining_urls)} listings left to scrape!")

        return remaining_urls

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
