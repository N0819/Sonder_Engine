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


def test_no_sheet_teaches_a_roster_the_dispatcher_does_not_have(temp_db):
    """Publish each current route; default surface work names its body owner."""

    from llm import prompts
    from llm.schemas import CAUSAL_CATEGORY_REDIRECTS

    channels = {
        CAUSAL_CATEGORY_REDIRECTS.get(channel, channel)
        for spec in SPECIALISTS.values()
        for channel in spec["channels"]
    }
    for language in ("en", "ja"):
        sheet = prompts.prose_author_prompt(None, language)
        missing = sorted(channel for channel in channels
                         if channel not in sheet)
        assert not missing, f"{language} omits routed channels {missing}"
        for retired in RETIRED_HANDS:
            assert f"{retired}:" not in sheet


def test_an_interpret_side_hand_is_shown_the_ruling_that_dispatched_it(
        temp_db):
    """A5's other half, pinned at the payload rather than at the resolver.

    The note lookup sits ABOVE the source branch: an interpret-side hand is
    dispatched BY a ruling, its sheet ends with "no note and no manifest
    entry: encode nothing", and the interpret manifest is always empty -- so
    a hand shown no note had been told, by its own sheet, to encode nothing.
    """
    import time

    from agents.director import _specialist_payload

    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) "
                     "VALUES(?,?,?)", ("Test", "", time.time()))

    class _Ctx:
        chat = {"id": cid}

    ctx = _Ctx()
    view = {"source": "causal_ledger", "player": "Hinami", "cast": [],
            "declared_actions": [], "dice": [], "dialogue": [],
            "manifest": [], "ledger_notes": {}, "spans": [{
                "chrono_id": 1, "event_id": 1, "item_id": 1,
                "object_name": "coat", "source_entity_id": "persona:1",
                "authority_mode": "actor_only", "kind": "action",
                "event": "shrugs the coat off onto the chair",
                "resolution_notes": "the coat is off and on the chair",
                "categories": ["attire"],
            }]}
    payload = _specialist_payload("body", ctx, {}, view, {})
    assert payload["ledgers"][0]["resolution_notes"] == \
        "the coat is off and on the chair"
    assert "item_id" not in payload["ledgers"][0]
    assert "chrono_id" not in payload["ledgers"][0]
    assert "ledgers" not in _specialist_payload(
        "spatial", ctx, {}, view, {})
