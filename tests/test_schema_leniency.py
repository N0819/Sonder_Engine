

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


class TestTheEngineIsAsLenientOnEitherPydantic:
    """The tolerance must not depend on which Pydantic happens to be installed.

    `schemas.py` supports both majors, and they disagree about a bare number in
    a `str` field: 1.x coerced it to its text, 2.x refuses it and the beat is
    discarded over `response: Input should be a valid string`. Left to the
    installed version, the same engine is measurably more brittle on one
    machine than another, and the difference surfaces as an unreliable model
    rather than as a dependency difference.

    This is the same reason the import of `pydantic.fields.SHAPE_LIST` was a
    defect and not a detail: a v1-only internal decided whether a character's
    beat survived, and the dev machine could not see it.
    """

    def test_a_number_where_prose_was_declared_becomes_its_text(self):
        from schemas import ResponseCandidate
        assert ResponseCandidate(response=5).response == "5"
        assert ResponseCandidate(response=0.5).response == "0.5"

    def test_a_flag_is_text_too_since_a_bool_is_an_int(self):
        from schemas import ResponseCandidate
        assert ResponseCandidate(response=True).response == "True"

    def test_a_number_is_untouched_where_a_number_was_declared(self):
        """Only a `str` field has no invariant a number violates."""
        from schemas import ResponseCandidate
        assert ResponseCandidate(response="x", risk=0.25).risk == 0.25


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
        # Stubbing the model is not enough: the retry path asks how many
        # candidates the role has, and that reads `agent_models` from the
        # settings table. Fast-tier tests are database-independent, so the
        # count comes from here (as tests/test_strict_stage_validation.py does).
        monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
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
        monkeypatch.setattr(llm_quality, "role_candidate_count", lambda role: 1)
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


class TestNothingToReportWhereAnObjectWasDeclared:
    """`[]` and `""` are how a model spells "nothing to report" for a field
    that happens to be an object.

    Pydantic 1 agreed with it for free -- `dict([])` and `dict("")` are both
    `{}` -- so every dict- and model-typed field in the engine accepted the
    wrong spelling on 1.x and none of them did on 2.x. It is not a
    per-field cost either: `validate_llm_output` returns the UNNORMALIZED
    payload when validation fails, so one `"appraisal": []` also costs the
    step every default, flatten and wrap the rest of the leniency layer
    would have applied. `_coerce_empty_list_to_dict` had already been
    written for six named state_diff/scene_patch keys after this crashed a
    live turn; the field's own declaration says which fields need it.
    """

    def test_an_empty_list_where_a_nested_model_was_declared(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output(
            "character", {"response": "hm", "appraisal": []})
        assert warnings == []
        assert out["appraisal"]["novelty"] == 0.0

    def test_an_empty_string_reads_the_same_way(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output(
            "character", {"response": "hm", "interaction": ""})
        assert warnings == []
        assert out["interaction"]["addresses"] == []

    def test_an_empty_list_where_a_dict_was_declared(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output("director_spatial", {"positions": []})
        assert warnings == []
        assert out["positions"] == {}

    def test_a_nested_dict_value_may_be_empty_too(self):
        """The value of a `dict[str, Model]` is not a field of anything, so
        no validator reaches it -- this is the only place it can be
        tolerated."""
        from schemas import validate_llm_output
        out, warnings = validate_llm_output(
            "director_resolve", {"state_diff": {"rooms": {"cellar": []}}})
        assert warnings == []
        assert out["state_diff"]["rooms"]["cellar"]["name"] == ""

    def test_an_empty_string_where_a_list_was_declared(self):
        """The mirror of the same spelling. Seen live on
        `lore_ops[].knowledge_locations: ""`, which cost the mapping
        commit -- on both majors, since neither ever accepted it."""
        from schemas import validate_llm_output
        out, warnings = validate_llm_output("mapping_commit", {"lore_ops": [
            {"op": "create", "content": "c", "knowledge_locations": ""}]})
        assert warnings == []
        assert out["lore_ops"][0]["knowledge_locations"] == []

    def test_an_empty_object_where_a_list_was_declared(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output("mapping_commit", {"lore_ops": [
            {"op": "create", "content": "c", "knowledge_locations": {}}]})
        assert warnings == []
        assert out["lore_ops"][0]["knowledge_locations"] == []

    def test_a_non_empty_list_is_still_a_real_disagreement(self):
        """Only the empty spellings mean "nothing". A populated list where an
        object was declared is a genuine mismatch and must not be guessed at.
        """
        from schemas import validate_llm_output
        _, warnings = validate_llm_output(
            "director_spatial", {"positions": [{"observer": "Mara"}]})
        assert warnings


class TestListElementsAndDictValuesAreCoercedToo:
    """A list element and a dict value are not fields, so the per-field
    validator never sees them.

    Pydantic 1 coerced them itself, element by element (`[1, 2]` ->
    `["1", "2"]`), and 2.x fails the whole step over `dialogue_order.0:
    Input should be a valid string`. That is a model answering with room
    NUMBERS instead of room names costing a beat -- and costing it only on
    one of the two supported majors.
    """

    def test_numbers_in_a_list_of_prose_become_their_text(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output(
            "director_resolve", {"dialogue_order": [1, 2]})
        assert warnings == []
        assert out["dialogue_order"] == ["1", "2"]

    def test_numbers_in_a_dict_of_prose_become_their_text(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output(
            "director_resolve", {"state_diff": {"positions": {"Kara": 3}}})
        assert warnings == []
        assert out["state_diff"]["positions"]["Kara"] == "3"

    def test_a_fractional_number_where_a_count_was_declared_truncates(self):
        """Pydantic 1's own truncation, kept rather than discovered: a
        fractional book id is still pointing at a book."""
        from schemas import validate_llm_output
        out, warnings = validate_llm_output(
            "mapping_stage", {"relevant_books": [12.5]})
        assert warnings == []
        assert out["relevant_books"] == [12]

    def test_a_whole_float_is_a_count_on_either_major(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output(
            "mapping_stage", {"relevant_books": [12.0]})
        assert warnings == []
        assert out["relevant_books"] == [12]

    def test_prose_in_a_list_of_prose_is_untouched(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output(
            "director_resolve", {"dialogue_order": ["Mara", "Vesk"]})
        assert warnings == []
        assert out["dialogue_order"] == ["Mara", "Vesk"]


class TestStagedLoreContentIsProse:
    """A drafted lore entry has to actually be text by the time anything
    reads it.

    `staged_lore` is declared `list[dict]`, so nothing checks inside an
    entry -- and a model asked to draft an entry about a room will sometimes
    return the entry as an object instead of the paragraph the prompt asks
    for. Observed live on an opening turn: `_room_notes_from_lore` did
    `content[:600]` against that dict and the turn died with
    `KeyError: slice(None, 600, None)`. The same value is what `commit.py`
    writes into `lore_entries.content`.
    """

    def test_a_structured_entry_is_flattened_into_prose(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output("mapping_stage", {"staged_lore": [
            {"keys": ["field_clinic"],
             "content": {"name": "Field Clinic",
                         "desc": "One lamp, one generator."}}]})
        assert warnings == []
        content = out["staged_lore"][0]["content"]
        assert isinstance(content, str)
        assert "One lamp" in content and "Field Clinic" in content

    def test_the_quick_mapping_path_is_covered_too(self):
        """`mapping_quick` has no schema of its own, so preprocess is the
        only place this can happen for it -- and `_room_notes_from_lore`
        reads both."""
        from schemas import validate_llm_output
        out, _ = validate_llm_output("mapping_quick", {"staged_lore": [
            {"keys": ["hold"], "content": {"desc": "Rope, and water below."}}]})
        assert out["staged_lore"][0]["content"] == "Rope, and water below."

    def test_prose_content_is_left_exactly_as_written(self):
        from schemas import validate_llm_output
        out, _ = validate_llm_output("mapping_stage", {"staged_lore": [
            {"keys": ["hold"], "content": "Rope, and water below."}]})
        assert out["staged_lore"][0]["content"] == "Rope, and water below."


class TestARepairPromptMustNameTheRealDisagreement:
    """`preprocess_llm_output` drops any `sequence` element that is not an
    object, so a model answering with a list of SENTENCES arrives at the
    semantic check with nothing left and is told "sequence is empty despite
    nonempty player input" -- which is false, and is then handed to it as the
    thing to repair. Observed live twice in eleven turns; both times repair
    and every fallback candidate failed and the turn died.

    Naming the shape is not the same as guessing what the sentences meant. A
    bare sentence does not say whether it is speech or action, and that is
    the player's conduct to declare -- see docs/UNBUILT.md 1.7.
    """

    def test_it_says_the_entries_were_discarded_and_what_shape_to_use(self):
        """Sentences are now read as events (see
        `TestASequenceWrittenAsSentences`), so what still reaches this path
        is an entry carrying neither structure nor prose."""
        from schemas import validate_llm_output_strict
        report = validate_llm_output_strict(
            "director_interpret",
            {"kind": "mixed", "flow": {}, "sequence": [7, 12]},
            source_payload={"player_raw_input": "pick it up and speak"})
        assert not report.valid
        assert "were not objects and were discarded" in report.errors[0]
        assert '"type": "speech"' in report.errors[0]

    def test_a_genuinely_empty_sequence_is_still_reported_as_empty(self):
        from schemas import validate_llm_output_strict
        report = validate_llm_output_strict(
            "director_interpret",
            {"kind": "mixed", "flow": {}, "sequence": []},
            source_payload={"player_raw_input": "wait"})
        assert report.errors == ["sequence is empty despite nonempty player input"]


class TestAConditionWrittenAsItsOwnDescription:
    """`conditions` is `dict[str, list[dict]]`, and a model will write the
    condition as the sentence that describes it:
    `{"generator_fuel": ["The generator is running low on fuel..."]}`.

    Observed live on `director_resolve`, identically on both Pydantic
    majors, and it failed the whole step — which loses the resolved event,
    the state diff and the beat, not just the condition.
    `_coerce_conditions` already existed to "coerce the leaf rather than
    reject the whole step"; its leaf handler passed a non-dict straight
    through to fail validation. The key already names the condition and
    `commit.py` stores the entry as its payload, so the prose is kept.
    """

    def test_prose_becomes_a_condition_keyed_by_its_own_name(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output("director_resolve", {"state_diff": {
            "conditions": {"generator_fuel": ["Running low; the lamp dies."]}}})
        assert warnings == []
        cond = out["state_diff"]["conditions"]["generator_fuel"][0]
        assert cond["condition_id"] == "generator_fuel"
        assert cond["note"] == "Running low; the lamp dies."

    def test_a_structured_condition_is_untouched(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output("director_resolve", {"state_diff": {
            "conditions": {"burn": [{"condition_id": "burn", "kind": "fire"}]}}})
        assert warnings == []
        assert out["state_diff"]["conditions"]["burn"] == [
            {"condition_id": "burn", "kind": "fire"}]

    def test_a_scalar_that_describes_nothing_is_dropped_not_passed_on(self):
        """A bare number carries neither an id nor a description. Passing it
        through only fails validation one layer later, with the whole step."""
        from schemas import validate_llm_output
        out, warnings = validate_llm_output("director_resolve", {"state_diff": {
            "conditions": {"burn": [7]}}})
        assert warnings == []
        assert out["state_diff"]["conditions"]["burn"] == []


class TestAMapKeyIsTheItemsSubject:
    """The map expansion carries the key into the item's first REQUIRED
    field, which is right for `BeliefUpdate.belief` and `AssociationUpdate.cue`
    and yields nothing for every item model where nothing is required — so
    the key was dropped, and for a knowledge seed keyed by its own text the
    key IS the seed.

    The fallback is the first field declared as plain, non-optional prose
    with an EMPTY default: an empty default is a hole a key can fill, a
    non-empty one is a value the author chose, and None means absence is
    already meaningful. Declaration order alone picks `category` on an
    asserted change and `temp_id` on a book op — both wrong.
    """

    def test_a_seed_keyed_by_its_own_text_keeps_the_text(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output("greeting_interpret", {
            "knowledge_seeds": {"She lost her brother at Kerrow": {"kind": "fact"}}})
        assert warnings == []
        assert out["knowledge_seeds"][0]["content"] == "She lost her brother at Kerrow"

    def test_an_asserted_change_takes_the_key_as_its_subject(self):
        from schemas import validate_llm_output
        out, _ = validate_llm_output("director_resolve", {
            "resolved_event": "the door gives",
            "changes_asserted": {"vault_door": {"change": "now open"}}})
        change = out["changes_asserted"][0]
        assert change["subject"] == "vault_door"
        assert change["category"] == "other"      # its chosen default, untouched

    def test_a_book_op_takes_the_key_as_its_name_not_its_temp_handle(self):
        from schemas import validate_llm_output
        out, _ = validate_llm_output("mapping_commit", {
            "book_ops": {"Aran's Reach": {"book_type": "location"}}})
        assert out["book_ops"][0]["name"] == "Aran's Reach"
        assert not out["book_ops"][0].get("temp_id")

    def test_a_required_slot_still_wins(self):
        from schemas import validate_llm_output
        out, _ = validate_llm_output("character", {
            "response": "x",
            "belief_updates": {"the door was never locked": {"confidence": 0.7}}})
        assert out["belief_updates"][0]["belief"] == "the door was never locked"


class TestDeliberationSurvivesItsSpelling:
    def test_candidates_as_a_map_keyed_by_the_option(self):
        """`_coerce_candidates` ran before the generic map expansion and
        returned `[]` for anything that was not a list, so a map discarded
        the character's whole deliberation with no warning."""
        from schemas import CharacterOutput
        out = CharacterOutput(response_candidates={
            "step back": {"risk": 0.2}, "hold the door": {"risk": 0.9}})
        assert [(c.response, c.risk) for c in out.response_candidates] == [
            ("step back", 0.2), ("hold the door", 0.9)]

    def test_a_response_written_as_a_list_of_elements_is_not_a_python_repr(self):
        """The list branch `str()`d its elements, so a structured response
        became "{'type': 'action'}; {'type': 'speech'}" — and that then reads
        as something the character considered saying."""
        from schemas import ResponseCandidate
        c = ResponseCandidate(response=[
            {"type": "action", "observable": "steps back"},
            {"type": "speech", "text": "no"}])
        assert c.response == "steps back; no"

    def test_a_prose_less_element_still_degrades_to_empty(self):
        from schemas import ResponseCandidate
        assert ResponseCandidate(response={"type": "action"}).response == ""


class TestAValidatorMustNotContradictItsOwnFieldsDefault:
    """A field validator runs before the inherited null-substitution, so a
    shared `_clamp_float` fallback was the effective value for `null` while
    an omitted field got the field's own default — the same field answering
    two different ways to two spellings of "not said"."""

    def test_novelty_answers_its_declared_default_either_way(self):
        from schemas import CharacterAppraisal
        assert CharacterAppraisal(novelty=None).novelty == 0.0
        assert CharacterAppraisal().novelty == 0.0

    def test_intentionality_answers_its_declared_default_either_way(self):
        from schemas import GoalImpact
        assert GoalImpact(intentionality=None).intentionality == 0.0
        assert GoalImpact().intentionality == 0.0

    def test_suddenness_answers_its_declared_default_either_way(self):
        from schemas import Observation
        req = dict(observation_id="o", perceiver_id="p", source_atom_id="a",
                   channel="sight", fidelity="clear")
        assert Observation(suddenness=None, **req).suddenness == 0.0
        assert Observation(**req).suddenness == 0.0

    def test_the_axes_that_do_declare_a_half_still_get_it(self):
        from schemas import CharacterAppraisal
        assert CharacterAppraisal(controllability=None).controllability == 0.5
        assert CharacterAppraisal(coping_potential=None).coping_potential == 0.5


class TestASequenceWrittenAsSentences:
    """Every non-object sequence entry was discarded, so a model answering
    with sentences reached the semantic check with nothing left and the turn
    died — twice in eleven live turns.

    An entry is kept as an ACTION unless the whole string is a quotation.
    Typing prose as speech would author an utterance AND transmit it to
    everyone in earshot; typing speech as an action under-informs the room
    instead, and where the engine cannot tell it must fail toward telling
    minds less than happened.
    """

    def test_a_sentence_becomes_an_action_attempt(self):
        from schemas import validate_llm_output_strict
        report = validate_llm_output_strict(
            "director_interpret",
            {"kind": "mixed", "flow": {}, "sequence": ["Picks up the PADD."]},
            source_payload={"player_raw_input": "pick it up"})
        assert report.valid
        assert report.output["sequence"] == [
            {"type": "action", "attempt": "Picks up the PADD."}]

    def test_a_wholly_quoted_sentence_is_speech(self):
        from schemas import validate_llm_output
        out, _ = validate_llm_output("director_interpret", {
            "sequence": ['"Nobody leaves this room."']})
        assert out["sequence"] == [{"type": "speech",
                                    "text": "Nobody leaves this room.",
                                    "volume": "normal"}]

    def test_a_sentence_that_merely_contains_a_quote_stays_an_action(self):
        """Nothing is lost — the attempt text still holds every word — and
        the conservative reading cannot put words in anyone's mouth."""
        from schemas import validate_llm_output
        out, _ = validate_llm_output("director_interpret", {
            "sequence": ['Says, "Nobody leaves this room."']})
        assert out["sequence"][0]["type"] == "action"
        assert "Nobody leaves this room." in out["sequence"][0]["attempt"]

    def test_an_empty_entry_is_still_dropped(self):
        from schemas import validate_llm_output
        out, _ = validate_llm_output("director_interpret", {
            "sequence": ["", "   ", 7]})
        assert out["sequence"] == []

    def test_a_real_event_object_is_untouched(self):
        from schemas import validate_llm_output
        out, _ = validate_llm_output("director_interpret", {"sequence": [
            {"type": "speech", "text": "hello", "volume": "whisper"}]})
        assert out["sequence"] == [
            {"type": "speech", "text": "hello", "volume": "whisper"}]


class TestAWholeAnswerWrappedInOneKey:
    """Observed live on an opening turn: `director_establish` returned
    `{"the_director_outputs": {"location": ..., "rooms": ..., "positions":
    ...}}` — every declared field present and correct, one level too deep.
    Nothing looked inside, so the step failed as "rooms is empty; positions
    is empty", which reads as a model that answered nothing when it had
    answered everything. The repair prompt was handed that same false
    complaint, returned the same envelope, and the turn died.
    """

    def test_the_envelope_is_opened_when_what_is_inside_is_recognised(self):
        from schemas import validate_llm_output_strict
        report = validate_llm_output_strict("director_establish", {
            "the_director_outputs": {
                "rooms": {"lamp_room": {"name": "Lamp room"}},
                "positions": {"Wren": "lamp_room"}}})
        assert report.valid
        assert report.output["positions"]["Wren"] == "lamp_room"

    def test_a_single_legitimate_field_is_not_mistaken_for_an_envelope(self):
        from schemas import validate_llm_output
        out, _ = validate_llm_output("mapping_stage", {
            "scene_patch": {"rooms": {"cellar": {"name": "Cellar"}}}})
        assert list(out["scene_patch"]["rooms"]) == ["cellar"]

    def test_an_envelope_of_nothing_recognisable_is_still_a_disagreement(self):
        """Guessing there would hide the real error behind a plausible
        unwrap."""
        from schemas import validate_llm_output_strict
        report = validate_llm_output_strict(
            "director_establish", {"wrapper": {"nope": 1}})
        assert not report.valid

    def test_two_top_level_keys_are_never_an_envelope(self):
        from schemas import validate_llm_output
        out, _ = validate_llm_output("director_establish", {
            "rooms": {"a": {"name": "A"}}, "positions": {"Wren": "a"}})
        assert out["positions"] == {"Wren": "a"}


class TestTheSameReadingForEveryPlayer:
    def test_a_co_players_sentence_is_read_like_the_primary_players(self):
        """Otherwise one player's prose is recovered and another's is
        discarded, in the same payload, for no reason either could see."""
        from schemas import validate_llm_output
        out, _ = validate_llm_output("director_interpret", {
            "sequence": ["Picks up the PADD."],
            "other_players": {"p2": {"sequence": ["Steps into the doorway.",
                                                 '"Wait."', 7]}}})
        assert out["sequence"][0]["type"] == "action"
        co = out["other_players"]["p2"]["sequence"]
        assert co[0] == {"type": "action", "attempt": "Steps into the doorway."}
        assert co[1]["type"] == "speech" and co[1]["volume"] == "normal"
        assert len(co) == 2


class TestEvidenceIsFiledTheSameWayInEitherSpelling:
    """A map keyed by the evidence itself landed the key in `event_id` — the
    first empty prose slot — which is the opposite of what the same words get
    in list form, where a sentence routes to `fact`. One rule, both paths."""

    def test_prose_keys_land_on_fact_and_id_like_keys_on_event_id(self):
        from schemas import MindHypothesis
        h = MindHypothesis(about_entity="Mara", kind="observation", claim="x",
                           evidence={"the sound from the east corridor": {},
                                     "turn:12:a": {}})
        assert [(e.event_id, e.fact) for e in h.evidence] == [
            ("", "the sound from the east corridor"), ("turn:12:a", "")]

    def test_a_list_of_strings_is_unchanged(self):
        from schemas import MindHypothesis
        h = MindHypothesis(about_entity="Mara", kind="observation", claim="x",
                           evidence=["the sound from the east corridor", "turn:12:a"])
        assert [(e.event_id, e.fact) for e in h.evidence] == [
            ("", "the sound from the east corridor"), ("turn:12:a", "")]


class TestDeliberationIsNeverInvented:
    """A blank candidate is an option the character never weighed, written
    into the record the variant viewer shows."""

    def test_an_empty_map_yields_no_candidates(self):
        from schemas import CharacterOutput
        assert CharacterOutput(response_candidates={}).response_candidates == []

    def test_a_map_that_is_neither_candidate_nor_map_of_candidates(self):
        from schemas import CharacterOutput
        assert CharacterOutput(response_candidates={"a": "b"}).response_candidates == []

    def test_one_candidate_written_as_itself_is_kept(self):
        from schemas import CharacterOutput
        out = CharacterOutput(response_candidates={"response": "hold the door"})
        assert [c.response for c in out.response_candidates] == ["hold the door"]

    def test_a_bare_string_is_one_candidate(self):
        from schemas import CharacterOutput
        out = CharacterOutput(response_candidates="step back")
        assert [c.response for c in out.response_candidates] == ["step back"]


class TestAYesNoFieldAnsweringADifferentQuestion:
    """Observed live: `entities.permit.container` — "is this a container" —
    came back as `"kess_vantar"`, the id of whoever was holding it. Both
    majors refuse it, and refusing cost the whole `director_establish` step
    its normalization over one misused field.

    The declared default asserts nothing: the value could not have meant
    yes-or-no, and the answer it did carry has no slot here to survive in.
    """

    def test_a_name_where_a_flag_was_declared_falls_back_to_the_default(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output("director_establish", {
            "rooms": {"quay": {"name": "Quay"}}, "positions": {"Kess": "quay"},
            "entities": {"permit": {"name": "Permit", "container": "kess_vantar"}}})
        assert warnings == []
        assert out["entities"]["permit"]["container"] is False

    def test_every_spelling_of_yes_and_no_both_majors_agree_on_is_kept(self):
        from schemas import SceneEntityDef
        for value, expected in ((True, True), (False, False), ("yes", True),
                                ("no", False), ("true", True), ("FALSE", False),
                                (1, True), (0, False)):
            assert SceneEntityDef(name="x", container=value).container is expected

    def test_a_number_that_is_neither_zero_nor_one_is_not_a_flag(self):
        from schemas import SceneEntityDef
        assert SceneEntityDef(name="x", container=2).container is False


class TestAnInfinityIsNotAWholeNumber:
    """`1e999` is ordinary JSON and `json.loads` hands it back as `inf`.
    Truncating a float into an `int`-declared field then raised
    `OverflowError` — which is neither `ValueError` nor `AssertionError`, so
    NEITHER Pydantic major rewraps it, and it escaped every
    `except ValidationError` in the engine as an uncaught exception in the
    character stage."""

    def test_an_infinity_degrades_with_a_warning_instead_of_escaping(self):
        import json
        from schemas import validate_llm_output
        out, warnings = validate_llm_output(
            "character", json.loads('{"active_state": {"enacted_want": 1e999}}'))
        assert warnings
        assert out["active_state"]["enacted_want"] == float("inf")

    def test_a_fraction_still_truncates(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output(
            "character", {"active_state": {"enacted_want": 1.5}})
        assert warnings == []
        assert out["active_state"]["enacted_want"] == 1


class TestAnUnpolicedListOfObjects:
    """A bare `list[dict]` says "objects, shape unpoliced". There is no item
    model to consult, so a scalar element carries nothing that could be
    mapped into one — and every consumer already skips it
    (`agents/common.lore_for` filters `isinstance(e, dict)`; nothing reads
    `npc_suggestions` at all). The schema was the only strict layer, and it
    failed the WHOLE step: observed live, `relevant_lore: [1934, 1938, …]`
    — the model answering with lore ids — aborted the turn.
    """

    def test_scalar_elements_are_dropped_and_real_ones_kept(self):
        from schemas import validate_llm_output
        out, warnings = validate_llm_output("mapping_stage", {
            "relevant_lore": [1934, 1938, {"id": 1, "content": "kept"}],
            "npc_suggestions": ["Severine might follow."]})
        assert warnings == []
        assert out["relevant_lore"] == [{"id": 1, "content": "kept"}]
        assert out["npc_suggestions"] == []

    def test_a_typed_list_of_models_still_refuses_rather_than_lose_content(self):
        """There the item model names what is missing, and repair can act on
        it — dropping a character's belief update silently would be the
        defect this layer exists to prevent."""
        from schemas import validate_llm_output
        _, warnings = validate_llm_output(
            "character", {"mind_model_updates": ["she flinched"]})
        assert warnings

    def test_an_archive_row_is_still_strict(self):
        """`chat_archive` declares `list[dict[str, Any]]` — parametrized, not
        bare. An archive quietly missing a turn is worse than one refused."""
        import pydantic, pytest
        from chat_archive import ChatArchiveData
        validate = getattr(ChatArchiveData, "model_validate", None) \
            or ChatArchiveData.parse_obj
        with pytest.raises(pydantic.ValidationError):
            validate({"chat": {"id": 1}, "turns": [{"idx": 0}, 7]})


class TestAnItemModelMayNameItsOwnSubject:
    """`_subject_field` beats both positional rules, because neither can see a
    subject field that carries a non-empty default.

    `GoalImpact.serves` defaults to "situational", so it is neither the first
    REQUIRED field nor the first EMPTY prose field — and a map keyed by the
    goal filed the goal in `why`, recording the goal as its own explanation
    and leaving `serves` generic. commit.py's goal matching reads `serves`, so
    the information survived (it used to be dropped outright) and landed
    exactly where nothing looks at it.
    """

    def _impacts(self, payload):
        import inspect

        import schemas
        holder = next(
            obj for _n, obj in vars(schemas).items()
            if inspect.isclass(obj)
            and "goal_impacts" in getattr(obj, "__fields__", {}))
        return schemas._dump(holder(**{"goal_impacts": payload}))["goal_impacts"]

    def test_the_goal_lands_in_serves_not_in_why(self):
        got = self._impacts({"reach the tower": {"impact": 0.6}})[0]
        assert got["serves"] == "reach the tower"
        assert got["why"] == ""
        assert got["impact"] == 0.6

    def test_a_key_never_overwrites_a_value_the_model_supplied(self):
        got = self._impacts(
            {"reach the tower": {"serves": "drive", "impact": 0.2}})[0]
        assert got["serves"] == "drive"

    def test_the_list_spelling_is_unchanged(self):
        got = self._impacts([{"serves": "drive", "impact": 0.2}])[0]
        assert got["serves"] == "drive"

    def test_models_without_the_declaration_still_use_the_positional_rule(self):
        """The rule this replaces must keep working where it was already
        right — it was a fix for one model, not a new general mechanism."""
        from schemas import MindHypothesis
        h = MindHypothesis(about_entity="Mara", kind="observation", claim="x",
                           evidence={"the sound from the east corridor": {}})
        assert h.evidence[0].fact == "the sound from the east corridor"

    def test_a_declared_subject_field_that_is_not_a_field_is_ignored(self):
        """A typo in the declaration must fall back, never crash."""
        import schemas
        from pydantic import Field

        class Bogus(schemas.LenientModel):
            _subject_field = "nope"
            name: str = ""

        class Holder(schemas.LenientModel):
            items: list[Bogus] = Field(default_factory=list)

        assert Holder(**{"items": {"Mara": {}}}).items[0].name == "Mara"


class TestSingleItemUnderAListValuedChannel:
    """`overlays` and `conditions` are name-keyed tables of LISTS, and a
    model with exactly one entry to report writes it directly under the key.

    Observed live (run 20, twice in 14 beats): interpret emitted
    `state_assertions.overlays.village_well: <one value>` and the whole
    otherwise-valid output failed with `value is not a valid list`, buying a
    full temperature-0 repair round-trip (4.9s) for a shape that means the
    same thing as the list of one. Same judgment as `mind_model_updates`
    above: the singular and the list of one are unambiguous.
    """

    def test_a_single_overlay_value_becomes_a_list_of_one(self):
        from schemas import StateDiff
        sd = StateDiff(overlays={"village_well": "moss-slick stones"})
        assert sd.overlays["village_well"] == ["moss-slick stones"]

    def test_a_single_condition_object_becomes_a_list_of_one(self):
        """The identical trap one channel over: conditions wants a LIST of
        condition objects per name, and one condition arrived bare."""
        from schemas import StateDiff
        sd = StateDiff(conditions={"Mara": {"id": "bruised", "note": "arm"}})
        assert sd.conditions["Mara"] == [{"id": "bruised", "note": "arm"}]

    def test_a_real_list_and_an_explicit_null_keep_their_meaning(self):
        from schemas import StateDiff
        sd = StateDiff(overlays={"Mara": ["ash streak"], "well": None})
        assert sd.overlays["Mara"] == ["ash streak"]
        assert sd.overlays["well"] == []

    def test_the_body_specialist_shares_the_coercion(self):
        """The specialist declares the same channels 'in exactly the shapes
        StateDiff declares for them, so assembly can move each channel into
        the resolve diff without a second spelling of any coercion' -- which
        must include this coercion, or the trap just moves into the
        orchestrated call."""
        from schemas import DirectorBodySpecialist
        out = DirectorBodySpecialist(
            overlays={"village_well": "moss-slick stones"},
            conditions={"Mara": {"id": "bruised"}})
        assert out.overlays["village_well"] == ["moss-slick stones"]
        assert out.conditions["Mara"] == [{"id": "bruised"}]

    def test_a_string_condition_item_still_fails(self):
        """Wrapping supplies the missing LIST, never the missing OBJECT: a
        bare string under `conditions` has no unambiguous field to land in,
        and papering over it would hide a real disagreement (the
        mind_model_updates rule above)."""
        import pydantic
        import pytest

        from schemas import StateDiff
        with pytest.raises(pydantic.ValidationError):
            StateDiff(conditions={"Mara": "bleeding"})


class TestBareStringEvidence:
    """Evidence cited as one naked string instead of a list.

    `_coerce_evidence_refs` accepted a LIST of bare strings and a dict, but
    the naked string fell through to pydantic. Observed live (run 20, five
    times in 14 beats): `remember_lines.0.evidence: value is not a valid
    list` threw away an otherwise-valid character output and bought a
    temperature-0 repair round for a shape whose meaning was never in doubt
    -- the docstring on the coercer itself argues the string form carries
    everything the object form does.
    """

    def test_a_bare_prose_string_lands_on_fact(self):
        from schemas import RememberLine
        line = RememberLine(quote="the shutter banged twice",
                            evidence="the sound from the east corridor")
        assert line.evidence[0].fact == "the sound from the east corridor"
        assert line.evidence[0].event_id == ""

    def test_a_bare_id_string_lands_on_event_id(self):
        from schemas import RememberLine
        line = RememberLine(quote="x", evidence="current")
        assert line.evidence[0].event_id == "current"

    def test_an_empty_string_is_no_evidence_at_all(self):
        from schemas import RememberLine
        assert RememberLine(quote="x", evidence="  ").evidence == []


def test_a_name_keyed_table_written_as_a_list_of_entries_is_keyed():
    """The other shape `overlays`/`conditions` get written as. Observed live
    at interpret: `state_assertions.overlays` came back a LIST, failed with
    "value is not a valid dict", and bought a 4.2s temperature-0 repair for
    a channel the body specialist replaced immediately afterwards."""
    from schemas import StateDiff

    keyed = StateDiff(**{"overlays": [
        {"subject": "Hinami", "value": "flushed to the ears"}]}).overlays
    assert keyed == {"Hinami": ["flushed to the ears"]}
    assert StateDiff(**{"overlays": [
        {"name": "Hinami", "entries": ["a", "b"]}]}).overlays == {
            "Hinami": ["a", "b"]}


def test_an_unclaimed_entry_is_rejected_rather_than_attributed():
    """A list of bare strings names nobody. Nothing here may invent a
    subject -- attaching an unclaimed mark to the wrong body is worse than
    rejecting the shape and paying for the repair."""
    import pytest
    from pydantic import ValidationError

    from schemas import StateDiff

    with pytest.raises(ValidationError):
        StateDiff(**{"overlays": ["a mark with no owner"]})


# --- the manifest event number a specialist echoes back -------------------

def test_an_echoed_event_number_survives_the_shapes_models_actually_send():
    """`resolved_events[].event_id` was 8 of 17 validation failures across the
    live corpus -- 47% of every repair call the engine has made. The number is
    assigned by the ENGINE and merely echoed, so a model writing "#1" has not
    misunderstood anything; it has punctuated. Failing the whole call over that
    buys a repair round trip to recover a value that was never in doubt."""
    from schemas import ResolvedEvent, _validate
    for sent in ("1", "#1", "E1", "event 1", "1.", " 1 ", 1):
        got = _validate(ResolvedEvent, {"event_id": sent, "status": "encoded"})
        assert got.event_id == 1, sent


def test_an_ambiguous_event_number_still_fails():
    """Coercion is not repair. Two runs of digits, or none, means the model's
    intent is genuinely unclear -- and inventing one there would hide a real
    error, which is the whole reason LenientModel leaves required fields
    alone."""
    import pytest
    from schemas import ResolvedEvent, _validate
    for sent in ("1,2", "none", "first"):
        with pytest.raises(Exception):
            _validate(ResolvedEvent, {"event_id": sent, "status": "encoded"})


def test_one_named_location_is_read_as_a_list_of_one():
    """4 of 17 validation failures across the live corpus -- 24% of every
    repair call -- were the whole mapping commit thrown away over the
    difference between "the vault" and ["the vault"]. LenientModel already
    reads "" as an empty list; this is the mirror case it did not reach."""
    from schemas import LoreOp, _validate
    assert _validate(LoreOp, {"op": "create",
                              "knowledge_locations": "the vault"}
                     ).knowledge_locations == ["the vault"]


def test_a_comma_inside_a_location_is_not_split_into_two():
    """Wrapped, never split. A comma might be two places or one place with a
    comma in its name, and reading a near-miss shape is not licence to invent
    structure that was never sent."""
    from schemas import LoreOp, _validate
    got = _validate(LoreOp, {"op": "create",
                             "knowledge_locations": "Vault, Lower"})
    assert got.knowledge_locations == ["Vault, Lower"]


def test_an_empty_narration_says_which_keys_did_arrive():
    """"prose is empty" is 18% of the corpus's repair calls and, unlike its two
    larger siblings, the message never carried the shape that failed -- so
    nothing distinguished a model that returned NOTHING from one that returned
    a page of narration under a key this contract does not read. The first is
    worth a repair call; the second is worth a one-line alias."""
    from schemas import semantic_output_errors
    assert semantic_output_errors("narrator", {}) == ["prose is empty"]
    assert semantic_output_errors("narrator", {"prose": "She turned."}) == []
    said = semantic_output_errors("narrator", {"narration": "a page", "beat": 1})
    assert said == ["prose is empty (keys present: beat, narration)"]


class TestAScalarWhereAnObjectWasDeclared:
    """A model that answered the subject and skipped the wrapper.

    Live: the opening turn of a story with six bodies in it died on
    `director_establish failed JSON validation: poses.Sarah Moon: value is not
    a valid dict` -- six times over, once per body, because every one of them
    came back as `"standing"` instead of `{"posture": "standing"}`. That is a
    complete and correct answer to what the field is FOR, written in the
    shorter of the two spellings, and the story got no scene at all.

    The schema was the only strict layer: `spatial._clean_pose` has always
    returned None for a non-dict and moved on.
    """

    def _establish(self, poses):
        import schemas

        out, _warnings = schemas.validate_llm_output("director_establish", {
            "location": "a room", "time": "now", "scene_description": "x",
            "poses": poses,
        })
        return out["poses"]

    def test_a_bare_string_becomes_the_subject_field(self):
        poses = self._establish({"Hinami": "seated, restrained"})
        assert poses["Hinami"]["posture"] == "seated, restrained"
        assert poses["Hinami"]["support"] == ""

    def test_the_whole_live_payload_survives(self):
        """Six bodies, six strings -- the shape that actually killed a turn."""
        names = ["Sarah Moon", "Hinami", "guard_1", "guard_2", "guard_3",
                 "guard_4"]
        poses = self._establish({name: "standing" for name in names})
        assert sorted(poses) == sorted(names)
        assert all(poses[name]["posture"] == "standing" for name in names)

    def test_the_long_spelling_is_untouched(self):
        """The tolerance must not cost the models that answered correctly."""
        poses = self._establish({"Mara": {
            "posture": "kneeling", "support": "the floor",
            "relative_to": "Vesk", "relation": "beneath",
            "constraint": "pinned", "detail": "one hand braced"}})
        assert poses["Mara"] == {
            "posture": "kneeling", "support": "the floor",
            "relative_to": "Vesk", "relation": "beneath",
            "constraint": "pinned", "detail": "one hand braced"}

    def test_the_strict_path_accepts_it_too(self):
        """`_agent_json` validates strictly and RAISES -- which is the path the
        live failure took. Passing leniently and failing strictly would fix
        nothing."""
        import schemas

        report = schemas.validate_llm_output_strict("director_establish", {
            "location": "a room", "time": "now", "scene_description": "x",
            "poses": {"Sarah Moon": "standing"}})
        # Asserted on the POSES errors specifically, not on `valid`: this
        # deliberately minimal payload also has no rooms and no positions, and
        # the strict path is right to say so. What must be gone is the schema
        # complaint that killed the turn.
        assert not [e for e in report.errors if "poses" in e], report.errors
        assert report.output["poses"]["Sarah Moon"]["posture"] == "standing"

    def test_it_holds_on_the_resolve_side_too(self):
        """Same channel, same shortcut, different stage. A tolerance that only
        covered the opening beat would leave the other 2,000."""
        import schemas

        out, _warnings = schemas.validate_llm_output("director_spatial", {
            "poses": {"Vesk": "leaning against the door"}})
        assert out["poses"]["Vesk"]["posture"] == "leaning against the door"

    def test_an_empty_value_still_means_nothing_to_report(self):
        poses = self._establish({"Ash": "", "Bel": {}})
        assert poses["Ash"] == {} or poses["Ash"]["posture"] == ""
        assert poses["Bel"]["posture"] == ""

    def test_a_number_is_carried_as_prose(self):
        """`_as_declared_scalar`'s job, one level in: the subject slot is prose,
        so a model answering with a bare number still lands somewhere."""
        poses = self._establish({"Ash": 3})
        assert poses["Ash"]["posture"] == "3"

    def test_a_model_with_no_answerable_subject_is_left_to_fail(self):
        """The rule guesses nothing. Where there is no subject slot to put a
        scalar in, inventing one would hide a real error."""
        import schemas
        from schemas import _subject_slot

        class Anonymous(schemas.LenientModel):
            count: int = 0
            flag: bool = False

        assert _subject_slot(Anonymous) is None
