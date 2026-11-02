"""Five defects that were silent by construction, and the warning that ends one.

Every one of these was found by reading source rather than by a failing test,
and every one produces no error, no warning and no visible symptom at the
moment it goes wrong. That is the property they share and the reason they are
in one file: a defect that announces itself gets fixed the day it lands.

The class, stated once: an authored value that the engine cannot read as the
author wrote it. A boolean that arrived as text, a ledger note narrated as
prose, a plural noun given a singular verb, an era's diagnostics carrying
another era's events, a cap that lets one through. Four of the five had no
consequence a player could name; the first spends money.
"""

from __future__ import annotations

import json

import pytest

from agents.common import _appearance_as_prose
from story.character_schema import (
    authored_bool,
    character_card_warnings,
)
from story.scene import appearance_of


BASE = "A tall figure in a grey travelling coat, hood raised."


class TestATextBooleanMeansWhatItSays:
    """`bool("false")` is True, so the string opted a character IN to the
    paid off-screen ceiling -- real model calls, for a character the author
    had switched off. That opt-in (`simulation.offscreen_agent`) was retired
    with its tier on 2026-11-01, and the three tests that drove it through
    the card reader went with it; `authored_bool` itself still reads every
    authored boolean that arrives as text (`spatial_fov`, `spatial_senses`)."""

    @pytest.mark.parametrize("written", ["false", "False", "FALSE", "no",
                                         "off", "0", " false ", ""])
    def test_the_words_a_human_writes_for_false(self, written):
        assert authored_bool(written) is False

    @pytest.mark.parametrize("written", ["true", "True", "yes", "on", "1"])
    def test_the_words_a_human_writes_for_true(self, written):
        assert authored_bool(written) is True

    def test_a_real_boolean_passes_through(self):
        assert authored_bool(True) is True
        assert authored_bool(False) is False

    def test_an_unknown_shape_keeps_pythons_answer(self):
        """Inventing a verdict for a shape nobody meant to write is how a
        coercion starts lying in the other direction."""
        assert authored_bool("maybe") is True
        assert authored_bool([]) is False
        assert authored_bool(None) is False
        assert authored_bool(None, default=True) is True


class TestADerivedNoteIsAClauseNotAModifier:
    """The label `; clothing state:` was replaced by `; with`, a preposition
    that assumes a NOUN PHRASE. Authored notes are noun-shaped and read
    correctly; the notes `flat_state` DERIVES are adjective-shaped, and every
    observer of every undressed body read `with bare at the head, torso`.

    Built from real `regions`, because `rederive_entry` rebuilds the derived
    half of `state` from them -- a note with no region behind it is dropped
    before any renderer sees it, which is the ledger working.
    """

    # `beneath` prose, because `rederive_entry` drops a region carrying
    # nothing at all -- a region with no garment AND nothing authored under it
    # is undescribed, not bare, and correctly says nothing.
    NAKED = {"regions": {r: {"garments": [], "beneath": "skin."} for r in
                         ("head", "torso", "arms", "waist", "groin", "legs",
                          "feet")}}

    def _prose(self, entry):
        return _appearance_as_prose(appearance_of(
            "H", BASE, {"attire": {"H": entry}, "overlays": {}}))

    def test_the_live_string_is_grammatical(self):
        prose = self._prose(self.NAKED)
        assert "with bare at the" not in prose
        assert "bare at the head" in prose          # the fact survives
        assert "clothing state:" not in prose

    def test_an_authored_note_still_reads(self):
        entry = json.loads(json.dumps(self.NAKED))
        entry["state"] = ["soaked through"]
        prose = self._prose(entry)
        assert "soaked through" in prose
        assert "; with" not in prose

    def test_a_dressed_body_keeps_its_wearing_clause(self):
        entry = {"regions": {"torso": {"garments": [
            {"name": "white lab coat", "state": "worn"}], "beneath": ""}}}
        prose = self._prose(entry)
        assert "wearing white lab coat" in prose
        assert "; with" not in prose


class TestHalfTheRegionNamesArePlural:
    """`{subject} is visible: {detail}` put a singular verb on a region name.
    Four of the eight regions are plural, and `feet` is the one a spelling
    rule gets wrong -- it was on the page as "exposed feet is visible".

    The sentence is composed in `agents/composer.py` from the compositor pack.
    `agents/perception.py` carries the same wording in
    `_deliver_foreground_body_details`, which only `torso` and `groin` have
    cues for -- both singular -- so it could never have produced the live
    string. Testing the seam the symptom actually came from.
    """

    def _render(self, place, label="Hinami"):
        from agents.composer import Percept, _render_standing

        return _render_standing(Percept(
            kind="body_region", channel="sight", source_label=label,
            data={"place": place, "detail": "worn and travelled"}))

    @pytest.mark.parametrize("place", ["feet", "arms", "legs", "hands"])
    def test_a_plural_place_takes_are(self, place):
        assert f"exposed {place} are visible" in self._render(place)

    @pytest.mark.parametrize("place", ["torso", "head", "waist", "groin",
                                       "chest", "midriff"])
    def test_a_singular_place_takes_is(self, place):
        assert f"exposed {place} is visible" in self._render(place)

    def test_the_self_view_agrees_too(self):
        assert "Your exposed feet are visible" in self._render("feet", "you")
        assert "Your exposed torso is visible" in self._render("torso", "you")

    def test_both_packs_carry_both_templates(self):
        """A pack missing the plural key would fall back silently."""
        for lang in ("en", "ja"):
            data = json.load(open(
                f"language_packs/{lang}/cards/compositor.json",
                encoding="utf-8"))
            assert "exposed_detail" in data["templates"], lang
            assert "exposed_detail_plural" in data["templates"], lang


class TestOneEraSDiagnostics:
    """`registry_for` is frame-scoped and the event listing beside it was
    not, so a story with frames explained its present with events another era
    minted. `scheduled_events` has no frame column; the scoping is in the
    payload."""

    def test_the_present_and_a_frame_are_told_apart(self):
        from world.charter_runtime import _event_frame

        assert _event_frame({"frame_id": None}) is None
        assert _event_frame({}) is None
        assert _event_frame({"frame_id": 4}) == 4
        assert _event_frame({"frame_id": "4"}) == 4

    def test_a_row_written_before_the_field_existed_reads_as_present(self):
        """Those stories had no frames, which is where the present is."""
        from world.charter_runtime import _event_frame

        assert _event_frame({"what": "the mill stopped"}) is None
        assert _event_frame({"frame_id": ""}) is None
        assert _event_frame({"frame_id": "not a number"}) is None


class TestACapOfZeroReturnsNothing:
    """Both appended before checking the bound, so `cap=0` returned one --
    and for the agent rung, one was a PAID model call the caller asked not to
    have. That rung's selector (`full_agent_candidates`) was retired with it
    on 2026-11-01, and its test with it; the fuse reader below is live."""

    def test_fired_consequences_at(self):
        from world import living_world

        assert living_world.fired_consequences_at.__doc__ is not None
        # The bound is checked before the append; with no rows the shape is
        # unchanged, and the ordering is what the unit above proves.
        assert living_world.fired_consequences_at(
            -1, "nowhere", 0.0, 1.0, cap=0) == []


class TestTheCardSaysWhatNobodyReads:
    """The warning that ends the class rather than one instance of it.

    `build`, `face`, `hair` and `eyes` are delivered now, so the warning that
    named them would be telling an author to move work that is already being
    read. What is left is the field that is still authored and still unread.
    """

    def _card(self, **visible):
        return {"identity": {"name": "Reya"},
                "psychology": {"drive": {"essence": "to be owed nothing"},
                               "capacity": "ordinary"},
                "initial_state": {"goals": ["reach the coast"]},
                "embodiment": {"visible": {"summary": "A tall woman.",
                                           **visible}}}

    def _warning(self, sheet, needle):
        return [w for w in character_card_warnings(sheet) if needle in w]

    def test_a_delivered_field_is_not_warned_about(self):
        """The four body fields reach a view now, so nothing tells the author
        to move them somewhere they would be read."""
        sheet = self._card(build="Slight.", face="Youthful.",
                           hair="Copper.", eyes="Amber.")
        assert not self._warning(sheet, "no view")
        assert not self._warning(sheet, "delivered to anyone")

    def test_the_delivered_fields_reach_the_shape_that_delivers_them(self):
        """And the warning is quiet for the right reason: the projection ran.

        A silent warning would otherwise be indistinguishable from a warning
        somebody deleted."""
        from story.character_schema import character_visible_body

        body = character_visible_body(self._card(
            build="Slight.", face="Youthful.", hair="Copper.", eyes="Amber."))
        assert body["build"] == "Slight."
        assert body["regions"]["head"] == {
            "face": "Youthful.", "hair": "Copper.", "eyes": "Amber."}

    def test_distinctive_features_counts(self):
        assert self._warning(
            self._card(distinctive_features=["six golden tails"]),
            "distinctive features")

    def test_a_card_that_only_fills_the_summary_is_quiet(self):
        assert not self._warning(self._card(), "no view")

    def test_an_empty_string_is_not_authored(self):
        assert not self._warning(self._card(build="", face="   "), "no view")

    def test_the_retired_off_screen_opt_in_is_not_warned_about(self):
        """A text boolean in `simulation.offscreen_agent` was reported to the
        author until 2026-11-01, when the opt-in went with the paid tier it
        opted into. A card still carrying it, in any shape, carries a key
        nothing reads, and a warning about its TYPE would say it matters."""
        for value in ("false", True, False):
            sheet = self._card()
            sheet["simulation"] = {"offscreen_agent": value}
            assert not self._warning(sheet, "offscreen_agent")

    def test_a_nameless_interior_station_is_named(self):
        """A station with no name is no handle anything can reach, so
        `_normalize_interior` drops it -- and an author who typed a
        description into it has every reason to think the room exists."""
        sheet = self._card()
        sheet["embodiment"]["interior"] = [{"name": "Entry Passage"},
                                           {"desc": "It widens here."}]
        found = self._warning(sheet, "embodiment.interior")
        assert found and "position 2" in found[0]

    def test_a_well_formed_interior_is_quiet(self):
        sheet = self._card()
        # A chain of stations that says how long the crossed one takes. A
        # chain that says nothing anywhere is its own silent defect and has
        # its own case below.
        sheet["embodiment"]["interior"] = [
            {"name": "Entry Passage", "transit_seconds": 8},
            {"name": "Deep Hold"}]
        assert not self._warning(sheet, "embodiment.interior")

    def test_a_chain_with_no_crossing_time_anywhere_is_named(self):
        """The same class as the empty drive: authored, plausible-looking,
        and silently inert. A chain no station gives a crossing time to
        holds its occupant in every station until something moves them by
        hand -- transit as a state someone is in rather than a process that
        runs."""
        sheet = self._card()
        sheet["embodiment"]["interior"] = [{"name": "Entry Passage"},
                                           {"name": "Deep Hold"}]
        assert self._warning(sheet, "transit_seconds")

    def test_an_ordinary_card_with_no_interior_is_quiet(self):
        """No noise on the common case: an ordinary human body has no inside
        the story moves through, and says so by leaving the key out."""
        assert not self._warning(self._card(), "embodiment.interior")

    def test_the_existing_warnings_still_fire(self):
        """This function runs on all nine card-producing surfaces; the three
        it was built for must not be displaced by the two added here."""
        blank = {"identity": {"name": "Reya"}}
        assert len(character_card_warnings(blank)) >= 3
