"""The encoder is handed what its grant can use, and not the whole world.

Measured on chat 166 (Brackwater, 2026-10-07/08) over the kept encoder calls:

- every spatial grant carried every room's whole record -- 31-34 rooms --
  and of the 97 rooms the answers named, the 15 standing two or more
  doorways from the beat's people were each a room something stood in, a
  room heard beyond its walls, a room the account named, or the inside of a
  thing in play;
- `world_index.elsewhere` repeated the name and exits of every room the same
  payload carried whole: 3,045 of 3,045 entries, about 174k tokens a run;
- the whole town's carried-report ledger (180-191 rows) rode every call
  holding any social channel, 711k chars to 20 calls that held no channel
  that names a report, used 0 times -- while `artifact_ops`, the one
  objects-owner channel whose poster must hold a report, saw it only when a
  social channel happened to be granted beside it.

Each rule is pinned at the radius `ENCODER_ROOM_HOPS` is patched to, so the
owner may move the number without these tests moving with it.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

import agents.director as director
import agents.director_prose as director_prose


class _Ctx:
    """The little of a pipeline context the payload assembly reads."""

    def __init__(self, chat_id):
        self.chat = {"id": chat_id}
        self.turn = SimpleNamespace(frame_id=None, idx=1)
        self.warnings = []

    def add_warning(self, text):
        self.warnings.append(text)

    def declared_movement(self):
        return None


@pytest.fixture
def ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Scope", "", time.time()))
    return _Ctx(chat_id)


#: The radius every room test runs at -- small, so the corridor is short, and
#: patched, so the shipped number stays the owner's to move.
HOPS = 2
#: Rooms past the radius in the corridor: enough that "far" has members.
BEYOND = 3


def _corridor():
    """`bay0 .. bayN` in a line, Mara standing in `bay0`. Names are written
    so that no prose below names a bay by accident."""
    count = HOPS + 1 + BEYOND
    rooms = {}
    for k in range(count):
        adjacent = [{"to": f"bay{k + 1}", "barrier": "open"}] if k + 1 < count else []
        rooms[f"bay{k}"] = {
            "name": f"Storage Bay {k}",
            "desc": f"a numbered storage bay, the {k}th along the spine",
            "adjacent": adjacent,
            "anchors": {f"rack_{k}": {"desc": "a steel rack"}},
        }
    return {"rooms": rooms, "positions": {"Mara": "bay0"}, "entities": {}}


def _far():
    return [f"bay{k}" for k in range(HOPS + 1, HOPS + 1 + BEYOND)]


def _near():
    return [f"bay{k}" for k in range(HOPS + 1)]


def _payload(ctx, scene, channels, *, prose="Mara checks the rack beside her.",
             extras=None, view=None):
    index = director.causal_world_index(
        scene, here="bay0", room_ids={"bay0", "bay1"})
    model_payload = {"event_inputs": [], "identity_index": {"persona:1": "Mara"},
                     "world_index": index}
    payload = director_prose.encoder_payload(
        ctx, scene, prose, model_payload,
        view or {"player": "Mara", "cast": []}, extras or {}, channels)
    return payload, model_payload


@pytest.fixture
def radius(monkeypatch):
    monkeypatch.setattr(director_prose, "ENCODER_ROOM_HOPS", HOPS)
    return HOPS


# ---------------------------------------------------------------------------
# Rooms: whole when in play, the map entry otherwise.
# ---------------------------------------------------------------------------

def test_a_room_past_the_radius_that_nothing_puts_in_play_rides_as_its_map_entry(ctx, radius):
    payload, _ = _payload(ctx, _corridor(), ["positions"])
    assert sorted(payload["rooms"]) == sorted(_near())
    elsewhere = payload["world_index"]["elsewhere"]
    for rid in _far():
        assert rid not in payload["rooms"]
        # ...and is still on the map: a route or a reference needs no more.
        assert elsewhere[rid]["name"] == f"Storage Bay {rid[3:]}"
        assert "exits" in elsewhere[rid]
        assert "desc" not in elsewhere[rid] and "anchors" not in elsewhere[rid]


def test_a_room_the_prose_names_rides_whole_however_far(ctx, radius):
    far = _far()[-1]
    payload, _ = _payload(
        ctx, _corridor(), ["positions"],
        prose=f"A crash echoes from Storage Bay {far[3:]}, far down the spine.")
    assert far in payload["rooms"]
    assert payload["rooms"][far]["anchors"]
    assert far not in payload["world_index"].get("elsewhere", {})


def test_a_room_named_by_its_id_in_the_inputs_rides_whole(ctx, radius):
    far = _far()[0]
    scene = _corridor()
    index = director.causal_world_index(scene, here="bay0", room_ids={"bay0"})
    model_payload = {"event_inputs": [{"identity": "persona:1", "events": [
        {"event_id": "e1", "type": "action", "targets": [far]}]}],
        "identity_index": {"persona:1": "Mara"}, "world_index": index}
    payload = director_prose.encoder_payload(
        ctx, scene, "Mara turns.", model_payload,
        {"player": "Mara", "cast": []}, {}, ["positions"])
    assert far in payload["rooms"]


def test_a_room_something_stands_in_rides_whole_however_far(ctx, radius):
    scene = _corridor()
    far = _far()[1]
    scene["positions"]["coil_of_rope"] = far
    scene["entities"]["coil_of_rope"] = {"name": "a coil of rope"}
    payload, _ = _payload(ctx, scene, ["positions"])
    assert far in payload["rooms"]
    assert set(_far()) - {far} == set(_far()) - set(payload["rooms"])


def test_a_room_heard_beyond_its_walls_rides_whole(ctx, radius):
    scene = _corridor()
    far = _far()[-1]
    scene["rooms"][far]["sound"] = {"level": "loud", "detail": "a pump hammering"}
    payload, _ = _payload(ctx, scene, ["positions"])
    assert far in payload["rooms"]


def test_the_inside_of_a_thing_in_play_rides_with_the_thing(ctx, radius):
    scene = _corridor()
    scene["positions"]["cart"] = "bay1"
    scene["entities"]["cart"] = {"name": "a handcart"}
    # No edge reaches it: an inside is reached through its thing.
    scene["rooms"]["cart_bed"] = {"name": "the cart's bed", "parent_entity": "cart",
                                  "adjacent": []}
    payload, _ = _payload(ctx, scene, ["positions"])
    assert "cart_bed" in payload["rooms"]


def test_a_room_sent_whole_is_not_repeated_on_the_map(ctx, radius):
    payload, model_payload = _payload(ctx, _corridor(), ["positions"])
    elsewhere = payload["world_index"].get("elsewhere") or {}
    assert not set(elsewhere) & set(payload["rooms"])
    # The Director's own map is the model payload's, and stays whole.
    director_map = model_payload["world_index"]["elsewhere"]
    assert set(_near()[2:]) <= set(director_map)
    assert set(director_map) == set(elsewhere) | (set(director_map) & set(payload["rooms"]))


def test_without_a_spatial_grant_the_map_is_the_directors_and_rooms_are_names(ctx, radius):
    payload, model_payload = _payload(ctx, _corridor(), ["entities"])
    assert payload["world_index"] == model_payload["world_index"]
    assert all(isinstance(name, str) for name in payload["rooms"].values())


def test_a_room_scope_that_cannot_be_computed_sends_every_room_whole(ctx, radius, monkeypatch):
    def broken(*_a, **_k):
        raise RuntimeError("no graph")
    monkeypatch.setattr(director_prose, "rooms_in_play", broken)
    scene = _corridor()
    payload, _ = _payload(ctx, scene, ["positions"])
    assert sorted(payload["rooms"]) == sorted(scene["rooms"])
    assert not payload["world_index"].get("elsewhere")
    assert any("room scope unavailable" in w for w in ctx.warnings)


def test_the_room_author_is_still_handed_every_room(ctx, radius):
    scene = _corridor()
    index = director.causal_world_index(scene, here="bay0", room_ids={"bay0"})
    room_payload = director_prose._room_payload(
        ctx, scene, "Mara walks on.", {"world_index": index},
        {"player": "Mara", "cast": []}, {}, {}, {})
    assert sorted(room_payload["rooms"]) == sorted(scene["rooms"])
    assert room_payload["world_index"] == index


@pytest.mark.parametrize("rooms, text, named", [
    # A script without spaces: the name stands where it stands.
    ({"shoro": {"name": "鐘楼"}}, "彼女は鐘楼へ登った。", True),
    # A spaced script: a whole name, never the head of a longer one.
    ({"bay1": {"name": "Storage Bay 1"}}, "storage bay 10 is empty", False),
    ({"loft": {"name": "the Bell Loft"}}, "up the ladder into the bell loft", True),
    # An id in a record is the same phrase as the name in prose.
    ({"bell_loft": {"name": "the loft"}}, '{"to_room": "bell_loft"}', True),
])
def test_a_room_is_named_by_its_whole_name_in_its_own_script(rooms, text, named):
    assert bool(director_prose.rooms_named_in(rooms, [text])) is named


# ---------------------------------------------------------------------------
# Carried reports: with the channels that name a held report, as stored.
# ---------------------------------------------------------------------------

REPORTS = [
    {"who": "Mara", "world_event_id": "event:bell", "gist": "the bell rang twice",
     "retellings": 0},
    {"who": "Ivo", "world_event_id": "event:bell", "gist": "the bell rang twice",
     "retellings": 1},
    {"who": "Ivo", "world_event_id": "claim:boat", "gist": "the boat sank",
     "retellings": 2},
    {"who": "Sela", "world_event_id": "claim:boat2", "gist": "the boat sank",
     "retellings": 0},
]


@pytest.mark.parametrize("channels, rides", [
    (["telling_ops"], True),
    (["courier_ops"], True),
    # The objects owner's: no social channel beside it, and the poster
    # still has to hold what it nails up.
    (["artifact_ops"], True),
    (["crowd_ops"], False),
    (["introductions", "obligations"], False),
    (["positions", "entities"], False),
])
def test_reports_ride_only_with_a_channel_that_names_a_held_report(ctx, channels, rides):
    scene = {"rooms": {"bay0": {"name": "Storage Bay 0", "adjacent": []}},
             "positions": {"Mara": "bay0"}, "entities": {}}
    payload, _ = _payload(ctx, scene, channels,
                          extras={"carried_reports": REPORTS})
    assert ("carried_reports" in payload) is rides
    if rides:
        # As stored: the shape the chunks were written against.
        assert payload["carried_reports"] == REPORTS


def test_every_chunk_that_sends_the_encoder_to_the_reports_is_a_reader():
    """The card and the gate say one thing. A channel whose chunk tells the
    encoder its actor must hold a report in `carried_reports` is a channel the
    reports ride with -- read off the chunks themselves, so a new chunk that
    names the ledger and is not a reader fails here."""
    from pathlib import Path
    chunks = Path(director_prose.__file__).resolve().parents[1] / (
        "language_packs/en/cards/system_prompts/encoder")
    naming = {path.stem.split("__")[0] for path in chunks.glob("*.txt")
              if "carried_reports" in path.read_text(encoding="utf-8")}
    assert naming
    assert naming <= director_prose.ledger_readers("reports_carried")
    assert director_prose.ledger_readers("reports_carried") <= set(
        director_prose._RECORD_FACTS)
