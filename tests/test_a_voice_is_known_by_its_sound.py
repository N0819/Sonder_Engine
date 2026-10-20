"""A VOICE IS RECOGNISED BY ITS SOUND (DESIGN_SOUND_FIELD.md § 12, wave A,
2026-10-20).

A familiar voice is known without sight; a stranger's voice gives what a
voice carries -- its timbre, its register -- and never a name the listener
has not learned.

What the composer did before this, verified: a speaker the listener knows
(the `known` ledger, through `observer_display_map` and perception's
`_attributed_label`) is named whether seen or not, for a whole line and for
a fragment; a stranger who cannot be seen is "a voice" -- and was the
English literal "a voice" in a Japanese view too -- and nothing about how
the voice sounds reached the listener: the speaker's own register from
their card (`social.voice.register`) was said only in the manner slot of a
line SEEN in full.

Now:

  1. a known voice heard through a wall, its words lost, is still named;
  2. an unseen stranger's voice is described once by the speaker's own
     register -- said after the line, whatever of it arrived -- and filed
     as a voice this listener has heard, so it is not said again;
  3. a speaker the listener can see keeps the register in the manner slot,
     as before; a card with no register gets nothing invented;
  4. the unseen speaker's label is the story language's own word.
"""

from __future__ import annotations

from agents import composer
from agents.composer import body_key, render_view, standing_key

REGISTER = "Low contralto, warm and unhurried."
WALL = {"same_room": False, "barrier": "wall", "distance": "near"}
DOOR = {"same_room": False, "barrier": "closed_door", "distance": "near"}
OPEN = {"same_room": False, "barrier": "open_door"}


def _line(volume="normal", text="The boat leaves at dawn."):
    return {"speaker": "Verolla", "exact_quote": text, "volume": volume,
            "intended_target": "Ivo", "tone": ""}


def _p(rel, *, volume="normal", display="a voice", can_see=False,
       voice=REGISTER, prev=frozenset(), order_key=0, text=None):
    return composer.speech_percept(
        _line(volume, text or "The boat leaves at dawn."), rel, "Eve",
        display=display, can_see=can_see, voice=voice,
        prev_standing=prev, order_key=order_key,
        bearing="" if can_see else "through the door")


KEY = standing_key("voice", (body_key("Verolla"),), (REGISTER,))


def test_a_known_voice_through_a_wall_is_named():
    p = _p(WALL, volume="loud", display="Verolla")
    assert p.fidelity == "voice" and p.data["attributed"]
    text = render_view([p], mode="player", language="en").text
    assert text.startswith("Verolla's voice, raised")
    assert "voice_apart" not in p.data          # the name is enough


def test_an_unseen_strangers_voice_is_described_by_its_own_card():
    for rel, fidelity in ((OPEN, "full"), (DOOR, "fragment"),
                          (WALL, "voice")):
        p = _p(rel, volume="loud" if rel is WALL else "normal")
        assert p.fidelity == fidelity
        text = render_view([p], mode="player", language="en").text
        assert text.endswith("The voice is low contralto, warm and unhurried."), text
        assert "Verolla" not in text
    # Never a name, and never prose about anything (review round 4,
    # 2026-10-05: sheet text can name the body it belongs to): a register
    # holding the speaker's name, or one that is a clause, is withheld whole.
    for register in ("Verolla's own low purr",
                     "the voice of someone who has smoked for years and spent "
                     "them shouting over engines"):
        p = _p(OPEN, voice=register)
        assert "voice_apart" not in p.data, register
        assert "The voice is" not in render_view([p], mode="player",
                                                 language="en").text
    # The complement: a speaker the listener can see keeps the register in
    # the manner slot, as before; a card with no register gets nothing
    # invented.
    seen = _p({"same_room": True, "barrier": "open", "tier": "near"},
              display="the tall woman", can_see=True)
    assert "voice_apart" not in seen.data
    assert "in a low contralto" in render_view([seen], mode="player",
                                               language="en").text
    bare = render_view([_p(OPEN, voice="")], mode="player", language="en").text
    assert bare == ('You hear a voice say: "The boat leaves at dawn." '
                    '\u2014 through the door')


def test_a_voice_heard_once_is_not_described_again():
    first = render_view([_p(OPEN)], mode="player", language="en")
    assert KEY in first.standing_keys
    again = render_view([_p(OPEN, prev=frozenset({KEY}))], mode="player",
                        language="en").text
    assert "The voice is" not in again
    # ...and three lines in one beat say it once.
    lines = [_p(OPEN, order_key=n, text="Line %d." % n) for n in range(3)]
    text = render_view(lines, mode="player", language="en").text
    assert text.count("The voice is") == 1


def test_the_unseen_speakers_label_is_the_storys_own_word():
    from language_runtime import compositor_text
    assert compositor_text("unseen_voice_label", "en") == "a voice"
    assert compositor_text("unseen_voice_label", "ja") == "誰か"
    p = _p(OPEN, display=compositor_text("unseen_voice_label", "ja"),
           voice="低いアルト、温かく穏やか。")
    ja = render_view([p], mode="player", language="ja").text
    assert "a voice" not in ja and "誰か" in ja
    assert "低いアルト" in ja
