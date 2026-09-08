"""A wardrobe edit lands on the key the ledger already holds for that body.

Review 2026-09-07, Section H residual of B5: the read side of the attire
ledger is deliberately case-tolerant (`attire.key_for` states the key rule
and `attire.entry_for` is how every reader asks), so a client is handed a
body's real entry under whatever spelling the row it came from used --
`world_routes.body_rows` builds its names from `positions` as well as from
the wardrobe. `PUT /api/chats/{cid}/attire` then wrote back under the
client's spelling, minting a SECOND key: one hand edit in the browser's
attire editor (`static/js/world_browser.js` saves under `body.name`) split
one dressed body into a full record and a fresh one, which is the fork
`commit_attire._heal_attire_identity_keys` repairs on the commit path.

Closed at the route, so it holds for every client of it rather than for the
one page that found it.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest

DRESSED = {
    "wearing": ["wool coat"],
    "state": [],
    "regions": {
        "torso": {"garments": [{"name": "wool coat", "state": "worn"}]},
    },
}


@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        response = c.post("/api/auth/setup",
                          json={"username": "host", "password": "pw12345"})
        assert response.status_code == 200, response.text
        yield c
    guest.reset_host_account()


@pytest.fixture
def case_variant_chat(temp_db, client):
    """A scene whose wardrobe is keyed 'hinami' while `positions` -- the row
    `body_rows` takes its name from -- spells her 'Hinami'."""
    persona = temp_db.qi(
        "INSERT INTO personas(name,sheet) VALUES(?,?)",
        ("Nathan", json.dumps({"identity": {"name": "Nathan"}})))
    cid = temp_db.qi(
        "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
        ("Forked", persona, "", time.time()))
    temp_db.wset(cid, "scene", {
        "location": "the shrine",
        "rooms": {"room_a": {"name": "Room A", "adjacent": []}},
        "positions": {"Hinami": "room_a"},
        "entities": {},
        "attire": {"hinami": json.loads(json.dumps(DRESSED))},
    })
    return cid


def _ledger(temp_db, cid):
    return (temp_db.wget(cid, "scene") or {}).get("attire") or {}


def test_an_edit_under_a_case_variant_does_not_fork_the_ledger(
        temp_db, client, case_variant_chat):
    cid = case_variant_chat
    edited = json.loads(json.dumps(DRESSED))
    edited["wearing"] = ["wool coat", "scarf"]
    edited["regions"]["torso"]["garments"].append(
        {"name": "scarf", "state": "worn"})
    response = client.put(f"/api/chats/{cid}/attire", json={"Hinami": edited})
    assert response.status_code == 200, response.text

    ledger = _ledger(temp_db, cid)
    assert list(ledger) == ["hinami"]
    assert "scarf" in ledger["hinami"]["wearing"]


def test_a_deletion_under_a_case_variant_removes_the_real_entry(
        temp_db, client, case_variant_chat):
    cid = case_variant_chat
    response = client.put(f"/api/chats/{cid}/attire", json={"Hinami": None})
    assert response.status_code == 200, response.text
    assert _ledger(temp_db, cid) == {}


def test_a_body_the_wardrobe_does_not_know_gets_its_own_entry(
        temp_db, client, case_variant_chat):
    """The complement: nothing to land on means a new key, as before."""
    cid = case_variant_chat
    response = client.put(f"/api/chats/{cid}/attire",
                          json={"Nathan": json.loads(json.dumps(DRESSED))})
    assert response.status_code == 200, response.text
    assert sorted(_ledger(temp_db, cid)) == ["Nathan", "hinami"]
