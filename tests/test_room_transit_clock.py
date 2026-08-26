"""A place may take time to cross, and an occupant crosses it on the clock.

THE MEASUREMENT, read-only against the author's corpus 2026-08-25 at 49ea899:
chat 89 entered a holder's interior at turn 54 and was still in the same
station at turn 62 -- nine beats, five of them with empty player input and no
readable time claim at all. Its sibling chat 88, entered on identical player
input, crossed three stations in four turns because that player kept feeding
physical beats the Director could read continuation into. The engine had no
mechanism; it had luck.

CLASS VOCABULARY ONLY IN THIS FILE. A vessel, an occupant and three stations
-- what the mechanism serves is a throat, a chute, a lift shaft, a mine
gallery and a river reach alike, and a fixture named after any one of them
would narrow what the next reader thinks the field is for.
"""
import copy
import json

import pytest

from world.spatial import (_UNSTATED_CROSSING_SECONDS,
                           advance_room_transits, materialize_named_stations,
                           merge_scene_with_diff, room_transit_seconds)

VESSEL = "vessel_one"
OCCUPANT = "Traveller"


def _chain_scene(*, transit=(10.0, 10.0, None), motion="moving",
                 body=True, start=0):
    """A vessel with an exterior room and a linear interior chain.

    `transit` gives each station's declared crossing time, outermost first;
    None means the station declares none. The occupant starts in station
    `start`.
    """
    rooms = {
        "outside": {"name": "Outside", "desc": "", "adjacent": []},
    }
    ids = ["st_%d" % i for i in range(len(transit))]
    for i, rid in enumerate(ids):
        room = {
            "name": "Station %d" % i,
            "desc": "",
            "light": "dark",
            "parent_entity": VESSEL,
            "adjacent": [],
        }
        if i == 0:
            room["dock_exit"] = True
        if transit[i] is not None:
            room["transit_seconds"] = transit[i]
        rooms[rid] = room
    for a, b in zip(ids, ids[1:]):
        rooms[a]["adjacent"].append({"to": b, "barrier": "membrane"})
        rooms[b]["adjacent"].append({"to": a, "barrier": "membrane"})
    scene = {
        "location": "Nowhere",
        "rooms": rooms,
        "entities": {
            VESSEL: {"name": "The Vessel", "kind": "person", "aliases": [],
                     "interior_rooms": list(ids), "state": {}},
        },
        "positions": {OCCUPANT: ids[start], "The Vessel": "outside"},
        "contacts": [{
            "actor": OCCUPANT, "target": "The Vessel", "relation": "interior",
            "target_interior": "Station %d" % start, "target_part": "",
            "motion": motion, "manner": "", "detail": "",
        }],
        "contained": {},
        "poses": {}, "stations": {}, "overlays": {}, "substances": [],
        # `_is_body_entity` reads exactly these two tables: a thing that WEARS
        # something or has a SIZE is a body, and a lift car, a crate and a
        # ship have neither.
        "attire": ({"The Vessel": {"worn": []}, OCCUPANT: {"worn": []}}
                   if body else {}),
        "scales": {},
    }
    return scene


def _where(scene):
    return (scene.get("positions") or {}).get(OCCUPANT)


def _contact(scene):
    for row in scene.get("contacts") or []:
        if str(row.get("relation") or "") == "interior":
            return row
    return {}


class TestAnAuthoredMagnitudeIsTheDeclaration:

    def test_the_reader_takes_a_positive_finite_number_and_nothing_else(self):
        assert room_transit_seconds({"transit_seconds": 8}) == 8.0
        assert room_transit_seconds({"transit_seconds": "14400"}) == 14400.0
        # `_tick_interval`'s doctrine: a field filled in with nothing is not
        # a cadence. 48 of 131 corpus rows spelled `0` where they meant unset.
        for bad in (None, 0, 0.0, -5, "soon", "", True, False,
                    float("inf"), float("nan")):
            assert room_transit_seconds({"transit_seconds": bad}) is None, bad
        assert room_transit_seconds({}) is None
        assert room_transit_seconds(None) is None

    def test_an_occupant_crosses_at_the_declared_magnitude_and_not_before(
            self):
        scene = _chain_scene()
        held = merge_scene_with_diff(scene, {}, clock_seconds=0.0)
        assert _where(held) == "st_0"
        # One second short.
        near = merge_scene_with_diff(held, {}, clock_seconds=9.0)
        assert _where(near) == "st_0"
        # On the bound.
        crossed = merge_scene_with_diff(near, {}, clock_seconds=10.0)
        assert _where(crossed) == "st_1"

    def test_the_remainder_is_carried_never_discarded(self):
        """A beat covering a long span crosses as many stations as the span
        buys, and the leftover counts toward the next one. `since` advances
        by the bound spent, not to `now`."""
        scene = merge_scene_with_diff(_chain_scene(), {}, clock_seconds=0.0)
        far = merge_scene_with_diff(scene, {}, clock_seconds=25.0)
        assert _where(far) == "st_2"
        stamp = far["room_since"][OCCUPANT]
        assert stamp["room"] == "st_2"
        # 10 + 10 spent; 5 carried into the terminal station.
        assert stamp["since"] == 20.0

    def test_a_terminal_station_with_no_magnitude_holds_forever(self):
        scene = merge_scene_with_diff(_chain_scene(), {}, clock_seconds=0.0)
        far = merge_scene_with_diff(scene, {}, clock_seconds=25.0)
        assert _where(far) == "st_2"
        for clock in (100.0, 100000.0, 1e9):
            far = merge_scene_with_diff(far, {}, clock_seconds=clock)
            assert _where(far) == "st_2"

    def test_a_large_magnitude_is_a_chamber_and_needs_no_enum(self):
        """The distinction is DERIVED from the magnitude. A station that
        kneads its occupant for hours authors the hours and is crossed --
        slowly. No `role` field ships, because an enum saying 'conduit' with
        no magnitude gives the crosser nothing to cross."""
        scene = _chain_scene(transit=(25200.0, 10.0, None))
        scene = merge_scene_with_diff(scene, {}, clock_seconds=0.0)
        for clock in (60.0, 3600.0, 25199.0):
            scene = merge_scene_with_diff(scene, {}, clock_seconds=clock)
            assert _where(scene) == "st_0"
        scene = merge_scene_with_diff(scene, {}, clock_seconds=25200.0)
        assert _where(scene) == "st_1"


class TestTheMergeIsUnchangedWithoutAClock:

    def test_no_clock_is_a_hard_no_op(self):
        """Every caller that merges for a purpose other than living a beat
        -- a paradox probe, a Director preview, a migration re-merge -- must
        get exactly the scene this function produced before crossings
        existed."""
        scene = _chain_scene()
        first = merge_scene_with_diff(copy.deepcopy(scene), {})
        assert _where(first) == "st_0"
        assert "room_since" not in first
        # And a clock changes it only because a clock was given. THE FIRST
        # CLOCKED MERGE ONLY STAMPS: a body the clock has not seen here
        # before starts its crossing now, which is what backfills every
        # enclosure entered before this landing existed rather than
        # teleporting its occupant to the deep end on the first beat.
        stamped = merge_scene_with_diff(copy.deepcopy(scene), {},
                                        clock_seconds=1e6)
        assert _where(stamped) == "st_0"
        assert stamped["room_since"][OCCUPANT]["since"] == 1e6
        carried = merge_scene_with_diff(stamped, {}, clock_seconds=1e6 + 25)
        assert _where(carried) == "st_2"

    def test_a_clocked_merge_is_a_fixpoint_at_one_clock(self):
        scene = merge_scene_with_diff(_chain_scene(), {}, clock_seconds=40.0)
        again = merge_scene_with_diff(scene, {}, clock_seconds=40.0)
        assert json.dumps(scene, sort_keys=True) == \
            json.dumps(again, sort_keys=True)

    def test_the_stamp_is_absent_when_nobody_is_crossing(self):
        """The `expired_entity_state` rule: written only while it says
        something, popped when it does not. Never `setdefault`."""
        scene = _chain_scene(transit=(None, None, None), motion="settled")
        merged = merge_scene_with_diff(scene, {}, clock_seconds=500.0)
        assert "room_since" not in merged


class TestTheEngineRefusesToGuessADestination:

    def test_a_branch_moves_nobody(self):
        """Two strictly-deeper neighbours is a grafted topology where no
        fact in the scene picks one. Guessing would be invention."""
        scene = _chain_scene(transit=(10.0, None, None))
        scene["rooms"]["st_branch"] = {
            "name": "Station branch", "desc": "", "light": "dark",
            "parent_entity": VESSEL, "adjacent": [
                {"to": "st_0", "barrier": "membrane"}],
        }
        scene["rooms"]["st_0"]["adjacent"].append(
            {"to": "st_branch", "barrier": "membrane"})
        scene["entities"][VESSEL]["interior_rooms"].append("st_branch")
        merged = merge_scene_with_diff(scene, {}, clock_seconds=10000.0)
        assert _where(merged) == "st_0"

    def test_a_shut_boundary_holds_the_occupant(self):
        """`closed_door` is not passable, so a shut door in a lift shaft
        holds you -- and the crossing resumes by itself on the beat
        something opens it."""
        scene = _chain_scene()
        for room in ("st_0", "st_1"):
            for edge in scene["rooms"][room]["adjacent"]:
                if edge["to"] in ("st_0", "st_1"):
                    edge["barrier"] = "closed_door"
        shut = merge_scene_with_diff(scene, {}, clock_seconds=10000.0)
        assert _where(shut) == "st_0"
        # Open it, and the same clock carries them.
        opened = copy.deepcopy(shut)
        for room in ("st_0", "st_1"):
            for edge in opened["rooms"][room]["adjacent"]:
                if edge["to"] in ("st_0", "st_1"):
                    edge["barrier"] = "membrane"
        moved = merge_scene_with_diff(opened, {}, clock_seconds=20000.0)
        assert _where(moved) == "st_2"

    def test_the_walk_can_never_eject_anybody(self):
        """Restricted to the holder's own interior set BY CONSTRUCTION, so
        the exterior room on the far side of the way in is excluded rather
        than checked for. Leaving stays a declared act."""
        scene = _chain_scene(transit=(10.0,))
        merged = merge_scene_with_diff(scene, {}, clock_seconds=100000.0)
        assert _where(merged) == "st_0"
        assert _where(merged) != "outside"

    def test_an_exterior_conduit_is_read_and_refused_by_name(self):
        """THE STATED BOUND OF THIS LANDING. A room with no `parent_entity`
        -- an exterior conduit, a river reach, a conveyor hall -- has no
        derivable way in, so 'onward' has no meaning. The declaration is
        READ and refused with a notice naming the missing fact, never a
        guessed move, and never silently ignored."""
        scene = _chain_scene(transit=(None, None, None), motion="settled")
        scene["rooms"]["outside"]["transit_seconds"] = 5.0
        # No enclosure at all: an ordinary room that declares a crossing.
        scene["contacts"] = []
        scene["positions"][OCCUPANT] = "outside"
        # Only the occupant stands in the conduit: the refusal is per body,
        # so a second body standing there is a second (correct) notice.
        scene["positions"]["The Vessel"] = "st_2"
        stamped = merge_scene_with_diff(scene, {}, clock_seconds=600.0)
        assert _where(stamped) == "outside"
        report = []
        merged = merge_scene_with_diff(stamped, {}, clock_seconds=606.0,
                                       crossing_report=report)
        assert _where(merged) == "outside"
        assert len(report) == 1
        assert "cannot derive which way is onward outside an enclosure" \
            in report[0]
        # Said ONCE. A standing situation does not re-report every beat.
        report2 = []
        merge_scene_with_diff(merged, {}, clock_seconds=1200.0,
                              crossing_report=report2)
        assert report2 == []


class TestTheLedgerDecidesAnUnauthoredStation:
    """No magnitude on the room: the occupant's own standing interior
    contact decides, in the engine's own two-word vocabulary. Measured
    against the corpus, this is what makes chat 88 and chat 89 come out
    differently for the right reason -- 88's row reads `settled` beside a
    card that measures its station in HOURS, 89's reads `moving`."""

    def test_a_running_crossing_advances_at_the_unstated_bound(self):
        scene = _chain_scene(transit=(None, None, None), motion="moving")
        scene = merge_scene_with_diff(scene, {}, clock_seconds=0.0)
        near = merge_scene_with_diff(
            scene, {}, clock_seconds=_UNSTATED_CROSSING_SECONDS - 1)
        assert _where(near) == "st_0"
        moved = merge_scene_with_diff(
            near, {}, clock_seconds=_UNSTATED_CROSSING_SECONDS)
        assert _where(moved) == "st_1"

    def test_a_settled_occupant_is_never_marched_anywhere(self):
        """Chat 88's measured shape. The structural rule -- 'you do not live
        in the middle of a chain' -- would drag this occupant out of a place
        its card measures in hours, in sixty seconds: the reported defect
        inverted at the same three orders of magnitude."""
        scene = _chain_scene(transit=(None, None, None), motion="settled")
        for clock in (60.0, 600.0, 86400.0):
            merged = merge_scene_with_diff(scene, {}, clock_seconds=clock)
            assert _where(merged) == "st_0"
            assert "room_since" not in merged

    def test_a_non_body_holder_moves_nobody_by_default(self):
        """The firewall bound `materialize_enclosure_interiors` gate 3 and
        `sync_entity_interior_rooms` both state: a lift car, a crate and a
        cargo hold need the non-body enclosure default first."""
        scene = _chain_scene(transit=(None, None, None), body=False)
        merged = merge_scene_with_diff(scene, {}, clock_seconds=100000.0)
        assert _where(merged) == "st_0"

    def test_an_authored_magnitude_outranks_the_ledger_in_both_directions(
            self):
        """The declaration wins wherever the room stands: a settled occupant
        of a room that declares its crossing time IS crossed, because the
        place said how long it takes."""
        scene = _chain_scene(transit=(10.0, None, None), motion="settled")
        stamped = merge_scene_with_diff(scene, {}, clock_seconds=0.0)
        merged = merge_scene_with_diff(stamped, {}, clock_seconds=10.0)
        assert _where(merged) == "st_1"


class TestTheChat89Shape:
    """One minted station, a crossing the ledger says is running, and
    nowhere onward. The engine will not invent a station to deliver anybody
    into -- the world does not contain one -- so it says which fact is
    missing and retires the claim that a crossing is running."""

    def _scene(self):
        return _chain_scene(transit=(None,), motion="moving")

    def test_nobody_moves_and_the_missing_fact_is_named_once(self):
        scene = merge_scene_with_diff(self._scene(), {}, clock_seconds=0.0)
        quiet = merge_scene_with_diff(scene, {}, clock_seconds=59.0)
        assert quiet.get("_crossing_notes") is None
        report = []
        overdue = merge_scene_with_diff(
            quiet, {}, clock_seconds=_UNSTATED_CROSSING_SECONDS,
            crossing_report=report)
        assert _where(overdue) == "st_0"
        assert len(report) == 1
        assert "declares no station beyond it" in report[0]

    def test_the_crossing_claim_is_retired_rather_than_the_fiction_invented(
            self):
        scene = merge_scene_with_diff(self._scene(), {}, clock_seconds=0.0)
        assert _contact(scene).get("motion") == "moving"
        overdue = merge_scene_with_diff(
            scene, {}, clock_seconds=_UNSTATED_CROSSING_SECONDS)
        assert _contact(overdue).get("motion") == "settled"

    def test_later_beats_are_silent_about_the_same_standing_situation(self):
        scene = merge_scene_with_diff(self._scene(), {}, clock_seconds=0.0)
        overdue = merge_scene_with_diff(
            scene, {}, clock_seconds=_UNSTATED_CROSSING_SECONDS)
        report = []
        later = merge_scene_with_diff(overdue, {}, clock_seconds=600.0,
                                      crossing_report=report)
        assert report == []
        assert _where(later) == "st_0"


class TestTheOnRamp:
    """A standing interior contact naming a region the holder's inside has
    no room for is a station the story declared and the engine never built.

    Measured inert on all 78 stored scenes 2026-08-25: five such contacts
    exist, and in every one the occupant is standing in the holder's
    EXTERIOR room, which gate 2 skips -- the merge's own mint names the same
    region from the same ledger one step earlier."""

    def test_a_newly_named_region_becomes_the_next_station(self):
        scene = _chain_scene(transit=(None,), motion="moving")
        _contact(scene)["target_interior"] = "Deeper"
        merged = merge_scene_with_diff(scene, {}, clock_seconds=0.0)
        here = _where(merged)
        assert here != "st_0"
        room = merged["rooms"][here]
        assert room["name"] == "Deeper"
        assert room["parent_entity"] == VESSEL
        # Chained to where they already stood, by the one barrier a body
        # passes through and nothing sees through.
        assert {"to": "st_0", "barrier": "membrane"} in room["adjacent"]

    def test_it_is_a_no_op_on_the_next_merge(self):
        scene = _chain_scene(transit=(None,), motion="moving")
        _contact(scene)["target_interior"] = "Deeper"
        once = merge_scene_with_diff(scene, {}, clock_seconds=0.0)
        twice = merge_scene_with_diff(once, {}, clock_seconds=0.0)
        assert len(twice["rooms"]) == len(once["rooms"])

    def test_a_region_that_already_resolves_mints_nothing(self):
        scene = _chain_scene(transit=(None, None, None), motion="moving")
        before = len(scene["rooms"])
        merged = merge_scene_with_diff(scene, {}, clock_seconds=0.0)
        assert len(merged["rooms"]) == before

    def test_it_refuses_past_the_station_cap(self):
        from world.spatial import _MAX_INTERIOR_STATIONS

        scene = _chain_scene(
            transit=tuple([None] * _MAX_INTERIOR_STATIONS), motion="moving")
        _contact(scene)["target_interior"] = "One Too Many"
        before = len(scene["rooms"])
        merged = merge_scene_with_diff(scene, {}, clock_seconds=0.0)
        assert len(merged["rooms"]) == before

    def test_a_non_body_holder_mints_nothing(self):
        """The same firewall bound the crossing itself is scoped by: an
        interior minted for a non-body is never indexed and never defaulted
        opaque, so an occupant a concealment was hiding becomes visible from
        the room outside -- information EXPANSION."""
        scene = _chain_scene(transit=(None,), motion="moving", body=False)
        _contact(scene)["target_interior"] = "Deeper"
        before = len(scene["rooms"])
        merged = merge_scene_with_diff(scene, {}, clock_seconds=0.0)
        assert len(merged["rooms"]) == before

    def test_the_chain_then_runs_on_the_clock_with_no_further_declaration(
            self):
        """The point of the on-ramp: one named region converts a dead end
        into a mechanism, and every later silent beat carries the occupant
        with no player and no further model output."""
        scene = _chain_scene(transit=(None,), motion="moving")
        _contact(scene)["target_interior"] = "Deeper"
        grafted = merge_scene_with_diff(scene, {}, clock_seconds=0.0)
        deeper = _where(grafted)
        # Now st_0 has somewhere onward, so an occupant put back at the
        # entry is carried on the clock alone.
        grafted["positions"][OCCUPANT] = "st_0"
        _contact(grafted)["target_interior"] = "Station 0"
        _contact(grafted)["motion"] = "moving"
        stamped = merge_scene_with_diff(grafted, {}, clock_seconds=0.0)
        carried = merge_scene_with_diff(
            stamped, {}, clock_seconds=_UNSTATED_CROSSING_SECONDS)
        assert _where(carried) == deeper


class TestTheLedgerFollowsTheBody:

    def test_a_carried_body_retargets_its_own_interior_contact(self):
        scene = merge_scene_with_diff(_chain_scene(), {}, clock_seconds=0.0)
        moved = merge_scene_with_diff(scene, {}, clock_seconds=10.0)
        row = _contact(moved)
        assert row["target_interior"] == "Station 1"
        # The cross op's own never-carry rule: the boundary just crossed is
        # not a point currently touched.
        assert row.get("target_part") == ""
        # A successful crossing does not retire the motion claim.
        assert row.get("motion") == "moving"

    def test_a_declared_position_resets_the_stamp_and_wins(self):
        """A DECLARED POSITION IS A DECLARED ACT. The stamp resets whenever
        the ledger's room differs from the stamped one, so a beat that moved
        a body starts its crossing from now rather than inheriting an
        expired one."""
        scene = merge_scene_with_diff(_chain_scene(), {}, clock_seconds=0.0)
        aged = merge_scene_with_diff(scene, {}, clock_seconds=9.0)
        declared = merge_scene_with_diff(
            aged, {"positions": {OCCUPANT: "st_2"}}, clock_seconds=9.0)
        assert _where(declared) == "st_2"
        assert declared["room_since"][OCCUPANT]["since"] == 9.0

    def test_a_body_that_leaves_the_scene_is_crossing_nothing(self):
        scene = merge_scene_with_diff(_chain_scene(), {}, clock_seconds=0.0)
        assert OCCUPANT in scene["room_since"]
        scene["entities"]["occupant_one"] = {
            "name": OCCUPANT, "kind": "person", "aliases": []}
        gone = merge_scene_with_diff(
            scene, {"remove_entities": ["occupant_one"]}, clock_seconds=0.0)
        assert OCCUPANT not in (gone.get("room_since") or {})
