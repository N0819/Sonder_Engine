"""Institutions and upkeep — the facade over the `charter_*` siblings.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md``. Status: **pure simulator,
production vertical slice.** This facade remains model-free and performs no
I/O. ``world.charter_runtime`` owns the frame-scoped persistence, guarded
catch-up job, consequence mint and bounded apertures that connect it to play.

    from world.charter import normalize_charter, seed_roster, run

    ship, events = run(normalize_charter(SHIP), hours=168.0, window=4.0)

Split across siblings from the first commit rather than after a monolith grew
one, because this repo has now paid for that split three times
(``world/spatial.py`` over fourteen, ``mind/memory.py`` over twelve,
``persist/commit.py`` over thirteen). The seam each sibling owns:

  * ``charter_model``  — the five primitives, normalized. No behaviour.
  * ``charter_drift``  — what time does to an upkeep. Recomputable, no history.
  * ``charter_roster`` — what the charter BELIEVES about its people, and only
    that; ground truth lives on the bodies and is never read by the planner.
  * ``charter_plan``   — the attempt: rank posts, staff them, report the gap.
  * ``charter_run``    — advancing time, and the only things written down.
  * ``charter_temper`` — per-body dispositions, in the card's own vocabulary.
  * ``charter_feel``   — felt state per body, produced by calling
    ``mind/psychology_runtime``'s own resolvers rather than a second model.
  * ``charter_mark``   — socially temporary facts about a body, each with a
    lifetime and a scope: what it holds now that it did not before, and which
    of those it may be told about.
  * ``charter_trigger`` — rules that fire off an objective CHANGE and produce
    an objective consequence: a situation, a mark, an event. It reads a change
    and never a state, and who LEARNS of the consequence stays
    ``charter_news``'s separate question.
  * ``charter_figure`` — the player and major characters as claim SUBJECTS:
    seen, told about, decaying, wrong — never rostered and never minded here.
  * ``charter_author`` — the §12a author-switch: authored conduct landing
    through the identical affordance path a chosen act takes.
  * ``charter_promote``— the selected past a promotion hands over, and the
    firewall on what may not cross with it.

A caller imports this module. A test may name a sibling it patches or reads the
source of; one that only calls through should come here, which is the same rule
``tools/project_check.py`` enforces for the three facades above. This one is
not registered there yet — the deeper fidelity work is still teaching us which
internal seams deserve to become permanent public boundaries.
"""

from __future__ import annotations

from .charter_drift import (
    advance_level,
    hours_until_floor,
    starving_input,
    supply_factor,
    urgency,
)
from .charter_model import (
    DEFAULT_FLOOR,
    LEVEL_MAX,
    LEVEL_MIN,
    meets,
    normalize_body,
    normalize_charter,
    normalize_competence,
    normalize_post,
    normalize_upkeep,
    out_of_band,
    priority_rank,
)
from .charter_identity import (
    address_components,
    components_repeat,
    derived_name_parts,
    display_name,
    extension_profile,
    generated_name,
    generated_name_parts,
    identity_aliases,
    identity_reservation,
    identity_seed,
    materialize_body_names,
    name_is_reserved,
    normalize_naming_profile,
    spread_components,
    strip_reserved_pools,
    title_for,
)
from .charter_feel import (
    NEGLIGIBLE,
    STRAIN_REST_TOLL,
    advance_feel,
    appraise_window,
    felt_handoff,
    normalize_feel,
    overloaded_bodies,
    strain_of,
)
from .charter_log import (
    chronicle, life_of, scene_ledger, summarize, window_note)
from .charter_mark import (
    BODY_MARKS,
    BY_MARKS,
    DISGRACE_RELUCTANCE,
    MARKS,
    MARK_HOURS,
    advance_marks,
    held_marks,
    mark_view,
    normalize_marks,
)
from .charter_move import (
    ERRAND_RATE, errands, furthest_travelled, homecomings, relocate, walk)
from .charter_temper import (
    SPREAD,
    TRAITS,
    derived_temperament,
    interoception_of,
    normalize_temperament,
    stress_profile_of,
    temperament_of,
    temperament_warnings,
)
from .charter_needs import (
    DEFAULT_NEEDS,
    ON_WATCH_STRAIN,
    RECOVERY_MARGIN,
    able,
    advance_needs,
    body_state,
    mood,
    pressure,
    seed_needs,
    unmet,
)
from .charter_author import FIGURE_ACTS, action_instances, authored
from .charter_figure import (
    figure_claim,
    figure_spread,
    known_figures,
    normalize_figures,
    sight_figures,
    stale_figure_claims,
)
from .charter_mind import (
    PERSONAL_FLOOR,
    RECALL_CAP,
    acquaintance,
    believes,
    cap_minds,
    contested,
    decay_minds,
    divergence,
    hear,
    hear_claim,
    normalize_minds,
    see,
)
from .charter_promote import (
    RELATIONSHIP_CAP,
    REMEMBERED_CAP,
    promotion_handoff,
    remembered,
)
from .charter_news import (
    CHECKABLE,
    WITNESSABLE,
    check_reports,
    claim_from_report,
    decay_news,
    known_news,
    news_key,
    report_from_claim,
    report_key,
    spread_of,
    witness,
)
from .charter_plan import criticality, plan_watch, tended_upkeeps
from .charter_practice import (
    ASKED_RETENTION,
    FAMILIAR_SATURATION,
    GRIEVANCE_KINDS,
    HISTORY_WEIGHT,
    IDLE_CLOSE_HOURS,
    PAIR_TAIL,
    PRACTICE_CAP,
    REFUSED_ABSENT,
    REFUSED_NO_SITUATION,
    REFUSED_OUTSIDE_LICENCE,
    PLACE_FAILURE_KINDS,
    REFUSED_UNABLE,
    close_stale,
    enact,
    entanglement,
    grievance_against,
    normalize_practices,
    offers,
    opportunities,
)
from .charter_politics import (
    attribute_blame,
    normalize_politics,
    regard_between,
    regard_key,
    regard_map,
    regard_pair,
    regard_value,
    spend_reluctance,
)
from .charter_space import REACH_LIMIT, charter_places, reach_map, travel_rooms
from .charter_talk import (
    FORMAL_REPORT_RETENTION,
    PARTNERS_PER_WINDOW,
    RETOLD_RETENTION,
    co_present,
    converse,
    pair_up,
    report_to_superiors,
    report_up,
    tell_ranking,
    tellable,
    witnessed,
)
from .charter_roster import (
    DECAY_PER_HOUR,
    TRUST_FLOOR,
    assignable,
    decay_roster,
    observe,
    seed_roster,
    stale_claims,
)
from .charter_run import run, step
from .charter_social import (
    CLOSE_FAMILIARITY, DEFAULT_SIGNALS, FAMILIAR_FLOOR, JUDGMENT_AXES,
    TIE_CAP, TIE_DWELL_HOURS, TIE_FORM, TIE_HOLD, TIE_LABELS, TIE_SATURATION,
    TIE_WEIGHTS, derive_tie, familiarity, judgment_of, judgment_view,
    normalize_judgments, normalize_social_norms, normalize_ties, tie_of,
    tie_strength, tie_view, update_judgments_from_minds, update_ties)
from .charter_commitment import (
    OPEN_STATES, TERMINAL_STATES, advance_commitments, commitment_id,
    commitment_view, normalize_commitments, observe_public_commitments)
from .charter_economy import (
    advance_economy, caravan_exchange, normalize_economy, quote, stock_band,
    trade)
from .charter_decide import (
    ORDER_ACTIONS, advance_decisions, decision_view, deliver_orders,
    execute_orders, normalize_decisions)
from .charter_intervene import (
    INTERVENTION_OPS, apply_due, intervention_warnings,
    normalize_interventions)
from .charter_chatter import (
    FRAGMENT_ODDS,
    HUM_BANDS,
    STEADY_HUM_ACTS,
    WINDOW_ACTS_CAP,
    acts_in_room,
    fragment_key,
    fragment_phrase,
    hum_phrase,
    hum_rank,
    normalize_window_acts,
    overheard_fragment,
    participant_label,
    subject_label,
    window_acts,
)
from .charter_trigger import (
    CHANGE_FAMILIES,
    DEFAULT_TRIGGERS,
    MATCHABLE,
    PENDING_CHANGE_CAP,
    REFERENTS,
    TRIGGER_CAP,
    TRIGGER_DEPTH,
    TRIGGER_EMITTABLE,
    TRIGGER_MEMORY_CAP,
    TRIGGER_OPS,
    TRIGGER_THEN_CAP,
    TRIGGER_YIELD_CAP,
    change_key,
    changes_from,
    fire_triggers,
    normalize_pending_changes,
    normalize_triggers,
    perceivable_change,
    prune_trigger_last,
    trigger_view,
    trigger_warnings,
)

__all__ = [
    "FRAGMENT_ODDS", "HUM_BANDS", "STEADY_HUM_ACTS", "WINDOW_ACTS_CAP",
    "acts_in_room", "fragment_key", "fragment_phrase", "hum_phrase",
    "hum_rank", "normalize_window_acts", "overheard_fragment",
    "participant_label", "subject_label", "window_acts",
    "CHANGE_FAMILIES", "DEFAULT_TRIGGERS", "MATCHABLE", "PENDING_CHANGE_CAP",
    "REFERENTS", "TRIGGER_CAP", "TRIGGER_DEPTH", "TRIGGER_EMITTABLE",
    "TRIGGER_MEMORY_CAP", "TRIGGER_OPS", "TRIGGER_THEN_CAP",
    "TRIGGER_YIELD_CAP", "change_key", "changes_from", "fire_triggers",
    "normalize_pending_changes", "normalize_triggers", "perceivable_change",
    "prune_trigger_last", "trigger_view", "trigger_warnings",
    "BODY_MARKS", "BY_MARKS", "DISGRACE_RELUCTANCE", "MARKS", "MARK_HOURS",
    "advance_marks", "held_marks", "mark_view", "normalize_marks",
    "CLOSE_FAMILIARITY", "FAMILIAR_FLOOR", "TIE_CAP", "TIE_DWELL_HOURS",
    "TIE_FORM", "TIE_HOLD", "TIE_LABELS", "TIE_SATURATION", "TIE_WEIGHTS",
    "derive_tie", "familiarity", "normalize_ties", "tie_of", "tie_strength",
    "tie_view", "update_ties",
    "DEFAULT_SIGNALS", "JUDGMENT_AXES", "OPEN_STATES", "ORDER_ACTIONS",
    "TERMINAL_STATES", "INTERVENTION_OPS", "advance_commitments", "advance_decisions",
    "advance_economy", "caravan_exchange", "commitment_id",
    "commitment_view", "decision_view", "deliver_orders", "execute_orders",
    "judgment_of", "judgment_view", "normalize_commitments",
    "normalize_decisions", "normalize_economy", "normalize_judgments",
    "normalize_social_norms", "observe_public_commitments", "quote",
    "stock_band", "trade", "update_judgments_from_minds", "apply_due",
    "intervention_warnings", "normalize_interventions",
    "ERRAND_RATE",
    "errands",
    "homecomings",
    "walk",
    "FIGURE_ACTS",
    "address_components",
    "components_repeat",
    "derived_name_parts",
    "display_name",
    "extension_profile",
    "generated_name",
    "generated_name_parts",
    "identity_aliases",
    "identity_reservation",
    "identity_seed",
    "materialize_body_names",
    "name_is_reserved",
    "normalize_naming_profile",
    "spread_components",
    "strip_reserved_pools",
    "title_for",
    "REFUSED_ABSENT",
    "REFUSED_NO_SITUATION",
    "REFUSED_OUTSIDE_LICENCE",
    "REFUSED_UNABLE",
    "RELATIONSHIP_CAP",
    "REMEMBERED_CAP",
    "action_instances",
    "authored",
    "cap_minds",
    "figure_claim",
    "figure_spread",
    "hear_claim",
    "known_figures",
    "normalize_figures",
    "offers",
    "promotion_handoff",
    "remembered",
    "sight_figures",
    "stale_figure_claims",
    "tell_ranking",
    "tellable",
    "decay_news",
    "CHECKABLE",
    "WITNESSABLE",
    "check_reports",
    "news_key",
    "witness",
    "spread_of",
    "known_news",
    "scene_ledger",
    "opportunities",
    "normalize_practices",
    "enact",
    "entanglement",
    "close_stale",
    "PRACTICE_CAP",
    "IDLE_CLOSE_HOURS",
    "ASKED_RETENTION",
    "HISTORY_WEIGHT",
    "PAIR_TAIL",
    "FAMILIAR_SATURATION",
    "GRIEVANCE_KINDS",
    "PLACE_FAILURE_KINDS",
    "grievance_against",
    "NEGLIGIBLE",
    "RECOVERY_MARGIN",
    "SPREAD",
    "STRAIN_REST_TOLL",
    "TRAITS",
    "advance_feel",
    "appraise_window",
    "derived_temperament",
    "felt_handoff",
    "interoception_of",
    "mood",
    "normalize_feel",
    "normalize_temperament",
    "overloaded_bodies",
    "pressure",
    "strain_of",
    "stress_profile_of",
    "temperament_of",
    "temperament_warnings",
    "ON_WATCH_STRAIN",
    "DEFAULT_NEEDS",
    "unmet",
    "seed_needs",
    "relocate",
    "life_of",
    "furthest_travelled",
    "body_state",
    "advance_needs",
    "able",
    "DECAY_PER_HOUR",
    "DEFAULT_FLOOR",
    "LEVEL_MAX",
    "LEVEL_MIN",
    "PARTNERS_PER_WINDOW",
    "PERSONAL_FLOOR",
    "REACH_LIMIT",
    "RECALL_CAP",
    "RETOLD_RETENTION",
    "TRUST_FLOOR",
    "acquaintance",
    "advance_level",
    "assignable",
    "attribute_blame",
    "believes",
    "charter_places",
    "chronicle",
    "co_present",
    "contested",
    "converse",
    "criticality",
    "decay_minds",
    "decay_roster",
    "divergence",
    "hear",
    "normalize_minds",
    "normalize_politics",
    "pair_up",
    "reach_map",
    "regard_between",
    "regard_key",
    "regard_map",
    "regard_pair",
    "regard_value",
    "report_up",
    "report_to_superiors",
    "see",
    "spend_reluctance",
    "summarize",
    "travel_rooms",
    "window_note",
    "witnessed",
    "hours_until_floor",
    "meets",
    "normalize_body",
    "normalize_charter",
    "normalize_competence",
    "normalize_post",
    "normalize_upkeep",
    "observe",
    "out_of_band",
    "plan_watch",
    "priority_rank",
    "run",
    "seed_roster",
    "stale_claims",
    "starving_input",
    "step",
    "supply_factor",
    "tended_upkeeps",
    "urgency",
]
