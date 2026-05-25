"""Tests for app.services.admin_password.

The password file is the single source of truth for the admin password
post-v0.2.1. Atomic write semantics + 0400 perms are load-bearing.
"""

from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from app.services import admin_password


def test_write_creates_file_with_mode_0400(tmp_path: Path) -> None:
    target = tmp_path / "admin.password"
    admin_password.write(target, "swordfish-rosebud-42")
    st = target.stat()
    # owner-read-only — no group / other access, no write even for owner.
    assert stat.S_IMODE(st.st_mode) == 0o400, f"expected 0400, got {oct(stat.S_IMODE(st.st_mode))}"


def test_read_round_trips_value(tmp_path: Path) -> None:
    target = tmp_path / "admin.password"
    admin_password.write(target, "abc123XYZ")
    assert admin_password.read(target) == "abc123XYZ"


def test_write_strips_trailing_whitespace(tmp_path: Path) -> None:
    target = tmp_path / "admin.password"
    admin_password.write(target, "  pad\n\n")
    assert admin_password.read(target) == "pad"


def test_read_missing_file_returns_empty(tmp_path: Path) -> None:
    assert admin_password.read(tmp_path / "nope.password") == ""


def test_write_creates_parent_dir(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "nested" / "admin.password"
    admin_password.write(target, "alpha")
    assert target.exists()
    assert admin_password.read(target) == "alpha"


def test_write_atomic_via_replace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Should not leave a partial file at the target path on crash."""
    target = tmp_path / "admin.password"
    admin_password.write(target, "initial-pw")

    # Simulate a crash partway through the second write — patch os.replace
    # to raise before it can swap in the new contents.
    def fake_replace(*_args: object) -> None:
        raise OSError("simulated rename failure")

    monkeypatch.setattr(os, "replace", fake_replace)
    with pytest.raises(OSError, match="simulated rename failure"):
        admin_password.write(target, "second-pw")

    # The original value should still be readable. The tmp sibling may or
    # may not exist — both states are acceptable, just not "target is the
    # new partial content".
    monkeypatch.undo()
    assert admin_password.read(target) == "initial-pw"
