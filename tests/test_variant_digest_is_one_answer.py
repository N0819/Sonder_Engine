"""One variant, one digest, across every export that publishes one.

Review finding B22 ("two representations free to disagree"): the pipeline
trace hashed a variant's decoded content whole, while the turn-debug artifact
hashed the same variant after popping `_engine_notes`. Both call the result
the SHA-256 of that step's output, so the join a reader makes between the two
artifacts -- `steps[].variants[].content_sha256` against the timeline's
`output_sha256` -- disagreed on every step the deterministic layer had
annotated, which is every step that repaired output or ran in a parallel
group.
"""

from __future__ import annotations

import time

from agents.storage import ENGINE_NOTES_KEY, save_step
from persist.pipeline_trace import (
    export_pipeline_trace,
    export_turn_debug,
    validate_pipeline_trace,
)


ANNOTATED = {
    "prose": "The door gives on the third shove.",
    ENGINE_NOTES_KEY: {
        "warnings": ["repetition retained"],
        "decisions": ["declined to move an unheld body"],
        "llm_calls": [{"step_key": "narrator", "duration": 4.0}],
    },
}
PLAIN = {"flow": {"needs_mapping": True}}


def _turn(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Digest", "Scenario", time.time()),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "I shove the door.", time.time()),
    )
    save_step(turn_id, "director_interpret", "Director", 0, PLAIN)
    save_step(turn_id, "narrator", "Narrator", 1, ANNOTATED)
    return turn_id


def _trace_digests(trace):
    return {
        step["key"]: step["variants"][0]["content_sha256"]
        for step in trace["steps"]
    }


def _debug_digests(debug):
    return {
        event["step"]: event["output_sha256"]
        for event in debug["timeline"] if event["kind"] == "step"
    }


def test_both_exports_publish_the_same_digest_for_one_variant(temp_db):
    turn_id = _turn(temp_db)
    trace = _trace_digests(export_pipeline_trace(turn_id))
    debug = _debug_digests(export_turn_debug(turn_id))

    assert set(trace) == set(debug) == {"director_interpret", "narrator"}
    # The unannotated step always agreed; the annotated one is the finding.
    assert debug["narrator"] == trace["narrator"]
    assert debug["director_interpret"] == trace["director_interpret"]


def test_the_digest_does_not_depend_on_what_an_export_shows(temp_db):
    turn_id = _turn(temp_db)
    with_content = _debug_digests(export_turn_debug(turn_id))
    without = _debug_digests(export_turn_debug(turn_id, include_content=False))
    hash_only = _trace_digests(export_pipeline_trace(turn_id))
    full = _trace_digests(
        export_pipeline_trace(turn_id, include_content=True)
    )
    assert with_content == without == hash_only == full


def test_debug_output_still_hides_the_notes_and_hoists_them(temp_db):
    turn_id = _turn(temp_db)
    steps = {
        event["step"]: event
        for event in export_turn_debug(turn_id)["timeline"]
        if event["kind"] == "step"
    }
    narrator = steps["narrator"]
    assert ENGINE_NOTES_KEY not in narrator["output"]
    assert narrator["output"] == {"prose": ANNOTATED["prose"]}
    assert narrator["warnings"] == ["repetition retained"]
    assert narrator["decisions"] == ["declined to move an unheld body"]
    assert narrator["llm_calls"] == ANNOTATED[ENGINE_NOTES_KEY]["llm_calls"]


def test_a_full_trace_still_verifies_against_its_own_digest(temp_db):
    turn_id = _turn(temp_db)
    trace = export_pipeline_trace(turn_id, include_content=True)
    assert validate_pipeline_trace(trace, require_content=True).valid
