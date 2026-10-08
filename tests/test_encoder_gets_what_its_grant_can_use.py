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

A FAR ROOM THE BEAT NAMES, OR A BODY IS BOUND FOR, ARRIVES WHOLE BY THE RULES
PINNED BELOW (owner, 2026-10-08: efficiency never removes a capability). A
map entry lets the encoder name a far room and route to it, never stand a
body at its fixtures. A far room rides whole when the beat calls it by two or
more of its words in a row, by the last word of one of its spellings, or by
a name its record or the room registry keeps; when a walk under way ends
there or a doorway being crossed opens on it; and when a crowd or a courier
is heading there. Failing open, every room rides whole when the beat's
declared destination resolves to no room at all. An ordinary beat keeps its
scope: a word from the front of a name, alone, or a number puts no room in
play. That leaves some references the engine resolves on the map: "Cope's"
alone, which the resolver reads as Cope's Boatyard, is a front word.
`docs/UNBUILT_PIPELINE.md` § 1.188(e) lists what the rules still leave there.
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
# A far room the beat names, or a body is bound for, arrives whole by these
# rules: a map entry lets the encoder name a room and route to it, never
# stand a body at its fixtures.
# ---------------------------------------------------------------------------

#: The id every far-room test below adds, one doorway past the corridor's
#: end -- so past the radius by construction.
FAR = "far_room"


def _with_far_room(name, **extra):
    """The corridor with one more room past its end, holding a fixture a body
    could be stood at."""
    scene = _corridor()
    last = f"bay{HOPS + BEYOND}"
    scene["rooms"][last]["adjacent"].append({"to": FAR, "barrier": "open"})
    scene["rooms"][FAR] = {"name": name, "adjacent": [{"to": last, "barrier": "open"}],
                           "anchors": {"altar": {"desc": "a stone altar"}}, **extra}
    return scene


def _whole(payload, rid=FAR):
    return (rid in payload["rooms"]
            and bool(payload["rooms"][rid].get("anchors"))
            and rid not in (payload["world_index"].get("elsewhere") or {}))


@pytest.mark.parametrize("name, prose", [
    # The last word of the name, alone: the word the rest describe.
    ("the Bell Loft", "Mara hears boots on the ladder up to the loft."),
    ("the wreck of the Corvina", "Mara thinks of the Corvina going down."),
    # Words in a row, one of them the tail of a word of the name -- the
    # resolver's own reading of a destination spelled the way people say it.
    ("Cope's Boatyard", "Mara looks along the quay toward Cope's yard."),
])
def test_a_far_room_called_by_part_of_its_name_rides_whole(ctx, radius, name, prose):
    payload, _ = _payload(ctx, _with_far_room(name), ["positions"], prose=prose)
    assert _whole(payload)


@pytest.mark.parametrize("name, prose", [
    # A word from the front of a name, alone, names no place: measured on
    # chat 166, words like these put far rooms in play on beats that never
    # meant them.
    ("the Low Walk", "Mara keeps her voice low."),
    ("the Counting House", "Mara is counting the crates on the rack."),
    # A number tells rooms that share a name apart; it names none of them,
    # even one no other room's name carries (the bays here end at 5).
    ("the Pile Houses 7", "Mara counts 7 crates on the rack."),
])
def test_a_word_that_is_not_a_part_of_a_far_rooms_name_leaves_it_on_the_map(
        ctx, radius, name, prose):
    payload, _ = _payload(ctx, _with_far_room(name), ["positions"], prose=prose)
    assert FAR not in payload["rooms"]
    assert payload["world_index"]["elsewhere"][FAR]["name"] == name


@pytest.mark.parametrize("aliases, prose", [
    ('["the old net store", "far room"]',
     "Mara remembers mending nets in the old net store."),
    # A script without spaces: the part rule reads only the letters a to z
    # and digits (`room_name_words`), so the whole alias is the only reading.
    ('["鐘楼"]', "彼女は鐘楼へ登った。"),
])
def test_a_far_room_called_by_a_name_the_registry_keeps_rides_whole(
        ctx, radius, temp_db, aliases, prose):
    """A renamed room keeps its old names as registry aliases, and a beat
    that still calls it by one is calling that room."""
    temp_db.qi("INSERT INTO room_registry(chat_id,room_uid,name,aliases,payload) "
               "VALUES(?,?,?,?,?)",
               (ctx.chat["id"], FAR, "the Salt House", aliases, "{}"))
    payload, _ = _payload(ctx, _with_far_room("the Salt House"), ["positions"],
                          prose=prose)
    assert _whole(payload)


def test_an_alias_is_read_whole_in_a_script_without_spaces():
    """`rooms_named_in` reads an alias where it stands, bounded by its own
    script, as it reads a name; without the alias the text names nothing."""
    rooms = {"far": {"name": "the Bell Tower"}}
    text = "彼女は鐘楼へ登った。"
    assert director_prose.rooms_named_in(rooms, [text]) == set()
    assert director_prose.rooms_named_in(rooms, [text], {"far": ["鐘楼"]}) == {"far"}


def test_a_rooms_other_names_are_its_records_and_the_registrys(temp_db):
    """Both stores of a room's other names, for the rooms the scene holds
    only; a lone alias stored as a string is one name, not its letters."""
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Aliases", "", time.time()))
    for uid, aliases in (("bay1", '["the old net store"]'),
                         ("gone", '["a room the scene no longer holds"]')):
        temp_db.qi("INSERT INTO room_registry(chat_id,room_uid,name,aliases,payload) "
                   "VALUES(?,?,?,?,?)", (chat_id, uid, uid, aliases, "{}"))
    rooms = {"bay0": {"name": "Storage Bay 0", "aliases": "the cold store"},
             "bay1": {"name": "Storage Bay 1", "aliases": ["the net loft"]}}
    assert director_prose.room_aliases(chat_id, rooms) == {
        "bay0": ["the cold store"],
        "bay1": ["the net loft", "the old net store"],
    }


def test_a_beat_bound_for_a_place_that_resolves_to_no_room_sends_every_room_whole(
        ctx, radius):
    """Fail-open: the world may hold the place under a spelling nothing here
    reads, and only a whole room lets the encoder stand a body in it."""
    scene = _corridor()
    payload, _ = _payload(ctx, scene, ["positions"], prose="Mara sets off.",
                          extras={"movement": {"to_room": "the far shore",
                                               "mover": "self"}})
    assert sorted(payload["rooms"]) == sorted(scene["rooms"])
    assert all(isinstance(record, dict) for record in payload["rooms"].values())
    assert not set(payload["world_index"].get("elsewhere") or {}) & set(scene["rooms"])
    assert any("resolves to no room" in w for w in ctx.warnings)


@pytest.mark.parametrize("to_room, extras, verdict", [
    # A room the plan holds and the scene does not, by its plan id or name.
    ("chapel_annex", {"planned_elsewhere": {"chapel_annex": "the chapel annex"}}, ""),
    ("the chapel annex", {"planned_elsewhere": {"chapel_annex": "the chapel annex"}}, ""),
    # A thing to get inside.
    ("cart", {}, ""),
    # A place spelled new: that the world already holds -- where she stands,
    # so the radius around it is the radius already drawn.
    ("new:storage bay 0", {}, ""),
    # The compiler's own verdict on the declared movement.
    ("somewhere the plan keeps", {}, "planned"),
])
def test_a_beat_bound_for_a_place_the_world_has_another_way_keeps_the_scope(
        ctx, radius, to_room, extras, verdict):
    scene = _corridor()
    scene["positions"]["cart"] = "bay1"
    scene["entities"]["cart"] = {"name": "a handcart"}
    ctx.movement_status = lambda: verdict
    payload, _ = _payload(ctx, scene, ["positions"], prose="Mara sets off.",
                          extras={"movement": {"to_room": to_room, "mover": "self"},
                                  **extras})
    for rid in _far():
        assert rid not in payload["rooms"]
    assert not any("resolves to no room" in w for w in ctx.warnings)


def test_an_ordinary_beat_with_a_near_destination_keeps_the_scope(ctx, radius):
    """The destination is a centre like the room she stands in: the radius
    is drawn from both, and everything past it stays on the map."""
    payload, _ = _payload(ctx, _with_far_room("the Tide Chapel"), ["positions"],
                          prose="Mara walks on to the next bay along the spine.",
                          extras={"movement": {"to_room": "bay1", "mover": "self"}})
    past = {f"bay{k}" for k in range(1 + HOPS + 1, HOPS + 1 + BEYOND)} | {FAR}
    assert past and not past & set(payload["rooms"])
    assert past <= set(payload["world_index"]["elsewhere"])
    assert not ctx.warnings


@pytest.mark.parametrize("approach", [
    {"Ivo": {"to_room": FAR}},
    # The scene-global shape that predates per-mover records.
    {"who": "Ivo", "to_room": FAR},
])
def test_the_room_a_body_is_walking_to_rides_whole(ctx, radius, approach):
    """A walk under way is a heading, in either shape the scene keeps one."""
    scene = _with_far_room("the Tide Chapel")
    scene["positions"]["Ivo"] = "bay1"
    scene["approach"] = approach
    payload, _ = _payload(ctx, scene, ["positions"])
    assert _whole(payload)


def test_the_room_a_body_has_just_stepped_out_of_rides_whole(ctx, radius):
    """Both sides of a doorway being crossed ride whole. The body stands in
    the room it entered, so no other rule reaches the one it left. Here Ivo
    has just come through a closed door out of the far room
    (`spatial_frames.infer_threshold_crossings` records a crossing only
    through a boundary sight does not pass)."""
    scene = _with_far_room("the Tide Chapel")
    last = f"bay{HOPS + BEYOND}"
    # The one doorway between them, from both sides.
    scene["rooms"][last]["adjacent"][-1]["barrier"] = "closed_door"
    scene["rooms"][FAR]["adjacent"][0]["barrier"] = "closed_door"
    scene["positions"]["Ivo"] = last
    scene["crossings"] = {"Ivo": {"from": FAR, "to": last, "beats": 1}}
    payload, _ = _payload(ctx, scene, ["positions"])
    assert _whole(payload)


@pytest.mark.parametrize("extras", [
    {"crowds": [{"crowd_id": "crowd:1", "room": f"bay{HOPS + BEYOND}",
                 "heading": FAR}]},
    {"couriers": [{"courier_id": "courier:1", "at": "bay1", "heading": "bay2",
                   "destination": FAR}]},
])
def test_the_room_a_crowd_or_a_courier_is_heading_for_rides_whole(ctx, radius, extras):
    payload, _ = _payload(ctx, _with_far_room("the Tide Chapel"), ["positions"],
                          extras=extras)
    assert _whole(payload)


def test_the_room_a_courier_enters_next_rides_whole_though_its_route_runs_on(
        ctx, radius):
    """A courier's `heading` is the next room on its route and its
    `destination` the last one (`director_views._couriers_view`). A route
    that runs on through the far room still puts that room in play."""
    scene = _with_far_room("the Tide Chapel")
    scene["rooms"][FAR]["adjacent"].append({"to": "crypt", "barrier": "open"})
    scene["rooms"]["crypt"] = {"name": "the Crypt",
                               "adjacent": [{"to": FAR, "barrier": "open"}]}
    payload, _ = _payload(ctx, scene, ["positions"], extras={"couriers": [
        {"courier_id": "courier:1", "at": f"bay{HOPS + BEYOND}", "heading": FAR,
         "destination": "crypt"}]})
    assert _whole(payload)


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
