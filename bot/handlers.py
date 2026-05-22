"""Telegram command handlers — pure functions returning a string reply.

Each handler takes (api, args) and returns Markdown-formatted reply text. The
main loop sends that text via sendMessage. No direct TG calls happen here —
makes handlers easy to test in isolation.
"""

from __future__ import annotations

from bot.api import ProxyBoxAPI

NL = "\n"


def _fmt_bytes(n: float) -> str:
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f}{u}"
        n /= 1024
    return f"{n:.1f}PB"


def _err(reply: dict) -> str | None:
    if reply.get("_error"):
        return f"❌ API error {reply['_status']}: {reply['_detail']}"
    return None


def cmd_help(api: ProxyBoxAPI, args: str) -> str:
    return (
        "*ProxyBox bot — commands*"
        + NL
        + "/status — system status"
        + NL
        + "/devices — devices + current usage"
        + NL
        + "/traffic — 24h system traffic"
        + NL
        + "/bans — currently banned IPs"
        + NL
        + "/pause <name> [until_ts] — pause a device (0 = indefinite)"
        + NL
        + "/resume <name> — resume a paused device"
        + NL
        + "/help — this message"
    )


def cmd_status(api: ProxyBoxAPI, args: str) -> str:
    r = api.get("/api/status")
    err = _err(r)
    if err:
        return err
    svcs = r.get("services", {})
    lines = [f"*System status* — {r.get('hostname', '?')}"]
    for name, state in svcs.items():
        mark = "✅" if state == "active" else ("⏸" if state == "inactive" else "❓")
        lines.append(f"{mark} `{name}` — {state}")
    mem = r.get("mem", {})
    disk = r.get("disk", {})
    lines.append("")
    lines.append(f"load: `{' '.join(r.get('load', []))}`")
    lines.append(f"mem: {mem.get('used_mb', 0)}/{mem.get('total_mb', 0)}MB ({mem.get('pct', 0)}%)")
    lines.append(
        f"disk: {disk.get('used', '?')} / {disk.get('total', '?')} ({disk.get('pct', '?')})"
    )
    lines.append(f"uptime: {r.get('uptime', '?')}")
    return NL.join(lines)


def cmd_devices(api: ProxyBoxAPI, args: str) -> str:
    r = api.get("/api/devices")
    err = _err(r)
    if err:
        return err
    devs = r.get("devices", [])
    if not devs:
        return "_no devices_"
    lines = [f"*{len(devs)} device(s)*"]
    for d in devs:
        flag = "⏸" if d["is_paused"] else "▶"
        lines.append(
            f"{flag} `{d['name']}` — today {_fmt_bytes(d['rx_today'])}↓ / "
            f"{_fmt_bytes(d['tx_today'])}↑"
        )
    return NL.join(lines)


def cmd_traffic(api: ProxyBoxAPI, args: str) -> str:
    r = api.get("/api/traffic")
    err = _err(r)
    if err:
        return err
    return (
        "*Traffic — last 24h*"
        + NL
        + f"down: {_fmt_bytes(r.get('rx_24h', 0))}"
        + NL
        + f"up: {_fmt_bytes(r.get('tx_24h', 0))}"
        + NL
        + f"active devices: {r.get('active_devices_24h', 0)}"
        + NL
        + f"today: {_fmt_bytes(r.get('rx_today', 0))}↓ / {_fmt_bytes(r.get('tx_today', 0))}↑"
    )


def cmd_bans(api: ProxyBoxAPI, args: str) -> str:
    r = api.get("/api/bans")
    err = _err(r)
    if err:
        return err
    banned = r.get("banned", [])
    if not banned:
        return f"_no IPs banned_ ({r.get('total_banned', 0)} historic)"
    return (
        f"*Banned IPs* ({r.get('currently_banned', 0)}):" + NL + NL.join(f"`{ip}`" for ip in banned)
    )


def cmd_pause(api: ProxyBoxAPI, args: str) -> str:
    parts = args.split()
    if not parts:
        return "usage: `/pause <name> [until_ts]`"
    name = parts[0]
    until_ts = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    r = api.post(f"/api/devices/{name}/pause", {"until_ts": until_ts})
    err = _err(r)
    if err:
        return err
    if r.get("paused_until", 0) > 0:
        return f"⏸ paused `{name}` (paused_until={r['paused_until']}); inbounds removed"
    return f"⏸ paused `{name}`"


def cmd_resume(api: ProxyBoxAPI, args: str) -> str:
    parts = args.split()
    if not parts:
        return "usage: `/resume <name>`"
    name = parts[0]
    r = api.post(f"/api/devices/{name}/resume")
    err = _err(r)
    if err:
        return err
    return f"▶ resumed `{name}`; inbounds restored"


COMMANDS = {
    "help": cmd_help,
    "start": cmd_help,
    "status": cmd_status,
    "devices": cmd_devices,
    "traffic": cmd_traffic,
    "bans": cmd_bans,
    "pause": cmd_pause,
    "resume": cmd_resume,
}


def dispatch(api: ProxyBoxAPI, text: str) -> str:
    text = text.strip()
    if not text.startswith("/"):
        return "_send /help for a list of commands_"
    parts = text[1:].split(maxsplit=1)
    cmd = parts[0].split("@")[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    handler = COMMANDS.get(cmd)
    if not handler:
        return f"unknown command `/{cmd}`. try /help"
    return handler(api, args)
