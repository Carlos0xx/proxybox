"""Historical traffic queries over the ``traffic_log`` table.

Four read-only endpoints powering the SPA charts:
- /history/devices       per-device daily totals (stacked bar)
- /history/device/{name} single-device hourly buckets (heatmap)
- /history/all-daily     system-wide daily totals
- /history/export        CSV dump (one row per traffic_log row)

The BWG endpoint /api/history/apps (host-group fingerprint) is dropped
per CONSTRAINTS §3 — no host-level data is stored.
"""

from __future__ import annotations

import csv
import io
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response

from app.auth.token import admin_auth
from app.db.connection import connection

router = APIRouter(
    prefix="/admin/{token}/api/history",
    dependencies=[Depends(admin_auth)],
    tags=["history"],
)

NameInPath = Annotated[str, Path(pattern=r"^[a-zA-Z0-9_-]{3,32}$")]
DaysQuery = Annotated[int, Query(ge=1, le=90)]


def _cutoff_ts(days: int) -> int:
    return int((datetime.now(UTC) - timedelta(days=days)).timestamp())


@router.get("/devices")
async def history_devices(days: DaysQuery = 7) -> dict:
    """Per-device daily totals over the last N days.

    Response shape is denormalised so the SPA's loadTrafficOverview can
    render directly without a second lookup — each row carries label/kind
    from the device table, daily entries carry total=rx+tx, and
    top-level fields cache derived stats (dates, grand_total,
    active_count).
    """
    cutoff = _cutoff_ts(days)
    with connection() as conn:
        rows = conn.execute(
            """SELECT device_name, date,
                      SUM(rx_bytes) AS rx,
                      SUM(tx_bytes) AS tx
               FROM traffic_log
               WHERE bucket_ts >= ?
               GROUP BY device_name, date
               ORDER BY device_name, date""",
            (cutoff,),
        ).fetchall()
        meta = {
            r["name"]: {"label": r["label"], "kind": r["kind"]}
            for r in conn.execute("SELECT name, label, kind FROM device").fetchall()
        }

    by_dev: dict[str, list[dict]] = {}
    all_dates: set[str] = set()
    for r in rows:
        rx, tx = int(r["rx"] or 0), int(r["tx"] or 0)
        by_dev.setdefault(r["device_name"], []).append(
            {"date": r["date"], "rx": rx, "tx": tx, "total": rx + tx}
        )
        all_dates.add(r["date"])

    devices = []
    grand_total = 0
    active = 0
    for name, daily in by_dev.items():
        d_total = sum(d["total"] for d in daily)
        grand_total += d_total
        if d_total > 0:
            active += 1
        m = meta.get(name, {})
        devices.append(
            {
                "name": name,
                "label": m.get("label") or name,
                "kind": m.get("kind", "generic"),
                "daily": daily,
                "total": d_total,
            }
        )
    devices.sort(key=lambda x: -x["total"])

    return {
        "days": days,
        "devices": devices,
        "dates": sorted(all_dates),
        "grand_total": grand_total,
        "active_count": active,
    }


@router.get("/device/{name}")
async def history_device(name: NameInPath, days: DaysQuery = 7) -> dict:
    """Single device — hourly buckets, daily rollup, and device metadata.

    SPA's `renderHistoryDevice` reads `d.device.label`, `d.daily`,
    `d.hosts`, `d.apps`. v0.1.x doesn't track host-/app-level fingerprints
    (per CONSTRAINTS §3 — BWG's host dictionary is intentionally dropped),
    so those two come back as empty lists; the SPA renders that as
    "暂无数据" — correct outcome.
    """
    cutoff = _cutoff_ts(days)
    with connection() as conn:
        rows = conn.execute(
            """SELECT bucket_ts, date, hour, rx_bytes, tx_bytes, conn_count
               FROM traffic_log
               WHERE device_name = ? AND bucket_ts >= ?
               ORDER BY bucket_ts""",
            (name, cutoff),
        ).fetchall()
        dev_row = conn.execute(
            "SELECT name, label, kind, last_ip, last_seen FROM device WHERE name = ?",
            (name,),
        ).fetchone()

    if dev_row is None:
        raise HTTPException(404, f"device {name!r} not found")

    buckets = []
    daily_map: dict[str, dict[str, int]] = {}
    for r in rows:
        rx, tx = int(r["rx_bytes"] or 0), int(r["tx_bytes"] or 0)
        buckets.append(
            {
                "bucket_ts": r["bucket_ts"],
                "date": r["date"],
                "hour": r["hour"],
                "rx": rx,
                "tx": tx,
                "conn_count": r["conn_count"],
            }
        )
        day = daily_map.setdefault(r["date"], {"date": r["date"], "rx": 0, "tx": 0, "total": 0})
        day["rx"] += rx
        day["tx"] += tx
        day["total"] += rx + tx

    # Per-host / per-app rollups from host_log (v0.1.9+). Empty before
    # the host-tracking worker has had time to populate buckets; the SPA
    # renders both as "(none yet)" cards rather than crashing.
    with connection() as conn:
        host_rows = conn.execute(
            """SELECT host, app_group,
                      SUM(rx_bytes) AS rx, SUM(tx_bytes) AS tx,
                      SUM(conn_count) AS conns
               FROM host_log
               WHERE device_name = ? AND bucket_ts >= ?
               GROUP BY host
               ORDER BY (SUM(rx_bytes) + SUM(tx_bytes)) DESC
               LIMIT 200""",
            (name, cutoff),
        ).fetchall()
        app_rows = conn.execute(
            """SELECT app_group,
                      SUM(rx_bytes + tx_bytes) AS total,
                      SUM(conn_count) AS conns,
                      COUNT(DISTINCT host) AS host_count
               FROM host_log
               WHERE device_name = ? AND bucket_ts >= ?
               GROUP BY app_group
               ORDER BY total DESC""",
            (name, cutoff),
        ).fetchall()

    hosts = [
        {
            "hostname": r["host"],
            "app_group": r["app_group"],
            "rx": int(r["rx"] or 0),
            "tx": int(r["tx"] or 0),
            "total": int((r["rx"] or 0) + (r["tx"] or 0)),
            "conns": int(r["conns"] or 0),
        }
        for r in host_rows
    ]
    apps = [
        {
            "app_group": r["app_group"],
            "total": int(r["total"] or 0),
            "conns": int(r["conns"] or 0),
            "host_count": int(r["host_count"] or 0),
        }
        for r in app_rows
    ]

    return {
        "name": name,
        "days": days,
        "device": {
            "name": dev_row["name"],
            "label": dev_row["label"] or dev_row["name"],
            "kind": dev_row["kind"],
            "last_ip": dev_row["last_ip"],
            "last_seen": dev_row["last_seen"],
        },
        "daily": [daily_map[d] for d in sorted(daily_map)],
        "buckets": buckets,
        "hosts": hosts,
        "apps": apps,
    }


@router.get("/all-daily")
async def history_all_daily(days: DaysQuery = 7) -> dict:
    """System-wide daily totals over N days (no device dimension)."""
    cutoff = _cutoff_ts(days)
    with connection() as conn:
        rows = conn.execute(
            """SELECT date,
                      SUM(rx_bytes) AS rx,
                      SUM(tx_bytes) AS tx,
                      COUNT(DISTINCT device_name) AS active_devices
               FROM traffic_log
               WHERE bucket_ts >= ?
               GROUP BY date
               ORDER BY date""",
            (cutoff,),
        ).fetchall()
    return {
        "days": days,
        "daily": [
            {
                "date": r["date"],
                "rx": r["rx"],
                "tx": r["tx"],
                "active_devices": r["active_devices"],
            }
            for r in rows
        ],
    }


@router.get("/export")
async def history_export(days: DaysQuery = 7, format: str = "csv") -> Response:
    """CSV dump of every traffic_log row in the window (one bucket per line)."""
    if format != "csv":
        raise HTTPException(400, "only format=csv is supported")

    cutoff = _cutoff_ts(days)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["device_name", "date", "hour", "bucket_ts", "rx_bytes", "tx_bytes", "conn_count"]
    )
    with connection() as conn:
        for r in conn.execute(
            """SELECT device_name, date, hour, bucket_ts, rx_bytes, tx_bytes, conn_count
               FROM traffic_log
               WHERE bucket_ts >= ?
               ORDER BY device_name, bucket_ts""",
            (cutoff,),
        ):
            writer.writerow(
                [
                    r["device_name"],
                    r["date"],
                    r["hour"],
                    r["bucket_ts"],
                    r["rx_bytes"],
                    r["tx_bytes"],
                    r["conn_count"],
                ]
            )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="proxybox-history-{days}d.csv"'},
    )
