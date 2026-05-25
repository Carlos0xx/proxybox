"""Live connections + throughput, proxied from sing-box's Clash API.

sing-box exposes a Clash-compatible API endpoint configured in
``config.yaml``. The same Clash API the traffic worker uses for bucketing
also exposes a snapshot of currently-open connections and instantaneous
up/down bps. We do not expose the Clash API directly to the browser — that
would bypass admin-token gating — instead we proxy it through this
admin-gated router and aggregate per-source-IP.

Per-device attribution: each connection's ``metadata.sourceIP`` is the
client's public IP (the user's phone / router). The ``device`` table
records each device's most-recent ``last_ip``, so joining by IP gives a
label for the row when a known device is connected. Unknown IPs (e.g. a
just-revoked device, or an IP-rotated mobile network) render with the
raw IP and an empty device_name.

Endpoint contract is intentionally a superset of what the legacy SPA used
to read, so the existing loadConns() / overview-KPI code paths can light up
without further changes.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, Depends

from app.auth.token import admin_auth
from app.config import get_settings
from app.db.connection import connection

_TIMEOUT = 2.0
# The Clash /traffic stream emits one {"up","down"} sample per second but
# interleaves spurious all-zero ticks even under sustained load, so a single
# read is unreliable (frequently shows 0 B/s mid-transfer). Read a few lines
# across this window and take the peak.
_SPEED_WINDOW = 2.5

router = APIRouter(
    prefix="/admin/{token}/api",
    dependencies=[Depends(admin_auth)],
    tags=["connections"],
)


def _fetch_json(path: str, *, stream: bool = False) -> dict[str, Any]:
    """Fetch JSON from the Clash API.

    Most endpoints return a complete JSON document. ``/traffic`` is a
    long-polling stream that emits one JSON line per second — never reaches
    EOF on its own. For that case pass ``stream=True`` and we read only the
    first line, then close the socket.
    """
    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.clash.api_secret:
        headers["Authorization"] = f"Bearer {settings.clash.api_secret}"
    try:
        req = urllib.request.Request(f"{settings.clash.api_url}{path}", headers=headers)
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            raw = resp.readline() if stream else resp.read()
        if not raw:
            return {}
        return json.loads(raw.split(b"\n", 1)[0])
    except (urllib.error.URLError, OSError, ValueError):
        return {}


def _traffic_speed() -> tuple[int, int]:
    """Peak (up, down) bytes/sec from the Clash /traffic stream.

    sing-box emits a sample per second but interleaves all-zero ticks even
    during an active transfer, so reading a single line frequently reports
    0 B/s mid-download. Read every sample within ``_SPEED_WINDOW`` and return
    the max of each direction — that ignores the spurious zero ticks while
    still reflecting the current throughput.
    """
    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.clash.api_secret:
        headers["Authorization"] = f"Bearer {settings.clash.api_secret}"
    up = down = 0
    try:
        req = urllib.request.Request(f"{settings.clash.api_url}/traffic", headers=headers)
        with urllib.request.urlopen(req, timeout=_SPEED_WINDOW + 1.0) as resp:
            deadline = time.monotonic() + _SPEED_WINDOW
            while time.monotonic() < deadline:
                raw = resp.readline()
                if not raw:
                    break
                try:
                    sample = json.loads(raw)
                except ValueError:
                    continue
                up = max(up, int(sample.get("up", 0) or 0))
                down = max(down, int(sample.get("down", 0) or 0))
    except (urllib.error.URLError, OSError, ValueError):
        pass
    return up, down


def _device_label_index() -> dict[str, dict[str, str]]:
    """Map last_ip → {name, label} for non-revoked devices."""
    with connection() as conn:
        rows = conn.execute(
            "SELECT name, label, last_ip FROM device WHERE revoked = 0 AND last_ip IS NOT NULL"
        ).fetchall()
    return {r["last_ip"]: {"name": r["name"], "label": r["label"]} for r in rows if r["last_ip"]}


def _conn_bytes_by_id(data: dict[str, Any]) -> dict[str, tuple[int, int]]:
    """Map connection id -> (cumulative upload, download) from a /connections snapshot."""
    out: dict[str, tuple[int, int]] = {}
    for c in data.get("connections", []) or []:
        cid = c.get("id")
        if cid:
            out[cid] = (int(c.get("upload") or 0), int(c.get("download") or 0))
    return out


@router.get("/connections")
async def get_connections() -> dict[str, Any]:
    # Two snapshots bracket the /traffic read so per-device speed is a byte
    # delta over the same window. Clash exposes only cumulative per-connection
    # bytes (no per-conn speed), so we diff by connection id: connections in
    # both snapshots contribute (now - then); new ones count from 0 next round;
    # closed ones drop out. Counter resets are clamped to >= 0.
    snap1 = _fetch_json("/connections")
    if not snap1:
        return {"count": 0, "connections": [], "error": "clash-api unreachable"}
    t1 = time.monotonic()
    prev = _conn_bytes_by_id(snap1)

    up_bps, down_bps = _traffic_speed()  # ~_SPEED_WINDOW seconds — also our delta window

    snap2 = _fetch_json("/connections") or snap1
    dt = max(0.5, time.monotonic() - t1)

    by_ip: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "tcp": 0,
            "udp": 0,
            "up_bytes": 0,
            "down_bytes": 0,
            "up_speed": 0,
            "down_speed": 0,
            "ports": set(),
        }
    )
    for c in snap2.get("connections", []) or []:
        meta = c.get("metadata") or {}
        ip = meta.get("sourceIP") or ""
        if not ip:
            continue
        slot = by_ip[ip]
        net = (meta.get("network") or "tcp").lower()
        if net == "udp":
            slot["udp"] += 1
        else:
            slot["tcp"] += 1
        cur_up = int(c.get("upload") or 0)
        cur_down = int(c.get("download") or 0)
        slot["up_bytes"] += cur_up
        slot["down_bytes"] += cur_down
        p = prev.get(c.get("id"))
        if p:
            slot["up_speed"] += max(0, cur_up - p[0])
            slot["down_speed"] += max(0, cur_down - p[1])
        dport = meta.get("destinationPort")
        if dport:
            slot["ports"].add(str(dport))

    # Convert accumulated per-IP byte deltas into bytes/sec over the window.
    for slot in by_ip.values():
        slot["up_speed"] = int(slot["up_speed"] / dt)
        slot["down_speed"] = int(slot["down_speed"] / dt)

    devices_by_ip = _device_label_index()

    connections = []
    for ip, agg in by_ip.items():
        dev = devices_by_ip.get(ip, {})
        connections.append(
            {
                "ip": ip,
                "device_name": dev.get("name", ""),
                "device_label": dev.get("label", ""),
                "tcp": agg["tcp"],
                "udp": agg["udp"],
                "up_bytes": agg["up_bytes"],
                "down_bytes": agg["down_bytes"],
                "up_speed": agg["up_speed"],
                "down_speed": agg["down_speed"],
                "total": agg["tcp"] + agg["udp"],
                "ports": sorted(agg["ports"])[:6],
                "geo": "",
            }
        )
    connections.sort(key=lambda x: -(x["up_bytes"] + x["down_bytes"]))

    return {
        "count": len(connections),
        "connections": connections,
        "up_bps": up_bps,
        "down_bps": down_bps,
        "total_upload_bytes": int(snap2.get("uploadTotal") or 0),
        "total_download_bytes": int(snap2.get("downloadTotal") or 0),
    }
