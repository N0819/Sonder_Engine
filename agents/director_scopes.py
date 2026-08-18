"""The Director's specialist registry, channel ownership, work gates and dispatch.

INVARIANT -- sole writer: this module is the only writer of `SPECIALISTS`,
`_CHANNEL_GATES` and `_CHANNEL_SPECIALISTS`. `register_specialist`,
`unregister_specialists`, `_rebuild_channel_owners` and
`_default_channel_gate` stay with the registries they mutate, even though
the first two are the extension seam: lifting them elsewhere would make
two modules co-writers of all three dicts, and a partial registration is
a KeyError inside the Director on every beat.

Also here: the prose-duty shipped-anyway table (`_PROSE_DUTY_SHIPPED`),
the per-stage gate facts (`_gate_facts`) and dispatch
(`_dispatch_specialists`). The prose-duty GATES themselves
(`_PROSE_DUTY_GATES`, `_prose_gate_facts`, `_prose_author_scope`) stay in
`agents/director.py` with the stage bodies.

Import direction: nothing outside `agents/director*.py` may import an
`agents/director_*` submodule, and no `director_*` module may import
`agents.director` (that is the cycle the facade exists to prevent).
"""

from typing import get_origin

from core.db import q
from world.survival import survival_enabled

from .director_views import (
    _artifacts_view,
    _carried_reports_view,
    _couriers_view,
    _crowds_view,
    _unratified_background_claims,
)

# ---------------------------------------------------------------------------
# Director orchestration (design note 19, `docs/UNBUILT.md` §2.18).
#
# The resolve stage stays ONE pipeline step -- one steps/variants row, the
# same step key, nothing new in agents/runtime.py -- and fans out INSIDE
# itself, on every beat: a deterministic
# dispatch decides which scoped specialists this beat needs, one prose author
# owns resolved_event (with the delegated instruction blocks cold-stored out
# of its sheet), each dispatched specialist reads the finished prose and owns
# its state_diff channels, and deterministic assembly merges the channels
# back before the existing cross-channel seams (movement backstop,
# reconciliation, restraint floor) run on the merged diff exactly as they do
# on an unsplit one. There is no unsplit path any more: it shipped behind
# a flag while the two were measured against each other, the fan-out won on
# stability, tokens and wall clock, and keeping the loser would only have
# preserved a way to make the engine worse. What remains a choice is
# CONCURRENCY -- see `fanout_is_parallel`.
#
# THE GATE FAILS OPEN AND KEYS ON SCENE STATE, never on the beat's prose --
# prose matching as a boundary is the silent-drop surface `docs/UNBUILT.md`
# §3.1 refuses. Where structure cannot decide, the specialist runs: a scoped
# specialist costs little to run needlessly, and that asymmetry is what makes
# a generous gate affordable. A wrongly-skipped specialist is never silent:
# `_orchestration_gate_backstop` is `changes_asserted` reconciliation pointed
# at the GATE, and reports the misprediction through `tell_director`.
#
# Dispatch is decided at THIS stage's time, from what is true then. Nothing
# here assumes a plan fixed at the top of the turn: when `director_interpret`
# grows its own specialists it will call its own dispatch against the state
# it sees, because characters declare between the two stages and bring
# channels into play nothing at interpret time could predict.
# ---------------------------------------------------------------------------

#: The specialists, one authority for channel ownership on the runtime side.
#: prompts.SPECIALIST_PROMPT_SPECS holds each one's sheet material keyed by
#: the same channel names, and schemas.SPECIALIST_CHANNELS the same map by
#: step key; tools/project_check.py holds all three level. Dict order is the
#: CANONICAL assembly order: merges happen in this order whatever order the
#: parallel calls complete in, so a rerun with the same inputs produces the
#: same merged diff.
SPECIALISTS = {
    "body": {
        "step_key": "director_body",
        "role": "director_body",
        "channels": ("attire", "conditions", "vitals", "overlays"),
    },
    "social": {
        "step_key": "director_social",
        "role": "director_social",
        # `following_ops` belongs to this family in the corpus table but is
        # NOT owned here: following is actor-owned and engine-projected
        # (`_collect_following_ops` overwrites the channel deterministically
        # every resolve), so no model authors it -- a specialist "owning" it
        # would own a channel whose content is discarded.
        "channels": ("cast_changes", "introductions", "world_facts"),
    },
    "contact": {
        "step_key": "director_contact",
        "role": "director_contact",
        "channels": ("contact_ops", "substance_ops", "containment",
                     "scales"),
    },
    "objects": {
        "step_key": "director_objects",
        "role": "director_objects",
        "channels": ("entities", "remove_entities", "inventory_ops",
                     "artifact_ops", "destruction"),
    },
    # The geography. Carved LAST by design: the movement backstop, the
    # following projection, approach semantics and the near-group
    # reconciliation all judge the MERGED diff and stay with the
    # orchestrator -- this specialist proposes relocations and never has
    # the last word on them.
    "spatial": {
        "step_key": "director_spatial",
        "role": "director_spatial",
        "channels": ("positions", "rooms", "remove_rooms",
                     "remove_adjacent", "stations", "poses", "comms_ops"),
    },
    # The world's traffic. The ops surface ONLY -- the offscreen SIMULATOR
    # (design note 19's out-of-band parallel) remains owner-deferred, and
    # nothing here schedules or simulates anything. Genuinely dispatchable:
    # it runs whenever its subjects exist in scene (crowds, couriers,
    # carried reports, unratified hearsay, the planning floor switched on),
    # and is cold in practice only because most scenes contain none.
    "offscreen": {
        "step_key": "director_offscreen",
        "role": "director_offscreen",
        "channels": ("crowd_ops", "courier_ops", "telling_ops",
                     "offscreen_plan_ops", "ratified_claims",
                     "contradicted_claims"),
    },
}

#: Every channel any specialist owns, in canonical assembly order. MUTATED
#: in place by `_rebuild_channel_owners`, never rebound: `director.py` and
#: `director_fanout.py` bind the name at import, so a rebind would leave both
#: readers holding the import-time list forever.
_DELEGATED_CHANNELS = []

#: `changes_asserted` category -> the delegated channel that answers for it.
#: Categories with no delegated channel (time, transit, other, ...) stay
#: the prose author's own and are not the scope backstop's business.
#:
#: KEYED ON THE NORMALIZED CATEGORY NAMES (_normalize_omission_category's
#: output: 'contacts', 'substances', 'poses', ...): every reader of this map
#: looks up items that already went through _manifest_items, which
#: normalizes. The original raw spellings ('contact', 'substance', 'pose')
#: are kept as tolerance for a caller that never normalized, but for two
#: releases they were the ONLY keys -- so a manifest entry asserting a
#: contact, substance or pose change could never reach the scope backstop
#: or be sliced into its specialist's payload, silently.
_CATEGORY_CHANNELS = {
    "attire": "attire",
    "conditions": "conditions",
    "cast_changes": "cast_changes",
    "contact": "contact_ops",
    "contacts": "contact_ops",
    "substance": "substance_ops",
    "substances": "substance_ops",
    "inventory": "inventory_ops",
    "entities": "entities",
    "positions": "positions",
    "rooms": "rooms",
    # An adjacency change is either a rooms-edge edit or a severance; the
    # rooms gate and the remove_adjacent gate are the same fact, so either
    # served scope answers for the category.
    "adjacency": "rooms",
    "pose": "poses",
    "poses": "poses",
    "stations": "stations",
    # Equipment that carries a voice, not the doorway it carries it past. A
    # beat that keys a mic, kills an intercom or hands someone a radio is
    # categorized here, so it reaches the specialist that owns the channel
    # rather than being detected as an omission every beat and repaired by a
    # mind that never saw it.
    "comms": "comms_ops",
    "comms_ops": "comms_ops",
    # The remaining delegated families. A category that reaches no channel
    # is a change nobody is handed and nobody can encode, so it is detected
    # as an omission every beat and buys a repair from a mind that never
    # saw it -- measured live at 49.2s for two such events in one beat.
    "overlays": "overlays",
    "vitals": "vitals",
    "containment": "containment",
    "scales": "scales",
    "destruction": "destruction",
    "artifacts": "artifact_ops",
    "introductions": "introductions",
    "world_facts": "world_facts",
}

#: The delegated channels whose value is a LIST rather than a keyed table.
#: `_normalized_channel_value` coerces everything else to dict-or-`{}`, so a
#: channel missing from here loses its whole value at assembly.
#:
#: DERIVED, not enumerated. For the engine's own channels the shape is already
#: declared once, in `schemas.StateDiff` -- and a hand-copy of it was free to
#: disagree with the model that actually parses the output. An extension's
#: channel is in no schema, so it declares its own shape at registration
#: (`register_specialist(list_channels=...)`) and defaults to a keyed table.
#: Mutated in place for the same reason as `_DELEGATED_CHANNELS`.
_LIST_DELEGATED = set()


def _schema_list_channels():
    """`StateDiff` fields typed as a bare list. The engine's half of the shape.

    Reads the annotation rather than the default factory: the factory is what
    an omission produces, the annotation is what the field IS.
    """
    from llm.schemas import StateDiff

    out = set()
    for name, field in StateDiff.__fields__.items():
        annotation = getattr(field, "outer_type_", None)
        if annotation is list or get_origin(annotation) is list:
            out.add(name)
    return out

#: Per-CHANNEL work gates: does this beat have possible work in this
#: channel? Every input is standing scene state or a structured declaration
#: -- never prose. FAIL OPEN is the rule: a channel is gated out only when
#: its subject provably does not exist (nobody wears anything, no vitals
#: tracked, no notice posted and nothing carried to post, nothing
#: destructible standing); where structure cannot decide, the channel is in
#: scope, which is why most gates degrade to `physical_beat`. The scope a
#: specialist is granted is the union the orchestrator measures itself by
#: (scope_report), and `_orchestration_scope_backstop` reports any channel
#: that shipped content without having been in a served scope.
#:
#: Two residuals are documented rather than closed, both backstopped:
#: dressing a fully bare body (attire gated on `anyone_wears`; caught by the
#: manifest half of the backstop) and posting an INVENTED claim with no
#: notice standing and nothing carried (artifact_ops; caught by the
#: reconciliation seam). `destruction` gates on a destructible ENTITY;
#: a narrated destruction of a bare room keeps its own deterministic
#: tripwire (`_narrated_destruction_subjects`), which stays core.
_CHANNEL_GATES = {
    "attire": lambda f: f["physical_beat"] and f["anyone_wears"],
    "conditions": lambda f: f["physical_beat"] or f["active_conditions"],
    "vitals": lambda f: f["physical_beat"] and f["vitals_tracked"],
    "overlays": lambda f: f["physical_beat"] or f["overlays_present"],
    "cast_changes": lambda f: f["physical_beat"],
    "introductions": lambda f: f["speech_present"],
    "world_facts": lambda f: f["speech_present"] or f["physical_beat"],
    "contact_ops": lambda f: f["physical_beat"] or f["contacts_standing"],
    "substance_ops": lambda f: (f["physical_beat"]
                                or f["material_effects_declared"]),
    "containment": lambda f: f["physical_beat"] or f["containment_active"],
    "scales": lambda f: f["physical_beat"] or f["scales_active"],
    "entities": lambda f: f["physical_beat"],
    "remove_entities": lambda f: f["physical_beat"],
    "inventory_ops": lambda f: f["physical_beat"],
    "artifact_ops": lambda f: f["physical_beat"] and (
        f["notices_in_scene"] or f["reports_carried"]),
    "destruction": lambda f: f["physical_beat"] and f["destructible_entity"],
    # Geography: every one of these changes by an act (moving, building,
    # sealing, sitting, rising), so the structural physical-beat fact is the
    # gate. Residual: a room's light changing on a pure time-skip beat
    # (dusk falls) is undecidable from state and is caught by the manifest
    # half of the backstop.
    "positions": lambda f: f["physical_beat"],
    "rooms": lambda f: f["physical_beat"],
    "remove_rooms": lambda f: f["physical_beat"],
    "remove_adjacent": lambda f: f["physical_beat"],
    "stations": lambda f: f["physical_beat"],
    "poses": lambda f: f["physical_beat"],
    # A channel is opened, closed, carried or installed by an ACT, so the
    # structural physical-beat fact gates it -- but a beat where anyone is
    # SPEAKING can also key a mic, which is the ordinary way an intercom gets
    # used. Fails open across both, per the rule this table follows.
    "comms_ops": lambda f: f["physical_beat"] or f["speech_present"],
    # The world's traffic: gated on its subjects EXISTING, which is what
    # makes this family cold in practice (0 fires in 2,243 beats) while
    # staying genuinely dispatchable the moment a crowd stands in a room or
    # a report is carried. Residuals, documented: a send/telling built on an
    # INVENTED claim with nothing carried, and minting a brand-new crowd in
    # a scene that had none -- both undecidable from state, both left to
    # the reconciliation seam, and both 0-fire channels today.
    "crowd_ops": lambda f: f["crowds_present"],
    "courier_ops": lambda f: f["couriers_present"] or f["reports_carried"],
    "telling_ops": lambda f: f["reports_carried"] or f["crowds_present"],
    "offscreen_plan_ops": lambda f: f["offscreen_planning_enabled"],
    "ratified_claims": lambda f: f["unratified_claims_present"],
    "contradicted_claims": lambda f: f["unratified_claims_present"],
}


# ---------------------------------------------------------------- extensions
#
# A seventh family, and an eighth, authored outside this tree.
#
# Every registry above is one an extension could only reach by mutating a
# module global, and there are SIX of them (`SPECIALISTS`, `_CHANNEL_GATES`,
# `_CHANNEL_SPECIALISTS`, `schemas.SPECIALIST_CHANNELS` + a model +
# `SCHEMA_MAP`, `prompts.SPECIALIST_PROMPT_SPECS`, `providers.ROLES`). Patching
# five of the six is not a degraded specialist -- `_dispatch_specialists` reads
# `SPECIALISTS` live and then indexes `_CHANNEL_GATES` by channel, so an
# unregistered gate is a KeyError inside the Director on every beat. This is
# the same shape `add_stage` was built to end: the execution half already
# worked, the REGISTRATION half was the part that forced a third party to edit
# an engine file.
#
# Three deliberate differences from an in-tree specialist, each because the
# alternative would be a quiet lie:
#
# * **Channels are namespaced `ext:<id>:<channel>`.** A family that could claim
#   `attire` would silently take ownership of the body specialist's channel and
#   replace it in the merged diff.
# * **Its channels are EVIDENCE, not causality.** No commit domain reads an
#   `ext:` channel, so a registered specialist's output lands in `state_diff`
#   and changes nothing by itself. The extension acts on it from its own commit
#   domain or stage -- which keeps the engine's own persistence honest and is
#   the same annotator default `ext:` steps already have.
# * **No prose-author chunk.** `PROSE_AUTHOR_SHEET` and its one-owner test live
#   in this tree; an extension cannot add a block to the sheet, so a registered
#   channel is written to the ledger and NOT narrated. Stated plainly in the
#   guide, because "it committed but nobody mentioned it" is otherwise a
#   fifty-beat mystery.
#
# The default gate fails open on `physical_beat`, which is the rule
# `_CHANNEL_GATES` already states: over-dispatch costs one call, under-dispatch
# silently drops work.

#: channel -> the specialist that owns it. The reconciliation repair router
#: reads this: an omission in a delegated channel is that channel's OWNER's to
#: repair, at specialist cost, never the prose author's at full-core cost.
#: Recomputed rather than frozen at import -- it WAS a module-level
#: comprehension over `SPECIALISTS`, which meant a family registered afterwards
#: was invisible to `_route_repair_omissions` while being perfectly visible to
#: dispatch: a split that routes a repair to nobody.
_CHANNEL_SPECIALISTS = {}


def _default_channel_gate(facts):
    return facts["physical_beat"]


def _rebuild_channel_owners():
    """The three channel registries, rebuilt together from `SPECIALISTS`.

    Together, because they are three views of one fact and were not always
    derived from it: an owner map, the ordered roll the scope backstop walks,
    and the shape table assembly coerces against. Each one that stayed frozen
    at import was a way for a family registered afterwards to be dispatched and
    then dropped -- routed to nobody, reported by nobody, or emptied at merge.
    """
    schema_shapes = _schema_list_channels()
    _CHANNEL_SPECIALISTS.clear()
    _DELEGATED_CHANNELS[:] = []
    _LIST_DELEGATED.clear()
    for name, spec in SPECIALISTS.items():
        for channel in spec["channels"]:
            _CHANNEL_SPECIALISTS[channel] = name
            _DELEGATED_CHANNELS.append(channel)
        # An engine channel's shape is `StateDiff`'s to state; an extension's
        # is its own, because no schema here has ever seen it.
        if spec.get("ext_id"):
            _LIST_DELEGATED.update(spec.get("list_channels") or ())
        else:
            _LIST_DELEGATED.update(
                ch for ch in spec["channels"] if ch in schema_shapes)


#: The engine's own six, populated the same way an extension's seventh will be.
_rebuild_channel_owners()


def register_specialist(ext_id, name, *, channels, prompt, gate=None,
                        role="default", label=None, list_channels=None):
    """Add a Director specialist family owned by an extension.

    Returns its registered name. Raises on a name or channel that would
    collide with the engine's own, because a silent collision here transfers
    ownership of a real channel.

    `list_channels` names the subset of `channels` whose value is a LIST.
    Assembly coerces every other channel to a keyed table, so a list-valued
    channel left undeclared arrives as `{}` -- dispatched, paid for and
    discarded with nothing said.
    """
    ext_id = str(ext_id or "").strip()
    name = str(name or "").strip()
    if not ext_id or not name:
        raise ValueError("a specialist needs an extension id and a name")
    full_name = f"ext:{ext_id}:{name}"
    wanted = [str(channel or "").strip() for channel in (channels or [])]
    if not wanted or not all(wanted):
        raise ValueError(f"specialist {full_name!r} declares no channels")
    if not str(prompt or "").strip():
        raise ValueError(f"specialist {full_name!r} declares no prompt")
    listed = [str(channel or "").strip() for channel in (list_channels or [])]
    unknown = sorted(set(listed) - set(wanted))
    if unknown:
        raise ValueError(
            f"specialist {full_name!r} declares {unknown} list-shaped, "
            "but does not own them")
    owned = [f"ext:{ext_id}:{channel}" for channel in wanted]
    for channel in owned:
        existing = _CHANNEL_SPECIALISTS.get(channel)
        if existing and existing != full_name:
            raise ValueError(
                f"channel {channel!r} already belongs to {existing!r}")

    SPECIALISTS[full_name] = {
        "step_key": full_name,
        "role": str(role or "default"),
        "channels": tuple(owned),
        "ext_id": ext_id,
        "list_channels": tuple(f"ext:{ext_id}:{channel}" for channel in listed),
        "prompt": str(prompt),
        "label": str(label or f"Specialist · {ext_id} · {name}"),
    }
    for channel in owned:
        _CHANNEL_GATES[channel] = gate if callable(gate) else _default_channel_gate
    _rebuild_channel_owners()
    return full_name


def unregister_specialists(ext_id):
    """Drop every specialist one extension registered. Returns their names."""
    prefix = f"ext:{str(ext_id or '')}:"
    dropped = [name for name in SPECIALISTS if name.startswith(prefix)]
    for name in dropped:
        for channel in SPECIALISTS[name]["channels"]:
            _CHANNEL_GATES.pop(channel, None)
        del SPECIALISTS[name]
    _rebuild_channel_owners()
    return dropped


def _extension_specialist_call(spec, scope, payload, language=None):
    """Run an extension-owned specialist. The CALL itself lives elsewhere.

    Deliberately a one-line delegation to `extension_runtime`. An extension
    owns the shape of its own channels, so its call cannot go through
    `_agent_json` -- that path validates against `schemas.SCHEMA_MAP`, which
    only knows this engine's own steps. But the permissive parse that follows
    from that must not live in THIS file: `test_stage_modules_stay_on_strict_path`
    forbids `jparse` in a stage module, and the rule is right -- a Director
    stage's own output reaches `commit.py` and must be strictly validated. The
    extension's does not (no commit domain reads an `ext:` channel), so the
    looseness is correct and belongs in the extension package, where it cannot
    be reached for by a future engine stage.
    """
    from extension_runtime import run_specialist_call

    return run_specialist_call(spec, scope, payload)


def _shipped_transit_state(sd):
    for entity in (sd.get("entities") or {}).values():
        if not isinstance(entity, dict):
            continue
        if entity.get("interior_rooms"):
            return True
        state = entity.get("state") \
            if isinstance(entity.get("state"), dict) else {}
        if state.get("transit") or state.get("link"):
            return True
    return any(isinstance(room, dict) and room.get("parent_entity")
               for room in (sd.get("rooms") or {}).values())


def _shipped_darkened_room(sd):
    from world.spatial import normalize_light
    return any(
        isinstance(room, dict) and room.get("light") is not None
        and normalize_light(room.get("light")) in ("dim", "dark")
        for room in (sd.get("rooms") or {}).values())


def _shipped_bodiless_definition(sd):
    from story.scene import is_ubiquitous_entity
    return any(is_ubiquitous_entity(entity)
               for entity in (sd.get("entities") or {}).values()
               if isinstance(entity, dict))


#: The prose half of the scope backstop: per gated chunk, deterministic
#: evidence in the FINAL output that its duty shipped anyway. Only the
#: chunks whose gate is a PREDICTION appear here; the exact-payload gates
#: (other_players, mapping_proposal, hearsay, due_events, world_pressure,
#: residue) read the very list their duty is about and cannot mispredict,
#: and `road`'s op channels are already audited by the specialist-channel
#: half (its gate facts are a superset of the offscreen dispatch gates).
_PROSE_DUTY_SHIPPED = {
    "voices": lambda out, sd: (
        "a bodiless (ubiquitous) voice was defined"
        if _shipped_bodiless_definition(sd) else None),
    "obligations": lambda out, sd: (
        "obligation ops shipped" if out.get("obligations") else None),
    "comm": lambda out, sd: (
        "a medium:'comm' line shipped"
        if any(isinstance(d, dict)
               and str(d.get("medium") or "").strip().lower() == "comm"
               for d in out.get("dialogue_log") or []) else None),
    "transit": lambda out, sd: (
        "transit/moving-room state was encoded"
        if _shipped_transit_state(sd) else None),
    "approach": lambda out, sd: (
        "a body was relocated" if sd.get("positions") else None),
    "light": lambda out, sd: (
        "a room was set dim or dark"
        if _shipped_darkened_room(sd) else None),
    "size": lambda out, sd: (
        "a size change was encoded" if sd.get("scales") else None),
}


def _gate_facts(ctx, sc, *, physical, speech, material_effects=False):
    """The scene facts every channel gate reads, computed once per stage,
    at that stage's own time. Standing scene state (ledgers, settings) plus
    the two structured beat facts the caller supplies; no prose anywhere.
    A fact whose read fails degrades to True -- fail open, never gate a
    channel out on an error."""
    chat_id = ctx.chat["id"]
    entities = sc.get("entities") or {}
    destructible = any(
        isinstance(e, dict) and (
            str(e.get("kind") or "").strip().casefold() in (
                "vehicle", "building", "structure", "ship", "boat")
            or e.get("interior_rooms"))
        for e in entities.values())
    try:
        notices = bool(_artifacts_view(chat_id, sc))
    except Exception:
        notices = True
    try:
        reports = bool(_carried_reports_view(ctx))
    except Exception:
        reports = True
    try:
        crowds = bool(_crowds_view(chat_id, sc))
    except Exception:
        crowds = True
    try:
        couriers = bool(_couriers_view(chat_id, sc))
    except Exception:
        couriers = True
    try:
        unratified = bool(_unratified_background_claims(
            chat_id, ctx.turn["idx"]))
    except Exception:
        unratified = True
    try:
        from world.living_world import living_world_allows, living_world_config
        planning = bool(living_world_allows(
            living_world_config(chat_id), "antagonist_ladder", "floor"))
    except Exception:
        # The one deliberate deviation from fail-open-on-error: plan ops are
        # refused deterministically at commit unless this setting is on, so
        # granting the chunk on a failed read could never yield an op commit
        # would accept -- it would only spend tokens on a dead channel.
        planning = False
    return {
        "physical_beat": bool(physical),
        "speech_present": bool(speech),
        "anyone_wears": any(
            bool(entry) for entry in (sc.get("attire") or {}).values()),
        "active_conditions": bool(q(
            "SELECT 1 FROM world_conditions WHERE chat_id=? AND active=1 "
            "LIMIT 1", (chat_id,))),
        "overlays_present": any(
            bool(v) for v in (sc.get("overlays") or {}).values()),
        "vitals_tracked": survival_enabled(chat_id),
        "contacts_standing": bool(sc.get("contacts")),
        "containment_active": bool(sc.get("contained")),
        "scales_active": any(
            isinstance(v, (int, float)) and float(v) != 1.0
            for v in (sc.get("scales") or {}).values()),
        "material_effects_declared": bool(material_effects),
        "notices_in_scene": notices,
        "reports_carried": reports,
        "destructible_entity": destructible,
        "crowds_present": crowds,
        "couriers_present": couriers,
        "unratified_claims_present": unratified,
        "offscreen_planning_enabled": planning,
    }


def _dispatch_specialists(ctx, sc, facts):
    """The orchestrator measuring how much of a job each specialist needs
    to do: per specialist, the SCOPE -- the set of its channels with
    possible work this beat. Everything else follows from that one value:
    an empty scope is a specialist not dispatched at all; a non-empty scope
    is dispatched with its sheet assembled from exactly those channels'
    chunks (prompts.specialist_prompt). Dispatch is `bool(scope)`, not a
    second decision that could disagree with the sheet assembly, and the
    single backstop below audits shipped content against the same value."""
    dispatch = {}
    for name, spec in SPECIALISTS.items():
        # `.get` with a fail-open default, not `[]`: a channel whose gate is
        # missing is a registration bug, and raising KeyError here would turn
        # it into a dead Director on every beat rather than one specialist
        # running more often than it needs to.
        scope = [channel for channel in spec["channels"]
                 if _CHANNEL_GATES.get(channel, _default_channel_gate)(facts)]
        dispatch[name] = {
            "run": bool(scope),
            "scope": scope,
            "channels": list(spec["channels"]),
            "facts": facts,
        }
    return dispatch
