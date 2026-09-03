"""Plot packages (`story/plot_packages.py`): the store, the lifecycle, the
closed operation table, and the author-layer invariant -- nothing a package
publishes reaches a mind except through a channel the mind has.
"""
from __future__ import annotations

import json
import time

import pytest

from story.plot_packages import (
    OPERATIONS, OPS_CAP, PACKAGES_CAP, activate_due_packages, draft_operation,
    edit_package, get_package, list_packages, new_package, package_projection,
    package_view, packages, prepare_package, preview_package, publish_package,
    remove_operation, resolve_package, retire_package, validate_package,
    visible_packages)

PLAYER = "Wren Ashby"


def _chat(db, *, book=False):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Packages", "A port at dusk.", time.time()))
    if book:
        bid = db.qi("INSERT INTO lorebooks(name,chat_id) VALUES(?,?)", ("Canon", cid))
        db.qi("INSERT INTO chat_lorebooks(chat_id,lorebook_id) VALUES(?,?)", (cid, bid))
        db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (bid, cid))
    return cid


def _scene():
    return {"location": "Port", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone and rope.",
                 "adjacent": [{"to": "warehouse", "barrier": "open_door"}]},
        "warehouse": {"name": "Warehouse", "desc": "Crates to the rafters.",
                      "adjacent": [{"to": "quay", "barrier": "open_door"}]},
    }, "positions": {PLAYER: "quay"}, "entities": {}, "attire": {}}


def _turn(db, cid, idx):
    return db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                 (cid, idx, "", time.time()))


def _story(db, *, book=False, turns=3):
    cid = _chat(db, book=book)
    db.wset(cid, "scene", _scene())
    for i in range(turns):
        _turn(db, cid, i)
    return cid


def _ready(db, cid, ops=(), **fields):
    head = {k: fields.pop(k) for k in ("spoiler_policy", "authority", "scope")
            if k in fields}
    pkg = new_package(cid, title="The Bell Without a Ringer",
                      premise="Somebody rang the drowned bell.", **head)
    if fields:
        edit_package(cid, pkg["uid"], fields)
    for op in ops:
        draft_operation(cid, pkg["uid"], op)
    return pkg["uid"]


def _rev(cid, uid):
    return get_package(cid, uid)["revision"]


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_a_draft_is_filed_pinned_and_revisioned(self, temp_db):
        cid = _story(temp_db)
        pkg = new_package(cid, title="Bell", premise="p")
        assert pkg["status"] == "draft" and pkg["revision"] == 1
        assert pkg["uid"].startswith("plot:bell:")
        assert pkg["base"]["turn_idx"] == 2
        edited = edit_package(cid, pkg["uid"], {"questions": ["Who rang it?"]})
        assert edited["revision"] == 2
        assert edited["questions"][0]["id"].startswith("question_")
        assert [h["action"] for h in edited["provenance"]["history"]] == [
            "created", "edited"]

    def test_publish_needs_a_validation_at_the_revision(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid)
        with pytest.raises(ValueError, match="validate"):
            publish_package(cid, uid, expected_revision=1)
        verdict = validate_package(cid, uid)
        assert verdict["ok"] and verdict["at_revision"] == 1
        edit_package(cid, uid, {"premise": "changed"})
        with pytest.raises(ValueError, match="validate"):
            publish_package(cid, uid, expected_revision=2)
        validate_package(cid, uid)
        with pytest.raises(ValueError, match="revision 2, not 1"):
            publish_package(cid, uid, expected_revision=1)
        out = publish_package(cid, uid, expected_revision=2)
        assert out["published_turn"] == 2 and out["visible_from_turn"] == 3
        assert get_package(cid, uid)["status"] == "published"

    def test_visibility_is_next_turn_and_activation_follows(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid)
        validate_package(cid, uid)
        publish_package(cid, uid, expected_revision=_rev(cid, uid))
        # The turn it was published in (the latest row, idx 2) does not see it.
        assert visible_packages(cid, 2) == []
        assert activate_due_packages(cid, 2) == []
        assert [p["uid"] for p in visible_packages(cid, 3)] == [uid]
        assert activate_due_packages(cid, 3) == [uid]
        assert get_package(cid, uid)["status"] == "active"
        assert get_package(cid, uid)["activated_turn"] == 3
        assert activate_due_packages(cid, 4) == []
        resolved = resolve_package(cid, uid, note="the ringer confessed")
        assert resolved["status"] == "resolved"
        assert retire_package(cid, uid)["status"] == "retired"

    def test_a_landed_package_is_not_edited_except_by_a_superseding_truth(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid, truths=[{"text": "The sexton rang it."}])
        validate_package(cid, uid)
        publish_package(cid, uid, expected_revision=_rev(cid, uid))
        with pytest.raises(ValueError, match="superseding truth"):
            edit_package(cid, uid, {"premise": "new"})
        old_id = get_package(cid, uid)["truths"][0]["id"]
        with pytest.raises(ValueError, match="reason"):
            edit_package(cid, uid, {"truths": [{"supersedes": old_id, "text": "x"}]})
        pkg = edit_package(cid, uid, {"truths": [{"supersedes": old_id,
                                                  "text": "The verger rang it."}]},
                           reason="the sexton was at sea that night")
        assert len(pkg["truths"]) == 2
        assert pkg["truths"][0]["superseded_by"] == pkg["truths"][1]["id"]
        assert pkg["truths"][1]["supersedes"] == old_id
        assert pkg["truths"][1]["reason"].startswith("the sexton")
        assert pkg["revision"] == 3
        with pytest.raises(ValueError, match="already superseded"):
            edit_package(cid, uid, {"truths": [{"supersedes": old_id, "text": "y"}]},
                         reason="again")
        with pytest.raises(ValueError, match="takes no new operations"):
            draft_operation(cid, uid, {"op": "schedule_event", "summary": "s"})

    def test_history_that_moved_without_breaking_anything_rebases(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid, ops=[{"op": "schedule_event",
                                         "summary": "the bell rings again",
                                         "due_in_turns": 2}])
        validate_package(cid, uid)
        _turn(temp_db, cid, 3)
        out = publish_package(cid, uid, expected_revision=_rev(cid, uid))
        pkg = get_package(cid, uid)
        assert out["published_turn"] == 3
        assert "rebased" in [h["action"] for h in pkg["provenance"]["history"]]
        assert pkg["base"]["turn_idx"] == 3

    def test_history_that_breaks_the_package_is_a_conflict(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid, ops=[{
            "op": "plan_rooms", "structure": {"key": "chapel", "name": "Chapel"},
            "rooms": {"drowned_chapel": {"name": "Drowned Chapel",
                                         "adjacent": [{"to": "quay"}]}}}])
        validate_package(cid, uid)
        # The story walks into the chapel and describes it before publish.
        scene = temp_db.wget(cid, "scene")
        scene["rooms"]["drowned_chapel"] = {"name": "Drowned Chapel",
                                            "desc": "A bell half under."}
        temp_db.wset(cid, "scene", scene)
        _turn(temp_db, cid, 3)
        with pytest.raises(ValueError, match="conflict"):
            publish_package(cid, uid, expected_revision=_rev(cid, uid))
        pkg = get_package(cid, uid)
        assert pkg["status"] == "draft" and not pkg["validation"]["ok"]
        assert "conflict" in [h["action"] for h in pkg["provenance"]["history"]]

    def test_the_live_cap_and_the_operation_cap(self, temp_db):
        cid = _story(temp_db)
        for i in range(PACKAGES_CAP):
            new_package(cid, title="p%d" % i)
        with pytest.raises(ValueError, match="cap"):
            new_package(cid, title="one more")
        uid = list(packages(cid))[0]
        for i in range(OPS_CAP):
            draft_operation(cid, uid, {"op": "schedule_event", "summary": "s%d" % i})
        with pytest.raises(ValueError, match="at most"):
            draft_operation(cid, uid, {"op": "schedule_event", "summary": "z"})
        assert remove_operation(cid, uid, 0)["revision"] > 1


# ---------------------------------------------------------------------------
# The closed operation table, each over its seam
# ---------------------------------------------------------------------------

class TestOperations:
    def test_an_operation_outside_the_table_is_refused_at_draft(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid)
        for kind in ("write_memory", "set_character_state", "edit_scene",
                     "sql", "", None):
            with pytest.raises(ValueError, match="not one the room may perform"):
                draft_operation(cid, uid, {"op": kind, "anything": 1})
        assert get_package(cid, uid)["operations"] == []
        # Every kind in the table names its seam and its three functions.
        for kind, spec in OPERATIONS.items():
            assert spec["seam"] and callable(spec["shape"]) and callable(spec["preview"])
            assert callable(spec["prepare"] if spec["long"] else spec["apply"])

    def test_rooms_plans_bills_events_and_needs_land_through_their_seams(self, temp_db):
        from story.artifacts import standing_artifacts
        from story.authored_events import due_authored_events
        from world.planned_entities import planned_entities
        from world.planning_needs import file_planning_need, open_planning_needs
        from world.structure import planned_room_ids
        cid = _story(temp_db)
        need, _ = file_planning_need(cid, {"kind": "person",
                                          "surface": {"name": "Sexton", "room": "quay"}})
        uid = _ready(temp_db, cid, ops=[
            {"op": "plan_rooms", "structure": {"key": "chapel", "name": "Chapel"},
             "rooms": {"drowned_chapel": {"name": "Drowned Chapel",
                                          "purpose": "worship",
                                          "adjacent": [{"to": "quay", "barrier": "open"}]}}},
            {"op": "plan_entity", "kind": "person", "name": "Sexton Abel Crane",
             "role": "sexton", "brief": {"purpose": "Keeps the bell.",
                                         "truths": "Rang it.",
                                         "where": "drowned_chapel"},
             "answers_need": need["uid"]},
            {"op": "post_artifact", "room": "quay",
             "description": "a bill about the bell", "text": "The bell rang."},
            {"op": "schedule_event", "summary": "the bell rings again",
             "due_in_turns": 1},
        ])
        preview = preview_package(cid, uid)
        assert preview["errors"] == []
        kinds = [c["kind"] for c in preview["changes"]]
        assert kinds == ["rooms_planted", "plan_filed", "artifact_posted",
                         "event_scheduled"]
        validate_package(cid, uid)
        out = publish_package(cid, uid, expected_revision=_rev(cid, uid))
        assert [a["op"] for a in out["applied"]] == [
            "plan_rooms", "plan_entity", "post_artifact", "schedule_event"]
        assert "drowned_chapel" in planned_room_ids(cid)
        plans = planned_entities(cid)
        assert [p["name"] for p in plans.values()] == ["Sexton Abel Crane"]
        assert list(plans.values())[0]["source"] == "writers_room"
        assert open_planning_needs(cid) == []
        bills = standing_artifacts(cid)
        assert bills[0]["room"] == "quay" and bills[0]["authored"] == "writers_room"
        assert bills[0]["text"] == "The bell rang."
        due = due_authored_events(cid, 3)
        assert [d["summary"] for d in due] == ["the bell rings again"]
        row = temp_db.q("SELECT payload FROM scheduled_events WHERE chat_id=?",
                        (cid,), one=True)
        assert json.loads(row["payload"])["source"] == "writers_room"

    def test_a_reserved_identity_and_a_room_nobody_holds_are_refused(self, temp_db):
        from world.planned_entities import add_planned_entity
        cid = _story(temp_db)
        add_planned_entity(cid, {"kind": "person", "name": "Old Sel",
                                 "aliases": ["the netmender"]})
        uid = _ready(temp_db, cid, ops=[
            {"op": "plan_entity", "name": "The Netmender", "brief": {"where": "nowhere"}},
            {"op": "post_artifact", "room": "chapel_loft", "description": "a bill"},
            {"op": "answer_need", "need_uid": "need_nobody", "fill": {"x": 1}},
        ])
        preview = preview_package(cid, uid)
        assert any("reserved identity" in e for e in preview["errors"])
        assert any("exists nowhere" in e for e in preview["errors"])
        assert any("not open" in e for e in preview["errors"])
        verdict = validate_package(cid, uid)
        assert not verdict["ok"]
        with pytest.raises(ValueError, match="validate"):
            publish_package(cid, uid, expected_revision=_rev(cid, uid))

    def test_a_described_room_is_a_retcon_not_a_plan(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid, ops=[{
            "op": "plan_rooms", "structure": {"key": "port", "name": "Port"},
            "rooms": {"quay": {"name": "Quay"}}}])
        preview = preview_package(cid, uid)
        assert any("retcon" in e for e in preview["errors"])

    def test_lore_files_through_promote_with_the_package_as_adjudicator(self, temp_db):
        cid = _story(temp_db, book=True)
        uid = _ready(temp_db, cid, ops=[{
            "op": "file_lore", "subject_id": "drowned_bell", "subject_kind": "place",
            "keys": "drowned bell, chapel bell", "title": "The Drowned Bell",
            "content": "The chapel bell went under in the flood of the wet year.",
            "category": "event"}])
        assert preview_package(cid, uid)["errors"] == []
        validate_package(cid, uid)
        out = publish_package(cid, uid, expected_revision=_rev(cid, uid))
        entry_id = out["applied"][0]["result"]["entry_id"]
        row = temp_db.q("SELECT * FROM lore_entries WHERE id=?", (entry_id,), one=True)
        assert row["category"] == "event" and row["title"] == "The Drowned Bell"
        assert row["source_notes"].startswith("imported_canon by writers_room:plot:")
        assert "imported_canon" not in row["content"]

    def test_a_web_result_files_under_its_own_disposition_and_cites_the_page(self, temp_db):
        # The shape `story.room_research.as_lore` hands the Planner: the
        # disposition, address and date ride the op and land in provenance.
        cid = _story(temp_db, book=True)
        uid = _ready(temp_db, cid, ops=[{
            "op": "file_lore", "subject_id": "tide_tables", "subject_kind": "setting",
            "title": "Spring tides", "content": "Spring tides run highest at syzygy.",
            "category": "other", "disposition": "web_reference",
            "source_url": "https://example.org/tides", "fetched_at": "2026-09-03"}])
        assert preview_package(cid, uid)["errors"] == []
        validate_package(cid, uid)
        out = publish_package(cid, uid, expected_revision=_rev(cid, uid))
        entry_id = out["applied"][0]["result"]["entry_id"]
        row = temp_db.q("SELECT * FROM lore_entries WHERE id=?", (entry_id,), one=True)
        assert row["source_notes"].startswith(
            "web_reference https://example.org/tides fetched 2026-09-03; web_reference by")

    def test_an_unknown_disposition_is_refused_at_preview(self, temp_db):
        cid = _story(temp_db, book=True)
        uid = _ready(temp_db, cid, ops=[{
            "op": "file_lore", "subject_id": "tide_tables", "content": "x",
            "disposition": "gospel"}])
        errors = preview_package(cid, uid)["errors"]
        assert any("gospel" in e and "disposition" in e for e in errors)

    def test_lore_with_no_book_or_a_bad_subject_is_refused(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid, ops=[{
            "op": "file_lore", "subject_id": "Drowned Bell!", "content": "x"}])
        errors = preview_package(cid, uid)["errors"]
        assert any("no book" in e for e in errors)
        assert any("not an id" in e for e in errors)

    def test_long_operations_are_prepared_before_publish(self, temp_db, monkeypatch):
        import story.plot_packages as pp
        cid = _story(temp_db)
        uid = _ready(temp_db, cid, ops=[{
            "op": "request_location", "request": {"name": "Saltmarsh", "scale": "hamlet"}}])
        validate_package(cid, uid)
        with pytest.raises(ValueError, match="unprepared"):
            publish_package(cid, uid, expected_revision=_rev(cid, uid))
        calls = []

        def fake_generate(cid_, request, *, frame_id=None):
            calls.append(request["name"])
            return {"town": {"name": "Saltmarsh", "rooms": {"salt_quay": {}},
                             "charters": {"salters": {}}}}
        monkeypatch.setattr("world.charter_runtime.generate_lived_location",
                            fake_generate)
        out = prepare_package(cid, uid)
        assert out["prepared"] == [0] and calls == ["Saltmarsh"]
        op = get_package(cid, uid)["operations"][0]
        assert op["prepared"]["rooms"] == ["salt_quay"]
        assert op["prepared"]["charters"] == ["salters"]
        # Preparing again runs nothing: the record says it is done.
        assert prepare_package(cid, uid)["prepared"] == [] and calls == ["Saltmarsh"]
        result = publish_package(cid, uid, expected_revision=_rev(cid, uid))
        assert result["applied"][0]["result"]["summary"] == "Saltmarsh"

    def test_authority_is_honoured(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid, authority={"may_create_people": False},
                     ops=[{"op": "plan_entity", "name": "Anyone", "kind": "person"}])
        assert any("does not permit creating people" in e
                   for e in preview_package(cid, uid)["errors"])

    def test_evidence_is_evidence_and_a_clock_has_a_due(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid, truths=[{"id": "truth_1", "text": "T"}],
                     evidence=[{"text": "a wet rope"}],
                     clocks=[{"text": "the tide"}])
        errors = preview_package(cid, uid)["errors"]
        assert any("is a label, not evidence" in e for e in errors)
        assert any("has no due" in e for e in errors)
        uid2 = _ready(temp_db, cid, truths=[{"id": "truth_1", "text": "T"}],
                      evidence=[{"text": "a wet rope", "origin": "the ringer",
                                 "location": "quay", "bears_on": ["truth_1"],
                                 "admission_path": "seen on the quay"}],
                      clocks=[{"text": "the tide", "due_turns": 4}])
        assert preview_package(cid, uid2)["errors"] == []


# ---------------------------------------------------------------------------
# Sealed packages and views
# ---------------------------------------------------------------------------

class TestViews:
    def test_a_sealed_package_shows_what_is_in_motion_never_what_it_is(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid, spoiler_policy="sealed",
                     truths=[{"text": "The verger drowned the sexton."}],
                     clocks=[{"text": "the inquest", "label": "an inquest",
                              "due_turns": 6}])
        view = package_view(cid, uid)
        assert view["sealed"] and "truths" not in view
        assert view["counts"]["truths"] == 1
        assert view["clocks"] == [{"id": view["clocks"][0]["id"], "label": "an inquest",
                                   "due_story_hours": None, "due_turns": 6}]
        assert "verger" not in json.dumps(view)
        revealed = package_view(cid, uid, reveal=True)
        assert revealed["truths"][0]["text"].startswith("The verger")
        assert "verger" not in json.dumps(list_packages(cid))
        # An open package shows itself whole.
        open_uid = _ready(temp_db, cid, truths=[{"text": "Open truth."}])
        assert package_view(cid, open_uid)["truths"][0]["text"] == "Open truth."
        proj = package_projection(get_package(cid, uid))
        assert proj["validation"] == {"ok": False, "errors": 0, "warnings": 0,
                                      "at_revision": None}

    def test_a_sealed_truth_with_one_path_warns(self, temp_db):
        cid = _story(temp_db)
        uid = _ready(temp_db, cid, spoiler_policy="sealed",
                     truths=[{"id": "truth_1", "text": "T"}],
                     evidence=[{"text": "e", "origin": "o", "location": "quay",
                                "bears_on": ["truth_1"], "admission_path": "p"}])
        warnings = preview_package(cid, uid)["warnings"]
        assert any("1 evidence path" in w for w in warnings)
        assert any("envelope" in w for w in warnings)


# ---------------------------------------------------------------------------
# The author layer
# ---------------------------------------------------------------------------

class TestAuthorLayer:
    def test_a_package_cannot_write_a_mind(self, temp_db):
        """The room publishes a whole package -- rooms, a plan, a bill, an
        event, lore, a need answered -- and no character's state, no memory
        row and no observer's view changes. What it placed is in the WORLD;
        a mind meets it by seeing it."""
        from story.scene import recent_events_for_observer
        cid = _story(temp_db, book=True)
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,created) VALUES(?,?,?)",
            ("Mara Quill", json.dumps({"name": "Mara Quill"}), time.time()))
        temp_db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
                   (cid, char_id, "active", json.dumps({"mood": "calm"})))
        temp_db.qi("INSERT INTO memories(chat_id,char_id,turn_idx,kind,content) "
                   "VALUES(?,?,?,?,?)", (cid, char_id, 1, "episodic", "The tide came in."))
        temp_db.qi("INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)",
                   (cid, None, "Wren walked the quay."))
        from world.planning_needs import file_planning_need
        need, _ = file_planning_need(cid, {"kind": "thing", "surface": {"name": "the rope"}})

        def snapshot():
            return {
                "chars": [dict(r) for r in temp_db.q(
                    "SELECT char_id, status, state, sheet FROM chat_chars "
                    "WHERE chat_id=?", (cid,))],
                "memories": [dict(r) for r in temp_db.q(
                    "SELECT char_id, turn_idx, kind, content FROM memories "
                    "WHERE chat_id=?", (cid,))],
                "known": temp_db.wget(cid, "known", {}),
                "relationships": [dict(r) for r in temp_db.q(
                    "SELECT key, value FROM world WHERE chat_id=? AND "
                    "key LIKE 'relationships:%'", (cid,))],
                "view": recent_events_for_observer(cid, "Mara Quill", n=5,
                                                   frame_id=None),
            }
        before = snapshot()
        uid = _ready(temp_db, cid, truths=[{"text": "The verger did it."}], ops=[
            {"op": "plan_rooms", "structure": {"key": "chapel", "name": "Chapel"},
             "rooms": {"chapel_nave": {"name": "Nave", "adjacent": [{"to": "quay"}]}}},
            {"op": "plan_entity", "name": "Verger Hale", "role": "verger",
             "brief": {"where": "chapel_nave", "truths": "Did it."}},
            {"op": "post_artifact", "room": "quay", "description": "a bill"},
            {"op": "schedule_event", "summary": "the verger is seen", "due_in_turns": 1},
            {"op": "file_lore", "subject_id": "chapel_nave", "subject_kind": "room",
             "content": "The nave floods at the spring tide.", "category": "layout"},
            {"op": "close_need", "need_uid": need["uid"], "reason": "not needed"},
        ])
        validate_package(cid, uid)
        publish_package(cid, uid, expected_revision=_rev(cid, uid))
        activate_due_packages(cid, 3)
        assert snapshot() == before
        # And the package's own text is nowhere a mind reads: not in the
        # events row, not in any lore entry, not in the scene.
        haystack = json.dumps([dict(r) for r in temp_db.q(
            "SELECT content FROM events WHERE chat_id=?", (cid,))])
        haystack += json.dumps([dict(r) for r in temp_db.q(
            "SELECT content FROM lore_entries")])
        haystack += json.dumps(temp_db.wget(cid, "scene"))
        assert "verger did it" not in haystack.casefold()

    def test_the_operation_table_names_no_mind_seam(self):
        import inspect
        import story.plot_packages as pp
        source = inspect.getsource(pp)
        for forbidden in ("chat_chars", "memories", "add_memory", "write_memory",
                          "commit_memory", "relationships:", "psychology",
                          "perception", "composer"):
            # Code lines only: an import or a call. Prose (the module's own
            # docstring naming what it refuses) is not a seam.
            occurrences = [line for line in source.splitlines()
                           if forbidden in line and not line.strip().startswith("#")
                           and ("import " in line or "(" in line)]
            # `chat_chars` is read (names) in the snapshot, never written.
            occurrences = [l for l in occurrences if "SELECT" not in l]
            assert not occurrences, (forbidden, occurrences)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def test_packages_survive_archive_checkpoint_and_frame(temp_db):
    from persist.checkpoints import ensure_checkpoint, restore_checkpoint
    from web import app
    cid = _story(temp_db)
    uid = _ready(temp_db, cid, truths=[{"text": "T"}])
    ensure_checkpoint(cid, 1)
    validate_package(cid, uid)
    publish_package(cid, uid, expected_revision=_rev(cid, uid))
    exported = app.chat_export(cid)
    assert "plot_packages" in exported["world"]
    imported = app.chat_import({"data": exported})
    assert get_package(imported["id"], uid)["status"] == "published"
    assert get_package(imported["id"], uid)["truths"][0]["text"] == "T"
    restore_checkpoint(cid, 1)
    assert get_package(cid, uid)["status"] == "draft"
    from core.db import FRAME_SCOPED_WORLD_KEYS
    assert "plot_packages" in FRAME_SCOPED_WORLD_KEYS
    # Another era holds no package of this one's.
    assert packages(cid, frame_id=7) == {}
