"""Admin authentication via ``Authorization: Bearer <password>``."""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Admin password as a Bearer token",
)


def get_admin_password() -> str | None:
    """Return configured admin password, or None if unset."""
    password = os.getenv("ADMIN_PASSWORD")
    return password or None


def _password_digest(value: str) -> bytes:
    """Fixed-length digest so compare_digest stays constant-time across lengths."""
    return hashlib.sha256(value.encode("utf-8")).digest()


def passwords_match(provided: str, expected: str) -> bool:
    """Constant-time password comparison."""
    return hmac.compare_digest(_password_digest(provided), _password_digest(expected))


def require_admin(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> None:
    """
    FastAPI dependency: require a valid Bearer token matching ADMIN_PASSWORD.

    Fails closed with 503 when ADMIN_PASSWORD is not configured.
    """
    expected = get_admin_password()
    if expected is None:
        logger.error("Admin request rejected: ADMIN_PASSWORD is not set")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured",
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not passwords_match(credentials.credentials, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin password",
            headers={"WWW-Authenticate": "Bearer"},
        )
