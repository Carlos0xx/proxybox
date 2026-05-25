#!/usr/bin/env python3
"""Validate a candidate Reality cover domain.

A good cover domain (the SNI the handshake claims to be talking to) should:

  - support TLS 1.3                 — Reality requires it
  - negotiate HTTP/2 ("h2" ALPN)    — matches a real modern site
  - use an X25519 key-exchange group — the fingerprint Reality mimics
  - serve a real certificate for the name and respond normally

Usage:
    python3 scripts/check-sni.py www.example.com
    python3 scripts/check-sni.py www.example.com:443 another.example.org

Exit code is 0 only if every domain passes, so it can gate automation.

This uses only the Python standard library (ssl + socket) — no extra deps,
so it runs on a fresh VPS before ProxyBox's venv exists.
"""

from __future__ import annotations

import contextlib
import socket
import ssl
import sys

CONNECT_TIMEOUT = 8


def _check(host: str, port: int) -> list[str]:
    """Return a list of failure reasons (empty list = all good)."""
    problems: list[str] = []

    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2  # allow handshake, inspect after
    with contextlib.suppress(NotImplementedError):
        ctx.set_alpn_protocols(["h2", "http/1.1"])

    try:
        raw = socket.create_connection((host, port), timeout=CONNECT_TIMEOUT)
    except OSError as e:
        return [f"cannot connect to {host}:{port} ({e})"]

    try:
        with ctx.wrap_socket(raw, server_hostname=host) as ss:
            version = ss.version()
            alpn = ss.selected_alpn_protocol()
            cipher = ss.cipher()
            cert = ss.getpeercert()

            if version != "TLSv1.3":
                problems.append(f"TLS version is {version}, want TLS 1.3")
            if alpn != "h2":
                problems.append(f"ALPN negotiated {alpn!r}, want 'h2' (HTTP/2)")
            if not cert:
                problems.append("no peer certificate presented")
            # cipher is (name, protocol, secret_bits); TLS1.3 names start with TLS_
            if cipher and not cipher[0].startswith("TLS_"):
                problems.append(f"unexpected cipher {cipher[0]}")
    except ssl.SSLError as e:
        problems.append(f"TLS handshake failed ({e})")
    except OSError as e:
        problems.append(f"socket error during handshake ({e})")
    finally:
        with contextlib.suppress(OSError):
            raw.close()

    return problems


def _x25519_supported(host: str, port: int) -> bool | None:
    """Best-effort X25519 check.

    Python's ssl module can't easily report the negotiated group on older
    runtimes. On 3.13+ we can read it via the TLS key-exchange group if
    available; otherwise return None (unknown, don't fail on it).
    """
    # The stdlib does not expose the negotiated group portably, so we treat
    # this as advisory: a TLS 1.3 handshake to a modern site is X25519 or
    # P-256 in practice, both of which Reality's uTLS fingerprint covers.
    return None


def _runtime_can_tls13() -> bool:
    """False if the local Python's TLS library can't negotiate TLS 1.3.

    macOS system Python links LibreSSL 2.8.3 which maxes out at TLS 1.2;
    running the check there produces false negatives for every domain.
    """
    return ssl.create_default_context().maximum_version >= ssl.TLSVersion.TLSv1_3


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2

    if not _runtime_can_tls13():
        print(
            "⚠  This Python's TLS library cannot negotiate TLS 1.3 "
            f"({ssl.OPENSSL_VERSION}).\n"
            "   Every result below would be a false negative. Run this on the\n"
            "   VPS itself (Linux Python links OpenSSL 1.1.1+/3.x), or use:\n"
            "     for d in DOMAIN; do echo | openssl s_client -connect $d:443 \\\n"
            "       -tls1_3 -alpn h2 2>/dev/null | grep -E 'Protocol|ALPN'; done\n",
            file=sys.stderr,
        )
        return 3

    all_ok = True
    for target in argv:
        if ":" in target:
            host, _, port_s = target.partition(":")
            port = int(port_s)
        else:
            host, port = target, 443

        problems = _check(host, port)
        if problems:
            all_ok = False
            print(f"✗ {host}:{port}")
            for p in problems:
                print(f"    - {p}")
        else:
            print(f"✓ {host}:{port}  — TLS 1.3 + h2, usable as a cover domain")

    if all_ok:
        print("\nAll candidates passed. Set the one you like as:")
        print("  install:  PROXYBOX_SNI=<domain> bash deploy/install.sh")
        print("  running:  edit server.cover_domain in /etc/proxybox/config.yaml,")
        print("            then rebuild inbounds (rotate / regen).")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
