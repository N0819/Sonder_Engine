"""BUILDING LOTS: one planned place standing for a whole building nobody has
been inside yet, turned into that building's rooms when the player or a
major character first comes upon it.

The owner's idea (2026-10-28), after a walk into an unplanned village built
the whole village as one six-by-eight-pace room and its shop as one room
more: "mark spaces as a building generation for when an actor like a player
or major character stumble upon it. These marked spaces can act as homes and
work places for charter npcs." A town is then planned as its ways and its
lots -- what each building is, how it looks from outside, which way it fronts
-- and a building is designed only where a story goes into it, as the room
designer already builds a room only where a body nears it.

A LOT IS A PLANNED ROOM CARRYING A `lot` RECORD (`LOT_KEY`, `normalize_lot`):
one row of the registry, so everything that names a place -- a charter
body's berth or post, a join from the street, a far look, a memory -- names
it by its uid, and the uid never moves. Until it is expanded it is the
building seen from outside: an enclosed place on its street, a home or a
workplace to the charter, a shape on the far view. No room of a beat or of
the rooms-in-view job designs it as one room (`agents/director_lots.py`).

EXPANDED, THE LOT IS ITS BUILDING'S ENTRY: the architect's call says which
rooms the building holds and how they join (`agents.director_lots.
expand_lot`); the room the outside door opens into keeps the lot's uid, its
name and its joins onto the ground, and every other room is a new planned
room of the lot's own part of the map carrying `lot_of` (`LOT_OF_KEY`), the
mark the layout tier reads as "these rooms are one building", whatever
storeys it has (`layout_bridge.plan_buildings`). The lot's record stays on
its entry with the turn it was expanded, so it is expanded once.

Pure: no model, no database.
"""
from __future__ import annotations

#: On a planned spec: the lot's own record (`normalize_lot`).
LOT_KEY = "lot"
#: On each room a lot was expanded into, its entry included: the lot's uid.
LOT_OF_KEY = "lot_of"
#: The most storeys above the ground a lot may ask for. A tower or a tall
#: town house is four; past it the architect's one call is asked for more
#: rooms than it plans well. Named per ask-before-limiting.
LOT_STOREYS_MAX = 4
#: The most rooms one expansion plants, its entry included. A farmhouse, an
#: inn or a merchant's house with its shop and store comes to eight to
#: twelve; the layout tier lays out up to `layout_bridge.
#: LAYOUT_TIER_MAX_ROOMS` (24) with its stair rooms. Named per
#: ask-before-limiting.
LOT_ROOMS_MAX = 14


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def normalize_lot(value):
    """The lot record as the engine reads it, or None for no lot.

    `true` or `{}` is a lot with nothing said. Otherwise `storeys` -- how
    many storeys stand above the ground, 1 to `LOT_STOREYS_MAX`, absent for
    the architect to decide; `cellar` -- whether a storey lies below it.
    Written by the engine alone, once the lot is expanded: `expanded`, the
    turn; `building`, the purpose the lot carried, which said what the whole
    building is before its entry took a purpose of its own; `footprint`, the
    extent it carried, the whole building's. Anything else is dropped."""
    if value is True:
        return {}
    if not isinstance(value, dict):
        return None
    out = {}
    storeys = _int(value.get("storeys"))
    if storeys is not None and storeys >= 1:
        out["storeys"] = min(storeys, LOT_STOREYS_MAX)
    if value.get("cellar") is True:
        out["cellar"] = True
    expanded = _int(value.get("expanded"))
    if expanded is not None and expanded >= 0:
        out["expanded"] = expanded
    building = " ".join(str(value.get("building") or "").split())[:400]
    if building:
        out["building"] = building
    footprint = value.get("footprint")
    if isinstance(footprint, dict):
        w, d = _int(footprint.get("w")), _int(footprint.get("d"))
        if w and d and w > 0 and d > 0:
            out["footprint"] = {"w": w, "d": d}
    return out


def lot_marks(raw) -> dict:
    """The lot fields a planned room carries through planting
    (`structure.plant_structure`): its `lot` record, read, and the lot it was
    expanded from. `{}` for a room that is neither."""
    raw = raw if isinstance(raw, dict) else {}
    out = {}
    lot = normalize_lot(raw.get(LOT_KEY))
    if lot is not None:
        out[LOT_KEY] = lot
    of = str(raw.get(LOT_OF_KEY) or "").strip()
    if of:
        out[LOT_OF_KEY] = of
    return out


def is_unexpanded_lot(planned) -> bool:
    """Whether a planned spec is a lot still waiting for its building."""
    if not isinstance(planned, dict):
        return False
    lot = normalize_lot(planned.get(LOT_KEY))
    return lot is not None and "expanded" not in lot


def unexpanded_lots(rows) -> set:
    """The uids among registry `rows` (`structure.registry_rows`) that are
    lots still waiting for their building."""
    return {uid for uid, entry in (rows or {}).items()
            if is_unexpanded_lot((entry or {}).get("planned"))}
