"""LOUD SOUND IS FELT (DESIGN_SOUND_FIELD.md § 14.4, wave B2, 2026-10-20).

A very loud low-frequency sound and a heavy impact are felt as well as
heard -- through the floor or the ground a body stands, sits or lies on: an
explosion, a falling beam, a big drum, machinery a voice cannot be raised
over. The structure carries a blow where the air has lost it, and a body
that cannot hear feels it all the same. Nothing in the engine did: chat 160
turn 11's elevator car struck the concrete at the foot of its shaft (a
`catastrophic` impact) and the only channel anyone had to it was sound.

The class, one test (or more) each:

  1. an impact or an emission past the felt threshold reaches nearby bodies
     as touch through what they stand on, graded by distance and by the
     storeys between (`felt_vibrations`); an ordinary crash, a household
     thing and a voice never are;
  2. a machine at `deafening` is felt by a body at it, steadily;
  3. a body that cannot hear feels it, through a wall the air did not cross;
  4. it is said in the story's language, as touch, and names nothing.
"""

from __future__ import annotations

import json
import time

from agents import composer
from world.spatial import (FELT_DB, FELT_LEVELS, felt_through_ground,
                           felt_vibrations)

PLAN = "layout:smithy"


def _room(name, level, x, y, w, d, *, exposure="enclosed", floor="timber",
          adjacent=()):
    return {"name": name, "level": level, "floor": floor, "exposure": exposure,
            "extent": {"w": w, "d": d},
            "site": {"plan": PLAN, "x": x, "y": y, "elev_m": 3.0 * level},
            "anchors": {}, "adjacent": list(adjacent)}


def _smithy(cells):
    """A smithy on one site plan: a loft over the forge, and the yard the
    forge opens onto -- the yard ninety-six paces long, east of the forge.
    `cells` places each body: {name: (room, (x, y))}."""
    rooms = {
        "loft": _room("The Loft", 1, 0, 0, 6, 4,
                      adjacent=[{"to": "forge", "barrier": "open",
                                 "vertical": "down", "way": "ladder"}]),
        "forge": _room("The Forge", 0, 0, 0, 6, 4, floor="stone",
                       adjacent=[{"to": "loft", "barrier": "open",
                                  "vertical": "up", "way": "ladder"},
                                 {"to": "yard", "barrier": "open_door",
                                  "dir": "e"}]),
        "yard": _room("The Yard", 0, 6, 0, 96, 4, exposure="open", floor="",
                      adjacent=[{"to": "forge", "barrier": "open_door",
                                 "dir": "w"}]),
    }
    return {"rooms": rooms,
            "positions": {k: v[0] for k, v in cells.items()},
            "stations": {k: {"cell": list(v[1])} for k, v in cells.items()},
            "entities": {}, "poses": {}, "orientation": {}, "contained": {}}


def _blow(level, room="loft"):
    return [{"kind": "sound", "room": room, "level": level,
             "detail": "the great anvil smashes down through the boards"}]


def _felt(sc, who, events=None):
    return [row["felt"] for row in felt_vibrations(sc, who, events=events,
                                                   turn_idx=7)]


def test_a_heavy_blow_is_felt_by_distance_and_through_the_floor():
    """A `thunderous` blow in the loft: a body two paces from it, and the
    smith in the forge under the boards, feel the floor shudder; a body
    twenty paces out in the yard, a storey down, feels a tremor through the
    ground; the far end of the yard, a hundred paces off, nothing. An
    ordinary crash -- the impact ladder's `deafening`, a slammed door or a
    dropped tray -- is heard and felt by nobody, and a catastrophe is felt
    across the whole yard."""
    sc = _smithy({"A": ("loft", (5, 2)), "S": ("forge", (3, 2)),
                  "C": ("yard", (17, 2)), "D": ("yard", (95, 2))})
    assert _felt(sc, "A", _blow("thunderous")) == ["shudder"]
    assert _felt(sc, "S", _blow("thunderous")) == ["shudder"]
    assert _felt(sc, "C", _blow("thunderous")) == ["tremor"]
    assert _felt(sc, "D", _blow("thunderous")) == []
    for who in ("A", "S", "C", "D"):
        assert _felt(sc, who, _blow("deafening")) == [], who
    assert _felt(sc, "S", _blow("catastrophic")) == ["jolt"]
    assert _felt(sc, "D", _blow("catastrophic")) == ["shudder"]
    assert felt_through_ground(sc, "yard") and not felt_through_ground(sc, "forge")


def test_a_deafening_machine_is_felt_by_a_body_at_it():
    """A steam hammer running at `deafening`: the smith at it feels a steady
    trembling; four paces off, nothing. A kettle at `loud` -- the loudest a
    household thing gets -- shakes nothing, ever."""
    sc = _smithy({"S": ("forge", (2, 2)), "B": ("forge", (5, 2))})
    sc["positions"]["hammer"] = "forge"
    sc["stations"]["hammer"] = {"cell": [1, 2]}
    sc["entities"]["hammer"] = {"name": "the steam hammer", "kind": "object",
                                "sound_source": "deafening",
                                "state": {"running": True}}
    rows = felt_vibrations(sc, "S", turn_idx=7)
    assert [(r["felt"], r["standing"]) for r in rows] == [("tremor", True)]
    assert felt_vibrations(sc, "B", turn_idx=7) == []
    sc["entities"]["hammer"]["sound_source"] = "loud"
    assert felt_vibrations(sc, "S", turn_idx=7) == []
    view = composer.render_view(composer.felt_percepts(
        felt_vibrations(dict(sc, entities={"hammer": dict(
            sc["entities"]["hammer"], sound_source="deafening")}), "S",
            turn_idx=7)), mode="character")
    assert "steady" in view.text and "floor" in view.text, view.text


def test_it_is_touch_said_in_the_storys_language_and_names_nothing():
    """The percept is touch, directed at the body; it carries the felt word
    and no source, no direction and no detail of the sound; in a Japanese
    story it is said in Japanese, through the ground under the open sky."""
    from language_runtime import language_scope
    sc = _smithy({"C": ("yard", (17, 2))})
    rows = felt_vibrations(sc, "C", events=_blow("catastrophic"), turn_idx=7)
    percepts = composer.felt_percepts(rows, ground=True, beat=7)
    assert [p.channel for p in percepts] == ["touch"]
    assert percepts[0].data["felt"] in FELT_LEVELS
    text = composer.render_view(percepts).text
    assert "ground" in text and "anvil" not in text, text
    with language_scope("ja"):
        ja = composer.felt_percepts(rows, ground=True, beat=7)
    assert "地面" in ja[0].data["clause"], ja[0].data["clause"]
    assert FELT_DB == 100.0


# ---------------------------------------------------------------------------
# A body that cannot hear: the act pass, through a wall
# ---------------------------------------------------------------------------

PLAYER = "Nan Corrie"
CAST = "Silas Penhale"


def _ctx(temp_db):
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from story.character_schema import (default_character_data,
                                        default_persona_data)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source,resource_uid) VALUES(?,?,?,?)",
        (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}", "persona_nan"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Fort", "", time.time(), persona_id))
    sheet = default_character_data(CAST)
    sheet.setdefault("embodiment", {})["senses"] = [
        {"channel": "hearing", "acuity": "deaf"}]
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (CAST, json.dumps(sheet), "{}", time.time(), "char_silas"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", {
        "location": "the fort", "time": "night",
        "rooms": {"magazine": {"name": "the magazine", "size": "small",
                               "adjacent": [{"to": "guardroom",
                                             "barrier": "wall", "dir": "e"}]},
                  "guardroom": {"name": "the guardroom", "size": "small",
                                "adjacent": [{"to": "magazine",
                                              "barrier": "wall", "dir": "w"}]}},
        "positions": {PLAYER: "magazine", CAST: "guardroom"},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", {CAST: [PLAYER], PLAYER: [CAST]})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Fort", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "magazine"
    ctx.director_interpret = {
        "action": {"attempt": "touches the slow match to the powder",
                   "visibility": "overt", "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [{
            "type": "action", "attempt": "touches the slow match to the powder",
            "observable": "touches the slow match to the powder",
            "visibility": "overt", "conceal_from": [], "targets": [],
            "commitment": "asserted", "verb": "touch", "stage": "immediate",
            "event_id": "turn:1:player:0:action",
        }],
        "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [cast[0]["id"]]},
        "state_assertions": {"sensory_events": [{
            "kind": "sound", "room": "magazine", "level": "catastrophic",
            "source": "the powder kegs",
            "detail": "the powder kegs go up with a roar"}]},
    }
    return ctx, cast[0]["id"]


def test_a_body_that_cannot_hear_feels_the_blast_through_the_wall(temp_db):
    """The magazine goes up beyond a stone wall. The guard in the next room
    is deaf, and the wall would have kept most of the roar from him anyway:
    his view carries no word of the sound, and the floor jolting under him."""
    import agents.perception as perception
    ctx, reactor_id = _ctx(temp_db)
    out = perception.perception_act(ctx, nonce="n")
    view = out["views"][str(reactor_id)] or ""
    assert "jolts hard beneath you" in view, view
    assert "roar" not in view, view
