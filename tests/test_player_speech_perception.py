"""Regression tests for player-speech authority at the PERCEPTION layer.

Live bug (Elevator Adventure branch 41, t42): after the director-level fix
cleaned dialogue_log, the perception LLM STILL invented a player line in the
player's own view -- "Same... the one who... did this... before." -- an echo of
the player's turn-39 fragment "The same...", which then propagated through the
narrator and memory. The player's words are exactly what they declared; the
perception layer may not author them.
"""

from __future__ import annotations

from agents.common import _scrub_invented_dialogue, _scrub_undeclared_player_speech


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


# ---------------------------------------------------------------------------
# Dialogue-fidelity floor over NON-player views (_scrub_invented_dialogue).
#
# Live bug (Elevator Adventure branch 41, turn id 583 / t42): the fabricated
# player line "It's the same... the same as when I was trapped under the
# rubble in the mountain pass..." appeared in Dr. Moon's (perceiver 25) view.
# It was in NO declared speech and NOT in dialogue_log (the director-level
# backstop had already dropped it there) -- but director_resolve's
# resolved_event PROSE carried it, and perception copied it into the NPC view,
# where the player is named ("Hinami"), so the player-only "you"-cue scrub
# never ran. From there it would enter Dr. Moon's next-turn context and
# durable memory.
# ---------------------------------------------------------------------------

_T42_SPOKEN = [
    "-p-pain killer an...any in there....?",
    "-pl-please it hurts so much.",
    "There are no painkillers in this kit. I am going to clean the wound and "
    "apply a fresh bandage. This will stabilize the bleeding and reduce the "
    "risk of infection. I cannot stop the pain, but I will work as quickly as "
    "I can.",
]

_T42_CAST = ["Dr. Moon", "Hinami"]


def test_invented_player_line_removed_from_npc_view():
    """The exact live t42 fabrication in Dr. Moon's view is removed, while
    her own real declared line and the player's real whispers survive."""
    view = (
        'Hinami is lying on her side near you, breathing shallowly. She '
        'whispers, "-p-pain killer an...any in there....?" and then, '
        '"-pl-please it hurts so much." You respond, "There are no '
        'painkillers in this kit. I am going to clean the wound and apply a '
        'fresh bandage. This will stabilize the bleeding and reduce the risk '
        'of infection. I cannot stop the pain, but I will work as quickly as '
        'I can." Hinami\'s breathing remains ragged. She forces words out '
        'between sobs: "It\'s the same... the same as when I was trapped '
        'under the rubble in the mountain pass. The same weight, the same '
        'darkness, the same feeling of being crushed. I thought I\'d never '
        'feel that again." Her voice cracks, and she turns her head away, '
        'tears still falling.'
    )
    scrubbed, dropped = _scrub_invented_dialogue(
        view, _T42_SPOKEN, cast_names=_T42_CAST)
    # the fabricated backstory line is gone, attribution clause included
    assert "trapped under the rubble" not in scrubbed
    assert "forces words out between sobs" not in scrubbed
    assert any("trapped under the rubble" in d for d in dropped)
    # every legitimately spoken line survives verbatim
    assert "-p-pain killer an...any in there....?" in scrubbed
    assert "-pl-please it hurts so much." in scrubbed
    assert "There are no painkillers in this kit." in scrubbed
    # surrounding non-quote prose is preserved
    assert "Hinami's breathing remains ragged." in scrubbed
    assert "Her voice cracks" in scrubbed


def test_muffled_fragment_of_real_line_survives():
    """A distant perceiver's partial rendering of a REAL line is legitimate
    perception degradation, not invention -- it must not be stripped."""
    view = ('Through the buckled doors you hear a muffled voice: "...it hurts '
            'so much..." Something shifts in the shaft above.')
    scrubbed, dropped = _scrub_invented_dialogue(
        view, _T42_SPOKEN, cast_names=_T42_CAST)
    assert "it hurts so much" in scrubbed
    assert not dropped


def test_environmental_quoted_text_left_intact():
    """Quoted text the perceiver READS (signage) is not speech: no
    speech-attribution cue, so the floor must leave it alone."""
    view = ('A sign bolted above the panel reads "CONDEMNED". Dust sifts '
            'from the ceiling.')
    scrubbed, dropped = _scrub_invented_dialogue(
        view, _T42_SPOKEN, cast_names=_T42_CAST)
    assert '"CONDEMNED"' in scrubbed
    assert not dropped


def test_npc_view_combined_invented_fragment_and_signage():
    """The three behaviors together in one NPC view: invented line dropped,
    muffled fragment of a real line kept, signage kept."""
    view = (
        'The sign by the hatch reads "CONDEMNED". A muffled voice: "...work '
        'as quickly as I can..." Hinami sobs, "You promised me on the '
        'mountain that we would never come back here." '
        'The emergency light flickers.'
    )
    scrubbed, dropped = _scrub_invented_dialogue(
        view, _T42_SPOKEN, cast_names=_T42_CAST)
    assert '"CONDEMNED"' in scrubbed
    assert "work as quickly as I can" in scrubbed
    assert "You promised me on the mountain" not in scrubbed
    assert any("You promised me" in d for d in dropped)
    assert "The emergency light flickers." in scrubbed


def test_trailing_attribution_clause_removed_with_quote():
    """'"...," she says.' -- the attribution tail goes with the invented
    quote instead of dangling."""
    view = ('Dr. Moon closes the kit. "I remember the day the mountain came '
            'down," she says quietly. She checks the bandage.')
    scrubbed, dropped = _scrub_invented_dialogue(
        view, _T42_SPOKEN, cast_names=_T42_CAST)
    assert "the day the mountain came down" not in scrubbed
    assert "she says quietly" not in scrubbed
    assert "Dr. Moon closes the kit." in scrubbed
    assert "She checks the bandage." in scrubbed
    assert len(dropped) == 1
