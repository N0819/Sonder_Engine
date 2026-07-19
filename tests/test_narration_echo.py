"""Regression tests for player-speech echo stripping in narrator prose.

The narrator must not re-quote the player's own declared speech verbatim
(the frontend already shows what the player typed). The stripping used to
be gated by a minimum length, which let short lines slip through
unmodified and end up duplicated in the rendered prose.
"""

from agents.common import _check_narrator_fidelity, _strip_player_echo

def test_short_quoted_line_is_stripped():
    prose = 'Mara flinches as you shout, "Stop!" and the lamp gutters.'
    result = _strip_player_echo(prose, ["Stop!"])
    assert "Stop!" not in result

def test_short_curly_quoted_line_is_stripped():
    prose = 'You shout, “Wait!” but the door has already shut.'
    result = _strip_player_echo(prose, ["Wait!"])
    assert "Wait!" not in result

def test_long_line_still_stripped():
    prose = 'You say, "I am not going back down into that cellar." Mara nods.'
    result = _strip_player_echo(prose, ["I am not going back down into that cellar."])
    assert "I am not going back down into that cellar." not in result

def test_no_lines_is_a_noop():
    prose = "The storm rattles the lamp room windows."
    assert _strip_player_echo(prose, []) == prose

def test_short_bare_substring_is_not_blindly_stripped():
    # A short line that never appears in quotes should not trigger the
    # length>=8 bare-substring path and corrupt unrelated text.
    prose = "You do not know the keeper's name yet."
    result = _strip_player_echo(prose, ["no"])
    assert "know" in result

def test_fidelity_flags_reused_content_from_recent_prose():
    # recent_prose_for_rhythm is a STYLE reference for the narrator, not a
    # content source. If the current turn's prose shares long verbatim
    # runs with a recent turn's prose, that means beats were recycled
    # instead of drawn from this turn's actual view -- exactly what
    # happened when a resumed turn's narration repeated a prior turn's
    # dialogue beats almost verbatim instead of the newly resolved ones.
    recent = [
        "Boyle grunts, key ring jingling as he plants his boots, flashlight "
        "beam pinning the first door's peeling label."
    ]
    reused_prose = (
        "Boyle's grunt vibrates low; his key ring chimes as he plants his "
        "boots, flashlight beam pinning the first door's peeling label."
    )

    warnings = _check_narrator_fidelity(
        {"prose": reused_prose}, view="", recent_prose=recent,
    )

    assert any("reuse a previous turn" in w for w in warnings)

def test_fidelity_accepts_surname_or_first_name_reference():
    # Referring to a character by surname or first name alone after their
    # full name has been established in view is normal prose style, not
    # a dropped proper noun.
    view = "Dr. Elena Voss watches from the doorway. Priya Nandakumar waits nearby."
    prose = "Voss watches without a word. Priya's pen scratches in her notebook."

    warnings = _check_narrator_fidelity({"prose": prose}, view=view)

    assert not any("missing in narrator prose" in w for w in warnings)

def test_fidelity_flags_a_name_entirely_absent():
    view = "Marcus Boyle stands by the door."
    prose = "The corridor is empty and quiet."

    warnings = _check_narrator_fidelity({"prose": prose}, view=view)

    assert any("Marcus Boyle" in w for w in warnings)

def test_fidelity_allows_similar_scene_with_new_content():
    recent = [
        "Boyle grunts, key ring jingling as he plants his boots, flashlight "
        "beam pinning the first door's peeling label."
    ]
    fresh_prose = (
        "Voss states her title and years of tenure in a flat, clinical "
        "tone, then Boyle turns to prompt Tommy for his own introduction."
    )

    warnings = _check_narrator_fidelity(
        {"prose": fresh_prose}, view="", recent_prose=recent,
    )

    assert not any("reuse a previous turn" in w for w in warnings)
