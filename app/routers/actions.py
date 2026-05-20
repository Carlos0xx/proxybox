"""Admin actions — service restart, Reality keypair rotation, admin token rotation.

These are high-risk operations:
- ``/action/restart/{svc}``  restricted to services in config's monitored allowlist
- ``/action/rotate``         regenerates Reality keypair (disconnects all clients)
- ``/api/auth/rotate-admin-token``  invalidates current session, returns new URL
"""

from __future__ import annotations

import os
import secrets
from typing import Annotated

import yaml
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path
from pydantic import BaseModel

from app.auth.token import admin_auth
from app.config import get_settings, reset_settings_cache
from app.db.connection import connection
from app.services import shell, singbox, subscriptions

router = APIRouter(
    prefix="/admin/{token}/action",
    dependencies=[Depends(admin_auth)],
    tags=["actions"],
)

api_router = APIRouter(
    prefix="/admin/{token}/api/auth",
    dependencies=[Depends(admin_auth)],
    tags=["actions"],
)


SvcInPath = Annotated[str, Path(pattern=r"^[a-zA-Z0-9._-]{1,64}$")]


class ConfirmBody(BaseModel):
    confirm: bool = False


@router.post("/restart/{svc}")
async def restart_service(svc: SvcInPath) -> dict:
    """systemctl restart {svc}, gated by config.services.monitored allowlist."""
    settings = get_settings()
    if svc not in settings.services.monitored:
        raise HTTPException(
            400,
            f"service {svc!r} not in monitored allowlist — only services listed "
            f"under config.services.monitored can be restarted",
        )
    shell.run(["systemctl", "restart", "--no-block", svc], timeout=5)
    return {"service": svc, "action": "restarted"}


@router.post("/rotate")
async def rotate_reality_keypair(body: ConfirmBody, background_tasks: BackgroundTasks) -> dict:
    """Regenerate Reality keypair + short_id + rewrite every device's sub file.

    Existing clients keep working until sing-box restarts (~5s background
    reload), then disconnect. Each client must re-fetch the subscription URL
    to pick up the new public key + short_id.
    """
    if not body.confirm:
        raise HTTPException(
            400,
            'destructive operation — pass {"confirm": true} in the body to proceed; '
            "all VPN clients will need to refresh their subscription URL afterwards",
        )

    keypair_out = shell.run(["sing-box", "generate", "reality-keypair"], timeout=5)
    private_key = ""
    for line in keypair_out.splitlines():
        if "PrivateKey" in line:
            parts = line.split()
            if len(parts) >= 2:
                private_key = parts[-1]
                break
    if not private_key:
        raise HTTPException(500, "failed to generate Reality keypair")
    new_short_id = secrets.token_hex(8)

    cfg = singbox.read_config()
    template = singbox.find_template_inbound(cfg, "vless")
    template["tls"]["reality"]["private_key"] = private_key
    template["tls"]["reality"]["short_id"] = [new_short_id]
    singbox.write_config(cfg, defer_reload=True)

    with connection() as conn:
        rows = conn.execute("SELECT * FROM device WHERE revoked = 0").fetchall()
    for row in rows:
        subscriptions.write_subscription_file(dict(row), cfg)

    background_tasks.add_task(singbox.reload_singbox)

    return {
        "action": "reality_keypair_rotated",
        "subscriptions_regenerated": len(rows),
        "notice": (
            "every VPN client must refresh its subscription URL; existing connections "
            "will drop when sing-box reloads (~5s)"
        ),
    }


@api_router.post("/rotate-admin-token")
async def rotate_admin_token() -> dict:
    """Generate a new admin token, persist to config.yaml, invalidate current URL."""
    path = os.environ.get("PROXYBOX_CONFIG", "/etc/proxybox/config.yaml")
    new_token = secrets.token_urlsafe(24)

    with open(path) as f:
        raw = yaml.safe_load(f) or {}
    raw.setdefault("admin", {})["token"] = new_token

    # Atomic write so we never end up with a truncated config on disk
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        yaml.dump(raw, f, default_flow_style=False, sort_keys=False)
    os.replace(tmp, path)

    reset_settings_cache()

    return {
        "new_token": new_token,
        "new_url_prefix": f"/admin/{new_token}/",
        "notice": (
            "current URL is dead — the next request must use the new prefix above. "
            "save this response before closing the window."
        ),
    }
