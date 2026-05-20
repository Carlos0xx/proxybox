#!/usr/bin/env bash
# ProxyBox — turn on HTTPS via Caddy + Let's Encrypt.
#
# This is a thin wrapper around the same Python code the admin UI uses
# (app.services.caddy). Power-users / scripted installs can call this
# from the CLI; everyone else can drive it from the "HTTPS · 域名" page
# in the admin panel.
#
# Usage:
#     sudo bash deploy/enable-https.sh <domain>
#
# What it does (idempotent):
#   1. validates <domain> resolves to this VPS's public IP
#   2. apt installs caddy from the Cloudsmith stable repo
#   3. opens 80 + 443 in ufw/firewalld if either is active
#   4. writes /etc/caddy/Caddyfile (reverse-proxy → 127.0.0.1:8080)
#   5. updates /etc/proxybox/config.yaml: server.public_host, passkey.rp_id,
#      passkey.origin
#   6. systemctl reload caddy → Let's Encrypt cert provisioned

set -euo pipefail

if [ "$(id -u)" != "0" ]; then
    echo "ERROR: must run as root" >&2
    exit 1
fi

DOMAIN="${1:-}"
if [ -z "$DOMAIN" ] || [ "$DOMAIN" = "-h" ] || [ "$DOMAIN" = "--help" ]; then
    echo "usage: sudo bash $0 <domain>"
    echo "example: sudo bash $0 proxybox.example.com"
    exit 1
fi

PROXYBOX_VENV="${PROXYBOX_VENV:-/opt/proxybox/.venv}"
if [ ! -x "$PROXYBOX_VENV/bin/python" ]; then
    echo "ERROR: $PROXYBOX_VENV/bin/python not found — run install.sh first" >&2
    exit 1
fi

cd /opt/proxybox
exec "$PROXYBOX_VENV/bin/python" -m app.services.caddy "$DOMAIN"
