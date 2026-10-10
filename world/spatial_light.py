# spatial_light.py
"""Illumination: the light ladder, source aggregation with radius falloff,
per-room and per-position light, and the light-to-sight ceiling."""

from typing import Optional

from world.scene_memo import scene_memo
from world.spatial_barriers import (
    _SIGHT_BARRIERS, effective_adjacent, normalize_barrier)
from world.spatial_geometry import (
    _DOOR_ANCHOR_PREFIX, door_anchor_id, effective_anchors, proximity_rel)
from world.spatial_identity import (
    PositionsIndex, normalize_room_id, room_of, room_of_record,
    room_spellings, same_subject)
from world.spatial_orientation import _BEARING_DEG, normalize_bearing


# ---------------------------------------------------------------------------
# LIGHT -- the other half of sight.
#
# Sight was decided entirely by barriers: whether something stood between two
# rooms, and whether you could see through it. Whether there was any light to
# see BY did not exist. A pitch-black cellar and a sunlit hall were identical
# to the engine, which for a system whose whole purpose is to stop a mind
# knowing what it did not perceive is the largest hole in that promise --
# darkness is the most ordinary perception gate there is.
#
# Absent means lit, so every existing scene behaves exactly as before. This is
# the same fail-open the awareness gate and scale use.
LIGHT_LEVELS = ("dark", "dim", "lit", "bright")
_LIGHT_ALIASES = {
    "": "lit", "none": "dark", "pitch_dark": "dark", "pitch black": "dark",
    "pitch_black": "dark", "black": "dark", "unlit": "dark", "blackout": "dark",
    "lightless": "dark", "gloom": "dim", "dusk": "dim", "twilight": "dim",
    "shadowed": "dim", "shadowy": "dim", "murky": "dim", "faint": "dim",
    "candlelit": "dim", "moonlit": "dim", "half_light": "dim", "low": "dim",
    "normal": "lit", "daylight": "lit", "well_lit": "lit", "well lit": "lit",
    "bright": "bright", "glaring": "bright", "blinding": "bright",
    "floodlit": "bright", "sunlit": "lit", "harsh": "bright",
}


def normalize_light(value) -> str:
    level = str(value or "").strip().casefold().replace(" ", "_")
    level = _LIGHT_ALIASES.get(level, level)
    return level if level in LIGHT_LEVELS else "lit"


def room_light(scene: dict, room_id: str) -> str:
    """The light a room has of its own, before anything spills into it.

    OUTDOORS, THE SKY IS THE CEILING. A room the weather reaches (its
    exposure is `open` or `sheltered`, `world/weather.room_exposure`) has
    the sun for its ambient light once the scene knows what phase of the day
    it is (`scene.day_phase`, written by the scene commit from the clock --
    `world/day_cycle`): dark through the night, dim at dawn and dusk, lit by
    day, one step dimmer under fog or cloud. A declared `light` on such a
    room may only DARKEN that -- a shadowed alley at noon is dim -- never
    brighten it, because a lamp is a light SOURCE and lives on an entity,
    where `source_light` counts it, not on the room. Which is the rule that
    makes a square go dark at night without anyone re-declaring it, and a
    torch in that square light it again without anyone re-declaring that.

    SOURCES DECIDE WHERE THE ENGINE CAN SEE SOURCES; WHERE IT CAN SEE NONE,
    THE DECLARATION IS THE EVIDENCE (owner's decision, 2026-09-05, F40 of
    `docs/experiments/DEBUG_RUN_2026_09_05.md`). The rule above is right
    about a square and wrong about a covered place nobody wrote a lamp into:
    chat 114's console room -- "bathed in amber and greenish light",
    `light: lit`, `exposure: sheltered`, holding no entity with
    `light_source` -- composed "It is dark here." in EVERY view for four
    turns while the narrator wrote the amber warmth of the chamber. So in a
    room that is not `open`, where the declared word stands ABOVE what the
    sky gives it and the room holds no light source of its own, the word
    stands as a floor: it is the only thing in the scene that knows about
    the lamp nobody wrote as an entity. The exclusions are the rule, not
    exceptions to it:

      * `open` is untouched. There is no roof to hide a lamp under, so the
        sky is that room's whole account and a word above it is simply
        wrong -- the moonlit shore stays dark at night.
      * A room that HOLDS a source is decided by its sources, switched off
        included: the account exists, so the word cannot overrule it, and
        putting the braziers out darkens a sheltered hall at midnight. That
        is the same direction as `ambient_floor_word`'s PA3 repair one
        module over (`world/spatial_light_field.py`), which lets an
        `enclosed` room's dead fixtures darken its word. The pair is one
        rule read from both ends.
      * A room that declares NOTHING declares nothing. An absent `light`
        reads as `lit` by the fail-open at the top of this module, and a
        fail-open is not a claim, so every scene that never said a word
        about its light is byte for byte what it was.

    `unsourced_light_rooms` is the engine notice that asks the Director to
    write the source. It used to report exactly the rooms this branch fires
    on and no longer does: whether a word may STAND is the sky rule's
    question and belongs here, while whether a room wants a source written
    is asked of every room, indoors included.

    Indoors -- or in a scene that has never said what time it is, or a room
    the exposure reader cannot place, which it reads as indoors -- the
    declared light stands exactly as it always has.
    """
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict):
        return "lit"
    declared = normalize_light(room.get("light"))
    phase = str((scene or {}).get("day_phase") or "").strip()
    if not phase:
        return declared
    from world.weather import room_exposure
    exposure = room_exposure(scene, room_id)
    if exposure == "enclosed":
        return declared
    sky = _sky_light(scene, phase)
    if _declaration_is_the_only_account(scene, room_id, room, exposure,
                                        declared, sky):
        return declared
    return _darker(sky, declared)


def _sky_light(scene: dict, phase: str) -> str:
    """What the sky alone gives a room the weather reaches, this phase."""
    from world.day_cycle import sun_light
    from world.weather import normalize_weather
    weather = (scene or {}).get("weather")
    # The whole record, not the sky's NAME: what dims a day is an axis since
    # A88, and normalising here is what recovers those axes for a scene stored
    # before they existed.
    record = normalize_weather(weather) or None
    # ONE MOON, NOT TWO. The sky's `moon` axis is the engine's account of the
    # night, and a story may ALSO have written the moon as a scene entity so it
    # can carry a `light_source` -- the owner's chat 151 holds `The Moon`,
    # `kind: "celestial"`, `state: {"phase": "full"}`, beside a sky whose prose
    # names the same full moon. Two records of one fact can only disagree, and
    # the one the story wrote as an object is the more explicit of the two: a
    # declared `phase` outranks a phase read out of the sky's wording. Where no
    # celestial entity carries one, the axis stands as it was.
    if record is not None:
        phase_word = _celestial_phase(scene)
        if phase_word:
            record = dict(record, moon=phase_word)
    return sun_light(phase, record)


def _celestial_phase(scene):
    """The phase a `celestial` scene entity declares, folded onto the moon axis,
    or "". First such entity wins; a scene with two moons is a fiction this
    reader has nothing to say about and leaves to the sky's own axis."""
    from world.weather import MOONS, _moon_in_prose
    for record in ((scene or {}).get("entities") or {}).values():
        if not isinstance(record, dict):
            continue
        if str(record.get("kind") or "").strip().casefold() != "celestial":
            continue
        state = record.get("state")
        word = str((state or {}).get("phase") or "").strip().casefold() \
            if isinstance(state, dict) else ""
        if word in MOONS:
            return word
        # A phase written as a phrase ("waxing gibbous") is read the same way
        # the sky's own prose is, so one spelling table serves both.
        folded = _moon_in_prose(word)
        if folded:
            return folded
    return ""


def _declaration_is_the_only_account(scene, room_id, room, exposure,
                                     declared, sky) -> bool:
    """Is this room's own light WORD the only account of its light, and is
    it brighter than the sky leaves it? The F40 branch of `room_light`,
    factored out so the branch has one spelling.

    The room must actually carry a word (an absent `light` is a fail-open,
    not a declaration), stand under a roof but not sealed under one
    (`sheltered`: `open` has no roof to hide a source under and `enclosed`
    never reaches the sky rule at all), claim more light than the sky gives
    it, and hold no light source of its own.

    WHAT COUNTS AS THE ROOM'S OWN SOURCE is `_room_fixtures`, the same
    reading PA3 makes: a thing that FILLS the room and stands in it, lit or
    not. A hand light someone carried in is not the room's account of
    itself -- it makes a pool and it leaves with its bearer -- so a doused
    lantern in a stranger's fist neither darkens the room nor silences the
    notice.
    """
    if exposure != "sheltered" or not str(room.get("light") or "").strip():
        return False
    if _LIGHT_ORDER.get(declared, 2) <= _LIGHT_ORDER.get(sky, 2):
        return False
    from world.spatial_light_field import _room_fixtures
    return not _room_fixtures(scene, room_id)


def unsourced_light_rooms(scene: dict) -> list:
    """`[(room_id, declared, otherwise)]` for every room whose light is
    claimed by a WORD and accounted for by nothing else in the scene --
    `otherwise` being the light everything but the word leaves it.

    A ROOM THAT SAYS IT IS LIT AND HOLDS NOTHING THAT MAKES LIGHT WANTS A
    SOURCE, wherever it stands. This began (F40) as the sky rule's own
    reader: a `sheltered` room whose word outranked the sun was the only
    room reported, because that was the only place `room_light` let a word
    stand. That scope was the sky rule's, not this question's, and indoors
    is where the question actually lives. Measured across three runs of the
    2026-09-05 campaign: a parlour whose scenario opened on "a fire in the
    grate" came out with a `hearth` ANCHOR, five minted objects and no fire,
    all three rooms `dim`, and thirteen beats went by before a specialist
    said outright that the grate was "absent from entity indexes" (PQ1); a
    tenement burning down for twenty beats committed `light_source: []` and
    `sound_source: []` (PR6); a ball "hung with lamps" produced five
    entities and not one source (PX7). In all three the engine was silent,
    because the rooms were `enclosed` and the sky rule never looked at them.

    What ACCOUNTS for a room's light, and the two exclusions are the rule:

      * a room that declares NOTHING declares nothing. An absent `light` is
        the fail-open at the top of this module, and a fail-open is not a
        claim -- so a scene that never said a word about its light is
        reported exactly as before, which is not at all.
      * a room that HOLDS a fixture has an account already, lit or out
        (`_room_fixtures`, the reading PA3 makes). The source is written;
        whether it is burning is the story's business, not this notice's.
      * `dark` claims no light, so there is nothing to source.

    The word is honoured either way -- this asks the Director for the thing
    that lights the room, it never darkens one. `unsourced_light_notices`
    composes the sentences; `merge_scene_with_diff` appends them to
    `light_report`, and the commit hands that to `ctx.tell_director`.
    """
    rooms = (scene or {}).get("rooms") or {}
    if not isinstance(rooms, dict):
        return []
    from world.spatial_light_field import _room_fixtures
    from world.weather import room_exposure
    phase = str((scene or {}).get("day_phase") or "").strip()
    sky = _sky_light(scene, phase) if phase else None
    out = []
    for room_id in sorted(rooms):
        room = rooms.get(room_id)
        if not isinstance(room, dict):
            continue
        if not str(room.get("light") or "").strip():
            continue
        declared = normalize_light(room.get("light"))
        # What the room would read on everything BUT its word: the sky where
        # the weather reaches it, and otherwise nothing at all -- an enclosed
        # room with no fixture in it has no other account of its light.
        otherwise = "dark"
        if sky and room_exposure(scene, room_id) != "enclosed":
            otherwise = sky
        if _LIGHT_ORDER.get(declared, 2) <= _LIGHT_ORDER.get(otherwise, 2):
            continue
        if _room_fixtures(scene, room_id):
            continue
        out.append((str(room_id), declared, otherwise))
    return out


#: How many rooms one beat's light notice NAMES before it counts the rest.
#: An establish mints a whole building at once, so an uncapped notice is a
#: paragraph per beat for as long as the Director declines to mint a lamp --
#: PR6's tenement would have run ten rooms wide, every beat, for twenty
#: beats. Three is enough for the Director to see the class and act on it.
UNSOURCED_LIGHT_NOTICE_ROOMS = 3


def unsourced_light_notices(scene: dict) -> list:
    """One engine notice per room that wants a light source, capped at
    `UNSOURCED_LIGHT_NOTICE_ROOMS` with a tail counting the rest.

    Rooms somebody is STANDING in come first: a room's light matters this
    beat where a body is in it, and the rest of the building can wait for
    the beat that walks into it.
    """
    rooms = (scene or {}).get("rooms") or {}
    occupied = {str(where) for where in
                ((scene or {}).get("positions") or {}).values() if where}
    wanted = sorted(unsourced_light_rooms(scene),
                    key=lambda row: (row[0] not in occupied, row[0]))
    out = []
    for room_id, declared, otherwise in wanted[:UNSOURCED_LIGHT_NOTICE_ROOMS]:
        room = rooms.get(room_id) or {}
        label = str(room.get("name") or room_id)
        out.append(
            "%r is declared `light: %s` and nothing in the scene accounts "
            "for that light: it holds no light source of its own, and "
            "everything else about it leaves it %s. The room's word stands, "
            "so nobody is in the dark for this. But a thing the story can "
            "change is an ENTITY, and a thing that only says where an entity "
            "stands is an anchor -- so if something in there gives that "
            "light, write it as an entity with `light_source` and a "
            "position, and it can then be seen, moved, put out, carried and "
            "lit from where it stands. If nothing gives it, the room's "
            "`light` should say what it is actually left with."
            % (label, declared, otherwise))
    rest = len(wanted) - len(out)
    if rest > 0:
        out.append("%d more room%s in this scene declare a light nothing in "
                   "them accounts for." % (rest, "" if rest == 1 else "s"))
    return out


_LIGHT_ORDER = {"dark": 0, "dim": 1, "lit": 2, "bright": 3}


def _brighter(a, b):
    return a if _LIGHT_ORDER.get(a, 2) >= _LIGHT_ORDER.get(b, 2) else b


def _darker(a, b):
    return a if _LIGHT_ORDER.get(a, 2) <= _LIGHT_ORDER.get(b, 2) else b


def source_light(scene: dict, room_id: str, *, filling_only=False) -> str:
    """The brightest ACTIVE light source in this room.

    A room's own `light` is what the place provides -- a window, a fixture, the
    sun. This is what someone brought with them: a torch, a lantern, a
    phone-screen, a burning brand. Without it, a character standing in a
    lightless cellar holding a lit lamp still saw nothing, which is the obvious
    way for a room-level model to be wrong.

    A carried source travels for free: an entity being carried already has its
    holder's position derived onto it (derive_contained_positions), so the lamp
    is wherever its bearer is without anything here needing to know who is
    holding what.

    Nothing here is specific to carrying. Any entity with `light_source` lights
    the room it is in, so every way a story makes light works the same way and
    none of them needed their own case: a campfire built this beat, a brazier,
    a hearth, a lamp switched on, a glowing rune, a burning wreck. Building one
    is creating an entity with `light_source` and a position -- which is what
    creating a campfire already was.

    Declared as `light_source` on the entity -- the level it EMITS -- and
    switched off with state.lit false, so a doused torch stops lighting the
    room without ceasing to be a torch.

    `filling_only` counts just the sources that light a whole room. A hand
    torch does not: it makes a pool of light around whoever holds it and leaves
    the rest of the room dark, which is `light_at`'s business, not this one's.
    """
    entities = (scene or {}).get("entities") or {}
    if not isinstance(entities, dict) or not room_id:
        return "dark"
    # One folded read of `positions` for the whole sweep (B18): the walk is
    # three labels per emitter, and each one otherwise rescans the table.
    index = PositionsIndex((scene or {}).get("positions") or {})

    best = "dark"
    for eid, entity in entities.items():
        if not isinstance(entity, dict) or not entity.get("light_source"):
            continue
        state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
        lit = state.get("lit", True)
        if lit in (False, 0, "off", "false", "no", "doused", "out"):
            continue
        where = room_of_record(scene, eid, entity, index=index)
        if where != room_id:
            continue
        if filling_only and _light_radius(entity) != "room":
            continue
        best = _brighter(best, normalize_light(entity.get("light_source")))
    return best


# ---------------------------------------------------------------------------
# WHERE A LIGHT POINTS -- read here once, for both tiers of the light model.
#
# A POINTED LIGHT LIGHTS WHAT IT POINTS AT (the owner's ruling, 2026-10-09,
# D3 of the Brackwater run, `docs/experiments/PLAY_2026_10_07_brackwater.md`
# F95). A cone's aim is its `state.pointed_at`, which the encoder's
# `entities__emits` part writes as "the entity, anchor, BODY or compass
# bearing a cone is aimed at". The light field read four shapes of it -- a
# number, a bearing word, a body or thing standing at a MEASURED cell, an
# anchor of the lamp's OWN room -- and left the cone all round for anything
# else, so a beam sent through a doorway at something with no measured place
# lit nothing it was pointed at. Measured over every checkpoint of both
# databases (2026-10-09): five distinct aims were ever written, all in scratch
# story 166, and three of the five were shapes nothing read -- a ROOM (the
# down-channel, aimed into from the boat), a thing with no measured place in
# the NEXT room (the coat on the stake), and a person with no measured place
# in the lamp's own room (Murren in the chapel).
#
# `aim_of` says what an aim NAMES, in the engine's own terms and nothing
# else; the field turns that into an axis and a cell
# (`spatial_light_field._resolve_pointed_at`), and the room-level readers
# below, which have no cells, turn it into which body and which room the beam
# reaches. One reading of the aim, so the two tiers cannot disagree about
# what a lamp is pointed at.
# ---------------------------------------------------------------------------

def _room_named(scene: dict, text: str) -> Optional[str]:
    """The room `text` is the id or the folded name of, or None. Exact
    spellings only (`room_spellings`): an aim is a NAME the scene holds, and
    a phrase that merely shares a word with a room is not one -- the card
    says so, and `test_an_aim_the_engine_cannot_read_is_all_round_not_the_
    chest` pins a phrase as unreadable."""
    rooms = (scene or {}).get("rooms") or {}
    if not isinstance(rooms, dict) or not text:
        return None
    if text in rooms:
        return str(text)
    folded = normalize_room_id(text)
    if not folded:
        return None
    hits = [str(rid) for rid, rdef in rooms.items()
            if folded in room_spellings(rid, rdef)]
    return hits[0] if len(hits) == 1 else None


def aim_of(scene: dict, eid, entity, src_room=None) -> Optional[dict]:
    """What a source's `state.pointed_at` names, or None when it names
    nothing the scene holds (unset, empty, a phrase).

    One of:
      {"degrees": float}               a number, or a compass word
      {"body": spelling, "room": id}   a body or thing the scene places --
                                       with "anchor" beside it when the
                                       lamp's own room also has an anchor of
                                       that id, which then answers for a
                                       body that has no measured cell
      {"anchor": id, "room": id}       a feature of the lamp's own room
                                       (its doorways included) or of exactly
                                       one other room
      {"room": id}                     a room, by id or name -- or the
                                       doorway of a room the lamp is not in

    The order is the field's order of old -- a body first, then the lamp's
    own room's anchor -- with the three new shapes after them, so every aim
    that resolved before resolves to what it did. `src_room` is the room the
    caller already placed the lamp in; absent, it is read from the scene."""
    if not isinstance(entity, dict):
        return None
    state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
    pointed = state.get("pointed_at")
    if pointed is None or isinstance(pointed, bool):
        return None
    if isinstance(pointed, (int, float)):
        return {"degrees": float(pointed) % 360.0}
    text = str(pointed or "").strip()
    if not text:
        return None
    bearing = normalize_bearing(text)
    if bearing in _BEARING_DEG:
        return {"degrees": float(_BEARING_DEG[bearing])}
    rooms = (scene or {}).get("rooms") or {}
    if src_room is None:
        src_room = room_of_record(scene, eid, entity)
    own = effective_anchors(scene, src_room) if src_room in rooms else {}
    if text not in rooms:
        where = room_of(scene, text)
        if where:
            aim = {"body": text, "room": str(where)}
            if text in own:
                aim["anchor"] = text
            return aim
    if text in own:
        return {"anchor": text, "room": str(src_room)}
    named = _room_named(scene, text)
    if named:
        return {"room": named}
    holders = [str(rid) for rid, rdef in rooms.items() if isinstance(rdef, dict)
               and text in (rdef.get("anchors") or {})]
    if len(holders) == 1:
        return {"anchor": text, "room": holders[0]}
    # A doorway written from the far side: `door:<room>` is the implicit
    # anchor every room beside <room> holds for the way into it, so from a
    # lamp standing in one of those rooms it is the lamp's own anchor (above),
    # and from anywhere else it names the room the doorway opens into.
    if text.startswith(_DOOR_ANCHOR_PREFIX):
        into = _room_named(scene, text[len(_DOOR_ANCHOR_PREFIX):])
        if into:
            return {"room": into}
    return None


def aim_into(scene: dict, aim: Optional[dict], src_room) -> Optional[str]:
    """The room a beam with this aim is SENT INTO, or None: the room of the
    body, feature or room it names -- and for a doorway of the lamp's own
    room, the room that doorway opens onto. A compass aim names no room."""
    if not aim or "room" not in aim:
        return None
    anchor = str(aim.get("anchor") or "")
    if "body" not in aim and anchor.startswith(_DOOR_ANCHOR_PREFIX) \
            and aim["room"] == str(src_room or ""):
        return _room_named(scene, anchor[len(_DOOR_ANCHOR_PREFIX):]) or aim["room"]
    return aim["room"]


def _is_lit_switch(entity) -> bool:
    state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
    return state.get("lit", True) not in (False, 0, "off", "false", "no",
                                          "doused", "out")


def _beams(scene: dict):
    """`[(eid, entity, room, aim)]` for every lit CONED source that names
    what it is pointed at -- the beams of the room-level readers below. A
    cone with no aim follows its holder's facing, which only the field can
    read; with no geometry it is the pool it always was. Derived once per
    read pass (`world/scene_memo.py`): `light_at` asks it per body per
    observer pair."""
    return scene_memo(scene, ("light_beams",), lambda: _derive_beams(scene))


def _derive_beams(scene: dict):
    from world.spatial_light_field import normalize_light_shape
    entities = (scene or {}).get("entities") or {}
    if not isinstance(entities, dict):
        return []
    index = PositionsIndex((scene or {}).get("positions") or {})
    out = []
    for eid, entity in entities.items():
        if not isinstance(entity, dict) or not entity.get("light_source"):
            continue
        if normalize_light_shape(entity.get("light_shape")) != "cone":
            continue
        if not _is_lit_switch(entity):
            continue
        if normalize_light(entity.get("light_source")) == "dark":
            continue
        aim = aim_of(scene, eid, entity)
        if not aim or "room" not in aim:
            continue
        where = room_of_record(scene, eid, entity, index=index)
        if where:
            out.append((eid, entity, str(where), aim))
    return out


def _light_crosses(scene: dict, a, b) -> bool:
    """Does an edge between rooms `a` and `b` let light across -- the same
    barriers sight crosses, which is what `spatial_light_field.light_passes`
    places a neighbour by. Either side's record of the edge answers
    (`effective_adjacent`)."""
    if not a or not b or str(a) == str(b):
        return False
    for edge in effective_adjacent(scene, a) or ():
        if isinstance(edge, dict) and str(edge.get("to") or "") == str(b) \
                and normalize_barrier(edge.get("barrier")) in _SIGHT_BARRIERS:
            return True
    return False


def _lamp_reach(scene: dict, eid, lamp_room, room_id):
    """HOW FAR A BEAM CARRIES IS THE LAMP'S OWN FIELD'S TO SAY, wherever the
    lamp's room has one. `(lf, {cell: the lamp's own light there})` over
    the cells of `room_id` the lamp's cast reaches in the field over
    `lamp_room` -- or, where that field does not place `room_id`, over the
    lamp room's own doorway onto it -- an empty dict when the cast reaches
    none of them: the end of its reach, a wall, an occluder at or above the
    lamp. None where the lamp's room has no field, and only the aim's name
    can answer.

    The room-level readers below are asked about a room WITHOUT a field.
    Answering them by name whenever that room has none, whatever the lamp's
    own room measures, gives one fiction two answers by whether the FAR
    room was measured. The case that showed it, built to test the reader
    (2026-10-09): a hall laid out 4 by 24 paces, the lamp at its far end
    aimed at a body in a cell off the hall's north doorway. The hall's
    field had the cone dead about seven cells out; with the cell given no
    size the name lit the body `lit`, and the lamp's holder saw it at
    `conduct` from 24 paces in the dark, while the same cell given a size
    read `dark` and `none`."""
    from world.spatial_light_field import light_field
    lf = light_field(scene, lamp_room)
    if lf is None:
        return None
    contrib = lf.per_source.get(str(eid)) or {}
    field = lf.field
    if str(room_id) in field.offsets:
        cells = lf.room_cells(str(room_id))
    else:
        placed = (field.anchors.get(lamp_room) or {}).get(
            door_anchor_id(room_id)) or {}
        cells = [field.cell_of(lamp_room, tuple(c))
                 for c in placed.get("cells") or ()]
    return lf, {c: contrib[c] for c in cells if contrib.get(c, 0.0) > 0.0}


def _measured_beam_level(scene: dict, lf, eid, name, room_id, reached):
    """The level where a measured beam falls on body `name` in `room_id`
    (`_lamp_reach`'s `lf` and `reached`), or None when it does not reach
    it. Read as `spatial_light_field._beam_on` reads a body: at its own
    measured cell where it has one, and it must be one the cast reaches;
    having none, where the beam enters its room -- the cell the aim resolved
    to when the cast reaches it, else the reached cell the lamp lights
    most."""
    if not reached:
        return None
    from world.spatial_fov import body_cell
    cell = body_cell(scene, name)
    if cell is not None and str(room_id) in lf.field.offsets:
        at = lf.field.cell_of(str(room_id), tuple(cell))
        return lf.level(at) if at in reached else None
    src = next((s for s in lf.sources if s["id"] == str(eid)), None) or {}
    goal = src.get("goal")
    at = goal if goal in reached else max(
        reached, key=lambda c: (reached[c], -c[0], -c[1]))
    return lf.level(at)


def _room_beam_on(scene: dict, name: str, room_id) -> Optional[str]:
    """The level a beam AIMED AT this body gives it where the body's room
    has no light field, or None when no beam names it or none reaches it.

    From a lamp in the same room, or in a room beside it whose edge lets
    light across. Where the lamp's own room has a field, that field answers
    (`_lamp_reach`): the light where its cast falls on the body, and nothing
    where the cast ends first. Only where NEITHER room has a field does the
    name answer alone: the body the beam is pointed at stands in its pool and
    reads what the lamp emits -- the room-level model's own rule for a hand
    light ("held by this body, or standing in its pool: fully lit"), which
    has no distance to decay it by.

    A room with no field is never lifted by a beam (`effective_light`): it
    lights what it is pointed at. A room the field measures counts a beam's
    light in its median like any other, so the two tiers part on a small
    room a beam floods (UNBUILT_PERCEPTION § 2.34)."""
    best = None
    for eid, entity, where, aim in _beams(scene):
        if "body" not in aim or not same_subject(scene, aim["body"], name):
            continue
        if where != room_id and not _light_crosses(scene, where, room_id):
            continue
        reach = _lamp_reach(scene, eid, where, room_id)
        if reach is None:
            level = normalize_light(entity.get("light_source"))
        else:
            level = _measured_beam_level(scene, reach[0], eid, name, room_id,
                                         reach[1])
            if level is None:
                continue
        best = _brighter(best or "dark", level)
    return best


def beam_sent_into(scene: dict, room_id, from_room) -> bool:
    """Is a beam from `from_room` sent INTO `room_id` and lighting it: a lit
    cone standing in `from_room` whose aim names `room_id`, the doorway onto
    it, a feature of it or a body in it (`aim_into`), across an edge light
    crosses -- and, where `from_room` has a light field, whose own cast
    lights a cell of `room_id` (or the doorway onto it, where the field does
    not place it) to at least `DIM_T` (`_lamp_reach`)?

    THE ROOM-LEVEL HALF OF WHAT A POINTED LIGHT SHOWS THROUGH A DOORWAY
    (D3). A room with no field has no cells for a beam to light and no line
    to test, so the beam lights only the body it names (`_room_beam_on`),
    never the room, and the room is NAMED -- without its notes -- only to an
    observer looking through the opening the beam is sent through
    (`perception._visible_openings`). Lifting the room's own light instead
    hands its notes and its onward record (`visible_adjacent_rooms`) to
    every mind beside it, a bystander on its far side who carries no light
    included -- measured on a landing, a vault and a back stair built with
    no geometry (2026-10-09), where the same three rooms laid out gave the
    lamp's holder the name alone and the bystander nothing."""
    from world.spatial_light_field import DIM_T
    for eid, _entity, where, aim in _beams(scene):
        if where != str(from_room) or where == str(room_id):
            continue
        if aim_into(scene, aim, where) != str(room_id):
            continue
        if not _light_crosses(scene, where, room_id):
            continue
        reach = _lamp_reach(scene, eid, where, room_id)
        if reach is None:
            return True
        if reach[1] and max(reach[1].values()) >= DIM_T:
            return True
    return False


def beam_light_on(scene: dict, name: str) -> Optional[str]:
    """The level a beam POINTED AT this body or thing gives it, or None
    when no lamp's aim names it or none reaches it -- through the light field
    where its room has one (`spatial_light_field.field_beam_on`), else the
    room-level answer. For a reader that gates on a ROOM's light and must
    still see what a beam picks out of the dark
    (`perception._visible_things`, rule 5)."""
    room_id = room_of(scene, name)
    if not room_id:
        return None
    from world.spatial_light_field import field_beam_on, light_geometry_exists
    if light_geometry_exists(scene, room_id):
        return field_beam_on(scene, name)
    return _room_beam_on(scene, name, room_id)


# How far a source throws. A hand light makes a pool; a hearth or a ceiling
# fixture fills the space. Portable things default to a pool, because that is
# what carrying a light is actually like -- and the difference is the whole
# reason a torch in a cellar is tense rather than a solved problem.
def _light_radius(entity):
    declared = str((entity or {}).get("light_radius") or "").strip().casefold()
    if declared in ("room", "spot"):
        return declared
    return "spot" if (entity or {}).get("portable") else "room"


def light_at(scene: dict, name: str) -> str:
    """The light actually falling on one body.

    A room's ambient light, plus any source close enough to reach them. This is
    what makes a torch a torch: standing next to the person holding it you are
    lit, across the room you are a shape in the dark, and the room itself never
    became "lit" for everyone at once.
    """
    room_id = room_of(scene, name)
    if not room_id:
        return "lit"

    # WHERE THE ROOM CARRIES GEOMETRY AND THE BODY A STATION, THE ANSWER IS
    # THE BODY'S CELL IN THE LIGHT FIELD (`world/spatial_light_field.py`):
    # the same four words, from the lamp's rays instead of from the room.
    # None means the field does not exist for this body and everything
    # below keeps its answer, byte for byte.
    from world.spatial_light_field import field_light_at
    field_level = field_light_at(scene, name)
    if field_level is not None:
        return field_level

    # Ambient: the room's own light, plus sources that fill a whole room.
    level = _brighter(room_light(scene, room_id),
                      source_light(scene, room_id, filling_only=True))

    entities = (scene or {}).get("entities") or {}
    index = PositionsIndex((scene or {}).get("positions") or {})
    for eid, entity in entities.items():
        if not isinstance(entity, dict) or not entity.get("light_source"):
            continue
        if _light_radius(entity) == "room":
            continue                      # already counted as ambient
        state = entity.get("state") if isinstance(entity.get("state"), dict) else {}
        if state.get("lit", True) in (False, 0, "off", "false", "no", "doused", "out"):
            continue
        label = str(entity.get("name") or eid)
        where = room_of_record(scene, eid, entity, index=index)
        if where != room_id:
            continue

        emitted = normalize_light(entity.get("light_source"))
        # Held by this body, or standing in its pool: fully lit. Elsewhere in
        # the room: you can see the light without being in it.
        if str(label).strip().casefold() == str(name).strip().casefold() \
                or proximity_rel(scene, name, label) in ("within_reach", "near"):
            level = _brighter(level, emitted)
        else:
            level = _brighter(level, "dim" if emitted != "dark" else "dark")
    # A POINTED LIGHT LIGHTS WHAT IT POINTS AT, from this room or through a
    # doorway (D3, the section above `_light_radius`). The loop above reads
    # only the lamps standing in this body's room, so a beam sent from the
    # next room at a body in this one left it in the dark.
    beam = _room_beam_on(scene, name, room_id)
    if beam:
        level = _brighter(level, beam)
    return level


def effective_light(scene: dict, room_id: str) -> str:
    """A room's light including what spills in from next door.

    A dark room with an open doorway onto a lit one is not pitch black -- there
    is enough to make out shapes, which is the difference between a cellar with
    the door open and a cellar with the door shut. Spill lifts dark to dim and
    never further: borrowed light does not let you read by it.
    """
    # WHERE THE ROOM CARRIES GEOMETRY the answer is the level of its MEDIAN
    # cell in the light field (`world/spatial_light_field.py`): the room's
    # typical light, with spill a consequence of the wall as a line and the
    # doorway as a gap in it rather than the one-step rule below. None means
    # no geometry, and the room-level answer stands unchanged.
    from world.spatial_light_field import field_effective_light
    field_level = field_effective_light(scene, room_id)
    if field_level is not None:
        return field_level

    # Anything burning in here counts as much as anything built in -- but only
    # what actually fills the room. A hand torch is handled per body, in
    # light_at, so it never silently illuminates the far corner.
    own = _brighter(room_light(scene, room_id),
                    source_light(scene, room_id, filling_only=True))
    if own != "dark":
        return own

    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(room_id)
    if not isinstance(room, dict):
        return own

    for edge in room.get("adjacent") or []:
        if not isinstance(edge, dict):
            continue
        if normalize_barrier(edge.get("barrier")) not in _SIGHT_BARRIERS:
            continue
        if room_light(scene, edge.get("to")) in ("lit", "bright"):
            return "dim"
    return "dark"


def light_blocks_sight(level) -> bool:
    """Is there too little light here to see anything at all."""
    return normalize_light(level) == "dark"


# What light lets you make out, mirroring hear_level's none/fragment/full. A
# binary "can you see" cannot express the state most scenes actually want: a
# shape moving in the gloom that you cannot identify.
#
# DIM WITHHOLDS DETAIL, NOT CONDUCT -- which is why there are four rungs and
# not three. `dim` is the word an author reaches for to mean "indoors, late
# afternoon"; `shapes` is what the engine meant by it, and the two are not the
# same claim. Measured (PQ2, `docs/experiments/PLAY_2026_09_05C_quiet.md`, a
# two-hander whose entire content is what two people do with their hands):
# with both bodies at `dim`, every act composed as "{label} moves, too little
# of it to make out" -- a glove drawn off finger by finger and laid on a table
# four feet away, three times -- and fifteen of twenty-one beats carried that
# phrase or a narrator paraphrase of it.
#
# The rule the four rungs state, in the engine's own vocabulary:
#
#   * `none` -- no visual channel at all. Not even a figure.
#   * `shapes` -- a body is there and moving, and nothing about what it is
#     doing. This is what a BOUNDARY leaves for a beat: a body still going
#     through a door sight does not cross, or into the dark. It is reached by
#     the crossing grace alone since 2026-10-05 -- the doorway cone's
#     large-room fallback became `conduct`, and the far-edge and 25 m
#     distance caps were removed (the owner: "an overzealous feature
#     overall"); distance takes nothing one doorway away.
#   * `conduct` -- what a body DOES, without what it IS. Where it moved,
#     whether it sat, what it took up and set down: the gross conduct a
#     silhouette genuinely carries. What it does not carry is the face, the
#     cut of a garment, the appearance of a stranger -- every reader that
#     wants detail already asks for `full`, so this rung costs identity by
#     construction and nothing here had to enumerate what "detail" means.
#   * `full` -- the lot.
#
# The grade WORD is an owner decision, taken 2026-09-05: `conduct` is the noun
# the rule itself uses, and it names the CONTENT of the rung rather than its
# cause, which is what the other three names do.
SIGHT_LEVELS = ("none", "shapes", "conduct", "full")
_LIGHT_SIGHT = {
    "dark": "none",       # nothing, including the person beside you
    "dim": "conduct",     # what a body does -- not faces, not detail
    "lit": "full",
    "bright": "full",
}
