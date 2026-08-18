"""The reasoning trace has to cross a thread to reach the row it belongs to.

Every pipeline step runs its model call on a worker thread (`_stream_one`
spawns one and streams through a bus), and `save_step` writes the row on the
GENERATOR thread once that worker has finished. `providers.last_reasoning` is a
ContextVar, so a value the worker set was never visible where it was read.

The result: 0 stored traces in 27,020 variants on a live install, for as long
as the column had existed. The API serves the field, the pipeline drawer has an
"Expand reasoning" panel for it, and both had always been shown nothing --
which is why a reader could watch a detailed in-character plan stream past in
the technical detail and have no way to copy it afterwards.

This is the fan-out contextvar hazard `agents/director.py` documents, in the
direction that one does not cover: copying a context INTO a worker carries
values inward, and nothing carries a value the worker produced back out.
"""

from __future__ import annotations

import queue

from llm import providers
from agents.runtime import _stream_one
from agents.storage import save_step


class _Bus:
    def __init__(self):
        self.q = queue.Queue()


def _run(step):
    bus, holder = _Bus(), {}
    for _ in _stream_one(bus, "narrator", step, holder):
        pass
    return holder


TRACE = "She is lying about the door. Plan: press once, then let the silence sit."


def test_a_trace_set_in_the_worker_reaches_the_caller():
    holder = _run(lambda: (providers.last_reasoning.set(TRACE),
                           {"prose": "ok"})[1])
    assert holder["reasoning"] == TRACE


def test_the_parent_context_never_sees_it_which_is_the_bug():
    """The proof that the hand-off is load-bearing rather than belt-and-braces:
    reading the ContextVar here -- which is exactly what `save_step` used to do
    -- still returns nothing."""
    providers.last_reasoning.set(None)
    _run(lambda: (providers.last_reasoning.set(TRACE), {"prose": "ok"})[1])
    assert providers.last_reasoning.get() is None


def test_it_lands_on_the_stored_variant(temp_db):
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("t", "", 0))
    turn = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat, 0, "", 0))
    holder = _run(lambda: (providers.last_reasoning.set(TRACE),
                           {"prose": "ok"})[1])
    save_step(turn, "narrator", "Narrator", 0, {"prose": "ok"},
              reasoning=holder.get("reasoning"))
    row = temp_db.q("SELECT reasoning FROM variants ORDER BY id DESC LIMIT 1",
                    one=True)
    assert row["reasoning"] == TRACE


def test_a_step_that_reasoned_about_nothing_stores_nothing(temp_db):
    """Absence must stay absence -- an empty panel is correct for a model that
    does not expose a trace, and a placeholder would read as one that does."""
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("t", "", 0))
    turn = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat, 0, "", 0))
    providers.last_reasoning.set(None)
    holder = _run(lambda: {"prose": "ok"})
    save_step(turn, "narrator", "Narrator", 0, {"prose": "ok"},
              reasoning=holder.get("reasoning"))
    row = temp_db.q("SELECT reasoning FROM variants ORDER BY id DESC LIMIT 1",
                    one=True)
    assert not row["reasoning"]


def test_a_long_trace_is_bounded(temp_db):
    """A reasoning model bills its thinking as output -- `providers.py` records
    11-13k tokens of it on one maze arm -- so the column takes a bounded slice
    rather than whatever arrives."""
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("t", "", 0))
    turn = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat, 0, "", 0))
    save_step(turn, "narrator", "Narrator", 0, {"prose": "ok"},
              reasoning="x" * 50000)
    row = temp_db.q("SELECT reasoning FROM variants ORDER BY id DESC LIMIT 1",
                    one=True)
    assert len(row["reasoning"]) == 20000


def test_the_reader_can_actually_get_at_it():
    """Storing it is only half: the drawer has to hand it over. Both halves
    existed and had never met."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parents[1]
    assert "reasoning FROM variants" in (root / "web" / "app.py").read_text(
        encoding="utf-8")
    chat_js = (root / "static" / "js" / "chat.js").read_text(encoding="utf-8")
    assert "variant.reasoning" in chat_js
