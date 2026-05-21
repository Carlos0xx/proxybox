# Guide · 使用指南

> Day-to-day usage walkthrough — install, drive the panel, troubleshoot.
> 日常使用指南 —— 怎么装、怎么用、出问题去哪查。

For a per-endpoint reference, see [`api/endpoints.md`](./api/endpoints.md). For service internals, see [`architecture.md`](./architecture.md).

<p>
  <a href="#english-guide"><strong>English ↓</strong></a> ·
  <a href="#中文指南"><strong>中文 ↓</strong></a>
</p>

---

## English guide

### 1 · What ProxyBox is for

ProxyBox is a self-hosted admin panel for a single VPS running sing-box. It hands out **one VLESS Reality + one Hysteria2 inbound per device**, so a leaked phone subscription can be revoked without touching the laptop, router, or family-member devices.

It accounts traffic per device, classifies destination hosts (Video / Social / AI / CDN / etc.), and exposes a Telegram-bot admin path for when you're on your phone.

> [!NOTE]
> ProxyBox is **not** a hosted service. Everything runs on your own VPS — no phone-home, no SaaS control plane.

---

### 2 · Prerequisites

| Requirement | Detail |
| --- | --- |
| **OS** | Debian 12/13 or Ubuntu 22.04/24.04/26.04 — clean install. |
| **Access** | Root SSH (the installer uses `apt` + `systemctl`). |
| **Resources** | ≥ 1 GB RAM · ≥ 5 GB free disk. |
| **Required ports** | `8080/tcp` (admin) · `11000-11050/tcp` (VLESS) · `21000-21050/udp` (Hysteria2). |
| **For HTTPS later** | A domain pointing at the VPS · `80/tcp` + `443/tcp` open. **Optional but recommended.** |

---

### 3 · Install — pick one path

| Path | Best for | Reference |
| --- | --- | --- |
| **A · Claude Code / Codex** *(recommended)* | Users with an AI coding agent | [`deploy/claude-skill.md`](./deploy/claude-skill.md) |
| **B · `install.sh`** | Fresh Debian/Ubuntu VPS | [`deploy/install-sh.md`](./deploy/install-sh.md) |
| **C · Docker Compose** | Anywhere with Docker | [`deploy/docker.md`](./deploy/docker.md) |

#### Path A — Claude Code / Codex *(recommended)*

For Claude Code, install the bundled skill once:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

Then ask in any session:

> deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519

The agent walks minimal VPS check → `git clone` / update → full pre-flight → `install.sh` → verification → relays the credentials back. For Codex or other agents, point them at [`deploy/claude-skill/SKILL.md`](../deploy/claude-skill/SKILL.md) directly.

#### Path B — `install.sh`

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox
bash deploy/install.sh --lang en       # or --lang zh
```

Idempotent — safe to re-run if it bails mid-way. End-to-end ~3 minutes. Prints a self-contained handoff: **login URL · username · password · 5 subscription URLs**.

> [!IMPORTANT]
> Copy the credentials into a password manager **before closing the terminal**. Recovery via SSH: `cat /etc/proxybox/admin.password` (mode 0400) for the password; the rest is in `/etc/proxybox/config.yaml`.

#### Path C — Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d
docker compose exec proxybox-admin \
    sh -c 'cat /etc/proxybox/admin.password; grep -E "username|login_path" /etc/proxybox/config.yaml'
```

Bootstrap container generates the config on first start. No fail2ban, no HTTPS UI on this path — pair with Caddy + a host firewall for production.

---

### 4 · First-time login

Open the **login URL** the installer printed:

```text
http://<your-vps>:8080/login/<random-12-char-suffix>
```

> [!NOTE]
> The bare `/login` returns **404**. The random suffix is by design — it stops scanners from confirming a login form even exists.

Enter `admin` + the printed password. A 30-day session cookie is set; you land in the SPA.

The auto-created **`phone-1`** device is already in the **Devices** page. The five subscription URLs are in **Endpoints**:

| Format | Best for |
| --- | --- |
| `[pick this]` *(default URI list)* | sing-box · Shadowrocket "Type: Subscribe" · Hiddify |
| `clash.yaml` | Stash · Clash for iOS · Clash Verge |
| `merlin.yaml` | AsusWRT-Merlin routers with Clash |
| `shadowrocket.conf` | Shadowrocket native parser (fallback) |
| `sub.txt` | Clients that key on the `.txt` extension |

Paste the matching URL into your client's "Add subscription" dialog. Then verify on the client device: `https://ifconfig.me` should now report your VPS's IP.

> [!TIP]
> The SPA ships bilingual — every UI label below also exists in Chinese. Flip the language with the topbar switcher if you prefer.

---

### 5 · Day-to-day operations

All from the panel — no SSH needed for anything below.

| Task | Where | Notes |
| --- | --- | --- |
| **Add a device** | Devices → New | Use generic names (`phone-1`, `tablet-1`, `home-router`). Avoid personal names — they bleed into sing-box config and sub files. |
| **Rotate a leaked URL** | Devices → 🔄 New URL | `sub_token` rotates; UUID + ports unchanged. Client re-imports once. |
| **Pause a device** | Devices → ⏸ Pause | Indefinite or until a timestamp. Inbound removed; traffic history preserved. |
| **Change password / username** | Security → Login → Edit | Requires the current password (defends against session-hijack re-auth). |
| **Rotate login-path suffix** | Security → Login → 🎲 Rotate | Old `/login/{old}` 404s immediately. Existing sessions stay valid. |
| **Enable HTTPS** | HTTPS → Enable | ~30 s: DNS check → Caddy + Let's Encrypt → config update + reload. |
| **Watch live traffic** | Overview | Real-time bps + connection count from sing-box's Clash API. |
| **Per-device drilldown** | History | KPIs · daily chart · 24h heatmap · per-app category · per-host table. |
| **Ban / unban an IP** | Security → Bans | Wraps fail2ban. |

---

### 6 · Troubleshooting

| Symptom | Try this |
| --- | --- |
| Every page says "refresh failed" | Hard refresh (Cmd+Shift+R / Ctrl+F5). v0.1.6+ sends `Cache-Control: no-store` so fresh installs shouldn't hit this. |
| Copy button does nothing | Pre-v0.1.12 SPA. `cd /opt/proxybox && git pull && systemctl restart proxybox-admin`. |
| Service shows "unknown" on Services page | Not in `services.monitored` or not installed (e.g. `caddy` before HTTPS is on — normal). |
| HTTPS provisioning → `dns_mismatch` | Your domain doesn't resolve to this VPS. Update the A record and retry. |
| Traffic page shows 0 while browsing | The worker took its first sample but no buckets are flushed yet. Check `journalctl -u proxybox-traffic-worker -n 20`. |
| Forgot login URL or password | `ssh root@<VPS>` → `cat /etc/proxybox/admin.password; grep -E "username\|login_path" /etc/proxybox/config.yaml`. |

Logs for any tracked service are live on the **Logs** page.

---

### 7 · Read more

- [Getting started](./getting-started.md) · install in 10 minutes
- [Architecture](./architecture.md) · service-by-service deep dive
- [API endpoints](./api/endpoints.md) · per-router reference
- [Changelog](../CHANGELOG.md) · per-version changes
- [← Back to README](../README.md)

---

## 中文指南

### 1 · ProxyBox 是干嘛的

ProxyBox 是跑在单台 VPS 上的 sing-box 管理后台。给**每台设备独立一对 VLESS Reality + Hysteria2 入站** —— 某台手机订阅泄漏可以单独 revoke,不影响笔记本、路由器、家人的设备。

按设备记账流量、按目标域名分类 (Video / Social / AI / CDN 等等),手机上能用 Telegram bot 远程管。

> [!NOTE]
> 不是 SaaS 服务 —— 全在你自己 VPS 上跑,不回拨、没有共享控制面。

---

### 2 · 准备工作

| 要求 | 详情 |
| --- | --- |
| **系统** | Debian 12/13 或 Ubuntu 22.04/24.04/26.04 — 干净安装。 |
| **访问** | root SSH (安装器用 `apt` + `systemctl`)。 |
| **资源** | ≥ 1 GB 内存 · ≥ 5 GB 空闲磁盘。 |
| **必开端口** | `8080/tcp` (后台) · `11000-11050/tcp` (VLESS) · `21000-21050/udp` (Hysteria2)。 |
| **想开 HTTPS** | 域名解析到 VPS · `80/tcp` + `443/tcp` 开放。**可选但推荐。** |

---

### 3 · 安装 — 挑一种

| 方式 | 适合 | 详细 |
| --- | --- | --- |
| **A · Claude Code / Codex** *(推荐)* | 手边有 AI 代理的用户 | [`deploy/claude-skill.md`](./deploy/claude-skill.md) |
| **B · `install.sh`** | 干净的 Debian/Ubuntu VPS | [`deploy/install-sh.md`](./deploy/install-sh.md) |
| **C · Docker Compose** | 任何带 Docker 的环境 | [`deploy/docker.md`](./deploy/docker.md) |

#### 方式 A — Claude Code / Codex *(推荐)*

Claude Code 用户先把 skill 复制过去一次:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

然后在对话里:

> 帮我在 1.2.3.4 这台 VPS 上部署 proxybox,SSH key 是 ~/.ssh/id_ed25519

代理走最小 VPS 检查 → `git clone` / 更新 → 完整 pre-flight → `install.sh` → 验证服务 → 把凭据发给你。Codex 或其他代理:直接把 [`deploy/claude-skill/SKILL.md`](../deploy/claude-skill/SKILL.md) 喂给它即可。

#### 方式 B — `install.sh`

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox
bash deploy/install.sh --lang zh       # 或 --lang en
```

幂等 —— 中途断了重跑没事。端到端 ~3 分钟。打印自包含的凭据 + 订阅 URL:**登录地址 · 用户名 · 密码 · 5 个订阅 URL**。

> [!IMPORTANT]
> **关闭终端前**先把凭据抄到密码管理器。SSH 找回:密码在 `/etc/proxybox/admin.password` (0400),其余 (用户名 / login_path / token) 在 `/etc/proxybox/config.yaml`。

#### 方式 C — Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d
docker compose exec proxybox-admin \
    sh -c 'cat /etc/proxybox/admin.password; grep -E "username|login_path" /etc/proxybox/config.yaml'
```

`bootstrap` 容器首次启动时生成 config。这个路径不带 fail2ban 和 HTTPS UI —— 生产环境请配 Caddy + 主机防火墙。

---

### 4 · 第一次登录

打开 install.sh 打印的**登录地址**:

```text
http://<你的-VPS>:8080/login/<12 位随机串>
```

> [!NOTE]
> `/login` 单独访问返回 **404**。后面的随机后缀是故意的 —— 扫描器连登录表单存在都确认不了。

输 `admin` + 打印的密码。30 天 session cookie 设上,进 SPA。

自动建好的 **`phone-1`** 设备已经在 **设备管理** 里。**订阅链接** 页有 5 种格式:

| 格式 | 适合 |
| --- | --- |
| `[推荐]` *(默认 URI 列表)* | sing-box · Shadowrocket "Type: Subscribe" · Hiddify |
| `clash.yaml` | Stash · Clash for iOS · Clash Verge |
| `merlin.yaml` | AsusWRT-Merlin 路由器跑 Clash |
| `shadowrocket.conf` | Shadowrocket 原生解析器 (备用) |
| `sub.txt` | 按 `.txt` 扩展名识别的客户端 |

把对应 URL 粘进客户端的 "添加订阅" 对话框。客户端访问 `https://ifconfig.me` 应该已经显示你 VPS 的 IP。

---

### 5 · 日常操作

下面全在后台做 —— 不用再 SSH。

| 任务 | 在哪 | 说明 |
| --- | --- | --- |
| **加新设备** | 设备管理 → 生成 | 用泛化命名 (`phone-1`、`tablet-1`、`home-router`)。**不要用个人名字** —— 设备名会进 sing-box 配置和订阅文件,算指纹面。 |
| **轮换泄漏的 URL** | 设备管理 → 🔄 换 URL | `sub_token` 变了;UUID + 端口不变。客户端重新导入一次。 |
| **暂停设备** | 设备管理 → ⏸ 暂停 | 选无限期或定时间。inbound 移除,历史流量保留。 |
| **改密码 / 用户名** | 安全 → 登录设置 → 修改 | 改密码需先输当前密码 (防 session 被劫后立刻被改密)。 |
| **轮换登录路径后缀** | 安全 → 登录设置 → 🎲 轮换 | 老的 `/login/{老后缀}` 立刻 404。已登录 session 不受影响。 |
| **开 HTTPS** | HTTPS · 域名 → 启用 HTTPS | ~30 秒:DNS 校验 → Caddy + Let's Encrypt → config 更新 + 重载。 |
| **看实时流量** | 总览 | 实时 bps + 连接数,从 sing-box Clash API 取。 |
| **单设备下钻** | 设备历史 | KPI · 每日柱状 · 24h 热力图 · 按 App 分类 · 按域名细表。 |
| **封禁 / 解封 IP** | 安全 → 封禁 | 包装 fail2ban。 |

---

### 6 · 排错

| 现象 | 试试 |
| --- | --- |
| 每页报 "刷新失败" | 硬刷新 (Cmd+Shift+R / Ctrl+F5)。v0.1.6+ 加了 `Cache-Control: no-store`,新装实例不该出。 |
| "复制" 按钮没反应 | v0.1.12 之前的 SPA。`cd /opt/proxybox && git pull && systemctl restart proxybox-admin`。 |
| 服务页某服务 "unknown" | 不在 `services.monitored` 或没装 (比如还没开 HTTPS 的 caddy —— 正常)。 |
| HTTPS 启用报 `dns_mismatch` | 域名解析的不是这台 VPS。改 DNS A 记录后重试。 |
| 流量页一直 0 但你在过墙 | worker 抓了第一拍但还没写桶。`journalctl -u proxybox-traffic-worker -n 20`。 |
| 忘了登录地址 / 密码 | `ssh root@VPS` → `cat /etc/proxybox/admin.password; grep -E "username\|login_path" /etc/proxybox/config.yaml`。 |

后台的「日志」页有每个服务的实时 `journalctl -u` 输出。

---

### 7 · 想了解更多

- [快速上手](./getting-started.md) · 10 分钟内装好
- [架构](./architecture.md) · 按服务展开的详细架构
- [API 端点](./api/endpoints.md) · 按 router 拆的接口参考
- [更新日志](../CHANGELOG.md) · 每个版本的变更
- [← 回到 README](../README.zh.md)
