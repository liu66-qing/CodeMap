"""Small API-key guard for admin and destructive endpoints."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status

from codegraph.config import settings


async def require_admin_api_key(
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
) -> None:
    """Require an admin API key when one is configured.

    Development stays frictionless when ADMIN_API_KEY is empty. Production and
    hosted demos can set ADMIN_API_KEY to protect operational endpoints without
    introducing a full auth system yet.
    """

    if not settings.admin_api_key:
        return

    if not x_admin_api_key or not hmac.compare_digest(
        x_admin_api_key, settings.admin_api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid admin API key",
        )


def require_confirmation(confirmation: str, expected: str) -> None:
    """Gate destructive operations behind an explicit typed confirmation."""

    if confirmation != expected:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Confirmation required: send confirmation='{expected}'",
        )
