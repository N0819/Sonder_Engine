"""The HTTP surface of scene backdrops.

backdrops.py was written and tested as a pure module; these pin the half that
faces the browser. The properties worth defending here are not "does it draw a
picture" -- that costs money and needs a provider -- but:

* reading a turn's backdrop NEVER generates one (a GET must stay free),
* the PNG route cannot be talked into serving something that isn't a backdrop,
* an unconfigured install fails loudly at the POST rather than silently
  producing nothing, and
* the settings round-trip actually reaches providers.image_model(), which is
  the only thing generation reads.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

import app as app_module
import backdrops
import guest_access as guest
from providers import image_model


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        r = c.post("/api/auth/setup",
                   json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        yield c
    guest.reset_host_account()


@pytest.fixture
def backdrop_dir(tmp_path, monkeypatch):
    """Never write into the repo's own gitignored backdrops/ during tests."""
    monkeypatch.setattr(backdrops, "BACKDROP_DIR", str(tmp_path))
    # The queue's state is module-level and keyed by signature, and every test
    # here builds the SAME scene -- so without this a failure recorded by one
    # test is still "error" for the next one, which would make these pass or
    # fail depending on the order they ran in.
    backdrops._IN_FLIGHT.clear()
    backdrops._LAST_ERROR.clear()
    return tmp_path


@pytest.fixture
def story(temp_db):
    """A chat with a persona, one turn, and a scene the player stands in."""
    pid = temp_db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        ("Hinami", json.dumps({"identity": {"name": "Hinami"}})))
    cid = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Backdrop test", pid, "", time.time()))
    tid = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 0, "look around", time.time()))
    temp_db.wset(cid, "scene", {
        "location": "USS Enterprise D",
        "time": "night",
        "rooms": {"ten_forward": {
            "name": "Ten Forward",
            "desc": "A long lounge with a curved bar and tall viewports.",
        }},
        "positions": {"Hinami": "ten_forward"},
    })
    return {"chat_id": cid, "turn_id": tid, "persona_id": pid}


def test_get_resolves_the_room_without_generating(client, story, backdrop_dir):
    r = client.get(f"/api/turns/{story['turn_id']}/backdrop")
    assert r.status_code == 200, r.text
    body = r.json()
    # Found via the persona SHEET's identity.name -> scene.positions, which is
    # the same resolution commit.py uses.
    assert body["room"] == "Ten Forward"
    # The room's identity travels beside its display name: a turn with no
    # picture of its own holds the previous one only while the reader is still
    # in the same room, and two rooms can share a name.
    assert body["room_id"] == "ten_forward"
    assert body["signature"]
    assert body["ready"] is False and body["url"] is None
    # A read is free: nothing was written, and nothing was billed.
    assert not list(backdrop_dir.rglob("*.png"))


def test_get_serves_a_cached_image_even_with_backdrops_off(
        client, story, backdrop_dir, temp_db):
    """Already-generated pictures cost nothing, so the off switch must not
    hide them -- it only stops NEW ones being commissioned."""
    sig = client.get(f"/api/turns/{story['turn_id']}/backdrop").json()["signature"]
    path = backdrop_dir / str(story["chat_id"]) / f"{sig}.png"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\x89PNG\r\n\x1a\n fake")

    body = client.get(f"/api/turns/{story['turn_id']}/backdrop").json()
    assert body["enabled"] is False          # never switched on
    assert body["ready"] is True
    assert body["url"] == f"/api/chats/{story['chat_id']}/backdrop/{sig}.png"

    img = client.get(body["url"])
    assert img.status_code == 200
    assert img.content == b"\x89PNG\r\n\x1a\n fake"
    assert img.headers["content-type"] == "image/png"


def test_a_room_with_no_player_is_not_an_error(client, story, temp_db):
    """An opening turn before anyone has been placed has nothing to depict.
    That is a legitimate empty answer, not a 500 and not a 404."""
    temp_db.wset(story["chat_id"], "scene", {"rooms": {}, "positions": {}})
    body = client.get(f"/api/turns/{story['turn_id']}/backdrop").json()
    assert body["room"] is None and body["signature"] is None
    assert body["ready"] is False


@pytest.mark.parametrize("signature", [
    "../../engine",              # the reason the route validates at all
    "..%2f..%2fengine",
    "not-hex-at-all",
    "ABCDEF0123456789abcdef01",  # uppercase is not a signature we ever mint
])
def test_png_route_refuses_anything_that_is_not_a_signature(
        client, story, signature, backdrop_dir):
    r = client.get(f"/api/chats/{story['chat_id']}/backdrop/{signature}.png")
    # 404 from the route's own hex check, or 422 when the URL layer collapsed
    # the dot-segments first and the request landed on a different route
    # entirely. Either way nothing off the backdrop tree is ever served, which
    # is the property being defended -- the signature is interpolated straight
    # into a filesystem path.
    assert r.status_code in (404, 422)


def test_png_route_404s_for_an_unknown_signature(client, story, backdrop_dir):
    r = client.get(
        f"/api/chats/{story['chat_id']}/backdrop/{'a' * 24}.png")
    assert r.status_code == 404


def test_generate_without_an_image_model_says_so(client, story, backdrop_dir):
    """Fail loudly and specifically: the whole feature is inert until this one
    setting exists, and 'nothing happened' is the worst possible symptom."""
    r = client.post(f"/api/turns/{story['turn_id']}/backdrop", json={})
    assert r.status_code == 503
    assert "image model" in r.json()["detail"].lower()


def test_missing_turn_is_404(client, backdrop_dir):
    assert client.get("/api/turns/999999/backdrop").status_code == 404
    assert client.post("/api/turns/999999/backdrop", json={}).status_code == 404


def test_image_model_round_trip_reaches_providers(client, temp_db):
    pid = temp_db.qi(
        "INSERT INTO providers(name,kind,base_url,api_key) VALUES(?,?,?,?)",
        ("nano", "nanogpt", "https://nano-gpt.com/api/v1", "k"))

    r = client.put("/api/image_model",
                   json={"provider": pid, "model": "flux-dev", "size": "1024x1024"})
    assert r.status_code == 200
    # The generator reads this and nothing else.
    assert image_model() == {"provider": pid, "model": "flux-dev",
                             "size": "1024x1024"}
    assert client.get("/api/bootstrap").json()["image_model"]["model"] == "flux-dev"

    # Clearing is how you switch the feature off at the source.
    assert client.put("/api/image_model", json={}).status_code == 200
    assert image_model() is None
    assert client.get("/api/bootstrap").json()["image_model"] is None


def test_image_model_rejects_an_unknown_provider(client):
    r = client.put("/api/image_model", json={"provider": 4242, "model": "x"})
    assert r.status_code == 404


def test_backdrops_toggle_round_trip(client):
    assert client.get("/api/bootstrap").json()["backdrops_enabled"] is False
    assert client.put("/api/backdrops", json={"enabled": True}).json()["enabled"] is True
    assert client.get("/api/bootstrap").json()["backdrops_enabled"] is True
    client.put("/api/backdrops", json={"enabled": False})
    assert client.get("/api/bootstrap").json()["backdrops_enabled"] is False


def test_backdrop_routes_are_host_only(story, backdrop_dir, temp_db):
    """Under /api/ on purpose: a StaticFiles mount would have put every room
    of every story outside the access-control middleware entirely."""
    guest.reset_host_account()
    with TestClient(app_module.app) as host:
        host.post("/api/auth/setup", json={"username": "h", "password": "pw12345"})
        sig = host.get(f"/api/turns/{story['turn_id']}/backdrop").json()["signature"]
        path = backdrop_dir / str(story["chat_id"]) / f"{sig}.png"
        path.parent.mkdir(parents=True)
        path.write_bytes(b"png")

    with TestClient(app_module.app) as anon:
        assert anon.get(f"/api/turns/{story['turn_id']}/backdrop").status_code == 401
        assert anon.get(
            f"/api/chats/{story['chat_id']}/backdrop/{sig}.png").status_code == 401
    guest.reset_host_account()


# --- the generation queue --------------------------------------------------
#
# The point of these: a route must never hold a server worker for the length of
# an image generation. The prose is already on screen; nobody is waiting.

def _configure_image_model(client, temp_db):
    pid = temp_db.qi(
        "INSERT INTO providers(name,kind,base_url,api_key) VALUES(?,?,?,?)",
        ("nano", "nanogpt", "https://nano-gpt.com/api/v1", "k"))
    r = client.put("/api/image_model", json={"provider": pid, "model": "flux"})
    assert r.status_code == 200
    return pid


def _wait_for(predicate, timeout=5.0):
    import time as _time
    deadline = _time.monotonic() + timeout
    while _time.monotonic() < deadline:
        if predicate():
            return True
        _time.sleep(0.05)
    return False


def test_generate_returns_immediately_and_finishes_in_the_background(
        client, story, backdrop_dir, temp_db, monkeypatch):
    import time as _time

    import providers
    started = []

    def slow_image(prompt, *a, **k):
        started.append(prompt)
        _time.sleep(0.6)               # stands in for tens of seconds
        return b"\x89PNG generated"

    monkeypatch.setattr(providers, "generate_image", slow_image)
    _configure_image_model(client, temp_db)

    began = _time.monotonic()
    r = client.post(f"/api/turns/{story['turn_id']}/backdrop", json={})
    elapsed = _time.monotonic() - began

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "pending"
    assert body["ready"] is False and body["url"] is None
    # The whole point: the request returned while the image was still being
    # made. A blocking route would have taken at least as long as the call.
    assert elapsed < 0.5, "the route waited for the image (%.2fs)" % elapsed

    # And the GET is pollable: pending now, ready once the worker lands.
    assert client.get(
        f"/api/turns/{story['turn_id']}/backdrop").json()["status"] == "pending"
    assert _wait_for(lambda: client.get(
        f"/api/turns/{story['turn_id']}/backdrop").json()["status"] == "ready")

    body = client.get(f"/api/turns/{story['turn_id']}/backdrop").json()
    assert body["ready"] is True
    assert client.get(body["url"]).content == b"\x89PNG generated"
    assert len(started) == 1


def test_two_requests_for_one_picture_share_a_worker(
        client, story, backdrop_dir, temp_db, monkeypatch):
    import time as _time

    import providers
    calls = []

    def slow_image(prompt, *a, **k):
        calls.append(prompt)
        _time.sleep(0.4)
        return b"\x89PNG generated"

    monkeypatch.setattr(providers, "generate_image", slow_image)
    _configure_image_model(client, temp_db)

    first = client.post(f"/api/turns/{story['turn_id']}/backdrop", json={}).json()
    second = client.post(f"/api/turns/{story['turn_id']}/backdrop", json={}).json()
    assert first["status"] == "pending" and second["status"] == "pending"
    assert _wait_for(lambda: client.get(
        f"/api/turns/{story['turn_id']}/backdrop").json()["status"] == "ready")
    assert len(calls) == 1, "paid twice for one picture"


def test_a_failed_generation_is_reported_not_swallowed(
        client, story, backdrop_dir, temp_db, monkeypatch):
    """Out-of-band work that fails silently is worse than work that fails
    loudly: the reader would sit in front of a picture that never arrives."""
    import providers

    def broken(prompt, *a, **k):
        raise RuntimeError("insufficient credit")

    monkeypatch.setattr(providers, "generate_image", broken)
    _configure_image_model(client, temp_db)

    client.post(f"/api/turns/{story['turn_id']}/backdrop", json={})
    assert _wait_for(lambda: client.get(
        f"/api/turns/{story['turn_id']}/backdrop").json()["status"] == "error")
    body = client.get(f"/api/turns/{story['turn_id']}/backdrop").json()
    assert "insufficient credit" in body["error"]
    assert body["ready"] is False


def test_asking_again_after_a_failure_retries(
        client, story, backdrop_dir, temp_db, monkeypatch):
    """The error clears when someone asks again, rather than expiring on a
    timer -- topping up credit and pressing the button should just work."""
    import providers
    attempts = []

    def flaky(prompt, *a, **k):
        attempts.append(prompt)
        if len(attempts) == 1:
            raise RuntimeError("insufficient credit")
        return b"\x89PNG generated"

    monkeypatch.setattr(providers, "generate_image", flaky)
    _configure_image_model(client, temp_db)

    client.post(f"/api/turns/{story['turn_id']}/backdrop", json={})
    assert _wait_for(lambda: client.get(
        f"/api/turns/{story['turn_id']}/backdrop").json()["status"] == "error")

    client.post(f"/api/turns/{story['turn_id']}/backdrop", json={})
    assert _wait_for(lambda: client.get(
        f"/api/turns/{story['turn_id']}/backdrop").json()["status"] == "ready")
    assert len(attempts) == 2


def test_continuity_is_off_until_explicitly_switched_on(client):
    """It changes how every picture after a room's first one is MADE, and a
    provider with a poor edit endpoint would quietly degrade every backdrop in
    the story. That is not something to discover from a default."""
    import backdrops

    assert backdrops._continuity_enabled() is False
    boot = client.get("/api/bootstrap").json()
    assert boot["backdrop_continuity"] is False

    r = client.put("/api/backdrops", json={"enabled": True, "continuity": True})
    assert r.status_code == 200, r.text
    assert r.json()["continuity"] is True
    assert backdrops._continuity_enabled() is True

    # Absent means unchanged, so the plain on/off toggle cannot silently clear it.
    client.put("/api/backdrops", json={"enabled": False})
    assert backdrops._continuity_enabled() is True

    client.put("/api/backdrops", json={"enabled": True, "continuity": False})
    assert backdrops._continuity_enabled() is False
