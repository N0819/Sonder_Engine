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
import time

import pytest

from character_schema import default_character_data, default_persona_data
from pipeline_context import ChatData, PipelineContext, TurnData


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
    """Run a perception pass against a stub model, keeping each observer's
    exact payload — the test subject is what the engine DELIVERS, and the
    stubbed view keeps every deterministic post-pass from having anything
    of its own to add."""
    import agents.perception as perception

    captured = {}

    def capture(role, key, system, payload, **kw):
        perceiver = payload["perceivers"][0]
        captured[str(perceiver["id"])] = payload
        return {"views": {str(perceiver["id"]): "You are in the Hall."}}

    monkeypatch.setattr(perception, "_agent_json", capture)
    run(perception)
    return captured


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
    captured = _pass1(ctx, monkeypatch)

    for observer, other in ((DOCTOR, TAMAMO), (TAMAMO, DOCTOR)):
        payload = captured[str(char_ids[observer])]
        prox = payload["perceivers"][0].get("proximity_to_sources") or {}
        assert other in prox, (
            f"{observer}'s pass-1 payload does not deliver co-present "
            f"{other}: {sorted(prox)}")
        assert prox[other]["tier"] == "near"
        assert prox[other]["sight"] == "full"


def test_pass_one_bystander_is_presence_not_an_actor(temp_db, monkeypatch):
    """A bystander must not be handed over as someone DOING something.

    The engine already learned this on contacts: a bare relation record read
    as an event and was narrated as one. The roster therefore carries only
    stative placement data — nothing act-shaped for the model to lift."""
    ctx, char_ids = _bystander_ctx(temp_db)
    captured = _pass1(ctx, monkeypatch)

    prox = captured[str(char_ids[DOCTOR])]["perceivers"][0][
        "proximity_to_sources"]
    assert set(prox[TAMAMO]) <= {"tier", "side", "arc", "sight"}


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

    captured = _capture_payloads(
        monkeypatch, lambda p: p.perception_outcome(ctx, nonce="n"))

    for observer, other in ((DOCTOR, TAMAMO), (TAMAMO, DOCTOR)):
        payload = captured[str(char_ids[observer])]
        prox = payload["perceivers"][0].get("proximity_to_sources") or {}
        assert prox.get(other, {}).get("tier") == "near"
        assert other in {s.get("name") for s in payload.get("sources") or []}


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
    captured = _pass1(ctx, monkeypatch)

    payload = captured[str(char_ids[DOCTOR])]
    assert "tamamo" not in json.dumps(payload).casefold()
    prox = payload["perceivers"][0]["proximity_to_sources"]
    (label,) = prox.keys()
    assert "fox" in label.casefold()      # described by what is visibly there


def test_a_body_in_the_dark_does_not_arrive_at_all(temp_db, monkeypatch):
    """The roster must not out-see the light.

    `visual_level_between` already answers "none" for an unlit body; a
    presence roster that bypassed it would tell an observer who is standing
    in a pitch-dark room with them — sight the room does not grant."""
    ctx, char_ids = _bystander_ctx(temp_db, light="dark")
    captured = _pass1(ctx, monkeypatch)

    payload = captured[str(char_ids[DOCTOR])]
    assert payload["perceivers"][0].get("proximity_to_sources") in ({}, None)
    # cast_pronouns legitimately carries a RECOGNISED name regardless of
    # sight (stable pronouns for people you know are knowledge, not
    # perception); everything else must stay silent about her.
    dump = json.dumps(
        {k: v for k, v in payload.items() if k != "cast_pronouns"})
    assert "tamamo" not in dump.casefold()


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
    captured = _pass1(ctx, monkeypatch)

    doctor = captured[str(char_ids[DOCTOR])]
    prox = doctor["perceivers"][0]["proximity_to_sources"]
    assert prox[TAMAMO]["sight"] == "shapes"
    assert "fox" not in json.dumps(doctor).casefold()

    tamamo = captured[str(char_ids[TAMAMO])]
    prox = tamamo["perceivers"][0]["proximity_to_sources"]
    (label,) = prox.keys()
    assert label == "an indistinct figure"
    assert "the doctor" not in json.dumps(tamamo).casefold()
    assert "frock" not in json.dumps(tamamo).casefold()


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
    captured = _pass1(ctx, monkeypatch)

    payload = captured[str(char_ids[DOCTOR])]
    # cast_pronouns is recognition-gated knowledge, not sight — see the
    # dark-room test above.
    dump = json.dumps(
        {k: v for k, v in payload.items() if k != "cast_pronouns"})
    assert "tamamo" not in dump.casefold()


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
             "known_to": [PLAYER],
         })))
    captured = _pass1(ctx, monkeypatch)

    payload = captured[str(char_ids[DOCTOR])]
    dump = json.dumps(payload).casefold()
    assert "tamamo" not in dump
    assert "fox" not in dump
    prox = payload["perceivers"][0]["proximity_to_sources"]
    assert any("pilgrim" in label.casefold() for label in prox)
