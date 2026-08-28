"""Promotion: the selected past, and the firewall on what may not cross.

`docs/UNBUILT.md` §2.20 in both directions at once. A promoted character
should not begin with an empty episodic self — that is the gap — and it
should not begin with four hundred hours of identical watches either,
because a thick past "does not read as depth; it reads as haunting." The
selection rule under test: a memory is minted only from what changed a
tracked ledger, the routine is remembered only as its aggregate, and the
whole list is flat in quiet time.

And the leak §12a names as the seam's exposure: a body crosses from the
coarse witness to `agents/perception.py`'s strict instrument HERE. Anything
in the payload that coarse witnessing could not have given it — the
institution's register, blame nobody said aloud, another head's interior —
becomes a real mind's illegitimate knowledge, so each of those is an
explicit test rather than an intention.
"""

from __future__ import annotations

import time

from mind.memory import MEMORY_KINDS, MEMORY_PROVENANCE

from world.charter import (
    REMEMBERED_CAP, normalize_charter, promotion_handoff, remembered,
    seed_needs, seed_roster, run)

from charter_worlds import twin_towns


def _guard_charter(watches=100):
    """A body with a long quiet service record, some news, an acquaintance,
    and blame in the books it was never told about."""
    charter = normalize_charter({
        "key": "gatehouse",
        "posts": {"the_gate": {"place": "arch", "serves": []}},
        "bodies": {
            "guard": {"competence": {}, "available": True, "place": "arch"},
            "hana": {"competence": {}, "available": True, "place": "arch"},
        },
    })
    charter["stood"] = {"guard": {"the_gate": int(watches)}}
    charter["minds"] = {"guard": {
        "hana": {"body": "hana", "competence": {}, "believed_available": True,
                 "strength": 0.9, "as_of_hours": 0.0, "heard_from": None},
        "news:upkeep_out_of_band:well@40.0000": {
            "kind": "news", "body": "news:upkeep_out_of_band:well@40.0000",
            "event_kind": "upkeep_out_of_band", "about": "well",
            "place": "arch", "happened_at": 40.0, "strength": 0.8,
            "as_of_hours": 40.0, "heard_from": None},
    }}
    charter["politics"] = {"blame": {"guard": 3}, "regard": {}, "standing": {}}
    return charter


class TestSelectionNotTranscription:
    def test_four_hundred_watches_are_one_sentence(self):
        few = remembered(_guard_charter(watches=4), "guard")
        many = remembered(_guard_charter(watches=400), "guard")

        assert len(few) == len(many), "quiet time bought more memories"
        service_few = [m for m in few if m["kind"] == "semantic"]
        service_many = [m for m in many if m["kind"] == "semantic"]
        assert len(service_few) == len(service_many) == 1
        assert "400" in service_many[0]["content"]

    def test_quiet_hours_add_nothing(self):
        """The whole cost model, applied to memory: a stretch in which
        nothing branched converts to nothing at promotion.

        Everything EXCEPT first meetings, which are keyed to people rather
        than to hours -- see the acquaintance test below for the bound that
        replaces this one for that kind.
        """
        charter = normalize_charter(twin_towns(40))
        charter["roster"] = seed_roster(charter["bodies"])
        charter["needs"] = seed_needs(charter["bodies"])
        key = sorted(charter["bodies"])[0]

        short, events_a = run(charter, hours=48.0, window=4.0)
        long, events_b = run(charter, hours=336.0, window=4.0)

        # THE KINDS STILL HELD TO IT. `charter_run`'s docstring was amended on
        # 2026-08-27: events grow with incident and not with time, and
        # autobiographical rows are deliberately held to a weaker bound. An
        # encounter is drawn from ordinary shared time and a `social` row from
        # an ordinary exchange, so both are time-bearing ON PURPOSE -- that is
        # the whole of what made a simulated year worth more than a month.
        # Everything else here still converts a quiet stretch to nothing.
        TIME_BEARING = {"acquaintance", "encounter", "social"}

        def timed(memories):
            return [m for m in memories
                    if m.get("experience_kind") not in TIME_BEARING]

        a = timed(remembered(short, key, events=events_a))
        b = timed(remembered(long, key, events=events_b))
        assert len(b) <= len(a) or \
            {m["event_key"] for m in b} == {m["event_key"] for m in a}, \
            "time alone grew the past"

    def test_acquaintance_grows_with_who_is_met_and_not_with_time(self):
        """Meeting somebody for the first time IS an incident, so it may add a
        row -- but only once per person, and the belief store cannot be the
        judge of that on its own because it DECAYS. Left appending on every
        absence-from-`known_before`, a quiet 40-body town wrote 8 acquaintance
        rows in 48 hours, 94 in two months and 1134 in two years: twenty-eight
        rows per person known, growing with time exactly as `charter_run`'s
        docstring forbids. Folding on the stable per-pair id is what keeps it
        keyed to the shape of the institution, and the volume rides on
        `repetitions` instead of on new rows.

        TWO MONTHS, WATCHED AT BOTH ENDS, rather than the two years this once
        simulated. The horizon was never the evidence: the same trajectory
        observed twice says outright what one long run could only imply, and
        a second month that adds no row IS "grows with incident and not with
        time". Measured 2026-08-28 on the pre-fold behaviour, which fails
        three of these four assertions: rows 38 -> 70 where the fold holds
        18 -> 18, and `repetitions` stays 1 forever because nothing ever
        folds. The old spelling cost 584.8s of a 643s suite -- a serial floor
        no worker count could go under -- and bought a weaker claim, since
        `len(met) < population` does not trip until two months anyway.
        """
        charter = normalize_charter(twin_towns(40))
        charter["roster"] = seed_roster(charter["bodies"])
        charter["needs"] = seed_needs(charter["bodies"])
        key = sorted(charter["bodies"])[0]
        population = len(charter["bodies"])

        def met(state):
            return [row for row in state["experiences"].get(key) or []
                    if row["kind"] == "acquaintance"]

        def deepest(rows):
            return max((int(row.get("repetitions") or 1) for row in rows),
                       default=0)

        month, _ = run(charter, hours=720.0, window=4.0)
        early = met(month)
        second, _ = run(month, hours=720.0, window=4.0)
        late = met(second)

        assert early, "a month alone in a town of forty"
        assert len(late) < population, (
            f"one row per person known, at most: {len(late)} of {population}")
        assert len(late) <= len(early) + 2, (
            f"a second month of the same forty people added "
            f"{len(late) - len(early)} rows")
        assert deepest(late) > deepest(early), (
            "re-meeting has to deepen the row rather than mint another")

    def test_the_cap_is_a_budget(self):
        charter = _guard_charter()
        held = charter["minds"]["guard"]
        for index in range(30):
            held[f"news:body_unable:n{index:02d}@{index}.0000"] = {
                "kind": "news", "body": f"news:body_unable:n{index:02d}"
                                        f"@{index}.0000",
                "event_kind": "body_unable", "about": f"n{index:02d}",
                "place": "arch", "happened_at": float(index),
                "strength": 0.9, "as_of_hours": float(index),
                "heard_from": None}

        # NO CEILING as of 2026-08-27 (owner's call): promotion fires once and
        # the character keeps the result for the whole story, so the number was
        # protecting nothing downstream. What still bounds the inheritance is
        # what the body actually lived -- thirty planted news claims produce
        # thirty memories and not one more, and a quiet life still promotes
        # with two or three.
        assert REMEMBERED_CAP is None
        minted = remembered(charter, "guard")
        assert len(minted) >= 30, "every planted claim crosses"
        assert len(minted) == len({m["event_key"] for m in minted})
        assert len(remembered(_guard_charter(), "guard")) < 10, (
            "a quiet life is still a quiet life")


class TestWhatMayNotCross:
    def test_blame_nobody_said_aloud_does_not_cross(self):
        """The books blame the guard three times; nobody has told them. The
        promoted mind arrives innocent of it — `heard_blame` is the channel,
        and there is no other."""
        memories = remembered(_guard_charter(), "guard")

        assert not any("fault" in m["content"] for m in memories)

        charter = _guard_charter()
        charter["heard_blame"] = {"guard": ["hana"]}
        memories = remembered(charter, "guard")
        accused = [m for m in memories if "fault" in m["content"]]
        assert accused and accused[0]["provenance"] == "told"
        assert accused[0]["entities"] == ["hana"]

    def test_register_facts_never_become_memories(self):
        """`post_unfilled` and `post_believed_filled` name bodies too, and
        both are conclusions in the institution's books that no one in a
        room could perceive."""
        events = [
            {"kind": "post_believed_filled", "at_hours": 8.0, "place": "arch",
             "post": "the_gate", "body": "guard", "reason": "absent"},
            {"kind": "post_unfilled", "at_hours": 12.0, "place": "arch",
             "post": "the_gate", "reason": "no_competence"},
            {"kind": "body_unable", "at_hours": 16.0, "place": "arch",
             "body": "guard", "worst": 0.1},
        ]

        memories = remembered(_guard_charter(), "guard", events=events)

        keys = [m["event_key"] for m in memories]
        assert any(k.startswith("body_unable:guard") for k in keys)
        assert not any("post_" in k for k in keys)

    def test_the_register_itself_is_absent(self):
        """The roster is the charter's belief about the guard, not the
        guard's own knowledge; no memory may quote it."""
        charter = _guard_charter()
        charter["roster"] = {"guard": {
            "body": "guard", "competence": {"secret": 3},
            "believed_available": False, "strength": 1.0,
            "as_of_hours": 0.0}}

        memories = remembered(charter, "guard")

        assert not any("secret" in str(m) for m in memories)

    def test_another_heads_interior_is_absent(self):
        charter = _guard_charter()
        charter["minds"]["hana"] = {"private": {
            "body": "private", "competence": {}, "believed_available": True,
            "strength": 1.0, "as_of_hours": 0.0, "heard_from": None}}

        memories = remembered(charter, "guard")

        assert not any("private" in str(m) for m in memories)

    def test_forgotten_news_stays_forgotten(self):
        """The world never forgets; minds do. Promotion reads the mind, so
        news this head let decay is not resurrected by the paperwork of
        becoming a character."""
        charter = _guard_charter()
        del charter["minds"]["guard"]["news:upkeep_out_of_band:well@40.0000"]
        events = [{"kind": "upkeep_out_of_band", "at_hours": 40.0,
                   "place": "arch", "upkeep": "well", "level": 0.1}]

        memories = remembered(charter, "guard", events=events)

        assert not any("well" in m["content"] for m in memories)


class TestTheReadersVocabulary:
    def test_every_row_speaks_prepare_memory(self):
        """Pinned against the REAL constants, because a docstring promising
        a payload shape has already been wrong once in this package."""
        charter = _guard_charter()
        charter["heard_blame"] = {"guard": ["hana"]}
        memories = remembered(charter, "guard", events=[
            {"kind": "body_unable", "at_hours": 16.0, "place": "arch",
             "body": "guard", "worst": 0.1}])

        assert memories
        for memory in memories:
            assert memory["kind"] in MEMORY_KINDS
            assert memory["provenance"] in MEMORY_PROVENANCE
            assert 0.0 <= memory["salience"] <= 1.0
            assert 0.0 <= memory["confidence"] <= 1.0
            assert memory["content"]
            assert memory["event_key"]

    def test_hearsay_keeps_its_provenance(self):
        charter = _guard_charter()
        charter["minds"]["guard"]["news:upkeep_out_of_band:well@40.0000"][
            "heard_from"] = "hana"

        memories = remembered(charter, "guard")

        heard = [m for m in memories if m["provenance"] == "heard"]
        assert heard and "hana" in heard[0]["entities"]
        assert heard[0]["confidence"] < 1.0

    def test_the_handoff_carries_both_halves(self):
        payload = promotion_handoff("guard", _guard_charter())

        for field in ("hedonic", "stress", "body_state", "interoception",
                      "stress_profile", "stood", "memories"):
            assert field in payload


class TestAcquaintanceIsAnEdge:
    """`remembered` renders acquaintance as prose, and prose is not an edge.
    `mind.get_relationships` is the only structure the character pipeline
    consults for trust, warmth, fear, respect and suspicion, and the sole
    writer into it at promotion was gated on `social_judgments` -- which
    measured ZERO holders across all four charters of a real story, so the
    branch never ran. A person who stood beside the same colleagues for 720
    hours arrived a stranger to every one of them.
    """

    def test_a_body_hands_over_the_people_it_knows(self):
        charter = _guard_charter()
        charter["served_beside"] = {"guard": {"hana": 100}}

        handoff = promotion_handoff("guard", charter)

        edges = {row["body"]: row for row in handoff["acquaintances"]}
        assert "hana" in edges, "stood beside them and knows them"
        assert edges["hana"]["firsthand"] is True
        assert 0.0 < edges["hana"]["familiarity"] <= 1.0

    def test_familiarity_follows_time_served_beside_them(self):
        near, far = _guard_charter(), _guard_charter()
        near["served_beside"] = {"guard": {"hana": 200}}
        far["served_beside"] = {"guard": {"hana": 2}}

        a = promotion_handoff("guard", near)["acquaintances"][0]
        b = promotion_handoff("guard", far)["acquaintances"][0]

        assert a["familiarity"] > b["familiarity"]

    def test_news_is_not_a_person(self):
        """`minds` holds claims about EVENTS beside claims about people, and
        an edge to a well that failed is not a relationship."""
        handoff = promotion_handoff("guard", _guard_charter())

        assert all(not row["body"].startswith("news:")
                   for row in handoff["acquaintances"])

    def test_the_edge_says_nothing_about_how_they_hold_back(self):
        """The firewall on this seam: an edge is built from this body's own
        claim, its own regard and its own co-presence. Nothing is read out of
        the other head, so the other's regard cannot change what crosses."""
        mutual = _guard_charter()
        mutual["served_beside"] = {"guard": {"hana": 50}}
        mutual["politics"] = dict(mutual["politics"],
                                  regard={"hana": {"guard": 0.1}})

        edge = promotion_handoff("guard", mutual)["acquaintances"][0]

        assert edge["regard"] == 1.0, "hana's low opinion is hana's, not the guard's"

    def test_a_tie_says_nothing_about_how_they_hold_back(self):
        """The same claim for the discrete label, which is the newest thing
        to cross this seam and exactly the kind of small addition that widens
        a payload without anyone noticing. `tie` is derived from the guard's
        OWN stance, OWN regard and OWN co-presence; hana holding the guard
        `close` is hana's, and it must not appear on the guard's row in any
        shape -- not as the label, not as a reciprocity flag, not as a
        `since` reading off her row."""
        mutual = _guard_charter()
        mutual["served_beside"] = {"guard": {"hana": 100},
                                   "hana": {"guard": 100}}
        mutual["judgments"] = {"hana": {"guard": {
            "trust": 1.0, "warmth": 1.0, "fear": 0.0, "respect": 1.0,
            "suspicion": 0.0, "reasons": [], "seen": []}}}
        mutual["ties"] = {"hana": {"guard": {
            "tie": "close", "since_hours": 12.0, "because": []}}}
        mutual = normalize_charter(mutual)

        edge = promotion_handoff("guard", mutual)["acquaintances"][0]

        assert mutual["ties"]["hana"]["guard"]["tie"] == "close", \
            "the fixture has to actually hold the tie for this to prove anything"
        assert edge["tie"] == "familiar", \
            "the guard read a bond out of hana's head"
        assert edge["tie_since_hours"] == 0.0
        assert "mutual" not in edge and "held_by" not in edge


def test_a_promoted_body_carries_no_charter_marks(temp_db):
    """A promoted body's cognition belongs to the registered character, and a
    temporary institutional status is cognition -- it scores what Charter
    would do with a person Charter no longer owns. Beside the minds/needs/feel
    purge and for the same reason.

    Marks are also deliberately absent from `promotion_handoff`: the character
    tier has no reader for a Charter-window scoring bias, and a field nothing
    reads is the dead weight this design exists to avoid.
    """
    from world.charter_runtime import (
        bind_promoted_character, registry_for, save_registry)

    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Charter marks", "", time.time()))
    charter = _guard_charter()
    charter["marks"] = {
        "guard": {"posted": {"since": 4.0},
                  "accused": {"since": 8.0, "by": "hana"}},
        "hana": {"posted": {"since": 4.0}}}
    save_registry(cid, {"gatehouse": charter})

    bound = bind_promoted_character(
        cid, {"charter": "gatehouse", "body": "guard"}, char_id=1,
        name="The Guard")

    after = registry_for(cid)["items"]["gatehouse"]["state"]
    assert bound is True
    assert "guard" not in (after.get("marks") or {})
    assert "hana" in after["marks"], "the institution keeps its other people"
    assert "marks" not in promotion_handoff("hana", charter)
