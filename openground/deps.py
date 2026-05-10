from __future__ import annotations

from fastapi import HTTPException, Request, status


def verify_ingest_token(expected: str, request: Request) -> None:
    if not expected:
        return
    x = request.headers.get("X-Ingest-Token")
    if x is not None and x.strip() == expected:
        return
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer ") and auth.removeprefix("Bearer ").strip() == expected:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing ingest credentials",
    )
