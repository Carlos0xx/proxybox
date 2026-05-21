# ProxyBox · Claude deploy skill

> A Claude Code skill bundle that drives the full ProxyBox install over SSH.

Trigger in any Claude Code session:

> deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519

Claude then checks the VPS, clones or updates the repo, lets `deploy/docker-install.sh` install/start Docker if needed, verifies the services, and hands back the login URL + credentials.

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
| 4 | Installs bootstrap tools (`git`, `curl`, `ca-certificates`) if missing. |
| 5 | `git clone https://github.com/carlos0xx/proxybox /opt/proxybox`, or updates an existing checkout from `origin/main` with `git pull --ff-only origin main`. |
| 6 | Runs `bash deploy/docker-install.sh`, which checks/installs Docker + Compose, starts Docker, and scans free host ports. |
| 7 | Starts the isolated Docker stack. |
| 8 | Verifies `sing-box`, `proxybox-admin`, and `proxybox-traffic-worker` are `Up`. |
| 9 | Relays the **login URL + full password + first device status** back to the user. |
| 10 | *(optional)* Writes `/opt/proxybox/bot.env` + starts `proxybox-bot` profile if Telegram details were supplied. |

---

## What the skill knows about

| Feature | Since | Skill behaviour |
| --- | --- | --- |
| Username + password login form | v0.1.6 | Surfaces `admin.username` (config.yaml) + the password file inside the Docker volume (`/etc/proxybox/admin.password`) + `admin.login_path` (config.yaml) in the handoff. |
| HTTPS options | v1.0 | Tells Docker users to put Admin UI behind a host reverse proxy, gateway, or Cloudflare Tunnel. |
| Account self-service | v0.1.11 | Mentions the rotation options in the *Security* page. |
| Per-line copy buttons | v0.1.12 | Confirms the SPA's copy buttons work over HTTP. |
| Docker-first install | v1.0 | Uses bridge networking, auto-selected ports, and no host systemd/fail2ban writes. |

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
> cd /opt/proxybox
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
