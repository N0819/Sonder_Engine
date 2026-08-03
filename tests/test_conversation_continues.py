"""A nod does not end the beat.

`_requires_director_resolution` ends the BEAT in `interaction_loop`, so its bar
should be "nobody can sensibly respond until the world says what happened". It
was instead "this act involves another person" — any action with a non-empty
`targets` list.

In a conversation, every piece of ordinary body language is aimed at whoever
you are talking to. Live, chat 38 t144–t147: the player deliberately stayed
silent for four consecutive turns to let two characters talk to each other, and
every one of those turns ended after a single exchange, on:

    "stand attentively with hands clasped, offering a small nod of
     acknowledgment to Tamamo"                       targets=['Tamamo']
    "pivots one golden ear toward the Doctor"        targets=['The Doctor']
    "shifts gaze fully to the Doctor"                targets=['The Doctor']
    "remains motionless with steady gaze on Tamamo"  targets=['Tamamo']

Nobody can contest a nod. Corpus-wide, **1002 of 1439 character-declared
actions were asserted, immediate and targeted** — 70% of everything a character
does was ending the beat.

`commitment` is the Director's own answer to the question and it separates the
two cleanly: `contestable` reads "Tightens grip on the caught prey's shoulder,
wrenching upward", "Closes the 1.5-meter gap in two quick steps"; `asserted`
reads "nods once slowly". Only 82 of the 1439 are contestable. Re-classifying
against the stored corpus frees 858 declarations and keeps 177 gating.
"""

from __future__ import annotations

from agents.common import _requires_director_resolution as needs_resolution


def _act(**kw):
    action = {"type": "action", "attempt": "", "targets": [],
              "commitment": "asserted", "visibility": "overt", "stage": "immediate"}
    action.update(kw)
    return {"sequence": [action]}


class TestTheLiveFailure:
    """All four verbatim from chat 38 t144-t147, with the Director's own
    metadata as recorded."""

    def test_a_nod_of_acknowledgment_does_not_end_the_beat(self):
        assert not needs_resolution(_act(
            attempt="stand attentively with hands clasped, offering a small "
                    "nod of acknowledgment to Tamamo",
            targets=["Tamamo"]))

    def test_an_ear_turning_does_not_end_the_beat(self):
        assert not needs_resolution(_act(
            attempt="pivots one golden ear toward the Doctor while letting a "
                    "single tail curl slowly behind her in thought",
            targets=["The Doctor"]))

    def test_a_gaze_does_not_end_the_beat(self):
        assert not needs_resolution(_act(
            attempt="shifts gaze fully to the Doctor while one golden tail "
                    "settles into a slow curl behind her",
            targets=["The Doctor"]))

    def test_standing_still_and_watching_does_not_end_the_beat(self):
        assert not needs_resolution(_act(
            attempt="remains motionless with steady gaze on Tamamo, allowing "
                    "the silence to linger",
            targets=["Tamamo"]))

    def test_addressing_two_people_at_once_is_still_not_a_contest(self):
        assert not needs_resolution(_act(
            attempt="tilts head a fraction toward Hinami with warm regard then "
                    "turns measured gaze to the Doctor",
            targets=["Hinami", "The Doctor"]))


class TestWhatStillEndsTheBeat:
    """The bar moved; it did not disappear. All verbatim from the corpus."""

    def test_a_grapple_does(self):
        assert needs_resolution(_act(
            attempt="Tightens grip on the caught prey's shoulder and torso, "
                    "wrenching upward and back",
            targets=["Kess"], commitment="contestable"))

    def test_closing_a_distance_does(self):
        assert needs_resolution(_act(
            attempt="Closes the 1.5-meter gap in two quick steps, planting "
                    "feet wide on the frost-slick deck",
            commitment="contestable"))

    def test_movement_does_however_confidently_it_is_declared(self):
        """`leave`/`enter` stay in the conflict list precisely because an
        asserted movement still needs the world to say where the body ended
        up before anyone answers it."""
        assert needs_resolution(_act(
            attempt="turns and leaves the chamber", commitment="asserted"))

    def test_a_concealed_act_does(self):
        assert needs_resolution(_act(
            attempt="slips the key into a sleeve", visibility="concealed"))

    def test_a_conflict_verb_survives_a_mislabelled_commitment(self):
        """The verb list is the backstop under a `commitment` the model got
        wrong, which is why it is kept rather than replaced."""
        assert needs_resolution(_act(
            attempt="grab the wrench from his hands",
            targets=["Yusuf"], commitment="asserted"))


class TestTheRuleItself:
    def test_a_target_alone_is_not_a_reason(self):
        assert not needs_resolution(_act(attempt="smiles", targets=["Tamamo"]))

    def test_commitment_is_the_discriminator(self):
        gesture = "reaches toward the offered cup"
        assert not needs_resolution(_act(attempt=gesture, commitment="asserted"))
        assert needs_resolution(_act(attempt=gesture, commitment="contestable"))

    def test_speech_alone_never_ends_the_beat(self):
        assert not needs_resolution(
            {"sequence": [{"type": "speech", "text": "Be at ease, both of you."}]})

    def test_an_empty_declaration_is_quiet(self):
        assert not needs_resolution({})
        assert not needs_resolution({"sequence": []})

    def test_one_contested_act_among_several_still_ends_it(self):
        assert needs_resolution({"sequence": [
            {"type": "action", "attempt": "nods", "targets": ["A"],
             "commitment": "asserted", "visibility": "overt"},
            {"type": "action", "attempt": "seizes her wrist", "targets": ["A"],
             "commitment": "contestable", "visibility": "overt"},
        ]})
