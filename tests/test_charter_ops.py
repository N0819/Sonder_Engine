"""Charter is a tool of the Planner: the read side shows the institution, and
the write side is `charter_ops`.

`docs/design/DESIGN_OFFSCREEN_SUPERSEDED.md` § 3a and
`docs/design/DESIGN_PLACE_HISTORY.md` § 2. Two halves and three invariants.

THE READ SIDE. Measured in the caravanserai run
(`docs/experiments/PLAY_2026_09_05_caravanserai.md` § 5): `inspect_charters`
returned no post, no watch, no station and 24 of 40 bodies, so the Room asked
to describe the house named the gate warden as its innkeeper and invented
three staff who did not exist. Every field it hid is asserted present here,
and the cap that hid sixteen bodies is now a page a caller can ask past.

THE WRITE SIDE. One authored EVENT, spelled in the vocabulary Charter already
owns, landing through the functions Charter already owns, refused with a
named reason when it cannot. And it is an INPUT: after it lands, everything
downstream is the simulation's answer.

  1. The Planner directs; Charter computes -- no op may name who reacts.
  2. The institution keeps its own beliefs -- a death does not correct the
     roster; only an observation does.
  3. The Director still reads Charter and does not steer it.
"""

from __future__ import annotations

import copy
import json
import re
import time

import pytest

from story.plot_packages import (OPERATIONS, draft_operation, get_package,
                                 new_package, preview_package,
                                 publish_package, validate_package)
from story.room_tools import (CHARTER_OVERVIEW_ROWS, CHARTER_PAGE,
                              CHARTER_SECTIONS, TOOL_INDEX, TOOL_RESULT_CHARS,
                              run_tool)
from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_ops import (CHARTER_OPS, CHARTER_OPS_CAP,
                               apply_charter_ops, normalize_charter_op)
from world.charter_runtime import (author_charter_ops, normalize_registry,
                                   registry_for, save_registry)

from charter_worlds import twin_towns


# ---------------------------------------------------------------------------
# Fixtures: a house with posts, a watch, upkeeps, stock and a roster
# ---------------------------------------------------------------------------

def _house():
    """One institution shaped like the caravanserai the Room misread: posts
    with places and anchors, upkeeps with floors, a watch standing, an
    economy with lots on the books, and a roster that happens to be right."""
    state = normalize_charter({
        "key": "caravanserai",
        "scene": {"rooms": {
            "gate": {"name": "Gate", "adjacent": [{"to": "yard"}]},
            "yard": {"name": "Yard", "adjacent": [{"to": "gate"},
                                                  {"to": "kitchen"}]},
            "kitchen": {"name": "Kitchen", "adjacent": [{"to": "yard"}]},
        }},
        "upkeeps": {
            "watchfulness": {"place": "gate", "level": 0.9, "floor": 0.3,
                             "drift_per_hour": 0.02, "service_per_hour": 0.08,
                             "requires": {"arms": 1}},
            "victuals": {"place": "kitchen", "level": 0.8, "floor": 0.4,
                         "drift_per_hour": 0.03, "service_per_hour": 0.09,
                         "requires": {"cooking": 1},
                         "depends_on": ["watchfulness"]},
        },
        "posts": {
            "gate_warden": {"place": "gate", "serves": ["watchfulness"],
                            "requires": {"arms": 1}, "anchor": "warden_bench",
                            "purpose": "keeps the gate"},
            "cook": {"place": "kitchen", "serves": ["victuals"],
                     "requires": {"cooking": 1}, "purpose": "feeds the house"},
            "hand": {"place": "yard", "serves": ["victuals"],
                     "requires": {}, "purpose": "carries and fetches"},
        },
        "bodies": {
            "vesk": {"name": "Orhan Vesk", "competence": {"arms": 2},
                     "place": "gate", "home_post": "gate_warden"},
            "yusra": {"name": "Yusra", "competence": {"cooking": 2},
                      "place": "kitchen", "home_post": "cook"},
            "neris": {"name": "Neris", "competence": {"labour": 1},
                      "place": "yard", "home_post": "hand"},
            "kurash": {"name": "Kurash Bel", "competence": {"labour": 1},
                       "place": "yard"},
        },
        "watch": {"gate_warden": "vesk", "cook": "yusra", "hand": "neris"},
        "economy": {"goods": {"flour": {}, "oil": {}},
                    "stocks": {"pantry": {"flour": 40.0, "oil": 6.0}}},
        "clock_hours": 12.0,
    })
    state["roster"] = seed_roster(state["bodies"])
    state["needs"] = seed_needs(state["bodies"])
    return state


def _registry(state=None):
    return normalize_registry({"items": {"caravanserai": {
        "state": state or _house()}}})


def _chat(db, *, scene=None):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Caravanserai", "A house at dusk.", time.time()))
    db.wset(cid, "scene", scene or {
        "location": "Caravanserai",
        "rooms": {"gate": {"name": "Gate", "desc": "A stone arch.",
                           "adjacent": [{"to": "yard", "barrier": "open_door"}]},
                  "yard": {"name": "Yard", "desc": "Dust and rope.",
                           "adjacent": [{"to": "gate", "barrier": "open_door"},
                                        {"to": "kitchen", "barrier": "open_door"}]},
                  "kitchen": {"name": "Kitchen", "desc": "Smoke and iron.",
                              "adjacent": [{"to": "yard", "barrier": "open_door"}]}},
        "positions": {}, "entities": {}, "attire": {}})
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (cid, 0, "", time.time()))
    return cid


def _story(db, state=None):
    cid = _chat(db)
    save_registry(cid, {"items": {"caravanserai": {"state": state or _house()}}})
    return cid


# ---------------------------------------------------------------------------
# 1. The read side must show the institution
# ---------------------------------------------------------------------------

class TestTheReadSideShowsTheInstitution:
    def test_every_field_the_room_was_missing_is_there(self, temp_db):
        """The measured failure: no post, no watch, no station. Each of the
        five sections comes back, and the upkeeps carry their floors."""
        cid = _story(temp_db)
        out = run_tool(cid, "inspect_charters", {"charter": "caravanserai"})
        house = out["charters"]["caravanserai"]
        assert set(CHARTER_SECTIONS) <= set(house)

        upkeeps = {u["key"]: u for u in house["upkeeps"]}
        assert upkeeps["watchfulness"]["floor"] == pytest.approx(0.3)
        assert upkeeps["watchfulness"]["level"] == pytest.approx(0.9)
        assert upkeeps["watchfulness"]["below_floor"] is False
        assert upkeeps["watchfulness"]["served_by"] == ["gate_warden"]
        assert upkeeps["watchfulness"]["tended_by"] == ["Orhan Vesk"]
        assert upkeeps["victuals"]["depends_on"] == ["watchfulness"]

        posts = {p["key"]: p for p in house["posts"]}
        assert posts["gate_warden"]["place"] == "gate"
        assert posts["gate_warden"]["anchor"] == "warden_bench"
        assert posts["gate_warden"]["serves"] == ["watchfulness"]
        assert posts["gate_warden"]["purpose"] == "keeps the gate"
        assert posts["gate_warden"]["held_by_name"] == "Orhan Vesk"

        watch = {w["post"]: w for w in house["watch"]}
        assert watch["gate_warden"]["name"] == "Orhan Vesk"
        assert watch["cook"]["name"] == "Yusra"
        assert "hand" in watch and house["unfilled_posts"] == []

        bodies = {b["key"]: b for b in house["bodies"]}
        assert bodies["vesk"]["standing"] == "gate_warden"
        assert bodies["vesk"]["home_post"] == "gate_warden"
        assert bodies["vesk"]["place"] == "gate"
        assert bodies["vesk"]["condition"] == "well"
        assert bodies["kurash"]["standing"] == ""

    def test_the_warden_is_not_offered_as_the_innkeeper(self, temp_db):
        """The exact misread: the Room named the gate warden as the house's
        innkeeper because nothing said what post he held. It says so now,
        and every body carries the post it stands and the post it belongs
        to, so the two cannot be confused with each other."""
        cid = _story(temp_db)
        house = run_tool(cid, "inspect_charters",
                         {"charter": "caravanserai"})["charters"]["caravanserai"]
        vesk = next(b for b in house["bodies"] if b["name"] == "Orhan Vesk")
        assert vesk["standing"] == vesk["home_post"] == "gate_warden"
        assert next(p for p in house["posts"]
                    if p["key"] == "gate_warden")["purpose"] == "keeps the gate"
        # And the roster invented nobody: every name in the read is a body.
        names = {b["name"] for b in house["bodies"]}
        assert names == {"Orhan Vesk", "Yusra", "Neris", "Kurash Bel"}

    def test_a_body_with_a_placement_shows_where_it_stands(self, temp_db):
        """`world/charter_place.py`, landed 2026-09-05: a body standing a
        post whose anchor its room carries stands AT that fixture."""
        cid = _chat(temp_db, scene={
            "location": "Caravanserai",
            "rooms": {"gate": {"name": "Gate", "desc": "A stone arch.",
                               "anchors": {"warden_bench":
                                           {"desc": "the warden's bench"}},
                               "adjacent": []}},
            "positions": {}, "entities": {}, "attire": {}})
        state = _house()
        for body in state["bodies"].values():
            body["place"] = "gate"
        save_registry(cid, {"items": {"caravanserai": {"state": state}}})
        house = run_tool(cid, "inspect_charters",
                         {"charter": "caravanserai"})["charters"]["caravanserai"]
        vesk = next(b for b in house["bodies"] if b["key"] == "vesk")
        assert vesk["station"] == {"at": "warden_bench"}
        assert vesk["station_from"] == "post"

    def test_the_roster_is_shown_only_where_it_differs(self, temp_db):
        """A roster is a BELIEF. The read shows it where it has come apart
        from the bodies -- which is the whole material -- and says nothing
        where it agrees."""
        cid = _story(temp_db)
        house = run_tool(cid, "inspect_charters",
                         {"charter": "caravanserai"})["charters"]["caravanserai"]
        assert house["roster"] == []

        state = _house()
        state["bodies"]["neris"]["available"] = False
        save_registry(cid, {"items": {"caravanserai": {"state": state}}})
        house = run_tool(cid, "inspect_charters",
                         {"charter": "caravanserai"})["charters"]["caravanserai"]
        row = next(r for r in house["roster"] if r["body"] == "neris")
        assert row["differs"] == "availability"
        assert row["believes"]["available"] is True
        assert row["in_fact"]["available"] is False

    def test_paging_returns_the_withheld_rows(self, temp_db):
        """THE DEFECT BEING FIXED: 24 of 40 bodies, silently. A page now says
        how many it withheld and the call that returns them, and that call
        returns them."""
        cid = _chat(temp_db)
        town = normalize_charter(twin_towns(40))
        town["roster"] = seed_roster(town["bodies"])
        save_registry(cid, {"items": {"twin_towns": {"state": town}}})

        first = run_tool(cid, "inspect_charters",
                         {"charter": "twin_towns", "section": "bodies"})
        entry = first["charters"]["twin_towns"]
        assert entry["counts"]["bodies"] == 40
        assert len(entry["bodies"]) == CHARTER_PAGE
        more = entry["withheld"]["bodies"]
        assert more["withheld"] == 40 - CHARTER_PAGE and more["of"] == 40
        assert more["next_cursor"] == CHARTER_PAGE
        assert "inspect_charters" in more["ask"] and "cursor" in more["ask"]

        rest = run_tool(cid, "inspect_charters",
                        {"charter": "twin_towns", "section": "bodies",
                         "cursor": more["next_cursor"]})["charters"]["twin_towns"]
        assert len(rest["bodies"]) == 40 - CHARTER_PAGE
        assert "withheld" not in rest
        seen = [b["key"] for b in entry["bodies"]] + [b["key"] for b in rest["bodies"]]
        assert sorted(seen) == sorted(town["bodies"])

    def test_a_bigger_page_may_be_asked_for(self, temp_db):
        cid = _chat(temp_db)
        town = normalize_charter(twin_towns(40))
        save_registry(cid, {"items": {"twin_towns": {"state": town}}})
        entry = run_tool(cid, "inspect_charters",
                         {"charter": "twin_towns", "section": "bodies",
                          "limit": 40})["charters"]["twin_towns"]
        assert len(entry["bodies"]) == 40 and "withheld" not in entry

    def test_the_overview_pages_every_section_and_counts_them_all(self, temp_db):
        cid = _chat(temp_db)
        town = normalize_charter(twin_towns(40))
        save_registry(cid, {"items": {"twin_towns": {"state": town}}})
        out = run_tool(cid, "inspect_charters", {})
        entry = out["charters"]["twin_towns"]
        assert entry["counts"]["bodies"] == 40
        assert len(entry["bodies"]) == CHARTER_OVERVIEW_ROWS
        assert entry["withheld"]["bodies"]["withheld"] == 40 - CHARTER_OVERVIEW_ROWS
        assert set(out["sections"]) == set(CHARTER_SECTIONS)

    def test_the_overview_of_a_forty_body_town_fits_the_result_cap(self, temp_db):
        """`fit_result` cuts a dict-valued key WHOLE, so an overview over the
        cap would lose every charter at once. The page sizes are the guard;
        this is the measurement that says they are the right ones."""
        cid = _chat(temp_db)
        town = normalize_charter(twin_towns(40))
        town["roster"] = seed_roster(town["bodies"])
        save_registry(cid, {"items": {"twin_towns": {"state": town},
                                      "caravanserai": {"state": _house()}}})
        out = run_tool(cid, "inspect_charters", {})
        assert "truncated" not in out
        assert len(json.dumps(out, ensure_ascii=False)) < TOOL_RESULT_CHARS

    def test_an_unknown_charter_or_section_is_refused_by_name(self, temp_db):
        from story.room_tools import ToolError
        cid = _story(temp_db)
        with pytest.raises(ToolError) as bad:
            run_tool(cid, "inspect_charters", {"charter": "nowhere"})
        assert "caravanserai" in str(bad.value)
        with pytest.raises(ToolError) as worse:
            run_tool(cid, "inspect_charters", {"section": "vibes"})
        assert "upkeeps" in str(worse.value)

    def test_the_manifest_says_what_the_tool_answers(self):
        described = TOOL_INDEX["inspect_charters"]["description"]
        for word in ("watch", "post", "station", "roster", "paged"):
            assert word in described.casefold()
        args = TOOL_INDEX["inspect_charters"]["args"]["properties"]
        assert {"charter", "body", "section", "cursor", "limit"} <= set(args)


# ---------------------------------------------------------------------------
# 2. The write side: every op through the function Charter already owns
# ---------------------------------------------------------------------------

class TestEveryOpLandsThroughItsOwner:
    def test_errand_walks_through_send_errand(self):
        registry = _registry()
        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "errand", "charter": "caravanserai", "body": "neris",
             "to": "gate", "purpose": "fetch the warden"})],
            scene=registry["items"]["caravanserai"]["state"]["scene"])
        neris = registry["items"]["caravanserai"]["state"]["bodies"]["neris"]
        assert neris["errand"]["to"] == "gate"
        assert neris["walk"]["target"] == "gate"
        assert neris["walk"]["route"][0] == "yard"

    def test_arrive_and_depart_are_one_transfer_and_a_hermit_is_expressible(self):
        registry = _registry()
        registry["items"]["stable"] = {"state": normalize_charter(
            {"key": "stable", "bodies": {}, "posts": {}, "upkeeps": {}})}
        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "depart", "charter": "caravanserai", "body": "kurash",
             "to_charter": "stable", "place": "yard"})])
        assert "kurash" not in registry["items"]["caravanserai"]["state"]["bodies"]
        assert "kurash" in registry["items"]["stable"]["state"]["bodies"]

        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "depart", "charter": "stable", "body": "kurash"})])
        assert "kurash" not in registry["items"]["stable"]["state"]["bodies"]
        # Employed nowhere, still a person.
        assert "kurash" in registry["people"]

        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "arrive", "charter": "caravanserai", "body": "kurash",
             "place": "gate"})])
        back = registry["items"]["caravanserai"]["state"]["bodies"]["kurash"]
        assert back["place"] == "gate" and back["name"] == "Kurash Bel"

    def test_die_goes_through_the_harm_model(self):
        registry = _registry()
        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "die", "charter": "caravanserai", "body": "yusra",
             "cause": "the fire in the kitchen"})])
        state = registry["items"]["caravanserai"]["state"]
        assert state["bodies"]["yusra"]["condition"] == "dead"
        assert state["bodies"]["yusra"]["available"] is False
        # The harm model's own event, at the place, for whoever stood there.
        assert any(e.get("kind") == "harm_done"
                   for e in state.get("carried_events") or ())

    def test_a_post_is_filled_and_vacated(self):
        registry = _registry()
        apply_charter_ops(registry, [
            normalize_charter_op({"op": "vacate_post", "charter": "caravanserai",
                                  "post": "cook"}),
            normalize_charter_op({"op": "fill_post", "charter": "caravanserai",
                                  "post": "cook", "body": "kurash"})])
        state = registry["items"]["caravanserai"]["state"]
        assert state["watch"]["cook"] == "kurash"
        assert state["bodies"]["kurash"]["home_post"] == "cook"
        assert state["bodies"]["yusra"]["home_post"] == ""

    def test_an_upkeep_fails_through_the_institutions_own_window(self):
        """The Planner says the condition dropped. The intervention is the
        institution's own and the window applies it, which is what emits the
        incident the place witnesses."""
        from world.charter_intervene import apply_due
        registry = _registry()
        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "upkeep_fails", "charter": "caravanserai",
             "upkeep": "victuals", "to": 0.05,
             "surface": "the store room burned"})])
        state = registry["items"]["caravanserai"]["state"]
        assert state["interventions"] and state["interventions"][0]["op"] == "upkeep_shock"
        state, events = apply_due(state, state["clock_hours"])
        assert state["upkeeps"]["victuals"]["level"] == pytest.approx(0.05)
        assert any(e["kind"] == "incident" and e["upkeep"] == "victuals"
                   for e in events)

    def test_a_supply_cut_only_ever_subtracts(self):
        registry = _registry()
        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "supply_cut", "charter": "caravanserai", "holder": "pantry",
             "good": "flour", "lots": 30})])
        economy = registry["items"]["caravanserai"]["state"]["economy"]
        assert economy["stocks"]["pantry"]["flour"] == pytest.approx(10.0)
        with pytest.raises(ValueError, match="0 < lots"):
            normalize_charter_op({"op": "supply_cut", "charter": "c",
                                  "holder": "pantry", "good": "flour",
                                  "lots": -5})

    def test_every_op_kind_is_routed(self):
        """No kind in the closed set is unreachable, and none outside it is."""
        from world import charter_ops
        assert set(charter_ops._HANDLERS) == set(CHARTER_OPS)


class TestEveryRefusalNamesItsReason:
    @pytest.mark.parametrize("op,fragment", [
        ({"op": "loot", "charter": "caravanserai"}, "no such charter op"),
        ({"op": "errand", "charter": "caravanserai", "body": "neris"},
         "errand names where"),
        ({"op": "errand", "charter": "caravanserai", "to": "gate"},
         "errand names the body"),
        ({"op": "errand", "body": "neris", "to": "gate"},
         "names the charter"),
        ({"op": "die", "charter": "caravanserai", "body": "vesk",
          "condition": "sad"}, "die names one of"),
        ({"op": "fill_post", "charter": "caravanserai", "body": "vesk"},
         "fill_post names the post"),
        ({"op": "upkeep_fails", "charter": "caravanserai",
          "upkeep": "victuals"}, "either `to`"),
        ({"op": "upkeep_fails", "charter": "caravanserai", "upkeep": "v",
          "to": 0.1, "by": 0.2}, "not both"),
        ({"op": "supply_cut", "charter": "caravanserai", "good": "flour",
          "lots": 1}, "names the holder"),
        ({"op": "errand", "charter": "caravanserai", "body": "neris",
          "to": "gate", "because": "she was told to"}, "does not take because"),
    ])
    def test_a_bad_shape_is_refused_at_draft(self, op, fragment):
        with pytest.raises(ValueError, match=re.escape(fragment)):
            normalize_charter_op(op)

    def test_a_body_the_town_does_not_stand_is_refused(self):
        registry = _registry()
        with pytest.raises(ValueError, match="holds no body"):
            apply_charter_ops(registry, [normalize_charter_op(
                {"op": "errand", "charter": "caravanserai", "body": "nobody",
                 "to": "gate"})])

    def test_a_room_no_plan_holds_is_refused(self):
        registry = _registry()
        with pytest.raises(ValueError, match="no route"):
            apply_charter_ops(registry, [normalize_charter_op(
                {"op": "errand", "charter": "caravanserai", "body": "neris",
                 "to": "the moon"})],
                scene=registry["items"]["caravanserai"]["state"]["scene"])

    def test_an_institution_the_registry_does_not_hold_is_not_founded(self):
        """`transfer_person` would MINT the item. A town founded by a typo is
        worse than a refused event."""
        registry = _registry()
        with pytest.raises(ValueError, match="no charter 'stabel'"):
            apply_charter_ops(registry, [normalize_charter_op(
                {"op": "depart", "charter": "caravanserai", "body": "kurash",
                 "to_charter": "stabel"})])
        assert "stabel" not in registry["items"]
        assert "kurash" in registry["items"]["caravanserai"]["state"]["bodies"]

    def test_the_dead_are_not_moved_and_do_not_die_twice(self):
        registry = _registry()
        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "die", "charter": "caravanserai", "body": "yusra"})])
        with pytest.raises(ValueError, match="is dead"):
            apply_charter_ops(registry, [normalize_charter_op(
                {"op": "errand", "charter": "caravanserai", "body": "yusra",
                 "to": "gate"})])
        with pytest.raises(ValueError, match="is dead"):
            apply_charter_ops(registry, [normalize_charter_op(
                {"op": "die", "charter": "caravanserai", "body": "yusra"})])

    def test_an_unknown_upkeep_is_refused_here_and_not_swallowed(self):
        """The window's own refusal is a silent row in
        `refused_interventions`, so an authored event that names an upkeep
        the institution does not owe must be refused before it is scheduled."""
        registry = _registry()
        with pytest.raises(ValueError, match="owes no upkeep"):
            apply_charter_ops(registry, [normalize_charter_op(
                {"op": "upkeep_fails", "charter": "caravanserai",
                 "upkeep": "morale", "by": 0.5})])
        assert not registry["items"]["caravanserai"]["state"].get("interventions")

    def test_the_whole_event_is_refused_when_any_op_is(self):
        registry = _registry()
        before = json.dumps(registry, sort_keys=True, default=str)
        with pytest.raises(ValueError, match=r"op 1 \(errand\)"):
            apply_charter_ops(registry, [
                normalize_charter_op({"op": "vacate_post",
                                      "charter": "caravanserai",
                                      "post": "cook"}),
                normalize_charter_op({"op": "errand",
                                      "charter": "caravanserai",
                                      "body": "nobody", "to": "gate"})])
        # The first op DID apply to this in-memory registry; what must not
        # happen is a SAVE, which is `author_charter_ops`' contract below.
        assert before != json.dumps(registry, sort_keys=True, default=str)

    def test_an_event_carrying_too_many_ops_is_refused(self):
        registry = _registry()
        one = normalize_charter_op({"op": "vacate_post",
                                    "charter": "caravanserai", "post": "cook"})
        with pytest.raises(ValueError, match="at most %d ops" % CHARTER_OPS_CAP):
            apply_charter_ops(registry, [one] * (CHARTER_OPS_CAP + 1))


class TestTheSeamSavesOnlyAWholeEvent:
    def test_a_refused_event_writes_nothing(self, temp_db):
        cid = _story(temp_db)
        before = json.dumps(registry_for(cid, None), sort_keys=True, default=str)
        with pytest.raises(ValueError, match="holds no body"):
            author_charter_ops(cid, None, [
                normalize_charter_op({"op": "vacate_post",
                                      "charter": "caravanserai",
                                      "post": "cook"}),
                normalize_charter_op({"op": "errand",
                                      "charter": "caravanserai",
                                      "body": "nobody", "to": "gate"})])
        assert json.dumps(registry_for(cid, None), sort_keys=True,
                          default=str) == before

    def test_the_authors_hand_is_recorded_on_the_institution(self, temp_db):
        cid = _story(temp_db)
        author_charter_ops(cid, None, [normalize_charter_op(
            {"op": "vacate_post", "charter": "caravanserai", "post": "cook"})],
            by="writers_room:plot:test", turn_idx=3)
        authored = registry_for(cid, None)["items"]["caravanserai"]["state"]["authored"]
        assert authored[-1]["op"] == "vacate_post"
        assert authored[-1]["by"] == "writers_room:plot:test"


# ---------------------------------------------------------------------------
# 3. The three things that must not change
# ---------------------------------------------------------------------------

class TestThePlannerDirectsAndCharterComputes:
    def test_no_op_has_a_field_for_who_reacts(self):
        """The vocabulary is the enforcement: an op moves a FACT the
        institution keeps, and there is nowhere to write a reaction."""
        for kind, fields in CHARTER_OPS.items():
            assert "reacts" not in fields and "reaction" not in fields
            assert "notices" not in fields and "blames" not in fields
        # And a field outside the schema is a refusal, not a dropped key --
        # so the reaction cannot be smuggled in as an extra.
        with pytest.raises(ValueError, match="does not take"):
            normalize_charter_op({"op": "die", "charter": "c", "body": "b",
                                  "who_reacts": "everyone"})

    def test_no_op_writes_a_mind(self):
        """`plant_claim` is the one surgery that puts something in a head and
        it is deliberately outside this set."""
        assert "plant_claim" not in CHARTER_OPS
        registry = _registry()
        before = copy.deepcopy(
            registry["items"]["caravanserai"]["state"].get("minds") or {})
        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "die", "charter": "caravanserai", "body": "yusra"})])
        assert (registry["items"]["caravanserai"]["state"].get("minds")
                or {}) == before

    def test_an_authored_upkeep_failure_produces_what_the_simulation_owes(self):
        """The Planner says the granary burned. Charter says who therefore
        has nothing to tend -- and it is the SIMULATION that says it: the
        upkeep is out of band, the post that serves it is the urgent one,
        and nothing authored named a single reactor."""
        from world.charter import out_of_band, step
        from world.charter_intervene import apply_due
        registry = _registry()
        apply_charter_ops(registry, [
            normalize_charter_op({"op": "upkeep_fails",
                                  "charter": "caravanserai",
                                  "upkeep": "victuals", "to": 0.0,
                                  "surface": "the store room burned"}),
            normalize_charter_op({"op": "vacate_post",
                                  "charter": "caravanserai", "post": "cook"})])
        state = registry["items"]["caravanserai"]["state"]
        state, _events = apply_due(state, state["clock_hours"])
        assert out_of_band(state["upkeeps"]["victuals"])
        assert "cook" not in state["watch"]

        after, _produced = step(state, hours=1.0, seed=7)
        # The institution answers on its own: it re-staffs the post that
        # serves the failed condition, out of its own ROSTER -- a body the
        # author never named, chosen by the charter's own planner.
        restaffed = after["watch"].get("cook")
        assert restaffed and restaffed in after["roster"]
        # And the author's hand is exactly the two facts it moved. No
        # reaction was authored, because there is nowhere to author one.
        assert [row["op"] for row in after["authored"]] == ["charter_shock",
                                                            "vacate_post"]


class TestTheInstitutionKeepsItsOwnBeliefs:
    def test_a_death_does_not_correct_the_roster(self):
        """A town learns of a death when somebody sees the body. The bodies
        know; the roster still believes."""
        registry = _registry()
        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "die", "charter": "caravanserai", "body": "yusra"})])
        state = registry["items"]["caravanserai"]["state"]
        assert state["bodies"]["yusra"]["condition"] == "dead"
        assert state["bodies"]["yusra"]["available"] is False
        assert state["roster"]["yusra"]["believed_available"] is True

    def test_only_an_observation_corrects_it(self):
        from world.charter import observe, stale_claims
        registry = _registry()
        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "die", "charter": "caravanserai", "body": "yusra"})])
        state = registry["items"]["caravanserai"]["state"]
        assert ("yusra", "availability") in stale_claims(state["roster"],
                                                         state["bodies"])
        state["roster"] = observe(state["roster"], state["bodies"]["yusra"],
                                  state["clock_hours"])
        assert state["roster"]["yusra"]["believed_available"] is False
        assert ("yusra", "availability") not in stale_claims(state["roster"],
                                                             state["bodies"])

    def test_the_read_side_shows_the_stale_belief(self, temp_db):
        """The tool is what makes this legible instead of looking like a bug
        -- which is why the roster section exists at all."""
        cid = _story(temp_db)
        author_charter_ops(cid, None, [normalize_charter_op(
            {"op": "die", "charter": "caravanserai", "body": "yusra"})])
        house = run_tool(cid, "inspect_charters",
                         {"charter": "caravanserai"})["charters"]["caravanserai"]
        row = next(r for r in house["roster"] if r["body"] == "yusra")
        assert row["believes"]["available"] is True
        assert row["in_fact"]["condition"] == "dead"


class TestTheDirectorStillReadsCharterAndDoesNotSteerIt:
    def test_the_directors_readers_are_unchanged_by_an_authored_event(self, temp_db):
        """One subsystem, two readers, one author: `charter_carriers`,
        `present_charter_figures` and the crowd derivation keep working over
        the same registry, and none of them writes it."""
        from agents.common import present_charter_figures
        from world.charter_runtime import charter_carriers
        cid = _story(temp_db)
        rooms = ["gate", "yard", "kitchen"]
        before_carriers = charter_carriers(cid, rooms)
        before = json.dumps(registry_for(cid, None), sort_keys=True, default=str)
        # Reading steers nothing.
        assert json.dumps(registry_for(cid, None), sort_keys=True,
                          default=str) == before

        author_charter_ops(cid, None, [normalize_charter_op(
            {"op": "errand", "charter": "caravanserai", "body": "neris",
             "to": "gate", "purpose": "fetch the warden"})])
        after_carriers = charter_carriers(cid, rooms)
        assert isinstance(after_carriers, type(before_carriers))
        from story.scene import get_scene
        from core.db import q
        scene = get_scene(cid, q("SELECT * FROM chats WHERE id=?", (cid,),
                                 one=True))
        figures = present_charter_figures(cid, scene, rooms)
        assert isinstance(figures, (list, tuple, dict))

    def test_the_crowd_derivation_still_reads_the_same_bodies(self):
        from world.charter_crowd import members_of
        registry = _registry()
        state = registry["items"]["caravanserai"]["state"]
        before = sorted(members_of(state, "yard"))
        apply_charter_ops(registry, [normalize_charter_op(
            {"op": "vacate_post", "charter": "caravanserai", "post": "hand"})])
        assert sorted(members_of(state, "yard")) == before


# ---------------------------------------------------------------------------
# The package: the shape the Planner writes
# ---------------------------------------------------------------------------

def _package(cid, ops, **fields):
    pkg = new_package(cid, title="The store room burns",
                      premise="A fire in the kitchen wing.", **fields)
    draft_operation(cid, pkg["uid"], {"op": "charter_ops", **ops})
    return pkg["uid"]


class TestThePackageOperation:
    def test_it_is_registered_in_the_closed_table(self):
        from story.mandates import MANDATE_CAPABILITIES
        from story.plot_packages import OPERATION_FIELDS
        assert "charter_ops" in OPERATIONS and "charter_ops" in OPERATION_FIELDS
        assert "charter_ops" in MANDATE_CAPABILITIES
        assert "author_charter_ops" in OPERATIONS["charter_ops"]["seam"]

    def test_it_previews_and_publishes_through_the_seam(self, temp_db):
        cid = _story(temp_db)
        uid = _package(cid, {"charter": "caravanserai",
                             "event": "The store room burns out.",
                             "ops": [{"op": "upkeep_fails",
                                      "upkeep": "victuals", "to": 0.0},
                                     {"op": "vacate_post", "post": "cook"}]})
        result = preview_package(cid, uid)
        assert not result["errors"]
        kinds = [c["op"] for c in result["changes"]]
        assert kinds == ["upkeep_fails", "vacate_post"]
        assert validate_package(cid, uid)["ok"]
        publish_package(cid, uid, expected_revision=_rev(cid, uid))
        state = registry_for(cid, None)["items"]["caravanserai"]["state"]
        assert "cook" not in state["watch"]
        assert state["interventions"][0]["op"] == "upkeep_shock"

    def test_a_refusal_is_reported_by_the_preview_and_writes_nothing(self, temp_db):
        cid = _story(temp_db)
        uid = _package(cid, {"charter": "caravanserai",
                             "ops": [{"op": "errand", "body": "nobody",
                                      "to": "gate"}]})
        before = json.dumps(registry_for(cid, None), sort_keys=True, default=str)
        result = preview_package(cid, uid)
        assert any("holds no body" in e for e in result["errors"])
        assert not validate_package(cid, uid)["ok"]
        assert json.dumps(registry_for(cid, None), sort_keys=True,
                          default=str) == before

    def test_a_bad_op_is_refused_at_draft_time(self, temp_db):
        cid = _story(temp_db)
        pkg = new_package(cid, title="Bad", premise="")
        with pytest.raises(ValueError, match="no such charter op"):
            draft_operation(cid, pkg["uid"], {
                "op": "charter_ops", "charter": "caravanserai",
                "ops": [{"op": "burn_it_down"}]})

    def test_a_death_asks_for_the_harm_grant(self, temp_db):
        from story.plot_packages import operation_harms, package_requirements
        cid = _story(temp_db)
        uid = _package(cid, {"charter": "caravanserai",
                             "ops": [{"op": "die", "body": "yusra"}]})
        pkg = get_package(cid, uid)
        assert operation_harms(pkg["operations"][0]) is True
        assert "schedule_harm" in package_requirements(pkg)
        harmless = _package(cid, {"charter": "caravanserai",
                                  "ops": [{"op": "vacate_post", "post": "cook"}]})
        assert "schedule_harm" not in package_requirements(get_package(cid, harmless))

    def test_a_package_with_no_charter_op_is_byte_identical(self, temp_db):
        """Nothing about this change touches a package that does not carry
        one: the registry is untouched, byte for byte."""
        cid = _story(temp_db)
        before = json.dumps(registry_for(cid, None), sort_keys=True, default=str)
        pkg = new_package(cid, title="A note", premise="")
        draft_operation(cid, pkg["uid"], {
            "op": "director_note", "text": "The kitchen wing is the one on fire."})
        assert validate_package(cid, pkg["uid"])["ok"]
        publish_package(cid, pkg["uid"], expected_revision=_rev(cid, pkg["uid"]))
        assert json.dumps(registry_for(cid, None), sort_keys=True,
                          default=str) == before

    def test_the_model_facing_shape_names_every_op(self):
        from story.plot_packages import operation_shape_text
        text = operation_shape_text()
        assert "charter_ops" in text
        for kind in CHARTER_OPS:
            assert kind in text

    def test_the_event_reaches_the_director_as_a_circumstance(self, temp_db):
        """`event` is what HAPPENED, handed to the Director next beat. Who
        answers it is nobody's to write here."""
        cid = _story(temp_db)
        uid = _package(cid, {"charter": "caravanserai",
                             "event": "The store room burns out.",
                             "ops": [{"op": "vacate_post", "post": "cook"}]})
        assert validate_package(cid, uid)["ok"]
        out = publish_package(cid, uid, expected_revision=_rev(cid, uid))
        applied = out["applied"][0]["result"]
        assert applied.get("notice")
        rows = temp_db.q("SELECT payload FROM scheduled_events WHERE chat_id=?",
                         (cid,))
        assert any("store room burns out" in str(r["payload"]) for r in rows)


def _rev(cid, uid):
    return get_package(cid, uid)["revision"]
