"""D19 (review 2026-09-07): an institution keeps its OWN hours.

`day_cycle.RESTING_PHASES`/`SOCIAL_PHASES` are when the daylit majority
sleeps and when it goes out, and until this they were imposed on every
charter: a nightwatch, a pre-dawn bakery and a house that only opens after
dusk all kept a farmer's day, because the only two sets in the engine were
module constants read straight out of `charter_move.errands`.

The rule these pin: `resting_phases`/`social_phases` are optional fields on
the charter record; None is the shipped set (so every existing charter
behaves byte for byte as it did), an empty list is an institution with no
such phase at all, and an authored name the day cycle cannot read is told to
the author rather than dropped in silence.
"""

from __future__ import annotations

import copy
import sys

import pytest

sys.path.insert(0, "tests")

from world.charter import normalize_charter, seed_needs, seed_roster
from world.charter_move import errands
from world.charter_runtime import registry_warnings
from world.charter_space import frequented_places, reach_map
from world.day_cycle import RESTING_PHASES, SOCIAL_PHASES


def _town():
    from charter_worlds import small_town
    charter = normalize_charter(copy.deepcopy(small_town()))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    return charter


def _args(charter):
    reach = reach_map(charter["scene"], frequented_places(charter),
                      charter["bodies"])
    return (charter["bodies"], charter["needs"], charter["upkeeps"], {},
            frequented_places(charter), reach)


def test_a_nocturnal_institution_sleeps_by_day_and_works_by_night():
    charter = _town()
    args = _args(charter)
    # The inversion of the shipped sets, which is exactly what an institution
    # on the night shift is.
    nocturnal = {"resting_phases": ["midday", "afternoon"],
                 "social_phases": ["pre-dawn"]}

    assert errands(*args, seed=3, rate=1.0, hours=4.0,
                   commons=charter["commons"], phase="midday",
                   **nocturnal) == {}
    at_night = errands(*args, seed=3, rate=1.0, hours=4.0,
                       commons=charter["commons"], phase="night", **nocturnal)
    assert at_night, "a nocturnal institution stayed home in its own hours"

    social = errands(*args, seed=3, rate=1.0, hours=4.0,
                     commons=charter["commons"], phase="pre-dawn",
                     **nocturnal)
    assert social and set(social.values()) <= set(charter["commons"])


def test_the_shipped_sets_are_what_an_unauthored_charter_still_keeps():
    charter = _town()
    args = _args(charter)
    for phase in sorted(RESTING_PHASES):
        assert errands(*args, seed=3, rate=1.0, hours=4.0,
                       commons=charter["commons"], phase=phase) == {}
        assert errands(*args, seed=3, rate=1.0, hours=4.0,
                       commons=charter["commons"], phase=phase,
                       resting_phases=None, social_phases=None) == {}
    for phase in sorted(SOCIAL_PHASES):
        out = errands(*args, seed=3, rate=1.0, hours=4.0,
                      commons=charter["commons"], phase=phase)
        assert set(out.values()) <= set(charter["commons"])


def test_an_empty_set_is_an_institution_that_never_rests():
    """Absence and emptiness are different answers, the way `errand_rate`
    already keeps None and 0.0 apart."""
    charter = _town()
    args = _args(charter)
    assert errands(*args, seed=3, rate=1.0, hours=4.0,
                   commons=charter["commons"], phase="night") == {}
    assert errands(*args, seed=3, rate=1.0, hours=4.0,
                   commons=charter["commons"], phase="night",
                   resting_phases=[])


def test_normalisation_keeps_the_fields_and_keeps_absence_apart_from_empty():
    stored = copy.deepcopy(_town())
    assert normalize_charter(stored)["resting_phases"] is None
    assert normalize_charter(stored)["social_phases"] is None

    stored["resting_phases"] = ["midday", "midday", "afternoon"]
    stored["social_phases"] = []
    out = normalize_charter(stored)
    assert out["resting_phases"] == ["afternoon", "midday"]
    assert out["social_phases"] == []


def test_the_run_hands_the_institutions_own_hours_to_its_errands():
    """The wiring, not just the leaf: `charter_run` reads the record.

    One window, straddling the middle of the night on a charter told when
    its day begins. Under the shipped sets that is rest and nobody stirs;
    with rest authored as empty, the same window at the same seed sends
    people out.
    """
    from world.charter import step

    def one_night_window(**authored):
        charter = _town()
        charter["errand_rate"] = 1.0
        charter["day_anchor_hours"] = 0.0    # charter hour 0 is midnight
        charter["day_length_hours"] = 24.0
        charter.update(authored)
        after, _events = step(charter, hours=4.0, seed=3)
        return {key for key, body in after["bodies"].items()
                if body["place"] != charter["bodies"][key]["place"]
                and key not in set(after["watch"].values())}

    assert one_night_window() == set(), \
        "the shipped resting set stopped holding the town in its berths"
    assert one_night_window(resting_phases=[]), \
        "an institution that never rests still slept through the night"


def test_an_hour_the_cycle_cannot_read_is_told_to_the_author():
    charter = _town()
    charter["resting_phases"] = ["midnight"]      # not a phase of any day
    charter["social_phases"] = ["evening"]
    notices = registry_warnings({"items": {"town": {"state": charter}}})
    assert any("resting_phases names 'midnight'" in n for n in notices)
    assert not any("social_phases" in n for n in notices)


@pytest.mark.parametrize("field", ["resting_phases", "social_phases"])
def test_a_readable_set_draws_no_warning(field):
    charter = _town()
    charter[field] = ["night"]
    notices = registry_warnings({"items": {"town": {"state": charter}}})
    assert not any(field in n for n in notices)


def test_an_hour_is_the_same_hour_however_the_author_typed_it():
    """D19 rework. `charter_creature` has always read `active_phases`
    stripped and casefolded; these two fields were reading their names
    verbatim, so one author writing "Night" on one record got a working
    field and a warned one. Casing is not a different hour.
    """
    stored = copy.deepcopy(_town())
    stored["resting_phases"] = ["Night", " dusk", "NIGHT"]
    stored["social_phases"] = ["Evening "]
    out = normalize_charter(stored)

    assert out["resting_phases"] == ["dusk", "night"]
    assert out["social_phases"] == ["evening"]
    assert registry_warnings({"items": {"town": {"state": out}}}) == \
        registry_warnings({"items": {"town": {"state": _town()}}})


def test_the_authored_casing_reaches_the_hours_it_names():
    """Not just the stored shape: the phase the day cycle hands `errands` is
    lower-case, so a verbatim "Night" was an unreachable rest set and the
    town walked out at three in the morning."""
    charter = _town()
    args = _args(charter)
    authored = normalize_charter(
        dict(copy.deepcopy(_town()), resting_phases=["Midday"],
             social_phases=["Pre-Dawn"]))

    assert errands(*args, seed=3, rate=1.0, hours=4.0,
                   commons=charter["commons"], phase="midday",
                   resting_phases=authored["resting_phases"],
                   social_phases=authored["social_phases"]) == {}
    social = errands(*args, seed=3, rate=1.0, hours=4.0,
                     commons=charter["commons"], phase="pre-dawn",
                     resting_phases=authored["resting_phases"],
                     social_phases=authored["social_phases"])
    assert social and set(social.values()) <= set(charter["commons"])


def test_a_creature_told_an_hour_the_day_has_not_got_is_told_so_too():
    """D19 rework, the sibling site. `creature.active_phases` is matched
    against `charter_phase` exactly as the two fields above are
    (`charter_creature.is_active`) and carried no warning at all, so a
    creature authored to hunt at 'midnight' hunts at every hour and nothing
    anywhere says why."""
    charter = _town()
    charter["creature"] = {"active_phases": ["midnight", "Night"]}
    notices = registry_warnings({"items": {"town": {"state": charter}}})

    assert any("creature.active_phases names 'midnight'" in n
               for n in notices)
    assert not any("'night'" in n for n in notices), \
        "the authored casing was read as an hour the day has not got"
