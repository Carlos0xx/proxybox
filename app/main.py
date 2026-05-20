"""ProxyBox FastAPI application entry point.

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.init import init_schema
from app.routers import bans, devices, history, subscriptions, system, traffic


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="ProxyBox", version="0.1.0", lifespan=lifespan)
    app.include_router(system.router)
    app.include_router(devices.router)
    app.include_router(subscriptions.router)
    app.include_router(traffic.router)
    app.include_router(history.router)
    app.include_router(bans.router)
    app.include_router(bans.action_router)
    return app


app = create_app()
