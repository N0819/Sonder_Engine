"""A Room reply stopped short of its words still says what it settled.

Hollowmere (scratch chat 196, 2026-10-12): the pre-story reply recorded a
grant, published a package with two people and the town's lore, opened a
second -- and stopped at its wall with no reply, so the player read only "The
room stopped at its budget for this reply; what it settled stands". Now the
reply names what it published and what it left drafted, in the story's
language, from the room's own titles (`story_planner._settled_line`).
"""
from __future__ import annotations

import json

from agents import story_planner as sp
from story.plot_packages import new_package
from tests.test_story_planner import _story


def _uid(result):
    return result["uid"] if isinstance(result, dict) else str(result)


def test_the_line_names_what_was_published_and_what_was_left_drafted(temp_db):
    cid, _ = _story(temp_db)
    done = _uid(new_package(cid, title="The line and its works"))
    left = _uid(new_package(cid, title="The town above the station"))
    line = sp._settled_line(cid, None, [done], [done, left])
    assert "“The line and its works”, published" in line
    assert "“The town above the station”, drafted" in line
    assert line.count("The line and its works") == 1


def test_it_speaks_the_storys_language(temp_db):
    from language_runtime import language_scope
    cid, _ = _story(temp_db)
    left = _uid(new_package(cid, title="駅の上の町"))
    with language_scope("ja"):
        line = sp._settled_line(cid, None, [], [left])
    assert "「駅の上の町」（下書き）" in line


def test_nothing_settled_keeps_the_fixed_line(temp_db):
    cid, _ = _story(temp_db)
    assert sp._settled_line(cid, None, [], []) == ""


def test_a_reply_stopped_at_its_steps_names_its_draft(temp_db, monkeypatch):
    from llm import providers
    monkeypatch.setattr(sp, "PLANNER_STEPS_PER_REPLY", 2)
    answers = iter([json.dumps({"calls": [{"tool": "new_package",
                                           "args": {"title": "The night it opens"}}]}),
                    json.dumps({"calls": [{"tool": "inspect_needs", "args": {}}]}),
                    json.dumps({"calls": [{"tool": "inspect_needs", "args": {"kind": "room"}}]})])
    monkeypatch.setattr(providers, "chat_complete", lambda *a, **k: next(answers))
    cid, _ = _story(temp_db)
    out = sp.run_planner(cid, None, text="Plan the opening night.")
    assert out["stopped"] == "steps"
    assert "“The night it opens”, drafted" in out["reply"], out["reply"]


def test_a_reply_from_the_panel_runs_in_the_storys_language(temp_db, monkeypatch):
    """The panel is a door outside the turn; it sets the story's language
    itself, so the room's card, its stopped line and the jobs it queues
    read the story's pack."""
    from language_runtime import current_language_id, set_story_language
    seen = []

    def planner(cid, frame_id, **kw):
        seen.append(current_language_id.get())
        return {"reply": "", "claims": [], "mandates": [], "status": "ok"}
    monkeypatch.setattr(sp, "run_planner", planner)
    cid, _ = _story(temp_db)
    set_story_language(cid, "ja")
    before = current_language_id.get()
    sp.planner_reply(cid, None, "Who keeps the bell?")
    assert seen == ["ja"]
    assert current_language_id.get() == before      # restored on the way out
