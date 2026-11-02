"""The sound key of a room is read in the script the room is written in.

`ambience._keywords` was `re.findall(r"[a-z][a-z'-]{2,}", ...)`, so a Japanese
room's name, description, fixtures and state contributed NOTHING to its
acoustic fingerprint (dressing audit F10):

    acoustic_fingerprint(ja room) -> {'name': [], 'desc': [], 'anchors': [], ...}
    hearth lit vs hearth cold (ja) -> identical signature

`_REUSE_EXACT["anchors"]` exists to stop "the fire playing in a cold room",
and in Japanese it was always `[]`; every two Japanese fingerprints scored
1.0, so `reusable_manifest` adopted any bed at all. The key now reads the
room's terms in every script, byte-identically to the old tokens for an
English room, so no English bed is orphaned.

The search query stays in English words: the library on the far end is
indexed in English, and a Japanese term in a Freesound query finds nothing
(the `ambience_prompt` model reads the Japanese place and writes the English).
"""

from __future__ import annotations

import pytest

from dressing import ambience
from dressing.ambience import (_query_ladder, acoustic_fingerprint,
                               acoustic_signature, compose_query,
                               fingerprint_similarity, room_soundscape)


def _ja_hall(hearth):
    return {"rooms": {"hall": {
        "name": "宿場の大広間",
        "desc": "石造りの大広間。梁の低い天井と長い卓。",
        "anchors": {"hearth": {"desc": hearth, "dir": "n"}}}},
        "time_of_day": "夕方", "day_phase": "evening"}


def test_a_japanese_room_has_terms_in_its_key():
    fp = acoustic_fingerprint(_ja_hall("燃え盛る石の暖炉"), "hall")
    assert fp["name"] and fp["desc"] and fp["anchors"], fp
    assert "暖炉" in fp["anchors"]


def test_a_japanese_hearth_going_cold_is_a_new_bed():
    lit = _ja_hall("燃え盛る石の暖炉")
    cold = _ja_hall("冷え切った石の暖炉")
    assert acoustic_signature(lit, "hall") != acoustic_signature(cold, "hall")
    assert fingerprint_similarity(acoustic_fingerprint(lit, "hall"),
                                  acoustic_fingerprint(cold, "hall")) == 0.0


def test_two_different_japanese_rooms_are_not_the_same_sound():
    hall = _ja_hall("燃え盛る石の暖炉")
    kitchen = _ja_hall("燃え盛る石の暖炉")
    kitchen["rooms"]["hall"]["name"] = "地下の台所"
    kitchen["rooms"]["hall"]["desc"] = "湯気の立つ大鍋と銅の鍋。"
    assert fingerprint_similarity(acoustic_fingerprint(hall, "hall"),
                                  acoustic_fingerprint(kitchen, "hall")) < 0.5


def test_an_english_rooms_key_terms_are_the_old_tokens():
    """Byte-identical for an English room, so no stored bed is orphaned."""
    import re

    text = ("The hunters' lodge: a warm, low-beamed hall where a stone hearth "
            "crackles; rain-slick o'clock deck10 Café")
    old = []
    for word in re.findall(r"[a-z][a-z'-]{2,}", text.casefold()):
        if word not in ambience._STOPWORDS and word not in old:
            old.append(word)
    assert ambience._key_terms(text, 50) == old


def test_the_hour_comes_from_the_day_phase():
    fp = acoustic_fingerprint(_ja_hall("燃え盛る石の暖炉"), "hall")
    assert fp["time"] == "evening"
    assert room_soundscape(_ja_hall("燃え盛る石の暖炉"), "hall")["time"] == "evening"


def test_a_rich_room_query_still_ends_on_its_anchor():
    """`compose_query` capped the WHOLE list at nine after appending its
    anchor, so a room with nine or more terms lost "ambience" (dressing audit
    F8) and was searched unanchored -- the knives-and-cupboard-doors failure
    the anchor exists to prevent."""
    place = {"name": "Waystation main hall",
             "desc": "A warm, modest hall where a stone hearth crackles.",
             "anchors": ["crackling stone hearth"], "time": "evening"}
    query = compose_query(place)
    assert query.split()[-1] == "ambience", query
    assert len(query.split()) <= 9
    for rung in _query_ladder(query):
        assert rung.split()[-1] == "ambience", rung


def test_a_short_query_is_unchanged():
    assert compose_query({"name": "Kitchen", "desc": "copper pans"}) == \
        "kitchen copper pans ambience"


@pytest.mark.parametrize("room, edges, expected", [
    # The cell declares nothing; the street's barred window onto it is the
    # same doorway seen from the other side (dressing audit F3).
    ("cell", {"street": [{"to": "cell", "barrier": "bars", "dir": "n"}]}, ["bars"]),
    ("street", {"street": [{"to": "cell", "barrier": "bars", "dir": "n"}]}, ["bars"]),
])
def test_openings_are_the_room_graphs_from_either_side(room, edges, expected):
    scene = {"rooms": {"cell": {"name": "Cell"}, "street": {"name": "Street"}}}
    for rid, adjacent in edges.items():
        scene["rooms"][rid]["adjacent"] = adjacent
    assert room_soundscape(scene, room).get("openings") == expected
