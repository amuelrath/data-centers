import dataclasses

from playwright.async_api import Browser as AsyncBrowser
from playwright.async_api import BrowserContext as AsyncBrowserContext
from playwright.async_api import Playwright as AsyncPlaywright
from playwright.async_api import async_playwright
from playwright.sync_api import Browser as SyncBrowser
from playwright.sync_api import BrowserContext as SyncBrowserContext
from playwright.sync_api import Playwright as SyncPlaywright
from playwright.sync_api import sync_playwright

from config import PlaywrightContextConfig
from utils.constants import STEALTH_INIT_SCRIPT


def launch_sync_client(
    config: PlaywrightContextConfig, headless: bool
) -> tuple[SyncPlaywright, SyncBrowser, SyncBrowserContext]:
    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=headless, args=["--disable-blink-features=AutomationControlled"]
    )
    context = browser.new_context(
        **{k: v for k, v in dataclasses.asdict(config).items() if v is not None}
    )
    context.add_init_script(STEALTH_INIT_SCRIPT)

    return playwright, browser, context


def close_sync_client(
    playwright: SyncPlaywright, browser: SyncBrowser, context: SyncBrowserContext
) -> None:
    context.close()
    browser.close()
    playwright.stop()


# **************************************************************


async def launch_async_client(
    config: PlaywrightContextConfig, headless: bool
) -> tuple[AsyncPlaywright, AsyncBrowser, AsyncBrowserContext]:
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=headless, args=["--disable-blink-features=AutomationControlled"]
    )
    context = await browser.new_context(
        **{k: v for k, v in dataclasses.asdict(config).items() if v is not None}
    )
    await context.add_init_script(STEALTH_INIT_SCRIPT)

    return playwright, browser, context


async def close_async_client(
    playwright: AsyncPlaywright, browser: AsyncBrowser, context: AsyncBrowserContext
) -> None:
    await context.close()
    await browser.close()
    await playwright.stop()
