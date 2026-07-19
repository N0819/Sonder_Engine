"""Regression tests for additional-player (multiplayer) support: the
chat_personas/turn_player_inputs tables, extra-player loading, and
build_plan's conditional narrator_extra step."""

from __future__ import annotations

import json
import time

from agents.runtime import _chat_has_extra_players, _load_extra_players, build_plan
from character_schema import default_persona_data


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def _make_persona(db, name="Extra Player"):
    sheet = default_persona_data(name)
    return db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) "
        "VALUES(?,?,?,?)",
        (name, json.dumps(sheet), json.dumps({"format": "native"}),
         f"persona_{name}"),
    )


class TestExtraPlayerLoading:
    def test_no_attached_personas_returns_empty(self, temp_db):
        chat_id = _make_chat(temp_db)
        assert _load_extra_players(chat_id, 0) == []
        assert _chat_has_extra_players(chat_id) is False

    def test_attached_persona_without_submission_is_included_but_idle(self, temp_db):
        chat_id = _make_chat(temp_db)
        persona_id = _make_persona(temp_db)
        temp_db.qi(
            "INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,'active')",
            (chat_id, persona_id),
        )
        assert _chat_has_extra_players(chat_id) is True
        # Attached, no turn_player_inputs row for this idx -- still
        # included (an idle connected player still needs their own
        # perceiver/narrated view of the passing beat), just flagged idle
        # with empty input for the director to skip.
        extras = _load_extra_players(chat_id, 0)
        assert len(extras) == 1
        assert extras[0]["persona_id"] == persona_id
        assert extras[0]["idle"] is True
        assert extras[0]["input"] == ""

    def test_attached_persona_with_submission_is_not_idle(self, temp_db):
        chat_id = _make_chat(temp_db)
        persona_id = _make_persona(temp_db, "Riker")
        temp_db.qi(
            "INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,'active')",
            (chat_id, persona_id),
        )
        temp_db.qi(
            "INSERT INTO turn_player_inputs(chat_id,turn_idx,persona_id,input,created) "
            "VALUES(?,?,?,?,?)",
            (chat_id, 3, persona_id, "I raise an eyebrow.", time.time()),
        )
        extras = _load_extra_players(chat_id, 3)
        assert len(extras) == 1
        assert extras[0]["persona_id"] == persona_id
        assert extras[0]["name"] == "Riker"
        assert extras[0]["input"] == "I raise an eyebrow."
        assert extras[0]["idle"] is False

        # A different turn index: still included (attached), but idle --
        # inputs are per-beat, not carried forward automatically.
        other_beat = _load_extra_players(chat_id, 4)
        assert len(other_beat) == 1
        assert other_beat[0]["idle"] is True
        assert other_beat[0]["input"] == ""

    def test_dormant_persona_is_excluded(self, temp_db):
        chat_id = _make_chat(temp_db)
        persona_id = _make_persona(temp_db)
        temp_db.qi(
            "INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,'dormant')",
            (chat_id, persona_id),
        )
        temp_db.qi(
            "INSERT INTO turn_player_inputs(chat_id,turn_idx,persona_id,input,created) "
            "VALUES(?,?,?,?,?)",
            (chat_id, 0, persona_id, "declared", time.time()),
        )
        assert _chat_has_extra_players(chat_id) is False
        assert _load_extra_players(chat_id, 0) == []


class TestBuildPlanMultiplayer:
    def test_single_player_chat_has_no_narrator_extra_step(self, temp_db):
        chat_id = _make_chat(temp_db)
        plan = build_plan({}, [], chat_id=chat_id)
        keys = [k for k, _ in plan]
        assert "narrator_extra" not in keys
        assert "commit" in keys

    def test_multiplayer_chat_gets_narrator_extra_before_commit(self, temp_db):
        chat_id = _make_chat(temp_db)
        persona_id = _make_persona(temp_db)
        temp_db.qi(
            "INSERT INTO chat_personas(chat_id,persona_id,status) VALUES(?,?,'active')",
            (chat_id, persona_id),
        )
        plan = build_plan({}, [], chat_id=chat_id)
        keys = [k for k, _ in plan]
        assert "narrator_extra" in keys
        assert keys.index("narrator_extra") == keys.index("commit") - 1
        assert keys.index("narrator") < keys.index("narrator_extra")
