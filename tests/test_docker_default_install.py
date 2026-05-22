import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from fastapi import HTTPException

from app import bootstrap
from app.routers import actions, connections, system
from app.services import caddy, fail2ban, singbox, system_stats, watchdog

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (ROOT / "docker-compose.yml").read_text()
DOCKER_INSTALL = (ROOT / "deploy" / "docker-install.sh").read_text()
DOCKER_GUARD = (ROOT / "deploy" / "docker-guard.sh").read_text()
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
    assert "PROXYBOX_DOCKER_LOG_DIR" in COMPOSE
    assert "/var/lib/proxybox/logs" in COMPOSE
    assert "PROXYBOX_WATCHDOG_HEARTBEAT=/var/lib/proxybox/watchdog.heartbeat" in COMPOSE
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


def test_docker_install_adds_project_scoped_host_guard() -> None:
    assert "install_docker_guard" in DOCKER_INSTALL
    assert "proxybox-docker-guard-${project_name}.service" in DOCKER_INSTALL
    assert "proxybox-docker-guard-${project_name}.timer" in DOCKER_INSTALL
    assert "After=network-online.target docker.service" in DOCKER_INSTALL
    assert "OnBootSec=45s" in DOCKER_INSTALL
    assert "OnUnitActiveSec=60s" in DOCKER_INSTALL
    assert 'systemctl enable --now "$timer_name"' in DOCKER_INSTALL
    assert "Docker guard enabled:" in DOCKER_INSTALL


def test_docker_guard_only_starts_this_compose_project() -> None:
    assert 'ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"' in DOCKER_GUARD
    assert 'ENV_FILE="$ROOT_DIR/.env"' in DOCKER_GUARD
    assert 'COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"' in DOCKER_GUARD
    assert "systemctl start docker" in DOCKER_GUARD
    assert '--env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d' in DOCKER_GUARD
    assert "docker compose down" not in DOCKER_GUARD
    assert "docker volume rm" not in DOCKER_GUARD
    assert "rm -rf" not in DOCKER_GUARD
    assert "--remove-orphans" not in DOCKER_GUARD


def test_install_red_line_is_documented_for_docker_path() -> None:
    red_line = "安装红线: 不要删除、修改、覆盖或复用用户 VPS 上本次安装以外的任何文件和服务"
    scope = "即便宿主机已经存在 `/opt/proxybox` 或同名目录,也必须保留不动"

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
    assert singbox_cfg["inbounds"][1]["type"] == "hysteria2"
    assert "obfs" not in singbox_cfg["inbounds"][1]
    assert singbox_cfg["inbounds"][1]["tls"]["alpn"] == ["h3"]

    creds = bootstrap._gen_proxybox_config(pb_dir)
    proxybox_cfg = yaml.safe_load((pb_dir / "config.yaml").read_text())
    assert creds["admin_port"] == "18080"
    assert proxybox_cfg["server"]["public_host"] == "203.0.113.10"
    assert proxybox_cfg["admin"]["port"] == 18080
    assert proxybox_cfg["ports"]["vless_range"] == [11101, 11150]
    assert proxybox_cfg["ports"]["hy2_range"] == [22101, 22150]
    assert proxybox_cfg["clash"]["api_url"] == "http://sing-box:19090"
    assert "proxybox-watchdog" in proxybox_cfg["services"]["monitored"]


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


def test_docker_admin_entrypoint_starts_watchdog() -> None:
    entrypoint = (ROOT / "deploy" / "docker" / "admin-entrypoint.sh").read_text()

    assert "python -m app.services.watchdog" in entrypoint
    assert "watchdog_pid" in entrypoint


def test_watchdog_recovers_failed_docker_ports_and_worker(
    monkeypatch,
    tmp_path: Path,
) -> None:
    reload_flag = tmp_path / "sing-box" / "reload.flag"
    worker_flag = tmp_path / "traffic-worker.restart"
    watchdog_heartbeat = tmp_path / "watchdog.heartbeat"
    settings = SimpleNamespace(
        services=SimpleNamespace(monitored=["proxybox-traffic-worker", "proxybox-watchdog"])
    )

    monkeypatch.setenv("PROXYBOX_RUNTIME", "docker")
    monkeypatch.setenv("PROXYBOX_SINGBOX_RELOAD_FILE", str(reload_flag))
    monkeypatch.setenv("PROXYBOX_WORKER_RESTART_FILE", str(worker_flag))
    monkeypatch.setenv("PROXYBOX_WATCHDOG_HEARTBEAT", str(watchdog_heartbeat))
    monkeypatch.setenv("PROXYBOX_WATCHDOG_COOLDOWN", "1")
    monkeypatch.setattr(
        watchdog.system_stats,
        "systemctl_is_active",
        lambda unit: (
            "failed" if unit in {"proxybox-traffic-worker", "proxybox-watchdog"} else "active"
        ),
    )
    monkeypatch.setattr(
        watchdog.system_stats,
        "project_port_statuses",
        lambda _settings: [
            {"owner": "sing-box", "status": "failed"},
            {"owner": "proxybox-admin", "status": "active"},
        ],
    )

    actions = watchdog.check_once(settings=settings, cooldowns={}, now=100.0)

    assert {"service": "sing-box", "action": "reload_requested"} in actions
    assert {"service": "proxybox-traffic-worker", "action": "restart_requested"} in actions
    assert {"service": "proxybox-watchdog", "action": "heartbeat_refreshed"} in actions
    assert reload_flag.exists()
    assert worker_flag.exists()
    assert watchdog_heartbeat.exists()


def test_watchdog_restarts_native_monitored_owner(monkeypatch) -> None:
    calls: list[list[str]] = []
    settings = SimpleNamespace(services=SimpleNamespace(monitored=["sing-box"]))

    monkeypatch.delenv("PROXYBOX_RUNTIME", raising=False)
    monkeypatch.setattr(watchdog.shell, "run", lambda cmd, timeout=8: calls.append(cmd) or "")

    result = watchdog.recover_owner("sing-box", settings=settings)

    assert result == {"service": "sing-box", "action": "restart_requested"}
    assert calls == [["systemctl", "restart", "--no-block", "sing-box"]]


def test_docker_status_uses_internal_runtime_probes(monkeypatch, tmp_path: Path) -> None:
    heartbeat = tmp_path / "traffic-worker.heartbeat"
    watchdog_heartbeat = tmp_path / "watchdog.heartbeat"
    heartbeat.write_text("ok")
    watchdog_heartbeat.write_text("ok")
    monkeypatch.setenv("PROXYBOX_RUNTIME", "docker")
    monkeypatch.setenv("PROXYBOX_TRAFFIC_HEARTBEAT", str(heartbeat))
    monkeypatch.setenv("PROXYBOX_WATCHDOG_HEARTBEAT", str(watchdog_heartbeat))

    assert system_stats.systemctl_is_active("proxybox-admin") == "active"
    assert system_stats.systemctl_is_active("proxybox-traffic-worker") == "active"
    assert system_stats.systemctl_is_active("proxybox-watchdog") == "active"


def test_project_port_statuses_include_native_service_ports(monkeypatch, tmp_path: Path) -> None:
    singbox_config = tmp_path / "sing-box.json"
    singbox_config.write_text(
        json.dumps(
            {
                "inbounds": [
                    {"type": "vless", "tag": "vless-template", "listen_port": 11100},
                    {"type": "vless", "tag": "vless-phone", "listen_port": 11101},
                    {"type": "hysteria2", "tag": "hy2-phone", "listen_port": 22101},
                ]
            }
        )
    )
    settings = SimpleNamespace(
        admin=SimpleNamespace(port=18080),
        clash=SimpleNamespace(api_url="http://127.0.0.1:19090"),
        paths=SimpleNamespace(singbox_config=singbox_config),
        services=SimpleNamespace(monitored=[]),
    )
    monkeypatch.delenv("PROXYBOX_RUNTIME", raising=False)
    monkeypatch.setattr(
        system_stats,
        "_port_listening_state",
        lambda proto, port: "failed" if (proto, port) == ("udp", 22101) else "active",
    )
    monkeypatch.setattr(system_stats, "_tcp_connect_state", lambda _host, _port: "active")

    rows = system_stats.project_port_statuses(settings)
    by_label = {row["label"]: row for row in rows}

    assert by_label["Admin UI"]["port"] == 18080
    assert by_label["Clash API"]["port"] == 19090
    assert by_label["VLESS 模板"]["status"] == "active"
    assert by_label["VLESS · phone"]["proto"] == "tcp"
    assert by_label["Hy2 · phone"]["proto"] == "udp"
    assert by_label["Hy2 · phone"]["status"] == "failed"


def test_docker_project_port_statuses_use_internal_service_health(
    monkeypatch,
    tmp_path: Path,
) -> None:
    singbox_config = tmp_path / "sing-box.json"
    singbox_config.write_text(
        json.dumps(
            {
                "inbounds": [
                    {"type": "vless", "tag": "vless-template", "listen_port": 12000},
                    {"type": "hysteria2", "tag": "hy2-template", "listen_port": 22000},
                ]
            }
        )
    )
    settings = SimpleNamespace(
        admin=SimpleNamespace(port=18080),
        clash=SimpleNamespace(api_url="http://sing-box:19090"),
        paths=SimpleNamespace(singbox_config=singbox_config),
        services=SimpleNamespace(monitored=["sing-box", "proxybox-admin"]),
    )
    monkeypatch.setenv("PROXYBOX_RUNTIME", "docker")
    monkeypatch.setattr(system_stats, "_clash_api_state", lambda: "active")
    monkeypatch.setattr(
        system_stats,
        "systemctl_is_active",
        lambda unit: "active" if unit in {"sing-box", "proxybox-admin"} else "unknown",
    )

    rows = system_stats.project_port_statuses(settings)
    by_label = {row["label"]: row for row in rows}

    assert by_label["Admin UI"]["status"] == "active"
    assert by_label["Clash API"]["host"] == "sing-box"
    assert by_label["VLESS 模板"]["host"] == "sing-box"
    assert by_label["Hy2 模板"]["status"] == "active"


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
