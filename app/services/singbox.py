"""sing-box config IO + per-device inbound construction.

Reads / writes the JSON config at settings.paths.singbox_config.
reload_singbox() is fire-and-forget — call it as a FastAPI BackgroundTask
so the HTTP response leaves first, then sing-box restarts.
"""

from __future__ import annotations

import contextlib
import copy
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app.config import get_settings


def read_config() -> dict[str, Any]:
    return json.loads(Path(get_settings().paths.singbox_config).read_text())


def write_config(cfg: dict[str, Any], *, defer_reload: bool = False) -> None:
    target = Path(get_settings().paths.singbox_config)
    tmp = target.with_suffix(target.suffix + ".new")
    data = json.dumps(cfg, indent=2, ensure_ascii=False)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, target)
        target.chmod(0o600)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise
    if not defer_reload:
        reload_singbox()


def signal_reload() -> bool:
    """Ask the Docker sing-box wrapper to reload via a shared flag file."""
    flag = os.environ.get("PROXYBOX_SINGBOX_RELOAD_FILE")
    if not flag:
        return False
    path = Path(flag)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return True


def reload_singbox() -> None:
    """SIGHUP first (preserves connections), fall back to restart on failure.

    Sleeps 5s up front so a triggering HTTP response can travel back to the
    client through the same sing-box proxy before sing-box itself restarts.
    """
    time.sleep(5)
    if signal_reload():
        return
    with contextlib.suppress(subprocess.SubprocessError, OSError):
        result = subprocess.run(
            ["systemctl", "reload", "sing-box"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return
    with contextlib.suppress(subprocess.SubprocessError, OSError):
        subprocess.run(
            ["systemctl", "restart", "--no-block", "sing-box"],
            capture_output=True,
            timeout=10,
        )


def find_template_inbound(cfg: dict[str, Any], kind: str) -> dict[str, Any]:
    """First inbound of the given type — used as template for per-device clones.

    Prefers tags ending in ``-template`` so that operator-added per-device
    inbounds are never accidentally used as the template.
    """
    for inbound in cfg.get("inbounds", []):
        if inbound.get("type") == kind and inbound.get("tag", "").endswith("-template"):
            return inbound
    for inbound in cfg.get("inbounds", []):
        if inbound.get("type") == kind:
            return inbound
    raise HTTPException(500, f"no template inbound for protocol {kind!r}")


def allocate_ports(cfg: dict[str, Any]) -> tuple[int, int]:
    """One vless port + one hy2 port from the configured ranges (no alt ports)."""
    ports = get_settings().ports
    used: set[int | None] = {inb.get("listen_port") for inb in cfg.get("inbounds", [])}

    vless_port = _next_free(used, ports.vless_range)
    used.add(vless_port)
    hy2_port = _next_free(used, ports.hy2_range)
    return vless_port, hy2_port


def _next_free(used: set[int | None], rng: tuple[int, int]) -> int:
    for port in range(rng[0], rng[1] + 1):
        if port not in used:
            return port
    raise HTTPException(503, f"no free port in range {rng}")


def add_device_inbounds(cfg: dict[str, Any], device: dict[str, Any]) -> list[str]:
    """Append vless-{name} and hy2-{name} inbounds. Idempotent on tag."""
    vless_tpl = find_template_inbound(cfg, "vless")
    hy2_tpl = find_template_inbound(cfg, "hysteria2")
    existing = {i.get("tag") for i in cfg.get("inbounds", [])}
    added: list[str] = []

    tpl_users = vless_tpl.get("users") or []
    flow = (tpl_users[0].get("flow") if tpl_users else None) or "xtls-rprx-vision"

    vless_tag = f"vless-{device['name']}"
    if vless_tag not in existing:
        inb = copy.deepcopy(vless_tpl)
        inb["tag"] = vless_tag
        inb["listen_port"] = device["vless_port"]
        inb["users"] = [{"name": device["name"], "uuid": device["vless_uuid"], "flow": flow}]
        cfg.setdefault("inbounds", []).append(inb)
        added.append(vless_tag)

    hy2_tag = f"hy2-{device['name']}"
    if hy2_tag not in existing:
        inb = copy.deepcopy(hy2_tpl)
        inb["tag"] = hy2_tag
        inb["listen_port"] = device["hy2_port"]
        inb["users"] = [{"name": device["name"], "password": device["hy2_password"]}]
        cfg.setdefault("inbounds", []).append(inb)
        added.append(hy2_tag)

    return added


def remove_device_inbounds(cfg: dict[str, Any], device_name: str) -> list[str]:
    """Strip vless-{name} and hy2-{name} inbounds. Returns removed tags."""
    targets = {f"vless-{device_name}", f"hy2-{device_name}"}
    kept: list[dict[str, Any]] = []
    removed: list[str] = []
    for inbound in cfg.get("inbounds", []):
        if inbound.get("tag") in targets:
            removed.append(inbound["tag"])
        else:
            kept.append(inbound)
    cfg["inbounds"] = kept
    return removed
