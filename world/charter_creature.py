"""A creature is an institution whose upkeep is fed from other institutions'
bodies or stock, whose triggers are authored, and whose evidence is left in
the world. This module is the DATA half: the closed schema, and the pure
questions the registry round (`charter_predation`) asks of it.

``docs/design/DESIGN_CREATURES_AS_CHARTER.md``. Nothing here knows what a
wolf is. A pack, a band of robbers, a solitary hoarder and a thing that
feeds on fear are one schema with different tables, the same way a ship's
watch bill and an abbey's hours are (`tests/charter_fixtures.py`). The
vocabulary is the engine's own throughout:

  * **prey** is an ordered preference over the four categories a place can
    hold -- ``stock`` (economy lots at a market), ``unposted`` (a body off
    the bill), ``posted`` (a body standing a post) and ``figure`` (a
    scene-owned person, whose fate is the bubble's and never this
    module's);
  * **senses** are a range in rooms, the hearing analogue: what a creature
    notices from where it stands;
  * **footprint** is `world/spatial_fov.FOOTPRINTS`, and a room too small
    for it holds the creature at the door exactly as a shut door holds a
    body that cannot open one (`can_open_doors`);
  * **contest** weights, **encounter odds** and the **kill ceiling** are
    authored on the creature, never engine constants -- the engine defaults
    below are what an unwritten field reads as, and every one is named;
  * **fed** names the upkeep predation restores and how much a body or a
    lot is worth to it. Hunger is that upkeep's distance from full, which is
    what drives the odds and what starves a creature that catches nothing
    -- the famine spiral `charter_needs` documents, applied to the hunter.
  * **spoor** is what a landed predation leaves for a body to READ
    (`charter_predation.read_spoor`): the stationary carrier, one tier down
    from `story/artifacts.py`.

Pure and deterministic. No clock, no model, no I/O.
"""

from __future__ import annotations

from .charter_harm import POSTED_CAPABILITY, UNPOSTED_CAPABILITY
from .charter_model import _clamp, integer, number

#: The four kinds of thing a place can hold that a creature may want.
PREY_CATEGORIES = ("stock", "unposted", "posted", "figure")

#: What an unwritten prey table reads as: goods before people, and the
#: straggler before the guard. `figure` is never in a default -- a
#: scene-owned person is the Director's to endanger.
DEFAULT_PREY = ("stock", "unposted", "posted")

#: Rooms out from where it stands that a creature notices prey.
DEFAULT_SENSE_RANGE_ROOMS = 2

#: Chance per hunting body per window that an encounter at a shared place
#: becomes an attack, before hunger and boldness scale it.
DEFAULT_ENCOUNTER_ODDS = 0.5

#: Bodies one creature institution may kill or take per window. A CEILING,
#: authored per creature; a pack cannot empty a town in one night.
DEFAULT_KILL_CEILING = 1

#: Lots taken from a store or market in one raid.
DEFAULT_STOCK_LOTS = 1.0

#: Hours a spoor record stands before nothing is left to read.
DEFAULT_SPOOR_HOURS = 72.0

#: Where an unwritten boldness dial sits. 0 is timid, 1 is brazen; it scales
#: the odds and is the thing an authored rule turns (`creature_dial`).
DEFAULT_BOLDNESS = 0.5

#: The contest, before authoring. `capability` is what one creature body
#: brings; `group_bonus` is what every extra prey body standing beside the
#: target adds, as a fraction of its own weight; the two weights are the
#: engine's posted/unposted distinction (`charter_harm`).
DEFAULT_CONTEST = {
    "capability": 1.0, "group_bonus": 0.5,
    "posted_weight": POSTED_CAPABILITY,
    "unposted_weight": UNPOSTED_CAPABILITY,
    # The chance of winning below which a creature does not attack at all.
    # A creature is needs and routes, not tactics, but a thing that throws
    # itself at a guarded gate every window until it dies is not a creature
    # either; it is a number going down. Measured on the first smoke run
    # before this existed: twenty attacks on a two-body watch, twenty
    # losses, and the pack never once turned away.
    "caution": 0.2,
}

#: What a body and a lot restore on the fed upkeep.
DEFAULT_FED = {"per_body": 0.6, "per_lot": 0.25}

#: The smallest room size a footprint fits (`world/spatial_geometry.ROOM_SIZES`
#: order). A room with no size fits everything: an unsized room is the
#: ordinary case and must not become a wall.
FOOTPRINT_MIN_ROOM = {"point": "", "small": "", "large": "medium",
                      "run": "large"}

#: Spoor records one creature institution keeps standing at once.
SPOOR_CAP = 32

#: The order of room sizes, for `room_fits`.
_ROOM_ORDER = ("tiny", "small", "medium", "large", "huge", "vast")


def normalize_creature(stored):
    """The closed creature record, or ``None`` for an ordinary institution.

    A refusal is a NOTICE, the contract every normalizer in this package
    holds: an unreadable field falls to its named default and the record
    carries ``refused`` so `creature_warnings` can render it.
    """
    if not isinstance(stored, dict) or not stored:
        return None
    from .spatial_fov import normalize_footprint

    refused = []
    prey = []
    for raw in (stored.get("prey") or DEFAULT_PREY):
        word = str(raw or "").strip().casefold()
        if word in PREY_CATEGORIES and word not in prey:
            prey.append(word)
        elif word:
            refused.append(f"{word!r} is not a prey category")
    if not prey:
        prey = list(DEFAULT_PREY)
    senses = stored.get("senses") if isinstance(stored.get("senses"), dict) \
        else {}
    contest = dict(DEFAULT_CONTEST)
    for key, value in (stored.get("contest") or {}).items():
        if key in contest:
            contest[key] = max(0.0, number(value, contest[key]))
        else:
            refused.append(f"contest has no weight {str(key)!r}")
    fed_raw = stored.get("fed") if isinstance(stored.get("fed"), dict) else {}
    fed = {
        "upkeep": str(fed_raw.get("upkeep") or "").strip(),
        "per_body": max(0.0, number(fed_raw.get("per_body"),
                                    DEFAULT_FED["per_body"])),
        "per_lot": max(0.0, number(fed_raw.get("per_lot"),
                                   DEFAULT_FED["per_lot"])),
    }
    spoor_raw = stored.get("spoor") if isinstance(stored.get("spoor"), dict) \
        else {}
    spoor = {
        "body": " ".join(str(spoor_raw.get("body") or "").split())[:80],
        "stock": " ".join(str(spoor_raw.get("stock") or "").split())[:80],
        "tracks": " ".join(str(spoor_raw.get("tracks") or "").split())[:80],
        "hours": max(0.0, number(spoor_raw.get("hours"),
                                 DEFAULT_SPOOR_HOURS)),
    }
    phases = []
    for raw in (stored.get("active_phases") or ()):
        word = str(raw or "").strip().casefold()
        if word and word not in phases:
            phases.append(word)
    bargains = []
    for raw in (stored.get("bargains") or ()):
        if not isinstance(raw, dict):
            continue
        partner = str(raw.get("with") or "").strip()
        good = str(raw.get("good") or "").strip()
        if not partner:
            refused.append("a bargain names no partner institution")
            continue
        bargains.append({
            "with": partner, "good": good,
            "holder": str(raw.get("holder") or "").strip(),
            "lots": max(0.0, number(raw.get("lots"), 1.0)),
            "every_hours": max(1.0, number(raw.get("every_hours"), 168.0)),
            "last_paid_hours": (None if raw.get("last_paid_hours") is None
                                else number(raw.get("last_paid_hours"))),
        })
    out = {
        "prey": prey,
        "senses": {"range_rooms": max(0, integer(
            senses.get("range_rooms"), DEFAULT_SENSE_RANGE_ROOMS))},
        "footprint": normalize_footprint(stored.get("footprint")),
        "can_open_doors": bool(stored.get("can_open_doors", False)),
        "contest": contest,
        "encounter_odds": _clamp(number(stored.get("encounter_odds"),
                                        DEFAULT_ENCOUNTER_ODDS)),
        "kill_ceiling": max(0, integer(stored.get("kill_ceiling"),
                                       DEFAULT_KILL_CEILING)),
        "stock_lots": max(0.0, number(stored.get("stock_lots"),
                                      DEFAULT_STOCK_LOTS)),
        "take": bool(stored.get("take", False)),
        "fed": fed,
        "spoor": spoor,
        "active_phases": phases,
        "boldness": _clamp(number(stored.get("boldness"), DEFAULT_BOLDNESS)),
        "hoard_holder": str(stored.get("hoard_holder") or "").strip(),
        "bargains": bargains,
    }
    if refused:
        out["refused"] = "; ".join(refused)[:240]
    return out


def creature_warnings(stored):
    """Author-facing notices for an unreadable creature record."""
    record = normalize_creature(stored)
    if not record:
        return []
    return [record["refused"]] if record.get("refused") else []


def normalize_spoor(stored):
    """Standing spoor records, closed and capped."""
    rows = []
    for raw in (stored or ()):
        if not isinstance(raw, dict) or not raw.get("key"):
            continue
        rows.append({
            "key": str(raw["key"]),
            "place": str(raw.get("place") or ""),
            "at_hours": round(number(raw.get("at_hours")), 6),
            "until_hours": round(number(raw.get("until_hours")), 6),
            "description": str(raw.get("description") or "")[:80],
            "kind": str(raw.get("kind") or "harm_done"),
            "about": str(raw.get("about") or "")[:120],
            "actor": str(raw.get("actor") or "")[:120],
        })
    rows.sort(key=lambda row: (row["at_hours"], row["key"]))
    return rows[-SPOOR_CAP:]


def room_fits(room, footprint):
    """Does a room of this size admit a body of this footprint."""
    need = FOOTPRINT_MIN_ROOM.get(str(footprint or ""), "")
    if not need:
        return True
    size = str((room or {}).get("size") or "").strip().casefold()
    if size not in _ROOM_ORDER:
        return True
    return _ROOM_ORDER.index(size) >= _ROOM_ORDER.index(need)


def creature_neighbors(scene, creature):
    """The graph THIS creature walks: the passable one, plus shut doors when
    it can open them, minus rooms its footprint does not fit.

    `charter_move._advance` re-checks every edge of a planned route against
    the map it is handed and HOLDS the body where the check fails, so a
    door that holds a wolf and a passage too narrow for a large thing need
    no second mover: the walk is planned on the whole graph and stops
    where this map says it cannot go.
    """
    from .spatial import neighbor_map, passable_neighbors

    scene = scene if isinstance(scene, dict) else {}
    rooms = scene.get("rooms") or {}
    if not isinstance(rooms, dict):
        return {}
    creature = normalize_creature(creature) or {}
    base = {k: set(v) for k, v in (passable_neighbors(scene) or {}).items()}
    if creature.get("can_open_doors"):
        every = neighbor_map(scene, None)
        for room, ends in (every or {}).items():
            for other in ends:
                edge = _edge(rooms, room, other)
                if edge and "door" in str(edge.get("barrier") or ""):
                    base.setdefault(room, set()).add(other)
                    base.setdefault(other, set()).add(room)
    footprint = creature.get("footprint") or "point"
    out = {}
    for room, ends in base.items():
        out[room] = {other for other in ends
                     if room_fits(rooms.get(other), footprint)}
    return out


def _edge(rooms, room, other):
    for edge in ((rooms.get(room) or {}).get("adjacent") or ()):
        if isinstance(edge, dict) and str(edge.get("to") or "") == str(other):
            return edge
    for edge in ((rooms.get(other) or {}).get("adjacent") or ()):
        if isinstance(edge, dict) and str(edge.get("to") or "") == str(room):
            return edge
    return None


def is_active(charter, at_hours):
    """Is this the creature's hour. No authored phases, or a charter the
    story has not told when it is, means always."""
    creature = (charter or {}).get("creature")
    phases = (creature or {}).get("active_phases") or ()
    if not phases:
        return True
    from .day_cycle import charter_phase

    phase = charter_phase(charter, at_hours)
    return phase is None or phase in phases


def hunger_of(charter):
    """How far the fed upkeep stands from full, 0 sated to 1 starving; 0 for
    a creature that names none."""
    creature = (charter or {}).get("creature") or {}
    key = (creature.get("fed") or {}).get("upkeep") or ""
    upkeep = ((charter or {}).get("upkeeps") or {}).get(key)
    if not isinstance(upkeep, dict):
        return 0.0
    return round(_clamp(1.0 - number(upkeep.get("level"), 1.0)), 6)


def attack_odds(creature, hunger):
    """Chance one hunting body attacks at a shared place this window."""
    creature = creature or {}
    odds = number(creature.get("encounter_odds"), DEFAULT_ENCOUNTER_ODDS)
    boldness = number(creature.get("boldness"), DEFAULT_BOLDNESS)
    return _clamp(odds * (0.5 + _clamp(hunger)) * (0.5 + _clamp(boldness)))


def predator_capability(bodies, contest):
    """What the creature bodies standing here bring, together."""
    from .charter_harm import HURT_CAPABILITY, normalize_condition

    weight = number((contest or {}).get("capability"), 1.0)
    total = 0.0
    for body in bodies or ():
        each = weight
        if normalize_condition(body.get("condition")) == "hurt":
            each *= HURT_CAPABILITY
        total += each
    return total


def prey_capability(target, posted, company, contest):
    """What the target brings, with everyone standing beside it.

    ``company`` is the count of available prey bodies at the place
    INCLUDING the target; each extra one adds ``group_bonus`` of the
    target's own weight. A posted body beside an unposted one makes the
    place guarded for both, which is what a guard is for.
    """
    from .charter_harm import capability_of

    own = capability_of(target, posted=posted, weights=contest)
    bonus = number((contest or {}).get("group_bonus"),
                   DEFAULT_CONTEST["group_bonus"])
    return own * (1.0 + bonus * max(0, int(company) - 1))


def win_chance(predator, prey):
    """The predator's chance, from two capabilities."""
    total = float(predator) + float(prey)
    if total <= 0.0:
        return 0.0
    return float(predator) / total


def contest(predator, prey, draw):
    """Does the predator win, from two capabilities and a 0..1 draw."""
    return float(draw) < win_chance(predator, prey)


__all__ = [
    "DEFAULT_BOLDNESS", "DEFAULT_CONTEST", "DEFAULT_ENCOUNTER_ODDS",
    "DEFAULT_FED", "DEFAULT_KILL_CEILING", "DEFAULT_PREY",
    "DEFAULT_SENSE_RANGE_ROOMS", "DEFAULT_SPOOR_HOURS", "DEFAULT_STOCK_LOTS",
    "FOOTPRINT_MIN_ROOM", "PREY_CATEGORIES", "SPOOR_CAP", "attack_odds",
    "contest", "creature_neighbors", "creature_warnings", "hunger_of",
    "is_active", "normalize_creature", "normalize_spoor",
    "predator_capability", "prey_capability", "room_fits", "win_chance",
]
