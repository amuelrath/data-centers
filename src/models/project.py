from pydantic import BaseModel, field_validator


class ProjectModel(BaseModel):
    """Complete Project information."""

    slug: str | None = None
    name: str | None = None
    company: str | None = None
    company_slug: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    power_density: float | None = None
    total_power_mw: float | None = None
    city: str | None = None
    state: str | None = None
    details: str | None = None
    total_space_sqft: float | int | None = None
    err: str | None = None


class ProjectExtractModel(BaseModel):
    """
    Partial ProjectModel which validates data extracted from React.

    DOES NOT include data scraped directly from markup.

    """

    name: str | None = None
    company: str | None = None
    company_slug: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    power_density: float | None = None
    total_power_mw: float | None = None
    city: str | None = None
    state: str | None = None
    err: str | None = None

    @field_validator("power_density", "total_power_mw", mode="before")
    @classmethod
    def zero_to_none(cls, v: str | float | None) -> float | None:
        """Coerces numeric strings to float, treating 0/0.0 as missing data."""
        if v is None or v == "":
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            return None
        return None if f == 0 else f
