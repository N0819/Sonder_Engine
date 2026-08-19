"""A view may not describe a body the perceiver has no way to perceive.

Live, chat 58 "Run! ⎇10 ⎇20" t28. Hinami slammed the TARDIS doors and stood in
the console room; the Dalek stood outside. The engine already knew the pair was
unreachable — `visual_level_between` returns 'none' and `spatial_rel` calls the
two rooms `separated`/`far`, no connecting geometry at all — and nothing
consumed that answer once the view was prose, so her actions were narrated into
the Dalek's view and from there into the Dalek's own next-turn context.

THE GUARD MOVED FROM THE PROSE TO THE IR, which is why this file no longer
tests `perception._strip_unreachable_bodies`. That function read a finished
view back, cut sentences that named an unreachable body, and refused to empty a
view entirely — a repair pass, with all a repair pass's edges: possessive
forms, the perceiver's own name, the view left beyond repair. `composer` now
builds the view instead of checking it, and `visual_level_between` is consulted
BEFORE any sentence exists: a body it answers 'none' for yields no presence
percept, no pose percept and no appearance percept, so there is no sentence to
cut. Subtraction at the source, which is the shape every guard in this engine
is supposed to have.

The deliberate limit survives the move and is asserted below: a body the
perceiver cannot see but can still HEAR is not silenced. Sight gates the
presence percept; the event channels are gated separately and independently,
so a voice through a shut door still arrives. Over-denial would be the worse
failure — a view is what a mind receives, and silence about someone audibly
present is its own lie.
"""

from __future__ import annotations

from agents import composer

ROSTER = [{"name": "A Dalek"}, {"name": "The Doctor"}, {"name": "Hinami"}]
DISPLAY = {"A Dalek": "A Dalek", "The Doctor": "The Doctor",
           "Hinami": "Hinami"}

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


def _others(scene, observer):
    return [b for b in ROSTER if b["name"] != observer]


def _view(scene, observer):
    percepts = composer.presence_percepts(
        scene, observer, _others(scene, observer), DISPLAY)
    percepts += composer.pose_percepts(
        scene, observer, _others(scene, observer), DISPLAY)
    return composer.render_view(percepts, mode="character").text


def _bodies(scene, observer):
    return {p.data.get("body") for p in composer.presence_percepts(
        scene, observer, _others(scene, observer), DISPLAY)}


def test_the_live_failure_never_becomes_a_percept():
    assert composer.body_key("Hinami") not in _bodies(SEALED, "A Dalek")
    assert "Hinami" not in _view(SEALED, "A Dalek")


def test_a_reachable_body_is_composed_about():
    """The Doctor is standing on the same street; nothing about him moves."""
    assert composer.body_key("The Doctor") in _bodies(SEALED, "A Dalek")
    assert "The Doctor" in _view(SEALED, "A Dalek")


def test_a_body_one_hop_away_behind_a_shut_door_is_still_audible():
    """The deliberate limit. From the alley, the console room is a closed door
    away — the Dalek cannot SEE her, so she is not a presence in his view; but
    the hearing channel is gated separately and her voice still arrives. The
    old guard could only refuse to cut a sentence; this one never had to
    conflate the two channels in the first place."""
    near = {**SEALED, "positions": {**SEALED["positions"], "A Dalek": "alley"}}

    assert composer.body_key("Hinami") not in _bodies(near, "A Dalek")
    heard = composer.speech_percept(
        {"speaker": "Hinami", "exact_quote": "get back", "volume": "shout"},
        {"same_room": False, "barrier": "closed_door", "distance": "near"},
        "A Dalek", display="Hinami", can_see=False, order_key=1)
    assert heard is not None
    assert "get back" in composer.render_view(
        [heard], mode="character").text


def test_same_room_is_composed_about_per_body():
    """Standing with her, the Dalek gets her. The Doctor two rooms off is
    correctly absent from the same view — the gate is per-body, not
    per-view."""
    together = {**SEALED,
                "positions": {**SEALED["positions"], "A Dalek": "console"}}
    bodies = _bodies(together, "A Dalek")

    assert composer.body_key("Hinami") in bodies
    assert composer.body_key("The Doctor") not in bodies


def test_the_perceiver_is_never_a_presence_in_their_own_view():
    """Not a repair, a construction: `presence_percepts` skips the observer,
    so the perceiver's own name cannot reach their own presence sentence."""
    assert composer.body_key("A Dalek") not in _bodies(SEALED, "A Dalek")


def test_a_view_with_nothing_admitted_is_empty_rather_than_wrong():
    """The old guard refused to empty a view, because an emptied view was
    worse than an over-broad one and there was no third option once the prose
    existed. There is now: nothing was admitted, so nothing is rendered, and
    the empty view is the true answer rather than a failure mode."""
    alone = {**SEALED, "positions": {"A Dalek": "street", "Hinami": "console"}}

    assert _bodies(alone, "A Dalek") == set()
    assert _view(alone, "A Dalek") == ""


def test_missing_inputs_are_noops():
    assert composer.presence_percepts(SEALED, "", ROSTER, DISPLAY) == []
    assert composer.presence_percepts(SEALED, "A Dalek", [], DISPLAY) == []


def test_a_body_with_no_room_at_all_is_unreachable():
    """`spatial_rel` answers 'unknown' when one side has no room. That is not a
    licence to describe them — it is the absence of any basis for doing so."""
    floating = {**SEALED,
                "positions": {"A Dalek": "street", "The Doctor": "street"}}

    assert composer.body_key("Hinami") not in _bodies(floating, "A Dalek")
    assert composer.body_key("The Doctor") in _bodies(floating, "A Dalek")
