---
name: proxybox-deploy
description: Deploy ProxyBox (per-device isolated home proxy panel) on a fresh Debian or Ubuntu VPS via SSH. Use this skill when the user asks to "install proxybox", "deploy proxybox on my server", "set up a proxy panel", or similar. Requires the user to provide an SSH-reachable VPS with root or sudo access.
---

# ProxyBox · One-shot VPS deploy

This skill drives a non-interactive install of ProxyBox onto a user-supplied
VPS. Output is a running stack of:

- sing-box (VLESS Reality + Hysteria2 templates)
- proxybox-admin (FastAPI dashboard at port 8080)
- proxybox-traffic-worker (per-device byte accounting)
- fail2ban (manual IP ban jail)
- Optional: proxybox-bot (Telegram control)

## Inputs to gather before starting

Ask the user for, in order:

1. **VPS host** — public IP or DNS name
2. **SSH user** — must be root OR have passwordless sudo
3. **SSH auth** — key path (preferred) or password (worse — record in
   blocklist, rotate after install)
4. **Optional bot config**: Telegram bot token + allowed user ID(s) if the
   user wants `/proxybox-bot` enabled. Skip otherwise.

**Never** ask the user to paste these into the chat if a safer channel
exists (e.g. they can put creds in an .env file on their laptop and reference
the path).

## Execution

### SSH session setup

Before the first SSH call, isolate host-key handling for this deployment
session. VPS rebuilds and recycled IPs often conflict with the operator's
normal `~/.ssh/known_hosts`; do not edit or delete that file. Use a temporary
known-hosts file that is deleted when the deploy shell exits, and use the
`SSH` array for every SSH command below. Do not print, persist, or hand off
SSH host fingerprints from this template flow.

```bash
: "${SSH_PORT:=22}"
PROXYBOX_KNOWN_HOSTS="$(mktemp "${TMPDIR:-/tmp}/proxybox-known-hosts.XXXXXX")"
trap 'rm -f "$PROXYBOX_KNOWN_HOSTS"' EXIT
SSH=(
  ssh
  -p "$SSH_PORT"
  -o UserKnownHostsFile="$PROXYBOX_KNOWN_HOSTS"
  -o StrictHostKeyChecking=accept-new
  -o UpdateHostKeys=no
  -o LogLevel=ERROR
)
```

### Step 1 — Minimal host pre-flight

For the **first** SSH after the user gave us VPS credentials, do a minimal
in-line check first. The repo may not exist yet, so do not try to run
`/opt/proxybox/deploy/check-prereqs.sh` until after Step 2 has cloned or
updated the source.

```bash
"${SSH[@]}" "$USER@$HOST" bash -s <<'EOF'
echo "[arch]" $(uname -m)
echo "[os]";   grep PRETTY_NAME /etc/os-release
echo "[disk]"; df -h / | tail -1
echo "[mem]";  free -h | head -2
echo "[priv]"; if [ "$(id -u)" = "0" ]; then echo root; else sudo -n true 2>/dev/null && echo "sudo-ok" || echo "no-sudo"; fi
EOF
```

Bail out if any of:
- arch ∉ {x86_64, aarch64}
- OS ∉ {debian, ubuntu}
- free disk on `/` < 5 G
- RAM < 512 MB
- `[priv]` is `no-sudo`

### Step 2 — Get the source onto the VPS

A minimal Debian image typically ships *without* `git` or `curl`, so
preamble the clone with an apt install. The package list is tiny and
idempotent — re-running it on a fully-provisioned host is a no-op. Existing
checkouts must be updated from `origin/main` explicitly so a stale
`/opt/proxybox` cannot keep serving an old installer.

```bash
"${SSH[@]}" "$USER@$HOST" '
  set -e
  SUDO=""
  if [ "$(id -u)" != "0" ]; then SUDO="sudo"; fi

  # bootstrap tools that may be missing on a minimal Debian / Ubuntu cloud image
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq git curl ca-certificates

  if [ -d /opt/proxybox/.git ]; then
    $SUDO git -C /opt/proxybox remote set-url origin https://github.com/carlos0xx/proxybox
    $SUDO git -C /opt/proxybox fetch --prune origin main
    if $SUDO git -C /opt/proxybox show-ref --verify --quiet refs/heads/main; then
      $SUDO git -C /opt/proxybox checkout main
    else
      $SUDO git -C /opt/proxybox checkout -b main --track origin/main
    fi
    $SUDO git -C /opt/proxybox pull --ff-only origin main
  elif [ -d /opt/proxybox ] && [ -n "$(ls -A /opt/proxybox 2>/dev/null)" ]; then
    echo "[skip] /opt/proxybox exists but is not a git checkout — leaving it alone"
    echo "       if you want a fresh start, ssh in and: rm -rf /opt/proxybox, then re-run"
    exit 1
  else
    $SUDO git clone https://github.com/carlos0xx/proxybox /opt/proxybox
  fi
'
```

### Step 3 — Full repo pre-flight

Now that `/opt/proxybox/deploy/check-prereqs.sh` exists on the host, run the
bundled checker — it's exhaustive (9 categories) and returns a clean exit
code:

```bash
LANG_FLAG=zh  # use en if the user is not writing in Chinese
"${SSH[@]}" "$USER@$HOST" "
  cd /opt/proxybox
  if [ \"\$(id -u)\" = \"0\" ]; then
    bash deploy/check-prereqs.sh --install --lang $LANG_FLAG
  else
    sudo bash deploy/check-prereqs.sh --install --lang $LANG_FLAG
  fi
"
```

If it exits non-zero, paste the output back to the user and **stop** —
don't try to "fix" their environment unless they explicitly ask.

### Step 4 — Run install.sh

```bash
LANG_FLAG=zh  # use en if the user is not writing in Chinese
"${SSH[@]}" "$USER@$HOST" "
  cd /opt/proxybox
  if [ \"\$(id -u)\" = \"0\" ]; then
    bash deploy/install.sh --lang $LANG_FLAG
  else
    sudo bash deploy/install.sh --lang $LANG_FLAG
  fi
"
```

`$LANG_FLAG` is `zh` if the user has been writing to you in Chinese, else
`en`. The script also auto-detects from the VPS's `$LANG` if you omit
`--lang`, but explicit is better so the output language matches the user's
conversation language rather than the server locale.

`install.sh` itself checks for root at the top; the wrapper above just picks
the right invocation (`sudo` or not) without assuming `sudo` is installed
(Debian minimal images don't ship it by default).

This is idempotent — re-running on an already-installed system reuses
the existing first device instead of creating a duplicate. Relay the
final summary verbatim — Step 6 / Step 8 below explain why the full
admin URL is okay to quote in this context.

### Step 5 — Verify

```bash
"${SSH[@]}" "$USER@$HOST" '
  for svc in sing-box proxybox-admin proxybox-traffic-worker fail2ban; do
    state=$(systemctl is-active "$svc" 2>/dev/null)
    printf "%-30s %s\n" "$svc" "$state"
  done
'
```

All four should be `active`. If any is not, fetch its `journalctl -u <svc> -n
30 --no-pager` and triage.

### Step 6 — Relay the install.sh summary

As of v0.1.6 the admin panel uses **username + password login**, not a
URL-token in the address bar. `install.sh` ends with a self-contained
handoff block:

- **🛡 后台登录凭据** — the user-must-save block in bold red:
  - `登录地址  http://{public_host}:8080/login/{random_12char_suffix}`
    (the random suffix is new in v0.1.11 — `/login` itself 404s, defends
    against /login bot scans)
  - `用户名    admin`
  - `密  码    <16-char alnum>`
- The auto-created first device (default name `phone-1`, override via env
  `PROXYBOX_FIRST_DEVICE=<name>` before re-running install.sh)
- All 5 per-device subscription URLs ready to copy

**Do not re-mask the credentials in chat output for this skill.** The
whole point of the one-shot UX is to avoid making普通用户 SSH back in
to recover files manually. The install.sh output is the user's private channel
(same as if they ran the installer locally) — relay it verbatim.

This rule is **scoped to install.sh output and this Step 6 / Step 8
handoff.** Ad-hoc bash you author elsewhere in a session (e.g. for
debugging or status checks) should still mask the password / token to
first 8 chars, because that's chat-only output that doesn't have the
same one-shot UX constraint.

If the user needs the credentials re-printed later (e.g. they lost the
chat backscroll), this fetches them from the live config and password file:

```bash
"${SSH[@]}" "$USER@$HOST" '
  /opt/proxybox/.venv/bin/python -c "
from pathlib import Path
import yaml
c = yaml.safe_load(open(\"/etc/proxybox/config.yaml\"))
a = c[\"admin\"]
host = c[\"server\"][\"public_host\"] or \"<your-vps-ip>\"
proto = \"https\" if a.get(\"login_path\") and c[\"server\"].get(\"public_host\") else \"http\"
port = \"\" if proto == \"https\" else \":8080\"
path = a.get(\"login_path\", \"\")
login_url = f\"{proto}://{host}{port}/login/{path}\" if path else f\"{proto}://{host}{port}/login\"
print(f\"login URL: {login_url}\")
print(f\"username:  {a[\\\"username\\\"]}\")
print(f\"password:  {Path(\\\"/etc/proxybox/admin.password\\\").read_text().strip()}\")
"
'
```

### Step 7 — Optional: Telegram bot

Only do this if the user explicitly provided bot credentials.

```bash
"${SSH[@]}" "$USER@$HOST" "
cat > /etc/proxybox/bot.env <<ENV
BOT_TOKEN=$BOT_TOKEN
TG_ALLOWED_USERS=$ALLOWED_USERS
ADMIN_TOKEN=\$(/opt/proxybox/.venv/bin/python -c \"import yaml; print(yaml.safe_load(open('/etc/proxybox/config.yaml'))['admin']['token'])\")
ENV
chmod 600 /etc/proxybox/bot.env
systemctl enable --now proxybox-bot
"
```

Verify with `systemctl is-active proxybox-bot`. If it crashed, check
`journalctl -u proxybox-bot -n 20` — most common cause is malformed bot
token format.

### Step 8 — Hand off to the user

The install.sh summary block already lays everything out. Just relay it
to the user with a one-line cover sentence — something like:

> "装好了。下面四块全部直接能用：登录凭据（账号 + 密码 + 加随机后缀的
> 登录地址,粘进浏览器就行）、5 个订阅 URL（任挑一个粘进客户端就翻墙）、
> 服务状态、可选功能。"

Then paste install.sh's output (or summarize it) — do not re-format, do not
hide the password / login URL. Do not include SSH host-key material in the
handoff.

Concretely, the user can:

1. **Open the login URL in a browser**. The form auto-focuses the username
   field — type the username + password from the summary, hit 登录,
   arrive in the SPA. Session cookie is set for 30 days.
2. **Pick the subscription URL** that matches their client (table below;
   the install summary labels each line). Default URI list works for
   sing-box / Shadowrocket / Hiddify / Stash — pick `clash.yaml` for
   Clash family or `merlin.yaml` for routers.
3. **Paste** into the client's "Add Subscription" dialog.
4. **Traffic should flow** through the VPS — `ifconfig.me` from the
   client device shows the VPS IP, not the home ISP.

The default first device is named `phone-1`. Override via env
`PROXYBOX_FIRST_DEVICE=tablet-1 bash deploy/install.sh ...` before
install, or rename in the admin UI afterwards.

### Stuff the user can do AFTER login (no SSH needed)

Mention any of these only when the user asks — don't dump them all at
handoff. v0.1.6+ exposes a lot in the panel:

- **HTTPS (v0.1.10):** `HTTPS · 域名` page. User enters a domain that
  resolves to the VPS, clicks 启用 HTTPS. Server auto-installs Caddy
  from Cloudsmith repo, requests Let's Encrypt, updates `config.yaml`,
  reloads. ~30 seconds. New login URL becomes `https://{domain}/login/
  {login_path}`. Caddy auto-renews the cert.
- **Change username / password (v0.1.11):** `安全` page → `🔐 登录设置`
  card. Password change requires the current password (session-hijack
  defense).
- **Rotate login path (v0.1.11):** same card → 🎲 轮换. Old `/login/{x}`
  immediately 404s; existing sessions unaffected. Defends against
  `/login` brute-force.
- **Add more devices:** 设备管理 → 生成. Generic naming convention:
  `phone-1`, `phone-2`, `tablet-1`, `laptop-1`, `home-router`. **Never
  use personal identifiers** — device names land in sing-box config
  + subscription file content, so they're surface for fingerprinting.
- **Per-device subscription URLs (all 5 formats):** 订阅链接 page or
  设备管理 → device → 📋 订阅 URL. The 复制 button works on plain
  HTTP too (v0.1.12 patched the textarea fallback that newer browsers
  refused). If a user reports "复制按钮没反应", they're on a SPA
  shipped before v0.1.12 — `git pull` in `/opt/proxybox` then
  `systemctl restart proxybox-admin` to upgrade.
- **Live throughput + per-device history:** 总览 / 设备历史 / 总流量.
  Host categorisation populates within ~10 s of any client browsing
  (v0.1.9 default-on).
- **Re-print credentials:** if user lost the install summary, the SSH
  fetcher in Step 6 prints login URL + username + password.
- **Switch panel language (v0.2.0):** small `中 / EN` toggle in the
  topbar, next to the theme switcher. Click → page reloads in the other
  language. Choice persists via `localStorage` + a `proxybox-lang`
  cookie, so the login page picks up the same language on next visit.
  Coverage is ~80% — uncovered phrases gracefully fall back to Chinese.
  The login form itself also honours `?lang=en|zh` for the bare URL.
  Note: `install.sh --lang en|zh` only affects the installer OUTPUT;
  the running panel always starts in Chinese and respects the user's
  in-panel toggle from there.

### Subscription URL formats

Each device exposes its own URL prefix at `/api/sub/{sub_token}` (the
`sub_token` is the per-device public auth — admin token is **not** in this
URL, so it's safe to put in a router). Five extension-suffixed variants
are generated on-the-fly from the same per-device row:

| URL suffix                | Format          | Tested clients                                    |
| ------------------------- | --------------- | ------------------------------------------------- |
| *(none, default)*         | URI list        | sing-box-iOS, Shadowrocket (Type: Subscribe), Hiddify |
| `/sub.txt`                | URI list        | Same as default — `.txt` alias for clients that key on extension |
| `/clash.yaml`             | Mihomo / Clash  | Stash, Clash for iOS, Clash Verge (macOS/Win), Clash for Android |
| `/merlin.yaml`            | Clash + `tun:`  | AsusWRT-Merlin with Clash on the router (transparent proxy) |
| `/shadowrocket.conf`      | Surge `.conf`   | Shadowrocket native parser (fallback when URI list misbehaves)   |

If the user is in doubt, the default (URI list) is the right choice for
phones and laptops — Clash YAML is mainly for routers and Stash power-users.

## Anti-patterns (do NOT do these)

- **The install.sh output IS the user's handoff** — relay it verbatim
  including the login URL + username + password (bold red in the
  summary). Re-masking defeats v0.1.6+'s one-shot UX. But ad-hoc bash
  you author later in the same session for status checks / debugging
  still masks credentials to first 8 chars.
- **Never** SSH with `-o StrictHostKeyChecking=no` without the user's
  explicit consent — it disables host-key warnings and would mask MITM
- **Never** delete or rewrite the user's normal `~/.ssh/known_hosts` to
  work around a rebuilt VPS. Use the session-local `PROXYBOX_KNOWN_HOSTS`
  file from the SSH setup step, let the `trap` delete it, and do not report
  or persist host fingerprints.
- **Never** run `install.sh` on a host that already runs unrelated services
  on port 8080, 11000-11050, or 21000-21050 — check `ss -tlnp` first
- **Never** commit the generated `config.yaml`, `bot.env`, or `session-secret`
  to any git repository
- **Don't** overwrite existing `/etc/proxybox/` or `/etc/sing-box/` content
  silently — install.sh is idempotent and skips, but if the user wants a
  fresh start, ask them to `rm -rf` those paths first

## Reporting failures

If a step fails, paste the failing command's output (with any tokens or
passwords masked) and stop. Don't attempt to brute-force around errors —
the user almost always has more context about their VPS than what's visible.
