"""ProxyBox FastAPI application entry point.

Run with:
    uvicorn app.main:app --host 0.0.0.0 --port 8080
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version

from fastapi import FastAPI

from app.config import get_settings
from app.db.init import init_schema
from app.routers import (
    account,
    actions,
    bans,
    connections,
    devices,
    history,
    login,
    subscriptions,
    system,
    traffic,
    ui,
)
from app.routers import (
    https as https_router,
)


def _version() -> str:
    """Pull the canonical version from the installed package metadata so
    pyproject.toml stays the single source of truth — avoids the drift
    release-audit.sh flagged before."""
    try:
        return _pkg_version("proxybox")
    except PackageNotFoundError:
        return "0.0.0-dev"


VERSION = _version()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_schema()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="ProxyBox",
        version=VERSION,
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.include_router(system.router)
    app.include_router(devices.router)
    app.include_router(subscriptions.router)
    app.include_router(traffic.router)
    app.include_router(connections.router)
    app.include_router(history.router)
    app.include_router(bans.router)
    app.include_router(bans.action_router)
    app.include_router(actions.router)
    app.include_router(actions.api_router)
    app.include_router(account.router)
    app.include_router(https_router.router)
    app.include_router(login.router)
    app.include_router(ui.router)

    if get_settings().features.passkey:
        from app.auth import passkey

        app.include_router(passkey.make_public_router())
        app.include_router(passkey.make_admin_router())

    return app


app = create_app()
