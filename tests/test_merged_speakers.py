"""One pair of quotes, one mouth.

DIALOGUE FIDELITY asks whether each line SURVIVED into the prose. It cannot ask
whether the line ended up in the right person's mouth — and both questions have
the same answer when two speakers' lines are welded into a single quoted span:
every body is present verbatim, so the existing check passes while the reader
is told the wrong character said half of it.

Live, chat 38 t140. The view had them correctly separated, one attributed
clause each:

    the otherworldly nine-tailed kitsune ... says: "Be at ease, both of you."
    The Doctor says: "Tamamo. A pleasure."

The prose welded them:

    "Be at ease, both of you. Tamamo. A pleasure." The Doctor's voice carries
    clean across the clearing — warm, unhurried, no edge in it.

Also chat 38 t39, where the whole of Guinan's line was absorbed into the
Doctor's. Swept across the corpus: 5 stored instances (t39 appears in four
branch descendants of one beat), 2 distinct beats, out of 1082 multi-speaker
beats — and zero false positives, which is what makes it safe to enforce.

Rare, but the exposure is rising: the interaction loop's first wave
(`test_interaction_first_wave.py`) makes beats with two speakers far more
common than they were.
"""

from __future__ import annotations

from agents.common import _check_narrator_fidelity
from agents.narration import _ENFORCEABLE_PREFIXES

VIEW = ('the kitsune says: "Be at ease, both of you." '
        'The Doctor says: "Tamamo. A pleasure."')


def _events(*pairs):
    return [{"n": i, "actor": a, "kind": "speech", "quote": q}
            for i, (a, q) in enumerate(pairs, 1)]


def _merges(prose, view=VIEW, events=None):
    out = _check_narrator_fidelity(
        {"prose": prose}, view, recent_prose=[], exclude_quotes=[],
        event_order=events if events is not None else _events(
            ("Tamamo", '"Be at ease, both of you."'),
            ("The Doctor", '"Tamamo. A pleasure."')))
    return [w for w in out if w.startswith("Merged dialogue")]


class TestTheLiveFailure:
    def test_the_weld_is_caught(self):
        prose = ('"Be at ease, both of you. Tamamo. A pleasure." '
                 "The Doctor's voice carries clean across the clearing.")
        found = _merges(prose)
        assert len(found) == 1
        assert "Tamamo" in found[0] and "The Doctor" in found[0]

    def test_the_same_lines_kept_apart_are_fine(self):
        prose = ('"Be at ease, both of you." Her tails settle. '
                 'The Doctor inclines his head. "Tamamo. A pleasure."')
        assert _merges(prose) == []

    def test_it_is_enforceable_so_the_rewrite_loop_repairs_it(self):
        """The reader is not merely missing something here — they are told the
        wrong person said it, which is worth a rewrite."""
        assert "Merged dialogue from different speakers" in _ENFORCEABLE_PREFIXES

    def test_dialogue_fidelity_alone_would_have_passed_it(self):
        """Why this needed its own check: both bodies ARE present verbatim."""
        prose = '"Be at ease, both of you. Tamamo. A pleasure."'
        out = _check_narrator_fidelity(
            {"prose": prose}, VIEW, recent_prose=[], exclude_quotes=[])
        assert [w for w in out if w.startswith("Dialogue from view missing")] == []


class TestItDoesNotOverfire:
    def test_one_speaker_in_a_span_is_not_a_merge(self):
        prose = '"Be at ease, both of you." She settles.'
        assert _merges(prose) == []

    def test_a_short_line_inside_a_longer_one_is_ignored(self):
        """A brief line can sit inside another by coincidence, and being wrong
        here costs a rewrite — so bodies under 15 characters do not count."""
        events = _events(("Tamamo", '"Go on."'),
                         ("The Doctor", '"Go on. I will wait here by the gate."'))
        prose = '"Go on. I will wait here by the gate."'
        assert _merges(prose, events=events) == []

    def test_a_line_the_player_never_heard_raises_nothing(self):
        """`event_order` is the source precisely because it is already gated to
        lines that reached the player — prose that rightly omits an unheard
        line must not be accused of merging it."""
        assert _merges('"Be at ease, both of you."', events=_events(
            ("Tamamo", '"Be at ease, both of you."'))) == []

    def test_no_dialogue_at_all_is_quiet(self):
        assert _merges("The clearing is quiet and nothing is said.") == []

    def test_missing_event_order_disables_the_check(self):
        """Callers that do not supply the beat's record get the old behaviour
        rather than a crash."""
        out = _check_narrator_fidelity(
            {"prose": '"Be at ease, both of you. Tamamo. A pleasure."'},
            VIEW, recent_prose=[], exclude_quotes=[])
        assert [w for w in out if w.startswith("Merged dialogue")] == []
