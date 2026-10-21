"""THE ENCODER NAMES THE LISTENER (DESIGN_SOUND_FIELD.md § 15, lane A,
2026-10-20).

Privacy in a din (§ 12.1) and the head's shadow (§ 14.1) take words only
from a BYSTANDER -- a listener a line was spoken to somebody ELSE in front
of -- and the engine reads that from the line's addressee (`targets` on the
encoder's spoken event, `intended_target` on the dialogue entry,
`spatial_senses.spoken_to`). Measured 2026-10-20: the field is EMPTY on
3,678 of the owner's 11,858 recorded lines (31%), so those rules could bite
on at most 69% of talk; of the 143 empty lines in beats the prose Director
wrote, 68 sit in prose that plainly says whom the line is to (57 by a name
in the line, 4 by "to <name>", 6 by a present body named in the sentence,
1 by a pronoun address), and 43 more in a room holding one other body.

The lever is upstream: the encoder names a line's addressee wherever the
prose says whom it is to. ONE clause, en + ja, no guard -- a model not
knowing something is the sentence's job; the readers already refuse to cap
a line that names nobody (`tests/test_a_line_to_nobody_has_no_bystander.py`).
Its effect needs a live run. These pin that the clause is stated once, on
the field it teaches, in both packs, as a class and not a list of the ways
prose names an addressee.
"""

from __future__ import annotations

from language_runtime import raw_card
from llm.prompts import unified_specialist_prompt

ADDRESSEE_EN = ("A spoken line names the body it is spoken to wherever the "
                "prose says whom it is to, however it says so; a line to the "
                "room, or to nobody in particular, names nobody.")
ADDRESSEE_JA = ("話された台詞は、記述が誰に向けた言葉かを――どのような言い方であれ――述べている"
                "ところでは、その相手の身体を targets に名指します。部屋全体に向けた台詞や、"
                "特に誰にも向けていない台詞は、誰も名指しません。")


def test_the_core_card_states_the_addressee_class_once_on_targets():
    sheet = unified_specialist_prompt([], "en", [])
    assert sheet.count(ADDRESSEE_EN) == 1
    bullet = next(line for line in sheet.splitlines()
                  if line.startswith("- targets:"))
    assert ADDRESSEE_EN in bullet
    # the complement is stated: a line to nobody names nobody
    assert "names nobody" in bullet


def test_the_japanese_card_says_the_same_on_the_same_field():
    core = raw_card("ja")["encoder"]["core"]
    assert core.count(ADDRESSEE_JA) == 1
    bullet = next(line for line in core.splitlines()
                  if line.startswith("- targets:"))
    assert ADDRESSEE_JA in bullet


def test_the_clause_names_the_class_and_not_the_ways_prose_says_it():
    """"however it says so" covers a vocative, "to <name>", "turns to
    <name>" and whatever English finds next; a list of them would reach
    only what it names (CLAUDE.md: no word lists in prompts)."""
    sheet = unified_specialist_prompt([], "en", [])
    bullet = next(line for line in sheet.splitlines()
                  if line.startswith("- targets:"))
    assert "however it says so" in bullet
    for instance in ("vocative", "turns to", "tells "):
        assert instance not in bullet
