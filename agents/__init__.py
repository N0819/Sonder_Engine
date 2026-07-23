"""Agent package and backward-compatible public facade.

Agent implementations are separated by role. Importing from ``agents`` remains
supported for the application and third-party extensions.
"""

from scene import active_cast, is_player_speaker

from .character import character_step
from .common import (
    _dict,
    _list,
    _dict_list,
    _text_piece,
    _join_text,
    _assert_plan_materialized,
    _character_by_id,
    _char_known_tags,
    _character_display_name,
    _normalize_scene_patch,
    _sequence_has_content,
    _asks_player,
    _next_speaker_candidates,
    _requires_reaction_phase,
    _requires_director_resolution,
    _classify_action_commitment,
    _normalize_effect,
    _extract_authority_claims,
    _agent_json,
    jparse,
    _books,
    lore_for,
    _room_notes_from_lore,
    norm_sequence,
    assign_event_ids,
    _stable_event_key,
    _lore_fingerprint,
    _append_once,
    _unknown_actor_label,
    _contains_quote,
    normalize_character_refs,
    _append_micro_view,
    _normalize_character_output,
    cap_mind_model_updates,
    player_speech_lines,
    _quote_body,
    _inject_dialogue,
    _inject_action,
    _inject_visible_actor,
    _compose_residue_view,
    observable_action_text,
    _normalise_views,
    _ensure_environment,
    _fallback_perception_views,
    _strip_player_echo,
    _check_narrator_fidelity,
    _llm_resolve_player_room,
    _resolve_player_room,
)
from .director import director_establish, director_interpret, director_resolve
from .loops import deterministic_micro_perception, interaction_loop, reaction_loop
from .mapping import mapping_quick, mapping_stage
from .narration import narrator
from .perception import perception_act, perception_establish, perception_outcome
from .runtime import (
    ABORTS,
    STEP_HANDLERS,
    Bus,
    PipelineBusyError,
    StaleStepError,
    _run_pipeline,
    begin_pipeline,
    build_plan,
    compute_step,
    establishment_plan,
    register_step,
    request_abort,
    resume_key_for_turn,
    run_pipeline,
)
from .storage import active_content, save_step, step_is_stale, variant_count

__all__ = [name for name in globals() if not name.startswith("__")]
