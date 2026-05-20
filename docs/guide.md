# ProxyBox Guide · 使用指南

A short walkthrough — how to install, how to use day-to-day, where to look
when something breaks. For a full reference of every endpoint / every config
key, see [`architecture.md`](./architecture.md) and the per-router files
under [`api/`](./api/).

简版指南 — 怎么装、怎么用、出问题去哪查。完整端点 / 完整配置参考见
[`architecture.md`](./architecture.md) 和 [`api/`](./api/) 下按 router 分的文件。

---

> [**English** ⤵](#english-guide) · [**中文** ⤵](#中文指南)

---

## English guide

### 1 · What ProxyBox is for

ProxyBox is a self-hosted admin panel for a single VPS that runs sing-box.
The panel hands out **one VLESS Reality + one Hysteria2 inbound per device**,
so you can revoke a leaked phone subscription without touching the laptop /
router / family member. It accounts traffic per device, classifies destination
hosts into Video / Social / AI / CDN / etc., and exposes a Telegram-bot-driven
admin path for when you're on your phone.

It is **not** a hosted service. Everything runs on your own VPS — no
phone-home, no SaaS control plane.

### 2 · Prerequisites

- A clean **Debian 12 / 13** or **Ubuntu 22.04 / 24.04 / 26.04** VPS.
- **Root SSH access** (the installer uses apt + systemctl).
- **≥ 1 GB RAM** and **≥ 5 GB free disk**.
- These ports open on the VPS firewall:
  - `8080/tcp` — the admin panel (HTTP).
  - `11000-11050/tcp` — VLESS Reality (template at :11000, per-device at :11001+).
  - `21000-21050/udp` — Hysteria2 (template at :21000, per-device at :21001+).
  - **Add `80/tcp` + `443/tcp`** if you plan to turn on HTTPS later.
- A domain name pointing at the VPS is **optional but recommended** — it
  enables HTTPS and makes the admin URL share-friendly. Skip it if you'll
  always type the IP.

### 3 · Install

Pick one of three paths.

#### Path A — `install.sh` (recommended)

SSH in as root and:

```bash
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox
bash deploy/install.sh --lang en       # or --lang zh
```

The script is idempotent — safe to re-run if it ever bails mid-way. It will:

1. Validate the environment (`deploy/check-prereqs.sh`).
2. apt-install runtime deps (python3-venv, curl, sqlite3, openssl, fail2ban).
3. Download the latest stable `sing-box` binary.
4. Generate a Reality keypair, Hy2 cert, and a random SNI from a public-domain pool.
5. Write `/etc/sing-box/config.json` + `/etc/proxybox/config.yaml`.
6. Install 4 systemd units and start them.
7. Auto-create your first device (default name `phone-1`).
8. Print a self-contained handoff: **login URL, username, password, 5 sub URLs.**

Copy the credentials into a password manager before closing the terminal.

#### Path B — Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d
```

The `bootstrap` container generates a fresh `config.yaml` on first start.
After it's up, read the credentials with:

```bash
docker compose exec proxybox-admin \
    sh -c 'grep -E "username|password|login_path" /etc/proxybox/config.yaml'
```

This path doesn't include fail2ban or the auto-HTTPS UI — pair with Caddy
+ a host firewall for production.

#### Path C — Claude Code skill

If you use Claude Code, copy the bundled skill once:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

Then ask Claude to deploy:

> deploy proxybox on my VPS at 1.2.3.4, ssh key ~/.ssh/id_ed25519

Claude runs the same pre-flight checks and `install.sh`, then relays the
credentials.

### 4 · First-time login

Open the **login URL** the installer printed (it looks like
`http://YOUR-VPS:8080/login/<random-12char>`). The `/login` path **alone**
returns 404 — that random suffix is intentional and defends against
brute-force scans. Enter `admin` + the password, you'll land in the SPA
with a 30-day session cookie.

The auto-created `phone-1` device is already in **设备管理 / Devices** with
five subscription URLs in **订阅链接 / Endpoints**:

| Label | Format | Best for |
| --- | --- | --- |
| `[pick this]` *(default)* | URI list | sing-box, Shadowrocket "Type: Subscribe", Hiddify |
| `clash.yaml` | Mihomo / Clash YAML | Stash, Clash for iOS, Clash Verge |
| `merlin.yaml` | same + `tun:` block | AsusWRT-Merlin routers with Clash |
| `shadowrocket.conf` | Surge `.conf` | Shadowrocket native parser (fallback) |
| `sub.txt` | URI list (.txt alias) | Clients that key on file extension |

Paste the matching URL into your client's "Add subscription" / "Type:
Subscribe" dialog and you're done. `ifconfig.me` from the client device
should now report your VPS IP.

### 5 · Day-to-day operations

All from the panel — no SSH needed for any of this.

- **Add another device** → 设备管理 → 生成. Use generic names: `phone-1`,
  `phone-2`, `tablet-1`, `laptop-1`, `home-router`. Never personal names —
  device names go into the sing-box config and subscription file content,
  so they're a small surface for fingerprinting.
- **Rotate a leaked URL** → 设备管理 → 设备卡 → 🔄 换 URL. The device's
  `sub_token` changes; existing client subscriptions stop fetching.
- **Pause a device** → 设备管理 → 设备卡 → ⏸ 暂停. Choose indefinite or
  pick a timestamp. sing-box inbound is removed; bytes already used stay in
  the history.
- **Change your admin password / username** → 安全 → 登录设置 → 修改.
  Password change requires the current password (defends against
  session-hijack attackers changing the password before you notice).
- **Rotate the random login-path suffix** → 安全 → 登录设置 → 🎲 轮换.
  Old `/login/{old-suffix}` immediately 404s; existing logged-in sessions
  are not invalidated.
- **Turn on HTTPS** → HTTPS · 域名 → enter a domain that resolves to the
  VPS → 启用 HTTPS. ~30 seconds: panel validates DNS, apt-installs Caddy,
  fetches a Let's Encrypt cert, writes a reverse-proxy `Caddyfile`,
  updates `config.yaml`. New login URL is `https://{your-domain}/login/{suffix}`.
- **Watch traffic** → 总览 (real-time bps + connection count from
  sing-box's Clash API) or 总流量 (7-day per-device aggregate) or
  设备历史 (per-device drill-down: KPIs, daily chart, 24h heatmap, per-app
  category, per-host table).
- **Ban / unban an IP** → 安全 → enter an IP → 封禁. Wraps fail2ban.

### 6 · Where to look when something breaks

| Symptom | Try this |
| --- | --- |
| Panel loads but every page says "刷新失败" | Hard refresh (Cmd+Shift+R / Ctrl+F5). v0.1.6+ adds `Cache-Control: no-store` so this shouldn't happen on fresh installs. |
| "复制" button does nothing | Pre-v0.1.12 SPA. `cd /opt/proxybox && git pull && systemctl restart proxybox-admin` to upgrade. |
| Service shows "unknown" on the 服务 page | The service isn't in `config.services.monitored` or simply isn't installed (e.g. caddy before you turned on HTTPS — normal). |
| HTTPS provisioning fails with `dns_mismatch` | Your domain points at a different IP than this VPS. Update the A record and re-run. |
| Traffic page shows 0 even though you're browsing | The traffic worker took its first sample but no buckets are written. `journalctl -u proxybox-traffic-worker -n 20`. |
| Forgot the admin URL or password | `ssh root@VPS` → `grep -E "username\|password\|login_path" /etc/proxybox/config.yaml`. |

For everything else, the 日志 page in the panel has live `journalctl -u`
output for each tracked service.

### 7 · Where to read more

- [`README.md`](../README.md) — project hero + 3 deploy paths + architecture diagram.
- [`architecture.md`](./architecture.md) — service-by-service deep dive.
- [`api/`](./api/) — per-router endpoint reference.
- [`deploy/install-sh.md`](./deploy/install-sh.md) — what `install.sh` does, line by line.
- [`CHANGELOG.md`](../CHANGELOG.md) — every version's changes.

---

## 中文指南

### 1 · ProxyBox 是干嘛的

ProxyBox 是一个跑在单台 VPS 上的代理管理后台 (基于 sing-box)。给**每台设备
独立一对 VLESS Reality + Hysteria2 入站**,所以某台手机订阅泄漏可以单独 revoke,
不影响笔记本、路由器、家人的设备。按设备记账流量、按目标域名分类
(Video / Social / AI / CDN / 等等)、手机上能用 Telegram bot 远程管。

不是 SaaS 服务 —— 全在你自己 VPS 上跑,不回拨、没有共享控制面。

### 2 · 准备工作

- 一台干净的 **Debian 12 / 13** 或 **Ubuntu 22.04 / 24.04 / 26.04** VPS。
- **root SSH 访问** (安装器用 apt + systemctl)。
- **≥ 1 GB 内存** + **≥ 5 GB 空闲磁盘**。
- VPS 防火墙开这些端口:
  - `8080/tcp` — 管理后台 (HTTP)。
  - `11000-11050/tcp` — VLESS Reality (:11000 是模板,每设备 :11001+)。
  - `21000-21050/udp` — Hysteria2 (:21000 是模板,每设备 :21001+)。
  - **以后想开 HTTPS,加开 `80/tcp` + `443/tcp`**。
- 域名解析到 VPS **可选但推荐** —— 开 HTTPS 必备,而且后台地址好分享。如果你
  打算一直用 IP 访问,可以不准备。

### 3 · 安装

挑一种。

#### 方式 A — `install.sh` (推荐)

SSH 以 root 登录,然后:

```bash
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox
bash deploy/install.sh --lang zh       # 或 --lang en
```

脚本幂等,中途断了重跑没事。会做这几件事:

1. 跑环境检查 (`deploy/check-prereqs.sh`)。
2. apt 装运行依赖 (python3-venv、curl、sqlite3、openssl、fail2ban)。
3. 下载最新 stable `sing-box` 二进制。
4. 生成 Reality 密钥对 + Hy2 证书 + 从公共域名池随机挑 SNI。
5. 写 `/etc/sing-box/config.json` + `/etc/proxybox/config.yaml`。
6. 装 4 个 systemd unit 并启动。
7. **自动建第一台设备** (默认名 `phone-1`)。
8. 打印自包含的凭据 + 订阅 URL: **登录地址、用户名、密码、5 个订阅 URL**。

关闭终端前先把凭据抄到密码管理器。

#### 方式 B — Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d
```

`bootstrap` 容器首次启动时生成 `config.yaml`。起来后取凭据:

```bash
docker compose exec proxybox-admin \
    sh -c 'grep -E "username|password|login_path" /etc/proxybox/config.yaml'
```

这个路径不带 fail2ban 和自动 HTTPS UI —— 生产环境请配 Caddy + 主机防火墙。

#### 方式 C — Claude Code skill

如果你用 Claude Code,把 skill 复制过去一次:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

然后让 Claude 部署:

> 帮我在 1.2.3.4 这台 VPS 上部署 proxybox,SSH key 是 ~/.ssh/id_ed25519

Claude 会跑同样的 pre-flight 检查 + `install.sh`,然后把凭据转给你。

### 4 · 第一次登录

打开 install.sh 打印的**登录地址** (形如
`http://你的-VPS:8080/login/<12 位随机串>`)。`/login` 单独访问返回 404 ——
那串随机后缀是故意的,挡爆破扫描。输 `admin` + 密码,进 SPA,30 天 session cookie。

自动建好的 `phone-1` 设备已经在 **设备管理** 里,**订阅链接** 页有 5 种格式:

| 标签 | 格式 | 适合 |
| --- | --- | --- |
| `[推荐]` *(默认)* | URI 列表 | sing-box、Shadowrocket "Type: Subscribe"、Hiddify |
| `clash.yaml` | Mihomo / Clash YAML | Stash、Clash for iOS、Clash Verge |
| `merlin.yaml` | 同上 + `tun:` 块 | AsusWRT-Merlin 路由器跑 Clash |
| `shadowrocket.conf` | Surge `.conf` | Shadowrocket 原生解析器 (备用) |
| `sub.txt` | URI 列表 (.txt 别名) | 按扩展名识别的客户端 |

把对应 URL 粘进客户端的"添加订阅"/"Type: Subscribe"对话框,搞定。手机访问
`ifconfig.me` 应该已经显示你 VPS 的 IP。

### 5 · 日常操作

下面全部在后台做 —— 不用再 SSH。

- **加新设备** → 设备管理 → 生成。用泛化命名:`phone-1`、`phone-2`、
  `tablet-1`、`laptop-1`、`home-router`。**不要用个人名字** —— 设备名会进
  sing-box 配置和订阅文件内容,算一个小的指纹面。
- **轮换泄漏的 URL** → 设备管理 → 设备卡 → 🔄 换 URL。设备的 `sub_token`
  变了,客户端用老订阅会拉不到。
- **暂停设备** → 设备管理 → 设备卡 → ⏸ 暂停。可以选无限期或定时间。
  sing-box inbound 会被移除,之前用过的流量保留在历史里。
- **改 admin 密码 / 用户名** → 安全 → 登录设置 → 修改。改密码需要先输当前
  密码 (防 session 被劫后立刻被改密)。
- **轮换登录路径随机后缀** → 安全 → 登录设置 → 🎲 轮换。老的
  `/login/{老后缀}` 立刻 404;已登录的 session 不受影响。
- **开 HTTPS** → HTTPS · 域名 → 输入解析到 VPS 的域名 → 启用 HTTPS。
  30 秒左右:校验 DNS → apt 装 Caddy → 申 Let's Encrypt → 写反代
  `Caddyfile` → 更新 `config.yaml`。新登录地址变成
  `https://{你的域名}/login/{后缀}`。
- **看流量** → 总览 (实时 bps + 连接数,从 sing-box Clash API 取) /
  总流量 (7 天每设备聚合) / 设备历史 (单设备下钻:KPI、每日柱状、24h 热力图、
  按 App 分类、按域名细表)。
- **封禁 / 解封 IP** → 安全 → 输入 IP → 封禁。包装 fail2ban。

### 6 · 出问题去哪查

| 现象 | 试试 |
| --- | --- |
| 后台打开但每页都报"刷新失败" | 硬刷新 (Cmd+Shift+R / Ctrl+F5)。v0.1.6+ 加了 `Cache-Control: no-store`,新装实例不该出。 |
| "复制" 按钮没反应 | v0.1.12 之前的 SPA。`cd /opt/proxybox && git pull && systemctl restart proxybox-admin` 升级。 |
| 服务页某个服务显示 "unknown" | 这个 service 不在 `config.services.monitored` 或根本没装 (比如还没开 HTTPS 时的 caddy — 正常)。 |
| HTTPS 启用报 `dns_mismatch` | 你的域名解析到的不是这台 VPS。改 DNS A 记录后重试。 |
| 流量页一直 0 但你在过墙 | traffic worker 抓了第一拍但还没写桶。`journalctl -u proxybox-traffic-worker -n 20`。 |
| 忘了登录地址 / 密码 | `ssh root@VPS` → `grep -E "username\|password\|login_path" /etc/proxybox/config.yaml`。 |

剩下的,后台的「日志」页有每个服务的实时 `journalctl -u` 输出。

### 7 · 想了解更多

- [`README.md`](../README.md) — 项目介绍 + 3 种部署方式 + 架构图。
- [`architecture.md`](./architecture.md) — 按服务展开的详细架构。
- [`api/`](./api/) — 按 router 拆的接口参考。
- [`deploy/install-sh.md`](./deploy/install-sh.md) — `install.sh` 一行一行讲。
- [`CHANGELOG.md`](../CHANGELOG.md) — 每个版本的变更。
