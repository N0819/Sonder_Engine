"""The voices of one beat are asked at once.

Each onscreen charter body's voice answers the beat from its own view, and the
prompt forbids one referencing another, so nothing one says can reach another
in the same beat. They ran one after another anyway: up to three calls in
series on every beat, 30 s of a 51 s resolve on the playerless Aldermill run
(round 6 idx 3, 2026-09-23).

Running them together must change nothing but the clock: the answers come
back in the order the cap ranked them (the figure index is in every event id,
and the reactor's first answer to a line is the one that keeps it), each call
sees the parent's context (frame, cancellation, call ledger) without its
streaming sinks, and a cancelled turn still stops.
"""
import contextvars
import threading
import time

import pytest

from agents import background
from llm import providers
# The module, not its names: a Test* class imported here is collected twice.
from tests import test_a_charter_body_speaks_before_the_director_resolves as beat

PROBE = contextvars.ContextVar("voices_probe", default=None)


def _declared(monkeypatch, temp_db, react):
    cid = beat._chat(temp_db)
    sc = {**beat.SC, "positions": {"Iris Vale": "scullery"}}
    monkeypatch.setattr(background, "_react_one", react)
    monkeypatch.setattr(background, "_player_room", lambda ctx, sc_: "scullery")
    rows = [{"name": n, "room": "scullery"} for n in ("Cole", "Ada", "Bran")]
    return background.declare_charter_figures(
        beat._ctx(cid), dict(beat.TestTheDeclaredBeatIsWhatTheVoiceHears.INTERP),
        sc, rows, [], 0)


def _nods(name):
    return {"name": name, "room": "scullery", "action": "%s nods" % name,
            "dialogue_log_entry": None, "charter_act": None,
            "charter_offers": []}


def test_three_voices_are_asked_together_and_answer_in_rank_order(
        monkeypatch, temp_db):
    meet = threading.Barrier(3, timeout=5)     # breaks if they ran in series
    lag = {"Ada": 0.2, "Bran": 0.1, "Cole": 0.0}   # finish in reverse
    seen = {}

    def react(ctx, dr, name, *args, **kwargs):
        meet.wait()
        seen[name] = (PROBE.get(), providers.token_sink.get())
        time.sleep(lag[name])
        return _nods(name)

    PROBE.set("parent")
    token = providers.token_sink.set(lambda _piece: None)
    try:
        out = _declared(monkeypatch, temp_db, react)
    finally:
        providers.token_sink.reset(token)
    assert [d["name"] for d in out] == ["Ada", "Bran", "Cole"]
    assert [d["sequence"][0]["event_id"] for d in out] == [
        "turn:7:figure:%d:0:action" % i for i in range(3)]
    # The parent's context reached every call; its stream did not.
    assert seen == {n: ("parent", None) for n in ("Ada", "Bran", "Cole")}


def test_a_silent_voice_keeps_its_rank_index(monkeypatch, temp_db):
    out = _declared(monkeypatch, temp_db,
                    lambda ctx, dr, name, *a, **k: None if name == "Ada" else _nods(name))
    assert [(d["name"], d["sequence"][0]["event_id"]) for d in out] == [
        ("Bran", "turn:7:figure:1:0:action"), ("Cole", "turn:7:figure:2:0:action")]


def test_one_voice_runs_as_it_always_did():
    caller = threading.get_ident()
    assert background._voices_at_once([lambda: threading.get_ident()]) == [caller]
    assert background._voices_at_once([]) == []


def test_a_cancelled_turn_still_stops():
    def cancelled():
        raise providers.Aborted("generation aborted by user")

    with pytest.raises(providers.Aborted):
        background._voices_at_once([lambda: "said", cancelled])


def test_any_other_failure_is_raised_as_the_loop_would_have():
    def broken():
        raise ValueError("first")

    def also_broken():
        raise KeyError("second")

    with pytest.raises(ValueError, match="first"):
        background._voices_at_once([broken, lambda: "said", also_broken])
