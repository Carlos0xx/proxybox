# Getting started

> Install ProxyBox on a fresh VPS, log in, get the first client routing through it — typically under 10 minutes.

For a higher-level walkthrough of day-to-day operations after install, see [`guide.md`](./guide.md). For the architecture, see [`architecture.md`](./architecture.md).

---

## Prerequisites

| Requirement | Detail |
| --- | --- |
| **OS** | Debian / Ubuntu VPS. Docker path can run on an existing host. Native path still expects a clean VPS. |
| **Access** | Root SSH or passwordless sudo. The Docker installer installs/starts Docker and Compose if missing. |
| **Resources** | ≥ 1 GB RAM · ≥ 5 GB free disk. |
| **Required ports** | Docker installer auto-selects free Admin, VLESS, and Hy2 ports and writes them to `.env`. |
| **For HTTPS later** | A domain pointing at the VPS · `80/tcp` + `443/tcp` open. Optional but recommended for production. |

---

## Path 1 — Interactive install &nbsp;<sub>(Docker recommended)</sub>

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR"
bash deploy/install.sh
```

`deploy/install.sh` shows a Chinese mode picker and requires an explicit `1` or `2` choice. Pick Docker to check Docker/Compose and `ss`/`iproute2`, install missing runtime packages, start Docker, scan host ports, write `.env`, start an isolated bridge-network stack, and install narrow Docker guard + HTTPS helper units for this project only. Use Docker if the VPS already runs websites, panels, or production services. Native install writes Python, sing-box, systemd units, and fail2ban directly to the host; only use it on a clean dedicated VPS.

> [!IMPORTANT]
> Installation red line: never delete, modify, overwrite, or reuse files/services on the user's VPS outside this install. Even if `/opt/proxybox` or another same-name directory already exists, leave it untouched, clone into a new `proxybox-<timestamp>-<suffix>` directory, and only touch resources created for this run.

Upgrades are not installs. Only run an in-place upgrade when you explicitly choose the exact existing ProxyBox install directory; the normal install flow always creates a new directory and a new isolated Docker project.

Full reference: [`deploy/docker.md`](./deploy/docker.md).

---

## Path 2 — Claude Code / Codex

Let an AI coding agent drive the install over SSH. Lowest-friction option if you already have Claude Code or Codex open.

For **Claude Code**, install the bundled skill once:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

Then in any session:

> deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519

The agent must ask you to choose Docker or native first. Docker already being installed, recommended, or a better fit for the ports is not consent. After your explicit answer, it uses an auto-deleted temporary SSH `known_hosts`, runs a minimal VPS check, clones the repo into a fresh per-install directory on the VPS, executes `deploy/install.sh --docker` or `deploy/install.sh --native --fresh`, verifies the core services, and relays the **login URL, username, password, and first device status** back to you.

For **Codex** or other coding agents, point them at [`deploy/claude-skill/SKILL.md`](../deploy/claude-skill/SKILL.md) — the instructions are framework-agnostic.

Full reference: [`deploy/claude-skill.md`](./deploy/claude-skill.md).

---

## Path 3 — `install.sh` &nbsp;<sub>(advanced native mode)</sub>

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR"
bash deploy/install.sh --native --fresh --lang en        # --lang zh for Chinese output
```

Native `--fresh` is a safety gate for new host-level installs: it proceeds only when no previous ProxyBox/sing-box native state is present. If old state exists, the installer refuses to continue rather than deleting it. The install performs:

1. **Pre-flight validation** via `deploy/check-prereqs.sh --install` (9 categories: OS, arch, privilege, RAM, disk, network, systemd, ports, apt deps) and Python 3.11 provisioning.
2. **apt install** of runtime dependencies (`python3.11`, `python3.11-venv`, `curl`, `sqlite3`, `openssl`, `fail2ban`).
3. **sing-box** — pulls the latest stable binary from GitHub releases (auto-detects amd64 / arm64).
4. **Crypto generation** — Reality keypair, Hy2 self-signed cert, random SNI picked per install.
5. **Config writes** — `/etc/sing-box/config.json` and `/etc/proxybox/config.yaml` (mode 0600, root-owned).
6. **systemd units** — `sing-box`, `proxybox-admin`, `proxybox-traffic-worker`, `proxybox-watchdog`, `proxybox-bot` (bot stays disabled until configured).
7. **Auto-create the first device** — default name is 5 random lowercase letters (override with env var `PROXYBOX_FIRST_DEVICE=<name>`, or set it empty to skip).
8. **Print the handoff** — the login URL, username, password, and 4 subscription URLs in a single self-contained block.

> [!IMPORTANT]
> Copy the credentials into a password manager **before closing the terminal**. Recovery via SSH:
> ```bash
> cat /etc/proxybox/admin.password        # mode 0400, password only
> grep -E "username|login_path" /etc/proxybox/config.yaml
> ```

Full reference: [`deploy/install-sh.md`](./deploy/install-sh.md).

---

## First-time login

1. **Open the login URL** the installer printed — `http://<your-vps>:<admin-port>/login/<random-12char>`.

   > [!NOTE]
   > `/login` alone returns **404**. The random suffix is by design — it stops bots that brute-force common paths from even confirming a form exists.

2. **Enter `admin` + the printed password.** A session cookie is set for 30 days; you land in the SPA.

3. **The first device is already created** (5 random lowercase letters by default). Open the **Endpoints** page from the side nav. Four URLs are listed:

   | Format | Best for |
   | --- | --- |
   | `shadowrocket.yaml` | Shadowrocket subscription with nodes + rules |
   | `clash.yaml` | Stash · Clash for iOS · Clash Verge |
   | `merlin.yaml` | AsusWRT-Merlin routers with Clash |
   | `[generic]` (default URI list) | sing-box · Hiddify · basic node clients |

4. **Paste the matching URL** into the client's "Add subscription" dialog. The client downloads the URI list; the proxy is active.

5. **Verify** — open `https://ifconfig.me` from the client device. It should now report your VPS's IP, not your home ISP's.

---

## Next steps

- **Day-to-day operations** — add devices, rotate URLs, pause a device, change credentials: [`guide.md`](./guide.md).
- **Turn on HTTPS** — paste a domain into the panel's *HTTPS* page: [`deploy/install-sh.md`](./deploy/install-sh.md#https-with-caddy).
- **Wire up Telegram** — control devices from your phone: [`deploy/install-sh.md`](./deploy/install-sh.md#telegram-bot).

---

## See also

- [Guide](./guide.md) · day-to-day usage
- [Architecture](./architecture.md) · how the four processes coordinate
- [API endpoints](./api/endpoints.md) · per-router reference
- [← Back to README](../README.md)
