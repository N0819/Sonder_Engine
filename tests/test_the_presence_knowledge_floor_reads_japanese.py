"""The presence-knowledge floor fires in Japanese as it does in English.

`_check_presence_knowledge_channel` is SUBTRACTIVE: `director_resolve` drops a
Director-voiced presence line that names a scene entity the presence has no
channel to (chat 65 t2148, Kadoman and "the strange coins"). It made three
whitespace assumptions (agents_common audit F3): a form of two characters
(硬貨) was never long enough, an unspaced multi-word form (奇妙な硬貨) was "one
word" and so needed a determiner, and the determiner rule demanded whitespace
after the determiner and a non-word character after the noun -- a Japanese
determiner is written straight onto its noun (その硬貨) and the noun straight
onto its particle. So `その奇妙な硬貨のことは知っている` raised nothing where the
English line warned.

A word is now counted in its own script (`_word_count`), a short form is
floored by its script (`_display_floor`), and a determiner of an unspaced
script binds the noun it is written onto, across at most two modifiers and
no particle that ends a phrase. The copper-and-silver rule holds in both
languages: generic talk about coins is never a claim of acquaintance.
"""

from __future__ import annotations

import pytest

from language_runtime import language_scope

from agents.common import _check_presence_knowledge_channel


def _scene(aliases):
    return {
        "rooms": {"market": {"adjacent": []}, "plaza": {"adjacent": []}},
        "entities": {
            "カドマン": {"name": "カドマン", "kind": "person"},
            "coins": {"name": "外国の硬貨", "kind": "object",
                      "aliases": list(aliases)},
        },
        "positions": {"カドマン": "market"},
        "contained": {},
    }


REC = {"sketch": {"station_room": "market"}}


@pytest.mark.parametrize("aliases, line", [
    (["奇妙な硬貨"], "その奇妙な硬貨のことは知っている"),
    (["奇妙な硬貨"], "奇妙な硬貨なら見たよ。"),
    (["硬貨"], "その硬貨はここでは使えない。"),
    (["硬貨"], "あの古い硬貨をどこで手に入れた？"),
])
def test_a_reference_with_no_channel_is_flagged_in_japanese(aliases, line):
    with language_scope("ja"):
        warnings = _check_presence_knowledge_channel(
            "カドマン", line, _scene(aliases), REC, "")
    assert warnings, line


@pytest.mark.parametrize("line", [
    "この町では硬貨しか使わない。",
    "硬貨なら両替商へ行け。",
    "銅貨と銀貨と硬貨で払う。",
])
def test_generic_talk_of_a_single_word_thing_is_not(line):
    with language_scope("ja"):
        assert _check_presence_knowledge_channel(
            "カドマン", line, _scene(["硬貨"]), REC, "") == [], line


def test_hearing_it_named_this_beat_is_still_a_channel():
    with language_scope("ja"):
        assert _check_presence_knowledge_channel(
            "カドマン", "その硬貨はここでは使えない。", _scene(["硬貨"]), REC,
            "この硬貨は使えますか？") == []


def test_english_is_unchanged():
    scene = {
        "rooms": {"market": {"adjacent": []}},
        "entities": {
            "Kadoman": {"name": "Kadoman", "kind": "person"},
            "coins": {"name": "foreign coins", "kind": "object",
                      "aliases": ["strange coins", "coins"]},
        },
        "positions": {"Kadoman": "market"},
        "contained": {},
    }
    rec = {"sketch": {"station_room": "market"}}
    assert _check_presence_knowledge_channel(
        "Kadoman", "I know about the strange coins", scene, rec, "")
    assert _check_presence_knowledge_channel(
        "Kadoman", "Those coins won't spend here.", scene, rec, "")
    assert _check_presence_knowledge_channel(
        "Kadoman", "Local trade runs on copper and silver coins.", scene,
        rec, "") == []
