"""Server delivery contracts for the authenticated replacement runtime."""

from __future__ import annotations

from fastapi.testclient import TestClient

from web import app as app_module


def _client(monkeypatch):
    monkeypatch.setattr(
        app_module.guest,
        "verify_host_session",
        lambda token: token == "valid-host-session",
    )
    return TestClient(app_module.app)


def test_runtime_harness_uses_the_host_session_boundary(monkeypatch):
    client = _client(monkeypatch)
    try:
        anonymous = client.get("/ui-next/runtime", follow_redirects=False)
        client.cookies.set(app_module.HOST_COOKIE, "valid-host-session")
        authenticated = client.get("/ui-next/runtime")
    finally:
        client.close()

    assert anonymous.status_code in {302, 303, 307, 308}
    assert anonymous.headers["location"] == "/login"
    assert authenticated.status_code == 200
    assert 'data-ui-next-entry="runtime-harness"' in authenticated.text


def test_documents_and_assets_have_coherent_cache_policy(monkeypatch):
    client = _client(monkeypatch)
    try:
        client.cookies.set(app_module.HOST_COOKIE, "valid-host-session")
        for path in ("/", "/login", "/guest", "/ui-next", "/ui-next/lab"):
            response = client.get(path)
            assert response.headers.get("cache-control") == "no-store", path

        unversioned = client.get("/static/js/ui-next/main.js")
        versioned = client.get("/static/js/ui-next/main.js?release=wp02.1")
    finally:
        client.close()

    assert unversioned.headers.get("cache-control") == "no-cache"
    assert versioned.headers.get("cache-control") == (
        "private, max-age=31536000, immutable"
    )

