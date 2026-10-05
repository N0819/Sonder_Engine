"""A beat's own sound event reaches the view in every language.

`ambient_percepts(order_key=...)` puts a beat's sound into the numbered
deliveries (chat 117 turn 65: the carbonic stalker's siphon-vent hiss had
been delivered as standing state and the prose said nothing moved). The
English renderer then had no event branch for an ambient percept, so every
one composed to '' -- while the Japanese adapter rendered it. Found
2026-10-04 by a look at the horizon (`vista_percepts`) that never arrived.
"""

from __future__ import annotations

from agents.composer import ambient_percepts, render_view

HISS = [{"kind": "sound", "room": "hall", "level": "loud",
         "detail": "a slow, rhythmic siphon-vent hiss nearby"}]


def test_an_ordered_ambient_percept_renders_in_english_for_player_and_character():
    percepts = ambient_percepts(HISS, "hall", order_key=500000)
    assert percepts and percepts[0].order_key == 500000
    for mode in ("player", "character"):
        text = render_view(percepts, mode=mode, full_render=True).text
        assert "siphon-vent hiss" in text, mode


def test_standing_ambience_renders_as_it_always_did():
    percepts = ambient_percepts(HISS, "hall")
    assert percepts[0].order_key is None
    assert "siphon-vent hiss" in render_view(percepts, mode="player", full_render=True).text
