"""Regression tests for the player-person leak (live: chat 27 "Elevator
Adventure", turn idx 54).

The player persona was Hinami; the only active character was Dr. Moon. The
player's own perception view came back mixing persons for ONE character --
"...her hand is braced against the wall beside YOUR shoulder. Dr. Moon steps
briskly from the barricade toward HINAMI..." -- and the narrator copied it
through ("She steps past you toward Hinami").

That third-person sentence was not a model whim: perception's deterministic
"last overt action" backstop appends the acting agent's `observable` surface
verbatim to every perceiver's view, and those surfaces are authored in third
person naming everyone else -- so the player's own name landed in the player's
own view at zero temperature. Two floors close it:

  1. _self_second_person rewrites the RECEIVING perceiver's own name to
     second person before injection (agents/common.py, wired through
     _inject_action's `self_forms`);
  2. _check_player_person raises an ENFORCEABLE narrator warning when the
     prose names the player while narration_person is second/first, which
     drives the existing correction-retry.

Both floors must stay quiet on the cases they'd otherwise cry wolf on:
quoted dialogue (a character calling the player by name is legitimate and
must survive verbatim) and third-person narration (where naming the player
is exactly correct).
"""

from __future__ import annotations

from agents.common import (
    _action_already_rendered,
    _check_narrator_fidelity,
    _check_player_person,
    _inject_action,
    _self_second_person,
)
from agents.narration import _ENFORCEABLE_PREFIXES

# The live observable Dr. Moon's character step emitted on turn 54.
MOON_OBSERVABLE = (
    "steps briskly from the barricade toward Hinami, one hand extending to "
    "brace against the wall beside her shoulder"
)

# The (correct, second-person) part of the live player view it was glued onto.
LIVE_PLAYER_VIEW = (
    "You are leaning against the cold concrete wall, your body trembling. "
    "She is near you, having moved quickly; her hand is braced against the "
    "wall beside your shoulder."
)


# --- floor 1: perception-side rewrite ---------------------------------------

def test_perceivers_own_name_becomes_second_person():
    out = _self_second_person(MOON_OBSERVABLE, ["Hinami"])
    assert "Hinami" not in out
    assert "toward you," in out


def test_possessive_form_becomes_your():
    out = _self_second_person("crouches beside Hinami's bag", ["Hinami"])
    assert out == "crouches beside your bag"


def test_sentence_initial_name_is_capitalized():
    out = _self_second_person(
        "The beam swings. Hinami is caught in it. Hinami's ears flatten.",
        ["Hinami"])
    assert out == "The beam swings. You are caught in it. Your ears flatten."


def test_subject_position_name_fixes_verb_agreement():
    # "Hinami steps" -> "You steps" would be visibly broken prose.
    cases = {
        "Hinami steps into the lobby": "You step into the lobby",
        "Hinami is caught in the beam": "You are caught in the beam",
        "Hinami was already moving": "You were already moving",
        "Hinami has the packet": "You have the packet",
        "Hinami catches the strap": "You catch the strap",
        "Hinami carries the bag": "You carry the bag",
        "Hinami pushes off the wall": "You push off the wall",
        "Hinami goes still": "You go still",
        "Hinami loses her footing": "You lose her footing",
        "Hinami doesn't move": "You don't move",
    }
    for src, want in cases.items():
        assert _self_second_person(src, ["Hinami"]) == want


def test_agreement_repair_leaves_non_verbs_alone():
    # A word that merely ends in -s after the subject must survive intact.
    assert _self_second_person(
        "Hinami always leans on the wall", ["Hinami"]
    ) == "You always leans on the wall"
    assert _self_second_person(
        "Hinami perhaps hears it", ["Hinami"]) == "You perhaps hears it"


def test_agreement_repair_does_not_touch_untouched_segments():
    # No substitution in this text -> no agreement pass at all.
    src = "Dr. Moon crosses the lobby."
    assert _self_second_person(src, ["Hinami"]) == src


def test_aliases_are_rewritten_too():
    out = _self_second_person("nods to Hinami, then to 火波", ["Hinami", "火波"])
    assert "Hinami" not in out and "火波" not in out


def test_other_characters_are_left_alone():
    # Only the RECEIVING perceiver's own name is rewritten; the actor and
    # every third party stay in third person where they belong.
    out = _self_second_person(MOON_OBSERVABLE, ["Dr. Moon"])
    assert "Hinami" in out
    assert "toward Hinami" in out


def test_quoted_name_survives_verbatim():
    # A character calling the player by name aloud is sensory signal, and
    # dialogue fidelity forbids rewriting it.
    text = 'Dr. Moon says, "Hinami, sit down." Then she steps toward Hinami.'
    out = _self_second_person(text, ["Hinami"])
    assert '"Hinami, sit down."' in out
    assert "steps toward you." in out


def test_common_word_name_matched_case_sensitively():
    # "Rose" the player vs "rose" the flower -- ordinary lowercase prose
    # must never be rewritten into second person.
    out = _self_second_person(
        "kneels by the rose bushes and hands Rose the trowel", ["Rose"])
    assert out == "kneels by the rose bushes and hands you the trowel"


def test_inject_action_into_own_view_never_names_the_perceiver():
    """End-to-end reproduction of the live turn-54 failure."""
    before = _inject_action(LIVE_PLAYER_VIEW, "Dr. Moon", MOON_OBSERVABLE, True)
    assert "toward Hinami" in before  # the bug, with no self_forms

    after = _inject_action(LIVE_PLAYER_VIEW, "Dr. Moon", MOON_OBSERVABLE, True,
                           self_forms=["Hinami"])
    assert "Hinami" not in after
    assert "Dr. Moon steps briskly from the barricade toward you" in after
    # The actor is still named and the beat is still delivered -- this floor
    # fixes the person, it does not suppress perception.
    assert "Dr. Moon" in after


def test_inject_action_into_another_perceivers_view_is_unchanged():
    # Dr. Moon's own view must still refer to Hinami by name; only the
    # perceiver's OWN name folds to second person.
    moon_view = "You are at the barricade."
    out = _inject_action(moon_view, "Hinami", "leans against the wall", True,
                         self_forms=["Dr. Moon"])
    assert "Hinami leans against the wall." in out


# --- floor 1b: the duplicate the person leak rode in on ---------------------
#
# The injected clone was appended at the END of the view, AFTER the dialogue,
# so the narrator rendered the beat, then the speech, then the SAME beat again
# as if it were a later action ("...braces you against the wall. [speech] She
# crosses to Hinami in three quick strides, ducks under her arm, and braces
# her weight against the wall. She doesn't look back."). Fixing the person
# alone would leave that temporal garble in place.

# The live reroll of chat 27 turn 54: the perception LLM rendered the beat
# itself, spread over two sentences and in second person.
REROLL_VIEW = (
    "Dr. Moon is right in front of you, having crossed quickly. Her arm is "
    "under yours, bracing you against the wall. Her face is close. She says, "
    '"Sit down. Do not attempt to move further." Her voice is flat, clinical.'
)
REROLL_OBSERVABLE = (
    "crosses to Hinami in three quick strides, ducks under her arm, and "
    "braces her weight against the wall"
)


def test_beat_spread_across_sentences_is_recognized_as_already_rendered():
    assert _action_already_rendered(REROLL_VIEW, "Dr. Moon", REROLL_OBSERVABLE)


def test_live_reroll_injects_no_duplicate_beat():
    out = _inject_action(REROLL_VIEW, "Dr. Moon", REROLL_OBSERVABLE, True,
                         self_forms=["Hinami"])
    assert out == REROLL_VIEW  # nothing appended
    assert "Hinami" not in out


def test_genuine_omission_still_injected_when_actor_is_named():
    # The whole-view rule must not swallow a real action just because the
    # actor happens to be mentioned in the view.
    view = ("Dr. Moon kneels by the medical kit and opens it. The lobby is "
            "dark around you.")
    out = _inject_action(view, "Dr. Moon", "shines the light toward the "
                         "northern barricade", True, self_forms=["Hinami"])
    assert "shines the light toward the northern barricade" in out


def test_place_words_alone_are_not_evidence_of_the_same_beat():
    # "against"/"beside"/"near" are function words. Before they joined the
    # stopword set they counted as distinctive content, so two unrelated
    # actions near the same wall scored as the same beat. Sharing ONLY place
    # words must leave the whole-view rule (>= 3 distinctive tokens) unarmed.
    view = "Dr. Moon shines the light around the lobby, near the far doors."
    assert not _action_already_rendered(
        view, "Dr. Moon", "kneels beside the medical kit near the wall")


def test_unnamed_actor_does_not_trigger_whole_view_suppression():
    view = ("A young woman crosses the lobby. Her arm is under yours. She "
            "braces you against the wall.")
    # Actor not named anywhere -> whole-view rule stays out of it.
    assert not _action_already_rendered(view, "Dr. Moon", REROLL_OBSERVABLE)


# --- floor 2: narrator-side check -------------------------------------------

def test_flags_player_named_in_second_person_narration():
    warnings = _check_player_person(
        "She steps past you toward Hinami without waiting for an answer.",
        "Hinami", "second")
    assert len(warnings) == 1
    assert "Hinami" in warnings[0]


def test_flags_player_named_in_first_person_narration():
    warnings = _check_player_person(
        "Dr. Moon braces the wall beside Hinami.", "Hinami", "first")
    assert len(warnings) == 1


def test_silent_when_narration_is_third_person():
    # In third person, naming the player is exactly what the prompt asks for.
    assert _check_player_person(
        "Dr. Moon braces the wall beside Hinami.", "Hinami", "third") == []


def test_silent_when_player_name_only_appears_in_dialogue():
    warnings = _check_player_person(
        'She does not look up. "Hinami, sit down," she says.',
        "Hinami", "second")
    assert warnings == []


def test_silent_on_clean_second_person_prose():
    warnings = _check_player_person(
        "Your tails drag as you step into the lobby. Dr. Moon reaches you "
        "before you can fall.", "Hinami", "second")
    assert warnings == []


def test_silent_when_person_unknown():
    assert _check_player_person("Hinami steps in.", "Hinami", None) == []
    assert _check_player_person("Hinami steps in.", None, "second") == []


def test_narrator_fidelity_surfaces_the_warning_and_it_is_enforceable():
    out = {"prose": "She steps past you toward Hinami, one hand out."}
    warnings = _check_narrator_fidelity(
        out, view="Dr. Moon steps briskly toward you, one hand out.",
        player_name="Hinami", narration_person="second")
    person = [w for w in warnings if w.startswith("Player named in third person")]
    assert len(person) == 1
    # Must land in the enforceable set so the existing rewrite-retry fires.
    assert person[0].startswith(_ENFORCEABLE_PREFIXES)


def test_narrator_fidelity_silent_without_person_context():
    # Callers that don't pass the person context (older call sites, tests)
    # must not start seeing spurious warnings.
    out = {"prose": "Hinami steps into the lobby."}
    warnings = _check_narrator_fidelity(out, view="Hinami steps into the lobby.")
    assert not [w for w in warnings
                if w.startswith("Player named in third person")]
