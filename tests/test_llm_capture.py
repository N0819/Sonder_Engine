"""Debug capture: what was sent, what came back, and why it is small.

The engine already persists what each call COST (PipelineContext.llm_calls)
and what each STEP answered (variants). Neither records what a stage was
ASKED, and neither sees the Director's six specialist sub-calls at all --
they have no step rows. This module is that missing half.

The property that makes it affordable is dedup: a beat sends ~104KB of sheet
text that is byte-identical on the next beat, so storing by content hash means
the second beat pays for the payload keys that actually changed and nothing
else. These tests pin that, and pin that hash_only really withholds bodies.
"""
import json

import pytest

from persist import llm_capture


def _enable(db, *, bodies="full"):
    db.set_setting("llm_capture_enabled", "1")
    db.set_setting("llm_capture_bodies", bodies)


def _turn(db):
    chat_id = db.qi("INSERT INTO chats(name,created) VALUES('t',0)")
    return chat_id, db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) "
        "VALUES(?,0,'hi',0)", (chat_id,))


def test_capture_is_off_by_default(temp_db):
    from core import db
    _chat, turn_id = _turn(db)
    llm_capture.record_exchange(
        turn_id=turn_id, step_key="director_resolve", role="director",
        system="SHEET", payload={"a": 1}, response={"ok": True})
    assert llm_capture.exchanges_for_turn(turn_id) == [], (
        "capture must record nothing until it is explicitly enabled -- the "
        "llm_calls ledger's 'never content' promise holds at the default")


def test_the_same_sheet_across_two_beats_is_stored_once(temp_db):
    """The whole reason this is content-addressed rather than a log file."""
    from core import db
    _enable(db)
    chat_id, first = _turn(db)
    second = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                   "VALUES(?,1,'again',0)", (chat_id,))
    sheet = "DIRECTOR SHEET " * 500
    for turn_id in (first, second):
        llm_capture.record_exchange(
            turn_id=turn_id, step_key="director_resolve", role="director",
            system=sheet,
            # `scene` is identical between beats; `events` is not. Only the
            # second should cost a row.
            payload={"scene": {"room": "hall"}, "events": [turn_id]},
            response={"ok": True})
    sheets = db.q("SELECT COUNT(*) AS n FROM llm_blobs WHERE hash=?",
                  (llm_capture.blob_hash(sheet),), one=True)["n"]
    assert sheets == 1, "the sheet was stored twice; dedup is not working"

    scene = json.dumps({"room": "hall"}, ensure_ascii=False, sort_keys=True)
    assert db.q("SELECT COUNT(*) AS n FROM llm_blobs WHERE hash=?",
                (llm_capture.blob_hash(scene),), one=True)["n"] == 1


def test_hash_only_records_the_call_and_withholds_the_text(temp_db):
    from core import db
    _enable(db, bodies="hash_only")
    _chat, turn_id = _turn(db)
    llm_capture.record_exchange(
        turn_id=turn_id, step_key="narrator", role="narrator",
        system="SECRET SHEET", payload={"private": "story text"},
        response={"prose": "she turned"})
    rows = llm_capture.exchanges_for_turn(turn_id, include_bodies=True)
    assert len(rows) == 1
    row = rows[0]
    # The skeleton survives...
    assert row["step_key"] == "narrator" and row["role"] == "narrator"
    assert row["system_hash"] == llm_capture.blob_hash("SECRET SHEET")
    # ...and every body is withheld.
    assert row["system"] is None and row["response"] is None
    assert all(v is None for v in row["payload"].values())


def test_an_exported_turn_reads_in_call_order(temp_db):
    """`seq` is assigned at insert, so the Director's fan-out -- which finishes
    out of order -- still reads as the order the calls were made."""
    from core import db
    _enable(db)
    _chat, turn_id = _turn(db)
    for n, role in enumerate(
            ("director", "director_body", "director_spatial", "narrator")):
        llm_capture.record_exchange(
            turn_id=turn_id, step_key="director_resolve", role=role,
            system="s", payload={"n": n}, response={"n": n},
            reasoning="thought %d" % n)
    rows = llm_capture.exchanges_for_turn(turn_id, include_bodies=True)
    assert [r["role"] for r in rows] == [
        "director", "director_body", "director_spatial", "narrator"]
    assert [r["seq"] for r in rows] == [1, 2, 3, 4]
    # reasoning is carried -- it is half of "what came back" and lives nowhere
    # else for a sub-call, which has no variant of its own
    assert rows[1]["reasoning"] == "thought 1"


def test_a_body_over_the_cap_is_truncated_but_the_hash_is_of_the_whole(temp_db):
    """A record that cannot show everything must still say WHICH text ran."""
    from core import db
    _enable(db)
    huge = "x" * (llm_capture.MAX_BLOB_BYTES + 5000)
    digest = llm_capture.put_blob(huge)
    assert digest == llm_capture.blob_hash(huge)
    stored = llm_capture.get_blob(digest)
    assert stored is not None and len(stored) <= llm_capture.MAX_BLOB_BYTES


def test_pruning_a_chat_keeps_blobs_other_turns_still_reference(temp_db):
    from core import db
    _enable(db)
    chat_id, first = _turn(db)
    shared = "SHARED SHEET"
    llm_capture.record_exchange(turn_id=first, step_key="a", role="r",
                                system=shared, payload={}, response={})
    second = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                   "VALUES(?,1,'b',0)", (chat_id,))
    llm_capture.record_exchange(turn_id=second, step_key="a", role="r",
                                system=shared, payload={}, response={})
    db.qi("DELETE FROM llm_capture WHERE turn_id=?", (first,))
    assert llm_capture.vacuum_blobs() == 0, (
        "a blob still referenced by another turn was collected")
    assert llm_capture.get_blob(llm_capture.blob_hash(shared)) == shared


def test_the_turn_debug_reads_in_wall_clock_order_across_steps_and_subcalls(
        temp_db):
    """The artifact the feature exists for: one turn, in the order it happened.

    The Director's specialists are sub-calls with no steps, so they appear
    ONLY as capture rows -- an export that read steps alone would show a
    single `director_resolve` and none of the six hands that produced it.
    """
    import json as _json
    from core import db
    from persist.pipeline_trace import export_turn_debug
    _enable(db)
    _chat, turn_id = _turn(db)

    step_id = db.qi("INSERT INTO steps(turn_id,key,label,ord) "
                    "VALUES(?,'director_resolve','Director',0)", (turn_id,))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (step_id, _json.dumps({
              "resolved_event": "the door opens",
              "_engine_notes": {
                  "warnings": ["a channel was dropped"],
                  "decisions": [{"kind": "act_percept", "subject": "a -> b",
                                 "verdict": "refused",
                                 "reason": "observer cannot see (sight gate)"}],
              }}), 100.0))

    for n, role in enumerate(("director", "director_body", "director_spatial")):
        llm_capture.record_exchange(
            turn_id=turn_id, step_key="director_resolve", role=role,
            system="SHEET-%s" % role, payload={"beat": n},
            response={"did": role}, reasoning="because %d" % n,
            started=10.0 + n, duration=1.0)

    art = export_turn_debug(turn_id)
    kinds = [(e["kind"], e.get("role") or e.get("step")) for e in art["timeline"]]
    assert kinds == [
        ("call", "director"), ("call", "director_body"),
        ("call", "director_spatial"), ("step", "director_resolve"),
    ], kinds

    assert art["capture_was_on"] is True and art["calls_captured"] == 3

    # what was SENT is there, decoded
    first = art["timeline"][0]
    assert first["sent"]["system"] == "SHEET-director"
    assert first["sent"]["payload"] == {"beat": 0}
    # ...and both halves of what came back
    assert first["received"]["output"] == {"did": "director"}
    assert first["received"]["reasoning"] == "because 0"

    # the deterministic layer's own record rides on the step, refusals included
    step = art["timeline"][-1]
    assert step["warnings"] == ["a channel was dropped"]
    assert step["decisions"][0]["verdict"] == "refused"


def test_an_export_with_capture_off_says_so_rather_than_looking_complete(
        temp_db):
    import json as _json
    from core import db
    from persist.pipeline_trace import export_turn_debug
    _chat, turn_id = _turn(db)          # capture never enabled
    step_id = db.qi("INSERT INTO steps(turn_id,key,label,ord) "
                    "VALUES(?,'narrator','Narrator',0)", (turn_id,))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (step_id, _json.dumps({"prose": "she turned"}), 1.0))
    art = export_turn_debug(turn_id)
    assert art["calls_captured"] == 0
    assert art["capture_was_on"] is False, (
        "an artifact with no captured calls must SAY it captured none -- "
        "silence here reads as 'the turn made no calls'")
    assert [e["kind"] for e in art["timeline"]] == ["step"]


@pytest.fixture
def host_client(temp_db):
    """A client that has completed host setup. The debug-capture route sits
    behind host auth like every other settings write."""
    from fastapi.testclient import TestClient
    from web import app as app_module
    from web import guest_access as guest

    with TestClient(app_module.app) as client:
        r = client.post("/api/auth/setup",
                        json={"username": "host", "password": "pw12345"})
        assert r.status_code == 200, r.text
        yield client
    guest.reset_host_account()
    guest._join_attempts.clear()
    guest._login_attempts.clear()


class TestTheSettingsToggle:
    """Capture is reachable from the API panel, and off is a real default.

    It shipped readable only from a setting row or an env var, which meant the
    feature existed and nobody could turn it on -- the same shape as the export
    that had no route.
    """

    def test_the_route_round_trips_and_applies_the_level(self, host_client):
        from core import db

        out = host_client.put("/api/debug_capture",
                              json={"enabled": True, "bodies": "full",
                                    "log_level": "DEBUG"}).json()
        assert out == {"enabled": True, "bodies": "full", "log_level": "DEBUG"}
        assert db.get_setting("llm_capture_enabled") == "1"

        import logging
        from core.logging_utils import logger
        assert logger.level == logging.DEBUG, (
            "the level must apply now, not at next start -- an engine you have "
            "to restart to make talkative has already lost the turn")

    def test_a_nonsense_mode_is_refused_rather_than_stored(self, host_client):
        from core import db

        db.set_setting("llm_capture_bodies", "hash_only")
        assert host_client.put(
            "/api/debug_capture",
            json={"bodies": "everything"}).status_code == 400
        assert host_client.put(
            "/api/debug_capture",
            json={"log_level": "CHATTY"}).status_code == 400
        assert db.get_setting("llm_capture_bodies") == "hash_only"

    def test_an_absent_key_leaves_that_setting_alone(self, host_client):
        """The panel sends all three, but a future toggle may send one."""
        from core import db

        db.set_setting("llm_capture_bodies", "full")
        out = host_client.put(
            "/api/debug_capture", json={"enabled": True}).json()
        assert out["bodies"] == "full"
