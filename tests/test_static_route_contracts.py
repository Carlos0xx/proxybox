"""Static SPA strings that must stay aligned with backend route contracts."""

from __future__ import annotations

from pathlib import Path

STATIC_HTML = Path("static/index.html").read_text(encoding="utf-8")


def test_passkey_management_calls_token_scoped_backend_routes() -> None:
    assert "/admin/auth/" not in STATIC_HTML
    assert "pkFetch('/api/auth/passkeys')" in STATIC_HTML
    assert "pkFetch('/api/auth/webauthn/register/begin'" in STATIC_HTML
    assert "pkFetch('/api/auth/webauthn/register/complete'" in STATIC_HTML
    assert "pkFetch('/api/auth/passkeys/' + cidEnc" in STATIC_HTML
    assert "p.id_full" in STATIC_HTML
    assert "p.id_short" in STATIC_HTML


def test_admin_token_rotation_dialog_uses_returned_contract() -> None:
    assert "env_backup" not in STATIC_HTML
    assert "new URL(d.new_admin_url || d.new_url_prefix, window.location.origin)" in STATIC_HTML
    assert "window.location.href = newAdminUrl" in STATIC_HTML
    assert "3 秒后自动重启" not in STATIC_HTML
    assert "不带 token" not in STATIC_HTML


def test_service_restart_icon_has_explicit_size_guard() -> None:
    assert "svc-restart-icon" in STATIC_HTML
    assert 'width="12" height="12"' in STATIC_HTML
    assert ".btn-svc-restart .svc-restart-icon" in STATIC_HTML
    assert "max-width: 12px" in STATIC_HTML
