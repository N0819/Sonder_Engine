"""The deterministic recognizers in `mind/` read the STORY's vocabulary.

Every judgement in this package that looks at words used to look at English
words: the theory-of-mind kind cues that keep a model from buying confidence
by mislabelling a claim, the affect lexicon that decides whether a stated mood
contradicts the computed appraisal, the memory stopwords and word regexes that
build every FTS query and key phrase, and the trust vocabulary that decides
whether an inference moves a relationship at all.

None of them ERRORED in a Japanese story. Each one degraded to "no signal",
which every caller downstream reads as a legitimate answer:

* `_inferred_kind` returned None on every claim, so `effective_kind` fell back
  to whatever the model declared and the confidence-calibration guard stopped
  existing;
* `label_matches` returns True for a label it does not know -- by design, so it
  never rejects what it cannot judge -- so against an English-only lexicon it
  agreed with everything and no undercurrent was ever synthesised;
* `[A-Za-z0-9'-]{3,}` matches nothing in unspaced Japanese, so every memory FTS
  query was empty and every recall neutral;
* and a conclusion of any strength moved trust by exactly zero.

The pack halves of these tables are checked in `tests/test_language_packs.py`.
This file is the other half: that the CODE reads them, so a pack that carries a
translation is actually consulted. It asserts the recognizers give a different
answer under a different story language -- never a specific Japanese reading,
which belongs to the pack, not to the engine.
"""

import pytest

from language_runtime import language_scope
from mind import affect, memory, theory_of_mind


def test_kind_cues_read_the_story_language():
    """A second-order claim is recognised as one in the story's own language."""
    english = "she thinks I want the letter"
    japanese = "彼女は私が鍵を欲しがっていると思っている"

    with language_scope("en"):
        assert theory_of_mind._inferred_kind(english) == "second_order"
        assert theory_of_mind._inferred_kind(japanese) is None
    with language_scope("ja"):
        assert theory_of_mind._inferred_kind(japanese) == "second_order"

    # And the calibration built on it: a model declaring the cheap ceiling
    # cannot keep it once the claim's own language votes for the dearer one.
    with language_scope("ja"):
        assert theory_of_mind.effective_kind(
            "observation", japanese) == "second_order"


def test_claim_tokens_read_the_story_language():
    japanese = "カレンは桟橋にいた"
    with language_scope("en"):
        assert not theory_of_mind._tokens(japanese) - {japanese}
    with language_scope("ja"):
        assert len(theory_of_mind._tokens(japanese)) > 1


def test_the_affect_lexicon_is_the_packs():
    """`label_matches` can only contradict a label it can look up."""
    with language_scope("en"):
        assert not affect.label_matches("cheerful", -0.8, 0.4)
        assert affect.quadrant_label(-0.8, -0.8) == "downcast"
    with language_scope("ja"):
        # Whatever the pack calls this quadrant, the label it returns must be
        # one its own lexicon can judge -- that is the contract quadrant_label
        # has with label_matches, and it holds per pack, not once in English.
        label = affect.quadrant_label(-0.8, -0.8)
        assert affect.label_matches(label, -0.8, -0.8)
        assert label != "downcast"


def test_memory_word_recognizers_read_the_story_language():
    japanese = "血の匂いがした部屋を覚えている"
    with language_scope("en"):
        assert memory._memory_fts_query(japanese) is None
    with language_scope("ja"):
        assert memory._memory_fts_query(japanese)


def test_summary_support_splits_clauses_in_the_story_language():
    summary = "彼女は鍵を渡した。私は桟橋へ向かった。"
    with language_scope("en"):
        one_clause = memory.derive_summary_support(summary, [])
    with language_scope("ja"):
        many = memory.derive_summary_support(summary, [])
    assert len(one_clause) == 1
    assert len(many) > 1


@pytest.mark.parametrize("language_id, conclusion, expected_sign", [
    ("en", "he lied to me", -1),
    ("en", "she helped me", 1),
    ("ja", "彼は嘘をついた", -1),
    ("ja", "彼女は助けてくれた", 1),
])
def test_trust_moves_on_the_story_languages_vocabulary(
        temp_db, language_id, conclusion, expected_sign):
    """MIND-F10: an inference that concludes something about a person moved
    trust only when it concluded it in English."""
    import time
    from core import db as db_module

    chat_id = db_module.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Trust", "", time.time()))
    char_id = 7
    with language_scope(language_id):
        graph = memory.update_relationships_from_inference(
            chat_id, char_id, 1,
            [{"about": "other", "conclusion": conclusion, "confidence": 1.0}])
    entry = graph.get("other")
    assert entry is not None
    moved = entry.trust
    assert moved != 0.0, conclusion
    assert (1 if moved > 0 else -1) == expected_sign
