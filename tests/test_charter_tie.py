"""The discrete tie: one word for what the five axes already say.

`docs/guides/RESEARCH.md` §1.7.6 item 3. Comme il Faut keeps a numeric social
network AND a set of discrete relationships on purpose — numbers drive
scoring, labels drive legibility, and a narrator can say "they are close"
where it cannot say a five-tuple. Charter had the numbers
(`world/charter_social.py`'s trust/warmth/fear/respect/suspicion) and no
label, so nothing downstream could state a relationship in a word.

MEASURED ON `twin_towns(40)` BEFORE THE TESTS BELOW WERE WRITTEN, because
every threshold in `charter_social` was set from one of these numbers:

  * window 8h, seed 5, healthy: `familiar` labels 0.0% of the 1560 directed
    pairs after a simulated week, 14.7% after a month and 26.4% after a year,
    against a 27.9% ceiling of pairs that ever shared a place at all. That is
    what set `FAMILIAR_FLOOR = 24` shared windows.
  * the same healthy year holds 4 judgment holders and 7 stances and forms
    NO signed tie. A stable institution produces `familiar` and nothing else,
    which is the correct reading of the evidence layer rather than a defect
    in this one.
  * window 4h, seed 7, driven into famine: 40 judgment holders, 149 stances,
    and 16 `close` + 11 `looks_up_to` labels across the quarter, 11 of them
    requited. RESEARCH.md §1.7.6 item 2 is what made that possible — before
    its producers landed, the largest axis anywhere in a stressed simulated
    year was 0.142 against a form threshold of 0.30 and this layer could
    only ever have delivered `familiar`.

Cost, measured on `.venv` with the tie pass swapped for a no-op and the two
arms strictly INTERLEAVED so machine drift cannot land on one of them: a
simulated healthy year costs 17.49s and 16.82s without the pass against
17.40s and 16.87s with it — inside the run-to-run spread, and one tie arm came
out FASTER, which is what noise looks like. A famine quarter costs 24.05s and
23.38s against 24.47s and 25.69s, about 3%, and that is the whole of the
pass's cost: it is paid only where 40 bodies actually hold stances. The holder
gate is why — a body holding neither a judgment nor a tie is skipped before
its co-presence is walked, so a healthy institution pays O(bodies) per window
and not O(pairs).
"""

from __future__ import annotations

import copy
import time

from world.charter import (
    CLOSE_FAMILIARITY, FAMILIAR_FLOOR, TIE_CAP, TIE_DWELL_HOURS, TIE_FORM,
    TIE_HOLD, TIE_LABELS, TIE_SATURATION, TIE_WEIGHTS, WITNESSABLE,
    derive_tie, familiarity, normalize_charter, promotion_handoff, run,
    scene_ledger, seed_needs, seed_roster, summarize, tie_of, tie_view,
    update_ties)
from world.charter_politics import REGARD_CEILING, REGARD_FLOOR
from world.charter_runtime import (bind_promoted_character, registry_for,
                                   save_registry)

from world.charter_observe import apply_public_evidence

from charter_worlds import twin_towns


AXES = ("trust", "warmth", "fear", "respect", "suspicion")


def _stance(**axes):
    """One five-axis stance, everything unnamed sitting at zero."""
    entry = {axis: 0.0 for axis in AXES}
    entry.update(axes)
    entry["reasons"] = [{"evidence_id": "e1", "signal": "aid_given",
                         "source": "", "weight": 1.0},
                        {"evidence_id": "e2", "signal": "aid_given",
                         "source": "", "weight": 1.0},
                        {"evidence_id": "e3", "signal": "aid_given",
                         "source": "", "weight": 1.0}]
    entry["seen"] = ["e1", "e2", "e3"]
    return entry


def _claim(key):
    """The ordinary body claim one head holds about another."""
    return {"body": key, "competence": {}, "believed_available": True,
            "strength": 1.0, "as_of_hours": 0.0}


def _crew(judgments=None, ties=None, shared=100):
    """Two bodies who have stood a hundred watches in the same yard."""
    return normalize_charter({
        "key": "yard",
        "posts": {"gate": {"place": "yard", "serves": []}},
        "bodies": {
            "ada": {"place": "yard", "competence": {}, "available": True},
            "bo": {"place": "yard", "competence": {}, "available": True},
        },
        "minds": {"ada": {"bo": _claim("bo")}, "bo": {"ada": _claim("ada")}},
        "served_beside": {"ada": {"bo": shared}, "bo": {"ada": shared}},
        "judgments": judgments or {},
        "ties": ties or {},
    })


def _quantities(bond=0.0, guard=0.0, dread=0.0, esteem=0.0):
    return {"bond": bond, "guard": guard, "dread": dread, "esteem": esteem}


def _twin_towns(hours, *, drift=None, window=4.0, seed=7, folk=40):
    charter = normalize_charter(copy.deepcopy(twin_towns(folk=folk)))
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    charter["active_places"] = []
    if drift is not None:
        charter["upkeeps"]["road_open"]["drift_per_hour"] = drift
    return run(charter, hours=hours, window=window, seed=seed)


_RUNS = {}


def _cached(name, *args, **kwargs):
    """One simulated run per shape per session. The famine arm is 1.8s and
    four tests want the same 480 hours of it."""
    if name not in _RUNS:
        _RUNS[name] = _twin_towns(*args, **kwargs)
    charter, events = _RUNS[name]
    return copy.deepcopy(charter), list(events)


def _labels(charter):
    keys = sorted(charter["bodies"])
    beside = charter.get("served_beside") or {}
    counted = {}
    for holder in keys:
        for other in keys:
            if other == holder:
                continue
            label = tie_of(charter.get("ties"), holder, other,
                           served_beside=beside)
            if label:
                counted[label] = counted.get(label, 0) + 1
    return counted


class TestATieIsOneHeadsView:
    """The firewall on this layer, stated as a shape rather than an
    intention: `ties[holder][other]` is built from `judgments[holder][other]`,
    `regard["holder->other"]` and `served_beside[holder][other]`, and from
    nothing else that exists."""

    def test_a_tie_is_one_head_s_view_and_the_other_head_may_not_hold_it(self):
        """CiF's discrete relationships are symmetric by definition. Here they
        cannot be, because two people do not share a head — the mirror of
        `test_charter_promote.py`'s regard case, one layer up."""
        one_sided = _crew(judgments={"ada": {"bo": _stance(warmth=0.7)}})
        ties, _ = update_ties(
            None, company={"yard": ["ada", "bo"]},
            judgments=one_sided["judgments"],
            served_beside=one_sided["served_beside"], at_hours=0.0)

        assert ties["ada"]["bo"]["tie"] == "close"
        assert "bo" not in ties, "bo holds nothing and was handed a bond"

        # And bo coming to adore ada must not touch what ada holds.
        both = _crew(judgments={"ada": {"bo": _stance(warmth=0.7)},
                                "bo": {"ada": _stance(warmth=1.0, trust=1.0)}})
        after, _ = update_ties(
            None, company={"yard": ["ada", "bo"]},
            judgments=both["judgments"],
            served_beside=both["served_beside"], at_hours=0.0)

        assert after["ada"] == ties["ada"]

    def test_a_tie_never_reaches_the_head_that_is_held(self):
        """`scene_ledger`'s presence slice is copied into a model payload
        voicing that body, so "they hold me close" — the other head's
        interior — must not be in it, and neither must any count of how many
        ties are requited."""
        charter = _crew(
            judgments={"ada": {"bo": _stance(warmth=0.7)},
                       "bo": {"ada": _stance(warmth=0.7)}})
        charter["ties"], _ = update_ties(
            None, company={"yard": ["ada", "bo"]},
            judgments=charter["judgments"],
            served_beside=charter["served_beside"], at_hours=0.0)

        view = scene_ledger(charter, "yard")

        entry = view["presences"]["ada"]["knows_here"]["bo"]
        assert entry["tie"] == "close"
        assert set(entry) == {"firsthand", "believes_present", "regard", "tie"}
        for presence in view["presences"].values():
            assert "mutual_ties" not in presence
            assert "ties" not in presence

    def test_mutuality_is_the_author_s_and_nobody_else_s(self):
        """It may be counted in `charter_log`, whose docstring is explicit
        that nothing here is canon and no mind reads it, and it exists in no
        other shape anywhere."""
        charter = _crew(
            judgments={"ada": {"bo": _stance(warmth=0.7)},
                       "bo": {"ada": _stance(warmth=0.7)}})
        charter["ties"], _ = update_ties(
            None, company={"yard": ["ada", "bo"]},
            judgments=charter["judgments"],
            served_beside=charter["served_beside"], at_hours=0.0)

        assert summarize(charter, [])["mutual_ties"] == 1
        for row in charter["ties"]["ada"].values():
            assert "mutual" not in row


class TestTheNumbersAreTheAuthority:
    """A label that can disagree with the axes it summarizes is a second
    store, and a second store is the thing this design is built to avoid."""

    def test_the_numbers_delete_a_label_they_no_longer_support(self):
        """The one test that makes "cannot contradict the numbers" structural
        rather than aspirational: `normalize_charter` runs on both load and
        save, so this covers archive import, checkpoint restore of an older
        charter shape, a hand-edited registry, and any future writer that
        moves a judgment without calling the tie updater."""
        planted = _crew(
            judgments={"ada": {"bo": _stance(warmth=-0.5)}},
            ties={"ada": {"bo": {"tie": "close", "since_hours": 0.0,
                                 "because": []}}})

        assert planted["ties"] == {}, \
            "a bond survived a head that dislikes them"

    def test_a_label_outside_the_vocabulary_is_dropped(self):
        planted = _crew(
            judgments={"ada": {"bo": _stance(warmth=0.9)}},
            ties={"ada": {"bo": {"tie": "betrothed", "since_hours": 0.0}}})

        assert planted["ties"] == {}

    def test_a_tie_to_somebody_who_is_not_a_body_is_dropped(self):
        """The rule `experiences` and `habit_runs` already follow: a store
        keyed by a body that left the charter is a row nothing can resolve."""
        planted = _crew(
            judgments={"ada": {"ghost": _stance(warmth=0.9)}},
            ties={"ada": {"ghost": {"tie": "close", "since_hours": 0.0}}})

        assert planted["ties"] == {}

    def test_a_bond_needs_time_in_the_same_room(self):
        """`CLOSE_FAMILIARITY` is a FORMATION gate: you cannot be close to
        somebody you have barely been near, however well the axes read. A
        stranger who does you one enormous favour is somebody you TRUST, and
        that is what the axes say on their own."""
        strangers = _crew(judgments={"ada": {"bo": _stance(warmth=0.9)}},
                          shared=1)
        ties, _ = update_ties(
            None, company={"yard": ["ada", "bo"]},
            judgments=strangers["judgments"],
            served_beside=strangers["served_beside"], at_hours=0.0)

        assert ties == {}
        assert familiarity(strangers["served_beside"], "ada", "bo") \
            < CLOSE_FAMILIARITY

    def test_a_planted_bond_between_strangers_does_not_survive_a_save(self):
        """The other half of `CLOSE_FAMILIARITY`, and the half that makes it
        structural: `normalize_ties` re-checks the formation gate, so a
        `close` hand-planted on a pair who never shared a room is gone on the
        next load even though the axes read 0.9 warmth. It can only ever
        delete a row this package could not have written -- `served_beside`
        only rises, so a legitimately formed `close` cannot fall back through
        the gate -- which is why the re-check is safe to run on every
        persistence boundary rather than only where rows are written."""
        planted = _crew(
            judgments={"ada": {"bo": _stance(warmth=0.9)}}, shared=1,
            ties={"ada": {"bo": {"tie": "close", "since_hours": 0.0}}})

        assert planted["ties"] == {}
        # And the same axes with the room-time behind them keep it.
        earned = _crew(
            judgments={"ada": {"bo": _stance(warmth=0.9)}}, shared=100,
            ties={"ada": {"bo": {"tie": "close", "since_hours": 0.0}}})
        assert earned["ties"]["ada"]["bo"]["tie"] == "close"

    def test_ties_are_capped_per_holder_however_long_the_run(self):
        """The same cap and the same argument as `JUDGMENT_CAP`: a head that
        holds a view about everyone holds a useful view about no one. This is
        also the whole of the store's growth bound — it is keyed bodies x
        bodies with a per-holder cap, so it grows with the SHAPE of the
        institution and never with the clock."""
        folk = {f"b{i:03d}": {"place": "yard", "competence": {},
                              "available": True} for i in range(60)}
        judgments = {"b000": {other: _stance(warmth=0.9)
                              for other in folk if other != "b000"}}
        planted = normalize_charter({
            "key": "yard", "bodies": folk, "judgments": judgments,
            "served_beside": {"b000": {o: 100 for o in folk}},
            "ties": {"b000": {other: {"tie": "close", "since_hours": 0.0}
                              for other in folk if other != "b000"}},
        })

        assert len(planted["ties"]["b000"]) == TIE_CAP


class TestFormingIsHarderThanHolding:
    def test_a_tie_survives_the_band_it_formed_above(self):
        """Hysteresis, or a tie is a number with a name on it: the label
        would flicker every time the arithmetic crossed a line, and the
        legible half of this design would be less legible than the numbers it
        summarizes."""
        formed = derive_tie(_quantities(bond=TIE_FORM), 1.0, None, 0.0)
        assert formed == "close"

        held = {"tie": "close", "since_hours": 0.0}
        assert derive_tie(_quantities(bond=0.22), 1.0, held, 1000.0) == "close"
        assert derive_tie(_quantities(bond=0.15), 1.0, held, 1000.0) == ""

    def test_a_rupture_breaks_a_bond_the_same_window_it_lands(self):
        """Forming takes a season, losing takes an instant. Inside the dwell
        an ordinary relabel waits; `at_odds` and `afraid_of` do not, because
        a rupture that had to sit out a day would be a rupture the state
        cannot represent."""
        young = {"tie": "close", "since_hours": 0.0}
        inside_dwell = TIE_DWELL_HOURS / 2.0

        ordinary = derive_tie(_quantities(bond=0.25, esteem=0.6), 1.0,
                              young, inside_dwell)
        rupture = derive_tie(_quantities(bond=0.25, dread=0.6), 1.0,
                             young, inside_dwell)

        assert ordinary == "close", "an ordinary relabel jumped the dwell"
        assert rupture == "afraid_of"
        # And the ordinary one does land once the label has had its day.
        assert derive_tie(_quantities(bond=0.25, esteem=0.6), 1.0, young,
                          TIE_DWELL_HOURS * 2) == "looks_up_to"

    def test_regard_alone_cannot_form_a_tie(self):
        """The soundness proof for `update_ties`' holder prefilter: a body
        with no stance and no tie is skipped before its co-presence is
        walked, which is only correct while directed regard — which EVERY
        pair in a charter has — cannot cross a threshold by itself."""
        assert TIE_WEIGHTS["regard"] < TIE_FORM

        for pinned in (REGARD_FLOOR, REGARD_CEILING):
            charter = _crew(judgments={"ada": {"bo": _stance()}})
            regard = {"ada->bo": pinned}
            ties, changes = update_ties(
                None, company={"yard": ["ada", "bo"]},
                judgments=charter["judgments"], politics={"regard": regard},
                served_beside=charter["served_beside"], at_hours=0.0)

            assert ties == {}, f"regard {pinned} minted a tie on its own"
            assert changes == []


class TestTheMeasuredInstitution:
    def test_nobody_is_familiar_after_a_week_and_the_crew_is_after_a_month(self):
        """twin_towns(40), window 8h, seed 5: 0 of 1560 directed pairs read
        `familiar` at 168 hours and 230 do at 720, against 418 pairs that had
        ever shared a place by then. The measurement that set
        `FAMILIAR_FLOOR = 24`."""
        week, _ = _cached("week", 168.0, window=8.0, seed=5)
        month, _ = _cached("month", 720.0, window=8.0, seed=5)

        assert _labels(week) == {}
        assert 100 <= _labels(month)["familiar"] <= 400
        assert familiarity({"a": {"b": TIE_SATURATION}}, "a", "b") == 1.0
        assert tie_of({}, "a", "b",
                      served_beside={"a": {"b": FAMILIAR_FLOOR}}) == "familiar"
        assert tie_of({}, "a", "b",
                      served_beside={"a": {"b": FAMILIAR_FLOOR - 1}}) == ""

    def test_a_healthy_year_of_this_engine_forms_no_signed_tie(self):
        """PINNED HONESTLY RATHER THAN HIDDEN. A stable institution produces
        `familiar` and nothing else: measured on twin_towns(40), window 8h,
        seed 5, a simulated year holds 4 judgment holders, 7 stances and zero
        signed labels. This test fails the day the evidence layer gets
        stronger, which is exactly when these thresholds must be re-measured
        rather than quietly lowered until `familiar` pairs read as friends."""
        year, _ = _cached("year", 8760.0, window=8.0, seed=5)

        assert set(_labels(year)) == {"familiar"}
        assert year["ties"] == {}
        assert len(year["judgments"]) <= 8

    def test_a_famine_is_what_it_takes_to_earn_a_signed_label(self):
        """And the other half of the same honesty: with `RESEARCH.md` §1.7.6
        item 2's producers in, the labels DO fire. twin_towns(40) driven into
        famine for 480 hours holds 9 `looks_up_to` ties across 4 holders —
        the people who kept picking each other up."""
        stressed, _ = _cached("famine", 480.0, drift=0.09)

        signed = {label: n for label, n in _labels(stressed).items()
                  if label != "familiar"}
        assert signed, "a quarter of catastrophe and nobody is anything"
        assert set(signed) <= set(TIE_LABELS)
        assert all(len(held) <= TIE_CAP for held in stressed["ties"].values())

    def test_the_same_seed_replays_the_same_ties(self):
        """In the register of `test_charter_run.py`'s TestReplay, and for the
        same reason: checkpoint restore and branching depend on a run being
        byte-identical, so a store that reached for `random` or a wall clock
        would break both."""
        one, _ = _twin_towns(480.0, drift=0.09)
        two, _ = _twin_towns(480.0, drift=0.09)

        assert one["ties"] == two["ties"]
        assert one["ties"], "a replay test over an empty store proves nothing"

    def test_a_quiet_window_writes_no_tie_row(self):
        """EVENTS GROW WITH INCIDENT AND NOT WITH TIME (`charter_run`'s
        docstring), and the tie store is held to the same bound: a window in
        which nobody's stance moved and nobody's familiarity crossed anything
        rewrites nothing at all, so a long quiet stretch costs the store
        zero."""
        quiet = _crew(judgments={"ada": {"bo": _stance(warmth=0.7)}})
        first, changes = update_ties(
            None, company={"yard": ["ada", "bo"]},
            judgments=quiet["judgments"],
            served_beside=quiet["served_beside"], at_hours=0.0)
        again, no_changes = update_ties(
            first, company={"yard": ["ada", "bo"]},
            judgments=quiet["judgments"],
            served_beside=quiet["served_beside"], at_hours=4.0)

        assert len(changes) == 1
        assert no_changes == []
        assert again == first

    def test_a_tie_is_never_an_event_and_never_witnessable(self):
        """Nobody witnesses somebody else's tie. It is one head's summary of
        its own numbers, so it mints no event, adds nothing to
        `charter_news.WITNESSABLE`, and cannot travel as a rumour."""
        stressed, events = _cached("famine", 480.0, drift=0.09)

        assert set(TIE_LABELS).isdisjoint(WITNESSABLE)
        assert set(TIE_LABELS).isdisjoint({e["kind"] for e in events})
        assert "tie" not in {e["kind"] for e in events}


class TestTheOnscreenBeat:
    """The one path where the axes actually move during play. A tie that
    waited for the next offscreen window would be a label nobody could state
    in the scene that earned it, which is the whole legibility claim."""

    def test_conduct_in_the_scene_relabels_the_tie_in_the_beat_it_lands(self):
        charter = normalize_charter({
            "key": "watch",
            "bodies": {"guard": {"place": "gate"},
                       "clerk": {"place": "office"}},
        })
        scene = {"rooms": {"gate": {"name": "Gate", "adjacent": []},
                           "office": {"name": "Office", "adjacent": []}},
                 "positions": {"Traveller": "gate", "Guard": "gate"}}
        threats = [{"source_id": f"sp:{n}", "kind": "speech",
                    "actor": "Traveller", "target": "Guard",
                    "exact_quote": "Leave before dusk", "volume": "normal",
                    "visibility": "overt", "conceal_from": [],
                    "speech_acts": [{"kind": "threat",
                                     "content": "Leave before dusk"}],
                    "salience": 0.8} for n in range(3)]

        after, metrics = apply_public_evidence(charter, threats, scene,
                                               turn_id=4)

        assert after["ties"]["guard"]["Traveller"]["tie"] == "afraid_of"
        assert metrics["ties_changed"] == 1
        assert "clerk" not in after["ties"], \
            "the clerk was in another room and came out afraid"

    def test_the_tie_cites_the_evidence_the_stance_already_cited(self):
        """`because` is COPIED off the holder's own judgment reasons: no scan
        of any store, no new read, and nothing that was not already on the
        same surface."""
        charter = _crew(judgments={"ada": {"bo": _stance(warmth=0.7)}})
        ties, _ = update_ties(
            None, company={"yard": ["ada", "bo"]},
            judgments=charter["judgments"],
            served_beside=charter["served_beside"], at_hours=0.0)

        cited = ties["ada"]["bo"]["because"]
        stance_ids = [r["evidence_id"]
                      for r in charter["judgments"]["ada"]["bo"]["reasons"]]
        assert cited and set(cited) <= set(stance_ids)
        assert len(cited) <= 2, "a summary that cites six things is not one"


class TestTheSurfacesAgree:
    """`familiar` is derived at read time and the signed labels are stored,
    which is two code paths for one concept. `tie_of` is the only reader for
    exactly that reason — otherwise one surface shows `close` where another
    shows `familiar` for the same pair."""

    def test_both_surfaces_read_the_same_pair_the_same_way(self):
        charter = _crew(judgments={"ada": {"bo": _stance(warmth=0.7)}})
        charter["ties"], _ = update_ties(
            None, company={"yard": ["ada", "bo"]},
            judgments=charter["judgments"],
            served_beside=charter["served_beside"], at_hours=12.0)

        ledger = scene_ledger(charter, "yard")
        handoff = promotion_handoff("ada", charter)

        edge = {row["body"]: row for row in handoff["acquaintances"]}["bo"]
        assert edge["tie"] == "close"
        assert edge["tie_since_hours"] == 12.0
        assert ledger["presences"]["ada"]["knows_here"]["bo"]["tie"] == "close"
        assert tie_view(charter["ties"], "ada",
                        served_beside=charter["served_beside"])[0] == {
            "other": "bo", "tie": "close", "since_hours": 12.0}

    def test_the_promotion_row_carries_the_same_familiarity_the_tie_reads(self):
        """`TIE_SATURATION` was inline in `charter_promote` as `shared / 200.0`
        and the tie layer needs the same number. Two copies of a tuned
        constant is how they drift."""
        charter = _crew(shared=TIE_SATURATION // 2)

        edge = promotion_handoff("ada", charter)["acquaintances"][0]

        assert edge["familiarity"] == familiarity(
            charter["served_beside"], "ada", "bo") == 0.5


def test_a_promoted_body_keeps_no_ties_and_the_institution_keeps_its_view(
        temp_db):
    """A promoted body's Charter cognition is retired and a tie IS cognition,
    so its own ties go with its judgments and its minds. Ties others hold
    ABOUT it stay: the institution keeps its view of a person who has become a
    character, exactly as their claims about it stay."""
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Charter ties", "", time.time()))
    charter = _crew(judgments={"ada": {"bo": _stance(warmth=0.7)},
                               "bo": {"ada": _stance(warmth=0.7)}})
    charter["ties"], _ = update_ties(
        None, company={"yard": ["ada", "bo"]}, judgments=charter["judgments"],
        served_beside=charter["served_beside"], at_hours=0.0)
    save_registry(cid, {"yard": charter})

    bound = bind_promoted_character(
        cid, {"charter": "yard", "body": "ada"}, char_id=1, name="Ada")

    after = registry_for(cid)["items"]["yard"]["state"]
    assert bound is True
    assert "ada" not in (after.get("ties") or {})
    assert after["ties"]["bo"]["ada"]["tie"] == "close"


def test_the_tie_pass_costs_a_healthy_window_nothing_measurable():
    """The cost rule at `world/charter_run.py`:9-35 applied to this layer. The
    holder gate — a body with neither a judgment nor a tie is skipped BEFORE
    its co-presence is walked — is what keeps this O(bodies) per window in a
    healthy institution, where the judgment network is empty. Asserted as a
    shape rather than a wall clock, because wall clocks are flaky: a run that
    formed no stance visits no pair, so it produces no change at all."""
    company = {"yard": [f"b{i:03d}" for i in range(200)]}
    started = time.perf_counter()
    ties, changes = update_ties(None, company=company, judgments={},
                                served_beside={}, at_hours=0.0)
    elapsed = time.perf_counter() - started

    assert (ties, changes) == ({}, [])
    # 200 bodies in one room is 39,800 directed pairs the gate never reaches.
    assert elapsed < 0.05
