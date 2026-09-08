"""Every out-of-band Writers' Room job carries the turn it was computed from.

Review 2026-09-07 finding A33. A Dramaturge pass runs in a job, and the story
can move -- or go BACK -- underneath it. Both rewind guards open the same way:
`run_planner`'s per-write check (`if base_turn is not None and
story_rewound_past(...)`) and `run_dramaturge_pass`'s own. So a `None` base
turn is not a missing number, it is the guard switched off.

The commit tail passes `turn_idx` for exactly that reason. `planner_reply` --
the panel's own door into the same act -- passed a hardcoded `base = None`, so
a pass a player launched by asking the Room a question could land proposals,
judgements and revisions onto a story that had been rewound beneath it, and
the guard written to stop that never ran.
"""

from __future__ import annotations

import json
import time

import pytest

from core.db import wset
from llm import providers
from story import mandates as md
from story import room_conversation as room
from agents import story_planner as sp

PLAYER = "The Stranger"


def _story(db, *, turns=3):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Base turn", "A port at dusk.", time.time()))
    wset(cid, "scene", {"location": "Port",
                        "rooms": {"quay": {"name": "Quay", "desc": "Wet stone."}},
                        "positions": {PLAYER: "quay"}, "entities": {},
                        "attire": {}})
    for i in range(turns):
        tid = db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (cid, i, "I walk the quay (beat %d)." % i, time.time()))
        sid = db.qi("INSERT INTO steps(turn_id,key,label,ord) VALUES(?,?,?,?)",
                    (tid, "narrator", "Narrator", 9))
        db.qi("INSERT INTO variants(step_id,content,created,active) "
              "VALUES(?,?,?,1)",
              (sid, json.dumps({"prose": "The tide climbs (beat %d)." % i}),
               time.time()))
    return cid


class _Script:
    """One scripted planner reply that hands a brief to the Dramaturge."""

    def __call__(self, role, *args, **kwargs):
        return json.dumps({"reply": "I will ask the Dramaturge.",
                           "to_dramaturge": "Something should go wrong at the "
                                            "quay.",
                           "calls": []})


@pytest.fixture
def _no_real_calls(monkeypatch):
    monkeypatch.setattr(providers, "chat_complete", _Script())


def test_a_panel_launched_dramaturge_pass_states_the_turn_it_ran_from(
        temp_db, monkeypatch, _no_real_calls):
    """The defect: the panel's door passed None and the guard never ran."""
    from core import jobs
    cid = _story(temp_db)
    md.grant_mandate(cid, None, text="Surprise me a little.",
                     capabilities=["plan_entity"], limits={"surprise": 1})
    seen = {}

    def _capture_pass(chat_id, frame_id, *, base_turn=None, brief=None,
                      job=None):
        seen["pass_base_turn"] = base_turn
        return {"skipped": "captured"}

    def _capture_submit(chat_id, key, fn, *, base_turn=None, **kwargs):
        # Run it here rather than on a thread: what is under test is the
        # number, and a job that has to be waited for is a flaky test.
        seen["job_base_turn"] = base_turn
        seen["result"] = fn(None)
        return None

    monkeypatch.setattr(sp, "run_dramaturge_pass", _capture_pass)
    monkeypatch.setattr(jobs, "submit", _capture_submit)

    out = sp.planner_reply(cid, None, "What should happen next?")

    assert out["reply"]
    # BOTH halves state it: the job record the panel can read back, and the
    # pass whose own guard opens `if base_turn is not None`.
    assert seen.get("job_base_turn") == room.current_turn_idx(cid) == 2
    assert seen.get("pass_base_turn") == 2


def test_the_number_is_what_the_rewind_guard_needs(temp_db):
    """And it is the same number the commit tail passes: the guard refuses a
    pass whose story has gone back underneath it, and answers nothing at all
    for a pass that never stated a turn."""
    from core.jobs import story_rewound_past
    cid = _story(temp_db)
    now = room.current_turn_idx(cid)

    assert story_rewound_past(now, now - 1) is True
    assert story_rewound_past(None, now - 1) is False
