"""Wrapper around fail2ban-client for manual IP bans.

The ProxyBox jail (``[manual]`` in
``/etc/fail2ban/jail.d/proxybox.local``) is configured with maxretry=99999
so fail2ban itself never auto-bans — every ban is explicit via the admin
endpoints. install.sh creates the jail.
"""

from __future__ import annotations

import re

from fastapi import HTTPException

from app.services import system_stats
from app.services.shell import run

DEFAULT_JAIL = "manual"


def _docker_status(jail: str) -> dict:
    return {
        "jail": jail,
        "currently_banned": 0,
        "total_banned": 0,
        "banned": [],
        "available": False,
        "backend": "docker-disabled",
        "note": "Docker 默认安装不读取或修改宿主机 fail2ban。",
    }


def _check_available() -> None:
    out = run(["fail2ban-client", "ping"], timeout=3)
    if "pong" not in out.lower():
        raise HTTPException(503, "fail2ban not running or not installed")


def jail_status(jail: str = DEFAULT_JAIL) -> dict:
    """Parse `fail2ban-client status <jail>` into a JSON-friendly dict."""
    if system_stats.runtime_is_docker():
        return _docker_status(jail)
    _check_available()
    out = run(["fail2ban-client", "status", jail], timeout=5)
    info: dict = {
        "jail": jail,
        "currently_banned": 0,
        "total_banned": 0,
        "banned": [],
        "available": True,
        "backend": "fail2ban",
    }
    for line in out.splitlines():
        if "Currently banned:" in line:
            m = re.search(r"(\d+)", line)
            if m:
                info["currently_banned"] = int(m.group(1))
        elif "Total banned:" in line:
            m = re.search(r"(\d+)", line)
            if m:
                info["total_banned"] = int(m.group(1))
        elif "Banned IP list:" in line:
            ips = line.split(":", 1)[1].strip()
            info["banned"] = ips.split() if ips else []
    return info


def ban(ip: str, jail: str = DEFAULT_JAIL) -> None:
    if system_stats.runtime_is_docker():
        raise HTTPException(
            501,
            "Docker 默认安装不修改宿主机 fail2ban，请使用宿主防火墙或云防火墙封禁 IP",
        )
    _check_available()
    run(["fail2ban-client", "set", jail, "banip", ip], timeout=5)


def unban(ip: str, jail: str = DEFAULT_JAIL) -> None:
    if system_stats.runtime_is_docker():
        raise HTTPException(
            501,
            "Docker 默认安装不修改宿主机 fail2ban，请使用宿主防火墙或云防火墙解封 IP",
        )
    _check_available()
    run(["fail2ban-client", "set", jail, "unbanip", ip], timeout=5)
