"""Uvicorn entrypoint: ``uv run uvicorn main:app --reload``."""

from openground.application import app

__all__ = ["app"]
