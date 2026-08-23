"""Authenticated application entry after replacement cutover."""

from __future__ import annotations

from fastapi.testclient import TestClient

from web import app as app_module


def test_root_redirects_anonymous_requests_and_ui_next_is_retired(
    monkeypatch,
):
    monkeypatch.setattr(app_module.guest, "verify_host_session", lambda token: False)
    client = TestClient(app_module.app)
    try:
        root = client.get("/", follow_redirects=False)
        retired = client.get("/ui-next", follow_redirects=False)
    finally:
        client.close()

    assert root.status_code in {302, 303, 307, 308}
    assert root.headers["location"] == "/login"
    assert retired.status_code == 404


def test_root_serves_only_the_static_application_to_a_valid_host(
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
        response = client.get("/")
    finally:
        client.close()

    assert response.status_code == 200
    assert 'data-ui-next-entry="application"' in response.text
    assert '/static/js/ui-next/main.js?release=alpha98-ui2-d5cf750f8b7e' in response.text
    assert "/api/" not in response.text
    assert "Baseline Story" not in response.text


def test_ui_next_lab_uses_the_same_host_only_boundary(monkeypatch):
    monkeypatch.setattr(
        app_module.guest,
        "verify_host_session",
        lambda token: token == "valid-host-session",
    )
    client = TestClient(app_module.app)
    try:
        anonymous = client.get("/ui-next/lab", follow_redirects=False)
        client.cookies.set(app_module.HOST_COOKIE, "valid-host-session")
        authenticated = client.get("/ui-next/lab")
    finally:
        client.close()

    assert anonymous.status_code in {302, 303, 307, 308}
    assert anonymous.headers["location"] == "/login"
    assert authenticated.status_code == 200
    assert 'data-ui-next-entry="component-lab"' in authenticated.text
