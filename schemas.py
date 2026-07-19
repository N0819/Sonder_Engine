# schemas.py
"""Pydantic schemas for all pipeline and world-state structures."""

from pydantic import BaseModel, Field, ValidationError
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Union

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

class GenreProfile(BaseModel):
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

class CausalRegime(BaseModel):
    regime_id: str
    scope: str = "default"
    priority: int = 0
    rules: dict[str, Any] = Field(default_factory=dict)

class FictionModel(BaseModel):
    genre: dict[str, Any] = Field(default_factory=dict)
    ontology: dict[str, Any] = Field(default_factory=dict)
    causal_regimes: list[dict] = Field(default_factory=list)
    scale_rules: dict[str, Any] = Field(default_factory=dict)
    abstraction_rules: dict[str, Any] = Field(default_factory=dict)
    narrative_conventions: list[dict] = Field(default_factory=list)
    epistemic_rules: list[dict] = Field(default_factory=list)
    content_rules: list[dict] = Field(default_factory=list)

class FictionFrame(BaseModel):
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

class ScenePressure(BaseModel):
    threat: float = 0.0
    mystery: float = 0.0
    social: float = 0.0
    environmental: float = 0.0
    recent_release: float = 0.0

# ---- Time ----

class SimulationClock(BaseModel):
    elapsed_seconds: float = 0.0
    calendar: Optional[dict[str, Any]] = None
    display: str = "now"
    time_scale: str = "scene"

class TimeDiff(BaseModel):
    start_seconds: float = 0.0
    duration_seconds: float = 0.0
    end_seconds: float = 0.0
    mode: str = "action"
    explicit: bool = False
    display_advance: str = ""

class TemporalProperties(BaseModel):
    rate_numerator: float = 1.0
    rate_denominator: float = 1.0
    offset_seconds: float = 0.0
    causal_ordering: str = "global"
    supports_time_travel: bool = False

# ---- Actions ----

class DurationHint(BaseModel):
    value: Optional[float] = None
    unit: str = "seconds"
    explicit: bool = False

class IntendedEffect(BaseModel):
    target_id: Optional[str] = None
    kind: str
    details: dict[str, Any] = Field(default_factory=dict)

class ActionElement(BaseModel):
    type: str = "action"
    event_id: str = ""
    actor_id: str = ""
    raw_text: str = ""
    attempt: str = ""
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

class SpeechElement(BaseModel):
    type: str = "speech"
    text: str
    volume: SpeechVolume = SpeechVolume.normal
    tone: str = ""
    visibility: ActionVisibility = ActionVisibility.overt
    conceal_from: list[str] = Field(default_factory=list)

class DiceSpec(BaseModel):
    actor: str
    attempt: str
    ability: str
    difficulty: str = "medium"

class ResolutionCheck(BaseModel):
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

class MovementDecl(BaseModel):
    to_room: str
    why: str = ""

# ---- Authority ----

class AuthorityClaim(BaseModel):
    claim_id: str = ""
    scope: str = "action"
    subject_id: Optional[str] = None
    predicate: str = ""
    value: Any = None
    commitment: str = "asserted"
    source_text: str = ""

class ClaimDisposition(BaseModel):
    claim_id: str = ""
    status: str = "realized"
    realized_event_ids: list[str] = Field(default_factory=list)
    notes: str = ""

class GenerationRequest(BaseModel):
    kind: str
    subject: str = ""
    location_id: Optional[str] = None
    constraints: list[str] = Field(default_factory=list)
    evidence_event_ids: list[str] = Field(default_factory=list)
    urgency: str = "now"

# ---- Flow ----

class FlowPlan(BaseModel):
    reactors: list[int] = Field(default_factory=list)
    reactor_refs: list[Any] = Field(default_factory=list)
    addressed_to: list[int] = Field(default_factory=list)
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

# ---- Director Interpret ----

class OtherPlayerInterpret(BaseModel):
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

class DirectorInterpret(BaseModel):
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
    # Additive multiplayer support: interpretations for any additional
    # human players declaring in this same beat, keyed by persona_id (as a
    # string, since JSON object keys are always strings). Empty for every
    # single-player chat -- nothing here changes behavior unless
    # ctx.extra_players is non-empty.
    other_players: dict[str, OtherPlayerInterpret] = Field(default_factory=dict)

# ---- Scene Entities ----

class SceneEntityDef(BaseModel):
    name: str
    kind: str = "object"
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    portable: bool = False
    container: bool = False
    interior_rooms: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)

class RoomDef(BaseModel):
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

class WorldEntity(BaseModel):
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

class AggregateEntity(BaseModel):
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

class ComponentState(BaseModel):
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

class WorldDef(BaseModel):
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

class LocationDef(BaseModel):
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

class SpatialZone(BaseModel):
    zone_id: str
    location_id: str
    name: str
    zone_kind: str = "area"
    neighbors: list[dict] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)

class TransitEdge(BaseModel):
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

class StrategicPlacement(BaseModel):
    subject_id: str
    zone_id: str
    posture: str = ""
    range_band_to: dict[str, str] = Field(default_factory=dict)
    heading: Optional[str] = None
    altitude_band: Optional[str] = None
    depth_band: Optional[str] = None

# ---- Conditions and Scheduling ----

class PersistentCondition(BaseModel):
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

class ScheduledEvent(BaseModel):
    event_id: str
    due_at_seconds: float
    kind: str
    subject_ids: list[str] = Field(default_factory=list)
    location_id: Optional[str] = None
    trigger: dict[str, Any] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)
    source_event_id: Optional[str] = None
    status: str = "pending"

class DestructionEffect(BaseModel):
    effect_id: str
    source_event_id: str
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

class Engagement(BaseModel):
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

class InventoryOp(BaseModel):
    op: str
    object_id: str
    from_id: Optional[str] = None
    to_id: Optional[str] = None
    relation: str = "held_by"
    details: dict[str, Any] = Field(default_factory=dict)

class ObjectStatePatch(BaseModel):
    object_id: str
    set_fields: dict[str, Any] = Field(default_factory=dict)
    add_tags: list[str] = Field(default_factory=list)
    remove_tags: list[str] = Field(default_factory=list)

# ---- Reactions and Perception ----

class ReactionDeclaration(BaseModel):
    actor_id: str
    trigger_event_ids: list[str] = Field(default_factory=list)
    sequence: list[dict] = Field(default_factory=list)
    urgency: float = 0.0

class EventAtom(BaseModel):
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

class Observation(BaseModel):
    observation_id: str
    perceiver_id: str
    source_atom_id: str
    channel: str
    fidelity: str
    observed: dict[str, Any] = Field(default_factory=dict)

class SensorChannel(BaseModel):
    channel_id: str
    owner_id: str
    kind: str
    range: str
    resolution: str
    latency_seconds: float = 0.0
    coverage: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)

class ActorDef(BaseModel):
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

class AttireState(BaseModel):
    wearing: list[str] = Field(default_factory=list)
    state: list[str] = Field(default_factory=list)

class InitialEntityState(BaseModel):
    posture: str = ""
    activity: str = ""
    held_items: list[str] = Field(default_factory=list)
    visible_conditions: list[str] = Field(default_factory=list)

class DirectorEstablish(BaseModel):
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

class DialogueLogEntry(BaseModel):
    speaker: str
    exact_quote: str
    volume: SpeechVolume = SpeechVolume.normal
    intended_target: Optional[str] = None
    tone: str = ""
    visibility: ActionVisibility = ActionVisibility.overt
    conceal_from: list[str] = Field(default_factory=list)

class BackgroundReactOutput(BaseModel):
    reacts: bool = False
    dialogue_log_entry: Optional[DialogueLogEntry] = None
    action: str = ""

class StateDiff(BaseModel):
    positions: dict[str, str] = Field(default_factory=dict)
    rooms: dict[str, RoomDef] = Field(default_factory=dict)
    entities: dict[str, SceneEntityDef] = Field(default_factory=dict)
    remove_entities: list[str] = Field(default_factory=list)
    remove_rooms: list[str] = Field(default_factory=list)
    remove_adjacent: list[dict] = Field(default_factory=list)
    conditions: dict[str, list[dict]] = Field(default_factory=dict)
    inventory_ops: list[dict] = Field(default_factory=list)
    overlays: dict[str, list] = Field(default_factory=dict)
    attire: dict[str, dict] = Field(default_factory=dict)
    cast_changes: list[dict] = Field(default_factory=list)
    world_facts: list = Field(default_factory=list)
    introductions: list[dict] = Field(default_factory=list)
    time: Optional[dict] = None
    claim_dispositions: list[dict] = Field(default_factory=list)

class DirectorResolve(BaseModel):
    resolved_event: str = ""
    summary: str = ""
    dialogue_order: list[str] = Field(default_factory=list)
    dialogue_log: list[DialogueLogEntry] = Field(default_factory=list)
    state_diff: StateDiff = Field(default_factory=StateDiff)
    dice: list[dict] = Field(default_factory=list)
    claim_dispositions: list[dict] = Field(default_factory=list)
    fiction_frame: dict[str, Any] = Field(default_factory=dict)

class NarratorOutput(BaseModel):
    prose: str = ""
    new_specifics: list[str] = Field(default_factory=list)
    text: str = ""

# ---- Character Output ----

class EvidenceRef(BaseModel):
    event_id: str = ""
    fact: str = ""

class MindHypothesis(BaseModel):
    about_entity: str
    kind: str
    claim: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    evidence: list[EvidenceRef] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)

class RelationshipUpdate(BaseModel):
    target_entity: str
    trust_delta: float = Field(default=0.0, ge=-0.2, le=0.2)
    warmth_delta: float = Field(default=0.0, ge=-0.2, le=0.2)
    fear_delta: float = Field(default=0.0, ge=-0.2, le=0.2)
    trigger_event_ids: list[str] = Field(default_factory=list)

class InteractionControl(BaseModel):
    addresses: list[str] = Field(default_factory=list)
    expects_response: bool = False
    yields_floor: bool = True
    urgency: float = Field(default=0.0, ge=0.0, le=1.0)
    conversation_complete_for_me: bool = False

class CharacterOutput(BaseModel):
    observations_used: list[EvidenceRef] = Field(default_factory=list)
    appraisal: dict = Field(default_factory=dict)
    considered_responses: list[str] = Field(default_factory=list)
    sequence: list[dict] = Field(default_factory=list)
    speech: Optional[str] = None
    action: Optional[dict] = None
    actions: list[dict] = Field(default_factory=list)
    active_state: dict = Field(default_factory=dict)
    mind_model_updates: list[MindHypothesis] = Field(default_factory=list)
    relationship_updates: list[RelationshipUpdate] = Field(default_factory=list)
    interaction: InteractionControl = Field(default_factory=InteractionControl)
    salience: float = Field(default=0.5, ge=0.0, le=1.0)

# ---- Mapping ----

class ScenePatch(BaseModel):
    rooms: dict[str, dict] = Field(default_factory=dict)
    entities: dict[str, dict] = Field(default_factory=dict)
    positions: dict[str, str] = Field(default_factory=dict)
    remove_entities: list[str] = Field(default_factory=list)
    remove_rooms: list[str] = Field(default_factory=list)
    remove_adjacent: list[dict] = Field(default_factory=list)

class BookOp(BaseModel):
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

class LoreOp(BaseModel):
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

class ValidatedFact(BaseModel):
    fact: str = ""
    ok: bool = False
    conflict_with: str = ""

class ValidatedIntroduction(BaseModel):
    who: str = ""
    learns: str = ""
    ok: bool = False
    corrected_learns: Optional[str] = None

class MappingCommit(BaseModel):
    validated: list[ValidatedFact] = Field(default_factory=list)
    lore_ops: list[LoreOp] = Field(default_factory=list)
    book_ops: list[BookOp] = Field(default_factory=list)
    shadow_profile: Optional[str] = None
    offscreen_events: list[dict] = Field(default_factory=list)
    standing_intentions: list[dict] = Field(default_factory=list)
    coherence_notes: list[str] = Field(default_factory=list)
    validated_introductions: list[ValidatedIntroduction] = Field(default_factory=list)

# ---- Lorebook Tree ----

class LorebookDef(BaseModel):
    id: int
    parent_id: Optional[int] = None
    name: str
    book_type: str = "general"
    summary: str = ""
    scope_world_id: Optional[str] = None
    scope_location_id: Optional[str] = None
    inheritance_mode: str = "inherit"
    sort_order: int = 0

class LoreEntryScope(BaseModel):
    world_ids: list[str] = Field(default_factory=list)
    location_ids: list[str] = Field(default_factory=list)
    entity_ids: list[str] = Field(default_factory=list)
    valid_from: Optional[float] = None
    valid_until: Optional[float] = None

class LoreEntryRelation(BaseModel):
    supersedes_entry_id: Optional[int] = None
    refines_entry_ids: list[int] = Field(default_factory=list)
    contradicts_entry_ids: list[int] = Field(default_factory=list)
    
class PerceptionOutput(BaseModel):
    views: dict[str, Optional[str]] = Field(default_factory=dict)

class MappingStageOutput(BaseModel):
    relevant_books: list[int] = Field(default_factory=list)
    relevant_lore: list[dict] = Field(default_factory=list)
    staged_lore: list[dict] = Field(default_factory=list)
    scene_patch: ScenePatch = Field(default_factory=ScenePatch)
    npc_suggestions: list[dict] = Field(default_factory=list)
    notes: str = ""

# ---- Validation ----

SCHEMA_MAP = {
    "director_interpret": DirectorInterpret,
    "director_establish": DirectorEstablish,
    "director_resolve": DirectorResolve,
    "narrator": NarratorOutput,
    "character": CharacterOutput,
    "mapping_stage": MappingStageOutput,
    "perception": PerceptionOutput,
    "mapping_commit": MappingCommit,
    "background_react": BackgroundReactOutput,
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
    if value == []:
        return {}
    if isinstance(value, list):
        grouped = {}
        for i, cond in enumerate(value):
            if not isinstance(cond, dict):
                continue
            key = str(cond.get("condition_id") or f"condition_{i}")
            grouped.setdefault(key, []).append(cond)
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
                fixed[key] = entry
            elif isinstance(entry, dict):
                fixed[key] = [entry]
            elif entry is not None:
                fixed[key] = [entry]
        return fixed
    return value

_STATE_DIFF_DICT_FIELDS = (
    "positions", "rooms", "entities", "overlays", "attire", "entity_states",
)

_STATE_DIFF_SIBLING_FIELDS = (
    "remove_entities", "remove_rooms", "remove_adjacent", "conditions",
    "inventory_ops", "overlays", "attire", "cast_changes", "world_facts",
    "introductions", "time", "claim_dispositions",
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

    if step_key == "perception":
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

    if step_key in ("director_resolve", "director_establish"):
        target = result
        if step_key == "director_resolve":
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
            if not isinstance(line, dict):
                continue

            line = dict(line)
            line["volume"] = normalize_speech_volume(
                line.get("volume")
            )
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
        "dice": [],
        "fiction_frame": {},
    },
    "character": {
        "observations_used": [],
        "appraisal": {},
        "considered_responses": [],
        "sequence": [],
        "active_state": {},
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
        "shadow_profile": None,
        "offscreen_events": [],
        "standing_intentions": [],
        "coherence_notes": [],
        "validated_introductions": [],
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