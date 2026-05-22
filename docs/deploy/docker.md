# Docker 默认安装

> 推荐路径。Docker stack 使用 bridge 网络隔离,自动挑选空闲宿主端口,不写宿主机 Python、fail2ban 或 SSH known_hosts。安装器只额外写本次安装专属的 systemd Docker guard 和 HTTPS helper；Caddy 只会在用户从后台 HTTPS 页面明确启用时由 helper 在宿主机配置。

> [!IMPORTANT]
> 安装红线: 不要删除、修改、覆盖或复用用户 VPS 上本次安装以外的任何文件和服务。即便宿主机已经存在 `/opt/proxybox` 或同名目录,也必须保留不动,改用新的 `proxybox-<时间戳>-<后缀>` 目录克隆和安装;安装器和部署代理只能碰本次安装新建的资源。

## 快速开始

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$$"
git clone https://github.com/carlos0xx/proxybox "$INSTALL_DIR"
cd "$INSTALL_DIR"
bash deploy/docker-install.sh
```

安装脚本会:

| 步骤 | 行为 |
| --- | --- |
| Docker 检查 | 检查 Docker CLI、Compose、daemon;缺失时 apt 安装 Docker/Compose,daemon 未运行时自动启动。 |
| 端口扫描 | 确保 `ss`/`iproute2` 可用后精确检测监听端口。8080 可用就用 8080;被占用就选 18080/28080/...。VLESS/Hy2 也会选择一整段空闲端口。 |
| 写 `.env` | 把新的 Compose project name、专属镜像 tag、选中的端口和 public host 写进项目目录 `.env`。 |
| 启动 stack | `docker compose up -d --build`,使用 bridge network + 显式 published ports。 |
| 首台设备 | 如果设备列表为空,自动创建 5 个小写字母的随机设备名。`PROXYBOX_FIRST_DEVICE=` 可跳过。 |
| Docker guard | 写入 `proxybox-docker-guard-<project>.timer`,每分钟只在本安装目录执行 `docker compose up -d`,并在 Docker daemon 停止时启动 `docker.service`。 |
| HTTPS helper | 写入 `proxybox-docker-https-<project>.path`,只监听本安装目录 `.proxybox-guard/https-request`,用于后台 HTTPS 页面的一键启用。 |

每次运行安装器默认都会新建一套 Compose project 和 Docker volumes。它不会 `down`、删除或改写旧 ProxyBox project；旧项目如果还在运行,只会被端口扫描识别为“端口已占用”,新项目会自动选择其他端口。

升级不是安装。只有你明确选中某个已有 ProxyBox 安装目录时,才允许原地升级；普通安装流程永远新建目录和新的隔离 Docker project。

## 端口策略

| 用途 | 默认 | 冲突时 |
| --- | --- | --- |
| Admin UI | TCP `8080` | 自动尝试 `18080`, `28080`, `38080`, `48080`,再随机挑选高位端口。 |
| VLESS 模板 + 设备段 | TCP `11000`, `11001-11050` | 自动尝试 `12000/12001-12050` 起的整段空闲端口。 |
| Hy2 模板 + 设备段 | UDP `21000`, `21001-21050` | 自动尝试 `22000/22001-22050` 起的整段空闲端口。 |
| Clash API | 容器内 `9090` | 不发布到宿主机,只在 Docker 网络内给 worker/admin 使用。 |

`.env` 示例:

```dotenv
COMPOSE_PROJECT_NAME=proxybox-1770000000-1a2b3c4d
PROXYBOX_IMAGE=proxybox:proxybox-1770000000-1a2b3c4d
PROXYBOX_SINGBOX_IMAGE=proxybox-sing-box:proxybox-1770000000-1a2b3c4d
PROXYBOX_PUBLIC_HOST=203.0.113.10
PROXYBOX_ADMIN_BIND=0.0.0.0
PROXYBOX_ADMIN_PORT=18080
PROXYBOX_CLASH_PORT=9090
PROXYBOX_VLESS_TEMPLATE_PORT=12000
PROXYBOX_VLESS_START=12001
PROXYBOX_VLESS_END=12050
PROXYBOX_HY2_TEMPLATE_PORT=22000
PROXYBOX_HY2_START=22001
PROXYBOX_HY2_END=22050
PROXYBOX_BOT_INTERNAL_SECRET=<64-hex-chars>
PROXYBOX_FRESH=0
```

## 服务与隔离

| Service | Role | Host impact |
| --- | --- | --- |
| `bootstrap` | 首次生成 `/etc/proxybox/config.yaml` 和 `/etc/sing-box/config.json`。 | 写 Docker named volumes。 |
| `sing-box` | 代理核心。 | 只发布 `.env` 里的 TCP/UDP 端口。 |
| `proxybox-admin` | FastAPI + 静态面板。 | 只发布 Admin UI 端口。 |
| `proxybox-traffic-worker` | 轮询 Clash API 记账。 | 不发布端口。 |
| `proxybox-bot` | 可选 Telegram bot。 | 只读项目目录 `bot.env`,不读宿主 `/etc/proxybox/bot.env`;通过 `.env` 里的安装级 internal secret 调用 admin API。 |

服务页会显示容器内 `看门狗` 和宿主机 `Docker Guard` 两项。`看门狗`
负责容器内服务/端口自恢复；`Docker Guard` 是宿主机 timer 的状态回传,
通过本安装目录 `.proxybox-guard/status` 回传进 admin 容器。这个目录也用于
HTTPS helper 的 request/response 文件,只属于本次安装。

Docker 模式下,后台不会调用宿主 `systemctl` 来控制服务:

| 操作 | Docker 行为 |
| --- | --- |
| sing-box reload | Admin 写共享卷里的 reload flag,`sing-box` 容器内 wrapper 给进程发 HUP。 |
| traffic worker restart | Admin 写共享卷里的 restart flag,worker 容器内 wrapper 重启子进程。 |
| 服务状态 | Admin 自检自身、探测 sing-box Clash API、读取 worker heartbeat。 |
| 日志 | 面板直接读取容器共享卷里的服务日志。 |

## 新装与升级边界

默认重新运行 `bash deploy/docker-install.sh` 是“新装”:生成新的 Compose project、新的 volume、新的端口选择、新的登录地址和订阅地址,不删除旧项目。

如果只是升级当前项目的代码和镜像,必须先进入你明确要升级的那个安装目录,再使用升级模式。升级模式会复用当前目录 `.env` 指向的 Compose project；新安装流程不能使用这个模式。

## HTTPS 与 fail2ban

Docker 默认路径不在容器内安装 Caddy 或 fail2ban。HTTPS 可以在后台 **HTTPS · 域名** 页面一键启用:

1. 先把域名 A 记录指向 VPS 公网 IP。
2. 后台点击启用 HTTPS。
3. admin 容器写 `.proxybox-guard/https-request`。
4. 宿主机 `proxybox-docker-https-<project>.path` 触发 `deploy/docker-https-apply.sh`。
5. helper 验证 DNS,安装/启动 Caddy,最佳努力放行 ufw/firewalld 的 80/443,写 ProxyBox 管理的 `/etc/caddy/Caddyfile`,反代到 `.env` 里的 Admin UI 端口。
6. helper 写 `.proxybox-guard/https-response`,admin 容器读取成功结果后更新 `server.public_host`、`passkey.rp_id`、`passkey.origin`。

安全边界: helper 只响应本安装目录的 request 文件,并且只信任本安装 `.env` 里的 Admin UI 端口,不接受容器请求覆盖端口。如果宿主机已有非 ProxyBox 管理的 `/etc/caddy/Caddyfile`,helper 会返回 `caddyfile_conflict`,不会覆盖用户原有 Caddy 配置。

## Telegram bot

Docker bot 是可选 profile:

```bash
cat > bot.env <<EOF
BOT_TOKEN=...
TG_ALLOWED_USERS=<your-telegram-user-id>
ADMIN_TOKEN=$(docker compose exec -T proxybox-admin sh -c "grep '^  token:' /etc/proxybox/config.yaml | cut -d'\"' -f2")
EOF
chmod 600 bot.env
docker compose --profile bot up -d proxybox-bot
```

Compose 会自动给 bot 设置 `PROXYBOX_API_URL=http://proxybox-admin:8080` 和 `PROXYBOX_BOT_INTERNAL_SECRET`,所以 bot 不需要暴露额外宿主端口。

## 相关文件

- [`docker-compose.yml`](../../docker-compose.yml)
- [`deploy/docker-install.sh`](../../deploy/docker-install.sh)
- [`deploy/docker/singbox-entrypoint.sh`](../../deploy/docker/singbox-entrypoint.sh)
