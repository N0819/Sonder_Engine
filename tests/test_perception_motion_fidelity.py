"""Perception may narrow what a body knows. It may not reverse it."""

from __future__ import annotations

import types

from agents.perception import _inverted_motion_check


def _ctx():
    return types.SimpleNamespace(warnings=[])


class TestAViewMayNotReverseTheResolvedDirection:
    """Perception's structured observations are re-derived from the scrubbed
    prose view precisely so a second representation cannot widen the
    information budget. Nothing checked the PROSE against the objective event
    it is supposed to be a view OF, so a model that rewrote the beat was
    invisible.

    Chat 52's last beat, all three stages on the active variants:

        declared:  "lowering her steadily toward exposed groin"
        resolved:  "begins to lower her hand steadily toward the parted robe"
        view:      "lifting you to eye level"

    The narrator renders the view, not the event, so it had no lowering to
    describe and the beat the story had committed to never reached the page.
    Reported as "her character action is not being passed to perception", which
    is exactly what it was.
    """

    RESOLVED = ("She continues the slow roll of her thumb against the tiny "
                "kitsune's back and begins to lower her hand steadily toward "
                "the parted robe and hiked skirt.")

    def test_it_catches_the_real_inversion(self):
        ctx = _ctx()
        _inverted_motion_check(
            ctx, "perception_outcome",
            {"player": "You feel a firm forefinger gripping your tiny body, "
                       "lifting you to eye level, while a thumb rolls slowly."},
            self.RESOLVED)
        assert len(ctx.warnings) == 1
        assert "reversed a physical direction" in ctx.warnings[0]

    def test_a_faithful_view_is_silent(self):
        ctx = _ctx()
        _inverted_motion_check(
            ctx, "perception_outcome",
            {"player": "The hand lowers you steadily toward her lap."},
            self.RESOLVED)
        assert ctx.warnings == []

    def test_a_view_that_simply_omits_the_motion_is_silent(self):
        """Narrowing is perception's JOB -- a view that does not mention the
        motion at all has not contradicted anything."""
        ctx = _ctx()
        _inverted_motion_check(
            ctx, "perception_outcome",
            {"47": "The room is dim. A thumb rolls against your back."},
            self.RESOLVED)
        assert ctx.warnings == []

    def test_a_beat_containing_both_directions_is_never_flagged(self):
        """One body rises while another is set down: no contradiction, and the
        check must not invent one."""
        ctx = _ctx()
        _inverted_motion_check(
            ctx, "perception_outcome",
            {"player": "She lifts you clear as the bucket lowers into the well."},
            "She lifts the fox clear while lowering the bucket into the well.")
        assert ctx.warnings == []

    def test_a_view_naming_both_is_not_flagged(self):
        """The view says lowering AND raising -- it has not replaced one with
        the other, so this tripwire stays out of it."""
        ctx = _ctx()
        _inverted_motion_check(
            ctx, "perception_outcome",
            {"player": "She lifts you a little, then lowers you again."},
            self.RESOLVED)
        assert ctx.warnings == []

    def test_the_reverse_direction_is_caught_too(self):
        ctx = _ctx()
        _inverted_motion_check(
            ctx, "perception_outcome",
            {"player": "The hand lowers you toward the floor."},
            "He raises the lantern above his head.")
        assert len(ctx.warnings) == 1

    def test_an_empty_event_or_view_does_nothing(self):
        ctx = _ctx()
        _inverted_motion_check(ctx, "perception_outcome", {"player": "x"}, "")
        _inverted_motion_check(ctx, "perception_outcome", {"player": ""}, "lowers")
        _inverted_motion_check(ctx, "perception_outcome", {}, "lowers")
        assert ctx.warnings == []

    def test_it_names_the_perceiver(self):
        """Both views were wrong on the live turn; a warning that does not say
        whose is not actionable."""
        ctx = _ctx()
        _inverted_motion_check(
            ctx, "perception_outcome",
            {"player": "lifting you to eye level", "47": "lifting her upward"},
            self.RESOLVED)
        assert len(ctx.warnings) == 2
        assert any("for player" in w for w in ctx.warnings)
        assert any("for 47" in w for w in ctx.warnings)
