"""Confirming a promotion is a cast writer like attaching a character.

Three defects in `confirm_promotion` (audit 2026-11-01):

* web_app F6 -- it wrote cast, scene and presence state with no idle guard.
  `promote_background_character` says its writes "stay in the turn thread
  because the turn rewrites `scene`, `background_presences` and `known`
  wholesale", and its sibling `chat_add_char` holds `_require_chat_idle` for
  that reason; a confirm landed mid-turn lost her position to the commit.
* story_scene_schema F12 -- it handed the RAW reviewed sheet to
  `character_card_warnings`, which raised on a scalar where a mapping
  belongs (`"psychology": "brave"`) AFTER the promotion had been written: the
  host saw a 500 for a promotion that succeeded.
* the refusal the writer raises for a taken or unusable name was a bare
  `ValueError`, so it reached the host as an unexplained 500 too -- the retry
  after that crash was exactly such a refusal.
"""
from __future__ import annotations

import threading
import time

import pytest
from fastapi import HTTPException


def _chat(db):
    return db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                 ("Enterprise-D", "", time.time()))


def _characters(db):
    return db.q("SELECT COUNT(*) AS n FROM characters", one=True)["n"]


def test_a_confirm_while_a_turn_runs_is_refused_with_nothing_written(temp_db):
    from agents.runtime import ABORTS
    from web import app

    cid = _chat(temp_db)
    ABORTS[(cid, None)] = threading.Event()
    try:
        with pytest.raises(HTTPException) as refused:
            app.confirm_promotion(cid, {"name": "Data",
                                        "sheet": {"identity": {"name": "Data"}}})
    finally:
        ABORTS.pop((cid, None), None)
    assert refused.value.status_code == 409
    assert _characters(temp_db) == 0


def test_a_scalar_where_a_mapping_belongs_is_warned_about_not_crashed_on(temp_db):
    from web import app

    cid = _chat(temp_db)
    out = app.confirm_promotion(cid, {
        "name": "Data",
        "sheet": {"identity": {"name": "Data"}, "psychology": "brave",
                  "embodiment": {"visible": "tall"}},
    })
    assert out["ok"] is True and out["char_id"]
    assert any("drive" in w for w in out["warnings"])
    assert _characters(temp_db) == 1


def test_the_warnings_are_asked_before_anything_is_written():
    import inspect
    from web import app

    source = inspect.getsource(app.confirm_promotion)
    assert source.index("character_card_warnings(") \
        < source.index("promote_background_character(")


def test_a_name_the_story_already_holds_is_refused_by_name(temp_db):
    from web import app

    cid = _chat(temp_db)
    app.confirm_promotion(cid, {"name": "Data", "sheet": {"identity": {"name": "Data"}}})
    with pytest.raises(HTTPException) as refused:
        app.confirm_promotion(cid, {"name": "Data", "sheet": {"identity": {"name": "Data"}}})
    assert refused.value.status_code == 409
    assert _characters(temp_db) == 1
