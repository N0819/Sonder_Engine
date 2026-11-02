"""A body that is dead or missing is in no room: it witnesses nothing, is
talked to by nobody, fills no crowd and voices nothing.

`charter_harm.apply_harm` keeps a dead body's `place` -- where it fell -- and
only `charter_talk.co_present` honoured the rule. Measured (audit
world_charter_behaviours F11): a dead `tam` in the yard received public
speech, stood in the yard's crowd and was laid as a standing figure, and a
corpse that "heard" a promise was added to its `recognized_by`. One reader
(`charter_harm.in_a_room`) answers the question at every site; a corpse is
laid where it fell, LYING."""
from world.charter import normalize_charter
from world.charter_crowd import members_of
from world.charter_feel import advance_feel
from world.charter_log import scene_ledger
from world.charter_observe import plan_public_evidence
from world.charter_place import charter_placements, scene_with_charter_bodies


def _charter():
    return normalize_charter({
        "key": "yard_folk", "upkeeps": {}, "posts": {},
        "bodies": {
            "ivo": {"place": "yard", "name": "Ivo"},
            "tam": {"place": "yard", "name": "Tam", "condition": "dead"},
            "wat": {"place": "yard", "name": "Wat"},
            "sal": {"place": "yard", "name": "Sal"},
        }})


def _scene():
    return {"rooms": {"yard": {"name": "Yard", "adjacent": [],
                               "size": "large"}},
            "positions": {"Mara": "yard"}, "entities": {}}


def test_a_dead_body_receives_no_speech():
    plan = plan_public_evidence(
        _charter(),
        [{"source_id": "s1", "kind": "speech", "actor": "Mara",
          "exact_quote": '"Run."', "volume": "normal"}],
        _scene(), 3, labels={"Mara": "the stranger"})
    assert "tam" not in plan["receiving"]
    assert "tam" not in plan["recipients"].get("s1", set())
    assert sorted(plan["receiving"]) == ["ivo", "sal", "wat"]


def test_a_dead_body_is_in_no_crowd():
    assert "tam" not in members_of(_charter(), "yard")


def test_a_dead_body_has_no_presence_and_is_nobodys_stranger():
    presences = scene_ledger(_charter(), "yard")["presences"]
    assert "tam" not in presences
    for presence in presences.values():
        assert "tam" not in presence["strangers_here"]


def test_a_dead_body_feels_nothing():
    charter = _charter()
    # A failing condition in the yard stirs everybody standing in it.
    upkeeps = {"well": {"place": "yard", "level": 0.1, "floor": 0.5,
                        "drift_per_hour": 0.0, "service_per_hour": 0.0}}
    feel = advance_feel({}, charter["bodies"], charter.get("needs") or {},
                        {}, {}, upkeeps, [], 4.0)
    assert "ivo" in feel, "the living in a failing yard are stirred"
    assert "tam" not in feel


def test_a_corpse_is_laid_where_it_fell_lying_down():
    charter = _charter()
    placements = charter_placements({"items": {"yard_folk": {
        "state": charter}}}, _scene())
    corpse = [p for p in placements.values() if p["body"] == "tam"]
    assert corpse and corpse[0]["room"] == "yard"
    assert corpse[0]["presented"] != "crowd"
    viewed = scene_with_charter_bodies(_scene(), placements)
    pose = (viewed.get("poses") or {}).get(corpse[0]["key"]) or {}
    assert pose.get("posture") == "lying"
    # ...and nobody alive is laid lying.
    for placement in placements.values():
        if placement["body"] != "tam":
            assert (viewed.get("poses") or {}).get(placement["key"]) is None
