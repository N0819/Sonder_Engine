"""Regression tests for player-speech authority at the PERCEPTION layer.

Live bug (Elevator Adventure branch 41, t42): after the director-level fix
cleaned dialogue_log, the perception LLM STILL invented a player line in the
player's own view -- "Same... the one who... did this... before." -- an echo of
the player's turn-39 fragment "The same...", which then propagated through the
narrator and memory. The player's words are exactly what they declared; the
perception layer may not author them.
"""

from __future__ import annotations

from agents.common import _scrub_undeclared_player_speech


def test_invented_player_line_sentence_is_dropped():
    view = ('A pained cry escapes your lips. Dr. Moon presses fresh gauze '
            'against the gash. Her voice is flat, even: "The wound is still '
            'bleeding. Remain still." Through gritted teeth, you whisper, '
            '"Same... the one who... did this... before." The pain makes it '
            'hard to think.')
    scrubbed, dropped = _scrub_undeclared_player_speech(
        view,
        declared_bodies=["AAUUaaaUAa!", "-p-pain....killer an...any in there....?"],
        protected_bodies=['"The wound is still bleeding. Remain still."'],
        cast_names=["Dr. Moon", "Hinami"])
    # the fabricated player line and its sentence are gone...
    assert "the one who" not in scrubbed
    assert any("the one who" in d for d in dropped)
    # ...but the NPC's legitimately-heard line survives verbatim
    assert "The wound is still bleeding. Remain still." in scrubbed
    # and surrounding non-quote prose is preserved
    assert "A pained cry escapes your lips." in scrubbed


def test_declared_player_line_is_kept():
    view = 'You whisper, "Little better..." and let the bottle fall.'
    scrubbed, dropped = _scrub_undeclared_player_speech(
        view, declared_bodies=["Little better..."], protected_bodies=[],
        cast_names=[])
    assert "Little better" in scrubbed
    assert not dropped


def test_npc_attributed_quote_not_touched():
    """A quote whose nearest speaker is an NPC is out of scope even if
    undeclared -- the player floor must not strip NPC-attributed lines."""
    view = 'Dr. Moon says, "Hold still." You nod weakly.'
    scrubbed, dropped = _scrub_undeclared_player_speech(
        view, declared_bodies=[], protected_bodies=[], cast_names=["Dr. Moon"])
    assert "Hold still" in scrubbed
    assert not dropped


def test_wordless_player_cry_not_expanded_is_fine():
    """No quoted player line at all -> nothing to scrub."""
    view = 'A raw scream tears out of you as the bandage peels away.'
    scrubbed, dropped = _scrub_undeclared_player_speech(
        view, declared_bodies=["AAUUaaaUAa!"], protected_bodies=[], cast_names=[])
    assert scrubbed == view and not dropped
