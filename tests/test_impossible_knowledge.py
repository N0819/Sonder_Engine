"""A speaker who names what only this mind knows is handed as a fact.

The firewall is a gap, and the gap is generative only while a mind can notice
it being crossed. Measured (scratch play 2026-09-14, chat 2 turn 12): a
stranger asked Bram Toll "Your sister. Wen. What's wrong with her?" -- a name
held only in his card's `knowledge.private_history` with `known_by: []` --
and he answered as though the name were public, because nothing in his
payload said it was not. `perception.impossible_knowledge` is that one fact,
computed by `agents/impossible_knowledge.py` from the mind's own private
history and the words its view already carries.

The proofs here are the firewall's: the cue names ONLY this mind's own
private matter, never another mind's; it is absent whenever the word has a
channel (a public history, a cast name, a room, a `known_by` naming the
speaker, a prior line in the story); and it is absent when the line was not
handed to this observer at all. Nothing here widens what a mind receives.
"""

from __future__ import annotations

import json
import time

import pytest

from agents.impossible_knowledge import (
    aired_in_story,
    impossible_knowledge_cues,
    naming_tokens,
)
from core.pipeline_context import ChatData, PipelineContext, TurnData
from llm.prompts import CHARACTER_BLOCK_KEYS, DEFAULT_PROMPTS, character_prompt
from story.character_schema import default_character_data, default_persona_data


BRAM_PRIVATE = ("Left the coast to buy his sister Wen's medicine; the last "
                "of the money went on the passage.")
PLAYER_LINE = "Your sister. Wen. What's wrong with her?"


def _cues(**overrides):
    kwargs = dict(
        own_entries=[{"content": BRAM_PRIVATE, "known_by": []}],
        lines=[("Ysolde Marr", PLAYER_LINE)],
        delivered=[("current:7:0", "The room is low and close."),
                   ("current:7:1", 'The gaunt woman says, "%s"' % PLAYER_LINE)],
        public_texts=["Bram Toll", "Ysolde Marr", "The Hold", "a deckhand"],
        speaker_keys={"Ysolde Marr": {"ysolde marr", "ysolde"}},
        already_aired=lambda token: False,
        label=lambda name: "the gaunt woman",
    )
    kwargs.update(overrides)
    return impossible_knowledge_cues(**kwargs)


# --- the rule, as a pure function ----------------------------------------

def test_a_stranger_naming_a_private_matter_is_cued():
    assert _cues() == [{
        "speaker": "the gaunt woman",
        "line_ref": "current:7:1",
        "private_matter": BRAM_PRIVATE,
    }]


def test_the_speaker_is_what_this_observer_may_call_them():
    """The cue is handed to a mind that has not been introduced, so it names
    the speaker the way the view beside it does -- never canonically."""
    cues = _cues()
    assert "Ysolde" not in json.dumps(cues)


@pytest.mark.parametrize("public", [
    # The name is in somebody's public history.
    ["Bram Toll left the coast for his sister Wen's sake."],
    # The name is a cast member's.
    ["Wen Toll"],
    # The name is a room's.
    ["Wen's Landing"],
    # The name is in lore this mind may read.
    ["The apothecary at the quay still owes Wen for the last delivery."],
])
def test_a_name_with_a_channel_is_never_cued(public):
    assert _cues(public_texts=["Bram Toll", "Ysolde Marr"] + public) == []


def test_a_matter_shared_with_the_speaker_is_not_impossible():
    shared = [{"content": BRAM_PRIVATE, "known_by": ["Ysolde Marr"]}]
    assert _cues(own_entries=shared) == []
    # Any name the speaker answers to, not only the canonical spelling.
    shared = [{"content": BRAM_PRIVATE, "known_by": ["ysolde"]}]
    assert _cues(own_entries=shared) == []
    # But a matter shared with somebody ELSE is still impossible for this
    # speaker: whom they got it from is exactly the question to appraise.
    shared = [{"content": BRAM_PRIVATE, "known_by": ["Mira Kesh"]}]
    assert len(_cues(own_entries=shared)) == 1


def test_a_line_not_handed_to_this_observer_leaves_no_cue():
    # Out of earshot, withheld, or muffled to a fragment that lost the word.
    assert _cues(delivered=[("current:7:0", "The room is low and close.")]) == []
    assert _cues(delivered=[("current:7:1",
                             "A muffled voice: ...sister... wrong...")]) == []


def test_a_word_already_aired_in_the_story_is_not_cued():
    assert _cues(already_aired=lambda token: token == "wen") == []


def test_the_second_mind_to_say_it_this_beat_has_a_channel():
    """Two lines in one beat name the word: the first speaker had no channel,
    the second heard the first."""
    cues = _cues(
        lines=[("Ysolde Marr", PLAYER_LINE),
               ("Mira Kesh", "Wen? Who is Wen?")],
        delivered=[("current:7:1", 'The gaunt woman says, "%s"' % PLAYER_LINE),
                   ("current:7:2", 'Mira Kesh says, "Wen? Who is Wen?"')],
        speaker_keys={"Ysolde Marr": {"ysolde marr"}, "Mira Kesh": {"mira kesh"}},
        label=lambda name: name,
    )
    assert [c["speaker"] for c in cues] == ["Ysolde Marr"]


def test_the_cue_points_at_the_observation_that_carried_the_word():
    cues = _cues(delivered=[
        ("current:7:0", "The gaunt woman looks up from the rail."),
        ("current:7:3", 'The gaunt woman says, "%s"' % PLAYER_LINE),
    ])
    assert [c["line_ref"] for c in cues] == ["current:7:3"]


def test_naming_tokens_reads_capitalisation_not_a_list():
    """What counts as a name is how the text writes it: capitalised where no
    sentence begins, and never in lower case in the same text."""
    assert naming_tokens(BRAM_PRIVATE) == {"wen"}
    assert naming_tokens("The medicine ran out. The shop was shut.") == set()
    # A title before a name is not the name (the same floor every name
    # comparison uses), and a word the text also writes in lower case is a
    # word.
    assert naming_tokens("He serves under Commander Riker on the Coast; "
                         "the coast is his.") == {"riker"}
    # A sentence-initial capital after a quotation mark is still initial.
    assert naming_tokens('She said: "Wait for me."') == set()
    # An uncased script gives no signal and therefore no cue.
    assert naming_tokens("妹のウェンの薬を買いに来た。") == set()


# --- the payload, end to end ---------------------------------------------

def _story(temp_db, *, persona_name="Ysolde Marr"):
    persona = default_persona_data(persona_name)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (persona_name, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,persona_id,created) VALUES(?,?,?,?)",
        ("Impossible knowledge", "", persona_id, time.time()))
    return chat_id, persona_id


def _attach(temp_db, chat_id, name, private, uid):
    sheet = default_character_data(name)
    sheet["knowledge"]["private_history"] = [
        {"content": private, "known_by": []}]
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time(), uid))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    return char_id


def _context(temp_db, chat_id, persona_id, cast, idx, player_line):
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, idx, player_line, time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Impossible knowledge",
                      persona_id=persona_id, lorebook_id=None, scenario="",
                      created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=idx,
                      player_input=player_line, created=time.time()),
        cast=cast, input=player_line)
    ctx.director_interpret = {
        "flow": {"reactors": [int(c["id"]) for c in cast], "tom_triggers": []},
        "sequence": [{"type": "speech", "text": player_line,
                      "volume": "normal"}],
        "speech": player_line,
    }
    return ctx


def _payload_for(temp_db, monkeypatch, ctx, cid):
    import agents.character as character_module
    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["payload"] = payload
        return {"sequence": []}

    monkeypatch.setattr(character_module, "_agent_json", fake_agent_json)
    character_module.character_step(ctx, cid, nonce=0)
    return captured["payload"]


def _seed(temp_db, monkeypatch, *, heard_by_bram, prior_dialogue=None):
    chat_id, persona_id = _story(temp_db)
    bram = _attach(temp_db, chat_id, "Bram Toll", BRAM_PRIVATE, "char_bram")
    mira = _attach(temp_db, chat_id, "Mira Kesh",
                   "Her brother Anselm deserted the levy at Harrow.",
                   "char_mira")
    temp_db.wset(chat_id, "scene", {
        "location": "The Hold", "time": "night",
        "rooms": {"hold": {"name": "The Hold", "adjacent": []}},
        "positions": {"Bram Toll": "hold", "Mira Kesh": "hold",
                      "Ysolde Marr": "hold"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    if prior_dialogue:
        tid = temp_db.qi("INSERT INTO turns(chat_id,idx,created) VALUES(?,?,?)",
                         (chat_id, 11, 0.0))
        sid = temp_db.qi(
            "INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
            (tid, "director_resolve", "", 0))
        temp_db.qi(
            "INSERT INTO variants(step_id,content,created,active) "
            "VALUES(?,?,?,1)",
            (sid, json.dumps({"dialogue_log": prior_dialogue}), 0.0))
    line = "Your sister. Wen. What's wrong with her? And Anselm -- Harrow?"
    ctx = _context(temp_db, chat_id, persona_id, cast, 12, line)
    quoted = 'The gaunt woman says, "%s"' % line
    ctx.perception_act = {
        "views": {str(bram): quoted if heard_by_bram else "The hold is dark.",
                  str(mira): quoted},
        "observations": {
            str(bram): ([{"observation_id": f"current:{bram}:0",
                          "channel": "hearing",
                          "observed": {"text": quoted}}]
                        if heard_by_bram else
                        [{"observation_id": f"current:{bram}:0",
                          "channel": "sight",
                          "observed": {"text": "The hold is dark."}}]),
            str(mira): [{"observation_id": f"current:{mira}:0",
                         "channel": "hearing", "observed": {"text": quoted}}],
        },
    }
    return ctx, bram, mira


def test_the_cue_names_only_this_minds_own_private_matter(temp_db, monkeypatch):
    """Two minds, two secrets, one line naming both: each payload cues its
    own matter and carries no trace of the other's."""
    ctx, bram, mira = _seed(temp_db, monkeypatch, heard_by_bram=True)
    bram_payload = _payload_for(temp_db, monkeypatch, ctx, bram)
    cues = bram_payload["perception"]["impossible_knowledge"]
    assert [c["private_matter"] for c in cues] == [BRAM_PRIVATE]
    # The wire payload carries observations under short handles, and the cue
    # points at its line by the SAME handle -- the one the sheet tells the
    # mind to cite.
    assert cues[0]["line_ref"] == \
        bram_payload["perception"]["observations"][0]["observation_id"]
    assert cues[0]["line_ref"].startswith("o")
    # Mira's secret is in the line Bram heard, legitimately; it is not in
    # any cue of his, because it is not his matter.
    assert "Anselm" not in json.dumps(cues)
    assert "Harrow" not in json.dumps(cues)
    # The speaker is a stranger to Bram, so the cue calls her what his view
    # calls her -- never by the name he has not been given.
    assert cues[0]["speaker"] and "Ysolde" not in cues[0]["speaker"]

    mira_payload = _payload_for(temp_db, monkeypatch, ctx, mira)
    cues = mira_payload["perception"]["impossible_knowledge"]
    assert [c["private_matter"] for c in cues] == [
        "Her brother Anselm deserted the levy at Harrow."]
    assert "Wen" not in json.dumps(mira_payload["perception"]["impossible_knowledge"])


def test_no_cue_when_the_line_did_not_reach_this_mind(temp_db, monkeypatch):
    ctx, bram, _mira = _seed(temp_db, monkeypatch, heard_by_bram=False)
    payload = _payload_for(temp_db, monkeypatch, ctx, bram)
    assert "impossible_knowledge" not in payload["perception"]


def test_a_matter_this_mind_already_said_aloud_is_not_cued(temp_db, monkeypatch):
    """`known_by` is authored and never written at runtime, so the record of
    what has been aired is the story's own dialogue: a word Bram said on an
    earlier beat has a channel, whoever heard it."""
    ctx, bram, _mira = _seed(
        temp_db, monkeypatch, heard_by_bram=True,
        prior_dialogue=[{"speaker": "Bram Toll",
                         "exact_quote": "My sister Wen is ill."}])
    payload = _payload_for(temp_db, monkeypatch, ctx, bram)
    assert "impossible_knowledge" not in payload["perception"]


def test_aired_in_story_matches_whole_words_only(temp_db):
    chat_id, _pid = _story(temp_db)
    tid = temp_db.qi("INSERT INTO turns(chat_id,idx,created) VALUES(?,?,?)",
                     (chat_id, 3, 0.0))
    sid = temp_db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                     (tid, "director_resolve", "", 0))
    temp_db.qi(
        "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
        (sid, json.dumps({"dialogue_log": [
            {"speaker": "Mira Kesh", "exact_quote": "Wendell owes me."}],
            "resolved_event": "Wen is named in the narration only."}), 0.0))
    # `Wendell` is not `Wen`, and narration is not a channel.
    assert aired_in_story(chat_id, None, 4, "wen") is False
    temp_db.qi(
        "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,0)",
        (sid, json.dumps({"dialogue_log": [
            {"speaker": "Mira Kesh", "exact_quote": "Wen owes me."}]}), 0.0))
    # An inactive variant is not the story.
    assert aired_in_story(chat_id, None, 4, "wen") is False
    tid2 = temp_db.qi("INSERT INTO turns(chat_id,idx,created) VALUES(?,?,?)",
                      (chat_id, 2, 0.0))
    sid2 = temp_db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                      (tid2, "director_interpret", "", 0))
    temp_db.qi(
        "INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
        (sid2, json.dumps({"sequence": [
            {"type": "speech", "text": "Tell Wen I asked."}]}), 0.0))
    assert aired_in_story(chat_id, None, 4, "wen") is True
    # Only beats BEFORE the one being played count.
    assert aired_in_story(chat_id, None, 2, "wen") is False


# --- the prompt states the class -----------------------------------------

def test_the_character_prompt_states_the_class():
    text = DEFAULT_PROMPTS["character"]
    assert "WHAT THEY COULD NOT KNOW:" in text
    assert "`perception.impossible_knowledge`" in text
    # The class, not an instance: knowledge with no channel behind it is an
    # event, and the sentence names no story's name.
    assert "no channel" in text
    assert "event to appraise" in text
    assert "Wen" not in text


def test_the_paragraph_is_gated_on_the_cue_being_present():
    assert ("WHAT THEY COULD NOT KNOW:", ("perception.impossible_knowledge",)) \
        in CHARACTER_BLOCK_KEYS
    base = DEFAULT_PROMPTS["character"]
    empty = {"self": {}, "memory": {}, "perception": {}, "decision": {}}
    assert "WHAT THEY COULD NOT KNOW:" not in character_prompt(empty, base=base)
    present = {"self": {}, "memory": {}, "decision": {}, "perception": {
        "impossible_knowledge": [{"speaker": "the gaunt woman",
                                  "line_ref": "current:7:1",
                                  "private_matter": BRAM_PRIVATE}]}}
    assert "WHAT THEY COULD NOT KNOW:" in character_prompt(present, base=base)
