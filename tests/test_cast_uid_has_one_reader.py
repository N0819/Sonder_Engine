"""One rule for a card's authored uid (Section H residual, review B12).

`cast_entity_id` -- the id every scene entity, subject and offscreen payload
keys a cast member by -- read `sheet["identity"]["uid"]` alone.
`character_identity` read the identity block AND then the top level, because
`repair_character_shape` rescues a flattened card's `uid` exactly as it
rescues its name. So a card that wrote its uid at top level was
`char_<authored>` to one reader and `character:<row id>` to the other, in the
two payloads that name the same person to the same beat.

`authored_uid` is now the one rule both read it by.
"""

from story.character_schema import (
    authored_uid, cast_entity_id, character_identity,
    normalize_character_data,
)


_FLAT = {"uid": "char_deadbeef", "name": "Kit"}
_BLOCKED = {"identity": {"uid": "char_beef", "name": "Kit"}}
_UNAUTHORED = {"identity": {"name": "Kit"}}


def test_a_flattened_card_gives_both_readers_the_same_answer():
    assert authored_uid(_FLAT) == "char_deadbeef"
    assert cast_entity_id(_FLAT, 7) == "char_deadbeef"
    assert character_identity(_FLAT)["uid"] == "char_deadbeef"


def test_the_identity_block_still_wins_where_a_card_wrote_one():
    assert cast_entity_id(_BLOCKED, 7) == "char_beef"
    assert character_identity(_BLOCKED)["uid"] == "char_beef"


def test_a_card_with_no_uid_anywhere_gets_the_stable_row_fallback():
    assert authored_uid(_UNAUTHORED) == ""
    assert character_identity(_UNAUTHORED)["uid"] == ""
    assert cast_entity_id(_UNAUTHORED, 7) == "character:7"
    # And the fallback is stable across calls, which is the whole point --
    # normalization would mint a fresh `char_<hex>` each time.
    assert cast_entity_id(_UNAUTHORED, 7) == cast_entity_id(_UNAUTHORED, 7)
    minted = {normalize_character_data(_UNAUTHORED)["identity"]["uid"]
              for _ in range(3)}
    assert len(minted) == 3


def test_junk_is_not_a_uid():
    assert authored_uid(None) == ""
    assert authored_uid({"identity": "Kit"}) == ""
    assert cast_entity_id({"identity": []}, 3) == "character:3"
