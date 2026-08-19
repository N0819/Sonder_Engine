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
