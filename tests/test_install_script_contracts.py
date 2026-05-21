from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = (ROOT / "deploy" / "install.sh").read_text()
DEPLOY_SKILL = (ROOT / "deploy" / "claude-skill" / "SKILL.md").read_text()


def test_installer_keeps_url_token_bypass_disabled_from_first_boot() -> None:
    assert "url_token_bypass: true" not in INSTALL_SH
    assert "url_token_bypass: false" in INSTALL_SH


def test_installer_bootstraps_first_device_with_login_session() -> None:
    assert '--data-urlencode "username=$ADMIN_USER"' in INSTALL_SH
    assert '--data-urlencode "password=$ADMIN_PASSWORD"' in INSTALL_SH
    assert '-b "$COOKIE_JAR"' in INSTALL_SH
    assert 'api_get "/api/devices/list"' in INSTALL_SH
    assert 'api_post_json "/api/devices/new"' in INSTALL_SH


def test_installer_auto_escalates_when_passwordless_sudo_is_available() -> None:
    assert 'if [ "$(id -u)" != "0" ]; then' in INSTALL_SH
    assert "sudo -n true" in INSTALL_SH
    assert "exec sudo env" in INSTALL_SH


def test_installer_preserves_existing_fail2ban_jail_local() -> None:
    assert "cat >> /etc/fail2ban/jail.local" in INSTALL_SH
    assert "cat > /etc/fail2ban/jail.local" not in INSTALL_SH


def test_deploy_skill_updates_existing_checkout_from_origin_main() -> None:
    assert "git -C /opt/proxybox fetch --prune origin main" in DEPLOY_SKILL
    assert "git -C /opt/proxybox pull --ff-only origin main" in DEPLOY_SKILL
    assert "deploy/check-prereqs.sh --lang $LANG_FLAG" in DEPLOY_SKILL
    assert "exists but is not a git checkout" in DEPLOY_SKILL
    assert "exit 1" in DEPLOY_SKILL
