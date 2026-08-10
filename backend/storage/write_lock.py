"""Cross-process exclusive lock for Parquet read-modify-write updates."""

from __future__ import annotations

import fcntl
import logging
import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

logger = logging.getLogger(__name__)

DEFAULT_LOCK_PATH = Path(
    os.getenv("DATA_LOCK_PATH", "/tmp/atp-analytics-data.lock")
)


@contextmanager
def data_write_lock(
    lock_path: Path | None = None,
    *,
    timeout: float | None = 3600.0,
    poll_interval: float = 0.25,
) -> Iterator[None]:
    """
    Hold an exclusive flock for the duration of a data write critical section.

    Use around load → merge → save so concurrent scrapes cannot overwrite
    each other's Parquet/S3 updates. Scraping itself should happen *outside*
    this lock.
    """
    path = lock_path or DEFAULT_LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("a+", encoding="utf-8") as fh:
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if deadline is not None and time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Timed out after {timeout}s waiting for data write lock "
                        f"at {path}"
                    ) from exc
                time.sleep(poll_interval)

        logger.debug("Acquired data write lock (%s)", path)
        try:
            yield
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            logger.debug("Released data write lock (%s)", path)
