# Docker 默认安装

> 推荐路径。Docker stack 使用 bridge 网络隔离,自动挑选空闲宿主端口,不写宿主机 Python、systemd、fail2ban、Caddy 或 SSH known_hosts。

## 快速开始

```bash
ssh root@<your-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox
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

每次运行安装器默认都会新建一套 Compose project 和 Docker volumes。它不会 `down`、删除或改写旧 ProxyBox project；旧项目如果还在运行,只会被端口扫描识别为“端口已占用”,新项目会自动选择其他端口。需要原地升级当前 `.env` 指向的项目时,显式使用:

```bash
git pull
PROXYBOX_UPGRADE=1 bash deploy/docker-install.sh
```

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
PROXYBOX_FRESH=0
```

## 服务与隔离

| Service | Role | Host impact |
| --- | --- | --- |
| `bootstrap` | 首次生成 `/etc/proxybox/config.yaml` 和 `/etc/sing-box/config.json`。 | 写 Docker named volumes。 |
| `sing-box` | 代理核心。 | 只发布 `.env` 里的 TCP/UDP 端口。 |
| `proxybox-admin` | FastAPI + 静态面板。 | 只发布 Admin UI 端口。 |
| `proxybox-traffic-worker` | 轮询 Clash API 记账。 | 不发布端口。 |
| `proxybox-bot` | 可选 Telegram bot。 | 只读项目目录 `bot.env`,不读宿主 `/etc/proxybox/bot.env`。 |

Docker 模式下,后台不会调用宿主 `systemctl` 来控制服务:

| 操作 | Docker 行为 |
| --- | --- |
| sing-box reload | Admin 写共享卷里的 reload flag,`sing-box` 容器内 wrapper 给进程发 HUP。 |
| traffic worker restart | Admin 写共享卷里的 restart flag,worker 容器内 wrapper 重启子进程。 |
| 服务状态 | Admin 自检自身、探测 sing-box Clash API、读取 worker heartbeat。 |
| 日志 | 面板直接读取容器共享卷里的服务日志。 |

## 新装与升级边界

默认重新运行 `bash deploy/docker-install.sh` 是“新装”:生成新的 Compose project、新的 volume、新的端口选择、新的登录地址和订阅地址,不删除旧项目。

如果只是升级当前项目的代码和镜像,使用 `PROXYBOX_UPGRADE=1 bash deploy/docker-install.sh`。升级模式会复用当前 `.env` 指向的 Compose project。

## HTTPS 与 fail2ban

Docker 默认路径不在宿主安装 Caddy 或 fail2ban。生产环境建议在宿主已有反向代理或 Cloudflare Tunnel 后面暴露 Admin UI,或者继续使用高级裸机安装路径 [`install.sh`](./install-sh.md)。

## 相关文件

- [`docker-compose.yml`](../../docker-compose.yml)
- [`deploy/docker-install.sh`](../../deploy/docker-install.sh)
- [`deploy/docker/singbox-entrypoint.sh`](../../deploy/docker/singbox-entrypoint.sh)
