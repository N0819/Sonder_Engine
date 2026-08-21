"""Institutions and upkeep — the facade over the `charter_*` siblings.

``docs/design/DESIGN_INSTITUTIONS_AND_UPKEEP.md``. Status: **prototype.** Pure,
offline, model-free, and not yet wired to any commit path — nothing in this
package reads or writes storage, mints a fuse, or calls a model.

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

A caller imports this module. A test may name a sibling it patches or reads the
source of; one that only calls through should come here, which is the same rule
``tools/project_check.py`` enforces for the three facades above. This one is
not registered there yet — it is a prototype, and registering it would freeze a
layout that is still being learned.
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
from .charter_log import chronicle, summarize, window_note
from .charter_mind import (
    PERSONAL_FLOOR,
    RECALL_CAP,
    acquaintance,
    believes,
    contested,
    decay_minds,
    divergence,
    hear,
    normalize_minds,
    see,
)
from .charter_plan import criticality, plan_watch, tended_upkeeps
from .charter_politics import (
    attribute_blame,
    normalize_politics,
    regard_between,
    regard_map,
    spend_reluctance,
)
from .charter_space import REACH_LIMIT, charter_places, reach_map, travel_rooms
from .charter_talk import (
    PARTNERS_PER_WINDOW,
    RETOLD_RETENTION,
    co_present,
    converse,
    pair_up,
    report_up,
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

__all__ = [
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
    "regard_map",
    "report_up",
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
