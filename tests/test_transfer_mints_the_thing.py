"""A transfer is evidence that a thing exists.

`derive_inventory_placements` skips any op naming something the scene has no
entity for -- correct for PLACEMENT, since a thing with no record has nowhere
to be put, and fatal for the POSSESSION, which went down with it. The hand
that resolves a handover owns `inventory_ops` and cannot write `entities`;
the hand that mints entities was never asked. Measured across 26 beats in 7
chats, and in the run that surfaced it a padd handed to a captain on turn 4
was resolved perfectly, recorded nowhere, and back in the giver's hands in
the prose four turns later because nothing had ever contradicted her holding
it.
"""
from __future__ import annotations

from world.spatial import mint_transferred_objects


def _scene(**kw):
    base = {"positions": {"Sabine": "bridge", "Picard": "bridge"},
            "entities": {}, "attire": {}, "rooms": {"bridge": {}}}
    base.update(kw)
    return base


def _transfer(obj, frm="Sabine", to="Picard"):
    return {"op": "transfer", "object_id": obj, "from_id": frm,
            "to_id": to, "relation": "held"}


def test_a_handed_over_thing_the_scene_never_minted_gets_a_record():
    sc = _scene()
    minted = mint_transferred_objects(sc, [_transfer("padd")])
    assert minted == ["padd"]
    assert sc["entities"]["padd"]["name"] == "padd"
    assert sc["entities"]["padd"]["kind"] == "object"
    # It was just carried, which is the one property the op vouches for.
    assert sc["entities"]["padd"]["portable"] is True


def test_a_thing_the_scene_already_knows_is_left_alone():
    sc = _scene(entities={"padd": {"name": "padd", "kind": "object",
                                   "description": "a scuffed padd"}})
    assert mint_transferred_objects(sc, [_transfer("padd")]) == []
    assert sc["entities"]["padd"]["description"] == "a scuffed padd"


def test_an_alias_counts_as_already_known():
    sc = _scene(entities={"padd_001": {"name": "padd_001",
                                       "aliases": ["padd"]}})
    assert mint_transferred_objects(sc, [_transfer("padd")]) == []
    assert list(sc["entities"]) == ["padd_001"]


def test_a_body_is_never_minted_over():
    """`_merge_entity`'s own docstring records the corruption this refuses:
    a registered character became 'an object named The Doctor'. A subject the
    scene stands somewhere is not a thing a transfer may invent."""
    sc = _scene()
    assert mint_transferred_objects(sc, [_transfer("Picard", frm="Sabine")]) == []
    assert mint_transferred_objects(
        sc, [{"op": "transfer", "object_id": "Sabine",
              "from_id": "Picard", "to_id": "Worf"}]) == []
    assert sc["entities"] == {}


def test_a_dressed_body_with_no_position_is_still_not_a_thing():
    sc = _scene(positions={}, attire={"Sabine": {"wearing": ["combadge"]}})
    assert mint_transferred_objects(sc, [_transfer("Sabine")]) == []
    assert sc["entities"] == {}


def test_the_spelling_is_folded_and_kept_as_an_alias():
    sc = _scene()
    mint_transferred_objects(sc, [_transfer("Dress Uniform Jacket")])
    key = next(iter(sc["entities"]))
    assert key == "dress_uniform_jacket"
    assert sc["entities"][key]["name"] == "Dress Uniform Jacket"
    assert "Dress Uniform Jacket" in sc["entities"][key]["aliases"]


def test_nothing_to_transfer_mints_nothing():
    sc = _scene()
    assert mint_transferred_objects(sc, []) == []
    assert mint_transferred_objects(sc, None) == []
    assert mint_transferred_objects(sc, [{"op": "transfer"}]) == []
    assert sc["entities"] == {}
