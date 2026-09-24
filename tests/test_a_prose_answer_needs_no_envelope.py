"""A step whose answer is its prose may send the prose alone.

Round-7 real-turn replays (2026-09-23, NanoGPT z-ai/glm-5.2:thinking): the
narrator's first answer on 4 of 13 beats was the narration itself -- HTML
paragraphs, cleanly finished, once with json_schema requested -- and the
parse failed at position 0. A temperature-0 repair then spent 9-52 s
re-sending the same prose inside `{"prose": ...}`, and on one beat rewrote
the engine's `{{L1}}` line tokens into its own version of the lines.
"""

from __future__ import annotations

import pytest

from llm import llm_quality

NARRATION = ("<p>The Doctor turns from the console to face you. {{L1}} Then he "
             "is already turning back.</p>\n\n<p>The deck drops out from under "
             "you.</p>")


def test_the_narrators_bare_prose_is_its_answer_on_the_first_call(monkeypatch):
    calls, noted = [], []

    def answer(*args, **kwargs):
        calls.append(1)
        return NARRATION

    monkeypatch.setattr(llm_quality, "chat_complete", answer)
    monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
    monkeypatch.setattr(llm_quality, "note_step_warning", noted.append)
    out = llm_quality.complete_validated_json(
        role="narrator", step_key="narrator", system="sys", payload={"x": 1})
    assert len(calls) == 1
    # Normalized as a JSON answer's prose would be; the line token stays the
    # engine's to fill.
    assert "{{L1}} Then he is already turning back." in out["prose"]
    assert "The deck drops out from under you." in out["prose"]
    assert noted and "bare prose" in noted[0]


def test_the_prose_authors_bare_prose_is_its_answer():
    assert llm_quality._bare_prose_answer(
        "director_prose", "Mara climbs the stair.") == {"prose": "Mara climbs the stair."}


@pytest.mark.parametrize("raw", [
    '{"prose": "<p>The deck drops',          # a broken object is not prose
    "```json\n{\"prose\": \"x\"}",           # nor a fence
    "[1, 2]",
    " -- . ",                                 # no word in it
    "",
])
def test_what_is_not_bare_prose_takes_the_ladder(raw):
    assert llm_quality._bare_prose_answer("narrator", raw) is None


def test_a_step_whose_answer_is_not_prose_takes_the_ladder():
    assert llm_quality._bare_prose_answer("character_kernel", NARRATION) is None
    assert llm_quality._bare_prose_answer("director_specialist", NARRATION) is None


def test_prose_cut_off_for_length_is_not_a_whole_answer(monkeypatch):
    monkeypatch.setattr(llm_quality, "output_ran_out_of_room", lambda raw: True)
    assert llm_quality._bare_prose_answer("narrator", NARRATION) is None
