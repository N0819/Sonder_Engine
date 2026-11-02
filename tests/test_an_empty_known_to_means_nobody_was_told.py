"""A disguise whose `known_to` is written EMPTY was told to nobody.

The encoder card asks for `known_to` as "the characters who legitimately KNOW
the real form", so a disguise nobody has been let in on is written
`known_to: []` -- 3 of the 18 live `physical_disguise` rows in the owner's
database were exactly that (story_scene_schema audit F1, 2026-11-01).

`disguises_from_rows` collapsed "authored as empty" and "never filled in"
into the same `[]`, and `disguise_known_to` then applied the LEGACY backstop
meant only for rows that predate the field: every observer whose
recognition map knows the subject was added to the aware set. For a disguise
that conceals identity -- a mask, another's uniform -- every acquaintance saw
straight through it, and the concealed-term tripwire treated them as aware,
so a leak to them was not flagged either. A cooperating model writing the
correct `[]` produced the leak: the engine's failure, never the model's.

The commit side already names this trap (`_supersede_disguises`: an empty
value must not mean both "authored as empty" and "never filled in"); this is
the read side adopting the same three states.
"""

from __future__ import annotations

import json

from story.scene import (disguise_breaks_recognition, disguise_known_to,
                         disguises_from_rows)


def _row(state, subject="Mara"):
    return {"subject_id": subject,
            "payload": json.dumps({"subject_id": subject, "state": state})}


KNOWN = {"Captain Holt": ["Mara"]}


def test_an_authored_empty_list_tells_no_acquaintance():
    disguise = disguises_from_rows([_row({
        "known_to": [], "conceals_identity": True,
        "presented_appearance": "a masked courier"})])["mara"]
    aware = disguise_known_to(disguise, "Mara", KNOWN)
    assert "mara" in aware                      # the wearer always knows
    assert "captain holt" not in aware
    assert disguise_breaks_recognition(aware, "Captain Holt", True) is True


def test_a_row_that_never_said_keeps_the_legacy_backstop():
    disguise = disguises_from_rows([_row({"conceals_identity": True})])["mara"]
    aware = disguise_known_to(disguise, "Mara", KNOWN)
    assert "captain holt" in aware
    assert disguise_breaks_recognition(aware, "Captain Holt", True) is False


def test_a_later_row_naming_nobody_does_not_untell_an_earlier_audience():
    disguise = disguises_from_rows([
        _row({"known_to": ["The Doctor"]}),
        _row({"known_to": []}),
    ])["mara"]
    aware = disguise_known_to(disguise, "Mara", KNOWN)
    assert "the doctor" in aware
    assert "captain holt" not in aware


def test_a_disguise_handed_in_directly_reads_the_same_three_states():
    assert "captain holt" not in disguise_known_to(
        {"known_to": []}, "Mara", KNOWN)
    assert "captain holt" in disguise_known_to({}, "Mara", KNOWN)
    assert "captain holt" in disguise_known_to(
        {"known_to": None}, "Mara", KNOWN)


def test_one_name_written_as_a_string_is_one_name_not_its_letters():
    disguise = disguises_from_rows([_row({"known_to": "The Doctor"})])["mara"]
    assert disguise["known_to"] == ["The Doctor"]
