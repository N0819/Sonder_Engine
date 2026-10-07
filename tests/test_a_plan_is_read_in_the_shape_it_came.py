"""A town plan is read in the shape the model wrote it, not the shape the
prompt asked for.

Found in play on 2026-10-06 (scratch story 164, the fen port Brackwater,
planned by the one-shot `propose_town` under the Writers' Room's
`request_location`), and reproduced on a private copy (chat 165, run 1):

* THE CRASH. The prompt asks `needs:{rest|sustenance|health:{fed_by:upkeep
  id}}`. The model kept that shape for `rest` and wrote `"sustenance":
  "inn_board", "health": "fen_herbs"` in all ten charters. `needs_template`
  skipped a need that was not a dict; `close_plan` read
  `needs.sustenance.fed_by` as one and raised `'str' object has no attribute
  'get'`, so the Room's `prepare_package` failed and the ground went unlaid.
* THE DEAD TOWN. The retry that did plant gave every one of its 12 upkeeps
  `depends_on: ["chandlery_supply"]`, an upkeep that exists nowhere.
  `supply_factor` reads a chain's inputs from the charter's OWN upkeeps and
  scores a missing one 0.0, so no tending restored anything: after the
  1,440-hour prehistory every upkeep was down and the whole town stood down
  unable (`/charters/diagnostics`: household 236 of 236, port_labor 55 of
  55). A need's `fed_by` resolves the same way (`advance_needs` is handed the
  charter's own upkeeps), so one naming nothing starves its bodies too.

One class -- a model-authored container read as the shape the prompt asked
for -- and its siblings on the same path, each confirmed by injecting the
variant: upkeeps written as rows, a plan's charters keyed by id, a naming
law's titles as a list, a historian's residents as a list, and charters past
the eight the closer keeps, which were dropped without a word.
"""

from __future__ import annotations

import copy
import json
import os

import pytest

from world.charter_drift import supply_factor
from world.charter_generate import (PLAN_CHARTERS, close_plan,
                                    ground_history_output)
from world.charter_identity import normalize_naming_profile

_HERE = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture()
def plan():
    with open(os.path.join(_HERE, "data", "harrowmere_plan.json")) as fh:
        return json.load(fh)


def _warned(town, *words):
    return [w for w in town["closure"]["warnings"]
            if all(word in w for word in words)]


def test_a_need_named_bare_is_read_as_the_upkeep_that_feeds_it(plan):
    charter = plan["charters"][0]
    own = sorted(charter["upkeeps"])[0]
    charter["needs"] = {"rest": {"fed_by": own}, "sustenance": own,
                        "health": "fen_herbs"}
    town = close_plan(plan)
    needs = next(iter(town["charters"][charter["key"]]["needs"].values()))
    assert needs["rest"]["fed_by"] == own
    assert needs["sustenance"]["fed_by"] == own
    assert not needs["health"]["fed_by"], (
        "a hand that is not one of its upkeeps would read as supply 0.0")
    assert _warned(town, "fen_herbs")


def test_a_dependency_on_nothing_is_dropped_rather_than_starving(plan):
    charter = plan["charters"][0]
    for upkeep in charter["upkeeps"].values():
        upkeep["depends_on"] = ["chandlery_supply"]
    town = close_plan(plan)
    upkeeps = town["charters"][charter["key"]]["upkeeps"]
    for upkeep in upkeeps.values():
        assert upkeep["depends_on"] == []
        assert supply_factor(upkeep, upkeeps) == 1.0
    assert _warned(town, "chandlery_supply")


def test_a_dependency_on_its_own_upkeep_is_a_chain_and_stays(plan):
    charter = plan["charters"][0]
    a, b = sorted(charter["upkeeps"])[:2]
    charter["upkeeps"][a]["depends_on"] = [b, a]
    town = close_plan(plan)
    upkeeps = town["charters"][charter["key"]]["upkeeps"]
    assert upkeeps[a]["depends_on"] == [b], (
        "a real input stays; depending on itself could never recover")


def test_upkeeps_written_as_rows_are_the_same_upkeeps(plan):
    charter = plan["charters"][0]
    table = copy.deepcopy(charter["upkeeps"])
    charter["upkeeps"] = [dict(spec, key=key) for key, spec in table.items()]
    town = close_plan(plan)
    assert set(town["charters"][charter["key"]]["upkeeps"]) == set(table)


def test_charters_keyed_by_their_ids_close_like_a_list(plan):
    listed = close_plan(copy.deepcopy(plan))
    keyed = copy.deepcopy(plan)
    keyed["charters"] = {c["key"]: {k: v for k, v in c.items() if k != "key"}
                         for c in keyed["charters"]}
    assert set(close_plan(keyed)["charters"]) == set(listed["charters"])


def test_charters_past_the_closers_limit_are_named_not_dropped_in_silence(plan):
    assert len(plan["charters"]) == PLAN_CHARTERS
    for i in range(2):
        extra = copy.deepcopy(plan["charters"][0])
        extra["key"], extra["name"] = f"extra_{i}", f"Extra {i}"
        plan["charters"].append(extra)
    town = close_plan(plan)
    assert "extra_0" not in town["charters"]
    assert _warned(town, "extra_0") and _warned(town, "extra_1")


def test_a_naming_laws_titles_written_as_a_list_do_not_raise():
    profile = normalize_naming_profile(
        {"titles": {"posts": ["reeve", "clerk"], "ranks": "high"}})
    assert profile["titles"] == {"posts": {}, "ranks": {}}


def test_a_historians_residents_written_as_a_list_lose_only_themselves():
    out = ground_history_output(
        {"overview": {}, "residents": [{"summary": "kept the ferry"}]}, [])
    assert out["residents"] == {}
