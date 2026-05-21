---
layout: home

hero:
  name: ProxyBox
  text: Per-device isolated proxy panel
  tagline: VLESS Reality + Hysteria2 · byte-level accounting · 1-click HTTPS · MIT
  actions:
    - theme: brand
      text: Get started →
      link: /guide
    - theme: alt
      text: Architecture
      link: /architecture
    - theme: alt
      text: GitHub
      link: https://github.com/carlos0xx/proxybox

features:
  - icon: 🔐
    title: Per-device credentials
    details: Every device has its own UUID + TCP/UDP port pair. Revoke one without touching the others. No shared subscriptions, no collateral damage.

  - icon: 📊
    title: Real traffic accounting
    details: Background worker polls sing-box's Clash API every 10 seconds. SQLite buckets bytes per device per hour and tags hosts into Video / Social / AI / CDN categories.

  - icon: 🔑
    title: Username + password login
    details: Login form at /login/{random-12-char-suffix}; /login itself 404s. URL-path token is opt-in for automation. Change creds + rotate the login path from the panel — no SSH.

  - icon: 🔒
    title: 1-click HTTPS
    details: Enter your domain, click Enable HTTPS. The panel installs Caddy, fetches a Let's Encrypt cert, and reloads — ~30 seconds end to end.

  - icon: 📲
    title: 5 subscription formats
    details: URI list (default) · clash.yaml · merlin.yaml · shadowrocket.conf · sub.txt. All generated on the fly per device — sing-box · Shadowrocket · Stash · Clash · Hiddify all work.

  - icon: 🌏
    title: Bilingual UI
    details: Topbar language switcher between English and Chinese. ~80% English coverage with graceful Chinese fallback. Login form also localised via ?lang=.

  - icon: 🤖
    title: Telegram bot (optional)
    details: /status · /devices · /traffic · /pause · /resume · /bans from your phone. Opt-in, runs as its own systemd service.

  - icon: 🚀
    title: Three deploy paths
    details: install.sh on Debian / Ubuntu, docker-compose anywhere, or let Claude Code drive the install via the bundled skill.

  - icon: 🏠
    title: Self-hosted, no SaaS
    details: Everything runs on the user's VPS. No phone-home, no API keys, no telemetry. Single VPS deploys family proxy infrastructure in under 10 minutes.
---
