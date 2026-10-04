"""Vistas: what stands on the horizon -- mountains, a coastline, a skyline.

Far scenery is not a place. Nobody walks to the range in a scene, so it is
not a room; it is a record on the scene, seen from open air or through a
window facing its way, and hidden by weather, by night, and by anything
nearer that stands higher in its direction. Every
open-world game keeps the same split -- Skyrim's and Morrowind's distant
land are view-only and never simulated -- and the text tradition reaches
the same rules: TADS 3's `Distant` (examined, never touched), Discworld
MUD's terrain rooms (the view shrinks at night, in snow and behind forests).
(Prior-art survey, 2026-10-04; docs/design/DESIGN_SITE_PLAN.md.)

A vista is

    {"id", "name", "desc", "bearing": "n".."nw", "distance_km", "height_m",
     "lit": bool}

`desc` is how it looks from here (adv3Lite's `remoteDesc`); `lit` says it
shows at night -- a city's lights, a lighthouse, a burning tower. A vista is
SEEN and may be TALKED ABOUT; it is never a target of touch or movement
(Inform's authors' one standing complaint: a blanket "too far" refuses even
conversation about the hills).

Visibility is decided at the moment of looking, never cached (Inform's
backdrops, re-placed only on movement, stayed visible after the weather
changed).
"""
from __future__ import annotations

import math
from typing import Optional

#: The eight bearings, clockwise from north.
BEARINGS = ("n", "ne", "e", "se", "s", "sw", "w", "nw")

#: How far one can see, in kilometres, by what the air holds. Sourced where
#: the condition is DEFINED by visibility (WMO: fog < 1 km, mist 1-5 km, haze
#: <= 5 km; AMS/NWS: snow light >= 1 km, moderate 0.5-1, heavy < 0.5) and
#: kept generous for rain, which stays above a kilometre even when heavy
#: (field study, Milan, up to 40 mm/h). Clear air is effectively unbounded
#: at a story's scale. Engine numbers, owner-visible.
VISIBILITY_KM = {
    "clear": 200.0, "haze": 5.0, "mist": 3.0, "fog": 0.8, "dense_fog": 0.2,
    "light_rain": 10.0, "rain": 5.0, "heavy_rain": 2.0,
    "light_snow": 1.5, "snow": 0.8, "heavy_snow": 0.4,
    "dust": 1.0, "smoke": 1.0,
}

#: Mean Earth radius and the refraction coefficient viewshed tools use
#: (k ~ 0.13): a far peak sinks by (1 - k) d^2 / 2R -- 27 m at 20 km,
#: 171 m at 50 km.
EARTH_RADIUS_M = 6_371_000.0
REFRACTION_K = 0.13

#: Rooms are measured in paces (`site_plan.PACE_M`).
_PACE_M = 0.75


def normalize_bearing8(value) -> Optional[str]:
    word = str(value or "").strip().casefold().replace("-", "").replace(" ", "")
    names = {"north": "n", "northeast": "ne", "east": "e", "southeast": "se",
             "south": "s", "southwest": "sw", "west": "w", "northwest": "nw"}
    word = names.get(word, word)
    return word if word in BEARINGS else None


def normalize_vista(value) -> Optional[dict]:
    """A readable vista, or None: it needs a name and a bearing; distance
    and height default to a far, low skyline (10 km, 0 m) rather than being
    guessed upward."""
    if not isinstance(value, dict):
        return None
    name = str(value.get("name") or "").strip()
    bearing = normalize_bearing8(value.get("bearing"))
    if not name or not bearing:
        return None

    def number(key, default):
        raw = value.get(key)
        if raw is None or isinstance(raw, bool):
            return default
        try:
            out = float(raw)
        except (TypeError, ValueError):
            return default
        return out if math.isfinite(out) and out >= 0 else default

    vid = str(value.get("id") or "").strip() or name.casefold().replace(" ", "_")
    return {"id": vid, "name": name, "desc": str(value.get("desc") or "").strip(),
            "bearing": bearing, "distance_km": number("distance_km", 10.0) or 10.0,
            "height_m": number("height_m", 0.0), "lit": bool(value.get("lit"))}


def scene_vistas(scene) -> list:
    """Every readable vista the scene holds, in its own order."""
    raw = (scene or {}).get("vistas")
    if isinstance(raw, dict):
        raw = [dict(v, id=k) if isinstance(v, dict) else v for k, v in raw.items()]
    return [v for v in (normalize_vista(item) for item in (raw or ())) if v]


def bearing_gap(a, b) -> int:
    """Steps of 45 degrees between two bearings, 0-4."""
    i, j = BEARINGS.index(a), BEARINGS.index(b)
    d = abs(i - j) % 8
    return min(d, 8 - d)


def curvature_drop_m(distance_km) -> float:
    d = distance_km * 1000.0
    return (1.0 - REFRACTION_K) * d * d / (2.0 * EARTH_RADIUS_M)


def elevation_angle(vista, eye_m) -> float:
    """How high the vista's top stands above the level, in radians, from
    an eye `eye_m` metres above the ground the vista is measured from."""
    d = vista["distance_km"] * 1000.0
    return math.atan2(vista["height_m"] - eye_m - curvature_drop_m(vista["distance_km"]), d)


def visibility_km(air) -> float:
    """How far one sees through `air` (a `VISIBILITY_KM` word, a weather
    word the caller has folded to one), clear when it says nothing."""
    return VISIBILITY_KM.get(str(air or "clear").strip().casefold(), VISIBILITY_KM["clear"])


def vista_verdict(vista, *, air="clear", dark=False, eye_m=1.6) -> Optional[str]:
    """Why a vista is not seen, or None when it is, before anything nearer
    is asked (`obstructed` follows the line over the site plan):

    * "air" -- further than the weather lets anyone see;
    * "dark" -- night, and nothing on it is lit;
    * "below" -- the earth's curve has taken its top below the horizon.
    Its TOP must clear, not its foot: a range half hidden is still seen.
    """
    if vista["distance_km"] > visibility_km(air):
        return "air"
    if dark and not vista["lit"]:
        return "dark"
    if vista["height_m"] > 0 and elevation_angle(vista, eye_m) < -0.002:
        return "below"
    return None


# ---------------------------------------------------------------------------
# From a scene: the air, the dark, the way out, the horizon
# ---------------------------------------------------------------------------

def air_from_weather(weather) -> str:
    """The `VISIBILITY_KM` word for a weather record (`world/weather`): the
    thicker of what the air holds (`air`: hazy | thick) and what is falling
    (`precipitation_kind` liquid | frozen | particulate at `intensity`)."""
    weather = weather if isinstance(weather, dict) else {}
    words = []
    air = str(weather.get("air") or "clear").strip().casefold()
    words.append({"hazy": "haze", "thick": "fog"}.get(air, "clear"))
    from world.weather import is_falling
    if is_falling(weather):
        kind = str(weather.get("precipitation_kind") or "liquid").strip().casefold()
        how = str(weather.get("intensity") or "moderate").strip().casefold()
        step = {"light": 0, "moderate": 1, "heavy": 2}.get(how, 1)
        table = {"liquid": ("light_rain", "rain", "heavy_rain"),
                 "frozen": ("light_snow", "snow", "heavy_snow"),
                 "particulate": ("haze", "dust", "dust")}.get(kind)
        if table:
            words.append(table[step])
    return min(words, key=visibility_km)


def _darkness(scene, weather) -> tuple:
    """(dark, moonlit) for the sky over a scene: night and the hour before
    dawn are dark; a moon that lights the ground through clear air leaves the
    skyline as a silhouette."""
    from world.weather import moon_lights
    phase = str((scene or {}).get("day_phase") or "").strip().casefold()
    dark = phase in ("night", "pre-dawn")
    moonlit = dark and moon_lights(weather) and \
        str((weather or {}).get("cloud") or "") != "covered" and \
        str((weather or {}).get("air") or "clear") == "clear"
    return dark, moonlit


def outlooks(scene, room_id) -> Optional[set]:
    """The bearings a body in `room_id` can look out along: every bearing
    under open sky; through a window, an open door or bars onto an open-air
    room, that edge's bearing and the two beside it; none from a closed room
    (an empty set). None means "every way"."""
    from world.spatial import effective_adjacent, normalize_barrier
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(room_id) or {}
    if str(room.get("exposure") or "").strip().casefold() in ("open", "sheltered"):
        return None
    out = set()
    for edge in effective_adjacent(scene, room_id):
        if not isinstance(edge, dict):
            continue
        if normalize_barrier(edge.get("barrier")) not in (
                "window", "open", "open_door", "bars", "one_way_window"):
            continue
        other = rooms.get(str(edge.get("to"))) or {}
        if str(other.get("exposure") or "").strip().casefold() not in ("open", "sheltered"):
            continue
        b = normalize_bearing8(edge.get("dir"))
        if b:
            i = BEARINGS.index(b)
            out.update({BEARINGS[(i - 1) % 8], b, BEARINGS[(i + 1) % 8]})
    # The room's own windows onto open air with no room beyond (`windows`).
    for raw in room.get("windows") or ():
        b = normalize_bearing8(raw)
        if b:
            i = BEARINGS.index(b)
            out.update({BEARINGS[(i - 1) % 8], b, BEARINGS[(i + 1) % 8]})
    return out


_UNIT8 = {b: (math.sin(math.radians(45 * i)), -math.cos(math.radians(45 * i)))
          for i, b in enumerate(BEARINGS)}


def obstructed(scene, name, vista, eye_z) -> bool:
    """Does something nearer stand in the line from a body's eye to a
    vista's top, on the body's site plan? The line is followed outward along
    the vista's bearing at the vista's own rise; it is cut where its height
    falls inside an enclosed room's slab (floor to ceiling) standing there,
    or below open ground standing higher. The body's own room's footprint is
    behind its window and is skipped -- the storeys above a kitchen are its
    ceiling, not a wall in front of its window (live, Larch Hill 2026-10-04:
    read as a column, they put the kitchen's horizon at 87 degrees)."""
    from world.site_plan import (PACE_M, STOREY_M, plan_point, room_elevation_m,
                                 room_site, site_cells, site_plans, _open_air)
    from world.spatial import room_of
    rid = room_of(scene, name)
    site = room_site(scene, rid) if rid else None
    point = plan_point(scene, name) if site else None
    if not point:
        return False
    own = site_cells(scene, rid)
    slabs: dict = {}
    for levels in site_plans(scene).get(site["plan"], {}).values():
        for other in levels:
            if other == rid:
                continue
            floor = room_elevation_m(scene, other)
            span = (float("-inf"), floor) if _open_air(scene, other) else (floor, floor + STOREY_M)
            for cell in site_cells(scene, other):
                if cell not in own:
                    slabs.setdefault(cell, []).append(span)
    if not slabs:
        return False
    rise = math.tan(elevation_angle(vista, eye_z))
    ux, uy = _UNIT8[vista["bearing"]]
    reach = max(math.hypot(c[0] + 0.5 - point[0], c[1] + 0.5 - point[1]) for c in slabs) + 2
    for i in range(1, int(reach * 2) + 1):
        t = i / 2.0
        cell = (math.floor(point[0] + ux * t), math.floor(point[1] + uy * t))
        z = eye_z + t * PACE_M * rise
        if any(lo <= z <= hi for lo, hi in slabs.get(cell, ())):
            return True
    return False


def visible_vistas(scene, name) -> list:
    """`[(vista, "clear" | "silhouette")]` a body sees now: its room looks
    that way, the weather reaches that far, the dark leaves it (lit, or a
    silhouette under a moon), and its top clears what stands nearer. Decided
    at the moment of looking; nothing is cached.

    WHICH WAY THE BODY FACES DOES NOT HIDE THE HORIZON. A view is part of
    where a body is, seen by turning its head, like the room it stands in;
    the walls and windows decide which way it can look, not the last thing
    it attended to. It was filtered by facing until a live run showed the
    facing is not the look: at Larch Hill (2026-10-04) Ren stood at the
    south windows looking for the town while her facing read north-west,
    derived from her attention on the man beside her, and the lit town was
    withheld as "behind" her."""
    from world.site_plan import EYE_M, body_altitude_m, room_elevation_m
    from world.spatial import posture_class, room_of
    vistas = scene_vistas(scene)
    rid = room_of(scene, name)
    if not vistas or not rid:
        return []
    ways = outlooks(scene, rid)
    if ways is not None and not ways:
        return []
    weather = (scene or {}).get("weather") or {}
    air = air_from_weather(weather)
    dark, moonlit = _darkness(scene, weather)
    eye_z = room_elevation_m(scene, rid) + body_altitude_m(scene, name) + \
        EYE_M.get(posture_class(scene, name), EYE_M["standing"])
    out = []
    for vista in vistas:
        if ways is not None and vista["bearing"] not in ways:
            continue
        why = vista_verdict(vista, air=air, dark=dark and not moonlit, eye_m=eye_z)
        if why is None and obstructed(scene, name, vista, eye_z):
            why = "below"
        if why is None:
            out.append((vista, "silhouette" if dark and not vista["lit"] else "clear"))
    return out
