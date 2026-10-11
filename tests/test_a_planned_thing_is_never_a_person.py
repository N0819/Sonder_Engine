"""A PLANNED THING IS NEVER A FIGURE OR A PERSON.

O16/O21/O30 of the Cwm Du run (chat 167, turns 4623-4631). The Writers'
Room planned "Gallery Nine timbering" -- a thing, `kind: "thing"` -- in the
gallery the player walked into, and four readers took it for somebody:

- the interpret Director's identity index listed it as a handle and the
  world index listed it among the room's figures, so the beat aimed at it as
  a body;
- the encoder minted it under the plan's exact name and look but no `kind`,
  and the binding floor, finding no kind, searched the people, so the mint
  never bound to its plan;
- the presence harvest filed the placed kindless record a person, and the
  speech verdict read "no kind" as "person", so it spoke and stood in a
  mind's view;
- and the harvest judged the beat's PATCH of a record before the merged
  record, so the gate post lamp, whose patch carried only its name and state,
  was filed a presence too (turn 4626).
"""

from __future__ import annotations

import json
import time

from agents import director_prose
from agents.director import (_bind_minted_entities_to_present_figures,
                             _figure_identities, causal_world_index)
from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import presence_name_items, track_background_presences
from story.character_schema import default_character_data
from world.planned_entities import (add_planned_entity, materialize_plans_in_sight,
                                    planned_entities, plans_in_view)

TIMBER = {"name": "Gallery Nine timbering", "room": "gallery_nine",
          "kind": "thing", "plan": "plan:thing:gallery_nine_timbering",
          "look": "old props dark with damp, one split",
          "brief": {"purpose": "the roof over the gallery is failing"}}
FFION = {"name": "Ffion Rees", "room": "gallery_nine", "kind": "person",
         "plan": "plan:person:ffion_rees"}
HAULIER = {"name": "Dai Haulier", "room": "gallery_nine", "role": "haulier",
           "charter": "colliery", "body": "hand_0"}


class TestItIsListedToBeRendered:
    def test_a_planned_thing_is_no_identity_handle(self):
        assert _figure_identities([TIMBER, FFION, HAULIER]) == {
            "Ffion Rees": "Ffion Rees", "Dai Haulier": "Dai Haulier"}
        index = director_prose.identities_with_figures(
            {"identity_index": {"persona:22": "Nell Hartley"},
             "present_figures": [TIMBER, FFION]})
        assert index == {"persona:22": "Nell Hartley", "Ffion Rees": "Ffion Rees"}

    def test_the_world_index_holds_it_as_a_thing_with_its_plan(self):
        sc = {"rooms": {"gallery_nine": {"name": "Gallery Nine", "adjacent": []}},
              "positions": {"Nell Hartley": "gallery_nine"}, "entities": {}}
        index = causal_world_index(sc, room_ids=["gallery_nine"],
                                   figures=[TIMBER, FFION])
        held = {row["id"]: row for row in index["rooms"]["gallery_nine"]["holds"]}
        assert held["Gallery Nine timbering"]["kind"] == "thing"
        assert held["Gallery Nine timbering"]["plan"] == TIMBER["plan"]
        assert held["Gallery Nine timbering"]["look"] == TIMBER["look"]
        assert held["Ffion Rees"]["kind"] == "figure"


class TestAKindlessMintNamedAsItIsIt:
    SCENE = {"rooms": {"gallery_nine": {"name": "Gallery Nine"}},
             "positions": {}, "entities": {}}

    def _mint(self, name, **fields):
        return {"entities": {"minted": {"name": name, **fields}},
                "positions": {name: "gallery_nine"}}

    def test_the_live_mint_binds_to_its_plan(self):
        """Turn 4624: the plan's exact name and look, and no kind."""
        diff = self._mint("Gallery Nine timbering",
                          description="Old props, dark with damp, one split.")
        _bind_minted_entities_to_present_figures(
            self.SCENE, diff, [TIMBER, FFION], fallback_room="gallery_nine")
        ent = diff["entities"]["minted"]
        assert ent["plan_ref"] == {"uid": TIMBER["plan"]}
        assert ent["kind"] == "object"

    def test_a_planned_thing_standing_elsewhere_binds_by_name_too(self):
        diff = self._mint("Gallery Nine timbering")
        _bind_minted_entities_to_present_figures(
            self.SCENE, diff, [FFION, {**TIMBER, "room": "gallery_eight",
                                       "reserved": True}],
            fallback_room="gallery_nine")
        assert diff["entities"]["minted"]["plan_ref"] == {"uid": TIMBER["plan"]}

    def test_a_kind_the_mint_states_is_kept(self):
        diff = self._mint("Gallery Nine timbering", kind="timber props")
        _bind_minted_entities_to_present_figures(
            self.SCENE, diff, [TIMBER], fallback_room="gallery_nine")
        ent = diff["entities"]["minted"]
        assert ent["plan_ref"] == {"uid": TIMBER["plan"]}
        assert ent["kind"] == "timber props"

    def test_a_kindless_mint_no_thing_plan_answers_to_is_left_alone(self):
        diff = self._mint("a stranger in a donkey jacket")
        _bind_minted_entities_to_present_figures(
            self.SCENE, diff, [TIMBER, FFION], fallback_room="gallery_nine")
        ent = diff["entities"]["minted"]
        assert "kind" not in ent and "plan_ref" not in ent

    def test_a_name_a_person_answers_to_as_well_is_no_thing(self):
        """Two plans answering one name is no ground to call it a thing."""
        diff = self._mint("Ffion Rees")
        _bind_minted_entities_to_present_figures(
            self.SCENE, diff, [{**TIMBER, "name": "Ffion Rees"}, FFION],
            fallback_room="gallery_nine")
        ent = diff["entities"]["minted"]
        assert ent.get("kind") != "object"
        assert ent.get("plan_ref") == {"uid": FFION["plan"]}


_UID = [0]


def _ctx(temp_db, scene, diff):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Cwm Du", "", time.time()))
    _UID[0] += 1
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Ffion Rees", json.dumps(default_character_data("Ffion Rees")), "{}",
         time.time(), "char_ffion_%d" % _UID[0]))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "Cwm Du colliery", "time": "night", "attire": {},
        "overlays": {}, **scene})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 9, "look up", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Cwm Du", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=9,
                      player_input="look up", created=time.time()),
        cast=cast, input="look up")
    ctx.director_resolve = {"resolved_event": "The props creak overhead.",
                            "dialogue_log": [], "state_diff": diff}
    return ctx


def _tracked(temp_db, ctx):
    track_background_presences(ctx, nonce=0)
    return {n for n, _ in presence_name_items(
        temp_db.wget(ctx.chat.id, "background_presences", {}))}


ROOMS = {"gallery_nine": {"name": "Gallery Nine", "adjacent": []}}


class TestTheHarvestFilesSomebodyOnly:
    def test_a_placed_record_that_states_no_kind_is_not_filed_a_person(self, temp_db):
        """Turns 4624-4631: the kindless timbering, placed, was filed a
        presence that spoke and stood in a mind's view."""
        record = {"name": "Gallery Nine timbering",
                  "description": "Old props, dark with damp, one split."}
        ctx = _ctx(temp_db, {
            "rooms": ROOMS, "entities": {"gallery_nine_timbering": record},
            "positions": {"gallery_nine_timbering": "gallery_nine",
                          "Ffion Rees": "gallery_nine"}},
            {"entities": {"gallery_nine_timbering": dict(record)},
             "positions": {"gallery_nine_timbering": "gallery_nine"}})
        assert "Gallery Nine timbering" not in _tracked(temp_db, ctx)

    def test_the_merged_record_judges_a_placed_thing_not_the_beats_patch(self, temp_db):
        """Turn 4626: the beat's patch carried the lamp's name and state
        alone; the record it merged into says lamp, portable."""
        ctx = _ctx(temp_db, {
            "rooms": ROOMS,
            "entities": {"gate_post_lamp": {
                "name": "gate post lamp", "kind": "lamp", "portable": True,
                "state": {"lit": True, "shielded": "shawl"}}},
            "positions": {"gate_post_lamp": "gallery_nine",
                          "Ffion Rees": "gallery_nine"}},
            {"entities": {"gate_post_lamp": {
                "name": "gate post lamp", "from_event": 2,
                "state": {"lit": True, "shielded": "shawl",
                          "pointed_at": "floor"}}},
             "positions": {"gate_post_lamp": "gallery_nine"}})
        assert "gate post lamp" not in _tracked(temp_db, ctx)

    def test_a_placed_body_with_no_record_is_still_somebody(self, temp_db):
        """The trade the positions path exists for (chat 72's night clerk):
        a bare placed name has nothing to judge it on and stays a person."""
        ctx = _ctx(temp_db, {
            "rooms": ROOMS, "entities": {},
            "positions": {"Ffion Rees": "gallery_nine"}},
            {"positions": {"Old Collier": "gallery_nine"}})
        assert "Old Collier" in _tracked(temp_db, ctx)


class TestABoundThingSettlesItsPlan:
    """The other half of the binding: before it, a thing plan was settled
    only through the presence ledger's PERSON loop, so a thing the floor
    bound stayed unrendered and was offered for rendering every beat beside
    the record the scene already held for it."""

    def _plan(self, temp_db, **over):
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Cwm Du", "", time.time()))
        entry = {"kind": "thing", "name": "Gallery Nine timbering",
                 "look": "Old props, dark with damp.",
                 "brief": {"where": "gallery_nine",
                           "purpose": "the roof over the gallery is failing"}}
        entry.update(over)
        return cid, add_planned_entity(cid, entry, turn_idx=0)

    def _scene(self, record):
        return {"rooms": ROOMS, "entities": {"timber": record},
                "positions": {"Nell Hartley": "gallery_nine",
                              "timber": "gallery_nine"},
                "stations": {}, "contained": {}, "contacts": []}

    def test_the_directors_bound_render_settles_the_plan_once(self, temp_db):
        cid, plan = self._plan(temp_db)
        scene, minted = materialize_plans_in_sight(
            cid, self._scene({"name": "Gallery Nine timbering", "kind": "object",
                              "description": "Old props, dark with damp, one split.",
                              "plan_ref": {"uid": plan["uid"]}}),
            occupied={"gallery_nine"}, turn_idx=12)
        assert minted == [] and list(scene["entities"]) == ["timber"]
        rendered = planned_entities(cid)[plan["uid"]]["rendered"]
        assert (rendered["entity_id"], rendered["turn"], rendered["render"]) == (
            "timber", 12, "Old props, dark with damp, one split.")
        assert "by" not in rendered
        assert plans_in_view(cid, {"gallery_nine"}) == []

    def test_a_bound_person_is_left_to_the_presence_ledger(self, temp_db):
        cid, plan = self._plan(temp_db, kind="person", name="Ffion Rees")
        materialize_plans_in_sight(
            cid, self._scene({"name": "Ffion Rees", "kind": "person",
                              "plan_ref": {"uid": plan["uid"]}}),
            occupied={"gallery_nine"}, turn_idx=12)
        assert "rendered" not in planned_entities(cid)[plan["uid"]]

    def test_a_name_the_scene_merely_shares_settles_nothing(self, temp_db):
        cid, plan = self._plan(temp_db)
        scene, minted = materialize_plans_in_sight(
            cid, self._scene({"name": "Gallery Nine timbering", "kind": "object"}),
            occupied={"gallery_nine"}, turn_idx=12)
        assert minted == []
        assert "rendered" not in planned_entities(cid)[plan["uid"]]
