"""System status + log inspection endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.responses import PlainTextResponse

from app.auth.token import admin_auth
from app.config import get_settings
from app.services import shell, system_stats

router = APIRouter(
    prefix="/admin/{token}/api",
    dependencies=[Depends(admin_auth)],
    tags=["system"],
)


SvcInPath = Annotated[str, Path(pattern=r"^[a-zA-Z0-9._-]{1,64}$")]
LinesQuery = Annotated[int, Query(ge=1, le=1000)]


@router.get("/status")
async def status() -> dict:
    settings = get_settings()
    return {
        "services": {
            unit: system_stats.systemctl_is_active(unit) for unit in settings.services.monitored
        },
        "load": system_stats.loadavg(),
        "uptime": system_stats.uptime_pretty(),
        "mem": system_stats.mem_stats(),
        "disk": system_stats.disk_stats(),
        "cpu_pct": system_stats.cpu_pct(),
        "now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "hostname": system_stats.hostname(),
    }


@router.get("/logs/{name}", response_class=PlainTextResponse)
async def logs(name: SvcInPath, n: LinesQuery = 50) -> str:
    """``journalctl -u {name} -n {n} --no-pager`` — name gated by allowlist.

    Same whitelist policy as /action/restart: only services declared in
    config.services.monitored can be inspected, to avoid arbitrary unit
    introspection via this endpoint.
    """
    settings = get_settings()
    if name not in settings.services.monitored:
        raise HTTPException(
            400,
            f"service {name!r} not in monitored allowlist — only services in "
            f"config.services.monitored can be inspected",
        )
    if system_stats.runtime_is_docker():
        return (
            "Docker 模式不读取宿主机 journalctl。\n"
            f"请在项目目录运行: docker compose logs --tail={n} {name}\n"
        )
    return shell.run(["journalctl", "-u", name, "-n", str(n), "--no-pager"], timeout=10)
