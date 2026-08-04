"""Which memories stand behind each clause of a consolidated summary.

A summary is the one thing in this engine that reaches a character with no
provenance at all. `memory_effects` is grounded to raw memories, beliefs cite
evidence, disputes need a delivered ref -- but a consolidator sentence arrives
as prose and is read as true. Summaries are deliberately barred from
reinforcing durable belief, which contains most of the danger, and they still
move appraisal and speech, and until now they left no trace when they did.

`derive_summary_support` records one entry per clause:

    {"claim": ..., "support_refs": [event_key, ...], "epistemic_origin": ...}

Three design choices this file pins, each with a reason that is not obvious:

**Host-side and lexical, not a model call and not embeddings.** The question
is "which stored rows does this sentence actually talk about", which has a
checkable answer. An audit trail produced by the same kind of process it
audits is not an audit trail.

**An empty support set is a result, not a failure.** It says the clause
generalises, compresses several rows, or was invented -- and this does not try
to tell those apart, because that is a judgement and this is a measurement.
What changed is that the clause is now countable.

**Refs are event_keys, never row ids.** Checkpoint restore is
delete-and-reinsert, so every id changes; an id-keyed trail would be shredded
by the first rollback and silently wrong after a branch. Same reasoning that
keeps disputes off id-keyed edges.

And one firewall: support is scoped to the memories of the summary's OWN
epistemic class. A first-hand clause supported by something the character was
merely told would be an audit trail that launders hearsay into experience.
"""

from __future__ import annotations

import time

import pytest

import memory
from memory import (derive_summary_support, save_memory_summary,
                    summary_support)


def _mem(event_key, gist, provenance="witnessed", **kw):
    return {"event_key": event_key, "gist": gist, "content": gist,
            "provenance": provenance, "key_phrases": kw.get("key_phrases", []),
            "entities": kw.get("entities", [])}


WINDOW = [
    _mem("event:aa", "Vrenak demanded the remand of Reyet Solan under the "
                     "Argosy Compact"),
    _mem("event:bb", "Tessik was found dead in the shuttle bay"),
    _mem("event:cc", "Solan offered the decryption key for the encrypted "
                     "schematics"),
]


class TestAClauseFindsItsMemories:
    def test_a_clause_is_matched_to_the_row_it_talks_about(self):
        support = derive_summary_support(
            "Vrenak demanded the remand of Solan under the Argosy Compact.",
            WINDOW)
        assert len(support) == 1
        assert support[0]["support_refs"] == ["event:aa"]

    def test_each_sentence_gets_its_own_entry(self):
        support = derive_summary_support(
            "Vrenak demanded the remand of Reyet Solan under the Argosy "
            "Compact. Tessik was found dead in the shuttle bay.", WINDOW)
        assert [s["claim"][:6] for s in support] == ["Vrenak", "Tessik"]
        assert support[0]["support_refs"] == ["event:aa"]
        assert support[1]["support_refs"] == ["event:bb"]

    def test_key_phrases_and_entities_count_as_the_memory_s_words(self):
        window = [_mem("event:dd", "she said it plainly",
                       key_phrases=["the northern door"],
                       entities=["Hensa"])]
        support = derive_summary_support(
            "Hensa warned about the northern door.", window)
        assert support[0]["support_refs"] == ["event:dd"]

    def test_a_clause_is_capped_at_a_few_refs(self):
        window = [_mem(f"event:{i}", "Vrenak demanded the remand of Reyet "
                                     "Solan under the Argosy Compact")
                  for i in range(8)]
        support = derive_summary_support(
            "Vrenak demanded the remand of Reyet Solan under the Argosy "
            "Compact.", window)
        assert len(support[0]["support_refs"]) <= memory._SUPPORT_MAX_REFS


class TestAnUnsupportedClauseIsVisible:
    def test_an_invented_clause_carries_no_refs(self):
        """The whole point. A sentence the consolidator produced that no
        memory in its own window talks about is now countable."""
        support = derive_summary_support(
            "He has always resented the Federation for what happened at "
            "Setlik.", WINDOW)
        assert support[0]["support_refs"] == []

    def test_an_unsupported_clause_claims_no_epistemic_origin(self):
        """Defaulting it to first-hand would be the one wrong answer that
        matters: a sentence with nothing behind it reading as something the
        character saw."""
        support = derive_summary_support("He has always resented them.", WINDOW)
        assert support[0]["epistemic_origin"] == ""

    def test_a_coincidental_word_or_two_is_not_support(self):
        """Prose this dense shares words constantly. At an overlap of two,
        every clause matched every memory in its own window."""
        assert memory._SUPPORT_MIN_OVERLAP >= 3
        support = derive_summary_support("The dead were counted.", WINDOW)
        assert support[0]["support_refs"] == []

    def test_the_supported_and_unsupported_are_separable_in_one_summary(self):
        support = derive_summary_support(
            "Tessik was found dead in the shuttle bay. Nobody has said why.",
            WINDOW)
        assert [bool(s["support_refs"]) for s in support] == [True, False]


class TestEpistemicOrigin:
    def test_it_names_the_class_of_the_strongest_supporter(self):
        window = [_mem("event:ee", "the harbour master keeps the ledger",
                       provenance="heard")]
        support = derive_summary_support(
            "The harbour master keeps the ledger.", window)
        assert support[0]["epistemic_origin"] == "what_i_was_told"

    def test_a_witnessed_supporter_reads_as_experience(self):
        support = derive_summary_support(
            "Tessik was found dead in the shuttle bay.", WINDOW)
        assert support[0]["epistemic_origin"] == "what_i_experienced"

    def test_an_inference_reads_as_a_conclusion(self):
        window = [_mem("event:ff", "Vrenak is stalling for the weapons to "
                                   "finish charging", provenance="inferred")]
        support = derive_summary_support(
            "Vrenak is stalling for the weapons to finish charging.", window)
        assert support[0]["epistemic_origin"] == "what_i_concluded"


class TestItSurvivesEverything:
    def _fixture(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", time.time()))
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            ("Picard", "{}", "{}", time.time()))
        return chat_id, char_id

    def test_it_round_trips_through_the_row(self, temp_db):
        chat_id, char_id = self._fixture(temp_db)
        support = derive_summary_support(
            "Tessik was found dead in the shuttle bay.", WINDOW)
        save_memory_summary(chat_id, char_id, "Tessik was found dead in the "
                                              "shuttle bay.",
                            end_turn_idx=10, support=support)
        stored = summary_support(chat_id, char_id)
        assert stored[0]["support_refs"] == ["event:bb"]
        assert stored[0]["claim"].startswith("Tessik")

    def test_an_old_summary_without_support_reads_as_empty(self, temp_db):
        """Existing rows keep '[]'. That means 'never derived', not 'nothing
        supports it' -- and the two are unknowable after the fact, because
        consolidation has already archived the window."""
        chat_id, char_id = self._fixture(temp_db)
        save_memory_summary(chat_id, char_id, "Something happened.",
                            end_turn_idx=10)
        assert summary_support(chat_id, char_id) == []

    def test_a_malformed_blob_does_not_break_the_summary(self, temp_db):
        chat_id, char_id = self._fixture(temp_db)
        save_memory_summary(chat_id, char_id, "Something happened.",
                            end_turn_idx=10)
        temp_db.qi("UPDATE memory_summaries SET support='{not json' "
                   "WHERE chat_id=?", (chat_id,))
        assert summary_support(chat_id, char_id) == []
        assert memory.get_memory_summary(chat_id, char_id)

    def test_it_survives_dump_and_restore(self, temp_db):
        """Checkpoint rollback and chat export both go through here."""
        chat_id, char_id = self._fixture(temp_db)
        support = derive_summary_support(
            "Tessik was found dead in the shuttle bay.", WINDOW)
        save_memory_summary(chat_id, char_id, "Tessik was found dead in the "
                                              "shuttle bay.",
                            end_turn_idx=10, support=support)
        dumped = memory.dump_memory_summaries(chat_id)
        assert dumped[0]["support"][0]["support_refs"] == ["event:bb"]
        memory.restore_memory_summaries(chat_id, dumped)
        assert summary_support(chat_id, char_id)[0]["support_refs"] == \
            ["event:bb"]

    def test_the_refs_are_event_keys_not_row_ids(self, temp_db):
        """Restore is delete-and-reinsert, so row ids all change. This is why
        the trail is keyed on something that does not."""
        support = derive_summary_support(
            "Tessik was found dead in the shuttle bay.", WINDOW)
        for ref in support[0]["support_refs"]:
            assert ref.startswith("event:")
            assert not ref.isdigit()


class TestTheFirewall:
    def test_consolidation_scopes_support_to_the_summary_s_own_class(self):
        """A first-hand clause supported by something the character was only
        TOLD would be an audit trail that launders hearsay into experience."""
        import inspect

        src = inspect.getsource(memory._write_consolidated_window)
        assert "support=derive_summary_support(" in src
        assert "summary_scope_for(m.get(\"provenance\")) == scope" in src

    def test_a_memory_with_no_event_key_cannot_be_cited(self):
        """An unkeyed row cannot be found again, so naming it in a trail would
        produce a reference nothing can resolve."""
        window = [{"event_key": "", "gist": "Tessik was found dead in the "
                                            "shuttle bay",
                   "content": "", "provenance": "witnessed"}]
        support = derive_summary_support(
            "Tessik was found dead in the shuttle bay.", window)
        assert support[0]["support_refs"] == []


def test_an_empty_summary_derives_nothing():
    assert derive_summary_support("", WINDOW) == []
    assert derive_summary_support(None, WINDOW) == []
    assert derive_summary_support("   ", WINDOW) == []


def test_no_memories_still_produces_one_entry_per_clause():
    """Because the absence of support is the finding, not a reason to record
    nothing."""
    support = derive_summary_support("One thing. Then another thing.", [])
    assert len(support) == 2
    assert all(s["support_refs"] == [] for s in support)
