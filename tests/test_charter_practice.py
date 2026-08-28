"""Situations, and the three defects found when the layer got its first tests.

The practices machinery landed with a measurement (5,432 interactions, zero
empty beats) and no tests, and all three defects below survived it — each of
the class this repo keeps re-learning: the output shape was checked, the
consumer was never called.

  * A retold NEWS claim was rebuilt in body-claim shape, losing its kind —
    "news travels for free" was true, but it travelled as a token no
    listener could articulate: `known_news` empty, `can_bring_up` empty.
  * `ask`'s utility enumerated the subjects THE OTHER HEAD HELD — 634 of
    2,413 asks on the twin towns named a subject the asker did not hold,
    knowledge of which reached it through no channel.
  * No affordance checked co-presence at ACT time, so a practice that
    outlived its room let two parted bodies keep trading claims — measured
    directly, a body in one room greeted a body in another and minted a
    full-strength first-hand sighting through the wall.
"""

from __future__ import annotations

from world.charter import (
    IDLE_CLOSE_HOURS, PAIR_TAIL, PRACTICE_CAP, close_stale, enact, hear,
    known_news, offers, opportunities, report_up, witness)
from world.charter_model import EXPERIENCE_CAP
from world.charter_news import news_key
from world.charter_practice import _open
from world.charter_talk import RETOLD_RETENTION


def _body(key, place, available=True):
    return {"key": key, "place": place, "available": available,
            "competence": {}}


def _claim(subject, strength, heard_from=None):
    return {"body": subject, "competence": {}, "believed_available": True,
            "strength": float(strength), "as_of_hours": 0.0,
            "heard_from": heard_from}


class TestRetoldNewsStaysNews:
    def test_a_second_hand_fact_can_still_be_brought_up(self):
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        event = {"kind": "upkeep_out_of_band", "place": "p1",
                 "at_hours": 10.0, "upkeep": "u1", "level": 0.1}
        minds, _ = witness({}, {"a": bodies["a"]}, [event], 10.0)

        assert hear(minds, "b", "a", news_key(event), RETOLD_RETENTION, 1.0)

        held = known_news(minds, "b")
        assert held, "the listener heard the news and cannot articulate it"
        assert held[0]["event_kind"] == "upkeep_out_of_band"
        assert held[0]["about"] == "u1"
        assert held[0]["heard_from"] == "a"

    def test_a_retold_body_claim_is_unchanged_by_the_fix(self):
        minds = {"a": {"c": _claim("c", 1.0)}, "b": {}}

        assert hear(minds, "b", "a", "c", RETOLD_RETENTION, 1.0)

        arrived = minds["b"]["c"]
        assert arrived["strength"] == RETOLD_RETENTION
        assert arrived["heard_from"] == "a"
        assert arrived["believed_available"] is True
        assert "kind" not in arrived


class TestOneDecayerPerStore:
    def test_news_fades_at_exactly_the_news_rate(self):
        """`decay_news`'s docstring always promised body claims to
        `charter_mind`; `decay_minds` was nonetheless decaying everything,
        so news actually faded at the SUM of two rates and
        `NEWS_DECAY_PER_HOUR` was not the news decay rate. An authored rate
        that does not mean what it says fails silently."""
        from world.charter import decay_minds, decay_news
        from world.charter_news import NEWS_DECAY_PER_HOUR

        key = "news:upkeep_out_of_band:u1@1.0000"
        minds = {"a": {key: {"kind": "news", "body": key,
                             "event_kind": "upkeep_out_of_band",
                             "about": "u1", "place": "p1",
                             "happened_at": 1.0, "strength": 1.0,
                             "as_of_hours": 1.0, "heard_from": None}}}

        minds = decay_minds(minds, 10.0)
        minds = decay_news(minds, 10.0, {key})

        assert abs(minds["a"][key]["strength"]
                   - (1.0 - NEWS_DECAY_PER_HOUR * 10.0)) < 1e-9


class TestTheRegisterHoldsPeople:
    def test_news_in_a_watch_standers_head_never_joins_the_roster(self):
        """`report_up` predates `kind` and reported every claim a
        watch-stander held — so every witnessed event joined the register as
        a pseudo-person named `news:…`, and a figure the guard met became an
        entry in the institution's book of its own people. The register is a
        roster of who can be posted; only body claims belong."""
        bodies = {"a": _body("a", "p1")}
        event = {"kind": "upkeep_out_of_band", "place": "p1",
                 "at_hours": 1.0, "upkeep": "u1", "level": 0.1}
        minds, _ = witness({}, bodies, [event], 1.0)
        minds["a"]["b"] = _claim("b", 1.0)
        minds["a"]["fig"] = {"kind": "figure", "body": "fig", "place": "p1",
                             "surface": {}, "strength": 1.0,
                             "as_of_hours": 1.0, "heard_from": None}

        roster = report_up({}, minds, {"post": "a"}, bodies, at_hours=2.0)

        assert set(roster) == {"b"}


class TestTheAskersOwnGap:
    def test_an_ask_names_a_subject_the_asker_holds(self):
        """The asker's thin claim is about s1; the other privately holds s2.
        Asking about s2 would require reading the other's head."""
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        minds = {"a": {"s1": _claim("s1", 0.2), "b": _claim("b", 1.0)},
                 "b": {"s1": _claim("s1", 1.0), "s2": _claim("s2", 1.0),
                       "a": _claim("a", 1.0)}}
        key, entry = _open("converse", "p1", {"a": "a", "b": "b"}, 0.0)

        acts, *_rest = enact(bodies, minds, {}, {key: entry}, {}, {}, 0.0)

        asks = [a for a in acts if a["act"] == "ask" and a["actor"] == "a"]
        assert asks, "the asker had a thin claim and did not ask"
        assert "s1" in asks[0]["line"]
        assert "s2" not in asks[0]["line"]

    def test_an_honest_ask_can_miss_and_a_miss_is_not_an_effect(self):
        """The other holds nothing on the subject: nothing arrives, and the
        beat records nothing. A dead question must not keep a situation
        warm — with misses counted as effects, every open conversation
        stayed open forever and the town measured 0.9 acts per body per
        hour against the 0.147 the layer was tuned at."""
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        minds = {"a": {"s1": _claim("s1", 0.2), "b": _claim("b", 1.0)},
                 "b": {"a": _claim("a", 1.0)}}
        key, entry = _open("converse", "p1", {"a": "a", "b": "b"}, 0.0)

        acts, *_rest = enact(bodies, minds, {}, {key: entry}, {}, {}, 1.0)

        assert not any(a["act"] == "ask" and a["actor"] == "a" for a in acts)
        assert minds["a"]["s1"]["strength"] == 0.2, "an answer from nowhere"
        assert entry["last_effect_at"] == 0.0, "a dead question kept the " \
            "situation warm"


class TestSpeakingDistance:
    def test_no_affordance_fires_across_rooms(self):
        """The situation remembers the pair; the world decides whether they
        are still within speaking distance."""
        bodies = {"a": _body("a", "east"), "b": _body("b", "west")}
        minds = {"a": {"c": _claim("c", 0.9)}, "b": {}}
        key, entry = _open("converse", "east", {"a": "a", "b": "b"}, 0.0)

        acts, *_rest = enact(bodies, minds, {}, {key: entry}, {}, {}, 1.0)

        assert acts == []
        assert minds["b"] == {}, "a first-hand sighting through a wall"

    def test_a_parted_pairs_practice_still_closes(self):
        key, entry = _open("converse", "east", {"a": "a", "b": "b"}, 0.0)

        survivors = close_stale({key: entry}, IDLE_CLOSE_HOURS + 0.1)

        assert survivors == {}


class TestSituationsOpenAndFeed:
    def test_two_strangers_in_a_room_get_a_greeting(self):
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}

        opened = opportunities(bodies, {}, {}, [], {}, 0.0)

        kinds = {entry["kind"] for entry in opened.values()}
        assert "greeting" in kinds

    def test_acting_spawns_the_next_situation(self):
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        minds = {}
        opened = opportunities(bodies, minds, {}, [], {}, 0.0)

        acts, spawned, _closed, _heard, _refused = enact(
            bodies, minds, {}, opened, {}, {}, 0.0)

        assert any(a["act"] == "greet" for a in acts)
        assert any(entry["kind"] == "converse" for _k, entry in spawned)

    def test_offers_enumerates_without_licensing(self):
        """The Versu seam: the action instances handed outward are the same
        set the chooser picks from, and reading them changes nothing."""
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        minds = {"a": {"b": _claim("b", 1.0), "s1": _claim("s1", 0.3)},
                 "b": {"a": _claim("a", 1.0)}}
        key, entry = _open("converse", "p1", {"a": "a", "b": "b"}, 0.0)
        before = {h: dict(c) for h, c in minds.items()}

        rows = offers(bodies, minds, {}, {key: entry}, {}, {}, 0.0)

        assert {r["act"] for r in rows["a"]} >= {"ask", "tell"}
        assert minds == before


class TestVolitionReadsHistory:
    """`_state_of` built `{bodies, figures, minds, needs, regard, blame, at}`,
    so a body deciding what to do could not see anything that had ever passed
    between it and the person in front of it — the one-line gap
    `docs/guides/RESEARCH.md` §1.7.6 names against Comme il Faut, whose whole
    claim to believability is that an exchange is scored against the social
    facts.

    Measured on `tests/charter_worlds.big_ship(crew=40)`, 480 simulated hours
    onscreen, seed 3, against the identical run with the four stores withheld:
    86 distinct `(actor, act, other)` triples moved, and the mean
    `served_beside` count of the body a question was taken to rose from 63.8
    to 71.3. The population did not act more; it acted toward different
    people, and toward the people it had a life with.
    """

    @staticmethod
    def _quarrel(actor, other, at=24.0):
        return _open("quarrel", "p1", {"a": actor, "b": other}, 0.0,
                     about=other)

    @staticmethod
    def _encounters(holder, other, count, valence, at=1.0):
        return [{"id": f"encounter:{holder}:{other}:{n}", "kind": "encounter",
                 "role": "self", "at_hours": float(at), "place": "p1",
                 "other": other, "valence": float(valence)}
                for n in range(count)]

    @staticmethod
    def _utility(rows, act, other):
        return next(r["utility"] for r in rows
                    if r["act"] == act and r["other"] == other)

    @staticmethod
    def _grievance(holder, against, at=1.0):
        """One claim in the holder's OWN head naming somebody answerable.

        The accuser's channel. Since 2026-08-27 `_afford_accuse` gates on this
        rather than on `politics.blame` -- the institution's private register,
        which no body in a room can perceive -- so a fixture that plants only
        a blame count produces no `accuse` offer at all.
        """
        return {f"news:harm_done:{against}@{at}": {
            "kind": "news", "body": f"news:harm_done:{against}@{at}",
            "event_kind": "harm_done", "about": against, "actor": against,
            "toward": holder, "place": "p1", "happened_at": float(at),
            "strength": 1.0, "as_of_hours": float(at), "heard_from": None}}

    def test_a_body_is_slower_to_accuse_somebody_it_has_a_life_with(self):
        """Prom Week's worked example is Simon refusing to carry Cassandra's
        gossip about Naomi: the friendship outweighs the influence, and the
        refusal is legible because it names a specific remembered thing. Here
        the two targets are identical in blame, in regard and in need — the
        only difference between them is two hundred windows stood beside one
        of them, and the accusation must cost more against that one.
        """
        bodies = {"a": _body("a", "p1"), "mate": _body("mate", "p1"),
                  "stranger": _body("stranger", "p1")}
        minds = {"a": {"mate": _claim("mate", 1.0),
                       "stranger": _claim("stranger", 1.0),
                       **self._grievance("a", "mate"),
                       **self._grievance("a", "stranger")}}
        # The BOOKS are identical and are not what makes either accusable --
        # the pair of grievances above is. Passed anyway, so this test would
        # fail the day anything reads the register here again.
        blame = {"mate": 2, "stranger": 2}
        regard = {}
        practices = dict((self._quarrel("a", "mate"),
                          self._quarrel("a", "stranger")))
        served = {"a": {"mate": 200}}
        warm = self._encounters("a", "mate", 4, 0.6)

        rows = offers(bodies, minds, {}, practices, regard, blame, 24.0,
                      experiences={"a": warm}, served_beside=served)["a"]

        assert self._utility(rows, "accuse", "mate") < \
            self._utility(rows, "accuse", "stranger"), (
                "a life together bought the mate nothing")

        # AND THE RELUCTANCE IS BOUGHT BY AFFECT, NOT BY HOURS. Two hundred
        # windows beside somebody you have come to dislike is not a reason to
        # spare them, so the term must fall back to the bare constant rather
        # than invert into an argument for accusing them harder — this
        # affordance may only ever subtract.
        cold = self._encounters("a", "mate", 4, -0.6)
        rows = offers(bodies, minds, {}, practices, regard, blame, 24.0,
                      experiences={"a": cold}, served_beside=served)["a"]

        assert self._utility(rows, "accuse", "mate") == \
            self._utility(rows, "accuse", "stranger")

    def test_a_question_goes_to_the_person_you_have_a_life_with(self):
        """The measured headline, in one pair. Two bodies who could both
        answer, identical in every present-state term the affordance reads;
        the asker takes it to the one it has stood beside."""
        bodies = {"a": _body("a", "p1"), "mate": _body("mate", "p1"),
                  "stranger": _body("stranger", "p1")}
        minds = {"a": {"s1": _claim("s1", 0.2), "mate": _claim("mate", 1.0),
                       "stranger": _claim("stranger", 1.0)}}
        practices = dict((_open("converse", "p1", {"a": "a", "b": "mate"}, 0.0),
                          _open("converse", "p1",
                                {"a": "a", "b": "stranger"}, 0.0)))

        rows = offers(bodies, minds, {}, practices, {}, {}, 4.0,
                      served_beside={"a": {"mate": 250}})["a"]

        assert self._utility(rows, "ask", "mate") > \
            self._utility(rows, "ask", "stranger")

    def test_a_stranger_is_greeted_at_exactly_the_old_constant(self):
        """The subtraction guard. Where there is no history the new term
        contributes NOTHING, so every constant in the affordance table still
        means exactly what it meant before this existed. A body with no rows,
        no tally and no stance greets at 0.9, to the digit."""
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        practices = dict([_open("greeting", "p1", {"a": "a", "b": "b"}, 0.0)])

        rows = offers(bodies, {}, {}, practices, {}, {}, 0.0,
                      experiences={}, served_beside={}, judgments={},
                      commitments={})["a"]

        assert self._utility(rows, "greet", "b") == 0.9

    def test_a_re_meeting_is_not_a_meeting(self):
        """`charter_mind.decay_minds` takes claims away and `experiences`
        keeps rows forever, so the greeting affordance reopens on a pair who
        have met before — and the actor still holds its own record of how the
        first time went. That asymmetry between the two stores is the whole
        reason this case exists."""
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        practices = dict([_open("greeting", "p1", {"a": "a", "b": "b"}, 0.0)])

        def greeting(valence):
            rows = offers(bodies, {}, {}, practices, {}, {}, 40.0,
                          experiences={"a": self._encounters(
                              "a", "b", 3, valence)})["a"]
            return self._utility(rows, "greet", "b")

        assert greeting(0.8) > 0.9, "a welcome re-meeting reads as a stranger"
        assert greeting(-0.8) < 0.9, "a sour one too"

    def test_a_body_never_reads_the_other_heads_record(self):
        """The firewall test, one tier below
        `tests/test_charter_promote.py::TestWhatMayNotCross`. Symmetric data
        is not shared data: `served_beside[a][b]` equals `served_beside[b][a]`
        because both are records of the same fact held separately, and that
        makes reaching for the other side look harmless. It is not — how an
        occasion LANDED on the other body, what the other body concluded, and
        what the other body needs are its own, and reading them to decide your
        own action is a leak however useful.

        Two states differing ONLY in the other party's four stores, at
        extremes, must produce byte-identical utility rows for the actor.
        """
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        minds = {"a": {"s1": _claim("s1", 0.2), "b": _claim("b", 1.0)},
                 "b": {"a": _claim("a", 1.0)}}
        practices = dict((_open("converse", "p1", {"a": "a", "b": "b"}, 0.0),
                          self._quarrel("a", "b")))
        mine = {"a": self._encounters("a", "b", 2, 0.1)}

        bare = offers(bodies, minds, {}, practices, {}, {"b": 1}, 24.0,
                      experiences=dict(mine),
                      served_beside={"a": {"b": 3}}, judgments={},
                      commitments={})

        loud = offers(
            bodies, minds, {}, practices, {}, {"b": 1}, 24.0,
            experiences=dict(mine, b=self._encounters("b", "a", 250, -1.0)),
            served_beside={"a": {"b": 3}, "b": {"a": 999_999}},
            judgments={"b": {"a": {"trust": -1.0, "warmth": -1.0,
                                   "fear": 1.0, "respect": -1.0,
                                   "suspicion": 1.0}}},
            commitments={"c1": {"id": "c1", "state": "open", "promisor": "b",
                                "beneficiary": "third",
                                "recognized_by": ["b"]}})

        assert bare["a"] == loud["a"]

    def test_the_books_alone_are_not_a_reason_to_round_on_anybody(self):
        """`politics.blame` is the institution's PRIVATE register.

        `charter_news.WITNESSABLE`'s allowlist comment states the rule: "a
        conclusion the institution reached in its own books, and a body in the
        room has no way to perceive it. Getting this list wrong is a firewall
        leak." Until 2026-08-27 `_afford_accuse` gated on that counter and
        sized its utility on the counter's MAGNITUDE, and
        `charter_runtime.presence_view` deep-copies exactly those utility rows
        into `action_instances` for a scene-manager model -- so a body's
        conduct, and a monotone reading of a register it cannot see, went to a
        model. The read was unreachable until the same day gave `quarrel` two
        live openers, which is what turned a residual into a defect.

        Three arms: a body with the books against it and nothing perceived
        offers no accusation at all; a grievance of its own offers one; and
        moving the counter from 1 to 40 moves no number anywhere.
        """
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        practices = dict([self._quarrel("a", "b")])

        books_only = offers(bodies, {}, {}, practices, {}, {"b": 3}, 24.0)
        with_reason = offers(bodies, {"a": self._grievance("a", "b")}, {},
                             practices, {}, {}, 24.0)
        louder_books = offers(bodies, {"a": self._grievance("a", "b")}, {},
                              practices, {}, {"b": 40}, 24.0)

        assert not [r for r in books_only.get("a", ())
                    if r["act"] == "accuse"]
        assert [r["act"] for r in with_reason["a"]] == ["accuse"]
        assert with_reason["a"] == louder_books["a"]

    def test_a_grievance_lapses_where_the_register_never_does(self):
        """The counter is MONOTONE -- `charter_mark`'s docstring: "the
        institution's ledger and it does not forget" -- so a body deciding
        from it would round on somebody a decade after the fact. A claim is
        deleted by `charter_news.decay_news` once it fades below
        `charter_mind.PERSONAL_FLOOR`, so the reason to accuse expires with
        the memory of the thing. Driven through the decayer rather than by
        deleting the row, because the property belongs to the store."""
        from world.charter import decay_news

        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        practices = dict([self._quarrel("a", "b")])
        minds = {"a": self._grievance("a", "b")}

        assert offers(bodies, minds, {}, practices, {}, {}, 24.0)["a"]

        decay_news(minds, 1_000.0, set(minds["a"]))

        assert not offers(bodies, minds, {}, practices, {}, {},
                          1_024.0).get("a")

    def test_recognising_a_promise_is_not_being_party_to_one(self):
        """`charter_commitment`'s docstring: each record "names who inside
        that Charter has actually received evidence of it." Evidence licenses
        a reader to KNOW a promise exists; it does not make the promise
        theirs. An open commitment between two other bodies, which the actor
        witnessed and is recorded as recognising, must move nothing about how
        the actor feels toward either of them."""
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        practices = dict([self._quarrel("a", "b")])
        theirs = {"c1": {"id": "c1", "state": "open", "promisor": "b",
                         "beneficiary": "third", "recognized_by": ["a", "b"]}}

        # Reconcile is only offered below full regard; NEUTRAL_REGARD is the
        # ceiling, so a quarrel needs a body that has actually lost some.
        cooled = {"a->b": 0.7}
        without = offers(bodies, {}, {}, practices, cooled, {}, 24.0)["a"]
        with_it = offers(bodies, {}, {}, practices, cooled, {}, 24.0,
                         commitments=theirs)["a"]

        assert self._utility(without, "reconcile", "b") == 0.4
        assert with_it == without

    def test_an_unsettled_matter_is_a_reason_to_make_peace(self):
        """The other half of the gate: the same record, now naming the actor
        as a party. Being at odds with somebody you have business with is its
        own argument for ending the quarrel, and the actor is licensed for
        this one by being in it."""
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1")}
        practices = dict([self._quarrel("a", "b")])
        ours = {"c1": {"id": "c1", "state": "open", "promisor": "b",
                       "beneficiary": "a", "recognized_by": ["a", "b"]}}

        rows = offers(bodies, {}, {}, practices, {"a->b": 0.7}, {}, 24.0,
                      commitments=ours)["a"]

        assert self._utility(rows, "reconcile", "b") > 0.4

    def test_a_debt_is_a_reason_to_be_the_one_who_steps_forward(self):
        """`tend` may only ever ADD: a body does not walk past somebody on
        the floor because it dislikes them, so affect is not read here at
        all. What history contributes is the one thing that genuinely changes
        who steps forward — an open commitment this body itself undertook."""
        bodies = {"a": _body("a", "p1"), "b": _body("b", "p1", available=False)}
        needs = {"b": {"rest": {"key": "rest", "level": 0.1, "floor": 0.4}}}
        practices = dict([_open("tending", "p1", {"a": "a", "b": "b"}, 0.0,
                                about="b")])
        owed = {"c1": {"id": "c1", "state": "open", "promisor": "a",
                       "beneficiary": "b", "recognized_by": ["a", "b"]}}

        plain = offers(bodies, {}, needs, practices, {}, {}, 4.0)["a"]
        indebted = offers(bodies, {}, needs, practices, {}, {}, 4.0,
                          commitments=owed)["a"]

        assert self._utility(indebted, "tend", "b") > \
            self._utility(plain, "tend", "b")

    def test_the_digest_is_one_pass_and_does_not_grow_with_a_long_life(self):
        """The two things a later refactor will quietly drop: the memo and the
        tail bound. `EXPERIENCE_CAP` is 4,000 and a body may hold four
        practices at once, so an unmemoised per-offer scan of a long life
        would visit rows in the tens of thousands. Bounded and memoised, a
        holder's rows are visited exactly once per window and never more than
        `PAIR_TAIL` of them — the same shape `charter_news.decay_news`'s
        `keys` index uses.
        """
        from world import charter_practice as practice_module

        partners = ["p%d" % n for n in range(PRACTICE_CAP)]
        bodies = {"a": _body("a", "p1")}
        bodies.update({k: _body(k, "p1") for k in partners})
        minds = {"a": {"s1": _claim("s1", 0.2)}}
        minds["a"].update({k: _claim(k, 1.0) for k in partners})
        practices = dict(
            _open("converse", "p1", {"a": "a", "b": partner}, 0.0)
            for partner in partners)
        rows = [{"id": "encounter:a:%s:%d" % (partners[n % len(partners)], n),
                 "kind": "encounter", "role": "self", "at_hours": float(n),
                 "place": "p1", "other": partners[n % len(partners)]}
                for n in range(EXPERIENCE_CAP)]

        visits = []
        original = practice_module._counterpart

        def counted(row, holder):
            visits.append(holder)
            return original(row, holder)

        practice_module._counterpart = counted
        try:
            offers(bodies, minds, {}, practices, {}, {}, 4000.0,
                   experiences={"a": rows})
        finally:
            practice_module._counterpart = original

        assert len(visits) <= PAIR_TAIL, (
            "%d row visits over a %d-row life: the tail bound or the memo is "
            "gone" % (len(visits), EXPERIENCE_CAP))
        assert visits, "the digest read nothing at all"
