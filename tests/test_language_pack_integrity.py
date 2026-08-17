"""Guards on the pack data itself, not on the code that reads it.

Every failure covered here is one the shipped Japanese pack actually had, and
every one of them failed SILENTLY: a translated enum is still valid JSON, an
uncompilable regex loads fine and raises mid-turn, a blanked prompt still has
the right key. The suite could not see any of it, which is why these assertions
are about pack CONTENT rather than pack structure.
"""

import re
import sys
from pathlib import Path
from string import Formatter

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from project_check import canonical_language_tokens  # noqa: E402
from language_runtime import installed_language_packs  # noqa: E402


PACKS = installed_language_packs()
NON_ENGLISH = sorted(pid for pid in PACKS if pid != "en")


def _leaves(value, path=()):
    from collections.abc import Mapping
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _leaves(child, path + (str(key),))
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from _leaves(child, path + (str(index),))
    elif isinstance(value, str):
        yield ".".join(path), value


# --- the token rule that decides what a translator may not touch -----------

@pytest.mark.parametrize("text, expected", [
    # The class that shipped broken: a schema example states its enum as one
    # quoted alternation. Excluding `|` from the token class meant this span
    # matched nothing at all and was handed to the model as prose.
    ('"operation":"reinforce|weaken|revise"', "reinforce|weaken|revise"),
    ('"op":"adopt|displace|satisfy"', "adopt|displace|satisfy"),
    # Id templates carry angle brackets.
    ('"event_id":"current:<perceiver>:0"', "current:<perceiver>:0"),
    ('"memory_ref":"event:<hash>"', "event:<hash>"),
])
def test_structured_protocol_spans_are_recognised(text, expected):
    assert expected in canonical_language_tokens(text)


def test_a_translated_enum_is_reported_as_lost():
    english = canonical_language_tokens('"operation":"reinforce|weaken|revise"')
    japanese = canonical_language_tokens('"operation":"強化|弱化|修正"')
    assert english.difference(japanese) == {"reinforce|weaken|revise"}


def test_a_languages_own_quote_marks_are_not_protocol_drift():
    """Japanese wraps spans in corner brackets. The protocol is the span, not
    the punctuation a translator put around it."""
    assert (canonical_language_tokens("name each channel as 'state_diff.<channel>'")
            == canonical_language_tokens("各チャネルを「state_diff.<channel>」と"))


def test_repetition_is_not_drift():
    """A translation may split one English clause into two. Counting
    occurrences would forbid ordinary rephrasing and catch nothing extra."""
    once = canonical_language_tokens('answer {"verdict": "keep"}')
    twice = canonical_language_tokens('"keep"のとき。"keep"です。 {"verdict": "keep"}')
    assert not once.difference(twice)


# --- the shipped packs hold to it ------------------------------------------

@pytest.mark.parametrize("language_id", NON_ENGLISH)
def test_no_pack_translates_a_canonical_protocol_span(language_id):
    """psychology_runtime, affect and importers parse these values back. A
    translated one is not a wrong answer, it is no answer -- the lookup misses
    and the operation silently does not happen."""
    english = dict(_leaves(PACKS["en"].card("system_prompts")))
    localized = dict(_leaves(PACKS[language_id].card("system_prompts")))
    lost = {}
    for path, source in english.items():
        if any(seg in {"nsfw_prompt_ids", "order"} for seg in path.split(".")):
            continue
        missing = canonical_language_tokens(source).difference(
            canonical_language_tokens(localized.get(path, "")))
        if missing:
            lost[path] = sorted(missing)
    assert not lost, f"{language_id} lost protocol spans: {lost}"


@pytest.mark.parametrize("language_id", sorted(PACKS))
def test_every_linguistic_regex_compiles(language_id):
    """_linguistic_cached compiles lazily, so a bad pattern loads clean and
    raises a bare re.error deep inside a turn."""
    from collections.abc import Mapping
    for module, transforms in PACKS[language_id].card("linguistics").items():
        for name, value in transforms.items():
            if isinstance(value, Mapping) and value.get("$type") == "regex":
                re.compile(str(value["pattern"]), int(value.get("flags") or 0))


@pytest.mark.parametrize("language_id", sorted(PACKS))
def test_compositor_templates_name_only_fields_english_supplies(language_id):
    """compositor_text() formats these at render time; an unknown field shows
    up as a broken view, never as a bad pack."""
    english = PACKS["en"].card("compositor").get("templates") or {}
    fields = lambda t: {n for _x, n, _s, _c in Formatter().parse(str(t)) if n}
    for key, template in (PACKS[language_id].card("compositor")
                          .get("templates") or {}).items():
        if key in english:
            assert not fields(template).difference(fields(english[key])), key


@pytest.mark.parametrize("language_id", sorted(PACKS))
def test_no_translation_mask_markers_survived(language_id):
    """A leaked ⟦S0000⟧ looks like ordinary text to every other rule."""
    pack = PACKS[language_id]
    for card in ("system_prompts", "compositor", "authoring"):
        for path, value in _leaves(pack.card(card)):
            assert "⟦" not in value and "⟧" not in value, f"{card}.{path}"
    for key, value in pack.ui_catalog.items():
        assert "⟦" not in value and "⟧" not in value, key


@pytest.mark.parametrize("language_id", NON_ENGLISH)
def test_no_prompt_english_supplies_is_blank(language_id):
    english = dict(_leaves(PACKS["en"].card("system_prompts")))
    localized = dict(_leaves(PACKS[language_id].card("system_prompts")))
    blank = [path for path, source in english.items()
             if source.strip() and not localized.get(path, "").strip()]
    assert not blank, f"{language_id} has blank prompt text at: {blank[:8]}"


# --- transforms whose VALUES are engine protocol ---------------------------

#: Deterministic transforms that carry canonical values, and what reads them
#: back. A pack may ADD alternatives to these -- a Japanese story's Director
#: writes Japanese, and code-switching keeps the English ones live -- but it
#: must never drop or rewrite a value English defines, because the consumer
#: named here does an exact lookup and a miss is silent.
CANONICAL_BEARING = {
    ("agents.character", "_VERDICTS"):
        "element [0] is the maze exit-entry key read by affect's verdict table",
    ("agents.director", "_OMISSION_CATEGORY_ALIASES"):
        "values are state_diff channel names routed by the Director",
    ("agents.narration", "_ENFORCEABLE_PREFIXES"):
        "matched with startswith against English f-strings built in common.py",
    ("agents.common", "_DIRECTOR_VOICEABLE_KINDS"):
        "matched against entity.kind from the merged state_diff",
    ("agents.common", "_APPEARANCE_LABELS"):
        "element [0] is the ledger separator emitted by scene.appearance_of",
}


def _canonical_values(value):
    """The values a consumer looks up, whatever container holds them."""
    if isinstance(value, dict):
        return {(str(k), str(v)) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return {str(v) for v in value}
    if isinstance(value, (list, tuple)):
        # Tuples of pairs: the HEAD of each pair is the canonical half; the
        # tail is reader prose and is expected to be translated.
        heads = set()
        for item in value:
            if isinstance(item, (list, tuple)) and item:
                heads.add(str(item[0]))
            else:
                heads.add(str(item))
        return heads
    return {str(value)}


@pytest.mark.parametrize("language_id", NON_ENGLISH)
@pytest.mark.parametrize("module, name", sorted(CANONICAL_BEARING))
def test_a_pack_may_add_alternatives_but_not_drop_canonical_ones(
        language_id, module, name):
    from language_runtime import linguistic

    reason = CANONICAL_BEARING[(module, name)]
    english = _canonical_values(linguistic(module, name, "en"))
    localized = _canonical_values(linguistic(module, name, language_id))
    missing = english.difference(localized)
    assert not missing, (
        f"{language_id} dropped canonical values from {module}.{name} "
        f"({reason}): {sorted(missing)[:6]}")


@pytest.mark.parametrize("language_id", NON_ENGLISH)
def test_localized_regexes_keep_the_anchors_english_defines(language_id):
    """A pack widens a pattern by alternation, and an alternation does not
    inherit the anchor on the branch beside it. `_LOOK_VERB_RE` means "a look
    verb IMMEDIATELY precedes"; without `$` on the Japanese branch it degraded
    to "appears anywhere earlier" and suppressed a fidelity warning.
    """
    from language_runtime import linguistic

    pattern = linguistic("agents.common", "_LOOK_VERB_RE", language_id).pattern
    branches = pattern.count("|")
    assert pattern.count("$") >= 2, (
        f"{language_id} _LOOK_VERB_RE has {branches} alternatives but only "
        f"{pattern.count('$')} end anchors")


# --- output budgets ---------------------------------------------------------

def test_a_language_that_costs_more_tokens_gets_a_wider_output_budget():
    """Every max_tokens in the engine was chosen against English. A cap that
    truncates does not return a shorter answer -- it returns invalid JSON, and
    the caller reports a generation failure that reads like a model fault.
    Measured: character generation returned exactly 5000 tokens against a 5000
    cap and the route 502'd.
    """
    from language_runtime import language_scope
    from providers import _scale_for_language

    with language_scope("en"):
        assert _scale_for_language(5000) == 5000
    with language_scope("ja"):
        assert _scale_for_language(5000) > 5000


def test_the_scale_is_declared_by_the_pack_and_bounded(temp_db):
    """A pack states its own cost; the engine does not guess per language."""
    from language_runtime import output_token_scale

    assert output_token_scale("en") == 1.0
    for language_id in NON_ENGLISH:
        scale = output_token_scale(language_id)
        assert 1.0 <= scale <= 4.0, f"{language_id} declares {scale}"


def test_an_unset_or_absent_budget_never_narrows_a_call():
    """Scaling may only ever RAISE. A pack with no declaration, or a lookup
    that fails, must leave the caller's own budget alone."""
    from language_runtime import language_scope
    from providers import _scale_for_language

    with language_scope("en"):
        assert _scale_for_language(None) is None
        assert _scale_for_language(0) == 0
        assert _scale_for_language(1234) == 1234


# --- authoring outside a story ---------------------------------------------

def test_chatless_authoring_follows_the_interface_language(temp_db):
    """Characters, personas and lorebooks are global, so there is no story to
    read a language from. Defaulting to English meant a host who had switched
    everything to Japanese still got English cards, because the only thing
    carrying their choice was whichever frontend remembered to send it.
    """
    import app
    from language_runtime import set_ui_language

    assert app._default_authoring_language() == "en"
    set_ui_language("ja")
    assert app._default_authoring_language() == "ja"
    # An explicit request still wins over the default.
    assert app._require_story_language("en") == "en"
    assert app._require_story_language(None) == "ja"


def test_an_uninstallable_interface_language_falls_back_rather_than_raising(
        temp_db, monkeypatch):
    """This runs on the authoring path, so it must degrade, not 500."""
    import app
    from language_runtime import LanguagePackError

    monkeypatch.setattr(app, "ui_language", lambda: "zz")
    assert app._default_authoring_language() == "en"
