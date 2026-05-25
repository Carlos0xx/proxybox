---
layout: home

hero:
  name: ProxyBox
  text: Per-device isolated proxy panel
  tagline: VLESS Reality + Hysteria2 · byte-level accounting · Docker-first install · MIT
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
    title: HTTPS options
    details: Docker installs can enable host Caddy + Let's Encrypt from the panel through an install-scoped helper. Native installs provision Caddy directly and refuse to overwrite user Caddy configs.

  - icon: 📲
    title: Subscription formats
    details: Shadowrocket split config · clash.yaml · merlin.yaml · default URI list. All generated on the fly per device — sing-box · Shadowrocket · Stash · Clash · Hiddify all work.

  - icon: 🐳
    title: Docker-first install
    details: Bridge-network stack with automatically selected free host ports. Existing services keep their ports; ProxyBox only publishes the chosen Admin, VLESS, and Hy2 ports.

  - icon: 🤖
    title: Telegram bot (optional)
    details: /status · /devices · /traffic · /pause · /resume · /bans from your phone. Opt-in; native uses systemd, Docker uses a sidecar profile.

  - icon: 🚀
    title: Multiple deploy paths
    details: Docker is the default path. Native install.sh remains available for clean VPS installs that need host fail2ban and Caddy integration.

  - icon: 🏠
    title: Self-hosted, no SaaS
    details: Everything runs on the user's VPS. No phone-home, no API keys, no telemetry. Single VPS deploys family proxy infrastructure in under 10 minutes.
---
