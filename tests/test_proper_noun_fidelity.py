"""A one-word name is a name, and the check could not see one.

`_check_narrator_fidelity` warns when a proper noun the view names never
reaches the narrator's prose. It found those nouns by regex --
`[A-Z][a-z]+(?:\\s+…[A-Z][a-z]+)+`, one-or-more -- so a name had to be at
least two capitalised words to be seen at all. "Hinami", "Tamamo", "Elyndra",
"Vorne": the commonest cast shape in this engine's own stored stories, and the
warning was structurally unavailable for every one of them.

Two questions, and the regex answered both by guessing:

  * WHAT IS A NAME. The engine already knows -- the cast roster rides the
    narrator payload as `cast_pronouns`. Guessing from capitalisation is what
    made the answer depend on how many words somebody's name happens to have.

  * WHAT COUNTS AS PRESENT. Prose refers to a person by pronoun after the
    first mention, which is ordinary English rather than a dropped body; the
    multi-word arm gets that tolerance free from its surname rule ("Voss" for
    "Elyra Voss") and a one-word name has no shorter form to fall back on.
    Measured over 2,277 stored beats carrying both a view and prose: the bare
    rule fires on 29 of 217 view-named single-token cast members, and 26 of
    those are prose rendering the person in pronouns. With the pronoun
    tolerance it fires 3 times.

The warning is diagnostic, not enforceable (`_ENFORCEABLE_PREFIXES` does not
carry this prefix), so a firing costs a note rather than a rewrite -- which is
the only reason a 1.4% rule is worth having at all.
"""

from __future__ import annotations

from agents.common import _check_narrator_fidelity


PRONOUNS = {"Elyndra": {"subject": "she", "object": "her",
                        "possessive": "her"}}


def _warnings(prose, view, cast_pronouns=PRONOUNS):
    return [w for w in _check_narrator_fidelity(
        {"prose": prose}, view, cast_pronouns=cast_pronouns)
        if w.startswith("Proper noun from view missing")]


def test_a_one_word_cast_name_the_prose_dropped_is_reported():
    assert _warnings(
        "The hearth pops. Smoke curls along the beams and nothing moves.",
        "Elyndra sets the kettle down beside the hearth.")


def test_a_one_word_cast_name_the_prose_kept_is_not():
    assert not _warnings(
        "Elyndra sets the kettle down. The hearth pops.",
        "Elyndra sets the kettle down beside the hearth.")


def test_pronoun_prose_is_not_a_dropped_body():
    """The measured false positive: 26 of the bare rule's 29 firings."""
    assert not _warnings(
        "She sets the kettle down, and the hearth pops beside her.",
        "Elyndra sets the kettle down beside the hearth.")


def test_a_name_the_view_never_said_is_not_checked():
    """The check is about what the VIEW carried, never about the roster: a
    cast member in another room is not missing from this beat's prose."""
    assert not _warnings(
        "The hearth pops and nothing moves.",
        "You are alone in the kitchen.")


def test_a_multi_word_name_is_checked_from_the_roster_not_from_capitals():
    """The rule that replaced the capitalisation arm (2026-09-06). A name is
    whoever the ROSTER says is here; each part of it answers for the whole,
    which is the surname tolerance the old arm had.

    The arm this replaces asked `[A-Z][a-z]+( [A-Z][a-z]+)+` of the view and
    required the prose to say whatever came back. Measured over the owner's
    3,770 stored beats: it fired on 1,577 of them (41.8%), 2,141 times, and
    what it caught by volume was ROOM NAMES the narrator never had to utter
    -- `Private Session Room` 595, `Reception Room` 465, `Ten Forward` 108 --
    and phrases that are not names at all: `Mmmm It`, `So Uhm`, `East Asian`.
    """
    roster = {"Elyra Voss": {"subject": "she", "object": "her",
                             "possessive": "her"}}
    assert _warnings(
        "The room is quiet.",
        "Elyra Voss sets the kettle down.", cast_pronouns=roster)
    assert not _warnings(
        "Voss sets the kettle down.",
        "Elyra Voss sets the kettle down.", cast_pronouns=roster)
    assert not _warnings(
        "She sets the kettle down.",
        "Elyra Voss sets the kettle down.", cast_pronouns=roster)


def test_a_capitalised_phrase_that_is_not_on_the_roster_is_not_a_name():
    """A room, a rank, a title and a stray capitalised phrase are not people,
    and the page owes them nothing. `Reception Room` alone was 465 of the
    deleted arm's firings."""
    assert not _warnings(
        "The room is quiet and nothing moves.",
        "You are in the Private Session Room, off the Reception Room.",
        cast_pronouns={})


def test_no_roster_is_the_old_behaviour_exactly():
    """The narrator payload builds `cast_pronouns` from sheets that declare
    pronouns, so an undeclared cast member contributes nothing here rather
    than becoming a name with no tolerance attached."""
    assert not _warnings(
        "The hearth pops.",
        "Elyndra sets the kettle down.", cast_pronouns=None)
