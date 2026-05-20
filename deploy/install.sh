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
    M_DONE_HEADER="ProxyBox 已安装"
    M_ADMIN_URL="  admin URL:    http://%s:8080/admin/%s.../"
    M_FULL_TOKEN="  完整 token:   %s/config.yaml  (admin.token 字段)"
    M_SERVICES_LABEL="  服务状态:"
    M_NEXT_LABEL="  接下来:"
    M_NEXT_1="    1. 从 %s/config.yaml 取 token, 离线保存"
    M_NEXT_2="    2. 浏览器打开上方 admin URL (HTTP, 生产请套 Caddy + Let's Encrypt)"
    M_NEXT_3="    3. 在 admin 面板点 '+ 添加设备' 创建第一个设备"
    M_NEXT_4="    4. 把订阅 URL 粘进 sing-box 兼容客户端 (Shadowrocket / sing-box / Hiddify)"
    M_OPTIONAL_LABEL="  可选功能:"
    M_OPTIONAL_PASSKEY="    - passkey:  config.yaml 里 features.passkey=true + 填 passkey.rp_id/origin + 套 HTTPS"
    M_OPTIONAL_BOT="    - TG bot:   编辑 /etc/proxybox/bot.env, 然后 'systemctl enable --now proxybox-bot'"
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
    M_DONE_HEADER="ProxyBox installed"
    M_ADMIN_URL="  admin URL:  http://%s:8080/admin/%s.../"
    M_FULL_TOKEN="  full token: %s/config.yaml  (admin.token field)"
    M_SERVICES_LABEL="  services:"
    M_NEXT_LABEL="  next:"
    M_NEXT_1="    1. grep token in %s/config.yaml — save it offline"
    M_NEXT_2="    2. open the admin URL above (HTTP for now; set up Caddy + Let's Encrypt for production)"
    M_NEXT_3="    3. in the admin UI, click '+ Add device' to create your first device"
    M_NEXT_4="    4. paste subscription URL into a sing-box-compatible client (Shadowrocket / sing-box / Hiddify)"
    M_OPTIONAL_LABEL="  optional features:"
    M_OPTIONAL_PASSKEY="    - passkey:  set features.passkey=true + passkey.rp_id/origin in config.yaml + Caddy/TLS"
    M_OPTIONAL_BOT="    - TG bot:   fill /etc/proxybox/bot.env then 'systemctl enable --now proxybox-bot'"
    M_ERR_UNSUPPORTED_ARCH="ERROR: unsupported arch %s"
fi

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

# ─── 12. summary ───────────────────────────────────────────────────
ADMIN_TOKEN=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('$CONFIG_DIR/config.yaml'))['admin']['token'])")
PUBLIC_HOST=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('$CONFIG_DIR/config.yaml'))['server']['public_host'])")
TOKEN_PREFIX="${ADMIN_TOKEN:0:8}"

echo ""
echo "============================================================"
echo "  $M_DONE_HEADER"
echo "============================================================"
printf "$M_ADMIN_URL\n" "${PUBLIC_HOST:-<your-vps-ip>}" "$TOKEN_PREFIX"
printf "$M_FULL_TOKEN\n" "$CONFIG_DIR"
echo ""
echo "$M_SERVICES_LABEL"
for svc in sing-box proxybox-admin proxybox-traffic-worker fail2ban; do
    state=$(systemctl is-active "$svc" 2>/dev/null || echo unknown)
    case "$state" in
        active)   mark="[+]" ;;
        inactive) mark="[-]" ;;
        *)        mark="[?]" ;;
    esac
    printf "    %s %-30s %s\n" "$mark" "$svc" "$state"
done
echo ""
echo "$M_NEXT_LABEL"
printf "$M_NEXT_1\n" "$CONFIG_DIR"
echo "$M_NEXT_2"
echo "$M_NEXT_3"
echo "$M_NEXT_4"
echo ""
echo "$M_OPTIONAL_LABEL"
echo "$M_OPTIONAL_PASSKEY"
echo "$M_OPTIONAL_BOT"
echo "============================================================"
