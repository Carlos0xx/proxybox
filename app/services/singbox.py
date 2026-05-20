"""sing-box config IO + per-device inbound construction.

Reads / writes the JSON config at settings.paths.singbox_config.
reload_singbox() is fire-and-forget — call it as a FastAPI BackgroundTask
so the HTTP response leaves first, then sing-box restarts.
"""

from __future__ import annotations

import copy
import json
import shutil
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
    tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False))
    shutil.move(tmp, target)
    if not defer_reload:
        reload_singbox()


def reload_singbox() -> None:
    """SIGHUP first (preserves connections), fall back to restart on failure.

    Sleeps 5s up front so a triggering HTTP response can travel back to the
    client through the same sing-box proxy before sing-box itself restarts.
    """
    time.sleep(5)
    try:
        result = subprocess.run(
            ["systemctl", "reload", "sing-box"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return
    except (subprocess.SubprocessError, OSError):
        pass
    try:
        subprocess.run(
            ["systemctl", "restart", "--no-block", "sing-box"],
            capture_output=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError):
        pass


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
        inb["users"] = [
            {"name": device["name"], "uuid": device["vless_uuid"], "flow": flow}
        ]
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
