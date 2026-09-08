"""Preparation decides; the transaction writes (review 2026-09-07 A66).

`_prepare_turn_commit` runs BEFORE the turn's write lock, so anything it
`wset`s is its own autocommit and survives the rollback of a turn that then
fails in any domain. Two channels were doing exactly that from
`prepare_scene_commit`:

* every engine notice, through `add_engine_notice`, which appended to the
  `engine_notices` world key regardless of whether it had a context to stage
  on -- and the sweep rewrote that key whole from the staged list a moment
  later anyway, so the durable write bought nothing and cost a beat's worth of
  notices standing in a chat whose turn never happened;
* the two once-per-chat "already told" flags, `sight_contradictions_told` and
  `layout_lint_told` -- spending a report that had not been delivered.

The rule that now holds: with a turn context, `add_engine_notice` stages and
only stages, until the sweep marks the beat's one rewrite as done
(`mark_engine_notices_rewritten`) -- after which the durable append is the
only channel left, which is what `commit_destruction` uses. And the flags ride
the prepared bundle in `world_flags`, written by `commit_scene` inside the
transaction.
"""

from __future__ import annotations

import time

from persist import commit
from core.pipeline_context import ChatData, PipelineContext, TurnData


CONTRADICTORY = {
    "rooms": {
        "annex": {"name": "Observation Annex",
                  "adjacent": [{"to": "cell", "barrier": "one_way_window"}]},
        "cell": {"name": "Interview Cell",
                 "adjacent": [{"to": "annex", "barrier": "one_way_window"}]},
    },
    "positions": {"Watcher": "annex", "Subject": "cell"},
    "entities": {"great_lamp": {"name": "the great lamp", "kind": "device",
                                "light_source": "bright",
                                "steadiness": "failing",
                                "state": {"lit": True}}},
}


def _ctx(temp_db):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Prepare", "", time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    temp_db.wset(chat_id, "scene", CONTRADICTORY)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Prepare", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=[], input="")
    ctx.director_resolve = {"state_diff": {"time": "a moment later"}}
    return chat_id, ctx


def _world_writes(temp_db, monkeypatch):
    """Every `wset` the call under test makes, in order."""
    seen = []
    real = temp_db.wset

    def _spy(chat_id, key, value):
        seen.append(key)
        return real(chat_id, key, value)

    monkeypatch.setattr(temp_db, "wset", _spy)
    # The DEFINING modules, never the facade: a moved function resolves `wset`
    # in its own module's globals, so a patch on the facade's re-export is
    # silently inert (`docs/experiments/AUDIT_COMMIT.md`).
    for name in ("persist.commit", "persist.commit_common",
                 "persist.commit_scene_state"):
        module = __import__(name, fromlist=["x"])
        if getattr(module, "wset", None) is real:
            monkeypatch.setattr(module, "wset", _spy)
    return seen


def test_preparation_writes_no_world_row(temp_db, monkeypatch):
    chat_id, ctx = _ctx(temp_db)
    seen = _world_writes(temp_db, monkeypatch)

    prepared = commit.prepare_scene_commit(ctx)

    assert seen == [], seen
    # It decided both things it used to write.
    assert ctx.engine_feedback, "the notices were not staged either"
    assert prepared["world_flags"]["sight_contradictions_told"] is True

    # The spy is live -- the domain that DOES write, writes through it. Without
    # this the emptiness above would pass just as well on a broken patch.
    commit.commit_scene(ctx, "nonce-1", prepared=prepared)
    assert "scene" in seen and "sight_contradictions_told" in seen, seen


def test_a_notice_with_a_context_is_staged_and_not_written(temp_db):
    chat_id, ctx = _ctx(temp_db)

    commit.add_engine_notice(ctx, chat_id, "the lamp has gone out")

    assert ctx.engine_feedback == ["the lamp has gone out"]
    assert temp_db.wget(chat_id, "engine_notices", []) == []


def test_a_notice_filed_after_the_rewrite_reaches_the_key(temp_db):
    """The half `commit_destruction` uses: that domain runs inside the
    transaction, behind the sweep's rewrite, so its notice cannot ride the
    staged list. Marked rather than remembered by the caller."""
    chat_id, ctx = _ctx(temp_db)
    commit.mark_engine_notices_rewritten(ctx)

    commit.add_engine_notice(ctx, chat_id, "the tower is rubble")

    assert temp_db.wget(chat_id, "engine_notices", []) == ["the tower is rubble"]


def test_a_notice_with_no_context_at_all_still_reaches_the_key(temp_db):
    chat_id, _ctx_unused = _ctx(temp_db)

    commit.add_engine_notice(None, chat_id, "the tower is rubble")

    assert temp_db.wget(chat_id, "engine_notices", []) == ["the tower is rubble"]


def test_the_flags_land_when_the_scene_domain_commits(temp_db, monkeypatch):
    """`commit_scene` is inside the turn's outer transaction, so the flag is
    spent exactly when the beat it was spent on is durable."""
    chat_id, ctx = _ctx(temp_db)
    prepared = commit.prepare_scene_commit(ctx)
    assert temp_db.wget(chat_id, "layout_lint_told", False) is False

    commit.commit_scene(ctx, "nonce-1", prepared=prepared)

    assert temp_db.wget(chat_id, "sight_contradictions_told", False) is True
    assert temp_db.wget(chat_id, "layout_lint_told", False) is True
