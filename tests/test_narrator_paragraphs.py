"""The narrator writes one block, and the reader gets one block.

Measured on a live story running current code: chat 59's last 25 turns, mean
939 characters, 24 of 25 carrying quoted speech from several speakers — and
**zero of 25 containing a single line break**. One of them puts three speakers
and four quoted lines into one unbroken paragraph.

The prompt asks for 1-3 paragraphs and asks that a beat change "land in its own
paragraph rather than being folded into one dense block". It never says how a
paragraph is made. The display already honours line breaks — `styles.css` sets
`white-space: pre-wrap` on `.prose` — so a break the narrator writes reaches the
reader unchanged. It simply never writes one.

Not an artefact of emitting JSON, either: `director_resolve` carries an escaped
newline in 38 of 400 sampled outputs and `commit` in 35 of 400, against the
narrator's 5. The pipeline can express it. This one field was never asked to.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app as app_module
import guest_access as guest
import prompts


def test_the_narrator_is_told_how_a_paragraph_is_made():
    """THE GAP. "1-3 paragraphs" is a count, not an instruction: it tells the
    model how many to write and never that a paragraph is a blank line in the
    string it returns.
    """
    text = json.dumps(prompts.DEFAULT_PROMPTS)
    assert "PARAGRAPHS ARE MADE WITH LINE BREAKS" in text
    assert "\\n\\n" in text, "the instruction must name the actual character"


def test_a_new_speaker_and_a_new_beat_are_named_as_break_points():
    """A rule with no occasions attached gets read as a suggestion. The live
    failure is several speakers in one block, so speakers are named first.
    """
    text = json.dumps(prompts.DEFAULT_PROMPTS)
    assert "own paragraph when a new person speaks" in text
    assert "own paragraph when the focus changes" in text


def test_the_length_rule_no_longer_reads_as_a_cap_on_the_output():
    """The narrator sat at ONE paragraph in 25 of 25 turns — the floor of its
    own stated range — while the same prompt told it not to fold beats into a
    dense block. A range that reads as a cap is a range that collapses to its
    minimum.
    """
    text = json.dumps(prompts.DEFAULT_PROMPTS)
    assert "FLOOR-AND-RANGE FOR DESCRIPTION, never a cap on the whole" in text


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
    carried a STYLE EXEMPLARS clause telling the model to study them — but
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


def test_something_other_than_a_list_is_refused(client):
    """The setting is read with `json.loads(... or "[]")`, so a string stored
    here would come back as a list of characters and every one would be
    presented to the narrator as a passage to imitate.
    """
    assert client.put("/api/exemplars",
                      json={"exemplars": "a passage"}).status_code == 400


def test_the_display_already_honours_a_break_the_narrator_writes():
    """The other half of the feature, and it needs no change: if the narrator
    emits a line break it reaches the reader. Losing `pre-wrap` would silently
    undo the prompt work.
    """
    css = (Path(__file__).resolve().parents[1] / "static" / "styles.css"
           ).read_text(encoding="utf-8")
    assert "white-space:pre-wrap" in css.replace(" ", "")
