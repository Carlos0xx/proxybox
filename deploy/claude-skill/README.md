# ProxyBox · Claude deploy skill

> A Claude Code skill bundle that drives the full ProxyBox install over SSH.

Trigger in any Claude Code session:

> deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519

Claude then checks the VPS, clones or updates the repo, runs the full pre-flight, executes `install.sh`, verifies the services, and hands back the login URL + credentials.

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
| 2 | Creates a temporary session-local `known_hosts` file, records the VPS fingerprint, and leaves the user's normal SSH trust store untouched. |
| 3 | Runs a minimal inline VPS check before the repo exists. |
| 4 | Installs bootstrap tools (`git`, `curl`, `ca-certificates`) if missing. |
| 5 | `git clone https://github.com/carlos0xx/proxybox /opt/proxybox`, or updates an existing checkout from `origin/main` with `git pull --ff-only origin main`. |
| 6 | Runs `deploy/check-prereqs.sh --install` over SSH, including Python 3.11 provisioning — aborts on a blocking failure. |
| 7 | Runs `bash deploy/install.sh --lang <auto-detected>`. |
| 8 | Verifies `sing-box`, `proxybox-admin`, `proxybox-traffic-worker`, and `fail2ban` are `active`. |
| 9 | Relays the **login URL + full password + 5 subscription URLs** back to the user. |
| 10 | *(optional)* Writes `/etc/proxybox/bot.env` + enables `proxybox-bot` if Telegram details were supplied. |

---

## What the skill knows about

| Feature | Since | Skill behaviour |
| --- | --- | --- |
| Username + password login form | v0.1.6 | Surfaces `admin.username` (config.yaml) + the password file (`/etc/proxybox/admin.password`, mode 0400) + `admin.login_path` (config.yaml) in the handoff. |
| HTTPS provisioning from the UI | v0.1.10 | Tells the user they can switch to HTTPS later from the panel — no SSH required. |
| Account self-service | v0.1.11 | Mentions the rotation options in the *Security* page. |
| Per-line copy buttons | v0.1.12 | Confirms the SPA's copy buttons work over HTTP. |
| Bilingual SPA + login form | v0.2.0 | Picks `--lang` based on the user's prompt language; mentions the topbar language toggle. |

---

## Credential handling

The skill instructs Claude to:

1. Echo the **full login URL** (it contains the URL-path token, but the token alone is useless without the password).
2. Echo the **freshly generated admin password** (the new install wrote it to `/etc/proxybox/admin.password` mode 0400, not into `config.yaml`) so the user can paste it into a password manager.
3. **Never echo the bare `admin.token`** outside the login URL context — no quoting it back in commentary, no writing it to logs.

The credentials live only on the VPS: username/login path in `/etc/proxybox/config.yaml`, password in `/etc/proxybox/admin.password`. The skill does not persist them locally.

> [!NOTE]
> The handoff prints the password and login URL once. If the user closes the session before copying, they retrieve both via SSH:
> ```bash
> cat /etc/proxybox/admin.password; grep -E "username|login_path" /etc/proxybox/config.yaml
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
