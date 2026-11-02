"""A reactor widening reads nothing the caller hands it.

Each `widen_reactors_*` read the committed scene, the chat row and the
persona for itself, from thirteen call sites a beat (agents_common audit,
Efficiency 1: a median live scene is ~50 KB and parses in ~0.8 ms, ~15-25 ms
a beat), though every caller already holds the scene and the player's name.
They now take both; a caller that hands them in costs no read, and one that
does not reads exactly as before.
"""

from __future__ import annotations

import pytest

from agents import common_beat


def _scene():
    return {"rooms": {"hall": {"name": "Hall", "adjacent": []},
                      "loft": {"name": "Loft", "adjacent": []}},
            "positions": {"Pip": "hall"}, "entities": {}}


@pytest.fixture
def no_reads(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("read the world it was handed: %r" % (args[:1],))
    monkeypatch.setattr(common_beat, "get_scene", refuse)
    monkeypatch.setattr(common_beat, "q", refuse)


def test_the_room_widenings_read_nothing_when_handed_the_scene(no_reads):
    interp = {"speech_volume": "normal", "flow": {}, "sequence": []}
    kw = {"scene": _scene(), "player_name": "Pip"}
    assert common_beat.widen_reactors_to_hearers(1, [], interp, [5], **kw) == [5]
    assert common_beat.widen_reactors_to_enclosure(1, [], [5], **kw) == [5]
    assert common_beat.widen_reactors_to_acted_upon(1, [], interp, [5], **kw) == [5]


def test_a_widening_handed_nothing_still_reads(monkeypatch):
    reads = []
    monkeypatch.setattr(common_beat, "get_scene",
                        lambda cid: reads.append("scene") or _scene())
    monkeypatch.setattr(common_beat, "q",
                        lambda *a, **k: reads.append("chat") or None)
    assert common_beat.widen_reactors_to_enclosure(1, [], [5]) == [5]
    assert reads == ["scene", "chat"]
