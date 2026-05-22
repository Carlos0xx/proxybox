"""Device deletion should remove retained per-device history."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import BackgroundTasks

from app.config import reset_settings_cache
from app.db.connection import connection
from app.db.init import init_schema
from app.routers import devices


def _write_config(tmp_path: Path) -> Path:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
admin:
  token: test-token
server:
  public_host: 203.0.113.10
paths:
  traffic_db: {tmp_path / "traffic.db"}
  static_dir: {tmp_path}
  sub_dir: {tmp_path / "subs"}
  singbox_config: {tmp_path / "sing-box.json"}
  session_secret: {tmp_path / "session-secret"}
  admin_password_file: {tmp_path / "admin.password"}
features:
  passkey: false
  bot: false
  url_token_bypass: false
""".lstrip(),
        encoding="utf-8",
    )
    cfg_path.chmod(0o600)
    return cfg_path


def test_delete_device_removes_traffic_and_host_history(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cfg_path = _write_config(tmp_path)
    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))
    reset_settings_cache()
    init_schema()

    with connection() as conn:
        conn.execute(
            """INSERT INTO device
               (name, label, kind, vless_uuid, hy2_password, vless_port, hy2_port,
                sni, created_at, notes, sub_token)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                "phone-1",
                "phone",
                "mobile",
                "00000000-0000-0000-0000-000000000001",
                "hy2-password",
                11001,
                21001,
                "www.example.com",
                1234,
                "",
                "sub-token-123",
            ),
        )
        conn.execute(
            """INSERT INTO traffic_log
               (device_name, bucket_ts, date, hour, rx_bytes, tx_bytes, conn_count)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("phone-1", 1000, "2026-05-21", 1, 10, 20, 1),
        )
        conn.execute(
            """INSERT INTO host_log
               (device_name, bucket_ts, date, hour, host, app_group, rx_bytes, tx_bytes,
                conn_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            ("phone-1", 1000, "2026-05-21", 1, "example.com", "Other", 10, 20, 1),
        )
        conn.commit()

    monkeypatch.setattr(devices.singbox, "read_config", lambda: {"inbounds": []})
    monkeypatch.setattr(devices.singbox, "write_config", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(devices.subscriptions, "delete_subscription_file", lambda _token: True)

    try:
        result = asyncio.run(devices.delete_device("phone-1", BackgroundTasks()))
        with connection() as conn:
            device_count = conn.execute("SELECT COUNT(*) FROM device").fetchone()[0]
            traffic_count = conn.execute("SELECT COUNT(*) FROM traffic_log").fetchone()[0]
            host_count = conn.execute("SELECT COUNT(*) FROM host_log").fetchone()[0]
    finally:
        reset_settings_cache()

    assert result["deleted_history_rows"] == 2
    assert device_count == 0
    assert traffic_count == 0
    assert host_count == 0
