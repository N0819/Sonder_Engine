"""What a beat writes down about who has what.

Three findings from the campaign-3 play runs of 2026-09-05, all in the seam
between a possession the fiction asserts and the ledger that would make it
true next beat.

* **PS3 / PX25** (Salt Terraces turn 2; the masque turns 15 and 18). A posture
  that MEANS carried is not a carriage record. The committed positions after
  the player walked five steps carrying everything were
  `{Mireille: upper_terrace_rim, brass_hand_lamp: haul_road_head, canteen:
  haul_road_head, folding_rule: haul_road_head}`; by turn 10 her possessions
  were spread over three rooms while the narrator went on using all of them,
  and the folding rule was still on the revetment stair at the end of the
  story. The masque left a pair of shoes in the passage their owner carried
  them out of.
* **PR9** (Vaunt's Yard turn 13). `mirela_box` had stood at `third_landing`
  since turn 8 and the body named as its source was a floor below it; the
  transfer committed anyway, and the box changed hands from somebody who did
  not have it.
* **PM16** (Vaunt's Yard turn 1). The Director minted `tally_boards` and moved
  them OUT of `tally_satchel` in the same diff; the alias overlap folded the
  boards into the satchel, so the transfer had nowhere to land and
  `scene.contained` was `{}` after twenty beats.
"""

from __future__ import annotations

import time

from persist import commit
from world.spatial import derive_contained_positions
from core.pipeline_context import ChatData, PipelineContext, TurnData


def _ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Possessions", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 3, "", time.time()))
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Possessions", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=3, player_input="",
                      created=time.time()),
        cast=[], input="")


def _kit_scene():
    """One body on the haul road with her kit, recorded three ways -- and a
    ladder she is holding on to, which is not hers to take."""
    return {
        "rooms": {"haul_road_head": {"name": "Haul Road Head"},
                  "upper_terrace_rim": {"name": "Upper Terrace Rim"}},
        "positions": {"Mireille Adjani": "haul_road_head",
                      "brass_hand_lamp": "haul_road_head",
                      "folding_rule": "haul_road_head",
                      "survey_staff": "haul_road_head",
                      "iron_ladder": "haul_road_head"},
        "attire": {"Mireille Adjani": {"wearing": ["a canvas coat"]}},
        "entities": {
            "Mireille Adjani": {"name": "Mireille Adjani", "kind": "person",
                                "state": {"held_items": ["brass_hand_lamp"]}},
            "brass_hand_lamp": {"name": "brass hand lamp", "kind": "object",
                                "portable": True},
            "folding_rule": {"name": "folding rule", "kind": "object",
                             "portable": True},
            "survey_staff": {"name": "survey staff", "kind": "object",
                             "portable": True},
            "iron_ladder": {"name": "iron ladder", "kind": "fixture"},
        },
        "poses": {"folding_rule": {"posture": "pocketed",
                                   "support": "Mireille Adjani"},
                  "survey_staff": {"posture": "upright"}},
        "contacts": [
            {"actor": "Mireille Adjani", "actor_part": "right hand",
             "target": "survey_staff", "manner": "grip", "motion": "settled"},
            {"actor": "Mireille Adjani", "actor_part": "left hand",
             "target": "iron_ladder", "manner": "grip", "motion": "settled"},
        ],
    }


class TestAThingABodyBearsGoesWhereItGoes:
    """PS3, PX25."""

    def test_every_way_a_beat_says_a_body_is_bearing_a_thing_is_read(self):
        sc = _kit_scene()
        borne = commit.derive_borne_containment(sc)
        assert {thing for thing, _who, _why in borne} == {
            "brass_hand_lamp", "folding_rule", "survey_staff"}
        assert {why for _t, _w, why in borne} == {
            "held_items", "pose", "contact"}
        assert all(record["in"] == "Mireille Adjani"
                   and record["mode"] == "carried"
                   for record in sc["contained"].values())

    def test_the_kit_follows_the_body_out_of_the_room(self):
        sc = _kit_scene()
        commit.derive_borne_containment(sc)
        sc["positions"]["Mireille Adjani"] = "upper_terrace_rim"
        derive_contained_positions(sc)
        assert sc["positions"]["brass_hand_lamp"] == "upper_terrace_rim"
        assert sc["positions"]["folding_rule"] == "upper_terrace_rim"
        assert sc["positions"]["survey_staff"] == "upper_terrace_rim"

    def test_a_fixture_a_hand_is_on_is_not_carried(self):
        """The direction this must not fail in: a body that grips a ladder
        does not walk off with the ladder."""
        sc = _kit_scene()
        commit.derive_borne_containment(sc)
        assert "iron_ladder" not in sc["contained"]
        sc["positions"]["Mireille Adjani"] = "upper_terrace_rim"
        derive_contained_positions(sc)
        assert sc["positions"]["iron_ladder"] == "haul_road_head"

    def test_a_record_this_derived_retires_when_the_evidence_does(self):
        """A thing set down stays where it was set down."""
        sc = _kit_scene()
        commit.derive_borne_containment(sc)
        assert "survey_staff" in sc["contained"]
        sc["contacts"] = []
        sc["poses"] = {}
        sc["entities"]["Mireille Adjani"]["state"]["held_items"] = []
        assert commit.derive_borne_containment(sc) == []
        assert sc["contained"] == {}

    def test_a_declared_containment_record_outranks_this(self):
        sc = _kit_scene()
        sc["contained"] = {"brass_hand_lamp": {"in": "Tobin Slake",
                                               "mode": "carried"}}
        commit.derive_borne_containment(sc)
        assert sc["contained"]["brass_hand_lamp"]["in"] == "Tobin Slake"


class TestATransferNamesAHolder:
    """PR9."""

    def _scene(self):
        return {
            "rooms": {"second_landing": {"name": "Second Landing"},
                      "third_landing": {"name": "Third Landing"}},
            "positions": {"Mirela Andelic": "second_landing",
                          "Vesna Kolar": "second_landing",
                          "mirela_box": "third_landing"},
            "attire": {"Mirela Andelic": {"wearing": ["a work apron"]},
                       "Vesna Kolar": {"wearing": ["a grey shawl"]}},
            "entities": {"mirela_box": {"name": "tin box", "kind": "object",
                                        "portable": True}},
        }

    def test_a_body_that_is_not_holding_it_cannot_hand_it_over(self, temp_db):
        ctx = _ctx(temp_db)
        sc = self._scene()
        diff = {"inventory_ops": [
            {"op": "transfer", "object_id": "mirela_box",
             "from_id": "Mirela Andelic", "to_id": "Vesna Kolar",
             "relation": "held"}]}
        refused = commit._refuse_unheld_transfers(ctx, sc, diff)

        assert len(refused) == 1
        assert diff["inventory_ops"] == []
        assert any("mirela_box" in w for w in ctx.warnings)

    def test_a_holder_the_ledger_records_is_still_a_holder(self, temp_db):
        ctx = _ctx(temp_db)
        sc = self._scene()
        sc["contained"] = {"mirela_box": {"in": "Mirela Andelic",
                                          "mode": "carried"}}
        diff = {"inventory_ops": [
            {"op": "transfer", "object_id": "mirela_box",
             "from_id": "Mirela Andelic", "to_id": "Vesna Kolar"}]}
        assert commit._refuse_unheld_transfers(ctx, sc, diff) == []
        assert len(diff["inventory_ops"]) == 1

    def test_a_body_standing_over_it_may_pick_it_up(self, temp_db):
        ctx = _ctx(temp_db)
        sc = self._scene()
        sc["positions"]["Mirela Andelic"] = "third_landing"
        diff = {"inventory_ops": [
            {"op": "transfer", "object_id": "mirela_box",
             "from_id": "Mirela Andelic", "to_id": "Vesna Kolar"}]}
        assert commit._refuse_unheld_transfers(ctx, sc, diff) == []

    def test_silence_is_not_a_contradiction(self, temp_db):
        """A thing the scene cannot place is not a thing anybody is proved
        not to be holding."""
        ctx = _ctx(temp_db)
        sc = self._scene()
        sc["positions"].pop("mirela_box")
        diff = {"inventory_ops": [
            {"op": "transfer", "object_id": "mirela_box",
             "from_id": "Mirela Andelic", "to_id": "Vesna Kolar"}]}
        assert commit._refuse_unheld_transfers(ctx, sc, diff) == []


class TestAThingTakenOutOfSomethingIsNotThatThing:
    """PM16."""

    def _scene(self):
        return {
            "rooms": {"guild_hall": {"name": "The Guild Hall"}},
            "positions": {"tally_satchel": "guild_hall"},
            "entities": {
                "tally_satchel": {"name": "tally satchel", "kind": "object",
                                  "aliases": ["satchel", "tally_boards"],
                                  "container": True},
                "tally_boards": {"name": "two notched wooden tally boards",
                                 "kind": "object", "portable": True},
            },
        }

    def test_the_mint_stands_when_the_same_diff_moves_it_out(self, temp_db):
        ctx = _ctx(temp_db)
        sc = self._scene()
        prev = {"entities": {"tally_satchel": sc["entities"]["tally_satchel"]}}
        diff = {
            "entities": {"tally_boards": sc["entities"]["tally_boards"]},
            "inventory_ops": [
                {"op": "transfer", "object_id": "tally_boards",
                 "from_id": "tally_satchel", "to_id": "factors_table_entity"}],
        }
        folded = commit._fold_duplicate_mints(
            ctx, ctx.chat.id, sc, prev, diff)

        assert folded == []
        assert "tally_boards" in sc["entities"]

    def test_a_mint_no_transfer_relates_to_the_record_still_folds(
            self, temp_db):
        """The fold this guard must not disable: chat Flat 4B's second
        buzzer, minted beside the one that was already sounding."""
        ctx = _ctx(temp_db)
        sc = self._scene()
        prev = {"entities": {"tally_satchel": sc["entities"]["tally_satchel"]}}
        diff = {"entities": {"tally_boards": sc["entities"]["tally_boards"]}}
        folded = commit._fold_duplicate_mints(
            ctx, ctx.chat.id, sc, prev, diff)

        assert folded == [("tally_boards", "tally_satchel")]
        assert "tally_boards" not in sc["entities"]
