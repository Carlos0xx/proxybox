"""Static SPA strings that must stay aligned with backend route contracts."""

from __future__ import annotations

from pathlib import Path

STATIC_HTML = Path("static/index.html").read_text(encoding="utf-8")


def test_passkey_management_calls_token_scoped_backend_routes() -> None:
    assert "/admin/auth/" not in STATIC_HTML
    assert "pkFetch('/api/auth/passkeys')" in STATIC_HTML
    assert "pkFetch('/api/auth/webauthn/register/begin'" in STATIC_HTML
    assert "pkFetch('/api/auth/webauthn/register/complete'" in STATIC_HTML
    assert "pkFetch('/api/auth/passkeys/' + cidEnc" in STATIC_HTML
    assert "p.id_full" in STATIC_HTML
    assert "p.id_short" in STATIC_HTML


def test_admin_token_rotation_dialog_uses_returned_contract() -> None:
    assert "env_backup" not in STATIC_HTML
    assert "new URL(d.new_admin_url || d.new_url_prefix, window.location.origin)" in STATIC_HTML
    assert "window.location.href = newAdminUrl" in STATIC_HTML
    assert "3 秒后自动重启" not in STATIC_HTML
    assert "不带 token" not in STATIC_HTML


def test_sidebar_brand_uses_current_product_version_only() -> None:
    assert '<span class="brand-name">ProxyBox</span>' in STATIC_HTML
    assert '<span class="brand-sub">v1.0</span>' in STATIC_HTML
    assert "v2.0 · LOS ANGELES" not in STATIC_HTML


def test_admin_ui_is_chinese_only() -> None:
    assert 'id="lang-toggle"' not in STATIC_HTML
    assert "toggleLang" not in STATIC_HTML
    assert "proxybox-lang" not in STATIC_HTML
    assert "I18N_DICT" not in STATIC_HTML
    assert "MutationObserver" not in STATIC_HTML
    assert "document.documentElement.lang = 'zh-CN'" in STATIC_HTML
    assert "function tr(s) { return s; }" in STATIC_HTML


def test_service_restart_button_uses_css_pseudo_icon() -> None:
    assert "btn-svc-restart" in STATIC_HTML
    assert "svc-restart-icon" not in STATIC_HTML
    assert '<svg class="svc-restart-icon"' not in STATIC_HTML
    start = STATIC_HTML.index('<button class="btn btn-sm btn-warn btn-svc-restart"')
    button_fragment = STATIC_HTML[start : STATIC_HTML.index("</button>", start)]
    assert "<span" not in button_fragment
    assert "<svg" not in button_fragment
    assert "data-restart-svc=" in button_fragment
    assert "data-svc=" not in button_fragment
    assert "重启服务</button>" in STATIC_HTML
    assert ".btn-svc-restart::before" in STATIC_HTML
    assert 'content: ""' in STATIC_HTML
    assert 'background-image: url("data:image/svg+xml' in STATIC_HTML
    assert "stroke='%23ea580c'" in STATIC_HTML
    assert "min-height: 182px" in STATIC_HTML
    assert "background-size: 14px 14px" in STATIC_HTML
    assert "width: 14px" in STATIC_HTML
    assert "height: 36px" in STATIC_HTML
    assert "color: #ea580c" in STATIC_HTML
    assert "font-weight: var(--weight-medium)" in STATIC_HTML
    assert "display: flex !important" in STATIC_HTML
    assert "white-space: nowrap !important" in STATIC_HTML
    assert "writing-mode: horizontal-tb !important" in STATIC_HTML
    assert '.btn-svc-restart [class*="icon"]' in STATIC_HTML


def test_service_status_dots_do_not_clobber_restart_buttons() -> None:
    assert "$$('.svc-dot[data-svc]').forEach" in STATIC_HTML
    assert "$$('[data-svc]').forEach" not in STATIC_HTML
    assert "restartSvc(btn.dataset.restartSvc)" in STATIC_HTML


def test_services_view_renders_project_port_cards() -> None:
    assert "lastStatus?.ports" in STATIC_HTML
    assert 'id="services-grid"' in STATIC_HTML
    assert "repeat(auto-fit, minmax(280px, 1fr))" in STATIC_HTML
    assert ".services-layout" not in STATIC_HTML
    assert "Docker Guard" in STATIC_HTML
    assert "proxybox-docker-guard" in STATIC_HTML
    assert "port-card" in STATIC_HTML
    assert "监听中" in STATIC_HTML
    assert "未监听" in STATIC_HTML
    assert "项目端口" in STATIC_HTML


def test_subscription_view_only_advertises_current_recommended_links() -> None:
    assert "/shadowrocket.yaml" in STATIC_HTML
    assert "Shadowrocket 订阅链接 · 节点+规则" in STATIC_HTML
    assert "/clash.yaml" in STATIC_HTML
    assert "/merlin.yaml" in STATIC_HTML
    assert "/shadowrocket.txt" not in STATIC_HTML
    assert "/shadowrocket.conf" not in STATIC_HTML
    assert "/sub.txt" not in STATIC_HTML
    assert "Shadowrocket 双协议节点订阅" not in STATIC_HTML
    assert "规则文件 · 需先添加节点订阅" not in STATIC_HTML
    assert "URI 列表 (.txt 别名)" not in STATIC_HTML
    assert "Shadowrocket 节点订阅 · sing-box · Hiddify" not in STATIC_HTML
    assert STATIC_HTML.index("Shadowrocket 订阅链接 · 节点+规则") < STATIC_HTML.index(
        "Stash · Clash for iOS"
    )
    assert "Shadowrocket 分流订阅 (推荐)" in STATIC_HTML
    assert "shadowrocket nodes:" not in STATIC_HTML
    assert "shadowrocket rules:" not in STATIC_HTML


def test_https_error_handling_does_not_resubmit_enable_request() -> None:
    catch_start = STATIC_HTML.index("} catch (e) {", STATIC_HTML.index("_httpsEnableSubmit"))
    catch_end = STATIC_HTML.index("log.innerHTML = `> ❌ 失败", catch_start)
    catch_fragment = STATIC_HTML[catch_start:catch_end]
    assert "e.detail" in catch_fragment
    assert "fetch(`${API_BASE}/api/https/enable`" not in catch_fragment
    assert "api/https/enable" not in catch_fragment
