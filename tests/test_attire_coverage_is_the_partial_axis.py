"""A coverage claim must not undress a body nobody touched.

The class, measured in chat 77 ("The Doctor — Hinami new") turn 8: the body
specialist emitted a `coverage` block naming every garment of BOTH characters
against every region it covers, with empty zone lists --

    "lightweight travel jacket": {"torso": [], "arms": []}
    "light blue dress shirt":    {"torso": [], "waist": [], "groin": [], "legs": []}

-- which is what a RESTATEMENT of the wardrobe looks like when the model puts
the regions in the keys and leaves the zones, which are the actual payload,
empty. An empty list means "displaced off this region" (`apply_coverage_changes`
says so), so the engine did what it was told: six garments and five garments to
"displaced off", on a beat where the two of them were talking. Both narrated as
bare for two beats while every garment record still read `state: worn`, and not
one warning was raised in thirteen turns.

THE DISCRIMINATOR IS NOT "empties everything it covers". That was the first fix
attempted here and the suite refused it, correctly: trousers around the ankles
are worn and cover nothing, the ladder is built to complete a removal from that
state in one rung, and `test_attire_displacement.py` pins both. One garment off
everything it covers is an ordinary, designed state.

The rule that holds is about the BODY, not the garment: a claim that would leave
someone covered NOWHERE, on a beat whose words remove nothing, is a restatement
rather than a change. Nobody undresses completely by displacement.
"""

from __future__ import annotations

import pytest

from story import attire as attire_model


def _wardrobe():
    """A dressed body: a jacket over the torso and arms, shorts below."""
    return attire_model.normalize_regions({"regions": {
        "torso": {"garments": [{"name": "lightweight travel jacket",
                                "state": "worn", "covers": ["torso", "arms"]}]},
        "arms": {"garments": [{"name": "lightweight travel jacket",
                               "state": "worn", "covers": ["torso", "arms"]}]},
        "groin": {"garments": [{"name": "travel shorts", "state": "worn",
                                "covers": ["groin", "legs"]}]},
        "legs": {"garments": [{"name": "travel shorts", "state": "worn",
                               "covers": ["groin", "legs"]}]},
    }})


class TestTheWholeWardrobeAtOnceIsRefused:
    def test_the_live_turn_8_block_would_bare_the_body(self):
        """Every garment, every region, all empty -- the shape that shipped."""
        assert attire_model.coverage_would_bare_the_body(_wardrobe(), {
            "lightweight travel jacket": {"torso": [], "arms": []},
            "travel shorts": {"groin": [], "legs": []},
        }) is True

    def test_an_already_bare_body_is_not_reported(self):
        """Nothing was covered, so nothing is being taken -- the guard must not
        fire on a body with no wardrobe to strip."""
        assert attire_model.coverage_would_bare_the_body(
            attire_model.normalize_regions({"regions": {}}),
            {"anything": {"torso": []}}) is False


class TestOneGarmentDisplacedIsOrdinary:
    """The designed state the first attempt at this fix broke. These are the
    cases `test_attire_displacement.py` owns; they are restated here because
    they are what bounds the guard."""

    def test_trousers_at_the_ankles_do_not_bare_a_dressed_body(self):
        assert attire_model.coverage_would_bare_the_body(
            _wardrobe(), {"travel shorts": {"groin": [], "legs": []}}) is False

    def test_a_lone_garment_off_everything_it_covers_still_applies(self):
        regions = attire_model.normalize_regions({"regions": {
            "legs": {"garments": [{"name": "travel shorts", "state": "worn",
                                   "covers": ["legs", "groin"]}]}}})
        after, notes = attire_model.apply_coverage_changes(
            regions, {"travel shorts": {"legs": [], "groin": []}})

        assert attire_model.covered_regions(after) == []
        assert {g["state"] for e in after.values()
                for g in e["garments"]} == {"worn"}
        assert not notes

    def test_partial_displacement_is_untouched(self):
        after, notes = attire_model.apply_coverage_changes(
            _wardrobe(), {"lightweight travel jacket": {"arms": []}})

        assert "torso" in attire_model.covered_regions(after)
        assert "arms" in attire_model.exposed_regions(after)
        assert not notes


class TestARealRemovalStillEscalates:
    """The escalation path is how a total emptying is allowed to mean what it
    says -- through `remove`, so the ladder and the shed-object minting apply."""

    def test_removal_words_escalate_the_block(self):
        assert attire_model.coverage_removal_escalations(
            ["She pulls off her lightweight travel jacket and drops it."],
            {"lightweight travel jacket": {"torso": [], "arms": []}},
            _wardrobe()) == ["lightweight travel jacket"]

    def test_an_ordinary_beat_escalates_nothing(self):
        """Turn 8's beat: nobody touched any clothing. This is the input that
        must not become a removal by either route."""
        assert attire_model.coverage_removal_escalations(
            ['"Old girl?" you ask him curiously.'],
            {"lightweight travel jacket": {"torso": [], "arms": []}},
            _wardrobe()) == []


class TestTheDetector:
    def test_total_emptyings_are_reported_by_handle(self):
        assert attire_model.coverage_total_emptyings(
            {"travel shorts": {"groin": [], "legs": []}},
            _wardrobe()) == ["travel shorts"]

    def test_a_partial_emptying_is_not_a_total_one(self):
        assert attire_model.coverage_total_emptyings(
            {"lightweight travel jacket": {"arms": []}}, _wardrobe()) == []

    def test_an_unresolvable_handle_is_not_reported(self):
        assert attire_model.coverage_total_emptyings(
            {"a garment nobody is wearing": {"torso": []}}, _wardrobe()) == []


class TestTheCommitSeam:
    def test_the_guard_runs_for_every_body_not_only_decisive_ones(self):
        """The gate that let this through. The block was skipped entirely
        unless the body had already done something decisive that beat -- so on
        an ordinary beat a strip was neither escalated NOR examined. The
        substantive test (`removal_directed_at`) lives inside
        `coverage_removal_escalations`; the outer gate only hid it.
        """
        import inspect

        from persist import commit_attire

        source = inspect.getsource(commit_attire)
        start = source.index('_coverage = (d.get("coverage")')
        block = source[start:start + 3000]

        assert "if _coverage:" in block
        assert "if _coverage and name in _decisive_names:" not in source
        assert "coverage_would_bare_the_body" in block
        assert "add_warning" in block
