"""System status probes: systemd unit state, load, mem, disk, cpu, hostname.

Linux-only — every probe degrades gracefully on missing files / tools.
"""

from __future__ import annotations

import json
import os
import re
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.services.shell import run


def runtime_is_docker() -> bool:
    return os.environ.get("PROXYBOX_RUNTIME") == "docker"


def systemctl_is_active(unit: str) -> str:
    if runtime_is_docker():
        return _docker_service_state(unit)
    return run(["systemctl", "is-active", unit]).strip() or "unknown"


def project_port_statuses(settings: Any | None = None) -> list[dict[str, Any]]:
    """Return health rows for every ProxyBox service port we know about.

    Native installs can inspect host sockets with ``ss``. Docker installs run
    inside the admin container, so they cannot reliably inspect host-published
    ports; for those rows we use the owning service's internal health probe.
    """
    if settings is None:
        from app.config import get_settings

        settings = get_settings()

    docker = runtime_is_docker()
    rows: list[dict[str, Any]] = []

    admin_port = int(getattr(settings.admin, "port", 8080) or 8080)
    rows.append(
        _port_row(
            key=f"admin:tcp:{admin_port}",
            label="Admin UI",
            desc="Web 后台",
            proto="tcp",
            port=admin_port,
            owner="proxybox-admin",
            status=systemctl_is_active("proxybox-admin")
            if docker
            else _port_listening_state("tcp", admin_port),
        )
    )

    clash_url = str(getattr(settings.clash, "api_url", "") or "")
    clash_host, clash_port = _url_host_port(clash_url)
    if clash_port:
        rows.append(
            _port_row(
                key=f"clash:tcp:{clash_port}",
                label="Clash API",
                desc="sing-box 控制接口",
                proto="tcp",
                port=clash_port,
                owner="sing-box",
                host=clash_host,
                status=_clash_api_state()
                if docker
                else _tcp_connect_state(clash_host or "127.0.0.1", clash_port),
            )
        )

    singbox_state = systemctl_is_active("sing-box")
    for row in _singbox_port_rows(settings, docker=docker, singbox_state=singbox_state):
        rows.append(row)

    monitored = set(getattr(getattr(settings, "services", None), "monitored", []) or [])
    if "caddy" in monitored or (not docker and systemctl_is_active("caddy") == "active"):
        for port, label in ((80, "HTTP"), (443, "HTTPS")):
            rows.append(
                _port_row(
                    key=f"caddy:tcp:{port}",
                    label=f"Caddy {label}",
                    desc="HTTPS 反向代理",
                    proto="tcp",
                    port=port,
                    owner="caddy",
                    status=_port_listening_state("tcp", port) if not docker else "unknown",
                )
            )

    return _dedupe_ports(rows)


def _docker_service_state(unit: str) -> str:
    if unit == "proxybox-admin":
        return "active"
    if unit == "proxybox-traffic-worker":
        return _heartbeat_state("PROXYBOX_TRAFFIC_HEARTBEAT")
    if unit == "proxybox-watchdog":
        return _heartbeat_state("PROXYBOX_WATCHDOG_HEARTBEAT")
    if unit == "proxybox-docker-guard":
        return _docker_guard_state()
    if unit == "sing-box":
        return _clash_api_state()
    return "unknown"


def _port_row(
    *,
    key: str,
    label: str,
    desc: str,
    proto: str,
    port: int,
    owner: str,
    status: str,
    host: str = "",
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "desc": desc,
        "proto": proto,
        "port": port,
        "owner": owner,
        "host": host,
        "status": status or "unknown",
    }


def _url_host_port(url: str) -> tuple[str, int | None]:
    if not url:
        return "", None
    parsed = urlparse(url)
    if not parsed.hostname:
        return "", None
    if parsed.port:
        return parsed.hostname, parsed.port
    if parsed.scheme == "https":
        return parsed.hostname, 443
    if parsed.scheme == "http":
        return parsed.hostname, 80
    return parsed.hostname, None


def _singbox_port_rows(settings: Any, *, docker: bool, singbox_state: str) -> list[dict[str, Any]]:
    try:
        cfg = json.loads(Path(settings.paths.singbox_config).read_text())
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return []

    rows: list[dict[str, Any]] = []
    for inbound in cfg.get("inbounds", []):
        if not isinstance(inbound, dict):
            continue
        try:
            port = int(inbound.get("listen_port"))
        except (TypeError, ValueError):
            continue
        kind = str(inbound.get("type") or "")
        tag = str(inbound.get("tag") or kind or f"port-{port}")
        proto = _inbound_proto(kind)
        label = _inbound_label(tag, kind)
        status = singbox_state if docker else _port_listening_state(proto, port)
        rows.append(
            _port_row(
                key=f"sing-box:{proto}:{port}:{tag}",
                label=label,
                desc=f"sing-box · {tag}",
                proto=proto,
                port=port,
                owner="sing-box",
                host="sing-box" if docker else "",
                status=status,
            )
        )
    return rows


def _inbound_proto(kind: str) -> str:
    return "udp" if kind in {"hysteria2", "hysteria", "tuic"} else "tcp"


def _inbound_label(tag: str, kind: str) -> str:
    if tag == "vless-template":
        return "VLESS 模板"
    if tag == "hy2-template":
        return "Hy2 模板"
    if tag.startswith("vless-"):
        return f"VLESS · {tag.removeprefix('vless-')}"
    if tag.startswith("hy2-"):
        return f"Hy2 · {tag.removeprefix('hy2-')}"
    return tag or kind or "sing-box"


def _port_listening_state(proto: str, port: int) -> str:
    option = "-ltn" if proto == "tcp" else "-lun"
    out = run(["ss", "-H", option, "sport", "=", f":{port}"], timeout=2)
    if out.strip():
        return "active"
    # Some older ss builds are fussy about split filters. Fall back to parsing
    # the full listener list before marking the port failed.
    out = run(["ss", "-H", option], timeout=2)
    return "active" if port in _parse_ss_ports(out) else "failed"


def _parse_ss_ports(output: str) -> set[int]:
    ports: set[int] = set()
    for line in output.splitlines():
        for match in re.finditer(r":(\d+)(?:\s|$)", line):
            with_context = match.group(1)
            try:
                ports.add(int(with_context))
            except ValueError:
                continue
    return ports


def _tcp_connect_state(host: str, port: int) -> str:
    target = "127.0.0.1" if host in {"", "0.0.0.0", "::"} else host
    try:
        with socket.create_connection((target, port), timeout=1):
            return "active"
    except OSError:
        return "failed"


def _dedupe_ports(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, int, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        marker = (str(row.get("proto")), int(row.get("port") or 0), str(row.get("owner")))
        if marker in seen:
            continue
        seen.add(marker)
        out.append(row)
    return out


def _heartbeat_state(env_name: str) -> str:
    raw_path = os.environ.get(env_name)
    if not raw_path:
        return "unknown"
    path = Path(raw_path)
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return "activating"
    return "active" if age <= 45 else "failed"


def _docker_guard_state() -> str:
    raw_path = os.environ.get("PROXYBOX_DOCKER_GUARD_STATUS")
    if not raw_path:
        return "unknown"
    path = Path(raw_path)
    try:
        age = time.time() - path.stat().st_mtime
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "activating"
    if age > 180:
        return "failed"
    for line in text.splitlines():
        key, _, value = line.partition("=")
        if key == "state":
            state = value.strip()
            return state if state in {"active", "failed", "activating", "checking"} else "unknown"
    return "active"


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
    out = run(["uptime", "-p"]).strip()
    if out:
        return out
    try:
        seconds = int(float(Path("/proc/uptime").read_text().split()[0]))
    except (OSError, IndexError, ValueError):
        return ""
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes = rem // 60
    parts: list[str] = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes or not parts:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    return "up " + ", ".join(parts[:2])


def mem_stats() -> dict[str, float | int]:
    try:
        meminfo: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            key, value = line.split(":", 1)
            meminfo[key] = int(value.split()[0])
        total = max(1, meminfo["MemTotal"] // 1024)
        available = meminfo.get("MemAvailable", 0) // 1024
        used = max(0, total - available)
        return {"used_mb": used, "total_mb": total, "pct": round(used * 100 / total, 1)}
    except (OSError, KeyError, IndexError, ValueError):
        pass

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
