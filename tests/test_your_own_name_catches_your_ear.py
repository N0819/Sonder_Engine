"""YOUR OWN NAME CATCHES YOUR EAR (DESIGN_SOUND_FIELD.md § 13, wave B1,
2026-10-20).

Real world: one's own name is detected at lower signal levels than other
words, and out of a din or a conversation one is not following -- the
cocktail-party effect (Moray 1959; Wood & Cowan 1995). Before this, a
listener who had a line only in pieces, or only as a voice through a wall,
caught their own name exactly as often as any other word: by length, and
never at all on the voice rung, which carries no words.

The class:

  1. where a listener has a line only in pieces, or as a voice without
     words, their own name in it comes through, and they know someone said
     it -- "You catch your name in it.";
  2. never another word: the voice rung still carries none, the fragment
     keeps exactly the pieces it had, and the percept says THAT the name was
     said, never which form, never who;
  3. only the listener's OWN name, as others call them -- the card's name,
     its words, its aliases; never an engine handle;
  4. a voice that does not reach them carries no name either;
  5. one voice a beat: a name in a later line of the same speaker is kept;
  6. both packs say it, and a memory keeps it.
"""

from __future__ import annotations

from agents import composer
from agents.composer import render_episode, render_view
from world.spatial import hear_level, voice_carries

WALL = {"same_room": False, "barrier": "wall", "distance": "near"}
DOOR = {"same_room": False, "barrier": "closed_door", "distance": "near"}

FORMS = composer.own_name_forms("Ivo Marsh", ["the clerk"])


def _percept(rel, quote, volume="loud", *, order_key=0, forms=FORMS,
             target="Tomas"):
    entry = {"speaker": "Mara", "exact_quote": quote, "volume": volume,
             "intended_target": target, "tone": "furious"}
    return composer.speech_percept(
        entry, rel, "Ivo Marsh", display="Mara", can_see=False,
        bearing="beyond the wall", order_key=order_key,
        prev_standing=frozenset(), name_forms=forms)


def test_the_forms_are_the_names_others_call_you_by():
    assert set(FORMS) == {"Ivo Marsh", "Ivo", "Marsh", "the clerk", "clerk"}
    # Never an engine handle, never a sliver of English.
    forms = composer.own_name_forms("Al", ["char_ab12", "character:7"])
    assert forms == []


def test_your_name_comes_through_a_wall_on_a_voice_alone():
    assert hear_level(WALL, "loud") == "none" and voice_carries(WALL, "loud")
    p = _percept(WALL, "Where is Ivo with the ledger?")
    assert p.fidelity == "voice" and p.data.get("own_name") is True
    text = render_view([p], mode="player", language="en").text
    assert text == ("Mara's voice, raised, beyond the wall — the words do "
                    "not carry. It sounds furious. You catch your name in it.")
    # Not one word of the line, nor which form of the name.
    for word in ("ledger", "Where", "Ivo"):
        assert word not in text
    # Somebody else's name, no name, or the name inside other words: nothing.
    for quote in ("Where is Tomas with the ledger?", "Where is the ledger?",
                  "Ivory and marshmallow"):
        other = _percept(WALL, quote)
        assert not other.data.get("own_name"), quote
        assert "your name" not in render_view(
            [other], mode="player", language="en").text


def test_your_name_in_a_fragment_through_a_door():
    p = _percept(DOOR, "Tell Ivo the cart is ready now.", "normal")
    assert p.fidelity == "fragment" and p.data.get("own_name") is True
    # The fragment keeps exactly the pieces it had.
    assert p.data["fragment"] == composer._muffled_fragment(
        "Tell Ivo the cart is ready now.")
    assert render_view([p], mode="player", language="en").text.endswith(
        "You catch your name in it.")
    # A line heard whole carries no flag -- the name is in it as said -- and
    # a voice that does not reach the listener carries no name either.
    full = _percept({"same_room": True, "barrier": "open", "distance": "near"},
                    "Ivo, sit down.", "normal")
    assert full.fidelity == "full" and not full.data.get("own_name")
    assert _percept(WALL, "Ivo!", "normal") is None


def test_a_name_in_a_later_line_of_one_voice_is_kept():
    lines = [_percept(WALL, q, order_key=n)
             for n, q in enumerate(("Where is it?", "Answer me!",
                                    "Ivo, get in here!"))]
    text = render_view(lines, mode="player", language="en").text
    assert text.count("Mara's voice") == 1
    assert text.endswith("You catch your name in it.")


def test_both_packs_say_it_and_a_memory_keeps_it():
    p = _percept(WALL, "Marsh, the account books!")
    ja = render_view([p], mode="player", language="ja").text
    assert ja.endswith("その中に、自分の名前が聞こえた。")
    episode = render_episode([p], language="en")[0]
    assert episode.endswith("I caught my name in it.")
    assert render_episode([p], language="ja")[0].endswith(
        "その中に、自分の名前が聞こえた。")


def test_a_japanese_name_is_caught_with_its_particle():
    forms = composer.own_name_forms("ヒナミ")
    p = composer.speech_percept(
        {"speaker": "Mara", "exact_quote": "ヒナミさんはどこ？", "volume": "loud"},
        WALL, "ヒナミ", display="Mara", can_see=False, prev_standing=frozenset(),
        name_forms=forms)
    assert p.data.get("own_name") is True
