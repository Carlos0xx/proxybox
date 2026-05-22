#!/usr/bin/env bash
# deploy/check-prereqs.sh — ProxyBox pre-install requirements check
#
# Usage:
#   bash deploy/check-prereqs.sh                 check only; exit 0 if ready
#   bash deploy/check-prereqs.sh --install       also apt-install missing tools
#   bash deploy/check-prereqs.sh --lang en|zh    force language (default: auto from $LANG)
#
# Exit codes:
#   0  all required checks passed (warnings OK)
#   1  one or more blocking failures
#   2  bad invocation
#
# This script is invoked by install.sh before host-level provisioning, and
# by the deploy skill after the repo has been cloned into a new directory.
# Designed to give the operator a complete go/no-go view in <5 seconds.

set -uo pipefail

INSTALL_MODE=false
LANG_CHOICE="${PROXYBOX_LANG:-auto}"

while [ $# -gt 0 ]; do
    case "$1" in
        --install)     INSTALL_MODE=true; shift ;;
        --lang)        LANG_CHOICE="${2:-auto}"; shift 2 ;;
        --lang=*)      LANG_CHOICE="${1#*=}"; shift ;;
        -h|--help)     sed -n '2,16p' "$0"; exit 0 ;;
        *)             echo "unknown arg: $1" >&2; exit 2 ;;
    esac
done

# Auto-detect from $LANG if not explicitly set
if [ "$LANG_CHOICE" = "auto" ]; then
    case "${LANG:-}" in
        zh*|ZH*) LANG_CHOICE=zh ;;
        *)       LANG_CHOICE=en ;;
    esac
fi

case "$LANG_CHOICE" in
    en|zh) ;;
    *) echo "unsupported lang: $LANG_CHOICE (use 'en' or 'zh')" >&2; exit 2 ;;
esac

# ─── i18n strings ─────────────────────────────────────────────
if [ "$LANG_CHOICE" = "zh" ]; then
    M_HEADER="==> ProxyBox 环境检查"
    M_OS="[1/9] 操作系统"
    M_OS_UNREADABLE="无法读取 /etc/os-release, 无法识别系统"
    M_OS_SUPPORTED="OS = %s (支持)"
    M_OS_UNSUPPORTED="OS = %s — 仅支持 debian/ubuntu (其他系统欢迎 PR)"
    M_ARCH="[2/9] CPU 架构"
    M_ARCH_OK="架构 = %s (%s)"
    M_ARCH_UNSUPPORTED="架构 = %s — 仅支持 x86_64 / aarch64"
    M_PRIV="[3/9] 权限"
    M_PRIV_ROOT="以 root 运行"
    M_PRIV_SUDO="passwordless sudo 可用"
    M_PRIV_NONE="不是 root, sudo 不可用或需要密码"
    M_MEM="[4/9] 内存"
    M_MEM_OK="总内存 = %s MB (≥ 512 MB)"
    M_MEM_WARN="总内存 = %s MB — 能跑但偏紧, 推荐 ≥ 512 MB"
    M_MEM_FAIL="总内存 = %s MB — 需 ≥ 256 MB (推荐 ≥ 512 MB)"
    M_DISK="[5/9] / 分区空闲磁盘"
    M_DISK_FAIL_DF="df 失败, 无法读取 / 的空闲磁盘"
    M_DISK_OK="/ 空闲 = %sG (≥ 5G)"
    M_DISK_WARN="/ 空闲 = %sG — 能跑但偏紧, 推荐 ≥ 5G"
    M_DISK_FAIL="/ 空闲 = %sG — 需 ≥ 2G (sing-box + venv + traffic.db)"
    M_NET="[6/9] 出站网络"
    M_NET_GH_OK="github.com 可达 (sing-box 二进制下载会成功)"
    M_NET_GH_FAIL="github.com 不可达 — 无法下载 sing-box"
    M_NET_IP_OK="IPv4 公网 IP 服务可达 (公网 IP 自动检测会工作)"
    M_NET_IP_WARN="IPv4 公网 IP 服务不可达 — install.sh 会留空 server.public_host"
    M_NET_CURL_WARN="curl 未安装 — 下方 apt 步骤会装上"
    M_SYSD="[7/9] 服务管理器"
    M_SYSD_OK="systemd 存在 (systemctl 找到)"
    M_SYSD_FAIL="未检测到 systemd — ProxyBox 需要 systemd 管理服务"
    M_PORTS="[8/9] 必须空闲的端口"
    M_PORT_FREE="%s/%s 空闲 (%s)"
    M_PORT_OURS="%s/%s 已被 ProxyBox 服务占用 (%s) — 重装 OK"
    M_PORT_HELD="%s/%s 被外部进程 %s 占用 (用于 %s)"
    M_PORTS_NOTE="(每设备端口 11001-11050 TCP + 21001-21050 UDP 由 /api/devices/new 按需分配)"
    M_APT="[9/9] apt 可装的运行依赖"
    M_APT_OK="%s 已装"
    M_APT_MISSING="%s 缺失"
    M_APT_INSTALL_FAIL="apt 依赖安装失败"
    M_SB_HEADER="[额外] sing-box 二进制"
    M_SB_PRESENT="sing-box 已装: %s"
    M_SB_MISSING="sing-box 不存在 (install.sh 会从 GitHub 拉最新)"
    M_FAIL_SUMMARY="✗ %d 项阻塞失败 — 修复后再跑 install.sh"
    M_WARN_SUMMARY="⚠ %d 项警告 — 可以装, 见上方注解"
    M_PASS_SUMMARY="✓ 全部检查通过 — 可以跑 install.sh 了"
    M_INSTALL_DOING="--install 模式 — 现在安装缺失的 apt 包:"
    M_INSTALL_DONE="✓ apt 依赖装好, 重跑本脚本复验后再跑 install.sh"
    M_INSTALL_HINT="自动装缺失包请重跑:"
    M_INSTALL_HINT2="(install.sh 自己也会装, 但前置装一下更干净)"
    PORT_DESC_ADMIN="admin HTTP"
    PORT_DESC_VLESS="VLESS Reality 模板"
    PORT_DESC_HY2="Hysteria2 模板"
else
    M_HEADER="==> ProxyBox prerequisite check"
    M_OS="[1/9] Operating system"
    M_OS_UNREADABLE="/etc/os-release unreadable; cannot identify OS"
    M_OS_SUPPORTED="OS = %s (supported)"
    M_OS_UNSUPPORTED="OS = %s — only debian/ubuntu supported (PRs welcome for others)"
    M_ARCH="[2/9] CPU architecture"
    M_ARCH_OK="arch = %s (%s)"
    M_ARCH_UNSUPPORTED="arch = %s — only x86_64 / aarch64 supported"
    M_PRIV="[3/9] Privilege"
    M_PRIV_ROOT="running as root"
    M_PRIV_SUDO="passwordless sudo available"
    M_PRIV_NONE="not root, and sudo unavailable or needs a password"
    M_MEM="[4/9] Memory"
    M_MEM_OK="total RAM = %s MB (≥ 512 MB)"
    M_MEM_WARN="total RAM = %s MB — works but tight; 512 MB recommended"
    M_MEM_FAIL="total RAM = %s MB — need ≥ 256 MB (recommend ≥ 512 MB)"
    M_DISK="[5/9] Free disk on /"
    M_DISK_FAIL_DF="df failed; cannot read free disk on /"
    M_DISK_OK="free on / = %sG (≥ 5G)"
    M_DISK_WARN="free on / = %sG — works but tight; 5G recommended"
    M_DISK_FAIL="free on / = %sG — need ≥ 2G for sing-box + venv + traffic.db"
    M_NET="[6/9] Outbound network"
    M_NET_GH_OK="github.com reachable (sing-box binary download will work)"
    M_NET_GH_FAIL="github.com unreachable — cannot download sing-box"
    M_NET_IP_OK="IPv4 public-IP service reachable (public IP auto-detection will work)"
    M_NET_IP_WARN="IPv4 public-IP service unreachable — install.sh will leave server.public_host blank"
    M_NET_CURL_WARN="curl not installed — will install in apt step below"
    M_SYSD="[7/9] Service manager"
    M_SYSD_OK="systemd present (systemctl found)"
    M_SYSD_FAIL="systemd not detected — ProxyBox requires systemd for service management"
    M_PORTS="[8/9] Required ports free"
    M_PORT_FREE="%s/%s free (%s)"
    M_PORT_OURS="%s/%s already held by ProxyBox service (%s) — re-install OK"
    M_PORT_HELD="%s/%s held by external process %s (needed for %s)"
    M_PORTS_NOTE="(per-device ports 11001-11050 TCP + 21001-21050 UDP are allocated by /api/devices/new on demand)"
    M_APT="[9/9] apt-installable runtime tools"
    M_APT_OK="%s installed"
    M_APT_MISSING="%s missing"
    M_APT_INSTALL_FAIL="apt dependency install failed"
    M_SB_HEADER="[bonus] sing-box binary"
    M_SB_PRESENT="sing-box already installed: %s"
    M_SB_MISSING="sing-box not present (install.sh will download latest from GitHub)"
    M_FAIL_SUMMARY="✗ %d blocking failure(s) — fix these before running install.sh"
    M_WARN_SUMMARY="⚠ %d warning(s) — install can proceed, see notes above"
    M_PASS_SUMMARY="✓ all checks pass — ready to run install.sh"
    M_INSTALL_DOING="--install mode — installing missing apt packages now:"
    M_INSTALL_DONE="✓ apt deps installed; re-run this script to re-verify, then run install.sh"
    M_INSTALL_HINT="to auto-install the missing apt packages, re-run:"
    M_INSTALL_HINT2="(install.sh will install them itself anyway, but doing it up-front is cleaner)"
    PORT_DESC_ADMIN="admin HTTP"
    PORT_DESC_VLESS="VLESS Reality template"
    PORT_DESC_HY2="Hysteria2 template"
fi

FAIL=0
WARN=0
NEEDED_APT=""

red()    { printf "\033[31m%s\033[0m" "$*"; }
green()  { printf "\033[32m%s\033[0m" "$*"; }
yellow() { printf "\033[33m%s\033[0m" "$*"; }

pass()  { printf "  $(green ✓) "; printf -- "$@"; printf "\n"; }
fail()  { printf "  $(red ✗) ";   printf -- "$@"; printf "\n"; FAIL=$((FAIL+1)); }
warn()  { printf "  $(yellow ⚠) ";printf -- "$@"; printf "\n"; WARN=$((WARN+1)); }

python311_candidate_available() {
    apt-cache policy python3.11 2>/dev/null \
        | awk 'BEGIN { ok = 1 } /Candidate:/ { ok = ($2 == "(none)") ? 1 : 0 } END { exit ok }'
}

ensure_python311_repo() {
    if python311_candidate_available; then
        return 0
    fi

    . /etc/os-release
    if [ "${ID:-}" = "ubuntu" ]; then
        apt-get -y install software-properties-common ca-certificates gnupg >/dev/null
        add-apt-repository -y ppa:deadsnakes/ppa >/dev/null
        apt-get -y update >/dev/null
    fi

    python311_candidate_available
}

echo "$M_HEADER"
echo ""

# ─── 1. OS ───────────────────────────────────────────────────
echo "$M_OS"
if [ ! -r /etc/os-release ]; then
    fail "$M_OS_UNREADABLE"
else
    OS_ID=$(awk -F= '/^ID=/{gsub(/"/,"",$2); print $2; exit}' /etc/os-release)
    OS_NAME=$(awk -F= '/^PRETTY_NAME=/{gsub(/"/,"",$2); print $2; exit}' /etc/os-release)
    case "$OS_ID" in
        debian|ubuntu) pass "$M_OS_SUPPORTED" "$OS_NAME" ;;
        *)             fail "$M_OS_UNSUPPORTED" "$OS_ID" ;;
    esac
fi

# ─── 2. Architecture ─────────────────────────────────────────
echo ""
echo "$M_ARCH"
ARCH=$(uname -m)
case "$ARCH" in
    x86_64|amd64)   pass "$M_ARCH_OK" "$ARCH" "linux/amd64" ;;
    aarch64|arm64)  pass "$M_ARCH_OK" "$ARCH" "linux/arm64" ;;
    *)              fail "$M_ARCH_UNSUPPORTED" "$ARCH" ;;
esac

# ─── 3. Privilege ────────────────────────────────────────────
echo ""
echo "$M_PRIV"
if [ "$(id -u)" = "0" ]; then
    pass "$M_PRIV_ROOT"
elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    pass "$M_PRIV_SUDO"
else
    fail "$M_PRIV_NONE"
fi

# ─── 4. Memory ───────────────────────────────────────────────
echo ""
echo "$M_MEM"
TOTAL_MB=$(awk '/^MemTotal:/{print int($2/1024); exit}' /proc/meminfo 2>/dev/null || echo 0)
if [ "$TOTAL_MB" -ge 512 ]; then
    pass "$M_MEM_OK" "$TOTAL_MB"
elif [ "$TOTAL_MB" -ge 256 ]; then
    warn "$M_MEM_WARN" "$TOTAL_MB"
else
    fail "$M_MEM_FAIL" "$TOTAL_MB"
fi

# ─── 5. Disk ─────────────────────────────────────────────────
echo ""
echo "$M_DISK"
AVAIL_GB=$(df -BG / 2>/dev/null | awk 'NR==2{sub(/G$/,"",$4); print $4; exit}')
if [ -z "$AVAIL_GB" ]; then
    fail "$M_DISK_FAIL_DF"
elif [ "$AVAIL_GB" -ge 5 ]; then
    pass "$M_DISK_OK" "$AVAIL_GB"
elif [ "$AVAIL_GB" -ge 2 ]; then
    warn "$M_DISK_WARN" "$AVAIL_GB"
else
    fail "$M_DISK_FAIL" "$AVAIL_GB"
fi

# ─── 6. Network ──────────────────────────────────────────────
echo ""
echo "$M_NET"
if command -v curl >/dev/null 2>&1; then
    if curl -fsSL --max-time 5 -o /dev/null https://github.com/SagerNet/sing-box; then
        pass "$M_NET_GH_OK"
    else
        fail "$M_NET_GH_FAIL"
    fi
    if curl -4 -fsSL --max-time 5 -o /dev/null https://api4.ipify.org \
        || curl -4 -fsSL --max-time 5 -o /dev/null https://ipv4.icanhazip.com; then
        pass "$M_NET_IP_OK"
    else
        warn "$M_NET_IP_WARN"
    fi
else
    warn "$M_NET_CURL_WARN"
fi

# ─── 7. systemd ──────────────────────────────────────────────
echo ""
echo "$M_SYSD"
if [ -d /run/systemd/system ] && command -v systemctl >/dev/null 2>&1; then
    pass "$M_SYSD_OK"
else
    fail "$M_SYSD_FAIL"
fi

# ─── 8. Ports ────────────────────────────────────────────────
echo ""
echo "$M_PORTS"
port_holder() {
    local port="$1"; local proto="$2"
    local flag="-tlnp"
    [ "$proto" = "udp" ] && flag="-ulnp"
    ss $flag 2>/dev/null | awk -v p=":$port" '$4 ~ p"$" || $4 ~ p" " {print $NF; exit}'
}
check_port() {
    local port="$1"; local proto="$2"; local desc="$3"
    local holder
    holder=$(port_holder "$port" "$proto")
    if [ -z "$holder" ]; then
        pass "$M_PORT_FREE" "$proto" "$port" "$desc"
    elif echo "$holder" | grep -qE '(sing-box|uvicorn|proxybox)'; then
        pass "$M_PORT_OURS" "$proto" "$port" "$holder"
    else
        fail "$M_PORT_HELD" "$proto" "$port" "$holder" "$desc"
    fi
}
check_port 8080  tcp "$PORT_DESC_ADMIN"
check_port 11000 tcp "$PORT_DESC_VLESS"
check_port 21000 udp "$PORT_DESC_HY2"
echo "  $M_PORTS_NOTE"

# ─── 9. apt deps ─────────────────────────────────────────────
echo ""
echo "$M_APT"
DEPS="python3.11 python3.11-venv curl sqlite3 openssl fail2ban"
for pkg in $DEPS; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
        pass "$M_APT_OK" "$pkg"
    else
        warn "$M_APT_MISSING" "$pkg"
        NEEDED_APT="$NEEDED_APT $pkg"
    fi
done

# ─── sing-box presence ───────────────────────────────────────
echo ""
echo "$M_SB_HEADER"
if command -v sing-box >/dev/null 2>&1; then
    pass "$M_SB_PRESENT" "$(sing-box version 2>/dev/null | head -1)"
else
    warn "$M_SB_MISSING"
fi

# ─── summary ─────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
    printf "  $(red "$M_FAIL_SUMMARY")\n" "$FAIL"
    exit 1
fi

if [ "$WARN" -gt 0 ]; then
    printf "  $(yellow "$M_WARN_SUMMARY")\n" "$WARN"
else
    printf "  $(green "$M_PASS_SUMMARY")\n"
fi

if [ -n "$NEEDED_APT" ]; then
    echo ""
    if [ "$INSTALL_MODE" = "true" ]; then
        echo "  $M_INSTALL_DOING"
        echo "    ↳$NEEDED_APT"
        apt-get -y update >/dev/null 2>&1
        if echo "$NEEDED_APT" | grep -q 'python3\.11'; then
            if ! ensure_python311_repo; then
                printf "  $(red "$M_APT_INSTALL_FAIL")\n"
                exit 1
            fi
        fi
        # shellcheck disable=SC2086
        if ! apt-get -y install $NEEDED_APT 2>&1 | tail -3; then
            printf "  $(red "$M_APT_INSTALL_FAIL")\n"
            exit 1
        fi
        printf "  $(green "$M_INSTALL_DONE")\n"
    else
        echo "  $M_INSTALL_HINT"
        printf "    $(yellow "sudo bash %s --install --lang %s")\n" "$(basename "$0")" "$LANG_CHOICE"
        echo "  $M_INSTALL_HINT2"
    fi
fi

exit 0
