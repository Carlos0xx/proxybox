#!/bin/sh
set -eu

config_path="${SINGBOX_CONFIG:-/etc/sing-box/config.json}"
reload_file="${PROXYBOX_SINGBOX_RELOAD_FILE:-/etc/sing-box/reload.flag}"
seen_file="/tmp/proxybox-singbox-reload.seen"

mkdir -p "$(dirname "$reload_file")"
touch "$reload_file" "$seen_file"

sing-box run -c "$config_path" &
pid="$!"

term() {
    kill -TERM "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    exit 0
}
trap term TERM INT

while kill -0 "$pid" 2>/dev/null; do
    if [ "$reload_file" -nt "$seen_file" ]; then
        kill -HUP "$pid" 2>/dev/null || true
        touch "$seen_file"
    fi
    sleep 2
done

wait "$pid"
