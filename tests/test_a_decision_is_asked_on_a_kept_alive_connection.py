"""A decision is asked on the calling thread's kept-alive connection.

Jev answers in about a third of a second, and a beat asks it 20-42 times,
almost all of them in a row on the critical path (chat 166 beats 24 and 26,
replayed 2026-10-10: 21 and 42 requests, about 0.3 s each). Every one went
out on a fresh connection -- `requests.post`, a new TCP and TLS handshake to
the same host each time -- where every other provider call in the engine
reuses its thread's session (`providers._session`). A probe the same day,
back to back on one thread against OpenRouter's decisions endpoint: a median
0.295 s a request fresh (n=12) against 0.248 s kept alive (n=6). The replayed
beats did not show it (a median 0.317 s a decision before, n=122, and 0.319 s
after, n=24), so this is a probe result, not a measured beat. What is asked,
and of whom, is unchanged; only the socket is kept.
"""

from __future__ import annotations

from types import SimpleNamespace

from llm import decisions, providers


class _Answer:
    status_code = 200
    text = ""

    def __init__(self, questions):
        self._questions = questions

    def json(self):
        return {"model": "jev-test", "usage": {"input_tokens": 9},
                "answers": {k: {"type": "noul", "noul": 0.9} for k in self._questions}}


def test_a_decision_goes_out_on_the_threads_own_session(temp_db, monkeypatch):
    used = []

    class _Session:
        def post(self, url, headers=None, json=None, timeout=None):
            used.append(self)
            return _Answer(json["questions"])

    session = _Session()
    monkeypatch.setattr(providers, "_session", lambda: session)
    monkeypatch.setattr(decisions, "_provider", lambda: {
        "api_key": "k", "kind": "openrouter", "base_url": "https://example.invalid/api/v1"})
    q = {"q": {"type": "noul", "instructions": "?"}}
    decisions.decide("state one", q)
    decisions.decide("state two", q)
    assert used == [session, session], "both decisions rode the thread's session"


def test_the_transport_seam_is_the_session(temp_db, monkeypatch):
    sent = []
    monkeypatch.setattr(decisions, "_http", lambda: SimpleNamespace(
        post=lambda url, headers=None, json=None, timeout=None:
            sent.append(url) or _Answer(json["questions"])))
    monkeypatch.setattr(decisions, "_provider", lambda: {
        "api_key": "k", "kind": "openrouter", "base_url": "https://example.invalid/api/v1"})
    got = decisions.decide("state", {"q": {"type": "noul", "instructions": "?"}})
    assert got["q"]["noul"] == 0.9
    assert sent == ["https://example.invalid" + decisions.DECISIONS_PATH]
