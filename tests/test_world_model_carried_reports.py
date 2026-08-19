"""MASTER-037: the Director's carried-report view enumerates every carrier.

The carrier ledger has one enumeration (`story.carriers._carriers`): extant
cast -- dormant included -- plus the player, whose reports live in a world key
because a persona has no cast row. The Director's `_carried_reports_view`
rebuilt that walk over `active_cast`/`cstate` alone, so the two carriers the
central walk exists to include were invisible to the one stage that must name
a `world_event_id` in a `telling_ops`/`courier_ops`: a player who legitimately
acquired a surface could never spread it (docs/UNBUILT.md 1.31).
"""

from __future__ import annotations

import json
import time
import types


class _Chat(dict):
    """A chat with both `.id` and `.get`, as the real `ChatData` has."""

    @property
    def id(self):
        return self["id"]


def _world(db, *, persona="Corin"):
    persona_id = db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (persona, json.dumps({"name": persona}), "{}"))
    cid = db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Report story", "", time.time(), persona_id))
    chars = {}
    for name, uid, status in (("Mora", "mora_uid", "active"),
                              ("Tavi", "tavi_uid", "dormant")):
        sheet = json.dumps({"identity": {"name": name, "uid": uid}})
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, sheet, "{}", time.time()))
        db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,'{}')", (cid, char_id, status))
        chars[name] = char_id
    db.wset(cid, "scene", {
        "rooms": {"square": {"name": "Square", "adjacent": []}},
        "positions": {"Mora": "square", "Tavi": "square", persona: "square"},
    })
    ctx = types.SimpleNamespace(
        chat=_Chat(id=cid, persona_id=persona_id),
        turn=types.SimpleNamespace(id=1, idx=3, frame_id=None),
        cast=[], extra_players=[],
    )
    return cid, chars, ctx


def _report(event_id, claim, retellings=0):
    return {"world_event_id": event_id, "claim": claim,
            "retellings": retellings, "acquired_turn": 1}


def _hold(db, cid, char_id, reports):
    db.qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
          (json.dumps({"carried_reports": reports}), cid, char_id))


def test_player_carried_report_reaches_the_director_view(temp_db):
    """A report only the player holds must be nameable in a telling op."""
    from agents.director import _carried_reports_view
    from story.carriers import PERSONA_STATE_KEY

    cid, chars, ctx = _world(temp_db)
    temp_db.wset(cid, PERSONA_STATE_KEY, {
        "carried_reports": [_report("world_bell", "the bell rang twice")]})

    view = _carried_reports_view(ctx)
    assert [(r["who"], r["world_event_id"]) for r in view] == \
        [("Corin", "world_bell")]
    assert view[0]["gist"] == "the bell rang twice"


def test_dormant_carrier_reaches_the_director_view(temp_db):
    """Dormancy is an engine-spend decision, not a departure: a dormant
    holder's report is still real and still addressable."""
    from agents.director import _carried_reports_view

    cid, chars, ctx = _world(temp_db)
    _hold(temp_db, cid, chars["Tavi"],
          [_report("world_gate", "the gate was barred")])

    view = _carried_reports_view(ctx)
    assert [(r["who"], r["world_event_id"]) for r in view] == \
        [("Tavi", "world_gate")]


def test_active_npc_carrier_unchanged(temp_db):
    """The active-cast slice the old walk did cover still comes through,
    shaped exactly as before ({who, world_event_id, gist, retellings})."""
    from agents.director import _carried_reports_view

    cid, chars, ctx = _world(temp_db)
    _hold(temp_db, cid, chars["Mora"],
          [_report("world_bell", "the bell rang twice", retellings=2),
           {"claim": "no id, never nameable in an op"}])

    view = _carried_reports_view(ctx)
    assert view == [{"who": "Mora", "world_event_id": "world_bell",
                     "gist": "the bell rang twice", "retellings": 2}]


def test_view_is_the_carriers_enumeration(temp_db):
    """Drift guard: the Director view IS `carriers.carried_reports_view` --
    one walk, not a second spelling that can fall behind it."""
    from agents.director import _carried_reports_view
    from story.carriers import PERSONA_STATE_KEY, carried_reports_view

    cid, chars, ctx = _world(temp_db)
    _hold(temp_db, cid, chars["Mora"], [_report("world_bell", "bell")])
    _hold(temp_db, cid, chars["Tavi"], [_report("world_gate", "gate")])
    temp_db.wset(cid, PERSONA_STATE_KEY, {
        "carried_reports": [_report("world_door", "door")]})

    scene = temp_db.wget(cid, "scene", {})
    assert _carried_reports_view(ctx) == carried_reports_view(
        cid, None, scene, chat=ctx.chat)
    assert {r["who"] for r in _carried_reports_view(ctx)} == \
        {"Mora", "Tavi", "Corin"}
