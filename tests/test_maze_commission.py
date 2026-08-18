"""The courier's floor and his re-issued work: drive + commission re-arm.

Two failures from the same live arm (A11), both of the shape "the world got
better and the character did not":

* The sheet authored rich traits, values, and goals and NO psychology.drive,
  so effective_drive() served empty strings -- his own reasoning read it back
  verbatim. Every motivation was therefore a GOAL, and goals are built to be
  completable and abandonable: when the shrine intention decayed after 150
  barren beats (against a world bug, not a world truth), nothing was
  underneath it. He walked sixteen optimal rooms to the shrine's threshold,
  correctly read its "destination" verdict, and turned away.

* The interlude between runs narrated the keepers re-issuing his commission
  ("set you at the threshold to run it again") but never re-issued it in
  STATE, so each run inherited the previous run's spent goal ledger.

These tests pin the fixes for both. The re-arm machinery is deliberately
harness-side: in live play a character PERCEIVES a re-issued job inside a
pipeline beat and their own agent emits an `add` op (affect.apply_intent_ops
deliberately skips satisfied/abandoned rows in its dedupe, so a closed goal
never blocks the same text forming a new one). The gap exists only for world
events outside pipeline beats -- exactly what the interlude is.
"""
from __future__ import annotations

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tools.maze_experiment as M


def _commission_texts():
    return [str(g.get("goal") or "").strip()
            for g in M.character_sheet("Vesk")["initial_state"]["goals"]]


class TestTheSheetHasAFloor:
    """A character whose every motivation is a goal stops wanting things the
    beat his goals decay. The drive is the floor goals decay onto."""

    def test_the_sheet_authors_a_nonempty_drive(self):
        from story.character_schema import effective_drive
        sheet = M.character_sheet("Vesk")
        drive = effective_drive(sheet.get("psychology") or {}, {})
        assert drive["essence"].strip(), (
            "an empty drive is invisible until the goals decay -- and then "
            "the character simply stops wanting things (A11, run 5: shrine "
            "abandoned, best-time blocked, keep-moving dormant, and a "
            "courier at the shrine's threshold turned away)")
        assert drive["expression"].strip() and drive["taboo"].strip()

    def test_the_drive_expression_says_he_runs(self):
        """A11 read the value 'never breaking stride' as an argument AGAINST
        sprinting (stride as steady pace, a sprint as the burst that breaks
        it): 26 beats with a multi-room run on offer, zero taken. The drive
        outranks intentions in appraisal weight and is the first-named
        source of wants, so its expression is where the running identity
        must live."""
        sheet = M.character_sheet("Vesk")
        assert "run" in sheet["psychology"]["drive"]["expression"].lower()

    def test_values_are_ordered_trade_offs(self):
        """A flat value list operates as a constraint set: nothing in it can
        be traded, so nothing in it can ever legibly lose. Its one
        prohibition, 'never breaking stride', was cited 249 times in 158
        beats (A11) and inverted into an argument AGAINST running, because a
        prohibition names no counterweight inside itself. Each value now
        names what it beats, so which one gives way under pressure is
        authored rather than left to the model's reading of an idiom -- and
        motivated violation (thoroughness losing when speed is at stake)
        becomes deterministic and readable rather than variance."""
        values = [str(v.get("name") or "").lower()
                  for v in M.character_sheet("Vesk")["psychology"]["values"]]
        assert values, "the courier must have values"
        for v in values:
            assert " over " in v, (
                f"value {v!r} names no trade-off: a value that cannot lose "
                "is a constraint, not a value")
        assert "never" not in " ".join(values), (
            "a prohibition has no counterweight inside it")

    def test_the_shrine_stays_a_goal_not_a_drive(self):
        """A drive that can be SATISFIED stops being a drive -- he would be
        hollow the moment he touched the shrine. Drives are pressure, not
        destinations; the shrine belongs to the episodic commission."""
        sheet = M.character_sheet("Vesk")
        drive_text = " ".join(
            sheet["psychology"]["drive"].values()).lower()
        assert "shrine" not in drive_text
        assert any("shrine" in t.lower() for t in _commission_texts())


class TestRearmCommission:
    """The keepers giving him his work back, as state and not just prose."""

    def _state_with(self, intentions):
        return {"interior": {"intentions": intentions}}

    def test_an_abandoned_commission_is_reissued_not_resurrected(self):
        """Abandonment is a historical fact about the character and stays on
        the record; the keepers re-issuing the job mints a NEW intention --
        the same path apply_intent_ops takes, whose dedupe deliberately
        skips closed rows. Resurrecting the abandoned row would rewrite his
        history to say he never gave up."""
        shrine = _commission_texts()[0]
        old = {"id": "ia1", "intent": shrine, "status": "abandoned",
               "progress": 0.6, "authored": True, "priority": 0.9}
        st = self._state_with([old])
        M.rearm_commission(st, "Vesk", 200)
        rows = [i for i in st["interior"]["intentions"]
                if i["intent"] == shrine]
        assert old in rows and old["status"] == "abandoned", (
            "the abandoned row must survive as history")
        fresh = next(i for i in rows if i is not old)
        assert fresh["status"] == "active"
        assert fresh["progress"] == 0.0
        assert fresh["reissued_from"] == "ia1"
        assert fresh["authored"] is True
        assert fresh["formed_turn"] == 200

    def test_a_blocked_commission_is_revived_in_place_and_reset(self):
        """A blocked goal progressed again is being routed around, so the
        block bookkeeping clears with it (the engine's _revive_intent rule)
        -- and a fresh run starts unrun, so progress resets rather than
        inheriting last run's 1.0 and stalling barren within four beats,
        which is exactly how 'keep moving' died in A11."""
        texts = _commission_texts()
        st = self._state_with([
            {"id": "ia3", "intent": texts[2], "status": "blocked",
             "progress": 1.0, "authored": True, "priority": 0.6,
             "blocked_why": "no eastern doorway", "blocked_turn": 149,
             "stalled_turn": 89, "barren_attempts": 2},
        ])
        M.rearm_commission(st, "Vesk", 200)
        row = next(i for i in st["interior"]["intentions"]
                   if i["intent"] == texts[2])
        assert row["id"] == "ia3", "revival is in place, not a duplicate"
        assert row["status"] == "active" and row["progress"] == 0.0
        assert row["reissued_turn"] == 200
        for gone in ("blocked_why", "blocked_turn", "stalled_turn",
                     "barren_attempts"):
            assert gone not in row

    def test_an_already_active_commission_resets_for_the_fresh_run(self):
        shrine = _commission_texts()[0]
        st = self._state_with([
            {"id": "ia1", "intent": shrine, "status": "active",
             "progress": 0.7, "authored": True, "priority": 0.9},
        ])
        M.rearm_commission(st, "Vesk", 200)
        rows = [i for i in st["interior"]["intentions"]
                if i["intent"] == shrine]
        assert len(rows) == 1, "an active commission is continued, not doubled"
        assert rows[0]["progress"] == 0.0

    def test_the_active_cap_is_respected(self):
        """The engine caps active intentions; a harness that minted past the
        cap would hand the character a goal ledger the engine itself refuses
        to build."""
        from mind.affect import _INTENT_CAP
        filler = [{"id": f"i{n}", "intent": f"unrelated pursuit {n}",
                   "status": "active", "progress": 0.1}
                  for n in range(1, _INTENT_CAP + 1)]
        shrine = _commission_texts()[0]
        st = self._state_with(filler + [
            {"id": "ia1", "intent": shrine, "status": "abandoned",
             "progress": 0.6, "authored": True, "priority": 0.9}])
        M.rearm_commission(st, "Vesk", 200)
        actives = [i for i in st["interior"]["intentions"]
                   if i["status"] == "active"]
        assert len(actives) == _INTENT_CAP
        assert all(i["intent"] != shrine for i in actives)

    def test_ids_come_from_the_engines_minting(self):
        """Forked id namespaces are how a later `serves` key or dedupe pass
        stops resolving; the mint must be the engine's own."""
        shrine = _commission_texts()[0]
        st = self._state_with([
            {"id": "i7", "intent": "something else", "status": "satisfied"},
            {"id": "ia1", "intent": shrine, "status": "abandoned"},
        ])
        M.rearm_commission(st, "Vesk", 200)
        fresh = next(i for i in st["interior"]["intentions"]
                     if i["intent"] == shrine and i["status"] == "active")
        assert fresh["id"] == "i8"

    def test_a_state_with_no_interior_is_grown_not_crashed(self):
        st = {}
        M.rearm_commission(st, "Vesk", 200)
        texts = {i["intent"] for i in st["interior"]["intentions"]}
        assert set(_commission_texts()) <= texts


class TestInterludeWiring:
    """run_interlude must leave the courier fed AND recommissioned -- for
    five runs it did only the first, and each run inherited a spent goal
    ledger wearing a fresh meal."""

    def _seed_chat(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Maze", "", time.time()))
        sheet = M.character_sheet("Vesk")
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            ("Vesk", json.dumps(sheet), "{}", time.time(), "char_vesk"))
        shrine = _commission_texts()[0]
        state = {"interior": {"intentions": [
            {"id": "ia1", "intent": shrine, "status": "abandoned",
             "progress": 0.6, "authored": True, "priority": 0.9}]}}
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)",
            (chat_id, char_id, "active", json.dumps(state)))
        return chat_id, char_id

    def test_the_interlude_rearms_the_commission(self, temp_db):
        chat_id, char_id = self._seed_chat(temp_db)
        M.run_interlude(chat_id, char_id, "Vesk", 1, True, 10)
        row = temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (chat_id, char_id), one=True)
        st = json.loads(row["state"])
        shrine = _commission_texts()[0]
        active = [i for i in st["interior"]["intentions"]
                  if i["intent"] == shrine and i["status"] == "active"]
        assert active, (
            "fed and carried back and still without his work: the next run "
            "would begin exactly as decayed as the last one ended")
        assert active[0]["progress"] == 0.0
        # the meal must still land -- re-arming must not displace the reward
        assert st["active_state"]["hedonic"]["pleasure"] >= 0.45

    def test_a_called_short_run_is_recommissioned_too(self, temp_db):
        """The keepers set him going again either way; only the meal's
        valence differs. A re-arm gated on success would teach the state
        machine that failure ends the job, which is the A11 decay all over
        again."""
        chat_id, char_id = self._seed_chat(temp_db)
        M.run_interlude(chat_id, char_id, "Vesk", 2, False, 20)
        row = temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (chat_id, char_id), one=True)
        st = json.loads(row["state"])
        shrine = _commission_texts()[0]
        assert any(i["intent"] == shrine and i["status"] == "active"
                   for i in st["interior"]["intentions"])
