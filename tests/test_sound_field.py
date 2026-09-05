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
    the edge rules: same room, unmeasured proximity -> `full` for all five."""
    sc = scene(hall(geometry=False), {"S": "hall", "L": "hall"},
               {"S": {"at": "west"}, "L": {"at": "east"}})
    assert sound_field(sc, "L") is None
    rel = spatial_rel_between(sc, "L", "S")
    assert rel == {"same_room": True, "barrier": "open", "distance": "same",
                   "light": "lit"}
    assert levels(sc, "S", "L") == {v: "full" for v in VOLUMES}
    # And across a room boundary without geometry: the edge rules verbatim.
    rooms = two_rooms("closed_door")
    for r in rooms.values():
        for anchor in r["anchors"].values():
            anchor.pop("height", None)
    sc = scene(rooms, {"S": "a", "L": "b"}, {"S": {"at": "c"}, "L": {"at": "w"}})
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
    assert SOUND_LEVELS == ("faint", "audible", "loud", "deafening")
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
