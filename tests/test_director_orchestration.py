"""Architecture pins for the orchestrated Director (design note 19).

The defect class this file exists to prevent is the one that has cost this
codebase a measurement three times (`entry_ops`, `offscreen_plan_ops`,
`project_ops`): a gating decision becoming a SILENT-DROP surface. Design
note 19 turns `director_resolve` into one step that fans out inside itself
-- dispatch, one prose author, scoped specialists, deterministic assembly --
and every one of those joints is a place where a channel could be dropped
with no warning, a stored turn could stop replaying, or the monolithic
default could quietly drift.

These tests pin the ARCHITECTURE, not the implementation:

- one pipeline step, no new stage keys in `agents/runtime.py`;
- the monolithic path stays the default and stays byte-identical;
- the gate keys on scene state, decided at resolve time, and FAILS OPEN;
- a wrongly-skipped specialist is never silent (the backstop is
  `changes_asserted` reconciliation pointed at the gate, via tell_director);
- a dispatched specialist OWNS its channels; a failed one does not take the
  beat down and leaves the prose author's channels standing;
- the specialist's payload is its written entitlement -- the body slice and
  nothing the Director's omniscience would have handed it;
- both paths emit the same deterministic detector signals (the
  reconciliation manifest), or the experiment's measurement is meaningless.
"""

from __future__ import annotations

import json
import time
import uuid

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData

import agents.director as director


BASE_SCENE = {
    "location": "Blackthorn Lighthouse",
    "time": "night",
    "rooms": {
        "keeper_room": {
            "name": "Keeper's Room",
            "adjacent": [
                {"to": "lamp_room", "barrier": "open", "distance": "near"},
            ],
        },
        "lamp_room": {"name": "Lamp Room", "adjacent": []},
    },
    "positions": {"The Stranger": "keeper_room", "Mara": "keeper_room"},
    "entities": {},
    "attire": {},
    "overlays": {},
}


def _make_ctx(temp_db, *, scene=None, interp=None, player_input="hello"):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    sheet = default_character_data("Mara")
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(),
         f"char_mara_{uuid.uuid4().hex[:8]}"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene",
                 json.loads(json.dumps(scene or BASE_SCENE)))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, player_input, time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input=player_input, created=time.time()),
        cast=cast, input=player_input,
    )
    ctx.director_interpret = interp or _speech_interp()
    return ctx


def _speech_interp():
    """A pure-dialogue beat: no action, no movement, no dice."""
    return {
        "sequence": [{"type": "speech", "text": "Quiet night.",
                      "volume": "normal", "visibility": "overt",
                      "conceal_from": []}],
        "speech": "Quiet night.", "action": None, "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }


def _action_interp():
    """A physical beat: one declared action attempt."""
    return {
        "sequence": [{"type": "action", "attempt": "pull off my wool coat",
                      "commitment": "asserted", "targets": [],
                      "visibility": "overt", "conceal_from": []}],
        "speech": None, "action": {"attempt": "pull off my wool coat"},
        "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }


def _fake_agent(calls, responses):
    """A `_agent_json` stand-in that answers per step_key and records every
    call, so a test can assert who was called, in what role, with what."""
    def fake(role, step_key, system, payload, **kw):
        calls.append({"role": role, "step_key": step_key,
                      "system": system, "payload": payload})
        value = responses.get(step_key, {})
        if isinstance(value, Exception):
            raise value
        if callable(value):
            value = value(payload)
        return json.loads(json.dumps(value))
    return fake


def _steps(calls):
    return [c["step_key"] for c in calls]


def _orch_on(temp_db):
    temp_db.set_setting("director_orchestration", "1")


# ---------------------------------------------------------------------------
# The flag, and the monolithic default.
# ---------------------------------------------------------------------------

def test_flag_off_is_the_monolithic_path_unchanged(temp_db, monkeypatch):
    """Requirement 7: feature-flagged and reversible, monolith the DEFAULT.
    With the setting absent, exactly one resolve call is made, with the full
    (unsplit) instruction sheet, and the output carries no orchestration
    record -- so stored turns and payload shapes are byte-compatible with
    every pre-orchestration variant."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert _steps(calls) == ["director_resolve"]
    assert "CLOTHING TRACKING" in calls[0]["system"]
    assert "BODY CHANNELS ARE DELEGATED" not in calls[0]["system"]
    # The schema dump supplies the declared default (the routed_to_background
    # pattern); a monolithic resolve must never claim an orchestrated one.
    assert not out.get("orchestration")


def test_monolithic_prompt_is_intact_and_lean_sheet_is_carved():
    """The prompt split must be a recomposition, not a rewrite: the full
    resolve sheet keeps every delegated block, and the lean sheet drops
    exactly the delegated machinery (delegation note in their place) while
    keeping everything the prose author still owns."""
    from prompts import DEFAULT_PROMPTS

    full = DEFAULT_PROMPTS["director_resolve"]
    lean = DEFAULT_PROMPTS["director_resolve_lean"]

    delegated_markers = (
        "CLOTHING TRACKING", "BODILY CONDITION",          # body
        "CAST CHANGES", "INTRODUCTIONS",                  # social
        "BODY POSITION — WHO IS IN CONTACT WITH WHOM",    # contact
        "MATERIAL TRANSFER", "BEING CARRIED — CONTAINMENT",
        "INVENTORY:", "NOTICES:", "DESTRUCTION — MANDATORY",  # objects
        "WITHIN-ROOM POSITION", "BODY POSE",              # spatial
        "ROOM CREATION", "RUNNING COVERS GROUND",
        "CROWDS:", "COURIERS:", "PASSING ON WHAT",        # offscreen
        "OFF-SCREEN REACTIVE PLANS", "UNRATIFIED CLAIMS",
    )
    for marker in delegated_markers:
        assert marker in full, marker
        assert marker not in lean, marker
    assert "DELEGATED CHANNELS" in lean
    assert "DELEGATED CHANNELS" not in full
    # The lean sheet still owns everything outside the delegated channels.
    for marker in ("WORLD PRESSURE", "APPROACHING IS NOT ARRIVING",
                   "SIZE CHANGES WHAT IS POSSIBLE",
                   "WHAT LIGHT LETS THEM DO", "DESTINATION RESIDUE",
                   "AUTHORITY APPRAISAL", "CONSEQUENCES ON THE CLOCK",
                   "CHANGES MANIFEST"):
        assert marker in lean, marker


def test_specialist_sheets_are_assembled_from_scope():
    """The chunked-prompt contract (design note 19, hierarchical gating):
    a specialist's sheet is core + one chunk per GRANTED channel and
    nothing else -- scope selects chunks, no other selection logic. An
    unchunked prompt would load everything on every beat while appearing
    scoped, which is why tools/project_check.py enforces the structure;
    this pins the assembly itself."""
    from prompts import SPECIALIST_PROMPT_SPECS, specialist_prompt

    attire_only = specialist_prompt("body", ["attire"])
    assert "CLOTHING TRACKING" in attire_only
    assert "BODILY CONDITION" not in attire_only
    assert "AWARENESS" not in attire_only
    everything = specialist_prompt(
        "body", ["attire", "conditions", "vitals", "overlays"])
    assert "BODILY CONDITION" in everything and "OVERLAYS" in everything
    # Empty scope is the bare core -- and dispatch never sends it (an empty
    # scope is a specialist not dispatched at all).
    assert specialist_prompt("body", []) == \
        SPECIALIST_PROMPT_SPECS["body"]["core"]
    # Canonical order: the sheet is byte-stable for a given scope whatever
    # order the scope list arrives in (provider prefix caching).
    assert specialist_prompt("contact", ["scales", "contact_ops"]) == \
        specialist_prompt("contact", ["contact_ops", "scales"])


def test_orchestration_adds_no_stage_keys_to_runtime():
    """Requirement 4: one step per Director stage, fan-out INSIDE. The
    runtime must need no new stage keys -- that is what keeps reroll,
    rerun-from-stage and every stored turn's replay untouched."""
    from agents import runtime

    assert "director_resolve" in runtime.STEP_HANDLERS
    assert not any("body" in key for key in runtime.STEP_HANDLERS)


def test_orchestration_record_survives_the_schema_round_trip():
    """The dispatch record is engine-authored step metadata. If the schema
    dump dropped it (the `routed_to_background` lesson), the persisted
    variant would claim a monolithic resolve for an orchestrated one and no
    stored turn could ever be audited for gate mispredictions."""
    from schemas import validate_llm_output

    out, _ = validate_llm_output("director_resolve", {
        "resolved_event": "x",
        "orchestration": {"enabled": True,
                          "specialists": {"body": {"run": True}}},
    })
    assert out["orchestration"]["specialists"]["body"]["run"] is True

    # And a pre-orchestration variant (no record) still validates unchanged.
    old, _ = validate_llm_output("director_resolve", {"resolved_event": "x"})
    assert old["orchestration"] == {}


# ---------------------------------------------------------------------------
# The gate: scene-state keyed, resolve-time, fails open.
# ---------------------------------------------------------------------------

def test_gate_fails_open_on_any_physical_beat(temp_db, monkeypatch):
    """Requirement 1. A bare-bodied cast with no active conditions is NOT
    evidence the body channels are out of play: a physical beat can wound a
    body that wears nothing. Where structure cannot decide, the specialist
    runs -- the saving comes from beats whose subjects cannot change, not
    from predicting cleverly."""
    _orch_on(temp_db)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert "director_body" in _steps(calls)
    body = out["orchestration"]["specialists"]["body"]
    assert body["run"] is True and body["ran"] is True


def test_gate_skips_a_pure_dialogue_beat_over_clean_bodies(temp_db,
                                                           monkeypatch):
    """The gate's skip direction, exercised: no declared action anywhere, no
    dice, no active condition, no overlay -- nothing the body channels
    govern can change, so the specialist is never called and costs nothing
    at all. Note the scene HAS attire: a worn coat is a fact, but a beat
    with no physical act cannot move it, so wearing alone must not fire."""
    _orch_on(temp_db)
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))

    ctx = _make_ctx(temp_db, scene=scene, interp=_speech_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert "director_body" not in _steps(calls)
    body = out["orchestration"]["specialists"]["body"]
    assert body["run"] is False
    assert body["facts"]["anyone_wears"] is True  # recorded, not load-bearing


def test_gate_keys_on_scene_state_at_resolve_time(temp_db, monkeypatch):
    """Requirements 1 and 3 together. An ACTIVE condition is standing scene
    state that needs maintaining even on a still beat, so it fires the gate
    with no physical activity at all -- and it is read from the ledger at
    RESOLVE time, not from any plan fixed earlier: this row is inserted
    after the interpretation already exists, the way a mid-turn character
    declaration brings channels into play nothing earlier predicted."""
    _orch_on(temp_db)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))

    ctx = _make_ctx(temp_db, interp=_speech_interp())
    # After interpret, before resolve: a condition lands on the ledger.
    temp_db.qi(
        "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
        "started_at,payload,active) VALUES(?,?,?,?,?,?,1)",
        ("mara_burn", ctx.chat.id, "Mara", "wound", 0.0,
         json.dumps({"subject_id": "Mara", "state": {"detail": "burn"}})),
    )
    out = director.director_resolve(ctx, nonce=0)

    assert "director_body" in _steps(calls)
    assert out["orchestration"]["specialists"]["body"]["facts"][
        "active_conditions"] is True


def test_backstop_reports_a_wrongly_skipped_specialist(temp_db, monkeypatch):
    """Requirement 2, the load-bearing one: A WRONGLY-SKIPPED SPECIALIST
    MUST NEVER BE SILENT. The gate skips (pure dialogue, clean bodies), yet
    the resolved prose asserts an attire change -- the exact silent-drop
    shape that cost entry_ops, offscreen_plan_ops and project_ops their
    measurements. The backstop must (a) say so via tell_director, and (b)
    drop NOTHING: the prose author's own encoding stands, because the gate
    fails open rather than enforcing its own prediction."""
    _orch_on(temp_db)
    calls = []
    resolve_out = {
        "resolved_event": "Mara shrugs the wool coat off her shoulders "
                          "and lets it fall.",
        "summary": "Mara sheds her coat.",
        "changes_asserted": [
            {"category": "attire", "subject": "Mara",
             "change": "The wool coat is off."},
        ],
        "state_diff": {"attire": {"Mara": {"remove": ["wool coat"]}}},
    }
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {"director_resolve": resolve_out}))

    ctx = _make_ctx(temp_db, scene=scene, interp=_speech_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert "director_body" not in _steps(calls)
    # Fail-open: the author's channel content shipped untouched.
    assert out["state_diff"]["attire"]["Mara"]["remove"] == ["wool coat"]
    # And the gate misprediction is REPORTED, on both surfaces.
    gate_notes = [n for n in ctx.engine_feedback
                  if "orchestration gate" in n]
    assert gate_notes and "attire" in gate_notes[0]
    assert any("orchestration gate" in w for w in ctx.warnings)
    assert out["orchestration"].get("gate_flags")


# ---------------------------------------------------------------------------
# Ownership, failure isolation, entitlement.
# ---------------------------------------------------------------------------

def test_dispatched_specialist_owns_its_channels(temp_db, monkeypatch):
    """One owner per channel is the join argument: prose and structure are
    never authored by blind peers, and when the prose author emits a body
    channel despite the delegation, the specialist -- which read the
    finished prose -- wins. Everything outside the four channels stays the
    author's untouched."""
    _orch_on(temp_db)
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "Mara pulls off her wool coat and drops it "
                              "by the door.",
            "summary": "Coat comes off.",
            "state_diff": {
                # Mis-emitted despite the delegation -- must lose.
                "attire": {"Mara": {"state": ["coat loosened"]}},
                # Mis-emitted too, now that geography is delegated -- the
                # spatial specialist (answering empty) must win here as well.
                "poses": {"Mara": {"posture": "standing"}},
                # NOT a delegated channel -- must survive assembly untouched.
                "consequences": [{"what": "the coat lies by the door",
                                  "where": "keeper_room",
                                  "due_seconds": 3600}],
            },
        },
        "director_body": {
            "attire": {"Mara": {"remove": ["wool coat"]}},
            "conditions": {}, "vitals": {}, "overlays": {}, "notes": [],
        },
    }
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    attire = out["state_diff"]["attire"]["Mara"]
    assert attire["remove"] == ["wool coat"]
    assert not attire.get("state")
    # The un-delegated channel survives; the mis-emitted spatial channel
    # was replaced by its owner (who asserted no pose change).
    assert out["state_diff"]["consequences"]
    assert not out["state_diff"]["poses"]
    body = out["orchestration"]["specialists"]["body"]
    assert "attire" in body["channels_replaced"]
    spatial = out["orchestration"]["specialists"]["spatial"]
    assert "poses" in spatial["channels_replaced"]
    assert any("ownership" in w for w in ctx.warnings)


def test_specialist_failure_never_takes_the_beat_down(temp_db, monkeypatch):
    """A specialist is an optimization, not a dependency: if its call dies,
    the beat completes, the prose author's own body channels stand
    (fail-open), and the failure is reported through the same gate backstop
    that reports a wrong skip -- an absent owner is never silent, whatever
    made it absent."""
    _orch_on(temp_db)
    calls = []

    def failing(payload):
        raise RuntimeError("provider 500")

    responses = {
        "director_resolve": {
            "resolved_event": "Mara pulls off her wool coat.",
            "summary": "Coat off.",
            "changes_asserted": [
                {"category": "attire", "subject": "Mara",
                 "change": "The wool coat is off."},
            ],
            "state_diff": {"attire": {"Mara": {"remove": ["wool coat"]}}},
        },
        "director_body": failing,
    }
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["attire"]["Mara"]["remove"] == ["wool coat"]
    body = out["orchestration"]["specialists"]["body"]
    assert body["run"] is True and body["ran"] is False
    assert "provider 500" in body["error"]
    assert any("fail-open" in w for w in ctx.warnings)
    assert any("orchestration gate" in n for n in ctx.engine_feedback)


def test_specialist_payload_is_the_body_slice_and_nothing_more(temp_db,
                                                              monkeypatch):
    """Requirement 5: an explicit entitlement, enforced. The Director's
    omniscience is justified by owning objective causality; the body
    specialist does not inherit it. Its payload must carry the body ledgers
    and the finished beat -- and none of the world machinery, no room graph,
    and never the player's raw input (which can carry a private thought the
    Director alone is entitled to read)."""
    _orch_on(temp_db)
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "Mara pulls off her wool coat.",
            "summary": "Coat off.", "state_diff": {},
        },
        "director_body": {"attire": {}, "conditions": {}, "vitals": {},
                          "overlays": {}, "notes": []},
    }
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp(),
                    player_input="(I secretly hate this coat) I pull it off")
    director.director_resolve(ctx, nonce=0)

    spayload = next(c["payload"] for c in calls
                    if c["step_key"] == "director_body")
    # Its entitlement:
    assert spayload["resolved_event"]
    assert "attire" in spayload and "overlays" in spayload
    assert "active_awareness" in spayload and "simulation_clock" in spayload
    assert spayload["declared_actions"]  # structured attempts, not prose
    # The room index is ids -> display names only -- no graph, no bodies.
    assert spayload["rooms"] == {"keeper_room": "Keeper's Room",
                                 "lamp_room": "Lamp Room"}
    # And nothing the Director's omniscience would have handed it:
    for forbidden in ("relevant_lore", "crowds", "couriers", "notices",
                      "world_pressure", "pending_obligations",
                      "offscreen_planning", "social_standing",
                      "carried_reports", "standing_intentions", "scene",
                      "positions", "player_declaration", "paradox",
                      "unratified_claims", "background_presence_knowledge"):
        assert forbidden not in spayload, forbidden
    flat = json.dumps(spayload)
    assert "secretly hate" not in flat  # the raw input never reaches it


def test_specialist_role_is_separable_and_inherits_the_director_model(
        monkeypatch):
    """Measurement hook: `_log_usage` keys on the role string, so the
    specialist must call under its OWN role name -- and a host that never
    configured `director_body` must get the director's model serving it,
    not a generic default that would silently change what serves the most
    failure-prone stage."""
    import providers

    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "cheap", "model": "small"},
        "director": {"provider": "frontier", "model": "big"},
    })
    monkeypatch.setattr(providers, "provider",
                        lambda name: {"name": name, "kind": "openai",
                                      "base_url": "http://x", "api_key": ""})

    prov, model, cfg = providers.resolve_role("director_body")
    assert (prov["name"], model) == ("frontier", "big")
    # Explicit configuration still wins over the inheritance.
    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "cheap", "model": "small"},
        "director": {"provider": "frontier", "model": "big"},
        "director_body": {"provider": "cheap", "model": "lean"},
    })
    prov, model, cfg = providers.resolve_role("director_body")
    assert (prov["name"], model) == ("cheap", "lean")


def test_specialist_call_carries_its_own_role(temp_db, monkeypatch):
    """The other half of the measurement hook: the resolve stage must hand
    `_agent_json` the specialist's role string, or every specialist call is
    logged as director spend and the experiment cannot be judged."""
    _orch_on(temp_db)
    calls = []
    responses = {"director_body": {"attire": {}, "conditions": {},
                                   "vitals": {}, "overlays": {}, "notes": []}}
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    director.director_resolve(ctx, nonce=0)

    body_calls = [c for c in calls if c["step_key"] == "director_body"]
    assert body_calls and body_calls[0]["role"] == "director_body"


# ---------------------------------------------------------------------------
# Detector parity: both paths must trip the same deterministic detectors.
# ---------------------------------------------------------------------------

def _asserting_resolve_output():
    """A resolve whose prose+manifest assert an attire change that the diff
    does not encode -- the canonical reconciliation-omission shape."""
    return {
        "resolved_event": "Mara shrugs the wool coat off and lets it fall.",
        "summary": "Coat off.",
        "changes_asserted": [
            {"category": "attire", "subject": "Mara",
             "change": "The wool coat is off."},
        ],
        "state_diff": {},
    }


def _manifest_omissions(out):
    return [o for o in (out.get("reconciliation") or {}).get("omissions", [])
            if o.get("source") == "manifest"]


def test_orchestrated_path_emits_the_same_detector_signals(temp_db,
                                                           monkeypatch):
    """Measurement hook: success is judged by the EXISTING deterministic
    detectors, so the orchestrated path must trip them identically or the
    comparison is meaningless. Here the beat asserts an attire change that
    nobody encodes (monolith leaves the diff empty; specialist answers
    empty): both paths must surface the same manifest omission through the
    same reconciliation record."""
    calls_mono = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls_mono, {
            "director_resolve": _asserting_resolve_output(),
            "resolve_repair": {"state_diff": {}, "dispositions": []},
        }))
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    ctx_mono = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out_mono = director.director_resolve(ctx_mono, nonce=0)

    _orch_on(temp_db)
    calls_orch = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls_orch, {
            "director_resolve": _asserting_resolve_output(),
            "director_body": {"attire": {}, "conditions": {}, "vitals": {},
                              "overlays": {}, "notes": []},
            "resolve_repair": {"state_diff": {}, "dispositions": []},
        }))
    ctx_orch = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out_orch = director.director_resolve(ctx_orch, nonce=0)

    mono = _manifest_omissions(out_mono)
    orch = _manifest_omissions(out_orch)
    assert mono and orch and mono == orch
    # Both paths escalated to the same bounded self-repair.
    assert "resolve_repair" in _steps(calls_mono)
    assert "resolve_repair" in _steps(calls_orch)
    # And both left the same unresolved warning trail.
    assert any("Resolve reconciliation" in w and "wool coat" in w
               for w in ctx_mono.warnings)
    assert any("Resolve reconciliation" in w and "wool coat" in w
               for w in ctx_orch.warnings)


# ---------------------------------------------------------------------------
# Scope: the orchestrator measures how much of a job a specialist needs.
# ---------------------------------------------------------------------------

def test_scope_selects_the_sheet_and_is_persisted(temp_db, monkeypatch):
    """Dispatch is `bool(scope)` and the sheet is assembled from exactly
    the granted channels' chunks -- one computation, one code path, so the
    "which specialists run" gate and the "how much sheet loads" gate can
    never disagree. The granted/served/produced report persists on the
    step, because over-grant is the number that says how well scoping
    works and under-grant is the direction the backstop catches."""
    _orch_on(temp_db)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))

    # Physical beat, someone wears something, no conditions, no vitals
    # tracking: body's scope must be attire+conditions+overlays (conditions
    # and overlays fail open on any physical beat; vitals is gated out by
    # the tracked-subject fact).
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    body = out["orchestration"]["specialists"]["body"]
    assert body["scope"] == ["attire", "conditions", "overlays"]
    body_sheet = next(c["system"] for c in calls
                      if c["step_key"] == "director_body")
    assert "CLOTHING TRACKING" in body_sheet
    assert "BODILY CONDITION" not in body_sheet  # vitals chunk not loaded
    report = out["orchestration"]["scope_report"]
    assert set(report["granted"]) >= {"attire", "conditions", "overlays"}
    assert report["served"] == report["granted"]  # every specialist answered
    assert report["produced"] == []               # and asserted no change


def test_scope_gates_out_channels_whose_subject_does_not_exist(temp_db,
                                                               monkeypatch):
    """The saving comes from channels whose subject provably does not
    exist, never from prediction: bare bodies gate out the wardrobe chunk,
    no tracked vitals gate out the reserves chunk, nothing destructible
    gates out the destruction chunk, no notice and nothing carried gate
    out the notices chunk -- while the undecidable channels stay in scope
    (fail open) on the same physical beat."""
    _orch_on(temp_db)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))

    ctx = _make_ctx(temp_db, interp=_action_interp())  # bare-bodied scene
    out = director.director_resolve(ctx, nonce=0)

    specialists = out["orchestration"]["specialists"]
    assert "attire" not in specialists["body"]["scope"]
    assert "conditions" in specialists["body"]["scope"]
    objects = specialists["objects"]
    assert "destruction" not in objects["scope"]
    assert "artifact_ops" not in objects["scope"]
    assert "entities" in objects["scope"]
    contact = specialists["contact"]
    assert set(contact["scope"]) >= {"contact_ops", "substance_ops",
                                     "containment", "scales"}


def test_specialist_notes_reach_tell_director(temp_db, monkeypatch):
    """The note lane is how out-of-scope work is reported: a specialist
    that found a change it had no channel for says so, and the engine
    carries the flag to the next beat's Director rather than letting the
    under-grant vanish into a log nobody reads."""
    _orch_on(temp_db)
    calls = []
    responses = {
        "director_body": {"attire": {}, "conditions": {}, "vitals": {},
                          "overlays": {},
                          "notes": ["the prose asserts Mara's reserves "
                                    "dropped but I had no block for it"]},
    }
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert any("reserves" in n for n in ctx.engine_feedback)
    assert out["orchestration"]["specialists"]["body"]["notes"]


# ---------------------------------------------------------------------------
# The specialists are SHARED between interpret and resolve.
# ---------------------------------------------------------------------------

def test_interpret_dispatches_the_same_specialists(temp_db, monkeypatch):
    """The constraint above all others: interpret and resolve stay
    equivalent in capability -- interpret is the same authority scoped to
    the player's input (the alpha-8.1 fix), so an orchestration that gave
    resolve specialists and interpret none would rebuild the asymmetry by
    construction. The SAME specialist definition serves both stages: at
    interpret it is called with source 'player_declaration', reads the
    declaration rather than resolved prose, and its channels merge into
    state_assertions BEFORE the deterministic validators."""
    _orch_on(temp_db)
    calls = []
    interpret_out = {
        "kind": "action",
        "sequence": [{"type": "action", "attempt": "pull off my wool coat",
                      "commitment": "asserted", "targets": [],
                      "raw_text": "I pull off my wool coat"}],
        "speech": None, "action": {"attempt": "pull off my wool coat"},
        "movement": None,
        # The interpret model mis-emits the delegated channel despite the
        # delegation -- the specialist, which read the same declaration,
        # must win (ownership).
        "state_assertions": {"attire": {"Mara": {"state": ["loosened"]}}},
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    responses = {
        "director_interpret": interpret_out,
        "director_body": {
            "attire": {"The Stranger": {"remove": ["wool coat"]}},
            "conditions": {}, "vitals": {}, "overlays": {}, "notes": [],
        },
    }
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"The Stranger": {"wearing": ["wool coat"]},
                       "Mara": {"wearing": ["shift"]}}
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, scene=scene,
                    player_input="I pull off my wool coat")
    ctx.director_interpret = None
    out = director.director_interpret(ctx, nonce=0)

    body_calls = [c for c in calls if c["step_key"] == "director_body"]
    assert body_calls, "interpret must dispatch the shared body specialist"
    spayload = body_calls[0]["payload"]
    assert spayload["source"] == "player_declaration"
    assert "player_declaration" in spayload
    assert "resolved_event" not in spayload
    # Ownership: the specialist's channel replaced the interpret model's.
    assert out["state_assertions"]["attire"]["The Stranger"]["remove"] == \
        ["wool coat"]
    assert out["orchestration"]["stage"] == "interpret"


def test_interpret_specialist_never_sees_the_raw_input(temp_db, monkeypatch):
    """The X19 lesson, applied to the new fan-out: the raw player input can
    carry a private thought only the interpreting Director is entitled to
    read. The specialist gets the STRUCTURED declaration -- never
    `ctx.input`, never `private_thought`."""
    _orch_on(temp_db)
    calls = []
    interpret_out = {
        "kind": "action",
        "sequence": [{"type": "action", "attempt": "pull off my coat",
                      "commitment": "asserted", "targets": []}],
        "speech": None, "action": {"attempt": "pull off my coat"},
        "movement": None, "private_thought": "I secretly hate this coat",
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"The Stranger": {"wearing": ["coat"]}}
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, {"director_interpret":
                                            interpret_out}))

    ctx = _make_ctx(
        temp_db, scene=scene,
        player_input="(I secretly hate this coat) I pull off my coat")
    ctx.director_interpret = None
    director.director_interpret(ctx, nonce=0)

    for call in calls:
        if call["step_key"].startswith("director_") \
                and call["step_key"] not in ("director_interpret",):
            flat = json.dumps(call["payload"])
            assert "secretly hate" not in flat, call["step_key"]


# ---------------------------------------------------------------------------
# The other specialists: ownership and entitlement, one test each.
# ---------------------------------------------------------------------------

def test_social_specialist_owns_the_roster_channels(temp_db, monkeypatch):
    _orch_on(temp_db)
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "Mara gives her name at last.",
            "summary": "Names exchanged.",
            "state_diff": {},
        },
        "director_social": {
            "cast_changes": [],
            "introductions": [{"who": "The Stranger", "learns": "Mara"}],
            "world_facts": [], "notes": [],
        },
    }
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, interp=_speech_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["introductions"] == [
        {"who": "The Stranger", "learns": "Mara"}]
    social = out["orchestration"]["specialists"]["social"]
    assert social["ran"] is True
    assert "introductions" in social["scope"]
    # Entitlement: the roster and the beat, nothing more.
    spayload = next(c["payload"] for c in calls
                    if c["step_key"] == "director_social")
    for forbidden in ("attire", "contacts", "entities", "rooms",
                      "relevant_lore", "world_pressure", "vitals"):
        assert forbidden not in spayload, forbidden
    assert "background_presences" in spayload


def test_contact_specialist_owns_the_relation_channels(temp_db, monkeypatch):
    _orch_on(temp_db)
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "Mara rests her hand on the Stranger's "
                              "shoulder.",
            "summary": "A hand on a shoulder.",
            "state_diff": {},
        },
        "director_contact": {
            "contact_ops": [{"op": "add", "actor": "Mara",
                             "actor_part": "hand",
                             "target": "The Stranger",
                             "target_part": "shoulder", "manner": "rest",
                             "relation": "surface", "motion": "settled"}],
            "substance_ops": [], "containment": {}, "scales": {},
            "notes": [],
        },
    }
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    ops = out["state_diff"]["contact_ops"]
    assert any(op.get("actor") == "Mara"
               and op.get("target_part") == "shoulder" for op in ops)
    # Entitlement: its own ledgers plus name indexes -- no wardrobe, no
    # lore, no minds, no world machinery.
    spayload = next(c["payload"] for c in calls
                    if c["step_key"] == "director_contact")
    assert "contacts" in spayload and "contained" in spayload
    assert "scales" in spayload and "entity_names" in spayload
    for forbidden in ("attire", "overlays", "relevant_lore",
                      "world_pressure", "notices", "vitals",
                      "active_awareness"):
        assert forbidden not in spayload, forbidden


def test_objects_specialist_owns_the_object_channels(temp_db, monkeypatch):
    _orch_on(temp_db)
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "Mara lights the storm lantern.",
            "summary": "Lantern lit.",
            "state_diff": {
                # Mis-emitted despite the delegation -- must lose to the
                # specialist's channel.
                "entities": {"storm_lantern": {"name": "Storm Lantern",
                                               "state": {"lit": False}}},
            },
        },
        "director_objects": {
            "entities": {"storm_lantern": {"name": "Storm Lantern",
                                           "kind": "object",
                                           "state": {"lit": True}}},
            "remove_entities": [], "inventory_ops": [], "artifact_ops": [],
            "destruction": None, "notes": [],
        },
    }
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["entities"]["storm_lantern"]["state"]["lit"] \
        is True
    objects = out["orchestration"]["specialists"]["objects"]
    assert "entities" in objects["channels_replaced"]
    spayload = next(c["payload"] for c in calls
                    if c["step_key"] == "director_objects")
    assert "entities" in spayload and "notices" in spayload
    for forbidden in ("attire", "contacts", "relevant_lore",
                      "world_pressure", "active_awareness", "vitals"):
        assert forbidden not in spayload, forbidden


def test_spatial_specialist_proposes_and_the_backstop_disposes(temp_db,
                                                               monkeypatch):
    """The spatial carve's one non-negotiable: the movement backstop STAYS
    WITH THE ORCHESTRATOR, judging the MERGED diff -- it cannot be seen
    from inside the channel. A specialist-asserted legal character move
    commits; a specialist-asserted move of the declared mover into a room
    with no passable route is STRIPPED by the same deterministic check
    that strips a monolithic Director's, with the same warning. The
    specialist proposes; physics disposes."""
    _orch_on(temp_db)
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["rooms"]["cliff_path"] = {"name": "Cliff Path", "adjacent": []}
    calls = []
    interp = _action_interp()
    # The player declares movement to a DISCONNECTED room...
    interp["movement"] = {"to_room": "cliff_path", "mover": "self"}
    responses = {
        "director_resolve": {
            "resolved_event": "Mara crosses into the lamp room; the "
                              "Stranger makes for the cliff path.",
            "summary": "Movement.",
            "state_diff": {},
        },
        "director_spatial": {
            # ...and the specialist wrongly asserts the impossible arrival,
            # alongside a legal move for Mara.
            "positions": {
                "Mara": "lamp_room",           # legal: open adjacency
                "The Stranger": "cliff_path",  # illegal: no route exists
            },
            "rooms": {}, "remove_rooms": [], "remove_adjacent": [],
            "stations": {"Mara": {"at": None, "near": ["The Stranger"]}},
            "poses": {}, "notes": [],
        },
    }
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, scene=scene, interp=interp)
    out = director.director_resolve(ctx, nonce=0)

    positions = out["state_diff"]["positions"]
    assert positions.get("Mara") == "lamp_room"
    # The backstop stripped the specialist's impossible move of the mover.
    assert "The Stranger" not in positions
    assert any("Blocked movement" in w for w in ctx.warnings)
    # Entitlement: the graph's keeper sees the graph -- and only its own
    # ledgers beside it.
    spayload = next(c["payload"] for c in calls
                    if c["step_key"] == "director_spatial")
    assert "rooms" in spayload and "positions" in spayload
    assert "movers" in spayload and "movement" in spayload
    for forbidden in ("attire", "contacts", "relevant_lore", "notices",
                      "world_pressure", "active_awareness", "vitals",
                      "crowds", "couriers"):
        assert forbidden not in spayload, forbidden


def test_offscreen_is_genuinely_dispatchable(temp_db, monkeypatch):
    """The offscreen carve is a PROMPT operation: the simulator stays
    unbuilt, but the specialist must be genuinely dispatchable -- cold in
    practice only because most scenes contain no crowds, couriers, carried
    reports or hearsay. With a crowd standing in a scene room it must
    dispatch, and its ops must survive assembly into state_diff, or
    "accessible" is a claim nothing checks."""
    _orch_on(temp_db)
    scene = json.loads(json.dumps(BASE_SCENE))
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "The Stranger pushes through the crowd of "
                              "keepers gathered in the lamp room.",
            "summary": "Through the crowd.",
            "state_diff": {},
        },
        "director_offscreen": {
            "crowd_ops": [{"op": "move", "crowd_id": "crowd_1",
                           "room": "lamp_room", "heading": "keeper_room"}],
            "courier_ops": [], "telling_ops": [], "offscreen_plan_ops": [],
            "ratified_claims": [], "contradicted_claims": [], "notes": [],
        },
    }
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    temp_db.wset(ctx.chat.id, "crowds", [
        {"uid": "crowd_1", "room_uid": "lamp_room", "band": "a dozen or so",
         "composition": "keepers", "mood": "restless"},
    ])
    out = director.director_resolve(ctx, nonce=0)

    offscreen = out["orchestration"]["specialists"]["offscreen"]
    assert offscreen["run"] is True and offscreen["ran"] is True
    assert "crowd_ops" in offscreen["scope"]
    assert out["state_diff"]["crowd_ops"] == [
        {"op": "move", "crowd_id": "crowd_1", "room": "lamp_room",
         "heading": "keeper_room"}]
    # Its entitlement is the traffic ledgers -- with the uid its ops need.
    spayload = next(c["payload"] for c in calls
                    if c["step_key"] == "director_offscreen")
    assert spayload["crowds"] and spayload["crowds"][0]["crowd_id"] == \
        "crowd_1"
    for forbidden in ("attire", "contacts", "entities", "relevant_lore",
                      "world_pressure", "active_awareness", "movers"):
        assert forbidden not in spayload, forbidden


def test_offscreen_is_cold_when_its_subjects_are_absent(temp_db,
                                                        monkeypatch):
    """The other direction of the same fact: an ordinary indoor beat with
    no crowds, no couriers, nothing carried, no hearsay and the planning
    floor off never dispatches the traffic specialist -- which is the
    entire saving of the coldest carve (0 fires in 2,243 beats)."""
    _orch_on(temp_db)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert "director_offscreen" not in _steps(calls)
    offscreen = out["orchestration"]["specialists"]["offscreen"]
    assert offscreen["run"] is False and offscreen["scope"] == []


# ---------------------------------------------------------------------------
# Parallelism: canonical assembly, failure isolation, cancellation, silence.
# ---------------------------------------------------------------------------

def _fake_agent_with_delays(calls, responses, delays):
    """Like _fake_agent, but each step sleeps its configured delay first --
    so completion order inverts submission order and a merge that read
    completion order would produce a different result."""
    import threading
    import time as _time
    lock = threading.Lock()

    def fake(role, step_key, system, payload, **kw):
        _time.sleep(delays.get(step_key, 0.0))
        with lock:
            calls.append({"role": role, "step_key": step_key,
                          "system": system, "payload": payload,
                          "done_at": _time.monotonic()})
        value = responses.get(step_key, {})
        if isinstance(value, Exception):
            raise value
        if callable(value):
            value = value(payload)
        return json.loads(json.dumps(value))
    return fake


def test_parallel_specialists_assemble_in_canonical_order(temp_db,
                                                          monkeypatch):
    """Requirement: DETERMINISTIC ASSEMBLY ORDER. The calls run
    concurrently and the delays force completion order to invert canonical
    order -- the merged diff and the per-specialist records must come out
    identical to a sequential run, or reroll and replay stop being
    reproducible and every later comparison is noise."""
    _orch_on(temp_db)
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    responses = {
        "director_resolve": {
            "resolved_event": "Mara sheds her coat and rests a hand on "
                              "the Stranger's shoulder.",
            "summary": "Coat off; a hand rests.", "state_diff": {},
        },
        "director_body": {
            "attire": {"Mara": {"remove": ["wool coat"]}},
            "conditions": {}, "vitals": {}, "overlays": {}, "notes": [],
        },
        "director_contact": {
            "contact_ops": [{"op": "add", "actor": "Mara",
                             "actor_part": "hand",
                             "target": "The Stranger",
                             "target_part": "shoulder", "manner": "rest",
                             "relation": "surface", "motion": "settled"}],
            "substance_ops": [], "containment": {}, "scales": {},
            "notes": [],
        },
    }
    # body (canonically first) finishes LAST; contact finishes first.
    delays = {"director_body": 0.20, "director_contact": 0.0,
              "director_social": 0.05, "director_objects": 0.05,
              "director_spatial": 0.05}
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent_with_delays(calls, responses, delays))

    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    # Completion order really was inverted...
    spec_calls = [c for c in calls if c["step_key"] != "director_resolve"]
    finished = sorted(spec_calls, key=lambda c: c["done_at"])
    assert finished[0]["step_key"] == "director_contact"
    assert finished[-1]["step_key"] == "director_body"
    # ...and the merge is what a sequential run produces.
    assert out["state_diff"]["attire"]["Mara"]["remove"] == ["wool coat"]
    assert out["state_diff"]["contact_ops"][0]["target_part"] == "shoulder"
    report = out["orchestration"]["scope_report"]
    assert report["served"] == report["granted"]


def test_parallel_failures_are_isolated_even_two_at_once(temp_db,
                                                         monkeypatch):
    """Requirement: FAILURE ISOLATION SURVIVES CONCURRENCY. Two specialists
    failing at once must cost exactly their own channels: the survivors'
    completed work merges, each failure is recorded on its own specialist,
    and the beat completes."""
    _orch_on(temp_db)
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    responses = {
        "director_resolve": {
            "resolved_event": "Mara sheds her coat.",
            "summary": "Coat off.", "state_diff": {},
        },
        "director_body": {
            "attire": {"Mara": {"remove": ["wool coat"]}},
            "conditions": {}, "vitals": {}, "overlays": {}, "notes": [],
        },
        "director_contact": RuntimeError("provider 500"),
        "director_spatial": RuntimeError("timeout"),
    }
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent_with_delays(calls, responses,
                                {"director_body": 0.05}))

    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["attire"]["Mara"]["remove"] == ["wool coat"]
    specialists = out["orchestration"]["specialists"]
    assert specialists["body"]["ran"] is True
    assert specialists["contact"]["ran"] is False
    assert "provider 500" in specialists["contact"]["error"]
    assert specialists["spatial"]["ran"] is False
    assert "timeout" in specialists["spatial"]["error"]
    assert sum(1 for w in ctx.warnings if "fail-open" in w) >= 2


def test_parallel_cancellation_aborts_the_beat(temp_db, monkeypatch):
    """Requirement: CANCELLATION. Aborted is the one exception that must
    propagate out of the fan-out -- a cancelled turn has no beat to fail
    open into, and swallowing it as a specialist failure would commit a
    half-cancelled resolve."""
    from providers import Aborted

    _orch_on(temp_db)
    responses = {
        "director_resolve": {"resolved_event": "x", "summary": "x",
                             "state_diff": {}},
        "director_contact": Aborted("generation aborted by user"),
    }
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent_with_delays(calls, responses, {}))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    try:
        director.director_resolve(ctx, nonce=0)
        raise AssertionError("Aborted must propagate out of the fan-out")
    except Aborted:
        pass


def test_specialists_never_stream(temp_db, monkeypatch):
    """Specialists produce structured output, not player-facing prose --
    only prose streams, so there is nothing to interleave. Every specialist
    call must observe a CLEARED token sink even when the enclosing step has
    one set (as it always does in the live pipeline), while cancellation
    context still reaches the worker (copy_context, the loops.py
    precedent)."""
    import providers

    _orch_on(temp_db)
    observed = {}

    real_fake = _fake_agent([], {})

    def probing(role, step_key, system, payload, **kw):
        observed[step_key] = providers.token_sink.get()
        return real_fake(role, step_key, system, payload, **kw)

    monkeypatch.setattr(director, "_agent_json", probing)

    ctx = _make_ctx(temp_db, interp=_action_interp())
    token = providers.token_sink.set(lambda delta: None)  # the step's sink
    try:
        director.director_resolve(ctx, nonce=0)
    finally:
        providers.token_sink.reset(token)

    # The prose author streams (it sees the step's sink)...
    assert observed["director_resolve"] is not None
    # ...and every specialist does not.
    specialist_keys = [k for k in observed if k != "director_resolve"]
    assert specialist_keys
    for key in specialist_keys:
        assert observed[key] is None, key
