import logging

import reverse_geocoder as rg
from playwright.async_api import Locator as AsyncLocator
from playwright.async_api import Page as AsyncPage
from playwright.sync_api import Locator as SyncLocator
from playwright.sync_api import Page as SyncPage
from pydantic import ValidationError

from models import ProjectExtractModel, ProjectSuccess
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


async def extract_listing(page: AsyncPage) -> ProjectSuccess | None:
    """
    Extracts and validates the details from a datacenters.com site listing.
    Additionally geocodes by lat/lon to get county.

    Note::

    If a numeric value is 0, then it is likely missing / not provided.

    :param page: The Playwright ``Page`` object.
    :return: A dict containing details found on the page, or None on failure.
    """

    await page.wait_for_selector(".leaflet-container", state="attached")

    raw = None
    try:
        raw = await page.evaluate(PROJECT_EXTRACT_SCRIPT)
        extract = ProjectExtractModel.model_validate(raw)
    except ValidationError:
        logging.error(f"Failed to validate extracted JSON!: {str(raw or None)}")
        return None
    except Exception as e:
        logging.error(f"Unknown exception occurred while trying to extract data! {e}")
        return None

    total_space_sqft = await extract_sqft(page)
    county = rg.get(
        (extract.latitude, extract.longitude),
        mode=1,  # single threaded kd tree
    )["admin2"]

    return ProjectSuccess(
        slug=page.url.split(".com/")[1],
        listing_url=page.url,
        name=extract.name,
        company=extract.company,
        total_power_mw=extract.total_power_mw,
        latitude=extract.latitude,
        longitude=extract.longitude,
        city=extract.city,
        county=county,
        state=extract.state,
        description=extract.description,
        full_address=extract.full_address,
        gross_colocation_space=extract.gross_colocation_space,
        gross_building_size=extract.gross_building_size,
        company_slug=extract.company_slug,
        total_space_sqft=total_space_sqft,
        created_at=extract.created_at,
    )


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
