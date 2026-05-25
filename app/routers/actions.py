"""Admin actions — service restart, Reality keypair rotation, admin token rotation.

These are high-risk operations:
- ``/action/restart/{svc}``  restricted to services in config's monitored allowlist
- ``/action/rotate``         regenerates Reality keypair (disconnects all clients)
- ``/api/auth/rotate-admin-token``  invalidates current session, returns new URL
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path as FilePath
from typing import Annotated

import yaml
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path
from pydantic import BaseModel

from app.auth.token import admin_auth
from app.config import get_settings, reset_settings_cache
from app.db.connection import connection
from app.services import shell, singbox, subscriptions, system_stats

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
    """Restart or reload a monitored service for the current runtime."""
    settings = get_settings()
    if svc not in settings.services.monitored:
        raise HTTPException(
            400,
            f"service {svc!r} not in monitored allowlist — only services listed "
            f"under config.services.monitored can be restarted",
        )
    if system_stats.runtime_is_docker():
        return _docker_restart_service(svc)
    shell.run(["systemctl", "restart", "--no-block", svc], timeout=5)
    return {"service": svc, "action": "restarted"}


def _docker_restart_service(svc: str) -> dict:
    if svc == "sing-box" and singbox.signal_reload():
        return {"service": svc, "action": "reload_requested"}
    if svc == "proxybox-traffic-worker":
        flag = os.environ.get("PROXYBOX_WORKER_RESTART_FILE")
        if flag:
            path = FilePath(flag)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            return {"service": svc, "action": "restart_requested"}
    raise HTTPException(
        501,
        f"service {svc!r} cannot be restarted from inside the Docker sandbox; "
        "use docker compose restart for that service",
    )


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
    path = FilePath(os.environ.get("PROXYBOX_CONFIG", "/etc/proxybox/config.yaml"))
    new_token = secrets.token_urlsafe(24)

    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    old_token = str(raw.get("admin", {}).get("token", ""))
    raw.setdefault("admin", {})["token"] = new_token

    # Atomic write so we never end up with a truncated config on disk. chmod
    # both the tmp file and final path so os.replace never widens config.yaml
    # to the process umask (often 0644), which would expose admin.token.
    tmp = path.with_suffix(path.suffix + ".tmp")
    data = yaml.safe_dump(raw, default_flow_style=False, sort_keys=False, allow_unicode=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(tmp, path)
    path.chmod(0o600)

    reset_settings_cache()

    new_url_prefix = f"/admin/{new_token}/"
    return {
        "new_token": new_token,
        "new_url_prefix": new_url_prefix,
        # Kept as a separate field so the SPA can show/copy a stable value even
        # if future versions choose to return a fully-qualified URL here.
        "new_admin_url": new_url_prefix,
        "old_token_short": f"{old_token[:8]}..." if old_token else "",
        "restart_scheduled_in_seconds": 0,
        "notice": (
            "current URL is dead — the next request must use the new prefix above. "
            "save this response before closing the window."
        ),
    }
