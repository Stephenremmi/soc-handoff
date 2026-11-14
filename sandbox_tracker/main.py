"""Assemble the standalone sandbox tracker FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from .config import TrackerSettings
from .database.client import tracker_client
from .database.tickets import TicketStore
from .routers.tickets import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = TrackerSettings.from_environment()
    with tracker_client(settings) as client:
        client.admin.command("ping")
        app.state.settings = settings
        app.state.tickets = TicketStore(client[settings.mongodb_database].tickets)
        yield


app = FastAPI(title="Sandbox Case Tracker", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(PyMongoError)
async def database_error(_request: Request, _error: PyMongoError):
    return JSONResponse({"detail": "Tracker storage is unavailable."}, status_code=503)


@app.get("/api/health", tags=["health"])
def health():
    return {"status": "ok"}
