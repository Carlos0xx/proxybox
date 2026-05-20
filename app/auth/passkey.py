"""WebAuthn / passkey authentication — opt-in alternative to URL-path token.

Enabled via ``config.yaml: features.passkey = true``. When off, the heavy
``webauthn`` dependency is never imported and no routes are mounted.

Two layers:
- *Always importable*: session cookie helpers (itsdangerous-signed), used by
  ``app.auth.token.admin_auth`` to accept a passkey-authenticated session as
  an alternative to the URL-path token.
- *Late-imported router*: ``make_passkey_router()`` imports the WebAuthn lib
  on demand and returns the FastAPI routes.

WebAuthn requires HTTPS origin in browsers — this only works behind a
TLS-terminating reverse proxy. Set ``passkey.rp_id`` (host without scheme)
and ``passkey.origin`` (full https:// URL) in config.
"""

from __future__ import annotations

import base64
import json
import secrets
import time
from pathlib import Path as P

from fastapi import APIRouter, HTTPException, Request, Response
from itsdangerous import BadData, URLSafeTimedSerializer
from pydantic import BaseModel

from app.config import get_settings
from app.db.connection import connection

SESSION_COOKIE_NAME = "proxybox_admin_session"
SESSION_MAX_AGE = 30 * 24 * 3600
CHALLENGE_TTL = 300

# In-process challenge store. Single-worker uvicorn is fine; for multi-worker
# scale, move to a shared store (Redis, sqlite WAL, etc.).
_challenges: dict[str, dict] = {}


def _load_or_create_secret() -> str:
    path = P(get_settings().paths.session_secret)
    if path.exists():
        return path.read_text().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    s = secrets.token_urlsafe(48)
    path.write_text(s)
    path.chmod(0o600)
    return s


def _signer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(_load_or_create_secret(), salt="proxybox-admin-session-v1")


def issue_session_cookie() -> str:
    return _signer().dumps({"iat": int(time.time()), "n": secrets.token_urlsafe(6)})


def validate_session_cookie(cookie: str | None) -> bool:
    if not cookie:
        return False
    try:
        _signer().loads(cookie, max_age=SESSION_MAX_AGE)
        return True
    except BadData:
        return False


def request_has_session(request: Request) -> bool:
    return validate_session_cookie(request.cookies.get(SESSION_COOKIE_NAME))


# ─── base64url helpers ──────────────────────────────────────────


def _b64url_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _b64url_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


# ─── Challenge store ────────────────────────────────────────────


def _store_challenge(challenge: bytes, kind: str) -> str:
    handle = secrets.token_urlsafe(16)
    _challenges[handle] = {"c": challenge, "ts": int(time.time()), "k": kind}
    now = int(time.time())
    for h in list(_challenges):
        if now - _challenges[h]["ts"] > CHALLENGE_TTL:
            del _challenges[h]
    return handle


def _pop_challenge(handle: str, kind: str) -> bytes:
    rec = _challenges.pop(handle, None)
    if not rec:
        raise HTTPException(400, "challenge expired or unknown")
    if rec["k"] != kind:
        raise HTTPException(400, "wrong challenge kind")
    if int(time.time()) - rec["ts"] > CHALLENGE_TTL:
        raise HTTPException(400, "challenge expired")
    return rec["c"]


# ─── Request models ─────────────────────────────────────────────


class _RegisterBeginReq(BaseModel):
    label: str = ""


class _RegisterCompleteReq(BaseModel):
    handle: str
    label: str = ""
    attestation: dict


class _LoginCompleteReq(BaseModel):
    handle: str
    assertion: dict


# ─── Router factory (late-imports webauthn) ─────────────────────


def make_public_router() -> APIRouter:
    """Login + logout endpoints — no admin token required (login bootstraps session)."""
    from webauthn import (
        generate_authentication_options,
        options_to_json,
        verify_authentication_response,
    )
    from webauthn.helpers.structs import (
        PublicKeyCredentialDescriptor,
        UserVerificationRequirement,
    )

    router = APIRouter(prefix="/auth/webauthn", tags=["passkey"])

    settings = get_settings()
    rp_id = settings.passkey.rp_id
    origin = settings.passkey.origin

    @router.post("/login/begin")
    async def login_begin() -> dict:
        with connection() as conn:
            existing = [
                r["credential_id"]
                for r in conn.execute("SELECT credential_id FROM passkey_credential").fetchall()
            ]
        if not existing:
            raise HTTPException(400, "no passkeys registered yet")
        allow = [PublicKeyCredentialDescriptor(id=_b64url_decode(cid)) for cid in existing]
        opts = generate_authentication_options(
            rp_id=rp_id,
            allow_credentials=allow,
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        handle = _store_challenge(opts.challenge, "login")
        return {"options": json.loads(options_to_json(opts)), "handle": handle}

    @router.post("/login/complete")
    async def login_complete(req: _LoginCompleteReq, response: Response) -> dict:
        challenge = _pop_challenge(req.handle, "login")
        cid_b64 = req.assertion.get("id")
        if not cid_b64:
            raise HTTPException(400, "missing credential id")
        with connection() as conn:
            row = conn.execute(
                "SELECT public_key, sign_count FROM passkey_credential WHERE credential_id = ?",
                (cid_b64,),
            ).fetchone()
            if not row:
                raise HTTPException(400, "unknown credential")
            try:
                verification = verify_authentication_response(
                    credential=req.assertion,
                    expected_challenge=challenge,
                    expected_rp_id=rp_id,
                    expected_origin=origin,
                    credential_public_key=row["public_key"],
                    credential_current_sign_count=row["sign_count"],
                    require_user_verification=True,
                )
            except Exception as e:
                raise HTTPException(400, f"verification failed: {e}") from e
            conn.execute(
                "UPDATE passkey_credential SET sign_count = ?, last_used_at = ? "
                "WHERE credential_id = ?",
                (verification.new_sign_count, int(time.time()), cid_b64),
            )
            conn.commit()
        response.set_cookie(
            SESSION_COOKIE_NAME,
            issue_session_cookie(),
            max_age=SESSION_MAX_AGE,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )
        return {"ok": True}

    @router.post("/logout")
    async def logout(response: Response) -> dict:
        response.delete_cookie(SESSION_COOKIE_NAME, path="/")
        return {"ok": True}

    return router


def make_admin_router() -> APIRouter:
    """Registration + management endpoints — sit under /admin/{token}/api/auth, admin-gated."""
    from fastapi import Depends
    from webauthn import (
        generate_registration_options,
        options_to_json,
        verify_registration_response,
    )
    from webauthn.helpers.structs import (
        AuthenticatorSelectionCriteria,
        PublicKeyCredentialDescriptor,
        ResidentKeyRequirement,
        UserVerificationRequirement,
    )

    from app.auth.token import admin_auth

    router = APIRouter(
        prefix="/admin/{token}/api/auth",
        dependencies=[Depends(admin_auth)],
        tags=["passkey"],
    )

    settings = get_settings()
    rp_id = settings.passkey.rp_id
    rp_name = settings.passkey.rp_name
    origin = settings.passkey.origin

    @router.post("/webauthn/register/begin")
    async def register_begin(req: _RegisterBeginReq) -> dict:
        with connection() as conn:
            existing = [
                r["credential_id"]
                for r in conn.execute("SELECT credential_id FROM passkey_credential").fetchall()
            ]
        excludes = [PublicKeyCredentialDescriptor(id=_b64url_decode(cid)) for cid in existing]
        opts = generate_registration_options(
            rp_id=rp_id,
            rp_name=rp_name,
            user_id=b"admin",
            user_name="admin",
            user_display_name="ProxyBox Admin",
            exclude_credentials=excludes,
            authenticator_selection=AuthenticatorSelectionCriteria(
                resident_key=ResidentKeyRequirement.PREFERRED,
                user_verification=UserVerificationRequirement.REQUIRED,
            ),
        )
        handle = _store_challenge(opts.challenge, "reg")
        return {"options": json.loads(options_to_json(opts)), "handle": handle}

    @router.post("/webauthn/register/complete")
    async def register_complete(req: _RegisterCompleteReq) -> dict:
        challenge = _pop_challenge(req.handle, "reg")
        verification = verify_registration_response(
            credential=req.attestation,
            expected_challenge=challenge,
            expected_rp_id=rp_id,
            expected_origin=origin,
        )
        cid_b64 = _b64url_encode(verification.credential_id)
        label = (req.label or f"passkey-{int(time.time())}")[:60]
        with connection() as conn:
            conn.execute(
                """INSERT INTO passkey_credential
                       (credential_id, public_key, sign_count, label, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    cid_b64,
                    verification.credential_public_key,
                    verification.sign_count,
                    label,
                    int(time.time()),
                ),
            )
            conn.commit()
        return {
            "ok": True,
            "credential_id_prefix": cid_b64[:12] + "...",
            "label": label,
        }

    @router.get("/passkeys")
    async def list_passkeys() -> dict:
        with connection() as conn:
            rows = conn.execute(
                """SELECT credential_id, label, created_at, last_used_at
                   FROM passkey_credential ORDER BY created_at DESC"""
            ).fetchall()
        return {
            "passkeys": [
                {
                    "id_prefix": r["credential_id"][:12] + "...",
                    "label": r["label"],
                    "created_at": r["created_at"],
                    "last_used_at": r["last_used_at"],
                }
                for r in rows
            ]
        }

    @router.delete("/passkeys/{cid}")
    async def revoke_passkey(cid: str) -> dict:
        with connection() as conn:
            cur = conn.execute("DELETE FROM passkey_credential WHERE credential_id = ?", (cid,))
            conn.commit()
        return {"ok": True, "deleted": cur.rowcount}

    return router
