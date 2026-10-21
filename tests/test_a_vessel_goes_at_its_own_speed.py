"""A vessel goes at its own speed when the story gives it one, and at a walk
only when nothing says.

Commit faba15b3 (2026-10-21) timed every journey toward a destination: a
written `eta_seconds`, else the engine's price of the way at the charter's
walking pace (`charter_move.WALK_PACES_PER_SECOND`, 1.3 paces a second),
because nothing in the world typed a vehicle's speed. So the control probe's
motor workboat, the Mary Ann, crossed the channel's thirteen kilometres in
2.8 hours, and a measured crossing of five hundred would have taken four and a
half days.

The owner's ruling, 2026-10-21: "vessels should perhaps be given speeds but
i'd rather handle it on a case by case basis rather than rigid code". So no
table of speeds by kind of craft exists anywhere: a vessel's speed is the
story's, written on the vessel's own record (`state.speed`, a `{value, unit}`
measurement in one of the engine's units) when the fiction says or makes
plain how fast it goes, and the walk prices the way only when nothing does. A
time the story states is still `eta_seconds`, and it still wins.

The scene is the probe's crossing (chat 2 idx 4), as
`test_a_journey_arrives_when_its_way_is_done` builds it.
"""

from __future__ import annotations

import copy
import json
import time

import pytest

from world.charter_move import WALK_PACES_PER_SECOND
from world.mechanics import PRICED_ARRIVAL_KEY, mechanics_sweep
from world.spatial import merge_scene_with_diff, room_span

DEPARTURE_BEAT_END = 1993.0      # chat 2 idx 4's clock at commit

UNDER_WAY = {"phase": "in_transit", "destination_room": "the_mainland",
             "route_room": "the_channel", "departed_from": "rock_landing"}

KNOT = 1852.0 / 3600.0           # metres a second


def _crossing(transit=None, speed=None):
    state = {"engine": "running",
             "transit": dict(transit if transit is not None else UNDER_WAY)}
    if speed is not None:
        state["speed"] = speed
    return {
        "rooms": {
            "rock_landing": {
                "name": "The Landing", "exposure": "open",
                "extent": {"w": 12, "d": 8},
                "adjacent": [{"to": "the_mainland", "barrier": "open_door"}]},
            "the_channel": {
                "name": "the channel", "size": "large", "floor": "water",
                "exposure": "open", "extent": {"w": 10.0, "d": 7.0},
                "adjacent": [
                    {"to": "rock_landing", "barrier": "open", "dir": "w",
                     "distance": {"value": 1.5, "unit": "km"}},
                    {"to": "the_mainland", "barrier": "open", "dir": "e",
                     "distance": {"value": 13, "unit": "km"}}]},
            "the_mainland": {
                "name": "The Mainland", "planned": True, "purpose": "",
                "adjacent": [{"to": "rock_landing", "barrier": "open_door"}]},
            "mary_ann_interior": {
                "name": "The Mary Ann", "parent_entity": "mary_ann",
                "dock_exit": True,
                "adjacent": [{"to": "the_channel", "distance": "near",
                              "barrier": "closed_door"}]},
        },
        "entities": {"mary_ann": {
            "name": "The Mary Ann", "kind": "vehicle", "container": True,
            "interior_rooms": ["mary_ann_interior"], "state": state}},
        "positions": {"mary_ann": "the_channel",
                      "Tam the deckhand": "mary_ann_interior"},
    }


def _way(scene):
    """The channel's own thirteen kilometres to the mainland plus the span
    of the channel being crossed -- the way `journey_seconds` prices."""
    return 13000.0 + room_span(scene, "the_channel")


def _sweep(scene, elapsed, pending=(), turn_id=11, turn_idx=4):
    return mechanics_sweep(scene, {"elapsed_seconds": elapsed}, None,
                           list(pending), chat_id=2, turn_id=turn_id,
                           turn_idx=turn_idx)


def _scheduled(ops):
    return [op[1] for op in ops if op[0] == "schedule"]


def _statuses(ops):
    return {op[1]: op[2] for op in ops if op[0] == "status"}


# ---------------------------------------------------------------------------
# A speed the story wrote prices the way
# ---------------------------------------------------------------------------

def test_a_vessel_with_its_own_speed_is_priced_by_it():
    from world.mechanics import PRICED_SPEED_KEY
    scene = _crossing(speed={"value": 7, "unit": "kn"})
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)

    rows = _scheduled(ops)
    assert len(rows) == 1
    pace = 7 * KNOT
    assert rows[0]["due_at"] == pytest.approx(DEPARTURE_BEAT_END + _way(scene) / pace)
    payload = json.loads(rows[0]["payload"])
    assert payload[PRICED_ARRIVAL_KEY] == pytest.approx(_way(scene) / pace, abs=0.1)
    assert payload[PRICED_SPEED_KEY] == pytest.approx(pace, abs=1e-4)
    # About an hour for a workboat at seven knots, where the walk took 2.8.
    assert 0.9 * 3600 < rows[0]["due_at"] - DEPARTURE_BEAT_END < 1.1 * 3600


def test_no_speed_is_the_walk_unchanged_and_says_so():
    """Nothing written, or nothing the engine can read as a speed, is the
    fallback the arrival always had -- and the row says the pace it was
    priced at, so a speed written later re-times it from there."""
    from world.mechanics import PRICED_SPEED_KEY
    unread = (None,                                   # nothing written
              {"value": 7, "unit": "leagues/h"},      # a unit the engine does not hold
              {"value": 7},                           # no unit
              7,                                      # a bare number
              "seven knots",                          # no number
              {"value": 0, "unit": "kn"},             # not moving
              {"value": -3, "unit": "kn"},
              {"value": True, "unit": "kn"})
    for speed in unread:
        scene = _crossing(speed=speed)
        _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
        row = _scheduled(ops)[0]
        assert row["due_at"] == pytest.approx(
            DEPARTURE_BEAT_END + _way(scene) / WALK_PACES_PER_SECOND), speed
        assert json.loads(row["payload"])[PRICED_SPEED_KEY] == pytest.approx(
            WALK_PACES_PER_SECOND), speed


def test_a_written_eta_wins_over_a_speed():
    scene = _crossing(dict(UNDER_WAY, eta_seconds=1800),
                      speed={"value": 7, "unit": "kn"})
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    rows = _scheduled(ops)
    assert len(rows) == 1 and rows[0]["due_at"] == DEPARTURE_BEAT_END + 1800
    # A written time's row is the shape it always was.
    assert json.loads(rows[0]["payload"]) == {
        "entity_id": "mary_ann", "destination_room": "the_mainland",
        "frame_id": None}

    # And a speed written after it never moves a time somebody wrote.
    written = rows[0]
    scene["entities"]["mary_ann"]["state"]["transit"].pop("eta_seconds")
    scene["entities"]["mary_ann"]["state"]["speed"] = {"value": 2, "unit": "kn"}
    _, ops, _, _ = _sweep(scene, 3000.0, [written], turn_id=12, turn_idx=5)
    assert not _scheduled(ops) and not _statuses(ops)


def test_a_time_written_after_a_speed_price_replaces_it_once():
    scene = _crossing(speed={"value": 7, "unit": "kn"})
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    priced = _scheduled(ops)[0]
    scene["entities"]["mary_ann"]["state"]["transit"]["eta_seconds"] = 600
    _, ops, _, _ = _sweep(scene, 3000.0, [priced], turn_id=12, turn_idx=5)
    assert _statuses(ops) == {priced["event_id"]: "cancelled"}
    written = _scheduled(ops)
    assert len(written) == 1 and written[0]["due_at"] == 3600.0
    assert PRICED_ARRIVAL_KEY not in json.loads(written[0]["payload"])


# ---------------------------------------------------------------------------
# The units
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("written, metres_a_second", [
    ({"value": 7, "unit": "kn"}, 7 * KNOT),
    ({"value": 7, "unit": "knots"}, 7 * KNOT),
    ({"value": 7, "unit": "KN"}, 7 * KNOT),
    ({"value": "7", "unit": "kn"}, 7 * KNOT),
    ({"value": 36, "unit": "km/h"}, 10.0),
    ({"value": 36, "unit": "kph"}, 10.0),
    ({"value": 10, "unit": "m/s"}, 10.0),
    ({"value": 30, "unit": "mph"}, 30 * 1609.344 / 3600.0),
    ("7 kn", 7 * KNOT),
    ("12.5 knots", 12.5 * KNOT),
    ("40 km/h", 40 / 3.6),
    ("3 m/s", 3.0),
])
def test_the_units_are_read(written, metres_a_second):
    from world.spatial import vessel_speed
    record = {"name": "The Mary Ann", "state": {"speed": written}}
    assert vessel_speed(record) == pytest.approx(metres_a_second, rel=1e-9)


def test_a_speed_names_a_unit_the_engine_holds_or_is_no_speed():
    from world.spatial import SPEED_UNIT_METRES_PER_SECOND, SPEED_UNITS, vessel_speed
    # The closed set the writers are told, each of them read.
    assert set(SPEED_UNITS) <= set(SPEED_UNIT_METRES_PER_SECOND)
    for written in ({"value": 7, "unit": "leagues/h"}, {"value": 7}, 7,
                    "seven knots", "fast", {"value": 0, "unit": "kn"},
                    {"value": -3, "unit": "kn"}, {"value": True, "unit": "kn"},
                    {"value": None, "unit": "kn"}, [], None):
        assert vessel_speed({"state": {"speed": written}}) is None, written
    assert vessel_speed({"state": {}}) is None
    assert vessel_speed({}) is None
    assert vessel_speed(None) is None
    # A speed inside the transit is not the vessel's: every journey rewrites
    # the transit whole, so it is read nowhere.
    assert vessel_speed({"state": {"transit": {"phase": "in_transit",
                                               "speed": {"value": 7, "unit": "kn"}}}}) is None


# ---------------------------------------------------------------------------
# A speed the story changes re-times a journey under way
# ---------------------------------------------------------------------------

def test_a_restated_speed_retimes_a_journey_under_way():
    """The engine fails mid-crossing and the boat limps on at two knots: the
    later beat restates the vessel's speed through the merge, and the
    arrival is re-timed as a turned journey is -- the old one cancelled, a
    new one booked -- for what is left of the way at the new speed."""
    from world.mechanics import PRICED_SPEED_KEY
    scene = _crossing(speed={"value": 7, "unit": "kn"})
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    first = _scheduled(ops)[0]

    # The next beat's whole-transit write (every write replaces the transit)
    # says nothing about the speed: it is kept, and nothing moves.
    scene = merge_scene_with_diff(copy.deepcopy(scene), {"entities": {"mary_ann": {
        "state": {"transit": {"phase": "in_transit", "hatch": "closed",
                              "destination_room": "the_mainland",
                              "route_room": "the_channel"}}}}})
    assert scene["entities"]["mary_ann"]["state"]["speed"] == {"value": 7, "unit": "kn"}
    _, ops, _, _ = _sweep(scene, 2500.0, [first], turn_id=12, turn_idx=5)
    assert not _scheduled(ops) and not _statuses(ops)

    # The engine fails: the beat writes the vessel's new speed.
    scene = merge_scene_with_diff(copy.deepcopy(scene), {"entities": {"mary_ann": {
        "state": {"speed": {"value": 2, "unit": "kn"}}}}})
    assert scene["entities"]["mary_ann"]["state"]["transit"]["destination_room"] \
        == "the_mainland"
    _, ops, _, _ = _sweep(scene, 3000.0, [first], turn_id=13, turn_idx=6)
    assert _statuses(ops) == {first["event_id"]: "cancelled"}
    retimed = _scheduled(ops)
    assert len(retimed) == 1
    left = first["due_at"] - 3000.0
    assert retimed[0]["due_at"] == pytest.approx(3000.0 + left * 7 / 2)
    payload = json.loads(retimed[0]["payload"])
    assert payload["destination_room"] == "the_mainland"
    assert payload[PRICED_SPEED_KEY] == pytest.approx(2 * KNOT, abs=1e-4)
    assert payload[PRICED_ARRIVAL_KEY] == pytest.approx(left * 7 / 2, abs=0.1)

    # Restated in the same words the beat after, it does not slip; and a
    # beat that drops the speed is silence about it, not a return to a walk.
    _, ops, _, _ = _sweep(scene, 3300.0, [retimed[0]], turn_id=14, turn_idx=7)
    assert not _scheduled(ops) and not _statuses(ops)
    scene["entities"]["mary_ann"]["state"].pop("speed")
    _, ops, _, _ = _sweep(scene, 3600.0, [retimed[0]], turn_id=15, turn_idx=8)
    assert not _scheduled(ops) and not _statuses(ops)


def test_a_speed_first_written_under_way_retimes_the_walk():
    """Priced at the walk because nothing said, then the story says: what is
    left of the way is covered at the speed written, from that beat."""
    scene = _crossing()
    _, ops, _, _ = _sweep(scene, DEPARTURE_BEAT_END)
    walked = _scheduled(ops)[0]
    scene["entities"]["mary_ann"]["state"]["speed"] = {"value": 7, "unit": "kn"}
    _, ops, _, _ = _sweep(scene, 3000.0, [walked], turn_id=12, turn_idx=5)
    assert _statuses(ops) == {walked["event_id"]: "cancelled"}
    left = walked["due_at"] - 3000.0
    assert _scheduled(ops)[0]["due_at"] == pytest.approx(
        3000.0 + left * WALK_PACES_PER_SECOND / (7 * KNOT))


# ---------------------------------------------------------------------------
# Where else a vessel is authored, and what a body is told
# ---------------------------------------------------------------------------

def test_the_rooms_planned_vessel_carries_its_speed_into_the_scene():
    from story.plot_packages import OPERATION_FIELDS
    from world.planned_entities import plan_state
    from world.spatial import SPEED_UNITS, vessel_speed
    brief = OPERATION_FIELDS["plan_entity"]["brief"]
    assert "speed: {value, unit}" in brief
    # The units are the engine's own, joined from where they are kept.
    assert "unit %s," % " | ".join(SPEED_UNITS) in brief
    state = plan_state({"engine": "a big diesel", "speed": {"value": 20, "unit": "kn"}})
    assert vessel_speed({"state": state}) == pytest.approx(20 * KNOT)


def test_a_speed_is_the_engines_record_and_never_read_off_the_craft():
    """Read off a craft lying at its mooring, a bare speed would state a
    motion it is not making; what checking a craft finds is in its own
    words in the rest of its state."""
    from agents import composer
    text = composer.thing_reading_text({"engine": "running",
                                        "speed": {"value": 7, "unit": "kn"}})
    assert text == "engine: running"


# ---------------------------------------------------------------------------
# The cards
# ---------------------------------------------------------------------------

def _speed_span():
    """The protocol span every card prints, built from the engine's own
    published units -- so a unit added to `SPEED_UNITS` is one every card
    must be taught, or this fails."""
    from world.spatial import SPEED_UNITS
    return "`state.speed = {value, unit:%s}`" % "|".join("'%s'" % u for u in SPEED_UNITS)


SPEED_SPAN = _speed_span()


def _cards(language):
    from language_runtime import installed_language_packs
    from llm import prompts
    card = installed_language_packs(refresh=True)[language].card("system_prompts")
    return {
        "transit": prompts.unified_specialist_prompt(
            ["entities"], language, parts=["entities__transit"]),
        "new": prompts.unified_specialist_prompt(
            ["entities"], language, parts=["entities__new"]),
        "bare": prompts.unified_specialist_prompt(["entities"], language, parts=[]),
        "transit_note": str(card["transit_note"]),
        "repair": str(card["prompts"]["resolve_repair"]),
    }


@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_cards_say_where_a_speed_is_written(language):
    cards = _cards(language)
    for name in ("transit", "new", "transit_note", "repair"):
        assert SPEED_SPAN in cards[name], (language, name)
    # Where a journey is written, a stated time is still its eta.
    for name in ("transit", "transit_note", "repair"):
        assert "eta_seconds" in cards[name], (language, name)
    # A part ships only with what it is about: the bare entities sheet
    # carries no clause about a speed.
    assert "state.speed" not in cards["bare"]


def test_the_speed_clauses_keep_one_protocol_in_both_languages():
    """`tools/project_check.py`'s own reading of a card's protocol: every
    span the English carries, the Japanese carries unchanged."""
    import pathlib
    import sys
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
    import project_check as check
    en, ja = _cards("en"), _cards("ja")
    for name in ("transit", "new", "transit_note", "repair"):
        assert SPEED_SPAN in check.canonical_language_tokens(en[name]), name
        assert check.canonical_language_tokens(en[name]) \
            <= check.canonical_language_tokens(ja[name]), name


# ---------------------------------------------------------------------------
# The record travels (docs/guides/DATABASE.md's checklist)
# ---------------------------------------------------------------------------

def test_a_vessels_speed_travels_through_checkpoint_archive_and_branch(temp_db):
    """The speed rides the vessel's record in the frame-scoped `scene` blob,
    which the checkpoint snapshots verbatim, the archive carries opaque and
    a branch copies with only its ids remapped -- so no carrier needs code of
    its own, and this proves each one rather than assuming it."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app
    from world.spatial import vessel_speed

    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Crossing", "", time.time()))
    tid = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                     "VALUES(?,?,?,?)", (cid, 0, "cast off", time.time()))
    temp_db.wset(cid, "scene", _crossing(speed={"value": 7, "unit": "kn"}))

    def speed_in(chat_id):
        scene = temp_db.wget(chat_id, "scene")
        scene = json.loads(scene) if isinstance(scene, str) else scene
        return vessel_speed(scene["entities"]["mary_ann"])

    ensure_checkpoint(cid, 0)
    temp_db.wset(cid, "scene", _crossing())
    assert speed_in(cid) is None
    restore_checkpoint(cid, 0)
    assert speed_in(cid) == pytest.approx(7 * KNOT)

    service = app._chat_archive_service
    imported = service.import_chat({"data": service.export_chat(cid)})
    assert speed_in(imported["id"] if isinstance(imported, dict) else imported) \
        == pytest.approx(7 * KNOT)

    branched = app.turn_branch(tid)
    assert speed_in(branched["id"]) == pytest.approx(7 * KNOT)
