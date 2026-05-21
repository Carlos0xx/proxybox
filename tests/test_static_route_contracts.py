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


def test_service_restart_button_is_text_only() -> None:
    assert "btn-svc-restart" in STATIC_HTML
    assert "svc-restart-icon" not in STATIC_HTML
    assert '<svg class="svc-restart-icon"' not in STATIC_HTML
    start = STATIC_HTML.index('<button class="btn btn-sm btn-warn btn-svc-restart"')
    button_fragment = STATIC_HTML[start : STATIC_HTML.index("</button>", start)]
    assert "<span" not in button_fragment
    assert "<svg" not in button_fragment
    assert "重启服务</button>" in STATIC_HTML
    assert '.btn-svc-restart [class*="icon"]' in STATIC_HTML
