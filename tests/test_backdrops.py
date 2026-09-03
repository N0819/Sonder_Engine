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

import json
import os

import pytest

from dressing import backdrops
from dressing.backdrops import _setting_only, visual_signature


def _scene():
    return {
        "location": "USS Enterprise D", "time_of_day": "night",
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
    sc["time_of_day"] = "dawn"
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
    assert visual_signature(sc, "ten_forward", {"tone": "noir"}) \
        != visual_signature(sc, "ten_forward", {"tone": "pastoral"})


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
    from dressing.backdrops import room_projection
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
    from dressing.backdrops import room_projection
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
    from dressing.backdrops import room_projection
    sc = _scene()
    sc["overlays"] = {"Hinami": ["bleeding from a head wound"]}
    assert "bleeding" not in repr(room_projection(sc, "ten_forward"))


def test_unknown_room_yields_a_harmless_stub():
    from dressing.backdrops import room_projection
    out = room_projection(_scene(), "nowhere")
    assert out["room"] == "nowhere"
    assert "desc" not in out


def test_notes_are_excluded_because_they_carry_people():
    """Real leak found by dry-running a live chat: a room's freeform `notes`
    read "The TARDIS materializes in this room... Hinami and the Doctor are
    outside it now." A whitelist that admits a freeform field is not one."""
    from dressing.backdrops import room_projection
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
    from dressing.backdrops import room_projection
    sc = _scene()
    sc["location"] = "Back Alley, City"
    assert "Back Alley" not in repr(room_projection(sc, "ten_forward"))


# --- narrative time must not bust the cache -------------------------------

def test_narrative_time_flavour_is_bucketed():
    """scene.time is freeform prose, not a clock. Live values seen include
    "Night", "a few seconds", "a few seconds pass", "moments pass"."""
    from dressing.backdrops import time_bucket
    assert time_bucket("Night") == "night"
    assert time_bucket("late afternoon") == "day"
    assert time_bucket("dawn") == "morning"
    # Pure duration says nothing about the light.
    for noise in ("a few seconds", "a few seconds pass", "moments pass", ""):
        assert time_bucket(noise) == ""


def test_same_room_consecutive_turns_is_a_cache_hit():
    """The bug this guards cost a full regeneration per beat: turns 4 and 6 of
    a real chat had an IDENTICAL room description but times of "a few seconds"
    and "a few seconds pass", so the raw string produced two different keys.

    Those two strings can no longer reach this field at all -- they were the
    passage phrase, and it has no scene field now -- but the rule that closed
    the bug is the one still worth pinning and is wider than they were: the
    key is a function of the BUCKET, not of the wording, so two ways of saying
    the same hour are one picture."""
    sc = _scene()
    sc["time_of_day"] = "night"
    first = visual_signature(sc, "ten_forward")
    sc["time_of_day"] = "just after nightfall"
    assert visual_signature(sc, "ten_forward") == first


def test_real_time_of_day_still_changes_the_picture():
    sc = _scene()
    sc["time_of_day"] = "night"
    night = visual_signature(sc, "ten_forward")
    sc["time_of_day"] = "high noon"
    assert visual_signature(sc, "ten_forward") != night


# --- paying only once ------------------------------------------------------

def test_concurrent_requests_for_one_room_generate_one_image(temp_db, tmp_path,
                                                             monkeypatch):
    """The same signature is very easy to ask for twice at once -- two turns in
    the same room scroll into view together, a second tab is open, the reader
    scrolls back. Each duplicate is a real image generation with a real price,
    so the second caller must WAIT for the first and then take the cache hit.
    """
    import threading
    import time

    from dressing import backdrops as bd

    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))
    monkeypatch.setattr(bd, "build_backdrop_request", lambda *a, **k: {
        "signature": "a" * 24, "cached": None, "room_name": "Ten Forward",
        # No `flavour`: it left this dict for `arrival_flavour`, which the
        # generate path calls for itself.
        "place": {"name": "Ten Forward"},
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

    monkeypatch.setattr(__import__("llm.providers", fromlist=["providers"]), "generate_image",
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


def test_no_half_written_image_is_ever_visible(temp_db, tmp_path, monkeypatch):
    """Readers hit the PNG route while generation is in flight; a partially
    written file would be served as a corrupt image."""
    from dressing import backdrops as bd

    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))
    monkeypatch.setattr(bd, "build_backdrop_request", lambda *a, **k: {
        "signature": "b" * 24, "cached": None, "room_name": "Corridor",
        "place": {"name": "Corridor"},
    })
    monkeypatch.setattr(bd, "refine_prompt", lambda draft, place: draft)

    seen = []

    def fake_generate_image(prompt, *a, **k):
        # Mid-generation: nothing readable may exist under the final name.
        seen.append(bd.cached_backdrop(9, "b" * 24))
        return b"\x89PNG fake"

    monkeypatch.setattr(__import__("llm.providers", fromlist=["providers"]), "generate_image",
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
    from dressing.backdrops import room_projection
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
    from dressing.backdrops import room_projection
    scene = {"rooms": {"mess": {"name": "Mess Hall",
                                "desc": "Crew members gather here."}}}
    projection = room_projection(scene, "mess")
    assert "desc" not in projection
    assert projection["name"] == "Mess Hall"


def test_architecture_that_merely_mentions_a_people_word_survives():
    """Both of these are real strings from the same chat, and both are things
    to DRAW -- which is why the filter matches "crew members" and not "crew"."""
    from dressing.backdrops import _setting_only
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


# --- branch lineage --------------------------------------------------------
#
# A branch inherits the source chat's whole scene graph, so the rooms it opens
# in are the rooms the source already paid to draw: same room id, same
# description, therefore the same signature. Only the storage directory
# differed, keyed by chat id, so every branch used to redraw its entire
# inheritance one room at a time. It now reads the ancestor's files IN PLACE
# -- never copying them, because a story branched a dozen times would
# otherwise hold a dozen copies of the same corridor.

def _chat(temp_db, name, lineage="[]"):
    import time as _time
    return temp_db.qi(
        "INSERT INTO chats(name,scenario,branched_from,created) VALUES(?,?,?,?)",
        (name, "", lineage, _time.time()))


def _write_backdrop(tmp_path, chat_id, signature, data=b"\x89PNG source"):
    d = tmp_path / str(chat_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / ("%s.png" % signature)).write_bytes(data)
    return d / ("%s.png" % signature)


def test_a_branch_reads_the_source_chats_backdrops(temp_db, tmp_path, monkeypatch):
    from dressing import backdrops as bd
    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))

    src = _chat(temp_db, "Elevator Adventure")
    branch = _chat(temp_db, "Elevator Adventure ⎇41", "[%d]" % src)
    sig = "c" * 24
    original = _write_backdrop(tmp_path, src, sig)

    assert bd.cached_backdrop(branch, sig) == str(original)


def test_an_inherited_backdrop_is_not_copied_into_the_branch(temp_db, tmp_path,
                                                             monkeypatch):
    """The point of the feature is that a branch costs no bytes. Reading the
    ancestor's file in place is what keeps it that way -- copying would turn
    every branch into a full second set of images."""
    from dressing import backdrops as bd
    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))

    src = _chat(temp_db, "Elevator Adventure")
    branch = _chat(temp_db, "Elevator Adventure ⎇41", "[%d]" % src)
    sig = "c" * 24
    _write_backdrop(tmp_path, src, sig)

    bd.cached_backdrop(branch, sig)
    assert not (tmp_path / str(branch)).exists(), "branch duplicated the image"


def test_a_branch_of_a_branch_still_reaches_the_original(temp_db, tmp_path,
                                                         monkeypatch):
    """Rerolling repeatedly from the same story is the normal way this engine
    is used, so lineage has to be transitive -- the picture lives in the
    original chat and the third branch has never met it directly."""
    from dressing import backdrops as bd
    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))

    first = _chat(temp_db, "Elevator Adventure")
    second = _chat(temp_db, "⎇41", "[%d]" % first)
    third = _chat(temp_db, "⎇12", "[%d,%d]" % (second, first))
    sig = "d" * 24
    original = _write_backdrop(tmp_path, first, sig)

    assert bd.cached_backdrop(third, sig) == str(original)


def test_an_unrelated_chat_sees_none_of_them(temp_db, tmp_path, monkeypatch):
    """Reuse follows the branch lineage and nothing else: a different story
    that happens to hash a room the same way still draws its own."""
    from dressing import backdrops as bd
    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))

    src = _chat(temp_db, "Elevator Adventure")
    other = _chat(temp_db, "A different story")
    sig = "e" * 24
    _write_backdrop(tmp_path, src, sig)

    assert bd.cached_backdrop(other, sig) is None


def test_inherited_backdrops_survive_the_source_chats_deletion(temp_db, tmp_path,
                                                               monkeypatch):
    """Why the lineage is a denormalized id list and not a parent_chat_id
    foreign key. Deleting a chat removes its rows and leaves its pictures on
    disk, so a cascade-nulled pointer would lose files that are still there."""
    from dressing import backdrops as bd
    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))

    src = _chat(temp_db, "Elevator Adventure")
    branch = _chat(temp_db, "Elevator Adventure ⎇41", "[%d]" % src)
    sig = "f" * 24
    original = _write_backdrop(tmp_path, src, sig)

    temp_db.qi("DELETE FROM chats WHERE id=?", (src,))
    assert bd.cached_backdrop(branch, sig) == str(original)


def test_a_branchs_own_backdrop_wins_over_the_inherited_one(temp_db, tmp_path,
                                                            monkeypatch):
    """Regenerating in a branch must not reach back and repaint the source."""
    from dressing import backdrops as bd
    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))

    src = _chat(temp_db, "Elevator Adventure")
    branch = _chat(temp_db, "Elevator Adventure ⎇41", "[%d]" % src)
    sig = "0" * 24
    _write_backdrop(tmp_path, src, sig, b"\x89PNG source")
    own = _write_backdrop(tmp_path, branch, sig, b"\x89PNG redrawn")

    assert bd.cached_backdrop(branch, sig) == str(own)


def test_a_damaged_lineage_degrades_to_generating(temp_db, tmp_path, monkeypatch):
    """A hand-edited or truncated value must not take the chat's backdrops
    down with it -- worst case is the pre-lineage behaviour."""
    from dressing import backdrops as bd
    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))

    src = _chat(temp_db, "Elevator Adventure")
    sig = "1" * 24
    _write_backdrop(tmp_path, src, sig)

    for broken in ("{not json", '"a string"', "[null]", '["../../etc"]', ""):
        chat = _chat(temp_db, "branch", broken)
        assert bd.cached_backdrop(chat, sig) is None
        assert bd.branch_lineage(chat) == []


def test_a_chat_is_never_its_own_ancestor(temp_db, tmp_path, monkeypatch):
    """A self-reference would make the lineage walk re-stat the directory the
    lookup just missed on; a cycle between two chats would do it forever."""
    from dressing import backdrops as bd
    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))

    chat = _chat(temp_db, "Elevator Adventure")
    temp_db.qi("UPDATE chats SET branched_from=? WHERE id=?",
               ("[%d,%d]" % (chat, chat), chat))
    assert bd.branch_lineage(chat) == []


# --- visual register -------------------------------------------------------
# Image generators reject on keywords, not on meaning. "Blood on the walls" is
# an ordinary thing for a room to have after a fight and an instant refusal
# from most generators, so a legitimate empty-room backdrop failed on a word.
# The fix is to say what the eye SEES -- which is better image prompting
# anyway, since generators render colour and texture far more reliably than
# they render abstractions.

from dressing.backdrops import place_desc, to_visual_register


class TestVisualRegister:
    def test_the_case_that_prompted_it(self):
        assert "blood" not in to_visual_register(
            "Blood on the walls.").casefold()
        assert "dark red" in to_visual_register("Blood on the walls.")

    @pytest.mark.parametrize("charged,expected", [
        ("bloodstained", "stained dark red"),
        ("bloody", "dark red streaked"),
        ("gore", "dark wet residue"),
        ("viscera", "dark wet matter"),
        ("shackles", "iron cuffs and chain"),
        ("gallows", "heavy wooden frame"),
        ("syringe", "glass and steel instrument"),
        ("gruesome", "stark"),
    ])
    def test_terms_become_what_they_look_like(self, charged, expected):
        assert to_visual_register(f"A {charged} thing.") == f"A {expected} thing."

    def test_the_picture_is_preserved_not_erased(self):
        """The point is a prompt that still paints the same room, not a
        sanitised one that paints a different room."""
        out = to_visual_register("The bloodstained altar and gore-streaked floor.")
        assert "altar" in out and "floor" in out
        assert "dark red" in out and "dark" in out

    def test_it_is_case_insensitive(self):
        assert "dark red staining" in to_visual_register("BLOOD everywhere.")

    def test_word_boundaries_are_respected(self):
        """A bloodwood table is furniture, not an aftermath."""
        assert to_visual_register("A bloodwood table.") == "A bloodwood table."

    def test_longer_terms_win_over_shorter_ones(self):
        assert to_visual_register("A blood-soaked rug.") == "A soaked dark red rug."

    def test_ordinary_description_is_untouched(self):
        text = "Dark oak panelling, a cold hearth, and rain at the window."
        assert to_visual_register(text) == text

    def test_empty_input(self):
        assert to_visual_register("") == ""
        assert to_visual_register(None) == ""


class TestBodySentencesAreDropped:
    """A sentence about a body is a sentence about a person, and belongs in an
    empty-room prompt no more than 'he leans on the console' does. Patching the
    word would leave 'The has been removed' behind."""

    @pytest.mark.parametrize("text", [
        "The corpse has been removed.",
        "Bodies were found here.",
        "A cadaver lay on the slab.",
        "The remains were carried out.",
    ])
    def test_dropped_whole(self, text):
        assert place_desc({"desc": text + " Dark oak panelling."}) \
            == "Dark oak panelling."

    def test_the_rest_of_the_room_survives(self):
        out = place_desc({"desc": "The corpse has been removed. "
                                  "Gore streaks the tiles."})
        assert "dark wet residue streaks the tiles" in out.casefold()

    def test_it_runs_through_the_cache_key_too(self):
        """place_desc is the single definition of what the place looks like,
        used by both the prompt and the signature, so they cannot drift."""
        room = {"desc": "Blood on the walls."}
        assert "blood" not in place_desc(room).casefold()


class TestRoomContinuity:
    """A room's second picture should be its first with the light changed, not
    a fresh invention of the same place."""

    def test_the_anchor_is_the_first_image_and_never_moves(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backdrops, "BACKDROP_DIR", str(tmp_path))
        monkeypatch.setattr(backdrops, "branch_lineage", lambda cid: [])
        first = backdrops.backdrop_path(1, "sigfirst")
        os.makedirs(os.path.dirname(first), exist_ok=True)
        open(first, "wb").write(b"\x89PNG first")

        backdrops.set_room_anchor(1, "yard", "sigfirst")
        assert backdrops.room_anchor(1, "yard")[0] == first

        # A later state of the same room must not become the new anchor: an
        # anchor that drifted would compound artifacts down a chain of edits.
        later = backdrops.backdrop_path(1, "siglater")
        open(later, "wb").write(b"\x89PNG later")
        backdrops.set_room_anchor(1, "yard", "siglater")
        assert backdrops.room_anchor(1, "yard")[0] == first

    def test_no_anchor_for_an_unseen_room_or_a_missing_file(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backdrops, "BACKDROP_DIR", str(tmp_path))
        monkeypatch.setattr(backdrops, "branch_lineage", lambda cid: [])
        assert backdrops.room_anchor(1, "yard")[0] is None
        # Indexed, but the host emptied the directory.
        backdrops.set_room_anchor(1, "yard", "gone")
        assert backdrops.room_anchor(1, "yard")[0] is None
        assert backdrops.room_anchor(1, None)[0] is None

    def test_a_branch_inherits_its_parents_rooms(self, tmp_path, monkeypatch):
        """Otherwise every room is re-invented at the fork, which is exactly
        the discontinuity this exists to prevent."""
        monkeypatch.setattr(backdrops, "BACKDROP_DIR", str(tmp_path))
        monkeypatch.setattr(backdrops, "branch_lineage",
                            lambda cid: [1] if cid == 2 else [])
        parent = backdrops.backdrop_path(1, "sigparent")
        os.makedirs(os.path.dirname(parent), exist_ok=True)
        open(parent, "wb").write(b"\x89PNG parent")
        backdrops.set_room_anchor(1, "yard", "sigparent")
        assert backdrops.room_anchor(2, "yard")[0] == parent


class TestRoomFoldering:
    """Images are filed under their room. A long story is hundreds of them
    across a dozen places, and a flat directory of hex names is unreadable to
    anyone trying to find, keep or delete a particular room."""

    def test_a_room_id_cannot_escape_its_directory(self):
        assert backdrops._room_dir("../../etc") == "etc"
        assert backdrops._room_dir("Ten Forward") == "ten_forward"
        assert backdrops._room_dir("") == "_room"
        assert "/" not in backdrops._room_dir("a/b/c")

    def test_the_flat_layout_is_still_found(self, tmp_path, monkeypatch):
        """Everything generated before rooms had folders is still on disk in
        the old shape, and must not silently regenerate."""
        monkeypatch.setattr(backdrops, "BACKDROP_DIR", str(tmp_path))
        monkeypatch.setattr(backdrops, "branch_lineage", lambda cid: [])
        legacy = backdrops.backdrop_path(1, "oldsig")
        os.makedirs(os.path.dirname(legacy), exist_ok=True)
        open(legacy, "wb").write(b"\x89PNG old")
        assert backdrops.cached_backdrop(1, "oldsig") == legacy

    def test_a_foldered_image_is_found_too(self, tmp_path, monkeypatch):
        monkeypatch.setattr(backdrops, "BACKDROP_DIR", str(tmp_path))
        monkeypatch.setattr(backdrops, "branch_lineage", lambda cid: [])
        nested = backdrops.backdrop_path(1, "newsig", "ten_forward")
        os.makedirs(os.path.dirname(nested), exist_ok=True)
        open(nested, "wb").write(b"\x89PNG new")
        assert backdrops.cached_backdrop(1, "newsig") == nested
        assert "ten_forward" in nested


class TestRevisionPrompt:
    """Two prompts, not one. A generation describes the whole place because
    nothing exists yet; a revision describes only what moved, because the place
    is already in the image it is handed."""

    def test_a_revision_states_the_change_and_not_the_room(self):
        place = {"name": "Courtyard", "desc": "Flagstones and a well.",
                 "weather": ["heavy rain"], "ground": "churned mud"}
        before = {"name": "Courtyard", "desc": "Flagstones and a well."}
        out = backdrops.compose_revision(place, None, before)
        assert "heavy rain" in out and "churned mud" in out
        # The fabric of the room is what the image already shows. Restating it
        # is what invites the model to draw a different courtyard.
        assert "Flagstones" not in out
        assert "EXACTLY" in out and "No people." in out

    def test_what_the_anchor_already_shows_is_not_repeated(self):
        place = {"name": "Courtyard", "weather": ["heavy rain"]}
        out = backdrops.compose_revision(place, None, {"weather": ["heavy rain"]})
        assert "heavy rain" not in out
        assert "reproduce the same room faithfully" in out

    def test_a_generation_still_describes_everything(self):
        place = {"name": "Courtyard", "desc": "Flagstones and a well.",
                 "weather": ["heavy rain"]}
        out = backdrops.compose_prompt(place, None, "")
        assert "Courtyard" in out and "Flagstones" in out and "heavy rain" in out


# --- was the edit tried, and did it work? ----------------------------------
#
# The fallback from a failed edit to a full generation is deliberate: a
# provider with no edits endpoint, a model that refuses one, a corrupt anchor,
# none of those is a reason to have no backdrop. What it was not is VISIBLE.
# A bare `except` set `data = None` and fell through, so an edit that was tried
# and failed left exactly the trace of one never attempted. Asked "is the
# editing suite working", nobody could answer from the artefacts: a room
# holding three images looks the same whether continuity is running or silently
# falling back on every beat.

def _stub_request(bd, monkeypatch, tmp_path, sig="c" * 24):
    monkeypatch.setattr(bd, "BACKDROP_DIR", str(tmp_path))
    monkeypatch.setattr(bd, "build_backdrop_request", lambda *a, **k: {
        "signature": sig, "cached": None, "room_name": "Main Hall",
        "place": {"name": "Main Hall"}, "flavour": "", "room": "hall",
    })
    monkeypatch.setattr(bd, "refine_prompt", lambda draft, place: draft)
    monkeypatch.setattr(bd, "set_room_anchor", lambda *a, **k: None)


def test_a_failed_edit_is_no_longer_indistinguishable_from_never_trying(
        temp_db, tmp_path, monkeypatch):
    """THE DEFECT THIS PINS. Both states produced one fresh generation and an
    identical return value, so `backdrop_continuity` could be on, the anchor
    present, and every edit failing, and the only visible symptom was a room
    with several images -- which is also what correct behaviour looks like.
    """
    from dressing import backdrops as bd
    from llm import providers
    _stub_request(bd, monkeypatch, tmp_path)
    anchor = tmp_path / "anchor.png"
    anchor.write_bytes(b"\x89PNG anchor")
    monkeypatch.setattr(bd, "_continuity_enabled", lambda: True)
    monkeypatch.setattr(bd, "room_anchor",
                        lambda cid, room: (str(anchor), {"name": "Main Hall"}))
    monkeypatch.setattr(bd, "compose_revision", lambda *a, **k: "revise it")

    def boom(*a, **k):
        raise RuntimeError("no edits endpoint")

    monkeypatch.setattr(providers, "edit_image", boom)
    monkeypatch.setattr(providers, "generate_image",
                        lambda *a, **k: b"\x89PNG fresh")

    out = bd.generate_backdrop(11, 0)

    assert out["edit_attempted"] is True
    assert out["edit_used"] is False
    assert "no edits endpoint" in out["edit_error"]
    assert "RuntimeError" in out["edit_error"]
    # Still produced a backdrop: the fallback itself is correct and stays.
    assert open(out["path"], "rb").read() == b"\x89PNG fresh"


def test_a_working_edit_says_it_edited(temp_db, tmp_path, monkeypatch):
    """The other half of the control. If a success looked the same as a
    failure the fields would answer nothing.
    """
    from dressing import backdrops as bd
    from llm import providers
    _stub_request(bd, monkeypatch, tmp_path, sig="d" * 24)
    anchor = tmp_path / "anchor.png"
    anchor.write_bytes(b"\x89PNG anchor")
    monkeypatch.setattr(bd, "_continuity_enabled", lambda: True)
    monkeypatch.setattr(bd, "room_anchor",
                        lambda cid, room: (str(anchor), {"name": "Main Hall"}))
    monkeypatch.setattr(bd, "compose_revision", lambda *a, **k: "revise it")
    monkeypatch.setattr(providers, "edit_image",
                        lambda prompt, data, *a, **k: b"\x89PNG revised")
    monkeypatch.setattr(providers, "generate_image",
                        lambda *a, **k: b"\x89PNG fresh")

    out = bd.generate_backdrop(12, 0)

    assert out["edit_attempted"] is True and out["edit_used"] is True
    assert "edit_error" not in out
    assert out["prompt"] == "revise it"
    assert open(out["path"], "rb").read() == b"\x89PNG revised"


def test_continuity_switched_off_reports_no_attempt_rather_than_a_failure(
        temp_db, tmp_path, monkeypatch):
    """A SHUT GATE IS NOT A BROKEN EDIT, and conflating them would send anyone
    reading these fields to debug a provider when the setting is simply off.
    `backdrop_continuity` defaults off, so this is the common case.
    """
    from dressing import backdrops as bd
    from llm import providers
    _stub_request(bd, monkeypatch, tmp_path, sig="e" * 24)
    monkeypatch.setattr(bd, "_continuity_enabled", lambda: False)
    monkeypatch.setattr(providers, "generate_image",
                        lambda *a, **k: b"\x89PNG fresh")

    out = bd.generate_backdrop(13, 0)

    assert out["edit_attempted"] is False
    assert out["edit_used"] is False
    assert "edit_error" not in out


class TestTheGenerationLockTable:
    """The lock dict grew with the key space and was pruned by nothing.

    A long chat left one dead entry per distinct room-state for the life of the
    process. The comment defending that -- pruning "would race with the
    waiters" -- was true of a bare delete and not of a counted one, so the
    entries were kept for a race that did not have to exist. Measured on the
    unmodified module: 500 distinct signatures, 500 entries, no work in flight.
    """

    def test_it_does_not_grow_with_the_number_of_room_states_seen(self):
        from dressing import backdrops as bd

        for i in range(500):
            with bd._generation_lock((1, "sig%04d" % i)):
                pass

        assert len(bd._GEN_LOCKS) == 0

    def test_a_key_somebody_is_waiting_on_is_not_dropped_underneath_them(self):
        """Pruning must not cost the exclusion the lock exists for: two callers
        for one signature would then generate the identical picture twice,
        which is the whole expense this table was added to avoid.
        """
        import threading

        from dressing import backdrops as bd

        inside = []
        holding = threading.Event()
        release = threading.Event()

        def first():
            with bd._generation_lock((1, "shared")):
                inside.append("first")
                holding.set()
                release.wait(3.0)
                inside.append("first-out")

        def second():
            holding.wait(3.0)
            with bd._generation_lock((1, "shared")):
                inside.append("second")

        threads = [threading.Thread(target=first), threading.Thread(target=second)]
        for t in threads:
            t.start()
        assert holding.wait(3.0)
        # The second caller is now either waiting on the entry or about to be,
        # and the entry must still be there for it to wait on.
        release.set()
        for t in threads:
            t.join(3.0)

        assert inside == ["first", "first-out", "second"]
        assert len(bd._GEN_LOCKS) == 0


# --- the house style, and which half of it the picture can see ---------------

def test_a_directors_note_does_not_invalidate_every_backdrop():
    """Live, chat 67 ("Lagunica adventure ⎇0"): a style guide was set after the
    story's rooms were drawn, and the engine reported EVERY existing image
    absent and began paying to redraw them.

    The whole guide was hashed into the cache key, including `director_notes`
    and `mapping_notes` — instructions to other agents that never touch a
    pixel. `place_desc` states the rule this broke: the key is a function of
    what reaches the image, because a key hashing text the prompt never sees
    pays for regenerations the picture cannot show.
    """
    scene = _scene()
    plain = visual_signature(scene, "ten_forward", None, viewer="Hinami")
    noted = visual_signature(
        scene, "ten_forward",
        {"director_notes": "Refer to RE:Zero canon",
         "mapping_notes": "Refer to RE:Zero canon"},
        viewer="Hinami")
    assert noted == plain


def test_a_tone_does_invalidate_because_it_reaches_the_prompt():
    """The other direction, and the reason this is a whitelist rather than a
    denylist of the retired note fields: `tone` is written into
    `compose_prompt`, so a room drawn under one tone really is a different
    picture. It was `genre` until 2026-09-04, when four of the guide's five
    fields were retired to the Writers' Room and `tone` was the one kept."""
    scene = _scene()
    plain = visual_signature(scene, "ten_forward", None, viewer="Hinami")
    toned = visual_signature(scene, "ten_forward", {"tone": "RE:Zero"},
                             viewer="Hinami")
    assert toned != plain


def test_clearing_a_style_field_returns_the_images_it_had():
    """Absent and present-but-blank must hash identically, or clearing a genre
    strands a story behind a THIRD key instead of returning it to the pictures
    it already paid for."""
    scene = _scene()
    assert (visual_signature(scene, "ten_forward", {}, viewer="Hinami")
            == visual_signature(scene, "ten_forward",
                                {"tone": None}, viewer="Hinami"))


@pytest.mark.parametrize("field", backdrops.VISUAL_STYLE_KEYS)
def test_every_keyed_style_field_actually_reaches_a_prompt(field):
    """The anti-drift check. `VISUAL_STYLE_KEYS` is only correct while every
    field in it changes what the image model is asked for — a field added here
    but not to the prompt reintroduces exactly the defect above."""
    place = {"name": "Ten Forward", "desc": "Amber light."}
    before = backdrops.compose_prompt(place, {}, "")
    after = backdrops.compose_prompt(place, {field: "SENTINELVALUE"}, "")
    assert before != after
    assert "SENTINELVALUE" in after


@pytest.mark.parametrize("field", ("genre", "director_notes", "mapping_notes"))
def test_a_field_the_prompt_ignores_stays_out_of_the_key(field):
    """The converse, stated as a property rather than a list: if setting a
    field cannot change the prompt, it must not change the key."""
    place = {"name": "Ten Forward", "desc": "Amber light."}
    assert (backdrops.compose_prompt(place, {field: "SENTINELVALUE"}, "")
            == backdrops.compose_prompt(place, {}, ""))
    assert field not in backdrops.VISUAL_STYLE_KEYS


# --- what the READ path is allowed to cost -----------------------------------

def test_the_read_path_does_not_walk_the_checkpoint_history(temp_db, monkeypatch):
    """"It used to load images instantly."

    `build_backdrop_request` serves `GET /api/turns/{id}/backdrop`, which the
    reader's scrolling polls and which NEVER generates anything. It was
    computing `flavour` -- and `flavour` needs `arrival_turn_for_room`, which
    walks up to eight per-turn checkpoints backwards, blobs that are ~4.7MB
    each on a real story.

    Measured on live chat 67: 0.548s of the 0.758s that seventeen calls took,
    72% of the read path, for a field only `generate_backdrop` reads. And it
    GREW with a stay, because the lookback walks further the longer the player
    stays put -- 56ms on the beat of arrival, 146ms five beats later. Moving it
    to the one caller that needs it took those seventeen calls from 1203ms to
    312ms and made the per-call cost flat.
    """
    from dressing import backdrops as bd

    walked = []
    real = bd.arrival_turn_for_room
    monkeypatch.setattr(bd, "arrival_turn_for_room",
                        lambda *a, **k: walked.append(a) or real(*a, **k))

    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Backdrop read path", "", 0.0))
    scene = _scene()
    temp_db.qi("INSERT INTO checkpoints(chat_id,turn_idx,blob,created) "
               "VALUES(?,?,?,?)",
               (cid, 1, json.dumps({"world": {"scene": scene}}), 0.0))

    req = bd.build_backdrop_request(cid, 0, "Hinami", None)
    assert req is not None and req["signature"]
    assert walked == [], "the read path walked the checkpoint history again"

    # POSITIVE CONTROL. The assertion above is an absence, and an absence is
    # also what a counter installed on the wrong object produces. So: call the
    # expensive path the read path was separated FROM, with the same wrapper
    # in place. If this does not record a walk, the wrapper is not on the
    # function anyone calls and the guard above proves nothing.
    bd.arrival_flavour(cid, 0, "kitchen", "Hinami")
    assert walked, (
        "arrival_flavour did not reach arrival_turn_for_room: the counter is "
        "not installed where the calls happen")
    walked.clear()
    # And the key is GONE rather than emptied, so a caller that needs the
    # atmosphere is forced to the function that makes it instead of silently
    # composing a prompt with a blank where the arrival prose should be.
    assert "flavour" not in req
