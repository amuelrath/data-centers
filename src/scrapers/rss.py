import logging
import math
import os
import random
import time
from datetime import datetime
from typing import List
from urllib.parse import quote

import feedparser
import requests
from requests import HTTPError
from tqdm.auto import tqdm

from config import RssScraperConfig
from models import (
    HeadlineError,
    HeadlineSuccess,
    ProjectAdapter,
    ProjectSuccess,
)
from utils import JsonlCheckpointWriter, build_proxy, thread_map_bounded
from utils.constants import EXCLUDED_SEARCH_TERMS, USER_AGENTS

logger = logging.getLogger(__name__)


class RssScraper:
    """
    Uses ``gnews`` to fetch RSS feeds for each project.
    """

    def __init__(
        self, writer: JsonlCheckpointWriter, config: RssScraperConfig | None = None
    ):
        self.writer = writer
        self.config = config or RssScraperConfig()

    def scrape_all(self):
        """
        Scrapes and writes RSS feed data.

        :return: None
        """
        remaining_projects = [
            ProjectAdapter.validate_python(d) for d in self.writer.load_remaining()
        ]

        if len(remaining_projects) == 0:
            logger.info("Nothing to scrape.")
            return None
        else:
            num_completed = len(self.writer.load_completed_keys())
            print(f"Found {num_completed} existing feeds!")
            logger.info(f"Found {num_completed} existing feeds!")

            print(f"{len(remaining_projects)} feeds left to scrape!")
            logger.info(f"{len(remaining_projects)} feeds left to scrape")

        for i in tqdm(
            range(0, len(remaining_projects), self.config.batch.size),
            total=math.ceil(len(remaining_projects) / self.config.batch.size),
            disable=not self.config.show_progress,
            desc="RSS: Processing Batch",
        ):
            batch = remaining_projects[i : i + self.config.batch.size]
            self._dispatch_batch(batch)

        return None

    def _dispatch_batch(self, batch: List[ProjectSuccess]) -> None:
        """
        :param batch: list of ProjectSuccess to fetch feeds for
        :return: None
        """
        thread_map_bounded(
            items=batch, fn=self._scrape_one, max_workers=self.config.max_workers
        )

    def _scrape_one(self, project: ProjectSuccess) -> None:
        """

        :return: None
        """
        # wait...
        time.sleep(random.uniform(self.config.jitter_min_s, self.config.jitter_max_s))

        # build the request
        url = self._build_query_url(project)
        proxies, user_agent = self._build_request_params()
        res = requests.get(
            url,
            proxies=proxies,
            headers={"User-Agent": user_agent},
            timeout=self.config.timeout_s,
        )

        try:
            res.raise_for_status()
        except HTTPError as e:
            logger.error(f"HTTP Error: {e}")
            if e.response.status_code >= 400:
                # was probably a rate limiting error.
                # do not write anything so we retry later.
                logger.critical(f"Rate Limited by Google RSS! UA: {user_agent}")
                print("Rate limited by Google RSS. Please wait a few hours...")
                # kill all threads
                os._exit(1)
            logger.error(f"HTTP Error: {e}, will retry later")
        except Exception as e:
            # do not write anything so we retry later.
            logger.error(f"Unhandled exception occurred: {e}")
            return None

        feed = feedparser.parse(res.content)

        if len(feed) == 0:
            logger.debug(f"No headlines returned for {project.slug}.")
            # write a blank row so that we don't refetch this later
            return self.writer.write(
                HeadlineError(slug=project.slug, error="no_articles").model_dump()
            )

        articles = []
        for entry in feed.entries:
            # remove source from title
            source = entry.source.title
            title = entry.title.replace(f"- {source}", "").strip()

            # parse date
            published = datetime.strptime(entry.published, "%a, %d %b %Y %H:%M:%S %Z")

            articles.append(
                HeadlineSuccess(
                    slug=project.slug,
                    title=title,
                    source=source,
                    published=published,
                    rss_url=entry.link,
                ).model_dump()
            )

        # write the data
        return self.writer.write(articles)

    @staticmethod
    def _build_query_url(project: ProjectSuccess) -> str:
        """
        Builds the Google RSS URL.

        :param project: ProjectModel
        :return: The URL
        """
        base_phrase = (
            f'"{project.company}" "data center" '
            f"(proposed OR announced OR opposed OR groundbreaking OR "
            f'construction OR "breaks ground" OR live OR delayed '
            f"cancelled OR halt OR permit OR rezoning OR protest)"
        )

        exclude_phrase = " ".join([f"-{term}" for term in EXCLUDED_SEARCH_TERMS])
        locale_phrase = (
            f'"{project.city.replace("-", " ")}" {project.state.replace("-", " ")}'
        )

        query = f"{base_phrase} {locale_phrase} {exclude_phrase}"

        return f"https://news.google.com/rss/search?q={quote(query)}&hl=en-US&gl=US&ceid=US:en"

    @staticmethod
    def _build_request_params() -> tuple[dict[str, str] | None, str]:
        """
        Builds an HTTPS proxy using decodo and selects random UA
        Decodo offers a free trial which should be enough to collect all the data.

        Optional but recommended, as Google RSS can rate limit quite aggressively.

        :return: ``proxies``, ``user_agent``
        """
        proxies = build_proxy()
        user_agent = random.choice(USER_AGENTS)

        return proxies, user_agent
