"""The narrator's sheet is its core plus the sections this beat's payload
carries -- the same miniaturisation the Director's hands got.

The narrator loaded 42 KB every beat; eleven of its sections describe a
payload field the beat carries only sometimes (portal states, attire, the
spatial frame, beat time, sensory channels, exemplars, correction notes,
dialogue placeholders...). Each such section now opens with a marker naming
its field and closes with `[[core]]`; `narrator_prompt` keeps the core and the
sections whose field is present, and the markers never reach a model.
"""

from llm.prompts import DEFAULT_PROMPTS, narrator_prompt, narrator_sections


def test_a_marked_sheet_is_cut_at_its_markers():
    body = "Core one.\n[[when: portal_states]]\nPORTAL STATE: doors.\n[[core]]\nCore two.\n[[when: exemplars, correction_notes]]\nEXEMPLARS.\n[[core]]\n"
    sections = narrator_sections(body)
    assert [(sorted(f), t.strip()) for f, t in sections] == [
        ([], "Core one."), (["portal_states"], "PORTAL STATE: doors."),
        ([], "Core two."), (["correction_notes", "exemplars"], "EXEMPLARS.")]


def test_the_english_sheet_drops_what_the_beat_does_not_carry():
    bare = narrator_prompt({"past_narration", "present_scene", "current_events"})
    full = narrator_prompt({"past_narration", "portal_states", "player_attire",
                            "spatial_frame", "beat_time", "sensory_channels",
                            "exemplars", "correction_notes", "dialogue_lines",
                            "authored_body_parts", "co_present_positions",
                            "overused_phrases", "already_established_phrases"})
    assert "[[when:" not in bare and "[[core]]" not in bare
    assert "PORTAL STATE:" not in bare and "PORTAL STATE:" in full
    assert "DIALOGUE PLACEHOLDERS" not in bare and "DIALOGUE PLACEHOLDERS" in full
    assert "STYLE EXEMPLARS" not in bare and "STYLE EXEMPLARS" in full
    # The core every beat reads stays: the four rules and the echo rule.
    assert "INVENT NOTHING" in bare and "PLAYER ECHO RULE" in bare
    assert len(bare) < 0.8 * len(full)


def test_a_sheet_with_no_markers_is_sent_whole():
    assert narrator_sections("Only core.") == [(frozenset(), "Only core.")]


def test_the_stored_sheet_still_publishes_every_section():
    """The editor and the presets keep ONE stored body: the full sheet, markers
    and all, so nothing a host edits is hidden from them."""
    whole = DEFAULT_PROMPTS["narrator"]
    for head in ("PORTAL STATE:", "STYLE EXEMPLARS", "DIALOGUE PLACEHOLDERS",
                 "SENSORY CHANNELS", "PERCEPTION IS NOT MEMORY"):
        assert head in whole
