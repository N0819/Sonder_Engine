"""Replacement: what a garment put on in another's PLACE turns out.

A third question beside the two `test_attire_displacement.py` pins. That
file asks what a still-worn garment no longer covers; this one asks what
leaves the body when something arrives where it was.

Found by playing (flat run, PE4, turn 11): out of the shower, the body hand
wrote `{"add": ["big blue bath towel"], "remove": []}` and the committed
ledger read `scrubs top, lanyard, jumper, towel, scrubs trousers, socks` --
a woman who had just showered, in a towel over a jumper over scrubs, with no
warning anywhere. An addition alone can only ever add.

The rule pinned here, and the two halves of it that matter:

  * layering stays the DEFAULT -- the ledger cannot tell a coat over a
    jumper from a towel instead of one, so it never guesses; a replacement
    happens only where the caller says one did (`displaces`);
  * a displaced garment COMES OFF rather than disappearing -- it reaches
    `removed` like any other departure, so `newly_removed` reports it and
    the commit path can mint it as a thing in the room.
"""

from __future__ import annotations

from story import attire


def _showered():
    """The flat run's turn-11 body, before the towel."""
    return attire.normalize_regions({"wearing": [
        "teal hospital scrubs top", "grey jumper",
        "teal hospital scrubs trousers", "black socks"]})


def _names(regions):
    return {region: [g["name"] for g in (entry.get("garments") or [])
                     if g.get("state") != "removed"]
            for region, entry in regions.items()}


class TestWhatAGarmentTakesThePlaceOf:

    def test_the_towel_takes_the_torso_and_leaves_the_legs_and_feet(self):
        taken = attire.displaced_by(_showered(), "big blue bath towel")
        assert taken == ["teal hospital scrubs top", "grey jumper"]

    def test_the_place_a_garment_holds_is_its_anchor_not_its_whole_span(self):
        """The jumper reaches the arms and the waist and is still a torso
        garment. A rule that asked the towel to cover a sleeve first would
        answer "nothing was displaced" for every replacement anyone writes."""
        jumper = attire.regions_covered("grey jumper")
        assert "arms" in jumper and "torso" in jumper
        assert "grey jumper" in attire.displaced_by(
            _showered(), "big blue bath towel")

    def test_something_that_only_attaches_is_in_nothing_s_way(self):
        regions = attire.normalize_regions({"wearing": ["silver hair clip"]})
        assert attire.attaches_only("silver hair clip")
        assert attire.displaced_by(regions, "wide straw hat") == []

    def test_a_garment_already_off_the_body_cannot_come_off_again(self):
        regions = attire.apply_flat_change(_showered(), [
            "grey jumper", "teal hospital scrubs trousers", "black socks"])
        assert "teal hospital scrubs top" not in attire.displaced_by(
            regions, "big blue bath towel")

    def test_a_garment_covering_nothing_holds_no_place_to_take(self):
        """Trousers at the ankles are worn, cover nothing, and are left where
        the coverage axis put them -- the safe direction, since wrongly
        keeping a garment on is recoverable and wrongly shedding one is not."""
        regions, _notes = attire.apply_coverage_changes(
            _showered(), {"teal hospital scrubs trousers":
                          {"legs": [], "groin": []}})
        assert attire.displaced_by(regions, "loose linen trousers") == []

    def test_a_declared_placement_beats_the_name_table(self):
        regions = _showered()
        assert attire.displaced_by(
            regions, "long silk scarf",
            placement={"long silk scarf": ("legs",)}) == [
                "teal hospital scrubs trousers"]


class TestDressingIsAChangeOfState:

    def test_the_displaced_garment_comes_off_and_does_not_vanish(self):
        previous = _showered()
        # The shape a commit path holds: the previous list with the addition
        # appended, which on its own is an accumulation.
        wanted = attire.flat_wearing(previous) + ["big blue bath towel"]
        after = attire.apply_flat_change(
            previous, wanted, displaces=["big blue bath towel"])
        assert attire.flat_wearing(after) == [
            "big blue bath towel", "teal hospital scrubs trousers",
            "black socks"]
        assert [name for _region, name in
                attire.newly_removed(previous, after)] == [
            "teal hospital scrubs top", "grey jumper"]

    def test_a_displaced_garment_is_still_in_the_ledger_as_removed(self):
        previous = _showered()
        after = attire.apply_flat_change(
            previous, attire.flat_wearing(previous) + ["big blue bath towel"],
            displaces=["big blue bath towel"])
        states = {g["name"]: g["state"]
                  for entry in after.values()
                  for g in entry.get("garments") or []}
        assert states["grey jumper"] == "removed"
        assert states["big blue bath towel"] == "worn"

    def test_adding_without_saying_it_replaces_anything_still_layers(self):
        """The default, and deliberately: a coat over a jumper and a towel
        instead of one occupy the same regions, and only the beat's words
        separate them, so the ledger never guesses."""
        previous = _showered()
        after = attire.apply_flat_change(
            previous, attire.flat_wearing(previous) + ["wool coat"])
        assert attire.flat_wearing(after) == [
            "teal hospital scrubs top", "grey jumper", "wool coat",
            "teal hospital scrubs trousers", "black socks"]
        assert attire.newly_removed(previous, after) == []

    def test_a_garment_sharing_no_place_leaves_the_ledger_untouched(self):
        previous = _showered()
        after = attire.apply_flat_change(
            previous, attire.flat_wearing(previous) + ["leather ankle boots"],
            displaces=["leather ankle boots"])
        assert attire.newly_removed(previous, after) == [
            ("feet", "black socks")]
        assert _names(after)["torso"] == [
            "teal hospital scrubs top", "grey jumper"]

    def test_the_caller_may_name_what_came_off_itself(self):
        previous = _showered()
        after = attire.apply_flat_change(
            previous, attire.flat_wearing(previous) + ["big blue bath towel"],
            displaces={"big blue bath towel": ["jumper"]})
        assert [name for _region, name in
                attire.newly_removed(previous, after)] == ["grey jumper"]

    def test_a_declared_replacement_beats_a_wanted_list_that_still_holds_it(
            self):
        """The accumulating caller states what it believed a moment ago; the
        displacement is this beat's news about the same body."""
        previous = _showered()
        after = attire.apply_flat_change(
            previous, ["grey jumper", "big blue bath towel"],
            displaces=["big blue bath towel"])
        assert "grey jumper" not in attire.flat_wearing(after)

    def test_nothing_displaces_itself(self):
        previous = _showered()
        after = attire.apply_flat_change(
            previous, attire.flat_wearing(previous),
            displaces=["grey jumper"])
        assert "grey jumper" in attire.flat_wearing(after)


class TestTheThreeDomainsStayDistinct:
    """Stable appearance, the authored starting outfit, and the mutable story
    ledger are three things (CLAUDE.md). Replacement is an act on the third."""

    def test_replacement_touches_neither_the_card_nor_the_body(self):
        card = {"embodiment": {"visible": {"summary": "a tall woman"}},
                "initial_outfit": ["teal hospital scrubs top", "grey jumper",
                                   "teal hospital scrubs trousers",
                                   "black socks"]}
        previous = attire.normalize_regions(
            {"wearing": list(card["initial_outfit"])})
        after = attire.apply_flat_change(
            previous, attire.flat_wearing(previous) + ["big blue bath towel"],
            displaces=["big blue bath towel"])
        assert card["initial_outfit"] == [
            "teal hospital scrubs top", "grey jumper",
            "teal hospital scrubs trousers", "black socks"]
        assert card["embodiment"]["visible"]["summary"] == "a tall woman"
        assert attire.flat_wearing(previous) == card["initial_outfit"]
        assert "grey jumper" not in attire.flat_wearing(after)

    def test_a_displaced_garment_leaves_by_the_ordinary_door(self):
        """It reaches `removed` like any other departure, so the seam that
        mints shed clothing and prunes the ledger needs no second path -- and
        the region it vacated is not recorded as bared, because the garment
        that took its place is covering it."""
        previous = attire.normalize_regions({"regions": {"torso": {
            "beneath": "a long scar under the collarbone",
            "garments": [{"name": "grey jumper"}]}}})
        after = attire.apply_flat_change(
            previous, ["grey jumper", "big blue bath towel"],
            displaces=["big blue bath towel"])
        assert attire.newly_removed(previous, after) == [
            ("torso", "grey jumper")]
        entry = attire.release_removed_garments({"regions": after})
        assert [g["name"] for g in entry["regions"]["torso"]["garments"]] == [
            "big blue bath towel"]
        assert entry["regions"]["torso"].get("uncovered") is not True
