"""A plan that names its structure by key keeps what the structure already
holds (`story/plot_packages._structure_as_held`).

The Room's `plan_rooms` names its structure as `{key, name}` -- all the
field text asks for -- and `world.structure.plant_structure` writes the
structure it is handed over the stored record. Probed 2026-10-08: a plan
into a structure holding a charter and a grammar row left both empty and
validated clean, so every room the Room planted ahead into a laid-out town
erased the grammar its frontier stubs are named from. Planting ahead is the
Room's standing work since the owner's ruling the same day.
"""
from __future__ import annotations

import time

from core.db import wget_for_frame


def test_a_plan_naming_its_structure_by_key_keeps_its_grammar_and_charters(temp_db):
    from story import plot_packages as pp
    from world.structure import STRUCTURES_KEY, normalize_structures, plant_structure
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Town", "A town.", time.time()))
    grammar = [{"kind": "street", "names": ["Lane"], "purposes": ["a lane"]}]
    plant_structure(cid, {"key": "town", "name": "Town", "charters": ["guild"],
                          "grammar": grammar}, {"a": {"name": "A"}})
    pkg = pp.new_package(cid, title="Ahead")
    pp.draft_operation(cid, pkg["uid"], {
        "op": "plan_rooms", "structure": {"key": "town", "name": "Town"},
        "rooms": {"b": {"name": "B", "adjacent": [{"to": "a"}]}}})
    verdict = pp.validate_package(cid, pkg["uid"])
    assert verdict["ok"], verdict
    pp.publish_package(cid, pkg["uid"], expected_revision=verdict["at_revision"])
    held = normalize_structures(
        wget_for_frame(cid, STRUCTURES_KEY, None, {}))["items"]["town"]
    assert held["charters"] == ["guild"]
    assert held["grammar"] == grammar
    # What a plan does state still wins.
    pkg = pp.new_package(cid, title="Renamed")
    pp.draft_operation(cid, pkg["uid"], {
        "op": "plan_rooms", "structure": {"key": "town", "name": "Old Town"},
        "rooms": {"c": {"name": "C", "adjacent": [{"to": "a"}]}}})
    verdict = pp.validate_package(cid, pkg["uid"])
    pp.publish_package(cid, pkg["uid"], expected_revision=verdict["at_revision"])
    held = normalize_structures(
        wget_for_frame(cid, STRUCTURES_KEY, None, {}))["items"]["town"]
    assert held["name"] == "Old Town" and held["grammar"] == grammar
