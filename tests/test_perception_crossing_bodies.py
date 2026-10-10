"""A crate carried through a doorway was narrated as a figure arriving.

`state_diff.positions` is not a roster of people. `AGENTS.md`'s
body-enclosure row states it outright -- "`positions` legitimately keys
objects and unregistered presences by entity id" -- and the outcome
composer's crossing loop took every key of it as a mover. Where the mover
was an object, no display name resolved and no observer recognised it, so
the label fell through to the unknown-body label and every observer at
either end of the move was told *"A figure comes in."* about a crate.

The rule the engine already has, in its own vocabulary: a crossing percept
is `kind="crossing", channel="sight"` about a BODY. An object's movement is
an object's movement; whatever it deserves, it is not a figure.
"""

import pytest
import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


PLAYER = "Hinami"
WATCHER = "The Doctor"


def _two_room_ctx(temp_db, *, entities, positions, moved, steps=None):
    """Watcher in the hall; something crosses in from the storeroom. `steps`,
    when given, are the beat's causal steps in order, one positions patch
    each."""
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Crossing", "", time.time(), persona_id))
    sheet = default_character_data(WATCHER)
    sheet.setdefault("embodiment", {}).setdefault("visible", {})["summary"] = (
        "A lean man in a battered frock coat.")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (WATCHER, json.dumps(sheet), "{}", time.time(), "char_w"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))

    scene = {
        "location": "the hall", "time": "day",
        "rooms": {
            "hall": {"name": "Hall", "desc": "A hall.",
                     "adjacent": [{"to": "store", "barrier": "open",
                                   "distance": "near"}]},
            "store": {"name": "Storeroom", "desc": "Shelves.",
                      "adjacent": [{"to": "hall", "barrier": "open",
                                    "distance": "near"}]},
        },
        "positions": dict(positions),
        "entities": dict(entities),
        "attire": {}, "overlays": {},
    }
    temp_db.wset(chat_id, "scene", scene)
    temp_db.wset(chat_id, "known", {WATCHER: [PLAYER]})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Crossing", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "hall"
    ctx.director_interpret = {
        "action": {"attempt": "waits", "visibility": "overt",
                   "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [], "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [char_id]},
    }
    diff = {"positions": dict(moved)}
    if steps:
        diff["causal_steps"] = [
            {"stage": "resolve", "chrono_id": n, "events": [],
             "patch": {"positions": dict(patch)}}
            for n, patch in enumerate(steps, 1)]
    ctx.director_resolve = {
        "resolved_event": "Something comes through the doorway.",
        "state_diff": diff,
        "dialogue_log": [], "dialogue_order": []}
    return ctx, char_id


def _views(ctx):
    import agents.perception as perception
    return perception.perception_outcome(ctx, nonce="n")["views"]


def test_an_object_crossing_rooms_is_not_a_figure(temp_db):
    """The defect. A crate is carried hall-ward and the watcher is told a
    person walked in."""
    ctx, char_id = _two_room_ctx(
        temp_db,
        entities={"crate_1": {"name": "supply crate", "kind": "container",
                              "portable": True, "desc": "A wooden crate."}},
        positions={PLAYER: "hall", WATCHER: "hall", "crate_1": "store"},
        moved={"crate_1": "hall"})
    view = _views(ctx)[str(char_id)] or ""

    assert "a figure comes in" not in view.casefold(), (
        "a crate moved between rooms was rendered as a body crossing the "
        f"threshold: {view!r}")


def test_a_body_crossing_rooms_still_arrives(temp_db):
    """The subtraction must stop at objects. An unregistered presence keyed
    by entity id is a person, and losing her would be the worse bug."""
    ctx, char_id = _two_room_ctx(
        temp_db,
        entities={"porter_1": {"name": "a porter", "kind": "person",
                               "desc": "A porter in grey."}},
        positions={PLAYER: "hall", WATCHER: "hall", "porter_1": "store"},
        moved={"porter_1": "hall"})
    view = _views(ctx)[str(char_id)] or ""

    assert "comes in" in view.casefold(), (
        f"a body crossing into the observer's room was dropped: {view!r}")


def _crossing_together(temp_db, steps=None):
    """The watcher and a porter both come from the storeroom into the hall,
    where the player stands, in the order `steps` gives."""
    return _two_room_ctx(
        temp_db,
        entities={"porter_1": {"name": "a porter", "kind": "person",
                               "desc": "A porter in grey."}},
        positions={PLAYER: "hall", WATCHER: "store", "porter_1": "store"},
        moved={WATCHER: "hall", "porter_1": "hall"}, steps=steps)


def test_a_body_that_came_with_you_does_not_come_in(temp_db):
    """Two bodies that cross in the same causal step walked it side by side,
    and neither came in on the other. Scratch story 166 turn 4607, replayed
    with the follow carrying her (2026-10-09), told the player "Hester Gale
    comes in." on the stair they had climbed together. A body arriving where
    the observer already stood still comes in -- to the player, both do."""
    ctx, char_id = _crossing_together(
        temp_db, steps=[{WATCHER: "hall", "porter_1": "hall"}])
    views = _views(ctx)
    watcher = (views[str(char_id)] or "").casefold()
    player = (views["player"] or "").casefold()
    assert "comes in" not in watcher, (
        f"the porter walked in beside him, and was told he came in: {watcher!r}")
    assert "comes in" in player, (
        f"bodies crossing into where the player stood were dropped: {player!r}")


def test_a_body_that_came_in_after_you_comes_in(temp_db):
    """Review F4: the same crossing is not the same moment. Scratch story
    166 idx 5 (turn 4590): the player went up the rise at the onset and the
    pilot followed at the resolve, and "Hester Gale comes in." was true --
    the page said "Hester came up the rise". The observer crossed first, so
    the mover came in on them."""
    ctx, char_id = _crossing_together(
        temp_db, steps=[{WATCHER: "hall"}, {"porter_1": "hall"}])
    watcher = (_views(ctx)[str(char_id)] or "").casefold()
    assert "comes in" in watcher, watcher


def test_a_body_that_was_there_first_does_not_come_in(temp_db):
    """The porter crossed first and was standing in the hall when the
    watcher came through: nobody came in on him."""
    ctx, char_id = _crossing_together(
        temp_db, steps=[{"porter_1": "hall"}, {WATCHER: "hall"}])
    watcher = (_views(ctx)[str(char_id)] or "").casefold()
    assert "comes in" not in watcher, watcher


def test_a_beat_with_no_steps_keeps_its_crossing_lines(temp_db):
    """Where the beat records no steps the order is unknown, and the line
    stands as it always did: dropping it would be a guess."""
    ctx, char_id = _crossing_together(temp_db)
    watcher = (_views(ctx)[str(char_id)] or "").casefold()
    assert "comes in" in watcher, watcher


def _from_the_yard(temp_db, steps):
    """The watcher comes into the hall from a yard; a porter comes in from
    the storeroom; the player stands in the hall throughout."""
    ctx, char_id = _two_room_ctx(
        temp_db,
        entities={"porter_1": {"name": "a porter", "kind": "person",
                               "desc": "A porter in grey."}},
        positions={PLAYER: "hall", WATCHER: "yard", "porter_1": "store"},
        moved={WATCHER: "hall", "porter_1": "hall"}, steps=steps)
    scene = temp_db.wget(ctx.chat.id, "scene")
    scene["rooms"]["yard"] = {"name": "Yard", "desc": "A yard.",
                              "adjacent": [{"to": "hall", "barrier": "open", "distance": "near"}]}
    scene["rooms"]["hall"]["adjacent"].append({"to": "yard", "barrier": "open", "distance": "near"})
    temp_db.wset(ctx.chat.id, "scene", scene)
    return ctx, char_id


@pytest.mark.parametrize("porter_first", [True, False])
def test_a_body_there_before_you_came_in_from_elsewhere_does_not_come_in(
        temp_db, porter_first):
    """Review N8: the rule is about who was in the room first, not which
    doorway each came by. The porter came in from the storeroom a step
    before the watcher came in from the yard: the watcher found him there.
    Came in the other way round, the porter came in on the watcher; and to
    the player, who stood there throughout, he comes in either way."""
    steps = [{"porter_1": "hall"}, {WATCHER: "hall"}]
    ctx, char_id = _from_the_yard(temp_db, steps if porter_first else steps[::-1])
    views = _views(ctx)
    watcher = (views[str(char_id)] or "").casefold()
    assert ("comes in" in watcher) is not porter_first, watcher
    assert "comes in" in (views["player"] or "").casefold(), views["player"]


# --- The mirror composes the beat from the room the body is in AT ITS END ---
#
# `perception_outcome` merges with `clock_seconds=_beat_end` so a passage
# carries its occupants onward inside the mirror exactly as it will inside the
# commit. That was W9's headline claim and no test held it: deleting the
# argument at `agents/perception.py:2202` left the whole suite green at 9573,
# so the narrator could compose a beat from a room the body had already left.
# Class vocabulary only: a vessel with an inside, and a traveller crossing it.

VESSEL = "the vessel"
VESSEL_EID = "vessel_1"
TRAVELLER = "a traveller"
TRAVELLER_EID = "traveller_1"


def _crossing_ctx(temp_db, *, transit=5.0, since=1000.0, clock=1000.0,
                  duration=30.0):
    """A watcher in the hall; a traveller mid-crossing inside a body there.

    The traveller stands in the vessel's first interior station, stamped as
    having been there since `since`; the station takes `transit` seconds to
    cross and the beat covers `duration`. So the merge -- in the mirror and in
    the commit alike -- must carry them to the second station.

    `_two_room_ctx` above cannot serve this: its rooms are a fixed pair with
    no `parent_entity`, and an inside is exactly what this needs.
    """
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Crossing", "", time.time(), persona_id))
    sheet = default_character_data(WATCHER)
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (WATCHER, json.dumps(sheet), "{}", time.time(), "char_w"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))

    scene = {
        "location": "the hall", "time": "day",
        "rooms": {
            "hall": {"name": "Hall", "desc": "A hall.", "adjacent": []},
            "st_0": {"name": "Station 0", "desc": "", "light": "dark",
                     "parent_entity": VESSEL_EID, "dock_exit": True,
                     "transit_seconds": transit,
                     "adjacent": [{"to": "st_1", "barrier": "membrane"}]},
            "st_1": {"name": "Station 1", "desc": "", "light": "dark",
                     "parent_entity": VESSEL_EID,
                     "adjacent": [{"to": "st_0", "barrier": "membrane"}]},
        },
        "positions": {PLAYER: "hall", WATCHER: "hall", VESSEL: "hall",
                      TRAVELLER: "st_0"},
        "entities": {
            VESSEL_EID: {"name": VESSEL, "kind": "person", "aliases": [],
                         "interior_rooms": ["st_0", "st_1"], "state": {}},
            TRAVELLER_EID: {"name": TRAVELLER, "kind": "person",
                            "aliases": [], "state": {}},
        },
        # `_is_body_entity` reads exactly these two tables.
        "attire": {VESSEL: {"worn": []}, TRAVELLER: {"worn": []}},
        "scales": {},
        "contacts": [{
            "actor": TRAVELLER, "target": VESSEL, "relation": "interior",
            "target_interior": "Station 0", "target_part": "",
            "motion": "moving", "manner": "", "detail": "",
        }],
        "contained": {}, "poses": {}, "stations": {}, "overlays": {},
        "substances": [],
        "room_since": {TRAVELLER: {"room": "st_0", "since": since}},
    }
    temp_db.wset(chat_id, "scene", scene)
    temp_db.wset(chat_id, "known", {WATCHER: [PLAYER]})
    temp_db.wset(chat_id, "simulation_clock",
                 {"elapsed_seconds": clock, "display": "moments later"})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Crossing", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "hall"
    ctx.director_interpret = {
        "action": {"attempt": "waits", "visibility": "overt",
                   "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [], "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [char_id]},
    }
    ctx.director_resolve = {
        "resolved_event": "The beat passes.",
        "state_diff": {"time": {"duration_seconds": duration}},
        "dialogue_log": [], "dialogue_order": []}
    return ctx, chat_id


class TestTheComposedRoomIsTheCommittedRoom:
    """The mirror and the commit read one clock, so they read one room."""

    def test_the_mirror_carries_a_crossing_body_onward(self, temp_db):
        import agents.perception as perception

        ctx, _chat_id = _crossing_ctx(temp_db)
        perception.perception_outcome(ctx, nonce="n")
        composed = (ctx._extra["outcome_scene"]["positions"] or {}).get(
            TRAVELLER)
        assert composed == "st_1", (
            "the outcome mirror composed the beat from the station the body "
            f"had already left: {composed!r}")

    def test_the_mirror_and_the_commit_land_on_one_room(self, temp_db):
        from persist.commit import commit_scene, prepare_scene_commit
        import agents.perception as perception

        ctx, chat_id = _crossing_ctx(temp_db)
        perception.perception_outcome(ctx, nonce="n")
        composed = (ctx._extra["outcome_scene"]["positions"] or {}).get(
            TRAVELLER)

        prepared = prepare_scene_commit(ctx)
        commit_scene(ctx, 0, prepared=prepared)
        committed = (temp_db.wget(chat_id, "scene", {}).get("positions")
                     or {}).get(TRAVELLER)

        assert composed == committed == "st_1", (
            f"composed {composed!r} but committed {committed!r}: the beat was "
            "narrated from a room the world does not agree the body is in")

    def test_a_bound_not_yet_reached_leaves_both_where_they_were(
            self, temp_db):
        """The pin cuts both ways: the mirror must not run the clock past
        what the beat bought, either."""
        from persist.commit import commit_scene, prepare_scene_commit
        import agents.perception as perception

        ctx, chat_id = _crossing_ctx(temp_db, transit=600.0)
        perception.perception_outcome(ctx, nonce="n")
        composed = (ctx._extra["outcome_scene"]["positions"] or {}).get(
            TRAVELLER)
        prepared = prepare_scene_commit(ctx)
        commit_scene(ctx, 0, prepared=prepared)
        committed = (temp_db.wget(chat_id, "scene", {}).get("positions")
                     or {}).get(TRAVELLER)

        assert composed == committed == "st_0"
