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

from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData
from world.spatial import contact_sensation, merge_scene_with_diff, spatial_rel

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


def _specialist_stubs(repair_output):
    """The same repair delta, re-addressed to each channel's OWNER.

    The core repair emits ``{"state_diff": {channel: ...}}``; a specialist
    emits its own channels at the top level. Omissions now route to the owning
    specialist before anything reaches the core `resolve_repair` call, so a
    fixture supplying only the core shape leaves the repair with nothing to
    apply and the seam reports `repaired: False`.

    Derived from `SPECIALISTS` rather than hardcoded, so a channel that
    changes owner does not quietly stop being covered here.
    """
    from agents.director import SPECIALISTS
    sd = (repair_output or {}).get("state_diff") or {}
    stubs = {}
    for spec in SPECIALISTS.values():
        patch = {ch: sd[ch] for ch in spec["channels"] if ch in sd}
        if patch:
            stubs[spec["step_key"]] = patch
    return stubs



def _owned_channels(resolve_output, *, omit=(), repair=None, verdicts=None):
    """Per-specialist canned outputs derived from a resolve fixture.

    A specialist's answer OWNS its granted channels: whatever the prose
    author emitted there is replaced by what the owner said, so a fixture
    that puts the whole beat in the resolve output has those channels
    replaced with nothing. Each owner has to emit its own share.

    `repair` is the MEND -- the channels a repair pass would add. By default
    an owner emits base and mend together on dispatch, which is a beat
    encoded correctly the first time. `omit` names the step keys that
    withhold the mend on dispatch and supply it on their SECOND call
    instead; that is how a test makes an omission actually happen, because a
    specialist's dispatch and its repair share one step key and the two
    answers have to be sequenced rather than named.

    `verdicts` maps a step key to the `resolved_events` echo that owner
    returns on its repair call -- the fan-out's analogue of the core
    repair's `dispositions`.
    """
    base = _specialist_stubs(resolve_output)
    mend = _specialist_stubs(repair) if repair else {}
    said = dict(verdicts or {})
    out = {}
    for key in list(base) + [k for k in mend if k not in base]:
        first, second = base.get(key, {}), mend.get(key)
        echo = {"resolved_events": said[key]} if key in said else {}
        if second is None and not echo:
            out[key] = first
        elif key in omit:
            out[key] = [first, {**(second or {}), **echo}]
        else:
            out[key] = {**first, **(second or {}), **echo}
    return out


def _core(calls):
    """Call step keys with the specialist fan-out filtered out.

    These tests assert that a beat spends no EXTRA calls -- no repair, no
    audit. They were written when the monolithic Director was the default and
    "extra" and "any call beyond the resolve" meant the same thing. The
    fan-out is now the only path, so a specialist call is baseline rather than
    extra, and the assertions are about what they were always about: whether
    the beat had to be resolved twice.
    """
    from agents.director import SPECIALISTS
    return [k for k in calls if k == "director_resolve"
            or not any(k == "director_%s" % name for name in SPECIALISTS)]



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


def test_live_two_contact_omission_fires_bounded_repair(temp_db, monkeypatch):
    """End-to-end reproduction of chat 68 turn 15. The hand relation remains,
    and the separately asserted interior relation is added by the one repair
    call instead of being hidden by their shared actor."""
    ctx = _make_ctx(temp_db, "I squirm at the depth.", _action_interp())
    calls = []
    resolved = {
        "resolved_event": (
            "Elyra's left hand tightens on Hinami's hip as her cock "
            "presses deeper against Hinami's cervix."
        ),
        "summary": "Both contacts deepen.",
        "dialogue_log": [],
        "changes_asserted": [
            {"category": "contact_ops", "subject": "Elyra Voss",
             "change": "Left hand tightens grip on Hinami's hip."},
            {"category": "contact_ops", "subject": "Elyra Voss",
             "change": "Cock presses deeper against Hinami's cervix."},
        ],
        "state_diff": {"contact_ops": [{
            "op": "add", "actor": "Elyra Voss",
            "actor_part": "left hand", "target": "Hinami",
            "target_part": "hip", "manner": "hold",
            "detail": "firm grip",
        }]},
    }
    mend = {
        "state_diff": {"contact_ops": [{
            "op": "add", "actor": "Elyra Voss", "actor_part": "cock",
            "target": "Hinami", "target_interior": "vaginal canal",
            "target_part": "cervix",
            "manner": "insert", "detail": "fully inserted",
        }]},
        "dispositions": [{"subject": "Elyra Voss", "status": "encoded",
                          "reason": "Added the omitted relation."}],
    }
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": resolved,
        "resolve_repair": mend,
        # `contact_ops` is the contact specialist's channel, so it is the
        # hand that encodes the hip relation and the hand asked again for
        # the interior one -- one scoped call, not a second full resolve.
        **_owned_channels(resolved, omit={"director_contact"}, repair=mend),
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    step_keys = [key for key, _ in calls]
    assert _core(step_keys) == ["director_resolve"]
    assert step_keys.count("director_contact") == 2
    assert {(op["actor_part"], op["target_part"])
            for op in out["state_diff"]["contact_ops"]} == {
                ("left hand", "hip"), ("cock", "cervix")}
    assert out["reconciliation"]["repaired"] is True
    assert out["reconciliation"]["unresolved"] == []

    scene = merge_scene_with_diff({
        "rooms": {"room": {"name": "Room", "desc": "", "adjacent": []}},
        "positions": {"Elyra Voss": "room", "Hinami": "room"},
        "entities": {}, "contacts": [],
    }, out["state_diff"])
    interior = next(c for c in scene["contacts"]
                    if c["target_part"] == "cervix")
    assert contact_sensation(interior, you="Hinami", scene=scene).startswith(
        "your body registers Elyra Voss's cock within your vaginal canal, "
        "with contact at your cervix")
    assert contact_sensation(interior, you="Elyra Voss", scene=scene).startswith(
        "your cock registers Hinami's vaginal canal enclosing it, with "
        "contact at Hinami's cervix")


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
    step keys invoked (director_resolve, resolve_reconcile, resolve_repair).

    A LIST value is consumed one entry per call, which the fan-out made
    necessary: a specialist's ordinary dispatch and its repair share one step
    key, so a single canned output cannot say "omitted it, then mended it" --
    handing the patch to the dispatch call encodes the change up front and
    the omission under test never happens. The last entry repeats once the
    list runs out.
    """
    pending = {k: list(v) for k, v in outputs.items() if isinstance(v, list)}

    def fake(role, step_key, system, payload, **kw):
        calls.append((step_key, payload))
        if step_key in pending:
            queue = pending[step_key]
            result = queue.pop(0) if len(queue) > 1 else (queue[0] if queue else {})
        else:
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
        # The prose author owns none of these channels, so whatever the
        # resolve fixture puts in them is replaced by what the OWNER said --
        # each owner has to emit its own share. `spatial` emits the blank
        # room placeholder the live Director emitted and withholds the mend
        # until its repair call, which is the omission under test; `body`
        # carries the descent condition, which is its channel and was never
        # the omitted thing.
        **_owned_channels(ELEVATOR_RESOLVE_OUTPUT,
                          omit={"director_spatial"},
                          repair=ELEVATOR_REPAIR_OUTPUT),
    }, calls))

    out = director.director_resolve(ctx, nonce=0)
    sd = out["state_diff"]

    # Manifest fold: no standalone audit call; exactly one bounded repair.
    step_keys = [k for k, _ in calls]
    assert "resolve_reconcile" not in step_keys
    # ONE bounded repair, by whichever tier owns the omitted channel. The
    # spatial specialist appears twice -- once for its ordinary dispatch and
    # once to repair `rooms` -- so the bound is on the REPAIR, which is what
    # "bounded" was always about: the beat is resolved once and mended once,
    # never resolved twice. Mending at the owner is also the cheap shape: a
    # ~1-4k specialist sheet instead of the full core.
    assert out["reconciliation"]["repaired"] is True
    assert step_keys.count("director_spatial") == 2
    assert step_keys.count("resolve_repair") == 0, (
        "an omission the spatial specialist owns must not also re-run the "
        "full-core prose author")

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
        # Same owners as the repaired case, but nobody mends: the spatial
        # specialist emits the blank placeholder and its repair call answers
        # with nothing.
        **_owned_channels(ELEVATOR_RESOLVE_OUTPUT),
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

    step_keys = _core([k for k, _ in calls])
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
    covered = {
        "resolved_event": ELEVATOR_PROSE,
        "summary": "Doors sealed.",
        "dialogue_log": [],
        "changes_asserted": [
            {"category": "adjacency", "subject": "elevator_interior",
             "change": "The elevator doors are sealed shut."},
        ],
        "state_diff": ELEVATOR_REPAIR_OUTPUT["state_diff"],
    }
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": covered,
        # Encoded by the channel's OWNER, which is where the encoding lives
        # on this path -- the assertion is that a beat encoded correctly the
        # first time buys no second pass over it.
        **_owned_channels(covered),
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    step_keys = [k for k, _ in calls]
    assert _core(step_keys) == ["director_resolve"]
    # ...and no owner was asked twice either: a repair pass is a repair pass
    # whoever pays for it.
    assert len(step_keys) == len(set(step_keys))
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
    partial = {
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
    }
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": partial,
        "resolve_repair": ELEVATOR_REPAIR_OUTPUT,
        # The desc-only entry is the SPATIAL specialist's, and so is the
        # mend: subject-present-but-wrong-dimension has to survive routing
        # to the owner, or the category classes never get consulted at all.
        **_owned_channels(partial, omit={"director_spatial"},
                          repair=ELEVATOR_REPAIR_OUTPUT),
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    step_keys = [k for k, _ in calls]
    assert step_keys.count("director_spatial") == 2
    assert step_keys.count("resolve_repair") == 0
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
    encoded = {
        "resolved_event": "The vault door shatters into fragments.",
        "summary": "Vault door destroyed.",
        "dialogue_log": [], "changes_asserted": [],
        "state_diff": {"remove_entities": ["vault_door"]},
    }
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": encoded,
        # `remove_entities` belongs to the objects specialist; the claim's
        # coverage check reads the MERGED diff, so the claim is covered by
        # whichever hand encoded it.
        **_owned_channels(encoded),
    }, calls))

    director.director_resolve(ctx, nonce=0)

    assert _core([k for k, _ in calls]) == ["director_resolve"]
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

    assert _core([k for k, _ in calls]) == ["director_resolve"]
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
    standoff = {
        "resolved_event": "The guard keeps Mara pinned at gunpoint "
                          "against the wall.",
        "summary": "Standoff.",
        "dialogue_log": [], "changes_asserted": [],
        "state_diff": {},
    }
    mend = {
        "state_diff": {"conditions": {"mara_restrained": [{
            "condition_id": "mara_restrained", "subject_id": "Mara",
            "kind": "restrained", "severity": 0.6,
            "started_at_seconds": 0.0, "state": {},
        }]}},
        "dispositions": [{"subject": "Mara", "status": "encoded",
                          "reason": ""}],
    }
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": standoff,
        "resolve_repair": mend,
        # The scan files the finding under `conditions`, which the BODY
        # specialist owns -- so the legacy detector's repair is a scoped
        # body call, not a second full resolve.
        **_owned_channels(standoff, repair=mend),
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    step_keys = [k for k, _ in calls]
    assert "resolve_reconcile" not in step_keys
    assert _core(step_keys) == ["director_resolve"]
    # A channel GATED OUT of the fan-out is still repairable by its owner.
    # The gates read standing state and this beat is pure dialogue, so body
    # never ran; the restraint scan reads PROSE, so it finds the hold
    # anyway and the repair reaches the hand that owns `conditions`.
    assert out["orchestration"]["specialists"]["body"]["run"] is False
    assert step_keys.count("director_body") == 1
    assert out["reconciliation"]["specialist_repairs"]["body"]["ok"] is True
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

    assert _core([k for k, _ in calls]) == ["director_resolve"]
    assert out["reconciliation"]["tripwire"] is True
    assert not ctx.warnings


def test_tripwire_escalates_to_deep_audit_when_opted_in(
    temp_db, monkeypatch,
):
    """resolve_deep_audit='tripwire' wires the retained standalone audit to
    the tripwire; its findings flow into the normal repair path."""
    from core.db import set_setting
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
            # The audit's finding is an `entities` omission, which the
            # objects specialist owns -- an audit finding routes to a
            # repairer by exactly the same rule a manifest one does. Objects
            # emits NOTHING on dispatch (an empty physical diff is half of
            # what arms the tripwire) and encodes the hatch when asked again.
            "director_objects": [{}, {
                "entities": {"hatch": {"name": "Torn Hatch", "kind": "object",
                                       "state": {"broken": True}}}}],
        }, calls))
        monkeypatch.setattr(director, "_ability_mod", lambda *a, **k: 30)

        out = director.director_resolve(ctx, nonce=0)

        step_keys = [k for k, _ in calls]
        assert "resolve_reconcile" in step_keys
        assert _core(step_keys) == ["director_resolve", "resolve_reconcile"]
        assert out["reconciliation"]["specialist_repairs"]["objects"]["ok"] \
            is True
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


def test_owner_verdict_on_a_repair_call_is_believed(temp_db, monkeypatch):
    """v26625, carried onto the path that now owns the repair.

    Original defect: the core repair answered every omission
    'already_encoded' and the staleness warning shipped anyway, because
    dispositions were matched to omissions by EXACT normalized subject
    against a repair that writes descriptive ones ('lightweight travel
    jacket — fully removed from shoulder, falls onto velvet'). The verdict
    existed and was discarded.

    An omission in a delegated channel no longer reaches the core repair at
    all -- its OWNER is asked -- so the hole reopens in a new place unless
    the owner's echo is read back off the repair call. It answers by
    event_id rather than by subject text, which is the mechanism that made
    the original mismatch impossible rather than merely tolerant."""
    ctx = _make_ctx(temp_db, "I slam the door-close button.",
                    _action_interp())
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": ELEVATOR_RESOLVE_OUTPUT,
        # Spatial emits the placeholder, is asked again for `rooms`, and
        # answers that standing state already carries the sealing rather
        # than emitting a delta.
        **_owned_channels(
            ELEVATOR_RESOLVE_OUTPUT,
            omit={"director_spatial"},
            repair={"state_diff": {}},
            verdicts={"director_spatial": [
                {"event_id": 1, "status": "already_true"}]}),
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    # The owner's verdict is believed for the MANIFEST omission: recorded
    # on the unresolved entry, and no staleness warning ships against it.
    entry = next(o for o in out["reconciliation"]["unresolved"]
                 if o["subject"] == "elevator_interior"
                 and o.get("source") == "manifest")
    assert entry["disposition"] == "already_encoded"
    assert not [w for w in ctx.warnings
                if "still does not encode" in w and "sealed shut" in w]
    # The STRUCTURAL signal (a blank placeholder was emitted) still warns:
    # that is a deterministic finding, and a model's verdict does not
    # overrule the deterministic layer -- only emergent detections
    # (manifest/audit, model-vs-model) yield to a rejection.
    assert [w for w in ctx.warnings
            if "still does not encode" in w and "empty placeholder" in w]


def test_a_repair_verdict_cannot_acquit_an_event_it_was_not_handed(
        temp_db, monkeypatch):
    """The same filter the dispatch echo carries: a repairer that echoes an
    id outside the omissions it was given acquits nothing. Without it, one
    owner answering `already_true` for the whole manifest would silence
    every sibling's omission in the beat -- the acquittal has to be
    ownership-scoped or it is a way for a model to switch the seam off."""
    ctx = _make_ctx(temp_db, "I slam the door-close button.",
                    _action_interp())
    calls = []
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": ELEVATOR_RESOLVE_OUTPUT,
        **_owned_channels(
            ELEVATOR_RESOLVE_OUTPUT,
            omit={"director_spatial"},
            repair={"state_diff": {}},
            # Event 99 is nobody's; event 1 is the one actually routed here,
            # and it is deliberately NOT answered.
            verdicts={"director_spatial": [
                {"event_id": 99, "status": "already_true"}]}),
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    entry = next(o for o in out["reconciliation"]["unresolved"]
                 if o["subject"] == "elevator_interior"
                 and o.get("source") == "manifest")
    assert entry["disposition"] == "none"
    assert [w for w in ctx.warnings
            if "still does not encode" in w and "sealed shut" in w]


def test_disposition_subjects_match_with_the_same_tolerance_as_evidence(
        temp_db, monkeypatch):
    """The core repair still owns every omission no specialist can answer --
    player claims and undelegated categories -- and its dispositions are
    still matched by subject TEXT, so v26625's own tolerance still has to
    hold there. `transit` reaches no delegated channel, so it routes to the
    core exactly as it always did."""
    ctx = _make_ctx(temp_db, "I slam the door-close button.",
                    _action_interp())
    calls = []
    resolved = {
        **ELEVATOR_RESOLVE_OUTPUT,
        "changes_asserted": [
            {"category": "transit", "subject": "elevator_interior",
             "change": "The elevator is now in transit between floors."},
        ],
    }
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": resolved,
        "resolve_repair": {
            "state_diff": {},
            "dispositions": [{
                "subject": "elevator_interior — now in transit between "
                           "floors, doors sealed",
                "status": "already_encoded",
                "reason": "the panel state already carries it"}],
        },
        **_owned_channels(resolved),
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    assert [k for k, _ in calls].count("resolve_repair") == 1
    entry = next(o for o in out["reconciliation"]["unresolved"]
                 if o["subject"] == "elevator_interior"
                 and o.get("source") == "manifest")
    assert entry["disposition"] == "already_encoded"
    assert not [w for w in ctx.warnings
                if "still does not encode" in w and "in transit" in w]


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


def test_an_unreferrable_claim_subject_degrades_to_a_note(temp_db,
                                                          monkeypatch):
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
    """
    ctx = _make_ctx(
        temp_db,
        "I ring the bell. (it is a hotel, someone should be staffing it)",
        _meta_claim_interp("I ring the bell."))
    calls = []
    resolved = {
        "resolved_event": "The bell rings out across the empty lobby.",
        "summary": "Bell rung.", "dialogue_log": [],
        "changes_asserted": [], "state_diff": {},
    }
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": resolved, **_owned_channels(resolved),
    }, calls))

    out = director.director_resolve(ctx, nonce=0)

    assert "resolve_repair" not in [k for k, _ in calls], (
        "an unreferrable claim bought a full-core repair call")
    assert not [w for w in ctx.warnings if "PLAYER AUTHORITY" in w]
    assert any(n.get("predicate") ==
               "even at late hour someone should be staffing it"
               for n in out["reconciliation"]["claim_notes"])


def test_a_claim_the_player_named_in_their_own_words_stays_hard(
        temp_db, monkeypatch):
    """The case that must NOT soften. `vault_door` is in no scene here --
    the player is asserting it into existence, which is exactly what player
    authority is for -- but they typed the words, so the subject has a
    referent and the coverage check is real."""
    claims = [{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": "vault_door", "predicate": "shattered",
        "value": {}, "commitment": "asserted",
        "source_text": "I shatter the vault door",
    }]
    ctx = _make_ctx(temp_db, "I shatter the vault door.",
                    _action_interp(authority_claims=claims))
    calls = []
    resolved = {
        "resolved_event": "The vault door shatters into fragments.",
        "summary": "Vault door destroyed.", "dialogue_log": [],
        "changes_asserted": [], "state_diff": {},
    }
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": resolved,
        "resolve_repair": {"state_diff": {}, "dispositions": []},
        **_owned_channels(resolved),
    }, calls))

    director.director_resolve(ctx, nonce=0)

    assert [k for k, _ in calls].count("resolve_repair") == 1
    assert any("PLAYER AUTHORITY" in w for w in ctx.warnings)


def test_a_claim_on_a_standing_scene_subject_stays_hard(temp_db, monkeypatch):
    """The other case that must not soften: the player says "I snuff the
    lamp" and the claim's subject is the scene's own `elevator_control_panel`
    id, which they never typed. Resolvable in the WORLD is enough on its
    own -- either channel qualifies, and only failing both is unreferrable.
    """
    claims = [{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": "elevator_control_panel", "predicate": "smashed",
        "value": {}, "commitment": "asserted",
        "source_text": "I smash the panel",
    }]
    ctx = _make_ctx(temp_db, "I smash the panel.",
                    _action_interp(authority_claims=claims))
    calls = []
    resolved = {
        "resolved_event": "The panel cracks under the blow.",
        "summary": "Panel smashed.", "dialogue_log": [],
        "changes_asserted": [], "state_diff": {},
    }
    monkeypatch.setattr(director, "_agent_json", _dispatching_agent_json({
        "director_resolve": resolved,
        "resolve_repair": {"state_diff": {}, "dispositions": []},
        **_owned_channels(resolved),
    }, calls))

    director.director_resolve(ctx, nonce=0)

    assert any("PLAYER AUTHORITY" in w for w in ctx.warnings)
