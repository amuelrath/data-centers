from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, HttpUrl, TypeAdapter, field_validator


class ProjectSuccess(BaseModel):
    status: Literal["ok"] = "ok"
    slug: str
    name: str
    company: str
    company_slug: str
    latitude: float
    longitude: float
    total_power_mw: float | None = None  # legitimately sometimes unknown
    city: str
    county: str
    state: str
    description: str | None = None
    full_address: str | None = None
    gross_building_size: int | None = None
    gross_colocation_space: int | None = None
    total_space_sqft: float | None = None
    created_at: str
    listing_url: HttpUrl


class ProjectError(BaseModel):
    status: Literal["error"] = "error"
    slug: str
    listing_url: HttpUrl | None = None
    error: Literal["404", "timeout", "unknown"]


class ProjectExtractModel(BaseModel):
    """
    Partial ProjectModel populated from JS-evaluated React state.
    Intentionally partial. markup-sourced fields are merged in later.
    """

    name: str
    company: str
    company_slug: str
    latitude: float
    longitude: float
    total_power_mw: float | None = None
    city: str
    state: str
    created_at: str
    description: str | None = None
    full_address: str | None = None
    gross_building_size: int | None = None
    gross_colocation_space: int | None = None
    error: Literal["404", "timeout", "unknown"] | None = None

    @field_validator("total_power_mw", "latitude", "longitude", mode="before")
    @classmethod
    def blank_or_nan_to_none(cls, v):
        if v is None or v == "":
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        if f != f:  # NaN check. JS sometimes serializes NaN as the string "NaN"
            return None
        return f

    @field_validator(
        "name",
        "company",
        "company_slug",
        "city",
        "state",
        "description",
        "full_address",
        mode="before",
    )
    @classmethod
    def blank_str_to_none(cls, v):
        if isinstance(v, str) and v.strip() == "":
            return None
        return v

    @field_validator(
        "total_power_mw", "gross_colocation_space", "gross_building_size", mode="before"
    )
    @classmethod
    def zero_to_none(cls, v):
        if v is None or v == "":
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return None if f != f or f == 0 else f


ExtractAdapter = TypeAdapter(ProjectExtractModel)
ProjectResult = Annotated[
    Union[ProjectSuccess, ProjectError],
    Field(discriminator="status"),
]
ProjectAdapter = TypeAdapter(ProjectResult)
