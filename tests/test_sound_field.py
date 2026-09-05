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

import pytest

from world.spatial import (
    APERTURE_PASS,
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


def test_a_counter_costs_path_and_blocks_nothing():
    """From the hearth, a listener BEHIND the counter (`cover`) is reached
    round the end of the run -- path 10.0 against 4.4 for the near side --
    and a normal voice is `full` on both sides. Nothing inside a room stops
    sound; it is walked round."""
    behind = scene(hall(), {"S": "hall", "L": "hall"},
                   {"S": {"at": "south"}, "L": {"at": "counter", "cover": True}})
    before = scene(hall(), {"S": "hall", "L": "hall"},
                   {"S": {"at": "south"}, "L": {"at": "counter"}})
    f_behind = sound_field(behind, "L")
    f_before = sound_field(before, "L")
    l_behind = spread(f_behind.grid, f_behind.locate("S"))[f_behind.locate("L")][0]
    l_before = spread(f_before.grid, f_before.locate("S"))[f_before.locate("L")][0]
    assert l_behind > l_before
    assert levels(behind, "S", "L")["normal"] == "full"
    assert levels(before, "S", "L")["normal"] == "full"
    # The counter's own cells are REACHED -- a body standing at the counter
    # hears -- and never passed THROUGH: every cell behind the run is
    # reached by a path longer than the straight line to it, because the
    # flood went round the end.
    counter_cells = {f_behind.grid.cell_of("hall", c)
                     for c in f_behind.grid.anchors["hall"]["counter"]["cells"]}
    origin = f_behind.locate("S")
    reached = spread(f_behind.grid, origin)
    assert counter_cells <= set(reached)
    wall_side = [c for c in f_behind.grid.inside
                 if c[1] < min(cc[1] for cc in counter_cells)]
    assert wall_side
    for cell in wall_side:
        straight = max(abs(cell[0] - origin[0]), abs(cell[1] - origin[1]))
        assert reached[cell][0] > straight, cell
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
