#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
HOST_GUARD_DIR="$ROOT_DIR/.proxybox-guard"
SUDO=()
DOCKER=(docker)
DOCKER_NEEDS_SUDO=0
COMPOSE=()

die() {
    echo "ERROR: $*" >&2
    exit 1
}

info() {
    echo "==> $*"
}

have_docker_compose() {
    if "${DOCKER[@]}" compose version >/dev/null 2>&1; then
        COMPOSE=("${DOCKER[@]}" compose)
        return 0
    fi
    local compose_bin
    compose_bin="$(command -v docker-compose 2>/dev/null || true)"
    if [ -n "$compose_bin" ]; then
        if [ "$DOCKER_NEEDS_SUDO" = "1" ]; then
            COMPOSE=("${SUDO[@]}" "$compose_bin")
        else
            COMPOSE=("$compose_bin")
        fi
        return 0
    fi
    return 1
}

setup_privilege() {
    if [ "$(id -u)" = "0" ]; then
        SUDO=()
        return
    fi
    command -v sudo >/dev/null 2>&1 || die "root or passwordless sudo is required"
    sudo -n true >/dev/null 2>&1 || die "passwordless sudo is required"
    SUDO=(sudo)
}

check_supported_os() {
    [ -r /etc/os-release ] || die "unsupported OS: /etc/os-release not found"
    # shellcheck disable=SC1091
    . /etc/os-release
    case "${ID:-}" in
        debian|ubuntu) ;;
        *) die "unsupported OS: ${ID:-unknown}; Debian or Ubuntu is required" ;;
    esac
}

install_docker_packages() {
    check_supported_os
    info "installing Docker runtime packages"
    "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get update -qq
    "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        git curl ca-certificates iproute2 docker.io
    if ! "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
        docker-compose-plugin; then
        if ! "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
            docker-compose-v2; then
            "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
                docker-compose
        fi
    fi
}

configure_docker_client() {
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        DOCKER=(docker)
        DOCKER_NEEDS_SUDO=0
        return 0
    fi
    if command -v docker >/dev/null 2>&1 \
        && [ "${#SUDO[@]}" -gt 0 ] \
        && "${SUDO[@]}" docker info >/dev/null 2>&1; then
        DOCKER=("${SUDO[@]}" docker)
        DOCKER_NEEDS_SUDO=1
        return 0
    fi
    return 1
}

start_docker_service() {
    if configure_docker_client; then
        return
    fi

    info "starting Docker service"
    if command -v systemctl >/dev/null 2>&1; then
        "${SUDO[@]}" systemctl enable --now docker >/dev/null 2>&1 || true
    elif command -v service >/dev/null 2>&1; then
        "${SUDO[@]}" service docker start >/dev/null 2>&1 || true
    fi

    for _ in {1..20}; do
        if configure_docker_client; then
            return
        fi
        sleep 1
    done
    die "Docker daemon is not available after install/start"
}

ensure_docker_runtime() {
    setup_privilege
    if ! command -v docker >/dev/null 2>&1 \
        || ! command -v curl >/dev/null 2>&1 \
        || ! command -v ss >/dev/null 2>&1; then
        install_docker_packages
    fi

    start_docker_service

    if ! have_docker_compose; then
        install_docker_packages
        start_docker_service
    fi
    have_docker_compose || die "Docker Compose is required but could not be installed"
    ensure_port_scanner
}

ensure_port_scanner() {
    if command -v ss >/dev/null 2>&1; then
        return
    fi
    check_supported_os
    info "installing port scanner (iproute2)"
    "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get update -qq
    "${SUDO[@]}" env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq iproute2
    command -v ss >/dev/null 2>&1 || die "ss is required for safe port detection"
}

ss_local_addresses() {
    local proto="$1"
    case "$proto" in
        tcp) ss -H -ltn 2>/dev/null || true ;;
        udp) ss -H -lun 2>/dev/null || true ;;
        *) return 1 ;;
    esac
}

port_busy() {
    local proto="$1" port="$2"
    local filter_opts=()
    case "$proto" in
        tcp) filter_opts=(-H -ltn) ;;
        udp) filter_opts=(-H -lun) ;;
        *) return 1 ;;
    esac

    if ss "${filter_opts[@]}" "sport = :$port" 2>/dev/null | grep -q .; then
        return 0
    fi
    ss_local_addresses "$proto" | awk -v port="$port" '
        {
            local_addr = $4
            if (local_addr ~ ("(^|[^0-9])" port "$")) {
                found = 1
            }
        }
        END { exit found ? 0 : 1 }
    '
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
    curl -4 -fsS --max-time 5 https://api4.ipify.org 2>/dev/null \
        || curl -4 -fsS --max-time 5 https://ipv4.icanhazip.com 2>/dev/null \
        || true
}

random_hex() {
    if command -v openssl >/dev/null 2>&1; then
        openssl rand -hex 32
    else
        od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
    fi
}

new_project_name() {
    printf 'proxybox-%s-%04x%04x' "$(date +%s)" "$RANDOM" "$RANDOM"
}

validate_project_name() {
    local name="$1"
    case "$name" in
        [a-z0-9]*)
            if printf '%s' "$name" | grep -Eq '^[a-z0-9][a-z0-9_-]*$'; then
                return 0
            fi
            ;;
    esac
    die "invalid PROXYBOX_PROJECT_NAME: use lowercase letters, digits, hyphen, or underscore"
}

write_env_file() {
    local admin_port public_host project_name
    local vless_block hy2_block
    local vless_template vless_start vless_end
    local hy2_template hy2_start hy2_end
    local bot_internal_secret

    project_name="${PROXYBOX_PROJECT_NAME:-$(new_project_name)}"
    validate_project_name "$project_name"
    admin_port="$(choose_admin_port)"
    vless_block="$(choose_block tcp 11000 12000 13000 14000 15000 16000 17000 18000 19000)"
    hy2_block="$(choose_block udp 21000 22000 23000 24000 25000 26000 27000 28000 29000)"
    read -r vless_template vless_start vless_end <<<"$vless_block"
    read -r hy2_template hy2_start hy2_end <<<"$hy2_block"
    public_host="$(detect_public_host)"
    bot_internal_secret="$(random_hex)"

    umask 077
    cat > "$ENV_FILE" <<EOF
COMPOSE_PROJECT_NAME=${project_name}
PROXYBOX_IMAGE=proxybox:${project_name}
PROXYBOX_SINGBOX_IMAGE=proxybox-sing-box:${project_name}
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
PROXYBOX_BOT_INTERNAL_SECRET=${bot_internal_secret}
PROXYBOX_FRESH=0
EOF
    info "created isolated Docker project: ${project_name}"
    info "selected ports: admin=${admin_port}/tcp, vless=${vless_template}+${vless_start}-${vless_end}/tcp, hy2=${hy2_template}+${hy2_start}-${hy2_end}/udp"
}

env_value() {
    local key="$1"
    awk -F= -v key="$key" '$1 == key { print substr($0, index($0, "=") + 1) }' "$ENV_FILE" \
        | tail -n 1
}

print_selected_ports() {
    [ -f "$ENV_FILE" ] || return
    local admin_port vless_template vless_start vless_end hy2_template hy2_start hy2_end
    admin_port="$(env_value PROXYBOX_ADMIN_PORT)"
    vless_template="$(env_value PROXYBOX_VLESS_TEMPLATE_PORT)"
    vless_start="$(env_value PROXYBOX_VLESS_START)"
    vless_end="$(env_value PROXYBOX_VLESS_END)"
    hy2_template="$(env_value PROXYBOX_HY2_TEMPLATE_PORT)"
    hy2_start="$(env_value PROXYBOX_HY2_START)"
    hy2_end="$(env_value PROXYBOX_HY2_END)"
    info "selected ports: admin=${admin_port:-8080}/tcp, vless=${vless_template:-11000}+${vless_start:-11001}-${vless_end:-11050}/tcp, hy2=${hy2_template:-21000}+${hy2_start:-21001}-${hy2_end:-21050}/udp"
}

prepare_guard_status_dir() {
    mkdir -p "$HOST_GUARD_DIR"
    chmod 700 "$HOST_GUARD_DIR"
    {
        printf 'state=activating\n'
        printf 'last_run=%s\n' "$(date +%s)"
        printf 'message=waiting for docker guard timer\n'
    } > "$HOST_GUARD_DIR/status"
}

install_docker_guard() {
    if ! command -v systemctl >/dev/null 2>&1 || [ ! -d /run/systemd/system ]; then
        info "systemd not detected; Docker guard timer skipped"
        return
    fi

    local project_name service_name timer_name service_path timer_path
    project_name="$(env_value COMPOSE_PROJECT_NAME)"
    validate_project_name "$project_name"
    service_name="proxybox-docker-guard-${project_name}.service"
    timer_name="proxybox-docker-guard-${project_name}.timer"
    service_path="/etc/systemd/system/$service_name"
    timer_path="/etc/systemd/system/$timer_name"

    info "installing host Docker guard for this ProxyBox project"
    "${SUDO[@]}" install -m 644 /dev/stdin "$service_path" <<UNIT
[Unit]
Description=ProxyBox Docker guard (${project_name})
Documentation=https://github.com/carlos0xx/proxybox
After=network-online.target docker.service
Wants=network-online.target docker.service

[Service]
Type=oneshot
WorkingDirectory=$ROOT_DIR
ExecStart=$ROOT_DIR/deploy/docker-guard.sh
TimeoutStartSec=180
UNIT

    "${SUDO[@]}" install -m 644 /dev/stdin "$timer_path" <<UNIT
[Unit]
Description=Run ProxyBox Docker guard (${project_name})

[Timer]
OnBootSec=45s
OnUnitActiveSec=60s
AccuracySec=15s
Persistent=true
Unit=$service_name

[Install]
WantedBy=timers.target
UNIT

    "${SUDO[@]}" systemctl daemon-reload
    "${SUDO[@]}" systemctl enable --now "$timer_name" >/dev/null
    "${SUDO[@]}" systemctl start "$service_name" >/dev/null 2>&1 || true
    info "Docker guard enabled: $timer_name"
}

install_docker_https_helper() {
    if ! command -v systemctl >/dev/null 2>&1 || [ ! -d /run/systemd/system ]; then
        info "systemd not detected; Docker HTTPS helper skipped"
        return
    fi

    local project_name service_name path_name service_path path_path
    project_name="$(env_value COMPOSE_PROJECT_NAME)"
    validate_project_name "$project_name"
    service_name="proxybox-docker-https-${project_name}.service"
    path_name="proxybox-docker-https-${project_name}.path"
    service_path="/etc/systemd/system/$service_name"
    path_path="/etc/systemd/system/$path_name"

    info "installing host HTTPS helper for this ProxyBox project"
    chmod +x "$ROOT_DIR/deploy/docker-https-apply.sh"
    mkdir -p "$HOST_GUARD_DIR"
    chmod 700 "$HOST_GUARD_DIR"

    "${SUDO[@]}" install -m 644 /dev/stdin "$service_path" <<UNIT
[Unit]
Description=ProxyBox Docker HTTPS helper (${project_name})
Documentation=https://github.com/carlos0xx/proxybox
After=network-online.target docker.service
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$ROOT_DIR
ExecStart=$ROOT_DIR/deploy/docker-https-apply.sh
TimeoutStartSec=180
UNIT

    "${SUDO[@]}" install -m 644 /dev/stdin "$path_path" <<UNIT
[Unit]
Description=Watch ProxyBox Docker HTTPS requests (${project_name})

[Path]
PathChanged=$HOST_GUARD_DIR/https-request
PathModified=$HOST_GUARD_DIR/https-request
Unit=$service_name

[Install]
WantedBy=multi-user.target
UNIT

    "${SUDO[@]}" systemctl daemon-reload
    "${SUDO[@]}" systemctl enable --now "$path_name" >/dev/null
    info "Docker HTTPS helper enabled: $path_name"
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

    ensure_docker_runtime

    if [ -f "$ENV_FILE" ] && [ "${PROXYBOX_UPGRADE:-0}" = "1" ]; then
        info "upgrade mode: using existing .env for the current ProxyBox project"
        print_selected_ports
    else
        info "scanning free host ports and writing a new isolated .env"
        write_env_file
    fi

    info "starting isolated Docker stack"
    prepare_guard_status_dir
    "${COMPOSE[@]}" up -d --build
    bootstrap_first_device
    install_docker_guard
    install_docker_https_helper
    print_handoff
    echo "Ports were written to:"
    echo "  ${ENV_FILE}"
    echo
}

main "$@"
