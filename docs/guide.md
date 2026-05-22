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
| **OS** | Debian/Ubuntu VPS. Docker path can run on an existing host; native path still expects a clean VPS. |
| **Access** | Root SSH or passwordless sudo. The Docker installer installs/starts Docker and Compose if missing. |
| **Resources** | ≥ 1 GB RAM · ≥ 5 GB free disk. |
| **Required ports** | Docker installer auto-selects free Admin, VLESS, and Hy2 ports and writes them to `.env`. |
| **For HTTPS later** | A domain pointing at the VPS · `80/tcp` + `443/tcp` open. **Optional but recommended.** |

---

### 3 · Install — pick one path

| Path | Best for | Reference |
| --- | --- | --- |
| **A · Interactive install** *(Docker recommended)* | Existing or clean Debian/Ubuntu VPS | [`deploy/docker.md`](./deploy/docker.md) |
| **B · Claude Code / Codex** | Users with an AI coding agent | [`deploy/claude-skill.md`](./deploy/claude-skill.md) |
| **C · `install.sh`** | Clean Debian/Ubuntu VPS needing host fail2ban/Caddy | [`deploy/install-sh.md`](./deploy/install-sh.md) |

#### Path A — Interactive install *(Docker recommended)*

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR"
bash deploy/install.sh
```

The installer shows a Chinese mode picker and requires an explicit `1` or `2` choice. Pick Docker to check Docker/Compose and `ss`/`iproute2`, install missing runtime packages, start Docker, scan host ports, print/write a fresh isolated Compose project to `.env`, start a bridge-network stack, and install narrow Docker guard + HTTPS helper units for this project only. If the VPS already runs websites, panels, or production services, choose Docker. Native install writes Python, sing-box, systemd units, and fail2ban directly to the host; only use it on a clean dedicated VPS.

> **Installation red line:** never delete, modify, overwrite, or reuse files/services on the user's VPS outside this install. Even if `/opt/proxybox` or another same-name directory already exists, leave it untouched and clone into a new `proxybox-<timestamp>-<suffix>` directory.

#### Path B — Claude Code / Codex

For Claude Code, install the bundled skill once:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

Then ask in any session:

> deploy proxybox on my VPS at 1.2.3.4 using ~/.ssh/id_ed25519

The agent must ask you to choose Docker or native first; Docker already being installed, recommended, or a better fit for the ports is not consent. After your explicit answer it walks auto-deleted temporary SSH `known_hosts` → minimal VPS check → clone into a fresh install directory → `deploy/install.sh --docker` or `deploy/install.sh --native --fresh` → verification → relays the credentials back. For Codex or other agents, point them at [`deploy/claude-skill/SKILL.md`](../deploy/claude-skill/SKILL.md) directly.

#### Path C — `install.sh`

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR"
bash deploy/install.sh --native --fresh --lang en       # or --lang zh
```

Native `--fresh` proceeds only when no previous ProxyBox/sing-box native state is present. It never deletes old state automatically. End-to-end ~3 minutes on a clean VPS and prints a self-contained handoff: **login URL · username · password · subscription URLs**.

> [!IMPORTANT]
> Copy the credentials into a password manager **before closing the terminal**. Recovery via SSH: `cat /etc/proxybox/admin.password` (mode 0400) for the password; the rest is in `/etc/proxybox/config.yaml`.

### 4 · First-time login

Open the **login URL** the installer printed:

```text
http://<your-vps>:<admin-port>/login/<random-12-char-suffix>
```

> [!NOTE]
> The bare `/login` returns **404**. The random suffix is by design — it stops scanners from confirming a login form even exists.

Enter `admin` + the printed password. A 30-day session cookie is set; you land in the SPA.

The auto-created first device uses a **5-letter random lowercase name** and is already in the **Devices** page. The subscription URLs are in **Endpoints**:

| Format | Best for |
| --- | --- |
| `shadowrocket.yaml` | Shadowrocket 订阅链接 · 节点+规则 |
| `clash.yaml` | Stash · Clash for iOS · Clash Verge |
| `merlin.yaml` | AsusWRT-Merlin routers with Clash |
| `[generic]` *(default URI list)* | sing-box · Hiddify · basic node clients |

Paste the matching URL into your client's "Add subscription" dialog. Then verify on the client device: `https://ifconfig.me` should now report your VPS's IP.

> [!TIP]
> The admin SPA is Chinese-only. English documentation remains available in the repo, but the production UI no longer ships a language toggle.

---

### 5 · Day-to-day operations

Mostly from the panel. Docker installs can enable HTTPS from the panel through the install-scoped host helper.

| Task | Where | Notes |
| --- | --- | --- |
| **Add a device** | Devices → New | Use generic names (`tablet-1`, `home-router`) or random lowercase strings. Avoid personal names — they bleed into sing-box config and sub files. |
| **Rotate a leaked URL** | Devices → 🔄 New URL | `sub_token` rotates; UUID + ports unchanged. Client re-imports once. |
| **Pause a device** | Devices → ⏸ Pause | Indefinite or until a timestamp. Inbound removed; traffic history preserved. |
| **Change password / username** | Security → Login → Edit | Requires the current password (defends against session-hijack re-auth). |
| **Rotate login-path suffix** | Security → Login → 🎲 Rotate | Old `/login/{old}` 404s immediately. Existing sessions stay valid. |
| **Enable HTTPS** | HTTPS page | Docker: host helper validates DNS and configures host Caddy. Native: provisions Caddy directly. |
| **Watch live traffic** | Overview | Real-time bps + connection count from sing-box's Clash API. |
| **Per-device drilldown** | History | KPIs · daily chart · 24h heatmap · per-app category · per-host table. |
| **Ban / unban an IP** | Security → Bans | Wraps fail2ban. |

---

### 6 · Troubleshooting

| Symptom | Try this |
| --- | --- |
| Every page says "refresh failed" | Hard refresh (Cmd+Shift+R / Ctrl+F5). v0.1.6+ sends `Cache-Control: no-store` so fresh installs shouldn't hit this. |
| Copy button does nothing | Pre-v0.1.12 SPA. For new installs, clone the latest code into a new install directory. Upgrade only if you explicitly choose the existing install directory. |
| Service shows "unknown" on Services page | Not in `services.monitored` or not installed (e.g. `caddy` before HTTPS is on — normal). |
| HTTPS provisioning → `dns_mismatch` | Your domain doesn't resolve to this VPS. Update the A record and retry. |
| Traffic page shows 0 while browsing | The worker took its first sample but no buckets are flushed yet. Check `cd <proxybox-install-dir> && docker compose logs --tail=80 proxybox-traffic-worker`. |
| Forgot login URL or password | `cd <proxybox-install-dir> && docker compose exec proxybox-admin sh -c 'cat /etc/proxybox/admin.password; grep -E "username\|login_path" /etc/proxybox/config.yaml'`. |

Logs for Docker services are available with `docker compose logs`.

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
| **系统** | Debian/Ubuntu VPS。Docker 路径可跑在已有服务的机器上;裸机路径仍建议干净 VPS。 |
| **访问** | root SSH 或免密 sudo。Docker/Compose 缺失时安装器会自动安装并启动。 |
| **资源** | ≥ 1 GB 内存 · ≥ 5 GB 空闲磁盘。 |
| **必开端口** | Docker 安装器会自动挑空闲的 Admin、VLESS、Hy2 端口并写入 `.env`。 |
| **想开 HTTPS** | 域名解析到 VPS · `80/tcp` + `443/tcp` 开放。**可选但推荐。** |

---

### 3 · 安装 — 挑一种

| 方式 | 适合 | 详细 |
| --- | --- | --- |
| **A · 交互式安装** *(默认推荐 Docker)* | 已有或干净的 Debian/Ubuntu VPS | [`deploy/docker.md`](./deploy/docker.md) |
| **B · Claude Code / Codex** | 手边有 AI 代理的用户 | [`deploy/claude-skill.md`](./deploy/claude-skill.md) |
| **C · `install.sh`** | 需要宿主 fail2ban/Caddy 的干净 VPS | [`deploy/install-sh.md`](./deploy/install-sh.md) |

#### 方式 A — 交互式安装 *(默认推荐 Docker)*

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR"
bash deploy/install.sh
```

安装器会用中文提示选择 Docker 或宿主机,并强制输入 `1` 或 `2`。推荐选 Docker:容器隔离、自动避开已占用端口,并安装只属于本项目的 Docker guard + HTTPS helper。如果 VPS 已经跑了其他服务、网站、面板或生产系统,强烈推荐 Docker。宿主机安装会直接安装 Python、sing-box、systemd unit、fail2ban,仅建议用于干净、专用、不跑其他生产服务的 VPS。

> **安装红线:** 不要删除、修改、覆盖或复用用户 VPS 上本次安装以外的任何文件和服务。即便宿主机已经存在 `/opt/proxybox` 或同名目录,也必须保留不动,改用新的 `proxybox-<时间戳>-<后缀>` 目录。

#### 方式 B — Claude Code / Codex

Claude Code 用户先把 skill 复制过去一次:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

然后在对话里:

> 帮我在 1.2.3.4 这台 VPS 上部署 proxybox,SSH key 是 ~/.ssh/id_ed25519

代理必须先让你选择 Docker 或宿主机安装;服务器已有 Docker、README 推荐 Docker、端口更适合 Docker 都不能代替你的选择。确认后再走自动删除的临时 SSH `known_hosts` → 最小 VPS 检查 → 克隆到新的安装目录 → `deploy/install.sh --docker` 或 `deploy/install.sh --native --fresh` → 验证服务 → 把凭据发给你。Codex 或其他代理:直接把 [`deploy/claude-skill/SKILL.md`](../deploy/claude-skill/SKILL.md) 喂给它即可。

#### 方式 C — `install.sh`

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR"
bash deploy/install.sh --native --fresh --lang zh       # 或 --lang en
```

宿主机 `--fresh` 只在没有旧 ProxyBox/sing-box native 状态时继续,不会自动删除旧状态。干净 VPS 上端到端 ~3 分钟。打印自包含的凭据 + 订阅 URL:**登录地址 · 用户名 · 密码 · 订阅 URL**。

> [!IMPORTANT]
> **关闭终端前**先把凭据抄到密码管理器。SSH 找回:密码在 `/etc/proxybox/admin.password` (0400),其余 (用户名 / login_path / token) 在 `/etc/proxybox/config.yaml`。

### 4 · 第一次登录

打开安装器打印的**登录地址**:

```text
http://<你的-VPS>:<admin-port>/login/<12 位随机串>
```

> [!NOTE]
> `/login` 单独访问返回 **404**。后面的随机后缀是故意的 —— 扫描器连登录表单存在都确认不了。

输 `admin` + 打印的密码。30 天 session cookie 设上,进 SPA。

自动建好的第一台设备会使用 **5 位小写随机名**,已经在 **设备管理** 里。**订阅链接** 页显示 4 种格式:

| 格式 | 适合 |
| --- | --- |
| `shadowrocket.yaml` | Shadowrocket 订阅链接 · 节点+规则 |
| `clash.yaml` | Stash · Clash for iOS · Clash Verge |
| `merlin.yaml` | AsusWRT-Merlin 路由器跑 Clash |
| `[通用]` *(默认 URI 列表)* | sing-box · Hiddify · 普通节点客户端 |

把对应 URL 粘进客户端的 "添加订阅" 对话框。客户端访问 `https://ifconfig.me` 应该已经显示你 VPS 的 IP。

---

### 5 · 日常操作

大多数操作都在后台做。Docker 安装可以在后台通过本次安装专属的宿主机 helper 启用 HTTPS。

| 任务 | 在哪 | 说明 |
| --- | --- | --- |
| **加新设备** | 设备管理 → 生成 | 用泛化命名 (`tablet-1`、`home-router`) 或小写随机串。**不要用个人名字** —— 设备名会进 sing-box 配置和订阅文件,算指纹面。 |
| **轮换泄漏的 URL** | 设备管理 → 🔄 换 URL | `sub_token` 变了;UUID + 端口不变。客户端重新导入一次。 |
| **暂停设备** | 设备管理 → ⏸ 暂停 | 选无限期或定时间。inbound 移除,历史流量保留。 |
| **改密码 / 用户名** | 安全 → 登录设置 → 修改 | 改密码需先输当前密码 (防 session 被劫后立刻被改密)。 |
| **轮换登录路径后缀** | 安全 → 登录设置 → 🎲 轮换 | 老的 `/login/{老后缀}` 立刻 404。已登录 session 不受影响。 |
| **开 HTTPS** | HTTPS · 域名页 | Docker:宿主机 helper 验证 DNS 并配置宿主 Caddy。裸机:直接配置 Caddy。 |
| **看实时流量** | 总览 | 实时 bps + 连接数,从 sing-box Clash API 取。 |
| **单设备下钻** | 设备历史 | KPI · 每日柱状 · 24h 热力图 · 按 App 分类 · 按域名细表。 |
| **封禁 / 解封 IP** | 安全 → 封禁 | 包装 fail2ban。 |

---

### 6 · 排错

| 现象 | 试试 |
| --- | --- |
| 每页报 "刷新失败" | 硬刷新 (Cmd+Shift+R / Ctrl+F5)。v0.1.6+ 加了 `Cache-Control: no-store`,新装实例不该出。 |
| "复制" 按钮没反应 | v0.1.12 之前的 SPA。新安装就克隆最新代码到新目录;只有明确选中已有安装目录时才原地升级。 |
| 服务页某服务 "unknown" | 不在 `services.monitored` 或没装 (比如还没开 HTTPS 的 caddy —— 正常)。 |
| HTTPS 启用报 `dns_mismatch` | 域名解析的不是这台 VPS。改 DNS A 记录后重试。 |
| 流量页一直 0 但你在过墙 | worker 抓了第一拍但还没写桶。`cd <proxybox-安装目录> && docker compose logs --tail=80 proxybox-traffic-worker`。 |
| 忘了登录地址 / 密码 | `cd <proxybox-安装目录> && docker compose exec proxybox-admin sh -c 'cat /etc/proxybox/admin.password; grep -E "username\|login_path" /etc/proxybox/config.yaml'`。 |

Docker 服务日志用 `docker compose logs` 查看。

---

### 7 · 想了解更多

- [快速上手](./getting-started.md) · 10 分钟内装好
- [架构](./architecture.md) · 按服务展开的详细架构
- [API 端点](./api/endpoints.md) · 按 router 拆的接口参考
- [更新日志](../CHANGELOG.md) · 每个版本的变更
- [← 回到 README](../README.zh.md)
