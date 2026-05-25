"""Device endpoints: current usage, list, single read, label / notes / create / state / delete."""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from app.auth.token import admin_auth
from app.db.connection import connection
from app.models.device import Device
from app.services import singbox, subscriptions

router = APIRouter(
    prefix="/admin/{token}/api/devices",
    dependencies=[Depends(admin_auth)],
    tags=["devices"],
)

NameInPath = Annotated[str, Path(pattern=r"^[a-zA-Z0-9_-]{3,32}$")]


class LabelUpdate(BaseModel):
    label: str = Field(default="", max_length=64)


class NotesUpdate(BaseModel):
    notes: str = Field(default="", max_length=1024)


class DeviceCreate(BaseModel):
    name: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")
    label: str = Field(default="", max_length=64)
    kind: str = Field(default="generic", max_length=32)
    notes: str = Field(default="", max_length=1024)


class PauseRequest(BaseModel):
    until_ts: int = Field(default=0, ge=0)


class RenameRequest(BaseModel):
    new_name: str = Field(min_length=3, max_length=32, pattern=r"^[a-zA-Z0-9_-]+$")


_RESERVED_NAMES = {"list"}

_PAUSE_INDEFINITE = 7258118400


_COLUMNS = (
    "name, label, kind, vless_uuid, hy2_password, "
    "vless_port, hy2_port, sni, "
    "created_at, last_seen, last_ip, "
    "revoked, notes, sub_token, paused_until"
)

_LIST_SQL = f"SELECT {_COLUMNS} FROM device ORDER BY revoked, created_at DESC"
_GET_SQL = f"SELECT {_COLUMNS} FROM device WHERE name = ?"

_USAGE_SQL = """
SELECT
    d.name,
    d.label,
    d.kind,
    d.last_seen,
    d.last_ip,
    d.paused_until,
    d.revoked,
    COALESCE(t24.rx, 0) AS rx_24h,
    COALESCE(t24.tx, 0) AS tx_24h,
    COALESCE(td.rx, 0)  AS rx_today,
    COALESCE(td.tx, 0)  AS tx_today
FROM device d
LEFT JOIN (
    SELECT device_name, SUM(rx_bytes) AS rx, SUM(tx_bytes) AS tx
    FROM traffic_log WHERE bucket_ts >= ?
    GROUP BY device_name
) t24 ON t24.device_name = d.name
LEFT JOIN (
    SELECT device_name, SUM(rx_bytes) AS rx, SUM(tx_bytes) AS tx
    FROM traffic_log WHERE date = ?
    GROUP BY device_name
) td ON td.device_name = d.name
WHERE d.revoked = 0
ORDER BY COALESCE(d.last_seen, 0) DESC
"""


@router.get("")
async def devices_current_usage() -> dict:
    """Per-device current usage view (today + 24h totals, paused flag, last_seen).

    Distinct from /list (which returns raw device config). This endpoint is
    what the SPA's main view consumes — it joins device metadata with
    traffic_log aggregations.
    """
    now = datetime.now(UTC)
    cutoff_24h = int((now - timedelta(hours=24)).timestamp())
    today_str = now.strftime("%Y-%m-%d")
    current_ts = int(now.timestamp())

    with connection() as conn:
        rows = conn.execute(_USAGE_SQL, (cutoff_24h, today_str)).fetchall()

    return {
        "devices": [
            {
                "name": r["name"],
                "label": r["label"],
                "kind": r["kind"],
                "last_seen": r["last_seen"],
                "last_ip": r["last_ip"],
                "is_paused": r["paused_until"] > current_ts,
                "paused_until": r["paused_until"],
                "rx_24h": r["rx_24h"],
                "tx_24h": r["tx_24h"],
                "rx_today": r["rx_today"],
                "tx_today": r["tx_today"],
            }
            for r in rows
        ]
    }


@router.get("/list")
async def list_devices() -> dict[str, list[Device]]:
    with connection() as conn:
        rows = conn.execute(_LIST_SQL).fetchall()
    return {"devices": [Device.model_validate(dict(r)) for r in rows]}


@router.get("/{name}")
async def get_device(name: NameInPath) -> Device:
    with connection() as conn:
        row = conn.execute(_GET_SQL, (name,)).fetchone()
    if row is None:
        raise HTTPException(404, "device not found")
    return Device.model_validate(dict(row))


@router.post("/{name}/label")
async def update_label(name: NameInPath, body: LabelUpdate) -> dict[str, str]:
    with connection() as conn:
        cur = conn.execute("UPDATE device SET label = ? WHERE name = ?", (body.label, name))
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "device not found")
    return {"name": name, "label": body.label}


@router.post("/{name}/notes")
async def update_notes(name: NameInPath, body: NotesUpdate) -> dict[str, str]:
    with connection() as conn:
        cur = conn.execute("UPDATE device SET notes = ? WHERE name = ?", (body.notes, name))
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "device not found")
    return {"name": name, "notes": body.notes}


@router.post("/new")
async def create_device(body: DeviceCreate, background_tasks: BackgroundTasks) -> dict:
    if body.name in _RESERVED_NAMES:
        raise HTTPException(400, f"name {body.name!r} is reserved")

    with connection() as conn:
        existing = conn.execute("SELECT 1 FROM device WHERE name = ?", (body.name,)).fetchone()
        if existing is not None:
            raise HTTPException(409, f"device {body.name!r} already exists")

    cfg = singbox.read_config()
    vless_tpl = singbox.find_template_inbound(cfg, "vless")
    sni = vless_tpl.get("tls", {}).get("server_name", "")

    vless_port, hy2_port = singbox.allocate_ports(cfg)
    vless_uuid = str(uuid.uuid4())
    hy2_password = secrets.token_urlsafe(24)
    # 192-bit URL-safe token. The previous token_hex(8) was only 64 bits
    # which is too short for an unauthenticated public path used as the
    # device's only credential. See subscriptions router — token IS the secret.
    sub_token = secrets.token_urlsafe(24)
    now = int(time.time())
    label = body.label or body.name

    device_row = {
        "name": body.name,
        "vless_uuid": vless_uuid,
        "hy2_password": hy2_password,
        "vless_port": vless_port,
        "hy2_port": hy2_port,
        "sub_token": sub_token,
    }
    singbox.add_device_inbounds(cfg, device_row)

    with connection() as conn:
        conn.execute(
            "INSERT INTO device (name, label, kind, vless_uuid, hy2_password, "
            "vless_port, hy2_port, sni, created_at, notes, sub_token) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                body.name,
                label,
                body.kind,
                vless_uuid,
                hy2_password,
                vless_port,
                hy2_port,
                sni,
                now,
                body.notes,
                sub_token,
            ),
        )
        conn.commit()

    singbox.write_config(cfg, defer_reload=True)
    subscriptions.write_subscription_file(device_row, cfg)
    background_tasks.add_task(singbox.reload_singbox)

    return {
        "device": {
            "name": body.name,
            "label": label,
            "kind": body.kind,
            "vless_uuid": vless_uuid,
            "hy2_password": hy2_password,
            "vless_port": vless_port,
            "hy2_port": hy2_port,
            "sni": sni,
            "sub_token": sub_token,
        },
        "subscription_url_path": f"/api/sub/{sub_token}",
        "notice": "sing-box reloading in background; existing proxy connections may briefly drop.",
    }


@router.post("/{name}/regen-subs")
async def regen_subs(name: NameInPath) -> dict:
    # 192-bit URL-safe — matches POST /devices/new. See note there.
    new_sub_token = secrets.token_urlsafe(24)
    with connection() as conn:
        old_row = conn.execute(_GET_SQL, (name,)).fetchone()
        if old_row is None:
            raise HTTPException(404, "device not found")
        old_sub_token = old_row["sub_token"]
        conn.execute("UPDATE device SET sub_token = ? WHERE name = ?", (new_sub_token, name))
        conn.commit()
        new_row = conn.execute(_GET_SQL, (name,)).fetchone()

    subscriptions.delete_subscription_file(old_sub_token)
    subscriptions.write_subscription_file(dict(new_row))

    return {
        "name": name,
        "sub_token": new_sub_token,
        "subscription_url_path": f"/api/sub/{new_sub_token}",
        "notice": "old sub_token invalidated; update client subscription URL",
    }


@router.post("/{name}/delete")
async def delete_device(name: NameInPath, background_tasks: BackgroundTasks) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT sub_token FROM device WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise HTTPException(404, "device not found")
        sub_token = row["sub_token"]
        traffic_rows = conn.execute(
            "DELETE FROM traffic_log WHERE device_name = ?", (name,)
        ).rowcount
        host_rows = conn.execute("DELETE FROM host_log WHERE device_name = ?", (name,)).rowcount
        conn.execute("DELETE FROM device WHERE name = ?", (name,))
        conn.commit()

    cfg = singbox.read_config()
    removed_tags = singbox.remove_device_inbounds(cfg, name)
    singbox.write_config(cfg, defer_reload=True)
    subscriptions.delete_subscription_file(sub_token)
    background_tasks.add_task(singbox.reload_singbox)

    return {
        "name": name,
        "removed_inbounds": removed_tags,
        "deleted_history_rows": traffic_rows + host_rows,
        "notice": "device deleted; sing-box reloading in background",
    }


@router.post("/{name}/pause")
async def pause_device(
    name: NameInPath, body: PauseRequest, background_tasks: BackgroundTasks
) -> dict:
    paused_until = body.until_ts if body.until_ts > 0 else _PAUSE_INDEFINITE
    with connection() as conn:
        row = conn.execute("SELECT name FROM device WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise HTTPException(404, "device not found")
        conn.execute("UPDATE device SET paused_until = ? WHERE name = ?", (paused_until, name))
        conn.commit()

    cfg = singbox.read_config()
    removed = singbox.remove_device_inbounds(cfg, name)
    singbox.write_config(cfg, defer_reload=True)
    background_tasks.add_task(singbox.reload_singbox)

    return {"name": name, "paused_until": paused_until, "removed_inbounds": removed}


@router.post("/{name}/resume")
async def resume_device(name: NameInPath, background_tasks: BackgroundTasks) -> dict:
    with connection() as conn:
        row = conn.execute(_GET_SQL, (name,)).fetchone()
        if row is None:
            raise HTTPException(404, "device not found")
        conn.execute("UPDATE device SET paused_until = 0 WHERE name = ?", (name,))
        conn.commit()
        updated = conn.execute(_GET_SQL, (name,)).fetchone()

    cfg = singbox.read_config()
    added = singbox.add_device_inbounds(cfg, dict(updated))
    singbox.write_config(cfg, defer_reload=True)
    background_tasks.add_task(singbox.reload_singbox)

    return {"name": name, "added_inbounds": added}


@router.post("/{name}/revoke")
async def revoke_device(name: NameInPath, background_tasks: BackgroundTasks) -> dict:
    with connection() as conn:
        row = conn.execute("SELECT sub_token FROM device WHERE name = ?", (name,)).fetchone()
        if row is None:
            raise HTTPException(404, "device not found")
        sub_token = row["sub_token"]
        conn.execute("UPDATE device SET revoked = 1 WHERE name = ?", (name,))
        conn.commit()

    cfg = singbox.read_config()
    removed = singbox.remove_device_inbounds(cfg, name)
    singbox.write_config(cfg, defer_reload=True)
    subscriptions.delete_subscription_file(sub_token)
    background_tasks.add_task(singbox.reload_singbox)

    return {"name": name, "revoked": True, "removed_inbounds": removed}


@router.post("/{name}/rename")
async def rename_device(
    name: NameInPath, body: RenameRequest, background_tasks: BackgroundTasks
) -> dict:
    if body.new_name in _RESERVED_NAMES:
        raise HTTPException(400, f"name {body.new_name!r} is reserved")
    if body.new_name == name:
        return {"name": name, "previous_name": name, "notice": "no change"}

    with connection() as conn:
        old_row = conn.execute(_GET_SQL, (name,)).fetchone()
        if old_row is None:
            raise HTTPException(404, "device not found")
        clash = conn.execute("SELECT 1 FROM device WHERE name = ?", (body.new_name,)).fetchone()
        if clash is not None:
            raise HTTPException(409, f"device {body.new_name!r} already exists")
        conn.execute("UPDATE device SET name = ? WHERE name = ?", (body.new_name, name))
        conn.commit()
        new_row = conn.execute(_GET_SQL, (body.new_name,)).fetchone()

    cfg = singbox.read_config()
    singbox.remove_device_inbounds(cfg, name)
    singbox.add_device_inbounds(cfg, dict(new_row))
    singbox.write_config(cfg, defer_reload=True)
    subscriptions.write_subscription_file(dict(new_row), cfg)
    background_tasks.add_task(singbox.reload_singbox)

    return {
        "name": body.new_name,
        "previous_name": name,
        "notice": "device renamed; sing-box reloading in background",
    }
