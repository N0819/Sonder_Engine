"""Every thread's session reuses the same pooled connections.

`providers._session()` keeps one `requests.Session` per THREAD, because a
Session is not safe to share under concurrent use -- and the pipeline makes
a new thread per step and new pools per call (`director_prose`,
`director_repair`, `background`, `decisions`, `memory_links`), so most calls
paid a fresh TCP+TLS handshake: 0.295 s fresh against 0.248 s kept alive on
OpenRouter, ~0.05 s a request (`llm/decisions.py`, measured by the owner).
urllib3's connection pools ARE thread-safe, so each thread's session now
mounts ONE shared `HTTPAdapter` (review 2026-11-01, llm_providers_quality,
Efficiency 2): sessions stay per thread, connections do not.
"""
from __future__ import annotations

import threading

from llm import providers


def _adapter_on_a_new_thread(url):
    got = {}

    def run():
        session = providers._session()
        got["session"] = session
        got["adapter"] = session.get_adapter(url)

    t = threading.Thread(target=run)
    t.start()
    t.join(10)
    return got


def test_two_threads_have_two_sessions_and_one_pool():
    one = _adapter_on_a_new_thread("https://openrouter.ai/api/v1/chat/completions")
    two = _adapter_on_a_new_thread("https://openrouter.ai/api/v1/embeddings")
    assert one["session"] is not two["session"]
    assert one["adapter"] is two["adapter"]
    plain = _adapter_on_a_new_thread("http://127.0.0.1:8181/v1/embeddings")
    assert plain["adapter"] is one["adapter"]


def test_the_pool_keeps_as_many_connections_as_it_says():
    adapter = _adapter_on_a_new_thread("https://x.example/")["adapter"]
    assert adapter._pool_maxsize == providers.HTTP_POOL_MAXSIZE
