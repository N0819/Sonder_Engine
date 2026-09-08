"""A setup is marked paid only once its payoff can be filed (A65).

`mark_paid` set `paid` on the setup, saved the bible, and only then built the
`paid` line -- which `add_entry` may refuse (no sentence, no source, a source
the story does not hold). The setup was then flagged as a promise kept with no
payoff line anywhere, and out of the eviction protection that keeps an unpaid
setup in the bible forever.
"""
from __future__ import annotations

import time

import pytest

from story import room_bible as rb
from story import room_conversation as room


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Bible", "A port at dusk.", time.time()))
    for i in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
              "VALUES(?,?,?,?)", (cid, i, "", time.time()))
    return cid


def _setup(cid):
    entry, _ = rb.add_entry(
        cid, None, "setups",
        "A sealed letter was planted at the quay (beat 1).",
        ["turn:1"], since_turn=1)
    return entry


REFUSED = [
    pytest.param("", ["turn:2"], id="no sentence"),
    pytest.param("The letter was read.", [], id="no source"),
    pytest.param("The letter was read.", ["turn:999"], id="untraceable source"),
]


@pytest.mark.parametrize("text,sources", REFUSED)
def test_a_refused_payoff_leaves_the_setup_unpaid(temp_db, text, sources):
    cid = _story(temp_db)
    setup = _setup(cid)
    with pytest.raises(ValueError):
        rb.mark_paid(cid, None, setup["uid"], text, sources, turn_idx=3)

    assert rb.entries(cid, None, "setups")[0]["paid"] is False
    assert rb.entries(cid, None, "paid") == []
    # And it is still protected: an unpaid setup never leaves the bible.
    assert "setups, unpaid:" in rb.render_block(cid, None)


def test_a_payoff_that_files_marks_the_setup(temp_db):
    cid = _story(temp_db)
    setup = _setup(cid)
    paid = rb.mark_paid(cid, None, setup["uid"],
                        "The letter was read at beat 3.", ["turn:2"],
                        turn_idx=3)
    assert paid["section"] == "paid" and paid["paid"]
    assert rb.entries(cid, None, "setups")[0]["paid"] is True


def test_an_unknown_setup_with_a_fileable_payoff_writes_nothing(temp_db):
    """The pre-existing None answer, and it still leaves no `paid` line."""
    cid = _story(temp_db)
    _setup(cid)
    room.add_message(cid, None, "player", "anything")
    assert rb.mark_paid(cid, None, "bib_nobody",
                        "Something was read.", ["turn:2"]) is None
    assert rb.entries(cid, None, "paid") == []
    assert rb.entries(cid, None, "setups")[0]["paid"] is False
