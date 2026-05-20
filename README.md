<div align="right">

**English** · [中文](./README.zh.md)

</div>

<h1 align="center">ProxyBox</h1>

<p align="center">
  A self-hosted, per-device-isolated proxy admin panel.<br>
  Each device gets its own VLESS Reality + Hysteria2 inbound on your VPS, with byte-level traffic accounting,<br>
  one-click HTTPS, optional Telegram-bot control, optional WebAuthn passkey — all under MIT license.
</p>

<p align="center">
  <a href="#-quick-start">Quick start</a> ·
  <a href="./docs/guide.md">Guide</a> ·
  <a href="./docs/architecture.md">Architecture</a> ·
  <a href="./docs/api/">API</a> ·
  <a href="./CHANGELOG.md">Changelog</a>
</p>

---

## ✨ Features

| | |
| :--- | :--- |
| 🔐 &nbsp; **Per-device inbounds** | Every device has its own UUID + TCP/UDP port pair. Revoke one device without rotating everyone else. |
| 🌐 &nbsp; **VLESS Reality + Hysteria2** | TCP path hidden behind a real domain's TLS fingerprint; UDP path picks up when TCP is throttled. |
| 📲 &nbsp; **5 subscription formats** | URI list · `clash.yaml` · `merlin.yaml` · `shadowrocket.conf` · `sub.txt` — generated on the fly per device. |
| 📊 &nbsp; **Real traffic accounting** | Background worker polls sing-box's Clash API every 10 s. SQLite buckets bytes per device per hour and tags hosts into categories (Video / Social / AI / CDN / 游戏 / ...). |
| 🔑 &nbsp; **Username + password login** | Login form at `/login/{random-12-char-suffix}` — `/login` itself returns 404 to deter brute-force bots. URL-path token is opt-in for automation. |
| 🔒 &nbsp; **HTTPS in the panel** | Enter a domain → click 启用 → Caddy + Let's Encrypt provisioned in ~30 s. No SSH needed. |
| 🌏 &nbsp; **Bilingual UI** | Topbar `中 / EN` toggle. ~80% English coverage with graceful Chinese fallback. Login form also bilingual via `?lang=`. |
| 🤖 &nbsp; **Optional Telegram bot** | `/status` · `/devices` · `/traffic` · `/pause` · `/resume` · `/bans` from your phone. |
| 🛡️ &nbsp; **Optional WebAuthn passkey** | Touch ID / Face ID / hardware key (requires HTTPS). |
| 🚀 &nbsp; **Three deploy paths** | Bash one-shot · Docker Compose · Claude Code skill drives the install for you. |

---

## 🚀 Quick start

### Path A — `install.sh` &nbsp;<sub>(recommended, Debian / Ubuntu VPS)</sub>

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox
bash deploy/install.sh --lang en        # or --lang zh
```

The script is idempotent. It auto-detects the VPS public IP, generates a Reality keypair + Hy2 cert + random 16-char admin password, installs 4 systemd units, auto-creates a first device, and prints a self-contained handoff:

```
🛡 admin credentials
   login URL  http://<your-vps>:8080/login/<random-12char>
   username   admin
   password   <16-char alnum>

📲 subscription URLs (phone-1)
   [pick this] http://<your-vps>:8080/api/sub/<sub-token>
   [Clash]     http://<your-vps>:8080/api/sub/<sub-token>/clash.yaml
   [router]    http://<your-vps>:8080/api/sub/<sub-token>/merlin.yaml
   [fallback]  http://<your-vps>:8080/api/sub/<sub-token>/shadowrocket.conf
   [.txt]      http://<your-vps>:8080/api/sub/<sub-token>/sub.txt
```

> [!IMPORTANT]
> Copy the login URL + credentials into a password manager **before closing the terminal**.
> They are also stored in `/etc/proxybox/config.yaml` (`admin.password` / `admin.login_path`).

### Path B — Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d                              # core stack
docker compose --profile bot up -d                # also start TG bot
docker compose exec proxybox-admin \
    sh -c 'grep -E "username|password|login_path" /etc/proxybox/config.yaml'
```

A `bootstrap` container generates config on first start; volumes preserve state across `down`/`up`. Pre-built multi-arch images (linux/amd64 + linux/arm64) land at `ghcr.io/carlos0xx/proxybox:latest` on every release.

> [!NOTE]
> fail2ban and the HTTPS auto-provisioning UI are not included on the Docker path — pair with Caddy + a host firewall for production.

### Path C — Claude Code

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

Then in a Claude Code session:

> deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519

Claude walks through pre-flight, `git clone`, `install.sh`, and relays the credentials. See [`docs/deploy/claude-skill.md`](./docs/deploy/claude-skill.md).

---

## 📐 Architecture

```text
┌─ Clients (iOS · Android · macOS · Windows) ───┐
│  sing-box · Shadowrocket · Hiddify · Stash    │
└───────────────────────┬───────────────────────┘
                        │ VLESS Reality (TCP 11001-11050, per device)
                        │ Hysteria2     (UDP 21001-21050, per device)
                        ▼
┌───────────────────────────────────────────────┐
│                    VPS                        │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  sing-box  (systemd)                    │◄─┼─ per-device Reality + Hy2 inbounds
│  └────────────────┬────────────────────────┘  │
│                   │ Clash API (127.0.0.1:9090)
│  ┌────────────────▼────────────────────────┐  │
│  │  proxybox-traffic-worker                │  │  bytes → traffic_log
│  │   polls /connections + /traffic every   │  │  hosts → host_log
│  │   10 s, writes to SQLite                │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  proxybox-admin  (uvicorn / FastAPI)    │◄─┼─ admin API + SPA on :8080
│  │   · /login/{secret}  — username+pwd     │  │
│  │   · /admin/{token}/... — cookie + token │  │
│  │   · /api/sub/{sub_token}[/format]       │  │  ← public subscription URLs
│  │   · /api/https/enable {domain}          │  │  ← 1-click HTTPS provision
│  │   · /api/admin/account, /login-path     │  │  ← credential rotation
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  caddy  (optional, v0.1.10+)            │  │  HTTPS reverse-proxy
│  │   reverse_proxy 127.0.0.1:8080          │  │  Let's Encrypt auto-renew
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  proxybox-bot   (opt-in, Telegram)      │  │
│  │  fail2ban       (manual IP jail)        │  │
│  └─────────────────────────────────────────┘  │
└───────────────────────────────────────────────┘
```

Deep dive: [`docs/architecture.md`](./docs/architecture.md).

---

## 🧩 Configuration

All settings live in `/etc/proxybox/config.yaml` (mode 0600, owned by root). Full schema with inline comments: [`config.example.yaml`](./config.example.yaml).

| Key | Effect |
| --- | --- |
| `admin.username` / `admin.password` | Browser login. `install.sh` generates a random 16-char password. |
| `admin.login_path` | 12-char random suffix on `/login`. Empty = legacy `/login` works. |
| `admin.token` | URL-path admin token. Also accepted as an API key when `features.url_token_bypass` is on. |
| `server.public_host` | Baked into subscription URIs. Auto-filled by `install.sh`; `enable-https.sh` rewrites to your domain. |
| `ports.vless_range` / `hy2_range` | Per-device port pools (default `11001-11050 TCP` / `21001-21050 UDP`). |
| `clash.api_url` | sing-box Clash API endpoint (default `127.0.0.1:9090`). |
| `worker.poll_interval` / `retention_days` | Traffic accounting cadence + retention. |
| `features.passkey` / `features.bot` | Opt-in WebAuthn / Telegram bot. |
| `features.url_token_bypass` | When `true`, URL-path token alone authenticates. **Default `false`** — login form required. |
| `services.monitored` | Which systemd units `GET /api/status` reports on. |

---

## 🔐 Security model

- **No SaaS dependency.** Everything runs on the user's VPS — no phone-home, no shared control plane.
- **Username + password by default.** Session cookie issued by `/login/{random-suffix}`. The bare `/login` path 404s — bots probing common paths can't even confirm the form exists.
- **Per-device credentials.** Leaking one device's UUID/Hy2 password doesn't affect others. Revoke + regen-subs cleanly cuts off compromised devices.
- **Constant-time secret comparison** (`secrets.compare_digest`) on every credential check.
- **Atomic config writes** — `config.yaml` rotation uses `tmp + rename`; an aborted process can never leave a truncated config.
- **HTTP by default**, HTTPS one click away via the admin UI or `deploy/enable-https.sh <domain>`.
- **Defense in depth** — every admin endpoint requires *both* a valid session cookie AND a matching URL-path token. A stolen cookie can't be replayed against an instance on a different host.

---

## 🛣️ Releases

| Version | Highlights |
| --- | --- |
| **v0.2.0** | Bilingual SPA + login form. Topbar `中 / EN` switcher. |
| v0.1.10 → v0.1.12 | HTTPS provisioning from the UI · username/password & login-path rotation in the panel · clipboard fixes |
| v0.1.7 → v0.1.9 | History page hardening · 5-format subscription URLs · host categorisation default-on |
| v0.1.6 | Username/password login replaces URL-token-only auth as the default |
| v0.1.1 → v0.1.5 | SPA reconciliation after the v0.1.x BWG → ProxyBox port · `/api/connections` proxy |
| v0.1.0 | Initial release — install.sh, Docker, Claude skill, 5 GHA workflows, 7-check release audit |

Per-release detail in [`CHANGELOG.md`](./CHANGELOG.md). The `scripts/release-audit.sh` gate enforces clean tree · PII blocklist · gitleaks · committer identity · commit-message blocklist · version sanity · CHANGELOG presence on every tag.

---

## 📖 Documentation

| | |
| --- | --- |
| [Guide](./docs/guide.md) | Install + day-to-day usage walkthrough |
| [Architecture](./docs/architecture.md) | Service-by-service deep dive |
| [API](./docs/api/) | Per-router endpoint reference |
| [Deploy](./docs/deploy/) | The three deploy paths in detail |
| [Changelog](./CHANGELOG.md) | Per-version changes (Keep-a-Changelog) |

---

## 📜 License

MIT — see [`LICENSE`](./LICENSE).
