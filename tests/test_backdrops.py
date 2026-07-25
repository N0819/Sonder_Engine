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


# --- paying only once ------------------------------------------------------

def test_concurrent_requests_for_one_room_generate_one_image(tmp_path, monkeypatch):
    """The same signature is very easy to ask for twice at once -- two turns in
    the same room scroll into view together, a second tab is open, the reader
    scrolls back. Each duplicate is a real image generation with a real price,
    so the second caller must WAIT for the first and then take the cache hit.
    """
    import threading
    import time

    import backdrops as bd

    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))
    monkeypatch.setattr(bd, "build_backdrop_request", lambda *a, **k: {
        "signature": "a" * 24, "cached": None, "room_name": "Ten Forward",
        "place": {"name": "Ten Forward"}, "flavour": "",
    })
    monkeypatch.setattr(bd, "refine_prompt", lambda draft, place: draft)

    calls = []
    barrier = threading.Barrier(2, timeout=5)

    def fake_generate_image(prompt, *a, **k):
        calls.append(prompt)
        # Slow enough that the second thread is provably waiting on the lock
        # rather than merely arriving after the first one finished.
        time.sleep(0.15)
        return b"\x89PNG fake"

    monkeypatch.setattr(__import__("providers"), "generate_image",
                        fake_generate_image)

    results = []

    def run():
        barrier.wait()                      # both threads arrive together
        results.append(bd.generate_backdrop(7, 0))

    threads = [threading.Thread(target=run) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert len(calls) == 1, "paid for the same picture twice"
    assert len(results) == 2
    assert {r["cached"] for r in results} == {False, True}
    assert (tmp_path / "7" / ("a" * 24 + ".png")).read_bytes() == b"\x89PNG fake"


def test_no_half_written_image_is_ever_visible(tmp_path, monkeypatch):
    """Readers hit the PNG route while generation is in flight; a partially
    written file would be served as a corrupt image."""
    import backdrops as bd

    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))
    monkeypatch.setattr(bd, "build_backdrop_request", lambda *a, **k: {
        "signature": "b" * 24, "cached": None, "room_name": "Corridor",
        "place": {"name": "Corridor"}, "flavour": "",
    })
    monkeypatch.setattr(bd, "refine_prompt", lambda draft, place: draft)

    seen = []

    def fake_generate_image(prompt, *a, **k):
        # Mid-generation: nothing readable may exist under the final name.
        seen.append(bd.cached_backdrop(9, "b" * 24))
        return b"\x89PNG fake"

    monkeypatch.setattr(__import__("providers"), "generate_image",
                        fake_generate_image)

    bd.generate_backdrop(9, 0)
    assert seen == [None]
    assert bd.cached_backdrop(9, "b" * 24)


# --- occupants written into rooms[].desc -----------------------------------
#
# The whitelist assumed `desc` was pure architecture. Dry-running chat 34
# through the finished routes proved it is not: mapping writes populations into
# it exactly where narrative prose would name a character.

_TEN_FORWARD = (
    "The ship's main lounge and social hub, located at the forward edge of "
    "Deck 10. A long curved bank of panoramic windows wraps around the forward "
    "section. Crew members and civilians gather here during off-duty hours, "
    "conversations murmuring at various tables."
)


def test_occupants_in_a_room_desc_never_reach_the_prompt():
    from backdrops import room_projection
    scene = {"rooms": {"ten_forward": {"name": "Ten Forward",
                                       "desc": _TEN_FORWARD}}}
    desc = room_projection(scene, "ten_forward")["desc"]
    assert "Crew members" not in desc and "civilians" not in desc
    assert "conversations murmuring" not in desc
    # ...and the room itself survives, or the strip would have cost more than
    # it saved.
    assert "panoramic windows" in desc


def test_a_desc_that_is_nothing_but_occupants_yields_no_desc():
    """No raw-text fallback: an empty description is a thinner prompt, which
    is the acceptable failure. Handing the occupants back is not."""
    from backdrops import room_projection
    scene = {"rooms": {"mess": {"name": "Mess Hall",
                                "desc": "Crew members gather here."}}}
    projection = room_projection(scene, "mess")
    assert "desc" not in projection
    assert projection["name"] == "Mess Hall"


def test_architecture_that_merely_mentions_a_people_word_survives():
    """Both of these are real strings from the same chat, and both are things
    to DRAW -- which is why the filter matches "crew members" and not "crew"."""
    from backdrops import _setting_only
    for line in (
        "Along the north and south walls, several standard doors lead to crew "
        "quarters, labs, and utility spaces.",
        "The LCARS display panel reads 'En Route to Deck 14' in soft amber "
        "text while lines of crew registration data scroll rapidly across it.",
    ):
        assert _setting_only(line) == line


def test_writing_people_into_a_room_desc_is_not_a_new_picture():
    """The cache key hashes the PROJECTED description, so a room does not
    regenerate because its occupants were written into or out of the text --
    a change the backdrop cannot show, since it never depicts them."""
    empty = {"rooms": {"ten_forward": {
        "name": "Ten Forward",
        "desc": "The ship's main lounge. A long curved bank of panoramic "
                "windows wraps around the forward section."}}}
    crowded = {"rooms": {"ten_forward": {
        "name": "Ten Forward",
        "desc": empty["rooms"]["ten_forward"]["desc"]
                + " Crew members and civilians gather here during off-duty hours."}}}
    assert (visual_signature(empty, "ten_forward")
            == visual_signature(crowded, "ten_forward"))
