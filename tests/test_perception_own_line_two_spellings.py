"""Your own line came back to you as a stranger's, because it was spelled twice.

One being, one name -- and a being routinely carries two at once, a cast
display name and a scene entity id. `_composer_outcome` suppressed an
observer's own speech and their own act with `==` between those two
spellings, twelve lines above a mover check that correctly asks
`same_subject`. Where the Director logged a line under the entity id and the
observer's perceiver record carried the display name (or the reverse), the
equality was False, the suppression did not fire, and the observer's view
delivered their own sentence back to them attributed to somebody else.

Not a leak -- nothing crossed a gap that should not have. It is worse in a
quieter way: a mind reads a line it just spoke as evidence that a second
person is in the room saying it.
"""

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


PLAYER = "Hinami"
SPEAKER = "Tamamo"
SPEAKER_EID = "tamamo_1"
LINE = "The lamps are out along the west wing."


def _ctx(temp_db, *, dialogue_log=None, acts=None):
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Spellings", "", time.time(), persona_id))
    sheet = default_character_data(SPEAKER)
    sheet.setdefault("embodiment", {}).setdefault("visible", {})["summary"] = (
        "A fox-eared young woman in shrine-maiden robes.")
    # The second spelling, and the documented reason there is one:
    # `character_scene_keys` -- "the director sometimes keys by identity.uid
    # (or an alias) -- so readers must try all of them".
    sheet.setdefault("identity", {})["uid"] = SPEAKER_EID
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (SPEAKER, json.dumps(sheet), "{}", time.time(), "char_t"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))

    # She exists under both spellings at once: the cast display name the
    # perceiver record is built from, and the scene entity id the Director
    # wrote her line under.
    temp_db.wset(chat_id, "scene", {
        "location": "the hall", "time": "night",
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "positions": {PLAYER: "hall", SPEAKER: "hall"},
        "entities": {SPEAKER_EID: {"name": SPEAKER, "kind": "person",
                                   "desc": "A shrine maiden."}},
        "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", {SPEAKER: [PLAYER]})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Spellings", persona_id=persona_id,
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
        "resolved_event": "The hall stands quiet.",
        "state_diff": {},
        "dialogue_log": list(dialogue_log or []),
        "dialogue_order": [],
        "events": list(acts or []),
    }
    return ctx, char_id


def _views(ctx):
    import agents.perception as perception
    return perception.perception_outcome(ctx, nonce="n")["views"]


def test_own_speech_logged_under_the_entity_id_is_still_own_speech(temp_db):
    """The defect: her line, logged under her entity id, delivered back to
    her as a line somebody else in the room said."""
    ctx, char_id = _ctx(temp_db, dialogue_log=[{
        "speaker": SPEAKER_EID, "exact_quote": LINE,
        "volume": "normal", "tone": "flat", "visibility": "overt",
    }])
    view = _views(ctx)[str(char_id)] or ""

    assert LINE not in view, (
        "an observer was handed their own line as another body's speech "
        f"because the two spellings of their name compared unequal: {view!r}")


def test_another_body_speaking_still_reaches_the_observer(temp_db):
    """The suppression must stop at the observer. A line from anyone else in
    the room is exactly what this loop exists to deliver."""
    ctx, char_id = _ctx(temp_db, dialogue_log=[{
        "speaker": PLAYER, "exact_quote": LINE,
        "volume": "normal", "tone": "flat", "visibility": "overt",
    }])
    view = _views(ctx)[str(char_id)] or ""

    assert LINE in view, (
        f"a co-present speaker's line did not reach the observer: {view!r}")
