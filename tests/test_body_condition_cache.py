"""The turn's disguise/transformation maps are read once, and dropped when
the one thing that can change them mid-run does.

Review 2026-09-07 C13: `scene.active_disguises` and `scene.active_transformations`
are each a SELECT over `world_conditions` plus a JSON parse per row, and
perception re-derived both PER BODY PER STAGE -- the disguise context for the
player and again for every cast member, the tripwire terms once more, and
`_body_descriptions` once more again -- ~4N+6 a stage on a cast of N. Counted
on a fixture that asks for all four per body: 14 reads at N=1, 75 at N=12, 243
at N=40, against 2 after the memo. A read costs 32.5us against chat 114 on the
bench copy, which carries no rows at all, and 65-70us against a fixture with
rows to parse.

What is pinned here is the MECHANISM, not the saving: a memo that outlives
what it caches is a wrong answer, and a memo that outlives the turn is a leak
between turns. So: read once per ctx, a fresh ctx reads again, and
`drop_body_condition_caches` forgets both maps and the extra-parts cache
derived from them.
"""

from __future__ import annotations

import json
import time

import pytest

from agents import perception
from agents.perception import (
    _body_descriptions,
    _subject_concealed_terms,
    _subject_disguise_context,
    drop_body_condition_caches,
)
from core.pipeline_context import ChatData, PipelineContext, TurnData

CHAT_ID = 4321

DISGUISE = {
    "subject_id": "Hinami",
    "state": {
        "description": "a courier's grey coat and a low hood",
        "presented_appearance": "a hooded courier, face in shadow",
        "concealed_terms": ["fox ears"],
        "known_to": ["The Doctor"],
    },
}
TRANSFORMATION = {
    "subject_id": "Hinami",
    "state": {"form": "a crow", "appearance": "a crow, black and quick-eyed"},
}


def _condition(db, condition_id, kind, payload, started_at):
    db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,active,payload) VALUES(?,?,?,?,?,1,?)",
        (condition_id, CHAT_ID, "Hinami", kind, started_at,
         json.dumps(payload)),
    )


def _ctx(cast=()):
    return PipelineContext(
        chat=ChatData(id=CHAT_ID, name="C13", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=1, chat_id=CHAT_ID, idx=1, player_input="",
                      created=time.time()),
        cast=list(cast),
        input="",
    )


@pytest.fixture
def chat(temp_db):
    temp_db.qi("INSERT INTO chats(id,name,created) VALUES(?,?,?)",
               (CHAT_ID, "C13", time.time()))
    _condition(temp_db, "disg", "physical_disguise", DISGUISE, 100)
    return temp_db


def test_the_two_maps_are_read_once_for_the_whole_turn(chat, monkeypatch):
    """Twelve bodies, four readers, two reads."""
    calls = {"disguises": 0, "transformations": 0}
    real_d = perception.active_disguises
    real_t = perception.active_transformations
    monkeypatch.setattr(perception, "active_disguises",
                        lambda cid: (calls.__setitem__(
                            "disguises", calls["disguises"] + 1),
                            real_d(cid))[1])
    monkeypatch.setattr(perception, "active_transformations",
                        lambda cid: (calls.__setitem__(
                            "transformations", calls["transformations"] + 1),
                            real_t(cid))[1])

    cast = [{"id": i, "sheet": json.dumps({"name": f"Body{i:02d}"}),
             "cstate": "{}"} for i in range(1, 13)]
    ctx = _ctx(cast)
    for i in range(1, 13):
        _subject_disguise_context(ctx, f"Body{i:02d}", "plain", {})
        _subject_concealed_terms(ctx, f"Body{i:02d}")
    _body_descriptions(ctx, {"rooms": {}, "positions": {}, "attire": {}})

    assert calls == {"disguises": 1, "transformations": 1}


def test_a_fresh_ctx_reads_again(chat):
    """The memo is the TURN's. Nothing may survive into the next turn or
    another chat, which is why it lives on the ctx and not a module global."""
    first = _ctx()
    assert _subject_concealed_terms(first, "Hinami") == ["fox ears"]

    chat.qi("UPDATE world_conditions SET active=0 WHERE condition_id='disg'")

    assert _subject_concealed_terms(first, "Hinami") == ["fox ears"], \
        "the turn already read the map; it must not change under a stage"
    assert _subject_concealed_terms(_ctx(), "Hinami") == []


def test_dropping_the_caches_re_reads_the_table(chat):
    """A checkpoint restore rewrites `world_conditions` wholesale mid-run --
    `runtime._restore_and_refresh` -- so the memo has to be droppable, and
    the extra-parts cache built from it has to go with it."""
    ctx = _ctx()
    visible, active, _known, _ci = _subject_disguise_context(
        ctx, "Hinami", "a kitsune, ears bare", {})
    assert active is True
    assert "hooded courier" in visible
    ctx["_composer_extra_parts_cache"] = {"Hinami": [{"kind": "six tails"}]}

    _condition(chat, "tran", "physical_transformation", TRANSFORMATION, 200)
    drop_body_condition_caches(ctx)

    visible, active, known, _ci = _subject_disguise_context(
        ctx, "Hinami", "a kitsune, ears bare", {})
    assert active is None, "a transformed body is concealing nothing"
    assert known is None
    assert "crow" in visible
    assert ctx.get("_composer_extra_parts_cache") is None


def test_the_restore_path_drops_them(chat):
    """The wiring, because the memo is only correct if the one mid-run writer
    of `world_conditions` clears it. Read from the source rather than run: a
    restore needs a whole pipeline, and what is being pinned is that the call
    is present in the helper that restores."""
    import inspect

    from agents import runtime

    assert runtime.drop_body_condition_caches is drop_body_condition_caches
    src = inspect.getsource(runtime._run_pipeline)
    assert "drop_body_condition_caches(ctx)" in src
