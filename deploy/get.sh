#!/usr/bin/env bash
# ProxyBox one-line bootstrap installer.
#
# For users who only have a fresh Debian/Ubuntu VPS and don't want to type
# several commands. SSH in as root, then paste ONE line:
#
#   bash <(curl -fsSL https://raw.githubusercontent.com/carlos0xx/proxybox/main/deploy/get.sh)
#
# It installs git/curl, clones ProxyBox to /opt/proxybox, and launches the
# installer (which lets you pick Docker or native — just press Enter for the
# recommended Docker install). Pass options through to skip the prompt:
#
#   bash <(curl -fsSL .../get.sh) --docker
#   bash <(curl -fsSL .../get.sh) --native --lang zh
#
# Prefer to read before running? Download first:
#   curl -fsSL https://raw.githubusercontent.com/carlos0xx/proxybox/main/deploy/get.sh -o get.sh
#   less get.sh && bash get.sh
#
# Env overrides: PROXYBOX_REPO, PROXYBOX_REF (branch/tag), PROXYBOX_DIR.

set -euo pipefail

REPO="${PROXYBOX_REPO:-https://github.com/carlos0xx/proxybox}"
REF="${PROXYBOX_REF:-main}"
DIR="${PROXYBOX_DIR:-/opt/proxybox}"

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "请用 root 运行 (例如先 sudo -i,再粘贴这一行) / run as root"

command -v apt-get >/dev/null 2>&1 \
    || die "一键脚本目前仅支持 Debian/Ubuntu (apt)。其他系统请按 docs/ 手动安装。"

say "安装依赖 git / curl / ca-certificates ..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq git curl ca-certificates >/dev/null

if [ -d "$DIR/.git" ]; then
    say "已存在 $DIR,更新到最新代码 ..."
    git -C "$DIR" fetch --quiet --depth 1 origin "$REF" 2>/dev/null || true
    git -C "$DIR" reset --hard --quiet "origin/$REF" 2>/dev/null \
        || git -C "$DIR" pull --quiet --ff-only 2>/dev/null || true
else
    say "克隆 ProxyBox 到 $DIR ..."
    rm -rf "$DIR"
    git clone --quiet --depth 1 --branch "$REF" "$REPO" "$DIR" 2>/dev/null \
        || git clone --quiet --depth 1 "$REPO" "$DIR"
fi

cd "$DIR"
say "启动安装程序 ..."
exec bash deploy/install.sh "$@"
