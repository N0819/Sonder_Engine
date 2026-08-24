"""Paid ceiling substrate: author opt-in and deterministic private selection."""

from __future__ import annotations

import json
import time


def _char(db, cid, name, uid, *, opted, state=None, status="dormant"):
    sheet = json.dumps({
        "identity": {"name": name, "uid": uid},
        "simulation": {"tier": "major", "offscreen_agent": opted},
    })
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, sheet, "{}", time.time()))
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (cid, char_id, status, json.dumps(state or {})))
    return char_id


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Agent story", "", time.time()))


def test_card_opt_in_defaults_false_and_round_trips():
    from story.character_schema import (character_offscreen_agent,
                                  normalize_character_data)

    assert not character_offscreen_agent({"identity": {"name": "Mora"}})
    sheet = normalize_character_data({
        "identity": {"name": "Mora"},
        "simulation": {"offscreen_agent": True},
    })
    assert sheet["simulation"]["offscreen_agent"] is True
    assert character_offscreen_agent(sheet)


def test_only_opted_in_dormant_character_with_new_private_evidence_is_selected(
        temp_db):
    from world.offscreen import full_agent_candidates

    cid = _chat(temp_db)
    private = {"carried_reports": [{
        "world_event_id": "evt", "claim": "the bell rang",
        "acquired_turn": 5,
    }], "offscreen_agent": {"last_turn": 3}}
    opted = _char(temp_db, cid, "Mora", "mora_uid", opted=True, state=private)
    _char(temp_db, cid, "Tavi", "tavi_uid", opted=False, state=private)
    rows = full_agent_candidates(cid, cap=3)
    assert [r["char_id"] for r in rows] == [opted]
    assert rows[0]["reasons"] == ["new_carried_report"]
    assert rows[0]["new_report_count"] == 1


def test_stale_evidence_without_a_plan_spends_nothing(temp_db):
    from world.offscreen import full_agent_candidates

    cid = _chat(temp_db)
    state = {"carried_reports": [{"world_event_id": "evt", "claim": "x",
                                   "acquired_turn": 5}],
             "offscreen_agent": {"last_turn": 5}}
    _char(temp_db, cid, "Mora", "mora_uid", opted=True, state=state)
    assert full_agent_candidates(cid, cap=3) == []


def test_an_active_authored_plan_is_a_selection_reason(temp_db):
    from world.offscreen import full_agent_candidates

    cid = _chat(temp_db)
    _char(temp_db, cid, "Mora", "mora_uid", opted=True)
    temp_db.wset(cid, "offscreen_plans", [{
        "plan_id": "p", "actor_id": "mora_uid", "status": "active",
    }])
    rows = full_agent_candidates(cid, cap=1)
    assert rows[0]["id"] == "mora_uid"
    assert rows[0]["reasons"] == ["active_plan"]


def test_cap_and_database_order_are_deterministic(temp_db):
    from world.offscreen import full_agent_candidates

    cid = _chat(temp_db)
    for i in range(3):
        _char(temp_db, cid, f"C{i}", f"c{i}", opted=True,
              state={"carried_reports": [{"world_event_id": f"e{i}",
                                           "claim": "x",
                                           "acquired_turn": 1}]})
    first = full_agent_candidates(cid, cap=2)
    second = full_agent_candidates(cid, cap=2)
    assert [r["char_id"] for r in first] == [r["char_id"] for r in second]
    assert len(first) == 2


def test_editor_exposes_the_opt_in_without_enabling_it_by_default():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    source = (root / "static/js/ui-next/library-editors/character-persona.js").read_text(encoding="utf-8")
    sections = (root / "static/js/ui-next/library-editors/person-sections.js").read_text(encoding="utf-8")
    assert "createPersonSectionEditor" in source
    assert 'path: "simulation.offscreen_agent"' in sections
    assert "createAdditionalNode" in sections
    assert "JSON.stringify(state.draft, null, 2)" in source
