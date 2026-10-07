"""A line its speaker declared before an act is said before that act.

Measured (scratch story 165, turn 4581, 2026-10-07). Hester declared three
lines and then "crosses the taproom, lifts the door latch, and stands
half-turned back toward the fire". The resolve prose dropped the lines and
walked her out through the door. Uncited by any row, the lines reached the
outcome stream as unbound dialogue appended after the whole beat, were graded
from the Main Walk through a shut plank door, and the player got "Hester Gale
says something you cannot make out: ...somebody's... Nobody's... changes --".
She had gone in at interpret and out at resolve, so the two snapshots showed
no move and `beat_movement_cuts` had nothing to cut.
"""

import types

from agents import perception
from world.causal_program import event_worlds

DECL = "turn:9:character:81:%d:%s"


def _ctx():
    return types.SimpleNamespace(
        get=lambda key, default=None: {"chat": {"persona_id": 21}}.get(
            key, default),
        extra_players=[])


INTERP = {"ledgers": [{}], "sequence": [{
    "type": "action", "observable": "steps in out of the fog",
    "actor": "persona:21", "chrono_id": 1,
    "event_id": "turn:9:player:0:action",
    "from_declaration": "turn:9:primary:raw"}]}


def _line(n, text):
    return {"type": "speech", "text": text, "volume": "normal",
            "visibility": "overt", "event_id": DECL % (n, "speech")}


def _act(n, attempt):
    return {"type": "action", "attempt": attempt, "observable": attempt,
            "visibility": "overt", "event_id": DECL % (n, "action")}


def _row(chrono, actor, observable, cited=""):
    return {"type": "action", "observable": observable, "actor": actor,
            "chrono_id": chrono, "event_id": "r%d" % chrono,
            "from_declaration": cited}


def _resolve(*rows):
    return {"ledgers": [{}], "sequence": list(rows)}


def _sequences(hester):
    return [("Tamsin", INTERP["sequence"], True), ("Hester Gale", hester, False)]


def _flat(result):
    return [(actor, events[0].get("type"),
             events[0].get("text") or events[0].get("observable"))
            for actor, events, _player in result]


def test_a_dropped_line_goes_back_before_the_act_it_preceded():
    hester = [_line(0, "Search bell."), _line(1, "First light stands."),
              _act(2, "lifts the door latch")]
    res = _resolve(
        _row(2, "character:81", "lifts the latch", DECL % (2, "action")),
        _row(3, "Niboold", "the fire takes"),
        _row(4, "character:81", "steps out and shuts the door",
             DECL % (2, "action")))
    result = perception._causal_outcome_sequences(
        _ctx(), INTERP, res, "Tamsin", _sequences(hester), {81: "Hester Gale"})
    assert _flat(result)[1:] == [
        ("Hester Gale", "speech", "Search bell."),
        ("Hester Gale", "speech", "First light stands."),
        ("Hester Gale", "action", "lifts the latch"),
        ("Niboold", "action", "the fire takes"),
        ("Hester Gale", "action", "steps out and shuts the door")]
    spliced = [events[0] for _a, events, _p in result
               if events[0].get("type") == "speech"]
    latch = result[3][1][0]
    assert all(line["_causal_span"] == latch["_causal_span"]
               for line in spliced), "heard in the world before her act"

    # And graded there: the before-world of her first act holds her inside.
    worlds = [{"stage": "resolve", "chrono_id": 2, "events": [],
               "before": {"Hester Gale": "taproom"}},
              {"stage": "resolve", "chrono_id": 4, "events": [],
               "before": {"Hester Gale": "taproom"}}]
    stream = [{"kind": "speech", "causal_span": line["_causal_span"],
               "event": line} for line in spliced]
    assert set(map(str, event_worlds(worlds, stream).values())) == {
        str({"Hester Gale": "taproom"})}


def test_a_line_declared_after_the_act_keeps_the_end_of_the_beat():
    hester = [_act(0, "steps out onto the walk"),
              _line(1, "Back before your books are closed.")]
    res = _resolve(_row(2, "character:81", "steps out onto the walk",
                        DECL % (0, "action")))
    result = perception._causal_outcome_sequences(
        _ctx(), INTERP, res, "Tamsin", _sequences(hester), {81: "Hester Gale"})
    assert [kind for _a, kind, _t in _flat(result)] == ["action", "action"]


def test_a_line_the_author_carried_is_not_put_back_twice():
    hester = [_line(0, "Search bell."), _act(1, "lifts the door latch")]
    carried = dict(_row(2, "character:81", "", DECL % (0, "speech")),
                   type="speech", text="Search bell.")
    res = _resolve(carried,
                   _row(3, "character:81", "lifts the latch",
                        DECL % (1, "action")))
    result = perception._causal_outcome_sequences(
        _ctx(), INTERP, res, "Tamsin", _sequences(hester), {81: "Hester Gale"})
    assert [t for _a, kind, t in _flat(result) if kind == "speech"] == [
        "Search bell."]
