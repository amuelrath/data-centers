import dataclasses
import logging
from abc import ABC, abstractmethod
from typing import Any, Literal

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

from config import PlaywrightContextConfig, PlaywrightScraperConfig
from utils import build_proxy
from utils.clients import (
    close_async_client,
    close_sync_client,
    launch_async_client,
    launch_sync_client,
)
from utils.constants import STEALTH_INIT_SCRIPT

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    @abstractmethod
    def scrape_all(self) -> None:
        pass

    @abstractmethod
    def _scrape_one(self, *args, **kwargs) -> None:
        pass

    @abstractmethod
    def _load_tasks(self) -> list[Any]:
        pass


class BaseSyncScraper(BaseScraper):
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

    def new_context(
        self,
        close_previous: bool = True,
        use_proxy: bool = True,
        config: PlaywrightContextConfig | None = None,
    ) -> SyncBrowserContext:
        """
        Creates and sets a new browser context.

        :param config: A new PlaywrightContextConfig. If not specified uses self.config.
        :param use_proxy: Whether to use a decodo proxy.
        :param close_previous: Whether to close the previous context.
        :return: SyncBrowserContext
        """
        if close_previous and self.context is not None:
            self.context.close()
            logger.debug("Previous sync context torn down.")

        cfg = {
            k: v
            for k, v in dataclasses.asdict(self.config.context or config).items()
            if v is not None
        }
        if use_proxy:
            proxy = build_proxy(returns="playwright")
            cfg["proxy"] = proxy

        context = self._browser.new_context(**cfg)
        context.add_init_script(STEALTH_INIT_SCRIPT)
        self.context = context
        return context

    def new_page(self) -> SyncPage:
        """
        Creates a new page and waits for 'domcontentloaded'.
        """

        page = self.context.new_page()
        page.set_default_timeout(self.config.timeout_ms)
        page.wait_for_load_state("domcontentloaded")

        return page

    def scrape_all(self, *args, **kwargs) -> None:
        raise NotImplementedError("scrape_all() not implemented")

    def _scrape_one(self, *args, **kwargs) -> None:
        raise NotImplementedError("_scrape_one() not implemented")

    def _load_tasks(self, *args, **kwargs) -> list[Any]:
        raise NotImplementedError("_load_tasks() not implemented")


class BaseAsyncScraper(BaseScraper):
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

    async def scrape_all(self, *args, **kwargs) -> None:
        raise NotImplementedError("scrape_all() not implemented")

    async def _scrape_one(self, *args, **kwargs) -> None:
        raise NotImplementedError("_scrape_one() not implemented")

    async def _load_tasks(self, *args, **kwargs) -> list[Any]:
        raise NotImplementedError("_load_tasks() not implemented")
