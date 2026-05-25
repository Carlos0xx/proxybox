# Architecture

> Five processes coordinating through one SQLite database and a sing-box JSON config.

For end-user workflows, see [`guide.md`](./guide.md). For per-endpoint reference, see [`api/endpoints.md`](./api/endpoints.md).

---

## At a glance

```text
┌─ Clients ────────────────────────────────────────────────────────────┐
│  sing-box · Shadowrocket · Hiddify · Stash · Clash · merlin routers  │
└────────────────────────┬─────────────────────────────────────────────┘
                         │  VLESS Reality  (TCP, per device — randomised base)
                         │  Hysteria2      (UDP, per device — randomised base)
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
| **fail2ban** | apt package | `fail2ban.service` | Manual IP-jail backend (`/etc/fail2ban/jail.d/proxybox.local`, `backend=systemd`). |

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
| **admin password** | 16-char random, stored in its own sibling file `/etc/proxybox/admin.password` (mode 0400, root-owned) — **not** inline in `config.yaml`. Constant-time compare via `secrets.compare_digest`. |
| **Session cookie** | `itsdangerous`-signed, 30-day expiry, `HttpOnly`, `SameSite=Lax`. |
| **`admin.token`** | URL-path component on every admin route. A stolen cookie cannot be replayed against an instance on a different host. |
| **`features.url_token_bypass`** | When `true`, the URL-path token *alone* authenticates (legacy v0.1.5 behaviour, useful for automation). **Defaults to `false`** in v0.1.6+. |
| **WebAuthn passkey** *(opt-in)* | Touch ID / Face ID / hardware key. Requires HTTPS. Adds a 2nd factor in front of the password — does not replace the URL-path token. |

---

## Database

Single SQLite file at `/var/lib/proxybox/traffic.db`, WAL mode, four tables.
The excerpt below shows the fields operators usually need to understand.

```sql
CREATE TABLE device (
  name          TEXT     PRIMARY KEY,    -- "abcde", "laptop-1", etc.
  label         TEXT     NOT NULL,        -- human-friendly display name
  kind          TEXT     NOT NULL,        -- "mobile" / "desktop" / "router"
  vless_uuid    TEXT     NOT NULL,        -- 128-bit RFC 4122 v4
  hy2_password  TEXT     NOT NULL,        -- 24-byte url-safe random
  vless_port    INTEGER  NOT NULL,        -- per-device TCP port
  hy2_port      INTEGER  NOT NULL,        -- per-device UDP port
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
| `GET /api/sub/{sub_token}/shadowrocket.yaml` | Shadowrocket nodes + split-rule config. |
| `GET /api/sub/{sub_token}/clash.yaml` | Clash config. |
| `GET /api/sub/{sub_token}/merlin.yaml` | AsusWRT-Merlin variant. |

### Server-rendered HTML

| Path | Notes |
| --- | --- |
| `GET /login/{login_path}` | Login form. The admin SPA is Chinese-only. |
| `POST /login/{login_path}` | Submit username + password — sets the session cookie. |
| `POST /logout` | Clears the cookie. |
| `GET /admin/{token}/` | SPA shell. Requires cookie. |
| `GET /admin/{token}/static/*` | SPA JS/CSS. |

### Admin API (cookie + URL token)

| Group | Examples |
| --- | --- |
| **Status** | `GET /admin/{token}/api/status` · `GET /admin/{token}/api/connections` |
| **Devices** | `GET /admin/{token}/api/devices/list` · `POST /admin/{token}/api/devices/new` · `POST /admin/{token}/api/devices/{name}/pause` · `POST /admin/{token}/api/devices/{name}/resume` · `POST /admin/{token}/api/devices/{name}/delete` |
| **Subscription** | `GET /admin/{token}/api/devices/{name}/sub` · `POST /admin/{token}/api/devices/{name}/sub/regen` |
| **History** | `GET /admin/{token}/api/history/devices?days=N` · `GET /admin/{token}/api/history/{device}/hourly` · `GET /admin/{token}/api/history/{device}/apps` · `GET /admin/{token}/api/history/{device}/hosts` |
| **HTTPS** | `GET /admin/{token}/api/https/status` · `POST /admin/{token}/api/https/enable` |
| **Account** | `GET /admin/{token}/api/admin/account` · `POST /admin/{token}/api/admin/account` (change username/password) · `POST /admin/{token}/api/admin/login-path` (rotate suffix) |
| **Logs** | `GET /admin/{token}/api/logs/{svc}` — allowlist follows `services.monitored`. |
| **Bans** | `GET /admin/{token}/api/bans` · `POST /admin/{token}/api/bans` · `POST /admin/{token}/api/bans/{id}/release` |
| **Rotate** | `POST /admin/{token}/action/rotate` (Reality keypair) |

> Full per-endpoint reference: [`api/endpoints.md`](./api/endpoints.md).

---

## Design choices

| Choice | What we did | Why |
| --- | --- | --- |
| **Per-device inbounds** | Unique TCP/UDP port + UUID per device | Revoke surgically; traffic accounting is naturally per-device. |
| **Traffic source** | sing-box Clash API (not nftables / eBPF) | No kernel-level rules to manage; single source of truth; works in Docker. |
| **Subscription path** | Plain HTTP `text/plain` URI list at `/api/sub/{token}` | Maximum client compatibility — not all clients parse raw `vless://`. |
| **Subscription formats** | Shadowrocket split config + Clash + Merlin + URI list — generated on the fly | Avoid format mismatches with router firmware and edge-case clients. |
| **Login form** | `/login/{12-char-suffix}`; bare `/login` 404s | Bots probing common paths can't even confirm a form exists. |
| **Admin auth** | Cookie + URL-path token *both* required; bypass mode opt-in | A stolen cookie can't be replayed against an instance on a different host. |
| **Login rate-limit** | Per-IP failure counter with progressive backoff on `/login/{secret}` | Slows password brute-force if the random login path ever leaks. |
| **Reality cover domain** | Random from a TLS1.3+h2-verified pool; override via `PROXYBOX_SNI` / `server.cover_domain`; `scripts/check-sni.py` validates a candidate | Avoids the canonical apple/microsoft Reality fingerprint; lets operators pick + verify their own domain. |
| **Port base** | Randomised per install (VLESS 10000-28999, Hy2 31000-54999) | A fixed 11000/21000 base is a fingerprint shared across every deployment. |
| **Host categorisation** | Suffix → app_group lookup (~120 entries, no DNS calls) | Privacy: no per-request DNS lookup; performance: O(1) per host. |
| **HTTPS provisioning** | Caddy + Let's Encrypt, triggered from the SPA | Docker uses an install-scoped host helper; native provisions directly and refuses to overwrite user Caddy configs. |
| **`install.sh` fresh/reuse/purge modes** | `--fresh` refuses old native state; default reuse keeps current-install state; destructive cleanup requires `--purge-existing-proxybox` confirmation | New installs stay non-destructive by default. |
| **i18n** | Chinese-only production SPA, English docs in repo | Avoids the previous language-toggle runtime complexity. |

---

## See also

- [Guide](./guide.md) · day-to-day usage walkthrough
- [Getting started](./getting-started.md) · install in under 10 minutes
- [API endpoints](./api/endpoints.md) · per-router reference
- [`config.example.yaml`](../config.example.yaml) · full configuration schema
- [← Back to README](../README.md)
