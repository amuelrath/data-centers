import asyncio
import logging
from pathlib import Path

from config import ArticleScraperConfig, PlaywrightScraperConfig
from scrapers import ListingScraper, ListingUrlScraper
from scrapers.articles import ArticleScraper
from scrapers.rss import RssScraper
from utils import JsonlCheckpointWriter

OUT_PATH = Path("data")

logger = logging.getLogger(__name__)


def main():
    """Execute the main pipeline"""
    print("Beginning Scraper...")
    setup_logging()
    logger.info("****STARTING NEW RUN****")

    run_listing_url_scraper()

    print("Scraping Listings... (May take a while)")
    asyncio.run(run_listing_scraper_async())

    print("Scraping Rss Feeds... (May take a while)")
    run_rss_scraper()

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


def run_rss_scraper() -> None:
    """Fetches RSS feeds about each datacenter"""
    rss_writer = JsonlCheckpointWriter(
        in_path=OUT_PATH / "projects.jsonl",
        out_path=OUT_PATH / "headlines.jsonl",
        key_field="slug",
    )
    scraper = RssScraper(rss_writer)
    scraper.scrape_all()


async def run_article_scraper_async() -> None:
    """Scrapes articles from the RSS feed"""
    article_writer = JsonlCheckpointWriter(
        in_path=OUT_PATH / "headlines.jsonl",
        out_path=OUT_PATH / "articles.jsonl",
        key_field="rss_url",
    )

    async with ArticleScraper(
        article_writer,
        config=ArticleScraperConfig(
            playwright=PlaywrightScraperConfig(max_concurrency=5)
        ),
    ) as scraper:
        await scraper.scrape_all()


if __name__ == "__main__":  # noqa: F821
    main()
