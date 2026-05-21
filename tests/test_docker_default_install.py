import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

from app import bootstrap
from app.services import caddy, singbox, system_stats

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = (ROOT / "docker-compose.yml").read_text()
DOCKER_INSTALL = (ROOT / "deploy" / "docker-install.sh").read_text()
STATIC_HTML = (ROOT / "static" / "index.html").read_text()


def test_compose_uses_bridge_network_and_env_published_ports() -> None:
    assert "network_mode: host" not in COMPOSE
    assert "proxybox-net:" in COMPOSE
    assert "driver: bridge" in COMPOSE
    assert "deploy/docker/singbox.Dockerfile" in COMPOSE
    assert "${PROXYBOX_ADMIN_BIND:-0.0.0.0}:${PROXYBOX_ADMIN_PORT:-8080}:8080/tcp" in COMPOSE
    assert "${PROXYBOX_VLESS_START:-11001}-${PROXYBOX_VLESS_END:-11050}" in COMPOSE
    assert "${PROXYBOX_HY2_START:-21001}-${PROXYBOX_HY2_END:-21050}" in COMPOSE
    assert "/etc/proxybox/bot.env" not in COMPOSE


def test_docker_install_scans_ports_without_host_service_changes() -> None:
    assert "choose_admin_port" in DOCKER_INSTALL
    assert "choose_block tcp" in DOCKER_INSTALL
    assert "choose_block udp" in DOCKER_INSTALL
    assert "bootstrap_first_device" in DOCKER_INSTALL
    assert "PROXYBOX_FIRST_DEVICE" in DOCKER_INSTALL
    assert "PROXYBOX_REWRITE_ENV=1" in DOCKER_INSTALL
    assert "network_mode" not in DOCKER_INSTALL
    assert "systemctl" not in DOCKER_INSTALL
    assert "apt-get" not in DOCKER_INSTALL


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


def test_docker_status_uses_internal_runtime_probes(monkeypatch, tmp_path: Path) -> None:
    heartbeat = tmp_path / "traffic-worker.heartbeat"
    heartbeat.write_text("ok")
    monkeypatch.setenv("PROXYBOX_RUNTIME", "docker")
    monkeypatch.setenv("PROXYBOX_TRAFFIC_HEARTBEAT", str(heartbeat))

    assert system_stats.systemctl_is_active("proxybox-admin") == "active"
    assert system_stats.systemctl_is_active("proxybox-traffic-worker") == "active"


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
