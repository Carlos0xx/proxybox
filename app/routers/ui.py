"""Serve the single-file SPA dashboard.

GET /admin/{token}/ returns the HTML with ``{{TOKEN}}`` replaced by the
URL-path token so the embedded JS can call ``/admin/{token}/api/...``.

Auth handling differs slightly from API routes: an unauthenticated SPA
load (no session cookie + url_token_bypass off) **redirects to /login**
rather than returning JSON 401. That gives a普通用户 a clickable login
form instead of a Network-tab error.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.auth.passkey import request_has_session
from app.config import get_settings

router = APIRouter(
    prefix="/admin/{token}",
    # Note: no admin_auth dependency here — we want HTML-aware behaviour
    # (redirect to /login) rather than the JSON 401 admin_auth produces.
    tags=["ui"],
)

_NO_CACHE_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
}


def _token_matches(token: str, expected: str) -> bool:
    return secrets.compare_digest(token.encode(), expected.encode())


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def index(token: Annotated[str, Path()], request: Request) -> Response:
    settings = get_settings()
    expected = settings.admin.token

    # URL-token still has to match — even with a session cookie. Defends
    # against a session cookie from a sibling instance / wrong path.
    if not _token_matches(token, expected):
        # Wrong token = no recovery, return 404 so we don't leak whether
        # the token slot is "almost right".
        raise HTTPException(404, "not found")

    has_session = request_has_session(request)
    bypass_ok = settings.features.url_token_bypass
    login_path = settings.admin.login_path
    login_url_base = f"/login/{login_path}" if login_path else "/login"

    if not (has_session or bypass_ok):
        # Send普通用户 to the login form instead of a 401 wall.
        next_path = request.url.path
        return RedirectResponse(f"{login_url_base}?next={next_path}", status_code=303)

    spa = settings.paths.static_dir / "index.html"
    if not spa.exists():
        raise HTTPException(
            500, f"SPA not found at {spa} — ship static/ directory or set paths.static_dir"
        )
    feats = getattr(settings, "features", None)
    passkey_on = bool(getattr(feats, "passkey", False)) if feats else False
    bot_on = bool(getattr(feats, "bot", False)) if feats else False
    body = (
        spa.read_text(encoding="utf-8")
        .replace("{{TOKEN}}", token)
        .replace("{{PASSKEY_ENABLED}}", "true" if passkey_on else "false")
        .replace("{{BOT_ENABLED}}", "true" if bot_on else "false")
        .replace("{{LOGIN_URL}}", login_url_base)
    )
    return HTMLResponse(content=body, headers=_NO_CACHE_HEADERS)
