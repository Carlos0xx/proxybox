<div align="right">

**English** · [中文](./README.zh.md)

</div>

<h1 align="center">ProxyBox</h1>

<p align="center">
  Self-hosted, per-device proxy admin panel.<br>
  One VLESS Reality + Hysteria2 pair per device · byte-level accounting · Docker-first install · MIT.
</p>

<p align="center">
  <a href="#install"><strong>Install</strong></a> ·
  <a href="#repository-layout">Repo layout</a> ·
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
| 🔒 &nbsp; **HTTPS options** | Docker path expects an external reverse proxy / tunnel; native mode can still provision Caddy + Let's Encrypt from the panel. |
| 🐳 &nbsp; **Docker-first install** | Bridge-network stack, auto-selected free host ports, no host Python/systemd/fail2ban writes. |
| 🤖 &nbsp; **Optional Telegram bot** | `/status` · `/devices` · `/traffic` · `/pause` · `/resume` · `/bans` from your phone. |

---

## Install

### A · Docker install *(recommended)*

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox && bash deploy/docker-install.sh
```

`deploy/docker-install.sh` installs/starts Docker, Compose, and the port scanner if missing, scans host ports, keeps the defaults when free, otherwise picks a free admin port and free VLESS/Hy2 port blocks, then prints and writes them to `.env`. Every installer run creates a new isolated Compose project name and new Docker volumes, so admin paths, passwords, keys, and subscription URLs are regenerated without deleting any older ProxyBox projects. The stack uses Docker bridge networking and only publishes those selected ports; it does not install or rewrite host Python, ProxyBox systemd units, fail2ban, Caddy, SSH known_hosts, or unrelated services. If the device list is empty, it auto-creates one random five-letter lowercase device.

To upgrade the current project in place instead of creating a fresh project:

```bash
cd /opt/proxybox
git pull
PROXYBOX_UPGRADE=1 bash deploy/docker-install.sh
```

### B · Claude Code / Codex

Let an AI coding agent drive the install over SSH. For Claude Code, install the bundled skill once:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

Then in any session: *"deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519"*. The agent uses an auto-deleted temporary SSH `known_hosts` → runs a minimal VPS check → `git clone` / update → Docker port pre-flight → `deploy/docker-install.sh` → service verification → hands back the login URL + credentials.

For Codex or other agents, point them at [`deploy/claude-skill/SKILL.md`](./deploy/claude-skill/SKILL.md) — the instructions are framework-agnostic.

### C · `install.sh` *(advanced native mode)*

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox && bash deploy/install.sh --fresh
```

Fresh mode clears old ProxyBox-managed state first, then generates a Reality keypair, Hy2 cert, random 16-char admin password, and a random five-letter first device. Omit `--fresh` only when intentionally preserving an existing ProxyBox install.

> [!IMPORTANT]
> The installer prints login URL + password **once**. Copy them into a password manager before closing the terminal. Docker recovery: `cd /opt/proxybox && docker compose exec proxybox-admin sh -c 'cat /etc/proxybox/admin.password; grep -E "username|login_path" /etc/proxybox/config.yaml'`.

---

## Repository layout

```text
.
├── app/        Admin backend — FastAPI service, SQLite, sing-box config writer
├── bot/        Mobile control surface — Telegram alternative to the web UI
├── static/     Web UI — Chinese single-file SPA served by the backend
├── deploy/     Provisioning + ops — installer, pre-flight, HTTPS, AI skill
├── docs/       User documentation — guide · architecture · API · deploy
├── scripts/    Release gates — PII blocklist + 7-step audit
└── tests/      Regression coverage — config loader, subscriptions, traffic worker
```

For service-by-service internals see [`docs/architecture.md`](./docs/architecture.md).

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
