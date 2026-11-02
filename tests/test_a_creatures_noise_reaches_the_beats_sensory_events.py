"""A charter creature's declared act is heard at its own voice rung.

`background.declare_charter_figures` derives the row (`_creature_noise`: the
Well Thing dragging itself closer is "a wet dragging", faint), and the
resolve folds it into the beat's `sensory_events`, which perception and the
commit read. The fold looked for `out["state_diff"]` at a point where the
prose path's output is still only `{"ledgers": rows}` -- the diff is built
later -- so it found none, did nothing, and every creature on every prose
beat was silent to every observer (review 2026-11-01, director core F3).
"""

from __future__ import annotations

import agents.background as background
import agents.common as common
import agents.director as director

from tests.director_fakes import _make_ctx, _speech_interp, prose_resolve_agent

NOISE = {"kind": "sound", "room": "keeper_room", "level": "faint",
         "source": "Well Thing", "detail": "a wet dragging"}


def test_a_creatures_noise_is_in_the_resolved_beats_sensory_events(
        temp_db, monkeypatch, prose_director):
    ctx = _make_ctx(temp_db, interp=_speech_interp(), player_input="Quiet night.")
    monkeypatch.setattr(common, "lay_charter_figures",
                        lambda ctx_, sc, rooms: [{"name": "Well Thing",
                                                  "room": "keeper_room"}])
    monkeypatch.setattr(background, "declare_charter_figures",
                        lambda *a, **k: [{"name": "Well Thing", "char_id": None,
                                          "is_figure": True, "sequence": [],
                                          "sensory_events": [dict(NOISE)]}])
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": "Something drags itself across the stones."}))

    out = director.director_resolve(ctx, nonce=0)

    assert NOISE in ((out.get("state_diff") or {}).get("sensory_events") or []), \
        (out.get("state_diff") or {}).get("sensory_events")
