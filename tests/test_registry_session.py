"""Review 2026-09-07 C1: one private charter registry per commit, written
once at the flush, through the one write chokepoint.
"""
import world.charter_runtime as runtime


def test_writers_inside_a_session_share_one_copy_and_land_once(temp_db, monkeypatch):
    writes = []
    import core.db as db
    real = db.wset_for_frame
    monkeypatch.setattr(db, "wset_for_frame",
                        lambda cid, key, val, fid: (writes.append(key), real(cid, key, val, fid)))
    chat_id = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                         ("Reg", "", 0.0))
    with runtime.registry_session():
        first = runtime.registry_for_update(chat_id, None)
        second = runtime.registry_for_update(chat_id, None)
        assert first is second, "one parsed copy per storage row"
        first.setdefault("recent_events", []).append({"kind": "probe"})
        runtime.save_registry(chat_id, first, None)
        runtime.save_registry(chat_id, first, None)
        assert runtime.registry_for(chat_id, None) is first, "readers see the session copy"
        assert writes == [], "nothing lands before the flush"
        assert runtime.flush_registry_session() == 1
    assert writes == [runtime.CHARTERS_KEY]
    # Outside a session every call behaves as before: an immediate write.
    runtime.save_registry(chat_id, runtime.registry_for_update(chat_id, None), None)
    assert writes == [runtime.CHARTERS_KEY, runtime.CHARTERS_KEY]
