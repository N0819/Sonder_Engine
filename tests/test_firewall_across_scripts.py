"""The deterministic identity floor must hold in every script, not just English.

Each guard below was measured failing OPEN in Japanese while passing in
English, and failing open silently: "no match" and "nothing to redact" are the
same answer, so `leaked` came back empty and no warning fired. Per AGENTS.md a
leak is an engine failure, never a model's, so these are asserted as behaviour
in both languages rather than as English behaviour plus a Japanese smoke test.

The pairs are deliberately structural mirrors: the same event, the same
concealment, one sentence of it privileged, so a difference in outcome between
the two languages is a difference in the FLOOR, not in the prose.
"""

import re

import pytest

from language_runtime import current_language_id


@pytest.fixture(params=["en", "ja"])
def language(request):
    token = current_language_id.set(request.param)
    try:
        yield request.param
    finally:
        current_language_id.reset(token)


# --- the name boundary the other three guards are built on -----------------

@pytest.mark.parametrize("form, text, matches, why", [
    ("Hinami", "steps toward Hinami and takes her arm", True, "English"),
    ("Hinami", "Hinami's arm", True, "possessive"),
    ("Hinami", "Hinamis walked away", False, "not inside a longer word"),
    ("Reya", "Reyanne entered", False, "not a prefix of another name"),
    # The measured failure: Japanese particles are word characters, so a
    # \b-style boundary never fires and the name is never found.
    ("ヒナミ", "ヒナミに歩み寄り、その腕を取る", True, "CJK name + particle"),
    ("ヒナミ", "ヒナミは棚に向かう。", True, "CJK name + topic marker"),
    # Code-switching runs both ways and is decided per NAME, not per story.
    ("Hinami", "彼はHinamiに近づく", True, "Latin name in Japanese prose"),
])
def test_a_name_is_recognised_in_its_own_script(form, text, matches, why):
    from story.character_schema import name_boundary_regex

    assert bool(name_boundary_regex(form, re.IGNORECASE).search(text)) is matches, why


# --- identity scrubbing ----------------------------------------------------

def test_an_unrecognised_name_is_scrubbed_out_of_a_view(language):
    """The view-prose floor. A model that writes a stranger's canonical name
    walks straight past knows_identity unless this fires."""
    from agents.common import _scrub_unknown_identities

    text = ("steps toward Hinami and takes her arm" if language == "en"
            else "ヒナミに歩み寄り、その腕を取る")
    name = "Hinami" if language == "en" else "ヒナミ"
    scrubbed, leaked = _scrub_unknown_identities(
        text, allowed_forms=[],
        unknown_sources=[{"name": name, "appearance": "a tall figure",
                          "aliases": []}])
    assert name not in scrubbed
    assert leaked == [name], "a silent leak is how the original bug hid"


def test_a_recognised_name_survives_scrubbing_intact(language):
    """Over-matching is the safe direction, but not into a name the observer
    legitimately commands."""
    from agents.common import _scrub_unknown_identities

    if language == "en":
        text, allowed, unknown = "Reyanne watched Reya go", ["Reyanne"], "Reya"
    else:
        text, allowed, unknown = "レイヤは見た。レイも見た。", ["レイヤ"], "レイ"
    scrubbed, leaked = _scrub_unknown_identities(
        text, allowed_forms=allowed,
        unknown_sources=[{"name": unknown, "appearance": "a tall figure",
                          "aliases": []}])
    assert allowed[0] in scrubbed
    assert leaked == [unknown]


# --- concealment redaction -------------------------------------------------

def test_a_concealed_act_is_redacted_out_of_an_event(language):
    """_redact_concealed_from_event decides who may see an act at all. In
    Japanese it returned the secret sentence verbatim, because the sentence
    splitter wanted `[.!?]` plus a space and Japanese writes neither."""
    from agents.perception import _redact_concealed_from_event

    if language == "en":
        text = ("Mika crosses to the shelf. She slips a vial into her sleeve. "
                "The lamp gutters.")
        actor, secret, public = "Mika", "vial", "The lamp gutters."
    else:
        text = "ミカは棚に向かう。彼女は小瓶を袖に滑り込ませる。ランプが揺れる。"
        actor, secret, public = "ミカ", "小瓶", "ランプが揺れる。"

    out = _redact_concealed_from_event(text, [{"actor": actor}])
    assert secret not in out, "the concealed act reached a perceiver with no channel to it"
    assert actor not in out
    assert public in out, "redaction must subtract, not blank the whole event"


def test_a_pronoun_continuation_of_a_concealed_act_is_also_dropped(language):
    """The sentence after the concealed one continues it with a pronoun
    subject; keeping it hands over the same fact in different words."""
    from agents.perception import _redact_concealed_from_event

    if language == "en":
        text = "Mika opens the safe. She reads the code aloud. Rain hits the glass."
        actor, secret = "Mika", "code"
    else:
        text = "ミカは金庫を開ける。彼女はコードを読み上げる。雨が窓を打つ。"
        actor, secret = "ミカ", "コード"
    out = _redact_concealed_from_event(text, [{"actor": actor}])
    assert secret not in out


# --- muffled speech --------------------------------------------------------

def test_a_muffled_line_does_not_deliver_the_whole_utterance(language):
    """Fragment fidelity degraded by `.split()`, so a language without spaces
    produced one "word" -- the entire secret -- and passed the word cap."""
    from agents.common import _muffled_fragment

    line = ("I hid the vial behind the shelf and we move it tonight"
            if language == "en"
            else "棚の裏に隠した小瓶を今夜のうちに運び出さなければならない")
    fragment = _muffled_fragment(line)
    assert fragment != line
    assert len(fragment) < len(line)
    # Every chunk must be verbatim: _scrub_invented_dialogue validates them
    # against what was actually spoken and drops the line if one is stitched.
    # Split on the PACK's own ellipsis -- Japanese sets it as 「……」, so a
    # hardcoded "..." would find no boundaries and test nothing.
    from language_runtime import compositor_value
    ellipsis = str(compositor_value("muffle_join"))
    for chunk in (c.strip(" .…‥") for c in fragment.split(ellipsis)):
        if chunk:
            assert chunk in line, f"chunk {chunk!r} is not verbatim"


# --- perception cues -------------------------------------------------------

@pytest.mark.parametrize("en_text, ja_text, expected", [
    ("a dull ache in your chest", "胸に鈍い痛みが走る", "interoception"),
    ("you hear a voice", "声が聞こえる", "hearing"),
    ("the scent of smoke", "煙の匂いがする", "smell"),
    ("pressure against your shoulder", "肩に圧力を感じる", "touch"),
])
def test_a_percept_reaches_the_same_channel_in_both_languages(
        language, en_text, ja_text, expected):
    """`linguistics.json` had no agents.perception entry at all, so every
    Japanese percept fell to `mixed` with flat salience."""
    from agents.perception import _atom_channel

    assert _atom_channel(en_text if language == "en" else ja_text) == expected


def test_an_event_aimed_at_the_perceiver_is_recognised_as_self_directed(language):
    """_SELF_DIRECTED decides whether an observer is told an event landed on
    their own body or on somebody else's."""
    from agents.perception import _ling

    text = ("the hand closes around your wrist" if language == "en"
            else "手があなたの手首を掴む")
    assert _ling("_SELF_DIRECTED").search(text)


# --- the quoted-span regexes callers read by position ----------------------

def test_quoted_spans_survive_splitting(language):
    """_QUOTED_SPAN_RE is handed to re.split, which keeps only CAPTURED text.
    The Japanese pattern put 「」 outside the capture group, so every corner-
    bracketed line came back as None and was silently deleted from the view."""
    from agents.common import _ling

    text = ('Reya says "the code is in the safe" and turns.' if language == "en"
            else "レイヤは「秘密は金庫にある」と言う。")
    parts = _ling("_QUOTED_SPAN_RE").split(text)
    assert None not in parts
    assert "".join(parts) == text, "splitting must be lossless"


def test_speech_helpers_do_not_raise_on_a_quoted_line(language):
    """Three helpers read group(1)/group(2) positionally. On a Japanese quote
    those were None: AttributeError inside _declaration_units, which every
    turn reaches through _uncovered_declarations."""
    import agents.common as common
    import agents.director as director

    if language == "en":
        line, name = 'Hinami says "let us go". Then she opened the door.', "Hinami"
    else:
        line, name = "Hinamiは「行こう」と言った。そして扉を開けた。", "Hinami"
    director._declaration_units(line)
    common._self_second_person(line, [name])
    common._cap_repeated_quotes(line, line)
