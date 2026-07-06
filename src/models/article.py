from typing import Literal

from pydantic import BaseModel


class ArticleModel(BaseModel):
    slug: str | None = None
    title: str | None = None
    description: str | None = None
    url: str | None = None
    published: str | None = None
    source: str | None = None
    text: str | None = None
    error: Literal["flagged", "timeout", "no_articles", "unknown"] | None = None
