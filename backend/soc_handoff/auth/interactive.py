"""Require the same-origin UI's custom header on mutating run routes."""

from fastapi import Header, HTTPException


def require_interactive_action(x_soc_action: str | None = Header(default=None)):
    if x_soc_action != "interactive":
        raise HTTPException(403, "Interactive action header required")
