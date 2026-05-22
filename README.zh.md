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
| 📲 &nbsp; **订阅格式** | Shadowrocket 分流 · `clash.yaml` · `merlin.yaml` · 默认 URI list,按设备服务端即时生成。 |
| 📊 &nbsp; **真实流量记账** | worker 每 10 秒拉一次 sing-box Clash API。SQLite 按设备×小时桶 bytes,按域名分类 (Video / Social / AI / CDN …)。 |
| 🔑 &nbsp; **用户名密码登录** | 表单在 `/login/{12 位随机后缀}`,`/login` 单独返 404。改密码 + 轮换登录路径都在面板里 —— 不用 SSH。 |
| 🔒 &nbsp; **HTTPS 方案** | Docker 路径可在面板里通过宿主机 helper 启用 Caddy + Let's Encrypt;裸机模式仍可直接启用。 |
| 🐳 &nbsp; **默认 Docker 安装** | bridge 网络隔离,自动避开宿主机已占用端口,只写本次安装专属 Docker guard 和 HTTPS helper。 |
| 🤖 &nbsp; **可选 Telegram bot** | 手机上发 `/status` · `/devices` · `/traffic` · `/pause` · `/resume` · `/bans`。 |

---

## 安装

### 方式 A · 交互式安装 *(默认推荐 Docker)*

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR" && bash deploy/install.sh
```

无参数运行 `deploy/install.sh` 会用中文提示选择 **Docker 安装** 或 **宿主机安装**,并强制用户输入 `1` 或 `2`。推荐选 Docker:容器隔离、自动避开已占用端口,只写本次安装专属 Docker guard 用于开机/daemon 中断自恢复,并写一个 HTTPS helper 供后台按需启用宿主机 Caddy;不写宿主机 Python/fail2ban。如果 VPS 里已经有其他服务、网站、面板或生产系统,强烈推荐 Docker。宿主机安装会直接安装 Python、sing-box、systemd unit、fail2ban,仅建议用于干净、专用、不跑其他生产服务的 VPS。

直接指定方式:

```bash
bash deploy/install.sh --docker
bash deploy/install.sh --native --fresh --lang zh
```

Docker 安装会在缺失时自动安装/启动 Docker、Compose 和端口检测工具,然后扫描宿主机端口:默认端口没被占用就用默认值,被占用就自动挑一组空闲端口并打印/写入 `.env`。每次运行都会生成新的 Compose project name 和新的 Docker volumes,所以管理路径、密码、密钥、订阅地址都会重新生成,同时不会删除任何旧 ProxyBox 项目。

> [!IMPORTANT]
> 安装红线: 不要删除、修改、覆盖或复用用户 VPS 上本次安装以外的任何文件和服务。即便宿主机已经存在 `/opt/proxybox` 或同名目录,也必须保留不动,改用新的 `proxybox-<时间戳>-<后缀>` 目录克隆和安装;安装器和部署代理只能碰本次安装新建的资源。

升级不是安装。只有你明确选中某个已有 ProxyBox 安装目录时,才允许原地升级;普通安装流程永远新建目录和新的隔离 Docker project。

### 方式 B · Claude Code / Codex

让 AI 代理通过 SSH 替你装。Claude Code 用户先把 skill 复制过去一次:

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
```

然后在对话里:*"帮我在 1.2.3.4 这台 VPS 上部署 proxybox,SSH key 是 ~/.ssh/id_ed25519"*。代理必须先让你选择 Docker 或宿主机安装;服务器已有 Docker、README 推荐 Docker、端口更适合 Docker 都不能代替你的选择。确认后再走自动删除的临时 SSH `known_hosts` → 最小 VPS 检查 → 克隆到新的安装目录 → 运行 `deploy/install.sh --docker` 或 `deploy/install.sh --native --fresh` → 验证服务 → 把登录地址 + 凭据发给你。

Codex 或其他代理:直接把 [`deploy/claude-skill/SKILL.md`](./deploy/claude-skill/SKILL.md) 喂给它 —— 指令是通用的,不绑 Claude Code。

### 方式 C · 宿主机安装 *(高级模式)*

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR" && bash deploy/install.sh --native --fresh --lang zh
```

宿主机 `--fresh` 现在只表示“全新 native 安装”:只有没有旧 ProxyBox/sing-box native 状态时才会生成新的 Reality 密钥对、Hy2 证书、16 位随机 admin 密码和 5 位小写随机设备名。如果发现旧状态,安装器会拒绝继续,不会自动删除。确实要清理旧 ProxyBox native 状态时,必须单独使用高级危险开关 `--purge-existing-proxybox`,并输入 `DELETE PROXYBOX` 确认。

> [!IMPORTANT]
> 安装器**只打印一次**登录地址 + 密码。关闭终端前抄进密码管理器。Docker 找回:`cd <proxybox-安装目录> && docker compose exec proxybox-admin sh -c 'cat /etc/proxybox/admin.password; grep -E "username|login_path" /etc/proxybox/config.yaml'`。

---

## 代码结构

```text
.
├── app/        管理后端 —— FastAPI 服务、SQLite、写 sing-box config
├── bot/        手机控制面 —— Web UI 之外的 Telegram 备选入口
├── static/     Web 前端 —— 后端挂载的中文单文件 SPA
├── deploy/     部署与运维 —— 安装器、预检、HTTPS、AI skill
├── docs/       用户文档 —— 指南 · 架构 · API · 部署
├── scripts/    发布闸门 —— PII 黑名单 + 审计检查
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
