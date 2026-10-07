"""The Writers' Room decides who lives in the place it plans, when the launch
left it open.

Owner ruling, 2026-10-07. A cast member reaches a generated town as a
featured resident -- a lived prehistory, the people they work beside as
acquaintances -- only on a resident route, and the automatic router reads
residence from the card's words alone; its travel test reads the opening too,
so an opening that sets the PLAYER down from a ferry made a local pilot a
"visitor" by somebody else's arrival. Measured (scratch story 165): she then
greeted the innkeeper as Petch and met her own brother as a stranger.

An automatic route that did not read residence is a CANDIDATE; the Room
places a candidate at a post if the place is their home, and the closure
adopts only what it placed. A route the author chose is never a candidate,
and the one-shot planner is never asked.
"""

import json
import time

import pytest

import world.charter_generate as charter_generate
from tests.test_fable_town import _plan
from world.charter_generate import close_plan
from world.charter_history import featured_resident_seed
from world.charter_runtime import (_complete_cast_histories,
                                   _plan_lived_location,
                                   _prepare_cast_histories)

SHEET = {"identity": {"name": "Hester Gale"},
         "knowledge": {"public_history": "A pilot of the Lowmarsh channels."}}


def test_a_candidate_the_plan_places_becomes_a_resident():
    cand = featured_resident_seed(81, SHEET)
    plan = _plan()
    plan["charters"][0]["featured_residents"] = [
        {"seed_id": cand["seed_id"], "post": "miller", "berth": "mill"}]
    town = close_plan(plan, candidate_residents=[cand])
    assert town["featured_residents"][cand["seed_id"]]["placed"] is True
    bodies = town["charters"]["town_council"]["bodies"].values()
    assert any(b.get("resident_seed_id") == cand["seed_id"]
               and b["name"] == "Hester Gale" for b in bodies)


def test_a_candidate_the_plan_leaves_out_lives_elsewhere():
    cand = featured_resident_seed(81, SHEET)
    town = close_plan(_plan(), candidate_residents=[cand])
    assert cand["seed_id"] not in town["featured_residents"], (
        "no omission repair for a candidate: leaving them out is the answer")
    assert not any(b.get("resident_seed_id") == cand["seed_id"]
                   for b in town["charters"]["town_council"]["bodies"].values())


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Fen", "The mail ferry sets the assessor down at dusk.",
                 time.time()))
    ids = {}
    for name in ("Hester Gale", "The Doctor"):
        key = db.qi("INSERT INTO characters(name,sheet,source,created,"
                    "resource_uid) VALUES(?,?,?,?,?)",
                    (name, json.dumps({"identity": {"name": name}}), "{}",
                     time.time(), name.replace(" ", "_").lower()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,?)", (cid, key, "active", "{}"))
        ids[name] = key
    return cid, ids


def test_an_open_route_is_a_candidate_and_a_chosen_one_is_not(temp_db):
    cid, ids = _story(temp_db)
    hester, doctor = ids["Hester Gale"], ids["The Doctor"]
    clean, prepared = _prepare_cast_histories(cid, {
        "brief": "A stilt town over the fen.",
        "character_histories": [{"char_id": hester, "mode": "auto"},
                                {"char_id": doctor, "mode": "visitor"}]})
    candidates = clean.get("candidate_residents") or []
    assert [c["seed_id"] for c in candidates] == ["character:%d" % hester]
    assert candidates[0]["router"]["verdict"], "the router's reading is evidence"
    routes = {p["char_id"]: p["route"] for p in prepared}
    assert routes[hester]["candidate_seed_id"] == "character:%d" % hester
    assert "candidate_seed_id" not in routes[doctor], "the author chose"
    assert not clean.get("featured_residents")


def test_a_placed_candidate_is_integrated_as_a_resident(temp_db, monkeypatch):
    import world.charter_history as charter_history
    cid, ids = _story(temp_db)
    hester = ids["Hester Gale"]
    _clean, prepared = _prepare_cast_histories(cid, {
        "character_histories": [{"char_id": hester, "mode": "auto"}]})
    seed = "character:%d" % hester
    calls = []
    monkeypatch.setattr(
        charter_history, "integrate_featured_resident",
        lambda cid, char_id, binding, sheet, **kw: calls.append(
            (char_id, binding)) or {"memory_event_keys": []})
    _complete_cast_histories(
        cid, {}, prepared,
        {"ok": True, "featured_residents": {
            seed: {"charter": "town_council", "body": "miller:featured:x"}}})
    assert calls == [(hester, {"charter": "town_council",
                               "body": "miller:featured:x"})]
    assert prepared[0]["route"]["seed_id"] == seed


@pytest.mark.parametrize("room", [True, False])
def test_only_the_room_is_asked(temp_db, monkeypatch, room):
    cid, _ids = _story(temp_db)
    seen = {}

    class Stop(Exception):
        pass

    def capture(lore, brief="", constraints=None, model_call=None):
        seen["constraints"] = constraints or {}
        raise Stop()

    monkeypatch.setattr(charter_generate, "propose_town", capture)
    chat = dict(temp_db.q("SELECT * FROM chats WHERE id=?", (cid,), one=True))
    request = {"brief": "A stilt town.", "generate_history": False,
               "candidate_residents": [featured_resident_seed(81, SHEET)]}
    with pytest.raises(Stop):
        _plan_lived_location(cid, request, chat,
                             town_planner=(lambda p, c: {}) if room else None)
    assert bool(seen["constraints"].get("candidate_residents")) is room
