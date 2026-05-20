"""Username/password login → session cookie.

v0.1.6 makes username/password the primary auth mode. The URL-path token
alone is no longer enough — every protected route also requires a valid
signed session cookie issued by /login (or by the passkey-login endpoint,
when that feature is enabled).

The cookie itself reuses the existing passkey-session machinery in
``app.auth.passkey`` (same itsdangerous serializer, same cookie name,
same max-age), so the two login paths are interchangeable from
admin_auth's perspective.

The form is a single self-contained HTML page — no JS framework, no
client-side validation; the browser handles the submit and the redirect
flow.
"""

from __future__ import annotations

import html
import secrets
from typing import Annotated

from fastapi import APIRouter, Cookie, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.auth.passkey import (
    SESSION_COOKIE_NAME,
    SESSION_MAX_AGE,
    issue_session_cookie,
)
from app.config import get_settings

router = APIRouter(tags=["login"])


def _login_path_ok(supplied: str) -> bool:
    """The login page is reachable at /login when admin.login_path is empty
    (backward compat for installs that pre-date v0.1.11) or at
    /login/{login_path} when set. Anything else 404s — bots probing
    /login can't even confirm the form exists."""
    expected = get_settings().admin.login_path
    if not expected:
        return supplied == ""
    return secrets.compare_digest(supplied, expected)


_LOGIN_HTML = """<!doctype html>
<html lang="__LANG_ATTR__">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ProxyBox · __TITLE_SUFFIX__</title>
  <style>
    :root { color-scheme: light dark; }
    * { box-sizing: border-box; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif;
           background: #f6f7f9; margin: 0; padding: 24px;
           display: flex; align-items: center; justify-content: center; min-height: 100vh; }
    .card { background: white; padding: 40px 32px; border-radius: 14px;
            max-width: 380px; width: 100%; box-shadow: 0 10px 32px rgba(0,0,0,.08); }
    h1 { margin: 0 0 4px; font-size: 22px; color: #16a34a; letter-spacing: -.3px; }
    .sub { color: #6b7280; font-size: 13px; margin-bottom: 24px; }
    label { display: block; font-size: 12px; color: #4b5563; margin-top: 14px;
            margin-bottom: 4px; font-weight: 500; }
    input { width: 100%; padding: 11px 12px; border: 1px solid #e5e7eb; border-radius: 7px;
            font-size: 14px; transition: border-color .15s; }
    input:focus { outline: none; border-color: #16a34a; box-shadow: 0 0 0 3px rgba(22,163,74,.15); }
    button { width: 100%; margin-top: 22px; background: #16a34a; color: white; padding: 11px;
             border: none; border-radius: 7px; font-size: 14px; font-weight: 600; cursor: pointer;
             transition: background .15s; }
    button:hover { background: #15803d; }
    .err { color: #dc2626; font-size: 13px; margin-top: 14px; text-align: center;
           background: #fef2f2; padding: 8px; border-radius: 6px; }
    .hint { color: #9ca3af; font-size: 11px; margin-top: 20px; line-height: 1.6;
            border-top: 1px solid #f3f4f6; padding-top: 16px; }
    code { background: #f3f4f6; padding: 1px 5px; border-radius: 3px; font-size: 11px; }
    .lang-switch { position: absolute; top: 16px; right: 20px; font-size: 11px;
                   color: #9ca3af; text-decoration: none; padding: 4px 10px;
                   border: 1px solid #e5e7eb; border-radius: 6px; }
    .lang-switch:hover { color: #16a34a; border-color: #16a34a; }
    @media (prefers-color-scheme: dark) {
      body { background: #0a0a0a; }
      .card { background: #171717; color: #e5e7eb; box-shadow: 0 10px 32px rgba(0,0,0,.4); }
      .sub { color: #9ca3af; }
      label { color: #d1d5db; }
      input { background: #262626; border-color: #404040; color: #e5e7eb; }
      .err { background: #2a1010; }
      .hint { color: #6b7280; border-color: #262626; }
      code { background: #262626; color: #d1d5db; }
      .lang-switch { border-color: #404040; }
    }
  </style>
</head>
<body>
  <a href="?lang=__OTHER_LANG__" class="lang-switch">__OTHER_LANG_LABEL__</a>
  <div class="card">
    <h1>🛡 ProxyBox</h1>
    <div class="sub">__TAGLINE__</div>
    <form method="post" action="__ACTION__">
      <label>__LBL_USERNAME__</label>
      <input type="text" name="username" autofocus required autocomplete="username">
      <label>__LBL_PASSWORD__</label>
      <input type="password" name="password" required autocomplete="current-password">
      <button type="submit">__BTN_LOGIN__</button>
      __ERROR__
    </form>
    <div class="hint">__HINT__</div>
  </div>
</body>
</html>
"""

# Bilingual strings. The login page is server-rendered (the SPA's
# client-side translator doesn't run here), so we read ?lang= or the
# proxybox-lang cookie and pick a side.
_STRINGS = {
    "zh": {
        "lang_attr": "zh-CN",
        "other_lang": "en",
        "other_lang_label": "EN",
        "title_suffix": "登录",
        "tagline": "输入用户名 + 密码登录后台",
        "lbl_username": "用户名",
        "lbl_password": "密码",
        "btn_login": "登 录",
        "err_creds": "用户名或密码错误",
        "hint": (
            "用户名 + 密码在 <code>install.sh</code> 安装结束时打印,也保存于"
            " <code>/etc/proxybox/config.yaml</code> 的 <code>admin.username</code> /"
            " <code>admin.password</code> 字段。"
        ),
    },
    "en": {
        "lang_attr": "en",
        "other_lang": "zh",
        "other_lang_label": "中",
        "title_suffix": "Login",
        "tagline": "Enter your username + password to access the admin panel",
        "lbl_username": "Username",
        "lbl_password": "Password",
        "btn_login": "Log in",
        "err_creds": "Wrong username or password",
        "hint": (
            "Username + password were printed when <code>install.sh</code> finished;"
            " they are also stored in <code>/etc/proxybox/config.yaml</code> under"
            " <code>admin.username</code> / <code>admin.password</code>."
        ),
    },
}


def _pick_lang(request_lang: str | None, cookie_lang: str | None) -> str:
    """?lang= takes priority over the cookie. Default to zh."""
    for v in (request_lang, cookie_lang):
        if v in ("zh", "en"):
            return v
    return "zh"


def _render(
    action: str = "/login",
    error: str = "",
    status: int = 200,
    lang: str = "zh",
    set_cookie_lang: str | None = None,
) -> HTMLResponse:
    s = _STRINGS.get(lang, _STRINGS["zh"])
    # `error` may be a free-form string OR the sentinel "creds" — translate
    # the sentinel to the localised "wrong username or password" copy.
    error_text = s.get("err_creds", "") if error == "creds" else error
    error_html = f'<div class="err">{html.escape(error_text)}</div>' if error_text else ""
    body = _LOGIN_HTML
    body = body.replace("__ACTION__", html.escape(action))
    body = body.replace("__ERROR__", error_html)
    body = body.replace("__LANG_ATTR__", s["lang_attr"])
    body = body.replace("__OTHER_LANG__", s["other_lang"])
    body = body.replace("__OTHER_LANG_LABEL__", s["other_lang_label"])
    body = body.replace("__TITLE_SUFFIX__", s["title_suffix"])
    body = body.replace("__TAGLINE__", s["tagline"])
    body = body.replace("__LBL_USERNAME__", s["lbl_username"])
    body = body.replace("__LBL_PASSWORD__", s["lbl_password"])
    body = body.replace("__BTN_LOGIN__", s["btn_login"])
    body = body.replace("__HINT__", s["hint"])
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }
    resp = HTMLResponse(content=body, status_code=status, headers=headers)
    # If the visitor clicked the language switcher (?lang=...), persist the
    # choice in a cookie so it sticks across reloads + matches the SPA's
    # localStorage convention.
    if set_cookie_lang in ("zh", "en"):
        resp.set_cookie(
            "proxybox-lang",
            set_cookie_lang,
            max_age=365 * 86400,
            httponly=False,
            samesite="lax",
        )
    return resp


def _post_login_destination(next_path: str, token: str) -> str:
    """Where to send the user after successful login.

    Default: /admin/{token}/ (the SPA). When the SPA bounced an unauthed
    user here via ``?next=...``, honour that — but ONLY if the path stays
    on this origin (starts with /, has no scheme), so a malicious link
    can't redirect to an attacker site.
    """
    if next_path.startswith("/") and not next_path.startswith("//"):
        return next_path
    return f"/admin/{token}/"


def _login_url(suffix: str = "") -> str:
    """Build the /login or /login/{secret} URL the form should submit to."""
    p = get_settings().admin.login_path
    base = f"/login/{p}" if p else "/login"
    return f"{base}{suffix}"


# Two-path registration: legacy /login (active when admin.login_path is
# empty) AND /login/{secret} (active when admin.login_path is set).
# Both handlers re-check _login_path_ok so a misconfigured /login/{wrong}
# returns 404, not "Wrong password".


@router.get("/login", response_class=HTMLResponse, include_in_schema=False)
async def login_page_legacy(
    next: str = "",
    lang: str | None = None,
    proxybox_lang: str | None = Cookie(default=None, alias="proxybox-lang"),
) -> HTMLResponse:
    if not _login_path_ok(""):
        raise HTTPException(404, "not found")
    chosen = _pick_lang(lang, proxybox_lang)
    action = _login_url(f"?next={html.escape(next)}" if next else "")
    return _render(action=action, lang=chosen, set_cookie_lang=lang if lang else None)


@router.get("/login/{secret}", response_class=HTMLResponse, include_in_schema=False)
async def login_page_secret(
    secret: str,
    next: str = "",
    lang: str | None = None,
    proxybox_lang: str | None = Cookie(default=None, alias="proxybox-lang"),
) -> HTMLResponse:
    if not _login_path_ok(secret):
        raise HTTPException(404, "not found")
    chosen = _pick_lang(lang, proxybox_lang)
    action = _login_url(f"?next={html.escape(next)}" if next else "")
    return _render(action=action, lang=chosen, set_cookie_lang=lang if lang else None)


async def _do_login(
    username: str,
    password: str,
    next_path: str,
    secret_supplied: str,
    lang: str,
) -> Response:
    if not _login_path_ok(secret_supplied):
        raise HTTPException(404, "not found")
    settings = get_settings()
    if not settings.admin.password:
        raise HTTPException(
            503,
            "password login not configured — set admin.password in /etc/proxybox/config.yaml "
            "or enable features.url_token_bypass for token-only access",
        )

    user_ok = secrets.compare_digest(username.encode(), settings.admin.username.encode())
    pass_ok = secrets.compare_digest(password.encode(), settings.admin.password.encode())
    if not (user_ok and pass_ok):
        action = _login_url(f"?next={html.escape(next_path)}" if next_path else "")
        return _render(action=action, error="creds", status=401, lang=lang)

    target = _post_login_destination(next_path, settings.admin.token)
    resp = RedirectResponse(target, status_code=303)
    resp.set_cookie(
        SESSION_COOKIE_NAME,
        issue_session_cookie(),
        max_age=SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return resp


@router.post("/login", include_in_schema=False)
async def login_submit_legacy(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: str = "",
    proxybox_lang: str | None = Cookie(default=None, alias="proxybox-lang"),
) -> Response:
    return await _do_login(
        username,
        password,
        next,
        secret_supplied="",
        lang=_pick_lang(None, proxybox_lang),
    )


@router.post("/login/{secret}", include_in_schema=False)
async def login_submit_secret(
    secret: str,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: str = "",
    proxybox_lang: str | None = Cookie(default=None, alias="proxybox-lang"),
) -> Response:
    return await _do_login(
        username,
        password,
        next,
        secret_supplied=secret,
        lang=_pick_lang(None, proxybox_lang),
    )


@router.post("/logout", include_in_schema=False)
async def logout() -> RedirectResponse:
    resp = RedirectResponse(_login_url(), status_code=303)
    resp.delete_cookie(SESSION_COOKIE_NAME, samesite="lax")
    return resp


@router.get("/logout", include_in_schema=False)
async def logout_get() -> RedirectResponse:
    return await logout()
