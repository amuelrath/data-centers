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
    "revenue",
    "earnings",
    "ipo",
]
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
