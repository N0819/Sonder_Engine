"""An ellipsis ended a sentence for one splitter and not for the one that ran.

`perception.py` bound `_SENTENCE_SPLIT` twice, 1,258 lines apart, with a
thirty-line comment above each describing behaviour only the FIRST one has.
Module globals resolve at call time, so every reader got the second, and the
second is strictly weaker on ASCII: it does not treat `...` as a terminator
and does not tolerate a closing `)` or `]` between the terminator and the
space.

Sentence boundaries are not cosmetic here. `_redact_concealed_from_event`
calls itself "the load-bearing guarantee for concealment" and works by
keeping a safe SUBSET of sentences; where the text will not split, there is
no subset, and the whole beat is thrown away to protect one clause of it.
"""

import agents.perception as perception


CONCEALED = [{"actor": "Mara"}]


def test_an_ellipsis_ends_a_sentence():
    """The unrelated half of the beat must survive the concealed half.

    Under the surviving definition the two clauses were one sentence, that
    sentence named Mara, and the observer was told nothing at all about a
    beat they were entitled to most of."""
    text = "The Doctor keeps reading… Mara slips the vial into her sleeve."
    out = perception._redact_concealed_from_event(text, CONCEALED)

    assert "vial" not in out, "the concealed act survived redaction"
    assert "The Doctor keeps reading" in out, (
        f"an ellipsis cost the observer the rest of the beat: {out!r}")


def test_a_closing_bracket_rides_with_the_sentence_it_ends():
    """Same defect, other half of the pattern: a terminator followed by a
    closing bracket before the space."""
    text = ("The lamp gutters (barely alight.) "
            "Mara slips the vial into her sleeve.")
    out = perception._redact_concealed_from_event(text, CONCEALED)

    assert "vial" not in out, "the concealed act survived redaction"
    assert "The lamp gutters" in out, (
        f"a closing bracket cost the observer the rest of the beat: {out!r}")


def test_a_closing_quote_still_rides_with_its_sentence():
    """The deleted twin's one genuine advantage, kept.

    It put the closer inside a LOOKBEHIND, so the quote stayed attached to
    the sentence it closes; the surviving definition put it inside the match
    and the split ate it. Neither definition was strictly stronger, which is
    why this repair is a union and not a deletion."""
    text = 'The Doctor says "keep still." Mara slips the vial into her sleeve.'
    out = perception._redact_concealed_from_event(text, CONCEALED)

    assert "vial" not in out
    assert out == 'The Doctor says "keep still."', (
        f"the split ate the quote that closed the kept sentence: {out!r}")


def test_a_japanese_sentence_end_needs_no_space():
    """The CJK branch is why the first definition was written; it must
    survive the deletion of the second."""
    text = "医者は本を読む。" \
           "マラは小瓶を袖に入れる。"
    out = perception._redact_concealed_from_event(text, [{"actor": "マラ"}])

    assert "小瓶" not in out
    assert "医者は本を読む。" in out, out


def test_the_module_binds_the_splitter_once():
    """Two bindings of one name is the defect itself: whichever comment a
    reader trusts, the other definition is the one that runs."""
    import inspect
    src = inspect.getsource(perception)
    assert src.count("\n_SENTENCE_SPLIT = ") == 1, (
        "_SENTENCE_SPLIT is bound more than once; the later binding wins "
        "silently and the earlier comment block describes nothing")


# ---------------------------------------------------------------------------
# The recognizer tables the same class of defect one layer over: the guard is
# fine, the language it is written in is not the language the story is in.
# Five tables that decide a full render, a continuity rescue, a refusal floor,
# a motion tripwire and whether a knocked-out mind feels pain were English
# literals on the live path, while the tables that HAD been routed through the
# pack sat on the dead one. Read at use time, never at import: the story
# language is a contextvar and two languages can run in one process.
# ---------------------------------------------------------------------------

import pytest

from language_runtime import current_language_id


@pytest.fixture
def japanese():
    token = current_language_id.set("ja")
    try:
        yield
    finally:
        current_language_id.reset(token)


def _look(verb):
    return perception._explicit_look_intent(
        {"sequence": [{"type": "action", "verb": verb, "attempt": verb}]})


def _rapid(verb):
    return perception._declares_rapid_movement(
        {"sequence": [{"type": "action", "verb": verb, "attempt": verb}]})


def test_an_explicit_look_re_earns_a_full_render_in_english():
    assert _look("examine") and _look("looks")
    assert not _look("shout")


def test_an_explicit_look_re_earns_a_full_render_in_japanese(japanese):
    """The player's outcome view re-renders their whole standing state on an
    explicit look. Against eleven English words a Japanese story could never
    earn it."""
    assert _look("見回す")
    assert _look("調べる")
    assert not _look("叫ぶ")


def test_declared_rapid_movement_is_recognised_in_both(japanese):
    assert _rapid("走る")
    assert _rapid("run")
    assert not _rapid("座る")


def test_the_sight_floor_recognises_a_japanese_assertion(japanese):
    """`_strip_self_narration` refuses to leave a view with no sight in it at
    all. In English literals a view asserting 見える scored as sightless, so
    the refusal could not fire and the whole cut went through -- over-denial,
    which is the failure this floor exists to prevent."""
    from language_runtime import linguistic

    sight = linguistic("agents.perception", "_SIGHT_ASSERTION")
    assert sight.search("彼女には鳥居の人影が見える。")
    assert sight.search("He catches sight of a figure at the torii.")
    assert not sight.search("雨が砂利を叩く音がする。")


def test_the_vertical_motion_tripwire_reads_both(japanese):
    from language_runtime import linguistic

    raising = linguistic("agents.perception", "_RAISING")
    lowering = linguistic("agents.perception", "_LOWERING")
    assert raising.search("手を持ち上げる") and raising.search("lifts a hand")
    assert lowering.search("手を下ろす") and lowering.search("lowers a hand")
    assert not raising.search("手を下ろす")


def test_pain_cues_are_one_table_read_from_the_pack(japanese):
    """Hand-copied twice, ten lines apart, in the two residue paths. A
    non-awake Japanese mind whose cause read 負傷 felt nothing."""
    from language_runtime import linguistic

    cues = linguistic("agents.perception", "_PAIN_CUES")
    assert any(w in "負傷により意識を失った" for w in cues)
    assert any(w in "struck from behind" for w in cues)
    assert not any(w in "眠っている" for w in cues)


def test_the_english_compat_export_is_not_what_the_floor_reads():
    """`_SIGHT_ASSERTION` survives as a module constant for tests and audits,
    bound once from the English pack -- the same convention
    `composer.DIM_FIGURE` keeps. The floor itself reads the ACTIVE pack, which
    is why the constant may be English while a Japanese turn still works."""
    from language_runtime import english_linguistic

    assert perception._SIGHT_ASSERTION.pattern == english_linguistic(
        "agents.perception", "_SIGHT_ASSERTION").pattern
    assert not perception._SIGHT_ASSERTION.search("彼女には人影が見える。")
