"""A STEADY SOUND'S START AND STOP ARE REMEMBERED (DESIGN_SOUND_FIELD.md
§ 17, round 2 lane C, 2026-10-20; § 13.7 item 12).

Habituation (wave B1) took a steady sound out of the view between its
start and its stop. It was also in no memory: the episode writer filed a
beat's own sounds (`_EPISODE_SOUND_TAGS`: `ambient`, `distant_sound`) and
never the room's soundscape, a crowd's hum or -- since round 2 -- the
weather's sound, so "the generator stopped some time in the night" was
recallable by nobody. The owner's standing ruling: memory is the
priority (2026-09-26).

The class, a test (or more) each:

  1. a steady sound is filed on the beat it starts and the beat it stops
     (and on a beat it changes), and on no other -- a sound heard every
     beat is filed once, while the view habituates;
  2. a stop the mind never heard is no memory (the view's own verdicts);
  3. the weather's sound is filed the same way;
  4. both packs; and the memory line carries the sound's character -- the
     sound sentence itself, named sources and level -- in the first
     person. The clock is the row's: `commit_memory` stamps every memory
     with `encoded_at_seconds` and the turn, so "some time in the night"
     is the recall layer's reading of the row, not a word in the line.
"""

from __future__ import annotations

import pytest

from agents import composer
from language_runtime import language_scope
from world import spatial

from tests.test_field_sentences import lamp_hall
from tests.test_the_rain_has_stopped import RAIN_IN, _house


def _standing(sc, name, prev_standing=frozenset(), *, prev_scene=None,
              language="en"):
    import agents.perception as perception
    rid = spatial.room_of(sc, name)
    p = {"room": rid, "room_name": sc["rooms"][rid]["name"], "room_notes": ""}
    with language_scope(language):
        return perception._composer_standing_percepts(
            sc, p, name, [], {}, {}, prev_standing=prev_standing,
            prev_scene=prev_scene)


def _keys(percepts):
    return {p.dedupe_key for p in percepts if p.order_key is None}


def _episode(percepts, prev, language):
    content, gist, _entities = composer.render_episode(
        percepts, prev_standing=prev, language=language)
    return content, gist


STOPPED = {"en": "The noise has stopped.", "ja": "騒音が止んだ。"}


# --- 1. start once, stop once ------------------------------------------------

@pytest.mark.parametrize("language", ["en", "ja"])
def test_a_steady_sound_is_filed_when_it_starts_and_when_it_stops(language):
    sc = lamp_hall(generator=True)
    first = _standing(sc, "Q", language=language)
    [sound] = [p for p in first if (p.data or {}).get("soundscape")]
    said = composer.render_view([sound], mode="character", language=language).text
    with language_scope(language):
        mine = composer._first_person(said)
    content, _gist = _episode(first, frozenset(), language)
    # the start: the sound's own sentence, in the first person
    assert mine in content
    assert sc["entities"]["gen"]["name"] in content
    # the next beat, unchanged: nothing new to file, and the view has faded
    content2, _ = _episode(_standing(sc, "Q", _keys(first), language=language),
                           _keys(first), language)
    assert said not in content2 and mine not in content2
    # the stop: filed once, then never again
    sc["entities"]["gen"]["state"] = {"running": False}
    third = _standing(sc, "Q", _keys(first), language=language)
    content3, gist3 = _episode(third, _keys(first), language)
    assert STOPPED[language] in content3
    content4, _ = _episode(_standing(sc, "Q", _keys(third), language=language),
                           _keys(third), language)
    assert STOPPED[language] not in content4


def test_a_change_in_the_sound_is_filed_as_a_new_line():
    sc = lamp_hall(generator=True)
    first = _standing(sc, "Q")
    sc["stations"]["gen"] = {"at": "table"}          # moved across the hall
    moved = _standing(sc, "Q", _keys(first))
    [sound] = [p for p in moved if (p.data or {}).get("soundscape")]
    content, _ = _episode(moved, _keys(first), "en")
    assert composer._first_person(
        composer.render_view([sound], mode="character").text) in content


# --- 2. a stop the mind never heard ----------------------------------------

@pytest.mark.parametrize("language", ["en", "ja"])
def test_a_stop_the_mind_never_heard_is_no_memory(language):
    sc = lamp_hall(generator=True)
    key = next(p.dedupe_key for p in _standing(sc, "Q")
               if (p.data or {}).get("soundscape"))
    sc["entities"]["gen"]["state"] = {"running": False}
    percepts = _standing(sc, "Q", {key})
    assert any((p.data or {}).get("ceased") for p in percepts)
    stranger = {composer.standing_key("soundscape", ("elsewhere",), ("hum",))}
    content, _ = _episode(percepts, stranger, language)
    assert STOPPED[language] not in content
    # ...and with its own ledger, it is
    content, _ = _episode(percepts, {key}, language)
    assert STOPPED[language] in content


# --- 3. the weather's sound --------------------------------------------------

@pytest.mark.parametrize("language,heard,stopped", [
    ("en", "The sound of the rain is all around me.", "The rain has stopped."),
    ("ja", "雨の音があたり一面に満ちている。", "雨が止んだ。"),
])
def test_the_rain_starting_and_stopping_are_filed(language, heard, stopped):
    sc = _house(RAIN_IN[language])
    first = _standing(sc, "Q", language=language)
    content, _ = _episode(first, frozenset(), language)
    assert heard in content
    content2, _ = _episode(_standing(sc, "Q", _keys(first), language=language),
                           _keys(first), language)
    assert heard not in content2
    dry = _house(dict(RAIN_IN[language], intensity="none"))
    third = _standing(dry, "Q", _keys(first), prev_scene=sc, language=language)
    content3, _ = _episode(third, _keys(first), language)
    assert stopped in content3
    content4, _ = _episode(_standing(dry, "Q", _keys(third), prev_scene=dry,
                                     language=language),
                           _keys(third), language)
    assert stopped not in content4


# --- 4. what the line carries --------------------------------------------------

def test_the_memory_line_carries_the_sounds_character():
    """The sound sentence IS the line: the named source and the room's level
    (an even room's one word, an uneven room's groups and where this body
    stood), first person, with nothing numeric."""
    sc = lamp_hall(generator=True)
    content, gist = _episode(_standing(sc, "Q"), frozenset(), "en")
    assert "the generator" in content
    assert "din" in content or "drowns" in content or "faint" in content
    assert not any(ch.isdigit() for ch in content)
    assert "you" not in content.split()                # first person
    assert composer._EPISODE_SOUND_TAGS[2:] == composer.HABITUATING_SOUND_TAGS
