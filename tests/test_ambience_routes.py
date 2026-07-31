"""The HTTP surface of room ambience.

ambience.py is tested as a pure module in test_ambience.py; these pin the half
that faces the browser. The properties worth defending here:

* reading a turn's ambience NEVER searches or downloads (a GET must stay free),
* a turn with nobody placed in a room is an empty answer, not an error, and
* nothing a client can put in the request body turns into a 500 -- the reroll
  button reached this route with a click event where a layer index belonged,
  and `int(event)` was an unhandled TypeError the browser could only report as
  "Internal Server Error".
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

import ambience
import app as app_module
import guest_access as guest


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
def story(temp_db):
    """A chat with a persona, one turn, and a scene the player stands in."""
    pid = temp_db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        ("Hinami", json.dumps({"identity": {"name": "Hinami"}})))
    cid = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Ambience test", pid, "", time.time()))
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


@pytest.fixture
def quiet_resolution(monkeypatch):
    """Record what the resolver was asked for; never search or download."""
    calls = []
    monkeypatch.setattr(ambience, "resolve_ambience",
                        lambda *a, **kw: calls.append(kw) or None)
    ambience._AMB_IN_FLIGHT.clear()
    ambience._AMB_LAST_ERROR.clear()
    return calls


def _resolved(calls, timeout=5.0):
    """The resolver runs on a background thread, so the POST returns before it
    has been called. Wait for it rather than racing it."""
    deadline = time.monotonic() + timeout
    while not calls and time.monotonic() < deadline:
        time.sleep(0.01)
    assert calls, "the resolver was never asked to do anything"
    return calls[0]


def test_get_resolves_the_room_without_searching(client, story):
    r = client.get(f"/api/turns/{story['turn_id']}/ambience")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["room"] == "Ten Forward"
    assert body["signature"]
    assert body["ready"] is False and body["url"] is None
    assert body["status"] == "absent"


def test_a_room_with_no_player_is_not_an_error(client, story, temp_db):
    """An opening beat before anyone has been placed has nothing to sound."""
    temp_db.wset(story["chat_id"], "scene", {"rooms": {}, "positions": {}})
    body = client.get(f"/api/turns/{story['turn_id']}/ambience").json()
    assert body["room"] is None and body["signature"] is None
    assert body["ready"] is False


def test_post_without_a_source_says_so(client, story, monkeypatch):
    monkeypatch.setattr(ambience, "get_setting", lambda key, default=None: None)
    r = client.post(f"/api/turns/{story['turn_id']}/ambience", json={})
    assert r.status_code == 503
    assert "source" in r.json()["detail"]


@pytest.mark.parametrize("layer", [
    {"isTrusted": True},   # a DOM click event, JSON-serialised: the real bug
    "not a number",
    [0],
    None,
])
def test_a_junk_layer_rerolls_the_mix_instead_of_500ing(
        client, story, layer, quiet_resolution, monkeypatch):
    monkeypatch.setattr(ambience, "get_setting",
                        lambda key, default=None:
                        {"ambience_source": "freesound",
                         "freesound_key": "k"}.get(key, default))
    r = client.post(f"/api/turns/{story['turn_id']}/ambience",
                    json={"reroll": True, "layer": layer})
    assert r.status_code == 200, r.text
    assert r.json()["status"] in ("pending", "ready")
    # Unparseable means "the whole mix", which is what the button asked for.
    assert _resolved(quiet_resolution)["reroll_layer"] is None


def test_a_real_layer_index_still_reaches_the_resolver(
        client, story, quiet_resolution, monkeypatch):
    monkeypatch.setattr(ambience, "get_setting",
                        lambda key, default=None:
                        {"ambience_source": "freesound",
                         "freesound_key": "k"}.get(key, default))
    r = client.post(f"/api/turns/{story['turn_id']}/ambience",
                    json={"reroll": True, "layer": 1})
    assert r.status_code == 200, r.text
    assert _resolved(quiet_resolution)["reroll_layer"] == 1


def test_a_silent_room_answers_ready_with_nothing_to_play(
        client, story, tmp_path, monkeypatch):
    """The payload for a room with no sound of its own has to say RESOLVED,
    not MISSING: `ready` true so the client crossfades to quiet and stops
    asking, no url (there is no file, and requesting one would 404), and no
    track (there is nobody to credit)."""
    monkeypatch.setattr(ambience, "AMBIENCE_DIR", str(tmp_path))
    sig = client.get(f"/api/turns/{story['turn_id']}/ambience").json()["signature"]
    ambience._write_manifest(story["chat_id"], sig, {
        "room": "Ten Forward", "layers": [], "rejected": [],
        "silent": True, "reason": "a sealed stone vault in still air",
    })

    body = client.get(f"/api/turns/{story['turn_id']}/ambience").json()
    assert body["ready"] is True
    assert body["silent"] is True
    assert body["reason"] == "a sealed stone vault in still air"
    assert body["layers"] == [] and body["url"] is None and body["track"] is None
    assert body["status"] == "ready"
    assert body["token"]                       # still moves the player


def test_a_sounding_room_is_not_marked_silent(client, story, tmp_path,
                                              monkeypatch):
    monkeypatch.setattr(ambience, "AMBIENCE_DIR", str(tmp_path))
    body = client.get(f"/api/turns/{story['turn_id']}/ambience").json()
    assert body["silent"] is False and body["reason"] == ""


def test_missing_turn_is_404(client):
    assert client.get("/api/turns/999999/ambience").status_code == 404
