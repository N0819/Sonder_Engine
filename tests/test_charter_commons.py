"""A place a body may go for its own sake.

`charter_places` is every place the institution has a post or an upkeep at --
that is, where its WORK is. `charter_move.errands` routed off-duty bodies only
there, so a room whose purpose is being in it rather than working at it was
somewhere the simulated population could never go, however social it was.
Leisure circulation existed and was correct; it had nowhere to send anyone.

Measured on chat 98's recorded charter, with the hand-added upkeep the run's
author used as a workaround removed again: 7 work places against 45 rooms, and
every errand at seeds 3, 4 and 5 landed in the same one -- distances were all
tied, so `min((rooms, place))` resolved on room id and the alphabetically
first workroom became the destination policy for the whole crew.

The graph in `_hub_world` is that shape: every room one edge off a single
transit hub, so distance decides nothing.
"""

from __future__ import annotations

from world.charter import (
    charter_places,
    commons_places,
    errands,
    frequented_places,
    normalize_charter,
    reach_map,
    run,
    seed_needs,
    seed_roster,
)


def _hub_world(spokes=6):
    rooms = {"hub": {"name": "hub", "adjacent": []}}
    for index in range(spokes):
        key = f"room_{index}"
        rooms[key] = {"name": key,
                      "adjacent": [{"to": "hub", "barrier": "open_door"}]}
        rooms["hub"]["adjacent"].append({"to": key, "barrier": "open_door"})
    return {"rooms": rooms}


def _hub_charter(folk=12, commons=("room_4", "room_5")):
    """One institution that works in two rooms and berths in a third."""
    charter = normalize_charter({
        "key": "works",
        "scene": _hub_world(),
        "commons": list(commons),
        "upkeeps": {
            "kept": {"place": "room_0", "drift_per_hour": 0.01,
                     "service_per_hour": 0.05, "floor": 0.25,
                     "requires": {"hands": 1}},
        },
        "posts": {
            "watch": {"place": "room_0", "serves": ["kept"],
                      "requires": {"hands": 1}},
            "second": {"place": "room_1", "serves": [],
                       "requires": {"hands": 1}},
        },
        "bodies": {
            f"folk_{index:02d}": {
                "competence": {"hands": 1}, "available": True,
                "place": "room_2", "berth": "room_2"}
            for index in range(folk)
        },
    })
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


class TestTheDestinationSet:
    def test_the_work_and_the_commons_are_different_questions(self):
        charter = _hub_charter()

        assert set(charter_places(charter)) == {"room_0", "room_1"}
        assert commons_places(charter) == ["room_4", "room_5"]
        assert set(frequented_places(charter)) == {
            "room_0", "room_1", "room_4", "room_5"}

    def test_a_market_is_a_place_people_go_without_being_posted(self):
        """The model could already name one and circulation could not use it:
        `economy.markets` carries a place and `charter_places` never read it."""
        charter = normalize_charter({
            "key": "trade",
            "economy": {"goods": {"grain": {"label": "Grain"}},
                        "markets": {"stall": {"place": "room_3",
                                              "holder": "stores"}}},
        })

        assert "room_3" in commons_places(charter)

    def test_commons_survives_normalization_and_drops_blanks(self):
        charter = normalize_charter({"key": "k",
                                     "commons": ["b", "", "a", "a", None]})

        assert charter["commons"] == ["a", "b"]


class TestWhereAnErrandGoes:
    def test_an_off_duty_body_prefers_the_commons_to_a_workplace(self):
        charter = _hub_charter()
        places = frequented_places(charter)
        reach = reach_map(charter["scene"], places, charter["bodies"])

        visits = errands(charter["bodies"], charter["needs"],
                         charter["upkeeps"], {}, places, reach,
                         seed=3, rate=1.0, commons=commons_places(charter))

        assert visits, "nobody circulated at rate 1.0"
        assert set(visits.values()) <= {"room_4", "room_5"}, (
            "an off-duty errand went to a workplace while a commons was the "
            f"same distance away: {visits}")

    def test_equal_distance_does_not_send_everyone_to_one_room(self):
        """The tie-break is not the destination policy."""
        charter = _hub_charter(folk=24, commons=("room_1", "room_3",
                                                 "room_4", "room_5"))
        places = frequented_places(charter)
        reach = reach_map(charter["scene"], places, charter["bodies"])

        visits = errands(charter["bodies"], charter["needs"],
                         charter["upkeeps"], {}, places, reach,
                         seed=3, rate=1.0, commons=commons_places(charter))

        assert len(set(visits.values())) > 1, (
            "every body went to the same room; every distance was tied and "
            f"the tie-break decided the world: {visits}")

    def test_the_nearer_room_still_wins(self):
        """Scattering ties must not become scattering, full stop: a body
        goes to the closest thing it wants, and only a TIE is broken by the
        body rather than by the room's name."""
        scene = _hub_world()
        scene["rooms"]["room_5"]["adjacent"] = [
            {"to": "room_4", "barrier": "open_door"}]
        scene["rooms"]["hub"]["adjacent"] = [
            edge for edge in scene["rooms"]["hub"]["adjacent"]
            if edge["to"] != "room_5"]
        scene["rooms"]["room_4"]["adjacent"].append(
            {"to": "room_5", "barrier": "open_door"})
        charter = _hub_charter(folk=24)
        charter["scene"] = scene
        places = frequented_places(charter)
        reach = reach_map(scene, places, charter["bodies"])

        visits = errands(charter["bodies"], charter["needs"],
                         charter["upkeeps"], {}, places, reach,
                         seed=3, rate=1.0, commons=commons_places(charter))

        assert set(visits.values()) == {"room_4"}, (
            "room_5 is one room further than room_4 and was chosen anyway: "
            f"{visits}")

    def test_a_fed_need_still_outranks_the_commons(self):
        """Circulation answers a need first; the commons is where a body goes
        when nothing is pulling it."""
        charter = _hub_charter()
        key = sorted(charter["bodies"])[0]
        charter["needs"][key]["sustenance"]["fed_by"] = "kept"
        places = frequented_places(charter)
        reach = reach_map(charter["scene"], places, charter["bodies"])

        visits = errands(charter["bodies"], charter["needs"],
                         charter["upkeeps"], {}, places, reach,
                         seed=3, rate=1.0, commons=commons_places(charter))

        assert visits[key] == "room_0"

    def test_an_institution_with_no_commons_still_circulates(self):
        """The widening may not become a requirement: a charter that names
        none keeps the behaviour it had."""
        charter = _hub_charter(commons=())
        places = frequented_places(charter)
        reach = reach_map(charter["scene"], places, charter["bodies"])

        visits = errands(charter["bodies"], charter["needs"],
                         charter["upkeeps"], {}, places, reach,
                         seed=3, rate=1.0, commons=commons_places(charter))

        assert visits
        assert set(visits.values()) <= {"room_0", "room_1"}

    def test_circulation_replays_under_the_same_seed(self):
        """The property movement already had, kept across the widening."""
        charter = _hub_charter(folk=24)
        places = frequented_places(charter)
        reach = reach_map(charter["scene"], places, charter["bodies"])
        args = (charter["bodies"], charter["needs"], charter["upkeeps"], {},
                places, reach)
        commons = commons_places(charter)

        assert errands(*args, seed=7, rate=1.0, commons=commons) == \
            errands(*args, seed=7, rate=1.0, commons=commons)
        assert errands(*args, seed=7, rate=1.0, commons=commons) != \
            errands(*args, seed=8, rate=1.0, commons=commons)


class TestThroughTheRun:
    def test_a_run_puts_bodies_in_rooms_no_post_serves(self):
        """The half that was invisible: a place absent from `reach` cannot be
        an errand destination however it is named, and `run` is what builds
        `reach`."""
        charter = _hub_charter(folk=24)

        after, _ = run(charter, hours=96.0, window=4.0)

        ended = {body["place"] for body in after["bodies"].values()}
        assert ended & {"room_4", "room_5"}, (
            "96 hours of circulation and nobody ever stood in a room the "
            f"institution does not work in: {sorted(ended)}")

    def test_the_quiet_control_is_unmoved_by_a_commons(self):
        """`errand_rate: 0.0` still pins the pre-circulation behaviour: the
        watch bill moves people and nothing else does, commons or no."""
        from world.charter import step

        charter = _hub_charter(folk=24)
        charter["errand_rate"] = 0.0
        posted_ever = set()
        for index in range(24):
            charter, _ = step(charter, hours=4.0, seed=index)
            posted_ever |= set((charter.get("watch") or {}).values())

        moved = {key for key, rooms in (charter.get("travelled") or {}).items()
                 if rooms > 0}
        assert moved <= posted_ever, \
            f"wandered with the rate pinned to zero: {moved - posted_ever}"
        assert not {body["place"] for body in charter["bodies"].values()} \
            & {"room_4", "room_5"}


class TestTheAuthorIsTold:
    """An empty authored field fails silently, which is the failure `CLAUDE.md`
    records for psychology and `registry_warnings` already exists to answer."""

    def test_a_commons_outside_the_frame_is_named(self):
        from world.charter_runtime import registry_warnings

        warnings = registry_warnings(
            {"works": {"key": "works", "commons": ["nowhere"]}},
            scene=_hub_world())

        assert any("nowhere" in warning and "not a room" in warning
                   for warning in warnings)

    def test_an_institution_that_works_everywhere_it_goes_is_named(self):
        from world.charter_runtime import registry_warnings

        state = _hub_charter(commons=())
        warnings = registry_warnings({"works": state}, scene=_hub_world())

        assert any("no commons" in warning for warning in warnings), warnings

    def test_naming_one_settles_it(self):
        from world.charter_runtime import registry_warnings

        state = _hub_charter()
        warnings = registry_warnings({"works": state}, scene=_hub_world())

        assert not any("no commons" in warning for warning in warnings)


class TestTheRoomIdsTravel:
    def test_a_re_keyed_town_re_keys_its_commons(self, temp_db):
        """A list of room ids is as much a place reference as a `place` field.
        Left out of the re-key, a commons points at ids that no longer exist
        and the circulation it was authored for is silently gone again."""
        import time

        from world.charter_runtime import _remap_generated_town

        cid = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Commons remap", "", time.time()))
        # A room the chat already owns, so the namespacing branch fires.
        temp_db.qi(
            "INSERT INTO room_registry(chat_id,room_uid,name,payload) "
            "VALUES(?,?,?,?)", (cid, "room_4", "Room Four", "{}"))

        town = _remap_generated_town(cid, {
            "structure": {"key": "site"},
            "rooms": {"room_4": {"name": "Room Four", "adjacent": []},
                      "room_5": {"name": "Room Five", "adjacent": []}},
            "charters": {"works": {"key": "works", "commons": ["room_4"],
                                   "upkeeps": {}, "posts": {}, "bodies": {}}},
        }, {"items": {}})

        moved = sorted(town["rooms"])
        charter = next(iter(town["charters"].values()))
        assert "room_4" not in moved, "the re-key did not fire"
        assert charter["commons"] and charter["commons"][0] in moved, \
            f"commons still points at a dead id: {charter['commons']}"
