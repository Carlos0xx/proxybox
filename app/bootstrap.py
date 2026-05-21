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
import contextlib
import json
import os
import secrets
import shutil
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


def _truthy(value: str | None) -> bool:
    return (value or "").lower() in {"1", "true", "yes", "on"}


def _empty_dir(path: Path) -> None:
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink(missing_ok=True)


def _write_private_text(path: Path, text: str, mode: int = 0o600) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, path)
        path.chmod(mode)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise


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


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw in (None, ""):
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if not (1 <= value <= 65535):
        raise ValueError(f"{name} must be between 1 and 65535")
    return value


def _env_range(prefix: str, default_start: int, default_end: int) -> tuple[int, int]:
    start = _env_int(f"{prefix}_START", default_start)
    end = _env_int(f"{prefix}_END", default_end)
    if start > end:
        raise ValueError(f"{prefix}_START must be <= {prefix}_END")
    return start, end


def _docker_ports() -> dict[str, int | tuple[int, int]]:
    return {
        "admin": _env_int("PROXYBOX_ADMIN_PORT", 8080),
        "clash": _env_int("PROXYBOX_CLASH_PORT", 9090),
        "vless_template": _env_int("PROXYBOX_VLESS_TEMPLATE_PORT", 11000),
        "hy2_template": _env_int("PROXYBOX_HY2_TEMPLATE_PORT", 21000),
        "vless_range": _env_range("PROXYBOX_VLESS", 11001, 11050),
        "hy2_range": _env_range("PROXYBOX_HY2", 21001, 21050),
    }


def _gen_singbox_config(sb_dir: Path) -> None:
    ports = _docker_ports()
    priv_key, _ = _reality_keypair()
    sni = secrets.choice(SNI_CANDIDATES)
    short_id = secrets.token_hex(8)
    hy2_obfs = secrets.token_hex(16)

    _hy2_self_signed_cert(sb_dir, sni)

    cfg = {
        "log": {"level": "info", "timestamp": True},
        "experimental": {
            "clash_api": {"external_controller": f"0.0.0.0:{ports['clash']}"}
        },
        "inbounds": [
            {
                "type": "vless",
                "tag": "vless-template",
                "listen": "::",
                "listen_port": ports["vless_template"],
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
                "listen_port": ports["hy2_template"],
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
    _write_private_text(out, json.dumps(cfg, indent=2))


def _gen_admin_password() -> str:
    """16-char alphanumeric password — matches install.sh."""
    import string

    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(16))


def _gen_login_path() -> str:
    """12-char alphanumeric suffix on /login — matches install.sh."""
    import string

    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(12))


def _gen_proxybox_config(pb_dir: Path) -> dict[str, str]:
    """Returns the generated admin credentials so the caller can echo them.

    The password is **not** written into config.yaml — it goes to a
    sibling file ``/etc/proxybox/admin.password`` (mode 0400) so a
    casual ``cat config.yaml`` (screenshot, backup, paste-in-chat) can't
    leak the credential. See ``app.services.admin_password``.
    """
    admin_token = secrets.token_urlsafe(24)
    admin_password = _gen_admin_password()
    admin_login_path = _gen_login_path()
    ports = _docker_ports()
    vless_range = ports["vless_range"]
    hy2_range = ports["hy2_range"]
    public_host = os.environ.get("PROXYBOX_PUBLIC_HOST") or _detect_public_host()
    yaml_text = f"""admin:
  token: "{admin_token}"
  username: "admin"
  login_path: "{admin_login_path}"
  host: "0.0.0.0"
  port: {ports["admin"]}
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
  vless_range: [{vless_range[0]}, {vless_range[1]}]
  hy2_range: [{hy2_range[0]}, {hy2_range[1]}]
clash:
  api_url: "http://sing-box:{ports["clash"]}"
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
    _write_private_text(out, yaml_text)

    # Write the password to its sibling file (mode 0400). Lazy import to
    # avoid a circular dep between config.py (PathsSettings) and the
    # bootstrap module on fresh installs where config doesn't exist yet.
    from app.services import admin_password as _ap

    _ap.write(pb_dir / "admin.password", admin_password)

    return {
        "token": admin_token,
        "password": admin_password,
        "login_path": admin_login_path,
        "public_host": public_host,
        "admin_port": str(ports["admin"]),
    }


def main() -> int:
    sb_dir = Path("/etc/sing-box")
    pb_dir = Path("/etc/proxybox")
    data_dir = Path("/var/lib/proxybox")
    sub_dir = Path("/var/www/proxybox-sub")

    if _truthy(os.environ.get("PROXYBOX_FRESH")):
        for path in (sb_dir, pb_dir, data_dir, sub_dir):
            _empty_dir(path)
        print("[bootstrap] fresh mode: cleared ProxyBox volumes", flush=True)

    for path in (sb_dir, pb_dir, data_dir, sub_dir):
        path.mkdir(parents=True, exist_ok=True)
    sb_dir.chmod(0o700)
    pb_dir.chmod(0o700)

    if not (sb_dir / "config.json").exists():
        _gen_singbox_config(sb_dir)
        print("[bootstrap] sing-box config generated", flush=True)
    else:
        print("[bootstrap] sing-box config exists, skip", flush=True)

    if not (pb_dir / "config.yaml").exists():
        creds = _gen_proxybox_config(pb_dir)
        host = creds["public_host"] or "<your-vps-ip>"
        print(
            "\n"
            "================================================================\n"
            " ProxyBox · Docker bootstrap — admin credentials (saved once)\n"
            "================================================================\n"
            f"  Login URL    http://{host}:{creds['admin_port']}/login/{creds['login_path']}\n"
            "  Username     admin\n"
            f"  Password     {creds['password']}\n"
            "----------------------------------------------------------------\n"
            "  Copy these into a password manager BEFORE this container exits.\n"
            "  Recovery:\n"
            "    cat /etc/proxybox/admin.password    (password, mode 0400)\n"
            "    grep -E 'token|login_path' /etc/proxybox/config.yaml\n"
            "================================================================\n",
            flush=True,
        )
    else:
        print("[bootstrap] ProxyBox config exists, skip", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
