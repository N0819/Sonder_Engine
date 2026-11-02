"""A room named in any script resolves as a subject by its name.

world_misc_causal F13 (audit 2026-11-01, CONFIRMED): `subjects` matched
room labels through `normalize_room_id`, which keeps ASCII only and folds
広場, 石段 and 船着き場 all to "" -- so every room spelled by its Japanese
name answered "is not a scene room" (`gaps.gap_for`, the living world's
place resolution, the off-screen subject check). `language_runtime.fold_key`
is the same slug for ASCII and keeps every other script's letters.
"""

from world import subjects


SCENE = {"rooms": {"hiroba": {"name": "広場"}, "ishidan": {"name": "石段"},
                   "back_yard": {"name": "Back Yard"},
                   "cafe": {"name": "Café Noir"}}}


def test_a_room_named_in_kanji_or_kana_resolves_by_its_name():
    for spelling, rid in (("広場", "hiroba"), ("石段", "ishidan"),
                          ("hiroba", "hiroba")):
        found = subjects.resolve_subject(None, SCENE, "room", spelling)
        assert found and found.subject.id == rid, spelling


def test_two_rooms_named_in_another_script_are_two_rooms():
    assert len(subjects._scene_room_matches(SCENE, "広場")) == 1


def test_an_ascii_spelling_matches_exactly_as_before():
    for spelling in ("Back Yard", "back_yard", "BACK-YARD"):
        found = subjects.resolve_subject(None, SCENE, "room", spelling)
        assert found and found.subject.id == "back_yard", spelling
    found = subjects.resolve_subject(None, SCENE, "room", "café noir")
    assert found and found.subject.id == "cafe"


def test_a_registry_row_named_in_kana_resolves(temp_db):
    import time
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("T", "", time.time()))
    temp_db.qi("INSERT INTO room_registry(room_uid,chat_id,name,aliases) "
               "VALUES(?,?,?,?)", ("pier_1", cid, "船着き場", "[]"))
    found = subjects.resolve_subject(cid, {"rooms": {}}, "room", "船着き場")
    assert found and found.subject.id == "pier_1"
