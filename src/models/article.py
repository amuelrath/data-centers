from typing import Literal

from pydantic import BaseModel


class ArticleModel(BaseModel):
    slug: str | None = None
    content: str | None = None
    rss_url: str | None = None
    decoded_url: str | None = None
    error: Literal["flagged", "timeout", "topn", "no_articles", "unknown"] | None = None
