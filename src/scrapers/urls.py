import logging
import sys

from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from tqdm.auto import tqdm

from config import PlaywrightScraperConfig
from utils.checkpoint import JsonlCheckpointWriter
from utils.parsers import (
    extract_anchors_from_location_grid,
    extract_buttons,
    extract_page_pagination,
)

from .base import BaseSyncScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.datacenters.com"


class ListingUrlScraper(BaseSyncScraper):
    """
    Scrapes datacenter listing URLs from paginated location-grid pages on datacenters.com.

    Usage::

        with ListingUrlScraper(writer, config) as scraper:
            scraper.scrape_all()
    """

    def __init__(
        self,
        writer: JsonlCheckpointWriter,
        config: PlaywrightScraperConfig | None = None,
    ):
        super().__init__(config or PlaywrightScraperConfig())
        self.writer: JsonlCheckpointWriter = writer
        self._page: Page | None = None
        self._current_paginated_page: int | None = None
        self._num_paginated_pages: int | None = None
        self._next_button: Locator | None = None
        self._prev_button: Locator | None = None
        self._num_urls_per_page: int | None = None

    def scrape_all(self) -> None:
        """
        Scrapes all pages. Saves to file as:

        { "listing_url": str, "slug": str  }

        :return: None
        """
        logger.info("Scraping all URLs...")

        saved_listing_urls = self.writer.load_completed_keys()
        logger.info(f"Found {len(saved_listing_urls)} previously scraped URLs!")

        self._goto_main_page_and_setup()

        # determine where we need to start
        start_page = (len(saved_listing_urls) // self._num_urls_per_page) + 1
        logger.debug(f"Starting on page {start_page}")

        # scrape the remaining pages
        end_page = (
            self.config.debug.num_debug_pages
            if self.config.debug.enabled
            else self._num_paginated_pages
        )

        # if range is already fully covered, skip entirely
        if start_page >= end_page:
            logger.info(
                f"Already have {len(saved_listing_urls)} URLs, "
                f"covering pages 1-{end_page}. Nothing to scrape."
            )
            return

        self._scrape_and_write_range(
            start_page=start_page,
            end_page=end_page,
            saved_listing_urls=saved_listing_urls,
        )

        logger.info("Done scraping all pages!")

    def _scrape_and_write_range(
        self, start_page: int, end_page: int, saved_listing_urls: set[str]
    ) -> None:
        """
        Scrapes pages [start_page, end_page] inclusive, writing new listing urls to file
        immediately after each page is scraped (instead of batching to the end).

        :param start_page: The paginated page number to begin scraping on (1-indexed).
        :param end_page: The paginated page number to stop scraping on (inclusive).
        :param saved_listing_urls: urls already saved, to avoid duplicate writes.
        :return: None
        :raises RuntimeError: If start_page or end_page is out of bounds, or start_page > end_page.
        """

        if not self._page:
            self._goto_main_page_and_setup()

        # ensure bounds are OK
        if (
            (start_page <= 0)
            or (end_page > self._num_paginated_pages)
            or start_page > end_page
        ):
            raise RuntimeError(
                f"Start page {start_page} or end page {end_page} is invalid. Must be between 1 and {self._num_paginated_pages}."
            )

        logger.debug(f"Scraping URLs from range {start_page} to {end_page}...")

        # handles dedup for entire run
        seen_this_run = set(saved_listing_urls)

        def _write_rows(listing_urls: list[str]) -> None:
            """Writes all unseen URLs and adds them to seen_this_run."""
            new_listing_urls = [u for u in listing_urls if u not in seen_this_run]
            if not new_listing_urls:
                logger.debug(f"Found no new URLs on {self._current_paginated_page}")
                return
            seen_this_run.update(new_listing_urls)
            listing_urls = [{"listing_url": u} for u in new_listing_urls]
            self.writer.write(listing_urls)
            logger.debug(
                f"Saved {len(new_listing_urls)} URLs from page {self._current_paginated_page}."
            )

        # scrape + write the start page
        logger.debug("Scraping first page...")
        self._goto_specific_paginated_page(start_page)
        _write_rows(self._scrape_one(self._page))

        # scrape + write the remaining pages
        num_navs = end_page - start_page
        for _ in tqdm(
            range(num_navs),
            desc="Scraping Pages...",
            disable=not self.config.show_progress,
        ):
            self._goto_next_paginated_page()
            logger.debug(f"Scraping page {self._current_paginated_page}...")
            _write_rows(self._scrape_one(self._page))

    def _goto_specific_paginated_page(self, page_num: int) -> None:
        """
        Safely navigate to a specific paginated page.

        :param int page_num: the paginated page to navigate to.
        :return: None
        :raises RuntimeError: If navigation completes on the wrong page.
        """

        # ensure we aren't trying to navigate out of bounds
        if page_num > self._num_paginated_pages:
            logger.warning(
                f"Tried to go to page {page_num} when on page {self._current_paginated_page}!"
            )
            return

        if page_num < 1:
            logger.warning(
                f"Tried to go to page {page_num} when on page {self._current_paginated_page}!"
            )
            return

        logger.debug(f"Navigating to page {page_num}...")

        # perform the navigation (want - current)
        # if we are on page 5 and want to go to page 10:
        #   ex: 10 - 5 = +5 -> we go forward five pages
        #
        # if we are on page 10 and want to go to page 5:
        #   ex: 5 - 10 = -5 -> we go back five pages
        num_navs = page_num - self._current_paginated_page
        if num_navs > 0:
            # positive -> click next_button num_nav times
            for _ in range(num_navs):
                self._goto_next_paginated_page()
        elif num_navs < 0:
            # negative -> click prev_button num_nav times
            for _ in range(-num_navs):
                self._goto_previous_paginated_page()
        else:
            # zero -> do nothing
            pass

        # check to ensure we are on the right page
        if self._current_paginated_page != page_num:
            raise RuntimeError(
                f"Navigation to specific page {page_num} failed!"
                f" Ended up on page {self._current_paginated_page} by navigating {num_navs} times."
            )

    def _goto_next_paginated_page(self) -> None:
        """
        Safely clicks next page button and updates state.

        :return: None
        """

        # Tried to go after last page.
        if self._current_paginated_page + 1 > self._num_paginated_pages:
            logger.warning(
                f"Tried to go to page {self._current_paginated_page + 1} when on page {self._current_paginated_page}!"
            )
            return

        self._next_button.click()
        self._page.wait_for_load_state("domcontentloaded")
        self._current_paginated_page += 1

    def _goto_previous_paginated_page(self) -> None:
        """
        Safely clicks previous page button and updates state.

        :return: None
        """

        # Tried to go before first page
        if self._current_paginated_page - 1 < 1:
            logger.warning(
                f"Tried to go to page {self._current_paginated_page - 1} when on page {self._current_paginated_page}!"
            )
            return

        self._prev_button.click()
        self._page.wait_for_load_state("domcontentloaded")
        self._current_paginated_page -= 1

    def _goto_main_page_and_setup(self) -> None:
        """
        Creates a new page and navigates to https://datacenters.com/locations/united-states.

        Then sets:

        * ``current_page``
        * ``num_pages``
        * ``next_button``
        * ``prev_button``
        * ``num_urls_per_page``

        :return: None
        :raises: PlaywrightTimeoutError
        """
        logger.debug("Navigating to main page and setting up...")

        # open new tab and navigate to site
        page = self.new_page()
        try:
            page.goto(BASE_URL + "/locations/united-states")
        except PlaywrightTimeoutError as e:
            logger.warning("Timed out while connecting!")
            print("Timed out while trying to connect to datacenters.com. Try again.", e)
            sys.exit(1)

        self._page = page

        # set up pagination info
        current_page, num_pages = extract_page_pagination(self._page)
        self._current_paginated_page = current_page
        self._num_paginated_pages = num_pages

        # get pagination controls
        next_page_button, prev_page_button = extract_buttons(self._page)
        self._next_button = next_page_button
        self._prev_button = prev_page_button

        # get number items per page
        items = extract_anchors_from_location_grid(self._page)
        self._num_urls_per_page = len(items)

    @staticmethod
    def _scrape_one(page: Page) -> list[str]:
        """
        Extracts the URLs from each ``<a/>`` within the location-grid.

        :param page: The Playwright ``Page`` object.
        :return: A list of URLs from the current page's location-grid.
        """

        anchors = extract_anchors_from_location_grid(page)
        listing_urls = [
            BASE_URL + listing_url
            for a in anchors
            if (listing_url := a.get_attribute("href"))
        ]
        return list(listing_urls)
