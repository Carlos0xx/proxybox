#!/bin/sh
set -eu

log_dir="${PROXYBOX_DOCKER_LOG_DIR:-/var/lib/proxybox/logs}"
log_file="$log_dir/proxybox-admin.log"

mkdir -p "$log_dir"
touch "$log_file"

tail -n 0 -f "$log_file" &
tail_pid="$!"

python -m app.services.watchdog >>"$log_file" 2>&1 &
watchdog_pid="$!"

uvicorn app.main:app --host 0.0.0.0 --port 8080 >>"$log_file" 2>&1 &
pid="$!"

term() {
    kill -TERM "$pid" 2>/dev/null || true
    kill -TERM "$watchdog_pid" 2>/dev/null || true
    kill -TERM "$tail_pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    wait "$watchdog_pid" 2>/dev/null || true
    exit 0
}
trap term TERM INT

status=0
wait "$pid" || status="$?"
kill -TERM "$watchdog_pid" 2>/dev/null || true
kill -TERM "$tail_pid" 2>/dev/null || true
exit "$status"
