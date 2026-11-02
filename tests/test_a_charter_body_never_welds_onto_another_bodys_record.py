"""A charter body overlaid onto the presence ledger never welds onto a record
that is bound to a different body.

`with_charter_presences` folds each derived charter body into the tracked
record answering to its display name. It never asked whether that record was
already PROVEN to be somebody else -- bound to another scene entity, or
carrying another body's charter ref -- the check `_resolve_or_mint_presence`
keeps ("A name match already bound to a DIFFERENT body falls through to the
mint: same name, two bodies, two records"). Measured (review 2026-11-01,
persist_background_memory F3, reproduced): a ledger "Mara" bound to entity
m1 in the hall took the charter's DIFFERENT "Mara" (millers/b17, at the mill)
-- `p_f09aa0e4013525ae m1 [{'charter': 'millers', 'body': 'b17'}]` -- and the
weld persisted, so promoting the hall Mara would hand her b17's memories,
relationships and stress and stand her at the mill.

A name both stores answer to is withheld from the overlay, the rule
`background_presence_records` already keeps when two charter bodies share
one: "Ambiguous display names are withheld until the fiction distinguishes
them."
"""

from __future__ import annotations

import world.charter_runtime as charter_runtime
from persist.commit import with_charter_presences

MILL_MARA = {"dialogue_turns": [], "mention_turns": [], "addressed_turns": [],
             "nature": "person",
             "charter_refs": [{"charter": "millers", "body": "b17"}],
             "sketch": {"role_hint": "miller", "station_room": "mill"}}


def _derive(monkeypatch, records):
    monkeypatch.setattr(
        charter_runtime, "background_presence_records",
        lambda cid, places=None, names=None, frame_id=None:
        {name: dict(rec) for name, rec in records.items()})


def _scene(mara_ref=None):
    mara = {"name": "Mara", "kind": "person"}
    if mara_ref:
        mara["charter_ref"] = mara_ref
    return {"rooms": {"hall": {}, "mill": {}},
            "positions": {"m1": "hall"}, "entities": {"m1": mara}}


def _welded(merged):
    return [key for key, rec in merged.items()
            if rec.get("entity_id") == "m1" and rec.get("charter_refs")]


def test_a_record_bound_to_another_body_is_not_welded(monkeypatch):
    _derive(monkeypatch, {"Mara": MILL_MARA})
    ledger = {"p_hall": {"uid": "p_hall", "name": "Mara", "entity_id": "m1",
                         "first_turn": 2}}
    merged = with_charter_presences(1, ledger, _scene(), names=["Mara"])
    assert _welded(merged) == [], merged
    assert not merged["p_hall"].get("charter_refs")
    assert merged["p_hall"].get("sketch", {}).get("station_room") != "mill"


def test_a_record_carrying_another_bodys_ref_is_not_welded(monkeypatch):
    _derive(monkeypatch, {"Mara": MILL_MARA})
    ledger = {"p_inn": {"uid": "p_inn", "name": "Mara",
                        "charter_refs": [{"charter": "inn", "body": "k2"}]}}
    merged = with_charter_presences(1, ledger, _scene(), names=["Mara"])
    assert merged["p_inn"]["charter_refs"] == [
        {"charter": "inn", "body": "k2"}]


def test_the_rendering_of_this_body_is_still_this_body(monkeypatch):
    """A record bound to the scene entity that IS this charter body (the
    entity carries its `charter_ref`) is the same person and merges."""
    _derive(monkeypatch, {"Mara": MILL_MARA})
    ledger = {"p_hall": {"uid": "p_hall", "name": "Mara", "entity_id": "m1"}}
    merged = with_charter_presences(
        1, ledger, _scene({"charter": "millers", "body": "b17"}),
        names=["Mara"])
    assert merged["p_hall"]["charter_refs"] == [
        {"charter": "millers", "body": "b17"}]


def test_an_unbound_record_is_connected_once_as_before(monkeypatch):
    _derive(monkeypatch, {"Mara": MILL_MARA})
    ledger = {"p_x": {"uid": "p_x", "name": "Mara", "dialogue_turns": [3]}}
    merged = with_charter_presences(1, ledger, _scene(), names=["Mara"])
    assert merged["p_x"]["charter_refs"] == [
        {"charter": "millers", "body": "b17"}]
