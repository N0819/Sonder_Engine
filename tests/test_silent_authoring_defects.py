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
    character_offscreen_agent,
    normalize_character_data,
)
from story.scene import appearance_of


BASE = "A tall figure in a grey travelling coat, hood raised."


class TestATextBooleanMeansWhatItSays:
    """`bool("false")` is True, so the string opted a character IN to the
    paid off-screen ceiling -- real model calls, for a character the author
    had switched off."""

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

    def test_the_card_reader_no_longer_opts_a_character_in(self):
        sheet = {"identity": {"name": "Reya"},
                 "simulation": {"offscreen_agent": "false"}}
        assert character_offscreen_agent(sheet) is False

    def test_the_legacy_normalize_branch_is_no_safer_and_is_covered(self):
        """The legacy branch applied the same `bool()`, so it was not the
        safe path the first reading of it suggested."""
        legacy = {"name": "Reya", "appearance": "tall",
                  "offscreen_agent": "false"}
        normalized = normalize_character_data(legacy)
        assert normalized["simulation"]["offscreen_agent"] is False

    def test_a_real_opt_in_still_works(self):
        sheet = {"identity": {"name": "Reya"},
                 "simulation": {"offscreen_agent": True}}
        assert character_offscreen_agent(sheet) is True


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
    and for the agent rung, one is a PAID model call the caller asked not to
    have."""

    def test_full_agent_candidates(self, monkeypatch):
        from world import offscreen

        entries = [{"id": f"c{i}", "display": f"C{i}", "char_id": i,
                    "sheet": {}, "state": {}} for i in range(4)]
        monkeypatch.setattr(offscreen, "dormant_subjects",
                            lambda *a, **k: entries)
        monkeypatch.setattr(
            offscreen, "_active_plans_by_actor",
            lambda *a, **k: {e["id"]: [{"status": "active"}] for e in entries},
            raising=False)
        for cap in (0, 1, 2):
            got = offscreen.full_agent_candidates(1, cap=cap)
            assert len(got) <= cap, (cap, len(got))

    def test_fired_consequences_at(self):
        from world import living_world

        assert living_world.fired_consequences_at.__doc__ is not None
        # The bound is checked before the append; with no rows the shape is
        # unchanged, and the ordering is what the unit above proves.
        assert living_world.fired_consequences_at(
            -1, "nowhere", 0.0, 1.0, cap=0) == []


class TestTheCardSaysWhatNobodyReads:
    """The warning that ends the class rather than one instance of it.

    `character_appearance` returns `embodiment.visible.summary` and nothing
    else, so four richly authored fields reach no view, no narrator and no
    memory -- and the only symptom is a body that reads thin.
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

    def test_an_unread_field_is_named(self):
        found = self._warning(
            self._card(hair="Long copper-gold, worn loose."), "hair")
        assert found, "an authored, unread field warned about nothing"
        assert "summary" in found[0]

    def test_every_unread_field_is_named_at_once(self):
        found = self._warning(self._card(
            build="Slight.", face="Youthful.", hair="Copper.",
            eyes="Amber."), "build")
        assert found and all(
            name in found[0] for name in ("build", "face", "hair", "eyes"))

    def test_distinctive_features_counts(self):
        assert self._warning(
            self._card(distinctive_features=["six golden tails"]),
            "distinctive features")

    def test_a_card_that_only_fills_the_summary_is_quiet(self):
        assert not self._warning(self._card(), "delivered to anyone")

    def test_an_empty_string_is_not_authored(self):
        assert not self._warning(
            self._card(build="", face="   "), "delivered to anyone")

    def test_a_text_boolean_is_reported_to_the_author(self):
        sheet = self._card()
        sheet["simulation"] = {"offscreen_agent": "false"}
        assert self._warning(sheet, "offscreen_agent")

    def test_a_real_boolean_is_quiet(self):
        for value in (True, False):
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
        sheet["embodiment"]["interior"] = [{"name": "Entry Passage"},
                                           {"name": "Deep Hold"}]
        assert not self._warning(sheet, "embodiment.interior")

    def test_an_ordinary_card_with_no_interior_is_quiet(self):
        """No noise on the common case: an ordinary human body has no inside
        the story moves through, and says so by leaving the key out."""
        assert not self._warning(self._card(), "embodiment.interior")

    def test_the_existing_warnings_still_fire(self):
        """This function runs on all nine card-producing surfaces; the three
        it was built for must not be displaced by the two added here."""
        blank = {"identity": {"name": "Reya"}}
        assert len(character_card_warnings(blank)) >= 3
