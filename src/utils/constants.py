import re

EXCLUDED_SEARCH_TERMS = [
    "crypto",
    "merger",
    "sports",
    "celebrity",
    "senate",
    "congress",
    "trump",
    "obituary",
    "food",
    "travel",
    "earnings call",
    "quarterly earnings",
    "ipo",
]

LIFECYCLE_TERMS = [
    "proposed",
    "announced",
    '"land purchase"',
    '"acquires land"',
    "rezoning",
    '"site plan"',
    "permit",
    "groundbreaking",
    '"breaks ground"',
    "construction",
    "operational",
    "online",
    "energized",
    '"now open"',
    "delayed",
    "cancelled",
    "halt",
    "paused",
    "opposed",
    "opposition",
    "protest",
    "lawsuit",
    "appeal",
    "moratorium",
    "rejected",
    "denied",
]

# Article Filtering

BLOCKED_SOURCES = [
    "LinkedIn",
    "Datacenters.com",
    "Indeed",
    "24/7 Wall St.",
]
BOT_FLAGS = [
    "security check",
    "access blocked",
    "verify you are human",
    "verifying you are human",
    "checking your browser",
    "needs to review the security",
    "were checking your connection to prevent automated abuse",
    "performance & security by cloudflare",
    "enable javascript and cookies",
    "please complete the security check",
    "are you a robot",
    "access denied",
    "captcha",
    "ray id",
    "reference id",
    "you have the right to opt-out of targeted advertising",
    "checking the site connection security",
    "access to this page is forbidden.",
    "forbidden",
    "performing security verification",
    "making sure you're not a bot ",
]
SIDEBAR_INFO_SEL = ".flex.flex-col.gap-2\\.5.p-7.text-black.bg-gray-50.rounded-b-md"
SIDEBAR_SPECS_SEL = ".flex.flex-col.gap-2\\.5"
SPACE_RE = re.compile(r"([\d,.]+)\s*sqft total space")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; 25078RA3EL Build/AP3A.240905.015.A2; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/149.0.7827.159 Mobile Safari/537.36",
    "Mozilla/5.0 (Android 10; Mobile; rv:130.0) Gecko/12021440 Firefox/130.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/37.0.2062.94 Chrome/37.0.2062.94 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; Trident/7.0; rv:11.0) like Gecko",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/600.8.9 (KHTML, like Gecko) Version/8.0.8 Safari/600.8.9",
    "Mozilla/5.0 (iPad; CPU OS 8_4_1 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12H321 Safari/600.1.4",
    "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/42.0.2311.135 Safari/537.36 Edge/12.10240",
    "Mozilla/5.0 (Windows NT 6.3; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Windows NT 6.3; WOW64; Trident/7.0; rv:11.0) like Gecko",
    "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; Trident/7.0; rv:11.0) like Gecko",
    "Mozilla/5.0 (Windows NT 10.0; WOW64; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_4) AppleWebKit/600.7.12 (KHTML, like Gecko) Version/8.0.7 Safari/600.7.12",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.85 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.10; rv:40.0) Gecko/20100101 Firefox/40.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_5) AppleWebKit/600.8.9 (KHTML, like Gecko) Version/7.1.8 Safari/537.85.17",
    "Mozilla/5.0 (iPad; CPU OS 8_4 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12H143 Safari/600.1.4",
    "Mozilla/5.0 (iPad; CPU OS 8_3 like Mac OS X) AppleWebKit/600.1.4 (KHTML, like Gecko) Version/8.0 Mobile/12F69 Safari/600.1.4",
    "Mozilla/5.0 (Windows NT 6.1; rv:40.0) Gecko/20100101 Firefox/40.0",
]


# language=JavaScript
PROJECT_EXTRACT_SCRIPT = """
                  (() => {
                 try {
                     const el = document.querySelector(".leaflet-container");
                     if (!el) return {error: "no leaflet container found"};

                     const fiberKey = Object.keys(el).find(k => k.startsWith("__reactFiber"));


                     let node = el[fiberKey];
                     while (node) {
                         if (node.memoizedProps?.map || node.memoizedState?.map) {
                             break;
                         }
                         node = node.return;
                     }

                     if (!node) return {error: "could not find node with map prop"};

                     const locationProps = node.memoizedProps?.[0]?._payload?.value?.props?.location;
                     if (!locationProps) return {error: "no location props found"};

                     return {
                         name: locationProps.name ?? null,
                         company: locationProps.provider?.name ?? null,
                         company_slug: locationProps.provider?.slug ?? null,
                         latitude: locationProps.latitude ?? null,
                         longitude: locationProps.longitude ?? null,
                         power_density: locationProps.powerDensity ?? null,
                         total_power_mw: locationProps.totalPowerMw ?? null,
                         city: locationProps.locationDemographic?.city?.slug ?? null,
                         state: locationProps.locationDemographic?.state?.slug ?? null,
                         error: null
                     };
                 } catch (e) {
                    return { error: e }
                 }
             })() \
             """

# language=JavaScript
COOKIE_BANNER_REMOVE_SCRIPT = """
    document
        .querySelectorAll('[class*="cookie"], [class*="consent"], [id*="cookie"], [id*="consent"]')
        .forEach(el => el.remove());
    """
PW_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}
PW_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)
DEBUG_ENABLED = False
