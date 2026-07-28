

class TestNullMeansOmitted:
    """`null` is the natural encoding of absence, and models reach for it.

    Observed live: a character agent on arcee-ai/trinity-large-thinking
    returned `"norm_conflict": null` -- there was no norm conflict -- and the
    entire beat was discarded with `norm_conflict: none is not an allowed
    value`. The field's own default is `""`, which means the same thing. The
    beat was thrown away over spelling, and a discarded beat in a navigation
    run reads afterwards as the model failing to navigate.
    """

    def test_null_on_an_optional_field_falls_back_to_its_default(self):
        from schemas import ResponseCandidate
        c = ResponseCandidate(response="step east", norm_conflict=None)
        assert c.norm_conflict == ""

    def test_null_uses_the_default_factory_for_containers(self):
        from schemas import ResponseCandidate
        c = ResponseCandidate(response="step east", serves=None)
        assert c.serves == []

    def test_null_works_for_numbers_and_flags_too(self):
        from schemas import ResponseCandidate
        c = ResponseCandidate(response="x", risk=None, selected=None)
        assert c.risk == 0.0 and c.selected is False

    def test_a_field_that_allows_none_keeps_it(self):
        """There None is a real value, not an omission, and overwriting it
        would be inventing content rather than tolerating a spelling."""
        from schemas import FictionFrame
        assert FictionFrame(location_id=None).location_id is None

    def test_a_required_field_still_fails_loudly(self):
        """Inventing a value for something the model was obliged to supply
        would hide the real error behind a plausible default."""
        import pydantic
        import pytest
        from schemas import CausalRegime
        with pytest.raises(pydantic.ValidationError):
            CausalRegime(regime_id=None)
