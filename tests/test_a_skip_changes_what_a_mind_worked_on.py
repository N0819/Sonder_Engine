"""A mind's own work in a skip changes the things it worked on
(`agents/skip_work.py`, laid at the far end by `agents/skip_stage.FarEnd`).

The lighthouse replayed on 8e3c60f2 (job tmp `fixes/live_skip6`, chat 3, turns
25 and 26): bodies moved -- each mind ended where its own day took it -- and
things did not. The keeper put the lamp out at dawn and lit it at dusk in rows
the executor marked `done`, and the lamp, the station mail and every crate
stood as the stretch had found them, while the memory job wrote that he had
done it all. The owner, of exactly this: "And do they actually change position
to reflect their actions?"

The rule: a `done` row on the map is told to the engine's encoder, once per
mind, and what it types for the things the mind had to hand is applied at the
far end -- in time order across minds, through the floors a beat's own changes
pass -- under the beat's own diff; a `failed`, `not_known`, off-map or asleep
row changes nothing, no body is placed by it, and a mind with no such row is
asked nothing. The encoder is stubbed at the Director's seam
(`agents.director._agent_json`), as every Director test stubs it; the world is
that story's shape, made small.
"""

from __future__ import annotations

import copy
import json
import time

import pytest

from core.pipeline_context import ChatData, PipelineContext, TurnData

PLAYER, ELIAS, NELL = "Rhona Carrick", "Elias Thorne", "Nell Hale"

#: The lighthouse's clock at its skip beat (chat 3 idx 8): 78466 s elapsed,
#: the day standing at 13:32.
CLOCK = {"elapsed_seconds": 78466.0, "anchor_hour": 15.75,
         "day_length_hours": 24.0, "display": "afternoon"}
SPAN = {"from_s": 78466.0, "until_s": 78466.0 + 48 * 3600.0}


def _rooms():
    return {
        "hall": {"name": "The Hall", "exposure": "enclosed",
                 "adjacent": [{"to": "kitchen", "barrier": "open_door"}],
                 "anchors": {"hall_table": {"desc": "a deal table by the stove"}}},
        "kitchen": {"name": "The Kitchen", "exposure": "enclosed",
                    "adjacent": [{"to": "hall", "barrier": "open_door"},
                                 {"to": "lamp_room", "barrier": "open"}]},
        "lamp_room": {"name": "The Lamp Room", "exposure": "enclosed",
                      "adjacent": [{"to": "kitchen", "barrier": "open"}],
                      "anchors": {"pedestal": {"desc": "the iron pedestal the lens turns on"}}},
    }


def _scene():
    return {
        "location": "the lighthouse", "time_of_day": "afternoon",
        "rooms": _rooms(),
        "entities": {
            "lamp": {"name": "the tower lamp", "kind": "light", "portable": False,
                     "light_source": "bright", "state": {"lit": False},
                     "description": "The great lantern at the top of the tower."},
            "clockwork": {"name": "the new clockwork", "kind": "mechanism",
                          "portable": True, "state": {"assembly": "unfitted"},
                          "description": "The Board's new clockwork, on a sack."},
            "crate": {"name": "the crate from the Board", "kind": "container",
                      "portable": True, "container": True, "state": {"hatch": "open"},
                      "description": "A wooden crate stood open on the floor."},
            "letter": {"name": "a sealed letter", "kind": "document", "portable": True,
                       "state": {}, "description": "A letter sealed with wax."},
            "oil_can": {"name": "the oil can", "kind": "tool", "portable": True,
                        "state": {}, "description": "A can with a long spout."},
        },
        "positions": {PLAYER: "kitchen", ELIAS: "lamp_room", NELL: "kitchen",
                      "lamp": "lamp_room", "clockwork": "lamp_room",
                      "crate": "lamp_room", "letter": "hall", "oil_can": "kitchen"},
        "stations": {}, "poses": {}, "contained": {}, "contacts": [],
        "attire": {ELIAS: {"wearing": ["oilskin coat"]}},
        "overlays": {}, "orientation": {},
    }


@pytest.fixture
def story(temp_db):
    """The lighthouse made small: the keeper in the lamp room, a second mind
    and the player in the kitchen, the lamp unlit, the new clockwork on the
    floor beside its crate, a letter in the hall, an oil can in the kitchen."""
    from core.db import qi, wset
    from story.character_schema import default_character_data, default_persona_data
    now = time.time()
    persona = qi("INSERT INTO personas(name,sheet,source) VALUES(?,?,?)",
                 (PLAYER, json.dumps(default_persona_data(PLAYER)), "{}"))
    chat = qi("INSERT INTO chats(name,scenario,created,persona_id) VALUES(?,?,?,?)",
              ("The Lamp Room", "", now, persona))
    ids = {}
    graph = {"place_graph": {"nodes": {r: {"name": v["name"]} for r, v in _rooms().items()},
                             "edges": {}}}
    for name, tier in ((ELIAS, "major"), (NELL, "mid")):
        sheet = default_character_data(name)
        sheet.setdefault("simulation", {})["tier"] = tier
        ids[name] = qi("INSERT INTO characters(name,sheet,source,created,resource_uid) "
                       "VALUES(?,?,?,?,?)", (name, json.dumps(sheet), "{}", now,
                                             "uid_" + name.split()[0].casefold()))
        qi("INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
           (chat, ids[name], "active", json.dumps(graph)))
    wset(chat, "scene", _scene())
    wset(chat, "simulation_clock", dict(CLOCK))
    wset(chat, "known", {ELIAS: [PLAYER, NELL], NELL: [ELIAS, PLAYER], PLAYER: [ELIAS, NELL]})
    prev = qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (chat, 7, "By the middle of the afternoon ...", now))
    turn = qi("INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
              (chat, 8, "Two days later the wind gets up from the west ...", now))
    from agents.storage import save_step
    save_step(prev, "perception_outcome", "Perception", 6, {"views": {}, "observations": {}})

    def context(interp=None):
        from story.scene import active_cast
        ctx = PipelineContext(
            chat=ChatData(id=chat, name="The Lamp Room", persona_id=persona,
                          lorebook_id=None, scenario="", created=now),
            turn=TurnData(id=turn, chat_id=chat, idx=8,
                          player_input="Two days later ...", created=now),
            cast=active_cast(chat), input="Two days later ...")
        ctx.director_interpret = interp if interp is not None else _interp()
        return ctx

    return {"chat": chat, "ids": ids, "turn": turn, "context": context}


def _interp():
    """The input's two-day skip, kept, the player placed in the kitchen."""
    from world.day_cycle import seconds_until
    hour0 = (15.75 + 78466.0 / 3600.0) % 24.0
    block = {"days": 2, "until_phase": "morning",
             "duration_seconds": seconds_until(hour0, phase="morning", days=2)}
    return {"state_assertions": {"time": dict(block), "causal_steps": [
                {"chrono_id": 1, "stage": "interpret", "patch": {"time": dict(block)}}],
                "positions": {PLAYER: "kitchen"}},
            "onset_state_assertions": {"positions": {PLAYER: "kitchen"}},
            "causal_ledger": [{"chrono_id": 1, "seconds": 0.0, "commitment": "asserted"}],
            "flow": {"reactors": [], "tom_triggers": []}, "authorial_offers": []}


def _row(start, end, room=None, *, away=None, doing="", outcome="done",
         asleep=False, reason=None):
    """One LOG row, in the build spec's shape."""
    return {"from_s": float(start), "until_s": float(end), "room": room, "away": away,
            "where_text": "", "doing": doing, "asleep": asleep, "seen": [],
            "weather": None, "outcome": outcome, "reason": reason, "missing": [],
            "meant": None}


def _mind(log, room="lamp_room", itinerary=None, away=None):
    """One mind's step entry: its log, the stretches it was lived under, and
    the far end its last row leaves it at."""
    stretches = itinerary if itinerary is not None else [
        {"from_s": r["from_s"], "until_s": r["until_s"], "room": r["room"],
         "away": r["away"], "where_text": "", "doing": r["doing"], "asleep": r["asleep"],
         "with": [], "why": "", "uses": []} for r in log]
    return {"source": "asked", "answer": None, "itinerary": stretches, "log": log,
            "far_end": {"room": room, "away": away, "asleep": False,
                        "asleep_since_s": None, "left_from": None}}


def _event(event_id, source, transforms, event="works"):
    return {"source_entity_id": source, "source_event_id": event_id, "event": event,
            "observable": event, "speech": False, "targets": [], "seconds": 60,
            "movement": None, "commitment": "asserted",
            "item_names": [t["item"] for t in transforms], "transforms": transforms}


def _encoder(by_doing, calls, also=()):
    """The encoder, stubbed at the Director's seam: for every line of the
    account told it that carries a key of `by_doing`, one event filed under
    that line's event id with the transforms given for it; and every
    `(event id, transforms)` in `also` filed as given, told or not."""
    def fake(role, step_key, system, payload, **kwargs):
        calls.append({"role": role, "step_key": step_key, "system": system,
                      "payload": copy.deepcopy(payload)})
        if step_key != "director_specialist":
            raise RuntimeError(f"unexpected call {step_key}")
        source = next(iter(payload["identity_index"]))
        events = []
        for line in payload["prose"].splitlines():
            told = line[1:line.index("]")]
            for words, transforms in by_doing.items():
                if words in line:
                    events.append(_event(told, source, copy.deepcopy(transforms), words))
        for told, transforms in also:
            events.append(_event(told, source, copy.deepcopy(transforms)))
        return {"events": events, "missing_tools": [], "missing_referents": [], "notes": []}
    return fake


def _lit(value):
    return {"item": "the tower lamp", "patch": {"entities": {"lamp": {"state": {"lit": value}}}}}


def _set_down(thing, item, to_id, from_id="lamp_room", relation=None):
    op = {"op": "transfer", "object_id": thing, "from_id": from_id, "to_id": to_id}
    if relation:
        op["relation"] = relation
    return {"item": item, "patch": {"inventory_ops": [op]}}


def _type(story, monkeypatch, minds, by_doing, also=(), named=None):
    """The stage's last step on a hand-built output: every mind's work typed
    (the encoder stubbed) and settled against the stored world."""
    import agents.director as director
    from agents import skip_work
    from core.db import wget
    calls = []
    monkeypatch.setattr(director, "_agent_json", _encoder(by_doing, calls, also))
    ctx = story["context"]()
    ids = {name.casefold(): cid for name, cid in story["ids"].items()}
    skip_work.type_the_work(ctx, minds, wget(story["chat"], "scene"), ids, named=named)
    ctx.skip_lives = {"span": dict(SPAN), "minds": minds}
    return ctx, calls


def _commit(ctx):
    """The commit's scene and skip domains, as a turn runs them: the far end
    previewed for the preparation, then written in one transaction."""
    from agents.skip_stage import far_end_for, onset_preview
    from core.db import transaction, wget
    from persist.commit import commit_scene, commit_skip_lives, prepare_scene_commit
    ctx.director_resolve = {"state_diff": {}, "dialogue_log": [],
                            "resolved_event": "", "sequence": []}
    with onset_preview(far_end_for(ctx)):
        prepared = prepare_scene_commit(ctx)
    with transaction():
        commit_scene(ctx, 0, prepared=prepared)
        commit_skip_lives(ctx, 0)
    return wget(ctx.chat.id, "scene")


# --------------------------------------------------------------------------
# Through the stage
# --------------------------------------------------------------------------

def _ask(by_name):
    """The skip question, stubbed: each asked mind answers as given."""
    def model(role, step_key, system, payload, **kwargs):
        answer = by_name.get(payload["self"]["name"])
        if answer is None:
            raise RuntimeError("no answer")
        return copy.deepcopy(answer)
    return model


def _run_stage(story, monkeypatch, answers, by_doing):
    import agents.director as director
    from agents import skip_stage
    from llm import decisions
    calls = []
    monkeypatch.setattr(skip_stage, "_agent_json", _ask(answers))
    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {})
    monkeypatch.setattr(director, "_agent_json", _encoder(by_doing, calls))
    ctx = story["context"]()
    out = skip_stage.skip_lives(ctx, 0)
    ctx.skip_lives = out
    return ctx, out, calls


KEEPER_EVENING = {"plan": [
    {"day": 0, "from": "dusk", "until": "evening", "where": "The Lamp Room",
     "doing": "lights the lamp at dusk and sets the new clockwork on the pedestal",
     "asleep": False, "with": [], "why": "THE KEEPER'S OWN REASON", "uses": []},
    {"day": 1, "from": "morning", "until": "midday", "where": "The Lamp Room",
     "doing": "test-fits the clockwork beside Rhona", "asleep": False,
     "with": [PLAYER], "why": "", "uses": []}]}
NELL_EVENING = {"plan": [
    {"day": 0, "from": "evening", "until": "night", "where": "The Kitchen",
     "doing": "darns socks by the range", "asleep": False, "with": [],
     "why": "", "uses": []}]}


def test_a_done_row_on_the_map_changes_what_it_worked_on(story, monkeypatch):
    """The keeper's dusk in the lamp room comes off (`done`): told to the
    encoder, the lamp it lit is lit and the clockwork it set on the pedestal
    stands there, in the scene the far end previews and in the scene the
    turn's whole commit writes -- under the beat's own (empty) diff. His row
    with the player (`not_known`) is not told. Background work is held back:
    queued, never run."""
    from agents.skip_stage import far_end_for, onset_preview
    from core import jobs
    from core.db import wget
    from persist.commit import commit_all
    from story.scene import get_scene
    monkeypatch.setattr(jobs, "submit", lambda *a, **k: None)
    monkeypatch.setattr(jobs, "submit_latest", lambda *a, **k: None)
    ctx, out, calls = _run_stage(
        story, monkeypatch, {ELIAS: KEEPER_EVENING, NELL: NELL_EVENING},
        {"lights the lamp": [_lit(True), _set_down("clockwork", "the new clockwork",
                                                   "pedestal")]})
    keeper = [c for c in calls if c["payload"]["identity_index"].get(
        f"character:{story['ids'][ELIAS]}") == ELIAS]
    assert len(keeper) == 1
    told = keeper[0]["payload"]["prose"]
    assert "lights the lamp at dusk" in told and "test-fits" not in told
    worked = out["minds"][ELIAS]["worked"]
    assert len(worked["changes"]) == 2 and not worked["record"].get("failed")
    with onset_preview(far_end_for(ctx)):
        previewed = get_scene(story["chat"])
    assert previewed["entities"]["lamp"]["state"]["lit"] is True
    ctx.director_resolve = {"state_diff": {}, "dialogue_log": [],
                            "resolved_event": "", "sequence": []}
    commit_all(ctx, 0)
    scene = wget(story["chat"], "scene")
    assert scene["entities"]["lamp"]["state"]["lit"] is True
    assert scene["positions"]["clockwork"] == "lamp_room"
    assert (scene.get("stations") or {}).get("clockwork", {}).get("at") == "pedestal"
    assert scene["positions"][ELIAS] == out["minds"][ELIAS]["far_end"]["room"]


def test_the_encoder_is_told_the_doing_and_never_the_why(story, monkeypatch):
    """THE FIREWALL. The encoder sees the mind's own done rows as public
    conduct -- each row's doing and its room -- and the world it needs to
    type them: the things it had to hand where its rows were spent, never
    the reason it gave, what it saw of anyone, or a thing out of its reach.
    Its sheet carries the skip's own piece and the channels that change
    things, never the one that places a body."""
    from llm.prompts import encoder_definition, prose_contract_text
    _ctx, out, calls = _run_stage(
        story, monkeypatch, {ELIAS: KEEPER_EVENING, NELL: NELL_EVENING},
        {"lights the lamp": [_lit(True)]})
    keeper = next(c for c in calls if ELIAS in c["payload"]["identity_index"].values())
    sent = json.dumps(keeper["payload"], ensure_ascii=False)
    assert "THE KEEPER'S OWN REASON" not in sent
    assert "darns socks" not in sent                      # another mind's doing
    assert set(keeper["payload"]["entities"]) == {"lamp", "clockwork", "crate"}
    assert keeper["payload"]["granted_tools"][:3] == ["entities", "inventory_ops",
                                                      "containment"]
    assert "positions" not in keeper["payload"]["granted_tools"]
    assert prose_contract_text("encoder_skip").strip()[:40] in keeper["system"]
    for channel in ("entities", "inventory_ops", "containment"):
        assert encoder_definition(channel)[:40] in keeper["system"]
    for channel in ("positions", "poses", "stations", "time", "conditions", "attire"):
        assert encoder_definition(channel)[:40] not in keeper["system"]


# --------------------------------------------------------------------------
# Which rows count
# --------------------------------------------------------------------------

def test_failed_not_known_off_map_and_asleep_rows_change_nothing(story, monkeypatch):
    """Only a `done` row on the map, awake, is told: a failed row did not come
    off, a `not_known` row's outcome is not known, off the map the world holds
    no thing, and a sleep is no work. A change filed under a row that was not
    told has no time or place to stand at, and lands nowhere."""
    t = SPAN["from_s"]
    log = [_row(t, t + 3600, "lamp_room", doing="oils the lamp bearings",
                outcome="failed", reason="no_route"),
           _row(t + 3600, t + 7200, "lamp_room", doing="fits the clockwork with Rhona",
                outcome="not_known"),
           _row(t + 7200, t + 10800, away="the harbour", doing="posts the sealed letter"),
           _row(t + 10800, t + 14400, "lamp_room", doing="sleeps in the chair",
                asleep=True),
           _row(t + 14400, t + 18000, "lamp_room", doing="lights the lamp")]
    minds = {ELIAS: _mind(log)}
    ctx, calls = _type(story, monkeypatch, minds, {"lights the lamp": [_lit(True)]}, also=(
        ("stretch:0", [{"item": "the tower lamp", "patch": {"entities": {
            "lamp": {"state": {"lit": True, "bearings": "oiled"}}}}}]),
        ("stretch:1", [_set_down("clockwork", "the new clockwork", "pedestal")]),
        ("stretch:2", [{"item": "a sealed letter", "patch": {"entities": {
            "letter": {"state": {"posted": True}}}}}]),
        ("stretch:3", [_set_down("crate", "the crate from the Board", "pedestal")])))
    told = calls[0]["payload"]["prose"].splitlines()
    assert [line[1:line.index("]")] for line in told] == ["stretch:4"]
    assert minds[ELIAS]["worked"]["record"]["unfiled"] == 4
    scene = _commit(ctx)
    assert scene["entities"]["lamp"]["state"]["lit"] is True
    assert "bearings" not in scene["entities"]["lamp"]["state"]
    assert "posted" not in scene["entities"]["letter"]["state"]
    assert not (scene.get("stations") or {}).get("clockwork", {}).get("at")
    assert not (scene.get("stations") or {}).get("crate", {}).get("at")


def test_a_mind_with_no_row_to_tell_is_asked_nothing(story, monkeypatch):
    """One encoder call per mind with a row to tell, and none for a mind
    without: the keeper's stretch failed, waited on another, lay off the map
    or was slept through; the other mind darned socks in the kitchen."""
    t = SPAN["from_s"]
    keeper = [_row(t, t + 3600, "lamp_room", doing="oils the bearings",
                   outcome="failed", reason="no_route"),
              _row(t + 3600, t + 7200, "lamp_room", doing="fits it with Rhona",
                   outcome="not_known"),
              _row(t + 7200, t + 10800, away="the harbour", doing="walks the quay"),
              _row(t + 10800, t + 14400, "lamp_room", doing="sleeps", asleep=True)]
    other = [_row(t, t + 3600, "kitchen", doing="darns socks by the range")]
    minds = {ELIAS: _mind(keeper), NELL: _mind(other, room="kitchen")}
    _ctx, calls = _type(story, monkeypatch, minds, {})
    assert len(calls) == 1
    assert list(calls[0]["payload"]["identity_index"].values()) == [NELL]
    assert minds[ELIAS]["worked"] is None
    assert minds[NELL]["worked"]["told"] == [0]


# --------------------------------------------------------------------------
# The floors
# --------------------------------------------------------------------------

def test_no_body_is_placed_by_a_minds_work(story, monkeypatch):
    """The skip owns where bodies are. Whatever the encoder writes of a body
    -- its room, its pose, its station, a walk, another body carried, shut in
    or handed about -- nothing of it lands: the keeper ends where his own log
    ends, the other mind stands where she stood, and the lamp he lit is lit."""
    t = SPAN["from_s"]
    minds = {ELIAS: _mind([_row(t, t + 3600, "lamp_room",
                                doing="lights the lamp and hauls Nell up the stair")])}
    bodies = [
        _lit(True),
        {"item": ELIAS, "patch": {"positions": {ELIAS: "hall", NELL: "lamp_room"},
                                  "poses": {ELIAS: {"posture": "kneeling"}},
                                  "stations": {ELIAS: {"at": "pedestal"}}}},
        {"item": NELL, "patch": {"containment": {NELL: {"in": "crate", "mode": "inside"}},
                                 "inventory_ops": [{"op": "transfer", "object_id": NELL,
                                                    "from_id": "kitchen", "to_id": ELIAS,
                                                    "relation": "carried"}]}},
        {"item": "the oil can", "patch": {"inventory_ops": [{
            "op": "transfer", "object_id": "clockwork", "from_id": "lamp_room",
            "to_id": NELL, "relation": "held"}]}},
    ]
    ctx, _calls = _type(story, monkeypatch, minds, {"lights the lamp": bodies})
    record = minds[ELIAS]["worked"]["record"]
    assert {"positions", "poses", "stations"} <= set(record["channels_dropped"])
    scene = _commit(ctx)
    assert scene["entities"]["lamp"]["state"]["lit"] is True
    assert scene["positions"][ELIAS] == "lamp_room"
    assert scene["positions"][NELL] == "kitchen"
    assert NELL not in (scene.get("contained") or {})
    assert (scene.get("contained") or {}).get("clockwork") is None
    assert len(record["out_of_reach"]) == 3


def test_a_mind_changes_only_what_it_had_to_hand(story, monkeypatch):
    """A mind's work changes what stood where the row was spent, what it had
    on it, and what its own stretch used -- never a thing in another room it
    never touched, never a thing the world does not hold, and it sets a thing
    down only where the row was spent."""
    t = SPAN["from_s"]
    minds = {ELIAS: _mind([_row(t, t + 3600, "lamp_room", doing="lights the lamp")])}
    writes = [
        _lit(True),
        {"item": "a sealed letter", "patch": {"entities": {"letter": {"state": {"read": True}}}}},
        {"item": "a brass shim", "patch": {"entities": {"shim": {
            "name": "a brass shim", "kind": "part", "portable": True}}}},
        _set_down("clockwork", "the new clockwork", "hall_table"),
    ]
    ctx, _calls = _type(story, monkeypatch, minds, {"lights the lamp": writes})
    assert len(minds[ELIAS]["worked"]["record"]["out_of_reach"]) == 3
    scene = _commit(ctx)
    assert scene["entities"]["lamp"]["state"]["lit"] is True
    assert "read" not in scene["entities"]["letter"]["state"]
    assert "shim" not in scene["entities"]
    assert scene["positions"]["clockwork"] == "lamp_room"
    assert not (scene.get("stations") or {}).get("clockwork", {}).get("at")


def test_an_unheld_transfer_is_still_refused(story, monkeypatch):
    """The beat's own floor holds for a skip's work: the keeper's stretch used
    the oil can, which lay in the kitchen, and a transfer of it from the
    keeper's own hands -- who never held it, standing in the lamp room -- is
    refused (`_refuse_unheld_transfers`) and said, while the rest of what he
    did lands."""
    t = SPAN["from_s"]
    row = _row(t, t + 3600, "lamp_room", doing="oils the lens track and lights the lamp")
    stretch = {"from_s": t, "until_s": t + 3600, "room": "lamp_room", "away": None,
               "where_text": "The Lamp Room", "doing": row["doing"], "asleep": False,
               "with": [], "why": "", "uses": ["the oil can"]}
    minds = {ELIAS: _mind([row], itinerary=[stretch])}
    writes = [_lit(True), _set_down("oil_can", "the oil can", "pedestal", from_id=ELIAS)]
    ctx, _calls = _type(story, monkeypatch, minds, {"lights the lamp": writes},
                        named={ELIAS: {"the oil can": {"oil_can"}}})
    record = minds[ELIAS]["worked"]["record"]
    assert record.get("unheld") and "oil_can" in record["unheld"][0]
    assert not record.get("out_of_reach")
    scene = _commit(ctx)
    assert scene["entities"]["lamp"]["state"]["lit"] is True
    assert scene["positions"]["oil_can"] == "kitchen"
    assert not (scene.get("stations") or {}).get("oil_can", {}).get("at")


@pytest.mark.parametrize("keeper_later", [True, False])
def test_two_minds_on_one_thing_apply_in_the_order_they_worked_it(
        story, monkeypatch, keeper_later):
    """Two minds working one thing apply in time order across minds, by the
    rows' own times, never by whose answer came first: the one who put the
    lamp out and set the clockwork down, and the one who lit it and packed
    the clockwork away, leave the world as whichever of them worked last."""
    t = SPAN["from_s"]
    early, late = (t + 3600, t + 7200), (t + 10800, t + 14400)
    keeper_at, other_at = (late, early) if keeper_later else (early, late)
    minds = {ELIAS: _mind([_row(*keeper_at, "lamp_room", doing="lights the lamp")]),
             NELL: _mind([_row(*other_at, "lamp_room", doing="puts the lamp out")])}
    by_doing = {
        "lights the lamp": [_lit(True), _set_down("clockwork", "the new clockwork", "crate",
                                                  relation="inside")],
        "puts the lamp out": [_lit(False), _set_down("clockwork", "the new clockwork",
                                                     "pedestal")],
    }
    ctx, calls = _type(story, monkeypatch, minds, by_doing)
    assert len(calls) == 2
    scene = _commit(ctx)
    assert scene["entities"]["lamp"]["state"]["lit"] is keeper_later
    packed = ((scene.get("contained") or {}).get("clockwork") or {}).get("in") == "crate"
    assert packed is keeper_later
    on_pedestal = ((scene.get("stations") or {}).get("clockwork") or {}).get("at") == "pedestal"
    assert on_pedestal is not keeper_later
