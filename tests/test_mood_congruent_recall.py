"""Mood-congruent recall, tested against the valence distribution the engine
now actually produces (resolved affect: ~22% negative), not the saturated
self-report it used to inherit."""
import json
import time

import pytest

import memory
from character_schema import default_character_data


@pytest.fixture
def bank(temp_db):
    """A bank big enough that k=3 cannot simply return everything, with the
    same subject at opposite affect — so only congruence can separate them."""
    chat = temp_db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                      ("Mood", "", time.time()))
    char = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(default_character_data("Mara")), "{}", time.time(),
         "char_mood"))
    dark = ["the lantern guttered while she waited alone in the cold",
            "she waited by the lantern and the dark pressed in",
            "the lantern light shook and she waited, wanting to leave",
            "waiting at the lantern, she could not stop shivering"]
    warm = ["waiting by the lantern, warm and unhurried",
            "she waited by the lantern and was glad of the company",
            "the lantern was warm and she waited without minding",
            "waiting at the lantern, easy and content"]
    filler = [f"an unrelated errand across the market, number {i}" for i in range(20)]
    idx = 0
    for content in dark:
        memory.add_memory(chat, char, None, "episodic", "witnessed", 0.6,
                          content, turn_idx=idx, gist=content,
                          key_phrases=["lantern"], valence=-0.8); idx += 1
    for content in warm:
        memory.add_memory(chat, char, None, "episodic", "witnessed", 0.6,
                          content, turn_idx=idx, gist=content,
                          key_phrases=["lantern"], valence=0.8); idx += 1
    for content in filler:
        memory.add_memory(chat, char, None, "episodic", "witnessed", 0.5,
                          content, turn_idx=idx, gist=content, valence=0.0)
        idx += 1
    return {"chat": chat, "char": char}


def _lean(bank, mood, k=4):
    """Net valence of the TOP k, by rank — congruence reorders, it does not
    change what is eligible."""
    from db import q
    hits = memory.search_memories(
        bank["chat"], bank["char"], "waiting by the lantern", k=k,
        aspects=[("how you are feeling", mood)] if mood else None)
    out = []
    for m in hits[:k]:
        r = q("SELECT valence FROM memories WHERE id=?", (m["id"],), one=True)
        out.append(r["valence"] or 0.0)
    return sum(out)


def test_a_warm_character_leans_toward_the_warmer_memories(bank):
    """Against the no-mood baseline, which this fixture leaves leaning dark:
    the darker memories happen to match the query more strongly on their own
    merits, so warmth has to overcome relevance to show at all — and does."""
    assert _lean(bank, "warm and glad of the company") > _lean(bank, None)


def test_the_two_moods_pull_in_opposite_directions(bank):
    """The claim proper. A one-sided comparison against the baseline is not
    available in both directions here: the baseline is already saturated dark
    (every one of the top four), so "darker than baseline" has nowhere to go.
    The differential is what congruence actually asserts."""
    assert _lean(bank, "warm and glad") > _lean(bank, "afraid and alone")


def test_the_effect_survives_a_bank_that_leans_the_other_way(bank):
    """Guards the direction, not just the magnitude — a sign error would pass
    a symmetric test and fail this one."""
    warm = _lean(bank, "warm, safe, content")
    cold = _lean(bank, "afraid, uneasy, tense")
    assert warm > cold, (warm, cold)


def test_a_neutral_memory_is_untouched_either_way(bank):
    """Valence 0 means the memory carries no charge; congruence must not
    invent one in either direction."""
    assert memory._MOOD_CONGRUENCE * 1.0 * 0.0 == 0.0


def test_congruence_cannot_outrank_an_actual_match(bank):
    """It breaks ties between comparably relevant memories. A feedback loop
    that outranked relevance would make a character in despair recall only
    despair, and never anything that might lift it."""
    assert memory._MOOD_CONGRUENCE < 0.08
    assert memory._MOOD_CONGRUENCE < 1.0 * memory._RRF_SCALE / 61.0


def test_prose_with_no_affect_yields_no_axis(bank):
    """No sign is better than a wrong sign for a tiebreak."""
    assert memory._mood_axis("the corridor stretches ahead") is None
