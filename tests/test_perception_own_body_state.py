"""A mind knew what was in its own hands on turn 0 and never again.

`body_state_percept` -- posture, activity, held items, channel
"interoception", source label "you" -- is emitted by
`_composer_standing_percepts` only when its `entity_state` kwarg is truthy,
and the kwarg was passed on the establish path alone. Its source there,
`director_establish.entity_states`, exists on the opening turn and nowhere
else, so from turn 1 onward the percept could not fire at all.

That matters here more than it would elsewhere: `composer.py`'s own header
says why -- "a character agent is a stateless LLM call; if it is not in
context, the mind does not have it". A character holding a lantern was not
told they were holding it, so nothing about the next beat could depend on it.

The durable home for the same three facts is the scene entity's `state`,
which `spatial_contact_migration._PROTECTED_STATE_KEYS` already reserves as
structural ("perception's own deterministic backstop"). Posture is the one
of the three that has a second, better home -- `scene.poses`, rendered by
`pose_percepts` with the sight grade -- so it is taken from `state` only
when the pose ledger is silent, rather than said twice.
"""

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


PLAYER = "Hinami"
WATCHER = "Tamamo"
WATCHER_EID = "tamamo_1"
LANTERN = "a brass lantern"


def _ctx(temp_db, *, state, poses=None):
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Interoception", "", time.time(), persona_id))
    sheet = default_character_data(WATCHER)
    sheet.setdefault("embodiment", {}).setdefault("visible", {})["summary"] = (
        "A fox-eared young woman in shrine-maiden robes.")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (WATCHER, json.dumps(sheet), "{}", time.time(), "char_t"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))

    scene = {
        "location": "the hall", "time": "night",
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "positions": {PLAYER: "hall", WATCHER: "hall"},
        "entities": {WATCHER_EID: {"name": WATCHER, "kind": "person",
                                   "desc": "A shrine maiden.",
                                   "state": dict(state)}},
        "attire": {}, "overlays": {},
    }
    if poses:
        scene["poses"] = dict(poses)
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
        chat=ChatData(id=chat_id, name="Interoception", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "hall"
    ctx.director_interpret = {
        "action": {"attempt": "waits", "visibility": "overt",
                   "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [{
            "type": "action", "attempt": "waits",
            "observable": "stands still in the hall",
            "visibility": "overt", "conceal_from": [], "targets": [],
            "commitment": "asserted", "verb": "wait", "stage": "immediate",
            "event_id": "turn:1:player:0:action",
        }],
        "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [char_id]},
    }
    ctx.director_resolve = {
        "resolved_event": "The hall stands quiet.", "state_diff": {},
        "dialogue_log": [], "dialogue_order": []}
    return ctx, char_id


def _act_view(ctx, char_id):
    import agents.perception as perception
    return perception.perception_act(ctx, nonce="n")["views"][str(char_id)] or ""


def _outcome_view(ctx, char_id):
    import agents.perception as perception
    return perception.perception_outcome(
        ctx, nonce="n")["views"][str(char_id)] or ""


def test_own_held_items_reach_the_onset_view(temp_db):
    ctx, char_id = _ctx(temp_db, state={"held_items": [LANTERN]})
    view = _act_view(ctx, char_id)
    assert LANTERN in view, (
        f"a character was not told what is in their own hands: {view!r}")


def test_own_held_items_reach_the_outcome_view(temp_db):
    ctx, char_id = _ctx(temp_db, state={"held_items": [LANTERN]})
    view = _outcome_view(ctx, char_id)
    assert LANTERN in view, (
        f"a character was not told what is in their own hands: {view!r}")


def test_own_activity_reaches_the_outcome_view(temp_db):
    ctx, char_id = _ctx(temp_db, state={"activity": "keeping watch"})
    view = _outcome_view(ctx, char_id)
    assert "keeping watch" in view, (
        f"a character was not told what they are doing: {view!r}")


def test_posture_is_not_said_twice_when_the_pose_ledger_has_it(temp_db):
    """`pose_percepts` renders posture with the sight grade and always
    delivers the observer's own. Reading it out of `state` as well is a
    second representation of one fact, free to drift."""
    ctx, char_id = _ctx(
        temp_db,
        state={"posture": "kneeling", "held_items": [LANTERN]},
        poses={WATCHER: {"posture": "kneeling"}})
    view = _outcome_view(ctx, char_id)
    assert LANTERN in view
    assert view.casefold().count("kneeling") == 1, (
        f"posture arrived from two representations at once: {view!r}")


def test_posture_still_arrives_when_the_pose_ledger_is_silent(temp_db):
    """The subtraction above must not cost the fact. A scene entity may carry
    `state.posture` with no `poses` entry beside it."""
    ctx, char_id = _ctx(temp_db, state={"posture": "kneeling"})
    view = _outcome_view(ctx, char_id)
    assert "kneeling" in view.casefold(), (
        f"an unposed body's own posture reached nobody: {view!r}")


def test_another_bodys_state_is_not_handed_over(temp_db):
    """Interoception is the observer's own. The player's entity state must
    not arrive in a character's view under any label."""
    ctx, char_id = _ctx(temp_db, state={})
    sc = temp_db.wget(ctx.chat["id"], "scene")
    sc["entities"]["player_pack"] = {
        "name": PLAYER, "kind": "person",
        "state": {"held_items": ["a sealed writ"]}}
    temp_db.wset(ctx.chat["id"], "scene", sc)
    view = _outcome_view(ctx, char_id)
    assert "sealed writ" not in view, (
        f"another body's interoception reached this mind: {view!r}")
