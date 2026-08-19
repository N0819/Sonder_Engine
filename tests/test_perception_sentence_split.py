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
