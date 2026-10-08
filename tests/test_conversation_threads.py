"""People in a room talk to each other, and it lasts while you are there.

The owner, 2026-10-07: "lets say you ask a charter npc to do something and
they imediatley start talking to their peers to get the task done so an
actualy conversation runs for as long as you are in that room", with talk
among themselves wanted but "even that I don't want overdone"
(`docs/design/DESIGN_CONVERSATION_THREADS.md`). A thread is voiced one
exchange a beat by one call for its people together; it becomes ordinary
figure declarations; the commit advances, opens and closes it from the
beat's typed reactions.
"""
from __future__ import annotations

from types import SimpleNamespace

from agents import background
from core.db import wget_for_frame, wset_for_frame
from persist.commit import advance_conversation_threads
from tests import test_a_charter_body_speaks_before_the_director_resolves as beat

KEEPER, HAND, COOK = "Marta Hale", "Ned Rook", "Old Ivy"


def _thread(**over):
    t = {"room": "scullery", "participants": [KEEPER, HAND],
         "purpose": "fetch the tally book from the back shelf", "to": "the stranger",
         "origin": "delegation", "opened_turn": 6, "last_turn": 6,
         "exchanges": 0, "status": "open", "last": []}
    t.update(over)
    return t


def _exchange(*lines, done=False, hands_over=None, by=""):
    return {"lines": [dict(speaker=s, words=w, to=to, act=a, tone="", goes_to="")
                      for s, w, to, a in lines],
            "hands_over": hands_over, "hands_over_by": by, "done": done}


def _declare(monkeypatch, temp_db, thread, exchange, *, addressed=(), rows=None):
    cid = beat._chat(temp_db)
    wset_for_frame(cid, background.THREADS_KEY, {"t1": thread}, None)
    sc = {**beat.SC, "positions": {"Iris Vale": "scullery"}}
    asked, voiced = [], []
    monkeypatch.setattr(background, "_react_one",
                        lambda ctx, dr, name, *a, **k: asked.append(name) or None)
    monkeypatch.setattr(background, "_player_room", lambda ctx, sc_: "scullery")
    monkeypatch.setattr(background, "_voice_thread",
                        lambda ctx, b, t, rs, nonce: voiced.append(
                            [r["name"] for r in rs]) or exchange)
    interp = dict(beat.TestTheDeclaredBeatIsWhatTheVoiceHears.INTERP)
    interp["flow"] = {"addressed_to_refs": list(addressed)}
    rows = rows or [{"name": n, "room": "scullery"} for n in (KEEPER, HAND, COOK)]
    out = background.declare_charter_figures(beat._ctx(cid), interp, sc, rows, [], 0)
    return out, asked, voiced


def test_a_threads_people_are_voiced_together_in_order(monkeypatch, temp_db):
    out, asked, voiced = _declare(monkeypatch, temp_db, _thread(), _exchange(
        (KEEPER, "Ned, the tally book's on the back shelf. Fetch it down.", HAND, ""),
        (HAND, "The blue one?", KEEPER, "sets down the rag")))
    assert voiced == [[KEEPER, HAND]]
    threaded = [d for d in out if d.get("thread")]
    assert [d["name"] for d in threaded] == [KEEPER, HAND]
    assert threaded[0]["dialogue_log_entry"]["intended_target"] == HAND
    assert [e["type"] for e in threaded[1]["sequence"]] == ["action", "speech"]
    assert {d["thread"]["id"] for d in threaded} == {"t1"}
    assert KEEPER not in asked and HAND not in asked, "voiced together, not one by one"


def test_each_speaks_once_and_only_its_own_people(monkeypatch, temp_db):
    out, _asked, _voiced = _declare(monkeypatch, temp_db, _thread(), _exchange(
        (KEEPER, "Fetch it down.", HAND, ""),
        ("Somebody Else", "I'll get it.", KEEPER, ""),
        (KEEPER, "And mind the step.", HAND, ""),
        (HAND, "Aye.", KEEPER, "")))
    assert [d["name"] for d in out if d.get("thread")] == [KEEPER, HAND]


def test_a_thread_waits_while_one_of_its_people_is_spoken_to(monkeypatch, temp_db):
    _out, asked, voiced = _declare(monkeypatch, temp_db, _thread(), _exchange(
        (KEEPER, "Fetch it.", HAND, "")), addressed=[HAND])
    assert voiced == [] and HAND in asked


def test_a_thread_nobody_can_hear_is_not_voiced(monkeypatch, temp_db):
    _out, _asked, voiced = _declare(monkeypatch, temp_db, _thread(room="yard"),
                                    _exchange((KEEPER, "Fetch it.", HAND, "")),
                                    rows=[{"name": KEEPER, "room": "yard"},
                                          {"name": HAND, "room": "yard"}])
    assert voiced == []


def test_the_thing_handed_over_rides_the_one_who_handed_it(monkeypatch, temp_db):
    out, _asked, _voiced = _declare(monkeypatch, temp_db, _thread(), _exchange(
        (HAND, "Here.", KEEPER, "hands down a blue tally book"),
        hands_over={"what": "the blue tally book", "to": KEEPER}, by=HAND))
    (hand,) = [d for d in out if d.get("thread")]
    assert hand["hands_over"] == {"what": "the blue tally book", "to": KEEPER}


def test_the_group_call_is_handed_only_what_is_common(monkeypatch, temp_db):
    """The design note's §3: a group call is where one body could voice
    another's knowledge, so it gets nothing private -- overt lines only, and
    each participant by name, post and look."""
    cid = beat._chat(temp_db)
    seen = {}

    def model(role, schema_key, prompt, payload, **kwargs):
        seen.update(role=role, key=schema_key, payload=payload)
        return {"lines": [], "hands_over": None, "hands_over_by": "", "done": False}

    monkeypatch.setattr(background, "_agent_json", model)
    monkeypatch.setattr(background, "_place_block", lambda ctx, room, **k: {"room": room})
    monkeypatch.setattr(background, "_common_knowledge", lambda ctx, room: [])
    monkeypatch.setattr(background, "get_prompt", lambda pid, language=None: pid)
    talk = {"dialogue_log": [
        {"speaker": "Iris Vale", "exact_quote": '"Is the book here?"',
         "intended_target": KEEPER, "visibility": "overt"},
        {"speaker": "Iris Vale", "exact_quote": '"Keep it from him."',
         "intended_target": KEEPER, "visibility": "concealed",
         "conceal_from": [HAND]}]}
    rows = [{"name": KEEPER, "room": "scullery", "body": "keeper:0001",
             "appearance": "a broad woman in an apron"},
            {"name": HAND, "room": "scullery", "body": "tap_hand:0002"}]
    ctx = beat._ctx(cid)
    ctx.language = "en"
    background._voice_thread(ctx, talk, _thread(), rows, 0)
    payload = seen["payload"]
    assert (seen["role"], seen["key"]) == ("character_bg", "conversation_thread")
    assert [h["words"] for h in payload["heard"]] == ['"Is the book here?"']
    assert payload["participants"] == [
        {"name": KEEPER, "post": "keeper", "look": "a broad woman in an apron"},
        {"name": HAND, "post": "tap hand", "look": ""}]
    assert set(payload) == {"place", "common_knowledge", "purpose", "for",
                            "participants", "heard", "last", "lines_at_most",
                            "variant_seed"}


# --------------------------------------------------------------------------
# The commit: opened by a task, moved on by the beat, closed when settled
# --------------------------------------------------------------------------

def _ctx(cid, idx=7):
    return SimpleNamespace(chat=SimpleNamespace(id=cid),
                           turn=SimpleNamespace(frame_id=None, idx=idx),
                           add_warning=lambda *_a: None)


def _ledger(*names):
    posts = {KEEPER: ("inn", "innkeeper:0001"), HAND: ("inn", "tap_hand:0002"),
             COOK: ("mill", "cook:0001")}
    return {"p_%d" % i: {"name": n, "charter_refs": [{"charter": posts[n][0],
                                                      "body": posts[n][1]}],
                         "sketch": {"station_room": "taproom"}}
            for i, n in enumerate(names)}


SCENE = {"rooms": {"taproom": {"name": "Taproom", "adjacent": []}},
         "positions": {KEEPER: "taproom", HAND: "taproom", COOK: "taproom"},
         "entities": {}}


def _owes(name=KEEPER, what="the tally book", to="the stranger"):
    return {"name": name, "room": "taproom", "action": "turns to the back",
            "dialogue_log_entry": {"speaker": name, "exact_quote": "Wait there."},
            "still_owes": {"what": what, "to": to}}


def test_a_task_taken_in_front_of_a_coworker_opens_a_thread(temp_db):
    cid = beat._chat(temp_db)
    kept = advance_conversation_threads(_ctx(cid), [_owes()], SCENE,
                                        _ledger(KEEPER, HAND, COOK))
    (thread,) = kept.values()
    assert thread["participants"] == [KEEPER, HAND], "a coworker, not the miller's cook"
    assert (thread["purpose"], thread["to"], thread["origin"]) == (
        "the tally book", "the stranger", "delegation")
    assert wget_for_frame(cid, background.THREADS_KEY, None, {}) == kept


def test_no_coworker_in_the_room_is_no_thread(temp_db):
    cid = beat._chat(temp_db)
    assert advance_conversation_threads(_ctx(cid), [_owes()], SCENE,
                                        _ledger(KEEPER, COOK)) == {}


def test_one_thread_a_room(temp_db):
    cid = beat._chat(temp_db)
    wset_for_frame(cid, background.THREADS_KEY, {"t0": _thread(room="taproom",
                                                              last_turn=7)}, None)
    kept = advance_conversation_threads(_ctx(cid), [_owes()], SCENE,
                                        _ledger(KEEPER, HAND))
    assert list(kept) == ["t0"]


def _voiced(tid, *rows):
    return [{"name": n, "dialogue_log_entry": {"exact_quote": w}, "action": "",
             "thread": {"id": tid, "done": done}, **({"hands_over": h} if h else {})}
            for n, w, done, h in rows]


def test_an_exchange_moves_the_thread_on(temp_db):
    cid = beat._chat(temp_db)
    wset_for_frame(cid, background.THREADS_KEY, {"t1": _thread()}, None)
    kept = advance_conversation_threads(_ctx(cid), _voiced(
        "t1", (KEEPER, '"Fetch it."', False, None), (HAND, '"Aye."', False, None)),
        SCENE, {})
    assert kept["t1"]["exchanges"] == 1 and kept["t1"]["last_turn"] == 7
    assert [line["words"] for line in kept["t1"]["last"]] == ['"Fetch it."', '"Aye."']


def test_it_closes_when_settled_handed_over_or_long_enough(temp_db):
    cid = beat._chat(temp_db)
    for rows, start in (([(KEEPER, '"That\'s that."', True, None)], 0),
                        ([(HAND, '"Here."', False, {"what": "the book", "to": KEEPER})], 0),
                        ([(KEEPER, '"Again."', False, None)],
                         background.THREAD_MAX_EXCHANGES - 1)):
        wset_for_frame(cid, background.THREADS_KEY, {"t1": _thread(exchanges=start)}, None)
        assert advance_conversation_threads(_ctx(cid), _voiced("t1", *rows), SCENE, {}) == {}


def test_a_thread_nobody_hears_lapses(temp_db):
    cid = beat._chat(temp_db)
    wset_for_frame(cid, background.THREADS_KEY, {"t1": _thread(last_turn=2)}, None)
    assert advance_conversation_threads(
        _ctx(cid, idx=2 + background.THREAD_IDLE_BEATS + 1), [], SCENE, {}) == {}


def _owing(what):
    return {"p_0": {"name": KEEPER, "pending_act": {"what": what, "to": "the stranger"}}}


def test_a_delivered_delegation_discharges_the_owners_debt(temp_db):
    """The keeper took the task and Ned put the thing in hand: the keeper is
    not asked again to deliver it."""
    cid = beat._chat(temp_db)
    wset_for_frame(cid, background.THREADS_KEY, {"t1": _thread()}, None)
    presences = _owing(_thread()["purpose"])
    advance_conversation_threads(_ctx(cid), _voiced(
        "t1", (HAND, '"Here."', False, {"what": "the tally book", "to": "the stranger"})),
        SCENE, presences)
    assert "pending_act" not in presences["p_0"]


def test_a_different_debt_is_not_discharged(temp_db):
    cid = beat._chat(temp_db)
    wset_for_frame(cid, background.THREADS_KEY, {"t1": _thread()}, None)
    presences = _owing("a bowl of stew")
    advance_conversation_threads(_ctx(cid), _voiced(
        "t1", (HAND, '"Here."', False, {"what": "the tally book", "to": "the stranger"})),
        SCENE, presences)
    assert presences["p_0"]["pending_act"]["what"] == "a bowl of stew"
