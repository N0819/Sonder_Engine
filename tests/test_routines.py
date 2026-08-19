"""Approach A: routine and residue — the world's default motion.

What is being prevented: the two chair-visible failures the design names
(the changelog — a quiet return narrated as a diff report — and the
clockwork — regularity reading as mechanism), plus the two epistemic sins
this floor could commit if built carelessly: asserting a fixture or an
hour the world's ledgers do not hold, and writing a residue somewhere a
mind could later receive without having been there.
"""

from __future__ import annotations

import json
import time

from world import routines
from world.routines import (
    DAY_SECONDS, RESIDUE_CAP, entropy_facts, occupancy_fact, residue_for,
    routine_band,
)


def _make_chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )


def test_the_social_affordances_stay_a_subset_of_the_vocabulary():
    """`_SOCIAL_AFFORDANCES` is a hand-picked subset of
    `place_purpose.AFFORDANCES` -- which purposes draw people is this
    module's judgment, not a property of the vocabulary, so it is not
    derived. It had no tether at all, and an affordance renamed over there
    would silently take its rooms out of every routine here with nothing
    anywhere noticing."""
    from world.place_purpose import AFFORDANCES

    assert routines._SOCIAL_AFFORDANCES <= set(AFFORDANCES)


class TestARhythmNotASchedule:
    def test_the_band_is_deterministic(self):
        """Seeded, logged, replayable: the same place at the same clock
        must answer the same on a reroll, or the world's motion becomes a
        second history each rerun."""
        for elapsed in (0.0, 3600.0, 40000.0, 90000.0):
            assert routine_band("room:1:tavern", elapsed) == \
                routine_band("room:1:tavern", elapsed)

    def test_two_places_do_not_keep_the_same_hours(self):
        """The clockwork failure: perfect regularity reads as mechanism.
        Phase jitter is per place, so somewhere in a day two places must
        disagree."""
        differs = any(
            routine_band("room:1:tavern", s) != routine_band("room:1:docks", s)
            for s in range(0, int(DAY_SECONDS), 3600))
        assert differs

    def test_hostile_input_is_a_quiet_zero_not_a_crash(self):
        assert routine_band("x", None) == routine_band("x", 0.0)


class TestFactsAssertOnlyWhatLedgersHold:
    def test_occupancy_is_relative_never_an_hour(self):
        """The clock has no day anchor — `display` is prose the Director
        owns — so 'it is midday' would assert what no ledger holds, and
        one story-night's taproom would be narrated busy at the wrong
        hour. A relative claim ('quieter than when last seen') asserts
        only the passage the clock actually measured."""
        fact = None
        for hours in range(1, 4 * 24):
            fact = occupancy_fact("The Brass Tankard tavern", "k",
                                  0.0, hours * 3600.0)
            if fact:
                break
        assert fact is not None
        assert "than when" in fact
        for hour_word in ("morning", "midday", "noon", "evening", "night"):
            assert hour_word not in fact.casefold()

    def test_a_room_without_a_social_routine_makes_no_crowd_claim(self):
        assert all(
            occupancy_fact("The Dusty Vault", "k", 0.0, s * 3600.0) is None
            for s in range(1, 48))

    def test_entropy_is_tag_gated(self):
        """A hearth claim in a room that never afforded warmth would mint
        a fixture in a reader — the 'quiet office' defect one door down."""
        assert any("hearth" in f for f in
                   entropy_facts("The Hearth Room", 5 * 3600.0))
        assert not any("hearth" in f for f in
                       entropy_facts("The Dusty Vault", 5 * 3600.0))
        assert entropy_facts("The Hearth Room", 3600.0) == []

    def test_no_fact_addresses_the_player(self):
        """Facts are Director staging state, not narration: a 'you' inside
        one would be prose aimed at the player from a module with no
        legitimate prose surface."""
        facts = entropy_facts("The Hearth Room tavern", 10 * DAY_SECONDS)
        shift = occupancy_fact("The Brass Tankard tavern", "k",
                               0.0, 30 * 3600.0)
        for fact in facts + ([shift] if shift else []):
            assert "you" not in fact.casefold().split()


class TestResidueIsContactOnly:
    def test_a_room_never_seen_owes_nothing(self, temp_db):
        """First arrival owes nothing to a diff — there is no 'as last
        seen' to differ from. Unvisited PLACES are approach D's ledger;
        blurring the two would deliver invented memories of a first
        visit."""
        cid = _make_chat(temp_db)
        assert residue_for(cid, {"rooms": {}}, "tavern_main",
                           now_seconds=90000.0) is None

    def test_a_round_trip_is_not_an_absence(self, temp_db):
        from core.db import wset

        cid = _make_chat(temp_db)
        wset(cid, "subject_last_seen",
             {"tavern_main": {"turn": 3, "room": "tavern_main",
                              "elapsed_seconds": 1000.0}})
        assert residue_for(cid, {"rooms": {}}, "tavern_main",
                           now_seconds=1200.0) is None

    def test_fired_consequences_outrank_texture_and_the_cap_holds(
            self, temp_db):
        """Layer-1 fact first, plausible motion after, and at most
        RESIDUE_CAP in total — the changelog failure is a return narrated
        as a diff report, and the cap ships with the mechanism rather
        than after it."""
        cid = _make_chat(temp_db)
        from core.db import qi, wset

        wset(cid, "subject_last_seen",
             {"hearth_room": {"turn": 3, "room": "hearth_room",
                              "elapsed_seconds": 1000.0}})
        for i, due in enumerate((2000.0, 3000.0)):
            qi("INSERT INTO scheduled_events(event_id,chat_id,due_at,kind,"
               "location_id,payload,seed,status) VALUES(?,?,?,?,?,?,?,?)",
               (f"event:c{i}", cid, due, "consequence", "hearth_room",
                json.dumps({"what": f"consequence {i} stands"}), "s",
                "fired"))
        scene = {"rooms": {"hearth_room": {
            "name": "The Hearth Room tavern"}}}
        out = residue_for(cid, scene, "hearth_room",
                          now_seconds=1000.0 + 9 * DAY_SECONDS)
        assert out["room"] == "hearth_room"
        assert len(out["facts"]) <= RESIDUE_CAP
        assert out["facts"][0] == "consequence 0 stands"
        assert out["facts"][1] == "consequence 1 stands"

    def test_this_module_writes_nothing(self, temp_db, monkeypatch):
        """A residue that is never stored cannot be delivered to the wrong
        mind later, and a hundred quiet turns cost nothing. The one-door
        rule, held by there being no door: no world-KV write, no INSERT, no
        model call.

        Held by DRIVING the module with every mutating seam booby-trapped,
        rather than by grepping its source for `wset(`, `INSERT INTO` and
        `chat_complete`. Those three spellings are three of many: `qi`,
        `qtx`, `transaction`, an import alias or any helper that wraps one
        satisfies the grep and writes anyway."""
        import core.db as db
        import llm.providers as providers

        cid = _make_chat(temp_db)

        def _refuse(name):
            def _fail(*a, **k):
                raise AssertionError("routines reached %s" % name)
            return _fail

        for seam in ("wset", "qi", "qtx", "transaction", "wset_for_frame"):
            if hasattr(db, seam):
                monkeypatch.setattr(db, seam, _refuse("db.%s" % seam))
        monkeypatch.setattr(providers, "chat_complete",
                            _refuse("providers.chat_complete"))

        routine_band("room:%s:tavern" % cid, 5000.0)
        occupancy_fact("room:%s:tavern" % cid, "The Boar Tavern", 0.0, 90000.0)
        entropy_facts("The Boar Tavern", 9 * DAY_SECONDS)
        residue_for(cid, {"rooms": {"tavern_main": {"name": "Tavern"}}},
                    "tavern_main", now_seconds=90000.0)
