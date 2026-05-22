"""System status + log inspection endpoints."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi import Path as ApiPath
from fastapi.responses import PlainTextResponse

from app.auth.token import admin_auth
from app.config import get_settings
from app.services import shell, system_stats

router = APIRouter(
    prefix="/admin/{token}/api",
    dependencies=[Depends(admin_auth)],
    tags=["system"],
)


SvcInPath = Annotated[str, ApiPath(pattern=r"^[a-zA-Z0-9._-]{1,64}$")]
LinesQuery = Annotated[int, Query(ge=1, le=1000)]

_DOCKER_LOG_NAMES = {
    "sing-box": "sing-box.log",
    "proxybox-admin": "proxybox-admin.log",
    "proxybox-traffic-worker": "proxybox-traffic-worker.log",
    "proxybox-watchdog": "proxybox-admin.log",
}


def _docker_log_dir() -> Path:
    return Path(os.environ.get("PROXYBOX_DOCKER_LOG_DIR", "/var/lib/proxybox/logs"))


def _tail_file(path: Path, n: int) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return "日志文件尚未生成，请稍等片刻后刷新。"
    except OSError as exc:
        return f"读取日志失败: {exc}"
    return "\n".join(lines[-n:]) + ("\n" if lines else "")


@router.get("/status")
async def status() -> dict:
    settings = get_settings()
    return {
        "services": {
            unit: system_stats.systemctl_is_active(unit) for unit in settings.services.monitored
        },
        "ports": system_stats.project_port_statuses(settings),
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
        log_name = _DOCKER_LOG_NAMES.get(name)
        if not log_name:
            return "Docker 模式下该服务没有容器内日志。"
        return _tail_file(_docker_log_dir() / log_name, n)
    return shell.run(["journalctl", "-u", name, "-n", str(n), "--no-pager"], timeout=10)
