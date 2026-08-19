"""An actor sealed inside something does not get an outside shot of themselves.

`observable` is the intent-free surface of an act as seen FROM OUTSIDE, and the
actor normally receives it in their own view -- rewritten to second person by
`_self_second_person` -- because people can see themselves doing things.

Sealed inside something that stops being true. The surface then describes the
outside of the enclosure, how its wall moves with them, and there is no channel
from inside to that.

Live, chat 60 t18. The declared observable was

    "A tiny lump writhes and squirms beneath the fabric, small limbs pushing
     at the cloth, the shirt shifting and bulging as the lump tries to find a
     way out."

and the actor's own view came back "The lump you make writhes and bulges under
the fabric" -- in darkness, under cloth, two clauses after her own narration
said she could see nothing. Reported from play as: she should not be able to
see the shape she makes.

The rule is keyed on being ENCLOSED, deliberately, and not on darkness or a
failed sight check. Being unable to see in the dark does not stop you knowing
what your own body is doing -- proprioception is not sight -- and suppressing
an actor's own conduct every time the lights went out would be a worse error
than the one this fixes. What an enclosure removes is specifically the outside
view of yourself.

Everyone else's view is untouched: the surface is exactly what they can see,
and that is what it is for.
"""

from __future__ import annotations

from agents.perception import _self_cannot_see_own_surface

ACTOR = "Wren"
HOST = "Vessel"
HOST_ID = "vessel_entity"


def _scene(contained=True):
    sc = {
        "rooms": {"hall": {"name": "Hall", "adjacent": []}},
        "positions": {ACTOR: "hall", HOST: "hall", "Onlooker": "hall"},
        "entities": {HOST_ID: {"name": HOST, "kind": "person", "aliases": []}},
        "attire": {HOST: {}, ACTOR: {}},
        "scales": {ACTOR: 0.05},
        "contained": {},
    }
    if contained:
        sc["contained"][ACTOR] = {"in": HOST_ID, "mode": "inside"}
    return sc


def _p(name):
    return {"id": "1", "name": name}


class TestTheEnclosedActor:
    def test_their_own_surface_is_withheld(self):
        assert _self_cannot_see_own_surface(_scene(), _p(ACTOR), ACTOR) is True

    def test_it_holds_when_the_actor_is_named_by_entity_id(self):
        """The actor arrives under whichever spelling the beat used."""
        sc = _scene()
        sc["entities"]["wren_entity"] = {"name": ACTOR, "kind": "person"}
        assert _self_cannot_see_own_surface(sc, _p(ACTOR), "wren_entity") is True

    def test_an_open_carry_is_not_an_enclosure(self):
        """Being held in view is not being shut inside anything, and someone
        carried in the open can see themselves perfectly well."""
        sc = _scene()
        sc["contained"][ACTOR] = {"in": HOST_ID, "mode": "held"}
        assert _self_cannot_see_own_surface(sc, _p(ACTOR), ACTOR) is False


class TestEveryoneElseIsUntouched:
    def test_an_onlooker_still_receives_the_surface(self):
        """The surface is exactly what an observer can see, which is what it
        is for. Withholding it from them would be a different bug."""
        assert _self_cannot_see_own_surface(
            _scene(), _p("Onlooker"), ACTOR) is False

    def test_the_host_still_receives_it(self):
        assert _self_cannot_see_own_surface(_scene(), _p(HOST), ACTOR) is False

    def test_an_unenclosed_actor_still_sees_themselves(self):
        assert _self_cannot_see_own_surface(
            _scene(contained=False), _p(ACTOR), ACTOR) is False


class TestItNeverRaises:
    def test_no_scene(self):
        assert _self_cannot_see_own_surface(None, _p(ACTOR), ACTOR) is False

    def test_no_perceiver(self):
        assert _self_cannot_see_own_surface(_scene(), None, ACTOR) is False

    def test_a_nameless_perceiver(self):
        assert _self_cannot_see_own_surface(_scene(), {"id": "1"}, ACTOR) is False


# --- what actually enforces the property now --------------------------------
#
# The two tests that used to stand here read `inspect.getsource` and asserted
# statement ORDER inside `_inject_onset_sequence` -- one of them saying so in
# its own docstring: "or it is a well-tested function nothing calls". That is
# exactly what happened. `_inject_onset_sequence` has no production caller,
# and neither does `_self_cannot_see_own_surface` outside it, so the wiring
# guard was asserting the internal layout of dead code, and passing.
#
# The property is not lost. The composer path enforces it by a stronger and
# blunter mechanism: an actor never receives their OWN act surface in their
# own view at all, enclosed or not, because `_composer_act` builds no
# perceiver for the acting player and `_composer_outcome`'s act loop skips
# the observer's own act. Nothing said so anywhere, which is how a guard came
# to be left pointing at the mechanism that was retired.

import json
import time

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


PLAYER = "Hinami"
SURFACE = "lifts the lantern high"
LANTERN = "a brass lantern"


def _outcome_ctx(temp_db, *, light=None, entity_state=None):
    """One cast actor who acts, one player watching."""
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Own surface", "", time.time(), persona_id))
    sheet = default_character_data(ACTOR)
    sheet.setdefault("embodiment", {}).setdefault("visible", {})["summary"] = (
        "A small woman in a grey coat.")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (ACTOR, json.dumps(sheet), "{}", time.time(), "wren_card"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))

    room = {"name": "Hall", "desc": "A hall.", "adjacent": []}
    if light:
        room["light"] = light
    entities = {}
    if entity_state is not None:
        entities["wren_1"] = {"name": ACTOR, "kind": "person",
                              "state": dict(entity_state)}
    temp_db.wset(chat_id, "scene", {
        "location": "the hall", "time": "night",
        "rooms": {"hall": room},
        "positions": {PLAYER: "hall", ACTOR: "hall"},
        "entities": entities, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", {ACTOR: [PLAYER]})

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Own surface", persona_id=persona_id,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1, player_input="",
                      created=time.time()),
        cast=cast, input="")
    ctx["_player_room"] = "hall"
    ctx.director_interpret = {
        "action": {"attempt": "waits", "visibility": "overt",
                   "conceal_from": [], "targets": [],
                   "commitment": "asserted"},
        "sequence": [], "speech": None, "speech_volume": "normal",
        "flow": {"reactors": [char_id]},
    }
    ctx.character_results[char_id] = {
        "speech": "", "action": "lifts the lantern",
        "sequence": [{"type": "action", "attempt": "lifts the lantern",
                      "observable": SURFACE, "visibility": "overt",
                      "conceal_from": [], "targets": [],
                      "commitment": "asserted"}]}
    ctx.director_resolve = {
        "resolved_event": "The hall stands quiet.", "state_diff": {},
        "dialogue_log": [], "dialogue_order": []}
    return ctx, char_id


def _views(ctx):
    import agents.perception as perception
    return perception.perception_outcome(ctx, nonce="n")["views"]


def test_an_actor_never_receives_their_own_act_surface(temp_db):
    """The live floor under this file's whole premise.

    `observable` is the act as seen FROM OUTSIDE. On the composer path the
    actor is not among the observers of their own act, so the outside shot of
    themselves cannot be delivered whatever they are sealed inside."""
    ctx, char_id = _outcome_ctx(temp_db)
    views = _views(ctx)

    assert SURFACE not in (views[str(char_id)] or ""), (
        "an actor was handed the outside view of their own act: "
        f"{views[str(char_id)]!r}")
    assert SURFACE in (views.get("player") or ""), (
        "the subtraction reached past the actor and cost a watching mind an "
        f"act it plainly saw: {views.get('player')!r}")


def test_proprioception_is_not_sight(temp_db):
    """The rule this file names, on the path that now carries it.

    Being unable to see does not stop a body knowing what it is doing.
    `body_state_percept` rides the interoception channel, so a pitch-dark
    room takes the actor's sight of everyone else and leaves their own held
    items exactly where they are."""
    ctx, char_id = _outcome_ctx(
        temp_db, light="dark", entity_state={"held_items": [LANTERN]})
    view = _views(ctx)[str(char_id)] or ""

    assert LANTERN in view, (
        f"darkness took a character's knowledge of their own hands: {view!r}")
    assert PLAYER not in view, (
        f"a pitch-dark room did not take sight of another body: {view!r}")
