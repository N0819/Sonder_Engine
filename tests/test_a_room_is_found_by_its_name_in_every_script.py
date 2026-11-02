"""A room is found by its name in whatever script the name is written.

Audit world_spatial_structure_light F2 (2026-11-01, CORRUPTION latent in ja):
`normalize_room_id` kept only `[a-z0-9]`, so `normalize_room_id("台所") == ''`,
`room_spellings("kitchen", {"name": "台所"}) == ('kitchen',)` and
`scene_room_id(scene, "台所") == ''` -- a held room could not be found by its
name, and a Japanese new place was never reserved (`reserve_places` keyed it
""), so the room author never built it. Accented Latin lost its letters:
"Café Rouge" folded to `caf_rouge`, "Ærø Quay" to `r_quay`. The same file
already used a script-aware fold for beings ("the old ASCII fold erased every
non-Latin name"); rooms now use `language_runtime.fold_key`, which is the SAME
string as the old slug for ASCII input, so every id already minted keeps
matching its own spelling.
"""

from world.spatial import normalize_room_id, room_name_words, room_spellings, scene_room_id


def test_ascii_is_byte_identical():
    assert normalize_room_id("Back Yard") == "back_yard"
    assert normalize_room_id("Cope's Boatyard") == "cope_s_boatyard"
    assert normalize_room_id("  the_Old--Mill ") == "the_old_mill"
    assert room_name_words("Cope's Boatyard") == ("copes", "boatyard")


def test_a_japanese_name_folds_to_itself():
    assert normalize_room_id("台所") == "台所"
    assert normalize_room_id("裏庭") == "裏庭"
    assert room_spellings("kitchen", {"name": "台所"}) == ("台所", "kitchen")


def test_accented_latin_keeps_its_letters():
    assert normalize_room_id("Café Rouge") == "café_rouge"
    assert normalize_room_id("Ærø Quay") == "ærø_quay"


def test_a_held_room_is_found_by_its_japanese_name():
    sc = {"rooms": {"kitchen": {"name": "台所", "adjacent": []},
                    "yard": {"name": "裏庭", "adjacent": []}}}
    assert scene_room_id(sc, "台所") == "kitchen"
    assert scene_room_id(sc, "裏庭") == "yard"
    assert scene_room_id(sc, "書斎") == ""


def test_a_japanese_name_is_found_by_its_content_words():
    sc = {"rooms": {"k": {"name": "裏庭の台所", "adjacent": []},
                    "s": {"name": "書斎", "adjacent": []}}}
    assert scene_room_id(sc, "台所") == "k"


def test_a_legacy_ascii_id_of_an_accented_name_still_answers():
    sc = {"rooms": {"caf_rouge": {"name": "Café Rouge", "adjacent": []}}}
    assert scene_room_id(sc, "caf_rouge") == "caf_rouge"
    assert scene_room_id(sc, "Café Rouge") == "caf_rouge"
