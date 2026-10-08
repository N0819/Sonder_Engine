"""A planned room the player can see into, or is heading for, is built
before anyone walks in.

The owner's ruling (2026-10-08): "Between turns, each planned room the player
can see into or is heading for is designed once and put into the world, so it
exists before they walk in and the view through a doorway has something real
in it. This replaces the hidden-draft predevelopment and is on by default."

What it replaced kept its designs in a hidden cache read only when a beat
ENTERED the room: on the Brackwater run (chat 166, 30 beats) 131 designer
calls made 25 designs, at least 19 of which never reached a beat, and a
planned room seen through a doorway stayed an empty stub until somebody went
in. Now the design is PREPARED out of band (the commit tail's job, which
writes its cache and never the scene) and INSTALLED in band: the next beat's
interpret opens on the scene with the finished designs built in, puts them in
the beat as its first event, perception previews them, and the commit -- still
the one scene writer -- persists them with the registry projection.
"""

from __future__ import annotations

import copy
import json
import time

import pytest

import agents.director as director
from agents import director_rooms
from llm import decisions
from world.structure import rooms_in_view_or_ahead

from tests.director_fakes import _action_interp, _fake_agent, _make_ctx


GALLERY = {
    "name": "Lamp Gallery",
    "desc": "A narrow iron walk girdling the lantern, its rail cold with salt.",
    "extent": {"w": 6, "d": 2},
    "light": "dim",
    "adjacent": [{"to": "keeper_room", "barrier": "open", "dir": "s"}],
    "anchors": {"rail": {"desc": "an iron rail, salt-pitted, at waist height",
                         "dir": "n", "height": "waist", "footprint": "run"}},
}

WATCH = {"name": "Watch Room", "desc": "A desk under a window, the log open on it.",
         "adjacent": [{"to": "keeper_room", "barrier": "open", "dir": "e"}]}

SCENE = {
    "location": "Blackthorn Lighthouse",
    "rooms": {
        "keeper_room": {
            "name": "Keeper's Room",
            "desc": "A round stone room under the lantern.",
            "extent": {"w": 5, "d": 5},
            "adjacent": [
                {"to": "lamp_gallery", "barrier": "open", "dir": "n"},
                {"to": "oil_store", "barrier": "closed_door", "dir": "e"},
            ],
        },
        "lamp_gallery": {"name": "Lamp Gallery", "planned": True,
                         "purpose": "the keeper's walk round the light",
                         "adjacent": [{"to": "keeper_room", "barrier": "open",
                                       "dir": "s"}]},
        "oil_store": {"name": "Oil Store", "planned": True,
                      "purpose": "oil, wicks and spare glass",
                      "adjacent": [{"to": "keeper_room",
                                    "barrier": "closed_door", "dir": "w"}]},
    },
    "positions": {"The Stranger": "keeper_room", "Mara": "keeper_room"},
    "entities": {},
    "attire": {},
    "overlays": {},
}


def _story(temp_db):
    """A chat on SCENE with a canon book, so the commit's room registry has
    a book to file the rooms under."""
    ctx = _make_ctx(temp_db, scene=SCENE, interp=_action_interp())
    canon = temp_db.qi("INSERT INTO lorebooks(name,chat_id,book_type) VALUES(?,?,?)",
                       ("Canon", ctx.chat.id, "general"))
    temp_db.qi("UPDATE chats SET lorebook_id=? WHERE id=?", (canon, ctx.chat.id))
    ctx.chat.lorebook_id = canon
    return ctx


def _wait(job):
    deadline = time.monotonic() + 10.0
    while job.state in ("pending", "running") and time.monotonic() < deadline:
        time.sleep(0.02)
    assert job.state == "done", job.as_dict()
    return job


def _designer(calls, rooms=None):
    """A room author that drafts each room it owes whole and submits."""
    def answer(role, step_key, system, payload, **kw):
        calls.append({"step_key": step_key, "payload": payload})
        owed = list((payload.get("develop") or {}))
        drafts = [{"tool": "draft_room", "args": {
            "room_id": rid, "room": copy.deepcopy((rooms or {}).get(rid) or {
                "name": rid.replace("_", " ").title(),
                "desc": f"The {rid.replace('_', ' ')}, as the plan has it."})}}
            for rid in owed]
        return {"calls": drafts + [{"tool": "submit", "args": {}}]}
    return answer


def _prepare(temp_db, monkeypatch, ctx, rooms=None, calls=None):
    import agents.common as common
    calls = [] if calls is None else calls
    monkeypatch.setattr(common, "_agent_json", _designer(calls, rooms))
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    return temp_db.wget(ctx.chat.id, director_rooms.PREPARED_KEY) or {}


def _decide(entered=()):
    """The decision model: every channel granted, a walk never stopped, and
    the planned rooms named in `entered` entered."""
    def answer(state, questions):
        out = {}
        for key in questions:
            if key.startswith(("walk__", "ended:")):
                p = 0.01
            elif key.startswith("enter__"):
                p = 0.95 if key[len("enter__"):] in entered else 0.01
            elif key.startswith("room_done"):
                p = 0.01
            else:
                p = 0.95
            out[key] = {"type": "noul", "noul": p}
        return out
    return answer


def _beat_agents(calls, prose="Mara looks up at the gallery rail.", places=None):
    return _fake_agent(calls, {
        "director_prose": {"prose": prose, **({"places": places} if places else {})},
        "director_specialist": {"events": [
            {"source_entity_id": "character:1", "event": "Mara looks up.",
             "item_names": ["Mara"], "transforms": []}]},
        "director_rooms": {"calls": [{"tool": "submit", "args": {}}]},
    })


# ---- on by default ---------------------------------------------------------

def test_rooms_in_view_are_built_by_default_and_a_setting_turns_it_off(
        temp_db, monkeypatch):
    ctx = _story(temp_db)
    assert director_rooms.predevelopment_enabled() is True
    calls = []
    cache = _prepare(temp_db, monkeypatch, ctx, {"lamp_gallery": GALLERY}, calls)
    assert cache["lamp_gallery"]["clean"] is True
    assert calls, "the job ran with no setting at all"

    temp_db.set_setting(director_rooms.PREDEVELOP_SETTING, "0")
    assert director_rooms.predevelopment_enabled() is False
    assert director_rooms.schedule_room_predevelopment(ctx) is None
    scene = temp_db.wget(ctx.chat.id, "scene")
    assert director_rooms.install_prepared_rooms(ctx.chat.id, scene, "The Stranger") \
        == (scene, {})


# ---- what is built: what the player can see into or is heading for -------

def test_a_room_behind_a_shut_door_is_not_in_view_until_somebody_heads_for_it():
    scene = copy.deepcopy(SCENE)
    assert rooms_in_view_or_ahead(scene, "keeper_room") == [
        "keeper_room", "lamp_gallery"]
    # A window shows the room; a wall shows nothing.
    scene["rooms"]["keeper_room"]["adjacent"][1]["barrier"] = "window"
    assert "oil_store" in rooms_in_view_or_ahead(scene, "keeper_room")
    scene["rooms"]["keeper_room"]["adjacent"][1]["barrier"] = "wall"
    assert "oil_store" not in rooms_in_view_or_ahead(scene, "keeper_room")
    # Heading for it: the walk's next leg comes before the rooms in view,
    # its end after them.
    shut = copy.deepcopy(SCENE)
    assert rooms_in_view_or_ahead(shut, "keeper_room", next_leg="oil_store") == [
        "keeper_room", "oil_store", "lamp_gallery"]
    assert rooms_in_view_or_ahead(shut, "keeper_room", bound_for="oil_store") == [
        "keeper_room", "lamp_gallery", "oil_store"]


def test_a_walk_under_way_puts_its_next_leg_and_its_end_in_reach():
    scene = copy.deepcopy(SCENE)
    scene["rooms"]["lamp_gallery"]["adjacent"].append(
        {"to": "lantern", "barrier": "open", "dir": "n"})
    scene["rooms"]["lantern"] = {"name": "Lantern", "planned": True,
                                 "purpose": "the light itself", "adjacent": [
                                     {"to": "lamp_gallery", "barrier": "open",
                                      "dir": "s"}]}
    scene["approach"] = {"The Stranger": {"to_room": "lantern"}}
    assert director_rooms.rooms_in_reach(scene, "The Stranger") == [
        "keeper_room", "lamp_gallery", "lantern"]
    # A walk does not advance through a door nobody has opened, so a walk
    # to the store has no next leg -- and its end is still where it is going.
    scene["approach"] = {"The Stranger": {"to_room": "oil_store"}}
    assert director_rooms.rooms_in_reach(scene, "The Stranger") == [
        "keeper_room", "lamp_gallery", "oil_store"]
    assert director_rooms.rooms_in_reach(scene, "Nobody") == []


def test_the_job_designs_what_is_in_view_and_not_what_is_behind_a_door(
        temp_db, monkeypatch):
    ctx = _story(temp_db)
    calls = []
    cache = _prepare(temp_db, monkeypatch, ctx, {"lamp_gallery": GALLERY}, calls)
    assert set(cache) == {"lamp_gallery"}
    owed = [sorted(c["payload"].get("develop") or {}) for c in calls]
    assert owed and all(o == ["lamp_gallery"] for o in owed)
    # The note it is handed is the story's pack's, not code's.
    from llm.prompts import prose_contract_text
    assert calls[0]["payload"]["note"] == prose_contract_text("room_prepare_note", "en")
    assert prose_contract_text("room_prepare_note", "ja").strip()


def test_each_frames_commits_design_in_a_job_of_their_own():
    """A frame's commit designs the rooms ahead of the bodies in that
    frame's scene, so each frame has its job, and a run reads one scene: the
    present's keeps the bare key, any other frame's is the key with its id.
    A causality bubble's commit used to design nothing at all ("the player
    is not in its frame"); see
    `test_a_bubble_travellers_room_ahead_is_built_in_her_frame_at_her_next_beat`."""
    assert director_rooms.predevelop_job_key(None) == director_rooms.PREDEVELOP_JOB_KEY
    assert director_rooms.predevelop_job_key(7) == f"{director_rooms.PREDEVELOP_JOB_KEY}:7"
    assert director_rooms.is_predevelop_job_key(director_rooms.predevelop_job_key(7))
    assert not director_rooms.is_predevelop_job_key("room_predevelopmentx")


# ---- installed in band, at the next beat ----------------------------------

def _beat_at(temp_db, ctx, idx, text, frame_id=None):
    """A beat's context on the same chat: a fresh turn row at `idx` in
    `frame_id`, its input `text`."""
    from core.pipeline_context import PipelineContext, TurnData
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created,frame_id) "
        "VALUES(?,?,?,?,?)", (ctx.chat.id, idx, text, time.time(), frame_id))
    return PipelineContext(
        chat=ctx.chat,
        turn=TurnData(id=turn_id, chat_id=ctx.chat.id, idx=idx,
                      player_input=text, created=time.time(), frame_id=frame_id),
        cast=ctx.cast, input=text)


def _next_beat(temp_db, ctx):
    """The next beat's context on the same chat: a fresh turn row."""
    return _beat_at(temp_db, ctx, 2, "I look up.")


def test_a_clean_design_in_view_stands_in_the_next_beat_and_its_view(
        temp_db, monkeypatch):
    from agents import perception
    ctx = _story(temp_db)
    _prepare(temp_db, monkeypatch, ctx, {"lamp_gallery": GALLERY})

    beat = _next_beat(temp_db, ctx)
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    calls = []
    # The Director invents a place beside the gallery, so the beat's own
    # room author runs at the interpret, on the scene the beat opened on.
    monkeypatch.setattr(director, "_agent_json", _beat_agents(calls, places=[
        {"name": "Watch Nook", "size": "small", "shape": "rect"}]))
    out = director.director_interpret(beat, nonce=0)

    # The beat's first event built it, so the stage's own diff carries it...
    built = out["state_assertions"]["rooms"]["lamp_gallery"]
    assert built["desc"] == GALLERY["desc"]
    assert "rail" in built["anchors"]
    assert out["orchestration"]["prose_contract"]["room_author"]["installed"] \
        == ["lamp_gallery"]
    # ...and the Director read the built room, not the stub: its fixture is
    # on the prose author's map, and the encoder had the record whole.
    by_key = {c["step_key"]: c for c in calls}
    index = json.dumps(by_key["director_prose"]["payload"].get("world_index"))
    assert "rail" in index
    # The room author reads it as a room that STANDS: drawn among the
    # rooms around the place it builds, its record the design -- a stub is
    # drawn for no one. (No plan reaches a model at this stage at all: the
    # interpret's model payload carries no planned brief and its decision
    # model asks no `enter__` question, so a built room handed back as a plan
    # to develop is the RESOLVE's hazard, pinned where it can happen --
    # `test_the_commit_persists_what_the_beat_opened_on`.)
    author = by_key["director_rooms"]["payload"]
    assert "lamp_gallery" in author["surroundings"], sorted(author["surroundings"])
    assert author["rooms"]["lamp_gallery"]["desc"] == GALLERY["desc"]
    assert "planned_rooms" not in by_key["director_prose"]["payload"]
    # Nothing is written yet: the commit is the one scene writer.
    stored = temp_db.wget(beat.chat.id, "scene")
    assert not stored["rooms"]["lamp_gallery"].get("desc")

    # Perception previews the beat's first event: a view through the
    # doorway holds the built room -- its record and the fixture sight
    # reaches -- where the stub showed only its name.
    beat.director_interpret = out
    act = perception.perception_act(beat, 0)
    view = act["views"]["1"]
    assert "Through the opening is Lamp Gallery. " + GALLERY["desc"] in view, view
    assert "salt-pitted" in view, view


def test_the_commit_persists_what_the_beat_opened_on(temp_db, monkeypatch):
    from agents import perception
    from persist import commit
    from persist.commit import _prepare_room_registry
    ctx = _story(temp_db)
    _prepare(temp_db, monkeypatch, ctx, {"lamp_gallery": GALLERY})

    beat = _next_beat(temp_db, ctx)
    decisions_asked = []
    decide = _decide(entered=("lamp_gallery",))

    def asked(state, questions):
        decisions_asked.append(list(questions))
        return decide(state, questions)
    monkeypatch.setattr(decisions, "OVERRIDE", asked)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _beat_agents(calls))
    beat.director_interpret = director.director_interpret(beat, nonce=0)
    beat["perception_act"] = perception.perception_act(beat, 0)
    resolved = director.director_resolve(beat, nonce=0)
    # The resolve does not owe a room the beat already built: no brief, no
    # question whether the passage enters it, no designer.
    assert "director_rooms" not in [c["step_key"] for c in calls]
    entering = [key for row in decisions_asked for key in row
                if key.startswith("enter__")]
    assert "enter__lamp_gallery" not in entering
    assert "enter__oil_store" in entering, "a stub behind a door is still briefed"
    # ...and its encoder is handed the built room's record whole.
    encoders = [c for c in calls if c["step_key"] == "director_specialist"]
    assert GALLERY["desc"] in json.dumps(encoders[-1]["payload"], ensure_ascii=False)
    beat.director_resolve = resolved
    # The player's own view at the end of the beat: the room through the
    # doorway, not a name on an empty stub.
    player = perception.perception_outcome(beat, 0)["views"]["player"]
    assert GALLERY["desc"] in player and "salt-pitted" in player, player

    prepared = commit.prepare_scene_commit(beat)
    commit.commit_scene(beat, nonce=0, prepared=prepared)
    stored = temp_db.wget(beat.chat.id, "scene")
    room = stored["rooms"]["lamp_gallery"]
    assert room["desc"] == GALLERY["desc"] and "rail" in room["anchors"]
    assert not room.get("planned"), "a built stub is settled into a room"
    assert sorted(stored["rooms"]) == sorted(SCENE["rooms"]), "built, not minted"

    # The registry projection matches the scene the commit wrote: preparing
    # it again against that scene finds nothing to change.
    row = temp_db.q("SELECT * FROM room_registry WHERE chat_id=? AND room_uid=?",
                    (beat.chat.id, "lamp_gallery"), one=True)
    assert row is not None and row["retired_turn_id"] is None
    assert row["name"] == "Lamp Gallery"
    again = _prepare_room_registry(beat.chat.id, beat.chat.lorebook_id,
                                   stored, stored)
    assert [u["room_uid"] for u in again["upserts"]
            if u["room_uid"] == "lamp_gallery"] == []

    # The next beat opens on a room, not a stub: nothing is built twice.
    assert director_rooms.install_prepared_rooms(
        beat.chat.id, stored, "The Stranger")[1] == {}


def test_a_reroll_builds_the_room_again_and_never_twice(temp_db, monkeypatch):
    from persist import checkpoints, commit
    ctx = _story(temp_db)
    _prepare(temp_db, monkeypatch, ctx, {"lamp_gallery": GALLERY})
    beat = _next_beat(temp_db, ctx)
    checkpoints.ensure_checkpoint(beat.chat.id, beat.turn.idx)
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    monkeypatch.setattr(director, "_agent_json", _beat_agents([]))

    def run_beat():
        # TWO INTERPRETS OF ONE BEAT BEFORE ITS COMMIT -- the stage rerolled:
        # each opens on the stored stub and builds the room into its own
        # first event, and only the one the beat keeps is committed.
        kept = None
        for nonce in (0, 1):
            kept = director.director_interpret(beat, nonce=nonce)
            assert kept["state_assertions"]["rooms"]["lamp_gallery"]["desc"] \
                == GALLERY["desc"]
            assert not temp_db.wget(beat.chat.id, "scene")["rooms"][
                "lamp_gallery"].get("desc"), "an interpret writes no scene"
        beat.director_interpret = kept
        beat.director_resolve = director.director_resolve(beat, nonce=0)
        commit.commit_scene(beat, nonce=0, prepared=commit.prepare_scene_commit(beat))
        return temp_db.wget(beat.chat.id, "scene")

    def registered():
        return [r["room_uid"] for r in temp_db.q(
            "SELECT room_uid FROM room_registry WHERE chat_id=?", (beat.chat.id,))]

    first = run_beat()
    assert first["rooms"]["lamp_gallery"]["desc"] == GALLERY["desc"]
    assert sorted(first["rooms"]) == sorted(SCENE["rooms"]), "one room, not two"
    assert registered().count("lamp_gallery") == 1

    checkpoints.restore_checkpoint(beat.chat.id, beat.turn.idx)
    assert not temp_db.wget(beat.chat.id, "scene")["rooms"]["lamp_gallery"].get("desc")
    second = run_beat()
    assert second["rooms"]["lamp_gallery"] == first["rooms"]["lamp_gallery"]
    assert sorted(second["rooms"]) == sorted(first["rooms"])
    assert registered().count("lamp_gallery") == 1


def test_an_unclean_design_in_view_is_taken_up_again_and_then_built_in(
        temp_db, monkeypatch):
    """The step cap is where a design runs out, and a fixture overlap is what
    it runs out on (the turn-26 Gale house replay). Taken up again from where
    it stopped, it comes back clean and the next beat builds it in."""
    import agents.common as common
    monkeypatch.setattr(director_rooms, "MAX_ROOM_STEPS", 1)
    ctx = _story(temp_db)
    stacked = dict(GALLERY, anchors={
        "rail": {"desc": "an iron rail", "dir": "n", "cell": [1, 0], "height": "waist"},
        "lamp": {"desc": "a lamp", "dir": "n", "cell": [1, 0], "height": "waist"}})
    fixed = dict(GALLERY, anchors={
        "rail": {"desc": "an iron rail", "dir": "n", "cell": [1, 0], "height": "waist"},
        "lamp": {"desc": "a lamp", "dir": "n", "cell": [4, 0], "height": "waist"}})
    answers = iter([stacked, fixed])
    seen = []

    def designer(role, step_key, system, payload, **kw):
        seen.append(payload)
        return {"calls": [{"tool": "draft_room", "args": {
            "room_id": "lamp_gallery", "room": copy.deepcopy(next(answers))}},
            {"tool": "submit", "args": {}}]}

    monkeypatch.setattr(common, "_agent_json", designer)
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    scene = temp_db.wget(ctx.chat.id, "scene")
    assert temp_db.wget(ctx.chat.id, director_rooms.PREPARED_KEY)[
        "lamp_gallery"]["clean"] is False
    assert director_rooms.install_prepared_rooms(ctx.chat.id, scene, "The Stranger")[1] == {}

    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert seen[1]["transcript"][0]["tool"] == "check"
    entry = temp_db.wget(ctx.chat.id, director_rooms.PREPARED_KEY)["lamp_gallery"]
    assert entry["clean"] is True and entry["continued"] == 1
    built = director_rooms.install_prepared_rooms(ctx.chat.id, scene, "The Stranger")[1]
    assert set(built["lamp_gallery"]["anchors"]) == {"rail", "lamp"}


# ---- what is not built in --------------------------------------------------

def _cached(temp_db, cid, scene, rid, room, *, clean=True):
    from world.structure import planned_room_brief
    brief = planned_room_brief(cid, scene, [rid])[rid]
    temp_db.wset(cid, director_rooms.PREPARED_KEY, {rid: {
        "room": room, "turn": 1, "steps": 2, "clean": clean,
        "brief": director_rooms._brief_signature(brief)}})
    return brief


def _with_watch_room(temp_db, ctx):
    """A second planned room in view, west of the keeper's room through an
    opening: `(scene, briefs)` for the gallery and it."""
    from world.structure import planned_room_brief
    scene = copy.deepcopy(temp_db.wget(ctx.chat.id, "scene"))
    scene["rooms"]["keeper_room"]["adjacent"].append(
        {"to": "watch_room", "barrier": "open", "dir": "w"})
    scene["rooms"]["watch_room"] = {"name": "Watch Room", "planned": True,
                                    "purpose": "where the keeper keeps the log",
                                    "adjacent": [{"to": "keeper_room",
                                                  "barrier": "open", "dir": "e"}]}
    temp_db.wset(ctx.chat.id, "scene", scene)
    return scene, planned_room_brief(ctx.chat.id, scene, ["lamp_gallery", "watch_room"])


def test_a_design_whose_check_failed_stays_a_seed_and_is_not_built_in(temp_db):
    ctx = _story(temp_db)
    scene = temp_db.wget(ctx.chat.id, "scene")
    brief = _cached(temp_db, ctx.chat.id, scene, "lamp_gallery", GALLERY, clean=False)
    assert director_rooms.install_prepared_rooms(ctx.chat.id, scene, "The Stranger") \
        == (scene, {})
    seed = director_rooms.prepared_rooms(ctx.chat.id, {"lamp_gallery": brief})
    assert seed["lamp_gallery"]["desc"] == GALLERY["desc"]


def test_a_design_the_world_has_since_contradicted_is_not_built_in(temp_db):
    """Clean when it was made, and the layout check is run again against the
    scene the beat opens on: two fixtures on one cell at one height is a
    contradiction now, whatever it was then."""
    ctx = _story(temp_db)
    scene = temp_db.wget(ctx.chat.id, "scene")
    stacked = dict(GALLERY, anchors={
        "rail": {"desc": "an iron rail", "dir": "n", "cell": [1, 0], "height": "waist"},
        "lamp": {"desc": "a lamp", "dir": "n", "cell": [1, 0], "height": "waist"}})
    _cached(temp_db, ctx.chat.id, scene, "lamp_gallery", stacked)
    assert director_rooms.install_prepared_rooms(
        ctx.chat.id, scene, "The Stranger")[1] == {}


def test_two_designs_that_contradict_each_other_build_the_first_met(
        temp_db, monkeypatch):
    """Each design was checked alone; built together they can still fight
    over one wall (the turn-3 replay: the open water's doorway and the low
    walk's on the same cells of the landing stage). The room the player
    meets first is built; the other waits as it was, and the next commit's
    job takes it up again beside the first
    (`test_a_design_refused_beside_another_is_taken_up_again_beside_it`)."""
    ctx = _story(temp_db)
    scene, briefs = _with_watch_room(temp_db, ctx)
    temp_db.wset(ctx.chat.id, director_rooms.PREPARED_KEY, {
        rid: {"room": room, "turn": 1, "steps": 2, "clean": True,
              "brief": director_rooms._brief_signature(briefs[rid])}
        for rid, room in (("lamp_gallery", GALLERY), ("watch_room", WATCH))})
    real = director_rooms._check

    def check(scene_, draft, owed, rows_out=None):
        if {"lamp_gallery", "watch_room"} <= set(draft.get("rooms") or {}):
            return {"clean": False, "errors": ["two doorways on one wall"]}
        return real(scene_, draft, owed, rows_out=rows_out)

    monkeypatch.setattr(director_rooms, "_check", check)
    _, installed = director_rooms.install_prepared_rooms(
        ctx.chat.id, scene, "The Stranger")
    assert list(installed) == ["lamp_gallery"]
    assert director_rooms.prepared_rooms(
        ctx.chat.id, {"watch_room": briefs["watch_room"]})["watch_room"]["desc"] \
        == WATCH["desc"], "the one refused waits as it was"


def test_a_room_a_beat_already_built_is_not_overwritten(temp_db):
    ctx = _story(temp_db)
    scene = temp_db.wget(ctx.chat.id, "scene")
    _cached(temp_db, ctx.chat.id, scene, "lamp_gallery", GALLERY)
    built = copy.deepcopy(scene)
    built["rooms"]["lamp_gallery"]["desc"] = "The beat's own gallery, built as it went."
    out, installed = director_rooms.install_prepared_rooms(
        ctx.chat.id, built, "The Stranger")
    assert installed == {}
    assert out["rooms"]["lamp_gallery"]["desc"] == \
        "The beat's own gallery, built as it went."


def test_a_design_made_from_an_old_brief_is_not_built_in(temp_db):
    ctx = _story(temp_db)
    scene = temp_db.wget(ctx.chat.id, "scene")
    _cached(temp_db, ctx.chat.id, scene, "lamp_gallery", GALLERY)
    replanned = copy.deepcopy(scene)
    replanned["rooms"]["lamp_gallery"]["purpose"] = "a signal walk for the pilots"
    assert director_rooms.install_prepared_rooms(
        ctx.chat.id, replanned, "The Stranger")[1] == {}
    assert director_rooms.install_prepared_rooms(
        ctx.chat.id, scene, "The Stranger")[1]["lamp_gallery"]["desc"] == GALLERY["desc"]


def test_a_design_out_of_reach_is_not_built_in(temp_db):
    """Built in only while the player can see into the room or is heading
    for it: a design for a room behind a shut door waits as a seed."""
    ctx = _story(temp_db)
    scene = temp_db.wget(ctx.chat.id, "scene")
    store = {"name": "Oil Store", "desc": "Casks of lamp oil on a stone shelf.",
             "extent": {"w": 3, "d": 3},
             "adjacent": [{"to": "keeper_room", "barrier": "closed_door", "dir": "w"}]}
    _cached(temp_db, ctx.chat.id, scene, "oil_store", store)
    assert director_rooms.install_prepared_rooms(
        ctx.chat.id, scene, "The Stranger")[1] == {}
    heading = copy.deepcopy(scene)
    heading["approach"] = {"The Stranger": {"to_room": "oil_store"}}
    assert set(director_rooms.install_prepared_rooms(
        ctx.chat.id, heading, "The Stranger")[1]) == {"oil_store"}


# ---- a design the install refuses is taken up again -----------------------

def _stacked():
    """The gallery with its lamp on the rail's cell, at the rail's height."""
    return dict(GALLERY, anchors={
        "rail": {"desc": "an iron rail", "dir": "n", "cell": [1, 0], "height": "waist"},
        "lamp": {"desc": "a lamp", "dir": "n", "cell": [1, 0], "height": "waist"}})


@pytest.mark.parametrize("filed, fix, refusal", [
    # Clean where it was drafted, and two fixtures on one cell against the
    # scene the beat opens on: the layout check refuses it.
    (_stacked(), {"anchors": {"lamp": {"cell": [4, 0]}}},
     lambda check: check.get("fixtures_overlapping")),
    # Clean to the layout check, and no record the world can hold: the
    # state schema's refusal, which no layout check reads.
    (dict(GALLERY, desc=""), {"desc": GALLERY["desc"]},
     lambda check: "desc" in " ".join(check.get("errors") or [])),
], ids=["the-layout-check", "the-state-schema"])
def test_a_clean_design_the_install_refuses_is_taken_up_again(
        temp_db, monkeypatch, filed, fix, refusal):
    """Filed clean -- its own final check passed where it was drafted -- and
    refused by the install against the scene a beat opens on. The job runs
    the install's own test before it chooses what to design and takes the
    refused design up again from where it stopped, the refusal the first
    thing its designer reads; what comes back is built in. Before, a design
    refused once was never designed again and every later beat refused it
    again, so its room stayed a name through the doorway (review of the
    2026-10-08 landing)."""
    import agents.common as common
    ctx = _story(temp_db)
    scene = temp_db.wget(ctx.chat.id, "scene")
    _cached(temp_db, ctx.chat.id, scene, "lamp_gallery", filed)
    assert director_rooms.install_prepared_rooms(
        ctx.chat.id, scene, "The Stranger")[1] == {}
    seen = []

    def designer(role, step_key, system, payload, **kw):
        seen.append(payload)
        return {"calls": [{"tool": "draft_room", "args": {
            "room_id": "lamp_gallery", "room": copy.deepcopy(fix)}},
            {"tool": "submit", "args": {}}]}

    monkeypatch.setattr(common, "_agent_json", designer)
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert len(seen) == 1, "the refused design is taken up again"
    first = seen[0]["transcript"][0]
    assert (first["step"], first["by"], first["tool"]) == (0, "engine", "check")
    assert first["result"]["clean"] is False and refusal(first["result"]), first
    assert seen[0]["draft"]["rooms"]["lamp_gallery"]["name"] == GALLERY["name"], \
        "from where it stopped, not from nothing"
    assert "prepared" not in seen[0]
    entry = temp_db.wget(ctx.chat.id, director_rooms.PREPARED_KEY)["lamp_gallery"]
    assert entry["clean"] is True and entry["continued"] == 1

    room = director_rooms.install_prepared_rooms(
        ctx.chat.id, scene, "The Stranger")[1]["lamp_gallery"]
    assert room["desc"] == GALLERY["desc"] and "rail" in room["anchors"]


def test_a_design_refused_beside_another_is_taken_up_again_beside_it(
        temp_db, monkeypatch):
    """Two designs each clean alone can take the same wall (the turn-3
    replay: the open water's doorway and the low walk's on the same cells of
    the landing stage's east wall), and the install builds the one the
    player meets first. The job runs the same test, merges what would stand
    into the scene it designs on, and takes the other up again THERE: every
    look its designer gets has the built room standing beside it, so what
    it submits is clean beside that room, and the next beat builds both."""
    import agents.common as common
    ctx = _story(temp_db)
    scene, briefs = _with_watch_room(temp_db, ctx)
    temp_db.wset(ctx.chat.id, director_rooms.PREPARED_KEY, {
        rid: {"room": room, "turn": 1, "steps": 2, "clean": True,
              "brief": director_rooms._brief_signature(briefs[rid])}
        for rid, room in (("lamp_gallery", GALLERY), ("watch_room", WATCH))})
    real = director_rooms._check
    looks = []

    def check(scene_, draft, owed, rows_out=None):
        built = ((scene_.get("rooms") or {}).get("lamp_gallery") or {}).get("desc") \
            == GALLERY["desc"]
        looks.append((sorted(draft.get("rooms") or {}), built))
        rooms = director_rooms._merged(scene_, draft).get("rooms") or {}
        if (rooms.get("lamp_gallery") or {}).get("desc") == GALLERY["desc"] \
                and (rooms.get("watch_room") or {}).get("desc") == WATCH["desc"]:
            return {"clean": False, "errors": ["two doorways on one wall"]}
        return real(scene_, draft, owed, rows_out=rows_out)

    monkeypatch.setattr(director_rooms, "_check", check)
    assert list(director_rooms.install_prepared_rooms(
        ctx.chat.id, scene, "The Stranger")[1]) == ["lamp_gallery"]
    seen = []

    def designer(role, step_key, system, payload, **kw):
        seen.append(payload)
        return {"calls": [{"tool": "draft_room", "args": {"room_id": "watch_room", "room": {
            "desc": "A desk under the west window, the log open on it."}}},
            {"tool": "submit", "args": {}}]}

    monkeypatch.setattr(common, "_agent_json", designer)
    looks.clear()
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert [sorted(p["develop"]) for p in seen] == [["watch_room"]]
    assert seen[0]["transcript"][0]["result"]["errors"] == ["two doorways on one wall"]
    drafting = [built for drafted, built in looks if drafted == ["watch_room"]]
    assert drafting and all(drafting), "drafted beside the room that stands"
    entry = temp_db.wget(ctx.chat.id, director_rooms.PREPARED_KEY)["watch_room"]
    assert entry["clean"] is True and entry["continued"] == 1

    _, installed = director_rooms.install_prepared_rooms(
        ctx.chat.id, scene, "The Stranger")
    assert set(installed) == {"lamp_gallery", "watch_room"}


def test_a_refused_design_with_its_continuations_spent_waits_as_a_seed(
        temp_db, monkeypatch):
    """Taken up again already, and refused again -- the world changed after
    it was filed: here a fixture the plan put on the stub stands on the
    lamp's cell. With no continuation left it is filed not clean: it waits
    as a seed for the beat that enters its room, and neither the job nor any
    beat's install spends anything on it again."""
    import agents.common as common
    from world.structure import planned_room_brief
    ctx = _story(temp_db)
    cid = ctx.chat.id
    scene = temp_db.wget(cid, "scene")
    brief = planned_room_brief(cid, scene, ["lamp_gallery"])["lamp_gallery"]
    fixed = dict(GALLERY, anchors={
        "rail": {"desc": "an iron rail", "dir": "n", "cell": [1, 0], "height": "waist"},
        "lamp": {"desc": "a lamp", "dir": "n", "cell": [4, 0], "height": "waist"}})
    temp_db.wset(cid, director_rooms.PREPARED_KEY, {"lamp_gallery": {
        "room": fixed, "turn": 1, "steps": 3, "clean": True,
        "continued": director_rooms.PREDEVELOP_CONTINUATIONS,
        "brief": director_rooms._brief_signature(brief)}})
    scene["rooms"]["lamp_gallery"]["anchors"] = {"bell": {
        "desc": "a ship's bell", "dir": "n", "cell": [4, 0], "height": "waist"}}
    temp_db.wset(cid, "scene", scene)
    assert planned_room_brief(cid, scene, ["lamp_gallery"])["lamp_gallery"] == brief
    assert director_rooms.install_prepared_rooms(cid, scene, "The Stranger")[1] == {}

    calls = []
    monkeypatch.setattr(common, "_agent_json", _designer(calls))
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert calls == []
    entry = temp_db.wget(cid, director_rooms.PREPARED_KEY)["lamp_gallery"]
    assert entry["clean"] is False and entry["refused_turn"] == ctx.turn.idx
    assert entry["room"] == fixed, "kept whole, as the seed"

    checks = []
    real = director_rooms._check
    monkeypatch.setattr(director_rooms, "_check",
                        lambda *a, **k: checks.append(a) or real(*a, **k))
    assert director_rooms.install_prepared_rooms(cid, scene, "The Stranger")[1] == {}
    assert checks == [], "no beat's install checks it again"
    seed = director_rooms.prepared_rooms(cid, {"lamp_gallery": brief})["lamp_gallery"]
    assert seed["anchors"]["lamp"]["cell"] == [4, 0]
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert calls == []


# ---- a space held open is the Writers' Room's ------------------------------

def test_a_frontier_space_held_open_is_left_for_the_writers_room(temp_db, monkeypatch):
    """A provisional stub -- the name a structure's grammar gave a frontier
    axis, standing in until a plan claims the space -- is in view through
    its opening like any room, and is neither designed between turns nor
    built in. What the space IS is the Writers' Room's to say: built from
    its name, it would be spent -- a claim keeps the name of a room with
    prose, and its purpose and geometry never reach the room -- before the
    Room, which plants ahead exactly there, could claim it (owner's ruling
    2026-10-08). A plan that claims it rewrites the row without the mark,
    and from then on it is built like any planned room."""
    from world import structure
    ctx = _story(temp_db)
    cid = ctx.chat.id
    scene = temp_db.wget(cid, "scene")
    uid, spec = structure.mint_frontier(
        {"key": "lighthouse", "grammar": []}, "keeper_room", "the headland path",
        f"{cid}:lighthouse", existing=set(scene["rooms"]))
    assert spec["provisional"] is True
    temp_db.qi("INSERT INTO room_registry(chat_id,room_uid,name,aliases,payload) "
               "VALUES(?,?,?,?,?)",
               (cid, uid, spec["name"], json.dumps([spec["name"]]),
                json.dumps({"planned": spec})))
    scene["rooms"]["keeper_room"]["adjacent"].append(
        {"to": uid, "barrier": "open_door", "dir": "w", "axis": "the headland path"})
    scene["rooms"][uid] = {"name": spec["name"], "planned": True,
                           "purpose": spec["purpose"],
                           "adjacent": [{"to": "keeper_room", "barrier": "open",
                                         "dir": "e"}]}
    temp_db.wset(cid, "scene", scene)
    assert uid in director_rooms.rooms_in_reach(scene, "The Stranger"), \
        "the space is in view"
    assert uid in structure.planned_room_brief(cid, scene, [uid]), "and a stub"
    to_build = director_rooms.rooms_to_build(cid, scene, "The Stranger")
    assert "lamp_gallery" in to_build and uid not in to_build

    calls = []
    cache = _prepare(temp_db, monkeypatch, ctx, {"lamp_gallery": GALLERY}, calls)
    owed = {rid for c in calls for rid in (c["payload"].get("develop") or {})}
    assert owed == {"lamp_gallery"} and uid not in cache

    # A design an earlier run filed for the space is not built in either;
    # the gallery beside it is.
    brief = structure.planned_room_brief(cid, scene, [uid])[uid]
    cache[uid] = {"room": {"name": spec["name"], "desc": "Open ground running to the cliff.",
                           "adjacent": [{"to": "keeper_room", "barrier": "open",
                                         "dir": "e"}]},
                  "turn": 1, "steps": 2, "clean": True,
                  "brief": director_rooms._brief_signature(brief)}
    temp_db.wset(cid, director_rooms.PREPARED_KEY, cache)
    _, installed = director_rooms.install_prepared_rooms(cid, scene, "The Stranger")
    assert set(installed) == {"lamp_gallery"}


# ---- a silent beat keeps the rooms it opened on ---------------------------

def test_a_silent_beat_keeps_the_rooms_it_opened_on(temp_db, monkeypatch):
    """Send with an empty box: the beat declares nothing, and the guard that
    clears the player's declarations used to clear the row establishing the
    beat's places with them. The Director had read the gallery standing, the
    record said it was installed, and the commit wrote the stub (review of
    the 2026-10-08 landing: INTERPRET ROOMS [], RECORD INSTALLED
    ['lamp_gallery'], STORED GALLERY DESC None). The rooms the install built
    are the world's, and the stage's assertions carry them; the player's
    silence is still the whole declaration
    (`test_a_silent_beat_keeps_nothing_its_prose_made`)."""
    from persist import commit
    ctx = _story(temp_db)
    _prepare(temp_db, monkeypatch, ctx, {"lamp_gallery": GALLERY})
    beat = _beat_at(temp_db, ctx, 2, "")
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    monkeypatch.setattr(director, "_agent_json", _beat_agents([]))
    out = director.director_interpret(beat, nonce=0)

    assert out["state_assertions"]["rooms"]["lamp_gallery"]["desc"] == GALLERY["desc"]
    assert out["onset_state_assertions"]["rooms"]["lamp_gallery"]["desc"] \
        == GALLERY["desc"]
    assert out["orchestration"]["installed_rooms"] == ["lamp_gallery"]
    # Still silent: the sequence holds nothing, and only the encoder's other
    # row was discarded as invented -- the places row is no declaration, and
    # it held only the room the install built, so no place is counted.
    assert out["sequence"] == []
    assert out["speech"] is None and out["action"] is None
    warned = [w for w in beat.warnings if "player input was empty" in w]
    assert warned and "discarded 1 invented declaration(s) and" in warned[0], warned

    beat.director_interpret = out
    beat.director_resolve = director.director_resolve(beat, nonce=0)
    commit.commit_scene(beat, nonce=0, prepared=commit.prepare_scene_commit(beat))
    assert temp_db.wget(ctx.chat.id, "scene")["rooms"]["lamp_gallery"]["desc"] \
        == GALLERY["desc"]


NOOK = {"name": "Crawlspace", "desc": "A low crawlspace behind the hatch.",
        "extent": {"w": 2, "d": 2},
        "adjacent": [{"to": "keeper_room", "barrier": "open", "dir": "w"}]}


def _restating_agents():
    """The Director on an empty input restating the player's last conduct --
    the chat 59 t154 class the silent guard exists for -- in interpret prose
    that names a place its room author builds, with a doorway onto the
    gallery; the resolve's prose names nothing."""
    turns = {"prose": 0}

    def prose(payload):
        turns["prose"] += 1
        if turns["prose"] == 1:
            return {"prose": "You push the hatch open and crawl into the crawlspace.",
                    "places": [{"name": "Crawlspace", "size": "small", "shape": "rect"}]}
        return {"prose": "The keeper's room is quiet."}
    return _fake_agent([], {
        "director_prose": prose,
        "director_specialist": {"events": [
            {"source_entity_id": "player", "event": "You crawl into the crawlspace.",
             "item_names": ["The Stranger"], "transforms": []}]},
        "director_rooms": {"calls": [
            {"tool": "draft_room", "args": {"room_id": "crawlspace", "room": NOOK}},
            {"tool": "draft_room", "args": {"room_id": "lamp_gallery", "room": {
                "adjacent": [{"to": "crawlspace", "barrier": "open", "dir": "e"}]}}},
            {"tool": "submit", "args": {}}]},
    })


@pytest.mark.parametrize("opened_on", [True, False],
                         ids=["opened-on-a-built-room", "predevelopment-off"])
def test_a_silent_beat_keeps_nothing_its_prose_made(temp_db, monkeypatch, opened_on):
    """Send with an empty box while the interpret's prose restates the
    player's last act and its room author builds the place that prose names,
    with a doorway onto the gallery. The beat declares nothing, so nothing
    its prose made reaches the world: the crawlspace is not committed, and
    the gallery the beat opened on is committed exactly as it was built in,
    without the author's doorway to the crawlspace. Kept whole, the row
    establishing the beat's places committed the crawlspace, with rooms in
    view built or not, while the guard's warning said the invention was
    discarded (review of the 2026-10-08 rooms-in-view landing, round 3)."""
    from persist import commit
    ctx = _story(temp_db)
    if opened_on:
        _prepare(temp_db, monkeypatch, ctx, {"lamp_gallery": GALLERY})
    else:
        temp_db.set_setting(director_rooms.PREDEVELOP_SETTING, "0")
    beat = _beat_at(temp_db, ctx, 2, "")
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    monkeypatch.setattr(director, "_agent_json", _restating_agents())
    out = director.director_interpret(beat, nonce=0)

    built = ["lamp_gallery"] if opened_on else []
    for key in ("state_assertions", "onset_state_assertions"):
        assert sorted((out[key] or {}).get("rooms") or {}) == built, key
    assert out["sequence"] == [], "a silent beat declares nothing"
    warned = [w for w in beat.warnings if "player input was empty" in w]
    assert warned and "crawlspace" in warned[0], beat.warnings
    assert "1 invented declaration(s)" in warned[0], warned
    if opened_on:
        gallery = out["state_assertions"]["rooms"]["lamp_gallery"]
        assert [edge["to"] for edge in gallery["adjacent"]] == ["keeper_room"], \
            "the design as it was built in, not the author's merge"
        assert out["orchestration"]["installed_rooms"] == ["lamp_gallery"]
        assert out["orchestration"]["prose_contract"]["room_author"]["installed"] \
            == ["lamp_gallery"]

    beat.director_interpret = out
    beat.director_resolve = director.director_resolve(beat, nonce=0)
    commit.commit_scene(beat, nonce=0, prepared=commit.prepare_scene_commit(beat))
    stored = temp_db.wget(ctx.chat.id, "scene")
    assert "crawlspace" not in stored["rooms"], "the place the stale prose invented"
    assert not [rid for rid, room in stored["rooms"].items()
                for edge in room.get("adjacent") or [] if edge.get("to") == "crawlspace"]
    assert (stored["rooms"]["lamp_gallery"].get("desc") == GALLERY["desc"]) is opened_on


def test_the_record_names_only_the_rooms_the_stage_carries():
    """The installed rooms a stage's assertions still hold -- at the top or
    in a causal step -- are what the beat commits, and the only ones its
    record may say were built in."""
    out = {"state_assertions": {"rooms": {"a": {}}, "causal_steps": [
        {"chrono_id": 1, "patch": {"rooms": {"b": {}}}}]}}
    assert director_rooms.installed_rooms_kept(
        out, {"a": {}, "b": {}, "c": {}}) == ["a", "b"]
    assert director_rooms.installed_rooms_kept({}, {"a": {}}) == []


def test_a_room_built_in_that_the_stage_loses_is_not_recorded_as_built(
        temp_db, monkeypatch):
    """The beat opens on two rooms built in, and the stage's own assertions
    lose one after the install -- here the validation of the stage's
    assertions drops it, as it drops a whole channel one malformed record
    spoils. The beat commits what its assertions carry, so its record says
    the watch room was built in and the gallery was not, and a warning names
    the gallery: the record once said a room was built on a beat that
    committed its stub (review of the 2026-10-08 landing)."""
    ctx = _story(temp_db)
    cid = ctx.chat.id
    _scene, briefs = _with_watch_room(temp_db, ctx)
    temp_db.wset(cid, director_rooms.PREPARED_KEY, {
        rid: {"room": room, "turn": 1, "steps": 2, "clean": True,
              "brief": director_rooms._brief_signature(briefs[rid])}
        for rid, room in (("lamp_gallery", GALLERY), ("watch_room", WATCH))})
    real = director.validated_player_state_assertions

    def losing_the_gallery(sc, raw, player_name, report=None):
        clean = real(sc, raw, player_name, report=report)
        (clean.get("rooms") or {}).pop("lamp_gallery", None)
        for step in clean.get("causal_steps") or ():
            ((step.get("patch") or {}).get("rooms") or {}).pop("lamp_gallery", None)
        return clean
    monkeypatch.setattr(director, "validated_player_state_assertions",
                        losing_the_gallery)
    beat = _next_beat(temp_db, ctx)
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    monkeypatch.setattr(director, "_agent_json", _beat_agents([]))
    out = director.director_interpret(beat, nonce=0)

    assert sorted(out["state_assertions"]["rooms"]) == ["watch_room"]
    assert out["orchestration"]["installed_rooms"] == ["watch_room"]
    assert out["orchestration"]["prose_contract"]["room_author"]["installed"] \
        == ["watch_room"]
    lost = [w for w in beat.warnings if "did not survive" in w]
    assert lost and "lamp_gallery" in lost[0] and "watch_room" not in lost[0], \
        beat.warnings


# ---- a run and a restore, a run and a commit -------------------------------

def _settled(job):
    deadline = time.monotonic() + 10.0
    while job.state in ("pending", "running") and time.monotonic() < deadline:
        time.sleep(0.02)
    return job


def test_a_restore_while_rooms_are_designed_keeps_what_it_restored(
        temp_db, monkeypatch):
    """Beat 2 opens on the built gallery and commits it; its commit's run
    starts designing the watch room. The player rerolls beat 2 while it
    designs. The restore puts back the pre-beat scene, where the gallery is
    a stub again, and the pre-beat cache, which holds its design. The run
    read the beat the restore discards, so it is stopped (`cancel_from`)
    and writes nothing when its call returns -- before, it wrote its whole
    in-memory cache over the restored row, and the redone beat opened on the
    gallery as a bare name (review of the 2026-10-08 landing: restored
    ['lamp_gallery'], after the run ['watch_room'])."""
    import threading
    import agents.common as common
    from persist import checkpoints, commit
    ctx = _story(temp_db)
    cid = ctx.chat.id
    _scene, briefs = _with_watch_room(temp_db, ctx)
    temp_db.wset(cid, director_rooms.PREPARED_KEY, {"lamp_gallery": {
        "room": GALLERY, "turn": 1, "steps": 2, "clean": True,
        "brief": director_rooms._brief_signature(briefs["lamp_gallery"])}})
    beat = _next_beat(temp_db, ctx)
    checkpoints.ensure_checkpoint(cid, beat.turn.idx)
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    monkeypatch.setattr(director, "_agent_json", _beat_agents([]))
    beat.director_interpret = director.director_interpret(beat, nonce=0)
    beat.director_resolve = director.director_resolve(beat, nonce=0)
    commit.commit_scene(beat, nonce=0, prepared=commit.prepare_scene_commit(beat))
    assert temp_db.wget(cid, "scene")["rooms"]["lamp_gallery"]["desc"] == GALLERY["desc"]

    started, release = threading.Event(), threading.Event()

    def designer(role, step_key, system, payload, **kw):
        started.set()
        release.wait(10)
        return {"calls": [{"tool": "draft_room", "args": {
            "room_id": "watch_room", "room": copy.deepcopy(WATCH)}},
            {"tool": "submit", "args": {}}]}

    monkeypatch.setattr(common, "_agent_json", designer)
    job = director_rooms.schedule_room_predevelopment(beat)
    try:
        assert started.wait(10)
        checkpoints.restore_checkpoint(cid, beat.turn.idx)
        assert job.cancelled.is_set(), "a run that read the discarded beat is stopped"
        restored = temp_db.wget(cid, director_rooms.PREPARED_KEY)
        assert set(restored) == {"lamp_gallery"}
    finally:
        release.set()
    assert _settled(job).state == "cancelled"
    assert temp_db.wget(cid, director_rooms.PREPARED_KEY) == restored, \
        "the stopped run wrote nothing over the restored row"
    scene = temp_db.wget(cid, "scene")
    assert not scene["rooms"]["lamp_gallery"].get("desc")
    assert "lamp_gallery" in director_rooms.install_prepared_rooms(
        cid, scene, "The Stranger")[1], "the redone beat opens on it built"


def test_a_run_files_its_own_rooms_onto_the_row_as_it_stands(
        temp_db, monkeypatch):
    """The row a run files into can change while it designs: another
    frame's run files a room, the player restores a LATER beat than the one
    the run read -- which keeps the run, since it read nothing the restore
    discards. The run re-reads the row and writes only what it made; it used
    to write its whole in-memory cache, and what landed meanwhile was gone."""
    import threading
    import agents.common as common
    from persist import checkpoints
    ctx = _story(temp_db)
    cid = ctx.chat.id
    started, release = threading.Event(), threading.Event()

    def designer(role, step_key, system, payload, **kw):
        started.set()
        release.wait(10)
        return {"calls": [{"tool": "draft_room", "args": {
            "room_id": "lamp_gallery", "room": copy.deepcopy(GALLERY)}},
            {"tool": "submit", "args": {}}]}

    monkeypatch.setattr(common, "_agent_json", designer)
    job = director_rooms.schedule_room_predevelopment(ctx)    # beat 1's commit
    elsewhere = {"room": {"name": "Oil Store", "desc": "Casks on a shelf."},
                 "turn": 1, "steps": 1, "clean": False, "brief": "another frame's"}
    try:
        assert started.wait(10)
        temp_db.wset(cid, director_rooms.PREPARED_KEY, {"oil_store": elsewhere})
        checkpoints.ensure_checkpoint(cid, 2)
        checkpoints.restore_checkpoint(cid, 2)
        assert not job.cancelled.is_set(), "a run that read a kept beat goes on"
    finally:
        release.set()
    _wait(job)
    cache = temp_db.wget(cid, director_rooms.PREPARED_KEY)
    assert cache["oil_store"] == elsewhere, "what landed meanwhile stands"
    assert cache["lamp_gallery"]["clean"] is True


def test_a_commit_during_a_run_has_its_view_designed_by_the_same_job(
        temp_db, monkeypatch):
    """A design takes about 40 s, longer than a sub-minute beat. Beat 2
    commits while beat 1's run designs the gallery: the player opened the
    oil store's door, and a new stub stands in view. Its commit joins the
    run, as before, and asks it to run once more (`jobs.submit_latest`):
    the next run reads the scene beat 2 left and designs the oil store, under
    beat 2's turn, without waiting for a further commit. Before, nothing was
    designed for beat 2's view until the first commit after the run ended
    (review of the 2026-10-08 landing: DESIGNED ['lamp_gallery'], the oil
    store absent)."""
    import threading
    import agents.common as common
    ctx = _story(temp_db)
    cid = ctx.chat.id
    started, release, owed = threading.Event(), threading.Event(), []

    def designer(role, step_key, system, payload, **kw):
        rid = sorted(payload.get("develop") or {})[0]
        owed.append(rid)
        started.set()
        release.wait(10)
        return {"calls": [{"tool": "draft_room", "args": {"room_id": rid, "room": {
            "name": rid, "desc": f"The {rid}."}}}, {"tool": "submit", "args": {}}]}

    monkeypatch.setattr(common, "_agent_json", designer)
    job = director_rooms.schedule_room_predevelopment(ctx)    # beat 1's commit
    try:
        assert started.wait(10)
        scene = copy.deepcopy(temp_db.wget(cid, "scene"))
        scene["rooms"]["keeper_room"]["adjacent"][1]["barrier"] = "open_door"
        scene["rooms"]["oil_store"]["adjacent"][0]["barrier"] = "open_door"
        temp_db.wset(cid, "scene", scene)
        ctx.turn.idx = 2
        assert director_rooms.schedule_room_predevelopment(ctx) is job   # beat 2's
    finally:
        release.set()
    _wait(job)
    cache = temp_db.wget(cid, director_rooms.PREPARED_KEY)
    assert "oil_store" in cache, "the room in view after beat 2 was designed"
    assert cache["oil_store"]["turn"] == 2 and job.base_turn == 2
    assert owed.count("lamp_gallery") == 1, "nothing is designed twice"


# ---- any actor: the rooms ahead of the cast are built too ------------------

STAIR = {"name": "Stair Foot", "desc": "The foot of the bell stair, a rope rail up the wall.",
         "extent": {"w": 3, "d": 3},
         "adjacent": [{"to": "keeper_room", "barrier": "closed_door", "dir": "n"},
                      {"to": "bell_loft", "barrier": "open", "dir": "s"}]}

BELL = {"name": "Bell Loft", "desc": "A loft under the bell, its wheel at the south wall.",
        "extent": {"w": 3, "d": 3},
        "adjacent": [{"to": "stair_foot", "barrier": "open", "dir": "n"}]}


def _with_mara_at_the_stair(temp_db, ctx):
    """Mara at the foot of the bell stair, behind the keeper's room's shut
    south door: the bell loft is open above her and in nobody else's view."""
    scene = copy.deepcopy(temp_db.wget(ctx.chat.id, "scene"))
    scene["rooms"]["keeper_room"]["adjacent"].append(
        {"to": "stair_foot", "barrier": "closed_door", "dir": "s"})
    scene["rooms"]["stair_foot"] = copy.deepcopy(STAIR)
    scene["rooms"]["bell_loft"] = {"name": "Bell Loft", "planned": True,
                                   "purpose": "the bell and the wheel that swings it",
                                   "adjacent": [{"to": "stair_foot", "barrier": "open",
                                                 "dir": "n"}]}
    scene["positions"]["Mara"] = "stair_foot"
    temp_db.wset(ctx.chat.id, "scene", scene)
    return scene


def test_a_room_ahead_of_a_cast_member_away_from_the_player_is_built(
        temp_db, monkeypatch):
    """The owner's choice (2026-10-08): "Rooms in view of, or ahead of, ANY
    cast member get built, bubble travellers included, not just the
    player's." Mara stands at the stair foot behind a door the player has
    not opened; the bell loft is open above her. It is designed between
    turns, built into the scene the next beat opens on, and committed."""
    from persist import commit
    ctx = _story(temp_db)
    scene = _with_mara_at_the_stair(temp_db, ctx)
    cache = _prepare(temp_db, monkeypatch, ctx,
                     {"lamp_gallery": GALLERY, "bell_loft": BELL})
    assert "bell_loft" in cache, "the room ahead of a cast member is designed"
    assert cache["bell_loft"]["clean"] is True
    assert director_rooms.actors_ahead(ctx.chat.id, None, scene) == (
        ["The Stranger"], ["Mara"])
    assert "bell_loft" not in director_rooms.rooms_to_build(
        ctx.chat.id, scene, "The Stranger"), "in no player's view"

    beat = _next_beat(temp_db, ctx)
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    monkeypatch.setattr(director, "_agent_json", _beat_agents([]))
    out = director.director_interpret(beat, nonce=0)
    assert out["state_assertions"]["rooms"]["bell_loft"]["desc"] == BELL["desc"]
    assert out["orchestration"]["installed_rooms"] == ["bell_loft", "lamp_gallery"]
    beat.director_interpret = out
    beat.director_resolve = director.director_resolve(beat, nonce=0)
    commit.commit_scene(beat, nonce=0, prepared=commit.prepare_scene_commit(beat))
    stored = temp_db.wget(ctx.chat.id, "scene")
    assert stored["rooms"]["bell_loft"]["desc"] == BELL["desc"]
    assert stored["positions"]["Mara"] == "stair_foot", "nobody walked anywhere"


def test_the_players_rooms_come_first_within_the_bound(temp_db, monkeypatch):
    """Within a frame's bound the players' rooms are designed before the
    cast's -- a continuation of the player's own unclean design included,
    ahead of a fresh design for a bystander -- and the cast's room is
    designed by the next run, not left for good."""
    import agents.common as common
    monkeypatch.setattr(director_rooms, "PREDEVELOP_PER_TURN", 1)
    ctx = _story(temp_db)
    scene = _with_mara_at_the_stair(temp_db, ctx)
    _cached(temp_db, ctx.chat.id, scene, "lamp_gallery", _stacked(), clean=False)
    calls = []
    monkeypatch.setattr(common, "_agent_json", _designer(calls, {
        "lamp_gallery": {"anchors": {"lamp": {"cell": [4, 0]}}}, "bell_loft": BELL}))

    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert {rid for c in calls for rid in c["payload"].get("develop") or {}} \
        == {"lamp_gallery"}, "the player's continuation came first"
    entry = temp_db.wget(ctx.chat.id, director_rooms.PREPARED_KEY)["lamp_gallery"]
    assert entry["continued"] == 1 and entry["clean"] is True

    calls.clear()
    ctx.turn.idx = 2
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert {rid for c in calls for rid in c["payload"].get("develop") or {}} \
        == {"bell_loft"}, "and the cast's room in the next run"


def _bubble(temp_db, ctx):
    """Mara walked away from the player into a causality bubble: a spatial
    frame of her own that no player plays, its scene placing her at the
    stair foot and nobody else; the present's scene keeps the player and no
    longer places her. `(frame id, her scene)`."""
    from core.frames import create_frame
    from world.spatial_frames import is_bubble_frame
    cid = ctx.chat.id
    main = _with_mara_at_the_stair(temp_db, ctx)
    away = copy.deepcopy(main)
    away["positions"] = {"Mara": "stair_foot"}
    main["positions"] = {"The Stranger": "keeper_room"}
    temp_db.wset(cid, "scene", main)
    fid = create_frame(cid, label="Mara, away", ordinal=1, kind="spatial",
                       split_turn_idx=1)
    temp_db.wset_for_frame(cid, "scene", away, fid)
    assert is_bubble_frame(cid, fid)
    return fid, away


def test_a_bubble_travellers_room_ahead_is_built_in_her_frame_at_her_next_beat(
        temp_db, monkeypatch):
    """Her frame's commit designs the bell loft ahead of her -- it used to
    design nothing ("the player is not in its frame") -- and her next beat,
    which the engine runs and which declares nothing, opens on it built: the
    stage carries it, the resolve carries it into the beat's diff, and the
    commit writes it into her frame's scene and not the player's."""
    import agents.common as common
    from core import db
    from persist import commit
    ctx = _story(temp_db)
    cid = ctx.chat.id
    fid, away = _bubble(temp_db, ctx)
    calls = []
    monkeypatch.setattr(common, "_agent_json", _designer(calls, {"bell_loft": BELL}))
    job = director_rooms.schedule_room_predevelopment(
        _beat_at(temp_db, ctx, 2, "", frame_id=fid))           # her commit
    assert job is not None and job.key == director_rooms.predevelop_job_key(fid)
    _wait(job)
    assert {rid for c in calls for rid in c["payload"].get("develop") or {}} \
        == {"bell_loft"}, "her room, read off her frame's scene"
    assert temp_db.wget(cid, director_rooms.PREPARED_KEY)["bell_loft"]["clean"] is True

    nxt = _beat_at(temp_db, ctx, 3, "", frame_id=fid)          # her next beat
    monkeypatch.setattr(decisions, "OVERRIDE", _decide())
    monkeypatch.setattr(director, "_agent_json", _beat_agents([]))
    token = db.active_frame_id.set(fid)
    try:
        out = director.director_interpret(nxt, nonce=0)
        assert out["state_assertions"]["rooms"]["bell_loft"]["desc"] == BELL["desc"]
        assert out["onset_state_assertions"]["rooms"]["bell_loft"]["desc"] \
            == BELL["desc"]
        assert out["orchestration"]["installed_rooms"] == ["bell_loft"]
        assert out["sequence"] == [], "her beat still declares nothing"
        nxt.director_interpret = out
        # What she sees through the opening is the loft, not its name.
        from agents import perception
        view = perception.perception_act(nxt, 0)["views"][str(ctx.cast[0]["id"])]
        assert BELL["desc"] in view, view
        nxt.director_resolve = director.director_resolve(nxt, nonce=0)
        assert nxt.director_resolve["state_diff"]["rooms"]["bell_loft"]["desc"] \
            == BELL["desc"]
        commit.commit_scene(nxt, nonce=0, prepared=commit.prepare_scene_commit(nxt))
    finally:
        db.active_frame_id.reset(token)
    assert temp_db.wget_for_frame(cid, "scene", fid)["rooms"]["bell_loft"]["desc"] \
        == BELL["desc"]
    assert not temp_db.wget(cid, "scene")["rooms"]["bell_loft"].get("desc"), \
        "the player's frame still holds its stub"


def test_a_frame_merged_back_designs_nothing(temp_db, monkeypatch):
    """A bubble's last commit, or a run asked for after its frame merged
    back, reads a frame no beat opens on any more: its traveller has gone
    home. Its job designs nothing -- not the bell loft ahead of where she
    stood, which it would build into a scene nobody plays (review of the
    2026-10-08 rooms-in-view landing, round 3)."""
    import agents.common as common
    ctx = _story(temp_db)
    cid = ctx.chat.id
    fid, _away = _bubble(temp_db, ctx)
    temp_db.qi("UPDATE frames SET merged_turn_idx=? WHERE id=?", (2, fid))
    calls = []
    monkeypatch.setattr(common, "_agent_json", _designer(calls, {"bell_loft": BELL}))
    job = director_rooms.schedule_room_predevelopment(
        _beat_at(temp_db, ctx, 2, "", frame_id=fid))           # her last commit
    assert job is not None and job.key == director_rooms.predevelop_job_key(fid)
    _wait(job)
    assert calls == [], "no designer for a frame merged back"
    assert "bell_loft" not in (temp_db.wget(cid, director_rooms.PREPARED_KEY) or {})


def test_a_design_another_frame_still_needs_is_kept(temp_db, monkeypatch):
    """The cache is the chat's, and every frame's run prunes it. The
    player's frame has built the bell loft; Mara's bubble still holds it as
    the stub its design was made for. The player's next run keeps the design
    for her frame to build, rather than dropping it -- her frame would design
    it again, the player's next run would drop that, every beat. Merged back,
    her frame needs nothing, and the design goes."""
    import agents.common as common
    from world.structure import planned_room_brief
    ctx = _story(temp_db)
    cid = ctx.chat.id
    fid, away = _bubble(temp_db, ctx)
    brief = planned_room_brief(cid, away, ["bell_loft"])["bell_loft"]
    temp_db.wset(cid, director_rooms.PREPARED_KEY, {"bell_loft": {
        "room": BELL, "turn": 1, "steps": 2, "clean": True,
        "brief": director_rooms._brief_signature(brief)}})
    main = copy.deepcopy(temp_db.wget(cid, "scene"))
    main["rooms"]["bell_loft"] = dict(BELL)
    temp_db.wset(cid, "scene", main)
    calls = []
    monkeypatch.setattr(common, "_agent_json", _designer(calls, {"lamp_gallery": GALLERY}))
    _wait(director_rooms.schedule_room_predevelopment(ctx))     # the player's run
    assert "bell_loft" in temp_db.wget(cid, director_rooms.PREPARED_KEY), \
        "kept for the frame that still holds the stub"
    assert set(director_rooms.install_prepared_rooms(
        cid, away, None, cast=ctx.cast, frame_id=fid)[1]) == {"bell_loft"}

    temp_db.qi("UPDATE frames SET merged_turn_idx=? WHERE id=?", (3, fid))
    ctx.turn.idx = 3
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert "bell_loft" not in temp_db.wget(cid, director_rooms.PREPARED_KEY)


def test_a_design_kept_for_another_frame_is_that_frames_to_build(
        temp_db, monkeypatch):
    """One cache row holds one design a room. Where two live frames hold the
    same stub under different briefs -- here the player's frame has a door
    on the loft Mara's frame does not -- the design made for her frame's
    brief is hers: the player's run neither takes it up nor designs over it,
    and the player's install does not build a design made from another
    brief. The player's beat that enters the loft still designs it then."""
    import agents.common as common
    from world.structure import planned_room_brief
    ctx = _story(temp_db)
    cid = ctx.chat.id
    fid, away = _bubble(temp_db, ctx)
    main = copy.deepcopy(temp_db.wget(cid, "scene"))
    main["positions"] = {"The Stranger": "stair_foot"}
    main["rooms"]["bell_loft"]["adjacent"].append(
        {"to": "belfry_stair", "barrier": "closed_door", "dir": "s"})
    temp_db.wset(cid, "scene", main)
    hers = planned_room_brief(cid, away, ["bell_loft"])["bell_loft"]
    assert hers != planned_room_brief(cid, main, ["bell_loft"])["bell_loft"]
    unclean = dict(BELL, anchors={
        "wheel": {"desc": "the bell wheel", "dir": "s", "cell": [1, 1], "height": "waist"},
        "rope": {"desc": "the bell rope", "dir": "s", "cell": [1, 1], "height": "waist"}})
    filed = {"room": unclean, "turn": 1, "steps": 8, "clean": False,
             "brief": director_rooms._brief_signature(hers)}
    temp_db.wset(cid, director_rooms.PREPARED_KEY, {"bell_loft": filed})
    calls = []
    monkeypatch.setattr(common, "_agent_json", _designer(calls, {"bell_loft": BELL}))
    _wait(director_rooms.schedule_room_predevelopment(ctx))     # the player's run
    assert calls == [], "her design is neither taken up nor designed over"
    assert temp_db.wget(cid, director_rooms.PREPARED_KEY)["bell_loft"] == filed
    clean = dict(filed, room=BELL, clean=True)
    temp_db.wset(cid, director_rooms.PREPARED_KEY, {"bell_loft": clean})
    assert director_rooms.install_prepared_rooms(
        cid, main, "The Stranger", cast=ctx.cast)[1] == {}
    assert set(director_rooms.install_prepared_rooms(
        cid, away, None, cast=ctx.cast, frame_id=fid)[1]) == {"bell_loft"}
