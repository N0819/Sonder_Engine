"""Every recognizer in `agents/common.py` answers in the story's language.

`_ling(...)` resolves 61 distinct pack keys in that file, and eight guards were
missed by the extraction and kept their English literals. All eight run on
every story regardless of language, so in a non-English story each was simply
inert -- not wrong-looking, not warned about, just never firing.

`_requires_director_resolution` is the consequential one: it is the interaction
loop's commonest early exit and it ENDS THE BEAT, so a Japanese story's
conflict-verb backstop was dead and the loop's only bound was `commitment`.

Owner decision 2: route through the packs AND translate Japanese in the same
commit, so the `ja` pack's `"story": true` becomes true rather than better
organised.
"""

from __future__ import annotations

import pytest

from language_runtime import language_scope, linguistic

#: The eight sites, by the pack key each now reads. `articles` lives in the
#: compositor card because that is where the compositor BUILDS labels from it.
ROUTED = [
    "_CONFLICT_VERBS",
    "_LEADING_SUBJECT_PRONOUNS",
    "_VISUAL_CONTRADICTION_RES",
    "_PARTIAL_QUOTE_PREFIXES",
    "_GENERIC_ROOM_WORDS",
    "_PLACEMENT_PHRASE",
    "_PORTAL_STATE",
    "_PRONOUN_GROUPS",
]


def _has_japanese(value):
    if isinstance(value, str):
        return any(ord(ch) > 0x2E80 for ch in value)
    if isinstance(value, dict):
        return any(_has_japanese(v) for v in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_has_japanese(v) for v in value)
    return _has_japanese(getattr(value, "pattern", ""))


@pytest.mark.parametrize("name", ROUTED)
def test_the_japanese_pack_answers_in_japanese(name):
    """A key that exists in both packs but holds the same English in each is
    the failure this row is about, one indirection later."""
    assert _has_japanese(linguistic("agents.common", name, "ja")), name


def test_a_conflict_verb_ends_a_japanese_beat_too():
    from agents.common import _requires_director_resolution

    declaration = {"sequence": [{"type": "action", "attempt": "衛兵を掴む"}]}
    with language_scope("ja"):
        assert _requires_director_resolution(declaration)
    # English is unchanged, and an ordinary act still does not end the beat.
    assert _requires_director_resolution(
        {"sequence": [{"type": "action", "attempt": "grab the guard"}]})
    assert not _requires_director_resolution(
        {"sequence": [{"type": "action", "attempt": "look at the map"}]})


def test_a_portal_contradiction_is_caught_in_japanese():
    from agents.common import _check_portal_fidelity

    with language_scope("ja"):
        warnings = _check_portal_fidelity(
            "開いた鉄の扉の向こうに廊下が伸びている。", {"鉄の扉": "shut"})
    assert warnings, "a door committed shut, narrated open, in Japanese"
    with language_scope("ja"):
        assert not _check_portal_fidelity(
            "開いた鉄の扉の向こうに廊下が伸びている。", {"鉄の扉": "open"})


def test_a_language_without_articles_keeps_its_descriptor_whole():
    """`_actor_reference_patterns` stripped a leading `the`/`a`/`an` from a
    descriptor label. The pack states its own article list, and a language with
    none supplies an empty one rather than having three English words applied
    to it."""
    from agents.common import _actor_reference_patterns

    assert _actor_reference_patterns("the unfamiliar woman")[0].search(
        "the unfamiliar woman turns")
    with language_scope("ja"):
        patterns = _actor_reference_patterns("見知らぬ女")
    assert patterns and patterns[0].search("見知らぬ女が振り向く")


#: "What counts as a quoted span" was answered eighteen times in one module
#: whose central job is quote fidelity: eight inline, in three spellings that
#: disagreed about whether a span may cross a nested opening curly quote, and
#: ten more in the pack. Every inline copy was invisible to a language pack.
QUOTE_KEYS = ["_NARRATION_QUOTE_RE", "_VIEW_QUOTE_BODY_RE",
              "_QUOTE_PAIRS", "_QUOTE_CHARS"]


@pytest.mark.parametrize("name", QUOTE_KEYS)
def test_the_quote_vocabulary_is_the_packs(name):
    assert _has_japanese(linguistic("agents.common", name, "ja")), name


def test_a_japanese_line_is_a_quoted_span():
    """Corner brackets mark speech in Japanese. Eight inline patterns knew
    only the straight and curly double quote, so for a Japanese story the
    protected-quote list came back empty and the echo strip ran unprotected."""
    from agents.common import _protected_view_quotes

    with language_scope("ja"):
        quotes = _protected_view_quotes("ヒナミは「もう遅い」と言った。")
    assert quotes == ["もう遅い"], quotes


def test_the_players_own_japanese_line_is_recognised_in_its_quotes():
    from agents.common import _strip_player_echo

    with language_scope("ja"):
        out = _strip_player_echo("あなたは「行こう」と言った。", ["行こう"])
    assert "行こう" not in out, out


def test_pronoun_fidelity_fires_for_a_name_not_written_in_latin_letters():
    """The `_pronoun_to_group` fix made the pronoun MAP per-story so the
    Japanese pack's 彼/彼女/彼ら groups would be live. The name tokenizer three
    lines into the consumer stayed `[A-Za-z']+`, so `token_owner` came back
    empty and the guard returned [] before consulting a pronoun at all -- the
    guard was still dead in the language it was revived for.

    MEASURED BEFORE ENFORCING, because this warning's prefix is enforceable
    and a false positive buys a full narrator rewrite: replayed over every
    stored narrator variant in the owner's live database (2,350 with prose,
    69,589 clauses), 0 clauses tokenise differently under `_name_tokens`.
    English is unchanged by construction; the whole of the new exposure is in
    scripts where the guard returns nothing at all today.
    """
    from agents.common import _check_pronoun_fidelity

    SHE = {"subject": "she", "object": "her",
           "possessive": "her"}

    latin = _check_pronoun_fidelity(
        "Hinami Sato lifts his hand.", {"Hinami Sato": SHE})
    assert latin and "his" in latin[0]

    with language_scope("ja"):
        mixed = _check_pronoun_fidelity(
            "佐藤ヒナミ lifts his hand.", {"佐藤ヒナミ": SHE})
        native = _check_pronoun_fidelity(
            "佐藤ヒナミは彼の手を上げた。", {"佐藤ヒナミ": SHE})
    assert mixed, "a Japanese name in English prose"
    assert native, "a Japanese name and a Japanese pronoun"


def test_a_japanese_cast_name_yields_reference_patterns():
    """`_actor_reference_patterns` returning [] makes both
    `_check_quote_attribution` and `_check_position_fidelity` decline
    entirely, and ヒナミ is three characters."""
    from agents.common import _actor_reference_patterns

    with language_scope("ja"):
        patterns = _actor_reference_patterns("佐藤ヒナミ")
    assert patterns
    assert any(p.search("ヒナミは頷いた。") for p in patterns)
