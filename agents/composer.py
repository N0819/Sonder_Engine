"""The deterministic perception composer: percept selection and rendering.

Two layers with a typed seam (design_notes/03-composer-design.md, 00-PLAN.md
Phase 2):

**Layer A -- percept builders (`build_*_percepts`). The information
boundary.** Pure functions of (scene + typed events + known/awareness) that
return an ordered ``list[Percept]``. Every admission decision happens here,
on structured data, before any prose exists: delivery gates, hear/sight/scent
levels, containment, rear-arc, concealment, recognition labels. Nothing
outside a Percept ever reaches the renderer, and no Percept field carries a
fact the observer has no channel to -- that property is unit-tested on the IR
itself (tests/test_composer.py), not asserted by regex over prose.

**Layer B -- rendering (`render_view` / `render_episode`).** Decision-free
realisation from percepts. The signature takes percepts and mode parameters,
nothing else -- no scene, no DB -- so a rendering path structurally cannot ADD
information (design_notes/03 section 5.3). The sentence grammar reuses the
renderers already in production: `_inject_dialogue`'s dialogue grammar,
`_observable_predicate`, `contact_sensation`/`substance_event_clause` clauses
(delivered as data on the percept), and `_compose_residue_view`.

Three render modes over one percept list, because the view has three
consumers with different needs:

- ``character`` -- full standing state every beat, including complete visible
  body and attire strings for every OTHER person. A character agent is a
  stateless LLM call; if it is not in context, the mind does not have it. The
  observer's own body/attire remains supplied by its updated card state.
- ``player`` -- LEADS WITH WHAT CHANGED. Standing state is the BACKGROUND of
  a percept, not its content: the view is this beat's events and the standing
  percepts that CHANGED for this observer first, then what is merely still
  true (first mentions, re-encounters, live sensations). Change is decided by
  `standing_verdicts` against this observer's own previous ledger -- never
  against the objective scene, which is the shape that leaks -- and the
  changed half is marked `beat`, so those percepts reach the narrator as
  noticed changes without invented occurrence times. An explicit look/examine intent
  (``full_render=True``) re-renders the whole standing state on purpose.
- ``memory`` -- `render_episode`: the salient delta, minted from the IR in
  first person, with typed entities. A percept list that is all unchanged
  standing state is a NON-EVENT and returns "" -- nothing is minted (the
  "You are in an unspecified area." pathology, 812 corpus rows, dies here).

Deliberately NO lexical-variation machinery (note 03 section 2.6's leverage
ranking was measured wrong): plain templates plus discourse rules. Repetition
is solved by change-tracking, not synonyms.

Module discipline: imports `agents/common.py`, `spatial.py`, `scene.py` only
-- never another role module. `agents/perception.py` orchestrates: it builds
the inputs (it owns the spatial relation maps and the stage contracts) and
calls down into this module, exactly as it calls into `common`.
"""

from __future__ import annotations

import dataclasses
import hashlib
import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from core.pipeline_context import note_step_decision

from language_runtime import (
    LanguagePackError, current_language_id, language_pack, linguistic,
    renderer_for)

logger = logging.getLogger(__name__)
from story.scene import disguise_breaks_recognition
from story.provenance_text import strip_engine_provenance
from world.spatial import (
    _clean_pose,
    _entities_named,
    _entity_named,
    _anchor_room_of,
    _is_body_entity,
    body_cell,
    body_visibility,
    contact_thing_label,
    effective_anchors,
    effective_station,
    entity_arc,
    entity_side,
    hear_level,
    spoken_to,
    hearing_reason,
    voice_carries,
    held_beam_falls_on,
    into_another_ear,
    movement_heard_at_ear,
    _sense_channel,
    sense_adjusted,
    proximity_rel,
    room_of,
    same_subject,
    sense_acuity_offset,
    sound_bearing,
    size_relation,
    visual_level_between,
)

from .common import (
    _appearance_as_prose,
    self_name_forms,
    name_occurrence_pattern,
    _base_from_third_person_s,
    _compose_residue_view,
    _identity_token_set,
    _inject_dialogue,
    _muffle_tokens,
    _muffled_fragment,
    _observable_predicate,
    _quote_body,
    _recognizes,
    _fix_you_agreement,
    _self_second_person,
    _unknown_actor_label,
    stranger_label_ladder,
)


# FACADE. Since 2026-11-01 every name below is defined in one of the
# `agents/composer_*` siblings, carved out of this file verbatim, and
# re-exported here explicitly -- private names included -- so every `from
# agents.composer import X` and every `composer.X` keeps meaning what it meant
# (docs/design/DESIGN_MODULE_LAYOUT.md, "Job 1: split behind facades"). This
# module defines nothing of its own.
#
# The import block above is RETAINED byte-for-byte, not pruned: tests
# monkeypatch names on this module, and a name that stops resolving here
# breaks them. A patch on this module is inert for a reader that moved to a
# sibling -- patch the sibling that reads the name, or use
# tests/helpers.py::patch_seam where several do.

from agents.composer_common import (  # noqa: F401
    CHANNELS,
    PERCEPT_KINDS,
    Percept,
    _ENGLISH_COMPOSITOR,
    _EN_TEMPLATES,
    _bare_words,
    _cap,
    _compositor,
    _en,
    _join_clauses,
    _ling,
    _lower_lead,
    _noun_phrase,
    _pack_words,
    _safe_renderer,
    _sense_graded,
    _short_hash,
    _spliced_fragment,
    _strip_sentence_ends,
    _subject_prefix,
    _t,
    body_key,
    standing_key,
)
from agents.composer_person import (  # noqa: F401
    _OBJECT_PRONOUNS,
    _OBJECT_PRONOUN_FOLLOWERS,
    _PERSON_WORDS_RE,
    _SEQUENCERS,
    _THIRD_PERSON_SETS,
    _WORD_TOKEN,
    _action_target_second_person,
    _first_person,
    _fix_i_agreement,
    _mine_if_it_matters,
    _opens_an_object,
    _participle,
    _pose_owner_second_person,
    _pronoun_forms,
    _reads_as_possessive,
    _reads_as_subject,
    _said_as_mine,
    _same_but_for_person,
    _second_to_first_rules,
    _self_first_person,
    _verbs_in_base,
    own_attempt,
)
from agents.composer_figures import (  # noqa: F401
    DIM_FIGURE,
    DIM_FIGURES,
    SURFACE_WIDENING_CAPS,
    _LABEL_DANGLING,
    _ORDINAL_WORDS,
    _PRESENCE_DEPTH_TIERS,
    _active_ordinal_words,
    _collided_names,
    _descriptor_words,
    _dim_figure,
    _label_core,
    _label_from_words,
    _ordinal_label,
    _ordinal_word,
    _presence_depth,
    _presence_sort_key,
    _silhouette_labels,
    _size_label,
    _unfamiliar_person,
    _visible_room_label,
    assign_stranger_labels,
    observer_display_map,
    presence_percepts,
)
from agents.composer_bodies import (  # noqa: F401
    EAR_STATES,
    _COUNT_NAMES,
    _ID_SHAPED,
    _OWN_POSE_KEY_FIELDS,
    _POSE_FREE_TEXT,
    _POSE_RENDER_FIELDS,
    _display_for_id,
    _names_a_body,
    _no_engine_ids,
    _part_qualified,
    _pose_referent,
    _same_referent,
    appearance_percept,
    body_part_percepts,
    body_region_percepts,
    body_state_percept,
    contact_action_percepts,
    contact_percepts,
    cue_percept,
    demeanor_percept,
    ear_percepts,
    pose_percepts,
    residue_percepts,
)
from agents.composer_speech import (  # noqa: F401
    _MANNER_PART_CHARS_UNSPACED,
    _MANNER_PART_WORDS,
    _TONE_NOT_A_QUALITY,
    _TONE_PART_END,
    _addresses,
    _affect_word,
    _can_say_the_voice,
    _carried_tone,
    _feeling_heard,
    _fits_the_manner_slot,
    _line_refs,
    _names_kept,
    _names_the_speaker,
    _one_voice_each,
    _register_heard_unseen,
    _tone_words,
    _trace_percept,
    _voice_feeling,
    _voice_fields,
    _voice_sound_heard_unseen,
    communication_percept,
    concealed_from_observer,
    line_addressed,
    line_hear_level,
    own_name_forms,
    own_name_said,
    silence_percept,
    speech_percept,
    typed_affect,
)
from agents.composer_acts import (  # noqa: F401
    _ARRIVAL_BAND,
    _DEPARTURE_BAND,
    _peel_own_name,
    _sound_bearing_phrase,
    _surface_suddenness,
    act_percept,
    crossing_percept,
    substance_percept,
)
from agents.composer_landscape import (  # noqa: F401
    FAR_SIGHT_TAGS,
    LANDSCAPE_COVERS,
    LANDSCAPE_GRAINS,
    LANDSCAPE_GROUNDS,
    LANDSCAPE_HEIGHTS,
    _beside_on_one_bearing,
    _far_line_text,
    _plain_ground,
    air_phrase,
    compose_landscape_line,
    far_sight,
    is_landscape,
    landscape_lines,
    landscape_look_percepts,
    landscape_percepts,
    near_text,
    render_landscape_line,
    vista_percepts,
)
from agents.composer_things import (  # noqa: F401
    _UNREADABLE_STATE_KEYS,
    _reading_label,
    _reading_value,
    chatter_percepts,
    micro_round_percept,
    micro_round_percepts,
    room_content_percepts,
    thing_clause,
    thing_in_hand_clause,
    thing_reading_percepts,
    thing_reading_text,
)
from agents.composer_standing import (  # noqa: F401
    HABITUATING_SOUND_TAGS,
    OBSERVATION_DEFAULTS,
    STANDING_VERDICTS,
    VOICE_KEY_PREFIX,
    WEATHER_SOUND_TAG,
    WIND_SOUND_TAG,
    _FIDELITY_AMBIGUITY,
    _FIRST_SIGHT_LEADS,
    _was_in_its_room,
    appearance_delta,
    as_beat,
    asked_this_beat,
    carried_voices,
    compact_observation,
    habituated,
    leads_the_beat,
    observations_from_render,
    perception_packet,
    player_view_order,
    standing_verdicts,
    steady_sound,
    unheard_ceasing,
    view_verdicts,
)
from agents.composer_fields import (  # noqa: F401
    DISTANT_SOUND_LEVELS,
    LIGHT_SHAPE_LEVELS,
    SOUND_SHAPE_LEVELS,
    _ENGINE_CHANNEL_PERCEPT,
    _FELT_SALIENCE,
    _SCENT_FIDELITY,
    _ambient_channel,
    _clean_shape,
    _shape_clauses,
    _shape_signature,
    _storm_percepts,
    _was_hearing,
    _weather_sound_heard,
    aim_worth_naming,
    ambient_percepts,
    distant_sound_percepts,
    environment_percept,
    felt_percepts,
    field_shape_sentence,
    render_distant_sound,
    render_light_shape,
    render_sound_shape,
    scent_percepts,
    sound_ceased_percept,
    soundscape_percept,
    walk_underway_percepts,
    weather_percepts,
    weather_sound_percepts,
)
from agents.composer_render import (  # noqa: F401
    ACTIVE_STANDING_KINDS,
    PLURAL_PLACES,
    RenderedView,
    _COUNT_WORDS,
    _LANDSCAPE_SLOT,
    _LEADING_CONNECTIVES,
    _OWN_BODY_DESCRIPTION_KINDS,
    _POSE_PREPOSITIONS,
    _PRESENCE_SLOT,
    _SIZE_PHRASES,
    _STANDING_ORDER,
    _TIER_PHRASES,
    _appearance_restates_label,
    _en_voice_line,
    _end_sentence,
    _feature_items,
    _heard_after,
    _is_own_body_description,
    _presence_clause,
    _render_ambient,
    _render_body_part,
    _render_event,
    _render_features,
    _render_openings,
    _render_pose,
    _render_presence_group,
    _render_scent,
    _render_standing,
    _render_view_english,
    _strip_leading_connective,
    render_view,
)
from agents.composer_episode import (  # noqa: F401
    _EPISODE_SOUND_TAGS,
    _EPISODE_STANDING_KINDS,
    _GENERIC_LABELS,
    _YOU_TO_ME,
    _episode_sentence,
    _files_as_memory,
    _render_episode_english,
    episode_signature,
    render_episode,
)
