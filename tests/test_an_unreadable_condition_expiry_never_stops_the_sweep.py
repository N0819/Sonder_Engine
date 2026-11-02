"""A condition whose `expires_at` is not a number is a condition with no
readable end -- never a sweep that raises.

world_offscreen_time F2 (audit 2026-11-01, reproduced): `_expire_conditions`
called `float(expires)` unguarded while the tick pass beside it guarded the
same column. SQLite keeps a non-numeric `expires_at` as TEXT, the sweep is
the FIRST domain inside the commit transaction, so one row written `""` or
`"dawn"` rolled back that beat and every beat after it until a hand edited
the row. One reader of the column now serves both passes.
"""

import json
import math

from world import mechanics


def _cond(cid, expires, **extra):
    return {"condition_id": cid, "subject_id": "yard", "kind": "flood",
            "started_at": 0.0, "expires_at": expires, "next_tick": None,
            "payload": json.dumps(extra.get("payload") or {})}


def test_an_unreadable_expiry_is_no_end_and_raises_nothing():
    conditions = [_cond("blank", ""), _cond("word", "dawn"),
                  _cond("nan", float("nan")), _cond("due", 50.0),
                  _cond("later", 500.0), _cond("none", None)]
    assert mechanics._expire_conditions(conditions, 100.0) == [
        ("expire_condition", "due")]


def test_the_whole_sweep_runs_past_a_row_with_a_word_for_its_end():
    scene = {"rooms": {"yard": {"name": "Yard"}}, "entities": {},
             "positions": {}}
    _scene, ops, _notices, _counts = mechanics.mechanics_sweep(
        scene, {"elapsed_seconds": 100.0}, None, [],
        conditions=[_cond("word", "soon"), _cond("due", "60")])
    assert ("expire_condition", "due") in ops
    assert ("expire_condition", "word") not in ops


def test_both_passes_read_the_column_through_one_reader():
    """The tick pass and the expiry pass answer the same question about the
    same column; a value one of them can read the other reads the same way."""
    for raw, want in (("", None), ("dawn", None), (None, None),
                      (float("nan"), None), (float("inf"), None),
                      ("3600", 3600.0), (3600, 3600.0), (True, None)):
        got = mechanics._condition_expires_at({"expires_at": raw})
        assert got == want or (want is not None and math.isclose(got, want)), raw
