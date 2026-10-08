"""Room predevelopment: the host's to turn on, and a brief designed once.

Measured on the Brackwater run (chat 166, 2026-10-07, 30 beats): preparing
the planned rooms beside the player between turns spent 131 designer calls --
1.76M prompt tokens (0.57M uncached), 51k response, 964 s -- on 25 designs, at
least 19 of which never seeded a beat. Every seeded design was judged
unfinished on its first look, because it was made with no prose to read the
room against, and on the one matched pair (turn 3, the low walk) the seeded
runs took 7 and 6 steps where the unseeded run took 3. So it is OFF until the
host turns it on (`PREDEVELOP_SETTING`).

For when it is on, the waste the same run measured: a design was kept only on
a clean final check and a failed attempt left nothing behind, so four design
runs opened on the identical 8,558-token first call. Now every attempt is
filed under the fingerprint of the brief it was made from, a design whose
check failed is kept as a seed, and a brief is designed again only when the
plan changes it.
"""

from __future__ import annotations

import json
import time

from agents import director_rooms
from llm import decisions

from tests.director_fakes import _action_interp, _make_ctx

SCENE = {
    "rooms": {
        "hall": {"name": "Hall", "desc": "A hall.", "extent": {"w": 6, "d": 4},
                 "adjacent": [{"to": "study", "barrier": "open", "dir": "n"}]},
        "study": {"name": "Study", "planned": True, "adjacent": [
            {"to": "hall", "barrier": "open", "dir": "s"}]},
    },
    "positions": {"The Stranger": "hall"},
}


def _wait(job):
    deadline = time.monotonic() + 10.0
    while job.state in ("pending", "running") and time.monotonic() < deadline:
        time.sleep(0.02)
    assert job.state == "done", job.as_dict()
    return job


def _study_designer(calls, room=None):
    """A designer that drafts the study whole and submits."""
    def answer(*args, **kwargs):
        calls.append(args)
        return {"calls": [
            {"tool": "draft_room", "args": {"room_id": "study", "room": room or {
                "name": "Study", "desc": "Shelves and a desk."}}},
            {"tool": "submit", "args": {}}]}
    return answer


def _brief(monkeypatch, purpose="a quiet room"):
    from world import structure
    brief = {"study": {"name": "Study", "purpose": purpose,
                       "exits": [{"to": "hall", "name": "Hall"}]}}
    monkeypatch.setattr(structure, "planned_room_brief",
                        lambda cid, sc, ids: {k: v for k, v in brief.items() if k in ids})
    return brief


def test_predevelopment_is_off_until_the_host_turns_it_on(temp_db, monkeypatch):
    """Off, no job is queued, no call is made, and a design an earlier run
    cached does not go on seeding beats."""
    import agents.common as common
    ctx = _make_ctx(temp_db, interp=_action_interp())
    temp_db.wset(ctx.chat.id, "scene", SCENE)
    _brief(monkeypatch)
    calls = []
    monkeypatch.setattr(common, "_agent_json", _study_designer(calls))
    temp_db.wset(ctx.chat.id, director_rooms.PREPARED_KEY,
                 {"study": {"room": {"name": "Study", "desc": "Old design."}}})

    assert director_rooms.predevelopment_enabled() is False
    assert director_rooms.schedule_room_predevelopment(ctx) is None
    assert director_rooms.prepared_rooms(ctx.chat.id, ["study"]) == {}
    assert calls == []

    temp_db.set_setting(director_rooms.PREDEVELOP_SETTING, "1")
    assert director_rooms.prepared_rooms(ctx.chat.id, ["study"])["study"]["desc"] \
        == "Old design."


def test_an_unchanged_brief_is_designed_once(temp_db, monkeypatch):
    import agents.common as common
    temp_db.set_setting(director_rooms.PREDEVELOP_SETTING, "1")
    ctx = _make_ctx(temp_db, interp=_action_interp())
    temp_db.wset(ctx.chat.id, "scene", SCENE)
    brief = _brief(monkeypatch)
    calls = []
    monkeypatch.setattr(common, "_agent_json", _study_designer(calls))

    _wait(director_rooms.schedule_room_predevelopment(ctx))
    first = len(calls)
    assert first >= 1
    entry = temp_db.wget(ctx.chat.id, director_rooms.PREPARED_KEY)["study"]
    assert entry["clean"] is True
    assert entry["brief"] == director_rooms._brief_signature(brief["study"])

    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert len(calls) == first, "the same brief is not designed again"

    # The plan changes what the room is for: that is a new job.
    brief["study"]["purpose"] = "the keeper's records room"
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert len(calls) > first


def test_a_design_whose_check_failed_is_kept_as_a_seed(temp_db, monkeypatch):
    """Two fixtures on one cell at one height is a check the design never
    passed within its steps: kept, flagged, and handed to the beat that
    enters the room -- not thrown away to be built again from nothing."""
    import agents.common as common
    temp_db.set_setting(director_rooms.PREDEVELOP_SETTING, "1")
    monkeypatch.setattr(director_rooms, "MAX_ROOM_STEPS", 1)
    ctx = _make_ctx(temp_db, interp=_action_interp())
    temp_db.wset(ctx.chat.id, "scene", SCENE)
    _brief(monkeypatch)
    calls = []
    stacked = {"name": "Study", "desc": "Shelves and a desk.",
               "extent": {"w": 4, "d": 3},
               "anchors": {"stool": {"desc": "a stool", "dir": "n", "cell": [1, 1]},
                           "chair": {"desc": "a chair", "dir": "n", "cell": [1, 1]}}}
    monkeypatch.setattr(common, "_agent_json", _study_designer(calls, stacked))

    _wait(director_rooms.schedule_room_predevelopment(ctx))
    entry = temp_db.wget(ctx.chat.id, director_rooms.PREPARED_KEY)["study"]
    assert entry["clean"] is False and entry["room"]["anchors"]
    seed = director_rooms.prepared_rooms(ctx.chat.id, ["study"])
    assert set(seed["study"]["anchors"]) == {"stool", "chair"}

    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert len(calls) == 1, "a failed check is not a reason to design the brief again"


def test_a_seed_whose_check_fails_arrives_with_its_check():
    """The first thing the in-turn designer reads is what the seed's check
    found, not an empty transcript it spends a step rediscovering."""
    scene = {"rooms": {"hall": SCENE["rooms"]["hall"]}, "positions": {}}
    seed = {"gallery": {"name": "Gallery", "desc": "Maps.", "extent": {"w": 4, "d": 3},
                        "adjacent": [{"to": "hall", "barrier": "open", "dir": "s"}],
                        "anchors": {"a": {"desc": "a chest", "dir": "n", "cell": [1, 1]},
                                    "b": {"desc": "a stool", "dir": "n", "cell": [1, 1]}}}}
    seen = []

    def call(system, payload):
        seen.append(payload)
        return {"calls": []}

    director_rooms.design_rooms(None, scene, {"prose": "Mara studies the maps."},
                                "sheet", ["gallery"], call, {}, seed=seed)
    first = seen[0]["transcript"]
    assert first and first[0]["by"] == "engine" and first[0]["tool"] == "check"
    assert first[0]["step"] == 0 and first[0]["result"]["clean"] is False
    assert first[0]["result"]["fixtures_overlapping"]


def test_a_clean_seed_the_prose_outgrew_arrives_with_what_is_missing(monkeypatch):
    """Clean but unfinished against this beat's prose: what the decision
    model found comes with the seed, and is said once -- not again on the
    first step that changes the draft."""
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.9 if key == "room_done_missing" else 0.1}
        for key in questions})
    scene = {"rooms": {"hall": SCENE["rooms"]["hall"]}, "positions": {}}
    seed = {"gallery": {"name": "Gallery", "desc": "A long gallery.", "size": "small",
                        "extent": {"w": 6, "d": 4},
                        "adjacent": [{"to": "hall", "barrier": "open", "dir": "s"}]}}
    seen = []
    steps = iter([{"calls": [{"tool": "draft_room", "args": {"room_id": "gallery", "room": {
        "desc": "A long gallery hung with maps."}}}]},
        {"calls": [{"tool": "submit", "args": {}}]}])

    def call(system, payload):
        seen.append(payload)
        return next(steps)

    record = {}
    director_rooms.design_rooms(None, scene, {"prose": "Mara studies the maps on the wall."},
                                "sheet", ["gallery"], call, record, seed=seed)
    first = seen[0]["transcript"]
    assert first and first[0]["tool"] == "complete" and first[0]["step"] == 0
    assert "does not mention" in first[0]["result"]["still_missing"][0]
    assert record["still_missing_said"] == 0
    later = [e for e in seen[-1]["transcript"] if e["tool"] == "complete"]
    assert len(later) == 1, "said once, at the seed's first look"


def test_a_design_made_from_an_old_brief_does_not_seed_the_beat(temp_db, monkeypatch):
    """A design seeds only the brief it was made from. Handed the beat's own
    briefs, `prepared_rooms` refuses one whose brief the plan has since
    changed -- a re-plan landing after the last commit tail (review of the
    2026-10-08 landing)."""
    temp_db.set_setting(director_rooms.PREDEVELOP_SETTING, "1")
    ctx = _make_ctx(temp_db, interp=_action_interp())
    old = {"name": "Study", "purpose": "a quiet room"}
    temp_db.wset(ctx.chat.id, director_rooms.PREPARED_KEY, {"study": {
        "room": {"name": "Study", "desc": "Shelves and a desk."},
        "brief": director_rooms._brief_signature(old)}})

    assert director_rooms.prepared_rooms(ctx.chat.id, {"study": old})["study"]["desc"] \
        == "Shelves and a desk."
    replanned = dict(old, purpose="the keeper's records room")
    assert director_rooms.prepared_rooms(ctx.chat.id, {"study": replanned}) == {}


def test_a_far_stubs_design_does_not_outlive_its_re_plan(temp_db, monkeypatch):
    """The cache keeps a design while its room is a stub AND its brief is the
    one it was made from, near or far."""
    import agents.common as common
    temp_db.set_setting(director_rooms.PREDEVELOP_SETTING, "1")
    ctx = _make_ctx(temp_db, interp=_action_interp())
    temp_db.wset(ctx.chat.id, "scene", SCENE)
    brief = _brief(monkeypatch)
    monkeypatch.setattr(common, "_agent_json", _study_designer([]))
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert "study" in temp_db.wget(ctx.chat.id, director_rooms.PREPARED_KEY)

    brief["study"]["purpose"] = "the keeper's records room"
    from world import structure
    monkeypatch.setattr(structure, "rooms_to_develop", lambda sc, room: [])
    _wait(director_rooms.schedule_room_predevelopment(ctx))
    assert "study" not in temp_db.wget(ctx.chat.id, director_rooms.PREPARED_KEY)


def test_an_inspect_result_is_fitted_room_by_room():
    """Whole records in the order asked while they fit, the first always,
    the rest named to ask for again -- never one raw prefix that cuts a
    record mid-field and loses every room after it."""
    big = "x" * 7000
    scene = {"rooms": {rid: {"name": rid, "desc": big, "extent": {"w": 4, "d": 4},
                             "adjacent": []} for rid in ("a", "b", "c")},
             "positions": {}}
    fitted = director_rooms._fit_inspection(
        director_rooms._inspect(scene, ["a", "b", "c"], whole=True))
    assert "truncated" not in json.dumps(fitted)
    assert fitted["a"]["record"]["desc"] == big
    shown = [rid for rid in ("a", "b", "c") if rid in fitted]
    assert shown[0] == "a" and fitted["not_shown"]["rooms"] == [
        rid for rid in ("a", "b", "c") if rid not in shown]
    assert len(json.dumps(fitted)) <= director_rooms.ROOM_INSPECT_CHARS + 200

    # A record that fits only without its drawing: a large room's map is
    # what tips it over (40 x 30 paces, 16.4k with the map, 15.1k without).
    huge = {"rooms": {"a": {"name": "a", "desc": "y" * 15000,
                            "extent": {"w": 40, "d": 30}, "adjacent": []}},
            "positions": {}}
    whole = director_rooms._inspect(huge, ["a"], whole=True)
    assert len(json.dumps(whole)) > director_rooms.ROOM_INSPECT_CHARS
    alone = director_rooms._fit_inspection(whole)
    assert alone["a"]["record"]["desc"] == "y" * 15000, \
        "the drawing goes before the record is cut"
    assert "map" not in alone["a"]
