"""A beat's one-off sounds are moments, not a floor.

The owner (2026-09-25): "sounds should be allowed to be transient mid beat.
there are types of sound after all." The engine has two: a STANDING sound
(`sound_source` with `state.running`) that goes on until something stops it,
and a sound EVENT (`sensory_events`) that happens at some moment in the beat.
Masking counted both alike, so an instant sat on every line of its beat at
full power. Measured on the owner's chat 155 turn 34: a listener's own single
`audible` moan, placed at her own cell, read 58 dB in her ears and took a
line murmured by a face inches from hers to nothing; with the moan gone, a
faint creak of the table she lay on still held it to a fragment.

Now a line -- or any sound -- is heard over what sounds THROUGHOUT it, and a
one-off sound is heard as itself.
"""

from __future__ import annotations

from world.spatial import sound_field

from tests.test_field_sentences import ANCHORS, room, scene

VOLUMES = ("whisper", "mutter", "normal", "loud")


def _hall(machine=None):
    """A small hall: P speaks from the table, Q listens at the hearth, R and
    (with `machine`) a running generator stand at the shelf, a pace from Q."""
    positions = {"P": "r", "Q": "r", "R": "r"}
    stations = {"P": {"at": "table"}, "Q": {"at": "hearth"}, "R": {"at": "shelf"}}
    entities = {}
    if machine:
        entities["gen"] = {"name": "the generator", "kind": "machine",
                           "sound_source": machine}
        positions["gen"] = "r"
        stations["gen"] = {"at": "shelf"}
    return scene({"r": room("the Hall", size="small", anchors=ANCHORS)},
                 positions, entities=entities, stations=stations,
                 orientation={"P": {"facing": "s"}, "Q": {"facing": "n"},
                              "R": {"facing": "w"}})


def _cry(source, level="loud"):
    return {"kind": "sound", "room": "r", "source": source, "level": level,
            "detail": "a cry"}


def _grades(sc, events):
    field = sound_field(sc, "Q", room="r", events=events)
    return {vol: field.speech_level("P", vol, "Q") for vol in VOLUMES}


def test_a_one_off_sound_does_not_drown_the_lines_of_its_beat():
    """Her own cry at her own cell, and another body's a pace from her."""
    quiet = _grades(_hall(), [])
    assert quiet["mutter"] == "full"
    assert _grades(_hall(), [_cry("Q")]) == quiet
    assert _grades(_hall(), [_cry("R")]) == quiet


def test_what_sounds_throughout_the_beat_still_masks():
    """The other type of sound is untouched: a running machine at the same
    spot takes a mutter to nothing and a normal voice below full. (How far
    a raised voice carries over it is the `loud` rung's calibration, which
    this test does not pin.)"""
    loud = _grades(_hall("loud"), [])
    assert loud["mutter"] == "none"
    assert loud["normal"] != "full"


def test_a_one_off_sound_is_still_heard_as_itself():
    """Moments do not mask each other -- a faint cry beside a loud one is
    heard -- and a standing noise still masks a moment."""
    field = sound_field(_hall(), "Q", room="r",
                        events=[_cry("R"), _cry("P", "faint")])
    assert field.level_of("Q", "event:0") == "full"
    assert field.level_of("Q", "event:1") == "full"
    over_machine = sound_field(_hall("loud"), "Q", room="r",
                               events=[_cry("P", "faint")])
    assert over_machine.level_of("Q", "event:0") == "none"


def test_a_speaker_raises_their_voice_over_standing_noise_only():
    """The Lombard term reads the same floor: a voice is raised over a
    machine that keeps going, not over a cry that has already passed."""
    quiet = sound_field(_hall(), "P", room="r", events=[])
    cry = sound_field(_hall(), "P", room="r", events=[_cry("R")])
    machine = sound_field(_hall("loud"), "P", room="r", events=[])
    base = quiet.speaker_noise("P", speaker_room="r")
    assert cry.speaker_noise("P", speaker_room="r") == base
    assert machine.speaker_noise("P", speaker_room="r") > base
