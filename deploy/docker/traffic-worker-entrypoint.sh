#!/bin/sh
set -eu

restart_file="${PROXYBOX_WORKER_RESTART_FILE:-/var/lib/proxybox/traffic-worker.restart}"
seen_file="/tmp/proxybox-worker-restart.seen"
log_dir="${PROXYBOX_DOCKER_LOG_DIR:-/var/lib/proxybox/logs}"
log_file="$log_dir/proxybox-traffic-worker.log"

mkdir -p "$(dirname "$restart_file")" "$log_dir"
touch "$restart_file" "$seen_file"
touch "$log_file"

mtime() {
    stat -c %Y "$1" 2>/dev/null || echo 0
}

tail -n 0 -f "$log_file" &
tail_pid="$!"

term_child() {
    if [ "${pid:-}" ]; then
        kill -TERM "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    fi
    kill -TERM "$tail_pid" 2>/dev/null || true
    exit 0
}
trap term_child TERM INT

while true; do
    python -m app.workers.traffic >>"$log_file" 2>&1 &
    pid="$!"

    while kill -0 "$pid" 2>/dev/null; do
        if [ "$(mtime "$restart_file")" -gt "$(mtime "$seen_file")" ]; then
            kill -TERM "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
            touch "$seen_file"
            break
        fi
        sleep 2
    done

    wait "$pid" 2>/dev/null || true
    sleep 1
done
