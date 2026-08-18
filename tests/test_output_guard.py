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

        assert _repeating_period("x" * 10 + ("abcdefghijklmnopqrstuvwx" * 3)) == 24
        assert _repeating_period("nothing repeating here at all, honestly") == 0
