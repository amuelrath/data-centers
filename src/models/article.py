from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, HttpUrl, TypeAdapter


class HeadlineSuccess(BaseModel):
    """What we know after step 1. Before we've fetched full article text."""

    status: Literal["ok"] = "ok"
    slug: str
    title: str
    rss_url: HttpUrl
    published: datetime
    source: str


class HeadlineError(BaseModel):
    status: Literal["error"] = "error"
    slug: str
    error: Literal["no_articles"]


class ArticleSuccess(BaseModel):
    status: Literal["ok"] = "ok"
    slug: str
    title: str
    rss_url: HttpUrl
    decoded_url: HttpUrl
    published: datetime
    source: str
    text: str


class ArticleError(BaseModel):
    status: Literal["error"] = "error"
    slug: str
    rss_url: HttpUrl
    decoded_url: HttpUrl | None = None
    error: Literal[
        "flagged",
        "empty",
    ]


HeadlineResult = Annotated[
    Union[HeadlineSuccess, HeadlineError], Field(discriminator="status")
]
HeadlineAdapter = TypeAdapter(HeadlineResult)

ArticleResult = Annotated[
    Union[ArticleSuccess, ArticleError], Field(discriminator="status")
]
ArticleAdapter = TypeAdapter(ArticleResult)
