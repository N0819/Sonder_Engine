"""A planned thing is marked rendered by the commit that stands it up, and a
noise its plan projected goes when the plan stops projecting it.

THE AUDIT (2026-11-01, world_layout_bridge_structure F1, reproduced):
`materialize_plans_in_sight` marked a plan `rendered` in the chat-wide ledger
during commit PREPARATION, before the turn's transaction opened. A domain that
raised afterwards rolled the scene back -- the entity was never stored -- and
left the ledger saying the thing stood: the next beat minted nothing, offered
nothing to the Director, and the thing never existed. The decision is now a
pair: preparation DECIDES (`plans_in_sight` returns the marks it would write
and writes nothing), and the commit writes them inside its transaction
(`mark_plans_rendered`), so a rollback takes the mark back with the scene.

F7, reproduced: `project_planned_emissions` only ever SET a room's `sound`.
A planned generator rendered and switched off went on sounding through its
room for the rest of the story, and a plan moved to another room left the
old one sounding. What the projection laid is recorded on the scene
(`PROJECTED_SOUNDS_KEY`) and taken back where no plan projects it any more and
the room still holds exactly what was laid; a thing the engine stands up
carries the emissions its plan declared, so taking the room's projection back
never silences it. A room's own authored voice is never touched.

Hand-made scenes; the names are illustrations, not the rule.
"""
from __future__ import annotations

import time

import pytest

from world.planned_entities import (PROJECTED_SOUNDS_KEY, add_planned_entity,
                                    mark_plans_rendered,
                                    materialize_plans_in_sight, plans_in_sight,
                                    plans_in_view, planned_entities,
                                    project_planned_emissions, reserved_plans)


@pytest.fixture
def cid(temp_db):
    return temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("A beach", "", time.time()))


def _beach():
    return {"rooms": {"beach": {"name": "Beach", "adjacent": []}},
            "positions": {"Ann": "beach"}, "entities": {}, "stations": {}}


def _box(cid, **over):
    entry = {"kind": "thing", "name": "Police Box", "look": "a tall blue box",
             "brief": {"where": "beach"}}
    entry.update(over)
    return add_planned_entity(cid, entry, turn_idx=0)


class TestTheCommitMarksWhatItStoodUp:
    def test_preparation_decides_and_writes_nothing(self, cid):
        plan = _box(cid)
        scene, minted, marks = plans_in_sight(cid, _beach(), occupied={"beach"},
                                              turn_idx=5)
        assert [m["plan"] for m in minted] == [plan["uid"]]
        assert minted[0]["entity_id"] in scene["entities"]
        assert set(marks) == {plan["uid"]}
        assert marks[plan["uid"]]["by"] == "engine"
        assert "rendered" not in planned_entities(cid)[plan["uid"]]

    def test_a_rolled_back_commit_takes_the_mark_back_with_the_scene(self, cid):
        from core.db import transaction
        plan = _box(cid)
        _scene, _minted, marks = plans_in_sight(cid, _beach(), occupied={"beach"})
        with pytest.raises(RuntimeError):
            with transaction():
                mark_plans_rendered(cid, marks)
                raise RuntimeError("a later commit domain failed")
        assert "rendered" not in planned_entities(cid)[plan["uid"]]
        # ...so the next beat stands it up again, and the Director is still
        # offered it meanwhile
        _scene, again, _marks = plans_in_sight(cid, _beach(), occupied={"beach"})
        assert [m["plan"] for m in again] == [plan["uid"]]
        assert [row["plan"] for row in plans_in_view(cid, ["beach"])] == [plan["uid"]]
        assert [row["plan"] for row in reserved_plans(cid)] == [plan["uid"]]

    def test_the_commit_that_lands_settles_it_once(self, cid):
        from core.db import transaction
        plan = _box(cid)
        scene, _minted, marks = plans_in_sight(cid, _beach(), occupied={"beach"})
        with transaction():
            assert mark_plans_rendered(cid, marks) == [plan["uid"]]
        stored = planned_entities(cid)[plan["uid"]]
        assert stored["rendered"]["by"] == "engine"
        # a second write of the same marks (a reroll's preparation raced it)
        # never overwrites the render that landed
        with transaction():
            assert mark_plans_rendered(cid, {plan["uid"]: dict(
                marks[plan["uid"]], render="something else")}) == []
        assert planned_entities(cid)[plan["uid"]]["rendered"] == stored["rendered"]
        _scene, again, more = plans_in_sight(cid, scene, occupied={"beach"})
        assert again == [] and more == {}

    def test_the_one_call_form_still_settles_for_a_caller_in_a_transaction(self, cid):
        plan = _box(cid)
        _scene, minted = materialize_plans_in_sight(cid, _beach(), occupied={"beach"})
        assert minted and planned_entities(cid)[plan["uid"]]["rendered"]["by"] == "engine"


class TestAProjectedNoiseIsTakenBack:
    def _generator(self, cid, where="plant_room"):
        return add_planned_entity(cid, {
            "kind": "thing", "name": "Generator", "look": "a diesel generator",
            "brief": {"where": where}, "sources": {"sound_source": "loud"}})

    def _plant(self):
        return {"rooms": {"plant_room": {"name": "Plant Room", "adjacent": []},
                          "yard": {"name": "Yard", "adjacent": []}},
                "positions": {}, "entities": {}, "stations": {}}

    def test_rendered_the_room_stops_sounding_and_the_thing_carries_it(self, cid):
        from core.db import transaction
        plan = self._generator(cid)
        scene, projected = project_planned_emissions(cid, self._plant())
        assert projected == [("plant_room", "loud")]
        assert scene["rooms"]["plant_room"]["sound"] == {"level": "loud"}
        # somebody walks in: the engine stands it up, and the commit marks it
        scene["positions"]["Ann"] = "plant_room"
        scene, minted, marks = plans_in_sight(cid, scene, occupied={"plant_room"})
        with transaction():
            mark_plans_rendered(cid, marks)
        entity = scene["entities"][minted[0]["entity_id"]]
        assert entity["sound_source"] == "loud", "the thing makes the noise now"
        scene, projected = project_planned_emissions(cid, scene)
        assert projected == []
        assert "sound" not in scene["rooms"]["plant_room"]
        assert PROJECTED_SOUNDS_KEY not in scene
        # switched off, nothing is heard from the room either
        entity.pop("sound_source")
        scene, _projected = project_planned_emissions(cid, scene)
        assert "sound" not in scene["rooms"]["plant_room"]
        assert plan["uid"] in planned_entities(cid)

    def test_a_plan_moved_elsewhere_leaves_its_old_room_silent(self, cid):
        self._generator(cid, where="plant_room")
        scene, _p = project_planned_emissions(cid, self._plant())
        self._generator(cid, where="yard")      # the same plan, re-placed
        scene, projected = project_planned_emissions(cid, scene)
        assert projected == [("yard", "loud")]
        assert "sound" not in scene["rooms"]["plant_room"]
        assert scene["rooms"]["yard"]["sound"] == {"level": "loud"}

    def test_a_room_s_own_voice_is_never_taken(self, cid):
        """An authored voice carries a detail; one the projection did not lay,
        or one a beat has changed since, is not the projection's to take."""
        self._generator(cid)
        plant = self._plant()
        plant["rooms"]["yard"]["sound"] = {"level": "loud"}
        scene, _p = project_planned_emissions(cid, plant)
        scene["rooms"]["plant_room"]["sound"] = {"level": "quiet",
                                                 "detail": "a tick of cooling metal"}
        add_planned_entity(cid, {"kind": "thing", "name": "Generator",
                                 "brief": {"where": "elsewhere"},
                                 "sources": {"sound_source": "loud"}})
        scene, _p = project_planned_emissions(cid, scene)
        assert scene["rooms"]["plant_room"]["sound"]["detail"] == "a tick of cooling metal"
        assert scene["rooms"]["yard"]["sound"] == {"level": "loud"}
