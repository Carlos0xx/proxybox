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
  <a href="./docs/guide.md">使用指南</a> ·
  <a href="./docs/architecture.md">架构</a>
</p>

---

## 为什么

- **按设备隔离** —— revoke 一台,不影响其他。
- **真实流量记账** —— 按设备×小时,按域名分类。
- **自托管** —— 不是 SaaS,不回拨。

---

## 安装

### 方式 A · `install.sh` *(推荐)*

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox && bash deploy/install.sh --lang zh
```

### 方式 B · Docker Compose

```bash
git clone https://github.com/carlos0xx/proxybox && cd proxybox
docker compose up -d
```

### 方式 C · Claude Code skill

```bash
mkdir -p ~/.claude/skills/proxybox-deploy
cp -r deploy/claude-skill/* ~/.claude/skills/proxybox-deploy/
# 然后在 Claude Code 对话里: "帮我在 1.2.3.4 这台 VPS 上部署 proxybox"
```

> [!IMPORTANT]
> 安装器只会打印一次登录地址 + 密码。关闭终端前抄进密码管理器。

---

## 文档

| | |
| --- | --- |
| [使用指南](./docs/guide.md) | 安装 + 日常使用 |
| [架构](./docs/architecture.md) | 5 个进程、一个 SQLite、一份 config |
| [API](./docs/api/) | 按 router 拆的接口参考 |
| [部署](./docs/deploy/) | 3 种安装方式详解 |

---

## 协议

MIT —— 见 [`LICENSE`](./LICENSE)。
