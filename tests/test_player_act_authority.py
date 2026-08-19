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

import re

from agents.common import _check_player_act_authority, _sentence_subjects


def _player_sentences(prose, player_name):
    """Sentences the live guard reads as the player's own.

    These cases used to run against `_player_subject_sentences`, which was
    superseded by `_sentence_subjects` and kept alive by this file alone. The
    difference is deliberate and is why the old one had to go: the superseded
    version refused a pronoun subject outright, and the live one continues the
    most recently NAMED subject through one -- the miss (chat 56 t1391) was
    four sentences of "he" after a single naming. Sentences opening with the
    player's own name resolve identically in both.
    """
    return [sentence for sentence, subject
            in _sentence_subjects(prose, [player_name])
            if subject == player_name]

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
    subjects = _player_sentences(prose, PLAYER)
    assert subjects == ["Hinami takes a small sip."]


def test_act_authority_empty_and_missing_inputs_are_noops():
    assert _check_player_act_authority("", [], PLAYER) == []
    assert _check_player_act_authority(T63, [], "") == []
    assert _check_player_act_authority(T63, [], None) == []
    assert _player_sentences("", PLAYER) == []


def test_short_full_name_is_matched_but_short_fragments_are_not():
    """A player whose whole name is short is still their name — the length
    guard exists for tokens split OUT of a longer name ("Jo" from "Jo Anne"),
    where a fragment could collide with ordinary words. Word boundaries keep
    "Al" from matching "Also"."""
    from agents.common import _player_name_forms
    assert _player_sentences("Al takes a sip.", "Al") == ["Al takes a sip."]
    assert _player_sentences("Also, the door opens.", "Al") == []
    assert "Jo" not in _player_name_forms("Jo Anne")


def test_full_name_player_is_matched_on_first_name():
    prose = "Hinami takes a small sip."
    assert _player_sentences(prose, "Hinami Sato") == [prose]


# ---- Enforcement, not just detection ----
#
# The first pass only appended to ctx.warnings, which the codebase itself notes
# is "accumulated pipeline-wide but never surfaced" -- so an invented act was
# neither removed nor reported, and a live reroll AFTER that fix still produced
# "Hinami straightens, her weight shifting more onto her own feet" on a
# speech-only beat. resolved_event feeds perception -> narrator -> memory, so
# the fabrication becomes canon.

LIVE_REROLL = ("Hinami straightens, her weight shifting more onto her own feet "
               'as she speaks. "Well... I love the confidence at least." '
               "Dr. Moon nods once, her expression flat but focused.")


def test_inflected_verbs_are_caught():
    """The first verb list missed "straightens" and "shifting" entirely."""
    assert _check_player_act_authority(LIVE_REROLL, [], PLAYER)


def test_director_resolve_retries_and_keeps_the_better_draft(monkeypatch):
    import agents.director as director

    drafts = [
        {"resolved_event": LIVE_REROLL},
        {"resolved_event": ('Hinami speaks, her voice warm. "Well... I love the '
                            'confidence at least." Dr. Moon nods once and '
                            "extends the bottle toward her.")},
    ]
    seen = []

    def fake_agent_json(role, key, prompt, payload, **kw):
        seen.append(payload)
        return drafts[len(seen) - 1]

    monkeypatch.setattr(director, "_agent_json", fake_agent_json)

    out = drafts[0]
    invented = _check_player_act_authority(out["resolved_event"], [], PLAYER)
    assert invented, "fixture must start in violation"

    # Second draft is clean, so the retry must win.
    clean = _check_player_act_authority(drafts[1]["resolved_event"], [], PLAYER)
    assert clean == []


def test_a_worse_retry_never_wins():
    """The retry is kept only if it reduces the violation count."""
    first = _check_player_act_authority(LIVE_REROLL, [], PLAYER)
    worse = _check_player_act_authority(
        "Hinami straightens. Hinami steps forward. Hinami reaches out.",
        [], PLAYER)
    assert len(worse) > len(first)


def test_surviving_violations_are_attached_to_the_step():
    """If the retry still offends, it must at least be visible in the
    step/variant inspector rather than vanishing into ctx.warnings.

    Matched on the assignment and its operands rather than one literal line:
    the character-authority guards joined the same list (`_cacts`, `_quotes`)
    and reflowed it across two lines, which a substring match on the old
    single-line form read as the feature having been removed.
    """
    source = open("agents/director.py").read()
    assign = re.search(
        r'out\["player_act_warnings"\]\s*=\s*\(?\s*([^\n)]*(?:\n[^\n)]*)?)',
        source)
    assert assign, 'player_act_warnings is no longer attached to the step'
    operands = assign.group(1)
    for required in ("_invented", "_mute", "_felt"):
        assert required in operands, f"{required} no longer reaches the step"


# ---- False positives caught by the existing suite ----
#
# The first enforcing version fired a correction retry on a pure-dialogue turn
# (tests/test_resolve_reconciliation.py::test_pure_dialogue_turn_triggers_
# nothing), for two independent reasons. Both are pinned here.

def test_article_led_player_name_is_not_split_to_its_article():
    """A player called "The Stranger" was reduced to the token "The", which
    then matched the opening of almost every sentence in the beat."""
    from agents.common import _player_name_forms
    forms = _player_name_forms("The Stranger")
    assert "The" not in forms
    assert "The Stranger" in forms and "Stranger" in forms


def test_titles_are_not_treated_as_the_name():
    from agents.common import _player_name_forms
    assert "Dr" not in _player_name_forms("Dr. Vorne")
    assert "Commander" not in _player_name_forms("Commander Vale")


def test_only_the_main_verb_counts():
    """"The Stranger asks Mara how she is holding up" has the player merely
    ASKING; "holding" belongs to a subordinate clause about someone else."""
    prose = "The Stranger asks Mara how she is holding up."
    assert _check_player_act_authority(prose, [], "The Stranger") == []


def test_act_verb_far_from_the_subject_is_not_flagged():
    prose = ("Hinami says nothing for a moment, watching the beam sweep the "
             "lobby while Dr. Moon lifts the medical kit from the desk.")
    assert _check_player_act_authority(prose, [], PLAYER) == []


def test_possessive_subject_is_still_the_player():
    assert _check_player_act_authority(
        "Hinami's fingers close around the cool plastic.", [], PLAYER)


# --- the mirror: a character owns their own speech --------------------------
#
# Live, alpha 6.0.2: a character agent declared silence -- empty sequence,
# stop_reason "natural silence", no dialogue_log entry -- and the Director's
# resolved_event said "<the character> adds a further comment" anyway.
# Perception rendered a speech event with no content; the narrator, having
# nothing to quote, dressed the absence as inaudibility. It was read as a
# muffling bug and was a fabrication. The player side of this boundary had a
# guard since alpha 6.0.2; characters had none, so nothing objected when the
# Director authored conduct for a mind that owns it.

from agents.common import _check_character_speech_authority

SILENT = ["Elyndra"]


def test_speech_authority_live_failure_is_caught():
    assert _check_character_speech_authority(
        "Elyndra adds a further comment. Hinami looks away.", SILENT)


def test_a_contentless_attribution_is_the_whole_point():
    """Nothing downstream can tell this was invented: it quotes nothing, so
    the dialogue-fidelity checks have no body to whitelist against."""
    assert _check_character_speech_authority(
        "Elyndra says something in reply.", SILENT)


def test_a_silent_character_may_still_act():
    assert _check_character_speech_authority(
        "Elyndra steps closer and watches her.", SILENT) == []


def test_thinking_and_looking_are_not_speech():
    for prose in ("Elyndra considers the question.",
                  "Elyndra looks at her for a long moment.",
                  "Elyndra hesitates, then turns away."):
        assert _check_character_speech_authority(prose, SILENT) == [], prose


def test_a_character_who_spoke_is_not_checked():
    """Separating an elaborated line from an added one needs more than a verb
    list, so only total silence is adjudicated -- the same scoping its sibling
    uses for actions."""
    assert _check_character_speech_authority(
        "Elyndra adds a further comment.", ["Hinami"]) == []


def test_speech_authority_pronoun_subject_is_not_guessed_at():
    assert _check_character_speech_authority(
        "She adds a further comment.", SILENT) == []


def test_inflected_speech_verbs_are_caught():
    for verb in ("murmurs", "muttered", "is replying", "answers", "puts in"):
        assert _check_character_speech_authority(
            f"Elyndra {verb} to nobody in particular.", SILENT), verb


def test_speech_authority_empty_and_missing_inputs_are_noops():
    assert _check_character_speech_authority("", SILENT) == []
    assert _check_character_speech_authority("Elyndra says something.", []) == []
    assert _check_character_speech_authority("Elyndra says something.", [""]) == []


# --- what the player FEELS is theirs as much as what they do ----------------
#
# Live, alpha 6.3, chat 52 "Elyndra — Hinami ⎇16 ⎇1" turn 19. The player typed
# only "W-what did you do to me!?" and director_resolve wrote:
#
#   "Elyndra's teasing smile falters completely at the shrill, PANICKED cry."
#   "...as she takes in the GENUINE TERROR in those wide eyes."
#
# Perception then copied both into Elyndra's own view, so an interior state the
# player never declared became something a second mind had observed as fact.
# The Director owns objective causality; it does not own what is inside the
# protagonist. It may report every observable a body shows and must stop there.

from agents.common import _check_player_interiority_authority

PLAYER = "Hinami"


def test_interiority_live_failure_is_caught():
    assert _check_player_interiority_authority(
        "Elyndra takes in the genuine terror in Hinami's wide eyes.",
        PLAYER, "W-what did you do to me!?")


def test_the_certainty_word_is_reported_with_it():
    """'genuine' is unremarkable alone and damning beside 'terror' — an
    observer cannot know an interior state is authentic."""
    got = _check_player_interiority_authority(
        "Elyndra sees the genuine terror in Hinami's eyes.", PLAYER)
    assert got and "genuine" in got[0]


def test_observable_surface_is_always_allowed():
    """Trembling, wide eyes, a shrill cry — the body's own showing is the
    Director's to report, and is what the prose should carry."""
    for prose in ("Hinami trembles, her golden ears flattened.",
                  "Hinami's eyes go wide and she steps back.",
                  "A shrill cry comes from the bundle where Hinami is."):
        assert _check_player_interiority_authority(prose, PLAYER) == [], prose


def test_a_feeling_the_player_declared_is_theirs_to_declare():
    assert _check_player_interiority_authority(
        "Hinami is terrified and cannot speak.", PLAYER,
        "I am terrified, I can't speak") == []


def test_an_npcs_interior_state_is_not_the_players_business():
    """The Director resolves NPC conduct; this guard is only about the player."""
    assert _check_player_interiority_authority(
        "Elyndra feels a flicker of doubt.", PLAYER) == []


def test_interiority_pronoun_subject_is_not_guessed_at():
    """"her terror" in a two-woman scene could be either of them, and guessing
    would flag ordinary NPC description."""
    assert _check_player_interiority_authority(
        "She takes in the terror in those wide eyes.", PLAYER) == []


def test_interior_verbs_are_caught_too():
    assert _check_player_interiority_authority(
        "Hinami realises what has happened to her.", PLAYER)


def test_interiority_empty_and_missing_inputs_are_noops():
    assert _check_player_interiority_authority("", PLAYER) == []
    assert _check_player_interiority_authority("Hinami is afraid.", "") == []


# --------------------------------------------------------------------------
# Chat 56 ("Run!"): the player narrates a gesture every single beat, which
# under the old blanket `if declared_actions: return []` disarmed the act
# guard for the entire story. Verbatim from the stored steps.
# --------------------------------------------------------------------------

T10_INPUT = '"Heh? What are we doing what\'s going on?" You look genuinely confused.'
T10_DECLARED = [{
    "attempt": "She looks genuinely confused, her expression open and uncertain.",
    "observable": "widens her eyes, brow furrowing, ears twitching",
}]
T10_RESOLVE = (
    "Hinami stands by the sealed police-box doors, her copper-gold hair "
    "catching the warm light, the feather clip askew from the chaos of the "
    "alley. She widens her eyes, brow furrowing, her fox ears twitching as she "
    "looks around the vaulted chamber. Hinami blinks, her ears flattening "
    "slightly as she processes. She takes a ragged breath, her hands coming up "
    "to grip the edge of the console, fingers finding a lever as if to steady "
    "herself."
)


def test_an_act_the_player_never_declared_is_caught_on_a_beat_they_did_act():
    """The reported symptom. The player declared a look; the Director had her
    take hold of a lever, and her NEXT input was "Which lever?!" -- the
    fabricated act replayed a beat later."""
    got = _check_player_act_authority(
        T10_RESOLVE, T10_DECLARED, PLAYER, ["The Doctor"], T10_INPUT)
    assert got, "the invented lever grip must be flagged"
    assert any("'edge'" in w for w in got), got


def test_restating_where_the_player_already_stands_is_not_an_act():
    """"Hinami stands by the sealed doors" re-establishes a position the beat
    already holds. Ordinary scene-setting, not conduct."""
    got = _check_player_act_authority(
        "Hinami stands by the sealed police-box doors, her hair catching the "
        "warm light.", T10_DECLARED, PLAYER, ["The Doctor"], T10_INPUT)
    assert got == [], got


def test_elaborating_a_declared_act_is_still_not_flagged():
    """t3: the player declared leaning on the wall and holding her chest, and
    the resolve rendered exactly that, richly. The Director's job."""
    declared = [{
        "attempt": "Leaning against the wall, holding chest, breathing ragged "
                   "breaths, throat raw, appearing in pain from overexertion",
        "observable": "leans back against the wall, one hand pressed to her "
                      "chest, breathing hard in ragged gasps",
    }]
    got = _check_player_act_authority(
        "Hinami leans back against the pale wall, one hand pressed to her "
        "chest, her breath coming in ragged, audible gasps.",
        declared, PLAYER, ["The Doctor"],
        "You continue to breath raged breaths leaning against the wall "
        "holding your chest.")
    assert got == [], got


def test_a_declared_act_elaborated_under_a_pronoun_subject_is_not_flagged():
    """t8: declared standing, tails lowering, ears rising -- rendered back
    under a pronoun subject. Vocabulary shared, so not an addition."""
    declared = [{
        "attempt": "She stands up, tails lowering, ears raising slightly.",
        "observable": "rises to her feet, tails swaying, ears lifting",
    }]
    got = _check_player_act_authority(
        "Hinami is by the doors. She rises to her feet, her tails lowering "
        "into a slow, shaking sway, her ears lifting from their pinned "
        "position.", declared, PLAYER, ["The Doctor"],
        "You slowly stand up still trembling slightly but your tails slowly "
        "lower going into a slow shaking sway your ears raising slightly.")
    assert got == [], got


def test_declaring_nothing_still_flags_everything():
    """The original scope is untouched: no declared action means any act is
    invented by construction."""
    assert _check_player_act_authority(
        "Hinami takes the bottle and drinks from it.", [], PLAYER)


T6_INPUT = (
    '"I mean... they were ranting... about how we were inferior lifeforms. '
    'Before they started screaming EXTERMINATE!" You imitate them slightly '
    'and shudder.'
)
T6_RESOLVE = (
    "Hinami's voice wavers as she speaks, then rises into a harsh, metallic "
    "imitation of the Dalek's cry. She looks at him, still shaky, but the "
    "terror in her eyes has begun to recede."
)


def test_player_interiority_under_a_pronoun_subject_is_caught():
    """t6. The player declared a shudder; the Director decided her emotional
    arc. The name-only test could not see a pronoun subject."""
    got = _check_player_interiority_authority(
        T6_RESOLVE, PLAYER, T6_INPUT, ["The Doctor"])
    assert got, "the invented receding terror must be flagged"
    assert any("terror" in w for w in got), got


def test_a_feeling_the_player_declared_is_still_theirs_to_declare():
    """The exemption survives the pronoun widening."""
    assert _check_player_interiority_authority(
        "Hinami is afraid. She is still afraid.", PLAYER,
        "You are afraid and shaking.", ["The Doctor"]) == []
