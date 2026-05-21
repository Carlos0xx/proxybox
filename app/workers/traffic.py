"""Traffic accounting worker.

Polls sing-box's Clash-compatible API endpoint for active connections,
diffs byte counts since the previous poll, and aggregates per-device
deltas into hourly UTC buckets in the ``traffic_log`` table.

Run as a daemon:
    python -m app.workers.traffic

The accompanying systemd unit lives at
``deploy/systemd/proxybox-traffic-worker.service`` and is installed by
install.sh. Each tick is independent — crashes just lose ≤ 1 cycle of
in-memory state, never corrupts the DB.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

from app.config import get_settings
from app.db.connection import connection
from app.services.host_classify import classify as classify_host

_PREV_CONNS: dict[str, dict] = {}


def _write_heartbeat() -> None:
    path = os.environ.get("PROXYBOX_TRAFFIC_HEARTBEAT")
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(str(int(time.time())), encoding="utf-8")


def _device_from_inbound_tag(tag: str) -> str | None:
    """Inbound tags follow ``vless-{name}`` or ``hy2-{name}``; templates are skipped."""
    for prefix in ("vless-", "hy2-"):
        if tag.startswith(prefix):
            name = tag[len(prefix) :]
            if name and name != "template":
                return name
    return None


def fetch_connections() -> list[dict]:
    settings = get_settings()
    headers: dict[str, str] = {}
    if settings.clash.api_secret:
        headers["Authorization"] = f"Bearer {settings.clash.api_secret}"
    req = urllib.request.Request(f"{settings.clash.api_url}/connections", headers=headers)
    with urllib.request.urlopen(req, timeout=5) as r:
        data = json.load(r)
    return data.get("connections") or []


def process_tick() -> int:
    """One poll cycle. Returns the number of distinct devices observed."""
    now = int(time.time())
    dt = datetime.now(UTC)
    hour_start = int(datetime(dt.year, dt.month, dt.day, dt.hour, tzinfo=UTC).timestamp())
    date_str = dt.strftime("%Y-%m-%d")
    hour_int = dt.hour

    try:
        conns = fetch_connections()
    except (urllib.error.URLError, OSError, json.JSONDecodeError) as e:
        print(f"[clash-fetch-error] {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        return 0

    active_cids: set[str] = set()
    deltas: dict[str, dict[str, int]] = {}
    devices_seen: dict[str, str] = {}
    # Per-device per-host deltas. host == "" when sing-box has no SNI/host
    # for this connection (rare; raw IP / DoH bypass). Skipped from host_log
    # so we never store a "(unknown)" bucket — keeps the table small.
    host_deltas: dict[tuple[str, str], dict[str, int]] = {}

    for c in conns:
        cid = c.get("id")
        if not cid:
            continue
        active_cids.add(cid)

        meta = c.get("metadata") or {}
        type_str = meta.get("type", "")
        if "/" not in type_str:
            continue
        inbound_tag = type_str.split("/", 1)[1]
        device_name = _device_from_inbound_tag(inbound_tag)
        if not device_name:
            continue

        devices_seen[device_name] = meta.get("sourceIP", "")
        host = (meta.get("host") or "").strip().lower()

        cur_up = c.get("upload", 0) or 0
        cur_dn = c.get("download", 0) or 0
        prev = _PREV_CONNS.get(cid)
        if prev:
            d_up = max(0, cur_up - prev["upload"])
            d_dn = max(0, cur_dn - prev["download"])
            is_new = False
        else:
            d_up, d_dn = cur_up, cur_dn
            is_new = True

        _PREV_CONNS[cid] = {"upload": cur_up, "download": cur_dn}

        if not is_new and d_up == 0 and d_dn == 0:
            continue

        agg = deltas.setdefault(device_name, {"rx": 0, "tx": 0, "new": 0})
        agg["rx"] += d_dn
        agg["tx"] += d_up
        if is_new:
            agg["new"] += 1

        if host:
            h_agg = host_deltas.setdefault((device_name, host), {"rx": 0, "tx": 0, "new": 0})
            h_agg["rx"] += d_dn
            h_agg["tx"] += d_up
            if is_new:
                h_agg["new"] += 1

    # GC connections that closed since last tick
    for cid in list(_PREV_CONNS.keys()):
        if cid not in active_cids:
            del _PREV_CONNS[cid]

    if not deltas and not devices_seen:
        return 0

    with connection() as conn:
        for dname, src in devices_seen.items():
            conn.execute(
                "UPDATE device SET last_seen = ?, last_ip = ? WHERE name = ?",
                (now, src, dname),
            )
        for dname, agg in deltas.items():
            conn.execute(
                """INSERT INTO traffic_log
                       (device_name, bucket_ts, date, hour, rx_bytes, tx_bytes, conn_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(device_name, bucket_ts) DO UPDATE SET
                       rx_bytes   = rx_bytes   + excluded.rx_bytes,
                       tx_bytes   = tx_bytes   + excluded.tx_bytes,
                       conn_count = conn_count + excluded.conn_count""",
                (dname, hour_start, date_str, hour_int, agg["rx"], agg["tx"], agg["new"]),
            )
        for (dname, host), h_agg in host_deltas.items():
            conn.execute(
                """INSERT INTO host_log
                       (device_name, bucket_ts, date, hour, host, app_group,
                        rx_bytes, tx_bytes, conn_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(device_name, bucket_ts, host) DO UPDATE SET
                       rx_bytes   = rx_bytes   + excluded.rx_bytes,
                       tx_bytes   = tx_bytes   + excluded.tx_bytes,
                       conn_count = conn_count + excluded.conn_count""",
                (
                    dname,
                    hour_start,
                    date_str,
                    hour_int,
                    host,
                    classify_host(host),
                    h_agg["rx"],
                    h_agg["tx"],
                    h_agg["new"],
                ),
            )
        conn.commit()

    return len(devices_seen)


def cleanup_old() -> int:
    settings = get_settings()
    cutoff = int(time.time()) - settings.worker.retention_days * 86400
    with connection() as conn:
        t = conn.execute("DELETE FROM traffic_log WHERE bucket_ts < ?", (cutoff,)).rowcount
        h = conn.execute("DELETE FROM host_log WHERE bucket_ts < ?", (cutoff,)).rowcount
        conn.commit()
    return t + h


def main() -> int:
    settings = get_settings()
    print(
        f"[traffic-worker] poll={settings.worker.poll_interval}s "
        f"retention={settings.worker.retention_days}d clash={settings.clash.api_url}",
        flush=True,
    )
    last_cleanup = 0.0
    while True:
        try:
            n = process_tick()
            if n:
                print(f"[tick] recorded {n} device(s)", flush=True)
        except Exception as e:
            print(f"[tick-error] {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        _write_heartbeat()

        if time.time() - last_cleanup > 86400:
            try:
                removed = cleanup_old()
                if removed:
                    print(
                        f"[cleanup] purged {removed} rows older than retention",
                        flush=True,
                    )
                last_cleanup = time.time()
            except Exception as e:
                print(f"[cleanup-error] {e}", file=sys.stderr, flush=True)

        time.sleep(settings.worker.poll_interval)


if __name__ == "__main__":
    sys.exit(main() or 0)
