

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


class TestOneItemWhereAListWasDeclared:
    """Asked for "updates" with exactly one to report, a model returns the
    object rather than a list of one.

    Observed live: a character agent returned a bare object for both
    `mind_model_updates` and `relationship_updates`, and the beat was
    discarded with "value is not a valid list". The singular and the list of
    one mean the same thing, so this is no more ambiguous than accepting a
    structured value where prose was declared.
    """

    def test_a_bare_object_is_accepted_as_a_list_of_one(self):
        from schemas import CharacterOutput
        out = CharacterOutput(
            mind_model_updates={"about_entity": "Mara", "kind": "observation",
                                "claim": "she flinched", "confidence": 0.4})
        assert len(out.mind_model_updates) == 1
        assert out.mind_model_updates[0].about_entity == "Mara"

    def test_a_real_list_is_untouched(self):
        from schemas import CharacterOutput
        out = CharacterOutput(mind_model_updates=[
            {"about_entity": "A", "kind": "observation", "claim": "x"},
            {"about_entity": "B", "kind": "observation", "claim": "y"}])
        assert len(out.mind_model_updates) == 2

    def test_a_string_is_not_silently_wrapped(self):
        """Only an object is unambiguously 'one of these'. A bare string
        where a list of objects was declared is a real disagreement and must
        not be papered over."""
        import pydantic, pytest
        from schemas import CharacterOutput
        with pytest.raises(pydantic.ValidationError):
            CharacterOutput(mind_model_updates="she flinched")


class TestSilenceMustNotAbortTheTurn:
    """Doing nothing is a legitimate thing for a mind to do.

    A character may stand still, stay silent, decline -- and an empty
    `sequence` is how that arrives. `director_resolve` demanded a non-empty
    `resolved_event` unconditionally, so a character's silence could abort
    the whole turn. Observed live three times in one run: empty sequence ->
    the director had nothing to write about -> empty resolved_event -> beat
    discarded. Non-deterministically, too, since the same model narrated "he
    stays where he is; no changes occur" on other beats, which made an
    engine bug look like an unreliable model.
    """

    from schemas import semantic_output_errors as _sem

    def test_an_empty_event_is_allowed_when_nobody_acted(self):
        from schemas import semantic_output_errors
        errs = semantic_output_errors(
            "director_resolve", {"resolved_event": "", "state_diff": {}},
            source_payload={"player_declaration": {"sequence": []},
                            "character_declarations": [{"sequence": []}]})
        assert "resolved_event is empty" not in errs

    def test_an_empty_event_is_still_refused_when_someone_acted(self):
        from schemas import semantic_output_errors
        errs = semantic_output_errors(
            "director_resolve", {"resolved_event": "", "state_diff": {}},
            source_payload={"character_declarations": [
                {"sequence": [{"type": "action", "attempt": "steps east"}]}]})
        assert "resolved_event is empty" in errs

    def test_the_player_acting_alone_still_requires_an_event(self):
        from schemas import semantic_output_errors
        errs = semantic_output_errors(
            "director_resolve", {"resolved_event": "", "state_diff": {}},
            source_payload={"player_declaration": {
                "sequence": [{"type": "speech", "text": "hello"}]}})
        assert "resolved_event is empty" in errs

    def test_a_dice_roll_counts_as_something_happening(self):
        from schemas import semantic_output_errors
        errs = semantic_output_errors(
            "director_resolve", {"resolved_event": "", "state_diff": {}},
            source_payload={"dice_results_final": [{"dc": 12, "roll": 9}]})
        assert "resolved_event is empty" in errs

    def test_state_diff_is_still_required_either_way(self):
        from schemas import semantic_output_errors
        errs = semantic_output_errors(
            "director_resolve", {"resolved_event": ""}, source_payload={})
        assert "state_diff must be an object" in errs


class TestAMapOfItemsIsNotOneItem:
    """A bare dict arrives as two different things needing opposite handling.

    One is a single item. The other is a MAP keyed by name, which models
    reach for when the list is "updates about people":
    {"Mara": {...}, "Vesk": {...}}. Wrapping that yields a one-element list
    whose element is the whole map, failing as
    `mind_model_updates.0.about_entity: field required` -- an error that
    reads like the model omitted a field when we mangled its structure.
    """

    def test_a_map_keyed_by_subject_becomes_a_list_of_items(self):
        from schemas import CharacterOutput
        out = CharacterOutput(mind_model_updates={
            "Mara": {"kind": "observation", "claim": "she flinched"},
            "Vesk": {"kind": "observation", "claim": "he lied"}})
        got = {m.about_entity: m.claim for m in out.mind_model_updates}
        assert got == {"Mara": "she flinched", "Vesk": "he lied"}, (
            "the key IS the subject in this shape")

    def test_a_single_item_is_still_just_wrapped(self):
        from schemas import CharacterOutput
        out = CharacterOutput(mind_model_updates={
            "about_entity": "Mara", "kind": "observation", "claim": "x"})
        assert len(out.mind_model_updates) == 1
        assert out.mind_model_updates[0].about_entity == "Mara"

    def test_an_explicit_subject_is_never_overwritten_by_the_key(self):
        from schemas import CharacterOutput
        out = CharacterOutput(mind_model_updates={
            "the woman in grey": {"about_entity": "Mara", "kind": "observation",
                                  "claim": "x"}})
        assert out.mind_model_updates[0].about_entity == "Mara"

    def test_a_dict_of_non_objects_is_not_a_map_of_items(self):
        """Values that are not objects cannot be items, so this is the
        single-item case however unlike an item it looks."""
        import pydantic, pytest
        from schemas import CharacterOutput
        with pytest.raises(pydantic.ValidationError):
            CharacterOutput(mind_model_updates={"a": 1, "b": 2})


class TestTheKeySlotIsTheItemsOwnRequiredField:
    """Which slot a map's key belongs in must come from the item, not a
    guessed list of field names.

    A hardcoded about_entity/name/entity/id looked general and was not: it
    missed `belief` on BeliefUpdate and `cue` on AssociationUpdate, so a map
    keyed by belief text dropped the text and failed as
    `belief_updates.0.belief: field required` -- the very error the map
    handling existed to prevent, one model over. Seen live one resume after
    the first version shipped.
    """

    def test_belief_updates_keyed_by_the_belief(self):
        from schemas import CharacterOutput
        out = CharacterOutput(belief_updates={
            "the bridge is watched": {"confidence": 0.6},
            "Mara lied about the ledger": {"confidence": 0.8}})
        assert [b.belief for b in out.belief_updates] == [
            "the bridge is watched", "Mara lied about the ledger"]

    def test_association_updates_keyed_by_the_cue(self):
        from schemas import CharacterOutput
        out = CharacterOutput(association_updates={
            "boots on wet stone": {"amount": 0.2}})
        assert out.association_updates[0].cue == "boots on wet stone"

    def test_mind_models_still_keyed_by_the_subject(self):
        """The case the first version did handle must keep working."""
        from schemas import CharacterOutput
        out = CharacterOutput(mind_model_updates={
            "Mara": {"kind": "observation", "claim": "she flinched"}})
        assert out.mind_model_updates[0].about_entity == "Mara"

    def test_an_explicit_value_still_wins_over_the_key(self):
        from schemas import CharacterOutput
        out = CharacterOutput(belief_updates={
            "shorthand": {"belief": "the bridge is watched", "confidence": 0.6}})
        assert out.belief_updates[0].belief == "the bridge is watched"


class TestAFailedBeatCarriesItsEvidence:
    """A validation error names the field that was wrong and says nothing
    about the shape that was sent.

    "about_entity: field required" reads as an omission whether the model
    omitted the field, nested it, or sent a map keyed by subject that we then
    mangled into a one-element list. Twice the same failure was
    undiagnosable, because the raw response died inside
    complete_validated_json -- and both times the fix had to be inferred from
    the beats either side of it.
    """

    def test_the_raw_response_is_attached_to_the_failure(self, monkeypatch):
        import llm_quality
        monkeypatch.setattr(
            llm_quality, "chat_complete",
            lambda *a, **k: '{"mind_model_updates": {"Mara": {"nope": 1}}}')
        import pytest
        with pytest.raises(RuntimeError) as exc:
            llm_quality.complete_validated_json(
                role="character_mid", step_key="character", system="sys",
                payload={"x": 1}, repair_attempts=0)
        msg = str(exc.value)
        assert "model sent:" in msg, "the shape that failed must be visible"
        assert "Mara" in msg, "and it must be the ACTUAL response"

    def test_the_evidence_is_bounded(self, monkeypatch):
        """A whole reasoning-model response in an exception message is not a
        diagnostic, it is a denial of service on the log."""
        import llm_quality
        monkeypatch.setattr(
            llm_quality, "chat_complete",
            lambda *a, **k: '{"sequence": "' + "x" * 20000 + '"}')
        import pytest
        with pytest.raises(RuntimeError) as exc:
            llm_quality.complete_validated_json(
                role="character_mid", step_key="character", system="sys",
                payload={"x": 1}, repair_attempts=0)
        assert len(str(exc.value)) < 1500


class TestReasoningIsKeptButQuarantined:
    """A thinking model's trace is worth keeping and must never be content.

    It is the model talking to itself: it has been through none of the
    validation the answer has, and nothing in the fiction has ratified it. So
    it is stored beside the output, offered behind a disclosure in the
    pipeline view, carried across a branch (same machine, same run), and
    deliberately NOT written into a portable archive.
    """

    def test_it_is_stored_beside_the_output(self, temp_db):
        import providers
        from agents.storage import save_step
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", 0.0))
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 0, "", 0.0))
        token = providers.last_reasoning.set("first I check the north door")
        try:
            save_step(tid, "character:1", "Vesk", 1, {"sequence": []})
        finally:
            providers.last_reasoning.reset(token)
        row = temp_db.q(
            "SELECT v.reasoning FROM variants v JOIN steps s ON v.step_id=s.id "
            "WHERE s.turn_id=?", (tid,), one=True)
        assert row["reasoning"] == "first I check the north door"

    def test_a_model_without_one_stores_empty_not_null(self, temp_db):
        import providers
        from agents.storage import save_step
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("T", "", 0.0))
        tid = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)", (chat_id, 0, "", 0.0))
        token = providers.last_reasoning.set(None)
        try:
            save_step(tid, "narrator", "Narrator", 1, {"prose": "x"})
        finally:
            providers.last_reasoning.reset(token)
        row = temp_db.q(
            "SELECT v.reasoning FROM variants v JOIN steps s ON v.step_id=s.id "
            "WHERE s.turn_id=?", (tid,), one=True)
        assert row["reasoning"] == ""

    def test_the_capture_handles_every_shape_a_provider_sends(self):
        import providers
        for message, expected in (
            ({"reasoning": "plain"}, "plain"),
            ({"reasoning_content": "deepseek style"}, "deepseek style"),
            ({"reasoning": [{"text": "a"}, {"text": "b"}]}, "a\nb"),
            ({"reasoning": ""}, None),
            ({}, None),
            (None, None),
        ):
            token = providers.last_reasoning.set("stale")
            try:
                providers._capture_reasoning(message)
                got = providers.last_reasoning.get()
            finally:
                providers.last_reasoning.reset(token)
            if message is None:
                continue          # junk leaves the previous value alone
            assert got == expected, f"{message!r} -> {got!r}"


class TestReasoningSurvivesTheStreamingPath:
    """The pipeline runs on the STREAMING path, so that is the one that had
    to capture reasoning -- and it was the one that did not.

    Capture was added to the non-streaming branch only. Every engine turn
    sets a token sink for the live UI and therefore streams, so the feature
    was dead exactly where it was meant to be used, and it looked from the
    outside like a model that does not expose a trace. Reasoning arrives on
    its own delta key and never in `content`.
    """

    def _stream(self, chunks):
        import json as _j
        return [b"data: " + _j.dumps(c).encode() for c in chunks] + [b"data: [DONE]"]

    def test_reasoning_deltas_are_accumulated_and_content_is_not_polluted(
            self, monkeypatch):
        import providers
        sent = []
        chunks = [
            {"choices": [{"delta": {"reasoning": "first I look "}}]},
            {"choices": [{"delta": {"reasoning": "north."}}]},
            {"choices": [{"delta": {"content": '{"ok":'}}]},
            {"choices": [{"delta": {"content": "1}"}}]},
        ]

        class FakeResp:
            status_code = 200
            def iter_lines(self):
                return iter(self._lines)
            def __enter__(self): return self
            def __exit__(self, *a): return False
        resp = FakeResp(); resp._lines = self._stream(chunks)
        monkeypatch.setattr(providers, "_session",
                            lambda: type("S", (), {"post": lambda *a, **k: resp})())
        token = providers.last_reasoning.set(None)
        try:
            out = providers._sse_openai("u", {}, {}, sent.append)
            assert out == '{"ok":1}', "content must be unchanged"
            assert providers.last_reasoning.get() == "first I look north."
        finally:
            providers.last_reasoning.reset(token)
        assert "".join(sent) == '{"ok":1}', (
            "reasoning must never reach the sink -- that is player-facing prose")
