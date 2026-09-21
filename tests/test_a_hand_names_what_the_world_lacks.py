"""A hand that cannot find a thing must be able to say WHICH thing.

`director.mint_unreferenced_things` stands up a thing a beat acted on that the
world does not hold, and it reads the hands' own verdicts rather than prose.
But `settled` is keyed per thing ON THE ROW -- the owner's rule that the verdict
follows the thing -- and a row's thing is usually the acting body. So a hand
that could not resolve a target marked the PERSON `no_referent` and named the
target only in a note.

Measured, two_lives v5 (2026-09-19): 9 of 10 `no_referent` verdicts in the run
named "Emory Vane" or "Sal Weatherby", while the notes beside them named
"apron timber", "wheel shroud" and "brass collar seam". The mint refused every
one of them -- correctly, since standing furniture up wearing a person's name
is worse than the gap -- and so it fired ZERO times across sixty beats while a
millwright worked a sluice the engine did not model as a thing.

The specialist sheet already asked for this: "mark the unresolved item
no_referent and explain the missing referent". Nothing answered the second
half, because there was nowhere to put it but prose, and a mint may never be
built out of prose.
"""

from __future__ import annotations

from agents.director import mint_unreferenced_things

SCENE = {"rooms": {"mill_race": {"name": "Mill Race"}},
         "positions": {"Emory Vane": "mill_race"},
         "entities": {}}


def _out(**result):
    row = {"status": "no_referent", "settled": {}, "missing_referents": []}
    row.update(result)
    return {"ledgers": [{"object_name": "Emory Vane",
                         "source_entity_id": "character:2",
                         "item_names": ["Emory Vane"]}],
            "orchestration": {"specialists": {"contact": {"results": [row]}}}}


class TestTheHandNamesTheThingAndTheThingIsMinted:
    def test_the_v5_case_now_mints(self):
        """The whole measured failure, in one call: the verdict names the
        body, the missing referents name the timber."""
        diff = {}
        minted = mint_unreferenced_things(
            _out(settled={"Emory Vane": "no_referent"},
                 missing_referents=["apron timber", "wheel shroud"]),
            SCENE, diff, "mill_race")
        assert minted == ["apron_timber", "wheel_shroud"]
        assert diff["entities"]["apron_timber"]["name"] == "apron timber"
        assert diff["positions"]["wheel_shroud"] == "mill_race"

    def test_the_old_channel_still_works(self):
        """A hand that names the thing in `settled` -- which is correct when
        the row's own thing is the thing -- keeps minting as it did."""
        diff = {}
        assert mint_unreferenced_things(
            _out(settled={"brass collar seam": "no_referent"}),
            SCENE, diff, "mill_race") == ["brass_collar_seam"]

    def test_a_person_is_still_never_furniture(self):
        """The refusal that made the old channel useless is the same refusal
        that keeps it honest, and it applies to the new one too."""
        diff = {}
        assert mint_unreferenced_things(
            _out(missing_referents=["Emory Vane"]),
            SCENE, diff, "mill_race") == []

    def test_a_description_is_not_a_name(self):
        diff = {}
        assert mint_unreferenced_things(
            _out(missing_referents=[
                "the heavy timber balks and framing lining the sluice channel"]),
            SCENE, diff, "mill_race") == []

    def test_a_thing_the_world_already_holds_is_not_doubled(self):
        scene = dict(SCENE, entities={"apron": {"name": "apron timber"}})
        diff = {}
        assert mint_unreferenced_things(
            _out(missing_referents=["apron timber"]),
            scene, diff, "mill_race") == []

    def test_a_thing_THIS_BEAT_already_stood_up_is_not_doubled_either(self):
        """The same refusal, one beat later, and the half it was missing.

        `held` was built from the SCENE -- the world before this beat -- while
        the hand that OWNS a thing's record mints it into this beat's diff. So
        a thing the objects hand established a moment ago was unknown here and
        a sibling hand reporting it missing got a second copy.

        Measured, two_lives v13 turn 8 (2026-09-20): the objects hand minted
        `copper_coin` with a kind, a description, an alias and `portable`; this
        function minted the coin AGAIN off a `missing_referents` line; the
        key-collision guard renamed the duplicate `copper_coin_2`; and the
        taproom carried two coins for one. It was invisible for as long as
        things in a room were invisible to everyone, and the beat things became
        visible the view said "There is the copper coin here" twice.
        """
        diff = {"entities": {"copper_coin": {
            "name": "copper coin", "kind": "coin", "aliases": ["coin"],
            "description": "A flat copper coin.", "portable": True}},
            "positions": {"copper_coin": "mill_race"}}
        assert mint_unreferenced_things(
            _out(missing_referents=["copper coin"]),
            SCENE, diff, "mill_race") == []
        assert list(diff["entities"]) == ["copper_coin"]

    def test_it_is_the_name_that_collides_not_only_the_key(self):
        """An alias or a different key spelling is the same thing, which is
        what the refusal has always said ("under any spelling, alias or
        position key") and what makes this a resolution failure rather than a
        gap in the world."""
        for established in ({"entities": {"coin_1": {"name": "copper coin"}}},
                            {"entities": {"c": {"aliases": ["copper coin"]}}},
                            {"positions": {"copper coin": "mill_race"}}):
            assert mint_unreferenced_things(
                _out(missing_referents=["copper coin"]),
                SCENE, dict(established), "mill_race") == [], established


class TestTheContractIsPublished:
    def test_every_hand_is_taught_the_field_and_prints_it(self):
        """Both halves, in both packs: a field taught in prose and left out of
        the printed envelope is a field no model ever sends (the `still_owes`
        defect, 2026-09-19)."""
        from llm import prompts

        for pack in ("en", "ja"):
            for hand in ("body", "social", "contact", "objects", "spatial"):
                card = prompts.language_pack(pack).card("system_prompts")
                text = card["specialists"][hand]["core"]
                assert text.count("missing_referents") >= 2, (pack, hand)

    def test_the_schema_carries_it(self):
        from llm import schemas

        fields = (getattr(schemas.LedgerTransformResult, "model_fields", None)
                  or schemas.LedgerTransformResult.__fields__)
        assert "missing_referents" in fields
