# ProxyBox · Claude deploy skill

> A Claude Code skill bundle that drives the full ProxyBox install over SSH.

Trigger in any Claude Code session:

> deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519

Claude must ask you to choose Docker or native install first. Docker being installed, supported, or recommended is not a choice on your behalf. After your explicit answer, it checks the VPS, clones the repo into a new per-install directory, runs `deploy/install.sh --docker` or `deploy/install.sh --native --fresh`, verifies the services, and hands back the login URL + credentials. Native `--fresh` refuses existing native state; it does not delete old data.

---

## Install

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

The next Claude Code session sees the skill. Confirm with `claude /skills` or just try a matching prompt.

---

## What it does

| # | Step |
| --- | --- |
| 1 | Asks for SSH user / auth method if missing from the prompt. |
| 2 | Creates a temporary session-local `known_hosts` file, deletes it on shell exit, and leaves the user's normal SSH trust store untouched. |
| 3 | Runs a minimal inline VPS check before the repo exists. |
| 4 | Requires an explicit Docker/native install-mode choice before running remote install commands; environment checks must not be used as consent. |
| 5 | Installs bootstrap tools (`git`, `curl`, `ca-certificates`) if missing. |
| 6 | Clones `https://github.com/carlos0xx/proxybox` into a new `/opt/proxybox-<timestamp>-<suffix>` directory and refuses to touch existing directories. |
| 7 | Runs `bash deploy/install.sh --docker` or `bash deploy/install.sh --native --fresh`; Docker mode checks/installs Docker + Compose, starts Docker, scans free host ports, and installs project-scoped Docker guard + HTTPS helper units. |
| 8 | Verifies `sing-box`, `proxybox-admin`, and `proxybox-traffic-worker` are healthy. |
| 9 | Relays the **login URL + full password + first device status** back to the user. |
| 10 | *(optional Docker mode)* Writes `bot.env` inside the new install directory + starts `proxybox-bot` profile if Telegram details were supplied. |

---

## What the skill knows about

| Feature | Since | Skill behaviour |
| --- | --- | --- |
| Username + password login form | v0.1.6 | Surfaces `admin.username` (config.yaml) + the password file inside the Docker volume (`/etc/proxybox/admin.password`) + `admin.login_path` (config.yaml) in the handoff. |
| HTTPS options | v1.0 | Docker users can enable HTTPS from the panel through the install-scoped host systemd helper, which configures host Caddy without installing Caddy inside the container. |
| Account self-service | v0.1.11 | Mentions the rotation options in the *Security* page. |
| Per-line copy buttons | v0.1.12 | Confirms the SPA's copy buttons work over HTTP. |
| Explicit install-mode choice | v1.0 | Requires Docker/native selection before remote install; Docker uses bridge networking, auto-selected ports, an install-scoped Docker guard, and an install-scoped HTTPS helper. |

---

## Credential handling

The skill instructs Claude to:

1. Echo the **full login URL** (it contains the URL-path token, but the token alone is useless without the password).
2. Echo the **freshly generated admin password** (the new install wrote it to `/etc/proxybox/admin.password` inside the Docker volume, not into `config.yaml`) so the user can paste it into a password manager.
3. **Never echo the bare `admin.token`** outside the login URL context — no quoting it back in commentary, no writing it to logs.

The credentials live only in the ProxyBox Docker volume: username/login path in `/etc/proxybox/config.yaml`, password in `/etc/proxybox/admin.password`. The skill does not persist them locally.

> [!NOTE]
> The handoff prints the password and login URL once. If the user closes the session before copying, they retrieve both via SSH:
> ```bash
> cd <proxybox-install-dir>
> docker compose exec proxybox-admin sh -c 'cat /etc/proxybox/admin.password; grep -E "username|login_path" /etc/proxybox/config.yaml'
> ```

---

## What it does NOT do

- **Doesn't configure DNS** — bring your own domain pointed at the VPS first if you want HTTPS.
- **Doesn't open firewall ports** — depends on your cloud provider's edge filter.
- **Doesn't migrate from other proxy panels** — fresh installs only.
- **Doesn't run on macOS / Windows hosts** — the install steps are Debian/Ubuntu-specific.

---

## See also

- [`SKILL.md`](./SKILL.md) · the actual instructions Claude reads at trigger time
- [`docs/deploy/claude-skill.md`](../../docs/deploy/claude-skill.md) · user-facing reference
- [`docs/getting-started.md`](../../docs/getting-started.md) · the three deploy paths
- [← Back to README](../../README.md)
