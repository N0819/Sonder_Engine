"""The word-boundary cue rule, pinned across an optimisation that rewrote it.

`_exact_cue_score` was 89% of all retrieval time -- 79.9 of 89.9 seconds over
8 queries on a 10,960-row bank (docs/experiments/RETRIEVAL_COST.md). The cost
was rebuilding a regex per row per cue per query, so the search is now guarded
by a plain substring test and the compiled patterns are cached.

The guard is a NECESSARY condition, so it cannot change a verdict -- but
"cannot" is an argument, and this file is the measurement. Every case here is
one the boundary rule was written for, and each has a scar attached:

- "Mara" must not fire inside "marathon". That is why the rule is a boundary
  match and not a substring match at all.
- The boundary class is ASCII alphanumerics rather than `\\w`, because `\\w`
  counts every CJK character as a word character -- which silenced this cue
  for Japanese banks entirely, where a name is followed directly by its
  particle. Found by adversarial review, and the easiest thing in this
  function to break by accident.
- A cue carrying regex metacharacters must match literally, since the pattern
  is escaped and the new guard tests the raw string.
"""

from __future__ import annotations

from mind import memory


def _score(query, *, phrases=(), entities=(), location=""):
    return memory._exact_cue_score(
        {"key_phrases": list(phrases), "entities": list(entities),
         "location": location}, query)


class TestEntityBoundaries:
    def test_a_name_does_not_fire_inside_a_longer_word(self):
        assert _score("she ran a marathon", entities=["Mara"]) == 0.0

    def test_a_name_fires_when_it_stands_alone(self):
        assert _score("where is Mara now", entities=["Mara"]) == 0.7

    def test_punctuation_is_a_boundary(self):
        assert _score("was that Mara's coat?", entities=["Mara"]) == 0.7
        assert _score("(Mara)", entities=["Mara"]) == 0.7

    def test_case_is_ignored_on_both_sides(self):
        assert _score("WHERE IS MARA", entities=["mara"]) == 0.7

    def test_a_cue_absent_from_the_query_scores_nothing(self):
        assert _score("where is Elias", entities=["Mara"]) == 0.0


class TestCJKStillFires:
    """The regression the ASCII-only boundary class exists to prevent.

    A Japanese query attaches a particle directly to the name with no space.
    Under `\\w` boundaries the following character counts as a word character,
    the lookahead fails, and the cue never fires -- silently, for every
    Japanese bank at once.
    """

    def test_a_name_followed_by_a_particle_fires(self):
        assert _score("ひなみはどこ", entities=["ひなみ"]) == 0.7

    def test_a_name_between_kanji_fires(self):
        assert _score("昨日ひなみを見た", entities=["ひなみ"]) == 0.7


class TestMetacharactersAreLiteral:
    def test_a_cue_with_regex_syntax_matches_itself(self):
        assert _score("he said c++ was fine", entities=["c++"]) == 0.7

    def test_a_cue_with_regex_syntax_does_not_match_as_a_pattern(self):
        # "a.c" as a PATTERN would match "abc"; as a literal it must not.
        assert _score("abc", entities=["a.c"]) == 0.0


class TestLocationUsesTheSameRule:
    def test_location_fires_on_a_boundary(self):
        assert _score("back at the harbor", location="harbor") == 0.7

    def test_location_does_not_fire_inside_a_word(self):
        assert _score("harborough road", location="harbor") == 0.0


class TestPhrasesAreSubstringsNotBoundaries:
    """Phrases deliberately use substring matching, not the boundary rule --
    the optimisation touched only the entity and location branches, and this
    pins that the two are still scored differently."""

    def test_a_distinctive_phrase_scores_the_full_tier(self):
        assert _score("i told her the gate was open tonight",
                      phrases=["the gate was open"]) == 1.0

    def test_a_generic_phrase_is_demoted(self):
        got = _score("the woman left", phrases=["the woman"])
        assert 0.0 < got < 1.0

    def test_the_cache_does_not_leak_between_cues(self):
        """Two cues sharing a prefix must not resolve to one pattern."""
        assert _score("where is Mara", entities=["Mar"]) == 0.0
        assert _score("where is Mara", entities=["Mara"]) == 0.7
        assert _score("where is Mar", entities=["Mar"]) == 0.7
