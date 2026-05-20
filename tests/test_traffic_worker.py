"""Unit tests for the traffic worker's pure functions."""

from app.workers.traffic import _device_from_inbound_tag


def test_vless_prefix_returns_device_name():
    assert _device_from_inbound_tag("vless-laptop") == "laptop"
    assert _device_from_inbound_tag("vless-phone-1") == "phone-1"


def test_hy2_prefix_returns_device_name():
    assert _device_from_inbound_tag("hy2-phone") == "phone"
    assert _device_from_inbound_tag("hy2-home-router") == "home-router"


def test_template_tags_skipped():
    assert _device_from_inbound_tag("vless-template") is None
    assert _device_from_inbound_tag("hy2-template") is None


def test_non_device_tags_skipped():
    assert _device_from_inbound_tag("direct") is None
    assert _device_from_inbound_tag("") is None
    assert _device_from_inbound_tag("socks-inbound") is None
    assert _device_from_inbound_tag("vless") is None
    assert _device_from_inbound_tag("vless-") is None  # empty name after prefix
