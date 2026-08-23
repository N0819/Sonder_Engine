"""A delivered Charter introduction teaches names without leaking them."""

import json
import time

from core.pipeline_context import ChatData, PipelineContext, TurnData
from persist.commit import prepare_memory_commit
from story.character_schema import default_character_data, default_persona_data
from world.charter_runtime import save_registry


def _story(temp_db, *, ysra_place="gate", with_character=False):
    persona = default_persona_data("Rowan Hale")
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        ("Rowan Hale", json.dumps(persona), "{}"))
    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Names", "", time.time(), persona_id))
    cast = []
    char_id = None
    if with_character:
        sheet = default_character_data("Mara Venn")
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            ("Mara Venn", json.dumps(sheet), "{}", time.time(), "mara"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (cid, char_id, "active", "{}"))
        cast = temp_db.q(
            "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,))
    save_registry(cid, {"watch": {
        "key": "watch",
        "naming": {
            "formal_format": "{title} {name}",
            "titles": {"ranks": {"captain": "Captain"}},
        },
        "bodies": {
            "ysra": {"name": "Ysra Vale", "rank": "captain",
                     "place": ysra_place},
            "mett": {"name": "Mett Voss", "place": "gate"},
        },
    }})
    scene = {
        "rooms": {"gate": {"name": "North Gate"},
                  "infirmary": {"name": "Infirmary"}},
        "positions": {"Rowan Hale": "gate", "Mara Venn": "gate"},
    }
    temp_db.wset(cid, "scene", scene)
    chat = ChatData(id=cid, name="Names", persona_id=persona_id,
                    lorebook_id=None, scenario="", created=time.time())
    turn = TurnData(id=701, chat_id=cid, idx=3, player_input="Who is she?",
                    created=time.time())
    views = {"player": 'A guard says, "Captain Ysra Vale."'}
    if char_id is not None:
        views[str(char_id)] = 'You hear a guard say, "Captain Ysra Vale."'
    ctx = PipelineContext(
        chat=chat, turn=turn, cast=cast, input="Who is she?",
        director_resolve={
            "resolved_event": "A guard identifies the captain.",
            "dialogue_log": [{
                "speaker": "Mett Voss",
                "exact_quote": "Captain Ysra Vale.",
                "intended_target": "Rowan Hale",
            }],
        },
        perception_outcome={"views": views},
    )
    return cid, char_id, ctx


def _without_embeddings(monkeypatch):
    from persist import commit_memory
    monkeypatch.setattr(
        commit_memory, "prepare_memories_batch",
        lambda rows: {"prepared": rows, "embedded": None})


def test_the_player_learns_a_colocated_charter_name(
        temp_db, monkeypatch):
    _without_embeddings(monkeypatch)
    _cid, _char_id, ctx = _story(temp_db)
    prepared = prepare_memory_commit(ctx)
    assert prepared["names_learned"] == {
        "Rowan Hale": ["Ysra Vale", "Captain Ysra Vale"]}


def test_a_full_character_learns_the_same_delivered_name(
        temp_db, monkeypatch):
    _without_embeddings(monkeypatch)
    _cid, _char_id, ctx = _story(temp_db, with_character=True)
    prepared = prepare_memory_commit(ctx)
    assert prepared["names_learned"] == {
        "Rowan Hale": ["Ysra Vale", "Captain Ysra Vale"],
        "Mara Venn": ["Ysra Vale", "Captain Ysra Vale"],
    }


def test_hearing_about_an_absent_charter_body_does_not_grant_recognition(
        temp_db, monkeypatch):
    _without_embeddings(monkeypatch)
    _cid, _char_id, ctx = _story(temp_db, ysra_place="infirmary")
    prepared = prepare_memory_commit(ctx)
    assert prepared["names_learned"] == {}


def test_a_titleless_introduction_matches_a_titled_display_name(
        temp_db, monkeypatch):
    _without_embeddings(monkeypatch)
    _cid, _char_id, ctx = _story(temp_db)
    ctx.director_resolve["dialogue_log"][0]["exact_quote"] = "Ysra Vale."
    ctx.perception_outcome["views"]["player"] = 'A guard says, "Ysra Vale."'
    prepared = prepare_memory_commit(ctx)
    assert prepared["names_learned"] == {
        "Rowan Hale": ["Ysra Vale", "Captain Ysra Vale"]}


def test_name_lookup_does_not_scan_five_thousand_people_per_line(monkeypatch):
    from persist import commit_common
    roster = [f"Given{i} House{i}" for i in range(5000)]
    rooms = {name: "gate" for name in roster}
    index = commit_common._address_index(roster)
    calls = 0
    real = commit_common._form_in

    def counted(form, body):
        nonlocal calls
        calls += 1
        return real(form, body)

    monkeypatch.setattr(commit_common, "_form_in", counted)
    learned = commit_common._names_heard_in(
        "Captain Given4999 House4999.", "Rowan", roster, {}, "gate",
        rooms_by_name=rooms, address_index=index)
    assert learned == ["Given4999 House4999"]
    assert calls < 10, "lookup regressed to one regex per Charter body"
