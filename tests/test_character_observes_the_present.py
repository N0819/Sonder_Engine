"""A character must react to the beat in front of it, not the one before.

Found in a live 61-turn chat ("The Doctor — Hinami ⎇14 ⎇17 ⎇16 ⎇23 ⎇54"),
where the Doctor kept answering the previous line. On the turn where the
player said "Why are you looking at me like that, you brought me here?", the
Doctor's considered_responses were about asking what she meant by "future is
weird" -- the line from the turn BEFORE -- and its cited observation resolved
to a `memories` row stamped turn_idx 59 on turn 60.

The cause is structural rather than a stale read. `observations_used` asks the
character to cite an `event_id`; the ONLY ids in its payload belong to memory
rows, and `recent_memory_buffer` deliberately excludes the current turn (audit
#10 -- a mind must not see how the turn it is deciding turned out). So the
present beat arrived as an uncitable prose string while the past arrived with
ids attached, and the model reached for what it could cite. Across that chat:
15 citations of a previous turn, 0 of the current one, ever.
"""

from __future__ import annotations

import json
import time

import memory
from agents.character import _ground_observation_citations
from character_schema import default_character_data
from schemas import EvidenceRef


def _chat_and_char(db, name="Alice"):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()),
    )
    return chat_id, char_id


def test_memory_payload_does_not_duplicate_the_present(temp_db):
    """Present perception/mood/goal live in their own payload branches."""
    ctx = memory.build_character_memory_context(
        chat_id=1, char_id=1, current_turn_idx=5,
        current_view="She says: 'Why are you looking at me like that?'",
        active_state={"mood": "attentive", "goal": "investigate"})

    assert "working_memory" not in ctx
    assert "Why are you looking at me" not in json.dumps(ctx)
    assert ctx["_internal"]["row_ids"] == {}


def test_every_real_event_id_is_older_than_this_turn(temp_db):
    """Documents WHY the sentinel is needed rather than only asserting it: the
    exclusion below is correct and deliberate, so the present beat can never
    acquire a real id before it commits.

    Asserted against a NON-EMPTY bank on purpose. The same assertion over an
    empty bank passes vacuously and would have kept passing through audit F1,
    when `search_memories` had no turn cutoff at all.
    """
    chat_id, char_id = _chat_and_char(temp_db)

    # Turn 5 is the turn being decided; its outcome memory is already
    # committed, which is exactly the state a reroll or a rerun-from-stage
    # replays the onset in. Turn 6 stands in for a later play-order row --
    # a branch or another frame can leave one sitting ahead of this turn.
    memory.add_memory(chat_id, char_id, None, "episode", "witnessed", 0.9,
                      "The door opened and the stranger shot me.", turn_idx=5,
                      gist="shot by the stranger")
    memory.add_memory(chat_id, char_id, None, "episode", "witnessed", 0.9,
                      "A door opens somewhere later.", turn_idx=6,
                      gist="a door opens later")
    # An older memory, so the recall is not empty for a boring reason.
    memory.add_memory(chat_id, char_id, None, "episode", "witnessed", 0.9,
                      "A door opened onto the ward last week.", turn_idx=2,
                      gist="a door opened onto the ward")

    ctx = memory.build_character_memory_context(
        chat_id=chat_id, char_id=char_id, current_turn_idx=5,
        current_view="A door opens.", active_state={})

    episodes = ctx["recent_episodes"] + ctx["recalled_old_memories"]
    assert episodes, "bank must be non-empty or this test is vacuous"
    assert all(episode["temporal_status"] == "remembered_past"
               for episode in episodes)
    contents = " ".join(str(e.get("details") or "") for e in episodes)
    assert "shot me" not in contents
    assert "somewhere later" not in contents
    assert "onto the ward" in contents


def test_the_prompt_says_which_one_to_cite():
    """The payload change alone is not enough -- the model reached for real
    ids because they looked authoritative, so the rule is stated too."""
    source = open("prompts.py", encoding="utf-8").read()
    assert "EVIDENCE HAS TWO LANES" in source
    assert "ids from perception.observations" in source
    # The reason, not just the instruction: a rule without its why is the
    # first thing an editor drops.
    assert "memory in the present lane" in source


def test_legacy_present_citations_normalize_without_touching_real_ids():
    assert EvidenceRef(event_id="current_perception").event_id == "current"
    assert EvidenceRef(event_id="perception:view").event_id == "current"
    assert EvidenceRef(event_id="current:35:2").event_id == "current:35:2"


def test_memory_rows_and_present_observations_use_disjoint_namespaces(temp_db):
    chat_id, char_id = _chat_and_char(temp_db)
    mid = memory.add_memory(
        chat_id, char_id, None, "episode", "witnessed", 0.9,
        "Yesterday the brass door opened onto the ward.", turn_idx=2,
        gist="the brass door opened")
    ctx = memory.build_character_memory_context(
        chat_id, char_id, current_turn_idx=5,
        current_view="The brass door is shut now.", active_state={})
    rows = ctx["recent_episodes"] + ctx["recalled_old_memories"]
    projected = next(row for row in rows
                     if "brass door" in row.get("gist", ""))
    assert projected["memory_ref"].startswith("event:")
    assert projected["temporal_status"] == "remembered_past"
    assert projected["when"] == "about 3 beats ago"
    assert projected["epistemic_origin"] == "what_i_experienced"
    assert "id" not in projected and "event_key" not in projected


def test_citation_guard_separates_present_from_delivered_memory():
    out = {"observations_used": [
        {"event_id": "42", "fact": "the old alarm rang"},
        {"event_id": "invented", "fact": "not delivered"},
        {"event_id": "current:35:0", "fact": "the corridor is quiet"},
    ]}
    observations = [{
        "observation_id": "current:35:0",
        "observed": {"text": "The corridor is quiet now."},
    }]
    memory_context = {
        "recent_episodes": [{
            "id": 42, "event_key": "event:old-alarm",
            "memory_ref": "event:old-alarm", "gist": "the old alarm rang"}],
        "recalled_old_memories": [],
    }
    warnings = _ground_observation_citations(
        out, observations, memory_context)
    assert out["observations_used"] == [
        {"event_id": "current:35:0", "fact": "the corridor is quiet"},
        {"event_id": "event:old-alarm", "fact": "the old alarm rang"},
    ]
    assert out["present_evidence_used"] == [
        {"event_id": "current:35:0", "fact": "the corridor is quiet"}]
    assert out["memory_evidence_used"] == [
        {"event_id": "event:old-alarm", "fact": "the old alarm rang"}]
    assert any("ungrounded" in warning for warning in warnings)


def test_citation_guard_accepts_only_a_delivered_summary_id():
    out = {"observations_used": [
        {"event_id": "summary:autobiographical:9", "fact": "the old ward"},
        {"event_id": "autobiographical_summary", "fact": "field label"},
        {"event_id": "current:7:0", "fact": "the ward is quiet"},
    ]}
    observations = [{
        "observation_id": "current:7:0",
        "observed": {"text": "The ward is quiet now."},
    }]
    memory_context = {
        "recent_episodes": [], "recalled_old_memories": [],
        "summary_citations": {
            "autobiographical_summary": {
                "summary_id": "summary:autobiographical:9"}},
    }
    warnings = _ground_observation_citations(
        out, observations, memory_context)
    assert [r["event_id"] for r in out["observations_used"]] == [
        "current:7:0", "summary:autobiographical:9"]
    assert any("autobiographical_summary" in warning for warning in warnings)


def test_every_evidence_ref_is_grounded_against_the_delivered_registry():
    out = {
        "observations_used": [
            {"event_id": "current:7:0", "fact": "quiet now"}],
        "belief_updates": [{"belief": "the bell once rang", "evidence": [
            {"event_id": "9", "fact": "old bell"},
            {"event_id": "not-delivered", "fact": "invented"}]}],
        "association_updates": [{"cue": "bells", "evidence": [
            {"event_id": "event:old-bell", "fact": "old bell"}]}],
        "mind_model_updates": [{"about_entity": "Mara", "kind": "goal",
            "claim": "she avoids bells", "evidence": [
                {"event_id": "event:old-bell", "fact": "old bell"}]}],
    }
    context = {"recent_episodes": [{
        "id": 9, "event_key": "event:old-bell",
        "memory_ref": "event:old-bell", "gist": "old bell"}]}
    warnings = _ground_observation_citations(
        out, [{"observation_id": "current:7:0",
               "observed": {"text": "quiet now"}}], context)
    assert out["belief_updates"][0]["evidence"] == [
        {"event_id": "event:old-bell", "fact": "old bell"}]
    assert out["association_updates"][0]["evidence"][0]["event_id"] == \
        "event:old-bell"
    assert out["mind_model_updates"][0]["evidence"][0]["event_id"] == \
        "event:old-bell"
    assert any("not-delivered" in warning for warning in warnings)


def test_guard_warns_but_does_not_fabricate_a_present_citation():
    out = {"observations_used": [
        {"event_id": "event:old-bell", "fact": "old bell"}]}
    context = {"recent_episodes": [{
        "id": 9, "event_key": "event:old-bell",
        "memory_ref": "event:old-bell", "gist": "old bell"}]}
    warnings = _ground_observation_citations(
        out, [{"observation_id": "current:7:0",
               "observed": {"text": "quiet now"}}], context)
    assert out["observations_used"] == [
        {"event_id": "event:old-bell", "fact": "old bell"}]
    assert any("no delivered present" in warning for warning in warnings)
