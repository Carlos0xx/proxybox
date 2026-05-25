"""HTTPS / Caddy management endpoints — drives the admin UI's HTTPS page.

The two endpoints:

  GET  /api/https/status   — what's the current state (caddy active? domain
                              configured? running on https?). Cheap, polled
                              by the SPA when the user opens the page.

  POST /api/https/enable   — one-shot enablement. Body: {"domain": "..."}.
                              Blocks until done (~10-30 s including DNS
                              check, apt install of Caddy, Let's Encrypt
                              issuance is handled async by Caddy itself).
                              Returns the new state on success, or a
                              structured error code on failure so the SPA
                              can show a localised message.

Both are admin-gated (session cookie or url_token_bypass). The actual work
lives in ``app.services.caddy``; this router is just the HTTP envelope.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.token import admin_auth
from app.services import caddy

router = APIRouter(
    prefix="/admin/{token}/api/https",
    dependencies=[Depends(admin_auth)],
    tags=["https"],
)


class EnableBody(BaseModel):
    domain: str = Field(..., min_length=4, max_length=253)


@router.get("/status")
async def get_status() -> dict:
    s = caddy.status()
    return {
        "caddy_installed": s.caddy_installed,
        "caddy_active": s.caddy_active,
        "configured_domain": s.configured_domain,
        "public_host": s.public_host,
        "using_https": s.using_https,
        "notes": s.notes,
        "docker_runtime": s.docker_runtime,
    }


@router.post("/enable")
async def enable(body: EnableBody) -> dict:
    try:
        result = caddy.run(body.domain.strip().lower())
    except caddy.HTTPSEnableError as e:
        # Translate to a structured 400 the SPA can branch on without
        # parsing the message string.
        raise HTTPException(
            status_code=400,
            detail={"code": e.code, "message": e.detail or e.code},
        ) from e
    return {"ok": True, **result}
