"""A body that serves somebody puts a thing in their hands.

A background reaction could speak (`dialogue_log_entry`), walk (`goes_to`) and
perform a social act (`charter_act`), and could not change one physical fact.
`apply_presence_departures` names the class in its own docstring -- "a
background reaction is stateless, and until now nothing it said could change
where its figure stands ... `action` is prose nobody reads" -- and repaired it
for MOVEMENT with a typed field and a commit-side applier. This is the same
repair for a handover.

Measured (Aldermill, fourth run, 2026-09-19). Sal Weatherby ordered a small
ale; the ostler pointed her at the tapster; the tapster answered

    "Right away for you."
    Robanot wipes his wet knuckles against his tabard and reaches down a
    clean earthenware mug from the shelf.

-- and nothing left the shelf. `inventory_ops` empty, `entities` unchanged.
The most ordinary transaction a tavern has could be described and not done.

THE FLOOR IS CODE'S, NEVER THE MODEL'S, exactly as the departure applier
says: the recipient must be a body standing in the same room, and a figure
cannot hand over what it is not there to hand over.
"""

import agents.background as background
from persist.commit import apply_presence_handovers


SCENE = {
    "rooms": {"taproom": {"name": "Taproom"}, "yard": {"name": "Yard"}},
    "positions": {"Sal Weatherby": "taproom", "Robanot": "taproom",
                  "Bram": "yard"},
    "entities": {"char_sal": {"name": "Sal Weatherby", "kind": "person"}},
}


def _scene():
    import copy
    return copy.deepcopy(SCENE)


def _reaction(what="a mug of small ale", to="Sal Weatherby", name="Robanot"):
    return [{"name": name, "room": "taproom",
             "hands_over": {"what": what, "to": to}}]


def test_the_ale_ends_up_in_her_hands():
    sc = _scene()
    moved = apply_presence_handovers(sc, _reaction(), {})
    assert moved, "a served drink must change hands"
    key = moved[0][2]
    assert sc["entities"][key]["name"] == "a mug of small ale"
    assert sc["entities"][key].get("portable") is True
    # A HELD THING LIVES IN `contained`, not `positions` -- its room is
    # derived from its holder's (`derive_contained_positions`), which is what
    # keeps a carried mug from being in two places.
    held = (sc.get("contained") or {}).get(key) or {}
    assert held.get("in") in ("Sal Weatherby", "char_sal"), held
    assert held.get("mode") == "held"


def test_a_recipient_in_another_room_is_refused():
    """The same floor the departure applier keeps: a figure cannot hand a
    thing to somebody it is not standing with."""
    sc = _scene()
    warned = []
    assert apply_presence_handovers(sc, _reaction(to="Bram"), {},
                                    warn=warned.append) == []
    assert warned and "Bram" in warned[0]


def test_a_recipient_nobody_knows_is_refused():
    sc = _scene()
    assert apply_presence_handovers(sc, _reaction(to="the Queen"), {}) == []


def test_a_nameless_thing_is_refused():
    sc = _scene()
    assert apply_presence_handovers(sc, _reaction(what="  "), {}) == []


def test_the_field_is_on_the_reaction_schema():
    from llm.schemas import BackgroundReactOutput
    assert "hands_over" in BackgroundReactOutput.model_fields
