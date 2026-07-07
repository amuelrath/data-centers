import logging
import os
from typing import Literal

logger = logging.getLogger(__name__)


def build_proxy(
    returns: Literal["requests", "playwright"] = "requests",
) -> dict[str, str] | None:
    """

    :param returns: The format to return the proxy in.
    :return: If "requests" returns ``{ "http": ..., "https": ... }``.
     If "playwright" returns ``{ "server": ..., "username":..., "password":... }``
    """
    USERNAME = os.getenv("DECODO_USERNAME")
    PASSWORD = os.getenv("DECODO_PASSWORD")

    if not USERNAME or not PASSWORD:
        logger.info("No decodo username or password found in .env. Skipping proxy use.")
        return None

    server = "http://gate.decodo.com:10000"

    if returns == "requests":
        url = f"http://{USERNAME}:{PASSWORD}@gate.decodo.com:10000"
        return {"http": url, "https": url}

    if returns == "playwright":
        return {"server": server, "username": USERNAME, "password": PASSWORD}

    return None
