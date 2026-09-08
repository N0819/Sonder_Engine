"""A co-player's declaration waits for THEIR frame's next beat (review A71).

Turn indices are chat-GLOBAL -- play order across every frame -- while turn
creation and `_load_extra_players` are per-FRAME. A co-player stationed away
from the frame the host is playing therefore declared against `max(idx) + 1`,
watched a turn take that index in another era, and lost the row: nothing ever
read it again. The window a declaration is pending for is now (this frame's
previous beat, this beat], and the two submit routes reject an index only
when THIS player's own frame has already resolved it.
"""

from __future__ import annotations

import json
import time
import types

import pytest
from fastapi import HTTPException

from agents.narration import _past_narration_extra_block
from agents.runtime import _load_extra_players
from story.character_schema import default_persona_data
from web.app import _reject_resolved_beat, _submit_player_input, guest_state


def _persona(db, name):
    return db.qi("INSERT INTO personas(name,sheet) VALUES(?,?)",
                 (name, json.dumps(default_persona_data(name))))


def _frame(db, chat_id, label):
    return db.qi(
        "INSERT INTO frames(chat_id,label,created) VALUES(?,?,?)",
        (chat_id, label, time.time()))


def _turn(db, chat_id, idx, frame_id, with_step=True):
    tid = db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (chat_id, idx, "", time.time(), frame_id))
    if with_step:
        db.qi("INSERT INTO steps(turn_id,ord,key,label) VALUES(?,?,?,?)",
              (tid, 0, "narrator", "Narrator"))
    return tid


def _chat(db, extras_frame):
    """A chat whose host plays the present frame and whose co-player is
    stationed in an era of their own."""
    primary = _persona(db, "Primary")
    chat_id = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Two eras", "", time.time(), primary))
    guest = _persona(db, "Guest")
    frame_id = _frame(db, chat_id, "elsewhen") if extras_frame else None
    db.qi("INSERT INTO chat_personas(chat_id,persona_id,status,frame_id) "
          "VALUES(?,?,?,?)", (chat_id, guest, "active", frame_id))
    return chat_id, guest, frame_id


def test_a_declaration_survives_a_beat_another_frame_took(temp_db):
    chat_id, guest, frame_id = _chat(temp_db, extras_frame=True)
    _turn(temp_db, chat_id, 0, frame_id)          # the guest's era, beat 0
    # The guest declares for what the page offered as the next index...
    _submit_player_input(chat_id, 1, guest, "I open the hatch")
    # ...and the host runs beat 1 in the PRESENT frame instead.
    _turn(temp_db, chat_id, 1, None)
    # The guest's own frame resolves next at index 2: the declaration is
    # still theirs, not lost with the index another era spent.
    extras = _load_extra_players(chat_id, 2, frame_id)
    assert [e["input"] for e in extras] == ["I open the hatch"]
    assert [e["idle"] for e in extras] == [False]


def test_a_beat_this_frame_already_resolved_does_not_come_back(temp_db):
    chat_id, guest, frame_id = _chat(temp_db, extras_frame=True)
    _submit_player_input(chat_id, 0, guest, "I open the hatch")
    _turn(temp_db, chat_id, 0, frame_id)          # consumed here
    extras = _load_extra_players(chat_id, 1, frame_id)
    assert [e["input"] for e in extras] == [""]
    assert [e["idle"] for e in extras] == [True]


def test_the_most_recent_declaration_wins(temp_db):
    chat_id, guest, frame_id = _chat(temp_db, extras_frame=True)
    _turn(temp_db, chat_id, 0, frame_id)
    _submit_player_input(chat_id, 1, guest, "I open the hatch")
    _turn(temp_db, chat_id, 1, None)
    _submit_player_input(chat_id, 2, guest, "I wait instead")
    extras = _load_extra_players(chat_id, 3, frame_id)
    assert [e["input"] for e in extras] == ["I wait instead"]


def test_one_frame_folds_exactly_the_beat_it_always_did(temp_db):
    """The degenerate case -- everyone stationed together -- is unchanged."""
    chat_id, guest, _frame_id = _chat(temp_db, extras_frame=False)
    _turn(temp_db, chat_id, 0, None)
    _submit_player_input(chat_id, 1, guest, "I follow her")
    assert [e["input"] for e in _load_extra_players(chat_id, 1, None)] == [
        "I follow her"]
    # And a declaration filed for a beat that has not arrived yet is not
    # dragged backwards into this one.
    _submit_player_input(chat_id, 2, guest, "later")
    assert [e["input"] for e in _load_extra_players(chat_id, 1, None)] == [
        "I follow her"]


def test_another_era_taking_the_index_is_not_a_resolved_beat(temp_db):
    chat_id, guest, frame_id = _chat(temp_db, extras_frame=True)
    # `turns` is UNIQUE(chat_id, idx), so an index belongs to exactly one
    # beat of one era -- which is the whole reason a guest declaring against
    # the chat's next index can watch another frame take it.
    _turn(temp_db, chat_id, 4, None)              # the host's era resolved it
    _reject_resolved_beat(chat_id, 4, guest)      # not this player's beat
    _turn(temp_db, chat_id, 5, frame_id)          # ...but this one is
    with pytest.raises(HTTPException) as caught:
        _reject_resolved_beat(chat_id, 5, guest)
    assert caught.value.status_code == 409


def test_an_unrun_beat_of_this_frame_still_accepts_a_declaration(temp_db):
    chat_id, guest, frame_id = _chat(temp_db, extras_frame=True)
    _turn(temp_db, chat_id, 4, frame_id, with_step=False)
    _reject_resolved_beat(chat_id, 4, guest)


def test_the_history_block_reads_the_beat_the_line_served(temp_db):
    """The same window, one reader downstream: a co-player's own history
    block is built from `turn_player_inputs` too, and reading it by index
    alone showed them prose describing an action with the line that caused
    it missing."""
    chat_id, guest, frame_id = _chat(temp_db, extras_frame=True)
    _turn(temp_db, chat_id, 0, frame_id)
    _submit_player_input(chat_id, 1, guest, "I open the hatch")
    _turn(temp_db, chat_id, 1, None)              # another era takes index 1
    _turn(temp_db, chat_id, 2, frame_id)          # ...this frame's next beat
    block, _prev = _past_narration_extra_block(
        chat_id, 3, frame_id, guest, depth=8)
    assert "I open the hatch" in block


def test_the_history_block_names_a_line_once(temp_db):
    chat_id, guest, frame_id = _chat(temp_db, extras_frame=True)
    _submit_player_input(chat_id, 0, guest, "I open the hatch")
    _turn(temp_db, chat_id, 0, frame_id)
    _turn(temp_db, chat_id, 1, frame_id)
    block, _prev = _past_narration_extra_block(
        chat_id, 2, frame_id, guest, depth=8)
    assert block.count("I open the hatch") == 1


def _guest_page(chat_id, persona_id):
    """`guest_state` as the guest's own page sees it -- the route is a plain
    function of the grant on the request."""
    request = types.SimpleNamespace(state=types.SimpleNamespace(
        guest_grant={"chat_id": chat_id, "persona_id": persona_id}))
    return {row["idx"]: row for row in guest_state(request)["turns"]}


def test_the_guest_page_shows_the_line_on_the_beat_that_served_it(temp_db):
    """The human's half of the same window: the guest's own transcript hangs
    their line on the beat of THEIR frame that took it, not on the beat of
    another era that merely took the index they filed under."""
    chat_id, guest, frame_id = _chat(temp_db, extras_frame=True)
    _turn(temp_db, chat_id, 0, frame_id)
    _submit_player_input(chat_id, 1, guest, "I open the hatch")
    _turn(temp_db, chat_id, 1, None)              # another era takes index 1
    _turn(temp_db, chat_id, 2, frame_id)          # ...this frame's next beat
    rows = _guest_page(chat_id, guest)
    assert rows[2]["player_input"] == "I open the hatch"
    assert rows[1]["player_input"] is None
    assert rows[0]["player_input"] is None


def test_the_guest_page_still_shows_a_pending_declaration(temp_db):
    """The complement the old keying got right: nothing of this guest's frame
    has served the line yet, so it stays under the index it was filed under."""
    chat_id, guest, frame_id = _chat(temp_db, extras_frame=True)
    _turn(temp_db, chat_id, 0, frame_id)
    _submit_player_input(chat_id, 1, guest, "I open the hatch")
    _turn(temp_db, chat_id, 1, None)              # another era, not theirs
    rows = _guest_page(chat_id, guest)
    assert rows[1]["player_input"] == "I open the hatch"
