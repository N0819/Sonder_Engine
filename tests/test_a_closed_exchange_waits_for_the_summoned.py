"""A speaker closing their own exchange does not close anyone else's.

The interaction loop's early exits end the BEAT, and two of them already defer
to the reactors the beat summoned and has not yet called
(`_defer_to_unrun_reactor`). The third -- every speaker so far closing their
exchange -- did not. Measured on the playerless Aldermill round 9
(2026-09-23): two lives in one frame, both listed as reactors, and on 4 of 8
joint beats the first called closed his own exchange and the beat ended with
the second never asked.
"""

from __future__ import annotations

import agents.loops as loops
# The module, not its names: a Test* class imported here is collected twice.
from tests import test_interaction_first_wave as wave

CLOSED = {"expects_response": False, "conversation_complete_for_me": True}


def _closing_step(monkeypatch, calls):
    def step(ctx, cid, nonce):
        calls.append(cid)
        return {"cid": cid, "sequence": [{"type": "speech", "line": f"{cid} speaks"}],
                "interaction": dict(CLOSED)}
    monkeypatch.setattr(loops, "character_step", step)


def test_a_listed_reactor_is_still_asked(monkeypatch):
    calls = []
    wave._install(monkeypatch, calls, wave=1)
    _closing_step(monkeypatch, calls)
    out = loops.interaction_loop(wave._Ctx(reactors=[41, 35], addressed=[41]), nonce=0)
    assert calls == [41, 35]
    assert out["stop_reason"] == "speaker completed exchange"


def test_nobody_the_beat_did_not_summon_is_drawn_in(monkeypatch):
    calls = []
    wave._install(monkeypatch, calls, wave=1)
    _closing_step(monkeypatch, calls)
    ctx = wave._Ctx(reactors=[41], addressed=[41], cast=[41, 35])
    out = loops.interaction_loop(ctx, nonce=0)
    assert calls == [41]
    assert out["stop_reason"] == "speaker completed exchange"


def test_a_question_to_the_player_is_still_why_the_beat_ended(monkeypatch):
    """The first speaker asks the player and closes; the second is drained in
    and closes too. The beat ended waiting on the player, and says so."""
    calls = []
    wave._install(monkeypatch, calls, wave=1, asks_player={41})
    _closing_step(monkeypatch, calls)
    out = loops.interaction_loop(wave._Ctx(reactors=[41, 35], addressed=[41]), nonce=0)
    assert calls == [41, 35]
    assert out["stop_reason"] == "awaiting player response"
