"""Projects (Tier 1.5): durable-but-not-eternal commitments, capped at two.

The tier between the eternal drive and the completable intention, built
against four measured failures (docs/DESIGN_LONG_TERM_GOALS.md):

- `ia4` ("walk the proved line to the shrine") marked satisfied the beat
  after first arrival -- true once, never steering again. (A13 run 4.)
- A shrine commission decayed dormant after ~150 barren beats the world had
  not withdrawn. The intention rules were right; the tier was wrong. (A12.)
- Aims abandoned along with the tactic that served them. (A13.)
- The standing purpose out-competed every beat at intention weight 0.8
  against drive-serving wants at 1.0. (Three arms.)

The properties pinned here are mostly ABSENCES: no dormancy sweep, no
barren counter, no progress ceiling, no silent eviction. The cap is the
mechanism -- two slots means there is always an answer to "what is this
person about right now", and taking on a third has a price that must be
paid out loud.

Database-independent: pure ledger and payload-shape contracts.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from affect import (PROJECT_CAP, apply_project_ops, normalize_serves,
                    normalize_wants, serves_priority)
from character_schema import character_projects


def _proj(pid, text, satisfied_when=""):
    return {"id": pid, "project": text, "about": "world",
            "satisfied_when": satisfied_when, "adopted_turn": 1}


class TestTheCapIsTheMechanism:

    def test_two_slots_never_more(self):
        live, former, warn = apply_project_ops(
            [_proj("p1", "Master the deep maze"),
             _proj("p2", "Keep the courier commission alive")],
            [], [{"op": "adopt", "project": "Catalogue every shrine symbol"}],
            10)
        assert len(live) == PROJECT_CAP == 2
        assert all("shrine symbol" not in str(p.get("project"))
                   for p in live)
        assert any("both slots full" in w for w in warn)

    def test_displace_and_adopt_land_in_one_beat_in_either_order(self):
        """Closures apply before adoptions whatever order the model emitted:
        the price of the third project is paid and the slot turns over,
        without the model having to know the processing order."""
        for ops in (
            [{"op": "displace", "id": "p1",
              "why": "the maze is mapped; mastery has nothing left to ask"},
             {"op": "adopt", "project": "Catalogue every shrine symbol"}],
            [{"op": "adopt", "project": "Catalogue every shrine symbol"},
             {"op": "displace", "id": "p1",
              "why": "the maze is mapped; mastery has nothing left to ask"}],
        ):
            live, former, warn = apply_project_ops(
                [_proj("p1", "Master the deep maze"),
                 _proj("p2", "Keep the courier commission alive")],
                [], ops, 10)
            texts = [p["project"] for p in live]
            assert "Catalogue every shrine symbol" in texts
            assert "Master the deep maze" not in texts
            assert len(live) == 2

    def test_a_restated_project_is_held_not_readopted(self):
        live, _, warn = apply_project_ops(
            [_proj("p1", "Master the deep maze")], [],
            [{"op": "adopt", "project": "master this deep maze fully"}], 10)
        assert len(live) == 1
        assert any("restates" in w for w in warn)


class TestGivingUpIsALegibleAct:

    def test_displacement_requires_a_stated_reason(self):
        live, former, warn = apply_project_ops(
            [_proj("p1", "Master the deep maze")], [],
            [{"op": "displace", "id": "p1"}], 10)
        assert len(live) == 1, "silent eviction is the thing this forbids"
        assert former == []
        assert any("stated reason" in w for w in warn)

    def test_the_reason_and_the_turn_survive_in_the_ledger(self):
        """Displacement is the one self-revision the engine supports -- the
        record of it is continuity, like former_drives."""
        live, former, _ = apply_project_ops(
            [_proj("p1", "Master the deep maze")], [],
            [{"op": "displace", "id": "p1",
              "why": "I am done proving things to the maze"}], 42)
        assert live == []
        assert former == [{
            "id": "p1", "project": "Master the deep maze",
            "why": "I am done proving things to the maze",
            "turn": 42, "end": "displaced"}]


class TestNotDischargedByOneInstance:

    def test_satisfy_needs_the_projects_own_criterion(self):
        """'Reach the shrine' satisfied on first arrival was the measured
        failure: a project with no satisfied_when is not completable at all
        -- it re-arms at every occasion by construction."""
        live, former, warn = apply_project_ops(
            [_proj("p1", "Every run I make ends at the shrine")], [],
            [{"op": "satisfy", "id": "p1",
              "why": "I reached the shrine this run"}], 10)
        assert len(live) == 1, "one arrival must not close a life's work"
        assert any("not completable" in w for w in warn)

    def test_a_met_criterion_closes_it_with_the_reason(self):
        live, former, _ = apply_project_ops(
            [_proj("p1", "Serve the commission",
                   satisfied_when="the commission is withdrawn")],
            [], [{"op": "satisfy", "id": "p1",
                  "why": "the courier guild recalled the commission"}], 10)
        assert live == []
        assert former[0]["end"] == "satisfied"
        assert former[0]["why"] == "the courier guild recalled the commission"

    def test_satisfy_still_needs_a_why(self):
        live, _, warn = apply_project_ops(
            [_proj("p1", "Serve the commission",
                   satisfied_when="the commission is withdrawn")],
            [], [{"op": "satisfy", "id": "p1"}], 10)
        assert len(live) == 1
        assert any("stated reason" in w for w in warn)


class TestTolerantOfBarrenStretches:

    def test_no_ops_across_two_hundred_turns_changes_nothing(self):
        """The property is an absence: no dormancy sweep, no stall counter,
        no decay. A hundred beats of nothing is a normal week inside a
        project -- contrast apply_intent_ops, which correctly spends an
        untouched intention at 30."""
        projects = [_proj("p1", "Every run I make ends at the shrine")]
        for turn in (10, 60, 110, 210):
            projects, former, warn = apply_project_ops(projects, [], [], turn)
            assert warn == []
        assert projects == [_proj("p1",
                                  "Every run I make ends at the shrine")]


class TestNotAnEntryInTheBeatAuction:

    def test_a_project_serving_want_weighs_like_a_drive_serving_one(self):
        """The measured loss: the shrine at 0.8 against drive wants at 1.0,
        every time, in three arms. A held project scores at drive weight;
        the scarcity cap is what makes that weight safe to grant."""
        assert serves_priority("p1", set(), {"p1"}) == 1.0
        assert serves_priority("drive", set(), {"p1"}) == 1.0
        assert serves_priority("i2", {"i2"}, {"p1"}) == 0.8
        assert serves_priority("i9", {"i2"}, {"p1"}) == 0.4

    def test_a_want_may_serve_a_project_without_demotion(self):
        wants, enacted, _ = normalize_wants(
            [{"want": "Walk the proved line to the shrine",
              "urgency": 0.9, "serves": "p1"}],
            {"i1", "p1"})
        assert wants[0]["serves"] == "p1", (
            "serves resolving to situational is the silent demotion that "
            "made the commission lose")

    def test_serves_prefix_resolves_to_the_project_id(self):
        projects = [_proj("p1", "Every run I make ends at the shrine")]
        assert normalize_serves("project:p1", [], projects) == "p1"
        assert normalize_serves(
            "project:every run ends at the shrine", [], projects) == "p1"
        assert normalize_serves("intention:i2",
                                [{"id": "i2", "intent": "x"}],
                                projects) == "i2"


class TestAuthoredProjects:

    def test_a_card_may_author_them_in_either_shape(self):
        sheet = {"identity": {"name": "Orrin"}, "psychology": {"projects": [
            "Every run I make ends at the shrine",
            {"project": "Understand what the maze is for",
             "about": "self", "satisfied_when": "the question stops asking"},
        ]}}
        got = character_projects(sheet)
        assert [p["id"] for p in got] == ["pa1", "pa2"]
        assert got[0]["project"] == "Every run I make ends at the shrine"
        assert got[1]["about"] == "self"
        assert got[1]["satisfied_when"] == "the question stops asking"
        assert all(p["authored"] for p in got)

    def test_the_authoring_cap_matches_the_runtime_cap(self):
        sheet = {"identity": {"name": "T"}, "psychology": {"projects": [
            "one", "two", "three"]}}
        assert len(character_projects(sheet)) == PROJECT_CAP

    def test_a_card_without_any_authors_none(self):
        assert character_projects({"identity": {"name": "T"}}) == []


class TestDecayIsReasonedNotSilent:
    """The sweep is right; its silence was the defect. A courier walked
    sixteen optimal rooms to the shrine's threshold and turned away because
    the goal underneath had been spent by a sweep he was never party to
    (A11/A12). The fuse is now visible while it burns: the character can
    renew, revise, or abandon with a stated reason, and the sweep remains
    only as the backstop for an unanswered question."""

    def _fading(self, intent, now_turn=100):
        from agents.character import _annotate_fading
        return _annotate_fading([intent], now_turn)[0]

    def test_an_idle_active_intention_shows_its_burning_fuse(self):
        got = self._fading({"id": "i1", "status": "active",
                            "last_progress_turn": 75})
        assert got["fading"] == 25

    def test_a_recently_progressed_intention_is_not_nagged(self):
        got = self._fading({"id": "i1", "status": "active",
                            "last_progress_turn": 95})
        assert "fading" not in got

    def test_only_active_rows_carry_the_question(self):
        got = self._fading({"id": "i1", "status": "dormant",
                            "last_progress_turn": 10})
        assert "fading" not in got, "already swept -- nothing left to answer"

    def test_the_stored_rows_are_never_mutated(self):
        """Read-side only: a payload annotation, not a new lifecycle."""
        from agents.character import _annotate_fading
        row = {"id": "i1", "status": "active", "last_progress_turn": 10}
        _annotate_fading([row], 100)
        assert "fading" not in row

    def test_the_fuse_shows_before_the_sweep_fires(self):
        """The whole point: the question reaches the character while there
        is still time to answer it."""
        from affect import INTENT_DORMANT_AFTER
        from agents.character import _FADING_AFTER
        assert _FADING_AFTER < INTENT_DORMANT_AFTER


class TestAProjectNamesADestination:

    def test_the_durable_fallback_routes_when_everything_else_died(self):
        """The A12/A13 hole on the routing side: goal thrashy, every
        intention naming the aim satisfied-once or decayed -- a held
        project naming a room still routes."""
        from agents.character import _destination_from_goals
        state = {
            "active_state": {"goal": "Keep moving"},
            "interior": {
                "intentions": [
                    {"id": "ia4", "status": "satisfied", "progress": 1.0,
                     "intent": "Reach the shrine at Chamber 0603"},
                ],
                "projects": [_proj(
                    "p1", "Every run I make ends at the shrine "
                          "in Chamber 0603")],
            },
        }
        pg = {"nodes": {"rD": {"basis": "walked", "name": "Chamber 0603"}},
              "edges": {}}
        dest = _destination_from_goals(state, pg)
        assert dest == {"rid": "rD", "name": "Chamber 0603"}

    def test_the_beat_goal_still_outranks_the_project(self):
        """A project is what he is about, not necessarily where he is going
        THIS beat: a goal that names a room keeps the wheel."""
        from agents.character import _destination_from_goals
        state = {
            "active_state": {"goal": "Carry the wounded man to Chamber 0100"},
            "interior": {"projects": [_proj(
                "p1", "Every run I make ends at the shrine "
                      "in Chamber 0603")]},
        }
        pg = {"nodes": {"rD": {"basis": "walked", "name": "Chamber 0603"},
                        "rH": {"basis": "walked", "name": "Chamber 0100"}},
              "edges": {}}
        assert _destination_from_goals(state, pg)["rid"] == "rH"


class TestAMutatedProjectIsNotReseeded:
    """A project's wording can legitimately change after adoption -- the maze
    harness appends the goal room's name the beat the character first stands
    in it, which is the moment that identifier becomes legitimately his. A
    text-keyed seeding check then stops recognising the authored source and
    seeds a second copy.

    Measured live: `pa1` held twice, one project occupying both slots, which
    defeats the cap that is the entire point of the tier.
    """

    def test_the_authored_id_is_what_makes_it_the_same_project(self):
        from character_schema import character_projects, default_character_data
        sheet = default_character_data("Someone")
        sheet.setdefault("psychology", {})["projects"] = [
            {"project": "Every run ends at the shrine.", "about": "world"}]
        authored = character_projects(sheet)
        assert authored and authored[0]["id"] == "pa1"

        # adopted, then its wording grew -- the same project, still pa1
        live = [dict(authored[0],
                     project="Every run ends at the shrine. It is Chamber 0603.")]
        seen_ids = {str(p.get("id") or "") for p in live}
        seeded = [p for p in authored
                  if str(p.get("id") or "") not in seen_ids]
        assert seeded == [], (
            "an authored project already held must not seed again just "
            "because its text has moved on")
