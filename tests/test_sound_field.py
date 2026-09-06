"""The sound field (`world/spatial_sound_field.py`, through the
`world.spatial` facade): loudness as a quantity on the sight grid.

The contract under test is the same fail-open the sight layer has -- THE
FIELD MAY ONLY EXIST ON EVIDENCE IT HAS. A scene without geometry stamps
nothing on the relation and every hearing reader answers byte-identically;
the containment cases keep their present answers whatever the field says;
the readers' three words never change. Where the field does exist, the
DESIGN_SOUND_FIELD.md section 9.3 table is pinned case by case, and the
numbers in the docstrings are the ones the table in the note was computed
from.
"""

from __future__ import annotations

import copy

import pytest

from world.spatial import (
    APERTURE_PASS,
    DIAGONAL_COST,
    FAIL_RATE,
    FLICKER_RATE,
    HEARING_LEVELS,
    SOUND_LEVELS,
    STEADINESS,
    SoundField,
    _merge_entity,
    body_cell,
    gain_at,
    hear_level,
    heard_events,
    observer_field,
    sound_field,
    sound_notices,
    sound_sources,
    spatial_rel_between,
    spread,
    stamp_sound_relation,
    steadiness_this_beat,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def room(size, anchors, adjacent=(), exposure="enclosed"):
    return {"name": "the %s room" % size, "size": size, "exposure": exposure,
            "adjacent": list(adjacent), "anchors": dict(anchors)}


def scene(rooms, positions, stations=None, entities=None, contained=None,
          weather=None):
    sc = {"rooms": rooms, "positions": dict(positions),
          "stations": dict(stations or {}), "orientation": {}, "poses": {},
          "entities": dict(entities or {}), "contained": dict(contained or {})}
    if weather:
        sc["weather"] = weather
    return sc


def hall(*, geometry=True, extra=None):
    """A large room: a waist-high counter running along the north wall one
    pace off it, a lamp on the west wall, a window east, a hearth south."""
    counter = {"desc": "the counter", "dir": "n"}
    if geometry:
        counter.update({"footprint": "run", "height": "waist"})
    anchors = {"counter": counter,
               "west": {"desc": "the west wall lamp", "dir": "w"},
               "east": {"desc": "the east window", "dir": "e"},
               "south": {"desc": "the south hearth", "dir": "s"}}
    anchors.update(extra or {})
    return {"hall": room("large", anchors)}


def two_rooms(barrier="open_door", material=None):
    """Two medium rooms joined east-west; both carry geometry (a counter in
    `a`, a shelf in `b`), because the field is the LISTENER's room's."""
    e1 = {"to": "b", "barrier": barrier, "dir": "e"}
    e2 = {"to": "a", "barrier": barrier, "dir": "w"}
    if material:
        e1["material"] = material
        e2["material"] = material
    return {
        "a": room("medium", {"c": {"desc": "a counter", "dir": "n",
                                   "height": "waist"}}, [e1]),
        "b": room("medium", {"w": {"desc": "the far window", "dir": "e"},
                             "shelf": {"desc": "a shelf", "dir": "s",
                                       "height": "waist"}}, [e2]),
    }


VOLUMES = ("mutter", "whisper", "normal", "loud", "shout")


def levels(sc, speaker, listener, volumes=VOLUMES):
    rel = spatial_rel_between(sc, listener, speaker)
    return {v: hear_level(rel, v) for v in volumes}


# ---------------------------------------------------------------------------
# Fail-open: no geometry, no field, nothing changes
# ---------------------------------------------------------------------------

def test_a_scene_without_geometry_stamps_nothing_and_composes_byte_identically():
    """THE PIN. The hall with no geometry field on any anchor: `sound_field`
    is None, the body-to-body relation carries exactly the keys it carried
    before this module existed (`same_room`, `barrier`, `distance`, `light`
    -- no `signal`, no `noise`), and `hear_level` answers every volume by
    the edge rules: same room, unmeasured proximity -> `full` for all five.

    THE BOUNDARY MOVED 2026-09-06. The gate used to be an authored anchor
    HEIGHT, which answered true for four of the owner's 580 live rooms -- so
    the near field ran for 0.7% of the world and this fallback was very
    nearly the whole engine. It is now the light field's
    (`light_geometry_exists`: a size tier, an extent, or any anchors is a
    grid), and the fallback is what it always meant to be: the room nobody
    has described at all. 244 of those 580 rooms are still exactly this."""
    rooms = hall(geometry=False)
    for room in rooms.values():
        room.pop("size", None)
        room.pop("extent", None)
        room["anchors"] = {}
    sc = scene(rooms, {"S": "hall", "L": "hall"}, {})
    assert sound_field(sc, "L") is None
    rel = spatial_rel_between(sc, "L", "S")
    assert rel == {"same_room": True, "barrier": "open", "distance": "same",
                   "light": "lit"}
    assert levels(sc, "S", "L") == {v: "full" for v in VOLUMES}
    # And across a room boundary without geometry: the edge rules verbatim.
    rooms = two_rooms("closed_door")
    for r in rooms.values():
        r.pop("size", None)
        r.pop("extent", None)
        r["anchors"] = {}
    sc = scene(rooms, {"S": "a", "L": "b"}, {})
    rel = spatial_rel_between(sc, "L", "S")
    assert "signal" not in rel and "noise" not in rel
    assert levels(sc, "S", "L") == {"mutter": "none", "whisper": "none",
                                    "normal": "fragment", "loud": "full",
                                    "shout": "full"}


def test_the_stamp_needs_the_listener_on_the_field():
    """A listener whose room carries geometry but a speaker in a room the
    field never placed (joined by a plain wall): no stamp, edge rules."""
    sc = scene(two_rooms("wall"), {"S": "a", "L": "b"},
               {"S": {"at": "c"}, "L": {"at": "w"}})
    field = sound_field(sc, "L")
    assert field is not None and sorted(field.grid.offsets) == ["b"]
    rel = spatial_rel_between(sc, "L", "S")
    assert "signal" not in rel
    assert hear_level(rel, "shout") == "fragment"       # today's wall rule
    assert hear_level(rel, "normal") == "none"


def test_the_readers_words_do_not_change():
    """Every answer the field path gives is one of `hear_level`'s own three
    words, and the ladder downstream of `sense_adjusted` is untouched."""
    assert HEARING_LEVELS == ("none", "trace", "fragment", "full")
    sc = scene(hall(), {"S": "hall", "L": "hall"},
               {"S": {"at": "west"}, "L": {"at": "east"}})
    seen = set(levels(sc, "S", "L").values())
    sc = scene(hall(), {"S": "hall", "L": "hall"},
               {"S": {"at": "west"}, "L": {"near": ["S"]}})
    seen |= set(levels(sc, "S", "L").values())
    assert seen <= {"none", "fragment", "full"}
    # The source ladder GREW on 2026-09-05 and the hearing ladder did not:
    # `thunderous` and `catastrophic` are two more things a source can be,
    # not two more things a listener can receive. What a body gets is still
    # `none | fragment | full` for words, and `trace` for a direction with
    # none -- which is what a distant sound has always been entitled to.
    assert SOUND_LEVELS == ("faint", "audible", "loud", "deafening",
                            "thunderous", "catastrophic")
    assert STEADINESS == ("steady", "flickering", "failing")


# ---------------------------------------------------------------------------
# The containment cases keep their present answers ALWAYS
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("flag,expected", [
    ("inside_source", {"mutter": "fragment", "whisper": "fragment",
                       "normal": "full", "loud": "full", "shout": "full"}),
    ("enclosed_from_source", {"mutter": "none", "whisper": "none",
                              "normal": "none", "loud": "fragment",
                              "shout": "fragment"}),
    ("source_enclosed", {"mutter": "none", "whisper": "none",
                         "normal": "fragment", "loud": "fragment",
                         "shout": "fragment"}),
])
def test_a_conducted_voice_ignores_the_field(flag, expected):
    """The medium is a body, not air: a relation carrying an enclosure flag
    answers exactly as before even with a signal stamped on it (a
    hand-built relation, since `stamp_sound_relation` itself refuses to
    stamp one -- tested below)."""
    rel = {"same_room": True, "barrier": "open", "distance": "same",
           flag: True, "signal": 1.0, "noise": 0.05}
    assert {v: hear_level(rel, v) for v in VOLUMES} == expected


def test_the_stamp_defers_to_every_enclosure_flag():
    sc = scene(hall(), {"S": "hall", "L": "hall"},
               {"S": {"at": "west"}, "L": {"at": "east"}})
    for flag in ("inside_source", "enclosed_from_source", "source_enclosed",
                 "concealed"):
        rel = {"same_room": True, flag: True}
        assert stamp_sound_relation(sc, dict(rel), "L", "S") == rel


# ---------------------------------------------------------------------------
# Section 9.3: the synthetic table
# ---------------------------------------------------------------------------

def test_a_whisper_across_a_large_room_dies_and_beside_the_speaker_lives():
    """West wall to east wall of a large room: path 5.8, gain 0.029, noise
    0.05 -> mutter none, whisper none, normal full, loud full, shout full.
    Beside the speaker (a `near` station): path 1, gain 0.5 -> all full."""
    sc = scene(hall(), {"S": "hall", "L": "hall"},
               {"S": {"at": "west"}, "L": {"at": "east"}})
    assert levels(sc, "S", "L") == {"mutter": "none", "whisper": "none",
                                    "normal": "full", "loud": "full",
                                    "shout": "full"}
    sc = scene(hall(), {"S": "hall", "L": "hall"},
               {"S": {"at": "west"}, "L": {"near": ["S"]}})
    assert levels(sc, "S", "L") == {v: "full" for v in VOLUMES}


def test_a_shout_through_a_closed_door_and_a_normal_voice_through_it():
    """Far walls of two medium rooms through a shut door: path 6.8, pass
    0.25, gain 0.005 -> normal fragment (the edge rule's own answer), loud
    and shout full, mutter and whisper none. Door to door (path 3): normal
    full."""
    sc = scene(two_rooms("closed_door"), {"S": "a", "L": "b"},
               {"S": {"at": "c"}, "L": {"at": "w"}})
    rel = spatial_rel_between(sc, "L", "S")
    assert "signal" in rel and "noise" in rel
    assert levels(sc, "S", "L") == {"mutter": "none", "whisper": "none",
                                    "normal": "fragment", "loud": "full",
                                    "shout": "full"}
    sc = scene(two_rooms("closed_door"), {"S": "a", "L": "b"},
               {"S": {"at": "door:b"}, "L": {"at": "door:a"}})
    assert levels(sc, "S", "L")["normal"] == "full"
    assert levels(sc, "S", "L")["whisper"] == "none"


def test_round_a_corner_through_an_open_door_reaches_and_through_the_wall_does_not():
    """The counter in `a` and the window in `b` are not in line through the
    doorway; the flood goes round (path 6.8) and a normal voice is `full`.
    Replace the door with a wall and `b` is never placed: the field stamps
    nothing and the edge rule answers `none` for a normal voice."""
    sc = scene(two_rooms("open_door"), {"S": "a", "L": "b"},
               {"S": {"at": "c"}, "L": {"at": "w"}})
    assert levels(sc, "S", "L")["normal"] == "full"
    assert levels(sc, "S", "L")["whisper"] == "none"
    sc = scene(two_rooms("wall"), {"S": "a", "L": "b"},
               {"S": {"at": "c"}, "L": {"at": "w"}})
    assert "signal" not in spatial_rel_between(sc, "L", "S")
    assert levels(sc, "S", "L")["normal"] == "none"


def test_a_counter_is_crossed_and_a_partition_is_gone_round():
    """PE1. SOUND GOES OVER AND AROUND WHAT IS NOT A PARTITION: a counter,
    a table, a sofa back are crossed for OCCLUDER_PASS and no path at all,
    and only something that reaches the ceiling parts a room acoustically.

    The live case this replaces: an 8x6 kitchen with a waist counter run
    and a waist table in it, two bodies four paces apart, a normal voice --
    signal 0.0067 against noise 0.32, `none`, because the flood walked 12
    cells round the end of the counter for a four-cell straight line, and
    neither of the two people standing in the room received either the lie
    or its correction (`PLAY_2026_09_05_flat.md` § PE1)."""
    behind = scene(hall(), {"S": "hall", "L": "hall"},
                   {"S": {"at": "south"}, "L": {"at": "counter", "cover": True}})
    f_behind = sound_field(behind, "L")
    origin = f_behind.locate("S")
    reached = spread(f_behind.grid, origin)
    counter_cells = {f_behind.grid.cell_of("hall", c)
                     for c in f_behind.grid.anchors["hall"]["counter"]["cells"]}
    assert counter_cells <= set(reached)
    # Behind the waist-high run: reached by the STRAIGHT walk, not round the
    # end of it, and paying OCCLUDER_PASS for the cells it crossed.
    wall_side = [c for c in f_behind.grid.inside
                 if c[1] < min(cc[1] for cc in counter_cells)]
    assert wall_side
    for cell in wall_side:
        straight = max(abs(cell[0] - origin[0]), abs(cell[1] - origin[1]))
        assert reached[cell][0] <= straight * DIAGONAL_COST, cell
    # The ones the run actually stands in front of paid for crossing it,
    # and paid a factor rather than a detour.
    over_the_counter = [c for c in wall_side
                        if c[0] in {cc[0] for cc in counter_cells}]
    assert over_the_counter
    for cell in over_the_counter:
        assert reached[cell][1] < 1.0, cell
    assert levels(behind, "S", "L")["normal"] == "full"
    # A body standing behind a waist counter four paces off still converses.
    kitchen = {"kitchen": room("large", {
        "counter": {"desc": "the counter", "dir": "n", "footprint": "run",
                    "height": "waist"},
        "table": {"desc": "the table", "cell": [3, 2], "footprint": "large",
                  "height": "waist"},
        "door": {"desc": "the way out", "dir": "s"}})}
    sc = scene(copy.deepcopy(kitchen), {"S": "kitchen", "L": "kitchen"},
               {"S": {"cell": [5, 1]}, "L": {"cell": [1, 2]}})
    assert levels(sc, "S", "L")["normal"] == "full"
    # The same room with a FULL-height partition standing between them: the
    # flood goes round it, and the voice pays the whole detour.
    partitioned = scene(copy.deepcopy(kitchen), {"S": "kitchen", "L": "kitchen"},
                        {"S": {"cell": [5, 1]}, "L": {"cell": [1, 2]}})
    for y in range(6):
        partitioned["rooms"]["kitchen"]["anchors"]["screen_%d" % y] = {
            "desc": "a full-height screen", "cell": [3, y], "height": "full"}
    f_open = sound_field(sc, "L")
    f_shut = sound_field(partitioned, "L")
    assert (f_shut.gain_between("S", "L")
            < f_open.gain_between("S", "L") * 0.5)
    # And a body whose station lands ON an occluder's cell is not deaf: a
    # listener standing where another anchor's seeded cell fell hears the
    # speaker beside them in full (until 2026-09-04 the flood never entered
    # the cell and stamped a signal of 0 -- a shout beside them was `none`).
    at_counter = scene(hall(), {"S": "hall", "L": "hall"},
                       {"S": {"at": "south"}, "L": {"at": "counter"}})
    f = sound_field(at_counter, "L")
    f.grid.height[f.locate("L")] = 1.0        # force the case whatever the seed did
    f._spreads.clear()
    assert f.gain_between("S", "L") > 0
    assert f.speech_level("S", "shout", "L") == "full"


def _gain_through(barrier, material=None):
    sc = scene(two_rooms(barrier, material), {"S": "a", "L": "b"},
               {"S": {"at": "c"}, "L": {"at": "w"}})
    return spatial_rel_between(sc, "L", "S")["signal"]


def test_aperture_attenuation_per_barrier_and_material():
    """Same path, five apertures: the gains order as APERTURE_PASS does, and
    a barrier's material shifts its class exactly as `_material_shifted_
    barrier` does for the edge rules -- a paper door passes like an open
    one, a steel door like a window."""
    g = {b: _gain_through(b) for b in ("open_door", "bars", "membrane",
                                       "closed_door", "window")}
    assert g["open_door"] == g["bars"] > g["membrane"] > g["closed_door"] \
        > g["window"] > 0
    assert g["membrane"] / g["open_door"] == pytest.approx(
        APERTURE_PASS["membrane"] / APERTURE_PASS["open_door"])
    assert _gain_through("closed_door", "paper") == pytest.approx(g["open_door"])
    assert _gain_through("closed_door", "steel") == pytest.approx(g["window"])
    assert APERTURE_PASS["wall"] == 0


GENERATOR = {"gen": {"name": "generator", "kind": "machine",
                     "sound_source": "loud"}}


def test_a_loud_generator_masks_a_normal_voice():
    """Listener at the hearth, speaker beside them, a loud generator at the
    east window three paces off: noise 4.58 against a normal voice's 6.0
    -> fragment; the same pair with no generator -> full; loud and shout
    clear it. Speaker at the west wall (path 5.2) with the generator on:
    normal none."""
    quiet = scene(hall(), {"S": "hall", "L": "hall"},
                  {"L": {"at": "south"}, "S": {"near": ["L"]}})
    noisy = scene(hall(), {"S": "hall", "L": "hall", "gen": "hall"},
                  {"gen": {"at": "east"}, "L": {"at": "south"},
                   "S": {"near": ["L"]}}, GENERATOR)
    assert levels(quiet, "S", "L")["normal"] == "full"
    assert levels(noisy, "S", "L") == {"mutter": "none", "whisper": "none",
                                       "normal": "fragment", "loud": "full",
                                       "shout": "full"}
    far = scene(hall(), {"S": "hall", "L": "hall", "gen": "hall"},
                {"gen": {"at": "east"}, "L": {"at": "south"},
                 "S": {"at": "west"}}, GENERATOR)
    assert levels(far, "S", "L")["normal"] == "none"
    assert levels(far, "S", "L")["shout"] == "fragment"


def test_the_listener_hears_their_own_running_machine_first():
    """A held running generator is at the listener's own cell (the carried
    entity derives to its holder): a normal voice beside them is `none`, a
    shout a fragment. Switched off (`state.running` false) the same pair is
    `full` at every volume."""
    sc = scene(hall(), {"S": "hall", "L": "hall", "gen": "hall"},
               {"L": {"at": "south"}, "S": {"near": ["L"]}}, GENERATOR,
               contained={"gen": {"in": "L", "mode": "held"}})
    field = sound_field(sc, "L")
    [source] = field.sources
    assert source["holder"] == "L" and source["at"] == field.locate("L")
    assert levels(sc, "S", "L") == {"mutter": "none", "whisper": "none",
                                    "normal": "none", "loud": "none",
                                    "shout": "fragment"}
    sc["entities"]["gen"]["state"] = {"running": False}
    assert sound_field(sc, "L").sources == []
    assert levels(sc, "S", "L") == {v: "full" for v in VOLUMES}


def test_two_normal_voices_at_once_mask_each_other():
    """Speakers at opposite walls of a medium room. A listener at the south
    wall, roughly equidistant, gets a fragment of one and nothing of the
    other where either voice alone would be `full`; a listener beside A
    hears A in full and B not at all."""
    rooms = {"m": room("medium", {
        "t": {"desc": "a table", "dir": "n", "height": "waist"},
        "w": {"desc": "west", "dir": "w"}, "e": {"desc": "east", "dir": "e"},
        "s": {"desc": "south", "dir": "s"}})}
    sc = scene(rooms, {"A": "m", "B": "m", "L": "m"},
               {"A": {"at": "w"}, "B": {"at": "e"}, "L": {"at": "s"}})
    both = sound_field(sc, "L", speakers={"A": "normal", "B": "normal"})
    alone = sound_field(sc, "L", speakers={"A": "normal"})
    assert alone.level_of("L", "speech:A") == "full"
    assert both.level_of("L", "speech:A") != "full"
    assert both.level_of("L", "speech:B") != "full"
    sc = scene(rooms, {"A": "m", "B": "m", "L": "m"},
               {"A": {"at": "w"}, "B": {"at": "e"}, "L": {"near": ["A"]}})
    both = sound_field(sc, "L", speakers={"A": "normal", "B": "normal"})
    assert both.level_of("L", "speech:A") == "full"
    assert both.level_of("L", "speech:B") == "none"


# ---------------------------------------------------------------------------
# Ambient, weather, crowds, events
# ---------------------------------------------------------------------------

def test_outdoors_and_weather_raise_the_floor():
    inside = scene(hall(), {"S": "hall", "L": "hall"},
                   {"S": {"at": "west"}, "L": {"at": "east"}})
    outside = scene(hall(), {"S": "hall", "L": "hall"},
                    {"S": {"at": "west"}, "L": {"at": "east"}})
    outside["rooms"]["hall"]["exposure"] = "open"
    storm = scene(hall(), {"S": "hall", "L": "hall"},
                  {"S": {"at": "west"}, "L": {"at": "east"}},
                  weather={"sky": "storm", "precipitation": "rain",
                           "intensity": "heavy", "wind": "gale"})
    storm["rooms"]["hall"]["exposure"] = "open"
    n_in = spatial_rel_between(inside, "L", "S")["noise"]
    n_out = spatial_rel_between(outside, "L", "S")["noise"]
    n_storm = spatial_rel_between(storm, "L", "S")["noise"]
    assert n_in < n_out < n_storm
    assert levels(inside, "S", "L")["normal"] == "full"
    assert levels(storm, "S", "L")["normal"] != "full"


def test_a_road_is_a_road_you_can_walk_and_talk_down():
    """§ 1.120, the owner's decision taken 2026-09-05: `AMBIENT["open"]`
    0.2 -> 0.1 and `WEATHER_NOISE` 0.3/0.6/1.0 -> 0.1/0.25/0.5.

    OPEN AIR IS NOT ITSELF A NOISE; what is noisy outdoors is the weather,
    and the weather is counted separately. Before the move an ordinary voice
    outdoors was `full` only inside about five paces and 3.3 in light rain,
    so two people walking together on an open road could not converse
    (`PLAY_2026_09_05_road.md` § PD2). The rule the constants must satisfy,
    stated by the run that found it: the road takes their voices at the
    distance you would have to raise your voice in life.

    The test § 1.120 asked to land with: an empty open room, fair weather,
    two bodies four paces apart, a normal voice."""
    from world.spatial import AMBIENT, WEATHER_NOISE
    assert AMBIENT["open"] == 0.1 and AMBIENT["open"] == AMBIENT["sheltered"]
    assert WEATHER_NOISE == {"light": 0.1, "moderate": 0.25, "heavy": 0.5}

    def road(weather=None):
        sc = scene({"road": room("large", {"stone": {"desc": "a milestone",
                                                     "dir": "n",
                                                     "height": "waist"}},
                                 exposure="open")},
                   {"A": "road", "B": "road"},
                   {"A": {"cell": [1, 4]}, "B": {"cell": [5, 4]}},
                   weather=weather)
        return sc

    fair = road()
    assert levels(fair, "A", "B")["normal"] == "full"
    # Rain you can talk through until it is heavy: at four paces a normal
    # voice survives light and moderate rain and is cut down by a downpour.
    for intensity, expected in (("light", "full"), ("moderate", "full"),
                                ("heavy", "fragment")):
        wet = road({"sky": "rain", "precipitation": "rain",
                    "intensity": intensity, "wind": "calm"})
        assert levels(wet, "A", "B")["normal"] == expected, intensity
    # And a still yard is now no noisier than a porch, which is the claim:
    # the difference between them is what the sky can reach them with.
    porch = road()
    porch["rooms"]["road"]["exposure"] = "sheltered"
    assert spatial_rel_between(porch, "B", "A")["noise"] \
        == spatial_rel_between(fair, "B", "A")["noise"]


def test_a_crowd_is_a_source_at_its_rooms_centre_by_band():
    sc = scene(hall(), {"L": "hall"}, {"L": {"at": "west"}})
    throng = [{"uid": "c1", "room_uid": "hall", "band": "a throng"}]
    handful = [{"uid": "c2", "room_uid": "hall", "band": "a handful"}]
    sources, _ = sound_sources(sc, crowds=throng)
    assert [s["level"] for s in sources] == ["loud"]
    sources, _ = sound_sources(sc, crowds=handful)
    assert [s["level"] for s in sources] == ["faint"]
    field = sound_field(sc, "L", crowds=throng)
    assert field.level_of("L", "crowd:c1") == "full"


def test_a_sound_event_next_door_is_heard_through_the_door_it_came_by():
    events = [{"kind": "sound", "description": "a crash of crockery",
               "source_room": "a", "intensity": "loud"},
              {"kind": "sight", "description": "a flash", "source_room": "a"}]
    heard = heard_events(scene(two_rooms("open_door"), {"L": "b"},
                               {"L": {"at": "w"}}), "L", events)
    assert [(e["description"], level) for e, level in heard] == [
        ("a crash of crockery", "full")]
    assert heard_events(scene(two_rooms("wall"), {"L": "b"},
                              {"L": {"at": "w"}}), "L", events) == []
    # Own-room events are the composer's already; nothing doubles them.
    assert heard_events(scene(two_rooms("open_door"), {"L": "a"},
                              {"L": {"at": "c"}}), "L", events) == []


# ---------------------------------------------------------------------------
# Steadiness
# ---------------------------------------------------------------------------

def test_the_flicker_hash_is_deterministic_and_rate_bound():
    beats = [steadiness_this_beat("flickering", t, "gen") for t in range(400)]
    assert beats == [steadiness_this_beat("flickering", t, "gen")
                     for t in range(400)]
    dropped = beats.count("dropped")
    assert 0 < dropped < 400
    assert dropped == pytest.approx(400 / FLICKER_RATE, rel=0.35)
    assert "out" not in beats
    outs = [steadiness_this_beat("failing", t, "gen") for t in range(600)]
    assert outs.count("out") == pytest.approx(600 / FAIL_RATE, rel=0.35)
    assert steadiness_this_beat("steady", 3, "gen") == "steady"
    assert steadiness_this_beat("failing", None, "gen") == "steady"
    # Different sources on the same beat do not fail together.
    assert [steadiness_this_beat("failing", t, "lamp") for t in range(600)] != outs


def test_a_failing_source_that_goes_quiet_files_a_notice_and_masks_nothing():
    sc = scene(hall(), {"S": "hall", "L": "hall", "gen": "hall"},
               {"gen": {"at": "east"}, "L": {"at": "south"},
                "S": {"near": ["L"]}},
               {"gen": {"name": "the generator", "kind": "machine",
                        "sound_source": "loud", "steadiness": "failing"}})
    out_beat = next(t for t in range(600)
                    if steadiness_this_beat("failing", t, "gen") == "out")
    on_beat = next(t for t in range(600)
                   if steadiness_this_beat("failing", t, "gen") == "steady")
    assert sound_notices(sc, on_beat) == []
    [notice] = sound_notices(sc, out_beat)
    assert "the generator" in notice and "the large room" in notice
    quiet = sound_field(sc, "L", turn_idx=out_beat)
    loud = sound_field(sc, "L", turn_idx=on_beat)
    assert quiet.sources[0]["power"] == 0
    assert quiet.noise_at("L") < loud.noise_at("L")
    assert quiet.notices == [notice] and loud.notices == []


def test_failing_sound_sources_out_names_running_failing_sources_on_their_beat():
    from world.spatial import failing_sound_sources_out, fails_on
    sc = scene(hall(), {"L": "hall", "gen": "hall"},
               {"gen": {"at": "east"}, "L": {"at": "south"}},
               {"gen": {"name": "the generator", "kind": "machine",
                        "sound_source": "loud", "steadiness": "failing"}})
    out = next(t for t in range(600) if fails_on(t, "gen"))
    on = next(t for t in range(600) if not fails_on(t, "gen"))
    # The SAME hash as the light field's: a thing that lights and hums fails
    # on one beat in both senses.
    assert steadiness_this_beat("failing", out, "gen") == "out"
    assert failing_sound_sources_out(sc, out) == [("gen", "the generator")]
    assert failing_sound_sources_out(sc, on) == []
    sc["entities"]["gen"]["state"] = {"running": False}
    assert failing_sound_sources_out(sc, out) == []
    sc["entities"]["gen"] = {"name": "the generator", "sound_source": "loud"}
    assert failing_sound_sources_out(sc, out) == []


def test_the_commit_switches_a_failed_source_off_in_every_sense_it_has_and_files_one_notice(temp_db):
    """SYMMETRY OF THE TWO FIELDS' COMMIT BLOCKS (2026-09-04). The light
    field wrote `state.lit: false` and filed a notice; the sound field filed
    a notice from perception and left `state.running` alone, so a stopped
    generator kept masking every voice on the beats after the Director was
    told it had stopped. One helper now reads both fields' failing lists,
    writes each switch the thing carries, and files ONE notice per thing:
    a generator `has stopped`, a lamp `has gone out`, a thing that both
    lights and hums `has failed` -- once, with both switches off."""
    import time as _time
    from core.pipeline_context import ChatData, PipelineContext, TurnData
    from persist import commit
    from world.spatial import BEAT_KEY, fails_on

    def commit_beat(sc, beat):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Shed", "", _time.time()))
        temp_db.wset(chat_id, "scene", sc)
        ctx = PipelineContext(
            chat=ChatData(id=chat_id, name="Shed", persona_id=None,
                          lorebook_id=None, scenario="", created=_time.time()),
            turn=TurnData(id=1, chat_id=chat_id, idx=beat, player_input="",
                          created=_time.time()),
            cast=[], input="")
        ctx.director_resolve = {"state_diff": {"time": "a moment later"}}
        merged = commit.prepare_scene_commit(ctx)["scene"]
        return merged, temp_db.wget(chat_id, "engine_notices", []), ctx

    out = next(t for t in range(600) if fails_on(t, "gen"))
    on = next(t for t in range(600) if not fails_on(t, "gen"))
    # A sound source alone.
    sc = scene(hall(), {"L": "hall", "gen": "hall"},
               {"gen": {"at": "east"}, "L": {"at": "south"}},
               {"gen": {"name": "the generator", "kind": "machine",
                        "sound_source": "loud", "steadiness": "failing"}})
    merged, notices, ctx = commit_beat(sc, out)
    assert merged["entities"]["gen"]["state"]["running"] is False
    assert "lit" not in merged["entities"]["gen"]["state"]
    assert merged[BEAT_KEY] == out + 1
    assert len(notices) == 1 and "has stopped" in notices[0] \
        and "the generator" in notices[0], notices
    assert sum("the generator" in w for w in ctx.warnings) == 1
    # The next beat it does not fail: nothing said, nothing switched.
    merged, notices, _ctx = commit_beat(sc, on)
    assert merged["entities"]["gen"].get("state", {}).get("running", True) is True
    assert notices == []
    # A thing that both lights and hums: ONE notice, both switches.
    sc = scene(hall(), {"L": "hall", "gen": "hall"},
               {"gen": {"at": "east"}, "L": {"at": "south"}},
               {"gen": {"name": "the humming lamp", "kind": "machine",
                        "sound_source": "loud", "light_source": "lit",
                        "steadiness": "failing"}})
    merged, notices, _ctx = commit_beat(sc, out)
    state = merged["entities"]["gen"]["state"]
    assert state["running"] is False and state["lit"] is False
    assert len(notices) == 1 and "has failed" in notices[0], notices
    assert "its light is gone" in notices[0] and "its sound has stopped" in notices[0]
    # And the silence is heard: the field on the NEXT beat has no source.
    assert sound_field(merged, "L").sources == []


def test_a_flickering_source_drops_one_level_on_its_beat():
    sc = scene(hall(), {"L": "hall", "gen": "hall"},
               {"gen": {"at": "east"}, "L": {"at": "south"}},
               {"gen": {"name": "generator", "kind": "machine",
                        "sound_source": "loud", "steadiness": "flickering"}})
    drop = next(t for t in range(400)
                if steadiness_this_beat("flickering", t, "gen") == "dropped")
    hold = next(t for t in range(400)
                if steadiness_this_beat("flickering", t, "gen") == "steady")
    from world.spatial import SOUND_POWER
    assert sound_field(sc, "L", turn_idx=drop).sources[0]["power"] \
        == SOUND_POWER["audible"]
    assert sound_field(sc, "L", turn_idx=hold).sources[0]["power"] \
        == SOUND_POWER["loud"]


# ---------------------------------------------------------------------------
# Grid, schema, merge
# ---------------------------------------------------------------------------

def test_the_acoustic_grid_places_an_open_door_neighbour_where_sight_does():
    sc = scene(two_rooms("open_door"), {"L": "b"}, {"L": {"at": "w"}})
    sight = observer_field(sc, "L")
    sound = sound_field(sc, "L").grid
    assert sight.offsets == sound.offsets
    assert [w["aperture"] for w in sight.walls] == \
        [w["aperture"] for w in sound.walls]
    assert sound.walls[0]["pass"] == APERTURE_PASS["open_door"]
    # And a shut door, which sight never places, sound does.
    sc = scene(two_rooms("closed_door"), {"L": "b"}, {"L": {"at": "w"}})
    assert sorted(observer_field(sc, "L").offsets) == ["b"]
    assert sorted(sound_field(sc, "L").grid.offsets) == ["a", "b"]


def test_an_unmeasured_body_stands_at_the_rooms_centre():
    sc = scene(hall(), {"S": "hall", "L": "hall"})
    assert body_cell(sc, "S") is None
    field = sound_field(sc, "L")
    assert field.locate("S") == field.locate("L") == (4, 4)
    assert levels(sc, "S", "L") == {v: "full" for v in VOLUMES}


def test_the_schema_round_trips_and_the_merge_keeps_the_fields():
    from llm.schemas import SceneEntityDef
    entity = SceneEntityDef(name="generator", kind="machine",
                            sound_source="loud", steadiness="failing",
                            state={"running": True})
    dumped = entity.model_dump() if hasattr(entity, "model_dump") \
        else entity.dict()
    assert dumped["sound_source"] == "loud" and dumped["steadiness"] == "failing"
    existing = {"name": "generator", "kind": "machine", "sound_source": "loud",
                "steadiness": "failing", "state": {"running": True}}
    # A re-declaration that says nothing about sound keeps it...
    merged = _merge_entity("gen", existing, {
        "name": "generator", "kind": "machine", "description": "", "aliases": [],
        "portable": False, "container": False, "interior_rooms": [],
        "state": {}, "sound_source": None, "steadiness": None})
    assert merged["sound_source"] == "loud" and merged["steadiness"] == "failing"
    # ...and one that switches it off lands in `state`.
    merged = _merge_entity("gen", existing, {"name": "generator",
                                             "state": {"running": False}})
    assert merged["state"]["running"] is False
    assert merged["sound_source"] == "loud"
    sc = scene(hall(), {"L": "hall", "gen": "hall"}, {"L": {"at": "south"}},
               {"gen": merged})
    assert sound_field(sc, "L").sources == []


def test_gain_is_path_not_line():
    """`gain_at` decays by the PATH length the spread recorded."""
    assert gain_at({(0, 0): (0.0, 1.0)}, (0, 0)) == 1.0
    assert gain_at({(3, 0): (3.0, 1.0)}, (3, 0)) == pytest.approx(0.1)
    assert gain_at({(3, 0): (3.0, 0.25)}, (3, 0)) == pytest.approx(0.025)
    assert gain_at({}, (1, 1)) == 0.0
    assert isinstance(sound_field(scene(hall(), {"L": "hall"},
                                        {"L": {"at": "west"}}), "L"), SoundField)


# ---------------------------------------------------------------------------
# PB2: a path between two cells has no direction
# ---------------------------------------------------------------------------

def _pair_rooms():
    """Two rooms of different sizes across one open arch -- the
    caravanserai's courtyard and gate in miniature, the shape whose two
    composites disagreed."""
    return {
        "yard": room("small", {
            "well": {"desc": "the well", "cell": [1, 1], "height": "waist"},
            "stair": {"desc": "the stair", "dir": "n"}},
            [{"to": "gate", "barrier": "open", "dir": "e", "offset": 0.5}],
            exposure="open"),
        "gate": room("tiny", {
            "beam": {"desc": "the bar beam", "dir": "e", "height": "full"},
            "bench": {"desc": "the warden's bench", "dir": "s",
                      "height": "waist"}},
            [{"to": "yard", "barrier": "open", "dir": "w", "offset": 0.5}],
            exposure="sheltered"),
    }


def test_the_gain_between_two_bodies_is_the_same_in_both_directions():
    """PB2, brute-forced over EVERY pair of cells of a two-room fixture, as
    `tests/test_wall_is_a_line.py` does for a sight line: the same pair
    asked from either body's own field, and from either end, is one number.

    The live case: a courtyard and a gate across one open arch, one beat,
    one pair -- the warden's field answered 0.0309 for the shout and the
    shouter's answered 0.0, so the warden heard and replied while the
    narrator wrote "no reply comes" over the reply
    (`PLAY_2026_09_05_caravanserai.md` § PB2)."""
    sc = scene(_pair_rooms(), {"S": "yard", "L": "gate"},
               {"S": {"cell": [0, 0]}, "L": {"cell": [0, 0]}})
    fields = {r: sound_field(sc, name, room=r)
              for r, name in (("yard", "S"), ("gate", "L"))}
    assert all(f is not None for f in fields.values())
    cells = {r: sorted(c for c, rid in fields[r].grid.inside.items()
                       if rid == r) for r in ("yard", "gate")}
    seen = set()
    pairs = 0
    for s_room in ("yard", "gate"):
        for l_room in ("yard", "gate"):
            for s_cell in cells[s_room]:
                for l_cell in cells[l_room]:
                    sc["positions"] = {"S": s_room, "L": l_room}
                    sc["stations"] = {"S": {"cell": list(s_cell)},
                                      "L": {"cell": list(l_cell)}}
                    answers = {
                        f.gain_between("S", "L", speaker_room=s_room,
                                       listener_room=l_room)
                        for f in fields.values()}
                    answers |= {
                        f.gain_between("L", "S", speaker_room=l_room,
                                       listener_room=s_room)
                        for f in fields.values()}
                    assert None not in answers or answers == {None}, (
                        s_room, s_cell, l_room, l_cell, answers)
                    if answers != {None}:
                        # One number, to within the order the products
                        # happened to be multiplied in.
                        assert max(answers) - min(answers) <= 1e-9, (
                            s_room, s_cell, l_room, l_cell, answers)
                    seen |= answers
                    pairs += 1
    assert pairs >= 100
    assert any(g and g > 0.0 for g in seen)        # the arch does carry


def test_a_shout_across_the_arch_is_heard_from_either_side():
    """The same beat both ways round: the pair either hears or does not, and
    the two bodies never disagree about which."""
    sc = scene(_pair_rooms(), {"S": "yard", "L": "gate"},
               {"S": {"at": "well"}, "L": {"at": "bench"}})
    assert levels(sc, "S", "L")["shout"] == levels(sc, "L", "S")["shout"]
    assert levels(sc, "S", "L")["shout"] != "none"


# ---------------------------------------------------------------------------
# PA5: one masking rule, on every path
# ---------------------------------------------------------------------------

def _three_rooms(bell=None):
    """A chain of three rooms through open doors: the listener is two hops
    from the speaker, so no composite places the pair and the edge model is
    what answers."""
    rooms = {
        "kitchen": room("medium", {"stove": {"desc": "the stove", "dir": "s",
                                             "height": "waist"}},
                        [{"to": "stair", "barrier": "open_door", "dir": "n"}]),
        "stair": room("medium", {"rail": {"desc": "the rail", "dir": "e",
                                          "height": "waist"}},
                      [{"to": "kitchen", "barrier": "open_door", "dir": "s"},
                       {"to": "watch", "barrier": "open_door", "dir": "n"}]),
        "watch": room("medium", {"lamp": {"desc": "the great lamp", "dir": "n",
                                          "height": "waist"},
                                 "rail2": {"desc": "the gallery rail",
                                           "dir": "s", "height": "waist"}},
                      [{"to": "stair", "barrier": "open_door", "dir": "s"}]),
    }
    entities = {}
    if bell:
        entities["bell"] = {"name": "the fog bell", "sound_source": bell}
    sc = scene(rooms, {"S": "kitchen", "L": "watch"},
               {"S": {"at": "stove"}, "L": {"at": "lamp"}}, entities=entities)
    if bell:
        sc["positions"]["bell"] = "watch"
    return sc


def test_noise_beside_the_listener_masks_a_voice_from_beyond_the_field():
    """PA5. A listener's noise floor is a property of where the LISTENER
    stands, so it grades a voice from two rooms off exactly as it grades one
    in the room. Live: the fog bell drowned an ordinary voice IN the watch
    room (signal 0.34, noise 20.5) while a shout from three rooms away
    arrived whole, because the edge model had no idea there was a bell
    (`PLAY_2026_09_05_lighthouse.md` § PA5)."""
    quiet = _three_rooms()
    assert "signal" not in spatial_rel_between(quiet, "L", "S")
    assert levels(quiet, "S", "L")["shout"] != "none"   # edge model, unchanged
    loud = _three_rooms(bell="deafening")
    rel = spatial_rel_between(loud, "L", "S")
    assert rel.get("door_gain") and rel.get("noise")
    assert levels(loud, "S", "L")["shout"] == "none"
    # And the same bell drowns a voice IN the room, which it always did:
    # one rule, both paths.
    same_room = _three_rooms(bell="deafening")
    same_room["positions"]["S"] = "watch"
    same_room["stations"]["S"] = {"at": "rail2"}
    assert levels(same_room, "S", "L")["shout"] == "none"


def test_a_quiet_room_masks_nothing_and_a_vouched_channel_is_exempt():
    """The ceiling only ever subtracts, and only where there is noise to
    subtract by: a quiet listener's answers are the edge model's own."""
    rel = spatial_rel_between(_three_rooms(), "L", "S")
    bare = {k: v for k, v in rel.items() if k not in ("door_gain", "noise")}
    for volume in VOLUMES:
        assert hear_level(rel, volume) == hear_level(bare, volume)
    # A vouched channel is not this room's air: the doorway says nothing.
    loud = spatial_rel_between(_three_rooms(bell="deafening"), "L", "S")
    loud["barrier"] = "unknown"
    assert hear_level(loud, "shout", vouched=True) == "fragment"


# ---------------------------------------------------------------------------
# PC3: a raised voice carries through an opening
# ---------------------------------------------------------------------------

def _across_one_edge(barrier="open", *, machine=None, at_the_ear=False):
    """Two rooms joined by one edge, the bodies at the far wall of each, and
    an optional machine running in the listener's room -- far off unless
    `at_the_ear`, which stands it on the listener's own anchor."""
    entities = {}
    if machine:
        entities["m"] = {"name": "the machine", "sound_source": machine}
    sc = scene(two_rooms(barrier), {"S": "a", "L": "b"},
               {"S": {"at": "c"}, "L": {"at": "w"}}, entities=entities)
    if machine:
        sc["positions"]["m"] = "b"
        if at_the_ear:
            sc["stations"]["m"] = {"at": "w"}
    return sc


def test_a_raised_voice_across_one_opening_is_at_worst_a_fragment():
    """PC3's second half. The edge model always delivered a shout through an
    archway; the field, which knows the path and the noise, can refuse the
    same shout -- so when both perception passes came to read the field a
    shout across one open archway could reach nobody at all. One passable
    edge away, a raised voice floors at `fragment`."""
    from world.spatial import sound_field_hear_level
    sc = _across_one_edge("open", machine="loud")
    rel = spatial_rel_between(sc, "L", "S")
    assert rel.get("open_edge") is True
    assert rel.get("signal") is not None          # the field DID place them
    assert sound_field_hear_level("shout", rel["signal"], rel["noise"]) == "none"
    assert hear_level(rel, "shout") == "fragment"
    assert hear_level(rel, "loud") == "fragment"
    # Only a RAISED voice: an ordinary one still follows the field.
    assert hear_level(rel, "normal") == "none"
    # And it is the same answer from either end (PB2): the machine is in
    # L's room, so the two noises differ and the OPENING does not.
    other_way = spatial_rel_between(sc, "S", "L")
    assert other_way.get("open_edge") is True
    assert hear_level(other_way, "shout") != "none"


def test_the_floor_needs_an_opening_and_yields_to_the_room_it_arrives_in():
    """A shut door is not an opening, two edges away is not one edge, and an
    opening carries a voice INTO a room rather than through the machine
    running in it -- the same masking rule everything else answers to."""
    shut = spatial_rel_between(_across_one_edge("closed_door",
                                                machine="loud"), "L", "S")
    assert not shut.get("open_edge")
    assert hear_level(shut, "shout") == "none"
    two_hops = spatial_rel_between(_three_rooms(), "L", "S")
    assert not two_hops.get("open_edge")
    drowned = spatial_rel_between(
        _across_one_edge("open", machine="deafening", at_the_ear=True),
        "L", "S")
    assert drowned.get("open_edge") is True
    assert hear_level(drowned, "shout") == "none"


def test_the_opening_is_one_doorway_however_it_was_declared():
    """A doorway is one object: an edge declared from either side is the
    same opening, which is also what keeps the floor reciprocal."""
    from world.spatial import one_opening_away
    sc = _across_one_edge("open")
    sc["rooms"]["b"]["adjacent"] = []             # declared from `a` alone
    assert one_opening_away(sc, "a", "b") is True
    assert one_opening_away(sc, "b", "a") is True
    assert one_opening_away(sc, "a", "a") is False
    # A paper door is the opening it acoustically is; a steel one is not.
    paper = scene(two_rooms("closed_door", material="paper"),
                  {"S": "a", "L": "b"}, {"S": {"at": "c"}, "L": {"at": "w"}})
    assert one_opening_away(paper, "a", "b") is True


# ---------------------------------------------------------------------------
# PC4: a drop is a source wavering, not a source stopping
# ---------------------------------------------------------------------------

def test_a_flickering_source_on_the_bottom_rung_still_sounds():
    """A `faint` source on a dropped beat keeps the quietest sound it can
    make; only `failing` goes out, and only that files a notice."""
    from world.spatial import _power_of_level, SOUND_POWER
    assert _power_of_level("faint", "dropped") == SOUND_POWER["faint"]
    assert _power_of_level("audible", "dropped") == SOUND_POWER["faint"]
    assert _power_of_level("faint", "out") == 0.0
    beat = next(b for b in range(4000)
                if steadiness_this_beat("flickering", b, "hum") == "dropped")
    sc = scene(hall(), {"L": "hall", "hum": "hall"}, {"L": {"at": "west"}},
               entities={"hum": {"name": "the vent", "sound_source": "faint",
                                 "steadiness": "flickering"}})
    sources, notices = sound_sources(sc, turn_idx=beat)
    assert [s["id"] for s in sources] == ["hum"]
    assert sources[0]["power"] > 0.0
    assert notices == []


# ---------------------------------------------------------------------------
# DECIBELS (DESIGN_SOUND_DECIBELS.md § 2A, 2026-09-05)
#
# The conversion is arithmetic, not a behaviour change, and these are the
# proof. One class of test asserts the two TABLES are the same numbers in two
# denominations; the other asserts the two PATHS answer the same WORD, over
# the suite's own fixtures and over randomised levels.
# ---------------------------------------------------------------------------

def test_the_decibel_tables_are_exact_conversions_of_the_powers():
    """Every dB table is `10*log10(P) + DB_REF` of the power table it
    denominates, every loss the negative of a factor's, and both thresholds
    the ratios they replace. The two rungs that are NOT a conversion are the
    two the ladder never had."""
    from world.spatial import (
        AMBIENT, AMBIENT_DB, APERTURE_LOSS_DB, APERTURE_PASS, db_of_power,
        db_ratio, FAR_FIELD_ENTRY_DB, FRAGMENT_SNR, FRAGMENT_SNR_DB, FULL_SNR,
        FULL_SNR_DB, HEAR_FLOOR, HEAR_FLOOR_DB, OCCLUDER_LOSS_DB,
        OCCLUDER_PASS, power_of_db, SOUND_DB, SOUND_POWER, SPEECH_DB,
        SPEECH_POWER)

    for word, power in SPEECH_POWER.items():
        assert SPEECH_DB[word] == db_of_power(power)
    for word, power in AMBIENT.items():
        assert AMBIENT_DB[word] == db_of_power(power)
    for word, power in SOUND_POWER.items():
        assert SOUND_DB[word] == db_of_power(power)
    for barrier, factor in APERTURE_PASS.items():
        if factor <= 0:
            # A wall is not an aperture on the near field, so it is not in
            # the aperture table at all -- its transmission is the far
            # field's `WALL_LOSS_DB`.
            assert barrier not in APERTURE_LOSS_DB
            continue
        assert APERTURE_LOSS_DB[barrier] == pytest.approx(-db_ratio(factor))
    assert OCCLUDER_LOSS_DB == pytest.approx(-db_ratio(OCCLUDER_PASS))
    assert FULL_SNR_DB == pytest.approx(db_ratio(FULL_SNR))
    assert FRAGMENT_SNR_DB == pytest.approx(db_ratio(FRAGMENT_SNR))
    assert HEAR_FLOOR_DB == db_of_power(HEAR_FLOOR)

    # The two new rungs, declared in dB and reaching where nothing did.
    assert SOUND_LEVELS[-2:] == ("thunderous", "catastrophic")
    assert SOUND_DB["thunderous"] == pytest.approx(85.0)
    assert SOUND_DB["catastrophic"] == pytest.approx(100.0)
    assert SOUND_POWER["catastrophic"] == pytest.approx(power_of_db(100.0))
    # ... and they are the only rungs the far field admits.
    assert [w for w in SOUND_LEVELS if SOUND_DB[w] >= FAR_FIELD_ENTRY_DB] \
        == ["thunderous", "catastrophic"]


def test_the_two_quantisers_agree_over_randomised_levels():
    """THE PROPERTY. `quantise_hearing` (linear, the path that shipped) and
    `quantise_hearing_db` (the path that runs) give the same word for any
    pair -- including the exact ties a synthetic fixture constructs, which
    is what the dB comparison's slack is for."""
    import random
    from world.spatial import (
        db_of_power, FRAGMENT_SNR, FULL_SNR, HEAR_FLOOR, quantise_hearing,
        quantise_hearing_db)

    rng = random.Random(20260905)
    pairs = []
    for _ in range(4000):
        noise = rng.choice([0.0, 10.0 ** rng.uniform(-4, 2)])
        pairs.append((10.0 ** rng.uniform(-5, 3), noise))
    # The boundaries themselves, exactly on them and to either side. The
    # nudges are RELATIVE, because the tolerance the conversion needs is: a
    # margin stated in dB is a ratio, so "a hair under twice the noise" is
    # `2n * (1 - e)` and not `2n - e`. An absolute nudge means something
    # different at 0.05 than at 24, and below about 1e-13 of the level it
    # means nothing at all -- it is under the resolution the logarithm
    # itself has, which is what `_DB_EPS` is measured against.
    for noise in (0.05, 0.1, 0.2, 1.0, 12.0, 4096.0):
        for ratio in (FULL_SNR, FRAGMENT_SNR):
            for nudge in (1.0, 1 - 1e-9, 1 + 1e-9, 1 - 1e-6, 1 + 1e-6):
                pairs.append((ratio * noise * nudge, noise))
    for nudge in (1.0, 1 - 1e-9, 1 + 1e-9):
        pairs.append((HEAR_FLOOR * nudge, 0.0))
        pairs.append((HEAR_FLOOR * nudge, HEAR_FLOOR / FRAGMENT_SNR))

    disagreed = [(s, n) for s, n in pairs
                 if quantise_hearing(s, n)
                 != quantise_hearing_db(db_of_power(s), db_of_power(n))]
    assert disagreed == [], (
        "the decibel path and the linear path answer differently for "
        "%d of %d pairs, starting at %r" % (len(disagreed), len(pairs),
                                            disagreed[:3]))


def _fixture_scenes():
    """Every scene this module's fixtures build, as (name, scene, bodies).
    The conversion identity is asserted over all of them at once."""
    out = [("hall", scene(hall(), {"A": "hall", "B": "hall"},
                          {"A": {"at": "west"}, "B": {"at": "south"}}),
            ("A", "B"))]
    for barrier in ("open", "open_door", "bars", "membrane", "closed_door",
                    "window"):
        out.append(("two rooms, %s" % barrier,
                    scene(two_rooms(barrier), {"A": "a", "B": "b"},
                          {"A": {"at": "c"}, "B": {"at": "w"}}),
                    ("A", "B")))
    for material in ("paper", "steel"):
        out.append(("closed door in %s" % material,
                    scene(two_rooms("closed_door", material),
                          {"A": "a", "B": "b"},
                          {"A": {"at": "c"}, "B": {"at": "w"}}), ("A", "B")))
    out.append(("a loud generator in the hall",
                scene(hall(), {"A": "hall", "B": "hall", "gen": "hall"},
                      {"A": {"at": "west"}, "B": {"at": "south"},
                       "gen": {"at": "east"}},
                      entities={"gen": {"name": "the generator",
                                        "sound_source": "loud"}}),
                ("A", "B")))
    out.append(("outdoors in heavy rain",
                scene({"yard": room("large", {"well": {"desc": "a well",
                                                       "dir": "n",
                                                       "height": "waist"}},
                                    exposure="open")},
                      {"A": "yard", "B": "yard"}, {"A": {"at": "well"}},
                      weather={"sky": "rain", "intensity": "heavy",
                               "wind": "gale"}),
                ("A", "B")))
    out.append(("no geometry at all",
                scene(hall(geometry=False), {"A": "hall", "B": "hall"},
                      {"A": {"at": "west"}, "B": {"at": "south"}}),
                ("A", "B")))
    return out


@pytest.mark.parametrize("name,sc,bodies", _fixture_scenes(),
                         ids=[row[0] for row in _fixture_scenes()])
def test_every_sound_fixture_gets_the_same_word_in_decibels(name, sc, bodies):
    """THE CONVERSION IDENTITY. For every pair and every volume in every
    fixture this module builds, the word the engine answers today is the
    word the linear arithmetic it replaced would have answered from the
    same stamped relation.

    Stated over the RELATION rather than over the field, because the
    relation is where the two models meet: `signal` is a path gain and
    `noise` a floor, both linear, both untouched by the conversion -- so if
    a word moved, the quantiser moved it, and this is the test that says so.
    """
    from world.spatial import quantise_hearing, SPEECH_POWER

    graded = 0
    for listener, speaker in ((bodies[0], bodies[1]), (bodies[1], bodies[0])):
        rel = spatial_rel_between(sc, listener, speaker)
        if rel.get("signal") is None or rel.get("noise") is None:
            continue                    # no field: the edge model, untouched
        for volume in VOLUMES:
            graded += 1
            word = hear_level(rel, volume)
            linear = quantise_hearing(SPEECH_POWER[volume] * rel["signal"],
                                      rel["noise"])
            assert word == linear, (
                "%s: %s hearing %s at %s is %r in decibels and %r linearly "
                "(signal %r, noise %r)" % (name, listener, speaker, volume,
                                           word, linear, rel["signal"],
                                           rel["noise"]))
    if name != "no geometry at all":
        assert graded, "%s graded nothing on the field" % name


def test_the_noise_ladder_is_the_same_three_words_in_decibels():
    """`noise_word` moved into dB with everything else; the words it hands
    the composer did not move with it."""
    import random
    from world.spatial import (db_of_power, FRAGMENT_SNR, FULL_SNR,
                              noise_word, noise_word_db, VOICE_ONE_PACE)
    rng = random.Random(5092026)
    floors = [0.0, VOICE_ONE_PACE / FULL_SNR, VOICE_ONE_PACE / FRAGMENT_SNR]
    floors += [10.0 ** rng.uniform(-4, 2) for _ in range(2000)]
    for floor in floors:
        assert noise_word(floor) == noise_word_db(db_of_power(floor))


def test_an_event_reads_its_level_word_its_number_and_its_old_intensity():
    """`event_db`, in the one order it reads: an authored `db` first (the
    escape hatch for anything the words do not reach), then `level` off the
    ladder, then the `intensity` `sensory_events` has always carried."""
    from world.spatial import event_db, SOUND_DB, SPEECH_DB
    assert event_db({"db": 137.0}) == 137.0
    assert event_db({"db": 137.0, "level": "faint"}) == 137.0
    assert event_db({"level": "catastrophic"}) == SOUND_DB["catastrophic"]
    assert event_db({"intensity": "shout"}) == SPEECH_DB["shout"]
    assert event_db({"intensity": 1.0}) == SOUND_DB["deafening"]
    assert event_db({}) == SOUND_DB["audible"]


# ---------------------------------------------------------------------------
# THE FAR FIELD (DESIGN_SOUND_DECIBELS.md § 2B/2C)
#
# Beyond the near field's one hop, a loud sound floods the ROOM graph by
# accumulated loss in dB and stops when it is inaudible. There is no hop cap
# and there must not be one: the reach of a sound is a property of how loud
# it is.
# ---------------------------------------------------------------------------

def bare_room(size="medium", adjacent=(), exposure="enclosed"):
    """A room with NO anchor geometry: the near field does not exist for it,
    so what these tests measure is the far field alone."""
    return {"name": "a room", "size": size, "exposure": exposure,
            "adjacent": list(adjacent), "anchors": {}}


def chain(n, barrier="open_door", size="medium", exposure="enclosed"):
    """`n` rooms in a line, each joined to the next by `barrier`."""
    rooms = {}
    for i in range(n):
        adjacent = []
        if i:
            adjacent.append({"to": "r%d" % (i - 1), "barrier": barrier,
                             "dir": "w"})
        if i < n - 1:
            adjacent.append({"to": "r%d" % (i + 1), "barrier": barrier,
                             "dir": "e"})
        rooms["r%d" % i] = bare_room(size, adjacent, exposure)
    return scene(rooms, {})


def crash(room="r0", level="catastrophic", detail="a long grinding collapse"):
    return [{"kind": "sound", "source_room": room, "level": level,
             "detail": detail}]


def test_a_wall_passes_a_catastrophic_event_and_refuses_a_shout():
    """THE OWNER'S SENTENCE. `APERTURE_PASS["wall"]` was 0 -- right for
    sight, where the table came from -- so no explosion, ever, was heard
    through a wall by anyone. A wall attenuates; it does not abolish.

    The near field is untouched by this: a wall is still not an aperture and
    still places no neighbour, because there is no cell path through a wall
    to walk. The finite transmission is the far field's, on the room graph,
    where a sound does not need a doorway to have crossed."""
    from world.spatial import (AMBIENT_DB, distant_level_word,
                               room_sound_flood, SOUND_DB, SPEECH_DB,
                               WALL_LOSS_DB)
    sc = chain(4, barrier="wall")
    floor = AMBIENT_DB["enclosed"]

    heard = room_sound_flood(sc, "r0", SOUND_DB["catastrophic"])
    assert distant_level_word(heard["r1"]["db"], floor), (
        "a catastrophic event is not heard through one wall")
    # ... and two rooms away it IS the fragment the note asked for.
    # RESOLVED 2026-09-05: 45 dB was the real-world transmission loss of a
    # masonry wall, standing in a table whose other seven entries are on a
    # scale compressed by 0.358 (whisper->shout spans 20.8 dB here against
    # 58 in the world, and window/open_door/membrane are all already
    # compressed). A real 45 dB wall on this scale is 16, and at 16 the
    # note's own sentence is finally true through a wall as well as through
    # a doorway.
    assert distant_level_word(heard["r2"]["db"], floor), (
        "a catastrophic event is not heard two rooms away")
    assert "r4" not in heard, "it should not carry forever either"

    # A voice never crosses one, at any volume -- which is what makes the
    # wall a wall rather than a slow door.
    for volume, level in SPEECH_DB.items():
        reached = room_sound_flood(sc, "r0", level)
        assert not distant_level_word(reached.get("r1", {}).get("db", -999.0),
                                      floor), volume
    assert WALL_LOSS_DB == 16.0


def test_a_floor_is_a_wall_that_goes_up_and_a_stair_is_not():
    """A vertical edge that is a WALL is a floor or a ceiling and costs
    `FLOOR_CEILING_LOSS_DB`; a vertical edge that is an OPENING is a
    stairwell and keeps its aperture's loss. A vertical passage's barrier
    already has one."""
    from world.spatial import (APERTURE_LOSS_DB, far_field_graph,
                               FLOOR_CEILING_LOSS_DB, WALL_LOSS_DB)
    sc = scene({"below": bare_room(adjacent=[
                    {"to": "above", "barrier": "wall", "vertical": "up"}]),
                "above": bare_room()}, {})
    assert far_field_graph(sc)["below"]["above"] == FLOOR_CEILING_LOSS_DB
    sc = scene({"below": bare_room(adjacent=[
                    {"to": "above", "barrier": "open", "vertical": "up"}]),
                "above": bare_room()}, {})
    assert far_field_graph(sc)["below"]["above"] == APERTURE_LOSS_DB["open"]
    # A horizontal wall is a partition and costs the partition's number.
    sc = scene({"a": bare_room(adjacent=[{"to": "b", "barrier": "wall",
                                          "dir": "e"}]),
                "b": bare_room()}, {})
    assert far_field_graph(sc)["a"]["b"] == WALL_LOSS_DB


def test_the_far_field_terminates_on_audibility_and_has_no_hop_cap():
    """A hundred rooms in a line and no counter anywhere. What stops the
    flood is that the sound stops being audible: loss only accumulates, so
    once a room is under the quietest floor the model has, no room beyond it
    can be over it. How far a sound goes is then a property of HOW LOUD IT
    IS, which is the whole claim."""
    from world.spatial import (AMBIENT_DB, FRAGMENT_SNR_DB, HEAR_FLOOR_DB,
                               room_sound_flood, SOUND_DB,
                               _inaudible_everywhere_db)
    sc = chain(100)
    reach = {level: len(room_sound_flood(sc, "r0", SOUND_DB[level]))
             for level in SOUND_LEVELS}
    assert reach["catastrophic"] > reach["thunderous"] > reach["deafening"]
    assert reach["catastrophic"] == 51 and reach["thunderous"] == 29
    assert reach["catastrophic"] < 100, (
        "the flood must stop of its own arithmetic, not run out of rooms")
    # The cut is the quietest floor the model has at the `fragment` margin,
    # or the absolute floor -- whichever is higher.
    assert _inaudible_everywhere_db() == max(
        AMBIENT_DB["enclosed"] + FRAGMENT_SNR_DB, HEAR_FLOOR_DB)
    for rec in room_sound_flood(sc, "r0", SOUND_DB["catastrophic"]).values():
        assert rec["db"] >= _inaudible_everywhere_db()


def test_a_far_field_path_has_no_direction():
    """RECIPROCITY, one level up from the near field's (§ PB2, repaired the
    same day this was built): the loss between two rooms is one number, so a
    sound in A reaching B and the same sound in B reaching A arrive at the
    same level. The graph is undirected because a doorway is one object and
    may be declared from either side."""
    from world.spatial import far_field_graph, room_sound_flood, SOUND_DB
    # Declared from ONE side only, and a ring so there are two ways round.
    rooms = {
        "hall": bare_room("large", [{"to": "stair", "barrier": "open_door",
                                     "dir": "n"},
                                    {"to": "cellar", "barrier": "wall",
                                     "dir": "s"}]),
        "stair": bare_room("small", [{"to": "cellar", "barrier": "open",
                                      "dir": "s"}]),
        "cellar": bare_room("huge"),
    }
    sc = scene(rooms, {})
    graph = far_field_graph(sc)
    for a, b in (("hall", "stair"), ("stair", "cellar"), ("hall", "cellar")):
        assert graph[a][b] == graph[b][a], (a, b)
    db = SOUND_DB["catastrophic"]
    for a, b in (("hall", "cellar"), ("cellar", "hall"), ("hall", "stair")):
        there = room_sound_flood(sc, a, db)[b]["db"]
        back = room_sound_flood(sc, b, db)[a]["db"]
        assert there == pytest.approx(back), (a, b, there, back)


def test_the_flood_takes_the_quietest_way_round_and_not_the_shortest():
    """ACCUMULATED LOSS, not hops. One wall away is one hop; three open
    doorways round is three, and the sound arrives by the long way because
    45 dB is more than three rooms of spreading."""
    from world.spatial import room_sound_flood, SOUND_DB
    rooms = {
        "a": bare_room(adjacent=[{"to": "d", "barrier": "wall", "dir": "e"},
                                 {"to": "b", "barrier": "open", "dir": "n"}]),
        "b": bare_room(adjacent=[{"to": "c", "barrier": "open", "dir": "e"}]),
        "c": bare_room(adjacent=[{"to": "d", "barrier": "open", "dir": "s"}]),
        "d": bare_room(),
    }
    sc = scene(rooms, {})
    reached = room_sound_flood(sc, "a", SOUND_DB["catastrophic"])
    assert reached["d"]["via"] == "c", "the flood took the wall"


def test_the_near_field_and_the_far_field_never_answer_the_same_room():
    """THE BOUNDARY IS A HANDOVER, NOT AN ARGUMENT. Between a cell model and
    a room model there is no arithmetic that makes two different derivations
    agree to the decibel, so the far field is not asked about a room the
    listener's own composite already places: every room on that composite is
    the near field's, and a listener is never answered twice about one
    sound. The rooms the near field lays are exactly `grid.offsets`."""
    from world.spatial import distant_sounds, sound_field
    rooms = two_rooms("open_door")
    rooms["c"] = bare_room(adjacent=[{"to": "b", "barrier": "open_door",
                                      "dir": "e"}])
    rooms["b"]["adjacent"].append({"to": "c", "barrier": "open_door",
                                   "dir": "w"})
    sc = scene(rooms, {"L": "a"}, {"L": {"at": "c"}})
    field = sound_field(sc, "L")
    assert field is not None and set(field.grid.offsets) == {"a", "b"}

    events = crash("b")                 # in a room the near field DOES place
    assert distant_sounds(sc, "L", room="a", events=events,
                          near_rooms=field.grid.offsets) == []
    # ... and the same event two rooms out, which the near field cannot
    # reach at all, is the far field's and is delivered.
    heard = distant_sounds(sc, "L", room="a", events=crash("c"),
                           near_rooms=field.grid.offsets)
    assert [r["level"] for r in heard] == ["overwhelming"]
    assert heard[0]["bearing"]["barrier"] == "open_door"
    # Without a near field there is nothing to hand over from, and the
    # neighbour is the far field's like any other room.
    assert distant_sounds(sc, "L", room="a", events=events)


def test_no_speech_crosses_the_far_field_at_any_volume_or_distance():
    """THE FIREWALL FLOOR, and it is not a threshold. A body two streets
    away who "hears" a line is the same defect as one who sees through a
    wall, so speech is refused at the only door it could come through --
    `far_field_sources` has no `speakers` parameter and drops the kind --
    and no setting of any constant can open it.

    Belt and braces, both stated: a shout is 60.8 dB against an entry of 70,
    so the loudest voice there is would not qualify even if the kind check
    were removed. And the record the far field returns has no key for
    content: it is built field by field from a closed set."""
    from world.spatial import (distant_sounds, FAR_FIELD_ENTRY_DB,
                               far_field_sources, SPEECH_DB)
    sc = chain(3)
    sc["positions"] = {"Ada": "r0", "Bel": "r2"}
    for volume in SPEECH_DB:
        speakers = {"Ada": volume}
        sources, _n = sound_sources(sc, speakers=speakers)
        assert any(s["kind"] == "speech" for s in sources)
        # The field's own source list carries the voice; the far field's
        # does not, and cannot be asked to.
        assert far_field_sources(sc) == []
        assert max(SPEECH_DB.values()) < FAR_FIELD_ENTRY_DB

    # An event that TRIES to smuggle a line through the channel carries it
    # nowhere: the record has room for a character and no room for words.
    events = [{"kind": "sound", "source_room": "r0", "level": "catastrophic",
               "detail": "a shattering roar", "text": "RUN, THEY ARE HERE",
               "speaker": "Ada", "quote": "RUN", "body": "RUN",
               "line": "RUN", "room": "r0"}]
    heard = distant_sounds(sc, "Bel", room="r2", events=events)
    assert heard and set(heard[0]) == {"kind", "level", "db", "character",
                                       "bearing"}
    blob = repr(heard)
    for leak in ("RUN", "THEY ARE HERE", "Ada", "r0", "r1"):
        assert leak not in blob, (leak, blob)
    assert heard[0]["character"] == "a shattering roar"


def test_a_running_thing_delivers_a_direction_and_no_description_of_itself():
    """A distant listener may be told what a sound was LIKE and never what
    the thing making it looks like. The engine has a public description of
    the THING and none of its sound, so a source that is not a one-beat
    event contributes a direction and a level and no character at all --
    handing over `desc` would put a sight fact on a hearing channel."""
    from world.spatial import distant_sounds
    sc = chain(3)
    sc["entities"] = {"forge": {"name": "the drop hammer",
                                "desc": "a black iron ram on a brass frame",
                                "sound_source": "catastrophic"}}
    sc["positions"] = {"forge": "r0"}
    heard = distant_sounds(sc, "Bel", room="r2")
    assert heard and heard[0]["character"] == ""
    blob = repr(heard)
    assert "drop hammer" not in blob and "brass" not in blob


def test_an_ordinary_beat_walks_no_graph_at_all(monkeypatch):
    """COST. Nothing under `FAR_FIELD_ENTRY_DB` enters the far field, and
    the loudest thing an ordinary beat holds is a shout at 60.8 dB against
    an entry of 70. So on an ordinary beat `distant_sounds` returns before
    it builds a graph -- proved by making the graph impossible to build and
    watching nothing fail."""
    from world.spatial import distant_sounds
    import world.spatial_sound_field as field_module

    sc = chain(40)
    sc["entities"] = {"gen": {"name": "a generator", "sound_source": "loud"}}
    sc["positions"] = {"gen": "r0"}
    calls = []
    real = field_module.far_field_graph

    def counted(*a, **k):
        calls.append(1)
        return real(*a, **k)

    monkeypatch.setattr(field_module, "far_field_graph", counted)
    for level in ("faint", "audible", "loud", "deafening"):
        sc["entities"]["gen"]["sound_source"] = level
        assert distant_sounds(sc, "L", room="r9",
                              events=crash("r0", "audible")) == []
    assert calls == [], "the far field built a graph on an ordinary beat"
    sc["entities"]["gen"]["sound_source"] = "thunderous"
    assert distant_sounds(sc, "L", room="r9")
    assert calls, "the far field did not run when something was loud"


def test_a_distant_sound_is_graded_by_the_room_it_arrives_in():
    """The three words are a MARGIN over the listening room's own floor, so
    the same event is overwhelming in a sealed room and merely plain in a
    gale -- which is the same masking rule everything else here obeys."""
    from world.spatial import distant_sounds, DISTANT_LEVELS
    quiet = chain(60)
    ladder, levels_db = [], []
    for i in range(1, 60):
        heard = distant_sounds(quiet, "L", room="r%d" % i, events=crash())
        if not heard:
            break
        ladder.append(heard[0]["level"])
        levels_db.append(heard[0]["db"])
    # The three words in order, each once it is earned, and the level only
    # ever falls with distance.
    assert set(ladder) == set(DISTANT_LEVELS)
    assert ladder == sorted(ladder, key=DISTANT_LEVELS.index, reverse=True)
    assert levels_db == sorted(levels_db, reverse=True)
    # The same event arriving at the same level is graded a rung quieter in
    # a noisier room, because the word is a MARGIN and not a level: an open
    # yard's floor is 6 dB over a sealed room's, and it takes the sound down
    # with it without moving it a pace.
    from world.spatial import AMBIENT_DB, distant_level_word
    open_air = chain(60, exposure="open")
    quieter = [distant_sounds(open_air, "L", room="r%d" % i, events=crash())
               for i in range(1, len(ladder) + 1)]
    quieter = [row[0]["level"] if row else None for row in quieter]
    rung = {None: -1, **{w: i for i, w in enumerate(DISTANT_LEVELS)}}
    assert all(rung[b] <= rung[a] for a, b in zip(ladder, quieter))
    assert quieter != ladder, "a louder room graded nothing differently"
    at = levels_db[ladder.index("overwhelming") - 1] if "overwhelming" \
        in ladder else levels_db[0]
    assert distant_level_word(at, AMBIENT_DB["enclosed"]) \
        != distant_level_word(at, AMBIENT_DB["open"] + 20.0)


# ---------------------------------------------------------------------------
# THE EVENT CHANNEL (docs/UNBUILT.md § 1.117)
# ---------------------------------------------------------------------------

def test_a_sound_that_happens_is_heard_on_its_beat_and_not_the_next():
    """THE GAP § 1.117 NAMED. A bell rung once was either a permanent source
    or nothing; now it is a record carrying the beat that made it, and every
    reader asks for a beat. Nothing expires on a counter -- the beat number
    IS the lifetime."""
    from world.spatial import beat_sensory_events, SENSORY_EVENTS_KEY
    sc = chain(3)
    sc[SENSORY_EVENTS_KEY] = {"beat": 7, "events": crash()}
    assert beat_sensory_events(sc, 7) == crash()
    assert beat_sensory_events(sc, 8) == []
    assert beat_sensory_events(sc, 6) == []
    assert beat_sensory_events(sc, None) == []
    assert beat_sensory_events({}, 7) == []


def test_the_event_record_keeps_the_notes_shape_and_nothing_else():
    """`{kind, room, level | db, source, detail}` -- a closed set of keys, so
    a hand that writes prose into a key nobody reads writes it into
    nothing."""
    from world.spatial import normalize_sensory_event
    record = normalize_sensory_event(
        {"kind": "SOUND", "room": "r0", "level": "Thunderous", "db": 121.5,
         "source": "the north gate", "detail": "  a long   splintering  ",
         "quote": "let me in", "speaker": "Ada"}, rooms={"r0": {}})
    assert record == {"kind": "sound", "room": "r0", "level": "thunderous",
                      "db": 121.5, "source": "the north gate",
                      "detail": "a long splintering"}
    # A sound happens somewhere, or it is not an event this engine holds.
    assert normalize_sensory_event({"level": "loud"}, rooms={"r0": {}}) is None
    assert normalize_sensory_event({"room": "nowhere"},
                                   rooms={"r0": {}}) is None
    # The older `intensity` survives for the opening turn, which writes it.
    assert normalize_sensory_event({"room": "r0", "intensity": 0.4},
                                   rooms={"r0": {}})["intensity"] == 0.4


def test_every_barrier_in_the_table_is_on_one_scale():
    """THE DEFECT WAS A UNIT, AND THIS IS THE GUARD AGAINST IT RETURNING.

    `WALL_LOSS_DB` was 45 -- the real-world transmission loss of a masonry
    wall -- in a table whose other entries are derived from `APERTURE_PASS`,
    which was calibrated against the near field's own sentences. The two
    scales differ by a measurable, constant factor, so a number entered in
    one of them behaved like a bunker in the other: only `catastrophic`
    crossed one wall and NOTHING crossed two, which made a collapsing roof
    two rooms away silent (`docs/UNBUILT.md` § 1.125).

    The compression is derived here rather than asserted, from the speech
    ladder against the levels a real voice has, and it comes out the same
    from two independent spans. Every barrier is then checked against its
    own real-world value scaled by it. A future edit that reaches for a
    physical number and forgets to compress it fails this.
    """
    from world.spatial import (APERTURE_LOSS_DB, FLOOR_CEILING_LOSS_DB,
                               SPEECH_DB, WALL_LOSS_DB)

    # A whisper is ~30 dBA at a metre, ordinary speech ~60, a shout ~88.
    k_wide = (SPEECH_DB["shout"] - SPEECH_DB["whisper"]) / (88.0 - 30.0)
    k_narrow = (SPEECH_DB["shout"] - SPEECH_DB["normal"]) / (88.0 - 60.0)
    assert abs(k_wide - k_narrow) < 0.01, (k_wide, k_narrow)
    assert 0.30 < k_wide < 0.42, k_wide

    real = {"open": 0.0, "open_door": 2.0, "bars": 2.0, "membrane": 5.0,
            "closed_door": 25.0, "window": 28.0, "one_way_window": 28.0}
    for barrier, engine_db in APERTURE_LOSS_DB.items():
        if barrier not in real:
            continue
        assert abs(engine_db - real[barrier] * k_wide) <= 4.0, (
            barrier, engine_db, real[barrier] * k_wide)
    # The two that were raw, and are not any more.
    assert abs(WALL_LOSS_DB - 45.0 * k_wide) <= 4.0, WALL_LOSS_DB
    assert abs(FLOOR_CEILING_LOSS_DB - 50.0 * k_wide) <= 4.0
    # A floor is heavier than a wall, as concrete is heavier than plaster.
    assert FLOOR_CEILING_LOSS_DB > WALL_LOSS_DB


# ---------------------------------------------------------------------------
# What the field could not lay out, and what it silenced (2026-09-06)
# ---------------------------------------------------------------------------

def test_a_room_longer_than_it_is_wide_holds_its_own_centre():
    """`_centre(grid_side(...))` squared the room's LONGER side, so a room
    with a short side put its middle outside itself -- a 6 by 24 service
    spine answered (12, 12) with six cells of width. Every source placed
    there was off the grid and dropped, so a noise made in a corridor
    reached nobody, the people standing in it included."""
    from world.spatial import room_centre, room_grid

    sc = scene({"spine": {"name": "the spine", "extent": {"w": 6, "d": 24},
                          "exposure": "enclosed", "adjacent": [],
                          "anchors": {}}}, {"L": "spine"})
    grid = room_grid(sc, "spine")
    assert (grid.w, grid.d) == (6, 24)
    assert grid.contains(room_centre(sc, "spine"))
    events = [{"kind": "sound", "description": "a crash", "room": "spine",
               "level": "loud"}]
    sources, _ = sound_sources(sc, events=events)
    assert [s["cell"] for s in sources] == [room_centre(sc, "spine")]
    # And a square room keeps the cell it always had.
    assert room_centre(scene(hall(), {"L": "hall"}), "hall") == (4, 4)


def test_sounds_made_in_one_place_do_not_mask_each_other_into_silence():
    """A ratio test gives each of N equal sources `1 / (N - 1)` of the din,
    so two in one place were marginal and THREE WERE INAUDIBLE AT ANY
    VOLUME. A beat's events all stand at their room's centre -- a one-off
    noise says which room it was in and nothing finer -- so a pair of them
    in one room shared a cell by construction: chat 117 turn 13, a pry bar
    on a door frame and a detonation overhead, both `loud`, both in the
    spine, and the room through the open door beside it heard neither."""
    def crash(n):
        return [{"kind": "sound", "description": "crash %d" % i,
                 "source_room": "a", "level": "loud"} for i in range(n)]

    for count in (1, 2, 3, 5):
        heard = heard_events(
            scene(two_rooms("open_door"), {"L": "b"}, {"L": {"at": "w"}}),
            "L", crash(count))
        assert [level for _e, level in heard] == ["full"] * count, count
    # Two voices from two different places still mask each other: the rule
    # is about a sound arriving from the signal's OWN place, not about
    # loudness going unpunished.
    rooms = {"m": room("medium", {
        "t": {"desc": "a table", "dir": "n", "height": "waist"},
        "w": {"desc": "west", "dir": "w"}, "e": {"desc": "east", "dir": "e"},
        "s": {"desc": "south", "dir": "s"}})}
    sc = scene(rooms, {"A": "m", "B": "m", "L": "m"},
               {"A": {"at": "w"}, "B": {"at": "e"}, "L": {"at": "s"}})
    field = sound_field(sc, "L", speakers={"A": "normal", "B": "normal"})
    assert field.level_of("L", "speech:A") != "full"
    assert field.level_of("L", "speech:B") != "full"
