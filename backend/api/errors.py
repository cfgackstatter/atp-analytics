"""Helpers for safe API error responses (log detail, return generic message)."""

from __future__ import annotations

import logging

from fastapi import HTTPException, status


def http_internal_error(
    logger: logging.Logger,
    exc: BaseException,
    *,
    public_message: str = "Internal server error",
) -> HTTPException:
    """Log the full exception and return a generic 500 for clients."""
    logger.exception("%s", public_message, exc_info=exc)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=public_message,
    )
