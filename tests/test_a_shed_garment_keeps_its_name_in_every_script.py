"""A garment taken off becomes a thing in the room, whatever script it is
named in, and two owners never share one floor object.

The floor object's key was `<garment>_<owner>` folded through the ASCII class
`[^a-z0-9]+`. In a Japanese story that class folds 上着 to "", so no floor
object was minted -- and `release_removed_garments` then deleted the removed
seat ("AFTER the mint, never before ... the seat is a duplicate"), so the
garment left the world entirely: the failure `_mint_shed_garments` exists to
prevent. With an ASCII garment and kana owners every owner folded to "" and
the keys collided: the second body's jacket was stamped onto the first
body's object.

Measured (review 2026-11-01, persist_scene_entities F2):
    'Hinami' 'jacket' -> ['jacket_hinami']
    'ヒナミ' '上着'   -> []
    two owners       -> {'jacket_': 'ヒナミ'}

Three sites spell this key and must agree: the mint
(`commit_attire._mint_shed_garments`), the placeholder test that lets the
ledger's spelling replace an id-shaped name (`commit_attire._stamp_shed`), and
the reservation the transfer mint yields to (`spatial_containment.
mint_transferred_objects`).
"""

from __future__ import annotations

from persist.commit import _mint_shed_garments, _stamp_shed
from world.spatial import mint_transferred_objects


def _clothes(sc):
    return {eid: ent for eid, ent in (sc.get("entities") or {}).items()
            if (ent.get("state") or {}).get("shed")}


def test_a_garment_named_in_kanji_is_minted_where_its_wearer_stands():
    sc = {"positions": {"ヒナミ": "居間"}}
    diff = {}
    _mint_shed_garments(sc, [("ヒナミ", "上着", "")], diff)
    shed = _clothes(sc)
    assert len(shed) == 1, sc.get("entities")
    key, ent = next(iter(shed.items()))
    assert ent["name"] == "上着"
    assert ent["state"]["worn_by"] == "ヒナミ"
    assert sc["positions"][key] == "居間"
    assert diff["entities"][key] is sc["entities"][key]


def test_two_kana_owners_shedding_one_kind_of_garment_get_two_objects():
    sc = {"positions": {"ヒナミ": "居間", "サクラ": "居間"}}
    _mint_shed_garments(sc, [("ヒナミ", "jacket", ""),
                             ("サクラ", "jacket", "")], {})
    shed = _clothes(sc)
    assert len(shed) == 2, sorted(shed)
    assert {ent["state"]["worn_by"] for ent in shed.values()} == {
        "ヒナミ", "サクラ"}


def test_owners_with_no_letter_at_all_stay_apart():
    sc = {"positions": {"★": "deck", "☆": "deck"}}
    _mint_shed_garments(sc, [("★", "cloak", ""), ("☆", "cloak", "")], {})
    assert len(_clothes(sc)) == 2


def test_an_ascii_key_is_spelled_exactly_as_before():
    """Every id already minted keeps matching its own spelling."""
    sc = {"positions": {"Hinami": "room_a"}}
    _mint_shed_garments(sc, [("Hinami", "Lightweight travel jacket", "")], {})
    assert list(_clothes(sc)) == ["lightweight_travel_jacket_hinami"]


def test_a_placeholder_name_in_kana_is_replaced_by_the_ledgers_spelling():
    """`_stamp_shed` replaces a name that is only the record's own id. The
    id is the folded key, so a kana placeholder has to fold the same way or
    it is read as a name the model chose and kept."""
    ent = {"name": "上着 ヒナミ"}
    _stamp_shed(ent, "上着", "ヒナミ", "", eid="上着_ヒナミ")
    assert ent["name"] == "上着"


def test_the_transfer_mint_yields_the_attire_seams_key_in_every_script():
    """`mint_transferred_objects` reserves `<garment>` and `<garment>_<owner>`
    for the attire seam, which alone knows it is clothing. The reservation
    has to spell the key the seam mints."""
    sc = {"positions": {"ヒナミ": "居間"}, "entities": {}}
    minted = mint_transferred_objects(
        sc, [{"op": "move", "object_id": "上着_ヒナミ", "relation": "shed"}],
        shedding=("上着",))
    assert minted == []
