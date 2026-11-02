"""A line no moment cites is heard on the same field as every other sound of
its beat.

The outcome pass grades the soundscape, the beat's own sounds and every act
on THIS observer's field for the beat -- the beat's sound events included --
and grades a line through `_channel_as_of`. A line with a causal moment got
the moment's field; a line without one was graded on the perceiver map's
relation, stamped before the beat's sounds were known. `event_worlds` gives a
moment only to cited spans, so a background presence's line, a Director row
and every line of an archived beat were graded as if the falls were silent
while the cast's lines beside them were drowned (audit agents_perception F4,
2026-11-01: `line heard without the beat's events=full / with them=none`).

Here no `_composed_beat` exists, so the player's line is uncited too -- the
same path the background presence's line takes in play.
"""

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData

PLAYER = "Hinami"
WATCHER = "Tamamo"
LINE = "The lamps are out along the west wing."
ROAR = "the mill race thunders through the wall"

_UID = [0]


def _ctx(temp_db, *, events):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Field", "", time.time(), persona_id))
    sheet = default_character_data(WATCHER)
    sheet.setdefault("embodiment", {}).setdefault("visible", {})["summary"] = (
        "A fox-eared young woman in shrine-maiden robes.")
    _UID[0] += 1
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (WATCHER, json.dumps(sheet), "{}", time.time(), f"field_t{_UID[0]}"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "the mill", "time": "day",
        "rooms": {"mill": {
            "name": "Mill Room", "notes": "A low stone room.", "light": "lit",
            "cells": [[x, y] for x in range(4) for y in range(3)],
            "anchors": {
                "quern": {"desc": "the quern", "cell": [0, 0],
                          "height": "waist"},
                "door": {"desc": "the door", "cell": [3, 2],
                         "height": "head"}},
            "adjacent": []}},
        "positions": {PLAYER: "mill", WATCHER: "mill"},
        "stations": {PLAYER: {"at": "quern", "near": []},
                     WATCHER: {"at": "door", "near": []}},
        "entities": {}, "contained": {}, "contacts": [],
        "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", {WATCHER: [PLAYER]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Field", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "mill"
    ctx.director_interpret = {"sequence": [], "speech": None,
                              "flow": {"reactors": [char_id]}}
    ctx.director_resolve = {
        "resolved_event": "", "state_diff": {"sensory_events": events},
        "dialogue_log": [{"speaker": PLAYER, "exact_quote": LINE,
                          "volume": "normal", "tone": "flat",
                          "visibility": "overt"}],
        "dialogue_order": []}
    return ctx, char_id


def _view(ctx, char_id):
    import agents.perception as perception
    return perception.perception_outcome(ctx, nonce="n")["views"][str(char_id)] or ""


def test_without_the_roar_the_line_is_heard_whole(temp_db):
    ctx, char_id = _ctx(temp_db, events=[])
    assert LINE in _view(ctx, char_id)


def test_a_roar_that_drowns_the_room_takes_the_uncited_lines_words(temp_db):
    ctx, char_id = _ctx(temp_db, events=[
        {"kind": "sound", "room": "mill", "level": "deafening",
         "detail": ROAR, "drowns": True}])
    view = _view(ctx, char_id)
    assert ROAR in view.casefold(), view
    assert LINE not in view, (
        f"a line no moment cites was graded on a field without the beat's "
        f"own roar: {view!r}")
