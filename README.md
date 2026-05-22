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
| 📲 &nbsp; **Subscription formats** | Shadowrocket split config · `clash.yaml` · `merlin.yaml` · default URI list — generated server-side per device. |
| 📊 &nbsp; **Real traffic accounting** | Worker polls sing-box's Clash API every 10 s. SQLite buckets bytes per device × hour and tags hosts (Video / Social / AI / CDN / …). |
| 🔑 &nbsp; **Username + password login** | Form at `/login/{12-char-suffix}`; bare `/login` 404s. Rotate password + login path from the panel — no SSH. |
| 🔒 &nbsp; **HTTPS options** | Docker installs can enable host Caddy + Let's Encrypt from the panel through an install-scoped helper; native mode provisions Caddy directly. |
| 🐳 &nbsp; **Docker-first install** | Bridge-network stack, auto-selected free host ports, install-scoped Docker guard, and HTTPS helper. |
| 🤖 &nbsp; **Optional Telegram bot** | `/status` · `/devices` · `/traffic` · `/pause` · `/resume` · `/bans` from your phone. |

---

## Install

### A · Interactive install *(Docker recommended)*

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR" && bash deploy/install.sh
```

Running `deploy/install.sh` without arguments shows a Chinese mode picker for **Docker install** or **native install** and requires an explicit `1` or `2` choice. Pick Docker for container isolation, automatic port selection, an install-scoped Docker guard, and an HTTPS helper that only runs when you enable HTTPS from the panel. If the VPS already runs websites, panels, or production services, use Docker. Native install writes Python, sing-box, systemd units, and fail2ban directly to the host; only use it on a clean dedicated VPS.

Direct mode selection:

```bash
bash deploy/install.sh --docker
bash deploy/install.sh --native --fresh --lang zh
```

Docker install provisions Docker/Compose and the port scanner if missing, scans host ports, writes `.env`, and creates fresh Compose project volumes, credentials, keys, and subscription URLs without deleting any older ProxyBox project.

> [!IMPORTANT]
> Installation red line: never delete, modify, overwrite, or reuse files/services on the user's VPS outside this install. Even if `/opt/proxybox` or another same-name directory already exists, leave it untouched, clone into a new `proxybox-<timestamp>-<suffix>` directory, and only touch resources created for this run.

Upgrades are not installs. Only run an in-place upgrade when you explicitly choose the exact existing ProxyBox install directory; the normal install flow always creates a new directory and a new isolated Docker project.

### B · Claude Code / Codex

Let an AI coding agent drive the install over SSH. For Claude Code, install the bundled skill once:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

Then in any session: *"deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519"*. The agent must ask you to choose Docker or native first; Docker already being installed, recommended, or a better fit for the ports is not consent. After your explicit answer, it uses an auto-deleted temporary SSH `known_hosts` → runs a minimal VPS check → clones into a new install directory → runs `deploy/install.sh --docker` or `deploy/install.sh --native --fresh` → service verification → hands back the login URL + credentials.

For Codex or other agents, point them at [`deploy/claude-skill/SKILL.md`](./deploy/claude-skill/SKILL.md) — the instructions are framework-agnostic.

### C · Native install *(advanced mode)*

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR" && bash deploy/install.sh --native --fresh
```

Native `--fresh` now means "new native install only": it generates a Reality keypair, Hy2 cert, random 16-char admin password, and a random five-letter first device only when no previous native ProxyBox/sing-box state is present. If old state exists, the installer refuses to continue rather than deleting it. Destructive cleanup is a separate advanced operation: `--purge-existing-proxybox` plus an explicit `DELETE PROXYBOX` confirmation.

> [!IMPORTANT]
> The installer prints login URL + password **once**. Copy them into a password manager before closing the terminal. Docker recovery: `cd <proxybox-install-dir> && docker compose exec proxybox-admin sh -c 'cat /etc/proxybox/admin.password; grep -E "username|login_path" /etc/proxybox/config.yaml'`.

---

## Repository layout

```text
.
├── app/        Admin backend — FastAPI service, SQLite, sing-box config writer
├── bot/        Mobile control surface — Telegram alternative to the web UI
├── static/     Web UI — Chinese single-file SPA served by the backend
├── deploy/     Provisioning + ops — installer, pre-flight, HTTPS, AI skill
├── docs/       User documentation — guide · architecture · API · deploy
├── scripts/    Release gates — PII blocklist + audit checks
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
