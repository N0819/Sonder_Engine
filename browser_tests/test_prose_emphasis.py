"""The narrator's inline emphasis, rendered rather than printed.

The narrator reaches for ``<i>`` unprompted and uses it well -- for a thought
the prose voices rather than quotes, and for what a gesture says without
words. Nothing rendered it, so it reached the page as literal angle brackets.

These run in a real browser because the thing under test IS the DOM: the
guarantee is not "the tags are gone" but "only elements this code created
exist, and everything else stayed text". A string assertion cannot tell those
apart, and getting it wrong turns model output into markup -- which is the one
thing ``paintProse`` has always been careful about.
"""

from __future__ import annotations

from pathlib import Path

from playwright.sync_api import Page


ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / "static" / "js"


def _harness(page: Page) -> None:
    """Load `el` plus chat.js's prose-painting block into a blank page.

    Sliced rather than imported whole: chat.js touches document ids and shared
    state at load, none of which this block needs. The slice is bounded by
    named functions so it fails loudly if the file is reorganised.
    """
    components = (JS / "components.js").read_text(encoding="utf-8")
    el_start = components.index("function el(")
    el_end = components.index("// ---- Modal ----")

    chat = (JS / "chat.js").read_text(encoding="utf-8")
    start = chat.index("const _FOLD_PAIRS")
    end = chat.index("function proseEl(")

    page.set_content("<!doctype html><body><div id='out'></div></body>")
    page.add_script_tag(content=components[el_start:el_end] + "\n" + chat[start:end])


def _paint(page: Page, prose: str, speech=None, colors=None) -> dict:
    return page.evaluate(
        """(a) => {
            const host = document.getElementById('out');
            paintProse(host, a.prose, a.speech, a.colors);
            return {
                html: host.innerHTML,
                text: host.textContent,
                tags: [...host.querySelectorAll('*')].map(e => e.tagName),
            };
        }""",
        {"prose": prose, "speech": speech, "colors": colors},
    )


def test_an_italic_run_becomes_an_element(page: Page) -> None:
    _harness(page)
    out = _paint(page, "He shrugged. <i>That was almost too easy.</i>")
    assert out["tags"] == ["I"]
    assert "That was almost too easy." in out["text"]
    # The reader must not see the machinery.
    assert "<i>" not in out["text"] and "</i>" not in out["text"]


def test_markup_that_is_not_on_the_allowlist_stays_text(page: Page) -> None:
    """The whole safety property, in one assertion: no element but the ones
    this code names, whatever the prose contains."""
    _harness(page)
    out = _paint(
        page,
        "She left. <script>window.PWNED=1</script> "
        "<img src=x onerror=alert(1)> <div>x</div> <i>Odd.</i>",
    )
    assert out["tags"] == ["I"]
    assert "<script>" in out["text"]          # still there, as characters
    assert page.evaluate("!!window.PWNED") is False


def test_an_attribute_form_is_not_treated_as_emphasis(page: Page) -> None:
    # Only the bare tag is recognised, so there is no attribute to sanitise.
    _harness(page)
    out = _paint(page, "<i class='x'>not markup</i>")
    assert out["tags"] == []
    assert "class='x'" in out["text"]


def test_an_unclosed_tag_is_left_alone(page: Page) -> None:
    """A typo must not italicise the rest of the turn. Showing the tag is the
    smaller failure, and it is the one that tells you what happened."""
    _harness(page)
    out = _paint(page, "He said <i>wait and nothing ever closed it.")
    assert out["tags"] == []
    assert "<i>" in out["text"]


def test_emphasis_inside_a_quoted_line_keeps_its_speaker_tint(page: Page) -> None:
    """The reason emphasis is resolved BEFORE dialogue matching. speechSpans
    searches the prose for the logged line; a tag inside the quote breaks that
    search, and the line would silently lose its colour."""
    _harness(page)
    out = _paint(
        page,
        '"I have <i>absolutely</i> got this," he said.',
        speech=[{"speaker": "The Doctor", "quote": "I have absolutely got this,"}],
        colors={"The Doctor": "#8ecfff"},
    )
    assert out["tags"] == ["SPAN", "I"]
    said = page.evaluate(
        "document.querySelector('#out .said').textContent")
    assert said == '"I have absolutely got this,"'


def test_prose_with_no_tags_is_unchanged(page: Page) -> None:
    _harness(page)
    out = _paint(page, "Nothing here but weather and a long silence.")
    assert out["tags"] == []
    assert out["text"] == "Nothing here but weather and a long silence."


def test_the_whole_canonical_set_renders(page: Page) -> None:
    """Everything `schemas.canonicalize_prose_markup` may leave in prose has a
    renderer here. A tag the boundary permits and this end does not know is a
    literal tag on the page, which is the bug this pair exists to close."""
    _harness(page)
    out = _paint(
        page,
        "<i>a</i><b>b</b><u>c</u><s>d</s>"
        "<mark>e</mark><sup>f</sup><sub>g</sub><code>h</code>",
    )
    assert out["tags"] == ["I", "B", "U", "S", "MARK", "SUP", "SUB", "CODE"]
    assert out["text"] == "abcdefgh"


def test_prose_that_talks_about_a_tag_does_not_become_one(page: Page) -> None:
    """Angle brackets stay encoded through the boundary and are decoded here,
    in text nodes only, after tag-finding. A narrator explaining markup must
    not have the explanation silently applied to itself."""
    _harness(page)
    out = _paint(page, "Type &lt;b&gt;this&lt;/b&gt; to make it <b>bold</b>.")
    assert out["tags"] == ["B"]                    # only the real one
    assert "<b>this</b>" in out["text"]            # the rest reads as written
    assert out["text"].endswith("to make it bold.")


def test_an_ampersand_survives_as_itself(page: Page) -> None:
    _harness(page)
    out = _paint(page, "Tea &amp; toast.")
    assert out["text"] == "Tea & toast."


def test_a_named_ink_renders_as_a_class_never_a_colour_value(page: Page) -> None:
    """The theme owns the ink. Model output must not reach a style attribute,
    which is also what keeps a colour from being invisible on four of five
    grounds."""
    _harness(page)
    out = _paint(page, 'The light went <font color="red">red</font>.')
    assert out["tags"] == ["SPAN"]
    assert page.evaluate(
        "document.querySelector('#out span').className") == "ink ink-red"
    assert page.evaluate(
        "document.querySelector('#out span').getAttribute('style')") is None


def test_a_font_with_no_name_is_not_markup(page: Page) -> None:
    _harness(page)
    out = _paint(page, "<font>no name</font>")
    assert out["tags"] == []
    assert "<font>" in out["text"]


def test_marks_nest_rather_than_flattening(page: Page) -> None:
    """A bold word can be coloured and a coloured phrase can carry an italic.
    Emitting them as siblings silently drops one of the two."""
    _harness(page)
    _paint(page, '<b>bold and <font color="blue">blue</font></b>')
    assert page.evaluate(
        "document.querySelector('#out b span.ink-blue').textContent") == "blue"
