---
name: proxybox-deploy
description: Deploy ProxyBox (per-device isolated home proxy panel) on a Debian or Ubuntu VPS via SSH. Use this skill when the user asks to "install proxybox", "deploy proxybox on my server", "set up a proxy panel", or similar. Requires the user to provide an SSH-reachable VPS with root or sudo access.
---

# ProxyBox · One-shot VPS deploy

This skill drives a non-interactive install of ProxyBox onto a user-supplied
VPS. The default path is Docker so existing host services are not disturbed.
Output is a running stack of:

- sing-box (VLESS Reality + Hysteria2 templates)
- proxybox-admin (FastAPI dashboard on an auto-selected host port)
- proxybox-traffic-worker (per-device byte accounting)
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
repo scripts until after Step 2 has cloned or updated the source.

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
preamble the clone with an apt install. Docker itself is checked and installed
by `deploy/docker-install.sh` in Step 4. The package list is small and
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
    echo "       remove or move /opt/proxybox, then re-run; Docker fresh mode handles runtime state"
    exit 1
  else
    $SUDO git clone https://github.com/carlos0xx/proxybox /opt/proxybox
  fi
'
```

### Step 3 — Docker pre-flight

Now that `/opt/proxybox` exists, do only a lightweight host probe. Do not run
the native `check-prereqs.sh` for the default Docker path; that script is for
the host-systemd installer. Missing Docker / Compose / daemon startup is
handled by `deploy/docker-install.sh` in the next step.

```bash
"${SSH[@]}" "$USER@$HOST" '
  cd /opt/proxybox
  ss -H -ltn >/dev/null 2>&1 || true
  ss -H -lun >/dev/null 2>&1 || true
'
```

If this basic probe fails, paste the error back to the user and stop.

### Step 4 — Run Docker installer

```bash
"${SSH[@]}" "$USER@$HOST" '
  cd /opt/proxybox
  bash deploy/docker-install.sh
'
```

`deploy/docker-install.sh` checks Docker, installs Docker / Compose if
missing, starts the Docker service, scans host ports, and writes `.env`.
Each installer run creates a new Compose project name and new Docker volumes.
It must not stop, delete, or rewrite any older ProxyBox project or unrelated
host service. If the user explicitly asks to upgrade the current project in
place, use `PROXYBOX_UPGRADE=1 bash deploy/docker-install.sh`.

### Step 5 — Verify

```bash
"${SSH[@]}" "$USER@$HOST" '
  cd /opt/proxybox
  docker compose ps
  docker compose logs --tail=80 bootstrap
  docker compose logs --tail=80 sing-box proxybox-admin proxybox-traffic-worker
'
```

The three core long-running services should be `Up`: `sing-box`,
`proxybox-admin`, and `proxybox-traffic-worker`. If any restarts repeatedly,
triage with `docker compose logs --tail=200 <service>`.

### Step 6 — Relay the Docker handoff

As of v0.1.6 the admin panel uses **username + password login**, not a
URL-token in the address bar. The Docker bootstrap logs print the one-shot
handoff block with:

- Login URL: `http://{public_host}:{admin_port}/login/{random_12char_suffix}`
- Username: `admin`
- Password: `<16-char alnum>`

**Do not re-mask the credentials in chat output for this skill.** The user
needs the first login URL and password to complete the install. The bootstrap
output is the same private channel they would see when running the installer
themselves.

If the user needs the credentials re-printed later, this fetches them from the
live Docker volume:

```bash
"${SSH[@]}" "$USER@$HOST" '
  cd /opt/proxybox
  docker compose exec proxybox-admin sh -c "
    echo password: \$(cat /etc/proxybox/admin.password)
    grep -E \"username|login_path|port:\" /etc/proxybox/config.yaml
  "
'
```

### Step 7 — Optional: Telegram bot

Only do this if the user explicitly provided bot credentials.

```bash
"${SSH[@]}" "$USER@$HOST" "
cd /opt/proxybox
ADMIN_TOKEN=\$(docker compose exec -T proxybox-admin python - <<'PY'
import yaml
print(yaml.safe_load(open('/etc/proxybox/config.yaml'))['admin']['token'])
PY
)
cat > bot.env <<ENV
BOT_TOKEN=$BOT_TOKEN
TG_ALLOWED_USERS=$ALLOWED_USERS
ADMIN_TOKEN=\$ADMIN_TOKEN
ENV
chmod 600 bot.env
docker compose --profile bot up -d proxybox-bot
"
```

Verify with `docker compose ps proxybox-bot`. If it crashed, check
`docker compose logs --tail=80 proxybox-bot` — most common cause is malformed
bot token format.

### Step 8 — Hand off to the user

The Docker bootstrap summary block already lays everything out. Just relay it
to the user with a one-line cover sentence — something like:

> "装好了。下面四块全部直接能用：登录凭据（账号 + 密码 + 加随机后缀的
> 登录地址,粘进浏览器就行）、首台设备（进后台订阅链接页复制 URL）、
> 服务状态、可选功能。"

Then paste the Docker bootstrap output (or summarize it) — do not re-format, do not
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

The default first device name is 5 random lowercase letters. Override via env
`PROXYBOX_FIRST_DEVICE=tablet-1 bash deploy/docker-install.sh` before install, or
rename in the admin UI afterwards. `PROXYBOX_FIRST_DEVICE=` skips auto-creation.
`PROXYBOX_FIRST_DEVICE=local-user` is supported only when the user explicitly
asks for it; it uses `PROXYBOX_LOCAL_USERNAME` if provided, else the remote
shell user, sanitized to the device-name format.

### Stuff the user can do AFTER login (no SSH needed)

Mention any of these only when the user asks — don't dump them all at
handoff. v0.1.6+ exposes a lot in the panel:

- **HTTPS:** Docker installs should use a host reverse proxy, gateway, or
  Cloudflare Tunnel. The in-panel Caddy provisioner is only for the advanced
  native `install.sh` path.
- **Change username / password (v0.1.11):** `安全` page → `🔐 登录设置`
  card. Password change requires the current password (session-hijack
  defense).
- **Rotate login path (v0.1.11):** same card → 🎲 轮换. Old `/login/{x}`
  immediately 404s; existing sessions unaffected. Defends against
  `/login` brute-force.
- **Add more devices:** 设备管理 → 生成. Generic naming convention:
  `phone-2`, `tablet-1`, `laptop-1`, `home-router`, or lowercase random strings. **Never
  use personal identifiers** — device names land in sing-box config
  + subscription file content, so they're surface for fingerprinting.
- **Per-device subscription URLs (all 5 formats):** 订阅链接 page or
  设备管理 → device → 📋 订阅 URL. The 复制 button works on plain
  HTTP too (v0.1.12 patched the textarea fallback that newer browsers
  refused). If a user reports "复制按钮没反应", they're on a SPA
  shipped before v0.1.12 — `git pull` in `/opt/proxybox` then
  `docker compose up -d --build proxybox-admin` to upgrade Docker installs.
- **Live throughput + per-device history:** 总览 / 设备历史 / 总流量.
  Host categorisation populates within ~10 s of any client browsing
  (v0.1.9 default-on).
- **Re-print credentials:** if user lost the install summary, the SSH
  fetcher in Step 6 prints login URL + username + password.
- **Panel language:** the web panel is Chinese-only. Do not promise an
  English toggle.

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

- **The Docker bootstrap output IS the user's handoff** — relay it verbatim
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
- **Never** bypass Docker port detection on a host that already runs unrelated
  services. Let `deploy/docker-install.sh` write a fresh isolated `.env`.
- **Never** commit the generated `config.yaml`, `bot.env`, or `session-secret`
  to any git repository
- **Never** delete or stop older ProxyBox containers/volumes just because this
  install is being re-run. New installs create a new Compose project; upgrades
  require explicit `PROXYBOX_UPGRADE=1`.

## Reporting failures

If a step fails, paste the failing command's output (with any tokens or
passwords masked) and stop. Don't attempt to brute-force around errors —
the user almost always has more context about their VPS than what's visible.
