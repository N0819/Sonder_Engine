"""A TRUTH REACHES THE MINDS ITS `known_by` NAMES.

O12/O13/O22 of the Cwm Du run (chat 167, turns 4619-4626). The owner told
the Writers' Room who died in Gallery Nine and who signed the timbering
report. The Room filed both as package truths, `known_by: ["Ffion Rees"]`,
and nothing ever read `known_by`: Ffion's mind held her card (generated a
minute before the owner's answer, naming nobody, and saying Prothero signed
the report) and her own overheard scraps, so she invented the dead and
named the wrong signatory. The launch could not file lore at all, so what
everyone in the valley knew had no channel either. And the deputy the Room
planned at the opening, placed by a crowd's dispersal under his name alone,
was never bound to his plan: a need was filed for him, and the Room planned
him again.

The owner's ruling (2026-10-10): a truth reaches every mind its `known_by`
names, from the turn after it lands, as something that mind already knew,
over an older card; what everyone here knows is common lore, and the launch
may file it.
"""

from __future__ import annotations

import json
import time

import pytest

from story.plot_packages import save_packages, truths_known_by
from story.scene import private_knowledge_for

SIGNED = "The timbering report was signed by the deputy, Emrys Vaughan."
DEAD = "Huw Jenkins and Ieuan Price died when Gallery Nine came in."


def _package(**over):
    pkg = {"uid": "pkg_gallery_nine", "title": "The Gallery Nine report",
           "status": "published", "published_turn": 3,
           "truths": [
               {"id": "truth_signed", "text": SIGNED, "known_by": ["Ffion Rees"]},
               {"id": "truth_dead", "text": DEAD,
                "known_by": ["Ffion Rees", "Emrys Vaughan"]},
               {"id": "truth_sound", "text": "The props were sound.",
                "known_by": ["Ffion Rees"], "superseded_by": "truth_signed"},
               {"id": "truth_prothero", "text": "Prothero knew.",
                "known_by": ["Mr Prothero"]},
               {"id": "truth_player", "text": "Nell's brother was a hewer.",
                "known_by": ["player"]},
               {"id": "truth_nobody", "text": "The larch was green.",
                "known_by": []}]}
    pkg.update(over)
    return pkg


@pytest.fixture
def cid(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Cwm Du", "", time.time()))
    save_packages(cid, {"pkg_gallery_nine": _package()})
    return cid


def _texts(rows):
    return [truth["text"] for _title, truth in rows]


class TestWhoKnowsIt:
    def test_a_truth_reaches_only_the_minds_it_names(self, cid):
        assert _texts(truths_known_by(cid, "Ffion Rees", 4)) == [SIGNED, DEAD]
        assert _texts(truths_known_by(cid, "  ffion   rees ", 4)) == [SIGNED, DEAD]
        assert _texts(truths_known_by(cid, "Emrys Vaughan", 4)) == [DEAD]
        assert truths_known_by(cid, "Nell Hartley", 4) == []

    def test_from_the_turn_after_it_landed_never_in_it(self, cid):
        assert truths_known_by(cid, "Ffion Rees", 3) == []
        assert _texts(truths_known_by(cid, "Ffion Rees", 4)) == [SIGNED, DEAD]

    def test_a_superseded_truth_stops_and_player_is_no_cast_mind(self, cid):
        assert "The props were sound." not in _texts(truths_known_by(cid, "Ffion Rees", 9))
        assert truths_known_by(cid, "player", 9) == []

    @pytest.mark.parametrize("status,kept", [("active", True), ("resolved", True),
                                             ("retired", False), ("draft", False)])
    def test_what_the_package_has_become(self, temp_db, status, kept):
        cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Cwm Du", "", time.time()))
        save_packages(cid, {"pkg_gallery_nine": _package(status=status)})
        assert bool(truths_known_by(cid, "Ffion Rees", 9)) is kept


class TestTheMindHoldsIt:
    def test_it_arrives_as_something_already_known_over_older_memory(self, temp_db, cid):
        rows = private_knowledge_for({"id": cid, "persona_id": None}, "Ffion Rees",
                                     turn_idx=4)
        truths = [row for row in rows if row["content"] in (SIGNED, DEAD)]
        assert [row["content"] for row in truths] == [SIGNED, DEAD]
        assert all(row["about"] == "The Gallery Nine report" for row in truths)
        assert "already knew" in truths[0]["source"]
        assert "older memory" in truths[0]["source"]

    def test_without_a_turn_it_waits_for_the_next_turn_row(self, temp_db, cid):
        def known():
            return [row["content"] for row in private_knowledge_for(
                {"id": cid, "persona_id": None}, "Ffion Rees")]
        for idx in range(4):
            temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                       (cid, idx, "", time.time()))
        assert known() == []
        temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                   (cid, 4, "", time.time()))
        assert known() == [SIGNED, DEAD]

    def test_the_label_is_the_story_language(self):
        from language_runtime import linguistic
        assert "already knew" in linguistic("story.scene", "_ALREADY_KNOWN_SOURCE", "en")
        assert linguistic("story.scene", "_ALREADY_KNOWN_SOURCE", "ja").startswith("ずっと以前から")


def test_the_room_is_told_the_three_ways_a_fact_is_held_and_may_file_lore_at_launch():
    from pathlib import Path
    import story.opening_plan as op
    assert "file_lore" in op.OPENING_CAPABILITIES
    for language in ("en", "ja"):
        card = Path(f"language_packs/{language}/cards/system_prompts/prompts/"
                    "story_planner.txt").read_text(encoding="utf-8")
        assert card.count("file_lore") >= 2, language       # the clause and the opening
        assert 'knowledge_tag "common"' in card, language


# ---- a planned body placed by name alone -------------------------------------

EMRYS = {"name": "Emrys Vaughan", "room": "pit_bottom", "kind": "person",
         "plan": "plan:person:emrys_vaughan", "reserved": True,
         "look": "a lean man in a deputy's waistcoat, a stick under his arm"}


class TestAPlannedBodyPlacedByNameIsItsPlan:
    def _stand(self, figures, positions=None, entities=None, roster=()):
        from agents.director import _stand_up_plans_placed_by_name
        sd = {"positions": positions or {"Emrys Vaughan": "saw_sheds"}}
        if entities is not None:
            sd["entities"] = entities
        return sd, _stand_up_plans_placed_by_name({"entities": {}}, sd, figures, roster)

    def test_the_live_placement_stands_up_the_plan(self):
        """Turn 4618: the crowd's dispersal placed him and wrote no record."""
        sd, stood = self._stand([EMRYS])
        record = sd["entities"]["Emrys Vaughan"]
        assert record == {"name": "Emrys Vaughan", "kind": "person",
                          "plan_ref": {"uid": EMRYS["plan"]}, "description": EMRYS["look"]}
        assert [b["plan"] for b in stood] == [EMRYS["plan"]]

    def test_a_body_the_scene_already_holds_by_name_alone_heals(self):
        """Replay of 4629: he was placed at 4628, before the rule, and every
        other floor skips a placed body -- the binder reads records, the
        lease counts a placed body as held."""
        from agents.director import _stand_up_plans_placed_by_name
        sc = {"positions": {"Emrys Vaughan": "pit_bottom", "Nell Hartley": "pit_bottom"},
              "entities": {}}
        sd = {"positions": {"Nell Hartley": "pit_bottom"}}
        stood = _stand_up_plans_placed_by_name(sc, sd, [EMRYS], ["Nell Hartley"])
        assert [b["entity_id"] for b in stood] == ["Emrys Vaughan"]
        assert sd["entities"]["Emrys Vaughan"]["plan_ref"] == {"uid": EMRYS["plan"]}
        assert "Nell Hartley" not in sd["entities"]

    def test_a_title_or_case_is_the_same_name(self):
        sd, stood = self._stand([EMRYS], positions={"Mr emrys vaughan": "saw_sheds"})
        assert sd["entities"]["Mr emrys vaughan"]["name"] == "Emrys Vaughan"

    def test_what_it_never_takes(self):
        # two plans answer the name: refused, not guessed
        twin = dict(EMRYS, plan="plan:person:emrys_vaughan_2")
        assert self._stand([EMRYS, twin])[1] == []
        # a charter body answers the name: the lease's, never the plan's
        charter = {"name": "Emrys Vaughan", "room": "pit_bottom",
                   "charter": "colliery", "body": "deputy:0001"}
        assert self._stand([EMRYS, charter])[1] == []
        # a registered mind answers the name
        assert self._stand([EMRYS], roster=["Emrys Vaughan"])[1] == []
        # a record already holds it: the binder's to bind
        assert self._stand([EMRYS], entities={
            "e1": {"name": "Emrys Vaughan", "kind": "person"}})[1] == []

    def test_a_planned_thing_stands_up_as_a_thing(self):
        timber = {"name": "Gallery Nine timbering", "room": "gallery_nine",
                  "kind": "thing", "plan": "plan:thing:gallery_nine_timbering"}
        sd, _ = self._stand([timber], positions={"Gallery Nine timbering": "gallery_nine"})
        assert sd["entities"]["Gallery Nine timbering"]["kind"] == "object"


def _presence_ctx(temp_db, cid):
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    temp_db.wset(cid, "scene", {
        "location": "Cwm Du", "time": "night", "attire": {}, "overlays": {},
        "rooms": {"saw_sheds": {"name": "Saw Sheds", "adjacent": []}},
        "positions": {"Emrys Vaughan": "saw_sheds"}, "entities": {}})
    turn_id = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                         (cid, 2, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Cwm Du", persona_id=None, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=2, player_input="", created=time.time()),
        cast=[], input="")
    ctx.director_resolve = {"resolved_event": "The men go back to the sheds.",
                            "dialogue_log": [],
                            "state_diff": {"positions": {"Emrys Vaughan": "saw_sheds"}}}
    return ctx


def test_a_name_the_room_planned_files_no_need(temp_db):
    """Turn 4618 filed `rendered_unplanned` for the deputy the Room planned
    at the opening, and the Room planned him again."""
    from persist.commit import track_background_presences
    from world.planned_entities import add_planned_entity
    from world.planning_needs import open_planning_needs

    def needs_for(cid):
        return [n for n in open_planning_needs(cid)
                if (n.get("surface") or {}).get("name") == "Emrys Vaughan"]

    unplanned = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                           ("Cwm Du", "", time.time()))
    track_background_presences(_presence_ctx(temp_db, unplanned), nonce=0)
    assert needs_for(unplanned), "the control: an unplanned person files a need"

    planned = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Cwm Du", "", time.time()))
    add_planned_entity(planned, {"kind": "person", "name": "Emrys Vaughan",
                                 "brief": {"where": "pit_bottom"}}, turn_idx=0)
    track_background_presences(_presence_ctx(temp_db, planned), nonce=0)
    assert needs_for(planned) == []


# ---- a name the Room planned is not unplanned, before or after it renders ----

def _plans_chat(temp_db):
    from world.planned_entities import add_planned_entity
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Cwm Du", "", time.time()))
    emrys = add_planned_entity(cid, {"kind": "person", "name": "Emrys Vaughan",
                                     "aliases": ["the deputy"],
                                     "brief": {"where": "pit_bottom"}}, turn_idx=0)
    add_planned_entity(cid, {"kind": "thing", "name": "Gallery Nine timbering",
                             "brief": {"where": "gallery_nine"}}, turn_idx=0)
    return cid, emrys["uid"]


def test_one_reader_says_which_plan_answers_a_name(temp_db):
    from world.planned_entities import (add_planned_entity, plan_answering,
                                        settle_rendered_plans)
    cid, uid = _plans_chat(temp_db)
    assert plan_answering(cid, "Emrys Vaughan") == uid
    assert plan_answering(cid, "Mr emrys  vaughan") == uid
    assert plan_answering(cid, "the deputy") == uid
    assert plan_answering(cid, "Gallery Nine timbering") is None     # no person
    assert plan_answering(cid, "Ffion Rees") is None
    settle_rendered_plans(cid, [{"plan": uid, "entity_id": "Emrys Vaughan",
                                 "render": "a lean man in a waistcoat", "turn": 3}])
    assert plan_answering(cid, "Emrys Vaughan") == uid               # still his
    add_planned_entity(cid, {"kind": "person", "name": "Dai Price",
                             "brief": {"where": "pit_bottom"}}, turn_idx=1)
    add_planned_entity(cid, {"kind": "person", "name": "Dai Haulier",
                             "aliases": ["Dai Price"], "brief": {"where": "lamp_room"}},
                       turn_idx=1)
    assert plan_answering(cid, "Dai Price") is None                  # two answer


def test_the_drain_closes_a_stale_need_for_a_planned_name(temp_db, monkeypatch):
    """The need filed at 4618, before the filer learned the rule, stayed open;
    retried by the drain it would enrol the planned deputy as a second body
    wherever a seat was open."""
    import world.charter_enrol as charter_enrol
    from world.planning_needs import (drain_planning_needs, file_planning_need,
                                      open_planning_needs)
    cid, uid = _plans_chat(temp_db)
    need, _fresh = file_planning_need(cid, {
        "kind": "person", "reason": "rendered_unplanned", "presence": "p_emrys",
        "surface": {"name": "Emrys Vaughan", "room": "saw_sheds",
                    "description": "a lean man", "did": "", "role": ""}}, turn_idx=1)

    def never(*_a, **_k):
        raise AssertionError("a planned person was sent to enrolment")
    monkeypatch.setattr(charter_enrol, "enrol_person", never)
    out = drain_planning_needs(cid)
    assert out["closed"] == [{"uid": need["uid"], "plan": uid}]
    assert out["filled"] == [] and open_planning_needs(cid) == []
