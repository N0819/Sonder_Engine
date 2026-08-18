import pytest

from providers import DegenerateOutput, OutputGuard

def test_output_guard_aborts_endless_spaces():
    guard = OutputGuard()

    with pytest.raises(DegenerateOutput):
        guard.feed(" " * 1000)

def test_output_guard_aborts_character_repetition():
    guard = OutputGuard()

    with pytest.raises(DegenerateOutput):
        guard.feed("x" * 500)

def test_output_guard_allows_normal_unicode_text():
    guard = OutputGuard()

    guard.feed(
        "Tamamo steps into the garden. "
        "狐火が石灯籠の周囲で静かに揺れる。 "
        "The Doctor watches with interest."
    )

class TestAPhraseLoop:
    """A stuck sampler repeating a SENTENCE, not a fragment.

    Measured live: a character step locked onto a 100-character cycle --
    "I apologize for the shock. Are you able to understand me? The restraints
    are a standard precaution." -- and rode it for three and a half minutes
    toward the 40,000-token ceiling. Every existing rule missed it, and for one
    reason: the longest repeating unit any of them looks for is 16 characters.

    The guard's job is not to be clever about it. `DegenerateOutput` is
    retryable, so catching it early is the whole win -- the ladder throws the
    ruined generation away and asks again.
    """

    LOOP = ("I apologize for the shock. Are you able to understand me? "
            "The restraints are a standard precaution. ")

    def _feed(self, text, chunk=64):
        guard = OutputGuard()
        for i in range(0, len(text), chunk):
            guard.feed(text[i:i + chunk])
        return guard

    def test_the_live_loop_is_caught(self):
        with pytest.raises(DegenerateOutput) as caught:
            self._feed(self.LOOP * 60)
        assert "100-character" in str(caught.value)
        assert caught.value.retryable is True

    def test_it_is_caught_in_hundreds_of_characters_not_thousands(self):
        """The point of catching it at all. Three cycles is roughly 400
        characters; the live one ran past 150,000."""
        guard = OutputGuard()
        with pytest.raises(DegenerateOutput):
            for _ in range(60):
                guard.feed(self.LOOP)
        assert len(guard.text) < 1000

    def test_two_repeats_are_not_a_loop(self):
        """A writer repeats a line for effect -- a stammer, a refrain, a
        character insisting. Three exactly-identical consecutive blocks is
        what a writer essentially never does and a stuck sampler never stops
        doing."""
        self._feed("She said it twice. " + self.LOOP * 2 + "Then she stopped.")

    def test_ordinary_prose_is_untouched(self):
        """Long, varied prose -- deliberately NOT one paragraph repeated, which
        is what a lazy long-text fixture reaches for and which really is three
        identical blocks in a row."""
        prose = " ".join(
            f"The observation room holds still for a {n}th beat, and the "
            f"reinforced glass gives back {n} reflections of the desk lamp "
            f"while the anomaly's folder lies unopened beside the microphone."
            for n in range(40))
        self._feed(prose)

    def test_a_paragraph_repeated_verbatim_three_times_does_trip_it(self):
        """Stated rather than hidden: this is the false-positive shape, and it
        is accepted. Swept against 4,000 stored narrator, character, loop and
        background outputs from live play -- zero tripped. The cost when it
        does is one retry; the cost of missing a loop was measured at three and
        a half minutes."""
        with pytest.raises(DegenerateOutput):
            self._feed("The corridor was empty and the lamp had gone out. " * 5)

    def test_a_repeated_short_run_still_belongs_to_the_older_rule(self):
        """Below the phrase threshold the 2-16 rule owns it, at a much higher
        repeat count -- which is the right trade at that length, because
        "ha ha ha" is prose and "ha" eighty times over is not."""
        self._feed("ha " * 20)

    def test_the_period_finder_reports_the_unit_it_found(self):
        from providers import _repeating_period

        # Stream-sized inputs: the finder needs more text than its own needle,
        # which is never a constraint on real output and is easy to trip over
        # in a fixture.
        assert _repeating_period("x" * 10 + ("abcdefghijklmnopqrstuvwx" * 12)) == 24
        assert _repeating_period(
            "nothing repeating here at all, honestly. " * 1 + "z" * 400) == 0

    def test_the_period_found_is_the_cycle_not_a_multiple_of_it(self):
        """`rfind`'s `end` bounds where a match must FINISH, not where it may
        start. Bounding it at `len - needle` demanded the whole needle fit
        before the final copy, so for a cycle shorter than the needle it
        skipped the nearest recurrence and returned a MULTIPLE -- 100 instead
        of 50 on a five-times-repeated sentence, which then failed its own
        three-repeat check and reported no loop at all."""
        from providers import _repeating_period

        sentence = "The corridor was empty and the lamp had gone out. "
        assert _repeating_period(sentence * 5) == len(sentence)

    def test_a_long_cycle_is_caught_too(self):
        """The second version of this rule exists because the first could not.

        It swept candidate periods from 24 to 700 and compared slices, so the
        longest cycle it could see was a number chosen in advance -- and the
        very next loop reported from play had a period of 1,237 and sailed
        straight through. Raising the bound would only move where the next one
        hides, so the period is now FOUND by searching for the last recurrence
        of the tail rather than guessed at.
        """
        from providers import DegenerateOutput, OutputGuard

        unit = ("The subject's transition from Japanese confusion to articulate "
                "English objection marks the shift from disoriented "
                "post-transport to coherent subject ready for intake, which is "
                "the boundary between the pre-intake observation phase and the "
                "active interview phase, and Sarah would remember the content "
                "because it is the subject's first real communication and the "
                "foundation of her psychological profile. ") * 2
        assert len(unit) > 700, "the point is a cycle longer than the old bound"

        guard = OutputGuard()
        with pytest.raises(DegenerateOutput):
            for _ in range(8):
                guard.feed(unit)
        assert len(guard.text) < len(unit) * 4

    def test_a_long_block_needs_only_two_repeats_a_short_one_needs_three(self):
        """A stammer repeats a sentence; nothing repeats a paragraph twice by
        accident. The threshold follows the length rather than being one number
        for both."""
        from providers import _LOOP_LONG_PERIOD, _repeating_period

        short = "just a modest little phrase here that runs on a while. "
        assert len(short) < _LOOP_LONG_PERIOD
        assert _repeating_period(short * 2) == 0
        assert _repeating_period(short * 4) == len(short)

        long_block = ("a considerably longer paragraph of prose that carries "
                      "well past the threshold where two exact repeats stop "
                      "being something any writer would ever produce on "
                      "purpose, and start being the signature of a sampler "
                      "that has locked onto its own tail and cannot let go. ")
        assert len(long_block) >= _LOOP_LONG_PERIOD
        assert _repeating_period(long_block * 2) == len(long_block)

    def test_the_live_thousand_character_cycle(self):
        """The one that got past the first version, at its real length."""
        from providers import _repeating_period

        unit = ("The subject's transition from Japanese confusion to articulate "
                "English objection, including the ability to register and "
                "challenge conversational rudeness, marks the shift from "
                "'disoriented post-transport' to 'coherent subject ready for "
                "intake' -- the boundary between the pre-intake observation "
                "phase and the active interview phase. Sarah would remember "
                "the content because it is the subject's first real "
                "communication and the foundation of her psychological "
                "profile. ")
        assert len(unit) > 400
        assert _repeating_period(unit * 3) == len(unit)
