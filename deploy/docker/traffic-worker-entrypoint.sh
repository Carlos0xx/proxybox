#!/bin/sh
set -eu

restart_file="${PROXYBOX_WORKER_RESTART_FILE:-/var/lib/proxybox/traffic-worker.restart}"
seen_file="/tmp/proxybox-worker-restart.seen"

mkdir -p "$(dirname "$restart_file")"
touch "$restart_file" "$seen_file"

term_child() {
    if [ "${pid:-}" ]; then
        kill -TERM "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
    fi
    exit 0
}
trap term_child TERM INT

while true; do
    python -m app.workers.traffic &
    pid="$!"

    while kill -0 "$pid" 2>/dev/null; do
        if [ "$restart_file" -nt "$seen_file" ]; then
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
