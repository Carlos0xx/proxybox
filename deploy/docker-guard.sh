#!/usr/bin/env bash
# Host-level guard for one ProxyBox Docker install.
#
# Scope is deliberately narrow: this script only starts Docker itself and
# runs `docker compose up -d` for the checkout directory that contains it.
# It never stops containers, removes volumes, or scans other Compose projects.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
GUARD_DIR="$ROOT_DIR/.proxybox-guard"
STATUS_FILE="$GUARD_DIR/status"

log() {
    echo "[proxybox-docker-guard] $*"
}

die() {
    write_status failed "$*"
    echo "[proxybox-docker-guard] ERROR: $*" >&2
    exit 1
}

write_status() {
    local state="$1" message="${2:-}"
    mkdir -p "$GUARD_DIR"
    {
        printf 'state=%s\n' "$state"
        printf 'last_run=%s\n' "$(date +%s)"
        printf 'message=%s\n' "$message"
    } > "$STATUS_FILE"
}

start_docker_if_needed() {
    if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
        return
    fi

    log "Docker daemon unavailable; attempting to start docker.service"
    if command -v systemctl >/dev/null 2>&1; then
        systemctl start docker >/dev/null 2>&1 || true
    elif command -v service >/dev/null 2>&1; then
        service docker start >/dev/null 2>&1 || true
    fi

    for _ in {1..20}; do
        if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
            return
        fi
        sleep 1
    done
    die "Docker daemon is not available"
}

compose_cmd() {
    if docker compose version >/dev/null 2>&1; then
        echo "docker compose"
        return
    fi
    if command -v docker-compose >/dev/null 2>&1; then
        echo "docker-compose"
        return
    fi
    die "Docker Compose is not available"
}

main() {
    [ -f "$ENV_FILE" ] || die "missing env file: $ENV_FILE"
    [ -f "$COMPOSE_FILE" ] || die "missing compose file: $COMPOSE_FILE"

    write_status checking "checking docker daemon and compose stack"
    start_docker_if_needed

    read -r -a compose <<<"$(compose_cmd)"
    log "ensuring ProxyBox stack is up in $ROOT_DIR"
    "${compose[@]}" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d
    write_status active "compose stack ensured"
}

main "$@"
