"""A co-present body that has not acted yet was absent from pass-1 payloads.

Reported three times from chat 63: "Tamamo and the Doctor cannot see each
other in perception pass 1." Two recognised acquaintances standing in the
same room did not appear in each other's action-onset views, because the
information was never in the payload the view was written from.

The mechanism: pass 1 (`perception_act`) runs BEFORE the interaction loop,
so `ctx.character_results` is empty and no cast member qualifies as a
source the way pass 2's source assembly admits them ("did their character
step produce something"). The only channels that could carry a co-present
body into a pass-1 payload were the acting player (`declared_act` and the
`*_to_actor` fields), the observer's single `orientation.focus` slot, and
the contact/scale/containment ledgers in the scene projection. A bystander
who had simply been standing there all along was in none of them — so
presence rode a one-slot channel (focus) that was never meant to carry it,
which is why the failure looked intermittent and one-directional (Tamamo,
focused on the Doctor, sometimes saw him; he, focused on a doorway, never
saw her).

Pass 2 (`perception_outcome`) computes proximity/side/rear for every acting
source and delivers it, so the fix belongs to pass 1 alone; a test below
pins pass 2's existing convention so the change cannot drift into it.

The roster is also a brand-new channel that hands a mind other bodies, so
every firewall rule that governs a name applies to it INPUT-side (the
pass-1 output scrub only floors the PLAYER's identity, not a fellow cast
member's): an unrecognised body arrives as its unknown-actor descriptor,
never its name; a body seen only as `shapes` is a shape, not a face or an
appearance; a disguised body is its outward form; a concealed or unlit body
does not arrive at all.
"""

import json
import re
import time

import pytest

from story.character_schema import default_character_data, default_persona_data
from core.pipeline_context import ChatData, PipelineContext, TurnData


PLAYER = "Hinami"
DOCTOR = "The Doctor"
TAMAMO = "Tamamo"

TAMAMO_LOOKS = "A fox-eared young woman in shrine-maiden robes."
DOCTOR_LOOKS = "A lean, energetic man in a battered frock coat."


def _sheet(name, looks):
    sheet = default_character_data(name)
    sheet.setdefault("embodiment", {}).setdefault("visible", {})["summary"] = looks
    return sheet


def _bystander_ctx(temp_db, *, light=None, known=None):
    """Player plus two cast members standing in one room; the player acts."""
    persona = default_persona_data(PLAYER)
    persona_id = temp_db.qi(
        "INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
        (PLAYER, json.dumps(persona), "{}"))
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
        ("Presence", "", time.time(), persona_id))
    char_ids = {}
    for i, (name, looks) in enumerate(
            ((DOCTOR, DOCTOR_LOOKS), (TAMAMO, TAMAMO_LOOKS))):
        char_id = temp_db.qi(
            "INSERT INTO characters(name,sheet,source,created,resource_uid) "
            "VALUES(?,?,?,?,?)",
            (name, json.dumps(_sheet(name, looks)), "{}", time.time(),
             f"char_{i}"))
        temp_db.qi(
            "INSERT INTO chat_chars(chat_id,char_id,status,state) "
            "VALUES(?,?,?,?)", (chat_id, char_id, "active", "{}"))
        char_ids[name] = char_id

    room = {"name": "Hall", "desc": "A hall.", "adjacent": []}
    if light:
        room["light"] = light
    temp_db.wset(chat_id, "scene", {
        "location": "the hall", "time": "night",
        "rooms": {"hall": room},
        "positions": {PLAYER: "hall", DOCTOR: "hall", TAMAMO: "hall"},
        "entities": {}, "attire": {}, "overlays": {}})
    temp_db.wset(chat_id, "known", known if known is not None else {
        DOCTOR: [PLAYER, TAMAMO],
        TAMAMO: [PLAYER, DOCTOR],
    })

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Presence", persona_id=persona_id,
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
        "flow": {"reactors": [char_ids[DOCTOR], char_ids[TAMAMO]]},
    }
    return ctx, char_ids


def _capture_payloads(monkeypatch, run):
    """Run a perception pass and return each observer's composed VIEW.

    This file used to capture the payload each observer's model call was
    built from, because with a model standing between the engine and the
    reader, the payload was as close to "what the engine delivers" as a
    test could get. Perception has no model now — the view IS the delivery
    — so every assertion below moved onto it. That is closer to the thing
    that matters, not further: a payload could carry a fact the model then
    declined to use, and a view cannot.

    What genuinely got weaker, said out loud: the payload distinguished
    "delivered, marked sight:shapes" from "delivered in full" as a field.
    Prose says the same thing with a descriptor, so the dim-light test
    below reads the descriptor instead.
    """
    import agents.perception as perception
    return run(perception)["views"]


def _pass1(ctx, monkeypatch):
    return _capture_payloads(
        monkeypatch, lambda p: p.perception_act(ctx, nonce="n"))


# --- the defect -------------------------------------------------------------

def test_pass_one_delivers_a_co_present_recognised_body(temp_db, monkeypatch):
    """The reported bug: recognised, co-present, well-lit — and absent.

    Neither observer's pass-1 payload carried any trace of the other, so
    the model could not mention what it was never told. The roster arrives
    through the fields the perception prompt already describes for
    co-located people (proximity_to_sources / behind_sources), as PRESENCE
    — a tier and a side, stative — never as an act."""
    ctx, char_ids = _bystander_ctx(temp_db)
    views = _pass1(ctx, monkeypatch)

    for observer, other in ((DOCTOR, TAMAMO), (TAMAMO, DOCTOR)):
        view = views[str(char_ids[observer])] or ""
        assert other in view, (
            f"{observer}'s pass-1 view does not deliver co-present "
            f"{other}: {view!r}")
        assert f"{other} is close by" in view


def test_pass_one_bystander_is_presence_not_an_actor(temp_db, monkeypatch):
    """A bystander must not be handed over as someone DOING something.

    The engine already learned this on contacts: a bare relation record read
    as an event and was narrated as one. The roster therefore carries only
    stative placement data — nothing act-shaped for the model to lift."""
    ctx, char_ids = _bystander_ctx(temp_db)
    view = _pass1(ctx, monkeypatch)[str(char_ids[DOCTOR])] or ""

    # Every sentence naming her is stative placement. Nothing act-shaped
    # exists for a reader -- or the character agent reading this view -- to
    # mistake for something she just did.
    naming = [s for s in view.split(". ") if TAMAMO in s]
    assert naming
    for sentence in naming:
        assert re.search(
            rf"{TAMAMO} is (close by|within arm's reach|across the room)",
            sentence), sentence


# --- pass 2 is not this bug and must not absorb the fix ---------------------

def test_pass_two_source_delivery_is_unchanged(temp_db, monkeypatch):
    """Pass 2 already delivers every acting body; the fix is pass 1's alone.

    Pins the outcome pass's existing convention — acting cast reach every
    observer's sources/proximity under their canonical names — so the pass-1
    roster cannot drift into a pass that was never broken."""
    ctx, char_ids = _bystander_ctx(temp_db)
    ctx.director_resolve = {
        "resolved_event": "The hall stands quiet.", "state_diff": {},
        "dialogue_log": [], "dialogue_order": []}
    for name in (DOCTOR, TAMAMO):
        ctx.character_results[char_ids[name]] = {
            "speech": "Hm.", "action": "", "sequence": []}

    views = _capture_payloads(
        monkeypatch, lambda p: p.perception_outcome(ctx, nonce="n"))

    for observer, other in ((DOCTOR, TAMAMO), (TAMAMO, DOCTOR)):
        view = views[str(char_ids[observer])] or ""
        assert f"{other} is close by" in view


# --- the roster is a new channel; the firewall applies input-side -----------

def test_unrecognised_body_arrives_as_descriptor_never_name(
        temp_db, monkeypatch):
    """An observer who has not met someone must not receive their name.

    The pass-1 output scrub floors only the PLAYER's identity for
    non-recognising observers; a fellow cast member's name delivered
    input-side would ride straight through it. The roster therefore applies
    the identity floor before the payload is built: the body arrives as its
    appearance-derived unknown-actor descriptor."""
    ctx, char_ids = _bystander_ctx(temp_db, known={
        DOCTOR: [PLAYER],           # has never met Tamamo
        TAMAMO: [PLAYER, DOCTOR],
    })
    view = _pass1(ctx, monkeypatch)[str(char_ids[DOCTOR])] or ""

    assert "tamamo" not in view.casefold()
    assert "fox" in view.casefold()       # described by what is visibly there


def test_a_body_in_the_dark_does_not_arrive_at_all(temp_db, monkeypatch):
    """The roster must not out-see the light.

    `visual_level_between` already answers "none" for an unlit body; a
    presence roster that bypassed it would tell an observer who is standing
    in a pitch-dark room with them — sight the room does not grant."""
    ctx, char_ids = _bystander_ctx(temp_db, light="dark")
    view = _pass1(ctx, monkeypatch)[str(char_ids[DOCTOR])] or ""

    # The payload version of this test had to carve out `cast_pronouns`,
    # which carries a recognised name regardless of sight. A view has no
    # such compartment: either she reached this mind or she did not.
    assert "tamamo" not in view.casefold()
    assert "close by" not in view


def test_dim_light_names_the_familiar_and_blurs_the_stranger(
        temp_db, monkeypatch):
    """Chat 63's actual room was dim: presence survives, faces do not.

    A recognised body seen as `shapes` still arrives under its name (you
    know who has been standing in the room with you) but marked
    sight:"shapes" so detail degrades honestly. An UNRECOGNISED body at
    `shapes` is only a figure — building its descriptor from the appearance
    summary would deliver detail (fox ears) a silhouette cannot show."""
    ctx, char_ids = _bystander_ctx(temp_db, light="dim", known={
        DOCTOR: [PLAYER, TAMAMO],
        TAMAMO: [PLAYER],           # has never met the Doctor
    })
    views = _pass1(ctx, monkeypatch)

    doctor = views[str(char_ids[DOCTOR])] or ""
    assert TAMAMO in doctor, (
        "dim light takes a face, not an acquaintance: a body this observer "
        "knows must not become an indistinct figure the moment a lamp dims")
    assert "fox" not in doctor.casefold()

    tamamo = views[str(char_ids[TAMAMO])] or ""
    assert "an indistinct figure" in tamamo.casefold()
    assert "the doctor" not in tamamo.casefold()
    assert "frock" not in tamamo.casefold()


def test_a_concealed_body_does_not_arrive_at_all(temp_db, monkeypatch):
    """Containment concealment beats co-location.

    A body carried inside another reads as `same_room` with everyone around
    the carrier; the roster must ask `visual_level_between` (which consults
    `containment_conceals`) rather than positions, or a body hidden in a
    pocket would be announced to the whole room."""
    ctx, char_ids = _bystander_ctx(temp_db)
    sc = temp_db.wget(ctx.chat["id"], "scene", {})
    sc["contained"] = {TAMAMO: {"in": PLAYER, "mode": "pocket"}}
    temp_db.wset(ctx.chat["id"], "scene", sc)
    view = _pass1(ctx, monkeypatch)[str(char_ids[DOCTOR])] or ""

    assert "tamamo" not in view.casefold()


def test_a_disguised_body_arrives_as_its_outward_form(temp_db, monkeypatch):
    """A disguise conceals appearance from everyone and identity from the
    unaware.

    The Doctor has met Tamamo, but he is not in the disguise's known_to —
    so connecting this hooded figure to the name he knows is exactly the
    unearned inference the disguise exists to prevent. The roster hands him
    the outward form's descriptor, never the name or a concealed feature."""
    ctx, char_ids = _bystander_ctx(temp_db)
    temp_db.qi(
        "INSERT INTO world_conditions("
        "condition_id,chat_id,subject_id,kind,started_at,payload,active) "
        "VALUES(?,?,?,?,?,?,1)",
        ("dz1", ctx.chat["id"], TAMAMO, "physical_disguise", time.time(),
         json.dumps({
             "subject_id": TAMAMO,
             "description": "her fox ears bound flat under a pilgrim's hood",
             "presented_appearance":
                 "a hooded pilgrim in travel-stained grey",
             "concealed_terms": ["fox-eared", "fox"],
             # A hood over the whole outward form is an identity claim, and
             # now has to make it: a disguise conceals FEATURES by default,
             # and only one that covers what a body is recognised by severs
             # the name. Without this the Doctor would still know her --
             # correctly, for a glamour that only hides ears; wrongly here.
             "conceals_identity": True,
             "known_to": [PLAYER],
         })))
    view = (_pass1(ctx, monkeypatch)[str(char_ids[DOCTOR])] or "").casefold()

    assert "tamamo" not in view
    assert "fox" not in view
    assert "pilgrim" in view


def test_a_disguise_that_hides_only_a_feature_leaves_the_name(temp_db,
                                                              monkeypatch):
    """THE OTHER HALF, and the one the old rule got wrong.

    A glamour over fox ears does not touch her face. Someone who has met her
    still knows exactly who he is looking at -- wearing unfamiliar ears --
    and denying that is the engine making a mind conclude less than its
    senses support. Live (chat 74) the old rule produced a view that used her
    NAME three times and a stranger's descriptor once, in one paragraph.
    """
    ctx, char_ids = _bystander_ctx(temp_db)
    temp_db.qi(
        "INSERT INTO world_conditions("
        "condition_id,chat_id,subject_id,kind,started_at,payload,active) "
        "VALUES(?,?,?,?,?,?,1)",
        ("dz2", ctx.chat["id"], TAMAMO, "physical_disguise", time.time(),
         json.dumps({
             "subject_id": TAMAMO,
             "description": "her fox ears glamoured to look human",
             "presented_appearance": "an ordinary woman with human ears",
             "concealed_terms": ["fox-eared", "fox"],
             "known_to": [PLAYER],
         })))
    view = (_pass1(ctx, monkeypatch)[str(char_ids[DOCTOR])] or "").casefold()

    assert "tamamo" in view, "he knows her face; the ears are not her face"
    assert "fox" not in view, "the concealed feature is still concealed"
