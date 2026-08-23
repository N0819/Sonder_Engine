"""Optional audit: population feeling and temperament, produced by affect
model rather than beside it.

The mood experiment set the bar: a scalar built at this tier from pressure,
blame and regard correlated with `pressure` at r = 0.994 and stayed out of
the planner as a duplicate. `charter_feel` instead calls
`mind/psychology_runtime.resolve_hedonic`/`resolve_stress` over channelled
inputs, and measured on the same fixtures the correlation is 0.07-0.72
depending on crisis phase — same institution, different information. These
tests pin the properties that made that true.
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import pathlib

from mind.psychology_runtime import resolve_hedonic, resolve_stress

from world.charter import (
    STRAIN_REST_TOLL,
    advance_feel,
    advance_needs,
    appraise_window,
    body_state,
    derived_temperament,
    felt_handoff,
    normalize_charter,
    run,
    seed_needs,
    seed_roster,
    temperament_of,
    temperament_warnings,
)
import world.charter_run as charter_run

from charter_worlds import twin_towns


def _ready(spec, feed=""):
    charter = normalize_charter(copy.deepcopy(spec))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    if feed:
        for held in charter["needs"].values():
            held["sustenance"]["fed_by"] = feed
    return charter


def _fed_towns():
    charter = _ready(twin_towns(240))
    for key, held in charter["needs"].items():
        held["sustenance"]["fed_by"] = (
            "up_bread" if key.startswith("up_") else "low_bread")
    return charter


def _cut_roads(charter):
    for body in charter["bodies"].values():
        if "arms" in body["competence"]:
            body["available"] = False
    return charter


_FAMINE_CACHE = {}


def _famine(fresh=False):
    """Twin towns run 20 quiet days, the road cut, 20 famine days. Cached,
    because four tests read the same world and a famine of 240 bodies is not
    free; ``fresh`` recomputes for the replay test, which must not be handed
    its own memoized answer."""
    if fresh or "famine" not in _FAMINE_CACHE:
        warm, _ = run(_fed_towns(), hours=480.0, window=4.0, seed=5)
        result = run(_cut_roads(warm), hours=480.0, window=4.0, seed=7)
        if fresh:
            return result
        _FAMINE_CACHE["famine"] = result
    after, events = _FAMINE_CACHE["famine"]
    return copy.deepcopy(after), copy.deepcopy(events)


class TestTheHandoffIsActuallyRead:
    """`body_state` claimed to be the shape `resolve_hedonic` takes, and the
    first version returned keys the resolver never reads — the same
    caller/callee shape agreement `resolve_stress`'s docstring records for
    `goal_impacts`. These assert the contract by CALLING the consumer."""

    def test_the_vitals_speak_survivals_vocabulary(self):
        held = {
            "rest": {"key": "rest", "level": 0.4, "floor": 0.15,
                     "drift_per_hour": 0.0, "service_per_hour": 0.0,
                     "fed_by": ""},
            "sustenance": {"key": "sustenance", "level": 0.6, "floor": 0.1,
                           "drift_per_hour": 0.0, "service_per_hour": 0.0,
                           "fed_by": ""},
            "health": {"key": "health", "level": 0.3, "floor": 0.2,
                       "drift_per_hour": 0.0, "service_per_hour": 0.0,
                       "fed_by": ""},
        }
        state = body_state(held)
        assert state["stamina"] == 0.4
        assert state["nourishment"] == 0.6
        assert state["injury"] == 0.7

    def test_resolve_hedonic_feels_a_broken_body(self):
        """A body whose health need is nearly gone must arrive at the
        character tier in pain, with no appraisal proposing any — the
        deterministic injury floor doing its job on charter-produced
        state."""
        held = {"health": {"key": "health", "level": 0.2, "floor": 0.2,
                           "drift_per_hour": 0.0, "service_per_hour": 0.0,
                           "fed_by": ""}}
        hedonic = resolve_hedonic({}, {}, {}, body_state(held),
                                  elapsed_units=1.0)
        assert hedonic["pain"] >= 0.6

    def test_the_handoff_continues_at_the_character_tier(self):
        """The promotion payload feeds the character tier's resolvers as-is:
        a copy, not a translation."""
        after, _ = _famine()
        felt = [k for k in after["bodies"] if k in after["feel"]]
        assert felt, "a famine nobody felt"
        payload = felt_handoff(felt[0], after)
        assert set(payload) >= {"hedonic", "stress", "body_state",
                                "interoception", "stress_profile", "stood"}
        hedonic = resolve_hedonic(payload["hedonic"], {},
                                  payload["interoception"],
                                  payload["body_state"], elapsed_units=1.0)
        stress = resolve_stress(payload["stress"], {},
                                payload["stress_profile"], hedonic,
                                elapsed_units=1.0)
        assert 0.0 <= hedonic["pain"] <= 1.0
        assert 0.0 <= stress["strain"] <= 1.0


class TestQuietIsFree:
    def test_a_working_institution_feels_nothing(self):
        """Sparseness IS the cost model here: a quiet month holds no feel
        entries at all, so there is nothing to advance, store, or replay."""
        after, events = run(_ready(twin_towns(240)), hours=480.0, window=4.0)
        assert events == []
        assert after["feel"] == {}

    def test_the_toll_at_zero_is_a_true_control(self):
        """With `strain_toll` pinned to zero a run is identical to one where
        feel is absent entirely — an experiment that quietly alters its own
        control is not an experiment. Same guard the mood dial carries."""
        pinned = _ready(twin_towns(240))
        pinned["strain_toll"] = 0.0
        with_feel, feel_events = run(pinned, hours=240.0, window=4.0, seed=3)

        absent = _ready(twin_towns(240))
        absent["strain_toll"] = 0.0
        original = charter_run.advance_feel
        charter_run.advance_feel = lambda *a, **k: {}
        try:
            without, without_events = run(absent, hours=240.0, window=4.0,
                                          seed=3)
        finally:
            charter_run.advance_feel = original

        assert feel_events == without_events
        assert with_feel["needs"] == without["needs"]
        assert with_feel["upkeeps"] == without["upkeeps"]


class TestFeelingIsChannelled:
    """A mind may use only what reached it through a channel: its own needs,
    the state of the place it stands, the transient events there."""

    def _upkeeps(self, place="here", level=0.1, floor=0.3):
        return {"kept": {"key": "kept", "place": place, "level": level,
                         "floor": floor, "drift_per_hour": 0.0,
                         "service_per_hour": 0.0, "requires": {},
                         "depends_on": []}}

    def test_a_failure_is_felt_where_it_stands_and_not_elsewhere(self):
        _, near = appraise_window("a", "here", self._upkeeps(), ())
        _, far = appraise_window("b", "away", self._upkeeps(), ())
        assert near and not far

    def test_your_own_charge_failing_weighs_more_than_a_strangers(self):
        _, witness = appraise_window("a", "here", self._upkeeps(), ())
        _, holder = appraise_window("a", "here", self._upkeeps(), (),
                                    own_upkeeps={"kept"})
        worst = lambda impacts: min(i["impact"] for i in impacts)
        assert worst(holder) < worst(witness)

    def test_a_register_fact_moves_nobody(self):
        """`post_unfilled` is an entry in the institution's books, not a
        state of the room, and a mind may not appraise a ledger it has
        never read."""
        events = ({"kind": "post_unfilled", "at_hours": 4.0, "place": "here",
                   "post": "p", "reason": "contended", "serves": []},)
        appraisal, impacts = appraise_window(
            "a", "here", {}, events,
            held_needs={"rest": {"key": "rest", "level": 1.0, "floor": 0.15,
                                 "drift_per_hour": 0.0,
                                 "service_per_hour": 0.0, "fed_by": ""}})
        assert appraisal == {} and impacts == []

    def test_deprivation_is_pain_and_names_the_need(self):
        held = {"sustenance": {"key": "sustenance", "level": 0.0,
                               "floor": 0.1, "drift_per_hour": 0.0,
                               "service_per_hour": 0.0, "fed_by": ""}}
        appraisal, _ = appraise_window("a", "here", {}, (), held_needs=held)
        somatic = appraisal["somatic_impact"]
        assert somatic["pain"] > 0.0
        assert "sustenance" in somatic["why"]


class TestTemperament:
    def test_derived_is_stable_and_not_uniform(self):
        first = derived_temperament("someone")
        again = derived_temperament("someone")
        other = derived_temperament("someone_else")
        assert first == again
        assert first != other

    def test_authoring_overrides_per_trait_and_is_validated(self):
        body = {"key": "x", "temperament": {"baseline_reactivity": 0.8}}
        temperament = temperament_of(body)
        assert temperament["baseline_reactivity"] == 0.8
        # The unauthored traits are the derived ones, not silent defaults.
        assert temperament["recovery_rate"] == \
            derived_temperament("x")["recovery_rate"]

        warned = temperament_warnings("x", {
            "baseline_reactivity": 7.0,
            "spelling_mistake": 0.5,
            "recovery_rate": "fast",
        })
        assert any("outside" in w for w in warned)
        assert any("spelling_mistake" in w for w in warned)
        assert any("not a number" in w for w in warned)

    def test_the_same_week_lands_differently_on_different_people(self):
        """Two bodies in the same room, the same needs, the same failing
        condition. The strain gap between them is temperament and nothing
        else — measured on the famine at 0.296 vs 0.485 for two co-located
        bodies at identical pressure 1.0."""
        upkeeps = {"kept": {"key": "kept", "place": "here", "level": 0.0,
                            "floor": 0.3, "drift_per_hour": 0.0,
                            "service_per_hour": 0.0, "requires": {},
                            "depends_on": []}}
        bodies = {k: {"key": k, "competence": {}, "available": True,
                      "stood_down": False, "place": "here"}
                  for k in ("calm_one", "raw_one")}
        needs = seed_needs(bodies)
        feel = {}
        for _ in range(6):
            feel = advance_feel(
                feel, bodies, needs, {}, {}, upkeeps, (), 4.0,
                temper_of=lambda body: dict(
                    derived_temperament(body["key"]),
                    baseline_reactivity=0.2 if body["key"] == "calm_one"
                    else 0.8))
        calm = feel["calm_one"]["stress"]["strain"]
        raw = feel["raw_one"]["stress"]["strain"]
        assert raw > calm > 0.0


class TestTheTollIsPhysicalNotPolitical:
    """Strain reaches the institution through rest — a shaken body sleeps
    badly — never through the planner's reluctance axis, where the mood
    experiment measured a duplicate signal."""

    def test_a_strained_body_spends_rest_faster(self):
        bodies = {"a": {"key": "a", "competence": {}, "available": True,
                        "stood_down": False, "place": ""}}
        needs = seed_needs(bodies)
        watch = {"somewhere": "a"}
        rested, _, _ = advance_needs(dict(needs), bodies, watch, {}, 8.0)
        worn, _, _ = advance_needs(dict(needs), bodies, watch, {}, 8.0,
                                   strain={"a": 1.0}, toll=STRAIN_REST_TOLL)
        assert worn["a"]["rest"]["level"] < rested["a"]["rest"]["level"]
        # Only rest is disturbed; hunger is not a nerve.
        assert worn["a"]["sustenance"]["level"] == \
            rested["a"]["sustenance"]["level"]

    def test_no_planner_reads_feeling(self):
        """The mood rule, extended to feel: nothing in the planning path may
        consult felt state. Reading the source is the guard that caught the
        genre nouns; it holds here too."""
        package = pathlib.Path(charter_run.__file__).parent
        plan_source = (package / "charter_plan.py").read_text()
        for name in ("feel", "strain", "hedonic", "mood"):
            assert name not in plan_source, (
                f"charter_plan reads {name!r}; feeling may cost rest, "
                "never a place in the watch bill ordering")


class TestStorageStaysIncident:
    def test_feel_and_stood_grow_with_shape_not_time(self):
        """The rule this package has broken three times, checked for the
        fourth: twice the quiet hours must mean identical feel storage and
        identical STOOD KEY COUNTS — the ledger deepens, it does not widen.

        Pinned at `errand_rate: 0.0`, because the strict form of the
        invariant belongs to the frozen world it was written in: once the
        population circulates, the watch legitimately rotates through more
        hands over more time and `stood` widens TOWARD its bodies-x-posts
        bound. That bounded widening has its own test below.
        """
        still = _ready(twin_towns(240))
        still["errand_rate"] = 0.0
        short, _ = run(still, hours=240.0, window=4.0)
        long_, _ = run(dict(still, errand_rate=0.0), hours=480.0, window=4.0)

        assert short["feel"] == {} and long_["feel"] == {}
        assert set(short["stood"]) == set(long_["stood"])
        for body, held in long_["stood"].items():
            assert set(held) == set(short["stood"][body])

    def test_a_circulating_watch_widens_only_within_its_shape(self):
        """With errands on, more time may mean more hands have taken a turn
        — but the ledger stays inside bodies x posts, and doubling the
        quiet hours must not double the pairs. Width is bounded by the
        SHAPE; only depth is bought with time."""
        short, _ = run(_ready(twin_towns(240)), hours=240.0, window=4.0)
        long_, _ = run(_ready(twin_towns(240)), hours=480.0, window=4.0)

        def pairs(charter):
            return {(body, post) for body, held in charter["stood"].items()
                    for post in held}

        assert short["feel"] == {} and long_["feel"] == {}
        assert pairs(long_) >= pairs(short)
        assert len(pairs(long_)) <= 2 * len(pairs(short))
        posts = set(long_["posts"])
        assert all(post in posts for _body, post in pairs(long_))

    def test_a_famine_writes_no_new_event_kinds(self):
        """Feeling produces state, never rows: the event vocabulary is
        exactly what it was before the module existed."""
        _, events = _famine()
        kinds = {e["kind"] for e in events}
        assert kinds <= {"post_unfilled", "post_filled_again",
                         "post_believed_filled", "upkeep_out_of_band",
                         "upkeep_restored", "body_unable", "body_recovered"}


class TestReplay:
    def test_feeling_replays_byte_identical(self):
        one, one_events = _famine(fresh=True)
        two, two_events = _famine(fresh=True)
        assert one_events == two_events
        assert one["feel"] == two["feel"]

    def test_the_watch_ordering_survives_a_new_process(self):
        """`plan_watch`'s tie-break used `hash()`, which Python salts per
        process — so 'same seed, byte-identical' held in a same-process
        replay test and would not have held across the restart a checkpoint
        restore actually is. Two interpreters, forced onto different hash
        seeds, must produce the same watch."""
        script = (
            "import json, sys; sys.path.insert(0, {root!r}); "
            "sys.path.insert(0, {tests!r}); "
            "from world.charter import normalize_charter, seed_roster, "
            "plan_watch; from charter_fixtures import SHIP; "
            "c = normalize_charter(SHIP); "
            "c['roster'] = seed_roster(c['bodies']); "
            "print(json.dumps(plan_watch(c, seed=9)['watch'], "
            "sort_keys=True))"
        ).format(root=str(pathlib.Path(__file__).resolve().parent.parent),
                 tests=str(pathlib.Path(__file__).resolve().parent.parent
                           / "tests"))
        watches = []
        for hash_seed in ("1", "2"):
            env = dict(os.environ, PYTHONHASHSEED=hash_seed)
            out = subprocess.run([sys.executable, "-c", script], env=env,
                                 capture_output=True, text=True, check=True)
            watches.append(json.loads(out.stdout))
        assert watches[0] == watches[1]


class TestTheFamineIsFelt:
    def test_a_crisis_produces_feeling_and_a_recovery_lets_it_go(self):
        """Feeling rises with the incident and drains after it — the sparse
        dict empties again once the needs are met and nothing is failing,
        which is what keeps a long story from accumulating a permanent
        anxiety ledger."""
        after, _ = _famine()
        assert after["feel"], "a famine nobody felt"

        # End the famine: restore every body and every upkeep, then let
        # quiet windows pass. What remains should drain to nothing.
        for body in after["bodies"].values():
            body["available"] = True
            body["stood_down"] = False
        for upkeep in after["upkeeps"].values():
            upkeep["level"] = 1.0
        for held in after["needs"].values():
            for need in held.values():
                need["level"] = 1.0
        # The register is state too: left holding "everyone is down", the
        # charter would staff nothing, the chains would fail again, and the
        # feeling would be CORRECT to persist. The claim under test is that
        # feel drains when nothing is wrong, so make nothing wrong.
        after["roster"] = seed_roster(after["bodies"])
        after["minds"] = {}
        calm, _ = run(after, hours=480.0, window=4.0, seed=13)
        assert calm["feel"] == {}

    def test_strain_is_not_a_synonym_for_pressure(self):
        """The information claim, pinned. Mid-famine, bodies at IDENTICAL
        saturated pressure carry strains spread over about a threefold
        range, because what they stood next to and who they are differ.
        Measured 0.161-0.485 across 240 bodies at pressure 1.0."""
        after, _ = _famine()
        from world.charter import pressure as pressure_of
        saturated = [k for k in after["bodies"]
                     if pressure_of(after["needs"].get(k) or {}) >= 0.999]
        strains = [float((after["feel"].get(k) or {}).get("stress", {})
                         .get("strain") or 0.0) for k in saturated]
        assert len(saturated) >= 50
        assert max(strains) > 2.0 * min(strains) + 0.05, (
            "equal-pressure bodies all feel alike; strain has collapsed "
            "into a pressure synonym")
