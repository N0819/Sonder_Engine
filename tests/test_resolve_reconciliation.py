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
"""

from __future__ import annotations

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData
from spatial import merge_scene_with_diff, spatial_rel

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
    step keys invoked (director_resolve, resolve_reconcile, resolve_repair)."""
    def fake(role, step_key, system, payload, **kw):
        calls.append((step_key, payload))
        result = outputs.get(step_key, {})
        return json.loads(json.dumps(result))
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

def test_elevator_omission_is_repaired(temp_db, monkeypatch):
    """Prose says sealed + descending; diff has a blank room placeholder.
    Detection is fully deterministic (structural signal + manifest gap --
    NO audit call); the Director's own repair delta must leave the final
    diff with the doors actually closed."""
    ctx = _make_ctx(temp_db, "I slam the door-close button.",
                    _action_interp())
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": ELEVATOR_RESOLVE_OUTPUT,
        "resolve_repair": ELEVATOR_REPAIR_OUTPUT,
    }, calls))

    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]

    # Manifest fold: no standalone audit call; exactly one bounded repair.
    step_keys = [k for k, _ in calls]
    assert "resolve_reconcile" not in step_keys
    assert step_keys.count("resolve_repair") == 1

    # The blank placeholder was caught deterministically and flagged, and
    # the manifest item registered as an omission.
    recon = out["reconciliation"]
    assert any(s["source"] == "structural"
               and s["subject"] == "elevator_interior"
               for s in recon["signals"])
    assert any(o["source"] == "manifest"
               and o["subject"] == "elevator_interior"
               for o in recon["omissions"])
    assert recon["repaired"] is True

    # The repaired diff actually closes the doors...
    room = sd["rooms"]["elevator_interior"]
    assert room["desc"]  # no longer a blank placeholder
    edges = {e["to"]: e["barrier"] for e in room["adjacent"]}
    assert edges["smoke_hallway"] == "closed_door"
    # ...and carries the descent as a persistent condition.
    assert "elevator_descending" in sd["conditions"]
    # The original diff's own substantive entry survived the merge.
    assert sd["entities"]["elevator_control_panel"]["state"][
        "descent_initiated"] is True

    # Everything encoded -> no reconciliation warnings.
    assert not [w for w in ctx.warnings if "reconciliation" in w.casefold()]

    # And the change is what PERCEPTION will actually see: merging the final
    # diff over the prior scene closes the doorway objective truth kept open.
    merged = merge_scene_with_diff(json.loads(json.dumps(ELEVATOR_SCENE)), sd)
    rel = spatial_rel(merged, "elevator_interior", "smoke_hallway")
    assert rel["barrier"] == "closed_door"


def test_elevator_omission_is_flagged_when_repair_fails(temp_db, monkeypatch):
    """If the self-repair returns nothing usable, the seam must not invent
    state: the blank placeholder is still stripped (deterministic floor) and
    the unencoded manifest change surfaces as a warning."""
    ctx = _make_ctx(temp_db, "I slam the door-close button.",
                    _action_interp())
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": ELEVATOR_RESOLVE_OUTPUT,
        "resolve_repair": {},  # repair came back empty
    }, calls))

    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]

    # Deterministic floor held: the noise entry cannot commit as "handled".
    assert "elevator_interior" not in sd["rooms"]
    # The divergence is flagged, never silently papered over.
    assert any("Resolve reconciliation" in w for w in ctx.warnings)
    unresolved_subjects = {o["subject"]
                          for o in out["reconciliation"]["unresolved"]}
    assert "elevator_interior" in unresolved_subjects


# ---- no false positives / no cost on the common case ----

def test_pure_dialogue_turn_triggers_nothing(temp_db, monkeypatch):
    """A speech-only beat with an empty diff and empty manifest must spend
    zero extra LLM calls and produce no warnings."""
    ctx = _make_ctx(temp_db, '"How are you holding up?"', _dialogue_interp())
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": {
            "resolved_event": "The Stranger asks Mara how she is holding up.",
            "summary": "A quiet exchange.",
            "dialogue_log": [],
            "changes_asserted": [],
            "state_diff": {},
        },
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    step_keys = [k for k, _ in calls]
    assert step_keys == ["director_resolve"]
    assert out["reconciliation"]["audited"] is False
    assert out["reconciliation"]["signals"] == []
    assert out["reconciliation"]["tripwire"] is False
    assert not ctx.warnings


def test_manifest_covered_beat_costs_zero_extra_calls(temp_db, monkeypatch):
    """The manifest fold's whole point: a well-encoded action beat -- the
    manifest names the change AND the diff encodes it -- reconciles fully
    deterministically, with NO audit and NO repair call."""
    interp = _action_interp()
    ctx = _make_ctx(temp_db, "I close the elevator doors.", interp)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": {
            "resolved_event": ELEVATOR_PROSE,
            "summary": "Doors sealed.",
            "dialogue_log": [],
            "changes_asserted": [
                {"category": "adjacency", "subject": "elevator_interior",
                 "change": "The elevator doors are sealed shut."},
            ],
            "state_diff": ELEVATOR_REPAIR_OUTPUT["state_diff"],
        },
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    step_keys = [k for k, _ in calls]
    assert step_keys == ["director_resolve"]
    assert out["reconciliation"]["audited"] is False
    assert out["reconciliation"]["omissions"] == []
    assert not ctx.warnings


# ---- category-aware evidence classes ----

def test_partial_encoding_is_caught_by_adjacency_evidence_class(
    temp_db, monkeypatch,
):
    """The partial-encoding trap: the diff updates the room's DESC (subject
    present -- bare containment would pass) but the manifested ADJACENCY
    change is nowhere. The category-aware check must still fire the repair."""
    ctx = _make_ctx(temp_db, "I slam the door-close button.",
                    _action_interp())
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": {
            "resolved_event": ELEVATOR_PROSE,
            "summary": "Doors sealed.",
            "dialogue_log": [],
            "changes_asserted": [
                {"category": "adjacency", "subject": "elevator_interior",
                 "change": "The elevator doors are sealed shut."},
            ],
            "state_diff": {
                # desc-only redeclaration: no adjacent, no remove_adjacent,
                # no transit state -- the narrated sealing is NOT encoded.
                "rooms": {"elevator_interior": {
                    "name": "Service Elevator",
                    "desc": "The doors gleam dully.", "adjacent": [],
                    "notes": ""}},
            },
        },
        "resolve_repair": ELEVATOR_REPAIR_OUTPUT,
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    assert [k for k, _ in calls].count("resolve_repair") == 1
    edges = {e["to"]: e["barrier"]
             for e in out["state_diff"]["rooms"]["elevator_interior"]["adjacent"]}
    assert edges["smoke_hallway"] == "closed_door"


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

def test_omitted_player_claim_fires_repair_and_hard_warns(
    temp_db, monkeypatch,
):
    """An asserted scope='effect' claim whose subject is nowhere in the diff
    is a hard omission: it fires the repair, and if still unencoded it
    ALWAYS warns -- dispositions cannot argue it away."""
    claims = [{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": "vault_door", "predicate": "shattered",
        "value": {}, "commitment": "asserted",
        "source_text": "I shatter the vault door",
    }]
    ctx = _make_ctx(temp_db, "I shatter the vault door.",
                    _action_interp(authority_claims=claims))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": {
            "resolved_event": "The vault door shatters into fragments.",
            "summary": "Vault door destroyed.",
            "dialogue_log": [], "changes_asserted": [],
            "state_diff": {},
        },
        # Repair even tries to reject it -- non-rejectable for player claims.
        "resolve_repair": {"state_diff": {}, "dispositions": [
            {"subject": "vault_door", "status": "rejected",
             "reason": "seems transient"}]},
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    assert [k for k, _ in calls].count("resolve_repair") == 1
    assert any("PLAYER AUTHORITY" in w for w in ctx.warnings)
    assert any(o["source"] == "player_claim"
               for o in out["reconciliation"]["unresolved"])


def test_encoded_player_claim_is_silent(temp_db, monkeypatch):
    claims = [{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": "vault_door", "predicate": "shattered",
        "value": {}, "commitment": "asserted",
        "source_text": "I shatter the vault door",
    }]
    ctx = _make_ctx(temp_db, "I shatter the vault door.",
                    _action_interp(authority_claims=claims))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": {
            "resolved_event": "The vault door shatters into fragments.",
            "summary": "Vault door destroyed.",
            "dialogue_log": [], "changes_asserted": [],
            "state_diff": {"remove_entities": ["vault_door"]},
        },
    }, calls))

    director.director_resolve(ctx, nonce=0)

    assert [k for k, _ in calls] == ["director_resolve"]
    assert not ctx.warnings


def test_null_subject_claim_degrades_to_metadata_note(temp_db, monkeypatch):
    """A claim with no resolvable subject cannot be containment-checked;
    it becomes a metadata note, never a warning or a repair trigger."""
    claims = [{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": None, "predicate": "everything feels colder",
        "value": {}, "commitment": "asserted", "source_text": "it gets cold",
    }]
    ctx = _make_ctx(temp_db, "It gets cold.",
                    _action_interp(authority_claims=claims))
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": {
            "resolved_event": "A chill settles over the room.",
            "summary": "Cold.", "dialogue_log": [],
            "changes_asserted": [], "state_diff": {},
        },
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    assert [k for k, _ in calls] == ["director_resolve"]
    assert out["reconciliation"]["claim_notes"]
    assert not ctx.warnings


def test_rejected_asserted_claim_is_a_contract_violation(temp_db, monkeypatch):
    """claim_dispositions cross-check: an asserted claim marked 'rejected'
    violates the player authority contract and warns deterministically,
    even when the effect itself IS encoded."""
    claims = [{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": "vault_door", "predicate": "shattered",
        "value": {}, "commitment": "asserted",
        "source_text": "I shatter the vault door",
    }]
    ctx = _make_ctx(temp_db, "I shatter the vault door.",
                    _action_interp(authority_claims=claims))
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": {
            "resolved_event": "The vault door shatters.",
            "summary": "Vault door destroyed.",
            "dialogue_log": [], "changes_asserted": [],
            "state_diff": {"remove_entities": ["vault_door"]},
            "claim_dispositions": [
                {"claim_id": "claim:0:effect:0", "status": "rejected"}],
        },
    }, []))

    director.director_resolve(ctx, nonce=0)

    assert any("PLAYER AUTHORITY" in w and "rejected" in w
               for w in ctx.warnings)


# ---- the folded-in restraint detector ----

def test_restraint_omission_repaired_through_seam(temp_db, monkeypatch):
    """The legacy restraint scan feeds the same seam: a narrated gunpoint
    hold with no condition triggers the repair (deterministically -- no
    audit call), and an encoded condition silences the legacy warning."""
    ctx = _make_ctx(temp_db, "I keep talking.", _dialogue_interp())
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": {
            "resolved_event": "The guard keeps Mara pinned at gunpoint "
                              "against the wall.",
            "summary": "Standoff.",
            "dialogue_log": [], "changes_asserted": [],
            "state_diff": {},
        },
        "resolve_repair": {
            "state_diff": {"conditions": {"mara_restrained": [{
                "condition_id": "mara_restrained", "subject_id": "Mara",
                "kind": "restrained", "severity": 0.6,
                "started_at_seconds": 0.0, "state": {},
            }]}},
            "dispositions": [{"subject": "Mara", "status": "encoded",
                              "reason": ""}],
        },
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    step_keys = [k for k, _ in calls]
    assert "resolve_reconcile" not in step_keys
    assert "resolve_repair" in step_keys
    assert "mara_restrained" in out["state_diff"]["conditions"]
    assert not any("untracked physical restraint" in w for w in ctx.warnings)


def test_restraint_warning_survives_failed_repair(temp_db, monkeypatch):
    """When the repair cannot encode the restraint, the exact legacy
    warn-only behavior remains as the floor."""
    ctx = _make_ctx(temp_db, "I keep talking.", _dialogue_interp())
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": {
            "resolved_event": "The guard keeps Mara pinned at gunpoint "
                              "against the wall.",
            "summary": "Standoff.",
            "dialogue_log": [], "changes_asserted": [],
            "state_diff": {},
        },
        "resolve_repair": {},
    }, []))

    director.director_resolve(ctx, nonce=0)

    assert any("untracked physical restraint" in w for w in ctx.warnings)


# ---- silent-false-negative tripwire + deep-audit escalation ----

def test_tripwire_flags_eventful_beat_with_empty_manifest(
    temp_db, monkeypatch,
):
    """Successful dice + empty manifest + empty physical diff = the beat
    provably did something the model reported nowhere. Metadata flag only
    (deep audit is default-off) -- no calls, no warnings."""
    interp = _action_interp()
    interp["flow"]["dice"] = [{"actor": "The Stranger",
                               "attempt": "force the hatch",
                               "ability": "might", "difficulty": "easy"}]
    ctx = _make_ctx(temp_db, "I force the hatch.", interp)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": {
            "resolved_event": "With a grunt, something gives way.",
            "summary": "Effort.", "dialogue_log": [],
            "changes_asserted": [], "state_diff": {},
        },
    }, calls))
    # Make the seeded roll a guaranteed success.
    monkeypatch.setattr(director, "_ability_mod", lambda *a, **k: 30)

    out = director.director_resolve(ctx, nonce=0)

    assert [k for k, _ in calls] == ["director_resolve"]
    assert out["reconciliation"]["tripwire"] is True
    assert not ctx.warnings


def test_tripwire_escalates_to_deep_audit_when_opted_in(
    temp_db, monkeypatch,
):
    """resolve_deep_audit='tripwire' wires the retained standalone audit to
    the tripwire; its findings flow into the normal repair path."""
    from db import set_setting
    set_setting("resolve_deep_audit", "tripwire")
    try:
        interp = _action_interp()
        interp["flow"]["dice"] = [{"actor": "The Stranger",
                                   "attempt": "force the hatch",
                                   "ability": "might", "difficulty": "easy"}]
        ctx = _make_ctx(temp_db, "I force the hatch.", interp)
        calls = []
        monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
            "director_resolve": {
                "resolved_event": "The hatch tears free of its hinges.",
                "summary": "Hatch forced.", "dialogue_log": [],
                "changes_asserted": [], "state_diff": {},
            },
            "resolve_reconcile": {"omissions": [{
                "category": "entities", "subject": "hatch",
                "change": "The hatch is torn from its hinges.",
                "evidence": "tears free of its hinges", "confidence": 0.9,
            }], "notes": ""},
            "resolve_repair": {"state_diff": {
                "entities": {"hatch": {"name": "Torn Hatch", "kind": "object",
                                       "state": {"broken": True}}}},
                "dispositions": [{"subject": "hatch", "status": "encoded",
                                  "reason": ""}]},
        }, calls))
        monkeypatch.setattr(director, "_ability_mod", lambda *a, **k: 30)

        out = director.director_resolve(ctx, nonce=0)

        step_keys = [k for k, _ in calls]
        assert "resolve_reconcile" in step_keys
        assert "resolve_repair" in step_keys
        assert out["reconciliation"]["audited"] is True
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
