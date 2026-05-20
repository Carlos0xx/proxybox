"""Device endpoints: list, single read, label / notes update, create. Delete TBD."""

from __future__ import annotations

import secrets
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path
from pydantic import BaseModel, Field

from app.auth.token import admin_auth
from app.db.connection import connection
from app.models.device import Device
from app.services import singbox

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


# Path-conflicting names — /api/devices/list is a literal endpoint, so a
# device literally named "list" would shadow it (FastAPI matches literal
# before parametric).
_RESERVED_NAMES = {"list"}


_COLUMNS = (
    "name, label, kind, vless_uuid, hy2_password, "
    "vless_port, hy2_port, sni, "
    "created_at, last_seen, last_ip, "
    "revoked, notes, sub_token, paused_until"
)

_LIST_SQL = f"SELECT {_COLUMNS} FROM device ORDER BY revoked, created_at DESC"
_GET_SQL = f"SELECT {_COLUMNS} FROM device WHERE name = ?"


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
        cur = conn.execute(
            "UPDATE device SET label = ? WHERE name = ?", (body.label, name)
        )
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "device not found")
    return {"name": name, "label": body.label}


@router.post("/{name}/notes")
async def update_notes(name: NameInPath, body: NotesUpdate) -> dict[str, str]:
    with connection() as conn:
        cur = conn.execute(
            "UPDATE device SET notes = ? WHERE name = ?", (body.notes, name)
        )
        conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(404, "device not found")
    return {"name": name, "notes": body.notes}


@router.post("/new")
async def create_device(body: DeviceCreate, background_tasks: BackgroundTasks) -> dict:
    if body.name in _RESERVED_NAMES:
        raise HTTPException(400, f"name {body.name!r} is reserved")

    with connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM device WHERE name = ?", (body.name,)
        ).fetchone()
        if existing is not None:
            raise HTTPException(409, f"device {body.name!r} already exists")

    cfg = singbox.read_config()
    vless_tpl = singbox.find_template_inbound(cfg, "vless")
    sni = vless_tpl.get("tls", {}).get("server_name", "")

    vless_port, hy2_port = singbox.allocate_ports(cfg)
    vless_uuid = str(uuid.uuid4())
    hy2_password = secrets.token_urlsafe(24)
    sub_token = secrets.token_hex(8)
    now = int(time.time())
    label = body.label or body.name

    device_row = {
        "name": body.name,
        "vless_uuid": vless_uuid,
        "hy2_password": hy2_password,
        "vless_port": vless_port,
        "hy2_port": hy2_port,
    }
    singbox.add_device_inbounds(cfg, device_row)

    with connection() as conn:
        conn.execute(
            "INSERT INTO device (name, label, kind, vless_uuid, hy2_password, "
            "vless_port, hy2_port, sni, created_at, notes, sub_token) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (body.name, label, body.kind, vless_uuid, hy2_password,
             vless_port, hy2_port, sni, now, body.notes, sub_token),
        )
        conn.commit()

    singbox.write_config(cfg, defer_reload=True)
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
        "notice": "sing-box reloading in background; existing proxy connections may briefly drop.",
    }
