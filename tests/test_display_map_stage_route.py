"""INDEPENDENT REPRODUCTION -- pipeline route, not a direct composer call.

Everything here goes through `agents.perception.perception_act`: a real
PipelineContext, a real chat row, a real scene blob, and the VIEW that the
stage hands a character agent. Nothing calls `observer_display_map`,
`presence_percepts` or `_co_present_company` directly.
"""

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData

PLAYER = "Pl"
OBS = "Obs"
SUBJ = "Subj"

SUBJ_LOOKS = "A lean middle-aged man in a wet oilskin coat."
OBS_LOOKS = "A stocky woman with cropped grey hair."

APPEARANCE_WORDS = ("lean", "middle", "oilskin", "wet", "coat")


def _sheet(name, looks, sight_acuity=None):
    sheet = default_character_data(name)
    sheet.setdefault("embodiment", {}).setdefault("visible", {})["summary"] = looks
    if sight_acuity:
        sheet["embodiment"]["senses"] = [
            {"channel": "vision", "acuity": sight_acuity, "range": "ordinary",
             "notes": ""},
            {"channel": "hearing", "acuity": "ordinary", "range": "ordinary",
             "notes": ""},
        ]
    return sheet


def _ctx(temp_db, *, light="dim", known=None, obs_sight=None, rooms=None,
         positions=None):
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Split", "", time.time(), persona_id))
    char_ids = {}
    for i, (name, looks) in enumerate(((OBS, OBS_LOOKS), (SUBJ, SUBJ_LOOKS))):
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(_sheet(name, looks,
                                     obs_sight if name == OBS else None)),
             "{}", time.time(), f"c_{i}"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
        char_ids[name] = char_id

    room = {"name": "Hall", "desc": "A hall.", "adjacent": []}
    if light:
        room["light"] = light
    scene_rooms = rooms or {"hall": room}
    temp_db.wset(chat_id, "scene", {
        "location": "the hall", "time": "night",
        "rooms": scene_rooms,
        "positions": positions or {PLAYER: "hall", OBS: "hall", SUBJ: "hall"},
        "poses": {SUBJ: {"posture": "sitting"}},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", known if known is not None else {
        OBS: [PLAYER], SUBJ: [PLAYER, OBS]})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Split", persona_id=persona_id,
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
            "event_id": "turn:1:player:0:action",
        }],
        "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [char_ids[OBS], char_ids[SUBJ]]},
    }
    return ctx, char_ids


def _view(temp_db, **kw):
    import agents.perception as perception
    ctx, char_ids = _ctx(temp_db, **kw)
    out = perception.perception_act(ctx, nonce="n")
    return out["views"][str(char_ids[OBS])] or "", ctx, char_ids


def _leaked(text):
    low = text.casefold()
    return [w for w in APPEARANCE_WORDS if w in low]


def test_dim_room_view_names_the_stranger_once_and_without_appearance(temp_db):
    """THE CENTRAL CLAIM, through the stage. A stranger at `shapes` is a
    silhouette in the presence line AND in the pose line."""
    view, _ctx_, _ids = _view(temp_db)
    assert "sitting" in view.casefold(), view      # the pose line is present
    assert not _leaked(view), (
        f"appearance facts {_leaked(view)} reached an observer holding a "
        f"silhouette:\n{view}")
    assert "an indistinct figure" in view.casefold(), view
    # ONE label for one body: no second name for the same person anywhere.
    assert "subj" not in view.casefold(), view


def test_full_sight_still_describes(temp_db):
    """Not over-subtracting: a lit room still earns the descriptor."""
    view, _c, _i = _view(temp_db, light="bright")
    assert _leaked(view), view
    assert "an indistinct figure" not in view.casefold(), view


def test_a_blind_observer_gets_no_figure_and_no_appearance(temp_db):
    """FIREWALL. An observer with no visual channel at all cannot receive a
    silhouette, let alone a build and an age."""
    view, _c, _i = _view(temp_db, light="bright", obs_sight="blind")
    assert not _leaked(view), view
    assert "indistinct figure" not in view.casefold(), view
    assert "sitting" not in view.casefold(), view


def test_another_room_delivers_nothing(temp_db):
    """FIREWALL. A body behind a wall reaches no channel."""
    rooms = {"hall": {"name": "Hall", "desc": "", "adjacent": []},
             "cell": {"name": "Cell", "desc": "", "adjacent": []}}
    view, _c, _i = _view(
        temp_db, light="bright", rooms=rooms,
        positions={PLAYER: "hall", OBS: "hall", SUBJ: "cell"})
    assert not _leaked(view), view
    assert "indistinct figure" not in view.casefold(), view


def test_a_dulled_eye_takes_the_descriptor_with_it(temp_db):
    """FIREWALL, one card down. The room is bright; the observer's own eyes
    are not. The sense card grades sight after the room does."""
    view, ctx, ids = _view(temp_db, light="bright", obs_sight="dulled")
    assert not _leaked(view), view
    assert "an indistinct figure" in view.casefold(), view


def test_a_hand_in_the_dark_names_no_build_and_no_age(temp_db):
    """FIREWALL, the channel that is not sight. Two bodies touching in a
    pitch-dark room: the touch percept must name the other party by
    something touch can support, never by a build and an age that only an
    eye delivers."""
    import agents.perception as perception
    ctx, ids = _ctx(temp_db, light="dark")
    sc = temp_db.wget(ctx.chat["id"], "scene", {})
    sc["contacts"] = [{"actor": SUBJ, "actor_part": "palm",
                       "target": OBS, "target_part": "shoulder",
                       "manner": "rest"}]
    temp_db.wset(ctx.chat["id"], "scene", sc)
    view = perception.perception_act(ctx, nonce="n")["views"][
        str(ids[OBS])] or ""
    assert "shoulder" in view.casefold(), view      # the touch arrived
    assert not _leaked(view), view
    assert "subj" not in view.casefold(), view


# --- THE DEDUPLICATION, COVERED ---------------------------------------------
#
# `_co_present_company` used to RESTATE observer_display_map's five naming
# rules. Both copies now gate on sight, so they agree, and reverting the
# refactor leaves every behavioural test green -- which is exactly what makes
# a second copy of a naming rule dangerous: nothing fails until it drifts.
#
# This asserts the READ rather than the result. Change what the display map
# returns and the company field must follow; a restated copy cannot.

def test_the_company_field_reads_the_display_map_it_does_not_restate_it(
        monkeypatch):
    """Fails if `_co_present_company` ever goes back to computing labels."""
    from agents import perception, composer

    scene = {
        "rooms": {"hall": {"name": "Hall", "light": "normal", "adjacent": []}},
        "positions": {"OBS": "hall", "SUBJ": "hall"},
        "stations": {"OBS": {"at": None, "near": ["SUBJ"]},
                     "SUBJ": {"at": None, "near": ["OBS"]}},
        "poses": {}, "contacts": {}, "contained": {},
    }
    bodies = [{"name": "SUBJ", "appearance": "A tall figure in a coat."}]

    sentinel = "the sentinel this test alone supplies"
    monkeypatch.setattr(
        composer, "observer_display_map",
        lambda *a, **k: {"SUBJ": sentinel})

    prox, _behind = perception._co_present_company(
        scene, "OBS", bodies, {"OBS": []})

    assert sentinel in prox, (
        "the company field did not take its label from observer_display_map, "
        f"so the naming rule is restated somewhere: {prox}")
