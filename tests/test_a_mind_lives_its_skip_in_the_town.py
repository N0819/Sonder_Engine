"""A registered mind lives a declared time skip inside the town's charter.

`world/charter_skip.live_in_charter`, `DESIGN_THE_CAST_ACROSS_A_SKIP.md`
§ 4.4 (a). The owner, 2026-10-21: "handing off major characters to charter,
either their own or a towns having it". The probe that motivated it (F16, the
lighthouse story): two days passed, nobody moved, and the keeper's only memory
of them was the storm through the walls.

What these pin, each the shape of one of the design's rules:
  * no charter, or no place of the town in the mind's day: None, and the
    skip stage's own executor runs it;
  * the mind's own day is walked through the town -- the watch, the errands
    and the homecomings yield wherever it speaks, and the town's needs-driven
    day fills its silences;
  * the residents it stood among reach its record under the name IT knows
    them by, a stranger's label for anybody it has not met;
  * the charter keeps nothing of the mind: no `minds` row, no temporary
    body, no stored change at all; only the lifted body is lifted;
  * the town's own advance after the commit lives the span once, and keeps
    its hands off the mind's body -- including one reserved for the mind by
    the engine's own seat token and never bound.
"""

from __future__ import annotations

import copy
import json
import time
import uuid

import pytest

from charter_worlds import small_town
from story.character_schema import default_character_data
from world.charter_model import body_of_an_authored_mind, normalize_charter
from world.charter_needs import seed_needs
from world.charter_roster import seed_roster
from world.charter_run import step
from world.charter_runtime import (advance_snapshot, registry_for,
                                   registry_for_update, registry_revision,
                                   save_registry)
from world.charter_skip import (SKIP_WINDOW_HOURS, TEMPORARY_BODY_PREFIX,
                                skip_windows, live_in_charter)

H = 3600.0
NAMES = {"smith": "Wat Hollin", "stallholder": "Ada Fenn",
         "tapster": "Tam Reddy"}
LOG_FIELDS = {"from_s", "until_s", "room", "away", "where_text", "doing",
              "asleep", "seen", "weather", "outcome", "reason"}
SPAN_DAY = {"from_s": 0.0, "until_s": 24 * H}


def _town(**over):
    town = small_town()
    for key, body in town["bodies"].items():
        body["name"] = NAMES.get(key, "Folk %s" % key.split("_")[-1])
    town = normalize_charter(dict(town, **over))
    town["roster"] = seed_roster(town["bodies"])
    town["needs"] = seed_needs(town["bodies"])
    return town


def _stretch(start_h, end_h, room, doing, *, asleep=False, away=None,
             with_=(), uses=()):
    return {"from_s": start_h * H, "until_s": end_h * H, "room": room,
            "away": away, "where_text": room or away or "", "doing": doing,
            "asleep": asleep, "with": list(with_), "why": "a reason",
            "uses": list(uses)}


def _day():
    return [_stretch(0, 4, "smithy", "Watch the smith at the anvil"),
            _stretch(4, 14, "tavern", "Drink by the fire"),
            _stretch(14, 24, "house_a", "Sleep", asleep=True)]


def _cast(temp_db, cid, name):
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(default_character_data(name)), "{}", time.time(),
         "char_%s_%s" % (name.casefold(), uuid.uuid4().hex[:8])))
    temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
               "VALUES(?,?,?,?)", (cid, char_id, "active", "{}"))
    return char_id


def _story(temp_db, town=None, *, minds=("Mara",), at="square", known=None,
           last_elapsed=0.0, rooms=None):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Skip", "", time.time()))
    ids = {name: _cast(temp_db, cid, name) for name in minds}
    scene = {"rooms": copy.deepcopy(rooms or small_town()["scene"]["rooms"]),
             "positions": {name: at for name in minds}}
    temp_db.wset(cid, "scene", scene)
    temp_db.wset(cid, "simulation_clock", {
        "elapsed_seconds": 0.0, "anchor_hour": 8.0, "day_length_hours": 24.0})
    if known:
        temp_db.wset(cid, "known", known)
    if town is not False:
        town = town if town is not None else _town()
        if callable(town):
            town = town(ids)
        save_registry(cid, {"version": 1, "items": {"small_town": {
            "state": town, "last_elapsed_seconds": last_elapsed}}})
    return cid, ids, scene


def _bound_to(body_key, char_id, name):
    def build(_ids):
        town = _town()
        town["bindings"] = {body_key: {"char_id": char_id(_ids),
                                       "name": name}}
        return town
    return build


# ------------------------------------------------------------------ None

class TestWhenNoCharterHoldsIt:
    def test_a_story_without_a_charter_is_none(self, temp_db):
        cid, _ids, scene = _story(temp_db, town=False)
        assert live_in_charter(cid, scene, "Mara", _day(), SPAN_DAY) is None

    def test_a_bodiless_mind_whose_day_names_no_town_place_is_none(
            self, temp_db):
        # `north_2` is a street: no post, no commons, nobody's berth, and
        # nobody of the town stands in it. Nobody there to live among, so
        # the stage's own executor carries this day.
        cid, _ids, scene = _story(temp_db)
        day = [_stretch(0, 24, "north_2", "Wait in the street")]
        assert live_in_charter(cid, scene, "Mara", day, SPAN_DAY) is None

    def test_a_charter_already_past_the_span_is_none(self, temp_db):
        cid, _ids, scene = _story(temp_db, last_elapsed=2 * H)
        assert live_in_charter(cid, scene, "Mara", _day(), SPAN_DAY) is None


# ------------------------------------------------ the day, walked in town

class TestTheItineraryIsWalkedInsideTheTown:
    def test_a_cast_member_lives_its_day_among_the_residents(self, temp_db):
        cid, _ids, scene = _story(temp_db, known={"Mara": ["Tam Reddy"]})
        log, far_end = live_in_charter(cid, scene, "Mara", _day(), SPAN_DAY)
        assert all(set(row) == LOG_FIELDS for row in log)
        assert [row["room"] for row in log] == ["smithy", "tavern", "house_a"]
        forge = log[0]["seen"]
        # The smith stood the forge's post while she watched -- and she has
        # never met him, so he reaches her record as a stranger, never by
        # name.
        assert {"at work here"} <= {row["doing"] for row in forge}
        assert not any("Hollin" in row["who"] or "Wat" in row["who"]
                       for row in forge)
        # The tapster she knows is named in the tavern.
        assert "Tam Reddy" in {row["who"] for row in log[1]["seen"]}
        # Nobody's reason is in anybody's doing; a sleep sees nobody.
        assert log[2]["asleep"] and log[2]["seen"] == []
        assert far_end["room"] == "house_a" and far_end["asleep"]
        # Travel eats the start of the stretch it is travel to.
        assert 14 * H < far_end["asleep_since_s"] < 15 * H

    def test_a_stretch_it_cannot_reach_fails_and_the_body_stays(
            self, temp_db):
        rooms = copy.deepcopy(small_town()["scene"]["rooms"])
        for x, y in (("south_0", "smithy"), ("smithy", "south_0")):
            for edge in rooms[x]["adjacent"]:
                if edge["to"] == y:
                    edge["barrier"] = "locked_door"
        town = _town(scene={"rooms": copy.deepcopy(rooms)})
        cid, _ids, scene = _story(temp_db, town=town, rooms=rooms)
        day = [_stretch(0, 24, "smithy", "Watch the smith at the anvil")]
        log, far_end = live_in_charter(cid, scene, "Mara", day, SPAN_DAY)
        assert log[0]["outcome"] == "failed"
        assert log[0]["reason"] == "shut_way"
        assert far_end["room"] == "square"

    def test_a_sleep_it_cannot_reach_its_bed_for_is_slept_where_it_lies(
            self, temp_db):
        rooms = copy.deepcopy(small_town()["scene"]["rooms"])
        for x, y in (("north_2", "house_a"), ("house_a", "north_2")):
            for edge in rooms[x]["adjacent"]:
                if edge["to"] == y:
                    edge["barrier"] = "locked_door"
        town = _town(scene={"rooms": copy.deepcopy(rooms)})
        cid, _ids, scene = _story(temp_db, town=town, rooms=rooms)
        day = [_stretch(0, 14, "tavern", "Drink by the fire"),
               _stretch(14, 24, "house_a", "Sleep", asleep=True)]
        log, far_end = live_in_charter(cid, scene, "Mara", day, SPAN_DAY)
        assert log[1]["outcome"] == "failed"
        assert log[1]["reason"] == "shut_way"
        assert far_end["asleep"] and far_end["room"] == "tavern"
        assert far_end["asleep_since_s"] == 14 * H

    def test_the_towns_day_fills_a_silence_in_the_minds(self, temp_db):
        cid, _ids, scene = _story(temp_db)
        day = [_stretch(0, 4, "smithy", "Watch the smith at the anvil"),
               _stretch(14, 24, "house_a", "Sleep", asleep=True)]
        log, _far = live_in_charter(cid, scene, "Mara", day, SPAN_DAY)
        assert [(row["from_s"], row["until_s"]) for row in log] == [
            (0.0, 4 * H), (4 * H, 14 * H), (14 * H, 24 * H)]
        silence = log[1]
        assert silence["outcome"] == "done" and silence["doing"]
        # The town ran the body through the afternoon its own day left
        # empty: out of the smithy, home or out among people.
        assert silence["room"] in scene["rooms"]
        assert silence["room"] != "smithy"

    def test_two_minds_asked_about_one_skip_meet_one_town(self, temp_db):
        # Both spend the day in the tavern, where who comes and goes is the
        # town's seeded errands; their days differ after. One town: the same
        # people stood in that room for both of them. (What those people
        # said to each other may differ -- each mind's own presence is
        # something the town talks about, and each is run alone.)
        town = _town(errand_rate=0.15)
        cid, _ids, scene = _story(temp_db, town=town, minds=("Mara", "Bryn"))
        # One stretch per window of the town's own grid, so each record row
        # is one window's company.
        edges = [edge / H for edge in skip_windows(0.0, 24 * H, (8.0, 24.0))
                 if edge <= 14 * H]
        tavern = [(a, b) for a, b in zip(edges, edges[1:])]
        day_a = [_stretch(a, b, "tavern", "Sell ribbons by the fire")
                 for a, b in tavern] + [
                     _stretch(14, 24, "house_a", "Sleep", asleep=True)]
        day_b = [_stretch(a, b, "tavern", "Wait for the carrier")
                 for a, b in tavern] + [
                     _stretch(14, 24, "market", "Mind the stall")]
        log_a, _ = live_in_charter(cid, scene, "Mara", day_a, SPAN_DAY)
        log_b, _ = live_in_charter(cid, scene, "Bryn", day_b, SPAN_DAY)
        rows_a = [{row["who"] for row in entry["seen"]}
                  for entry in log_a[:len(tavern)]]
        rows_b = [{row["who"] for row in entry["seen"]}
                  for entry in log_b[:len(tavern)]]
        assert sum(len(who) for who in rows_a) >= len(tavern), \
            "the tavern was nearly empty all day"
        assert rows_a == rows_b


class TestTheGridIsTheTownsNotTheMinds:
    def test_every_part_of_the_day_starts_a_window_and_none_is_long(self):
        # Anchored at 08:00: the day's parts begin 11:00, 13:30, 18:00,
        # 19:30, 22:00, 04:30, 06:00 and 07:00 of the story's own clock.
        edges = skip_windows(0.0, 24 * H, (8.0, 24.0))
        for hour in (3.0, 5.5, 10.0, 11.5, 14.0, 20.5, 22.0, 23.0):
            assert round(hour * H, 6) in edges
        gaps = [b - a for a, b in zip(edges, edges[1:])]
        assert max(gaps) <= SKIP_WINDOW_HOURS * H + 1e-6
        assert edges[0] == 0.0 and edges[-1] == 24 * H

    def test_a_span_that_runs_on_keeps_every_window_but_its_last(self):
        # The town's own advance after the commit covers the skip and the
        # beat's own few seconds after it. Ending inside the night (a part
        # of the day longer than one window), both cuts must agree on every
        # window but the one the span ends in.
        skip = skip_windows(0.0, 19 * H, (8.0, 24.0))
        beat = skip_windows(0.0, 19 * H + 30.0, (8.0, 24.0))
        assert skip[:-1] == beat[:-1]
        assert skip[-1] == 19 * H and beat[-1] == 19 * H + 30.0


# ------------------------------------------------- the planners yield

class TestThePlannersYield:
    def _bound(self, key="smith"):
        town = _town()
        town["bindings"] = {key: {"char_id": 7, "name": NAMES.get(
            key, "Folk")}}
        return town

    def test_where_its_day_is_silent_the_watch_still_posts_it(self):
        after, _ = step(self._bound(), hours=4.0, seed=3,
                        simulate_bound={"smith"})
        assert after["watch"].get("smith_shift") == "smith"
        assert after["bodies"]["smith"]["place"] == "smithy"

    def test_where_its_day_speaks_the_watch_yields(self):
        after, _ = step(self._bound(), hours=4.0, seed=3,
                        simulate_bound={"smith"},
                        itinerary={"smith": {"room": "tavern",
                                             "asleep": False}})
        assert "smith" not in after["watch"].values()
        assert after["bodies"]["smith"]["place"] == "tavern"

    def test_where_its_day_speaks_the_errands_and_homecomings_yield(self):
        town = self._bound("folk_0")
        town["bodies"]["folk_0"]["place"] = "market"
        left, _ = step(town, hours=4.0, seed=3, simulate_bound={"folk_0"})
        assert left["bodies"]["folk_0"]["place"] != "market"
        held, _ = step(town, hours=4.0, seed=3, simulate_bound={"folk_0"},
                       itinerary={"folk_0": {"room": "market",
                                             "asleep": False}})
        assert held["bodies"]["folk_0"]["place"] == "market"
        # Not sent home and walked back: never sent anywhere.
        assert held["travelled"].get("folk_0", 0) == 0

    def test_a_long_way_it_chose_is_walked_past_the_planners_reach(self):
        # Eleven doors down a corridor: further than the planner's
        # `REACH_LIMIT` (8) would post anybody. A destination the body
        # declared is the body's to reach.
        rooms = {}
        keys = ["r%d" % i for i in range(12)]
        for i, key in enumerate(keys):
            edges = []
            if i:
                edges.append({"to": keys[i - 1], "barrier": "open_door"})
            if i + 1 < len(keys):
                edges.append({"to": keys[i + 1], "barrier": "open_door"})
            rooms[key] = {"name": key, "adjacent": edges}
        town = normalize_charter({
            "key": "line", "scene": {"rooms": rooms}, "upkeeps": {},
            "posts": {}, "bodies": {"walker": {"place": "r0", "berth": "r0",
                                               "available": True}},
            "bindings": {"walker": {"char_id": 9, "name": "Walker"}}})
        after, _ = step(town, hours=4.0, seed=1, simulate_bound={"walker"},
                        itinerary={"walker": {"room": "r11"}})
        assert after["bodies"]["walker"]["place"] == "r11"


# --------------------------------------- the charter keeps nothing of it

class TestNothingOfTheMindStaysInTheCharter:
    def test_a_lifted_body_holds_no_head_and_acts_on_nobody(self):
        town = _town(active_places=["tavern", "square"])
        town["bindings"] = {"smith": {"char_id": 7, "name": "Wat Hollin"}}
        after = town
        for index in range(8):
            after, _ = step(after, hours=2.0, seed=index,
                            simulate_bound={"smith"},
                            itinerary={"smith": {"room": "tavern"}})
        assert after["bodies"]["smith"]["place"] == "tavern"
        assert "smith" in after["needs"]          # its body lived the span
        for store in ("minds", "feel", "judgments", "marks", "ties",
                      "heard_blame"):
            assert "smith" not in (after.get(store) or {}), store
        assert not any(str(row.get("actor")) == "smith"
                       for row in after.get("window_acts") or ())

    def test_only_the_lifted_body_is_lifted(self):
        town = _town()
        town["bindings"] = {"smith": {"char_id": 7, "name": "Wat Hollin"},
                            "tapster": {"char_id": 8, "name": "Tam Reddy"}}
        after, _ = step(town, hours=4.0, seed=3, simulate_bound={"smith"},
                        itinerary={"smith": {"room": "tavern"}})
        assert after["bodies"]["smith"]["place"] == "tavern"
        assert after["bodies"]["tapster"]["place"] \
            == town["bodies"]["tapster"]["place"]
        assert "tapster" not in after["walked"]
        assert "tapster" not in after["needs"]

    def test_the_skip_writes_nothing_and_enrols_nobody(self, temp_db):
        cid, _ids, scene = _story(temp_db)
        stored = json.dumps(temp_db.wget(cid, "charters", {}), sort_keys=True)
        revision = registry_revision(registry_for(cid))
        assert live_in_charter(cid, scene, "Mara", _day(), SPAN_DAY)
        assert json.dumps(temp_db.wget(cid, "charters", {}),
                          sort_keys=True) == stored
        registry = registry_for(cid)
        assert registry_revision(registry) == revision
        for item in registry["items"].values():
            assert not any(key.startswith(TEMPORARY_BODY_PREFIX)
                           for key in item["state"]["bodies"])
            assert not any(str(key).startswith(TEMPORARY_BODY_PREFIX)
                           for key in item["state"].get("minds") or {})


# ----------------------------------------- the town's advance, once

class TestTheTownsOwnAdvanceIsNotDoubled:
    def test_the_mind_lives_the_span_here_and_the_town_once_after(
            self, temp_db):
        cid, ids, scene = _story(temp_db, town=_bound_to(
            "folk_0", lambda ids: ids["Mara"], "Mara"))
        before = registry_for(cid)["items"]["small_town"]["state"]
        clock = float(before["clock_hours"])
        log, far_end = live_in_charter(cid, scene, "Mara", _day(), SPAN_DAY)
        assert far_end["room"] == "house_a"
        # The commit stands the mind at its far end; then the town's own
        # out-of-band advance lives the same span for its people.
        after_scene = dict(scene, positions={"Mara": far_end["room"]})
        advanced, _rows, _events = advance_snapshot(
            registry_for_update(cid), elapsed_seconds=24 * H,
            epoch_id="beat_skip", base_turn=1, cid=cid, frame_id=None,
            scene=after_scene)
        state = advanced["items"]["small_town"]["state"]
        assert float(state["clock_hours"]) == clock + 24.0
        # The residents lived it -- the smith stood his forge.
        assert state["walked"].get("smith")
        # The mind's own body did not live it twice: it stands where the
        # commit put it, walked by nobody, and tired by nobody here.
        assert state["bodies"]["folk_0"]["place"] == "house_a"
        assert "folk_0" not in state["walked"]
        assert "folk_0" not in state["needs"]


class TestABodyReservedForAMindIsTheMinds:
    def test_the_engines_own_seat_token_reserves_a_body(self):
        charter = {"bindings": {}, "bodies": {
            "lead_psychologist:featured:ea04f223bf": {
                "name": "Sarah Moon", "place": "psych_office",
                "resident_seed_id": "character:63"}}}
        assert body_of_an_authored_mind(
            charter, "lead_psychologist:featured:ea04f223bf")

    def test_the_town_does_not_walk_a_body_reserved_for_a_mind(self):
        town = _town()
        town["bodies"]["smith"]["resident_seed_id"] = "character:7"
        after, _ = step(town, hours=4.0, seed=3)
        assert after["bodies"]["smith"]["place"] == "house_a"
        assert "smith" not in after["walked"]

    def test_a_reserved_body_follows_the_scene_in_the_towns_advance(
            self, temp_db):
        def reserved(ids):
            town = _town()
            town["bodies"]["smith"]["resident_seed_id"] = \
                "character:%d" % ids["Wat Hollin"]
            return town
        cid, ids, scene = _story(temp_db, town=reserved,
                                 minds=("Wat Hollin",), at="tavern")
        advanced, _rows, _events = advance_snapshot(
            registry_for_update(cid), elapsed_seconds=4 * H,
            epoch_id="beat_one", base_turn=1, cid=cid, frame_id=None,
            scene=scene)
        state = advanced["items"]["small_town"]["state"]
        assert state["bodies"]["smith"]["place"] == "tavern"
        assert "smith" not in state["walked"]


class TestTheTownStoresTheDayItsMindsLived:
    @pytest.mark.parametrize("lag", [0.0, 30.0])
    def test_the_towns_own_advance_steps_the_skip_as_the_minds_lived_it(
            self, temp_db, lag):
        """The town's advance after a time-skip beat is stepped on the
        skip's own windows and seed, so where it stores its people is where
        the mind saw them. Measured on three owner registries before this:
        13 of 21, 2 of 10 and 43 of 66 residents ended the span where the
        mind's run had them; on the skip's grid, 21 of 21 and 66 of 66 (the
        tenth of chat 115 is its mind's own post, below).

        ``lag``: the town's own clock standing behind the story's when the
        skip begins -- 5 and 25 seconds in chats 115 and 114. The grid opens
        where the town stands, as its own advance will."""
        from world.charter_skip import _stretches, _TownRun

        # A town that runs errands often, so where its people end the day
        # turns on the day's own draws.
        cid, ids, scene = _story(temp_db, town=_town(errand_rate=0.3))
        span = {"from_s": lag, "until_s": lag + 24 * H}
        day = [dict(row, from_s=row["from_s"] + lag,
                    until_s=row["until_s"] + lag) for row in _day()]
        log, far_end = live_in_charter(cid, scene, "Mara", day, span)
        lived = _TownRun(
            cid, scene, registry_for(cid), "small_town",
            TEMPORARY_BODY_PREFIX + str(ids["Mara"]), temporary=True,
            mind_name="Mara", char_id=ids["Mara"],
            stretches=_stretches(day, lag, lag + 24 * H),
            span=(lag, lag + 24 * H), deadline=None)
        lived.live()
        where = {key: body["place"] for key, body in
                 lived.states["small_town"]["state"]["bodies"].items()
                 if not key.startswith(TEMPORARY_BODY_PREFIX)}
        # The commit stands the mind at its far end; the beat runs on past
        # the skip by its own steps; then the town advances out of band.
        advanced, _rows, _events = advance_snapshot(
            registry_for_update(cid), elapsed_seconds=lag + 24 * H + 30.0,
            epoch_id="beat_skip", base_turn=1, cid=cid, frame_id=None,
            scene=dict(scene, positions={"Mara": far_end["room"]}),
            context="time_skip")
        stored = {key: body["place"] for key, body in
                  advanced["items"]["small_town"]["state"]["bodies"].items()}
        assert stored == where
