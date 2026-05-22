# Subscription URLs

> The public path each client device hits to fetch its proxy config. One default URI list plus three YAML variants; the `sub_token` itself is the secret.

For the admin-only endpoints that create devices and rotate tokens, see [`endpoints.md · Devices`](./endpoints.md#devices).

---

## URL shape

After `POST /api/devices/new`, the response carries `subscription_url_path: "/api/sub/{sub_token}"`. The full URL the client imports is:

```text
http://<server.public_host>:8080/api/sub/<sub_token>
```

…or `https://<domain>/api/sub/<sub_token>` once Caddy is provisioned.

These suffixes are accepted — pick the one that matches the client:

| Suffix | MIME | Best for |
| --- | --- | --- |
| *(none)* | `text/plain` | sing-box · Shadowrocket "Type: Subscribe" · Hiddify · NekoBox · v2rayN |
| `/shadowrocket.yaml` | `application/yaml` | Shadowrocket subscription with nodes + rules |
| `/clash.yaml` | `application/yaml` | Stash · Clash for iOS · Clash Verge · Clash Meta |
| `/merlin.yaml` | `application/yaml` | AsusWRT-Merlin routers with Clash |

> [!NOTE]
> All public formats are generated server-side, on the fly, from the same device row. No persisted files. Rotating `sub_token` invalidates every format simultaneously.

---

## Default content (URI list)

`GET /api/sub/<sub_token>` returns plain text — one URI per line, VLESS first then Hysteria2:

```text
vless://{uuid}@{host}:{vless_port}?security=reality&sni={sni}&fp=chrome&pbk={pubkey}&sid={short_id}&type=tcp&flow=xtls-rprx-vision#ProxyBox-{name}-vless
hysteria2://{password}@{host}:{hy2_port}?sni={sni}&insecure=1#ProxyBox-{name}-hy2
```

The Clash, Merlin, and Shadowrocket variants encode the same two endpoints in each client's native syntax. Hy2 YAML variants include explicit `auth`, `password`, `alpn: [h3]`, and `skip-cert-verify: true` for Stash/Shadowrocket compatibility.

---

## Client compatibility

| Client | Path to import |
| --- | --- |
| sing-box (iOS / Android / macOS / Windows) | `+ → Subscribe` → paste default URL |
| Shadowrocket (iOS) | Add subscription → paste `.../shadowrocket.yaml` |
| Hiddify Next | `+ → Add profile from URL` → paste default URL |
| NekoBox (Android) | `+ → Subscription` → paste default URL |
| v2rayN (Windows) | `Subscriptions → Add` → paste default URL |
| Stash · Clash Verge · Clash Meta | Add subscription → paste `.../clash.yaml` |
| AsusWRT-Merlin (Clash) | Subscription URL → paste `.../merlin.yaml` |

> [!IMPORTANT]
> Shadowrocket should use `shadowrocket.yaml` when you want nodes + split rules. The default URI list remains for clients that only understand raw node subscriptions.

---

## Rotation

If a device's `sub_token` leaks — or you just want a fresh URL:

```bash
curl -X POST \
  http://<host>:8080/admin/<admin_token>/api/devices/<name>/regen-subs
```

The old token immediately returns 404 on every format. The new URL points at the same device — UUID, ports, and Reality keypair are unchanged. The client re-imports once and is back online.

From the SPA: **Devices → Regenerate sub** button on each row.

---

## See also

- [Endpoints · Devices](./endpoints.md#devices) · `regen-subs` and friends
- [Architecture · Database](../architecture.md#database) · where `sub_token` is stored
- [Guide](../guide.md) · day-to-day device flow
- [← Back to API index](./index.md)
