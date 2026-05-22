# Claude Code skill

> A bundled Claude Code skill that drives an explicitly selected install mode over SSH — minimal VPS check, clone into a new install directory, `deploy/install.sh --docker` or `deploy/install.sh --native --fresh`, verification, credential handoff. Native `--fresh` refuses existing native state; it does not delete old data.

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
| 3 | Require an explicit Docker/native install-mode choice before running remote install commands; Docker being installed, supported, or recommended is not consent. |
| 4 | Run a minimal inline VPS check before the repo exists. |
| 5 | Install bootstrap tools (`git`, `curl`, `ca-certificates`) if missing. |
| 6 | Clone `https://github.com/carlos0xx/proxybox` into a new `/opt/proxybox-<timestamp>-<suffix>` directory and refuse to touch existing directories. |
| 7 | Run `bash deploy/install.sh --docker` or `bash deploy/install.sh --native --fresh`; Docker mode checks/installs Docker + Compose, starts Docker, scans free host ports, and installs project-scoped Docker guard + HTTPS helper systemd units. |
| 8 | Verify the core services are healthy. |
| 9 | Relay the login URL, username, password, and first device status back to you. |

---

## What the skill knows about

The bundled `SKILL.md` carries instructions for:

- **v0.1.6+** login model — username + password form at `/login/{login_path}`, *not* URL-token-only auth.
- **HTTPS options** — Docker users can enable HTTPS from the panel; a project-scoped host systemd helper validates DNS and configures Caddy without installing Caddy inside the container.
- **v0.1.11+** account self-service — how to mention rotation options in the handoff.
- **v0.1.12** copy-button fix — the SPA now has per-line copy buttons on the subscription page.
- **Explicit install-mode choice** — Docker remains recommended; native is advanced and host-level.

---

## Credential handling

The skill explicitly instructs Claude to:

1. **Echo the full login URL** (the URL-path token is one of two required factors — printing it alone doesn't leak access).
2. **Echo the freshly generated admin password** (lives in `/etc/proxybox/admin.password` inside the ProxyBox Docker volume — not in `config.yaml`) so the user can paste it into a password manager.
3. **Never echo the bare `admin.token`** outside the login URL context. Don't quote it in commentary, don't write it to logs.

The credentials live only in the ProxyBox Docker volume: username/login path in `/etc/proxybox/config.yaml`, password in `/etc/proxybox/admin.password`. The skill never persists them locally.

> [!IMPORTANT]
> The skill assumes you trust your local Claude Code session. If you'd rather Claude never see the credentials, run `deploy/install.sh` over SSH yourself — the skill is a convenience, not a hard requirement.

---

## Telegram bot (optional)

If you also pass Telegram bot details in the initial prompt:

> deploy proxybox on 1.2.3.4 with TG bot token 123:ABC for user id 4567

…the skill will additionally write `bot.env` inside the new install directory and run `docker compose --profile bot up -d proxybox-bot` at the end. Docker compose supplies the internal admin URL and install-scoped bot secret from `.env`; the bot does not need an extra host port.

---

## See also

- [Docker install](./docker.md) · what the skill runs underneath
- [`deploy/claude-skill/SKILL.md`](../../deploy/claude-skill/SKILL.md) · the actual skill instructions Claude reads
- [Getting started](../getting-started.md) · the three deploy paths side-by-side
- [← Back to README](../../README.md)
