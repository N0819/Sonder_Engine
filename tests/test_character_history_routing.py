"""Compact topology and grounding tests for pre-story character history."""

from story.history_routing import (
    resolve_character_history_route, route_uses_charter)
from story.journey_history import compile_journey_history, ground_journey_history
from world.charter_history import featured_resident_private_habits
from world.charter_model import normalize_charter
from world.charter_run import step


def test_itinerant_alien_is_an_encounter_not_a_charter_resident():
    sheet = {
        "identity": {"name": "The Wanderer"},
        "knowledge": {"public_history":
            "A mysterious alien traveler who wanders between worlds, arriving "
            "at crises in a strange vessel with changing companions."},
    }
    route = resolve_character_history_route(
        sheet, opening="The vessel arrives above a desert city.",
        location_brief="a lived-in desert city")

    assert route["anchor"] == "itinerary"
    assert route["opening_relationship"] == "visiting"
    assert route["backends"] == ["authored_history"]
    assert not route_uses_charter(route)


def test_explicit_resident_and_moving_institution_are_the_only_charter_routes():
    sheet = {"identity": {"name": "Mara"}, "knowledge": {
        "public_history": "Mara serves as chief medic aboard the Wayfarer."}}
    auto = resolve_character_history_route(
        sheet, opening="The Wayfarer infirmary is quiet.",
        location_brief="the Wayfarer")
    visitor = resolve_character_history_route(sheet, requested="visitor")

    assert auto["anchor"] == "bounded_moving_institution"
    assert route_uses_charter(auto)
    assert not route_uses_charter(visitor)


def test_uncertain_competence_does_not_become_tenure():
    sheet = {"identity": {"name": "Ilyan"}, "knowledge": {
        "public_history": "A gifted surgeon and linguist."}}
    route = resolve_character_history_route(
        sheet, opening="A hospital gate opens.", location_brief="a hospital")
    assert route["authority"] == "authored"
    assert not route_uses_charter(route)


def test_generated_journey_is_ordered_identified_and_bounded():
    grounded = ground_journey_history({
        "summary": "A road of bargains and losses.",
        "events": [
            {"sequence": 3, "when": "last winter", "place": "Orison",
             "people": ["Mara Venn"], "memory": "I left Mara at the north gate.",
             "consequence": "I still owe her a map."},
            {"sequence": 1, "when": "two years ago", "place": "Glass Sea",
             "people": ["Captain Sorn"], "memory": "I crossed with Captain Sorn.",
             "consequence": "I learned the storm route."},
            {"sequence": 2, "when": "the following spring", "place": "Nacre",
             "people": ["Iven"], "memory": "I promised Iven safe passage.",
             "consequence": "The promise remains open."},
        ]}, [], generated=True)

    assert [row["place"] for row in grounded["events"]] == [
        "Glass Sea", "Nacre", "Orison"]
    assert grounded["events"][0]["people"] == ["Captain Sorn"]
    assert all(row["event_id"].startswith("journey:")
               for row in grounded["events"])


def test_cited_journey_drops_an_uncited_canon_invention():
    sources = [{"source_id": "lore:7", "text": "Visited the Moon Court."}]
    grounded = ground_journey_history({"events": [
        {"sequence": 1, "place": "Moon Court", "memory": "I visited.",
         "source_ids": ["lore:7"]},
        {"sequence": 2, "place": "Mars", "memory": "I ruled Mars.",
         "source_ids": ["invented"]},
    ]}, sources, generated=False)
    assert [row["place"] for row in grounded["events"]] == ["Moon Court"]
    assert grounded["grounding"]["dropped"][0]["reason"] == "uncited"


def test_private_habits_run_only_into_the_owners_bounded_experience():
    sheet = {"identity": {"name": "Sana"}, "psychology": {
        "coping": {"strategies": [{
            "name": "Private baking", "trigger": "off duty and alone",
            "response": "Locks the office and bakes small cakes."}]}}}
    habits = featured_resident_private_habits(sheet)
    charter = normalize_charter({
        "key": "clinic", "posts": {}, "upkeeps": {}, "priority": [],
        "bodies": {
            "sana": {"name": "Sana", "place": "office", "berth": "office",
                     "private_habits": habits},
            "other": {"name": "Other", "place": "hall", "berth": "hall"}},
    })
    after, events = step(charter, hours=48)

    assert events == []
    assert after["experiences"]["sana"][0]["kind"] == "private_habit"
    assert "other" not in after["experiences"]
    assert after["habit_runs"]["sana"]


def test_generated_journey_persists_ledger_then_ordered_memory_rows(
        temp_db, monkeypatch):
    import json
    import time

    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Journey", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", json.dumps({"identity": {"name": "Mara"}}), "{}",
         time.time()))
    written = []
    monkeypatch.setattr(
        "mind.memory.add_memories_batch",
        lambda rows: written.extend(rows) or list(range(len(rows))))

    result = compile_journey_history(
        cid, char_id, {"identity": {"name": "Mara"}},
        {"authority": "generated", "guidance": "A debt should survive."},
        model_call=lambda payload: {
            "summary": "Mara crossed three worlds and carried one debt onward.",
            "events": [
                {"sequence": 2, "when": "later", "place": "Nacre",
                 "people": ["Iven"], "memory": "I promised Iven passage."},
                {"sequence": 1, "when": "first", "place": "Glass Sea",
                 "people": ["Sorn"], "memory": "I crossed with Sorn."},
                {"sequence": 3, "when": "recently", "place": "Orison",
                 "people": ["Mara Venn"], "memory": "I left at dawn."},
            ]})

    assert [event["place"] for event in result["events"]] == [
        "Glass Sea", "Nacre", "Orison"]
    assert len(written) == 4  # one era summary plus three episodes
    assert written[1]["content"].startswith("first: Early in my travels")
    assert written[-1]["content"].startswith("Most recently, I left")
    stored = temp_db.wget(cid, "character_journey_histories", {})
    assert stored[str(char_id)]["memory_event_keys"] == result["memory_event_keys"]
