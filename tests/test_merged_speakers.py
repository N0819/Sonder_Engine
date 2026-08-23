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
from language_runtime import linguistic

VIEW = ('the kitsune says: "Be at ease, both of you." '
        'The Doctor says: "Tamamo. A pleasure."')


def _enforceable():
    """The prefixes the ACTIVE story pack calls enforceable.

    Not `narration._ENFORCEABLE_PREFIXES`, which every one of these files used
    to import: that constant is bound once at import from the ENGLISH pack and
    is a compatibility view for tests and audits, while the three live checks
    read the active pack at use time (`narration.py:991, 1016, 1138`). Scoring
    against the eagerly-bound copy is scoring against an object no story
    evaluates -- `AUDIT_DIRECTOR.md` finding 4's shape, one module over.
    """
    return linguistic("agents.narration", "_ENFORCEABLE_PREFIXES")


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
        assert "Merged dialogue from different speakers" in _enforceable()

    def test_dialogue_fidelity_alone_would_have_passed_it(self):
        """Why this needed its own check: both bodies ARE present verbatim."""
        prose = '"Be at ease, both of you. Tamamo. A pleasure."'
        out = _check_narrator_fidelity(
            {"prose": prose}, VIEW, recent_prose=[], exclude_quotes=[])
        assert [w for w in out if w.startswith("Dialogue from view missing")] == []


class TestItDoesNotOverfire:
    def test_dialogue_tag_terminal_comma_is_fidelity_equivalent(self):
        view = '"Lie back," Elyra commands.'
        out = _check_narrator_fidelity(
            {"prose": '"Lie back."'}, view,
            recent_prose=[], exclude_quotes=[])
        assert [w for w in out
                if w.startswith("Dialogue from view missing")] == []

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


def test_a_japanese_story_evaluates_the_same_enforceable_set():
    """And it MUST, today, for a reason worth writing down rather than
    discovering later.

    The two packs carry byte-identical English values for this key, so the
    indirection buys nothing yet -- and that is correct, not an oversight. The
    warnings these prefixes match are still minted as English literals in
    `agents/common.py` ("Merged dialogue from different speakers in one quoted
    span ...", `common.py:6107`). Translating the prefix list before the
    PRODUCERS move would make `startswith` fail on every warning in a Japanese
    story, so nothing would be enforceable and the rewrite-retry would never
    fire -- a silent loss of the whole floor.

    Both halves move together or neither does: the producer half is
    `agents/common.py`'s, tracked as MINDS-22.
    """
    from language_runtime import current_language_id

    token = current_language_id.set("ja")
    try:
        assert "Merged dialogue from different speakers" in _enforceable()
    finally:
        current_language_id.reset(token)


class TestTheShortLineThatWasExempt:
    """A length floor alone exempted exactly the lines that get absorbed.

    Live, chat 84 turn 13. Sarah Moon's two lines and a guard's "Yes ma'am."
    -- ten characters, under the 15-character floor -- were welded into one
    quoted span. The guard never entered the comparison at all, so the span
    scored as ONE speaker and no warning was raised. Rerolling the narrator
    was the only thing that fixed it, and nothing had told the reader why.
    """

    def test_a_short_reply_absorbed_into_another_speakers_span_is_caught(self):
        prose = ('"Guard. Step back from the chair. The subject is '
                 'cooperative. Hinami. The guard will not use force on you. '
                 'Yes ma\'am."')
        found = _merges(prose, view="", events=_events(
            ("Sarah Moon", '"Guard. Step back from the chair. The subject is '
                           'cooperative."'),
            ("Sarah Moon", '"Hinami. The guard will not use force on you."'),
            ("the guard", '"Yes ma\'am."')))
        assert len(found) == 1
        assert "Sarah Moon" in found[0] and "the guard" in found[0]
        assert found[0].startswith(_enforceable())

    def test_the_same_beat_rendered_correctly_is_not_flagged(self):
        """The reroll that fixed it: three spans, one mouth each."""
        prose = ('"Guard. Step back from the chair. The subject is '
                 'cooperative." Her next words follow without pause. '
                 '"Hinami. The guard will not use force on you." '
                 'The guard answers at once. "Yes ma\'am."')
        assert _merges(prose, view="", events=_events(
            ("Sarah Moon", '"Guard. Step back from the chair. The subject is '
                           'cooperative."'),
            ("Sarah Moon", '"Hinami. The guard will not use force on you."'),
            ("the guard", '"Yes ma\'am."'))) == []

    def test_a_short_body_mid_sentence_is_still_coincidence(self):
        """Why the floor existed. A fragment inside another line is not an
        absorbed line, and this warning is enforceable -- being wrong costs a
        rewrite. The sentence-boundary test is what separates the two."""
        assert _merges('"I said no. That is final."', view="", events=_events(
            ("Vale", '"I said no. That is final."'),
            ("Bryn", '"no"'))) == []

    def test_the_players_own_line_is_never_a_merge(self):
        """`event_order` carries the player's quote for ORDER, marked
        `declared`. The echo rule requires it to be absent from the prose, so
        its presence is a different failure with a different fix -- scoring it
        here would buy a rewrite for the wrong reason."""
        events = _events(("Vale", '"Then we are agreed on the terms."'))
        events.append({"n": 2, "actor": "Player", "kind": "speech",
                       "declared": True,
                       "quote": '"Then we are agreed on the terms."'})
        assert _merges('"Then we are agreed on the terms."',
                       view="", events=events) == []
