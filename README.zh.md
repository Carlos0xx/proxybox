<div align="right">

[English](./README.md) · **中文**

</div>

# ProxyBox

> **自托管的、按设备隔离的代理管理面板。** VPS 上每台手机、笔记本、路由器都有
> 自己独立的 VLESS Reality + Hysteria2 入站,字节级流量记账,可选 Telegram bot
> 控制 + WebAuthn passkey 登录,管理后台一键 HTTPS + 用户名密码轮换。MIT 协议。

---

## ✨ 你能得到什么

- **按设备独立入站** — 每个设备一对独立的 UUID + 端口。某台设备凭证泄漏只 revoke
  那一台,不影响其他设备。(`config/sing-box.json` 由 `POST /api/devices/new`
  per-device 改写。)
- **VLESS Reality + Hysteria2** — 一条 TCP 路 + 一条 UDP 路。Reality 把入站
  伪装在真实域名 (cloudflare / apple / microsoft,安装时随机挑) 的 TLS 指纹后面。
  Hy2 在只剩 UDP 没被掐时顶上。
- **每设备 5 种订阅 URL 格式**,服务器即时生成:
  - URI list (sing-box / Shadowrocket "Type: Subscribe" / Hiddify)
  - `clash.yaml` (Stash / Clash for iOS / Clash Verge)
  - `merlin.yaml` (AsusWRT-Merlin Clash + `tun:` 块)
  - `shadowrocket.conf` (Surge `.conf` 格式)
  - `sub.txt` (`.txt` 扩展名别名)
- **真实流量记账** — worker 每 10 秒拉一次 sing-box 的 Clash API,按设备×小时桶
  bytes 写 SQLite。SPA 渲染 7 天每设备图表 + 24h 热力图 + App 类型聚合
  (Video / Social / AI / CDN / 游戏 / Music / ...)。支持 CSV 导出。
- **默认用户名密码登录** — 后台地址在 `/login/{12 位随机后缀}`,`/login` 本身返
  404,URL-path token 单独不能登 (要开启 `features.url_token_bypass` 才作为 API
  fallback)。账号密码 + 登录路径都能在「安全」页一键轮换。
- **后台一键开 HTTPS** — 在「HTTPS · 域名」页贴域名 → 点启用。后台自动:校验 DNS
  → apt 装 Caddy → 申 Let's Encrypt → 写反代 Caddyfile → reload,30 秒搞定。
  不用 SSH。
- **手动 IP 封禁** — 包装 fail2ban(`backend=systemd`,绕开 Debian 13 没
  `/var/log/auth.log` 的坑)。从面板或 `POST /action/{block,unblock}` 操作。
- **可选 Telegram bot** — 手机上发 `/status`、`/devices`、`/traffic`、
  `/pause`、`/resume`、`/bans` 等命令。
- **可选 WebAuthn passkey** — Touch ID / Face ID / 硬件 key 作为密码的补充
  (需要 HTTPS)。
- **三种部署方式** — bash 一键、Docker Compose、或者**让 Claude Code 替你装** (自带 skill)。

## 🚀 快速上手

挑一种适合你环境的。

### 方式 A — `install.sh` (Debian / Ubuntu VPS,推荐)

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox
bash deploy/install.sh --lang zh        # 或 --lang en
```

脚本幂等,重跑安全。会自动检测公网 IP → 生成 Reality 密钥对 + Hy2 证书 + 16 位
随机 admin 密码 → 配 fail2ban + 4 个 systemd unit → **自动建第一台设备**
(默认名 `phone-1`,可用 `PROXYBOX_FIRST_DEVICE=tablet-1` 覆盖) → 打印自包含的
凭据 + 订阅 URL:

```
🛡 后台登录凭据
    登录地址  http://<你的-vps>:8080/login/<12 位随机串>
    用户名    admin
    密  码    <16 位字母数字,终端里加粗红色>

📲 订阅 URL (phone-1)
    [推荐]   http://<你的-vps>:8080/api/sub/<sub-token>
    [Clash]  http://<你的-vps>:8080/api/sub/<sub-token>/clash.yaml
    [路由器] http://<你的-vps>:8080/api/sub/<sub-token>/merlin.yaml
    [备用]   http://<你的-vps>:8080/api/sub/<sub-token>/shadowrocket.conf
    [.txt]   http://<你的-vps>:8080/api/sub/<sub-token>/sub.txt
```

**关闭终端之前**把登录 URL + 用户名密码抄进密码管理器。完整密码也存在
`/etc/proxybox/config.yaml` 的 `admin.password` 字段里。

### 方式 B — Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d                              # 核心栈
docker compose --profile bot up -d                # 也启动 TG bot
docker compose exec proxybox-admin \
    sh -c 'grep -E "username|password|login_path" /etc/proxybox/config.yaml'
```

`bootstrap` 容器首次启动时生成配置;volume 在 `docker compose down/up` 之间
保留状态。**这条路径没有 fail2ban** —— 生产环境请配 Caddy + 主机防火墙。每
个版本的多架构镜像 (linux/amd64 + linux/arm64) 都发到 `ghcr.io/carlos0xx/proxybox:latest`。

### 方式 C — Claude Code 替你装 (`proxybox-deploy` skill)

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

然后在 Claude Code 对话里:

> 帮我在 1.2.3.4 这台 VPS 上部署 proxybox,SSH key 是 ~/.ssh/id_ed25519

Claude 会走 pre-flight 检查 → `git clone` → `install.sh` → 把凭据直接发给你
(自包含 handoff,和方式 A 一样)。

## 📐 架构

```
┌─ 客户端 (iOS / Android / macOS / Win) ────────┐
│  sing-box · Shadowrocket · Hiddify · Stash    │
└──────────────────────┬────────────────────────┘
                       │ VLESS Reality (TCP 11001-11050,每设备一对)
                       │ Hysteria2 (UDP 21001-21050,每设备一对)
                       ▼
┌──────────────────────────────────────────────┐
│                  VPS                         │
│  ┌────────────────────────────────────────┐  │
│  │  sing-box (systemd)                    │◄─┼─ 每设备独立 Reality + Hy2 入站
│  └──────────────────┬─────────────────────┘  │
│                     │ Clash API (127.0.0.1:9090)
│  ┌──────────────────▼─────────────────────┐  │
│  │  proxybox-traffic-worker               │  │   bytes → traffic_log
│  │   每 10s 轮询 /connections + /traffic   │  │   hosts → host_log (v0.1.9+)
│  │   写 SQLite                             │  │
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  proxybox-admin  (uvicorn / FastAPI)   │◄─┼─ admin API + SPA on :8080
│  │  · 40+ admin endpoints                 │  │   ────────────
│  │  · /login/{secret} 用户名+密码登录       │  │   登录页 (URL-path token
│  │  · /admin/{token}/... 要 cookie         │  │     单独登录是 opt-in)
│  │  · /api/sub/{sub_token}[/format]       │  │   公开订阅地址
│  │  · /api/https/enable {domain}          │  │   一键 HTTPS
│  │  · /api/admin/account, /login-path     │  │   凭据轮换
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  caddy (可选, v0.1.10+)                 │  │   HTTPS 反代,Let's Encrypt
│  │   reverse_proxy 127.0.0.1:8080         │  │   自动续期
│  └────────────────────────────────────────┘  │
│                                              │
│  ┌────────────────────────────────────────┐  │
│  │  proxybox-bot      (opt-in, Telegram)  │  │
│  │  fail2ban          (manual IP jail)    │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

## 🧩 配置

所有配置在 `/etc/proxybox/config.yaml` (权限 0600,root 拥有)。完整字段含
inline 注释见 [`config.example.yaml`](./config.example.yaml)。核心字段:

| 字段 | 作用 |
| --- | --- |
| `admin.username` / `admin.password` | 浏览器登录凭据。install.sh 自动生成 16 位随机密码。 |
| `admin.login_path` | `/login` 后的 12 位随机后缀。留空 = legacy `/login` (仍可用)。 |
| `admin.token` | URL-path admin token (开启 `features.url_token_bypass` 时也是 API key fallback)。 |
| `server.public_host` | 烤进订阅 URI 的公网 IP / 域名。install.sh 自动填,`enable-https.sh` 改成你的域名。 |
| `ports.vless_range` / `hy2_range` | 每设备端口池 (默认 11001-11050 TCP / 21001-21050 UDP)。 |
| `clash.api_url` | sing-box Clash API 地址 (默认 `127.0.0.1:9090`)。 |
| `worker.poll_interval` / `retention_days` | 流量记账周期 + 保留天数。 |
| `features.passkey` / `features.bot` | 可选的 WebAuthn / Telegram bot 开关。 |
| `features.url_token_bypass` | true 时 URL-path token 单独就能登。**默认 false** — 强制走登录表单。 |
| `services.monitored` | `GET /api/status` 检查哪些 systemd unit。 |

## 🔐 安全模型

- **没有 SaaS 依赖。** 一切跑在用户自己的 VPS,不回拨、没有共享控制面。
- **默认用户名 + 密码登录**,session cookie 由 `/login/{随机后缀}` 签发。
  `/login` 本身 404 — 扫常见路径的 bot 连表单存在都确认不了。
- **每设备独立凭据。** 某台设备 UUID / Hy2 密码泄漏不影响别的设备。
  revoke + regen-subs 干净切断被攻陷的设备。
- **常量时间凭据比较** (`secrets.compare_digest`),所有凭据检查都用。
- **配置原子写** — 改 config 用 tmp + rename,进程中途崩了也不会留半截
  `config.yaml`。
- **默认 HTTP。** 生产环境用 Caddy + Let's Encrypt 包一层。HTTPS 面板一键
  做这件事;`enable-https.sh` CLI 是同一份代码给脚本化安装用。
- **所有 admin 接口同时校验 session cookie + 匹配的 URL-path token。**
  defense-in-depth — 偷到 cookie 也没法 replay 到不同主机的实例上。

## 🛣️ 进度

| 版本 | 重点 |
| --- | --- |
| v0.1.0 | 首版:install.sh、Docker、Claude skill、34 个 admin endpoint、5 个 GHA workflow |
| v0.1.1 → v0.1.5 | SPA 适配 v0.1.x server (BWG-port 迁移)、多格式订阅 URL、真实 `/api/connections` 代理 |
| v0.1.6 | 用户名/密码登录 + URL token 单独登录默认关闭 |
| v0.1.7 → v0.1.8 | 历史页加固、HTTP 下复制工作、订阅链接排版变宽松 |
| v0.1.9 | 域名分类 (默认开)、`enable-https.sh` CLI |
| v0.1.10 | **管理后台一键开 HTTPS** |
| v0.1.11 | 后台改用户名 / 密码 / 轮换登录路径 |
| v0.1.12 | 复制按钮引号冲突 bug 修复,clipboard fallback 加固 |
| v0.2 (规划) | SPA 英文版 · passkey 浏览器 E2E · demo 录屏 |

`scripts/release-audit.sh` 在每个 tag 都跑 7 道闸门:工作树干净、PII 黑名单
扫已跟踪文件、gitleaks 扫 git 历史、commit 元数据身份核对、commit 消息体
黑名单扫描、版本一致性、CHANGELOG 存在。

## 📖 更多文档

- [`docs/guide.md`](./docs/guide.md) — 安装 + 日常使用 walkthrough。
- [`docs/architecture.md`](./docs/architecture.md) — 详细架构。
- [`docs/api/`](./docs/api/) — 按 router 拆的接口参考。
- [`docs/deploy/`](./docs/deploy/) — 三种部署方式详解。
- [`CHANGELOG.md`](./CHANGELOG.md) — 每个版本的变更 (Keep-a-Changelog)。

## 📜 协议

MIT — 见 [`LICENSE`](./LICENSE)。
