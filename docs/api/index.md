# API

> All ProxyBox HTTP surfaces, grouped by intent.

| Page | Covers |
| --- | --- |
| [Endpoints](./endpoints.md) | Admin API — devices · traffic · history · HTTPS · account · logs · bans. Cookie + URL-path token gated. |
| [Subscription URLs](./subscription.md) | Public `/api/sub/{sub_token}` — default URI list plus `shadowrocket.yaml`, `clash.yaml`, and `merlin.yaml`. |

---

## Two URL prefixes

| Prefix | Auth | Used by |
| --- | --- | --- |
| `/admin/{admin.token}/...` | session cookie **and** matching URL-path token | Admin SPA + admin API. |
| `/api/sub/{sub_token}[/format]` | none — `sub_token` *is* the secret | Proxy clients (sing-box, Shadowrocket, Clash, etc.). |

> [!IMPORTANT]
> `admin.token` and the per-device `sub_token` are independent. Rotating one does not affect the other. Both live in `/etc/proxybox/config.yaml` and the device table respectively.

---

## See also

- [Architecture](../architecture.md) · how the routers fit into the bigger picture
- [Guide](../guide.md) · day-to-day operations
- [← Back to README](../../README.md)
