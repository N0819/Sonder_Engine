# schemas.py
"""Pydantic schemas for all pipeline and world-state structures."""

import json
import re

from pydantic import BaseModel, Field, ValidationError, validator
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Union


def _coerce_str_list(value):
    """Normalize a value into a list[str], tolerating the shapes smaller /
    cheaper LLMs emit where the schema wants plain strings: a bare string,
    a single object, a list of objects, or nested lists. We preserve the
    text (pulling a sensible field out of objects) instead of hard-rejecting
    the entire step -- a dropped alternative is far cheaper than a crashed
    character turn. See tests/test_tom_normalization.py."""
    if value is None:
        return []
    if isinstance(value, (str, dict)):
        value = [value]
    elif not isinstance(value, (list, tuple)):
        value = [value]

    out = []
    for item in value:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            picked = next(
                (
                    str(item[key])
                    for key in ("claim", "text", "label", "description", "hypothesis", "value")
                    if item.get(key)
                ),
                None,
            )
            out.append(picked if picked is not None else json.dumps(item, ensure_ascii=False, sort_keys=True))
        elif isinstance(item, (list, tuple)):
            out.append("; ".join(str(part) for part in item))
        else:
            out.append(str(item))
    return out


def _clamp_float(value, lo, hi, default):
    """Coerce to a float within [lo, hi], tolerating the out-of-range numbers
    and non-numeric strings weaker models emit for bounded fields (a
    prompt-compliant 'big betrayal' delta of 0.3, confidence '85', urgency
    'high'). Clamping is obviously correct here and keeps the character step
    from hard-crashing on an advisory number. See tests/test_tom_normalization.py."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f:  # NaN
        return default
    return max(lo, min(hi, f))

# ---- Pydantic v1/v2 Compatibility ----

if hasattr(BaseModel, "model_validate"):
    def _validate(model_cls, data):
        return model_cls.model_validate(data)

    def _dump(model):
        return model.model_dump(exclude_none=True)

    def _fields(model_cls):
        return model_cls.model_fields
else:
    def _validate(model_cls, data):
        return model_cls.parse_obj(data)

    def _dump(model):
        return model.dict(exclude_none=True)

    def _fields(model_cls):
        return model_cls.__fields__

# ---- Enums ----

class SpeechVolume(str, Enum):
    whisper = "whisper"
    mutter = "mutter"
    normal = "normal"
    loud = "loud"
    shout = "shout"

class ActionVisibility(str, Enum):
    overt = "overt"
    concealed = "concealed"

class ActionCommitment(str, Enum):
    asserted = "asserted"
    contestable = "contestable"

class ActionStage(str, Enum):
    immediate = "immediate"
    preparation = "preparation"
    approach = "approach"
    contact = "contact"
    sustained = "sustained"

class TemporalMode(str, Enum):
    immediate = "immediate"
    extended = "extended"
    time_skip = "time_skip"

class PlayerAuthorityMode(str, Enum):
    actor_only = "actor_only"
    explicit_outcomes = "explicit_outcomes"
    world_author = "world_author"

class BehaviorController(str, Enum):
    inert = "inert"
    deterministic = "deterministic"
    reactive = "reactive"
    stochastic = "stochastic"
    character_agent = "character_agent"
  
_VOLUME_ALIASES = {
    "": "normal",
    "quiet": "mutter",
    "quietly": "mutter",
    "soft": "mutter",
    "softly": "mutter",
    "conversational": "normal",
    "conversation": "normal",
    "moderate": "normal",
    "medium": "normal",
    "ordinary": "normal",
    "enthusiastic": "loud",
    "excited": "loud",
    "raised": "loud",
    "raised voice": "loud",
    "yell": "shout",
    "yelling": "shout",
    "scream": "shout",
    "screaming": "shout",
}

def normalize_speech_volume(value: Any) -> str:
    volume = str(value or "normal").strip().casefold()
    volume = _VOLUME_ALIASES.get(volume, volume)

    if volume not in {
        "whisper",
        "mutter",
        "normal",
        "loud",
        "shout",
    }:
        return "normal"

    return volume
    

# ---- Fiction Model ----

# ---- One coercion for a whole failure family ----
#
# Five separate crashes in one session were the same shape: a field typed `str`
# receiving a structured object, which discards the ENTIRE stage output and
# costs a whole beat -- observations_used, association_updates, initial_state
# goals, response_candidates.response, changes_asserted.change. Roughly ninety
# more str-typed fields in this file carry the same exposure, and fixing them as
# they crash is a queue rather than a solution.
#
# So the coercion lives once, on a base every schema model inherits. It fires
# only when the declared type is `str` AND the value is a dict or list -- the
# exact mismatch -- and reduces to the prose the value contains. Anything else
# passes through untouched, so it cannot mask a genuine type error on a field
# never meant to hold text.
#
# Rejecting these was never protecting anything: a str field has no invariant a
# nested object violates, and the model plainly meant the words inside it.
_PROSE_KEYS = ("text", "observable", "attempt", "summary", "description",
               "content", "value", "claim", "response", "detail", "reason",
               "name", "id")


def _flatten_to_text(value):
    """The prose inside a structured value, for a field declared `str`."""
    if isinstance(value, dict):
        for key in _PROSE_KEYS:
            got = value.get(key)
            if isinstance(got, str) and got.strip():
                return got.strip()
        parts = [str(v).strip() for v in value.values()
                 if isinstance(v, (str, int, float)) and str(v).strip()]
        return "; ".join(parts)
    if isinstance(value, (list, tuple)):
        parts = [
            _flatten_to_text(v) if isinstance(v, (dict, list, tuple))
            else str(v).strip()
            for v in value
        ]
        return "; ".join(p for p in parts if p)
    return value


class LenientModel(BaseModel):
    """BaseModel that accepts a structured value where prose was declared."""

    @validator("*", pre=True, allow_reuse=True)
    def _coerce_structured_into_str(cls, value, field):
        if isinstance(value, (dict, list, tuple)) and field.outer_type_ is str:
            return _flatten_to_text(value)
        return value



class GenreProfile(LenientModel):
    primary: str = "unspecified"
    secondary: list[str] = Field(default_factory=list)
    tone: list[str] = Field(default_factory=list)
    motifs: list[str] = Field(default_factory=list)
    threat_density: float = 0.3
    mystery_density: float = 0.3
    humor_density: float = 0.2
    lethality: float = 0.3
    supernatural_prevalence: float = 0.0
    technology_level: str = "unspecified"
    content_boundaries: list[str] = Field(default_factory=list)

class CausalRegime(LenientModel):
    regime_id: str
    scope: str = "default"
    priority: int = 0
    rules: dict[str, Any] = Field(default_factory=dict)

class FictionModel(LenientModel):
    genre: dict[str, Any] = Field(default_factory=dict)
    ontology: dict[str, Any] = Field(default_factory=dict)
    causal_regimes: list[dict] = Field(default_factory=list)
    scale_rules: dict[str, Any] = Field(default_factory=dict)
    abstraction_rules: dict[str, Any] = Field(default_factory=dict)
    narrative_conventions: list[dict] = Field(default_factory=list)
    epistemic_rules: list[dict] = Field(default_factory=list)
    content_rules: list[dict] = Field(default_factory=list)

class FictionFrame(LenientModel):
    frame_id: str = ""
    world_id: str = ""
    location_id: Optional[str] = None
    scale: str = "personal"
    temporal_mode: str = "immediate"
    causal_regime_ids: list[str] = Field(default_factory=list)
    active_entity_ids: list[str] = Field(default_factory=list)
    aggregate_entity_ids: list[str] = Field(default_factory=list)
    observer_ids: list[str] = Field(default_factory=list)
    stakes: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)

class ScenePressure(LenientModel):
    threat: float = 0.0
    mystery: float = 0.0
    social: float = 0.0
    environmental: float = 0.0
    recent_release: float = 0.0

# ---- Time ----

class SimulationClock(LenientModel):
    elapsed_seconds: float = 0.0
    calendar: Optional[dict[str, Any]] = None
    display: str = "now"
    time_scale: str = "scene"

class TimeDiff(LenientModel):
    start_seconds: float = 0.0
    duration_seconds: float = 0.0
    end_seconds: float = 0.0
    mode: str = "action"
    explicit: bool = False
    display_advance: str = ""

class TemporalProperties(LenientModel):
    rate_numerator: float = 1.0
    rate_denominator: float = 1.0
    offset_seconds: float = 0.0
    causal_ordering: str = "global"
    supports_time_travel: bool = False

# ---- Actions ----

class DurationHint(LenientModel):
    value: Optional[float] = None
    unit: str = "seconds"
    explicit: bool = False

class IntendedEffect(LenientModel):
    target_id: Optional[str] = None
    kind: str
    details: dict[str, Any] = Field(default_factory=dict)

class ActionElement(LenientModel):
    type: str = "action"
    event_id: str = ""
    actor_id: str = ""
    raw_text: str = ""
    attempt: str = ""
    # Intent-free OUTWARD surface of the act -- what a bystander literally
    # sees/hears, with no purpose, magical intent, or private mental content.
    # Delivered to OTHER perceivers in place of `attempt` (which is the actor's
    # own intent-laden framing). "" = the act has no outward manifestation (a
    # purely mental beat) and must not be surfaced to observers at all. See
    # agents/common.observable_action_text and norm_sequence.
    observable: str = ""
    # Authorship mode of a player-authored element. 'pc_action' (default) is
    # the player's character acting. 'npc_offer' is the player authoring another
    # character's interior/behavior -- rerouted to that character's own agent as
    # an offer rather than enacted as truth (the character owns its psychology).
    # 'world_assertion'/'ooc_directive' name the authorial and out-of-character
    # channels. Legacy payloads with no mode default to pc_action.
    mode: str = "pc_action"
    verb: str = ""
    commitment: ActionCommitment = ActionCommitment.contestable
    stage: ActionStage = ActionStage.immediate
    targets: list[str] = Field(default_factory=list)
    instruments: list[str] = Field(default_factory=list)
    intended_effects: list[IntendedEffect] = Field(default_factory=list)
    asserted_effects: list[IntendedEffect] = Field(default_factory=list)
    duration: DurationHint = Field(default_factory=DurationHint)
    visibility: ActionVisibility = ActionVisibility.overt
    conceal_from: list[str] = Field(default_factory=list)
    conditions: list[dict] = Field(default_factory=list)

class SpeechElement(LenientModel):
    type: str = "speech"
    text: str
    volume: SpeechVolume = SpeechVolume.normal

    _norm_volume = validator("volume", pre=True, allow_reuse=True)(
        lambda cls, v: normalize_speech_volume(v)
    )
    tone: str = ""
    visibility: ActionVisibility = ActionVisibility.overt
    conceal_from: list[str] = Field(default_factory=list)

class DiceSpec(LenientModel):
    # Advisory sub-field of the interpret flow; the Director re-judges
    # difficulty during resolution, so a weak model dropping one key must
    # not hard-crash the whole director_interpret step.
    actor: str = ""
    attempt: str = ""
    ability: str = ""
    difficulty: str = "medium"

class ResolutionCheck(LenientModel):
    check_id: str = ""
    event_id: str = ""
    actor_id: str = ""
    opposing_actor_id: Optional[str] = None
    ability: str = ""
    opposing_ability: Optional[str] = None
    difficulty: str = "medium"
    modifiers: list[dict] = Field(default_factory=list)
    seed: str = ""
    roll: Optional[int] = None
    opposing_roll: Optional[int] = None
    outcome: str = ""

class MovementDecl(LenientModel):
    to_room: str
    why: str = ""
    # WHO relocates. "self" (default) = the player's own body. An entity id
    # = the declared move is of a VEHICLE/vessel/mount the player is
    # driving or piloting: the ENTITY's exterior position changes and the
    # player's body stays where it is (typically that entity's interior).
    # Without this field "I drive the van onto the ferry" was structurally
    # identical to "I walk onto the ferry" and moved the player's body.
    mover: str = "self"

# ---- Authority ----

class AuthorityClaim(LenientModel):
    claim_id: str = ""
    scope: str = "action"
    subject_id: Optional[str] = None
    predicate: str = ""
    value: Any = None
    commitment: str = "asserted"
    source_text: str = ""

class ClaimDisposition(LenientModel):
    claim_id: str = ""
    status: str = "realized"
    realized_event_ids: list[str] = Field(default_factory=list)
    notes: str = ""

class GenerationRequest(LenientModel):
    kind: str
    subject: str = ""
    location_id: Optional[str] = None
    constraints: list[str] = Field(default_factory=list)
    evidence_event_ids: list[str] = Field(default_factory=list)
    urgency: str = "now"

# ---- Flow ----

class FlowPlan(LenientModel):
    reactors: list[int] = Field(default_factory=list)
    reactor_refs: list[Any] = Field(default_factory=list)
    addressed_to: list[int] = Field(default_factory=list)
    addressed_to_refs: list[Any] = Field(default_factory=list)
    dialogue_mode: bool = False
    needs_mapping: bool = False
    mapping_request: str = ""
    dice: list[DiceSpec] = Field(default_factory=list)
    tom_triggers: list[int] = Field(default_factory=list)
    tom_trigger_refs: list[Any] = Field(default_factory=list)
    resolution_flags: dict[str, Any] = Field(default_factory=dict)
    generation_requests: list[dict] = Field(default_factory=list)
    authority_claims: list[dict] = Field(default_factory=list)
    fiction_frame: dict[str, Any] = Field(default_factory=dict)
    # Future world beats the player narrated for a LATER turn (P4). Each
    # {summary, due_in_turns}; the engine stores and re-delivers them when due
    # so a player-scheduled event is never silently dropped.
    scheduled_assertions: list[dict] = Field(default_factory=list)

# ---- Director Interpret ----

class OtherPlayerInterpret(LenientModel):
    """Same-beat declaration for an additional human player, interpreted
    with the same rigor as the primary player's top-level fields above --
    this is a second real player, not an NPC. Deliberately a narrower
    mirror of DirectorInterpret's own fields (no separate flow/movement
    plan) rather than a full duplicate: each extra player still shares the
    beat's single flow/reactor plan, since interaction/reaction resolution
    stays scene-wide, not per-player.
    """
    sequence: list[dict] = Field(default_factory=list)
    speech: Optional[str] = None
    speech_volume: SpeechVolume = SpeechVolume.normal
    private_thought: Optional[str] = None
    action: Optional[dict] = None
    notes: str = ""

    _norm_volume = validator("speech_volume", pre=True, allow_reuse=True)(
        lambda cls, v: normalize_speech_volume(v)
    )

class DirectorInterpret(LenientModel):
    kind: str = "mixed"
    sequence: list[dict] = Field(default_factory=list)
    speech: Optional[str] = None
    speech_volume: SpeechVolume = SpeechVolume.normal
    private_thought: Optional[str] = None
    action: Optional[dict] = None
    actions: list[dict] = Field(default_factory=list)
    movement: Optional[MovementDecl] = None
    location_query: Optional[str] = None
    flow: FlowPlan = Field(default_factory=FlowPlan)
    notes: str = ""

    _norm_volume = validator("speech_volume", pre=True, allow_reuse=True)(
        lambda cls, v: normalize_speech_volume(v)
    )
    # Additive multiplayer support: interpretations for any additional
    # human players declaring in this same beat, keyed by persona_id (as a
    # string, since JSON object keys are always strings). Empty for every
    # single-player chat -- nothing here changes behavior unless
    # ctx.extra_players is non-empty.
    other_players: dict[str, OtherPlayerInterpret] = Field(default_factory=dict)

# ---- Scene Entities ----

class SceneEntityDef(LenientModel):
    name: str
    kind: str = "object"
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    portable: bool = False
    container: bool = False
    interior_rooms: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    # A voice with no body and no room: a ship's computer, a station AI, a
    # building PA. Positioning one is a category error -- the Enterprise
    # computer is not "in Ten Forward" -- and doing so both pinned it to a
    # single room and made it a promotion candidate. Flagged entities are
    # voiced by the Director, audible wherever the scene is, and never tracked
    # as background presences.
    ubiquitous: bool = False
    # What an interior lets through: opaque | transparent | barred | membrane
    # (spatial._closed_enclosure_barrier / _open_enclosure_barrier). The first
    # three describe the CLOSED state and leave an open one see-through, which
    # is right for a lid or a hatch. `membrane` is the soft or draped opening
    # that is opaque in BOTH states -- passable, never see-through -- so an
    # occupant is concealed by going in rather than exposed by it.
    # Declared for the same reason RoomDef.zone is -- an undeclared field does
    # not survive the validation round-trip, so a Director-authored glass case
    # would silently come back opaque. Absent means opaque, the pre-existing
    # behaviour.
    enclosure: Optional[str] = None
    # What this thing EMITS when lit: dim | lit | bright. A torch, a lantern,
    # a screen. Switched off with state.lit false. Declared here for the same
    # reason enclosure is -- an undeclared field does not survive the
    # validation round-trip, and a lamp that comes back unlit is a character
    # standing in the dark holding it.
    light_source: Optional[str] = None

class RoomDef(LenientModel):
    name: str = ""
    desc: str = ""
    adjacent: list[dict] = Field(default_factory=list)
    notes: str = ""
    parent_entity: Optional[str] = None
    # Declared here (not just passed through) because Pydantic's default
    # model_dump() drops any field the model doesn't declare -- without
    # this, a model-authored "zone" would be silently stripped during
    # validate_llm_output's round-trip, before spatial_frames.py's
    # split/merge detector ever got a chance to see it. Only an
    # explicitly authored zone difference between two rooms means
    # "genuinely disconnected locale" (see spatial_frames.py's module
    # docstring); most rooms should leave this unset.
    zone: Optional[str] = None
    # How much light there is to see BY: dark | dim | lit | bright. Declared
    # for the same reason `zone` is -- an undeclared field is dropped by the
    # validation round-trip, and a room going dark must survive it. Absent
    # means lit, so nothing changes for a scene that never mentions light.
    light: Optional[str] = None

class WorldEntity(LenientModel):
    entity_id: str
    kind: str
    subtype: str = ""
    name: str = ""
    aliases: list[str] = Field(default_factory=list)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_turn: Optional[int] = None
    retired_turn: Optional[int] = None

class AggregateEntity(LenientModel):
    entity_id: str
    name: str
    aggregate_kind: str
    member_kind: str = ""
    named_member_ids: list[str] = Field(default_factory=list)
    estimated_count: Optional[int] = None
    strength: float = 1.0
    cohesion: float = 1.0
    morale: float = 1.0
    readiness: float = 1.0
    supply: float = 1.0
    mobility: float = 1.0
    command_quality: float = 0.5
    sensor_quality: float = 0.5
    capabilities: list[dict] = Field(default_factory=list)
    objectives: list[dict] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)

class ComponentState(LenientModel):
    component_id: str
    parent_entity_id: str
    kind: str
    name: str
    integrity: float = 1.0
    operational: bool = True
    capabilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)

# ---- World and Location Hierarchy ----
#
# DEPRECATED -- MARKED FOR REMOVAL (movement/space Phase 2, removed in
# Phase 3): WorldDef, LocationDef, and TransitEdge belong to the dead
# fiction_worlds/fiction_locations/transit_edges macro schema that nothing
# in the runtime pipeline ever writes. Their roles are absorbed by the
# unified model: macro geography = upper lorebook-tree books; macro
# transit = portal links (entity.state.link) + scheduled_events latency.
# Kept only so old imports/checkpoint blobs keep tolerating the shapes.

class WorldDef(LenientModel):
    world_id: str
    name: str
    kind: str = "world"
    parent_world_id: Optional[str] = None
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    ontology: dict[str, Any] = Field(default_factory=dict)
    mechanics: list[str] = Field(default_factory=list)
    genre_overrides: dict[str, Any] = Field(default_factory=dict)
    temporal_properties: dict[str, Any] = Field(default_factory=dict)
    spatial_properties: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

# DEPRECATED -- see the WorldDef block comment above.
class LocationDef(LenientModel):
    location_id: str
    world_id: str
    parent_location_id: Optional[str] = None
    kind: str = "location"
    name: str = ""
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    scale: str = "site"
    tags: list[str] = Field(default_factory=list)
    children: list[str] = Field(default_factory=list)
    connections: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    state: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

class SpatialZone(LenientModel):
    zone_id: str
    location_id: str
    name: str
    zone_kind: str = "area"
    neighbors: list[dict] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)

# DEPRECATED -- see the WorldDef block comment above.
class TransitEdge(LenientModel):
    edge_id: str
    from_world_id: str
    from_location_id: Optional[str] = None
    to_world_id: str
    to_location_id: Optional[str] = None
    kind: str
    bidirectional: bool = False
    traversal_time_seconds: Optional[float] = None
    requirements: list[dict] = Field(default_factory=list)
    costs: list[dict] = Field(default_factory=list)
    hazards: list[dict] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    source_entity_id: Optional[str] = None

class StrategicPlacement(LenientModel):
    subject_id: str
    zone_id: str
    posture: str = ""
    range_band_to: dict[str, str] = Field(default_factory=dict)
    heading: Optional[str] = None
    altitude_band: Optional[str] = None
    depth_band: Optional[str] = None

# ---- Conditions and Scheduling ----

class PersistentCondition(LenientModel):
    condition_id: str
    subject_id: str
    kind: str
    severity: float = 0.0
    started_at_seconds: float = 0.0
    expires_at_seconds: Optional[float] = None
    tick_interval_seconds: Optional[float] = None
    next_tick_seconds: Optional[float] = None
    state: dict[str, Any] = Field(default_factory=dict)
    source_event_id: Optional[str] = None

class ScheduledEvent(LenientModel):
    event_id: str
    due_at_seconds: float
    kind: str
    subject_ids: list[str] = Field(default_factory=list)
    location_id: Optional[str] = None
    trigger: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    source_event_id: Optional[str] = None
    status: str = "pending"

class DestructionEffect(LenientModel):
    """REVIVED (movement/space Phase 2, item 4) as the Director's
    declaration shape for destruction, carried in StateDiff.destruction.
    The Director owns the causal event -- code never originates a
    destruction; commit.py only realizes a declared one
    deterministically: retire the doomed book(s) + their registered
    rooms, drop the live rooms/entities via the ordinary diff machinery,
    and mint latency-gated `news_arrival` scheduled events (one per
    `news` entry). scale 'vehicle'/'building' dooms the target's ONE
    book; scale 'region' (Phase 3b) dooms the multi-book cascade
    enumerated deterministically from the lorebook tree (parent_id
    descendants + currently_within members physically inside).
    effect_id/source_event_id are optional in the declaration (commit
    derives stable ids itself)."""
    effect_id: str = ""
    source_event_id: str = ""
    target_id: str
    scale: str
    kind: str
    severity: float = 0.0
    affected_components: list[str] = Field(default_factory=list)
    affected_locations: list[str] = Field(default_factory=list)
    immediate_facts: list[str] = Field(default_factory=list)
    persistent_conditions: list[str] = Field(default_factory=list)
    estimated_casualties: Optional[dict] = None
    uncertainty: dict[str, Any] = Field(default_factory=dict)
    # Awareness propagation (info-barrier): destruction is objective the
    # moment it commits; who LEARNS of it is latency-gated. One entry per
    # audience scope: {audience: str, latency_seconds: float, summary: str}
    # -> one news_arrival scheduled event due at clock + latency, delivered
    # with told/heard provenance through the normal director/perception
    # path when it fires. latency_seconds may be omitted: the engine then
    # derives it from the audience's distance to the destroyed root in
    # the lorebook graph (near hears sooner -- Phase 3b,
    # mechanics.news_latency_seconds).
    news: list[dict] = Field(default_factory=list)

class Engagement(LenientModel):
    engagement_id: str
    world_id: str
    location_id: str
    scale: str
    side_ids: list[str] = Field(default_factory=list)
    participant_ids: list[str] = Field(default_factory=list)
    phase: str = "contact"
    objectives: dict[str, list[dict]] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    initiative_state: dict[str, Any] = Field(default_factory=dict)
    command_state: dict[str, Any] = Field(default_factory=dict)
    unresolved_effects: list[dict] = Field(default_factory=list)
    started_at_seconds: float = 0.0
    state: dict[str, Any] = Field(default_factory=dict)

# ---- Inventory and Mutations ----

class InventoryOp(LenientModel):
    op: str
    object_id: str
    from_id: Optional[str] = None
    to_id: Optional[str] = None
    relation: str = "held_by"
    details: dict[str, Any] = Field(default_factory=dict)

class ObjectStatePatch(LenientModel):
    object_id: str
    set_fields: dict[str, Any] = Field(default_factory=dict)
    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)

# ---- Reactions and Perception ----

class ReactionDeclaration(LenientModel):
    actor_id: str
    trigger_event_ids: list[str] = Field(default_factory=list)
    sequence: list[dict] = Field(default_factory=list)
    urgency: float = 0.0

class EventAtom(LenientModel):
    atom_id: str
    event_id: str
    kind: str
    source_ids: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    location_id: Optional[str] = None
    start_offset_seconds: float = 0.0
    duration_seconds: float = 0.0
    channels: dict[str, dict] = Field(default_factory=dict)
    observable: dict[str, Any] = Field(default_factory=dict)

class Observation(LenientModel):
    observation_id: str
    perceiver_id: str
    source_atom_id: str
    channel: str
    fidelity: str
    observed: dict[str, Any] = Field(default_factory=dict)
    intensity: float = Field(default=0.5, ge=0.0, le=1.0)
    suddenness: float = Field(default=0.0, ge=0.0, le=1.0)
    ambiguity: float = Field(default=0.5, ge=0.0, le=1.0)
    directed_at_self: bool = False

    _clamp_observation_axes = validator(
        "intensity", "suddenness", "ambiguity", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.5))

class SensorChannel(LenientModel):
    channel_id: str
    owner_id: str
    kind: str
    range: str
    resolution: str
    latency_seconds: float = 0.0
    coverage: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)

class ActorDef(LenientModel):
    entity_id: str
    name: str
    kind: str = "creature"
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    abilities: list[dict] = Field(default_factory=list)
    drives: list[str] = Field(default_factory=list)
    behavior_model: str = "reactive"
    cognition_tier: str = "background"
    senses: list[dict] = Field(default_factory=list)
    body: dict[str, Any] = Field(default_factory=dict)
    inventory: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

# ---- Establishment and Resolve ----

class AttireState(LenientModel):
    wearing: list[str] = Field(default_factory=list)
    state: list[str] = Field(default_factory=list)

class InitialEntityState(LenientModel):
    posture: str = ""
    activity: str = ""
    held_items: list[str] = Field(default_factory=list)
    visible_conditions: list[str] = Field(default_factory=list)

class DirectorEstablish(LenientModel):
    location: str = ""
    time: str = "now"
    scene_description: str = ""
    rooms: dict[str, RoomDef] = Field(default_factory=dict)
    entities: dict[str, SceneEntityDef] = Field(default_factory=dict)
    positions: dict[str, str] = Field(default_factory=dict)
    attire: dict[str, AttireState] = Field(default_factory=dict)
    entity_states: dict[str, InitialEntityState] = Field(default_factory=dict)
    sensory_events: list[dict] = Field(default_factory=list)
    world_facts: list = Field(default_factory=list)
    opening: str = ""
    fiction_frame: dict[str, Any] = Field(default_factory=dict)
    simulation_clock: dict[str, Any] = Field(default_factory=dict)
    # World-pressure openers (F5): scenario objects/processes established
    # with authored threat/escalation potential register on the ledger from
    # beat 0 -- {op:'open', subject, note}. Applied deterministically by
    # commit.py's commit_world_pressure.
    world_pressure: list[dict] = Field(default_factory=list)

class DialogueLogEntry(LenientModel):
    speaker: str
    exact_quote: str
    volume: SpeechVolume = SpeechVolume.normal

    _norm_volume = validator("volume", pre=True, allow_reuse=True)(
        lambda cls, v: normalize_speech_volume(v)
    )
    intended_target: Optional[str] = None
    tone: str = ""
    visibility: ActionVisibility = ActionVisibility.overt
    conceal_from: list[str] = Field(default_factory=list)

class BackgroundReactOutput(LenientModel):
    reacts: bool = False
    dialogue_log_entry: Optional[DialogueLogEntry] = None
    action: str = ""

class SceneLifeEntry(LenientModel):
    """One managed presence's conduct for this beat, attributed by name so the
    commit-side append is a ROUTING operation rather than an authoring one
    (docs/BACKGROUND_LIFE_DESIGN.md §3.11)."""
    name: str
    speech: Optional[DialogueLogEntry] = None
    action: str = ""
    # Proper nouns / world facts this entry introduces that the beat did not
    # already establish. Self-declared so they can be recorded as CLAIMS rather
    # than silently entering canon (background_claims.py); a deterministic
    # novel-proper-noun scan backstops omissions.
    asserts: list[str] = Field(default_factory=list)

class SceneLifeOutput(LenientModel):
    entries: list[SceneLifeEntry] = Field(default_factory=list)

class BlurbMintEntry(LenientModel):
    """A frozen personality blurb (§3.8). Surface only -- manner, a standing
    concern, a repeatable tic -- never private goals or beliefs about others."""
    name: str
    manner: str = ""
    trait: str = ""
    tell: str = ""
    look: str = ""

class BackdropPromptOutput(LenientModel):
    prompt: str = ""

class BlurbMintOutput(LenientModel):
    blurbs: list[BlurbMintEntry] = Field(default_factory=list)

class StateDiff(LenientModel):
    positions: dict[str, str] = Field(default_factory=dict)
    rooms: dict[str, RoomDef] = Field(default_factory=dict)
    entities: dict[str, SceneEntityDef] = Field(default_factory=dict)
    remove_entities: list[str] = Field(default_factory=list)
    remove_rooms: list[str] = Field(default_factory=list)
    remove_adjacent: list[dict] = Field(default_factory=list)
    conditions: dict[str, list[dict]] = Field(default_factory=dict)
    inventory_ops: list[dict] = Field(default_factory=list)
    # Body position tracking. Contact is a RELATION, so it is not stored on
    # either body: these ops maintain the scene-level `contacts` list
    # (spatial.apply_contact_ops), and spatial.normalize_scene_contacts prunes
    # whatever positions no longer permit. {op: add|remove|clear, actor,
    # actor_part, target, target_part, manner}.
    contact_ops: list[dict] = Field(default_factory=list)
    # Scale: {name: factor} relative to that body's own baseline. 1.0 (or
    # omission) is normal size; the engine cancels contacts on a body whose
    # size changed, since a hold is a fact about two bodies at the sizes they
    # were (spatial.contacts_broken_by_scale_change).
    scales: dict[str, float] = Field(default_factory=dict)
    # Containment: {subject: {"in": holder, "mode": ...}}, or a null value to
    # release. A contained body's position is DERIVED from its container's
    # (spatial.derive_contained_positions), so it cannot be somewhere else.
    containment: dict[str, Optional[dict]] = Field(default_factory=dict)
    # Bodily condition {name: {air|stamina|nourishment|injury: 0..1}}. Only
    # ever populated when the survival setting is ON; absent otherwise, which
    # is what keeps the feature free for stories that do not want it.
    vitals: dict[str, Optional[dict]] = Field(default_factory=dict)
    overlays: dict[str, list] = Field(default_factory=dict)
    attire: dict[str, dict] = Field(default_factory=dict)
    cast_changes: list[dict] = Field(default_factory=list)
    world_facts: list = Field(default_factory=list)
    introductions: list[dict] = Field(default_factory=list)
    # Names/details a background presence asserted on an earlier beat that this
    # resolution ADOPTS as true (background_claims.py). Ratifying is the
    # Director's alone -- an unratified claim stays hearsay and expires.
    ratified_claims: list[str] = Field(default_factory=list)
    # Top-level place label, set only when the beat relocates the party to a
    # genuinely different place (DW-1). commit.py's _refresh_relocated_location
    # prefers this over the new room's own name.
    location: str = ""
    time: Optional[dict] = None
    claim_dispositions: list[dict] = Field(default_factory=list)
    # Destruction declaration (DestructionEffect shape -- see its
    # docstring). Declared here so model_dump() keeps it through
    # validation (the zone-field precedent above); commit.py validates it
    # deterministically: one vehicle/building, or a 'region' whose
    # multi-book cascade commit.py enumerates from the lorebook tree.
    destruction: Optional[dict] = None

class AssertedChange(LenientModel):
    """One entry of director_resolve's own changes-asserted manifest: a
    persistent physical change its resolved_event asserts as completed,
    beyond the player's supplied authority_claims. Reconciled against the
    state_diff deterministically (see agents/director.py's seam)."""
    category: str = "other"   # rooms|adjacency|positions|entities|conditions|attire|inventory|cast_changes|time|transit|other
    subject: str = ""         # room id / entity id / character name concerned
    change: str = ""          # one short sentence stating the persistent change

class DirectorResolve(LenientModel):
    resolved_event: str = ""
    summary: str = ""
    dialogue_order: list[str] = Field(default_factory=list)
    dialogue_log: list[DialogueLogEntry] = Field(default_factory=list)
    state_diff: StateDiff = Field(default_factory=StateDiff)
    changes_asserted: list[AssertedChange] = Field(default_factory=list)
    dice: list[dict] = Field(default_factory=list)
    claim_dispositions: list[dict] = Field(default_factory=list)
    fiction_frame: dict[str, Any] = Field(default_factory=dict)
    # Obligation-ledger ops: {op:'open'|'discharge'|'refuse', id, who, what,
    # kind}. Applied deterministically to the world-KV pending_obligations
    # ledger by commit.py's commit_obligations (mirrors standing_intentions).
    obligations: list[dict] = Field(default_factory=list)
    # World-pressure ops (F5 -- THE WORLD ACTS): {op:'open'|'tick'|'hold'|
    # 'resolve', id, subject, note}. Every open pressure on the world-KV
    # world_pressures ledger must be ticked or explicitly held each resolve;
    # commit.py's commit_world_pressure applies the ops deterministically and
    # treats silence as an implicit hold WITH a warning, so an inert world is
    # always a visible choice, never a default (Enterprise: the Array).
    world_pressure: list[dict] = Field(default_factory=list)
    # Player-asserted plot-fact verdicts: {claim_id, claim, subject,
    # verdict:'confirmed'|'contested'|'false', landing}. Audited
    # deterministically in agents/director.py (_audit_fact_adjudications).
    fact_adjudications: list[dict] = Field(default_factory=list)

# ---- Resolve reconciliation (agents/director.py's post-resolve seam) ----

class ReconcileOmission(LenientModel):
    """One persistent, physically consequential change asserted as completed
    in resolved_event prose but not encoded anywhere in the state_diff."""
    category: str = "other"   # rooms|adjacency|positions|entities|conditions|attire|inventory|cast_changes|time|other
    subject: str = ""         # room id / entity id / character name concerned
    change: str = ""          # one short sentence stating the persistent change
    evidence: str = ""        # short verbatim quote from resolved_event
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    _clamp_confidence = validator("confidence", pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, 0.0, 1.0, 0.5)
    )

class ResolveReconcileOutput(LenientModel):
    omissions: list[ReconcileOmission] = Field(default_factory=list)
    notes: str = ""

class ResolveRepairOutput(LenientModel):
    """The Director's own correction delta: a state_diff containing ONLY the
    entries needed to encode the detected omissions (merged additively over
    the original diff by deterministic code -- never applied wholesale)."""
    state_diff: StateDiff = Field(default_factory=StateDiff)
    dispositions: list[dict] = Field(default_factory=list)

class InterpretRepairOutput(LenientModel):
    """The Director's own interpret-side correction delta (the structural
    twin of ResolveRepairOutput, for the seam that runs right after
    director_interpret): ONLY the additional sequence elements / movement /
    generation_requests needed to capture the player declarations the
    original interpretation dropped. Merged ADDITIVELY by deterministic
    code -- existing sequence elements and a declared movement are never
    replaced."""
    sequence: list[dict] = Field(default_factory=list)
    movement: Optional[MovementDecl] = None
    mapping_request: str = ""
    generation_requests: list[dict] = Field(default_factory=list)
    dispositions: list[dict] = Field(default_factory=list)
    notes: str = ""

class NarratorOutput(LenientModel):
    prose: str = ""
    new_specifics: list[str] = Field(default_factory=list)
    text: str = ""

# ---- Character Output ----


def _coerce_evidence_refs(value):
    """Accept a bare string where an EvidenceRef was expected.

    Models routinely cite evidence as a list of strings rather than objects
    ("the sound from the east corridor"), and because BOTH EvidenceRef fields
    have defaults, the object form carries no information a string cannot --
    so rejecting it threw away a whole valid character turn over shape alone.
    Observed live: a character step failed validation with three
    `observations_used.N: value is not a valid dict`, which in an unattended
    run aborts the beat entirely.

    A token that looks like an id ("current", "turn:12:...") lands on
    `event_id`; anything else is prose and lands on `fact`.
    """
    if not isinstance(value, (list, tuple)):
        return value
    out = []
    for item in value:
        if isinstance(item, str):
            text = item.strip()
            if not text:
                continue
            looks_like_id = bool(re.fullmatch(r"[\w:.\-]+", text)) and " " not in text
            out.append({"event_id": text} if looks_like_id else {"fact": text})
        else:
            out.append(item)
    return out


class EvidenceRef(LenientModel):
    event_id: str = ""
    fact: str = ""

class MindHypothesis(LenientModel):
    about_entity: str
    kind: str
    claim: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)

    _coerce_evidence = validator("evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))
    alternatives: list[str] = Field(default_factory=list)

    _coerce_alternatives = validator("alternatives", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_str_list(v)
    )
    _clamp_confidence = validator("confidence", pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, 0.0, 1.0, 0.5)
    )

class RelationshipUpdate(LenientModel):
    target_entity: str
    trust_delta: float = Field(default=0.0, ge=-0.2, le=0.2)
    warmth_delta: float = Field(default=0.0, ge=-0.2, le=0.2)
    fear_delta: float = Field(default=0.0, ge=-0.2, le=0.2)
    trigger_event_ids: list[str] = Field(default_factory=list)

    _clamp_deltas = validator("trust_delta", "warmth_delta", "fear_delta",
                              pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, -0.2, 0.2, 0.0)
    )

class GoalImpact(LenientModel):
    serves: str = "situational"
    impact: float = Field(default=0.0, ge=-1.0, le=1.0)
    certainty: float = Field(default=0.5, ge=0.0, le=1.0)
    agency: str = "none"
    intentionality: float = Field(default=0.0, ge=0.0, le=1.0)
    why: str = ""

    _impact = validator("impact", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, -1.0, 1.0, 0.0)
    )
    _certainty_intentionality = validator(
        "certainty", "intentionality", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.5))


class SomaticImpact(LenientModel):
    pain: float = Field(default=0.0, ge=0.0, le=1.0)
    pleasure: float = Field(default=0.0, ge=0.0, le=1.0)
    why: str = ""

    _axes = validator("pain", "pleasure", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0)
    )


class CharacterAppraisal(LenientModel):
    goal_relevance: str = ""
    expectation: str = ""
    emotion: str = ""
    uncertainty: str = ""
    novelty: float = Field(default=0.0, ge=0.0, le=1.0)
    controllability: float = Field(default=0.5, ge=0.0, le=1.0)
    coping_potential: float = Field(default=0.5, ge=0.0, le=1.0)
    norm_compatibility: float = Field(default=0.0, ge=-1.0, le=1.0)
    self_congruence: float = Field(default=0.0, ge=-1.0, le=1.0)
    intrinsic_pleasantness: float = Field(default=0.0, ge=-1.0, le=1.0)
    somatic_impact: SomaticImpact = Field(default_factory=SomaticImpact)
    goal_impacts: list[GoalImpact] = Field(default_factory=list)

    _unit_axes = validator(
        "novelty", "controllability", "coping_potential",
        pre=True, allow_reuse=True,
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.5))
    _signed_axes = validator(
        "norm_compatibility", "self_congruence", "intrinsic_pleasantness",
        pre=True, allow_reuse=True,
    )(lambda cls, value: _clamp_float(value, -1.0, 1.0, 0.0))

    class Config:
        extra = "allow"


class StressState(LenientModel):
    activation: float = Field(default=0.0, ge=0.0, le=1.0)
    # Aversive component of activation, peak-held on its own so a pleasant
    # drive is never re-read as distress next beat (psychology_runtime).
    strain: float = Field(default=0.0, ge=0.0, le=1.0)
    load: float = Field(default=0.0, ge=0.0, le=1.0)
    coping_mode: str = ""
    overloaded: bool = False

    _clamp_stress = validator(
        "activation", "strain", "load", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0))


class HedonicState(LenientModel):
    pain: float = Field(default=0.0, ge=0.0, le=1.0)
    pleasure: float = Field(default=0.0, ge=0.0, le=1.0)
    source: str = ""
    # Slow integral of unresolved somatic drive, and the character's own
    # declaration that it discharged this beat (psychology_runtime).
    charge: float = Field(default=0.0, ge=0.0, le=1.0)
    saturated: bool = False
    released: bool = False

    _clamp_hedonics = validator(
        "pain", "pleasure", "charge", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0))


class CharacterActiveState(LenientModel):
    mood: Any = ""
    goal: str = ""
    affect: dict = Field(default_factory=dict)
    wants: list[dict] = Field(default_factory=list)
    enacted_want: Optional[int] = None
    suppressed_want: Optional[int] = None
    active_concerns: list[str] = Field(default_factory=list)
    stress: StressState = Field(default_factory=StressState)
    hedonic: HedonicState = Field(default_factory=HedonicState)

    class Config:
        extra = "allow"


def _coerce_candidate_response(value):
    """Accept a candidate `response` expressed as a sequence ELEMENT.

    `response` is the prose of one option the character weighed, but "the
    candidate response" reads just as naturally as the act itself, and models
    emit it structurally:

        "response": {"type": "action", "attempt": "step through the doorway",
                     "observable": "steps forward through the doorway", ...}

    Rejecting that failed the ENTIRE character turn -- the beat was lost, the
    character did nothing, and the only signal was a type error naming a field
    the author never sees. Reduce it to the prose it contains instead. The
    surface (`observable`) is preferred over the intent (`attempt`) because
    these candidates are weighed, not enacted, and the observable is what the
    other machinery would ever show anyone.
    """
    if isinstance(value, dict):
        for key in ("observable", "attempt", "text", "response", "summary",
                    "content", "description"):
            text = str(value.get(key) or "").strip()
            if text:
                return text
        return ""
    if isinstance(value, (list, tuple)):
        parts = [str(v).strip() for v in value if str(v or "").strip()]
        return "; ".join(parts)
    return value


class ResponseCandidate(LenientModel):
    response: str = ""
    serves: list[str] = Field(default_factory=list)
    expected_outcome: str = ""
    risk: float = Field(default=0.0, ge=0.0, le=1.0)
    inhibition: float = Field(default=0.0, ge=0.0, le=1.0)
    norm_conflict: str = ""
    selected: bool = False

    _lists = validator("serves", pre=True, allow_reuse=True)(
        lambda cls, value: _coerce_str_list(value)
    )
    _coerce_response = validator("response", pre=True, allow_reuse=True)(
        lambda cls, value: _coerce_candidate_response(value)
    )
    _candidate_axes = validator(
        "risk", "inhibition", pre=True, allow_reuse=True
    )(lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.0))


class BeliefUpdate(LenientModel):
    belief: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)

    _coerce_evidence = validator("evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))
    operation: str = "reinforce"
    emotional_charge: float = Field(default=0.0, ge=-1.0, le=1.0)

    _confidence = validator("confidence", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, 0.0, 1.0, 0.5)
    )
    _charge = validator("emotional_charge", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, -1.0, 1.0, 0.0)
    )


class AssociationUpdate(LenientModel):
    cue: str
    appraisal_bias: str = ""
    response_tendency: str = ""
    operation: str = "reinforce"
    amount: float = Field(default=0.1, ge=0.0, le=0.25)
    evidence: list[EvidenceRef] = Field(default_factory=list)

    _coerce_evidence = validator("evidence", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))

    _amount = validator("amount", pre=True, allow_reuse=True)(
        lambda cls, value: _clamp_float(value, 0.0, 0.25, 0.1)
    )


class InteractionControl(LenientModel):
    addresses: list[str] = Field(default_factory=list)
    expects_response: bool = False
    yields_floor: bool = True
    urgency: float = Field(default=0.0, ge=0.0, le=1.0)
    conversation_complete_for_me: bool = False

    _clamp_urgency = validator("urgency", pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, 0.0, 1.0, 0.0)
    )

class CharacterOutput(LenientModel):
    observations_used: list[EvidenceRef] = Field(default_factory=list)

    _coerce_observations = validator(
        "observations_used", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_evidence_refs(v))
    appraisal: CharacterAppraisal = Field(default_factory=CharacterAppraisal)
    considered_responses: list[str] = Field(default_factory=list)
    response_candidates: list[ResponseCandidate] = Field(default_factory=list)

    _coerce_considered = validator("considered_responses", pre=True, allow_reuse=True)(
        lambda cls, v: _coerce_str_list(v)
    )
    _coerce_candidates = validator(
        "response_candidates", pre=True, allow_reuse=True
    )(
        lambda cls, value: [
            {"response": item} if isinstance(item, str) else item
            for item in (value if isinstance(value, list) else [])
            if isinstance(item, (str, dict))
        ]
    )
    _coerce_active_state = validator("active_state", pre=True, allow_reuse=True)(
        lambda cls, value: (
            {"mood": value, "goal": ""} if isinstance(value, str) else value
        )
    )
    sequence: list[dict] = Field(default_factory=list)
    speech: Optional[str] = None
    action: Optional[dict] = None
    actions: list[dict] = Field(default_factory=list)
    active_state: Optional[CharacterActiveState] = None
    # Interior depth (all optional; the deterministic floors in affect.py apply
    # at commit). Kept as permissive dicts/lists -- affect.py validates/normalizes.
    intent_ops: list[dict] = Field(default_factory=list)
    manifest: dict = Field(default_factory=dict)
    # A drive rupture proposal -- only valid inside an engine-opened window;
    # commit (validate_drive_shift) decides whether it counts.
    drive_shift: Optional[dict] = None
    belief_updates: list[BeliefUpdate] = Field(default_factory=list)
    association_updates: list[AssociationUpdate] = Field(default_factory=list)

    # `cue` is required and an entry without one names nothing, so it cannot be
    # applied -- but dropping the entry is right where failing the entire
    # character turn is not. Same posture as the dialogue coercion, which drops
    # a line with no quote rather than rejecting the beat.
    _drop_cueless = validator(
        "association_updates", pre=True, allow_reuse=True)(
        lambda cls, v: [
            item for item in (v if isinstance(v, (list, tuple)) else [])
            if not isinstance(item, dict) or str(item.get("cue") or "").strip()
        ] if isinstance(v, (list, tuple)) else v)
    mind_model_updates: list[MindHypothesis] = Field(default_factory=list)
    relationship_updates: list[RelationshipUpdate] = Field(default_factory=list)
    interaction: InteractionControl = Field(default_factory=InteractionControl)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)

    _clamp_salience = validator("salience", pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, 0.0, 1.0, 0.5)
    )

# ---- Mapping ----

class ScenePatch(LenientModel):
    rooms: dict[str, dict] = Field(default_factory=dict)
    entities: dict[str, dict] = Field(default_factory=dict)
    positions: dict[str, str] = Field(default_factory=dict)
    remove_entities: list[str] = Field(default_factory=list)
    remove_rooms: list[str] = Field(default_factory=list)
    remove_adjacent: list[dict] = Field(default_factory=list)

class BookOp(LenientModel):
    """A live, per-turn proposal to create ONE new child lorebook,
    mirroring importers.py's book_ops shape (the existing manual
    reinterpret-lorebook flow) but usable during ordinary play. temp_id
    is this proposal's own scratch handle -- LoreOp.book_id may reference
    it directly so an entry can be filed into a book proposed the SAME
    commit, before it has a real database id yet."""
    op: str = "create"
    temp_id: Optional[str] = None
    name: str = ""
    book_type: str = "general"
    summary: str = ""
    parent_id: Optional[Union[int, str]] = None  # an existing book's int id, or another op's temp_id
    inheritance_mode: str = "inherit"
    scope_world_id: Optional[str] = None
    scope_location_id: Optional[str] = None
    anchor_entity_id: Optional[str] = None

class LoreOp(LenientModel):
    op: str = "create"
    id: Optional[int] = None
    book_id: Optional[Union[int, str]] = None  # an existing book's int id, or a same-turn BookOp's temp_id
    keys: str = ""
    content: str = ""
    category: str = "other"
    title: Optional[str] = None
    knowledge_tag: Optional[str] = None
    knowledge_range: Optional[str] = None
    knowledge_locations: list[str] = Field(default_factory=list)
    importance: Optional[float] = None
    aliases: Optional[list[str]] = None
    scope: Optional[dict[str, Any]] = None
    relations: Optional[dict[str, Any]] = None
    source_notes: Optional[str] = None
    reason: str = ""

class ValidatedFact(LenientModel):
    fact: str = ""
    ok: bool = False
    conflict_with: str = ""

class ValidatedIntroduction(LenientModel):
    who: str = ""
    learns: str = ""
    ok: bool = False
    corrected_learns: Optional[str] = None

class MappingCommit(LenientModel):
    validated: list[ValidatedFact] = Field(default_factory=list)
    lore_ops: list[LoreOp] = Field(default_factory=list)
    book_ops: list[BookOp] = Field(default_factory=list)
    shadow_profile: Optional[str] = None
    offscreen_events: list[dict] = Field(default_factory=list)
    standing_intentions: list[dict] = Field(default_factory=list)
    coherence_notes: list[str] = Field(default_factory=list)
    validated_introductions: list[ValidatedIntroduction] = Field(default_factory=list)

# ---- Lorebook Tree ----

class LorebookDef(LenientModel):
    id: int
    parent_id: Optional[int] = None
    name: str
    book_type: str = "general"
    summary: str = ""
    scope_world_id: Optional[str] = None
    scope_location_id: Optional[str] = None
    inheritance_mode: str = "inherit"
    sort_order: int = 0

class LoreEntryScope(LenientModel):
    world_ids: list[str] = Field(default_factory=list)
    location_ids: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    valid_from: Optional[float] = None
    valid_until: Optional[float] = None

class LoreEntryRelation(LenientModel):
    supersedes_entry_id: Optional[int] = None
    refines_entry_ids: list[int] = Field(default_factory=list)
    contradicts_entry_ids: list[int] = Field(default_factory=list)
    
class PerceptionOutput(LenientModel):
    views: dict[str, Optional[str]] = Field(default_factory=dict)
    # Produced by deterministic post-processing from the final scrubbed view,
    # never trusted from model output. This makes structured perception a
    # projection of the already-audited prose channel, not a second leak path.
    observations: dict[str, list[Observation]] = Field(default_factory=dict)

class MappingStageOutput(LenientModel):
    relevant_books: list[int] = Field(default_factory=list)
    relevant_lore: list[dict] = Field(default_factory=list)
    staged_lore: list[dict] = Field(default_factory=list)
    scene_patch: ScenePatch = Field(default_factory=ScenePatch)
    npc_suggestions: list[dict] = Field(default_factory=list)
    notes: str = ""

# ---- Greeting interpretation (ingest-time, per docs/GREETING_IMPORT_DESIGN.md) ----

class GreetingKnowledgeSeed(LenientModel):
    content: str = ""
    about_entity: str = "self"      # 'self' = the character
    kind: str = "fact"              # fact|goal|relationship|recent_event
    salience: float = Field(default=0.6, ge=0.0, le=1.0)
    # true = the greeting states it openly on the page (player legitimately
    # sees it); false = implied/secret -> routes to CHARACTER memory only.
    revealed_in_prose: bool = False

    _clamp_salience = validator("salience", pre=True, allow_reuse=True)(
        lambda cls, v: _clamp_float(v, 0.0, 1.0, 0.6)
    )

class GreetingInterpret(LenientModel):
    location: str = ""
    time: str = "now"
    scene_description: str = ""
    # freeform dicts (kept tolerant, consumed defensively by the launch merge)
    rooms: dict = Field(default_factory=dict)
    positions: dict = Field(default_factory=dict)
    entities: dict = Field(default_factory=dict)
    attire: dict = Field(default_factory=dict)
    character_state: dict = Field(default_factory=dict)
    knowledge_seeds: list[GreetingKnowledgeSeed] = Field(default_factory=list)
    player_room: str = ""           # room id {{PLAYER}} occupies, if present
    notes: str = ""

# ---- Validation ----

SCHEMA_MAP = {
    "greeting_interpret": GreetingInterpret,
    "director_interpret": DirectorInterpret,
    "director_establish": DirectorEstablish,
    "director_resolve": DirectorResolve,
    "resolve_reconcile": ResolveReconcileOutput,
    "resolve_repair": ResolveRepairOutput,
    "interpret_repair": InterpretRepairOutput,
    "narrator": NarratorOutput,
    "character": CharacterOutput,
    "mapping_stage": MappingStageOutput,
    "perception": PerceptionOutput,
    "mapping_commit": MappingCommit,
    "background_react": BackgroundReactOutput,
    "scene_life": SceneLifeOutput,
    "blurb_mint": BlurbMintOutput,
    "backdrop_prompt": BackdropPromptOutput,
}

def _coerce_int_list(value):
    result = []
    for item in value or []:
        if isinstance(item, int):
            result.append(item)
        elif isinstance(item, str) and item.strip().isdigit():
            result.append(int(item.strip()))
    return result

def _coerce_considered_responses(value):
    """considered_responses is internal deliberation scratch -- nothing
    downstream reads it (it exists for inspecting a character's reasoning
    in the step/variant viewer). Models commonly emit structured entries
    (e.g. {"response": ..., "score": ...}) instead of the declared
    list[str], which used to hard-fail the entire character turn on a
    field with no behavioral effect. Coerce leniently instead.
    """
    if not isinstance(value, list):
        return []

    result = []

    for item in value:
        if isinstance(item, str):
            text = item.strip()
        elif isinstance(item, dict):
            text = str(
                item.get("response") or item.get("text")
                or item.get("option") or item.get("action")
                or item.get("description") or item.get("content") or ""
            ).strip()
            score = item.get("score")
            if text and score is not None:
                text = f"{text} (score: {score})"
        else:
            text = str(item).strip()

        if text:
            result.append(text)

    return result

def _coerce_empty_list_to_dict(value):
    """A field typed as a dict (positions/rooms/entities/conditions/...)
    commonly comes back as `[]` instead of `{}` when a model has nothing
    to report for it -- both read as "empty" to a model, but pydantic
    rejects the type mismatch outright. This crashed a live turn on
    state_diff.conditions being `[]`. director.py already has downstream
    code that defensively re-coerces exactly these fields to `{}` when
    they arrive malformed, but that code is unreachable dead weight if
    strict validation upstream already aborted the call -- so the
    coercion has to happen here, before validation, to actually work.
    Only the unambiguous empty-list case is handled; a genuinely
    non-empty list where a dict was expected is left for validation to
    reject rather than guessed at.
    """
    if value == []:
        return {}
    return value

def _coerce_empty_dict_to_list(value):
    """Inverse of _coerce_empty_list_to_dict, same underlying model behavior:
    a field typed as a list (scene_patch.remove_entities/remove_rooms/
    remove_adjacent) comes back as `{}` instead of `[]` when there's nothing
    to report. Crashed a live turn on exactly this. Only the unambiguous
    empty-dict case is handled; a genuinely non-empty dict where a list was
    expected is left for validation to reject rather than guessed at.
    """
    if value == {}:
        return []
    return value

def _coerce_conditions(value):
    def condition_dict(entry):
        if not isinstance(entry, dict):
            return entry
        entry = dict(entry)
        if "state" in entry and not isinstance(entry.get("state"), dict):
            # Condition consumers require structured state. A scalar must not
            # pass list[dict] validation only to crash those readers later.
            entry["state"] = {}
        return entry

    if value == []:
        return {}
    if isinstance(value, list):
        grouped = {}
        for i, cond in enumerate(value):
            if not isinstance(cond, dict):
                continue
            key = str(cond.get("condition_id") or f"condition_{i}")
            grouped.setdefault(key, []).append(condition_dict(cond))
        return grouped
    if isinstance(value, dict):
        # conditions is dict[str, list[dict]] -- a model sometimes writes a
        # single condition object (or the model crashed a live turn on
        # exactly this: a bare dict) for one key instead of wrapping it in
        # the expected one-item list. Same failure shape as the perception
        # views fix: coerce the leaf rather than reject the whole step.
        fixed = {}
        for key, entry in value.items():
            if isinstance(entry, list):
                fixed[key] = [condition_dict(item) for item in entry]
            elif isinstance(entry, dict):
                fixed[key] = [condition_dict(entry)]
            elif entry is not None:
                fixed[key] = [entry]
        return fixed
    return value

_STATE_DIFF_DICT_FIELDS = (
    "positions", "rooms", "entities", "overlays", "attire", "entity_states",
)

_STATE_DIFF_SIBLING_FIELDS = (
    "remove_entities", "remove_rooms", "remove_adjacent", "conditions",
    "inventory_ops", "contact_ops", "scales", "containment", "vitals",
    "overlays",
    "attire", "cast_changes",
    "world_facts", "introductions", "time", "claim_dispositions",
)

_SCENE_PATCH_SIBLING_FIELDS = (
    "rooms", "positions", "remove_entities", "remove_rooms", "remove_adjacent",
)

def _hoist_misplaced_entity_siblings(container, sibling_fields):
    """Both StateDiff.entities and ScenePatch.entities are dict[str, <entity
    def>] -- keyed by actual in-fiction entity names. Observed live in both
    schemas: a model writes the REST of the parent object's own sibling
    fields (conditions, attire, time, remove_rooms, ...) as if they were
    entries inside `entities`, one nesting level too deep, instead of at
    their correct position as the parent's own top-level keys. A
    flatten-to-string coercion (as used for perception views / narrator
    new_specifics) would be wrong here -- these values need to move up a
    level intact, not collapse into prose. Only hoist keys whose name
    exactly matches a genuine sibling field, and only when the parent
    doesn't already have that field set (never clobber a correctly-placed
    value); an actual entity legitimately named e.g. "time" is not a
    realistic collision risk for either schema's field-name vocabulary.
    """
    entities = container.get("entities")
    if not isinstance(entities, dict):
        return
    for field in sibling_fields:
        if field in entities and field not in container:
            container[field] = entities.pop(field)

def _flatten_view_value(value):
    """perception's views field is typed as {perceiver_id: string|null} -- one
    continuous piece of sensory prose per perceiver. Some models default to
    decomposing that prose into labeled sub-fields instead (e.g.
    {"sight": "...", "sound": "...", "entity_state": {...}}), which reads as
    valid JSON but fails the string type outright and used to abort the whole
    perception step. Rather than depend on every candidate model reliably
    following the "write one string" instruction, flatten any nested
    structure into prose here -- join leaf values in traversal order. Only
    engages when a value isn't already a plain string or null; the common
    case (a compliant model) never touches this path.
    """
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = [_flatten_view_value(v) for v in value.values()]
        return " ".join(p for p in parts if p) or None
    if isinstance(value, list):
        parts = [_flatten_view_value(v) for v in value]
        return " ".join(p for p in parts if p) or None
    return str(value)

# Suffixes a model appends to an entity KEY purely to keep the id distinct
# ("guinan_entity", "turbolift_car_entity"); they are not part of the display
# name, as the model's own successful outputs show ("Guinan", "Turbolift Car").
_ENTITY_KEY_SUFFIX = re.compile(r"[_\-](entity|obj|object|item|node)$", re.I)
# Keys a model reaches for instead of `name`, mirroring the dialogue_log
# alias handling below.
_ENTITY_NAME_ALIASES = ("name", "label", "title", "display_name", "displayName")
# A generated handle rather than a word: long, separator-free, and either pure
# hex or all digits. Live scenes key some entities this way
# ("10ae6b6a11324780") alongside semantic ones ("sake_carafe").
_OPAQUE_ID = re.compile(r"(?:[0-9a-f]{12,}|[0-9]{6,})", re.I)


def _entity_name_from_key(key) -> str:
    """A display name derived from the entity's own dict key.

    `entities` is keyed by id, so the key ALREADY names the thing and models
    routinely omit the redundant `name` -- observed live with glm-latest as
    Director: "state_diff.entities.sake_carafe.name: field required;
    state_diff.entities.computer.name: field required", which failed the whole
    turn. Rejecting an output over a field recoverable from its own key is the
    same over-strictness the dialogue_log repair below already addresses.
    """
    slug = _ENTITY_KEY_SUFFIX.sub("", str(key or "").strip())
    # An opaque generated id ("10ae6b6a11324780") names nothing. Live scenes
    # mix semantic keys with hex ids, and title-casing one produces a display
    # name like "10Ae6B6A11324780" that would then be shown to the player and
    # used as a lookup key. Better to derive nothing and let the caller fall
    # back to the schema default than to invent a garbage name.
    if _OPAQUE_ID.fullmatch(slug):
        return ""
    words = [w for w in re.split(r"[_\-\s]+", slug) if w]
    # Preserve deliberate acronyms (LCARS, EPS) rather than title-casing them.
    return " ".join(w if w.isupper() else w.capitalize() for w in words)


def is_derived_entity_name(key, name, kind=None) -> bool:
    """Would `_fill_entity_names` have invented exactly this name for `key`?

    The recovery below is a repair for a MISSING name, but it is indis-
    tinguishable downstream from a name the model actually chose -- and a
    scene merge cannot tell "the Director renamed this" from "the Director
    sent a state-only diff and validation filled the blank". Live
    (Elevator Adventure branch 41): a pose-only update to `the_doctor_10`
    came back named "The Doctor 10" and overwrote "The Doctor", and
    `tardis_001` overwrote "Blue Police Box" with "Tardis 001". Exposed so
    spatial._merge_entity can refuse a placeholder that would replace a
    real name; an explicit rename to some OTHER string still wins.
    """
    text = str(name or "").strip()
    if not text:
        return False
    candidates = {_entity_name_from_key(key),
                  str(kind or "").strip().title(),
                  "Object"}
    return text in {c for c in candidates if c}


def _fill_entity_names(container) -> None:
    """Give every entity def in `container['entities']` a name, in place."""
    if not isinstance(container, dict):
        return
    entities = container.get("entities")
    if not isinstance(entities, dict):
        return
    for key, entity in entities.items():
        if not isinstance(entity, dict):
            continue
        for alias in _ENTITY_NAME_ALIASES:
            value = entity.get(alias)
            if isinstance(value, str) and value.strip():
                entity["name"] = value.strip()
                break
        else:
            # Preference order: a semantic key names the thing; an opaque
            # generated id names nothing, so fall back to the kind rather than
            # either showing the player "10Ae6B6A11324780" or failing the turn
            # over a missing required field.
            derived = (_entity_name_from_key(key)
                       or str(entity.get("kind") or "").strip().title()
                       or "Object")
            entity["name"] = derived


def preprocess_llm_output(step_key: str, raw: dict) -> dict:
    if not isinstance(raw, dict):
        return {}

    result = dict(raw)

    if step_key == "mapping_stage":
        patch = result.get("scene_patch")
        if isinstance(patch, dict):
            _hoist_misplaced_entity_siblings(patch, _SCENE_PATCH_SIBLING_FIELDS)
            for field in ("remove_entities", "remove_rooms", "remove_adjacent"):
                if field in patch:
                    patch[field] = _coerce_empty_dict_to_list(patch[field])
            # ScenePatch.entities is untyped so a missing name does not fail
            # validation here -- but it lands in the scene, where readers key
            # display name -> entity id (commit.track_background_presences,
            # agents/background._name_to_entity_id). A nameless entity is
            # invisible to both.
            _fill_entity_names(patch)

    if step_key == "perception":
        # Observations are a deterministic projection of the final scrubbed
        # view. Model-authored copies are discarded before validation so a
        # malformed or malicious second channel can neither fail the step nor
        # smuggle information past the prose gates.
        result.pop("observations", None)
        views = result.get("views")
        if isinstance(views, dict):
            result["views"] = {
                k: _flatten_view_value(v) for k, v in views.items()
            }

    if step_key == "narrator":
        # new_specifics is list[str] -- proper nouns/hard facts the
        # narrator coined this turn. Same over-structuring failure mode as
        # perception's views: a model occasionally reports one as a nested
        # object instead of a bare string. Flatten rather than reject.
        specifics = result.get("new_specifics")
        if isinstance(specifics, list):
            result["new_specifics"] = [
                flat for flat in (_flatten_view_value(x) for x in specifics)
                if flat
            ]

    if step_key in ("director_resolve", "director_establish", "resolve_repair"):
        target = result
        if step_key in ("director_resolve", "resolve_repair"):
            state_diff = result.get("state_diff")
            target = state_diff if isinstance(state_diff, dict) else None
            if target is not None:
                _hoist_misplaced_entity_siblings(target, _STATE_DIFF_SIBLING_FIELDS)
            if target is not None and "conditions" in target:
                target["conditions"] = _coerce_conditions(target["conditions"])
        if isinstance(target, dict):
            for field in _STATE_DIFF_DICT_FIELDS:
                if field in target:
                    target[field] = _coerce_empty_list_to_dict(target[field])
            # SceneEntityDef.name is required but the dict key already carries
            # it; recover rather than fail the turn.
            _fill_entity_names(target)
    
    if "speech_volume" in result:
        result["speech_volume"] = normalize_speech_volume(
            result.get("speech_volume")
        )

    sequence = result.get("sequence")
    if isinstance(sequence, list):
        cleaned_sequence = []

        for event in sequence:
            if not isinstance(event, dict):
                continue

            event = dict(event)

            if event.get("type") == "speech":
                event["volume"] = normalize_speech_volume(
                    event.get("volume")
                )

            cleaned_sequence.append(event)

        result["sequence"] = cleaned_sequence

    if "considered_responses" in result:
        result["considered_responses"] = _coerce_considered_responses(
            result.get("considered_responses")
        )

    dialogue_log = result.get("dialogue_log")
    if isinstance(dialogue_log, list):
        cleaned_dialogue = []

        for line in dialogue_log:
            # A weak model may emit a bare "Speaker: quote" string instead of
            # an object; dropping it (as we used to) silently erased the beat's
            # dialogue, leaving DIALOGUE FIDELITY nothing to protect.
            if isinstance(line, str):
                text = line.strip()
                if not text:
                    continue
                # X14: preserve concealment markers a weak model may embed
                # in a string line (e.g. "[concealed] Sarah: I know").
                line_visibility = "overt"
                m = re.match(r'^\s*\[(concealed|overt)\]\s*(.*)', text, re.IGNORECASE)
                if m:
                    line_visibility = m.group(1).lower()
                    text = m.group(2)
                if ":" in text and len(text.split(":", 1)[0]) <= 60:
                    spk, quote = text.split(":", 1)
                    line = {"speaker": spk.strip(), "exact_quote": quote.strip().strip('"\'')}
                else:
                    line = {"speaker": "unknown", "exact_quote": text}
                line["visibility"] = line_visibility
            if not isinstance(line, dict):
                continue

            line = dict(line)
            # Alias common key variants a model reaches for onto the schema's
            # required exact_quote / speaker (parallel to the volume path).
            if not line.get("exact_quote"):
                for alias in ("quote", "text", "line", "content", "utterance"):
                    if line.get(alias):
                        line["exact_quote"] = line[alias]
                        break
            if not line.get("speaker"):
                line["speaker"] = line.get("name") or line.get("who") or "unknown"
            line["volume"] = normalize_speech_volume(line.get("volume"))
            # X14: normalize visibility so a concealed line survives the
            # coercion intact. Without this, visibility from the original
            # entry is silently dropped for string lines and unrecognized
            # variants on dict lines, defaulting to "overt" downstream.
            vis = str(line.get("visibility") or "").strip().lower()
            if vis in ("concealed", "hidden", "secret"):
                line["visibility"] = "concealed"
            else:
                line.setdefault("visibility", "overt")
            if not isinstance(line.get("conceal_from"), list):
                line["conceal_from"] = []
            if str(line.get("exact_quote") or "").strip():
                cleaned_dialogue.append(line)

        result["dialogue_log"] = cleaned_dialogue

    if step_key == "director_interpret":
        flow_raw = result.get("flow")
        flow = flow_raw if isinstance(flow_raw, dict) else {}

        reactors = flow.get("reactors")
        if not isinstance(reactors, list):
            reactors = []

        addressed_to = flow.get("addressed_to")
        if not isinstance(addressed_to, list):
            addressed_to = []

        tom_triggers = flow.get("tom_triggers")
        if not isinstance(tom_triggers, list):
            tom_triggers = []

        resolution_flags = flow.get("resolution_flags")
        if not isinstance(resolution_flags, dict):
            resolution_flags = {}

        dice = flow.get("dice")
        if not isinstance(dice, list):
            dice = []

        generation_requests = flow.get("generation_requests")
        if not isinstance(generation_requests, list):
            generation_requests = []

        authority_claims = flow.get("authority_claims")
        if not isinstance(authority_claims, list):
            authority_claims = []

        fiction_frame = flow.get("fiction_frame")
        if not isinstance(fiction_frame, dict):
            fiction_frame = {}

        flow["reactor_refs"] = list(reactors)
        flow["tom_trigger_refs"] = list(tom_triggers)
        # Raw refs preserved BEFORE int coercion: a name string here is the
        # only way the director can address an UNREGISTERED background
        # presence (commit.pick_background_reactors forces it to answer).
        flow["addressed_to_refs"] = list(addressed_to)
        flow["reactors"] = _coerce_int_list(reactors)
        flow["tom_triggers"] = _coerce_int_list(tom_triggers)
        flow["addressed_to"] = _coerce_int_list(addressed_to)
        flow["resolution_flags"] = resolution_flags
        flow["dice"] = [
            item for item in dice if isinstance(item, dict)
        ]
        flow["generation_requests"] = [
            item for item in generation_requests
            if isinstance(item, dict)
        ]
        flow["authority_claims"] = [
            item for item in authority_claims
            if isinstance(item, dict)
        ]
        flow["fiction_frame"] = fiction_frame

        result["flow"] = flow

        # Extra players get the same speech-volume normalization the primary
        # player's sequence already gets (schemas.py above) -- otherwise a
        # co-player's out-of-enum volume either hard-fails or survives raw and
        # is read as inaudible by hear_level. Also tolerate other_players:null.
        others = result.get("other_players")
        if not isinstance(others, dict):
            result["other_players"] = {}
        else:
            for pid, decl in list(others.items()):
                if not isinstance(decl, dict):
                    continue
                if "speech_volume" in decl:
                    decl["speech_volume"] = normalize_speech_volume(decl.get("speech_volume"))
                seq = decl.get("sequence")
                if isinstance(seq, list):
                    for ev in seq:
                        if isinstance(ev, dict) and ev.get("type") == "speech":
                            ev["volume"] = normalize_speech_volume(ev.get("volume"))

    return result

def validate_llm_output(step_key: str, raw: dict) -> tuple[dict, list[str]]:
    model_cls = SCHEMA_MAP.get(step_key)
    if not isinstance(raw, dict):
        raw = {}
    prepared = preprocess_llm_output(step_key, raw)
    if not model_cls:
        return prepared, []
    try:
        model = _validate(model_cls, prepared)
        return _dump(model), []
    except ValidationError as exc:
        warnings = [f"Schema validation warning: {len(exc.errors())} errors"]
        for error in exc.errors()[:5]:
            location = ".".join(str(part) for part in error.get("loc", []))
            warnings.append(f"  {location}: {error.get('msg', '')}")
        if step_key == "director_interpret":
            flow = prepared.get("flow")
            if not isinstance(flow, dict):
                flow = {}
            if not isinstance(flow.get("resolution_flags"), dict):
                flow["resolution_flags"] = {}
            for key in ("reactors", "addressed_to", "tom_triggers", "dice",
                        "generation_requests", "authority_claims"):
                if not isinstance(flow.get(key), list):
                    flow[key] = []
            if not isinstance(flow.get("fiction_frame"), dict):
                flow["fiction_frame"] = {}
            prepared["flow"] = flow
        return prepared, warnings
        
@dataclass
class ValidationReport:
    valid: bool
    output: dict
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

OUTPUT_EXAMPLES = {
    "director_interpret": {
        "kind": "mixed",
        "sequence": [],
        "speech": None,
        "speech_volume": "normal",
        "private_thought": None,
        "action": None,
        "actions": [],
        "movement": None,
        "location_query": None,
        "flow": {
            "reactors": [],
            "addressed_to": [],
            "dialogue_mode": False,
            "needs_mapping": False,
            "mapping_request": "",
            "dice": [],
            "tom_triggers": [],
            "resolution_flags": {
                "contested": False,
                "possible_reactors": [],
            },
            "authority_claims": [],
            "fiction_frame": {},
            "generation_requests": [],
        },
        "notes": "",
    },
    "director_establish": {
        "location": "",
        "time": "now",
        "scene_description": "",
        "rooms": {},
        "entities": {},
        "positions": {},
        "attire": {},
        "entity_states": {},
        "sensory_events": [],
        "world_facts": [],
        "fiction_frame": {},
        "simulation_clock": {
            "elapsed_seconds": 0.0,
            "display": "now",
            "time_scale": "scene",
        },
        "opening": "",
    },
    "director_resolve": {
        "resolved_event": "",
        "summary": "",
        "dialogue_order": [],
        "dialogue_log": [],
        "state_diff": {
            "positions": {},
            "rooms": {},
            "entities": {},
            "remove_entities": [],
            "remove_rooms": [],
            "remove_adjacent": [],
            "conditions": {},
            "inventory_ops": [],
            "overlays": {},
            "attire": {},
            "cast_changes": [],
            "world_facts": [],
            "introductions": [],
            "time": None,
            "claim_dispositions": [],
        },
        "changes_asserted": [
            {"category": "adjacency", "subject": "vault_door",
             "change": "The vault door is sealed shut."},
        ],
        "dice": [],
        "fiction_frame": {},
        "obligations": [
            {"op": "open", "who": "Merek", "what": "deliver the survey "
             "report Captain Hale demanded", "kind": "demand"},
        ],
        "fact_adjudications": [
            {"claim_id": "claim:0:event", "claim": "the crew on deck 12 "
             "are dead", "subject": "deck 12 crew", "verdict": "confirmed",
             "landing": "the medic confirms the deaths on-page"},
        ],
    },
    "character": {
        "observations_used": [],
        "appraisal": {},
        "considered_responses": [],
        "response_candidates": [],
        "sequence": [],
        "active_state": {},
        "belief_updates": [],
        "association_updates": [],
        "mind_model_updates": [],
        "relationship_updates": [],
        "interaction": {
            "addresses": [],
            "expects_response": False,
            "yields_floor": True,
            "urgency": 0.0,
            "conversation_complete_for_me": False,
        },
        "salience": 0.5,
    },
    "perception": {
        "views": {},
        "observations": {},
    },
    "mapping_stage": {
        "relevant_books": [],
        "relevant_lore": [],
        "staged_lore": [],
        "scene_patch": {
            "rooms": {},
            "entities": {},
            "positions": {},
            "remove_entities": [],
            "remove_rooms": [],
            "remove_adjacent": [],
        },
        "npc_suggestions": [],
        "notes": "",
    },
    "narrator": {
        "prose": "",
        "new_specifics": [],
    },
    "mapping_commit": {
        "validated": [],
        "lore_ops": [],
        "book_ops": [],
        "shadow_profile": None,
        "offscreen_events": [],
        "standing_intentions": [],
        "coherence_notes": [],
        "validated_introductions": [],
    },
    # Without an example, output_example() returned {} and the repair prompt
    # steered a compliant model to return {} -- which validates (all defaults),
    # silently swallowing the reaction. This shows the real shape.
    "background_react": {
        "reacts": True,
        "dialogue_log_entry": {
            "speaker": "the barkeep",
            "exact_quote": "Aye, coming right up.",
            "volume": "normal",
            "intended_target": "",
            "tone": "gruff",
        },
        "action": "wipes down the counter",
    },
    "scene_life": {
        "entries": [
            {
                "name": "Hettie Crawe",
                "speech": {
                    "exact_quote": "Coin first. I've heard the songs.",
                    "volume": "normal",
                    "intended_target": "Bran",
                    "tone": "flat",
                },
                "action": "sets the tankard down harder than needed",
            },
            {
                "name": "Old Sarn",
                "speech": None,
                "action": "turns a little on his stool to watch",
            },
        ],
    },
    "blurb_mint": {
        "blurbs": [
            {
                "name": "Hettie Crawe",
                "manner": "short sentences, never says please, prices everything",
                "trait": "convinced adventurers always leave without paying",
                "tell": "wipes the same clean spot on the bar",
                "look": "forearms like a smith's, grey braid pinned up",
            },
        ],
    },
    "greeting_interpret": {
        "location": "a dim tavern",
        "time": "night",
        "scene_description": "A low-ceilinged tavern, rain against the shutters.",
        "rooms": {"tavern": {"name": "The Tavern", "desc": "Low-ceilinged, smoke-hazed.",
                              "adjacent": []}},
        "positions": {"Kara": "tavern", "{{PLAYER}}": "tavern"},
        "entities": {},
        "attire": {"Kara": {"summary": "a travel-worn cloak"}},
        "character_state": {"mood": "wary", "goal": "size up the newcomer"},
        "knowledge_seeds": [
            {"content": "I have been waiting here for three nights for a courier.",
             "about_entity": "self", "kind": "recent_event", "salience": 0.7,
             "revealed_in_prose": False},
        ],
        "player_room": "tavern",
        "notes": "",
    },
    "resolve_reconcile": {
        "omissions": [
            {"category": "adjacency",
             "subject": "vault_door",
             "change": "The vault door is now sealed shut.",
             "evidence": "the vault door grinds shut and seals",
             "confidence": 0.9},
        ],
        "notes": "",
    },
    "resolve_repair": {
        "state_diff": {
            "positions": {},
            "rooms": {},
            "entities": {},
            "remove_entities": [],
            "remove_rooms": [],
            "remove_adjacent": [],
            "conditions": {},
            "inventory_ops": [],
            "overlays": {},
            "attire": {},
            "cast_changes": [],
            "world_facts": [],
            "introductions": [],
            "time": None,
            "claim_dispositions": [],
        },
        "dispositions": [
            {"subject": "vault_door", "status": "encoded", "reason": ""},
        ],
    },
    "interpret_repair": {
        "sequence": [
            {"type": "action", "raw_text": "duck into the armory",
             "attempt": "duck into the armory", "commitment": "asserted",
             "verb": "enter", "targets": [], "asserted_effects": []},
        ],
        "movement": {"to_room": "armory", "why": "player declared entering",
                     "mover": "self"},
        "mapping_request": "Player enters the armory — generate its layout.",
        "generation_requests": [
            {"kind": "player_declaration", "subject": "a rifle grabbed from "
             "the armory rack", "constraints": [], "urgency": "now"},
        ],
        "dispositions": [
            {"subject": "duck into the armory and grab a rifle",
             "status": "captured", "reason": ""},
        ],
        "notes": "",
    },
}

def output_example(step_key: str) -> dict:
    return OUTPUT_EXAMPLES.get(step_key, {})

def semantic_output_errors(
    step_key: str,
    output: dict,
    *,
    source_payload: dict | None = None,
) -> list[str]:
    errors = []
    source_payload = source_payload or {}

    if step_key == "director_interpret":
        raw_input = str(
            source_payload.get("player_raw_input") or ""
        ).strip()

        if raw_input and not output.get("sequence"):
            errors.append(
                "sequence is empty despite nonempty player input"
            )

        if not isinstance(output.get("flow"), dict):
            errors.append("flow must be an object")

    elif step_key == "director_establish":
        if not output.get("rooms"):
            errors.append("rooms is empty")

        if not output.get("positions"):
            errors.append("positions is empty")

    elif step_key == "director_resolve":
        if not str(output.get("resolved_event") or "").strip():
            errors.append("resolved_event is empty")

        if not isinstance(output.get("state_diff"), dict):
            errors.append("state_diff must be an object")

    elif step_key == "character":
        if not isinstance(output.get("sequence"), list):
            errors.append("sequence must be an array")

        if not isinstance(output.get("interaction"), dict):
            errors.append("interaction must be an object")

    elif step_key == "perception":
        perceivers = source_payload.get("perceivers") or []
        views = output.get("views")

        if not isinstance(views, dict):
            errors.append("views must be an object")
        else:
            expected = {
                str(item.get("id"))
                for item in perceivers
                if isinstance(item, dict)
                and item.get("id") is not None
            }

            missing = sorted(
                expected - {str(key) for key in views}
            )

            if missing:
                errors.append(
                    "views is missing perceiver IDs: "
                    + ", ".join(missing)
                )

    elif step_key == "mapping_stage":
        if not isinstance(output.get("scene_patch"), dict):
            errors.append("scene_patch must be an object")

    elif step_key == "narrator":
        if not str(output.get("prose") or "").strip():
            errors.append("prose is empty")

    return errors

def validate_llm_output_strict(
    step_key: str,
    raw: dict,
    *,
    source_payload: dict | None = None,
) -> ValidationReport:
    if not isinstance(raw, dict):
        return ValidationReport(
            valid=False,
            output={},
            errors=["Output is not a JSON object"],
        )

    prepared = preprocess_llm_output(step_key, raw)
    model_cls = SCHEMA_MAP.get(step_key)

    if model_cls is None:
        return ValidationReport(
            valid=True,
            output=prepared,
        )

    try:
        model = _validate(model_cls, prepared)
        output = _dump(model)
    except ValidationError as exc:
        errors = []

        for error in exc.errors():
            location = ".".join(
                str(part)
                for part in error.get("loc", [])
            )
            message = error.get("msg", "invalid value")
            errors.append(f"{location}: {message}")

        return ValidationReport(
            valid=False,
            output=prepared,
            errors=errors,
        )

    semantic_errors = semantic_output_errors(
        step_key,
        output,
        source_payload=source_payload,
    )

    return ValidationReport(
        valid=not semantic_errors,
        output=output,
        errors=semantic_errors,
    )
