"""Authored bearings must survive model re-declarations (maze arm, live).

The measured damage: a harness-authored 7x7 maze whose every edge carried a
correct `dir` ended, after ~400 turns of ordinary Director/mapping room
re-declarations, with 18 of 98 edge-sides stripped bare (including the
shrine's ONLY approach, r0503-r0603) and 10 more carrying
internally-consistent but geometrically FALSE bearings. Three engine
mechanisms manufactured that out of model noise:

  * `_merge_room` upserted edges by `to` with WHOLESALE replacement, so a
    model re-mentioning a doorway without echoing its bearing erased it --
    the exact silence-vs-erasure bug `_merge_entity` fixes for entity
    fields, unfixed at edge level;
  * `normalize_scene_bearings` answers a contradiction by dropping BOTH
    sides, so one wrong model claim destroyed the standing authored truth
    beside it;
  * its reciprocal inference then faithfully completed whatever wrong
    bearing was asserted next into a consistent pair of lies.

Downstream, `sprint_reach` refused to offer any passage whose first edge
lacked a `dir`, so the character was told nothing and the event log filled
with "fails to move east due to missing bearing" -- three clusters of
beats (130-133, 338-341, 406-408) re-declaring a compass the world could
not bind, previously misread as psychology.

Database-independent: pure merge and offer-shape contracts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from world.spatial import merge_scene_with_diff, sprint_reach
from world.spatial import normalize_scene_bearings


def _scene(rooms):
    return {"rooms": rooms, "entities": {}, "positions": {}}


def _pair(a, b, dir_ab, dir_ba, barrier="open"):
    """Two rooms declaring one doorway from both sides."""
    return {
        a: {"name": a, "adjacent": [
            {"to": b, "barrier": barrier, "distance": "immediate",
             "dir": dir_ab}]},
        b: {"name": b, "adjacent": [
            {"to": a, "barrier": barrier, "distance": "immediate",
             "dir": dir_ba}]},
    }


class TestEdgeFieldsSurviveSilence:
    """_merge_room: an incoming edge field that is absent is silence, never
    an erasure -- the doctrine `_merge_entity` established, applied at the
    level where the live scene actually bled."""

    def test_a_redeclared_doorway_keeps_its_bearing(self):
        """The exact live kill shape: the Director re-mentions the shrine
        doorway ("r0503 connects to r0603, open") without the bearing it
        never thinks about, and the authored `dir` must survive."""
        scene = _scene(_pair("r0503", "r0603", "s", "n"))
        diff = {"rooms": {"r0503": {"adjacent": [
            {"to": "r0603", "barrier": "open", "distance": "immediate"}]}}}
        merged = merge_scene_with_diff(scene, diff)
        edge = merged["rooms"]["r0503"]["adjacent"][0]
        assert edge["dir"] == "s"
        assert edge["barrier"] == "open"

    def test_a_bearing_survives_normalization_after_the_merge(self):
        """End-to-end with the normalizer: nothing later in the pipeline
        re-drops what the merge preserved."""
        scene = _scene(_pair("r0503", "r0603", "s", "n"))
        diff = {"rooms": {"r0503": {"adjacent": [
            {"to": "r0603", "barrier": "open"}]}}}
        merged = normalize_scene_bearings(merge_scene_with_diff(scene, diff))
        assert merged["rooms"]["r0503"]["adjacent"][0]["dir"] == "s"
        assert merged["rooms"]["r0603"]["adjacent"][0]["dir"] == "n"

    def test_a_spoken_field_still_lands(self):
        """Deliberate changes are not blocked: a barrier change carried by
        the re-declaration takes effect while the unmentioned bearing and
        distance survive."""
        scene = _scene(_pair("hall", "vault", "e", "w"))
        diff = {"rooms": {"hall": {"adjacent": [
            {"to": "vault", "barrier": "closed_door"}]}}}
        merged = merge_scene_with_diff(scene, diff)
        edge = merged["rooms"]["hall"]["adjacent"][0]
        assert edge["barrier"] == "closed_door"
        assert edge["dir"] == "e"
        assert edge["distance"] == "immediate"

    def test_a_new_edge_is_taken_as_declared(self):
        scene = _scene(_pair("hall", "vault", "e", "w"))
        diff = {"rooms": {"hall": {"adjacent": [
            {"to": "garden", "barrier": "open", "dir": "n"}]}}}
        merged = merge_scene_with_diff(scene, diff)
        edges = {e["to"]: e for e in merged["rooms"]["hall"]["adjacent"]}
        assert edges["garden"]["dir"] == "n"
        assert edges["vault"]["dir"] == "e"


class TestStandingBearingsResistOneSidedRewrites:
    """A doorway both sides agree on is settled geometry. One passing model
    claim must not overturn it -- measured live as five doorway pairs of
    internally-consistent false bearings, and a runner walked north on a
    declared west."""

    def test_a_one_sided_contradiction_is_refused(self):
        scene = _scene(_pair("r0304", "r0404", "s", "n"))
        diff = {"rooms": {"r0304": {"adjacent": [
            {"to": "r0404", "barrier": "open", "dir": "w"}]}}}
        merged = normalize_scene_bearings(merge_scene_with_diff(scene, diff))
        assert merged["rooms"]["r0304"]["adjacent"][0]["dir"] == "s", (
            "the standing two-sided agreement outranks a passing claim")
        assert merged["rooms"]["r0404"]["adjacent"][0]["dir"] == "n", (
            "and the untouched reciprocal must not be collateral damage")

    def test_a_two_sided_redeclaration_lands(self):
        """Changing settled geometry is allowed -- it takes both sides,
        said consistently, which is what deliberate re-authoring looks
        like and what noise never does."""
        scene = _scene(_pair("hall", "vault", "e", "w"))
        diff = {"rooms": {
            "hall": {"adjacent": [
                {"to": "vault", "barrier": "open", "dir": "n"}]},
            "vault": {"adjacent": [
                {"to": "hall", "barrier": "open", "dir": "s"}]},
        }}
        merged = merge_scene_with_diff(scene, diff)
        assert merged["rooms"]["hall"]["adjacent"][0]["dir"] == "n"
        assert merged["rooms"]["vault"]["adjacent"][0]["dir"] == "s"

    def test_an_unsettled_bearing_may_be_written_one_sided(self):
        """The shield protects AGREEMENTS, not absence: a doorway with no
        standing pair takes a one-sided bearing exactly as before, and the
        normalizer completes the reciprocal."""
        rooms = _pair("hall", "vault", None, None)
        for room in rooms.values():
            room["adjacent"][0].pop("dir")
        scene = _scene(rooms)
        diff = {"rooms": {"hall": {"adjacent": [
            {"to": "vault", "barrier": "open", "dir": "e"}]}}}
        merged = normalize_scene_bearings(merge_scene_with_diff(scene, diff))
        assert merged["rooms"]["hall"]["adjacent"][0]["dir"] == "e"
        assert merged["rooms"]["vault"]["adjacent"][0]["dir"] == "w"

    def test_the_callers_diff_is_never_mutated(self):
        scene = _scene(_pair("r0304", "r0404", "s", "n"))
        diff = {"rooms": {"r0304": {"adjacent": [
            {"to": "r0404", "barrier": "open", "dir": "w"}]}}}
        merge_scene_with_diff(scene, diff)
        assert diff["rooms"]["r0304"]["adjacent"][0]["dir"] == "w"


class TestBearinglessDoorwaysStillRun:
    """sprint_reach: a doorway with no bearing is still a doorway. Refusing
    to offer it deleted the shrine's only approach from every run and
    produced beats of a character declaring a compass the world could not
    bind."""

    def _corridor(self, first_dir):
        """start -> a -> b -> end, single file; the first doorway's `dir`
        is the variable under test."""
        first = {"to": "a", "barrier": "open"}
        if first_dir:
            first["dir"] = first_dir
        return {
            "start": {"name": "start", "adjacent": [first]},
            "a": {"name": "a", "adjacent": [
                {"to": "start", "barrier": "open"},
                {"to": "b", "barrier": "open"}]},
            "b": {"name": "b", "adjacent": [
                {"to": "a", "barrier": "open"},
                {"to": "end", "barrier": "open"}]},
            "end": {"name": "end", "adjacent": [
                {"to": "b", "barrier": "open"}]},
        }

    def test_the_passage_is_offered_without_a_bearing_key(self):
        offers = sprint_reach({"rooms": self._corridor(None)}, "start")
        assert len(offers) == 1
        assert "bearing" not in offers[0], (
            "absent means the world gives no compass here -- a null would "
            "read as a heading to fill in")
        assert offers[0]["path"] == ["a", "b", "end"]
        assert offers[0]["stops"] == "dead_end"

    def test_a_beared_passage_is_offered_exactly_as_before(self):
        offers = sprint_reach({"rooms": self._corridor("e")}, "start")
        assert len(offers) == 1
        assert offers[0]["bearing"] == "e"
        assert offers[0]["path"] == ["a", "b", "end"]

    def test_no_heading_certifies_no_sightline(self):
        """The offer-side firewall holds: with no straight line to vouch
        for it, only the first room (seen through the doorway) is offered
        to a character who has walked none of it -- everything beyond is
        remembered ground only."""
        offers = sprint_reach({"rooms": self._corridor(None)}, "start",
                              known_rooms=set())
        assert len(offers) == 1
        assert offers[0]["path"] == ["a"]
        assert offers[0]["stops"] == "unknown"

    def test_remembered_ground_extends_a_bearingless_run(self):
        offers = sprint_reach({"rooms": self._corridor(None)}, "start",
                              known_rooms={"a", "b", "end"})
        assert offers[0]["path"] == ["a", "b", "end"]


class TestASiblingCollisionSparesTheIncumbent:
    """The third mechanism above, one case wider than the maze arm found it.

    `normalize_scene_bearings` resolves a same-bearing collision by dropping
    `dir` from every edge in it. That is right when both claims arrive
    together -- nothing chooses between them. It is wrong when one of them
    was already settled, because then something does.

    Measured live (chat 114 turn 10): the Director minted `tardis_console_room`
    off the beach carrying `dir: w`, while the beach's standing edge to the
    terrace was also `w`. The collision rule took BOTH, leaving a room whose
    every edge was bearingless -- and `spatial_fov._sight_neighbours` skips an
    edge with no bearing, so nothing could place either neighbour in the
    observer's field at all. One newly minted room cost the story the geometry
    of a doorway that had stood since its first beat.
    """

    def test_a_new_edge_does_not_take_a_settled_bearing_down_with_it(self):
        scene = _scene(_pair("beach", "terrace", "w", "e"))
        diff = {"rooms": {
            "beach": {"adjacent": [
                {"to": "terrace", "barrier": "open", "dir": "w"},
                {"to": "tardis", "barrier": "open_door", "dir": "w"}]},
            "tardis": {"name": "tardis", "adjacent": [
                {"to": "beach", "barrier": "open_door"}]}}}
        merged = merge_scene_with_diff(scene, diff)
        edges = {e["to"]: e.get("dir")
                 for e in merged["rooms"]["beach"]["adjacent"]}
        assert edges["terrace"] == "w", "the incumbent must survive"
        assert edges["tardis"] is None, "the newcomer is dropped, not guessed"
        assert merged["rooms"]["terrace"]["adjacent"][0]["dir"] == "e"

    def test_a_non_colliding_mint_keeps_its_bearing(self):
        """The guard is scoped to the collision: an honest bearing lands, and
        its reciprocal is still inferred."""
        scene = _scene(_pair("beach", "terrace", "w", "e"))
        diff = {"rooms": {
            "beach": {"adjacent": [
                {"to": "terrace", "barrier": "open", "dir": "w"},
                {"to": "tardis", "barrier": "open_door", "dir": "n"}]},
            "tardis": {"name": "tardis", "adjacent": [
                {"to": "beach", "barrier": "open_door"}]}}}
        merged = merge_scene_with_diff(scene, diff)
        edges = {e["to"]: e.get("dir")
                 for e in merged["rooms"]["beach"]["adjacent"]}
        assert edges == {"terrace": "w", "tardis": "n"}
        assert merged["rooms"]["tardis"]["adjacent"][0]["dir"] == "s"

    def test_two_fresh_claims_still_both_drop(self):
        """Unchanged where the drop rule was right: neither bearing was
        standing, so nothing chooses between them and neither is guessed."""
        scene = _scene({"hall": {"name": "hall", "adjacent": []}})
        diff = {"rooms": {
            "hall": {"adjacent": [
                {"to": "vault", "barrier": "open", "dir": "e"},
                {"to": "cellar", "barrier": "open", "dir": "e"}]},
            "vault": {"name": "vault", "adjacent": [
                {"to": "hall", "barrier": "open"}]},
            "cellar": {"name": "cellar", "adjacent": [
                {"to": "hall", "barrier": "open"}]}}}
        merged = merge_scene_with_diff(scene, diff)
        assert all(e.get("dir") is None
                   for e in merged["rooms"]["hall"]["adjacent"])

    def test_a_two_sided_replan_still_moves_the_incumbent(self):
        """The incumbent is defended only while the diff leaves it alone.
        Re-declare it in the same breath and both claims are live again --
        the case the drop rule exists for."""
        scene = _scene(_pair("beach", "terrace", "w", "e"))
        diff = {"rooms": {
            "beach": {"adjacent": [
                {"to": "terrace", "barrier": "open", "dir": "n"},
                {"to": "tardis", "barrier": "open_door", "dir": "w"}]},
            "terrace": {"adjacent": [
                {"to": "beach", "barrier": "open", "dir": "s"}]},
            "tardis": {"name": "tardis", "adjacent": [
                {"to": "beach", "barrier": "open_door"}]}}}
        merged = merge_scene_with_diff(scene, diff)
        edges = {e["to"]: e.get("dir")
                 for e in merged["rooms"]["beach"]["adjacent"]}
        assert edges == {"terrace": "n", "tardis": "w"}

    def test_the_doorway_itself_is_never_the_casualty(self):
        """Whatever happens to the compass, the way through survives -- the
        invariant every rule in this module is written under."""
        scene = _scene(_pair("beach", "terrace", "w", "e"))
        diff = {"rooms": {
            "beach": {"adjacent": [
                {"to": "terrace", "barrier": "open", "dir": "w"},
                {"to": "tardis", "barrier": "open_door", "dir": "w"}]},
            "tardis": {"name": "tardis", "adjacent": [
                {"to": "beach", "barrier": "open_door"}]}}}
        merged = merge_scene_with_diff(scene, diff)
        assert {e["to"] for e in merged["rooms"]["beach"]["adjacent"]} == {
            "terrace", "tardis"}
        assert merged["rooms"]["beach"]["adjacent"][1]["barrier"] == "open_door"


class TestADoorwayNobodyGaveAWallStillHasOne:
    """`derived_edge_bearings` (2026-09-06).

    `spatial_fov.room_field` places a neighbour only where the edge carries
    a bearing, and a bearing is written by a hand that stood in the room and
    said which way the door was. A room the Writers' Room planned has never
    been stood in -- the plan schema asks for `{to, barrier, distance}` and
    no bearing at all -- so its composite was an ISLAND, and the near sound
    field answered `none` to a loud noise through an open door in the next
    room because the next room was not on the field. Measured across the
    stories live on 2026-09-06 (chats 115, 116 and the descent copy): 4 of
    54 edges carried a bearing, and 0 of the 38 belonging to a planned room.
    """

    def _pair(self, near_dir=None, far_dir=None):
        near = {"to": "b", "barrier": "open_door"}
        far = {"to": "a", "barrier": "open_door"}
        if near_dir:
            near["dir"] = near_dir
        if far_dir:
            far["dir"] = far_dir
        return {"rooms": {"a": {"name": "a", "adjacent": [near]},
                          "b": {"name": "b", "adjacent": [far]}}}

    def test_a_silent_doorway_is_given_opposite_walls_at_its_two_ends(self):
        from world.spatial import derived_edge_bearings, opposite_bearing

        derived = derived_edge_bearings(self._pair())
        assert derived[("a", "b")] == opposite_bearing(derived[("b", "a")])

    def test_a_declared_bearing_is_never_moved_or_contradicted(self):
        from world.spatial import derived_edge_bearings

        for scene in (self._pair(near_dir="e"), self._pair(far_dir="w")):
            assert derived_edge_bearings(scene) == {}

    def test_a_derived_wall_never_collides_with_a_declared_one(self):
        from world.spatial import derived_edge_bearings

        rooms = {"hub": {"name": "hub", "adjacent": [
            {"to": "n1", "barrier": "open", "dir": "n"},
            {"to": "x1", "barrier": "open"},
            {"to": "x2", "barrier": "open"}]}}
        for uid in ("n1", "x1", "x2"):
            rooms[uid] = {"name": uid,
                          "adjacent": [{"to": "hub", "barrier": "open"}]}
        derived = derived_edge_bearings({"rooms": rooms})
        walls = [derived[("hub", uid)] for uid in ("x1", "x2")]
        assert "n" not in walls and len(set(walls)) == 2

    def test_a_room_with_more_doorways_than_walls_leaves_the_rest_unplaced(self):
        """Eight points, one apiece: a ninth way through has nowhere to go,
        and stays unplaced rather than sharing a wall -- sharing is the
        collision `normalize_scene_bearings` drops both sides of."""
        from world.spatial import DERIVED_BEARING_LIMIT, derived_edge_bearings

        count = DERIVED_BEARING_LIMIT + 1
        rooms = {"hub": {"name": "hub", "adjacent": [
            {"to": "r%d" % i, "barrier": "open"} for i in range(count)]}}
        for i in range(count):
            rooms["r%d" % i] = {"name": "r%d" % i,
                                "adjacent": [{"to": "hub", "barrier": "open"}]}
        derived = derived_edge_bearings({"rooms": rooms})
        placed = [uid for uid in rooms if ("hub", uid) in derived]
        assert len(placed) == DERIVED_BEARING_LIMIT

    def test_sound_crosses_the_derived_doorway_and_sight_does_not(self):
        """Sound and light ask how MUCH of a thing reaches you, and a
        guessed wall moves that number a little in a model that estimates
        throughout. Sight asks WHAT you can make out, and its answer is a
        list of things: a guessed wall there does not shade an answer, it
        mints an object the observer could not have seen. So sight keeps
        its refusal (`test_openings_in_view.py`) and the two senses whose
        failure is a level ask for the estimate."""
        from world.spatial import observer_field, sound_field

        scene = self._pair()
        scene["rooms"]["a"]["extent"] = {"w": 8, "d": 8}
        scene["rooms"]["b"]["extent"] = {"w": 8, "d": 8}
        scene["positions"] = {"L": "b"}
        assert sorted(sound_field(scene, "L").grid.offsets) == ["a", "b"]
        assert sorted(observer_field(scene, "L").offsets) == ["b"]
