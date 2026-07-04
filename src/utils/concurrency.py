import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Awaitable, Callable, TypeVar

from tqdm import tqdm

logger = logging.getLogger(__name__)

T = TypeVar("T")
R = TypeVar("R")


async def async_gather_bounded(
    items: list[T],
    coro_fn: Callable[[T], Awaitable[R]],
    max_concurrency: int,
    on_error: Callable[[T, Exception], None] | None = None,
) -> list[R | None]:
    """
    Run coro_fn(item) over items with bounded concurrency.
    Isolates per-item exceptions so one failure doesn't kill the whole batch.
    Returns results in the same order as items; failed items are None.
    """
    sem = asyncio.Semaphore(max_concurrency)

    async def _bound(item: T) -> R | None:
        async with sem:
            try:
                result = await coro_fn(item)
            except Exception as e:
                logger.warning(f"Failed on item {item!r}: {e!r}")
                if on_error:
                    on_error(item, e)
                result = None

            return result

    return await asyncio.gather(*(_bound(item) for item in items))


def thread_map_bounded(
    items: list[T],
    fn: Callable[[T], R],
    max_workers: int,
    on_error: Callable[[T, Exception], None] | None = None,
) -> list[R | None]:
    """
    Run fn(item) over items using a bounded thread pool.
    Isolates per-item exceptions; returns results (None for failures),
    preserving input order.
    """

    results: list[R | None] = [None] * len(items)

    logger.info("Starting thread_map_bounded...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_index = {
            executor.submit(fn, item): idx for idx, item in enumerate(items)
        }

        for future in as_completed(future_to_index):
            idx = future_to_index[future]
            item = items[idx]
            try:
                results[idx] = future.result()
            except Exception as e:
                logger.warning(f"Failed on item {item!r}: {e!r}")
                if on_error:
                    on_error(item, e)
                results[idx] = None

    return results
