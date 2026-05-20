"""IP ban management via fail2ban — admin-controlled manual block/unblock."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, IPvAnyAddress

from app.auth.token import admin_auth
from app.services import fail2ban

# Read-only listing lives under /api
router = APIRouter(
    prefix="/admin/{token}/api",
    dependencies=[Depends(admin_auth)],
    tags=["bans"],
)

# Mutating actions live under /action (matches BWG's URL convention)
action_router = APIRouter(
    prefix="/admin/{token}/action",
    dependencies=[Depends(admin_auth)],
    tags=["bans"],
)


class IPBody(BaseModel):
    # IPvAnyAddress validates IPv4 + IPv6 and rejects malformed input.
    ip: IPvAnyAddress


@router.get("/bans")
async def list_bans() -> dict:
    return fail2ban.jail_status()


@action_router.post("/block")
async def block_ip(body: IPBody) -> dict:
    ip_str = str(body.ip)
    fail2ban.ban(ip_str)
    return {"ip": ip_str, "action": "blocked"}


@action_router.post("/unblock")
async def unblock_ip(body: IPBody) -> dict:
    ip_str = str(body.ip)
    fail2ban.unban(ip_str)
    return {"ip": ip_str, "action": "unblocked"}
