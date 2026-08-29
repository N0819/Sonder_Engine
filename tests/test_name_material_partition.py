"""Material names nobody: the partition, held at the fragment.

`refuse_harvested_material` empties a generated law's name POOLS because a
pool is a list of whole name elements and the elements are the story's own
people. Its fragments were kept on the premise that "a fragment names nobody
however well a model knows a canon". That premise is false, and this file is
the measurement that says so.

Measured 2026-08-28 across three consecutive generations of one institution
whose lore carried a large named cast. Generation A and generation C supplied
`family_parts.starts` that were, entry for entry, the openings of the cast's
own surnames -- generation C's list was 100% cast-derived and included one
element belonging to a character REGISTERED IN THAT CHAT. Nothing
reconstructed a whole name (the novelty floor holds), yet the material was
the cast, cut up, and one body still came out wearing a registered person's
surname exactly. Generation B supplied ordinary fragments that touched
nobody, so this is variance in what a model volunteers, not a constant --
which is precisely why the guard cannot be the model.

The rule these tests pin, in engine vocabulary and naming no setting:

- A fragment that is an ELEMENT of a name the story gives to somebody is not
  material. An element is anchored: it opens or closes that name, or that
  name opens or closes it. The middle is excluded for the reason
  `_reserves_component` already excludes it.
- One letter is the alphabet. Two that open or close somebody's name are a
  piece of that name.
- **Refusal may empty a bucket; it may not leave one empty.** A guard that
  turns a naming defect into a generation failure is not an improvement, so
  every refusal here is paired with the material that replaces it: the law's
  own surviving fragments first, then the words the setting uses for PLACES
  AND INSTITUTIONS, which belong to its sound system and to nobody.
"""

from __future__ import annotations

import pytest

from world.charter_generate import close_plan
from world.charter_identity import (
    fragment_is_name_element,
    identity_reservation,
    materialize_body_names,
    naming_material_exists,
    refuse_harvested_material,
    reserved_name_elements,
    vocabulary_name_parts,
)

# The measured generation, transcribed. No setting is named here and none is
# needed: what matters is that every family opening is the opening of a name
# the story gives to somebody, which is a property of the pair, not of a
# franchise.
CAST = [
    "Jean-Luc Picard", "William Riker", "Beverly Crusher", "Deanna Troi",
    "Geordi La Forge", "Data", "Worf", "Tasha Yar", "Miles O'Brien",
]

GEN_C = {
    "given_parts": {
        "starts": ["Wil", "Aly", "Roe", "Dav", "Bev", "Geo", "Dea", "Jean"],
        "middles": [], "ends": ["era", "oly", "rson", "lison"]},
    "family_parts": {
        "starts": ["Rik", "La", "For", "Tro", "Ob", "Brien", "Crush", "Yar",
                   "Forge"],
        "middles": [], "ends": ["ison", "ardez", "geez", "er"]},
    "name_format": "{given} {family}",
}

# The same institution's OTHER generation: ordinary fragments belonging to
# nobody in the story. Nothing here may be taken away.
GEN_B = {
    "given_parts": {"starts": ["Sm", "Joh", "Ad", "Car", "Ed", "Fra", "Gre"],
                    "middles": [], "ends": ["ith", "nson", "ams", "ter"]},
    "family_parts": {"starts": ["Mor", "Kel", "Hend", "Ryn", "Vas"],
                     "middles": [], "ends": ["ley", "don", "stad", "queth"]},
    "name_format": "{given} {family}",
}

# Words the setting uses for places and institutions. A place is not a
# person, so cutting one up cannot issue anybody's name.
PLACE_WORDS = ["Ashlow Terminus", "The Copper Cistern", "Marrowgate",
               "Lantern Quarter", "Verdigris Hall"]


def _reservation(law=GEN_C):
    return identity_reservation(CAST, law)


def _elements():
    return reserved_name_elements(_reservation())


def _components(bodies):
    out = set()
    for body in bodies.values():
        for key in ("given_name", "family_name"):
            value = str(body.get(key) or "").strip()
            if value:
                out.add(value.casefold())
    return out


# ---------------------------------------------------------------------------
# the rule
# ---------------------------------------------------------------------------

class TestAFragmentIsMaterialOnlyWhenItNamesNobody:
    def test_a_fragment_that_opens_a_reserved_name_is_not_material(self):
        elements = _elements()
        for fragment in ("Rik", "Tro", "Crush", "Ob", "Wil", "Bev", "Dea"):
            assert fragment_is_name_element(fragment, elements), fragment

    def test_a_fragment_that_closes_a_reserved_name_is_not_material(self):
        elements = _elements()
        for fragment in ("Brien", "er", "card", "sher"):
            assert fragment_is_name_element(fragment, elements), fragment

    def test_a_fragment_that_is_a_whole_reserved_token_is_not_material(self):
        elements = _elements()
        assert fragment_is_name_element("Yar", elements)
        assert fragment_is_name_element("Forge", elements)
        assert fragment_is_name_element("La", elements)

    def test_a_reserved_token_opening_a_longer_fragment_is_not_material(self):
        """Anchored in both directions. A fragment that carries a whole name
        at its head is that name with a suffix stapled on."""
        assert fragment_is_name_element("Rikerson", _elements())

    def test_a_run_buried_mid_fragment_is_not_an_element(self):
        """The same exclusion `_reserves_component` already holds: what a
        person is called by is the head and the tail of their name."""
        assert not fragment_is_name_element("zatroix", _elements())

    def test_one_letter_is_the_alphabet(self):
        """Refusing a single letter would take the alphabet away from the
        law -- every name a story ever wrote starts with one."""
        assert not fragment_is_name_element("D", _elements())
        assert not fragment_is_name_element("W", _elements())

    def test_material_the_reservation_does_not_reach_survives_whole(self):
        law = refuse_harvested_material(GEN_B, _reservation(GEN_B))
        assert law["given_parts"]["starts"] == GEN_B["given_parts"]["starts"]
        assert law["given_parts"]["ends"] == GEN_B["given_parts"]["ends"]
        assert law["family_parts"]["starts"] == GEN_B["family_parts"]["starts"]
        assert law["family_parts"]["ends"] == GEN_B["family_parts"]["ends"]

    def test_no_reservation_takes_nothing(self):
        law = refuse_harvested_material(GEN_C, identity_reservation([]))
        assert law["family_parts"]["starts"] == GEN_C["family_parts"]["starts"]


# ---------------------------------------------------------------------------
# the refusal, on the measured law
# ---------------------------------------------------------------------------

class TestTheMeasuredLawStopsBeingTheCastCutUp:
    def test_the_pools_are_still_refused(self):
        law = refuse_harvested_material(
            dict(GEN_C, given=["Aly"], family=["Ryn"]), _reservation())
        assert law["given"] == []
        assert law["family"] == []

    def test_every_cast_derived_opening_is_gone(self):
        law = refuse_harvested_material(GEN_C, _reservation())
        elements = _elements()
        for field in ("given_parts", "family_parts"):
            for bucket in ("starts", "middles", "ends"):
                for value in law[field][bucket]:
                    assert not fragment_is_name_element(value, elements), value

    def test_the_law_still_has_material(self):
        """THE STARVATION BAR. Every family opening in this law is cast
        derived, so a refusal alone leaves the law with nothing and turns a
        naming defect into a generation failure."""
        law = refuse_harvested_material(GEN_C, _reservation())
        assert naming_material_exists(law)
        assert law["family_parts"]["starts"]
        assert law["family_parts"]["ends"]

    def test_no_minted_body_wears_a_reserved_element(self):
        law = refuse_harvested_material(GEN_C, _reservation())
        bodies = materialize_body_names(
            "works", {"post:%04d" % i: {} for i in range(24)},
            law, _reservation())
        elements = _elements()
        assert all(str(b.get("name") or "").strip() for b in bodies.values())
        for component in _components(bodies):
            assert component not in elements, component

    def test_the_measured_body_that_wore_a_registered_surname_is_gone(self):
        """`Rik` + `er` assembled a registered character's surname exactly,
        and every guard passed it: the novelty floor permits an exact share
        on purpose, and the element rule only fires where the law addresses
        people by one component. Neither was wrong; the MATERIAL was."""
        law = refuse_harvested_material(GEN_C, _reservation())
        bodies = materialize_body_names(
            "works", {"post:%04d" % i: {} for i in range(24)},
            law, _reservation())
        families = {str(b.get("family_name") or "").casefold()
                    for b in bodies.values()}
        assert "riker" not in families
        assert "crusher" not in families


# ---------------------------------------------------------------------------
# and then what does the mint read
# ---------------------------------------------------------------------------

class TestRefusalMayEmptyABucketButNotLeaveOneEmpty:
    def test_a_field_that_lost_its_openings_borrows_the_law_s_own(self):
        """A start is a start. The law's other field is the same law's
        phonology, so borrowing invents no culture."""
        law = refuse_harvested_material(GEN_C, _reservation())
        assert set(law["family_parts"]["starts"]) \
            >= set(law["given_parts"]["starts"])

    def test_the_setting_s_place_words_are_material(self):
        """A place is not a person."""
        parts = vocabulary_name_parts(PLACE_WORDS, _reservation())
        assert parts["starts"] and parts["ends"]

    def test_a_place_named_after_a_person_contributes_nothing_of_them(self):
        reservation = _reservation()
        parts = vocabulary_name_parts(["Picard Hall", "Riker Terminus"],
                                      reservation)
        elements = reserved_name_elements(reservation)
        for bucket in ("starts", "middles", "ends"):
            for value in parts[bucket]:
                assert not fragment_is_name_element(value, elements), value

    def test_a_law_whose_every_fragment_is_reserved_still_names_everybody(self):
        """The hard case: nothing of the planner's material survives, so the
        setting's own place words are all that is left. A generation that
        cannot name its residents fails loudly (`_plan_lived_location`), and
        this is the test that says it does not have to."""
        wholly_reserved = {
            "given_parts": {"starts": ["Bev", "Dea", "Geo"], "middles": [],
                            "ends": ["card", "sher", "erly"]},
            "family_parts": {"starts": ["Rik", "Tro"], "middles": [],
                             "ends": ["ker", "roi"]},
            "name_format": "{given} {family}",
        }
        law = refuse_harvested_material(
            wholly_reserved, _reservation(), PLACE_WORDS)
        assert naming_material_exists(law)
        bodies = materialize_body_names(
            "works", {"post:%04d" % i: {} for i in range(12)},
            law, _reservation())
        assert all(str(b.get("name") or "").strip() for b in bodies.values())


# ---------------------------------------------------------------------------
# the generation path
# ---------------------------------------------------------------------------

def _plan(law):
    return {
        "name": "Ashlow Terminus",
        "structure": {"key": "terminus", "max_planned": 8, "grammar": []},
        "rooms": {"cistern": {"name": "The Copper Cistern", "purpose": "work",
                              "adjacent": [], "frontier": []},
                  "quarter": {"name": "Lantern Quarter", "purpose": "rest",
                              "adjacent": [], "frontier": []}},
        "charters": [{
            "key": "works", "name": "Verdigris Hall", "naming": law,
            "posts": {"hand": {"place": "cistern", "serves": [],
                               "requires": {}}},
            "populations": [{"post": "hand", "count": 18,
                             "competence": {}, "berth": "cistern"}],
        }],
    }


class TestGenerationDrawsFromMaterialAndNotFromTheCast:
    def test_the_persisted_law_carries_no_cast_derived_fragment(self):
        town = close_plan(_plan(GEN_C), reservation=_reservation())
        law = town["charters"]["works"]["naming"]
        elements = _elements()
        for field in ("given_parts", "family_parts"):
            for bucket in ("starts", "middles", "ends"):
                for value in law[field][bucket]:
                    assert not fragment_is_name_element(value, elements), value

    def test_every_generated_body_is_named(self):
        town = close_plan(_plan(GEN_C), reservation=_reservation())
        bodies = town["charters"]["works"]["bodies"]
        assert bodies
        for key, body in bodies.items():
            assert str(body.get("name") or "").strip()
            assert str(body.get("name") or "").strip() != key

    def test_no_generated_body_wears_a_reserved_element(self):
        town = close_plan(_plan(GEN_C), reservation=_reservation())
        elements = _elements()
        for component in _components(town["charters"]["works"]["bodies"]):
            assert component not in elements, component


class TestAPoolIsTheLastResortAndNoLongerTheFirst:
    """A DELIBERATE BEHAVIOUR CHANGE, pinned here so it is not mistaken for
    drift. `refuse_harvested_pools` kept a law's pools whenever it carried no
    fragments -- a bridge whose own comment said it existed only because
    nothing else could name anybody yet, and that it should go when something
    could. Something can: the setting's own place words. A model's list of
    people is now reached for only when there is nothing else at all.
    """

    POOLED = {"given": ["Wren", "Talis", "Oren"],
              "family": ["Halloway", "Ardent"],
              "name_format": "{given} {family}"}

    def test_place_words_displace_the_pool(self):
        law = refuse_harvested_material(self.POOLED, _reservation(),
                                        PLACE_WORDS)
        assert law["given"] == []
        assert law["family"] == []
        assert naming_material_exists(law)

    def test_a_setting_whose_places_do_not_split_keeps_the_pool(self):
        """The promise that no story which generated yesterday fails today.
        A single-syllable room name contributes nothing, so a law with no
        fragments and no splittable vocabulary is exactly where it was."""
        law = refuse_harvested_material(self.POOLED, _reservation(),
                                        ["Hall", "Bay", "Deck"])
        assert law["given"] == self.POOLED["given"]
        assert law["family"] == self.POOLED["family"]

    def test_no_vocabulary_at_all_keeps_the_pool(self):
        law = refuse_harvested_material(self.POOLED, _reservation())
        assert law["given"] == self.POOLED["given"]
