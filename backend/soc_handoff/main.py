"""Assemble the SOC Handoff FastAPI application."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from .config import Settings
from .database.client import atlas_client
from .database.repository import MongoStore
from .exception_handlers import register_exception_handlers
from .integrations.tracker import TrackerClient
from .middleware.request_id import RequestIdMiddleware
from .routers import runs, web
from .services.workflow import HandoffWorkflow


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings.from_environment()
    with (
        atlas_client(settings) as mongo,
        httpx.Client(base_url=settings.tracker_url, timeout=4, trust_env=False) as http,
    ):
        mongo.admin.command("ping")
        store = MongoStore(mongo[settings.mongodb_database])
        app.state.settings = settings
        app.state.store = store
        app.state.workflow = HandoffWorkflow(store, TrackerClient(http, settings.tracker_token))
        yield


app = FastAPI(title="SOC Handoff", lifespan=lifespan)
app.add_middleware(RequestIdMiddleware)
register_exception_handlers(app)
app.include_router(web.router)
app.include_router(runs.router)
