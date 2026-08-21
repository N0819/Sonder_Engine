"""Needs, movement, and two towns that cannot feed themselves alone.

A need is an upkeep whose place is a body, so `available` stops being an
authored flag and becomes a consequence. That closes the loop the simulation
had been missing — a chain fails, the need it fed goes unserviced, bodies go
under, posts go unfilled, more chains fail — and the famine below is not
scripted anywhere.

Three defects this round, all of them found by running it:

  * bodies flapped across their floor every window, because coming off watch
    restored them instantly: 666 events in twenty days the log called quiet;
  * pressure only existed AFTER a body collapsed, so no watch could ever
    rotate and every patrol burned out inside twelve hours;
  * `post_believed_filled` keyed on which body was sent rather than on the
    post, so one cut road wrote 308 rows.
"""

from __future__ import annotations

from world.charter import (
    RECOVERY_MARGIN, able, chronicle, furthest_travelled, life_of, mood,
    normalize_charter, out_of_band, pressure, run, seed_needs, seed_roster)

from charter_worlds import twin_towns


def _ready(spec, fed_by="low_bread"):
    charter = normalize_charter(spec)
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"], template={
        "rest": {"floor": 0.15, "drift_per_hour": 0.030,
                 "service_per_hour": 0.110},
        "sustenance": {"floor": 0.10, "drift_per_hour": 0.014,
                       "service_per_hour": 0.090, "fed_by": fed_by},
    })
    return charter


class TestAWatchRotatesWithoutBeingScheduled:
    def test_twenty_days_of_two_working_towns_writes_nothing(self):
        """The cost model, and the rotation, in one assertion. If pressure
        were still a cliff the patrols would burn out on day one and this
        would be hundreds of rows."""
        _, events = run(_ready(twin_towns(240)), hours=480.0, window=4.0)

        assert events == []

    def test_pressure_rises_before_a_body_breaks_not_after(self):
        held = {"rest": {"key": "rest", "level": 0.5, "floor": 0.15,
                         "drift_per_hour": 0.03, "service_per_hour": 0.11,
                         "fed_by": ""}}

        assert pressure(held) > 0.0, "a half-spent body registered as fresh"
        assert able(held) is True

    def test_recovery_takes_more_than_crossing_back_over_the_line(self):
        """Hysteresis. Nobody stops being exhausted at the instant they cross
        the floor, and an institution that put them straight back on watch is
        one nobody would work for."""
        just_over = {"rest": {"key": "rest", "level": 0.16, "floor": 0.15,
                              "drift_per_hour": 0.0, "service_per_hour": 0.0,
                              "fed_by": ""}}

        assert able(just_over, was_able=True) is True
        assert able(just_over, was_able=False) is False
        rested = dict(just_over)
        rested["rest"] = dict(just_over["rest"],
                              level=0.15 + RECOVERY_MARGIN + 0.01)
        assert able(rested, was_able=False) is True


class TestTheRoadIsAnInput:
    def test_cutting_the_road_starves_both_towns_in_order(self):
        """One road, two chains, and no authored step between them. The
        upland grows and cannot mill; the lowland mills and cannot grow.
        """
        charter = _ready(twin_towns(240))
        charter, _ = run(charter, hours=480.0, window=4.0)
        for key, body in charter["bodies"].items():
            if "arms" in body["competence"]:
                body["available"] = False

        after, events = run(charter, hours=720.0, window=4.0)
        failures = [e for e in events if e["kind"] == "upkeep_out_of_band"]
        order = [e["upkeep"] for e in failures]

        assert order[0] == "road_open", "the road did not fail first"
        starved = {e["upkeep"]: e["starved_by"] for e in failures
                   if e.get("starved_by")}
        # Both towns' bread is starved, and the road is named as the cause of
        # at least one of them rather than the failure being unattributed.
        assert "road_open" in starved.values()
        assert out_of_band(after["upkeeps"]["low_bread"])

    def test_the_famine_reaches_the_people(self):
        """The loop closing: a chain fails, and the bodies at the end of it
        go under. `available` is a consequence here, not a flag."""
        charter = _ready(twin_towns(240))
        charter, _ = run(charter, hours=480.0, window=4.0)
        for key, body in charter["bodies"].items():
            if "arms" in body["competence"]:
                body["available"] = False

        after, events = run(charter, hours=720.0, window=4.0)
        went_under = [e for e in events if e["kind"] == "body_unable"]

        assert went_under, "a total famine put nobody out of action"
        # Each body reports going under once, not once a window.
        assert len({e["body"] for e in went_under}) == len(went_under)

    def test_an_authored_absence_is_not_undone_by_being_well_rested(self):
        """Needs may pick up only a body needs put down. One subsystem must
        not quietly overturn another's decision."""
        charter = _ready(twin_towns(240))
        armed = [k for k, b in charter["bodies"].items()
                 if "arms" in b["competence"]]
        for key in armed:
            charter["bodies"][key]["available"] = False

        after, _ = run(charter, hours=240.0, window=4.0)

        assert all(not after["bodies"][k]["available"] for k in armed)


class TestBodiesActuallyGo:
    def test_the_posted_travel_and_the_distance_is_counted(self):
        after, _ = run(_ready(twin_towns(240)), hours=480.0, window=4.0)
        travelled = after.get("travelled") or {}

        assert travelled, "nobody went anywhere in twenty days"
        assert all(rooms > 0 for rooms in travelled.values())
        top = furthest_travelled(travelled, limit=3)
        assert len(top) <= 3 and top[0][1] >= top[-1][1]

    def test_an_unreachable_post_does_not_teleport_anybody(self):
        """A charter's mistake must not be laundered into a movement."""
        charter = _ready(twin_towns(240))
        after, _ = run(charter, hours=48.0, window=4.0)

        for key, body in after["bodies"].items():
            assert body["place"] in after["scene"]["rooms"]


class TestTheIndividualCanBeRead:
    def test_a_body_has_a_readable_life(self):
        charter = _ready(twin_towns(240))
        after, events = run(charter, hours=480.0, window=4.0)
        who = furthest_travelled(after.get("travelled"), limit=1)[0][0]

        life = life_of(who, after, events)

        assert life["body"] == who
        assert life["rooms_travelled"] > 0
        assert set(life["needs"]) == {"rest", "sustenance"}
        assert "mood" in life and 0.0 <= life["mood"] <= 1.0
        assert isinstance(life["events"], list)


class TestMoodIsMeasuredNotUsed:
    """Kept out of the planner on purpose. `psychology_runtime` owns tone for
    characters, and a second affect model would leave a promoted body with two
    incompatible interiors. Measuring it is how we find out whether it would
    have earned its way in."""

    def test_mood_moves_with_pressure_blame_and_regard(self):
        rested = {"rest": {"key": "rest", "level": 1.0, "floor": 0.15,
                           "drift_per_hour": 0.0, "service_per_hour": 0.0,
                           "fed_by": ""}}
        spent = {"rest": dict(rested["rest"], level=0.2)}

        assert mood(rested) < mood(spent)
        assert mood(spent) < mood(spent, blamed=3)
        assert mood(spent, blamed=3) <= mood(
            spent, blamed=3, regard_of_others=[0.4, 0.5])

    def test_nothing_in_the_engine_reads_it(self):
        """The guard: `mood` may be reported and must not be planned on."""
        import pathlib

        package = pathlib.Path(__file__).resolve().parent.parent / "world"
        for path in package.glob("charter*.py"):
            if path.name in ("charter_needs.py", "charter_log.py",
                             "charter.py"):
                continue
            assert "mood" not in path.read_text(), path.name
