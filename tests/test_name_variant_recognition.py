"""Regression tests for V3 (enterprise_d_v3 findings): a known person named by a
rank/title variant must not be anonymized.

Live, v3 t5 and t11: a background presence voiced as "Commander Riker" rendered
as "the unfamiliar person" in the player's view, though the player recognized
"William T. Riker". Perception's identity scrub compared names by exact string,
so the rank variant missed the recognized set. This is the name-variant half of
backlog P7.

The information barrier is the whole point of this engine, so the recognition
is deliberately tight: a variant is recognized ONLY when every one of its
significant tokens is contained in a single known name. The tests that matter
most here are the ones asserting a STRANGER is still anonymized.
"""

from __future__ import annotations

from agents.perception import _recognizes, _significant_name_tokens

KNOWN = {"Captain Picard", "Dr. Vorne", "William T. Riker",
         "Dr. Beverly Crusher", "Commander Vale"}


def test_rank_variant_of_a_known_person_is_recognized():
    assert _recognizes("Commander Riker", KNOWN)
    assert _recognizes("Cmdr. Riker", KNOWN)
    assert _recognizes("Ensign Riker", KNOWN)


def test_known_first_name_alone_is_recognized():
    assert _recognizes("Beverly", KNOWN)


def test_exact_name_is_recognized():
    assert _recognizes("Dr. Vorne", KNOWN)


# ---- the barrier: these MUST stay anonymized ----

def test_a_true_stranger_is_not_recognized():
    assert not _recognizes("Commander Sato", KNOWN)
    assert not _recognizes("the unfamiliar person", KNOWN)
    assert not _recognizes("a tall officer", KNOWN)


def test_a_same_surname_stranger_is_not_recognized():
    """'Thomas Riker' shares a surname with a known person but is a different
    person -- 'Thomas' is not in any known name, so it must not resolve."""
    assert not _recognizes("Thomas Riker", KNOWN)


def test_partial_overlap_is_not_enough():
    """'Jean-Luc Vorne' shares 'Vorne' with Dr. Vorne but adds unknown tokens,
    so it is not the known person."""
    assert not _recognizes("Jean-Luc Vorne", KNOWN)


def test_empty_and_titles_only_never_recognize():
    assert not _recognizes("", KNOWN)
    assert not _recognizes("the Commander", KNOWN)  # only title/stopword tokens
    assert not _recognizes("Riker", set())


def test_significant_tokens_drop_titles_and_initials():
    assert _significant_name_tokens("Commander Riker") == {"riker"}
    assert _significant_name_tokens("William T. Riker") == {"william", "riker"}
    assert _significant_name_tokens("Dr. Beverly Crusher") == {"beverly", "crusher"}
    assert _significant_name_tokens("the unfamiliar person") == {"unfamiliar",
                                                                 "person"}
