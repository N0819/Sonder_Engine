"""The reading pass that replaced two statistics, and what it may not become.

`recall_confidence` answered "does anything here bear on the moment" with a
z-score over retrieval scores and fires 0 of 30 times on probes whose answers
are absent by construction; deterministic contradiction detection answered "do
any two of these disagree" with similarity and entity overlap, and a real
contradiction scores BELOW the 95th percentile of unrelated pairs while
sharing a named person 0.0% of the time against 16.6% for random pairs. Both
failures have one cause: contradiction and relevance are semantic relations,
and every signal available to a scorer is a topical one.

So the engine reads the rows now. These tests are mostly about the ways that
reading must be prevented from becoming something else.

**The one it must never become is a verdict.** Nothing outside a mind is
entitled to decide which of that mind's memories is true. A tension names two
memories and the subject they disagree about; a "tension" with one side is a
judgement about a single memory wearing the word, and it is dropped rather
than trusted, because a prompt clause cannot be a guarantee (three literal
guards were measured failing in one day for exactly that reason).

**And it must never speak from silence.** A review that did not happen -- no
model configured, a timeout, unreadable output -- has said nothing about this
bank. Writing `nothing_comes_back_clearly` on a failure would be the engine
telling a mind its own memory came back empty because a network call did.
"""

from __future__ import annotations

import json
import time

import pytest

from mind import memory_judge
from mind.memory_judge import review_recall


def _rows(n=4):
    return [
        {"memory_ref": "event:%02d" % i,
         # Fiction time, like every real caller since the clock reading
         # landed on the row -- a fixture teaching the old beat vocabulary
         # outlives the code that produced it.
         "when": "about %d minutes ago" % (i * 10),
         "epistemic_origin": "what_i_experienced",
         "gist": "gist %d" % i,
         "details": "The %dth thing that happened." % i}
        for i in range(1, n + 1)
    ]


def _answering(payload):
    """A stub that records what it was asked and answers with `payload`."""
    seen = {}

    def _fn(role, system, user, **kw):
        seen["role"] = role
        seen["system"] = system
        seen["user"] = json.loads(user)
        seen["kw"] = kw
        return json.dumps(payload)

    _fn.seen = seen
    return _fn


class TestItFailsOpen:
    def test_a_provider_error_returns_the_empty_verdict(self, monkeypatch):
        def _boom(*_a, **_k):
            raise RuntimeError("No model configured for role 'utility'")

        monkeypatch.setattr(memory_judge, "chat_complete", _boom)
        got = review_recall("Mara", "the bridge at dusk", _rows())
        assert got["available"] is False
        assert got["tensions"] == []
        assert got["bears"] is None, (
            "None, not [] -- an empty list means 'nothing bears on this', "
            "which is a claim a failed call has not earned")

    def test_unreadable_output_returns_the_empty_verdict(self, monkeypatch):
        monkeypatch.setattr(memory_judge, "chat_complete",
                            lambda *a, **k: "I'm afraid I can't do that.")
        assert review_recall("Mara", "the bridge", _rows())["available"] is False

    def test_json_inside_prose_is_still_read(self, monkeypatch):
        """The consolidator's own tolerance, for the same reason it has it."""
        monkeypatch.setattr(
            memory_judge, "chat_complete",
            lambda *a, **k: 'Sure!\n{"bears_on_this_moment": ["event:01"], '
                            '"tensions": []}\nHope that helps.')
        got = review_recall("Mara", "the bridge", _rows())
        assert got["available"] is True and got["bears"] == ["event:01"]


class TestATensionIsNeverAVerdict:
    def test_a_one_sided_tension_is_dropped(self, monkeypatch):
        """A judgement about a single memory is exactly what this pass may
        not produce, whatever it calls itself."""
        monkeypatch.setattr(memory_judge, "chat_complete", _answering({
            "bears_on_this_moment": ["event:01"],
            "tensions": [{"memories": ["event:01"],
                          "they_disagree_about": "this memory is unreliable"}],
        }))
        assert review_recall("Mara", "the bridge", _rows())["tensions"] == []

    def test_a_tension_citing_an_undelivered_memory_is_dropped(self,
                                                               monkeypatch):
        """A citation to a row the mind was not handed is how a model's
        invention would enter a character's head in the engine's voice."""
        monkeypatch.setattr(memory_judge, "chat_complete", _answering({
            "tensions": [{"memories": ["event:01", "event:99"],
                          "they_disagree_about": "the canal"}],
        }))
        assert review_recall("Mara", "the bridge", _rows())["tensions"] == []

    def test_a_tension_with_no_subject_is_dropped(self, monkeypatch):
        """"These two disagree" with nothing named is an assertion the mind
        cannot check against the rows it holds."""
        monkeypatch.setattr(memory_judge, "chat_complete", _answering({
            "tensions": [{"memories": ["event:01", "event:02"],
                          "they_disagree_about": "   "}],
        }))
        assert review_recall("Mara", "the bridge", _rows())["tensions"] == []

    def test_a_good_tension_survives_with_both_sides(self, monkeypatch):
        monkeypatch.setattr(memory_judge, "chat_complete", _answering({
            "bears_on_this_moment": ["event:01", "event:02"],
            "tensions": [{"memories": ["event:01", "event:02"],
                          "they_disagree_about": "the water level in the canal"}],
        }))
        got = review_recall("Mara", "the bridge", _rows())
        assert got["tensions"] == [
            {"memories": ["event:01", "event:02"],
             "they_disagree_about": "the water level in the canal"}]

    def test_the_occasion_budget_is_capped(self, monkeypatch):
        rows = _rows(8)
        monkeypatch.setattr(memory_judge, "chat_complete", _answering({
            "tensions": [{"memories": ["event:0%d" % a, "event:0%d" % b],
                          "they_disagree_about": "subject %d" % a}
                         for a, b in ((1, 2), (3, 4), (5, 6), (7, 8))],
        }))
        got = review_recall("Mara", "the bridge", rows)
        assert len(got["tensions"]) == memory_judge._MAX_TENSIONS


class TestWhatItIsAsked:
    def test_it_only_ever_sees_the_rows_it_was_given(self, monkeypatch):
        """The firewall property, and it is structural rather than promised:
        the payload is built from the argument, so there is no path by which
        another mind's memory could reach this call."""
        stub = _answering({})
        monkeypatch.setattr(memory_judge, "chat_complete", stub)
        rows = _rows(5)
        review_recall("Mara", "the bridge at dusk", rows)
        sent = stub.seen["user"]
        assert [r["memory_ref"] for r in sent["what_came_back"]] == \
            [r["memory_ref"] for r in rows]
        assert sent["character"] == "Mara"

    def test_it_rides_the_cheap_lane(self, monkeypatch):
        stub = _answering({})
        monkeypatch.setattr(memory_judge, "chat_complete", stub)
        review_recall("Mara", "the bridge", _rows())
        assert stub.seen["role"] == "utility"
        assert stub.seen["kw"]["temperature"] == 0.0

    def test_a_long_moment_and_long_rows_are_bounded(self, monkeypatch):
        stub = _answering({})
        monkeypatch.setattr(memory_judge, "chat_complete", stub)
        rows = _rows(3)
        rows[0]["details"] = "x" * 5000
        review_recall("Mara", "y " * 4000, rows)
        sent = stub.seen["user"]
        assert len(sent["the_moment"]) <= memory_judge._MOMENT_CHARS
        assert all(len(r["memory"]) <= memory_judge._ROW_CHARS
                   for r in sent["what_came_back"])

    def test_too_few_rows_costs_no_call_at_all(self, monkeypatch):
        called = []
        monkeypatch.setattr(memory_judge, "chat_complete",
                            lambda *a, **k: called.append(1) or "{}")
        assert review_recall("Mara", "the bridge",
                             _rows(2))["available"] is False
        assert not called, "a tension needs two rows to sit between"

    def test_no_moment_costs_no_call_at_all(self, monkeypatch):
        called = []
        monkeypatch.setattr(memory_judge, "chat_complete",
                            lambda *a, **k: called.append(1) or "{}")
        assert review_recall("Mara", "   ", _rows())["available"] is False
        assert not called

    def test_a_row_with_no_ref_cannot_be_cited_so_is_not_sent(self,
                                                              monkeypatch):
        stub = _answering({})
        monkeypatch.setattr(memory_judge, "chat_complete", stub)
        rows = _rows(4)
        rows[1]["memory_ref"] = ""
        review_recall("Mara", "the bridge", rows)
        assert len(stub.seen["user"]["what_came_back"]) == 3


class TestTheOccasionBecameARetrieval:
    """What the pass leaves behind, and the one thing it must never say.

    The first build handed a mind the pair and the subject:
    `memories_that_do_not_sit_together`. Measured on a neutral beat with both
    rows already in the payload, that scored **13/16** against **16/16** for
    saying nothing at all -- the third instance in one day of an invitation to
    notice making a mind notice less.

    What the same measurement found is that co-presence is the whole
    mechanism: on an unaimed beat, ordinary recall put both halves of a
    contradiction in front of a mind **0 times in 18**. So the subject is used
    to RETRIEVE and the verdict is never stated.
    """

    def test_the_subject_is_offered_and_the_pair_is_not(self):
        from mind.memory_judge import pending_subject
        state = {"memory_tensions": [
            {"memories": ["event:01", "event:02"],
             "they_disagree_about": "the water level in the canal",
             "turn_idx": 100}]}
        assert pending_subject(state, 110) == "the water level in the canal"

    def test_nothing_pending_seeds_nothing(self):
        from mind.memory_judge import pending_subject
        assert pending_subject({}, 110) == ""

    def test_a_stale_occasion_expires_unoffered(self):
        """Re-offering forever is the haunting `contrast_memory` refuses to
        become."""
        from mind.memory_judge import pending_subject, _TENSION_TTL_BEATS
        state = {"memory_tensions": [
            {"memories": ["event:01", "event:02"],
             "they_disagree_about": "the canal", "turn_idx": 100}]}
        assert pending_subject(state, 100 + _TENSION_TTL_BEATS + 1) == ""

    def test_a_malformed_blob_is_read_as_nothing(self):
        """Six other writers touch this column. Anything unreadable must cost
        a character a missing annotation, never a raised beat."""
        from mind.memory_judge import pending_tensions
        for junk in ({"memory_tensions": "not a list"},
                     {"memory_tensions": [None, 3, "x"]},
                     {"memory_tensions": [{"memories": ["only-one"],
                                           "they_disagree_about": "x",
                                           "turn_idx": 1}]},
                     {"memory_tensions": [{"memories": ["a", "b"],
                                           "they_disagree_about": "",
                                           "turn_idx": 1}]},
                     {"memory_tensions": [{"memories": ["a", "b"],
                                           "they_disagree_about": "x",
                                           "turn_idx": "soon"}]}):
            assert pending_tensions(junk, 10) == []

    def test_the_docket_is_bounded(self):
        from mind.memory_judge import pending_tensions, _MAX_PENDING_TENSIONS
        state = {"memory_tensions": [
            {"memories": ["event:%d" % i, "event:%d" % (i + 100)],
             "they_disagree_about": "subject %d" % i, "turn_idx": 5}
            for i in range(10)]}
        assert len(pending_tensions(state, 6)) == _MAX_PENDING_TENSIONS

    def test_the_seed_becomes_a_retrieval_on_that_subject(self, monkeypatch,
                                                          temp_db):
        """Co-presence is the mechanism, so the subject must reach the
        retriever -- measured: on an unaimed beat ordinary recall delivers
        both halves of a contradiction 0 times in 18."""
        from mind import memory, memory_context
        asked = []
        real = memory_context.search_memories

        def _spy(chat_id, char_id, query, **kw):
            asked.append(query)
            return real(chat_id, char_id, query, **kw)

        monkeypatch.setattr(memory_context, "search_memories", _spy)
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Resurface", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Mara", "{}", "{}", time.time()))
        memory.add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.6,
                          "The canal ran dangerously low.", turn_idx=1)
        ctx = memory.build_character_memory_context(
            chat_id, char_id, current_turn_idx=20, current_view="a quiet quay",
            active_state={}, resurfaced_subject="the water level in the canal")
        assert "the water level in the canal" in asked
        blob = json.dumps(ctx)
        assert "disagree" not in blob and "do_not_sit_together" not in blob, (
            "it may hand over rows, never the verdict it formed")

    def test_no_subject_means_no_lane_and_no_second_retrieval(self, temp_db):
        from mind import memory
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Resurface", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Mara", "{}", "{}", time.time()))
        memory.add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.6,
                          "The canal ran low.", turn_idx=1)
        ctx = memory.build_character_memory_context(
            chat_id, char_id, current_turn_idx=20, current_view="a quiet room",
            active_state={})
        assert "resurfaced_without_asking" not in ctx


class TestTheMintPassWritesWithoutClobbering:
    @pytest.fixture
    def bank(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Tension", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) "
            "VALUES(?,?,?,?)", ("Mara", "{}", "{}", time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,state) "
                   "VALUES(?,?,?)",
                   (chat_id, char_id,
                    json.dumps({"stress": 0.4, "unbidden": {"recent_ids": [7]}})))
        return chat_id, char_id

    def test_it_touches_only_its_own_key(self, bank, temp_db):
        """The reason `json_set` is used instead of read-modify-write. This
        job runs on a background thread while the next beat's commit rewrites
        the SAME column with the character's psychology, stress, beliefs and
        unbidden ledger in it. Whole-blob writes mean the loser of that race
        forfeits a turn of primary state, for the sake of an annotation that
        is reconstructible by re-running the pass.
        """
        from mind import memory_judge
        chat_id, char_id = bank
        memory_judge._store_tensions(chat_id, char_id, None, [
            {"memories": ["event:a", "event:b"],
             "they_disagree_about": "the roof", "turn_idx": 3}])
        state = json.loads(temp_db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (chat_id, char_id), one=True)["state"])
        assert state["stress"] == 0.4, "psychology must survive"
        assert state["unbidden"] == {"recent_ids": [7]}, "ledger must survive"
        assert state["memory_tensions"][0]["they_disagree_about"] == "the roof"

    def test_a_beat_that_minted_nothing_costs_no_call(self, bank, monkeypatch):
        """Nothing new was recorded, so nothing new can have contradicted
        anything."""
        from mind import memory_judge
        called = []
        monkeypatch.setattr(memory_judge, "chat_complete",
                            lambda *a, **k: called.append(1) or "{}")
        chat_id, char_id = bank
        assert memory_judge.review_minted_memories(
            chat_id, char_id, "Mara", [], current_turn_idx=4) == 0
        assert not called

    def test_a_second_occasion_does_not_erase_the_first(self, bank,
                                                        monkeypatch):
        """Two beats can each find a real one, and the second must not wipe
        the first before any mind has been handed it."""
        from mind import memory_judge
        chat_id, char_id = bank
        memory_judge._store_tensions(chat_id, char_id, None, [
            {"memories": ["event:a", "event:b"],
             "they_disagree_about": "the roof", "turn_idx": 3}])
        monkeypatch.setattr(memory_judge, "search_memories", lambda *a, **k: [],
                            raising=False)
        monkeypatch.setattr(
            memory_judge, "review_recall",
            lambda *a, **k: {"available": True, "bears": [], "tensions": [
                {"memories": ["event:c", "event:d"],
                 "they_disagree_about": "the ledger"}]})
        added = memory_judge.review_minted_memories(
            chat_id, char_id, "Mara",
            [{"event_key": "event:c", "gist": "found it", "turn_idx": 5}],
            current_turn_idx=5)
        assert added == 1
        from core import db
        state = json.loads(db.q(
            "SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
            (chat_id, char_id), one=True)["state"])
        subjects = {t["they_disagree_about"] for t in state["memory_tensions"]}
        assert subjects == {"the roof", "the ledger"}


class TestAMindIsToldWhyItWentLooking:
    """`ponder.why` was required, stored, and never read back.

    `agents/common.py` DROPS a ponder that arrives without a reason and warns
    about it, on the stated grounds that "dropping half of one silently is the
    same failure shape as blanking an act". `commit_memory.py` then stores the
    reason beside the query. Nothing read it: `agents/character.py` took
    `.get("query")` alone, and the payload carried `query_i_chose_last_turn`
    and nothing else.

    So a mind was compelled to say why it wanted to remember something, and on
    the beat its answer came back it was shown the question and left to
    re-derive its own motive. Write-only, exactly like `knows_identity`
    (UNBUILT 3.1) -- set at several sites, read at none.
    """

    def _ctx(self, temp_db, **kw):
        from mind import memory
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Ponder", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Mara", "{}", "{}", time.time()))
        memory.add_memory(chat_id, char_id, None, "episodic", "witnessed", 0.6,
                          "The ledger was ruined in the flood.", turn_idx=1)
        return memory.build_character_memory_context(
            chat_id, char_id, current_turn_idx=9, current_view="a quiet room",
            active_state={}, **kw)

    def test_the_reason_reaches_the_mind_beside_the_question(self, temp_db):
        ctx = self._ctx(temp_db, ponder_query="what happened to the ledger",
                        ponder_why="I keep being asked for it and cannot say")
        lane = ctx["deliberate_recall"]
        assert lane["query_i_chose_last_turn"] == "what happened to the ledger"
        assert lane["why_i_chose_it"] == \
            "I keep being asked for it and cannot say"

    def test_a_legacy_state_with_no_reason_omits_the_key(self, temp_db):
        """Blobs written before this existed carry query and set_turn only.
        An empty string would spend a mind's attention saying nothing."""
        ctx = self._ctx(temp_db, ponder_query="what happened to the ledger")
        assert "why_i_chose_it" not in ctx["deliberate_recall"]

    def test_no_ponder_means_no_lane_at_all(self, temp_db):
        ctx = self._ctx(temp_db, ponder_why="orphaned reason, no question")
        assert "deliberate_recall" not in ctx

    def test_the_reason_travels_with_the_label_outside_the_lane(self, temp_db):
        """A ponder result that ALSO came back through ordinary recall sits in
        `recalled_old_memories`, stamped `deliberate_ponder` but structurally
        apart from the lane that states the reason once. That row is the one a
        mind reads as "you went looking for this" with no motive attached."""
        from mind import memory
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Ponder", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Mara", "{}", "{}", time.time()))
        for i in range(4):
            memory.add_memory(chat_id, char_id, None, "episodic", "witnessed",
                              0.6, "The ledger was ruined in the flood, %d." % i,
                              turn_idx=i + 1)
        ctx = memory.build_character_memory_context(
            chat_id, char_id, current_turn_idx=9,
            current_view="the ledger was ruined in the flood",
            active_state={}, ponder_query="the ledger in the flood",
            ponder_why="Tom keeps asking and I cannot say")
        overlap = [m for m in ctx["recalled_old_memories"]
                   if "deliberate_ponder" in (m.get("retrieval_origin") or [])]
        assert overlap, "the query and view were built to overlap"
        assert all(m.get("why_i_went_looking") == "Tom keeps asking and I "
                   "cannot say" for m in overlap)

    def test_the_lane_does_not_pay_for_the_reason_twice(self, temp_db):
        """Rows inside `deliberate_recall` have it at their head already."""
        ctx = self._ctx(temp_db, ponder_query="what happened to the ledger",
                        ponder_why="Tom keeps asking")
        lane = ctx.get("deliberate_recall") or {}
        assert lane.get("why_i_chose_it") == "Tom keeps asking"
        assert all("why_i_went_looking" not in m
                   for m in (lane.get("additional_episodes") or []))
