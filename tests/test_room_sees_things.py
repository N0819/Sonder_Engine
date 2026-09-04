"""The Writers' Room's world model was people and rooms; a thing was write-only.

`PLAN_KINDS` is (person, thing, creature). A thing plan could be FILED and
then never seen again, in four separate places at once:

  * no tool read the scene's entities. `inspect_rooms` returned `occupants`
    from `positions`, which keys bodies, and the reply payload
    (`story_planner._payload`) carries no scene at all -- correctly, on cost
    grounds. So the Room could not ask what stands in a room;
  * `frontier_report` filtered `identities_ahead` to `kind == "person"`, and
    it was the one standing report an unrendered plan surfaced in;
  * `inspect_contradictions` checked `plan_in_no_room` -- does the plan's room
    exist -- but never whether the scene had already put that plan somewhere
    ELSE;
  * `settle_rendered_plans` was reachable only from inside the background
    PRESENCE loop, which excludes every inert kind, so a bound thing stayed
    `rendered: False` for the life of the story and `plans_in_view` went on
    offering it to the Director every time anyone entered the planned room.

Measured live (chat 114). Asked to put the TARDIS somewhere, the Room filed it
for the hibiscus garden at beat 6 -- correctly, on what it could see. The
Director stood the box on the beach at beat 9 with `plan_ref` bound. Nothing
could report the divergence, nothing settled the plan, and the plan still
promises a police box to a garden that has none.

Database-independent: the pure projections, not the tool wrappers that read
a chat row.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from world.planned_entities import plans_in_view, reserved_plans


def _plan(uid="plan:thing:the_tardis:1e1ac4", where="garden", kind="thing",
          rendered=False):
    plan = {"uid": uid, "kind": kind, "name": "The TARDIS",
            "aliases": ["TARDIS"], "role": "Time machine",
            "brief": {"purpose": "", "truths": "", "where": where},
            "look": "A weathered blue police box."}
    if rendered:
        plan["rendered"] = {"turn": 9, "render": "on the sand"}
    return plan


class TestWhyAnUnsettledThingIsDangerous:
    """The cost of the settle gap, stated as the behaviour it produces."""

    def test_an_unrendered_plan_is_offered_to_whoever_enters_its_room(
            self, monkeypatch):
        monkeypatch.setattr("world.planned_entities.planned_entities",
                            lambda *a, **k: {"u": _plan()})
        assert [f["name"] for f in plans_in_view(1, ["garden"])] == ["The TARDIS"]

    def test_a_settled_plan_is_offered_to_nobody(self, monkeypatch):
        """Which is why the settle has to be reachable for a thing: this is
        the only thing standing between one plan and two police boxes."""
        monkeypatch.setattr("world.planned_entities.planned_entities",
                            lambda *a, **k: {"u": _plan(rendered=True)})
        assert plans_in_view(1, ["garden"]) == []
        assert reserved_plans(1) == []

    def test_an_unrendered_plan_stays_reserved_everywhere_else(
            self, monkeypatch):
        monkeypatch.setattr("world.planned_entities.planned_entities",
                            lambda *a, **k: {"u": _plan()})
        assert [f["name"] for f in reserved_plans(1)] == ["The TARDIS"]


class TestTheSettleReachesEveryPlanKind:
    """The gathering loop, in the shape `commit_background` runs it: rows come
    off the beat's entity diff, where the binding actually lives, not off the
    presence sketches, which never see a vehicle."""

    def _gather(self, entities):
        settled, rows = set(), []
        for eid, edef in entities.items():
            ref = edef.get("plan_ref")
            uid = str(ref.get("uid") or "") if isinstance(ref, dict) else ""
            desc = str(edef.get("description") or "").strip()
            if not uid or not desc or uid in settled:
                continue
            settled.add(uid)
            rows.append({"plan": uid, "entity_id": eid, "render": desc})
        return rows

    def test_a_vehicle_bound_to_a_plan_produces_a_settle_row(self):
        rows = self._gather({"tardis": {
            "name": "The TARDIS", "kind": "vehicle",
            "description": "A blue police box on the dark sand.",
            "plan_ref": {"uid": "plan:thing:the_tardis:1e1ac4"}}})
        assert [r["plan"] for r in rows] == ["plan:thing:the_tardis:1e1ac4"]
        assert rows[0]["render"] == "A blue police box on the dark sand."

    def test_an_entity_with_no_plan_produces_nothing(self):
        assert self._gather({"crate": {"name": "Crate", "kind": "object",
                                       "description": "A crate."}}) == []

    def test_a_bound_entity_with_no_description_settles_nothing(self):
        """A render is what was SEEN. There is nothing to settle without one,
        and settling an empty string would spend the once-only write."""
        assert self._gather({"tardis": {
            "name": "The TARDIS", "kind": "vehicle", "description": "",
            "plan_ref": {"uid": "plan:thing:the_tardis:1e1ac4"}}}) == []

    def test_one_plan_settles_once_however_many_entities_claim_it(self):
        rows = self._gather({
            "tardis": {"description": "A blue police box.",
                       "plan_ref": {"uid": "plan:thing:x"}},
            "tardis_2": {"description": "Another blue police box.",
                         "plan_ref": {"uid": "plan:thing:x"}}})
        assert len(rows) == 1
