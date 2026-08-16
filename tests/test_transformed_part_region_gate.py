"""A part whose placement the verdict map does not know is CONCEALED.

`region_visibility` is keyed by `attire.REGIONS`. A part authored on a CARD is
coerced to those keys (`character_schema._extra_part_placement`), so the gate
in `observer_body_regions` always found a verdict and every card-path test
passed. A part minted by a `physical_transformation` is different: the body
specialist writes `at` as free prose and NOTHING normalises it. `.get()` missed,
the empty verdict read as "not concealed", and the gate failed OPEN.

Live, chat 76 turn 71. Hinami showering behind a closed bathroom door; The
Doctor in the adjoining room. Every one of the eight regions correctly returned
`{"visibility": "concealed", "by": {"vantage": ["out of sight"]}}` -- and he
still received, as a SIGHT percept:

    "Two fox ears emerge from the fluffy, pointed, golden of Hinami's top of
     the head. Six tails emerge from the golden and fluffy of Hinami's back of
     the waist."

It reached his view, his structured observations, and his character step, which
appraised it as "Hinami's fox ears and six tails are fully visible". The stored
condition (minted at turn 52, branched from chat 74) carries
`at: "top of the head"` and `at: "back of the waist"`.

A guard on the firewall must fail CLOSED. A missing key is not evidence of
exposure, and the deterministic floor may never depend on a model having
written a word from the right vocabulary.
"""

from __future__ import annotations

from agents.common import observer_body_regions

ROOMS = {
    "bedroom": {"name": "Bedroom",
                "adjacent": [{"to": "bathroom", "barrier": "closed_door",
                              "dir": "e"}]},
    "bathroom": {"name": "Bathroom",
                 "adjacent": [{"to": "bedroom", "barrier": "closed_door",
                               "dir": "w"}]},
}

# Exactly the shape the body specialist minted, free-text `at` and all.
TRANSFORMED = [
    {"kind": "fox ears", "count": 2, "at": "top of the head",
     "aspect": "fluffy, pointed, golden"},
    {"kind": "tails", "count": 6, "at": "back of the waist",
     "aspect": "golden and fluffy"},
]
# The same anatomy with the canonical placements a card would have produced.
CANONICAL = [
    {"kind": "fox ears", "count": 2, "at": "head", "aspect": "top"},
    {"kind": "tails", "count": 6, "at": "waist", "aspect": "back"},
]


def _scene(same_room):
    return {
        "rooms": dict(ROOMS),
        "positions": {"Doctor": "bedroom",
                      "Hinami": "bedroom" if same_room else "bathroom"},
        "attire": {"Hinami": {"wearing": []}},
    }


def _parts(rows):
    return [p for row in rows for p in (row.get("parts") or [])]


# -- the leak ---------------------------------------------------------------

def test_a_free_text_placement_does_not_leak_through_a_closed_door():
    """THE regression. Nothing about this body may reach an observer who
    cannot see it, whatever vocabulary the placement was written in."""
    rows = observer_body_regions(_scene(False), "Doctor",
                                 {"Hinami": "the traveller"},
                                 extra_parts={"Hinami": TRANSFORMED})
    assert rows == [], f"leaked through a closed door: {rows!r}"


def test_the_canonical_spelling_was_never_the_leaking_one():
    """Pins that the card path was always safe -- which is exactly why this
    went unseen for nineteen turns."""
    rows = observer_body_regions(_scene(False), "Doctor",
                                 {"Hinami": "the traveller"},
                                 extra_parts={"Hinami": CANONICAL})
    assert rows == []


def test_darkness_conceals_a_free_text_placement_too():
    """Vantage is body-level; the placement vocabulary must not decide it."""
    dark = {"rooms": {"cellar": {"name": "Cellar", "light": "dark"}},
            "positions": {"Doctor": "cellar", "Hinami": "cellar"},
            "attire": {"Hinami": {"wearing": []}}}
    rows = observer_body_regions(dark, "Doctor", {"Hinami": "the traveller"},
                                 extra_parts={"Hinami": TRANSFORMED})
    assert rows == []


# -- and it still delivers what it should ----------------------------------

def test_a_free_text_placement_is_still_delivered_when_the_body_is_visible():
    """Failing closed must not mean failing silent: an observer in the room
    still sees the ears and the tails. The fix resolves the placement, it does
    not discard it."""
    rows = observer_body_regions(_scene(True), "Doctor",
                                 {"Hinami": "the traveller"},
                                 extra_parts={"Hinami": TRANSFORMED})
    parts = _parts(rows)
    assert any("fox ears" in p for p in parts), parts
    assert any("tails" in p for p in parts), parts


def test_the_free_text_and_canonical_spellings_agree_when_visible():
    """The resolution maps onto the card path rather than inventing a second
    behaviour: 'top of the head' is the head, 'back of the waist' the waist."""
    seen_free = _parts(observer_body_regions(
        _scene(True), "Doctor", {"Hinami": "the traveller"},
        extra_parts={"Hinami": TRANSFORMED}))
    seen_canon = _parts(observer_body_regions(
        _scene(True), "Doctor", {"Hinami": "the traveller"},
        extra_parts={"Hinami": CANONICAL}))
    assert len(seen_free) == len(seen_canon) == 2


def test_a_body_still_knows_its_own_transformed_anatomy():
    """The self-knowledge floor is unchanged: concealment from others is never
    concealment from yourself."""
    rows = observer_body_regions(_scene(False), "Hinami", {"Hinami": "you"},
                                 extra_parts={"Hinami": TRANSFORMED})
    assert any("fox ears" in p for p in _parts(rows))


def test_an_unknown_kind_with_an_unknown_placement_still_fails_closed():
    """The general statement, not the live instance: any placement this map
    cannot resolve is treated as concealed when the body is unseen."""
    weird = [{"kind": "chitinous frill", "count": 1,
              "at": "somewhere along the spine", "aspect": "iridescent"}]
    assert observer_body_regions(_scene(False), "Doctor",
                                 {"Hinami": "the traveller"},
                                 extra_parts={"Hinami": weird}) == []
