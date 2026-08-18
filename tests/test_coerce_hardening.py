"""Batch A/E hardening: coerce-vs-crash for numeric bounds, dialogue_log,
dice, other_players volumes; tolerant character-sheet floats; strict_json_parse
prose recovery; ToM cap consistency; provider network-retry classification."""

from __future__ import annotations

import json

import pytest

from llm.schemas import (
    validate_llm_output_strict, MindHypothesis, RelationshipUpdate,
    InteractionControl, OUTPUT_EXAMPLES,
)


# ---- numeric-bounds clamping (was: hard-reject -> crashed the character step) ----

def test_relationship_delta_clamps_instead_of_rejecting():
    ru = RelationshipUpdate(target_entity="x", trust_delta=0.5, warmth_delta=-3, fear_delta="high")
    assert ru.trust_delta == 0.2 and ru.warmth_delta == -0.2 and ru.fear_delta == 0.0


def test_confidence_and_urgency_and_salience_clamp():
    assert MindHypothesis(about_entity="x", kind="goal", claim="c", confidence=85).confidence == 1.0
    assert MindHypothesis(about_entity="x", kind="goal", claim="c", confidence="high").confidence == 0.5
    assert InteractionControl(urgency=2).urgency == 1.0


def test_character_step_with_out_of_bounds_numbers_validates():
    payload = {
        "sequence": [], "interaction": {"urgency": 5},
        "relationship_updates": [{"target_entity": "y", "trust_delta": 0.9}],
        "mind_model_updates": [{"about_entity": "y", "kind": "goal", "claim": "c", "confidence": 42}],
        "salience": 99,
    }
    report = validate_llm_output_strict("character", payload)
    assert report.valid, report.errors
    assert report.output["relationship_updates"][0]["trust_delta"] == 0.2
    assert report.output["mind_model_updates"][0]["confidence"] == 1.0
    assert report.output["salience"] == 1.0


# ---- dialogue_log alias / string coercion (was: crash or silent drop) ----

def test_dialogue_log_alias_and_string_lines_survive():
    payload = {
        "resolved_event": "e", "state_diff": {},
        "dialogue_log": [
            {"speaker": "Barkeep", "quote": "Aye."},          # alias key
            "Guard: 'Move along.'",                            # bare string
            "A distant bell.",                                  # unattributed string
        ],
    }
    report = validate_llm_output_strict("director_resolve", payload)
    assert report.valid, report.errors
    dl = report.output["dialogue_log"]
    quotes = [e["exact_quote"] for e in dl]
    assert "Aye." in quotes
    assert any("Move along" in q for q in quotes)
    assert any("distant bell" in q for q in quotes)


# ---- FlowPlan.dice tolerates a missing key ----

def test_interpret_dice_missing_key_does_not_crash():
    payload = {"kind": "action", "sequence": [], "flow": {"dice": [{"actor": "player", "attempt": "stab"}]}}
    report = validate_llm_output_strict("director_interpret", payload)
    assert report.valid, report.errors


# ---- other_players volumes normalized + null tolerated ----

def test_other_players_volume_normalized():
    payload = {"kind": "mixed", "sequence": [], "flow": {},
               "other_players": {"7": {"speech": "hi", "speech_volume": "quietly",
                                       "sequence": [{"type": "speech", "text": "psst", "volume": "hushed"}]}}}
    report = validate_llm_output_strict("director_interpret", payload)
    assert report.valid, report.errors
    op = report.output["other_players"]["7"]
    assert op["speech_volume"] in ("whisper", "mutter", "normal", "loud", "shout")


def test_other_players_null_tolerated():
    payload = {"kind": "dialogue", "sequence": [], "flow": {}, "other_players": None}
    report = validate_llm_output_strict("director_interpret", payload)
    assert report.valid, report.errors


# ---- character-sheet tolerant floats (was: 500 on import / crash every turn) ----

def test_normalize_character_data_tolerates_nonnumeric():
    from story.character_schema import normalize_character_data, character_temperature, character_name
    sheet = {
        "identity": {"name": "Bad"},
        "simulation": {"temperature": "warm"},
        "initial_state": {"mood": {"label": "x", "valence": None, "arousal": "very"}},
        "social": {"baseline_stances": {"unknown_person": {"trust": None}}},
    }
    norm = normalize_character_data(sheet)             # must not raise
    assert character_name(norm) == "Bad"
    assert isinstance(character_temperature(norm), float)


# ---- strict_json_parse recovers prose-wrapped JSON ----

def test_strict_json_parse_recovers_prose_wrapped():
    from llm.llm_quality import strict_json_parse
    assert strict_json_parse('Here is the JSON: {"a": 1} hope that helps') == {"a": 1}
    assert strict_json_parse('{"a": {"b": 2}}\n\nlet me know') == {"a": {"b": 2}}


# ---- ToM cap consistency for off-enum kinds ----

def test_tom_cap_offenum_kind_uses_default_kind():
    from mind.theory_of_mind import cap_mind_model_updates, _kind_or_default, _TOM_CONFIDENCE_CAPS
    out = cap_mind_model_updates([{"about_entity": "a", "kind": "suspicion", "claim": "c", "confidence": 1.0}])
    assert out[0]["confidence"] == _TOM_CONFIDENCE_CAPS[_kind_or_default("suspicion")]


# ---- provider network-retry classification ----

def test_requests_network_errors_classified_retryable():
    import requests.exceptions as rex
    from llm.providers import _classify_error, _should_retry, DEFAULT_RETRY
    for exc in (rex.ConnectionError("x"), rex.ReadTimeout("x"),
                rex.ChunkedEncodingError("x"), rex.ConnectTimeout("x")):
        e = _classify_error(exc)
        assert e.retryable, f"{type(exc).__name__} should be retryable"
        assert _should_retry(e, 0, DEFAULT_RETRY)


# ---- background_react now has an output example (was: repair steered to {}) ----

def test_background_react_output_example_present():
    ex = OUTPUT_EXAMPLES.get("background_react")
    assert ex and ex.get("dialogue_log_entry", {}).get("exact_quote")


def test_latent_string_and_custom_summary_separates_outfit():
    from story.character_schema import normalize_character_data
    sheet = {"identity": {"name": "Merc"}, "embodiment": {
        "visible": {"summary": "A scarred mercenary."},
        "hair": "silver", "clothing": "red cloak", "latent": ["telepathy", {"capability": "x"}]}}
    norm = normalize_character_data(sheet)
    summ = norm["embodiment"]["visible"]["summary"]
    assert "scarred mercenary" in summ and "silver" in summ
    assert "red cloak" not in summ
    assert norm["initial_outfit"]["wearing"] == ["red cloak"]
    caps = [l.get("capability") for l in norm["embodiment"]["latent"]]
    assert "telepathy" in caps and "x" in caps


class TestCandidateResponseShape:
    """A character turn must not be lost to the SHAPE of one weighed option.

    `response` is the prose of an option the character considered, but "the
    candidate response" reads just as naturally as the act itself, and models
    emit it structurally. Found live: inception/mercury-2 returned a sequence
    element there on roughly 40% of beats, and each one failed the entire
    character step -- the beat lost, the character inert, the only signal a
    type error naming a field the author never sees.
    """

    def _one(self, raw_response):
        from llm.schemas import validate_llm_output
        out, _ = validate_llm_output("character", {
            "name": "V", "sequence": [],
            "response_candidates": [{"response": raw_response}]})
        return out["response_candidates"][0]["response"]

    def test_a_sequence_element_reduces_to_its_surface(self):
        """The observable is preferred over the attempt: these candidates are
        weighed, not enacted, and the observable is what anyone would ever
        actually be shown."""
        assert self._one({
            "type": "action", "attempt": "step through the nearest doorway",
            "observable": "steps forward through the doorway",
        }) == "steps forward through the doorway"

    def test_it_falls_back_through_the_other_prose_keys(self):
        assert self._one({"type": "action", "attempt": "wait here"}) == "wait here"
        assert self._one({"text": "say nothing"}) == "say nothing"

    def test_a_plain_string_is_untouched(self):
        assert self._one("just wait") == "just wait"

    def test_a_list_joins_rather_than_failing(self):
        assert self._one(["step out", "look back"]) == "step out; look back"

    def test_an_empty_object_degrades_to_empty_not_an_error(self):
        assert self._one({}) == ""
        assert self._one({"type": "action"}) == ""

    def test_the_rest_of_the_turn_survives(self):
        """The point of the coercion: the beat lives."""
        from llm.schemas import validate_llm_output
        out, _ = validate_llm_output("character", {
            "name": "V",
            "sequence": [{"type": "action", "attempt": "walk on",
                          "observable": "walks on"}],
            "response_candidates": [
                {"response": {"observable": "steps forward"}, "selected": True}],
        })
        assert out["sequence"][0]["attempt"] == "walk on"
        assert out["response_candidates"][0]["selected"] is True


class TestEmptyChoicesIsTransport:
    """A 200 carrying no `choices` is the provider not answering, not the model
    answering badly.

    Observed live at ~2.6% of beats on one endpoint. It surfaced as "'choices'"
    inside a JSON-validation error that blamed the model, and a KeyError there
    aborts the beat -- which reads to a player as the character having nothing
    to say. Retried as the transport failure it is.
    """

    def test_it_is_flagged_retryable(self):
        from llm import providers
        err = providers.LLMError("x: response carried no choices ({})", 200, True)
        assert err.retryable is True

    def test_there_is_no_raw_subscript_left_to_win(self):
        """Originally: the raise must precede the subscript, or the KeyError
        wins. The subscript is now gone entirely -- every read of the answer
        goes through `_message_content`, which turns a missing message, a
        missing content key and an empty string into named, retryable
        failures. Same invariant, enforced by absence rather than ordering.

        The sibling case cost a live specialist call: a reasoning model
        returned `reasoning` with no `content`, and the KeyError surfaced as
        "all providers failed (last provider error: 'content')" -- a parser
        bug wearing a provider's clothes.
        """
        import inspect

        from llm import providers

        src = inspect.getsource(providers)
        assert '["message"]["content"]' not in src, (
            "a raw content subscript is back; route it through "
            "_message_content so a missing answer stays retryable")
        assert src.index("carried no choices") < src.index(
            "def _message_content")


class TestLenientStrFields:
    """One coercion for a whole failure family.

    Five separate crashes in a single session were the same shape: a field typed
    `str` receiving a structured object, discarding the ENTIRE stage output and
    costing a beat. Roughly ninety more str-typed fields carry the same
    exposure, so the coercion lives once on a base every schema model inherits
    rather than being added field-by-field as each one crashes.
    """

    def test_a_dict_reduces_to_the_prose_it_contains(self):
        from llm.schemas import validate_llm_output
        out, _ = validate_llm_output("director_resolve", {
            "resolved_event": {"text": "Vesk walks on."},
            "dialogue_log": [], "state_diff": {}})
        assert out["resolved_event"] == "Vesk walks on."

    def test_a_list_joins(self):
        from llm.schemas import validate_llm_output
        out, _ = validate_llm_output("director_resolve", {
            "resolved_event": "x", "summary": ["A step", "deeper"],
            "dialogue_log": [], "state_diff": {}})
        assert out["summary"] == "A step; deeper"

    def test_the_last_open_crash_of_the_family(self):
        """changes_asserted.change was still failing live when this landed."""
        from llm.schemas import validate_llm_output
        out, _ = validate_llm_output("director_resolve", {
            "resolved_event": "x", "dialogue_log": [], "state_diff": {},
            "changes_asserted": [
                {"change": {"kind": "moved", "detail": "door opened"}}]})
        assert out["changes_asserted"][0]["change"] == "door opened"

    def test_a_dict_with_no_prose_key_still_yields_something(self):
        from llm.schemas import _flatten_to_text
        assert _flatten_to_text({"kind": "moved", "n": 3}) == "moved; 3"

    def test_it_only_fires_on_str_fields(self):
        """A structured value bound for a structured field must pass through
        untouched, or this masks real type errors instead of fixing one."""
        from llm.schemas import validate_llm_output
        out, _ = validate_llm_output("director_resolve", {
            "resolved_event": "x", "dialogue_log": [], "state_diff": {},
            "obligations": [{"id": "o1", "text": "return the letter"}]})
        assert isinstance(out["state_diff"], dict)
        assert isinstance(out["obligations"], list)

    def test_plain_strings_are_untouched(self):
        from llm.schemas import _flatten_to_text
        assert _flatten_to_text("already prose") == "already prose"
        assert _flatten_to_text(7) == 7
