"""Subscription generation: URI builders + file IO.

A subscription is a plain-text file containing one URI per line that a
sing-box-compatible client (Shadowrocket, sing-box mobile, Hiddify, etc.)
can fetch via HTTP and decode into a node list. Files live at
``settings.paths.sub_dir / {sub_token}.txt`` — the sub_token IS the
authentication, so leaking it leaks the device. Rotate with
``POST /api/devices/{name}/regen-subs``.
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from app.config import get_settings
from app.services import singbox


def derive_reality_public_key(private_b64: str) -> str:
    """Derive Reality X25519 public key (base64url, no padding) from private."""
    priv_bytes = base64.urlsafe_b64decode(private_b64 + "==")
    priv = X25519PrivateKey.from_private_bytes(priv_bytes)
    pub_bytes = priv.public_key().public_bytes_raw()
    return base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()


def build_vless_uri(device: dict[str, Any], sb_cfg: dict[str, Any], vps_host: str) -> str:
    vless_tpl = singbox.find_template_inbound(sb_cfg, "vless")
    reality = vless_tpl["tls"]["reality"]
    sni = vless_tpl["tls"]["server_name"]
    public_b64 = derive_reality_public_key(reality["private_key"])
    short_id = reality["short_id"][0]
    tpl_users = vless_tpl.get("users") or []
    flow = (tpl_users[0].get("flow") if tpl_users else None) or "xtls-rprx-vision"

    return (
        f"vless://{device['vless_uuid']}@{vps_host}:{device['vless_port']}"
        f"?security=reality&sni={sni}&fp=chrome&pbk={public_b64}&sid={short_id}"
        f"&type=tcp&flow={flow}"
        f"#ProxyBox-{device['name']}-vless"
    )


def build_hysteria2_uri(device: dict[str, Any], sb_cfg: dict[str, Any], vps_host: str) -> str:
    hy2_tpl = singbox.find_template_inbound(sb_cfg, "hysteria2")
    obfs_pw = hy2_tpl.get("obfs", {}).get("password", "")
    sni = (
        hy2_tpl.get("tls", {}).get("server_name")
        or singbox.find_template_inbound(sb_cfg, "vless")["tls"]["server_name"]
    )

    return (
        f"hysteria2://{device['hy2_password']}@{vps_host}:{device['hy2_port']}"
        f"?sni={sni}&obfs=salamander&obfs-password={obfs_pw}&insecure=1"
        f"#ProxyBox-{device['name']}-hy2"
    )


def generate_subscription_text(device: dict[str, Any], sb_cfg: dict[str, Any] | None = None) -> str:
    """Build the subscription file content for one device.

    Raises RuntimeError if server.public_host is not configured — the URIs
    need a host clients can connect to.
    """
    if sb_cfg is None:
        sb_cfg = singbox.read_config()
    vps_host = get_settings().server.public_host
    if not vps_host:
        raise RuntimeError(
            "server.public_host is empty in config.yaml — set it before generating subs"
        )
    return (
        build_vless_uri(device, sb_cfg, vps_host)
        + "\n"
        + build_hysteria2_uri(device, sb_cfg, vps_host)
        + "\n"
    )


def _sub_path(sub_token: str) -> Path:
    return Path(get_settings().paths.sub_dir) / f"{sub_token}.txt"


def write_subscription_file(device: dict[str, Any], sb_cfg: dict[str, Any] | None = None) -> Path:
    sub_dir = Path(get_settings().paths.sub_dir)
    sub_dir.mkdir(parents=True, exist_ok=True)
    content = generate_subscription_text(device, sb_cfg)
    path = _sub_path(device["sub_token"])
    path.write_text(content)
    path.chmod(0o644)
    return path


def read_subscription(sub_token: str) -> str | None:
    path = _sub_path(sub_token)
    if not path.exists():
        return None
    return path.read_text()


def delete_subscription_file(sub_token: str) -> bool:
    path = _sub_path(sub_token)
    if path.exists():
        path.unlink()
        return True
    return False
