"""IS THIS NAME TAKEN is one question with one answer (B19, review
2026-09-07).

Package validation counted four kinds of name -- the registered cast,
charter bodies, authored plans and their aliases -- and exempted a
participant the package's own `plan_entity` operation plans. The Room's
`inspect_contradictions` counted the registered cast alone and knew nothing
of the exemption, so the same package that validated clean was then
reported as naming three strangers by the tool reading it back.

Both sites now read `plot_packages.reserved_names` and
`plot_packages.unheld_participants`, and `inspect_reserved_identities`
reports that one reservation instead of deriving a second.
"""
from __future__ import annotations

import time

import pytest

from story import plot_packages
from story.room_tools import run_tool


def _story(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Reservations", "A port at dusk.", time.time()))
    db.wset(cid, "scene", {"location": "Port", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone.", "adjacent": []},
    }, "positions": {}, "entities": {}, "attire": {}})
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (cid, 0, "", time.time()))
    return cid


def _world(db, monkeypatch):
    """A cast member, a charter body, a plan with an alias -- one of each
    kind of name the world holds."""
    from world import charter_runtime
    from world.planned_entities import add_planned_entity

    cid = _story(db)
    char_id = db.qi("INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
                    ("Mara Quill", "{}", time.time()))
    db.qi("INSERT INTO chat_chars(chat_id,char_id) VALUES(?,?)", (cid, char_id))
    registry = {"items": {"harbour_office": {"state": {"bodies": {
        "b1": {"name": "Tamsin Rook", "place": "quay", "available": True}}}}}}
    monkeypatch.setattr(charter_runtime, "registry_for",
                        lambda cid_, frame_id=None: registry)
    add_planned_entity(cid, {"kind": "person", "name": "Old Sel",
                             "aliases": ["the netmender"],
                             "brief": {"where": "quay"}})
    return cid


def _landed_package(db, cid):
    """A published package naming one participant of every held kind, one it
    plans itself, and one nobody holds."""
    pkg = plot_packages.normalize_package({
        "uid": "pkg_reservations", "title": "The netmender's debt",
        "status": "published", "revision": 1, "published_turn": 0,
        "participants": [{"name": "Mara Quill"}, {"name": "Tamsin Rook"},
                         {"name": "the netmender"}, {"name": "Halvane Ash"},
                         {"name": "Nobody Atall"}],
        "operations": [{"op": "plan_entity", "kind": "person",
                        "name": "Halvane Ash", "aliases": [],
                        "brief": {"where": "quay"}}],
    })
    plot_packages.save_packages(cid, {pkg["uid"]: pkg})
    return pkg


def test_the_lint_and_validation_name_the_same_strangers(temp_db, monkeypatch):
    cid = _world(temp_db, monkeypatch)
    pkg = _landed_package(temp_db, cid)

    validated = [w for w in plot_packages._package_checks(
        pkg, plot_packages._world_snapshot(cid))[1] if "participant" in w]
    linted = [row["name"] for row
              in run_tool(cid, "inspect_contradictions")["dangling"]
              if row["kind"] == "participant_nobody_holds"]

    assert linted == ["Nobody Atall"]
    assert len(validated) == 1 and "Nobody Atall" in validated[0]


def test_the_tool_reports_the_one_reservation_rather_than_a_second(
        temp_db, monkeypatch):
    cid = _world(temp_db, monkeypatch)
    reported = run_tool(cid, "inspect_reserved_identities")

    shown = {str(c["name"]).casefold() for c in reported["characters"]
             if c["name"]}
    for names in reported["charter_bodies"].values():
        shown |= {n.casefold() for n in names}
    for plan in reported["plans"]:
        shown.add(plan["name"].casefold())
        shown |= {a.casefold() for a in plan["aliases"]}

    assert shown == plot_packages.reserved_names(cid)
    assert shown == {"mara quill", "tamsin rook", "old sel", "the netmender"}


def test_a_package_that_plans_its_own_stranger_is_not_naming_one():
    pkg = {"participants": [{"name": "Halvane Ash"}],
           "operations": [{"op": "plan_entity", "name": "halvane ash"}]}
    assert plot_packages.unheld_participants(pkg, set()) == []
    assert plot_packages.unheld_participants(
        {"participants": [{"text": "Halvane Ash"}], "operations": []},
        set()) == ["Halvane Ash"]


@pytest.mark.parametrize("held", ["Mara Quill", "TAMSIN ROOK", "the netmender"])
def test_every_kind_of_held_name_answers_the_same_way(temp_db, monkeypatch, held):
    cid = _world(temp_db, monkeypatch)
    assert plot_packages.unheld_participants(
        {"participants": [{"name": held}], "operations": []},
        plot_packages.reserved_names(cid)) == []
