"""A need with a chain at one end and a person at the other.

Review 2026-09-07, owner's rulings 2026-09-08:

  * **A25** -- no generated charter ever set a need's `fed_by`, so every town
    serviced sustenance at supply 1.0 whatever its stocks. `fed_by` is now
    derived from whichever upkeep ANYWHERE IN TOWN produces a good this
    institution consumes, and from nothing else; where the town produces no
    good anybody eats, the author is told at generation and at every
    registry read rather than the need being fed out of nowhere.
  * **D17** -- the fidelity change that `fed_by` makes visible: a chain that
    fails now reaches the bodies at the end of it.
  * **D18** -- `company`, a fourth need in the same shape, serviced by the
    window's acts, read as a third pull in `charter_move.errands`, and never
    able to stand a body down from its post -- nor to decide anything else
    the institution does about a body (`charter_needs.bears_on_duty`).

MEASURED ON bench.db CHAT 114 (the four real charters of the island town),
2026-09-08. 0 of 66 stored needs name a hand before; 0 of 66 after, and all
four charters warn. That is the ruling's outcome rather than a shortfall:
the town produces `meals`, `linens` and `iced_fish`, and consumes
`groceries`, `cleaning_supplies`, `lodging`, `block_ice`, `diesel_fuel`,
`net_rope`, `engine_parts`, `island_produce`, `sundries`, `fresh_fish`,
`breakfast_meals`, `food_supply` and `linen_supply` -- an intersection of
nothing. The store buys `fresh_fish` while the fishery lands `iced_fish`,
which is the lore fact the warning exists to put in front of an author.

A SECOND CLAUSE WAS TRIED AND REFUSED. Reading the upkeep the consuming flow
itself requires derived a hand 66 times of 66 on that town, which is the
objection to it: it fed every institution from its own cupboard, ranked the
fishery's crew onto `block_ice` because two flows consume ice and one
consumes diesel, and could only have told ice from bread with a goods word
list. See `charter_needs.feeding_upkeep`.
"""

import copy

from world.charter import (able, advance_needs, bears_on_duty, ensure_needs,
                           enact, feeding_upkeep, needs_template,
                           normalize_charter, normalize_need, offers, pressure,
                           run, seed_needs, seed_roster, unfed_notice, unmet,
                           wants_company, worst_need)
from world.charter_feel import appraise_window
from world.charter_generate import close_plan
from world.charter_move import errands
from world.charter_runtime import normalize_registry, registry_warnings


def _economy(flows, goods=("bread", "groceries", "meals")):
    """`holder` on every flow because `charter_economy.normalize_economy`
    drops a flow without one, and a registry read normalizes before this
    module ever sees the economy."""
    return {"goods": {good: {"label": good, "base_value": 1.0, "unit": "lot"}
                      for good in goods},
            "flows": {key: dict(flow, holder=flow.get("holder", "store"))
                      for key, flow in flows.items()}}


# ------------------------------------------------------------------ A25


def test_a_good_this_institution_makes_and_eats_feeds_its_people():
    """A25's clause, at its simplest: the mill town that eats its own
    bread. The producing upkeep is the hand, and a producer this charter
    holds itself is preferred over one it does not."""
    feeder = feeding_upkeep({"ovens": {}, "granary": {}}, _economy({
        "bake": {"good": "bread", "kind": "produce", "lots_per_hour": 3.0,
                 "requires_upkeep": "ovens"},
        "eat": {"good": "bread", "kind": "consume", "lots_per_hour": 2.0,
                "requires_upkeep": "granary"},
    }))
    assert feeder == {"upkeep": "ovens", "charter": "", "good": "bread",
                      "hand": "producer"}
    assert needs_template(None, {"ovens": {}}, _economy({
        "bake": {"good": "bread", "kind": "produce", "lots_per_hour": 3.0,
                 "requires_upkeep": "ovens"},
        "eat": {"good": "bread", "kind": "consume", "lots_per_hour": 2.0},
    }))["sustenance"]["fed_by"] == "ovens"


def test_a_good_nobody_in_town_makes_derives_nothing_and_says_so():
    """A25's ruling, and chat 114's real shape: the guesthouse makes meals
    and linens and buys groceries, so no institution produces a good anybody
    consumes. The engine has no structural way to know that the kitchen's
    provisions ARE the food rather than a cupboard the food arrives into,
    and guessing it fed all 66 of that town's bodies out of nowhere."""
    holder_shape = _economy({
        "meal_prep": {"good": "meals", "kind": "produce",
                      "lots_per_hour": 6.0,
                      "requires_upkeep": "kitchen_provisions"},
        "grocery_use": {"good": "groceries", "kind": "consume",
                        "lots_per_hour": 2.0,
                        "requires_upkeep": "kitchen_provisions"},
    })
    assert feeding_upkeep({"kitchen_provisions": {}}, holder_shape) is None
    assert needs_template(None, {"kitchen_provisions": {}},
                          holder_shape)["sustenance"].get("fed_by", "") == ""
    assert "nothing in town makes" in unfed_notice("guesthouse_ops", None)


def test_a_producer_anywhere_in_town_is_found_and_reported():
    """A25: the ruling's own case -- the guesthouse's groceries from the
    farm. The SEARCH is the town's; the ANSWER is still the institution's,
    because a window resolves an upkeep against its OWN charter's upkeeps
    (`advance_needs`, `charter_drift.supply_factor`), so writing a foreign
    key would read as level 0.0 and starve the town it was meant to feed."""
    town = [("farm", {"fields": {}}, _economy({
        "grow": {"good": "groceries", "kind": "produce", "lots_per_hour": 3.0,
                 "requires_upkeep": "fields"}}))]
    feeder = feeding_upkeep({"desk": {}}, _economy({
        "buy": {"good": "groceries", "kind": "consume",
                "lots_per_hour": 1.0, "requires_upkeep": ""}}), town)
    assert feeder == {"upkeep": "fields", "charter": "farm",
                      "good": "groceries", "hand": "producer"}
    assert needs_template(None, {"desk": {}}, _economy({
        "buy": {"good": "groceries", "kind": "consume",
                "lots_per_hour": 1.0}}),
        town)["sustenance"].get("fed_by", "") == ""
    notice = unfed_notice("inn", feeder)
    assert "farm" in notice and "fields" in notice


def test_a_town_that_feeds_nobody_says_so_instead_of_supplying_one():
    """A25's ruling: a town where the bread comes from nowhere is a lore fact
    to author, not a need quietly serviced at full supply."""
    assert feeding_upkeep({"desk": {}}, _economy({})) is None
    assert needs_template(None, {"desk": {}},
                          _economy({}))["sustenance"].get("fed_by", "") == ""
    assert "nothing in town" in unfed_notice("inn", None)


def test_an_authored_hand_survives_the_derivation():
    authored = needs_template({"health": {"fed_by": "infirmary"}}, {}, {})
    assert authored["health"]["fed_by"] == "infirmary"


# ------------------------------------------------ A25 at generation

def _plan(name, key, flows, goods, upkeeps=("ovens",)):
    """The smallest plan `close_plan` will close: one room, one charter, one
    post, one crew."""
    return {
        "name": name,
        "structure": {"key": key, "max_planned": 6},
        "rooms": {"yard": {"name": "The Yard", "purpose": "work",
                           "adjacent": []}},
        "charters": [{
            "key": key,
            "naming": {"given": ["Ann", "Bo", "Cy"], "family": ["Reed"]},
            "upkeeps": {name: {"place": "yard", "floor": 0.3,
                               "fails_untended": "days",
                               "one_body_restores_in": "hours"}
                        for name in upkeeps},
            "posts": {"hand": {"place": "yard", "serves": list(upkeeps),
                               "requires": {"labour": 1}}},
            "populations": [{"post": "hand", "count": 3,
                             "competence": {"labour": 1}, "berth": "yard"}],
            "economy": _economy(flows, goods),
        }],
    }


def test_a_town_that_makes_what_it_eats_closes_with_the_hand_written():
    """A25 at GENERATION, which is where the finding was filed: `close_plan`
    seeds every body's needs from the town-wide template, so the hand is on
    the charter from the day it is written. Reverting `close_plan`'s town
    hunk leaves this red -- the seeded needs carry `fed_by: ""`."""
    town = close_plan(_plan("Mill", "mill", {
        "bake": {"good": "bread", "kind": "produce", "lots_per_hour": 3.0,
                 "requires_upkeep": "ovens"},
        "eat": {"good": "bread", "kind": "consume", "lots_per_hour": 2.0,
                "requires_upkeep": "ovens"},
    }, goods=("bread",)))

    needs = town["charters"]["mill"]["needs"]
    assert needs, "the closer seeds a needs row per body"
    assert {held["sustenance"]["fed_by"] for held in needs.values()} \
        == {"ovens"}
    assert not [line for line in town["closure"]["warnings"]
                if "live on" in line or "nothing in town makes" in line]


def test_a_town_that_makes_nothing_it_eats_closes_with_the_notice():
    """A25's ruling, at the surface the author actually reads: the closure
    warning list, in the D19 shape. This is the outcome for all four of
    bench.db chat 114's charters and it is the intended one -- a town where
    the bread comes from nowhere is a lore fact to author, not a default to
    hide."""
    town = close_plan(_plan("Quay", "quay", {
        "eat": {"good": "rations", "kind": "consume", "lots_per_hour": 2.0,
                "requires_upkeep": "dock_stores"},
    }, goods=("rations",), upkeeps=("dock_stores",)))

    needs = town["charters"]["quay"]["needs"]
    assert needs
    assert {held["sustenance"]["fed_by"] for held in needs.values()} == {""}
    assert [line for line in town["closure"]["warnings"]
            if line.startswith("quay: nothing in town makes")]


def test_the_author_may_name_the_hand_the_derivation_cannot_find():
    """The escape the warning points at: a town whose food arrives from off
    the map names the upkeep that lands it, and the closer neither derives
    over it nor complains about it."""
    plan = _plan("Quay", "quay", {
        "eat": {"good": "rations", "kind": "consume", "lots_per_hour": 2.0,
                "requires_upkeep": "dock_stores"},
    }, goods=("rations",), upkeeps=("dock_stores",))
    plan["charters"][0]["needs"] = {"sustenance": {"fed_by": "dock_stores"}}

    town = close_plan(plan)
    assert {held["sustenance"]["fed_by"]
            for held in town["charters"]["quay"]["needs"].values()} \
        == {"dock_stores"}
    assert not [line for line in town["closure"]["warnings"]
                if line.startswith("quay: nothing in town makes")]


# ------------------------------------------------ A25 on stored towns

def _registry(**charters):
    return {"items": {key: {"state": state}
                      for key, state in charters.items()}}


def _town_state(key, upkeeps, economy, bodies=("a", "b")):
    state = {
        "key": key,
        "upkeeps": {name: {"place": "hall", "level": 1.0, "floor": 0.2}
                    for name in upkeeps},
        "posts": {"post": {"place": "hall", "serves": list(upkeeps)}},
        "bodies": {body: {"place": "hall", "home_post": "post",
                          "available": True} for body in bodies},
        "economy": economy,
    }
    state["needs"] = seed_needs(state["bodies"])
    return state


_MILL_FLOWS = {
    "bake": {"good": "bread", "kind": "produce", "lots_per_hour": 3.0,
             "requires_upkeep": "ovens"},
    "eat": {"good": "bread", "kind": "consume", "lots_per_hour": 2.0,
            "requires_upkeep": "ovens"},
}


def test_a_stored_town_picks_up_the_hand_that_feeds_it_on_the_next_read():
    """A25: no generator ever wrote `fed_by`, so a rule that reached only
    towns written after it would reach almost nobody -- bench.db chat 114's
    66 stored needs all carry an empty one."""
    stored = _registry(mill=_town_state("mill", ("ovens",),
                                        _economy(_MILL_FLOWS)))
    for held in stored["items"]["mill"]["state"]["needs"].values():
        assert held["sustenance"]["fed_by"] == ""
    once = normalize_registry(copy.deepcopy(stored))
    fed = {held["sustenance"]["fed_by"]
           for held in once["items"]["mill"]["state"]["needs"].values()}
    assert fed == {"ovens"}
    twice = normalize_registry(once)
    assert {held["sustenance"]["fed_by"]
            for held in twice["items"]["mill"]["state"]["needs"].values()} \
        == {"ovens"}
    # An authored hand is never overwritten by the derivation.
    authored = copy.deepcopy(stored)
    for held in authored["items"]["mill"]["state"]["needs"].values():
        held["sustenance"]["fed_by"] = "infirmary"
    kept = normalize_registry(authored)
    assert {held["sustenance"]["fed_by"]
            for held in kept["items"]["mill"]["state"]["needs"].values()} \
        == {"infirmary"}


def test_the_author_hears_about_a_need_the_town_cannot_feed():
    """A25's ruling: WARN at every registry read as well as at generation,
    in the D19 shape, rather than silently supplying 1.0. Measured on
    bench.db chat 114: four warnings, one per charter."""
    fed = normalize_registry(_registry(
        mill=_town_state("mill", ("ovens",), _economy(_MILL_FLOWS))))
    assert not [line for line in registry_warnings(fed) if "live on" in line]

    unfed = normalize_registry(_registry(
        inn=_town_state("inn", ("pantry",), _economy({
            "eat": {"good": "groceries", "kind": "consume",
                    "lots_per_hour": 1.0, "requires_upkeep": "pantry"}}))))
    assert [line for line in registry_warnings(unfed)
            if "nothing in town makes" in line]

    stranded = normalize_registry(_registry(
        inn=_town_state("inn", ("pantry",), _economy({}))))
    for held in stranded["items"]["inn"]["state"]["needs"].values():
        held["sustenance"]["fed_by"] = "somebody_elses_upkeep"
    assert [line for line in registry_warnings(stranded)
            if "which this institution does not hold" in line]


# ------------------------------------------------------------------ D17


def test_a_failed_chain_reaches_the_bodies_at_the_end_of_it():
    """D17: the fidelity change `fed_by` makes visible, and it is visible
    only where A25 derives or an author names a hand. Measured on bench.db
    chat 114's guesthouse, whose `kitchen_provisions` stands at 0.571: a
    body fed by it recovers a 0.5 sustenance to 0.815 in one 8 h window
    where an unfed one recovers to 1.0."""
    bodies = {"a": {"available": True}}
    upkeeps = {"ovens": {"level": 0.0}}

    unwired = seed_needs(bodies)
    for _ in range(40):
        unwired, unable, _ = advance_needs(
            unwired, bodies, {}, upkeeps, 8.0)
        assert not unable
    assert unwired["a"]["sustenance"]["level"] == 1.0

    wired = seed_needs(bodies, needs_template(
        None, upkeeps, _economy(_MILL_FLOWS)))
    assert wired["a"]["sustenance"]["fed_by"] == "ovens"
    fell = False
    for _ in range(40):
        wired, unable, _ = advance_needs(wired, bodies, {}, upkeeps, 8.0)
        fell = fell or bool(unable)
    assert fell, "a need drawing on a dead upkeep must reach its floor"


# ------------------------------------------------------------------ D18


def test_company_hurts_and_pulls_and_never_stands_a_body_down():
    """D18, the owner's constraint: unmet company must never stand a body
    down from its post -- nor weigh on the watch bill, which is the same
    door one step further in (`charter_run` spends the least reluctant
    body first)."""
    held = {name: normalize_need(name, {})
            for name in ("rest", "sustenance", "health", "company")}
    held["company"]["level"] = 0.0
    assert able(held) is True
    assert pressure(held) == pressure({k: v for k, v in held.items()
                                       if k != "company"})
    # It is still a breach, so `unmet` -- which REPORTS what a body is short
    # of rather than deciding anything -- counts it.
    assert unmet(held) > 0.0
    assert unmet(held, duty_only=True) == 0.0
    held["rest"]["level"] = 0.0
    assert able(held) is False


def test_company_drifts_while_nobody_speaks_and_is_serviced_when_they_do():
    bodies = {"a": {"available": True}}
    alone = seed_needs(bodies)
    for _ in range(20):
        alone, unable, _ = advance_needs(alone, bodies, {}, {}, 8.0)
        assert not unable, "loneliness never stands a body down"
    assert alone["a"]["company"]["level"] < alone["a"]["company"]["floor"]

    spoken_to = copy.deepcopy(alone)
    spoken_to, _u, _r = advance_needs(
        spoken_to, bodies, {}, {}, 8.0, company={"a": 1.0})
    assert spoken_to["a"]["company"]["level"] > alone["a"]["company"]["level"]
    assert not wants_company(spoken_to["a"]) or \
        spoken_to["a"]["company"]["level"] > 1.0  # recovered past the floor


def test_a_body_short_of_people_walks_to_a_commons_somebody_is_in():
    """D18: the third pull, ahead of the commons fallback. The answer to a
    company need is a person, so an empty lounge is no answer."""
    bodies = {"lonely": {"place": "hall", "available": True},
              "other": {"place": "far_commons", "available": True}}
    needs = seed_needs(bodies)
    reach = {("lonely", "near_commons"): 1, ("lonely", "far_commons"): 4,
             ("lonely", "hall"): 0, ("other", "far_commons"): 0}
    kwargs = dict(seed=3, rate=1.0, hours=4.0,
                  commons=("near_commons", "far_commons"))

    content = errands(bodies, needs, {}, {}, ("hall",), reach, **kwargs)
    assert content["lonely"] == "near_commons", "the nearest, as before"

    needs["lonely"]["company"]["level"] = 0.0
    pulled = errands(bodies, needs, {}, {}, ("hall",), reach, **kwargs)
    assert pulled["lonely"] == "far_commons", "the one with somebody in it"

    # Nobody anywhere: the ordinary fallback still runs, so a town that has
    # emptied its commons starts filling one again.
    alone = {"lonely": bodies["lonely"]}
    assert errands(alone, needs, {}, {}, ("hall",), reach,
                   **kwargs)["lonely"] == "near_commons"


def test_a_town_seeded_before_company_existed_picks_it_up():
    """D18: a need nobody has is a need that changes nothing -- the
    silent-empty-field failure `CLAUDE.md` records. bench.db chat 114's 66
    bodies were seeded before `company` existed."""
    bodies = {"a": {"available": True}, "b": {"available": True}}
    old = seed_needs(bodies)
    for held in old.values():
        held.pop("company")
    old["a"]["rest"]["level"] = 0.4
    filled = ensure_needs(old, bodies)
    assert set(filled["a"]) == {"rest", "sustenance", "health", "company"}
    assert filled["a"]["company"]["level"] == 1.0
    assert filled["a"]["rest"]["level"] == 0.4, "a lived level is the story's"


def test_a_body_the_caller_models_no_needs_for_is_left_alone():
    """D18: "missing one key" is a charter that predates a need; "no needs
    row" is a caller that chose not to model them. Filling the second put a
    full needs model on the SHIP fixture's crew, whose silent simulated week
    became 69 `body_unable` and 53 `post_unfilled`."""
    bodies = {"a": {"available": True}, "b": {"available": True}}
    assert ensure_needs({}, bodies) == {}
    assert ensure_needs({"a": {}}, bodies) == {"a": {}}
    partial = ensure_needs({"a": seed_needs({"a": {}})["a"]}, bodies)
    assert "company" in partial["a"] and "b" not in partial


def test_loneliness_does_not_wear_the_rest_it_is_forbidden_to_spend():
    """D18's constraint, defended at the back door as well as the front:
    `appraise_window`'s somatic pain becomes strain, `charter_run` hands
    strain to `advance_needs` as a multiplier on rest drift, and a body
    exhausted by that is a body stood down for loneliness one window late."""
    held = {name: normalize_need(name, {})
            for name in ("rest", "sustenance", "health", "company")}
    held["company"]["level"] = 0.0
    appraisal, _impacts = appraise_window("a", "hall", {}, (), held_needs=held)
    assert "somatic_impact" not in appraisal

    held["rest"]["level"] = 0.0
    appraisal, _impacts = appraise_window("a", "hall", {}, (), held_needs=held)
    assert appraisal["somatic_impact"]["why"] == "rest below its floor"


# ------------------------------------- D18 through a running institution

def _lonely_town():
    """One post, five bodies, and last window's talk already deposited.

    `newcomer` predates `company` (its needs row has no such key) and has
    lived its health down; `speaker` and `listener` were the two ends of an
    act; `ignored` was in none; `unmodelled` has no needs row at all.
    """
    charter = normalize_charter({
        "key": "hall",
        "upkeeps": {"fire": {"place": "hall", "level": 1.0, "floor": 0.2,
                             "drift_per_hour": 0.001,
                             "service_per_hour": 0.05}},
        "posts": {"warden": {"place": "hall", "serves": ["fire"],
                             "requires": {"labour": 1}}},
        "bodies": {key: {"place": "hall", "berth": "hall",
                         "home_post": "warden", "available": True,
                         "competence": {"labour": 1}}
                   for key in ("newcomer", "speaker", "listener", "ignored",
                               "unmodelled")},
        "window_acts": [
            {"actor": "speaker", "act": "converse", "other": "listener",
             "place": "hall", "at_hours": 0.0},
        ],
    })
    charter["roster"] = seed_roster(charter["bodies"])
    needs = seed_needs(charter["bodies"])
    del needs["unmodelled"]
    del needs["newcomer"]["company"]
    needs["newcomer"]["health"]["level"] = 0.5
    for key in ("speaker", "listener", "ignored"):
        needs[key]["company"]["level"] = 0.2
    charter["needs"] = needs
    return charter


def test_a_running_charter_gives_every_body_the_need_the_model_has():
    """D18 (i), through `world.charter.run` rather than beside it: the
    migration onto stored charters is the only thing that lets a town seeded
    before `company` ever feel it, and reverting `charter_run`'s
    `ensure_needs` call leaves this red."""
    after, _events = run(_lonely_town(), hours=4.0, window=4.0)

    held = after["needs"]["newcomer"]
    assert "company" in held, "a stored charter picks the need up in a window"
    # A LIVED LEVEL IS THE STORY'S: `health` drifts at zero and services at
    # 0.04/h, so 0.5 becomes 0.66 over one 4 h window and a re-seeded body
    # would read 1.0.
    assert 0.6 < held["health"]["level"] < 0.7


def test_the_window_s_talk_is_what_services_the_need_it_names():
    """D18 (ii): a body named as actor or as other in the previous window's
    acts is serviced; a body named in neither drifts. Reverting
    `charter_run`'s `company=kept_company` leaves this red -- every body
    drifts alike and nothing in the model ever pulls one toward another."""
    after, _events = run(_lonely_town(), hours=4.0, window=4.0)

    for key in ("speaker", "listener"):
        assert after["needs"][key]["company"]["level"] > 0.2, key
    assert after["needs"]["ignored"]["company"]["level"] < 0.2


def test_a_body_the_charter_models_no_needs_for_stays_that_way():
    """D18 (iii), and the safety of doing the migration at all: filling a
    body that was never modelled put a full needs model on the SHIP
    fixture's crew and turned a silent simulated week into 69 `body_unable`
    events."""
    after, _events = run(_lonely_town(), hours=4.0, window=4.0)

    assert "unmodelled" not in after["needs"]


# --------------------------------- D18: what a carer services, and why

def test_a_carer_services_the_need_that_put_the_body_down():
    """D18, the fourth door (skeptic 2026-09-08). `company`'s floor of 0.12
    is the highest of the four and it is the only need that cannot stand a
    body down, so selecting the widest gap sent the carer to loneliness
    every time: a body on the floor with sustenance at 0.0 (gap 0.10) was
    tended for company (gap 0.12), took its +0.05 there, and stayed down --
    exactly the case tending exists for, since the opportunity gate already
    requires the subject to be unavailable."""
    bodies = {"carer": {"key": "carer", "place": "hall", "available": True,
                        "competence": {}},
              "down": {"key": "down", "place": "hall", "available": False,
                       "competence": {}}}
    held = {name: normalize_need(name, {})
            for name in ("rest", "sustenance", "health", "company")}
    held["sustenance"]["level"] = 0.0
    held["company"]["level"] = 0.0
    assert not able(held)
    assert worst_need(held)["key"] == "sustenance"
    assert bears_on_duty(held["sustenance"]) and not bears_on_duty(
        held["company"])

    needs = {"down": copy.deepcopy(held)}
    practices = _tending(bodies)
    rows = offers(bodies, {}, needs, practices, {}, {}, 4.0)["carer"]
    assert [row for row in rows if row["act"] == "tend"]

    # The CHOOSER's own path (`charter_practice._afford_tend`), unpinned.
    acts, _spawned, _closed, _blame, _refused = enact(
        bodies, {}, needs, practices, {}, {}, 4.0)
    assert [act["line"] for act in acts] == ["carer tended down (sustenance)"]
    assert needs["down"]["sustenance"]["level"] == 0.05
    assert needs["down"]["company"]["level"] == 0.0


def test_the_author_switch_services_the_need_the_chooser_would():
    """The authored twin (`charter_author`) runs the same selector as the
    chooser: two sites, one rule, and the §12a property that pinning a body
    to what it would have chosen is indistinguishable from not pinning it."""
    bodies = {"carer": {"key": "carer", "place": "hall", "available": True,
                        "competence": {}},
              "down": {"key": "down", "place": "hall", "available": False,
                       "competence": {}}}
    held = {name: normalize_need(name, {})
            for name in ("rest", "sustenance", "health", "company")}
    held["sustenance"]["level"] = 0.0
    held["company"]["level"] = 0.0

    written = {"down": copy.deepcopy(held)}
    acts, _s, _c, _b, _r = enact(
        bodies, {}, written, _tending(bodies), {}, {}, 4.0,
        conduct={"carer": {"act": "tend", "other": "down"}})
    assert [act["line"] for act in acts] == ["carer tended down (sustenance)"]
    assert written["down"]["sustenance"]["level"] == 0.05


def _tending(bodies):
    from world.charter_practice import _open
    return dict([_open("tending", "hall", {"a": "carer", "b": "down"}, 0.0,
                       about="down")])
