"""D3 (review 2026-09-07): silence where there was sound.

A room the sound field grades unevenly composes a soundscape percept; the
beat its one source stops, the field goes EVEN and the percept is simply not
built. Nothing anywhere then says the humming stopped: the observer's ledger
holds a key nothing renews, and a key that vanished cannot be compared
against anything. Measured in the descent run -- the PLAYER wrote "nothing
hummed" themselves, because the page never did.

The real gap is exactly the single-source case. A room with several sources
losing one moves the shape, which moves the content half of
`composer.standing_key`, which is already `changed`; only the room that goes
even has no percept left to carry the news.

Firewall: a silence is news to an ear that had the noise and to no other.
`perception._was_hearing_this_room` mints nothing unless this observer's OWN
previous ledger holds this room's sound, and `composer.unheard_ceasing`
drops the percept a second time wherever no verdict says `ceased` -- the
character tier, which diffs against no ledger, included.
"""

from __future__ import annotations

import pytest

from agents import composer, perception
from world import spatial
from world.spatial import NOISE_WORDS, room_noise_word, sound_shape

from tests.test_field_sentences import ANCHORS, lamp_hall, room, scene, standing


CEASED_EN = "The noise has stopped."
CEASED_JA = "騒音が止んだ。"


def _standing(sc, name, prev_standing=frozenset()):
    """This observer's standing percepts, with their own previous ledger."""
    room = spatial.room_of(sc, name)
    p = {"room": room, "room_name": sc["rooms"][room]["name"],
         "room_notes": ""}
    return perception._composer_standing_percepts(
        sc, p, name, [], {}, {}, prev_standing=prev_standing)


def _soundscape_key(sc, name):
    return next(p.dedupe_key for p in standing(sc, name)
                if p.kind == "ambient" and p.data.get("soundscape"))


# ---------------------------------------------------------------------------
# The two beats
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("language,sentence",
                         [("en", CEASED_EN), ("ja", CEASED_JA)])
def test_the_generator_stopping_reaches_the_page(language, sentence):
    """Beat one: an uneven room, a soundscape sentence, a filed key. Beat
    two: the generator is off, the room is even and quiet, and the view says
    so -- in the BEAT half, because it is what happened."""
    sc = lamp_hall(generator=True)
    first = standing(sc, "Q")
    key = next(p.dedupe_key for p in first
               if p.kind == "ambient" and p.data.get("soundscape"))

    sc["entities"]["gen"]["state"] = {"running": False}
    assert sound_shape(sc, "Q") is None          # the room went even
    assert room_noise_word(sc, "r") == NOISE_WORDS[0]

    percepts = _standing(sc, "Q", prev_standing={key})
    ceased = [p for p in percepts if (p.data or {}).get("ceased")]
    assert len(ceased) == 1
    assert ceased[0].channel == "hearing" and ceased[0].order_key is None

    verdicts = composer.standing_verdicts(percepts, {key})
    assert verdicts[ceased[0].dedupe_key] == "ceased"
    assert composer.leads_the_beat(ceased[0], "ceased", {key})

    rendered = composer.render_view(percepts, mode="player",
                                    prev_standing={key}, language=language)
    assert sentence in rendered.text


def test_the_silence_is_said_once_and_the_sound_returning_is_news_again():
    """The ceased percept takes the SAME subject as the sound it ends, so
    the room's sound ledger stays one ledger: a silence that holds is
    `unchanged` and costs no second sentence, and the generator coming back
    is `changed` against it."""
    sc = lamp_hall(generator=True)
    sound_key = _soundscape_key(sc, "Q")

    sc["entities"]["gen"]["state"] = {"running": False}
    percepts = _standing(sc, "Q", prev_standing={sound_key})
    ceased_key = next(p.dedupe_key for p in percepts
                      if (p.data or {}).get("ceased"))
    assert composer._subject_prefix(ceased_key) == \
        composer._subject_prefix(sound_key)

    # Beat three: still quiet. The key is re-minted, the verdict is
    # `unchanged`, and nothing is said a second time.
    again = _standing(sc, "Q", prev_standing={ceased_key})
    verdicts = composer.standing_verdicts(again, {ceased_key})
    assert verdicts[ceased_key] == "unchanged"
    text = composer.render_view(again, mode="player",
                                prev_standing={ceased_key}).text
    assert CEASED_EN not in text

    # Beat four: the generator runs again. Its shape is a subject this
    # observer holds under different content -- the beat's news.
    sc["entities"]["gen"]["state"] = {"running": True}
    back = _standing(sc, "Q", prev_standing={ceased_key})
    verdicts = composer.standing_verdicts(back, {ceased_key})
    assert verdicts[_soundscape_key(sc, "Q")] == "changed"


# ---------------------------------------------------------------------------
# The subtractions
# ---------------------------------------------------------------------------

def test_an_ordinary_quiet_beat_mints_nothing():
    """A room that was never sounding does not get a percept saying it
    stopped -- with no ledger and with a ledger holding no sound alike."""
    sc = lamp_hall()
    assert sound_shape(sc, "Q") is None
    assert all(p.channel != "hearing" for p in standing(sc, "Q"))
    other = composer.standing_key("soundscape", ("elsewhere",), ("hum",))
    assert all(not (p.data or {}).get("ceased")
               for p in _standing(sc, "Q", prev_standing={other}))


def _small_hall(level):
    """A small hall with one machine in it. `loud` grades it unevenly;
    `deafening` drowns every cell, which is EVEN -- and not a silence."""
    return scene({"r": room("the Hall", size="small", anchors=ANCHORS)},
                 {"Q": "r", "gen": "r"},
                 entities={"gen": {"name": "the generator", "kind": "machine",
                                   "sound_source": level}},
                 stations={"gen": {"at": "table"}, "Q": {"at": "hearth"}},
                 orientation={"Q": {"facing": "n"}})


def test_a_room_that_went_even_by_filling_up_is_not_a_silence():
    """A room goes even two ways, and `sound_shape` answers None for both.
    The generator drowning every cell is not the generator stopping, and
    the word the room's own cells agree on is what separates them."""
    loud = _small_hall("loud")
    assert sound_shape(loud, "Q") is not None
    key = _soundscape_key(loud, "Q")

    sc = _small_hall("deafening")
    assert sound_shape(sc, "Q") is None              # even
    assert room_noise_word(sc, "r") != NOISE_WORDS[0]  # and not quiet
    assert all(not (p.data or {}).get("ceased")
               for p in _standing(sc, "Q", prev_standing={key}))


def test_a_silence_is_only_news_to_an_ear_that_had_the_noise():
    """The firewall half. A percept that reaches a renderer against a ledger
    holding no sound for this room renders nothing at all, and the character
    tier -- which computes no verdicts -- renders nothing either."""
    sc = lamp_hall(generator=True)
    key = _soundscape_key(sc, "Q")
    sc["entities"]["gen"]["state"] = {"running": False}
    percepts = _standing(sc, "Q", prev_standing={key})
    ceased = next(p for p in percepts if (p.data or {}).get("ceased"))

    stranger = composer.standing_key("soundscape", ("elsewhere",), ("hum",))
    assert composer.standing_verdicts(percepts, {stranger})[
        ceased.dedupe_key] == "first"
    assert composer.unheard_ceasing(ceased, "first")
    assert not composer.unheard_ceasing(ceased, "ceased")
    for language in ("en", "ja"):
        text = composer.render_view(percepts, mode="player",
                                    prev_standing={stranger},
                                    language=language).text
        assert CEASED_EN not in text and CEASED_JA not in text
        # Character mode diffs against nothing, so it says nothing here.
        text = composer.render_view(percepts, mode="character",
                                    full_render=True, language=language).text
        assert CEASED_EN not in text and CEASED_JA not in text


def test_a_body_that_walked_away_did_not_hear_the_sound_stop():
    """"In the same room" is exact rather than approximate: the ledger key
    carries the room as its subject, so an observer who moved is holding
    another room's sound and mints nothing for the one they are in."""
    sc = lamp_hall(generator=True)
    elsewhere = composer.standing_key(
        "soundscape", ("some other room",), ("hum",))
    sc["entities"]["gen"]["state"] = {"running": False}
    assert all(not (p.data or {}).get("ceased")
               for p in _standing(sc, "Q", prev_standing={elsewhere}))


def _dark_hall(*, measured):
    """The generator running loud at one wall of a big unlit hall. With
    `measured`, Q stands at a station; without, Q is in the room and nowhere
    in it -- and a dark room shows no anchor to grade, so `sound_shape` has
    neither of the two things it can speak from."""
    entities = {"gen": {"name": "the generator", "kind": "machine",
                        "sound_source": "loud"}}
    stations = {"gen": {"at": "shelf"}}
    if measured:
        stations["Q"] = {"at": "hearth"}
    return scene({"r": room("the Hall", size="huge", anchors=ANCHORS)},
                 {"Q": "r", "gen": "r"}, entities=entities,
                 stations=stations, orientation={"Q": {"facing": "n"}})


def test_a_running_generator_is_never_heard_to_stop():
    """A shape that is None is NOT a silence. `sound_shape` answers None for
    three reasons and only the first is the room going even: rule (a) even;
    no cells at all; and nothing to grade -- no visible anchor AND no
    measured cell (`not ordered and self_word is None`). The third is an
    uneven room with the source still running.

    Beat one files the room's sound from a measured cell. Beat two takes the
    station away and leaves the generator untouched: nothing about the ROOM
    changed, so nothing about it may be said. The trigger asks the room's own
    cells and not the observer's, which is why this holds for a body the
    scene cannot place as well as for one it can."""
    sc = _dark_hall(measured=True)
    key = _soundscape_key(sc, "Q")

    sc = _dark_hall(measured=False)
    assert sound_shape(sc, "Q") is None          # no anchor graded, no cell
    assert room_noise_word(sc, "r") != NOISE_WORDS[0]   # and still uneven
    percepts = _standing(sc, "Q", prev_standing={key})
    assert all(not (p.data or {}).get("ceased") for p in percepts)
    for language in ("en", "ja"):
        text = composer.render_view(percepts, mode="player",
                                    prev_standing={key},
                                    language=language).text
        assert CEASED_EN not in text and CEASED_JA not in text


def test_an_unmeasured_body_still_hears_the_generator_stop():
    """The other half of the same rework: evenness is the ROOM's property,
    so a body the scene cannot place hears the silence too. Same two beats,
    with the generator switched off instead of left running."""
    sc = _dark_hall(measured=True)
    key = _soundscape_key(sc, "Q")

    sc = _dark_hall(measured=False)
    sc["entities"]["gen"]["state"] = {"running": False}
    assert room_noise_word(sc, "r") == NOISE_WORDS[0]
    percepts = _standing(sc, "Q", prev_standing={key})
    assert sum(bool((p.data or {}).get("ceased")) for p in percepts) == 1
    assert CEASED_EN in composer.render_view(
        percepts, mode="player", prev_standing={key}).text


@pytest.mark.parametrize("size", ["small", "large"])
def test_a_one_beat_sound_is_never_heard_to_stop(size):
    """Only a sound that was STANDING can be heard to stop (D3 rework).

    From the live record rather than a synthetic case: chat 117 turn 115
    filed a one-beat `{"kind": "sound", "room": ..., "level": "audible",
    "source": "deck slab"}` sensory event, which mints a soundscape key of
    its own; the next beat holds nothing at all, and the trigger read that
    as the room going quiet. It is not -- the crash was the beat's, not the
    room's, and `sound_shape` already refuses to name a beat's own sounds as
    the room's shape. Measured at every room size for `faint` and `audible`,
    which is why this is parametrized.
    """
    sc = scene({"r": room("the Hall", size=size, anchors=ANCHORS)},
               {"Q": "r"}, stations={"Q": {"at": "hearth"}},
               orientation={"Q": {"facing": "n"}})
    event = {"kind": "sound", "room": "r", "level": "audible",
             "source": "deck slab"}
    heard = spatial.sound_field(sc, "Q", room="r", events=[event])
    assert not spatial.room_holds_a_standing_source(sc, "r")

    # Beat one: the crash gives this observer a soundscape key.
    p = {"room": "r", "room_name": "the Hall", "room_notes": ""}
    first = perception._composer_standing_percepts(
        sc, p, "Q", [], {}, {}, sound=heard, prev_standing=frozenset())
    keys = {x.dedupe_key for x in first
            if x.kind == "ambient" and (x.data or {}).get("soundscape")}

    # Beat two: nothing at all. The room never held a standing sound, so
    # nothing may be heard to stop.
    quiet = spatial.sound_field(sc, "Q", room="r", events=[])
    second = perception._composer_standing_percepts(
        sc, p, "Q", [], {}, {}, sound=quiet, prev_standing=keys)
    assert all(not (x.data or {}).get("ceased") for x in second), size


def test_the_verdict_is_in_the_published_vocabulary():
    assert "ceased" in composer.STANDING_VERDICTS
