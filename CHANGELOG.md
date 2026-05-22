# Changelog

All notable changes to ProxyBox follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Pre-release hardening

- **Native installs no longer delete old state through `--fresh`.** `--fresh`
  now refuses to continue when previous ProxyBox/sing-box native state exists;
  destructive cleanup moved behind `--purge-existing-proxybox` plus an explicit
  `DELETE PROXYBOX` confirmation.
- **HTTPS enablement avoids user config overwrite and duplicate side effects.**
  Native and Docker paths both refuse non-ProxyBox Caddyfiles, Docker helper
  trusts the install `.env` port instead of container request data, and the SPA
  no longer sends a second `POST /api/https/enable` when showing errors.
- **Docker HTTPS/bot/docs contracts aligned.** Docker HTTPS status now reports
  last successful host-helper enablement, helper does best-effort ufw/firewalld
  80/443 opening, and the optional Docker bot uses the internal admin URL plus
  an install-scoped secret.
- **Documentation updated for the current Chinese-only UI and Docker-first
  architecture.** README, deploy docs, API docs, and the deployment skill no
  longer describe the removed language switcher or obsolete Docker HTTPS
  limitations.

### Installation reliability — Codex install follow-up

- **Fresh installs keep URL-token-only admin access disabled from first boot.**
  `install.sh` now logs in with the generated username/password and uses the
  resulting session cookie for first-device bootstrap instead of temporarily
  enabling `features.url_token_bypass`.
- **Re-runs can bootstrap through the current auth model.** Existing installs
  with `features.url_token_bypass=false` can still list or create the first
  device during `install.sh` because the installer authenticates through
  `/login/{login_path}` first.
- **Existing fail2ban config is preserved.** The installer appends the
  ProxyBox `[manual]` jail via `/etc/fail2ban/jail.d/proxybox.local` instead
  of overwriting `/etc/fail2ban/jail.local`, and forces systemd backends so
  minimal Ubuntu/Debian images without `/var/log/auth.log` do not fail.
- **Deploy skill always clones into a new install directory.** The agent path
  performs a minimal host check, installs bootstrap tools, and refuses to touch
  existing checkout directories during a normal install.
- **Deploy skill avoids SSH host-key residue.** It now uses a temporary
  session-local `known_hosts` file, deletes it on shell exit, and does not
  print or persist VPS host fingerprints.
- **Ubuntu 22.04 installs now provision Python 3.11.** Pre-flight `--install`
  and `install.sh` install `python3.11` + `python3.11-venv` before creating the
  app venv, preserving the project's Python `>=3.11` runtime contract.
- **Service restart icons stay button-sized.** The service page restart SVG now
  has explicit dimensions and a local CSS guard so it cannot expand to the
  browser's default SVG size.

### Security — Codex audit follow-up #6

- **Sensitive runtime rewrites keep private permissions.** `sing-box` config,
  Caddy HTTPS config patches, install lock-down rewrites, and generated SQLite
  DB files now preserve owner-only permissions instead of inheriting a wider
  process umask.
- **Passkey login and revoke contracts fixed.** The login page now exposes the
  WebAuthn login flow when Passkey is enabled, and passkey management returns
  the full credential id the SPA needs to revoke a lost device.
- **Device deletion now clears retained per-device history.** Deleting a
  device removes its traffic and host history rows in addition to the device
  row and subscription file.
- **Production API docs disabled by default.** FastAPI `/docs`, `/redoc`, and
  `/openapi.json` are no longer mounted in the production app.
- **Telegram bot keeps token-only access local.** Optional bot mode can use the
  admin URL token from loopback without re-opening token-only auth to the
  public admin API.

### Security — Codex audit follow-up #5

- **Admin-token rotation keeps `config.yaml` private.** The atomic rewrite now
  chmods both the temporary file and final config back to `0600`, preventing a
  default umask from widening `/etc/proxybox/config.yaml` to `0644` and exposing
  `admin.token`.
- **Admin-token rotation response matches the SPA.** The backend now returns the
  `new_admin_url`, `old_token_short`, and no-restart timing fields the UI needs;
  the dialog builds a full URL from the browser origin and no longer tells users
  to wait for a restart that does not happen.
- **Passkey management routes realigned.** The SPA now calls the actual
  `/admin/{token}/api/auth/...` backend routes for passkey list/register/revoke,
  and uses the public `/auth/webauthn/logout` endpoint for logout.
- **Passkey challenge store capped.** In-memory WebAuthn challenges now evict
  stale entries and cap live entries to prevent unbounded memory growth from
  repeated public begin requests.

### Security — Codex audit follow-up #4

- **Forwarded-header trust restricted to local reverse proxies.** Login
  rate-limit keying and HTTPS cookie detection now only honor
  `X-Forwarded-For` / `X-Forwarded-Proto` when the socket peer is loopback.
  Direct traffic to `:8080` can no longer spoof `X-Forwarded-For` to evade
  per-IP backoff.
- **Final credential-location drift cleaned up.** Login-page hints, the
  passkey emergency text, install handoff text, and Claude deploy-skill
  recovery snippets now consistently read the password from
  `/etc/proxybox/admin.password`. The remaining UI token-rotation copy now
  describes the 192-bit `sub_token`.

### Security — Codex audit follow-up

- **Stored XSS hardening in the SPA.** Inline `onclick="fn('${escapeHtml(...)}')"`
  patterns let a single-quote inside an HTML-escaped value (`&#39;`) decode
  back to `'` once the browser parses the attribute, breaking out of the
  JS string literal. `dev.label` allowed arbitrary 64-char text, so an
  admin entering a hostile label could execute JS on their own session.
  Switched 13 inline-onclick template sites — device row actions
  (subs/rename/rotate/pause/resume/revoke/delete), passkey revoke,
  ban unblock, service restart, history jump (×3), conn-row toggle/
  rename/block, dialog-rotate — to `data-*` attributes plus two
  delegated event listeners.
- **Docker bootstrap now generates full admin credentials.** `app/bootstrap.py`
  previously only wrote `admin.token` to the freshly generated
  `config.yaml`, so with the default `features.url_token_bypass=false`
  the login form had no password to compare against and Docker installs
  were effectively locked out of the panel. Now generates `admin.username`,
  a 16-char alnum password in `/etc/proxybox/admin.password`, and
  `admin.login_path` (12-char alnum), then prints them in a single
  self-contained handoff block to the bootstrap container's stdout —
  matches `install.sh`'s behaviour.
- **`sub_token` entropy bumped 64 → 192 bits.** `secrets.token_hex(8)`
  (16 hex chars) replaced by `secrets.token_urlsafe(24)` (32 url-safe
  chars) in both `POST /api/devices/new` and `POST /devices/{name}/regen-subs`.
  The path-regex `[A-Za-z0-9_-]{8,64}` already accepted both, so existing
  shorter tokens remain valid until rotated.
- **Subscription file permissions tightened 0644 → 0600.** Files contain
  VLESS UUID + Hy2 password (effectively credentials); only the
  proxybox-admin process needs read access.
- **Default `/api/sub/{token}` + `/sub.txt` now do a DB revoke check.**
  Previously these two endpoints just read the on-disk `.txt`; a
  revoked device whose file lingered on disk would still serve. Both
  now route through `_device_by_sub_token`, which raises 410 on
  revoked devices — same behaviour the Clash/Merlin/Shadowrocket
  format endpoints already had.
- **Session cookie `Secure` flag now reflects request scheme.** Was
  hardcoded `secure=False`. Now `secure=True` when the request is
  HTTPS (direct or via trusted local `X-Forwarded-Proto: https` from Caddy)
  and `secure=False` otherwise. Bare-HTTP installs still work; HTTPS
  installs no longer leak the session cookie over a downgrade.
- **`POST /api/https/enable` returns the correct login URL.** Was
  hardcoded `https://{domain}/login`; now reads `admin.login_path` and
  returns `https://{domain}/login/{login_path}` when set, matching the
  rest of the post-install handoff.

### Security — Codex audit follow-up #3 (post-merge tail)

- **Login rate-limit on `/login/{secret}`.** A fourth speed bump in
  front of password brute-force, on top of (1) the random URL suffix,
  (2) the 16-char random password, and (3) constant-time compare.
  After 5 failed attempts from one IP in a 15-minute window, each
  subsequent failure adds an `asyncio.sleep` delay that doubles
  (1 → 2 → 4 → 8 → 16 → 60 s cap). A successful login or 15 min of
  no failures resets the counter. Per-IP keying respects `X-Forwarded-For`
  from local Caddy/nginx only. New module
  `app/services/login_rate_limit.py` + tests
  `tests/test_login_rate_limit.py`.
- **Docs aligned with v0.2.1 password file location.** README + 9
  docs files were still saying "password is in `/etc/proxybox/config.yaml`"
  even though v0.2.1 moved it to `/etc/proxybox/admin.password` (mode
  0400). Every recovery snippet now points at the new file. Support
  triage will no longer send users to the wrong path.
- **Final inline `onclick` migrated to delegated handler.** The "复制
  全部 URL" button at `static/index.html:4803` was the last hold-out
  passing dynamic data through an inline onclick. Same pattern as the
  rest of the audit-batch fixes: `data-base-url=` + delegated click
  listener.
- **Docker base images pinned.** `Dockerfile` was using floating
  `python:3.13-slim-bookworm`; `docker-compose.yml` was pulling
  `ghcr.io/sagernet/sing-box:latest`. Both now pin specific tags
  (`python:3.13.13-slim-bookworm`, `sing-box:v1.13.12`) so the
  build is reproducible and Dependabot's docker ecosystem opens a
  PR on each upstream bump.

### Security — Codex audit follow-up #2 (the deferred items)

- **Admin password moved out of `config.yaml`.** The password used to
  live inline in `/etc/proxybox/config.yaml` (mode 0600). A casual
  `cat config.yaml` in a screen-share / screenshot / backup would leak
  it. Now it lives in its own sibling file
  `/etc/proxybox/admin.password` (mode 0400, root-owned), written
  atomically via tmp + `os.replace`. `cat config.yaml` is now
  screenshot-safe; password recovery is still one `cat /etc/proxybox/admin.password`
  away over SSH. New `app/services/admin_password.py` module is the
  single writer (used by install.sh, Docker bootstrap, and the
  account POST handler).
- **Implicit migration.** The config loader now reads the password
  from the file when present; falls back to the YAML field for
  existing v0.2.x installs. The next password change via the SPA's
  Security → Login card writes to the file and strips the stale YAML
  field — drift-free upgrade with zero operator action.
- **`shell.py` rejects string commands.** The wrapper used to allow
  `shell.run("...some pipeline...")` which silently enabled
  `shell=True`. Current callsites all pass argv lists, so there's no
  active vulnerability, but the door is now closed: `shell=False` is
  explicit, and a string argument raises `TypeError` at runtime.
  The one historical string callsite (`top | awk` in
  `system_stats.cpu_pct`) was rewritten as pure-Python parsing.
- **CI supply-chain hardening.** Every third-party GitHub Action is
  now pinned to its commit SHA (with a `# vX.Y.Z` comment for diff
  readability) — was floating major tags like `@v4`. Dependabot
  config (`.github/dependabot.yml`) tracks three ecosystems
  (github-actions, pip, docker) and opens weekly PRs to bump pins.
  Two new workflows:
  - `pip-audit` in `test.yml` — fails CI on any CVE in the installed
    Python environment, scanned via `pip-audit --strict`.
  - `secrets-scan.yml` — second-layer secret scan via Yelp's
    `detect-secrets` (different ruleset from gitleaks), driven by
    `scripts/detect-secrets-ci.py`.

## [v0.2.0] — SPA English version + bilingual login form

### Added
- **Language toggle in the admin panel topbar** (`中/EN` button next to the
  theme switcher). Click to flip the SPA between Chinese and English; the
  choice is persisted in `localStorage` AND a `proxybox-lang` cookie so
  it sticks across reloads and is visible to the server-rendered login
  page too.
- **`I18N_DICT`** — a ~230-entry phrase-to-phrase dictionary embedded in
  `static/index.html` covering the highest-traffic UI surfaces (nav,
  page titles, KPI labels, primary buttons, common dialogs, error
  toasts, the 安全 → 登录设置 card, the HTTPS · 域名 page). Chinese is
  the source of truth; missing keys gracefully fall back to Chinese.
- **`translateNode()` walker** + **MutationObserver** — runs a single
  pass over `document.body` at load, then re-runs incrementally on every
  subtree mutation. JS-generated content (toasts, dialog bodies, table
  rows, KPI updates) is translated automatically without per-call `t()`
  wrapping.
- **Server-side bilingual login form**. `/login/{secret}?lang=en` (or
  `?lang=zh`) selects the language; a `proxybox-lang` cookie persists
  the choice for subsequent visits. The "EN ↔ 中" switch at the top
  right of the card reloads the page with the other language.

### Notes
- Coverage is ~80% of high-traffic text. Long composite sentences and
  rarely-seen warning dialogs still render in Chinese under `LANG=en`
  — they fall through the dictionary cleanly. Future patches add more
  entries; the only edit needed is appending to `I18N_DICT`.
- The MutationObserver only runs when `LANG === 'en'`, so Chinese-only
  users pay zero overhead.

## [v0.1.12] — copy buttons actually work; hardened clipboard fallback

### Fixed
- **「订阅链接」+「设备管理 → 📋 订阅 URL」 复制 buttons did nothing.**
  Inline `onclick="copyText(this, ${JSON.stringify(url)})"` produced HTML
  like `onclick="copyText(this, "http://..." )"` — the inner double
  quotes from `JSON.stringify` collided with the outer double quotes of
  the attribute, so the browser parsed the URL as text *outside* the
  attribute and the click handler never fired.
- Switched the two affected templates to `data-copy="..."` attributes
  (correctly HTML-escaped via `escapeHtml`) plus a single delegated
  `document.addEventListener('click', ...)` that matches `.btn-copy`.
  Eliminates the quoting trap class-wide.
- **`_writeClipboard` execCommand fallback** was using `top: -9999px;
  opacity: 0` to hide its temporary textarea. Newer Chrome / Safari
  refuse to copy from off-screen / invisible elements (treat it as
  "the user can't see what they're copying"). Replaced with a 1×1 px
  fixed-position textarea at z-index −1 — visually invisible but
  considered rendered by the engine, so execCommand succeeds. Also
  saves + restores scroll position so the page doesn't jump.

## [v0.1.11] — change username / password / rotate login path from the panel

### Added
- **`admin.login_path`** config field — a random 12-char alnum suffix.
  When set, the login form lives at `/login/{login_path}` and `/login`
  itself 404s, so bots probing common paths can't even confirm the form
  exists. Empty value preserves the legacy `/login` behaviour for
  existing installs.
- **`安全 → 登录设置` card** (top of the security page). Three rows:
  - **用户名** + edit button (validates alphanumeric, 2-32 chars)
  - **密码** + edit button (opens a 3-field dialog: current + new + confirm,
    client-side validates min-8 length + match, server-side requires
    correct current_password)
  - **登录路径** + 🎲 轮换 button (generates fresh 12-char suffix,
    旧地址立即 404; an inline note explains why this defends against
    /login brute-force)
- **`app/routers/account.py`** — `GET /api/admin/account` (read current
  state), `POST /api/admin/account` (change username + password with a
  `current_password` gate for the password change), `POST /api/admin/
  login-path` (rotate to random / specific value / "off"). All gated by
  the existing session-cookie auth; all touch `/etc/proxybox/config.yaml`
  + `reset_settings_cache()` so changes apply in-process without a
  self-restart.
- **install.sh** generates `ADMIN_LOGIN_PATH` on fresh installs and the
  summary prints the full `/login/{secret}` URL.

### Changed
- **`app/routers/login.py`** registers both `/login` and `/login/{secret}`
  paths. Both call `_login_path_ok()` which constant-time-compares the
  supplied secret against `admin.login_path` (or empty string when
  unset). Wrong secret → HTTP 404, not "invalid login" — keeps the form
  un-enumerable.
- **`ui.py`** redirects unauthed SPA loads to the configured login URL
  (`/login/{path}` or `/login`).
- **SPA `api()` helper** now attaches `err.detail` to thrown Errors for
  4xx responses with JSON bodies, so callers can show structured
  messages (used by the new account dialogs).
- **SPA `LOGIN_URL`** injected via the same template substitution as
  `{{TOKEN}}` — on a 401, the SPA bounces to the right path regardless
  of whether login_path is set.

### Why
User: "登录链接太简单, 容易被爆破" + "用户可以更改用户名和密码".
v0.1.10 ended with /login as the well-known login path and credentials
only editable via SSH-editing config.yaml. v0.1.11 closes both — random
path defeats /login bot scans, and the security page lets users rotate
credentials from the browser.

## [v0.1.10] — HTTPS enablement from the admin UI (no SSH needed)

### Added
- **「HTTPS · 域名」admin page**. New nav entry under 管理.  Shows current
  state (HTTPS on / configured but Caddy down / HTTP-only) and a 4-step
  wizard:
  1. Set an A record pointing at the auto-detected VPS IP
  2. Wait 1-10 min for DNS to propagate
  3. Type the domain + click 启用 HTTPS
  4. Visit the new https://{domain}/login URL
  Inline notes explain ports, cert expiry, rollback. Step text is plain
  enough for non-技术 users.
- **`app/services/caddy.py`** — Python implementation of the
  `enable-https.sh` flow. Validates domain syntax + DNS match, apt
  installs Caddy from Cloudsmith, opens firewall, writes Caddyfile,
  patches `config.yaml` (public_host / passkey.rp_id / origin),
  resets the in-process settings cache so admin picks up the new
  public_host **without self-restart**, then reloads Caddy.
  `HTTPSEnableError(code, detail)` raised on failure with structured
  codes (`invalid_domain` / `dns_no_answer` / `dns_mismatch` /
  `cmd_failed`) the SPA branches on for localised messages.
- **`/api/https/status`** + **`/api/https/enable`** — admin-gated
  endpoints driving the above page.
- **`deploy/enable-https.sh`** refactored into a thin wrapper around
  `python -m app.services.caddy <domain>` so CLI + UI share one
  implementation.

### Why
v0.1.9 already had `enable-https.sh`, but普通用户 don't SSH into
their VPS — they expect to configure things from the panel.  v0.1.10
closes that gap.  The HTTPS button is one click + one paste away,
with auto-detect of the VPS IP and step-by-step inline notes.

## [v0.1.9] — host categorization + HTTPS one-shot script + 24h heatmap fix

### Added
- **Per-device per-host traffic accounting**. The traffic worker now
  also samples sing-box Clash API's `metadata.host` per connection and
  buckets bytes into a new `host_log` table (`device_name, bucket_ts,
  host, app_group, rx, tx, conns`). Old buckets are pruned by the same
  retention window as `traffic_log`.
- **`app/services/host_classify.py`** — suffix-based domain → app-group
  lookup table (~120 entries). Categories: Video / Social / 通讯 /
  Google / Apple / Microsoft / AI / 开发工具 / CDN / Music / 游戏 /
  新闻 / 购物 / 其他. Generic categorisation only — no personal
  "sites I track" dictionary (the original §3 concern doesn't apply).
- **`/api/history/device/{name}`** now returns populated `hosts` and
  `apps` arrays from `host_log` (was empty placeholders in v0.1.8).
- **设备历史 SPA** drops the "v0.2 待实现" empty state and renders the
  按 App 类型 chart + 访问域名 table directly. Per-app-group `title`
  attribute shows the number of distinct hosts under each category.
- **`deploy/enable-https.sh <domain>`** — separate post-install script
  for HTTPS. Validates the domain resolves to this VPS, apt-installs
  Caddy from Cloudsmith, writes a reverse-proxy Caddyfile, updates
  `server.public_host` + `passkey.rp_id` + `passkey.origin` in
  `config.yaml`, restarts services. Let's Encrypt provisions the cert
  on first request — typical first-issuance latency ~10s. Bilingual
  (`--lang zh|en`).

### Fixed
- **24-hour activity heatmap was empty** even when bucket data existed.
  SPA was reading `d.hourly`, but the server returns `d.buckets[]` with
  `{date, hour, rx, tx}` (no pre-computed `total`). Folded the
  client-side conversion to `{date, hour, total: rx+tx}` so the
  heatmap fills the appropriate cells.

### Memory / project-policy update
- **CONSTRAINTS §3 partially reversed.** The original "no host-based
  traffic mapping" rule was about a personal-dictionary feature in
  BWG. Generic categorisation is different in kind: it doesn't expose
  which *specific* site within a category. User explicitly requested
  default-on, so the host_log table populates from install onward.

## [v0.1.8] — clipboard works on HTTP; 订阅链接 layout roomier; apps/hosts deferred-by-design

### Fixed
- **Copy buttons silently failed on HTTP**. `navigator.clipboard` only
  works in a "secure context" (HTTPS or `localhost`). With the admin
  panel on plain HTTP, copies fell into the `.catch()` toast with no
  recovery. Added `_writeClipboard()` helper that uses
  `navigator.clipboard` when available and falls back to a hidden
  `<textarea>` + `document.execCommand('copy')` for HTTP contexts.
  All three copy paths (`copyText` / `copySubUrl` / `copyAllSubUrls`)
  now use it.
- **CI lint failure** — ruff SIM108 on the `_fetch_json(stream)` branch
  in `app/routers/connections.py`. Collapsed to a ternary.

### Changed
- **`订阅链接` layout redesigned**. Previously a tight 3-column grid
  (`tag | URL | button` at `text-xs`). Now each format row is a
  vertical card: tag + description on top, full URL in its own
  monospace input-style box with proper padding, fixed-width copy
  button. Recommended row gets accent background + bolded tag instead
  of just an ✦ glyph. Easier to read on phones + the URL doesn't crowd
  the copy button.

### Notes (not a code bug — clearer messaging)
- **`设备历史` → 按 App 类型 / 访问域名** show no rows because v0.1.x
  intentionally doesn't track per-host or per-app traffic (BWG's
  host-fingerprint dictionary is intentionally dropped per CONSTRAINTS
  §3 for privacy). Replaced generic "暂无数据" with an explicit
  "App 维度统计 · v0.2 待实现" card explaining the design choice.
  The "访问域名 N 个" KPI now reads "—" rather than "0 个" so it's
  visibly distinct from a real zero.

## [v0.1.7] — SPA history pages no longer crash; logs hide uninstalled services

### Fixed
- **`总流量` page** threw `Cannot read properties of undefined (reading
  'label')`. `loadTrafficOverview` was calling `/api/history/all-daily`
  (system-wide daily rollup) but `renderTrafficOverview` reads per-device
  fields (`dev.label`, `dev.kind`, `dev.total`, `dev.daily[idx].total`).
  Switched the call to `/api/history/devices`, and expanded that
  endpoint's response to carry `devices[].label/kind/total`,
  `devices[].daily[].total`, plus top-level `dates`, `grand_total`,
  `active_count`.
- **`设备历史` page** same `'label'` crash. `/api/history/device/{name}`
  now joins to the `device` table for `device: {name, label, kind,
  last_ip, last_seen}`, rolls hourly buckets up into a `daily` array
  with `total`, and returns empty `hosts`/`apps` arrays (those are BWG
  host-fingerprint features intentionally dropped per CONSTRAINTS §3).
- **`日志` page tabs** for caddy / TG bot / 看门狗 returned HTTP 400.
  Hardcoded tab list dropped — `日志` view now iterates
  `lastStatus.services` (= `config.services.monitored`) to build tabs
  dynamically, matching the server-side allowlist on `/api/logs/{name}`.

### Removed
- **`订阅记录` nav entry**. v0.1.x doesn't ship the nginx-tail worker
  that backed this view in BWG; rather than show a "feature disabled"
  placeholder forever, the nav item is removed entirely.

### Notes (not bugs)
- `总览` "实时速度" shows 0 B/s when no client is actively transferring;
  this is correct — `/api/connections` reports the sing-box Clash API's
  instantaneous `up_bps/down_bps`, which goes to zero between flows.
  Switch on the phone and refresh — non-zero values appear.

## [v0.1.6] — username/password login is the default (URL-token bypass off)

### Changed (BREAKING for direct URL-token users)
- **`/admin/{token}/...` requires a session cookie by default.** The URL
  token alone no longer unlocks the panel — every request must present
  `proxybox_admin_session` (set by `/login`). Token in URL is still part
  of the route (defense in depth, prevents cookie replay against the
  wrong instance) but is not sufficient on its own.
- **`features.url_token_bypass: false`** is the new default. Flip to
  `true` in `config.yaml` if you need automation/SDK to use the URL
  token directly without a login round-trip.

### Added
- **`app/routers/login.py`** — GET/POST `/login` (self-contained HTML
  form, no JS), POST/GET `/logout` (clears cookie). Form validates
  `admin.username` + `admin.password` (constant-time compare), then
  issues the same itsdangerous-signed session cookie the passkey flow
  already uses.
- **`admin.username` + `admin.password`** in `config.yaml`. install.sh
  generates a 16-char alnum password at fresh-install time.
- **`{{PASSKEY_ENABLED}}` / `{{BOT_ENABLED}}`** SPA template injection
  so the front-end can hide nav entries for disabled opt-in features.
- **SPA `api()` helper** — on 401 redirects to `/login?next=<current>`,
  so a session-expired panel bounces to the form instead of throwing.

### Install summary redesign
The post-install card hierarchy now leads with the user-must-save
credentials in bold red:
```
🛡 后台登录凭据  — 务必复制保存
    登录地址  http://<vps>:8080/login
    用户名    admin                       (bold red)
    密  码    <16-char alnum>             (bold red)
```
Admin URL with token is no longer surfaced unless `url_token_bypass` is
on.

### Internals
- `app/auth/token.py` rewritten: session cookie + URL-token-match is the
  primary accept path; `url_token_bypass=true` is the opt-in fallback.
  401 carries `X-Login-URL: /login` header.
- `app/routers/ui.py` no longer uses the `admin_auth` dependency — does
  its own auth check inline so it can `RedirectResponse(303 → /login)`
  instead of returning JSON 401 for the SPA HTML route.
- install.sh logs in with the generated username/password and uses the
  session cookie for auto device creation while keeping
  `url_token_bypass: false`.

### Why
User feedback (2026-05-20): "默认使用账户密码登录, 关闭默认 token 登录
选项, 不安全". Tokens leak via screenshots / browser history more
easily than passwords; making the username/password flow the default
matches普通用户's mental model + restores a "logout" affordance.

### Dependencies
- `python-multipart >= 0.0.9` added (required by FastAPI's `Form(...)`
  parameter parsing).

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
