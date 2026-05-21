# Claude Code skill

> A bundled Claude Code skill that drives the Docker-first install over SSH — minimal VPS check, `git clone` / update, Docker runtime provisioning via `deploy/docker-install.sh`, verification, credential handoff.

For the high-level walkthrough, see [Getting started · Path 3](../getting-started.md#path-3--claude-code).

---

## Install the skill

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

The skill is self-contained — once installed it is available in every Claude Code session, no per-project setup needed.

---

## Use the skill

In any Claude Code session:

> deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519

Claude will:

| # | Step |
| --- | --- |
| 1 | Ask for SSH user / auth method if missing from the prompt. |
| 2 | Use a temporary session-local `known_hosts` file that is deleted on shell exit instead of editing your normal SSH trust store. |
| 3 | Run a minimal inline VPS check before the repo exists. |
| 4 | Install bootstrap tools (`git`, `curl`, `ca-certificates`) if missing. |
| 5 | `git clone https://github.com/carlos0xx/proxybox /opt/proxybox`, or update an existing checkout from `origin/main` with `git pull --ff-only origin main`. |
| 6 | Run `bash deploy/docker-install.sh`, which checks/installs Docker + Compose, starts Docker, and scans free host ports. |
| 7 | Start the isolated Docker stack. |
| 8 | Verify the Docker services are `Up`. |
| 9 | Relay the login URL, username, password, and first device status back to you. |

---

## What the skill knows about

The bundled `SKILL.md` carries instructions for:

- **v0.1.6+** login model — username + password form at `/login/{login_path}`, *not* URL-token-only auth.
- **HTTPS options** — Docker users should put Admin UI behind a host reverse proxy, gateway, or Cloudflare Tunnel.
- **v0.1.11+** account self-service — how to mention rotation options in the handoff.
- **v0.1.12** copy-button fix — the SPA now has per-line copy buttons on the subscription page.
- **Docker-first install** — bridge network, auto-selected ports, no host systemd/fail2ban writes.

---

## Credential handling

The skill explicitly instructs Claude to:

1. **Echo the full login URL** (the URL-path token is one of two required factors — printing it alone doesn't leak access).
2. **Echo the freshly generated admin password** (lives in `/etc/proxybox/admin.password` inside the ProxyBox Docker volume — not in `config.yaml`) so the user can paste it into a password manager.
3. **Never echo the bare `admin.token`** outside the login URL context. Don't quote it in commentary, don't write it to logs.

The credentials live only in the ProxyBox Docker volume: username/login path in `/etc/proxybox/config.yaml`, password in `/etc/proxybox/admin.password`. The skill never persists them locally.

> [!IMPORTANT]
> The skill assumes you trust your local Claude Code session. If you'd rather Claude never see the credentials, run `deploy/docker-install.sh` over SSH yourself — the skill is a convenience, not a hard requirement.

---

## Telegram bot (optional)

If you also pass Telegram bot details in the initial prompt:

> deploy proxybox on 1.2.3.4 with TG bot token 123:ABC for user id 4567

…the skill will additionally write `/opt/proxybox/bot.env` and run `docker compose --profile bot up -d proxybox-bot` at the end.

---

## See also

- [Docker install](./docker.md) · what the skill runs underneath
- [`deploy/claude-skill/SKILL.md`](../../deploy/claude-skill/SKILL.md) · the actual skill instructions Claude reads
- [Getting started](../getting-started.md) · the three deploy paths side-by-side
- [← Back to README](../../README.md)
