"""A view may not describe a body the perceiver has no way to perceive.

Live, chat 58 "Run! ⎇10 ⎇20" t28. Hinami slammed the TARDIS doors and stood in
the console room; the Dalek stood outside. The engine already knew the pair was
unreachable — `visual_level_between` returns 'none' and `spatial_rel` calls the
two rooms `separated`/`far`, no connecting geometry at all — and nothing
consumed that answer once the view was prose, so her actions were narrated into
the Dalek's view and from there into the Dalek's own next-turn context.

`_strip_unreachable_bodies` is the HARD case only: no sensory channel of any
kind. A body the perceiver cannot see but can still hear through a shut door is
deliberately left alone, because a view is what a mind receives and silence
about someone audibly present is its own lie. The narrower case — sight
asserted where only hearing exists — needs sense-cue analysis and is not this
guard's job.
"""

from __future__ import annotations

from agents.perception import _strip_unreachable_bodies

ROSTER = [{"name": "A Dalek"}, {"name": "The Doctor"}, {"name": "Hinami"}]

# console room --(closed door)-- alley --(open)-- street.
# The Dalek is on the street; Hinami is inside. Two hops, no edge between them.
SEALED = {
    "rooms": {
        "alley": {"name": "Alley", "adjacent": []},
        "console": {"name": "Console Room",
                    "adjacent": [{"to": "alley", "barrier": "closed_door",
                                  "distance": "near"}]},
        "street": {"name": "Street",
                   "adjacent": [{"to": "alley", "barrier": "open",
                                 "distance": "near"}]},
    },
    "positions": {"A Dalek": "street", "The Doctor": "street",
                  "Hinami": "console"},
}

VIEW = ("The rain-slicked street glints under dim streetlights. "
        "Hinami leans against the doors, her chest heaving. "
        "The Doctor pivots, fingers tight around a humming sonic screwdriver. "
        "Hinami's tails flick behind her in the amber light.")


def test_the_live_failure_is_removed():
    kept, dropped = _strip_unreachable_bodies(VIEW, "A Dalek", SEALED, ROSTER)
    assert len(dropped) == 2
    assert all("Hinami" in d for d in dropped)
    assert "Hinami" not in kept


def test_a_reachable_body_is_left_alone():
    kept, dropped = _strip_unreachable_bodies(VIEW, "A Dalek", SEALED, ROSTER)
    # The Doctor is standing on the same street; nothing about him moves.
    assert "The Doctor pivots" in kept
    assert "rain-slicked street" in kept


def test_the_possessive_form_is_caught_too():
    view = ("Rain falls steadily. "
            "Hinami's tails flick behind her in the amber light.")
    kept, dropped = _strip_unreachable_bodies(view, "A Dalek", SEALED, ROSTER)
    assert dropped == ["Hinami's tails flick behind her in the amber light."]
    assert kept == "Rain falls steadily."


def test_a_body_one_hop_away_behind_a_shut_door_is_NOT_dropped():
    """The deliberate limit. From the alley, the console room is a closed door
    away — the Dalek cannot SEE her but could hear her through it, so the
    channel exists and this guard must not touch the sentence. Over-denial
    would be the worse failure."""
    near = {**SEALED, "positions": {**SEALED["positions"], "A Dalek": "alley"}}
    kept, dropped = _strip_unreachable_bodies(VIEW, "A Dalek", near, ROSTER)
    assert dropped == []
    assert kept == VIEW


def test_same_room_is_never_dropped():
    """Standing with her, the Dalek keeps every sentence about her. The Doctor
    two rooms off is correctly dropped in the same pass — the guard is
    per-body, not per-view."""
    together = {**SEALED,
                "positions": {**SEALED["positions"], "A Dalek": "console"}}
    kept, dropped = _strip_unreachable_bodies(VIEW, "A Dalek", together, ROSTER)
    assert not any("Hinami" in d for d in dropped)
    assert "Hinami leans against the doors" in kept
    assert dropped == ["The Doctor pivots, fingers tight around a humming "
                       "sonic screwdriver."]


def test_the_perceiver_is_never_dropped_from_their_own_view():
    view = ("A Dalek grinds forward across the pavement. "
            "Hinami leans against the doors.")
    kept, dropped = _strip_unreachable_bodies(view, "A Dalek", SEALED, ROSTER)
    assert dropped == ["Hinami leans against the doors."]
    assert "A Dalek grinds forward" in kept


def test_a_view_is_never_emptied_entirely():
    # Every sentence is about the unreachable body: beyond repair by deletion,
    # so it is left alone for the warning to carry — same rule as
    # _strip_self_narration.
    view = "Hinami leans against the doors. Hinami's tails flick."
    kept, dropped = _strip_unreachable_bodies(view, "A Dalek", SEALED, ROSTER)
    assert dropped == []
    assert kept == view


def test_missing_inputs_are_noops():
    assert _strip_unreachable_bodies("", "A Dalek", SEALED, ROSTER) == ("", [])
    assert _strip_unreachable_bodies(VIEW, "", SEALED, ROSTER) == (VIEW, [])
    assert _strip_unreachable_bodies(VIEW, "A Dalek", None, ROSTER) == (VIEW, [])
    assert _strip_unreachable_bodies(VIEW, "A Dalek", SEALED, []) == (VIEW, [])


def test_a_body_with_no_room_at_all_is_unreachable():
    """`spatial_rel` answers 'unknown' when one side has no room. That is not a
    licence to describe them — it is the absence of any basis for doing so."""
    floating = {**SEALED,
                "positions": {"A Dalek": "street", "The Doctor": "street"}}
    kept, dropped = _strip_unreachable_bodies(
        VIEW, "A Dalek", floating, ROSTER)
    assert any("Hinami" in d for d in dropped)
    assert "The Doctor pivots" in kept
