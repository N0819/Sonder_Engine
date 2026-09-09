"""`positions` is not a body roster, at the last two sites that read it as one.

Reported from play (2026-09-08, chat 122 "The great debuging time travel
story"): "the moon the tardis and few items are being registered as attire",
and the World Browser offered each of them a station and an Attire editor.

The scene was right the whole way down -- The Moon is `kind: celestial`, The
TARDIS is `kind: vehicle`, neither is worn, neither has an attire entry --
and `story/room_slice` built its occupants from EVERY position row with no
body test at all. `_things_by_room` then excluded anything whose name matched
an occupant, so they were not merely counted as people, they were only ever
shown as people. That is review 2026-09-07 A56's own class, at the one site
the sweep missed.

Fixing it exposed the second half: `scene_names_body`'s entity tier admitted
`person` and `creature` alone, which is narrower than the engine's own
animate vocabulary. A guard, an android, a ghost and a swarm were bodies to
`llm.schemas._ANIMATE_ENTITY_KINDS` and things to the predicate written to
speak for it. The tier reads that vocabulary now, so the three spellings the
review found -- the slice's, the browser's and the ladder's -- are one.
"""
from __future__ import annotations

import pytest

from llm.schemas import _ANIMATE_ENTITY_KINDS
from world.spatial import scene_names_body


def _time_travel_scene():
    """Chat 122's shape: three people and five things, all placed."""
    return {
        "rooms": {"quay": {"name": "The Quay", "adjacent": []}},
        "positions": {
            "Hinami": "quay", "The Doctor": "quay",
            "The Station Watchkeeper": "quay",
            "The Moon": "quay", "Ocean Surf": "quay",
            "Beacon Lantern": "quay", "Cast-Iron Stove": "quay",
            "The TARDIS": "quay",
        },
        "entities": {
            "Hinami": {"kind": "person"}, "The Doctor": {"kind": "person"},
            "The Station Watchkeeper": {"kind": "person"},
            "The Moon": {"kind": "celestial"},
            "Ocean Surf": {"kind": "terrain"},
            "Beacon Lantern": {"kind": "fixture"},
            "Cast-Iron Stove": {"kind": "fixture"},
            "The TARDIS": {"kind": "vehicle"},
        },
        "attire": {}, "stations": {}, "poses": {},
    }


PEOPLE = ["Hinami", "The Doctor", "The Station Watchkeeper"]
THINGS = ["The Moon", "Ocean Surf", "Beacon Lantern", "Cast-Iron Stove",
          "The TARDIS"]


@pytest.mark.parametrize("who", PEOPLE)
def test_a_person_standing_here_is_a_body(who):
    assert scene_names_body(_time_travel_scene(), who) is True


@pytest.mark.parametrize("who", THINGS)
def test_a_thing_standing_here_is_not_a_body(who):
    assert scene_names_body(_time_travel_scene(), who) is False


def test_the_room_slice_offers_attire_to_people_only(temp_db):
    """The reported symptom, at the site that produced it."""
    import time

    from story.room_slice import room_slices

    scene = _time_travel_scene()
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Time travel", "", time.time()))
    temp_db.wset(cid, "scene", scene)

    slices = room_slices(cid, None, ["quay"], scene=scene)
    quay = next(s for s in slices if s["id"] == "quay")
    occupants = sorted(o["name"] for o in quay["occupants"])
    assert occupants == sorted(PEOPLE), occupants

    # ...and they are not lost between the two lists: a thing is a thing.
    things = sorted(t["name"] for t in quay["things"])
    for name in THINGS:
        assert name in things, (name, things)


def test_the_browser_and_the_engine_answer_alike(temp_db):
    """Three spellings of one question is what A56 was about; the browser's
    was the third and it is now the shared one."""
    from web.world_routes import _is_body

    scene = _time_travel_scene()
    for who in PEOPLE + THINGS:
        assert _is_body(scene, who) is scene_names_body(scene, who), who


@pytest.mark.parametrize("kind", ["guard", "android", "ghost", "swarm",
                                  "humanoid", "drone"])
def test_the_entity_tier_speaks_the_engines_animate_vocabulary(kind):
    """The narrowing the fix exposed: these are bodies to the schema's own
    closed set, and were things to the predicate written to speak for it."""
    assert kind in _ANIMATE_ENTITY_KINDS
    scene = {"rooms": {"r": {}}, "positions": {"X": "r"},
             "entities": {"X": {"kind": kind}}}
    assert scene_names_body(scene, "X") is True


def test_a_dressed_box_is_still_a_body():
    """The ladder's order, unchanged and worth pinning: a body LEDGER row is
    read before the entity record, so a subject the scene dresses is a body
    whatever its record calls it."""
    scene = {"rooms": {"r": {}}, "positions": {"X": "r"},
             "entities": {"X": {"kind": "container"}},
             "attire": {"X": {"wearing": ["a coat"]}}}
    assert scene_names_body(scene, "X") is True


def test_unchecking_near_unchecks_it(temp_db):
    """"I can't uncheck the near checkbox" (owner, 2026-09-08).

    NEAR IS ONE FACT STORED TWICE. `normalize_scene_stations` symmetrizes on
    every merge -- if A names B, B is given A -- and nothing ever removed the
    mirror, so clearing the box on A's row wrote `near: []` and the next merge
    put B back from B's own list. The link could not be broken from either
    side. The route owns the intent, so it drops this body from the list of
    every co-located body it no longer names.
    """
    import time

    from fastapi.testclient import TestClient

    from web import app as app_module
    from web import guest_access as guest

    scene = _time_travel_scene()
    scene["stations"] = {"Hinami": {"at": None, "near": ["The Doctor"]},
                         "The Doctor": {"at": None, "near": ["Hinami"]}}
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Near", "", time.time()))
    temp_db.wset(cid, "scene", scene)

    guest.reset_host_account()
    client = TestClient(app_module.app)
    client.__enter__()
    try:
        assert client.post("/api/auth/setup",
                           json={"username": "host",
                                 "password": "pw12345"}).status_code == 200
        out = client.put(f"/api/chats/{cid}/bodies/Hinami/station",
                         json={"at": None, "near": [], "cell": None})
        assert out.status_code == 200, out.text
    finally:
        client.__exit__(None, None, None)

    stations = (temp_db.wget(cid, "scene", {}) or {}).get("stations") or {}
    assert stations["Hinami"].get("near") == []
    # The half that used to put it straight back.
    assert stations["The Doctor"].get("near") == []
