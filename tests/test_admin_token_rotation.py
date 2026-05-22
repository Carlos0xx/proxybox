"""Regression tests for admin-token rotation."""

from __future__ import annotations

import asyncio
import stat
from pathlib import Path

import yaml

from app.config import reset_settings_cache
from app.routers import actions


def test_rotate_admin_token_preserves_config_mode_and_returns_ui_fields(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
admin:
  token: old-token-abcdef
  username: admin
  login_path: login-secret
server:
  public_host: 203.0.113.10
features:
  url_token_bypass: false
""".lstrip(),
        encoding="utf-8",
    )
    cfg_path.chmod(0o600)

    monkeypatch.setenv("PROXYBOX_CONFIG", str(cfg_path))
    monkeypatch.setattr(actions.secrets, "token_urlsafe", lambda _n: "new-token-xyz")

    try:
        result = asyncio.run(actions.rotate_admin_token())
    finally:
        reset_settings_cache()

    assert stat.S_IMODE(cfg_path.stat().st_mode) == 0o600
    saved = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    assert saved["admin"]["token"] == "new-token-xyz"
    assert saved["admin"]["username"] == "admin"
    assert result["new_token"] == "new-token-xyz"
    assert result["new_url_prefix"] == "/admin/new-token-xyz/"
    assert result["new_admin_url"] == "/admin/new-token-xyz/"
    assert result["old_token_short"] == "old-toke..."
    assert result["restart_scheduled_in_seconds"] == 0
