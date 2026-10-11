"""A Writers' Room answer with a miscounted closing bracket is read, not lost.

Measured 2026-10-11 on deepseek v4.1 flash, the Room's model, answering
without JSON mode (the provider layer turns it off for a process once
OpenRouter has twice held a JSON-mode answer past the first-token clock): two
of three plans for five rooms closed a room one brace too many or never
closed the calls list, and the Room read each as a step that said nothing --
its replay of the owner's chat 165 lost two such steps, and the plans in them,
in its first reply (`agents.common._mend_closers`, the last rung of
`jparse`). Hand-made answers in the two shapes observed.
"""
from __future__ import annotations

import json

from agents.common import _mend_closers, jparse

ROOMS = {"genkan": {"name": "The Genkan", "purpose": "where shoes come off"},
         "main_hall": {"name": "The Main Hall", "purpose": "the altar's room"}}
GOOD = json.dumps({"calls": [{"tool": "draft_operation",
                              "args": {"op": "plan_rooms", "rooms": ROOMS}}],
                   "reply": "Two rooms planned.", "status_line": "planning"})


def _break(text, old, new):
    assert text.count(old) == 1
    return text.replace(old, new)


def test_a_room_closed_one_brace_too_many_is_mended():
    broken = _break(GOOD, '}}}], "reply"', '}}}}], "reply"')
    assert jparse(broken) == json.loads(GOOD)


def test_a_calls_list_left_open_is_mended():
    broken = _break(GOOD, '}}}], "reply"', '}}}, "reply"')
    assert jparse(broken) == json.loads(GOOD)


def test_two_miscounts_in_one_answer_are_both_mended():
    many = json.dumps({"calls": [
        {"tool": "draft_operation", "args": {"op": "plan_rooms", "rooms": ROOMS}},
        {"tool": "draft_operation", "args": {"op": "plan_rooms", "rooms": ROOMS}}],
        "reply": "Planned twice."})
    broken = _break(many, '}}}, {"tool"', '}}}}, {"tool"')
    broken = _break(broken, '}}}], "reply"', '}}}, "reply"')
    assert jparse(broken) == json.loads(many)


def test_what_parsed_before_parses_the_same_and_prose_stays_prose():
    assert jparse(GOOD) == json.loads(GOOD)
    assert jparse("The room has nothing to add.") == {"text": "The room has nothing to add."}
    # a bracket inside a string is the model's words, never a closer to mend
    said = json.dumps({"reply": "the sign reads ]} closed", "calls": []})
    assert jparse(said) == json.loads(said)


def test_an_answer_cut_off_is_not_guessed_at():
    """A truncated answer is no miscount: there is no run of closers that one
    edit makes whole, and the answer is reported as prose, as before."""
    cut = GOOD[: GOOD.index("altar")]
    assert _mend_closers(cut) is None
    assert jparse(cut) == {"text": cut}


def test_a_room_step_whose_answer_miscounts_runs_its_calls(temp_db, monkeypatch):
    """Through the Room's own loop: the step reads as the calls it asked for,
    not as a step that said nothing."""
    from agents import story_planner as sp
    from llm import providers
    from tests.test_story_planner import _story
    answers = iter([
        _break(json.dumps({"calls": [{"tool": "inspect_needs", "args": {"kind": "room"}}],
                           "status_line": "reading"}), '}}], "status_line"', '}}}], "status_line"'),
        json.dumps({"reply": "done"}),
    ])
    seen = []

    def script(role, system, user, **kw):
        seen.append(json.loads(user))
        return next(answers)
    monkeypatch.setattr(providers, "chat_complete", script)
    cid, _ = _story(temp_db)
    sp.run_planner(cid, None, text="hi")
    assert [e["tool"] for e in seen[1]["transcript"]] == ["inspect_needs"]
