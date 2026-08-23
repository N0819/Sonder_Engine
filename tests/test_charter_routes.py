"""The structured Charter authoring surface is reachable and era-scoped."""

from __future__ import annotations

import copy
import time

import pytest
from fastapi import HTTPException

from web import app as app_module


@pytest.fixture
def chat_id(temp_db):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Charter routes", "", time.time()),
    )
    temp_db.wset(cid, "scene", {
        "rooms": {"engine_room": {"name": "Engine Room", "adjacent": []}},
        "positions": {}, "entities": {}, "attire": {}, "overlays": {},
    })
    return cid


def test_round_trip_normalizes_and_reports_authoring_warnings(
        temp_db, chat_id):
    body = app_module.charters_put(chat_id, {
        "ship": {
            "key": "ship",
            "upkeeps": {"air": {"place": "engine_room"}},
            "posts": {},
            "bodies": {},
        },
    })

    assert set(body["charters"]["items"]) == {"ship"}
    assert any("no posts" in warning for warning in body["warnings"])
    assert any("served by no post" in warning for warning in body["warnings"])
    assert app_module.charters_get(chat_id)["charters"] == body["charters"]

    routes = {(route.path, method)
              for route in app_module.app.routes
              for method in (getattr(route, "methods", None) or ())}
    assert ("/api/chats/{cid}/charters", "GET") in routes
    assert ("/api/chats/{cid}/charters", "PUT") in routes
    assert ("/api/chats/{cid}/charters/diagnostics", "GET") in routes
    assert ("/api/chats/{cid}/charters/generate", "POST") in routes


def test_diagnostics_explain_state_without_changing_it(temp_db, chat_id):
    app_module.charters_put(chat_id, {
        "watch": {"key": "watch", "bodies": {"iri": {
            "place": "engine_room"}}, "judgments": {"iri": {"Visitor": {
                "trust": -0.2, "suspicion": 0.3,
                "reasons": [{"evidence_id": "scene:1:speech",
                             "signal": "threat"}]}}}}})

    before = app_module.charters_get(chat_id)["charters"]
    view = app_module.charters_diagnostics(
        chat_id, charter="watch", body="iri")
    after = app_module.charters_get(chat_id)["charters"]

    assert before == after
    assert view["items"]["watch"]["judgments_by"]["Visitor"]["suspicion"] > 0


def test_generation_route_closes_and_presims_one_model_plan(
        temp_db, chat_id, monkeypatch):
    plan = {
        "name": "Engine Ward",
        "structure": {"key": "ward", "max_planned": 8},
        "rooms": {"engine_room": {"name": "Engine Room",
                                   "purpose": "maintenance", "adjacent": []}},
            "charters": [{
                "key": "crew", "priority": ["air"],
                "naming": {"given": ["Mara", "Iven", "Sorn"],
                           "family": ["Vale", "North", "Ash"]},
                "upkeeps": {"air": {"place": "engine_room", "floor": .2,
                                  "fails_untended": "a_week",
                                  "one_body_restores_in": "a_shift"}},
            "posts": {"tech": {"place": "engine_room", "serves": ["air"],
                                "requires": {"technical": 1}}},
            "populations": [{"post": "tech", "count": 1,
                             "competence": {"technical": 1},
                             "berth": "engine_room"}],
        }],
    }
    monkeypatch.setattr("world.charter_generate.propose_town",
                        lambda lore, brief="": plan)
    monkeypatch.setattr("world.charter_generate.propose_history",
                        lambda plan, lore, horizon: {"eras": [],
                                                     "interventions": []})
    monkeypatch.setattr("world.charter_generate.narrate_actual_history",
                        lambda town, registry, events: {
                            "overview": {}, "eras": [], "residents": {},
                            "institutions": [], "grounding": {}})

    out = app_module.charters_generate(
        chat_id, {"brief": "industrial", "horizon_hours": 12,
                  "active_tail_hours": 4})

    assert out["ok"] is True
    assert out["town"] == "Engine Ward"
    assert out["charters"] == ["crew"]
    assert app_module.charters_get(chat_id)["charters"]["items"]["crew"] \
        ["state"]["clock_hours"] == 12


def test_generation_reads_only_selected_lorebook_subtree(
        temp_db, chat_id, monkeypatch):
    root = temp_db.qi(
        "INSERT INTO lorebooks(name,book_type,summary) VALUES(?,?,?)",
        ("Port Lore", "location", ""))
    child = temp_db.qi(
        "INSERT INTO lorebooks(name,book_type,summary,parent_id) "
        "VALUES(?,?,?,?)", ("Dock Lore", "location", "", root))
    unrelated = temp_db.qi(
        "INSERT INTO lorebooks(name,book_type,summary) VALUES(?,?,?)",
        ("Unrelated Moon", "location", ""))
    owning = temp_db.qi(
        "INSERT INTO lorebooks(name,book_type,summary,chat_id,origin_id) "
        "VALUES(?,?,?,?,?)", ("Port Lore", "location", "", chat_id, root))
    for lid, title in ((root, "Port law"), (child, "Dock custom"),
                       (unrelated, "Moon secret")):
        temp_db.qi(
            "INSERT INTO lore_entries(lorebook_id,title,keys,content,category) "
            "VALUES(?,?,?,?,?)", (lid, title, title, title, "locations"))
    seen = {}
    def capture_plan(lore, brief=""):
        seen["lore"] = lore
        return {"name": "Port", "structure": {"key": "port"},
                "rooms": {"quay": {"name": "Quay", "adjacent": []}},
                "charters": []}
    monkeypatch.setattr(
        "world.charter_generate.propose_town",
        capture_plan)

    app_module.charters_generate(chat_id, {
        "lorebook_id": root, "owning_lorebook_id": owning,
        "horizon_hours": 0,
        "generate_history": False})

    assert {row["title"] for row in seen["lore"]} == {
        "Port law", "Dock custom"}
    assert all(row["book"] in {"Port Lore", "Dock Lore"}
               for row in seen["lore"])
    room = temp_db.q(
        "SELECT owning_book_id FROM room_registry "
        "WHERE chat_id=? AND room_uid='quay'", (chat_id,), one=True)
    assert room["owning_book_id"] == owning


def test_second_generated_location_is_additive_and_collision_safe(
        temp_db, chat_id, monkeypatch):
    plan = {
        "name": "Engine Ward",
        "structure": {"key": "ward", "max_planned": 8},
        "rooms": {"engine_room": {"name": "Engine Room",
                                    "purpose": "maintenance", "adjacent": []}},
            "charters": [{
                "key": "crew", "priority": ["air"],
                "naming": {"given": ["Mara", "Iven", "Sorn"],
                           "family": ["Vale", "North", "Ash"]},
                "upkeeps": {"air": {"place": "engine_room", "floor": .2,
                                   "fails_untended": "a_week",
                                   "one_body_restores_in": "a_shift"}},
            "posts": {"tech": {"place": "engine_room", "serves": ["air"]}},
            "populations": [{"post": "tech", "count": 1,
                              "berth": "engine_room"}],
        }],
    }
    monkeypatch.setattr(
        "world.charter_generate.propose_town",
        lambda lore, brief="": copy.deepcopy(plan))

    app_module.charters_generate(chat_id, {
        "horizon_hours": 12, "generate_history": False})
    app_module.charters_generate(chat_id, {
        "horizon_hours": 5, "generate_history": False})

    items = app_module.charters_get(chat_id)["charters"]["items"]
    assert set(items) == {"crew", "crew_2"}
    assert items["crew"]["state"]["clock_hours"] == 12
    assert items["crew_2"]["state"]["clock_hours"] == 5
    rooms = temp_db.q(
        "SELECT room_uid FROM room_registry WHERE chat_id=? ORDER BY room_uid",
        (chat_id,))
    assert len({row["room_uid"] for row in rooms}) == 2
    assert "engine_room" in {row["room_uid"] for row in rooms}


def test_missing_chat_is_not_created_by_the_authoring_route(temp_db):
    with pytest.raises(HTTPException) as get_error:
        app_module.charters_get(999999)
    with pytest.raises(HTTPException) as put_error:
        app_module.charters_put(999999, {})
    assert get_error.value.status_code == 404
    assert put_error.value.status_code == 404


def test_reasoning_budget_failure_is_a_readable_gateway_error(
        temp_db, chat_id, monkeypatch):
    from llm.providers import ReasoningBudgetExhausted

    def fail(*args, **kwargs):
        raise ReasoningBudgetExhausted("trace consumed answer")

    monkeypatch.setattr(
        "world.charter_runtime.generate_lived_location", fail)
    with pytest.raises(HTTPException) as caught:
        app_module.charters_generate(chat_id, {"brief": "a port"})

    assert caught.value.status_code == 502
    assert "whole response for reasoning" in caught.value.detail
    assert "No presimulation was applied" in caught.value.detail


def test_unauthored_chat_returns_the_empty_shape_the_menu_reads(
        temp_db, chat_id):
    """A story with no institution must answer, not raise.

    The dialogue-config menu fetches this on EVERY open (`static/js/
    settings.js`, the Institutions block), so the overwhelmingly common case
    is a chat where nobody ever authored a charter. That path had no test:
    the round-trip above always writes one first.
    """
    payload = app_module.charters_get(chat_id)

    assert payload["charters"]["items"] == {}
    assert payload["warnings"] == []


def test_authored_charter_exposes_the_fields_the_menu_renders(
        temp_db, chat_id):
    """`items[key].state` and `window_hours` are read by name in the menu.

    Renaming either is a silent blank row rather than an error, because the
    reader is JavaScript walking a JSON dict.
    """
    body = app_module.charters_put(chat_id, {
        "ship": {
            "key": "ship",
            "upkeeps": {"air": {"place": "engine_room"}},
            "posts": {"scrubber": {"serves": ["air"], "place": "engine_room"}},
            "bodies": {"iri": {"place": "engine_room"}},
        },
    })

    item = body["charters"]["items"]["ship"]
    assert item["window_hours"] > 0
    state = item["state"]
    assert state["key"] == "ship"
    for field in ("bodies", "posts", "upkeeps"):
        assert isinstance(state[field], dict) and state[field]
    assert isinstance(state["clock_hours"], float)
