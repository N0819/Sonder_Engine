"""Regression tests for the resolve-reconciliation seam in agents/director.py.

The failure class: director_resolve's resolved_event PROSE asserts a
persistent, physically consequential change while its structured state_diff
omits it -- commit then applies stale objective truth and perception (which
renders from structured truth, never prose) contradicts the story next turn.

Live fixture reproduced here: an elevator beat resolved with "...the heavy
metal doors slide shut, sealing the two of you inside and blocking out the
smoky corridor" plus a control-panel entity set to descent_initiated -- but
the state_diff room entry for the elevator was a BLANK PLACEHOLDER
({"name":"","desc":"","adjacent":[],"notes":""}), remove_adjacent was empty
and conditions empty, so objective truth kept the doors "held open" onto the
smoke-filled hallway and the next turn re-rendered the open doorway.

The seam is three-tiered with all DETECTION deterministic on the common
path (zero extra LLM calls): Tier 0 = blank-placeholder floor + legacy
restraint scan + player authority_claim coverage; Tier 1 = director_
resolve's own changes_asserted manifest checked with category-aware
evidence classes and alias-aware subjects; Tier 2 = one bounded self-repair
call fired ONLY on a real detected gap, merged additively, with tiered
disposition authority (player claims non-rejectable) and warn-only fallback
-- never fabrication.

WHERE IT RUNS NOW. Since c452a50d (2026-09-12) `director_resolve` calls the
seam only on a beat with no causal ledger, and the prose Director (the only
one since 2026-09-27) writes rows on every beat its encoder answers -- so
through the stage these tests run it on a beat whose encoder returned no
events, and the rest call `_reconcile_resolution` directly. That gate is a
recorded defect (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3). Tier 1's
`changes_asserted` manifest was the causal Director's own and nothing writes
it now; its evidence classes are still pinned below for stored variants.
"""

from __future__ import annotations

import json
import time

from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData
from world.spatial import merge_scene_with_diff, spatial_rel

import agents.director as director
from agents.director import (
    _evidence_present,
    _is_blank_placeholder,
    _merge_repair_into_diff,
    _normalize_diff_shape,
    _omission_subject_encoded,
    _strip_blank_diff_placeholders,
    _subject_match_forms,
)
from core.db import set_setting
from tests.director_fakes import prose_resolve_agent


ELEVATOR_PROSE = (
    "Mara slams her palm against the control panel and the heavy metal "
    "doors slide shut, sealing the two of you inside and blocking out the "
    "smoky corridor. With a lurch, the elevator begins its descent."
)

ELEVATOR_SCENE = {
    "location": "Kessler Tower",
    "time": "night",
    "rooms": {
        "elevator_interior": {
            "name": "Service Elevator",
            "desc": "A cramped service elevator. The doors are currently "
                    "held open.",
            "adjacent": [
                {"to": "smoke_hallway", "barrier": "open_door",
                 "distance": "near"},
            ],
        },
        "smoke_hallway": {
            "name": "Smoke-filled Hallway",
            "desc": "A corridor thick with smoke.",
            "adjacent": [],
        },
    },
    "positions": {"The Stranger": "elevator_interior",
                  "Mara": "elevator_interior"},
    "entities": {"elevator_control_panel": {
        "name": "Elevator Control Panel", "kind": "fixture"}},
    "attire": {},
    "overlays": {},
}

# What the live director_resolve actually emitted: prose says sealed +
# descending, diff says nothing but a blank room placeholder and a panel
# state flag. The manifest design adds the changes_asserted entry the
# prompt now requires -- the deterministic evidence check is what turns it
# into a detected omission.
ELEVATOR_RESOLVE_OUTPUT = {
    "resolved_event": ELEVATOR_PROSE,
    "summary": "The elevator doors seal and the descent begins.",
    "dialogue_log": [],
    "changes_asserted": [
        {"category": "adjacency", "subject": "elevator_interior",
         "change": "The elevator doors are sealed shut against the "
                   "smoke-filled hallway."},
    ],
    "state_diff": {
        "rooms": {"elevator_interior": {
            "name": "", "desc": "", "adjacent": [], "notes": ""}},
        "entities": {"elevator_control_panel": {
            "name": "Elevator Control Panel", "kind": "fixture",
            "state": {"descent_initiated": True}}},
        "remove_adjacent": [],
        "conditions": {},
        "positions": {},
    },
}

ELEVATOR_REPAIR_OUTPUT = {
    "state_diff": {
        "rooms": {"elevator_interior": {
            "name": "Service Elevator",
            "desc": "A cramped service elevator, doors sealed shut, "
                    "descending.",
            "adjacent": [
                {"to": "smoke_hallway", "barrier": "closed_door",
                 "distance": "near"},
            ],
            "notes": "",
        }},
        "conditions": {"elevator_descending": [{
            "condition_id": "elevator_descending",
            "subject_id": "elevator_interior",
            "kind": "descending", "severity": 0.0,
            "started_at_seconds": 0.0, "state": {},
        }]},
    },
    "dispositions": [
        {"subject": "elevator_interior", "status": "encoded", "reason": ""},
    ],
}


def _make_ctx(temp_db, player_input, interp):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}",
         time.time(), "char_mara"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )
    temp_db.wset(chat_id, "scene", json.loads(json.dumps(ELEVATOR_SCENE)))
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
    ctx.director_interpret = interp
    return ctx


def _action_interp(authority_claims=None):
    return {
        "sequence": [{"type": "action",
                      "attempt": "slam the door-close button",
                      "commitment": "asserted", "targets": [],
                      "visibility": "overt", "conceal_from": []}],
        "speech": None, "action": {"attempt": "slam the door-close button"},
        "movement": None,
        "flow": {"reactors": [], "authority_claims": authority_claims or [],
                 "dice": [], "resolution_flags": {}, "fiction_frame": {}},
    }


def test_contact_manifest_checks_contact_ops_in_the_right_dimension():
    """A contact transition was previously classified as ``other`` because
    neither the prompt nor the evidence table admitted contact as a category.
    Correct contact_ops then triggered a needless repair and a false warning."""
    sd = _normalize_diff_shape({"contact_ops": [{
        "op": "add", "actor": "Elyra Voss", "actor_part": "left hand",
        "target": "Hinami", "target_part": "hip", "manner": "grip",
    }]})

    assert _evidence_present(sd, {
        "category": "contact", "subject": "Elyra Voss",
        "change": "Her left hand settles on Hinami's hip.",
    })
    assert _evidence_present(sd, {
        "category": "contact", "subject": "contacts",
        "change": "The standing contact changes.",
    })


def test_contact_manifest_cannot_be_satisfied_by_another_contact_same_actor():
    """Live chat 68 turn 15: the hand op made the actor present in contact_ops,
    and that shallow match falsely covered the separately manifested cervix
    contact. Both the model's ``contact_ops`` category spelling and the legacy
    endpoint-free manifest shape are reproduced here."""
    hand_only = _normalize_diff_shape({"contact_ops": [{
        "op": "add", "actor": "Elyra Voss", "actor_part": "left hand",
        "target": "Hinami", "target_part": "hip", "manner": "hold",
        "detail": "firm grip",
    }]})

    assert not _evidence_present(hand_only, {
        "category": "contact_ops", "subject": "Elyra Voss",
        "change": "Cock presses deeper against Hinami's cervix.",
    })
    assert _evidence_present(hand_only, {
        "category": "contact_ops", "subject": "Elyra Voss",
        "change": "Left hand tightens its grip on Hinami's hip.",
    })


def test_contact_manifest_structured_endpoints_match_exact_relation():
    sd = _normalize_diff_shape({"contact_ops": [{
        "op": "add", "actor": "Elyra Voss", "actor_part": "cock",
        "target": "Hinami", "target_part": "cervix", "manner": "insert",
    }]})
    manifest = {
        "category": "contact", "subject": "Elyra Voss",
        "change": "The interior contact moves deeper.",
        "actor": "Elyra Voss", "actor_part": "cock",
        "target": "Hinami", "target_part": "cervix",
    }

    assert _evidence_present(sd, manifest)
    assert not _evidence_present(sd, {**manifest, "target_part": "groin"})


def _dialogue_interp():
    return {
        "sequence": [{"type": "speech", "text": "How are you holding up?",
                      "volume": "normal"}],
        "speech": "How are you holding up?", "action": None, "movement": None,
        "flow": {"reactors": [], "authority_claims": [], "dice": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }


def _dispatching_agent_json(outputs, calls):
    """Fake _agent_json returning per-step canned outputs and recording the
    step keys invoked (resolve_reconcile, resolve_repair)."""
    def fake(role, step_key, system, payload, **kw):
        calls.append((step_key, payload))
        return json.loads(json.dumps(outputs.get(step_key, {})))
    return fake


# ---- deterministic floor: blank placeholder diff entries ----

def test_blank_placeholder_detection():
    assert _is_blank_placeholder(
        {"name": "", "desc": "", "adjacent": [], "notes": ""})
    assert _is_blank_placeholder({})
    assert not _is_blank_placeholder(
        {"name": "", "desc": "Doors sealed.", "adjacent": [], "notes": ""})
    assert not _is_blank_placeholder(
        {"name": "", "desc": "", "adjacent": [{"to": "hall"}], "notes": ""})
    assert not _is_blank_placeholder(
        {"state": {"descent_initiated": True}})
    # Non-dicts are not "placeholders" -- shape coercion handles them.
    assert not _is_blank_placeholder("elevator")


def test_strip_blank_placeholders_flags_and_removes_only_noise():
    sd = _normalize_diff_shape({
        "rooms": {
            "elevator_interior": {"name": "", "desc": "", "adjacent": [],
                                  "notes": ""},
            "smoke_hallway": {"name": "Hallway", "desc": "Smoky.",
                              "adjacent": [], "notes": ""},
        },
        "entities": {"panel": {}},
        "conditions": {"cond_x": []},
        "positions": {"Mara": ""},
        "attire": {},
    })
    signals = _strip_blank_diff_placeholders(sd)

    assert "elevator_interior" not in sd["rooms"]
    assert "smoke_hallway" in sd["rooms"]          # substantive entry kept
    assert "panel" not in sd["entities"]
    assert "cond_x" not in sd["conditions"]
    assert "Mara" not in sd["positions"]
    flagged = {(s["category"], s["subject"]) for s in signals}
    assert ("rooms", "elevator_interior") in flagged
    assert ("entities", "panel") in flagged
    assert ("conditions", "cond_x") in flagged
    assert ("positions", "Mara") in flagged
    assert all(s["source"] == "structural" for s in signals)


# ---- the elevator fixture, end to end through director_resolve ----


NO_EVENTS = {"events": [], "missing_tools": [], "missing_referents": [], "notes": []}

VAULT_CLAIMS = [{
    "claim_id": "claim:0:effect:0", "scope": "effect",
    "subject_id": "vault_door", "predicate": "shattered",
    "value": {}, "commitment": "asserted",
    "source_text": "I shatter the vault door",
}]


def _zero(output, calls, **per_step):
    """The prose Director answers; the encoder returns NO events, which is the
    only beat on which `_reconcile_resolution` runs."""
    return prose_resolve_agent(output, calls=calls,
                               per_step={"director_specialist": NO_EVENTS, **per_step})


def _direct(ctx, out, interp):
    director._reconcile_resolution(
        ctx, out, json.loads(json.dumps(ELEVATOR_SCENE)), interp, {}, [],
        ["Mara", "The Stranger"])
    return out


def test_elevator_omission_is_repaired(temp_db, monkeypatch):
    """Prose says sealed + descending; diff has a blank room placeholder.
    Detection is fully deterministic (structural signal + manifest gap --
    NO audit call); the Director's own repair delta must leave the final
    diff with the doors actually closed.

    Called directly since 2026-09-27: on the prose path the reconciliation runs
    only on a beat with no rows, where it reads the declaration template rather
    than the prose (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    interp = _action_interp()
    ctx = _make_ctx(temp_db, "I slam the door-close button.", interp)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "resolve_repair": ELEVATOR_REPAIR_OUTPUT}, calls))
    out = _direct(ctx, {"resolved_event": ELEVATOR_PROSE, "dialogue_log": [],
                        "state_diff": json.loads(json.dumps(
                            ELEVATOR_RESOLVE_OUTPUT["state_diff"]))}, interp)
    sd = out["state_diff"]
    assert [k for k, _ in calls] == ["resolve_repair"]
    assert out["reconciliation"]["repaired"] is True
    assert any(s["source"] == "structural" and s["subject"] == "elevator_interior"
               for s in out["reconciliation"]["signals"])
    edges = {e["to"]: e["barrier"] for e in sd["rooms"]["elevator_interior"]["adjacent"]}
    assert edges["smoke_hallway"] == "closed_door"
    assert "elevator_descending" in sd["conditions"]
    assert sd["entities"]["elevator_control_panel"]["state"]["descent_initiated"] is True
    assert not [w for w in ctx.warnings if "reconciliation" in w.casefold()]
    merged = merge_scene_with_diff(json.loads(json.dumps(ELEVATOR_SCENE)), sd)
    assert spatial_rel(merged, "elevator_interior", "smoke_hallway")["barrier"] == "closed_door"


def test_elevator_omission_is_flagged_when_repair_fails(temp_db, monkeypatch):
    """If the self-repair returns nothing usable, the seam must not invent
    state: the blank placeholder is still stripped (deterministic floor) and
    the unencoded manifest change surfaces as a warning.

    Called directly since 2026-09-27: on the prose path the reconciliation runs
    only on a beat with no rows, where it reads the declaration template rather
    than the prose (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    interp = _action_interp()
    ctx = _make_ctx(temp_db, "I slam the door-close button.", interp)
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "resolve_repair": {}}, []))
    out = _direct(ctx, {"resolved_event": ELEVATOR_PROSE, "dialogue_log": [],
                        "state_diff": json.loads(json.dumps(
                            ELEVATOR_RESOLVE_OUTPUT["state_diff"]))}, interp)
    assert "elevator_interior" not in out["state_diff"]["rooms"]
    assert any("Resolve reconciliation" in w for w in ctx.warnings)
    assert "elevator_interior" in {o["subject"] for o in out["reconciliation"]["unresolved"]}


# ---- no false positives / no cost on the common case ----

def test_pure_dialogue_turn_triggers_nothing(temp_db, prose_director, monkeypatch):
    """A speech-only beat with an empty diff and empty manifest must spend
    zero extra LLM calls and produce no warnings.

    Ported 2026-09-27 to the prose Director, on a beat whose encoder returned
    no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    ctx = _make_ctx(temp_db, '"How are you holding up?"', _dialogue_interp())
    calls = []
    monkeypatch.setattr(director, "_agent_json", _zero({
        "resolved_event": "The Stranger asks Mara how she is holding up."}, calls))
    out = director.director_resolve(ctx, nonce=0)
    assert [k for k, _ in calls] == ["director_prose", "director_specialist"]
    assert out["reconciliation"]["audited"] is False
    assert out["reconciliation"]["signals"] == []
    assert out["reconciliation"]["tripwire"] is False
    assert not ctx.warnings


# ---- category-aware evidence classes ----


def test_rooms_category_is_satisfied_by_desc_update():
    """The same desc-only diff DOES satisfy a 'rooms' category manifest item
    -- category classes must not over-fire on the dimension that was
    actually encoded."""
    sd = _normalize_diff_shape({
        "rooms": {"elevator_interior": {
            "name": "Service Elevator", "desc": "Scorched walls.",
            "adjacent": [], "notes": ""}},
    })
    assert _evidence_present(
        sd, {"category": "rooms", "subject": "elevator_interior"})
    assert not _evidence_present(
        sd, {"category": "adjacency", "subject": "elevator_interior"})


def test_transit_category_evidence_classes():
    """A transit manifest item is satisfied by an entity state.transit
    change, or by the entity's own position change (an arrival)."""
    sd = _normalize_diff_shape({
        "entities": {"service_elevator": {
            "name": "Service Elevator", "kind": "vehicle",
            "state": {"transit": {"phase": "sealed", "hatch": "closed"}}}},
    })
    assert _evidence_present(
        sd, {"category": "transit", "subject": "service_elevator"})
    sd2 = _normalize_diff_shape(
        {"positions": {"service_elevator": "sub4_shelter"}})
    assert _evidence_present(
        sd2, {"category": "transit", "subject": "service_elevator"})
    assert not _evidence_present(
        _normalize_diff_shape({}),
        {"category": "transit", "subject": "service_elevator"})


def test_conditions_category_accepts_an_ending_entry():
    """'The fire burns out' is encoded by an active:0 / expiring conditions
    entry -- the evidence class must accept removal-shaped encodings."""
    sd = _normalize_diff_shape({
        "conditions": {"warehouse_fire": [{
            "condition_id": "warehouse_fire", "subject_id": "warehouse",
            "kind": "fire", "active": 0}]},
    })
    assert _evidence_present(
        sd, {"category": "conditions", "subject": "warehouse_fire"})


# ---- Tier 0: player authority claim coverage ----

def test_omitted_player_claim_fires_repair_and_hard_warns(temp_db, prose_director, monkeypatch):
    """An asserted scope='effect' claim whose subject is nowhere in the diff
    is a hard omission: it fires the repair, and if still unencoded it
    ALWAYS warns -- dispositions cannot argue it away.

    Ported 2026-09-27 to the prose Director, on a beat whose encoder returned
    no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    ctx = _make_ctx(temp_db, "I shatter the vault door.",
                    _action_interp(authority_claims=VAULT_CLAIMS))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _zero({
        "resolved_event": "The vault door shatters into fragments."}, calls,
        resolve_repair={"state_diff": {}, "dispositions": [
            {"subject": "vault_door", "status": "rejected", "reason": "seems transient"}]}))
    out = director.director_resolve(ctx, nonce=0)
    assert [k for k, _ in calls].count("resolve_repair") == 1
    assert any("PLAYER AUTHORITY" in w for w in ctx.warnings)
    assert any(o["source"] == "player_claim" for o in out["reconciliation"]["unresolved"])


def test_encoded_player_claim_is_silent(temp_db, prose_director, monkeypatch):
    """Ported 2026-09-27 to the prose Director, on a beat whose encoder
    returned no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    interp = _action_interp(authority_claims=VAULT_CLAIMS)
    interp["state_assertions"] = {"remove_entities": ["vault_door"]}
    ctx = _make_ctx(temp_db, "I shatter the vault door.", interp)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _zero({
        "resolved_event": "The vault door shatters into fragments."}, calls))
    out = director.director_resolve(ctx, nonce=0)
    assert "resolve_repair" not in [k for k, _ in calls]
    assert out["reconciliation"]["omissions"] == []
    assert not ctx.warnings


def test_null_subject_claim_degrades_to_metadata_note(temp_db, prose_director, monkeypatch):
    """A claim with no resolvable subject cannot be containment-checked;
    it becomes a metadata note, never a warning or a repair trigger.

    Ported 2026-09-27 to the prose Director, on a beat whose encoder returned
    no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    claims = [{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": None, "predicate": "everything feels colder",
        "value": {}, "commitment": "asserted", "source_text": "it gets cold",
    }]
    ctx = _make_ctx(temp_db, "It gets cold.", _action_interp(authority_claims=claims))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _zero({
        "resolved_event": "A chill settles over the room."}, calls))
    out = director.director_resolve(ctx, nonce=0)
    assert [k for k, _ in calls] == ["director_prose", "director_specialist"]
    assert out["reconciliation"]["claim_notes"]
    assert not ctx.warnings


def test_rejected_asserted_claim_is_a_contract_violation(temp_db, monkeypatch):
    """claim_dispositions cross-check: an asserted claim marked 'rejected'
    violates the player authority contract and warns deterministically,
    even when the effect itself IS encoded.

    Called directly since 2026-09-27: on the prose path the reconciliation runs
    only on a beat with no rows, where it reads the declaration template rather
    than the prose (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    interp = _action_interp(authority_claims=VAULT_CLAIMS)
    ctx = _make_ctx(temp_db, "I shatter the vault door.", interp)
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({}, []))
    _direct(ctx, {"resolved_event": "The vault door shatters.", "dialogue_log": [],
                  "state_diff": {"remove_entities": ["vault_door"]},
                  "claim_dispositions": [
                      {"claim_id": "claim:0:effect:0", "status": "rejected"}]}, interp)
    assert any("PLAYER AUTHORITY" in w and "rejected" in w for w in ctx.warnings)


# ---- the folded-in restraint detector ----

def test_restraint_omission_repaired_through_seam(temp_db, monkeypatch):
    """The legacy restraint scan feeds the same seam: a narrated gunpoint
    hold with no condition triggers the repair (deterministically -- no
    audit call), and an encoded condition silences the legacy warning.

    Called directly since 2026-09-27: on the prose path the reconciliation runs
    only on a beat with no rows, where it reads the declaration template rather
    than the prose (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    interp = _dialogue_interp()
    ctx = _make_ctx(temp_db, "I keep talking.", interp)
    calls = []
    mend = {
        "state_diff": {"conditions": {"mara_restrained": [{
            "condition_id": "mara_restrained", "subject_id": "Mara",
            "kind": "restrained", "severity": 0.6,
            "started_at_seconds": 0.0, "state": {},
        }]}},
        "dispositions": [{"subject": "Mara", "status": "encoded", "reason": ""}],
    }
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "resolve_repair": mend}, calls))
    out = _direct(ctx, {"resolved_event": "The guard keeps Mara pinned at gunpoint "
                                          "against the wall.",
                        "dialogue_log": [], "state_diff": {}}, interp)
    assert [k for k, _ in calls] == ["resolve_repair"]
    assert "mara_restrained" in out["state_diff"]["conditions"]
    assert not any("untracked physical restraint" in w for w in ctx.warnings)


def test_restraint_warning_survives_failed_repair(temp_db, monkeypatch):
    """When the repair cannot encode the restraint, the exact legacy
    warn-only behavior remains as the floor.

    Called directly since 2026-09-27: on the prose path the reconciliation runs
    only on a beat with no rows, where it reads the declaration template rather
    than the prose (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    interp = _dialogue_interp()
    ctx = _make_ctx(temp_db, "I keep talking.", interp)
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "resolve_repair": {}}, []))
    _direct(ctx, {"resolved_event": "The guard keeps Mara pinned at gunpoint "
                                    "against the wall.",
                  "dialogue_log": [], "state_diff": {}}, interp)
    assert any("untracked physical restraint" in w for w in ctx.warnings)


# ---- silent-false-negative tripwire + deep-audit escalation ----

def test_tripwire_flags_eventful_beat_with_empty_manifest(temp_db, prose_director, monkeypatch):
    """Successful dice + empty manifest + empty physical diff = the beat
    provably did something the model reported nowhere. Metadata flag only
    (deep audit is default-off) -- no calls, no warnings.

    Ported 2026-09-27 to the prose Director, on a beat whose encoder returned
    no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    interp = _action_interp()
    interp["flow"]["dice"] = [{"actor": "The Stranger", "attempt": "force the hatch",
                               "ability": "might", "difficulty": "easy"}]
    ctx = _make_ctx(temp_db, "I force the hatch.", interp)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _zero({
        "resolved_event": "With a grunt, something gives way."}, calls))
    monkeypatch.setattr(director, "_ability_mod", lambda *a, **k: 30)
    out = director.director_resolve(ctx, nonce=0)
    assert [k for k, _ in calls] == ["director_prose", "director_specialist"]
    assert out["reconciliation"]["tripwire"] is True
    assert not ctx.warnings


def test_tripwire_escalates_to_deep_audit_when_opted_in(temp_db, prose_director, monkeypatch):
    """resolve_deep_audit='tripwire' wires the retained standalone audit to
    the tripwire; its findings flow into the normal repair path.

    Ported 2026-09-27 to the prose Director, on a beat whose encoder returned
    no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    set_setting("resolve_deep_audit", "tripwire")
    try:
        interp = _action_interp()
        interp["flow"]["dice"] = [{"actor": "The Stranger", "attempt": "force the hatch",
                                   "ability": "might", "difficulty": "easy"}]
        ctx = _make_ctx(temp_db, "I force the hatch.", interp)
        calls = []
        monkeypatch.setattr(director, "_agent_json", _zero({
            "resolved_event": "The hatch tears free of its hinges."}, calls,
            resolve_reconcile={"omissions": [{
                "category": "entities", "subject": "hatch",
                "change": "The hatch is torn from its hinges.",
                "evidence": "tears free of its hinges", "confidence": 0.9,
            }], "notes": ""},
            resolve_repair={"state_diff": {
                "entities": {"hatch": {"name": "Torn Hatch", "kind": "object",
                                       "state": {"broken": True}}}},
                "dispositions": [{"subject": "hatch", "status": "encoded", "reason": ""}]}))
        monkeypatch.setattr(director, "_ability_mod", lambda *a, **k: 30)
        out = director.director_resolve(ctx, nonce=0)
        steps = [k for k, _ in calls]
        assert steps == ["director_prose", "director_specialist",
                         "resolve_reconcile", "resolve_repair"]
        assert out["reconciliation"]["audited"] is True
        assert out["reconciliation"]["repaired"] is True
        assert "hatch" in out["state_diff"]["entities"]
    finally:
        set_setting("resolve_deep_audit", "")


# ---- merge conservatism + subject machinery ----

def test_repair_merge_is_additive_and_cannot_move_validated_positions():
    sd = _normalize_diff_shape({
        "positions": {"The Stranger": "lamp_room"},
        "rooms": {"lamp_room": {"name": "Lamp Room", "desc": "Bright.",
                                "adjacent": [{"to": "stairs",
                                              "barrier": "open"}]}},
        "remove_adjacent": [{"room": "lamp_room", "to": "gallery"}],
    })
    patch = _normalize_diff_shape({
        # May NOT override the deterministically validated player move.
        "positions": {"The Stranger": "cliff_path", "Lantern": "lamp_room"},
        # Adjacency merges edge-aware: the existing edge survives.
        "rooms": {"lamp_room": {"adjacent": [{"to": "gallery",
                                              "barrier": "closed_door"}]}},
        "remove_adjacent": [{"room": "lamp_room", "to": "gallery"},
                            {"room": "stairs", "to": "cellar"}],
    })

    _merge_repair_into_diff(sd, patch)

    assert sd["positions"]["The Stranger"] == "lamp_room"
    assert sd["positions"]["Lantern"] == "lamp_room"
    edges = {e["to"]: e["barrier"] for e in sd["rooms"]["lamp_room"]["adjacent"]}
    assert edges == {"stairs": "open", "gallery": "closed_door"}
    assert {"room": "stairs", "to": "cellar"} in sd["remove_adjacent"]
    # Union, not duplication.
    assert sd["remove_adjacent"].count(
        {"room": "lamp_room", "to": "gallery"}) == 1


def test_omission_subject_containment_check():
    sd = _normalize_diff_shape({
        "rooms": {"elevator_interior": {"name": "Service Elevator"}},
        "conditions": {"c1": [{"subject_id": "Mara", "kind": "restrained"}]},
        "remove_adjacent": [{"room": "vault", "to": "hall"}],
    })
    assert _omission_subject_encoded(sd, "elevator")          # substring
    assert _omission_subject_encoded(sd, "Service Elevator")  # by name
    assert _omission_subject_encoded(sd, "Mara")              # condition
    assert _omission_subject_encoded(sd, "vault")             # removal edge
    assert not _omission_subject_encoded(sd, "smoke hallway")
    assert not _omission_subject_encoded(sd, "")


def test_alias_aware_subjects_resolve_through_entity_aliases():
    """A manifest subject naming an entity by ALIAS must match a diff entry
    keyed by the entity's id -- the name-vs-uid-vs-alias hole. The prior
    scene supplies the alias table."""
    sc = {"entities": {"tardis_exterior": {
        "name": "The TARDIS", "kind": "vehicle",
        "aliases": ["blue police box"]}}}
    forms = _subject_match_forms("blue police box", [], sc)
    assert "tardis_exterior" in forms
    sd = _normalize_diff_shape({
        "entities": {"tardis_exterior": {"name": "The TARDIS",
                                         "state": {"transit": {
                                             "phase": "in_transit"}}}},
    })
    assert _omission_subject_encoded(sd, "blue police box", forms)
    assert _evidence_present(
        sd, {"category": "transit", "subject": "blue police box"}, forms)
    # Without alias expansion the same subject would miss.
    assert not _omission_subject_encoded(sd, "blue police box")


# ---------------------------------------------------------------------------
# The checker must be able to SEE a correct encoding (chat 71, turn 2354).
# ---------------------------------------------------------------------------
#
# Live ground truth, resolve variants v26625/v26634/v26643 (three orchestrated
# rerolls of one beat): every dispatched specialist ran, and the merged
# state_diff carried their encodings -- attire.Hinami.remove the jacket,
# contact_ops remove(stomach)+add(waist), the jacket entity shed, an
# inventory drop, a station {at: null}. The beat was ENCODED. The
# deterministic evidence classes then reported five of six manifest items as
# omissions anyway, fired the Tier-2 repair on them (tens of seconds), the
# repair answered "already_encoded", the disposition lookup lost that answer
# to an exact-subject match, and three false "objective state may be stale"
# warnings shipped per reroll. The checker, not the encoding, was wrong:
# each class gated on the manifest's free-text SUBJECT naming one particular
# kind of thing (the wearer for attire, a participant for contacts, a
# positions key for a placement), while the model words the subject freely
# ("lightweight travel jacket", "contact_end", "prior hand-to-stomach
# contact") -- so coverage flickered reroll to reroll with the wording.
# These fixtures are the live diffs verbatim.

_LIVE_ATTIRE_SD = {  # v26625: garment-subject manifest, wearer-keyed channel
    "attire": {"Hinami": {"add": [], "remove": ["lightweight travel jacket"],
                          "conditions": {}, "coverage": {}, "regions": {},
                          "notes": {}}},
}

_LIVE_CONTACT_OPS = [  # v26625: the specialist's own encoding
    {"op": "remove", "actor": "Elyra Voss", "actor_part": "hand",
     "target": "Hinami", "target_part": "stomach",
     "source": "character_declaration", "declared_by": "Elyra Voss"},
    {"op": "add", "actor": "Elyra Voss", "actor_part": "hand",
     "target": "Hinami", "target_interior": "", "target_part": "waist",
     "manner": "grip", "relation": "surface", "motion": "settled",
     "detail": "fingers hooked beneath utility sash"},
]


def test_attire_evidence_accepts_the_garment_as_subject():
    """v26625: manifest subject 'lightweight travel jacket', channel keyed by
    the WEARER. The attire class checked only wearer keys, so a correctly
    encoded removal read as an omission whenever the model named the garment
    rather than the body it came off."""
    omission = {"category": "attire", "subject": "lightweight travel jacket",
                "change": "fully removed from Hinami's remaining shoulder"}
    assert _evidence_present(_LIVE_ATTIRE_SD, omission)
    # The wearer-subject spelling (v26634) keeps working.
    assert _evidence_present(_LIVE_ATTIRE_SD,
                             {"category": "attire", "subject": "Hinami",
                              "change": "jacket removed"})
    # And a garment nowhere in the channel still reads as omitted.
    assert not _evidence_present(_LIVE_ATTIRE_SD,
                                 {"category": "attire",
                                  "subject": "utility sash",
                                  "change": "sash unbuckled"})


def test_contact_evidence_trusts_structured_endpoints_over_the_subject():
    """v26625/v26643: the manifest carried full structured endpoints
    (actor/actor_part/target/target_part) -- added for exactly this check --
    but the participant gate demanded the free-text SUBJECT name a
    participant before endpoints were even compared. 'contact_end' and
    'prior hand-to-stomach contact' name the RELATION, so ops matching the
    manifest's own endpoints exactly were invisible; v26634 passed only
    because the model happened to spell 'Hinami' inside the subject."""
    sd = {"contact_ops": list(_LIVE_CONTACT_OPS)}
    for subject in ("contact_end", "prior hand-to-stomach contact"):
        assert _evidence_present(sd, {
            "category": "contacts", "subject": subject, "change": "ended",
            "actor": "Elyra Voss", "actor_part": "hand",
            "target": "Hinami", "target_part": "stomach"}), subject
    assert _evidence_present(sd, {
        "category": "contacts", "subject": "contact_new",
        "change": "established", "actor": "Elyra Voss",
        "actor_part": "hand", "target": "Hinami", "target_part": "waist"})
    # Endpoints still discriminate: a manifested relation no op encodes
    # (hand at the SHOULDER) stays an omission whatever the subject says.
    assert not _evidence_present(sd, {
        "category": "contacts", "subject": "contact_new",
        "change": "established", "actor": "Elyra Voss",
        "actor_part": "hand", "target": "Hinami",
        "target_part": "shoulder"})


def test_contact_evidence_reads_a_cross_op_for_the_ended_endpoint():
    """v26643 encoded the hand's move as op:'cross' with
    crossed_target_part:'stomach' -- the one op the repair sheet itself
    prescribes for relocating a standing endpoint -- and the checker
    compared manifests only against target_part, so the ENDED contact could
    never be covered by the very op that ends it."""
    sd = {"contact_ops": [{
        "op": "cross", "actor": "Elyra Voss", "actor_part": "hand",
        "target": "Hinami", "crossed_target_part": "stomach",
        "target_interior": "", "target_part": "waist", "manner": "hook",
        "relation": "surface", "motion": "moving",
        "detail": "fingers trailing before hooking under the sash"}]}
    assert _evidence_present(sd, {
        "category": "contacts", "subject": "prior hand-to-stomach contact",
        "change": "ended", "actor": "Elyra Voss", "actor_part": "hand",
        "target": "Hinami", "target_part": "stomach"})


def test_positions_evidence_accepts_a_station_for_a_within_room_drop():
    """v26634: 'dropped from platform edge to the stone floor' -- the room
    unchanged, the placement encoded as stations {at: null} (plus an
    inventory transfer and the entity's own state). The positions class
    consulted only sd.positions and cast_changes, so a within-room placement
    the model filed under 'positions' was an omission however thoroughly the
    diff carried it."""
    sd = {"stations": {"lightweight travel jacket": {"at": None,
                                                    "near": []}}}
    assert _evidence_present(sd, {
        "category": "positions", "subject": "lightweight travel jacket",
        "change": "dropped from platform edge to the stone floor"})
    # A subject with no placement anywhere still reads as omitted.
    assert not _evidence_present(sd, {
        "category": "positions", "subject": "Elyra Voss",
        "change": "left the room"})


def test_disposition_subjects_match_with_the_same_tolerance_as_evidence(temp_db, prose_director, monkeypatch):
    """The core repair still owns every omission no specialist can answer --
    player claims and undelegated categories -- and its dispositions are
    still matched by subject TEXT, so v26625's own tolerance still has to
    hold there. `transit` reaches no delegated channel, so it routes to the
    core exactly as it always did.

    Ported 2026-09-27 to the prose Director, on a beat whose encoder returned
    no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    set_setting("resolve_deep_audit", "always")
    try:
        ctx = _make_ctx(temp_db, "I slam the door-close button.", _action_interp())
        calls = []
        monkeypatch.setattr(director, "_agent_json", _zero(
            {"resolved_event": ELEVATOR_PROSE}, calls,
            resolve_reconcile={"omissions": [{
                "category": "transit", "subject": "elevator_interior",
                "change": "The elevator is now in transit between floors.",
                "evidence": "begins its descent", "confidence": 0.9}], "notes": ""},
            resolve_repair={"state_diff": {}, "dispositions": [{
                "subject": "elevator_interior — now in transit between floors, doors sealed",
                "status": "already_encoded", "reason": "the panel state already carries it"}]}))
        out = director.director_resolve(ctx, nonce=0)
        assert [k for k, _ in calls].count("resolve_repair") == 1
        entry = next(o for o in out["reconciliation"]["unresolved"]
                     if o["subject"] == "elevator_interior" and o.get("source") == "audit")
        assert entry["disposition"] == "already_encoded"
        assert not [w for w in ctx.warnings
                    if "still does not encode" in w and "in transit" in w]
    finally:
        set_setting("resolve_deep_audit", "")


# --- a quote inside a declared line is not a new utterance -----------------

class TestProseQuoteAuthorityDoesNotFlagQuotation:
    """Measured across the live corpus: 14 flags, 13 false. Every firing costs
    a full second Director call -- the most expensive retry the engine has --
    so a 93% false-positive rate here was the single largest source of the
    6s-to-60s spread in director_resolve latency.

    Two causes, one shape. `_PROSE_QUOTE_RES` sweeps the prose with four
    independent patterns, so a declared line carrying inner quotes yields the
    outer span AND each inner one; and the membership test was exact, so a
    Director that re-punctuated a line it was faithfully quoting failed to
    match its own source.
    """

    def test_a_nested_quote_is_not_an_invention(self):
        from agents.common import _check_prose_quote_authority
        declared = ['And I said "ask me again" — not "yes, absolutely, show '
                    'you the stars." Though I\'ll grant you it\'s closer to '
                    'yes than no.']
        prose = ("He adds, 'And I said \"ask me again\" — not \"yes, "
                 "absolutely, show you the stars.\" Though I'll grant you "
                 "it's closer to yes than no.'")
        assert _check_prose_quote_authority(prose, set(declared)) == []

    def test_a_repunctuated_declared_line_is_not_an_invention(self):
        from agents.common import _check_prose_quote_authority
        declared = ["Only a mere ten minute walk"]
        prose = "She says, 'Only a mere ten-minute walk,' and sets off."
        assert _check_prose_quote_authority(prose, set(declared)) == []

    def test_a_line_nobody_declared_is_still_caught(self):
        from agents.common import _check_prose_quote_authority
        warnings = _check_prose_quote_authority(
            'The ferryman says, "Not too full. Spills make mud."',
            {"Mind the step", "I will take the oars"})
        assert len(warnings) == 1
        assert "Spills make mud" in warnings[0]

    def test_prose_that_expands_on_a_declared_line_is_still_caught(self):
        """Containment is ONE direction. A declared line sitting inside the
        flagged span is prose that added words to what somebody said, which is
        the invention this guard exists for -- allowing that direction cleared
        the corpus's one genuine case along with the thirteen false ones."""
        from agents.common import _check_prose_quote_authority
        warnings = _check_prose_quote_authority(
            'He says, "Mind the step, and mind the man behind you."',
            {"Mind the step"})
        assert len(warnings) == 1


# --- a subject nobody can point at is not a claim anyone can check --------

def _meta_claim_interp(player_input):
    interp = _action_interp()
    interp["flow"]["authority_claims"] = [{
        "claim_id": "claim:1:event", "scope": "effect",
        # A schema placeholder, not a referent. The model reached for it
        # when the "subject" slot did not fit what it was reading.
        "subject_id": "narrative_assertion",
        "predicate": "even at late hour someone should be staffing it",
        "value": None, "commitment": "asserted",
        "source_text": "even at late hour someone should be staffing it",
    }]
    return interp


def test_an_unreferrable_claim_subject_degrades_to_a_note(temp_db, prose_director, monkeypatch):
    """Live, chat 72 turn 45. The player added an out-of-fiction aside to
    the engine -- "(it is a hotel. even at late hour someone should be
    staffing it, use logic and reasoning instead of assuming no one is
    there)" -- and interpret turned it into TWO asserted completed effects
    on a subject called `narrative_assertion`, split at a comma.

    Player claims are non-rejectable by design, so each one warned every
    beat and could never be satisfied: `narrative_assertion` names nothing
    in the world and nothing the player typed, so `_omission_subject_
    encoded` can only ever answer False. Between them they bought one
    full-core repair call -- the most expensive retry the engine has -- to
    encode a remark addressed to the engine rather than to the fiction, and
    the repair's own 'already_encoded' answer could not stop the warnings.

    The floor is the same shape as the null-subject one already here: a
    claim whose subject is neither resolvable in the world NOR present in
    the player's own words is not coverage-checkable, so it becomes a
    metadata note. Nothing about player authority is weakened -- see the
    two tests below for the cases that must stay hard.

    Ported 2026-09-27 to the prose Director, on a beat whose encoder returned
    no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    ctx = _make_ctx(temp_db,
                    "I ring the bell. (it is a hotel, someone should be staffing it)",
                    _meta_claim_interp("I ring the bell."))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _zero({
        "resolved_event": "The bell rings out across the empty lobby."}, calls))
    out = director.director_resolve(ctx, nonce=0)
    assert "resolve_repair" not in [k for k, _ in calls]
    assert not [w for w in ctx.warnings if "PLAYER AUTHORITY" in w]
    assert any(n.get("predicate") == "even at late hour someone should be staffing it"
               for n in out["reconciliation"]["claim_notes"])


def test_a_claim_the_player_named_in_their_own_words_stays_hard(temp_db, prose_director, monkeypatch):
    """The case that must NOT soften. `vault_door` is in no scene here --
    the player is asserting it into existence, which is exactly what player
    authority is for -- but they typed the words, so the subject has a
    referent and the coverage check is real.

    Ported 2026-09-27 to the prose Director, on a beat whose encoder returned
    no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    ctx = _make_ctx(temp_db, "I shatter the vault door.",
                    _action_interp(authority_claims=VAULT_CLAIMS))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _zero({
        "resolved_event": "The vault door shatters into fragments."}, calls,
        resolve_repair={"state_diff": {}, "dispositions": []}))
    director.director_resolve(ctx, nonce=0)
    assert [k for k, _ in calls].count("resolve_repair") == 1
    assert any("PLAYER AUTHORITY" in w for w in ctx.warnings)


def test_a_claim_on_a_standing_scene_subject_stays_hard(temp_db, prose_director, monkeypatch):
    """The other case that must not soften: the player says "I snuff the
    lamp" and the claim's subject is the scene's own `elevator_control_panel`
    id, which they never typed. Resolvable in the WORLD is enough on its
    own -- either channel qualifies, and only failing both is unreferrable.

    Ported 2026-09-27 to the prose Director, on a beat whose encoder returned
    no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    claims = [{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": "elevator_control_panel", "predicate": "smashed",
        "value": {}, "commitment": "asserted", "source_text": "I smash the panel",
    }]
    ctx = _make_ctx(temp_db, "I smash the panel.", _action_interp(authority_claims=claims))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _zero({
        "resolved_event": "The panel cracks under the blow."}, calls,
        resolve_repair={"state_diff": {}, "dispositions": []}))
    director.director_resolve(ctx, nonce=0)
    assert any("PLAYER AUTHORITY" in w for w in ctx.warnings)


# ---- Tier 0: a claim subject that is not a THING ----
#
# Player authority makes an asserted EFFECT true. It does not make that
# effect's grammatical subject an object. The referrability gate lets a
# subject through on either of two channels and only one of them is evidence
# of thinghood -- the world already holds a record for it; the other, "the
# player typed the word", is satisfied by every noun in a narrated sentence.
# The repair sheet then forbade the only correct answer for the second class
# ("never 'rejected'"), so the only permitted answer was to encode, and
# encoding a subject the world model has no shape for means MINTING IT AS A
# SCENE ENTITY. Measured over the audited 15-beat run: that is where the
# minted entities came from.

def _worldless_claim(subject, predicate, source_text):
    return [{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": subject, "predicate": predicate,
        "value": {}, "commitment": "asserted", "source_text": source_text,
    }]


def _mint_nothing_resolve():
    return {
        "resolved_event": "The reading holds steady.",
        "summary": "Nothing structural.",
        "dialogue_log": [], "changes_asserted": [], "state_diff": {},
    }


def test_a_claim_subject_with_no_referent_is_refused_without_a_warning(temp_db, prose_director, monkeypatch):
    """A grammatical subject the world model has no shape for -- a measure, a
    pattern, a state of light -- is not a thing, and the repair may now say
    so. The effect still stands; what does not happen is a scene entity.

    Ported 2026-09-27 to the prose Director, on a beat whose encoder returned
    no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    subject = "the ambient level"
    ctx = _make_ctx(temp_db, "The ambient level steadies.",
                    _action_interp(authority_claims=_worldless_claim(
                        subject, "steadied", "The ambient level steadies")))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _zero(
        _mint_nothing_resolve(), calls,
        resolve_repair={"state_diff": {}, "dispositions": [
            {"subject": subject, "status": "no_referent", "reason": "a measure"}]}))
    out = director.director_resolve(ctx, nonce=0)
    assert not any("PLAYER AUTHORITY" in w for w in ctx.warnings), ctx.warnings
    assert not (out["state_diff"].get("entities") or {}), out["state_diff"]
    notes = out["reconciliation"]["claim_notes"]
    assert any(n.get("subject") == subject for n in notes), notes
    assert [o for o in out["reconciliation"]["unresolved"]
            if o.get("disposition") == "no_referent"]


def test_a_subject_the_world_already_knows_can_never_be_refused(temp_db, prose_director, monkeypatch):
    """The verdict is bounded the way `already_true` is. A subject naming a
    room the scene contains IS a thing, so the refusal is inadmissible there
    and non-rejectability stands exactly as before.

    Ported 2026-09-27 to the prose Director, on a beat whose encoder returned
    no events: the only beat on which the resolve reconciliation runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3).
    """
    subject = "elevator_interior"
    ctx = _make_ctx(temp_db, "I seal the room.",
                    _action_interp(authority_claims=_worldless_claim(
                        subject, "sealed", "I seal the room")))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _zero(
        _mint_nothing_resolve(), calls,
        resolve_repair={"state_diff": {}, "dispositions": [
            {"subject": subject, "status": "no_referent", "reason": "trying it on"}]}))
    out = director.director_resolve(ctx, nonce=0)
    assert any("PLAYER AUTHORITY" in w for w in ctx.warnings), ctx.warnings
    notes = out["reconciliation"]["claim_notes"]
    assert not [n for n in notes if n.get("subject") == subject], notes


def test_the_two_referrability_channels_answer_different_questions():
    """The split the whole fix rests on: what the world knows is evidence of
    thinghood; what the player typed is not, because every noun of a narrated
    sentence satisfies it."""
    from agents.director import (_claim_subject_in_world,
                                 _claim_subject_is_referrable,
                                 _subject_match_forms)

    sc = {"rooms": {"room_a": {"name": "Room A"}}, "entities": {}}
    typed = "the shifting pattern on the wall of room a"

    forms = _subject_match_forms("shifting_pattern", [], sc)
    assert _claim_subject_is_referrable("shifting_pattern", forms, sc, typed)
    assert not _claim_subject_in_world("shifting_pattern", forms, sc)

    forms = _subject_match_forms("room_a", [], sc)
    assert _claim_subject_in_world("room_a", forms, sc)


def test_the_repair_sheet_permits_the_refusal_in_every_pack():
    """The sheet used to forbid the only correct answer, and a prompt is read
    by every story -- so the vocabulary has to exist in every pack that ships
    one, not just the one this was found in."""
    from language_runtime import installed_language_packs, raw_card

    packs = sorted(pack.id for pack in installed_language_packs().values()
                   if pack.story)
    assert packs
    for language in packs:
        text = raw_card(language)["prompts"]["resolve_repair"]
        assert "no_referent" in text, language
        assert "player_claim" in text, language


def test_the_refusal_verdict_is_wired_into_the_seam():
    """One keyword on one branch, in a function a green suite would not
    notice losing it from: assert the wiring itself."""
    import inspect

    source = inspect.getsource(director._reconcile_resolution)
    assert "_verify_no_referent(" in source
    assert "_NO_REFERENT" in source


def test_a_doorway_encoded_as_an_anchor_is_not_an_omission():
    """A CHANNEL THIS DOES NOT WALK IS A CHANNEL IN WHICH A CORRECT ENCODING
    READS AS AN OMISSION -- `_omission_subject_encoded`'s own docstring, and
    the `rooms` channel found the case.

    The walk reads room ids and a room's `name`. A DOORWAY's identity in
    that channel is an ANCHOR KEY: `effective_anchors` mints `door:<to>` for
    every edge, and an authored doorway is keyed by its own id.

    Measured (chat 117, turn 21): the player hauled a bulkhead fully open.
    The objects hand declined it as the spatial hand's -- "opening a door
    between rooms is an edge barrier change belonging to spatial" -- the
    engine rerouted it, and spatial encoded the barrier on the edge with the
    doorway redescribed under `anchors`. The world was right: open on both
    sides, and sight between the two bodies went to `full`. The beat still
    reported the change unencoded, which is the noise that makes a good turn
    look broken.
    """
    from agents.director import _omission_subject_encoded

    encoded = {"rooms": {"sub5a_service_spine": {
        "adjacent": [{"to": "sub5a_plant_room", "barrier": "open_door"}],
        "anchors": {"plant_room_bulkhead_door": {
            "desc": "A reinforced steel bulkhead door, locked fully open "
                    "against the wall stop."}}}}}
    assert _omission_subject_encoded(encoded, "plant_room_bulkhead_door")
    # The doorway's own description answers for it too, which is how a
    # subject named in prose rather than by id is found.
    assert _omission_subject_encoded(
        {"rooms": {"r": {"anchors": {"a1": {"desc": "the iron wicket"}}}}},
        "the iron wicket")
    # And it stays a containment check, not a wildcard: a subject the diff
    # never mentions is still an omission.
    assert not _omission_subject_encoded(encoded, "security_grate")
    assert not _omission_subject_encoded({"rooms": {"r": {}}}, "anything")


def test_a_doors_identity_is_an_anchor_key_in_every_evidence_class():
    """The category-AWARE reader had the blindness the agnostic one was
    fixed for, and it is the one the manifest path uses.

    A doorway is never a room, so a reader that stops at a room's id and
    name cannot see the subject of an adjacency claim. Measured twice in
    chat 117 and the same shape both times: turn 21 (a bulkhead hauled
    open) was fixed in `_omission_subject_encoded` alone, and turn 44 came
    straight back through `_evidence_present`. The objects hand declined
    the door as spatial's, spatial encoded the edge barrier with the door
    under `anchors.fire_egress_door`, and the beat still warned that
    objective state might be stale. The three ways a manifest spells this
    beat -- `door`, `barrier`, `portal` -- all fold onto `adjacency` and
    `transit`, and all three reported a perfectly encoded door unencoded."""
    from agents.director import _evidence_present

    encoded = {"rooms": {"landing": {
        "name": "The Landing",
        "adjacent": [{"to": "riser", "barrier": "open_door", "dir": "s"}],
        "anchors": {"fire_egress_door": {"desc": "a heavy steel door",
                                         "dir": "s"}}}}}
    for category in ("adjacency", "transit", "rooms", "portal", "barrier",
                     "door"):
        assert _evidence_present(
            encoded, {"subject": "fire_egress_door", "category": category,
                      "change": "eased ajar"}), category

    # Still evidence, not mere mention: a room merely redescribed does not
    # acquit an edge claim, which is what the `adjacent` conjunct holds.
    redescribed = {"rooms": {"landing": {
        "name": "The Landing",
        "anchors": {"fire_egress_door": {"desc": "a heavy steel door"}}}}}
    assert not _evidence_present(
        redescribed, {"subject": "fire_egress_door", "category": "adjacency",
                      "change": "eased ajar"})
    # And a door nobody encoded is still unencoded.
    assert not _evidence_present(
        {"rooms": {"landing": {"name": "The Landing",
                               "adjacent": [{"to": "riser"}]}}},
        {"subject": "fire_egress_door", "category": "adjacency",
         "change": "eased ajar"})

    # THIRD TIME, chat 117 turn 110: SHUTTING a door changes the edge and
    # nothing about the doorway, so a correct beat restates no anchors and
    # the fixture is only in the SCENE. Reading anchors out of the diff
    # alone, this could never find the subject -- and the beat warned that
    # objective state might be stale after buying a self-repair retry, with
    # `closed_door` sitting symmetric on both sides of the edge.
    barrier_only = {"rooms": {"terminus": {
        "adjacent": [{"to": "riser21", "barrier": "closed_door",
                      "dir": "n"}]}}}
    onset = {"rooms": {"terminus": {
        "name": "Terminus 20",
        "anchors": {"fire_door": {"desc": "a rated steel fire door"}}}}}
    assert _evidence_present(
        barrier_only, {"subject": "fire_door", "category": "adjacency",
                       "change": "pulled shut and dogged down"}, scene=onset)

    # The `adjacent` conjunct still carries the weight: the scene naming the
    # doorway acquits nothing on its own.
    assert not _evidence_present(
        {"rooms": {"terminus": {"name": "Terminus 20"}}},
        {"subject": "fire_door", "category": "adjacency",
         "change": "pulled shut and dogged down"}, scene=onset)

    # And with no scene the reader degrades to its old answer, never a
    # wrong one -- the contract `_evidence_present`'s docstring states.
    assert not _evidence_present(
        barrier_only, {"subject": "fire_door", "category": "adjacency",
                       "change": "pulled shut and dogged down"})

