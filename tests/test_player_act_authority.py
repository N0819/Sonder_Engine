"""Regression tests for player-ACT authority in director_resolve.

Live: chat 27 "Elevator Adventure", reported as "perception is inventing player
actions and also out of ordering events". Perception was innocent — it rendered
faithfully what the Director handed it. `director_resolve.resolved_event` was
giving the player conduct they never declared:

  t63  player declared SPEECH ONLY ("Well... I love the confidence at least.
       Let's get going?") and resolved_event read "Hinami's fingers close around
       the cool plastic. She lifts it to her lips and takes a small sip, then
       lowers it with a nod."

  t59  player ASKED "I hope you don't mind if I lean on you..." and
       resolved_event performed the acceptance for them: "Hinami shifts from the
       wall to Dr. Moon's support, her fingers gripping the fabric."

The out-of-order symptom is the same bug's shadow: the engine enacts the act,
then the player declares it a beat later, so the moment happens twice.

The line this draws is elaboration vs invention. Rendering a DECLARED act with
as much physical detail as the prose wants is the Director's job and must never
be flagged. Only an act arriving from nowhere is.
"""

from __future__ import annotations

from agents.common import _check_player_act_authority, _player_subject_sentences

PLAYER = "Hinami"

# The live t63 resolved_event, verbatim.
T63 = ("Dr. Moon shifts the water bottle from her grip into Hinami's free hand, "
       "pressing it firmly into her palm. Hinami's fingers close around the cool "
       "plastic. She lifts it to her lips and takes a small sip, then lowers it "
       "with a nod. Dr. Moon angles the smartphone beam toward the northern "
       "barricade and begins walking forward.")


def test_speech_only_beat_flags_invented_player_acts():
    warnings = _check_player_act_authority(T63, declared_actions=[],
                                           player_name=PLAYER)
    assert warnings, "invented player conduct on a speech-only beat not flagged"
    assert any("player-act authority" in w for w in warnings)


def test_declared_act_may_be_elaborated_freely():
    """The whole point: more detail on a declared act is welcome. A beat with a
    declared action is left alone, however richly it is rendered."""
    prose = ("Hinami pushes herself upright, her legs trembling. She leans "
             "heavily against the buckled steel wall, one hand pressed flat "
             "against the cold metal, breath shallow in the dust.")
    declared = [{"type": "action", "attempt": "slowly stands up",
                 "observable": "stands, unsteady"}]
    assert _check_player_act_authority(prose, declared, PLAYER) == []


def test_npc_conduct_is_never_the_players_problem():
    """Only sentences whose subject is the PLAYER are considered."""
    prose = ("Dr. Moon lifts the bottle to her lips and takes a sip, then nods. "
             "She steps eastward, the beam swinging ahead of her.")
    assert _check_player_act_authority(prose, [], PLAYER) == []


def test_player_speech_attribution_is_not_an_act():
    """The player's words are guarded separately; quoting them is not conduct."""
    prose = 'Hinami says, "Let\'s get going?" her voice thin in the dark.'
    assert _check_player_act_authority(prose, [], PLAYER) == []


def test_pronoun_subject_is_not_guessed_at():
    """"She lifts it" could be any woman in the beat. Guessing the referent
    would make this cry wolf on ordinary narration, so only an explicit
    player-name subject counts."""
    prose = "She lifts it to her lips and takes a small sip."
    assert _check_player_act_authority(prose, [], PLAYER) == []


def test_subject_detection_requires_the_sentence_to_open_with_the_name():
    prose = ("Dr. Moon presses the bottle into Hinami's palm. "
             "Hinami takes a small sip.")
    subjects = _player_subject_sentences(prose, PLAYER)
    assert subjects == ["Hinami takes a small sip."]


def test_empty_and_missing_inputs_are_noops():
    assert _check_player_act_authority("", [], PLAYER) == []
    assert _check_player_act_authority(T63, [], "") == []
    assert _check_player_act_authority(T63, [], None) == []
    assert _player_subject_sentences("", PLAYER) == []


def test_very_short_player_name_is_not_matched():
    """A two-letter name would match far too much ordinary prose."""
    assert _player_subject_sentences("Al takes a sip.", "Al") == []


def test_full_name_player_is_matched_on_first_name():
    prose = "Hinami takes a small sip."
    assert _player_subject_sentences(prose, "Hinami Sato") == [prose]
