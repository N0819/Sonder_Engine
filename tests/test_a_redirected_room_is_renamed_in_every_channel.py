"""A minted room redirected onto the room the scene already holds is renamed
in EVERY channel of the beat, not in the ones somebody listed.

`dedup_minted_rooms` redirects a beat's mint (`deck_three`) onto the room the
scene already holds (`deck_3`), and `_apply_room_renames` rewrote the rooms
table, adjacency, positions, room removals, interior rooms and transit --
nothing else. So the same beat's `sensory_events[].room`,
`inventory_ops[].to_id`, `movement_refused[].to_room` and a pose's
room-valued `support` kept `deck_three`; `_record_sensory_events` then
dropped the event as naming "a room this scene does not hold", so the
beat's noise was heard nowhere, and a set-down "onto deck three" resolved
nowhere and stayed in the hand.

Measured (review 2026-11-01, persist_scene_entities F6): after
`_apply_room_renames(diff, {"deck_three": "deck_3"})` only `positions` and
`rooms` had moved. The entity sibling (`_apply_entity_renames`) states the
class: "A per-channel rewrite would have to be extended by hand ... which is
how the room sibling's own list grew".
"""

from __future__ import annotations

from persist.commit import _apply_room_renames

RENAMES = {"deck_three": "deck_3"}


def _diff():
    return {
        "rooms": {"deck_three": {"name": "Deck Three",
                                 "adjacent": [{"to": "lift"}]},
                  "lift": {"name": "Lift",
                           "adjacent": [{"to": "deck_three"}]}},
        "positions": {"Mara": "deck_three"},
        "sensory_events": [{"room": "deck_three", "kind": "sound",
                            "description": "a bulkhead slams",
                            "level": "loud"}],
        "inventory_ops": [{"op": "move", "object_id": "crate",
                           "from_id": "Mara", "to_id": "deck_three"}],
        "movement_refused": [{"who": "Mara", "to_room": "deck_three"}],
        "poses": {"Mara": {"posture": "kneeling", "support": "deck_three"}},
        "charter_ops": [{"op": "errand", "body": "hand", "to": "deck_three"}],
        "entities": {"shuttle": {"name": "Shuttle",
                                 "interior_rooms": ["deck_three", "deck_3"],
                                 "state": {"transit": {
                                     "destination_room": "deck_three"}}}},
        "causal_steps": [{"patch": {
            "positions": {"Tam": "deck_three"},
            "sensory_events": [{"room": "deck_three", "kind": "sound"}]}}],
    }


def test_every_room_valued_field_follows_the_redirect():
    diff = _diff()
    _apply_room_renames(diff, RENAMES)
    assert diff["sensory_events"][0]["room"] == "deck_3"
    assert diff["inventory_ops"][0]["to_id"] == "deck_3"
    assert diff["movement_refused"][0]["to_room"] == "deck_3"
    assert diff["poses"]["Mara"]["support"] == "deck_3"
    assert diff["charter_ops"][0]["to"] == "deck_3"
    step = diff["causal_steps"][0]["patch"]
    assert step["positions"]["Tam"] == "deck_3"
    assert step["sensory_events"][0]["room"] == "deck_3"


def test_the_channels_it_already_rewrote_still_follow():
    diff = _diff()
    _apply_room_renames(diff, RENAMES)
    assert "deck_three" not in diff["rooms"] and "deck_3" in diff["rooms"]
    assert diff["rooms"]["lift"]["adjacent"][0]["to"] == "deck_3"
    assert diff["positions"]["Mara"] == "deck_3"
    shuttle = diff["entities"]["shuttle"]
    assert shuttle["interior_rooms"] == ["deck_3"], \
        "a rename that makes two entries one keeps one"
    assert shuttle["state"]["transit"]["destination_room"] == "deck_3"


def test_a_key_is_never_renamed_only_a_value():
    """A dict KEY in a channel is a subject (a body, an entity), never a
    room: a body that happens to be keyed like the minted room is not
    renamed onto another key."""
    diff = {"positions": {"deck_three": "deck_three"}}
    _apply_room_renames(diff, RENAMES)
    assert diff["positions"] == {"deck_three": "deck_3"}


def test_prose_is_not_a_room_reference():
    """Exact strings only: a sentence that mentions the key is prose."""
    diff = {"sensory_events": [{"room": "lift",
                                "description": "deck_three echoes"}]}
    _apply_room_renames(diff, RENAMES)
    assert diff["sensory_events"][0]["description"] == "deck_three echoes"
