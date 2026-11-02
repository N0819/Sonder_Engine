"""Where a body walks is its own; where the world puts it is the world's.

`director_prose.a_walk_is_its_owners` keeps a mind in its room when another
mind's declaration writes its walk (owner ruling, 2026-10-07), and leaves the
world its moves: a `world`/`mechanical` input, a hold, a carry, an inside
joining the moved mind to the declarer. The encoder's own card says the rest
of the class (`encoder/positions.txt`): "A body that is moved rather than
moving -- dragged, carried off by a current or a press, dropped through a
floor ... ends where the prose leaves it". Audit of 2026-11-01
(`agents_director_prose_movement_rooms` F1), reproduced:

* a passenger riding in the cart the player drives -- `contained` in it as
  the beat began -- was refused, and because the floor read the event as the
  passenger's own conduct (`_doer_alone` counted one BODY, the cart being a
  thing), the cart's own move went with it: "kept: []";
* "The rotten boards give way under Elias and he drops into the barn below"
  in the player's stamp lost the boards' breaking with his fall.

The rule, in the engine's vocabulary: A BODY BORNE BY WHAT MOVES IS MOVED BY
THE WORLD -- what it is inside or upon, a body joined to it by a contact, the
fixture it rests on, the room it stands in -- moved to where it goes, or
taken out of the world in the same event. And the floor refuses only the
span it judges: an event that writes more than one mind's own conduct keeps
everything that is not that mind's walk.
"""

from __future__ import annotations

import copy

from agents.director_prose import a_walk_is_its_owners

RHONA, ELIAS, HESTER = "Rhona Carrick", "Elias Thorne", "Hester Gale"
INDEX = {"persona:1": RHONA, "character:2": ELIAS, "character:81": HESTER}
STAMP = "turn:3:primary:raw"
INPUTS = [{"entity_id": "persona:1", "authority_mode": "world_author",
           "events": [{"event_id": STAMP, "type": "raw_input"}]}]

YARD = {
    "rooms": {"yard": {"name": "The Yard", "adjacent": [{"to": "road", "barrier": "open"}]},
              "road": {"name": "The Road", "adjacent": [{"to": "yard", "barrier": "open"}]},
              "loft": {"name": "The Loft", "level": 2,
                       "adjacent": [{"to": "barn", "barrier": "open", "vertical": "down"}]},
              "barn": {"name": "The Barn", "level": 1,
                       "adjacent": [{"to": "loft", "barrier": "open", "vertical": "up"}]}},
    "positions": {RHONA: "yard", ELIAS: "yard", HESTER: "yard", "cart": "yard"},
    "entities": {"cart": {"name": "the cart", "kind": "vehicle"},
                 "loft_boards": {"name": "the loft boards", "kind": "fixture"}},
    "contained": {ELIAS: {"in": "cart", "mode": "riding"}},
    "contacts": [], "poses": {},
}


def _floor(events, scene=None, inputs=INPUTS):
    warnings, rows = [], []
    out = a_walk_is_its_owners(copy.deepcopy(events), inputs, INDEX,
                               copy.deepcopy(YARD if scene is None else scene),
                               warn=warnings.append, refusals=rows)
    return out, rows, warnings


def _drives(passenger_room="road", cart_patch=None):
    patch = {"positions": {"cart": "road", RHONA: "road", ELIAS: passenger_room}}
    if cart_patch:
        patch = cart_patch
    return {"source_entity_id": "persona:1", "source_event_id": STAMP,
            "event": "Rhona drives the cart out of the yard onto the road, "
                     "Elias riding in the back.",
            "observable": "drives the cart out onto the road", "speech": False,
            "movement": None, "item_names": ["the cart", ELIAS],
            "transforms": [{"item": "the cart", "patch": patch}]}


def test_a_passenger_rides_the_cart_the_player_drives():
    """The audit's driven cart: `kept: []`, the cart's move offered to the
    passenger as his own act. He is in the cart; the cart goes; so does he."""
    out, rows, warnings = _floor([_drives()])
    assert out == [_drives()]
    assert rows == [] and warnings == []


def test_a_vehicle_moved_by_its_movement_carries_its_passenger_too():
    driven = _drives(cart_patch={"positions": {ELIAS: "road"}})
    driven["movement"] = {"to_room": "road", "mover": "cart", "arrives": True}
    out, rows, warnings = _floor([driven])
    assert out == [driven] and rows == [] and warnings == []


def test_a_passenger_written_somewhere_the_cart_did_not_go_walked_there():
    """Borne means taken where the bearer goes: written into another room
    than the cart's, he walked, and the floor keeps him -- the cart's move
    and the player's own drive still stand."""
    out, rows, warnings = _floor([_drives(passenger_room="loft")])
    assert len(out) == 1
    assert out[0]["transforms"][0]["patch"]["positions"] == {"cart": "road", RHONA: "road"}
    assert [row["mind"] for row in rows] == ["character:2"]
    assert warnings and ELIAS in warnings[0]


def test_a_mind_the_floor_keeps_carries_nobody():
    """Riding a mind whose own move the floor refuses is no carriage: the
    bearer stays, so the borne stays with it."""
    scene = dict(copy.deepcopy(YARD), contained={ELIAS: {"in": HESTER, "mode": "riding"}})
    event = _drives(cart_patch={"positions": {HESTER: "road", ELIAS: "road"}})
    out, rows, _w = _floor([event], scene=scene)
    assert sorted(row["mind"] for row in rows) == ["character:2", "character:81"]
    assert all(ELIAS not in (t["patch"].get("positions") or {})
               and HESTER not in (t["patch"].get("positions") or {})
               for e in out for t in e["transforms"])


def _gives_way(extra):
    patch = {"positions": {ELIAS: "barn"}}
    patch.update(extra)
    return {"source_entity_id": "persona:1", "source_event_id": STAMP,
            "event": "The rotten boards give way under Elias and he drops into "
                     "the barn below.",
            "observable": "the boards give way and Elias drops through",
            "speech": False, "movement": None,
            "item_names": ["the loft boards", ELIAS],
            "transforms": [{"item": "the loft boards", "patch": patch}]}


LOFT = dict(copy.deepcopy(YARD),
            positions={RHONA: "loft", ELIAS: "loft"}, contained={},
            poses={ELIAS: {"posture": "standing", "support": "loft_boards",
                           "relative_to": "", "relation": "on", "constraint": "",
                           "detail": ""}})


def test_the_floor_refuses_only_the_span_it_judges():
    """The audit's fall, as the encoder wrote it: the boards' new state is a
    word (`entities`), which says nothing typed about where a body goes, so
    his drop is still another's declaration moving him -- refused and
    offered. But the event is not HIS conduct alone: the boards break."""
    event = _gives_way({"entities": {"loft_boards": {"state": {"condition": "broken"}}}})
    out, rows, warnings = _floor([event], scene=LOFT)
    assert len(out) == 1, "the boards' breaking is no mind's walk"
    patch = out[0]["transforms"][0]["patch"]
    assert patch == {"entities": {"loft_boards": {"state": {"condition": "broken"}}}}
    assert [(row["mind"], row["to"]) for row in rows] == [("character:2", "barn")]
    assert warnings and ELIAS in warnings[0]


def test_a_body_whose_footing_is_taken_out_of_the_world_falls_with_it():
    """The boards GONE (`remove_entities`), the thing his pose rests on: what
    bore him left the world in this event, and the world puts him where the
    prose leaves him."""
    event = _gives_way({"remove_entities": ["loft_boards"]})
    out, rows, warnings = _floor([event], scene=LOFT)
    assert out == [event] and rows == [] and warnings == []


def test_a_body_whose_footing_falls_with_it_is_carried_down():
    """The boards fall into the barn too (`positions`): a bearer moved to
    where the body goes."""
    event = _gives_way({"positions": {ELIAS: "barn", "loft_boards": "barn"}})
    out, rows, warnings = _floor([event], scene=LOFT)
    assert out == [event] and rows == [] and warnings == []


def test_a_room_taken_out_of_the_world_puts_its_people_out_of_it():
    """`destruction` and `remove_rooms` require everyone in the place to be
    moved in the same beat or the destruction is refused (encoder card
    `destruction`): the floor must not keep a body in a room the world is
    taking away."""
    event = _gives_way({"remove_rooms": ["loft"]})
    out, rows, warnings = _floor([event], scene=LOFT)
    assert out == [event] and rows == [] and warnings == []


def test_his_own_walk_written_under_her_is_still_dropped_whole():
    """The lighthouse class stands: an event whose every write is his own
    body's is his conduct, dropped whole and offered in its own words."""
    walks = {"source_entity_id": "persona:1", "source_event_id": STAMP,
             "event": "Elias climbs up into the loft.",
             "observable": "climbs up into the loft", "speech": False,
             "movement": None, "item_names": [ELIAS],
             "transforms": [{"item": ELIAS, "patch": {
                 "positions": {ELIAS: "loft"},
                 "attire": {ELIAS: {"add": ["straw hat"]}}}}]}
    out, rows, _w = _floor([walks])
    assert out == []
    assert [(row["mind"], row["event"]) for row in rows] == [
        ("character:2", "climbs up into the loft")]
