<div align="right">

[English](./README.md) · **中文**

</div>

<h1 align="center">ProxyBox</h1>

<p align="center">
  自托管、按设备隔离的代理后台。<br>
  每台设备独立一对 VLESS Reality + Hysteria2 · 字节级流量记账 · 一键 HTTPS · MIT。
</p>

<p align="center">
  <a href="#安装"><strong>安装</strong></a> ·
  <a href="#代码结构">代码结构</a> ·
  <a href="./docs/guide.md">使用指南</a>
</p>

---

## 特性

| | |
| :--- | :--- |
| 🔐 &nbsp; **按设备独立入站** | 每台设备一对独立 UUID + TCP/UDP 端口。某台凭证泄漏只 revoke 那一台,不影响其他。 |
| 🌐 &nbsp; **VLESS Reality + Hysteria2** | TCP 路伪装在真实域名 TLS 指纹后面;TCP 被限速时 UDP 路顶上。 |
| 📲 &nbsp; **5 种订阅格式** | URI list · `clash.yaml` · `merlin.yaml` · `shadowrocket.conf` · `sub.txt`,按设备服务端即时生成。 |
| 📊 &nbsp; **真实流量记账** | worker 每 10 秒拉一次 sing-box Clash API。SQLite 按设备×小时桶 bytes,按域名分类 (Video / Social / AI / CDN …)。 |
| 🔑 &nbsp; **用户名密码登录** | 表单在 `/login/{12 位随机后缀}`,`/login` 单独返 404。改密码 + 轮换登录路径都在面板里 —— 不用 SSH。 |
| 🔒 &nbsp; **一键 HTTPS** | 输域名 → 点启用 → Caddy + Let's Encrypt 30 秒搞定。 |
| 🌏 &nbsp; **中英双语 UI** | 顶栏 `中 / EN` 一键切。登录页也支持 `?lang=` 切换。 |
| 🤖 &nbsp; **可选 Telegram bot** | 手机上发 `/status` · `/devices` · `/traffic` · `/pause` · `/resume` · `/bans`。 |

---

## 安装

### 方式 A · Claude Code / Codex *(推荐)*

让 AI 代理通过 SSH 替你装。Claude Code 用户先把 skill 复制过去一次:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

然后在对话里:*"帮我在 1.2.3.4 这台 VPS 上部署 proxybox,SSH key 是 ~/.ssh/id_ed25519"*。代理走最小 VPS 检查 → `git clone` / 更新 → 完整 pre-flight → `install.sh` → 验证服务 → 把登录地址 + 凭据发给你。

Codex 或其他代理:直接把 [`deploy/claude-skill/SKILL.md`](./deploy/claude-skill/SKILL.md) 喂给它 —— 指令是通用的,不绑 Claude Code。

### 方式 B · `install.sh` *(Debian / Ubuntu VPS)*

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox && bash deploy/install.sh --lang zh
```

幂等。自动生成 Reality 密钥对、Hy2 证书、16 位随机 admin 密码,自动建第一台设备,最后打印自包含的**登录地址 · 用户名 · 密码 · 5 个订阅 URL**。

### 方式 C · Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d
```

多架构镜像在 `ghcr.io/carlos0xx/proxybox:latest`。这个路径不带 fail2ban 和 HTTPS UI —— 生产环境请配 Caddy + 主机防火墙。

> [!IMPORTANT]
> 安装器**只打印一次**登录地址 + 密码。关闭终端前抄进密码管理器。SSH 找回:`cat /etc/proxybox/admin.password` (0400) 拿密码,其余在 `/etc/proxybox/config.yaml`。

---

## 代码结构

```text
.
├── app/        管理后端 —— FastAPI 服务、SQLite、写 sing-box config
├── bot/        手机控制面 —— Web UI 之外的 Telegram 备选入口
├── static/     Web 前端 —— 后端挂载的单文件双语 SPA
├── deploy/     部署与运维 —— 安装器、预检、HTTPS、AI skill
├── docs/       用户文档 —— 指南 · 架构 · API · 部署
├── scripts/    发布闸门 —— PII 黑名单 + 7 道审计
└── tests/      回归测试 —— 配置加载、订阅、traffic worker
```

按服务展开的详细架构见 [`docs/architecture.md`](./docs/architecture.md)。

---

## 文档

| | |
| --- | --- |
| [使用指南](./docs/guide.md) | 安装 + 日常使用 |
| [架构](./docs/architecture.md) | 按服务展开的详细架构 |
| [API](./docs/api/) | 按 router 拆的接口参考 |
| [部署](./docs/deploy/) | 3 种安装方式详解 |

---

## 协议

MIT —— 见 [`LICENSE`](./LICENSE)。
