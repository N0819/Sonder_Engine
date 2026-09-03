"""The six specialist core sheets are one text with six headers.

`language_packs/<id>/cards/system_prompts/specialists/<hand>/core.txt` is
maintained as six files. Only the first two paragraphs (three for spatial,
which carries the movement backstop note) are about the hand that reads them;
everything after that is the shared contract every specialist answers under --
how to read payload.source, what a referent may be, how to answer numbered
events, where to forward one that is not yours.

Six copies of one text is a copy-paste surface, and it has already failed as
one. Both defects repaired on 2026-09-01 were present IDENTICALLY in all six
sheets, in both packs: the WHEN AN EVENT IS NOT YOURS block spliced into the
middle of the sentence that closes ANSWER THE NUMBERED EVENTS (leaving the
word "events." orphaned at the head of the next paragraph), and body's own
three channels -- overlays, conditions, vitals -- handed to five hands that
have no block for any of them as the only illustration of what "the closest
channel you own" means. Neither was a divergence between the sheets; both were
an edit made once and pasted six times, which is exactly what no existing test
could see.

These tests pin the shared text so the NEXT such edit costs one failure
instead of six pastes. They deliberately do not merge the files: the en
paragraphs are byte-identical and a `{{fragment:...}}` would collapse them,
but the ja renderings of those same paragraphs are six independent
translations (pairwise similarity 0.70-0.93, never 1.0), so one fragment would
impose one hand's Japanese on the other five. So en is pinned by equality and
ja by the structure equality cannot reach.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from agents.director import SPECIALISTS


ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("en", "ja")
HANDS = ("body", "social", "contact", "objects", "spatial")
#: How many trailing paragraphs are the shared contract rather than the hand's
#: own preamble. 8 of 10 (spatial has one extra preamble paragraph, the
#: movement backstop, so 8 of 11).
SHARED_TAIL = 8


def _core(language: str, hand: str) -> str:
    return (ROOT / "language_packs" / language / "cards" / "system_prompts"
            / "specialists" / hand / "core.txt").read_text(encoding="utf-8")


def _paragraphs(text: str) -> list[str]:
    return [p for p in text.split("\n\n") if p.strip()]


def test_the_roster_this_file_pins_is_the_engines_roster():
    """If a seventh hand is registered, these tests must be told about it."""
    assert set(HANDS) == set(SPECIALISTS)


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_core_carries_the_shared_contract(language):
    for hand in HANDS:
        paragraphs = _paragraphs(_core(language, hand))
        assert len(paragraphs) >= SHARED_TAIL + 2, (
            f"{language}/{hand}: {len(paragraphs)} paragraphs, too few to "
            "hold a preamble plus the shared contract")


def test_the_english_cores_agree_word_for_word():
    """The load-bearing one: en is six copies, so it must be six IDENTICAL
    copies. A fix applied to one sheet and not the other five fails here."""
    reference = _paragraphs(_core("en", "body"))[-SHARED_TAIL:]
    for hand in HANDS:
        shared = _paragraphs(_core("en", hand))[-SHARED_TAIL:]
        first = next((i for i, (a, b) in enumerate(zip(shared, reference))
                      if a != b), None)
        assert shared == reference, (
            f"en/{hand} diverges from en/body in the shared contract "
            f"(first differing paragraph: {first}, counting from the start "
            f"of the shared tail of {SHARED_TAIL}). The shared text is "
            "maintained as six copies: an edit to one is an edit to all six.")


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_forwarding_note_publishes_the_hand_names_verbatim(language):
    """The roster of hands is the value vocabulary of `reroute_to`, and it is
    checked by identity: `target in SPECIALISTS` in
    `agents/director_fanout.py` (the hand's own verdict) and in
    `agents/director_reconcile.py` (the routing decision). A translated or
    misspelt row is an address the engine silently drops, and routing falls
    back to the category map that just mis-sent the event -- the re-ask the
    block exists to prevent. Measured 2026-09-01: ja/body had translated
    three of the six rows and ja/objects all six, so on the Japanese pack the
    objects hand could not address anyone at all.
    """
    for hand in HANDS:
        text = _core(language, hand)
        for name in SPECIALISTS:
            assert re.search(rf"^  {name} +-- ", text, re.M), (
                f"{language}/{hand} does not publish '{name}' as a "
                "reroute_to value; an address the engine cannot match is an "
                "address it drops")


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_forwarding_block_starts_its_own_paragraph(language):
    """The 2026-09-01 splice, pinned in the form that survives translation.

    The en test above catches a re-splice by equality only if it happens to
    ONE sheet; a paste into all six would pass it. This asks the structural
    question instead: the omit rule and the forwarding note are two
    paragraphs, and neither may open inside the other's sentence.
    """
    opener = ("WHEN AN EVENT IS NOT YOURS" if language == "en"
              else "イベントがあなたの")
    for hand in HANDS:
        paragraphs = _paragraphs(_core(language, hand))
        starts = [p for p in paragraphs if p.startswith(opener)]
        assert len(starts) == 1, (
            f"{language}/{hand}: the forwarding note must begin exactly one "
            f"paragraph (found {len(starts)})")
        mid = [p for p in paragraphs
               if opener in p and not p.startswith(opener)]
        assert not mid, (
            f"{language}/{hand}: the forwarding note is spliced into the "
            "middle of another paragraph")


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_omit_rule_kept_its_object(language):
    """The other half of the splice: the sentence it cut in half.

    'Omit resolved_events entirely when you were given no numbered events.'
    lost its last word to the splice in en, and in ja -- translated from the
    already-spliced English -- lost it before the sentence was ever written.
    A rule whose object is missing is a rule about nothing, and the orphan
    ('events.', 'イベント。') read as the opening of the paragraph after it.
    """
    needle = ("no numbered events." if language == "en" else "番号付きイベント")
    orphan = re.compile(r"^(events|イベント(です)?)[.。]")
    for hand in HANDS:
        paragraphs = _paragraphs(_core(language, hand))
        assert any(needle in p for p in paragraphs), (
            f"{language}/{hand}: the omit rule has lost its object")
        stranded = [p[:24] for p in paragraphs if orphan.match(p)]
        assert not stranded, (
            f"{language}/{hand}: a paragraph opens on the orphaned object of "
            f"another paragraph's sentence: {stranded}")


#: Channel stems the shared contract may say anyway, with the reason. The
#: payload's room INDEX is what a subject is named from -- every hand gets one
#: and no hand owns it -- so it is not the `rooms` channel wearing the same
#: word. Anything else on this list should be argued for in the same commit.
STEM_EXEMPT = {"room"}


def _channel_stems() -> set[str]:
    """`SPECIALISTS` is a closed set the engine owns, so it can be enumerated
    -- the case CLAUDE.md exempts from its no-word-lists rule."""
    return {c[:-1] if c.endswith("s") and not c.endswith("ss") else c
            for spec in SPECIALISTS.values() for c in spec["channels"]}


def test_no_core_illustrates_the_closest_channel_with_one_hands_channels():
    """The second 2026-09-01 defect, stated as the rule it broke.

    'the closest channel you own' was illustrated with body's own three --
    'a visible bodily manifestation onto the surface it marks, an impairment
    as a condition, a spent reserve as a vital' -- in all six sheets. A hand
    cannot encode into a channel it was given no block for, so five sheets
    taught the rule with the one example that contradicted it. The general
    form, which is what this asserts: the core is read by every hand, so it
    may name NO hand's channel; the channel blocks appended after it are
    where a channel is named and the only place a hand is told it owns one.

    Singular as well as plural, because that is the form an example takes:
    on the pre-fix text this catches 'condition' and 'vital' (not 'overlay',
    which was spelt out in prose) -- two of three is a failure. English only:
    the ja cores carry these ideas as Japanese prose, so a token scan there
    would prove nothing and quietly pass.
    """
    stems = sorted(_channel_stems() - STEM_EXEMPT)
    for hand in HANDS:
        shared = "\n\n".join(_paragraphs(_core("en", hand))[-SHARED_TAIL:])
        named = [s for s in stems if re.search(rf"\b{s}s?\b", shared)]
        assert not named, (
            f"en/{hand}: the shared contract names the channel(s) {named}, "
            "which the other hands have no block for. State the class the "
            "channels are instances of, or move the sentence into the "
            "channel's own chunk.")
