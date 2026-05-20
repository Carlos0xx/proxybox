<div align="right">

**English** · [中文](./README.zh.md)

</div>

<h1 align="center">ProxyBox</h1>

<p align="center">
  Self-hosted, per-device proxy admin panel.<br>
  One VLESS Reality + Hysteria2 pair per device · byte-level accounting · 1-click HTTPS · MIT.
</p>

<p align="center">
  <a href="#quick-start"><strong>Quick start</strong></a> ·
  <a href="./docs/guide.md">Guide</a> ·
  <a href="./docs/architecture.md">Architecture</a> ·
  <a href="./CHANGELOG.md">Changelog</a>
</p>

---

## Why

- **Revoke one device, not all of them.** Every device has its own UUID + ports.
- **Real traffic accounting.** SQLite buckets bytes per device per hour, classified by host (Video / Social / AI / CDN …).
- **No SaaS.** Everything runs on your VPS — no phone-home, no shared control plane.
- **One click for HTTPS, language, account.** No SSH after the first install.

---

## Quick start

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox && bash deploy/install.sh
```

Idempotent. ~3 minutes. Prints **login URL · username · password · 5 subscription URLs** at the end.

> [!IMPORTANT]
> Copy the credentials into a password manager before closing the terminal.

Other paths: [Docker Compose](./docs/deploy/docker.md) · [Claude Code skill](./docs/deploy/claude-skill.md).

---

## Documentation

| | |
| --- | --- |
| [Guide](./docs/guide.md) | Install + day-to-day usage |
| [Getting started](./docs/getting-started.md) | First 10 minutes, step by step |
| [Architecture](./docs/architecture.md) | Five processes, one SQLite, one config |
| [API](./docs/api/) | Per-router endpoint reference |
| [Deploy](./docs/deploy/) | The three install paths in detail |
| [Changelog](./CHANGELOG.md) | Per-version changes |

---

## License

MIT — see [`LICENSE`](./LICENSE).
