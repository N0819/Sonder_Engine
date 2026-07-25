"""Scene backdrops (EXPERIMENTAL) — prompt derivation and cache keying.

The feature renders the room the player is standing in as a chat background.
These tests pin the two properties that make it safe and affordable:

  * the image prompt comes from a WHITELISTED spatial projection -- room
    architecture, light, exits, damage -- with occupants excluded by
    construction, so a character or monster cannot reach the picture. An
    earlier draft derived it from perception prose and stripped people with
    regexes; structured data is both safer and much richer, and the prose path
    survives only as optional flavour.
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
    sc = _scene()          # fixture is "night"
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


# --- the spatial projection is a whitelist, not a filter -------------------

def test_projection_excludes_occupants_by_construction():
    """The safety argument for preferring spatial data over prose: a monster
    cannot appear in a backdrop built from a projection that has no concept of
    occupants. This is a whitelist, so a NEW scene field cannot silently start
    leaking people either."""
    from backdrops import room_projection
    sc = _scene()
    sc["entities"] = {"grue": {"name": "Lurking Grue", "kind": "monster"}}
    sc["positions"]["Lurking Grue"] = "ten_forward"
    sc["attire"] = {"Hinami": {"wearing": ["a red coat"]}}
    sc["rooms"]["ten_forward"]["occupants_hint"] = "a grue waits in the dark"

    out = room_projection(sc, "ten_forward")
    blob = repr(out).lower()
    for leak in ("grue", "hinami", "red coat", "occupants_hint"):
        assert leak not in blob, "leaked %r into the backdrop source" % leak
    assert out["desc"].startswith("Amber light")


def test_projection_keeps_what_makes_a_picture():
    from backdrops import room_projection
    sc = _scene()
    sc["rooms"]["ten_forward"]["adjacent"] = [
        {"to": "deck10", "barrier": "open_door", "dir": "n"}]
    sc["overlays"] = {"ten_forward": ["smoke-filled, emergency lighting"]}
    out = room_projection(sc, "ten_forward")
    assert out["name"] == "Ten Forward"
    assert out["time"] == "night"
    assert out["overlays"] == ["smoke-filled, emergency lighting"]
    # Exits carry layout, never a destination occupant.
    assert out["exits"] == [{"barrier": "open_door", "dir": "n"}]
    assert "to" not in repr(out["exits"])


def test_person_overlays_cannot_reach_the_projection():
    """Overlays are keyed by room OR by person; only the room lookup is used."""
    from backdrops import room_projection
    sc = _scene()
    sc["overlays"] = {"Hinami": ["bleeding from a head wound"]}
    assert "bleeding" not in repr(room_projection(sc, "ten_forward"))


def test_unknown_room_yields_a_harmless_stub():
    from backdrops import room_projection
    out = room_projection(_scene(), "nowhere")
    assert out["room"] == "nowhere"
    assert "desc" not in out


def test_notes_are_excluded_because_they_carry_people():
    """Real leak found by dry-running a live chat: a room's freeform `notes`
    read "The TARDIS materializes in this room... Hinami and the Doctor are
    outside it now." A whitelist that admits a freeform field is not one."""
    from backdrops import room_projection
    sc = _scene()
    sc["rooms"]["ten_forward"]["notes"] = \
        "Hinami and the Doctor are outside it now."
    out = room_projection(sc, "ten_forward")
    assert "notes" not in out
    assert "Hinami" not in repr(out)


def test_global_location_is_excluded():
    """Not an engine bug: scene.location tracks relocation correctly since
    TR-3. But backdrops also render HISTORICAL turns when scrolling back, and
    pre-TR-3 checkpoints carry a stale label -- the Enterprise's janitor closet
    still reads "Back Alley, City". A wrong one-line label would render a
    starship cupboard as a city alley, and the room desc already carries the
    setting."""
    from backdrops import room_projection
    sc = _scene()
    sc["location"] = "Back Alley, City"
    assert "Back Alley" not in repr(room_projection(sc, "ten_forward"))


# --- narrative time must not bust the cache -------------------------------

def test_narrative_time_flavour_is_bucketed():
    """scene.time is freeform prose, not a clock. Live values seen include
    "Night", "a few seconds", "a few seconds pass", "moments pass"."""
    from backdrops import time_bucket
    assert time_bucket("Night") == "night"
    assert time_bucket("late afternoon") == "day"
    assert time_bucket("dawn") == "morning"
    # Pure duration says nothing about the light.
    for noise in ("a few seconds", "a few seconds pass", "moments pass", ""):
        assert time_bucket(noise) == ""


def test_same_room_consecutive_turns_is_a_cache_hit():
    """The bug this guards cost a full regeneration per beat: turns 4 and 6 of
    a real chat had an IDENTICAL room description but times of "a few seconds"
    and "a few seconds pass", so the raw string produced two different keys."""
    sc = _scene()
    sc["time"] = "a few seconds"
    first = visual_signature(sc, "ten_forward")
    sc["time"] = "a few seconds pass"
    assert visual_signature(sc, "ten_forward") == first


def test_real_time_of_day_still_changes_the_picture():
    sc = _scene()
    sc["time"] = "night"
    night = visual_signature(sc, "ten_forward")
    sc["time"] = "high noon"
    assert visual_signature(sc, "ten_forward") != night
