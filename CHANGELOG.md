# Changelog

All notable changes to ProxyBox follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
