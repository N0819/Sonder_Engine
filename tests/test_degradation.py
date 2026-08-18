"""A retold claim gets fainter, never different.

Approach C's rumor floor rests on one correctness argument: distortion is
subtractive, so it "cannot invent and therefore cannot contradict". Additive
distortion produces a DIFFERENT story and a different story reads as an engine
error; subtractive distortion produces a FAINTER story, which reads as a rumor.
The fatal failure mode is "how did he know that" — and its quieter twin, an NPC
who believes something that never happened.

These pin the properties that argument depends on.
"""

from __future__ import annotations

from world import degradation

CLAIM = "Mora killed thirty-seven raiders at the Gate Passage"
NAMES = ["Mora"]
PLACES = ["Gate Passage"]


def _degrade(hops):
    return degradation.degrade(CLAIM, hops, names=NAMES, places=PLACES)


class TestSubtractionOnly:
    def test_the_witnessed_surface_travels_intact_at_zero_hops(self):
        """The holder who saw it has not been told anything — they were
        there. Degrading at the source would make the eyewitness wrong."""
        assert _degrade(0) == CLAIM

    def test_a_retelling_never_adds_a_word_that_was_not_there(self):
        """The whole correctness argument. Every word of the result must
        either be in the original or be one of the three vague tokens this
        module is allowed to introduce."""
        allowed = set(CLAIM.casefold().split()) | {
            degradation.VAGUE_COUNT, *degradation.VAGUE_PLACE.split(),
            *degradation.VAGUE_PERSON.split()}
        for hops in range(0, 8):
            for word in _degrade(hops).casefold().split():
                assert word in allowed, \
                    "hop %d invented %r" % (hops, word)

    def test_the_specifics_only_ever_shrink(self):
        """Subtraction is monotonic. A claim that grew a detail back would be
        a mind knowing something nobody delivered.

        Measured as which of the ORIGINAL words survive, not as string length:
        "a stranger" is longer than "Mora" and carries far less. Length is the
        wrong yardstick for specificity, and this test asserted it at first.
        """
        original = set(CLAIM.casefold().split())
        surviving = [original & set(_degrade(h).casefold().split())
                     for h in range(0, 8)]
        for earlier, later in zip(surviving, surviving[1:]):
            assert later <= earlier, \
                "a detail came back: %s" % (later - earlier)

    def test_a_count_of_one_is_left_alone(self):
        """Rewriting "one man" to "several man" would claim MORE people than
        the witnessed surface ever said — additive, in the one direction that
        matters most."""
        claim = "one man was seen leaving"
        assert degradation.degrade(claim, 3) == claim


class TestWhatIsLostAndInWhatOrder:
    def test_the_count_goes_first(self):
        first = _degrade(degradation.TIER_COUNTS)
        assert "thirty-seven" not in first
        assert degradation.VAGUE_COUNT in first
        assert "Mora" in first and "Gate Passage" in first

    def test_the_place_goes_second(self):
        second = _degrade(degradation.TIER_PLACES)
        assert "Gate Passage" not in second
        assert degradation.VAGUE_PLACE in second
        assert "Mora" in second, "the name should outlive the place"

    def test_the_name_goes_last(self):
        """The point of a rumor is WHO. Dropping the name at the first hop
        makes every rumor useless one room from its source — "a stranger did
        something somewhere" — and the strongest signal in approach C, that
        the player's own deeds precede them, would never land."""
        third = _degrade(degradation.TIER_NAMES)
        assert "Mora" not in third
        assert degradation.VAGUE_PERSON in third

    def test_a_longer_place_name_is_not_eaten_a_word_at_a_time(self):
        """Replacing "Gate" before "Gate Passage" leaves "some place Passage" —
        neither the original claim nor a vaguer one, but a sentence nobody
        wrote."""
        out = degradation.degrade(
            "seen at the Gate Passage", degradation.TIER_PLACES,
            places=["Gate", "Gate Passage"])
        assert "Passage" not in out
        assert out.count(degradation.VAGUE_PLACE) == 1

    def test_the_article_goes_with_the_thing_it_pointed_at(self):
        """"at the some place" reads as broken grammar, and broken grammar
        reads as an engine fault rather than as vague hearsay — the exact
        confusion this module exists to prevent."""
        out = degradation.degrade("seen at the Gate Passage",
                                  degradation.TIER_PLACES,
                                  places=["Gate Passage"])
        assert out == "seen at some place"


class TestNothingIsGuessed:
    def test_a_name_the_caller_did_not_supply_survives(self):
        """A general-purpose name detector would have to judge which words are
        people, and a wrong guess silently rewrites a claim into something
        false. The engine knows its own cast; it should say so."""
        out = degradation.degrade(CLAIM, 9, names=[], places=[])
        assert "Mora" in out and "Gate Passage" in out

    def test_an_empty_claim_stays_empty(self):
        assert degradation.degrade("", 4, names=NAMES) == ""

    def test_a_nonsense_hop_count_degrades_nothing(self):
        assert degradation.degrade(CLAIM, None, names=NAMES) == CLAIM
        assert degradation.degrade(CLAIM, -3, names=NAMES) == CLAIM


class TestDerivedNeverStored:
    def test_degrading_twice_is_not_degrading_further(self):
        """THE reason the vague text is derived from hops instead of stored.
        `several` is itself a word; a function run over its own output would
        eventually chew a claim into something nobody wrote. Re-running from
        the original at a higher hop count is the only safe shape."""
        once = degradation.degrade(CLAIM, 1, names=NAMES, places=PLACES)
        twice = degradation.degrade(once, 1, names=NAMES, places=PLACES)
        assert twice == once

    def test_retelling_a_retelling_lands_where_telling_it_twice_would(self):
        """THE property that lets a told report store the vaguer wording
        rather than the original.

        The firewall this whole engine is built on says no mind may use
        information it did not legitimately acquire, and a row holding the
        exact witnessed surface for someone who only heard a rumor is that
        breach waiting for one careless reader. So a told report stores what
        its holder actually heard — which is only safe if degrading THAT again
        lands in the same place as degrading the original further. The tiers
        are independent replacements and the vague tokens are not themselves
        counts, places or names, so it does.
        """
        for first in range(0, 5):
            for total in range(first, 6):
                stepwise = degradation.degrade(
                    _degrade(first), total, names=NAMES, places=PLACES)
                assert stepwise == _degrade(total), \
                    "stepwise %d->%d diverged from direct" % (first, total)

    def test_the_result_depends_on_nothing_but_the_claim_and_the_hops(self):
        """"Seeded" in the design means reproducible, and the strongest form
        of reproducible is a pure function. No clock, no randomness, no row."""
        assert _degrade(2) == _degrade(2)


class TestAnExhaustedRumorStopsTravelling:
    def test_a_claim_that_has_lost_everything_is_exhausted(self):
        """The deterministic answer to the town of criers, where every NPC
        recites news forever. The words stay grammatical; they have simply
        stopped being about anything."""
        assert not degradation.is_exhausted(0)
        assert not degradation.is_exhausted(degradation.TIER_NAMES)
        assert degradation.is_exhausted(degradation.EXHAUSTED_HOPS)

    def test_exhaustion_survives_a_bad_value(self):
        assert degradation.is_exhausted(None) is False


class TestDiagnosticsAreNotDelivered:
    def test_what_was_lost_is_answerable(self):
        assert degradation.lost_at(0) == []
        assert degradation.lost_at(2) == ["count", "place"]
        assert degradation.lost_at(3) == ["count", "place", "name"]

    def test_it_is_not_wired_into_any_payload(self):
        """A mind that knew WHICH details had been filed off would know more
        than a mind that had merely heard a vague story."""
        import pathlib

        root = pathlib.Path(degradation.__file__).resolve().parents[1]
        packages = ("core", "llm", "world", "mind", "story",
                    "dressing", "persist", "web", "agents")
        for path in [p for pkg in packages for p in (root / pkg).glob("*.py")]:
            if path.name == "degradation.py":
                continue
            assert "lost_at" not in path.read_text(encoding="utf-8"), \
                "%s delivers what was lost" % path.name
