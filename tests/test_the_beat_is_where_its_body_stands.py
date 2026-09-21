"""A thing is minted where the body that reached for it stood.

`director.mint_unreferenced_things` stands up a thing the beat acted on and
the world does not hold, and it needs a room to stand it in. `_beat_room`
derived that room from the positions of the ledger's own objects -- which
answers itself on every beat but the one that matters: the beat needing a
mint is exactly the beat whose object the world has no record, and therefore
no position, for.

Measured, two_lives v5 (2026-09-19) turn 17: Emory Vane pressed his
fingertips to the seam where a turning brass collar met wet oak. The ledger's
one object was "brass collar seam", the contact hand settled it
`no_referent`, and the mint built to answer that refused -- the only room it
could have used was the missing thing's own. The acting body's position was
in the scene the whole time.
"""

from __future__ import annotations

from agents.director import _beat_room

SCENE = {"rooms": {"mill_race": {"name": "Mill Race", "adjacent": []},
                   "grist_mill": {"name": "Grist Mill", "adjacent": []}},
         "positions": {"Emory Vane": "mill_race", "Sal Weatherby": "grist_mill"},
         "entities": {"balk": {"name": "timber balk", "room": "mill_race"}}}
INDEX = {"character:2": "Emory Vane", "character:1": "Sal Weatherby"}


def _out(*ledgers):
    return {"ledgers": list(ledgers)}


def _row(object_name, source="character:2", items=None):
    return {"object_name": object_name, "source_entity_id": source,
            "item_names": list(items or [])}


class TestAThingTheWorldHoldsPlacesTheBeat:
    def test_a_placed_object_answers_first(self):
        assert _beat_room(_out(_row("timber balk")), SCENE, INDEX) == "mill_race"

    def test_an_object_in_the_scene_outranks_the_actors_room(self):
        """A body can reach into a room it does not stand in; where the
        THING is, is the better answer when the world has one."""
        scene = dict(SCENE, positions=dict(SCENE["positions"],
                                           **{"timber balk": "grist_mill"}))
        assert _beat_room(_out(_row("timber balk")), scene, INDEX) == "grist_mill"


class TestOtherwiseTheBodyThatReachedPlacesIt:
    def test_an_unplaced_thing_falls_back_to_its_actor(self):
        assert _beat_room(_out(_row("brass collar seam")), SCENE, INDEX) \
            == "mill_race"

    def test_a_handle_the_index_does_not_know_is_tried_as_a_name(self):
        assert _beat_room(_out(_row("brass collar seam", source="Emory Vane")),
                          SCENE, INDEX) == "mill_race"

    def test_without_an_index_the_room_is_still_refused_not_guessed(self):
        assert _beat_room(_out(_row("brass collar seam")), SCENE, None) == ""


class TestItRefusesToGuess:
    def test_two_bodies_in_two_rooms_place_nothing(self):
        out = _out(_row("brass collar seam"),
                   _row("brass collar seam", source="character:1"))
        assert _beat_room(out, SCENE, INDEX) == ""

    def test_two_placed_objects_in_two_rooms_place_nothing(self):
        scene = dict(SCENE, positions=dict(
            SCENE["positions"], **{"timber balk": "mill_race",
                                   "hopper": "grist_mill"}))
        assert _beat_room(_out(_row("timber balk"), _row("hopper")),
                          scene, INDEX) == ""

    def test_a_beat_with_no_ledger_places_nothing(self):
        assert _beat_room({}, SCENE, INDEX) == ""
