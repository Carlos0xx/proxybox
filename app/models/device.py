"""Pydantic representation of the device row."""

from __future__ import annotations

from pydantic import BaseModel


class Device(BaseModel):
    name: str
    label: str = ""
    kind: str = "generic"
    vless_uuid: str
    hy2_password: str
    vless_port: int
    hy2_port: int
    sni: str
    created_at: int
    last_seen: int | None = None
    last_ip: str | None = None
    revoked: int = 0
    notes: str = ""
    sub_token: str
    paused_until: int = 0
