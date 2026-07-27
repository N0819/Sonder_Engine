"""Focused tests for portable, no-provider pipeline trace replay."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import time

import pytest

from agents.storage import save_step
from pipeline_trace import (
    PipelineTraceError,
    dump_pipeline_trace,
    export_pipeline_trace,
    load_pipeline_trace,
    replay_pipeline_trace,
    validate_pipeline_trace,
    write_pipeline_trace,
)


def _turn_with_variants(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Private title", "Private scenario", time.time()),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "I open the hidden door.", time.time()),
    )
    save_step(
        turn_id,
        "director_interpret",
        "Director · interpret",
        0,
        {"flow": {"needs_mapping": False}, "private": "first attempt"},
    )
    save_step(
        turn_id,
        "director_interpret",
        "Director · interpret",
        0,
        {"flow": {"needs_mapping": True}, "private": "active attempt"},
    )
    save_step(
        turn_id,
        "mapping_stage",
        "Mapping",
        1,
        {"relevant_lore": ["The door belongs to Mara."]},
    )
    return chat_id, turn_id


def test_hash_only_export_is_stable_and_omits_story_content(temp_db):
    _chat_id, turn_id = _turn_with_variants(temp_db)

    first = export_pipeline_trace(turn_id)
    second = export_pipeline_trace(turn_id)

    assert dump_pipeline_trace(first) == dump_pipeline_trace(second)
    assert first["privacy"]["content"] == "sha256-only"
    assert "player_input" not in first["turn"]
    assert "Private title" not in dump_pipeline_trace(first)
    assert "Private scenario" not in dump_pipeline_trace(first)
    assert "hidden door" not in dump_pipeline_trace(first)
    assert "Mara" not in dump_pipeline_trace(first)
    assert all(
        "content" not in variant
        for step in first["steps"]
        for variant in step["variants"]
    )
    assert validate_pipeline_trace(first).valid


def test_full_trace_replays_active_steps_without_runtime_or_provider_calls(temp_db):
    _chat_id, turn_id = _turn_with_variants(temp_db)
    trace = export_pipeline_trace(turn_id, include_content=True)

    events = list(replay_pipeline_trace(trace))

    assert [event["type"] for event in events] == [
        "trace_start",
        "step_start",
        "step",
        "step_start",
        "step",
        "done",
    ]
    step_events = [event for event in events if event["type"] == "step"]
    assert [event["key"] for event in step_events] == [
        "director_interpret",
        "mapping_stage",
    ]
    assert step_events[0]["content"]["private"] == "active attempt"
    assert step_events[0]["variants"] == 2
    assert all(event.get("replayed") for event in step_events)


def test_hash_only_trace_refuses_replay_with_clear_error(temp_db):
    _chat_id, turn_id = _turn_with_variants(temp_db)
    trace = export_pipeline_trace(turn_id)

    with pytest.raises(PipelineTraceError, match="required for replay"):
        list(replay_pipeline_trace(trace))


def test_all_variants_preserves_reroll_history_but_replays_active(temp_db):
    _chat_id, turn_id = _turn_with_variants(temp_db)
    trace = export_pipeline_trace(
        turn_id,
        include_content=True,
        include_all_variants=True,
    )

    director = trace["steps"][0]
    assert len(director["variants"]) == 2
    assert [variant["active"] for variant in director["variants"]] == [
        False,
        True,
    ]
    replayed = [
        event for event in replay_pipeline_trace(trace)
        if event["type"] == "step"
    ]
    assert replayed[0]["content"]["private"] == "active attempt"


def test_integrity_validation_detects_payload_tampering(temp_db):
    _chat_id, turn_id = _turn_with_variants(temp_db)
    trace = export_pipeline_trace(turn_id, include_content=True)
    tampered = copy.deepcopy(trace)
    tampered["steps"][0]["variants"][0]["content"]["private"] = "changed"

    validation = validate_pipeline_trace(tampered, require_content=True)

    assert not validation.valid
    assert any("trace_sha256" in error for error in validation.errors)
    assert any("content_sha256" in error for error in validation.errors)


def test_stale_step_is_replayable_but_visible_as_warning(temp_db):
    _chat_id, turn_id = _turn_with_variants(temp_db)
    temp_db.qi(
        "UPDATE steps SET stale=1 WHERE turn_id=? AND key='mapping_stage'",
        (turn_id,),
    )
    trace = export_pipeline_trace(turn_id, include_content=True)

    validation = validate_pipeline_trace(trace, require_content=True)

    assert validation.valid
    assert validation.warnings == ("step 'mapping_stage' is marked stale",)
    start = next(replay_pipeline_trace(trace))
    assert start["warnings"] == ["step 'mapping_stage' is marked stale"]


def test_atomic_file_round_trip(temp_db, tmp_path):
    _chat_id, turn_id = _turn_with_variants(temp_db)
    trace = export_pipeline_trace(turn_id, include_content=True)
    destination = tmp_path / "turn.trace.json"

    write_pipeline_trace(destination, trace)

    assert load_pipeline_trace(destination) == trace
    assert json.loads(destination.read_text(encoding="utf-8")) == trace
    assert not list(tmp_path.glob("*.tmp"))


def test_cli_exports_inspects_and_replays_without_engine_startup(
    temp_db,
    tmp_path,
):
    _chat_id, turn_id = _turn_with_variants(temp_db)
    root = Path(__file__).resolve().parents[1]
    tool = root / "tools" / "pipeline_trace.py"
    destination = tmp_path / "cli.trace.json"

    exported = subprocess.run(
        [
            sys.executable,
            str(tool),
            "export",
            str(turn_id),
            "--db",
            temp_db.DB,
            "--include-content",
            "--output",
            str(destination),
        ],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert exported.returncode == 0, exported.stderr

    inspected = subprocess.run(
        [sys.executable, str(tool), "inspect", str(destination)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert inspected.returncode == 0, inspected.stderr
    assert json.loads(inspected.stdout)["replayable"] is True

    replayed = subprocess.run(
        [sys.executable, str(tool), "replay", str(destination)],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert replayed.returncode == 0, replayed.stderr
    events = [
        json.loads(line) for line in replayed.stdout.splitlines() if line
    ]
    assert events[0]["type"] == "trace_start"
    assert events[-1] == {
        "replayed": True,
        "turn_id": turn_id,
        "type": "done",
        "valid": True,
    }
