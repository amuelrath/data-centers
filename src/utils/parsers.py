import asyncio
import logging
import re

from playwright.async_api import Locator as AsyncLocator
from playwright.async_api import Page as AsyncPage
from playwright.sync_api import Locator as SyncLocator
from playwright.sync_api import Page as SyncPage
from pydantic import ValidationError

from models import ProjectExtractModel
from utils.constants import PROJECT_EXTRACT_SCRIPT, SIDEBAR_SPECS_SEL, SPACE_RE

# Parsers for ListingUrlScraper


def extract_anchors_from_location_grid(page: SyncPage) -> list[SyncLocator]:
    """
    Extracts the ``<a/>`` elements from the locations-grid once it is visible.

    :param page: The Playwright ``Page`` object.
    :return: ``<a/>`` elements within the page's locations-grid element.
    """
    locations_grid = page.get_by_test_id("locations-grid")
    locations_grid.wait_for(state="visible")
    return locations_grid.locator("a").all()


def extract_buttons(page: SyncPage) -> tuple[SyncLocator, SyncLocator]:
    """
    Extracts the next and previous page buttons.

    :param page: The Playwright ``Page`` object.
    :return: ``(next_page_button, prev_page_button)``
    """
    next_page_button = page.get_by_test_id("next-page-button")
    prev_page_button = page.get_by_test_id("prev-page-button")

    return next_page_button, prev_page_button


def extract_page_pagination(page: SyncPage) -> tuple[int, int]:
    """
    :param page: The Playwright ``Page`` object.
    :return: ``current_page``, ``num_pages``
    """
    el = page.get_by_test_id("page-info")

    # will be "Page X of Y"
    text = el.inner_text()

    current_page = int(text.split(" ")[1].strip())
    num_pages = int(text.split(" ")[3].strip())

    return current_page, num_pages


# Parsers for ListingScraper


async def extract_map_button(page: AsyncPage) -> AsyncLocator:
    map_button = page.get_by_role("tab", name="On Map")
    return map_button


async def extract_listing(page: AsyncPage) -> ProjectExtractModel | None:
    """
    Extracts and validates the details from a datacenters.com site listing.

    Note::

    If a numeric value is 0, then it is likely missing / not provided.

    :param page: The Playwright ``Page`` object.
    :return: A dict containing details found on the page, or None on failure.
    """

    await page.wait_for_selector(".leaflet-container", state="attached")

    try:
        raw = await page.evaluate(PROJECT_EXTRACT_SCRIPT)
        data = ProjectExtractModel.model_validate(raw)
    except ValidationError:
        logging.error("Failed to validate extracted JSON!")
        return None
    except Exception as e:
        logging.error(f"Unknown exception occurred while trying to extract data! {e}")
        return None

    details, total_space_sqft = await asyncio.gather(
        extract_details(page),
        extract_sqft(page),
    )

    return {
        "slug": page.url.split(".com/")[1],
        "listing_url": page.url,
        "name": data.name,
        "company": data.company,
        "total_space_sqft": total_space_sqft,
        "capacity_mw": data.total_power_mw,
        "power_density": data.power_density,
        "details": details,
        "latitude": data.latitude,
        "longitude": data.longitude,
        "city": data.city,
        "state": data.state,
        "company_slug": data.company_slug,
    }


async def extract_details(page: AsyncPage) -> str | None:
    paragraphs = await page.locator("#contentDescription p").all_inner_texts()
    text = " ".join(p.strip() for p in paragraphs if p.strip())
    return text or None


async def extract_sqft(page: AsyncPage) -> float | None:
    """
    Extracts total space (sqft) sidebar specs.

    :param page: The Playwright ``Page`` object.
    :return: The total space or None
    """
    texts = (
        await page.locator("#sidebar")
        .locator(SIDEBAR_SPECS_SEL)
        .locator("div")
        .all_inner_texts()
    )

    total_space_sqft = None
    for t in texts:
        if total_space_sqft is None and (m := SPACE_RE.search(t)):
            total_space_sqft = float(m.group(1).replace(",", ""))

    return total_space_sqft


async def extract_is_404(page: AsyncPage) -> bool:
    """
    Returns true if the listing we are on is a 404

    :param page: The Playwright ``Page`` object.
    :return: True if we have reached a 404
    """
    msg_404 = page.locator("h1.text-4xl.font-semibold.text-black.mb-4")

    if await msg_404.count() == 0:
        return False

    msg = await msg_404.inner_text()
    return msg.strip() == "Oops...Page not found"


# Parsers for ArticleScraper


def extract_clean_text(txt: str | None) -> str | None:
    """Remove extra junk included in trafilatura extractions"""
    if not txt:
        return None

    txt = txt.replace("\x0a", " ")

    # removes just non-ascii characters
    return re.sub(r"[^\x20-\x7E\n]", "", txt).strip()
