# `deploy/install.sh`

> The one-shot Bash installer. Idempotent. Provisions a full ProxyBox stack on Debian / Ubuntu in ~3 minutes.

For the high-level walkthrough, see [Getting started · Path 1](../getting-started.md#path-1--installsh-nbsprecommended-for-linux-vps).

---

## Invocation

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox
bash deploy/install.sh --lang en        # --lang zh for Chinese output
```

| Flag | Effect |
| --- | --- |
| `--lang en` / `--lang zh` | Force language. Default: auto-detect from `$LANG`. |
| `-h` / `--help` | Print the header comment and exit. |
| `PROXYBOX_FIRST_DEVICE=<name>` *(env)* | Override the auto-created first device (default `phone-1`). |
| `PROXYBOX_LANG=<en\|zh>` *(env)* | Same as `--lang`. |

---

## Pre-flight (`deploy/check-prereqs.sh`)

Invoked automatically before any destructive step. Nine categories — exits non-zero on the first blocking failure:

| # | Category | Checks |
| --- | --- | --- |
| 1 | **OS** | Debian 12/13 or Ubuntu 22.04/24.04/26.04 — `/etc/os-release` match. |
| 2 | **Architecture** | `x86_64` or `aarch64`. |
| 3 | **Privilege** | Effective UID 0 (root). |
| 4 | **Memory** | `MemTotal` ≥ 1 GB. |
| 5 | **Disk** | `/` has ≥ 5 GB free. |
| 6 | **Network** | DNS resolves `github.com`; outbound HTTPS reaches `api.github.com`. |
| 7 | **systemd** | PID 1 is `systemd`. |
| 8 | **Ports** | `8080/tcp`, `11000/tcp`, `21000/udp` not already bound. |
| 9 | **apt deps** | `python3-venv`, `python3-systemd`, `curl`, `sqlite3`, `openssl`, `fail2ban` present (`--install` auto-installs missing). |

Run standalone:

```bash
bash deploy/check-prereqs.sh                 # check only
sudo bash deploy/check-prereqs.sh --install  # also apt-install missing apt deps
```

---

## What it provisions

| Step | Outcome |
| --- | --- |
| 1 | **System packages** via apt: `python3-venv`, `python3-systemd`, `curl`, `sqlite3`, `openssl`, `fail2ban`. |
| 2 | **Directories**: `/etc/proxybox`, `/var/lib/proxybox`, `/var/log/proxybox`, `/var/www/proxybox-sub`, `/etc/sing-box`. |
| 3 | **sing-box binary** — latest GitHub release for the host's arch (amd64 / arm64). |
| 4 | **sing-box systemd unit** — `/etc/systemd/system/sing-box.service`. |
| 5 | **Reality keypair** (X25519), **Hy2 self-signed cert**, random **SNI** picked per install, `experimental.clash_api` enabled. |
| 6 | **Python venv** at `/opt/proxybox/.venv` + `pip install -e .`. |
| 7 | **`/etc/proxybox/config.yaml`** — random `admin.token` (24 bytes), random `admin.password` (16 alnum), random `admin.login_path` (12 alnum), `server.public_host` auto-detected via `ifconfig.me` / `ipify.org`. Mode 0600, root-owned. |
| 8 | **fail2ban `[manual]` jail** with `backend=systemd` (Debian 13 has no `/var/log/auth.log`). |
| 9 | **Four systemd units** — `proxybox-admin`, `proxybox-traffic-worker`, `proxybox-bot` (disabled by default). |
| 10 | `systemctl enable --now` for core services. |
| 11 | **Auto-creates the first device** (`phone-1` by default; override with `PROXYBOX_FIRST_DEVICE`). |
| 12 | **Self-contained handoff** — login URL, username, password, 5 subscription URLs in a single coloured block. |

> [!IMPORTANT]
> The handoff prints the **full** password and **full** login URL — copy them into a password manager before closing the terminal. The token in the URL and the password in plain text are both required to log in; either alone is useless.

---

## Idempotency

Every step is gated by `[ ! -f ... ]` or `if ! command -v ...`. Re-running on an installed system does nothing destructive:

- existing config files are kept verbatim
- existing systemd units are not overwritten
- `pip install` is idempotent (same wheels)
- the bootstrap "create first device" step skips if any device row already exists

Safe to re-run after a partial failure — pick up where the previous run left off.

---

## HTTPS with Caddy *(v0.1.10+)*

Two entry points; same flow underneath.

### From the admin UI *(recommended)*

1. Log in.
2. Side nav → **HTTPS**.
3. Enter the domain that already points at the VPS.
4. Click **Enable HTTPS**.

Server-side: validates DNS → apt-installs Caddy from the Cloudsmith stable repo → requests a Let's Encrypt cert → writes a reverse-proxy `Caddyfile` → rewrites `server.public_host`, `passkey.rp_id`, `passkey.origin` in `config.yaml` → reloads. End-to-end ~30 s.

### From the CLI

```bash
sudo bash deploy/enable-https.sh <your-domain>
```

Same flow without panel access — useful for automation or when the panel isn't yet reachable (e.g. wrong `public_host`).

### Roll back

```bash
systemctl stop caddy
# clear server.public_host back to the VPS IP in /etc/proxybox/config.yaml
systemctl restart proxybox-admin
```

The panel keeps working over plain HTTP on `:8080`. Caddy auto-renews certs on its own schedule — no cron needed.

---

## Passkey *(opt-in)*

Set `features.passkey: true` and fill `passkey.rp_id` (host without port) and `passkey.origin` (`https://...`) in `config.yaml`. Requires HTTPS in modern browsers — set up Caddy first.

---

## Telegram bot *(opt-in)*

```bash
cat > /etc/proxybox/bot.env <<EOF
BOT_TOKEN=...
TG_ALLOWED_USERS=<your-telegram-user-id>,<another>
ADMIN_TOKEN=$(grep '^  token:' /etc/proxybox/config.yaml | cut -d'"' -f2)
EOF
chmod 600 /etc/proxybox/bot.env
systemctl enable --now proxybox-bot
```

Commands: `/status` · `/devices` · `/traffic` · `/pause <name>` · `/resume <name>` · `/bans`.

---

## See also

- [Docker Compose](./docker.md) · containerised alternative
- [Claude Code skill](./claude-skill.md) · let Claude drive the install
- [`config.example.yaml`](../../config.example.yaml) · every config knob explained
- [← Back to README](../../README.md)
