"""Both decision-model passes around a character call read the psychology the
mind holds NOW -- the drive a rupture shifted it to, the cues its own ledger
has learned and extinguished -- not the card as authored.

The payload a mind is sent is built live: `self.psychology.drive` is
`effective_drive` (a rupture's `interior.drive_override` wins) and
`self.learned_associations` is the interior ledger, "the live one --
credence moves there, not on the card". The two passes beside it read the
CARD: `affect_pass.before_call(name, sh, ...)` appraised every event against
"WHAT DRIVES YOU: <old essence>", and `character_bare.holding_from` offered
the old essence as the `drive` aim and quoted extinguished cues as "WHAT
STIRS YOU, LEARNED" (review 2026-11-01, mind_affect_psychology F7). Both
now read it through `psychology_runtime.live_psychology` (L9's, the one
owner of the rule) off the mind's own ledger.
"""

from __future__ import annotations

from copy import deepcopy

from agents.character_bare import holding_from
from story.character_schema import default_character_data

OLD = "Keep the lighthouse lit through the winter"
NEW = "Find out who let the light go dark"


def _card():
    sheet = default_character_data("Mara")
    sheet["psychology"]["drive"] = {"essence": OLD, "expression": "tends the lamp",
                                    "taboo": "letting it fail"}
    sheet["psychology"].setdefault("learning", {})["associations"] = [
        {"cue": "a bell at night", "appraisal_bias": "dread", "response_tendency": "freeze"}]
    return sheet


LIVE_SELF = {
    "psychology": {"drive": {"essence": NEW, "expression": "asks questions",
                             "taboo": "lying to herself"}},
    "learned_associations": [
        {"cue": "a bell at night", "appraisal_bias": "dread", "strength": 0.0},
        {"cue": "salt wind", "appraisal_bias": "home", "strength": 0.6}],
}


def test_the_read_back_offers_the_drive_she_holds_now():
    h = holding_from("Mara", _card(), {"self": deepcopy(LIVE_SELF)}, [], {}, {})
    assert h.aims and h.aims[0]["kind"] == "drive" and h.aims[0]["text"] == NEW
    assert h.drive["essence"] == NEW
    assert NEW in h.psychology and OLD not in h.psychology


def test_a_cue_the_story_extinguished_no_longer_stirs_her_and_a_learned_one_does():
    h = holding_from("Mara", _card(), {"self": deepcopy(LIVE_SELF)}, [], {}, {})
    assert "salt wind" in h.psychology
    assert "a bell at night" not in h.psychology


def test_before_the_first_commit_the_card_is_the_only_copy():
    h = holding_from("Mara", _card(), {"self": {}}, [], {}, {})
    assert h.aims[0]["text"] == OLD and "a bell at night" in h.psychology


def test_the_mood_pass_is_handed_the_live_psychology(temp_db, monkeypatch):
    import agents.character as character
    import mind.affect_pass as affect_pass
    from llm import decisions
    from tests.test_character_bare import _answer
    seen = {}
    real = affect_pass.before_call

    def spy(name, sheet, *args, **kwargs):
        # What the pass will appraise against: the card read through the
        # ledger it is handed (`psychology_runtime.live_psychology`).
        seen["psychology"] = affect_pass.psychology_text(sheet, kwargs.get("interior"))
        return real(name, sheet, *args, **kwargs)

    monkeypatch.setattr(affect_pass, "before_call", spy)
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: _answer([])(questions))
    char_id, context = _mara(temp_db)
    monkeypatch.setattr(character, "_agent_json", lambda *a, **k: {
        "want": "ask", "held_back": "", "hinge": "", "unsure": "",
        "sequence": [{"do": "looks up at the dark lamp"}], "demeanor": "", "tells": [],
        "notebook": [], "changes": [], "note": ""})
    character.character_step(context, char_id, 1)
    assert NEW in seen["psychology"] and OLD not in seen["psychology"]


def _mara(temp_db):
    import json
    import time
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    now = time.time()
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Light", "", now))
    sheet = _card()
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", now, sheet["identity"]["uid"]))
    state = {"interior": {"drive_override": LIVE_SELF["psychology"]["drive"]}}
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
               (chat_id, char_id, "active", json.dumps(state)))
    temp_db.wset(chat_id, "scene", {
        "location": "Light", "rooms": {"lamp": {"name": "Lamp Room", "adjacent": []}},
        "positions": {"Mara": "lamp"}, "entities": {}, "attire": {}, "overlays": {}})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "Listen.", now))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Light", persona_id=None, lorebook_id=None,
                      scenario="", created=now),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="Listen.",
                      created=now),
        cast=cast, input="Listen.")
    ctx.director_interpret = {"flow": {"reactors": [char_id], "tom_triggers": []}}
    ctx.director_resolve = {"dialogue_log": []}
    ctx.perception_act = {"views": {str(char_id): "The lamp is dark."}}
    return char_id, ctx
