"""Aborting one turn costs that turn's embeddings, never another's.

The coalescer (`providers._coalesced_embed`) lets concurrent callers share one
request: whoever arrives first leads, and everyone queued behind it is served
by the leader. It served them ON THE LEADER'S CONTEXT -- the leader's cancel
event, the leader's ledger sink -- so a player aborting chat A closed the
request chat B's commit (or a consolidation job) was queued behind, and the
retry, seeing A's event set, degraded B to the crc32 hash. B never aborted;
its rows were written with `cheap:crc32:256` vectors, keyword-only recall
until a rebuild (review 2026-11-01, llm_providers_quality F2, reproduced:
"A fallback=True ... B fallback=True ... generation aborted by user"). On the
success path B's request was booked to A's step and B's ledger got nothing.

A group is now served on its own callers' context: callers queue together
only behind the same cancel event, the request runs under that event, and
each caller's share of the round trip lands on its own ledger.
"""
from __future__ import annotations

import threading
import time

import numpy as np
import pytest

from llm import providers


@pytest.fixture(autouse=True)
def _clean_queue():
    providers._COALESCE_QUEUE[:] = []
    providers._COALESCE_INFLIGHT = False
    providers._EMBED_FALLBACK_SAID.clear()
    providers._embed_dead_forget()
    yield
    providers._COALESCE_QUEUE[:] = []
    providers._COALESCE_INFLIGHT = False


def _wait_until(predicate, what, timeout=20.0):
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError(f"timed out waiting for {what}")
        time.sleep(0.001)


def _fake_request(monkeypatch, *, hold=None):
    """`_embed_request` as the wire behaves: a closed request (the run's
    cancel event set) raises `Aborted`; otherwise one vector per text, and
    one ledger entry for the round trip, as the real one records."""
    sent = []

    def request(texts):
        sent.append(list(texts))
        if hold is not None and len(sent) == 1:
            hold.wait(30)
        providers._check_cancel()
        providers.record_llm_call({
            "role": "embeddings", "requested": "m", "served": "m",
            "in": 10 * len(texts), "out": 0, "cached": 0, "duration": 0.01,
            "kind": "embedding", "texts": len(texts)})
        return providers.EmbeddingBatch(
            vectors=[np.ones(4, dtype=np.float32) for _ in texts],
            model_key="fake:1:m", dimensions=4, fallback=False)

    monkeypatch.setattr(providers, "_embed_request", request)
    monkeypatch.setattr(providers.time, "sleep", lambda _s: None)
    return sent


def _caller(texts, results, name, *, cancel=None, ledger=None):
    def run():
        if cancel is not None:
            providers.cancel_event.set(cancel)
        if ledger is not None:
            providers.call_ledger_sink.set(ledger.append)
        results[name] = providers.embed_texts_meta(texts)
    return threading.Thread(target=run)


def test_a_follower_from_another_run_is_not_degraded_by_the_leaders_abort(
        monkeypatch):
    held = threading.Event()
    sent = _fake_request(monkeypatch, hold=held)
    ev_a, ev_b = threading.Event(), threading.Event()
    results, ledger_a, ledger_b = {}, [], []
    a = _caller(["chat A's memory"], results, "a", cancel=ev_a, ledger=ledger_a)
    a.start()
    _wait_until(lambda: sent, "chat A's request to go out")
    b = _caller(["chat B's memory"], results, "b", cancel=ev_b, ledger=ledger_b)
    b.start()
    _wait_until(lambda: len(providers._COALESCE_QUEUE) >= 1,
                "chat B to queue behind chat A")
    ev_a.set()          # the player aborts chat A
    held.set()
    a.join(30)
    b.join(30)

    assert results["a"].fallback, "the aborted turn's own embedding degrades"
    assert not results["b"].fallback, (
        "chat B never aborted: its vectors must be the provider's, not crc32")
    assert results["b"].model_key == "fake:1:m"
    assert ledger_a == []
    assert [e["texts"] for e in ledger_b] == [1]


def test_callers_of_one_run_still_share_a_request_and_split_its_ledger(
        monkeypatch):
    """The coalescing itself is kept: two of one run's callers queued behind
    a leader cost one request, and each books its own share of it."""
    held = threading.Event()
    sent = _fake_request(monkeypatch, hold=held)
    ev = threading.Event()
    results, lead_ledger, one, two = {}, [], [], []
    lead = _caller(["lead"], results, "lead", cancel=ev, ledger=lead_ledger)
    lead.start()
    _wait_until(lambda: sent, "the leader's request to go out")
    first = _caller(["x", "y"], results, "one", cancel=ev, ledger=one)
    second = _caller(["z"], results, "two", cancel=ev, ledger=two)
    first.start()
    second.start()
    _wait_until(lambda: len(providers._COALESCE_QUEUE) >= 2,
                "two followers to queue")
    held.set()
    for t in (lead, first, second):
        t.join(30)

    assert sorted(map(sorted, sent)) == [["lead"], ["x", "y", "z"]]
    assert not any(r.fallback for r in results.values())
    assert [e["texts"] for e in lead_ledger] == [1]
    assert [e["texts"] for e in one] == [2] and [e["texts"] for e in two] == [1]
    # The shares add up to the one round trip the provider billed.
    assert one[0]["in"] + two[0]["in"] == 30


def test_runs_queue_apart_and_each_request_carries_its_own_run(monkeypatch):
    """Two runs' callers queued behind a third are served by TWO requests,
    each registered under its own run's cancel event."""
    held = threading.Event()
    seen_events = []
    sent = _fake_request(monkeypatch, hold=held)
    real = providers._embed_request

    def tagging(texts):
        seen_events.append(providers.cancel_event.get())
        return real(texts)

    monkeypatch.setattr(providers, "_embed_request", tagging)
    ev_l, ev_a, ev_b = threading.Event(), threading.Event(), threading.Event()
    results = {}
    lead = _caller(["lead"], results, "lead", cancel=ev_l)
    lead.start()
    _wait_until(lambda: sent, "the leader's request to go out")
    a = _caller(["a"], results, "a", cancel=ev_a)
    b = _caller(["b"], results, "b", cancel=ev_b)
    a.start()
    b.start()
    _wait_until(lambda: len(providers._COALESCE_QUEUE) >= 2, "two runs to queue")
    held.set()
    for t in (lead, a, b):
        t.join(30)
    assert sorted(map(sorted, sent)) == [["a"], ["b"], ["lead"]]
    assert seen_events[0] is ev_l
    assert set(map(id, seen_events[1:])) == {id(ev_a), id(ev_b)}


def test_an_aborted_leader_goes_home_without_serving_other_runs(monkeypatch):
    """The aborted turn's thread is not held for another run's round trip:
    its own answer is in hand, so the next caller in line leads instead."""
    first_held, second_held = threading.Event(), threading.Event()
    sent = []

    def request(texts):
        sent.append(list(texts))
        (first_held if len(sent) == 1 else second_held).wait(30)
        providers._check_cancel()
        return providers.EmbeddingBatch(
            vectors=[np.ones(4, dtype=np.float32) for _ in texts],
            model_key="fake:1:m", dimensions=4, fallback=False)

    monkeypatch.setattr(providers, "_embed_request", request)
    monkeypatch.setattr(providers.time, "sleep", lambda _s: None)
    ev_a, ev_b = threading.Event(), threading.Event()
    results = {}
    a = _caller(["chat A's memory"], results, "a", cancel=ev_a)
    a.start()
    _wait_until(lambda: sent, "chat A's request to go out")
    b = _caller(["chat B's memory"], results, "b", cancel=ev_b)
    b.start()
    _wait_until(lambda: len(providers._COALESCE_QUEUE) >= 1, "chat B to queue")
    ev_a.set()
    first_held.set()
    a.join(10)
    assert not a.is_alive(), "the aborted leader is waiting on chat B's request"
    assert results["a"].fallback
    _wait_until(lambda: len(sent) == 2, "chat B to lead its own request")
    second_held.set()
    b.join(30)
    assert not results["b"].fallback
    assert not providers._COALESCE_INFLIGHT and not providers._COALESCE_QUEUE
