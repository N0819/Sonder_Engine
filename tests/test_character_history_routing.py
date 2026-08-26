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


_ORISON = (
    "I left Mara Venn at the north gate of Orison with the wind coming off "
    "the salt flats, and she would not take the map back from me. She said "
    "keep it, you will need the crossing more than I do, and I put it inside "
    "my coat where it stayed damp for a week. I did not say thank you.")
_GLASS_SEA = (
    "I crossed the Glass Sea with Captain Sorn on a hull that rang like a "
    "struck bell every time the swell took it. He made me hold the tiller "
    "through the third night so that I would learn what the storm route felt "
    "like in my wrists, and the cold of it is still the first thing I "
    "remember about him.")
_NACRE = (
    "I promised Iven safe passage out of Nacre while the market awnings "
    "snapped above us and someone's burning sugar caught in my throat. He "
    "did not believe me, which is why I said it twice, and I have carried "
    "the second saying ever since as the one that actually bound me.")


def _journey_events():
    return [
        {"sequence": 3, "when": "last winter", "place": "Orison",
         "people": ["Mara Venn"], "kind": "departure", "memory": _ORISON,
         "consequence": "I still owe her a map.",
         "tone": "bittersweet", "lesson": "boundaries",
         "valence": -0.4, "arousal": 0.35, "salience": 0.9},
        {"sequence": 1, "when": "two years ago", "place": "Glass Sea",
         "people": ["Captain Sorn"], "kind": "crossing", "memory": _GLASS_SEA,
         "consequence": "I learned the storm route.",
         "tone": "absorbing", "lesson": "precision",
         "valence": 0.2, "arousal": 0.7, "salience": 0.55},
        {"sequence": 2, "when": "the following spring", "place": "Nacre",
         "people": ["Iven"], "kind": "promise", "memory": _NACRE,
         "consequence": "The promise remains open.",
         "tone": "unsettling", "lesson": "responsibility",
         "valence": -0.1, "arousal": 0.5, "salience": 0.62},
    ]


def test_generated_journey_is_ordered_identified_and_bounded():
    grounded = ground_journey_history({
        "summary": "A road of bargains and losses.",
        "events": _journey_events()}, [], generated=True)

    assert [row["place"] for row in grounded["events"]] == [
        "Glass Sea", "Nacre", "Orison"]
    assert grounded["events"][0]["people"] == ["Captain Sorn"]
    assert all(row["event_id"].startswith("journey:")
               for row in grounded["events"])


def test_journey_events_carry_the_resident_paths_affect_and_ranking():
    """A journey memory and a resident memory land in the same bank, so the
    journey path must hand retrieval the same things to discriminate on."""
    events = _journey_events()
    events[0]["tone"] = "elated"          # outside the closed vocabulary
    events[1]["lesson"] = "swordsmanship"  # outside the closed vocabulary
    grounded = ground_journey_history(
        {"events": events}, [], generated=True)
    by_place = {row["place"]: row for row in grounded["events"]}

    assert by_place["Orison"]["emotional_context"] == "tone:neutral;lesson:boundaries"
    assert by_place["Glass Sea"]["emotional_context"] == "tone:absorbing;lesson:none"
    assert by_place["Nacre"]["emotional_context"] == (
        "tone:unsettling;lesson:responsibility")
    assert by_place["Orison"]["valence"] == -0.4
    assert by_place["Glass Sea"]["arousal"] == 0.7
    # The resident path's cap, not a second one: 0.9 clamps to 0.7 and the
    # three events no longer rank identically the way a flat constant made them.
    assert by_place["Orison"]["salience"] == 0.7
    assert len({row["salience"] for row in grounded["events"]}) == 3
    assert by_place["Nacre"]["kind"] == "promise"


def test_a_third_person_synopsis_is_not_an_autobiographical_memory():
    """The instruction has always been in the prompt and measurably does not
    hold; the deterministic detector is what makes it true."""
    events = _journey_events()
    events[1]["memory"] = (
        "The traveler participated in the crossing of the Glass Sea, underwent "
        "a change of allegiance, and afterward became known to the captains of "
        "the northern routes as a reliable hand in bad weather.")
    grounded = ground_journey_history(
        {"events": events}, [], generated=True)

    assert [row["place"] for row in grounded["events"]] == ["Nacre", "Orison"]
    assert grounded["grounding"]["dropped"] == [
        {"sequence": 1, "reason": "not_first_person"}]


def test_a_generated_dossier_line_is_dropped_but_a_cited_one_survives():
    thin = {"sequence": 1, "when": "once", "place": "Orison",
            "people": [], "memory": "I passed through Orison.",
            "consequence": "", "source_ids": ["lore:1"]}
    generated = ground_journey_history(
        {"events": [thin]}, [], generated=True)
    cited = ground_journey_history(
        {"events": [thin]}, [{"source_id": "lore:1"}], generated=False)

    assert generated["events"] == []
    assert generated["grounding"]["dropped"][0]["reason"] == "thin_memory"
    # Cited mode may only summarize the evidence it was handed; it cannot be
    # ordered to invent the detail that would make the count.
    assert [row["place"] for row in cited["events"]] == ["Orison"]


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
        {"authority": "generated", "guidance": "A debt should survive.",
         "event_count": 3},
        model_call=lambda payload: {
            "summary": "Mara crossed three worlds and carried one debt onward.",
            "events": _journey_events()})

    assert [event["place"] for event in result["events"]] == [
        "Glass Sea", "Nacre", "Orison"]
    assert len(written) == 4  # one era summary plus three episodes
    # The recollection is what the character remembers, with no generator
    # scaffolding welded to the front of it: no ordinal, no "<when>: " glue.
    assert written[1]["content"] == _GLASS_SEA
    assert written[-1]["content"] == _ORISON
    for row in written[1:]:
        assert not row["content"].startswith(
            ("Early in my travels", "Later,", "Most recently,"))
        assert ": " not in row["content"][:40]
    # When and place kept their own retrievable fields all along.
    assert [row["location"] for row in written[1:]] == [
        "Glass Sea", "Nacre", "Orison"]
    assert written[-1]["emotional_context"] == "tone:bittersweet;lesson:boundaries"
    assert written[-1]["salience"] == 0.7
    assert "importance" not in written[-1]
    stored = temp_db.wget(cid, "character_journey_histories", {})
    assert stored[str(char_id)]["memory_event_keys"] == result["memory_event_keys"]


def _capture_compile(temp_db, monkeypatch, route, **kwargs):
    """Compile one journey against a capturing stub and return its payload."""
    import json
    import time

    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Journey", "", time.time()))
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", json.dumps({"identity": {"name": "Mara"}}), "{}", time.time()))
    monkeypatch.setattr("mind.memory.add_memories_batch",
                        lambda rows: list(range(len(rows))))
    seen = {}

    def model_call(payload):
        seen.update(payload)
        return {"summary": "Three worlds and one debt.",
                "events": _journey_events()}

    result = compile_journey_history(
        cid, char_id, {"identity": {"name": "Mara"}}, route,
        model_call=model_call, **kwargs)
    return seen, result


def test_the_author_chooses_how_many_journey_memories(temp_db, monkeypatch):
    payload, _result = _capture_compile(
        temp_db, monkeypatch, {"authority": "generated", "event_count": 16})
    assert payload["target_events"] == 16
    assert payload["maximum_events"] == 16


def test_an_author_count_is_re_clamped_and_truncates_the_ledger(
        temp_db, monkeypatch):
    payload, result = _capture_compile(
        temp_db, monkeypatch,
        # Whatever a stale tab or an edited archive carries, the server decides.
        {"authority": "generated", "event_count": "999"})
    assert payload["target_events"] == 20

    _payload, small = _capture_compile(
        temp_db, monkeypatch, {"authority": "generated", "event_count": 2})
    assert len(result["events"]) == 3
    assert len(small["events"]) == 3  # the floor, not the requested 2


def test_a_route_minted_before_the_count_existed_reads_as_the_default(
        temp_db, monkeypatch):
    payload, _result = _capture_compile(
        temp_db, monkeypatch, {"authority": "generated"})
    assert payload["target_events"] == 12


def test_the_journey_can_run_toward_the_place_the_story_opens_at(
        temp_db, monkeypatch):
    payload, _result = _capture_compile(
        temp_db, monkeypatch, {"authority": "generated"},
        arrival_brief="a rain-soaked port at the mouth of a dead river")
    assert payload["arrival_location"] == (
        "a rain-soaked port at the mouth of a dead river")

    bare, _result = _capture_compile(
        temp_db, monkeypatch, {"authority": "generated"})
    assert bare["arrival_location"] == ""
