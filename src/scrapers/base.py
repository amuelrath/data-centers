import logging

from playwright.async_api import (
    Browser as AsyncBrowser,
)
from playwright.async_api import (
    BrowserContext as AsyncBrowserContext,
)
from playwright.async_api import Page as AsyncPage
from playwright.async_api import (
    Playwright as AsyncPlaywright,
)
from playwright.sync_api import (
    Browser as SyncBrowser,
)
from playwright.sync_api import (
    BrowserContext as SyncBrowserContext,
)
from playwright.sync_api import Page as SyncPage
from playwright.sync_api import (
    Playwright as SyncPlaywright,
)
from utils.clients import (
    close_async_client,
    close_sync_client,
    launch_async_client,
    launch_sync_client,
)

from config import PlaywrightScraperConfig


class BaseSyncScraper:
    """
    Owns the Sync Playwright lifecycle. Subclasses focus on scraping logic only.

    Usage::

        with BaseSyncScraper(config) as scraper:
            page = scraper.new_page()
            page.goto("https://example.com")
            ...
    """

    def __init__(self, config: PlaywrightScraperConfig | None = None):
        self.config = config or PlaywrightScraperConfig()
        self._playwright: SyncPlaywright | None = None
        self._browser: SyncBrowser | None = None
        self.context: SyncBrowserContext | None = None

    def __enter__(self) -> "BaseSyncScraper":
        self._playwright, self._browser, self.context = launch_sync_client(
            self.config.context, self.config.headless
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        close_sync_client(self._playwright, self._browser, self.context)

    def new_page(self) -> SyncPage:
        """
        Creates a new page and waits for 'domcontentloaded'.
        """

        page = self.context.new_page()
        page.set_default_timeout(self.config.timeout_ms)
        page.wait_for_load_state("domcontentloaded")

        return page


class BaseAsyncScraper:
    """
    Owns the Async Playwright lifecycle. Subclasses focus on scraping logic only.

    Usage::

        async with BaseAsyncScraper(config) as scraper:
            page = await scraper.new_page()
            await page.goto("https://example.com")
            ...
    """

    def __init__(self, config: PlaywrightScraperConfig | None = None):
        self.config = config or PlaywrightScraperConfig()
        self._playwright: AsyncPlaywright | None = None
        self._browser: AsyncBrowser | None = None
        self.context: AsyncBrowserContext | None = None

    async def __aenter__(self) -> "BaseAsyncScraper":
        self._playwright, self._browser, self.context = await launch_async_client(
            self.config.context, headless=self.config.headless
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await close_async_client(self._playwright, self._browser, self.context)

    async def new_page(self) -> AsyncPage:
        """
        Creates a new page, sets default timeout, and waits for 'domcontentloaded'.
        """

        page = await self.context.new_page()
        page.set_default_timeout(self.config.timeout_ms)
        await page.wait_for_load_state("domcontentloaded")

        return page
