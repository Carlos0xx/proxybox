import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = (ROOT / "deploy" / "install.sh").read_text()
CHECK_PREREQS_SH = (ROOT / "deploy" / "check-prereqs.sh").read_text()
DEPLOY_SKILL = (ROOT / "deploy" / "claude-skill" / "SKILL.md").read_text()
DOCKER_COMPOSE = (ROOT / "docker-compose.yml").read_text()
PYPROJECT = (ROOT / "pyproject.toml").read_text()


def test_installer_keeps_url_token_bypass_disabled_from_first_boot() -> None:
    assert "url_token_bypass: true" not in INSTALL_SH
    assert "url_token_bypass: false" in INSTALL_SH


def test_unified_installer_prompts_for_docker_or_native() -> None:
    assert "ProxyBox 安装方式选择" in INSTALL_SH
    assert "Docker 安装（推荐）" in INSTALL_SH
    assert "VPS 已经跑了其他服务、网站、面板或生产系统" in INSTALL_SH
    assert "仅建议用于干净、专用、不会跑其他生产服务的 VPS" in INSTALL_SH
    assert "必须明确选择 1 或 2" in INSTALL_SH
    assert "非交互环境不能自动选择安装方式" in INSTALL_SH
    assert "PROXYBOX_INSTALL_DEFAULT" not in INSTALL_SH
    assert "--docker" in INSTALL_SH
    assert "--native" in INSTALL_SH
    assert "PROXYBOX_INSTALL_MODE" in INSTALL_SH


def test_unified_installer_refuses_noninteractive_implicit_mode() -> None:
    proc = subprocess.run(
        ["bash", str(ROOT / "deploy" / "install.sh")],
        cwd=ROOT,
        input="",
        capture_output=True,
        text=True,
        check=False,
    )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 2
    assert "ProxyBox 安装方式选择" in combined
    assert "非交互环境不能自动选择安装方式" in combined
    assert "bash deploy/install.sh --docker" in combined
    assert "bash deploy/install.sh --native --fresh --lang zh" in combined


def test_installer_bootstraps_first_device_with_login_session() -> None:
    assert '--data-urlencode "username=$ADMIN_USER"' in INSTALL_SH
    assert '--data-urlencode "password=$ADMIN_PASSWORD"' in INSTALL_SH
    assert '-b "$COOKIE_JAR"' in INSTALL_SH
    assert 'api_get "/api/devices/list"' in INSTALL_SH
    assert 'api_post_json "/api/devices/new"' in INSTALL_SH
    assert "string.ascii_lowercase" in INSTALL_SH
    assert "for _ in range(5)" in INSTALL_SH
    assert "PROXYBOX_FIRST_DEVICE-device-1" not in INSTALL_SH
    assert "M_BOOTSTRAP_SKIP" in INSTALL_SH
    assert "local-user|@local-user|auto-user" in INSTALL_SH


def test_installer_handoff_only_prints_current_recommended_subscriptions() -> None:
    assert "/shadowrocket.txt" not in INSTALL_SH
    assert "/shadowrocket.yaml" in INSTALL_SH
    assert "/shadowrocket.conf" not in INSTALL_SH
    assert "/sub.txt" not in INSTALL_SH
    assert "Shadowrocket 双协议节点订阅" not in INSTALL_SH
    assert "Shadowrocket 订阅链接 · 节点+规则" in INSTALL_SH
    assert "Shadowrocket 节点订阅 · sing-box · Hiddify" not in INSTALL_SH
    recommended_block = INSTALL_SH.split("# Recommended", 1)[1].split("# Other formats", 1)[0]
    assert "M_SUB_SR_YAML_TAG" in recommended_block
    assert "M_SUB_CLASH_TAG" not in recommended_block
    assert "规则文件, 需先添加节点订阅" not in INSTALL_SH


def test_installer_auto_escalates_when_passwordless_sudo_is_available() -> None:
    assert 'if [ "$(id -u)" != "0" ]; then' in INSTALL_SH
    assert "sudo -n true" in INSTALL_SH
    assert "exec sudo env" in INSTALL_SH


def test_installer_provisions_python_311_for_runtime_venv() -> None:
    assert 'requires-python = ">=3.11"' in PYPROJECT
    assert 'target-version = "py311"' in PYPROJECT
    assert "PYTHON_BIN:=python3.11" in INSTALL_SH
    assert '"$PYTHON_BIN" -m venv .venv' in INSTALL_SH
    assert "python3.11 python3.11-venv" in INSTALL_SH
    assert "python3.11 python3.11-venv" in CHECK_PREREQS_SH
    assert "ppa:deadsnakes/ppa" in INSTALL_SH
    assert "ppa:deadsnakes/ppa" in CHECK_PREREQS_SH


def test_native_installer_generates_hysteria2_without_obfs() -> None:
    assert "HY2_OBFS_PW" not in INSTALL_SH
    assert '"obfs": { "type": "salamander"' not in INSTALL_SH
    assert '"alpn": ["h3"]' in INSTALL_SH


def test_installer_uses_managed_fail2ban_jail_dropin() -> None:
    assert "/etc/fail2ban/jail.d/proxybox.local" in INSTALL_SH
    assert "[sshd]" in INSTALL_SH
    assert "backend = systemd" in INSTALL_SH
    assert "cleanup_legacy_fail2ban_jail_local" in INSTALL_SH
    assert "cat > /etc/fail2ban/jail.local" not in INSTALL_SH


def test_installer_has_explicit_fresh_mode_without_touching_ssh_trust() -> None:
    assert "--fresh" in INSTALL_SH
    assert "PROXYBOX_FRESH" in INSTALL_SH
    assert "--purge-existing-proxybox" in INSTALL_SH
    assert "PROXYBOX_CONFIRM_PURGE" in INSTALL_SH
    assert "DELETE PROXYBOX" in INSTALL_SH
    assert "M_EXISTING_REFUSE" in INSTALL_SH
    assert (
        "Fresh mode: --fresh or PROXYBOX_FRESH=1 generates a new native install only" in INSTALL_SH
    )
    assert "Destructive cleanup requires --purge-existing-proxybox plus confirmation" in INSTALL_SH
    assert "/etc/systemd/system/proxybox-admin.service" in INSTALL_SH
    assert "/etc/systemd/system/proxybox-traffic-worker.service" in INSTALL_SH
    assert "/etc/fail2ban/jail.d/proxybox-manual.conf" in INSTALL_SH
    assert "~/.ssh/known_hosts" not in INSTALL_SH
    assert "Installation red line: never delete or modify user files/services outside" in INSTALL_SH


def test_installer_rewrites_managed_systemd_units() -> None:
    assert "[ ! -f /etc/systemd/system/sing-box.service ]" not in INSTALL_SH
    assert "[ ! -f /etc/systemd/system/proxybox-admin.service ]" not in INSTALL_SH
    assert 'install -m 644 "$src" "$dst"' in INSTALL_SH
    assert 'systemctl restart "$svc"' in INSTALL_SH


def test_native_installer_adds_watchdog_for_service_and_port_recovery() -> None:
    assert "/etc/systemd/system/proxybox-watchdog.service" in INSTALL_SH
    assert "python -m app.services.watchdog" in INSTALL_SH
    assert "proxybox-watchdog" in INSTALL_SH
    assert (
        "for svc in fail2ban sing-box proxybox-admin proxybox-traffic-worker proxybox-watchdog"
    ) in INSTALL_SH


def test_docker_bootstrap_supports_fresh_mode_for_named_volumes() -> None:
    assert "PROXYBOX_FRESH=${PROXYBOX_FRESH:-0}" in DOCKER_COMPOSE
    assert "proxybox-data:/var/lib/proxybox" in DOCKER_COMPOSE
    assert "proxybox-sub:/var/www/proxybox-sub" in DOCKER_COMPOSE


def test_deploy_skill_clones_new_directory_without_reusing_checkout() -> None:
    assert "REMOTE_INSTALL_DIR" in DEPLOY_SKILL
    assert 'REMOTE_INSTALL_DIR="/opt/proxybox-$(date +%Y%m%d-%H%M%S)-$RANDOM"' in DEPLOY_SKILL
    assert 'git clone https://github.com/carlos0xx/proxybox "$REMOTE_INSTALL_DIR"' in DEPLOY_SKILL
    assert "git -C /opt/proxybox" not in DEPLOY_SKILL
    assert "fetch --prune" not in DEPLOY_SKILL
    assert "pull --ff-only" not in DEPLOY_SKILL
    assert "checkout main" not in DEPLOY_SKILL
    assert "remove or move /opt/proxybox" not in DEPLOY_SKILL
    assert "PROXYBOX_UPGRADE=1" not in DEPLOY_SKILL
    assert "no reuse of an old `.env`" in DEPLOY_SKILL
    assert "existing Docker volumes" in DEPLOY_SKILL
    assert "bash deploy/install.sh --docker" in DEPLOY_SKILL
    assert "installs Docker / Compose" in DEPLOY_SKILL
    assert "proxybox-docker-https-<project>.path" in DEPLOY_SKILL
    assert ".proxybox-guard/https-request" in DEPLOY_SKILL
    assert "non-ProxyBox-managed" in DEPLOY_SKILL
    assert "deploy/check-prereqs.sh --install --lang $LANG_FLAG" not in DEPLOY_SKILL
    assert "deploy/install.sh --fresh --lang $LANG_FLAG" not in DEPLOY_SKILL
    assert "install dir already exists; refusing to touch it" in DEPLOY_SKILL
    assert "exit 1" in DEPLOY_SKILL


def test_deploy_skill_cannot_infer_install_mode_from_environment() -> None:
    assert "must stop and ask for the install mode" in DEPLOY_SKILL
    assert "before any clone or install" in DEPLOY_SKILL
    assert "Docker being installed on the VPS is not consent" in DEPLOY_SKILL
    assert "README recommending Docker is not consent" in DEPLOY_SKILL
    assert "Existing host port conflicts are not consent" in DEPLOY_SKILL
    assert "Never set" in DEPLOY_SKILL
    assert "merely because Docker is recommended or already" in DEPLOY_SKILL
    assert "Do not run any SSH, `git clone`, or installer command" in DEPLOY_SKILL


def test_deploy_skill_uses_session_local_known_hosts() -> None:
    assert "PROXYBOX_KNOWN_HOSTS" in DEPLOY_SKILL
    assert 'UserKnownHostsFile="$PROXYBOX_KNOWN_HOSTS"' in DEPLOY_SKILL
    assert "StrictHostKeyChecking=accept-new" in DEPLOY_SKILL
    assert "UpdateHostKeys=no" in DEPLOY_SKILL
    assert "LogLevel=ERROR" in DEPLOY_SKILL
    assert "trap 'rm -f \"$PROXYBOX_KNOWN_HOSTS\"'" in DEPLOY_SKILL
    assert "ssh-keyscan" not in DEPLOY_SKILL
    assert "ssh-keygen -lf" not in DEPLOY_SKILL
    assert "StrictHostKeyChecking=no" in DEPLOY_SKILL


def test_deploy_skill_enforces_vps_data_red_line() -> None:
    assert "Installation red line:" in DEPLOY_SKILL
    assert "never delete files or services on the user's VPS" in DEPLOY_SKILL
    assert "must not touch any user data, files, services, containers, or volumes" in DEPLOY_SKILL
    assert "Never update an existing checkout during an install" in DEPLOY_SKILL
