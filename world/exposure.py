# exposure.py
"""Ambient discomfort from the sky: what the WEATHER costs a body standing in it.

`world/comfort.py` is this module's twin and its opposite. Comfort is the
world's deterministic PLEASURE floor -- a featherbed and a hearth reaching
`resolve_hedonic` whether or not a model thought to mention them. Pain already
had a world-side floor for injury and bad air, and nothing at all for the
weather: a character bare-armed in freezing rain felt exactly what the one at
the hearth felt unless the model said so, and the model says so about a third
of the time. Review 2026-09-07 D20; built on A88's axes in the same change.

FOUR RULES, and the first three are comfort's read backwards.

**1. It reaches the body the way comfort does and no other way.** One reader,
`persist/commit_memory.py`, hands it to `resolve_hedonic` as a floor on the
pain LEVEL. It never touches `charge` -- being cold is a resolved state a body
is in, not an unresolved drive demanding release -- and it is never
navigational pull. A body that wants to get out of the rain wants that because
it feels the rain, which is what this is for.

**2. It reads AXES, never names** (A88). `world/weather.weather_for_room`
answers what this body's room actually gets of the sky, and what this module
asks of that answer is: how cold or hot is it, does the wind reach here, is
anything landing on this body, and does what is landing WET it. A fall of ash
and a fall of blood are different stories and the same arithmetic; a fall
whose kind nothing stated asserts nothing about wetness at all, which is the
conservative direction because the alternative is inventing a soaking.

**3. What it does not know, it does not assert.** Indoors is nothing: the
module's own rule is that an enclosed room gets no weather, and a cellar under
a blizzard is a cellar. A body with no attire entry at all is not a naked body
-- it is a story that never wrote clothing down -- so it takes the fully
clothed reading. (`world/stimulation.py` reads the same silence the other way
round, and for the same reason: its question is "is there anything between",
where a naked default would GRANT reach. Both directions subtract.)

**4. Habituation is deferred, deliberately.** Comfort halves on a sustained
source, because the tenth beat on a cushion is not the first. Cold is not
obviously the same: a body that stops noticing the cold is a body in trouble,
and whether that reads as habituation or as its opposite is a design question
and not a constant. Until it is answered this floor is flat -- and it is
CAPPED, so flat cannot mean overwhelming.
"""

from __future__ import annotations

from story import attire as attire_model
from world.spatial import room_of
from world.weather import weather_for_room

#: The absolute ceiling on world-contributed discomfort, and the deliberate
#: twin of `comfort.COMFORT_CEILING`, which is 0.3. Named per the house rule
#: on caps: it means the weather alone can never carry a body past a pain
#: level of 0.3, however long it stands in it and however little it has on.
#: What it drops is the difference between severe weather and catastrophic --
#: standing in a blizzard and standing in a worse blizzard read the same here,
#: and a beat that wants more than 0.3 of pain out of the sky has to say so as
#: an event, which is the Director's to write.
DISCOMFORT_CEILING = 0.3

#: What each rung of the temperature axis costs a body standing in it, before
#: clothing, wind, wet and fatigue. Mild is free by construction: it is the
#: axis word for "weather a body does not have to think about".
#: Scaled against DISCOMFORT_CEILING, not against 1.0: freezing still air on a
#: fully dressed body reads a little under half the ceiling, and reaching the
#: ceiling takes the cold AND the wind AND the wet AND a bare body. Before
#: this scaling a cold drizzle on two bare regions already saturated, which
#: made every worse sky read identically to it.
_TEMPERATURE_COST = {
    "freezing": 0.30, "cold": 0.12, "mild": 0.0, "warm": 0.03, "hot": 0.16,
}

#: What moving air adds. It is a MULTIPLIER on cold and not a term of its own,
#: because wind is how cold reaches a body: a gale on a mild day is loud and
#: it is not painful, and the same gale at freezing is the difference between
#: uncomfortable and dangerous.
_WIND_CHILL = {"still": 1.0, "breeze": 1.05, "wind": 1.25, "gale": 1.5}

#: What being rained on adds, by how hard it is coming down. A term of its own
#: rather than a multiplier: being soaked is its own misery at any temperature,
#: and it also raises the chill, below.
_WET_COST = {"none": 0.0, "light": 0.03, "moderate": 0.07, "heavy": 0.12}

#: How much of the sky a body at each exposure is actually standing in. An
#: enclosed room is zero, which is this module's whole indoor answer -- the
#: weather does not reach in, and asserting a cost there would be asserting
#: weather in a cellar.
_EXPOSURE_REACH = {"open": 1.0, "sheltered": 0.5, "enclosed": 0.0}

#: How much of the weather clothing keeps off. A fully covered body pays this
#: much less than a bare one; a body with half its regions bare pays half the
#: relief. It is not immunity: a coat in a blizzard is still a body in a
#: blizzard.
_CLOTHED_RELIEF = 0.55

#: A spent body feels the weather more, the same shape (and the same gain) as
#: comfort's `_COMFORT_RELIEF_GAIN`: a chair is worth more to a tired body,
#: and so is a doorway out of the rain.
_FATIGUE_GAIN = 0.8


def _bare_fraction(scene, name):
    """How much of this body the weather is landing on directly, 0.0-1.0.

    Regions the story never wrote read as covered, and a body with no attire
    entry at all reads as fully covered -- rule 3. `attire.REGIONS` is the
    denominator, so "half bare" means half the regions this engine models and
    not half of some other count.

    THE RECORDED SET COMES FROM THE RAW LEDGER, not the normalised one:
    `attire.normalize_regions` DROPS a region with nothing left on it, which
    is exactly the region this is asking about. Read off the normalised map
    alone, a body stripped to the waist and a body nobody dressed answer
    identically -- both zero -- and the feature is a constant. So the raw map
    says which regions this story has written down, and the normalised map
    says which of those still have something on them.
    """
    attire = (scene or {}).get("attire") if isinstance(scene, dict) else None
    entry = attire_model.entry_for(attire, name) \
        if isinstance(attire, dict) else None
    if not isinstance(entry, dict):
        return 0.0
    recorded = entry.get("regions")
    recorded = recorded if isinstance(recorded, dict) else {}
    if not recorded:
        return 0.0
    covered = attire_model.normalize_regions(entry)
    bare = sum(1 for region in attire_model.REGIONS
               if region in recorded
               and not attire_model.region_is_covered(covered, region))
    return bare / float(len(attire_model.REGIONS))


def _wets(scoped):
    """Does what is falling here WET a body it lands on?

    The axis and nothing else. Liquid wets. Frozen wets when it is not cold
    enough for it to stay solid on the skin -- which is the same fact
    `weather._ground_ladder` reads to decide between a piled floor and a
    slushy one. Particulate does not, and `other` is a fall the story named
    without saying what it does, so this asserts nothing about it.
    """
    kind = str((scoped or {}).get("precipitation_kind") or "none")
    if kind == "liquid":
        return True
    if kind == "frozen":
        return str((scoped or {}).get("temperature") or "") != "freezing"
    return False


def _derive(scene, name, body_state=None):
    scene = scene if isinstance(scene, dict) else {}
    label = str(name or "").strip()
    room_id = room_of(scene, label) if label else None
    if not room_id:
        return 0.0, ""
    scoped = weather_for_room(scene, room_id)
    if not scoped:
        return 0.0, ""
    reach = _EXPOSURE_REACH.get(str(scoped.get("exposure") or ""), 0.0)
    if not reach:
        return 0.0, ""

    temperature = str(scoped.get("temperature") or "mild")
    cold = _TEMPERATURE_COST.get(temperature, 0.0)
    landing = bool(scoped.get("falls_on_you"))
    soaked = landing and _wets(scoped)
    # ONLY a fall that wets costs anything on its own. A fall this engine
    # was given no kind for is a fall it declines to price -- the alternative
    # is inventing a soaking out of a word (A88's defect, one layer down).
    wet = _WET_COST.get(str(scoped.get("intensity") or "none"), 0.0) \
        if soaked else 0.0
    wind = str(scoped.get("wind") or "still")
    chill = _WIND_CHILL.get(wind, 1.0) if scoped.get("wind_reaches") else 1.0
    # Wet clothing stops being clothing. A soaking multiplies the chill by the
    # same rung a gale does, which is the one place these three axes are not
    # independent of each other.
    if soaked and temperature in ("freezing", "cold"):
        chill *= _WIND_CHILL["wind"]

    raw = cold * chill + wet
    if raw <= 0.0:
        return 0.0, ""

    bare = _bare_fraction(scene, label)
    raw *= 1.0 - _CLOTHED_RELIEF * (1.0 - bare)
    fatigue = 1.0 - max(0.0, min(1.0, _float(
        (body_state or {}).get("stamina"), 1.0)))
    raw *= 1.0 + _FATIGUE_GAIN * fatigue
    level = min(DISCOMFORT_CEILING, raw * reach)
    if level <= 0.0:
        return 0.0, ""

    # The cause, in the story's own nouns where it has them: the fall carries
    # whatever this fiction called it (A88), so "heavy ashfall" and "heavy
    # rain" reach the character's own state as themselves.
    parts = []
    if cold:
        parts.append(temperature)
    if soaked:
        parts.append("%s %s" % (scoped.get("intensity"),
                                scoped.get("precipitation")))
    if scoped.get("wind_reaches") and wind not in ("still", "breeze"):
        parts.append(wind)
    source = "standing out in %s" % ", ".join(parts) if parts else \
        "standing out in the weather"
    return round(level, 4), source


def _float(value, default=0.0):
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return default if out != out else out


def discomfort_level(scene, name, body_state=None):
    """(level 0.0..DISCOMFORT_CEILING, source string) of ambient discomfort.

    Derived from the settled scene and nothing else: where this body is, what
    that room gets of the sky, what the body has on, and how spent it is.
    (0.0, "") indoors, in a scene with no weather, for a body the scene does
    not place, and for weather that costs a body nothing -- which is most
    weather, most of the time.

    `body_state` is `survival.vitals_of` for this body, read for `stamina`
    alone. Omitted (a caller with no vitals, a story with survival off), the
    fatigue term collapses to 1.0 rather than inventing a body the story
    deliberately turned off.
    """
    return _derive(scene, name, body_state)
