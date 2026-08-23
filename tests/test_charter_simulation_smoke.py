"""Fast proof that the integrated Charter simulation advances and replays."""

import copy

from world.charter import (
    RECALL_CAP,
    acquaintance,
    normalize_charter,
    run,
    seed_needs,
    seed_roster,
)

from charter_fixtures import SHIP


def _small_charter():
    state = normalize_charter(copy.deepcopy(SHIP))
    state["roster"] = seed_roster(state["bodies"])
    state["needs"] = seed_needs(state["bodies"])
    return state


def test_a_small_institution_advances_without_writing_idle_noise():
    after, events = run(_small_charter(), hours=8.0, window=2.0, seed=7)

    assert events == []
    assert after["watch"]
    assert set(after["needs"]) == set(after["bodies"])
    assert set(after["minds"]) <= set(after["bodies"])
    assert all(value <= RECALL_CAP for value in acquaintance(
        after["minds"]).values())


def test_the_integrated_simulation_replays_from_the_same_seed():
    one, one_events = run(_small_charter(), hours=48.0, window=4.0, seed=11)
    two, two_events = run(_small_charter(), hours=48.0, window=4.0, seed=11)

    assert one_events == two_events
    assert one == two


def test_a_small_failure_is_reported_instead_of_silently_ignored():
    state = _small_charter()
    state["bodies"]["chief"]["available"] = False
    state["bodies"]["ramos"]["available"] = False
    state["roster"] = seed_roster(state["bodies"])

    _after, events = run(state, hours=48.0, window=4.0, seed=3)

    assert any(row["kind"] == "post_unfilled" for row in events)
    assert any(row["kind"] == "upkeep_out_of_band" for row in events)
