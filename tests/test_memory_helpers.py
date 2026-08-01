"""Tests for pure memory helper functions."""

from memory import (
    _default_category,
    _extract_entities,
    _extract_key_phrases,
    _gist,
    _temporal_mode,
)

def test_temporal_old_cues():
    assert _temporal_mode("What happened long ago?") == "old"
    assert _temporal_mode("When was the first time we met?") == "old"

def test_temporal_recent_cues():
    assert _temporal_mode("What just happened?") == "recent"

def test_temporal_neutral():
    assert _temporal_mode("What did Mara promise?") == "neutral"

def test_quoted_phrase_is_preserved():
    phrases = _extract_key_phrases(
        'Mara said, "I will return before dawn."',
    )

    assert "I will return before dawn." in phrases

def test_kind_to_category():
    assert _default_category("episodic") == "episode"
    assert _default_category("dialogue") == "dialogue"
    assert _default_category("inference") == "inference"
    assert _default_category("unknown") == "episode"

def test_entity_extraction():
    entities = _extract_entities(
        "Alice met Bob at the Old Bridge",
    )

    assert "Alice" in entities
    assert "Bob" in entities
    assert "Old Bridge" in entities

def test_gist_truncation():
    long_text = "This is a sentence. " * 50
    gist = _gist(long_text, limit=100)

    assert len(gist) <= 100

def test_gist_normalizes_whitespace():
    assert _gist("One\n\n  two\tthree.") == "One two three."

def test_empty_helpers_are_safe():
    assert _extract_entities("") == []
    assert _extract_key_phrases("") == []
    assert _gist("") == ""

class TestStrandedEmbeddingsAreAnnounced:
    """Configuring an `embeddings` provider on a story with history silently
    halves its retrieval, and nothing said a word.

    A row whose `embedding_model`/`embedding_dim` differ from the live
    provider's scores 0.0 on BOTH vector rankings — correct in itself, since a
    vector from another model is not comparable — and nothing re-embeds, so it
    stays 0.0 forever. Memories written before the switch drop to keyword and
    exact matching while newer ones keep all four signals: the bank splits into
    two eras at the moment of the upgrade. Retrieval still WORKS, which is
    precisely why it needs announcing rather than raising. See
    docs/UNBUILT.md §1.15.
    """

    def _capture(self, monkeypatch):
        import logging

        import memory
        seen = []

        class _H(logging.Handler):
            def emit(self, record):
                seen.append(record.getMessage())

        handler = _H()
        memory.logger.addHandler(handler)
        monkeypatch.setattr(memory, "_STRANDED_REPORTED", set())
        return memory, seen, handler

    def test_a_mismatched_bank_is_reported(self, monkeypatch):
        memory, seen, handler = self._capture(monkeypatch)
        try:
            memory._warn_stranded_embeddings(1, 2, 300, 442, "openai:x:embed-3")
        finally:
            memory.logger.removeHandler(handler)
        assert len(seen) == 1
        assert "300 of 442" in seen[0]

    def test_it_reports_once_per_situation_not_once_per_beat(self, monkeypatch):
        """Retrieval runs for every character on every beat; a warning per call
        is the noise it exists to cut through."""
        memory, seen, handler = self._capture(monkeypatch)
        try:
            for _ in range(5):
                memory._warn_stranded_embeddings(1, 2, 300, 442, "openai:x:embed-3")
        finally:
            memory.logger.removeHandler(handler)
        assert len(seen) == 1

    def test_a_different_model_is_a_new_situation(self, monkeypatch):
        memory, seen, handler = self._capture(monkeypatch)
        try:
            memory._warn_stranded_embeddings(1, 2, 300, 442, "openai:x:embed-3")
            memory._warn_stranded_embeddings(1, 2, 300, 442, "cheap:crc32:256")
        finally:
            memory.logger.removeHandler(handler)
        assert len(seen) == 2

    def test_a_compatible_bank_says_nothing(self, monkeypatch):
        memory, seen, handler = self._capture(monkeypatch)
        try:
            memory._warn_stranded_embeddings(1, 2, 0, 442, "cheap:crc32:256")
            memory._warn_stranded_embeddings(1, 2, 5, 0, "cheap:crc32:256")
        finally:
            memory.logger.removeHandler(handler)
        assert seen == []


class TestRelevanceCanOutrankRecency:
    """Two score scales were being summed as if they shared one.

    RRF's magnitude is arbitrary — `weight / (60 + rank)` is ~0.02 at rank 1
    and only its ORDER means anything — while the bonuses after it (salience,
    recency, presence) are hand-tuned on a 0..1 utility scale. Raw, the four
    relevance rankings could contribute 0.074 combined against a recency bonus
    reaching 0.12 alone: a recent, salient memory with NO relevance to the
    query outranked the best match on every relevance signal there is.

    Invisible until real embeddings landed — with the crc32 fallback the
    vector rankings were lexical noise, so nobody could tell they were being
    ignored. Measured on a live 441-memory story, end-to-end retrieval of a
    paraphrased memory ran at 1/16 and 88% of what reached a character carried
    no vector match at all.
    """

    def test_the_four_rankings_together_outweigh_the_recency_bonus(self):
        import memory
        best = sum(w * memory._RRF_SCALE / 61.0 for w in (1.25, 1.15, 1.1, 1.0))
        # The bonuses, at their individual maxima, from search_memories.
        recency, salience, here = 0.12, 0.08, 0.09
        assert best > recency + salience + here, (
            "relevance must be able to beat a recent, salient, present memory "
            "that matches nothing")

    def test_a_single_top_ranked_signal_outweighs_recency_alone(self):
        import memory
        assert 1.0 * memory._RRF_SCALE / 61.0 > 0.12

    def test_the_bonuses_still_decide_between_comparable_matches(self):
        """Scaled, not silenced. Salience and recency are what should choose
        between two memories the query fits equally well — the failure being
        fixed is them choosing between memories it does NOT fit."""
        import memory
        one_signal_mid_rank = 1.0 * memory._RRF_SCALE / 70.0
        assert 0.12 < one_signal_mid_rank * 2, (
            "the bonus band must stay within reach of a ranking difference, "
            "or it stops being a tiebreak and becomes decoration")


class TestHowManyMemoriesReachACharacter:
    """`recall_limit` was 8, and every result set is padded with chronological
    neighbours of what was recalled — so four padding entries were a third of
    what a character saw. Measured on real perception views, raising the limit
    dilutes the padding with relevance-selected memories: mean relevance of
    the whole set RISES (0.608 -> 0.640) while the least relevant slot does
    not move. The added memories are better than what they displace.
    """

    def test_the_limit_is_the_one_that_was_measured(self):
        import memory
        assert memory._RECALL_LIMIT == 16

    def test_the_default_is_taken_from_the_constant(self):
        """So tuning it is one edit, not a hunt through call sites."""
        import inspect

        import memory
        sig = inspect.signature(memory.build_character_memory_context)
        assert sig.parameters["recall_limit"].default == memory._RECALL_LIMIT

    def test_it_stops_short_of_where_the_payload_stops_paying(self):
        """24 recalls more but flattens on relevance while the payload keeps
        growing; the attention budget is real (docs/UNBUILT.md 1.12)."""
        import memory
        assert 8 < memory._RECALL_LIMIT <= 16


class TestAnAbsenceIsNotAnEpisode:
    """A view saying only "you are somewhere unspecified" records the ABSENCE
    of an event, and an absence is not a memory.

    Measured live before this: 356 rows across five stories — 7.3% of the
    whole bank, and a THIRD of one story's 442 — were the single sentence
    "You are in an unspecified area.", all at salience 0.47, all identical,
    all eligible to be handed to a character instead of something that
    happened. Still being written on the most recent turn of three stories.

    It arises legitimately (an NPC off in unloaded space) and illegitimately
    (`agents/common.character_room` calls the same phrase "leaking a false
    empty view" from a position it could not resolve). The cause does not
    change the remedy: either way there is nothing to remember.
    """

    def test_the_engines_own_placeholders_are_recognised(self):
        from commit import _is_empty_view
        assert _is_empty_view("You are in an unspecified area.")
        assert _is_empty_view("you register nothing new this beat.")
        assert _is_empty_view("   ")
        assert _is_empty_view("")

    def test_a_view_that_goes_on_to_say_something_is_kept(self):
        """Matched on the placeholder, not on prose containing it."""
        from commit import _is_empty_view
        assert not _is_empty_view(
            "You are in an unspecified area. The Doctor circles the console "
            "and the light shifts across his face.")
        assert not _is_empty_view(
            "The corridor stretches ahead, lit by recessed strips.")


class TestAMemoryCarriesTheMoodItWasFormedIn:
    """A memory took the character's raw self-report, not their real mood.

    `affect.resolve_affect` is what turns a proposed mood into the one the
    character actually holds — decayed toward baseline, moved by this beat's
    appraisal, cross-checked against the label. It runs ~500 lines BELOW the
    memory mint, so a memory could never see it.

    Measured across the same characters: the raw self-report averages +0.773
    with 0% negative; their resolved affect averages +0.467 with 22% negative.
    They disagree by +0.31, and only one of them is a mood. Newer stories
    inherited the saturated one — median valence +0.85, four negatives in
    3,162 rows — which is a constant, not an axis, and it silently disables
    everything downstream that reads affect.
    """

    def test_the_resolved_affect_is_preferred_over_the_self_report(self):
        import inspect

        import commit
        src = inspect.getsource(commit.prepare_memory_commit)
        i_resolved = src.index('_surface = (((st.get("active_state")')
        i_raw = src.index('_surface = (active_state.get("affect")')
        assert i_resolved < i_raw, (
            "the stored resolved affect must be consulted first; the raw "
            "self-report is only the fallback for a character's first beat")

    def test_the_self_report_still_covers_a_first_beat(self):
        """A character with no resolved affect yet has only their own report."""
        import inspect

        import commit
        src = inspect.getsource(commit.prepare_memory_commit)
        assert "if not _surface:" in src
