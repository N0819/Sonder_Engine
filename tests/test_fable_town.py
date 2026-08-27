"""Compact seams for planned towns and presimulation.

Long realism playthroughs remain tools. These tests prove closure, graph
composition, intervention firewalls, determinism, and grounded history.
"""

import time

import pytest

from world.charter_generate import (
    close_plan, ensure_required_rooms, ground_history_output, propose_town)
from world.charter_history import (
    featured_resident_bindings, featured_resident_seed,
    ground_personal_history, ground_recent_history,
    integrate_featured_resident)
from world.charter_intervene import apply_due
from world.charter_economy import (
    advance_economy, ensure_supply_points, normalize_economy)
from world.charter_plan import plan_watch
from world.charter_runtime import (
    exchange_caravan_freight, load_caravan_freight, presim_registry,
    generation_lore, registry_for, save_registry)
from world.structure import (
    apply_frontier_mutations, composed_scene, materialize_planned_fringe,
    plant_structure, planned_context, prepare_frontier_expansion,
    skeleton_rooms, structure_warnings)


def _plan():
    return {
        "name": "Aldermere",
        "structure": {"key": "aldermere", "max_planned": 20,
                      "grammar": [{"kind": "lane", "names": ["North Lane"],
                                   "purposes": ["homes"]}]},
        "rooms": {
            "square": {"name": "Market Square", "purpose": "market",
                       "adjacent": [{"to": "mill", "barrier": "open_door"}]},
            "mill": {"name": "Old Mill", "purpose": "milling",
                     "adjacent": [{"to": "square", "barrier": "open_door"}]},
        },
        "charters": [{
            "key": "town_council",
            "naming": {"given": ["Mara", "Oren"], "family": ["Vale"]},
            "priority": ["grain"],
            "upkeeps": {"grain": {
                "place": "mill", "floor": 0.25, "level": 1,
                "fails_untended": "a_week",
                "one_body_restores_in": "a_shift"}},
            "posts": {"miller": {"place": "mill", "serves": ["grain"],
                                   "requires": {"milling": 1}}},
            "populations": [{"post": "miller", "count": 2,
                             "competence": {"milling": 1}, "berth": "mill"}],
        }],
    }


def test_qualitative_plan_closes_to_stable_named_people_and_rates():
    town = close_plan(_plan(), history={"interventions": []})
    charter = town["charters"]["town_council"]

    assert charter["upkeeps"]["grain"]["drift_per_hour"] > 0
    assert charter["upkeeps"]["grain"]["service_per_hour"] > 0
    # A Charter post is a continuous watch. Closure supplies the third shift
    # instead of making two millers work until the needs system drops them.
    assert len(charter["bodies"]) == 3
    names = [body["name"] for body in charter["bodies"].values()]
    assert len(set(names)) == 3
    assert close_plan(_plan())["charters"]["town_council"]["bodies"] \
        == close_plan(_plan())["charters"]["town_council"]["bodies"]


def test_featured_resident_uses_public_card_for_placement_and_exact_identity():
    sheet = {
        "identity": {"name": "Dr. Sarah Moon"},
        "knowledge": {
            "public_history": "Lead psychologist for unusual residents.",
            "private_history": [{"content": "DO NOT SEND THIS TO CHARTER"}],
        },
        "competence": {"abilities": [{
            "name": "Applied psychology", "level": "expert",
            "scope": "assessment and rehabilitation",
            "limits": "PRIVATE LIMIT NOTE"}, {
            "name": "Secret baking", "level": "expert",
            "scope": "pastries made alone"}]},
    }
    resident = featured_resident_seed(63, sheet)
    seen = {}

    def planner(payload):
        seen.update(payload)
        plan = _plan()
        charter = plan["charters"][0]
        charter["posts"]["psychologist"] = {
            "place": "square", "serves": [],
            "requires": {"psychology": 3}}
        charter["featured_residents"] = [{
            "seed_id": resident["seed_id"], "post": "psychologist",
            "competence": {"psychology": 3}, "berth": "square",
            "title": "Dr."}]
        return plan

    plan = propose_town(
        [], constraints={"featured_residents": [resident]}, model_call=planner)
    town = close_plan(plan, featured_residents=[resident])
    bindings = featured_resident_bindings(
        {"items": {"town_council": {
            "state": town["charters"]["town_council"]}}},
        [resident["seed_id"]])
    binding = bindings[resident["seed_id"]]
    body = town["charters"]["town_council"]["bodies"][binding["body"]]

    assert "DO NOT SEND" not in str(seen)
    assert "PRIVATE LIMIT NOTE" not in str(seen)
    assert "Secret baking" not in str(seen)
    assert body["name"] == "Dr. Sarah Moon"
    assert body["resident_seed_id"] == "character:63"
    assert body["competence"]["psychology"] == 3
    # The authored person counts toward the rotation; closure adds only two.
    assert len([key for key in town["charters"]["town_council"]["bodies"]
                if key.startswith("psychologist:")]) == 3


def test_featured_resident_omission_repairs_to_relevant_existing_post():
    plan = _plan()
    plan["charters"][0]["posts"]["psychologist"] = {
        "place": "square", "serves": [],
        "requires": {"psychology": 2}}
    resident = {
        "seed_id": "character:7", "name": "Sana",
        "public_history": "A clinical psychologist.",
        "abilities": [{"name": "psychology"}],
    }

    town = close_plan(plan, featured_residents=[resident])
    body = next(body for body in town["charters"]["town_council"]["bodies"].values()
                if body.get("resident_seed_id") == "character:7")

    assert body["competence"]["psychology"] == 2
    assert body["place"] == "square"


def test_watch_prefers_a_cross_qualified_residents_home_post():
    plan = _plan()
    charter = plan["charters"][0]
    charter["posts"]["research_lead"] = {
        "place": "square", "serves": [], "requires": {"research": 2}}
    charter["posts"]["lead_psychologist"] = {
        "place": "square", "serves": [], "requires": {"psychology": 2}}
    charter["populations"].extend([
        {"post": "research_lead", "count": 3,
         "competence": {"research": 2}, "berth": "square"},
        {"post": "lead_psychologist", "count": 2,
         "competence": {"psychology": 2, "research": 2}, "berth": "square"},
    ])
    resident = {"seed_id": "character:63", "name": "Sarah Moon",
                "public_history": "Lead psychologist and researcher.",
                "abilities": []}
    charter["featured_residents"] = [{
        "seed_id": "character:63", "post": "lead_psychologist",
        "competence": {"psychology": 3, "research": 3}, "berth": "square"}]
    closed = close_plan(plan, featured_residents=[resident]) \
        ["charters"]["town_council"]
    body_key = next(key for key, body in closed["bodies"].items()
                    if body.get("resident_seed_id") == "character:63")

    watch = plan_watch(closed, seed=8)["watch"]

    assert watch["lead_psychologist"].startswith("lead_psychologist:")
    assert watch["research_lead"] != body_key
    assert watch["research_lead"].startswith("research_lead:")


def test_personal_history_can_interpret_only_cited_charter_surfaces():
    packet = {"evidence": [{
        "source_id": "service:real", "surface": "I stood infirmary watch.",
        "kind": "semantic", "provenance": "remembered", "salience": .55,
        "confidence": 1, "location": "infirmary", "entities": ["medic"],
    }]}
    grounded = ground_personal_history({
        "career_reflection": "Routine became a form of steadiness.",
        "career_source_ids": ["service:real"],
        "memories": [
            {"source_id": "service:real", "tone": "steadying",
             "lesson": "patience", "salience": 1.0,
             "personal_meaning": "I secretly saved the city."},
            {"source_id": "invented:breach", "tone": "meaningful"},
        ],
    }, packet)

    assert len(grounded["memories"]) == 1
    assert grounded["memories"][0]["content"] == "I stood infirmary watch."
    assert "saved the city" not in grounded["memories"][0]["content"]
    assert grounded["memories"][0]["emotional_context"] == \
        "tone:steadying;lesson:patience"
    assert grounded["memories"][0]["salience"] == .55
    assert grounded["grounding"]["dropped"][0]["source_id"] == "invented:breach"


def test_sparse_recent_life_is_rejected_instead_of_becoming_canon():
    packet = {"recent_context": {
        "resident_body_id": "sana", "recent_window_hours": 720,
        "people": [{"body_id": "iven", "name": "Iven Vale"}],
        "places": [{"location_id": "clinic", "name": "Clinic"}],
    }, "evidence": []}
    thin_batch = {"episodes": [{
        "sequence": i, "when": f"day {i}", "title": f"Case {i}",
        "location_id": "clinic", "participant_ids": ["iven"],
        "memory": (
            "I worked with Iven Vale on a difficult intake, compared the "
            "conflicting notes twice, asked what assumption each of us had "
            "made, and chose to pause the routine interview until we could "
            "explain the discrepancy without guessing or blaming the patient."),
        "consequence": "We left one question open and changed the next review.",
    } for i in range(1, 10)]}

    with pytest.raises(ValueError, match="at least 10 rich independent memories"):
        ground_recent_history(thin_batch, packet)


def test_featured_resident_history_seeds_turn_zero_then_retires_charter_mind(
        temp_db, monkeypatch):
    import json

    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Featured resident", "", time.time()))
    sheet = {"identity": {"name": "Sana"},
             "knowledge": {"public_history": "Clinic psychologist."}}
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Sana", json.dumps(sheet), "{}", time.time()))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
        (cid, char_id))
    plan = _plan()
    plan["charters"][0]["featured_residents"] = [{
        "seed_id": f"character:{char_id}", "post": "miller",
        "competence": {"milling": 1}, "berth": "mill"}]
    resident = {"seed_id": f"character:{char_id}", "name": "Sana",
                "public_history": "Clinic psychologist.", "abilities": []}
    charter = close_plan(plan, featured_residents=[resident]) \
        ["charters"]["town_council"]
    body_key = next(key for key, body in charter["bodies"].items()
                    if body.get("resident_seed_id") == f"character:{char_id}")
    charter["stood"] = {body_key: {"miller": 18}}
    charter["experiences"] = {body_key: [
        {"id": f"social:{i}", "kind": "social", "role": "actor",
         "at_hours": i * 4, "place": "mill", "actor": body_key,
         "other": "miller:0002", "act": act}
        for i, act in enumerate(("greet", "ask", "tell", "reconcile"), 1)
    ]}
    save_registry(cid, {"items": {"town_council": {
        "state": charter, "window_hours": 4}}})
    binding = featured_resident_bindings(
        registry_for(cid), [f"character:{char_id}"])[f"character:{char_id}"]
    written = []
    monkeypatch.setattr(
        "mind.memory.add_memories_batch",
        lambda rows: written.extend(rows) or list(range(len(rows))))

    def interpret(payload):
        assert payload["character_context_for_interpretation_only"] \
            ["public_history"] == "Clinic psychologist."
        context = payload["recent_context"]
        other = context["people"][0]
        place = context["places"][0]
        return {
            "overview": "A month of careful work left Sana with practical "
                        "trust, several unresolved questions, and a routine "
                        "that now feels personally inhabited.",
            "episodes": [{
                "sequence": i, "when": f"{13 - i} days ago",
                "title": f"The flour test {i}", "kind": "work_choice",
                "location_id": place["location_id"],
                "participant_ids": [other["body_id"]],
                "memory": (
                    f"I worked beside {other['name']} when the mill began "
                    f"producing an uneven batch marked {i}. We compared the "
                    "texture by hand, argued over whether haste or damp grain "
                    "was responsible, and I chose to stop the line long enough "
                    "to test both possibilities. The scratched brass scoop on "
                    "the bench helped me notice which sample had clumped first."),
                "consequence": (
                    f"We kept sample {i} aside, and I became more willing to "
                    "challenge a familiar explanation before the next shift."),
                "tone": "meaningful", "lesson": "precision",
                "salience": .6,
            } for i in range(1, 13)],
        }

    result = integrate_featured_resident(
        cid, char_id, binding, sheet, model_call=interpret)
    final = registry_for(cid)["items"]["town_council"]["state"]
    state_row = temp_db.q(
        "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
        (cid, char_id), one=True)

    # TURN ZERO, NOT NULL. `mind/memory_read` filters `turn_idx IS NOT NULL`
    # for the two readers that constitute a self -- the autobiographical
    # summary and the recent-memory buffer that grounds a beat -- so a null
    # here left the inherited life reachable by embedding search alone: a
    # character with a past it could neither narrate nor be reminded of.
    # Nothing was protecting the null; rollback deletes by `turn_id`, which
    # these rows carry as None, so they survive a branch either way.
    assert written and written[0]["turn_idx"] == 0
    assert written[0]["content"] == "I worked as miller in mill."
    assert len(written) == 14  # career + recent overview + 12 episodes
    assert written[1]["kind"] == "semantic"
    assert written[2]["content"].startswith("The flour test 1")
    assert written[-1]["content"].startswith("The flour test 12")
    assert len({row["event_key"] for row in written}) == len(written)
    assert all("watches" not in row["content"] for row in written)
    assert final["bindings"][body_key]["char_id"] == char_id
    assert body_key not in final["minds"]
    other_key = next(key for key in final["bodies"] if key != body_key)
    reciprocal = final["experiences"][other_key]
    assert len(reciprocal) == 12
    assert all(row["kind"] == "shared_prestory" for row in reciprocal)
    assert all("Sana" in row["surface"] for row in reciprocal)
    assert json.loads(state_row["state"])["charter_origin"]["stood"] == {
        "miller": 18}
    assert result["overview"].startswith("A month")
    assert result["reciprocal_records"] == 12
    from world.charter_runtime import charter_diagnostics
    diagnostic = charter_diagnostics(
        cid, charter_key="town_council", body_key=body_key)
    assert diagnostic["items"]["town_council"] \
        ["featured_resident_histories"][str(char_id)] \
        ["memory_event_keys"] == result["memory_event_keys"]


def test_generated_posts_have_real_shift_crews_and_run_quietly():
    charter = close_plan(_plan())["charters"]["town_council"]

    after, events = presim_registry(
        {"items": {"town_council": {"state": charter,
                                      "window_hours": 4}}},
        horizon_hours=720, active_tail_hours=0, seed=4)
    final = after["items"]["town_council"]["state"]

    assert len(final["bodies"]) == 3
    assert final["reported"].get("post_unfilled") == {}
    assert not any(event["kind"] in {
        "body_unable", "post_unfilled"} for event in events)
    # Equal hands actually rotate; stable id ordering must not turn the last
    # member into a permanent reserve with no working history.
    assert all(final["stood"].get(body_id, {}).get("miller", 0) > 0
               for body_id in final["bodies"])
    closure = final["history"]["architecture"]["closure"]
    assert closure["staffing_model"] == "three_person_continuous_watch"
    assert closure["staffing_reserve_added"] == ["miller:0003"]


def test_closure_accepts_model_shorthand_for_requirements_and_dependencies():
    plan = _plan()
    upkeep = plan["charters"][0]["upkeeps"]["grain"]
    upkeep["requires"] = ["mechanical", "logistics"]
    upkeep["depends_on"] = "power"
    post = plan["charters"][0]["posts"]["miller"]
    post["requires"] = ["milling"]
    post["serves"] = "grain"
    plan["charters"][0]["populations"][0]["competence"] = "milling"

    charter = close_plan(plan)["charters"]["town_council"]

    assert charter["upkeeps"]["grain"]["requires"] == {
        "mechanical": 1, "logistics": 1}
    assert charter["upkeeps"]["grain"]["depends_on"] == ["power"]
    assert charter["posts"]["miller"]["requires"] == {"milling": 1}
    assert charter["posts"]["miller"]["serves"] == ["grain"]
    assert all(body["competence"] == {"milling": 1}
               for body in charter["bodies"].values())


def test_numeric_authority_is_dropped_instead_of_crashing_or_granting_power():
    plan = _plan()
    plan["charters"][0]["posts"]["miller"]["authority"] = 4

    charter = close_plan(plan)["charters"]["town_council"]

    assert charter["posts"]["miller"]["authority"] == []


def test_economy_accepts_model_list_shorthand():
    economy = normalize_economy({
        "goods": [{"key": "food", "label": "Canteen food",
                   "base_value": 2}],
        "stocks": [{"holder": "stores", "good": "food", "amount": 12}],
        "targets": [{"holder": "stores", "good": "food",
                     "minimum": 4, "desired": 10, "capacity": 20}],
        "flows": [{"key": "meals", "holder": "stores", "good": "food",
                   "kind": "consume", "lots_per_hour": 0.25}],
        "markets": [{"key": "canteen", "holder": "stores",
                     "place": "staff_canteen"}],
    })

    assert economy["goods"]["food"]["label"] == "Canteen food"
    assert economy["stocks"]["stores"]["food"] == 12
    assert economy["targets"]["stores"]["food"]["desired"] == 10
    assert economy["flows"]["meals"]["kind"] == "consume"
    assert economy["markets"]["canteen"]["place"] == "staff_canteen"


def test_closure_repairs_loose_population_shapes_into_a_working_charter():
    plan = {
        "name": "Site-17", "structure": {"key": "site-17"},
        "rooms": {
            "entry": {"name": "Entry", "adjacent": []},
            "wing": {"name": "Wing", "adjacent": []},
        },
        "charters": [{
            "key": "operations",
            "upkeeps": {"containment": {
                "place": "wing", "fails_untended": "a_week",
                "one_body_restores_in": "a_shift"}},
            "posts": {"director": {
                "place": "entry", "serves": "overall site",
                "requires": {"clearance": 4}}},
            "populations": [
                {"post": "director", "count": 1,
                 "competence": "high", "berth": "permanent"},
                {"post": "researcher", "count": 4,
                 "competence": "standard", "berth": "rotating"},
            ],
        }],
    }

    charter = close_plan(plan)["charters"]["operations"]
    watch = plan_watch(charter, horizon_hours=4)["watch"]

    assert set(body["place"] for body in charter["bodies"].values()) \
        <= {"entry", "wing"}
    assert charter["bodies"]["director:0001"]["competence"]["clearance"] == 4
    assert "researcher" in charter["posts"]
    assert any("containment" in post["serves"]
               for post in charter["posts"].values())
    assert watch


def test_author_required_facilities_survive_a_sparse_model_plan():
    town = close_plan(_plan())
    added = ensure_required_rooms(town, [
        {"id": "medical", "name": "Medical Wing",
         "purpose": "treatment and quarantine", "adjacent": ["square"]},
        {"id": "utilities", "name": "Utilities Level",
         "purpose": "power, water, and ventilation",
         "adjacent": ["medical"]},
    ])

    assert added == ["medical", "utilities"]
    assert town["rooms"]["medical"]["name"] == "Medical Wing"
    assert town["rooms"]["medical"]["adjacent"][0]["to"] == "square"
    assert town["rooms"]["utilities"]["adjacent"][0]["to"] == "medical"
    assert town["structure"]["max_planned"] >= len(town["rooms"])


def test_net_consumption_gets_an_explicit_boundary_supply_point():
    economy = normalize_economy({
        "goods": {"food": {"label": "Food"}},
        "stocks": {"stores": {"food": 10}},
        "targets": {"stores": {"food": {
            "minimum": 4, "desired": 10, "capacity": 40}}},
        "flows": {"meals": {"holder": "stores", "good": "food",
                              "kind": "consume", "lots_per_hour": 2}},
    })
    economy = ensure_supply_points(economy, {
        "loading_dock": {"name": "Loading Dock", "purpose": "deliveries"}})
    point = next(iter(economy["supply_points"].values()))
    after, _events = advance_economy(economy, 4)

    assert point["place"] == "loading_dock"
    assert point["holder"] == "stores"
    assert point["goods"]["food"] == 2
    # Reliability below one makes the compressed route consequential rather
    # than a perfect magic faucet: a small deficit remains after four hours.
    assert 9 < after["stocks"]["stores"]["food"] < 10


def test_generation_lore_ranks_the_request_but_keeps_setting_law(
        temp_db, monkeypatch):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Lore retrieval", "", time.time()))
    lid = temp_db.qi(
        "INSERT INTO lorebooks(name,chat_id) VALUES(?,NULL)", ("World",))
    rules = temp_db.qi(
        "INSERT INTO lore_entries(lorebook_id,content,category) "
        "VALUES(?,?,?)", (lid, "<rules>Keep the gates shut.</rules>", "other"))
    relevant = temp_db.qi(
        "INSERT INTO lore_entries(lorebook_id,keys,content) VALUES(?,?,?)",
        (lid, "Site-17", "Site-17 is an underground facility."))
    temp_db.qi(
        "INSERT INTO lore_entries(lorebook_id,keys,content) VALUES(?,?,?)",
        (lid, "distant farm", "An unrelated farm."))
    seen = {}

    def ranked(book_ids, query, k):
        seen.update(book_ids=list(book_ids), query=query, k=k)
        return [{"id": relevant}]

    monkeypatch.setattr("mind.memory.search_lore", ranked)
    rows, source = generation_lore(
        cid, lid, query="Site-17 medical containment", limit=2)

    assert source == lid
    assert [row["id"] for row in rows] == [rules, relevant]
    assert "Site-17" in seen["query"]


def test_planned_graph_composes_but_live_room_wins():
    skeleton = {"rooms": {
        "square": {"name": "Square", "planned": True,
                   "adjacent": [{"to": "mill", "barrier": "open_door"}]},
        "mill": {"name": "Mill", "planned": True, "adjacent": []},
    }}
    live = {"rooms": {"square": {"name": "Rainy Square",
                                   "desc": "Rain silvers the setts.",
                                   "adjacent": []}},
            "positions": {"Player": "square"}}
    merged = composed_scene(skeleton, live)

    assert merged["rooms"]["square"]["name"] == "Rainy Square"
    assert merged["rooms"]["square"]["desc"]
    assert merged["rooms"]["mill"]["planned"] is True


def test_structure_storage_and_fringe_are_prose_free(temp_db):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Fable", "", time.time()))
    town = close_plan(_plan())
    plant_structure(cid, town["structure"], town["rooms"])
    skeleton = skeleton_rooms(cid, "aldermere")
    scene = {"rooms": {"square": {"name": "Market Square", "adjacent": []}},
             "positions": {"Player": "square"}}
    scene, added = materialize_planned_fringe(cid, scene)

    assert set(skeleton["rooms"]) == {"square", "mill"}
    assert added == 1
    assert scene["rooms"]["mill"]["planned"] is True
    assert scene["rooms"]["square"]["adjacent"][0]["to"] == "mill"
    assert "desc" not in scene["rooms"]["mill"]
    context = planned_context(cid, "Old Mill")
    assert context["room_uid"] == "mill"
    assert context["purpose"] == "milling"
    assert structure_warnings(town["structure"], town["rooms"]) == []


def test_interventions_change_circumstance_not_minds():
    charter = close_plan(_plan())["charters"]["town_council"]
    charter["interventions"] = [{
        "id": "fire", "op": "upkeep_shock", "at_hours": 4,
        "upkeep": "grain", "delta": -0.9, "place": "mill",
        "surface": "smoke pours from the mill", "cause": "kiln fire"},
        {"id": "forbidden", "op": "set_relationship", "at_hours": 2}]
    before_minds = charter["minds"]
    after, events = apply_due(charter, 4)

    assert after["upkeeps"]["grain"]["level"] < 0.25
    assert after["minds"] == before_minds == {}
    assert events[0]["kind"] == "incident"
    assert after["refused_interventions"][0]["id"] == "forbidden"


def test_approaching_a_frontier_mints_one_deterministic_planned_stub(temp_db):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Frontier", "", time.time()))
    town = close_plan(_plan())
    town["rooms"]["square"]["frontier"] = ["north"]
    plant_structure(cid, town["structure"], town["rooms"])
    scene = {"rooms": {"square": {"name": "Market Square", "adjacent": []}},
             "positions": {"Player": "square"}}

    scene, mutations = prepare_frontier_expansion(cid, scene)
    minted = set(scene["rooms"]) - {"square"}
    assert len(minted) == 1
    assert mutations
    with temp_db.transaction():
        apply_frontier_mutations(cid, None, mutations)
    _, repeated = prepare_frontier_expansion(cid, scene)
    assert repeated == []


def test_presim_is_deterministic_and_history_citations_are_grounded():
    charter = close_plan(_plan())["charters"]["town_council"]
    registry = {"items": {"town_council": {
        "state": charter, "window_hours": 4}}}
    left, left_events = presim_registry(
        registry, horizon_hours=48, active_tail_hours=12,
        tail_places=["mill"], seed=19)
    right, right_events = presim_registry(
        registry, horizon_hours=48, active_tail_hours=12,
        tail_places=["mill"], seed=19)

    assert left == right
    assert left_events == right_events
    grounded = ground_history_output({"residents": {"miller:0001": {
        "summary": "worked at the mill", "turning_points": [
            {"event_id": "real", "meaning": "served"},
            {"event_id": "invented", "meaning": "became mayor"}]}}},
        [{"event_id": "real", "kind": "post_filled_again"}])
    points = grounded["residents"]["miller:0001"]["turning_points"]
    assert [point["event_id"] for point in points] == ["real"]
    assert grounded["grounding"]["dropped"]


def test_historian_can_cite_a_quiet_residents_actual_service_record():
    from world.charter_generate import narrate_actual_history

    charter = close_plan(_plan())["charters"]["town_council"]
    charter["clock_hours"] = 720
    charter["stood"] = {"miller:0001": {"miller": 90}}
    registry = {"items": {"town_council": {"state": charter}}}

    def historian(payload):
        service = next(row for row in payload["chronicle"]
                       if row["kind"] == "service_record")
        return {
            "overview": {}, "eras": [], "institutions": [],
            "residents": {"town_council/miller:0001": {
                "summary": "Mara served repeated rotations at the mill.",
                "event_ids": [service["event_id"]],
                "turning_points": [],
            }},
        }

    actual = narrate_actual_history(
        {"name": "Aldermere", "structure": {}}, registry, [],
        model_call=historian)
    resident = actual["residents"]["town_council/miller:0001"]

    assert resident["summary"].startswith("Mara served")
    assert resident["event_ids"][0].startswith("presim:service:")


def test_caravan_freight_is_loaded_from_and_sold_into_real_stock(temp_db):
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Freight", "", time.time()))
    economy = {
        "goods": {"grain": {"base_value": 1}},
        "stocks": {"granary": {"grain": 10}, "inn": {}},
        "targets": {"granary": {"grain": {"desired": 8, "capacity": 20}},
                    "inn": {"grain": {"desired": 6, "capacity": 10}}},
        "markets": {"origin": {"place": "mill", "holder": "granary"},
                    "destination": {"place": "gate", "holder": "inn"}},
    }
    save_registry(cid, {"town": {"key": "town", "economy": economy}})

    freight, loaded = load_caravan_freight(
        cid, {"from_holder": "granary", "stock": {"grain": 4}}, "mill")
    freight, sold = exchange_caravan_freight(cid, freight, "gate")
    after = registry_for(cid)["items"]["town"]["state"]["economy"]

    assert loaded and sold
    assert after["stocks"]["granary"]["grain"] == 6
    assert after["stocks"]["inn"]["grain"] == 4
    assert not freight.get("stock", {}).get("grain")
