"""Authenticated development entry for the replacement interface."""

from __future__ import annotations

from fastapi.testclient import TestClient

from web import app as app_module


def test_ui_next_redirects_anonymous_requests_without_changing_root(
    monkeypatch,
):
    monkeypatch.setattr(app_module.guest, "verify_host_session", lambda token: False)
    client = TestClient(app_module.app)
    try:
        response = client.get("/ui-next", follow_redirects=False)
        root = client.get("/")
    finally:
        client.close()

    assert response.status_code in {302, 303, 307, 308}
    assert response.headers["location"] == "/login"
    assert root.status_code == 200
    assert 'data-ui-next-ready="true"' not in root.text


def test_ui_next_serves_only_the_static_fixture_to_a_valid_host(
    monkeypatch,
):
    monkeypatch.setattr(
        app_module.guest,
        "verify_host_session",
        lambda token: token == "valid-host-session",
    )
    client = TestClient(app_module.app)
    try:
        client.cookies.set(app_module.HOST_COOKIE, "valid-host-session")
        response = client.get("/ui-next")
    finally:
        client.close()

    assert response.status_code == 200
    assert 'data-ui-next-entry="development"' in response.text
    assert "/api/" not in response.text
    assert "Baseline Story" not in response.text
