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