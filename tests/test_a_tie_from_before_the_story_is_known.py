"""A tie from before the story is recognition, both ways.

Owner ruling, 2026-10-07. Until now only an in-play introduction wrote the
`known` ledger, so nothing authored before the story could make two people
know each other. Measured (scratch story 165, turn 4584): the pilot Hester
Gale called her own brother an impostor -- "That's not Abel. Abel Gale is my
brother ... This man's a stranger to me" -- because the Writers' Room had
planned him at the inn and nothing said she had known his face since before
either of them could walk. A plan now names the cast who know the person
from before (`known_by`), and publishing writes `known` both ways.
"""

import json
import time

from core.db import wget
from story.character_schema import default_character_data, default_persona_data
from story.plot_packages import (draft_operation, get_package, new_package,
                                 preview_package, publish_package,
                                 validate_package)
from world.planned_entities import planned_entities

ROOM = "quay"


def _story(db):
    pid = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                ("Tamsin Coyle", json.dumps(default_persona_data("Tamsin Coyle")),
                 "{}"))
    cid = db.qi("INSERT INTO chats(name,scenario,created,persona_id) "
                "VALUES(?,?,?,?)", ("Fen", "", time.time(), pid))
    key = db.qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                "VALUES(?,?,?,?,?)",
                ("Hester Gale", json.dumps(default_character_data("Hester Gale")),
                 "{}", time.time(), "hester"))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
          (cid, key, "active", "{}"))
    db.wset(cid, "scene", {"location": "Fen", "rooms": {
        ROOM: {"name": "Quay", "desc": "Wet stone.", "adjacent": []}},
        "positions": {"Tamsin Coyle": ROOM}, "entities": {}, "attire": {}})
    for idx in range(3):
        db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
              "VALUES(?,?,?,?)", (cid, idx, "", time.time()))
    return cid


def _plan(cid, known_by):
    pkg = new_package(cid, title="The Gales", premise="Her brother is here.")
    draft_operation(cid, pkg["uid"], {
        "op": "plan_entity", "name": "Abel Gale", "kind": "person",
        "role": "bargeman", "known_by": known_by,
        "brief": {"purpose": "Hester's younger brother", "where": ROOM}})
    return pkg["uid"]


def _publish(cid, uid):
    validate_package(cid, uid)
    return publish_package(cid, uid,
                           expected_revision=get_package(cid, uid)["revision"])


def test_a_sister_and_her_brother_know_each_other(temp_db):
    cid = _story(temp_db)
    uid = _plan(cid, ["Hester Gale"])
    assert preview_package(cid, uid)["errors"] == []
    _publish(cid, uid)
    known = wget(cid, "known", {})
    assert "Abel Gale" in known["Hester Gale"]
    assert "Hester Gale" in known["Abel Gale"]
    plan = next(p for p in planned_entities(cid).values()
                if p["name"] == "Abel Gale")
    assert plan["known_by"] == ["Hester Gale"]


def test_the_player_is_named_by_the_truths_own_word(temp_db):
    cid = _story(temp_db)
    _publish(cid, _plan(cid, ["player"]))
    known = wget(cid, "known", {})
    assert "Abel Gale" in known["Tamsin Coyle"]
    assert "Tamsin Coyle" in known["Abel Gale"]


def test_a_tie_to_nobody_the_story_holds_is_refused(temp_db):
    cid = _story(temp_db)
    errors = preview_package(cid, _plan(cid, ["Nobody Here"]))["errors"]
    assert any("Nobody Here" in e and "not a registered character" in e
               for e in errors)


def test_a_plan_with_no_tie_writes_no_recognition(temp_db):
    cid = _story(temp_db)
    _publish(cid, _plan(cid, []))
    assert "Abel Gale" not in (wget(cid, "known", {}) or {})


def _plan_two(cid, first_known_by, second_known_by, *, title="The wire"):
    pkg = new_package(cid, title=title, premise="The line and its keeper.")
    draft_operation(cid, pkg["uid"], {
        "op": "plan_entity", "name": "Karl Wessel", "kind": "person",
        "role": "lineman", "known_by": first_known_by,
        "brief": {"purpose": "walks the wire", "where": ROOM}})
    draft_operation(cid, pkg["uid"], {
        "op": "plan_entity", "name": "Agathe Brenn", "kind": "person",
        "role": "telegraphist", "known_by": second_known_by,
        "brief": {"purpose": "keeps the instrument", "where": ROOM}})
    return pkg["uid"]


def test_two_people_the_room_plans_together_may_know_each_other(temp_db):
    """Hollowmere (scratch chat 196, 2026-10-12): the lineman's plan said he
    courts the telegraphist, both were the room's own people, and a tie
    between two plans was refused -- so he addressed her, in the line that
    spoke her name, by a stranger's label (turn 4685)."""
    cid = _story(temp_db)
    uid = _plan_two(cid, [], ["Karl Wessel"])
    assert preview_package(cid, uid)["errors"] == []
    _publish(cid, uid)
    known = wget(cid, "known", {})
    assert "Agathe Brenn" in known["Karl Wessel"]
    assert "Karl Wessel" in known["Agathe Brenn"]


def test_a_person_planned_in_an_earlier_package_may_be_named(temp_db):
    cid = _story(temp_db)
    _publish(cid, _plan(cid, []))                    # Abel Gale, planned first
    pkg = new_package(cid, title="The ferry", premise="A second bargeman.")
    draft_operation(cid, pkg["uid"], {
        "op": "plan_entity", "name": "Jory Pell", "kind": "person",
        "role": "bargeman", "known_by": ["Abel Gale"],
        "brief": {"purpose": "Abel's mate on the barge", "where": ROOM}})
    assert preview_package(cid, pkg["uid"])["errors"] == []
    _publish(cid, pkg["uid"])
    assert "Jory Pell" in wget(cid, "known", {})["Abel Gale"]


def test_a_plan_cannot_know_itself(temp_db):
    cid = _story(temp_db)
    errors = preview_package(cid, _plan(cid, ["Abel Gale"]))["errors"]
    assert any("knows themself" in e for e in errors)


def _plan_one(cid, name, known_by, truths, *, title):
    pkg = new_package(cid, title=title, premise="People of the line.")
    draft_operation(cid, pkg["uid"], {
        "op": "plan_entity", "name": name, "kind": "person", "role": "lineman",
        "known_by": known_by,
        "brief": {"purpose": "walks the wire", "truths": truths, "where": ROOM}})
    return pkg["uid"]


def _tie_warnings(cid, uid):
    return [w for w in preview_package(cid, uid)["warnings"] if "known_by" in w and "strangers" in w]


def test_a_tie_the_brief_states_and_known_by_leaves_out_is_named(temp_db):
    """Replaying Hollowmere's turn-20 fill (2026-10-12): a retired lineman's
    truths read "He knows Karl Wessel, the company's present lineman", and
    his known_by named only the companion. Preview asks; it never seeds."""
    cid = _story(temp_db)
    _publish(cid, _plan_one(cid, "Karl Wessel", [], "He walks the poles.", title="The lineman"))
    stated = ["He knows Karl Wessel, the company's present lineman for this stretch."]
    uid = _plan_one(cid, "Lorenz Haid", [], stated, title="The old lineman")
    warned = _tie_warnings(cid, uid)
    assert len(warned) == 1 and "Karl Wessel" in warned[0]
    listed = _plan_one(cid, "Lorenz Haid", ["Karl Wessel"], stated, title="The old lineman, listed")
    assert _tie_warnings(cid, listed) == []


def test_a_plan_whose_brief_names_the_newcomer_asks_from_the_other_side(temp_db):
    """The original case: the lineman's own plan said he courts her, and she
    was planned twenty beats later with no word of him."""
    cid = _story(temp_db)
    _publish(cid, _plan_one(cid, "Karl Wessel", [], "He courts Agathe Brenn.", title="The lineman"))
    uid = _plan_one(cid, "Agathe Brenn", [], "She keeps the instrument.", title="The keeper")
    warned = _tie_warnings(cid, uid)
    assert len(warned) == 1 and "Karl Wessel" in warned[0] and "Agathe Brenn" in warned[0]


def test_a_brief_naming_a_registered_character_asks_too_and_player_counts(temp_db):
    cid = _story(temp_db)
    uid = _plan_one(cid, "Abel Gale", [], "Hester Gale is his sister; Tamsin Coyle hired him.",
                    title="The brother")
    warned = _tie_warnings(cid, uid)
    assert {("Hester Gale" in w, "Tamsin Coyle" in w) for w in warned} == {(True, False), (False, True)}
    both = _plan_one(cid, "Abel Gale", ["Hester Gale", "player"],
                     "Hester Gale is his sister; Tamsin Coyle hired him.", title="The brother, tied")
    assert _tie_warnings(cid, both) == []
