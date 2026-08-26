"""Quick start routes attached full characters without a scale simulation."""

from __future__ import annotations

import json
import time

import pytest

from story.character_schema import default_character_data
from world import charter_runtime


def _attached_character(db, cid, name="Mara Vale"):
    sheet = default_character_data(name)
    sheet["knowledge"]["public_history"] = (
        f"{name} has worked as a surveyor at Site 17 for three years.")
    char_id = db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time()))
    db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
        (cid, char_id))
    return char_id, sheet


def test_quick_start_history_accepts_only_attached_characters(temp_db):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Site 17", "The story opens inside Site 17.", time.time()))
    char_id, _sheet = _attached_character(temp_db, cid)

    request, prepared = charter_runtime._prepare_cast_histories(cid, {
        "brief": "Site 17, an underground facility",
        "character_histories": [
            {"char_id": char_id, "mode": "resident",
             "brief": "Emphasize medical colleagues."},
            {"char_id": 999999, "mode": "resident"},
        ],
    })

    assert [row["char_id"] for row in prepared] == [char_id]
    assert [row["seed_id"] for row in request["featured_residents"]] == [
        f"character:{char_id}"]
    assert "character_histories" not in request
    route = temp_db.wget(cid, "character_history_routes", {})[str(char_id)]
    assert route["mode"] == "resident"
    assert route["guidance"] == "Emphasize medical colleagues."


def test_quick_start_history_rejects_an_explicitly_oversized_full_cast(
        temp_db):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Crowded", "A crowded opening.", time.time()))
    character_ids = [
        _attached_character(temp_db, cid, f"Resident {index}")[0]
        for index in range(charter_runtime.CAST_HISTORY_REQUEST_CAP + 1)
    ]

    with pytest.raises(ValueError, match="at most 16 full characters"):
        charter_runtime._prepare_cast_histories(cid, {
            "character_histories": [
                {"char_id": char_id, "mode": "resident"}
                for char_id in character_ids
            ],
        })


def test_quick_start_resident_is_handed_back_to_full_cognition(
        temp_db, monkeypatch):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Site 17", "The story opens inside Site 17.", time.time()))
    char_id, sheet = _attached_character(temp_db, cid)
    request, prepared = charter_runtime._prepare_cast_histories(cid, {
        "brief": "Site 17", "character_histories": [
            {"char_id": char_id, "mode": "resident"}],
    })
    binding = {
        "charter": "research", "body": "mara", "name": "Mara Vale",
        "place": "medical", "post": "surveyor",
    }
    calls = []
    monkeypatch.setattr(
        "world.charter_history.integrate_featured_resident",
        lambda cid, char_id, binding, sheet, **kwargs: calls.append(
            (cid, char_id, binding, kwargs)) or {
                "memory_event_keys": ["prestory:a", "prestory:b"]})

    charter_runtime._complete_cast_histories(
        cid, request, prepared, {
            "ok": True,
            "featured_residents": {f"character:{char_id}": binding},
        })

    assert calls[0][1] == char_id
    assert calls[0][2] == binding
    route = temp_db.wget(cid, "character_history_routes", {})[str(char_id)]
    assert route["handoff"]["complete"] is True
    assert route["handoff"]["memory_count"] == 2


def test_quick_start_visitor_uses_journey_history_not_charter(
        temp_db, monkeypatch):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Arrival", "A traveler arrives at the port.", time.time()))
    char_id, _sheet = _attached_character(temp_db, cid, "Iria North")
    request, prepared = charter_runtime._prepare_cast_histories(cid, {
        "brief": "the port", "character_histories": [
            {"char_id": char_id, "mode": "generated_journey",
             "brief": "She owes someone passage.", "events": 14}],
    })
    assert "featured_residents" not in request
    monkeypatch.setattr(charter_runtime, "generation_lore",
                        lambda *args, **kwargs: ([], None))
    journeys = []
    monkeypatch.setattr(
        "story.journey_history.compile_journey_history",
        lambda cid, char_id, sheet, route, **kwargs: journeys.append(
            (char_id, route, kwargs)) or {
                "memory_event_keys": ["prestory:journey"],
                "events": [{"event_id": "journey"}]})

    charter_runtime._complete_cast_histories(
        cid, request, prepared, {"ok": True, "featured_residents": {}})

    assert journeys[0][0] == char_id
    assert journeys[0][1]["guidance"] == "She owes someone passage."
    assert journeys[0][1]["event_count"] == 14
    # A journey ends where the story begins: the location the route was
    # decided from reaches the generator instead of being thrown away.
    assert journeys[0][2]["arrival_brief"] == "the port"
    route = temp_db.wget(cid, "character_history_routes", {})[str(char_id)]
    assert route["handoff"]["journey_events"] == 1
