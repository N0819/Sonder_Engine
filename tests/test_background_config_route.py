"""The scene-manager settings need a UI surface.

alpha4.0 shipped `background_config` with no route and no UI, so `scene_life`
was only reachable by writing world KV by hand -- which is how both live demo
runs had to enable it. These pin the route that fixes that.

It lives beside dialogue_config rather than the style guide because these are
simulation dials (who gets to speak and act), the same family as
allow_npc_to_npc_dialogue. The style guide still owns how invented extras
SOUND -- blurb theming and the §3.8.1 canon licence.
"""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest
from story.scene import background_config


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
def chat_id(temp_db):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("Cfg", "", time.time()))


def test_defaults_are_off(client, chat_id):
    """An untouched chat must behave exactly as it did before alpha4.0."""
    r = client.get(f"/api/chats/{chat_id}/background_config")
    assert r.status_code == 200
    assert r.json()["scene_life"] == "off"


def test_round_trip(client, chat_id, temp_db):
    r = client.put(f"/api/chats/{chat_id}/background_config",
                   json={"scene_life": "ambient", "max_managed": 4,
                         "max_reactors": 2})
    assert r.status_code == 200
    assert r.json()["scene_life"] == "ambient"
    # And it is what the stage will actually read.
    cfg = background_config(chat_id)
    assert cfg["scene_life"] == "ambient"
    assert cfg["max_managed"] == 4
    assert cfg["max_reactors"] == 2
    assert client.get(
        f"/api/chats/{chat_id}/background_config").json()["max_managed"] == 4


@pytest.mark.parametrize("level", ["off", "ambient", "full"])
def test_every_level_accepted(client, chat_id, level):
    assert client.put(f"/api/chats/{chat_id}/background_config",
                      json={"scene_life": level}).status_code == 200


def test_unknown_level_rejected(client, chat_id):
    """A typo must not silently disable the feature or enable `full`."""
    r = client.put(f"/api/chats/{chat_id}/background_config",
                   json={"scene_life": "on"})
    assert r.status_code == 400


def test_counts_are_clamped_not_rejected(client, chat_id):
    """max_managed is hard-capped in agents/background.py; the route must not
    let the UI store a value the stage will silently ignore."""
    r = client.put(f"/api/chats/{chat_id}/background_config",
                   json={"scene_life": "full", "max_managed": 99,
                         "max_reactors": 99})
    body = r.json()
    assert body["max_managed"] == 8
    assert body["max_reactors"] == 3


def test_non_numeric_count_is_a_400(client, chat_id):
    assert client.put(f"/api/chats/{chat_id}/background_config",
                      json={"scene_life": "full",
                            "max_managed": "lots"}).status_code == 400
