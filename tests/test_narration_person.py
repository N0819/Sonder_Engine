"""Regression tests for grammatical-person detection: which person the
narrator renders the player character in (first/second/third), inferred
from how the player phrased their own input.

Covers two layers:
  - agents.common._detect_narration_person / _narration_person_counts:
    the per-turn evidence count, hardened against name/verb collisions and
    ambiguous object/possessive pronouns.
  - agents.narration._resolve_narration_person: the campaign-level resolver,
    whose hysteresis stops a single stray token from flipping an already
    established narration person.
"""

from __future__ import annotations

import time

import pytest

from agents.common import _detect_narration_person, _narration_person_counts
from agents.narration import _resolve_narration_person
from db import wget, wset


# ---- per-turn detection ------------------------------------------------

@pytest.mark.parametrize("raw, name, pronouns, expected", [
    # Clean, unambiguous cases.
    ("You push through the door.", "Alex", {"subj": "he"}, "second"),
    ("I push through the door.", "Alex", {"subj": "he"}, "first"),
    ("Alex opens the door. He steps inside.", "Alex", {"subj": "he"}, "third"),
    ("Grace steps into the light.", "Grace", {"subj": "she"}, "third"),
    # Pure imperative (the IF default): no person signal at all.
    ("Open the door and look under the bed.", "Alex", {"subj": "he"}, None),
    # First-person plural is recognised.
    ("We move north together.", "Alex", {"subj": "he"}, "first"),
])
def test_detect_clean_cases(raw, name, pronouns, expected):
    assert _detect_narration_person(raw, name, pronouns) == expected


def test_name_that_is_also_a_common_word_does_not_force_third():
    # "will" the auxiliary verb must not be read as the character named
    # "Will" -- otherwise ordinary first-person input scores a spurious
    # third-person hit and the true 'first' signal gets tied out to None.
    assert _detect_narration_person("I will open the door.", "Will",
                                    {"subj": "he"}) == "first"
    counts = _narration_person_counts("I will open the door.", "Will",
                                      {"subj": "he"})
    assert counts["third"] == 0
    assert counts["first"] == 1


def test_object_pronoun_for_someone_else_is_not_player_third_person():
    # The player narrates in first person and mentions another character as
    # "her"; that object pronoun must not be counted as the PLAYER being
    # narrated in third person -- even when the player's own pronoun set
    # happens to include "her".
    counts = _narration_person_counts(
        "I gave her the key and left.", "Alex",
        {"subj": "she", "obj": "her", "poss": "her"})
    assert counts["third"] == 0
    assert _detect_narration_person(
        "I gave her the key and left.", "Alex",
        {"subj": "she", "obj": "her", "poss": "her"}) == "first"


def test_duplicate_pronoun_values_are_not_double_counted():
    # obj and poss both "them": the single occurrence in the text must count
    # at most once, not once per dict entry that carries the same string.
    # (Here the player IS narrated in third person, so we expect exactly 1.)
    counts = _narration_person_counts(
        "They open the door.", "Robin",
        {"subj": "they", "obj": "them", "poss": "their"})
    assert counts["third"] == 1


def test_quoted_you_addressed_to_npc_is_ignored():
    # A "you" inside spoken dialogue addresses another character; only the
    # narrating frame ("I say") should count.
    assert _detect_narration_person('"You should go," I say to Rose.',
                                    "Alex", {"subj": "he"}) == "first"


# ---- campaign-level resolution + hysteresis ----------------------------

def _new_chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Test", "", time.time()))


def test_resolver_establishes_on_first_clear_signal(temp_db):
    cid = _new_chat(temp_db)
    assert wget(cid, "narration_person", None) is None
    got = _resolve_narration_person(cid, "I open the door.", "Alex",
                                    {"subj": "he"})
    assert got == "first"
    assert wget(cid, "narration_person", None) == "first"


def test_resolver_ambiguous_turn_keeps_established_person(temp_db):
    cid = _new_chat(temp_db)
    wset(cid, "narration_person", "first")
    # A bare imperative carries no signal; must not snap back to a default.
    got = _resolve_narration_person(cid, "Open the door.", "Alex",
                                    {"subj": "he"})
    assert got == "first"
    assert wget(cid, "narration_person", None) == "first"


def test_resolver_single_stray_token_does_not_flip_established_person(temp_db):
    # Campaign established as first person. One imperative that happens to
    # collide with the character's name ("Mark the map." for a player named
    # Mark) yields a bare third=1 majority -- not decisive enough to override
    # an established convention. This is the core anti-flakiness guard.
    cid = _new_chat(temp_db)
    wset(cid, "narration_person", "first")
    got = _resolve_narration_person(cid, "Mark the map, then rest.", "Mark",
                                    {"subj": "he"})
    assert got == "first"
    assert wget(cid, "narration_person", None) == "first"


def test_resolver_flips_on_decisive_signal(temp_db):
    # A genuine, sustained switch to third person (name + pronoun, lead >= 2)
    # SHOULD override the established first-person convention.
    cid = _new_chat(temp_db)
    wset(cid, "narration_person", "first")
    got = _resolve_narration_person(
        cid, "Alex crosses the room. He tries the far door.", "Alex",
        {"subj": "he"})
    assert got == "third"
    assert wget(cid, "narration_person", None) == "third"


def test_resolver_extra_persona_keys_are_independent(temp_db):
    # Additional human players each keep their own established person under a
    # distinct key, so one player's voice never bleeds into another's.
    cid = _new_chat(temp_db)
    _resolve_narration_person(cid, "I wait by the fire.", "Ada",
                              {"subj": "she"}, key="narration_person:extra:7")
    assert wget(cid, "narration_person:extra:7", None) == "first"
    assert wget(cid, "narration_person", None) is None


# ---- a story that could not get out of the wrong person ----------------
#
# Reported live: a chat narrated in first person that would not go back to
# second however many times it was rerolled. Three separate defects stacked,
# and no one of them alone would have produced it.


def test_an_unterminated_quote_is_still_dialogue():
    """THE necessary condition for the reported bug.

    The paired pattern needs a closing mark, so a quote that never closed left
    the speech in the text — and every `I` and `my` inside it voted on how the
    NARRATION should read. 11 of 2163 live player turns change verdict on this;
    one of them latched a whole story into first person.
    """
    counts = _narration_person_counts(
        '"Wait," You turn to face her. "I need my coat and I', "", {})
    assert counts["first"] == 0
    assert counts["second"] == 1


def test_a_doubled_opening_mark_does_not_desynchronise_the_line():
    """`""` made the paired pattern match an EMPTY span, after which every
    quote on the line paired with the wrong partner. Observed live."""
    counts = _narration_person_counts(
        '""Hello," you say. "I know," she says. You nod.', "", {})
    assert counts["first"] == 0
    assert counts["second"] == 2


def test_balanced_quotes_are_unaffected(temp_db):
    """The paired path was always right. This pins that closing the hole did
    not cost the case that already worked."""
    counts = _narration_person_counts(
        '"I\'ll go with you," she says as you step forward', "", {})
    assert counts["first"] == 0 and counts["second"] == 1


def test_a_genuinely_first_person_turn_still_reads_first_person():
    counts = _narration_person_counts(
        "I push the door open and my hand shakes on the latch", "", {})
    assert counts["first"] == 2 and counts["second"] == 0


def test_a_story_stuck_in_the_wrong_person_can_get_out_of_it(temp_db):
    """The end-to-end shape of the report: a chat narrating in first person
    that would not go back to second.

    What fixed it was the quote fold, NOT the hysteresis. Once an unterminated
    quote stops feeding the speech's `I` and `my` into the narration vote, the
    turn reads plainly as second person and the existing rule lets it through.
    Measured before assuming: with the fold in place, all three candidate
    hysteresis rules recover on the very next turn.
    """
    cid = _new_chat(temp_db)
    wset(cid, "narration_person", "first")
    got = _resolve_narration_person(
        cid, '"I can manage," you say, and you get the door open.', "", {})
    assert got == "second"


def test_the_lead_is_measured_against_the_person_actually_stored(temp_db):
    """The comparison was against the RUNNER-UP — whether the winner beat some
    third person nobody was arguing for — rather than against the incumbent.

    Measured over 2212 live player turns, fixing it costs no extra mid-story
    changes. Dropping the lead of 2 as well was tried and reverted: a single
    misparsed token is indistinguishable from unanimity by counts alone.
    """
    import inspect

    from agents import narration
    body = inspect.getsource(narration._resolve_narration_person)
    assert "top - stored_support >= 2" in body
    assert "top - runner >= 2" not in body


def test_a_stray_token_beside_real_evidence_still_does_not_flip(temp_db):
    """What the lead-of-2 rule was actually written to prevent, and what the
    new rule must keep preventing: the stored person still has support here,
    so one token on the other side is not enough."""
    cid = _new_chat(temp_db)
    wset(cid, "narration_person", "second")
    got = _resolve_narration_person(
        cid, "You open my letter and you read it.", "", {})
    assert got == "second"


def test_narration_person_is_not_preserved_across_a_restore():
    """It is DETECTED state, not a reader's dial.

    Every other key on `PRESERVED_SETTING_KEYS` is something the person at the
    keyboard can set; this one has no endpoint in `app.py` and no control in
    `static/`. Preserving it meant a single misdetection outlived the turn that
    caused it, the restore meant to undo it, and every reroll after — the one
    repair available to the player was the one thing that could not touch it.
    Observed live: a checkpoint holding `second` restored into a world still
    holding `first`.
    """
    import checkpoints

    assert "narration_person" not in checkpoints.PRESERVED_SETTING_KEYS


def test_it_has_no_dial_to_justify_preserving_it():
    """Guards the reasoning above rather than the line above. If narration
    person ever gains a real control, this fails and someone re-reads the
    argument instead of finding the bug again."""
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    surfaces = [root / "app.py"] + list((root / "static").rglob("*.js"))
    for path in surfaces:
        if path.exists():
            assert "narration_person" not in path.read_text(encoding="utf-8"), \
                "%s exposes narration_person; revisit preserving it" % path.name
