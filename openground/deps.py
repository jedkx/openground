"""FastAPI dependencies shared across routers (auth, limits, etc.)."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Header, HTTPException, status

from openground.config import Settings


def build_ingest_token_checker(settings: Settings) -> Callable[..., None]:
    """Return a FastAPI dependency that enforces ``OPENGROUND_INGEST_TOKEN`` when set."""

    expected = (settings.ingest_token or "").strip()

    def check_credentials(
        x_ingest_token: str | None = Header(default=None, alias="X-Ingest-Token"),
        authorization: str | None = Header(default=None),
    ) -> None:
        if not expected:
            return
        if x_ingest_token is not None and x_ingest_token.strip() == expected:
            return
        if authorization and authorization.startswith("Bearer "):
            if authorization.removeprefix("Bearer ").strip() == expected:
                return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing ingest credentials",
        )

    return check_credentials
