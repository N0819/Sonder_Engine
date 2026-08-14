"""Regression tests for V2 (enterprise_d_v3 findings): stripping the player's
echoed quote must not leave a dangling attributive colon.

Live, v3 t7: the narrator wrote "...and when I speak again it's quieter, almost
gentle: <player quote>. Vorne swallows once...". The PLAYER ECHO RULE correctly
removes the player's own quote (the UI already shows what they typed), but the
colon that introduced it was left dangling straight into the next sentence.

The heal keeps the lead-in text and converts only the orphaned colon to a full
stop -- it never removes narration, and it stays off a legitimate non-speech
colon (a list, a ratio, a time).
"""

from __future__ import annotations

from agents.common import _strip_player_echo


def test_dangling_colon_becomes_a_full_stop():
    prose = ('I turn back to face Vorne, and when I speak again it is quieter, '
             'almost gentle: "You do not have to say it kindly." Vorne swallows.')
    out = _strip_player_echo(prose, ["You do not have to say it kindly."])
    assert ":" not in out
    assert "almost gentle. Vorne swallows." in out
    # The lead-in narration is preserved, not eaten.
    assert out.startswith("I turn back to face Vorne")


def test_orphaned_period_after_colon_is_absorbed():
    prose = 'She adds, softer now: "Please." He looks away.'
    out = _strip_player_echo(prose, ["Please."])
    assert ":" not in out and '"Please."' not in out
    assert "softer now. He looks away." in out


def test_a_list_colon_is_never_touched():
    prose = "She lists the supplies: water, a kit, and rope. He nods."
    assert _strip_player_echo(prose, ["irrelevant"]) == prose


def test_a_time_or_ratio_colon_is_never_touched():
    assert _strip_player_echo("The clock reads 4:30. We move.", ["x"]) == \
        "The clock reads 4:30. We move."


def test_a_colon_with_content_after_it_is_left_alone():
    """Only a colon with nothing (or a new sentence) after it is dangling; one
    that still introduces text is doing its job."""
    prose = "He says the only thing that matters: the ship is dying."
    assert _strip_player_echo(prose, ["nothing declared"]) == prose


def test_noop_when_nothing_is_stripped():
    prose = "The bridge hums. Vorne watches the Array."
    assert _strip_player_echo(prose, []) == prose


# ---- V4: the dangling-verb heal must not corrupt a surviving NPC attribution ----
#
# Live, Doctor Who run t7: a beat that stripped a player echo ALSO ran the
# global dangling-speech-verb heal, which fired on the Doctor's own attribution
# "he says, quiet and gentle, 'Ellie'" -> "he says it., quiet and gentle,". The
# heal must fire only at a genuine sentence end, not on a comma that continues
# the attribution around a quote that survived.

def test_surviving_npc_attribution_is_not_healed():
    prose = ('I say, "Tell me that is good." Then he says, quiet and gentle, '
             '"Ellie." He steps back.')
    out = _strip_player_echo(prose, ["Tell me that is good."])
    assert "says it." not in out
    assert 'he says, quiet and gentle, "Ellie."' in out


def test_a_genuinely_dangling_verb_at_sentence_end_still_heals():
    assert _strip_player_echo('I only whisper, "no."', ["no."]) == "I only whisper it."


def test_unquoted_object_after_a_speech_verb_is_never_eaten():
    """'he tells Karen the truth' -- 'tells' is followed by a proper-noun
    object, not a dangling end. Healing on a following capital would destroy it,
    so the heal is sentence-end only."""
    prose = 'I say, "Go." He tells Karen the truth. She nods.'
    out = _strip_player_echo(prose, ["Go."])
    assert "tells Karen the truth" in out


def test_the_verb_healer_and_the_colon_healer_share_one_vocabulary():
    """They drifted, and the drift reached the page. The colon healer knew
    `add`, `speak`, `voice`, `continue` and `offer`; the verb healer knew none
    of them -- so a player quote stripped after "as you add," left

        You let the wry amusement show as you add,

    standing on the page with nothing after it (live, chat 72). A dangling
    verb and a dangling colon are the same wound from the same cut; there is
    no reason for them to disagree about what counts as speech."""
    from agents.common import _DANGLING_SPEECH_VERB_RE, _SPEECH_CUE
    for verb in ("add", "adds", "added", "speak", "spoke", "voiced",
                 "continue", "continued", "offer", "offered"):
        assert verb in _SPEECH_CUE
        assert _DANGLING_SPEECH_VERB_RE.search("as you %s," % verb), verb


def test_the_verbs_the_colon_healer_never_had_are_kept():
    """`call` and `shout` were only ever in the verb healer. Merging the two
    lists must not quietly drop them."""
    from agents.common import _DANGLING_SPEECH_VERB_RE
    for verb in ("call", "called", "shout", "shouted", "says", "asked"):
        assert _DANGLING_SPEECH_VERB_RE.search("she %s," % verb), verb


def test_healing_never_welds_two_paragraphs():
    """The trailing-whitespace class is `[^\\S\\n]*` for a reason: a dangling
    verb at the end of a paragraph must heal in place, not swallow the break
    after it."""
    from agents.common import _DANGLING_SPEECH_VERB_RE
    healed = _DANGLING_SPEECH_VERB_RE.sub(
        lambda m: "%s it." % m.group(1), "you add,\n\nThe next paragraph.")
    assert "\n\n" in healed
