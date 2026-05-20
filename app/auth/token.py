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
  3. Otherwise → 401 with header X-Login-URL: /login so the SPA can
     redirect.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import HTTPException, Path, Request

from app.config import get_settings


def _token_matches(token: str, expected: str) -> bool:
    return secrets.compare_digest(token.encode(), expected.encode())


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

    raise HTTPException(
        status_code=401,
        detail="login required",
        headers={"X-Login-URL": "/login"},
    )
