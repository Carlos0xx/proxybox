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

```bash
ssh "$USER@$HOST" '
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

This is idempotent — re-running it on an already-installed system does
nothing destructive. Capture the output, but do **not** quote any line that
contains an `admin URL: http://...` — the URL contains the token prefix
which is fine, but echoing the full URL elsewhere is not. The script itself
only prints the first 8 chars, so quoting its output as-is is safe.

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

### Step 5 — Read public IP + token (carefully)

```bash
ssh "$USER@$HOST" '
  /opt/proxybox/.venv/bin/python -c "
import yaml
c = yaml.safe_load(open(\"/etc/proxybox/config.yaml\"))
token = c[\"admin\"][\"token\"]
host = c[\"server\"][\"public_host\"] or \"<your-vps-ip>\"
print(f\"URL: http://{host}:8080/admin/{token[:8]}...\")
print(f\"TOKEN_LEN: {len(token)}\")
print(f\"TOKEN_PREFIX: {token[:8]}...\")
"
'
```

Note: use the **venv python** (`/opt/proxybox/.venv/bin/python`), not
system `python3`. Debian minimal does not ship `python3-yaml`; the venv
installed by `install.sh` already has `pyyaml` as a ProxyBox dep.

Report back **only** the prefix + URL with truncated token. Tell the user
the full token is in `/etc/proxybox/config.yaml` on the VPS and they should
copy it locally (e.g. into a password manager) before sharing the URL with
anyone.

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

Tell them, in this order:

1. Where the admin URL is (with token prefix only)
2. Where the full token lives on the VPS
3. They should set up Caddy + Let's Encrypt before exposing the URL beyond
   trusted networks — current setup is HTTP only
4. Next steps inside the admin UI: create their first device, copy the
   subscription URL, paste into a sing-box-compatible client (Shadowrocket
   on iOS, sing-box-for-android, Hiddify on desktop)

## Anti-patterns (do NOT do these)

- **Never** echo the full admin token in chat output. Always mask to first
  8 chars + `...`
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
