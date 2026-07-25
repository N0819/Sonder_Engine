"""Scene backdrops (EXPERIMENTAL) — prompt derivation and cache keying.

The feature renders the room the player is standing in as a chat background.
These tests pin the two properties that make it safe and affordable:

  * the prompt is derived from the player's PERCEPTION view with people and
    speech stripped, never from the objective scene, so a picture cannot leak
    what the prose withheld;
  * the cache key changes when the room LOOKS different and not when someone
    walks through it, which is what makes revisiting a room free.
"""

from __future__ import annotations

from backdrops import _setting_only, visual_signature


def _scene():
    return {
        "location": "USS Enterprise D", "time": "night",
        "rooms": {
            "ten_forward": {"name": "Ten Forward",
                            "desc": "Amber light, panoramic windows."},
            "deck10": {"name": "Corridor", "desc": "Grey panelling."},
        },
        "positions": {"Hinami": "ten_forward"},
    }


# --- cache keying ----------------------------------------------------------

def test_rooms_have_distinct_signatures():
    sc = _scene()
    assert visual_signature(sc, "ten_forward") != visual_signature(sc, "deck10")


def test_people_moving_does_not_invalidate_a_backdrop():
    """The whole economics of the feature: a room is not a different picture
    because someone walked into it."""
    sc = _scene()
    before = visual_signature(sc, "ten_forward")
    sc["positions"]["Guinan"] = "ten_forward"
    sc["positions"]["Hinami"] = "deck10"
    assert visual_signature(sc, "ten_forward") == before


def test_a_visible_change_does_invalidate_it():
    sc = _scene()
    before = visual_signature(sc, "ten_forward")
    sc["rooms"]["ten_forward"]["desc"] = "Dark. Emergency lighting only."
    assert visual_signature(sc, "ten_forward") != before


def test_time_of_day_changes_the_picture():
    sc = _scene()
    before = visual_signature(sc, "ten_forward")
    sc["time"] = "dawn"
    assert visual_signature(sc, "ten_forward") != before


def test_damage_elsewhere_does_not_invalidate_this_room():
    """Overlays are read per-room so a fire two decks away does not force every
    other backdrop to regenerate."""
    sc = _scene()
    before = visual_signature(sc, "ten_forward")
    sc["overlays"] = {"deck10": ["scorched, smoke-filled"]}
    assert visual_signature(sc, "ten_forward") == before
    sc["overlays"]["ten_forward"] = ["window cracked"]
    assert visual_signature(sc, "ten_forward") != before


def test_style_is_part_of_the_key():
    sc = _scene()
    assert visual_signature(sc, "ten_forward", {"genre": "noir"}) \
        != visual_signature(sc, "ten_forward", {"genre": "pastoral"})


# --- keeping people out of the frame --------------------------------------

def test_dialogue_is_removed_before_person_clauses():
    """The first draft stripped attributions first, which left the quoted
    sentence behind looking like narration -- the "setting" text came out as
    almost pure dialogue."""
    text = ('The Doctor smiles and says, "The bar is where forgotten things '
            'are remembered." Amber light falls across the long windows.')
    out = _setting_only(text)
    assert "forgotten things" not in out
    assert "Doctor" not in out
    assert "Amber light" in out


def test_person_action_sentences_are_dropped():
    text = ("He leans toward the panel. The corridor is narrow and grey-lit. "
            "She turns away.")
    out = _setting_only(text)
    assert "corridor is narrow" in out
    assert "leans" not in out and "turns away" not in out


def test_pure_setting_prose_survives_intact():
    text = ("Peat smoke hangs under low beams. The hearth throws orange "
            "across rough stone.")
    out = _setting_only(text)
    assert "Peat smoke" in out and "hearth" in out


def test_empty_and_none_are_safe():
    assert _setting_only("") == ""
    assert _setting_only(None) == ""


def test_all_dialogue_yields_nothing_rather_than_leaking():
    """Over-stripping is the correct failure direction: a thin prompt is
    recoverable, a character in the picture is not."""
    text = '"Get down!" he shouted. "They are already inside."'
    assert _setting_only(text).strip(" .") == ""
