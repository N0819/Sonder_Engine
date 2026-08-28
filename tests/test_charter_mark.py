"""Status as a temporary trait: what a body is now that it was not before.

`docs/guides/RESEARCH.md` §1.7.6 design 4. Comme il Faut keeps permanent
traits and temporary status side by side; this package had needs, felt state,
a service tally and nothing socially temporary at all.

Measured on this working tree, before and after:

  * `big_town(40)`, healthy simulated year, window 4.0, seed 3 -- 3 events,
    0 blame, 0 `heard_blame`. The only mark a working institution produces is
    `posted`: 13 of 40 bodies ever, 0.31% of (body, window) pairs holding it,
    and an EMPTY store at the end of the year.
  * the same fixture with needs seeded -- 804 `aid_given` acts over the year,
    6 bodies ever `aided`, 12.39% mean held. The plan for this design
    predicted `aid_given` fired only under famine; it does not, and `aided` is
    the busiest of the four.
  * `twin_towns(240)` driven into famine for a simulated month -- 48 of 240
    ever `posted`, 2 ever `disgraced`, 0 `accused`. Accusation is an ONSCREEN
    act: `quarrel` is not in `COARSE_PRACTICES`, so an institution nobody is
    looking at produces no accusations at all, in health or in famine.

THE FIREWALL SPLIT IS THE DESIGN'S SPINE, and the two arms of
`test_being_told_to_your_face_is_felt_and_the_ledger_alone_is_not` measure it:
the same register blame, on screen and off, leaves the blamed body at strain
0.163 / load 0.067 with somebody saying it to their face and at strain 0.0 /
load 0.0 without.
"""

from __future__ import annotations

import copy

import pytest

import world.charter_run as charter_run
from world.charter_news import news_keys_in, witness
from world.charter import (
    BODY_MARKS,
    DISGRACE_RELUCTANCE,
    MARKS,
    MARK_HOURS,
    advance_feel,
    advance_marks,
    authored,
    held_marks,
    life_of,
    mark_view,
    normalize_charter,
    normalize_marks,
    scene_ledger,
    seed_needs,
    seed_roster,
    step,
)


def _saw_it_fail(charter, place="yard", upkeep="granary", at=0.0):
    """Everybody standing in `place` holds their own claim that it failed.

    THE ACCUSER'S CHANNEL, and the fixtures need it because since 2026-08-27
    `charter_practice._afford_accuse` decides from the actor's own claims
    rather than from `politics.blame` -- the institution's private register,
    which is a fact no body in a room can perceive. A yard whose granary is
    healthy and whose books blame somebody now produces no accusation at all,
    and that is the firewall rather than a broken fixture. Seeded through
    `charter_news.witness` rather than hand-built so the claim is exactly the
    one a body standing there would have received.
    """
    witness(charter["minds"], charter["bodies"],
            [{"kind": "upkeep_out_of_band", "place": place, "upkeep": upkeep,
              "at_hours": at}], at)
    charter["news_keys"] = sorted(news_keys_in(charter["minds"]))
    return charter


def _yard(*folk, blame=None, active=True):
    """One upkeep, one post, and whoever the caller stands in the yard."""
    charter = normalize_charter({
        "key": "town",
        "upkeeps": {"granary": {"place": "yard", "level": 0.9, "floor": 0.2,
                                "drift_per_hour": 0.001,
                                "service_per_hour": 0.03}},
        "posts": {"keeper": {"place": "yard", "serves": ["granary"]}},
        "bodies": {key: {"place": "yard"} for key in folk},
    })
    charter["roster"] = seed_roster(charter["bodies"])
    charter["needs"] = seed_needs(charter["bodies"])
    charter["active_places"] = ["yard"] if active else []
    if blame:
        charter["politics"] = {"blame": dict(blame)}
    return charter


def _works(hands, posts=3):
    """Interchangeable hands and fewer posts than hands: a bill with slack,
    so the planner's preference is visible in who it reaches for."""
    upkeeps, bill = {}, {}
    for index in range(posts):
        upkeeps[f"line_{index}"] = {
            "place": "yard", "level": 0.9, "floor": 0.3,
            "drift_per_hour": 0.01, "service_per_hour": 0.05}
        bill[f"post_{index}"] = {"place": "yard", "serves": [f"line_{index}"]}
    charter = normalize_charter({
        "key": "works", "upkeeps": upkeeps, "posts": bill,
        "priority": sorted(upkeeps),
        "bodies": {f"hand_{i}": {"place": "yard", "berth": "yard"}
                   for i in range(hands)}})
    charter["roster"] = seed_roster(charter["bodies"])
    return charter


class TestAMarkIsTemporary:
    """The whole claim of the tier. A permanent fact is a trait, a
    completable one is a goal, and this is neither."""

    def test_a_mark_lapses_and_the_store_empties_again(self):
        """The bound `charter_run`'s docstring holds the event log to, applied
        to a per-body store: it grows with incident and never with time. This
        package has now lost that bound in three places by writing a row per
        window, so the lapse is asserted directly rather than assumed from the
        expiry arithmetic."""
        marks, fresh = advance_marks({}, 10.0, aided=[("raul", "ilse")])

        assert fresh == [("raul", "aided", "ilse")]
        assert held_marks(marks, "raul", 10.0 + MARK_HOURS["aided"] - 1.0)

        quiet, still_fresh = advance_marks(
            marks, 10.0 + MARK_HOURS["aided"])

        assert quiet == {}, "a mark nothing renewed is gone"
        assert still_fresh == []

    def test_the_same_mark_twice_is_one_row_with_a_newer_date(self):
        """Bounded by bodies x kinds, not by incidents. Two accusers in two
        windows are one thing that is true of the accused, dated by the last
        of them -- which is what keeps the store's size a function of the
        institution's shape."""
        first, _ = advance_marks({}, 8.0, accused=[("raul", "ilse")])
        second, fresh = advance_marks(first, 12.0, accused=[("raul", "mira")])

        assert list(second["raul"]) == ["accused"]
        assert second["raul"]["accused"] == {"since": 12.0, "by": "mira"}
        assert fresh == [("raul", "accused", "mira")]

    def test_two_accusers_in_one_window_still_leave_one_row(self):
        """`heard` is a dict of SETS, so the winner has to be decided by sort
        order rather than by iteration order or a checkpoint restore lands a
        different past."""
        one, fresh_one = advance_marks(
            {}, 8.0, accused=[("raul", "mira"), ("raul", "ilse")])
        two, fresh_two = advance_marks(
            {}, 8.0, accused=[("raul", "ilse"), ("raul", "mira")])

        assert one == two
        assert fresh_one == fresh_two == [("raul", "accused", "mira")]

    def test_a_body_that_leaves_the_charter_leaves_no_mark_behind(self):
        """The bodies filter runs at `normalize_charter`, which is the head of
        every `step` -- the same enforcement point `experiences` and
        `habit_runs` are capped at, and the reason a filter applied only where
        rows are written is inert."""
        stored = {"raul": {"accused": {"since": 1.0, "by": "ilse"}},
                  "ghost": {"posted": {"since": 1.0}}}

        assert set(normalize_marks(stored, bodies={"raul": {}})) == {"raul"}

    def test_reading_one_bodys_marks_does_not_walk_the_whole_store(self):
        """The planner reads this ONCE PER BODY PER WINDOW
        (`charter_run.step`'s reluctance loop), and `held_marks` used to get
        its answer by normalizing the WHOLE store and then indexing one key --
        so the loop cost bodies x marked-bodies every window, which is exactly
        the quadratic-in-the-crowd class `CO_PRESENCE_WIDTH` exists to
        prevent. Measured 2026-08-27, strictly interleaved in one process
        against a one-row lookup: `big_ship(500)` at 240 h 18.25/18.41 s
        against 15.71/15.63 s, +17% against this package's 5% gate; the loop
        alone microbenched at 1.358 s per window with 1,000 bodies marked, and
        "every body marked" is reachable -- `posted` peaks at 32.5% of
        `big_town(40)` in the institution's first window.

        Asserted as a COUNT rather than as a wall clock, because a timing
        assertion in the suite is flaky by nature and this property is not.
        """
        import world.charter_mark as charter_mark

        store = {f"body_{index}": {"posted": {"since": 0.0}}
                 for index in range(500)}
        visits = []
        original = charter_mark._normalize_row

        def counted(held):
            visits.append(held)
            return original(held)

        charter_mark._normalize_row = counted
        try:
            held = charter_mark.held_marks(store, "body_499", 1.0)
        finally:
            charter_mark._normalize_row = original

        assert held == {"posted": {"since": 0.0}}
        assert len(visits) == 1

    def test_a_charter_saved_before_this_existed_loads_empty(self):
        charter = normalize_charter({"key": "t", "upkeeps": {}, "posts": {},
                                     "bodies": {}})

        assert charter["marks"] == {}


class TestTheScopeSplit:
    """`disgraced` is a register fact and the other three are not, and the
    difference is a channel rather than a policy."""

    def test_the_institution_reads_a_disgrace_and_the_body_never_does(self):
        """`attribute_blame` follows the watch the charter BELIEVED it had
        arranged, so a body can be disgraced for a post it was never at and
        there is no channel by which it would learn. Asserted from both ends:
        absent from the presence slice a scene manager voices an extra from,
        absent from the appraisal, present in the author's diagnostic."""
        charter = _yard("raul", "ilse", active=False)
        charter["marks"] = {"raul": {"disgraced": {"since": 0.0},
                                     "posted": {"since": 0.0}}}
        charter["clock_hours"] = 4.0

        slice_ = scene_ledger(charter, "yard")["presences"]["raul"]["marks"]
        feel = advance_feel(
            {}, charter["bodies"], charter["needs"], {}, charter["posts"],
            charter["upkeeps"], (), 4.0,
            fresh_marks=[("raul", "disgraced", "")])
        author = life_of("raul", charter, [])

        assert [row["mark"] for row in slice_] == ["posted"]
        assert feel == {}, "a register fact reached an interior"
        assert set(author["marks"]) == {"disgraced", "posted"}

    def test_the_scope_filter_is_the_allowlist_and_not_the_caller(self):
        """`charter_news.WITNESSABLE` is an allowlist for the same reason: a
        mark added tomorrow must be register-scoped until somebody argues it
        into the list, because the failure of a denylist is silent."""
        assert BODY_MARKS < set(MARKS)
        assert "disgraced" not in BODY_MARKS
        planted = {"raul": {kind: {"since": 0.0} for kind in MARKS}}

        shown = {row["mark"] for row in mark_view(planted, "raul", 1.0)}

        assert shown == BODY_MARKS

    def test_being_told_to_your_face_is_felt_and_the_ledger_alone_is_not(self):
        """The paired case, and it closes the residual `charter_feel`'s
        docstring named: blame reached nobody and nothing modelled the
        telling.

        SAME REGISTER BLAME AND THE SAME PERCEIVED FAILURE, TWICE. On screen
        the yard opens a quarrel and somebody says it aloud; off screen
        `quarrel` is not in `COARSE_PRACTICES`, no blame lands (the granary
        here is healthy -- what the room holds is a claim, seeded by
        `_saw_it_fail`), so the consequence rule has nothing to fire on and
        nobody ever does. Measured over six windows: 12 accusations and strain
        0.163 / load 0.067 on the first arm, zero accusations and strain 0.0 /
        load 0.0 on the second, from identical books.
        """
        def arm(active):
            charter = _saw_it_fail(_yard(
                "ilse", "raul", "mira", "tomas",
                blame={"raul": 2}, active=active))
            events = []
            for index in range(6):
                charter, produced = step(charter, hours=4.0, seed=5 + index)
                events.extend(produced)
            return charter, events

        told, spoken = arm(True)
        untold, silent = arm(False)

        assert [e for e in spoken if e["kind"] == "accusation"]
        assert "accused" in told["marks"]["raul"]
        assert told["marks"]["raul"]["accused"]["by"] in told["bodies"]

        assert not [e for e in silent if e["kind"] == "accusation"]
        assert untold["heard_blame"] == {}
        assert "accused" not in (untold["marks"].get("raul") or {})
        # The books say the same thing in both arms. Only one of them hurts.
        assert untold["politics"]["blame"]["raul"] == \
            told["politics"]["blame"]["raul"] == 2
        assert told["feel"]["raul"]["stress"]["strain"] > \
            untold["feel"]["raul"]["stress"]["strain"] == 0.0

    def test_an_authored_accusation_leaves_the_same_mark_a_chosen_one_does(
            self):
        """`charter_author` is the §12a author-switch and an authored act must
        leave the record a simulated one leaves. A figure accusing a body is
        the one accusation reachable with nobody on screen."""
        charter = _yard("raul", active=False)
        charter["figures"] = {"ilse": {"key": "ilse", "place": "yard"}}
        charter["clock_hours"] = 10.0

        charter, record = authored(charter, "ilse", "accuse", "raul")

        assert not record.get("refused")
        assert charter["marks"]["raul"]["accused"] == {
            "since": 10.0, "by": "ilse"}

    def test_an_authored_act_leaves_no_mark_on_a_body_charter_gave_away(self):
        """The bound-body arm the test above did not have.

        `charter_run.step` filters all four onset lists by `bindings` ("a
        promoted body's interior has exactly one owner, and Charter scoring a
        person it no longer owns is the thing the promotion purge exists to
        prevent") and `charter_runtime.bind_promoted_character` pops the store
        at binding for the same reason. `charter_author.authored` applied
        neither -- it had `charter["bindings"]` in hand and never read it --
        so the author path was the one writer of this store that did not
        check. Verified by execution before the fix: with raul bound,
        `authored(charter, "ilse", "accuse", "raul")` returned
        `marks = {"raul": {"accused": ...}}`, which then rode
        `normalize_charter` (it filters to live BODIES, not to unbound ones)
        onto `charter_log.scene_ledger`'s presence slice, surviving the
        promotion purge that had already run.
        """
        charter = _yard("raul", active=False)
        charter["figures"] = {"ilse": {"key": "ilse", "place": "yard"}}
        charter["clock_hours"] = 10.0
        charter["bindings"] = {"raul": {"char_id": 7, "name": "raul"}}

        charter, record = authored(charter, "ilse", "accuse", "raul")

        assert not record.get("refused"), "the ACT still lands; the mark does not"
        assert charter["marks"] == {}
        # And the telling itself is unchanged: `heard_blame` is the objective
        # record of who said what to whom, not a scoring bias, and belongs to
        # the institution either way.
        assert charter["heard_blame"]["raul"] == ["ilse"]


class TestTheInstitutionSpendsADisgracedBodyLater:
    """The one reader `disgraced` has, and the invariant
    `charter_politics.spend_reluctance` exists to state: standing makes a body
    EXPENSIVE, never unpostable."""

    @staticmethod
    def _run(reluctance, disgraced, hands, windows=60, monkeypatch=None):
        monkeypatch.setattr(charter_run, "DISGRACE_RELUCTANCE", reluctance)
        charter = _works(hands)
        charter["marks"] = {key: {"disgraced": {"since": 0.0}}
                            for key in disgraced}
        stood, unfilled = {}, 0
        for index in range(windows):
            charter, events = step(charter, hours=4.0, seed=11 + index)
            unfilled += sum(1 for e in events
                            if e["kind"] == "post_unfilled")
            for body in (charter.get("watch") or {}).values():
                stood[body] = stood.get(body, 0) + 1
            # Renew, so the whole run measures one state rather than the
            # fourteen days it takes the mark to lapse.
            for key in disgraced:
                charter["marks"].setdefault(key, {})["disgraced"] = {
                    "since": charter["clock_hours"]}
        return stood, unfilled

    def test_a_disgraced_body_is_spent_later(self, monkeypatch):
        """Nine interchangeable hands and three posts. Measured over 60
        windows: two disgraced hands take 22.2% of the watches with the term
        at zero -- their exact fair share, because the planner rotates on
        `watches_stood` -- and 0% with it live. The institution has slack and
        it uses it."""
        blank, _ = self._run(0.0, ["hand_0", "hand_1"], 9,
                             monkeypatch=monkeypatch)
        live, _ = self._run(DISGRACE_RELUCTANCE, ["hand_0", "hand_1"], 9,
                            monkeypatch=monkeypatch)

        shamed = ("hand_0", "hand_1")
        assert sum(blank.get(key, 0) for key in shamed) > 0
        assert sum(live.get(key, 0) for key in shamed) < \
            sum(blank.get(key, 0) for key in shamed)
        assert sum(live.values()) == sum(blank.values()), \
            "the same number of watches were stood either way"

    def test_and_is_still_spent_when_it_must_be(self, monkeypatch):
        """Three hands, three posts, every one of them in disgrace. A charter
        short of hands still posts them; that is the difference between
        expensive and unpostable, and it is the property that makes this term
        safe to add to the same axis standing already rides."""
        stood, unfilled = self._run(
            DISGRACE_RELUCTANCE, ["hand_0", "hand_1", "hand_2"], 3,
            monkeypatch=monkeypatch)

        assert unfilled == 0
        assert sum(stood.values()) == 60 * 3

    def test_a_disgrace_never_outweighs_being_the_last_qualified_body(self):
        """`criticality` contributes whole numbers to the same sort component,
        so a term at or above 1.0 would let a fortnight-old failure outrank
        being irreplaceable -- the exact defect `criticality`'s docstring
        exists for, arriving by a new road."""
        assert 0.0 < DISGRACE_RELUCTANCE < 1.0

    def test_the_counter_is_monotone_and_the_mark_is_not(self, monkeypatch):
        """`politics.blame` says it happened, forever; the mark says it
        happened recently. Only the mark reaches the bill, which is why a
        charter does not spend a body more grudgingly a decade after."""
        monkeypatch.setattr(charter_run, "DISGRACE_RELUCTANCE",
                            DISGRACE_RELUCTANCE)
        charter = _works(9)
        charter["politics"] = {"blame": {"hand_0": 5}}
        charter["marks"] = {"hand_0": {
            "disgraced": {"since": -MARK_HOURS["disgraced"]}}}

        after, _ = step(charter, hours=4.0, seed=11)

        assert after["politics"]["blame"]["hand_0"] == 5
        assert "disgraced" not in (after["marks"].get("hand_0") or {})


class TestWhatAMarkCostsToCarry:
    def test_a_quiet_institution_carries_nothing(self):
        """The sparseness `charter_log.summarize` treats as the health signal,
        extended to this store. Nothing happened, so nobody is anything."""
        charter = _yard("ilse", "raul", active=False)
        for index in range(4):
            charter, _ = step(charter, hours=4.0, seed=index)
        charter["marks"] = {}

        after, _ = step(charter, hours=4.0, seed=99)

        assert after["marks"] == {}

    def test_a_mark_survives_a_json_round_trip_byte_identically(self):
        """No schema change and no migration: the charter lives whole inside a
        frame-scoped `world` row, so archive, checkpoint, branch clone and
        story delete carry this key for free -- provided the shape does."""
        import json
        charter = _yard("raul", "ilse", active=False)
        charter["marks"] = {"raul": {"accused": {"since": 4.0, "by": "ilse"},
                                     "posted": {"since": 8.0}}}

        once = normalize_charter(charter)["marks"]
        twice = normalize_charter(
            json.loads(json.dumps(normalize_charter(charter))))["marks"]

        assert once == twice == charter["marks"]


@pytest.mark.parametrize("kind", MARKS)
def test_every_mark_has_a_lifetime_and_a_scope(kind):
    """The vocabulary is one table. A kind with no lifetime could never
    expire, and a kind absent from both scope sets would be silently
    unreadable -- both of them fail as a wrong answer rather than an error."""
    assert kind in MARK_HOURS and MARK_HOURS[kind] > 0.0
    assert (kind in BODY_MARKS) != (kind == "disgraced")
