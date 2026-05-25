# Changelog

All notable changes to ProxyBox follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed — randomised port base

- **VLESS/Hy2 ports are randomised per install** instead of the fixed
  `11000/11001-11050` and `21000/21001-21050`. A fixed port is a
  fingerprint; now each deployment picks a random base (VLESS in
  10000-28999, Hy2 in 31000-54999, non-overlapping). Applies to both
  `install.sh` and the Docker bootstrap. Env vars
  (`PROXYBOX_VLESS_TEMPLATE_PORT`, `PROXYBOX_HY2_TEMPLATE_PORT`, and the
  `_START`/`_END` range vars) override for reproducible installs.
- `install.sh` summary now prints the randomised ranges so you know
  which ports to open in your cloud firewall.
- Pre-flight (`check-prereqs.sh`) no longer probes 11000/21000 — those
  aren't known until after the random pick.

### Changed — Reality cover domain (SNI) hardening

- **Dropped the canonical apple/microsoft/cloudflare/amazon SNI pool.**
  Those are the oldest Reality example domains, so "claims to be apple.com
  but the IP isn't Apple's" is itself a fingerprint. Replaced with a
  larger pool of lower-profile domains, **every one verified to negotiate
  TLS 1.3 + HTTP/2 (h2)** (many big-brand sites sit behind WAFs that only
  do HTTP/1.1 — those make poor cover domains and were excluded).
- **Cover domain is now configurable.** `PROXYBOX_SNI=<domain>` overrides
  the random pick at install time (both `install.sh` and the Docker
  bootstrap); the chosen value is recorded as `server.cover_domain` in
  `config.yaml`.
- **New `scripts/check-sni.py`** validates a candidate domain (TLS 1.3 +
  h2 + reachable) so operators can pick and verify their own cover domain
  rather than relying on the shared default pool — which, being in
  open-source code, is itself a weaker fingerprint. The tool detects a
  TLS-1.3-incapable runtime (e.g. macOS LibreSSL) and tells you to run it
  on the VPS instead of emitting false negatives.

## [0.2.0] — Initial public release

First open-source release. Per-device-isolated proxy admin panel for a
single VPS.

### Highlights

- **Per-device inbounds** — each device gets its own VLESS Reality (TCP)
  + Hysteria2 (UDP) pair with a unique UUID and port. Revoke one device
  without rotating the rest.
- **Real traffic accounting** — a background worker polls sing-box's
  Clash API every 10 s and buckets bytes per device per hour in SQLite,
  with host categorisation (Video / Social / AI / CDN / …).
- **Username + password login** — form at `/login/{random-suffix}`; the
  bare `/login` returns 404. Password lives in `/etc/proxybox/admin.password`
  (mode 0400), not inline in `config.yaml`.
- **1-click HTTPS** — enter a domain in the panel; Caddy + Let's Encrypt
  provisioned in ~30 s.
- **4 subscription formats** — URI list · `clash.yaml` ·
  `shadowrocket.yaml` · `merlin.yaml`, generated server-side per device.
- **Chinese admin UI** — the panel is Chinese-only; project docs are in
  English. (An earlier language toggle was removed to avoid runtime
  i18n complexity.)
- **Optional Telegram bot** + **optional WebAuthn passkey**.
- **Three deploy paths** — Claude Code / Codex skill, `install.sh`, or
  Docker Compose.

### Security

- Login rate-limit on `/login/{secret}` — per-IP failure counter with
  progressive backoff.
- `sub_token` is 192-bit (`secrets.token_urlsafe(24)`).
- Subscription files are mode 0600; all five formats check device
  revoked-status against the DB before serving.
- Session cookie `Secure` flag derived from the request scheme
  (`X-Forwarded-Proto`).
- `shell.py` rejects string commands (`shell=False` always).
- Supply chain: GitHub Actions pinned to commit SHAs, Docker base images
  pinned to tags, Dependabot enabled, plus `gitleaks` + `detect-secrets`
  + `pip-audit` in CI.
