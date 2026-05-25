"""Regression tests for sensitive runtime file permissions."""

from __future__ import annotations

import os
import stat
from pathlib import Path

import yaml

from app.auth import passkey
from app.config import reset_settings_cache
from app.db.connection import connection
from app.services import caddy, singbox, subscriptions


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _write_config(tmp_path: Path, *, db_path: Path, singbox_path: Path) -> Path:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        f"""
admin:
  token: test-token
  username: admin
  login_path: login-secret
server:
  public_host: 203.0.113.10
paths:
  traffic_db: {db_path}
  static_dir: {tmp_path}
  sub_dir: {tmp_path / "subs"}
  singbox_config: {singbox_path}
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


def test_singbox_write_config_keeps_private_mode(tmp_path: Path, monkeypatch) -> None:
    cfg_path = _write_config(
        tmp_path,
        db_path=tmp_path / "traffic.db",
        singbox_path=tmp_path / "sing-box.json",
    )
    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))
    reset_settings_cache()

    old_umask = os.umask(0o022)
    try:
        singbox.write_config({"inbounds": [], "outbounds": []}, defer_reload=True)
    finally:
        os.umask(old_umask)
        reset_settings_cache()

    assert _mode(tmp_path / "sing-box.json") == 0o600


def test_sqlite_db_file_is_private_on_create(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "state" / "traffic.db"
    cfg_path = _write_config(
        tmp_path,
        db_path=db_path,
        singbox_path=tmp_path / "sing-box.json",
    )
    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))
    reset_settings_cache()

    old_umask = os.umask(0o022)
    try:
        with connection() as conn:
            conn.execute("SELECT 1").fetchone()
    finally:
        os.umask(old_umask)
        reset_settings_cache()

    assert _mode(db_path) == 0o600


def test_caddy_config_patch_keeps_config_private(tmp_path: Path, monkeypatch) -> None:
    cfg_path = _write_config(
        tmp_path,
        db_path=tmp_path / "traffic.db",
        singbox_path=tmp_path / "sing-box.json",
    )
    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))

    old_umask = os.umask(0o022)
    try:
        caddy._patch_config("proxybox.example.com")
    finally:
        os.umask(old_umask)
        reset_settings_cache()

    saved = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert saved["server"]["public_host"] == "proxybox.example.com"
    assert saved["passkey"]["rp_id"] == "proxybox.example.com"
    assert _mode(cfg_path) == 0o600


def test_session_secret_is_private_from_creation(tmp_path: Path, monkeypatch) -> None:
    cfg_path = _write_config(
        tmp_path,
        db_path=tmp_path / "traffic.db",
        singbox_path=tmp_path / "sing-box.json",
    )
    secret_path = tmp_path / "session-secret"
    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))
    reset_settings_cache()

    old_umask = os.umask(0o022)
    try:
        assert passkey._load_or_create_secret()
    finally:
        os.umask(old_umask)
        reset_settings_cache()

    assert _mode(secret_path) == 0o600


def test_subscription_file_is_private_from_creation(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cfg_path = _write_config(
        tmp_path,
        db_path=tmp_path / "traffic.db",
        singbox_path=tmp_path / "sing-box.json",
    )
    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))
    monkeypatch.setattr(
        subscriptions,
        "generate_subscription_text",
        lambda _device, _cfg=None: "vless://secret\nhysteria2://secret\n",
    )
    reset_settings_cache()

    old_umask = os.umask(0o022)
    try:
        path = subscriptions.write_subscription_file({"sub_token": "sub-token-123"})
    finally:
        os.umask(old_umask)
        reset_settings_cache()

    assert _mode(path) == 0o600
