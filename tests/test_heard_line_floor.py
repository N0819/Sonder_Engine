"""A line the hearing gate granted must survive everything that runs after it.

`perception_outcome` injects each audible line into a perceiver's view, and
THEN runs four passes that can remove text: the identity floor, the
player-speech scrub, the invented-dialogue scrub, and a sentence dedupe. Each
is correct on its own. None of them knows that a line the gate already granted
might be inside what it takes, and nothing re-checked afterwards.

Live (chat 38, t137): the Doctor walked beside the player and spoke four times
— all `normal` volume, same room, open barrier, nothing concealed. Her view
ends

    "...as we scan the mist-shrouded surroundings together. Yeah, I bet I will.\""

an orphaned tail carrying a closing quote and no opening — the signature of a
partial quoted span removed from the middle of a delivered line. The other
three lines are absent entirely. Across the stored corpus, **30 of 1549 lines
spoken by somebody standing in the player's own room never reached the player's
view** (1.9%), in seven different chats.

Nothing downstream could catch it. The narrator's dialogue-fidelity check
compares the PROSE against the VIEW, so a line already lost from the view is
one the check agrees is not missing — which is why this survived alongside a
guard built for exactly this failure one stage later.
"""

from __future__ import annotations

import re

from agents.common import _contains_quote, _inject_dialogue, _quote_body


class TestTheFloorItself:
    """The floor is the last thing in the per-perceiver loop: for each line the
    gate delivered at FULL clarity, if the body is no longer in the view, put
    it back."""

    def _floor(self, view, delivered):
        restored = []
        for display, quote, volume, can_see, conducted in delivered:
            body = _quote_body(quote)
            if not body or _contains_quote(view, body):
                continue
            view = _inject_dialogue(view, display, quote, "full", volume,
                                    can_see, conducted=conducted)
            restored.append(body)
        return view, restored

    def test_a_scrubbed_line_comes_back(self):
        delivered = [("The Doctor", '"Okaa Sama? Yeah, I bet I will."',
                      "normal", True, False)]
        scrubbed = "I walk the mossy path. Yeah, I bet I will.\""
        view, restored = self._floor(scrubbed, delivered)
        assert restored == ["Okaa Sama? Yeah, I bet I will."]
        assert "Okaa Sama? Yeah, I bet I will." in view

    def test_a_line_that_survived_is_not_duplicated(self):
        delivered = [("The Doctor", '"Shrine first, then we pick a direction."',
                      "normal", True, False)]
        view = 'The Doctor says: "Shrine first, then we pick a direction."'
        out, restored = self._floor(view, delivered)
        assert restored == []
        assert out.count("Shrine first") == 1

    def test_dialogue_tag_punctuation_does_not_duplicate_the_line(self):
        """Live chat 68: a period in the dialogue log becomes a comma before
        a speech tag; that grammatical change is not a second line."""
        delivered = [("Elyra Voss", '"Lie back."',
                      "normal", True, False)]
        view = '"Lie back," Elyra commands, her voice low.'

        out, restored = self._floor(view, delivered)

        assert restored == []
        assert out == view

    def test_several_lost_lines_all_return(self):
        delivered = [
            ("The Doctor", '"Shrine first, then we pick a direction."',
             "normal", True, False),
            ("The Doctor", '"Saturn\'s rings or those dragons?"',
             "normal", True, False),
            ("The Doctor", '"Your lead."', "normal", True, False),
        ]
        view, restored = self._floor("The forest is unnaturally quiet.", delivered)
        assert len(restored) == 3
        for body in restored:
            assert body in view

    def test_an_unseen_speaker_is_restored_as_a_voice(self):
        """The floor must not upgrade the channel it restores through: a line
        heard without sight goes back as something heard."""
        delivered = [("a voice", '"Who is out there?"', "normal", False, False)]
        view, restored = self._floor("Darkness.", delivered)
        assert restored and "You hear a voice" in view

    def test_volume_survives_the_round_trip(self):
        delivered = [("Tamamo", '"Welcome home."', "mutter", True, False)]
        view, _ = self._floor("The clearing is quiet.", delivered)
        assert "says under their breath" in view


class TestWhatTheFloorDoesNotDo:
    """Three source-placement tests lived here and have been retired.

    They pinned WHERE the heard-line floor sat inside
    `perception_outcome`'s model path: after every scrub, recording only
    full-fidelity lines, warning on every restoration. That path is gone —
    perception composes views from the IR and no model prose is scrubbed —
    so there is no ordering left to assert.

    What they were protecting is now protected upstream instead of
    repaired downstream. The floor existed because a scrub could eat a
    delivered line; the composer's own repair passes are barred from doing
    that (`_strip_self_narration_quote_safe`, and the invented-dialogue
    tripwire no longer edits at all — see
    tests/test_composer_admission_gate.py). Measured after that change:
    same-room line recall 100%, player same-room lines missing 0, against
    the model path's 94.7% and 6.
    """


class TestTypographyCannotSplitOneLine:
    """One spoken line rendered with two typographies is one line.

    Live (chat 69 "Horny Story. ⎇49", turn 63): the model rendered a line
    with U+2011 non-breaking hyphens and curly apostrophes; the floor's
    restore pass then re-injected the same line from the log in ASCII
    punctuation, and the byte-wise `_contains_quote` saw two different
    strings -- so the perceiver was handed the same sentence twice in one
    view.
    """

    def test_a_curly_rendering_contains_its_ascii_line(self):
        view = 'She murmurs, “I‑I can’t stay long.”'
        assert _contains_quote(view, '"I-I can\'t stay long."')

    def test_the_fold_works_in_the_other_direction_too(self):
        view = 'She murmurs, "I-I can\'t stay long."'
        assert _contains_quote(view, '“I‑I can’t stay long.”')

    def test_a_genuinely_different_line_still_reads_as_absent(self):
        view = 'She murmurs, “I‑I can’t stay long.”'
        assert not _contains_quote(view, '"I can stay all night."')
