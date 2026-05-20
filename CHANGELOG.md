# Changelog

All notable changes to ProxyBox follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [v0.1.5] — post-install SPA UX fixes (real connection data + clean service list)

### Added
- **`/api/connections` endpoint** — proxies sing-box Clash API at
  `127.0.0.1:9090`, aggregates per source-IP, joins to `device.last_ip`
  to label rows by device, and folds in instantaneous `/traffic` up/down
  bps. Lights up the previously-stubbed 在线设备 count + 实时速度 KPI
  + tunnels list with real data.
- **`{{PASSKEY_ENABLED}}` / `{{BOT_ENABLED}}` template substitutions** in
  the SPA index route. SPA reads them as `FEATURES.passkey/bot` and hides
  nav entries for disabled opt-in features (before first paint).

### Fixed
- **`订阅链接` view now shows all 5 formats per device** in a per-device
  block (default URI list with `✦ [推荐]` marker + clash.yaml / merlin.yaml
  / shadowrocket.conf / sub.txt rows). Previously rendered just the base
  URL.
- **`服务` page no longer shows `unknown` for 3 services**. The hardcoded
  list (caddy / proxy-bot / proxy-admin / proxy-traffic-worker /
  proxy-watchdog.timer — BWG service names) is replaced by an iteration
  over `lastStatus.services` (which mirrors `config.services.monitored`).
  Sidebar `data-svc` dots got the same treatment.
- **Passkey nav 404 confusion**: nav entry is hidden via
  `display: none` on `DOMContentLoaded` when `features.passkey=false`.
  Was always visible before and clicking it 404'd because the passkey
  router wasn't mounted.

## [v0.1.4] — SPA pause-state rendering fix

### Fixed
- **Auto-created devices were displayed as "暂停中 · 无期限".** The DB
  default for `paused_until` is `0` (= NOT paused, matching what the
  resume endpoint writes back). The SPA's `loadDevicesMgmt` and
  `renderDeviceCard` both used `paused_until !== null` as the "paused"
  predicate, which mis-classified every fresh device as paused, then
  used `paused_until === 0` as the "indefinite" check, surfacing the
  warning badge on a perfectly active device. Rewrote both to match
  server semantics: paused iff `paused_until > now()`; indefinite iff
  `paused_until > now() + 10 years` (threshold-based so it tolerates
  small clock skew without hard-coding the server's sentinel constant
  `_PAUSE_INDEFINITE = 7258118400`).

## [v0.1.3] — polished install summary

### Changed
- `install.sh`'s post-install summary now uses ANSI color + structured
  layout: bold green banner, cyan section titles, yellow `✦` marker on
  the recommended subscription URL, bold-green admin URL, dim greys for
  the "advanced" / footer rows. Colors auto-disable when stdout is not
  a TTY (so output piped to a file or relayed through a non-interactive
  SSH stays plain ASCII — no escape-code bleed).
- Section dividers use `━━━` (unicode) instead of `===` for a cleaner
  look. Service status uses `✓ / ✗` instead of `[+] / [-]`.

### Why
The previous summary was correct but dense — important and unimportant
information shared the same visual weight. Now the admin URL and the
"[推荐]" subscription URL pop visually; "advanced features" and the
"completed token backup location" recede into dim text so普通用户
focuses on the action items.

## [v0.1.2] — one-shot install UX

### Added
- **Auto-bootstrap first device.** `install.sh` now polls localhost
  until `/api/status` returns 200, then `POST /api/devices/new` with
  name `phone-1` (override via `PROXYBOX_FIRST_DEVICE=<name>` env var).
  Re-running detects the existing device and reuses it — no duplicate.
- **Self-contained handoff summary.** The post-install block prints:
  - The full admin URL (token visible — for a brand-new server on the
    user's own VPS, making them SSH back in to grep `config.yaml` was
    the wrong default)
  - All 5 subscription URLs for the auto-created device, each labeled
    with its target client (default URI list / clash.yaml / merlin.yaml
    / shadowrocket.conf / sub.txt)
  - Services state + optional-features hint
- **`SKILL.md` Step 5 / 7 / anti-patterns updated** to relay install.sh
  output verbatim instead of masking. Ad-hoc bash authored mid-session
  (status checks, debugging) still masks to first 8 chars; only install
  output and the matching skill handoff are exempt.
- **`SKILL.md` Step 2 preamble**: `apt-get install -y git curl
  ca-certificates` so a minimal Debian image without `git` doesn't
  fail at the clone step.

## [v0.1.1] — SPA refresh fixes + multi-format subscriptions

### Fixed
- **SPA dashboard** was BWG-ported as-is and called endpoint paths /
  shapes that v0.1.x rewrote. Repaired so every view loads without
  `刷新失败` toasts on a clean install:
  - `loadTraffic` adapted to `/api/traffic` raw-byte schema (`rx_today`,
    `tx_today`, `active_devices_24h`) — was reading the old `today.total`
    pre-formatted string.
  - `loadBans` adapted to `/api/bans` field names (`currently_banned`,
    `banned`) — was reading BWG's `current_banned` / `banned_ips`.
  - `loadDevices` (订阅记录 / subscribers view) stubbed — BWG's nginx
    access-log tailing isn't in v0.1.x; view now shows a placeholder.
  - `loadConns` (`/api/connections`) and `loadSubs` (`/api/subs` list-all)
    stubbed at the call site — v0.2 candidates.
  - Device-management endpoint paths: `/api/device/...` (singular) →
    `/api/devices/...`; `/rename` body `{label}` → `/label`;
    `/rotate-token` (+ `r.new_token`) → `/regen-subs` (+ `r.sub_token`).
  - `showDeviceSubs` baseUrl: was `<host>/{sub_token}` → corrected to
    `<host>/api/sub/{sub_token}`.
- **PII / brand drift in `static/index.html`**: replaced personal device
  names in placeholder examples with generic ones (`phone-1`, `tablet-1`,
  `laptop-1`, `home-router`); removed the BWG-migration
  `deprecateLegacyURL()` function (mentioned the user's router model and
  device count); generic-ized "家用路由器 + N 设备" copy. Brand
  blocklist updated to catch regressions.

### Added
- **Multi-format subscription URLs** — five extension-suffixed routes per
  device, all generated on-the-fly from one row:
  - `/api/sub/{sub_token}` — URI list (sing-box family, default)
  - `/api/sub/{sub_token}/sub.txt` — same, `.txt` alias
  - `/api/sub/{sub_token}/clash.yaml` — Mihomo / Clash for iOS / Stash
  - `/api/sub/{sub_token}/merlin.yaml` — Clash YAML + `tun: enable: true`
    block for AsusWRT-Merlin transparent proxy
  - `/api/sub/{sub_token}/shadowrocket.conf` — Surge `.conf` format
  Implemented via `build_clash_yaml(with_tun=...)` and
  `build_shadowrocket_conf()` in `app/services/subscriptions.py`.
- **No-cache headers** on the SPA index route so SPA bugfixes reach the
  browser without manual hard refresh in the future.
- **`订阅链接` view** (loadSubs) now lists per-device public sub URLs,
  copy-to-clipboard for each.
- **Diagnostic stack trace in refresh-error toast** — the
  `loadCurrentView` catch now logs to console and includes view name +
  top 3 stack frames in the toast text.
- **SKILL.md Step 7 (handoff)** documents the 5 subscription URL formats
  in a table and lists generic device-name examples (`phone-1`,
  `tablet-1`, `laptop-1`, `home-router`).

## [v0.1.0] — initial release

### Added

#### Core admin API (34 endpoints)
- `GET /api/status` — system + per-service health (load, mem, disk, cpu, hostname, systemd unit state)
- `GET /api/devices` — per-device current usage (today + 24h, last seen, last IP, paused flag)
- `GET /api/devices/list` — raw device config rows
- `GET /api/devices/{name}` — single device detail
- `POST /api/devices/new` — create device (allocates ports, generates UUID + sub_token, writes sing-box config + subscription file)
- `POST /api/devices/{name}/label` / `notes` — metadata updates
- `POST /api/devices/{name}/pause` / `resume` — `{until_ts}` body, indefinite via sentinel
- `POST /api/devices/{name}/revoke` — soft delete (DB row kept, inbounds + sub file removed)
- `POST /api/devices/{name}/delete` — hard delete
- `POST /api/devices/{name}/rename` — DB + sing-box re-tag + sub file rewrite
- `POST /api/devices/{name}/regen-subs` — rotate sub_token + URL
- `GET /api/sub/{sub_token}` — **public** subscription URL (text/plain, vless:// + hysteria2:// URIs)
- `GET /api/traffic` — 24h totals + hourly breakdown
- `GET /api/history/devices` / `device/{name}` / `all-daily` / `export?format=csv` — time-window queries over `traffic_log`
- `GET /api/bans` + `POST /action/block` + `POST /action/unblock` — fail2ban [manual] jail wrapper
- `POST /action/restart/{svc}` — whitelisted systemctl restart
- `POST /action/rotate` — `{confirm:true}` body, regenerates Reality keypair + rewrites all device subscription files
- `POST /api/auth/rotate-admin-token` — atomic config rewrite, returns new URL prefix
- `GET /api/logs/{svc}` — whitelisted journalctl wrapper (text/plain)

#### Single-page admin dashboard
- `GET /admin/{token}/` — 4144-line single-file SPA ported from upstream, brand-stripped, `{{TOKEN}}` substituted server-side so embedded JS calls `/admin/{token}/api/...` without a second auth handshake
- Visual layout, CSS, JS preserved verbatim per CONSTRAINTS §4

#### Background services
- `app/workers/traffic.py` — independent systemd worker, polls sing-box Clash API every 10s, diffs per-connection byte counts, aggregates by (device, UTC hour) into `traffic_log`
- 7-day default retention with daily cleanup pass

#### Opt-in features
- `features.passkey` — WebAuthn / passkey login (lazy-imported `webauthn` library)
- `features.bot` — Telegram bot module (`bot/`, ~390 lines, 7 commands: `/help /status /devices /traffic /bans /pause /resume`) over stdlib urllib

#### Deploy paths
- `deploy/install.sh` — 304-line idempotent Debian/Ubuntu installer (apt packages, sing-box from GitHub releases, Reality keypair + Hy2 cert, fail2ban jail, 4 systemd units)
- `Dockerfile` + `docker-compose.yml` — 4-service stack (bootstrap one-shot + sing-box + admin + worker) with optional bot profile, multi-arch GHCR build via GitHub Actions
- `deploy/claude-skill/` — Claude Code skill bundle for "deploy proxybox on my VPS at <ip>" prompts

#### Tooling
- `scripts/pii-check.sh` — fixed-string grep against `~/.proxybox-pii-blocklist.txt`, runs via pre-commit hook
- `scripts/release-audit.sh` — pre-release security gate (7 checks)
- 5 GitHub Actions workflows: lint, test, build, gitleaks, release
- 13 unit tests covering pure functions (URI builders, env-var expansion, inbound-tag parsing)

#### Documentation
- README with 3-path quick-starts, ASCII architecture diagram, configuration table, security model
- VitePress site scaffold under `docs/`

### Changed vs upstream BWG codebase
- Single VLESS port + single Hy2 port per device (no alt ports)
- No host-level traffic classifier (privacy: each request's destination is not stored)
- UTC timestamps (not Beijing-specific) with configurable monitoring list
- No proprietary brand strings, domains, or device names — all replaced with `example.com` / `ProxyBox` / `phone-1` placeholders

### Known limitations
- WebAuthn passkey flow not end-to-end tested (requires HTTPS + browser; verify on a real Caddy-fronted deploy)
- Docker Compose path doesn't include fail2ban (host-level iptables not bridgeable)
- No automatic Caddy / Let's Encrypt setup yet (stretch goal for v0.1.1)
- Demo video not recorded yet (planned for v0.1.1)

### Security
- Admin token is constant-time-compared (`secrets.compare_digest`)
- Token rotation is atomic (`tmp + os.replace`)
- All credentials live on the server in `/etc/proxybox/config.yaml` mode 600; never echoed in chat output
- Per-device credentials isolate blast radius — leaking one device's UUID doesn't affect others
- Per-deployment Reality keypair (no shared cover-domain fingerprint)
- `pii-check.sh` pre-commit + gitleaks GitHub Actions = two-layer secret scrubbing
- `release-audit.sh` gates pre-release with 7 checks including author-metadata and commit-message scans

[Unreleased]: https://github.com/carlos0xx/proxybox/compare/v0.1.0...HEAD
[v0.1.0]: https://github.com/carlos0xx/proxybox/releases/tag/v0.1.0
