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

    @field_validator("token")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        if not v:
            raise ValueError(
                "admin.token is empty — set ADMIN_TOKEN env var or hardcode in config.yaml"
            )
        return v


class PathsSettings(BaseModel):
    traffic_db: Path = Path("/var/lib/proxybox/traffic.db")
    static_dir: Path = Path("/opt/proxybox/static")
    sub_dir: Path = Path("/var/www/proxybox-sub")
    singbox_config: Path = Path("/etc/sing-box/config.json")


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


class FeaturesSettings(BaseModel):
    passkey: bool = False
    bot: bool = False


class AppConfig(BaseModel):
    admin: AdminSettings
    paths: PathsSettings = Field(default_factory=PathsSettings)
    services: ServicesSettings = Field(default_factory=ServicesSettings)
    ports: PortsSettings = Field(default_factory=PortsSettings)
    features: FeaturesSettings = Field(default_factory=FeaturesSettings)

    @classmethod
    def load(cls, path: str | os.PathLike[str] | None = None) -> AppConfig:
        target = Path(path or os.environ.get("PROXYBOX_CONFIG", "/etc/proxybox/config.yaml"))
        if not target.exists():
            raise FileNotFoundError(
                f"config not found: {target} — see config.example.yaml in the repo"
            )
        raw = yaml.safe_load(target.read_text()) or {}
        return cls.model_validate(_expand_env(raw))


@lru_cache(maxsize=1)
def get_settings() -> AppConfig:
    return AppConfig.load()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
