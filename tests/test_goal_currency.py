"""The beat-goal slot's currency: tenure and spend (maze, turns 370-385).

The measured failure: `active_state.goal` behaved as an UNGOVERNED project.
"Compare chalk circle patterns across chambers" survived a run boundary and
a process restart -- durable, steering, occupying the slot, with no
satisfied_when, cap, displacement rule, or visibility. Separately, "Run
east to Chamber 0403 along the proved line" was still the stated goal
EIGHT ROOMS past Chamber 0403, and the same shape recurred live at turn
384: goal "Run east to Chamber 0206 along the proved line" while the
visited tail read ... 0306 0206 0205 0206 0306 0206 -- the stale claim
tethering him back to the room it named, because one step out of 0206 made
0206 the destination again for exits, en_route and run offers alike.

Both are one defect: the slot is rewritten every commit from the enacted
want, but the CLAIM inside it is whatever the model re-emits, re-emission
is free (the en_route continuation-default made goals sticky by design, and
stickiness serves whatever holds the slot), and nothing counted the claim's
tenure or noticed its named room had been reached. The fix is the standing
legible-not-forced shape: commit stamps two deterministic facts
(affect.goal_slot_currency), the payload reads them back as `goal_reached`
/ `goal_held` (agents/character._annotate_goal_currency), and routing
declines a SPENT claim exactly as it already declines one naming the room
he stands in. The goal text itself is never rewritten or suppressed.

Ordinary non-maze characters, pinned below: a conversation goal names no
room (no reached marker, routing untouched), is rewritten as wants shift
(tenure never accumulates), or serves an intention or project (tenure
suppressed). Database-independent: pure stamp and payload-shape contracts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mind.affect import goal_slot_currency
from agents.character import (_GOAL_HELD_AFTER, _annotate_goal_currency,
                              _destination_from_goals)

NAMED = {"chamber 0206": "r0206", "chamber 0603": "r0603"}


class TestGoalSlotCurrency:
    """The commit-side stamps: pure, total, and word-keyed."""

    def test_an_empty_slot_holds_nothing(self):
        assert goal_slot_currency({}, "", NAMED, "r0001", 10) == {}
        assert goal_slot_currency({}, "   ", NAMED, "r0001", 10) == {}

    def test_a_roomless_goal_is_stamped_with_its_tenure_only(self):
        got = goal_slot_currency({}, "Compare chalk circle patterns "
                                     "across chambers", NAMED, "r0001", 42)
        assert got == {"goal_since": 42}

    def test_the_same_words_carry_the_clock(self):
        prev = {"goal": "Compare chalk circle patterns across chambers",
                "goal_since": 42}
        got = goal_slot_currency(prev, "Compare chalk circle patterns "
                                       "across chambers", NAMED, "r0002", 60)
        assert got["goal_since"] == 42, (
            "verbatim re-emission is not re-authoring; tenure accumulates")

    def test_new_words_restart_the_clock(self):
        prev = {"goal": "Compare chalk circle patterns across chambers",
                "goal_since": 42}
        got = goal_slot_currency(prev, "Map the tally marks instead",
                                 NAMED, "r0002", 60)
        assert got["goal_since"] == 60

    def test_a_room_naming_goal_records_its_room(self):
        got = goal_slot_currency({}, "Run east to Chamber 0206 along the "
                                     "proved line", NAMED, "r0100", 380)
        assert got["goal_room"] == "r0206"
        assert "goal_room_reached" not in got

    def test_standing_in_the_named_room_spends_the_claim(self):
        got = goal_slot_currency({}, "Run east to Chamber 0206 along the "
                                     "proved line", NAMED, "r0206", 381)
        assert got["goal_room_reached"] == 381

    def test_a_spent_claim_stays_spent_while_the_words_stand(self):
        """The live tether shape: he stepped out of Chamber 0206 with the
        goal re-emitted verbatim, and the claim must not spring back to
        life just because he is no longer standing in the room."""
        text = "Run east to Chamber 0206 along the proved line"
        prev = {"goal": text, "goal_since": 380, "goal_room": "r0206",
                "goal_room_reached": 381}
        got = goal_slot_currency(prev, text, NAMED, "r0306", 382)
        assert got["goal_room_reached"] == 381

    def test_dwelling_keeps_the_first_reach(self):
        text = "Run east to Chamber 0206 along the proved line"
        prev = {"goal": text, "goal_since": 380, "goal_room": "r0206",
                "goal_room_reached": 381}
        got = goal_slot_currency(prev, text, NAMED, "r0206", 385)
        assert got["goal_room_reached"] == 381

    def test_a_fresh_return_is_a_new_claim(self):
        """The guard case, protected: 'go back to the kitchen', said in new
        words, must route -- a deliberate return is not inertia, and only
        verbatim re-emission carries the spent stamp."""
        prev = {"goal": "Hold the door of Chamber 0206",
                "goal_since": 380, "goal_room": "r0206",
                "goal_room_reached": 381}
        got = goal_slot_currency(prev, "Go back to Chamber 0206",
                                 NAMED, "r0306", 383)
        assert got["goal_room"] == "r0206"
        assert "goal_room_reached" not in got

    def test_junk_previous_state_is_tolerated(self):
        got = goal_slot_currency(None, "Run east to Chamber 0206",
                                 NAMED, None, 5)
        assert got["goal_room"] == "r0206"
        got = goal_slot_currency({"goal_since": "junk", "goal": "x"},
                                 "x", None, "r1", 5)
        assert got == {"goal_since": 5}


class TestSpentGoalsDoNotRoute:
    """The routing exclusion: a claim the engine can see is spent is not
    evidence of going anywhere. His intentions and projects speak instead,
    exactly as when the goal names the room he stands in."""

    def _pg(self):
        return {"nodes": {"r0206": {"name": "Chamber 0206"},
                          "r0603": {"name": "Chamber 0603"}},
                "edges": {}}

    def _state(self, **active_extra):
        active = {"goal": "Run east to Chamber 0206 along the proved line"}
        active.update(active_extra)
        return {
            "active_state": active,
            "interior": {"projects": [{
                "id": "pa1",
                "project": "Every run through this maze ends at the "
                           "shrine. The shrine is Chamber 0603."}]},
        }

    def test_the_live_tether_shape_routes_to_the_project(self):
        """Turn 384's exact texture: standing one room out of Chamber
        0206 with the goal re-emitted verbatim and spent, the destination
        must be the project's shrine, not the room behind him."""
        dest = _destination_from_goals(
            self._state(goal_room="r0206", goal_room_reached=381),
            self._pg(), here_rid="r0306")
        assert dest == {"rid": "r0603", "name": "Chamber 0603"}

    def test_an_unspent_goal_still_routes_as_before(self):
        dest = _destination_from_goals(self._state(), self._pg(),
                                       here_rid="r0306")
        assert dest["rid"] == "r0206"

    def test_a_fresh_return_routes_back(self):
        """Commit clears the spent stamp when the words change, so a
        deliberately restated return carries no goal_room_reached and the
        old goal-first reading stands."""
        st = self._state()
        st["active_state"]["goal"] = "Go back to Chamber 0206"
        dest = _destination_from_goals(st, self._pg(), here_rid="r0306")
        assert dest["rid"] == "r0206"


class TestGoalCurrencyMarkers:
    """The payload's read-back: facts stated, never a mechanism that acts."""

    NODES = {"r0206": "Chamber 0206", "r0603": "Chamber 0603"}

    def test_a_spent_claim_is_named_as_reached(self):
        got = _annotate_goal_currency(
            {"goal": "Run east to Chamber 0206 along the proved line",
             "goal_since": 380, "goal_room": "r0206",
             "goal_room_reached": 381},
            384, self.NODES)
        assert got["goal_reached"] == {"room": "Chamber 0206",
                                       "beats_ago": 3}

    def test_a_journey_underway_carries_no_marker(self):
        """A room-naming goal not yet reached is healthy continuity --
        en_route owns it, and tenure must not nag the exact persistence
        en_route was built to buy."""
        got = _annotate_goal_currency(
            {"goal": "Walk the proved line to the shrine at Chamber 0603",
             "goal_since": 300, "goal_room": "r0603"},
            340, self.NODES)
        assert "goal_reached" not in got
        assert "goal_held" not in got

    def test_a_roomless_squatter_shows_its_tenure(self):
        """The chalk-circles shape: a room-less claim holding the slot
        past the threshold while serving nothing governed. Tenure rides
        the stamp, so it survives a process restart WITH the goal -- the
        marker is present on the first beat after, which is exactly when
        the slot was measured presenting a dead scene's want as current."""
        got = _annotate_goal_currency(
            {"goal": "Compare chalk circle patterns across chambers",
             "goal_since": 300}, 315, self.NODES)
        assert got["goal_held"] == 15

    def test_under_the_threshold_the_payload_says_nothing(self):
        got = _annotate_goal_currency(
            {"goal": "Compare chalk circle patterns across chambers",
             "goal_since": 300}, 300 + _GOAL_HELD_AFTER - 1, self.NODES)
        assert "goal_held" not in got

    def test_service_of_a_governed_tier_suppresses_tenure(self):
        """A goal that is an intention's or project's instrument is that
        tier's business -- its fading / adrift clocks already burn."""
        got = _annotate_goal_currency(
            {"goal": "Press the interrogation", "goal_since": 300,
             "wants": [{"want": "Press the interrogation",
                        "serves": "i2", "enacted": True}],
             "enacted_want": 0},
            320, self.NODES, governed_ids={"i2", "pa1"})
        assert "goal_held" not in got

    def test_a_self_declared_drive_label_does_not_exempt(self):
        """The live want claimed serves:'drive' -- a model's own label,
        free to emit, and the drive is eternal and placeless: a concrete
        want wearing its name for a dozen beats is precisely the
        project-shaped thing this marker exists to name."""
        got = _annotate_goal_currency(
            {"goal": "Compare chalk circle patterns across chambers",
             "goal_since": 300,
             "wants": [{"want": "Compare chalk circle patterns",
                        "serves": "drive", "enacted": True}],
             "enacted_want": 0},
            320, self.NODES, governed_ids={"i2", "pa1"})
        assert got["goal_held"] == 20

    def test_the_stored_state_is_never_mutated(self):
        active = {"goal": "x", "goal_since": 1}
        _annotate_goal_currency(active, 50, self.NODES)
        assert active == {"goal": "x", "goal_since": 1}

    def test_without_a_turn_nothing_is_said(self):
        active = {"goal": "x", "goal_since": 1,
                  "goal_room": "r0206", "goal_room_reached": 2}
        assert _annotate_goal_currency(active, None, self.NODES) is active

    def test_a_stampless_legacy_state_passes_through(self):
        """Every pre-existing chat: no stamps, no markers, no change."""
        active = {"mood": "wary", "goal": "Keep moving"}
        got = _annotate_goal_currency(active, 100, self.NODES)
        assert got == active
