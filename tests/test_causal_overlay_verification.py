"""Surface marks receive proof from the world at their own causal span."""

from copy import deepcopy

import pytest

from persist.commit import _merge_overlays
from world.causal_completion import execution_receipt
from world.causal_verification import verify_causal_worlds, verify_patch


def _scene():
    return {"rooms": {"workshop": {"name": "Workshop"}},
            "positions": {"Sera": "workshop", "Tomas": "workshop"},
            "overlays": {"Sera": ["paint on left hand"], "Tomas": []}}


def _apply(before, patch):
    after = deepcopy(before)
    _merge_overlays(after, deepcopy(patch["overlays"]))
    return after


def _statuses(before, after, patch):
    return [row["status"] for row in verify_patch(before, after, patch)]


def test_added_marks_require_the_actual_requested_details_on_each_body():
    before = _scene()
    patch = {"overlays": {
        "Sera": [{"name": "soot", "description": "soot on right cheek"}],
        "Tomas": ["wet hair", "mud on boots"],
    }}
    after = _apply(before, patch)
    saved = deepcopy((before, after, patch))
    assert _statuses(before, after, patch) == ["applied", "applied", "applied"]
    assert after["overlays"]["Sera"][0] == "paint on left hand"
    assert (before, after, patch) == saved
    after["overlays"]["Sera"][-1]["description"] = "soot on left cheek"
    after["overlays"]["Tomas"].remove("wet hair")
    assert _statuses(before, after, patch) == ["unresolved", "unresolved", "applied"]


@pytest.mark.parametrize("ending", [
    {"name": "soot", "active": False},
    {"text": "SOOT ON RIGHT CHEEK", "active": False},
    {"desc": "soot", "present": False},
    {"description": "soot", "ended": True},
    {"name": "soot", "removed": True},
])
def test_endings_use_exact_mark_handles_and_preserve_other_marks(ending):
    before = _scene()
    before["overlays"]["Sera"] += [
        {"name": "soot", "description": "soot on right cheek", "subject": "Sera"},
        {"name": "soot on boots", "subject": "Sera"},
    ]
    before["overlays"]["Tomas"] = ["soot"]
    patch = {"overlays": {"Sera": [ending]}}
    assert _statuses(before, before, patch) == ["unresolved"]
    after = _apply(before, patch)
    assert _statuses(before, after, patch) == ["applied"]
    assert after["overlays"]["Sera"] == [
        "paint on left hand", {"name": "soot on boots", "subject": "Sera"}]
    assert after["overlays"]["Tomas"] == ["soot"]


def test_already_present_or_already_absent_effect_is_checked_without_a_model_verdict():
    before = _scene()
    before["overlays"]["Sera"].append({"name": "Soot", "description": "Black cheek"})
    patch = {"overlays": {"Sera": [
        " soot ", {"name": "Soot"}, {"name": "wet hair", "active": False}]}}
    assert _statuses(before, before, patch) == ["unchanged", "unchanged", "unchanged"]


@pytest.mark.parametrize("changes", [
    {}, {"Sera": []}, {"Sera": [""]}, {"Sera": [{}]},
    {"Sera": [{"active": False}]}, {"Sera": [{"id": "Sera", "active": False}]},
    {"Sera": [{"subject": "Sera", "active": False}]},
    {"Sera": [{"from_event": "soot", "active": False}]},
    {"Missing body": ["soot"]},
])
def test_empty_or_unidentifiable_effects_do_not_certify_completion(changes):
    before = _scene()
    patch = {"overlays": changes}
    assert _statuses(before, _apply(before, patch), patch) == ["unresolved"]


def test_ending_an_unrecognised_stored_shape_does_not_claim_the_mark_is_gone():
    before = _scene()
    before["overlays"]["Sera"].append({"text": "soot"})
    patch = {"overlays": {"Sera": [{"text": "soot", "active": False}]}}
    after = _apply(before, patch)
    assert {"text": "soot"} in after["overlays"]["Sera"]
    assert _statuses(before, after, patch) == ["unresolved"]


def test_add_then_remove_is_verified_at_each_span_and_allows_action_delivery():
    before = _scene()
    patches = [
        {"overlays": {"Sera": [{"name": "soot", "active": True}]}},
        {"overlays": {"Sera": [{"name": "soot", "active": False}]}},
    ]
    worlds = []
    for chrono, patch in enumerate(patches, 1):
        after = _apply(before, patch)
        span = {"stage": "resolve", "chrono_id": chrono, "item_id": 7,
                "specialist": "body", "patch": patch,
                "before": before, "after": after}
        completion = execution_receipt(before, after, span)
        assert completion["status"] == completion["action_status"] == "applied"
        worlds.append(span)
        before = after
    receipts = verify_causal_worlds(worlds)
    assert [row["status"] for row in receipts] == ["applied", "applied"]
    assert [row["chrono_id"] for row in receipts] == [1, 2]
    assert all(row["item_id"] == 7 and row["specialist"] == "body" for row in receipts)
    assert before["overlays"]["Sera"] == ["paint on left hand"]


@pytest.mark.parametrize("chronological", [False, True])
def test_onset_preview_applies_surface_changes_once_to_a_scene_copy(chronological, monkeypatch):
    from agents.common import preview_player_state_assertions
    from persist import commit
    from world.causal_program import program_from_history
    from world.causality import compile_transforms

    before = _scene()
    patches = [{"overlays": {"Sera": [{"name": "blue dot", "active": active}]}}
               for active in (True, False)]
    history = [{"chrono_id": i, "item_id": 1, "specialist": "body", "patch": patch}
               for i, patch in enumerate(patches, 1)]
    diff, history, rejected = compile_transforms(history, allowed_channels=["overlays"])
    assert not rejected
    if chronological:
        diff["causal_steps"] = program_from_history(history, [], "interpret")
    else:
        diff = patches[0]
    saved = deepcopy((before, diff))
    applications = []
    merge = commit._merge_overlays

    def record_apply(world, incoming):
        applications.append(deepcopy(incoming))
        merge(world, incoming)

    monkeypatch.setattr(commit, "_merge_overlays", record_apply)
    worlds = []
    preview = preview_player_state_assertions(before, diff, causal_worlds=worlds)
    assert (before, diff) == saved
    if chronological:
        assert applications == [step["patch"]["overlays"] for step in diff["causal_steps"]]
        assert worlds[0]["after"]["overlays"]["Sera"][-1]["name"] == "blue dot"
        assert worlds[1]["before"]["overlays"]["Sera"][-1]["name"] == "blue dot"
        assert preview["overlays"]["Sera"] == ["paint on left hand"]
        assert [world["completion"]["action_status"] for world in worlds] == ["applied", "applied"]
    else:
        assert applications == [patches[0]["overlays"]]
        assert preview["overlays"]["Sera"][-1]["name"] == "blue dot"


def test_onset_perception_delivers_both_surface_addition_and_removal(temp_db):
    from agents import perception
    from tests.test_a_line_is_heard_from_where_it_was_spoken import _beat
    from world.causal_program import program_from_history
    from world.causality import compile_transforms

    ctx = _beat(temp_db)
    actions = ["dabs a blue dot onto her left cheek", "wipes the blue dot from her left cheek"]
    sequence = [{"type": "action", "actor": "Hinami", "attempt": action,
                 "observable": action, "commitment": "asserted", "visibility": "overt",
                 "event_id": f"surface:{i}", "chrono_id": i}
                for i, action in enumerate(actions, 1)]
    transforms = [{"chrono_id": i, "item_id": 1, "specialist": "body", "patch": {
        "overlays": {"Hinami": [{"name": "blue dot on left cheek", "active": active}]}}}
        for i, active in enumerate((True, False), 1)]
    diff, history, rejected = compile_transforms(transforms, allowed_channels=["overlays"])
    assert not rejected
    diff["causal_steps"] = program_from_history(history, sequence, "interpret")
    ctx.director_interpret.update(sequence=sequence, state_assertions=diff, ledgers=[{}])
    out = perception.perception_act(ctx, "n0")
    others = [view for key, view in out["views"].items() if key != "player"]
    assert others
    assert any(all(action in view for action in actions) for view in others)
