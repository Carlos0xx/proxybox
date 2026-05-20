# Docker Compose

> Containerised alternative to `install.sh`. Multi-arch images at `ghcr.io/carlos0xx/proxybox:latest`.

For the high-level walkthrough, see [Getting started · Path 2](../getting-started.md#path-2--docker-compose).

---

## Stack

The `docker-compose.yml` at the repo root ships five services:

| Service | Image | Role | Profile |
| --- | --- | --- | --- |
| `bootstrap` | `proxybox:local` | One-shot — generates `config.yaml` + `sing-box/config.json`. Exits 0 if both already exist. | default |
| `sing-box` | `ghcr.io/sagernet/sing-box:latest` | The proxy. `network_mode: host`. | default |
| `proxybox-admin` | `proxybox:local` | FastAPI admin on `:8080`. | default |
| `proxybox-traffic-worker` | `proxybox:local` | Clash API polling. | default |
| `proxybox-bot` | `proxybox:local` | Telegram bot. | `bot` |

Volumes preserve state across `down`/`up`:

| Volume | Mount | Purpose |
| --- | --- | --- |
| `proxybox-config` | `/etc/proxybox` | `config.yaml`, `bot.env` |
| `proxybox-data` | `/var/lib/proxybox` | `traffic.db` (SQLite) |
| `proxybox-sub` | `/var/www/proxybox-sub` | Cached sub files |
| `singbox-config` | `/etc/sing-box` | sing-box config + Reality keypair + Hy2 cert |

---

## Quick start

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d                              # core stack
docker compose --profile bot up -d                # also start the TG bot
```

Read the freshly generated credentials:

```bash
docker compose exec proxybox-admin \
    sh -c 'grep -E "username|password|login_path" /etc/proxybox/config.yaml'
```

Open `http://<host>:8080/login/<login_path>` in a browser. Username `admin`, password as printed.

---

## Pre-built images

Every tag publishes multi-arch images to GHCR:

```text
ghcr.io/carlos0xx/proxybox:latest          # rolling
ghcr.io/carlos0xx/proxybox:v0.2.0          # pinned
```

To use the pre-built image instead of building locally, edit `docker-compose.yml`:

```yaml
proxybox-admin:
  image: ghcr.io/carlos0xx/proxybox:latest
  pull_policy: always   # or never if you've already pulled
```

Arches: `linux/amd64`, `linux/arm64`.

---

## Limitations

| Limitation | Workaround |
| --- | --- |
| **No fail2ban.** Host-level iptables is not exposed into the container. | Use the host firewall + your provider's edge filter. |
| **No HTTPS auto-provisioning UI.** `enable-https.sh` writes to host paths the container can't reach. | Front the stack with Caddy / nginx / Cloudflare Tunnel. |
| **No passkey** by default (needs HTTPS, which needs the bullet above). | Once HTTPS is fronted, set `features.passkey: true` in `config.yaml`. |

---

## Production sketch — Caddy in front

```text
        ┌─ caddy (host)
        │  reverse_proxy 127.0.0.1:8080
        │  Let's Encrypt
        ▼
   docker-compose stack on the same host
```

`Caddyfile` example:

```caddyfile
proxy.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

`config.yaml` updates:

```yaml
server:
  public_host: proxy.example.com    # baked into sub URIs
features:
  passkey: true
passkey:
  rp_id: proxy.example.com
  origin: https://proxy.example.com
```

Restart `proxybox-admin` to pick up the new config:

```bash
docker compose restart proxybox-admin
```

---

## See also

- [`install.sh`](./install-sh.md) · the recommended Linux path
- [Claude Code skill](./claude-skill.md) · automated install via Claude
- [`docker-compose.yml`](../../docker-compose.yml) · the actual stack
- [← Back to README](../../README.md)
