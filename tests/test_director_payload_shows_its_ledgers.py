"""Every hand the Director fans out to must be SHOWN the ledgers it writes.

One defect class, found live five times, fixed five times by adding one key to
one payload:

  * `stations` -- "it was being asked to write stations it was never allowed
    to read" (agents/director.py, interpret scene view);
  * `contacts` -- the Director "wrote `hand -> waist` one beat and
    `hand -> side` the next, not renaming anything but writing fresh each
    time, blind" (resolve scene view);
  * `comms` -- the spatial specialist owns `comms_ops`, whose `open`/`close`/
    `remove` are addressed by an `id` no payload had ever carried, so every
    maintenance op was written against a GUESSED key and
    `spatial_senses.apply_comms_ops` failed silently in three directions
    (agents/director_fanout.py);
  * `overlays` -- withheld while the prose author was asked to END marks, and
    chat 111 turn 54 ended one anyway from the transcript prose (254d898d);
  * `weather` -- this one. The prose author owns `state_diff.weather`, its
    sheet tells it the engine drifts the sky between its edits, and the sky
    was in no payload it received.

Every one of the five was found by a human reading a captured payload as the
model, one channel at a time, after the wrong behaviour had already shipped.
This file is the check that does not need the story to go wrong first: for
every channel some Director hand is asked to write, if the standing value of
that channel lives in the scene blob, the hand that writes it must be able to
see it. Verified by ablation rather than asserted: deleting each of the four
earlier fixes in turn makes
`test_every_hand_is_shown_the_scene_ledgers_it_is_asked_to_write` name that
exact channel and hand ("director_spatial writes `comms_ops` and cannot see
scene.comms"). Since 2026-09-27 the one encoder receives these standing
ledgers -- each granted channel's owner's world slice
(`director_prose.encoder_payload`) -- in place of the five causal hands;
dedicated checks also preserve the exact contact endpoint and overlay records
it needs to end them.

SCOPE, stated because it is the honest half. The guard covers ledgers that
live in the frame-scoped `world.scene` blob, which is one object a test can
populate completely. Channels whose standing value lives in a DATABASE ledger
(conditions, notices, crowds, couriers, carried reports, hearsay, open plans)
are listed in `LEDGERS` with the payload key that delivers them and are NOT
asserted here: each needs its own fixture, several are conditional on rows
existing, and a row asserted wrongly would be a false alarm on every run. They
are named rather than omitted so the next reader can see exactly how far the
guard reaches. `test_the_ledger_table_covers_every_channel_a_hand_writes`
keeps the scope honest: a new channel fails this file until somebody writes
down where its standing value lives.
"""

from __future__ import annotations

import json
import time
import uuid

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data

import agents.director as director
from tests.director_fakes import _fake_agent


# The scene every gate in `director_scopes._CHANNEL_GATES` fires on, with one
# distinctive token per ledger so a payload can be searched for the ledger
# rather than for the key it happens to be delivered under -- the delivery key
# is exactly the thing under test, and half the ledgers arrive transformed
# (attire as one compact line, contacts with a stamped `contact_id`, comms and
# substances as rows built from the stored table).
RICH_SCENE = {
    "location": "Zolmirath Lighthouse",
    "time_of_day": "the small hours before zoldawn",
    "weather": {"sky": "storm", "precipitation": "snow", "intensity": "heavy",
                "wind": "gale", "temperature": "freezing",
                "thundersnow": True},
    "rooms": {
        "keeper_room": {
            "name": "Zolkeep Hall",
            "adjacent": [
                {"to": "lamp_room", "barrier": "open", "distance": "near"},
            ],
        },
        "lamp_room": {"name": "Lamp Room", "adjacent": []},
    },
    # `Zolwarden` stands in no other ledger, so finding the name proves the
    # POSITIONS table arrived and not some neighbouring view of the same room.
    "positions": {"The Stranger": "keeper_room", "Mara": "keeper_room",
                  "Zolwarden": "keeper_room"},
    "entities": {
        "zol_lantern": {"name": "Zollantern", "kind": "object",
                        "room": "keeper_room"},
        # A destructible entity: the `destruction` gate reads `kind`.
        "zol_boat": {"name": "Zolboat", "kind": "vehicle",
                     "room": "keeper_room"},
    },
    "attire": {"Mara": {"wearing": ["zolcoat"]}},
    "overlays": {"Mara": ["zolsoot"]},
    "contacts": [{"actor": "Mara", "actor_part": "hand",
                  "target": "The Stranger", "target_part": "shoulder",
                  "manner": "zolgrip", "relation": "surface",
                  "motion": "settled"}],
    "contained": {"zolparcel": {"in": "Mara", "mode": "carried"}},
    "scales": {"Mara": 0.37},
    "poses": {"Mara": "zolkneel"},
    "stations": {"Mara": {"at": "zolhearth"}},
    "following": {"Zolwarden": "Zolquill"},
    "comms": {"zolradio": {"name": "Zolradio", "open": True}},
    "substances": [{"source": "Mara", "substance": "zolink",
                    "target": "The Stranger", "target_part": "cheek",
                    "placement": "surface"}],
    "vitals": {"The Stranger": {"injury": 0.41}},
}


#: channel -> (scene-blob key, token proving that ledger arrived) for a channel
#: whose standing value lives in the scene, or (None, why not) for one whose
#: does not. The `None` half is documentation with a completeness test behind
#: it, not a skip list: it names where the value DOES live and, where one
#: exists, the payload key that delivers it.
LEDGERS = {
    # --- body -------------------------------------------------------------
    "attire": ("attire", "zolcoat"),
    "overlays": ("overlays", "zolsoot"),
    "vitals": ("vitals", "0.41"),
    "conditions": (None, "world_conditions rows; delivered as "
                         "`active_conditions`/`active_awareness`"),
    # --- social -----------------------------------------------------------
    "cast_changes": (None, "the roster is chat_chars; the hand gets `cast`"),
    "introductions": (None, "the recognition ledger is a table"),
    "obligations": (None, "the world store; delivered as pending_obligations "
                           "at both Director stages; covered by test_causal_obligations"),
    # Compiled by the ENGINE, not by any hand (`ENGINE_CATEGORIES`), so no
    # specialist is ever shown a standing ledger of it -- there is none to
    # show. What was said is over when the beat is, like `sensory_events`.
    "speech": (None, "the beat's own record of what was said; no hand writes "
                     "it and nothing stands after the beat"),
    "public_evidence": (None, "describes THIS beat; there is no standing "
                              "ledger of it to show"),
    # --- contact ----------------------------------------------------------
    "contact_ops": ("contacts", "zolgrip"),
    "contact_action_ops": ("contact_actions", "zolstroke"),
    "substance_ops": ("substances", "zolink"),
    "containment": ("contained", "zolparcel"),
    "scales": ("scales", "0.37"),
    # --- objects ----------------------------------------------------------
    "entities": ("entities", "Zollantern"),
    "remove_entities": ("entities", "Zollantern"),
    "inventory_ops": ("entities", "Zollantern"),
    "artifact_ops": (None, "world_artifacts rows; delivered as `notices`"),
    "destruction": (None, "acts on rooms and entities the hand already has; "
                          "no ledger of its own"),
    "sensory_events": (None, "there IS no standing ledger: the beat number "
                             "is the whole lifetime, and a beat that says "
                             "nothing about a noise does not inherit the "
                             "last one -- which is the difference from "
                             "`state.running` and the reason the fog bell "
                             "was a defect"),
    # --- spatial ----------------------------------------------------------
    "positions": ("positions", "Zolwarden"),
    "rooms": ("rooms", "Zolkeep Hall"),
    "remove_rooms": ("rooms", "Zolkeep Hall"),
    "remove_adjacent": ("rooms", "Zolkeep Hall"),
    "stations": ("stations", "zolhearth"),
    "poses": ("poses", "zolkneel"),
    "comms_ops": ("comms", "zolradio"),
    # --- the world's traffic (the social hand's since 2026-09-04) ---------
    "crowd_ops": (None, "the crowds table; delivered as `crowds`"),
    "courier_ops": (None, "the couriers table; delivered as `couriers`"),
    "telling_ops": (None, "world events; delivered as `carried_reports`"),
    # The institution's own ledgers reach this hand through the charter
    # aperture the payload already carries (`scene_ledger`, the crowd and
    # figure projections), and the registry is the one owner of who is
    # employed and where they are standing -- so an errand is written
    # against what the beat can already see, and lands on the registry
    # rather than on any scene row.
    "charter_ops": (None, "the institution's own ledgers; delivered as "
                          "the charter aperture"),
    "ratified_claims": (None, "background claims; delivered as "
                              "`unratified_claims`"),
    "contradicted_claims": (None, "background claims; delivered as "
                                  "`unratified_claims`"),
    # --- scene-wide spatial state and non-scene channels ------------------
    # `time` HAS NO MODEL OWNER (2026-09-20). The beat's span is engine
    # arithmetic over the prose author's per-row `seconds`
    # (`world.mechanics.beat_time_from_spans`), so there is no hand to show a
    # ledger to -- and the ledger this row named was the wrong one anyway:
    # `scene.time_of_day` is the standing label establish writes, not the
    # clock a duration is measured against. The author gets the clock, under
    # `simulation_clock`, which the pair of tests below already covers.
    "time": (None, "engine-authored from the ledger's own `seconds`; the "
                   "author is shown the clock as `simulation_clock`"),
    "weather": ("weather", "thundersnow"),
    "location": ("location", "Zolmirath"),
    "following_ops": ("following", "Zolquill"),
    "consequences": (None, "the consequence queue is a table; this beat's own "
                           "arrivals come back as `engine_notices`"),
    "claim_dispositions": (None, "the claims are this turn's, from interpret"),
    "phase_sources": (None, "provenance stamped on this beat's own diff, not "
                            "a standing ledger"),
    "causal_steps": (None, "engine-authored execution order for this beat; "
                           "private to recompilation and never shown to a hand"),
    "movement_refused": (None, "engine-authored by the movement backstop "
                               "about this beat's own refusal; no hand "
                               "writes it and there is no standing ledger "
                               "of refusals to show"),
}


def _every_channel():
    """Every channel a Director hand is asked to write.

    The union of two registries, because neither is complete on its own:
    `StateDiff`'s fields are what the assembled diff can carry, and
    `SPECIALISTS` is what each hand is granted -- and `public_evidence` is
    granted to `social` while being no StateDiff field at all (see
    `director_scopes.CHANNEL_STAGES`, where that mismatch is documented as
    the reason three emissions were silently dropped).
    """
    from llm.schemas import StateDiff
    fields = set(getattr(StateDiff, "model_fields", None)
                 or StateDiff.__fields__)
    for spec in director.SPECIALISTS.values():
        fields.update(spec["channels"])
    return fields


def _make_ctx(temp_db, *, scene, interp):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(),
         f"char_mara_{uuid.uuid4().hex[:8]}"))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"))
    temp_db.wset(chat_id, "scene", json.loads(json.dumps(scene)))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "hello", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="hello", created=time.time()),
        cast=cast, input="hello")
    ctx.director_interpret = interp
    return ctx


def _interp():
    """A beat that both acts and speaks, so no gate is closed by the beat."""
    return {
        "sequence": [{"type": "action", "attempt": "pull off my wool coat",
                      "commitment": "asserted", "targets": [],
                      "visibility": "overt", "conceal_from": []},
                     {"type": "speech", "text": "Quiet night.",
                      "volume": "normal", "visibility": "overt",
                      "conceal_from": []}],
        "speech": "Quiet night.",
        "action": {"attempt": "pull off my wool coat"},
        "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }


PROSE = {"prose": "The keeper tends the lamp while the storm howls."}


def _encoder_payload(temp_db, monkeypatch, scene=None, *, survival=True, crowds=True,
                     interp=None, events=()):
    from world.spatial import contact_id
    from world.survival import set_survival_enabled

    scene = json.loads(json.dumps(scene or RICH_SCENE))
    if scene.get("contacts"):
        cid = contact_id(scene["contacts"][0])
        scene["contacts"][0]["contact_id"] = cid
        scene["contact_actions"] = [{"actor": "Mara", "contact_id": cid,
                                     "action": "zolstroke"}]
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": PROSE,
        "director_specialist": {"events": list(events), "missing_tools": [],
                                "missing_referents": [], "notes": []},
    }))
    ctx = _make_ctx(temp_db, scene=scene, interp=interp or _interp())
    if survival:
        set_survival_enabled(ctx.chat.id, True)
    if crowds:
        temp_db.wset(ctx.chat.id, "crowds", [
            {"uid": "crowd_1", "room_uid": "lamp_room", "band": "a dozen",
             "composition": "keepers", "mood": "restless"}])
    director.director_resolve(ctx, nonce=0)
    payloads = {c["step_key"]: c["payload"] for c in calls}
    return scene, payloads, calls


# ---------------------------------------------------------------------------
# The general guard.
# ---------------------------------------------------------------------------

def test_every_hand_is_shown_the_scene_ledgers_it_is_asked_to_write(temp_db, prose_director, monkeypatch):
    """The guard that would have caught all five, before any of them shipped.

    For each channel whose standing value lives in the scene blob: the hand
    that OWNS that channel (`_CHANNEL_SPECIALISTS`, the same table
    `_route_repair_omissions` reads; the prose author owns whatever is
    undelegated) must receive that ledger. Checked by TOKEN rather than by
    key, because the delivery key is what the defect changes and several
    ledgers arrive reshaped -- a key-name assertion would pass on a payload
    that showed the hand the wrong ledger under the right name.

    Ported 2026-09-27: the encoder receives, for every channel granted, its
    owner's world slice (`director_prose.encoder_payload`); one payload now
    carries what the five hands were shown.
    """
    scene, payloads, calls = _encoder_payload(temp_db, monkeypatch)
    enc = payloads["director_specialist"]
    granted = set(enc["granted_tools"])
    ungranted = sorted(ch for ch, (key, _t) in LEDGERS.items() if key and ch not in granted)
    blind = []
    for channel, (key, token) in sorted(LEDGERS.items()):
        if not key:
            continue
        assert scene.get(key), (channel, key)
        if token.casefold() not in json.dumps(enc).casefold():
            blind.append(f"encoder writes `{channel}` and cannot see scene.{key}")
    assert not blind, blind
    assert not ungranted


@pytest.mark.parametrize("has_clock", [False, True])
def test_current_causal_spatial_hand_sees_standing_scene_and_clock(temp_db, prose_director, monkeypatch, has_clock):
    """The current row contract must carry the state its new owner writes.

    A scene predating the clock still has an authored time-of-day label. The
    payload can expose that label without inventing a clock or its elapsed
    time; a real existing clock must arrive unchanged.

    Ported 2026-09-27: the encoder receives, for every channel granted, its
    owner's world slice (`director_prose.encoder_payload`); one payload now
    carries what the five hands were shown.
    """
    scene = json.loads(json.dumps(RICH_SCENE))
    ctx = _make_ctx(temp_db, scene=scene, interp={"sequence": []})
    clock = {"elapsed_seconds": 7200, "display": scene["time_of_day"],
             "time_scale": "scene", "anchor_hour": 1.25}
    if has_clock:
        temp_db.wset(ctx.chat.id, "simulation_clock", clock)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": PROSE,
        "director_specialist": {"events": [], "missing_tools": [],
                                "missing_referents": [], "notes": []},
    }))
    director.director_resolve(ctx, nonce=0)
    spatial = next(c["payload"] for c in calls if c["step_key"] == "director_specialist")
    for key in ("following", "location", "weather", "time_of_day"):
        assert spatial[key] == scene[key], key
    if has_clock:
        assert spatial["simulation_clock"] == clock
        assert temp_db.wget(ctx.chat.id, "simulation_clock", None) == clock
    else:
        assert spatial["simulation_clock"]["elapsed_seconds"] == 0
        assert spatial["simulation_clock"]["display"] == ""
        assert temp_db.wget(ctx.chat.id, "simulation_clock", None) is None


def test_resolve_and_its_hands_see_the_room_interpret_just_authored(temp_db, prose_director, monkeypatch):
    """`docs/guides/PIPELINE.md`: director_resolve "receives the same
    previewed world". It did not -- only `contacts` came from the preview;
    rooms, positions and stations came from the stored scene. Chat 117 turn
    82: the interpret spatial hand authored the plenum the player climbed
    into, with `vertical: "down"` and a see-through sleeve; the resolve hand
    never saw it, wrote the same room blind under another name with neither
    field, and the merge let the blind version win. The causal Director's
    world index must include the asserted room and occupants, while the
    spatial hand receives the full room record it owns.

    Ported 2026-09-27: the encoder receives, for every channel granted, its
    owner's world slice (`director_prose.encoder_payload`); one payload now
    carries what the five hands were shown.
    """
    interp = _interp()
    interp["onset_state_assertions"] = {
        "rooms": {"asserted_attic": {
            "name": "The Attic",
            "desc": "a low boarded loft over the keeper's room",
            "adjacent": [{"to": "keeper_room", "barrier": "open",
                          "vertical": "down", "name": "the loft hatch"}]}},
        "positions": {"Mara": "asserted_attic"},
    }
    scene, payloads, _ = _encoder_payload(temp_db, monkeypatch, interp=interp,
                                          survival=False, crowds=False)
    enc = payloads["director_specialist"]
    causal = payloads["director_prose"]
    rooms = causal["world_index"]["rooms"]
    assert "asserted_attic" in rooms, sorted(rooms)
    assert "keeper_room" in rooms["asserted_attic"]["exits"]
    assert any(body["id"] == "Mara" for body in rooms["asserted_attic"]["holds"])
    assert causal["standing_relations"]["positions"]["Mara"] == "asserted_attic"
    assert enc["positions"]["Mara"] == "asserted_attic"
    assert enc["world_index"] == causal["world_index"]
    assert "asserted_attic" in enc["rooms"], sorted(enc["rooms"])


def test_the_ledger_table_covers_every_channel_a_hand_writes():
    """The half that keeps the guard from rotting.

    A new channel is added, with a specialist to own it and a prompt asking
    for it; whether its standing value reaches that hand is the question
    nobody asks -- five times over, so far. It cannot be asked automatically
    -- "does this channel have a standing value, and where" is a judgement --
    so this test asks a person for it once, at the moment the channel is
    added, and records the answer above.
    """
    channels = _every_channel()
    assert set(LEDGERS) == channels, {
        "undocumented": sorted(channels - set(LEDGERS)),
        "no longer a channel": sorted(set(LEDGERS) - channels),
    }


def test_contact_and_body_hands_can_see_the_ledgers_they_are_asked_to_end(temp_db, prose_director, monkeypatch):
    """The current owners receive the exact records an ending addresses.

    Chat 111 turn 54 ended a mark that the old prose author had never been
    shown. Causal dispatch assigns those endings to contact and body; those
    hands must see the standing endpoint and overlay rather than reconstruct
    them from the transcript.

    Ported 2026-09-27: the encoder receives, for every channel granted, its
    owner's world slice (`director_prose.encoder_payload`); one payload now
    carries what the five hands were shown.
    """
    scene, payloads, _ = _encoder_payload(temp_db, monkeypatch)
    enc = payloads["director_specialist"]
    assert enc["overlays"] == scene["overlays"]
    contacts = enc["contacts"]
    assert [row["actor_part"] for row in contacts] == ["hand"]
    assert "zolgrip" in json.dumps(contacts)
    assert contacts[0]["contact_id"] == scene["contacts"][0]["contact_id"]


# ---------------------------------------------------------------------------
# The sky, which is the instance this file was written for.
# ---------------------------------------------------------------------------

def test_the_spatial_hand_can_see_the_sky_it_owns(temp_db, prose_director, monkeypatch):
    """Weather's current owner sees the standing sky without rewriting it.

    The spatial weather chunk asks for an edit only when the event changes
    the sky. The engine may have drifted the weather since its last edit.
    The stored record here predates operational axes and carries the retired
    `thundersnow` flag; payload assembly must preserve that record too.

    Ported 2026-09-27: the encoder receives, for every channel granted, its
    owner's world slice (`director_prose.encoder_payload`); one payload now
    carries what the five hands were shown.
    """
    scene, payloads, _ = _encoder_payload(temp_db, monkeypatch)
    view = payloads["director_specialist"]
    assert view["weather"] == scene["weather"]
    assert view["weather"]["thundersnow"] is True


def test_an_undeclared_sky_costs_two_characters(temp_db, prose_director, monkeypatch):
    """The cost, and why it is bounded rather than proportional.

    `overlays` cost 449 chars on chat 111 and 2 on a scene with no marks:
    proportional to what the scene holds. Weather cannot grow with the scene
    -- the axis shape is fixed at ten keys (`world/weather.py`) and the only
    free text in it is the two authored names, each bounded by `NAME_LIMIT`
    (60) -- so the whole cost is `{}` before any sky is declared, 185-206
    characters across the 5x6x4x4x5 cross product of this engine's own sky
    and fall words with intensity, wind and temperature (measured 2026-09-08
    over `normalize_weather`), and 316 at the ceiling with both names
    authored at full length -- 342 once `drift_step` is stamped, which every
    live record carries after the first declaration -- against 4,187-8,463
    for `attire` on the
    same scenes. The record this test measures is a shorter pre-axis one.

    Ported 2026-09-27: the encoder receives, for every channel granted, its
    owner's world slice (`director_prose.encoder_payload`); one payload now
    carries what the five hands were shown.
    """
    bare = json.loads(json.dumps(RICH_SCENE))
    bare.pop("weather")
    _scene, payloads, _ = _encoder_payload(temp_db, monkeypatch, scene=bare)
    assert payloads["director_specialist"]["weather"] == {}
    assert len(json.dumps(payloads["director_specialist"]["weather"])) == 2
    _scene, payloads, _ = _encoder_payload(temp_db, monkeypatch)
    cost = len(json.dumps(payloads["director_specialist"]["weather"]))
    assert 100 < cost < 160, cost


@pytest.mark.parametrize("weather", [
    {"sky": s, "precipitation": p, "intensity": i, "wind": w, "temperature": t}
    for s, p, i, w, t in (
        ("clear", "none", "none", "still", "hot"),
        ("overcast", "drizzle", "light", "breeze", "mild"),
        ("storm", "hail", "heavy", "gale", "freezing"),
        ("fog", "snow", "moderate", "wind", "cold"),
    )])
def test_the_sky_reaches_the_payload_in_the_vocabulary_it_is_stored_in(weather, temp_db, prose_director, monkeypatch):
    """No re-spelling on the way out.

    The sheet asks for `{sky, precipitation, intensity, wind, temperature}`
    "using the same vocabulary the opening used", and what a hand writes back
    is what it was shown -- so the payload must carry the stored words, not a
    prose rendering of them. `weather_words` exists for the reader-facing
    side and is deliberately not what goes here.

    Ported 2026-09-27: the encoder receives, for every channel granted, its
    owner's world slice (`director_prose.encoder_payload`); one payload now
    carries what the five hands were shown.
    """
    from world.weather import normalize_weather
    scene = json.loads(json.dumps(RICH_SCENE))
    scene["weather"] = normalize_weather(weather)
    scene, payloads, _ = _encoder_payload(temp_db, monkeypatch, scene=scene)
    assert payloads["director_specialist"]["weather"] == scene["weather"]

