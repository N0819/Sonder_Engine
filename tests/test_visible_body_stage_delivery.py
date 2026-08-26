"""VERIFIER: independent reproduction of the body-fields delivery through the
real `perception_act` stage, plus the firewall negatives.

Different route from the builder's tests, which call
`_composer_standing_percepts` directly and hand it `body_descriptions=`
themselves. This drives the whole stage on a real database, so the wiring from
`_composer_act` -> `_body_descriptions` -> `visible_body_text` is exercised.
"""

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData

PLAYER = "Wren"
OBSERVER = "Observer"
SUBJECT = "Subject"

BUILD = "rangy and heavy-shouldered"
FACE = "a broken nose set crooked"
HAIR = "a grey braid pinned up"
EYES = "pale grey"
FACTS = (BUILD, FACE, HAIR, EYES)


def _sheet(name, described=True):
    sheet = default_character_data(name)
    v = sheet["embodiment"]["visible"]
    v["summary"] = "A tall figure in a coat."
    if described:
        v.update({"build": BUILD, "face": FACE, "hair": HAIR, "eyes": EYES})
    return sheet


def _ctx(temp_db, *, scene_over=None, known=None, subject_room="hall"):
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("V", "", time.time(), persona_id))
    char_ids = {}
    for i, name in enumerate((OBSERVER, SUBJECT)):
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(_sheet(name, name == SUBJECT)), "{}",
             time.time(), f"char_{i}"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, cid, "active", "{}"))
        char_ids[name] = cid

    scene = {
        "location": "the hall", "time": "night",
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.",
                           "adjacent": [{"to": "annex", "barrier": "door"}]},
                  "annex": {"name": "Annex", "desc": "An annex.",
                            "adjacent": [{"to": "hall", "barrier": "door"}]}},
        "positions": {PLAYER: "hall", OBSERVER: "hall", SUBJECT: subject_room},
        "entities": {}, "attire": {}, "overlays": {},
    }
    scene.update(scene_over or {})
    temp_db.wset(chat_id, "scene", scene)
    temp_db.wset(chat_id, "known", known if known is not None else {
        OBSERVER: [PLAYER, SUBJECT], SUBJECT: [PLAYER, OBSERVER]})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="V", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "hall"
    ctx.director_interpret = {
        "action": {"attempt": "crosses to the window", "visibility": "overt",
                   "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [{
            "type": "action", "attempt": "crosses to the window",
            "observable": "crosses the hall toward the window",
            "visibility": "overt", "conceal_from": [], "targets": [],
            "commitment": "asserted", "verb": "cross", "stage": "immediate",
            "event_id": "turn:1:player:0:action"}],
        "speech": None, "speech_volume": "normal",
        "flow": {"reactors": list(char_ids.values())},
    }
    return ctx, char_ids, chat_id


def _view(ctx, char_ids, who=OBSERVER):
    import agents.perception as perception
    return perception.perception_act(ctx, nonce="n")["views"][
        str(char_ids[who])] or ""


def _has(view):
    return tuple(f for f in FACTS if f in view)


def _condition(temp_db, chat_id, cid, kind, payload):
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,payload,active) VALUES(?,?,?,?,?,?,?)",
        (cid, chat_id, SUBJECT, kind, time.time(), json.dumps(payload), 1))


# --- the central claim, through the whole stage ----------------------------

def test_copresent_full_sight_receives_the_body(temp_db):
    ctx, ids, _ = _ctx(temp_db)
    assert _has(_view(ctx, ids)) == FACTS


def test_covered_region_withholds_located_keeps_build(temp_db):
    ctx, ids, _ = _ctx(temp_db, scene_over={"attire": {SUBJECT: {"regions": {
        "head": {"garments": [{"name": "a covering", "state": "worn"}]}}}}})
    assert _has(_view(ctx, ids)) == (BUILD,)


def test_uncovering_delivers_it_again(temp_db):
    ctx, ids, _ = _ctx(temp_db, scene_over={"attire": {SUBJECT: {"regions": {
        "head": {"garments": [{"name": "a covering", "state": "removed"}]}}}}})
    assert _has(_view(ctx, ids)) == FACTS


# --- observers with no channel ---------------------------------------------

def test_another_room_receives_none(temp_db):
    ctx, ids, _ = _ctx(temp_db, subject_room="annex")
    assert _has(_view(ctx, ids)) == ()


def test_darkness_receives_none(temp_db):
    ctx, ids, _ = _ctx(temp_db, scene_over={"rooms": {"hall": {
        "name": "Hall", "desc": "A hall.", "light": "dark", "adjacent": []}}})
    assert _has(_view(ctx, ids)) == ()


def test_dim_light_receives_none(temp_db):
    """Presence still arrives; the body does not."""
    ctx, ids, _ = _ctx(temp_db, scene_over={"rooms": {"hall": {
        "name": "Hall", "desc": "A hall.", "light": "dim", "adjacent": []}}})
    view = _view(ctx, ids)
    assert "Subject is close by" in view
    assert _has(view) == ()


def test_shut_inside_something_receives_none(temp_db):
    ctx, ids, _ = _ctx(temp_db, scene_over={
        "entities": {"a crate": {"name": "a crate",
                                 "description": "a sealed crate",
                                 "room": "hall"}},
        "contained": {SUBJECT: {"in": "a crate", "mode": "shut"}}})
    assert _has(_view(ctx, ids)) == ()


def test_rear_arc_receives_none(temp_db):
    from world.spatial import entity_arc
    from story.scene import get_scene
    ctx, ids, chat_id = _ctx(temp_db, scene_over={
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "size": "large",
                           "anchors": {"front": {"desc": "a window", "dir": "n"},
                                       "back": {"desc": "a stair", "dir": "s"}},
                           "adjacent": []}},
        "orientation": {OBSERVER: {"facing": "n"}},
        "stations": {OBSERVER: {"at": "front"}, SUBJECT: {"at": "back"}}})
    assert entity_arc(get_scene(chat_id, ctx.chat), OBSERVER, SUBJECT) == "rear"
    assert _has(_view(ctx, ids)) == ()


def test_a_disguised_body_delivers_none_of_its_card(temp_db):
    ctx, ids, chat_id = _ctx(temp_db)
    _condition(temp_db, chat_id, "d1", "physical_disguise", {
        "subject_id": SUBJECT, "description": "a stooped porter",
        "presented_appearance": "a stooped porter in sacking",
        "concealed_terms": [], "conceals_identity": True})
    view = _view(ctx, ids)
    assert "a stooped porter in sacking" in view
    assert _has(view) == ()


def test_a_transformed_body_delivers_none_of_its_card(temp_db):
    ctx, ids, chat_id = _ctx(temp_db)
    _condition(temp_db, chat_id, "t1", "physical_transformation", {
        "subject_id": SUBJECT, "appearance": "a grey wolf"})
    view = _view(ctx, ids)
    assert "a grey wolf" in view
    assert _has(view) == ()


def test_a_stranger_at_full_sight_still_gets_a_summary_only_label(temp_db):
    """Seeing is the channel, so an unintroduced observer legitimately gets
    the body. What must not move is the LABEL, which is handed out without
    asking what the observer can see."""
    ctx, ids, _ = _ctx(temp_db, known={OBSERVER: [], SUBJECT: []})
    view = _view(ctx, ids)
    assert _has(view) == FACTS
    assert "The tall figure in a coat is close by" in view
    for fact in FACTS:
        assert f"{fact} is close by" not in view


def test_a_blind_observer_receives_none(temp_db):
    """The senses gate (G4) grades sight below full for an authored-blind
    card, so the appearance percept -- and the body with it -- never forms."""
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("V", "", time.time(), persona_id))
    ids = {}
    for i, name in enumerate((OBSERVER, SUBJECT)):
        sheet = _sheet(name, name == SUBJECT)
        if name == OBSERVER:
            sheet["embodiment"]["senses"] = [
                {"channel": "sight", "acuity": "absent"}]
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(), f"char_{i}"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, cid, "active", "{}"))
        ids[name] = cid
    temp_db.wset(chat_id, "scene", {
        "location": "the hall", "time": "night",
        "rooms": {"hall": {"name": "Hall", "desc": "A hall.", "adjacent": []}},
        "positions": {PLAYER: "hall", OBSERVER: "hall", SUBJECT: "hall"},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", {OBSERVER: [PLAYER, SUBJECT],
                                    SUBJECT: [PLAYER, OBSERVER]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="V", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "hall"
    ctx.director_interpret = {
        "action": {"attempt": "crosses to the window", "visibility": "overt",
                   "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [{
            "type": "action", "attempt": "crosses to the window",
            "observable": "crosses the hall toward the window",
            "visibility": "overt", "conceal_from": [], "targets": [],
            "commitment": "asserted", "verb": "cross", "stage": "immediate",
            "event_id": "turn:1:player:0:action"}],
        "speech": None, "speech_volume": "normal",
        "flow": {"reactors": list(ids.values())}}
    assert _has(_view(ctx, ids)) == ()


def test_an_unconscious_observer_receives_none(temp_db):
    ctx, ids, chat_id = _ctx(temp_db)
    _condition_for(temp_db, chat_id, "a1", OBSERVER, "awareness",
                   {"subject_id": OBSERVER, "level": "unconscious",
                    "cause": "a blow"})
    assert _has(_view(ctx, ids)) == ()


def _condition_for(temp_db, chat_id, cid, subject, kind, payload):
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,payload,active) VALUES(?,?,?,?,?,?,?)",
        (cid, chat_id, subject, kind, time.time(), json.dumps(payload), 1))


# --- THE EXPANSION THIS FOUND ----------------------------------------------

def test_case_variant_ledger_key_still_conceals(temp_db):
    """FAILS on the change as written.

    The covering is recorded under a case-variant spelling of the body's name
    -- the shape `agents.common.observer_body_regions` explicitly tolerates
    with a casefold fallback, and the shape
    `persist.commit_attire._heal_attire_identity_keys` exists to heal. But
    `perception_act` never heals, and `scene.visible_body_text` does a bare
    `.get(name)`, so the gate finds no garment and delivers a face that a
    covering conceals."""
    ctx, ids, _ = _ctx(temp_db, scene_over={"attire": {SUBJECT.lower(): {
        "regions": {"head": {
            "garments": [{"name": "a covering", "state": "worn"}]}}}}})
    assert _has(_view(ctx, ids)) == (BUILD,)
