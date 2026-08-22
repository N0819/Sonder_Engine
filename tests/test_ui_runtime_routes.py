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
        for path in (
            "/", "/login", "/guest", "/ui-next", "/ui-next/lab",
            "/ui-next/runtime",
        ):
            response = client.get(path)
            assert response.headers.get("cache-control") == "no-store", path

        unversioned = client.get("/static/js/ui-next/main.js")
        versioned = client.get("/static/js/ui-next/main.js?release=wp03.1")
    finally:
        client.close()

    assert unversioned.headers.get("cache-control") == "no-cache"
    assert versioned.headers.get("cache-control") == (
        "private, max-age=31536000, immutable"
    )


def test_current_runtime_routes_round_trip_under_host_auth(temp_db, monkeypatch):
    client = _client(monkeypatch)
    try:
        unauthorized = client.get("/api/bootstrap")
        client.cookies.set(app_module.HOST_COOKIE, "valid-host-session")

        boot = client.get(
            "/api/bootstrap",
            headers={"X-Sonder-Request-Id": "runtime-route-proof"},
        )
        ui = client.get("/api/ui")
        selected_language = boot.json()["ui_language"]
        changed_language = "ja" if selected_language != "ja" else "en"
        changed = client.put(
            "/api/ui-language",
            json={"language": changed_language},
        )
        restored = client.put(
            "/api/ui-language",
            json={"language": selected_language},
        )

        created = client.post(
            "/api/chats",
            json={"name": "Runtime route proof", "scenario": "A quiet room."},
        )
        chat_id = created.json()["id"]
        read = client.get(f"/api/chats/{chat_id}")
        updated = client.put(
            f"/api/chats/{chat_id}",
            json={"name": "Runtime route proof updated"},
        )
        reread = client.get(f"/api/chats/{chat_id}")
        deleted = client.delete(f"/api/chats/{chat_id}")
        missing = client.get(f"/api/chats/{chat_id}")
    finally:
        client.close()

    assert unauthorized.status_code == 401
    assert boot.status_code == 200
    assert boot.json()["ui_messages"]
    assert ui.status_code == 200
    assert ui.json()["language"] == selected_language
    assert changed.json() == {"ok": True, "language": changed_language}
    assert restored.json() == {"ok": True, "language": selected_language}
    assert created.status_code == 200
    assert read.status_code == 200
    assert updated.json() == {"ok": True}
    assert reread.json()["chat"]["name"] == "Runtime route proof updated"
    assert deleted.json() == {"ok": True}
    assert missing.status_code == 404


def test_guest_session_gets_forbidden_not_host_expiry(monkeypatch):
    monkeypatch.setattr(app_module.guest, "verify_host_session", lambda _token: False)
    monkeypatch.setattr(
        app_module.guest,
        "verify_guest_token",
        lambda token: {"chat_id": 99, "persona_id": 7} if token == "guest" else None,
    )
    client = TestClient(app_module.app)
    try:
        client.cookies.set(app_module.GUEST_COOKIE, "guest")
        response = client.get("/api/bootstrap")
    finally:
        client.close()

    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}
