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

### Step 1 — Pre-flight

After Step 2 has run (so `/opt/proxybox/deploy/check-prereqs.sh` exists on
the host), use the bundled checker — it's exhaustive (9 categories) and
returns a clean exit code:

```bash
ssh "$USER@$HOST" 'bash /opt/proxybox/deploy/check-prereqs.sh'
```

If it exits non-zero, paste the output back to the user and **stop** —
don't try to "fix" their environment unless they explicitly ask.

For the **first** SSH after the user gave us VPS credentials (before
Step 2 has cloned the repo), do a minimal in-line check first:

```bash
ssh -o BatchMode=yes "$USER@$HOST" bash -s <<'EOF'
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
idempotent — re-running it on a fully-provisioned host is a no-op.

```bash
ssh "$USER@$HOST" '
  # bootstrap tools that may be missing on a minimal Debian / Ubuntu cloud image
  apt-get update -qq && apt-get install -y -qq git curl ca-certificates

  if [ -d /opt/proxybox/.git ]; then
    cd /opt/proxybox && git pull --ff-only
  elif [ -d /opt/proxybox ] && [ -n "$(ls -A /opt/proxybox 2>/dev/null)" ]; then
    echo "[skip] /opt/proxybox exists but is not a git checkout — leaving it alone"
    echo "       if you want a fresh start, ssh in and: rm -rf /opt/proxybox, then re-run"
  else
    git clone https://github.com/carlos0xx/proxybox /opt/proxybox
  fi
'
```

If the user is on Ubuntu's minimal image and the SSH session is not root,
prefix the `apt-get` lines with `sudo`. The git-clone itself runs as the
SSH user — clone into `/opt/proxybox` will need root anyway on most images.

### Step 3 — Run install.sh

```bash
ssh "$USER@$HOST" '
  cd /opt/proxybox
  if [ "$(id -u)" = "0" ]; then
    bash deploy/install.sh --lang $LANG_FLAG
  else
    sudo bash deploy/install.sh --lang $LANG_FLAG
  fi
'
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
final summary verbatim — Step 5 / Step 7 below explain why the full
admin URL is okay to quote in this context.

### Step 4 — Verify

```bash
ssh "$USER@$HOST" '
  for svc in sing-box proxybox-admin proxybox-traffic-worker fail2ban; do
    state=$(systemctl is-active "$svc" 2>/dev/null)
    printf "%-30s %s\n" "$svc" "$state"
  done
'
```

All four should be `active`. If any is not, fetch its `journalctl -u <svc> -n
30 --no-pager` and triage.

### Step 5 — Relay the install.sh summary

As of v0.1.2 `install.sh` ends with a self-contained handoff block:
- The full admin URL (with the live token — not masked)
- The auto-created first device (default name `phone-1`, override via env
  `PROXYBOX_FIRST_DEVICE=<name>` before re-running)
- All 5 per-device subscription URLs ready to copy

**Do not re-mask the token in chat output for this skill.** The whole
point of v0.1.2's one-shot UX is to avoid making普通用户 SSH back in to
grep config.yaml. The install.sh output is the user's private channel
(same as if they ran the installer locally) — relay it verbatim.

This rule is **scoped to install.sh output and this Step 5 / Step 7
handoff.** Ad-hoc bash you author elsewhere in a session (e.g. for
debugging or status checks) should still mask the token to first 8 chars,
because that's chat-only output that doesn't have the same one-shot UX
constraint.

If the user needs the URL re-printed later (e.g. they lost the chat
backscroll), this fetches it from the live config:

```bash
ssh "$USER@$HOST" '
  /opt/proxybox/.venv/bin/python -c "
import yaml
c = yaml.safe_load(open(\"/etc/proxybox/config.yaml\"))
token = c[\"admin\"][\"token\"]
host  = c[\"server\"][\"public_host\"] or \"<your-vps-ip>\"
print(f\"http://{host}:8080/admin/{token}/\")
"
'
```

### Step 6 — Optional: Telegram bot

Only do this if the user explicitly provided bot credentials.

```bash
ssh "$USER@$HOST" "
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

### Step 7 — Hand off to the user

The install.sh summary block already lays everything out. Just relay it
to the user with a one-line cover sentence — something like:

> "装好了。下面 4 块都是直接能用的：管理后台 URL（带 token，登录就进）、
> 5 个订阅 URL（任挑一个粘进客户端就翻墙）、服务状态、可选功能。"

Then paste install.sh's output (or summarize it) — do not re-format
or hide the admin URL.

Concretely, the user can:
1. Open the admin URL in a browser → already logged in via the URL-path token
2. Pick the subscription URL that matches their client (table below for
   reference; the install summary already labels each line)
3. Paste it into the client's "Add Subscription" dialog
4. Done — traffic should flow through the VPS

The default first device is named `phone-1`. To bootstrap a different
name (e.g. `tablet-1` for an iPad-first user), re-run install.sh with
`PROXYBOX_FIRST_DEVICE=tablet-1` in the environment, or rename in the
admin UI afterwards.

If the user wants extra devices (one per gadget for proper isolation),
they create them from 设备管理 / Devices → 生成 / Create. Generic
naming convention: `phone-1`, `phone-2`, `tablet-1`, `laptop-1`,
`home-router`. **Never use personal identifiers** — device names go
into sing-box config + subscription file content, so they're surface
for fingerprinting.

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
  including the full admin URL. (Re-masking the token defeats v0.1.2's
  one-shot UX.) But: ad-hoc bash you author later in the same session
  for status checks / debugging still masks to first 8 chars.
- **Never** SSH with `-o StrictHostKeyChecking=no` without the user's
  explicit consent — it disables host-key warnings and would mask MITM
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
