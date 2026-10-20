"""Failed requested effects remain auditable without becoming observed successes."""

import pytest

from agents import director, perception
from tests.test_a_line_is_heard_from_where_it_was_spoken import _beat
from world.beat_ledger import beat_events
from world.causal_completion import execution_receipt
from world.causal_program import program_from_history
from world.causality import compile_transforms


def _program(actor, stage):
    sequence = [
        {"type": "action", "actor": actor, "attempt": "steps onto the broken platform",
         "observable": "steps onto the broken platform", "commitment": "asserted",
         "visibility": "overt", "event_id": "completion:failed", "chrono_id": 1},
        {"type": "speech", "actor": actor, "text": "The platform will have to wait.",
         "volume": "normal", "visibility": "overt", "event_id": "completion:speech", "chrono_id": 2},
        {"type": "action", "actor": actor, "attempt": "raises two fingers",
         "observable": "raises two fingers", "commitment": "asserted",
         "visibility": "overt", "event_id": "completion:gesture", "chrono_id": 3},
    ]
    transforms = [
        {"chrono_id": chrono, "item_id": 1, "specialist": "spatial",
         "patch": {"stations": {actor: {"at": "nonexistent_platform"}}}}
        for chrono in (1, 2)
    ]
    diff, history, rejected = compile_transforms(transforms, allowed_channels=["stations"])
    assert rejected == []
    diff["causal_steps"] = program_from_history(history, sequence, stage)
    return sequence, diff


def test_failed_outcome_act_is_not_delivered_but_speech_gesture_and_audit_survive(temp_db):
    ctx = _beat(temp_db)
    sequence, diff = _program("The Doctor", "resolve")
    ctx["interaction_loop"]["rounds"][0]["result"]["sequence"] = sequence
    ctx.character_results[int(ctx.cast[0]["id"])] = {"sequence": sequence}
    resolved = [{**row, "from_declaration": row["event_id"]} for row in sequence]
    ctx.director_resolve = {
        "ledgers": [{}], "sequence": resolved, "state_diff": diff,
        "resolved_event": "The Doctor steps onto the broken platform and raises two fingers.",
        "dialogue_log": [{"speaker": "The Doctor", "exact_quote": sequence[1]["text"], "volume": "normal"}],
    }
    ctx.director_resolve["beat_events"] = director.beat_event_ledger(
        ctx.director_resolve, ctx.director_interpret,
        [{"name": "The Doctor", "sequence": sequence}])
    out = perception.perception_outcome(ctx, "n0")
    view = out["views"]["player"]
    assert "steps onto the broken platform" not in view
    assert "The platform will have to wait." in view
    assert "raises two fingers" in view
    compiled = ctx["_composed_beat"]
    assert [row["completion"]["status"] for row in compiled.causal_worlds] == [
        "unresolved", "unresolved", "recorded"]
    events = beat_events(compiled.scene, ctx.turn.idx)
    assert len(events) == 3
    assert [row["execution"] for row in events] == ["unresolved", "unresolved", "recorded"]
    assert "steps onto the broken platform" in str(events[0])


def test_a_withheld_outcome_act_leaves_a_decision_row(temp_db):
    """The outcome pass dropped a withheld act with a bare `continue`, so an
    act the world never refused vanished from every view with nothing in the
    pipeline drawer to say where it went (chats 175-177, 2026-10-19: 54 such
    acts). It is said out loud now, as the onset pass says it."""
    from core.pipeline_context import current_decision_sink
    ctx = _beat(temp_db)
    sequence, diff = _program("The Doctor", "resolve")
    ctx["interaction_loop"]["rounds"][0]["result"]["sequence"] = sequence
    ctx.character_results[int(ctx.cast[0]["id"])] = {"sequence": sequence}
    ctx.director_resolve = {
        "ledgers": [{}], "state_diff": diff,
        "sequence": [{**row, "from_declaration": row["event_id"]} for row in sequence],
        "resolved_event": "The Doctor steps onto the broken platform and raises two fingers.",
        "dialogue_log": [{"speaker": "The Doctor", "exact_quote": sequence[1]["text"],
                          "volume": "normal"}],
    }
    decisions = []
    token = current_decision_sink.set(
        lambda kind, subject, verdict, reason: decisions.append(
            (kind, subject, verdict, reason)))
    try:
        out = perception.perception_outcome(ctx, "n0")
    finally:
        current_decision_sink.reset(token)
    assert "steps onto the broken platform" not in out["views"]["player"]
    assert ("act_percept", "The Doctor -> Hinami", "refused",
            "the beat verified this act as unexecuted") in decisions


def test_failed_onset_act_is_not_delivered_but_speech_and_transient_gesture_survive(temp_db):
    ctx = _beat(temp_db)
    sequence, diff = _program("Hinami", "interpret")
    ctx.director_interpret.update(sequence=sequence, state_assertions=diff, ledgers=[{}])
    out = perception.perception_act(ctx, "n0")
    other_views = [view for key, view in out["views"].items() if key != "player"]
    assert other_views
    assert all("steps onto the broken platform" not in view for view in other_views)
    assert any("The platform will have to wait." in view for view in other_views)
    assert any("raises two fingers" in view for view in other_views)


def test_a_sole_failed_action_cannot_return_through_resolved_prose_fallback(temp_db):
    ctx = _beat(temp_db)
    sequence, diff = _program("The Doctor", "resolve")
    sequence = sequence[:1]
    diff["causal_steps"] = diff["causal_steps"][:1]
    ctx["interaction_loop"]["rounds"][0]["result"]["sequence"] = sequence
    ctx.character_results[int(ctx.cast[0]["id"])] = {"sequence": sequence}
    ctx.director_resolve = {
        "ledgers": [{}],
        "sequence": [{**sequence[0], "from_declaration": sequence[0]["event_id"]}],
        "state_diff": diff, "dialogue_log": [],
        "resolved_event": "The Doctor steps onto the broken platform.",
    }
    out = perception.perception_outcome(ctx, "n0")
    assert "steps onto the broken platform" not in out["views"]["player"]
    assert ctx["_composed_beat"].causal_worlds[0]["completion"]["status"] == "unresolved"


def _one_act(temp_db, observable, wanted, specialist):
    """The Doctor's act and his line, the act's span writing `wanted`."""
    ctx = _beat(temp_db)
    sequence, _ = _program("The Doctor", "resolve")
    sequence[0].update(observable=observable, attempt=observable)
    sequence = sequence[:2]
    history = [{"chrono_id": 1, "item_id": 1, "specialist": specialist, "patch": wanted}]
    diff = {**wanted, "causal_steps": program_from_history(history, sequence, "resolve")}
    ctx["interaction_loop"]["rounds"][0]["result"]["sequence"] = sequence
    ctx.character_results[int(ctx.cast[0]["id"])] = {"sequence": sequence}
    ctx.director_resolve = {
        "ledgers": [{}], "sequence": [{**row, "from_declaration": row["event_id"]} for row in sequence],
        "state_diff": diff, "resolved_event": "The Doctor " + observable + ".",
        "dialogue_log": [{"speaker": "The Doctor", "exact_quote": sequence[1]["text"], "volume": "normal"}],
    }
    out = perception.perception_outcome(ctx, "n0")
    return out["views"]["player"], ctx["_composed_beat"].causal_worlds[0]["completion"]


@pytest.mark.parametrize("channel, specialist", [("artifact_ops", "objects"),
                                                 ("public_evidence", "social")])
def test_unverified_work_stays_pending_and_never_un_sees_the_act(temp_db, channel, specialist):
    """NO VERIFIER IS A LIMITATION, never the world refusing the act. Until
    2026-10-20 this test held the opposite for a PHYSICAL channel -- a
    `substance_ops` row nothing could vouch for kept "raises a palm in
    greeting" from the player -- and chats 175-177 lost 54 acts to that rule
    and its siblings (`tests/test_a_done_act_is_seen.py`). The receipt still
    claims nothing: it stays pending."""
    view, completion = _one_act(temp_db, "raises a palm in greeting",
                                {channel: [{"target": "The Doctor", "kind": "greeting"}]},
                                specialist)
    assert "raises a palm in greeting" in view
    assert "The platform will have to wait." in view
    assert completion["status"] == "pending"
    assert completion["action_status"] == "recorded"


@pytest.mark.parametrize("target, seen", [("The Doctor", True), ("a cloak nobody brought", False)])
def test_matter_that_landed_renders_and_matter_with_nowhere_to_go_does_not(temp_db, target, seen):
    """`substance_ops` is verified off the ledger the merge wrote. Matter that
    landed is an act that happened; matter whose destination the world does
    not hold is the world refusing the act, as the Doctor's platform is."""
    view, completion = _one_act(
        temp_db, "shakes the sea water off his hands",
        {"substance_ops": [{"op": "add", "source": "The Doctor", "source_part": "hands",
                            "substance": "sea water", "target": target,
                            "placement": "surface", "target_part": "coat"}]},
        "contact")
    assert ("shakes the sea water off his hands" in view) is seen
    assert "The platform will have to wait." in view
    assert completion["action_status"] == ("applied" if seen else "unresolved")


@pytest.mark.parametrize("requested", [["inventory_ops"], ["not_a_channel"]])
def test_empty_owner_cannot_acquit_itself_with_an_unfulfilled_referral(requested):
    dispatch = {"objects": {
        "run": True, "ran": True,
        "ledger_items": [{"chrono_id": 1, "item_ids": [1], "item_names": ["tin"],
                          "categories": ["inventory_ops"]}],
        "results": [{"status": "not_mine", "transforms": [], "required_channels": requested}],
    }}
    requirements = director._causal_completion_requirements(dispatch, [])
    receipt = execution_receipt({}, {}, {"chrono_id": 1, "transforms": [],
                                        "requirements": requirements})
    assert receipt["status"] == "unresolved"


def test_one_items_valid_effect_cannot_acquit_another_item_without_a_transform():
    history = [{"chrono_id": 1, "item_id": 1, "specialist": "objects",
                "patch": {"entities": {"tin": {"state": {"open": False}}}}}]
    dispatch = {"objects": {
        "run": True, "ran": True,
        "ledger_items": [{"chrono_id": 1, "item_ids": [1, 2], "item_names": ["tin", "cup"],
                          "categories": ["entities"]}],
        "results": [{"status": "encoded", "transforms": []}],
    }}
    requirements = director._causal_completion_requirements(dispatch, history)
    before = {"entities": {"tin": {"name": "tin", "state": {"open": True}},
                            "cup": {"name": "cup", "state": {"broken": False}}}}
    after = {"entities": {"tin": {"name": "tin", "state": {"open": False}},
                           "cup": {"name": "cup", "state": {"broken": False}}}}
    receipt = execution_receipt(before, after, {"chrono_id": 1, "transforms": history,
                                              "requirements": requirements})
    assert receipt["status"] == "unresolved"
    assert any(row.get("item_id") == 2 and row["status"] == "unresolved"
               for row in receipt["effects"])


# ---------------------------------------------------------------------------
# Expression is an action and renders no matter how temporary
# ---------------------------------------------------------------------------

def test_a_thin_ledger_does_not_un_see_an_act(temp_db):
    """EXPRESSION IS AN ACTION THAT RENDERS NO MATTER HOW TEMPORARY (owner
    ruling, 2026-09-16).

    Measured on chat 135 turn 1. The player looked at Mirelle, flushed and
    stiffened her tails; the Director carried it as one action whose
    observable read "looks at Mirelle, flushes, tails stiffen and sway"; and
    the body hand declined every channel, correctly, with "Hinami's flush and
    tail stiffening are brief momentary reactions, not persistent conditions
    or lasting surface marks -- the row's observable action carries them."
    The verifier then filed two `missing_effect` rows, `action_status` went
    `unresolved`, and perception dropped the act from every view. Mirelle
    received two spoken lines and nothing else.

    A `missing_effect` says an assigned hand wrote nothing, which is a fact
    about the LEDGER. Only a requested patch the world does not show is
    evidence the act did not happen, and that case is the Doctor and the
    broken platform above, which still refuses.
    """
    from world.causal_completion import execution_receipt

    step = {
        "chrono_id": 2,
        "requirements": [
            # Assigned to the body hand, no channel demanded of it: there is
            # nothing durable about a blush to demand.
            {"specialist": "body", "item_id": 1, "item": "Hinami",
             "channels": [], "reason": "assigned owner supplied no desired effect"},
        ],
        "transforms": [],
        "patch": {},
    }
    receipt = execution_receipt({}, {}, step)
    # The gap is still in the audit ledger, exactly as it was...
    assert receipt["status"] == "unresolved"
    assert any(e["code"] == "missing_effect" for e in receipt["effects"])
    # ...and the act is still something that happened.
    assert receipt["action_status"] == "recorded"


def test_a_requested_patch_the_world_refuses_still_un_sees_the_act(temp_db):
    """The other half, and it must not move: a patch that WAS requested and
    did not land is an act that did not happen, and stays refused."""
    from world.causal_completion import execution_receipt

    step = {
        "chrono_id": 1, "requirements": [], "patch": {},
        "transforms": [{
            "item_id": 1, "specialist": "spatial", "transform_index": 0,
            "patch": {"stations": {"The Doctor": {"at": "nonexistent_platform"}}},
        }],
    }
    receipt = execution_receipt({"rooms": {}, "positions": {}},
                                {"rooms": {}, "positions": {}}, step)
    codes = {e.get("code") for e in receipt["effects"]}
    assert codes and "missing_effect" not in codes, receipt["effects"]
