#!/bin/sh
set -eu

config_path="${SINGBOX_CONFIG:-/etc/sing-box/config.json}"
reload_file="${PROXYBOX_SINGBOX_RELOAD_FILE:-/etc/sing-box/reload.flag}"
seen_file="/tmp/proxybox-singbox-reload.seen"
log_dir="${PROXYBOX_DOCKER_LOG_DIR:-/var/lib/proxybox/logs}"
log_file="$log_dir/sing-box.log"

mkdir -p "$(dirname "$reload_file")" "$log_dir"
touch "$reload_file" "$seen_file"
touch "$log_file"

mtime() {
    stat -c %Y "$1" 2>/dev/null || echo 0
}

tail -n 0 -f "$log_file" &
tail_pid="$!"

sing-box run -c "$config_path" >>"$log_file" 2>&1 &
pid="$!"

term() {
    kill -TERM "$pid" 2>/dev/null || true
    kill -TERM "$tail_pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    exit 0
}
trap term TERM INT

while kill -0 "$pid" 2>/dev/null; do
    if [ "$(mtime "$reload_file")" -gt "$(mtime "$seen_file")" ]; then
        kill -HUP "$pid" 2>/dev/null || true
        touch "$seen_file"
    fi
    sleep 2
done

status=0
wait "$pid" || status="$?"
kill -TERM "$tail_pid" 2>/dev/null || true
exit "$status"
