"""Artifacts: a claim on a wall, acquired by reading, stopped by tearing down.

Every test here defends the floor against the two cheap implementations the
design warns about: a notice that broadcasts into every mind in the room
(knowledge by proximity, the thing the whole carrier network exists to
refuse), and a notice that is really a message box (undestructible, so
removing it changes nothing). And the ceiling must be dress, never
information: the floor is pinned complete with no model anywhere.
"""

from __future__ import annotations

import json
import time
import types

SQUARE, GATE, KEEP = "square", "gate", "keep"

THE_NEWS = "three riders took the grain at the square"


def _edges(*targets):
    return [{"to": t, "barrier": "open"} for t in targets]


def _scene():
    return {
        "rooms": {
            SQUARE: {"name": "The Square", "adjacent": _edges(GATE)},
            GATE: {"name": "The Gate", "adjacent": _edges(SQUARE, KEEP)},
            KEEP: {"name": "The Keep", "adjacent": _edges(GATE)},
        },
        "positions": {"Maelor": SQUARE, "Sera": SQUARE, "Corin": KEEP},
    }


def _world(db, *, retellings=0, claim=THE_NEWS):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Notice story", "", time.time()))
    chars = {}
    for name in ("Maelor", "Sera", "Corin"):
        sheet = json.dumps({"identity": {"name": name,
                                         "uid": "%s_uid" % name.lower()}})
        char_id = db.qi(
            "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
            (name, sheet, "{}", time.time()))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) "
              "VALUES(?,?,?,'{}')", (cid, char_id, "active"))
        chars[name] = char_id
    db.qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
          (json.dumps({"carried_reports": [{
              "world_event_id": "event:grain", "source_event_id": "",
              "claim": claim, "kind": "consequence",
              "occurred_at": 10.0, "acquired_turn": 1,
              "acquired_location": SQUARE, "current_location": SQUARE,
              "route": [SQUARE], "hops": 0, "retellings": retellings,
              "told_by": "", "provenance": "witnessed_surface"}]}),
           cid, chars["Maelor"]))
    ctx = types.SimpleNamespace(
        chat=types.SimpleNamespace(id=cid),
        turn=types.SimpleNamespace(id=1, idx=4, frame_id=None),
    )
    return cid, chars, _scene(), ctx


def _post(**over):
    op = {"op": "post", "poster": "Maelor", "world_event_id": "event:grain",
          "description": "a notice nailed to the well post"}
    op.update(over)
    return op


def _run(ctx, scene, ops):
    from story.artifacts import run_artifacts

    return run_artifacts(ctx, scene, list(ops))


def _standing(db, cid):
    return db.wget(cid, "artifacts", []) or []


def _reports(db, cid, char_id):
    row = db.q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
               (cid, char_id), one=True)
    return (json.loads(row["state"] or "{}")).get("carried_reports") or []


def test_a_posted_notice_informs_only_whoever_reads_it(temp_db):
    """Knowledge by proximity is the defect the whole carrier network exists
    to refuse: Sera standing beside the post learns nothing until a beat has
    her READ it -- and then holds the claim with provenance recording that
    she read it rather than was told it, attributed to the paper, never to
    the man who nailed it up."""
    cid, chars, scene, ctx = _world(temp_db)
    metrics, rejected = _run(ctx, scene, [_post()])
    assert metrics["artifacts_posted"] == 1 and not rejected
    artifact = _standing(temp_db, cid)[0]
    assert artifact["status"] == "posted" and artifact["room"] == SQUARE

    # Standing in the room delivered nothing.
    assert _reports(temp_db, cid, chars["Sera"]) == []

    metrics, rejected = _run(ctx, scene, [
        {"op": "read", "reader": "Sera", "artifact_id": artifact["uid"]}])
    assert metrics["artifacts_read"] == 1 and not rejected
    report = _reports(temp_db, cid, chars["Sera"])[0]
    assert report["claim"] == THE_NEWS          # a copy, not a mouth
    assert report["retellings"] == 0
    assert report["provenance"] == "read"
    assert report["told_by"] == "a notice nailed to the well post"


def test_the_perception_surface_shows_paper_and_never_the_claim(temp_db):
    """From across a square a bill is paper: if the room surface carried the
    claim, walking past a wall would broadcast it into every mind present
    and the read op would be ceremony."""
    from agents.common import artifacts_for_room

    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_post()])
    seen = artifacts_for_room(cid, scene, SQUARE)
    assert seen and seen[0]["artifact_id"].startswith("artifact:")
    assert "grain" not in json.dumps(seen)
    assert artifacts_for_room(cid, scene, KEEP) == []


def test_a_bill_posted_from_a_rumor_carries_the_rumor_not_the_truth(temp_db):
    """The copy-of-a-copy rule: writing is not a retelling (the sealed
    letter precedent), so a notice posted from a twice-told story carries
    that story's already-faded wording at its faded count -- never the
    original the poster no longer holds, and never one fainter than what
    the poster would say aloud."""
    from world import degradation

    faded = degradation.degrade(THE_NEWS, 2, places=("the square",))
    cid, chars, scene, ctx = _world(temp_db, retellings=2, claim=faded)
    _run(ctx, scene, [_post()])
    artifact = _standing(temp_db, cid)[0]
    _run(ctx, scene, [
        {"op": "read", "reader": "Sera", "artifact_id": artifact["uid"]}])
    report = _reports(temp_db, cid, chars["Sera"])[0]
    assert report["claim"] == faded
    assert report["retellings"] == 2
    assert "three" not in report["claim"]


def test_tearing_a_bill_down_stops_it_informing_anyone(temp_db):
    """The artifact equivalent of silencing a courier, and what makes a
    notice part of the world rather than a message box: after it comes
    down, a read is refused, the room surface is bare, and nobody learns."""
    from agents.common import artifacts_for_room

    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_post()])
    artifact = _standing(temp_db, cid)[0]
    metrics, rejected = _run(ctx, scene, [
        {"op": "remove", "by": "Sera", "artifact_id": artifact["uid"],
         "manner": "torn down"}])
    assert metrics["artifacts_removed"] == 1 and not rejected

    metrics, rejected = _run(ctx, scene, [
        {"op": "read", "reader": "Sera", "artifact_id": artifact["uid"]}])
    assert metrics["artifacts_read"] == 0 and len(rejected) == 1
    assert _reports(temp_db, cid, chars["Sera"]) == []
    assert artifacts_for_room(cid, scene, SQUARE) == []


def test_a_false_bill_posts_exactly_like_a_true_one(temp_db):
    """Wrongness stays diegetic: a wanted bill naming somebody for a thing
    they never did enters through the same physics as a true one. The
    poster's own row says `invented` -- they know what they did -- and
    nothing a reader can reach ever marks the copy false."""
    cid, chars, scene, ctx = _world(temp_db)
    metrics, rejected = _run(ctx, scene, [_post(
        world_event_id="",
        claim="the boy from the Fenwater poisoned the wells",
        description="a wanted bill with a clumsy woodcut")])
    assert metrics["artifacts_posted"] == 1 and not rejected
    own = [r for r in _reports(temp_db, cid, chars["Maelor"])
           if r["provenance"] == "invented"]
    assert own and own[0]["world_event_id"].startswith("claim:")

    artifact = _standing(temp_db, cid)[0]
    _run(ctx, scene, [
        {"op": "read", "reader": "Sera", "artifact_id": artifact["uid"]}])
    report = _reports(temp_db, cid, chars["Sera"])[0]
    assert report["provenance"] == "read"       # nothing marks it false
    assert report["world_event_id"].startswith("claim:")


def test_posting_requires_holding_and_a_body_at_the_wall(temp_db):
    """The firewall, arriving through the newest door: without the holding
    check the Director could publish any fact to any room by writing one
    op, and without the room checks a bill could be posted, read or torn
    down from across the map -- a menu, not a wall."""
    cid, chars, scene, ctx = _world(temp_db)
    metrics, rejected = _run(ctx, scene, [_post(poster="Sera")])
    assert metrics["artifacts_posted"] == 0 and len(rejected) == 1

    metrics, rejected = _run(ctx, scene, [_post(room=KEEP)])
    assert metrics["artifacts_posted"] == 0 and len(rejected) == 1

    _run(ctx, scene, [_post()])
    artifact = _standing(temp_db, cid)[0]
    metrics, rejected = _run(ctx, scene, [
        {"op": "read", "reader": "Corin", "artifact_id": artifact["uid"]}])
    assert metrics["artifacts_read"] == 0 and len(rejected) == 1
    metrics, rejected = _run(ctx, scene, [
        {"op": "remove", "by": "Corin", "artifact_id": artifact["uid"]}])
    assert metrics["artifacts_removed"] == 0 and len(rejected) == 1
    assert _standing(temp_db, cid)[0]["status"] == "posted"


def test_checkpoint_restore_takes_the_bill_off_the_wall(temp_db):
    """New durable state must rewind with the story: a bill that survived a
    rollback would inform readers of a posting that no longer happened, and
    a restored removal would resurrect one already torn down."""
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint

    cid, chars, scene, ctx = _world(temp_db)
    ensure_checkpoint(cid, 4)
    _run(ctx, scene, [_post()])
    assert _standing(temp_db, cid)
    restore_checkpoint(cid, 4)
    assert _standing(temp_db, cid) == []

    _run(ctx, scene, [_post()])
    ensure_checkpoint(cid, 5)
    artifact = _standing(temp_db, cid)[0]
    _run(ctx, scene, [
        {"op": "remove", "by": "Sera", "artifact_id": artifact["uid"]}])
    assert _standing(temp_db, cid)[0]["status"] == "removed"
    restore_checkpoint(cid, 5)
    assert _standing(temp_db, cid)[0]["status"] == "posted"


def test_the_archive_carries_the_wall(temp_db):
    """Archive export/import must move artifacts with the chat, or an
    imported story would arrive with every notice quietly gone."""
    from persist.chat_archive import ChatArchiveService

    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_post()])
    blob = ChatArchiveService.export_chat(None, cid)
    assert any("artifacts" in key for key in (blob.get("world") or {}))


def test_the_floor_is_whole_with_no_model_and_no_ceiling_setting(temp_db):
    """The ceiling is dress, never information: with no model configured
    and the ceiling off, `text` stays empty, nothing schedules, and every
    verb above still worked -- which is what 'build the floor first' means.
    """
    from story.artifacts import schedule_artifact_wording

    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_post()])
    artifact = _standing(temp_db, cid)[0]
    assert artifact["text"] == ""

    # Floor setting: the ceiling gate refuses to spend.
    temp_db.wset(cid, "living_world", {"rumor_ledger": "floor"})
    assert schedule_artifact_wording(ctx) is None


def test_the_ceiling_schedules_a_job_and_stops_paying_after_failures(temp_db):
    """Fail toward not spending: with the ceiling ON, one job is queued for
    the unworded bill -- and once the mint has failed its capped attempts,
    nothing schedules again, so a dead provider costs two cheap failures
    rather than a retry per beat for the rest of the story."""
    from core import jobs
    from story.artifacts import schedule_artifact_wording

    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_post()])
    temp_db.wset(cid, "living_world", {"rumor_ledger": "ceiling"})

    submitted = []
    real_submit = jobs.submit

    def fake_submit(chat_id, key, fn, base_turn=None):
        submitted.append({"chat_id": chat_id, "key": key,
                          "base_turn": base_turn})
        return types.SimpleNamespace(
            as_dict=lambda: {"key": key, "state": "pending"})

    jobs.submit = fake_submit
    try:
        job = schedule_artifact_wording(ctx)
        assert job is not None and len(submitted) == 1
        assert submitted[0]["key"].startswith("artifact_wording:")
        assert submitted[0]["base_turn"] == 4

        artifact = dict(_standing(temp_db, cid)[0], wording_failures=2)
        temp_db.wset(cid, "artifacts", [artifact])
        assert schedule_artifact_wording(ctx) is None
    finally:
        jobs.submit = real_submit


def test_wording_lands_only_while_the_bill_still_stands(temp_db):
    """The `land_profile_ticks` discipline for the wording mint: a job that
    returns after the player rewound past the posting, or tore the bill
    down, must discard its text -- and a failed mint counts toward the cap
    so a dead provider stops being paid for."""
    from story.artifacts import land_artifact_wording

    cid, chars, scene, ctx = _world(temp_db)
    _run(ctx, scene, [_post()])
    artifact = _standing(temp_db, cid)[0]

    record = land_artifact_wording(
        cid, artifact["uid"], "BY ORDER: several riders are sought.", "",
        base_turn=4)
    assert record["landed"]
    assert _standing(temp_db, cid)[0]["text"].startswith("BY ORDER")

    # A second landing is refused: the bill is already worded.
    record = land_artifact_wording(
        cid, artifact["uid"], "different words", "", base_turn=4)
    assert not record["landed"]

    # A failure lands as a counted failure, not silence.
    temp_db.wset(cid, "artifacts", [dict(_standing(temp_db, cid)[0],
                                         text="")])
    record = land_artifact_wording(
        cid, artifact["uid"], "", "provider unreachable", base_turn=4)
    assert not record["landed"]
    assert _standing(temp_db, cid)[0]["wording_failures"] == 1

    # Torn down before the job returned: the wording dies with the bill.
    _run(ctx, scene, [
        {"op": "remove", "by": "Sera", "artifact_id": artifact["uid"]}])
    record = land_artifact_wording(
        cid, artifact["uid"], "BY ORDER: too late.", "", base_turn=4)
    assert not record["landed"]

    # Gone entirely (a rewind): discarded, loudly, never raising.
    temp_db.wset(cid, "artifacts", [])
    record = land_artifact_wording(
        cid, artifact["uid"], "BY ORDER: to nobody.", "", base_turn=4)
    assert not record["landed"] and record["error"]
