"""The story bible (`story/room_bible.py`): the Writers' Room's narrative
memory. Typed state first, particulars with sources, sections not a
summary, an unpaid setup that never falls off, a reversal that keeps both
lines, a fold that refuses what it cannot trace, and a block served to the
agents and to no mind.
"""
from __future__ import annotations

import json
import time

import pytest

from core.db import FRAME_SCOPED_WORLD_KEYS
from llm import providers
from story import room_bible as rb
from story import room_conversation as room


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Bible", "A port at dusk.", time.time()))
    for i in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (cid, i, "", time.time()))
    return cid


def test_the_key_is_frame_scoped_and_an_entry_needs_a_real_source(temp_db):
    cid = _story(temp_db)
    assert rb.BIBLE_KEY in FRAME_SCOPED_WORLD_KEYS
    with pytest.raises(ValueError):
        rb.add_entry(cid, None, "wants", "The player wants a harbour.", [])
    with pytest.raises(ValueError):
        rb.add_entry(cid, None, "wants", "The player wants a harbour.", ["msg:999"])
    with pytest.raises(ValueError):
        rb.add_entry(cid, None, "moods", "gloomy", ["turn:1"])
    msg = room.add_message(cid, None, "player", "Give me a harbour by turn ten.")
    entry, fresh = rb.add_entry(cid, None, "wants",
                                "At beat 2 the player asked for 'a harbour by turn ten'.",
                                ["msg:%d" % msg["id"]], since_turn=2)
    assert fresh and entry["source"] == ["msg:%d" % msg["id"]]
    again, fresh = rb.add_entry(cid, None, "wants",
                                "At beat 2 the player asked for 'a harbour by turn ten'.",
                                ["msg:%d" % msg["id"]])
    assert not fresh and again["uid"] == entry["uid"]
    # Every source prefix the story holds is a source; a turn is one.
    turn_entry, _ = rb.add_entry(cid, None, "open_loops",
                                 "Who rang the bell at beat 1 is unanswered.", ["turn:1"])
    assert turn_entry["section"] == "open_loops"


def test_a_reversal_keeps_both_lines_and_an_unpaid_setup_never_falls_off(temp_db):
    cid = _story(temp_db)
    a, _ = rb.add_entry(cid, None, "wants", "Wanted a quiet harbour (beat 1).",
                        ["turn:1"], since_turn=1)
    b, _ = rb.add_entry(cid, None, "wants", "Reversed at beat 2: wants a storm.",
                        ["turn:2"], since_turn=2, supersedes=a["uid"])
    wants = rb.entries(cid, None, "wants")
    assert [e["uid"] for e in wants] == [a["uid"], b["uid"]]
    assert wants[0]["superseded_by"] == b["uid"]
    # Fill the setups past the cap: unpaid setups survive, the section grows.
    for n in range(rb.BIBLE_ENTRIES_PER_SECTION + 3):
        rb.add_entry(cid, None, "setups", "Setup %d planted at the quay." % n,
                     ["turn:1"], since_turn=1)
    assert len(rb.entries(cid, None, "setups")) == rb.BIBLE_ENTRIES_PER_SECTION + 3
    # Another section evicts its oldest past the cap.
    for n in range(rb.BIBLE_ENTRIES_PER_SECTION + 3):
        rb.add_entry(cid, None, "decided", "Decision %d." % n, ["turn:1"])
    decided = rb.entries(cid, None, "decided")
    assert len(decided) == rb.BIBLE_ENTRIES_PER_SECTION
    assert decided[0]["text"] == "Decision 3."


def test_a_paid_setup_moves_and_the_block_shows_unpaid_first(temp_db):
    cid = _story(temp_db)
    setup, _ = rb.add_entry(cid, None, "setups", "A sealed letter was planted at the quay (beat 1).",
                            ["turn:1"], since_turn=1)
    rb.add_entry(cid, None, "voice", "Slow dread, the player said.", ["turn:1"])
    block = rb.render_block(cid, None)
    assert block.index("setups, unpaid:") < block.index("voice:")
    assert "sealed letter" in block and "Serve it to no mind" in block
    paid = rb.mark_paid(cid, None, setup["uid"], "The letter was read at beat 3.", ["turn:2"],
                        turn_idx=3)
    assert paid["section"] == "paid" and paid["paid"]
    assert rb.entries(cid, None, "setups")[0]["paid"]
    assert "setups, unpaid:" not in rb.render_block(cid, None)
    assert rb.mark_paid(cid, None, "bib_nobody", "x", ["turn:1"]) is None
    assert rb.render_block(cid, None, limit=80) == "" or len(rb.render_block(cid, None, limit=400)) <= 402


def test_the_fold_reads_only_lines_past_the_window_and_refuses_the_untraceable(
        temp_db, monkeypatch):
    cid = _story(temp_db)
    ids = [room.add_message(cid, None, "player", "line %d" % n)["id"] for n in range(20)]
    assert rb.pending_fold_count(cid, None, window=30) == 0
    batch = rb.unfolded_messages(cid, None, window=8)
    assert [m["id"] for m in batch] == ids[:12]
    seen = []

    def script(role, system, user, **kw):
        assert role == rb.BIBLE_ROLE
        payload = json.loads(user)
        seen.append(payload)
        return json.dumps({"entries": [
            {"section": "wants", "text": "At beat 0 the player wrote 'line 3'.",
             "source": ["msg:%d" % ids[3]], "since_turn": 0},
            {"section": "promises", "text": "No source here.", "source": []},
            {"section": "decided", "text": "Cites a ghost.", "source": ["plot:nothing"]},
            {"section": "nope", "text": "Bad section.", "source": ["msg:%d" % ids[0]]},
        ]})
    monkeypatch.setattr(providers, "chat_complete", script)
    report = rb.fold(cid, None, window=8, turn_idx=2)
    assert report == {"folded": 12, "kept": 1, "refused": 3,
                      "notes": report["notes"]}
    assert len(report["notes"]) == 3
    assert [l["ref"] for l in seen[0]["lines"]][:2] == ["msg:%d" % ids[0], "msg:%d" % ids[1]]
    assert rb.bible(cid, None)["folded_through"] == ids[11]
    assert rb.pending_fold_count(cid, None, window=8) == 0
    # The next fold starts after the last folded line.
    for n in range(20, 24):
        room.add_message(cid, None, "planner", "line %d" % n)
    assert [m["id"] for m in rb.unfolded_messages(cid, None, window=8)][0] == ids[12]


def test_publish_and_resolve_add_deterministic_lines(temp_db):
    from story.plot_packages import new_package
    cid = _story(temp_db)
    pkg = new_package(cid, title="The Harbour", premise="p")
    entry = rb.note_publish(cid, None, package_uid=pkg["uid"], title="The Harbour", turn_idx=2)
    assert entry["section"] == "decided" and pkg["uid"] in entry["source"]
    paid = rb.note_resolve(cid, None, package_uid=pkg["uid"], title="The Harbour", turn_idx=3)
    assert paid["section"] == "paid"
    assert rb.note_publish(cid, None, package_uid="plot:ghost", title="x", turn_idx=1) is None


def test_the_fold_job_is_queued_only_past_the_batch(temp_db, monkeypatch):
    from core import jobs
    cid = _story(temp_db)
    ids = [room.add_message(cid, None, "player", "line %d" % n)["id"]
           for n in range(rb.BIBLE_FOLD_BATCH + 3)]
    assert rb.schedule_fold(cid, None, window=30) is None
    monkeypatch.setattr(providers, "chat_complete",
                        lambda *a, **k: json.dumps({"entries": []}))
    job = rb.schedule_fold(cid, None, window=3, base_turn=2)
    assert job is not None and job.key == rb.BIBLE_JOB_KEY
    deadline = time.time() + 10.0
    while job.state in ("pending", "running") and time.time() < deadline:
        time.sleep(0.02)
    assert job.state == "done", (job.state, job.error)
    assert job.result["folded"] == rb.BIBLE_FOLD_BATCH
    assert rb.bible(cid, None)["folded_through"] == ids[rb.BIBLE_FOLD_BATCH - 1]
    jobs.drain(timeout=1.0)
