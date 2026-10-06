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


#: Where a vista whose distance nobody gave is placed, for the curve and the
#: haze (`normalize_vista`).
_DEFAULT_DISTANCE_KM = 10.0


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

    def number(key, default, signed=False):
        raw = value.get(key)
        if raw is None or isinstance(raw, bool):
            return default
        try:
            out = float(raw)
        except (TypeError, ValueError):
            return default
        if not math.isfinite(out):
            return default
        return out if (signed or out >= 0) else default

    vid = str(value.get("id") or "").strip() or name.casefold().replace(" ", "_")
    distance = number("distance_km", None)
    # Whether the author SAID how far: the default places a vista for the
    # curve and the haze, and says nothing about which of two is the farther
    # (`composer.vista_percepts`). A stored vista keeps its flag through
    # every later read (review, 2026-10-05: re-derived from the stored
    # default, it read as given after the first write); one stored before the
    # flag existed holds the default as if it were authored, and is read as
    # given only where its distance is not that default.
    if "distance_given" in value:
        given = bool(value.get("distance_given")) and bool(distance)
    else:
        given = bool(distance) and distance != _DEFAULT_DISTANCE_KM
    return {"id": vid, "name": name, "desc": str(value.get("desc") or "").strip(),
            "bearing": bearing, "distance_km": distance or _DEFAULT_DISTANCE_KM,
            "distance_given": given,
            "height_m": number("height_m", 0.0, signed=True), "lit": bool(value.get("lit"))}


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


def beyond_the_horizon(vista, eye_m) -> bool:
    """Has the earth's curve taken the vista's TOP out of sight from this
    eye: is it further than the eye's horizon and the top's own together
    (d > sqrt(2 R' h_eye) + sqrt(2 R' h_top), R' the radius the refraction
    coefficient lengthens)? A top merely below the eye is not hidden -- a
    village seen from a tower is below the eye and in plain view; the old
    test asked whether the top stood below eye level and hid it
    (2026-10-05: a 20 m roof 1 km off from a 60 m eye). A top at or under
    the ground is never hidden by the curve: that is a valley, which
    terrain and nearer things decide (`obstructed`)."""
    if vista["height_m"] <= 0:
        return False
    radius = EARTH_RADIUS_M / (1.0 - REFRACTION_K)
    reach = (math.sqrt(2.0 * radius * max(eye_m, 0.0))
             + math.sqrt(2.0 * radius * vista["height_m"]))
    return vista["distance_km"] * 1000.0 > reach


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
    if vista["height_m"] > 0 and beyond_the_horizon(vista, eye_m):
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
    """(dark, moonlit) for the sky over a scene, ASKED OF THE DAY CYCLE:
    dark is whatever `day_cycle.SUN_LIGHT` calls dark for the phase, and the
    moon that lifts it is the one `day_cycle.sun_light` lifts the ground's
    light by. A second list here disagreed with the first: it counted night
    and pre-dawn only, so at 19:50 -- "evening", dark by the engine's own
    table -- the Larch Hill range still read as clear (2026-10-04)."""
    from world.day_cycle import SUN_LIGHT, sun_light
    phase = str((scene or {}).get("day_phase") or "").strip().casefold()
    dark = SUN_LIGHT.get(phase) == "dark"
    moonlit = dark and sun_light(phase, weather or {}) == "dim"
    return dark, moonlit


def outlooks(scene, room_id) -> Optional[set]:
    """The bearings a body in `room_id` can look out along: every bearing
    from open ground; through a window, an open door or bars onto open
    ground that sight crosses from here, that edge's bearing and the two
    beside it; none from a closed room (an empty set). None means "every
    way".

    ONE READER for the horizon and the far places (`landscape.outlook`), on
    DECLARED exposure: the inside of a thing (`parent_entity`) looks out
    nowhere whatever it declares -- a sheltered cabin aboard a ship saw
    every vista -- and a one-way pane looks out only from its seeing side.
    An outdoor room that declares nothing looks out nowhere until it does:
    the keyword guess `weather.room_exposure` falls back on read a tavern's
    staircase landing and a shrine's roost as open air, and an outlook is a
    sightline prose may not open (2026-10-05, the landscape panel)."""
    from world.landscape import outlook
    return outlook(scene, room_id)


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
    # THE BODY'S OWN ROOM IS BEHIND ITS WINDOW, and only when it has walls:
    # the storeys over a kitchen are its ceiling, not a wall in front of its
    # window. Open ground has no ceiling -- a mill standing in the field is
    # in front of the ridge behind it (2026-10-05: it was skipped with the
    # field's whole footprint, and hid nothing).
    from world.landscape import OPEN_GROUND, declared_ground
    own = (frozenset() if declared_ground(scene, rid) in OPEN_GROUND
           else site_cells(scene, rid))
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


def visible_vistas(scene, name, senses=None) -> list:
    """`[(vista, "clear" | "lights" | "silhouette")]` a body sees now: its
    room looks that way, the weather reaches that far, the dark leaves it --
    a lit one as its LIGHTS (its daytime `desc` is roofs and a spire no eye
    makes out at midnight), an unlit one as a silhouette under a moon -- and
    its top clears what stands nearer. Decided at the moment of looking;
    nothing is cached. `senses` is the body's card: an eye that sees
    nothing sees no horizon either (it saw both lines, 2026-10-05).

    WHICH WAY THE BODY FACES DOES NOT HIDE THE HORIZON. A view is part of
    where a body is, seen by turning its head, like the room it stands in;
    the walls and windows decide which way it can look, not the last thing
    it attended to. It was filtered by facing until a live run showed the
    facing is not the look: at Larch Hill (2026-10-04) Ren stood at the
    south windows looking for the town while her facing read north-west,
    derived from her attention on the man beside her, and the lit town was
    withheld as "behind" her."""
    from world.site_plan import EYE_M, body_altitude_m, room_elevation_m
    from world.spatial import posture_class, room_of, sense_adjusted
    vistas = scene_vistas(scene)
    rid = room_of(scene, name)
    if not vistas or not rid or sense_adjusted("full", "sight", senses) == "none":
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
            out.append((vista, ("lights" if dark and vista["lit"] else
                                "silhouette" if dark else "clear")))
    return out


def _fold_name(value) -> str:
    return " ".join(str(value or "").replace("_", " ").casefold().split())


def looked_vistas(scene, looks, name=None, senses=None) -> list:
    """The vistas a set of `look` values names: by id or by name -- the
    actor named it, so the name is theirs -- or by the compass point a vista
    this body can SEE stands on: "look south" is a look at what is in view
    to the south (chat 165: `south`, binoculars down the valley, never
    became the look event). A compass word carries no knowledge of what
    stands that way, so it finds only what is in view; matched to every
    vista on the bearing, a look south in a windowless cellar was told the
    name of a town it could not see, and remembered it (review
    2026-10-05)."""
    wanted = {_fold_name(v) for v in looks or () if str(v or "").strip()}
    bearings = {b for b in (normalize_bearing8(v) for v in looks or ()) if b}
    in_view = ({v["id"] for v, _how in visible_vistas(scene, name, senses=senses)}
               if bearings and name else set())
    return [v for v in scene_vistas(scene)
            if _fold_name(v["id"]) in wanted or _fold_name(v["name"]) in wanted
            or (v["bearing"] in bearings and v["id"] in in_view)]


def what_a_look_finds(scene, name, vista, senses=None) -> str:
    """"clear" | "lights" | "silhouette" when the vista is seen now, else
    "unseen": a look aimed at the range in fog finds that it cannot be made
    out."""
    for seen, how in visible_vistas(scene, name, senses=senses):
        if seen["id"] == vista["id"]:
            return how
    return "unseen"
