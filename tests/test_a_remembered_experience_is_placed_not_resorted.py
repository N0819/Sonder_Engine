"""A body's experience list is kept in order by placing each new row, never
by re-sorting the whole life on every insert.

`charter_run._remember_experience` copied the holder's list and re-sorted it
by (hour, id) on every append, so its cost grew with the life it was
appending to: measured (audit world_charter_core E1), a 720 h profile made
840,579 sort-key calls for 8,507 inserts, and the cost of a 240 h chunk rose
1.46 -> 2.98 s as the mean rows per body rose 72 -> 253 -- the reason the
year test takes 95 s. The order it keeps is unchanged."""
import random

from world import charter_run
from world.charter_run import EXPERIENCE_CAP, _remember_experience


def _reference(rows):
    rows = sorted(rows, key=lambda r: (float(r.get("at_hours") or 0.0),
                                       str(r.get("id") or "")))
    return rows[-EXPERIENCE_CAP:]


def test_the_kept_order_is_the_sorted_order():
    rng = random.Random(7)
    store, written = {}, []
    for index in range(600):
        # Mostly forward in time, with ties and the odd late arrival.
        at = float(index // 3) - (rng.random() * 5 if index % 17 == 0 else 0)
        row = {"id": "e:%04d:%d" % (rng.randrange(50), index),
               "at_hours": round(at, 2), "kind": "social"}
        written.append(dict(row))
        _remember_experience(store, "ada", row, fold=False)
    assert store["ada"] == _reference(written)


def test_an_insert_looks_at_a_handful_of_rows_not_the_whole_life(monkeypatch):
    calls = []
    real = charter_run._experience_order

    def counted(row):
        calls.append(1)
        return real(row)

    monkeypatch.setattr(charter_run, "_experience_order", counted)
    store = {"ada": [{"id": "e:%05d" % i, "at_hours": float(i)}
                     for i in range(2000)]}
    calls.clear()
    _remember_experience(store, "ada", {"id": "late", "at_hours": 10.5},
                         fold=False)
    assert len(calls) <= 40, len(calls)
    assert [r["id"] for r in store["ada"][10:13]] == [
        "e:00010", "late", "e:00011"]
