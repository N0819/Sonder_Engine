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

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


PLAYER = "Hinami"
WATCHER = "The Doctor"


def _two_room_ctx(temp_db, *, entities, positions, moved):
    """Watcher in the hall; something crosses in from the storeroom."""
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
    ctx.director_resolve = {
        "resolved_event": "Something comes through the doorway.",
        "state_diff": {"positions": dict(moved)},
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
