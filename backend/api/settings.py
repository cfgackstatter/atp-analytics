"""Environment-driven API settings (CORS, docs, etc.)."""

from __future__ import annotations

import os


def _env_flag(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    return raw.strip().lower()


def flag_enabled(name: str, *, default: bool = False) -> bool:
    """Parse a truthy/falsey env flag; return ``default`` when unset."""
    raw = _env_flag(name)
    if raw is None or raw == "":
        return default
    if raw in {"1", "true", "yes", "on"}:
        return True
    if raw in {"0", "false", "no", "off"}:
        return False
    return default


def force_https_enabled() -> bool:
    """Return True when FORCE_HTTPS is truthy (set in production)."""
    return flag_enabled("FORCE_HTTPS", default=False)


def cors_origins() -> list[str]:
    """
    Allowed browser origins for CORS.

    Empty (default) means do not enable cross-origin access. The React app is
    served same-origin by FastAPI (and Vite proxies in local frontend dev), so
    CORS is usually unnecessary.
    """
    raw = os.getenv("CORS_ORIGINS", "").strip()
    if not raw:
        return []
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def docs_enabled() -> bool:
    """
    Whether /docs, /redoc, and /openapi.json are exposed.

    Default: on for local (FORCE_HTTPS off), off when FORCE_HTTPS is on.
    Override with ENABLE_DOCS=true|false.
    """
    raw = _env_flag("ENABLE_DOCS")
    if raw is not None and raw != "":
        return flag_enabled("ENABLE_DOCS", default=False)
    return not force_https_enabled()
