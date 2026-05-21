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
  <a href="./docs/guide.md">Guide</a> ·
  <a href="./docs/architecture.md">Architecture</a>
</p>

---

## Why

- **Per-device isolation** — revoke one device, not all of them.
- **Real traffic accounting** — per-device × hour, host-categorised.
- **Self-hosted** — no SaaS, no phone-home.

---

## Install

### A · `install.sh` *(recommended)*

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox && bash deploy/install.sh
```

### B · Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d
```

### C · Claude Code skill

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
# then in a Claude Code session: "deploy proxybox on my VPS at 1.2.3.4"
```

> [!IMPORTANT]
> The installer prints login URL + password once. Copy them into a password manager before closing the terminal.

---

## Documentation

| | |
| --- | --- |
| [Guide](./docs/guide.md) | Install + day-to-day usage |
| [Architecture](./docs/architecture.md) | Five processes, one SQLite, one config |
| [API](./docs/api/) | Per-router endpoint reference |
| [Deploy](./docs/deploy/) | The three install paths in detail |

---

## License

MIT — see [`LICENSE`](./LICENSE).
