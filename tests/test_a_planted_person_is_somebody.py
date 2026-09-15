"""A planted person is enrolled as a charter body, so there is a mind to tell.

Scratch play 2026-09-14, chat 9 turn 9: a telling to the brewer the Room had
planted in the card room was refused as naming someone unregistered -- a plan
is a look and a brief, and nothing simulates it. `plan_entity` for a person
now enrols them the way a person-need is answered.
"""

import time

from story.plot_packages import _apply_plan_entity
from world.charter import normalize_charter
from world.charter_runtime import registry_for, save_registry
from world.planned_entities import planned_entities, plan_figure


def test_a_planted_person_gets_a_body_on_the_post_their_role_names(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Wendover", "", time.time()))
    save_registry(cid, {"version": 1, "items": {"crown": {"state": normalize_charter({
        "key": "crown",
        "posts": {"brewer": {"place": "card_room", "serves": []},
                  "landlord": {"place": "hall", "serves": []}},
        "bodies": {"landlord:1": {"name": "Bragg", "place": "hall", "berth": "hall",
                                  "available": True, "home_post": "landlord"}},
    })}}})
    out = _apply_plan_entity(cid, None, {
        "kind": "person", "name": "Josiah Crane", "aliases": [], "role": "brewer",
        "brief": {"purpose": "plays cards", "truths": "", "where": "card_room"},
        "surface": {}, "look": "a heavy man in a snuff-coloured coat",
        "answers_need": ""}, turn_idx=0)
    assert out["enrolled"]["charter"] == "crown"
    body_key = out["enrolled"]["body"]
    body = registry_for(cid)["items"]["crown"]["state"]["bodies"][body_key]
    assert body["name"] == "Josiah Crane" and body["place"] == "card_room"
    plan = planned_entities(cid)[out["uid"]]
    assert plan["enrolled"] == out["enrolled"]
    row = plan_figure(plan)
    assert (row["charter"], row["body"]) == ("crown", body_key)
