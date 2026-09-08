"""A retired room's identity is spent: review 2026-09-07, Section I residual
on B8/A55 (`R-ruin-revival`).

B8 made the registry the authority for retirement and stopped the next
commit's scene projection from un-retiring a ruin. The frontier mint was the
other door into the same defect and stayed open: every `planned_*` reader
filters `retired_turn_id IS NULL`, so `prepare_frontier_expansion` reserved
only live spellings, a stub could be minted under a ruin's own uid, and
`apply_frontier_mutations` wrote `retired_turn_id=NULL` on conflict -- the
destroyed building came back live, as a nameless planned stub, one beat after
the wave that ended it.
"""

from __future__ import annotations

import json
import time

import pytest

from world.structure import (apply_frontier_mutations, plant_structure,
                             prepare_frontier_expansion,
                             retired_room_spellings)


#: A grammar whose one road name is the room the story is about to ruin, so
#: the mint's first choice IS the ruin. `mint_frontier` picks a grammar name
#: only when the axis asks for it by a word of its own, which "bridge road"
#: does.
GRAMMAR = {"key": "harrowmere", "max_planned": 100, "grammar": [
    {"kind": "road", "names": ["bridge road"], "purposes": ["crossing"]},
]}


@pytest.fixture()
def planted(temp_db):
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Ruin", "", time.time()))
    turn = temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                      "VALUES(?,?,?,?)", (cid, 0, "", time.time()))
    plant_structure(cid, GRAMMAR, {
        "gate": {"name": "Upland Gate", "purpose": "gatehouse",
                 "adjacent": [], "frontier": ["bridge road"]},
        "bridge_road": {"name": "Bridge Road", "purpose": "crossing",
                        "adjacent": []},
    })
    # The wave that ends it: the registry retires the row and the room stays
    # in the scene, because a ruin is still a place.
    temp_db.qi("UPDATE room_registry SET retired_turn_id=? WHERE chat_id=? "
               "AND room_uid=?", (turn, cid, "bridge_road"))
    return cid, turn


def _expand(temp_db, cid):
    scene = {"rooms": {"gate": {"name": "Upland Gate", "adjacent": []}},
             "positions": {"Player": "gate"}}
    scene, mutations = prepare_frontier_expansion(cid, scene)
    with temp_db.transaction():
        apply_frontier_mutations(cid, None, mutations)
    return scene, mutations


def test_the_ruin_s_spellings_are_readable(temp_db, planted):
    """Uid, NAME and ALIAS, each folded the way `mint_frontier` folds its
    candidates -- so the reservation covers the spellings a plan or a mint
    would actually reach for, not just the id."""
    cid, _turn = planted
    temp_db.qi("UPDATE room_registry SET name=?, aliases=? WHERE chat_id=? "
               "AND room_uid=?",
               ("The Old Span", json.dumps(["Ferry Crossing"]), cid,
                "bridge_road"))

    spellings = retired_room_spellings(cid)

    assert "bridge_road" in spellings          # the uid
    assert "the_old_span" in spellings         # the name it answers to
    assert "ferry_crossing" in spellings       # and every alias


def test_the_mint_does_not_land_on_the_ruin(temp_db, planted):
    cid, _turn = planted

    _scene, mutations = _expand(temp_db, cid)

    minted = [m["room_uid"] for m in mutations if m["room_uid"] != "gate"]
    assert minted and "bridge_road" not in minted


def test_the_ruin_is_still_retired_afterwards(temp_db, planted):
    cid, turn = planted

    _expand(temp_db, cid)

    row = temp_db.q("SELECT retired_turn_id FROM room_registry WHERE "
                    "chat_id=? AND room_uid=?", (cid, "bridge_road"),
                    one=True)
    assert row["retired_turn_id"] == turn


def test_a_write_naming_a_retired_row_does_not_revive_it(temp_db, planted):
    """The upsert half, stated on its own: a caller handing this a mutation
    for a retired uid changes the row and leaves the retirement alone."""
    cid, turn = planted

    with temp_db.transaction():
        apply_frontier_mutations(cid, None, [{
            "room_uid": "bridge_road", "owning_book_id": None,
            "parent_entity": None, "name": "Bridge Road",
            "aliases": ["Bridge Road"], "payload": {"planned": {}}}])

    row = temp_db.q("SELECT retired_turn_id FROM room_registry WHERE "
                    "chat_id=? AND room_uid=?", (cid, "bridge_road"),
                    one=True)
    assert row["retired_turn_id"] == turn


def test_planting_a_plan_does_not_land_on_the_ruin(temp_db, planted):
    """The OTHER door into the same defect, and the one a story walks through
    mid-play: `story.plot_packages._apply_plan_rooms` plants a package's rooms
    with `plant_structure`, whose upserts carried `retired_turn_id=NULL` -- so
    a package naming a room the wave ended re-minted the spent identity. The
    plan keeps its room; it gets its own uid beside the ruin."""
    cid, turn = planted

    _structure, planted_rooms = plant_structure(cid, GRAMMAR, {
        "bridge_road": {"name": "Bridge Road", "purpose": "crossing",
                        "adjacent": [{"to": "gate", "barrier": "open"}]},
        "toll_house": {"name": "Toll House", "purpose": "toll",
                       "adjacent": [{"to": "bridge_road",
                                     "barrier": "open"}]},
    })

    assert "bridge_road" not in planted_rooms
    assert "bridge_road_2" in planted_rooms
    # And the plan's own edges follow the room, so the package is not left
    # pointing at a ruin.
    assert [e["to"] for e in planted_rooms["toll_house"]["adjacent"]] \
        == ["bridge_road_2"]

    row = temp_db.q("SELECT retired_turn_id,name FROM room_registry WHERE "
                    "chat_id=? AND room_uid=?", (cid, "bridge_road"),
                    one=True)
    assert row["retired_turn_id"] == turn
    assert row["name"] == "Bridge Road"      # the ruin's own row, untouched


def test_a_plant_naming_a_live_room_still_writes_it(temp_db, planted):
    """The reservation reads RETIRED spellings only: replanting a live
    planned room is the ordinary case and still updates it in place."""
    cid, _turn = planted

    _structure, planted_rooms = plant_structure(cid, GRAMMAR, {
        "gate": {"name": "Upland Gate", "purpose": "gatehouse",
                 "adjacent": [], "frontier": []},
    })

    assert list(planted_rooms) == ["gate"]
    rows = temp_db.q("SELECT room_uid FROM room_registry WHERE chat_id=? AND "
                     "room_uid LIKE 'gate%'", (cid,))
    assert [r["room_uid"] for r in rows] == ["gate"]


def test_a_live_room_whose_spelling_a_ruin_also_wore_keeps_its_uid(temp_db, planted):
    """Writing a live row revives nothing, so the ruin reservation must not
    re-key it (A55 rework, second skeptic): a retired row aliased with the
    live room's name made a replant of that live room come back under a
    fresh suffix -- a second registry row for one place, the live row's
    payload left stale."""
    cid, _turn = planted
    temp_db.qi("UPDATE room_registry SET aliases=? WHERE chat_id=? AND "
               "room_uid=?", (json.dumps(["Upland Gate", "gate"]), cid, "bridge_road"))

    _structure, planted_rooms = plant_structure(cid, GRAMMAR, {
        "gate": {"name": "Upland Gate", "purpose": "gatehouse",
                 "adjacent": [], "frontier": []},
    })

    assert list(planted_rooms) == ["gate"]
    rows = temp_db.q("SELECT room_uid, retired_turn_id FROM room_registry "
                     "WHERE chat_id=? AND room_uid LIKE 'gate%'", (cid,))
    assert [r["room_uid"] for r in rows] == ["gate"]
    assert rows[0]["retired_turn_id"] is None
    ruin = temp_db.q("SELECT retired_turn_id FROM room_registry WHERE chat_id=? "
                     "AND room_uid='bridge_road'", (cid,), one=True)
    assert ruin["retired_turn_id"] is not None
