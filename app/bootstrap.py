"""First-boot config generator for ProxyBox.

Idempotent. Runs once via the `bootstrap` docker-compose service before the
admin / worker / sing-box containers start. Generates two files if missing:

- /etc/sing-box/config.json   template inbounds, Reality keypair (X25519 via
                              cryptography lib — no sing-box binary needed),
                              Hy2 self-signed cert via openssl shell-out
- /etc/proxybox/config.yaml   admin token + auto-detected public_host

For non-Docker installs, prefer ``deploy/install.sh`` which does the same
plus apt packaging, systemd units, fail2ban jail, etc.
"""

from __future__ import annotations

import base64
import json
import secrets
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

SNI_CANDIDATES = (
    "www.microsoft.com",
    "www.apple.com",
    "www.cloudflare.com",
    "www.amazon.com",
)


def _reality_keypair() -> tuple[str, str]:
    """Return (private_key_b64url, public_key_b64url) sing-box compatible."""
    priv = X25519PrivateKey.generate()
    priv_b = priv.private_bytes_raw()
    pub_b = priv.public_key().public_bytes_raw()
    return (
        base64.urlsafe_b64encode(priv_b).rstrip(b"=").decode(),
        base64.urlsafe_b64encode(pub_b).rstrip(b"=").decode(),
    )


def _hy2_self_signed_cert(out_dir: Path, cn: str) -> None:
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "3650",
            "-keyout",
            str(out_dir / "key.pem"),
            "-out",
            str(out_dir / "cert.pem"),
            "-subj",
            f"/CN={cn}",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    (out_dir / "key.pem").chmod(0o600)


def _detect_public_host() -> str:
    for url in ("https://ifconfig.me", "https://api.ipify.org"):
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.read().decode().strip()
        except (urllib.error.URLError, OSError):
            continue
    return ""


def _gen_singbox_config(sb_dir: Path) -> None:
    priv_key, _ = _reality_keypair()
    sni = secrets.choice(SNI_CANDIDATES)
    short_id = secrets.token_hex(8)
    hy2_obfs = secrets.token_hex(16)

    _hy2_self_signed_cert(sb_dir, sni)

    cfg = {
        "log": {"level": "info", "timestamp": True},
        "experimental": {"clash_api": {"external_controller": "127.0.0.1:9090"}},
        "inbounds": [
            {
                "type": "vless",
                "tag": "vless-template",
                "listen": "::",
                "listen_port": 11000,
                "users": [],
                "tls": {
                    "enabled": True,
                    "server_name": sni,
                    "reality": {
                        "enabled": True,
                        "handshake": {"server": sni, "server_port": 443},
                        "private_key": priv_key,
                        "short_id": [short_id],
                    },
                },
            },
            {
                "type": "hysteria2",
                "tag": "hy2-template",
                "listen": "::",
                "listen_port": 21000,
                "users": [],
                "obfs": {"type": "salamander", "password": hy2_obfs},
                "tls": {
                    "enabled": True,
                    "alpn": ["h3"],
                    "certificate_path": str(sb_dir / "cert.pem"),
                    "key_path": str(sb_dir / "key.pem"),
                },
                "masquerade": f"https://{sni}",
            },
        ],
        "outbounds": [{"type": "direct", "tag": "direct"}],
    }
    out = sb_dir / "config.json"
    out.write_text(json.dumps(cfg, indent=2))
    out.chmod(0o600)


def _gen_proxybox_config(pb_dir: Path) -> str:
    admin_token = secrets.token_urlsafe(24)
    public_host = _detect_public_host()
    yaml_text = f"""admin:
  token: "{admin_token}"
  host: "0.0.0.0"
  port: 8080
server:
  public_host: "{public_host}"
paths:
  traffic_db: /var/lib/proxybox/traffic.db
  static_dir: /opt/proxybox/static
  sub_dir: /var/www/proxybox-sub
  singbox_config: /etc/sing-box/config.json
  session_secret: /etc/proxybox/session-secret
services:
  monitored:
    - sing-box
    - proxybox-admin
    - proxybox-traffic-worker
ports:
  vless_range: [11001, 11050]
  hy2_range: [21001, 21050]
clash:
  api_url: "http://127.0.0.1:9090"
  api_secret: ""
worker:
  poll_interval: 10
  retention_days: 7
passkey:
  rp_id: ""
  rp_name: "ProxyBox"
  origin: ""
features:
  passkey: false
  bot: false
"""
    out = pb_dir / "config.yaml"
    out.write_text(yaml_text)
    out.chmod(0o600)
    return admin_token


def main() -> int:
    sb_dir = Path("/etc/sing-box")
    pb_dir = Path("/etc/proxybox")
    sb_dir.mkdir(parents=True, exist_ok=True)
    pb_dir.mkdir(parents=True, exist_ok=True)

    if not (sb_dir / "config.json").exists():
        _gen_singbox_config(sb_dir)
        print("[bootstrap] sing-box config generated", flush=True)
    else:
        print("[bootstrap] sing-box config exists, skip", flush=True)

    if not (pb_dir / "config.yaml").exists():
        token = _gen_proxybox_config(pb_dir)
        print(
            f"[bootstrap] ProxyBox config generated; admin token first 8 chars: "
            f"{token[:8]}... (full value in /etc/proxybox/config.yaml)",
            flush=True,
        )
    else:
        print("[bootstrap] ProxyBox config exists, skip", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
