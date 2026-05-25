"""Admin-route authentication.

v0.1.6 makes the **session cookie** (issued by /login or by passkey-login)
the primary credential. The URL-path token alone is a backdoor and only
works when ``features.url_token_bypass = true`` in config — turned off by
default because tokens leak through screenshots / browser history more
easily than passwords.

Order of checks:
  1. Session cookie valid AND URL token matches → accept.
     (Token must still match the config so an attacker holding a session
     cookie from another instance can't piggyback.)
  2. ``url_token_bypass`` enabled AND URL token matches → accept.
     (Emergency / automation / SDK use case.)
  3. Optional Telegram bot mode AND loopback peer AND URL token matches → accept.
     (Native bot automation.)
  4. Docker sidecar bot secret AND URL token matches → accept.
     (Install-scoped service-to-service auth, not exposed to browsers.)
  5. Otherwise → 401 with header X-Login-URL: /login so the SPA can
     redirect.
"""

from __future__ import annotations

import os
import secrets
from ipaddress import ip_address
from typing import Annotated

from fastapi import HTTPException, Path, Request

from app.config import get_settings


def _token_matches(token: str, expected: str) -> bool:
    return secrets.compare_digest(token.encode(), expected.encode())


def _request_from_loopback(request: Request) -> bool:
    host = request.client.host if request.client else ""
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _bot_secret_matches(request: Request) -> bool:
    if os.environ.get("PROXYBOX_RUNTIME") != "docker":
        return False
    expected = os.environ.get("PROXYBOX_BOT_INTERNAL_SECRET", "")
    provided = request.headers.get("X-ProxyBox-Bot-Secret", "")
    return bool(expected and provided) and secrets.compare_digest(
        provided.encode(), expected.encode()
    )


async def admin_auth(request: Request, token: Annotated[str, Path()]) -> str:
    settings = get_settings()
    expected = settings.admin.token

    # Path 1: session cookie + matching URL token (the default v0.1.6 flow).
    from app.auth.passkey import request_has_session

    if request_has_session(request) and _token_matches(token, expected):
        return token

    # Path 2: URL-token bypass (opt-in).
    if settings.features.url_token_bypass and _token_matches(token, expected):
        return token

    # Telegram bot / localhost automation path. Keeps the public admin API
    # session-gated while still allowing the optional bot to talk to
    # 127.0.0.1:8080 with the path token it already stores in bot.env.
    if (
        settings.features.bot
        and _request_from_loopback(request)
        and _token_matches(token, expected)
    ):
        return token

    # Docker Telegram bot path. The bot is a separate container, so it is not
    # loopback from the admin process. Limit this to an install-scoped secret
    # generated into the Docker .env and passed only to proxybox-admin/bot.
    if _bot_secret_matches(request) and _token_matches(token, expected):
        return token

    raise HTTPException(
        status_code=401,
        detail="login required",
        headers={"X-Login-URL": "/login"},
    )
