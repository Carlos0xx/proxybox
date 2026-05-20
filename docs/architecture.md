# Architecture

> Five processes coordinating through one SQLite database and a sing-box JSON config.

For end-user workflows, see [`guide.md`](./guide.md). For per-endpoint reference, see [`api/endpoints.md`](./api/endpoints.md).

---

## At a glance

```text
┌─ Clients ────────────────────────────────────────────────────────────┐
│  sing-box · Shadowrocket · Hiddify · Stash · Clash · merlin routers  │
└────────────────────────┬─────────────────────────────────────────────┘
                         │  VLESS Reality  (TCP 11001-11050, per device)
                         │  Hysteria2      (UDP 21001-21050, per device)
                         ▼
┌──────────────────────────────────────────────────────────────────────┐
│                              VPS                                     │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  sing-box                                  systemd              │  │
│  │  - reads /etc/sing-box/config.json                              │  │
│  │  - per-device Reality (TCP) + Hy2 (UDP) inbounds                │  │
│  │  - exposes Clash API on 127.0.0.1:9090                          │  │
│  └────────────────────────────┬───────────────────────────────────┘  │
│                               │ /connections · /traffic                │
│  ┌────────────────────────────▼───────────────────────────────────┐  │
│  │  proxybox-traffic-worker                  systemd              │  │
│  │  - polls Clash API every 10s                                   │  │
│  │  - byte delta → traffic_log (per device × hour)                │  │
│  │  - host suffix → app_group → host_log                          │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  proxybox-admin   (FastAPI + uvicorn)     systemd  :8080       │  │
│  │  - /login/{secret} ──→ username/password ──→ session cookie    │  │
│  │  - /admin/{token}/...   ←── cookie + URL-path token            │  │
│  │  - /api/sub/{sub_token}[/format]    (public, sub_token is key) │  │
│  │  - /api/https/enable     {domain}   → Caddy provisioning       │  │
│  │  - /api/admin/account, /login-path  → credential rotation      │  │
│  │  - /api/connections                 → Clash API proxy          │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  caddy            (opt-in, provisioned from the UI)            │  │
│  │  - reverse_proxy 127.0.0.1:8080                                │  │
│  │  - Let's Encrypt auto-issue + auto-renew                       │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  proxybox-bot     (opt-in, Telegram long-poll)                 │  │
│  │  fail2ban         (manual IP jail, backend=systemd)            │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
│              ┌──────────────────────────────────────┐                │
│              │  /var/lib/proxybox/traffic.db        │                │
│              │  device · traffic_log · host_log     │                │
│              │  passkey_credential (opt-in)         │                │
│              └──────────────────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────┘
```

---

## Processes

| Process | Source | systemd unit | Purpose |
| --- | --- | --- | --- |
| **sing-box** | upstream binary | `sing-box.service` | The actual proxy — per-device Reality + Hy2 inbounds. Configured via `/etc/sing-box/config.json`. |
| **proxybox-admin** | [`app/main.py`](../app/main.py) | `proxybox-admin.service` | FastAPI app — admin API, SPA, login form, subscription endpoints, HTTPS provisioning. Listens on `:8080`. |
| **proxybox-traffic-worker** | [`app/workers/traffic.py`](../app/workers/traffic.py) | `proxybox-traffic-worker.service` | Polls sing-box Clash API every 10s; writes byte deltas to `traffic_log`, host suffixes to `host_log`. |
| **caddy** *(opt-in)* | upstream binary | `caddy.service` | HTTPS reverse-proxy in front of `:8080`. Provisioned via the panel's HTTPS page. |
| **proxybox-bot** *(opt-in)* | [`bot/__main__.py`](../bot/__main__.py) | `proxybox-bot.service` | Telegram long-poll — `/status`, `/devices`, `/traffic`, `/pause`, `/resume`, `/bans`. |
| **fail2ban** | apt package | `fail2ban.service` | Manual IP-jail backend (custom `[manual]` jail, `backend=systemd`). |

The first three are always running. The last three are opt-in and start disabled.

---

## Authentication

Two layered checks. Both must pass for every admin endpoint.

```text
        ┌──────────────────────────────────────┐
        │  Browser  →  /login/{login_path}     │  ① Layer 1: session
        │            POST username + password  │     - issued by /login/{...}
        │            ←  Set-Cookie: session    │     - 30-day expiry
        └──────────────────────────────────────┘     - HttpOnly, SameSite=Lax
                            │
                            ▼
        ┌──────────────────────────────────────┐
        │  Browser  →  /admin/{token}/api/...  │  ② Layer 2: URL-path token
        │            Cookie: session=...       │     - token must match config
        │            (admin.token in YAML)     │     - re-checked every request
        └──────────────────────────────────────┘
```

| Property | Behavior |
| --- | --- |
| **Login form** | Lives at `/login/{login_path}`. The bare `/login` returns **404** so brute-force scanners can't even confirm a form exists. |
| **`admin.login_path`** | Random 12-char alphanumeric, generated by `install.sh`. Rotate from the SPA's *Security* page — no SSH needed. |
| **`admin.password`** | 16-char random, hashed by FastAPI session middleware. Constant-time compare via `secrets.compare_digest`. |
| **Session cookie** | `itsdangerous`-signed, 30-day expiry, `HttpOnly`, `SameSite=Lax`. |
| **`admin.token`** | URL-path component on every admin route. A stolen cookie cannot be replayed against an instance on a different host. |
| **`features.url_token_bypass`** | When `true`, the URL-path token *alone* authenticates (legacy v0.1.5 behaviour, useful for automation). **Defaults to `false`** in v0.1.6+. |
| **WebAuthn passkey** *(opt-in)* | Touch ID / Face ID / hardware key. Requires HTTPS. Adds a 2nd factor in front of the password — does not replace the URL-path token. |

---

## Database

Single SQLite file at `/var/lib/proxybox/traffic.db`, WAL mode, four tables.

```sql
CREATE TABLE device (
  name          TEXT     PRIMARY KEY,    -- "phone-1", "laptop-1", etc.
  label         TEXT     NOT NULL,        -- human-friendly display name
  kind          TEXT     NOT NULL,        -- "mobile" / "desktop" / "router"
  vless_uuid    TEXT     NOT NULL,        -- 128-bit RFC 4122 v4
  hy2_password  TEXT     NOT NULL,        -- 24-byte url-safe random
  vless_port    INTEGER  NOT NULL,        -- per-device TCP port
  hy2_port      INTEGER  NOT NULL,        -- per-device UDP port
  sni           TEXT     NOT NULL,        -- Reality cover-domain
  created_at    INTEGER  NOT NULL,
  last_seen     INTEGER,                  -- updated by traffic-worker
  last_ip       TEXT,                     -- last source IP seen
  revoked       INTEGER  NOT NULL DEFAULT 0,
  notes         TEXT     NOT NULL DEFAULT '',
  sub_token     TEXT     NOT NULL UNIQUE, -- subscription URL secret
  paused_until  INTEGER  NOT NULL DEFAULT 0
);

CREATE TABLE traffic_log (
  device_name  TEXT    NOT NULL,
  bucket_ts    INTEGER NOT NULL,  -- UTC hour-aligned epoch
  date         TEXT    NOT NULL,  -- YYYY-MM-DD UTC
  hour         INTEGER NOT NULL,  -- 0-23 UTC
  rx_bytes     INTEGER NOT NULL,  -- download (server → client)
  tx_bytes     INTEGER NOT NULL,  -- upload (client → server)
  conn_count   INTEGER NOT NULL,  -- new connections in bucket
  PRIMARY KEY (device_name, bucket_ts)
);

CREATE TABLE host_log (                -- v0.1.9+
  device_name  TEXT    NOT NULL,
  bucket_ts    INTEGER NOT NULL,       -- UTC hour-aligned epoch
  host         TEXT    NOT NULL,       -- destination hostname (or IP)
  app_group    TEXT    NOT NULL,       -- "video" / "social" / "ai" / "cdn" / ...
  rx_bytes     INTEGER NOT NULL,
  tx_bytes     INTEGER NOT NULL,
  conn_count   INTEGER NOT NULL,
  PRIMARY KEY (device_name, bucket_ts, host)
);

CREATE TABLE passkey_credential (      -- opt-in
  credential_id  TEXT     PRIMARY KEY,
  public_key     BLOB     NOT NULL,
  sign_count     INTEGER  NOT NULL,
  label          TEXT     NOT NULL DEFAULT '',
  created_at     INTEGER  NOT NULL,
  last_used_at   INTEGER
);
```

> [!NOTE]
> Schema lives in [`app/db/schema.sql`](../app/db/schema.sql). All statements use `IF NOT EXISTS` — `init_schema()` runs on every startup and migrations are additive only.

---

## URL layout

### Public (no auth)

| Path | Notes |
| --- | --- |
| `GET /api/sub/{sub_token}` | Subscription URI list (default). `sub_token` itself is the secret. |
| `GET /api/sub/{sub_token}/clash.yaml` | Clash config. |
| `GET /api/sub/{sub_token}/merlin.yaml` | AsusWRT-Merlin variant. |
| `GET /api/sub/{sub_token}/shadowrocket.conf` | Shadowrocket native format. |
| `GET /api/sub/{sub_token}/sub.txt` | URI list with `.txt` extension (some clients key on it). |

### Server-rendered HTML

| Path | Notes |
| --- | --- |
| `GET /login/{login_path}` | Login form. `?lang=en` / `?lang=zh` to switch language. |
| `POST /login/{login_path}` | Submit username + password — sets the session cookie. |
| `POST /logout` | Clears the cookie. |
| `GET /admin/{token}/` | SPA shell. Requires cookie. |
| `GET /admin/{token}/static/*` | SPA JS/CSS. |

### Admin API (cookie + URL token)

| Group | Examples |
| --- | --- |
| **Status** | `GET /admin/{token}/api/status` · `GET /api/connections` (Clash API proxy) |
| **Devices** | `GET /api/devices/list` · `POST /api/devices/new` · `POST /api/devices/{name}/pause` · `POST /api/devices/{name}/resume` · `POST /api/devices/{name}/delete` |
| **Subscription** | `GET /api/devices/{name}/sub` · `POST /api/devices/{name}/sub/regen` |
| **History** | `GET /api/history/devices?days=N` · `GET /api/history/{device}/hourly` · `GET /api/history/{device}/apps` · `GET /api/history/{device}/hosts` |
| **HTTPS** | `GET /api/https/status` · `POST /api/https/enable` · `POST /api/https/disable` |
| **Account** | `GET /api/admin/account` · `POST /api/admin/account` (change username/password) · `POST /api/admin/login-path` (rotate suffix) |
| **Logs** | `GET /api/logs/{svc}` — allowlist: `sing-box`, `proxybox-admin`, `proxybox-traffic-worker`, `proxybox-bot`, `caddy`, `fail2ban` |
| **Bans** | `GET /api/bans` · `POST /api/bans` · `POST /api/bans/{id}/release` |
| **Rotate** | `POST /admin/{token}/action/rotate` (Reality keypair) |

> Full per-endpoint reference: [`api/endpoints.md`](./api/endpoints.md).

---

## Design choices

| Choice | What we did | Why |
| --- | --- | --- |
| **Per-device inbounds** | Unique TCP/UDP port + UUID per device | Revoke surgically; traffic accounting is naturally per-device. |
| **Traffic source** | sing-box Clash API (not nftables / eBPF) | No kernel-level rules to manage; single source of truth; works in Docker. |
| **Subscription path** | Plain HTTP `text/plain` URI list at `/api/sub/{token}` | Maximum client compatibility — not all clients parse raw `vless://`. |
| **5 subscription formats** | URI list + Clash + Merlin + Shadowrocket + .txt — generated on the fly | Avoid format mismatches with router firmware and edge-case clients. |
| **Login form** | `/login/{12-char-suffix}`; bare `/login` 404s | Bots probing common paths can't even confirm a form exists. |
| **Admin auth** | Cookie + URL-path token *both* required; bypass mode opt-in | A stolen cookie can't be replayed against an instance on a different host. |
| **Reality cover-domain** | Random pick from `www.microsoft.com` / `apple.com` / `cloudflare.com` / `amazon.com` per install | No shared fingerprint across deployments. |
| **Host categorisation** | Suffix → app_group lookup (~120 entries, no DNS calls) | Privacy: no per-request DNS lookup; performance: O(1) per host. |
| **HTTPS provisioning** | Caddy + Let's Encrypt, triggered from the SPA | One click instead of an SSH session for a non-technical user. |
| **`install.sh` idempotency** | Every step gated by an existence check | Safe to re-run; partial failures resume cleanly. |
| **i18n** | Phrase → phrase dict + MutationObserver | No source-code annotation of every Chinese string; topbar toggle reloads via cookie + `localStorage`. |

---

## See also

- [Guide](./guide.md) · day-to-day usage walkthrough
- [Getting started](./getting-started.md) · install in under 10 minutes
- [API endpoints](./api/endpoints.md) · per-router reference
- [`config.example.yaml`](../config.example.yaml) · full configuration schema
- [← Back to README](../README.md)
