"""Authored prose may contain several actual speakers and repeated lines."""
import json
import time

from agents import director, perception
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data, default_persona_data


def _ctx(db):
    pid = db.qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                ("Nia", json.dumps(default_persona_data("Nia")), "{}"))
    cid = db.qi("INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
                ("Speech test", "", time.time(), pid))
    ids = {}
    for name in ("Tomas", "Pavel", "Rin"):
        key = db.qi("INSERT INTO characters(name,sheet,source,created,resource_uid) VALUES(?,?,?,?,?)",
                    (name, json.dumps(default_character_data(name)), "{}", time.time(), name))
        db.qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
              (cid, key, "active", "{}"))
        ids[name] = key
    names = ["Nia", *ids]
    scene = {"rooms": {"bay": {"name": "Bay", "light": "bright", "adjacent": []}},
             "positions": {name: "bay" for name in names}, "entities": {}, "attire": {},
             "poses": {}, "stations": {}, "contacts": [], "overlays": {}}
    db.wset(cid, "scene", scene)
    db.wset(cid, "known", {name: names for name in names})
    cast = db.q("SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
                "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
                (cid, 1, 'Tomas said "Ready." Pavel said "Then leave it."', time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Speech test", persona_id=pid, lorebook_id=None,
                      scenario="", created=time.time()),
        turn=TurnData(id=tid, chat_id=cid, idx=1, player_input="", created=time.time()),
        cast=cast, input='Tomas said "Ready." Pavel said "Then leave it."')
    sequence = [{"type": "speech", "text": text, "volume": "normal",
                 "visibility": "overt", "chrono_id": n,
                 "actor": f"character:{ids[name]}",
                 "event_id": f"turn:{tid}:player:{n}:speech",
                 "from_declaration": f"turn:{tid}:primary:raw"}
                for n, (name, text) in enumerate(
                    [("Tomas", "Ready."), ("Pavel", "Then leave it.")], 1)]
    ctx.director_interpret = {
        "ledgers": [{}], "sequence": sequence, "speech": "Ready.", "action": None,
        "flow": {"reactors": [], "addressed_to": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}}}
    return ctx, ids, scene


def test_authored_npc_lines_keep_their_speakers_in_dialogue_and_both_views(temp_db, monkeypatch):
    ctx, ids, _ = _ctx(temp_db)
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {"ledgers": []})
    onset = perception.perception_act(ctx, "n0")
    assert 'Tomas says: "Ready."' in onset["views"][str(ids["Rin"]) ]
    assert 'Pavel says: "Then leave it."' in onset["views"][str(ids["Rin"]) ]
    assert '"Ready."' not in onset["views"][str(ids["Tomas"]) ]
    out = director.director_resolve(ctx, "n0")
    assert [(d["speaker"], d["exact_quote"]) for d in out["dialogue_log"]] == [
        ("Tomas", '"Ready."'), ("Pavel", '"Then leave it."')]
    ctx.director_resolve = out
    outcome = perception.perception_outcome(ctx, "n0")
    assert 'Tomas says: "Ready."' in outcome["views"]["player"]
    assert 'Pavel says: "Then leave it."' in outcome["views"]["player"]
    assert 'Nia says: "Ready."' not in outcome["views"][str(ids["Rin"]) ]


def test_same_line_before_and_after_movement_keeps_both_occurrences(temp_db, monkeypatch):
    from world.causal_program import event_worlds
    ctx, ids, scene = _ctx(temp_db)
    first = ctx.director_interpret["sequence"][0]
    move = {"type": "action", "observable": "walks to the corridor",
            "actor": first["actor"], "chrono_id": 2, "event_id": "move",
            "from_declaration": first["from_declaration"]}
    second = {**first, "chrono_id": 3, "event_id": "second", "volume": "whisper"}
    ctx.director_interpret["sequence"] = [first, move, second]
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {"ledgers": []})
    out = director.director_resolve(ctx, "n0")
    assert [(d["speaker"], d["exact_quote"], d["volume"]) for d in out["dialogue_log"]] == [
        ("Tomas", '"Ready."', "normal"), ("Tomas", '"Ready."', "whisper")]
    stream = perception._outcome_event_stream(
        ctx, scene, ctx.director_interpret, out, "Nia", out["dialogue_log"], [])
    assert [e["kind"] for e in stream] == ["speech", "action", "speech"]
    worlds = [{"stage": "interpret", "chrono_id": n, "events": [],
               "before": {"room": room}} for n, room in
              [(1, "bay"), (2, "bay"), (3, "corridor")]]
    assert event_worlds(worlds, stream)[0] == {"room": "bay"}
    assert event_worlds(worlds, stream)[2] == {"room": "corridor"}


def test_a_line_quoted_with_its_tags_comma_keeps_its_slot(temp_db, monkeypatch):
    """Playerless Aldermill round 7 (2026-09-23) idx 9: the author quoted
    "Aye. Keep your eyes open down there," before its tag and the dialogue
    log held it ending "."; compared as text the line bound to nothing, was
    appended after the listener's walk out of the square, and was heard from
    the room she ended in."""
    ctx, _ids, scene = _ctx(temp_db)
    first = dict(ctx.director_interpret["sequence"][0], text="Ready,")
    move = {"type": "action", "observable": "walks to the corridor",
            "actor": first["actor"], "chrono_id": 2, "event_id": "move",
            "from_declaration": first["from_declaration"]}
    ctx.director_interpret["sequence"] = [first, move]
    monkeypatch.setattr(director, "_agent_json", lambda *a, **k: {"ledgers": []})
    out = director.director_resolve(ctx, "n0")
    spoken = [dict(d, exact_quote='"Ready."') for d in out["dialogue_log"]]
    stream = perception._outcome_event_stream(
        ctx, scene, ctx.director_interpret, out, "Nia", spoken, [])
    assert [e["kind"] for e in stream] == ["speech", "action"]
