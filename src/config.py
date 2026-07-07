from dataclasses import dataclass, field

from utils.constants import DEBUG_ENABLED, PW_HEADERS, PW_USER_AGENT


@dataclass
class DebugConfig:
    enabled: bool = DEBUG_ENABLED
    # how many pages of listing urls to scrape
    # don't want to hammer websites while testing
    num_debug_pages: int = 2


@dataclass
class BatchConfig:
    size: int = 20


@dataclass
class PlaywrightContextConfig:
    user_agent: str | None = PW_USER_AGENT
    extra_http_headers: dict[str, str] | None = field(
        default_factory=lambda: PW_HEADERS
    )
    timezone_id: str = "America/Los_Angeles"
    viewport: dict[str, int] = field(
        default_factory=lambda: {"width": 1920, "height": 1080}
    )
    locale: str = "en-US"
    color_scheme: str = "dark"
    reduced_motion: str = "no-preference"
    service_workers: str = "block"
    accept_downloads: bool = False
    device_scale_factor: int = 1
    java_script_enabled: bool = True


@dataclass
class PlaywrightScraperConfig:
    headless: bool = True
    show_progress: bool = True
    timeout_ms: int = 15_000
    max_concurrency: int = 10
    context: PlaywrightContextConfig = field(default_factory=PlaywrightContextConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)


@dataclass
class ArticleScraperConfig:
    show_progress: bool = True
    playwright: PlaywrightScraperConfig = field(default_factory=PlaywrightScraperConfig)
    batch: BatchConfig = field(default_factory=BatchConfig)
    debug: DebugConfig = field(default_factory=DebugConfig)


@dataclass
class RssScraperConfig:
    show_progress: bool = True
    max_workers: int = 8
    timeout_s: int = 10
    batch: BatchConfig = field(default_factory=BatchConfig)
