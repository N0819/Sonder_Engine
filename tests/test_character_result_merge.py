"""Regression test for the second-round character-result overwrite
(AUDIT_FINDINGS #19 / MEDIUM).

agents/loops.py's interaction_loop did `ctx.character_results[speaker_id] =
result` each round, so a character who spoke in more than one micro-round had
its earlier round's result (sequence, mind_model_updates, relationship_updates,
etc.) silently discarded before commit -- which reads
ctx.character_results[id] as that character's single result.

Fix: agents.common._merge_character_results concatenates the sequence and
unions the accumulating update fields, keeping the latest active_state.
"""

from __future__ import annotations

from agents import common
from agents.common import _merge_character_results
from llm.schemas import CharacterOutput


def _round0():
    return {
        "sequence": [{"type": "action", "attempt": "draws a blade"}],
        "mind_model_updates": [{"about_entity": "Kael", "kind": "goal", "claim": "flee"}],
        "relationship_updates": [{"target": "Kael", "trust": -0.1}],
        "intent_ops": [{"op": "add", "id": "escape"}],
        "contact_ops": [{"op": "remove", "contact_ref": "contact:0"}],
        "active_state": {"mood": "tense"},
    }


def _round1():
    return {
        "sequence": [{"type": "speech", "text": "Stand down."}],
        "mind_model_updates": [{"about_entity": "Mara", "kind": "goal", "claim": "help"}],
        "relationship_updates": [{"target": "Mara", "trust": 0.2}],
        "intent_ops": [{"op": "add", "id": "warn"}],
        "active_state": {"mood": "resolved"},
    }


def test_merge_preserves_round0_sequence_and_updates():
    merged = _merge_character_results(_round0(), _round1())

    attempts = [e.get("attempt") for e in merged["sequence"] if e.get("type") == "action"]
    texts = [e.get("text") for e in merged["sequence"] if e.get("type") == "speech"]
    assert "draws a blade" in attempts  # round-0 action survived
    assert "Stand down." in texts       # round-1 speech present

    about = {u["about_entity"] for u in merged["mind_model_updates"]}
    assert about == {"Kael", "Mara"}    # both rounds' inferences kept

    targets = {u["target"] for u in merged["relationship_updates"]}
    assert targets == {"Kael", "Mara"}

    intent_ids = {op["id"] for op in merged["intent_ops"]}
    assert intent_ids == {"escape", "warn"}
    assert merged["contact_ops"] == [
        {"op": "remove", "contact_ref": "contact:0"}]

    # Latest active_state wins.
    assert merged["active_state"] == {"mood": "resolved"}


def test_merge_dedupes_identical_repeated_updates():
    a = {"sequence": [], "mind_model_updates": [{"about_entity": "Kael", "kind": "goal", "claim": "flee"}]}
    b = {"sequence": [], "mind_model_updates": [{"about_entity": "Kael", "kind": "goal", "claim": "flee"}]}

    merged = _merge_character_results(a, b)

    assert len(merged["mind_model_updates"]) == 1


def test_merge_falls_back_to_existing_active_state_when_new_lacks_it():
    a = {"sequence": [], "active_state": {"mood": "tense"}}
    b = {"sequence": []}

    merged = _merge_character_results(a, b)

    assert merged["active_state"] == {"mood": "tense"}


def test_merge_tolerates_missing_existing():
    b = {"sequence": [{"type": "speech", "text": "hi"}]}
    assert _merge_character_results(None, b) == b


def test_merge_keeps_a_drive_shift_a_later_silent_round_omits():
    """The rupture proposal survives a round that says nothing about it.

    `drive_shift` is offered only inside an engine-opened three-turn window,
    so the one round that answers is the whole rupture. It reached commit
    through `elif own_result.get("drive_shift")` -- the single reader -- which
    means the drop took every warning about it along: a shift lost here was
    indistinguishable from a character who never proposed one.
    """
    shift = {"essence": "keep the ones I failed", "because": "she died"}
    earlier = {"sequence": [], "drive_shift": shift}
    later = {"sequence": [{"type": "speech", "text": "I have nothing to add."}]}

    assert _merge_character_results(earlier, later)["drive_shift"] == shift
    # ...and the same loss shape on the react-then-act path, where the
    # reaction is `existing` and the action result is `new`
    # (persist/commit_memory.py's own_result).
    assert _merge_character_results(
        {"drive_shift": shift}, {"sequence": [], "drive_shift": None},
    )["drive_shift"] == shift


def test_merge_lets_a_later_explicit_drive_shift_win():
    """Preserve-if-silent, not accumulate: the slot holds exactly one.

    affect.validate_drive_shift takes a single proposal and a break closes the
    window, so two proposals in one beat cannot both apply; the later explicit
    one is the character's current answer.
    """
    merged = _merge_character_results(
        {"drive_shift": {"essence": "first"}},
        {"drive_shift": {"essence": "second"}},
    )
    assert merged["drive_shift"] == {"essence": "second"}


def test_merge_keeps_a_barren_beat_flag_sticky():
    """A repeated move in round 0 still bars credit for round 0's ops.

    `_barren_beat` is set only when true and gates whether apply_intent_ops
    credits a `progress` claim; the intent_ops themselves accumulate. Under
    latest-wins the barren round's ops arrived at commit under the clean
    round's flag.
    """
    merged = _merge_character_results(
        {"_barren_beat": True, "intent_ops": [{"op": "progress", "id": "reach"}]},
        {"sequence": [], "intent_ops": [{"op": "add", "id": "warn"}]},
    )
    assert merged["_barren_beat"] is True
    assert len(merged["intent_ops"]) == 2


def test_every_character_output_field_is_classified():
    """The structural guard: no field may be latest-wins BY OMISSION.

    The merge builds from `new` alone, so a key nobody classified is silently
    latest-wins -- and for a sparse field that means dropped, with no warning,
    because a field's warnings live in the branch the drop skips. That is how
    `project_ops` was lost inside one loop and how `drive_shift` was lost
    across the react/act merge. This fails when a field is added to
    CharacterOutput and not put in one of the four tables, which forces the
    author to answer the question rather than inherit an answer.
    """
    fields = set(getattr(CharacterOutput, "model_fields", None)
                 or CharacterOutput.__fields__)
    tables = {
        "_MERGE_APPEND_FIELDS": common._MERGE_APPEND_FIELDS,
        "_MERGE_UNION_FIELDS": common._MERGE_UNION_FIELDS,
        "_MERGE_PRESERVE_FIELDS": common._MERGE_PRESERVE_FIELDS,
        "_MERGE_LATEST_WINS_FIELDS": common._MERGE_LATEST_WINS_FIELDS,
    }
    classified = set()
    for name, table in tables.items():
        assert len(set(table)) == len(table), f"{name} lists a key twice"
        overlap = classified & set(table)
        assert not overlap, f"{name} re-classifies {sorted(overlap)}"
        classified |= set(table)

    unclassified = fields - classified
    assert not unclassified, (
        "CharacterOutput field(s) %s are combined by nothing but `merged = "
        "dict(new)`. Add each to one of agents/common.py's four _MERGE_* "
        "tables -- _MERGE_LATEST_WINS_FIELDS is a legitimate answer, but it "
        "has to be stated." % sorted(unclassified))

    # A classified name that is not a schema field must be a KNOWN extra the
    # stage writes after validation (ponder, name, _barren_beat, ...) or a
    # legacy key commit still reads -- otherwise it is a typo, and a typo here
    # classifies nothing while looking like it does.
    extras = classified - fields
    assert extras == set(common._MERGE_NON_SCHEMA_KEYS), (
        "undocumented non-schema key(s) %s; _MERGE_NON_SCHEMA_KEYS says %s"
        % (sorted(extras - set(common._MERGE_NON_SCHEMA_KEYS)),
           sorted(set(common._MERGE_NON_SCHEMA_KEYS) - extras)))


def test_classified_tables_match_what_the_merge_actually_does():
    """The tables are not documentation -- the merge reads them.

    A table that drifted from behaviour would make the guard above worthless,
    so check one representative of each rule against a real merge.
    """
    for field in common._MERGE_UNION_FIELDS:
        merged = _merge_character_results(
            {field: [{"a": 1}]}, {"sequence": [], field: [{"b": 2}]})
        assert merged[field] == [{"a": 1}, {"b": 2}], field
    for field in common._MERGE_PRESERVE_FIELDS:
        merged = _merge_character_results({field: {"x": 1}}, {"sequence": []})
        assert merged[field] == {"x": 1}, field
    for field in common._MERGE_LATEST_WINS_FIELDS:
        merged = _merge_character_results(
            {field: "earlier"}, {"sequence": [], field: "later"})
        assert merged[field] == "later", field
        # ...and latest-wins means the earlier value is GONE when the later
        # round is silent. That is the licence these fields are granted; the
        # guard exists so it is granted on purpose.
        assert field not in _merge_character_results(
            {field: "earlier"}, {"sequence": []}), field
