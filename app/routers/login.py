"""Username/password login → session cookie.

v0.1.6 makes username/password the primary auth mode. The URL-path token
alone is no longer enough — every protected route also requires a valid
signed session cookie issued by /login (or by the passkey-login endpoint,
when that feature is enabled).

The cookie itself reuses the existing passkey-session machinery in
``app.auth.passkey`` (same itsdangerous serializer, same per-instance
cookie name, same max-age), so the two login paths are interchangeable from
admin_auth's perspective.

The form is a single self-contained HTML page — no JS framework, no
client-side validation; the browser handles the submit and the redirect
flow.
"""

from __future__ import annotations

import asyncio
import html
import secrets
from ipaddress import ip_address
from typing import Annotated

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.auth.passkey import (
    SESSION_MAX_AGE,
    issue_session_cookie,
    session_cookie_name,
)
from app.config import get_settings
from app.services import login_rate_limit

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
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ProxyBox · 登录</title>
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
    @media (prefers-color-scheme: dark) {
      body { background: #0a0a0a; }
      .card { background: #171717; color: #e5e7eb; box-shadow: 0 10px 32px rgba(0,0,0,.4); }
      .sub { color: #9ca3af; }
      label { color: #d1d5db; }
      input { background: #262626; border-color: #404040; color: #e5e7eb; }
      .err { background: #2a1010; }
      .hint { color: #6b7280; border-color: #262626; }
      code { background: #262626; color: #d1d5db; }
    }
  </style>
</head>
<body>
  <div class="card">
    <h1>🛡 ProxyBox</h1>
    <div class="sub">输入用户名 + 密码登录后台</div>
    <form method="post" action="__ACTION__">
      <label>用户名</label>
      <input type="text" name="username" autofocus required autocomplete="username">
      <label>密码</label>
      <input type="password" name="password" required autocomplete="current-password">
      <button type="submit">登 录</button>
      __PASSKEY_LOGIN__
      __ERROR__
    </form>
    <div class="hint">
      用户名 + 密码在 <code>install.sh</code> 安装结束时打印。用户名保存在
      <code>/etc/proxybox/config.yaml</code> 的 <code>admin.username</code>,
      密码保存在 <code>/etc/proxybox/admin.password</code>。
    </div>
  </div>
  __PASSKEY_SCRIPT__
</body>
</html>
"""

_PASSKEY_LOGIN_HTML = """
      <button type="button" id="passkey-login" style="margin-top:10px;background:#111827;">
        Passkey / Touch ID
      </button>
"""

_PASSKEY_LOGIN_SCRIPT = """
  <script>
    const b64ToBytes = s => {
      s = s.replace(/-/g, '+').replace(/_/g, '/');
      const bin = atob(s + '='.repeat((4 - s.length % 4) % 4));
      return Uint8Array.from(bin, c => c.charCodeAt(0));
    };
    const bytesToB64 = b => btoa(String.fromCharCode(...new Uint8Array(b)))
      .replace(/\\+/g, '-').replace(/\\//g, '_').replace(/=+$/, '');
    const passkeyBtn = document.getElementById('passkey-login');
    if (passkeyBtn) {
      passkeyBtn.addEventListener('click', async () => {
        passkeyBtn.disabled = true;
        passkeyBtn.textContent = 'Touch ID...';
        try {
          const begin = await fetch('/auth/webauthn/login/begin', {method: 'POST'});
          if (!begin.ok) throw new Error(await begin.text());
          const d1 = await begin.json();
          const opts = d1.options;
          opts.challenge = b64ToBytes(opts.challenge);
          if (opts.allowCredentials) {
            opts.allowCredentials = opts.allowCredentials.map(c => ({...c, id: b64ToBytes(c.id)}));
          }
          const cred = await navigator.credentials.get({publicKey: opts});
          const assertion = {
            id: cred.id,
            rawId: bytesToB64(cred.rawId),
            type: cred.type,
            response: {
              authenticatorData: bytesToB64(cred.response.authenticatorData),
              clientDataJSON: bytesToB64(cred.response.clientDataJSON),
              signature: bytesToB64(cred.response.signature),
              userHandle: cred.response.userHandle ? bytesToB64(cred.response.userHandle) : null,
            },
          };
          const complete = await fetch('/auth/webauthn/login/complete', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              handle: d1.handle,
              assertion,
              next_path: new URLSearchParams(window.location.search).get('next') || '',
            }),
          });
          if (!complete.ok) throw new Error(await complete.text());
          const d2 = await complete.json();
          window.location.href = d2.redirect || '/';
        } catch (e) {
          passkeyBtn.disabled = false;
          passkeyBtn.textContent = 'Passkey / Touch ID';
          alert('Passkey 登录失败: ' + e.message);
        }
      });
    }
  </script>
"""


def _render(
    action: str = "/login",
    error: str = "",
    status: int = 200,
) -> HTMLResponse:
    # `error` may be a free-form string OR the sentinel "creds".
    error_text = "用户名或密码错误" if error == "creds" else error
    error_html = f'<div class="err">{html.escape(error_text)}</div>' if error_text else ""
    body = _LOGIN_HTML
    body = body.replace("__ACTION__", html.escape(action))
    body = body.replace("__ERROR__", error_html)
    passkey_on = bool(get_settings().features.passkey)
    body = body.replace("__PASSKEY_LOGIN__", _PASSKEY_LOGIN_HTML if passkey_on else "")
    body = body.replace("__PASSKEY_SCRIPT__", _PASSKEY_LOGIN_SCRIPT if passkey_on else "")
    headers = {
        "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
        "Pragma": "no-cache",
    }
    resp = HTMLResponse(content=body, status_code=status, headers=headers)
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
) -> HTMLResponse:
    if not _login_path_ok(""):
        raise HTTPException(404, "not found")
    action = _login_url(f"?next={html.escape(next)}" if next else "")
    return _render(action=action)


@router.get("/login/{secret}", response_class=HTMLResponse, include_in_schema=False)
async def login_page_secret(
    secret: str,
    next: str = "",
) -> HTMLResponse:
    if not _login_path_ok(secret):
        raise HTTPException(404, "not found")
    action = _login_url(f"?next={html.escape(next)}" if next else "")
    return _render(action=action)


def _trusted_forwarded_peer(request: Request) -> bool:
    """Only loopback peers may supply X-Forwarded-* identity headers."""
    host = request.client.host if request.client else ""
    try:
        return ip_address(host).is_loopback
    except ValueError:
        return False


def _forwarded_first(request: Request, header: str) -> str:
    value = request.headers.get(header, "")
    return value.split(",", 1)[0].strip()


def _request_is_https(request: Request) -> bool:
    """True if the inbound request is HTTPS — direct or behind local Caddy/nginx."""
    if _trusted_forwarded_peer(request):
        fwd = _forwarded_first(request, "x-forwarded-proto").lower()
        if fwd:
            return fwd == "https"
    return request.url.scheme == "https"


def _client_ip(request: Request) -> str:
    """Best-effort client IP for rate-limit keying.

    Only trusts ``X-Forwarded-For`` from loopback reverse proxies. Direct
    requests to :8080 can otherwise spoof the header and bypass per-IP
    login backoff.
    """
    if _trusted_forwarded_peer(request):
        # XFF is "client, proxy1, proxy2, ..." — first entry is the
        # originating client. Strip whitespace, ignore empties.
        first = _forwarded_first(request, "x-forwarded-for")
        if first:
            return first
    return request.client.host if request.client else "unknown"


async def _do_login(
    request: Request,
    username: str,
    password: str,
    next_path: str,
    secret_supplied: str,
) -> Response:
    if not _login_path_ok(secret_supplied):
        raise HTTPException(404, "not found")
    settings = get_settings()
    if not settings.admin.password:
        raise HTTPException(
            503,
            "password login not configured — see /etc/proxybox/admin.password "
            "or enable features.url_token_bypass for token-only access",
        )

    # Rate-limit BEFORE comparing credentials so timing attacks against a
    # high-fail-count IP slow down too. asyncio.sleep is cooperative, so
    # this only blocks the offender's request, not the rest of the server.
    ip = _client_ip(request)
    delay = login_rate_limit.delay_for(ip)
    if delay > 0:
        await asyncio.sleep(delay)

    user_ok = secrets.compare_digest(username.encode(), settings.admin.username.encode())
    pass_ok = secrets.compare_digest(password.encode(), settings.admin.password.encode())
    if not (user_ok and pass_ok):
        login_rate_limit.record_fail(ip)
        action = _login_url(f"?next={html.escape(next_path)}" if next_path else "")
        return _render(action=action, error="creds", status=401)

    login_rate_limit.record_success(ip)
    target = _post_login_destination(next_path, settings.admin.token)
    resp = RedirectResponse(target, status_code=303)
    resp.set_cookie(
        session_cookie_name(),
        issue_session_cookie(),
        max_age=SESSION_MAX_AGE,
        path="/",
        httponly=True,
        samesite="lax",
        # Only set Secure when actually serving over HTTPS — otherwise the
        # cookie would never be sent back over plain HTTP and the user would
        # appear unauthenticated on bare-IP installs. See _request_is_https.
        secure=_request_is_https(request),
    )
    return resp


@router.post("/login", include_in_schema=False)
async def login_submit_legacy(
    request: Request,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: str = "",
) -> Response:
    return await _do_login(
        request,
        username,
        password,
        next,
        secret_supplied="",
    )


@router.post("/login/{secret}", include_in_schema=False)
async def login_submit_secret(
    request: Request,
    secret: str,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    next: str = "",
) -> Response:
    return await _do_login(
        request,
        username,
        password,
        next,
        secret_supplied=secret,
    )


@router.post("/logout", include_in_schema=False)
async def logout() -> RedirectResponse:
    resp = RedirectResponse(_login_url(), status_code=303)
    resp.delete_cookie(session_cookie_name(), samesite="lax")
    return resp


@router.get("/logout", include_in_schema=False)
async def logout_get() -> RedirectResponse:
    return await logout()
