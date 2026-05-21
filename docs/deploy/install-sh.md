# `deploy/install.sh`

> Native host installer. Running `deploy/install.sh` without arguments opens the Docker/native chooser on an interactive terminal; non-interactive runs must pass `--docker` or `--native` explicitly. Use `--native` for this host-level path.

For the high-level walkthrough, see [Getting started · Path 1](../getting-started.md#path-1--interactive-install-docker-recommended).

---

## Invocation

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR"
bash deploy/install.sh --native --fresh --lang en   # --lang zh for Chinese output
```

If you connect as a non-root user with passwordless `sudo`, run the same
command; `install.sh` re-executes itself through `sudo` before making system
changes.

| Flag | Effect |
| --- | --- |
| `--native` | Use the host-level installer instead of the Docker/native chooser. |
| `--fresh` / `PROXYBOX_FRESH=1` | Stop ProxyBox services, remove ProxyBox-managed config/data/subscriptions/systemd units/managed Caddyfile, then generate a new identity. |
| `--reuse` / `--no-fresh` | Keep existing ProxyBox state. This is the default for manual reruns and upgrades. |
| `--lang en` / `--lang zh` | Force language. Default: auto-detect from `$LANG`. |
| `-h` / `--help` | Print the header comment and exit. |
| `PROXYBOX_FIRST_DEVICE=<name>` *(env)* | Override the auto-created first device (default: 5 random lowercase letters). Set it to an empty string to skip auto-creation. |
| `PROXYBOX_FIRST_DEVICE=local-user` *(env)* | Opt-in username-based device name. Uses `PROXYBOX_LOCAL_USERNAME` if set, otherwise the remote shell user, then sanitizes it. |
| `PROXYBOX_LANG=<en\|zh>` *(env)* | Same as `--lang`. |

---

## Pre-flight (`deploy/check-prereqs.sh`)

Invoked automatically before any destructive step. Nine categories — exits non-zero on the first blocking failure:

| # | Category | Checks |
| --- | --- | --- |
| 1 | **OS** | Debian 12/13 or Ubuntu 22.04/24.04/26.04 — `/etc/os-release` match. |
| 2 | **Architecture** | `x86_64` or `aarch64`. |
| 3 | **Privilege** | Effective UID 0 (root) or passwordless `sudo`. |
| 4 | **Memory** | `MemTotal` ≥ 512 MB passes; 256-511 MB warns; below 256 MB blocks. |
| 5 | **Disk** | `/` has ≥ 5 GB free. |
| 6 | **Network** | DNS resolves `github.com`; outbound HTTPS reaches `api.github.com`. |
| 7 | **systemd** | PID 1 is `systemd`. |
| 8 | **Ports** | `8080/tcp`, `11000/tcp`, `21000/udp` not already bound. |
| 9 | **apt deps** | `python3.11`, `python3.11-venv`, `curl`, `sqlite3`, `openssl`, `fail2ban` present (`--install` auto-installs missing; Ubuntu images without `python3.11` get the deadsnakes PPA first). |

Run standalone:

```bash
bash deploy/check-prereqs.sh                 # check only
sudo bash deploy/check-prereqs.sh --install  # also apt-install missing apt deps
```

---

## What it provisions

| Step | Outcome |
| --- | --- |
| 1 | **System packages** via apt: `python3.11`, `python3.11-venv`, `curl`, `sqlite3`, `openssl`, `fail2ban`. |
| 2 | **Directories**: `/etc/proxybox`, `/var/lib/proxybox`, `/var/log/proxybox`, `/var/www/proxybox-sub`, `/etc/sing-box`. |
| 3 | **sing-box binary** — latest GitHub release for the host's arch (amd64 / arm64). |
| 4 | **sing-box systemd unit** — `/etc/systemd/system/sing-box.service`. |
| 5 | **Reality keypair** (X25519), **Hy2 self-signed cert**, random **SNI** picked per install, `experimental.clash_api` enabled. |
| 6 | **Python 3.11 venv** at `<proxybox-install-dir>/.venv` + `pip install -e .`; an existing non-3.11 venv in that install dir is recreated. |
| 7 | **`/etc/proxybox/config.yaml`** — random `admin.token` (24 bytes), random `admin.login_path` (12 alnum), `features.url_token_bypass: false`, and `server.public_host` auto-detected via `ifconfig.me` / `ipify.org`. Mode 0600, root-owned. **The password lives separately** at `/etc/proxybox/admin.password` (mode 0400, root-owned) so a casual `cat config.yaml` cannot leak it. |
| 8 | **fail2ban `[manual]` jail** in `/etc/fail2ban/jail.d/proxybox.local` with `backend=systemd`, plus an `sshd` backend override so minimal images without `/var/log/auth.log` do not fail. |
| 9 | **Four systemd units** — `proxybox-admin`, `proxybox-traffic-worker`, `proxybox-bot` (disabled by default). |
| 10 | `systemctl enable --now` for core services. |
| 11 | **Auto-creates the first device** (5 random lowercase letters by default; override with `PROXYBOX_FIRST_DEVICE`; set it empty to skip) by logging in with the generated username/password and using that session cookie. |
| 12 | **Self-contained handoff** — login URL, username, password, 5 subscription URLs in a single coloured block. |

> [!IMPORTANT]
> The handoff prints the **full** password and **full** login URL — copy them into a password manager before closing the terminal. The token in the URL and the password in plain text are both required to log in; either alone is useless.

---

## Fresh vs Reuse

Use `--fresh` for first installs on templates, rebuilt VPSes, or any host that might contain previous ProxyBox state. It removes:

- `/etc/proxybox`, `/var/lib/proxybox`, `/var/log/proxybox`, `/var/www/proxybox-sub`
- ProxyBox's `sing-box` config/cert/key under `/etc/sing-box`
- ProxyBox-managed systemd unit files
- ProxyBox fail2ban drop-ins and the old marked `[manual]` block in `/etc/fail2ban/jail.local`
- the managed ProxyBox Caddyfile if HTTPS was enabled from the panel

Without `--fresh`, re-running on an installed system keeps state:

- existing config files are kept verbatim
- managed systemd units are rewritten to the current shipped version
- `pip install` is idempotent (same wheels)
- the bootstrap "create first device" step skips if any device row already exists

Use reuse mode for upgrades or partial-failure recovery when you want to keep devices, traffic history, subscription URLs, and credentials.

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
