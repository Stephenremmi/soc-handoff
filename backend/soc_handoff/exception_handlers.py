"""Translate known application failures into safe HTTP responses."""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from .errors import Conflict, NotFound, TrackerUnavailable

logger = logging.getLogger("uvicorn.error")


async def application_error(request: Request, error: Exception):
    if isinstance(error, NotFound):
        return JSONResponse({"detail": str(error)}, status_code=404)
    if isinstance(error, Conflict):
        return JSONResponse({"detail": str(error)}, status_code=409)

    logger.warning("Request %s failed: %s", request.state.request_id, type(error).__name__)
    detail = (
        "Tracker is unavailable." if isinstance(error, TrackerUnavailable)
        else "Atlas is unavailable. Retry when it reconnects."
    )
    return JSONResponse({"detail": detail}, status_code=503)


def register_exception_handlers(app):
    for error_type in (NotFound, Conflict, TrackerUnavailable, PyMongoError):
        app.add_exception_handler(error_type, application_error)
