"""A transient provider failure must not strand a memory forever.

`embed_texts_meta` degrades to a 256-wide crc32 hash on ANY error and the
writers store that hash under its own `cheap:crc32:256` stamp. For a QUERY
that is a bad ranking for one beat; for a WRITE it is permanent, because
nothing re-embeds a row until somebody accepts a paid rebuild. Reported live
on 2026-08-11: a story created from a greeting offered to rebuild memories it
had written seconds earlier, and a turn two beats later stranded four more --
with a correctly configured provider that embedded the very same documents on
demand a minute afterwards. The failure was transient; the damage was not,
because the one call was never retried and never mentioned.

No network: `_session` is faked, so these are fast-tier tests.
"""

from __future__ import annotations

import pytest

from llm import providers

PROV = {"id": 3, "kind": "openrouter", "name": "openrouter", "api_key": "k",
        "base_url": "https://openrouter.ai/api/v1"}


class _Resp:
    def __init__(self, status, payload=None, text=""):
        self.status_code = status
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise AssertionError("raise_for_status reached with %s"
                                 % self.status_code)


def _vectors(n, dim=4):
    return {"data": [{"index": i, "embedding": [0.0] * (dim - 1) + [1.0]}
                     for i in range(n)]}


class _Session:
    """Answers each POST from a scripted list of responses."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def post(self, url, **kw):
        self.calls += 1
        item = self.script.pop(0) if self.script else self.script_default()
        if isinstance(item, Exception):
            raise item
        return item

    def script_default(self):
        return _Resp(200, _vectors(1))


def _wire(monkeypatch, script, *, no_sleep=True):
    session = _Session(script)
    monkeypatch.setattr(providers, "_session", lambda: session)
    monkeypatch.setattr(providers, "resolve_role",
                        lambda role: (PROV, "perplexity/pplx-embed-v1-4b", {}))
    monkeypatch.setattr(providers, "_headers", lambda prov: {})
    if no_sleep:
        monkeypatch.setattr(providers.time, "sleep", lambda _s: None)
    providers._EMBED_FALLBACK_SAID.clear()
    providers._embed_dead_forget()
    return session


# ---- Retrying ----

def test_a_rate_limit_is_retried_not_stranded(monkeypatch):
    """429 then 200: the vectors are the provider's, not the hash."""
    session = _wire(monkeypatch, [_Resp(429, text="rate limited"),
                                  _Resp(200, _vectors(2))])
    got = providers.embed_texts_meta(["a", "b"])
    assert session.calls == 2
    assert not got.fallback
    assert got.model_key == "openrouter:3:perplexity/pplx-embed-v1-4b"
    assert got.dimensions == 4


def test_a_dropped_connection_is_retried(monkeypatch):
    """The network exceptions the chat path already treats as transient."""
    import requests.exceptions as req_exc
    session = _wire(monkeypatch, [req_exc.ConnectionError("reset"),
                                  _Resp(200, _vectors(1))])
    got = providers.embed_texts_meta(["a"])
    assert session.calls == 2
    assert not got.fallback


def test_a_wrong_model_is_not_retried(monkeypatch):
    """A 400 is an answer, not a hiccup.

    Retrying "that model does not exist" spends the whole retry budget on
    every single write for as long as the role is misconfigured, and still
    falls back. The host is told instead: the body reaches the settings panel
    verbatim as `fallback_reason`.
    """
    session = _wire(monkeypatch, [_Resp(400, text="Model x does not exist")])
    got = providers.embed_texts_meta(["a"])
    assert session.calls == 1
    assert got.fallback
    assert "does not exist" in got.error


def test_retries_are_bounded_and_then_it_degrades(monkeypatch):
    """Four attempts, then the hash -- a memory is worth more than its vector."""
    session = _wire(monkeypatch, [_Resp(503, text="upstream down")] * 8)
    got = providers.embed_texts_meta(["a"])
    assert session.calls == 1 + providers.DEFAULT_RETRY.max_retries
    assert got.fallback
    assert got.model_key == "cheap:crc32:256"
    assert got.dimensions == 256


def test_a_measurement_can_decline_to_retry(monkeypatch):
    """`retry=None` for the bank probe: it runs while a chat is opening.

    A degraded provider is what that caller is asking ABOUT, so spending
    seconds proving it would only make a chat slow to open during an outage.
    """
    session = _wire(monkeypatch, [_Resp(503, text="down")] * 8)
    got = providers.embed_texts_meta(["status"], retry=None)
    assert session.calls == 1
    assert got.fallback


# ---- Saying so ----

def test_a_degraded_write_is_logged_with_the_reason(monkeypatch, caplog):
    """The incident left NO trace anywhere. That was half the defect."""
    _wire(monkeypatch, [_Resp(503, text="no instances available")] * 8)
    with caplog.at_level("WARNING", logger="fiction_engine"):
        providers.embed_texts_meta(["a memory"])
    said = "\n".join(r.getMessage() for r in caplog.records)
    assert "crc32" in said
    assert "no instances available" in said


def test_the_same_failure_does_not_flood_the_log(monkeypatch, caplog):
    """An outage says so once a minute, not once a row."""
    _wire(monkeypatch, [_Resp(503, text="down")] * 40)
    with caplog.at_level("WARNING", logger="fiction_engine"):
        for _ in range(5):
            providers.embed_texts_meta(["a memory"])
    assert sum("crc32" in r.getMessage() for r in caplog.records) == 1


def test_no_provider_configured_is_not_a_failure(monkeypatch, caplog):
    """With no embeddings role the hash IS the engine's embedding.

    Nothing is stranded and nothing was lost, so there is nothing to warn
    about -- and warning anyway would make the ordinary unconfigured setup
    look broken.
    """
    session = _wire(monkeypatch, [_Resp(503, text="down")] * 8)
    monkeypatch.setattr(providers, "embedding_model_key",
                        lambda: "cheap:crc32:256")
    with caplog.at_level("WARNING", logger="fiction_engine"):
        got = providers.embed_texts_meta(["a memory"])
    assert got.fallback and session.calls >= 1
    assert not any("crc32" in r.getMessage() for r in caplog.records)


# ---- Pacing ----
#
# The 2026-08-11 measurement that motivated this: against the configured
# OpenRouter/Perplexity embeddings route, a burst of 12 took 4 rate limits and
# 8 SEQUENTIAL requests at ~2.5/s took 3. So the ceiling is a request RATE,
# not merely a concurrency cap, and the engine's own fan-out reaches it.

def _pace_reset():
    providers._EMBED_PACE.update({"interval": 0.0, "next_at": 0.0})


def test_the_engine_starts_unpaced(monkeypatch):
    """A provider that never refuses must never be slowed.

    The ceiling belongs to the model, not to the engine: a local embedder
    does tens per second and a number chosen for somebody else's provider
    would be a permanent tax on it.
    """
    _pace_reset()
    slept = []
    session = _wire(monkeypatch, [_Resp(200, _vectors(1))] * 4, no_sleep=False)
    monkeypatch.setattr(providers.time, "sleep", lambda s: slept.append(s))
    for _ in range(4):
        providers.embed_texts_meta(["a"])
    assert session.calls == 4
    assert slept == []
    assert providers._EMBED_PACE["interval"] == 0.0


def test_a_rate_limit_teaches_the_pace(monkeypatch):
    """429 once, and subsequent calls space themselves out.

    The retry that succeeds immediately afterwards eases the pace by one
    decay step — the two happen inside the same call, and that ordering is
    deliberate: the refusal is evidence about the ceiling and the success is
    evidence the new pace clears it.
    """
    _pace_reset()
    _wire(monkeypatch, [_Resp(429, text="rate limited"),
                        _Resp(200, _vectors(1))])
    providers.embed_texts_meta(["a"])
    assert providers._EMBED_PACE["interval"] == pytest.approx(
        providers._EMBED_PACE_FIRST * providers._EMBED_PACE_DECAY)


def test_repeated_refusals_back_off_but_stay_bounded(monkeypatch):
    """Past the ceiling the provider is broken, not busy."""
    _pace_reset()
    _wire(monkeypatch, [_Resp(429, text="rate limited")] * 40)
    for _ in range(6):
        providers.embed_texts_meta(["a"])
    assert providers._EMBED_PACE["interval"] == providers._EMBED_PACE_MAX


def test_concurrent_callers_get_separate_slots(monkeypatch):
    """N waiters must get N spaced departures, and wait in PARALLEL.

    The slot is taken under the lock and slept outside it. Holding the lock
    across the sleep would serialize the waits into each other and make the
    queue quadratic in the fan-out — which is precisely the wave this exists
    to smooth.
    """
    _pace_reset()
    providers._EMBED_PACE["interval"] = 0.5
    monkeypatch.setattr(providers.time, "monotonic", lambda: 100.0)
    slots = []
    monkeypatch.setattr(providers.time, "sleep", lambda s: slots.append(round(s, 3)))
    for _ in range(4):
        providers._embed_pace_wait()
    assert slots == [0.5, 1.0, 1.5]  # the first departs immediately
    assert providers._EMBED_PACE["next_at"] == pytest.approx(102.0)


def test_a_clean_run_eases_the_pace_back_off(monkeypatch):
    """A provider that had one bad minute must not pay for it all session."""
    _pace_reset()
    providers._EMBED_PACE["interval"] = providers._EMBED_PACE_FLOOR * 1.01
    _wire(monkeypatch, [_Resp(200, _vectors(1))] * 4)
    providers.embed_texts_meta(["a"])
    assert providers._EMBED_PACE["interval"] == 0.0


def test_pacing_is_announced_once(monkeypatch, caplog):
    """Silence is what made the original incident invisible."""
    _pace_reset()
    _wire(monkeypatch, [_Resp(429, text="rate limited")] * 40)
    with caplog.at_level("WARNING", logger="fiction_engine"):
        for _ in range(4):
            providers.embed_texts_meta(["a"])
    assert sum("pacing requests" in r.getMessage() for r in caplog.records) == 1


# ---- Jitter ----

def test_backoff_is_jittered_so_a_wave_does_not_recollide():
    """A fan-out that all sleeps exactly 1s retries as the same wave."""
    config = providers.RetryConfig()
    draws = {config.delay_for(1) for _ in range(50)}
    assert len(draws) > 1, "unjittered backoff synchronizes the retry storm"


def test_jitter_is_equal_not_full():
    """Half fixed, half random: a full-jitter draw near zero against a rate
    ceiling is a retry that was never a backoff."""
    config = providers.RetryConfig()
    flat = min(config.base_delay * 2, config.max_delay)
    for _ in range(200):
        assert flat / 2 <= config.delay_for(1) <= flat


def test_jitter_still_respects_the_ceiling():
    config = providers.RetryConfig()
    for attempt in range(8):
        assert config.delay_for(attempt) <= config.max_delay


# ---- The whole point, end to end ----

def test_a_burst_beyond_the_ceiling_completes_instead_of_stranding(monkeypatch):
    """Eight concurrent writers against a provider that refuses any unpaced
    request: every one must come back with the provider's vectors, none with
    the hash. This is the incident replayed -- greeting seeds and a turn's
    fan-out firing together -- with the pacer and the jittered retry
    composing: the first refusals teach the interval, the retries land under
    it, and the fallback (which is permanent for a write) is never reached.
    """
    import threading as _threading

    providers._EMBED_PACE.update({"interval": 0.0, "next_at": 0.0})

    class _CeilingSession:
        """429s exactly while the engine is unpaced -- the measured provider
        shape reduced to its essence: requests above the ceiling fail, and
        the ceiling clears once departures are spaced.

        ANSWERS THE REQUEST IT WAS GIVEN, one vector per input. Eight
        concurrent callers is precisely the traffic the coalescer exists to
        merge, so some runs hand this one request carrying several texts --
        and a stub that always returned a single vector failed those runs
        with `unexpected vector count`, four retries, and the hash for the
        whole group. Read as an engine flake for a day (2026-08-18): it is
        timing-shaped, so it surfaced in the full suite and never once in
        four hundred standalone bursts.
        """

        def __init__(self):
            self._lock = _threading.Lock()
            self.calls = 0
            self.refusals = 0

        def post(self, url, **kw):
            asked = len((kw.get("json") or {}).get("input") or [])
            with self._lock:
                self.calls += 1
                if providers._EMBED_PACE["interval"] <= 0:
                    self.refusals += 1
                    return _Resp(429, text="request_rate_limit_exceeded")
            return _Resp(200, _vectors(asked))

    session = _CeilingSession()
    monkeypatch.setattr(providers, "_session", lambda: session)
    monkeypatch.setattr(providers, "resolve_role",
                        lambda role: (PROV, "perplexity/pplx-embed-v1-4b", {}))
    monkeypatch.setattr(providers, "_headers", lambda prov: {})
    monkeypatch.setattr(providers.time, "sleep", lambda _s: None)
    providers._EMBED_FALLBACK_SAID.clear()

    results = [None] * 8

    def work(i):
        results[i] = providers.embed_texts_meta([f"text {i}"])

    threads = [_threading.Thread(target=work, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(r is not None and not r.fallback for r in results), \
        "a queued call must cost a wait, never a stranded row"
    assert session.refusals >= 1, "the ceiling was never exercised"
    providers._EMBED_PACE.update({"interval": 0.0, "next_at": 0.0})


def test_the_queue_does_not_reach_past_the_horizon(monkeypatch):
    """A wide fan-out must not book itself minutes into the future.

    Each waiter takes the next free slot, so without a bound the horizon
    grows with the arrival rate and every waiter sits in `time.sleep` — a
    hung engine wearing a rate limiter's clothes. Past the horizon the
    arrival rate is simply above what the ceiling serves, and the
    429/retry/fallback ladder is the release valve.
    """
    _pace_reset()
    providers._EMBED_PACE["interval"] = 1.0
    monkeypatch.setattr(providers.time, "monotonic", lambda: 100.0)
    slept = []
    monkeypatch.setattr(providers.time, "sleep", lambda s: slept.append(s))
    for _ in range(20):
        providers._embed_pace_wait()
    assert max(slept) <= providers._EMBED_PACE_MAX_WAIT
    assert (providers._EMBED_PACE["next_at"] - 100.0
            <= providers._EMBED_PACE_MAX_WAIT + 1.0)


# ---- Coalescing ----
#
# The ceiling counts REQUESTS, not tokens, and the engine fans out. Verified
# live before building this (2026-08-11): the same document embedded alone and
# inside a batch of three came back BITWISE identical at both first and last
# position, so a text's vector does not depend on its companions and nothing
# here can move a ranking.

def _coalesce_reset():
    providers._COALESCE_QUEUE[:] = []
    providers._COALESCE_INFLIGHT = False
    providers._EMBED_STATS.update(
        {"callers": 0, "groups": 0, "texts_in": 0, "texts_sent": 0})


def _wait_until(predicate, what, timeout=20.0):
    """Block until a coalescing state is reached, or say what was waited for.

    These tests set up a race deliberately -- a leader in flight, followers
    queueing behind it -- and the setup used unbounded `while not cond:` spins.
    That is fine alone and flaky under a loaded full suite: if the followers
    are slow to enqueue, the leader's own barrier expires first, the grouping
    the test asserts never forms, and the failure reads as a coalescing defect
    rather than as scheduling.

    It is not a defect. A caller that arrives after the leader has gone simply
    forms its own group, which is correct behaviour and the whole point of the
    queue being time-ordered. So the fix belongs here: wait with a deadline
    generous enough that load cannot change the ANSWER, and fail with a
    sentence naming the state that never arrived.
    """
    import time as _time
    deadline = _time.monotonic() + timeout
    while not predicate():
        if _time.monotonic() > deadline:
            raise AssertionError(
                f"timed out after {timeout:g}s waiting for {what}; "
                f"queue={len(providers._COALESCE_QUEUE)} "
                f"inflight={providers._COALESCE_INFLIGHT}")
        _time.sleep(0.001)


def test_a_solo_caller_is_not_delayed_or_batched(monkeypatch):
    """Under no contention this must be the old behaviour exactly."""
    _pace_reset(); _coalesce_reset()
    session = _wire(monkeypatch, [_Resp(200, _vectors(2))])
    got = providers.embed_texts_meta(["a", "b"])
    assert session.calls == 1
    assert not got.fallback and len(got.vectors) == 2
    assert providers._EMBED_STATS["groups"] == 1


def test_callers_arriving_during_a_flight_share_the_next_request(monkeypatch):
    """Three concurrent retrievals cost ONE request, not three.

    Deterministic by construction: the leader is held inside its request
    while the others queue, so the group it takes on its next lap is exactly
    those three.
    """
    import threading
    _pace_reset(); _coalesce_reset()
    released = threading.Event()
    served = []

    def fake(texts, config):
        served.append(list(texts))
        if len(served) == 1:
            released.wait(30)
        import numpy as np
        return providers.EmbeddingBatch(
            vectors=[np.full(4, float(hash(t) % 97), dtype=np.float32) for t in texts],
            model_key="test:1:model", dimensions=4, fallback=False)

    monkeypatch.setattr(providers, "_embed_with_retry", fake)
    results = {}
    leader = threading.Thread(target=lambda: results.update(
        {"lead": providers.embed_texts_meta(["lead"])}))
    leader.start()
    _wait_until(lambda: providers._COALESCE_INFLIGHT, "the leader to go in flight")
    followers = []
    for name in ("b", "c", "d"):
        t = threading.Thread(target=lambda n=name: results.update(
            {n: providers.embed_texts_meta([n])}))
        t.start(); followers.append(t)
    _wait_until(lambda: len(providers._COALESCE_QUEUE) >= 3,
                "three followers to queue behind it")
    released.set()
    leader.join(30); [t.join(30) for t in followers]

    assert served == [["lead"], ["b", "c", "d"]], served
    assert providers._EMBED_STATS["groups"] == 2
    assert providers._EMBED_STATS["callers"] == 4
    # Every caller got ITS OWN vector, not a neighbour's.
    for name in ("lead", "b", "c", "d"):
        assert results[name].vectors[0][0] == float(hash(name) % 97)


def test_the_same_text_is_embedded_once_for_everyone(monkeypatch):
    """Two minds asking the same question cost one embedding, and get the
    same vector — which is what bitwise batch-invariance licenses."""
    _pace_reset(); _coalesce_reset()
    import numpy as np
    seen = []

    def fake(texts, config):
        seen.append(list(texts))
        return providers.EmbeddingBatch(
            vectors=[np.arange(4, dtype=np.float32) + i for i in range(len(texts))],
            model_key="test:1:model", dimensions=4, fallback=False)

    monkeypatch.setattr(providers, "_embed_with_retry", fake)
    group = [providers._EmbedWaiter(["same"]), providers._EmbedWaiter(["same"]),
             providers._EmbedWaiter(["other"])]
    providers._serve_embed_group(group, providers.DEFAULT_RETRY)
    assert seen == [["same", "other"]]
    assert group[0].result.vectors[0].tolist() == group[1].result.vectors[0].tolist()
    assert group[2].result.vectors[0].tolist() != group[0].result.vectors[0].tolist()


def test_a_group_splits_rather_than_sending_a_body_that_is_too_big(monkeypatch):
    _pace_reset(); _coalesce_reset()
    providers._COALESCE_QUEUE[:] = [
        providers._EmbedWaiter(["x" * 1000] * 40) for _ in range(3)]
    first = providers._take_embed_group_locked()
    assert len(first) == 1  # 40 texts already fills the 64-text cap
    assert len(providers._COALESCE_QUEUE) == 2


def test_a_degraded_batch_degrades_every_caller_the_same_way(monkeypatch):
    """One shared failure, and nobody silently keeps a real vector."""
    _pace_reset(); _coalesce_reset()
    _wire(monkeypatch, [_Resp(503, text="down")] * 40)
    group = [providers._EmbedWaiter(["a"]), providers._EmbedWaiter(["b", "c"])]
    providers._serve_embed_group(group, providers.RetryConfig(max_retries=0))
    assert all(w.result.fallback for w in group)
    assert [len(w.result.vectors) for w in group] == [1, 2]
    assert all(w.result.model_key == "cheap:crc32:256" for w in group)


def test_a_measurement_never_queues_behind_a_turn(monkeypatch):
    """`retry=None` bypasses coalescing: a chat is opening and waiting."""
    _pace_reset(); _coalesce_reset()
    _wire(monkeypatch, [_Resp(200, _vectors(1))])
    providers.embed_texts_meta(["status"], retry=None)
    assert providers._EMBED_STATS["callers"] == 0


# ---- Coalescing: woken is not the same as served ----
#
# Found 2026-08-18 as an intermittent failure of the burst test above: one of
# the eight callers came back holding `None` rather than a batch. The leader
# drops leadership the moment the queue first reads empty and only drains the
# queue afterwards, so a caller arriving between those two points elects
# itself leader and is then drained by the outgoing one -- woken, with no
# result, by a leader that never served it. Both callers then returned
# `waiter.result` on the strength of the event alone.
#
# Two changes came out of it. The floor below is the one with teeth and is
# tested here. The other -- the leader holding leadership until it has
# drained, rather than dropping it when the queue first reads empty -- closes
# the window that produced the empty wake in the first place, and is NOT
# covered by a test of its own: the window is one statement wide and any test
# that claimed to hit it would in fact pass against the old code too. With the
# floor in place its remaining cost is lost coalescing, not a lost row.

def test_a_woken_caller_with_no_result_serves_itself(monkeypatch):
    """The drain wakes a queued caller; it does not answer it.

    `embed_texts_meta` returns a batch or it degrades to the hash. It must
    never return `None` -- every writer above it stores `.vectors` and
    stamps `.model_key` without asking whether there was a batch at all.
    """
    _wire(monkeypatch, [_Resp(200, _vectors(1))] * 4)

    def _wake_without_serving(group, config):
        for waiter in group:
            waiter.done.set()

    monkeypatch.setattr(providers, "_serve_embed_group", _wake_without_serving)
    got = providers.embed_texts_meta(["a memory"])
    assert got is not None, "a caller may be woken empty, never answered empty"
    assert not got.fallback


def test_the_coalescing_arithmetic_reaches_somebody(monkeypatch, caplog):
    """`_EMBED_STATS` calls itself "visible arithmetic for did this help" and
    was visible to nothing: four counters incremented on every embedding call,
    with no reader anywhere outside a test. The question it answers -- did the
    queue, the leader election and the deadlock backstop buy anything -- is
    the argument for that machinery existing, and it could not be asked.

    Reported on the groups that actually merged callers; a group of one is the
    ordinary case and would be a log line per embedding.
    """
    import logging

    from llm import providers

    monkeypatch.setattr(
        providers, "_embed_with_retry",
        lambda order, config: providers.EmbeddingBatch(
            vectors=[[0.0] for _ in order], model_key="m", dimensions=1))

    waiters = [providers._EmbedWaiter(["one", "two"]),
               providers._EmbedWaiter(["two", "three"])]
    with caplog.at_level(logging.INFO, logger="fiction_engine"):
        providers._serve_embed_group(waiters, {})
    merged = [r for r in caplog.records if "embed_coalesced" in r.getMessage()]
    assert merged, [r.getMessage() for r in caplog.records]
    # Three distinct texts for four requested: the saving is the point.
    assert "texts_sent=3" in merged[0].getMessage()

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="fiction_engine"):
        providers._serve_embed_group([providers._EmbedWaiter(["solo"])], {})
    assert not [r for r in caplog.records
                if "embed_coalesced" in r.getMessage()]


# ---- Remembering an unreachable endpoint ----
#
# Measured live 2026-08-28 (chat 95, turn idx 905, wall 313.1s): against an
# endpoint that never completed a TCP connect, the retry ladder ran IN FULL
# twice in one turn -- 126.0s inside interaction_loop's memory-context build,
# 126.4s inside commit's prepare_memories_batch, four 30.1s connect timeouts
# plus jittered backoff each -- 252.4s, 81% of the turn, spent re-proving a
# fact the same process finished proving seventy seconds earlier. The memory
# these tests pin keeps the verdict; nothing about the verdict changes.


def _dead(monkeypatch, script):
    """Wire a session and hand back both it and a connect-level exception."""
    import requests.exceptions as req_exc
    return _wire(monkeypatch, script), req_exc


def test_an_unreachable_endpoint_is_proved_once_not_once_per_call(monkeypatch):
    """The 252.4s turn: two full ladders for one fact. Now one ladder.

    The second call must make ZERO requests and still return exactly the
    batch the exhausted ladder would have: the crc32 hash under its own
    stamp, with the remembered reason in `error`.
    """
    import requests.exceptions as req_exc
    session = _wire(monkeypatch,
                    [req_exc.ConnectionError("connect timed out")] * 8)
    first = providers.embed_texts_meta(["a memory"])
    assert session.calls == 1 + providers.DEFAULT_RETRY.max_retries
    assert first.fallback

    second = providers.embed_texts_meta(["a memory"])
    assert session.calls == 1 + providers.DEFAULT_RETRY.max_retries, \
        "the second call re-paid the ladder the first call already ran"
    assert second.fallback
    assert second.model_key == "cheap:crc32:256"
    assert "remembered unreachable" in (second.error or "")
    # Byte-for-byte the verdict the ladder produces: cheap_embed(text).
    import numpy as np
    assert np.array_equal(second.vectors[0],
                          providers.cheap_embed("a memory"))
    assert (second.dimensions, second.model_key) == (
        first.dimensions, first.model_key)


def test_a_status_from_a_live_server_is_never_remembered(monkeypatch):
    """A 503 is a server ANSWERING. Only a connect-level failure -- no server
    reached at all -- may be remembered, or one upstream bad minute would
    silence a healthy endpoint for the whole cooldown."""
    session = _wire(monkeypatch, [_Resp(503, text="upstream down")] * 16)
    providers.embed_texts_meta(["a"])
    providers.embed_texts_meta(["b"])
    assert session.calls == 2 * (1 + providers.DEFAULT_RETRY.max_retries)
    assert providers._EMBED_DEAD["key"] is None


def test_a_single_declined_attempt_proves_nothing(monkeypatch):
    """`retry=None` makes one attempt; one connect failure is a hiccup, not a
    verdict, and must not put the whole pipeline on the hash for 300s."""
    import requests.exceptions as req_exc
    _wire(monkeypatch, [req_exc.ConnectionError("blip")] * 2)
    got = providers.embed_texts_meta(["status"], retry=None)
    assert got.fallback
    assert providers._EMBED_DEAD["key"] is None


def test_the_measurement_caller_still_asks_the_wire(monkeypatch):
    """The bank probe exists to observe the endpoint as it is NOW. Answered
    from memory it could never report a recovery -- so it bypasses the
    memory, and its success clears it for everyone."""
    session = _wire(monkeypatch, [_Resp(200, _vectors(1))])
    providers._EMBED_DEAD.update(
        key="openrouter:3:perplexity/pplx-embed-v1-4b",
        reason="connect timed out", probe_at=float("inf"), probing=False)
    got = providers.embed_texts_meta(["status"], retry=None)
    assert session.calls == 1
    assert not got.fallback
    assert providers._EMBED_DEAD["key"] is None, \
        "a successful request must clear the remembered deadness"


def test_recovery_is_probed_off_everyones_wall_clock(monkeypatch):
    """When the memory comes due, the caller is still answered immediately
    and the re-check happens on a background thread -- the probe's connect
    timeout lands on nobody's turn. A probe that succeeds clears the memory;
    one that fails leaves it standing for the next window."""
    session = _wire(monkeypatch, [_Resp(200, _vectors(1))])
    key = "openrouter:3:perplexity/pplx-embed-v1-4b"
    providers._EMBED_DEAD.update(key=key, reason="connect timed out",
                                 probe_at=0.0, probing=False)

    started = []

    class _InlineThread:
        def __init__(self, target=None, args=(), **kw):
            started.append((target, args))

        def start(self):
            pass

    monkeypatch.setattr(providers.threading, "Thread", _InlineThread)
    got = providers.embed_texts_meta(["a memory"])
    assert got.fallback, "the caller waits for no probe"
    assert session.calls == 0
    assert len(started) == 1 and started[0][1] == (key,)
    assert providers._EMBED_DEAD["probing"] is True
    assert providers._EMBED_DEAD["probe_at"] > 0.0, \
        "the next window must be booked before the probe reports"

    # Run the probe the thread would have run: the 200 clears the memory.
    target, args = started[0]
    target(*args)
    assert session.calls == 1
    assert providers._EMBED_DEAD["key"] is None
    assert providers._EMBED_DEAD["probing"] is False


def test_a_failed_probe_keeps_the_memory_standing(monkeypatch):
    import requests.exceptions as req_exc
    session = _wire(monkeypatch, [req_exc.ConnectionError("still dead")] * 2)
    key = "openrouter:3:perplexity/pplx-embed-v1-4b"
    providers._EMBED_DEAD.update(key=key, reason="connect timed out",
                                 probe_at=float("inf"), probing=True)
    providers._embed_dead_probe(key)
    assert session.calls == 1
    assert providers._EMBED_DEAD["key"] == key
    assert providers._EMBED_DEAD["probing"] is False


def test_a_reconfigured_role_is_not_answered_from_the_old_keys_memory(
        monkeypatch):
    """Deadness is a fact about ONE (provider, model) key. The host who
    points the role at a new endpoint must reach it on the next call."""
    session = _wire(monkeypatch, [_Resp(200, _vectors(1))])
    providers._EMBED_DEAD.update(
        key="openrouter:9:some-old-endpoint", reason="connect timed out",
        probe_at=float("inf"), probing=False)
    got = providers.embed_texts_meta(["a memory"])
    assert session.calls == 1
    assert not got.fallback


# ---- The verdict must reach the TURN PATH, not just the providers layer ----
#
# The residual audit (finding 2, 2026-08-28) first attributed ~245s of a
# 313.1s turn to un-probed deterministic work in two windows --
# interaction_loop 13.9-151.2s and the commit stretch 180.3-313.1s. Both
# windows were the connect ladder above: 126.0s inside interaction_loop's
# memory-context build, 126.4s inside commit's prepare_memories_batch.
# Re-measured on the live 300-body market town with the memory in place
# (chat 95, turns idx 920-922): pre-fix 324.4s wall with interaction_loop at
# 141.5s and commit at 136.8s; fixed, the warm turn ran 66.7s with those
# windows at 10.4s and 9.1s -- model-call time plus single-digit
# deterministic seconds, no hidden deterministic residual.
#
# That collapse only holds while the turn-path callers ACCEPT the remembered
# verdict, which they do by calling `embed_texts_meta` with the default
# retry. The tests here pin the callers, not the memory itself: a turn-path
# call site that grows `retry=None` silently re-opens consult_memory=False
# (a caller's own RetryConfig does NOT -- only the None spelling routes to
# the measurement path) and puts the ladder back on the turn's wall clock,
# and every providers-layer test above stays green while it happens.


def test_the_commit_window_accepts_the_remembered_verdict(monkeypatch):
    """`prepare_memories_batch` -- the 126.4s of the commit stretch -- must
    make ZERO requests once the endpoint is remembered unreachable, and
    still hand back the batch commit expects: two fallback-stamped vectors
    per memory, refusable and rebuildable exactly like an outage write."""
    from mind.memory import prepare_memories_batch

    session = _wire(monkeypatch, [])
    providers._EMBED_DEAD.update(
        key=providers.embedding_model_key(), reason="connect timed out",
        probe_at=float("inf"), probing=False)
    try:
        got = prepare_memories_batch([
            dict(chat_id=1, char_id="c1", turn_id=7, turn_idx=5,
                 kind="episodic", provenance="witnessed", salience=0.6,
                 content="The stall keeper undercut the grain price."),
            dict(chat_id=1, char_id="c2", turn_id=7, turn_idx=5,
                 kind="episodic", provenance="witnessed", salience=0.4,
                 content="Rain drove the buyers under the awnings."),
        ])
    finally:
        providers._embed_dead_forget()
    assert session.calls == 0, \
        "the commit window paid the connect ladder the process already ran"
    embedded = got["embedded"]
    assert embedded.fallback
    assert embedded.model_key == "cheap:crc32:256"
    assert len(embedded.vectors) == 2 * len(got["prepared"])


def test_no_turn_path_caller_opts_out_of_the_dead_endpoint_memory():
    """`retry=None` means consult_memory=False: a single live observation of
    the endpoint, sanctioned for exactly two measurement probes (the bank
    status probe and the lore rebuild probe) because answering THEM from
    memory could never report a recovery. Any other `embed_texts_meta`
    caller in pipeline code that spells `retry=None` has quietly put the
    ~126s connect ladder back inside a turn; this scan is the tripwire."""
    import pathlib
    import re

    root = pathlib.Path(providers.__file__).resolve().parents[1]
    sanctioned = {"mind/memory_vectors.py", "mind/memory_lore_entries.py"}
    offenders = {}
    for pkg in ("mind", "agents", "persist", "world", "story", "core"):
        for path in sorted((root / pkg).glob("*.py")):
            text = path.read_text(encoding="utf-8")
            hits = re.findall(
                r"embed_texts_meta\([^)]*retry\s*=\s*None", text)
            if hits:
                offenders[f"{pkg}/{path.name}"] = len(hits)
    assert set(offenders) <= sanctioned, (
        "turn-path module(s) bypass the dead-endpoint memory with "
        "retry=None: %r -- each such call pays the full connect ladder on "
        "the caller's wall clock when the endpoint is down" % (offenders,))
