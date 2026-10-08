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
from tests.helpers import model_fields_of


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
    assert "hands_over" in model_fields_of(BackgroundReactOutput)


def test_a_figure_the_director_resolved_is_not_applied_twice():
    """A charter figure declared BEFORE the resolve had its act resolved by
    the Director, whose encoder writes what moved: scratch story 165 turn
    4581, a keeper's declared reach for the premium book came back as the
    encoder's own `inventory_ops` transfer. Applying its `hands_over` here as
    well would put a second book in the room."""
    sc = _scene()
    reaction = _reaction()
    reaction[0]["is_figure"] = True
    assert apply_presence_handovers(sc, reaction, {}) == []
    assert sorted(sc["entities"]) == ["char_sal"]


def _served(temp_db, monkeypatch, answer):
    from tests.test_background_description_address import (
        DESCRIPTOR, THREE_TRADERS, _make_ctx)

    monkeypatch.setattr(background, "_agent_json",
                        lambda role, stage, prompt, payload, **kw: answer)
    ctx = _make_ctx(temp_db, THREE_TRADERS, addressed_refs=[DESCRIPTOR],
                    player_input="You. The man with the braided cords. An ale.")
    ctx["director_interpret"]["sequence"] = [
        {"type": "speech", "visibility": "overt", "volume": "normal",
         "text": "You. The man with the braided cords. An ale."}]
    out = background.background_react(ctx, nonce="seed")
    assert out["fired"], out
    return out["reactions"][0]


def test_the_voice_hands_its_service_fields_on(temp_db, monkeypatch):
    """THE PRODUCER SIDE, which nothing tested. From 2026-09-20, when the
    fields, the card clause and the applier were built, the reactor returned
    neither: on the 2026-10-07 scratch play db the model had set `still_owes`
    11 times and `hands_over` 3, and 0 of 342 stored declarations carried
    one -- so no promise was ever owed and nothing served changed hands."""
    reaction = _served(temp_db, monkeypatch, {
        "reacts": True, "action": "draws a mug and sets it down",
        "dialogue_log_entry": {"speaker": "?", "exact_quote": "There. Stew's coming."},
        "hands_over": {"what": " a mug of  ale ", "to": "the stranger"},
        "still_owes": {"what": "a bowl of stew", "to": "the stranger"}})
    assert reaction["hands_over"] == {"what": "a mug of ale", "to": "the stranger"}
    assert reaction["still_owes"] == {"what": "a bowl of stew", "to": "the stranger"}


def test_a_service_that_names_nothing_is_none(temp_db, monkeypatch):
    reaction = _served(temp_db, monkeypatch, {
        "reacts": True, "action": "nods", "dialogue_log_entry": None,
        "hands_over": {"what": "  ", "to": "the stranger"}, "still_owes": None})
    assert reaction["hands_over"] is None and reaction["still_owes"] is None
