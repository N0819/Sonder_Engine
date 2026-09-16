"""The executable causal program, distinct from its final-state projection."""
from copy import deepcopy

from agents import director
from agents.common import prune_blocked_phase_changes
from world.causality import compile_transforms
from world.causal_program import bind_items, program_from_history, program_steps
from world.spatial import merge_scene_with_diff


def scene():
    return {"rooms": {key: {"name": key, "adjacent": []}
                      for key in ("hall", "yard", "study")},
            "entities": {"box": {"name": "Brass Box", "kind": "item"}},
            "positions": {"box": "hall", "Mara": "hall"}}


def program(*patches):
    rows = [{"chrono_id": n, "item_id": 7, "patch": patch}
            for n, patch in enumerate(patches, 1) if patch]
    diff, history, rejected = compile_transforms(
        rows, allowed_channels=set().union(*(set(p) for p in patches)))
    assert not rejected
    diff["causal_steps"] = program_from_history(history)
    return diff


def test_remove_then_restore_executes_in_order():
    diff = program({"remove_entities": ["box"]},
                   {"entities": {"box": {"name": "Brass Box", "kind": "item"}}})
    assert "box" in merge_scene_with_diff(scene(), diff)["entities"]


def test_a_blocked_later_write_restores_the_previous_transform():
    diff = program({"positions": {"Mara": "yard"}},
                   {"positions": {"Mara": "study"}})
    prune_blocked_phase_changes(diff, [{"event_id": 2, "status": "blocked"}])
    assert diff["positions"]["Mara"] == "yard"
    assert merge_scene_with_diff(scene(), diff)["positions"]["Mara"] == "yard"


def test_engine_attribution_overwrites_patch_attribution():
    diff = program({"inventory_ops": [{"op": "transfer", "object_id": "box",
                                      "to_id": "Mara", "from_event": 99}]})
    prune_blocked_phase_changes(diff, [{"event_id": 1, "status": "blocked"}])
    assert not diff.get("inventory_ops")


def test_item_binding_preserves_complementary_channels_and_rewrites_references():
    rows = [
        {"chrono_id": 1, "item_id": 7, "object_name": "Brass Box",
         "patch": {"entities": {"new_box": {"name": "Brass Box"}}}},
        {"chrono_id": 1, "item_id": 7, "object_name": "Brass Box",
         "patch": {"rooms": {"box_inside": {"name": "Box Interior",
                                           "parent_entity": "new_box"}}}},
        {"chrono_id": 2, "item_id": 7, "object_name": "Brass Box",
         "patch": {"entities": {"other_box": {"name": "Brass Box", "state": {"open": True}}},
                   "conditions": {"other_box": [{"subject_id": "other_box", "kind": "wet"}]},
                   "inventory_ops": [{"op": "transfer", "object_id": "other_box", "to_id": "Mara"}]}},
    ]
    original = deepcopy(rows)
    bound, bindings, notes = bind_items(rows, scene())
    assert rows == original
    assert bindings["7"]["entity"] == "box"
    assert list(bound[0]["patch"]["entities"]) == ["box"]
    assert list(bound[2]["patch"]["entities"]) == ["box"]
    assert bound[1]["patch"]["rooms"]["box_inside"]["parent_entity"] == "box"
    assert bound[2]["patch"]["inventory_ops"][0]["object_id"] == "box"
    assert bound[2]["patch"]["conditions"]["box"][0]["subject_id"] == "box"


def test_transfer_source_is_checked_after_the_preceding_handover():
    from types import SimpleNamespace
    from persist.commit import _refuse_unheld_transfers

    initial = scene()
    initial["positions"].update(Bela="yard", Cora="study")
    diff = program({"inventory_ops": [{"op": "transfer", "object_id": "box",
                                       "from_id": "Mara", "to_id": "Bela", "relation": "held"}]},
                   {"inventory_ops": [{"op": "transfer", "object_id": "box",
                                       "from_id": "Bela", "to_id": "Cora", "relation": "held"}]})
    warnings = []
    ctx = SimpleNamespace(add_warning=warnings.append, tell_director=warnings.append)
    final = merge_scene_with_diff(
        initial, diff, causal_guard=lambda world, patch: _refuse_unheld_transfers(ctx, world, patch))
    assert not warnings
    assert final["positions"]["box"] == "study"


def test_same_span_keeps_multiple_items_and_multiple_hands():
    diff = program({"entities": {"new": {"name": "New Thing"}},
                    "positions": {"Mara": "yard", "new": "yard"}})
    worlds = []
    final = merge_scene_with_diff(scene(), diff, causal_worlds=worlds)
    assert final["positions"]["new"] == "yard"
    assert len(worlds) == 1
    assert worlds[0]["before"]["positions"]["Mara"] == "hall"


def test_replay_keeps_each_intermediate_world():
    diff = program({"positions": {"Mara": "yard"}}, {},
                   {"positions": {"Mara": "study"}})
    # A speech-only span needs no state patch but still has a time coordinate.
    diff["causal_steps"].insert(1, {"chrono_id": 2, "stage": "resolve", "patch": {}, "events": ["speech"]})
    worlds = []
    merge_scene_with_diff(scene(), diff, causal_worlds=worlds)
    assert worlds[1]["before"]["positions"]["Mara"] == "yard"


def test_final_guard_removal_cannot_be_resurrected_by_replay():
    diff = program({"positions": {"Mara": "yard"}})
    diff["positions"].pop("Mara")
    assert merge_scene_with_diff(scene(), diff)["positions"]["Mara"] == "hall"


def test_final_guard_correction_keeps_earlier_worlds():
    diff = program({"positions": {"Mara": "yard"}},
                   {"positions": {"Mara": "study"}})
    diff["positions"]["Mara"] = "hall"
    steps = program_steps(diff)
    assert steps[0]["patch"]["positions"]["Mara"] == "yard"
    assert steps[-1]["patch"]["positions"]["Mara"] == "hall"


def test_room_registry_renames_preserve_the_intermediate_destination():
    from persist.commit import _apply_room_renames

    diff = program({"positions": {"Mara": "garden"}},
                   {"positions": {"Mara": "study"}})
    _apply_room_renames(diff, {"garden": "yard"})
    worlds = []
    merge_scene_with_diff(scene(), diff, causal_worlds=worlds)
    assert worlds[1]["before"]["positions"]["Mara"] == "yard"


def test_missing_handle_does_not_take_a_later_authored_handle():
    out = {"ledgers": [{"item_names": ["box"], "item_ids": [None]},
                       {"item_names": ["key"], "item_ids": [1]}]}
    director.normalize_causal_ledger(out)
    assert out["ledgers"][0]["item_ids"] != out["ledgers"][1]["item_ids"]


def test_binding_happens_before_partial_entity_validation(temp_db, monkeypatch):
    from tests.test_director_orchestration import _make_ctx, _fake_agent, _action_interp, BASE_SCENE
    initial = deepcopy(BASE_SCENE)
    initial["entities"]["box"] = {"name": "Brass Box", "kind": "item"}
    initial["positions"]["box"] = "keeper_room"
    responses = {
        "director_resolve": {"ledgers": [
            {"chrono_id": n, "item_ids": [7], "item_names": ["Brass Box"],
             "source_entity_id": "character:mara", "event": event,
             "resolution_notes": event, "categories": ["entities"]}
            for n, event in [(1, "Mara opens the box"), (2, "Mara shuts the box")]
        ]},
        "director_objects": {"results": [
            {"status": "encoded", "transforms": [{"patch": {"entities": {
                "first_key": {"name": "Brass Box", "state": {"open": True}}}}}]},
            {"status": "encoded", "transforms": [{"patch": {"entities": {
                "second_key": {"state": {"open": False}}}}}]},
        ]},
    }
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, responses))
    ctx = _make_ctx(temp_db, scene=initial, interp=_action_interp())
    out = director.director_resolve(ctx, 0)
    assert set(out["state_diff"]["entities"]) == {"box"}
    steps = out["state_diff"]["causal_steps"]
    boxes = [s["patch"]["entities"]["box"] for s in steps if s["patch"].get("entities")]
    assert [box["state"]["open"] for box in boxes] == [True, False]
    payload = next(c["payload"] for c in calls if c["step_key"] == "director_objects")
    assert all("item_ids" not in row and "chrono_id" not in row for row in payload["ledgers"])


def test_item_binding_does_not_merge_a_primary_object_with_its_interior():
    rows = [{"chrono_id": 1, "item_id": 7, "object_name": "Box", "patch": {
        "entities": {"box": {"name": "Box"}},
        "rooms": {"inside": {"name": "Box", "parent_entity": "box"}},
    }}]
    bound, bindings, _ = bind_items(rows)
    assert bindings == {"7": {"entity": "box"}}
    assert set(bound[0]["patch"]["rooms"]) == {"inside"}


def test_wrapped_live_inventory_patches_keep_their_items_and_chronology(temp_db, monkeypatch):
    from tests.test_director_orchestration import _make_ctx, _fake_agent, BASE_SCENE

    scene = deepcopy(BASE_SCENE)
    scene["entities"].update({
        "key": {"name": "Copper key", "kind": "item"},
        "mug": {"name": "Empty mug", "kind": "item"},
    })
    operations = [
        {"op": "transfer", "object_id": "key", "from_id": "table",
         "to_id": "Mara", "relation": "held"},
        {"op": "transfer", "object_id": "key", "from_id": "Mara", "to_id": "table"},
        {"op": "transfer", "object_id": "mug", "from_id": "keeper_room", "to_id": "shelf"},
    ]
    items = [(7, "Copper key"), (7, "Copper key"), (8, "Empty mug")]
    responses = {
        "director_resolve": {"ledgers": [
            {"chrono_id": n, "item_ids": [item], "item_names": [name],
             "source_entity_id": "character:mara", "event": f"transfer {name}",
             "resolution_notes": f"transfer {name}", "categories": ["inventory_ops"]}
            for n, (item, name) in enumerate(items, 1)]},
        "director_objects": {"results": [
            {"status": "encoded", "transforms": [{"item": name,
                "patch": {"state_diff": {"inventory_ops": [op]}}}]}
            for (_, name), op in zip(items, operations)]},
    }
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], responses))
    ctx = _make_ctx(temp_db, scene=scene, interp={"sequence": []})
    out = director.director_resolve(ctx, 0)
    history = [row for row in out["orchestration"]["transform_history"]
               if row["patch"].get("inventory_ops")]
    assert [row["item_id"] for row in history] == [7, 7, 8]
    assert [row["chrono_id"] for row in history] == [1, 2, 3]
    assert [row["patch"]["inventory_ops"][0]["to_id"] for row in history] == [
        "Mara", "table", "shelf"]
    errors = out["orchestration"]["specialists"]["objects"].get("result_alignment_errors", [])
    assert not errors


def test_wrapper_normalization_does_not_bypass_ownership_or_guess_outer_precedence():
    state = {"ledger_items": [{"chrono_id": 1, "item_id": 7,
                               "item_ids": [7], "item_names": ["key"]}]}
    results = {"objects": {"results": [{"transforms": [{"patch": {
        "state_diff": {"inventory_ops": [{"op": "transfer", "object_id": "key"}],
                       "positions": {"Mara": "hall"}}, "notes": ["carried"],
    }}]}]}}
    patches, _, notes = director._bind_specialist_patches(
        results, {"objects": state}, {}, {})
    assert set(patches[("objects", 0, 0)]) == {"inventory_ops"}
    assert any(note.get("channels") == ["positions"] for note in notes)

    results["objects"]["results"][0]["transforms"][0]["patch"] = {
        "state_diff": {"inventory_ops": [{"object_id": "key"}]},
        "entities": {"key": {"name": "key", "kind": "item"}},
    }
    patches, _, notes = director._bind_specialist_patches(
        results, {"objects": state}, {}, {})
    assert set(patches[("objects", 0, 0)]) == {"entities"}
    assert any(note.get("channels") == ["state_diff"] for note in notes)


def test_exact_nested_pose_channel_is_recovered_before_station_validation(temp_db, monkeypatch):
    from tests.test_director_orchestration import _make_ctx, _fake_agent

    responses = {
        "director_resolve": {"ledgers": [{
            "chrono_id": 1, "item_ids": [1], "item_names": ["Mara"],
            "source_entity_id": "character:mara", "event": "sits on the chair",
            "resolution_notes": "Mara sits", "categories": ["stations", "poses"]}]},
        "director_spatial": {"results": [{"status": "encoded", "transforms": [{
            "item": "Mara", "patch": {"stations": {
                "Mara": {"at": "chair", "near": []},
                "poses": {"Mara": {"posture": "seated", "support": "chair"}},
                "invalid_record": {"unused": "value"},
            }}}]}]},
    }
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], responses))
    out = director.director_resolve(_make_ctx(temp_db, interp={"sequence": []}), 0)
    state = out["orchestration"]["specialists"]["spatial"]
    assert not any("dropped malformed stations record(s): poses" in error
                   for error in state.get("result_alignment_errors", []))
    assert any("dropped malformed stations record(s): invalid_record" in error
               for error in state["result_alignment_errors"])
    assert out["state_diff"]["poses"]["Mara"]["posture"] == "seated"
    assert out["state_diff"]["stations"]["Mara"]["at"] == "chair"


def test_prevalidation_binding_leaves_malformed_fields_to_the_validator():
    rows = [{"chrono_id": 1, "item_id": 7, "object_name": "Box", "patch": {
        "entities": {"box": {"name": "Box", "aliases": 42}},
        "inventory_ops": 42, "remove_entities": 42,
    }}]
    bound, bindings, _ = bind_items(rows)
    assert bindings == {"7": {"entity": "box"}}
    assert bound[0]["patch"]["inventory_ops"] == 42


def test_recompilation_cannot_restore_a_channel_dropped_by_the_stage(temp_db, monkeypatch):
    from tests.test_director_orchestration import _make_ctx, _fake_agent
    responses = {
        "director_interpret": {"ledgers": [{
            "chrono_id": 1, "item_ids": [7], "item_names": ["Mara"],
            "event": "Mara greets the keeper", "resolution_notes": "A greeting",
            "categories": ["introductions"],
        }]},
        "director_social": {"results": [{"status": "encoded", "transforms": [
            {"patch": {"public_evidence": [{"source_id": "invented", "speech_act": "greeting"}]}}
        ]}]},
    }
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], responses))
    ctx = _make_ctx(temp_db, player_input="Mara greets the keeper")
    ctx.director_interpret = None
    out = director.director_interpret(ctx, 0)
    assert not out["state_assertions"].get("public_evidence")
    assert all("public_evidence" not in row["patch"]
               for row in out["state_assertions"].get("causal_steps") or [])


def test_same_span_and_same_item_keeps_every_complementary_transform():
    transforms = [
        {"chrono_id": 1, "item_id": 7, "patch": {"entities": {"box": {"name": "Box"}}}},
        {"chrono_id": 1, "item_id": 7, "patch": {"inventory_ops": [{"op": "transfer", "object_id": "box", "to_id": "yard"}]}},
        {"chrono_id": 1, "item_id": 9, "patch": {"entities": {"key": {"name": "Key"}}}},
    ]
    diff, history, rejected = compile_transforms(transforms, allowed_channels=["entities", "inventory_ops"])
    assert not rejected and len(history) == 3
    diff["causal_steps"] = program_from_history(history)
    assert len(diff["causal_steps"]) == 1
    final = merge_scene_with_diff(scene(), diff)
    assert final["positions"]["box"] == "yard"
    assert "key" in final["entities"]


def test_invocation_local_ids_stay_separate():
    from agents.common import merge_player_state_assertions
    first = program({"positions": {"Mara": "yard"}})
    first["causal_steps"][0].update(stage="interpret", events=["onset:move"])
    second = program({"positions": {"Mara": "study"}})
    second["causal_steps"][0].update(stage="resolve", events=["resolve:move"])
    combined = merge_player_state_assertions(first, second)
    prune_blocked_phase_changes(combined, [{"event_id": "resolve:move", "status": "blocked"}])
    assert merge_scene_with_diff(scene(), combined)["positions"]["Mara"] == "yard"


def test_several_contact_spans_age_the_contacts_only_once(monkeypatch):
    from world import spatial_merge
    original = spatial_merge.apply_contact_ops
    calls = []
    def apply(world, ops, **kwargs):
        if ops:
            calls.append(kwargs.get("_age"))
        return original(world, ops, **kwargs)
    monkeypatch.setattr(spatial_merge, "apply_contact_ops", apply)
    merge_scene_with_diff(scene(), program(
        {"contact_ops": [{"op": "clear", "actor": "Ada"}]},
        {"contact_ops": [{"op": "clear", "actor": "Mara"}]}))
    assert calls == [True, False]


def test_onset_contact_normalization_preserves_add_remove_chronology(temp_db, monkeypatch):
    from tests.test_director_orchestration import _make_ctx, _fake_agent

    initial = scene()
    initial["positions"]["The Stranger"] = "hall"
    initial["attire"] = {"The Stranger": {}, "Mara": {}}
    rows = [{"chrono_id": n, "item_ids": [1, 7],
             "item_names": ["The Stranger", "Brass Box"],
             "event": text, "observable": text,
             "source_entity_id": "persona:primary", "commitment": "asserted",
             "resolution_notes": text, "categories": ["contacts"]}
            for n, text in enumerate([
                "The Stranger grips the brass box.",
                "The Stranger releases the brass box."], 1)]
    responses = {
        "director_interpret": {"ledgers": rows},
        "director_contact": {"results": [
            {"status": "encoded", "transforms": [{"item": "The Stranger", "patch": {
                "contact_ops": [{"op": op, "actor": "The Stranger",
                    "actor_part": "hand", "target": "box", **fields}]}}],
             "settled": {"Brass Box": "already_true"}}
            for op, fields in [("add", {"manner": "grip", "relation": "surface",
                                         "motion": "settled"}), ("remove", {})]]},
    }
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], responses))
    ctx = _make_ctx(temp_db, scene=initial,
                    player_input="I grip the brass box, then release it.")
    ctx.director_interpret = None
    out = director.director_interpret(ctx, 0)
    for field in ("state_assertions", "onset_state_assertions"):
        steps = program_steps(out[field])
        contact_steps = [step for step in steps if step["patch"].get("contact_ops")]
        assert [step["chrono_id"] for step in contact_steps] == [1, 2]
        assert [step["patch"]["contact_ops"][0]["op"]
                for step in contact_steps] == ["add", "remove"]
        assert all(step["stage"] == "interpret" for step in contact_steps)
        assert contact_steps[0]["patch"]["contact_ops"][0]["target_part"] == ""
        assert not merge_scene_with_diff(initial, out[field])["contacts"]


def test_authorial_contact_program_admits_other_actors_without_widening_actor_only():
    initial = scene()
    initial["positions"].update({"The Stranger": "hall", "Mara": "hall"})
    for world_author in (False, True):
        diff = program({"contact_ops": [{"op": "add", "actor": "Mara",
            "actor_part": "hand", "target": "box", "manner": "grip",
            "relation": "surface", "motion": "settled"}]})
        notes = []
        contacts = director._validated_causal_contact_program(
            initial, diff, diff["contact_ops"], "The Stranger",
            world_author=world_author, report=notes.append)
        assert bool(contacts) is world_author
        assert bool(notes) is not world_author
        assert not [step for step in program_steps(diff)
                    if step["stage"] == "engine" and step["patch"].get("contact_ops")]


def test_contact_validation_reads_prior_spans_and_keeps_repeated_operations():
    initial = scene()
    initial["positions"]["Mara"] = "yard"
    add = {"op": "add", "actor": "Mara", "actor_part": "hand",
           "target": "box", "manner": "grip", "relation": "surface",
           "motion": "settled"}
    remove = {"op": "remove", "actor": "Mara", "target": "box"}
    diff = program({"positions": {"Mara": "hall"}},
                   {"contact_ops": [add]}, {"contact_ops": [remove]},
                   {"contact_ops": [add]}, {"contact_ops": [remove]})
    notes = []
    contacts = director._validated_causal_contact_program(
        initial, diff, diff["contact_ops"], "Mara", report=notes.append)
    assert not notes
    assert [op["op"] for op in contacts] == ["add", "remove", "add", "remove"]
    assert [op["from_event"] for op in contacts] == [2, 3, 4, 5]
    assert not merge_scene_with_diff(initial, diff)["contacts"]


def test_cumulative_time_readings_do_not_tick_survival_twice(monkeypatch):
    from world import survival
    calls = []
    monkeypatch.setattr(survival, "tick_vitals", lambda world, elapsed, **kw: calls.append(elapsed))
    initial = scene()
    initial["vitals"] = {"Mara": {"air": 1.0}}
    diff = program({"time": {"start_seconds": 0, "end_seconds": 10, "duration_seconds": 10}},
                   {"time": {"start_seconds": 0, "end_seconds": 20, "duration_seconds": 20}})
    merge_scene_with_diff(initial, diff)
    assert sum(calls) == 20
    assert diff["time"]["duration_seconds"] == 20
def test_normalization_preserves_repeated_actions_and_quotes_at_distinct_times():
    from agents.common import norm_sequence
    out = {"sequence": [
        {"type": "action", "chrono_id": 1, "attempt": "closes the tin",
         "observable": "closes the tin"},
        {"type": "speech", "chrono_id": 2, "text": "Done."},
        {"type": "action", "chrono_id": 3, "attempt": "opens the tin",
         "observable": "opens the tin"},
        {"type": "action", "chrono_id": 4, "attempt": "closes the tin",
         "observable": "closes the tin"},
        {"type": "speech", "chrono_id": 5, "text": "Done."},
    ]}
    norm_sequence(out)
    assert [row["chrono_id"] for row in out["sequence"]] == [1, 2, 3, 4, 5]
    assert [row["text"] for row in out["sequence"] if row["type"] == "speech"] == ["Done.", "Done."]


def test_causal_quote_keeps_its_recollection_and_refusal_around_an_inner_quote():
    from agents.common import repair_narrated_speech_elements
    line = "Yesterday you said, 'Break the lock,' but I am not doing that"
    out = {"sequence": [{"type": "speech", "chrono_id": 5,
                         "source_entity_id": "persona:2", "text": line}],
           "speech": line}
    assert repair_narrated_speech_elements(out) == []
    assert out["sequence"][0]["text"] == out["speech"] == line


def test_structured_rewear_cancels_the_previous_remove_in_the_projection():
    added = {"name": "coat", "covers": ["arms", "torso"]}
    diff = program({"attire": {"Mara": {"remove": ["coat"]}}},
                   {"attire": {"Mara": {"add": [added]}}})
    assert diff["attire"]["Mara"]["remove"] == []
    assert diff["attire"]["Mara"]["add"] == [added]
    steps = program_steps(diff)
    assert steps[0]["patch"]["attire"]["Mara"]["remove"] == ["coat"]
    assert steps[1]["patch"]["attire"]["Mara"]["add"] == [added]


def test_later_wardrobe_operation_addresses_the_garment_not_its_add_metadata():
    diff = program({"attire": {"Mara": {"add": [{"name": "coat", "covers": ["head"]}]}}},
                   {"attire": {"Mara": {"add": [{"name": "coat", "covers": ["torso"]}]}}},
                   {"attire": {"Mara": {"remove": ["coat"]}}})
    assert diff["attire"]["Mara"]["add"] == []
    assert diff["attire"]["Mara"]["remove"] == ["coat"]
    assert len(diff["causal_steps"]) == 3
