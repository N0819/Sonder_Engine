"""Inline markup in narration, reduced to a closed set at the boundary.

THE ENGINE ASKED FOR THIS AND THEN WAS SURPRISED BY IT. The paragraph contract
tells the narrator to mark paragraphs with `<p>`, chosen precisely because the
model has seen a billion of them where a private token like `[[P]]` returned an
empty prose field. Familiarity does not stop at one tag: told that this channel
speaks HTML, the narrator began emitting `<i>` for a thought the prose voices
rather than quotes -- good writing, landing on the page as angle brackets.

So the set is closed here rather than guessed at downstream, and these pin the
three outcomes: canonical, removed, or removed with its content. `<p>` is NOT
one of them -- it is a structural delimiter consumed into paragraph breaks
before this runs, and it stays that way.
"""

from __future__ import annotations

from agents.common import strip_prose_markup, _contains_quote
from llm.schemas import canonicalize_prose_markup, preprocess_llm_output


def test_the_canonical_set_survives_with_one_spelling_each():
    assert canonicalize_prose_markup(
        "<em>a</em> <cite>b</cite> <strong>c</strong> <ins>d</ins> "
        "<del>e</del> <strike>f</strike> <samp>g</samp>"
    ) == "<i>a</i> <i>b</i> <b>c</b> <u>d</u> <s>e</s> <s>f</s> <code>g</code>"


def test_decoration_is_removed_and_its_text_is_kept():
    """The rule the paragraph handler set: no text is EVER dropped for a
    markup reason. A stray tag costs its own characters and nothing else."""
    assert canonicalize_prose_markup(
        '<h2>Chapter</h2><span class="x">She</span> '
        '<a href="/x">left</a>.<hr>'
    ) == "ChapterShe left."


def test_content_that_is_not_prose_goes_with_its_container():
    assert canonicalize_prose_markup(
        "She left. <script>window.X=1</script> Gone."
    ) == "She left.  Gone."


def test_a_ruby_reading_is_dropped_rather_than_welded_into_the_word():
    # Keeping it inline produces "漢字かんじ" -- a pronunciation gloss fused
    # into the middle of the sentence, which is worse than losing it.
    assert canonicalize_prose_markup(
        "<ruby>漢字<rt>かんじ</rt></ruby> on the sign."
    ) == "漢字 on the sign."


def test_an_unmatched_tag_is_removed_not_honoured():
    """An opener with no closer is a typo. Honouring it would italicise the
    rest of the beat; leaving it would print a tag."""
    assert canonicalize_prose_markup(
        "He said <i>wait and nothing closed it."
    ) == "He said wait and nothing closed it."
    assert canonicalize_prose_markup("A closer </i> alone.") == "A closer  alone."


def test_br_is_the_one_tag_that_is_text():
    assert canonicalize_prose_markup("One<br>Two") == "One\nTwo"


def test_entities_decode_but_angle_brackets_do_not():
    """`&lt;i&gt;` is a narrator writing ABOUT a tag. Decoding it here would
    hand the renderer a real pair to italicise, so those two stay encoded
    through storage and are decoded in text nodes at the far end."""
    assert canonicalize_prose_markup("Tea &amp; toast &mdash; cold") == (
        "Tea & toast — cold")
    assert canonicalize_prose_markup("He typed &lt;i&gt;hello&lt;/i&gt;.") == (
        "He typed &lt;i&gt;hello&lt;/i&gt;.")


def test_a_comparison_is_not_a_tag():
    assert canonicalize_prose_markup("if a < b then run") == "if a < b then run"


def test_it_is_idempotent():
    # Prose is editable by hand, and a saved edit passes through again.
    once = canonicalize_prose_markup(
        "<b>bold <i>both</i></b> &amp; <span>x</span> &lt;n&gt;")
    assert canonicalize_prose_markup(once) == once


def test_the_paragraph_contract_is_untouched_and_runs_first():
    """`<p>` is a structural delimiter, not one of the marks: it is consumed
    into blank lines and a count before this pass sees the string."""
    out = preprocess_llm_output("narrator", {
        "prose": "<p>She turned. <i>Not again.</i></p><p>Then <span>she</span> ran.</p>",
    })
    assert out["prose"] == "She turned. <i>Not again.</i>\n\nThen she ran."
    assert out["paragraph_count"] == 2


def test_an_emphasised_dialogue_line_still_reads_as_delivered():
    """The downstream half, and the reason this cannot live in the frontend
    alone. `_contains_quote` searches prose for the logged line by substring,
    so a tag inside the quote makes a correctly rendered line look DROPPED and
    sends the narrator back to rewrite prose that was already right."""
    prose = '"I have <i>absolutely</i> got this," he said.'
    assert _contains_quote(prose, "I have absolutely got this,")
    assert strip_prose_markup(prose) == '"I have absolutely got this," he said.'


def test_a_named_ink_survives_in_narration():
    assert canonicalize_prose_markup(
        'The light went <font color="crimson">red</font> above the door.'
    ) == 'The light went <font color="red">red</font> above the door.'


def test_a_colour_value_is_dropped_and_its_words_kept():
    """A hex reads on some grounds and vanishes on others -- this engine has
    five themes including a pure-black console and a parchment tavern -- and
    nothing downstream could tell which. The narrator names an intent; the
    theme owns the ink."""
    for value in ('#3af', 'chartreuse', 'rgb(1,2,3)'):
        assert canonicalize_prose_markup(
            'A <font color="%s">shade</font> of it.' % value
        ) == "A shade of it."


def test_ink_inside_a_quotation_is_discarded():
    """A spoken line already carries its speaker's colour, from the reader's
    own palette. Enforced here rather than asked for, because a rule the model
    has to remember is a rule that holds most of the time."""
    assert canonicalize_prose_markup(
        '"I said <font color="red">no</font>," he snapped.'
    ) == '"I said no," he snapped.'
    # Curly quotes are the ones a narrator actually types.
    assert canonicalize_prose_markup(
        '“Stay <font color="blue">back</font>,” she said.'
    ) == "“Stay back,” she said."


def test_narration_keeps_its_ink_in_the_same_beat_speech_loses_it():
    assert canonicalize_prose_markup(
        'The bulb went <font color="amber">amber</font>. '
        '"Get <font color="red">down</font>!"'
    ) == ('The bulb went <font color="amber">amber</font>. "Get down!"')


def test_a_colour_attribute_is_not_read_as_dialogue():
    """`color="red"` carries quote marks of its own. Reading them as a spoken
    line made the attribute delete the colour it declares -- so quote-finding
    masks tag interiors first, at equal length so offsets still mean what they
    meant."""
    assert 'color="red"' in canonicalize_prose_markup(
        'The light went <font color="red">red</font>.')
