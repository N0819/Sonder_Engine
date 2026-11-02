"""A resident's recent history written in Japanese is long enough when it
is long enough in Japanese.

`ground_recent_history` counted `memory.split()` words, and Japanese does not
space its words: a 159-character episode measured ONE word, every episode was
dropped as `thin_memory`, and the generation of any Japanese story with a
charter-route resident failed with "produced 0 usable episodes" (audit
world_charter_generation_run F3). The floors stay; the unit is the script's
-- a spaced run is one unit, an unspaced character is one, the trade
`agents.common._countable_word_units` already makes."""
import pytest

from world.charter_history import ground_recent_history


_PACKET = {"recent_context": {
    "resident_body_id": "sana", "recent_window_hours": 720,
    "people": [{"body_id": "iven", "name": "イヴェン"}],
    "places": [{"location_id": "clinic", "name": "診療所"}],
}, "evidence": []}

_JA_MEMORY = (
    "朝の受付でイヴェンと一緒に難しい初診の記録を見直し、互いの書き込みが食い違う"
    "箇所を二度確かめた。どちらがどんな前提を置いていたのかを一つずつ口に出して"
    "確かめ、推測で患者を責めることのないよう、説明がつくまでいつもの面談を止め"
    "ておくことにした。昼過ぎには食い違いの原因が古い紹介状にあると分かり、"
    "二人で記録を書き直した。")
_JA_CONSEQUENCE = "一つの問いを残したまま、次の見直しの手順を変えた。"


def _batch(memory, consequence, count=12):
    return {"episodes": [{
        "sequence": i, "when": f"{i}日目", "title": f"症例{i}",
        "location_id": "clinic", "participant_ids": ["iven"],
        "memory": memory, "consequence": consequence,
    } for i in range(1, count + 1)]}


def test_realistic_japanese_episodes_are_accepted():
    grounded = ground_recent_history(_batch(_JA_MEMORY, _JA_CONSEQUENCE),
                                     _PACKET)
    assert len(grounded["memories"]) == 12


def test_a_thin_japanese_episode_is_still_thin():
    with pytest.raises(ValueError, match="at least 10"):
        ground_recent_history(_batch("診療所にいた。", "特になし。"), _PACKET)
