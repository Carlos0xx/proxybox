# Getting started

> Install ProxyBox on a fresh VPS, log in, get the first client routing through it — typically under 10 minutes.

For a higher-level walkthrough of day-to-day operations after install, see [`guide.md`](./guide.md). For the architecture, see [`architecture.md`](./architecture.md).

---

## Prerequisites

| Requirement | Detail |
| --- | --- |
| **OS** | Debian 12 / 13 or Ubuntu 22.04 / 24.04 / 26.04 — clean install. |
| **Access** | Root SSH (the installer uses `apt` + `systemctl`). |
| **Resources** | ≥ 1 GB RAM · ≥ 5 GB free disk. |
| **Required ports** | `8080/tcp` (admin) · `11000-11050/tcp` (VLESS) · `21000-21050/udp` (Hysteria2). |
| **For HTTPS later** | A domain pointing at the VPS · `80/tcp` + `443/tcp` open. Optional but recommended for production. |

---

## Path 1 — `install.sh` &nbsp;<sub>(recommended for Linux VPS)</sub>

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox
bash deploy/install.sh --lang en        # --lang zh for Chinese output
```

The installer is idempotent — safe to re-run mid-way. It performs:

1. **Pre-flight validation** via `deploy/check-prereqs.sh` (9 categories: OS, arch, privilege, RAM, disk, network, systemd, ports, apt deps).
2. **apt install** of runtime dependencies (`python3-venv`, `curl`, `sqlite3`, `openssl`, `fail2ban`).
3. **sing-box** — pulls the latest stable binary from GitHub releases (auto-detects amd64 / arm64).
4. **Crypto generation** — Reality keypair, Hy2 self-signed cert, random SNI from a public-domain pool (`www.microsoft.com` / `apple.com` / `cloudflare.com` / `amazon.com`).
5. **Config writes** — `/etc/sing-box/config.json` and `/etc/proxybox/config.yaml` (mode 0600, root-owned).
6. **systemd units** — `sing-box`, `proxybox-admin`, `proxybox-traffic-worker`, `proxybox-bot` (bot stays disabled until configured).
7. **Auto-create the first device** — default name `phone-1` (override with env var `PROXYBOX_FIRST_DEVICE=<name>`).
8. **Print the handoff** — the login URL, username, password, and 5 subscription URLs in a single self-contained block.

> [!IMPORTANT]
> Copy the credentials into a password manager **before closing the terminal**. They are also stored in `/etc/proxybox/config.yaml` under `admin.username` / `admin.password` / `admin.login_path`.

Full reference: [`deploy/install-sh.md`](./deploy/install-sh.md).

---

## Path 2 — Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d
docker compose exec proxybox-admin \
    sh -c 'grep -E "username|password|login_path" /etc/proxybox/config.yaml'
```

A one-shot `bootstrap` container generates `config.yaml` on first start. Volumes preserve state across `docker compose down`/`up`.

To also run the Telegram bot:

```bash
# fill BOT_TOKEN + TG_ALLOWED_USERS into /etc/proxybox/bot.env first
docker compose --profile bot up -d proxybox-bot
```

| Limitation | Workaround |
| --- | --- |
| No fail2ban (host iptables not exposed to containers). | Use the host firewall + your provider's edge filter. |
| No automatic Caddy / HTTPS provisioning. | Pair with an external Caddy / nginx / Cloudflare Tunnel in front of port 8080. |

Full reference: [`deploy/docker.md`](./deploy/docker.md).

---

## Path 3 — Claude Code

If you use Claude Code, install the bundled skill once:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

Then ask Claude in any session:

> deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519

Claude runs the same pre-flight checks, `git clone`s the repo, runs `install.sh`, verifies all four services, and relays the credentials. Full reference: [`deploy/claude-skill.md`](./deploy/claude-skill.md).

---

## First-time login

1. **Open the login URL** the installer printed — `http://<your-vps>:8080/login/<random-12char>`.

   > [!NOTE]
   > `/login` alone returns **404**. The random suffix is by design — it stops bots that brute-force common paths from even confirming a form exists.

2. **Enter `admin` + the printed password.** A session cookie is set for 30 days; you land in the SPA.

3. **The first device is already created** (`phone-1` by default). Open **订阅链接 / Endpoints** in the side nav. Five URLs are listed:

   | Format | Best for |
   | --- | --- |
   | `[pick this]` (default URI list) | sing-box · Shadowrocket "Type: Subscribe" · Hiddify |
   | `clash.yaml` | Stash · Clash for iOS · Clash Verge |
   | `merlin.yaml` | AsusWRT-Merlin routers with Clash |
   | `shadowrocket.conf` | Shadowrocket native parser (fallback) |
   | `sub.txt` | Clients that key on file extension |

4. **Paste the matching URL** into the client's "Add subscription" dialog. The client downloads the URI list; the proxy is active.

5. **Verify** — open `https://ifconfig.me` from the client device. It should now report your VPS's IP, not your home ISP's.

---

## Next steps

- **Day-to-day operations** — add devices, rotate URLs, pause a device, change credentials: [`guide.md`](./guide.md).
- **Turn on HTTPS** — paste a domain into the panel's "HTTPS · 域名" page: [`deploy/install-sh.md`](./deploy/install-sh.md#https-with-caddy).
- **Wire up Telegram** — control devices from your phone: [`deploy/install-sh.md`](./deploy/install-sh.md#telegram-bot).
- **Switch UI language** — `中 / EN` toggle in the topbar.

---

## See also

- [Guide](./guide.md) · day-to-day usage
- [Architecture](./architecture.md) · how the four processes coordinate
- [API endpoints](./api/endpoints.md) · per-router reference
- [← Back to README](../README.md)
