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

import providers

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
        the ceiling clears once departures are spaced."""

        def __init__(self):
            self._lock = _threading.Lock()
            self.calls = 0
            self.refusals = 0

        def post(self, url, **kw):
            with self._lock:
                self.calls += 1
                if providers._EMBED_PACE["interval"] <= 0:
                    self.refusals += 1
                    return _Resp(429, text="request_rate_limit_exceeded")
            return _Resp(200, _vectors(1))

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
            released.wait(5)
        import numpy as np
        return providers.EmbeddingBatch(
            vectors=[np.full(4, float(hash(t) % 97), dtype=np.float32) for t in texts],
            model_key="test:1:model", dimensions=4, fallback=False)

    monkeypatch.setattr(providers, "_embed_with_retry", fake)
    results = {}
    leader = threading.Thread(target=lambda: results.update(
        {"lead": providers.embed_texts_meta(["lead"])}))
    leader.start()
    while not providers._COALESCE_INFLIGHT:
        time.sleep(0.001)
    followers = []
    for name in ("b", "c", "d"):
        t = threading.Thread(target=lambda n=name: results.update(
            {n: providers.embed_texts_meta([n])}))
        t.start(); followers.append(t)
    while len(providers._COALESCE_QUEUE) < 3:
        time.sleep(0.001)
    released.set()
    leader.join(5); [t.join(5) for t in followers]

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
