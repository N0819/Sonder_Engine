"""What a concurrent group of steps keeps, and what it hands back.

Properties the sequential path already has and the parallel copy did not.
"""

from __future__ import annotations

from agents.runtime import Bus, _stream_parallel


def test_each_worker_carries_its_own_reasoning_trace_out():
    from llm.providers import last_reasoning

    def job(text):
        def run():
            last_reasoning.set(text)
            return {"prose": text}
        return run

    bus = Bus()
    holders = {}
    jobs = [("narrator", job("thought about the narrator")),
            ("narrator_extra", job("thought about the co-player"))]
    list(_stream_parallel(bus, jobs, holders))

    # A ContextVar set inside a worker is invisible to the generator thread,
    # so `save_step`'s own fallback read cannot see it -- the value has to be
    # handed back through `holders`, exactly as the single-step path does.
    assert holders["narrator"]["reasoning"] == "thought about the narrator"
    assert holders["narrator_extra"]["reasoning"] == "thought about the co-player"
    assert last_reasoning.get() in (None, "")
