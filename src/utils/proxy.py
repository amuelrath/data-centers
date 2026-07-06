import logging
import os

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def build_proxy() -> str | None:
    load_dotenv()
    USERNAME = os.getenv("DECODO_USERNAME")
    PASSWORD = os.getenv("DECODO_PASSWORD")

    if not USERNAME or not PASSWORD:
        logger.info("No decodo username or password found in .env. Skipping proxy use.")
        proxies = None
    else:
        proxy_url = f"https://{USERNAME}:{PASSWORD}@gate.decodo.com:10000"
        proxies = {"http": proxy_url, "https": proxy_url}

    return proxies