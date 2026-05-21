import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import HTTPException

from app import bootstrap
from app.routers import actions, connections, system
from app.services import caddy, fail2ban, singbox, system_stats

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (ROOT / "docker-compose.yml").read_text()
DOCKER_INSTALL = (ROOT / "deploy" / "docker-install.sh").read_text()
README_ZH = (ROOT / "README.zh.md").read_text()
DOCKER_DOC = (ROOT / "docs" / "deploy" / "docker.md").read_text()
STATIC_HTML = (ROOT / "static" / "index.html").read_text()


def test_compose_uses_bridge_network_and_env_published_ports() -> None:
    assert "network_mode: host" not in COMPOSE
    assert "proxybox-net:" in COMPOSE
    assert "driver: bridge" in COMPOSE
    assert "deploy/docker/singbox.Dockerfile" in COMPOSE
    assert "${PROXYBOX_ADMIN_BIND:-0.0.0.0}:${PROXYBOX_ADMIN_PORT:-8080}:8080/tcp" in COMPOSE
    assert "${PROXYBOX_VLESS_START:-11001}-${PROXYBOX_VLESS_END:-11050}" in COMPOSE
    assert "${PROXYBOX_HY2_START:-21001}-${PROXYBOX_HY2_END:-21050}" in COMPOSE
    assert "${PROXYBOX_IMAGE:-proxybox:local}" in COMPOSE
    assert "${PROXYBOX_SINGBOX_IMAGE:-proxybox-sing-box:local}" in COMPOSE
    assert "proxybox-data:/var/lib/proxybox" in COMPOSE
    assert "/opt/proxybox/deploy/docker/admin-entrypoint.sh" in COMPOSE
    assert "PROXYBOX_DOCKER_LOG_DIR=/var/lib/proxybox/logs" in COMPOSE
    assert "/etc/proxybox/bot.env" not in COMPOSE


def test_docker_install_provisions_runtime_and_scans_ports() -> None:
    assert "ensure_docker_runtime" in DOCKER_INSTALL
    assert "install_docker_packages" in DOCKER_INSTALL
    assert "iproute2" in DOCKER_INSTALL
    assert "ensure_port_scanner" in DOCKER_INSTALL
    assert "docker.io" in DOCKER_INSTALL
    assert "docker-compose-plugin" in DOCKER_INSTALL
    assert "docker-compose-v2" in DOCKER_INSTALL
    assert "docker-compose" in DOCKER_INSTALL
    assert "systemctl enable --now docker" in DOCKER_INSTALL
    assert "service docker start" in DOCKER_INSTALL
    assert "docker info" in DOCKER_INSTALL
    assert "sport = :$port" in DOCKER_INSTALL
    assert "selected ports:" in DOCKER_INSTALL
    assert "choose_admin_port" in DOCKER_INSTALL
    assert "choose_block tcp" in DOCKER_INSTALL
    assert "choose_block udp" in DOCKER_INSTALL
    assert "bootstrap_first_device" in DOCKER_INSTALL
    assert "PROXYBOX_FIRST_DEVICE" in DOCKER_INSTALL
    assert "COMPOSE_PROJECT_NAME=" in DOCKER_INSTALL
    assert "PROXYBOX_IMAGE=proxybox:${project_name}" in DOCKER_INSTALL
    assert "PROXYBOX_SINGBOX_IMAGE=proxybox-sing-box:${project_name}" in DOCKER_INSTALL
    assert "PROXYBOX_UPGRADE" in DOCKER_INSTALL
    assert "PROXYBOX_REWRITE_ENV" not in DOCKER_INSTALL
    assert "network_mode" not in DOCKER_INSTALL
    assert "systemctl restart" not in DOCKER_INSTALL
    assert "docker compose down" not in DOCKER_INSTALL
    assert "docker volume rm" not in DOCKER_INSTALL
    assert "rm -rf" not in DOCKER_INSTALL


def test_install_red_line_is_documented_for_docker_path() -> None:
    red_line = "安装红线: 不要删除用户 VPS 上任何文件和服务"
    scope = "绝不能碰本次安装以外任何用户数据、文件、服务、容器或 volume"

    assert red_line in README_ZH
    assert scope in README_ZH
    assert red_line in DOCKER_DOC
    assert scope in DOCKER_DOC


def test_bootstrap_uses_docker_env_ports(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PROXYBOX_PUBLIC_HOST", "203.0.113.10")
    monkeypatch.setenv("PROXYBOX_ADMIN_PORT", "18080")
    monkeypatch.setenv("PROXYBOX_CLASH_PORT", "19090")
    monkeypatch.setenv("PROXYBOX_VLESS_TEMPLATE_PORT", "11100")
    monkeypatch.setenv("PROXYBOX_VLESS_START", "11101")
    monkeypatch.setenv("PROXYBOX_VLESS_END", "11150")
    monkeypatch.setenv("PROXYBOX_HY2_TEMPLATE_PORT", "22100")
    monkeypatch.setenv("PROXYBOX_HY2_START", "22101")
    monkeypatch.setenv("PROXYBOX_HY2_END", "22150")
    monkeypatch.setattr(bootstrap, "_reality_keypair", lambda: ("priv", "pub"))
    monkeypatch.setattr(bootstrap, "_hy2_self_signed_cert", lambda _out, _cn: None)

    sb_dir = tmp_path / "sing-box"
    pb_dir = tmp_path / "proxybox"
    sb_dir.mkdir()
    pb_dir.mkdir()

    bootstrap._gen_singbox_config(sb_dir)
    singbox_cfg = json.loads((sb_dir / "config.json").read_text())
    assert singbox_cfg["experimental"]["clash_api"]["external_controller"] == "0.0.0.0:19090"
    assert singbox_cfg["inbounds"][0]["listen_port"] == 11100
    assert singbox_cfg["inbounds"][1]["listen_port"] == 22100

    creds = bootstrap._gen_proxybox_config(pb_dir)
    proxybox_cfg = yaml.safe_load((pb_dir / "config.yaml").read_text())
    assert creds["admin_port"] == "18080"
    assert proxybox_cfg["server"]["public_host"] == "203.0.113.10"
    assert proxybox_cfg["admin"]["port"] == 18080
    assert proxybox_cfg["ports"]["vless_range"] == [11101, 11150]
    assert proxybox_cfg["ports"]["hy2_range"] == [22101, 22150]
    assert proxybox_cfg["clash"]["api_url"] == "http://sing-box:19090"


def test_singbox_reload_uses_docker_flag_before_systemctl(monkeypatch, tmp_path: Path) -> None:
    flag = tmp_path / "reload.flag"
    monkeypatch.setenv("PROXYBOX_SINGBOX_RELOAD_FILE", str(flag))
    monkeypatch.setattr(singbox.time, "sleep", lambda _seconds: None)

    def fail_run(*_args, **_kwargs):
        raise AssertionError("systemctl must not run in Docker reload mode")

    monkeypatch.setattr(singbox.subprocess, "run", fail_run)
    singbox.reload_singbox()
    assert flag.exists()


def test_docker_service_restart_actions_stay_inside_docker(
    monkeypatch,
    tmp_path: Path,
) -> None:
    reload_flag = tmp_path / "sing-box" / "reload.flag"
    worker_flag = tmp_path / "worker.restart"
    monitored = ["sing-box", "proxybox-traffic-worker", "caddy"]
    monkeypatch.setenv("PROXYBOX_RUNTIME", "docker")
    monkeypatch.setenv("PROXYBOX_SINGBOX_RELOAD_FILE", str(reload_flag))
    monkeypatch.setenv("PROXYBOX_WORKER_RESTART_FILE", str(worker_flag))
    monkeypatch.setattr(
        actions,
        "get_settings",
        lambda: SimpleNamespace(services=SimpleNamespace(monitored=monitored)),
    )

    def fail_shell_run(*_args, **_kwargs):
        raise AssertionError("Docker service actions must not call host systemctl")

    monkeypatch.setattr(actions.shell, "run", fail_shell_run)

    singbox_result = asyncio.run(actions.restart_service("sing-box"))
    worker_result = asyncio.run(actions.restart_service("proxybox-traffic-worker"))

    assert singbox_result == {"service": "sing-box", "action": "reload_requested"}
    assert worker_result == {
        "service": "proxybox-traffic-worker",
        "action": "restart_requested",
    }
    assert reload_flag.exists()
    assert worker_flag.exists()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(actions.restart_service("caddy"))
    assert exc.value.status_code == 501


def test_docker_status_uses_internal_runtime_probes(monkeypatch, tmp_path: Path) -> None:
    heartbeat = tmp_path / "traffic-worker.heartbeat"
    heartbeat.write_text("ok")
    monkeypatch.setenv("PROXYBOX_RUNTIME", "docker")
    monkeypatch.setenv("PROXYBOX_TRAFFIC_HEARTBEAT", str(heartbeat))

    assert system_stats.systemctl_is_active("proxybox-admin") == "active"
    assert system_stats.systemctl_is_active("proxybox-traffic-worker") == "active"


def test_connections_use_configured_clash_api(monkeypatch) -> None:
    calls: list[tuple[str, str]] = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self) -> bytes:
            return b'{"connections":[]}'

        def readline(self) -> bytes:
            return b'{"up":1,"down":2}\n'

    def fake_urlopen(req, timeout):  # noqa: ANN001
        calls.append((req.full_url, req.headers.get("Authorization", "")))
        return FakeResponse()

    monkeypatch.setattr(
        connections,
        "get_settings",
        lambda: SimpleNamespace(
            clash=SimpleNamespace(api_url="http://sing-box:19090", api_secret="secret")
        ),
    )
    monkeypatch.setattr(connections.urllib.request, "urlopen", fake_urlopen)

    assert connections._fetch_json("/connections") == {"connections": []}
    assert calls == [("http://sing-box:19090/connections", "Bearer secret")]


def test_fail2ban_status_degrades_in_docker(monkeypatch) -> None:
    monkeypatch.setenv("PROXYBOX_RUNTIME", "docker")

    status = fail2ban.jail_status()
    assert status["available"] is False
    assert status["currently_banned"] == 0
    assert status["banned"] == []

    with pytest.raises(HTTPException) as exc:
        fail2ban.ban("203.0.113.9")
    assert exc.value.status_code == 501


def test_docker_logs_read_shared_log_file(monkeypatch, tmp_path: Path) -> None:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "sing-box.log").write_text("one\ntwo\nthree\n", encoding="utf-8")
    monkeypatch.setenv("PROXYBOX_RUNTIME", "docker")
    monkeypatch.setenv("PROXYBOX_DOCKER_LOG_DIR", str(log_dir))
    monkeypatch.setattr(
        system,
        "get_settings",
        lambda: SimpleNamespace(services=SimpleNamespace(monitored=["sing-box"])),
    )

    assert asyncio.run(system.logs("sing-box", n=2)) == "two\nthree\n"


def test_https_caddy_is_explicitly_disabled_in_docker(monkeypatch) -> None:
    monkeypatch.setenv("PROXYBOX_RUNTIME", "docker")
    monkeypatch.setattr(
        caddy,
        "get_settings",
        lambda: SimpleNamespace(server=SimpleNamespace(public_host="203.0.113.10")),
    )

    status = caddy.status()
    assert status.docker_runtime is True
    assert status.caddy_installed is False
    assert "容器内安装 Caddy" in status.notes[0]

    with pytest.raises(caddy.HTTPSEnableError) as exc:
        caddy.run("proxybox.example.com")
    assert exc.value.code == "docker_unsupported"
    assert "docker_unsupported" in STATIC_HTML
