#!/usr/bin/env bash
# ProxyBox installer — unified entrypoint for Docker or native install.
#
# Usage:
#   INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
#   git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
#   cd "$INSTALL_DIR" && bash deploy/install.sh                      # choose install mode
#   cd "$INSTALL_DIR" && bash deploy/install.sh --docker             # Docker install
#   cd "$INSTALL_DIR" && bash deploy/install.sh --native --fresh     # native install; refuses old state
#
# Idempotent: re-running it on an existing install does nothing destructive,
# only fills in missing pieces. Safe to run repeatedly.
# Fresh mode: --fresh or PROXYBOX_FRESH=1 generates a new native install only
# when no previous native state is present. It does not delete old state.
# Destructive cleanup requires --purge-existing-proxybox plus confirmation.
# Installation red line: never delete or modify user files/services outside
# this ProxyBox install. On non-dedicated VPS hosts, use Docker install.

set -euo pipefail
ORIG_ARGS=("$@")
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

dispatch_install_mode() {
    local mode="${PROXYBOX_INSTALL_MODE:-}"
    case "$mode" in
        docker)
            exec bash "$ROOT_DIR/deploy/docker-install.sh" "$@"
            ;;
        native)
            return
            ;;
        "")
            ;;
        *)
            echo "错误: PROXYBOX_INSTALL_MODE 只能是 docker 或 native" >&2
            exit 2
            ;;
    esac

    # Back-compat: any native install option keeps the old native path.
    if [ "$#" -gt 0 ]; then
        export PROXYBOX_INSTALL_MODE=native
        return
    fi

    echo
    echo "ProxyBox 安装方式选择"
    echo
    echo "  1) Docker 安装（推荐）"
    echo "     容器隔离，自动避开已占用端口；只写本次安装专属 Docker guard 和 HTTPS helper。"
    echo "     如果这台 VPS 已经跑了其他服务、网站、面板或生产系统，强烈推荐选这个。"
    echo
    echo "  2) 宿主机安装（高级）"
    echo "     直接安装 Python、sing-box、systemd unit、fail2ban，可在面板内配置 Caddy/HTTPS。"
    echo "     仅建议用于干净、专用、不会跑其他生产服务的 VPS。"
    echo
    echo "必须明确选择 1 或 2；推荐选择 1(Docker)。"
    local choice
    if [ -t 0 ] && [ -t 1 ]; then
        read -r -p "请选择 [1/2]: " choice
    else
        echo "错误: 非交互环境不能自动选择安装方式。" >&2
        echo "请显式运行: bash deploy/install.sh --docker" >&2
        echo "或: bash deploy/install.sh --native --fresh --lang zh" >&2
        exit 2
    fi
    case "$choice" in
        1|d|D|docker|Docker|DOCKER)
            exec bash "$ROOT_DIR/deploy/docker-install.sh"
            ;;
        2|n|N|native|Native|NATIVE)
            export PROXYBOX_INSTALL_MODE=native
            ;;
        *)
            echo "错误: 请输入 1(Docker) 或 2(宿主机)" >&2
            exit 2
            ;;
    esac
}

case "${1:-}" in
    --docker)
        shift
        exec bash "$ROOT_DIR/deploy/docker-install.sh" "$@"
        ;;
    --native)
        shift
        ORIG_ARGS=("$@")
        export PROXYBOX_INSTALL_MODE=native
        ;;
esac

dispatch_install_mode "$@"

# ─── argv: --lang en|zh + pass-through to check-prereqs.sh ────────
LANG_CHOICE="${PROXYBOX_LANG:-auto}"
FRESH_MODE="${PROXYBOX_FRESH:-0}"
PURGE_MODE="${PROXYBOX_PURGE_EXISTING_PROXYBOX:-0}"
while [ $# -gt 0 ]; do
    case "$1" in
        --lang)        LANG_CHOICE="${2:-auto}"; shift 2 ;;
        --lang=*)      LANG_CHOICE="${1#*=}"; shift ;;
        --fresh)       FRESH_MODE=1; shift ;;
        --reuse|--no-fresh) FRESH_MODE=0; shift ;;
        --purge-existing-proxybox) PURGE_MODE=1; shift ;;
        -h|--help)     sed -n '2,13p' "$0"; exit 0 ;;
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
case "$FRESH_MODE" in
    1|true|TRUE|yes|YES|on|ON) FRESH_MODE=1 ;;
    *)                         FRESH_MODE=0 ;;
esac
case "$PURGE_MODE" in
    1|true|TRUE|yes|YES|on|ON) PURGE_MODE=1 ;;
    *)                         PURGE_MODE=0 ;;
esac

# ─── i18n strings ────────────────────────────────────────────────
if [ "$LANG_CHOICE" = "zh" ]; then
    M_NOT_PROXYBOX_DIR="错误: PROXYBOX_DIR=%s 不像 ProxyBox 源码目录"
    M_EXPECT_PYPROJECT="       预期 \$PROXYBOX_DIR/ 下有 pyproject.toml"
    M_PREFLIGHT_FAIL="错误: 环境检查失败, 修复上方问题后重跑."
    M_PREFLIGHT_HINT="       (自动装缺失 apt 包请跑: sudo bash %s --install --lang %s)"
    M_ESCALATE="==> 检测到非 root, 使用 sudo 重新运行安装器..."
    M_NEED_ROOT="错误: install.sh 需要 root 或免密 sudo"
    M_INSTALLER="==> ProxyBox 安装器"
    M_INSTALLER_SRC="    源码:   %s"
    M_INSTALLER_CFG="    配置:   %s"
    M_INSTALLER_MODE="    模式:   %s"
    M_MODE_FRESH="fresh (发现旧 native 状态会拒绝, 不自动删除)"
    M_MODE_REUSE="reuse (保留已有状态)"
    M_MODE_PURGE="purge (显式删除旧 ProxyBox native 状态)"
    M_PURGE_CLEAN="==> 危险清理: 删除旧 ProxyBox 配置、数据、订阅、unit 和 HTTPS 配置..."
    M_PURGE_DONE="    清理完成, 将重新生成全新身份"
    M_EXISTING_REFUSE="错误: 检测到已有 ProxyBox/sing-box native 状态, 为保护用户数据已拒绝继续。请改用 Docker 新目录安装, 或在确认要删除旧 ProxyBox 状态后显式运行 --purge-existing-proxybox。"
    M_PURGE_CONFIRM="这会删除旧 ProxyBox native 状态。请输入 DELETE PROXYBOX 确认: "
    M_PURGE_NEED_CONFIRM="错误: 非交互环境执行 --purge-existing-proxybox 时, 必须设置 PROXYBOX_CONFIRM_PURGE='DELETE PROXYBOX'"
    M_APT_INSTALLING="==> 安装系统包..."
    M_PY311_INSTALLING="==> 安装并验证 Python 3.11..."
    M_PY311_FAIL="错误: 未能安装可用的 Python 3.11"
    M_SINGBOX_DOWNLOAD="==> 下载 sing-box..."
    M_SINGBOX_VERSION="    sing-box: %s"
    M_GEN_KEYPAIR="==> 生成 Reality 密钥 + Hy2 证书 + 随机 SNI..."
    M_VENV_CREATE="==> 创建 Python venv..."
    M_INSTALL_DEPS="==> 安装 ProxyBox 依赖..."
    M_GEN_CONFIG="==> 生成 ProxyBox config.yaml..."
    M_START_SERVICES="==> 启动服务..."
    M_BOOTSTRAP_DEVICE="==> 创建首台默认设备 (%s)..."
    M_BOOTSTRAP_SKIP="    已跳过首台默认设备创建 (PROXYBOX_FIRST_DEVICE 为空)"
    M_BOOTSTRAP_OK="    设备已创建: sub_token=%s"
    M_BOOTSTRAP_FAIL="    [警告] 首台设备自动创建失败, 请稍后手动到 admin 面板新建"
    M_DONE_HEADER="ProxyBox 安装完成"
    M_DONE_SUB="请保存下方登录凭据, 然后访问后台地址"
    M_SECTION_LOGIN_TITLE="🛡 后台登录凭据"
    M_SECTION_LOGIN_HINT="务必复制保存 — 凭据丢失需 SSH 读取 admin.password + config.yaml"
    M_LOGIN_URL_LABEL="登录地址"
    M_LOGIN_USER_LABEL="用户名"
    M_LOGIN_PASS_LABEL="密  码"
    M_SECTION_SUBS_TITLE="📲 订阅 URL"
    M_SECTION_SUBS_HINT="Shadowrocket 优先用 [SR 分流]; Stash/Clash 用 [Clash 系]"
    M_SUB_DEFAULT_TAG="[通用]"
    M_SUB_DEFAULT_DESC="sing-box · Hiddify · 双协议节点"
    M_SUB_CLASH_TAG="[Clash 系]"
    M_SUB_CLASH_DESC="Stash · Clash for iOS · Clash Verge"
    M_SUB_SR_YAML_TAG="[SR 分流]"
    M_SUB_SR_YAML_DESC="Shadowrocket 订阅链接 · 节点+规则"
    M_SUB_MERLIN_TAG="[路由器]"
    M_SUB_MERLIN_DESC="AsusWRT-Merlin · Clash 透明代理"
    M_SECTION_SERVICES_TITLE="服务状态"
    M_SECTION_ADVANCED_TITLE="进阶 — 按需开启"
    M_ADV_PASSKEY="passkey   config.yaml 里 features.passkey=true + 套 HTTPS"
    M_ADV_BOT="TG bot    填 /etc/proxybox/bot.env, 然后 systemctl enable --now proxybox-bot"
    M_ADV_TLS="HTTPS     Caddy + Let's Encrypt 反代 8080 (生产环境)"
    M_FOOTER_TIP="凭据找回: 用户名/login_path 在 %s/config.yaml,密码在 %s/admin.password (0400)"
    M_ERR_UNSUPPORTED_ARCH="错误: 不支持的架构 %s"
else
    M_NOT_PROXYBOX_DIR="ERROR: PROXYBOX_DIR=%s doesn't look like a ProxyBox checkout"
    M_EXPECT_PYPROJECT="       expected pyproject.toml at \$PROXYBOX_DIR/"
    M_PREFLIGHT_FAIL="ERROR: pre-flight check failed. fix the issues above and re-run."
    M_PREFLIGHT_HINT="       (to install missing apt packages automatically: sudo bash %s --install --lang %s)"
    M_ESCALATE="==> not running as root; re-running installer with sudo..."
    M_NEED_ROOT="ERROR: install.sh needs root or passwordless sudo"
    M_INSTALLER="==> ProxyBox installer"
    M_INSTALLER_SRC="    source:     %s"
    M_INSTALLER_CFG="    config:     %s"
    M_INSTALLER_MODE="    mode:       %s"
    M_MODE_FRESH="fresh (refuse existing native state; no auto-delete)"
    M_MODE_REUSE="reuse (keep existing state)"
    M_MODE_PURGE="purge (explicitly remove old ProxyBox native state)"
    M_PURGE_CLEAN="==> dangerous purge: removing old ProxyBox config, data, subscriptions, units, and HTTPS config..."
    M_PURGE_DONE="    purge complete; generating a new identity"
    M_EXISTING_REFUSE="ERROR: existing ProxyBox/sing-box native state detected; refusing to continue to protect user data. Use Docker in a new directory, or explicitly run --purge-existing-proxybox only after you decide to delete the old ProxyBox state."
    M_PURGE_CONFIRM="This deletes old ProxyBox native state. Type DELETE PROXYBOX to confirm: "
    M_PURGE_NEED_CONFIRM="ERROR: non-interactive --purge-existing-proxybox requires PROXYBOX_CONFIRM_PURGE='DELETE PROXYBOX'"
    M_APT_INSTALLING="==> installing system packages..."
    M_PY311_INSTALLING="==> installing and verifying Python 3.11..."
    M_PY311_FAIL="ERROR: could not install a working Python 3.11"
    M_SINGBOX_DOWNLOAD="==> installing sing-box..."
    M_SINGBOX_VERSION="    sing-box: %s"
    M_GEN_KEYPAIR="==> generating Reality keypair + Hy2 cert + random SNI..."
    M_VENV_CREATE="==> creating Python venv..."
    M_INSTALL_DEPS="==> installing ProxyBox deps..."
    M_GEN_CONFIG="==> generating ProxyBox config..."
    M_START_SERVICES="==> starting services..."
    M_BOOTSTRAP_DEVICE="==> auto-creating first device (%s)..."
    M_BOOTSTRAP_SKIP="    skipped first-device auto-create (PROXYBOX_FIRST_DEVICE is empty)"
    M_BOOTSTRAP_OK="    device created: sub_token=%s"
    M_BOOTSTRAP_FAIL="    [warn] first-device auto-create failed, create one manually from admin UI later"
    M_DONE_HEADER="ProxyBox installed"
    M_DONE_SUB="save the credentials below, then open the login URL"
    M_SECTION_LOGIN_TITLE="🛡 admin login credentials"
    M_SECTION_LOGIN_HINT="must save — recovery needs SSH access to admin.password + config.yaml"
    M_LOGIN_URL_LABEL="login URL"
    M_LOGIN_USER_LABEL="username"
    M_LOGIN_PASS_LABEL="password"
    M_SECTION_SUBS_TITLE="📲 subscription URLs"
    M_SECTION_SUBS_HINT="use [SR rules] for Shadowrocket; [Clash] for Stash/Clash clients"
    M_SUB_DEFAULT_TAG="[generic]"
    M_SUB_DEFAULT_DESC="sing-box · Hiddify · dual-protocol nodes"
    M_SUB_CLASH_TAG="[Clash]"
    M_SUB_CLASH_DESC="Stash · Clash for iOS · Clash Verge"
    M_SUB_SR_YAML_TAG="[SR rules]"
    M_SUB_SR_YAML_DESC="Shadowrocket subscription · nodes + rules"
    M_SUB_MERLIN_TAG="[router]"
    M_SUB_MERLIN_DESC="AsusWRT-Merlin · Clash transparent proxy"
    M_SECTION_SERVICES_TITLE="services"
    M_SECTION_ADVANCED_TITLE="advanced — enable later if needed"
    M_ADV_PASSKEY="passkey   set features.passkey=true + passkey.rp_id/origin in config.yaml + Caddy/TLS"
    M_ADV_BOT="TG bot    fill /etc/proxybox/bot.env then systemctl enable --now proxybox-bot"
    M_ADV_TLS="HTTPS     install Caddy + Let's Encrypt in front of 8080 for production"
    M_FOOTER_TIP="credentials recovery: username/login_path in %s/config.yaml; password in %s/admin.password (0400)"
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
    C_RED=$'\033[1;31m'    # bold red — user-must-save credentials
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
: "${PYTHON_BIN:=python3.11}"

# ─── privilege: install needs root; auto-escalate when safe ────────
if [ "$(id -u)" != "0" ]; then
    if command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
        echo "$M_ESCALATE"
        sudo_env=(
            PROXYBOX_LANG="$LANG_CHOICE" \
            PROXYBOX_DIR="$PROXYBOX_DIR" \
            CONFIG_DIR="$CONFIG_DIR" \
            DATA_DIR="$DATA_DIR" \
            LOG_DIR="$LOG_DIR" \
            SUB_DIR="$SUB_DIR" \
            SINGBOX_DIR="$SINGBOX_DIR" \
            PYTHON_BIN="$PYTHON_BIN"
        )
        [ "${PROXYBOX_INSTALL_MODE+x}" = x ] && sudo_env+=(PROXYBOX_INSTALL_MODE="$PROXYBOX_INSTALL_MODE")
        [ "${PROXYBOX_FRESH+x}" = x ] && sudo_env+=(PROXYBOX_FRESH="$PROXYBOX_FRESH")
        [ "${PROXYBOX_PURGE_EXISTING_PROXYBOX+x}" = x ] && sudo_env+=(PROXYBOX_PURGE_EXISTING_PROXYBOX="$PROXYBOX_PURGE_EXISTING_PROXYBOX")
        [ "${PROXYBOX_CONFIRM_PURGE+x}" = x ] && sudo_env+=(PROXYBOX_CONFIRM_PURGE="$PROXYBOX_CONFIRM_PURGE")
        [ "${PROXYBOX_FIRST_DEVICE+x}" = x ] && sudo_env+=(PROXYBOX_FIRST_DEVICE="$PROXYBOX_FIRST_DEVICE")
        [ "${PROXYBOX_LOCAL_USERNAME+x}" = x ] && sudo_env+=(PROXYBOX_LOCAL_USERNAME="$PROXYBOX_LOCAL_USERNAME")
        exec sudo env "${sudo_env[@]}" bash "$0" "${ORIG_ARGS[@]}"
    fi
    echo "$M_NEED_ROOT" >&2
    exit 1
fi

# ─── sentinel: this looks like a ProxyBox checkout ─────────────────
if [ ! -f "$PROXYBOX_DIR/pyproject.toml" ]; then
    printf "$M_NOT_PROXYBOX_DIR\n" "$PROXYBOX_DIR" >&2
    printf "$M_EXPECT_PYPROJECT\n" >&2
    exit 1
fi

cleanup_legacy_fail2ban_jail_local() {
    local jail="/etc/fail2ban/jail.local"
    [ -f "$jail" ] || return 0
    grep -q '^# ProxyBox manual ban jail' "$jail" 2>/dev/null || return 0

    local tmp
    tmp=$(mktemp "${TMPDIR:-/tmp}/proxybox-jail-local.XXXXXX")
    awk '
        /^# ProxyBox manual ban jail/ { skip = 1; next }
        skip && /^\[/ && $0 != "[manual]" { skip = 0; print; next }
        skip { next }
        { print }
    ' "$jail" > "$tmp"
    if ! cmp -s "$tmp" "$jail"; then
        install -m 644 "$tmp" "$jail"
    fi
    rm -f "$tmp"
    if ! grep -q '[^[:space:]]' "$jail" 2>/dev/null; then
        rm -f "$jail"
    fi
}

path_has_entries() {
    [ -d "$1" ] || return 1
    find "$1" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null | grep -q .
}

native_state_exists() {
    for path in \
        "$CONFIG_DIR/config.yaml" \
        "$CONFIG_DIR/admin.password" \
        "$DATA_DIR/traffic.db" \
        "$SINGBOX_DIR/config.json" \
        "$SINGBOX_DIR/key.pem" \
        "$SINGBOX_DIR/cert.pem" \
        /etc/systemd/system/proxybox-admin.service \
        /etc/systemd/system/proxybox-watchdog.service \
        /etc/systemd/system/proxybox-traffic-worker.service \
        /etc/systemd/system/proxybox-bot.service \
        /etc/systemd/system/sing-box.service \
        /etc/fail2ban/jail.d/proxybox.local \
        /etc/fail2ban/jail.d/proxybox-manual.conf; do
        [ -e "$path" ] && return 0
    done
    if [ -f /etc/fail2ban/jail.local ] \
        && grep -q '^# ProxyBox manual ban jail' /etc/fail2ban/jail.local 2>/dev/null; then
        return 0
    fi
    if [ -f /etc/caddy/Caddyfile ] \
        && grep -q '^# ProxyBox HTTPS' /etc/caddy/Caddyfile 2>/dev/null; then
        return 0
    fi
    for dir in "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR" "$SUB_DIR"; do
        path_has_entries "$dir" && return 0
    done
    return 1
}

native_state_belongs_to_current_install() {
    if [ -f "$CONFIG_DIR/config.yaml" ] \
        && grep -Fq "static_dir: $PROXYBOX_DIR/static" "$CONFIG_DIR/config.yaml"; then
        return 0
    fi
    if [ -f /etc/systemd/system/proxybox-admin.service ] \
        && grep -Fq "WorkingDirectory=$PROXYBOX_DIR" /etc/systemd/system/proxybox-admin.service; then
        return 0
    fi
    return 1
}

confirm_purge_existing_proxybox() {
    if [ "${PROXYBOX_CONFIRM_PURGE:-}" = "DELETE PROXYBOX" ]; then
        return 0
    fi
    if [ -t 0 ] && [ -t 1 ]; then
        local answer
        printf "%s" "$M_PURGE_CONFIRM"
        read -r answer
        [ "$answer" = "DELETE PROXYBOX" ] && return 0
    else
        echo "$M_PURGE_NEED_CONFIRM" >&2
        exit 3
    fi
    echo "$M_EXISTING_REFUSE" >&2
    exit 3
}

purge_existing_proxybox() {
    echo "$M_PURGE_CLEAN"

    if command -v systemctl >/dev/null 2>&1; then
        systemctl stop proxybox-watchdog proxybox-bot proxybox-traffic-worker proxybox-admin sing-box >/dev/null 2>&1 || true
        if [ -f /etc/caddy/Caddyfile ] && grep -q '^# ProxyBox HTTPS' /etc/caddy/Caddyfile 2>/dev/null; then
            systemctl stop caddy >/dev/null 2>&1 || true
            systemctl disable caddy >/dev/null 2>&1 || true
            rm -f /etc/caddy/Caddyfile
        fi
    fi

    rm -f \
        /etc/systemd/system/proxybox-admin.service \
        /etc/systemd/system/proxybox-watchdog.service \
        /etc/systemd/system/proxybox-traffic-worker.service \
        /etc/systemd/system/proxybox-bot.service \
        /etc/systemd/system/sing-box.service
    systemctl daemon-reload >/dev/null 2>&1 || true

    rm -rf "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR" "$SUB_DIR"
    rm -f "$SINGBOX_DIR/config.json" "$SINGBOX_DIR/key.pem" "$SINGBOX_DIR/cert.pem"
    rmdir "$SINGBOX_DIR" 2>/dev/null || true

    rm -f /etc/fail2ban/jail.d/proxybox.local /etc/fail2ban/jail.d/proxybox-manual.conf
    cleanup_legacy_fail2ban_jail_local

    echo "$M_PURGE_DONE"
}

if native_state_exists; then
    if [ "$PURGE_MODE" = "1" ]; then
        confirm_purge_existing_proxybox
        purge_existing_proxybox
    elif [ "$FRESH_MODE" = "1" ] || ! native_state_belongs_to_current_install; then
        echo "$M_EXISTING_REFUSE" >&2
        exit 3
    fi
fi

# ─── pre-flight: defer to check-prereqs.sh ─────────────────────────
if [ "${PROXYBOX_SKIP_PREREQ:-0}" != "1" ]; then
    if ! bash "$PROXYBOX_DIR/deploy/check-prereqs.sh" --install --lang "$LANG_CHOICE"; then
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
if [ "$PURGE_MODE" = "1" ]; then
    printf "$M_INSTALLER_MODE\n" "$M_MODE_PURGE"
elif [ "$FRESH_MODE" = "1" ]; then
    printf "$M_INSTALLER_MODE\n" "$M_MODE_FRESH"
else
    printf "$M_INSTALLER_MODE\n" "$M_MODE_REUSE"
fi

ensure_python311_repo() {
    if apt-cache policy python3.11 2>/dev/null | awk 'BEGIN { ok = 1 } /Candidate:/ { ok = ($2 == "(none)") ? 1 : 0 } END { exit ok }'; then
        return 0
    fi

    . /etc/os-release
    if [ "${ID:-}" = "ubuntu" ]; then
        apt-get -y install software-properties-common ca-certificates gnupg >/dev/null
        add-apt-repository -y ppa:deadsnakes/ppa >/dev/null
        apt-get -y update >/dev/null
    fi

    apt-cache policy python3.11 2>/dev/null | awk 'BEGIN { ok = 1 } /Candidate:/ { ok = ($2 == "(none)") ? 1 : 0 } END { exit ok }'
}

ensure_python311() {
    echo "$M_PY311_INSTALLING"
    apt-get -y update >/dev/null
    ensure_python311_repo || { echo "$M_PY311_FAIL" >&2; exit 1; }
    apt-get -y install python3.11 python3.11-venv >/dev/null
    if ! "$PYTHON_BIN" -c 'import sys, venv; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)' >/dev/null 2>&1; then
        echo "$M_PY311_FAIL" >&2
        exit 1
    fi
}

# ─── 1. system packages ────────────────────────────────────────────
echo "$M_APT_INSTALLING"
ensure_python311
apt-get -y update >/dev/null
apt-get -y install \
    curl sqlite3 openssl fail2ban \
    >/dev/null

# ─── 2. directories ────────────────────────────────────────────────
mkdir -p "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR" "$SUB_DIR" "$SINGBOX_DIR"
chmod 700 "$CONFIG_DIR" "$DATA_DIR"

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
install -m 644 /dev/stdin /etc/systemd/system/sing-box.service <<'UNIT'
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

# ─── 5. sing-box config (only generate if missing) ────────────────
if [ ! -f "$SINGBOX_DIR/config.json" ]; then
    echo "$M_GEN_KEYPAIR"
    KEYPAIR=$(sing-box generate reality-keypair)
    PRIVATE_KEY=$(printf '%s\n' "$KEYPAIR" | awk '/PrivateKey/{print $2}')
    SHORT_ID=$(openssl rand -hex 8)

    SNI_CANDIDATES=(www.microsoft.com www.apple.com www.cloudflare.com www.amazon.com)
    SNI="${SNI_CANDIDATES[$RANDOM % 4]}"

    openssl req -x509 -newkey rsa:2048 -nodes -days 3650 \
        -keyout "$SINGBOX_DIR/key.pem" -out "$SINGBOX_DIR/cert.pem" \
        -subj "/CN=$SNI" 2>/dev/null
    chmod 600 "$SINGBOX_DIR/key.pem"

    install -m 600 /dev/stdin "$SINGBOX_DIR/config.json" <<JSON
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
if [ -x .venv/bin/python ] && ! .venv/bin/python -c 'import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)' >/dev/null 2>&1; then
    rm -rf .venv
fi
if [ ! -d .venv ]; then
    echo "$M_VENV_CREATE"
    "$PYTHON_BIN" -m venv .venv
fi
echo "$M_INSTALL_DEPS"
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -e .

# ─── 7. ProxyBox config.yaml ───────────────────────────────────────
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    echo "$M_GEN_CONFIG"
    ADMIN_TOKEN=$(.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(24))")
    # Password = 16 alnum chars — readable / typeable but ~95 bits entropy.
    ADMIN_PASSWORD=$(.venv/bin/python -c "import secrets, string; alpha = string.ascii_letters + string.digits; print(''.join(secrets.choice(alpha) for _ in range(16)))")
    # login_path = 12 alnum chars (~71 bits) — makes /login a 404 so bots
    # can't even find the form to attempt password brute-force.
    ADMIN_LOGIN_PATH=$(.venv/bin/python -c "import secrets, string; alpha = string.ascii_letters + string.digits; print(''.join(secrets.choice(alpha) for _ in range(12)))")
    PUBLIC_HOST=$(curl -4 -fsS --max-time 5 https://api4.ipify.org 2>/dev/null \
                 || curl -4 -fsS --max-time 5 https://ipv4.icanhazip.com 2>/dev/null \
                 || echo "")
    # Password lives in /etc/proxybox/admin.password (mode 0400), NOT in
    # config.yaml. Keeps cat config.yaml screenshot-safe and backup-safe
    # while still being one ``cat`` away for password recovery.
    printf '%s' "$ADMIN_PASSWORD" | install -m 400 /dev/stdin "$CONFIG_DIR/admin.password"
    chmod 0400 "$CONFIG_DIR/admin.password"
    install -m 600 /dev/stdin "$CONFIG_DIR/config.yaml" <<YAML
admin:
  token: "$ADMIN_TOKEN"
  username: "admin"
  login_path: "$ADMIN_LOGIN_PATH"
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
    - proxybox-watchdog
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
  # URL-token-only admin API access is disabled from first boot. install.sh
  # logs in with the generated username/password and uses that session cookie
  # for its one-shot first-device bootstrap.
  url_token_bypass: false
YAML
    chmod 600 "$CONFIG_DIR/config.yaml"
fi

# ─── 8. fail2ban [manual] jail ─────────────────────────────────────
cleanup_legacy_fail2ban_jail_local
mkdir -p /etc/fail2ban/jail.d
install -m 644 /dev/stdin /etc/fail2ban/jail.d/proxybox.local <<'JAIL'
# ProxyBox managed fail2ban config.
# systemd backend avoids /var/log/auth.log dependency on minimal images.
[DEFAULT]
backend = systemd

# Some distro packages enable sshd by default with file-log backends. Force
# systemd so fail2ban does not fail on images without /var/log/auth.log.
[sshd]
backend = systemd

# Explicit manual ban jail used by ProxyBox /action/block.
[manual]
enabled  = true
backend  = systemd
filter   = sshd
action   = iptables-allports[name=manual]
bantime  = -1
findtime = 60
maxretry = 99999
JAIL

# ─── 9. ProxyBox admin systemd unit ────────────────────────────────
install -m 644 /dev/stdin /etc/systemd/system/proxybox-admin.service <<UNIT
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

# ─── 10. ProxyBox watchdog systemd unit ────────────────────────────
install -m 644 /dev/stdin /etc/systemd/system/proxybox-watchdog.service <<UNIT
[Unit]
Description=ProxyBox service and port watchdog
After=network.target sing-box.service proxybox-admin.service proxybox-traffic-worker.service
Wants=sing-box.service proxybox-admin.service proxybox-traffic-worker.service

[Service]
Type=simple
WorkingDirectory=$PROXYBOX_DIR
Environment=PROXYBOX_CONFIG=$CONFIG_DIR/config.yaml
ExecStart=$PROXYBOX_DIR/.venv/bin/python -m app.services.watchdog
Restart=always
RestartSec=5s
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
UNIT

# ─── 11. other systemd units (worker + bot) ────────────────────────
for unit in proxybox-traffic-worker.service proxybox-bot.service; do
    src="$PROXYBOX_DIR/deploy/systemd/$unit"
    dst="/etc/systemd/system/$unit"
    if [ -f "$src" ]; then
        install -m 644 "$src" "$dst"
    fi
done
systemctl daemon-reload

# ─── 12. enable + start core services ──────────────────────────────
echo "$M_START_SERVICES"
for svc in fail2ban sing-box proxybox-admin proxybox-traffic-worker proxybox-watchdog; do
    systemctl enable "$svc" >/dev/null 2>&1 || true
    systemctl restart "$svc" >/dev/null 2>&1 || true
done
sleep 3

# ─── 13. read token + host ─────────────────────────────────────────
ADMIN_TOKEN=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('$CONFIG_DIR/config.yaml'))['admin']['token'])")
PUBLIC_HOST=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('$CONFIG_DIR/config.yaml'))['server']['public_host'])")
ADMIN_BASE="http://${PUBLIC_HOST:-<your-vps-ip>}:8080"
ADMIN_LOCAL="http://127.0.0.1:8080"
ADMIN_USER=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('$CONFIG_DIR/config.yaml'))['admin'].get('username', 'admin'))")
# Password lives in its own 0400 file, not in YAML — see app/services/admin_password.py.
ADMIN_PASSWORD=$(cat "$CONFIG_DIR/admin.password" 2>/dev/null || true)
ADMIN_LOGIN_PATH=$(.venv/bin/python -c "import yaml; print(yaml.safe_load(open('$CONFIG_DIR/config.yaml'))['admin'].get('login_path', ''))")
if [ -n "$ADMIN_LOGIN_PATH" ]; then
    LOGIN_PATH="/login/$ADMIN_LOGIN_PATH"
else
    LOGIN_PATH="/login"
fi

# ─── 14. auto-create first device (one-shot UX) ────────────────────
# Wait for proxybox-admin to be reachable on localhost (sleep 3 above
# is usually enough on a real VPS, but be defensive on slow hosts).
resolve_first_device_name() {
    local raw
    if [ "${PROXYBOX_FIRST_DEVICE+x}" = x ]; then
        raw="$PROXYBOX_FIRST_DEVICE"
    else
        .venv/bin/python -c "import secrets, string; print(''.join(secrets.choice(string.ascii_lowercase) for _ in range(5)))"
        return
    fi

    case "$raw" in
        local-user|@local-user|auto-user)
            raw="${PROXYBOX_LOCAL_USERNAME:-${SUDO_USER:-${USER:-${LOGNAME:-}}}}"
            ;;
    esac

    PROXYBOX_RAW_DEVICE="$raw" .venv/bin/python -c "
import os, re
raw = os.environ.get('PROXYBOX_RAW_DEVICE', '').strip()
if not raw:
    print('')
    raise SystemExit
name = re.sub(r'[^A-Za-z0-9_-]+', '-', raw).strip('-_')
if not name:
    print('')
    raise SystemExit
if len(name) < 3:
    name = f'device-{name}'
name = name[:32].strip('-_')
if len(name) < 3:
    name = 'device'
print(name)
"
}

DEFAULT_DEVICE_NAME=$(resolve_first_device_name)
SUB_TOKEN=""
for _ in 1 2 3 4 5 6 7 8 9 10; do
    if curl -s -o /dev/null -w "%{http_code}" "$ADMIN_LOCAL$LOGIN_PATH" 2>/dev/null | grep -q '^200$'; then
        break
    fi
    sleep 1
done

COOKIE_JAR=$(mktemp "${TMPDIR:-/tmp}/proxybox-install-cookie.XXXXXX")
cleanup_cookie() { rm -f "$COOKIE_JAR"; }
trap cleanup_cookie EXIT

LOGIN_OK=0
if [ -n "$ADMIN_PASSWORD" ]; then
    if curl -fsS -c "$COOKIE_JAR" -o /dev/null \
        -X POST \
        --data-urlencode "username=$ADMIN_USER" \
        --data-urlencode "password=$ADMIN_PASSWORD" \
        "$ADMIN_LOCAL$LOGIN_PATH" 2>/dev/null; then
        LOGIN_OK=1
    fi
fi

api_get() {
    local path="$1"
    if [ "$LOGIN_OK" = "1" ]; then
        curl -fsS -b "$COOKIE_JAR" "$ADMIN_LOCAL/admin/$ADMIN_TOKEN$path" 2>/dev/null
    else
        curl -fsS "$ADMIN_LOCAL/admin/$ADMIN_TOKEN$path" 2>/dev/null
    fi
}

api_post_json() {
    local path="$1"
    local body="$2"
    if [ "$LOGIN_OK" = "1" ]; then
        curl -fsS -b "$COOKIE_JAR" -X POST \
            -H "Content-Type: application/json" \
            -d "$body" \
            "$ADMIN_LOCAL/admin/$ADMIN_TOKEN$path" 2>/dev/null
    else
        curl -fsS -X POST \
            -H "Content-Type: application/json" \
            -d "$body" \
            "$ADMIN_LOCAL/admin/$ADMIN_TOKEN$path" 2>/dev/null
    fi
}

# Check if device already exists (re-install on a host that already has one)
EXISTING_JSON=$(api_get "/api/devices/list" || true)
EXISTING=$(printf '%s' "$EXISTING_JSON" | .venv/bin/python -c "
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
elif [ -z "$DEFAULT_DEVICE_NAME" ]; then
    echo "$M_BOOTSTRAP_SKIP"
else
    printf "$M_BOOTSTRAP_DEVICE\n" "$DEFAULT_DEVICE_NAME"
    CREATE_BODY=$(DEFAULT_DEVICE_NAME="$DEFAULT_DEVICE_NAME" .venv/bin/python -c "
import json, os
name = os.environ['DEFAULT_DEVICE_NAME']
print(json.dumps({'name': name, 'kind': 'mobile', 'label': name}))
")
    RESPONSE=$(api_post_json "/api/devices/new" "$CREATE_BODY" || true)
    SUB_TOKEN=$(printf '%s' "$RESPONSE" | .venv/bin/python -c "
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

# ─── 15. lock down: disable URL-token bypass + restart admin ───────
# Enforce the documented default after bootstrap and after any re-run from an
# older install: /admin/{token}/ requires a /login session cookie. Restart so
# the @lru_cache'd settings reload. ~3s, harmless.
.venv/bin/python -c "
import os, yaml, pathlib
p = pathlib.Path('$CONFIG_DIR/config.yaml')
cfg = yaml.safe_load(p.read_text())
cfg.setdefault('features', {})['url_token_bypass'] = False
tmp = p.with_suffix(p.suffix + '.tmp')
fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True))
os.replace(tmp, p)
p.chmod(0o600)
"
systemctl restart proxybox-admin >/dev/null 2>&1 || true

# Read credentials for the summary block. Read AFTER the lock-down so we
# show the user the actual state of the running config.
if [ -n "$ADMIN_LOGIN_PATH" ]; then
    LOGIN_URL="$ADMIN_BASE/login/$ADMIN_LOGIN_PATH"
else
    LOGIN_URL="$ADMIN_BASE/login"
fi

# ─── 16. summary ───────────────────────────────────────────────────
echo ""
echo ""
printf "%s  %s%s\n" "$C_GREEN_B" "$HR" "$C_RESET"
printf "  %s✅  %s%s\n" "$C_GREEN_B" "$M_DONE_HEADER" "$C_RESET"
printf "      %s%s%s\n" "$C_DIM" "$M_DONE_SUB" "$C_RESET"
printf "%s  %s%s\n" "$C_GREEN_B" "$HR" "$C_RESET"
echo ""

# ── Login credentials — THE primary card, bold + red emphasis ───────
printf "  %s%s%s  %s— %s%s\n" "$C_CYAN_B" "$M_SECTION_LOGIN_TITLE" "$C_RESET" "$C_DIM" "$M_SECTION_LOGIN_HINT" "$C_RESET"
echo ""
printf "      %s%-9s%s %s%s%s\n" "$C_DIM" "$M_LOGIN_URL_LABEL" "$C_RESET" "$C_GREEN_B" "$LOGIN_URL" "$C_RESET"
printf "      %s%-9s%s %s%s%s\n" "$C_DIM" "$M_LOGIN_USER_LABEL" "$C_RESET" "$C_RED" "$ADMIN_USER" "$C_RESET"
printf "      %s%-9s%s %s%s%s\n" "$C_DIM" "$M_LOGIN_PASS_LABEL" "$C_RESET" "$C_RED" "$ADMIN_PASSWORD" "$C_RESET"
echo ""

# ── Subscription URLs block ─────────────────────────────────────────
if [ -n "$SUB_TOKEN" ]; then
    SUB_BASE="$ADMIN_BASE/api/sub/$SUB_TOKEN"
    printf "  %s%s%s  %s— %s%s\n" "$C_CYAN_B" "$M_SECTION_SUBS_TITLE" "$C_RESET" "$C_DIM" "$M_SECTION_SUBS_HINT" "$C_RESET"
    echo ""

    # Recommended — yellow ✦ + bold tag + bold green URL
    printf "    %s✦ %s%s  %s%s%s\n" \
        "$C_YELLOW_B" "$M_SUB_SR_YAML_TAG" "$C_RESET" "$C_BOLD" "$M_SUB_SR_YAML_DESC" "$C_RESET"
    printf "      %s%s/shadowrocket.yaml%s\n" "$C_GREEN_B" "$SUB_BASE" "$C_RESET"
    echo ""

    # Other formats — same tag-bold + URL-green pattern, no ✦, no bold on URL
    for entry in \
        "$M_SUB_CLASH_TAG|$M_SUB_CLASH_DESC|/clash.yaml" \
        "$M_SUB_MERLIN_TAG|$M_SUB_MERLIN_DESC|/merlin.yaml" \
        "$M_SUB_DEFAULT_TAG|$M_SUB_DEFAULT_DESC|"; do
        IFS='|' read -r tag desc suffix <<< "$entry"
        printf "      %s%s%s  %s\n" "$C_BOLD" "$tag" "$C_RESET" "$desc"
        printf "      %s%s%s%s\n" "$C_GREEN" "$SUB_BASE" "$suffix" "$C_RESET"
        echo ""
    done
fi

# ── Services block — green ✓ for active, red ✗ for inactive ─────────
printf "  %s%s%s\n" "$C_CYAN_B" "$M_SECTION_SERVICES_TITLE" "$C_RESET"
echo ""
for svc in sing-box proxybox-admin proxybox-traffic-worker proxybox-watchdog fail2ban; do
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
printf "$M_FOOTER_TIP" "$CONFIG_DIR" "$CONFIG_DIR"
printf "%s\n" "$C_RESET"
echo ""
