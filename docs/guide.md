# Guide

> Day-to-day usage walkthrough: install, use the panel, and troubleshoot.

For endpoint details, see [`api/endpoints.md`](./api/endpoints.md). For service
internals, see [`architecture.md`](./architecture.md).

## 1. What ProxyBox Is For

ProxyBox is a self-hosted admin panel for a single VPS running sing-box. It
hands out one VLESS Reality and one Hysteria2 inbound per device, so a leaked
phone subscription can be revoked without touching the laptop, router, or
family devices.

It accounts traffic per device, classifies destination hosts at a category
level, and exposes an optional Telegram bot for mobile administration.

> [!NOTE]
> ProxyBox is not a hosted service. Everything runs on your own VPS: no
> phone-home and no SaaS control plane.

## 2. Prerequisites

| Requirement | Detail |
| --- | --- |
| OS | Debian/Ubuntu VPS. Docker mode can run on an existing host; native mode expects a clean dedicated VPS. |
| Access | Root SSH or passwordless sudo. The Docker installer installs/starts Docker and Compose if missing. |
| Resources | At least 1 GB RAM and 5 GB free disk. |
| Required ports | Docker mode auto-selects free Admin, VLESS, and Hy2 ports and writes them to `.env`. |
| HTTPS later | A domain pointing at the VPS, plus `80/tcp` and `443/tcp` open. Optional but recommended. |

## 3. Install

| Path | Best for | Reference |
| --- | --- | --- |
| Claude Code / Codex | Recommended. An AI coding agent drives SSH deployment for you. | [`deploy/claude-skill.md`](./deploy/claude-skill.md) |
| One-line install | Backup for users with just a VPS and no local tooling. | [`deploy/docker.md`](./deploy/docker.md) |
| Native `install.sh` | Clean VPS that must use host-level fail2ban/Caddy. | [`deploy/install-sh.md`](./deploy/install-sh.md) |

### Claude Code / Codex

The lowest-friction path if you already use Claude Code or Codex. For Claude
Code, install the bundled skill once:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

Then ask the agent to deploy ProxyBox on your VPS and provide the SSH target.
The agent must ask you to choose Docker or native first; Docker already being
installed, recommended, or a better fit for available ports is not consent.

After your explicit answer, it uses an auto-deleted temporary SSH
`known_hosts` file, runs a minimal VPS check, clones into a fresh install
directory, runs `deploy/install.sh --docker` or
`deploy/install.sh --native --fresh`, verifies services, and relays the
credentials.

### One-line Install

No coding agent? SSH into a fresh Debian/Ubuntu VPS as root and paste one line:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/carlos0xx/proxybox/main/deploy/get.sh)
```

It installs git/curl, clones ProxyBox to `/opt/proxybox`, and launches the
installer. The only question is Docker or native install — **pressing Enter
picks Docker**, the recommended mode. Append `--docker` or
`--native --fresh --lang en` to skip the prompt entirely.

Pick Docker for container isolation, automatic port selection, and
project-scoped host helpers. If the VPS already runs websites, panels, or
production services, choose Docker. Native install writes Python, sing-box,
systemd units, and fail2ban directly to the host; only use it on a clean
dedicated VPS.

> [!IMPORTANT]
> Installation red line: never delete, modify, overwrite, or reuse files or
> services outside the current install. If `/opt/proxybox` or another
> same-name directory already exists, leave it untouched and clone into a new
> `proxybox-<timestamp>-<suffix>` directory.

### Native Install

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR"
bash deploy/install.sh --native --fresh --lang en
```

Native `--fresh` proceeds only when no previous ProxyBox/sing-box native state
is present. It never deletes old state automatically. On a clean VPS it prints
a self-contained handoff: login URL, username, password, and subscription URLs.

> [!IMPORTANT]
> Copy the credentials into a password manager before closing the terminal.
> Recovery via SSH: `cat /etc/proxybox/admin.password` for the password; the
> rest is in `/etc/proxybox/config.yaml`.

## 4. First Login

Open the login URL printed by the installer:

```text
http://<your-vps>:<admin-port>/login/<random-12-char-suffix>
```

The bare `/login` returns 404. The random suffix prevents scanners from
confirming that a login form exists.

Enter `admin` plus the printed password. A 30-day session cookie is set and
the panel opens.

The auto-created first device uses a random five-letter lowercase name. Its
subscription URLs are available in the subscription page:

| Format | Best for |
| --- | --- |
| `shadowrocket.yaml` | Shadowrocket with nodes plus routing rules. |
| `clash.yaml` | Stash, Clash for iOS, Clash Verge. |
| `merlin.yaml` | AsusWRT-Merlin routers running Clash. |
| Default URI list | sing-box, Hiddify, and basic node clients. |

Paste the matching URL into your client's add-subscription dialog. Then verify
from the client device that `https://ifconfig.me` reports your VPS IP.

## 5. Day-To-Day Operations

Most operations happen in the panel. Docker installs can enable HTTPS from the
panel through the install-scoped host helper.

| Task | Where | Notes |
| --- | --- | --- |
| Add a device | Devices | Use generic names such as `tablet-1`, `home-router`, or random lowercase strings. Avoid personal names because device names enter config and subscription files. |
| Rotate a leaked URL | Devices | `sub_token` rotates; UUID and ports stay unchanged. Re-import once on the client. |
| Pause a device | Devices | Pause indefinitely or until a timestamp. Inbound is removed and traffic history is preserved. |
| Change password / username | Security | Requires the current password. |
| Rotate login-path suffix | Security | Old `/login/{old}` returns 404 immediately. Existing sessions stay valid. |
| Enable HTTPS | HTTPS page | Docker uses the host helper; native mode configures Caddy directly. |
| Watch live traffic | Overview | Real-time bps plus connection count from sing-box's Clash API. |
| Per-device drilldown | History | KPIs, daily chart, 24-hour heatmap, app category, and host table. |
| Ban or unban an IP | Security | Native mode wraps fail2ban. Docker mode leaves host firewall policy to the host/cloud firewall. |

## 6. Troubleshooting

| Symptom | Try this |
| --- | --- |
| Every page says "refresh failed" | Hard refresh with Cmd+Shift+R or Ctrl+F5. Fresh installs send `Cache-Control: no-store`. |
| Copy button does nothing | This usually means an older SPA is cached. For new installs, clone the latest code into a new install directory. Upgrade only after explicitly choosing the existing install directory. |
| A service shows `unknown` | It may not be installed or included in `services.monitored`. For example, `caddy` is absent before HTTPS is enabled. |
| HTTPS provisioning returns `dns_mismatch` | The domain does not resolve to this VPS. Update the A record and retry. |
| Traffic stays at 0 while browsing | The worker may not have flushed a bucket yet. Check `cd <proxybox-install-dir> && docker compose logs --tail=80 proxybox-traffic-worker`. |
| Login URL or password is lost | `cd <proxybox-install-dir> && docker compose exec proxybox-admin sh -c 'cat /etc/proxybox/admin.password; grep -E "username\|login_path" /etc/proxybox/config.yaml'`. |

Docker service logs are available with `docker compose logs`.

## 7. Read More

- [Getting started](./getting-started.md)
- [Architecture](./architecture.md)
- [API endpoints](./api/endpoints.md)
- [Back to README](../README.md)
