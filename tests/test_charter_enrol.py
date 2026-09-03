"""Enrolment: the deterministic fill behind a person the Director rendered
with no plan behind them (`world/charter_enrol.py`).

THE CLASS. A person the story names is a member of a real institution from
the beat they are seen, never of a placeholder. Measured on the Harrowmere
replay (2026-09-03): seven person mints, six of them shadows of a
post-holder standing beside them, every one held by an ambient charter with
no posts, no upkeeps and berth = the room it was first seen in. That charter
is gone; these tests pin what replaced it.
"""
from __future__ import annotations

import time

import pytest

from world.charter_enrol import (GUEST_STAY_HOURS, HOUSEHOLDS_CHARTER,
                                 berth_in_households, depart_guests,
                                 enrol_person, enrolled_body_key,
                                 households_charter_key, lodging_charter_for,
                                 posts_for_role, seat_open)


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Enrol", "", time.time()))


def _body(name, place, berth=None, post="", **extra):
    out = {"name": name, "place": place, "berth": berth or place,
           "competence": {}, "available": True, "home_post": post}
    out.update(extra)
    return out


def _town():
    """Three institutions in the closer's own vocabulary: a hall with a
    head post and a crew post, an inn whose staff sleep over the taproom
    (a LODGING: workplace and berth in one room), and the households
    charter -- every upkeep it serves is at a house its members sleep in."""
    return {"items": {
        "reeves_hall": {"state": {
            "key": "reeves_hall", "priority": [], "clock_hours": 10.0,
            "upkeeps": {"court": {"place": "reeve_hall"},
                        "ledgers": {"place": "clerk_office"},
                        "gate": {"place": "upland_gate"}},
            "posts": {
                "reeve": {"place": "reeve_hall", "serves": ["court"],
                          "requires": {}, "reports_to": "reeve"},
                "clerk": {"place": "clerk_office", "serves": ["ledgers"],
                          "requires": {}, "reports_to": "reeve"},
                "watchman": {"place": "upland_gate", "serves": ["gate"],
                             "requires": {}, "reports_to": "reeve"}},
            "bodies": {
                "r1": _body("Halin Nook", "reeve_hall", "reeve_house", "reeve"),
                "c1": _body("Osric Fell", "clerk_office", "clerk_lodging",
                            "clerk"),
                "w1": _body("Bran Gate", "upland_gate", "gate_house",
                            "watchman"),
            },
            "watch": {"reeve": "r1", "clerk": "c1", "watchman": "w1"},
        }},
        "ford_inn": {"state": {
            "key": "ford_inn", "priority": [], "clock_hours": 10.0,
            "upkeeps": {"taproom": {"place": "inn_common"}},
            "posts": {"innkeeper": {"place": "inn_common",
                                    "serves": ["taproom"], "requires": {},
                                    "reports_to": "innkeeper"}},
            "bodies": {"i1": _body("Tam Ashwell", "inn_common", "inn_common",
                                   "innkeeper")},
            "watch": {"innkeeper": "i1"},
        }},
        "households": {"state": {
            "key": "households", "priority": [], "clock_hours": 10.0,
            "upkeeps": {"keep_house_a": {"place": "house_a"},
                        "keep_house_b": {"place": "house_b"}},
            "posts": {"householder_a": {"place": "house_a",
                                        "serves": ["keep_house_a"],
                                        "requires": {}},
                      "householder_b": {"place": "house_b",
                                        "serves": ["keep_house_b"],
                                        "requires": {}}},
            "bodies": {
                "h1": _body("Ada Fen", "house_a"),
                **{"hb%d" % n: _body("Bryn %d" % n, "house_b")
                   for n in range(8)},
            },
            "watch": {},
        }},
    }}


def _scene():
    """reeve_hall - lane - house_b - house_a: house_b is nearer the hall."""
    return {"rooms": {
        "reeve_hall": {"name": "Hall", "adjacent": [{"to": "lane", "barrier": "open"}]},
        "lane": {"name": "Lane", "adjacent": [
            {"to": "reeve_hall", "barrier": "open"},
            {"to": "house_b", "barrier": "open_door"},
            {"to": "inn_common", "barrier": "open_door"}]},
        "house_b": {"name": "House B", "adjacent": [
            {"to": "lane", "barrier": "open_door"},
            {"to": "house_a", "barrier": "open_door"}]},
        "house_a": {"name": "House A", "adjacent": [{"to": "house_b", "barrier": "open_door"}]},
        "inn_common": {"name": "Inn", "adjacent": [{"to": "lane", "barrier": "open_door"}]},
    }, "positions": {}, "entities": {}}


def _need(name, room, description="", role=""):
    return {"kind": "person",
            "surface": {"name": name, "room": room,
                        "description": description, "role": role}}


@pytest.fixture
def town(temp_db):
    from world.charter_runtime import save_registry
    cid = _chat(temp_db)
    save_registry(cid, _town())
    return cid


class TestTheClassesOfEnrolment:
    def test_a_role_naming_a_post_with_an_open_seat_enrols_there(self, temp_db, town):
        from world.charter_runtime import registry_for
        rec = enrol_person(town, _need("The Clerk", "clerk_office",
                                       "A thin clerk with ink on his fingers."))
        assert rec["how"] == "post" and rec["charter"] == "reeves_hall"
        assert rec["post"] == "clerk"
        state = registry_for(town)["items"]["reeves_hall"]["state"]
        body = state["bodies"][rec["body"]]
        assert body["home_post"] == "clerk" and body["place"] == "clerk_office"
        # The post's own reporting chain comes with the seat.
        assert state["posts"]["clerk"]["reports_to"] == "reeve"
        # Sleeps where the post's holders sleep, not where it was seen.
        assert body["berth"] == "clerk_lodging"
        # Needs and roster exist for the new body, so the next window can
        # live it.
        assert rec["body"] in state["needs"] and rec["body"] in state["roster"]

    def test_a_compound_role_is_its_head_noun(self, temp_db, town):
        """"The bridge watchman" is a watchman with a station in front
        (the replay's t13 mint, which no room pool could bind)."""
        rec = enrol_person(town, _need("The Bridge Watchman", "bridge_road"))
        assert rec["how"] == "post" and rec["post"] == "watchman"

    def test_a_head_post_already_held_is_not_seated_twice(self, temp_db, town):
        """One reeve. A second one enrols as a householder and the record
        says why."""
        rec = enrol_person(town, _need("The Reeve", "reeve_hall"))
        assert rec["how"] != "post" and rec["post"] == ""
        assert any("seat" in note for note in rec["notes"])

    def test_standing_in_a_lodging_with_no_role_is_a_guest(self, temp_db, town):
        from world.charter_runtime import registry_for
        rec = enrol_person(town, _need("Marrow", "inn_common",
                                       "A tired traveller in a dusty cloak."))
        assert rec["how"] == "guest" and rec["charter"] == "ford_inn"
        body = registry_for(town)["items"]["ford_inn"]["state"]["bodies"][rec["body"]]
        assert body["guest"] is True
        assert body["guest_until"] == pytest.approx(10.0 + GUEST_STAY_HOURS)
        assert body["berth"] == "inn_common"

    def test_a_guest_whose_stay_ran_out_departs(self, temp_db, town):
        from world.charter_model import normalize_charter
        from world.charter_runtime import (background_presence_records,
                                           registry_for)
        rec = enrol_person(town, _need("Marrow", "inn_common"))
        state = registry_for(town)["items"]["ford_inn"]["state"]
        early, gone = depart_guests(dict(state), 10.0 + GUEST_STAY_HOURS - 1)
        assert gone == []
        late, gone = depart_guests(dict(state), 10.0 + GUEST_STAY_HOURS)
        assert gone == [rec["body"]]
        body = late["bodies"][rec["body"]]
        assert body["departed"] and not body["available"] and body["place"] == ""
        # The mark survives normalization, and nobody lists the departed.
        again = normalize_charter(late)
        assert again["bodies"][rec["body"]]["departed"] is True
        from world.charter_runtime import save_registry
        reg = registry_for(town)
        reg = {"items": {**reg["items"], "ford_inn": {"state": late}}}
        save_registry(town, reg)
        names = set(background_presence_records(town, places={"inn_common", ""}))
        assert "Marrow" not in names

    def test_a_householder_berths_in_the_nearest_house_with_room(self, temp_db, town):
        """house_b is one hop nearer the hall but full; house_a has room."""
        rec = enrol_person(town, _need("Wat Penny", "reeve_hall"),
                           scene=_scene())
        assert rec["how"] == "household" and rec["charter"] == "households"
        assert rec["berth"] == "house_a" and rec["room_need"] is False

    def test_every_house_full_is_the_least_full_house_and_a_room_owed(self, temp_db):
        from world.charter_runtime import save_registry
        cid = _chat(temp_db)
        reg = _town()
        bodies = reg["items"]["households"]["state"]["bodies"]
        for n in range(8):
            bodies["ha%d" % n] = _body("Ada %d" % n, "house_a")
        save_registry(cid, reg)
        rec = enrol_person(cid, _need("Wat Penny", "reeve_hall"))
        assert rec["how"] == "household" and rec["room_need"] is True
        assert rec["berth"] in ("house_a", "house_b")

    def test_a_story_with_no_town_mints_a_households_charter(self, temp_db):
        from world.charter_runtime import registry_for
        cid = _chat(temp_db)
        rec = enrol_person(cid, _need("Dock Hand", "quay"))
        assert rec["how"] == "minted_households"
        assert rec["charter"] == HOUSEHOLDS_CHARTER and rec["room_need"] is True
        state = registry_for(cid)["items"][HOUSEHOLDS_CHARTER]["state"]
        assert state["bodies"][rec["body"]]["place"] == "quay"
        assert not state["posts"] and not state["upkeeps"]
        assert "ambient" not in registry_for(cid)["items"]

    def test_a_person_the_registry_already_holds_is_left_there(self, temp_db, town):
        from world.charter_runtime import registry_for
        before = registry_for(town)["items"]["ford_inn"]["state"]["bodies"]
        rec = enrol_person(town, _need("Tam Ashwell", "lane"))
        assert rec["how"] == "held"
        assert rec["ref"] == {"charter": "ford_inn", "body": "i1"}
        assert registry_for(town)["items"]["ford_inn"]["state"]["bodies"].keys() == before.keys()

    def test_the_same_name_is_the_same_body(self, temp_db, town):
        first = enrol_person(town, _need("Dock Hand", "lane"))
        again = enrol_person(town, _need("Dock Hand", "reeve_hall"))
        assert again["how"] == "held" and again["ref"] == first["ref"]
        assert enrolled_body_key("Dock Hand") == first["body"]


class TestWhatWasSeenWins:
    def test_the_dealt_surface_yields_to_the_description(self, temp_db, town):
        """A description naming another value of a dealt axis's pool takes
        that value: what the Director saw was seen; the plan behind it may
        add and never contradict."""
        from world.charter_runtime import registry_for
        from world.charter_surface import AXES, default_looks, deal_surface
        looks = default_looks()
        key = enrolled_body_key("The Clerk")
        dealt = deal_surface("reeves_hall", key, looks)
        axis = AXES[0]
        other = next(v for v in looks[axis] if v != dealt[axis])
        rec = enrol_person(town, _need(
            "The Clerk", "clerk_office",
            "A %s clerk with ink on his fingers." % other))
        surface = registry_for(town)["items"]["reeves_hall"]["state"]["bodies"][rec["body"]]["surface"]
        assert surface[axis] == other
        assert surface["rendered"].startswith("A %s clerk" % other)

    def test_a_description_naming_nothing_leaves_the_dealt_surface(self, temp_db, town):
        from world.charter_runtime import registry_for
        from world.charter_surface import AXES
        rec = enrol_person(town, _need("The Clerk", "clerk_office",
                                       "A clerk, nothing more."))
        surface = registry_for(town)["items"]["reeves_hall"]["state"]["bodies"][rec["body"]]["surface"]
        assert all(surface.get(axis) for axis in AXES)
        assert surface["rendered"] == "A clerk, nothing more."


class TestTheClassesAreReadFromTheRegistry:
    def test_the_households_charter_is_the_one_that_keeps_its_own_berths(self):
        reg = _town()
        assert households_charter_key(reg) == "households"
        # By the class, not the key: rename it and it is still the one.
        reg["items"]["guild"] = reg["items"].pop("households")
        reg["items"]["guild"]["state"]["key"] = "guild"
        assert households_charter_key(reg) == "guild"

    def test_a_lodging_is_a_workplace_that_is_also_a_berth(self):
        reg = _town()
        assert lodging_charter_for(reg, "inn_common") == "ford_inn"
        assert lodging_charter_for(reg, "reeve_hall") is None
        assert lodging_charter_for(reg, "house_a") is None

    def test_a_seat_is_open_under_the_ceiling(self):
        state = _town()["items"]["reeves_hall"]["state"]
        assert seat_open(state, "clerk")      # a crew post with one holder
        assert not seat_open(state, "reeve")  # the head, held
        assert not seat_open(state, "nobody")

    def test_a_role_resolves_through_the_posts_own_forms(self):
        reg = _town()
        assert posts_for_role(reg, ["clerk"]) == [("reeves_hall", "clerk")]
        assert posts_for_role(reg, ["bridge", "watchman"]) == [("reeves_hall", "watchman")]
        assert posts_for_role(reg, []) == []

    def test_the_nearest_house_under_the_ceiling(self):
        state = _town()["items"]["households"]["state"]
        assert berth_in_households(state, "reeve_hall", _scene()) == ("house_a", False)
        state["bodies"]["hb0"]["berth"] = "house_a"  # house_b now has room
        state["bodies"]["hb0"]["place"] = "house_a"
        assert berth_in_households(state, "reeve_hall", _scene()) == ("house_b", False)
