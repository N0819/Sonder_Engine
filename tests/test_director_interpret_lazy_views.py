"""Interpret builds a world view only where something reads it (C8).

The defect this file pins (review 2026-09-07, finding C8): `director_interpret`
built every specialist extra eagerly. The condition views, sightlines and exits
were gated behind "any hand runs" earlier in the review; what remained were the
five world views the channel gates ask about -- crowds, couriers, posted
notices, carried reports, unratified hearsay -- built on every beat to produce
five booleans for a record nobody could act on. On an interpret beat whose
ruling reaches NO hand there is no payload to carry them and no scope they
could change, because the gates decide how much sheet an ADDRESSED hand loads.
Measured on a copy of chat 114 at turn 13 (307-body charter town, 125 carried
reports): 48 ms of a 205 ms deterministic interpret, dominated by
`_carried_reports_view`.

The mechanism is a thunk (`director_views._lazy_view`) handed to `_gate_facts`
where the rows used to go, plus a `_dispatch_specialists` that consults the
gates only when a hand could run. What must stay true, and is what these tests
are for:

* ONE BUILD PER STAGE when anything reads them -- the `crowds_rows` rule, so
  the gate and the payload cannot disagree about what stands in reach;
* the recorded facts on a beat that dispatched a hand are the same facts the
  eager build recorded, short-circuited gates included;
* on the beat that saves the work, the record says so (`gated: None`) rather
  than recording an empty list, which would read as "the scene admitted no
  channel".
"""

from __future__ import annotations

import json
import time
import uuid

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data

import agents.director as director


BASE_SCENE = {
    "location": "Blackthorn Lighthouse",
    "time": "night",
    "rooms": {"keeper_room": {"name": "Keeper's Room", "adjacent": []}},
    "positions": {"Mara": "keeper_room"},
    "entities": {},
    "attire": {"Mara": {"wearing": ["wool coat"]}},
    "overlays": {},
}

#: The five views interpret used to build on every beat, with the counter
#: patched at `agents.director` because that is the module whose globals its
#: call sites resolve (the facade rule: patch the module that READS the name).
_VIEWS = ("_crowds_view", "_artifacts_view", "_couriers_view",
          "_carried_reports_view", "_unratified_background_claims")


def _make_ctx(temp_db, *, player_input):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}",
         time.time(), f"char_mara_{uuid.uuid4().hex[:8]}"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene", json.loads(json.dumps(BASE_SCENE)))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 3, player_input, time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=3,
                      player_input=player_input, created=time.time()),
        cast=cast, input=player_input,
    )
    ctx.director_interpret = None
    return ctx


def _interpret_out(*, ledger_notes=None):
    out = {
        "kind": "action",
        "sequence": [{"type": "action", "attempt": "pull off my wool coat",
                      "commitment": "asserted", "targets": [],
                      "raw_text": "I pull off my wool coat"}],
        "speech": None, "action": {"attempt": "pull off my wool coat"},
        "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    if ledger_notes:
        out["ledger_notes"] = dict(ledger_notes)
    return out


def _run(temp_db, monkeypatch, *, ledger_notes=None):
    """One interpret, with the model stubbed and every view build counted."""
    counts = {}
    for name in _VIEWS:
        real = getattr(director, name)

        def counted(*a, _real=real, _name=name, **kw):
            counts[_name] = counts.get(_name, 0) + 1
            return _real(*a, **kw)

        monkeypatch.setattr(director, name, counted)

    interp = _interpret_out(ledger_notes=ledger_notes)

    def fake(role, step_key, system, payload, **kw):
        if step_key == "director_interpret":
            return json.loads(json.dumps(interp))
        return {}

    monkeypatch.setattr(director, "_agent_json", fake)
    ctx = _make_ctx(temp_db, player_input="I pull off my wool coat")
    return director.director_interpret(ctx, nonce=0), counts


def test_a_beat_whose_ruling_reaches_no_hand_builds_no_world_view(
        temp_db, monkeypatch):
    """C8: no hand, no payload, no gate that could change a scope -- so none
    of the five views is built, and the record says the gates were not
    consulted instead of recording an empty gate list."""
    out, counts = _run(temp_db, monkeypatch)

    specialists = out["orchestration"]["specialists"]
    assert all(not state["run"] for state in specialists.values())
    assert counts == {}, f"a view was built for nobody: {counts}"
    for name, state in specialists.items():
        assert state["gated"] is None, name
        # The cheap facts -- standing scene state, one indexed row, the
        # survival setting -- are recorded as they always were.
        assert state["facts"]["anyone_wears"] is True
        assert state["facts"]["physical_beat"] is True
        assert "vitals_tracked" in state["facts"]
        # The view-derived five are absent rather than guessed at.
        for fact in ("crowds_present", "couriers_present", "notices_in_scene",
                     "reports_carried", "unratified_claims_present"):
            assert fact not in state["facts"], fact


def test_a_beat_that_dispatches_a_hand_builds_each_view_once(
        temp_db, monkeypatch):
    """The other half: a ruling reaches the body hand, so the gates are
    consulted and the payload is assembled -- each view built EXACTLY once
    (the `crowds_rows` rule: the gate and the payload read the same rows),
    and every fact recorded, including one no gate asked for."""
    out, counts = _run(temp_db, monkeypatch,
                       ledger_notes={"body": "the coat comes off"})

    specialists = out["orchestration"]["specialists"]
    assert specialists["body"]["run"] is True
    assert counts == {name: 1 for name in _VIEWS}, counts
    for name, state in specialists.items():
        assert isinstance(state["gated"], list), name
        for fact in ("crowds_present", "couriers_present", "notices_in_scene",
                     "reports_carried", "unratified_claims_present"):
            assert fact in state["facts"], (name, fact)
    # One facts object for every hand, as before.
    values = list(specialists.values())
    assert all(state["facts"] == values[0]["facts"] for state in values)


def test_the_thunk_and_the_rows_give_the_same_facts(temp_db):
    """The lazy fact IS the eager fact: `_gate_facts` takes rows or the thunk
    that builds them, and a gate reading either gets the same answer."""
    ctx = _make_ctx(temp_db, player_input="hello")
    sc = json.loads(json.dumps(BASE_SCENE))
    rows = [{"crowd_id": "crowd_1"}]

    eager = director._gate_facts(
        ctx, sc, physical=True, speech=False, crowds_rows=rows,
        notices_rows=[], couriers_rows=[], reports_rows=[], unratified_rows=[])
    lazy = director._gate_facts(
        ctx, sc, physical=True, speech=False,
        crowds_rows=lambda: rows, notices_rows=lambda: [],
        couriers_rows=lambda: [], reports_rows=lambda: [],
        unratified_rows=lambda: [])

    assert lazy.pending() is True
    assert dict(eager) == dict(lazy)
    assert lazy.pending() is False
    # Read means recorded; a fact nothing read is not invented.
    assert eager.consulted() == dict(eager)


def test_a_view_that_raises_still_fails_open(temp_db):
    """A fact whose read fails degrades to True -- never gate a channel out
    on an error -- with the thunk exactly as with the eager read."""
    def boom():
        raise RuntimeError("registry unreadable")

    ctx = _make_ctx(temp_db, player_input="hello")
    facts = director._gate_facts(
        ctx, json.loads(json.dumps(BASE_SCENE)), physical=True, speech=False,
        crowds_rows=boom, notices_rows=boom, couriers_rows=boom,
        reports_rows=boom, unratified_rows=boom)

    assert facts["crowds_present"] is True
    assert facts["reports_carried"] is True


def test_a_plain_dict_of_facts_still_dispatches(temp_db):
    """`_dispatch_specialists` is called with a hand-built dict in three
    tests and by any caller without a stage payload; nothing pending means
    the gates are read exactly as they always were."""
    ctx = _make_ctx(temp_db, player_input="hello")
    facts = dict(director._gate_facts(
        ctx, json.loads(json.dumps(BASE_SCENE)), physical=True, speech=False,
        crowds_rows=[], notices_rows=[], couriers_rows=[], reports_rows=[],
        unratified_rows=[]))
    assert isinstance(facts, dict)
    dispatch = director._dispatch_specialists(None, None, facts, {})

    assert all(isinstance(state["gated"], list)
               for state in dispatch.values())
    assert dispatch["body"]["facts"] is facts
