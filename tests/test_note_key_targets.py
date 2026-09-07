"""One resolver for a `ledger_notes` key: hand, channel, category word, or
a retired hand's name -- read by dispatch, the unrouted report and the
payload's note lookup alike.

Review 2026-09-07 A5/A20/A21/A38: interpret-side hands were dispatched by a
note and shown none; the roster taught a retired hand so its rulings were
reported unrouted; `inventory`/`entity` never met `inventory_ops`/`entities`;
the establish sheet asked for a crowd op the engine did not know.
"""
from agents.director import (RETIRED_HANDS, SPECIALISTS, _ruling_for,
                             _unrouted_rulings, note_key_targets)
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


def test_dispatch_and_the_unrouted_report_read_the_same_resolver():
    view = {"ledger_notes": {"inventory": "she pockets the key",
                             "offscreen": "a rider is sent",
                             "transit": "nothing"}}
    addressed, named = _ruling_for("objects", view)
    assert addressed == ["note"] and named == ["inventory_ops"]
    addressed, _named = _ruling_for("social", view)
    assert "note" in addressed
    assert _unrouted_rulings(view) == ["transit"]


def test_the_plural_tolerance_knows_y_and_ies():
    assert ("channel", "entities") in note_key_targets("entity")
    assert ("channel", "entities") in note_key_targets("ENTITIES")


def test_the_establish_sheets_crowd_op_spelling_is_tolerated():
    assert _op_word("open") == OP_SET
    assert _op_word("set") == OP_SET
    assert _op_word("levitate") == ""
