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
