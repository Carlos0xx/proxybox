"""URL-path admin token authentication, with optional passkey-session fallback.

Mounted as a FastAPI dependency on routers prefixed with /admin/{token}/.
Uses constant-time comparison for the token check. When
``features.passkey == true``, a valid session cookie (issued after WebAuthn
login) is accepted as an alternative — the URL-path token segment then
acts as a route prefix only, not as the sole auth credential.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import HTTPException, Path, Request

from app.config import get_settings


async def admin_auth(request: Request, token: Annotated[str, Path()]) -> str:
    settings = get_settings()
    expected = settings.admin.token.encode()
    if secrets.compare_digest(token.encode(), expected):
        return token

    if settings.features.passkey:
        # Late import — avoids loading itsdangerous on first hit if not needed,
        # though it's a cheap import either way.
        from app.auth.passkey import request_has_session

        if request_has_session(request):
            return token

    raise HTTPException(status_code=403, detail="Unauthorized")
