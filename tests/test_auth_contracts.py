"""Auth route contract regressions."""

from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.auth import passkey
from app.auth import token as token_auth
from app.config import reset_settings_cache
from app.db.connection import connection


def _request(peer: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/admin/test-token/api/status",
            "scheme": "http",
            "headers": [],
            "client": (peer, 12345),
            "server": ("testserver", 80),
        }
    )


def test_bot_token_only_auth_is_loopback_only(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = SimpleNamespace(
        admin=SimpleNamespace(token="test-token"),
        features=SimpleNamespace(url_token_bypass=False, bot=True),
    )
    monkeypatch.setattr(token_auth, "get_settings", lambda: settings)

    assert asyncio.run(token_auth.admin_auth(_request("127.0.0.1"), "test-token")) == "test-token"

    with pytest.raises(HTTPException):
        asyncio.run(token_auth.admin_auth(_request("198.51.100.10"), "test-token"))


def test_session_cookie_name_is_scoped_per_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        passkey,
        "get_settings",
        lambda: SimpleNamespace(admin=SimpleNamespace(token="native-token")),
    )
    native_name = passkey.session_cookie_name()
    monkeypatch.setattr(
        passkey,
        "get_settings",
        lambda: SimpleNamespace(admin=SimpleNamespace(token="docker-token")),
    )
    docker_name = passkey.session_cookie_name()

    assert native_name.startswith("proxybox_admin_session_")
    assert docker_name.startswith("proxybox_admin_session_")
    assert native_name != docker_name
    assert native_name != "proxybox_admin_session"


def _write_config(tmp_path: Path, *, passkey: bool = False) -> Path:
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
  traffic_db: {tmp_path / "traffic.db"}
  static_dir: {tmp_path}
  sub_dir: {tmp_path / "subs"}
  singbox_config: {tmp_path / "sing-box.json"}
  session_secret: {tmp_path / "session-secret"}
  admin_password_file: {tmp_path / "admin.password"}
features:
  passkey: {str(passkey).lower()}
  bot: false
  url_token_bypass: true
passkey:
  rp_id: proxybox.example.com
  origin: https://proxybox.example.com
""".lstrip(),
        encoding="utf-8",
    )
    cfg_path.chmod(0o600)
    return cfg_path


def test_docs_routes_are_not_exposed_in_app(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg_path = _write_config(tmp_path)
    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))
    reset_settings_cache()
    try:
        from app.main import create_app

        app = create_app()
        paths = {route.path for route in app.routes}
    finally:
        reset_settings_cache()

    assert "/docs" not in paths
    assert "/redoc" not in paths
    assert "/openapi.json" not in paths


def test_passkey_list_returns_full_id_for_revoke_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg_path = _write_config(tmp_path, passkey=True)
    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))
    reset_settings_cache()
    from app.main import create_app

    app = create_app()

    try:
        with TestClient(app) as client:
            with connection() as conn:
                conn.execute(
                    """INSERT INTO passkey_credential
                       (credential_id, public_key, sign_count, label, created_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    ("credential-full-id-123", b"public-key", 0, "laptop", 1234),
                )
                conn.commit()

            res = client.get("/admin/test-token/api/auth/passkeys")
            assert res.status_code == 200
            item = res.json()["passkeys"][0]
    finally:
        reset_settings_cache()

    assert item["id_full"] == "credential-full-id-123"
    assert item["id_short"] == "credential-f..."


def test_login_page_exposes_passkey_login_when_enabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg_path = _write_config(tmp_path, passkey=True)
    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))
    reset_settings_cache()
    from app.main import create_app

    try:
        app = create_app()
        with TestClient(app) as client:
            res = client.get("/login/login-secret?next=/admin/test-token/")
    finally:
        reset_settings_cache()

    assert res.status_code == 200
    assert "Passkey / Touch ID" in res.text
    assert "const opts = d1.options;" in res.text
    assert "/auth/webauthn/login/complete" in res.text


def test_password_login_sets_instance_scoped_cookie(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg_path = _write_config(tmp_path)
    password_file = tmp_path / "admin.password"
    password_file.write_text("secret-password", encoding="utf-8")
    password_file.chmod(0o400)
    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))
    reset_settings_cache()
    from app.main import create_app

    try:
        app = create_app()
        expected_cookie_name = passkey.session_cookie_name()
        with TestClient(app, follow_redirects=False) as client:
            res = client.post(
                "/login/login-secret",
                data={"username": "admin", "password": "secret-password"},
            )
    finally:
        reset_settings_cache()

    assert res.status_code == 303
    set_cookie = res.headers["set-cookie"]
    assert f"{expected_cookie_name}=" in set_cookie
    assert "proxybox_admin_session=" not in set_cookie


def test_login_page_is_chinese_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cfg_path = _write_config(tmp_path)
    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))
    reset_settings_cache()
    from app.main import create_app

    try:
        app = create_app()
        with TestClient(app) as client:
            client.cookies.set("proxybox-lang", "en")
            res = client.get("/login/login-secret?lang=en")
    finally:
        reset_settings_cache()

    assert res.status_code == 200
    assert '<html lang="zh-CN">' in res.text
    assert "输入用户名 + 密码登录后台" in res.text
    assert "登 录" in res.text
    assert "lang-switch" not in res.text
    assert "Log in" not in res.text
    assert "Wrong username or password" not in res.text
    assert "proxybox-lang" not in res.headers.get("set-cookie", "")
