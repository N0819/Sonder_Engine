"""Regression tests for `repair_narrated_speech`.

A weak `director_interpret` can return the player's raw input as a single
speech element, narration and all. Perception injects speech texts verbatim
as dialogue, so whatever is left here is delivered to every hearer as words
the player spoke -- and because player prose is written in the second person,
the "you" in it lands on the LISTENER, who is told they said it.

The repair keeps a wholly unquoted line (the normal shape) untouched, and
must not gut an ordinary spoken line that happens to quote someone.
"""

from agents.common import (
    discard_unanchored_player_speech,
    repair_narrated_speech,
    repair_narrated_speech_elements,
)


# ---- the failure being repaired ------------------------------------------

def test_second_person_narration_is_stripped_to_the_spoken_words():
    raw = ('"Wait" You say it flatly, without turning around. '
           '"I am not going."')
    assert repair_narrated_speech(raw) == "Wait. I am not going."


def test_attribution_clause_between_quotes_is_stripped():
    assert repair_narrated_speech('"Stop," she said, "right there."') == (
        "Stop, right there.")


def test_repair_reaches_both_representations():
    out = {
        "sequence": [
            {"type": "speech",
             "text": '"Wait" You say it flatly. "I am not going."'},
            {"type": "action", "attempt": "turns away"},
        ],
        "speech": '"Wait" You say it flatly. "I am not going."',
    }
    changed = repair_narrated_speech_elements(out)

    assert out["sequence"][0]["text"] == "Wait. I am not going."
    assert out["speech"] == "Wait. I am not going."
    assert out["sequence"][1]["attempt"] == "turns away"  # actions untouched
    assert changed, "the repair must report what it changed, for the warning"


# ---- what must NOT be touched --------------------------------------------

def test_plain_unquoted_line_is_untouched():
    """The normal shape: interpret already extracted the words said."""
    line = "I am just having a bit of fun."
    assert repair_narrated_speech(line) is line


def test_line_that_is_only_its_quote_is_untouched():
    assert repair_narrated_speech('"I am not going."') == '"I am not going."'


def test_spoken_line_quoting_someone_else_survives_intact():
    """A speaker relaying another's words is not narration.

    This is why the attribution vocabulary excludes `tell`/`told`: the
    residue here carries no second-person pronoun and no say-verb, so the
    repair declines and the whole utterance survives.
    """
    line = 'He told me "get out" and I left.'
    assert repair_narrated_speech(line) is line


def test_short_residue_alone_does_not_trigger():
    """Trailing punctuation or a stray word is not a narration clause."""
    assert repair_narrated_speech('"I am not going." --') is not None
    assert repair_narrated_speech('"I am not going." --') == (
        '"I am not going." --')


def test_total_on_junk_input():
    for junk in (None, "", "   ", 17, {"text": "x"}):
        assert repair_narrated_speech(junk) is junk
    assert repair_narrated_speech_elements(None) == []
    assert repair_narrated_speech_elements({}) == []


def test_described_player_speech_cannot_be_expanded_into_exact_words():
    out = {
        "sequence": [
            {"type": "action", "attempt": "apply a dressing"},
            {"type": "speech", "text": "Watch for redness or fever."},
        ],
        "speech": "Watch for redness or fever.",
    }
    dropped = discard_unanchored_player_speech(
        out, "I apply a dressing and explain the infection warning signs.")

    assert dropped == ["Watch for redness or fever."]
    assert out["speech"] is None
    assert [event["type"] for event in out["sequence"]] == ["action"]


def test_player_speech_copied_from_input_survives_provenance_floor():
    out = {
        "sequence": [{"type": "speech", "text": "Hold still, please."}],
        "speech": "Hold still, please.",
    }
    assert discard_unanchored_player_speech(
        out, 'I say, "Hold still, please."') == []
    assert out["speech"] == "Hold still, please."
