#!/usr/bin/env bash
# deploy/check-prereqs.sh — ProxyBox pre-install requirements check
#
# Usage:
#   bash deploy/check-prereqs.sh            # check only; exit 0 if ready
#   bash deploy/check-prereqs.sh --install  # also apt-install missing tools
#
# Exit codes:
#   0  all required checks passed (warnings OK)
#   1  one or more blocking failures
#   2  bad invocation
#
# This script is invoked by install.sh before any destructive operation, and
# referenced by the Claude Code deploy skill as Step 1. Designed to give the
# operator a complete go/no-go view in <5 seconds.

set -uo pipefail

INSTALL_MODE=false
case "${1:-}" in
    "")           ;;
    --install)    INSTALL_MODE=true ;;
    -h|--help)
        sed -n '2,16p' "$0"
        exit 0
        ;;
    *)
        echo "unknown arg: $1" >&2
        exit 2
        ;;
esac

FAIL=0
WARN=0
NEEDED_APT=""

red()   { printf "\033[31m%s\033[0m" "$*"; }
green() { printf "\033[32m%s\033[0m" "$*"; }
yellow() { printf "\033[33m%s\033[0m" "$*"; }

pass()  { printf "  $(green ✓) %s\n" "$*"; }
fail()  { printf "  $(red ✗) %s\n" "$*"; FAIL=$((FAIL+1)); }
warn()  { printf "  $(yellow ⚠) %s\n" "$*"; WARN=$((WARN+1)); }

echo "==> ProxyBox prerequisite check"
echo ""

# ─── 1. OS ───────────────────────────────────────────────────
echo "[1/9] Operating system"
if [ ! -r /etc/os-release ]; then
    fail "/etc/os-release unreadable; cannot identify OS"
else
    OS_ID=$(awk -F= '/^ID=/{gsub(/"/,"",$2); print $2; exit}' /etc/os-release)
    OS_NAME=$(awk -F= '/^PRETTY_NAME=/{gsub(/"/,"",$2); print $2; exit}' /etc/os-release)
    case "$OS_ID" in
        debian|ubuntu) pass "OS = $OS_NAME (supported)" ;;
        *)             fail "OS = $OS_ID — only debian/ubuntu supported (PRs welcome for others)" ;;
    esac
fi

# ─── 2. Architecture ─────────────────────────────────────────
echo ""
echo "[2/9] CPU architecture"
ARCH=$(uname -m)
case "$ARCH" in
    x86_64|amd64)   pass "arch = $ARCH (linux/amd64)" ;;
    aarch64|arm64)  pass "arch = $ARCH (linux/arm64)" ;;
    *)              fail "arch = $ARCH — only x86_64 / aarch64 supported" ;;
esac

# ─── 3. Privilege ────────────────────────────────────────────
echo ""
echo "[3/9] Privilege"
if [ "$(id -u)" = "0" ]; then
    pass "running as root"
elif command -v sudo >/dev/null 2>&1 && sudo -n true 2>/dev/null; then
    pass "passwordless sudo available"
else
    fail "not root, and sudo unavailable or needs a password"
fi

# ─── 4. Memory ───────────────────────────────────────────────
echo ""
echo "[4/9] Memory"
TOTAL_MB=$(awk '/^MemTotal:/{print int($2/1024); exit}' /proc/meminfo 2>/dev/null || echo 0)
if [ "$TOTAL_MB" -ge 512 ]; then
    pass "total RAM = ${TOTAL_MB} MB (≥ 512 MB)"
elif [ "$TOTAL_MB" -ge 256 ]; then
    warn "total RAM = ${TOTAL_MB} MB — works but tight; 512 MB recommended"
else
    fail "total RAM = ${TOTAL_MB} MB — need ≥ 256 MB (recommend ≥ 512 MB)"
fi

# ─── 5. Disk space ───────────────────────────────────────────
echo ""
echo "[5/9] Free disk on /"
AVAIL_GB=$(df -BG / 2>/dev/null | awk 'NR==2{sub(/G$/,"",$4); print $4; exit}')
if [ -z "$AVAIL_GB" ]; then
    fail "df failed; cannot read free disk on /"
elif [ "$AVAIL_GB" -ge 5 ]; then
    pass "free on / = ${AVAIL_GB}G (≥ 5G)"
elif [ "$AVAIL_GB" -ge 2 ]; then
    warn "free on / = ${AVAIL_GB}G — works but tight; 5G recommended"
else
    fail "free on / = ${AVAIL_GB}G — need ≥ 2G for sing-box + venv + traffic.db"
fi

# ─── 6. Network outbound ─────────────────────────────────────
echo ""
echo "[6/9] Outbound network"
if command -v curl >/dev/null 2>&1; then
    if curl -fsSL --max-time 5 -o /dev/null https://github.com/SagerNet/sing-box; then
        pass "github.com reachable (sing-box binary download will work)"
    else
        fail "github.com unreachable — cannot download sing-box"
    fi
    if curl -fsSL --max-time 5 -o /dev/null https://ifconfig.me; then
        pass "ifconfig.me reachable (public IP auto-detection will work)"
    else
        warn "ifconfig.me unreachable — install.sh will leave server.public_host blank"
    fi
else
    warn "curl not installed — will install in apt step below"
fi

# ─── 7. systemd ──────────────────────────────────────────────
echo ""
echo "[7/9] Service manager"
if [ -d /run/systemd/system ] && command -v systemctl >/dev/null 2>&1; then
    pass "systemd present (systemctl found)"
else
    fail "systemd not detected — ProxyBox requires systemd for service management"
fi

# ─── 8. Ports that must be free ──────────────────────────────
echo ""
echo "[8/9] Required ports free"
port_holder() {
    # Return the process listening on the given port (proto = tcp or udp), or empty.
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
        pass "$proto/$port free ($desc)"
    elif echo "$holder" | grep -qE '(sing-box|uvicorn|proxybox)'; then
        # Held by one of our own services — idempotent re-install scenario.
        # Treat as passing so install.sh can re-run on an existing host.
        pass "$proto/$port already held by ProxyBox service ($holder) — re-install OK"
    else
        fail "$proto/$port held by external process $holder (needed for $desc)"
    fi
}
check_port 8080  tcp "admin HTTP"
check_port 11000 tcp "VLESS Reality template"
check_port 21000 udp "Hysteria2 template"
echo "  (per-device ports 11001-11050 TCP + 21001-21050 UDP are allocated by /api/devices/new on demand)"

# ─── 9. apt-installable runtime deps ────────────────────────
echo ""
echo "[9/9] apt-installable runtime tools"
DEPS="python3 python3-venv python3-systemd curl sqlite3 openssl fail2ban"
for pkg in $DEPS; do
    if dpkg -s "$pkg" >/dev/null 2>&1; then
        pass "$pkg installed"
    else
        warn "$pkg missing"
        NEEDED_APT="$NEEDED_APT $pkg"
    fi
done

# Report sing-box presence (will be downloaded by install.sh if absent)
echo ""
echo "[bonus] sing-box binary"
if command -v sing-box >/dev/null 2>&1; then
    pass "sing-box already installed: $(sing-box version 2>/dev/null | head -1)"
else
    warn "sing-box not present (install.sh will download latest from GitHub)"
fi

# ─── Summary + optional auto-install ─────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"

if [ "$FAIL" -gt 0 ]; then
    printf "  $(red "✗ %d blocking failure(s)") — fix these before running install.sh\n" "$FAIL"
    exit 1
fi

if [ "$WARN" -gt 0 ]; then
    printf "  $(yellow "⚠ %d warning(s)") — install can proceed, see notes above\n" "$WARN"
else
    printf "  $(green "✓ all checks pass") — ready to run install.sh\n"
fi

if [ -n "$NEEDED_APT" ]; then
    echo ""
    if [ "$INSTALL_MODE" = "true" ]; then
        echo "  --install mode — installing missing apt packages now:"
        echo "    ↳$NEEDED_APT"
        apt-get -y update >/dev/null 2>&1
        # shellcheck disable=SC2086
        apt-get -y install $NEEDED_APT 2>&1 | tail -3
        echo "  $(green "✓ apt deps installed; re-run this script to re-verify, then run install.sh")"
    else
        echo "  to auto-install the missing apt packages, re-run:"
        echo "    $(yellow "sudo bash $(basename "$0") --install")"
        echo "  (install.sh will install them itself anyway, but doing it up-front is cleaner)"
    fi
fi

exit 0
