"""A blind character saw the room, because only the micro-loop asked the card.

`embodiment.senses` is an authored, UI-editable card field, and
`spatial.sense_adjusted` is "THE senses gate (G4)". Exactly one deterministic
delivery path consulted it: `loops.deterministic_micro_perception`. The three
composed views -- onset, outcome, and the opening -- each wrote `senses` into
every perceiver dict and then read the key nowhere, so authored blindness,
deafness and keen hearing changed what a mind received in an interaction
micro-round and changed nothing in the view it remembered the beat by.

The two paths therefore disagreed inside one turn, which is the worse half:
a deaf character was correctly denied a line by the micro-loop and handed the
same line by the outcome view a moment later.
"""

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


PLAYER = "Hinami"
WATCHER = "Tamamo"
LINE = "The lamps are out along the west wing."


_UID = [0]


def _ctx(temp_db, *, senses):
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Senses", "", time.time(), persona_id))
    sheet = default_character_data(WATCHER)
    embodiment = sheet.setdefault("embodiment", {})
    embodiment.setdefault("visible", {})["summary"] = (
        "A fox-eared young woman in shrine-maiden robes.")
    embodiment["senses"] = list(senses)
    _UID[0] += 1
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (WATCHER, json.dumps(sheet), "{}", time.time(), f"char_t{_UID[0]}"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))

    temp_db.wset(chat_id, "scene", {
        "location": "the hall", "time": "day",
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "positions": {PLAYER: "hall", WATCHER: "hall"},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", {WATCHER: [PLAYER]})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Senses", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "hall"
    ctx.director_interpret = {
        "action": {"attempt": "crosses to the window", "visibility": "overt",
                   "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [{
            "type": "action", "attempt": "crosses to the window",
            "observable": "crosses the hall toward the window",
            "visibility": "overt", "conceal_from": [], "targets": [],
            "commitment": "asserted", "verb": "cross", "stage": "immediate",
            "event_id": "turn:1:player:0:action",
        }],
        "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [char_id]},
    }
    ctx.director_resolve = {
        "resolved_event": "The hall stands quiet.", "state_diff": {},
        "dialogue_log": [{"speaker": PLAYER, "exact_quote": LINE,
                          "volume": "normal", "tone": "flat",
                          "visibility": "overt"}],
        "dialogue_order": []}
    return ctx, char_id


def _act_view(ctx, char_id):
    import agents.perception as perception
    return perception.perception_act(ctx, nonce="n")["views"][str(char_id)] or ""


def _outcome_view(ctx, char_id):
    import agents.perception as perception
    return perception.perception_outcome(
        ctx, nonce="n")["views"][str(char_id)] or ""


ORDINARY = []
BLIND = [{"channel": "sight", "acuity": "absent"}]
DEAF = [{"channel": "hearing", "acuity": "absent"}]


def test_an_ordinary_card_sees_and_hears(temp_db):
    """The baseline the subtractions below are measured against."""
    ctx, char_id = _ctx(temp_db, senses=ORDINARY)
    assert PLAYER in _act_view(ctx, char_id)
    ctx, char_id = _ctx(temp_db, senses=ORDINARY)
    assert LINE in _outcome_view(ctx, char_id)


def test_a_blind_card_does_not_see_a_co_present_body_at_onset(temp_db):
    ctx, char_id = _ctx(temp_db, senses=BLIND)
    view = _act_view(ctx, char_id)
    assert "close by" not in view, (
        f"an authored-blind character was handed a body by sight: {view!r}")


def test_a_blind_card_does_not_see_a_co_present_body_at_outcome(temp_db):
    ctx, char_id = _ctx(temp_db, senses=BLIND)
    view = _outcome_view(ctx, char_id)
    assert "close by" not in view, (
        f"an authored-blind character was handed a body by sight: {view!r}")


def test_a_blind_card_still_hears(temp_db):
    """The gate is per channel. Taking sight must not take hearing -- the
    firewall subtracts what a body cannot reach, never more."""
    ctx, char_id = _ctx(temp_db, senses=BLIND)
    assert LINE in _outcome_view(ctx, char_id)


def test_a_deaf_card_does_not_receive_a_spoken_line(temp_db):
    ctx, char_id = _ctx(temp_db, senses=DEAF)
    view = _outcome_view(ctx, char_id)
    assert LINE not in view, (
        f"an authored-deaf character was handed a spoken line: {view!r}")


def test_a_deaf_card_still_sees(temp_db):
    ctx, char_id = _ctx(temp_db, senses=DEAF)
    assert "close by" in _act_view(ctx, char_id)


# --------------------------------------------------------------------------
# THE ROOM, NOT ONLY ITS BODIES AND LINES (audit agents_perception F1,
# 2026-11-01). The card above gated presence, pose, appearance, far places,
# vistas, scent and spoken lines, and nothing else: an authored-blind card
# in a lit kitchen was told "You can see the hearth ... Through the back
# door is The Yard. A muddy yard. There is a silver coin at the long oak
# counter.", byte-identical to a sighted one, and an authored-deaf card
# heard the generator's din and the kettle shriek. One floor now asks the
# card at each stage, after every builder has spoken: what arrived on a
# channel the card says is absent does not reach the mind. The place a
# sightless body stands in is still where it is -- its name and the room's
# own description, which the dark leaves a sighted body too -- and touch is
# no channel a card takes away.
# --------------------------------------------------------------------------

KETTLE = "a kettle shrieks on the stove"
TOAST = "the smell of burnt toast"


def _kitchen():
    return {
        "location": "the kitchen", "time": "day",
        "rooms": {
            "kitchen": {
                "name": "Kitchen", "notes": "A warm kitchen with a scrubbed table.",
                "light": "lit",
                "cells": [[0, 0], [1, 0], [2, 0], [0, 1], [1, 1], [2, 1]],
                "anchors": {
                    "hearth": {"desc": "the hearth", "cell": [0, 0],
                               "height": "waist"},
                    "counter": {"desc": "the long oak counter", "cell": [1, 0],
                                "height": "waist"}},
                "adjacent": [{"to": "yard", "barrier": "open_door",
                              "name": "the back door"}]},
            "yard": {"name": "The Yard", "notes": "A muddy yard.",
                     "light": "lit",
                     "adjacent": [{"to": "kitchen", "barrier": "open_door",
                                   "name": "the back door"}]},
        },
        "positions": {PLAYER: "kitchen", WATCHER: "kitchen", "coin": "kitchen",
                      "gen": "kitchen"},
        "stations": {WATCHER: {"at": "counter", "near": []},
                     "coin": {"at": "counter", "near": []},
                     "gen": {"at": "hearth", "near": []}},
        "entities": {
            "coin": {"name": "silver coin", "kind": "coin", "portable": True},
            "gen": {"name": "the generator", "kind": "machine",
                    "sound_source": "loud"}},
        "contained": {}, "contacts": [], "attire": {}, "overlays": {}}


def _kitchen_ctx(temp_db, *, senses):
    ctx, char_id = _ctx(temp_db, senses=senses)
    temp_db.wset(ctx.chat.id, "scene", _kitchen())
    ctx["_player_room"] = "kitchen"
    ctx.director_resolve["state_diff"] = {"sensory_events": [
        {"kind": "sound", "room": "kitchen", "level": "loud",
         "detail": KETTLE},
        {"kind": "smell", "room": "kitchen", "detail": TOAST}]}
    return ctx, char_id


ANOSMIC = [{"channel": "smell", "acuity": "absent"}]


def test_an_ordinary_card_is_given_the_kitchen(temp_db):
    """The baseline: every subtraction below is measured against it."""
    ctx, char_id = _kitchen_ctx(temp_db, senses=ORDINARY)
    view = _outcome_view(ctx, char_id)
    for said in ("You are in Kitchen", "the long oak counter", "silver coin",
                 "The Yard", KETTLE, TOAST, LINE):
        assert said.casefold() in view.casefold(), (said, view)
    assert "generator" in view, view


def test_a_blind_card_is_not_shown_the_room(temp_db):
    ctx, char_id = _kitchen_ctx(temp_db, senses=BLIND)
    view = _outcome_view(ctx, char_id)
    for unseen in ("You can see", "long oak counter", "silver coin",
                   "The Yard", "muddy yard"):
        assert unseen.casefold() not in view.casefold(), (
            f"an authored-blind card was shown {unseen!r}: {view!r}")
    # where it stands, what it hears and smells, are not sight's to take
    assert "You are in Kitchen" in view, view
    for heard in (KETTLE, TOAST, LINE):
        assert heard.casefold() in view.casefold(), (heard, view)


def test_a_blind_card_is_not_shown_the_room_at_onset(temp_db):
    ctx, char_id = _kitchen_ctx(temp_db, senses=BLIND)
    view = _act_view(ctx, char_id)
    for unseen in ("You can see", "long oak counter", "silver coin",
                   "The Yard"):
        assert unseen.casefold() not in view.casefold(), (unseen, view)
    ctx, char_id = _kitchen_ctx(temp_db, senses=ORDINARY)
    assert "silver coin" in _act_view(ctx, char_id)


def test_a_deaf_card_hears_no_room(temp_db):
    ctx, char_id = _kitchen_ctx(temp_db, senses=DEAF)
    view = _outcome_view(ctx, char_id)
    assert KETTLE not in view, view
    assert "generator" not in view and "noise" not in view.casefold(), view
    # it still sees and smells
    assert "long oak counter" in view and TOAST.casefold() in view.casefold(), view


def test_an_anosmic_card_smells_no_room(temp_db):
    ctx, char_id = _kitchen_ctx(temp_db, senses=ANOSMIC)
    view = _outcome_view(ctx, char_id)
    assert TOAST.casefold() not in view.casefold(), view
    assert KETTLE.casefold() in view.casefold() \
        and "long oak counter" in view, view


def test_a_blind_card_is_not_shown_the_room_at_the_opening(temp_db):
    """The third stage, the scene's opening, through the same floor."""
    import agents.perception as perception

    def opening(senses):
        ctx, char_id = _kitchen_ctx(temp_db, senses=senses)
        ctx.director_establish = {"sensory_events": [
            {"kind": "sound", "room": "kitchen", "level": "loud",
             "detail": KETTLE}]}
        return perception.perception_establish(
            ctx, nonce=0)["views"].get(str(char_id)) or ""

    seen = opening(ORDINARY)
    assert "silver coin" in seen and "The Yard" in seen, seen
    blind = opening(BLIND)
    for unseen in ("You can see", "long oak counter", "silver coin",
                   "The Yard"):
        assert unseen not in blind, (unseen, blind)
    assert "You are in Kitchen" in blind and KETTLE in blind.casefold(), blind
    deaf = opening(DEAF)
    assert KETTLE not in deaf.casefold() and "din" not in deaf, deaf
    assert "silver coin" in deaf, deaf
