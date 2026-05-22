"""ProxyBox service and port watchdog.

The watchdog only acts on services declared in config.services.monitored and
ports returned by project_port_statuses(). It never scans or restarts arbitrary
host services.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.services import shell, singbox, system_stats

BAD_STATES = {"failed", "inactive", "deactivating"}
DEFAULT_INTERVAL_SECONDS = 20.0
DEFAULT_COOLDOWN_SECONDS = 60.0


def unhealthy_owners(settings: Any | None = None) -> list[str]:
    """Return ProxyBox service owners whose service or port health is bad."""
    if settings is None:
        settings = get_settings()

    owners: set[str] = set()
    monitored = list(getattr(getattr(settings, "services", None), "monitored", []) or [])

    for unit in monitored:
        if _is_bad_state(system_stats.systemctl_is_active(unit)):
            owners.add(unit)

    for row in system_stats.project_port_statuses(settings):
        if _is_bad_state(str(row.get("status") or "")):
            owner = str(row.get("owner") or "")
            if owner:
                owners.add(owner)

    return sorted(owners)


def check_once(
    *,
    settings: Any | None = None,
    cooldowns: dict[str, float] | None = None,
    now: float | None = None,
) -> list[dict[str, str]]:
    """Run one watchdog pass and return the recovery actions taken."""
    if settings is None:
        settings = get_settings()
    if cooldowns is None:
        cooldowns = {}
    if now is None:
        now = time.time()

    cooldown = _env_float("PROXYBOX_WATCHDOG_COOLDOWN", DEFAULT_COOLDOWN_SECONDS)
    actions: list[dict[str, str]] = []
    for owner in unhealthy_owners(settings):
        last = cooldowns.get(owner, 0.0)
        if now - last < cooldown:
            actions.append({"service": owner, "action": "cooldown"})
            continue
        cooldowns[owner] = now
        actions.append(recover_owner(owner, settings=settings))
    return actions


def recover_owner(owner: str, *, settings: Any | None = None) -> dict[str, str]:
    """Recover one ProxyBox-owned service in the current runtime."""
    if settings is None:
        settings = get_settings()

    if system_stats.runtime_is_docker():
        return _recover_docker_owner(owner)

    monitored = set(getattr(getattr(settings, "services", None), "monitored", []) or [])
    if owner not in monitored:
        return {"service": owner, "action": "skipped_not_monitored"}
    if owner == "proxybox-watchdog":
        return {"service": owner, "action": "covered_by_systemd_restart"}
    shell.run(["systemctl", "restart", "--no-block", owner], timeout=5)
    return {"service": owner, "action": "restart_requested"}


def main() -> None:
    """Run watchdog forever. Used by Docker admin entrypoint and systemd."""
    if os.environ.get("PROXYBOX_WATCHDOG_DISABLED") == "1":
        print("[watchdog] disabled by PROXYBOX_WATCHDOG_DISABLED=1", flush=True)
        return

    interval = _env_float("PROXYBOX_WATCHDOG_INTERVAL", DEFAULT_INTERVAL_SECONDS)
    cooldowns: dict[str, float] = {}
    print(
        f"[watchdog] started interval={interval:g}s "
        f"cooldown={_env_float('PROXYBOX_WATCHDOG_COOLDOWN', DEFAULT_COOLDOWN_SECONDS):g}s",
        flush=True,
    )
    while True:
        try:
            _touch_env_file("PROXYBOX_WATCHDOG_HEARTBEAT")
            for action in check_once(cooldowns=cooldowns):
                if action["action"] != "cooldown":
                    print(f"[watchdog] {action['service']}: {action['action']}", flush=True)
        except Exception as exc:
            print(f"[watchdog] check failed: {exc}", flush=True)
        time.sleep(interval)


def _recover_docker_owner(owner: str) -> dict[str, str]:
    if owner == "sing-box":
        if singbox.signal_reload():
            return {"service": owner, "action": "reload_requested"}
        return {"service": owner, "action": "covered_by_docker_restart_policy"}
    if owner == "proxybox-traffic-worker":
        if _touch_env_file("PROXYBOX_WORKER_RESTART_FILE"):
            return {"service": owner, "action": "restart_requested"}
        return {"service": owner, "action": "covered_by_docker_restart_policy"}
    if owner == "proxybox-watchdog":
        _touch_env_file("PROXYBOX_WATCHDOG_HEARTBEAT")
        return {"service": owner, "action": "heartbeat_refreshed"}
    return {"service": owner, "action": "covered_by_docker_restart_policy"}


def _touch_env_file(name: str) -> bool:
    value = os.environ.get(name)
    if not value:
        return False
    path = Path(value)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    return True


def _is_bad_state(state: str) -> bool:
    return state in BAD_STATES or state.startswith("failed")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value > 0 else default


if __name__ == "__main__":
    main()
