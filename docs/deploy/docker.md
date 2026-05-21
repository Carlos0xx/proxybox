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
| 端口扫描 | 8080 可用就用 8080;被占用就选 18080/28080/...。VLESS/Hy2 也会选择一整段空闲端口。 |
| 写 `.env` | 把选中的端口、public host、fresh 标记写进项目目录 `.env`。 |
| 启动 stack | `docker compose up -d --build`,使用 bridge network + 显式 published ports。 |
| 首台设备 | 如果设备列表为空,自动创建 5 个小写字母的随机设备名。`PROXYBOX_FIRST_DEVICE=` 可跳过。 |

如果 `.env` 已存在,脚本默认复用它,避免升级时悄悄换端口。需要清理旧 volume 并重新扫描端口:

```bash
PROXYBOX_FRESH=1 PROXYBOX_REWRITE_ENV=1 bash deploy/docker-install.sh
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
| 日志 | 面板提示使用 `docker compose logs --tail=N <service>`。 |

## 无痕重装

```bash
cd /opt/proxybox
docker compose down
PROXYBOX_FRESH=1 PROXYBOX_REWRITE_ENV=1 bash deploy/docker-install.sh
```

这会清理 ProxyBox Docker volumes 内的配置、流量库、订阅缓存和 sing-box 密钥,再重新 bootstrap。它不会删除项目目录、不会改宿主 systemd/fail2ban/Caddy/SSH 配置。

## HTTPS 与 fail2ban

Docker 默认路径不在宿主安装 Caddy 或 fail2ban。生产环境建议在宿主已有反向代理或 Cloudflare Tunnel 后面暴露 Admin UI,或者继续使用高级裸机安装路径 [`install.sh`](./install-sh.md)。

## 相关文件

- [`docker-compose.yml`](../../docker-compose.yml)
- [`deploy/docker-install.sh`](../../deploy/docker-install.sh)
- [`deploy/docker/singbox-entrypoint.sh`](../../deploy/docker/singbox-entrypoint.sh)
