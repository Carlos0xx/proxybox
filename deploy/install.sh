#!/usr/bin/env bash
# ProxyBox installer — sets up a fresh Debian/Ubuntu VPS.
#
# Usage:
#   git clone https://github.com/carlos0xx/proxybox /opt/proxybox
#   cd /opt/proxybox && bash deploy/install.sh                       # auto language
#   cd /opt/proxybox && bash deploy/install.sh --lang en             # force English
#   cd /opt/proxybox && bash deploy/install.sh --lang zh             # force Chinese
#
# Idempotent: re-running it on an existing install does nothing destructive,
# only fills in missing pieces. Safe to run repeatedly.

set -euo pipefail

# ─── argv: --lang en|zh + pass-through to check-prereqs.sh ────────
LANG_CHOICE="${PROXYBOX_LANG:-auto}"
while [ $# -gt 0 ]; do
    case "$1" in
        --lang)        LANG_CHOICE="${2:-auto}"; shift 2 ;;
        --lang=*)      LANG_CHOICE="${1#*=}"; shift ;;
        -h|--help)     sed -n '2,11p' "$0"; exit 0 ;;
        *)             echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

if [ "$LANG_CHOICE" = "auto" ]; then
    case "${LANG:-}" in
        zh*|ZH*) LANG_CHOICE=zh ;;
        *)       LANG_CHOICE=en ;;
    esac
fi

case "$LANG_CHOICE" in
    en|zh) ;;
    *) echo "unsupported --lang: $LANG_CHOICE (use 'en' or 'zh')" >&2; exit 2 ;;
esac

# ─── i18n strings ────────────────────────────────────────────────
if [ "$LANG_CHOICE" = "zh" ]; then
    M_NOT_PROXYBOX_DIR="错误: PROXYBOX_DIR=%s 不像 ProxyBox 源码目录"
    M_EXPECT_PYPROJECT="       预期 \$PROXYBOX_DIR/ 下有 pyproject.toml"
    M_PREFLIGHT_FAIL="错误: 环境检查失败, 修复上方问题后重跑."
    M_PREFLIGHT_HINT="       (自动装缺失 apt 包请跑: sudo bash %s --install --lang %s)"
    M_INSTALLER="==> ProxyBox 安装器"
    M_INSTALLER_SRC="    源码:   %s"
    M_INSTALLER_CFG="    配置:   %s"
    M_APT_INSTALLING="==> 安装系统包..."
    M_SINGBOX_DOWNLOAD="==> 下载 sing-box..."
    M_SINGBOX_VERSION="    sing-box: %s"
    M_GEN_KEYPAIR="==> 生成 Reality 密钥 + Hy2 证书 + 随机 SNI..."
    M_VENV_CREATE="==> 创建 Python venv..."
    M_INSTALL_DEPS="==> 安装 ProxyBox 依赖..."
    M_GEN_CONFIG="==> 生成 ProxyBox config.yaml..."
    M_START_SERVICES="==> 启动服务..."
    M_BOOTSTRAP_DEVICE="==> 创建首台默认设备 (%s)..."
    M_BOOTSTRAP_OK="    设备已创建: sub_token=%s"
    M_BOOTSTRAP_FAIL="    [警告] 首台设备自动创建失败, 请稍后手动到 admin 面板新建"
    M_DONE_HEADER="ProxyBox 安装完成"
    M_DONE_SUB="直接复制下方任一 URL 使用, 无需其他操作"
    M_SECTION_ADMIN_TITLE="🔑 后台管理 URL"
    M_SECTION_ADMIN_HINT="含 token, 请妥善保存"
    M_SECTION_SUBS_TITLE="📲 订阅 URL"
    M_SECTION_SUBS_HINT="任挑一个粘进客户端的 \"添加订阅\""
    M_SUB_DEFAULT_TAG="[推荐]"
    M_SUB_DEFAULT_DESC="sing-box · Shadowrocket · Hiddify  (Type: Subscribe)"
    M_SUB_CLASH_TAG="[Clash 系]"
    M_SUB_CLASH_DESC="Stash · Clash for iOS · Clash Verge"
    M_SUB_MERLIN_TAG="[路由器]"
    M_SUB_MERLIN_DESC="AsusWRT-Merlin · Clash 透明代理"
    M_SUB_SR_TAG="[备用]"
    M_SUB_SR_DESC="Shadowrocket .conf · Surge 格式"
    M_SUB_TXT_TAG="[别名]"
    M_SUB_TXT_DESC="URI 列表 · .txt 扩展名"
    M_SECTION_SERVICES_TITLE="服务状态"
    M_SECTION_ADVANCED_TITLE="进阶 — 按需开启"
    M_ADV_PASSKEY="passkey   config.yaml 里 features.passkey=true + 套 HTTPS"
    M_ADV_BOT="TG bot    填 /etc/proxybox/bot.env, 然后 systemctl enable --now proxybox-bot"
    M_ADV_TLS="HTTPS     Caddy + Let's Encrypt 反代 8080 (生产环境)"
    M_FOOTER_TIP="完整 token 备份位置: %s/config.yaml (admin.token 字段)"
    M_ERR_UNSUPPORTED_ARCH="错误: 不支持的架构 %s"
else
    M_NOT_PROXYBOX_DIR="ERROR: PROXYBOX_DIR=%s doesn't look like a ProxyBox checkout"
    M_EXPECT_PYPROJECT="       expected pyproject.toml at \$PROXYBOX_DIR/"
    M_PREFLIGHT_FAIL="ERROR: pre-flight check failed. fix the issues above and re-run."
    M_PREFLIGHT_HINT="       (to install missing apt packages automatically: sudo bash %s --install --lang %s)"
    M_INSTALLER="==> ProxyBox installer"
    M_INSTALLER_SRC="    source:     %s"
    M_INSTALLER_CFG="    config:     %s"
    M_APT_INSTALLING="==> installing system packages..."
    M_SINGBOX_DOWNLOAD="==> installing sing-box..."
    M_SINGBOX_VERSION="    sing-box: %s"
    M_GEN_KEYPAIR="==> generating Reality keypair + Hy2 cert + random SNI..."
    M_VENV_CREATE="==> creating Python venv..."
    M_INSTALL_DEPS="==> installing ProxyBox deps..."
    M_GEN_CONFIG="==> generating ProxyBox config..."
    M_START_SERVICES="==> starting services..."
    M_BOOTSTRAP_DEVICE="==> auto-creating first device (%s)..."
    M_BOOTSTRAP_OK="    device created: sub_token=%s"
    M_BOOTSTRAP_FAIL="    [warn] first-device auto-create failed, create one manually from admin UI later"
    M_DONE_HEADER="ProxyBox installed"
    M_DONE_SUB="copy any URL below to start using it, no further steps required"
    M_SECTION_ADMIN_TITLE="🔑 admin URL"
    M_SECTION_ADMIN_HINT="contains token, keep private"
    M_SECTION_SUBS_TITLE="📲 subscription URLs"
    M_SECTION_SUBS_HINT="paste any one into your client's \"Add Subscription\""
    M_SUB_DEFAULT_TAG="[pick this]"
    M_SUB_DEFAULT_DESC="sing-box · Shadowrocket · Hiddify  (Type: Subscribe)"
    M_SUB_CLASH_TAG="[Clash]"
    M_SUB_CLASH_DESC="Stash · Clash for iOS · Clash Verge"
    M_SUB_MERLIN_TAG="[router]"
    M_SUB_MERLIN_DESC="AsusWRT-Merlin · Clash transparent proxy"
    M_SUB_SR_TAG="[fallback]"
    M_SUB_SR_DESC="Shadowrocket .conf · Surge format"
    M_SUB_TXT_TAG="[alias]"
    M_SUB_TXT_DESC="URI list · .txt extension"
    M_SECTION_SERVICES_TITLE="services"
    M_SECTION_ADVANCED_TITLE="advanced — enable later if needed"
    M_ADV_PASSKEY="passkey   set features.passkey=true + passkey.rp_id/origin in config.yaml + Caddy/TLS"
    M_ADV_BOT="TG bot    fill /etc/proxybox/bot.env then systemctl enable --now proxybox-bot"
    M_ADV_TLS="HTTPS     install Caddy + Let's Encrypt in front of 8080 for production"
    M_FOOTER_TIP="full token also stored at %s/config.yaml (admin.token field)"
    M_ERR_UNSUPPORTED_ARCH="ERROR: unsupported arch %s"
fi

# ─── colour helpers (TTY only — bot/file-piped output stays plain) ──
if [ -t 1 ]; then
    C_RESET=$'\033[0m'
    C_BOLD=$'\033[1m'
    C_DIM=$'\033[2m'
    C_GREEN=$'\033[32m'
    C_GREEN_B=$'\033[1;32m'
    C_YELLOW_B=$'\033[1;33m'
    C_CYAN_B=$'\033[1;36m'
    C_RED=$'\033[31m'
else
    C_RESET=''
    C_BOLD=''
    C_DIM=''
    C_GREEN=''
    C_GREEN_B=''
    C_YELLOW_B=''
    C_CYAN_B=''
    C_RED=''
fi
HR="━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ─── config (overridable via env) ──────────────────────────────────
: "${PROXYBOX_DIR:=$(cd "$(dirname "$0")/.." && pwd)}"
: "${CONFIG_DIR:=/etc/proxybox}"
: "${DATA_DIR:=/var/lib/proxybox}"
: "${LOG_DIR:=/var/log/proxybox}"
: "${SUB_DIR:=/var/www/proxybox-sub}"
: "${SINGBOX_DIR:=/etc/sing-box}"

# ─── sentinel: this looks like a ProxyBox checkout ─────────────────
if [ ! -f "$PROXYBOX_DIR/pyproject.toml" ]; then
    printf "$M_NOT_PROXYBOX_DIR\n" "$PROXYBOX_DIR" >&2
    printf "$M_EXPECT_PYPROJECT\n" >&2
    exit 1
fi

# ─── pre-flight: defer to check-prereqs.sh ─────────────────────────
if [ "${PROXYBOX_SKIP_PREREQ:-0}" != "1" ]; then
    if ! bash "$PROXYBOX_DIR/deploy/check-prereqs.sh" --lang "$LANG_CHOICE"; then
        echo ""
        printf "$M_PREFLIGHT_FAIL\n" >&2
        printf "$M_PREFLIGHT_HINT\n" "$PROXYBOX_DIR/deploy/check-prereqs.sh" "$LANG_CHOICE" >&2
        exit 1
    fi
fi

echo ""
echo "$M_INSTALLER"
printf "$M_INSTALLER_SRC\n" "$PROXYBOX_DIR"
printf "$M_INSTALLER_CFG\n" "$CONFIG_DIR"

# ─── 1. system packages ────────────────────────────────────────────
echo "$M_APT_INSTALLING"
apt-get -y update >/dev/null
apt-get -y install \
    python3 python3-venv python3-pip python3-systemd \
    curl sqlite3 openssl fail2ban \
    >/dev/null

# ─── 2. directories ────────────────────────────────────────────────
mkdir -p "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR" "$SUB_DIR" "$SINGBOX_DIR"

# ─── 3. sing-box binary ────────────────────────────────────────────
if ! command -v sing-box >/dev/null; then
    echo "$M_SINGBOX_DOWNLOAD"
    ARCH=$(uname -m)
    case "$ARCH" in
        x86_64)         ARCH=amd64 ;;
        aarch64|arm64)  ARCH=arm64 ;;
        *) printf "$M_ERR_UNSUPPORTED_ARCH\n" "$ARCH" >&2; exit 1 ;;
    esac
    RESP=$(curl -fsSL "https://api.github.com/repos/SagerNet/sing-box/releases/latest")
    SBVER=$(printf '%s\n' "$RESP" | grep '"tag_name":' | head -1 | cut -d'"' -f4)
    cd /tmp
    curl -fsSLO "https://github.com/SagerNet/sing-box/releases/download/${SBVER}/sing-box-${SBVER#v}-linux-${ARCH}.tar.gz"
    tar -xzf "sing-box-${SBVER#v}-linux-${ARCH}.tar.gz"
    install -m 755 "sing-box-${SBVER#v}-linux-${ARCH}/sing-box" /usr/local/bin/sing-box
    rm -rf "/tmp/sing-box-${SBVER#v}"*
fi
printf "$M_SINGBOX_VERSION\n" "$(sing-box version | head -1)"

# ─── 4. sing-box systemd unit ──────────────────────────────────────
if [ ! -f /etc/systemd/system/sing-box.service ]; then
    cat > /etc/systemd/system/sing-box.service <<'UNIT'
[Unit]
Description=sing-box service
Documentation=https://sing-box.app
After=network.target

[Service]
Type=simple
NoNewPrivileges=yes
ExecStart=/usr/local/bin/sing-box run -c /etc/sing-box/config.json
ExecReload=/bin/kill -HUP $MAINPID
Restart=on-failure
RestartSec=3s
LimitNOFILE=1048576

[Install]
WantedBy=multi-user.target
UNIT
    systemctl daemon-reload
fi

# ─── 5. sing-box config (only generate if missing) ────────────────
if [ ! -f "$SINGBOX_DIR/config.json" ]; then
    echo "$M_GEN_KEYPAIR"
    KEYPAIR=$(sing-box generate reality-keypair)
    PRIVATE_KEY=$(printf '%s\n' "$KEYPAIR" | awk '/PrivateKey/{print $2}')
    SHORT_ID=$(openssl rand -hex 8)
    HY2_OBFS_PW=$(openssl rand -hex 16)

    SNI_CANDIDATES=(www.microsoft.com www.apple.com www.cloudflare.com www.amazon.com)
    SNI="${SNI_CANDIDATES[$RANDOM % 4]}"

    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout "$SINGBOX_DIR/key.pem" -out "$SINGBOX_DIR/cert.pem" \
        -subj "/CN=$SNI" 2>/dev/null
    chmod 600 "$SINGBOX_DIR/key.pem"

    cat > "$SINGBOX_DIR/config.json" <<JSON
{
  "log": { "level": "info", "timestamp": true },
  "experimental": {
    "clash_api": { "external_controller": "127.0.0.1:9090" }
  },
  "inbounds": [
    {
      "type": "vless",
      "tag": "vless-template",
      "listen": "::",
      "listen_port": 11000,
      "users": [],
      "tls": {
        "enabled": true,
        "server_name": "$SNI",
        "reality": {
          "enabled": true,
          "handshake": { "server": "$SNI", "server_port": 443 },
          "private_key": "$PRIVATE_KEY",
          "short_id": ["$SHORT_ID"]
        }
      }
    },
    {
      "type": "hysteria2",
      "tag": "hy2-template",
      "listen": "::",
      "listen_port": 21000,
      "users": [],
      "obfs": { "type": "salamander", "password": "$HY2_OBFS_PW" },
      "tls": {
        "enabled": true,
        "alpn": ["h3"],
        "certificate_path": "$SINGBOX_DIR/cert.pem",
        "key_path": "$SINGBOX_DIR/key.pem"
      },
      "masquerade": "https://$SNI"
    }
  ],
  "outbounds": [{ "type": "direct", "tag": "direct" }]
}
JSON
    chmod 600 "$SINGBOX_DIR/config.json"
    sing-box check -c "$SINGBOX_DIR/config.json"
fi

# ─── 6. Python venv + deps ─────────────────────────────────────────
cd "$PROXYBOX_DIR"
if [ ! -d .venv ]; then
    echo "$M_VENV_CREATE"
    python3 -m venv .venv
fi
echo "$M_INSTALL_DEPS"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e .

# ─── 7. ProxyBox config.yaml ───────────────────────────────────────
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    echo "$M_GEN_CONFIG"
    ADMIN_TOKEN=$(.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(24))")
    PUBLIC_HOST=$(curl -fsS --max-time 5 https://ifconfig.me 2>/dev/null \
                 || curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null \
                 || echo "")
    cat > "$CONFIG_DIR/config.yaml" <<YAML
admin:
  token: "$ADMIN_TOKEN"
  host: "0.0.0.0"
  port: 8080
server:
  public_host: "$PUBLIC_HOST"
paths:
  traffic_db: $DATA_DIR/traffic.db
  static_dir: $PROXYBOX_DIR/static
  sub_dir: $SUB_DIR
  singbox_config: $SINGBOX_DIR/config.json
  session_secret: $CONFIG_DIR/session-secret
services:
  monitored:
    - sing-box
    - proxybox-admin
    - proxybox-traffic-worker
    - fail2ban
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
YAML
    chmod 600 "$CONFIG_DIR/config.yaml"
fi

# ─── 8. fail2ban [manual] jail ─────────────────────────────────────
if ! grep -q '^\[manual\]' /etc/fail2ban/jail.local 2>/dev/null; then
    cat > /etc/fail2ban/jail.local <<'JAIL'
# ProxyBox manual ban jail — explicit ban via /action/block.
# backend=systemd avoids /var/log/auth.log dependency (Debian 13 = journald-only).
[manual]
enabled  = true
backend  = systemd
filter   = sshd
action   = iptables-allports[name=manual]
bantime  = -1
findtime = 60
maxretry = 99999
JAIL
fi

# ─── 9. ProxyBox admin systemd unit ────────────────────────────────
if [ ! -f /etc/systemd/system/proxybox-admin.service ]; then
    cat > /etc/systemd/system/proxybox-admin.service <<UNIT
[Unit]
Description=ProxyBox admin HTTP API
After=network.target sing-box.service
Wants=sing-box.service

[Service]
Type=simple
WorkingDirectory=$PROXYBOX_DIR
Environment=PROXYBOX_CONFIG=$CONFIG_DIR/config.yaml
ExecStart=$PROXYBOX_DIR/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080
Restart=on-failure
RestartSec=5s
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
UNIT
    systemctl daemon-reload
fi

# ─── 10. other systemd units (worker + bot) ────────────────────────
for unit in proxybox-traffic-worker.service proxybox-bot.service; do
    src="$PROXYBOX_DIR/deploy/systemd/$unit"
    dst="/etc/systemd/system/$unit"
    if [ -f "$src" ] && [ ! -f "$dst" ]; then
        cp "$src" "$dst"
        systemctl daemon-reload
    fi
done

# ─── 11. enable + start core services ──────────────────────────────
echo "$M_START_SERVICES"
systemctl enable --now fail2ban  >/dev/null 2>&1 || true
systemctl enable --now sing-box  >/dev/null 2>&1 || true
systemctl enable --now proxybox-admin >/dev/null 2>&1 || true
systemctl enable --now proxybox-traffic-worker >/dev/null 2>&1 || true
sleep 3

# ─── 12. read token + host ─────────────────────────────────────────
ADMIN_TOKEN=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('$CONFIG_DIR/config.yaml'))['admin']['token'])")
PUBLIC_HOST=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('$CONFIG_DIR/config.yaml'))['server']['public_host'])")
ADMIN_BASE="http://${PUBLIC_HOST:-<your-vps-ip>}:8080"
ADMIN_URL="$ADMIN_BASE/admin/$ADMIN_TOKEN/"

# ─── 13. auto-create first device (one-shot UX) ────────────────────
# Wait for proxybox-admin to be reachable on localhost (sleep 3 above
# is usually enough on a real VPS, but be defensive on slow hosts).
DEFAULT_DEVICE_NAME="${PROXYBOX_FIRST_DEVICE:-phone-1}"
SUB_TOKEN=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -s -o /dev/null -w "%{http_code}" "http://localhost:8080/admin/$ADMIN_TOKEN/api/status" 2>/dev/null | grep -q '^200$'; then
        break
    fi
    sleep 1
done

# Check if device already exists (re-install on a host that already has one)
EXISTING=$(curl -s "http://localhost:8080/admin/$ADMIN_TOKEN/api/devices/list" 2>/dev/null \
    | .venv/bin/python -c "
import json, sys
try:
    d = json.load(sys.stdin)
    devs = d.get('devices', [])
    if devs:
        print(devs[0]['name'] + '\\t' + devs[0]['sub_token'])
except Exception:
    pass
" 2>/dev/null)

if [ -n "$EXISTING" ]; then
    DEFAULT_DEVICE_NAME=$(echo "$EXISTING" | cut -f1)
    SUB_TOKEN=$(echo "$EXISTING" | cut -f2)
else
    printf "$M_BOOTSTRAP_DEVICE\n" "$DEFAULT_DEVICE_NAME"
    RESPONSE=$(curl -s -X POST \
        -H "Content-Type: application/json" \
        -d "{\"name\":\"$DEFAULT_DEVICE_NAME\",\"kind\":\"mobile\",\"label\":\"$DEFAULT_DEVICE_NAME\"}" \
        "http://localhost:8080/admin/$ADMIN_TOKEN/api/devices/new" 2>/dev/null)
    SUB_TOKEN=$(echo "$RESPONSE" | .venv/bin/python -c "
import json, sys
try:
    print(json.load(sys.stdin)['device']['sub_token'])
except Exception:
    pass
" 2>/dev/null)
    if [ -n "$SUB_TOKEN" ]; then
        printf "$M_BOOTSTRAP_OK\n" "$SUB_TOKEN"
    else
        echo "$M_BOOTSTRAP_FAIL"
    fi
fi

# ─── 14. summary ───────────────────────────────────────────────────
echo ""
echo ""
printf "%s  %s%s\n" "$C_GREEN_B" "$HR" "$C_RESET"
printf "  %s✅  %s%s\n" "$C_GREEN_B" "$M_DONE_HEADER" "$C_RESET"
printf "      %s%s%s\n" "$C_DIM" "$M_DONE_SUB" "$C_RESET"
printf "%s  %s%s\n" "$C_GREEN_B" "$HR" "$C_RESET"
echo ""

# ── Admin URL block (the credential — emphasised) ───────────────────
printf "  %s%s%s  %s— %s%s\n" "$C_CYAN_B" "$M_SECTION_ADMIN_TITLE" "$C_RESET" "$C_DIM" "$M_SECTION_ADMIN_HINT" "$C_RESET"
echo ""
printf "      %s%s%s\n" "$C_GREEN_B" "$ADMIN_URL" "$C_RESET"
echo ""

# ── Subscription URLs block ─────────────────────────────────────────
if [ -n "$SUB_TOKEN" ]; then
    SUB_BASE="$ADMIN_BASE/api/sub/$SUB_TOKEN"
    printf "  %s%s%s  %s— %s%s\n" "$C_CYAN_B" "$M_SECTION_SUBS_TITLE" "$C_RESET" "$C_DIM" "$M_SECTION_SUBS_HINT" "$C_RESET"
    echo ""

    # Recommended — yellow ✦ + bold tag + bold green URL
    printf "    %s✦ %s%s  %s%s%s\n" \
        "$C_YELLOW_B" "$M_SUB_DEFAULT_TAG" "$C_RESET" "$C_BOLD" "$M_SUB_DEFAULT_DESC" "$C_RESET"
    printf "      %s%s%s\n" "$C_GREEN_B" "$SUB_BASE" "$C_RESET"
    echo ""

    # Other formats — same tag-bold + URL-green pattern, no ✦, no bold on URL
    for entry in \
        "$M_SUB_CLASH_TAG|$M_SUB_CLASH_DESC|/clash.yaml" \
        "$M_SUB_MERLIN_TAG|$M_SUB_MERLIN_DESC|/merlin.yaml" \
        "$M_SUB_SR_TAG|$M_SUB_SR_DESC|/shadowrocket.conf" \
        "$M_SUB_TXT_TAG|$M_SUB_TXT_DESC|/sub.txt"; do
        IFS='|' read -r tag desc suffix <<< "$entry"
        printf "      %s%s%s  %s\n" "$C_BOLD" "$tag" "$C_RESET" "$desc"
        printf "      %s%s%s%s\n" "$C_GREEN" "$SUB_BASE" "$suffix" "$C_RESET"
        echo ""
    done
fi

# ── Services block — green ✓ for active, red ✗ for inactive ─────────
printf "  %s%s%s\n" "$C_CYAN_B" "$M_SECTION_SERVICES_TITLE" "$C_RESET"
echo ""
for svc in sing-box proxybox-admin proxybox-traffic-worker fail2ban; do
    state=$(systemctl is-active "$svc" 2>/dev/null || echo unknown)
    case "$state" in
        active)
            printf "      %s✓%s  %-26s %s%s%s\n" \
                "$C_GREEN_B" "$C_RESET" "$svc" "$C_GREEN" "$state" "$C_RESET"
            ;;
        inactive)
            printf "      %s✗%s  %-26s %s%s%s\n" \
                "$C_RED" "$C_RESET" "$svc" "$C_RED" "$state" "$C_RESET"
            ;;
        *)
            printf "      ?  %-26s %s\n" "$svc" "$state"
            ;;
    esac
done
echo ""

# ── Advanced (dim — these are opt-in, deliberately low-emphasis) ─────
printf "  %s%s%s\n" "$C_DIM" "$M_SECTION_ADVANCED_TITLE" "$C_RESET"
printf "    %s· %s%s\n" "$C_DIM" "$M_ADV_PASSKEY" "$C_RESET"
printf "    %s· %s%s\n" "$C_DIM" "$M_ADV_BOT" "$C_RESET"
printf "    %s· %s%s\n" "$C_DIM" "$M_ADV_TLS" "$C_RESET"
echo ""

# ── Footer (dim — backup info, not primary action) ──────────────────
printf "  %s" "$C_DIM"
printf "$M_FOOTER_TIP" "$CONFIG_DIR"
printf "%s\n" "$C_RESET"
echo ""
