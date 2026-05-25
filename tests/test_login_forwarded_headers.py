"""Forwarded-header handling for login security decisions."""

from __future__ import annotations

from starlette.requests import Request

from app.routers.login import _client_ip, _request_is_https


def _request(peer: str, headers: dict[str, str] | None = None, scheme: str = "http") -> Request:
    raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/login",
            "scheme": scheme,
            "headers": raw_headers,
            "client": (peer, 54321),
            "server": ("testserver", 80),
        }
    )


def test_client_ip_ignores_spoofed_xff_from_direct_peer() -> None:
    req = _request("198.51.100.10", {"X-Forwarded-For": "203.0.113.99"})

    assert _client_ip(req) == "198.51.100.10"


def test_client_ip_trusts_xff_from_loopback_proxy() -> None:
    req = _request("127.0.0.1", {"X-Forwarded-For": "203.0.113.99, 127.0.0.1"})

    assert _client_ip(req) == "203.0.113.99"


def test_client_ip_trusts_xff_from_ipv6_loopback_proxy() -> None:
    req = _request("::1", {"X-Forwarded-For": "2001:db8::42"})

    assert _client_ip(req) == "2001:db8::42"


def test_https_header_ignored_from_direct_peer() -> None:
    req = _request("198.51.100.10", {"X-Forwarded-Proto": "https"})

    assert not _request_is_https(req)


def test_https_header_trusted_from_loopback_proxy() -> None:
    req = _request("127.0.0.1", {"X-Forwarded-Proto": "https"})

    assert _request_is_https(req)


def test_https_detection_falls_back_to_request_scheme() -> None:
    req = _request("198.51.100.10", scheme="https")

    assert _request_is_https(req)
