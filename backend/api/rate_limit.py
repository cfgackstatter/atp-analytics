"""Simple in-memory sliding-window rate limiter for admin routes."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status


class SlidingWindowRateLimiter:
    """Thread-safe per-key limiter: at most ``max_requests`` per ``window_seconds``."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def hit(self, key: str) -> None:
        """Record a hit for ``key`` or raise 429 if the window is full."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests; try again later",
                )
            hits.append(now)


# Generous enough for the admin UI poll (every 5s) + manual actions.
_admin_limiter = SlidingWindowRateLimiter(max_requests=60, window_seconds=60.0)


def client_ip(request: Request) -> str:
    """Best-effort client IP, honoring the first X-Forwarded-For hop."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip() or "unknown"
    if request.client is not None:
        return request.client.host
    return "unknown"


async def rate_limit_admin(request: Request) -> None:
    """FastAPI dependency: rate-limit admin API calls by client IP."""
    _admin_limiter.hit(client_ip(request))
