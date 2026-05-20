<div align="right">

[English](./README.md) · **中文**

</div>

<h1 align="center">ProxyBox</h1>

<p align="center">
  自托管、按设备隔离的代理管理面板。<br>
  VPS 上每台设备独立一对 VLESS Reality + Hysteria2 入站,字节级流量记账、一键 HTTPS、<br>
  可选 Telegram bot 控制、可选 WebAuthn passkey 登录 —— MIT 协议。
</p>

<p align="center">
  <a href="#-快速上手">快速上手</a> ·
  <a href="./docs/guide.md">使用指南</a> ·
  <a href="./docs/architecture.md">架构</a> ·
  <a href="./docs/api/">API</a> ·
  <a href="./CHANGELOG.md">更新日志</a>
</p>

---

## ✨ 特性

| | |
| :--- | :--- |
| 🔐 &nbsp; **按设备独立入站** | 每台设备一对独立 UUID + TCP/UDP 端口。某台凭证泄漏只 revoke 那一台,不影响其他。 |
| 🌐 &nbsp; **VLESS Reality + Hysteria2** | TCP 路由伪装在真实域名的 TLS 指纹后面;TCP 被限速时 Hy2 UDP 顶上。 |
| 📲 &nbsp; **每设备 5 种订阅格式** | URI list · `clash.yaml` · `merlin.yaml` · `shadowrocket.conf` · `sub.txt`,服务端即时生成。 |
| 📊 &nbsp; **真实流量记账** | worker 每 10 秒拉一次 sing-box Clash API。SQLite 按设备×小时桶 bytes + 按域名分类 (Video / Social / AI / CDN / 游戏 / ...)。 |
| 🔑 &nbsp; **用户名密码登录** | 登录表单在 `/login/{12 位随机后缀}`,`/login` 本身返 404 防爆破扫描。URL-path token 单独登录是 opt-in。 |
| 🔒 &nbsp; **后台一键 HTTPS** | 输域名 → 点启用 → ~30 秒 Caddy + Let's Encrypt 全配好,不用 SSH。 |
| 🌏 &nbsp; **中英双语 UI** | 顶栏 `中 / EN` 切换,~80% 英文覆盖 + 中文 fallback。登录页也支持 `?lang=` 切换。 |
| 🤖 &nbsp; **可选 Telegram bot** | 手机上发 `/status` · `/devices` · `/traffic` · `/pause` · `/resume` · `/bans`。 |
| 🛡️ &nbsp; **可选 WebAuthn passkey** | Touch ID / Face ID / 硬件 key (需 HTTPS)。 |
| 🚀 &nbsp; **三种部署方式** | Bash 一键 · Docker Compose · Claude Code skill 替你装。 |

---

## 🚀 快速上手

### 方式 A — `install.sh` &nbsp;<sub>(推荐,Debian / Ubuntu VPS)</sub>

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox
bash deploy/install.sh --lang zh        # 或 --lang en
```

脚本幂等。自动检测公网 IP,生成 Reality 密钥对 + Hy2 证书 + 16 位随机 admin 密码,装 4 个 systemd unit,自动建第一台设备,打印自包含的凭据 + 订阅 URL:

```
🛡 后台登录凭据
   登录地址  http://<你的-vps>:8080/login/<12 位随机串>
   用户名    admin
   密  码    <16 位字母数字>

📲 订阅 URL (phone-1)
   [推荐]   http://<你的-vps>:8080/api/sub/<sub-token>
   [Clash]  http://<你的-vps>:8080/api/sub/<sub-token>/clash.yaml
   [路由器] http://<你的-vps>:8080/api/sub/<sub-token>/merlin.yaml
   [备用]   http://<你的-vps>:8080/api/sub/<sub-token>/shadowrocket.conf
   [.txt]   http://<你的-vps>:8080/api/sub/<sub-token>/sub.txt
```

> [!IMPORTANT]
> **关闭终端之前**把登录 URL + 用户名密码抄进密码管理器。
> 完整密码也存在 `/etc/proxybox/config.yaml` 的 `admin.password` / `admin.login_path` 字段。

### 方式 B — Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d                              # 核心栈
docker compose --profile bot up -d                # 也启动 TG bot
docker compose exec proxybox-admin \
    sh -c 'grep -E "username|password|login_path" /etc/proxybox/config.yaml'
```

`bootstrap` 容器首次启动时生成配置;volume 在 `down`/`up` 之间保留状态。每个版本的多架构镜像 (linux/amd64 + linux/arm64) 都发到 `ghcr.io/carlos0xx/proxybox:latest`。

> [!NOTE]
> 这个路径不带 fail2ban 和自动 HTTPS UI —— 生产环境请配 Caddy + 主机防火墙。

### 方式 C — Claude Code

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

然后在 Claude Code 对话里:

> 帮我在 1.2.3.4 这台 VPS 上部署 proxybox,SSH key 是 ~/.ssh/id_ed25519

Claude 会走 pre-flight 检查 → `git clone` → `install.sh` → 把凭据直接发给你。见 [`docs/deploy/claude-skill.md`](./docs/deploy/claude-skill.md)。

---

## 📐 架构

```text
┌─ 客户端 (iOS · Android · macOS · Windows) ────┐
│  sing-box · Shadowrocket · Hiddify · Stash    │
└───────────────────────┬───────────────────────┘
                        │ VLESS Reality (TCP 11001-11050,每设备一对)
                        │ Hysteria2     (UDP 21001-21050,每设备一对)
                        ▼
┌───────────────────────────────────────────────┐
│                    VPS                        │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  sing-box  (systemd)                    │◄─┼─ 每设备独立 Reality + Hy2 入站
│  └────────────────┬────────────────────────┘  │
│                   │ Clash API (127.0.0.1:9090)
│  ┌────────────────▼────────────────────────┐  │
│  │  proxybox-traffic-worker                │  │  bytes → traffic_log
│  │   每 10s 轮询 /connections + /traffic    │  │  hosts → host_log
│  │   写 SQLite                              │  │
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  proxybox-admin  (uvicorn / FastAPI)    │◄─┼─ admin API + SPA on :8080
│  │   · /login/{secret} 用户名+密码           │  │
│  │   · /admin/{token}/... 要 cookie         │  │
│  │   · /api/sub/{sub_token}[/format]        │  │  ← 公开订阅地址
│  │   · /api/https/enable {domain}           │  │  ← 一键 HTTPS
│  │   · /api/admin/account, /login-path      │  │  ← 凭据轮换
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  caddy  (可选,v0.1.10+)                 │  │  HTTPS 反代
│  │   reverse_proxy 127.0.0.1:8080          │  │  Let's Encrypt 自动续期
│  └─────────────────────────────────────────┘  │
│                                               │
│  ┌─────────────────────────────────────────┐  │
│  │  proxybox-bot   (opt-in, Telegram)      │  │
│  │  fail2ban       (manual IP jail)        │  │
│  └─────────────────────────────────────────┘  │
└───────────────────────────────────────────────┘
```

详细架构见 [`docs/architecture.md`](./docs/architecture.md)。

---

## 🧩 配置

所有配置在 `/etc/proxybox/config.yaml` (权限 0600,root 拥有)。完整字段含 inline 注释见 [`config.example.yaml`](./config.example.yaml)。

| 字段 | 作用 |
| --- | --- |
| `admin.username` / `admin.password` | 浏览器登录凭据。`install.sh` 自动生成 16 位随机密码。 |
| `admin.login_path` | `/login` 后的 12 位随机后缀。留空 = legacy `/login` (仍可用)。 |
| `admin.token` | URL-path admin token。开启 `features.url_token_bypass` 时也是 API key fallback。 |
| `server.public_host` | 烤进订阅 URI 的公网 IP / 域名。`install.sh` 自动填,`enable-https.sh` 改成你的域名。 |
| `ports.vless_range` / `hy2_range` | 每设备端口池 (默认 `11001-11050 TCP` / `21001-21050 UDP`)。 |
| `clash.api_url` | sing-box Clash API 地址 (默认 `127.0.0.1:9090`)。 |
| `worker.poll_interval` / `retention_days` | 流量记账周期 + 保留天数。 |
| `features.passkey` / `features.bot` | 可选的 WebAuthn / Telegram bot 开关。 |
| `features.url_token_bypass` | `true` 时 URL-path token 单独就能登。**默认 `false`** — 强制走登录表单。 |
| `services.monitored` | `GET /api/status` 检查哪些 systemd unit。 |

---

## 🔐 安全模型

- **没有 SaaS 依赖。** 一切跑在用户自己的 VPS,不回拨、没有共享控制面。
- **默认用户名 + 密码登录。** session cookie 由 `/login/{随机后缀}` 签发。`/login` 本身 404 — 扫常见路径的 bot 连表单存在都确认不了。
- **每设备独立凭据。** 某台设备 UUID / Hy2 密码泄漏不影响别的设备。revoke + regen-subs 干净切断被攻陷的设备。
- **常量时间凭据比较** (`secrets.compare_digest`),所有凭据检查都用。
- **配置原子写** — 改 `config.yaml` 用 `tmp + rename`,进程中途崩了也不会留半截配置。
- **默认 HTTP**,后台一键开 HTTPS 或 `deploy/enable-https.sh <域名>`。
- **Defense in depth** — 所有 admin 接口同时校验 session cookie + 匹配的 URL-path token。偷到 cookie 也没法 replay 到不同主机的实例上。

---

## 🛣️ 版本

| 版本 | 重点 |
| --- | --- |
| **v0.2.0** | SPA 双语 + 登录页双语,顶栏 `中 / EN` 一键切换 |
| v0.1.10 → v0.1.12 | 后台 UI 一键 HTTPS · 改账号密码 · 轮换登录路径 · 复制按钮修复 |
| v0.1.7 → v0.1.9 | 历史页加固 · 5 种订阅格式 · 域名分类默认开 |
| v0.1.6 | 用户名/密码登录取代 URL token 单独登录 |
| v0.1.1 → v0.1.5 | SPA 适配 v0.1.x server (BWG-port 迁移) · `/api/connections` 代理 |
| v0.1.0 | 首版 — install.sh / Docker / Claude skill · 5 GHA workflow · 7 道 release-audit 闸门 |

每版详情见 [`CHANGELOG.md`](./CHANGELOG.md)。`scripts/release-audit.sh` 在每个 tag 都跑 7 道闸门:工作树干净 · PII 黑名单 · gitleaks · 提交者身份 · commit 消息黑名单 · 版本一致性 · CHANGELOG 存在。

---

## 📖 文档

| | |
| --- | --- |
| [使用指南](./docs/guide.md) | 安装 + 日常使用 walkthrough |
| [架构](./docs/architecture.md) | 按服务展开的详细架构 |
| [API](./docs/api/) | 按 router 拆的接口参考 |
| [部署](./docs/deploy/) | 三种部署方式详解 |
| [更新日志](./CHANGELOG.md) | 每个版本的变更 (Keep-a-Changelog) |

---

## 📜 协议

MIT — 见 [`LICENSE`](./LICENSE)。
