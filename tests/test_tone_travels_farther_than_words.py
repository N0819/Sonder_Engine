"""TONE TRAVELS FARTHER THAN WORDS (DESIGN_SOUND_FIELD.md § 12, wave A,
2026-10-20).

Through a wall, a door or distance a listener detects a voice -- that
someone spoke, how loudly, in what tone -- some ten decibels under the
level at which any of its words come through. Where a line's words are
lost the fact of the voice still arrives, down to that lower threshold:
"Mara's voice, raised, beyond the wall -- the words do not carry. It sounds
furious." The firewall: tone is a channel; words and names are not.

One test (or more) per rule:

  1. the rung: a raised voice through a wall, a normal one through a heavy
     door or glass, a voice rooms away -- words lost, the voice heard; a
     normal voice through a wall, and breath anywhere, not even that;
  2. the percept carries no word and no name it was not given: no body, no
     fragment, the speaker named only where the voice is known or seen, and
     the line's tone only where it is shaped like a voice quality and holds
     no word of the line;
  3. one voice, one sentence a beat;
  4. both packs render it; a memory keeps it;
  5. the sense card's `trace` -- detected, nothing more -- no longer falls
     through to the full line (an extraordinary ear behind a wall was handed
     the words verbatim).
"""

from __future__ import annotations

from agents import composer
from agents.composer import render_view
from world.spatial import (VOICE_TONE_SNR_DB, FRAGMENT_SNR_DB, hear_level,
                           spatial_rel_between, voice_carries,
                           voice_margin_db)

WALL = {"same_room": False, "barrier": "wall", "distance": "near"}
IRON_DOOR = {"same_room": False, "barrier": "closed_door", "material": "iron",
             "distance": "near"}
DOOR = {"same_room": False, "barrier": "closed_door", "distance": "near"}

LINE = {"speaker": "Mara", "exact_quote": "Where is the ledger, Ivo?",
        "intended_target": "Ivo", "tone": "furious, pacing the floorboards"}


def _percept(rel, volume="loud", *, display="Mara", tone=None, voice="",
             senses=None, bearing="beyond the wall", order_key=0, **line):
    entry = dict(LINE, volume=volume, **line)
    if tone is not None:
        entry["tone"] = tone
    return composer.speech_percept(
        entry, rel, "Eve", display=display, can_see=False, senses=senses,
        voice=voice, bearing=bearing, order_key=order_key,
        prev_standing=frozenset())


def test_a_raised_voice_through_a_wall_is_heard_as_a_voice():
    """A wall passes a raised voice's low half -- its tune, not its
    consonants: no word arrives, the voice does. An ordinary voice through
    the same masonry is not even that. The rung sits ten decibels under the
    last caught word."""
    assert VOICE_TONE_SNR_DB == FRAGMENT_SNR_DB - 10.0
    assert hear_level(WALL, "loud") == "none"
    assert voice_carries(WALL, "loud")
    assert hear_level(WALL, "normal") == "none"
    assert not voice_carries(WALL, "normal")
    # A heavy door with nobody at it: the words are gone, the voice is not.
    assert hear_level(IRON_DOOR, "normal") == "none"
    assert voice_carries(IRON_DOOR, "normal")
    # The complement: a whisper has no voicing to carry, and the owner
    # ruled it private beyond reach -- through a door, nothing.
    for volume in ("whisper", "mutter"):
        assert hear_level(DOOR, volume) == "none"
        assert not voice_carries(DOOR, volume)


def test_rooms_away_the_voice_outlasts_its_words():
    """Down a run of open doorways an ordinary voice is in pieces from four
    rooms and gone at eight; its voice is still there where its words are
    gone, and at last gone too."""
    def run(hops):
        rooms = {}
        for i in range(hops + 1):
            adjacent = []
            if i:
                adjacent.append({"to": "r%d" % (i - 1), "barrier": "open_door", "dir": "w"})
            if i < hops:
                adjacent.append({"to": "r%d" % (i + 1), "barrier": "open_door", "dir": "e"})
            rooms["r%d" % i] = {"name": "room %d" % i, "exposure": "enclosed",
                                "size": "medium", "anchors": {}, "adjacent": adjacent}
        return {"rooms": rooms, "positions": {"L": "r0", "S": "r%d" % hops},
                "stations": {}, "entities": {}, "poses": {}, "orientation": {},
                "contained": {}}
    words_gone = [h for h in range(2, 30)
                  if hear_level(spatial_rel_between(run(h), "L", "S"), "normal") == "none"]
    assert words_gone, "a normal voice should be lost somewhere down the run"
    first = words_gone[0]
    rel = spatial_rel_between(run(first), "L", "S")
    assert voice_carries(rel, "normal")
    assert voice_margin_db(rel, "normal") >= VOICE_TONE_SNR_DB


def test_the_percept_holds_no_word_of_the_line():
    p = _percept(WALL)
    assert p.fidelity == "voice" and p.channel == "hearing"
    assert "body" not in p.data and "fragment" not in p.data
    text = render_view([p], mode="player", language="en").text
    assert text == ("Mara's voice, raised, beyond the wall — the words do "
                    "not carry. It sounds furious.")
    for word in ("ledger", "Ivo", "Where", "floorboards", "pacing"):
        assert word not in text


def test_a_stranger_behind_a_wall_is_a_voice_and_never_a_name():
    p = _percept(WALL, display="a voice")
    text = render_view([p], mode="player", language="en").text
    assert text.startswith("A voice, raised, beyond the wall")
    assert "Mara" not in text


def test_only_a_voice_quality_of_the_tone_is_carried():
    """TONE IS A CHANNEL; WORDS AND NAMES ARE NOT. The tone's first part,
    one word shaped like a voice quality, and nothing of the line or of a
    name; anything else is withheld whole. Measured on the owner's 272
    distinct toned lines: the heads that would carry as phrases included
    "murmured against skin" and "whispered command"."""
    carried = {
        "furious": "furious",
        "panicked, fearful": "panicked",
        "Warm and lightly teasing, glancing over her shoulder": "",
        "flustered and bright": "",                # a phrase: where the voice
        "murmured against skin": "",               # ends and the body begins
        "mocking Ivo": "",                         # a name
        "ledger-obsessed": "",                     # a word of the line
        "settling into the chair across from her": "",   # a clause
        "with a smirk": "",                        # conduct: the eye's
        "a 3 am rasp": "",                         # a digit
        "": "",
    }
    for tone, want in carried.items():
        p = _percept(WALL, tone=tone)
        assert p.data.get("tone_heard", "") == want, tone


def test_one_voice_one_sentence_a_beat():
    lines = [_percept(WALL, exact_quote=q, order_key=n)
             for n, q in enumerate(("Where is it?", "Answer me!", "Ivo!"))]
    text = render_view(lines, mode="player", language="en").text
    assert text.count("Mara's voice") == 1


def test_both_packs_say_it_and_a_memory_keeps_it():
    p = _percept(IRON_DOOR, volume="normal", bearing="")
    ja = render_view([p], mode="player", language="ja").text
    assert "Mara" in ja and "聞き取れない" in ja
    assert "words" not in ja and "voice" not in ja
    episode = composer.render_episode([p], language="en")
    remembered = getattr(episode, "text", episode)
    remembered = remembered[0] if isinstance(remembered, tuple) else remembered
    assert "Mara's voice" in remembered and "ledger" not in remembered


def test_a_trace_carries_no_words_and_no_name():
    """An extraordinary ear behind a wall detects a voice (`sense_adjusted`'s
    `trace`): detection, direction at best -- never the line. It fell
    through to the full branch and was handed the words verbatim."""
    senses = [{"channel": "hearing", "acuity": "extraordinary"}]
    p = _percept(WALL, volume="normal", senses=senses)
    assert p.fidelity == "trace" and p.source_label == ""
    text = render_view([p], mode="player", language="en").text
    assert "ledger" not in text and "Mara" not in text
    assert text == "A faint voice beyond the wall — nothing you can make out."
    ja = render_view([p], mode="player", language="ja").text
    assert "ledger" not in ja and "Mara" not in ja
