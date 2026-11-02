"""A route's own refusal reaches the caller as itself.

Six routes resolved the story language INSIDE the `try` that turns any
generation failure into a 502, so `_require_story_language`'s own 400 ("language
pack 'zz-nope' is not installed") reached the host as "502 Psychology fill
failed: 400: ..." -- a bad request reported as a broken provider (audit
2026-11-01, web_app F14, reproduced). The language is resolved before
the `try` now. And one missing-resource condition got 404, 500 or 200
depending on the route (F15): a chat-scoped writer whose chat does not exist
raised the foreign key as an unhandled 500, and the two card editors answered
`{"ok": true}` for a card that does not exist, having written nothing.
"""
from __future__ import annotations

import json
import time

import pytest
from fastapi import HTTPException

BAD = {"language": "zz-nope"}


def _character(db):
    from story.character_schema import default_character_data
    return db.qi("INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
                 ("Alice", json.dumps(default_character_data("Alice")), "{}", time.time()))


@pytest.mark.parametrize("route", ["char_fill_psychology", "char_fill_interior",
                                   "char_fill_appearance", "char_generate_greeting"])
def test_an_unknown_story_language_is_a_bad_request(temp_db, route):
    from web import app

    cid = _character(temp_db)
    with pytest.raises(HTTPException) as refused:
        getattr(app, route)(cid, dict(BAD))
    assert refused.value.status_code == 400, refused.value.detail
    assert "zz-nope" in refused.value.detail


def test_a_lore_plan_in_an_unknown_language_is_a_bad_request(temp_db):
    from web import app

    lid = temp_db.qi("INSERT INTO lorebooks(name) VALUES('Library')")
    with pytest.raises(HTTPException) as refused:
        app.lorebook_generate_plan(lid, dict(BAD))
    assert refused.value.status_code == 400


@pytest.mark.parametrize("route, body", [
    ("style_guide_put", {"style_guide": {}}),
    ("bg_cfg_put", {"scene_life": "off"}),
    ("frames_create", {"label": "Before"}),
    ("dlg_put", {}),
    # `living_world_put` stood here until 2026-11-01, when the route went with
    # the off-screen ladder it set.
    ("pph_put", {"entries": []}),
    ("naming_profile_put", {}),
])
def test_a_story_writer_for_a_missing_story_is_not_found(temp_db, route, body):
    from web import app

    with pytest.raises(HTTPException) as refused:
        getattr(app, route)(999999, body)
    assert refused.value.status_code == 404


@pytest.mark.parametrize("route", ["char_edit", "persona_edit"])
def test_a_card_edit_for_a_missing_card_is_not_found(temp_db, route):
    from web import app

    with pytest.raises(HTTPException) as refused:
        getattr(app, route)(999999, {"sheet": {"identity": {"name": "Nobody"}}})
    assert refused.value.status_code == 404
