"""Authenticate requests from the SOC Handoff service."""

from hmac import compare_digest

from fastapi import Header, HTTPException, Request


def require_service(request: Request, authorization: str | None = Header(default=None)):
    token = request.app.state.settings.token
    if not token or not compare_digest((authorization or "").encode(), f"Bearer {token}".encode()):
        raise HTTPException(401, "Tracker authorization required")
