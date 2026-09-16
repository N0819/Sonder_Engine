"""A hand's completed contribution must not hide another owner's missing work."""
import json
from copy import deepcopy

import pytest

from agents import director
from tests.test_director_orchestration import BASE_SCENE, _fake_agent, _make_ctx
from world.spatial import merge_scene_with_diff


def _completion_scene():
    scene = deepcopy(BASE_SCENE)
    scene["entities"] = {
        "cup": {"name": "Copper cup", "kind": "object", "portable": True},
        "table": {"name": "Table", "kind": "fixture"},
        "sill": {"name": "Windowsill", "kind": "fixture"},
    }
    scene["positions"].update({key: "keeper_room" for key in ("cup", "table", "sill")})
    scene["attire"]["Mara"] = {}
    scene["rooms"]["keeper_room"]["anchors"] = {
        "table": {"desc": "A table"}, "sill": {"desc": "A windowsill"}}
    scene["stations"] = {"cup": {"at": "table"}}
    return scene


def _result(channel, value):
    return {"status": "encoded", "transforms": [
        {"item": "Copper cup", "patch": {channel: value}}], "settled": {}}


def _transfer(op, origin, destination):
    return _result("inventory_ops", [{"op": op, "object_id": "cup",
        "from_id": origin, "to_id": destination,
        **({"relation": "held"} if destination == "Mara" else {})}])


def _run_completion_case(temp_db, monkeypatch, *, status="encoded", fail=False,
                         request="required_channels", stale_pickup=False):
    """Objects already answers 1, 3, 4; only span 2 lacks that owner."""
    calls = []
    rows = [{"chrono_id": number, "item_ids": [7], "item_names": ["Copper cup"],
             "source_entity_id": "character:mara", "commitment": "asserted",
             "event": event, "observable": event, "resolution_notes": event,
             "categories": categories}
            for number, event, categories in [
                (1, "Mara picks up the copper cup from the table.", ["inventory"]),
                (2, "Mara sets the copper cup on the table.", ["stations"]),
                (3, "Mara picks up the copper cup again.", ["inventory"]),
                (4, "Mara sets the copper cup on the windowsill.", ["inventory", "stations"]),
            ]]
    object_calls = []

    def objects(payload):
        object_calls.append(deepcopy(payload))
        if len(object_calls) == 1:
            pickup = _transfer("pickup", "table", "Mara")
            # Archived/normalized patches can already carry engine provenance;
            # the prior-work public view must strip that alias as well.
            pickup["transforms"][0]["patch"]["inventory_ops"][0]["from_event"] = 991
            later_pickup = ({"status": "already_true", "transforms": [], "settled": {}}
                            if stale_pickup else _transfer("pickup_again", "table", "Mara"))
            return {"results": [pickup, later_pickup,
                                _transfer("setdown", "Mara", "sill")]}
        if fail == "unaligned":
            return {"results": [_transfer("setdown", "Mara", "table")]}
        if fail:
            raise RuntimeError("test forwarded owner unavailable")
        # Inserting the omitted release changes the initial assumptions of
        # later answers. The owner's suffix must be re-evaluated as a batch.
        return {"results": [_transfer("setdown", "Mara", "table"),
                            _transfer("pickup_again", "table", "Mara"),
                            _transfer("setdown", "Mara", "sill")]}

    first = (_result("stations", {"cup": {"at": "table"}})
             if status == "encoded" else {"status": status, "transforms": [], "settled": {}})
    last = _result("stations", {"cup": {"at": "sill"}})
    for result in (first, last):
        if request in {"required_channels", "both"}:
            result["required_channels"] = ["inventory_ops"]
        if request in {"reroute_to", "both"}:
            result["reroute_to"] = "objects"
    responses = {"director_resolve": {"ledgers": rows},
                 "director_objects": objects,
                 "director_spatial": {"results": [first, last]}}
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, responses))
    initial = _completion_scene()
    ctx = _make_ctx(temp_db, scene=initial, interp={"sequence": []})
    out = director.director_resolve(ctx, 0)
    return initial, ctx, calls, object_calls, out


@pytest.mark.parametrize("request_kind", ["required_channels", "reroute_to", "both"])
def test_partial_completion_keeps_station_and_calls_missing_owner_once(
        temp_db, monkeypatch, request_kind):
    initial, _ctx, calls, object_calls, out = _run_completion_case(
        temp_db, monkeypatch, request=request_kind)

    assert len(object_calls) == 2
    assert len(object_calls[0]["ledgers"]) == 3
    assert len(object_calls[1]["ledgers"]) == 3
    assert "Mara sets the copper cup on the table." in json.dumps(
        object_calls[1]["ledgers"][0]), object_calls[1]["ledgers"][0]
    assert out["orchestration"]["forwards"] == {"objects": [2]}
    assert out["orchestration"]["recompiled_rows"] == {"objects": [2, 3, 4]}

    spatial = next(call["payload"] for call in calls
                   if call["step_key"] == "director_spatial")
    assert set(spatial["ledgers"][0]["assigned_hands"]) == {"spatial"}
    assert set(spatial["ledgers"][1]["assigned_hands"]) == {"spatial", "objects"}
    forwarded = object_calls[1]["ledgers"][0]
    assert set(forwarded["assigned_hands"]) == {"spatial", "objects"}
    # The missing set-down must see the earlier accepted pickup, not merely
    # the original table station and mistake the release for already true.
    for row in object_calls[1]["ledgers"]:
        prior = json.dumps(row.get("prior_work", []))
        assert "pickup_again" not in prior and '"sill"' not in prior
    assert "pickup" in json.dumps(forwarded["prior_work"])
    serialized = json.dumps(object_calls[1]["ledgers"])
    assert all('"' + private + '":' not in serialized
               for private in ("chrono_id", "item_id", "item_ids", "event_id", "from_event"))

    step = next(step for step in out["state_diff"]["causal_steps"]
                if step["chrono_id"] == 2)
    assert step["patch"]["stations"]["cup"]["at"] == "table"
    assert step["patch"]["inventory_ops"][0]["object_id"] == "cup"
    history = [row for row in out["orchestration"]["transform_history"]
               if row["chrono_id"] == 2]
    assert {row["specialist"] for row in history} == {"spatial", "objects"}
    assert {row["item_id"] for row in history} == {7}

    worlds = []
    final = merge_scene_with_diff(initial, out["state_diff"], causal_worlds=worlds)
    released = next(world for world in worlds if world["chrono_id"] == 2)
    assert "cup" in released["before"]["contained"]
    assert "cup" not in released["after"]["contained"]
    repicked = next(world for world in worlds if world["chrono_id"] == 3)
    assert "cup" in repicked["after"]["contained"]
    assert "cup" not in final["contained"]
    assert final["stations"]["cup"]["at"] == "sill"
    # The suffix replaces the prior answers rather than duplicating them.
    assert [entry["chrono_id"] for entry in out["orchestration"]["transform_history"]
            if entry["specialist"] == "objects"] == [1, 2, 3, 4]


def test_inserted_release_replaces_later_already_true_with_a_real_pickup(temp_db, monkeypatch):
    initial, _ctx, _calls, object_calls, out = _run_completion_case(
        temp_db, monkeypatch, stale_pickup=True)
    assert len(object_calls) == 2
    assert len(object_calls[1]["ledgers"]) == 3
    assert out["orchestration"]["forwards"] == {"objects": [2]}
    assert out["orchestration"]["recompiled_rows"] == {"objects": [2, 3, 4]}
    for row in object_calls[1]["ledgers"]:
        prior = json.dumps(row.get("prior_work", []))
        assert '"already_true"' not in prior and '"sill"' not in prior
    history = [entry for entry in out["orchestration"]["transform_history"]
               if entry["specialist"] == "objects"]
    assert [entry["chrono_id"] for entry in history] == [1, 2, 3, 4]
    assert out["orchestration"]["events_addressed"][3]["by_hand"]["objects"]["status"] \
        == "encoded"
    worlds = []
    final = merge_scene_with_diff(initial, out["state_diff"], causal_worlds=worlds)
    by_span = {world["chrono_id"]: world for world in worlds}
    assert "cup" not in by_span[2]["after"]["contained"]
    assert "cup" in by_span[3]["after"]["contained"]
    assert "cup" not in final["contained"]
    assert final["stations"]["cup"]["at"] == "sill"


def test_locally_already_true_can_still_request_missing_transfer_owner(temp_db, monkeypatch):
    _initial, _ctx, _calls, object_calls, out = _run_completion_case(
        temp_db, monkeypatch, status="already_true")
    assert len(object_calls) == 2
    assert out["orchestration"]["forwards"] == {"objects": [2]}
    step = next(step for step in out["state_diff"]["causal_steps"]
                if step["chrono_id"] == 2)
    assert step["patch"]["inventory_ops"][0]["to_id"] == "table"


@pytest.mark.parametrize("failure_mode", ["exception", "unaligned"])
def test_failed_complement_preserves_valid_station_and_reports_unfulfilled_owner(
        temp_db, monkeypatch, failure_mode):
    _initial, ctx, _calls, object_calls, out = _run_completion_case(
        temp_db, monkeypatch, fail=failure_mode)
    assert len(object_calls) == 2
    step = next(step for step in out["state_diff"]["causal_steps"]
                if step["chrono_id"] == 2)
    assert step["patch"]["stations"]["cup"]["at"] == "table"
    assert not step["patch"].get("inventory_ops")
    unfinished = out["orchestration"]["unfulfilled_requests"]
    assert any(row["chrono_id"] == 2 and row["from"] == "spatial"
               and row["to"] == "objects" and row["reason"] for row in unfinished)
    assert "objects" not in out["orchestration"]["events_addressed"][2]["by_hand"]
    assert [entry["chrono_id"] for entry in out["orchestration"]["transform_history"]
            if entry["specialist"] == "objects"] == [1, 3, 4]
    assert any("forward" in warning and "failed" in warning for warning in ctx.warnings)


def _single_span_reply(temp_db, monkeypatch, spatial, *, objects=None):
    calls = []
    row = {"chrono_id": 1, "item_ids": [7], "item_names": ["Copper cup"],
           "source_entity_id": "character:mara", "commitment": "asserted",
           "event": "Mara sets the cup on the table.",
           "resolution_notes": "The cup is now on the table.",
           "categories": ["stations"]}
    responses = {"director_resolve": {"ledgers": [row]},
                 "director_spatial": {"results": [spatial]}}
    if objects is not None:
        responses["director_objects"] = {"results": [objects]}
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, responses))
    ctx = _make_ctx(temp_db, scene=_completion_scene(), interp={"sequence": []})
    return calls, director.director_resolve(ctx, 0)


def test_unknown_required_channel_is_reported_without_guessing_an_owner(temp_db, monkeypatch):
    spatial = _result("stations", {"cup": {"at": "table"}})
    spatial["required_channels"] = ["teleport_cup"]
    calls, out = _single_span_reply(temp_db, monkeypatch, spatial)

    assert [call["step_key"] for call in calls] == ["director_resolve", "director_spatial"]
    assert not out["orchestration"].get("forwards")
    assert out["state_diff"]["stations"]["cup"]["at"] == "table"
    assert out["orchestration"]["unfulfilled_requests"] == [{
        "chrono_id": 1, "from": "spatial", "to": "", "channels": ["teleport_cup"],
        "reason": "no owner for requested channel or hand"}]


def test_second_decline_stays_unfulfilled_without_a_third_model_round(temp_db, monkeypatch):
    spatial = _result("stations", {"cup": {"at": "table"}})
    spatial["required_channels"] = ["inventory_ops"]
    objects = {"status": "not_mine", "transforms": [],
               "settled": {"Copper cup": "not_mine"},
               "required_channels": ["contact_ops"]}
    calls, out = _single_span_reply(temp_db, monkeypatch, spatial, objects=objects)

    assert [call["step_key"] for call in calls] == [
        "director_resolve", "director_spatial", "director_objects"]
    assert out["orchestration"]["forwards"] == {"objects": [1]}
    assert out["state_diff"]["stations"]["cup"]["at"] == "table"
    missing = out["orchestration"]["unfulfilled_requests"]
    assert {(row["chrono_id"], row["from"], row["to"]) for row in missing} == {
        (1, "spatial", "objects"), (1, "objects", "contact")}
    assert all(row["reason"] for row in missing)


def test_forward_rows_sort_across_requesters_and_merge_same_owner_channels():
    # Canonical hand ordering is not fiction chronology. Both hands may also
    # notice the same missing owner; that owner must get one row, not two.
    jobs = [("contact", {"ledger_items": [{"chrono_id": 8}, {"chrono_id": 3}]}),
            ("spatial", {"ledger_items": [{"chrono_id": 1}, {"chrono_id": 3},
                                          {"chrono_id": 4}]})]
    results = {
        "contact": {"results": [
            {"status": "encoded", "required_channels": ["inventory_ops"]},
            {"status": "encoded", "required_channels": ["inventory_ops"]}]},
        "spatial": {"results": [
            {"status": "already_true", "required_channels": ["inventory_ops"]},
            {"status": "encoded", "required_channels": ["entities"],
             "reroute_to": "objects"},
            {"status": "not_mine", "required_channels": ["inventory_ops"]}]},
    }
    dispatch = {"objects": {"run": True, "event_ids": [4]}}
    forwarded = director._rows_to_forward(jobs, results, dispatch)
    assert list(forwarded) == ["objects"]
    rows = forwarded["objects"]
    assert [row["chrono_id"] for row in rows] == [1, 3, 8]
    assert set(rows[1]["channels"]) == {"entities", "inventory_ops"}
    assert rows[1]["full_scope"] is True


def test_forward_widens_existing_owner_only_by_requested_channels(temp_db, monkeypatch):
    calls, object_scopes = [], []
    real_dispatch = director._dispatch_specialists

    def limited_dispatch(*args, **kwargs):
        dispatch = real_dispatch(*args, **kwargs)
        # Reproduce the existing-owner branch with a deliberately narrow first
        # entitlement, as happens when only an entity record was initially due.
        dispatch["objects"]["scope"] = ["entities"]
        return dispatch

    real_prompt = director.specialist_prompt

    def record_prompt(name, scope, *args, **kwargs):
        if name == "objects":
            object_scopes.append(list(scope))
        return real_prompt(name, scope, *args, **kwargs)

    rows = [{"chrono_id": number, "item_ids": [7], "item_names": ["Copper cup"],
             "source_entity_id": "character:mara", "commitment": "asserted",
             "event": event, "resolution_notes": event, "categories": categories}
            for number, event, categories in [
                (1, "The copper cup is dented.", ["entities"]),
                (2, "Mara sets the copper cup on the table.", ["stations"])]]
    object_calls = []

    def objects(payload):
        object_calls.append(deepcopy(payload))
        answer = (_result("entities", {"cup": {"name": "Copper cup", "desc": "Dented."}})
                  if len(object_calls) == 1 else _transfer("setdown", "Mara", "table"))
        return {"results": [answer]}

    spatial = _result("stations", {"cup": {"at": "table"}})
    spatial["required_channels"] = ["inventory_ops"]
    responses = {"director_resolve": {"ledgers": rows}, "director_objects": objects,
                 "director_spatial": {"results": [spatial]}}
    monkeypatch.setattr(director, "_dispatch_specialists", limited_dispatch)
    monkeypatch.setattr(director, "specialist_prompt", record_prompt)
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, responses))
    ctx = _make_ctx(temp_db, scene=_completion_scene(), interp={"sequence": []})
    out = director.director_resolve(ctx, 0)

    assert object_scopes == [["entities"], ["entities", "inventory_ops"]]
    assert object_calls[1]["ledgers"][0]["requested_channels"] == ["inventory_ops"]
    assert out["orchestration"]["forwards"] == {"objects": [2]}
    assert not out["orchestration"].get("unfulfilled_requests")
    assert out["state_diff"]["inventory_ops"][0]["to_id"] == "table"


@pytest.mark.parametrize("complete", [False, True])
def test_multi_item_forward_requires_every_item_without_dropping_valid_work(
        temp_db, monkeypatch, complete):
    calls = []
    initial = _completion_scene()
    initial["entities"]["spoon"] = {
        "name": "Wooden spoon", "kind": "object", "portable": True}
    initial["positions"]["spoon"] = "keeper_room"
    initial = merge_scene_with_diff(initial, {"inventory_ops": [
        {"op": "pickup", "object_id": key, "from_id": "table",
         "to_id": "Mara", "relation": "held"} for key in ("cup", "spoon")]})
    row = {"chrono_id": 1, "item_ids": [7, 8],
           "item_names": ["Copper cup", "Wooden spoon"],
           "source_entity_id": "character:mara", "commitment": "asserted",
           "event": "Mara sets the cup and the spoon on the table.",
           "resolution_notes": "Both objects leave Mara's hands for the table.",
           "categories": ["stations"]}
    spatial = _result("stations", {"cup": {"at": "table"}})
    spatial["transforms"].append({"item": "Wooden spoon", "patch": {
        "stations": {"spoon": {"at": "table"}}}})
    spatial["required_channels"] = ["inventory_ops"]
    objects = _transfer("setdown", "Mara", "table")
    if complete:
        objects["transforms"].append({"item": "Wooden spoon", "patch": {
            "inventory_ops": [{"op": "setdown", "object_id": "spoon",
                               "from_id": "Mara", "to_id": "table"}]}})
    responses = {"director_resolve": {"ledgers": [row]},
                 "director_spatial": {"results": [spatial]},
                 "director_objects": {"results": [objects]}}
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, responses))
    ctx = _make_ctx(temp_db, scene=initial, interp={"sequence": []})
    out = director.director_resolve(ctx, 0)

    assert [call["step_key"] for call in calls] == [
        "director_resolve", "director_spatial", "director_objects"]
    forwarded = calls[-1]["payload"]["ledgers"][0]
    assert forwarded["item_names"] == ["Copper cup", "Wooden spoon"]
    assert forwarded["requested_channels"] == ["inventory_ops"]
    assert out["orchestration"]["forwards"] == {"objects": [1]}

    # An incomplete receipt must never turn into removal of useful work. The
    # cup's transfer and both spatial contributions remain independently valid.
    step = next(step for step in out["state_diff"]["causal_steps"]
                if step["chrono_id"] == 1)
    assert set(step["patch"]["stations"]) == {"cup", "spoon"}
    assert any(op["object_id"] == "cup" and op["to_id"] == "table"
               for op in step["patch"]["inventory_ops"])
    accepted = [entry for entry in out["orchestration"]["transform_history"]
                if entry["specialist"] == "objects"]
    assert {entry["item_id"] for entry in accepted} == ({7, 8} if complete else {7})
    final = merge_scene_with_diff(initial, out["state_diff"])
    assert "cup" not in final["contained"]
    assert ("spoon" not in final["contained"]) is complete

    owner = out["orchestration"]["specialists"]["objects"]
    by_hand = out["orchestration"]["events_addressed"][1]["by_hand"]
    if complete:
        assert not owner.get("things_unaccounted")
        assert by_hand["objects"]["status"] == "encoded"
        assert not out["orchestration"].get("unfulfilled_requests")
    else:
        assert [item["item"] for item in owner["things_unaccounted"]] == ["Wooden spoon"]
        assert "objects" not in by_hand
        assert any(request["chrono_id"] == 1 and request["to"] == "objects"
                   and request["channels"] == ["inventory_ops"] and request["reason"]
                   for request in out["orchestration"]["unfulfilled_requests"])
