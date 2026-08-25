"""The hand that owns a ledger has to be able to ADDRESS it.

The contact specialist alone owns `substance_ops` and `contact_action_ops`.
Its prompt has always documented closing a record by id -- "Use
{op:'remove',substance_id} when a known record is drained, washed away..." --
and no `substance_id` had ever reached it: the payload carried the contacts
but neither of the specialist's own two ledgers. So the remove op it was told
to use could not be written, which is the measured 38 adds against 5 removes
and zero removes after turn 38 that `docs/design/DESIGN_MATERIAL_MODEL.md` §1
attributes to prompt efficacy.

This widens what the OWNER can address, not what any mind knows: Director
payloads are objective-causality surfaces, no cognition payload changes, and
no other specialist gains the keys -- the same category as `worn_garments`.
"""

from __future__ import annotations

import json

from agents import director
from world.spatial import (
    apply_contact_ops,
    contact_action_ledger_index,
    substance_ledger_index,
)


def _scene():
    return {
        "rooms": {"workshop": {"name": "Workshop", "adjacent": []}},
        "positions": {"Ada": "workshop", "Bex": "workshop"},
        "entities": {"ada": {"name": "Ada", "kind": "person"},
                     "bex": {"name": "Bex", "kind": "person"}},
        "contacts": [],
        "contact_actions": [],
        "substances": [],
        "attire": {},
    }


def _selector():
    return {"actor": "Ada", "actor_part": "hand",
            "target": "Bex", "target_part": "shoulder"}


class TestSubstanceLedgerIndex:
    def test_a_record_saved_without_an_id_is_still_addressable(self):
        """Stamping happens on write; a scene saved before it, or written by
        a restore path, must not be unaddressable forever."""
        scene = _scene()
        scene["substances"] = [{"source": "Ada", "source_part": "hand",
                                "substance": "lamp oil", "target": "Bex",
                                "target_part": "shoulder",
                                "placement": "surface", "amount": "a smear"}]
        [row] = substance_ledger_index(scene)
        assert row["substance_id"].startswith("substance:")
        assert row["substance"] == "lamp oil"
        assert row["target"] == "Bex"

    def test_the_id_matches_the_one_a_removal_would_address(self):
        from world.spatial import apply_substance_ops

        scene = _scene()
        apply_substance_ops(scene, [{
            "op": "add", "source": "Ada", "source_part": "hand",
            "substance": "lamp oil", "target": "Bex",
            "target_part": "shoulder", "placement": "surface"}])
        [stored] = scene["substances"]
        [row] = substance_ledger_index(scene)
        assert row["substance_id"] == stored["substance_id"]

    def test_a_malformed_row_is_not_offered_as_addressable(self):
        scene = _scene()
        scene["substances"] = [{"substance": "lamp oil"}]
        assert substance_ledger_index(scene) == []

    def test_empty_fields_are_left_out_rather_than_sent_blank(self):
        scene = _scene()
        scene["substances"] = [{"source": "Ada", "substance": "lamp oil",
                                "target": "Bex", "placement": "surface"}]
        [row] = substance_ledger_index(scene)
        assert "" not in row.values()


class TestContactActionLedgerIndex:
    def _with_effects(self, *actions):
        from world.spatial import apply_contact_action_ops

        scene = _scene()
        apply_contact_ops(scene, [{"op": "add", **_selector(),
                                   "manner": "rest", "relation": "surface",
                                   "motion": "settled"}])
        for action in actions:
            apply_contact_action_ops(scene, [{
                "op": "add", "actor": "Ada", "contact_ref": _selector(),
                "action": action}])
        return scene

    def test_every_row_carries_the_id_a_change_op_addresses(self):
        scene = self._with_effects("steady pressure")
        [row] = contact_action_ledger_index(scene)
        assert row["action_id"].startswith("contact-action:")
        assert row["actor"] == "Ada"
        assert row["contact_id"] == scene["contacts"][0]["contact_id"]

    def test_a_saved_stack_of_rewordings_is_reported_collapsed(self):
        scene = self._with_effects("steady pressure")
        scene["contact_actions"].append(
            {**scene["contact_actions"][0],
             "action_id": "contact-action:stale",
             "action": "rolling pressure"})
        [row] = contact_action_ledger_index(scene)
        assert row["action"] == "rolling pressure"

    def test_author_diagnostics_are_not_part_of_the_index(self):
        """`detail` is author diagnostics; the index is what the op grammar
        can address, and nothing more."""
        scene = self._with_effects("steady pressure")
        scene["contact_actions"][0]["detail"] = "private note"
        [row] = contact_action_ledger_index(scene)
        assert "detail" not in row


class TestEntitlement:
    """A specialist receives its OWN ledgers, and no other hand's."""

    def _payload(self, name, scene):
        view = {
            "source": "resolved_beat",
            "player": "Ada",
            "cast": ["Bex"],
            "declared_actions": [],
            "dice": {},
            "prose": "Ada steadies the lamp.",
            "dialogue": [],
            "manifest": [],
        }
        return director._specialist_payload(
            name, None, scene, view, {})

    def _loaded_scene(self):
        from world.spatial import apply_contact_action_ops, apply_substance_ops

        scene = _scene()
        apply_contact_ops(scene, [{"op": "add", **_selector(),
                                   "manner": "rest", "relation": "surface",
                                   "motion": "settled"}])
        apply_contact_action_ops(scene, [{
            "op": "add", "actor": "Ada", "contact_ref": _selector(),
            "action": "steady pressure"}])
        apply_substance_ops(scene, [{
            "op": "add", "source": "Ada", "source_part": "hand",
            "substance": "lamp oil", "target": "Bex",
            "target_part": "shoulder", "placement": "surface"}])
        return scene

    def test_the_contact_hand_receives_both_of_its_ledgers(self):
        payload = self._payload("contact", self._loaded_scene())
        assert payload["substances"][0]["substance_id"]
        assert payload["contact_actions"][0]["action_id"]

    def test_the_objects_hand_receives_neither(self):
        payload = self._payload("objects", self._loaded_scene())
        for forbidden in ("substances", "contact_actions"):
            assert forbidden not in payload, forbidden

    def test_the_payload_stays_serialisable(self):
        payload = self._payload("contact", self._loaded_scene())
        assert json.loads(json.dumps(payload))["substances"]
