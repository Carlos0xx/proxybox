"""Configuration loader for ProxyBox.

Reads YAML at PROXYBOX_CONFIG (default /etc/proxybox/config.yaml), validates
through pydantic, and expands ${ENV_VAR} references for secrets that should
not live in the YAML file (e.g. admin token).
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

_ENV_PATTERN = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _expand_env(value: object) -> object:
    if isinstance(value, str):

        def repl(m: re.Match[str]) -> str:
            return os.environ.get(m.group(1), "")

        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    return value


class AdminSettings(BaseModel):
    token: str
    host: str = "0.0.0.0"
    port: int = 8080
    # username/password login (v0.1.6+). Empty password = login disabled and
    # only url_token_bypass works. install.sh generates a random password
    # at fresh-install time so the default is a working login.
    username: str = "admin"
    password: str = ""
    # v0.1.11+: random suffix on the login URL so /login itself is 404 and
    # only /login/{login_path} renders the form. Defends against bots that
    # brute-force common /login paths. Empty = legacy /login still works
    # (existing installs untouched). install.sh generates a 12-char alnum
    # value for fresh installs.
    login_path: str = ""

    @field_validator("token")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "admin.token is empty — set ADMIN_TOKEN env var or hardcode in config.yaml"
            )
        return v


class ServerSettings(BaseModel):
    public_host: str = ""


class PathsSettings(BaseModel):
    traffic_db: Path = Path("/var/lib/proxybox/traffic.db")
    static_dir: Path = Path("/opt/proxybox/static")
    sub_dir: Path = Path("/var/www/proxybox-sub")
    singbox_config: Path = Path("/etc/sing-box/config.json")
    session_secret: Path = Path("/etc/proxybox/session-secret")
    # The admin password lives in this sibling file (mode 0400, root-owned)
    # rather than inside config.yaml itself. Keeps the password out of any
    # accidental config.yaml screenshot / backup / paste, while still being
    # one ``cat`` away for SSH-style password recovery.
    admin_password_file: Path = Path("/etc/proxybox/admin.password")


class ServicesSettings(BaseModel):
    monitored: list[str] = Field(
        default_factory=lambda: [
            "sing-box",
            "caddy",
            "proxybox-admin",
            "proxybox-traffic-worker",
            "fail2ban",
        ]
    )


class PortsSettings(BaseModel):
    vless_range: tuple[int, int] = (11001, 11050)
    hy2_range: tuple[int, int] = (21001, 21050)


class ClashSettings(BaseModel):
    api_url: str = "http://127.0.0.1:9090"
    api_secret: str = ""


class WorkerSettings(BaseModel):
    poll_interval: int = 10
    retention_days: int = 7


class PasskeySettings(BaseModel):
    # WebAuthn relying-party identity. rp_id is the host portion (no scheme,
    # no port) — must match the browser-visible domain. origin is the full
    # https:// URL the SPA is served from.
    rp_id: str = ""
    rp_name: str = "ProxyBox"
    origin: str = ""


class FeaturesSettings(BaseModel):
    passkey: bool = False
    bot: bool = False
    # When false (default), every /admin/{token}/... request MUST present a
    # valid session cookie (issued by /login). When true, the URL-path token
    # alone is sufficient — useful for automation / emergency access, but
    # disabled by default because tokens leak via screenshots and browser
    # history more easily than passwords.
    url_token_bypass: bool = False


class AppConfig(BaseModel):
    admin: AdminSettings
    server: ServerSettings = Field(default_factory=ServerSettings)
    paths: PathsSettings = Field(default_factory=PathsSettings)
    services: ServicesSettings = Field(default_factory=ServicesSettings)
    ports: PortsSettings = Field(default_factory=PortsSettings)
    clash: ClashSettings = Field(default_factory=ClashSettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    passkey: PasskeySettings = Field(default_factory=PasskeySettings)
    features: FeaturesSettings = Field(default_factory=FeaturesSettings)

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> AppConfig:
        target = Path(path or os.environ.get("PROXYBOX_CONFIG", "/etc/proxybox/config.yaml"))
        if not target.exists():
            raise FileNotFoundError(
                f"config not found: {target} — see config.example.yaml in the repo"
            )
        raw = yaml.safe_load(target.read_text()) or {}
        cfg = cls.model_validate(_expand_env(raw))
        # Admin password lives in its own root-owned file, not the YAML — see
        # PathsSettings.admin_password_file. If the file is present we use it
        # and override whatever YAML may carry; if not we fall through to the
        # YAML field for back-compat with v0.2.x installs.
        from app.services.admin_password import read as _read_admin_password

        file_pw = _read_admin_password(cfg.paths.admin_password_file)
        if file_pw:
            cfg.admin.password = file_pw
        return cfg


@lru_cache(maxsize=1)
def get_settings() -> AppConfig:
    return AppConfig.load()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
