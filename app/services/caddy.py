"""UI-driven HTTPS enablement (Caddy + Let's Encrypt).

This is the Python port of ``deploy/enable-https.sh`` — same flow, callable
from the admin HTTP API so users don't need to SSH back in. The CLI script
now uses ``python -m app.services.caddy <domain>`` under the hood so the
two entry points share one implementation.

The flow, in order:
  1. validate ``domain`` is a real DNS name (no shell metachars, has a dot)
  2. resolve ``domain`` and the VPS's own public IP, compare
  3. ``apt install caddy`` from the official Cloudsmith repo (idempotent)
  4. open ports 80 + 443 in ufw/firewalld if either is active
  5. write /etc/caddy/Caddyfile (reverse-proxy to localhost:8080)
  6. patch /etc/proxybox/config.yaml: server.public_host, passkey.rp_id,
     passkey.origin
  7. reset the in-process @lru_cache settings so the running admin picks
     up the new public_host immediately (avoids needing a self-restart)
  8. systemctl reload-or-restart caddy

Docker mode never installs Caddy inside the container. Instead the admin
container writes a request file into the install-scoped host guard directory;
a host systemd .path helper applies Caddy on the host and writes a response
file back for this process to consume.

We intentionally do NOT restart proxybox-admin — restarting our own process
mid-request would kill the response we're trying to return. The cache reset
at step 7 covers the only case where it would matter.

When called from the API endpoint, ``run()`` raises ``HTTPSEnableError`` on
failure with a structured ``code`` so the SPA can show a tailored message.
"""

from __future__ import annotations

import contextlib
import os
import re
import secrets
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import yaml

from app.config import get_settings, reset_settings_cache

# ─── pre-check ──────────────────────────────────────────────────────

# domain-label: 1-63 chars, alnum + hyphen (not leading/trailing), 2+ labels
_DOMAIN_RX = re.compile(
    r"^(?=.{4,253}$)([a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,63}$"
)
_NATIVE_MANAGED_CADDY_HEADER = "# ProxyBox HTTPS"


class HTTPSEnableError(Exception):
    """Raised when any step of enablement fails. ``code`` is a short
    string the SPA pattern-matches to localize the message; ``detail`` is
    free-form (subprocess stderr, IP mismatch info, etc.)."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


# ─── status (read-only — used by /api/https/status) ─────────────────


@dataclass
class HTTPSStatus:
    caddy_installed: bool
    caddy_active: bool
    configured_domain: str | None
    public_host: str
    using_https: bool
    notes: list[str] = field(default_factory=list)
    docker_runtime: bool = False


def runtime_is_docker() -> bool:
    return os.environ.get("PROXYBOX_RUNTIME") == "docker"


def status() -> HTTPSStatus:
    s = get_settings()
    public_host = s.server.public_host or ""
    if runtime_is_docker():
        configured_domain = public_host if _DOMAIN_RX.match(public_host) else None
        helper_success = False
        guard_dir_raw = os.environ.get("PROXYBOX_DOCKER_GUARD_DIR")
        if guard_dir_raw:
            guard_dir = Path(guard_dir_raw)
            request = _safe_parse_kv_file(guard_dir / "https-request")
            response = _safe_parse_kv_file(guard_dir / "https-response")
            helper_domain = request.get("domain") or configured_domain
            if response.get("state") == "success" and helper_domain == public_host:
                configured_domain = helper_domain
                helper_success = True
        using_https = bool(
            configured_domain and configured_domain == public_host and helper_success
        )
        notes = ["Docker 模式通过本次安装的宿主机 helper 启用 HTTPS; 容器内不安装 Caddy"]
        if using_https:
            notes.append("宿主机 helper 上次执行成功; Caddy 运行状态由宿主 systemd 管理")
        return HTTPSStatus(
            caddy_installed=helper_success,
            caddy_active=helper_success,
            configured_domain=configured_domain,
            public_host=public_host,
            using_https=using_https,
            notes=notes,
            docker_runtime=True,
        )
    caddy_bin = shutil.which("caddy") is not None
    caddy_active = False
    if caddy_bin:
        rc = subprocess.run(
            ["systemctl", "is-active", "caddy"],
            capture_output=True,
            text=True,
            check=False,
        )
        caddy_active = rc.stdout.strip() == "active"
    cfg_path = Path("/etc/caddy/Caddyfile")
    configured_domain = None
    if cfg_path.exists():
        for line in cfg_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            if line.endswith("{"):
                configured_domain = line.rstrip("{").strip()
                break
    using_https = caddy_active and bool(configured_domain) and configured_domain == public_host
    notes: list[str] = []
    if not caddy_bin:
        notes.append("Caddy 未安装 — 这是干净状态, 启用 HTTPS 时会自动安装")
    elif not caddy_active:
        notes.append("Caddy 已安装但未运行 — systemctl start caddy 或重跑启用")
    return HTTPSStatus(
        caddy_installed=caddy_bin,
        caddy_active=caddy_active,
        configured_domain=configured_domain,
        public_host=public_host,
        using_https=using_https,
        notes=notes,
    )


# ─── enablement (run via API or CLI) ────────────────────────────────


def _validate_domain(domain: str) -> None:
    if not _DOMAIN_RX.match(domain):
        raise HTTPSEnableError("invalid_domain", domain)


def _public_ip() -> str:
    for url in ("https://api4.ipify.org", "https://ipv4.icanhazip.com"):
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return r.read().decode().strip()
        except (urllib.error.URLError, OSError):
            continue
    return ""


def _resolve(domain: str) -> str:
    try:
        return socket.gethostbyname(domain)
    except OSError:
        return ""


def _run(
    cmd: list[str],
    *,
    input_text: str | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        input=input_text,
        check=False,
        env={"DEBIAN_FRONTEND": "noninteractive", "PATH": "/usr/sbin:/usr/bin:/sbin:/bin"},
    )
    if check and proc.returncode != 0:
        raise HTTPSEnableError(
            "cmd_failed",
            f"{' '.join(cmd[:3])} … exit={proc.returncode}\n"
            f"stdout: {proc.stdout[:500]}\n"
            f"stderr: {proc.stderr[:500]}",
        )
    return proc


def _install_caddy() -> Literal["installed", "already"]:
    if shutil.which("caddy"):
        return "already"
    # Cloudsmith-published official Caddy stable repo for Debian/Ubuntu.
    _run(
        [
            "apt-get",
            "install",
            "-y",
            "-qq",
            "debian-keyring",
            "debian-archive-keyring",
            "apt-transport-https",
            "curl",
            "gpg",
        ]
    )
    # Add key + repo.
    key_url = "https://dl.cloudsmith.io/public/caddy/stable/gpg.key"
    repo_url = "https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt"
    keyring = "/usr/share/keyrings/caddy-stable-archive-keyring.gpg"
    with urllib.request.urlopen(key_url, timeout=15) as r:
        key_text = r.read().decode("latin-1")
    _run(
        ["gpg", "--batch", "--yes", "--dearmor", "-o", keyring],
        input_text=key_text,
    )
    with urllib.request.urlopen(repo_url, timeout=15) as r:
        Path("/etc/apt/sources.list.d/caddy-stable.list").write_bytes(r.read())
    _run(["apt-get", "update", "-qq"])
    _run(["apt-get", "install", "-y", "-qq", "caddy"])
    return "installed"


def _firewall_open() -> None:
    """Best-effort open 80 + 443 — silent if neither tool is active."""
    if shutil.which("ufw"):
        rc = subprocess.run(["ufw", "status"], capture_output=True, text=True, check=False)
        if "Status: active" in rc.stdout:
            for port in ("80/tcp", "443/tcp"):
                subprocess.run(["ufw", "allow", port], check=False, capture_output=True)
    if shutil.which("firewall-cmd"):
        rc = subprocess.run(
            ["systemctl", "is-active", "firewalld"],
            capture_output=True,
            text=True,
            check=False,
        )
        if rc.stdout.strip() == "active":
            for svc in ("http", "https"):
                subprocess.run(
                    ["firewall-cmd", f"--add-service={svc}", "--permanent"],
                    check=False,
                    capture_output=True,
                )
            subprocess.run(["firewall-cmd", "--reload"], check=False, capture_output=True)


def _write_caddyfile(domain: str) -> None:
    cfg_path = Path("/etc/caddy/Caddyfile")
    if cfg_path.exists():
        existing = cfg_path.read_text(encoding="utf-8", errors="replace")
        if (
            existing.strip()
            and _NATIVE_MANAGED_CADDY_HEADER not in existing
            and not ("/usr/share/caddy" in existing and "reverse_proxy" not in existing)
        ):
            raise HTTPSEnableError(
                "caddyfile_conflict",
                "/etc/caddy/Caddyfile already exists and is not managed by ProxyBox; "
                "refusing to overwrite user Caddy config",
            )

    body = f"""# ProxyBox HTTPS - generated by app/services/caddy.py
{domain} {{
    encode gzip zstd

    reverse_proxy 127.0.0.1:8080 {{
        header_up X-Forwarded-Proto https
        header_up X-Forwarded-Host  {{http.request.host}}
    }}
}}
"""
    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    cfg_path.write_text(body, encoding="utf-8")
    _run(["caddy", "validate", "--config", "/etc/caddy/Caddyfile"])


def _patch_config(domain: str) -> None:
    cfg_path = Path(os.environ.get("PROXYBOX_CONFIG", "/etc/proxybox/config.yaml"))
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
    cfg.setdefault("server", {})["public_host"] = domain
    pk = cfg.setdefault("passkey", {})
    pk["rp_id"] = domain
    pk["origin"] = f"https://{domain}"
    tmp = cfg_path.with_suffix(cfg_path.suffix + ".tmp")
    data = yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(data)
        os.replace(tmp, cfg_path)
        cfg_path.chmod(0o600)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise
    # Drop the in-process settings cache so the running admin picks up the
    # new public_host without needing a self-restart (which would kill the
    # very request that's running this code).
    reset_settings_cache()


def _parse_kv_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _safe_parse_kv_file(path: Path) -> dict[str, str]:
    try:
        return _parse_kv_file(path)
    except OSError:
        return {}


def _write_kv_atomic(path: Path, data: dict[str, str]) -> None:
    tmp = path.with_name(path.name + f".{secrets.token_hex(4)}.tmp")
    body = "".join(f"{key}={value}\n" for key, value in data.items())
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            tmp.unlink()
        raise


def _run_docker_host_https(domain: str) -> dict[str, str]:
    guard_dir_raw = os.environ.get("PROXYBOX_DOCKER_GUARD_DIR")
    if not guard_dir_raw:
        raise HTTPSEnableError(
            "docker_helper_unavailable",
            "PROXYBOX_DOCKER_GUARD_DIR is not configured; reinstall or upgrade the Docker helper",
        )
    guard_dir = Path(guard_dir_raw)
    request_path = guard_dir / "https-request"
    response_path = guard_dir / "https-response"
    try:
        guard_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPSEnableError("docker_helper_unavailable", str(e)) from e
    if not os.access(guard_dir, os.W_OK):
        raise HTTPSEnableError(
            "docker_helper_unavailable", f"{guard_dir} is not writable from the container"
        )

    request_id = secrets.token_urlsafe(18)
    with contextlib.suppress(FileNotFoundError):
        response_path.unlink()
    try:
        _write_kv_atomic(
            request_path,
            {
                "request_id": request_id,
                "domain": domain,
                "created_at": str(int(time.time())),
            },
        )
    except OSError as e:
        raise HTTPSEnableError("docker_helper_unavailable", str(e)) from e

    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        if response_path.exists():
            try:
                response = _parse_kv_file(response_path)
            except OSError:
                response = {}
            if response.get("request_id") == request_id:
                state = response.get("state", "")
                if state == "success":
                    return {
                        "public_ip": response.get("public_ip") or "unknown",
                        "caddy": response.get("caddy") or "unknown",
                    }
                code = response.get("code") or "docker_helper_failed"
                detail = response.get("message") or code
                raise HTTPSEnableError(code, detail)
        time.sleep(1)
    raise HTTPSEnableError(
        "docker_helper_timeout",
        "host HTTPS helper did not write https-response within 180 seconds",
    )


def _reload_caddy() -> None:
    _run(["systemctl", "enable", "--now", "caddy"])
    rc = subprocess.run(
        ["systemctl", "reload", "caddy"],
        capture_output=True,
        text=True,
        check=False,
    )
    if rc.returncode != 0:
        # reload only works when caddy is running; restart covers cold-start
        _run(["systemctl", "restart", "caddy"])


def run(domain: str) -> dict[str, str]:
    """Full enablement. Raises HTTPSEnableError on failure with a short
    ``code`` the SPA can branch on. Returns the new state on success."""
    if runtime_is_docker():
        _validate_domain(domain)
        result = _run_docker_host_https(domain)
        _patch_config(domain)
        login_path = get_settings().admin.login_path or ""
        login_url = (
            f"https://{domain}/login/{login_path}" if login_path else f"https://{domain}/login"
        )
        return {
            "domain": domain,
            "public_ip": result["public_ip"],
            "caddy": result["caddy"],
            "login_url": login_url,
        }
    _validate_domain(domain)

    vps_ip = _public_ip()
    domain_ip = _resolve(domain)
    if not domain_ip:
        raise HTTPSEnableError("dns_no_answer", f"{domain} did not resolve")
    if vps_ip and domain_ip != vps_ip:
        raise HTTPSEnableError(
            "dns_mismatch", f"{domain} → {domain_ip}, but VPS public IP = {vps_ip}"
        )

    install_result = _install_caddy()
    _firewall_open()
    _write_caddyfile(domain)
    _patch_config(domain)
    _reload_caddy()
    # _patch_config rewrites public_host + reloads the settings cache, so
    # this read sees the post-enable login_path (which is unchanged but
    # we read it explicitly rather than assuming).
    login_path = get_settings().admin.login_path or ""
    login_url = f"https://{domain}/login/{login_path}" if login_path else f"https://{domain}/login"
    return {
        "domain": domain,
        "public_ip": vps_ip or "unknown",
        "caddy": install_result,
        "login_url": login_url,
    }


# ─── CLI entry point — wired into deploy/enable-https.sh ────────────


def _cli() -> int:
    import argparse
    import sys

    p = argparse.ArgumentParser(prog="python -m app.services.caddy")
    p.add_argument("domain")
    args = p.parse_args()
    try:
        result = run(args.domain)
    except HTTPSEnableError as e:
        print(f"[error] {e.code}: {e.detail}", file=sys.stderr, flush=True)
        return 1
    print(f"[ok] HTTPS enabled for {result['domain']}", flush=True)
    print(f"     login URL: {result['login_url']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
