"""Optional HTTPS redirect + HSTS for deployments behind a TLS terminator."""

from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import RedirectResponse, Response


def force_https_enabled() -> bool:
    """Return True when FORCE_HTTPS is truthy (set in production)."""
    return os.getenv("FORCE_HTTPS", "").strip().lower() in {"1", "true", "yes", "on"}


def request_is_https(request: Request) -> bool:
    """Detect HTTPS using X-Forwarded-Proto (EB/ALB) or the raw URL scheme."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto.split(",", 1)[0].strip().lower() == "https"


# ELB/ALB probes are plain HTTP and must not be redirected or the instance
# never becomes healthy during rolling updates.
_HEALTH_PATHS = frozenset({"/health", "/health/"})


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Redirect HTTP → HTTPS when FORCE_HTTPS is enabled; set HSTS on HTTPS."""

    async def dispatch(self, request: Request, call_next) -> Response:
        if not force_https_enabled():
            return await call_next(request)

        path = request.url.path
        user_agent = request.headers.get("user-agent", "")
        if path in _HEALTH_PATHS or "ELB-HealthChecker" in user_agent:
            return await call_next(request)

        if not request_is_https(request):
            https_url = request.url.replace(scheme="https")
            return RedirectResponse(url=str(https_url), status_code=308)

        response = await call_next(request)
        response.headers.setdefault(
            "Strict-Transport-Security",
            "max-age=31536000; includeSubDomains",
        )
        return response
