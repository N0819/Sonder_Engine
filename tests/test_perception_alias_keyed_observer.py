"""An observer the scene keys by one of their own aliases still perceives.

Live, chat 82 "Sarah Moon — Hinami attempt 2". The cast sheet's
`identity.name` was "Sarah Moon"; the Director created her scene entity as
"Dr. Sarah Moon" and keyed `positions`, `poses` and `stations` under that.
Both spellings are hers and neither writer was wrong — they simply disagreed
about which is primary, and the disagreement was invisible because the two
halves of the engine never compare notes: perception addresses a cast member
by the SHEET's name, the scene ledgers answer to the ENTITY's.

`room_of` did not join them, so it returned None for the observer's own name,
and None is not a small wrong answer. `visual_level_between`, `proximity_rel`,
`entity_arc` and `region_visibility` all begin by asking for two rooms and all
fail CLOSED on a miss — which reads exactly like distance, or a wall, or the
dark. Her view of the interview cell across the observation glass therefore
contained the room and nobody in it: no presence, no pose, no appearance, no
attire, and an empty `company` record. Every region of the woman she was
watching came back "concealed by vantage" while the attire ledger describing
those clothes was intact all along.

`agents.common.character_room` already walked a cast sheet's every key to
dodge this for the ROOM. Nothing dodged it for the RELATIONS, and the
relations are what a view is made of — so the fix belongs in `room_of`, the
one function all of them share.
"""

from __future__ import annotations

from agents import composer
from agents.common import observer_body_regions
from world.spatial import room_of, visual_level_between

# The observer is keyed under an alias of her sheet name; the body she is
# watching is one room away, seen through glass. Nothing here is about a
# mirror or a laboratory: the shape is "the ledger spells her one way and the
# reader asks the other".
OBSERVER_SHEET_NAME = "Sarah Moon"
SCENE = {
    "rooms": {
        "annex": {
            "name": "Observation Annex",
            "adjacent": [{"to": "cell", "barrier": "one_way_window",
                          "distance": "near"}],
            "light": "bright",
        },
        "cell": {"name": "Interview Cell", "adjacent": [], "light": "bright"},
    },
    "positions": {"Dr. Sarah Moon": "annex", "Hinami": "cell"},
    "entities": {
        "Dr. Sarah Moon": {
            "name": "Dr. Sarah Moon",
            "kind": "character",
            "aliases": ["Sarah Moon", "Dr. Moon"],
        },
        "Hinami": {"name": "Hinami", "kind": "character", "aliases": []},
    },
    "attire": {
        "Hinami": {
            "wearing": ["travel jacket", "travel shorts"],
            "regions": {
                "torso": {"garments": [{"name": "travel jacket",
                                        "state": "worn",
                                        "covers": ["torso"]}]},
                "legs": {"garments": [{"name": "travel shorts",
                                       "state": "worn",
                                       "covers": ["legs"]}]},
            },
        },
    },
}

OTHERS = [{"name": "Hinami", "room": "cell", "appearance": "a young woman",
           "aliases": []}]
DISPLAY = {"Hinami": "Hinami"}


def test_the_observers_own_name_finds_her_room():
    assert room_of(SCENE, OBSERVER_SHEET_NAME) == "annex"


def test_she_can_see_the_body_she_is_looking_at():
    assert visual_level_between(SCENE, OBSERVER_SHEET_NAME, "Hinami") == "full"


def test_the_body_arrives_as_a_presence_percept():
    percepts = composer.presence_percepts(
        SCENE, OBSERVER_SHEET_NAME, OTHERS, DISPLAY)
    bodies = [p.data.get("body") for p in percepts if p.kind == "presence"]
    assert bodies == [composer.body_key("Hinami")]


def test_the_attire_ledger_reaches_her_view():
    rows = observer_body_regions(
        SCENE, OBSERVER_SHEET_NAME,
        {OBSERVER_SHEET_NAME: "you", "Hinami": "Hinami"})
    seen = {row["body"]: row.get("regions") or {} for row in rows}
    assert "Hinami" in seen, "the watched body produced no attire row at all"
    assert "travel jacket" in seen["Hinami"].get("torso", "")
    assert "travel shorts" in seen["Hinami"].get("legs", "")


def test_the_gate_still_subtracts_when_there_is_nothing_to_see():
    """The repair widens WHO resolves, never WHAT crosses a wall."""
    walled = {**SCENE, "rooms": {
        **SCENE["rooms"],
        "annex": {**SCENE["rooms"]["annex"],
                  "adjacent": [{"to": "cell", "barrier": "wall"}]},
    }}
    assert visual_level_between(walled, OBSERVER_SHEET_NAME, "Hinami") == "none"
    assert not [p for p in composer.presence_percepts(
        walled, OBSERVER_SHEET_NAME, OTHERS, DISPLAY) if p.kind == "presence"]
