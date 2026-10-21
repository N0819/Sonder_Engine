""""THE RAIN HAS STOPPED" (DESIGN_SOUND_FIELD.md § 17, round 2 lane C,
2026-10-20; § 13.4's registered half).

Real world: rain on a roof is a sound you stop hearing and notice stop.
The engine folded the weather's sound into the field's FLOOR -- which
masks and is never told -- so no mind was ever told by ear that it was
raining, none could be told it stopped, and the narrator's manifest
re-derived `weather_words(scoped, "sound")` every beat with no key, so
steady rain reached the page as news on every beat of a storm. A steady
source in a room it fills evenly (a clock, a generator in a small room)
had no percept either: `sound_shape` speaks only for an uneven room.

The class, a test (or more) each:

  1. the weather's sound is a hearing percept keyed like the soundscape:
     told when it starts, faded between (habituation), its stopping told
     ONCE by what the observer's ledger held -- on every tier;
  2. a newcomer hears the room as it is and is never told a stop it never
     heard; a body that walked out of earshot is told no stop either;
  3. indoors the sound is what reaches the room (`weather_for_room`'s
     audibility): muffled through a wall, and gone when it eases below
     hearing -- told as the sound stopping, honestly;
  4. the wind at the ear is its own sound, and drops once;
  5. the narrator's manifest entry carries the ledger's verdict, so the
     page is not re-told steady rain every beat;
  6. an even room's steady source is a percept of its own, under the
     soundscape's subject: it starts, fades and stops as one;
  7. both packs agree. Telling only: the field's floor is untouched (the
     owner's rain ruling -- rain never masks a line).
"""

from __future__ import annotations

import pytest

from agents import composer, narration, perception
from language_runtime import language_scope
from world import spatial
from world.spatial import NOISE_WORDS, sound_fill, sound_shape
from world.weather import weather_for_room, weather_sound_words, weather_words

from tests.test_field_sentences import ANCHORS, lamp_hall, room, scene


RAIN = {"sky": "overcast", "precipitation": "rain", "precipitation_kind": "liquid",
        "intensity": "moderate", "wind": "still", "temperature": "mild"}
#: The fall's name is the story's own word, spliced as written (names are
#: reproduced, never interpreted): a Japanese story's record says 雨.
RAIN_IN = {"en": RAIN, "ja": dict(RAIN, precipitation="雨")}


def _house(weather=RAIN, *, where="yard", door="closed_door"):
    """A yard under the sky and a study one layer in, behind a `door`
    (a closed door is one muffling layer; an open doorway none); Q stands
    in `where`."""
    rooms = {
        "yard": dict(room("the yard", light="lit", anchors=ANCHORS),
                     exposure="open",
                     adjacent=[{"to": "study", "barrier": door, "dir": "n"}]),
        "study": dict(room("the study", light="lit", anchors=ANCHORS),
                      exposure="enclosed",
                      adjacent=[{"to": "yard", "barrier": door, "dir": "s"}]),
    }
    sc = scene(rooms, {"Q": where}, stations={"Q": {"at": "table"}},
               orientation={"Q": {"facing": "n"}})
    sc["weather"] = dict(weather)
    return sc


def _standing(sc, name, prev_standing=frozenset(), *, prev_scene=None,
              language="en"):
    """This observer's standing percepts, minted as a turn in `language`
    mints them (the sentence a weather percept carries is the active
    pack's, `composer._t`)."""
    rid = spatial.room_of(sc, name)
    p = {"room": rid, "room_name": sc["rooms"][rid]["name"], "room_notes": ""}
    with language_scope(language):
        return perception._composer_standing_percepts(
            sc, p, name, [], {}, {}, prev_standing=prev_standing,
            prev_scene=prev_scene)


def _weather_sound(percepts, tag=composer.WEATHER_SOUND_TAG):
    return [p for p in percepts
            if p.channel == "hearing" and p.kind == "ambient"
            and str(p.dedupe_key).split(":", 1)[0] == tag]


def _keys(percepts):
    return {p.dedupe_key for p in percepts if p.order_key is None}


STOPPED = {"en": "The rain has stopped.", "ja": "雨が止んだ。"}
HEARD = {"en": "The sound of the rain is all around you.",
         "ja": "雨の音があたり一面に満ちている。"}


# --- 1. told, faded, stopped once ------------------------------------------

@pytest.mark.parametrize("language", ["en", "ja"])
def test_the_rain_is_heard_then_fades_then_its_stopping_is_told_once(language):
    sc = _house(RAIN_IN[language])
    first = _standing(sc, "Q", language=language)
    [rain] = _weather_sound(first)
    assert composer.steady_sound(rain)
    view1 = composer.render_view(first, mode="player", language=language)
    assert HEARD[language] in view1.text
    # the next beat, unchanged: out of the view, still filed -- both tiers
    for mode in ("player", "character"):
        view2 = composer.render_view(
            _standing(sc, "Q", view1.standing_keys, language=language),
            mode=mode, prev_standing=view1.standing_keys, language=language)
        assert HEARD[language] not in view2.text
        assert rain.dedupe_key in view2.standing_keys
    # the rain stops: told once, leading the player's beat
    dry = _house(dict(RAIN_IN[language], intensity="none"))
    third = _standing(dry, "Q", view1.standing_keys, prev_scene=sc,
                      language=language)
    [ceased] = [p for p in third if (p.data or {}).get("ceased")]
    assert composer.steady_sound(ceased)
    verdicts = composer.standing_verdicts(third, view1.standing_keys)
    assert verdicts[ceased.dedupe_key] == "ceased"
    assert composer.leads_the_beat(ceased, "ceased", view1.standing_keys)
    for mode in ("player", "character"):
        view3 = composer.render_view(third, mode=mode,
                                     prev_standing=view1.standing_keys,
                                     language=language)
        assert STOPPED[language] in view3.text
        view4 = composer.render_view(
            _standing(dry, "Q", view3.standing_keys, prev_scene=dry,
                      language=language),
            mode=mode, prev_standing=view3.standing_keys, language=language)
        assert STOPPED[language] not in view4.text
    # the rain coming back is news again, against the stop
    back = _standing(sc, "Q", view3.standing_keys, prev_scene=dry,
                     language=language)
    [rain_again] = _weather_sound(back)
    assert composer.standing_verdicts(back, view3.standing_keys)[
        rain_again.dedupe_key] == "changed"


def test_a_change_in_the_rain_is_told_again():
    """Light rain to heavy rain is a new key under one subject: `changed`."""
    sc = _house(dict(RAIN, intensity="light"))
    first = _standing(sc, "Q")
    heavy = _house(dict(RAIN, intensity="heavy"))
    second = _standing(heavy, "Q", _keys(first), prev_scene=sc)
    [rain] = _weather_sound(second)
    assert composer.standing_verdicts(second, _keys(first))[rain.dedupe_key] == "changed"
    assert "heavy rain" in composer.render_view([rain], mode="character").text


# --- 2. a newcomer, and a body that walked out of earshot --------------------

def test_a_newcomer_hears_the_rain_as_it_is_and_is_never_told_a_stop():
    sc = _house()
    elsewhere = {composer.standing_key("env", ("cellar",), ("x",))}
    percepts = _standing(sc, "Q", elsewhere)
    [rain] = _weather_sound(percepts)
    assert composer.standing_verdicts(percepts, elsewhere)[rain.dedupe_key] == "first"
    assert not composer.leads_the_beat(rain, "first", elsewhere)   # background
    view = composer.render_view(percepts, mode="player", prev_standing=elsewhere)
    assert HEARD["en"] in view.text
    # a stop they never heard: no percept at all, and nothing rendered
    dry = _house(dict(RAIN, intensity="none"))
    stranger = {composer.standing_key(composer.WEATHER_SOUND_TAG,
                                      ("some other yard",), ("rain",))}
    percepts = _standing(dry, "Q", stranger, prev_scene=sc)
    assert not any((p.data or {}).get("ceased") for p in percepts)


def test_walking_indoors_is_not_the_rain_stopping():
    """The subject is the room: Q hears the yard's rain, walks into the
    study while it goes on -- the study's muffled rain is `first`, and no
    stop is told; back in the yard it is the yard's sound again."""
    sc = _house()
    yard = _keys(_standing(sc, "Q"))
    inside = _house(where="study")
    percepts = _standing(inside, "Q", yard, prev_scene=sc)
    assert not any((p.data or {}).get("ceased") for p in percepts)
    [rain] = _weather_sound(percepts)
    assert composer.standing_verdicts(percepts, yard)[rain.dedupe_key] == "first"


# --- 3. indoors: what reaches the room ----------------------------------------

@pytest.mark.parametrize("language,muffled,gone", [
    ("en", "Through the walls, you can hear the rain, muffled.",
     "The sound of the rain from beyond the walls has stopped."),
    ("ja", "壁越しに、くぐもった雨の音が聞こえる。", "壁の向こうの雨の音が止んだ。"),
])
def test_indoors_the_rain_is_what_reaches_the_room(language, muffled, gone):
    sc = _house(RAIN_IN[language], where="study")
    reach = weather_for_room(sc, "study", "Q")
    assert reach["audible"] and reach["muffling"] == "muffled"
    first = _standing(sc, "Q", language=language)
    [rain] = _weather_sound(first)
    assert composer.render_view([rain], mode="character",
                                language=language).text == muffled
    # light rain does not reach one layer in: the sound is gone, told as
    # the sound stopping -- the honest sentence through a wall
    light = _house(dict(RAIN_IN[language], intensity="light"), where="study")
    assert not weather_for_room(light, "study", "Q")["audible"]
    second = _standing(light, "Q", _keys(first), prev_scene=sc,
                       language=language)
    [ceased] = [p for p in second if (p.data or {}).get("ceased")]
    assert composer.render_view(second, mode="player", prev_standing=_keys(first),
                                language=language).text.count(gone) == 1
    # the sound bed and the view read ONE audibility
    assert weather_words(reach, "sound") and not weather_words(
        weather_for_room(light, "study", "Q"), "sound")


def test_the_stop_names_what_fell_from_the_record_when_no_before_is_at_hand():
    """The act stage has no previous scene: a sky keeps its fall's name
    through a dry spell, so the record names it; a record that never named
    one gets the class."""
    rid = "yard"
    held = {composer.standing_key(composer.WEATHER_SOUND_TAG, (rid,), ("rain",))}
    dry = weather_for_room(_house(dict(RAIN, intensity="none")), rid, "Q")
    [ceased] = composer.weather_sound_percepts(dry, rid, prev_standing=held)
    assert ceased.data["desc"] == "The rain has stopped."
    nameless = dict(dry, precipitation="none")
    [ceased] = composer.weather_sound_percepts(nameless, rid, prev_standing=held)
    assert ceased.data["desc"] == "The sound of the weather has stopped."
    [ceased] = composer.weather_sound_percepts(
        nameless, rid, prev_standing=held, before=dict(dry, audible=True,
                                                       precipitation="sleet"))
    assert ceased.data["desc"] == "The sleet has stopped."


# --- 4. the wind --------------------------------------------------------------

@pytest.mark.parametrize("language,loud,dropped", [
    ("en", "The gale is loud in your ears.", "The wind has dropped."),
    ("ja", "風が耳元で鳴り続けている。", "風が止んだ。"),
])
def test_the_wind_at_the_ear_is_its_own_sound_and_drops_once(language, loud, dropped):
    gale = _house(dict(RAIN, intensity="none", wind="gale"))
    first = _standing(gale, "Q", language=language)
    [wind] = _weather_sound(first, composer.WIND_SOUND_TAG)
    assert composer.steady_sound(wind)
    assert composer.render_view([wind], mode="character",
                                language=language).text == loud
    assert not _weather_sound(first)             # no rain: no rain sound
    calm = _house(dict(RAIN, intensity="none", wind="still"))
    second = _standing(calm, "Q", _keys(first), prev_scene=gale,
                       language=language)
    view = composer.render_view(second, mode="player", prev_standing=_keys(first),
                                language=language)
    assert view.text.count(dropped) == 1
    third = _standing(calm, "Q", view.standing_keys, prev_scene=calm,
                      language=language)
    assert dropped not in composer.render_view(
        third, mode="player", prev_standing=view.standing_keys,
        language=language).text


# --- 5. the narrator's manifest carries the verdict ---------------------------

def test_the_narrators_manifest_entry_carries_the_rains_verdict():
    sc = _house()
    first = _standing(sc, "Q")
    [rain] = _weather_sound(first)
    scoped = weather_for_room(sc, "yard")
    words = weather_words(scoped, "sound")
    assert words                                   # the sound bed's words
    grouped = weather_sound_words(scoped)
    assert grouped["precipitation"] == words and not grouped["wind"]
    view = composer.render_view(first, mode="player", prev_standing=_keys(first))
    assert view.verdicts[rain.dedupe_key] == "unchanged"
    manifest = narration._sensory_channels_manifest(
        sc, "Q", view.text, [], set(), {}, "yard",
        standing_verdicts=view.verdicts)
    entries = manifest["hearing"]["standing"]
    assert [e["clause"] for e in entries] == words
    assert all(e.get("verdict") == "unchanged" for e in entries)
    # no ledger answer reads as "not computed", never as new
    manifest = narration._sensory_channels_manifest(
        sc, "Q", view.text, [], set(), {}, "yard", standing_verdicts={})
    assert all("verdict" not in e for e in manifest["hearing"]["standing"])
    # the wind's word rides the wind's key
    gale = _house(dict(RAIN, wind="gale"))
    percepts = _standing(gale, "Q")
    view = composer.render_view(percepts, mode="player", prev_standing=_keys(percepts))
    manifest = narration._sensory_channels_manifest(
        gale, "Q", view.text, [], set(), {}, "yard",
        standing_verdicts=view.verdicts)
    by_clause = {e["clause"]: e.get("verdict") for e in manifest["hearing"]["standing"]}
    assert by_clause["gale"] == "unchanged"


# --- 6. an even room's steady source -------------------------------------------

def _study_with_a_clock(*, running=True, level="faint"):
    sc = scene({"r": dict(room("the study", light="lit", size="small",
                               anchors=ANCHORS))},
               {"Q": "r", "clock": "r"},
               entities={"clock": {"name": "the clock", "kind": "object",
                                   "sound_source": level,
                                   **({} if running else
                                      {"state": {"running": False}})}},
               stations={"clock": {"at": "shelf"}, "Q": {"at": "table"}},
               orientation={"Q": {"facing": "n"}})
    return sc


EVEN = {"en": ("The noise from the clock can be heard all through the room, "
               "low enough to talk over."),
        "ja": "時計の音が部屋じゅうに低く続いている。その上から話はできる。"}
CEASED = {"en": "The noise has stopped.", "ja": "騒音が止んだ。"}


@pytest.mark.parametrize("language", ["en", "ja"])
def test_an_even_rooms_steady_source_is_a_sound_of_its_own(language):
    """A clock in a small study: every cell `quiet`, so `sound_shape` has
    nothing to say (rule (a) stands); `sound_fill` names the clock under
    the soundscape's own subject, so it starts, fades and stops as one."""
    sc = _study_with_a_clock()
    if language == "ja":
        sc["entities"]["clock"]["name"] = "時計"
    assert sound_shape(sc, "Q") is None
    fill = sound_fill(sc, "Q")
    assert fill and fill["even"] == NOISE_WORDS[0] and fill["sources"]
    first = _standing(sc, "Q", language=language)
    [clock] = [p for p in first if (p.data or {}).get("soundscape")]
    assert composer.steady_sound(clock)
    assert composer.render_view([clock], mode="character",
                                language=language).text == EVEN[language]
    assert composer.field_shape_sentence("sound", fill, language=language) \
        == EVEN[language]
    # faded on the next beat, on both tiers; an explicit look asks it back
    for mode in ("player", "character"):
        view2 = composer.render_view(_standing(sc, "Q", _keys(first)), mode=mode,
                                     prev_standing=_keys(first), language=language)
        assert EVEN[language] not in view2.text
    look = composer.render_view(_standing(sc, "Q", _keys(first)), mode="character",
                                prev_standing=_keys(first), full_render=True,
                                language=language)
    assert EVEN[language] in look.text
    # the clock stops: told once
    stopped = _study_with_a_clock(running=False)
    if language == "ja":
        stopped["entities"]["clock"]["name"] = "時計"
    third = _standing(stopped, "Q", _keys(first))
    [ceased] = [p for p in third if (p.data or {}).get("ceased")]
    assert composer._subject_prefix(ceased.dedupe_key) == \
        composer._subject_prefix(clock.dedupe_key)
    view3 = composer.render_view(third, mode="player", prev_standing=_keys(first),
                                 language=language)
    assert view3.text.count(CEASED[language]) == 1
    view4 = composer.render_view(_standing(stopped, "Q", view3.standing_keys),
                                 mode="player", prev_standing=view3.standing_keys,
                                 language=language)
    assert CEASED[language] not in view4.text


def test_an_even_room_with_nothing_running_and_an_uneven_room_are_untouched():
    """The floor alone is no sound; an uneven room is `sound_shape`'s."""
    assert sound_fill(lamp_hall(), "Q") is None
    assert sound_fill(_study_with_a_clock(running=False), "Q") is None
    assert sound_shape(lamp_hall(generator=True), "Q") is not None
    assert sound_fill(lamp_hall(generator=True), "Q") is None


def test_the_rain_never_masks_a_line():
    """Telling only: the hearing rule's answer for a line in the rain is the
    same as in the dry."""
    from world.spatial import hear_level, spatial_rel_between
    wet, dry = _house(), _house(dict(RAIN, intensity="none"))
    for sc in (wet, dry):
        sc["positions"]["P"] = "yard"
        sc["stations"]["P"] = {"at": "hearth"}
    assert hear_level(spatial_rel_between(wet, "Q", "P"), "normal") == \
        hear_level(spatial_rel_between(dry, "Q", "P"), "normal") == "full"
