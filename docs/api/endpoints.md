# Admin endpoints

> Every endpoint below sits under `/admin/{admin.token}/`. Requests must carry both a valid session cookie and a matching URL-path token. Cookies come from [`/login/{login_path}`](#authentication).

For the public client-facing subscription endpoints, see [`subscription.md`](./subscription.md).

---

## Conventions

| | |
| --- | --- |
| Base URL | `http://<server.public_host>:8080` (or `https://<domain>` once Caddy is provisioned). |
| Token | `admin.token` in `/etc/proxybox/config.yaml`. URL-path component on every admin route. |
| Auth | `Cookie: session=...` + URL-path token match. **Both** are required when `features.url_token_bypass` is `false` (default). |
| Content-Type | `application/json` for POST bodies unless noted. |
| Errors | JSON `{detail: "..."}` with appropriate HTTP status. HTTPS errors include a structured `code`. |

---

## Authentication

Cookie-issuing endpoints — not under `/admin/{token}/`.

| Method · Path | Notes |
| --- | --- |
| `GET /login/{login_path}` | Chinese login form HTML. The bare `/login` returns **404** when `admin.login_path` is set. |
| `POST /login/{login_path}` | Form-urlencoded `username` + `password`. Sets `session` cookie (30 days) and redirects to `/admin/{token}/`. |
| `POST /logout` · `GET /logout` | Clears the cookie. |

---

## System

| Method · Path | Notes |
| --- | --- |
| `GET /api/status` | OS · load · mem · disk · CPU · hostname · per-service `active/inactive/failed`. Used by the SPA's Overview page. |
| `GET /api/logs/{name}?n=50` | `journalctl -u <name>` wrapper. `name` must be in `services.monitored` (allowlist). |
| `GET /api/connections` | Live Clash API `/connections` snapshot. Used by Overview's "Real-time speed". |

---

## Devices

Base: `/admin/{token}/api/devices`.

| Method · Path | Notes |
| --- | --- |
| `GET /` | Per-device current usage — today bytes + 24h totals + `last_seen` + `last_ip`. |
| `GET /list` | Raw device rows (includes revoked). Used by Devices tab. |
| `GET /{name}` | Single device detail. |
| `POST /new` | Create. Body: `{name, label?, kind?}`. Allocates ports, generates UUID + sub_token, writes sing-box config + sub file, reloads sing-box. |
| `POST /{name}/label` | Body: `{label}`. Update display name. |
| `POST /{name}/notes` | Body: `{notes}`. Update notes field. |
| `POST /{name}/rename` | Body: `{new_name}`. Renames the device row + sub file. |
| `POST /{name}/pause` | Body: `{until_ts}` (epoch seconds, `0` = indefinite). Removes inbounds, keeps the row. |
| `POST /{name}/resume` | Restores inbounds. |
| `POST /{name}/revoke` | Soft delete — DB row kept, inbounds + sub file gone. |
| `POST /{name}/delete` | Hard delete — DB + config + sub file. |
| `POST /{name}/regen-subs` | Rotate `sub_token` + URL. Old token immediately 404s. UUID + ports unchanged. |

---

## Traffic & history

| Method · Path | Notes |
| --- | --- |
| `GET /api/traffic` | 24h totals + per-hour breakdown across all devices. |
| `GET /api/history/devices?days=N` | Per-device daily totals — N defaults to 7. |
| `GET /api/history/device/{name}?days=N` | Single device, hourly + daily + per-app-group + per-host breakdown. |
| `GET /api/history/all-daily?days=N` | System daily totals (sum across all devices). |
| `GET /api/history/export?days=N&format=csv` | CSV dump. |

---

## HTTPS (v0.1.10+)

Base: `/admin/{token}/api/https`.

| Method · Path | Notes |
| --- | --- |
| `GET /status` | Returns `{caddy_installed, caddy_active, configured_domain, public_host, using_https, notes, docker_runtime}`. In Docker mode, Caddy state is the last known host-helper result because Caddy runs on the host. |
| `POST /enable` | Body: `{domain}`. Validates DNS, apt-installs Caddy, best-effort opens `80/tcp` and `443/tcp` in ufw/firewalld, writes a ProxyBox-managed Caddyfile without overwriting user configs, rewrites `server.public_host` + `passkey.rp_id` + `passkey.origin` in `config.yaml`, reloads. Docker mode delegates the host work to the install-scoped helper. |

> [!NOTE]
> `POST /enable` returns a structured error code on failure: `invalid_domain`, `dns_no_answer`, `dns_mismatch`, `caddyfile_conflict`, `cmd_failed`, `docker_helper_unavailable`, `docker_helper_timeout`, `docker_helper_failed`. The SPA surfaces these as Chinese messages.

---

## Account (v0.1.11+)

Base: `/admin/{token}/api/admin`.

| Method · Path | Notes |
| --- | --- |
| `GET /account` | Returns `{username, login_path}`. Password is never returned. |
| `POST /account` | Body: `{username?, current_password, new_password?}`. Constant-time compare on `current_password`. Atomic write — username lands in `config.yaml`, new password lands in `/etc/proxybox/admin.password` (mode 0400). |
| `POST /login-path` | Rotate the random suffix on `/login`. Returns the new `login_url`. Session cookie remains valid. |

---

## Bans

| Method · Path | Notes |
| --- | --- |
| `GET /api/bans` | Current fail2ban `[manual]` jail status. |
| `POST /action/block` | Body: `{ip}`. |
| `POST /action/unblock` | Body: `{ip}`. |

---

## Admin actions

| Method · Path | Notes |
| --- | --- |
| `POST /action/restart/{svc}` | `systemctl restart <svc>`. `svc` must be in `services.monitored`. |
| `POST /action/rotate` | Body: `{confirm: true}`. Rotate Reality keypair + rewrite every device's sub file. |
| `POST /api/auth/rotate-admin-token` | Invalidate the current URL prefix and return a new one. |

---

## WebAuthn (opt-in)

Active when `features.passkey: true` and HTTPS is enabled.

| Method · Path | Auth | Notes |
| --- | --- | --- |
| `POST /auth/webauthn/login/begin` | public | Returns challenge. |
| `POST /auth/webauthn/login/complete` | public | Returns session cookie on success. |
| `POST /auth/webauthn/logout` | session | Clears cookie. |
| `POST /admin/{token}/api/auth/webauthn/register/begin` | session or token | Registration challenge. |
| `POST /admin/{token}/api/auth/webauthn/register/complete` | session or token | Persists credential. |
| `GET /admin/{token}/api/auth/passkeys` | session or token | List registered keys. |
| `DELETE /admin/{token}/api/auth/passkeys/{cid}` | session or token | Revoke a key. |

---

## See also

- [Subscription URLs](./subscription.md) · the public client-facing path
- [Architecture · URL layout](../architecture.md#url-layout) · diagram view
- [`config.example.yaml`](../../config.example.yaml) · full configuration schema
- [← Back to API index](./index.md)
