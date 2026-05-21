"""System status probes: systemd unit state, load, mem, disk, cpu, hostname.

Linux-only — every probe degrades gracefully on missing files / tools.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from app.services.shell import run


def runtime_is_docker() -> bool:
    return os.environ.get("PROXYBOX_RUNTIME") == "docker"


def systemctl_is_active(unit: str) -> str:
    if runtime_is_docker():
        return _docker_service_state(unit)
    return run(["systemctl", "is-active", unit]).strip() or "unknown"


def _docker_service_state(unit: str) -> str:
    if unit == "proxybox-admin":
        return "active"
    if unit == "proxybox-traffic-worker":
        return _heartbeat_state()
    if unit == "sing-box":
        return _clash_api_state()
    return "unknown"


def _heartbeat_state() -> str:
    raw_path = os.environ.get("PROXYBOX_TRAFFIC_HEARTBEAT")
    if not raw_path:
        return "unknown"
    path = Path(raw_path)
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return "activating"
    return "active" if age <= 45 else "failed"


def _clash_api_state() -> str:
    try:
        from app.config import get_settings

        settings = get_settings()
        headers: dict[str, str] = {}
        if settings.clash.api_secret:
            headers["Authorization"] = f"Bearer {settings.clash.api_secret}"
        req = urllib.request.Request(f"{settings.clash.api_url}/connections", headers=headers)
        with urllib.request.urlopen(req, timeout=2) as r:
            json.load(r)
        return "active"
    except urllib.error.HTTPError as e:
        return "active" if e.code in {401, 403} else "failed"
    except Exception:
        return "failed"


def loadavg() -> list[str]:
    try:
        return Path("/proc/loadavg").read_text().split()[:3]
    except OSError:
        return ["0", "0", "0"]


def uptime_pretty() -> str:
    return run(["uptime", "-p"]).strip()


def mem_stats() -> dict[str, float | int]:
    out = run(["free", "-m"])
    used, total = 0, 1
    for line in out.splitlines():
        if line.startswith("Mem:"):
            parts = line.split()
            total = int(parts[1])
            used = int(parts[2])
            break
    return {"used_mb": used, "total_mb": total, "pct": round(used * 100 / total, 1)}


def disk_stats(mountpoint: str = "/") -> dict[str, str]:
    lines = run(["df", "-h", mountpoint]).splitlines()
    if len(lines) < 2:
        return {"used": "?", "total": "?", "pct": "?"}
    parts = lines[1].split()
    if len(parts) < 6:
        return {"used": "?", "total": "?", "pct": "?"}
    return {"used": parts[2], "total": parts[1], "pct": parts[4]}


def cpu_pct() -> str:
    """%us + %sy from `top -bn1` first sample, parsed in Python.

    Previously piped through awk via ``shell=True``. Now run() refuses
    string commands so we read top's stdout and parse the `%Cpu(s):` line
    ourselves.
    """
    for line in run(["top", "-bn1"]).splitlines():
        s = line.lstrip()
        if not s.startswith("%Cpu"):
            continue
        # Examples (Debian / Ubuntu):
        #   %Cpu(s):  1.2 us,  0.4 sy,  0.0 ni, 98.4 id, 0.0 wa, ...
        #   %Cpu(s):  1,2 us,  0,4 sy,  0,0 ni, 98,4 id, ...    (some locales)
        parts = s.replace(",", ".").split()
        try:
            us = float(parts[1])
            sy = float(parts[3])
        except (IndexError, ValueError):
            return "0"
        return f"{us + sy:.1f}"
    return "0"


def hostname() -> str:
    try:
        return Path("/etc/hostname").read_text().strip()
    except OSError:
        return "unknown"
