"""Regression tests for the destruction reconciliation tripwire.

Observed live (chat 26, the Emberhold razing): director_resolve's
resolved_event narrated a whole-town firestorm consuming a named region
and its wards, but state_diff.destruction was null and remove_rooms empty
-- so the Phase-3b cascade (which only realizes a DECLARED destruction)
never fired and the town stayed objectively intact against the prose,
with no warning anywhere.

_narrated_destruction_subjects is the deterministic, warn-only safety net:
it flags a named, KNOWN place (scene room, scene location, interior-
bearing entity, live lorebook name) appearing in a destruction-shaped
grammatical position in the prose while the diff encodes neither
destruction nor a covering removal. It must NOT fire on ordinary fire/
damage flavor or on an object being destroyed IN a room, and it never
mutates the diff -- warnings only (a wrongly-invented razing would be far
worse than a stale-missing one).

The end-to-end tests through `director_resolve` were deleted on 2026-09-27:
the scan runs inside `_reconcile_resolution`, which a beat with rows never
reaches -- every prose beat (UNBUILT_PIPELINE §1.1, the reconciliation gate).
The detector below is still the engine's; its caller is what is gated.
"""

import agents.director as director


def _scene():
    return {
        "location": "Emberhold",
        "time": "night",
        "rooms": {
            "market_ward": {"name": "Market Ward", "adjacent": []},
            "temple_ward": {"name": "Temple Ward", "adjacent": []},
            "harbor_row": {"name": "Harbor Row", "adjacent": []},
        },
        "positions": {"The Stranger": "market_ward"},
        "entities": {
            "elevator": {
                "name": "the elevator", "kind": "vehicle", "aliases": [],
                "interior_rooms": ["elevator_interior"], "state": {},
            },
        },
        "attire": {},
        "overlays": {},
    }


def _empty_sd(**over):
    sd = {"positions": {}, "rooms": {}, "entities": {}, "conditions": {},
          "attire": {}, "overlays": {}, "remove_rooms": [],
          "remove_entities": [], "remove_adjacent": [], "inventory_ops": [],
          "cast_changes": [], "introductions": [],
          "claim_dispositions": [], "time": None, "destruction": None}
    sd.update(over)
    return sd


# ---- unit level: the detector itself -------------------------------------

def test_flags_named_region_and_ward_destruction():
    prose = ("The firestorm consumed Emberhold ward by ward. By dawn the "
             "Market Ward was razed to its foundations.")
    flagged = director._narrated_destruction_subjects(
        prose, [], _empty_sd(), _scene())
    assert "Emberhold" in flagged
    assert "Market Ward" in flagged


def test_no_false_positive_on_ordinary_fire_flavor():
    prose = ("The fire spread along the rooftops of the Market Ward as "
             "sparks drifted over Harbor Row. Smoke filled Emberhold's "
             "narrow streets.")
    assert director._narrated_destruction_subjects(
        prose, [], _empty_sd(), _scene()) == []


def test_no_false_positive_on_object_destroyed_inside_a_room():
    prose = "The ledger was destroyed in the Market Ward before anyone read it."
    assert director._narrated_destruction_subjects(
        prose, [], _empty_sd(), _scene()) == []


def test_declared_destruction_suppresses_the_scan():
    prose = "The firestorm consumed Emberhold ward by ward."
    sd = _empty_sd(destruction={"target_id": "emberhold", "scale": "region",
                                "kind": "fire", "news": []})
    assert director._narrated_destruction_subjects(prose, [], sd, _scene()) == []


def test_remove_rooms_covers_a_single_razed_room():
    prose = "The Market Ward was razed; the rest of the town stood untouched."
    sd = _empty_sd(remove_rooms=["market_ward"])
    assert director._narrated_destruction_subjects(prose, [], sd, _scene()) == []


def test_entity_destruction_flagged_and_covered_by_remove_entities():
    prose = "The rockslide flattened the elevator against the shaft wall."
    assert "the elevator" in director._narrated_destruction_subjects(
        prose, [], _empty_sd(), _scene())
    sd = _empty_sd(remove_entities=["elevator"])
    assert director._narrated_destruction_subjects(prose, [], sd, _scene()) == []


def test_lorebook_names_are_matched_via_extra_names():
    prose = "Nothing was left of the Ashen Quarter when the flames died."
    flagged = director._narrated_destruction_subjects(
        prose, [], _empty_sd(), _scene(), extra_names=["Ashen Quarter"])
    assert flagged == ["Ashen Quarter"]
