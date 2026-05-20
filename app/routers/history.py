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
from datetime import datetime, timedelta, timezone
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
    return int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())


@router.get("/devices")
async def history_devices(days: DaysQuery = 7) -> dict:
    """Per-device daily totals over the last N days."""
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

    by_dev: dict[str, list[dict]] = {}
    for r in rows:
        by_dev.setdefault(r["device_name"], []).append(
            {"date": r["date"], "rx": r["rx"], "tx": r["tx"]}
        )

    return {
        "days": days,
        "devices": [{"name": n, "daily": d} for n, d in by_dev.items()],
    }


@router.get("/device/{name}")
async def history_device(name: NameInPath, days: DaysQuery = 7) -> dict:
    """Single device — hourly buckets over N days (drives a date×hour heatmap)."""
    cutoff = _cutoff_ts(days)
    with connection() as conn:
        rows = conn.execute(
            """SELECT bucket_ts, date, hour, rx_bytes, tx_bytes, conn_count
               FROM traffic_log
               WHERE device_name = ? AND bucket_ts >= ?
               ORDER BY bucket_ts""",
            (name, cutoff),
        ).fetchall()

    return {
        "name": name,
        "days": days,
        "buckets": [
            {
                "bucket_ts": r["bucket_ts"],
                "date": r["date"],
                "hour": r["hour"],
                "rx": r["rx_bytes"],
                "tx": r["tx_bytes"],
                "conn_count": r["conn_count"],
            }
            for r in rows
        ],
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
                    r["device_name"], r["date"], r["hour"], r["bucket_ts"],
                    r["rx_bytes"], r["tx_bytes"], r["conn_count"],
                ]
            )
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="proxybox-history-{days}d.csv"'
        },
    )
