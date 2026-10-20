"""GETTING USED TO A SOUND, AND NOTICING IT STOP (DESIGN_SOUND_FIELD.md
§ 13, wave B1, 2026-10-20).

Real world: a steady sound fades from attention -- habituation -- and its
stopping or changing is salient: "the rain has stopped", "the clock has
stopped". The engine had half of this for the player alone: the player's
delta view drops a standing percept it already holds. The character tier
re-told every steady sound every beat -- a generator a mind had stood
beside for an hour was announced to it hourly -- and was never told one
stop, because it computed no verdict to tell it by.

The class, a test (or more) each:

  1. a steady sound is told when it starts, and when it changes; between,
     it fades from the view -- on the character tier too;
  2. its stopping is told ONCE to whoever was hearing it, character or
     player, and never to an ear that did not have it;
  3. a sound that STARTS where the observer already stood is the beat's
     news; a newcomer hears the room as it is (background, not hidden);
  4. an explicit look asks for the room back; both packs agree.
"""

from __future__ import annotations

import pytest

from agents import composer, perception
from world import spatial

from tests.test_field_sentences import lamp_hall


CEASED = {"en": "The noise has stopped.", "ja": "騒音が止んだ。"}


def _standing(sc, name, prev_standing=frozenset()):
    room = spatial.room_of(sc, name)
    p = {"room": room, "room_name": sc["rooms"][room]["name"],
         "room_notes": ""}
    return perception._composer_standing_percepts(
        sc, p, name, [], {}, {}, prev_standing=prev_standing)


def _sound(percepts):
    """The room's steady sound, as perception mints it (`soundscape_percept`)."""
    return [p for p in percepts
            if p.kind == "ambient" and (p.data or {}).get("soundscape")]


def _beat(sc, name, prev, mode="character", language="en", full=False):
    percepts = _standing(sc, name, prev)
    rendered = composer.render_view(percepts, mode=mode, prev_standing=prev,
                                    full_render=full, language=language)
    return percepts, rendered


@pytest.mark.parametrize("language", ["en", "ja"])
def test_a_mind_stops_being_told_a_sound_it_keeps_hearing(language):
    sc = lamp_hall(generator=True)
    first, view1 = _beat(sc, "Q", frozenset(), language=language)
    key = _sound(first)[0].dedupe_key
    said = composer.render_view(_sound(first), mode="character",
                                language=language).text
    assert said and said in view1.text          # told the first beat
    # The next beat, the same sound, unchanged: out of the view, still filed,
    # and the character ledger files no verdicts, as before.
    _p, view2 = _beat(sc, "Q", view1.standing_keys, language=language)
    assert said not in view2.text
    assert key in view2.standing_keys
    assert view2.verdicts == {}
    # An explicit look asks for the room back.
    _p, look = _beat(sc, "Q", view1.standing_keys, language=language,
                     full=True)
    assert said in look.text
    # A sound that CHANGES is told again: the generator moved across the hall.
    sc["stations"]["gen"] = {"at": "table"}
    moved, view3 = _beat(sc, "Q", view2.standing_keys, language=language)
    assert _sound(moved)[0].dedupe_key not in view2.standing_keys
    changed = composer.render_view(_sound(moved), mode="character",
                                   language=language).text
    assert changed and changed in view3.text


@pytest.mark.parametrize("language", ["en", "ja"])
def test_a_mind_that_was_hearing_it_is_told_it_stopped_once(language):
    """THE CHARACTER TIER HEARS A SOUND STOP. Its ledger held the room's
    sound; the generator goes off; "The noise has stopped." -- once. An ear
    whose ledger never had the sound is told nothing."""
    sc = lamp_hall(generator=True)
    _p, view1 = _beat(sc, "Q", frozenset(), language=language)
    sc["entities"]["gen"]["state"] = {"running": False}
    _p, view2 = _beat(sc, "Q", view1.standing_keys, language=language)
    assert CEASED[language] in view2.text
    _p, view3 = _beat(sc, "Q", view2.standing_keys, language=language)
    assert CEASED[language] not in view3.text
    stranger = composer.standing_key("soundscape", ("elsewhere",), ("hum",))
    _p, view = _beat(sc, "Q", frozenset({stranger}), language=language)
    assert CEASED[language] not in view.text


def test_a_sound_starting_where_you_stand_is_the_beats_news():
    """The player stood in the hall last beat (their ledger holds the hall's
    room description); the generator starts: it leads. A player who walks
    in to find it running hears the room as it is -- told, as background."""
    sc = lamp_hall(generator=False)
    before = _standing(sc, "Q")
    here = {p.dedupe_key for p in before}
    sc = lamp_hall(generator=True)
    now = _standing(sc, "Q", here)
    sound = _sound(now)[0]
    verdicts = composer.standing_verdicts(now, here)
    assert verdicts[sound.dedupe_key] == "first"
    assert composer.leads_the_beat(sound, "first", here)
    # A newcomer: the ledger is somewhere else's.
    elsewhere = {composer.standing_key("env", ("cellar",), ("x",))}
    assert not composer.leads_the_beat(sound, "first", elsewhere)
    view = composer.render_view(now, mode="player", prev_standing=elsewhere)
    assert composer.render_view([sound], mode="character").text in view.text
