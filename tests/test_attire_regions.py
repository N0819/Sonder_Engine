"""Clothing by region, and the fact that taking it off takes time.

The transcript this exists for: the player wrote "you begin to untie your sash.
Still fully clothed not quite undressed yet", and the beat had her bare in the
same paragraph. Two causes, both structural rather than a bad model call --
there was no state between dressed and undressed to stop at, and the ledger
recorded three complete outfits worn at once because nothing said a garment
occupies anywhere.

Deliberately database-free: everything here is a pure function over dicts.
"""

from __future__ import annotations

import attire


# --- where a garment goes ---------------------------------------------------

def test_garments_land_on_the_body_part_they_cover():
    assert attire.region_of("leather boots") == "feet"
    assert attire.region_of("a woollen hat") == "head"
    assert attire.region_of("silk sash") == "waist"
    assert attire.region_of("flowing robes") == "torso"
    assert attire.region_of("riding trousers") == "legs"
    assert attire.region_of("embroidered gloves") == "hands"


def test_the_noun_at_the_end_wins():
    """English puts the noun last, so a modifier must not capture the garment."""
    assert attire.region_of("leather riding boots") == "feet"
    assert attire.region_of("boot-black apron") == "waist"


def test_a_long_description_is_cut_at_a_word_not_mid_word():
    """These are bounded because seven unbounded fields on a card is an
    unbounded prompt. But "old scars across the ri" reads as a bug, and is."""
    long = "silvered burn scarring along the inside of the forearm, " * 12
    kept = attire.normalize_regions(
        {"regions": {"arms": {"garments": [], "beneath": long}}})["arms"]["beneath"]
    assert len(kept) <= attire.BENEATH_LIMIT
    assert long.startswith(kept)          # a prefix, never a paraphrase
    assert not kept.endswith(",")
    assert long[len(kept):len(kept) + 1] in ("", " ", ",")


def test_a_description_that_fits_is_left_exactly_alone():
    text = "old scars across the ribs"
    kept = attire.normalize_regions(
        {"regions": {"torso": {"garments": [], "beneath": text}}})["torso"]["beneath"]
    assert kept == text


def test_an_unrecognisable_garment_is_kept_not_dropped():
    """Losing someone's clothes because the parser did not know the word would
    be worse than filing them roughly."""
    assert attire.region_of("a qipao of unusual cut") == attire.DEFAULT_REGION
    assert attire.region_of("") == attire.DEFAULT_REGION


# --- the old shape still works ----------------------------------------------

def test_a_legacy_flat_outfit_becomes_regions():
    """Every existing card and every live story predates this. A character
    whose clothes vanished on upgrade would be worse than no feature."""
    regions = attire.normalize_regions(
        {"wearing": ["a linen shirt", "heavy boots", "a wide belt"]})
    assert set(regions) == {"torso", "feet", "waist"}
    assert regions["feet"]["garments"][0]["name"] == "heavy boots"
    assert regions["feet"]["garments"][0]["state"] == "worn"


def test_authored_regions_are_not_overruled_by_the_flat_list():
    outfit = {
        "wearing": ["a linen shirt"],
        "regions": {"torso": {"garments": [{"name": "a linen shirt",
                                            "state": "loosened"}],
                              "beneath": "old scars across the ribs"}},
    }
    regions = attire.normalize_regions(outfit)
    assert len(regions["torso"]["garments"]) == 1     # not duplicated
    assert regions["torso"]["garments"][0]["state"] == "loosened"
    assert regions["torso"]["beneath"] == "old scars across the ribs"


def test_junk_is_discarded_without_taking_the_outfit_with_it():
    regions = attire.normalize_regions({"regions": {
        "torso": {"garments": ["a shirt", None, {"state": "worn"}, 7]},
        "nonsense": {"garments": ["a hat"]},
    }})
    assert [g["name"] for g in regions["torso"]["garments"]] == ["a shirt"]
    assert "nonsense" not in regions


# --- undressing takes time --------------------------------------------------

def test_a_garment_moves_one_rung_per_beat():
    """The whole point. Worn to removed in a single beat is what put a
    character bare in the paragraph that said she was still dressed."""
    before = attire.normalize_regions({"wearing": ["silk sash"]})
    proposed = {"waist": {"garments": [{"name": "silk sash", "state": "removed"}]}}
    after = attire.advance(before, proposed)
    assert after["waist"]["garments"][0]["state"] == "loosened"


def test_the_next_beat_carries_on_from_there():
    regions = attire.normalize_regions({"wearing": ["silk sash"]})
    for expected in ("loosened", "open", "removed"):
        regions = attire.advance(
            regions,
            {"waist": {"garments": [{"name": "silk sash", "state": "removed"}]}})
        assert regions["waist"]["garments"][0]["state"] == expected


def test_a_player_who_says_so_gets_it_at_once():
    before = attire.normalize_regions({"wearing": ["silk sash"]})
    after = attire.advance(
        before,
        {"waist": {"garments": [{"name": "silk sash", "state": "removed"}]}},
        decisive=True)
    assert after["waist"]["garments"][0]["state"] == "removed"


def test_decisive_intent_is_about_meaning_not_vocabulary():
    assert attire.decisive_intent("She tears the robe off and throws it aside")
    assert attire.decisive_intent("you strip completely")
    assert attire.decisive_intent("he rips off his shirt")
    assert attire.decisive_intent("she wrenches the coat away")
    assert attire.decisive_intent("flings it aside")
    assert attire.decisive_intent("gone in one motion")
    assert not attire.decisive_intent("you begin to untie your sash")
    assert not attire.decisive_intent("her fingers work at the knot")


class TestWhoseClothesCameOff:
    """A character can be as decisive as the player, and one flag for the whole
    beat meant the player yanking their own coat off undressed everyone
    standing near them."""

    WARDROBE = {"Mira": ["a silk sash", "flowing robes"],
                "Corin": ["a leather coat"]}

    def targets(self, player="", others=()):
        return attire.decisive_targets(player, list(others), self.WARDROBE, "Mira")

    def test_a_character_can_be_decisive_not_only_the_player(self):
        assert self.targets(others=["Corin rips his own coat off."]) == {"Corin"}

    def test_the_actor_is_not_the_target(self):
        """"Corin tears the sash from her waist" is MIRA being undressed. The
        garment says whose body it is; the name in the sentence need not."""
        assert self.targets(
            others=["Corin tears the sash from her waist."]) == {"Mira"}

    def test_one_person_hurrying_does_not_undress_the_room(self):
        assert self.targets("I rip my robes off") == {"Mira"}

    def test_prose_says_the_garment_differently_than_the_card_did(self):
        """A card wrote "a leather coat"; prose says "the leather coat"."""
        assert self.targets(others=["The leather coat is yanked away."]) == {"Corin"}

    def test_the_head_noun_is_enough_when_only_one_person_has_one(self):
        assert self.targets(others=["He tears the sash free."]) == {"Mira"}

    def test_a_name_decides_when_no_garment_is_mentioned(self):
        assert self.targets(others=["Mira strips to the waist."]) == {"Mira"}

    def test_the_players_own_words_default_to_the_player(self):
        assert self.targets("I strip.") == {"Mira"}

    def test_first_person_from_elsewhere_does_not_claim_the_player(self):
        """Only the player's own input has an unspoken first-person subject."""
        assert self.targets(others=["I strip."]) == set()

    def test_patience_is_still_patience(self):
        assert self.targets("she begins to untie her sash") == set()

    def test_prose_naming_nobody_hurries_nobody(self):
        assert self.targets(others=["Clothing is torn away somewhere."]) == set()


def test_getting_dressed_is_not_slowed_down():
    """The asymmetry is deliberate: it is undressing that kept happening
    instantly, and undressing that has a middle worth staying in."""
    before = {"torso": {"garments": [{"name": "a coat", "state": "removed"}]}}
    after = attire.advance(
        before, {"torso": {"garments": [{"name": "a coat", "state": "worn"}]}})
    assert after["torso"]["garments"][0]["state"] == "worn"


def test_a_region_nobody_mentioned_is_unchanged_not_undressed():
    before = attire.normalize_regions({"wearing": ["boots", "a shirt"]})
    after = attire.advance(
        before, {"torso": {"garments": [{"name": "a shirt", "state": "loosened"}]}})
    assert after["feet"]["garments"][0]["state"] == "worn"


def test_a_new_garment_is_kept_rather_than_policed():
    before = attire.normalize_regions({"wearing": ["a shirt"]})
    after = attire.advance(
        before, {"head": {"garments": [{"name": "a borrowed hood", "state": "worn"}]}})
    assert after["head"]["garments"][0]["name"] == "a borrowed hood"


# --- what is covered, and what is shown -------------------------------------

def test_covered_and_exposed_are_answerable_at_all():
    """The thing the flat list could not express: partial undress as state
    rather than as a sentence."""
    regions = attire.advance(
        attire.normalize_regions({"wearing": ["a robe", "boots"]}),
        {"torso": {"garments": [{"name": "a robe", "state": "removed"}]}},
        decisive=True)
    # A robe is not a torso garment that happens to be long: it covers the
    # torso, the waist, the groin and the legs, and taking it off uncovers
    # all four at once.
    assert attire.exposed_regions(regions) == ["torso", "waist", "groin", "legs"]
    assert attire.covered_regions(regions) == ["feet"]


def test_what_is_underneath_is_hidden_unless_asked_for():
    """Explicit body detail that travels in an exported card. Off by default,
    and the body's own description is what fills the gap."""
    regions = {"torso": {"garments": [], "beneath": "old scars across the ribs"}}
    quiet = attire.describe(regions, beneath_visible=False)
    assert quiet == ["torso: bare"]
    loud = attire.describe(regions, beneath_visible=True)
    assert "old scars across the ribs" in loud[0]


def test_the_body_description_fills_in_for_an_unauthored_region():
    """Nobody should have to fill seven fields before they can play."""
    regions = {"legs": {"garments": [], "beneath": ""}}
    out = attire.describe(regions, beneath_visible=True, body="long-limbed, pale")
    assert "long-limbed, pale" in out[0]


def test_a_partly_open_garment_says_so():
    regions = {"torso": {"garments": [{"name": "a robe", "state": "open"}]}}
    assert attire.describe(regions) == ["torso: a robe (open)"]


# --- the bridge to how the Director speaks ----------------------------------

class TestFlatChange:
    """The Director says "remove the sash", because whole garments are the
    shape a model reliably produces. That phrasing means "gone", which is
    exactly the instant undress this module exists to stop."""

    def test_a_removal_is_a_proposal_not_a_result(self):
        before = attire.normalize_regions({"wearing": ["silk sash", "a robe"]})
        after = attire.apply_flat_change(before, ["a robe"])
        sash = after["waist"]["garments"][0]
        assert sash["state"] == "loosened"
        # ...and it is therefore STILL BEING WORN. Dropping it from the list
        # the moment it was touched is how a half-undone robe became no robe.
        assert "silk sash" in attire.flat_wearing(after)

    def test_three_beats_to_take_something_off(self):
        regions = attire.normalize_regions({"wearing": ["silk sash"]})
        seen = []
        for _ in range(3):
            regions = attire.apply_flat_change(regions, [])
            seen.append(regions["waist"]["garments"][0]["state"])
        assert seen == ["loosened", "open", "removed"]
        assert attire.flat_wearing(regions) == []

    def test_a_decisive_player_gets_it_in_one(self):
        before = attire.normalize_regions({"wearing": ["silk sash"]})
        after = attire.apply_flat_change(before, [], decisive=True)
        assert after["waist"]["garments"][0]["state"] == "removed"
        assert attire.flat_wearing(after) == []

    def test_a_garment_still_listed_keeps_its_partial_state(self):
        """A beat that merely mentions the robe must not re-fasten it."""
        before = attire.apply_flat_change(
            attire.normalize_regions({"wearing": ["a robe"]}), [])
        after = attire.apply_flat_change(before, ["a robe"])
        assert after["torso"]["garments"][0]["state"] == "loosened"

    def test_putting_something_new_on_is_immediate(self):
        before = attire.normalize_regions({"wearing": ["a robe"]})
        after = attire.apply_flat_change(before, ["a robe", "heavy boots"])
        assert "heavy boots" in attire.flat_wearing(after)
        assert after["feet"]["garments"][0]["state"] == "worn"

    def test_the_derived_notes_say_what_the_free_text_used_to(self):
        regions = attire.apply_flat_change(
            attire.normalize_regions({"wearing": ["silk sash", "a robe"]}), [])
        notes = attire.flat_state(regions)
        assert any("sash loosened" in n for n in notes)
        assert any("robe loosened" in n for n in notes)

    def test_a_fully_bare_region_is_reported(self):
        regions = attire.apply_flat_change(
            attire.normalize_regions({"wearing": ["a robe"]}), [], decisive=True)
        notes = attire.flat_state(regions)
        assert any("bare at the torso, waist, groin, legs" in n for n in notes)


class TestAWholeOutfitWrite:
    """`{"wearing": [...]}` with no add/remove/replace — the shape
    director_establish sends. It used to skip reconciliation entirely, so it
    was the one way left to undress someone in a single beat."""

    def test_replacing_the_whole_list_still_takes_time(self):
        before = attire.normalize_regions({"wearing": ["silk sash", "a robe"]})
        after = attire.apply_flat_change(before, ["a robe"])
        assert after["waist"]["garments"][0]["state"] == "loosened"

    def test_an_opening_outfit_is_simply_worn(self):
        """Establishment is dressing, and dressing is never slowed down."""
        after = attire.apply_flat_change({}, ["a robe", "heavy boots"])
        assert sorted(attire.flat_wearing(after)) == ["a robe", "heavy boots"]
        assert after["feet"]["garments"][0]["state"] == "worn"


class TestWhatHappensToAGarment:
    """Someone spills wine on your shirt. That is a fact about the SHIRT --
    it outlives the beat, survives the shirt coming undone, and goes with the
    shirt when it comes off."""

    def _stained(self):
        regions = attire.normalize_regions({"wearing": ["a linen shirt"]})
        return attire.apply_flat_change(
            regions, ["a linen shirt"],
            conditions={"a linen shirt": "wine-stained down the front"})

    def test_a_garment_can_be_marked_without_being_removed(self):
        regions = self._stained()
        assert attire.condition_of(regions, "a linen shirt") == \
            "wine-stained down the front"
        assert attire.flat_wearing(regions) == ["a linen shirt"]

    def test_it_shows_beside_the_garment(self):
        assert attire.describe(self._stained()) == [
            "torso: a linen shirt (wine-stained down the front)"]

    def test_state_and_condition_are_different_questions(self):
        """How far off the body, versus what has happened to it. A shirt can be
        soaked and still fully worn; a dry one can be hanging open."""
        regions = attire.apply_flat_change(self._stained(), [])
        assert attire.describe(regions) == [
            "torso: a linen shirt (loosened, wine-stained down the front)"]

    def test_a_later_beat_that_says_nothing_does_not_launder_it(self):
        regions = self._stained()
        for _ in range(3):
            regions = attire.apply_flat_change(regions, ["a linen shirt"])
        assert attire.condition_of(regions, "a linen shirt") == \
            "wine-stained down the front"

    def test_a_later_beat_that_says_something_is_the_news(self):
        regions = attire.apply_flat_change(
            self._stained(), ["a linen shirt"],
            conditions={"a linen shirt": "scrubbed clean, still damp"})
        assert attire.condition_of(regions, "a linen shirt") == \
            "scrubbed clean, still damp"

    def test_it_survives_the_garment_coming_off(self):
        """The point of putting it on the garment: the stain must not stay on
        the person while a clean shirt lands on the floor."""
        regions = self._stained()
        for _ in range(3):
            regions = attire.apply_flat_change(regions, [])
        assert attire.exposed_regions(regions) == ["torso"]
        assert attire.condition_of(regions, "a linen shirt") == \
            "wine-stained down the front"

    def test_an_unmarked_garment_says_nothing(self):
        regions = attire.normalize_regions({"wearing": ["a linen shirt"]})
        assert attire.describe(regions) == ["torso: a linen shirt"]
        assert attire.condition_of(regions, "a linen shirt") == ""
        assert attire.condition_of(regions, "a coat nobody owns") == ""


class TestRemovedGarmentsBecomeThings:
    """A garment that leaves a body does not stop existing. It is on the floor
    or over a chair -- findable, takeable, and something the story can refer to
    later."""

    def test_the_beat_it_comes_off_is_reported_once(self):
        worn = attire.normalize_regions({"wearing": ["silk sash"]})
        loosened = attire.apply_flat_change(worn, [])
        assert attire.newly_removed(worn, loosened) == []
        opened = attire.apply_flat_change(loosened, [])
        off = attire.apply_flat_change(opened, [])
        assert attire.newly_removed(opened, off) == [("waist", "silk sash")]
        # ...and not again on every beat afterwards, or the room fills up with
        # copies of the same sash.
        still_off = attire.apply_flat_change(off, [])
        assert attire.newly_removed(off, still_off) == []

    def test_a_decisive_removal_reports_it_immediately(self):
        worn = attire.normalize_regions({"wearing": ["a robe", "heavy boots"]})
        after = attire.apply_flat_change(worn, [], decisive=True)
        # One entry per GARMENT, not per region it covered -- the robe spans
        # four, and four robes on the floor is not what came off.
        assert sorted(attire.newly_removed(worn, after)) == [
            ("feet", "heavy boots"), ("torso", "a robe")]


class TestAGarmentNameIsAHandleNotADescription:
    """Live failure, Tamamo's card: the generator wrote the whole description
    into `name`, and every garment came back cut at 116 characters mid-clause.

    Two costs, not one. The visible cost was the truncation. The invisible cost
    was that `name` is the MATCHING KEY -- the Director says "remove the
    kimono" and `decisive_targets` looks for a head noun -- and the head noun
    of "Ceremonial kimono - deep vermillion silk brocade, gold-thread motifs
    woven through the fabric in geometric" is "geometric".
    """

    FULL = ("Ceremonial kimono — deep vermillion silk brocade, gold-thread "
            "spiritual motifs woven through the fabric in geometric patterns "
            "of protection and station")

    def test_the_description_is_kept_not_cut_off(self):
        name, description = attire.split_garment_name(self.FULL)
        assert name == "Ceremonial kimono"
        assert description.endswith("protection and station")
        assert len(name) <= attire.GARMENT_NAME_LIMIT

    def test_it_splits_on_shape_not_only_on_length(self):
        """A hundred-character name is under the limit and still unmatchable."""
        name, description = attire.split_garment_name(
            "Tabi — white split-toed silk socks, fitted close")
        assert name == "Tabi"
        assert description == "white split-toed silk socks, fitted close"

    def test_a_hyphenated_garment_stays_one_thing(self):
        name, description = attire.split_garment_name("split-toed silk socks")
        assert name == "split-toed silk socks"
        assert description == ""

    def test_an_authored_description_is_not_overruled(self):
        name, description = attire.split_garment_name(
            self.FULL, description="what the author wrote")
        assert name == "Ceremonial kimono"
        assert description == "what the author wrote"

    def test_the_ledger_carries_both(self):
        regions = attire.normalize_regions({"wearing": [self.FULL]})
        garment = regions["torso"]["garments"][0]
        assert garment["name"] == "Ceremonial kimono"
        assert "vermillion" in garment["description"]
        # The flat list is the handle, because that is what gets matched.
        assert attire.flat_wearing(regions) == ["Ceremonial kimono"]

    def test_the_handle_is_what_the_story_matches_on(self):
        """The invisible half of the bug: with the description in the name,
        the head noun was "geometric" and nothing could refer to the kimono."""
        regions = attire.normalize_regions({"wearing": [self.FULL]})
        assert attire.decisive_targets(
            "", ["She tears the kimono open."],
            {"Tamamo": attire.flat_wearing(regions)}) == {"Tamamo"}

    def test_a_description_is_said_once_not_once_per_region(self):
        """A kimono covers five regions. Repeating 400 characters five times
        is a prompt cost paid for nothing."""
        regions = attire.normalize_regions({"wearing": [self.FULL]})
        lines = attire.describe(regions)
        assert sum("vermillion" in line for line in lines) == 1
        assert len(lines) == 5

    def test_a_description_survives_the_garment_coming_undone(self):
        regions = attire.normalize_regions({"wearing": [self.FULL]})
        after = attire.apply_flat_change(regions, ["Ceremonial kimono"])
        assert "vermillion" in after["torso"]["garments"][0]["description"]


class TestWornAtIsNotWornOver:
    """A ribbon does not cover a head; it sits in the hair. Without the
    distinction a woman in nothing but a hair ribbon has a covered head, and
    taking the ribbon off "uncovers" one."""

    def test_an_ornament_covers_nothing(self):
        regions = attire.normalize_regions({"wearing": ["a red silk ribbon"]})
        assert attire.covered_regions(regions) == []
        assert attire.exposed_regions(regions) == ["head"]

    def test_it_is_still_present_and_still_said(self):
        """Covering nothing is not the same as not being there."""
        regions = attire.normalize_regions({"wearing": ["a red silk ribbon"]})
        assert "a red silk ribbon" in attire.flat_wearing(regions)
        assert attire.describe(regions) == [
            "head: a red silk ribbon [worn at, covers nothing]"]

    def test_ornaments_land_somewhere_sensible(self):
        for name, region in (("a red silk ribbon", "head"),
                             ("a jade necklace", "torso"),
                             ("a signet ring", "hands"),
                             ("a silver anklet", "feet")):
            assert attire.region_of(name) == region, name
            assert attire.attaches_only(name), name

    def test_an_ornament_occupies_one_place_only(self):
        """A necklace is at the throat, not across everything it hangs near."""
        regions = attire.normalize_regions({"wearing": ["a jade necklace"]})
        assert list(regions) == ["torso"]

    def test_real_clothing_is_not_mistaken_for_an_ornament(self):
        for name in ("a woollen hat", "a hooded cloak", "embroidered gloves",
                     "a silk sash"):
            assert not attire.attaches_only(name), name

    def test_an_author_overrules_the_cue_table(self):
        regions = attire.normalize_regions({"regions": {"head": {"garments": [
            {"name": "a mourning band", "attaches": False}]}}})
        assert attire.covered_regions(regions) == ["head"]


class TestLayers:
    """Undergarments, as the generator wrote them for Tamamo: a nagajuban
    under a kimono, both real garments in one region."""

    def _dressed(self):
        return attire.normalize_regions({"regions": {"torso": {"garments": [
            {"name": "Ceremonial kimono", "auto": True},
            {"name": "Nagajuban", "covers": ["arms", "waist", "groin", "legs"]},
        ]}}})

    def test_what_is_underneath_is_marked_as_hidden(self):
        """Telling the Director an under-kimono is on show invites prose
        describing clothes nobody can see."""
        line = attire.describe(self._dressed())[0]
        assert "Nagajuban [under the above]" in line
        assert "Ceremonial kimono" in line

    def test_removing_the_outer_layer_does_not_bare_anyone(self):
        after = attire.apply_flat_change(
            self._dressed(), ["Nagajuban"], decisive=True)
        assert attire.exposed_regions(after) == []
        # ...and what was under is now what is on show.
        assert "[under the above]" not in attire.describe(after)[0]

    def test_removing_both_does(self):
        regions = self._dressed()
        after = attire.apply_flat_change(regions, [], decisive=True)
        assert attire.exposed_regions(after) == [
            "torso", "arms", "waist", "groin", "legs"]
