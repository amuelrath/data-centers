import logging
import math
import random
import time

logger = logging.getLogger(__name__)


def sleep_norm(min_s: float | int, mu_s: float | int, sigma_s: float | int) -> None:
    """
    Sleeps for a normally-distributed amount of seconds.

    :param min_s: The minimum seconds to sleep for.
    :param mu_s: Average seconds of jitter applied.
    :param sigma_s: Variance seconds of jitter applied.
    :return: None
    """
    len_s = math.fabs(min_s + random.normalvariate(mu_s, sigma_s))
    time.sleep(len_s)

    return None
