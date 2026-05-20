"""Generic domain → app-group classification.

Used by the traffic worker (when populating host_log) and by the
``/api/history/device/{name}`` aggregator (when bucketing per app group).

The mapping is intentionally generic and category-level — not a personal
"sites I track" dictionary. Categories like "Video" / "Social" / "Google"
say *roughly* what the traffic is, not *which specific show on which
specific platform*. New entries should keep this level of abstraction.

The classifier walks ``_SUFFIXES`` in declared order and returns the
first match by suffix. Unknown hosts fall to ``"其他"``.
"""

from __future__ import annotations

# Ordered (suffix, app_group) pairs. Most specific first within each group.
# Suffix match is right-anchored on a "." boundary, so "youtube.com" matches
# both "www.youtube.com" and "r3---sn-abc.youtube.com" but not "fakeyoutube.com".
_SUFFIXES: list[tuple[str, str]] = [
    # ─── Video ──────────────────────────────────────────────────────
    ("youtube.com", "Video"),
    ("youtu.be", "Video"),
    ("googlevideo.com", "Video"),
    ("ytimg.com", "Video"),
    ("ggpht.com", "Video"),
    ("netflix.com", "Video"),
    ("nflxvideo.net", "Video"),
    ("nflximg.net", "Video"),
    ("nflxso.net", "Video"),
    ("tiktok.com", "Video"),
    ("tiktokcdn.com", "Video"),
    ("muscdn.com", "Video"),
    ("bytedance.com", "Video"),
    ("hulu.com", "Video"),
    ("twitch.tv", "Video"),
    ("ttvnw.net", "Video"),
    ("vimeo.com", "Video"),
    ("disneyplus.com", "Video"),
    ("hbomax.com", "Video"),
    ("primevideo.com", "Video"),
    # ─── Social ─────────────────────────────────────────────────────
    ("twitter.com", "Social"),
    ("twimg.com", "Social"),
    ("x.com", "Social"),
    ("facebook.com", "Social"),
    ("fbcdn.net", "Social"),
    ("instagram.com", "Social"),
    ("cdninstagram.com", "Social"),
    ("threads.net", "Social"),
    ("reddit.com", "Social"),
    ("redd.it", "Social"),
    ("redditmedia.com", "Social"),
    ("linkedin.com", "Social"),
    ("licdn.com", "Social"),
    ("pinterest.com", "Social"),
    ("pinimg.com", "Social"),
    # ─── Messaging ──────────────────────────────────────────────────
    ("whatsapp.net", "通讯"),
    ("whatsapp.com", "通讯"),
    ("telegram.org", "通讯"),
    ("t.me", "通讯"),
    ("telegram.me", "通讯"),
    ("discord.com", "通讯"),
    ("discordapp.com", "通讯"),
    ("discord.gg", "通讯"),
    ("signal.org", "通讯"),
    ("slack.com", "通讯"),
    ("zoom.us", "通讯"),
    ("zoomgov.com", "通讯"),
    ("teams.microsoft.com", "通讯"),
    ("webex.com", "通讯"),
    # ─── Google ─────────────────────────────────────────────────────
    ("google.com", "Google"),
    ("google.co.jp", "Google"),
    ("gstatic.com", "Google"),
    ("googleapis.com", "Google"),
    ("googleusercontent.com", "Google"),
    ("googletagmanager.com", "Google"),
    ("googleadservices.com", "Google"),
    ("doubleclick.net", "Google"),
    ("googlesyndication.com", "Google"),
    ("gmail.com", "Google"),
    ("youtube-nocookie.com", "Google"),
    ("blogger.com", "Google"),
    ("blogspot.com", "Google"),
    # ─── Apple ──────────────────────────────────────────────────────
    ("apple.com", "Apple"),
    ("icloud.com", "Apple"),
    ("icloud-content.com", "Apple"),
    ("mzstatic.com", "Apple"),
    ("cdn-apple.com", "Apple"),
    ("itunes.apple.com", "Apple"),
    ("apps.apple.com", "Apple"),
    ("appleid.apple.com", "Apple"),
    # ─── Microsoft ──────────────────────────────────────────────────
    ("microsoft.com", "Microsoft"),
    ("msftconnecttest.com", "Microsoft"),
    ("live.com", "Microsoft"),
    ("office.com", "Microsoft"),
    ("office365.com", "Microsoft"),
    ("onedrive.com", "Microsoft"),
    ("sharepoint.com", "Microsoft"),
    ("outlook.com", "Microsoft"),
    ("bing.com", "Microsoft"),
    ("msn.com", "Microsoft"),
    # ─── AI services ────────────────────────────────────────────────
    ("openai.com", "AI"),
    ("chatgpt.com", "AI"),
    ("oaiusercontent.com", "AI"),
    ("anthropic.com", "AI"),
    ("claude.ai", "AI"),
    ("perplexity.ai", "AI"),
    ("gemini.google.com", "AI"),
    ("midjourney.com", "AI"),
    ("huggingface.co", "AI"),
    # ─── GitHub & dev ───────────────────────────────────────────────
    ("github.com", "开发工具"),
    ("githubusercontent.com", "开发工具"),
    ("githubassets.com", "开发工具"),
    ("gitlab.com", "开发工具"),
    ("bitbucket.org", "开发工具"),
    ("stackexchange.com", "开发工具"),
    ("stackoverflow.com", "开发工具"),
    ("npmjs.com", "开发工具"),
    ("pypi.org", "开发工具"),
    ("pythonhosted.org", "开发工具"),
    ("docker.com", "开发工具"),
    ("docker.io", "开发工具"),
    ("hashicorp.com", "开发工具"),
    ("vercel.com", "开发工具"),
    ("vercel.app", "开发工具"),
    ("netlify.com", "开发工具"),
    ("netlify.app", "开发工具"),
    # ─── CDN / infra ────────────────────────────────────────────────
    ("cloudflare.com", "CDN / 基础设施"),
    ("cloudflare.net", "CDN / 基础设施"),
    ("cloudflareinsights.com", "CDN / 基础设施"),
    ("akamai.net", "CDN / 基础设施"),
    ("akamaihd.net", "CDN / 基础设施"),
    ("akamaized.net", "CDN / 基础设施"),
    ("akamaiedge.net", "CDN / 基础设施"),
    ("fastly.net", "CDN / 基础设施"),
    ("fastlylb.net", "CDN / 基础设施"),
    ("cloudfront.net", "CDN / 基础设施"),
    ("amazonaws.com", "CDN / 基础设施"),
    ("aws.amazon.com", "CDN / 基础设施"),
    ("azure.com", "CDN / 基础设施"),
    ("azureedge.net", "CDN / 基础设施"),
    ("digitaloceanspaces.com", "CDN / 基础设施"),
    # ─── Music ──────────────────────────────────────────────────────
    ("spotify.com", "Music"),
    ("scdn.co", "Music"),
    ("spotifycdn.com", "Music"),
    ("music.apple.com", "Music"),
    ("soundcloud.com", "Music"),
    # ─── Gaming ─────────────────────────────────────────────────────
    ("steampowered.com", "游戏"),
    ("steamcommunity.com", "游戏"),
    ("steamcontent.com", "游戏"),
    ("steamstatic.com", "游戏"),
    ("playstation.net", "游戏"),
    ("playstation.com", "游戏"),
    ("xbox.com", "游戏"),
    ("xboxlive.com", "游戏"),
    ("nintendo.com", "游戏"),
    ("nintendo.net", "游戏"),
    ("epicgames.com", "游戏"),
    ("ea.com", "游戏"),
    ("activision.com", "游戏"),
    ("ubisoft.com", "游戏"),
    ("battle.net", "游戏"),
    # ─── News ───────────────────────────────────────────────────────
    ("nytimes.com", "新闻"),
    ("bbc.com", "新闻"),
    ("bbc.co.uk", "新闻"),
    ("wsj.com", "新闻"),
    ("ft.com", "新闻"),
    ("bloomberg.com", "新闻"),
    ("reuters.com", "新闻"),
    ("medium.com", "新闻"),
    ("substack.com", "新闻"),
    ("news.ycombinator.com", "新闻"),
    # ─── E-commerce ─────────────────────────────────────────────────
    ("amazon.com", "购物"),
    ("amazon.co.jp", "购物"),
    ("ebay.com", "购物"),
    ("shopify.com", "购物"),
    ("paypal.com", "购物"),
    ("stripe.com", "购物"),
]

# Build a single dict for O(suffix-length) match — keyed on the suffix
# (without leading dot) for fast bracketing in classify().
_LOOKUP = dict(_SUFFIXES)


def classify(host: str | None) -> str:
    """Return the app group for a host name, or '其他' if unknown.

    Matching is right-anchored on '.' boundaries: the host is split into
    suffixes (every drop-leftmost-label form) and we return the first
    suffix that's in the lookup table. Examples:
        r3---sn-abc.googlevideo.com  → 'Video'
        chat.openai.com              → 'AI'
        unknown.example.org          → '其他'
        ""                           → '其他'
        IPv4 address                 → '其他'
    """
    if not host:
        return "其他"
    h = host.strip().lower().rstrip(".")
    if not h or h[0].isdigit():  # IP literal or empty
        return "其他"
    parts = h.split(".")
    # Try suffixes from longest (full host) to shortest (TLD).
    for i in range(len(parts)):
        suffix = ".".join(parts[i:])
        group = _LOOKUP.get(suffix)
        if group:
            return group
    return "其他"


def known_groups() -> list[str]:
    """All app-group names referenced in the classification table."""
    seen: dict[str, None] = {}
    for _, g in _SUFFIXES:
        seen[g] = None
    seen["其他"] = None
    return list(seen)
