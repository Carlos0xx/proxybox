"""Public subscription endpoints — sub_token IS the auth, no admin token required.

Clients (Shadowrocket, sing-box, Hiddify, Stash, Clash for iOS, Merlin) fetch
the appropriate format via HTTP GET; HEAD is also accepted for clients that
probe subscription status first. The path validator constrains sub_token to
hex/base64-safe chars so the URL can never be tricked into traversing the
filesystem.

Format selection:
  /api/sub/{sub_token}                  — URI list (default, sing-box family)
  /api/sub/{sub_token}/shadowrocket.yaml — Clash YAML alias for Shadowrocket
                                           config import (nodes + rules)
  /api/sub/{sub_token}/clash.yaml       — Mihomo / Clash for iOS / Stash YAML
  /api/sub/{sub_token}/merlin.yaml      — Clash YAML with tun: enable: true
                                           (AsusWRT-Merlin transparent proxy)

For non-URI formats the device row is re-queried by sub_token and the file
is built on the fly (no extra disk writes on device create / regen).
The YAML formats include nodes + built-in split rules. The URI list formats only
carry nodes because the node-subscription format has no routing-rule syntax.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path
from fastapi.responses import PlainTextResponse, Response

from app.db.connection import connection
from app.services import singbox, subscriptions

router = APIRouter(prefix="/api/sub", tags=["subscriptions"])

SubTokenInPath = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{8,64}$")]


def _device_by_sub_token(sub_token: str) -> dict:
    with connection() as conn:
        row = conn.execute(
            "SELECT name, label, kind, vless_uuid, hy2_password, vless_port, hy2_port, "
            "sni, sub_token, revoked, paused_until FROM device WHERE sub_token = ?",
            (sub_token,),
        ).fetchone()
    if row is None:
        raise HTTPException(404, "subscription not found")
    if row["revoked"]:
        raise HTTPException(410, "subscription revoked")
    return dict(row)


@router.api_route("/{sub_token}", methods=["GET", "HEAD"], response_class=PlainTextResponse)
async def get_subscription(sub_token: SubTokenInPath) -> str:
    # DB lookup first — same revoked / not-found behaviour as every other
    # format. Earlier versions read the file directly, which bypassed
    # revoked-status checks for any device whose .txt was still on disk.
    device = _device_by_sub_token(sub_token)
    return subscriptions.generate_subscription_text(device, singbox.read_config())


@router.api_route("/{sub_token}/clash.yaml", methods=["GET", "HEAD"])
async def get_clash_yaml(sub_token: SubTokenInPath) -> Response:
    device = _device_by_sub_token(sub_token)
    body = subscriptions.build_clash_yaml(device, singbox.read_config(), with_tun=False)
    return Response(content=body, media_type="text/yaml")


@router.api_route("/{sub_token}/shadowrocket.yaml", methods=["GET", "HEAD"])
async def get_shadowrocket_yaml(sub_token: SubTokenInPath) -> Response:
    device = _device_by_sub_token(sub_token)
    body = subscriptions.build_clash_yaml(device, singbox.read_config(), with_tun=False)
    return Response(content=body, media_type="text/yaml")


@router.api_route("/{sub_token}/merlin.yaml", methods=["GET", "HEAD"])
async def get_merlin_yaml(sub_token: SubTokenInPath) -> Response:
    device = _device_by_sub_token(sub_token)
    body = subscriptions.build_clash_yaml(device, singbox.read_config(), with_tun=True)
    return Response(content=body, media_type="text/yaml")
