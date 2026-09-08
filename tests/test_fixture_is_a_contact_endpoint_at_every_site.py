"""A room's own fixture is a contact endpoint at EVERY site, not at one.

`spatial_contacts.normalize_scene_contacts` has said since the caravanserai
run that a counter, a doorway or a rail -- an ANCHOR of its room, with no
position of its own -- is where its room is, and resolves an unplaced
contact endpoint through the room that declares it. Two sibling sites kept
the narrower test and failed in the same beats, measured on the descent copy
(chat 117, beats 115-117, a player at a steel access door the landing
declared as an anchor and both bodies stood STATIONED at):

  * `director_contact._validated_player_contact_assertions` compared bare
    `room_of` answers, so the player's palm on the door plate (115) and
    shoulder against the leaf (117) were "discarded ... between
    non-co-located bodies" and reached the ledger only through the resolve
    manifest, a stage late;
  * `composer._pose_referent` dropped the anchor id as engine plumbing before
    asking whether a room declared it, so the sensation the ledger did carry
    was delivered as "You feel something's steel plate against your right
    palm" and "something's lever handle".

One resolver, asked at all three sites.
"""

from __future__ import annotations

from agents import composer
from agents.director import _validated_player_contact_assertions


def _landing():
    return {
        "rooms": {
            "landing": {
                "name": "Sub-Level Three Landing", "desc": "", "adjacent": [],
                "anchors": {
                    "access_door": {
                        "desc": "A heavy steel access door seated in a "
                                "reinforced frame.", "dir": "n"},
                    "stair_head": {"desc": "The head of the stairwell.",
                                   "dir": "s"},
                },
            },
            "spine": {"name": "Service Spine", "desc": "", "adjacent": [],
                      "anchors": {"bulkhead": {"desc": "A bulkhead door."}}},
        },
        "positions": {"Aurel Voss": "landing", "Sarah Moon": "landing"},
        "stations": {"Aurel Voss": {"at": "access_door", "near": []}},
        "entities": {},
        "contacts": [],
    }


def _palm_on(target, actor="Aurel Voss"):
    return {"actor": actor, "actor_part": "right palm", "target": target,
            "target_part": "steel plate", "manner": "press",
            "relation": "surface"}


class TestPlayerAssertionAgainstAFixture:
    def test_a_players_hand_on_the_rooms_own_door_is_kept(self):
        reports = []
        kept = _validated_player_contact_assertions(
            _landing(), [_palm_on("access_door")], "Aurel Voss", reports.append)
        assert [c["target"] for c in kept] == ["access_door"]
        assert reports == []

    def test_a_fixture_of_another_room_is_still_out_of_reach(self):
        reports = []
        kept = _validated_player_contact_assertions(
            _landing(), [_palm_on("bulkhead")], "Aurel Voss", reports.append)
        assert kept == []
        assert reports == [
            "discarded a contact assertion between non-co-located bodies"]

    def test_a_name_no_room_declares_is_still_unplaced(self):
        reports = []
        kept = _validated_player_contact_assertions(
            _landing(), [_palm_on("the void")], "Aurel Voss", reports.append)
        assert kept == []
        assert len(reports) == 1


class TestTheReferentLadderNamesAFixture:
    def test_a_fixture_renders_as_the_noun_its_id_was_minted_from(self):
        label = composer._pose_referent(
            _landing(), "Aurel Voss", {}, [], "access_door", is_self=True)
        assert label == "the access door"

    def test_an_id_no_record_claims_is_still_dropped(self):
        assert composer._pose_referent(
            _landing(), "Aurel Voss", {}, [], "scranton_anchor",
            is_self=True) is None

    def test_a_fixtures_part_is_possessed_by_the_fixture(self):
        sc = _landing()
        sc["contacts"] = [{
            "actor": "Aurel Voss", "actor_part": "right hand",
            "target": "access_door", "target_part": "lever handle",
            "manner": "grip", "relation": "surface", "motion": "settled"}]
        from agents import perception
        label_for = (lambda other: composer._pose_referent(
            sc, "Aurel Voss", {}, [], other, is_self=True) or "something")
        text = perception.contact_sensation(
            sc["contacts"][0], you="Aurel Voss", scene=sc, label_for=label_for)
        assert "something" not in text
        assert "access door" in text


def test_both_packs_hand_the_world_a_players_reading_aloud():
    """The player's read-aloud line is the ONE player line the author fills:
    the words are the world's fact, not the player's authorship. Beat 115
    on the descent copy: the player 'read the stencil out loud', the
    interpret carried the act, and the sheet's absolute rule against
    authoring a player line left the number unspoken for a beat."""
    import pathlib
    for pack, marker in (("en", "READ, RECITE or REPEAT ALOUD"),
                         ("ja", "読み上げる")):
        text = pathlib.Path(
            "language_packs", pack, "cards", "system_prompts",
            "prose_author_sheet", "06.txt").read_text(encoding="utf-8")
        assert marker in text, pack
