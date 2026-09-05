"""An overt act in a lit room reaches everybody in it -- and the one branch
that takes it away, named.

Live: `docs/experiments/PLAY_2026_09_05C_multitude.md` § PM5, "The Hearing at
Vaunt's Yard", turn 8, 2026-09-05. Ottoline hauled the yard doors open in
front of five people in one lit room. Tobin Slake's and Devereux Hallam's act
views carried

    "Ottoline Sarr takes hold of the iron ring with both hands, levers her
     shoulder beneath the bar, and heaves the right-hand leaf of the heavy
     doors open."

Maren Vaunt's, Ilsabet Roon's and Corin Ashe's carried only her speech, and
Maren's also omitted Ottoline from its presence list entirely while ending
with her line and reading "The tall yard doors is shut." She then declared
"Unbolt the doors." The report could not isolate the branch and said so; the
three suspects it ruled out were `flow.reactors` (perception widened past it
long ago), the standing dedupe (`composer_ledger.standing` held no `act:`
keys) and station (Maren, Hallam and Tobin were all `at: factors_table`).

The branch is `world.spatial.entity_arc` -- the within-room blind spot. It is
consulted three times per observer, in `composer.presence_percepts`, in
`composer.act_percept` and in `_composer_standing_percepts`, and each one
DROPS rather than degrades. The split follows FACING, which is why it did not
follow station: everyone at the table was at the same anchor and only some of
them were turned toward the doors.

Two tests, and the second is a characterisation test on purpose. What the
engine does today is pinned so a change to it is deliberate; what
`entity_arc` PROMISES ("no new visual detail ... though sound still carries")
is not what happens, because an act reaches an observer on the sight channel
alone and a sound that HAPPENS has no channel at all (`docs/UNBUILT.md`
§ 1.117). Fixing that is a composer change and is written up with this run.
"""

from __future__ import annotations

import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data

HALL = "hall"
FACTORS = ["Maren Vaunt", "Ilsabet Roon", "Corin Ashe", "Tobin Slake",
           "Devereux Hallam"]
OBSERVABLE = ("takes hold of the iron ring with both hands and heaves the "
              "right-hand leaf of the heavy doors open")


def _scene(*, stations=None, orientation=None):
    scene = {
        "location": "Vaunt's Yard", "time": "day",
        "rooms": {HALL: {
            "name": "the Counting Hall", "light": "bright",
            "notes": "Tallies lie in rows on the table.",
            "anchors": {
                "factors_table": {"desc": "the factors' table", "dir": "n"},
                "yard_doors": {"desc": "the tall yard doors", "dir": "s"},
            },
            "adjacent": [],
        }},
        "positions": {name: HALL for name in ["The Stranger", *FACTORS]},
        "entities": {}, "attire": {}, "overlays": {},
    }
    if stations:
        scene["stations"] = stations
    if orientation:
        scene["orientation"] = orientation
    return scene


def _ctx(temp_db, scene):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Vaunt's Yard", "", time.time()))
    ids = {}
    for name in FACTORS:
        sheet = default_character_data(name)
        sheet["embodiment"]["visible"]["summary"] = "%s, a factor" % name
        cid = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(sheet), "{}", time.time(),
             "char_" + name.split()[0].lower()))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, cid, "active", "{}"))
        ids[name] = cid
    temp_db.wset(chat_id, "scene", scene)
    everyone = ["The Stranger", *FACTORS]
    temp_db.wset(chat_id, "known", {who: list(everyone) for who in everyone})
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "haul the yard doors open", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Vaunt's Yard", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="haul the yard doors open",
                      created=time.time()),
        cast=cast, input="haul the yard doors open")
    ctx.director_interpret = {
        "sequence": [{"type": "action", "attempt": OBSERVABLE,
                      "observable": OBSERVABLE, "visibility": "overt",
                      "conceal_from": []}],
        "speech": None, "speech_volume": "normal", "action": None,
        "flow": {"reactors": list(ids.values()), "addressed_to": [],
                 "authority_claims": [], "resolution_flags": {},
                 "fiction_frame": {}},
    }
    return ctx, ids


def test_an_overt_act_reaches_every_body_in_the_lit_room(temp_db):
    """PM5's own test, in the shape the report asked for: five bodies in one
    lit room, one declares an overt unconcealed act, and the act surface
    appears in all five other views.

    No facing anywhere, which is the ordinary case -- 'facing' is inferred
    and mostly absent -- so this pins that delivery is not gated on
    `flow.reactors`, on the standing dedupe, or on station.
    """
    from agents.perception import perception_act

    ctx, ids = _ctx(temp_db, _scene())
    views = perception_act(ctx, "n0")["views"]
    for name in FACTORS:
        assert "heaves the right-hand leaf" in views[str(ids[name])], \
            (name, views[str(ids[name])])


def test_the_rear_arc_is_the_branch_that_took_it_away(temp_db):
    """PM5's cause, pinned. Everyone stands at the factors' table (bearing
    north); the actor is at the yard doors (bearing south). The two who face
    south receive the act and the woman herself; the three who face north
    receive neither -- not the act, and not her PRESENCE, though she has
    been in the room with them all along.

    This is a characterisation test: it records what the engine does, and
    it is the evidence for the change written up beside it. `entity_arc`
    promises "no new visual detail ... though sound still carries", and
    both halves are broken here -- a body already in the room is not new
    detail, and nothing carries the sound of an act.
    """
    from agents.perception import perception_act

    ctx, ids = _ctx(temp_db, _scene(
        stations={name: {"at": "factors_table"} for name in FACTORS}
        | {"The Stranger": {"at": "yard_doors"}},
        orientation={"Maren Vaunt": {"facing": "n"},
                     "Ilsabet Roon": {"facing": "n"},
                     "Corin Ashe": {"facing": "n"},
                     "Tobin Slake": {"facing": "s"},
                     "Devereux Hallam": {"facing": "s"}}))
    views = perception_act(ctx, "n0")["views"]

    for facing_her in ("Tobin Slake", "Devereux Hallam"):
        view = views[str(ids[facing_her])]
        assert "heaves the right-hand leaf" in view, (facing_her, view)
        assert "The Stranger is across the room" in view, (facing_her, view)

    for turned_away in ("Maren Vaunt", "Ilsabet Roon", "Corin Ashe"):
        view = views[str(ids[turned_away])]
        assert "heaves the right-hand leaf" not in view, (turned_away, view)
        # The half that produced the run's most visible nonsense: the woman
        # heaving the doors is not in the room at all, so the chair ordered
        # them unbolted.
        assert "The Stranger" not in view, (turned_away, view)


def test_a_body_within_reach_is_never_a_blind_spot(temp_db):
    """The exemption `entity_arc` already makes, pinned so the change above
    is measured against it: somebody at arm's length is 'front' whatever
    the facing, so the arc can never delete the person beside you."""
    from agents.perception import perception_act

    ctx, ids = _ctx(temp_db, _scene(
        stations={name: {"at": "factors_table"} for name in FACTORS}
        | {"The Stranger": {"at": "factors_table"}},
        orientation={name: {"facing": "n"} for name in FACTORS}))
    views = perception_act(ctx, "n0")["views"]
    for name in FACTORS:
        assert "heaves the right-hand leaf" in views[str(ids[name])], \
            (name, views[str(ids[name])])
