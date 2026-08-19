"""An actor sealed inside something does not get an outside shot of themselves.

`observable` is the intent-free surface of an act as seen FROM OUTSIDE, and the
actor normally receives it in their own view -- rewritten to second person by
`_self_second_person` -- because people can see themselves doing things.

Sealed inside something that stops being true. The surface then describes the
outside of the enclosure, how its wall moves with them, and there is no channel
from inside to that.

Live, chat 60 t18. The declared observable was

    "A tiny lump writhes and squirms beneath the fabric, small limbs pushing
     at the cloth, the shirt shifting and bulging as the lump tries to find a
     way out."

and the actor's own view came back "The lump you make writhes and bulges under
the fabric" -- in darkness, under cloth, two clauses after her own narration
said she could see nothing. Reported from play as: she should not be able to
see the shape she makes.

The rule is keyed on being ENCLOSED, deliberately, and not on darkness or a
failed sight check. Being unable to see in the dark does not stop you knowing
what your own body is doing -- proprioception is not sight -- and suppressing
an actor's own conduct every time the lights went out would be a worse error
than the one this fixes. What an enclosure removes is specifically the outside
view of yourself.

Everyone else's view is untouched: the surface is exactly what they can see,
and that is what it is for.
"""

from __future__ import annotations

# --- what actually enforces the property ------------------------------------
#
# This file used to open with three classes over
# `perception._self_cannot_see_own_surface`, plus two `inspect.getsource`
# tests asserting that `_inject_onset_sequence` called it before
# `_inject_action`. One of those said the failure out loud in its own
# docstring -- "or it is a well-tested function nothing calls" -- and that is
# exactly what had happened: neither function has a production caller, so
# thirteen passing tests pinned the internal statement order of a retired
# path.
#
# The property is not lost, and it is not enforced by a guard either. The
# composer path makes it structural: `_composer_act` builds no perceiver for
# the acting player and `_composer_outcome`'s act loop skips `actor == name`,
# so an actor never receives the outside shot of their own act in ANY scene,
# enclosed or not. The enclosure special case became unnecessary rather than
# wrong. The two tests at the bottom of this file assert that on the live
# path, and assert the deliberate limit beside it: proprioception is not
# sight.

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


ACTOR = "Wren"
PLAYER = "Hinami"
SURFACE = "lifts the lantern high"
LANTERN = "a brass lantern"


def _outcome_ctx(temp_db, *, light=None, entity_state=None):
    """One cast actor who acts, one player watching."""
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Own surface", "", time.time(), persona_id))
    sheet = default_character_data(ACTOR)
    sheet.setdefault("embodiment", {}).setdefault("visible", {})["summary"] = (
        "A small woman in a grey coat.")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (ACTOR, json.dumps(sheet), "{}", time.time(), "wren_card"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))

    room = {"name": "Hall", "desc": "A hall.", "adjacent": []}
    if light:
        room["light"] = light
    entities = {}
    if entity_state is not None:
        entities["wren_1"] = {"name": ACTOR, "kind": "person",
                              "state": dict(entity_state)}
    temp_db.wset(chat_id, "scene", {
        "location": "the hall", "time": "night",
        "rooms": {"hall": room},
        "positions": {PLAYER: "hall", ACTOR: "hall"},
        "entities": entities, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", {ACTOR: [PLAYER]})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Own surface", persona_id=persona_id,
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
    ctx.character_results[char_id] = {
        "speech": "", "action": "lifts the lantern",
        "sequence": [{"type": "action", "attempt": "lifts the lantern",
                      "observable": SURFACE, "visibility": "overt",
                      "conceal_from": [], "targets": [],
                      "commitment": "asserted"}]}
    ctx.director_resolve = {
        "resolved_event": "The hall stands quiet.", "state_diff": {},
        "dialogue_log": [], "dialogue_order": []}
    return ctx, char_id


def _views(ctx):
    import agents.perception as perception
    return perception.perception_outcome(ctx, nonce="n")["views"]


def test_an_actor_never_receives_their_own_act_surface(temp_db):
    """The live floor under this file's whole premise.

    `observable` is the act as seen FROM OUTSIDE. On the composer path the
    actor is not among the observers of their own act, so the outside shot of
    themselves cannot be delivered whatever they are sealed inside."""
    ctx, char_id = _outcome_ctx(temp_db)
    views = _views(ctx)

    assert SURFACE not in (views[str(char_id)] or ""), (
        "an actor was handed the outside view of their own act: "
        f"{views[str(char_id)]!r}")
    assert SURFACE in (views.get("player") or ""), (
        "the subtraction reached past the actor and cost a watching mind an "
        f"act it plainly saw: {views.get('player')!r}")


def test_proprioception_is_not_sight(temp_db):
    """The rule this file names, on the path that now carries it.

    Being unable to see does not stop a body knowing what it is doing.
    `body_state_percept` rides the interoception channel, so a pitch-dark
    room takes the actor's sight of everyone else and leaves their own held
    items exactly where they are."""
    ctx, char_id = _outcome_ctx(
        temp_db, light="dark", entity_state={"held_items": [LANTERN]})
    view = _views(ctx)[str(char_id)] or ""

    assert LANTERN in view, (
        f"darkness took a character's knowledge of their own hands: {view!r}")
    assert PLAYER not in view, (
        f"a pitch-dark room did not take sight of another body: {view!r}")
