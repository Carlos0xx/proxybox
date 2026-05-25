"""Tests for the Reality cover-domain (SNI) selection logic.

The pool itself is validated out-of-band (every entry negotiates TLS1.3 +
h2); these tests cover the selection / override behaviour, which is what
can regress in code.
"""

from __future__ import annotations

import pytest

from app import bootstrap


def test_pool_is_nonempty_and_well_formed() -> None:
    assert bootstrap.SNI_CANDIDATES, "pool must not be empty"
    for d in bootstrap.SNI_CANDIDATES:
        assert "." in d, f"{d!r} doesn't look like a domain"
        assert " " not in d
        assert not d.startswith("http"), f"{d!r} should be a bare host, no scheme"


def test_pool_excludes_canonical_reality_defaults() -> None:
    # The whole point of the change: stop shipping the four oldest Reality
    # example domains, which are themselves a fingerprint.
    canonical = {"www.apple.com", "www.microsoft.com", "www.cloudflare.com", "www.amazon.com"}
    assert canonical.isdisjoint(set(bootstrap.SNI_CANDIDATES))


def test_pick_sni_honours_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROXYBOX_SNI", "cover.example.org")
    assert bootstrap._pick_sni() == "cover.example.org"


def test_pick_sni_strips_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROXYBOX_SNI", "  cover.example.org  ")
    assert bootstrap._pick_sni() == "cover.example.org"


def test_pick_sni_random_from_pool_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PROXYBOX_SNI", raising=False)
    for _ in range(20):
        assert bootstrap._pick_sni() in bootstrap.SNI_CANDIDATES


def test_read_singbox_sni_round_trips(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bootstrap, "_reality_keypair", lambda: ("priv", "pub"))
    monkeypatch.setattr(bootstrap, "_hy2_self_signed_cert", lambda _out, _cn: None)
    sb_dir = tmp_path / "sing-box"
    sb_dir.mkdir()
    bootstrap._gen_singbox_config(sb_dir, sni="cover.example.net")
    assert bootstrap._read_singbox_sni(sb_dir) == "cover.example.net"


def test_read_singbox_sni_missing_file_returns_empty(tmp_path) -> None:
    assert bootstrap._read_singbox_sni(tmp_path) == ""


def test_docker_port_base_is_randomised_not_fixed() -> None:
    # The whole point: Docker installs must not all share 11000/21000.
    assert bootstrap._DEFAULT_VLESS_BASE != 11000
    assert bootstrap._DEFAULT_HY2_BASE != 21000
    # Within the documented non-overlapping windows.
    assert 10000 <= bootstrap._DEFAULT_VLESS_BASE <= 28999
    assert 31000 <= bootstrap._DEFAULT_HY2_BASE <= 54999


def test_docker_ports_ranges_track_the_base(monkeypatch: pytest.MonkeyPatch) -> None:
    # No env → ranges are base+1..base+50, and stable across calls.
    for var in (
        "PROXYBOX_VLESS_TEMPLATE_PORT",
        "PROXYBOX_HY2_TEMPLATE_PORT",
        "PROXYBOX_VLESS_START",
        "PROXYBOX_VLESS_END",
        "PROXYBOX_HY2_START",
        "PROXYBOX_HY2_END",
    ):
        monkeypatch.delenv(var, raising=False)
    p = bootstrap._docker_ports()
    assert p["vless_range"] == (p["vless_template"] + 1, p["vless_template"] + 50)
    assert p["hy2_range"] == (p["hy2_template"] + 1, p["hy2_template"] + 50)
    assert bootstrap._docker_ports() == p  # stable across calls
