<div align="right">

**English** · [中文](./README.zh.md)

</div>

<h1 align="center">ProxyBox</h1>

<p align="center">
  Self-hosted, per-device proxy admin panel.<br>
  One VLESS Reality + Hysteria2 pair per device · byte-level accounting · 1-click HTTPS · MIT.
</p>

<p align="center">
  <a href="#install"><strong>Install</strong></a> ·
  <a href="#architecture">Architecture</a> ·
  <a href="./docs/guide.md">Guide</a>
</p>

---

## Features

| | |
| :--- | :--- |
| 🔐 &nbsp; **Per-device inbounds** | Each device gets its own UUID + TCP/UDP port pair. Revoke one without rotating everyone else. |
| 🌐 &nbsp; **VLESS Reality + Hysteria2** | TCP path hidden behind a real domain's TLS fingerprint; UDP path takes over when TCP is throttled. |
| 📲 &nbsp; **5 subscription formats** | URI list · `clash.yaml` · `merlin.yaml` · `shadowrocket.conf` · `sub.txt` — generated server-side per device. |
| 📊 &nbsp; **Real traffic accounting** | Worker polls sing-box's Clash API every 10 s. SQLite buckets bytes per device × hour and tags hosts (Video / Social / AI / CDN / …). |
| 🔑 &nbsp; **Username + password login** | Form at `/login/{12-char-suffix}`; bare `/login` 404s. Rotate password + login path from the panel — no SSH. |
| 🔒 &nbsp; **1-click HTTPS** | Enter a domain → click *Enable* → Caddy + Let's Encrypt provisioned in ~30 s. |
| 🌏 &nbsp; **Bilingual UI** | Topbar language switcher (Chinese / English). Login form also bilingual via `?lang=`. |
| 🤖 &nbsp; **Optional Telegram bot** | `/status` · `/devices` · `/traffic` · `/pause` · `/resume` · `/bans` from your phone. |

---

## Install

### A · `install.sh` *(recommended, Debian / Ubuntu VPS)*

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox && bash deploy/install.sh
```

Idempotent. Generates Reality keypair, Hy2 cert, random 16-char admin password. Auto-creates the first device. Prints **login URL · username · password · 5 subscription URLs** in a single block.

### B · Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d
```

Multi-arch images at `ghcr.io/carlos0xx/proxybox:latest`. No fail2ban or HTTPS UI on this path — pair with Caddy + a host firewall for production.

### C · Claude Code skill

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

Then in a Claude Code session: *"deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519"*. Claude runs pre-flight + `install.sh` + verification + credential handoff.

> [!IMPORTANT]
> The installer prints login URL + password **once**. Copy them into a password manager before closing the terminal — they are also stored in `/etc/proxybox/config.yaml`.

---

## Architecture

```text
Clients (sing-box · Shadowrocket · Hiddify · Stash · Clash)
    │ VLESS Reality (TCP 11001-11050, per device)
    │ Hysteria2     (UDP 21001-21050, per device)
    ▼
┌─────────────────────────────────────────────────────────┐
│ VPS                                                     │
│                                                         │
│  sing-box                  (systemd)                    │
│       │ Clash API 127.0.0.1:9090                        │
│       ▼                                                 │
│  proxybox-traffic-worker   polls every 10 s → SQLite    │
│  proxybox-admin            FastAPI on :8080             │
│  caddy           [opt-in]  HTTPS reverse-proxy          │
│  proxybox-bot    [opt-in]  Telegram long-poll           │
│  fail2ban                  manual IP jail               │
│                                                         │
│           /var/lib/proxybox/traffic.db                  │
│           device · traffic_log · host_log               │
└─────────────────────────────────────────────────────────┘
```

Deep dive: [`docs/architecture.md`](./docs/architecture.md).

---

## Documentation

| | |
| --- | --- |
| [Guide](./docs/guide.md) | Install + day-to-day usage |
| [Architecture](./docs/architecture.md) | Service-by-service deep dive |
| [API](./docs/api/) | Per-router endpoint reference |
| [Deploy](./docs/deploy/) | The three install paths in detail |

---

## License

MIT — see [`LICENSE`](./LICENSE).
