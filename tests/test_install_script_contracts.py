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


def test_installer_uses_managed_fail2ban_jail_dropin() -> None:
    assert "/etc/fail2ban/jail.d/proxybox.local" in INSTALL_SH
    assert "[sshd]" in INSTALL_SH
    assert "backend = systemd" in INSTALL_SH
    assert "cleanup_legacy_fail2ban_jail_local" in INSTALL_SH
    assert "cat > /etc/fail2ban/jail.local" not in INSTALL_SH


def test_installer_has_explicit_fresh_mode_without_touching_ssh_trust() -> None:
    assert "--fresh" in INSTALL_SH
    assert "PROXYBOX_FRESH" in INSTALL_SH
    assert 'rm -rf "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR" "$SUB_DIR"' in INSTALL_SH
    assert (
        'rm -f "$SINGBOX_DIR/config.json" "$SINGBOX_DIR/key.pem" "$SINGBOX_DIR/cert.pem"'
        in INSTALL_SH
    )
    assert "/etc/systemd/system/proxybox-admin.service" in INSTALL_SH
    assert "/etc/systemd/system/proxybox-traffic-worker.service" in INSTALL_SH
    assert "/etc/fail2ban/jail.d/proxybox-manual.conf" in INSTALL_SH
    assert "~/.ssh/known_hosts" not in INSTALL_SH


def test_installer_rewrites_managed_systemd_units() -> None:
    assert "[ ! -f /etc/systemd/system/sing-box.service ]" not in INSTALL_SH
    assert "[ ! -f /etc/systemd/system/proxybox-admin.service ]" not in INSTALL_SH
    assert 'install -m 644 "$src" "$dst"' in INSTALL_SH
    assert "systemctl restart \"$svc\"" in INSTALL_SH


def test_docker_bootstrap_supports_fresh_mode_for_named_volumes() -> None:
    assert "PROXYBOX_FRESH=${PROXYBOX_FRESH:-0}" in DOCKER_COMPOSE
    assert "proxybox-data:/var/lib/proxybox" in DOCKER_COMPOSE
    assert "proxybox-sub:/var/www/proxybox-sub" in DOCKER_COMPOSE


def test_deploy_skill_updates_existing_checkout_from_origin_main() -> None:
    assert "git -C /opt/proxybox fetch --prune origin main" in DEPLOY_SKILL
    assert "git -C /opt/proxybox pull --ff-only origin main" in DEPLOY_SKILL
    assert "docker compose version" in DEPLOY_SKILL
    assert "bash deploy/docker-install.sh" in DEPLOY_SKILL
    assert "deploy/check-prereqs.sh --install --lang $LANG_FLAG" not in DEPLOY_SKILL
    assert "deploy/install.sh --fresh --lang $LANG_FLAG" not in DEPLOY_SKILL
    assert "exists but is not a git checkout" in DEPLOY_SKILL
    assert "exit 1" in DEPLOY_SKILL


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
