<div align="right">

[English](./README.md) · **中文**

</div>

<h1 align="center">ProxyBox</h1>

<p align="center">
  自托管、按设备隔离的代理后台。<br>
  每台设备独立一对 VLESS Reality + Hysteria2 · 字节级流量记账 · 一键 HTTPS · MIT。
</p>

<p align="center">
  <a href="#快速上手"><strong>快速上手</strong></a> ·
  <a href="./docs/guide.md">使用指南</a> ·
  <a href="./docs/architecture.md">架构</a> ·
  <a href="./CHANGELOG.md">更新日志</a>
</p>

---

## 为什么用

- **单台 revoke,不影响其他。** 每台设备独立 UUID + 端口。
- **真实流量记账。** SQLite 按设备×小时桶 bytes,按目标域名分类 (Video / Social / AI / CDN …)。
- **不是 SaaS。** 全在你自己 VPS 上跑,不回拨、没有共享控制面。
- **HTTPS、语言、账号一键搞定。** 装好以后不用再 SSH。

---

## 快速上手

```bash
ssh root@<你的-vps>
apt-get update && apt-get install -y git curl ca-certificates
git clone https://github.com/carlos0xx/proxybox /opt/proxybox
cd /opt/proxybox && bash deploy/install.sh --lang zh
```

幂等。3 分钟左右。最后打印**登录地址 · 用户名 · 密码 · 5 个订阅 URL**。

> [!IMPORTANT]
> 关闭终端前把凭据抄到密码管理器。

其他方式: [Docker Compose](./docs/deploy/docker.md) · [Claude Code skill](./docs/deploy/claude-skill.md)。

---

## 文档

| | |
| --- | --- |
| [使用指南](./docs/guide.md) | 安装 + 日常使用 |
| [快速上手](./docs/getting-started.md) | 头 10 分钟,一步步走 |
| [架构](./docs/architecture.md) | 5 个进程、一个 SQLite、一份 config |
| [API](./docs/api/) | 按 router 拆的接口参考 |
| [部署](./docs/deploy/) | 3 种安装方式详解 |
| [更新日志](./CHANGELOG.md) | 每个版本的变更 |

---

## 协议

MIT —— 见 [`LICENSE`](./LICENSE)。
