"""An economy window reads every stock band from the economy it already
normalized.

`advance_economy` called `stock_band`, which normalized the WHOLE economy on
every call, twice per target per window: measured (audit
world_charter_behaviours E3) 0.72 s per call with 20 holders x 12 goods,
one normalization 1.5 ms -- once per window per charter, every beat. The
bands, events and stocks are unchanged."""
from world import charter_economy
from world.charter_economy import advance_economy, normalize_economy, stock_band


def _economy(holders=6, goods=5):
    goods_spec = {"g%d" % g: {"label": "good %d" % g, "base_value": 1.0}
                  for g in range(goods)}
    stocks = {"h%d" % h: {"g%d" % g: float((h + g) % 4) for g in range(goods)}
              for h in range(holders)}
    targets = {"h%d" % h: {"g%d" % g: {"minimum": 1.0, "desired": 2.0,
                                        "capacity": 3.0}
                            for g in range(goods)} for h in range(holders)}
    flows = {"f%d" % h: {"holder": "h%d" % h, "good": "g%d" % (h % goods),
                         "kind": "consume" if h % 2 else "produce",
                         "lots_per_hour": 0.5} for h in range(holders)}
    return {"goods": goods_spec, "stocks": stocks, "targets": targets,
            "flows": flows}


def test_a_window_normalizes_its_economy_a_fixed_number_of_times(monkeypatch):
    calls = []
    real = charter_economy.normalize_economy
    monkeypatch.setattr(charter_economy, "normalize_economy",
                        lambda value: calls.append(1) or real(value))
    advance_economy(_economy(), 2.0, at_hours=4.0)
    assert len(calls) <= 3, len(calls)


def test_the_bands_and_events_are_unchanged():
    economy = _economy()
    out, events = advance_economy(economy, 2.0, at_hours=4.0)
    normalized = normalize_economy(out)
    for holder, held in normalized["targets"].items():
        for good in held:
            assert stock_band(out, holder, good) == stock_band(
                normalized, holder, good)
    assert events, "a two-hour window moves some band"
