"""What `remember_lines` is actually keeping, measured before it is gated.

The plan was to consider a budget or a novelty gate on marked lines: 149
dialogue rows corpus-wide, nothing separating a line the model chose to keep
from one the fixed phrase list would have kept anyway, and no idea whether any
of them ever come back. `tools/remember_lines.py` answered all three
(1,633 turns, 146 marks):

    landed as a memory row              125 / 146   85.6%
    the fixed phrase list had it too      0 / 125    0.0%
    only this character's judgement     125 / 125  100.0%
    gave a `why`                        146 / 146  100.0%

    retrieved later, kept by judgement   38 / 125   30.4%
    retrieved later, every non-dialogue 587 / 6326   9.3%

So: **no gate.** Zero overlap with the phrase list means the feature is doing
entirely new work rather than re-keeping what was already durable, and a 3.3x
retrieval rate against ordinary memory means what it keeps is what comes back.
Budgeting a mechanism with those numbers would be throttling the most
load-bearing rows in the bank.

Two things the measurement could NOT answer, recorded rather than guessed:
`why` is present on 146 of 146 marks, so it cannot predict anything -- a
constant is not a signal; and 21 marks matched no row, which is either the
grounding drop working as designed or the tool's quote matching being strict.

The discriminator that made all of this possible needs no schema change: the
phrase list is a pure function of the quote, so a kept line the list would have
REJECTED is one only this character preserved. That only holds while the tool
asks the same question the engine asked, which is what this file pins. Both
now read one table -- `persist.commit_memory._DURABLE_QUOTE_MARKERS` in the
story's own language pack -- so the two can no longer drift apart by editing
one of them; what they can still do is read it differently, and that is what
is checked here.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import remember_lines  # noqa: E402

from persist.commit import _durable_dialogue_category  # noqa: E402

# Every trigger in commit._durable_dialogue_category, plus the shapes that must
# NOT trigger it -- the ones the feature exists to catch.
LISTED = [
    "I promise I will be there", "I swear it on my life", "I vow to return",
    "you have my word", "I'll return before dark", "I will return",
    "my name is Mara", "call me Bram", "I confess I took it",
    "the truth is he never left", "I killed him", "I betrayed you",
    "I love you", "I hate you", "I'll kill you", "I will kill him",
]
NOT_LISTED = [
    "Do not open the northern door after dark",
    "The seal breaks at the third bell",
    "Bring the ledger to the harbour, not the house",
    "It would be a shame if the shipment were delayed",
    "Grey coats never come to this quarter alone",
    "Ask for Hensa; she still owes me",
    # A marker begins at a word boundary, never inside another word. Bare
    # substring matching filed these as promises: of the live corpus's 5
    # promise-category rows, 3 were the word "compromised" (chat 6, twice,
    # and chat 58's "TARGETING COMPROMISED").
    "Section C and D compromised -- compromised how?",
    "TARGETING COMPROMISED. THROWING OBJECTS WILL NOT SAVE YOU!",
]


class TestTheToolAsksTheSameQuestionTheEngineAsked:
    """The tool still does not import the engine -- importing `commit` pulls
    the database configuration in behind it, and a read-only analysis tool
    that opens a live database for writing is worse than a second copy of a
    word list. It does not need to: `language_runtime` defers every `core.db`
    import into a function body, so both sides can read the one pack table
    without either of them configuring a database."""

    def test_every_listed_phrase_agrees(self):
        for text in LISTED:
            assert (remember_lines._phrase_list_would_keep(text)
                    == _durable_dialogue_category(text)), text

    def test_every_unlisted_phrase_agrees(self):
        for text in NOT_LISTED:
            assert remember_lines._phrase_list_would_keep(text) is None, text
            assert _durable_dialogue_category(text) is None, text

    def test_the_two_functions_agree_on_emptiness(self):
        for text in ("", None, "   "):
            assert (remember_lines._phrase_list_would_keep(text)
                    == _durable_dialogue_category(text))

    def test_the_tool_reads_the_language_the_story_was_played_in(self):
        """COMMIT-12: the discriminator is "would the list have kept this",
        and asking it in English of a Japanese line answers no every time --
        which counts every kept line in that story as the character's own
        judgement and silently inflates the one number this tool produces."""
        from language_runtime import language_scope

        line = "必ず戻ると約束する"
        assert remember_lines._phrase_list_would_keep(line, "en") is None
        assert remember_lines._phrase_list_would_keep(line, "ja") == "promise"
        with language_scope("ja"):
            assert _durable_dialogue_category(line) == "promise"


class TestWhatTheListCannotCatch:
    """The premise of the whole feature, stated as cases. A warning, an
    instruction, a code, an indirect threat and a newly established fact are
    all obviously worth keeping and all invisible to a keyword list."""

    def test_a_warning_is_not_listed(self):
        assert _durable_dialogue_category(
            "Do not open the northern door after dark") is None

    def test_an_indirect_threat_is_not_listed(self):
        assert _durable_dialogue_category(
            "It would be a shame if the shipment were delayed") is None

    def test_a_newly_established_fact_is_not_listed(self):
        assert _durable_dialogue_category(
            "The seal breaks at the third bell") is None


class TestTheQuoteReader:
    def test_it_takes_the_words_inside_the_marks(self):
        assert remember_lines._quote_body(
            'she said "bring the ledger" to him') == "bring the ledger"

    def test_typographic_quotes_count(self):
        assert remember_lines._quote_body(
            "he said “not the house”") == "not the house"

    def test_an_unquoted_line_is_taken_whole(self):
        assert remember_lines._quote_body("bring the ledger") == "bring the ledger"

    def test_nothing_is_survivable(self):
        assert remember_lines._quote_body(None) == ""


def test_no_budget_or_novelty_gate_was_added():
    """The conclusion, guarded. If someone later adds a cap on marks per beat
    or a novelty filter, this test should fail and make them re-run
    tools/remember_lines.py first -- because the numbers that were measured say
    a gate would throttle the highest-retrieval rows in the bank."""
    import inspect

    from persist import commit
    src = inspect.getsource(commit._marked_for_memory)
    for gate in ("MAX_REMEMBER", "remember_budget", "novelty"):
        assert gate not in src, gate
