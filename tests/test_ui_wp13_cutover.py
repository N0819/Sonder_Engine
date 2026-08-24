"""Default-entry and legacy-elimination contracts for WP13."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from web import app as app_module


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


def test_authenticated_root_is_the_only_product_host_entry(monkeypatch):
    monkeypatch.setattr(
        app_module.guest,
        "verify_host_session",
        lambda token: token == "valid-host-session",
    )
    client = TestClient(app_module.app)
    try:
        anonymous = client.get("/", follow_redirects=False)
        client.cookies.set(app_module.HOST_COOKIE, "valid-host-session")
        root = client.get("/")
        former_development_route = client.get("/ui-next", follow_redirects=False)
    finally:
        client.close()

    assert anonymous.status_code in {302, 303, 307, 308}
    assert anonymous.headers["location"] == "/login"
    assert root.status_code == 200
    assert 'data-ui-next-entry="application"' in root.text
    assert "/static/js/ui-next/main.js?release=alpha98-ui10-c14a4cf8dabd" in root.text
    assert "/static/js/app.js" not in root.text
    assert former_development_route.status_code == 404


def test_classic_host_files_are_deleted_after_cutover():
    retired = (
        "index.html",
        "styles.css",
        "lorebooks.css",
        "themes.css",
        "js/utils.js",
        "js/components.js",
        "js/editors.js",
        "js/lorebooks.js",
        "js/backdrops.js",
        "js/ambience.js",
        "js/weather-fx.js",
        "js/chime.js",
        "js/chat.js",
        "js/settings.js",
        "js/themes.js",
        "js/app.js",
        "js/extensions.js",
        "js/theme-init.js",
    )
    assert [path for path in retired if (STATIC / path).exists()] == []


def test_replacement_entry_has_no_classic_asset_or_private_host_dependency():
    entry = (STATIC / "ui-next.html").read_text(encoding="utf-8")
    assert "/static/styles.css" not in entry
    assert "/static/themes.css" not in entry
    assert "/api/extensions/ui.css" not in entry
    assert '<script type="module"' in entry

    replacement = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (STATIC / "js" / "ui-next").rglob("*.js")
    )
    assert "window.S =" not in replacement
    assert "window.S=" not in replacement
    assert "setInterval(" not in replacement
