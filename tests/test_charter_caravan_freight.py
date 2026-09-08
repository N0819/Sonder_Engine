"""Review 2026-09-07 A52: a stop trades a caravan's freight, never edits it.

The wagon was loaded into the town's own `stocks`, and `normalize_economy`
keeps a holder's stocks to the goods that economy defines -- so every lot
the local market had no word for was dropped the first time `trade` ran.
"""
from world.charter_economy import caravan_exchange


def _grain_and_wool_town():
    return {
        "goods": {"grain": {"base_value": 1.0}, "wool": {"base_value": 2.0}},
        "stocks": {"miller": {"grain": 2.0, "wool": 6.0}},
        "targets": {"miller": {"grain": {"desired": 10.0, "capacity": 20.0},
                               "wool": {"desired": 4.0, "capacity": 8.0}}},
        "markets": {"m": {"place": "market", "holder": "miller"}},
    }


def test_a_good_the_town_has_no_word_for_stays_on_the_wagon():
    freight = {"stock": {"grain": 5.0, "salt": 9.0}, "wants": {}}
    economy, carried, events = caravan_exchange(
        _grain_and_wool_town(), freight, "market")
    assert [(e["good"], e["amount"]) for e in events] == [("grain", 5.0)]
    # Sold what the town buys, kept what it does not define.
    assert carried["stock"] == {"salt": 9.0}
    assert "caravan" not in economy["stocks"]
    assert "salt" not in economy["goods"]


def test_freight_survives_a_stop_where_nothing_is_traded():
    freight = {"stock": {"salt": 9.0}, "wants": {"wool": 3.0}}
    economy, carried, events = caravan_exchange(
        _grain_and_wool_town(), freight, "elsewhere")
    assert events == [] and carried["stock"] == {"salt": 9.0}
    assert "caravan" not in economy["stocks"]


def test_a_purchase_lands_beside_the_freight_it_did_not_touch():
    freight = {"stock": {"salt": 9.0}, "wants": {"wool": 3.0}}
    _economy, carried, events = caravan_exchange(
        _grain_and_wool_town(), freight, "market")
    assert [(e["good"], e["amount"]) for e in events] == [("wool", 3.0)]
    assert carried["stock"] == {"salt": 9.0, "wool": 3.0}
