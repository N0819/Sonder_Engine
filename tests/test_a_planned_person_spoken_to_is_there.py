"""A planned person the beat speaks to is there -- and his name is his own.

Measured (scratch story 165, turn 4582, 2026-10-07). The Writers' Room had
planned Abel Gale at the inn (an authored plan, `brief.where: inn_common`,
not yet rendered). `plans_in_view` offered him to the Director and the
encoder as a body in the room, and the player's "One of you had better be
Petch" bound to him -- but perception and the voices read only the scene, so
he was never narrated, never answered and never placed. And the descriptor
seed dealt the plan's NAME, "Abel Gale", to the innkeeper standing nearby: from
then on the name resolved to the keeper by retrieval.
"""

from core.db import wset_for_frame

from agents.director import _stand_touching_figures
from persist.commit import descriptor_bindings
from tests.test_background_description_address import ROOM, _make_ctx

UID = "plan:person:abel_gale:1"
ABEL = {"name": "Abel Gale", "room": "inn_common", "role": "bargeman",
        "posts": [], "charter": "", "body": "", "plan": UID, "kind": "person",
        "aliases": ["Abel"], "look": "a broad young bargeman, wet to the knee"}


def _diff():
    return {"causal_steps": [{"patch": {}}]}


def test_a_planned_person_the_beat_addresses_stands_where_planned():
    sd = _diff()
    stood = _stand_touching_figures({"entities": {}, "positions": {}}, sd,
                                    [dict(ABEL)], addressed=["Abel Gale"])
    assert stood == ["Abel Gale"]
    abel = sd["entities"]["Abel Gale"]
    assert abel["kind"] == "person" and abel["plan_ref"] == {"uid": UID}
    assert abel["description"] == ABEL["look"], "the commit settles the render"
    assert "charter_ref" not in abel
    assert sd["positions"]["Abel Gale"] == "inn_common"
    assert sd["causal_steps"][0]["patch"]["positions"]["Abel Gale"] == "inn_common", (
        "present from the beat's first moment, not arriving at its end")


def test_a_plan_nobody_reached_stays_a_plan():
    sd = _diff()
    assert _stand_touching_figures({"entities": {}, "positions": {}}, sd,
                                   [dict(ABEL)], addressed=["Gatoen Netowick"]) == []
    assert "Abel Gale" not in (sd.get("entities") or {})


def test_a_plan_out_of_view_is_not_stood_here():
    assert _stand_touching_figures({}, _diff(), [dict(ABEL, reserved=True)],
                                   addressed=["Abel Gale"]) == []


def test_a_plan_already_rendered_is_not_minted_twice():
    scene = {"entities": {"abel": {"name": "Abel Gale", "kind": "person",
                                   "plan_ref": {"uid": UID}}},
             "positions": {"abel": "inn_common"}}
    assert _stand_touching_figures(scene, _diff(), [dict(ABEL)],
                                   addressed=["Abel Gale"]) == []


def test_a_planned_persons_name_is_never_dealt_to_somebody_else(temp_db):
    traders = {"Trader Tate": {"first_turn": 1, "last_turn": 4},
               "Trader Mira": {"first_turn": 1, "last_turn": 4}}
    ctx = _make_ctx(temp_db, traders, addressed_refs=["Abel Gale"],
                    director_resolve={"resolved_event": "", "dialogue_log": [],
                                      "state_diff": {}})
    wset_for_frame(ctx.chat.id, "planned_entities", {UID: {
        "uid": UID, "name": "Abel Gale", "kind": "person",
        "aliases": ["Abel"], "brief": {"where": ROOM}}}, None)
    assert descriptor_bindings(ctx) == {}
