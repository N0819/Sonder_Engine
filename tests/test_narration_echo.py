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
    # past_narration is the story's own text for the narrator, not a
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


# --- the narrator tidies what the player typed -----------------------------

def test_a_repunctuated_player_line_is_still_stripped():
    """Chat 72, turn 35, live. The player typed

        "He was kind of annoying, but harmless." You look around.
        "Anyways your plan doctor?"

    and the narrator rendered the second line as `"Anyways, your plan,
    Doctor?"` -- two inserted commas and a capitalised Doctor. The strip
    matched declared speech as a LITERAL substring, so the tidy-up defeated it
    and the player's own line reached the page as an unattributed quote.

    Correcting the player's grammar is the one thing a narrator reliably does,
    which made the guard's failure rate proportional to how well it wrote.
    """
    from agents.common import _strip_player_echo
    prose = ('You glance around the dim forecourt.\n\n'
             '"Anyways, your plan, Doctor?"\n\n'
             'The Doctor answers. "Plan? Right."')
    out = _strip_player_echo(
        prose,
        ["He was kind of annoying, but harmless.", "Anyways your plan doctor?"],
        protect_quotes=['"Plan? Right."'])
    assert "Anyways" not in out
    assert "Plan? Right." in out, "an NPC quote must survive the strip"


def test_a_short_folded_match_is_not_treated_as_an_echo():
    """Below three words the fold is not evidence: "no", "wait", "why" recur in
    anyone's mouth, and the literal pass already catches a short line that
    arrived unedited. Over-stripping would eat an NPC's line."""
    from agents.common import _strip_player_echo
    prose = 'She stops. "Wait!" he calls after her.'
    out = _strip_player_echo(prose, ["wait"], protect_quotes=[])
    assert '"Wait!"' in out


def test_the_fold_does_not_reach_a_protected_npc_quote():
    """Masking runs first, so a protected NPC span is out of reach even when
    its words match the player's exactly -- the case blind stripping would
    corrupt."""
    from agents.common import _strip_player_echo
    prose = 'You nod. The Doctor repeats it back: "So, what is the plan?"'
    out = _strip_player_echo(prose, ["So what is the plan"],
                             protect_quotes=['"So, what is the plan?"'])
    assert "So, what is the plan?" in out
