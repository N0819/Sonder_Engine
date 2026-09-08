"""A86 (review 2026-09-07): a memory the mind has since re-read.

`record_dispute` deliberately leaves the event alone -- "I saw this" stays
true, and `content`, `gist`, `provenance` and `salience` are untouched --
because deception, disguise and plain misidentification change what a moment
MEANT, not that it happened. The consolidator was shown none of that: the row
it receives had no `disputed` field, so a window was summarised from the
reading the mind had already abandoned, and the corrected belief came back the
moment the individual rows aged out.

Two halves, and this file pins both. The payload half puts the character's own
later reading on the row as `now_reads`, absent (never blank) on a memory
nobody has re-read. The sheet half, landed 2026-09-08, is the sentence in the
`memory_consolidate` prompt that says what the field IS -- without it the key
reached the model unannounced, which is a field a reader may or may not honour
rather than an instruction.
"""

from __future__ import annotations

import pytest

from language_runtime import raw_card
# The sibling, not the `mind.memory` facade: `_consolidator_row` is private
# and the facade re-exports no private name, so there is no facade spelling of
# it. Reached through `getattr` because that is what this file does with the
# module -- it introspects it (the docstring assertion at the foot) as well as
# calling it, which is the exemption `tools/project_check.py` states.
from mind import memory_summaries
# The facade for the one this file only CALLS: `_with_reading` builds the
# live payload row and is reached the way every other caller reaches it.
from mind.memory import _with_reading

_consolidator_row = getattr(memory_summaries, "_consolidator_row")


class _StubClock:
    """`_with_reading` asks the clock for one thing, the `when` stamp; a
    disputed blob is not its business, so the test says what it depends on."""

    def of_memory(self, mem):
        return "just now"


def _row(**over):
    memory = {"id": 7, "turn_idx": 3, "category": "event",
              "provenance": "witnessed", "salience": 0.6, "confidence": 0.8,
              "gist": "The courier handed me a sealed tube.",
              "content": "A courier in a grey coat handed me a sealed tube.",
              "key_phrases": ["sealed tube"], "entities": ["courier"],
              "location": "Harbour Office", "emotional_context": "wary"}
    memory.update(over)
    return _consolidator_row(memory)


def test_a_reread_memory_carries_what_it_now_means():
    row = _row(disputed={"reading": "That was no courier -- it was Ilse in "
                                    "a borrowed coat.",
                         "turn_idx": 40})
    assert row["now_reads"] == ("That was no courier -- it was Ilse in a "
                                "borrowed coat.")
    # The EVENT is untouched: the re-reading changes the meaning of the
    # moment, never that it happened.
    assert row["gist"] == "The courier handed me a sealed tube."
    assert row["provenance"] == "witnessed"
    assert row["salience"] == 0.6


def test_a_memory_nobody_reread_carries_no_key():
    """Absent, not empty. A key that is there and blank on every row teaches
    the reader to skip it."""
    assert "now_reads" not in _row()
    assert "now_reads" not in _row(disputed=None)
    assert "now_reads" not in _row(disputed={})
    assert "now_reads" not in _row(disputed={"reading": "   "})
    assert "now_reads" not in _row(disputed="a bare string")


@pytest.mark.parametrize("lang", ["en", "ja"])
def test_the_consolidator_card_announces_the_field(lang):
    """The half that makes the payload an instruction. Stated as the class --
    a re-read memory is consolidated as what it NOW means, the earlier reading
    kept as something the character used to think -- so it holds for a face
    misrecognised, a lie later caught, and any later re-reading alike."""
    text = raw_card(lang)["prompts"]["memory_consolidate"]
    assert "now_reads" in text
    if lang == "en":
        assert "what the memory means to them NOW" in text
        assert "never as something that was the case" in text
    else:
        assert "読み直した記憶" in text
        assert "事実だったこととしては決して" in text


def test_the_live_payload_reads_a_disputed_blob_the_same_way():
    """The SIBLING site, and the class rather than the instance. Two
    functions project a memory's `disputed` blob -- this consolidator row and
    `memory_context._with_reading`, which builds the payload handed to a
    character on the turn itself -- and the shape check belongs to both. The
    live one has the stronger claim: a consolidation summary is
    reconstructible and a turn is not."""
    clock = _StubClock()
    mem = {"event_key": "k", "gist": "g", "content": "c",
           "disputed": "a bare string"}
    assert "i_now_read_this_differently" not in _with_reading(mem, clock)
    mem["disputed"] = {"reading": "It was Ilse in a borrowed coat."}
    assert _with_reading(mem, clock)["i_now_read_this_differently"] == \
        "It was Ilse in a borrowed coat."


def test_the_docstring_no_longer_calls_the_item_half_done():
    """The blocked wording was true while the sheet was silent and is not
    now; a stale "not yet proven" note is a status list that disagrees with
    the code beside it."""
    doc = _consolidator_row.__doc__ or ""
    assert "HALF DONE" not in doc
    assert "memory_consolidate" in doc
