"""Bot configuration — read entirely from environment.

Keeps secrets out of config.yaml. Set via systemd unit's [Service] Environment=
or a /etc/proxybox/bot.env file referenced by EnvironmentFile=.

Required env:
    BOT_TOKEN              Telegram bot token from @BotFather
    TG_ALLOWED_USERS       Comma-separated Telegram user IDs (whitelist)
    ADMIN_TOKEN            ProxyBox admin token (must match config.yaml admin.token)
                            Native mode also needs features.bot=true so token-only
                            API access is accepted from 127.0.0.1 only. Docker
                            mode uses PROXYBOX_BOT_INTERNAL_SECRET instead.

Optional env:
    PROXYBOX_API_URL       Default http://127.0.0.1:8080
    PROXYBOX_BOT_INTERNAL_SECRET
                           Docker sidecar auth secret. Automatically set by
                           docker-compose for Docker installs.
    POLL_TIMEOUT           getUpdates long-poll timeout seconds, default 30
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BotConfig:
    bot_token: str
    allowed_users: frozenset[int]
    admin_token: str
    api_url: str
    internal_secret: str
    poll_timeout: int


def load_config() -> BotConfig:
    missing = []
    bot_token = os.environ.get("BOT_TOKEN", "")
    if not bot_token:
        missing.append("BOT_TOKEN")
    admin_token = os.environ.get("ADMIN_TOKEN", "")
    if not admin_token:
        missing.append("ADMIN_TOKEN")
    raw_users = os.environ.get("TG_ALLOWED_USERS", "")
    if not raw_users:
        missing.append("TG_ALLOWED_USERS")
    if missing:
        raise SystemExit(f"missing required env: {', '.join(missing)}; see bot/config.py docstring")
    try:
        users = frozenset(int(s.strip()) for s in raw_users.split(",") if s.strip())
    except ValueError as e:
        raise SystemExit(f"TG_ALLOWED_USERS must be comma-separated integers: {e}") from None
    return BotConfig(
        bot_token=bot_token,
        allowed_users=users,
        admin_token=admin_token,
        api_url=os.environ.get("PROXYBOX_API_URL", "http://127.0.0.1:8080").rstrip("/"),
        internal_secret=os.environ.get("PROXYBOX_BOT_INTERNAL_SECRET", ""),
        poll_timeout=int(os.environ.get("POLL_TIMEOUT", "30")),
    )
