<div align="right">

**English** · [中文](./README.zh.md)

</div>

# ProxyBox

> **A self-hosted, per-device-isolated proxy admin panel.** Every phone, laptop and
> router on your VPS gets its own VLESS Reality + Hysteria2 inbound, with byte-level
> traffic accounting, optional Telegram-bot control, optional WebAuthn passkey, and a
> one-click admin panel that handles HTTPS provisioning + credential rotation for
> you. MIT-licensed.

<!-- Status badges go here once the public release is announced (v0.2 candidates). -->

---

## ✨ What you get

- **Per-device inbounds** — every device has its own UUID + port pair. Leak one and
  you revoke it without rotating everyone else. (`config/sing-box.json` is rewritten
  per-device by `POST /api/devices/new`.)
- **VLESS Reality + Hysteria2** — one TCP path, one UDP path. Reality hides the
  inbound behind a real domain's TLS fingerprint (cloudflare / apple / microsoft
  picked at install). Hy2 picks up when UDP is the only thing not throttled.
- **5 subscription URL formats** per device, generated on the fly:
  - URI list (sing-box / Shadowrocket "Type: Subscribe" / Hiddify)
  - `clash.yaml` (Stash / Clash for iOS / Clash Verge)
  - `merlin.yaml` (AsusWRT-Merlin Clash + `tun:` block)
  - `shadowrocket.conf` (Surge `.conf` syntax)
  - `sub.txt` (plain `.txt` extension alias)
- **Real traffic accounting** — a worker polls sing-box's Clash API every 10 s and
  buckets bytes per device per hour into SQLite. The SPA renders 7-day per-device
  charts, an hourly heatmap, and a per-app-group breakdown (Video / Social / AI /
  CDN / 游戏 / Music / ...). CSV export available.
- **Username / password login** by default — the admin panel binds at
  `/login/{random_12char_suffix}`, `/login` itself returns 404, and the URL-path
  token is opt-in for automation (`features.url_token_bypass`). Rotate creds and
  the login path from the **安全 / Security** page in the panel.
- **HTTPS in the panel** — paste a domain in **HTTPS · 域名**, click 启用. The
  panel installs Caddy from the Cloudsmith stable repo, requests Let's Encrypt,
  writes a reverse-proxy `Caddyfile`, and reloads — typical 30 s. No SSH required.
- **Manual IP bans** — wraps fail2ban with `backend=systemd` (Debian 13 has no
  `/var/log/auth.log`), ban/unban from the panel or `POST /action/{block,unblock}`.
- **Optional Telegram bot** — `/status`, `/devices`, `/traffic`, `/pause`,
  `/resume`, `/bans` from your phone.
- **Optional WebAuthn passkey** — Touch ID / Face ID / hardware key in addition
  to the password (requires HTTPS).
- **Three deploy paths** — bash one-shot, Docker Compose, or **Claude Code does
  it for you** via the bundled skill.

## 🚀 Quick start

Pick the path that fits your setup.

### Path A — `install.sh` (Debian / Ubuntu VPS, recommended)

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox
bash deploy/install.sh --lang en        # or --lang zh
```

The script is idempotent. It auto-detects your public IP, generates a Reality
keypair + Hy2 cert + a random 16-char admin password, configures fail2ban + 4
systemd units, **auto-creates a first device** (default name `phone-1`, override
via `PROXYBOX_FIRST_DEVICE=tablet-1`), and prints a self-contained handoff:

```
🛡 admin credentials
    login URL  http://<your-vps>:8080/login/<random-12char>
    username   admin
    password   <16-char alnum, BOLD RED in your terminal>

📲 subscription URLs (phone-1)
    [pick this] http://<your-vps>:8080/api/sub/<sub-token>
    [Clash]     http://<your-vps>:8080/api/sub/<sub-token>/clash.yaml
    [router]    http://<your-vps>:8080/api/sub/<sub-token>/merlin.yaml
    [fallback]  http://<your-vps>:8080/api/sub/<sub-token>/shadowrocket.conf
    [.txt]      http://<your-vps>:8080/api/sub/<sub-token>/sub.txt
```

Copy the login URL + credentials into a password manager **before refreshing**.
The full password also lives in `/etc/proxybox/config.yaml` (`admin.password`).

### Path B — Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d                              # core stack
docker compose --profile bot up -d                # also start TG bot
docker compose exec proxybox-admin \
    sh -c 'grep -E "username|password|login_path" /etc/proxybox/config.yaml'
```

The `bootstrap` container generates configs on first start; volumes preserve
state across `docker compose down/up`. fail2ban is **not** included in this
path — use Caddy + a host firewall for production. Pre-built multi-arch
images (linux/amd64 + linux/arm64) are published at
`ghcr.io/carlos0xx/proxybox:latest` for every release.

### Path C — Claude Code does it ("proxybox-deploy" skill)

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

Then in a Claude Code session:

> deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519

Claude walks through pre-flight checks, `git clone`, `install.sh`, and relays
the credentials to you — same self-contained handoff as Path A.

## 📐 Architecture

```
┌─ Clients (iOS / Android / macOS / Win) ──────┐
│  sing-box · Shadowrocket · Hiddify · Stash   │
└──────────────────────┬───────────────────────┘
                       │ VLESS Reality (TCP 11001-11050, per device)
                       │ Hysteria2 (UDP 21001-21050, per device)
                       ▼
┌──────────────────────────────────────────────┐
│                  VPS                         │
│  ┌────────────────────────────────────────┐  │
│  │  sing-box (systemd)                    │◄─┼─ Reality + Hy2 inbounds per device
│  └──────────────────┬─────────────────────┘  │
│                     │ Clash API (127.0.0.1:9090)
│  ┌──────────────────▼─────────────────────┐  │
│  │  proxybox-traffic-worker               │  │   bytes  → traffic_log
│  │   polls /connections + /traffic        │  │   hosts  → host_log (v0.1.9+)
│  │   every 10 s → SQLite                  │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  proxybox-admin  (uvicorn / FastAPI)   │◄─┼─ admin API + SPA on :8080
│  │  · 40+ admin endpoints                 │  │   ────────────
│  │  · /login/{secret} username+password   │  │   login page (URL-path
│  │  · /admin/{token}/...  with cookie     │  │     token alone is opt-in)
│  │  · /api/sub/{sub_token}[/format]       │  │   public subscriptions
│  │  · /api/https/enable {domain}          │  │   1-click HTTPS provision
│  │  · /api/admin/account, /login-path     │  │   credential rotation
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  caddy (optional, v0.1.10+)            │  │   HTTPS reverse proxy with
│  │   reverse_proxy 127.0.0.1:8080         │  │   Let's Encrypt auto-renew
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  proxybox-bot      (opt-in, Telegram)  │  │
│  │  fail2ban          (manual IP jail)    │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

## 🧩 Configuration

Everything lives in `/etc/proxybox/config.yaml` (mode 0600, owned by root). See
[`config.example.yaml`](./config.example.yaml) for the full schema with inline
comments. Highlights:

| Key | What it sets |
| --- | --- |
| `admin.username` / `admin.password` | Browser login. install.sh generates a random 16-char password. |
| `admin.login_path` | 12-char random suffix on `/login`. Empty = legacy `/login` (still works). |
| `admin.token` | URL-path admin token (also a fallback API key when `features.url_token_bypass` is on). |
| `server.public_host` | Public IP/domain baked into subscription URIs. install.sh auto-fills; `enable-https.sh` rewrites to your domain. |
| `ports.vless_range` / `hy2_range` | Per-device port pools (default 11001-11050 TCP / 21001-21050 UDP). |
| `clash.api_url` | sing-box Clash API endpoint (default `127.0.0.1:9090`). |
| `worker.poll_interval` / `retention_days` | Traffic accounting cadence + retention. |
| `features.passkey` / `features.bot` | Opt-in WebAuthn / Telegram bot. |
| `features.url_token_bypass` | When true, the URL-path token alone authenticates. **Default false** — login form required. |
| `services.monitored` | Which systemd units `GET /api/status` reports on. |

## 🔐 Security model

- **No SaaS dependency.** Everything runs on the user's VPS; no phone-home, no
  shared control plane.
- **Username + password login (default)** with a session cookie issued by
  `/login/{random-suffix}`. The `/login` path itself 404s — bots probing common
  paths can't even confirm the form exists.
- **Per-device credentials.** Leaking one device's UUID/Hy2 password doesn't
  affect others. Revoke + regen-subs cleanly cuts off compromised devices.
- **Constant-time secret comparison** (`secrets.compare_digest`) on every
  credential check.
- **Atomic config writes** — config rotation uses tmp+rename so an aborted
  process can never leave a truncated `config.yaml`.
- **HTTP by default.** Wrap with Caddy + Let's Encrypt for production. The
  HTTPS panel does this in one click; the `enable-https.sh` CLI does the same
  thing for scripted installs.
- **All admin endpoints require both the session cookie AND a matching URL-path
  token.** Defense-in-depth — a stolen cookie can't be replayed against an
  instance on a different host.

## 🛣️ Status

| Version | Highlights |
| --- | --- |
| v0.1.0 | initial release: install.sh, Docker, Claude skill, 34 admin endpoints, 5 GHA workflows |
| v0.1.1 → v0.1.5 | SPA reconciliation with the v0.1.x server (BWG-port migration), multi-format subscription URLs, real `/api/connections` proxy |
| v0.1.6 | username/password login + URL-token bypass off by default |
| v0.1.7 → v0.1.8 | history page hardening, clipboard works on HTTP, roomier sub-link layout |
| v0.1.9 | host categorisation (default-on), `enable-https.sh` CLI |
| v0.1.10 | **HTTPS provisioning from the admin UI** |
| v0.1.11 | change username / password / rotate login path from the admin UI |
| v0.1.12 | copy-button quote-collision fix; clipboard fallback hardened |
| v0.2 (planned) | SPA English translation · passkey browser E2E · demo screencast |

`scripts/release-audit.sh` enforces 7 gates on every tag: clean tree, PII
blocklist on tracked files, gitleaks on git history, identity check on
commit metadata, blocklist on commit-message bodies, version sanity,
CHANGELOG presence.

## 📖 More docs

- [`docs/guide.md`](./docs/guide.md) — install + day-to-day usage walkthrough.
- [`docs/architecture.md`](./docs/architecture.md) — full architecture deep dive.
- [`docs/api/`](./docs/api/) — endpoint reference per router.
- [`docs/deploy/`](./docs/deploy/) — deploy paths in detail.
- [`CHANGELOG.md`](./CHANGELOG.md) — per-version changes (Keep-a-Changelog).

## 📜 License

MIT — see [`LICENSE`](./LICENSE).
