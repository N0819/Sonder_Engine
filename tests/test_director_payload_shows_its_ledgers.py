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
scene.comms"). The overlay fix of 254d898d is the one it does NOT reproduce,
because that hand READS a ledger it does not own -- see
`test_the_prose_author_can_see_the_ledgers_it_is_asked_to_end`.

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
    "world_facts": (None, "the world store, not the scene"),
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
    # --- spatial ----------------------------------------------------------
    "positions": ("positions", "Zolwarden"),
    "rooms": ("rooms", "Zolkeep Hall"),
    "remove_rooms": ("rooms", "Zolkeep Hall"),
    "remove_adjacent": ("rooms", "Zolkeep Hall"),
    "stations": ("stations", "zolhearth"),
    "poses": ("poses", "zolkneel"),
    "comms_ops": ("comms", "zolradio"),
    # --- offscreen --------------------------------------------------------
    "crowd_ops": (None, "the crowds table; delivered as `crowds`"),
    "courier_ops": (None, "the couriers table; delivered as `couriers`"),
    "telling_ops": (None, "world events; delivered as `carried_reports`"),
    "offscreen_plan_ops": (None, "plans in the world store; delivered as "
                                 "`offscreen_planning`"),
    "ratified_claims": (None, "background claims; delivered as "
                              "`unratified_claims`"),
    "contradicted_claims": (None, "background claims; delivered as "
                                  "`unratified_claims`"),
    # --- the prose author's own five, plus the two nobody writes here -----
    "time": ("time_of_day", "zoldawn"),
    "weather": ("weather", "thundersnow"),
    "location": ("location", "Zolmirath"),
    "following_ops": ("following", "Zolquill"),
    "consequences": (None, "the consequence queue is a table; this beat's own "
                           "arrivals come back as `engine_notices`"),
    "claim_dispositions": (None, "the claims are this turn's, from interpret"),
    "phase_sources": (None, "provenance stamped on this beat's own diff, not "
                            "a standing ledger"),
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


def _owner_step(channel):
    """The step key of the hand that writes `channel`."""
    # Through the facade: `tools/project_check.py` allows a test to name a
    # `director` sibling only to patch or introspect it, and this only reads.
    owner = director._CHANNEL_SPECIALISTS.get(channel)
    return f"director_{owner}" if owner else "director_resolve"


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


def _fake_agent(calls):
    """Records every call. The Director's own answer rules for EVERY hand,
    because a hand the ruling does not reach is not dispatched
    (`director_scopes._dispatch_specialists`) and an undispatched hand has
    no payload to check."""
    from agents.director import SPECIALISTS

    def fake(role, step_key, system, payload, **kw):
        calls.append({"step_key": step_key, "payload": payload})
        if step_key == "director_resolve":
            return {"ledger_notes": {name: f"{name}: settled this beat"
                                     for name in SPECIALISTS}}
        return {}
    return fake


def _resolve_payloads(temp_db, monkeypatch, scene=None):
    """Run one resolve over the rich scene; return {step_key: payload}."""
    from world.spatial import contact_id
    from world.survival import set_survival_enabled

    scene = json.loads(json.dumps(scene or RICH_SCENE))
    # The effect ledger is keyed on its parent contact, and
    # `_live_contact_actions` drops an orphan -- so the id has to be the one
    # the engine itself would stamp on the standing contact.
    cid = contact_id(scene["contacts"][0])
    scene["contacts"][0]["contact_id"] = cid
    scene["contact_actions"] = [{"actor": "Mara", "contact_id": cid,
                                 "action": "zolstroke"}]

    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls))
    ctx = _make_ctx(temp_db, scene=scene, interp=_interp())
    # `vitals` is gated on the survival setting, and `crowd_ops` and its
    # siblings on a crowd standing in reach -- without these two the body and
    # offscreen hands are never dispatched and the check would pass by never
    # asking.
    set_survival_enabled(ctx.chat.id, True)
    temp_db.wset(ctx.chat.id, "crowds", [
        {"uid": "crowd_1", "room_uid": "lamp_room", "band": "a dozen",
         "composition": "keepers", "mood": "restless"}])
    director.director_resolve(ctx, nonce=0)
    return scene, {c["step_key"]: c["payload"] for c in calls}


# ---------------------------------------------------------------------------
# The general guard.
# ---------------------------------------------------------------------------

def test_every_hand_is_shown_the_scene_ledgers_it_is_asked_to_write(
        temp_db, monkeypatch):
    """The guard that would have caught all five, before any of them shipped.

    For each channel whose standing value lives in the scene blob: the hand
    that OWNS that channel (`_CHANNEL_SPECIALISTS`, the same table
    `_route_repair_omissions` reads; the prose author owns whatever is
    undelegated) must receive that ledger. Checked by TOKEN rather than by
    key, because the delivery key is what the defect changes and several
    ledgers arrive reshaped -- a key-name assertion would pass on a payload
    that showed the hand the wrong ledger under the right name.
    """
    scene, payloads = _resolve_payloads(temp_db, monkeypatch)

    missing_hands = [step for step in {
        _owner_step(channel) for channel, (key, _t) in LEDGERS.items() if key
    } if step not in payloads]
    assert not missing_hands, (
        "a hand was never dispatched, so this run proves nothing about its "
        "payload: %s" % missing_hands)

    blind = []
    for channel, (key, token) in sorted(LEDGERS.items()):
        if not key:
            continue
        assert scene.get(key), (channel, key)  # the fixture, not the engine
        step = _owner_step(channel)
        if token.casefold() not in json.dumps(payloads[step]).casefold():
            blind.append(f"{step} writes `{channel}` and cannot see "
                         f"scene.{key}")
    assert not blind, blind


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


def test_the_prose_author_can_see_the_ledgers_it_is_asked_to_end(
        temp_db, monkeypatch):
    """The one case the owner-side guard above cannot state.

    `contacts` and `overlays` are DELEGATED -- their owners are `contact` and
    `body`, and the guard above checks them there. But chunk 12 asks the
    PROSE AUTHOR, which writes neither, to read both against what just
    happened and name what this beat brought to an end ("You can see the
    standing contact and overlay ledgers in the scene"). A hand asked to read
    a ledger it does not own is a second way to be blind, and it is the one
    that shipped: chat 111 turn 54 ended a mark that was in no payload it
    had, inferring the record's existence from the transcript prose.
    """
    scene, payloads = _resolve_payloads(temp_db, monkeypatch)
    view = payloads["director_resolve"]["scene"]
    assert view["overlays"] == scene["overlays"]
    assert [row["actor_part"] for row in view["contacts"]] == ["hand"]
    assert "zolgrip" in json.dumps(view["contacts"])


# ---------------------------------------------------------------------------
# The sky, which is the instance this file was written for.
# ---------------------------------------------------------------------------

def test_the_prose_author_can_see_the_sky_it_owns(temp_db, monkeypatch):
    """`weather` is the prose author's own channel and was in no payload.

    The sheet (prose_author_sheet/08.txt) asks for an edit ONLY when the beat
    changes the sky and says the engine drifts it in between, so the hand
    needs the standing value to answer either half -- and `thundersnow` is a
    flag the drift sets by itself which the same chunk forbids narrating
    lightning over snow without.
    """
    scene, payloads = _resolve_payloads(temp_db, monkeypatch)
    view = payloads["director_resolve"]["scene"]
    assert view["weather"] == scene["weather"]
    # Under its own name, like `time_of_day` beside it: showing the `time`
    # channel's owner a duration phrase under the key `time` is what taught
    # the model to write one back (see the comment on that key).
    assert view["weather"]["thundersnow"] is True
    assert "weather" not in payloads["director_resolve"], (
        "the sky belongs to the scene view, not beside it")


def test_an_undeclared_sky_costs_two_characters(temp_db, monkeypatch):
    """The cost, and why it is bounded rather than proportional.

    `overlays` cost 449 chars on chat 111 and 2 on a scene with no marks:
    proportional to what the scene holds. Weather cannot grow -- the
    vocabulary is closed (`world/weather.py`) and the shape fixed -- so the
    whole cost, forever, is `{}` before any sky is declared and 120-139
    characters after, against 4,187-8,463 for `attire` on the same scenes.
    """
    bare = json.loads(json.dumps(RICH_SCENE))
    bare.pop("weather")
    _scene, payloads = _resolve_payloads(temp_db, monkeypatch, scene=bare)
    assert payloads["director_resolve"]["scene"]["weather"] == {}
    assert len(json.dumps(
        payloads["director_resolve"]["scene"]["weather"])) == 2

    _scene, payloads = _resolve_payloads(temp_db, monkeypatch)
    cost = len(json.dumps(payloads["director_resolve"]["scene"]["weather"]))
    assert 100 < cost < 160, cost


@pytest.mark.parametrize("weather", [
    {"sky": s, "precipitation": p, "intensity": i, "wind": w,
     "temperature": t}
    for s, p, i, w, t in (
        ("clear", "none", "none", "still", "hot"),
        ("overcast", "drizzle", "light", "breeze", "mild"),
        ("storm", "hail", "heavy", "gale", "freezing"),
        ("fog", "snow", "moderate", "wind", "cold"),
    )])
def test_the_sky_reaches_the_payload_in_the_vocabulary_it_is_stored_in(
        weather, temp_db, monkeypatch):
    """No re-spelling on the way out.

    The sheet asks for `{sky, precipitation, intensity, wind, temperature}`
    "using the same vocabulary the opening used", and what a hand writes back
    is what it was shown -- so the payload must carry the stored words, not a
    prose rendering of them. `weather_words` exists for the reader-facing
    side and is deliberately not what goes here.
    """
    from world.weather import normalize_weather

    scene = json.loads(json.dumps(RICH_SCENE))
    scene["weather"] = normalize_weather(weather)
    scene, payloads = _resolve_payloads(temp_db, monkeypatch, scene=scene)
    assert payloads["director_resolve"]["scene"]["weather"] == scene["weather"]
