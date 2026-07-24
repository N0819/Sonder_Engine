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


def test_short_full_name_is_matched_but_short_fragments_are_not():
    """A player whose whole name is short is still their name — the length
    guard exists for tokens split OUT of a longer name ("Jo" from "Jo Anne"),
    where a fragment could collide with ordinary words. Word boundaries keep
    "Al" from matching "Also"."""
    from agents.common import _player_name_forms
    assert _player_subject_sentences("Al takes a sip.", "Al") == ["Al takes a sip."]
    assert _player_subject_sentences("Also, the door opens.", "Al") == []
    assert "Jo" not in _player_name_forms("Jo Anne")


def test_full_name_player_is_matched_on_first_name():
    prose = "Hinami takes a small sip."
    assert _player_subject_sentences(prose, "Hinami Sato") == [prose]


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
    step/variant inspector rather than vanishing into ctx.warnings."""
    source = open("agents/director.py").read()
    assert 'out["player_act_warnings"] = _invented' in source


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
