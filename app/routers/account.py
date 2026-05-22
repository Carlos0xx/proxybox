"""Self-service admin-account management.

Three endpoints, all admin-gated (session cookie required), all touch
``/etc/proxybox/config.yaml`` + call ``reset_settings_cache()`` so changes
take effect in the running admin process without a self-restart:

  GET  /api/admin/account     — current username + login-path (password masked)
  POST /api/admin/account     — change username and/or password
                                 (current_password required for password change)
  POST /api/admin/login-path  — rotate login-path to a new random value
                                 (or to a user-supplied one, or clear)

These exist so a normal user can change their own credentials from the
"安全 → 登录设置" card without SSH-ing into the VPS to edit YAML.

Security:
- Password change demands the current password — protects against an
  attacker who momentarily owns the session cookie.
- Username and login-path changes only need the session (no extra gate)
  because they don't change the "secret" the user needs to log in.
"""

from __future__ import annotations

import contextlib
import os
import re
import secrets
import string
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.token import admin_auth
from app.config import get_settings, reset_settings_cache
from app.services import admin_password as _admin_password

router = APIRouter(
    prefix="/admin/{token}/api/admin",
    dependencies=[Depends(admin_auth)],
    tags=["admin-account"],
)


_USERNAME_RX = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{1,31}$")
_LOGIN_PATH_RX = re.compile(r"^[A-Za-z0-9_-]{6,64}$")
_PASSWORD_MIN = 8
_PASSWORD_MAX = 128
_LOGIN_PATH_DEFAULT_LEN = 12


def _load_config() -> tuple[Path, dict]:
    p = Path(os.environ.get("PROXYBOX_CONFIG", "/etc/proxybox/config.yaml"))
    return p, yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def _save_config(p: Path, cfg: dict) -> None:
    tmp = p.with_suffix(p.suffix + ".tmp")
    data = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, p)
        p.chmod(0o600)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise
    reset_settings_cache()


def _gen_login_path() -> str:
    alpha = string.ascii_letters + string.digits
    return "".join(secrets.choice(alpha) for _ in range(_LOGIN_PATH_DEFAULT_LEN))


# ─── current-state read ─────────────────────────────────────────────


@router.get("/account")
async def get_account() -> dict:
    s = get_settings()
    return {
        "username": s.admin.username,
        "password_set": bool(s.admin.password),
        "login_path": s.admin.login_path,
        "login_url_path": f"/login/{s.admin.login_path}" if s.admin.login_path else "/login",
    }


# ─── username + password change ─────────────────────────────────────


class AccountUpdate(BaseModel):
    username: str | None = Field(None, min_length=2, max_length=32)
    new_password: str | None = Field(None, min_length=_PASSWORD_MIN, max_length=_PASSWORD_MAX)
    current_password: str | None = None


@router.post("/account")
async def update_account(body: AccountUpdate) -> dict:
    if body.username is None and body.new_password is None:
        raise HTTPException(400, {"code": "no_change", "message": "nothing to update"})

    if body.username is not None and not _USERNAME_RX.match(body.username):
        raise HTTPException(
            400,
            {"code": "bad_username", "message": "用户名只能含字母/数字/. _ -, 2-32 字符"},
        )

    path, cfg = _load_config()
    admin = cfg.setdefault("admin", {})

    settings = get_settings()
    pw_file = settings.paths.admin_password_file
    current_pw_on_disk = settings.admin.password  # sourced from file by loader

    if body.new_password is not None:
        # Password change requires current password as a defense against
        # a stolen-cookie attacker. (Username and login-path don't grant
        # new access on their own, so they don't need this gate.)
        if not body.current_password:
            raise HTTPException(
                400,
                {"code": "current_password_required", "message": "改密码需要先输入当前密码"},
            )
        if not secrets.compare_digest(body.current_password.encode(), current_pw_on_disk.encode()):
            raise HTTPException(
                400,
                {"code": "current_password_wrong", "message": "当前密码错误"},
            )
        # Write to the sibling file (mode 0400), not the YAML. Also strip any
        # legacy plaintext that may still be in config.yaml from a v0.2.x
        # install — drift-free migration the operator gets for free on their
        # next password change.
        _admin_password.write(pw_file, body.new_password)
        if "password" in admin:
            admin.pop("password", None)

    if body.username is not None:
        admin["username"] = body.username

    _save_config(path, cfg)
    new_pw_set = bool(body.new_password) or bool(current_pw_on_disk)
    return {
        "ok": True,
        "username": admin.get("username", settings.admin.username),
        "password_set": new_pw_set,
    }


# ─── login-path rotation ────────────────────────────────────────────


class LoginPathUpdate(BaseModel):
    # None or empty string  → rotate to a fresh random value
    # Non-empty string      → use that exact value (must match _LOGIN_PATH_RX)
    # "off"                 → clear (legacy /login becomes accessible again)
    login_path: str | None = None


@router.post("/login-path")
async def rotate_login_path(body: LoginPathUpdate | None = None) -> dict:
    requested = (body.login_path if body else None) or ""
    requested = requested.strip()

    if requested == "off":
        new_path = ""
    elif requested:
        if not _LOGIN_PATH_RX.match(requested):
            raise HTTPException(
                400,
                {
                    "code": "bad_login_path",
                    "message": "登录路径只能含字母/数字/_/-, 6-64 字符",
                },
            )
        new_path = requested
    else:
        new_path = _gen_login_path()

    path, cfg = _load_config()
    cfg.setdefault("admin", {})["login_path"] = new_path
    _save_config(path, cfg)
    return {
        "ok": True,
        "login_path": new_path,
        "login_url_path": f"/login/{new_path}" if new_path else "/login",
    }
