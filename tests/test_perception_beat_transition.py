"""An act that closes a channel must not erase the perception of itself.

Live, chat 58 "Run! ⎇10 ⎇20" t27. The player ran through the TARDIS's open
doors, the doors slammed, and the ship went `in_transit` — which correctly
severs the interior's exterior edges. All three happened in ONE beat, and
perception runs against the outcome scene, so by the time the Doctor's view was
built the room she had run into was adjacent to nothing. His view records the
doors closing on an empty doorway. He never saw her go in.

Nothing about the transit model is wrong here: a ship in flight IS cut off, and
`in_transit` with no destination yet is a legitimate state — the destination
does not have to be declared at the moment of departure. What was wrong is that
perception asked its question only of the beat's last frame.

`_source_channels` now takes `prev_sc` and answers over the whole beat: a
source counts as perceptible if it was reachable at EITHER end. It only ever
upgrades, so a body unreachable for the entire beat stays unreachable.

The same shape covers every act that shuts a channel it is seen through — a
slammed door, a drawn curtain, stepping into a container, a vehicle pulling
away.
"""

from __future__ import annotations

import pytest

from agents.perception import _saw_across_beat, _source_channels


def _scene(*, sealed):
    """A box in a yard. Open, its interior is a doorway off the yard; sealed,
    the interior is adjacent to nothing — the derived state a departing
    vehicle produces."""
    return {
        "rooms": {
            "yard": {"name": "Yard", "adjacent": []},
            "box_interior": {
                "name": "Box Interior",
                "parent_entity": "box",
                "adjacent": ([] if sealed else
                             [{"to": "yard", "barrier": "open_door",
                               "distance": "near"}]),
            },
        },
        "positions": {"Watcher": "yard", "Runner": ("box_interior" if sealed
                                                    else "yard"),
                      "box": "yard"},
        "entities": {"box": {"name": "A Box", "interior_rooms":
                             ["box_interior"]}},
    }


BEFORE = _scene(sealed=False)   # doors open, Runner still outside
AFTER = _scene(sealed=True)     # Runner inside, doors shut, interior severed

SOURCES = [{"name": "Runner", "room": "box_interior"}]


def test_the_live_failure_the_watcher_saw_nothing():
    """Baseline: asked only of the end state, the Runner is not perceptible —
    the room she ran into is adjacent to nothing."""
    ch = _source_channels(AFTER, "Watcher", "yard", SOURCES)
    assert ch["visual_channel_to_sources"]["Runner"] is False
    assert ch["spatial_to_sources"]["Runner"]["barrier"] == "separated"


def test_asking_over_the_beat_restores_it():
    ch = _source_channels(AFTER, "Watcher", "yard", SOURCES,
                          prev_sc=BEFORE)
    assert ch["visual_channel_to_sources"]["Runner"] is True
    # And the rel carries the marker, so a reader can tell this was a
    # transition rather than a standing line of sight.
    assert ch["spatial_to_sources"]["Runner"].get(
        "was_reachable_at_beat_start") is True


def test_it_only_ever_upgrades():
    """A body unreachable at BOTH ends of the beat stays unreachable. This
    opens nothing that was closed for the whole beat."""
    always_sealed = _scene(sealed=True)
    ch = _source_channels(AFTER, "Watcher", "yard", SOURCES,
                          prev_sc=always_sealed)
    assert ch["visual_channel_to_sources"]["Runner"] is False
    assert "was_reachable_at_beat_start" not in \
        ch["spatial_to_sources"]["Runner"]


def test_a_channel_the_beat_OPENED_is_not_downgraded():
    """The mirror case: she was sealed in and the doors opened. The end state
    grants sight and the start does not; the end must win."""
    ch = _source_channels(BEFORE, "Watcher", "yard",
                          [{"name": "Runner", "room": "yard"}],
                          prev_sc=AFTER)
    assert ch["visual_channel_to_sources"]["Runner"] is True


def test_no_prev_scene_is_the_old_behaviour_exactly():
    with_none = _source_channels(AFTER, "Watcher", "yard", SOURCES,
                                 prev_sc=None)
    bare = _source_channels(AFTER, "Watcher", "yard", SOURCES)
    assert with_none == bare


def test_the_helper_answers_each_end_independently():
    rel = {"same_room": False, "barrier": "separated"}
    assert _saw_across_beat(AFTER, BEFORE, "Watcher", "Runner", rel) is True
    assert _saw_across_beat(AFTER, None, "Watcher", "Runner", rel) is False
    assert _saw_across_beat(BEFORE, None, "Watcher", "Runner", rel) is True


def test_a_perceiver_who_moved_is_resolved_in_each_scene():
    """The perceiver can be the one who moved. Their room is looked up in the
    scene being asked, not carried over from the other one."""
    before = _scene(sealed=False)
    after = _scene(sealed=True)
    # This time the WATCHER is the one who went inside.
    after["positions"]["Watcher"] = "box_interior"
    after["positions"]["Runner"] = "yard"
    ch = _source_channels(after, "Watcher", "box_interior",
                          [{"name": "Runner", "room": "yard"}],
                          prev_sc=before)
    assert ch["visual_channel_to_sources"]["Runner"] is True
