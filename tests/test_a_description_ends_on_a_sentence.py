"""A room's description in a view ends where a sentence ends.

`common.room_prose` sliced a room's text at 600 characters, so the landing
stage's 655 reached the player's view as "... and the open fen stretc."
(scratch story 166, turn 4597), and 60 of the 681 described rooms on that
db ran past the cap. The cap stays, named (`ROOM_PROSE_CHARS`); the cut
falls between sentences.
"""

from agents.common import ROOM_PROSE_CHARS, room_prose, whole_sentences

STAGE = (
    "A timber platform built on driven piles over the tidal fen, planked with "
    "rough-sawn boards tarred black at the edges where the water reaches. The "
    "stage runs out west from the low walk to the deeper water where the mail "
    "ferry can come alongside, its outer end fringed with rope fenders and "
    "worn mooring posts. Gaps between the boards show the dark fen water moving "
    "below. The smell of salt mud, rotting reed, and cold tar comes up through "
    "the planking. From here the town rises on its stilts to the east -- tarred "
    "plank walks, rope bridges, the smoking chimneys of pile houses -- and the "
    "open fen stretches away to the west under a sky going grey with fog.")


def test_a_long_description_keeps_whole_sentences():
    assert len(STAGE) > ROOM_PROSE_CHARS
    view = room_prose({"desc": STAGE})
    assert len(view) <= ROOM_PROSE_CHARS
    assert STAGE.startswith(view)
    assert view.endswith("up through the planking.")


def test_a_short_description_is_untouched():
    assert room_prose({"desc": "A low tarred shed."}) == "A low tarred shed."


def test_a_first_sentence_longer_than_the_cap_is_kept_whole():
    one = "A " + "very " * 200 + "long room."
    assert whole_sentences(one, ROOM_PROSE_CHARS) == one


def test_japanese_sentences_are_cut_between_them():
    text = "長い部屋だ。" * 150
    out = whole_sentences(text, ROOM_PROSE_CHARS)
    assert out.endswith("。") and len(out) <= ROOM_PROSE_CHARS and text.startswith(out)
