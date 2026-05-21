"""Unit tests for subscription URI builders (pure functions, no DB / no FS)."""

import base64
from types import SimpleNamespace

import yaml
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from app.services import subscriptions
from app.services.subscriptions import (
    build_clash_yaml,
    build_hysteria2_uri,
    build_shadowrocket_conf,
    build_vless_uri,
    derive_reality_public_key,
)


def _gen_keypair() -> tuple[str, str]:
    priv = X25519PrivateKey.generate()
    priv_b = priv.private_bytes_raw()
    pub_b = priv.public_key().public_bytes_raw()
    return (
        base64.urlsafe_b64encode(priv_b).rstrip(b"=").decode(),
        base64.urlsafe_b64encode(pub_b).rstrip(b"=").decode(),
    )


def test_derive_reality_public_key_matches_keypair():
    priv_b64, expected_pub_b64 = _gen_keypair()
    assert derive_reality_public_key(priv_b64) == expected_pub_b64


def test_derive_is_deterministic():
    priv_b64, _ = _gen_keypair()
    a = derive_reality_public_key(priv_b64)
    b = derive_reality_public_key(priv_b64)
    assert a == b


def _fake_sb_cfg(priv_b64: str) -> dict:
    return {
        "inbounds": [
            {
                "type": "vless",
                "tag": "vless-template",
                "users": [{"flow": "xtls-rprx-vision"}],
                "tls": {
                    "server_name": "www.example.com",
                    "reality": {
                        "private_key": priv_b64,
                        "short_id": ["abc123def4567890"],
                    },
                },
            },
            {
                "type": "hysteria2",
                "tag": "hy2-template",
                "obfs": {"password": "obfs-pw-hex"},  # pragma: allowlist secret
                "tls": {"server_name": "www.example.com"},
            },
        ]
    }


def _fake_device() -> dict:
    return {
        "name": "test-phone",
        "vless_uuid": "00000000-0000-0000-0000-000000000001",
        "vless_port": 11001,
        "hy2_password": "fake-hy2-pw",  # pragma: allowlist secret
        "hy2_port": 21001,
    }


def _stub_public_host(monkeypatch, host: str = "1.2.3.4") -> None:
    settings = SimpleNamespace(server=SimpleNamespace(public_host=host))
    monkeypatch.setattr(subscriptions, "get_settings", lambda: settings)


def test_build_vless_uri_shape():
    priv_b64, pub_b64 = _gen_keypair()
    device = _fake_device()
    uri = build_vless_uri(device, _fake_sb_cfg(priv_b64), "1.2.3.4")
    assert uri.startswith("vless://00000000-0000-0000-0000-000000000001@1.2.3.4:11001?")
    assert "security=reality" in uri
    assert "sni=www.example.com" in uri
    assert f"pbk={pub_b64}" in uri
    assert "sid=abc123def4567890" in uri
    assert "flow=xtls-rprx-vision" in uri
    assert uri.endswith("#ProxyBox-test-phone-vless")


def test_build_hysteria2_uri_shape():
    priv_b64, _ = _gen_keypair()
    device = _fake_device()
    uri = build_hysteria2_uri(device, _fake_sb_cfg(priv_b64), "1.2.3.4")
    assert uri.startswith("hysteria2://fake-hy2-pw@1.2.3.4:21001?")
    assert "sni=www.example.com" in uri
    assert "obfs=salamander" in uri
    assert "obfs-password=obfs-pw-hex" in uri
    assert "insecure=1" in uri
    assert uri.endswith("#ProxyBox-test-phone-hy2")


def test_clash_yaml_uses_split_rules_without_binance(monkeypatch):
    _stub_public_host(monkeypatch)
    priv_b64, _ = _gen_keypair()

    text = build_clash_yaml(_fake_device(), _fake_sb_cfg(priv_b64))
    cfg = yaml.safe_load(text)

    group_names = {group["name"] for group in cfg["proxy-groups"]}
    assert group_names >= {"PROXY", "AUTO", "AI", "Streaming", "China", "Final"}
    hy2_proxy = next(proxy for proxy in cfg["proxies"] if proxy["type"] == "hysteria2")
    auto_group = next(group for group in cfg["proxy-groups"] if group["name"] == "AUTO")
    assert hy2_proxy["alpn"] == ["h3"]
    assert auto_group["url"] == "https://www.gstatic.com/generate_204"
    assert auto_group["lazy"] is False
    assert auto_group["tolerance"] == 50
    assert auto_group["timeout"] == 5000
    assert "DOMAIN-SUFFIX,push.apple.com,PROXY" in cfg["rules"]
    assert "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve" in cfg["rules"]
    assert "DOMAIN-SUFFIX,openai.com,AI" in cfg["rules"]
    assert "DOMAIN-SUFFIX,netflix.com,Streaming" in cfg["rules"]
    assert "DOMAIN-SUFFIX,qq.com,China" in cfg["rules"]
    assert "GEOIP,CN,China" in cfg["rules"]
    assert cfg["rules"][-1] == "MATCH,Final"
    assert "binance" not in text.lower()
    assert "bnbstatic" not in text.lower()
    assert "bsc-dataseed" not in text.lower()
    assert "Binance-SG" not in text


def test_merlin_yaml_keeps_tun_and_split_rules(monkeypatch):
    _stub_public_host(monkeypatch)
    priv_b64, _ = _gen_keypair()

    text = build_clash_yaml(_fake_device(), _fake_sb_cfg(priv_b64), with_tun=True)
    cfg = yaml.safe_load(text)

    assert cfg["tun"]["enable"] is True
    assert cfg["rules"][-1] == "MATCH,Final"
    assert "DOMAIN-SUFFIX,openai.com,AI" in cfg["rules"]
    assert "binance" not in text.lower()
    assert "bnbstatic" not in text.lower()
    assert "bsc-dataseed" not in text.lower()


def test_shadowrocket_conf_is_rules_only_without_binance(monkeypatch):
    _stub_public_host(monkeypatch)
    priv_b64, _ = _gen_keypair()

    text = build_shadowrocket_conf(_fake_device(), _fake_sb_cfg(priv_b64))

    assert "[Proxy]" not in text
    assert "[Proxy Group]" not in text
    assert "vless," not in text
    assert "hysteria2," not in text
    assert "[Rule]" in text
    assert "DOMAIN-SUFFIX,push.apple.com,PROXY" in text
    assert "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve" in text
    assert "DOMAIN-SUFFIX,openai.com,PROXY" in text
    assert "DOMAIN-SUFFIX,netflix.com,PROXY" in text
    assert "DOMAIN-SUFFIX,qq.com,DIRECT" in text
    assert "GEOIP,CN,DIRECT" in text
    assert "FINAL,PROXY" in text
    assert ",AI" not in text
    assert ",Streaming" not in text
    assert ",Final" not in text
    assert "binance" not in text.lower()
    assert "bnbstatic" not in text.lower()
    assert "bsc-dataseed" not in text.lower()
    assert "Binance-SG" not in text
