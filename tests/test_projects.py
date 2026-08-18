"""Projects (Tier 1.5): durable-but-not-eternal commitments, capped at two.

The tier between the eternal drive and the completable intention, built
against four measured failures (docs/design/DESIGN_LONG_TERM_GOALS.md):

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

from mind.affect import (PROJECT_CAP, apply_project_ops, normalize_serves,
                    normalize_wants, project_boundary,
                    projects_served_this_beat, serves_priority)
from story.character_schema import character_projects


def _proj(pid, text, satisfied_when=""):
    return {"id": pid, "project": text, "about": "world",
            "satisfied_when": satisfied_when, "adopted_turn": 1}


class TestTheCapIsTheMechanism:

    def test_two_slots_never_more(self):
        live, former, warn = apply_project_ops(
            [_proj("p1", "Master the deep maze"),
             _proj("p2", "Keep the courier commission alive")],
            [], [{"op": "adopt", "project": "Catalogue every shrine symbol",
                  "satisfied_when": "the keepers publish the record"}],
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
             {"op": "adopt", "project": "Catalogue every shrine symbol",
              "satisfied_when": "the keepers publish the record"}],
            [{"op": "adopt", "project": "Catalogue every shrine symbol",
              "satisfied_when": "the keepers publish the record"},
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
        from mind.affect import INTENT_DORMANT_AFTER
        from agents.character import _FADING_AFTER
        assert _FADING_AFTER < INTENT_DORMANT_AFTER


class TestAdoptionIsADeliberation:
    """'Can they reliably deliberate this is worthy as a project?' -- made
    mechanical. satisfied_when IS the deliberation: state what would end
    this OTHER than doing it once. The discriminator was measured before
    being trusted: circular/task criteria restate their project text
    (similarity 0.5-0.75), genuine external conditions do not
    (0.125-0.25). What the gate cannot catch -- an insincere but external
    criterion -- is what probation is for."""

    def _adopt(self, project, satisfied_when=None):
        op = {"op": "adopt", "project": project}
        if satisfied_when is not None:
            op["satisfied_when"] = satisfied_when
        return apply_project_ops([], [], [op], 10)

    def test_no_criterion_no_project(self):
        """The chalk-circle shape: a bare fascination, adopted. Refused --
        the articulation the op forces is the deliberation."""
        live, _, warn = self._adopt(
            "Understand the symbolic sequence running through this maze")
        assert live == []
        assert any("deliberation" in w for w in warn)

    def test_a_circular_criterion_is_a_task_pretending(self):
        live, _, warn = self._adopt(
            "Understand the symbolic sequence running through this maze",
            "when I understand the symbolic sequence")
        assert live == []
        assert any("circular" in w for w in warn)

    def test_fetch_the_physician_is_caught_as_what_it_is(self):
        """Nathan's framing, verbatim: a task's completion restates the
        task, so the same gate refuses it the tier."""
        live, _, warn = self._adopt("Fetch the physician",
                                    "the physician is here")
        assert live == []
        assert any("circular" in w for w in warn)

    def test_an_external_end_is_a_real_project(self):
        for project, crit in (
            ("Keep this village alive through the winter",
             "spring comes and the village still stands"),
            ("Understand the symbolic sequence running through this maze",
             "the keepers confirm the sequence's purpose, or the maze "
             "is decommissioned"),
        ):
            live, _, warn = self._adopt(project, crit)
            assert len(live) == 1, (project, warn)

    def test_authored_projects_are_exempt(self):
        """The author's deliberation already happened; a card needs no
        gate. This is also what keeps the live pa1 untouched."""
        sheet = {"identity": {"name": "T"}, "psychology": {"projects": [
            "Every run I make ends at the shrine"]}}
        got = character_projects(sheet)
        assert len(got) == 1
        assert "probation" not in got[0]


class TestTimeFiltersInsteadOfJudgement:
    """Probation: nobody knows on day one that something is their life's
    work. A runtime adoption weighs as an intention until SERVICE
    establishes it -- never survival, because the measured failure mode of
    this tier is inattention, and establishment by surviving ignored
    boundary reviews would make the pathology permanent. What probation
    buys over an intention: barren tolerance to the lapse fuse, slot
    scarcity, drift visibility, review invitations, and the path to drive
    weight."""

    def _adopted(self, turn=10, **over):
        live, _, _ = apply_project_ops(
            [], [], [{"op": "adopt", "project": "Learn the low passages",
                      "satisfied_when": "the guild grants the survey "
                                        "seal"}], turn)
        live[0].update(over)
        return live

    def test_adoption_starts_on_probation_at_intention_weight(self):
        from mind.affect import settle_probation
        live = self._adopted()
        assert live[0]["probation"] is True
        assert serves_priority(live[0]["id"], set(), set(),
                               {live[0]["id"]}) == 0.8

    def test_service_plus_time_establishes(self):
        from mind.affect import settle_probation
        live = self._adopted(served_beats=3, last_served_turn=22)
        live, former, warn = settle_probation(live, [], 22)
        assert "probation" not in live[0]
        assert any("established" in w for w in warn)

    def test_service_alone_does_not_establish_a_same_day_enthusiasm(self):
        from mind.affect import settle_probation
        live = self._adopted(served_beats=3, last_served_turn=13)
        live, _, warn = settle_probation(live, [], 13)
        assert live[0].get("probation") is True

    def test_age_alone_is_establishment_by_neglect_and_refused(self):
        from mind.affect import settle_probation
        live = self._adopted(served_beats=2, last_served_turn=30)
        live, _, _ = settle_probation(live, [], 30)
        assert live[0].get("probation") is True

    def test_an_unserved_probationary_project_lapses_quietly(self):
        """The chalk-circle counterfactual: adopted, then never served --
        it leaves without ceremony, recorded, freeing the slot."""
        from mind.affect import settle_probation
        live = self._adopted(served_beats=1, last_served_turn=10)
        live, former, warn = settle_probation(live, [], 34)
        assert live == []
        assert former[0]["end"] == "lapsed"
        assert "unserved for 24 beats" in former[0]["why"]

    def test_an_established_project_never_lapses(self):
        """The stated-reason floor stays where it matters: on projects a
        character has actually lived by. Only displacement or its own
        criterion ends one -- however long unserved."""
        from mind.affect import settle_probation
        held = [dict(_proj("pa1", "Every run ends at the shrine"),
                     last_served_turn=10)]
        live, former, warn = settle_probation(held, [], 500)
        assert len(live) == 1 and former == [] and warn == []


class TestServingIsObservable:
    """A15 run 5: pa1 held at weight 1.0 while, twenty beats in, nothing
    emitted served it. The tier stopped failing by being outranked and
    started failing by being FORGOTTEN. This ledger is what the drift
    marker reads: which projects this beat's declared interior actually
    served, by explicit `serves` or by the goal naming the project's own
    destination."""

    PROJECTS = [_proj("pa1", "Every run I make ends at the shrine "
                             "in Chamber 0603")]
    NAMED = {"chamber 0603": "rD", "chamber 0402": "rQ"}

    def test_an_explicit_want_serves(self):
        got = projects_served_this_beat(
            self.PROJECTS,
            [{"want": "push on", "serves": "pa1"}], "", (), self.NAMED)
        assert got == {"pa1"}

    def test_a_goal_naming_the_projects_room_serves_in_substance(self):
        """'Move west along proven route toward Chamber 0603' never says
        pa1 -- and is service. Text similarity was measured and rejected:
        it scored the chalk-circle detour above this."""
        got = projects_served_this_beat(
            self.PROJECTS, [],
            "Move west along proven route toward Chamber 0603",
            (), self.NAMED)
        assert got == {"pa1"}

    def test_the_drift_goal_does_not_serve(self):
        """The measured drift shapes, verbatim from the run-5 trace."""
        for goal in ("Test connectivity by taking the east turn",
                     "Reorient and test connectivity via available exits",
                     "Investigate chalk circle in Chamber 0402"):
            assert projects_served_this_beat(
                self.PROJECTS, [], goal, (), self.NAMED) == set()

    def test_an_impact_serves(self):
        got = projects_served_this_beat(
            self.PROJECTS, [], "", ("pa1",), self.NAMED)
        assert got == {"pa1"}

    def test_a_want_prefixed_project_id_is_not_demoted(self):
        """The same silent demotion normalize_serves fixes for impacts
        existed in normalize_wants: serves 'project:pa1' became
        situational, and the ledger read a serving beat as drift."""
        wants, _, _ = normalize_wants(
            [{"want": "walk the line", "urgency": 0.8,
              "serves": "project:pa1"}], {"pa1"})
        assert wants[0]["serves"] == "pa1"
        wants, _, _ = normalize_wants(
            [{"want": "press the theory", "urgency": 0.8,
              "serves": "intention:i2"}], {"i2"})
        assert wants[0]["serves"] == "i2"


class TestDriftIsLegible:
    """The gap between HOLDING a project and SERVING it was invisible: the
    project sat in the payload as a static string the character stopped
    referring to. Same move as `fading` and en_route's closer/further:
    state the fact, never force the behaviour."""

    def _adrift(self, project, now_turn=100):
        from agents.character import _annotate_project_drift
        return _annotate_project_drift([project], now_turn)[0]

    def test_an_unserved_project_shows_its_distance(self):
        got = self._adrift(dict(_proj("pa1", "x"), last_served_turn=90))
        assert got["adrift"] == 10

    def test_a_recently_served_project_is_not_nagged(self):
        """The resident clause: a project may REST while the scene demands
        other things -- under the threshold the payload says nothing."""
        got = self._adrift(dict(_proj("pa1", "x"), last_served_turn=95))
        assert "adrift" not in got

    def test_a_project_with_no_ledger_yet_is_silent(self):
        """Authored, pre-first-commit: absent means cannot tell."""
        got = self._adrift(_proj("pa1", "x"))
        assert "adrift" not in got

    def test_the_stored_rows_are_never_mutated(self):
        from agents.character import _annotate_project_drift
        row = dict(_proj("pa1", "x"), last_served_turn=10)
        _annotate_project_drift([row], 100)
        assert "adrift" not in row

    def test_adoption_and_seeding_start_the_clock_at_now(self):
        """A fresh commitment must not read as instantly adrift."""
        live, _, _ = apply_project_ops(
            [], [], [{"op": "adopt", "project": "Learn the low passages",
                      "satisfied_when": "the guild grants the survey seal"}],
            50)
        assert live[0]["last_served_turn"] == 50


class TestBoundariesTheEngineCanActuallySee:
    """v1 left review prompt-normative and it did not hold. These are the
    detectable boundaries, each honest -- and 'run end' and 'major event'
    are deliberately absent, because the engine has no row for either."""

    PROJECTS = [_proj("pa1", "Every run I make ends at the shrine "
                             "in Chamber 0603")]
    NAMED = {"chamber 0603": "rD"}

    def _why(self, **kw):
        args = dict(projects=self.PROJECTS, intentions=[], before_status={},
                    new_room=None, prev_room=None, scene_marker=None,
                    location="The maze", frame_id="f1",
                    named_rooms=self.NAMED)
        args.update(kw)
        return project_boundary(**args)

    def test_arrival_where_the_project_points(self):
        why = self._why(new_room="rD", prev_room="rC")
        assert "arrived" in why and "pa1" in why

    def test_standing_on_is_not_arriving_again(self):
        assert self._why(new_room="rD", prev_room="rD") is None

    def test_a_task_closing_is_a_boundary(self):
        why = self._why(
            intentions=[{"id": "i3", "status": "satisfied"}],
            before_status={"i3": "active"})
        assert "task i3 closed" in why

    def test_an_already_closed_task_is_not_a_boundary_again(self):
        assert self._why(
            intentions=[{"id": "i3", "status": "satisfied"}],
            before_status={"i3": "satisfied"}) is None

    def test_the_scene_changing_is_a_boundary(self):
        why = self._why(scene_marker={"location": "The maze",
                                      "frame": "f1"},
                        location="The Lantern inn")
        assert "scene has changed" in why

    def test_the_frame_changing_is_a_boundary(self):
        why = self._why(scene_marker={"location": "The maze",
                                      "frame": "f1"}, frame_id="f2")
        assert "frame has changed" in why

    def test_no_marker_is_silence_not_a_boundary(self):
        """First beat: nothing to compare against, nothing fires."""
        assert self._why(scene_marker=None) is None

    def test_no_projects_no_review(self):
        assert self._why(projects=[], new_room="rD",
                         prev_room="rC") is None


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
        from story.character_schema import character_projects, default_character_data
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
