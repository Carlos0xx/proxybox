# install.sh

Full reference for the one-shot installer.

See [Getting started · Path 1](../getting-started#path-1-install-sh-recommended-for-linux-vps) for the quick version.

## What it provisions

1. **System packages** via apt: `python3-venv`, `python3-systemd`, `curl`, `sqlite3`, `openssl`, `fail2ban`
2. **Directories**: `/etc/proxybox`, `/var/lib/proxybox`, `/var/log/proxybox`, `/var/www/proxybox-sub`, `/etc/sing-box`
3. **sing-box binary** — latest GitHub release for the host's arch
4. **sing-box systemd unit** — `/etc/systemd/system/sing-box.service`
5. **sing-box config** — Reality keypair (X25519), Hy2 self-signed cert, random SNI from `{microsoft, apple, cloudflare, amazon}.com`, experimental.clash_api enabled
6. **Python venv** at `/opt/proxybox/.venv`, `pip install -e .`
7. **/etc/proxybox/config.yaml** — random ADMIN_TOKEN (`secrets.token_urlsafe(24)`), public_host auto-detected via ifconfig.me / ipify.org
8. **fail2ban [manual] jail** with `backend=systemd` (Debian 13 has no `/var/log/auth.log`)
9. **proxybox-admin.service** systemd unit
10. **proxybox-traffic-worker.service** + **proxybox-bot.service** (bot stays disabled)
11. `systemctl enable --now` for core services
12. Summary print with token first 8 chars only

## Idempotency

Every step is gated by `[ ! -f ... ]` or `if ! command -v ...`. Re-running
on an installed system does nothing destructive:

- existing config files are kept verbatim
- existing systemd units are not overwritten
- pip install is idempotent (same wheels)

## HTTPS with Caddy

Shipped in v0.1.10. Two ways:

1. **From the admin UI (recommended):** log in → "HTTPS · 域名" nav
   entry → enter your domain → 启用 HTTPS. Server-side validates DNS,
   apt-installs Caddy from the Cloudsmith stable repo, requests a
   Let's Encrypt cert, writes a reverse-proxy `Caddyfile`, updates
   `server.public_host` + `passkey.rp_id` + `passkey.origin` in
   `config.yaml`, and reloads. Typical end-to-end ~30 s.

2. **CLI fallback:** `sudo bash deploy/enable-https.sh <domain>`. Same
   flow, no panel access required. Useful for automation or when the
   panel isn't yet reachable (e.g. wrong public_host).

The cert auto-renews via Caddy. Roll back by stopping Caddy
(`systemctl stop caddy`) and clearing `server.public_host` in
config.yaml — the panel keeps working over plain HTTP on port 8080.

## Passkey

Set `features.passkey: true` and fill `passkey.rp_id` (host without port)
and `passkey.origin` (`https://...`) in config.yaml. Requires HTTPS in
modern browsers — set up Caddy first.

## Telegram bot

```bash
cat > /etc/proxybox/bot.env <<EOF
BOT_TOKEN=...
TG_ALLOWED_USERS=...
ADMIN_TOKEN=$(grep '^  token:' /etc/proxybox/config.yaml | cut -d'"' -f2)
EOF
chmod 600 /etc/proxybox/bot.env
systemctl enable --now proxybox-bot
```
