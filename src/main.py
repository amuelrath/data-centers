import asyncio
import logging
import os
from pathlib import Path

from dotenv import load_dotenv

from config import ArticleScraperConfig, NewsScraperConfig, PlaywrightScraperConfig
from scrapers import ArticleScraper, ListingScraper, ListingUrlScraper, NewsScraper
from utils import JsonlCheckpointWriter

OUT_PATH = Path("data")
load_dotenv()

logger = logging.getLogger(__name__)


def main():
    """Execute the main pipeline"""
    print("Beginning Scraper...")
    setup_logging()
    logger.info("****STARTING NEW RUN****")

    print("Scraping Listings... (May take a while)")
    run_listing_url_scraper()
    asyncio.run(run_listing_scraper_async())

    print("Scraping News Feeds... (May take a while)")
    run_feed_scraper()

    print("Scaping Articles... (May take a while)")
    asyncio.run(run_article_scraper_async())

    print("Scraping Complete!")


def setup_logging():
    logging.basicConfig(
        filename="scraper.log",
        filemode="a",
        format="%(asctime)s,%(msecs)03d %(name)-20.20s %(levelname)-8s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.DEBUG,
    )


def run_listing_url_scraper() -> None:
    """Scrapes URLs for Datacenter site listings"""
    listing_url_writer = JsonlCheckpointWriter(
        path=OUT_PATH / "listing_urls.jsonl", key_field="listing_url"
    )
    with ListingUrlScraper(listing_url_writer) as scraper:
        scraper.scrape_all()


async def run_listing_scraper_async() -> None:
    """Scrapes details about each datacenter"""
    listing_writer = JsonlCheckpointWriter(
        in_path=OUT_PATH / "listing_urls.jsonl",
        out_path=OUT_PATH / "projects.jsonl",
        key_field="listing_url",
    )
    async with ListingScraper(listing_writer) as scraper:
        await scraper.scrape_all()


def run_feed_scraper() -> None:
    """Fetches RSS feeds about each datacenter"""

    rss_writer = JsonlCheckpointWriter(
        in_path=OUT_PATH / "projects.jsonl",
        out_path=OUT_PATH / "headlines.jsonl",
        key_field="slug",
    )
    scraper = NewsScraper(
        rss_writer, config=NewsScraperConfig(searchapi_key=os.getenv("SEARCH_API_KEY"))
    )
    scraper.scrape_all()


async def run_article_scraper_async() -> None:
    """Scrapes articles from the RSS feed"""
    article_writer = JsonlCheckpointWriter(
        in_path=OUT_PATH / "headlines.jsonl",
        out_path=OUT_PATH / "articles.jsonl",
        key_field="url",
    )

    async with ArticleScraper(
        article_writer,
        config=ArticleScraperConfig(
            playwright=PlaywrightScraperConfig(max_concurrency=3)
        ),
    ) as scraper:
        await scraper.scrape_all()


if __name__ == "__main__":  # noqa: F821
    main()
