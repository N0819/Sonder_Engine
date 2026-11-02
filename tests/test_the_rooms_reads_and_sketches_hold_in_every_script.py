"""The Room's reads and its planting sketch, held to what they promise
(audit 2026-11-01: agents_narration_planner F8; story_room_carriers F9, F14
and efficiency 3).

* `inspect_charters` promised "every section is paged, never truncated" and,
  past the 12,000-character result cap, `fit_result` deleted the whole
  `charters` overview: a twelve-institution town answered with no
  institution at all.
* The planting sketch read a join's barrier out of its free-prose `way`
  with an ASCII, English-ordered reader, so every Japanese door and window
  became an open passage.
* A generated journey in a Japanese story counted its memories with
  `.split()`, so every one was "thin" and the launch raised.
* A sketch payload read the standing grants once per capability it asked
  about.
"""
from __future__ import annotations

import json
import time

import pytest


# ---------------------------------------------------------------------------
# agents_narration_planner F8 -- the overview pages, it never vanishes
# ---------------------------------------------------------------------------

def _chat(db):
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                ("Town", "", time.time()))
    db.wset(cid, "scene", {"location": "Town", "rooms": {}, "positions": {},
                           "entities": {}, "attire": {}})
    db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
          (cid, 0, "", time.time()))
    return cid


def _institution(key, bodies=12):
    from world.charter import normalize_charter
    state = {
        "key": key, "clock_hours": 1.0,
        "upkeeps": {"u%d" % i: {"place": "%s_hall" % key, "level": 0.8,
                                "floor": 0.3, "drift_per_hour": 0.02,
                                "service_per_hour": 0.05,
                                "requires": {"labour": 1}}
                    for i in range(6)},
        "posts": {"p%d" % i: {"place": "%s_hall" % key, "serves": ["u%d" % i],
                              "requires": {"labour": 1},
                              "purpose": "keeps the %s going for the house" % i}
                  for i in range(6)},
        "bodies": {"b%02d" % i: {"name": "%s Person %02d" % (key.title(), i),
                                 "competence": {"labour": 1},
                                 "place": "%s_hall" % key,
                                 "home_post": "p%d" % (i % 6)}
                   for i in range(bodies)},
        "watch": {"p%d" % i: "b%02d" % i for i in range(6)},
    }
    return normalize_charter(state)


def test_a_twelve_institution_overview_names_every_institution(temp_db):
    from story.room_tools import TOOL_RESULT_CHARS, run_tool
    from world.charter_runtime import save_registry
    cid = _chat(temp_db)
    keys = ["house_%02d" % i for i in range(12)]
    save_registry(cid, {"items": {k: {"state": _institution(k)} for k in keys}})
    out = run_tool(cid, "inspect_charters", {})
    assert len(json.dumps(out, ensure_ascii=False)) <= TOOL_RESULT_CHARS
    assert "truncated" not in out, sorted(out)
    shown = set(out.get("charters") or {})
    withheld = {row["key"] for row in out.get("charters_withheld") or ()}
    assert shown, "the overview names institutions"
    assert shown | withheld == set(keys)
    assert not shown & withheld
    for row in out.get("charters_withheld") or ():
        assert "inspect_charters" in row["ask"] and row["key"] in row["ask"]
    # Every section the overview DID show is a page that says what it holds back.
    for entry in out["charters"].values():
        assert entry["counts"]["bodies"] == 12
        if len(entry.get("bodies") or ()) < 12:
            assert entry["withheld"]["bodies"]["withheld"] == 12 - len(entry["bodies"])


def test_a_small_town_overview_is_as_it_was(temp_db):
    from story.room_tools import CHARTER_OVERVIEW_ROWS, run_tool
    from world.charter_runtime import save_registry
    cid = _chat(temp_db)
    save_registry(cid, {"items": {"house_00": {"state": _institution("house_00")}}})
    out = run_tool(cid, "inspect_charters", {})
    assert "charters_withheld" not in out
    entry = out["charters"]["house_00"]
    assert len(entry["bodies"]) == CHARTER_OVERVIEW_ROWS
    assert out["rows_per_page"] == CHARTER_OVERVIEW_ROWS


# ---------------------------------------------------------------------------
# story_room_carriers F14 -- a join's barrier is a field, not a reading of prose
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("way, barrier, expected", [
    ("鍵のかかった鉄の門", "closed_door", "closed_door"),
    ("細い窓から", "window", "window"),
    ("the bolted cellar door", "closed_door", "closed_door"),
    ("a curtained arch", "open_door", "open_door"),
])
def test_a_sketched_join_takes_its_barrier_from_the_field(way, barrier, expected):
    from story.room_sketch import _edge
    edge = _edge("quay", {"way": way, "barrier": barrier})
    assert edge["to"] == "quay" and edge["name"] == way
    assert edge.get("barrier") == expected


def test_a_barrier_the_vocabulary_cannot_read_leaves_the_way_open():
    from story.room_sketch import _edge
    edge = _edge("quay", {"way": "a gap in the nets", "barrier": "kinda shut"})
    assert "barrier" not in edge


def test_a_japanese_way_with_no_barrier_field_is_not_read_for_one():
    """With no field the label is never parsed in a script the reader cannot
    read: an opening, as before, and never a guess."""
    from story.room_sketch import _edge
    assert "barrier" not in _edge("quay", {"way": "細い石段"})


# ---------------------------------------------------------------------------
# story_room_carriers F9 -- a Japanese journey is measured in its own words
# ---------------------------------------------------------------------------

JA_MEMORY = ("私はあの夜、港の灯台の下で兄と別れた。冷たい潮風が頬を打ち、"
             "兄は古い羅針盤を私の手に握らせて、必ず戻ると約束した。"
             "私は泣かずに頷いたが、船の灯が霧に消えるまで桟橋に立ち尽くしていた。"
             "あの羅針盤は今も私の鞄の底にある。")


def test_a_long_first_person_japanese_memory_is_not_thin():
    from language_runtime import language_scope
    from story.journey_history import ground_journey_history
    events = [{"sequence": i + 1, "when": "春", "place": "港",
               "memory": JA_MEMORY, "kind": "departure", "consequence": "兄を待つ"}
              for i in range(4)]
    with language_scope("ja"):
        out = ground_journey_history({"summary": "s", "events": events}, [],
                                     generated=True)
    assert out["grounding"]["dropped"] == [], out["grounding"]["dropped"]
    assert len(out["events"]) >= 1


def test_a_short_japanese_line_is_still_thin():
    from language_runtime import language_scope
    from story.journey_history import ground_journey_history
    with language_scope("ja"):
        out = ground_journey_history({"summary": "s", "events": [
            {"sequence": 1, "when": "春", "place": "港", "memory": "私は港に着いた。",
             "kind": "arrival"}]}, [], generated=True)
    assert [d["reason"] for d in out["grounding"]["dropped"]] == ["thin_memory"]


def test_an_english_memory_is_counted_as_before():
    from story.journey_history import _GENERATED_MEMORY_FLOOR_WORDS, memory_words
    text = " ".join(["word"] * _GENERATED_MEMORY_FLOOR_WORDS)
    assert memory_words(text) == _GENERATED_MEMORY_FLOOR_WORDS
    assert memory_words("I don't know -- it was well-known.") == len(
        "I don't know -- it was well-known.".split())


# ---------------------------------------------------------------------------
# story_room_carriers efficiency 3 -- a sketch reads the grants once
# ---------------------------------------------------------------------------

def test_a_sketch_payload_reads_the_standing_grants_once(temp_db, monkeypatch):
    from story import mandates as md
    from story import room_frontier as rf
    from story.room_sketch import sketch_payload
    cid = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                     ("Sketch", "A port.", time.time()))
    temp_db.wset(cid, "scene", {"location": "Port", "rooms": {
        "quay": {"name": "Quay", "desc": "Wet stone.", "adjacent": []}},
        "positions": {"The Stranger": "quay"}, "entities": {}, "attire": {}})
    for i in range(3):
        temp_db.qi("INSERT INTO turns(chat_id,idx,player_input,created) "
                   "VALUES(?,?,?,?)", (cid, i, "", time.time()))
    md.grant_mandate(cid, None, text="Plan ahead.",
                     capabilities=["plan_rooms", "plan_entity", "create_people",
                                   "arrival", "incident"])
    report = rf.frontier_report(cid, None)
    reads = []
    real = md.active_mandates
    monkeypatch.setattr(md, "active_mandates",
                        lambda *a, **k: reads.append(1) or real(*a, **k))
    _context, payload = sketch_payload(cid, None, report, turn_idx=2)
    assert payload["granted"]["rooms"] and payload["granted"]["people"]
    assert len(reads) == 1
