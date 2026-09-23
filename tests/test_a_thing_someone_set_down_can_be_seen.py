"""A thing standing in a room reaches the eyes of the people in it.

THE CASE THAT FOUND IT (two_lives v13, 2026-09-20, chat frame 2). Sal
Weatherby laid a copper coin on the taproom counter to pay for an ale. The
commit was correct in every particular: `stations: {copper_coin: {at:
oak_bar_counter}}`, `contained` empty, the coin positioned in her own room.
The coin then appeared in **0 of her 24 composed views**, act and outcome
alike. Two beats later her view named the HOST's leather coin pouch and not
her own coin, so she drew a second coin from her pocket and paid again.

Read as fiction it looks like a stupid character. It was not: there was no
sight path from `scene.entities` to any view in the engine.
`feature_visibility` answers for "every ANCHOR of the observer's room", and
perception's only walk over scene entities on the view path is the scent loop,
gated on `entity.scent`. A thing reached a mind only through a channel that
owned it for some other reason -- attire, a pose, a contact, a smell, or being
authored furniture. The mug she drank from rendered, as part of her own pose.
Nothing in the engine ever said "that is lying there".

`composer.room_content_percepts` was already the home for exactly this -- its
docstring names a crowd, a courier and a posted notice -- and the fourth
member of that family was missing.
"""

import pytest

from agents import composer, perception


COUNTER = "a thick oak counter stained dark by spilled ale"


def _taproom(**scene):
    """Sal at the bar, a coin on the counter, in a room with real geometry."""
    base = {
        "rooms": {
            "taproom": {
                "name": "Wheel and Bushel Taproom",
                "cells": [[0, 0], [1, 0], [2, 0], [0, 1], [1, 1], [2, 1]],
                "anchors": {"oak_bar_counter": {"desc": COUNTER, "cell": [1, 0]}},
                "adjacent": [],
                "light": "lit",
            },
        },
        "positions": {"Sal Weatherby": "taproom", "copper_coin": "taproom"},
        "stations": {
            "Sal Weatherby": {"at": "oak_bar_counter", "near": []},
            "copper_coin": {"at": "oak_bar_counter", "near": []},
        },
        "entities": {
            "copper_coin": {"name": "copper coin", "kind": "coin",
                            "description": "A flat copper coin.",
                            "portable": True},
        },
        "contained": {},
        "contacts": [],
    }
    base.update(scene)
    return base


def _things(scene, observer="Sal Weatherby", room="taproom", **kw):
    return perception._visible_things(scene, observer, room, **kw)


def _said(rows):
    return " ".join(row["what"] for row in rows)


class TestTheCoinOnTheCounter:
    def test_a_thing_set_down_in_your_own_room_reaches_your_eyes(self):
        rows = _things(_taproom())
        assert [row["uid"] for row in rows] == ["copper_coin"]
        assert "copper coin" in _said(rows)

    def test_it_says_where_the_thing_lies(self):
        """The anchor's own authored description, because that is the whole of
        what the observer has about where it is."""
        assert COUNTER in _said(_things(_taproom()))

    def test_the_percept_family_carries_it(self):
        """End of the seam: the rows have to survive into a percept, or this
        is another field nothing reads."""
        percepts = composer.room_content_percepts(_things(_taproom()))
        assert len(percepts) == 1
        assert percepts[0].kind == "ambient"
        assert percepts[0].channel == "sight"
        assert "copper coin" in percepts[0].data["desc"]

    def test_moving_it_is_news_and_leaving_it_is_furniture(self):
        """`room_content_percepts` dedupes on state, never on the sentence.
        A thing that sits is furniture a delta view omits; a thing that moves
        re-renders."""
        still = composer.room_content_percepts(_things(_taproom()))[0]
        again = composer.room_content_percepts(_things(_taproom()))[0]
        assert still.dedupe_key == again.dedupe_key
        moved = _taproom()
        moved["stations"]["copper_coin"] = {"at": "hearth", "near": []}
        moved["rooms"]["taproom"]["anchors"]["hearth"] = {
            "desc": "a wide soot-blacked hearth", "cell": [2, 1]}
        assert composer.room_content_percepts(_things(moved))[0].dedupe_key \
            != still.dedupe_key


class TestEveryRuleSubtracts:
    def test_a_thing_in_another_room_is_not_here(self):
        scene = _taproom()
        scene["positions"]["copper_coin"] = "kitchen"
        scene["rooms"]["kitchen"] = {"name": "Kitchen", "adjacent": []}
        assert _things(scene) == []

    def test_a_body_is_not_a_thing(self):
        """Presence and pose own every body. A registered person can also
        stand in `entities` under another key, so the test is the engine's own
        subject identity, never a name comparison."""
        scene = _taproom()
        scene["entities"]["Sal Weatherby"] = {"name": "Sal Weatherby"}
        rows = _things(scene, bodies=["Sal Weatherby"])
        assert [row["uid"] for row in rows] == ["copper_coin"]

    def test_a_pocketed_thing_stays_pocketed(self):
        """The firewall half. Read through `hiding_holders_of`, so containment
        keeps its one owner and a concealed thing is not published to the room
        by a second path."""
        scene = _taproom()
        scene["stations"].pop("copper_coin")
        # `in`, which is the ledger's own key -- `holder` reads as no record at
        # all and the thing walks straight through the guard. Written out
        # because a fixture in the wrong shape is how this test first passed
        # against a guard that was never consulted.
        scene["contained"] = {"copper_coin": {"in": "Sal Weatherby",
                                              "mode": "pocket"}}
        assert _things(scene) == []

    def test_authored_furniture_is_the_features_sentence_s(self):
        """Two representations of one object can only disagree, and the
        observer would be told about it twice."""
        scene = _taproom()
        scene["entities"]["oak_bar_counter"] = {"name": "oak bar counter",
                                                "kind": "fixture"}
        scene["positions"]["oak_bar_counter"] = "taproom"
        assert [row["uid"] for row in _things(scene)] == ["copper_coin"]

    def test_a_thing_at_an_anchor_you_cannot_see_is_not_admitted(self):
        """The rule that makes this small: sight is the ANCHOR's answer, which
        the cone, the line, the occluder and the light have already decided.
        This adds no new judgment about what an eye reaches, and it inherits
        `feature_visibility`'s carve-outs rather than re-deciding them."""
        scene = _taproom()
        scene["rooms"]["taproom"]["anchors"]["far_shelf"] = {
            "desc": "a high shelf of pewter", "cell": [0, 1], "opaque": True}
        scene["rooms"]["taproom"]["light"] = "dark"
        scene["stations"]["copper_coin"] = {"at": "far_shelf", "near": []}
        assert _things(scene) == []

    def test_what_your_hands_are_on_you_know_in_the_dark(self):
        """The complement, and it is `feature_visibility`'s carve-out rather
        than this seam's: the anchor a body is STATIONED AT is exempt from the
        light gate, because it has its hands on it. So a coin on the counter
        Sal is leaning against survives the lamps going out, and this pass
        neither adds that rule nor argues with it."""
        scene = _taproom()
        scene["rooms"]["taproom"]["light"] = "dark"
        assert [row["uid"] for row in _things(scene)] == ["copper_coin"]

    def test_an_unplaced_thing_is_named_without_claiming_a_distance(self):
        """A room can hold a thing without placing it. Then the thing is named
        and no distance is claimed -- the subtraction `_feature_items` already
        makes for furniture seen through a doorway, because the distance
        vocabulary is measured within one room."""
        scene = _taproom()
        scene["stations"].pop("copper_coin")
        rows = _things(scene)
        assert [row["uid"] for row in rows] == ["copper_coin"]
        said = _said(rows)
        assert "copper coin" in said and COUNTER not in said

    def test_an_unplaced_thing_in_the_dark_is_not_seen(self):
        """The anchor carve-outs in `feature_visibility` are for a thing a body
        has its hands on and for a doorway. An unplaced object is neither, so
        it needs light like anything else."""
        scene = _taproom()
        scene["stations"].pop("copper_coin")
        scene["rooms"]["taproom"]["light"] = "dark"
        assert _things(scene) == []

    def test_a_nameless_record_says_nothing(self):
        scene = _taproom()
        scene["entities"]["copper_coin"] = {"kind": "coin"}
        assert _things(scene) == []

    def test_no_room_is_no_answer(self):
        assert _things(_taproom(), room="") == []


class TestTheWordingIsThePacks:
    @pytest.mark.parametrize("language", ["en", "ja"])
    def test_both_packs_can_say_it(self, language):
        """A percept kind that renders in one language and not the other is
        how `communication` was dropped from every Japanese view with no error
        anywhere. `ambient` already renders in both; the clause has to too."""
        from language_runtime import installed_language_packs
        templates = installed_language_packs()[language].card(
            "compositor")["templates"]
        assert templates["thing_placed"] and templates["thing_here"]
        assert "{desc}" in templates["thing_placed"]
        assert "{place}" in templates["thing_placed"]
        assert "{desc}" in templates["thing_here"]


class TestAThingInSomebodysHands:
    """Playerless Aldermill round 7 (2026-09-23): "There is the tallow tub
    here. There is the horn paddle here." in seventeen of Emory's views, while
    the commit held both in his grip. Held in the open, the tub was not
    concealed, so the concealment rule let it through as a thing lying on the
    floor."""

    def _in_hand(self, mode="held", holder="Sal Weatherby"):
        scene = _taproom(stations={"Sal Weatherby": {"at": "oak_bar_counter", "near": []}},
                         contained={"copper_coin": {"in": holder, "mode": mode}})
        scene["positions"]["Bram Toll"] = "taproom"
        return scene

    def test_the_bearer_is_told_it_is_theirs(self):
        said = _said(_things(self._in_hand()))
        assert said == "You are holding the copper coin."
        assert _said(_things(self._in_hand("carried"))) == \
            "You are carrying the copper coin."

    def test_nobody_else_sees_it_lying_here(self):
        assert _things(self._in_hand(), observer="Bram Toll") == []

    def test_a_worn_thing_is_the_wardrobes(self):
        assert _things(self._in_hand("worn")) == []

    def test_a_thing_on_a_cart_still_lies_where_the_cart_stands(self):
        scene = self._in_hand(holder="hand cart")
        scene["positions"]["hand cart"] = "taproom"
        scene["entities"]["hand cart"] = {"name": "hand cart", "kind": "cart",
                                          "description": "A two-wheeled cart."}
        assert "There is the copper coin here." in _said(
            _things(scene, observer="Bram Toll"))
