"""The narrator wrote one block, and the reader got one block.

Measured first on chat 59's last 25 turns: mean 939 characters, 24 of 25
carrying quoted speech from several speakers, and **zero of 25 containing a
single line break**. The prompt asked for 1-3 paragraphs and asked that a beat
change "land in its own paragraph rather than being folded into one dense
block". It never said how a paragraph is MADE, so an instruction naming the
literal `\\n\\n` was added on 2026-08-06.

**It did not work, and that is the finding.** Re-measured a week later across
the 600 most recent active narrator variants: **592 still contained no line
break at all** -- median 962 characters, p90 1430, several speakers apiece.
Six in six hundred. An emphatic, all-caps, correctly-worded instruction moved
compliance from ~0% to 1%.

This file's original note argued the transport was innocent, on the grounds
that `director_resolve` carried an escaped newline in 38 of 400 sampled
outputs against the narrator's 5 -- "the pipeline can express it, this one
field was never asked to". The first half still holds; the second no longer
does. The field WAS asked, as plainly as prose can ask, and it declined. (The
comparison is also confounded: the two roles run on different models and
providers, so it never isolated transport from model.)

Then it was asked for a `paragraphs` ARRAY instead, and did WORSE: an
engine-written `paragraph_count` came back 0 on every live variant -- the
model never emitted the field at all.

What both failures share is that they asked the model to change the SHAPE of
its reply. A delimiter does not: `<p>` and `</p>` are characters inside a
string it was already writing, needing no JSON escape and no new key. Benched
against the live narrator on a three-speaker beat (`tools/paragraph_bench.py`),
the array contract produced multiple paragraphs 2 times in 5 and `<p>` produced
them **10 times in 10**, every tag balanced. `<p>` specifically, not a private
token: `[[P]]` came back with prose EMPTY and `[[BREAK]]` silently dropped two
speakers' lines.

`preprocess_llm_output` splits on the markers and joins with blank lines, so
everything downstream still receives exactly one `prose` string.

The exemplar tests below are the voice-anchor API, which rides the same
narrator prompt and is unrelated to paragraphing.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from web import app as app_module
from web import guest_access as guest
from llm import prompts
from llm.schemas import preprocess_llm_output, validate_llm_output


def _pre(raw):
    return preprocess_llm_output("narrator", raw)


# ---- The contract the narrator is asked for ----

def test_the_narrator_is_asked_for_markers_not_a_shape():
    """THE GAP, three times. "1-3 paragraphs" was a count. Naming the literal
    `\\n\\n` reached 1%. An array reached 0. Markers are not a shape."""
    text = json.dumps(prompts.DEFAULT_PROMPTS)
    assert "MARK PARAGRAPHS WITH <p> AND </p>" in text
    assert "{prose, new_specifics" in text


def test_the_formatting_rules_are_gone():
    """The point of the change: five blocks of paragraphing guidance replaced
    by one mechanical instruction, with WHERE to break left to the model."""
    text = json.dumps(prompts.DEFAULT_PROMPTS)
    for dead in ("ONE PARAGRAPH PER ARRAY ELEMENT", "ONE SPEAKER OWNS A PARAGRAPH",
                 "THE CEILING ON THAT IS TWO SPOKEN LINES", "LENGTH: 1-3 paragraphs"):
        assert dead not in text, f"{dead!r} survived the cut"


def test_the_judgement_rules_are_novel_convention_and_short():
    """WHERE to break is the model's call, guided by four one-line rules
    rather than five blocks. The load-bearing one is the first: a paragraph
    break during dialogue is how a reader is told somebody else has taken
    over, so two speakers in one paragraph reads as the first still talking.

    Benched at 6/6 compliance on the mechanism with these in place, and
    100% on one-voice-per-paragraph; the action-merging rule runs about 1 in
    4 (`tools/paragraph_bench.py --arms live`)."""
    text = json.dumps(prompts.DEFAULT_PROMPTS)
    assert "ONE PARAGRAPH, ONE VOICE" in text
    assert "A SPEAKER KEEPS THEIR OWN ACTIONS" in text
    assert "KEEP A THING WHOLE" in text
    # Short is the point: the five deleted blocks ran ~2,700 characters.
    at = text.index("WHERE the breaks fall")
    assert len(text[at:text.index("Paragraph count NEVER licenses", at)]) < 1200


def test_dialogue_completeness_survived_the_cut():
    """It lived INSIDE the deleted LENGTH block and is a fidelity rule, not a
    formatting one -- and the losing bench arms dropped whole speakers' lines,
    so this is exactly the guarantee not to lose."""
    text = json.dumps(prompts.DEFAULT_PROMPTS)
    assert "NEVER licenses dropping a line" in text
    assert "trim description harder" in text


# ---- The render ----

def test_markers_become_blank_lines():
    out = _pre({"prose": "<p>One.</p>\n\n<p>Two.</p>"})
    assert out["prose"] == "One.\n\nTwo."
    assert out["paragraph_count"] == 2


def test_no_markup_ever_reaches_the_reader():
    """A leftover tag is worse than the unbroken block this replaces: visibly
    broken rather than merely dense."""
    for raw in ("<p>First. <p>Second.", "<p>Good.</p> tail </p>",
                "<P CLASS=x>Shouty.</P>"):
        assert "<p" not in _pre({"prose": raw})["prose"].lower()
        assert "</p" not in _pre({"prose": raw})["prose"].lower()


def test_text_outside_the_markers_is_never_dropped():
    """The first version extracted <p>...</p> matches and rebuilt from them,
    which silently deleted anything written outside a pair -- and a model that
    half-marks its output is the case this must survive. A stray tag may cost
    a break in an odd place; it may never cost a sentence."""
    out = _pre({"prose": "<p>Good.</p> leftover </p> tail"})
    for word in ("Good.", "leftover", "tail"):
        assert word in out["prose"]


def test_an_unmarked_reply_is_left_exactly_as_it_came():
    """Every stored variant predating this, plus any turn where the model
    ignores the markers. Replay, reroll and archive import all read them back
    through this same seam."""
    out = _pre({"prose": "Old contract, one block.", "new_specifics": []})
    assert out["prose"] == "Old contract, one block."
    assert out["paragraph_count"] == 0


def test_empty_pairs_do_not_become_blank_paragraphs():
    """`<p></p>` renders as a stray gap under pre-wrap."""
    assert _pre({"prose": "<p></p><p>Real.</p>"})["prose"] == "Real."


def test_the_marked_count_is_recorded():
    """0 means no markers came back at all; 1 means the model marked the whole
    beat as one paragraph. Without this the two are the same string in
    storage, and the next report of flat prose is unanswerable."""
    assert _pre({"prose": "unmarked"})["paragraph_count"] == 0
    assert _pre({"prose": "<p>whole beat</p>"})["paragraph_count"] == 1
    assert _pre({"prose": "<p>a</p><p>b</p><p>c</p>"})["paragraph_count"] == 3


def test_the_count_survives_validation_into_the_stored_variant():
    out, _w = validate_llm_output(
        "narrator", {"prose": "<p>a</p><p>b</p>", "new_specifics": []})
    assert out["paragraph_count"] == 2 and out["prose"] == "a\n\nb"


def test_the_repair_example_matches_the_live_contract():
    """It is handed to the model on every repair and fallback call, so a stale
    shape here teaches the old contract back to the model that just failed."""
    from llm.schemas import output_example

    assert "<p>" in output_example("narrator")["prose"]


def test_the_display_already_honours_a_break_the_narrator_writes():
    """The other half, needing no change: a break that reaches the string
    reaches the reader. Losing `pre-wrap` would silently undo all of it."""
    css = (Path(__file__).resolve().parents[1] / "static" / "styles.css"
           ).read_text(encoding="utf-8")
    assert "white-space:pre-wrap" in css.replace(" ", "")


# ---- The voice anchor (exemplars), which rides the same prompt ----

@pytest.fixture
def client(temp_db):
    guest.reset_host_account()
    with TestClient(app_module.app) as c:
        r = c.post("/api/auth/setup",
                   json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        yield c
    guest.reset_host_account()


def test_the_voice_anchor_finally_has_a_door(client):
    """THE SLOT EXISTED AND COULD NOT BE FILLED. `agents/narration.py` has
    always read `settings.exemplars`, and the narrator prompt has always
    carried a STYLE EXEMPLARS clause telling the model to study them -- but
    nothing could write the setting, so every install that has ever run did so
    with that clause pointing at an empty list.
    """
    r = client.put("/api/exemplars", json={"exemplars": ["A short passage."]})
    assert r.status_code == 200, r.text
    assert r.json()["exemplars"] == ["A short passage."]
    assert client.get("/api/bootstrap").json()["exemplars"] == \
        ["A short passage."]


def test_the_anchor_is_bounded_on_both_axes(client):
    """It rides EVERY narrator call. A handful of short passages is a
    calibration; a dozen long ones is a permanent tax on every turn of every
    story, paid forever and invisible at the point of payment.
    """
    r = client.put("/api/exemplars",
                   json={"exemplars": ["x" * 5000] + ["p"] * 20})
    body = r.json()
    assert len(body["exemplars"]) == app_module.EXEMPLAR_MAX_COUNT
    assert len(body["exemplars"][0]) == app_module.EXEMPLAR_MAX_CHARS


def test_empty_passages_are_dropped_rather_than_stored(client):
    """A blank exemplar is a slot spent saying nothing, and the model is told
    to study whatever is in the list.
    """
    r = client.put("/api/exemplars", json={"exemplars": ["", "  ", "real"]})
    assert r.json()["exemplars"] == ["real"]
