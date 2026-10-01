"""A new body never takes a cast member's identity (2026-09-30).

The concept lab's story: with the doctor in a causality bubble, a knock at
her clinic was answered in the Director's prose by "a woman somewhere past
fifty with steel-grey hair", which the encoder filed as entity `ines_calder`
aliased "the doctor". The bubble merged at commit, the world held both, and
38 turns later the phantom answered a line in the doctor's place.
"""

import json

from agents.director import _refuse_minted_cast_doubles

INES = {"sheet": json.dumps({"identity": {"name": "Ines Calder", "uid": "ines-uid", "aliases": ["Dr. Calder"]}})}


def _diff(eid, name, aliases=()):
    return {"entities": {eid: {"name": name, "kind": "person", "aliases": list(aliases)}},
            "positions": {eid: "clinic", name: "clinic"}, "stations": {eid: {"at": "door"}}}


def test_a_stranger_filed_under_a_cast_members_id_is_refused():
    sd = _diff("ines_calder", "a woman with steel-grey hair", ["the doctor"])
    got = _refuse_minted_cast_doubles({}, sd, [INES], here_names=["Ines Calder"])
    assert got == [{"entity_id": "ines_calder", "name": "a woman with steel-grey hair", "cast": "Ines Calder"}]
    assert sd["entities"] == {} and sd["positions"] == {} and sd["stations"] == {}


def test_a_body_for_a_member_another_frame_holds_is_refused_even_under_her_name():
    sd = _diff("char_ines_calder", "Ines Calder")
    assert _refuse_minted_cast_doubles({}, sd, [INES], here_names=[])[0]["cast"] == "Ines Calder"
    assert sd["entities"] == {}


def test_the_engines_own_record_of_a_member_standing_here_is_kept():
    sd = _diff("char_ines_calder", "Ines Calder")
    assert _refuse_minted_cast_doubles({}, sd, [INES], here_names=["Ines Calder"]) == []
    assert "char_ines_calder" in sd["entities"]


def test_an_unrelated_mint_and_a_record_the_scene_holds_are_untouched():
    sd = _diff("the_postman", "the postman")
    assert _refuse_minted_cast_doubles({}, sd, [INES], here_names=[]) == []
    held = _diff("ines_calder", "a woman with steel-grey hair")
    assert _refuse_minted_cast_doubles({"entities": {"ines_calder": {}}}, held, [INES], here_names=[]) == []
    thing = {"entities": {"ines_calder_bag": {"name": "Ines Calder's bag", "kind": "item"}}}
    assert _refuse_minted_cast_doubles({}, thing, [INES], here_names=[]) == []
