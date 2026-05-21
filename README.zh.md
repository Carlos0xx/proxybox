<div align="right">

[English](./README.md) · **中文**

</div>

<h1 align="center">ProxyBox</h1>

<p align="center">
  自托管、按设备隔离的代理后台。<br>
  每台设备独立一对 VLESS Reality + Hysteria2 · 字节级流量记账 · Docker 默认安装 · MIT。
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
| 🔒 &nbsp; **HTTPS 方案** | Docker 路径建议接宿主反代 / Tunnel;裸机模式仍可在面板里启用 Caddy + Let's Encrypt。 |
| 🐳 &nbsp; **默认 Docker 安装** | bridge 网络隔离,自动避开宿主机已占用端口,不写宿主 Python/systemd/fail2ban。 |
| 🤖 &nbsp; **可选 Telegram bot** | 手机上发 `/status` · `/devices` · `/traffic` · `/pause` · `/resume` · `/bans`。 |

---

## 安装

### 方式 A · Docker 默认安装 *(推荐)*

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox && bash deploy/docker-install.sh
```

`deploy/docker-install.sh` 会在缺失时自动安装/启动 Docker、Compose 和端口检测工具,然后扫描宿主机端口:默认端口没被占用就用默认值,被占用就自动挑一组空闲端口并打印/写入 `.env`。每次运行安装器都会生成新的 Compose project name 和新的 Docker volumes,所以管理路径、密码、密钥、订阅地址都会重新生成,同时不会删除任何旧 ProxyBox 项目。Docker stack 使用 bridge 网络,只发布被选中的端口,不会安装或改写宿主机 Python、ProxyBox systemd unit、fail2ban、Caddy、SSH known_hosts 或无关服务。设备列表为空时,安装器会自动创建一个 5 位小写随机设备名。

如果是要原地升级当前项目,而不是新建一套:

```bash
cd /opt/proxybox
git pull
PROXYBOX_UPGRADE=1 bash deploy/docker-install.sh
```

### 方式 B · Claude Code / Codex

让 AI 代理通过 SSH 替你装。Claude Code 用户先把 skill 复制过去一次:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

然后在对话里:*"帮我在 1.2.3.4 这台 VPS 上部署 proxybox,SSH key 是 ~/.ssh/id_ed25519"*。代理走自动删除的临时 SSH `known_hosts` → 最小 VPS 检查 → `git clone` / 更新 → Docker 端口预检 → `deploy/docker-install.sh` → 验证服务 → 把登录地址 + 凭据发给你。

Codex 或其他代理:直接把 [`deploy/claude-skill/SKILL.md`](./deploy/claude-skill/SKILL.md) 喂给它 —— 指令是通用的,不绑 Claude Code。

### 方式 C · `install.sh` *(裸机高级模式)*

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox && bash deploy/install.sh --fresh --lang zh
```

fresh 模式会先清理 ProxyBox 自己管理的旧配置、旧数据、旧订阅和旧服务文件,再生成新的 Reality 密钥对、Hy2 证书、16 位随机 admin 密码和 5 位小写随机设备名。只有明确要保留旧 ProxyBox 安装时才去掉 `--fresh`。

> [!IMPORTANT]
> 安装器**只打印一次**登录地址 + 密码。关闭终端前抄进密码管理器。Docker 找回:`cd /opt/proxybox && docker compose exec proxybox-admin sh -c 'cat /etc/proxybox/admin.password; grep -E "username|login_path" /etc/proxybox/config.yaml'`。

---

## 代码结构

```text
.
├── app/        管理后端 —— FastAPI 服务、SQLite、写 sing-box config
├── bot/        手机控制面 —— Web UI 之外的 Telegram 备选入口
├── static/     Web 前端 —— 后端挂载的中文单文件 SPA
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
