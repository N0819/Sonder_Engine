"""A charter creature reaches every seam as WHAT IT IS, not as a person.

Scratch play 2026-09-14, chat 4 (the horror torture test): a Writers'
Room creature stood one pace from the player at an open door for two beats.
It reached the page as "the unfamiliar person"; the background reactor was
told it was "a person with no character sheet", offered it a conversation,
and gave it eyes its look denied; and the causal Director's world index for
the yard held one body -- the player -- so the line spoken at the thing had
nobody to be routed to. Four seams, one class: a body's charter says what it
is, and every reader asks the charter.
"""
import time

from agents.director import causal_world_index
from persist.commit import _merge_presence_record, presence_personhood
from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import (background_presence_records,
                                   presence_view, save_registry)


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Creature", "", time.time()))


def _well_thing(look="a long pale jointed thing with no eyes", noun="thing"):
    creature = {"prey": ["figure"], "senses": {"hearing": True},
                "look": look, "noun": noun}
    charter = normalize_charter({
        "key": "well",
        "upkeeps": {"hunger": {"place": "well_house", "level": 0.7,
                               "floor": 0.3, "drift_per_hour": 0.01,
                               "service_per_hour": 0.0}},
        "posts": {"hunt": {"place": "yard", "serves": ["hunger"],
                           "requires": {"hunt": 1}}},
        "bodies": {"thing_0": {"place": "yard", "name": "Well Thing",
                               "competence": {"hunt": 1}}},
        "priority": ["hunger"],
        "creature": creature,
    })
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


class TestTheCausalDirectorSeesWhoTheCharterPutHere:
    SC = {"rooms": {"yard": {"name": "Farmyard", "adjacent": []},
                    "lane": {"name": "Lane", "adjacent": []}},
          "positions": {"Iris": "yard"}, "entities": {}}

    def test_a_figure_in_the_slice_is_held_by_its_room(self):
        index = causal_world_index(self.SC, room_ids=["yard"], figures=[
            {"name": "Well Thing", "room": "yard", "role": "thing",
             "look": "a long pale jointed thing",
             "creature": {"hunts": ["figure"]}}])
        held = {row["id"]: row for row in index["rooms"]["yard"]["holds"]}
        assert set(held) == {"Iris", "Well Thing"}
        assert held["Well Thing"] == {
            "id": "Well Thing", "name": "Well Thing", "kind": "figure",
            "role": "thing", "look": "a long pale jointed thing",
            "creature": {"hunts": ["figure"]}}

    def test_a_figure_outside_the_slice_or_already_held_adds_nothing(self):
        index = causal_world_index(self.SC, room_ids=["yard"], figures=[
            {"name": "Far Off", "room": "lane"},
            {"name": "Iris", "room": "yard"},
            {"name": "Reserved", "room": "yard", "reserved": True}])
        assert [r["id"] for r in index["rooms"]["yard"]["holds"]] == ["Iris"]
        assert "lane" not in index["rooms"]

    def test_no_figures_leaves_the_index_byte_identical(self):
        assert causal_world_index(self.SC, room_ids=["yard"]) == \
            causal_world_index(self.SC, room_ids=["yard"], figures=[])


class TestTheRecordSaysCreature:
    def test_a_creature_body_is_a_creature_with_its_look_and_noun(self, temp_db):
        cid = _chat(temp_db)
        save_registry(cid, {"well": _well_thing()})
        records = background_presence_records(cid, places={"yard"})
        rec = records["Well Thing"]
        assert rec["nature"] == "creature"
        assert rec["sketch"]["appearance"] == \
            "a long pale jointed thing with no eyes"
        assert rec["sketch"]["noun"] == "thing"

    def test_a_person_stays_a_person(self, temp_db):
        cid = _chat(temp_db)
        charter = _well_thing()
        charter["creature"] = None
        save_registry(cid, {"well": charter})
        rec = background_presence_records(cid, places={"yard"})["Well Thing"]
        assert rec["nature"] == "person"
        assert "noun" not in rec["sketch"]

    def test_the_charter_overrules_a_record_minted_before_it_said_so(self):
        target = {"nature": "person", "sketch": {}}
        _merge_presence_record(target, {
            "nature": "creature", "sketch": {"appearance": "a pale thing"},
            "charter_refs": [{"charter": "well", "body": "thing_0"}]})
        assert target["nature"] == "creature"
        assert target["sketch"]["appearance"] == "a pale thing"
        kept = {"nature": "thing", "sketch": {}}
        _merge_presence_record(kept, {"nature": "person"})
        assert kept["nature"] == "thing"

    def test_a_creature_acts_but_never_speaks(self):
        record = {"nature": "creature", "dialogue_turns": [3]}
        assert presence_personhood({}, "Well Thing", record) == "creature"
        from persist.commit import _presence_speech_verdict
        assert _presence_speech_verdict({}, "Well Thing", record) == "creature"


class TestTheVoiceIsToldWhatItIs:
    def test_a_creature_gets_its_block_and_no_conversation(self, temp_db):
        cid = _chat(temp_db)
        save_registry(cid, {"well": _well_thing()})
        rows = presence_view(cid, "yard", "Well Thing",
                             figures=[{"key": "Iris", "label": "a woman"}])
        assert len(rows) == 1
        row = rows[0]
        assert "action_instances" not in row
        assert "presence" not in row
        assert row["creature"]["look"] == \
            "a long pale jointed thing with no eyes"
        assert row["creature"]["noun"] == "thing"
        assert row["creature"]["prey"] == ["figure"]
        assert row["look"] == "a long pale jointed thing with no eyes"


class TestTheStrangerLabelIsNotAPerson:
    def test_the_compositor_has_a_word_for_an_unnamed_shape(self):
        from agents.common import _text
        assert _text("creature_noun") == "figure"

    def test_a_pose_with_no_stated_relation_claims_no_contact(self):
        from agents.common import _text
        assert _text("pose_relation", other="the scullery door") == \
            "by the scullery door"

    def test_a_closed_surface_is_not_closed_twice(self):
        from agents.common import _observable_predicate
        assert _observable_predicate(
            "The figure", "shifts its weight, eyes on the light.") == \
            "The figure shifts its weight, eyes on the light."
        assert _observable_predicate("The figure", "waits...").endswith("...")


class TestACutLookEndsOnTheThingsNoun:
    LOOK = ("long, black-slick and eel-jointed, with a flat head, no eyes to "
            "speak of, and hands")

    def test_the_head_noun_closes_a_cut_description(self):
        from agents.common import _unknown_actor_label
        label = _unknown_actor_label("Thing_0", self.LOOK, head_noun="shape")
        assert label.startswith("the long") and label.endswith(" shape")

    def test_a_noun_already_in_the_description_is_not_doubled(self):
        from agents.common import _unknown_actor_label
        assert _unknown_actor_label(
            "Thing_0", "a pale shape in the reeds", head_noun="shape") \
            == "the pale shape in the reeds"

    def test_no_look_at_all_is_the_noun(self):
        from agents.common import _unknown_actor_label
        assert _unknown_actor_label("Thing_0", "", head_noun="shape") == "the shape"

    def test_the_display_map_reads_the_noun_off_the_body(self):
        from agents.composer import assign_stranger_labels
        labels = assign_stranger_labels([
            ("Thing_0", self.LOOK, [], "shape", None, "shape")])
        assert labels["Thing_0"].endswith(" shape")


class TestAMintOfAPresentCreatureIsDropped:
    FIGURES = [
        {"name": "The_thing_0", "role": "", "posts": [], "room": "pound",
         "charter": "well", "body": "the_thing_0",
         "creature": {"hunts": ["figure"]}},
        {"name": "Innkeeper Tam", "role": "innkeeper", "posts": ["inn"],
         "room": "pound", "charter": "inn", "body": "b1"},
    ]

    def _floor(self):
        from agents.director import _bind_minted_entities_to_present_figures
        return _bind_minted_entities_to_present_figures

    def test_a_mint_under_the_bodys_own_key_is_that_body(self):
        """Chat 5 turn 0: the opening Director minted the creature under its
        body key with a name the display never matched, and the creature
        stood twice."""
        sd = {"entities": {"the_thing_0": {
                  "name": "The thing in the pound", "kind": "figure",
                  "description": "long and black-slick"}},
              "positions": {"the_thing_0": "pound"}}
        bound = self._floor()({"entities": {}}, sd, self.FIGURES)
        assert bound == [{"entity_id": "the_thing_0",
                          "minted_name": "The thing in the pound",
                          "bound_to": "The_thing_0", "room": "pound",
                          "by": "body", "ambiguous": False, "dropped": True,
                          "plan": ""}]
        assert sd["entities"] == {}
        assert sd["positions"] == {"the_thing_0": "pound"}

    def test_a_person_minted_under_its_key_binds_and_stays(self):
        sd = {"entities": {"b1": {"name": "the innkeeper", "kind": "person",
                                   "description": "a stout man"}},
              "positions": {"b1": "pound"}}
        bound = self._floor()({"entities": {}}, sd, self.FIGURES)
        assert bound[0]["by"] == "body" and not bound[0].get("dropped")
        assert sd["entities"]["b1"]["name"] == "Innkeeper Tam"
        assert sd["entities"]["b1"]["charter_ref"] == {"charter": "inn",
                                                        "body": "b1"}
