"""A Writers' Room answer written in its model's own tool-call markup is read.

deepseek v4.1 flash, the Room's model, answering without JSON mode, sometimes
writes DeepSeek's own tool-call markup ("DSML") instead of the JSON the card
asks for -- or the card's own answer in the markup. A replay of the owner's
chat 165 (2026-10-11) lost 8 of its 98 steps so, each read as a step that
said nothing (`story_planner._native_answer`). The samples below are in the
captured syntax, with neutral names.
"""
from __future__ import annotations

import json

from agents import story_planner as sp

BAR = "｜"     # the fullwidth bar the markup is written with


def _invoke(name, *params):
    body = "".join(
        f'<{BAR}DSML{BAR} parameter name="{key}" string="{string}">{value}</{BAR}DSML{BAR} parameter>\n'
        for key, string, value in params)
    return f'<{BAR}DSML{BAR} invoke name="{name}">\n{body}</{BAR}DSML{BAR} invoke>\n'


def _calls(*invokes):
    return f"<{BAR}DSML{BAR} calls>\n" + "".join(invokes) + f"</{BAR}DSML{BAR} calls>"


def test_the_calls_in_the_markup_are_the_planners_calls():
    raw = _calls(_invoke("preview_package", ("uid", "true", "plot:the_inn:abc123")),
                 _invoke("inspect_structures"),
                 _invoke("read_lore", ("entry_id", "false", "229")),
                 _invoke("draft_operation", ("uid", "true", "plot:the_inn:abc123"),
                         ("operation", "false", '{"op": "plan_rooms", "rooms": {}}')))
    assert sp._native_answer(raw)["calls"] == [
        {"tool": "preview_package", "args": {"uid": "plot:the_inn:abc123"}},
        {"tool": "inspect_structures", "args": {}},
        {"tool": "read_lore", "args": {"entry_id": 229}},
        {"tool": "draft_operation", "args": {"uid": "plot:the_inn:abc123",
                                             "operation": {"op": "plan_rooms", "rooms": {}}}}]


def test_a_json_value_that_does_not_parse_is_kept_as_written():
    raw = _calls(_invoke("search_lore", ("query", "false", "the well's founding")))
    assert sp._native_answer(raw)["calls"] == [{"tool": "search_lore",
                                               "args": {"query": "the well's founding"}}]


def test_an_answer_with_no_markup_makes_no_calls():
    assert sp._native_answer("The room has nothing to add.") == {}
    assert sp._native_answer('{"calls": []}') == {}


def test_the_answers_own_keys_written_in_the_markup_are_read():
    """The card's answer, its keys written as markup elements: `calls` (here
    opened with the invoke tag and closed with the parameter one, as the model
    wrote it) holding the JSON list, beside `reply`."""
    raw = (f'<{BAR}DSML{BAR} calls>\n<{BAR}DSML{BAR} invoke name="calls" string="false">'
           '[{"tool": "scan_lore", "args": {"limit": 40}}, '
           '{"tool": "inspect_rooms", "args": {"room_ids": ["gate", "path"]}}]'
           f'</{BAR}DSML{BAR} parameter>\n'
           f'<{BAR}DSML{BAR} parameter name="reply" string="false">null</{BAR}DSML{BAR} parameter>\n'
           f'</{BAR}DSML{BAR} invoke>\n</{BAR}DSML{BAR} calls>')
    assert sp._native_answer(raw) == {
        "reply": None,
        "calls": [{"tool": "scan_lore", "args": {"limit": 40}},
                  {"tool": "inspect_rooms", "args": {"room_ids": ["gate", "path"]}}]}


def test_a_list_of_calls_written_inside_the_markup_is_read():
    raw = (f'<{BAR}DSML{BAR} calls>[\n  {{"tool": "read_package", "args": {{"uid": "plot:a"}}}},\n'
           f'  {{"tool": "inspect_rooms", "args": {{"room_ids": ["hall"]}}}}\n]'
           f'</{BAR}DSML{BAR} parameter>\n</{BAR}DSML{BAR} invoke>\n</{BAR}DSML{BAR} calls>')
    assert sp._native_answer(raw)["calls"] == [
        {"tool": "read_package", "args": {"uid": "plot:a"}},
        {"tool": "inspect_rooms", "args": {"room_ids": ["hall"]}}]


def test_a_tools_own_argument_is_never_taken_for_the_answer():
    raw = _calls(_invoke("draft_operation", ("reply", "true", "a note the operation carries")))
    assert sp._native_answer(raw) == {"calls": [
        {"tool": "draft_operation", "args": {"reply": "a note the operation carries"}}]}


def test_a_room_step_answering_in_the_markup_runs_its_calls(temp_db, monkeypatch):
    from llm import providers
    from tests.test_story_planner import _story
    answers = iter([_calls(_invoke("inspect_needs", ("kind", "true", "room"))),
                    json.dumps({"reply": "done"})])
    seen = []

    def script(role, system, user, **kw):
        seen.append(json.loads(user))
        return next(answers)
    monkeypatch.setattr(providers, "chat_complete", script)
    cid, _ = _story(temp_db)
    sp.run_planner(cid, None, text="hi")
    (entry,) = seen[1]["transcript"]
    assert entry["tool"] == "inspect_needs" and entry["args"] == {"kind": "room"}


def test_a_json_answer_is_read_as_json_whatever_it_says():
    """The markup is read only where no JSON answer was: an answer the card's
    way is never second-guessed."""
    said = json.dumps({"reply": f"the model once wrote <{BAR}DSML{BAR} invoke> by mistake"})
    from agents.common import jparse
    assert jparse(said)["reply"].startswith("the model once wrote")
