"""The Director is told what the charter moved since the last beat.

Owner's rule (2026-09-14): the world needs to move every beat. The runtime
already advances every charter every beat by the beat's own seconds; what
was missing is the page hearing of it -- a pot-boy who walked down the
towpath was simply THERE in the next view and no beat said he came.
"""
import time

from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_runtime import charter_moves_since, save_registry


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Moves", "", time.time()))


def _inn(place="taproom", acts=()):
    charter = normalize_charter({
        "key": "inn",
        "upkeeps": {"custom": {"place": "taproom", "level": 1.0, "floor": 0.2,
                               "drift_per_hour": 0.0, "service_per_hour": 1.0}},
        "posts": {"keep": {"place": "taproom", "serves": ["custom"],
                           "requires": {"keep": 1}}},
        "bodies": {"toby": {"place": place, "name": "Toby Callow",
                            "competence": {"keep": 1}}},
        "priority": ["custom"],
        "scene": {"rooms": {"taproom": {"name": "The Taproom"},
                            "towpath": {"name": "The Towpath"},
                            "lock_side": {"name": "The Lock-side"}}},
    })
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    charter["window_acts"] = list(acts)
    return charter


def test_a_body_that_walked_in_is_an_arrival(temp_db):
    cid = _chat(temp_db)
    save_registry(cid, {"inn": _inn(place="lock_side")})
    out = charter_moves_since(cid, {"lock_side"}, {
        "places": {"Toby Callow": "towpath"}, "acts": []})
    assert out["lines"] == [
        "Toby Callow came into The Lock-side from The Towpath since the last beat."]
    assert out["snapshot"]["places"] == {"Toby Callow": "lock_side"}


def test_a_body_that_walked_out_is_a_departure(temp_db):
    cid = _chat(temp_db)
    save_registry(cid, {"inn": _inn(place="towpath")})
    out = charter_moves_since(cid, {"lock_side"}, {
        "places": {"Toby Callow": "lock_side"}, "acts": []})
    assert out["lines"] == [
        "Toby Callow left The Lock-side for The Towpath since the last beat."]


def test_the_first_beat_reports_nothing_and_seeds_the_snapshot(temp_db):
    cid = _chat(temp_db)
    save_registry(cid, {"inn": _inn(place="lock_side")})
    out = charter_moves_since(cid, {"lock_side"}, {})
    assert out["lines"] == []
    assert out["snapshot"]["places"] == {"Toby Callow": "lock_side"}


def test_an_unreported_act_in_the_rooms_is_a_line_once(temp_db):
    cid = _chat(temp_db)
    act = {"actor": "toby", "act": "greet", "other": "", "subject": "",
           "place": "taproom", "at_hours": 12.0}
    save_registry(cid, {"inn": _inn(place="taproom", acts=[act])})
    first = charter_moves_since(cid, {"taproom"}, {
        "places": {"Toby Callow": "taproom"}, "acts": []})
    assert first["lines"] == ["Toby Callow: greet in The Taproom since the last beat."]
    again = charter_moves_since(cid, {"taproom"}, first["snapshot"])
    assert again["lines"] == []


def test_a_move_outside_the_rooms_is_not_the_beats_business(temp_db):
    cid = _chat(temp_db)
    save_registry(cid, {"inn": _inn(place="towpath")})
    out = charter_moves_since(cid, {"lock_side"}, {
        "places": {"Toby Callow": "taproom"}, "acts": []})
    assert out["lines"] == []
