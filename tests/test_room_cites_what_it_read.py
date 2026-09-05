"""A recap states what the ledgers say and cites the rows it read.

Measured 2026-09-05. The caravanserai run's recap said a character was
"feigning sleep while listening intently" (his ledger says watchful and
hooded, never asleep) and that another had "sent a servant to alert Gate
Warden Vesk" (nothing was sent). The road run's said a salve was offered
and "she declined" (the ledger holds a contact and a transfer, and no
refusal). The class is not lying: the room reads ledgers and renders them
as motives, and nothing between the reading and the rendering asked which
row said so.

The contract is `story/room_citations.py`. A claim cites the rows it came
from; a proposal cites nothing and says it is one; a claim citing no row
the room actually read this reply is DEMOTED to a proposal -- it keeps its
sentence and loses the authority it was borrowing.
"""

import pytest

from story import room_citations as cite


def test_a_claim_citing_a_row_the_room_read_stands():
    with cite.reading():
        cite.note_reads("inspect_minds",
                        {"minds": [{"uid": "halvard", "beliefs": []}]})
        out = cite.check_claims([
            {"text": "Halvard is watchful", "cites": ["halvard"]}])
    assert out["claims"][0]["verdict"] == "supported"
    assert out["asserted"] == ["Halvard is watchful"]
    assert out["unsupported"] == []


def test_a_claim_with_no_row_is_refused_as_an_assertion():
    """"Tamsin sent a servant to alert Gate Warden Vesk" -- nothing was."""
    with cite.reading():
        cite.note_reads("inspect_events", {"events": [{"id": "ev_1"}]})
        out = cite.check_claims([
            {"text": "Tamsin sent a servant to alert the gate warden",
             "cites": ["errand_vesk"]}])
    claim = out["claims"][0]
    assert claim["verdict"] == "unsupported"
    assert claim["missing"] == ["errand_vesk"]
    assert out["asserted"] == []
    assert claim["text"] in out["proposed"], (
        "an unsupported claim is demoted to a proposal, never deleted")


def test_a_claim_citing_nothing_at_all_is_unsupported():
    """"Halvard was feigning sleep" arrived as prose with no row behind it,
    which is the shape the measured failures actually had."""
    with cite.reading():
        cite.note_reads("inspect_minds", {"minds": [{"uid": "halvard"}]})
        out = cite.check_claims([{"text": "Halvard was feigning sleep"}])
    assert out["claims"][0]["verdict"] == "unsupported"
    assert out["claims"][0]["uncited"] is True


def test_a_proposal_needs_no_row():
    """The room stays free to suggest. That is its job, and the contract is
    about marking the difference, not narrowing what it may offer."""
    with cite.reading():
        out = cite.check_claims([
            {"text": "a courier could arrive at dusk", "proposal": True}])
    assert out["claims"][0]["verdict"] == "proposal"
    assert out["unsupported"] == []
    assert out["proposed"] == ["a courier could arrive at dusk"]


def test_a_reply_that_enumerated_nothing_says_so():
    """Silence is not a clean bill: it is the same silence the contract
    exists to end."""
    with cite.reading():
        assert cite.check_claims([])["stated_nothing"] is True
        assert cite.check_claims(None)["stated_nothing"] is True


def test_rows_are_harvested_from_ids_and_from_the_keys_of_a_table():
    """Both halves of how this engine spells a row: an `uid`/`id` field,
    and a mapping FROM ids to records."""
    with cite.reading():
        cite.note_reads("read_scene", {
            "rooms": {"lamp_room": {"name": "Lamp room"},
                      "watch_room": {"name": "Watch room"}},
            "positions": [{"body": "corin", "room": "lamp_room"}]})
        rows = cite.rows_read()
    assert {"lamp_room", "watch_room", "corin"} <= rows


def test_the_ledger_is_one_reply_long():
    """A room recapping from what it remembers of an earlier session is the
    failure; memory is not a ledger."""
    with cite.reading():
        cite.note_reads("inspect_rooms", {"rooms": [{"uid": "hall"}]})
        assert "hall" in cite.rows_read()
    assert cite.rows_read() == set()
    with cite.reading():
        out = cite.check_claims([{"text": "the hall is empty",
                                  "cites": ["hall"]}])
    assert out["claims"][0]["verdict"] == "unsupported"


def test_a_tool_result_fills_the_ledger_through_the_one_call_site(temp_db):
    """`run_tool` is where every read passes, so it is where the ledger is
    filled -- no tool has to remember to."""
    from core import db
    from story import room_tools

    chat_id = db.qi("INSERT INTO chats(name,created) VALUES('t',0)")
    pkg = room_tools.run_tool(chat_id, "new_package",
                              {"title": "The courier",
                               "premise": "someone comes"}, host=True)
    with cite.reading():
        room_tools.run_tool(chat_id, "inspect_packages", {}, host=True)
        assert pkg["uid"] in cite.rows_read(), (
            "a row the room read through the one call site is a row it may "
            "cite, and no tool had to remember to say so")


def test_the_room_reply_carries_its_citations(temp_db):
    """End to end through the seam the panel uses."""
    from core import db
    from story import room_conversation as room

    chat_id = db.qi("INSERT INTO chats(name,created) VALUES('t',0)")

    def planner(cid, frame_id, text, **kw):
        cite.note_reads("inspect_minds", {"minds": [{"uid": "halvard"}]})
        return {"reply": "Halvard is watchful; he may be feigning sleep.",
                "claims": [
                    {"text": "Halvard is watchful", "cites": ["halvard"]},
                    {"text": "Halvard is feigning sleep",
                     "cites": ["halvard_sleep"]}]}

    room.seat_planner(planner)
    try:
        out = room.converse(chat_id, None, "what is going on?")
    finally:
        room.seat_planner(None)
    assert out["citations"]["asserted"] == ["Halvard is watchful"]
    assert out["citations"]["unsupported"] == ["Halvard is feigning sleep"]


def test_the_contract_the_room_is_given_is_the_one_that_is_checked():
    """The sentence and the check live in one module so they cannot drift."""
    assert "proposal" in cite.CONTRACT_TEXT
    assert "cites" in cite.CONTRACT_TEXT
