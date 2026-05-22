---
name: proxybox-deploy
description: Deploy ProxyBox (per-device isolated home proxy panel) on a Debian or Ubuntu VPS via SSH. Use this skill when the user asks to "install proxybox", "deploy proxybox on my server", "set up a proxy panel", or similar. Requires the user to provide an SSH-reachable VPS with root or sudo access.
---

# ProxyBox · One-shot VPS deploy

This skill drives a user-selected install mode of ProxyBox onto a user-supplied
VPS. It must stop and ask for the install mode before any clone or install
command. Docker is recommended so existing host services are not disturbed, but
that recommendation is not consent to choose Docker for the user.
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
4. **Install mode** — ask explicitly unless the user already stated one of the
   two modes in this conversation:
   - Docker install (recommended): isolated containers, auto-selected ports,
     one install-scoped Docker guard, and one install-scoped HTTPS helper.
     It does not write host Python/fail2ban. Host Caddy is touched only if
     the user later clicks the panel's HTTPS enable button.
   - Native host install (advanced): writes Python, sing-box, systemd units,
     and fail2ban directly to the VPS; only for a clean dedicated VPS.
5. **Optional bot config**: Telegram bot token + allowed user ID(s) if the
   user wants `/proxybox-bot` enabled. Skip otherwise.

**Never** ask the user to paste these into the chat if a safer channel
exists (e.g. they can put creds in an .env file on their laptop and reference
the path).

Install-mode consent is strict:

- Docker being installed on the VPS is not consent.
- Ubuntu / Debian being supported is not consent.
- README recommending Docker is not consent.
- Existing host port conflicts are not consent.
- The agent's own judgment that Docker is safer is not consent.

If the user has not explicitly answered "Docker" / "1" or "宿主机" / "2",
stop before Step 1 and ask:

> 请选择安装方式: 1) Docker 安装（推荐,容器隔离,适合已有服务的 VPS） 2) 宿主机安装（高级,会写宿主机 Python/systemd/fail2ban,只适合干净 VPS）

## Execution

Do not run any SSH, `git clone`, or installer command until
`PROXYBOX_INSTALL_MODE` has been set from the user's explicit answer. Never set
`PROXYBOX_INSTALL_MODE=docker` merely because Docker is recommended or already
installed.

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
REMOTE_INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$RANDOM"
# Set this only after the user explicitly chooses: docker or native.
PROXYBOX_INSTALL_MODE="${PROXYBOX_INSTALL_MODE:?choose docker or native first}"
case "$PROXYBOX_INSTALL_MODE" in docker|native) ;; *) echo "invalid install mode"; exit 2 ;; esac
```

### Step 1 — Minimal host pre-flight

For the **first** SSH after the user gave us VPS credentials, do a minimal
in-line check first. The repo may not exist yet, so do not try to run
repo scripts until after Step 2 has cloned the source into a new install
directory.

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

### Step 2 — Clone into a new install directory

A minimal Debian image typically ships *without* `git` or `curl`, so
preamble the clone with an apt install. Docker itself is checked and installed
by `deploy/install.sh --docker` in Step 4 when Docker mode was selected. The
package list is small and idempotent — re-running it on a fully-provisioned
host is a no-op.

Every install must clone into a brand-new directory such as
`/opt/proxybox-20260522-131500-12345`. Do not update, overwrite, delete, move,
or reuse `/opt/proxybox` or any other existing path. If the generated path
already exists, fail and choose a different `REMOTE_INSTALL_DIR`; never touch
the existing directory.

```bash
"${SSH[@]}" "$USER@$HOST" "REMOTE_INSTALL_DIR='$REMOTE_INSTALL_DIR' bash -s" <<'EOF'
  set -e
  SUDO=""
  if [ "$(id -u)" != "0" ]; then SUDO="sudo"; fi

  # bootstrap tools that may be missing on a minimal Debian / Ubuntu cloud image
  $SUDO apt-get update -qq
  $SUDO apt-get install -y -qq git curl ca-certificates

  if [ -z "${REMOTE_INSTALL_DIR:-}" ]; then
    echo "[error] REMOTE_INSTALL_DIR is empty"
    exit 1
  fi
  if [ -e "$REMOTE_INSTALL_DIR" ]; then
    echo "[error] install dir already exists; refusing to touch it: $REMOTE_INSTALL_DIR"
    exit 1
  fi

  $SUDO git clone https://github.com/carlos0xx/proxybox "$REMOTE_INSTALL_DIR"
  echo "[install-dir] $REMOTE_INSTALL_DIR"
EOF
```

### Step 3 — Mode-specific pre-flight

Now that the fresh install directory exists, do only a lightweight host probe
for Docker mode. Do not run the native `check-prereqs.sh` for Docker; missing
Docker / Compose / daemon startup is handled by `deploy/install.sh --docker`
in the next step. If native mode was selected, skip this lightweight probe and
let `deploy/install.sh --native --fresh` run the full native pre-flight. Native
`--fresh` is non-destructive: if previous ProxyBox/sing-box native state is
present, the installer refuses instead of deleting it.

```bash
"${SSH[@]}" "$USER@$HOST" "cd '$REMOTE_INSTALL_DIR' && PROXYBOX_INSTALL_MODE='$PROXYBOX_INSTALL_MODE' bash -s" <<'EOF'
  if [ "$PROXYBOX_INSTALL_MODE" != "docker" ]; then
    echo "[preflight] native mode selected; native installer will run its own checks"
    exit 0
  fi
  ss -H -ltn >/dev/null 2>&1 || true
  ss -H -lun >/dev/null 2>&1 || true
EOF
```

If this basic probe fails, paste the error back to the user and stop.

### Step 4 — Run the selected installer

```bash
"${SSH[@]}" "$USER@$HOST" "cd '$REMOTE_INSTALL_DIR' && PROXYBOX_INSTALL_MODE='$PROXYBOX_INSTALL_MODE' bash -s" <<'EOF'
  case "$PROXYBOX_INSTALL_MODE" in
    docker)
      bash deploy/install.sh --docker
      ;;
    native)
      bash deploy/install.sh --native --fresh --lang zh
      ;;
    *)
      echo "[error] invalid install mode: $PROXYBOX_INSTALL_MODE"
      exit 2
      ;;
  esac
EOF
```

`deploy/install.sh --docker` checks Docker, installs Docker / Compose if
missing, starts the Docker service, scans host ports, and writes `.env`.
Each installer run creates a new Compose project name and new Docker volumes.
It must not stop, delete, or rewrite any older ProxyBox project or unrelated
host service. It also installs two project-scoped systemd helpers:
`proxybox-docker-guard-<project>` for Docker self-recovery and
`proxybox-docker-https-<project>.path` for optional panel-driven HTTPS.
`deploy/install.sh --native --fresh` is the advanced host-level path and must
only be run after the user explicitly chose native mode. It must not be used
as a cleanup mechanism; destructive native cleanup requires the separate
`--purge-existing-proxybox` confirmation flow, which this skill should not run
unless the user explicitly asks to delete the old ProxyBox native install.

### Step 5 — Verify

```bash
"${SSH[@]}" "$USER@$HOST" "cd '$REMOTE_INSTALL_DIR' && PROXYBOX_INSTALL_MODE='$PROXYBOX_INSTALL_MODE' bash -s" <<'EOF'
  if [ "$PROXYBOX_INSTALL_MODE" = "docker" ]; then
    docker compose ps
    docker compose logs --tail=80 bootstrap
    docker compose logs --tail=80 sing-box proxybox-admin proxybox-traffic-worker
    project="$(awk -F= '$1 == "COMPOSE_PROJECT_NAME" { print $2 }' .env | tail -n 1)"
    systemctl is-enabled "proxybox-docker-guard-${project}.timer" || true
    systemctl is-active "proxybox-docker-guard-${project}.timer" || true
    systemctl is-enabled "proxybox-docker-https-${project}.path" || true
    systemctl is-active "proxybox-docker-https-${project}.path" || true
  else
    systemctl is-active sing-box proxybox-admin proxybox-traffic-worker
    journalctl -u sing-box -u proxybox-admin -u proxybox-traffic-worker -n 80 --no-pager
  fi
EOF
```

The three core long-running services should be healthy: Docker mode shows them
as `Up`; native mode shows them as `active`. If any restarts repeatedly, triage
with Docker logs for Docker mode or `journalctl -u <service>` for native mode.

### Step 6 — Relay the install handoff

As of v0.1.6 the admin panel uses **username + password login**, not a
URL-token in the address bar. The installer output prints the one-shot handoff
block with:

- Login URL: `http://{public_host}:{admin_port}/login/{random_12char_suffix}`
- Username: `admin`
- Password: `<16-char alnum>`

**Do not re-mask the credentials in chat output for this skill.** The user
needs the first login URL and password to complete the install. The installer
output is the same private channel they would see when running it themselves.

If the user needs the credentials re-printed later, this fetches them from the
live install:

```bash
"${SSH[@]}" "$USER@$HOST" "cd '$REMOTE_INSTALL_DIR' && PROXYBOX_INSTALL_MODE='$PROXYBOX_INSTALL_MODE' bash -s" <<'EOF'
  if [ "$PROXYBOX_INSTALL_MODE" = "docker" ]; then
    docker compose exec proxybox-admin sh -c "
      echo password: \$(cat /etc/proxybox/admin.password)
      grep -E \"username|login_path|port:\" /etc/proxybox/config.yaml
    "
  else
    echo password: "$(cat /etc/proxybox/admin.password)"
    grep -E "username|login_path|port:" /etc/proxybox/config.yaml
  fi
EOF
```

### Step 7 — Optional: Telegram bot

Only do this if the user explicitly provided bot credentials and selected
Docker mode. Native mode has separate host-level bot configuration.

```bash
"${SSH[@]}" "$USER@$HOST" "REMOTE_INSTALL_DIR='$REMOTE_INSTALL_DIR' PROXYBOX_INSTALL_MODE='$PROXYBOX_INSTALL_MODE' BOT_TOKEN='$BOT_TOKEN' ALLOWED_USERS='$ALLOWED_USERS' bash -s" <<'EOF'
if [ "$PROXYBOX_INSTALL_MODE" != "docker" ]; then
  echo "[skip] Telegram bot automation in this skill is Docker-only"
  exit 0
fi
cd "$REMOTE_INSTALL_DIR"
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
EOF
```

Verify with `docker compose ps proxybox-bot`. If it crashed, check
`docker compose logs --tail=80 proxybox-bot` — most common cause is malformed
bot token format. Docker compose automatically supplies
`PROXYBOX_API_URL=http://proxybox-admin:8080` and the install-scoped
`PROXYBOX_BOT_INTERNAL_SECRET` from `.env`; do not add host ports for the bot.

### Step 8 — Hand off to the user

The installer summary block already lays everything out. Just relay it to the
user with a one-line cover sentence — something like:

> "装好了。下面四块全部直接能用：登录凭据（账号 + 密码 + 加随机后缀的
> 登录地址,粘进浏览器就行）、首台设备（进后台订阅链接页复制 URL）、
> 服务状态、可选功能。"

Then paste the installer output (or summarize it) — do not re-format, do not
hide the password / login URL. Do not include SSH host-key material in the handoff.

Concretely, the user can:

1. **Open the login URL in a browser**. The form auto-focuses the username
   field — type the username + password from the summary, hit 登录,
   arrive in the SPA. Session cookie is set for 30 days.
2. **Pick the subscription URL** that matches their client (table below;
   the install summary labels each line). Default URI list works for
   sing-box / Shadowrocket / Hiddify / Stash — pick `clash.yaml` for
   Clash family or `merlin.yaml` for routers.
3. **Paste** the default URL into the client's "Add Subscription" dialog.
   Shadowrocket `.conf` URLs are configuration profiles; import them from
   Shadowrocket's configuration/profile screen, not the node subscription form.
4. **Traffic should flow** through the VPS — `ifconfig.me` from the
   client device shows the VPS IP, not the home ISP.

The default first device name is 5 random lowercase letters. Override via env
`PROXYBOX_FIRST_DEVICE=tablet-1 bash deploy/install.sh --docker` before a Docker
install, or rename in the admin UI afterwards. `PROXYBOX_FIRST_DEVICE=` skips auto-creation.
`PROXYBOX_FIRST_DEVICE=local-user` is supported only when the user explicitly
asks for it; it uses `PROXYBOX_LOCAL_USERNAME` if provided, else the remote
shell user, sanitized to the device-name format.

### Stuff the user can do AFTER login (no SSH needed)

Mention any of these only when the user asks — don't dump them all at
handoff. v0.1.6+ exposes a lot in the panel:

- **HTTPS:** Docker installs can use the panel's HTTPS page. The container
  writes `.proxybox-guard/https-request`; the install-scoped host systemd
  `.path` helper validates DNS, installs/configures Caddy on the host, writes
  `.proxybox-guard/https-response`, then the container updates
  `server.public_host` and passkey origin fields. The helper refuses to
  overwrite a non-ProxyBox-managed `/etc/caddy/Caddyfile`, only trusts the
  Admin UI port from this install's `.env`, and best-effort opens ufw/firewalld
  80/443; in that case report the conflict instead of editing host Caddy by
  hand.
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
  shipped before v0.1.12. For a new install, clone the latest code into a
  fresh directory and install there. Do not run `git pull` inside a VPS path
  unless the user explicitly names that exact install as the one to upgrade.
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
URL, so it's safe to put in a router). Extension-suffixed variants
are generated on-the-fly from the same per-device row:

| URL suffix                | Format          | Tested clients                                    |
| ------------------------- | --------------- | ------------------------------------------------- |
| `/shadowrocket.yaml`      | Clash YAML      | Recommended Shadowrocket subscription with nodes + rules |
| `/clash.yaml`             | Mihomo / Clash  | Stash, Clash for iOS, Clash Verge (macOS/Win), Clash for Android |
| `/merlin.yaml`            | Clash + `tun:`  | AsusWRT-Merlin with Clash on the router (transparent proxy) |
| *(none, default)*         | URI list        | sing-box-iOS, Hiddify, generic URI-list clients |

If the user is in doubt on Shadowrocket, use `/shadowrocket.yaml` first. For
ordinary URI-list clients, use the default URL without a suffix.

## Anti-patterns (do NOT do these)

- **Installation red line:** never delete files or services on the user's VPS.
  The deploy flow may only touch ProxyBox resources created for this install,
  and must not touch any user data, files, services, containers, or volumes
  outside this install. On conflicts, pick different ports, create a new
  isolated instance, or fail clearly.
- **Never update an existing checkout during an install.** No `git -C`, no
  `git pull`, no branch checkout, no reuse of an old `.env`, and no reuse of
  existing Docker volumes. Even if `/opt/proxybox` already exists and looks
  like this repo, leave it alone and clone into a new
  `/opt/proxybox-<timestamp>-<suffix>` directory.
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
  install is being re-run. New installs create a new Compose project in the new
  source directory and leave older projects alone.

## Reporting failures

If a step fails, paste the failing command's output (with any tokens or
passwords masked) and stop. Don't attempt to brute-force around errors —
the user almost always has more context about their VPS than what's visible.
