"""A cache write rides beside the call that asks for it -- only where the host asks.

Measured 2026-10-10 on the encoder's drafts (google/gemini-3.8-flash through
OpenRouter, chat 166 beats 24 and 26, on a copy of the play database): a
draft carrying the breakpoint began answering 4.56 s after its request
(4.32-4.77, n=4) against 2.11 s unmarked (1.91-2.49, n=4) -- the write, on
the beat's critical path twice a beat. The repairs that continue the draft
read what it wrote either way. With the write beside it the draft began in
1.80 s (1.48-2.87, n=10, beats 21-24 and 26).

It is a trade, and the host's. Writing inside, the draft is billed the
write's price for its prompt ($0.1167/M); beside it, the draft pays the full
input price ($0.75/M) and a short write pays the write's: about $0.026 more a
draft at Brackwater's median 35k-token draft, about $0.05 a beat, for about
2.45 s of each draft's first token. So BY DEFAULT the call writes its own
prefix, as it always did, and a host who wants the seconds turns writing
beside on for a provider (`prompt_cache_write_beside`, the box beside the
provider's cache box). Then the first call on a prefix goes plain and the
breakpoint's request goes beside it on a thread of its own, cut to
`CACHE_WRITE_BESIDE_TOKENS`; every later call on the prefix -- the repairs, a
re-ask of the draft -- goes marked and reads it once the write has landed,
and plain until then. What the model is sent is the same either way: the
marker is transport.

The guards in this file -- the default, routes that were not measured or
take no breakpoint, the deny list, a call that asks for no breakpoint --
pin behaviour the engine had before writing beside existed, and pass on it:
the fixture patches the new names with `raising=False` for that reason.
"""

from __future__ import annotations

import json
import threading
import time

import pytest

from llm import providers

GEMINI = "google/gemini-3.8-flash"
OPENROUTER = {"id": 3, "name": "openrouter", "kind": "openrouter",
              "base_url": "http://openrouter.invalid/api/v1", "api_key": "k"}
NANOGPT = {"id": 1, "name": "nanogpt", "kind": "nanogpt",
           "base_url": "http://nanogpt.invalid/api/v1", "api_key": "k"}
CLAUDE = "anthropic/claude-sonnet-4"
CUE = [{"role": "user", "content": "Encode the beat in the message above."}]
#: The engine's own seam, taken before any fixture replaces it.
_REAL_RUN_BESIDE = getattr(providers, "_run_beside", None)


def _is_marked(message):
    content = message["content"]
    return (isinstance(content, list) and len(content) == 1
            and content[0].get("cache_control") == {"type": "ephemeral"})


class _Stream:
    status_code = 200
    text = ""

    def __init__(self):
        self._lines = [("data: " + json.dumps(chunk)).encode("utf-8") for chunk in (
            {"model": GEMINI, "choices": [{"delta": {"content": "{}"}}]},
            {"model": GEMINI, "choices": [{"delta": {}, "finish_reason": "stop"}],
             "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
        )] + [b"data: [DONE]"]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def iter_lines(self):
        return iter(self._lines)

    def close(self):
        pass


#: What the write beside reports when it wrote the prefix (probed 2026-10-10).
WROTE = {"prompt_tokens": 14931, "completion_tokens": 12,
         "prompt_tokens_details": {"cached_tokens": 14926, "cache_write_tokens": 14926}}
#: ...and when it came back having written nothing (chat 166 beat 23's
#: interpret, replayed 2026-10-10: 16,143 tokens billed at the full price).
WROTE_NOTHING = {"prompt_tokens": 16143, "completion_tokens": 12,
                 "prompt_tokens_details": {"cached_tokens": 0}}


class _Answer:
    """A plain (unstreamed) answer: what the write beside gets back."""

    def __init__(self, status, usage=None):
        self.status_code = status
        self.text = "" if status < 400 else '{"error": {"message": "no"}}'
        self._usage = usage

    def json(self):
        return {"model": GEMINI, "choices": [{"finish_reason": "length"}],
                "usage": self._usage or {}}


class _Wire:
    def __init__(self, write_status=200, write_usage=None):
        self.streamed, self.written = [], []
        self.write_status = write_status
        self.write_usage = write_usage or WROTE

    def post(self, url, **kw):
        body = json.loads(json.dumps(kw.get("json")))
        if body.get("stream"):
            self.streamed.append(body)
            return _Stream()
        self.written.append(body)
        return _Answer(self.write_status, usage=self.write_usage)


@pytest.fixture
def wire(temp_db, monkeypatch):
    def route(prov=OPENROUTER, model=GEMINI, write_status=200, write_usage=None,
              beside="openrouter"):
        w = _Wire(write_status, write_usage)
        monkeypatch.setattr(providers, "resolve_role_candidates",
                            lambda role: [(prov, model, {})])
        monkeypatch.setattr(providers, "_session", lambda: w)
        # In line, so the test reads what the write sent the moment the call
        # returns; the engine runs it on a thread of its own, which
        # `test_the_write_runs_on_a_thread_of_its_own` pins with the real seam.
        # `raising=False`: the guards run on code older than these names.
        monkeypatch.setattr(providers, "_run_beside", lambda fn: fn(), raising=False)
        monkeypatch.setattr(providers, "_PREFIX_WRITTEN", {}, raising=False)
        monkeypatch.setattr(providers, "_BESIDE_REFUSED", set(), raising=False)
        if beside:
            temp_db.set_setting("prompt_cache_write_beside", beside)
        return w
    return route


def _ask(user='{"prose": "x"}', history=CUE):
    providers.chat_complete("encoder", "SHEET", user, json_mode=False,
                            history=history, cache_user=True)


# ---- the default: the call writes its own prefix, as it always did ----------

def test_by_default_the_call_writes_its_own_cache_as_before(wire):
    """REGRESSION GUARD. No host setting: the breakpoint rides on the call
    itself, every time, and nothing is sent beside it -- the draft billed the
    write's price for its prompt and 2.45 s later to start."""
    w = wire(beside=None)
    _ask()
    _ask(history=CUE + [{"role": "assistant", "content": "{}"},
                        {"role": "user", "content": "REPAIR TURN"}])
    assert w.written == []
    assert all(_is_marked(body["messages"][1]) for body in w.streamed)
    assert len(w.streamed) == 2


# ---- where the host asks: the write rides beside the call -------------------

def test_where_the_host_asks_the_first_call_goes_plain_and_its_write_goes_beside_it(wire):
    w = wire()
    _ask()
    assert len(w.streamed) == 1 and len(w.written) == 1
    call, write = w.streamed[0], w.written[0]
    # The call itself carries no marker: nothing waits on a write.
    assert call["messages"][1] == {"role": "user", "content": '{"prose": "x"}'}
    assert "cache_control" not in json.dumps(call)
    # The write is the same request with its user message the breakpoint and
    # the cue after it (Gemini through OpenRouter writes nothing for a
    # breakpoint on the last message), cut short and sent whole, not streamed.
    assert _is_marked(write["messages"][1])
    assert write["messages"][1]["content"][0]["text"] == '{"prose": "x"}'
    assert write["messages"][0] == call["messages"][0]
    assert write["messages"][2:] == CUE == call["messages"][2:]
    assert write["max_tokens"] == providers.CACHE_WRITE_BESIDE_TOKENS
    assert "stream" not in write and "response_format" not in write


def test_the_host_names_a_provider_by_name_or_by_kind(temp_db):
    """The provider-level answer the settings box shows, from the request
    path's own predicate: offered only where it was measured, off until named,
    and off while caching itself is off for the provider."""
    named = dict(OPENROUTER, name="or-play")
    assert providers.cache_write_beside_offered_for(named)
    assert not providers.cache_write_beside_offered_for(NANOGPT)
    assert not providers.cache_write_beside_enabled_for(named)
    temp_db.set_setting("prompt_cache_write_beside", "or-play")
    assert providers.cache_write_beside_enabled_for(named)
    assert not providers.cache_write_beside_enabled_for(dict(OPENROUTER, name="or-other"))
    temp_db.set_setting("prompt_cache_write_beside", "openrouter")
    assert providers.cache_write_beside_enabled_for(dict(OPENROUTER, name="or-other"))
    temp_db.set_setting("prompt_cache_write_beside", "nanogpt")
    assert not providers.cache_write_beside_enabled_for(NANOGPT), "not offered there"
    temp_db.set_setting("prompt_cache_write_beside", "openrouter")
    temp_db.set_setting("prompt_cache_deny", "openrouter")
    assert not providers.cache_write_beside_enabled_for(named)


def test_a_later_call_on_the_written_prefix_goes_marked_and_reads_it(wire):
    """The repair continues the draft: same system, same user message, then
    the draft as the answer it was and the repair's turn."""
    w = wire()
    _ask()
    _ask(history=CUE + [{"role": "assistant", "content": "{}"},
                        {"role": "user", "content": "REPAIR TURN"}])
    assert len(w.written) == 1, "the prefix was written once"
    assert _is_marked(w.streamed[1]["messages"][1])
    # ...and a different prefix is a first call of its own.
    _ask(user='{"prose": "another beat"}')
    assert len(w.written) == 2 and not _is_marked(w.streamed[2]["messages"][1])


def test_a_written_prefix_lapses_with_the_storage_it_was_billed_for(wire, monkeypatch):
    monkeypatch.setattr(providers, "_PREFIX_WRITTEN", {}, raising=False)
    ttl = providers.CACHE_WRITE_TTL_SECONDS
    assert providers._claim_prefix_write("p", now=0.0) == "write"
    assert providers._claim_prefix_write("p", now=5.0) == "wait"
    providers._prefix_write_landed("p", now=10.0)
    assert providers._claim_prefix_write("p", now=10.0 + ttl - 1) == "read"
    assert providers._claim_prefix_write("p", now=10.0 + ttl + 1) == "write"
    # On the wire: once its storage is over, the next call writes it again,
    # beside itself.
    w = wire()
    _ask()
    for key in list(providers._PREFIX_WRITTEN):
        providers._PREFIX_WRITTEN[key] = [True, 0.0]   # landed, storage over
    _ask()
    assert len(w.written) == 2 and not _is_marked(w.streamed[1]["messages"][1])


def test_a_call_while_the_write_is_in_flight_goes_plain(wire, monkeypatch):
    """The repair can start before the write beside its draft has landed; a
    marker then would make the repair write the prefix itself, the 2.5 s this
    exists to keep off the beat. It goes plain; once the write lands, the next
    call reads it."""
    w = wire()
    held = []
    monkeypatch.setattr(providers, "_run_beside", held.append, raising=False)
    _ask()
    _ask()
    assert len(held) == 1, "one write for the prefix, still in flight"
    assert not _is_marked(w.streamed[1]["messages"][1])
    held[0]()
    _ask()
    assert _is_marked(w.streamed[2]["messages"][1])


def test_a_write_that_wrote_nothing_is_made_again_beside_the_next_call(wire):
    """Measured: three writes beside of eleven came back billed in full and
    having written nothing; when the first came back, the two repairs it was
    meant for went marked and wrote the prefix themselves (first tokens 3.1 s
    and 3.8 s against about 2 s for a read). A write is taken to stand only
    when its own count says it does."""
    w = wire(write_usage=WROTE_NOTHING)
    _ask()
    _ask()
    assert len(w.written) == 2, "the second call wrote it beside itself again"
    assert not any(_is_marked(body["messages"][1]) for body in w.streamed)


def test_a_refused_write_leaves_the_route_writing_inside(wire):
    """Fail open: a write beside that did not land leaves the prefix unwritten,
    and a host that refuses the short request has its breakpoints written
    inside the call -- as before -- for the rest of the process."""
    w = wire(write_status=422)
    _ask()
    assert len(w.written) == 1
    _ask()
    assert len(w.written) == 1, "a refused route is not asked again"
    assert _is_marked(w.streamed[1]["messages"][1])


def test_a_write_that_cannot_be_started_leaves_the_call_writing_inside(wire, monkeypatch):
    """No thread to be had ("can't start new thread"): the call does not fail
    and does not go plain on a write nobody is making. It carries its own
    breakpoint, as before, and no claim of the prefix is left standing, so
    the next call is free to write it beside itself."""
    w = wire()

    def no_thread(fn):
        raise RuntimeError("can't start new thread")

    monkeypatch.setattr(providers, "_run_beside", no_thread)
    _ask()
    assert w.written == [] and _is_marked(w.streamed[0]["messages"][1])
    assert providers._PREFIX_WRITTEN == {}
    monkeypatch.setattr(providers, "_run_beside", lambda fn: fn())
    _ask()
    assert len(w.written) == 1 and not _is_marked(w.streamed[1]["messages"][1])


def test_the_write_runs_on_a_thread_of_its_own(wire, monkeypatch):
    """The rule this exists for, on the engine's own seam (`_run_beside` is
    NOT replaced): the call is answered while the write beside it is still
    blocked on the wire, and the write's price reaches the step's ledger once
    it lands. Run in line instead, the write would finish before the call was
    even sent -- slower than the marker it replaced."""
    from llm.providers import call_ledger_sink

    w = wire()
    monkeypatch.setattr(providers, "_run_beside", _REAL_RUN_BESIDE)
    entered, release = threading.Event(), threading.Event()
    order = []
    plain_post = w.post

    def post(url, **kw):
        if not (kw.get("json") or {}).get("stream"):
            entered.set()
            order.append("write sent")
            release.wait(timeout=5)
            order.append("write answered")
        return plain_post(url, **kw)

    w.post = post
    landed = threading.Event()
    seen = []

    def sink(entry):
        seen.append(entry)
        if entry.get("kind") == "cache_write":
            landed.set()

    token = call_ledger_sink.set(sink)
    try:
        _ask()
        answered_while_blocked = not release.is_set() and "write answered" not in order
        assert entered.wait(timeout=5), "the write was sent"
    finally:
        call_ledger_sink.reset(token)
        release.set()
    assert answered_while_blocked, order
    assert landed.wait(timeout=5), "the write's price reached the ledger"
    deadline = time.time() + 5
    while time.time() < deadline and not any(entry[0] for entry in providers._PREFIX_WRITTEN.values()):
        time.sleep(0.01)
    assert [e["kind"] for e in seen if e.get("kind") == "cache_write"] == ["cache_write"]
    _ask()
    assert _is_marked(w.streamed[-1]["messages"][1]), "the landed write is read"



def test_the_writes_price_reaches_the_steps_ledger(wire):
    from llm.providers import call_ledger_sink
    seen = []
    token = call_ledger_sink.set(seen.append)
    try:
        wire()
        _ask()
    finally:
        call_ledger_sink.reset(token)
    write = [e for e in seen if e["kind"] == "cache_write"]
    assert len(write) == 1 and write[0]["role"] == "encoder"
    assert write[0]["in"] == 14931 and write[0]["out"] == 12


# ---- regression guards: what writing beside never touches -------------------

@pytest.mark.parametrize("prov, model", [
    # Claude through an aggregator was not measured: it writes inside, as
    # before, even where the host names the provider.
    (OPENROUTER, CLAUDE), (NANOGPT, CLAUDE),
])
def test_a_route_not_measured_writes_inside_the_call_as_before(wire, prov, model):
    """REGRESSION GUARD."""
    w = wire(prov, model, beside="openrouter,nanogpt")
    _ask()
    assert w.written == [] and _is_marked(w.streamed[0]["messages"][1])


@pytest.mark.parametrize("prov, model", [
    (OPENROUTER, "z-ai/glm-5.2"), (NANOGPT, GEMINI)])
def test_a_route_that_takes_no_breakpoint_is_sent_nothing_beside(wire, prov, model):
    """REGRESSION GUARD."""
    w = wire(prov, model, beside="openrouter,nanogpt")
    _ask()
    assert w.written == [] and "cache_control" not in json.dumps(w.streamed[0])


def test_the_hosts_deny_list_still_ends_it(wire, temp_db):
    """REGRESSION GUARD."""
    temp_db.set_setting("prompt_cache_deny", "openrouter")
    w = wire()
    _ask()
    assert w.written == [] and "cache_control" not in json.dumps(w.streamed[0])


def test_a_call_that_asks_for_no_breakpoint_writes_nothing(wire):
    """REGRESSION GUARD."""
    w = wire()
    providers.chat_complete("encoder", "SHEET", '{"prose": "x"}', json_mode=False,
                            history=CUE)
    assert w.written == [] and "cache_control" not in json.dumps(w.streamed[0])
