# Docker Install

> Recommended path. The Docker stack runs on a bridge network, auto-selects
> free host ports, and does not install host Python, fail2ban, or SSH
> `known_hosts` entries. The installer only adds project-scoped host helpers:
> a Docker guard timer and an HTTPS helper that runs only after the admin panel
> requests HTTPS setup.

> [!IMPORTANT]
> Installation red line: never delete, modify, overwrite, or reuse files,
> services, containers, or volumes outside the current install. If
> `/opt/proxybox` or another same-name directory already exists, leave it
> untouched and clone into a fresh `proxybox-<timestamp>-<suffix>` directory.

## Quick Start

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR"
bash deploy/docker-install.sh
```

The installer:

| Step | Behavior |
| --- | --- |
| Docker check | Checks Docker CLI, Compose, and daemon; installs Docker/Compose when missing and starts the daemon when needed. |
| Port scan | Ensures `ss`/`iproute2` is available, then detects listening ports. `8080` is used when free; otherwise the installer tries `18080`, `28080`, and higher candidates. VLESS and Hy2 also receive a contiguous free port range. |
| `.env` write | Writes the new Compose project name, image tags, selected ports, and public host to the install directory. |
| Stack start | Runs `docker compose up -d --build` with a bridge network and explicit published ports. |
| First device | Creates a random five-letter lowercase device name when the device table is empty. Set `PROXYBOX_FIRST_DEVICE=` to skip it. |
| Docker guard | Installs `proxybox-docker-guard-<project>.timer`, which runs `docker compose up -d` from this install directory every minute and starts `docker.service` if the Docker daemon is stopped. |
| HTTPS helper | Installs `proxybox-docker-https-<project>.path`, which watches this install's `.proxybox-guard/https-request` file for one-click HTTPS setup from the panel. |

Every normal installer run creates a fresh Compose project and fresh Docker
volumes. It never runs `down`, removes old volumes, or rewrites an older
ProxyBox project. If an older project is still running, its ports are treated
as occupied and the new install selects different ports.

An upgrade is not an install. Only upgrade in place after explicitly choosing
the existing ProxyBox install directory.

## Port Policy

| Use | Default | Override |
| --- | --- | --- |
| Admin UI | TCP `8080` | `PROXYBOX_ADMIN_PORT` |
| VLESS template + device range | **randomised** (TCP base in 10000-28999, +1..+50) | `PROXYBOX_VLESS_TEMPLATE_PORT` + `PROXYBOX_VLESS_START/END` |
| Hy2 template + device range | **randomised** (UDP base in 31000-54999, +1..+50) | `PROXYBOX_HY2_TEMPLATE_PORT` + `PROXYBOX_HY2_START/END` |
| Clash API | Container `9090` | Not published to the host; only admin and worker use it inside Docker. |

The bootstrap container randomises the VLESS/Hy2 base on first start (a fixed port is a fingerprint). Set the env vars above for reproducible ports, e.g. in CI or when pinning firewall rules. The chosen base is recorded in `config.yaml` under `ports`.

Example `.env`:

```dotenv
COMPOSE_PROJECT_NAME=proxybox-1770000000-1a2b3c4d
PROXYBOX_IMAGE=proxybox:proxybox-1770000000-1a2b3c4d
PROXYBOX_SINGBOX_IMAGE=proxybox-sing-box:proxybox-1770000000-1a2b3c4d
PROXYBOX_PUBLIC_HOST=203.0.113.10
PROXYBOX_ADMIN_BIND=0.0.0.0
PROXYBOX_ADMIN_PORT=18080
PROXYBOX_CLASH_PORT=9090
PROXYBOX_VLESS_TEMPLATE_PORT=12000
PROXYBOX_VLESS_START=12001
PROXYBOX_VLESS_END=12050
PROXYBOX_HY2_TEMPLATE_PORT=22000
PROXYBOX_HY2_START=22001
PROXYBOX_HY2_END=22050
PROXYBOX_BOT_INTERNAL_SECRET=<64-hex-chars>
PROXYBOX_FRESH=0
```

## Services And Isolation

| Service | Role | Host impact |
| --- | --- | --- |
| `bootstrap` | Generates `/etc/proxybox/config.yaml` and `/etc/sing-box/config.json` on first boot. | Writes Docker named volumes. |
| `sing-box` | Proxy core. | Publishes only the TCP/UDP ports from `.env`. |
| `proxybox-admin` | FastAPI admin backend and static panel. | Publishes only the Admin UI port. |
| `proxybox-traffic-worker` | Polls the Clash API for traffic accounting. | Publishes no host port. |
| `proxybox-bot` | Optional Telegram bot. | Reads project-local `bot.env` only; uses the install-scoped internal secret to call the admin API. |

The Services page reports both the in-container watchdog and the host-level
Docker Guard. The watchdog handles service and port self-recovery inside the
stack. Docker Guard reports its status through `.proxybox-guard/status`.
The same install-scoped directory is used for HTTPS helper request/response
files.

In Docker mode, the admin container does not call host `systemctl` to control
services:

| Operation | Docker behavior |
| --- | --- |
| sing-box reload | Admin writes a reload flag into the shared volume; the sing-box wrapper sends HUP inside the container. |
| traffic worker restart | Admin writes a restart flag; the worker wrapper restarts its child process inside the container. |
| Service status | Admin probes itself, the sing-box Clash API, worker heartbeat, and the Docker Guard status file. |
| Logs | The panel reads service logs from shared container volumes. |

## New Install Vs Upgrade

Running `bash deploy/docker-install.sh` normally means a new install: new
Compose project, new volumes, new selected ports, new login URL, and new
subscription URLs. Existing projects are left untouched.

To upgrade one existing project, first enter that exact install directory and
run the documented upgrade flow from there. Upgrade mode reuses the `.env`
and Compose project in that directory; a normal install must not reuse it.

## HTTPS And fail2ban

The Docker path does not install Caddy or fail2ban inside containers. HTTPS can
be enabled from the admin panel:

1. Point the domain's A record at the VPS public IP.
2. Click enable HTTPS in the panel.
3. The admin container writes `.proxybox-guard/https-request`.
4. `proxybox-docker-https-<project>.path` triggers `deploy/docker-https-apply.sh` on the host.
5. The helper validates DNS, installs/starts Caddy, opens `80/tcp` and `443/tcp` in ufw/firewalld on a best-effort basis, writes the ProxyBox-managed Caddyfile, and reverse-proxies to the Admin UI port from `.env`.
6. The helper writes `.proxybox-guard/https-response`; the admin container reads it and updates the public host plus passkey origin settings.

Safety boundary: the helper only reacts to request files from this install
directory, and it trusts the Admin UI port only from this install's `.env`.
If a non-ProxyBox-managed `/etc/caddy/Caddyfile` already exists, the helper
returns `caddyfile_conflict` and does not overwrite it.

## Telegram Bot

The Docker bot is an optional profile:

```bash
cat > bot.env <<EOF
BOT_TOKEN=...
TG_ALLOWED_USERS=<your-telegram-user-id>
ADMIN_TOKEN=$(docker compose exec -T proxybox-admin sh -c "grep '^  token:' /etc/proxybox/config.yaml | cut -d'\"' -f2")
EOF
chmod 600 bot.env
docker compose --profile bot up -d proxybox-bot
```

Compose sets `PROXYBOX_API_URL=http://proxybox-admin:8080` and
`PROXYBOX_BOT_INTERNAL_SECRET`, so the bot does not need another published
host port.

## Related Files

- [`docker-compose.yml`](../../docker-compose.yml)
- [`deploy/docker-install.sh`](../../deploy/docker-install.sh)
- [`deploy/docker/singbox-entrypoint.sh`](../../deploy/docker/singbox-entrypoint.sh)
