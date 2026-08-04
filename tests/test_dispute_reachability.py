"""A memory whose meaning is overturned, walked the whole way to the row.

`memory_disputes` has fired zero times in production. Measured honestly
(`tools/fire_rates.py`) that is 0 of 178 -- the beats whose stored result even
carried the field -- next to a sibling introduced in the same commit, on the
same 178 results, firing 78% of the time:

    remember_lines    139/178   78.09%
    memory_disputes     0/178    0.00%

Same model, same beats, same payload, same prompt file. Two readings of that,
and they need different fixes: either the wire is broken somewhere between the
model and the row, or no character in this corpus has ever had a reason to
re-read a memory. These stories are a doctor and a fox spirit having dinner;
nobody has been deceived, disguised or misidentified in any of them.

This file settles it by construction. It builds the occasion the corpus never
produced -- a stranger remembered as kind, seen this beat picking a pocket --
and walks a model-shaped dispute through every stage it must survive: schema
coercion, citation grounding, the commit collector, `record_dispute`, and the
projection that hands the re-reading back to the mind on the next beat. If
these pass, 0/178 is an absence of occasions and the fix is prompt-side; if any
fail, the tier was never reachable and the number meant nothing about the
fiction at all.

Also pinned here: the three ways a dispute must NOT work. It cannot reach
another mind's memory, it cannot locate a memory that was never delivered to
it, and it never edits the memory it re-reads. Deception changes what an
experience meant; it does not change what happened.
"""

from __future__ import annotations

import time

import pytest

import memory
from agents.character import _ground_observation_citations
from memory import add_memory, effective_importance, record_dispute
from schemas import CharacterOutput


# --- the occasion ----------------------------------------------------------

KIND_STRANGER = ("A man in a grey coat stopped to give me directions to the "
                 "waystation when I was lost in the market.")
NOW_READS = ("He was not being kind. He was placing himself beside me long "
             "enough to learn which pocket I keep the purse in.")
SEEN_NOW = ("The man in the grey coat slips two fingers into a merchant's "
            "coat pocket and walks on without breaking stride.")

MEMORY_REF = "event:9f3ac1"
CURRENT_ID = "current:Mara:0"


def _observations():
    return [{"observation_id": CURRENT_ID, "observed": {"text": SEEN_NOW}}]


def _memory_context():
    return {"recent_episodes": [
        {"memory_ref": MEMORY_REF, "gist": KIND_STRANGER}]}


def _result(**overrides):
    """What the model emits on the beat it recognises the face."""
    out = {
        "memory_disputes": [{
            "memory_ref": MEMORY_REF,
            "now_reads": NOW_READS,
            "evidence": [{"event_id": CURRENT_ID,
                          "fact": "he is picking a pocket in front of me"}],
        }],
    }
    out.update(overrides)
    return out


# --- stage 1: the schema keeps it -----------------------------------------

class TestTheSchemaKeepsIt:
    def test_a_dispute_survives_validation(self):
        parsed = CharacterOutput(**_result())
        assert len(parsed.memory_disputes) == 1
        assert parsed.memory_disputes[0].now_reads == NOW_READS
        assert parsed.memory_disputes[0].memory_ref == MEMORY_REF

    def test_a_re_reading_with_nothing_to_say_is_dropped(self):
        """`now_reads` IS the dispute. Without it there is a memory named and
        no claim about it, which would record a bare importance bump under the
        word 're-read'."""
        parsed = CharacterOutput(**_result(memory_disputes=[
            {"memory_ref": MEMORY_REF, "now_reads": "  "}]))
        assert parsed.memory_disputes == []

    def test_a_dispute_naming_no_memory_is_dropped(self):
        parsed = CharacterOutput(**_result(memory_disputes=[
            {"now_reads": NOW_READS}]))
        assert parsed.memory_disputes == []

    def test_the_legacy_gist_locator_still_validates(self):
        parsed = CharacterOutput(**_result(memory_disputes=[
            {"gist": KIND_STRANGER, "now_reads": NOW_READS}]))
        assert len(parsed.memory_disputes) == 1


# --- stage 2: grounding keeps it ------------------------------------------

class TestGroundingKeepsIt:
    def test_a_delivered_ref_with_present_evidence_survives(self):
        out = _result()
        _ground_observation_citations(out, _observations(), _memory_context())
        assert len(out["memory_disputes"]) == 1
        assert out["memory_disputes"][0]["memory_ref"] == MEMORY_REF

    def test_the_magic_word_current_is_bound_to_a_real_observation(self):
        """Models overwhelmingly cite the present beat by label rather than by
        its real id -- 4,939 of 6,404 citations in the corpus. If that cost a
        dispute its evidence, the tier would be unreachable in practice while
        looking reachable in a test that used the real id."""
        out = _result(memory_disputes=[{
            "memory_ref": MEMORY_REF, "now_reads": NOW_READS,
            "evidence": [{"event_id": "current", "fact": "he is stealing"}]}])
        _ground_observation_citations(out, _observations(), _memory_context())
        assert len(out["memory_disputes"]) == 1
        assert out["memory_disputes"][0]["evidence"][0]["event_id"] == CURRENT_ID

    def test_a_legacy_spelling_normalises_before_grounding(self):
        """`perception`, `view`, `current_perception` and a dozen more all
        arrive as `current` via schemas._normalize_event_id."""
        out = CharacterOutput(**_result(memory_disputes=[{
            "memory_ref": MEMORY_REF, "now_reads": NOW_READS,
            "evidence": [{"event_id": "perception", "fact": "he is stealing"}],
        }])).dict()
        _ground_observation_citations(out, _observations(), _memory_context())
        assert len(out["memory_disputes"]) == 1

    def test_the_gist_locator_resolves_to_the_delivered_ref(self):
        out = _result(memory_disputes=[{
            "gist": KIND_STRANGER, "now_reads": NOW_READS,
            "evidence": [{"event_id": CURRENT_ID, "fact": "stealing"}]}])
        _ground_observation_citations(out, _observations(), _memory_context())
        assert out["memory_disputes"][0]["memory_ref"] == MEMORY_REF

    def test_a_memory_this_mind_was_never_given_is_dropped(self):
        """The firewall. A re-reading is still a claim about a memory, and a
        mind cannot make one about a row it was never handed."""
        out = _result(memory_disputes=[{
            "memory_ref": "event:someone-elses", "now_reads": NOW_READS,
            "evidence": [{"event_id": CURRENT_ID, "fact": "stealing"}]}])
        warnings = _ground_observation_citations(
            out, _observations(), _memory_context())
        assert out["memory_disputes"] == []
        assert any("memory_disputes" in w for w in warnings)

    def test_a_re_reading_with_no_present_evidence_is_dropped(self):
        """The whole premise is that LATER evidence changed the meaning. A
        dispute citing nothing from this beat is a mind revising its past for
        no stated reason, which is the one thing this must not become."""
        out = _result(memory_disputes=[{
            "memory_ref": MEMORY_REF, "now_reads": NOW_READS, "evidence": []}])
        _ground_observation_citations(out, _observations(), _memory_context())
        assert out["memory_disputes"] == []

    def test_a_memory_ref_cannot_be_used_as_its_own_evidence(self):
        """Evidence for a re-reading is grounded in the PRESENT namespace, so
        citing the disputed memory back at itself grounds nothing and the
        dispute falls with it."""
        out = _result(memory_disputes=[{
            "memory_ref": MEMORY_REF, "now_reads": NOW_READS,
            "evidence": [{"event_id": MEMORY_REF, "fact": "I remember it"}]}])
        _ground_observation_citations(out, _observations(), _memory_context())
        assert out["memory_disputes"] == []


# --- stage 3: the row records it ------------------------------------------

def _bank(temp_db):
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Market", "", time.time()))
    mara = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Mara", "{}", "{}", time.time()))
    other = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        ("Bram", "{}", "{}", time.time()))
    mid = add_memory(chat_id, mara, None, "episodic", "witnessed", 0.44,
                     KIND_STRANGER, gist=KIND_STRANGER, turn_idx=3,
                     event_key=MEMORY_REF)
    return chat_id, mara, other, mid


class TestTheRowRecordsIt:
    def test_the_re_reading_lands_on_the_row(self, temp_db):
        chat_id, mara, _other, mid = _bank(temp_db)
        assert record_dispute(chat_id, mara, "", NOW_READS, 9,
                              memory_ref=MEMORY_REF) == [mid]
        row = temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True)
        assert NOW_READS in row["disputed"]

    def test_what_she_saw_is_still_true(self, temp_db):
        """The founding distinction. She did meet a man who gave her
        directions; that happened. Only what it meant has moved."""
        chat_id, mara, _other, mid = _bank(temp_db)
        before = temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True)
        record_dispute(chat_id, mara, "", NOW_READS, 9, memory_ref=MEMORY_REF)
        after = temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True)
        for column in ("content", "gist", "provenance", "salience", "kind"):
            assert after[column] == before[column], column

    def test_being_wrong_about_it_makes_it_matter_more(self, temp_db):
        chat_id, mara, _other, mid = _bank(temp_db)
        before = effective_importance(
            temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True))
        record_dispute(chat_id, mara, "", NOW_READS, 9, memory_ref=MEMORY_REF)
        after = effective_importance(
            temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True))
        assert after > before

    def test_it_cannot_reach_another_mind_s_memory(self, temp_db):
        chat_id, _mara, other, _mid = _bank(temp_db)
        assert record_dispute(chat_id, other, KIND_STRANGER, NOW_READS, 9,
                              memory_ref=MEMORY_REF) == []

    def test_the_next_beat_shows_her_the_re_reading(self, temp_db):
        """Recorded and never delivered would be the same as not recorded."""
        chat_id, mara, _other, mid = _bank(temp_db)
        record_dispute(chat_id, mara, "", NOW_READS, 9, memory_ref=MEMORY_REF)
        row = temp_db.q("SELECT * FROM memories WHERE id=?", (mid,), one=True)
        projected = memory._with_reading(memory._row_memory(row))
        assert projected["i_now_read_this_differently"] == NOW_READS


# --- stage 4: the collector between them ----------------------------------

def test_commit_collects_every_field_record_dispute_needs():
    """The one seam with no unit of its own: `prepare_memory_commit` flattens
    each result's disputes into tuples that the write phase replays. A field
    dropped here fails silently -- `record_dispute` returns [] for a missing
    reading and nothing anywhere objects."""
    import inspect

    import commit
    src = inspect.getsource(commit)
    collector = src[src.index('for _d in own_result.get("memory_disputes")'):]
    collector = collector[:collector.index("# Consequence, not popularity")]
    for field in ('_d.get("gist")', '_d.get("now_reads")',
                  '_d.get("memory_ref")'):
        assert field in collector, field
    writer = src[src.index('prepared.get(\n                "memory_disputes")'):]
    writer = writer[:writer.index("# Memories that turned out")]
    assert "record_dispute(chat_id, char_id, _gist, _reading, _tidx," in writer
    assert "memory_ref=_ref" in writer


def test_the_prompt_states_an_occasion_and_not_only_prohibitions():
    """Why the corpus reads 0/178 while its sibling reads 139/178, once the
    wire above is proven intact.

    CLAUDE.md records the same failure shape twice from the maze arms: bare
    prohibitions invert, and a character read `never breaking stride` as an
    argument against running. The dispute instruction was two prohibitions and
    one abstract permission, next to `memory_effects` -- which fires 89% and
    names concrete occasions. A model that has never seen an example of when
    to do a thing does not do it.
    """
    import prompts

    block = prompts.DEFAULT_PROMPTS["character"]
    line = next(l for l in block.splitlines()
                if "READING A MEMORY DIFFERENTLY" in l)
    for occasion in ("disguise", "lied", "staged"):
        assert occasion in line.casefold(), occasion
