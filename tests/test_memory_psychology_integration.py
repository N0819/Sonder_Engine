"""The character/psychology boundary must preserve memory's epistemic shape."""

import json
import time

from mind import memory
from agents.character import _ground_observation_citations
from agents.common import _merge_character_results, norm_sequence
from story.character_schema import default_character_data
from llm.prompts import DEFAULT_PROMPTS


def _chat_and_char(db, name="Mara"):
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Memory psychology", "", time.time()))
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time()))
    return chat_id, char_id


def test_present_appraisal_and_memory_modulation_are_grounded_separately():
    out = {
        "present_evidence_used": [{"event_id": "current:7:0"}],
        "memory_evidence_used": [{"event_id": "event:bell", "use": "recognition"}],
        "appraisal": {
            "present_evidence": [{"event_id": "current:7:0"}],
            "memory_modulation": {
                "evidence": [{"event_id": "event:bell"}],
                "familiarity": .8, "coping_effect": .4,
                "somatic_echo": -.7, "threat_bias": .6,
                "why": "the bell recalls the old alarm"},
            "somatic_impact": {
                "pain": .8, "why": "invented", "evidence": []},
            "goal_impacts": [{"impact": -.7, "evidence": []}],
        },
        "belief_updates": [{"belief": "summary must be true", "evidence": [
            {"event_id": "summary:autobiographical:9"}]}],
    }
    context = {
        "recent_episodes": [{"memory_ref": "event:bell", "gist": "old bell"}],
        "summary_citations": {"autobiographical_summary": {
            "summary_id": "summary:autobiographical:9"}},
    }
    warnings = _ground_observation_citations(
        out,
        [{"observation_id": "current:7:0",
          "observed": {"text": "A bell rings now."}}],
        context)

    assert out["present_evidence_used"][0]["event_id"].startswith("current:")
    assert out["memory_evidence_used"][0]["event_id"].startswith("event:")
    assert out["appraisal"]["memory_modulation"]["familiarity"] == .8
    assert out["appraisal"]["memory_modulation"]["somatic_echo"] == -.7
    assert out["appraisal"]["memory_modulation"]["threat_bias"] == .6
    assert out["appraisal"]["somatic_impact"]["pain"] == 0.0
    assert out["appraisal"]["goal_impacts"][0]["impact"] == 0.0
    assert out["belief_updates"] == []
    assert any("unsupported" in warning for warning in warnings)


def test_ungrounded_memory_echo_cannot_reach_psychology():
    out = {"appraisal": {"memory_modulation": {
        "evidence": [{"event_id": "event:not-delivered"}],
        "somatic_echo": -1.0, "threat_bias": 1.0,
        "why": "remembered danger"}}}
    _ground_observation_citations(out, [], {"recalled_old_memories": []})
    modulation = out["appraisal"]["memory_modulation"]
    assert modulation["evidence"] == []
    assert modulation["somatic_echo"] == 0.0
    assert modulation["threat_bias"] == 0.0
    assert modulation["why"] == ""


def test_micro_round_merge_keeps_memory_outputs_from_every_round():
    merged = _merge_character_results(
        {"sequence": [],
         "present_evidence_used": [{"event_id": "current:1:micro:0"}],
         "remember_lines": [{"quote": "first", "why": "a"}],
         "memory_effects": [{"memory_ref": "event:a", "changed": "goal"}]},
        {"sequence": [],
         "present_evidence_used": [{"event_id": "current:1:micro:1"}],
         "memory_disputes": [{"memory_ref": "event:b", "now_reads": "trap"}]})
    assert [e["event_id"] for e in merged["present_evidence_used"]] == [
        "current:1:micro:0", "current:1:micro:1"]
    assert merged["remember_lines"][0]["quote"] == "first"
    assert merged["memory_effects"][0]["memory_ref"] == "event:a"
    assert merged["memory_disputes"][0]["memory_ref"] == "event:b"


def test_ponder_is_extracted_as_private_state_not_public_conduct():
    out = {
        "sequence": [
            {"type": "ponder", "query": "  who carried the violet sigil?  ",
             "why": "I need to decide whom to trust."},
            {"type": "speech", "text": "Give me a moment."},
        ]}
    norm_sequence(out)
    assert out["ponder"] == {
        "type": "ponder",
        "query": "who carried the violet sigil?",
        "why": "I need to decide whom to trust.",
    }
    assert [item["type"] for item in out["sequence"]] == ["speech"]


def test_dispute_uses_stable_memory_ref_not_approximate_gist(temp_db):
    chat_id, char_id = _chat_and_char(temp_db)
    memory.add_memory(
        chat_id, char_id, None, "episode", "witnessed", .8,
        "Two similar vials stood on the tray.", turn_idx=1,
        gist="a vial on the tray", event_key="event:first")
    memory.add_memory(
        chat_id, char_id, None, "episode", "witnessed", .8,
        "Another similar vial stood on the tray.", turn_idx=2,
        gist="a vial on the tray", event_key="event:second")
    changed = memory.record_dispute(
        chat_id, char_id, "a vial on the tray", "the second was poison", 3,
        memory_ref="event:second")
    assert len(changed) == 1
    rows = temp_db.q(
        "SELECT event_key, disputed FROM memories WHERE chat_id=? ORDER BY event_key",
        (chat_id,))
    assert rows[0]["disputed"] == ""
    assert "poison" in rows[1]["disputed"]


def test_absorption_narrows_deliberative_recall_without_erasing_it(temp_db):
    chat_id, char_id = _chat_and_char(temp_db)
    import random
    words = ("anchor bramble cinder dovetail ember falcon garnet harbour ivory juniper "
             "kettle lantern meadow nettle orchard pebble quarry rafter saffron thistle "
             "umber velvet willow yarrow").split()
    for turn in range(1, 25):
        # Distinct rows: one sentence with its numbers changed is one memory
        # reworded to recall's near-duplicate cut, which keeps one of them.
        detail = " ".join(random.Random(turn).sample(words, 6))
        memory.add_memory(
            chat_id, char_id, None, "episode", "witnessed", .7,
            f"The brass door rang; {detail}.",
            turn_idx=turn, gist=f"brass door {detail}")
    low = memory.build_character_memory_context(
        chat_id, char_id, 30, "The brass door rings.", {}, absorption=0.0)
    high = memory.build_character_memory_context(
        chat_id, char_id, 30, "The brass door rings.", {}, absorption=.9)
    assert len(low["recalled_old_memories"]) > len(
        high["recalled_old_memories"])
    assert len(high["recent_memories"]) <= 4
    assert len(high["recalled_old_memories"]) <= 4
    assert high["recent_memories"] or high["recalled_old_memories"]


def test_ponder_adds_labelled_recall_without_replacing_normal_recall(temp_db):
    chat_id, char_id = _chat_and_char(temp_db)
    for turn in range(1, 31):
        gist = ("Mara saw the violet sigil beneath Rowan's glove"
                if turn == 3 else f"ordinary market errand number {turn}")
        memory.add_memory(
            chat_id, char_id, None, "episode", "witnessed", .7,
            gist, turn_idx=turn, gist=gist,
            event_key=("event:violet" if turn == 3 else f"event:errand:{turn}"))
    ordinary = memory.build_character_memory_context(
        chat_id, char_id, 40, "Rain falls in the empty square.", {})
    pondered = memory.build_character_memory_context(
        chat_id, char_id, 40, "Rain falls in the empty square.", {},
        ponder_query="Who carried the violet sigil?")

    assert [m["memory_ref"] for m in ordinary["recalled_old_memories"]] == [
        m["memory_ref"] for m in pondered["recalled_old_memories"]]
    deliberate = pondered["deliberate_recall"]
    assert deliberate["query_i_chose_last_turn"] == (
        "Who carried the violet sigil?")
    assert deliberate["retrieval_origin"] == "deliberate_ponder"
    assert deliberate["may_set_another_ponder_this_turn"] is True
    assert "event:violet" in deliberate["result_refs"]
    delivered = {
        m["memory_ref"]: m
        for m in (pondered["recent_memories"]
                  + pondered["recalled_old_memories"]
                  + deliberate["additional_episodes"])}
    assert "deliberate_ponder" in delivered["event:violet"]["retrieval_origin"]


def test_recent_memory_is_one_chronological_stream_each_row_saying_its_kind(
        temp_db):
    """The owner, 2026-09-28: "better ordered in chronological order rather
    than by type, type obviously still needs to be attached to each entry".
    Written across three turns so the old grouping (episodes, then what was
    told, then conclusions) would have put them in a different order."""
    chat_id, char_id = _chat_and_char(temp_db)
    memory.add_memory(
        chat_id, char_id, None, "inference", "inferred", .6,
        "Mara expected pursuit.", turn_idx=6, event_key="event:inference")
    memory.add_memory(
        chat_id, char_id, None, "episode", "witnessed", .8,
        "You step away and the contact ends.", turn_idx=7,
        event_key="event:episode")
    memory.add_memory(
        chat_id, char_id, None, "dialogue", "heard", .8,
        "Mara said 'wait'", turn_idx=8, event_key="event:line")

    context = memory.build_character_memory_context(
        chat_id, char_id, 9, "The room is still.", {})

    assert [(m["memory_ref"], m["epistemic_origin"])
            for m in context["recent_memories"]] == [
        ("event:inference", "what_i_concluded"),
        ("event:episode", "what_i_experienced"),
        ("event:line", "what_i_was_told")]
    for lane in ("recent_episodes", "recent_received_information",
                 "recent_conclusions"):
        assert lane not in context


def test_encoding_affect_round_trips_through_snapshot_restore(temp_db):
    chat_id, char_id = _chat_and_char(temp_db)
    memory.add_memory(
        chat_id, char_id, None, "episode", "witnessed", .8,
        "The hatch opened.", turn_idx=1, event_key="event:hatch",
        valence=-.2, arousal=.3,
        encoding_valence=.65, encoding_arousal=.8)
    dumped = memory.dump_chat_memories(chat_id)
    assert dumped[0]["encoding_valence"] == .65
    memory.restore_chat_memories(chat_id, dumped)
    row = temp_db.q(
        "SELECT valence, arousal, encoding_valence, encoding_arousal "
        "FROM memories WHERE chat_id=?", (chat_id,), one=True)
    assert tuple(row) == (-.2, .3, .65, .8)


# `test_character_prompt_does_not_launder_claim_origin_through_memory_form`
# went with the full card (2026-09-27): the bare card does not state that a
# received line is not a memory of one's own, nor bound `ponder` in words --
# the memory keys are named for their status (`what_i_was_told`,
# `what_i_concluded`) and recorded open in docs/UNBUILT_CHARACTERS.md §6.17.
