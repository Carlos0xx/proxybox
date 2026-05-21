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
import contextlib
import os
from pathlib import Path
from typing import Any

import yaml
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from app.config import get_settings
from app.services import singbox

POLICY_PROXY = "PROXY"
POLICY_AUTO = "AUTO"
POLICY_AI = "AI"
POLICY_STREAMING = "Streaming"
POLICY_CHINA = "China"
POLICY_FINAL = "Final"
PROBE_URL = "https://www.gstatic.com/generate_204"
_BLOCKED_REFERENCE_RULE_KEYWORDS = ("binance", "bnbstatic", "bnbchain", "bsc-dataseed")

_APPLE_PUSH_PROXY_RULES = [
    "DOMAIN-SUFFIX,push.apple.com,{proxy}",
    "DOMAIN-SUFFIX,gateway.push.apple.com,{proxy}",
    "DOMAIN-SUFFIX,api.push.apple.com,{proxy}",
    "DOMAIN-SUFFIX,courier.push.apple.com,{proxy}",
    "DOMAIN,identity.apple.com,{proxy}",
    "DOMAIN-KEYWORD,apple.com.edgekey.net,{proxy}",
    "DOMAIN-KEYWORD,push-apple.com.akadns.net,{proxy}",
    "IP-CIDR,17.249.0.0/16,{proxy},no-resolve",
    "IP-CIDR,17.252.0.0/16,{proxy},no-resolve",
    "IP-CIDR,17.57.144.0/22,{proxy},no-resolve",
    "IP-CIDR,17.188.128.0/18,{proxy},no-resolve",
    "IP-CIDR,17.188.20.0/23,{proxy},no-resolve",
    "IP-CIDR6,2620:149:a44::/48,{proxy},no-resolve",
    "IP-CIDR6,2403:300:a42::/48,{proxy},no-resolve",
    "IP-CIDR6,2403:300:a51::/48,{proxy},no-resolve",
    "IP-CIDR6,2a01:b740:a42::/48,{proxy},no-resolve",
]

_DIRECT_RULES = [
    "DOMAIN-SUFFIX,smtp,DIRECT",
    "DOMAIN-KEYWORD,aria2,DIRECT",
    "DOMAIN-SUFFIX,acl4.ssr,DIRECT",
    "DOMAIN-SUFFIX,ip6-localhost,DIRECT",
    "DOMAIN-SUFFIX,ip6-loopback,DIRECT",
    "DOMAIN-SUFFIX,local,DIRECT",
    "DOMAIN-SUFFIX,localhost,DIRECT",
    "IP-CIDR,10.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,100.64.0.0/10,DIRECT,no-resolve",
    "IP-CIDR,127.0.0.0/8,DIRECT,no-resolve",
    "IP-CIDR,172.16.0.0/12,DIRECT,no-resolve",
    "IP-CIDR,192.168.0.0/16,DIRECT,no-resolve",
    "IP-CIDR,198.18.0.0/16,DIRECT,no-resolve",
    "IP-CIDR6,::1/128,DIRECT,no-resolve",
    "IP-CIDR6,fc00::/7,DIRECT,no-resolve",
    "IP-CIDR6,fe80::/10,DIRECT,no-resolve",
    "IP-CIDR6,fd00::/8,DIRECT,no-resolve",
    "DOMAIN,instant.arubanetworks.com,DIRECT",
    "DOMAIN,setmeup.arubanetworks.com,DIRECT",
    "DOMAIN,router.asus.com,DIRECT",
    "DOMAIN-SUFFIX,hiwifi.com,DIRECT",
    "DOMAIN-SUFFIX,leike.cc,DIRECT",
    "DOMAIN-SUFFIX,miwifi.com,DIRECT",
    "DOMAIN-SUFFIX,my.router,DIRECT",
    "DOMAIN-SUFFIX,p.to,DIRECT",
    "DOMAIN-SUFFIX,peiluyou.com,DIRECT",
    "DOMAIN-SUFFIX,phicomm.me,DIRECT",
    "DOMAIN-SUFFIX,router.ctc,DIRECT",
    "DOMAIN-SUFFIX,routerlogin.com,DIRECT",
    "DOMAIN-SUFFIX,tendawifi.com,DIRECT",
    "DOMAIN-SUFFIX,zte.home,DIRECT",
]

_REJECT_RULES = [
    "DOMAIN-KEYWORD,admarvel,REJECT",
    "DOMAIN-KEYWORD,admaster,REJECT",
    "DOMAIN-KEYWORD,adsage,REJECT",
    "DOMAIN-KEYWORD,adsensor,REJECT",
    "DOMAIN-KEYWORD,adservice,REJECT",
    "DOMAIN-KEYWORD,adsmogo,REJECT",
    "DOMAIN-KEYWORD,adsrvmedia,REJECT",
    "DOMAIN-KEYWORD,adsserving,REJECT",
    "DOMAIN-KEYWORD,adsystem,REJECT",
    "DOMAIN-KEYWORD,adwords,REJECT",
    "DOMAIN-KEYWORD,applovin,REJECT",
    "DOMAIN-KEYWORD,appsflyer,REJECT",
    "DOMAIN-KEYWORD,domob,REJECT",
    "DOMAIN-KEYWORD,duomeng,REJECT",
    "DOMAIN-KEYWORD,dwtrack,REJECT",
    "DOMAIN-KEYWORD,guanggao,REJECT",
    "DOMAIN-KEYWORD,omgmta,REJECT",
    "DOMAIN-KEYWORD,omniture,REJECT",
    "DOMAIN-KEYWORD,openx,REJECT",
    "DOMAIN-KEYWORD,partnerad,REJECT",
    "DOMAIN-KEYWORD,pingfore,REJECT",
    "DOMAIN-KEYWORD,socdm,REJECT",
    "DOMAIN-KEYWORD,supersonicads,REJECT",
    "DOMAIN-KEYWORD,wlmonitor,REJECT",
    "DOMAIN-SUFFIX,amazon-adsystem.com,REJECT",
    "DOMAIN-SUFFIX,appsflyer.com,REJECT",
    "DOMAIN-SUFFIX,doubleclick.net,REJECT",
]

_AI_SUFFIXES = [
    "openai.com",
    "chatgpt.com",
    "oaiusercontent.com",
    "anthropic.com",
    "claude.ai",
    "perplexity.ai",
    "gemini.google.com",
    "midjourney.com",
    "huggingface.co",
]

_STREAMING_SUFFIXES = [
    "youtube.com",
    "youtu.be",
    "googlevideo.com",
    "ytimg.com",
    "youtube-nocookie.com",
    "netflix.com",
    "nflxvideo.net",
    "nflximg.net",
    "nflxso.net",
    "tiktok.com",
    "tiktokcdn.com",
    "muscdn.com",
    "hulu.com",
    "twitch.tv",
    "ttvnw.net",
    "vimeo.com",
    "disneyplus.com",
    "hbomax.com",
    "primevideo.com",
]

_CHINA_DIRECT_RULES = [
    "DOMAIN-SUFFIX,cn,{china}",
    "DOMAIN-SUFFIX,中国,{china}",
    "DOMAIN-SUFFIX,公司,{china}",
    "DOMAIN-SUFFIX,网络,{china}",
    "DOMAIN-SUFFIX,qq.com,{china}",
    "DOMAIN-SUFFIX,wechat.com,{china}",
    "DOMAIN-SUFFIX,weixin.qq.com,{china}",
    "DOMAIN-SUFFIX,taobao.com,{china}",
    "DOMAIN-SUFFIX,tmall.com,{china}",
    "DOMAIN-SUFFIX,jd.com,{china}",
    "DOMAIN-SUFFIX,alicdn.com,{china}",
    "DOMAIN-SUFFIX,alipay.com,{china}",
    "DOMAIN-SUFFIX,baidu.com,{china}",
    "DOMAIN-SUFFIX,bilibili.com,{china}",
    "DOMAIN-SUFFIX,biliapi.net,{china}",
    "DOMAIN-SUFFIX,douyin.com,{china}",
    "DOMAIN-SUFFIX,amap.com,{china}",
    "DOMAIN-SUFFIX,163.com,{china}",
    "DOMAIN-SUFFIX,126.com,{china}",
    "DOMAIN-SUFFIX,mi.com,{china}",
    "DOMAIN-SUFFIX,xiaomi.com,{china}",
    "GEOIP,CN,{china}",
]


def _routing_rules(
    *,
    final_rule: str,
    proxy: str = POLICY_PROXY,
    ai: str = POLICY_AI,
    streaming: str = POLICY_STREAMING,
    china: str = POLICY_CHINA,
    final: str = POLICY_FINAL,
) -> list[str]:
    rules: list[str] = []
    rules.extend(_APPLE_PUSH_PROXY_RULES)
    rules.extend(_DIRECT_RULES)
    rules.extend(_REJECT_RULES)
    rules.extend(f"DOMAIN-SUFFIX,{suffix},{{ai}}" for suffix in _AI_SUFFIXES)
    rules.extend(f"DOMAIN-SUFFIX,{suffix},{{streaming}}" for suffix in _STREAMING_SUFFIXES)
    rules.extend(_CHINA_DIRECT_RULES)
    rules.append(final_rule)
    return [
        rule.format(
            proxy=proxy,
            ai=ai,
            streaming=streaming,
            china=china,
            final=final,
        )
        for rule in rules
        if not any(keyword in rule.lower() for keyword in _BLOCKED_REFERENCE_RULE_KEYWORDS)
    ]


def _clash_rules() -> list[str]:
    return _routing_rules(final_rule="MATCH,{final}")


def _shadowrocket_rules() -> list[str]:
    return _routing_rules(
        final_rule="FINAL,{final}",
        proxy=POLICY_PROXY,
        ai=POLICY_PROXY,
        streaming=POLICY_PROXY,
        china="DIRECT",
        final=POLICY_PROXY,
    )


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


def _reality_params(sb_cfg: dict[str, Any]) -> dict[str, Any]:
    """Pull the bits both Clash and Surge clients need from the sing-box config."""
    vless_tpl = singbox.find_template_inbound(sb_cfg, "vless")
    reality = vless_tpl["tls"]["reality"]
    tpl_users = vless_tpl.get("users") or []
    return {
        "sni": vless_tpl["tls"]["server_name"],
        "public_b64": derive_reality_public_key(reality["private_key"]),
        "short_id": reality["short_id"][0],
        "flow": (tpl_users[0].get("flow") if tpl_users else None) or "xtls-rprx-vision",
    }


def _hy2_obfs_password(sb_cfg: dict[str, Any]) -> str:
    return singbox.find_template_inbound(sb_cfg, "hysteria2").get("obfs", {}).get("password", "")


def _require_public_host() -> str:
    vps_host = get_settings().server.public_host
    if not vps_host:
        raise RuntimeError(
            "server.public_host is empty in config.yaml — set it before generating subs"
        )
    return vps_host


def build_clash_yaml(
    device: dict[str, Any],
    sb_cfg: dict[str, Any] | None = None,
    *,
    with_tun: bool = False,
) -> str:
    """Mihomo / Clash for iOS / Stash / Clash Verge YAML config.

    Built-in split rules are adapted from the operator reference template:
    local networks stay direct, ads are rejected, AI/streaming/CN traffic get
    separate policy groups, and Binance-specific rules are intentionally
    omitted. ``with_tun=True`` enables transparent routing for AsusWRT-Merlin.
    """
    if sb_cfg is None:
        sb_cfg = singbox.read_config()
    vps_host = _require_public_host()
    r = _reality_params(sb_cfg)
    name_v = f"ProxyBox-{device['name']}-vless"
    name_h = f"ProxyBox-{device['name']}-hy2"
    cfg: dict[str, Any] = {
        "mixed-port": 7890,
        "allow-lan": False,
        "mode": "rule",
        "log-level": "info",
        "proxies": [
            {
                "name": name_v,
                "type": "vless",
                "server": vps_host,
                "port": device["vless_port"],
                "uuid": device["vless_uuid"],
                "network": "tcp",
                "udp": True,
                "tls": True,
                "flow": r["flow"],
                "servername": r["sni"],
                "reality-opts": {"public-key": r["public_b64"], "short-id": r["short_id"]},
                "client-fingerprint": "chrome",
            },
            {
                "name": name_h,
                "type": "hysteria2",
                "server": vps_host,
                "port": device["hy2_port"],
                "password": device["hy2_password"],
                "sni": r["sni"],
                "obfs": "salamander",
                "obfs-password": _hy2_obfs_password(sb_cfg),
                "alpn": ["h3"],
                "skip-cert-verify": True,
            },
        ],
        "proxy-groups": [
            {
                "name": POLICY_PROXY,
                "type": "select",
                "proxies": [POLICY_AUTO, name_v, name_h, "DIRECT"],
            },
            {
                "name": POLICY_AUTO,
                "type": "url-test",
                "proxies": [name_v, name_h],
                "url": PROBE_URL,
                "interval": 300,
                "tolerance": 50,
                "lazy": False,
                "timeout": 5000,
            },
            {
                "name": POLICY_AI,
                "type": "select",
                "proxies": [POLICY_PROXY, name_v, name_h, "DIRECT"],
            },
            {
                "name": POLICY_STREAMING,
                "type": "select",
                "proxies": [POLICY_PROXY, POLICY_AUTO, name_v, name_h, "DIRECT"],
            },
            {
                "name": POLICY_CHINA,
                "type": "select",
                "proxies": ["DIRECT", POLICY_PROXY],
            },
            {
                "name": POLICY_FINAL,
                "type": "select",
                "proxies": [POLICY_PROXY, "DIRECT"],
            },
        ],
        "rules": _clash_rules(),
    }
    if with_tun:
        cfg["tun"] = {
            "enable": True,
            "stack": "system",
            "dns-hijack": ["any:53"],
            "auto-route": True,
            "auto-detect-interface": True,
        }
    return yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)


def build_shadowrocket_conf(device: dict[str, Any], sb_cfg: dict[str, Any] | None = None) -> str:
    """Shadowrocket rules-only .conf.

    Shadowrocket can import VLESS Reality / Hy2 reliably from URI subscriptions,
    and it can import Clash YAML profiles with nodes + rules. Its native .conf
    local-node syntax is less reliable for these newer protocols, so this file
    deliberately contains rules only and relies on an already selected node.
    """
    rules_text = "\n".join(_shadowrocket_rules())
    return f"""[General]
bypass-system = true
skip-proxy = 127.0.0.1, 192.168.0.0/16, 10.0.0.0/8, 172.16.0.0/12, localhost, *.local
dns-server = system

[Rule]
{rules_text}
"""


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
    tmp = path.with_suffix(path.suffix + ".tmp")
    # 0600 from creation — the file contains VLESS UUID + Hy2 password,
    # equivalent to raw credentials. Only proxybox-admin reads it.
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)
        path.chmod(0o600)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise
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
