"""A body part named in any script is that part, for every rule built on it.

Audit world_spatial_movement_sight F2 (2026-11-01, CONFIRMED WRONG-SCENE,
language pack): `_part_identity` folded with `[^a-z0-9]+`, so
`_part_identity("左手") == ("", "")`, `canonical_region("口") == ""` and
`_same_region("口", "口") is False`; "épaule" folded to "paule". Everything
built on it failed for a Japanese story: a substance add into the very cavity a
standing contact names was discarded, re-asserting `手` on a new spot never
retired the old one (the behaviour the ja contact card promises), and every
contact between the same two bodies shared ONE `contact_id`.
"""

from world.spatial_contacts import (_displaces, _part_identity, _same_region,
                                    canonical_region, contact_id)


def test_a_japanese_part_is_its_own_kind():
    assert _part_identity("左手") == ("左手", "")
    assert canonical_region("口") == "口"
    assert _same_region("口", "口") is True
    assert _same_region("口", "指") is False


def test_an_accented_latin_part_keeps_its_letters():
    assert _part_identity("épaule") == ("épaule", "")
    assert _part_identity("Épaule") == ("épaule", "")


def test_english_is_unchanged():
    assert _part_identity("Left Hand") == ("hand", "left")
    assert _part_identity("left_hand") == ("hand", "left")
    assert _part_identity("hands") == ("hand", "")
    assert canonical_region("Intake_Ports") == "intake port"


def test_two_japanese_contacts_between_the_same_bodies_have_two_ids():
    a = {"actor": "A", "actor_part": "指", "target": "B", "target_part": "口"}
    b = {"actor": "A", "actor_part": "手", "target": "B", "target_part": "肩"}
    assert contact_id(a) and contact_id(b) and contact_id(a) != contact_id(b)


def test_a_japanese_limb_reasserted_elsewhere_displaces_the_old_spot():
    standing = {"actor": "A", "actor_part": "手", "target": "B", "target_part": "肩"}
    moved = {"actor": "A", "actor_part": "手", "target": "B", "target_part": "腰"}
    assert _displaces(standing, moved) is True
    other = {"actor": "A", "actor_part": "尾", "target": "B", "target_part": "腰"}
    assert _displaces(standing, other) is False
