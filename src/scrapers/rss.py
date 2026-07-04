import logging
import math
import sys
from datetime import datetime
from typing import Any
from urllib.parse import quote

import feedparser
from pydantic import ValidationError
from tqdm.auto import tqdm

from config import RssScraperConfig
from exceptions import RateLimitedError
from models import ArticleModel, ProjectModel
from utils import JsonlCheckpointWriter, sleep_norm, thread_map_bounded
from utils.constants import BLOCKED_SOURCES, EXCLUDED_SEARCH_TERMS

logger = logging.getLogger(__name__)


class RssScraper:
    def __init__(
        self, writer: JsonlCheckpointWriter, config: RssScraperConfig | None = None
    ):
        self.writer = writer
        self.config = config or RssScraperConfig()

    def scrape_all(self):
        remaining_projects = self.writer.load_remaining()

        if len(remaining_projects) == 0:
            logger.info("Nothing to scrape.")
            return None
        else:
            num_completed = len(self.writer.load_completed_keys())
            print(f"Found {num_completed} existing feeds!")
            logger.info(f"Found {num_completed} existing feeds!")

            print(f"{len(remaining_projects)} feeds left to scrape!")
            logger.info(f"{len(remaining_projects)}! feeds left to scrape")

        for i in tqdm(
            range(0, len(remaining_projects), self.config.batch.size),
            total=math.ceil(len(remaining_projects) / self.config.batch.size),
            desc="RSS: Processing Batch",
            disable=not self.config.show_progress,
            position=0,
        ):
            batch = remaining_projects[i : i + self.config.batch.size]
            blocked = self._dispatch_batch(batch)

            if blocked:
                # stop trying to scrape
                logger.error("Possibly rate limited!!")
                print("You may have been rate limited by Google!")
                sys.exit(1)

            # sleep to avoid hammering Google RSS.
            sleep_norm(
                self.config.batch.sleep_s_base,
                self.config.batch.jitter_s_mu,
                self.config.batch.jitter_s_sigma,
            )

    def _dispatch_batch(self, batch: list[dict[str, Any]]) -> bool:
        """
        Orchestrates fetching of feeds for a batch of projects.

        :param batch: Multiple rows of output from ListingScraper.
        :return: True if a block is detected during this batch.
        """
        blocked = False

        def on_error(_, exc):
            nonlocal blocked
            if isinstance(exc, RateLimitedError):
                blocked = True

        # get feed and save
        thread_map_bounded(
            items=batch,
            fn=self._fetch_one_feed,
            max_workers=self.config.max_workers,
            on_error=on_error,
        )

        return blocked

    def _fetch_one_feed(self, project: dict[str, Any]) -> None:
        """
        Validates project data, builds a specific query string, and writes headline
        data returned by Google's RSS Feed.

        :param project: One row of output from ListingScraper
        :return: None
        """
        # validate project data
        try:
            project = ProjectModel.model_validate(project)
        except ValidationError as e:
            logger.error(f"Failed to validate project data: {e}!")
            return None

        # fetch the feed
        url = self._build_query(project)
        feed = feedparser.parse(url)

        if feed.status >= 400:
            logger.error(f"Likely blocked by Google RSS: {feed.status}!")
            raise RateLimitedError(f"HTTP {feed.status} from Google RSS.")

        # process the feed
        articles = []
        for entry in feed.entries:
            # remove source name from the headline
            source = entry.source.title
            headline = entry.title.replace(f"- {source}", "").strip()

            # format date
            published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %Z")

            if source in BLOCKED_SOURCES:
                # exclude junk such as job listings
                continue

            article = ArticleModel(
                slug=project.slug,
                headline=headline,
                published=published,
                source=source,
                rss_url=entry.link,
            )

            articles.append(article.model_dump())

        # write data
        if len(articles) != 0:
            self.writer.write(articles)
            return None

        return None

    @staticmethod
    def _build_query(project: ProjectModel):
        """
        Builds the URL for Google RSS given project data.

        :param project: Validated ProjectModel
        :return: The URL
        """
        base_phrase = (
            f'"{project.company}" "data center" '
            f"(proposed OR announced OR opposed OR groundbreaking OR "
            f'"construction" OR "breaks ground" OR live OR delayed '
            f"cancelled OR halt OR permit OR rezoning)"
        )

        exclude_phrase = " ".join([f"-{term}" for term in EXCLUDED_SEARCH_TERMS])
        locale_phrase = (
            f'"{project.city.replace("-", " ")}" {project.state.replace("-", " ")}'
        )

        raw_query = f"{base_phrase} {locale_phrase} {exclude_phrase}"

        url = f"https://news.google.com/rss/search?q={quote(raw_query)}&hl=en-US&gl=US&ceid=US:en"

        return url
