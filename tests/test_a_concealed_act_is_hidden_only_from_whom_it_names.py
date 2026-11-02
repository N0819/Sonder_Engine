"""An act concealed from ONE observer is hidden from that observer alone.

`_outcome_event_stream` dropped every action whose `visibility` was
`concealed` before any perceiver was asked, while its own docstring says
"Concealment, sight, hearing, containment and identity remain per-observer
decisions in the loop that consumes the stream" -- and the per-observer rule
(`composer.concealed_from_observer`: "a populated list is an explicit
excluded audience") already runs inside `act_percept`. So a hand-off hidden
from the guard was hidden from the accomplice it was made to as well, in her
view and in her memory of the beat (audit agents_perception F3, 2026-11-01:
`hidden from Mara? False`, `hidden from Guard? True`, stream `[]`). Lines and
communications kept their `conceal_from` and were gated per observer; only
actions were decided for everyone at once.
"""

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData

PLAYER = "Nera"
ACCOMPLICE = "Mara"
GUARD = "Guard Holt"
HANDOFF = "presses a small iron key into Mara's palm"

_UID = [0]


def _character(temp_db, chat_id, name):
    sheet = default_character_data(name)
    sheet.setdefault("embodiment", {}).setdefault("visible", {})["summary"] = (
        "A person in a grey coat.")
    _UID[0] += 1
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time(), f"conceal_t{_UID[0]}"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    return char_id


def _ctx(temp_db, *, conceal_from):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Conceal", "", time.time(), persona_id))
    mara = _character(temp_db, chat_id, ACCOMPLICE)
    guard = _character(temp_db, chat_id, GUARD)
    temp_db.wset(chat_id, "scene", {
        "location": "the cell block", "time": "day",
        "rooms": {"block": {"name": "Cell Block", "desc": "A stone corridor.",
                            "light": "lit", "adjacent": []}},
        "positions": {PLAYER: "block", ACCOMPLICE: "block", GUARD: "block"},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", {ACCOMPLICE: [PLAYER], GUARD: [PLAYER]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Conceal", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "block"
    act = {"type": "action", "attempt": HANDOFF, "observable": HANDOFF,
           "visibility": "concealed", "conceal_from": list(conceal_from),
           "targets": [ACCOMPLICE], "commitment": "asserted",
           "verb": "press", "stage": "immediate",
           "event_id": "turn:1:player:0:action"}
    ctx.director_interpret = {
        "action": {k: act[k] for k in ("attempt", "visibility",
                                       "conceal_from", "targets",
                                       "commitment")},
        "sequence": [act], "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [mara, guard]},
    }
    ctx.director_resolve = {"resolved_event": "", "state_diff": {},
                            "dialogue_log": [], "dialogue_order": []}
    return ctx, mara, guard


def _outcome(ctx):
    import agents.perception as perception
    return perception.perception_outcome(ctx, nonce="n")["views"]


def test_the_accomplice_sees_what_was_hidden_from_the_guard(temp_db):
    ctx, mara, guard = _ctx(temp_db, conceal_from=[GUARD])
    views = _outcome(ctx)
    assert "iron key" in (views.get(str(mara)) or ""), views
    assert "iron key" not in (views.get(str(guard)) or ""), views


def test_an_act_hidden_from_everyone_reaches_nobody(temp_db):
    """An empty `conceal_from` still hides the act from every non-actor."""
    ctx, mara, guard = _ctx(temp_db, conceal_from=[])
    views = _outcome(ctx)
    assert "iron key" not in (views.get(str(mara)) or ""), views
    assert "iron key" not in (views.get(str(guard)) or ""), views
