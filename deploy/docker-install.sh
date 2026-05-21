#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

die() {
    echo "ERROR: $*" >&2
    exit 1
}

info() {
    echo "==> $*"
}

have_docker_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE=(docker compose)
        return 0
    fi
    if command -v docker-compose >/dev/null 2>&1; then
        COMPOSE=(docker-compose)
        return 0
    fi
    return 1
}

ss_listen() {
    local proto="$1"
    if ! command -v ss >/dev/null 2>&1; then
        return 0
    fi
    case "$proto" in
        tcp) ss -H -ltn 2>/dev/null || true ;;
        udp) ss -H -lun 2>/dev/null || true ;;
        *) return 1 ;;
    esac
}

port_busy() {
    local proto="$1" port="$2"
    ss_listen "$proto" | awk '{print $4}' | grep -Eq "(^|[^0-9])${port}$"
}

range_free() {
    local proto="$1" start="$2" end="$3" port
    for ((port = start; port <= end; port++)); do
        if port_busy "$proto" "$port"; then
            return 1
        fi
    done
    return 0
}

choose_admin_port() {
    local port
    for port in 8080 18080 28080 38080 48080; do
        if ! port_busy tcp "$port"; then
            echo "$port"
            return 0
        fi
    done
    for _ in {1..100}; do
        port=$((30000 + RANDOM % 20000))
        if ! port_busy tcp "$port"; then
            echo "$port"
            return 0
        fi
    done
    die "no free TCP admin port found"
}

choose_block() {
    local proto="$1"
    shift
    local base start end
    for base in "$@"; do
        start=$((base + 1))
        end=$((base + 50))
        if ! port_busy "$proto" "$base" && range_free "$proto" "$start" "$end"; then
            echo "$base $start $end"
            return 0
        fi
    done
    die "no free $proto port block found"
}

detect_public_host() {
    if [ -n "${PROXYBOX_PUBLIC_HOST:-}" ]; then
        echo "$PROXYBOX_PUBLIC_HOST"
        return 0
    fi
    if ! command -v curl >/dev/null 2>&1; then
        return 0
    fi
    curl -fsS --max-time 5 https://ifconfig.me 2>/dev/null \
        || curl -fsS --max-time 5 https://api.ipify.org 2>/dev/null \
        || true
}

write_env_file() {
    local admin_port public_host
    local vless_block hy2_block
    local vless_template vless_start vless_end
    local hy2_template hy2_start hy2_end

    admin_port="$(choose_admin_port)"
    vless_block="$(choose_block tcp 11000 12000 13000 14000 15000 16000 17000 18000 19000)"
    hy2_block="$(choose_block udp 21000 22000 23000 24000 25000 26000 27000 28000 29000)"
    read -r vless_template vless_start vless_end <<<"$vless_block"
    read -r hy2_template hy2_start hy2_end <<<"$hy2_block"
    public_host="$(detect_public_host)"

    umask 077
    cat > "$ENV_FILE" <<EOF
PROXYBOX_PUBLIC_HOST=${public_host}
PROXYBOX_ADMIN_BIND=0.0.0.0
PROXYBOX_ADMIN_PORT=${admin_port}
PROXYBOX_CLASH_PORT=9090
PROXYBOX_VLESS_TEMPLATE_PORT=${vless_template}
PROXYBOX_VLESS_START=${vless_start}
PROXYBOX_VLESS_END=${vless_end}
PROXYBOX_HY2_TEMPLATE_PORT=${hy2_template}
PROXYBOX_HY2_START=${hy2_start}
PROXYBOX_HY2_END=${hy2_end}
PROXYBOX_FRESH=${PROXYBOX_FRESH:-0}
EOF
}

bootstrap_first_device() {
    local exec_env=()
    if [ "${PROXYBOX_FIRST_DEVICE+x}" = x ]; then
        exec_env+=(-e "PROXYBOX_FIRST_DEVICE=$PROXYBOX_FIRST_DEVICE")
    fi
    if [ "${PROXYBOX_LOCAL_USERNAME+x}" = x ]; then
        exec_env+=(-e "PROXYBOX_LOCAL_USERNAME=$PROXYBOX_LOCAL_USERNAME")
    fi
    info "creating first device if needed"
    "${COMPOSE[@]}" exec -T "${exec_env[@]}" proxybox-admin python - <<'PY'
import http.cookiejar
import json
import os
import re
import secrets
import string
import sys
import time
import urllib.parse
import urllib.request

import yaml

base = "http://127.0.0.1:8080"
cfg = yaml.safe_load(open("/etc/proxybox/config.yaml", encoding="utf-8")) or {}
admin = cfg.get("admin", {})
token = admin.get("token", "")
username = admin.get("username", "admin")
login_path = admin.get("login_path") or ""
login_url = f"{base}/login/{login_path}" if login_path else f"{base}/login"
password = open("/etc/proxybox/admin.password", encoding="utf-8").read().strip()

for _ in range(30):
    try:
        urllib.request.urlopen(login_url, timeout=2).close()
        break
    except Exception:
        time.sleep(2)
else:
    print("[first-device] admin not ready; skip", file=sys.stderr)
    raise SystemExit(0)

cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
login_body = urllib.parse.urlencode({"username": username, "password": password}).encode()
opener.open(urllib.request.Request(login_url, data=login_body, method="POST"), timeout=5).close()

list_url = f"{base}/admin/{token}/api/devices/list"
devices = json.load(opener.open(list_url, timeout=5)).get("devices") or []
if devices:
    print("[first-device] existing device found; skip")
    raise SystemExit(0)

raw = os.environ.get("PROXYBOX_FIRST_DEVICE")
if raw is None:
    name = "".join(secrets.choice(string.ascii_lowercase) for _ in range(5))
elif raw == "":
    print("[first-device] PROXYBOX_FIRST_DEVICE empty; skip")
    raise SystemExit(0)
else:
    if raw in {"local-user", "@local-user", "auto-user"}:
        raw = os.environ.get("PROXYBOX_LOCAL_USERNAME") or os.environ.get("USER", "")
    name = re.sub(r"[^A-Za-z0-9_-]+", "-", raw.strip()).strip("-_")
    if len(name) < 3:
        name = f"device-{name}" if name else ""
    name = name[:32].strip("-_")
    if len(name) < 3:
        print("[first-device] resolved name empty; skip")
        raise SystemExit(0)

body = json.dumps({"name": name, "label": name, "kind": "generic"}).encode()
req = urllib.request.Request(
    f"{base}/admin/{token}/api/devices/new",
    data=body,
    headers={"Content-Type": "application/json"},
    method="POST",
)
opener.open(req, timeout=10).close()
print(f"[first-device] created {name}")
PY
}

print_handoff() {
    "${COMPOSE[@]}" exec -T proxybox-admin python - <<'PY'
import yaml

cfg = yaml.safe_load(open("/etc/proxybox/config.yaml", encoding="utf-8")) or {}
admin = cfg.get("admin", {})
host = (cfg.get("server", {}) or {}).get("public_host") or "<your-vps-ip>"
port = admin.get("port") or 8080
path = admin.get("login_path") or ""
password = open("/etc/proxybox/admin.password", encoding="utf-8").read().strip()
login_url = f"http://{host}:{port}/login/{path}" if path else f"http://{host}:{port}/login"
print("")
print("ProxyBox Docker install finished.")
print("")
print(f"Login URL: {login_url}")
print(f"Username:  {admin.get('username', 'admin')}")
print(f"Password:  {password}")
print("")
print("Recovery command:")
print("  docker compose exec proxybox-admin sh -c 'cat /etc/proxybox/admin.password; grep -E \"username|login_path\" /etc/proxybox/config.yaml'")
print("")
PY
}

main() {
    cd "$ROOT_DIR"

    command -v docker >/dev/null 2>&1 || die "Docker is required. Install Docker first, then rerun this script."
    docker info >/dev/null 2>&1 || die "Docker daemon is not available."
    have_docker_compose || die "Docker Compose is required."

    if [ -f "$ENV_FILE" ] && [ "${PROXYBOX_REWRITE_ENV:-0}" = "1" ] && [ "${PROXYBOX_FRESH:-0}" != "1" ]; then
        die "port rescan changes published ports; rerun with PROXYBOX_FRESH=1 PROXYBOX_REWRITE_ENV=1 for a clean reinstall"
    fi

    if [ -f "$ENV_FILE" ] && [ "${PROXYBOX_REWRITE_ENV:-0}" != "1" ]; then
        info "using existing .env (set PROXYBOX_FRESH=1 PROXYBOX_REWRITE_ENV=1 for a clean port rescan)"
    else
        info "scanning free host ports and writing .env"
        write_env_file
    fi

    info "starting isolated Docker stack"
    "${COMPOSE[@]}" up -d --build
    bootstrap_first_device
    print_handoff
    echo "Ports were written to:"
    echo "  ${ENV_FILE}"
    echo
}

main "$@"
