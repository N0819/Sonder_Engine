"""The shared registry cache: one fetch serves a turn, and writes end it.

Motivating measurement (2026-08-28, generated market town, 307 bodies,
chat 95): the stored charters blob was 41.4MB, one fetch+parse+normalize
cost ~0.95s, and a single live turn read it 21 times with zero intervening
writes — 22.2s of a 63.4s turn re-deriving one unchanged object. The fix
shares one normalized registry per (chat, storage row) behind
`core.db.world_read_token`; these tests pin the properties that would
regress silently: the fetch count, the invalidation channels, and the
read-only/private split that keeps an abandoned mutation from leaking.
"""

from __future__ import annotations

import time

import core.db as core_db
from world import charter_runtime as cr


def _chat(db):
    return db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Registry cache", "", time.time()),
    )


def _seed_registry(db, cid, body_name="Ana"):
    cr.save_registry(cid, {"items": {
        "guild": {"state": {
            "key": "guild", "posts": {}, "upkeeps": {}, "priority": [],
            "bodies": {"b1": {"key": "b1", "name": body_name,
                              "place": "hall"}},
        }},
    }})


def _counting_wget(counter):
    real = core_db.wget

    def counted(chat_id, key, d=None):
        if key == cr.CHARTERS_KEY:
            counter.append(key)
        return real(chat_id, key, d)

    return counted


class TestOneFetchServesManyReads:
    def test_repeated_reads_between_writes_perform_one_fetch(
            self, temp_db, monkeypatch):
        """Measured live: 21 fetches of one unchanged 41.4MB row in one
        turn. With the cache, every read after the first is the same
        object and no fetch fires."""
        cid = _chat(temp_db)
        _seed_registry(temp_db, cid)
        fetches = []
        monkeypatch.setattr(core_db, "wget", _counting_wget(fetches))
        first = cr.registry_for(cid)
        for _ in range(20):
            assert cr.registry_for(cid) is first
        assert len(fetches) == 1

    def test_chatter_inputs_shares_the_turn_cache(
            self, temp_db, monkeypatch):
        """The perception-stage reader (`chatter_inputs`) reads the same
        ambient row; it must ride the same cache entry, not fetch again."""
        from agents.common import chatter_inputs

        cid = _chat(temp_db)
        _seed_registry(temp_db, cid)
        cr.registry_for(cid)   # warm, present frame == ambient default
        fetches = []
        monkeypatch.setattr(core_db, "wget", _counting_wget(fetches))
        inputs = chatter_inputs(cid, {}, turn_idx=3)
        assert [c["key"] for c in inputs["charters"]] == ["guild"]
        assert fetches == []


class TestWritesEndTheSharedRead:
    def test_a_save_is_visible_to_the_very_next_read(self, temp_db):
        cid = _chat(temp_db)
        _seed_registry(temp_db, cid)
        stale = cr.registry_for(cid)
        updated = cr.registry_for_update(cid)
        updated["items"]["guild"]["state"]["bodies"]["b2"] = {
            "key": "b2", "name": "Bram", "place": "yard"}
        cr.save_registry(cid, updated)
        fresh = cr.registry_for(cid)
        assert fresh is not stale
        assert "b2" in fresh["items"]["guild"]["state"]["bodies"]

    def test_a_write_inside_a_transaction_is_reread_after_commit(
            self, temp_db):
        """wset bumps its token at execute time AND at outermost commit:
        a reader threading between the two must not pin the pre-commit
        view for good (the race is documented in core.db.wset)."""
        cid = _chat(temp_db)
        _seed_registry(temp_db, cid)
        with core_db.transaction():
            core_db.wset(cid, cr.CHARTERS_KEY, {"items": {}})
            cr.registry_for(cid)   # a read inside the window caches
        assert cr.registry_for(cid)["items"] == {}

    def test_a_raw_delete_is_covered_by_the_epoch_bump(self, temp_db):
        """Checkpoint restore, story reset and extension deletes bypass
        wset; bump_world_epoch is their invalidation channel."""
        cid = _chat(temp_db)
        _seed_registry(temp_db, cid)
        assert cr.registry_for(cid)["items"]
        temp_db.qi("DELETE FROM world WHERE chat_id=?", (cid,))
        core_db.bump_world_epoch()
        assert cr.registry_for(cid)["items"] == {}

    def test_an_unrelated_world_write_does_not_invalidate(
            self, temp_db, monkeypatch):
        cid = _chat(temp_db)
        _seed_registry(temp_db, cid)
        first = cr.registry_for(cid)
        temp_db.wset(cid, "scene", {"rooms": {}})
        assert cr.registry_for(cid) is first


class TestSharedMeansReadOnly:
    def test_an_abandoned_update_mutation_never_leaks_into_readers(
            self, temp_db):
        """The pre-cache contract writers rely on: a mutation dropped
        without save_registry is discarded with its private copy. A cache
        that handed writers the shared object would leak it."""
        cid = _chat(temp_db)
        _seed_registry(temp_db, cid)
        shared = cr.registry_for(cid)
        abandoned = cr.registry_for_update(cid)
        assert abandoned is not shared
        abandoned["items"]["guild"]["state"]["bodies"]["ghost"] = {
            "key": "ghost", "name": "Never Saved"}
        again = cr.registry_for(cid)
        assert again is shared
        assert "ghost" not in again["items"]["guild"]["state"]["bodies"]

    def test_frames_cache_separately_and_ambient_follows_the_pipeline(
            self, temp_db):
        """The charters key is frame-scoped; a flashback's observer must
        hear the flashback's charters (chatter_inputs' contract)."""
        cid = _chat(temp_db)
        _seed_registry(temp_db, cid)
        present = cr.registry_for(cid)
        era = cr.registry_for(cid, 7)
        assert era is not present and era["items"] == {}
        token = core_db.active_frame_id.set(7)
        try:
            assert cr.cached_registry(cid) is era
        finally:
            core_db.active_frame_id.reset(token)
        assert cr.cached_registry(cid) is present


class TestTheSixCallTurnBracket:
    """Finding [8]: a live turn calls `chatter_inputs` six times — the
    background gate, the interpret payload, perception_act, the resolve
    payload, the gate again, perception_outcome — and before the shared
    cache each call paid its own fetch+parse of the 41.4MB charters blob.
    Measured on the live 307-body turn (2026-08-28, chat 95): 6 calls,
    7.58s and 6 private parses with the pre-fix body; 6 calls, 0.003s and
    0 parses riding the shared cache. These pin the bracket's cost shape
    and the per-call isolation a cruder fix would have broken."""

    def test_six_stage_reads_interleaved_with_a_turns_other_traffic_fetch_nothing(
            self, temp_db, monkeypatch):
        """The live bracket, deterministically: six `chatter_inputs` calls
        interleaved with `registry_for` reads and mid-turn scene writes
        (which land on OTHER world keys) perform zero charters fetches
        after the turn's one warming read."""
        from agents.common import chatter_inputs

        cid = _chat(temp_db)
        _seed_registry(temp_db, cid)
        cr.registry_for(cid)   # the turn's one shared parse
        fetches = []
        monkeypatch.setattr(core_db, "wget", _counting_wget(fetches))
        for stage_turn_idx in (3, 3, 3, 3, 3, 3):
            inputs = chatter_inputs(cid, {}, turn_idx=stage_turn_idx)
            assert [c["key"] for c in inputs["charters"]] == ["guild"]
            cr.registry_for(cid)                      # a sibling reader
            temp_db.wset(cid, "scene", {"beat": stage_turn_idx})  # mid-turn
        assert fetches == []

    def test_each_stage_gets_its_own_memos_over_the_shared_registry(
            self, temp_db):
        """The registry parse is shared; the per-room memos are NOT. A
        memo caches room views computed from the SCENE, and the scene
        changes between perception_act and perception_outcome (a resolve
        moves people), so a fix that cached the whole inputs object across
        stages would serve the post-resolve stage the pre-resolve room.
        Each call must hand back fresh, independent memo dicts."""
        from agents.common import chatter_inputs

        cid = _chat(temp_db)
        _seed_registry(temp_db, cid)
        act = chatter_inputs(cid, {}, turn_idx=3)
        outcome = chatter_inputs(cid, {}, turn_idx=3)
        assert act is not outcome
        assert act["memo"] is not outcome["memo"]
        act["memo"]["hall"] = [{"stale": True}]
        act.setdefault("crowd_memo", {})["hall"] = [{"stale": True}]
        assert "hall" not in outcome["memo"]
        assert "hall" not in outcome.get("crowd_memo", {})
