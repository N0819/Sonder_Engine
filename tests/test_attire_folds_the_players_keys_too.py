"""The player is a body with a wardrobe, and their attire keys must fold too.

`_heal_attire_identity_keys` collapses every scene key a body answers to onto
one record, because every reader of attire (`scene.appearance_of`,
`agents/character.py`, the attire panel) looks under one spelling and a second
record is invisible to all of them. It built its policy from the CAST alone --
`cast_spelling_policy(cast)` with no `player_name` -- so the one body that is
never in the cast was the one body whose records could not fold.

Measured in chat 77 ("The Doctor — Hinami new"): the persona held two attire
records at once, `hinami` (the scene's entity id) and `Hinami` (the persona's
own spelling), and they drifted apart -- one read "bare at the head", the other
carried a full displaced wardrobe. Which one a reader got depended on which
spelling it asked with.

This is the same two-callers-disagree defect `cast_spelling_policy`'s docstring
records from chat 82, in the axis that fix did not reach:
`canonicalize_positions` passes `player_name` and has always passed it; this
side did not.
"""

from __future__ import annotations

import json

import pytest


CAST = [{"id": 1, "name": "The Doctor",
         "sheet": json.dumps({"identity": {"name": "The Doctor",
                                           "aliases": []}})}]


class TestThePlayersOwnKeysFold:
    def test_an_entity_keyed_persona_folds_onto_the_persona_spelling(self):
        """The live shape: the scene mints the persona's entity as a lowercase
        slug, the Director keys a later change by the persona's name, and both
        records stay live."""
        from persist import commit

        scene = {"attire": {
            "hinami": {"wearing": ["a fitted tank top"], "state": []},
            "Hinami": {"wearing": [], "state": ["bare at the head"]}}}

        commit._heal_attire_identity_keys(scene, CAST, "Hinami")

        assert list(scene["attire"]) == ["Hinami"]
        assert scene["attire"]["Hinami"]["wearing"] == ["a fitted tank top"]

    def test_the_canonicalizer_answers_for_the_player(self):
        from persist import commit

        canonical = commit._heal_attire_identity_keys({}, CAST, "Hinami")

        assert canonical("hinami") == "Hinami"
        assert canonical("Hinami") == "Hinami"

    def test_without_a_player_name_nothing_about_the_cast_changes(self):
        """The argument is additive. A story with no persona, and every
        existing caller that passes nothing, must behave exactly as before."""
        from persist import commit

        canonical = commit._heal_attire_identity_keys({}, CAST)

        assert canonical("The Doctor") == "The Doctor"
        assert canonical("hinami") == "hinami"

    def test_the_player_never_swallows_a_cast_member(self):
        """The folding guards still apply to the player: a persona whose name
        somebody else already answers to must not collect their wardrobe.
        Folding two bodies into one is strictly worse than two spellings of
        one -- `cast_spelling_policy`'s ambiguity rule, which the player must
        not be an exception to."""
        from persist import commit

        cast = [{"id": 1, "name": "Hinami",
                 "sheet": json.dumps({"identity": {"name": "Hinami",
                                                   "aliases": []}})}]
        scene = {"attire": {
            "Hinami": {"wearing": ["a fitted tank top"], "state": []}}}

        commit._heal_attire_identity_keys(scene, cast, "Hinami")

        assert scene["attire"]["Hinami"]["wearing"] == ["a fitted tank top"]

    def test_an_unregistered_body_is_still_left_alone(self):
        """Objects, fixtures and background presences are not cast and are
        never rewritten -- the rule the healer has always kept."""
        from persist import commit

        scene = {"attire": {
            "a coat rack": {"wearing": ["a long brown coat"], "state": []}}}

        commit._heal_attire_identity_keys(scene, CAST, "Hinami")

        assert list(scene["attire"]) == ["a coat rack"]


class TestTheCommitSeamPassesItThrough:
    def test_the_call_site_hands_over_the_player_name(self):
        """A defaulted argument nobody passes is a fix that does not run.

        Asserted against the source rather than by driving a whole turn: this
        is one call site, and what can regress is somebody dropping the
        argument, not the pipeline around it.
        """
        import inspect

        from persist import commit_attire

        source = inspect.getsource(commit_attire)
        call = source[source.index("canonical_attire_key = "):]
        call = call[:call.index("\n\n")]

        assert "_player_name_or_none(ctx)" in call
