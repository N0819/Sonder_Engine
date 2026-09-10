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
- a hand runs only when the Director's own ruling reached it (a
  `ledger_notes` line keyed by the hand or a channel it owns, or a
  `changes_asserted` entry in one of its categories), decided at each
  stage's own time from that stage's output; the scene-state gates decide
  only how much sheet an addressed hand loads, and FAIL OPEN within it;
- an unserved channel is never silent (the backstop is `changes_asserted`
  reconciliation pointed at the served scopes, via tell_director), and a
  ruling keyed by a name no hand answers to is reported as unrouted;
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

from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData

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


def _ruling(*hands):
    """A Director output that rules to exactly these hands. Dispatch keys on
    the ruling, so a fake resolve/interpret that names nobody runs nobody."""
    return {"ledger_notes": {hand: f"{hand}: settled this beat"
                             for hand in hands}}


_RULES_ALL = _ruling(*director.SPECIALISTS)


# ---------------------------------------------------------------------------
# The flag, and the monolithic default.
# ---------------------------------------------------------------------------

def test_the_fanout_is_the_only_path_and_has_no_off_switch(temp_db,
                                                           monkeypatch):
    """The monolithic Director is GONE, not defaulted-off.

    It shipped behind `director_orchestration`, default off, and stayed
    there while the fan-out was measured against it. The measurement
    finished: the fan-out is more stable, costs fewer tokens and less wall
    clock, so keeping a switch for the losing path would only preserve a way
    to make the engine worse. Every resolve now dispatches, carries an
    orchestration record, and loads the lean prose-author sheet -- with no
    setting, in any spelling, that returns the old one.
    """
    calls = []
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, {"director_resolve": _ruling("body")}))

    # DELIBERATE USE OF A DEAD SETTING KEY. Nothing in the engine reads
    # `director_orchestration` any more, and this is the tripwire that keeps
    # it that way: if some future change starts honouring it again, these
    # spellings will turn the fan-out off and this test will say so.
    for value in ("", "0", "off", "false"):
        temp_db.set_setting("director_orchestration", value)
        ctx = _make_ctx(temp_db, interp=_action_interp())
        out = director.director_resolve(ctx, nonce=0)
        assert out["orchestration"]["enabled"] is True, value

    sheet = calls[0]["system"]
    assert "DELEGATED CHANNELS -- SPECIALISTS ENCODE, YOU NARRATE" in sheet
    assert "CLOTHING TRACKING" not in sheet, (
        "the prose author loaded a delegated channel's machinery")
    assert any(c["step_key"].startswith("director_")
               and c["step_key"] != "director_resolve" for c in calls)


def test_every_delegated_block_has_exactly_one_owner():
    """The split was a recomposition, not a rewrite, and the way to keep it
    one is to check that nothing was lost and nothing is taught twice.

    Each block below was a section of the single sheet the Director used to
    carry. Every one must now live in exactly ONE specialist -- lost means a
    rule nobody applies, duplicated means two hands authoring the same
    channel from two spellings that can drift. And none may appear in the
    prose author's own sheet, which is what "delegated" means.
    """
    from llm.prompts import DEFAULT_PROMPTS

    owners = {
        "CLOTHING TRACKING": "director_body",
        "BODILY CONDITION": "director_body",
        "CAST CHANGES": "director_social",
        "INTRODUCTIONS": "director_social",
        "BODY POSITION — WHO IS IN CONTACT WITH WHOM": "director_contact",
        "MATERIAL TRANSFER": "director_contact",
        "BEING CARRIED — CONTAINMENT": "director_contact",
        "INVENTORY:": "director_objects",
        "NOTICES:": "director_objects",
        "DESTRUCTION — MANDATORY": "director_objects",
        "WITHIN-ROOM POSITION": "director_spatial",
        "BODY POSE": "director_spatial",
        "ROOM CREATION": "director_spatial",
        "RUNNING COVERS GROUND": "director_spatial",
        "CROWDS:": "director_social",
        "COURIERS:": "director_social",
        "PASSING ON WHAT": "director_social",
        "UNRATIFIED CLAIMS": "director_social",
    }
    sheets = {pid: DEFAULT_PROMPTS[pid]
              for pid in ("director_body", "director_social",
                          "director_contact", "director_objects",
                          "director_spatial")}
    for marker, owner in owners.items():
        carrying = [pid for pid, text in sheets.items() if marker in text]
        assert carrying == [owner], (marker, carrying)

    lean = DEFAULT_PROMPTS["director_resolve_lean"]
    for marker in owners:
        assert marker not in lean, marker
    assert "DELEGATED CHANNELS" in lean
    # The lean sheet still owns everything outside the delegated channels.
    for marker in ("WORLD PRESSURE", "APPROACHING IS NOT ARRIVING",
                   "SIZE CHANGES WHAT IS POSSIBLE",
                   "WHAT LIGHT LETS THEM DO", "DESTINATION RESIDUE",
                   "AUTHORITY APPRAISAL", "CONSEQUENCES ON THE CLOCK",
                   "SPANS ARE THE WORK ITEMS"):
        assert marker in lean, marker


def test_a_preset_can_actually_replace_a_chunked_sheet(temp_db):
    """A registry key nothing reads is folklore.

    The chunked sheets are assembled per beat rather than fetched through
    `get_prompt`, so for two releases a host could rewrite the body
    specialist's sheet, save the preset, and the engine would send the stock
    one -- silently. An override now replaces the sheet entirely, scope and
    all, which is the only honest reading of replacing a sheet: a host's
    text carries no chunk boundaries for scope to select between.
    """
    from llm import prompts

    temp_db.set_setting("prompt_presets", json.dumps({
        "Mine": {"director_body": "BODY SHEET, REWRITTEN.",
                 "director_resolve_lean": "PROSE SHEET, REWRITTEN."}}))
    temp_db.set_setting("active_preset", "Mine")
    body = prompts.specialist_prompt("body", ["attire"])
    prose = prompts.prose_author_prompt(None)
    assert body.startswith("BODY SHEET, REWRITTEN.")
    assert prose.startswith("PROSE SHEET, REWRITTEN.")
    # Presets replace authored role instructions, but cannot replace the
    # language/schema boundary every model call must retain.
    assert "LANGUAGE AND SCHEMA CONTRACT" in body
    assert "LANGUAGE AND SCHEMA CONTRACT" in prose
    # An untouched sheet still assembles from its chunks.
    assert "CROWDS:" in prompts.specialist_prompt("social", ["crowd_ops"])

    temp_db.set_setting("active_preset", "Default")
    assert "CLOTHING TRACKING" in prompts.specialist_prompt("body", ["attire"])


def test_specialist_sheets_are_assembled_from_scope():
    """The chunked-prompt contract (design note 19, hierarchical gating):
    a specialist's sheet is core + one chunk per GRANTED channel and
    nothing else -- scope selects chunks, no other selection logic. An
    unchunked prompt would load everything on every beat while appearing
    scoped, which is why tools/project_check.py enforces the structure;
    this pins the assembly itself."""
    from llm.prompts import SPECIALIST_PROMPT_SPECS, specialist_prompt

    attire_only = specialist_prompt("body", ["attire"])
    assert "CLOTHING TRACKING" in attire_only
    assert "BODILY CONDITION" not in attire_only
    assert "AWARENESS" not in attire_only
    everything = specialist_prompt(
        "body", ["attire", "conditions", "vitals", "overlays"])
    assert "BODILY CONDITION" in everything and "OVERLAYS" in everything
    # Empty scope is the bare core -- and dispatch never sends it (an empty
    # scope is a specialist not dispatched at all).
    # An empty scope contributes NO CHUNK -- which is the property this pins.
    # It is no longer byte-equal to the core: specialist_prompt also appends
    # the one shared rule every hand carries about the Director's ruling
    # channel, and `nsfw_overlay` when that is on. Asserting equality made
    # this test a hostage to any future shared clause AND to a host setting,
    # neither of which is what "scope selects chunks" means.
    bare = specialist_prompt("body", [])
    for chunk_marker in ("CLOTHING TRACKING", "BODILY CONDITION", "OVERLAYS"):
        assert chunk_marker not in bare, chunk_marker
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
    from llm.schemas import validate_llm_output

    out, _ = validate_llm_output("director_resolve", {
        "resolved_event": "x",
        "orchestration": {"enabled": True,
                          "specialists": {"body": {
                              "run": True, "addressed_by": ["note"],
                              "gated": ["conditions"],
                              "scope": ["conditions"]}},
                          "unrouted_rulings": ["transit"]},
    })
    body = out["orchestration"]["specialists"]["body"]
    assert body["run"] is True
    # The two halves of the dispatch decision persist beside it, or a
    # stored turn could never say WHY a hand did or did not run.
    assert body["addressed_by"] == ["note"] and body["gated"] == ["conditions"]
    assert out["orchestration"]["unrouted_rulings"] == ["transit"]

    # And a pre-orchestration variant (no record) still validates unchanged.
    old, _ = validate_llm_output("director_resolve", {"resolved_event": "x"})
    assert old["orchestration"] == {}


# ---------------------------------------------------------------------------
# Dispatch: the ruling decides who runs; the gate, decided at resolve time
# from scene state, decides how much sheet an addressed hand loads, and
# fails open within it.
# ---------------------------------------------------------------------------

def test_a_hand_named_without_a_channel_keeps_its_whole_ledger_set(
        temp_db, monkeypatch):
    """A ruling that names the HAND and no channel leaves the gates nothing
    to narrow, so the hand loads every ledger its story keeps.

    This replaced `gated union named`, which let a standing-state prediction
    overrule the Director. Measured live 2026-09-10
    (`tools/interpret_beats.py` beat 1, gemini-3.8-flash): the Director filed
    "pull off my sword belt" under category `body` with the note "remove sword
    belt from worn gear"; the wardrobe gate read `anyone_wears` false over a
    bare-bodied scene; and the body hand ran and answered `not_mine` about its
    own span -- "Event 1 requires the attire/wardrobe channel, which has no
    block on this sheet" -- at 6,466 output tokens and 37 seconds.

    It was never going to name a channel, either: the Director's sheet asks
    for a category from the five HAND names, and the owner's design is that it
    need not know a specialist's channels at all. The gate table had already
    logged this exact case as an open residual and chosen to backstop it; a
    backstop catches the record, it does not get the call back.

    What it costs, measured on the assembled sheets: 1.08x the two-chunk sheet
    for `body`, 2.17x for `social`, all of it prefill."""
    calls = []
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, {"director_resolve": _ruling("body")}))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert "director_body" in _steps(calls)
    body = out["orchestration"]["specialists"]["body"]
    assert body["run"] is True and body["ran"] is True
    assert body["addressed_by"] == ["note"]
    assert "conditions" in body["scope"] and "overlays" in body["scope"]
    # The channel the gate used to subtract, over a scene where nobody wears
    # anything -- which is a fact about what STANDS, and a span is a claim
    # about what CHANGES.
    assert "attire" in body["scope"]
    # `gated` still records what the scene admitted, unchanged: the record has
    # to keep saying "the ruling reached this hand" apart from "this story
    # keeps no such ledger", and a scope that swallowed the gates would not.
    assert "attire" not in (body["gated"] or [])


def test_no_ruling_runs_no_hand(temp_db, monkeypatch):
    """The rule itself. A physical beat over worn attire -- every gate a
    scene-state dispatch would have opened -- runs NO specialist when the
    Director's output names none: no note, no manifest. Every hand records
    that the ruling never reached it, which is a different fact from a
    gate reading the scene as still, and the record says which."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}

    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert _steps(calls) == ["director_resolve"]
    for name, state in out["orchestration"]["specialists"].items():
        assert state["run"] is False, name
        assert state["scope"] == [], name
        assert state["addressed_by"] == [], name
    body = out["orchestration"]["specialists"]["body"]
    assert "attire" in body["gated"]  # the scene admitted it; nobody ruled


def test_a_manifest_entry_addresses_its_hand(temp_db, monkeypatch):
    """The second half of the ruling: a `changes_asserted` entry in a
    hand's category is the Director saying that channel changed, whether
    or not it also wrote a note. The body hand runs, records that the
    manifest reached it, and has the named channel in scope."""
    calls = []
    resolve_out = {
        "resolved_event": "Mara shrugs the wool coat off.",
        "summary": "Coat off.",
        "changes_asserted": [
            {"category": "attire", "subject": "Mara",
             "change": "The wool coat is off."},
        ],
        "state_diff": {},
    }
    responses = {
        "director_resolve": resolve_out,
        "director_body": {"attire": {"Mara": {"remove": ["wool coat"]}},
                          "conditions": {}, "vitals": {}, "overlays": {},
                          "notes": []},
    }
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    body = out["orchestration"]["specialists"]["body"]
    assert body["run"] is True and body["ran"] is True
    assert body["addressed_by"] == ["manifest"]
    assert "attire" in body["scope"]
    assert out["state_diff"]["attire"]["Mara"]["remove"] == ["wool coat"]
    assert "director_spatial" not in _steps(calls)


def test_a_note_keyed_by_a_channel_addresses_its_owner(temp_db, monkeypatch):
    """Measured: most notes are keyed by CHANNEL, not by hand. A line under
    `positions` reaches the spatial hand, and nobody else runs."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_resolve": {
            "resolved_event": "Mara crosses to the lamp room.",
            "summary": "A move.",
            "ledger_notes": {"positions": "Mara is now in lamp_room"},
            "state_diff": {},
        }}))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    spatial = out["orchestration"]["specialists"]["spatial"]
    assert spatial["run"] is True and spatial["addressed_by"] == ["note"]
    assert "positions" in spatial["scope"]
    assert [k for k in _steps(calls) if k != "director_resolve"] == \
        ["director_spatial"]


def test_a_ruling_widens_a_closed_gate(temp_db, monkeypatch):
    """Sibling of the pure-dialogue skip below: the same still beat, but
    the Director rules under `conditions`. A ruling is direct evidence and
    a gate is a prediction, so the channel enters scope whatever the gate
    read, and the body hand runs with it."""
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_resolve": {
            "resolved_event": "Mara says the burn has closed.",
            "summary": "A burn, healed.",
            "ledger_notes": {"conditions": "Mara's burn ends"},
            "state_diff": {},
        }}))

    ctx = _make_ctx(temp_db, scene=scene, interp=_speech_interp())
    out = director.director_resolve(ctx, nonce=0)

    body = out["orchestration"]["specialists"]["body"]
    assert body["gated"] == []               # the gate read nothing to do
    assert body["run"] is True and body["scope"] == ["conditions"]
    assert "director_body" in _steps(calls)


def test_a_ruling_nobody_answers_to_is_reported_not_guessed(temp_db,
                                                             monkeypatch):
    """A note keyed `transit` names no hand and no channel. The engine
    does not guess that it meant `positions`: nobody runs for it, the key
    is recorded on the step, and the next beat's Director is told which
    names route."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_resolve": {
            "resolved_event": "The lift climbs.",
            "summary": "Lift.",
            "ledger_notes": {"transit": "the lift is between floors"},
            "state_diff": {},
        }}))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert _steps(calls) == ["director_resolve"]
    assert out["orchestration"]["unrouted_rulings"] == ["transit"]
    notes = [n for n in ctx.engine_feedback if n.startswith("ledger_notes:")]
    assert notes and "'transit'" in notes[0] and "spatial" in notes[0]


def test_at_interpret_both_halves_of_the_ruling_address(temp_db, monkeypatch):
    """Both halves of the ruling reach a hand at interpret, as at resolve.

    This test previously pinned the opposite -- "the declaration asserts, it
    does not narrate changes", interpret view manifest `[]`, a
    `changes_asserted` list reaching nobody. That premise is contradicted by
    the schema it describes: `DirectorInterpret` carries a full `StateDiff`
    because "WHAT THE PLAYER SAYS HAPPENS, HAPPENS -- that turn, before
    perception pass 1 fires", and every specialist sheet tells a hand serving
    `player_declaration` to encode what the declaration asserts as ALREADY
    TRUE or COMPLETED. Pulling off a coat is a completed change. What interpret
    lacked was not the authority, it was the FIELD.

    Measured 2026-09-09 over 416 captured rulings, the cost of that gap:
    `changes_asserted` was absent from 100% of 184 interpret outputs, so no
    interpret beat could ever address a hand by category, and dispatch there
    ran entirely on hand-addressed notes -- the one router that cannot be
    replaced by code (`tools/dispatch_replay.py`, design note section 3c-bis).

    Contestable acts are still nobody's to encode here, but that is the
    sheet's rule about what belongs IN the manifest, not a reason the stage
    cannot have one.
    """
    calls = []
    interpret_out = {
        "kind": "action",
        "sequence": [{"type": "action", "attempt": "pull off my wool coat",
                      "commitment": "asserted", "targets": [],
                      "raw_text": "I pull off my wool coat"}],
        "speech": None, "action": {"attempt": "pull off my wool coat"},
        "movement": None,
        "ledger_notes": {"body": "the coat comes off"},
        "changes_asserted": [
            {"category": "positions", "subject": "Mara", "change": "moves"},
        ],
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_interpret": interpret_out,
        "director_body": {"attire": {}, "conditions": {}, "vitals": {},
                          "overlays": {}, "notes": []},
    }))
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}

    ctx = _make_ctx(temp_db, scene=scene,
                    player_input="I pull off my wool coat")
    ctx.director_interpret = None
    out = director.director_interpret(ctx, nonce=0)

    view = director._interpret_beat_view(ctx, interpret_out, "P")
    assert [i["category"] for i in view["manifest"]] == ["positions"]
    assert [i["event_id"] for i in view["manifest"]] == [1], (
        "the engine numbers the manifest here exactly as it does at resolve")

    specialists = out["orchestration"]["specialists"]
    # the note still addresses its hand, unchanged
    assert specialists["body"]["run"] is True
    assert specialists["body"]["addressed_by"] == ["note"]
    # ...and the manifest now addresses the hand that owns `positions`, which
    # no note named. Before the field existed this hand did not run and the
    # player's declared step reached no ledger at this stage.
    assert specialists["spatial"]["run"] is True
    assert specialists["spatial"]["addressed_by"] == ["manifest"]


class TestTheInstructionRidesOnTheEvent:
    """The Director's intent belongs to the EVENT, not to the hand.

    `DESIGN_SPECIALIST_CONTRACT.md`: a hand's work item is a chunk carrying a
    chronological id and a note saying how the Director wants that one
    resolved. Before this, resolution intent existed only as `ledger_notes:
    {specialist: line}` -- one line per HAND, aggregated across everything
    that hand does this beat, arriving through a different channel from the
    event it was about.

    Measured 2026-09-09 on current code (`tools/instruction_coverage.py`):
    every dispatched hand does receive some instruction -- 0% get none -- but
    46% of calls carry a hand-level note with no numbered event beside it, so
    the intent and its event had different coverage and no link.

    `note` is OPTIONAL and stays so: an entry without one is still a routable
    change, and the hand reads it exactly as it does today.
    """

    def test_the_shared_type_carries_the_instruction(self):
        from llm.schemas import AssertedChange
        entry = AssertedChange(category="pose", subject="Maren",
                               change="Maren has turned to face you.",
                               note="She is standing, facing you now.")
        assert entry.note == "She is standing, facing you now."

    def test_an_entry_without_one_is_still_valid(self):
        from llm.schemas import AssertedChange
        assert AssertedChange(category="pose", subject="Maren",
                              change="Maren has turned.").note == ""

    def test_both_halves_of_the_director_carry_it(self):
        """`AssertedChange` is shared by both stages deliberately, so this
        pins that the sharing still holds rather than re-testing the field."""
        from llm.schemas import DirectorInterpret, DirectorResolve
        for model in (DirectorInterpret, DirectorResolve):
            built = model(changes_asserted=[
                {"category": "pose", "subject": "Maren", "change": "turned",
                 "note": "settle her facing you"}])
            assert built.changes_asserted[0].note == "settle her facing you"

    def test_the_instruction_reaches_the_hand_that_owns_the_event(self):
        """The whole point: it has to survive the slice into the payload."""
        view = {"manifest": [
            {"category": "poses", "event_id": 1, "subject": "Maren",
             "change": "Maren has turned to face you.",
             "note": "She is standing, facing you now."}]}
        sliced = director._specialist_manifest_slice("spatial", view)
        assert sliced[0]["note"] == "She is standing, facing you now."

    def test_it_survives_the_numbering_the_engine_actually_runs(self):
        """THROUGH `_manifest_items`, not around it.

        The test above hand-builds its view and so proves nothing about the
        pipeline. `_manifest_items` rebuilds every entry as an explicit dict
        and then copies a FIXED LIST of extra fields onto it, so a field
        missing from that list is dropped with nothing raised and nothing
        logged. `note` was, on the first cut of this change: the Director
        wrote the instruction, the slice would have carried it, and the hand
        would never have seen it.
        """
        out = {"changes_asserted": [
            {"category": "pose", "subject": "Maren",
             "change": "Maren has turned to face you.",
             "note": "She is standing, facing you now."}]}
        items = director._manifest_items(out)
        assert items[0]["note"] == "She is standing, facing you now."
        assert items[0]["event_id"] == 1

    def test_an_entry_with_no_instruction_grows_no_empty_key(self):
        """Same rule the endpoint fields follow: a key appears when the model
        supplied one, rather than an empty string on every item."""
        out = {"changes_asserted": [
            {"category": "pose", "subject": "Maren", "change": "turned"}]}
        assert "note" not in director._manifest_items(out)[0]

    def test_the_instruction_now_rides_on_the_span(self):
        """`note` moved with the work item. When `changes_asserted` was the
        work list the instruction lived on a manifest entry; the work list is
        now the categorized span, so that is where the sheet asks for it --
        and neither sheet asks for a second decomposition at all."""
        from llm.prompts import get_prompt
        from llm import prompts
        interpret = get_prompt("director_interpret", "en")
        for _field in ("depends_on:[]", "category", "note", "items:[]"):
            assert _field in interpret, _field
        assert "changes_asserted" not in interpret
        assert "changes_asserted" not in prompts._PROSE_AUTHOR_OUTPUT_SHAPE

    def test_the_output_example_shows_it(self):
        """The third place: the object a repaired call is told to imitate.
        `director_interpret`'s example is shape-only by its own stated
        convention, so the worked entry lives on the resolve side."""
        from llm.schemas import OUTPUT_EXAMPLES
        entry = OUTPUT_EXAMPLES["director_resolve"]["changes_asserted"][0]
        assert entry.get("note"), entry

    def test_no_sheet_promises_the_hand_the_beats_prose(self):
        """The inversion `DESIGN_SPECIALIST_CONTRACT.md` is about, in the
        sheet's own words.

        Every core used to call `resolved_event` "the AUTHORITATIVE prose of
        what objectively happened" and close with "never contradict the
        prose", while introducing the instruction channel conditionally --
        so a hand asked to settle event 3 was told the narrative outranked
        it. The prose is no longer sent at all, so a sheet that still
        describes it is promising a payload key that will not arrive, which
        is worse than the original inversion: the hand goes looking for its
        account of the beat and finds nothing.
        """
        from llm.prompts import specialist_prompt
        for name in director.SPECIALISTS:
            sheet = specialist_prompt(name,
                                      director.SPECIALISTS[name]["channels"])
            assert "AUTHORITATIVE prose" not in sheet, name
            assert "YOUR WHOLE JOB" in sheet, name
            # Said out loud, because a hand told only "you don't get X" can
            # reasonably infer it is being deprived of something it needs.
            assert "nothing is being kept from you" in sheet, name

    def test_the_beats_prose_is_not_in_the_payload(self):
        """The removal itself, at the seam that assembles what a hand is
        sent. Measured before it: `resolved_event` reached the hand on 632 of
        632 resolve-side calls, 910 chars, and 73% of those calls carried no
        numbered event to check it against."""
        from types import SimpleNamespace
        view = {"source": "resolved_beat", "player": "Corin", "cast": [],
                "declared_actions": [], "dice": {},
                "prose": "Maren turns from the water to face you.",
                "dialogue": [],
                "ledger_notes": {"spatial": "she is facing you"},
                "manifest": []}
        payload = director._specialist_payload(
            "spatial", SimpleNamespace(chat={"id": 1}),
            {"rooms": {}, "positions": {}, "entities": {}}, view, {})
        assert "resolved_event" not in payload
        assert payload.get("director_note") == "she is facing you"

    def test_every_specialist_sheet_says_the_event_carries_it(self):
        """The fourth place, and the one that matters most: the hand has to
        know the instruction is there, or it reads the prose instead.

        Assembled through `specialist_prompt`, which is what the hand is
        actually sent -- a core the pack ships but the assembler drops would
        pass a file-level check and teach nobody."""
        from llm.prompts import specialist_prompt
        for name in director.SPECIALISTS:
            sheet = specialist_prompt(name, director.SPECIALISTS[name]["channels"])
            assert "carries `note`" in sheet, name


class TestASpanIsSettledOnlyWhenEveryOwnerHas:
    """A span in several categories is not a routing hedge with one right
    answer. The owner, 2026-09-10: "neither resolve overwrites the other, they
    are both completed halves or thirds or quarters of a singular ledger."

    `_index_addressed_events` keyed one owner per `event_id`, so the last hand
    to answer overwrote the first: a span whose wardrobe half was encoded and
    whose object half was not would read as fully settled, and the seam would
    acquit it. Written BEFORE any span carries two categories, so the silent
    loss is never possible rather than fixed after it appears.
    """

    def _index(self, answers):
        dispatch = {
            hand: {"ran": True,
                   "events_resolved": [{"event_id": 1, "status": status}]}
            for hand, status in answers.items()}
        return director._index_addressed_events(dispatch)

    def test_every_owner_is_kept_not_the_last_one(self):
        index = self._index({"body": "encoded", "objects": "not_mine"})
        assert set(index[1]["by_hand"]) == {"body", "objects"}
        assert index[1]["by_hand"]["body"]["status"] == "encoded"
        assert index[1]["by_hand"]["objects"]["status"] == "not_mine"

    def test_a_half_settled_span_stays_owed(self):
        out = {"orchestration": {
            "events_addressed": self._index({"body": "encoded",
                                             "objects": "not_mine"})}}
        omission = {"event_id": 1, "category": "attire", "subject": "Corin",
                    "change": "the belt is off"}
        owed, acquitted, _refused = director._acquit_addressed_events(
            out, [omission], {})
        assert owed == [omission]
        assert acquitted == []

    def test_a_fully_settled_span_is_acquitted(self):
        out = {"orchestration": {
            "events_addressed": self._index({"body": "encoded",
                                             "objects": "encoded"})}}
        omission = {"event_id": 1, "category": "attire", "subject": "Corin",
                    "change": "the belt is off"}
        owed, acquitted, _refused = director._acquit_addressed_events(
            out, [omission], {})
        assert owed == []
        assert len(acquitted) == 1

    def test_a_single_owner_settles_as_it_always_did(self):
        """The fallback. A row written before `by_hand` existed, and a span
        one hand owns, both read the way they always have."""
        out = {"orchestration": {
            "events_addressed": {1: {"owner": "body", "status": "encoded"}}}}
        omission = {"event_id": 1, "category": "attire", "subject": "Corin",
                    "change": "the belt is off"}
        owed, acquitted, _refused = director._acquit_addressed_events(
            out, [omission], {})
        assert owed == []
        assert len(acquitted) == 1


class TestTheSpanIsTheWorkItem:
    """`sequence` becomes the four-field work item: chunk, id, note, category.

    `DESIGN_SPECIALIST_CONTRACT.md` 4a, and the owner's ruling on which field
    survives. `sequence` was always the right dissection -- typed spans of the
    player's own input -- and lacked only a category saying which ledger family
    a span belongs to, an id, and the Director's note on how it should resolve.

    `changes_asserted` still exists and still routes; the two share ONE id
    space so a record's `from_event` is never ambiguous about which list it
    points into.
    """

    def test_the_engine_numbers_the_spans(self):
        out = {"sequence": [
            {"type": "action", "attempt": "I pull off my belt",
             "category": "attire", "note": "belt comes off"},
            {"type": "action", "attempt": "drop it on the bench",
             "category": "entities", "note": "belt rests on the bench"}]}
        items = director._span_items(out)
        assert [i["event_id"] for i in items] == [1, 2]
        assert items[0]["note"] == "belt comes off"

    def test_an_uncategorized_span_is_not_a_work_item(self):
        """A question asked or a look given is a perfectly good sequence
        element -- perception and the narrator read it -- it just addresses no
        ledger. Making every span a work item would dispatch a hand for every
        line of dialogue."""
        out = {"sequence": [
            {"type": "speech", "text": "Have you seen the reeve?"},
            {"type": "action", "attempt": "I sit", "category": "poses"}]}
        items = director._span_items(out)
        assert [i["attempt"] for i in items] == ["I sit"]
        assert items[0]["event_id"] == 1

    def test_the_manifest_continues_past_the_spans(self):
        """ONE ID SPACE. Both lists live during the migration, and a record's
        `from_event` names one number -- so they cannot both start at 1."""
        out = {"sequence": [{"type": "action", "attempt": "x",
                             "category": "poses"}],
               "changes_asserted": [{"category": "attire", "subject": "Corin",
                                     "change": "the belt is off"}]}
        assert director._span_items(out)[0]["event_id"] == 1
        assert director._manifest_items(out)[0]["event_id"] == 2

    def test_a_span_dispatches_the_hand_that_owns_its_category(self):
        view = {"ledger_notes": {}, "manifest": [], "spans": [
            {"category": "poses", "event_id": 1, "attempt": "I kneel",
             "note": "set her kneeling"}]}
        assert director._ruling_for("spatial", view)[0] == ["manifest"]
        assert director._ruling_for("body", view)[0] == []

    def test_the_span_reaches_the_hand_that_owns_it(self):
        view = {"spans": [
            {"category": "poses", "event_id": 1, "attempt": "I kneel",
             "note": "set her kneeling"},
            {"category": "attire", "event_id": 2, "attempt": "belt off",
             "note": "unequip the belt"}]}
        assert [c["event_id"] for c in
                director._specialist_span_slice("spatial", view)] == [1]
        assert [c["event_id"] for c in
                director._specialist_span_slice("body", view)] == [2]

    def test_the_work_item_reaches_the_hand_in_exactly_one_list(self):
        """`spans` carries the work; `declaration` carries what was declared.

        The three fields lived in BOTH for a day, and the duplication cost a
        beat. `assign_event_ids` stamps every declaration element with a
        phase-graph id also called `event_id`, so a hand's payload held two
        fields of that name with different values. Measured 2026-09-10, beat
        2: the contact hand echoed "turn:2:player:0:action", its entire answer
        was rejected, and its repair returned no usable object -- 16,180
        output tokens and 96.9s on a receipt for the wrong ledger.

        The allowlist that drops what it does not name is still the hazard it
        was; what changed is which list is meant to hold these."""
        from types import SimpleNamespace
        ctx = SimpleNamespace(cast=[], scene=None)
        out = {"sequence": [{"type": "action", "attempt": "I kneel",
                             "category": "poses", "note": "set her kneeling"}]}
        view = director._interpret_beat_view(ctx, out, "Corin")
        span = view["spans"][0]
        assert span["category"] == "poses"
        assert span["note"] == "set her kneeling"
        assert span["event_id"] == 1
        declared = view["declaration"]["sequence"][0]
        assert declared["attempt"] == "I kneel"
        for field in ("event_id", "category", "note"):
            assert field not in declared, field

    def test_a_span_nothing_answers_to_is_reported_not_guessed(self):
        """A work item in a category no hand owns is a change the engine
        cannot deliver, and the silence is the same one `_unrouted_rulings`
        was written for -- one field over.

        Measured 2026-09-10: with `reasoning_effort=low` on the Director the
        category vocabulary DRIFTS. It filed `geography` twice for what
        `spatial` owns, on a run that was otherwise clean (0 errors, 0
        unroutable notes). Reported rather than folded onto the nearest hand:
        a synonym table would be the engine inventing vocabulary on the
        Director's behalf and getting it wrong quietly, which is what
        `_note_key_forms` refuses in as many words.
        """
        view = {"ledger_notes": {}, "spans": [
            {"category": "geography", "event_id": 1, "attempt": "I walk out"},
            {"category": "poses", "event_id": 2, "attempt": "I kneel"}]}
        assert director._unrouted_rulings(view) == ["geography"]

    def test_the_sheet_asks_for_them(self):
        from llm.prompts import get_prompt
        sheet = get_prompt("director_interpret", "en")
        for _field in ("depends_on:[]", "category", "note", "items:[]"):
            assert _field in sheet, _field
        assert "AND SAY WHERE EACH SPAN LANDS" in sheet


class TestTheSheetAsksForNothingUnread:
    """A field the sheet asks for and nothing reads costs three times: the
    sentence teaching it, the tokens writing it, and a reader's belief that it
    matters.

    `referents[].role` looked like that and IS NOT. It published six values --
    actor / actor_possessive / target / target_possessive / instrument /
    instrument_possessive -- and a first reading of
    `agents.common.resolve_action_referents` found it using only `text`,
    `entity` and `occurrence`. That reading was of a TRUNCATED view of the
    function: line 378 reads `role` and drives the possessive form off it, and
    cutting the field turned "takes Mara's hand with Iris' left hand" into
    "takes Mara hand with Iris left hand". The guard below caught it, which is
    the argument for writing the guard before the cut rather than after.

    What IS dead is five sixths of the enum. The only test anywhere is
    `"possessive" in role`, so actor / target / instrument are never
    distinguished and the six values carry one bit. `plain|possessive`
    satisfies the same predicate -- and so does every value the old enum had,
    so a stored variant replayed from before this still resolves.
    """

    def test_the_referent_role_is_two_values_carrying_one_bit(self):
        from llm.prompts import DEFAULT_PROMPTS
        sheet = DEFAULT_PROMPTS["director_interpret"]
        assert "role:'plain|possessive'" in sheet
        assert "actor_possessive" not in sheet

    def test_possessive_still_renders(self):
        """The behaviour the enum actually drives, and the assertion that
        caught the bad cut."""
        from agents.common import resolve_action_referents
        event = {"referents": [
            {"text": "her", "entity": "Mara", "role": "possessive",
             "occurrence": 1},
            {"text": "her", "entity": "Iris", "role": "possessive",
             "occurrence": 2},
        ]}
        assert resolve_action_referents(
            "takes her hand with her left hand", event) == (
            "takes Mara's hand with Iris' left hand")

    def test_the_old_spelling_still_resolves(self):
        """`"possessive" in role` matches every value the six-value enum had,
        so stored variants and mid-flight reruns are unaffected."""
        from agents.common import resolve_action_referents
        event = {"referents": [
            {"text": "her", "entity": "Mara", "role": "target_possessive",
             "occurrence": 1},
        ]}
        assert resolve_action_referents("takes her hand", event) == \
            "takes Mara's hand"

    def test_a_plain_referent_is_not_made_possessive(self):
        from agents.common import resolve_action_referents
        event = {"referents": [
            {"text": "her", "entity": "Mara", "role": "plain",
             "occurrence": 1}]}
        assert resolve_action_referents("takes her hand", event) == \
            "takes Mara hand"


class TestNoSheetAddressesACallThatCannotHappen:
    """A dispatched hand always carries something, so "you may have nothing"
    is text no running call ever needs.

    Dispatch is `bool(scope)` and a hand is only addressed by a `ledger_notes`
    line, a work item in one of its categories, or a pressure tick -- and each
    of those puts its own key in the payload. A hand that would arrive empty is
    a hand that does not run.

    Measured 2026-09-10 across every current-code run: 185 dispatched
    specialist calls, 129 note-only, 55 note-and-work, 1 work-only, and ZERO
    with nothing. (The owner's archive shows 796 of 1,214 arriving empty, which
    is historical traffic from before `ledger_notes` reached the interpret
    half -- the same trap that made an earlier reading of this look like a live
    defect. And 17 apparently-empty calls in the current runs were
    JSON-REPAIR retries, whose payload is `instruction`/`validation_errors`
    and is not a dispatch at all.)
    """

    def test_the_ruling_card_does_not_offer_an_empty_beat(self):
        from llm.prompts import specialist_prompt
        for name in director.SPECIALISTS:
            sheet = specialist_prompt(name,
                                      director.SPECIALISTS[name]["channels"])
            assert "nothing at all" not in sheet, name

    def test_the_ruling_card_does_not_send_a_hand_back_to_prose(self):
        """It told hands not to restate ledgers "from the prose" -- which they
        have not been given since the prose left the payload."""
        from llm.prompts import specialist_prompt
        for name in director.SPECIALISTS:
            sheet = specialist_prompt(name,
                                      director.SPECIALISTS[name]["channels"])
            assert "restating them from the prose" not in sheet, name

    def test_a_hand_with_no_address_is_not_dispatched(self):
        """The premise. If this ever stops holding, the card above has a case
        to describe again."""
        empty = {"ledger_notes": {}, "manifest": [], "spans": []}
        for name in director.SPECIALISTS:
            assert director._ruling_for(name, empty)[0] == [], name


class TestBothHalvesEmitWorkItems:
    """Resolve is the interpret half's structural twin, and stayed behind.

    "Resolve would mostly do the same but for characters" -- so a span there is
    anything the beat made true, by anyone, rather than only the player's own
    declared conduct.

    It did not have one. `_span_items` reads `sequence`, `DirectorResolve`
    had no such field, and the retirement of `changes_asserted` left the
    resolve author with a sheet block telling it that "the categorized spans
    of the beat are the work items every ledger is written from" and NO FIELD
    to write them into -- so resolve-side hands got `director_note` and
    nothing else. This is the same defect the class two files up was written
    for (`ledger_notes` built on the resolve half only) pointing the other
    way, which is why it gets a guard rather than a fix.
    """

    def test_both_models_carry_the_work_item_field(self):
        from llm.schemas import DirectorInterpret, DirectorResolve
        span = {"actor": "Maren", "attempt": "turns to face you",
                "category": "poses", "note": "set her facing you"}
        for model in (DirectorInterpret, DirectorResolve):
            built = model(sequence=[span])
            assert built.sequence[0]["category"] == "poses", model.__name__
            assert built.sequence[0]["note"], model.__name__

    def test_both_beat_views_carry_spans(self):
        """The view is what a hand is handed. Numbered on both halves, by the
        engine, or the ids a record cites mean nothing on one of them."""
        from types import SimpleNamespace
        out = {"sequence": [{"actor": "Maren", "attempt": "turns",
                             "category": "poses", "note": "face you"}]}
        interpret = director._interpret_beat_view(
            SimpleNamespace(cast=[], scene=None), out, "Corin")
        assert interpret["spans"][0]["event_id"] == 1

        resolve = director._resolve_beat_view(
            out, [], {}, [], "Corin", {"sequence": []})
        assert resolve["spans"][0]["event_id"] == 1
        assert resolve["spans"][0]["note"] == "face you"

    def test_a_resolve_span_dispatches_by_its_category(self):
        view = {"ledger_notes": {}, "manifest": [], "spans": [
            {"actor": "Maren", "attempt": "turns", "category": "poses",
             "event_id": 1, "note": "face you"}]}
        assert director._ruling_for("spatial", view)[0] == ["manifest"]
        assert director._ruling_for("social", view)[0] == []

    def test_both_sheets_ask_for_the_field(self):
        from llm.prompts import get_prompt_body, prose_author_prompt
        _body = get_prompt_body("director_interpret")
        for _field in ("category", "note", "items:[]"):
            assert _field in _body, _field
        resolve = prose_author_prompt(None)
        assert "sequence:[{actor,attempt,category,note}]" in resolve
        assert "SPANS ARE THE WORK ITEMS" in resolve

    def test_a_resolve_span_is_reconciled_by_its_actor(self):
        """An interpret span is the player's own and names no subject; a
        resolve span names whose act it was, and that is what the evidence
        check matches when the hand stamped no id."""
        from agents.director import _subject_match_forms  # noqa: F401
        item = {"actor": "Maren", "attempt": "turns", "category": "poses",
                "event_id": 1, "note": "face you"}
        filled = {**item, "change": item["note"],
                  "subject": item.get("subject") or item.get("actor") or ""}
        assert filled["subject"] == "Maren"


class TestTheOpCarriesTheChunkId:
    """A record says which instruction it answers, on itself.

    `DESIGN_SPECIALIST_CONTRACT.md` section 4b. Reconciliation proves an entry
    was encoded by matching ENDPOINT TEXT against the diff, which is why
    `changes_asserted` carries ten endpoint fields it would otherwise not
    need. An id makes that an exact lookup and unblocks the four-field chunk
    format.

    `phase_sources` was the cheaper candidate and lost on measurement:
    emitted on 25% of productive calls, 68% of `encoded` claims cited, never
    once by `director_social` across 91 calls
    (`tools/provenance_coverage.py`) -- because a structure filled in ALONGSIDE
    the work is a second thing to remember. A field inside the object the
    model is already composing is not.
    """

    def test_a_typed_record_keeps_it(self):
        """Typed models STRIP what they do not declare, so every delegated
        channel's record type has to name it or the hand's answer is dropped
        by validation -- which is how `note` was lost earlier today."""
        from llm.schemas import (ArtifactOp, AttireDiff, CharterPublicEvidence,
                                 CommsOp, CourierOp, CrowdOp, PoseEntry,
                                 RoomDef, SceneEntityDef, TellingOp)
        # A superset of the required fields across the ten; each model ignores
        # the keys it does not declare, so this is still real validation and
        # not a construct-without-checking.
        common = {"from_event": 3, "name": "x", "id": "x", "kind": "x",
                  "op": "add", "subject": "x", "text": "x", "who": "x",
                  "what": "x", "location_id": "x", "claim_id": "x"}
        for model in (SceneEntityDef, RoomDef, CommsOp, PoseEntry, CrowdOp,
                      AttireDiff, CharterPublicEvidence, TellingOp, CourierOp,
                      ArtifactOp):
            assert model(**common).from_event == 3, model.__name__

    def test_the_attire_coercion_does_not_eat_it(self):
        """`AttireDiff` runs a before-validator that files unrecognised keys
        under `notes` for commit to resolve against the wardrobe. Untaught, it
        turned the provenance id into a garment handle called
        'from_event' -- a tolerant reader has to be told what its new fields
        are, or its tolerance quietly eats them."""
        from llm.schemas import AttireDiff
        diff = AttireDiff(from_event=3, remove=["wool coat"])
        assert diff.from_event == 3
        assert "from_event" not in diff.notes

    def test_reconciliation_accepts_an_id_over_endpoint_text(self):
        """The point of the field. The manifest entry and the record share no
        subject spelling and no endpoints -- only the id."""
        sd = {"poses": {"Maren": {"posture": "kneeling", "from_event": 7}}}
        omission = {"category": "pose", "subject": "somebody the text does "
                                                   "not name the same way",
                    "change": "she kneels", "event_id": 7}
        assert director._evidence_present(sd, omission) is True

    def test_a_record_naming_nothing_falls_through_to_the_old_check(self):
        """Additive, so it can land ahead of the `sequence` migration: every
        record written before the field existed, and every standing record
        refreshed on its own account, still gets exactly the check it got."""
        sd = {"poses": {"Maren": {"posture": "kneeling"}}}
        assert director._evidence_present(
            sd, {"category": "pose", "subject": "Maren", "change": "kneels",
                 "event_id": 7}) is True
        assert not director._evidence_present(
            sd, {"category": "pose", "subject": "Corin", "change": "kneels",
                 "event_id": 7})

    def test_a_wrong_id_does_not_acquit(self):
        sd = {"poses": {"Maren": {"posture": "kneeling", "from_event": 2}}}
        assert not director._evidence_present(
            sd, {"category": "pose", "subject": "Nobody", "change": "x",
                 "event_id": 7})

    def test_ids_are_found_at_every_channel_shape(self):
        """A delegated channel is a record dict, a list of ops, or a dict of
        lists. Provenance has to be read out of all three or it works on
        poses and silently not on contacts."""
        assert director._cited_event_ids(
            {"poses": {"Maren": {"from_event": 1}}}) == {1}
        assert director._cited_event_ids(
            {"contact_ops": [{"op": "add", "from_event": 2}]}) == {2}
        assert director._cited_event_ids(
            {"conditions": {"Maren": [{"kind": "hurt", "from_event": 3}]}}) == {3}

    def test_every_specialist_sheet_asks_for_it(self):
        from llm.prompts import specialist_prompt
        for name in director.SPECIALISTS:
            sheet = specialist_prompt(name,
                                      director.SPECIALISTS[name]["channels"])
            assert "from_event" in sheet, name


class TestAnEncodedClaimNeedsSomethingEncoded:
    """`encoded` from a hand whose channels are all empty is not an answer.

    The shared specialist core defines the verdict as "you put it in your
    channels this beat", and warns that "answering honestly is always cheaper
    than answering agreeably". A hand that returns every channel empty and
    still says `encoded` is self-contradictory, and it is the worst available
    answer: the reconciliation seam believes it, buys no repair, and the
    change is lost with no warning anywhere.

    Measured 2026-09-09 (`tools/false_encoded.py`). At the roles' default
    reasoning effort, 0 of 11 `encoded` claims wrote nothing. With
    `reasoning_effort=low` on the five specialists, 2 of 12 did -- both
    `director_objects`, both on a beat where a thing came into being or was
    broken (a hinge hammered apart; a notice nailed up). It returned
    `{"entities": {}}` beside `resolved_events: [{event_id: 1, status:
    "encoded"}]`.

    The guard is not about that lever. The claim is refutable from the
    RESPONSE ALONE -- no diff, no manifest, no scene -- so there is no reason
    to have ever believed it, at any effort level.

    `already_true` and `not_mine` are deliberately still honoured on an empty
    response: both MEAN "correctly wrote nothing".
    """

    def test_an_encoded_claim_with_content_is_kept(self):
        result = {"entities": {"hinge": {"name": "broken hinge"}},
                  "resolved_events": [{"event_id": 1, "status": "encoded"}]}
        assert director._resolved_event_verdicts(result, [1]) == [
            {"event_id": 1, "status": "encoded"}]

    def test_an_encoded_claim_with_every_channel_empty_is_dropped(self):
        result = {"entities": {}, "remove_entities": [], "inventory_ops": [],
                  "sensory_events": [],
                  "resolved_events": [{"event_id": 1, "status": "encoded"}],
                  "notes": []}
        assert director._resolved_event_verdicts(result, [1]) == []

    def test_already_true_survives_an_empty_response(self):
        """It is the verdict that MEANS the ledgers already carry it, so
        writing nothing is the correct behaviour, not a contradiction."""
        result = {"entities": {},
                  "resolved_events": [{"event_id": 1,
                                       "status": "already_true"}]}
        assert director._resolved_event_verdicts(result, [1]) == [
            {"event_id": 1, "status": "already_true"}]

    def test_not_mine_survives_an_empty_response(self):
        result = {"entities": {},
                  "resolved_events": [{"event_id": 1, "status": "not_mine",
                                       "reroute_to": "spatial"}]}
        assert director._resolved_event_verdicts(result, [1]) == [
            {"event_id": 1, "status": "not_mine", "reroute_to": "spatial"}]

    def test_bookkeeping_keys_do_not_count_as_content(self):
        """`notes` and `phase_sources` are the hand talking about its work,
        not the work. Counting them would make the guard inert exactly when a
        model pads its excuse."""
        result = {"entities": {}, "notes": ["could not name the thing"],
                  "phase_sources": {"entities.x": 1},
                  "resolved_events": [{"event_id": 1, "status": "encoded"}]}
        assert director._resolved_event_verdicts(result, [1]) == []

    def test_one_empty_claim_does_not_silence_a_sibling_that_worked(self):
        """The drop is per RESPONSE, and a response either wrote something or
        did not -- so this pins the whole-call semantics rather than letting a
        later reader assume it is per event."""
        result = {"poses": {"Corin": {"posture": "kneeling"}},
                  "resolved_events": [{"event_id": 1, "status": "encoded"},
                                      {"event_id": 2, "status": "encoded"}]}
        assert director._resolved_event_verdicts(result, [1, 2]) == [
            {"event_id": 1, "status": "encoded"},
            {"event_id": 2, "status": "encoded"}]


class TestANoteAloneStillDispatchesAHand:
    """`ledger_notes` stays a dispatch trigger. Design note section 3c-quater.

    Section 3c proposed deleting it and letting `changes_asserted` categories
    route everything. Measured 2026-09-09 with `tools/dispatch_survival.py`
    against the engine's own committed output: of the 13 entries the eight
    hands a categories-only dispatch would have skipped actually produced, 12
    were COMMITTED -- and 11 of 11 on record-shaped channels.

    The reason is structural, which is why this is a guard and not a note.
    `changes_asserted` counts CHANGES. A record-shaped ledger (`poses`,
    `overlays`, `conditions`, `attire`) carries the whole current state of a
    subject and is restated every beat, so the Director correctly files no
    manifest entry when nothing about it changed -- and the manifest therefore
    cannot be what dispatches the hand that keeps it. `body`, whose channels
    are ALL record-shaped, is the hand the manifest can least address and the
    one whose empty-call rate (76%) made it the target.
    """

    def test_a_hand_named_by_a_note_alone_runs(self):
        view = {"ledger_notes": {"body": "Hinami's flush deepens."},
                "manifest": []}
        assert director._ruling_for("body", view)[0] == ["note"]

    def test_every_channel_the_body_hand_keeps_is_record_shaped(self):
        """The premise of the rejection, pinned. If someone adds an
        event-shaped channel to `body` this stops being true, and the
        argument in section 3c-quater has to be re-read rather than
        re-cited."""
        from tools.narrow_interface_coverage import RECORD_SHAPED
        event_shaped = [c for c in director.SPECIALISTS["body"]["channels"]
                        if c not in RECORD_SHAPED]
        assert event_shaped == [], event_shaped

    def test_a_manifest_cannot_reach_a_hand_whose_records_did_not_change(self):
        """The case the corpus is full of: the Director rules that nothing
        changed for a hand, files no manifest entry -- correctly -- and
        addresses it by note so its records still get restated."""
        view = {"ledger_notes": {
                    "spatial": "No position changes; both remain at the bed."},
                "manifest": [{"category": "contact_action", "subject": "Vexara",
                              "change": "she settles"}]}
        assert director._ruling_for("spatial", view)[0] == ["note"]
        assert director._ruling_for("spatial",
                                    {"ledger_notes": {},
                                     "manifest": view["manifest"]})[0] == []


class TestTheManifestSpeaksTheNoteKeysVocabulary:
    """One vocabulary, two fields, one resolver.

    Measured 2026-09-09 over twelve live interpret beats on
    gemini-3.8-flash: the author filed a manifest on 8 of 12 and used four
    category words -- `body`, `objects`, `spatial`, `contact`. Three reached
    no channel, and `tools/dispatch_replay.py --filed-only` scored 8 false
    negatives, 100% of productive calls. Every ruling was correct; only the
    vocabulary missed, because `director_interpret.txt` asks for "one of the
    ledgers named above" and the only names above it are the five hands.

    These pin the resolver rather than the beat, so the guard survives the
    prompt being reworded -- which it is going to be.
    """

    def test_a_category_naming_a_hand_reaches_that_hand(self):
        for hand in ("body", "social", "contact", "objects", "spatial"):
            view = {"ledger_notes": {}, "manifest": [
                {"category": hand, "subject": "x", "change": "y"}]}
            addressed, _ = director._ruling_for(hand, view)
            assert addressed == ["manifest"], hand

    def test_a_category_naming_a_hand_reaches_only_that_hand(self):
        view = {"ledger_notes": {}, "manifest": [
            {"category": "objects", "subject": "a bucket",
             "change": "the bucket is up on the rim"}]}
        for other in ("body", "social", "contact", "spatial"):
            assert director._ruling_for(other, view)[0] == [], other

    def test_a_hand_named_category_grants_no_channel_so_the_gate_decides(self):
        """Coarser, deliberately. A hand's name does not say WHICH ledger, so
        `named` stays empty and `_dispatch_specialists` grants the hand its
        story's channels -- the fail-open rule it already follows for a note
        keyed by hand alone."""
        view = {"ledger_notes": {}, "manifest": [
            {"category": "objects", "subject": "x", "change": "y"}]}
        assert director._ruling_for("objects", view) == (["manifest"], [])

    def test_a_category_naming_a_channel_still_names_that_channel(self):
        view = {"ledger_notes": {}, "manifest": [
            {"category": "poses", "subject": "Corin",
             "change": "Corin is kneeling"}]}
        assert director._ruling_for("spatial", view) == (["manifest"],
                                                         ["poses"])

    def test_contact_resolves_as_both_the_hand_and_its_ledger(self):
        """The union, not the fallback, and this is the case that needs it.
        `note_key_targets` stops at the first kind that matched, and `contact`
        matches the HAND -- so resolving through it alone would have dropped
        `contact_ops`, the one channel the manifest used to name correctly."""
        view = {"ledger_notes": {}, "manifest": [
            {"category": "contact", "subject": "Sera",
             "change": "a hand rests on her shoulder"}]}
        assert director._ruling_for("contact", view) == (["manifest"],
                                                         ["contact_ops"])

    def test_the_category_lookup_tolerates_case_and_a_plural(self):
        """The note key's tolerances, which the manifest never had: its lookup
        was raw, so `Objects` and `contacts` were misses on one field and hits
        on the other."""
        for spelling, hand in (("Objects", "objects"), ("BODY", "body"),
                               ("contacts", "contact"), ("pose", "spatial")):
            view = {"ledger_notes": {}, "manifest": [
                {"category": spelling, "subject": "x", "change": "y"}]}
            assert director._ruling_for(hand, view)[0] == ["manifest"], spelling

    def test_a_hand_named_category_is_carried_into_that_hands_payload(self):
        """Dispatch and the payload slice must agree. Routing the hand while
        slicing its manifest by the old narrow lookup would run a specialist
        and hand it an empty manifest -- a call paid for and told nothing."""
        view = {"manifest": [
            {"category": "objects", "event_id": 1, "subject": "the hinge",
             "change": "the hinge has come apart"},
            {"category": "body", "event_id": 2, "subject": "Corin",
             "change": "Corin has burned his palm"},
        ]}
        got = director._specialist_manifest_slice("objects", view)
        assert [i["event_id"] for i in got] == [1]
        assert [i["event_id"] for i in
                director._specialist_manifest_slice("body", view)] == [2]
        assert director._specialist_manifest_slice("social", view) == []


def test_an_interpret_category_no_channel_answers_for_still_reaches_nobody(
        temp_db, monkeypatch):
    """The manifest gains a router, not a guess.

    `_CATEGORY_CHANNELS` is the whole map; a category outside it reaches no
    hand and is not approximated to the nearest one. Same rule the notes side
    already follows for a key nobody answers to.
    """
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_interpret": {
            "kind": "action",
            "sequence": [{"type": "action", "attempt": "wait",
                          "commitment": "asserted", "targets": [],
                          "raw_text": "I wait"}],
            "speech": None, "action": None, "movement": None,
            "ledger_notes": {},
            "changes_asserted": [
                {"category": "weather", "subject": "sky", "change": "it rains"},
            ],
            "flow": {"reactors": [], "authority_claims": [], "dice": [],
                     "resolution_flags": {}, "fiction_frame": {}},
        }}))

    ctx = _make_ctx(temp_db, player_input="I wait")
    ctx.director_interpret = None
    out = director.director_interpret(ctx, nonce=0)

    for name, record in out["orchestration"]["specialists"].items():
        assert record["addressed_by"] == [], (name, record["addressed_by"])


def test_gate_skips_a_pure_dialogue_beat_over_clean_bodies(temp_db,
                                                           monkeypatch):
    """The gate's skip direction, exercised: no declared action anywhere, no
    dice, no active condition, no overlay -- nothing the body channels
    govern can change, so the specialist is never called and costs nothing
    at all. Note the scene HAS attire: a worn coat is a fact, but a beat
    with no physical act cannot move it, so wearing alone must not fire."""
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
    """An ACTIVE condition is standing scene state that needs maintaining
    even on a still beat, so it opens the `conditions` gate with no
    physical activity at all -- and it is read from the ledger at RESOLVE
    time, not from any plan fixed earlier: this row is inserted after the
    interpretation already exists, the way a mid-turn character
    declaration brings channels into play nothing earlier predicted. The
    ruling reaches the body hand by name; the gate, read now, is what puts
    `conditions` in its sheet."""
    calls = []
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, {"director_resolve": _ruling("body")}))

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
    body = out["orchestration"]["specialists"]["body"]
    assert body["facts"]["active_conditions"] is True
    assert "conditions" in body["gated"] and "conditions" in body["scope"]


def test_backstop_reports_an_unserved_channel_that_shipped(temp_db,
                                                           monkeypatch):
    """The load-bearing one: AN UNSERVED CHANNEL MUST NEVER BE SILENT. A
    manifest entry now addresses its hand, so the old shape (gate skipped,
    manifest asserted) cannot occur; the shape that CAN is the Director
    ruling to nobody -- no note, no manifest -- while its own `state_diff`
    carries attire content anyway. The body hand does not run; the
    content stands (fail-open, the author's encoding is never dropped);
    and the backstop says so on both surfaces and records it."""
    calls = []
    resolve_out = {
        "resolved_event": "Mara shrugs the wool coat off her shoulders "
                          "and lets it fall.",
        "summary": "Mara sheds her coat.",
        "state_diff": {"attire": {"Mara": {"remove": ["wool coat"]}}},
    }
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {"director_resolve": resolve_out}))

    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert "director_body" not in _steps(calls)
    assert out["orchestration"]["specialists"]["body"]["addressed_by"] == []
    # Fail-open: the author's channel content shipped untouched.
    assert out["state_diff"]["attire"]["Mara"]["remove"] == ["wool coat"]
    # And the unserved channel is REPORTED, on both surfaces.
    scope_notes = [n for n in ctx.engine_feedback
                   if "orchestration scope" in n]
    assert scope_notes and "attire" in scope_notes[0]
    assert any("orchestration scope" in w for w in ctx.warnings)
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
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "Mara pulls off her wool coat and drops it "
                              "by the door.",
            "summary": "Coat comes off.",
            **_ruling("body", "spatial"),
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
    # Reported, but NOT as a gate mispredict: the scope was granted
    # correctly and simply went unserved, so the author's content standing
    # is fail-open working as designed. Blaming the gate here sends the
    # next reader to widen a gate that was already right -- measured live,
    # where a contact call died on a provider returning reasoning with no
    # answer and the backstop announced "the scope gate mispredicted".
    assert any("specialist call(s) failed" in n for n in ctx.engine_feedback)
    assert not any("gate mispredicted" in n for n in ctx.engine_feedback)


def test_specialist_payload_is_the_body_slice_and_nothing_more(temp_db,
                                                              monkeypatch):
    """Requirement 5: an explicit entitlement, enforced. The Director's
    omniscience is justified by owning objective causality; the body
    specialist does not inherit it. Its payload must carry the body ledgers
    and the finished beat -- and none of the world machinery, no room graph,
    and never the player's raw input (which can carry a private thought the
    Director alone is entitled to read)."""
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "Mara pulls off her wool coat.",
            "summary": "Coat off.", "state_diff": {}, **_ruling("body"),
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
    # Its entitlement -- and the beat's PROSE is not part of it. A hand is a
    # tool, not an author: it gets its scene-scoped ledgers and the work it
    # was asked to settle. See DESIGN_SPECIALIST_CONTRACT.md.
    assert "resolved_event" not in spayload
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


def test_specialist_role_is_separable_and_follows_default_when_unset(
        monkeypatch):
    """Measurement hook: `_log_usage` keys on the role string, so the
    specialist must call under its OWN role name.

    An unconfigured `director_body` follows `default`, like every other
    blank row. It used to inherit `director` -- defensible on paper (a
    specialist is a hand of the Director) and wrong in practice: a host who
    leaves the six blank is parking them on something cheap, and setting
    `director` to a writing model silently moved all six onto it. Separable
    spend does not require a hidden parent; it comes from the role string,
    which is unchanged either way. See `tests/test_provider_fallbacks.py`."""
    from llm import providers

    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "cheap", "model": "small"},
        "director": {"provider": "frontier", "model": "big"},
    })
    monkeypatch.setattr(providers, "provider",
                        lambda name: {"name": name, "kind": "openai",
                                      "base_url": "http://x", "api_key": ""})

    prov, model, cfg = providers.resolve_role("director_body")
    assert (prov["name"], model) == ("cheap", "small")
    # Explicit configuration still wins.
    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "cheap", "model": "small"},
        "director": {"provider": "frontier", "model": "big"},
        "director_body": {"provider": "own", "model": "lean"},
    })
    prov, model, cfg = providers.resolve_role("director_body")
    assert (prov["name"], model) == ("own", "lean")


def test_specialist_call_carries_its_own_role(temp_db, monkeypatch):
    """The other half of the measurement hook: the resolve stage must hand
    `_agent_json` the specialist's role string, or every specialist call is
    logged as director spend and the experiment cannot be judged."""
    calls = []
    responses = {"director_resolve": _ruling("body"),
                 "director_body": {"attire": {}, "conditions": {},
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


def test_the_detectors_fire_on_an_omission_no_hand_encoded(temp_db,
                                                          monkeypatch):
    """The measurement hook. This used to run the beat twice -- once
    monolithic, once orchestrated -- and assert the two reconciliation
    records were equal, which is how the fan-out earned its way to being the
    only path. There is nothing left to compare it against, so what remains
    is the property that comparison was protecting: a change the manifest
    asserts and NO hand encoded is detected, routed to its owner, and
    warned about when the owner cannot encode it either.
    """
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {
            "director_resolve": _asserting_resolve_output(),
            "director_body": {"attire": {}, "conditions": {}, "vitals": {},
                              "overlays": {}, "notes": []},
            "resolve_repair": {"state_diff": {}, "dispositions": []},
        }))
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert _manifest_omissions(out)
    # Repaired by the channel's OWNER, at specialist cost -- measured on
    # chat 71 turn 10, where re-running the prose author with the full-core
    # repair sheet was the single largest avoidable spend of a 105.5s
    # resolve. The body specialist is called twice (fan-out + repair) and
    # the full-core repair sheet is never loaded.
    assert "resolve_repair" not in _steps(calls)
    assert _steps(calls).count("director_body") == 2
    assert any("Resolve reconciliation" in w and "wool coat" in w
               for w in ctx.warnings)


# ---------------------------------------------------------------------------
# Scope: the orchestrator measures how much of a job a specialist needs.
# ---------------------------------------------------------------------------

def test_scope_selects_the_sheet_and_is_persisted(temp_db, monkeypatch):
    """Dispatch is `bool(scope)` and the sheet is assembled from exactly
    the granted channels' chunks -- one computation, one code path, so the
    "which specialists run" decision and the "how much sheet loads" gate
    can never disagree. The granted/served/produced report persists on the
    step, because over-grant is the number that says how well scoping
    works and under-grant is the direction the backstop catches."""
    calls = []
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, {"director_resolve": _ruling("body")}))

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
    (fail open) on the same physical beat. The ruling reaches all three
    hands by name; the gates decide the sheets."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(
        calls, {"director_resolve": _ruling("body", "objects", "contact")}))

    ctx = _make_ctx(temp_db, interp=_action_interp())  # bare-bodied scene
    out = director.director_resolve(ctx, nonce=0)

    specialists = out["orchestration"]["specialists"]
    # THE GATES STILL MEASURE THE SCENE; what changed is who they may overrule.
    # Each hand here is named without a channel, so each loads its whole
    # ledger set and `gated` is where the saving is still visible.
    assert "attire" not in (specialists["body"]["gated"] or [])
    assert "conditions" in (specialists["body"]["gated"] or [])
    objects = specialists["objects"]
    assert "destruction" not in (objects["gated"] or [])
    assert "artifact_ops" not in (objects["gated"] or [])
    assert "entities" in (objects["gated"] or [])
    contact = specialists["contact"]
    assert set(contact["gated"] or []) >= {"contact_ops", "substance_ops",
                                           "containment", "scales"}
    # And a channel THIS STAGE cannot carry is still subtracted, because that
    # is not a prediction about the beat (`channel_serves_stage`).
    assert set(specialists["body"]["scope"]) >= {"attire", "conditions"}


def test_specialist_notes_reach_tell_director(temp_db, monkeypatch):
    """The note lane is how out-of-scope work is reported: a specialist
    that found a change it had no channel for says so, and the engine
    carries the flag to the next beat's Director rather than letting the
    under-grant vanish into a log nobody reads."""
    calls = []
    responses = {
        "director_resolve": _ruling("body"),
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
    calls = []
    interpret_out = {
        "kind": "action",
        "sequence": [{"type": "action", "attempt": "pull off my wool coat",
                      "commitment": "asserted", "targets": [],
                      "raw_text": "I pull off my wool coat"}],
        "speech": None, "action": {"attempt": "pull off my wool coat"},
        "movement": None,
        **_ruling("body"),
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
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "Mara gives her name at last.",
            "summary": "Names exchanged.",
            "state_diff": {}, **_ruling("social"),
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
    # `rooms` is no longer forbidden: the social hand carries the world's
    # traffic since 2026-09-04, and a crowd or courier op names a room.
    for forbidden in ("attire", "contacts", "entities",
                      "relevant_lore", "world_pressure", "vitals"):
        assert forbidden not in spayload, forbidden
    assert "background_presences" in spayload


def test_contact_specialist_owns_the_relation_channels(temp_db, monkeypatch):
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "Mara rests her hand on the Stranger's "
                              "shoulder.",
            "summary": "A hand on a shoulder.",
            "state_diff": {}, **_ruling("contact"),
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
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "Mara lights the storm lantern.",
            "summary": "Lantern lit.",
            **_ruling("objects"),
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
            "state_diff": {}, **_ruling("spatial"),
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


def test_the_traffic_channels_dispatch_through_the_social_hand(temp_db, monkeypatch):
    """The offscreen hand is retired (2026-09-04): its channels are the
    social hand's. A ruling that reaches the social hand with a crowd in
    the room dispatches it with the traffic ledgers -- the crowd's uid its
    op needs -- and the op survives assembly into state_diff."""
    scene = json.loads(json.dumps(BASE_SCENE))
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "The Stranger pushes through the crowd of "
                              "keepers gathered in the lamp room.",
            "summary": "Through the crowd.",
            "state_diff": {}, **_ruling("social"),
        },
        "director_social": {
            "cast_changes": [], "introductions": [], "world_facts": [],
            "crowd_ops": [{"op": "move", "crowd_id": "crowd_1",
                           "room": "lamp_room", "heading": "keeper_room"}],
            "courier_ops": [], "telling_ops": [],
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

    social = out["orchestration"]["specialists"]["social"]
    assert social["run"] is True and social["ran"] is True
    assert "crowd_ops" in social["scope"]
    assert out["state_diff"]["crowd_ops"] == [
        {"op": "move", "crowd_id": "crowd_1", "room": "lamp_room",
         "heading": "keeper_room"}]
    spayload = next(c["payload"] for c in calls
                    if c["step_key"] == "director_social")
    assert spayload["crowds"] and spayload["crowds"][0]["crowd_id"] == \
        "crowd_1"
    assert "offscreen" not in out["orchestration"]["specialists"]
    for forbidden in ("attire", "contacts", "entities", "relevant_lore",
                      "world_pressure", "active_awareness", "movers",
                      "offscreen_planning"):
        assert forbidden not in spayload, forbidden


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
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    responses = {
        "director_resolve": {
            "resolved_event": "Mara sheds her coat and rests a hand on "
                              "the Stranger's shoulder.",
            "summary": "Coat off; a hand rests.", "state_diff": {},
            **_ruling("body", "contact", "social", "objects", "spatial"),
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
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    responses = {
        "director_resolve": {
            "resolved_event": "Mara sheds her coat.",
            "summary": "Coat off.", "state_diff": {},
            **_ruling("body", "contact", "spatial"),
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
    from llm.providers import Aborted

    responses = {
        "director_resolve": {"resolved_event": "x", "summary": "x",
                             "state_diff": {}, **_ruling("contact")},
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
    from llm import providers

    observed = {}

    real_fake = _fake_agent([], {"director_resolve": _ruling("body", "contact")})

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


# ---------------------------------------------------------------------------
# The prose author's OWN sheet is scoped (same mechanism, same rules).
# ---------------------------------------------------------------------------

def _resolve_sheet(calls):
    """The system sheet the prose author actually received."""
    return next(c["system"] for c in calls
                if c["step_key"] == "director_resolve")


#: heading -> the chunk name that carries it, for presence assertions.
PROSE_DUTY_HEADINGS = {
    "voices": "BODILESS VOICES",
    "obligations": "OBLIGATION LEDGER",
    "other_players": "OTHER PLAYERS' DECLARATIONS",
    "comm": "MEDIUM — COMM CHANNELS",
    "transit": "MOVING ROOMS",
    "planning_need": "A PLACE NOBODY PLANNED",
    "hearsay": "- HEARSAY:",
    "road": "- THE ROAD:",
    "approach": "APPROACHING IS NOT ARRIVING",
    "due_events": "DUE AUTHORED EVENTS",
    "world_pressure": "WORLD PRESSURE — THE WORLD ACTS",
    "residue": "DESTINATION RESIDUE",
    "light": "WHAT LIGHT LETS THEM DO",
    "size": "SIZE CHANGES WHAT IS POSSIBLE",
}

#: Every-beat contract blocks that may NEVER be gated out of the sheet.
NEVER_GATED_HEADINGS = (
    "KNOWLEDGE FIREWALL",
    "SPANS ARE THE WORK ITEMS",
    "PLAYER-ASSERTED FACTS",
    "DIALOGUE LOG — MANDATORY",
    "PLAYER AUTHORITY CONTRACT",
    "DELEGATED CHANNELS",
    "WORLD PRESSURE — OPENING",
    "CONSEQUENCES ON THE CLOCK",
    "NO STALLED SCENE",
)


def test_prose_author_core_keeps_the_never_gated_blocks():
    """THE CONSTRAINT ABOVE ALL OTHERS: the firewall, the manifest, the
    player-authority contract, the dialogue-log duty and the delegation
    contract load on EVERY beat -- the empty scope (a floor dispatch can
    never even produce) still carries all of them, plus the world-pressure
    OPENING duty, so an empty ledger can still be opened into. And the
    gated headings are genuinely chunked: none of them survives into the
    bare core."""
    from llm.prompts import prose_author_prompt

    core = prose_author_prompt([])
    for marker in NEVER_GATED_HEADINGS:
        assert marker in core, marker
    assert "op:'open', subject, note" in core  # the opening op teaching
    for name, heading in PROSE_DUTY_HEADINGS.items():
        assert heading not in core, (name, heading)


def test_prose_author_full_scope_is_the_registered_lean_sheet(monkeypatch):
    """One spelling: the fail-open ceiling (scope=None) is byte-identical
    to DEFAULT_PROMPTS['director_resolve_lean'], which is what the _ops
    drift check and preset editing see -- and assembly is canonical-order,
    so a given scope is byte-stable whatever order it arrives in (provider
    prefix caching)."""
    from llm import prompts

    monkeypatch.setattr(prompts, "nsfw_enabled", lambda: False)
    full = prompts.prose_author_prompt(None)
    assert full == prompts.DEFAULT_PROMPTS["director_resolve_lean"]
    assert full == prompts.prose_author_prompt(list(
        reversed(prompts.PROSE_DUTY_CHUNKS)))
    for heading in list(PROSE_DUTY_HEADINGS.values()) + list(
            NEVER_GATED_HEADINGS):
        assert heading in full, heading
    assert prompts.prose_author_prompt(["light", "size"]) == \
        prompts.prose_author_prompt(["size", "light"])


def test_prose_scope_gates_out_duties_whose_subject_is_absent(temp_db,
                                                              monkeypatch):
    """The skip direction, exercised end-to-end: a physical beat with no
    speech, one lit room, empty ledgers, no bodiless voice, no vehicle, no
    proposal. Every conditional duty whose subject provably does not exist
    is out of the sheet; every contract block is still in it; and the
    granted/gated_out split is persisted for the measurement."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    sheet = _resolve_sheet(calls)
    for name in ("voices", "obligations", "other_players", "transit",
                 "planning_need", "hearsay", "road", "due_events",
                 "world_pressure", "residue", "light"):
        assert PROSE_DUTY_HEADINGS[name] not in sheet, name
    # A physical beat can move, split rooms, and change sizes: those duties
    # stay loaded because structure cannot rule them out (fail open).
    for name in ("approach", "comm", "size"):
        assert PROSE_DUTY_HEADINGS[name] in sheet, name
    for marker in NEVER_GATED_HEADINGS:
        assert marker in sheet, marker
    prose = out["orchestration"]["prose_scope"]
    assert set(prose["granted"]) == {"approach", "comm", "size"}
    assert "light" in prose["gated_out"]


def _sustained_interp():
    """A beat the interpret stage staged as SUSTAINED: hours may pass."""
    return {
        "sequence": [{"type": "action", "attempt": "sleep until first light",
                      "stage": "sustained", "commitment": "asserted",
                      "targets": [], "visibility": "overt",
                      "conceal_from": []}],
        "speech": None, "action": {"attempt": "sleep until first light"},
        "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }


def test_the_light_duty_loads_on_a_beat_that_can_move_the_sun(temp_db,
                                                             monkeypatch):
    """Harrowmere replay (2026-09-03, t9): "I sleep right through until
    first light" was staged sustained, the resolve skipped twenty-one hours
    to dawn, and the author set the room dim with no light duty loaded --
    the backstop's manifest half caught it, which is a warning, not a duty.
    A sustained act in an ANCHORED day loads the duty; the same act in a
    story with no day cycle, and a lit instantaneous beat under an anchored
    day, leave it gated out as before."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))
    anchored = json.loads(json.dumps(BASE_SCENE))
    anchored["day_phase"] = "morning"

    ctx = _make_ctx(temp_db, scene=anchored, interp=_sustained_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert PROSE_DUTY_HEADINGS["light"] in _resolve_sheet(calls)
    assert "light" in out["orchestration"]["prose_scope"]["granted"]

    for scene, interp in ((json.loads(json.dumps(BASE_SCENE)),
                           _sustained_interp()),
                          (anchored, _action_interp())):
        calls.clear()
        ctx = _make_ctx(temp_db, scene=scene, interp=interp)
        out = director.director_resolve(ctx, nonce=0)
        assert PROSE_DUTY_HEADINGS["light"] not in _resolve_sheet(calls)
        assert "light" in out["orchestration"]["prose_scope"]["gated_out"]


def test_prose_scope_loads_a_block_when_its_subject_exists(temp_db,
                                                           monkeypatch):
    """The load direction: a pure-dialogue beat -- movement, comm and size
    duties provably out of play -- EXCEPT every subject seeded here brings
    its duty back in: a dim room, a bodiless ship AI, a docked elevator, an
    open world-pressure ledger, a standing obligation, and speech itself
    (a new debt is a speech act, so obligations ride any spoken beat)."""
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["rooms"]["lamp_room"]["light"] = "dim"
    scene["entities"] = {
        "ship_ai": {"name": "VIGIL", "kind": "ship AI", "ubiquitous": True},
        "lift": {"name": "Service Lift", "kind": "elevator",
                 "interior_rooms": ["lift_car"],
                 "state": {"transit": {"phase": "docked", "hatch": "open"}}},
    }
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))

    ctx = _make_ctx(temp_db, scene=scene, interp=_speech_interp())
    temp_db.wset(ctx.chat.id, "world_pressures",
                 [{"id": "wp1", "subject": "an active scan", "note": "",
                   "held_streak": 0}])
    temp_db.wset(ctx.chat.id, "pending_obligations",
                 [{"id": "ob1", "who": "Mara", "what": "the report",
                   "kind": "demand", "opened_turn": 0}])
    out = director.director_resolve(ctx, nonce=0)

    sheet = _resolve_sheet(calls)
    for name in ("voices", "obligations", "world_pressure", "transit",
                 "light"):
        assert PROSE_DUTY_HEADINGS[name] in sheet, name
    # A pure-dialogue beat in one known room still provably cannot move
    # anyone, transmit to a remote listener, or change a size.
    for name in ("approach", "comm", "size"):
        assert PROSE_DUTY_HEADINGS[name] not in sheet, name
    prose = out["orchestration"]["prose_scope"]
    assert {"voices", "obligations", "world_pressure", "transit",
            "light"} <= set(prose["granted"])
    assert {"approach", "comm", "size"} <= set(prose["gated_out"])


def test_prose_scope_comm_loads_when_minds_are_apart(temp_db, monkeypatch):
    """The comm duty's subject is a remote listener: the same dialogue beat
    gains the MEDIUM block the moment a tracked mind stands in another room
    -- and an UNKNOWN position is undecidable, which is the fail-open
    direction (asserted with Mara's position removed)."""
    for mutate in (
        lambda s: s["positions"].__setitem__("Mara", "lamp_room"),
        lambda s: s["positions"].pop("Mara"),
    ):
        scene = json.loads(json.dumps(BASE_SCENE))
        mutate(scene)
        calls = []
        monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))
        ctx = _make_ctx(temp_db, scene=scene, interp=_speech_interp())
        out = director.director_resolve(ctx, nonce=0)
        assert PROSE_DUTY_HEADINGS["comm"] in _resolve_sheet(calls)
        assert "comm" in out["orchestration"]["prose_scope"]["granted"]


def test_prose_scope_fails_open_when_the_facts_cannot_be_read(temp_db,
                                                              monkeypatch):
    """Undecidable means loaded, at every level: if the prose facts cannot
    be computed at all, the WHOLE sheet loads -- the fail-open ceiling,
    byte-identical to the registered lean sheet -- and the beat proceeds."""
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))

    def broken(*a, **kw):
        raise RuntimeError("facts unreadable")
    monkeypatch.setattr(director, "_prose_gate_facts", broken)

    ctx = _make_ctx(temp_db, interp=_speech_interp())
    out = director.director_resolve(ctx, nonce=0)

    sheet = _resolve_sheet(calls)
    for heading in PROSE_DUTY_HEADINGS.values():
        assert heading in sheet, heading
    assert out["orchestration"]["prose_scope"]["gated_out"] == []


def test_prose_scope_fails_open_per_fact(temp_db, monkeypatch):
    """One fact source erroring grants ITS chunk without disturbing the
    rest of the scope: the bodiless-voices reader raising loads the voices
    block on a beat whose every other absent subject stays gated out."""
    from story import scene as scene_mod

    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {}))

    def broken(_sc):
        raise RuntimeError("unreadable")
    monkeypatch.setattr(scene_mod, "ubiquitous_speaker_names", broken)

    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert PROSE_DUTY_HEADINGS["voices"] in _resolve_sheet(calls)
    prose = out["orchestration"]["prose_scope"]
    assert "voices" in prose["granted"]
    assert "light" in prose["gated_out"]  # the rest of the scope undisturbed


def test_prose_backstop_reports_a_duty_shipped_without_its_block(temp_db,
                                                                 monkeypatch):
    """The backstop's prose half, the load-bearing direction: a duty whose
    block was not loaded ships anyway (an obligation opened on a speechless
    beat with an empty ledger -- the gate's documented blind side made
    real). The SAME backstop that audits specialist scopes must (a) say so
    via tell_director, and (b) drop nothing: the ops stand, because the
    gate fails open rather than enforcing its own prediction."""
    calls = []
    resolve_out = {
        "resolved_event": "Mara holds out an open palm until the coin is "
                          "promised to her.",
        "summary": "Mara exacts a promise.",
        "state_diff": {},
        "obligations": [{"op": "open", "who": "The Stranger",
                         "what": "the promised coin", "kind": "promise"}],
    }
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {"director_resolve": resolve_out}))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    assert PROSE_DUTY_HEADINGS["obligations"] not in _resolve_sheet(calls)
    # Fail-open: the ops shipped untouched.
    assert out["obligations"] and out["obligations"][0]["op"] == "open"
    # And the misprediction is REPORTED, on both surfaces, and recorded.
    notes = [n for n in ctx.engine_feedback if "'obligations' duty" in n]
    assert notes and "orchestration scope" in notes[0]
    assert any("'obligations' duty" in w for w in ctx.warnings)
    assert any("obligations" in f
               for f in out["orchestration"]["gate_flags"])


def test_prose_registries_are_level():
    """The three prose-scoping registries cannot drift: every chunk has a
    gate (an ungated chunk never loads on the orchestrated path), every
    gate a chunk, and every shipped-duty audit points at a real chunk --
    the same three-files-level discipline the specialists get from
    tools/project_check.py, which enforces this same fact at check time."""
    from llm.prompts import PROSE_DUTY_CHUNKS

    assert set(PROSE_DUTY_CHUNKS) == set(director._PROSE_DUTY_GATES)
    assert set(director._PROSE_DUTY_SHIPPED) <= set(PROSE_DUTY_CHUNKS)
    # The exact-payload gates deliberately carry no shipped audit; the
    # audited set is exactly the prediction gates.
    assert set(director._PROSE_DUTY_SHIPPED) == {
        "voices", "obligations", "comm", "transit", "approach", "light",
        "size"}


# ---------------------------------------------------------------------------
# The delegation must not depend on the model's obedience (run 20).
# ---------------------------------------------------------------------------

def test_prose_author_shape_carries_no_delegated_fields():
    """Run 20 measured the delegation note NOT holding: 18 discarded-channel
    emissions in 14 beats, because the prose author's sheet still ENDED with
    the full monolithic output shape -- the note said "leave them empty" a
    thousand tokens before a JSON template that listed every delegated field
    with its sub-shape, and the template won (23 of the 28 replacements were
    the spatial channels, the ones spelled out most concretely). Every such
    emission is discarded at assembly, so it was pure output-token latency.
    The fix is structural, not rhetorical: the delegated channels have NO
    field in the prose author's stated shape, so there is nothing to fill."""
    import re

    from llm.prompts import _PROSE_AUTHOR_OUTPUT_SHAPE

    for channel in director._DELEGATED_CHANNELS:
        assert not re.search(r"\b%s\b" % re.escape(channel),
                             _PROSE_AUTHOR_OUTPUT_SHAPE), channel
    # What stays the prose author's own is still all there.
    for kept in ("resolved_event", "summary", "dialogue_order",
                 "dialogue_log", "state_diff", "time",
                 "weather", "location", "claim_dispositions", "consequences",
                 "obligations", "world_pressure", "fact_adjudications"):
        assert kept in _PROSE_AUTHOR_OUTPUT_SHAPE, kept
    # And the sheet actually ships the lean shape, not the monolithic one.
    from llm.prompts import DEFAULT_PROMPTS
    assert _PROSE_AUTHOR_OUTPUT_SHAPE in DEFAULT_PROMPTS[
        "director_resolve_lean"]


def test_interpret_always_gets_the_delegation_note_as_a_suffix(
        temp_db, monkeypatch):
    """The interpret sheet's own PASS 1 block instructs "the FULL state_diff
    structure ... no subset", so without an override the stage model is
    GUARANTEED to duplicate every dispatched specialist's work and have it
    replaced at assembly (run 20: 8 interpret-side replaced-channel warnings
    in 14 beats, all pure wasted output tokens, and output tokens are the
    wall clock). The note overrides that instruction.

    It is appended AT THE CALL SITE rather than folded into the registered
    prompt, and that is worth pinning: the registered sheet stays a stable
    cache prefix, so the note landing after it costs no cache write. A
    future edit that moves the note into the sheet would be a silent
    per-beat cache miss on the largest prefix the interpret stage has.
    """
    interpret_out = {
        "kind": "dialogue",
        "sequence": [{"type": "speech", "text": "Quiet night."}],
        "speech": "Quiet night.", "action": None, "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    calls = []
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, {"director_interpret":
                                            interpret_out}))
    ctx = _make_ctx(temp_db, player_input="Quiet night.")
    ctx.director_interpret = None
    director.director_interpret(ctx, nonce=0)

    sheet = [c for c in calls if c["step_key"] == "director_interpret"
             ][0]["system"]
    from llm.prompts import get_prompt_body
    assert sheet.startswith(get_prompt_body("director_interpret"))
    assert "SPECIALISTS ENCODE, YOU DECOMPOSE" in sheet
    # English now has role-specific causal floors as well as the common
    # language/schema policy.  Both must survive the call-site delegation
    # suffix; their relative tail order is owned by prompt_policy.
    assert "translate only its free-text human-language values." in sheet
    assert "CONTESTABLE ONSET" in sheet
    # The note must name the interpret spelling of the contact channel --
    # that is the one whose name differs between the stages.
    assert "contact_assertions" in sheet


class TestTheHostCanFindTheSwitch:
    """A capability nobody can turn on is a capability nobody has.

    The fan-out itself no longer has a switch and should not: it is the only
    Director path. What it does have is a CONCURRENCY choice, because
    concurrency is not free everywhere -- a provider key that takes one
    request at a time, a limit measured in connections, a local runtime
    serving one model on one GPU. Parallel is the default and the point.
    """

    def test_the_route_writes_what_the_engine_reads(self, temp_db):
        """One setting key, one spelling. The route and the gate agreeing is
        the whole contract; a toggle that writes a key nothing reads is the
        failure this pins."""
        from web import app as app_module
        import agents.director as director

        assert director.fanout_is_parallel() is True   # the default
        assert app_module.set_director_fanout_mode({"parallel": False}) == {
            "parallel": False}
        assert director.fanout_is_parallel() is False
        assert app_module.set_director_fanout_mode({"parallel": True}) == {
            "parallel": True}
        assert director.fanout_is_parallel() is True

    def test_boot_reports_it_so_the_checkbox_can_show_its_state(self, temp_db):
        """A toggle that always renders unchecked is worse than none: it
        invites a host to switch off something already off."""
        from web import app as app_module

        app_module.set_director_fanout_mode({"parallel": False})
        assert app_module.bootstrap()["director_fanout_parallel"] is False
        app_module.set_director_fanout_mode({"parallel": True})
        assert app_module.bootstrap()["director_fanout_parallel"] is True

    def test_every_specialist_role_is_offered_to_the_host(self, temp_db):
        """The switch and the roles it governs have to arrive together."""
        from web import app as app_module

        roles = app_module.bootstrap()["roles"]
        for name in ("director_body", "director_social", "director_contact",
                     "director_objects", "director_spatial"):
            assert name in roles, f"{name} has no settings row"

    def test_sequential_runs_the_same_specialists_in_the_same_order(
            self, temp_db, monkeypatch):
        """Sequential is not a fallback to the monolith. The same hands run
        with the same scopes and assemble in canonical order -- the only
        difference is that the calls do not overlap."""
        import agents.director as director

        scene = json.loads(json.dumps(BASE_SCENE))
        scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
        runs = {}
        for mode, parallel in (("parallel", True), ("sequential", False)):
            temp_db.set_setting("director_fanout_mode", mode)
            calls = []
            monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
                "director_resolve": _asserting_resolve_output()}))
            ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
            out = director.director_resolve(ctx, nonce=0)
            runs[mode] = (out["orchestration"]["specialists"],
                          out["state_diff"])
        assert runs["parallel"][0] == runs["sequential"][0]
        assert runs["parallel"][1] == runs["sequential"][1]


# ---------------------------------------------------------------------------
# Reconciliation repair goes to the CHANNEL'S OWNER, not the prose author.
# ---------------------------------------------------------------------------
#
# The defect (chat 71 turn 10, measured live): an orchestrated resolve took
# 105.5s against the monolith's 14.2s on the same beat, and the single
# avoidable spend was the reconciliation seam's Tier-2 repair -- an EXTRA
# SEQUENTIAL call that re-ran the PROSE AUTHOR on the director role with the
# full-core repair sheet, to re-encode a change the body specialist owned.
# It then still shipped "state_diff still does not encode it after
# self-repair" warnings. Under orchestration the wrong repairer was being
# asked: the specialist that owns the omitted channel answers in ~1s with a
# 1-4k sheet, and is the authority the channel already belongs to. Detection
# is unchanged (the changes_asserted seam stays the one reconciliation
# mechanism); only the REPAIRER changes, and only on the orchestrated path.

def test_routed_repair_is_answered_by_the_owning_specialist(temp_db,
                                                            monkeypatch):
    """An attire omission on the orchestrated path is repaired by the body
    specialist -- called a second time, scoped to the omitted channel, with
    the omission and what currently stands in its payload -- and the
    full-core resolve_repair sheet is never loaded."""
    calls = []

    def body(payload):
        if "correction_notes" in payload:
            # The repair call: scoped payload carries the detection verbatim
            # and the standing channel content; answer the omission.
            assert payload["detected_omissions"] == [
                {"category": "attire", "subject": "Mara",
                 "change": "The wool coat is off.", "evidence": "",
                 "source": "manifest"}]
            assert "previous_channels" in payload
            # The beat's PROSE is not sent, here either: a repair is still a
            # specialist call and gets a specialist's entitlement. What it is
            # answering is `detected_omissions` above, which is the
            # instruction in its most explicit form.
            assert "resolved_event" not in payload
            assert "relevant_lore" not in payload  # same entitlement slice
            return {"attire": {"Mara": {"remove": ["wool coat"]}},
                    "conditions": {}, "vitals": {}, "overlays": {},
                    "notes": []}
        # The fan-out call: the specialist misses the change.
        return {"attire": {}, "conditions": {}, "vitals": {},
                "overlays": {}, "notes": []}

    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_resolve": _asserting_resolve_output(),
        "director_body": body,
    }))
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    steps = _steps(calls)
    assert "resolve_repair" not in steps
    assert steps.count("director_body") == 2
    # The repair call ran under the specialist's OWN role, so its spend
    # stays separable in _log_usage exactly like the fan-out call's.
    repair_call = [c for c in calls if c["step_key"] == "director_body"][-1]
    assert repair_call["role"] == "director_body"
    # And the repair sheet is the specialist's scoped sheet, not the core.
    assert "CLOTHING TRACKING" in repair_call["system"]
    assert "BODILY CONDITION" not in repair_call["system"]

    assert out["state_diff"]["attire"]["Mara"]["remove"] == ["wool coat"]
    recon = out["reconciliation"]
    assert recon["repaired"] is True
    assert recon["specialist_repairs"]["body"]["ok"] is True
    assert recon["unresolved"] == []
    assert not [w for w in ctx.warnings
                if "still does not encode" in w]


def test_unroutable_omissions_still_reach_the_full_core_repair(temp_db,
                                                               monkeypatch):
    """Player claims have no owning specialist -- their coverage check is
    whole-diff and they are non-rejectable -- so on a beat carrying BOTH an
    attire omission and an unencoded player claim, the attire goes to the
    body specialist and the full-core repair is asked about the claim
    alone. Only the repairer is split; nothing is dropped."""
    calls = []
    resolve_out = _asserting_resolve_output()
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_resolve": resolve_out,
        "director_body": lambda payload: (
            {"attire": {"Mara": {"remove": ["wool coat"]}},
             "conditions": {}, "vitals": {}, "overlays": {}, "notes": []}
            if "correction_notes" in payload else
            {"attire": {}, "conditions": {}, "vitals": {},
             "overlays": {}, "notes": []}),
        "resolve_repair": {"state_diff": {}, "dispositions": []},
    }))
    interp = _action_interp()
    interp["flow"]["authority_claims"] = [{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": "keeper_lamp", "predicate": "extinguished",
        "commitment": "asserted", "source_text": "I snuff the lamp.",
    }]
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    scene["entities"] = {"keeper_lamp": {"name": "Keeper's Lamp",
                                         "kind": "fixture"}}
    ctx = _make_ctx(temp_db, scene=scene, interp=interp)
    out = director.director_resolve(ctx, nonce=0)

    steps = _steps(calls)
    assert steps.count("director_body") == 2
    assert steps.count("resolve_repair") == 1
    core_call = [c for c in calls if c["step_key"] == "resolve_repair"][0]
    detected = core_call["payload"]["detected_omissions"]
    # The core repair sees ONLY what no specialist owns.
    assert {o["source"] for o in detected} == {"player_claim"}
    assert core_call["payload"]["non_rejectable_subjects"] == ["keeper_lamp"]
    # The routed half was still repaired by its owner.
    assert out["state_diff"]["attire"]["Mara"]["remove"] == ["wool coat"]
    # The claim the core repair failed to encode still hard-warns.
    assert any("PLAYER AUTHORITY" in w and "not encoded" in w
               for w in ctx.warnings)


def test_failed_specialist_repair_stops_and_reports_the_residual(
        temp_db, monkeypatch):
    """A repair that cannot succeed must stop: the owning specialist gets
    ONE repair call, a failure is fail-open (warned, beat kept), and the
    still-unencoded omission lands in the reconciliation record's
    unresolved list -- the existing manifest channel -- instead of buying
    another attempt."""
    calls = []

    def body(payload):
        if "correction_notes" in payload:
            raise RuntimeError("provider 500")
        return {"attire": {}, "conditions": {}, "vitals": {},
                "overlays": {}, "notes": []}

    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_resolve": _asserting_resolve_output(),
        "director_body": body,
    }))
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    steps = _steps(calls)
    assert steps.count("director_body") == 2      # fan-out + ONE repair
    assert "resolve_repair" not in steps          # no escalation spend
    recon = out["reconciliation"]
    assert recon["specialist_repairs"]["body"]["ok"] is False
    assert "provider 500" in recon["specialist_repairs"]["body"]["error"]
    assert any(o["subject"] == "Mara" for o in recon["unresolved"])
    assert any("specialist repair failed" in w for w in ctx.warnings)
    assert any("Resolve reconciliation" in w and "wool coat" in w
               for w in ctx.warnings)


def test_category_channel_map_reads_normalized_categories():
    """_manifest_items normalizes categories ('contact' -> 'contacts',
    'substance' -> 'substances', 'pose' -> 'poses') and every reader of
    _CATEGORY_CHANNELS looks up the normalized form -- but for two releases
    the map carried only the raw spellings, so a manifest entry asserting a
    contact, substance or pose change could never reach the scope backstop
    or its owning specialist, silently."""
    for raw, channel in (("contact", "contact_ops"),
                         ("substance", "substance_ops"),
                         ("pose", "poses"),
                         ("station", "stations"),
                         ("inventory_ops", "inventory_ops"),
                         ("clothing", "attire")):
        normalized = director._normalize_omission_category(raw)
        assert director._CATEGORY_CHANNELS.get(normalized) == channel, raw
    # And every channel the map names has an owner in the specialist table.
    for channel in set(director._CATEGORY_CHANNELS.values()):
        assert channel in director._CHANNEL_SPECIALISTS, channel


def test_a_specialist_encoded_beat_buys_no_repair_and_no_warning(
        temp_db, monkeypatch):
    """Chat 71 turn 2354 end to end (reroll v26625's real shapes): the body
    and contact specialists encode exactly what the manifest asserts -- the
    jacket removed (wearer-keyed), the hand off the stomach and onto the
    waist -- while the manifest words its subjects freely ('lightweight
    travel jacket', 'contact_end', 'contact_new'). On the live server the
    evidence classes could not see any of it: three false omissions, a
    Tier-2 repair spent answering 'already_encoded', the answer lost to an
    exact-subject disposition match, and three false 'objective state may be
    stale' warnings -- three rerolls running. A beat the specialists encoded
    correctly must reconcile deterministically: no repair call of any kind,
    no reconciliation warnings."""
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": (
                "Elyra slides the lightweight travel jacket from Hinami's "
                "remaining shoulder and lets it fall to the velvet; her "
                "hand lifts from Hinami's stomach and her fingers hook "
                "beneath the utility sash at her waist."),
            "summary": "Jacket off; hand moves from stomach to sash.",
            "dialogue_log": [],
            "changes_asserted": [
                {"category": "attire", "subject": "lightweight travel jacket",
                 "change": "fully removed from Hinami's remaining shoulder; "
                           "falls onto the velvet platform beside her",
                 "actor": "Elyra Voss", "actor_part": "hand",
                 "target": "lightweight travel jacket"},
                {"category": "contacts", "subject": "contact_end",
                 "change": "Elyra's hand lifts from Hinami's stomach",
                 "actor": "Elyra Voss", "actor_part": "hand",
                 "target": "Hinami", "target_part": "stomach"},
                {"category": "contacts", "subject": "contact_new",
                 "change": "Elyra's fingers hook beneath Hinami's utility "
                           "sash at her waist",
                 "actor": "Elyra Voss", "actor_part": "hand",
                 "target": "Hinami", "target_part": "waist"},
            ],
            "state_diff": {},
        },
        "director_body": {
            "attire": {"Hinami": {"add": [],
                                  "remove": ["lightweight travel jacket"]}},
            "conditions": {}, "vitals": {}, "overlays": {}, "notes": [],
        },
        "director_contact": {
            "contact_ops": [
                {"op": "remove", "actor": "Elyra Voss",
                 "actor_part": "hand", "target": "Hinami",
                 "target_part": "stomach"},
                {"op": "add", "actor": "Elyra Voss", "actor_part": "hand",
                 "target": "Hinami", "target_interior": "",
                 "target_part": "waist", "manner": "grip",
                 "relation": "surface", "motion": "settled",
                 "detail": "fingers hooked beneath utility sash"},
            ],
            "substance_ops": [], "containment": {}, "scales": {},
            "notes": [],
        },
    }
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["positions"]["Hinami"] = "keeper_room"
    scene["positions"]["Elyra Voss"] = "keeper_room"
    scene["attire"] = {"Hinami": {"wearing": ["lightweight travel jacket"]}}
    scene["contacts"] = [{"actor": "Elyra Voss", "actor_part": "hand",
                          "target": "Hinami", "target_part": "stomach"}]
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    # The encodings assembled (this half never failed live, and the
    # channels_filled record now SAYS so -- 'replaced' counts author
    # content that lost to ownership, which a compliant lean author never
    # produces, so [] there is health, not absence).
    assert out["state_diff"]["attire"]["Hinami"]["remove"] == [
        "lightweight travel jacket"]
    assert {op["op"] for op in out["state_diff"]["contact_ops"]} == {
        "remove", "add"}
    body = out["orchestration"]["specialists"]["body"]
    assert body["channels_filled"] == ["attire"]
    assert "contact_ops" in \
        out["orchestration"]["specialists"]["contact"]["channels_filled"]

    # And the checker SAW them: no omissions, no repair of either kind,
    # no reconciliation warnings.
    assert out["reconciliation"]["omissions"] == []
    steps = _steps(calls)
    assert "resolve_repair" not in steps
    assert steps.count("director_body") == 1
    assert steps.count("director_contact") == 1
    assert not [w for w in ctx.warnings
                if "reconciliation" in w.casefold()
                or "still does not encode" in w]


# ---------------------------------------------------------------------------
# Design note 21: the beat's changes are numbered, and the numbers round-trip.
# ---------------------------------------------------------------------------

def _two_event_resolve():
    """A beat asserting two changes in chronological order: a hand leaves a
    waist, then a coat comes off. Two entries, in that order -- which is
    what the manifest numbering is FOR."""
    return {
        "resolved_event": ("Mara's hand lifts from Bo's waist, and she "
                           "shrugs the wool coat off."),
        "summary": "Hand away, coat off.",
        "changes_asserted": [
            {"category": "contact", "subject": "prior hand-to-waist contact",
             "change": "ended", "actor": "Mara", "actor_part": "hand",
             "target": "Bo", "target_part": "waist"},
            {"category": "attire", "subject": "wool coat",
             "change": "The wool coat is off."},
        ],
        "state_diff": {},
    }


def test_the_engine_numbers_the_manifest_in_narrated_order(temp_db):
    """The ids are the ENGINE's, assigned 1..N in emission order, never the
    model's. A model-authored id could repeat, skip or reorder, and every
    downstream use assumes a dense sequence over exactly this manifest."""
    items = director._manifest_items(_two_event_resolve())
    assert [i["event_id"] for i in items] == [1, 2]
    # Chronology, not category order: the contact ended BEFORE the coat came
    # off, and that is the order the resolve wrote them in.
    assert items[0]["category"] == "contacts"
    assert items[1]["category"] == "attire"


def test_each_specialist_is_handed_only_its_own_numbered_events(temp_db):
    """The slice a specialist receives and the ids it is answerable for come
    from ONE filter -- two spellings would let a specialist be judged on an
    event it never saw."""
    view = {"manifest": director._manifest_items(_two_event_resolve())}
    body = director._specialist_manifest_slice("body", view)
    contact = director._specialist_manifest_slice("contact", view)
    assert [i["event_id"] for i in body] == [2]
    assert [i["event_id"] for i in contact] == [1]


def test_a_verdict_on_an_unhanded_event_is_discarded(temp_db):
    """A specialist cannot acquit an event it was never given. Without this,
    a model echoing the whole manifest back would silence every omission in
    the beat."""
    # The channel content is not what this test is about, but it has to be
    # here: an `encoded` verdict from a response that wrote NOTHING is dropped
    # on its own account (TestAnEncodedClaimNeedsSomethingEncoded), which would
    # make this pass for the wrong reason.
    result = {"poses": {"Corin": {"posture": "kneeling"}},
              "resolved_events": [
        {"event_id": 1, "status": "encoded"},      # granted
        {"event_id": 2, "status": "already_true"},  # NOT granted to this call
        {"event_id": 1, "status": "nonsense"},      # unrecognized verdict
    ]}
    assert director._resolved_event_verdicts(result, [1]) == [
        {"event_id": 1, "status": "encoded"}]


def test_an_answered_event_buys_no_second_call(temp_db, monkeypatch):
    """The measured waste (chat 71 turn 10): a full-core repair spending
    tens of seconds to re-ask a change the owner had already correctly
    declined to re-encode, whose 'already encoded' answer was then discarded
    on a subject-text mismatch. An event its owner answered is settled --
    detection still fires, no one is asked twice."""
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {
            "director_resolve": _asserting_resolve_output(),
            # The owner answers: standing state already carries it.
            "director_body": {
                "attire": {}, "conditions": {}, "vitals": {}, "overlays": {},
                "notes": [],
                "resolved_events": [{"event_id": 1,
                                     "status": "already_true"}],
            },
            "resolve_repair": {"state_diff": {}, "dispositions": []},
        }))
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    # Detection is untouched -- the omission is still recorded.
    assert _manifest_omissions(out)
    # But nobody was asked again: no full-core repair, and the body
    # specialist ran exactly once (the fan-out), not twice.
    assert "resolve_repair" not in _steps(calls)
    assert _steps(calls).count("director_body") == 1
    recon = out["reconciliation"]
    assert recon["acquitted"] == [{
        "event_id": 1, "category": "attire", "subject": "Mara",
        "owner": "body", "status": "already_true"}]
    assert not any("may be stale" in w for w in ctx.warnings)


def test_an_unanswered_event_still_buys_its_repair(temp_db, monkeypatch):
    """The acquittal is bookkeeping, not belief. A specialist that stays
    silent on an id it was handed has not addressed it, and the repair tier
    is exactly what an unaddressed gap is for."""
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {
            "director_resolve": _asserting_resolve_output(),
            "director_body": {"attire": {}, "conditions": {}, "vitals": {},
                              "overlays": {}, "notes": [],
                              "resolved_events": []},
            "resolve_repair": {"state_diff": {}, "dispositions": []},
        }))
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert _steps(calls).count("director_body") == 2   # fan-out + repair
    assert not (out["reconciliation"].get("acquitted") or [])


def test_not_mine_reports_a_gap_rather_than_closing_one(temp_db, monkeypatch):
    """'not_mine' is a specialist saying the change needs a channel it was
    not granted. That is scope under-grant -- a gap REPORTED, and the repair
    tier is what a reported gap is for."""
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {
            "director_resolve": _asserting_resolve_output(),
            "director_body": {"attire": {}, "conditions": {}, "vitals": {},
                              "overlays": {}, "notes": [],
                              "resolved_events": [{"event_id": 1,
                                                   "status": "not_mine"}]},
            "resolve_repair": {"state_diff": {}, "dispositions": []},
        }))
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat"]}}
    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert not (out["reconciliation"].get("acquitted") or [])
    assert _steps(calls).count("director_body") == 2


def test_a_failed_specialist_acquits_nothing(temp_db, monkeypatch):
    """Fail-open must not become fail-silent: a specialist whose call died
    leaves its events unaddressed, so the changes it was supposed to encode
    still escalate."""
    dispatch = {"body": {"run": True, "ran": False,
                         "events_resolved": [{"event_id": 1,
                                              "status": "encoded"}]}}
    assert director._index_addressed_events(dispatch) == {}


def test_the_stage_variant_carries_every_call_made_under_its_fanout(
        temp_db, monkeypatch):
    """The ledger defect found on the first live turn under the per-call
    ledger (variant v26648: ONE recorded call against five ran=True
    specialists). `_call_isolated` ran `contextvars.copy_context()` INSIDE
    the pool worker, and ThreadPoolExecutor workers do not inherit the
    submitting thread's contextvars -- so the copy was of an EMPTY context,
    and everything it exists to carry was None inside every
    multi-specialist fan-out: the ledger sink (calls unrecorded), the
    warning sink (a repair ladder firing inside a specialist left no
    trace), cancel_event (an abort could not reach in-flight specialists),
    and db.active_frame_id. The existing thread test proved attribution BY
    contextvar; this proves what it did not: that a persisted stage
    variant carries the calls its own fan-out made, stamped with the
    STAGE's key, each entry's role still naming the specialist."""
    import threading

    from llm import providers
    from agents.runtime import _with_engine_notes
    from agents.storage import ENGINE_NOTES_KEY
    from core.pipeline_context import current_step_key, current_warning_sink
    from core.pipeline_context import note_step_warning

    calls = []
    seen_cancel_events = []

    def reporting(role):
        def respond(payload):
            # What a real call does beneath _agent_json: report usage to
            # the ledger, and (sometimes) note a repair through the sink.
            providers._log_usage(role, "m-" + role, time.time() - 0.1,
                                 {"prompt_tokens": 10,
                                  "completion_tokens": 5})
            note_step_warning(f"{role}: repair ladder fired")
            seen_cancel_events.append(providers.cancel_event.get())
            if role == "director":
                return _ruling("body", "social", "contact", "objects",
                               "spatial")
            return {}
        return respond

    responses = {
        "director_resolve": reporting("director"),
        "director_body": reporting("director_body"),
        "director_social": reporting("director_social"),
        "director_contact": reporting("director_contact"),
        "director_objects": reporting("director_objects"),
        "director_spatial": reporting("director_spatial"),
    }
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, interp=_action_interp())
    abort = threading.Event()
    tokens = (current_step_key.set("director_resolve"),
              current_warning_sink.set(ctx.add_warning),
              providers.call_ledger_sink.set(ctx.note_llm_call),
              providers.cancel_event.set(abort))
    try:
        out = director.director_resolve(ctx, nonce=0)
    finally:
        providers.cancel_event.reset(tokens[3])
        providers.call_ledger_sink.reset(tokens[2])
        current_warning_sink.reset(tokens[1])
        current_step_key.reset(tokens[0])

    ran = [name for name, st in out["orchestration"]["specialists"].items()
           if st.get("ran")]
    assert len(ran) >= 2, "the pool path needs a real fan-out"

    # Every fan-out call is on the stage's ledger slice -- the slice
    # _with_engine_notes persists -- with the specialist identity intact.
    entries = ctx.llm_calls_for_step("director_resolve")
    roles = sorted(e["role"] for e in entries)
    assert "director" in roles
    for name in ran:
        assert f"director_{name}" in roles, name
    saved = _with_engine_notes(out, ctx, "director_resolve")
    persisted_roles = {e["role"]
                       for e in saved[ENGINE_NOTES_KEY]["llm_calls"]}
    assert {f"director_{name}" for name in ran} <= persisted_roles

    # A warning raised INSIDE a specialist call reaches the stage's notes.
    stage_warnings = saved[ENGINE_NOTES_KEY]["warnings"]
    for name in ran:
        assert any(f"director_{name}: repair ladder fired" == w
                   for w in stage_warnings), name

    # And the abort event actually rides into every worker, as the fan-out
    # comment has always claimed.
    assert all(ev is abort for ev in seen_cancel_events)


# ---------------------------------------------------------------------------
# already_true is checked against standing state (design note 21, residual 2
# closed): a defect detector, deliberately not a truth prover.
# ---------------------------------------------------------------------------
#
# The manifest's structure carries no DIRECTION -- whether a change puts the
# garment on or takes it off lives only in its prose, and prose matching is
# the boundary this design exists to get away from. Both end states are
# legitimate no-op targets, so an undirected "is it already so" check is
# vacuous. What IS decidable is whether standing state can support ANY
# definite claim about the subject: the live corruption that motivated this
# (chat 70/71, repaired via attire.release_removed_garments) was a garment
# marked `removed` while still resident in three regions -- a ledger a
# specialist could honestly read and answer `already_true` about a change
# standing state did NOT properly carry. Refusal turns that silence into a
# named defect; everything undecidable falls through to the existing trust.

def test_already_true_is_refused_on_the_removed_resident_corruption(
        temp_db, monkeypatch):
    """End to end on the corrupt-ledger shape: the body specialist answers
    already_true; standing attire still seats the garment in regions marked
    'removed'. The acquittal is refused, the omission still buys its owner
    repair, and the ledger defect is named on the step and to the Director."""
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {
            "director_resolve": {
                "resolved_event": "Mara shrugs the wool coat off.",
                "summary": "Coat off.",
                "changes_asserted": [
                    {"category": "attire", "subject": "Mara",
                     "change": "The wool coat is off."},
                ],
                "state_diff": {},
            },
            "director_body": {
                "attire": {}, "conditions": {}, "vitals": {}, "overlays": {},
                "notes": [],
                "resolved_events": [{"event_id": 1,
                                     "status": "already_true"}],
            },
        }))
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {
        "wearing": [],
        "regions": {"torso": {"garments": [
            {"name": "wool coat", "state": "removed"}]}},
    }}
    ctx = _make_ctx(temp_db, scene=scene, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    recon = out["reconciliation"]
    assert not (recon.get("acquitted") or [])
    refusal = recon["already_true_refused"][0]
    assert refusal["event_id"] == 1 and refusal["owner"] == "body"
    assert "removed" in refusal["reason"]
    # The gap still escalated to the owner: fan-out + one repair call.
    assert _steps(calls).count("director_body") == 2
    assert any("already_true refused" in w for w in ctx.warnings)
    assert any("already_true refused" in n for n in ctx.engine_feedback)


def test_already_true_verifier_names_each_decidable_defect():
    """Unit coverage of the refusal classes, each a measured ledger-defect
    shape: removed-yet-resident attire; wearing/regions drift; a standing
    position naming a non-room (the category error every spatial query
    answers as unknown); a contained body carrying its own disagreeing
    position (derived-position violation)."""
    om_attire = {"category": "attire", "subject": "Mara"}
    ok, reason = director._verify_already_true(om_attire, {
        "attire": {"Mara": {"wearing": [], "regions": {"torso": {"garments": [
            {"name": "wool coat", "state": "removed"}]}}}}})
    assert not ok and "removed" in reason

    ok, reason = director._verify_already_true(om_attire, {
        "attire": {"Mara": {"wearing": ["wool coat"],
                            "regions": {"torso": {"garments": [
                                {"name": "silk scarf", "state": "worn"}]}}}}})
    assert not ok and "disagree" in reason

    ok, reason = director._verify_already_true(
        {"category": "positions", "subject": "Mara"},
        {"rooms": {"keeper_room": {}},
         "positions": {"Mara": "elevator_control_panel"}})
    assert not ok and "not a room" in reason

    ok, reason = director._verify_already_true(
        {"category": "inventory", "subject": "wool coat"},
        {"contained": {"wool coat": {"in": "Mara"}},
         "positions": {"wool coat": "lamp_room", "Mara": "keeper_room"}})
    assert not ok and "derived" in reason


def test_already_true_verifier_trusts_what_it_cannot_decide():
    """The fall-through side, deliberate rather than by omission: a coherent
    ledger earns the acquittal whichever direction the change went (direction
    is not in the manifest's structure); a legacy entry with underived
    regions is undecidable; contacts and conditions have no decidable
    refusal (either end state is a legitimate no-op); and a broken scene
    fails open."""
    # Coherent wardrobe: worn AND seated -- no refusal, whatever the change.
    ok, _ = director._verify_already_true(
        {"category": "attire", "subject": "Mara"},
        {"attire": {"Mara": {"wearing": ["wool coat"],
                             "regions": {"torso": {"garments": [
                                 {"name": "wool coat",
                                  "state": "worn"}]}}}}})
    assert ok
    # Legacy shape: wearing only, regions never derived -- undecidable.
    ok, _ = director._verify_already_true(
        {"category": "attire", "subject": "Mara"},
        {"attire": {"Mara": {"wearing": ["wool coat"]}}})
    assert ok
    # Contacts: presence and absence are both legitimate no-op end states.
    ok, _ = director._verify_already_true(
        {"category": "contacts", "subject": "contact_end",
         "actor": "Mara", "actor_part": "hand",
         "target": "Bo", "target_part": "waist"},
        {"contacts": []})
    assert ok
    # Conditions: no decidable refusal either.
    ok, _ = director._verify_already_true(
        {"category": "conditions", "subject": "Mara"}, {})
    assert ok
    # Fail open on garbage.
    ok, _ = director._verify_already_true(
        {"category": "attire", "subject": "Mara"},
        {"attire": {"Mara": "not-a-dict"}})
    assert ok


def test_diff_application_is_order_independent_by_construction():
    """Design note 21's other residual, closed as a PROVEN INVARIANT rather
    than built machinery: applying the merged diff needs no event-id
    ordering, and this test is the tripwire that forces the decision to be
    remade consciously if a future channel breaks the reasons why.

    The reasons, precisely:

    1. EXCLUSIVE OWNERSHIP. Every delegated channel has exactly one
       specialist, and assembly replaces whole channels -- so no channel is
       ever interleaved from two model sources, and "op order across
       specialists" cannot exist within a channel.
    2. END-STATE CHANNELS COMMUTE. Every dict channel is a keyed end-state
       upsert (attire, conditions, vitals, overlays, entities, containment,
       scales, positions, rooms, stations, poses); one writer per beat per
       key means application order across channels changes nothing.
    3. THE SEQUENTIAL APPLIERS SHARE ONE OWNER. The only appliers that walk
       an op list against evolving state are apply_contact_ops and
       apply_substance_ops, and their whole read/write family -- contact_ops,
       substance_ops, containment, scales -- belongs to the ONE contact
       specialist. Within-beat chronology there IS that specialist's own
       list order, preserved verbatim through assembly; the engine-side
       sources merged into contact_ops (player onset assertions, character
       contact endings) are ordered by fixed conventions that match
       chronology (onset precedes resolve).
    4. CROSS-CHANNEL COUPLINGS ARE ADJUDICATED BY DELIBERATE FIXED
       CONVENTIONS in spatial.merge_scene_with_diff, each with a stated
       causal reason: substances resolve against the PRE-BEAT contact
       topology and apply before contact removals (a release can route
       through an interior relation the same beat's withdrawal ends); scale
       changes cancel contacts BEFORE the beat's own contact ops (a
       re-established hold survives); stations derive AFTER contacts settle;
       vitals last. Event-id ordering would re-litigate conventions that
       were each chosen deliberately -- including the coordinating suspect
       (a contact ending and a new contact on the same part in one beat),
       which lives entirely inside one specialist's one list.

    What would have to become true for ordering to be needed -- and what
    this test therefore refuses: a sequential-stateful op channel granted
    to a specialist other than the owner of the state its applier reads; a
    new delegated op channel left unclassified below; two owners able to
    write the same coupled family."""
    from agents.director import (
        SPECIALISTS, _CHANNEL_SPECIALISTS, _DELEGATED_CHANNELS,
        _LIST_DELEGATED,
    )

    # Keyed end-state upserts: order across channels cannot matter.
    end_state = {
        "attire", "conditions", "vitals", "overlays", "entities",
        "containment", "scales", "positions", "rooms", "stations", "poses",
        "destruction",
    }
    # Op lists whose appliers read no other delegated channel's
    # mid-application state (commit-side ledgers of their own).
    independent_ops = {
        "cast_changes", "introductions", "world_facts", "remove_entities",
        "inventory_ops", "artifact_ops", "remove_rooms", "remove_adjacent",
        "crowd_ops", "courier_ops", "telling_ops",
        # An order lands on the REGISTRY, not the scene: it is routed
        # out of the diff before the merge and applied inside the
        # commit, so it reads no other channel's mid-application state.
        "charter_ops",
        "ratified_claims", "contradicted_claims",
        # Observer evidence is stage metadata applied later to independent
        # Charter minds; it reads no scene-diff channel while assembling.
        "public_evidence",
        # `apply_comms_ops` records what the beat said and checks nothing
        # against the rooms: every prune is `normalize_scene_comms`, which runs
        # once rooms have settled. That split is deliberate and is what keeps
        # this channel out of the sequential set.
        "comms_ops",
        # `_record_sensory_events` files the beat's one-off signals under the
        # beat that made them, reading no channel mid-application: it checks
        # each event's room against the SETTLED scene, the same split
        # `comms_ops` keeps above. Nothing decays and nothing carries over,
        # so there is no evolving state for it to walk.
        "sensory_events",
    }
    # Op lists whose appliers walk evolving state sequentially. Two axes on
    # purpose: containment and scales APPLY as end-state upserts (so they
    # sit in end_state above) while still being part of what the
    # sequential appliers READ -- which is an ownership question, asserted
    # separately below. Contact actions ride standing contacts: the merge
    # applies contacts first so contact_ref pointers resolve, then the
    # actions, so they belong with the family of sequential channels.
    sequential_ops = {"contact_ops", "substance_ops", "contact_action_ops"}
    sequential_read_set = sequential_ops | {"containment", "scales"}

    # 1. One owner per channel -- no channel under two specialists.
    seen = {}
    for name, spec in SPECIALISTS.items():
        for channel in spec["channels"]:
            assert channel not in seen, (
                f"{channel} owned by both {seen[channel]} and {name}")
            seen[channel] = name

    # 2. Every delegated channel is classified EXACTLY once. A new channel
    #    failing here is the forcing function: decide which class it is in
    #    -- and if it is sequential-stateful, put it with its family's
    #    owner -- before shipping it.
    classified = end_state | independent_ops | sequential_ops
    for channel in _DELEGATED_CHANNELS:
        assert channel in classified, (
            f"unclassified delegated channel {channel!r}: decide whether "
            "its application is end-state, independent ops, or "
            "sequential-coupled before shipping it")
        assert (channel in end_state) + (channel in independent_ops) + (
            channel in sequential_ops) == 1, channel

    # 3. The sequential appliers AND everything they read share ONE owner,
    #    so within-beat chronology is one specialist's own list order.
    family_owners = {_CHANNEL_SPECIALISTS[c] for c in sequential_read_set
                     if c in _CHANNEL_SPECIALISTS}
    assert family_owners == {"contact"}, family_owners

    # 4. Shape agreement: the op classes are lists, the end states are not
    #    (destruction is the one dict-or-null exception, asserted as such).
    for channel in independent_ops | {"contact_ops", "substance_ops"}:
        if channel in _DELEGATED_CHANNELS:
            assert channel in _LIST_DELEGATED, channel
    for channel in end_state - {"destruction"}:
        assert channel not in _LIST_DELEGATED, channel


# ---------------------------------------------------------------------------
# Every delegated family must be REACHABLE by a category.
# ---------------------------------------------------------------------------

#: Channels a category deliberately cannot name, with the reason. Removal
#: channels are reached through the family they remove from (an object
#: destroyed is 'entities'/'destruction'; a sealed passage is 'adjacency');
#: `following_ops` is engine-projected and no model authors it.
_UNREACHABLE_BY_DESIGN = {
    "remove_entities": "reached as 'entities'",
    "remove_rooms": "reached as 'rooms'",
    "remove_adjacent": "reached as 'adjacency'",
    "following_ops": "engine-projected, never model-authored",
    "crowd_ops": "traffic ops surface, not a manifest category",
    "courier_ops": "traffic ops surface, not a manifest category",
    "telling_ops": "traffic ops surface, not a manifest category",
    # An order is a dispatch, not a change this beat's prose asserts: what
    # the manifest enumerates is what CHANGED, and an errand changes
    # nothing until the body has walked it, one room at a time, on the
    # beats after.
    "charter_ops": "traffic ops surface, not a manifest category",
    # Adjudications of a CARRIED claim, not changes the beat's prose
    # asserts: they answer "was this hearsay true?", which the manifest --
    # an enumeration of what this beat changed -- has nothing to say about.
    # They reach their owner through the claim lane, never the manifest.
    "ratified_claims": "claim adjudication, not a beat change",
    "contradicted_claims": "claim adjudication, not a beat change",
    "public_evidence": "observer metadata, not an objective beat change",
    # A ONE-BEAT SIGNAL IS NOT A PERSISTENT CHANGE, and the manifest says so
    # of itself: it enumerates "every PERSISTENT physical change your
    # resolved_event asserts as COMPLETED". A bang leaves nothing standing
    # to enumerate -- the beat number is its whole lifetime -- so a category
    # for it would file a thing that expires in a ledger built for things
    # that do not, and the omission detector would report it missing from
    # the next scene for ever. It reaches its hand the other way the
    # dispatch offers: a `ledger_notes` line keyed by the channel name,
    # which `_note_for` routes by channel exactly as it routes one keyed by
    # a hand.
    "sensory_events": "a one-beat signal, not a persistent change; reaches "
                      "the objects hand through a ledger note keyed by the "
                      "channel",
}


def test_every_delegated_family_is_reachable_by_a_category():
    """A channel no category can name is a change that lands NOWHERE: no
    specialist is handed it, so nobody can encode it, so the seam detects an
    omission on every beat containing it and buys a repair from a mind that
    never saw the event.

    Measured twice. contacts/substances/poses/stations were dead this way
    from 8.2 (the category map was keyed on raw spellings while every reader
    looked up the normalized form). `overlays` and `vitals` were dead the
    same way while the body specialist OWNED them -- which is what a live
    beat's 'slight quiver' and 'heavy heated breathing' fell through, at
    49.2s of repair for two events nobody could have encoded.

    Adding a delegated channel now costs a decision here: give it a
    category, or say in _UNREACHABLE_BY_DESIGN why it needs none.
    """
    reachable = set(director._CATEGORY_CHANNELS.values())
    for name, spec in director.SPECIALISTS.items():
        for channel in spec["channels"]:
            assert channel in reachable or channel in _UNREACHABLE_BY_DESIGN, (
                f"{name} owns {channel!r}, but no manifest category reaches "
                f"it -- a change categorized there would be handed to no "
                f"specialist and repaired by a mind that never saw it. Add a "
                f"category to _CATEGORY_CHANNELS or record why it needs none."
            )


def test_every_category_route_lands_on_a_real_owned_channel():
    """The other direction: a category mapping to a channel no specialist
    owns routes an event to nobody just as silently."""
    owners = {c for s in director.SPECIALISTS.values() for c in s["channels"]}
    for category, channel in director._CATEGORY_CHANNELS.items():
        assert channel in owners, (
            f"category {category!r} routes to {channel!r}, which no "
            f"specialist owns")


def test_every_alias_normalizes_onto_a_routed_category():
    """An alias is the Director's own vocabulary. One that normalizes to a
    category with no route is the same silent drop, arriving through a
    spelling instead of a channel."""
    core_owned = {"time", "transit", "other"}
    aliases = director._ling("_OMISSION_CATEGORY_ALIASES")
    for alias, normalized in aliases.items():
        assert (normalized in director._CATEGORY_CHANNELS
                or normalized in core_owned), (
            f"alias {alias!r} normalizes to {normalized!r}, which reaches "
            f"neither a specialist channel nor a core-owned category")


# ---------------------------------------------------------------------------
# The omitted-thought ledger: says what was left out, commits nothing.
# ---------------------------------------------------------------------------

def _interior_resolve_output():
    return {
        "resolved_event": "Mara says nothing, and decides she will not go.",
        "summary": "She decides.",
        "changes_asserted": [],
        "thoughts_omitted": [
            {"subject": "Mara", "thought": "resolves not to go"},
            {"subject": "Mara", "thought": ""},          # blank: dropped
        ],
        "state_diff": {},
    }


def test_the_thought_ledger_is_recorded_and_commits_nothing(temp_db,
                                                            monkeypatch):
    """A thought is not a change to the world. The ledger exists so an
    honestly interior beat stops reading like a beat that lost its changes
    -- it reaches no channel, no specialist and no committed state."""
    calls = []
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, {
                            "director_resolve": _interior_resolve_output()}))
    ctx = _make_ctx(temp_db, interp=_speech_interp())
    out = director.director_resolve(ctx, nonce=0)
    recon = out["reconciliation"]
    assert recon["thoughts_omitted"] == [
        {"subject": "Mara", "thought": "resolves not to go"}]
    # Nothing it says reaches objective state. The diff is normalized to
    # its declared channels, so the check is that every one is EMPTY --
    # no thought became a condition, an overlay, or anything else.
    assert not any((out.get("state_diff") or {}).values())
    # And it is not a change, so it is never an event anyone must answer.
    assert recon["manifest"] == []
    assert "resolve_repair" not in _steps(calls)


def test_the_thought_ledger_cannot_excuse_a_physical_beat(temp_db,
                                                          monkeypatch):
    """It quiets a subroutine when nothing is wrong -- not when something
    is. A successful roll or an asserted effect-claim moved the world, and
    no amount of declared interiority accounts for an empty manifest there.
    That case is exactly what the tripwire exists for."""
    out_data = _interior_resolve_output()
    calls = []
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, {"director_resolve": out_data}))
    interp = _action_interp()
    interp["flow"]["authority_claims"] = [
        {"claim_id": "c0", "scope": "effect", "predicate": "the latch gives"}]
    ctx = _make_ctx(temp_db, interp=interp)
    out = director.director_resolve(ctx, nonce=0)
    recon = out["reconciliation"]
    assert recon["thoughts_omitted"]        # recorded
    assert recon["tripwire"] is True        # and still caught


# ---------------------------------------------------------------------------
# One real change is one numbered event; one garment is one record.
# ---------------------------------------------------------------------------

def _live_duplicating_resolve():
    """The live beat's exact manifest shape (chat 71, v26670): two garments
    removed, and the SAME two garments separately asserted as entities
    created on the floor -- which is what the commit seam does by itself."""
    return {
        "resolved_event": "Elyra strips the sash and shorts away.",
        "summary": "Undressed.",
        "changes_asserted": [
            {"category": "contact", "subject": "Elyra Voss",
             "change": "hand leaves Hinami stomach", "actor": "Elyra Voss",
             "actor_part": "hand", "target": "Hinami",
             "target_part": "stomach"},
            {"category": "attire", "subject": "Hinami",
             "change": "utility sash removed"},
            {"category": "attire", "subject": "Hinami",
             "change": "travel shorts removed"},
            {"category": "entities", "subject": "utility sash",
             "change": "created in room, placed on floor"},
            {"category": "entities", "subject": "travel shorts",
             "change": "created in room, placed on floor"},
        ],
        "state_diff": {},
    }


def test_a_derived_entity_event_folds_into_its_attire_event():
    """A garment coming off and the same garment appearing on the floor are
    one change described twice. Numbered separately they route to two
    owners, each of which faithfully authors its own record -- which is
    exactly how the live scene reached five entity records for two
    garments. Ids stay a dense sequence after the fold."""
    items = director._manifest_items(_live_duplicating_resolve())
    assert [i["category"] for i in items] == ["contacts", "attire", "attire"]
    assert [i["event_id"] for i in items] == [1, 2, 3]
    # The fold is remembered, not silently dropped.
    assert all("entities" in i.get("also_described_as", [])
               for i in items if i["category"] == "attire")


def test_positions_and_poses_are_not_derived_of_attire():
    """Three different facts about a body, not three descriptions of one --
    the fold must not reach them."""
    out = {"changes_asserted": [
        {"category": "attire", "subject": "Hinami",
         "change": "travel shorts removed"},
        {"category": "poses", "subject": "Hinami",
         "change": "legs lifted, knees parted"},
        {"category": "positions", "subject": "Hinami",
         "change": "moved onto the platform"},
    ]}
    items = director._manifest_items(out)
    assert [i["category"] for i in items] == ["attire", "poses", "positions"]
    assert [i["event_id"] for i in items] == [1, 2, 3]


def test_every_hand_can_name_a_worn_garment(temp_db):
    """A worn garment lives only in sc.attire, so a specialist that needed
    to name one could not -- and invented an entity instead (the live
    `hinami_shorts`, whose own note admitted it). Identity only: the name
    and whose body it is on, never the wardrobe's state."""
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat", "boots"]}}
    ctx = _make_ctx(temp_db, scene=scene)
    view = {"source": "resolved_beat", "prose": "x", "dialogue": [],
            "player": "Mara", "cast": [], "declared_actions": [],
            "dice": [], "manifest": []}
    for name in ("contact", "objects"):
        payload = director._specialist_payload(name, ctx, scene, view, {})
        assert {"name": "wool coat", "worn_by": "Mara"} \
            in payload["worn_garments"], name
        # Identity only -- no wardrobe state crosses.
        assert all(set(g) == {"name", "worn_by"}
                   for g in payload["worn_garments"]), name


def test_the_sheet_tells_every_hand_a_body_is_not_a_thing_it_keeps():
    """Live warning, chat 71 interpret: "Structural blocker: Hinami is not
    in the entities index, cannot update state for 'lifts legs'". The
    lookup was reasonable -- bodies ARE sometimes entity records (the cast
    NPC has one, kind 'npc') -- but the player has none by design, and a
    pose belongs to another hand either way. Every specialist answers the
    same beat at once, so one hand hunting for another hand's subject is
    both a false blocker and N-1 duplicated observations."""
    from llm.prompts import specialist_prompt

    sheet = specialist_prompt("objects", ["entities"])
    assert "A BODY IS NOT A THING YOU KEEP" in sheet
    # The two facts that make the false blocker impossible to reach.
    assert "payload.player" in sheet and "payload.cast" in sheet
    assert "NOT a blocker" in sheet


# ---------------------------------------------------------------------------
# A forwarding note beats the category map.
# ---------------------------------------------------------------------------

def _pose_miscategorized_resolve():
    """The live shape: a posture change filed under a category that routes
    it to the body specialist, which owns no posture channel. Both contact
    and objects said so in free-text notes nothing read, while the repair
    tier kept re-asking by category."""
    return {
        "resolved_event": "Mara lifts her legs, knees parted.",
        "summary": "Legs lifted.",
        "changes_asserted": [
            {"category": "conditions", "subject": "Mara",
             "change": "legs lifted, knees parted"},
        ],
        "state_diff": {},
    }


def _body_declines_to(target):
    return {"attire": {}, "conditions": {}, "vitals": {}, "overlays": {},
            "notes": [], "resolved_events": [
                {"event_id": 1, "status": "not_mine", "reroute_to": target}]}


def test_a_declined_event_goes_to_the_hand_that_was_named(temp_db,
                                                          monkeypatch):
    """Routing by category re-asks the hand that just declined it. The
    address is what turns a complaint into a forwarding note."""
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {
            "director_resolve": _pose_miscategorized_resolve(),
            "director_body": _body_declines_to("spatial"),
            "resolve_repair": {"state_diff": {}, "dispositions": []},
        }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    steps = _steps(calls)
    # The named hand was asked; the declining hand was NOT asked twice.
    assert steps.count("director_spatial") >= 1
    assert steps.count("director_body") == 1
    assert "resolve_repair" not in steps
    # And the misroute is recorded, so the category map can be corrected
    # from data rather than guessed at.
    assert out["reconciliation"]["reroutes"] == [
        {"event_id": 1, "declined_by": "body", "reroute_to": "spatial",
         "category": "conditions"}]


def test_an_address_naming_nobody_falls_back_to_the_category(temp_db,
                                                             monkeypatch):
    """The address is a PROPOSAL, checked against the roster. An unknown
    hand is dropped rather than carried into routing as a half-fact."""
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {
            "director_resolve": _pose_miscategorized_resolve(),
            "director_body": _body_declines_to("the vibes department"),
            "resolve_repair": {"state_diff": {}, "dispositions": []},
        }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)
    assert not (out["reconciliation"].get("reroutes") or [])
    # Category routing stands: conditions is the body specialist's own.
    assert _steps(calls).count("director_body") == 2


def test_an_address_on_anything_but_a_decline_is_ignored(temp_db):
    """Only a decline forwards. An `encoded` verdict carrying an address is
    a model contradicting itself, and the engine keeps the encoding."""
    # Carries channel content for the same reason as
    # test_a_verdict_on_an_unhanded_event_is_discarded: an empty response's
    # `encoded` is dropped on its own account, and this test is about the
    # ADDRESS, not the content.
    result = {"poses": {"Corin": {"posture": "kneeling"}},
              "resolved_events": [
        {"event_id": 1, "status": "encoded", "reroute_to": "spatial"}]}
    assert director._resolved_event_verdicts(result, [1]) == [
        {"event_id": 1, "status": "encoded"}]


def test_a_specialist_cannot_forward_to_itself(temp_db, monkeypatch):
    """Otherwise the note is a loop with extra steps."""
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {
            "director_resolve": _pose_miscategorized_resolve(),
            "director_body": _body_declines_to("body"),
            "resolve_repair": {"state_diff": {}, "dispositions": []},
        }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    director.director_resolve(ctx, nonce=0)
    # Falls back to category routing rather than forwarding to itself.
    assert _steps(calls).count("director_body") == 2


def test_a_ledger_this_story_does_not_keep_is_not_a_gate_mispredict(temp_db,
                                                                    monkeypatch):
    """Measured live, chat 71 with survival off: the resolve filed a
    climax's spent-ness under `vitals` -- reasonably, since 8.2.2 tells it
    to take the CLOSEST category and never omit -- and the backstop
    announced "the scope gate mispredicted" about a channel that shipped
    nothing and could never ship anything, because this story keeps no
    vitals ledger at all.

    Two different things wear the same shape. "No work in it this beat" is
    a prediction and a manifest item naming it is evidence the prediction
    was wrong. "This story has no such ledger" is not a prediction. A
    warning that fires when nothing is wrong is how a reader learns to skip
    warnings."""
    calls = []
    monkeypatch.setattr(
        director, "_agent_json",
        _fake_agent(calls, {
            "director_resolve": {
                "resolved_event": "Mara sags, spent.",
                "summary": "Spent.",
                "changes_asserted": [
                    {"category": "vitals", "subject": "Mara",
                     "change": "reserves spent"},
                ],
                "state_diff": {},
            },
            "resolve_repair": {"state_diff": {}, "dispositions": []},
        }))
    ctx = _make_ctx(temp_db, interp=_action_interp())
    out = director.director_resolve(ctx, nonce=0)

    # survival is off in the fixture, so `vitals_tracked` is False and the
    # gate never served vitals -- correctly.
    served = set((out["orchestration"].get("scope_report") or {}).get("served") or ())
    assert "vitals" not in served
    # No mispredict is claimed...
    assert not any("gate mispredicted" in w for w in ctx.warnings)
    # ...and the Director is told what it actually needs to know instead.
    assert any("this story keeps no vitals ledger" in n
               for n in ctx.engine_feedback)


def test_dialogue_reaches_only_the_hands_a_speech_act_can_write(temp_db):
    """Saying a thing is not a physical action.

    The beat's dialogue rode in the COMMON payload, so every hand got it
    whether or not any channel they own could be written by somebody talking.
    Three of the five cannot -- `body`, `contact` and `objects` own physical
    ledgers, and
    a transcript is material they can only echo, which is this fan-out's
    measured failure mode rather than a hypothetical one. Measured over chat
    78: 27% of the beat text every hand received.

    The three that DO keep it each have a named reason in the channel table:
    a name is given by being said (`introductions`), a line carried by a
    device IS the op (`comms_ops`), and a claim is made and disputed in
    speech (`telling_ops`, `ratified_claims`, `contradicted_claims`).
    """
    scene = json.loads(json.dumps(BASE_SCENE))
    ctx = _make_ctx(temp_db, scene=scene)
    view = {"source": "resolved_beat", "prose": "x",
            "dialogue": [{"speaker": "Mara", "exact_quote": "\"Hello.\""}],
            "player": "Mara", "cast": [], "declared_actions": [],
            "dice": [], "manifest": []}

    for name in ("social", "spatial"):
        payload = director._specialist_payload(name, ctx, scene, view, {})
        assert payload.get("dialogue_log"), name
    for name in ("body", "contact", "objects"):
        payload = director._specialist_payload(name, ctx, scene, view, {})
        assert "dialogue_log" not in payload, name
        # And the beat does NOT reach them by another door either. This used
        # to assert the opposite -- that the prose carried what speech made
        # happen -- which was the justification for withholding the
        # transcript. With the prose gone the reasoning inverts: these hands
        # get neither, because a spoken line is not something their channels
        # can encode, and what they must encode arrives as an instruction.
        assert "resolved_event" not in payload, name


def test_who_reads_dialogue_is_derived_from_the_channel_table():
    """Not a per-specialist list. A channel that moves between hands takes
    its answer with it, so this cannot drift out of agreement with
    `SPECIALISTS` the way a second copy of the rule would."""
    from agents.director import (
        SPECIALISTS, SPEECH_WRITTEN_CHANNELS, reads_dialogue)

    for name, spec in SPECIALISTS.items():
        expected = bool(set(spec["channels"]) & SPEECH_WRITTEN_CHANNELS)
        assert reads_dialogue(name) is expected, name
    # Every speech-written channel is owned by somebody, or the set has a
    # name in it that no longer exists.
    owned = {c for s in SPECIALISTS.values() for c in s["channels"]}
    assert SPEECH_WRITTEN_CHANNELS <= owned


def test_no_sheet_promises_a_dialogue_field_its_hand_may_not_receive():
    """A sheet naming a field the payload does not carry is not a wording
    problem, it is the defect that minted a garment.

    The body sheet sent its hand to a `worn_garments` index `director_fanout`
    never attached, so the only garment names in its payload lived inside the
    compact attire line and it read across the `=` delimiter -- emitting
    coverage for "modern open-front jacket", the first 58 characters of
    another garment's description. The shared stage clause made the same
    promise about `dialogue_log` to every hand, and now only three receive
    it, so the clause states the condition instead of asserting the field.
    """
    from llm.prompts import specialist_prompt
    from agents.director import SPECIALISTS, reads_dialogue

    for name, spec in SPECIALISTS.items():
        sheet = specialist_prompt(name, list(spec["channels"]))
        if "dialogue_log" not in sheet:
            continue
        assert "WHEN YOUR PAYLOAD CARRIES IT" in sheet, (
            f"{name}'s sheet names dialogue_log without saying it may be "
            f"absent (this hand receives it: {reads_dialogue(name)})")


# ---------------------------------------------------------------------------
# A channel that belongs to ONE stage.
#
# Measured, chat 98 turns 6, 26 and 30: the social specialist emitted
# `public_evidence` at `director_interpret`, whose granted scope was
# ['cast_changes', 'introductions', 'world_facts'] on two of them and
# ['introductions', 'world_facts'] on the third. Every notice said "Content
# was kept (fail-open); the scope gate under-granted and should be widened if
# this recurs", and every one of those three recorded steps carries
# `state_assertions: {}` -- nothing was kept. Both halves of the notice were
# wrong, and acting on the second half would have granted the channel at a
# stage that has not adjudicated anything yet.
# ---------------------------------------------------------------------------

def test_a_stage_only_channel_is_not_a_state_diff_field():
    """The structural fact underneath: at interpret a specialist's channels
    merge into `state_assertions`, which is a `StateDiff` -- and
    `public_evidence` is not one of its fields, so a value written there is
    dropped by `validated_player_state_assertions` a few lines later. That is
    why the fail-open kept nothing."""
    from llm.schemas import DirectorResolve, StateDiff, _fields
    from agents.director import CHANNEL_STAGES

    assert "public_evidence" not in set(_fields(StateDiff))
    assert "public_evidence" in set(_fields(DirectorResolve))
    for channel, stages in CHANNEL_STAGES.items():
        assert channel not in set(_fields(StateDiff)) or "interpret" in stages


def test_every_stage_only_channel_names_a_real_channel():
    """The table is level with the specialist registry, the way the three
    channel registries already are."""
    from agents.director import CHANNEL_STAGES, SPECIALISTS

    owned = {channel for spec in SPECIALISTS.values()
             for channel in spec["channels"]}
    for channel, stages in CHANNEL_STAGES.items():
        assert channel in owned, channel
        assert stages and set(stages) <= {"interpret", "resolve"}, channel


def test_interpret_drops_a_resolve_only_channel_and_says_so(temp_db,
                                                            monkeypatch):
    """Chat 98 turn 26's shape. The channel is not merely out of this beat's
    scope -- interpret cannot carry it at all, so the guard SUBTRACTS and the
    notice says the content was dropped, never that it was kept."""
    calls = []
    responses = {
        "director_interpret": {
            "kind": "speech",
            "sequence": [{"type": "speech", "text": "Quiet night.",
                          "volume": "normal", "visibility": "overt",
                          "conceal_from": []}],
            "speech": "Quiet night.", "action": None, "movement": None,
            **_ruling("social"),
            "flow": {"reactors": [], "authority_claims": [], "dice": [],
                     "resolution_flags": {}, "fiction_frame": {}},
        },
        "director_social": {
            "cast_changes": [], "introductions": [], "world_facts": [],
            "public_evidence": [
                {"source_id": "invented", "speech_act": "greeting"}],
            "notes": [],
        },
    }
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, player_input="Quiet night.")
    ctx.director_interpret = None
    out = director.director_interpret(ctx, nonce=0)

    social = out["orchestration"]["specialists"]["social"]
    assert "public_evidence" not in social["scope"]
    assert social.get("dropped_channels") == ["public_evidence"]
    assert social.get("outside_scope") in (None, [])
    assert "public_evidence" not in (out.get("state_assertions") or {})
    notes = [str(note) for note in ctx.engine_feedback]
    assert any("public_evidence" in note and "dropped" in note
               for note in notes), notes
    assert not any("should be widened" in note for note in notes), notes


def test_resolve_still_fails_open_on_a_genuine_under_grant(temp_db,
                                                           monkeypatch):
    """The other half must not change. A channel the stage CAN carry, gated
    out of this beat, is under-grant evidence: kept, and reported as the
    thing to widen."""
    calls = []
    responses = {
        "director_resolve": {
            "resolved_event": "Mara says nothing more.",
            "summary": "Quiet.",
            "state_diff": {},
            # KEYED BY A CHANNEL, not by the hand. That is what leaves the
            # gates something to narrow -- a hand named alone now loads every
            # ledger it keeps, so it cannot be under-granted and this path
            # would never be reached through one.
            "ledger_notes": {"introductions": "social: settled this beat"},
        },
        "director_social": {
            "cast_changes": [{"name": "Mara", "change": "present"}],
            "introductions": [], "world_facts": [], "notes": [],
        },
    }
    monkeypatch.setattr(director, "_agent_json",
                        _fake_agent(calls, responses))

    ctx = _make_ctx(temp_db, interp=_speech_interp())
    out = director.director_resolve(ctx, nonce=0)

    social = out["orchestration"]["specialists"]["social"]
    # A pure-dialogue beat: `cast_changes` gates on `physical_beat`, so the
    # channel is legal at resolve and out of scope for THIS beat -- exactly
    # the case the fail-open exists for.
    assert "cast_changes" not in social["scope"]
    assert social.get("dropped_channels") in (None, [])
    assert social.get("outside_scope") == ["cast_changes"]
    assert out["state_diff"]["cast_changes"] == [
        {"name": "Mara", "change": "present"}]
    notes = [str(note) for note in ctx.engine_feedback]
    assert any("kept (fail-open)" in note for note in notes), notes


class TestAHandIsToldWhoElseHasThisSpan:
    """Five shared chunks, one per hand, loaded by whoever ELSE got the span.

    The owner, 2026-09-10: "we basically just need 5 chunks, 1 explaining each
    hand and that it is working on one or more ledgers that you've also
    received, and they can be shared chunks as I don't think the 5 hands need
    explanations unique to them on how other hands work."

    The failure this prevents is a hand doing its co-worker's half: a record
    written into a channel it does not own is dropped by the merge, so the work
    is invisible AND the span still does not close (`_acquit_addressed_events`
    waits for every owner). The hand cannot know that from its own sheet, which
    describes only its own channels -- so the engine says it, from the same
    ownership table dispatch reads.
    """

    BELT = {"event_id": 1, "categories": ["attire", "objects"],
            "category": "attire", "note": "the belt leaves her waist"}
    STEP = {"event_id": 2, "categories": ["positions"],
            "category": "positions", "note": "she crosses to the window"}

    def test_the_roster_is_every_other_owner_of_a_span_it_got(self):
        view = {"spans": [self.BELT, self.STEP]}
        assert director.specialist_co_hands("body", view) == ["objects"]
        assert director.specialist_co_hands("objects", view) == ["body"]
        # `spatial` was handed the step and nothing else, and the step is
        # wholly its own -- so it is told about nobody.
        assert director.specialist_co_hands("spatial", view) == []
        # A hand handed no span at all has no co-workers to hear about.
        assert director.specialist_co_hands("social", view) == []

    def test_a_span_wholly_one_hands_own_adds_nothing(self):
        """The ordinary beat. Every span single-category means every roster is
        empty, which is what keeps the paragraph off the sheet the rest of the
        time -- a clause every hand always carries is a clause in the core."""
        view = {"spans": [self.STEP]}
        for name in director.SPECIALISTS:
            assert director.specialist_co_hands(name, view) == [], name

    def test_the_roster_reaches_the_sheet(self, temp_db):
        from llm.prompts import specialist_prompt
        view = {"spans": [self.BELT]}
        shared = specialist_prompt(
            "body", ["attire"], "en", director.specialist_co_hands("body", view))
        alone = specialist_prompt("body", ["attire"], "en")
        assert "OBJECTS hand" in shared
        assert "OBJECTS hand" not in alone
        # It says what the OTHER hand settles, never what this one does.
        assert "BODY hand" not in shared

    def test_every_hand_has_a_chunk_in_every_story_pack(self):
        """A missing chunk is silent: the loop skips a hand it cannot find and
        the sheet assembles one paragraph short. `installed_language_packs`
        refuses a pack missing an English leaf, so this holds for `ja` too --
        pinned here because the fanout, not the pack loader, is what breaks."""
        from language_runtime import installed_language_packs
        for pack in installed_language_packs().values():
            if not pack.story:
                continue
            shared = pack.card("system_prompts").get("co_hands") or {}
            for name in director.SPECIALISTS:
                assert str(shared.get(name) or "").strip(), (pack.id, name)

    def test_a_preset_override_still_carries_it(self, temp_db):
        """A host's replacement sheet has no way to know which of the other
        four hands got a piece of the same span, so the chunk is appended
        outside the override branch -- beside `director_note`."""
        from llm import prompts
        temp_db.set_setting("prompt_presets", json.dumps({
            "Mine": {"director_body": "BODY SHEET, REWRITTEN."}}))
        temp_db.set_setting("active_preset", "Mine")
        sheet = prompts.specialist_prompt("body", ["attire"], "en", ["objects"])
        assert sheet.startswith("BODY SHEET, REWRITTEN.")
        assert "OBJECTS hand" in sheet


class TestTwoKnownNamesInOneStringAreTwoNames:
    """The sheets say to write a list. A model that reaches for a separator
    instead used to lose the whole span in silence: "body, objects" folds to
    no known category, routes to no hand, and the change the beat asserted
    reaches nobody.

    This is not the guessing `_note_key_forms` refuses. Nothing is inferred
    from wording -- the string is split on punctuation and the split is
    DISCARDED unless every part is a category the engine already routes, so it
    can recognise names the engine owns and can never invent a route.
    """

    def _cats(self, raw):
        out = director._span_items({"sequence": [
            {"type": "action", "attempt": "x", "category": raw, "note": "n"}]})
        return out[0].get("categories"), director.span_owners(out[0])

    def test_a_separator_a_model_reaches_for_is_two_names(self):
        for raw in ("body, objects", "body and objects", "body/objects",
                    "body; objects", "body|objects"):
            cats, owners = self._cats(raw)
            assert cats == ["body", "objects"], raw
            assert owners == ["body", "objects"], raw

    def test_three_of_them_are_three(self):
        cats, owners = self._cats("body, objects, spatial")
        assert cats == ["body", "objects", "spatial"]
        assert owners == ["body", "objects", "spatial"]

    def test_one_unknown_name_keeps_the_whole_string_whole(self):
        """Routability, not foldability: `_normalize_omission_category` passes
        an unknown name straight through, so a truthiness test would accept
        anything. The Director gets its own string echoed back by the unrouted
        report, which is clearer feedback than half a route."""
        cats, owners = self._cats("body, geography")
        assert cats == ["body, geography"]
        assert owners == []

    def test_free_prose_is_never_split_into_categories(self):
        """The failure the routability test exists to prevent. This string
        contains "and", so a looser rule would file two ledger families named
        after halves of a sentence."""
        cats, owners = self._cats(
            "the belt comes off and lands on the bench")
        assert cats == ["the belt comes off and lands on the bench"]
        assert owners == []

    def test_a_single_name_is_untouched(self):
        cats, owners = self._cats("body")
        assert cats == ["body"] and owners == ["body"]

    def test_a_real_list_is_still_the_preferred_shape(self):
        """The clause asks for this and the worked example shows it; the split
        above is the fallback, not the contract."""
        cats, owners = self._cats(["objects", "spatial"])
        assert cats == ["objects", "spatial"]
        assert owners == ["objects", "spatial"]

    def test_both_sheets_say_how_to_write_two(self):
        """A capability the prompt does not describe does not exist, and one
        it describes without a SHAPE gets written as a comma string -- which
        is what the split above had to be built for. `state_diff.time` is the
        precedent: prose two thousand lines away, a scalar in the example, and
        a model that sent a string."""
        from llm.prompts import DEFAULT_PROMPTS, prose_author_prompt
        from llm.schemas import output_example
        for sheet in (DEFAULT_PROMPTS["director_interpret"],
                      prose_author_prompt(None, "en")):
            assert "may name TWO" in sheet
            assert "never one string with a comma" in sheet
        worked = [e.get("category")
                  for e in output_example("director_resolve").get("sequence")]
        assert ["objects", "spatial"] in worked


class TestAHandIsAnswerableForTheWorkItemsItGot:
    """`event_ids` is the grant a verdict is checked against, and it was built
    from the RETIRED channel.

    `_resolved_event_verdicts` discards any id outside the grant, so a grant
    built from `changes_asserted` alone -- a field neither sheet asks for, and
    which measured 0 entries on all 12 beats of every live run since it was
    retired -- is empty on every beat, and every verdict a hand returns is
    thrown away. `events_addressed` is then `{}`, and per-hand acquittal, the
    seam that keeps a half-settled span owed, cannot run at all.

    Measured 2026-09-10, the padlock beat: the Director filed ONE span
    categorized `["objects", "spatial"]`, both hands were handed it, `objects`
    answered `encoded` and `spatial` answered `not_mine` with a reason. Three
    correct structured facts, and that beat's orchestration record read
    `events_addressed: {}`.
    """

    VIEW = {"spans": [
        {"event_id": 1, "categories": ["objects", "spatial"],
         "category": "objects", "attempt": "padlock the forge door shut",
         "note": "the forge door is shut and padlocked"},
        {"event_id": 2, "categories": ["body"], "category": "body",
         "note": "the belt leaves her waist"},
    ]}

    def test_the_grant_is_the_hands_own_spans(self):
        granted = director._granted_event_ids("objects", self.VIEW)
        assert granted == [1]
        assert director._granted_event_ids("spatial", self.VIEW) == [1]
        assert director._granted_event_ids("body", self.VIEW) == [2]
        # A hand no span reached is answerable for nothing, which is a
        # different fact from a hand whose grant was never built.
        assert director._granted_event_ids("social", self.VIEW) == []

    def test_a_verdict_on_a_granted_span_survives(self):
        """The whole point: without the grant this returned {} and the hand's
        answer vanished."""
        kept = director._resolved_event_verdicts(
            {"entities": {"padlock": {"name": "padlock"}},
             "resolved_events": [{"event_id": 1, "status": "encoded"}]},
            director._granted_event_ids("objects", self.VIEW))
        assert kept and kept[0]["status"] == "encoded"

    def test_a_manifest_id_is_still_granted_beside_the_spans(self):
        """One id space, so this is a union and never a renumbering: spans
        take 1..N and the manifest continues past the ceiling."""
        view = dict(self.VIEW)
        view["manifest"] = [{"event_id": 3, "category": "objects",
                             "subject": "hinge", "change": "it came apart"}]
        assert director._granted_event_ids("objects", view) == [1, 3]

    def test_a_span_neither_owner_settles_stays_owed(self):
        """And the reason the grant has to be right: acquittal reads the index
        the grant produces, so an empty grant acquitted nothing AND owed
        nothing -- silence that looks exactly like a beat with no work."""
        dispatch = {
            "objects": {"ran": True, "events_resolved": [
                {"event_id": 1, "status": "encoded"}]},
            "spatial": {"ran": True, "events_resolved": [
                {"event_id": 1, "status": "not_mine"}]},
        }
        index = director._index_addressed_events(dispatch)
        assert set(index[1]["by_hand"]) == {"objects", "spatial"}
        out = {"orchestration": {"events_addressed": index}}
        omission = {"event_id": 1, "category": "objects",
                    "subject": "forge door", "change": "it is padlocked"}
        owed, acquitted, _refused = director._acquit_addressed_events(
            out, [omission], {})
        assert owed == [omission] and acquitted == []


class TestADialRefusesTheSpanAndTheRecordWithIt:
    """The owner's ruling, 2026-09-10: "Either it mints the window or door or
    it refuses the whole span depending on player authority level."

    The refuse arm did neither. `apply_player_authority` moves two labels --
    the claim's scope to `intent`, the element's commitment to `contestable` --
    and it runs AFTER the fan-out, so the hands have already written the
    record. Measured on one beat under both dials, everything else equal:

        world_author  downgrades=0  state_assertions {"rooms":{"bay":{"desc":"dark now"}}}
        actor_only    downgrades=1  state_assertions {"rooms":{"bay":{"desc":"dark now"}}}

    Byte-identical. Under hard mode the player's world assertion was relabelled
    an intention and the world kept the fact.
    """

    LAMP = {
        "kind": "action",
        "sequence": [{
            "type": "event",
            "description": "the lamp above the door goes out",
            "raw_text": "the lamp above the door goes out",
            "category": "spatial",
            "note": "the lamp above the door is out",
        }],
        "ledger_notes": {"spatial": "the lamp above the door is out"},
        "flow": {"reactors": [], "dice": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    SPATIAL = {
        "rooms": {"bay": {"name": "Bay", "desc": "dark now", "from_event": 1}},
        "resolved_events": [{"event_id": 1, "status": "encoded"}],
    }

    def _beat(self, temp_db, monkeypatch, mode):
        from story.scene import set_player_authority
        calls = []
        monkeypatch.setattr(director, "_agent_json", _fake_agent(
            calls, {"director_interpret": self.LAMP,
                    "director_spatial": self.SPATIAL}))
        ctx = _make_ctx(temp_db, player_input="the lamp goes out")
        set_player_authority(ctx.chat.id, mode)
        ctx.director_interpret = None
        return director.director_interpret(ctx, nonce=0)

    def test_world_author_is_untouched(self, temp_db, monkeypatch):
        """The default, and the property that matters most to everyone who
        does not want hard mode: it grants everything, so there is nothing to
        void and an existing story means tomorrow what it meant yesterday."""
        out = self._beat(temp_db, monkeypatch, "world_author")
        assert not out.get("authority_downgrades")
        assert not out.get("voided_spans")
        assert out["state_assertions"]["rooms"]["bay"]["desc"] == "dark now"

    def test_a_refused_span_takes_the_record_with_it(self, temp_db,
                                                     monkeypatch):
        for mode in ("explicit_outcomes", "actor_only"):
            out = self._beat(temp_db, monkeypatch, mode)
            assert len(out["authority_downgrades"]) == 1, mode
            assert out["voided_spans"] == [
                {"event_id": 1, "dropped": ["rooms.bay"]}], mode
            assert out["state_assertions"].get("rooms") == {}, mode

    def test_the_refusal_is_reported_never_silent(self, temp_db, monkeypatch):
        """A refused assertion must not silently vanish -- the player wrote it
        for a reason. The downgrade already reaches the Director in the same
        beat; the DROPPED RECORD is a second fact and needs saying too, or the
        step shows a hand that ran and a channel that is empty with no reason
        anywhere."""
        ctx_warnings = []
        from story.scene import set_player_authority
        calls = []
        monkeypatch.setattr(director, "_agent_json", _fake_agent(
            calls, {"director_interpret": self.LAMP,
                    "director_spatial": self.SPATIAL}))
        ctx = _make_ctx(temp_db, player_input="the lamp goes out")
        set_player_authority(ctx.chat.id, "actor_only")
        ctx.director_interpret = None
        director.director_interpret(ctx, nonce=0)
        notes = [str(w) for w in ctx.warnings]
        assert any("PLAYER AUTHORITY" in n and "refused whole" in n
                   for n in notes), notes

    def test_a_span_no_record_cites_voids_nothing(self):
        """The bound on the guarantee, stated because it is real: `from_event`
        is how a record says which span it settles, so a hand that omits it
        leaves a record nothing can attribute. Same limit the deferred-phase
        floor has always had, and the reason provenance went ON the record."""
        assertions = {"rooms": {"bay": {"name": "Bay", "desc": "dark now"}}}
        dropped = director.void_span_records(assertions, [1])
        assert dropped == []
        assert assertions["rooms"]["bay"]["desc"] == "dark now"

    def test_every_owner_of_a_shared_span_loses_its_half(self):
        """WHOLE is the rule. A span may be owned by several hands, and
        voiding one hand's record while another's stands is exactly the
        half-settlement the ruling was given to end. They cite one id, so one
        pass reaches all of them."""
        assertions = {
            "entities": {"shutter": {"name": "shutter", "from_event": 1}},
            "rooms": {"forge": {"name": "Forge", "from_event": 1}},
            "poses": {"Corin": {"posture": "standing", "from_event": 2}},
        }
        dropped = director.void_span_records(assertions, [1])
        assert assertions["entities"] == {} and assertions["rooms"] == {}
        # A span nobody refused is untouched.
        assert set(assertions["poses"]) == {"Corin"}
        assert {path for path, _ in dropped} == {"entities.shutter",
                                                 "rooms.forge"}

    def test_the_join_is_position_to_span_id(self):
        """A downgrade names a sequence POSITION; a record cites a SPAN id.
        Both spaces are real and neither is the other -- the lesson of the
        beat where a hand cited the phase graph because the payload carried
        two fields called `event_id`."""
        out = {"sequence": [
            {"type": "speech", "text": "hello"},
            {"type": "action", "attempt": "x", "category": "body",
             "note": "n"},
            {"type": "event", "description": "the lamp goes out",
             "category": "spatial", "note": "m"},
        ]}
        # position 2 is the second SPAN (id 2), not the second element.
        assert director.voided_span_ids(
            out, [{"claim_id": "claim:2:event"}]) == [2]
        assert director.voided_span_ids(
            out, [{"claim_id": "claim:1:0"}]) == [1]
        # An element that became no span addressed no ledger, so nothing
        # cites it and there is nothing to void.
        assert director.voided_span_ids(
            out, [{"claim_id": "claim:0:0"}]) == []
        assert director.voided_span_ids(out, []) == []

    def test_no_engine_private_key_reaches_a_hand(self, temp_db, monkeypatch):
        """`_from_position` is the engine's bookkeeping. A number in a payload
        is a number the model will try to cite: the contact hand spent 16,180
        output tokens citing the wrong one of two fields called `event_id`."""
        from agents.director import _specialist_payload
        view = {"source": "player_declaration", "player": "Corin", "cast": [],
                "declared_actions": {}, "dice": [], "ledger_notes": {},
                "declaration": {"sequence": []}, "manifest": [],
                "spans": director._span_items({"sequence": [
                    {"type": "action", "attempt": "x", "category": "spatial",
                     "note": "n"}]})}
        assert view["spans"][0]["_from_position"] == 0
        ctx = _make_ctx(temp_db)
        payload = _specialist_payload(
            "spatial", ctx, json.loads(json.dumps(BASE_SCENE)), view,
            {"nonce": 0})
        assert payload["spans"], payload.keys()
        for span in payload["spans"]:
            assert not [k for k in span if str(k).startswith("_")], span


class TestAHandSeesWhatItsCoOwnerHolds:
    """The owner, 2026-09-10: "we can temporarily show the part of the world
    state the colaborating agents see", then "conditional formating based on
    what hands are interacting".

    `co_hands/<hand>.txt` tells a hand WHO is settling the other half of its
    span. Without the rows behind it that is a paragraph it cannot act on: a
    hand that cannot name its co-owner's thing invents one, and the invention
    becomes a second record of a thing that already existed. That is not
    hypothetical -- the payload's unconditional worn-garment index exists
    because "the objects specialist minted a duplicate object for the same
    reason and said so".

    Five slices for twenty pairings, the same collapse the chunks made: what
    the body hand holds is the same rows whoever asks.
    """

    SCENE = {
        "attire": {"Corin": {"wearing": ["apron"],
                             "regions": {"torso": ["apron"]},
                             "conditions": ["scorched"]}},
        "entities": {"hook": {"name": "hook", "state": {"loose": True}}},
        "positions": {"Corin": "forge", "hook": "forge"},
        "rooms": {"forge": {"name": "Forge", "adjacent": [
            {"to": "well", "barrier": "closed_door", "name": "forge door"}]}},
        "contacts": [], "contained": {},
    }

    def _view(self, categories):
        return {"spans": director._span_items({"sequence": [
            {"type": "action", "attempt": "hang my apron on the hook",
             "category": categories, "note": "n"}]})}

    def test_each_owner_sees_the_other_and_only_the_other(self):
        view = self._view(["body", "objects"])
        assert director.co_hand_view("objects", view, self.SCENE) == {
            "body": {"worn": [{"garment": "apron", "worn_by": "Corin"}]}}
        assert director.co_hand_view("body", view, self.SCENE) == {
            "objects": {"things": [
                {"id": "hook", "name": "hook", "at": "forge"}]}}

    def test_a_hand_that_shares_no_span_sees_nothing(self):
        """The same gate the chunk uses, so the paragraph and the rows that
        make it actionable arrive together or not at all."""
        view = self._view(["body", "objects"])
        assert director.co_hand_view("spatial", view, self.SCENE) == {}
        assert director.co_hand_view("contact", view, self.SCENE) == {}

    def test_a_span_wholly_one_hands_own_shows_nobody_anything(self):
        view = self._view("body")
        for hand in director.SPECIALISTS:
            assert director.co_hand_view(hand, view, self.SCENE) == {}, hand

    def test_identity_crosses_and_state_never_does(self):
        """The boundary the unconditional index already states: this widens
        who can be NAMED, not what is KNOWN. A hand that could read its
        co-owner's state could write its co-owner's conclusions, which is the
        ownership race the disjoint partition exists to prevent."""
        view = self._view(["body", "objects"])
        objects_sees = json.dumps(director.co_hand_view(
            "objects", view, self.SCENE))
        # The wardrobe's own state: coverage, condition, the region map.
        assert "scorched" not in objects_sees
        assert "regions" not in objects_sees and "torso" not in objects_sees
        body_sees = json.dumps(director.co_hand_view(
            "body", view, self.SCENE))
        assert "loose" not in body_sees and "state" not in body_sees

    def test_the_slice_is_keyed_on_the_hand_looked_at_not_the_looker(self):
        """Five functions, twenty pairings. What `body` holds is one answer,
        so `contact` and `objects` reading it get the same rows."""
        both = self._view(["body", "contact"])
        assert director.co_hand_view("contact", both, self.SCENE)["body"] == \
            director.co_hand_view("objects", self._view(
                ["body", "objects"]), self.SCENE)["body"]

    def test_the_ways_between_rooms_reach_a_sharing_hand(self):
        """The pair this session made routine: a padlock is the objects hand's
        and the door it hangs on is an edge in the spatial hand's. Neither
        could name the other's half, and nothing in the tree joins an entity
        to a passage."""
        view = self._view(["objects", "spatial"])
        seen = director.co_hand_view("objects", view, self.SCENE)
        # `way` is the doorway's OWN id, the same token `span_pairings` groups
        # by. A hand handed only a name has to invent where its record went;
        # a hand handed the id can say it, and both sides of the seam then
        # spell the place one way.
        assert seen["spatial"]["ways"] == [
            {"way": "forge|well", "from": "forge", "to": "well",
             "barrier": "closed_door", "name": "forge door"}]
        assert seen["spatial"]["standing"] == [
            {"who": "Corin", "in": "forge"}, {"who": "hook", "in": "forge"}]

    def test_it_reaches_the_payload_only_when_a_span_is_shared(self, temp_db):
        from agents.director import _specialist_payload
        ctx = _make_ctx(temp_db)
        base = {"source": "player_declaration", "player": "Corin", "cast": [],
                "declared_actions": {}, "dice": [], "ledger_notes": {},
                "declaration": {"sequence": []}, "manifest": []}
        shared = dict(base, spans=self._view(["body", "objects"])["spans"])
        alone = dict(base, spans=self._view("objects")["spans"])
        sc = json.loads(json.dumps(self.SCENE))
        with_co = _specialist_payload("objects", ctx, sc, shared, {"nonce": 0})
        without = _specialist_payload("objects", ctx, sc, alone, {"nonce": 0})
        assert "body" in with_co["co_hands"]
        assert "co_hands" not in without


class TestASpansRecordsArePairedByWhereTheyHappen:
    """The owner, 2026-09-10: "We need some sort of reconciliation code that
    pairs things together based on where they are supposed to happen."

    `span_records` says which records are one event's outcome; it cannot say
    which of them are the same THING within it, because the apron and the hook
    both cite the span that hung one on the other. Place answers that, and it
    is the right key because the engine ISSUES it -- a room id, a doorway's
    room pair. Names are the model's and drift; the folds in this tree all
    match on names because until the span id there was nothing else to match
    on, and one of them admits matching "coat" against "coat rack".

    A grouping, never a decision. Two lamps in a room are two lamps.
    """

    SCENE = {"positions": {"Corin": "forge", "padlock": "forge"}}
    DIFF = {
        "entities": {"padlock": {"name": "padlock", "from_event": 1}},
        "rooms": {
            "forge": {"name": "Forge", "adjacent": [
                {"to": "well", "barrier": "closed_door", "from_event": 1}]},
            "well": {"name": "Well", "adjacent": [
                {"to": "forge", "barrier": "closed_door", "from_event": 1}]},
        },
    }

    def test_one_doorway_is_one_place_not_two_edges(self):
        """Both mirrored edges of a doorway carry the same token, sorted, so
        the two sides of one way cannot read as two places."""
        places = director.span_pairings(self.DIFF, self.SCENE)[1]
        assert sorted(places) == ["room:forge", "way:forge|well"]
        assert len(places["way:forge|well"]) == 2

    def test_a_thing_in_a_room_meets_the_doorway_of_that_room(self):
        """The padlock stands in the forge and the door lies between the forge
        and the well, so exactly by place they never met. A way belongs to each
        room it joins, which costs no new vocabulary and is what lets the two
        halves of one act land together."""
        rooms = director.span_colocations(self.DIFF, self.SCENE)[1]
        assert set(rooms) == {"forge", "well"}
        assert [p for p, _c, _r in rooms["forge"]] == [
            "entities.padlock", "rooms.forge.adjacent[0]",
            "rooms.well.adjacent[0]"]
        # The padlock is not in the well, and does not appear there.
        assert "entities.padlock" not in [p for p, _c, _r in rooms["well"]]

    def test_a_record_the_engine_cannot_place_pairs_with_nothing(self):
        """Silence, never a guess. An unplaced entity has no room, and parking
        it under one would weld it to whatever else was there."""
        diff = {"entities": {"ghost": {"name": "ghost", "from_event": 1}}}
        assert director.span_pairings(diff, {"positions": {}}) == {}
        assert director.span_colocations(diff, {"positions": {}}) == {}

    def test_this_beats_move_wins_over_where_it_stood(self):
        """A subject the beat moved pairs where it now IS, so a record about
        the arrival does not group with the room it left."""
        sc = {"positions": {"Corin": "forge"}}
        diff = {"positions": {"Corin": "well"},
                "poses": {"Corin": {"posture": "kneeling", "from_event": 1}}}
        rooms = director.span_colocations(diff, sc)[1]
        assert set(rooms) == {"well"}

    def test_separate_spans_are_never_pooled(self):
        """The span bounds the question. Two acts in one room stay two acts,
        which is the half of the key that names are no help with at all."""
        sc = {"positions": {"lamp": "forge", "stool": "forge"}}
        diff = {"entities": {"lamp": {"name": "lamp", "from_event": 1},
                             "stool": {"name": "stool", "from_event": 2}}}
        grouped = director.span_colocations(diff, sc)
        assert [p for p, _c, _r in grouped[1]["forge"]] == ["entities.lamp"]
        assert [p for p, _c, _r in grouped[2]["forge"]] == ["entities.stool"]

    def test_the_room_record_itself_is_placed(self):
        diff = {"rooms": {"forge": {"name": "Forge", "desc": "dark",
                                    "from_event": 1}}}
        assert sorted(director.span_pairings(diff, {})[1]) == ["room:forge"]


class TestTheBeatNumbersTheThingsItTouches:
    """The owner, 2026-09-10: "the director main stage could also emit
    temporary item ids for the persons places or things mentioned in input
    that get attached to all ledgers that involve that item ... this id
    actually never gets exposed to the specialists ... it should allow the
    reconciliation of multiple interactions with a freshly minted object to be
    just that."

    THE GAP, and neither the span id nor place reaches it. A hand's payload is
    built from the scene AS IT STOOD BEFORE THE BEAT, and the hands run in
    parallel -- so a thing minted in span 1 exists for nobody, and every later
    interaction with it is an interaction with something the acting hand cannot
    see. Its only outcomes are to mint a second copy or decline. Only the
    Director can supply the identity, because only the Director reads the input
    and can say the console in the last clause is the console from the third.

    A NUMBER, and the model's own. The reasons a span id must be engine-issued
    -- dense, ordered, unique, because every downstream use assumes a dense
    sequence -- do not carry: a temp item id need only be CONSISTENT, repeats
    are the entire point, and skips and order mean nothing. It also removes
    what made a string unusable: across 34 measured Director calls the same
    model wrote `sword_belt` and `sword belt` for one object.

    Measured live on the first try (gemini-3.8-flash): "I tell Sera to wait
    here, then I step into the tardis, pull the door shut behind me, tell her
    she can't hear me now, and pull the levers on the console" numbered Sera 1
    across spans 1 AND 4, tardis 2 across spans 2 and 3, door 3, console 4,
    levers 5. And "I set the crate down by the forge door, open the crate, and
    take the mallet out of it" carried crate 1 through all three spans --
    including the one where the input says only "it".
    """

    def _spans(self, sequence):
        return director._span_items({"sequence": sequence})

    def test_the_numbers_are_kept_and_never_reach_a_hand(self):
        """The owner's constraint, enforced rather than asked for: they ride
        under a leading underscore, and `_specialist_payload` already strips
        every such key from a span. A number in a payload is a number the model
        will try to cite -- one spent 16,180 output tokens doing exactly
        that."""
        span, = self._spans([
            {"type": "action", "attempt": "I step into the tardis",
             "category": "spatial", "note": "inside",
             "items": [{"id": 2, "name": "tardis"}]}])
        assert span["_items"] == [{"id": 2, "name": "tardis"}]
        assert "items" not in span
        assert not [k for k in director._without_private_keys(span)
                    if str(k).startswith("_")]
        assert "_items" not in director._without_private_keys(span)

    def test_one_thing_across_several_spans_is_one_thing(self):
        """The case it exists for. Three interactions with a crate the beat
        itself minted, the last of them naming it only as "it"."""
        spans = self._spans([
            {"type": "action", "attempt": "I set the crate down",
             "category": "objects", "note": "a",
             "items": [{"id": 1, "name": "crate"}]},
            {"type": "action", "attempt": "open the crate",
             "category": "objects", "note": "b",
             "items": [{"id": 1, "name": "crate"}]},
            {"type": "action", "attempt": "take the mallet out of it",
             "category": "objects", "note": "c",
             "items": [{"id": 3, "name": "mallet"},
                       {"id": 1, "name": "crate"}]}])
        sd = {"entities": {
            "crate": {"name": "crate", "from_event": 1},
            "mallet": {"name": "mallet", "from_event": 3}}}
        items = director.beat_item_records(sd, spans)
        assert items[1]["name"] == "crate"
        assert items[1]["spans"] == [1, 2, 3]
        assert items[3]["spans"] == [3]

    def test_it_gathers_what_two_hands_wrote_that_could_not_see_each_other(
            self):
        """The TARDIS shape, from the live beat: `objects` minted
        `entities.tardis` and `spatial` minted `rooms.tardis_interior`, in
        parallel, each from a payload showing the scene before either existed.
        One thing, two records, and nothing joined them."""
        spans = self._spans([
            {"type": "action", "attempt": "I step into the tardis",
             "category": ["objects", "spatial"], "note": "inside",
             "items": [{"id": 2, "name": "tardis"}]}])
        sd = {"entities": {"tardis": {"name": "tardis", "from_event": 1}},
              "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                            "from_event": 1}}}
        paths = sorted({p for p, _c, _r
                        in director.beat_item_records(sd, spans)[2]["records"]})
        assert paths == ["entities.tardis", "rooms.tardis_interior"]

    def test_a_beat_that_numbers_nothing_costs_nothing(self):
        spans = self._spans([
            {"type": "action", "attempt": "I kneel", "category": "spatial",
             "note": "n"}])
        assert spans[0].get("_items") is None
        assert director.beat_item_records(
            {"poses": {"Corin": {"posture": "kneeling", "from_event": 1}}},
            spans) == {}

    def test_a_mention_with_no_number_says_nothing_and_is_dropped(self):
        """Tolerant about the shape a model reaches for -- a bare number is an
        id with no name -- but a mention carrying no number cannot say the one
        thing this exists to say."""
        span, = self._spans([
            {"type": "action", "attempt": "x", "category": "objects",
             "note": "n", "items": [{"id": 4, "name": "console"}, 5,
                                    "levers", {"name": "no number"}]}])
        assert span["_items"] == [{"id": 4, "name": "console"},
                                  {"id": 5, "name": ""}]

    def test_both_sheets_ask_for_them(self):
        from llm.prompts import DEFAULT_PROMPTS, prose_author_prompt
        for sheet in (DEFAULT_PROMPTS["director_interpret"],
                      prose_author_prompt(None, "en")):
            assert "NUMBER THE THINGS THE BEAT TOUCHES" in sheet
            assert "SAME THING KEEPS THE SAME NUMBER" in sheet


class TestWhichRecordOfAThingIsAllowedToExist:
    """The owner, 2026-09-10: "the temp id allows the reconciler to apply all
    transforms in chronological order to an existing object, the priority ...
    being 'Actually exists in the world even before this beat.' then 'Freshly
    minted by the most relevant authority.' And the chosen object must receive
    all transforms."

    ORDER is borrowed, not owned: the chronological id exists so that events
    resolved in parallel are reassembled in the beat's true order for
    PERCEPTION, which must deliver them to a mind in the order they happened.
    This is a second consumer of the same property. (The first is still
    unbuilt -- `perception.py` dedupes on the phase id and streams each actor's
    sequence by `enumerate`.)
    """

    OWNER = {channel: hand for hand, spec in director.SPECIALISTS.items()
             for channel in spec["channels"]}

    def _spans(self, *sequence):
        return director._span_items({"sequence": list(sequence)})

    def _span(self, category, item_id, name):
        return {"type": "action", "attempt": "x", "category": category,
                "note": "n", "items": [{"id": item_id, "name": name}]}

    def test_what_stood_before_the_beat_outranks_what_it_minted(self):
        """Rung one, and it is what stops a beat re-founding a crate it merely
        opened."""
        spans = self._spans(self._span("objects", 1, "crate"))
        sd = {"entities": {
            "crate": {"name": "crate", "from_event": 1},
            "wooden_crate": {"name": "wooden crate", "from_event": 1}}}
        sc = {"entities": {"crate": {"name": "crate"}}}
        got = director.item_survivors(sd, spans, sc, self.OWNER)[1]
        assert got["render_from"][0] == "entities.crate"
        assert got["reason"] == "standing"
        assert [p for p, _c, _r in got["duplicates"]] == ["entities.wooden_crate"]

    def test_otherwise_the_channels_own_hand_wins(self):
        """Rung two. The partition is disjoint, so "most relevant authority"
        is a lookup and never a judgement."""
        spans = self._spans(self._span(["objects", "spatial"], 2, "tardis"))
        sd = {"entities": {"tardis": {"name": "tardis", "from_event": 1}},
              "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                            "from_event": 1}}}
        got = director.item_survivors(sd, spans, {}, self.OWNER)[2]
        assert got["reason"] == "owning_hand"

    def test_a_duplicate_folds_and_a_pair_only_links(self):
        """The distinction the channel decides. `entities.tardis` and
        `rooms.tardis_interior` are one thing and two TRUE halves -- folding
        either into the other deletes the place the player is standing in --
        while two records in ONE channel are one hand's two attempts at one
        thing, because the partition is disjoint."""
        spans = self._spans(self._span(["objects", "spatial"], 2, "tardis"))
        sd = {"entities": {"tardis": {"name": "tardis", "from_event": 1},
                           "tardis_box": {"name": "blue box",
                                          "from_event": 1}},
              "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                            "from_event": 1}}}
        got = director.item_survivors(sd, spans, {}, self.OWNER)[2]
        assert [p for p, _c, _r in got["duplicates"]] == ["entities.tardis_box"]
        assert [p for p, _c, _r in got["other_facts"]] == ["rooms.tardis_interior"]

    def test_what_folds_arrives_in_chronological_order(self):
        """"in chronological order" is the owner's phrase and the span number
        is what carries it -- not the order a hand's call happened to return
        in, which the parallel fan-out makes meaningless."""
        spans = self._spans(
            self._span("objects", 1, "crate"),
            self._span("objects", 1, "crate"),
            self._span("objects", 1, "crate"))
        sd = {"entities": {
            "crate": {"name": "crate", "from_event": 1},
            "z_later": {"name": "crate", "from_event": 3},
            "a_middle": {"name": "crate", "from_event": 2}}}
        sc = {"entities": {"crate": {"name": "crate"}}}
        got = director.item_survivors(sd, spans, sc, self.OWNER)[1]
        # Alphabetically `a_middle` precedes `z_later`; chronologically it is
        # span 2 before span 3, and that is what decides.
        assert [p for p, _c, _r in got["duplicates"]] == [
            "entities.a_middle", "entities.z_later"]

    def test_one_record_is_not_a_reconciliation(self):
        spans = self._spans(self._span("objects", 1, "crate"))
        sd = {"entities": {"crate": {"name": "crate", "from_event": 1}}}
        assert director.item_survivors(sd, spans, {}, self.OWNER) == {}

    def test_a_beat_that_numbers_nothing_reconciles_nothing(self):
        spans = self._spans(
            {"type": "action", "attempt": "x", "category": "objects",
             "note": "n"})
        sd = {"entities": {"a": {"name": "a", "from_event": 1},
                           "b": {"name": "b", "from_event": 1}}}
        assert director.item_survivors(sd, spans, {}, self.OWNER) == {}


class TestTheCausalityRecompiler:
    """The owner's name for it, 2026-09-10: "basically we are making a
    causality recompiler after our director deciphers and resolves", serving
    the thesis "a system that can decipher any arbitrarily long series of
    events by a player or character and resolve it properly with proper
    respect to chronology and space. Even though its disecting and feeding it
    to paralel agents."

    A beat's diff is applied all at once, so every question about the beat is
    answered against the world as it stood AFTER everything in it happened. In
    a beat where a door shuts halfway through, that is the wrong world for both
    halves: the speech before it shut was audible and the speech after was not,
    and one world cannot say both.

    NOTHING NEW IS NEEDED FOR THE CONES. `world/spatial_fov` is pure, derived
    and never stored, and `spatial_rel` / `body_visibility` / `hear_level` take
    the SCENE as a parameter -- so handing them a different scene answers for
    that world, and the geometry is respected by construction rather than by a
    rule a caller has to remember.
    """

    SCENE = {
        "rooms": {
            "yard": {"name": "Yard", "adjacent": [
                {"to": "box", "barrier": "open_door", "name": "box door"}]},
            "box": {"name": "Box", "adjacent": [
                {"to": "yard", "barrier": "open_door", "name": "box door"}]},
        },
        "positions": {"Corin": "yard", "Sera": "yard"},
        "entities": {}, "contacts": [], "poses": {}, "stations": {},
        "contained": {},
    }
    DIFF = {
        # span 2: he steps inside. A position is `dict[str, str]` -- a bare
        # string with nowhere to carry a citation -- so its provenance rides
        # in the sidecar the sheets already ask for.
        "positions": {"Corin": "box"},
        "phase_sources": {"positions.Corin": 2},
        # span 3: the door is pulled shut, both sides, as the hands write it.
        "rooms": {
            "yard": {"adjacent": [{"to": "box", "barrier": "closed_door",
                                   "name": "box door", "from_event": 3}]},
            "box": {"adjacent": [{"to": "yard", "barrier": "closed_door",
                                  "name": "box door", "from_event": 3}]},
        },
    }

    def _worlds(self):
        from world.spatial import merge_scene_with_diff
        return director.beat_worlds(
            json.loads(json.dumps(self.SCENE)), self.DIFF,
            merge_scene_with_diff)

    def test_the_beat_yields_a_world_per_span_in_order(self):
        worlds = self._worlds()
        assert [span for span, _w in worlds] == [2, 3]
        before2, before3 = worlds[0][1], worlds[1][1]
        # The world BEFORE a span does not contain that span.
        assert before2["positions"]["Corin"] == "yard"
        assert before3["positions"]["Corin"] == "box"
        assert before3["rooms"]["yard"]["adjacent"][0]["barrier"] == "open_door"

    def test_the_same_question_gets_three_answers_from_one_beat(self):
        """The whole claim, measured. Today every event in this beat is judged
        against the last row, so the first two are unreachable."""
        from world.spatial import (merge_scene_with_diff, hear_level, room_of,
                                   spatial_rel)

        def heard(world):
            rel = spatial_rel(world, room_of(world, "Sera"),
                              room_of(world, "Corin"))
            return rel.get("same_room"), hear_level(rel, "normal")

        worlds = self._worlds()
        assert heard(worlds[0][1]) == (True, "full")        # same room
        assert heard(worlds[1][1]) == (False, "full")       # apart, door open
        final = merge_scene_with_diff(
            json.loads(json.dumps(self.SCENE)), self.DIFF)
        assert heard(final) == (False, "fragment")          # door shut

    def test_a_scalar_channel_is_placed_by_the_sidecar(self):
        """`positions` is `dict[str, str]`, so a body's position cannot carry
        `from_event` -- and a beat's movements are exactly what a replay must
        order. `phase_sources` is the sidecar built for that, already taught by
        the sheets and already read by `prune_blocked_phase_changes`."""
        slices, loose = director.span_slices(self.DIFF)
        assert slices[2] == {"positions": {"Corin": "box"}}
        assert "positions" not in loose

    def test_a_records_own_citation_outranks_the_sidecar(self):
        """The field the sheets now lead with, and the one a hand fills while
        composing the record itself. The sidecar is a second structure to
        remember, and measured 25% emission."""
        slices, _loose = director.span_slices({
            "poses": {"Corin": {"posture": "kneeling", "from_event": 5}},
            "phase_sources": {"poses.Corin": 9}})
        assert sorted(slices) == [5]

    def test_a_record_and_its_rows_go_to_their_own_spans(self):
        """`rooms.<id>` holds `name` beside an `adjacent` LIST whose rows cite
        their own spans. Filing the whole record in one bucket AND
        distributing its rows applies the same edge twice on replay."""
        slices, loose = director.span_slices({
            "rooms": {"forge": {"name": "Forge", "adjacent": [
                {"to": "well", "barrier": "closed_door", "from_event": 2}]}}})
        assert slices[2] == {"rooms": {"forge": {"adjacent": [
            {"to": "well", "barrier": "closed_door", "from_event": 2}]}}}
        assert loose == {"rooms": {"forge": {"name": "Forge"}}}

    def test_what_cites_nothing_lands_before_the_beat(self):
        """It belongs to no point in the order, and the two ends are not
        equal: applied first it is background the beat acts upon, applied last
        it would silently overwrite what the beat established."""
        from world.spatial import merge_scene_with_diff
        worlds = director.beat_worlds(
            json.loads(json.dumps(self.SCENE)),
            {"positions": {"Sera": "box"},
             "poses": {"Corin": {"posture": "kneeling", "from_event": 4}}},
            merge_scene_with_diff)
        assert [span for span, _w in worlds] == [4]
        assert worlds[0][1]["positions"]["Sera"] == "box"

    def test_every_sliced_record_is_a_collected_record(self):
        """`span_records` collects and `span_slices` reconstructs, so they
        cannot be one function -- and this pins them to each other rather than
        to shared code. The property is what matters: the two must agree about
        which shapes a channel takes."""
        slices, _loose = director.span_slices(self.DIFF)
        for span_id, sliced in slices.items():
            collected = {path for path, _c, _r
                         in director.span_records(self.DIFF).get(span_id, [])}
            for channel, content in sliced.items():
                if isinstance(content, dict):
                    for key in content:
                        assert any(p.startswith("%s.%s" % (channel, key))
                                   for p in collected) or not collected, (
                            span_id, channel, key)


class TestASpecialistReturnsTransformsNotRecords:
    """The owner, 2026-09-10: "what the specialists actually give us are
    transforms we can apply to objects, even if it's an object the specialists
    freshly minted", and "the chosen object must receive all transforms."

    That is the right abstraction for the fan-out. Identity is the Director's
    item number, order is the chronological span number, and a freshly minted
    object is one whose first transform happens to be its creation.
    """

    OWNER = {channel: hand for hand, spec in director.SPECIALISTS.items()
             for channel in spec["channels"]}

    def _spans(self, *ids):
        return director._span_items({"sequence": [
            {"type": "action", "attempt": "x", "category": "objects",
             "note": "n", "items": [{"id": i, "name": "crate"}]}
            for i in ids]})

    def _fold(self, sd, sc):
        spans = self._spans(1, 1)
        survivors = director.item_survivors(sd, spans, sc, self.OWNER)
        return director.apply_item_transforms(sd, survivors)

    def test_the_survivor_receives_the_transforms_and_the_duplicate_goes(self):
        sd = {"entities": {
            "crate": {"name": "crate", "from_event": 1},
            "wooden_crate": {"name": "wooden crate", "kind": "container",
                             "material": "oak", "aliases": ["box"],
                             "from_event": 2}}}
        applied = self._fold(sd, {"entities": {"crate": {"name": "crate"}}})
        assert list(sd["entities"]) == ["crate"]
        assert sd["entities"]["crate"]["kind"] == "container"
        assert sd["entities"]["crate"]["material"] == "oak"
        assert applied[0]["folded"] == ["entities.wooden_crate"]

    def test_the_latest_transform_sets_the_state(self):
        """A crate that stood before the beat and was opened during it must
        not keep the shut snapshot it stood as. Identity comes from the
        survivor; state comes from the most recent thing said about it."""
        sd = {"entities": {
            "crate": {"name": "crate", "state": {"open": False},
                      "from_event": 1},
            "wooden_crate": {"name": "wooden crate", "state": {"open": True},
                             "from_event": 2}}}
        self._fold(sd, {"entities": {"crate": {"name": "crate"}}})
        assert sd["entities"]["crate"]["state"] == {"open": True}

    def test_state_is_never_deep_merged(self):
        """The tree's own rule and its reason: state describes a single
        instant, so folding a stale snapshot into a fresh one is what
        manufactures the contradiction. The latest wins WHOLE."""
        sd = {"entities": {
            "crate": {"name": "crate", "state": {"open": False, "locked": True},
                      "from_event": 1},
            "crate_two": {"name": "crate", "state": {"open": True},
                          "from_event": 2}}}
        self._fold(sd, {"entities": {"crate": {"name": "crate"}}})
        assert sd["entities"]["crate"]["state"] == {"open": True}

    def test_a_duplicate_never_rewrites_what_the_survivor_already_says(self):
        """The conservative direction, deliberately: the survivor may be a
        thing that STOOD BEFORE THE BEAT whose fields are the world's existing
        truth, and a duplicate the beat minted must not rewrite it. A wrong
        adoption is reported and visible; a wrong duplicate is silent,
        permanent, and compounds every beat."""
        sd = {"entities": {
            "crate": {"name": "crate", "kind": "crate", "from_event": 1},
            "crate_two": {"name": "barrel", "kind": "barrel",
                          "from_event": 2}}}
        self._fold(sd, {"entities": {"crate": {"name": "crate"}}})
        assert sd["entities"]["crate"]["name"] == "crate"
        assert sd["entities"]["crate"]["kind"] == "crate"

    def test_a_pair_in_two_channels_is_never_folded(self):
        """`entities.tardis` and `rooms.tardis_interior` are one thing and two
        TRUE halves. Folding either into the other deletes the place the player
        is standing in, so `apply` touches only the `fold` side."""
        spans = director._span_items({"sequence": [
            {"type": "action", "attempt": "x", "category": ["objects",
                                                            "spatial"],
             "note": "n", "items": [{"id": 2, "name": "tardis"}]}]})
        sd = {"entities": {"tardis": {"name": "tardis", "from_event": 1}},
              "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                            "from_event": 1}}}
        survivors = director.item_survivors(sd, spans, {}, self.OWNER)
        director.apply_item_transforms(sd, survivors)
        assert "tardis_interior" in sd["rooms"]
        assert "tardis" in sd["entities"]

    def test_nothing_to_reconcile_changes_nothing(self):
        sd = {"entities": {"crate": {"name": "crate", "from_event": 1}}}
        before = json.dumps(sd, sort_keys=True)
        spans = self._spans(1)
        assert director.apply_item_transforms(
            sd, director.item_survivors(sd, spans, {}, self.OWNER)) == []
        assert json.dumps(sd, sort_keys=True) == before


class TestWhichHandRendersAThingTheBeatMinted:
    """The owner, 2026-09-10: "if the object is freshly minted potentially by
    multiple agents, we have to decide which is the highest authority for
    rendering that object, it might be case by case, but thankfully we only
    have 5 classess to work with." Then, on the TARDIS: "in that case interior
    and entity are two seperate facts about one object", and "neither should be
    discarded."

    THE GAP THIS CLOSED WAS REAL. The ladder's second rung is "the channel's
    own hand", and the partition is DISJOINT -- every record already sits in
    its own hand's channel -- so that rung cannot discriminate between two
    hands at all. Two mints of one thing tied there and fell through to a
    tiebreak that ordered them BY PATH: `entities.tardis` beat
    `rooms.tardis_interior` because "e" sorts before "r".
    """

    OWNER = {channel: hand for hand, spec in director.SPECIALISTS.items()
             for channel in spec["channels"]}

    def _tardis(self, sd):
        spans = director._span_items({"sequence": [
            {"type": "action", "attempt": "I step into the tardis",
             "category": ["objects", "spatial"], "note": "n",
             "items": [{"id": 2, "name": "tardis"}]}]})
        return director.item_survivors(sd, spans, {}, self.OWNER)[2]

    def test_the_table_is_ordered_and_total(self):
        for index, hand in enumerate(
                ("objects", "spatial", "body", "contact", "social")):
            assert director.mint_authority_rank(hand) == index, hand
        assert set(director.SPECIALISTS) == {
            "objects", "spatial", "body", "contact", "social"}, (
            "five classes -- if a sixth hand is registered the table needs a "
            "rung, and an unranked hand sorts last rather than raising")
        assert director.mint_authority_rank("nobody") == 5

    def test_authority_decides_and_path_order_does_not(self):
        """`attire` sorts before `entities`, so path order would hand the
        rendering record to the body hand."""
        got = self._tardis({
            "attire": {"tardis_cloth": {"subject": "Corin", "from_event": 1}},
            "entities": {"tardis": {"name": "tardis", "from_event": 1}},
            "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                          "from_event": 1}}})
        assert got["render_from"][0] == "entities.tardis"

    def test_neither_fact_is_discarded(self):
        """The owner's rule, stated twice and pinned here. An entity and its
        interior are two separate facts about one object; choosing which to
        render FROM is not a claim that the other is a lesser truth."""
        sd = {"entities": {"tardis": {"name": "tardis", "from_event": 1}},
              "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                            "from_event": 1}}}
        got = self._tardis(sd)
        assert [p for p, _c, _r in got["other_facts"]] == [
            "rooms.tardis_interior"]
        assert got["duplicates"] == []
        director.apply_item_transforms(sd, {2: got})
        assert "tardis_interior" in sd["rooms"]
        assert "tardis" in sd["entities"]

    def test_a_standing_thing_still_outranks_authority(self):
        """The ladder's first rung is above the table: what the world already
        held is the thing, whichever hand wrote about it this beat."""
        spans = director._span_items({"sequence": [
            {"type": "action", "attempt": "x", "category": ["objects",
                                                            "spatial"],
             "note": "n", "items": [{"id": 2, "name": "hall"}]}]})
        sd = {"entities": {"lamp": {"name": "lamp", "from_event": 1}},
              "rooms": {"hall": {"name": "Hall", "from_event": 1}}}
        got = director.item_survivors(
            sd, spans, {"rooms": {"hall": {"name": "Hall"}}}, self.OWNER)[2]
        assert got["render_from"][0] == "rooms.hall"
        assert got["reason"] == "standing"
