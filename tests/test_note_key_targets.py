"""One resolver for a `ledger_notes` key: hand, channel, category word, or
a retired hand's name -- read by dispatch, the unrouted report and the
payload's note lookup alike.

Review 2026-09-07 A5/A20/A21/A38: interpret-side hands were dispatched by a
note and shown none; the roster taught a retired hand so its rulings were
reported unrouted; `inventory`/`entity` never met `inventory_ops`/`entities`;
the establish sheet asked for a crowd op the engine did not know.

Dispatch by ruling and the unrouted report went with the causal hands on
2026-09-27; the resolver stays, and so does the retired hand's absence.
"""
from agents.director import RETIRED_HANDS, SPECIALISTS, note_key_targets
from world.crowds import OP_SET, _op_word


def test_a_category_word_reaches_its_channel():
    assert ("channel", "inventory_ops") in note_key_targets("inventory")
    assert ("channel", "entities") in note_key_targets("entity")
    assert ("channel", "entities") in note_key_targets("entities")
    assert ("channel", "substance_ops") in note_key_targets("substances")


def test_a_retired_hand_routes_to_its_successor():
    assert RETIRED_HANDS == {"offscreen": "social"}
    assert ("hand", "social") in note_key_targets("offscreen")
    assert "offscreen" not in SPECIALISTS


def test_the_plural_tolerance_knows_y_and_ies():
    assert ("channel", "entities") in note_key_targets("entity")
    assert ("channel", "entities") in note_key_targets("ENTITIES")


def test_the_establish_sheets_crowd_op_spelling_is_tolerated():
    assert _op_word("open") == OP_SET
    assert _op_word("set") == OP_SET
    assert _op_word("levitate") == ""


def test_no_sheet_teaches_a_roster_the_dispatcher_does_not_have(temp_db):
    """No sheet names a retired hand. The prose author's sheet until
    2026-09-27; the encoder's since, granted every channel an owner holds.
    (That every channel has a chunk is pinned where the encoder's card is:
    tests/test_the_encoder_has_its_own_card.py.)"""
    from llm import prompts

    channels = sorted({channel for spec in SPECIALISTS.values()
                       for channel in spec["channels"]})
    for language in ("en", "ja"):
        sheet = prompts.unified_specialist_prompt(channels, language)
        for retired in RETIRED_HANDS:
            assert retired not in sheet, (language, retired)
