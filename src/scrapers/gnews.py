import logging
import math
from typing import Any

from gnews import GNews
from pydantic import ValidationError
from tqdm.auto import tqdm

from config import NewsScraperConfig
from models import ArticleModel, ProjectModel
from utils import JsonlCheckpointWriter, thread_map_bounded
from utils.constants import EXCLUDED_SEARCH_TERMS

logger = logging.getLogger(__name__)


class NewsScraper:
    """
    Uses GNews with the Search API backend to fetch relevant news.
    """

    def __init__(
        self, writer: JsonlCheckpointWriter, config: NewsScraperConfig | None = None
    ):
        self.writer = writer
        self.config = config or NewsScraperConfig()

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
            logger.info(f"{len(remaining_projects)} feeds left to scrape")

        for i in tqdm(
            range(0, len(remaining_projects), self.config.batch.size),
            total=math.ceil(len(remaining_projects) / self.config.batch.size),
            desc="Feeds: Processing Batch",
            disable=not self.config.show_progress,
        ):
            batch = remaining_projects[i : i + self.config.batch.size]
            self._dispatch_batch(batch)

        return None

    def _dispatch_batch(self, batch: list[dict[str, Any]]) -> None:
        """

        :param batch: Multiple rows of output from ListingScraper.
        :return: None
        """
        # get the feeds and save
        thread_map_bounded(
            items=batch, fn=self._scrape_one, max_workers=self.config.max_workers
        )

        return None

    def _scrape_one(self, project: list[dict[str, Any]]) -> None:
        """
        :param project: The row of output from ListingUrlScraper
        :return: None
        """
        # create gnews.
        # using search api will prevent us from getting 503 errors.
        # also means we don't have to decode rss urls
        # only downside is that this costs money
        gnews = GNews(searchapi_key=self.config.searchapi_key)

        # validate project data
        try:
            project = ProjectModel.model_validate(project)
        except ValidationError as e:
            logger.error(f"Failed to validate project data: {e}!")
            return None

        # fetch the feed
        query = self._build_query(project)

        try:
            feed = gnews.get_news(query)
        except Exception as e:
            logger.warning(f"Error fetching feed for {project.slug}. {e}")
            return None

        if not feed:
            # fetching will NOT be retried on future runs.
            logger.debug(f"No articles found for {project.slug}")
            self.writer.write(
                ArticleModel(slug=project.slug, error="no_articles").model_dump()
            )
            return None

        for entry in feed:
            article = ArticleModel(
                slug=project.slug,
                title=entry.get("title"),
                description=entry.get("description"),
                url=entry.get("url"),
                published=entry.get("iso_date"),
                source=entry.get("publisher"),
            )

            self.writer.write(article.model_dump())

        return None

    @staticmethod
    def _build_query(project: ProjectModel) -> str:
        """
        Builds the query to forward to GNews().get_news()

        :param project: ProjectModel
        :return: The query phrase
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

        query = f"{base_phrase} {locale_phrase} {exclude_phrase}"

        return query
