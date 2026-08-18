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
from world.spatial_orientation import normalize_scene_bearings


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
