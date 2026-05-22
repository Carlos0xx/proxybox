"""System-level traffic aggregation endpoints.

Read-only views over the ``traffic_log`` table populated by
``app.workers.traffic``. Numbers reflect what the worker has observed since
its last poll cycle — for live counts you may need to wait one poll_interval.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends

from app.auth.token import admin_auth
from app.db.connection import connection

router = APIRouter(
    prefix="/admin/{token}/api",
    dependencies=[Depends(admin_auth)],
    tags=["traffic"],
)


@router.get("/traffic")
async def system_traffic() -> dict:
    """Aggregate system traffic over the last 24h + per-hour breakdown."""
    now = datetime.now(UTC)
    cutoff_24h = int((now - timedelta(hours=24)).timestamp())
    today_str = now.strftime("%Y-%m-%d")

    with connection() as conn:
        totals_24h = conn.execute(
            """SELECT
                   COALESCE(SUM(rx_bytes), 0)  AS rx,
                   COALESCE(SUM(tx_bytes), 0)  AS tx,
                   COUNT(DISTINCT device_name) AS active_devices
               FROM traffic_log
               WHERE bucket_ts >= ?""",
            (cutoff_24h,),
        ).fetchone()

        today = conn.execute(
            """SELECT
                   COALESCE(SUM(rx_bytes), 0) AS rx,
                   COALESCE(SUM(tx_bytes), 0) AS tx
               FROM traffic_log
               WHERE date = ?""",
            (today_str,),
        ).fetchone()

        hourly = conn.execute(
            """SELECT bucket_ts,
                      SUM(rx_bytes) AS rx,
                      SUM(tx_bytes) AS tx
               FROM traffic_log
               WHERE bucket_ts >= ?
               GROUP BY bucket_ts
               ORDER BY bucket_ts""",
            (cutoff_24h,),
        ).fetchall()

    return {
        "window_hours": 24,
        "rx_24h": totals_24h["rx"],
        "tx_24h": totals_24h["tx"],
        "rx_today": today["rx"],
        "tx_today": today["tx"],
        "active_devices_24h": totals_24h["active_devices"],
        "hourly": [{"bucket_ts": r["bucket_ts"], "rx": r["rx"], "tx": r["tx"]} for r in hourly],
    }
