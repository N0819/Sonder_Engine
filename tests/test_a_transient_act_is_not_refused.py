"""An act whose effect is an event -- a noise, a strike -- happened.

Playerless Aldermill round 5 (2026-09-23): a nod that made a knock (idx 7),
a smith rendered only as sounds (idx 17, 19), and three kicks at one pawl
(idx 14, 16) were un-seen, because their receipts read "no verifier" or "the
contact is gone" as the world refusing them. A strike is kept out of the
standing contacts on purpose, and a noise leaves nothing to verify; neither
is a refusal. A physical channel whose verifier is merely unbuilt still holds
an act back (`test_causal_physical_verification`).
"""
from world.causal_completion import execution_receipt


def _scene():
    return {"rooms": {"smithy": {"name": "Smithy", "anchors": {"anvil": {"kind": "fixture"}}}},
            "positions": {"Kenend": "smithy", "Sal": "smithy"},
            "entities": {"Kenend": {"name": "Kenend", "kind": "person"}},
            "contacts": []}


def test_a_noise_does_not_unsee_the_act():
    receipt = execution_receipt(_scene(), _scene(), {"patch": {
        "sensory_events": [{"kind": "sound", "description": "a dull knock"}]}})
    assert receipt["action_status"] != "unresolved"
    assert receipt["status"] == "pending"


def test_a_strike_does_not_unsee_the_act():
    patch = {"contact_ops": [{"op": "add", "actor": "Kenend", "actor_part": "boot",
                              "target": "anvil", "manner": "strike"}]}
    receipt = execution_receipt(_scene(), _scene(), {"patch": patch})
    assert receipt["action_status"] != "unresolved"


def test_a_standing_contact_that_never_landed_still_does():
    patch = {"contact_ops": [{"op": "add", "actor": "Kenend", "actor_part": "hand",
                              "target": "anvil", "manner": "rest"}]}
    receipt = execution_receipt(_scene(), _scene(), {"patch": patch})
    assert receipt["action_status"] == "unresolved"
