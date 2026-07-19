"""Tests for pipeline safety and completion invariants."""

import json
import time

import pytest

from agents import _join_text, _assert_plan_materialized, save_step
from pipeline_context import ChatData, PipelineContext, TurnData

class TestJoinText:
    def test_discards_booleans(self):
        assert _join_text([
            "player input",
            True,
            False,
            None,
            "recent event",
        ]) == "player input recent event"

    def test_handles_mixed_values(self):
        result = _join_text([
            "hello",
            12,
            {"room": "kitchen"},
            ["Alice", "Bob"],
        ])

        assert "hello" in result
        assert "12" in result
        assert "kitchen" in result
        assert "Alice" in result

    def test_empty_values(self):
        assert _join_text([None, False, True, "", "  "]) == ""

    def test_serializes_dict_safely(self):
        result = _join_text([{"nested": {"deep": True}}])
        assert isinstance(result, str)
        assert "nested" in result

def make_context(chat_id, turn_id):
    return PipelineContext(
        chat=ChatData(
            id=chat_id,
            name="Test",
            persona_id=None,
            lorebook_id=None,
            scenario="",
            created=time.time(),
        ),
        turn=TurnData(
            id=turn_id,
            chat_id=chat_id,
            idx=1,
            player_input="test",
            created=time.time(),
        ),
        cast=[],
        input="test",
    )

def test_completion_invariant_detects_missing_step(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    turn_id = temp_db.qi(
        """
        INSERT INTO turns(chat_id,idx,player_input,created)
        VALUES(?,?,?,?)
        """,
        (chat_id, 1, "test", time.time()),
    )

    ctx = make_context(chat_id, turn_id)
    plan = [
        ("mapping_quick", "Mapping"),
        ("narrator", "Narrator"),
    ]

    mapping_result = {"relevant_lore": []}
    ctx["mapping_quick"] = mapping_result
    save_step(
        turn_id,
        "mapping_quick",
        "Mapping",
        0,
        mapping_result,
    )

    with pytest.raises(
        RuntimeError,
        match="narrator",
    ):
        _assert_plan_materialized(turn_id, plan, ctx)

def test_completion_invariant_detects_missing_variant(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    turn_id = temp_db.qi(
        """
        INSERT INTO turns(chat_id,idx,player_input,created)
        VALUES(?,?,?,?)
        """,
        (chat_id, 1, "test", time.time()),
    )

    ctx = make_context(chat_id, turn_id)
    plan = [
        ("mapping_quick", "Mapping"),
        ("narrator", "Narrator"),
    ]

    ctx["mapping_quick"] = {"relevant_lore": []}
    ctx["narrator"] = {"prose": "test"}

    save_step(
        turn_id, "mapping_quick", "Mapping", 0,
        {"relevant_lore": []},
    )
    save_step(
        turn_id, "narrator", "Narrator", 1,
        {"prose": "test"},
    )

    temp_db.qi(
        """
        UPDATE variants SET active=0
        WHERE step_id IN (
            SELECT id FROM steps
            WHERE turn_id=? AND key='narrator'
        )
        """,
        (turn_id,),
    )

    with pytest.raises(RuntimeError, match="narrator"):
        _assert_plan_materialized(turn_id, plan, ctx)

def test_completion_invariant_accepts_complete_plan(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    turn_id = temp_db.qi(
        """
        INSERT INTO turns(chat_id,idx,player_input,created)
        VALUES(?,?,?,?)
        """,
        (chat_id, 1, "test", time.time()),
    )

    ctx = make_context(chat_id, turn_id)
    plan = [
        ("mapping_quick", "Mapping"),
        ("narrator", "Narrator"),
    ]

    for index, (key, label) in enumerate(plan):
        result = {"step": key}
        ctx[key] = result
        save_step(
            turn_id,
            key,
            label,
            index,
            result,
        )

    _assert_plan_materialized(turn_id, plan, ctx)

class TestRecentEventsSafety:
    def test_returns_only_strings(self, temp_db):
        from scene import recent_events

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        turn_id = temp_db.qi(
            """
            INSERT INTO turns(chat_id,idx,player_input,created)
            VALUES(?,?,?,?)
            """,
            (chat_id, 1, "test", time.time()),
        )

        temp_db.qi(
            """
            INSERT INTO events(chat_id,turn_id,content)
            VALUES(?,?,?)
            """,
            (
                chat_id,
                turn_id,
                json.dumps({
                    "summary": "Alice arrived.",
                    "event": "Alice arrived at the manor.",
                }),
            ),
        )

        events = recent_events(chat_id, n=5)

        assert events == ["Alice arrived."]
        assert all(isinstance(event, str) for event in events)

    def test_skips_non_dict_payload(self, temp_db):
        from scene import recent_events

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        turn_id = temp_db.qi(
            """
            INSERT INTO turns(chat_id,idx,player_input,created)
            VALUES(?,?,?,?)
            """,
            (chat_id, 1, "test", time.time()),
        )

        temp_db.qi(
            """
            INSERT INTO events(chat_id,turn_id,content)
            VALUES(?,?,?)
            """,
            (chat_id, turn_id, '"just a string"'),
        )

        assert recent_events(chat_id, n=5) == []

    def test_skips_invalid_json(self, temp_db):
        from scene import recent_events

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        turn_id = temp_db.qi(
            """
            INSERT INTO turns(chat_id,idx,player_input,created)
            VALUES(?,?,?,?)
            """,
            (chat_id, 1, "test", time.time()),
        )

        temp_db.qi(
            """
            INSERT INTO events(chat_id,turn_id,content)
            VALUES(?,?,?)
            """,
            (chat_id, turn_id, "{not valid JSON"),
        )

        assert recent_events(chat_id, n=5) == []

    def test_skips_non_string_summary(self, temp_db):
        from scene import recent_events

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        turn_id = temp_db.qi(
            """
            INSERT INTO turns(chat_id,idx,player_input,created)
            VALUES(?,?,?,?)
            """,
            (chat_id, 1, "test", time.time()),
        )

        temp_db.qi(
            """
            INSERT INTO events(chat_id,turn_id,content)
            VALUES(?,?,?)
            """,
            (
                chat_id,
                turn_id,
                json.dumps({
                    "summary": True,
                    "event": "something",
                }),
            ),
        )

        assert recent_events(chat_id, n=5) == []

    def test_handles_empty_summary(self, temp_db):
        from scene import recent_events

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        turn_id = temp_db.qi(
            """
            INSERT INTO turns(chat_id,idx,player_input,created)
            VALUES(?,?,?,?)
            """,
            (chat_id, 1, "test", time.time()),
        )

        temp_db.qi(
            """
            INSERT INTO events(chat_id,turn_id,content)
            VALUES(?,?,?)
            """,
            (
                chat_id,
                turn_id,
                json.dumps({
                    "summary": "  ",
                    "event": "x",
                }),
            ),
        )

        assert recent_events(chat_id, n=5) == []

class TestCommitFailure:
    def _stub_preparation(self, commit_module, monkeypatch):
        monkeypatch.setattr(
            commit_module,
            "_prepare_turn_commit",
            lambda ctx: {
                "scene": {"scene": {}, "clock": None},
                "mapping": {},
                "memories": {},
            },
        )

    def test_commit_all_raises_on_failure(self, temp_db, monkeypatch):
        import commit as commit_module

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 1, "test", time.time()),
        )
        ctx = make_context(chat_id, turn_id)
        self._stub_preparation(commit_module, monkeypatch)

        def failing_scene(ctx, nonce, *, prepared=None):
            raise RuntimeError("simulated scene failure")

        monkeypatch.setattr(commit_module, "commit_scene", failing_scene)

        with pytest.raises(
            RuntimeError,
            match="Commit failed and was rolled back.*scene",
        ):
            commit_module.commit_all(ctx, nonce=0)

    def test_late_failure_rolls_back_earlier_domain_writes(
        self, temp_db, monkeypatch,
    ):
        import commit as commit_module

        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Test", "", time.time()),
        )
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (chat_id, 1, "test", time.time()),
        )
        ctx = make_context(chat_id, turn_id)
        self._stub_preparation(commit_module, monkeypatch)

        def write_scene_probe(ctx, nonce, *, prepared=None):
            commit_module.wset(ctx.chat.id, "atomic_probe", {"written": True})
            return {"probe": True}

        def fail_entities(ctx, nonce):
            raise RuntimeError("simulated later failure")

        monkeypatch.setattr(commit_module, "commit_scene", write_scene_probe)
        monkeypatch.setattr(commit_module, "commit_world_entities", fail_entities)

        with pytest.raises(RuntimeError, match="rolled back.*entities"):
            commit_module.commit_all(ctx, nonce=0)

        assert temp_db.wget(chat_id, "atomic_probe") is None
