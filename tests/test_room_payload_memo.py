"""The Room's per-reply payload memo, and what drops it.

Review 2026-09-07, C21. The Planner and the Dramaturge rebuilt the derived
half of their payload -- the frontier, the cast's minds, the clock, the
packages, the mandates, the status row, the standing proposals -- on every
step of a reply, measured at 0.69 s of a forty-step reply on the bench copy
of chat 114 against 0.02 s held. `room_calls.ReplyMemo` holds that half
until the reply WRITES -- or until a beat lands under it -- so what these
tests are for is the invalidation: a memo that is not dropped serves a
stale world for the rest of the reply, and nothing else in the engine
would notice.
"""
from __future__ import annotations

import json
import time

import pytest

from core.db import wset
from llm import providers
from story import room_conversation as room
from story.room_calls import ReplyMemo, memo_part
from story.room_tools import TOOLS, tool_only_reads
from agents import dramaturge as dg
from agents import story_planner as sp

PLAYER = "The Stranger"


def _story(db, *, turns=2):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Memo", "A port at dusk.", time.time()))
    wset(cid, "scene", {"location": "Port", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone.",
                 "adjacent": [{"to": "shed", "barrier": "open_door"}]},
        "shed": {"name": "Shed", "desc": "Rope and tar.",
                 "adjacent": [{"to": "quay", "barrier": "open_door"}]},
    }, "positions": {PLAYER: "quay"}, "entities": {}, "attire": {}})
    for i in range(turns):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
              "VALUES(?,?,?,?)", (cid, i, "", time.time()))
    return cid


@pytest.fixture
def scripted(monkeypatch):
    def install(role, *steps):
        seen = []

        def call(_role, _system, user, **kw):
            seen.append(json.loads(user))
            return json.dumps(steps[len(seen) - 1] if len(seen) <= len(steps)
                              else {"reply": "done"})
        monkeypatch.setattr(providers, "chat_complete", call)
        return seen
    return install


# ---------------------------------------------------------------------------
# The memo itself
# ---------------------------------------------------------------------------

def test_a_part_is_built_once_until_the_reply_writes():
    memo, built = ReplyMemo(), []

    def build():
        built.append(len(built))
        return {"n": len(built)}

    assert memo_part(memo, "k", build) == {"n": 1}
    assert memo_part(memo, "k", build) == {"n": 1}
    assert len(built) == 1
    memo.wrote()
    assert memo_part(memo, "k", build) == {"n": 2}
    assert len(built) == 2


def test_one_write_drops_every_part_not_only_the_one_that_moved():
    """A write is not told WHAT it changed, so it may not be believed about
    what it did not: a publish moves the packages, the frontier, the plans
    and the clock at once."""
    memo, built = ReplyMemo(), []
    for key in ("frontier", "packages"):
        memo_part(memo, key, lambda k=key: built.append(k))
    memo.wrote()
    for key in ("frontier", "packages"):
        memo_part(memo, key, lambda k=key: built.append(k))
    assert built == ["frontier", "packages", "frontier", "packages"]


def test_without_a_memo_every_part_is_derived_again():
    built = []
    for _ in range(3):
        memo_part(None, "k", lambda: built.append(1))
    assert len(built) == 3


# ---------------------------------------------------------------------------
# What counts as a write
# ---------------------------------------------------------------------------

def test_only_a_tool_the_table_marks_as_a_read_is_a_read():
    assert tool_only_reads("inspect_clock")
    assert tool_only_reads("inspect_rooms")
    # The write section, the research tools and anything unknown all count
    # as writers -- the default is what keeps the memo honest.
    assert not tool_only_reads("publish_package")
    assert not tool_only_reads("new_package")
    assert not tool_only_reads("web_search")
    assert not tool_only_reads("a_tool_nobody_has_written_yet")
    assert not tool_only_reads("")


def test_no_tool_that_writes_through_a_package_is_marked_a_read():
    """The mark is the table's, so it cannot drift from the handler: every
    entry whose name the room writes through must be unmarked."""
    marked = {t["name"] for t in TOOLS if t.get("reads")}
    writers = {"new_package", "edit_package", "draft_operation",
               "remove_operation", "validate_package", "prepare_package",
               "publish_package", "resolve_package", "retire_package"}
    assert not (marked & writers)


# ---------------------------------------------------------------------------
# The Planner's loop
# ---------------------------------------------------------------------------

def test_a_write_tool_makes_the_next_step_read_the_packages_again(temp_db,
                                                                  scripted):
    seen = scripted(sp.PLANNER_ROLE,
                    {"calls": [{"tool": "inspect_clock", "args": {}}]},
                    {"calls": [{"tool": "new_package",
                                "args": {"title": "The tide turns"}}]},
                    {"reply": "drafted"})
    cid = _story(temp_db)
    sp.run_planner(cid, None, text="draft something")
    assert len(seen) == 3
    # A pure read left the payload alone; the draft is in the next one.
    assert seen[0]["packages"] == seen[1]["packages"] == []
    assert [p["title"] for p in seen[2]["packages"]] == ["The tide turns"]


def test_a_rewritten_status_row_is_in_the_next_payload(temp_db, scripted):
    seen = scripted(sp.PLANNER_ROLE,
                    {"status_line": "Weighing the harbour.",
                     "calls": [{"tool": "inspect_clock", "args": {}}]},
                    {"reply": "done"})
    cid = _story(temp_db)
    sp.run_planner(cid, None, text="what is in motion?")
    assert seen[0]["status"]["line"] != "Weighing the harbour."
    assert seen[1]["status"]["line"] == "Weighing the harbour."


def test_a_granted_mandate_is_in_the_next_payload(temp_db, scripted):
    seen = scripted(sp.PLANNER_ROLE,
                    {"grants": [{"text": "You may plan rooms",
                                 "capabilities": ["plan_rooms"]}],
                     "calls": [{"tool": "inspect_clock", "args": {}}]},
                    {"reply": "granted"})
    cid = _story(temp_db)
    sp.run_planner(cid, None, text="you may plan rooms")
    assert seen[0]["mandates"] == []
    assert [m["text"] for m in seen[1]["mandates"]] == ["You may plan rooms"]


def test_a_reply_of_pure_reads_shows_the_same_derived_half_throughout(
        temp_db, scripted):
    seen = scripted(sp.PLANNER_ROLE,
                    {"calls": [{"tool": "inspect_rooms", "args": {}}]},
                    {"calls": [{"tool": "inspect_plans", "args": {}}]},
                    {"reply": "read three times"})
    cid = _story(temp_db)
    sp.run_planner(cid, None, text="what stands ahead?")
    keys = ("story", "clock", "minds", "conversation", "mandates", "withdrawn",
            "status", "frontier", "packages", "pending_proposals")
    for key in keys:
        assert seen[0][key] == seen[1][key] == seen[2][key], key


# ---------------------------------------------------------------------------
# The Dramaturge's pass
# ---------------------------------------------------------------------------

def test_a_filed_proposal_is_in_the_next_dramaturge_payload(temp_db, scripted):
    seen = scripted(dg.DRAMATURGE_ROLE,
                    {"proposals": [{"kind": "pressure", "title": "The tide",
                                    "wants_true": "The quay floods by dawn.",
                                    "why_now": "The moon is full."}],
                     "calls": [{"tool": "search_lore", "args": {"query": "tide"}}]},
                    {"note": "that is enough"})
    cid = _story(temp_db)
    out = dg.propose(cid, None, dial=2)
    assert len(out["proposals"]) == 1
    assert seen[0]["standing_proposals"] == []
    assert [p["title"] for p in seen[1]["standing_proposals"]] == ["The tide"]
    # The stream and the thread did not move, and are the same objects' worth
    # of bytes in both payloads.
    assert seen[0]["stream"] == seen[1]["stream"]
    assert seen[0]["thread"] == seen[1]["thread"]


# ---------------------------------------------------------------------------
# The memo is per reply
# ---------------------------------------------------------------------------

def test_two_replies_do_not_share_a_memo(temp_db, scripted):
    seen = scripted(sp.PLANNER_ROLE, {"reply": "first"}, {"reply": "second"})
    cid = _story(temp_db)
    sp.run_planner(cid, None, text="one")
    sp.run_planner(cid, None, text="two")
    # The second reply built its own payload: the status row the first one
    # left behind is in it.
    assert len(seen) == 2
    assert seen[1]["status"] == room.status(cid, None)


# ---------------------------------------------------------------------------
# A beat is the other writer
# ---------------------------------------------------------------------------

def _from_another_connection(write):
    """Run `write` on another thread, hence another (thread-local) SQLite
    connection -- the shape a beat's commit really has beside a Room reply,
    and the only shape `core.db.data_version` can see: SQLite moves it on
    another connection's commit and never on this connection's own."""
    import threading
    err = []

    def run():
        try:
            write()
        except BaseException as e:      # noqa: BLE001 -- re-raised below
            err.append(e)
    t = threading.Thread(target=run)
    t.start()
    t.join(timeout=10)
    if err:
        raise err[0]


def test_a_beat_landing_under_the_reply_drops_the_memo(temp_db, monkeypatch):
    """THE ROOM IS NOT ALONE IN THE DATABASE. `converse_stream` runs the
    Planner in a daemon thread against no lock -- which is why `run_planner`
    checks `story_rewound_past` at all -- so a turn can commit between two
    steps of one reply, and none of the reply's own writes reports it.

    Measured before this was held (review 2026-09-07, C21 rework): a reply
    of pure reads whose second step ran after a beat kept serving the beat's
    predecessor -- `player_room` "quay" against a scene that said "shed",
    and a `clock.turn_idx` one behind -- for the rest of the reply.
    """
    payloads = []

    def beat():
        # The beat lands between step one and step two: a turn row, and the
        # move it committed.
        temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                   "VALUES(?,?,?,?)",
                   (cid, 2, "walk to the shed", time.time()))
        blob = json.loads(temp_db.q(
            "SELECT value FROM world WHERE chat_id=? AND key='scene'",
            (cid,), one=True)["value"])
        blob["positions"][PLAYER] = "shed"
        wset(cid, "scene", blob)

    def call(_role, _system, user, **kw):
        payloads.append(json.loads(user))
        if len(payloads) == 1:
            _from_another_connection(beat)
            return json.dumps({"calls": [{"tool": "inspect_rooms", "args": {}}]})
        return json.dumps({"reply": "read after the beat"})

    cid = _story(temp_db)
    monkeypatch.setattr(providers, "chat_complete", call)
    sp.run_planner(cid, None, text="what stands ahead?")
    assert len(payloads) == 2
    assert payloads[0]["frontier"]["player_room"] == "quay"
    assert payloads[1]["frontier"]["player_room"] == "shed"
    assert payloads[0]["clock"]["turn_idx"] == 1
    assert payloads[1]["clock"]["turn_idx"] == 2


def test_reading_the_version_every_step_costs_no_re_derivation():
    """The other half of the same rule: a data version that has not moved
    must not drop anything, or the memo would be no memo at all."""
    memo, built = ReplyMemo(), []
    memo.at_version(7)
    memo_part(memo, "frontier", lambda: built.append("frontier"))
    memo.at_version(7)
    memo_part(memo, "frontier", lambda: built.append("frontier"))
    assert built == ["frontier"]
    memo.at_version(8)
    memo_part(memo, "frontier", lambda: built.append("frontier"))
    assert built == ["frontier", "frontier"]


def test_the_dramaturge_pass_drops_its_memo_on_a_beat_too(temp_db, monkeypatch):
    """The same rule at the sibling loop: `propose` reads the data version
    on every step, so a beat under a pass is not served stale there either."""
    payloads = []

    def beat():
        temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                   "VALUES(?,?,?,?)", (cid, 2, "", time.time()))
        sp.write_status(cid, None, line="A beat landed.", questions=[],
                        turn_idx=2)

    def call(_role, _system, user, **kw):
        payloads.append(json.loads(user))
        if len(payloads) == 1:
            _from_another_connection(beat)
            return json.dumps({"calls": [{"tool": "search_lore",
                                          "args": {"query": "tide"}}]})
        return json.dumps({"note": "that is enough"})

    cid = _story(temp_db)
    monkeypatch.setattr(providers, "chat_complete", call)
    dg.propose(cid, None, dial=2)
    assert len(payloads) == 2
    assert payloads[0]["status_line"] != "A beat landed."
    assert payloads[1]["status_line"] == "A beat landed."
