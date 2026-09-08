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
    """A21's own half. The two sheets that ask for `ledger_notes` print the
    roster of hands a key may name, and it is written by hand in each pack.
    While it named the retired `offscreen` hand, a crowd, courier or telling
    ruling keyed exactly as instructed was reported unrouted and the social
    hand did not run. `RETIRED_HANDS` routes such a key now; this keeps the
    sheets from teaching one in the first place, in every language pack --
    a retired name, an invented name, and a live hand left out all fail here.
    """
    import re

    from llm import prompts

    alternation = re.compile(r"[a-z_]+(?:\|[a-z_]+)+")
    hands = set(SPECIALISTS)
    known = hands | set(RETIRED_HANDS)
    for language in ("en", "ja"):
        sheets = {
            "director_interpret": prompts.get_prompt("director_interpret",
                                                     language),
            "prose_author": prompts.prose_author_prompt(None, language),
        }
        for label, text in sheets.items():
            rosters = [set(m.group(0).split("|"))
                       for m in alternation.finditer(text)]
            # WHAT MAKES AN ALTERNATION A ROSTER: it names more than one of
            # the dispatcher's hands, live or retired. One shared word is a
            # coincidence of vocabulary -- the sheets' action-stage enum
            # (`approach|contact|immediate|preparation|sustained`) names a
            # `contact` STAGE and is not this test's business -- and two is a
            # set of hands. Deliberately NOT `roster <= known`: that filter
            # silently discarded a roster carrying an invented name, which is
            # the half of the claim that needs to fail loudly.
            rosters = [r for r in rosters if len(r & known) > 1]
            assert rosters, f"{language} {label} prints no hand roster"
            for roster in rosters:
                assert roster == hands, (
                    f"{language} {label} teaches {sorted(roster)}; the "
                    f"dispatcher has {sorted(hands)}")


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
    view = {"source": "player_declaration",
            "declaration": "she shrugs the coat off onto the chair",
            "player": "Hinami", "cast": [], "declared_actions": [],
            "dice": [], "manifest": [],
            "ledger_notes": {"attire": "the coat is off and on the chair"}}
    payload = _specialist_payload("body", ctx, {}, view, {})
    assert payload["director_note"] == "the coat is off and on the chair"
    assert payload["player_declaration"] == view["declaration"]
    # And no hand is shown another hand's ruling.
    assert "director_note" not in _specialist_payload(
        "spatial", ctx, {}, view, {})
