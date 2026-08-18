"""What a character may call the player in their own private memory.

Three answers, and only one of them was right. Observed live in "Run!" (chat
54), The Doctor's memory bank at turn 0:

    The Doctor knows the player was being chased by a Dalek and narrowly
    escaped death.
    The Doctor is intrigued by the player's appearance, specifically their
    six tails and fox ears...
    ...the player's unique traits make them a potential candidate.

`{{PLAYER}}` appears in none of them: the model wrote the literal English
words instead of the token, so `sub()` -- which replaces only the exact token
-- had nothing to replace, and the engine's own out-of-fiction word for the
protagonist went into a fictional mind at salience 1.0.

An earlier run of the same card had the opposite failure: the token WAS
present, `sub()` resolved it to "Hinami", and the character began the story
knowing a name the launch had explicitly said he did not know
(`already_known=False`).

The rule these tests hold:

* checkbox ticked -> the persona's name is correct and expected;
* checkbox unticked -> a DESCRIPTION of a stranger, from the same
  `_unknown_actor_label` every perception path uses;
* never, in either case, "the player".
"""
from __future__ import annotations

import pytest

from story.greetings import _substitute_player_slot, player_handle_for


PERSONA = {
    "identity": {"name": "Hinami"},
    "embodiment": {"visible": {"summary": (
        "A beautiful young woman appearing in her early twenties, with "
        "golden fox ears and six golden tails."
    )}},
}

# The three seeds from the live launch, verbatim.
LIVE_SEEDS = [
    "The Doctor knows the player was being chased by a Dalek and narrowly "
    "escaped death.",
    "The Doctor is intrigued by the player's appearance, specifically their "
    "six tails and fox ears, which are unusual and fascinating to him.",
    "The Doctor is always on the lookout for new companions, and the "
    "player's unique traits make them a potential candidate.",
]


# --- the handle ------------------------------------------------------------

def test_a_known_player_is_called_by_name():
    assert player_handle_for(PERSONA, already_known=True) == "Hinami"


def test_an_unknown_player_is_called_by_description():
    handle = player_handle_for(PERSONA, already_known=False)
    assert handle == "the beautiful young woman"


def test_the_description_never_leaks_the_name():
    """`_unknown_actor_label` strips the actor's own name tokens, because
    appearance summaries routinely lead with the canonical name."""
    named = dict(PERSONA)
    named["embodiment"] = {"visible": {"summary":
        "Hinami, a beautiful young woman with golden fox ears."}}
    handle = player_handle_for(named, already_known=False)
    assert "hinami" not in handle.casefold()
    assert handle.startswith("the ")


# --- the substitution ------------------------------------------------------

@pytest.mark.parametrize("seed", LIVE_SEEDS)
@pytest.mark.parametrize("known", [True, False])
def test_no_seed_ever_says_the_player(seed, known):
    out = _substitute_player_slot(
        seed, player_handle_for(PERSONA, already_known=known))
    assert "player" not in out.casefold(), out


@pytest.mark.parametrize("seed", LIVE_SEEDS)
def test_an_unknown_player_is_not_named_in_any_seed(seed):
    """The `already_known=False` guarantee, which the old `sub()` defeated by
    resolving the token to the persona's name regardless."""
    out = _substitute_player_slot(
        seed, player_handle_for(PERSONA, already_known=False))
    assert "hinami" not in out.casefold(), out
    assert "the beautiful young woman" in out


def test_a_known_player_is_named_in_seeds():
    out = _substitute_player_slot(
        LIVE_SEEDS[0], player_handle_for(PERSONA, already_known=True))
    assert out == ("The Doctor knows Hinami was being chased by a Dalek and "
                   "narrowly escaped death.")


def test_the_token_is_still_substituted():
    """The path that already worked must keep working -- this is a superset
    of `sub()`, not a replacement for a different job."""
    out = _substitute_player_slot(
        "I saw {{PLAYER}} run.", player_handle_for(PERSONA, already_known=True))
    assert out == "I saw Hinami run."


def test_possessives_survive_the_swap():
    # Capitalised because it opens the string, which for a seed is a sentence.
    assert _substitute_player_slot("the player's ears", "the fox-eared woman") \
        == "The fox-eared woman's ears"
    assert _substitute_player_slot("he saw the player's ears", "the fox-eared woman") \
        == "he saw the fox-eared woman's ears"
    assert _substitute_player_slot("{{PLAYER}}'s ears", "Hinami") \
        == "Hinami's ears"


def test_a_sentence_initial_description_is_capitalised():
    """These strings are read as prose in a memory panel. A description handle
    is lower-case by construction, so it has to be lifted where it lands
    first in a sentence."""
    out = _substitute_player_slot(
        "The player ran. The player's ears were flat.", "the fox-eared woman")
    assert out == ("The fox-eared woman ran. The fox-eared woman's ears were "
                   "flat.")


def test_an_in_fiction_player_is_left_alone():
    """The match is anchored on a leading article or the token, so a musician
    keeps their job. This is why it is a regex and not a bare word swap."""
    for text in ("A lute player sat in the corner.",
                 "The harp player's hands were bandaged.",
                 "Two players of the old game remained."):
        assert _substitute_player_slot(text, "the stranger") == text


def test_user_and_pc_spellings_of_the_token():
    assert _substitute_player_slot("{{user}} waited.", "Hinami") == "Hinami waited."
    assert _substitute_player_slot("{{ PLAYER }} waited.", "Hinami") == "Hinami waited."


def test_empty_and_missing_content_are_safe():
    assert _substitute_player_slot("", "Hinami") == ""
    assert _substitute_player_slot(None, "Hinami") == ""


# --- the fallback when there is no appearance to describe ------------------

def test_a_persona_with_no_appearance_still_never_says_player():
    bare = {"identity": {"name": "Hinami"}}
    handle = player_handle_for(bare, already_known=False)
    assert "player" not in handle.casefold()
    assert "hinami" not in handle.casefold()
    out = _substitute_player_slot(LIVE_SEEDS[0], handle)
    assert "player" not in out.casefold()
