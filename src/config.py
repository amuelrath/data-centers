from dataclasses import dataclass, field

HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEBUG_ENABLED = False


@dataclass
class DebugConfig:
    enabled: bool = DEBUG_ENABLED
    # how many pages of listing urls to scrape
    # don't want to hammer websites while testing
    num_debug_pages: int = 2


@dataclass
class BatchConfig:
    size: int = 20
    # normally distributed 30-100s wait between batches
    sleep_s_base: int | float = 30.0
    jitter_s_mu: int | float = 10.0
    jitter_s_sigma: int | float = 20.0


@dataclass
class PlaywrightContextConfig:
    user_agent: str | None = USER_AGENT
    extra_http_headers: dict[str, str] | None = field(default_factory=lambda: HEADERS)
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
class NewsScraperConfig:
    show_progress: bool = True
    searchapi_key: str | None = None
    max_workers: int = 10
    batch: BatchConfig = field(default_factory=BatchConfig)
