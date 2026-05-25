"""ProxyBox Telegram bot — entry point.

Long-poll loop over Telegram's getUpdates, dispatches commands to handlers,
sends replies via sendMessage. Talks to ProxyBox admin API over HTTP using
the configured ADMIN_TOKEN.

Run:
    BOT_TOKEN=... TG_ALLOWED_USERS=12345 ADMIN_TOKEN=... python -m bot

systemd unit at deploy/systemd/proxybox-bot.service drives this in production.
"""

from __future__ import annotations

import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from bot.api import ProxyBoxAPI
from bot.config import BotConfig, load_config
from bot.handlers import dispatch

log = logging.getLogger("proxybox-bot")


def _tg_call(
    cfg: BotConfig,
    method: str,
    params: dict[str, Any] | None = None,
    timeout: int = 35,
) -> dict:
    url = f"https://api.telegram.org/bot{cfg.bot_token}/{method}"
    data = urllib.parse.urlencode(params or {}).encode()
    req = urllib.request.Request(url, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        log.error("tg http %s on %s: %s", e.code, method, e.read().decode()[:200])
        return {"ok": False}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
        log.error("tg call %s failed: %s", method, e)
        return {"ok": False}


def _send_message(cfg: BotConfig, chat_id: int, text: str) -> None:
    _tg_call(
        cfg,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": "true",
        },
    )


def _handle_update(cfg: BotConfig, api: ProxyBoxAPI, update: dict) -> None:
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return
    user_id = (msg.get("from") or {}).get("id")
    chat_id = (msg.get("chat") or {}).get("id")
    text = (msg.get("text") or "").strip()
    if not text or not chat_id:
        return
    if user_id not in cfg.allowed_users:
        log.warning("unauthorized user_id=%s text=%r", user_id, text[:80])
        _send_message(cfg, chat_id, "⚠️ unauthorized")
        return
    try:
        reply = dispatch(api, text)
    except Exception:
        log.exception("handler crashed on %r", text)
        reply = "❌ internal error — see bot logs"
    _send_message(cfg, chat_id, reply)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    cfg = load_config()
    api = ProxyBoxAPI(cfg.api_url, cfg.admin_token, internal_secret=cfg.internal_secret)

    me = _tg_call(cfg, "getMe", {}, timeout=10)
    if not me.get("ok"):
        log.error("failed to authenticate with Telegram — check BOT_TOKEN")
        return 1
    log.info(
        "started bot %s allowed_users=%d",
        (me["result"].get("username") or "?"),
        len(cfg.allowed_users),
    )

    offset = 0
    while True:
        resp = _tg_call(
            cfg,
            "getUpdates",
            {"offset": offset, "timeout": cfg.poll_timeout},
            timeout=cfg.poll_timeout + 5,
        )
        if not resp.get("ok"):
            time.sleep(5)
            continue
        for upd in resp.get("result", []):
            offset = max(offset, upd["update_id"] + 1)
            _handle_update(cfg, api, upd)


if __name__ == "__main__":
    sys.exit(main() or 0)
