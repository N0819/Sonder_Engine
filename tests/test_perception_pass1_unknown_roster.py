"""A co-present stranger's canonical name must not reach an observer.

Live, chat 63 turn 165: two co-present bodies, one scrub pass, the warning
reporting ``scrubbed unearned identity ['Hinami']`` while "Tamamo" sat
untouched in the same sentence, delivered to an observer with no ``known``
entry at all. The pass-1 scrub had enumerated a one-element roster holding
the player persona alone, so no pattern was ever built for a cast name.

**This file used to slice the fixed block out of `agents/perception.py` by
its own source text and exec it**, because — in its own words — "exercising
it end-to-end needs a model call". Perception makes no model call now, so
the whole apparatus is gone: the anchors, the sha print, the reconstructed
locals. The same two cases run through the real stage entry point, which is
what the original wanted and could not have.

Note what changed underneath, too. The old block was a SCRUB: the name
reached the view and was removed afterwards. On the composer path the name
is never admitted — an unrecognised body becomes a descriptor at
percept-build time (`observer_display_map`), and the scrub survives only as
a tripwire that should never fire. Both tests therefore assert the outcome
rather than the repair, and the second one asserts no tripwire fired.
"""

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


PLAYER = "Kestrel"
OBSERVER = "The Doctor"
HINAMI = "Hinami"
TAMAMO = "Tamamo"

LOOKS = {
    OBSERVER: "A lean man in a battered frock coat.",
    HINAMI: "A fox-eared woman with six golden tails.",
    TAMAMO: "A white-haired shrine maiden with one pivoting ear.",
}


def _ctx(temp_db, known):
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Roster", "", time.time(), persona_id))
    ids = {}
    for i, name in enumerate((OBSERVER, HINAMI, TAMAMO)):
        sheet = default_character_data(name)
        sheet["embodiment"]["visible"]["summary"] = LOOKS[name]
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(), f"char_{i}"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, cid, "active", "{}"))
        ids[name] = cid
    temp_db.wset(chat_id, "scene", {
        "location": "the shrine", "time": "day",
        "rooms": {"shrine": {"name": "Shrine", "desc": "A shrine.",
                             "adjacent": []}},
        "positions": {PLAYER: "shrine", OBSERVER: "shrine",
                      HINAMI: "shrine", TAMAMO: "shrine"},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", known)
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Roster", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "shrine"
    ctx.director_interpret = {
        "action": {"attempt": "kneels by the offering box",
                   "visibility": "overt", "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [{
            "type": "action", "attempt": "kneels by the offering box",
            "observable": "kneels by the offering box", "visibility": "overt",
            "conceal_from": [], "targets": [], "commitment": "asserted",
            "verb": "kneel", "stage": "immediate",
            "event_id": "turn:1:player:0:action"}],
        "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [ids[OBSERVER]]}}
    return ctx, ids


def test_observer_with_no_known_key_scrubs_both_co_present_bodies(temp_db):
    """The live defect: one of two names went, the other stayed."""
    from agents.perception import perception_act

    ctx, ids = _ctx(temp_db, known={})
    view = perception_act(ctx, nonce="n")["views"][str(ids[OBSERVER])] or ""

    assert HINAMI not in view, view
    assert TAMAMO not in view, view
    # ...and both are still delivered, as what the observer can actually see.
    assert "fox-eared" in view.casefold()
    assert "shrine maiden" in view.casefold() or "white-haired" in view.casefold()


def test_observer_recognising_tamamo_keeps_tamamo_and_scrubs_hinami(temp_db):
    """Recognition is per-body, not per-view: knowing one of two people in
    a room must not hand over the other."""
    from agents.perception import perception_act

    ctx, ids = _ctx(temp_db, known={OBSERVER: [PLAYER, TAMAMO]})
    view = perception_act(ctx, nonce="n")["views"][str(ids[OBSERVER])] or ""

    assert TAMAMO in view, view
    assert HINAMI not in view, view
    assert "fox-eared" in view.casefold()
    # Nothing was repaired on the way out: the name was never admitted.
    assert not [w for w in ctx.warnings if "COMPOSER TRIPWIRE" in w], (
        ctx.warnings)


# ---------------------------------------------------------------------------
# A name's own parts are spellings of the body it names
# ---------------------------------------------------------------------------

def test_a_bare_given_name_is_withheld_exactly_as_the_full_name_is():
    """The forms were the full name and the authored aliases, so a Director
    writing a bare given name in free text walked past this floor while the
    same channel carrying the full name was caught and repaired.

    Measured (the Cold Season Ball, 2026-09-05, PX1):
    `poses["Verrin Sault"].detail` read "eyes fixed on Ivo through his white
    silk mask", and that sentence reached two minds' composed views, their
    observations and their stored episodes -- one episode's `entities` array
    literally ends `"Verrin Sault", "Ivo"`. The control is in the same run:
    turns 8, 9 and 15 carried "Ivo Sarn" through the same channel and every
    one of them fired the tripwire. The only difference was the spelling.
    """
    from agents.common import _scrub_unknown_identities

    unknown = [{"name": "Ivo Sarn", "appearance": "a slight man in a mask",
                "aliases": []}]
    for text in ("Verrin looks at Ivo Sarn.", "Verrin looks at Ivo.",
                 "Verrin looks at Sarn."):
        out, leaked = _scrub_unknown_identities(
            text, allowed_forms=["Verrin"], unknown_sources=unknown)
        assert "Ivo" not in out and "Sarn" not in out, (text, out)
        assert leaked == ["Ivo Sarn"], (text, leaked)


def test_a_part_the_name_shares_with_the_language_is_not_a_spelling():
    """`The Stranger` is an engine label, not an identity: its parts are an
    article and one of the engine's own label heads, and scrubbing them
    would eat every article in the view. Both tables are the pack's."""
    from agents.common import _scrub_unknown_identities

    unknown = [{"name": "The Stranger", "appearance": "a person in grey",
                "aliases": []}]
    out, leaked = _scrub_unknown_identities(
        "The Stranger raises the lantern in the Long Hall.",
        allowed_forms=[], unknown_sources=unknown)
    assert "The Stranger" not in out
    assert "the lantern" in out and "the Long Hall" in out


def test_a_part_the_observer_legitimately_commands_is_shielded():
    """Recognition is per-body. An observer who knows one Sarn and not the
    other keeps the one they know, whole."""
    from agents.common import _scrub_unknown_identities

    unknown = [{"name": "Ivo Sarn", "appearance": "a slight man in a mask",
                "aliases": []}]
    out, _leaked = _scrub_unknown_identities(
        "Mira Sarn nods to Ivo Sarn.",
        allowed_forms=["Mira Sarn"], unknown_sources=unknown)
    assert "Mira Sarn" in out
    assert "Ivo" not in out
