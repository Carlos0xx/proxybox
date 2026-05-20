#!/usr/bin/env bash
# ProxyBox — turn on HTTPS via Caddy + Let's Encrypt.
#
# This is a separate post-install step on purpose: HTTPS needs a real
# domain name that resolves to the VPS, and that's the one piece the
# user has to supply. Once it's in place, Caddy fetches a Let's Encrypt
# cert automatically and renews on its own.
#
# Usage:
#     sudo bash deploy/enable-https.sh <domain>
#
# Example:
#     sudo bash deploy/enable-https.sh proxybox.example.com
#
# What it does (idempotent):
#   1. Validates <domain> resolves to this VPS's public IP
#   2. Opens ports 80 + 443 in firewalld/ufw if either is active
#   3. apt installs caddy from the Cloudsmith repo (Debian/Ubuntu)
#   4. Writes /etc/caddy/Caddyfile (reverse-proxy → localhost:8080)
#   5. Updates /etc/proxybox/config.yaml:
#        server.public_host  = <domain>
#        passkey.rp_id       = <domain>
#        passkey.origin      = https://<domain>
#   6. systemctl reload caddy → Let's Encrypt cert provisioned
#   7. systemctl restart proxybox-admin to pick up the new public_host
#
# Rollback / disable:
#   sudo systemctl stop caddy && sudo systemctl disable caddy
#   then revert public_host in /etc/proxybox/config.yaml + restart admin.

set -euo pipefail

# ─── i18n ─────────────────────────────────────────────────────────
LANG_CHOICE=""
for arg in "$@"; do
    case "$arg" in
        --lang=zh|--lang=en) LANG_CHOICE="${arg#--lang=}" ;;
    esac
done
if [ -z "$LANG_CHOICE" ]; then
    case "${LANG:-}" in zh*|ZH*) LANG_CHOICE=zh ;; *) LANG_CHOICE=en ;; esac
fi
if [ "$LANG_CHOICE" = "zh" ]; then
    M_USAGE="用法: sudo bash %s <domain> [--lang=zh|en]"
    M_NEED_ROOT="错误: 必须用 root 运行"
    M_NO_CONFIG="错误: 找不到 %s — 先跑 install.sh"
    M_DNS_CHECK="==> 验证 %s 解析到本机..."
    M_DNS_FAIL="❌ %s 解析为 %s, 但本机公网 IP 是 %s"
    M_DNS_FIX="    请在你的 DNS 提供商把 A 记录指向 %s 再重跑"
    M_DNS_OK="    ✓ DNS 指向本机"
    M_INSTALL_CADDY="==> 安装 Caddy..."
    M_CADDY_HAVE="==> Caddy 已存在, 跳过安装"
    M_FIREWALL="==> 打开 80 + 443 端口..."
    M_WRITE_CADDY="==> 写入 /etc/caddy/Caddyfile..."
    M_UPDATE_CONFIG="==> 更新 /etc/proxybox/config.yaml..."
    M_RELOAD="==> reload caddy + restart proxybox-admin..."
    M_DONE_HEADER="HTTPS 已启用"
    M_DONE_URL="    新登录地址: %s"
    M_DONE_NOTE="    (Let's Encrypt 首次签发可能需要 ~10 秒, 不通就稍等一下重试)"
else
    M_USAGE="usage: sudo bash %s <domain> [--lang=zh|en]"
    M_NEED_ROOT="ERROR: must run as root"
    M_NO_CONFIG="ERROR: %s not found — run install.sh first"
    M_DNS_CHECK="==> verifying %s resolves to this host..."
    M_DNS_FAIL="❌ %s resolves to %s, but this VPS's public IP is %s"
    M_DNS_FIX="    point an A record at %s in your DNS provider, then re-run"
    M_DNS_OK="    ✓ DNS points to this host"
    M_INSTALL_CADDY="==> installing Caddy..."
    M_CADDY_HAVE="==> Caddy already installed, skipping"
    M_FIREWALL="==> opening ports 80 + 443..."
    M_WRITE_CADDY="==> writing /etc/caddy/Caddyfile..."
    M_UPDATE_CONFIG="==> updating /etc/proxybox/config.yaml..."
    M_RELOAD="==> reloading caddy + restarting proxybox-admin..."
    M_DONE_HEADER="HTTPS enabled"
    M_DONE_URL="    new login URL: %s"
    M_DONE_NOTE="    (first Let's Encrypt issuance takes ~10s; retry if the page doesn't load yet)"
fi

# ─── colors (TTY-detected) ────────────────────────────────────────
if [ -t 1 ]; then
    C_RESET=$'\033[0m'
    C_GREEN_B=$'\033[1;32m'
    C_CYAN_B=$'\033[1;36m'
    C_RED_B=$'\033[1;31m'
    C_DIM=$'\033[2m'
else
    C_RESET=''
    C_GREEN_B=''
    C_CYAN_B=''
    C_RED_B=''
    C_DIM=''
fi

# ─── args + pre-flight ────────────────────────────────────────────
DOMAIN="${1:-}"
if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "-h" ] || [ "$DOMAIN" = "--help" ]; then
    printf "$M_USAGE\n" "$0"
    exit 1
fi
case "$DOMAIN" in
    *.*) ;;
    *) printf "$M_USAGE\n" "$0"; exit 1 ;;
esac

if [ "$(id -u)" != "0" ]; then
    printf "%s%s%s\n" "$C_RED_B" "$M_NEED_ROOT" "$C_RESET"
    exit 1
fi

CONFIG_DIR="${CONFIG_DIR:-/etc/proxybox}"
CONFIG="$CONFIG_DIR/config.yaml"
if [ ! -f "$CONFIG" ]; then
    printf "$M_NO_CONFIG\n" "$CONFIG"
    exit 1
fi

# ─── 1. DNS check ─────────────────────────────────────────────────
printf "%s" "$C_CYAN_B"; printf "$M_DNS_CHECK\n" "$DOMAIN"; printf "%s" "$C_RESET"
VPS_IP=$(curl -fsS --max-time 5 https://ifconfig.me 2>/dev/null \
        || curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null \
        || echo "")
DOMAIN_IP=$(getent hosts "$DOMAIN" 2>/dev/null | awk '{print $1; exit}')
if [ -z "$DOMAIN_IP" ]; then
    DOMAIN_IP=$(dig +short "$DOMAIN" A 2>/dev/null | head -1 || echo "")
fi
if [ -z "$DOMAIN_IP" ]; then
    printf "$M_DNS_FAIL\n" "$DOMAIN" "(no answer)" "$VPS_IP"
    printf "$M_DNS_FIX\n" "$VPS_IP"
    exit 1
fi
if [ -n "$VPS_IP" ] && [ "$DOMAIN_IP" != "$VPS_IP" ]; then
    printf "%s" "$C_RED_B"; printf "$M_DNS_FAIL\n" "$DOMAIN" "$DOMAIN_IP" "$VPS_IP"; printf "%s" "$C_RESET"
    printf "$M_DNS_FIX\n" "$VPS_IP"
    exit 1
fi
printf "$M_DNS_OK\n"

# ─── 2. install caddy ─────────────────────────────────────────────
if command -v caddy >/dev/null 2>&1; then
    echo "$M_CADDY_HAVE"
else
    echo "$M_INSTALL_CADDY"
    apt-get install -y -qq debian-keyring debian-archive-keyring apt-transport-https curl gpg >/dev/null
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/gpg.key \
        | gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
    curl -fsSL https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt \
        > /etc/apt/sources.list.d/caddy-stable.list
    apt-get update -qq
    apt-get install -y -qq caddy
fi

# ─── 3. firewall ──────────────────────────────────────────────────
echo "$M_FIREWALL"
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "^Status: active"; then
    ufw allow 80/tcp >/dev/null
    ufw allow 443/tcp >/dev/null
elif command -v firewall-cmd >/dev/null 2>&1 && systemctl is-active --quiet firewalld; then
    firewall-cmd --add-service=http  --permanent >/dev/null
    firewall-cmd --add-service=https --permanent >/dev/null
    firewall-cmd --reload >/dev/null
fi

# ─── 4. write Caddyfile ───────────────────────────────────────────
echo "$M_WRITE_CADDY"
cat > /etc/caddy/Caddyfile <<CADDY
# ProxyBox HTTPS — generated by deploy/enable-https.sh
$DOMAIN {
    encode gzip zstd

    # Proxy everything to ProxyBox's HTTP backend on localhost.
    reverse_proxy 127.0.0.1:8080 {
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-Host  {http.request.host}
    }
}
CADDY
caddy validate --config /etc/caddy/Caddyfile >/dev/null

# ─── 5. update ProxyBox config ────────────────────────────────────
echo "$M_UPDATE_CONFIG"
PROXYBOX_VENV="${PROXYBOX_VENV:-/opt/proxybox/.venv}"
"$PROXYBOX_VENV/bin/python" - <<PY
import pathlib, yaml
p = pathlib.Path("$CONFIG")
cfg = yaml.safe_load(p.read_text())
cfg.setdefault("server", {})["public_host"] = "$DOMAIN"
pk = cfg.setdefault("passkey", {})
pk["rp_id"]  = "$DOMAIN"
pk["origin"] = "https://$DOMAIN"
p.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
PY

# ─── 6. reload / restart ──────────────────────────────────────────
echo "$M_RELOAD"
systemctl enable --now caddy >/dev/null 2>&1 || true
systemctl reload caddy >/dev/null 2>&1 || systemctl restart caddy
sleep 1
systemctl restart proxybox-admin
systemctl restart proxybox-traffic-worker >/dev/null 2>&1 || true

# ─── done ─────────────────────────────────────────────────────────
HR="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
printf "%s%s%s\n" "$C_GREEN_B" "  $HR" "$C_RESET"
printf "  %s✅  %s%s\n" "$C_GREEN_B" "$M_DONE_HEADER" "$C_RESET"
printf "%s%s%s\n" "$C_GREEN_B" "  $HR" "$C_RESET"
echo ""
printf "$M_DONE_URL\n" "https://$DOMAIN/login"
printf "%s$M_DONE_NOTE%s\n" "$C_DIM" "$C_RESET"
echo ""
