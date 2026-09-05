"""What lights a room, and what a dim room shows.

Two classes, both from the 2026-09-05 play campaign, both about the same
gap between what an author writes and what the engine holds.

THE ESTABLISH DESCRIBES A LIGHT AND MINTS NO SOURCE (PQ1
`PLAY_2026_09_05C_quiet.md`, PR6 `..._rush.md`, PX7 `..._masque.md`). A
scenario opening on "a fire in the grate that is low and wants making up"
produced the anchor `hearth: {"desc": "A stone fireplace with an iron grate
holding dying coals and grey ash"}`, five minted objects, and no fire; all
three rooms came out `dim` and `scene.entities` held no `light_source` of
any kind. A tenement burning down for twenty beats committed
`light_source: []` and `sound_source: []`. A ball "hung with lamps" minted
five entities and not one source. In every case the engine said nothing,
because the only notice it had was scoped to the sky rule and these rooms
were all indoors.

DIM WITHHOLDS DETAIL, NOT CONDUCT (PQ2, `..._quiet.md`). `_LIGHT_SIGHT`
graded `dim` to `shapes`, so in a two-hander whose whole content is what two
people do with their hands, a glove drawn off finger by finger and laid on a
table four feet away reached the other body three times as "Halla Renn
moves, too little of it to make out" -- fifteen of twenty-one beats.

Two smaller ones ride along, because both are a room's light or its fabric
misdescribed to a reader: PM17 (a one-hop look at the room next door
reported as a corridor terminating in darkness) and PR14 (the picture of a
room taken from inside a stairwell).
"""
from __future__ import annotations

from agents import composer
from world.spatial import (
    corridor_sightlines,
    merge_scene_with_diff,
    unsourced_light_notices,
    unsourced_light_rooms,
    UNSOURCED_LIGHT_NOTICE_ROOMS,
    visual_level_between,
)


# ---------------------------------------------------------------------------
# The parlour with the fire nobody minted
# ---------------------------------------------------------------------------

def _parlour(light="dim", entities=None, positions=None):
    """PQ1's shape: an indoor room whose light is described in an ANCHOR."""
    return {
        "rooms": {"parlour": {
            "name": "The Parlour", "desc": "Low chairs and a cold draught.",
            "exposure": "enclosed", "size": "small", "adjacent": [],
            "light": light,
            "anchors": {"hearth": {
                "desc": "A stone fireplace with an iron grate holding dying "
                        "coals and grey ash", "dir": "w"},
                "table": {"desc": "a low table", "dir": "e"}},
        }},
        "entities": dict(entities or {}),
        "positions": dict(positions or {"Halla": "parlour", "Toft": "parlour"}),
    }


class TestARoomThatSaysItIsLitAndHoldsNothingThatMakesLight:
    def test_the_parlour_is_named_and_the_source_is_asked_for(self):
        [notice] = unsourced_light_notices(_parlour())
        assert "The Parlour" in notice
        assert "`light: dim`" in notice
        assert "light_source" in notice
        # The class, in the notice itself: an anchor is a place, an entity is
        # a thing the story can change.
        assert "anchor" in notice

    def test_the_word_still_stands_because_this_never_darkens_a_room(self):
        """The notice ASKS; it does not overrule. A room reads exactly what
        it read before, so nobody is put in the dark by a missing entity."""
        scene = _parlour()
        assert merge_scene_with_diff(scene, {})["rooms"]["parlour"]["light"] \
            == "dim"
        from world.spatial import room_light
        assert room_light(scene, "parlour") == "dim"

    def test_minting_the_fire_answers_it(self):
        """The whole point: an entity with `light_source` standing in the
        room is the account the room was missing, and the notice stops."""
        scene = _parlour(
            entities={"hearth_fire": {
                "name": "the fire in the grate", "kind": "fire",
                "light_source": "dim", "light_radius": "room",
                "sound_source": "faint", "state": {"lit": True}}},
            positions={"Halla": "parlour", "Toft": "parlour",
                       "hearth_fire": "parlour"})
        assert unsourced_light_notices(scene) == []

    def test_a_fire_that_has_gone_out_is_still_an_account(self):
        """PA3 from this end: the source is written, so whether it burns is
        the story's business and nothing is asked of the Director."""
        scene = _parlour(
            entities={"hearth_fire": {
                "name": "the fire in the grate", "light_source": "dim",
                "light_radius": "room", "state": {"lit": False}}},
            positions={"Halla": "parlour", "hearth_fire": "parlour"})
        assert unsourced_light_notices(scene) == []

    def test_a_dark_room_claims_no_light_so_nothing_is_asked(self):
        assert unsourced_light_notices(_parlour(light="dark")) == []

    def test_a_room_that_declares_nothing_declares_nothing(self):
        """The fail-open at the top of the module is not a claim."""
        scene = _parlour()
        scene["rooms"]["parlour"].pop("light")
        assert unsourced_light_notices(scene) == []

    def test_the_notice_is_capped_and_counts_the_rest(self):
        """PR6's tenement was ten rooms wide and burned for twenty beats;
        an uncapped notice is a paragraph per beat for as long as the
        Director declines to mint a lamp."""
        scene = _parlour()
        rooms = scene["rooms"]
        for n in range(6):
            rooms["room_%d" % n] = {"name": "Room %d" % n, "adjacent": [],
                                    "exposure": "enclosed", "light": "lit"}
        notices = unsourced_light_notices(scene)
        assert len(notices) == UNSOURCED_LIGHT_NOTICE_ROOMS + 1
        assert notices[-1].startswith("4 more rooms")
        # The room somebody is standing in is named first: a room's light
        # matters this beat where a body is in it.
        assert "The Parlour" in notices[0]

    def test_the_rooms_query_says_what_the_word_outran(self):
        [(room_id, declared, otherwise)] = unsourced_light_rooms(_parlour())
        assert (room_id, declared, otherwise) == ("parlour", "dim", "dark")


# ---------------------------------------------------------------------------
# What a dim room shows
# ---------------------------------------------------------------------------

def _dim_two_hander():
    """PQ2's shape: two bodies at different anchors of one small dim room."""
    return {
        "rooms": {"parlour": {
            "name": "The Parlour", "desc": "Low chairs.", "size": "small",
            "exposure": "enclosed", "light": "dim", "adjacent": [],
            "anchors": {"table": {"desc": "a low table", "dir": "e"},
                        "chair": {"desc": "a wing chair", "dir": "w"}},
        }},
        "entities": {},
        "positions": {"Halla": "parlour", "Toft": "parlour"},
        "stations": {"Halla": {"at": "table"}, "Toft": {"at": "chair"}},
    }


class TestDimWithholdsDetailNotConduct:
    def test_the_light_grades_to_conduct(self):
        sc = _dim_two_hander()
        assert visual_level_between(sc, "Toft", "Halla") == "conduct"
        assert visual_level_between(sc, "Halla", "Toft") == "conduct"

    def test_the_act_arrives_whole_instead_of_a_body_moving(self):
        """The measured failure: Halla pulled a glove off finger by finger
        and laid it on the table four feet from her brother, and he received
        "Halla Renn moves, too little of it to make out" three times."""
        from agents.perception import _sight_detail
        from world.spatial import spatial_rel

        sc = _dim_two_hander()
        rel = spatial_rel(sc, "parlour", "parlour")
        sight = _sight_detail(sc, "Toft", "Halla", rel)
        event = {"event_id": "e1", "actor": "Halla", "targets": [],
                 "observable": "pulls a glove off finger by finger and lays "
                               "it on the low table"}
        percept = composer.act_percept(
            sc, event, "Toft", "Halla", rel, display="Halla",
            can_see=True, surface=event["observable"], sight=sight)
        assert percept is not None
        assert percept.fidelity != "shapes"
        assert "glove" in percept.data["surface"]

    def test_and_the_detail_is_still_withheld(self):
        """The other half of the same rule, and the reason a whole rung was
        added rather than `dim` being graded `full`: an unrecognised body in
        a dim room gets no appearance descriptor and no name."""
        sc = _dim_two_hander()
        bodies = [{"name": "Halla", "appearance": "a tall woman with a "
                                                  "scar across one cheek",
                   "aliases": [], "role": ""}]
        display = composer.observer_display_map(sc, "Toft", bodies,
                                                {"Toft": []})
        assert "Halla" not in display["Halla"]
        assert "scar" not in display["Halla"].casefold()

    def test_dark_is_untouched(self):
        sc = _dim_two_hander()
        sc["rooms"]["parlour"]["light"] = "dark"
        assert visual_level_between(sc, "Toft", "Halla") == "none"


# ---------------------------------------------------------------------------
# The room next door is not a corridor
# ---------------------------------------------------------------------------

class TestAOneHopLookIsNotACorridor:
    def _two_rooms(self, light="dim"):
        """PM17's shape: a tiny lit alcove one open door east of the hall."""
        return {
            "rooms": {
                "hall": {"name": "Hall", "light": "lit", "size": "medium",
                         "adjacent": [{"to": "clerks_room",
                                       "barrier": "open_door", "dir": "e"}]},
                "clerks_room": {"name": "Clerks' Room", "light": light,
                                "size": "tiny",
                                "adjacent": [{"to": "hall",
                                              "barrier": "open_door",
                                              "dir": "w"}]},
            },
            "positions": {"Clerk": "clerks_room"},
        }

    def test_the_alcove_next_door_is_not_reported_as_a_passage(self):
        """Sent to five minds sixty-two times as `{"along": [], "dir": "e",
        "distance": 1, "terminus": "darkness", "vagueness": "just ahead"}`
        while the same payload's view called the room "Dimly lit from the
        hall doorway"."""
        assert corridor_sightlines(self._two_rooms(), "hall") == []

    def test_nor_when_the_room_next_door_is_a_dead_end_in_full_light(self):
        """The suppression is about the LINE, not about the light: a line
        that stops at the neighbour is not a passage whichever thing stopped
        it, and what the neighbour is like is a room fact the room channels
        already carry."""
        assert corridor_sightlines(self._two_rooms(light="lit"), "hall") == []

    def test_a_line_that_gets_past_the_neighbour_is_still_reported(self):
        sc = self._two_rooms(light="lit")
        sc["rooms"]["clerks_room"]["adjacent"].append(
            {"to": "strong_room", "barrier": "open", "dir": "e"})
        sc["rooms"]["strong_room"] = {"name": "Strong Room", "light": "lit",
                                      "adjacent": []}
        [line] = corridor_sightlines(sc, "hall")
        assert line["dir"] == "e" and line["distance"] == 2
        assert line["terminus"] == "dead_end"


# ---------------------------------------------------------------------------
# A camera does not stand in a stairwell
# ---------------------------------------------------------------------------

class TestThePictureIsNotTakenFromInsideAStair:
    def _landing(self, extra_edges=()):
        """PR14's shape: a landing whose north way is the stair down."""
        return {
            "rooms": {"fourth_landing": {
                "name": "Fourth Landing", "desc": "Bare boards.",
                "size": "small", "light": "dark",
                "adjacent": [{"to": "third_landing", "barrier": "open",
                              "dir": "n", "vertical": "down",
                              "name": "the stair down"},
                             *extra_edges],
            }, "third_landing": {"name": "Third Landing", "adjacent": []},
                "flat_tomo": {"name": "Tomo's Flat", "adjacent": []}},
            "positions": {},
        }

    def test_a_vertical_way_is_no_place_to_stand_and_look_level(self):
        from dressing.backdrops import room_brief

        brief = room_brief(self._landing(), "fourth_landing")
        assert "camera" not in brief

    def test_a_level_way_in_the_same_room_is_taken_instead(self):
        from dressing.backdrops import room_brief

        brief = room_brief(self._landing(
            [{"to": "flat_tomo", "barrier": "open_door", "dir": "e"}]),
            "fourth_landing")
        assert brief["camera"]["from"] == "the east doorway"
        assert brief["camera"]["looking"] == "west"
