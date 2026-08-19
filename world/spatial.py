# spatial.py
"""Spatial reasoning with entity-aware scene merging and containment validation."""

import copy
import hashlib
import re
from collections import defaultdict
from typing import Optional

from llm.schemas import NON_ENTITY_FIELD_KEYS, is_derived_entity_name
from world.spatial_orientation import (
    _LEFT_SECTORS,
    _REL_SECTORS,
    _RIGHT_SECTORS,
    lateral_of,
    normalize_bearing,
    normalize_scene_bearings,
    normalize_vertical,
    opposite_bearing,
    opposite_vertical,
    relative_bearing,
    travel_bearing,
)


from world.spatial_identity import (
    _ci_get, _entity_named, _live_subject_spellings, _position_of,
    _SUBJECT_KEYED, canonical_subject, canonical_subject_map,
    is_derived_room_name, normalize_room_id, normalize_scene_subjects,
    room_of, same_subject,
)


from world.spatial_barriers import (
    _AMBIENT_BARRIERS, _barrier_against_its_own_name, _BARRIER_ALIASES,
    _BARRIER_CLOSED_FORM, _BARRIER_CLOSED_QUALIFIERS, _barrier_exact,
    _BARRIER_OPEN_FORM, _BARRIER_OPEN_QUALIFIERS, _BARRIER_SEAL_QUALIFIERS,
    _BARRIER_SEALED_FORM, _OPENING_WORDS, _PASSABLE_BARRIERS, _SCENT_BARRIER_LEVELS,
    _SIGHT_BARRIERS, _VALID_BARRIERS, normalize_barrier,
    normalize_scene_barriers, unresolved_barrier_words,
)


from world.spatial_transit import (
    _closed_enclosure_barrier, _entity_exterior_room, _is_body_entity,
    _link_state, _open_enclosure_barrier, _TRANSIT_CLOSED_PHASES,
    _transit_state, ambient_scope, apply_transit_dock_edges,
    CONTAINER_ENCLOSURES, containment_chain, infer_body_enclosures,
)


from world.spatial_containment import (
    _body_interior_holder, _clean_containment, _hiding_holders,
    _innermost_hiding_holder, _MAX_CONTAINED, _MAX_SCALE, _MAX_SCALES,
    _MIN_SCALE, _NEVER_STATIONED_KINDS, _OPEN_CONTAINMENT_MODES,
    _SCALE_CONTACT_BREAK, _scale_phrase, _shares_enclosure, _SIZE_TIERS,
    carrier_chain, clamp_scale, container_of,
    containment_broken_by_scale_change, containment_conceals,
    containment_facts, containment_hides, CONTAINMENT_MODES, contents_of,
    derive_contained_positions, hiding_holders_of,
    normalize_scene_containment, normalize_scene_scales, scale_of,
    scale_ratio, size_facts, size_relation, size_tier,
)


from world.spatial_contacts import (
    _CAVITY_GRIP_MANNERS, _clean_contact, _contact_key,
    _CONTACT_MOMENTARY_STALE_BEATS, _contact_motion_from_text,
    _contact_ops_are_evidence, _CONTACT_RESIDUE_VERB, _CONTACT_STALE_BEATS,
    _CONTACT_STATE_VERBS, _contact_text, _contained_inversion, _displaces,
    _ENCLOSING_PART_CAVITY, _ENVELOPMENT_MANNERS, _flip,
    _INTERIOR_MOVING_MANNERS, _is_anatomical_part, _LATERAL_QUALIFIERS,
    _MAX_CONTACT_DETAIL, _MAX_CONTACT_PART, _MAX_CONTACTS, _mirror_key,
    _MOMENTARY_SET, _NON_ANATOMICAL_PART_WORDS, _normalize_contact_motion,
    _normalize_contact_relation, _part_identity, _part_is_plural,
    _same_appendage, _same_region, _SENSATION_FORMS, _SINGULAR_S_PARTS,
    _STRICT_CAVITY_KINDS, apply_contact_ops, canonical_region,
    CONTACT_INTERIOR_MANNERS, contact_is_momentary, contact_manner_kind,
    CONTACT_MANNERS, CONTACT_MOMENTARY_MANNERS, contact_motion,
    CONTACT_MOVING_MANNERS, contact_relation, contacts_broken_by_scale_change,
    contacts_of, normalize_scene_contacts, owned_region, same_owned_region,
)


from world.spatial_contact_migration import (
    _CONTACT_KEY_MANNERS, _CONTACT_PROXIMITIES, _DIRECTION_AFTER_VERB,
    _drop_contradicted_state, _lift_valued_contact, _manner_from_fragment,
    _part_from_key, _PROTECTED_STATE_KEYS, _RELATIONAL_STATE_SUFFIXES,
    contacts_from_entity_state,
)


from world.spatial_substance import (
    _absorb_into_pool, _interior_destination_for_release, _record_region,
    _resolved_substance_add, _same_pool, _SPEECH_CAVITY_INTERIORS,
    _SPEECH_MOUTH_KINDS, _stock_consumed_by, _substance_id,
    _substance_placement, _SUBSTANCE_PLACEMENTS, _substance_target_exists,
    _substance_text, apply_substance_ops, ARTICULATION_SLURRED,
    ARTICULATION_STIFLED, resolve_substance_ops,
    speech_articulation_impediment, substance_event_clause, substances_for,
)


from world.spatial_geometry import (
    _anchor_dir, _anchor_for_entity, _BARRIER_ANCHOR_DESC, _clean_pose,
    _DOOR_ANCHOR_PREFIX, _occupancy, _POSE_FIELDS, _REAR_SECTORS,
    _relative_sector, _ROOM_SIZE_HINT_WORDS, ROOM_SIZES,
    DEFAULT_ROOM_SIZE, _sector_label, _station,
    anchor_bearing_of, apply_pose_diff, crossing_of, derive_scene_stations,
    door_anchor_id, effective_anchors, effective_facing, effective_room_size,
    effective_station, egocentric_frame, entity_arc, entity_side,
    guessed_room_sizes, measured_proximity_rel, normalize_scene_poses,
    normalize_scene_stations, pose_facts, proximity_rel, room_layout,
    spatial_digest, THRESHOLD_CROSSING_BEATS,
)


from world.spatial_light import (
    _brighter, _LIGHT_ALIASES, _LIGHT_ORDER, _light_radius, _LIGHT_SIGHT,
    effective_light, light_at, light_blocks_sight, LIGHT_LEVELS,
    normalize_light, room_light, SIGHT_LEVELS, source_light,
)


from world.spatial_routing import (
    _CORRIDOR_NAMED, _CORRIDOR_VAGUENESS, _DISTANCE_ALIASES,
    _DISTANCE_UNIT_METERS, _is_carried_interior, _onward_exits, _reverse_dir,
    _ROOM_COST, CORRIDOR_SIGHT_LIMIT, corridor_sightlines, DISTANCE_TIERS,
    nearby_rooms, normalize_edge_distance, passable_neighbors, passable_path,
    passable_route_exists, passable_route_next_step, rooms_adjacent,
    spatial_rel, SPRINT_BUDGET, sprint_reach, visible_adjacent_rooms,
)


from world.spatial_senses import (
    _ACUITY_ABSENT, _ACUITY_MINUS_ONE, _ACUITY_PLUS_ONE, _ACUITY_PLUS_TWO,
    _clean_comms_channel, _comms_carrier_room, _comms_delivers,
    _comms_transmits, _COMPASS_WORDS, _edge_vertical,
    _material_shifted_barrier, _MATERIAL_SOUND_STEPS, _measured_intimacy,
    _opening_view_cap, _phrase_table, _RANGE_EXTENDED, _RANGE_REDUCED,
    _sector_phrases, _SECTOR_PHRASES, _SECTOR_STEPS, _sense_channel,
    _SENSE_CHANNEL_ALIASES, _SENSE_LADDERS, _sight_line, _SIGHT_ORDER,
    _sound_barrier_phrases, _SOUND_BARRIER_PHRASES, _SOUND_LADDER,
    _SOUND_WALK_BARRIERS, _weaker_sight, apply_comms_ops, can_perceive,
    can_perceive_onset, comms_between, comms_link, COMMS_MODES, comms_reach,
    crossing_visible_from, has_visual, hear_level, HEARING_LEVELS,
    is_alarming, normalize_scene_comms, scent_level, SCENT_LEVELS,
    sense_acuity_offset, sense_adjusted, sense_entry, sense_range_class,
    sight_level, sound_bearing, sound_path, sound_walk_level,
    spatial_rel_between, visual_level_between,
)


from world.spatial_prose import (
    contact_phrase, contact_sensation, spatial_facts,
)


from world.spatial_merge import (
    _dedup_duplicate_entity_keys, _dedup_duplicate_position_keys,
    _dedupe_adjacent, _ENTITY_DEFAULT_FIELDS, _ENTITY_STRUCTURAL_FIELDS,
    _merge_entity, _merge_room, _position_key, _ROOM_SILENT_WHEN_EMPTY,
    _shield_standing_bearings, _shield_standing_passage, apply_following_ops,
    connect_orphan_new_rooms, merge_scene_with_diff, prune_bodiless_positions,
    repair_entity_positions,
)
