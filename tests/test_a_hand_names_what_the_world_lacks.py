"""A model that cannot find a thing must be able to say WHICH thing.

`director.mint_unreferenced_things` stood up a thing a beat acted on that the
world did not hold, and it read the hands' own verdicts rather than prose.
But `settled` was keyed per thing ON THE ROW -- the owner's rule that the
verdict follows the thing -- and a row's thing is usually the acting body. So
a hand that could not resolve a target marked the PERSON `no_referent` and
named the target only in a note.

Measured, two_lives v5 (2026-09-19): 9 of 10 `no_referent` verdicts in the run
named "Emory Vane" or "Sal Weatherby", while the notes beside them named
"apron timber", "wheel shroud" and "brass collar seam". The mint refused every
one of them -- correctly, since standing furniture up wearing a person's name
is worse than the gap -- and so it fired ZERO times across sixty beats while a
millwright worked a sluice the engine did not model as a thing.

The mint and its tests went with the causal hands on 2026-09-27. What stands
is the field: the encoder names a thing the prose needs and the world lacks in
`missing_referents`, by the words the prose used, and code answers by granting
`entities`, `positions` and the `entities__new` part and asking again
(`director_prose.encode`). A mint may still never be built out of prose.
"""

from __future__ import annotations


class TestTheContractIsPublished:
    def test_every_hand_is_taught_the_field_and_prints_it(self):
        """Both halves, in both packs: a field taught in prose and left out of
        the printed envelope is a field no model ever sends (the `still_owes`
        defect, 2026-09-19). Each hand's core until 2026-09-27; the encoder's
        core since, which ships on every beat."""
        from llm import prompts

        for pack in ("en", "ja"):
            card = prompts.language_pack(pack).card("system_prompts")
            assert card["encoder"]["core"].count("missing_referents") >= 2, pack

    def test_the_schema_carries_it(self):
        from llm import schemas

        # The encoder's answer since 2026-09-27; a hand's positional result
        # (`LedgerTransformResult`) before.
        fields = (getattr(schemas.UnifiedSpecialistOutput, "model_fields", None)
                  or schemas.UnifiedSpecialistOutput.__fields__)
        assert "missing_referents" in fields
