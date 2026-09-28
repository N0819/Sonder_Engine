"""Pins for the Director's fold: what happens between the encoder's answer
and the merged diff.

The Director writes prose and ONE encoder writes the beat as ordered events
(`agents/director_prose.py`); `director._run_specialists` splits those events
by channel owner and binds, validates and folds each owner's share, and every
deterministic floor after it -- the movement backstop, the entity-interior
integrity floor, the player-authority dial, reconciliation -- judges the
MERGED result. The causal Director this file was written for (a ledger author
dispatching five specialist hands, design note 19) was deleted 2026-09-27;
what it pinned about dispatch, rulings, forwarding and the hands' sheets went
with it. What stays is the fold's own contract:

- one pipeline step per Director stage, no stage keys for the channel owners;
- the orchestration record survives the schema round trip;
- a channel written at a stage that cannot carry it is dropped LOUDLY, never
  silently;
- the work items, the item handles and the recompiler that turn the rows into
  one chronological program;
- the floors that judge the merged diff, run end to end through the prose
  Director.
"""

from __future__ import annotations

import json

import pytest

import agents.director as director
from agents.director import manifest_category_targets
from tests.director_fakes import (
    BASE_SCENE,
    _action_interp,
    _fake_agent,
    _make_ctx,
    _speech_interp,
    encoder_event,
    prose_answers,
)


def test_orchestration_adds_no_stage_keys_to_runtime():
    """Requirement 4: one step per Director stage, fan-out INSIDE. The
    runtime must need no new stage keys -- that is what keeps reroll,
    rerun-from-stage and every stored turn's replay untouched."""
    from agents import runtime

    assert "director_resolve" in runtime.STEP_HANDLERS
    assert not any("body" in key for key in runtime.STEP_HANDLERS)


def test_orchestration_record_survives_the_schema_round_trip():
    """The dispatch record is engine-authored step metadata. If the schema
    dump dropped it (the `routed_to_background` lesson), the persisted
    variant would claim a monolithic resolve for an orchestrated one and no
    stored turn could ever be audited for gate mispredictions."""
    from llm.schemas import validate_llm_output

    out, _ = validate_llm_output("director_resolve", {
        "resolved_event": "x",
        "orchestration": {"enabled": True,
                          "specialists": {"body": {
                              "run": True, "addressed_by": ["note"],
                              "gated": ["conditions"],
                              "scope": ["conditions"]}},
                          "unrouted_rulings": ["transit"]},
    })
    body = out["orchestration"]["specialists"]["body"]
    assert body["run"] is True
    # The two halves of the dispatch decision persist beside it, or a
    # stored turn could never say WHY a hand did or did not run.
    assert body["addressed_by"] == ["note"] and body["gated"] == ["conditions"]
    assert out["orchestration"]["unrouted_rulings"] == ["transit"]

    # And a pre-orchestration variant (no record) still validates unchanged.
    old, _ = validate_llm_output("director_resolve", {"resolved_event": "x"})
    assert old["orchestration"] == {}


# ---------------------------------------------------------------------------
# Dispatch: the ruling decides who runs; the gate, decided at resolve time
# from scene state, decides how much sheet an addressed hand loads, and
# fails open within it.
# ---------------------------------------------------------------------------


class TestTheInstructionRidesOnTheEvent:
    """The Director's intent belongs to the EVENT, not to the hand.

    `DESIGN_SPECIALIST_CONTRACT.md`: a hand's work item is a chunk carrying a
    chronological id and a note saying how the Director wants that one
    resolved. Before this, resolution intent existed only as `ledger_notes:
    {specialist: line}` -- one line per HAND, aggregated across everything
    that hand does this beat, arriving through a different channel from the
    event it was about.

    Measured 2026-09-09 on current code (`tools/instruction_coverage.py`):
    every dispatched hand does receive some instruction -- 0% get none -- but
    46% of calls carry a hand-level note with no numbered event beside it, so
    the intent and its event had different coverage and no link.

    `note` is OPTIONAL and stays so: an entry without one is still a routable
    change, and the hand reads it exactly as it does today.
    """

    def test_the_shared_type_carries_the_instruction(self):
        from llm.schemas import AssertedChange
        entry = AssertedChange(category="pose", subject="Maren",
                               change="Maren has turned to face you.",
                               note="She is standing, facing you now.")
        assert entry.note == "She is standing, facing you now."

    def test_an_entry_without_one_is_still_valid(self):
        from llm.schemas import AssertedChange
        assert AssertedChange(category="pose", subject="Maren",
                              change="Maren has turned.").note == ""

    def test_both_halves_of_the_director_carry_it(self):
        """`AssertedChange` is shared by both stages deliberately, so this
        pins that the sharing still holds rather than re-testing the field."""
        from llm.schemas import DirectorInterpret, DirectorResolve
        for model in (DirectorInterpret, DirectorResolve):
            built = model(changes_asserted=[
                {"category": "pose", "subject": "Maren", "change": "turned",
                 "note": "settle her facing you"}])
            assert built.changes_asserted[0].note == "settle her facing you"

    def test_the_instruction_reaches_the_hand_that_owns_the_event(self):
        """The whole point: it has to survive the slice into the payload."""
        view = {"manifest": [
            {"category": "poses", "event_id": 1, "subject": "Maren",
             "change": "Maren has turned to face you.",
             "note": "She is standing, facing you now."}]}
        sliced = director._specialist_manifest_slice("spatial", view)
        assert sliced[0]["note"] == "She is standing, facing you now."

    def test_it_survives_the_numbering_the_engine_actually_runs(self):
        """THROUGH `_manifest_items`, not around it.

        The test above hand-builds its view and so proves nothing about the
        pipeline. `_manifest_items` rebuilds every entry as an explicit dict
        and then copies a FIXED LIST of extra fields onto it, so a field
        missing from that list is dropped with nothing raised and nothing
        logged. `note` was, on the first cut of this change: the Director
        wrote the instruction, the slice would have carried it, and the hand
        would never have seen it.
        """
        out = {"changes_asserted": [
            {"category": "pose", "subject": "Maren",
             "change": "Maren has turned to face you.",
             "note": "She is standing, facing you now."}]}
        items = director._manifest_items(out)
        assert items[0]["note"] == "She is standing, facing you now."
        assert items[0]["event_id"] == 1

    def test_an_entry_with_no_instruction_grows_no_empty_key(self):
        """Same rule the endpoint fields follow: a key appears when the model
        supplied one, rather than an empty string on every item."""
        out = {"changes_asserted": [
            {"category": "pose", "subject": "Maren", "change": "turned"}]}
        assert "note" not in director._manifest_items(out)[0]


class TestASpanIsSettledOnlyWhenEveryOwnerHas:
    """A span in several categories is not a routing hedge with one right
    answer. The owner, 2026-09-10: "neither resolve overwrites the other, they
    are both completed halves or thirds or quarters of a singular ledger."

    `_index_addressed_events` keyed one owner per `event_id`, so the last hand
    to answer overwrote the first: a span whose wardrobe half was encoded and
    whose object half was not would read as fully settled, and the seam would
    acquit it. Written BEFORE any span carries two categories, so the silent
    loss is never possible rather than fixed after it appears.
    """

    def _index(self, answers):
        dispatch = {
            hand: {"ran": True,
                   "events_resolved": [{"event_id": 1, "status": status}]}
            for hand, status in answers.items()}
        return director._index_addressed_events(dispatch)

    def test_every_owner_is_kept_not_the_last_one(self):
        index = self._index({"body": "encoded", "objects": "not_mine"})
        assert set(index[1]["by_hand"]) == {"body", "objects"}
        assert index[1]["by_hand"]["body"]["status"] == "encoded"
        assert index[1]["by_hand"]["objects"]["status"] == "not_mine"

    def test_a_half_settled_span_stays_owed(self):
        out = {"orchestration": {
            "events_addressed": self._index({"body": "encoded",
                                             "objects": "not_mine"})}}
        omission = {"event_id": 1, "category": "attire", "subject": "Corin",
                    "change": "the belt is off"}
        owed, acquitted, _refused = director._acquit_addressed_events(
            out, [omission], {})
        assert owed == [omission]
        assert acquitted == []

    def test_a_fully_settled_span_is_acquitted(self):
        out = {"orchestration": {
            "events_addressed": self._index({"body": "encoded",
                                             "objects": "encoded"})}}
        omission = {"event_id": 1, "category": "attire", "subject": "Corin",
                    "change": "the belt is off"}
        owed, acquitted, _refused = director._acquit_addressed_events(
            out, [omission], {})
        assert owed == []
        assert len(acquitted) == 1

    def test_a_single_owner_settles_as_it_always_did(self):
        """The fallback. A row written before `by_hand` existed, and a span
        one hand owns, both read the way they always have."""
        out = {"orchestration": {
            "events_addressed": {1: {"owner": "body", "status": "encoded"}}}}
        omission = {"event_id": 1, "category": "attire", "subject": "Corin",
                    "change": "the belt is off"}
        owed, acquitted, _refused = director._acquit_addressed_events(
            out, [omission], {})
        assert owed == []
        assert len(acquitted) == 1


class TestTheSpanIsTheWorkItem:
    """`sequence` becomes the four-field work item: chunk, id, note, category.

    `DESIGN_SPECIALIST_CONTRACT.md` 4a, and the owner's ruling on which field
    survives. `sequence` was always the right dissection -- typed spans of the
    player's own input -- and lacked only a category saying which ledger family
    a span belongs to, an id, and the Director's note on how it should resolve.

    `changes_asserted` still exists and still routes; the two share ONE id
    space so a record's `from_event` is never ambiguous about which list it
    points into.
    """

    def test_the_engine_numbers_the_spans(self):
        out = {"sequence": [
            {"type": "action", "attempt": "I pull off my belt",
             "category": "attire", "note": "belt comes off"},
            {"type": "action", "attempt": "drop it on the bench",
             "category": "entities", "note": "belt rests on the bench"}]}
        items = director._span_items(out)
        assert [i["event_id"] for i in items] == [1, 2]
        assert items[0]["note"] == "belt comes off"

    def test_an_uncategorized_span_is_not_a_work_item(self):
        """A question asked or a look given is a perfectly good sequence
        element -- perception and the narrator read it -- it just addresses no
        ledger. Making every span a work item would dispatch a hand for every
        line of dialogue."""
        out = {"sequence": [
            {"type": "speech", "text": "Have you seen the reeve?"},
            {"type": "action", "attempt": "I sit", "category": "poses"}]}
        items = director._span_items(out)
        assert [i["attempt"] for i in items] == ["I sit"]
        assert items[0]["event_id"] == 1

    def test_the_manifest_continues_past_the_spans(self):
        """ONE ID SPACE. Both lists live during the migration, and a record's
        `from_event` names one number -- so they cannot both start at 1."""
        out = {"sequence": [{"type": "action", "attempt": "x",
                             "category": "poses"}],
               "changes_asserted": [{"category": "attire", "subject": "Corin",
                                     "change": "the belt is off"}]}
        assert director._span_items(out)[0]["event_id"] == 1
        assert director._manifest_items(out)[0]["event_id"] == 2

    def test_the_span_reaches_the_hand_that_owns_it(self):
        view = {"spans": [
            {"category": "poses", "event_id": 1, "attempt": "I kneel",
             "note": "set her kneeling"},
            {"category": "attire", "event_id": 2, "attempt": "belt off",
             "note": "unequip the belt"}]}
        assert [c["event_id"] for c in
                director._specialist_span_slice("spatial", view)] == [1]
        assert [c["event_id"] for c in
                director._specialist_span_slice("body", view)] == [2]

    def test_the_work_item_reaches_the_hand_in_exactly_one_list(self):
        """`spans` carries the work; `declaration` carries what was declared.

        The three fields lived in BOTH for a day, and the duplication cost a
        beat. `assign_event_ids` stamps every declaration element with a
        phase-graph id also called `event_id`, so a hand's payload held two
        fields of that name with different values. Measured 2026-09-10, beat
        2: the contact hand echoed "turn:2:player:0:action", its entire answer
        was rejected, and its repair returned no usable object -- 16,180
        output tokens and 96.9s on a receipt for the wrong ledger.

        The allowlist that drops what it does not name is still the hazard it
        was; what changed is which list is meant to hold these."""
        from types import SimpleNamespace
        ctx = SimpleNamespace(cast=[], scene=None)
        out = {"sequence": [{"type": "action", "attempt": "I kneel",
                             "category": "poses", "note": "set her kneeling"}]}
        view = director._interpret_beat_view(ctx, out, "Corin")
        span = view["spans"][0]
        assert span["category"] == "poses"
        assert span["note"] == "set her kneeling"
        assert span["event_id"] == 1
        declared = view["declaration"]["sequence"][0]
        assert declared["attempt"] == "I kneel"
        for field in ("event_id", "category", "note"):
            assert field not in declared, field


class TestTheSheetAsksForNothingUnread:
    """A field the sheet asks for and nothing reads costs three times: the
    sentence teaching it, the tokens writing it, and a reader's belief that it
    matters.

    `referents[].role` looked like that and IS NOT. It published six values --
    actor / actor_possessive / target / target_possessive / instrument /
    instrument_possessive -- and a first reading of
    `agents.common.resolve_action_referents` found it using only `text`,
    `entity` and `occurrence`. That reading was of a TRUNCATED view of the
    function: line 378 reads `role` and drives the possessive form off it, and
    cutting the field turned "takes Mara's hand with Iris' left hand" into
    "takes Mara hand with Iris left hand". The guard below caught it, which is
    the argument for writing the guard before the cut rather than after.

    What IS dead is five sixths of the enum. The only test anywhere is
    `"possessive" in role`, so actor / target / instrument are never
    distinguished and the six values carry one bit. `plain|possessive`
    satisfies the same predicate -- and so does every value the old enum had,
    so a stored variant replayed from before this still resolves.
    """

    def test_possessive_still_renders(self):
        """The behaviour the enum actually drives, and the assertion that
        caught the bad cut."""
        from agents.common import resolve_action_referents
        event = {"referents": [
            {"text": "her", "entity": "Mara", "role": "possessive",
             "occurrence": 1},
            {"text": "her", "entity": "Iris", "role": "possessive",
             "occurrence": 2},
        ]}
        assert resolve_action_referents(
            "takes her hand with her left hand", event) == (
            "takes Mara's hand with Iris' left hand")

    def test_the_old_spelling_still_resolves(self):
        """`"possessive" in role` matches every value the six-value enum had,
        so stored variants and mid-flight reruns are unaffected."""
        from agents.common import resolve_action_referents
        event = {"referents": [
            {"text": "her", "entity": "Mara", "role": "target_possessive",
             "occurrence": 1},
        ]}
        assert resolve_action_referents("takes her hand", event) == \
            "takes Mara's hand"

    def test_a_plain_referent_is_not_made_possessive(self):
        from agents.common import resolve_action_referents
        event = {"referents": [
            {"text": "her", "entity": "Mara", "role": "plain",
             "occurrence": 1}]}
        assert resolve_action_referents("takes her hand", event) == \
            "takes Mara hand"


class TestBothHalvesEmitWorkItems:
    """Resolve is the interpret half's structural twin, and stayed behind.

    "Resolve would mostly do the same but for characters" -- so a span there is
    anything the beat made true, by anyone, rather than only the player's own
    declared conduct.

    It did not have one. `_span_items` reads `sequence`, `DirectorResolve`
    had no such field, and the retirement of `changes_asserted` left the
    resolve author with a sheet block telling it that "the categorized spans
    of the beat are the work items every ledger is written from" and NO FIELD
    to write them into -- so resolve-side hands got `director_note` and
    nothing else. This is the same defect the class two files up was written
    for (`ledger_notes` built on the resolve half only) pointing the other
    way, which is why it gets a guard rather than a fix.
    """

    def test_both_models_carry_the_work_item_field(self):
        from llm.schemas import DirectorInterpret, DirectorResolve
        span = {"actor": "Maren", "attempt": "turns to face you",
                "category": "poses", "note": "set her facing you"}
        for model in (DirectorInterpret, DirectorResolve):
            built = model(sequence=[span])
            assert built.sequence[0]["category"] == "poses", model.__name__
            assert built.sequence[0]["note"], model.__name__

    def test_both_beat_views_carry_spans(self):
        """The view is what a hand is handed. Numbered on both halves, by the
        engine, or the ids a record cites mean nothing on one of them."""
        from types import SimpleNamespace
        out = {"sequence": [{"actor": "Maren", "attempt": "turns",
                             "category": "poses", "note": "face you"}]}
        interpret = director._interpret_beat_view(
            SimpleNamespace(cast=[], scene=None), out, "Corin")
        assert interpret["spans"][0]["event_id"] == 1

        resolve = director._resolve_beat_view(
            out, [], {}, [], "Corin", {"sequence": []})
        assert resolve["spans"][0]["event_id"] == 1
        assert resolve["spans"][0]["note"] == "face you"

    def test_a_resolve_span_is_reconciled_by_its_actor(self):
        """An interpret span is the player's own and names no subject; a
        resolve span names whose act it was, and that is what the evidence
        check matches when the hand stamped no id."""
        from agents.director import _subject_match_forms  # noqa: F401
        item = {"actor": "Maren", "attempt": "turns", "category": "poses",
                "event_id": 1, "note": "face you"}
        filled = {**item, "change": item["note"],
                  "subject": item.get("subject") or item.get("actor") or ""}
        assert filled["subject"] == "Maren"


class TestTheOpCarriesTheChunkId:
    """A record says which instruction it answers, on itself.

    `DESIGN_SPECIALIST_CONTRACT.md` section 4b. Reconciliation proves an entry
    was encoded by matching ENDPOINT TEXT against the diff, which is why
    `changes_asserted` carries ten endpoint fields it would otherwise not
    need. An id makes that an exact lookup and unblocks the four-field chunk
    format.

    `phase_sources` was the cheaper candidate and lost on measurement:
    emitted on 25% of productive calls, 68% of `encoded` claims cited, never
    once by `director_social` across 91 calls
    (`tools/provenance_coverage.py`) -- because a structure filled in ALONGSIDE
    the work is a second thing to remember. A field inside the object the
    model is already composing is not.
    """

    def test_a_typed_record_keeps_it(self):
        """Typed models STRIP what they do not declare, so every delegated
        channel's record type has to name it or the hand's answer is dropped
        by validation -- which is how `note` was lost earlier today."""
        from llm.schemas import (ArtifactOp, AttireDiff, CharterPublicEvidence,
                                 CommsOp, CourierOp, CrowdOp, PoseEntry,
                                 RoomDef, SceneEntityDef, TellingOp)
        # A superset of the required fields across the ten; each model ignores
        # the keys it does not declare, so this is still real validation and
        # not a construct-without-checking.
        common = {"from_event": 3, "name": "x", "id": "x", "kind": "x",
                  "op": "add", "subject": "x", "text": "x", "who": "x",
                  "what": "x", "location_id": "x", "claim_id": "x"}
        for model in (SceneEntityDef, RoomDef, CommsOp, PoseEntry, CrowdOp,
                      AttireDiff, CharterPublicEvidence, TellingOp, CourierOp,
                      ArtifactOp):
            assert model(**common).from_event == 3, model.__name__

    def test_the_attire_coercion_does_not_eat_it(self):
        """`AttireDiff` runs a before-validator that files unrecognised keys
        under `notes` for commit to resolve against the wardrobe. Untaught, it
        turned the provenance id into a garment handle called
        'from_event' -- a tolerant reader has to be told what its new fields
        are, or its tolerance quietly eats them."""
        from llm.schemas import AttireDiff
        diff = AttireDiff(from_event=3, remove=["wool coat"])
        assert diff.from_event == 3
        assert "from_event" not in diff.notes

    def test_reconciliation_accepts_an_id_over_endpoint_text(self):
        """The point of the field. The manifest entry and the record share no
        subject spelling and no endpoints -- only the id."""
        sd = {"poses": {"Maren": {"posture": "kneeling", "from_event": 7}}}
        omission = {"category": "pose", "subject": "somebody the text does "
                                                   "not name the same way",
                    "change": "she kneels", "event_id": 7}
        assert director._evidence_present(sd, omission) is True

    def test_a_record_naming_nothing_falls_through_to_the_old_check(self):
        """Additive, so it can land ahead of the `sequence` migration: every
        record written before the field existed, and every standing record
        refreshed on its own account, still gets exactly the check it got."""
        sd = {"poses": {"Maren": {"posture": "kneeling"}}}
        assert director._evidence_present(
            sd, {"category": "pose", "subject": "Maren", "change": "kneels",
                 "event_id": 7}) is True
        assert not director._evidence_present(
            sd, {"category": "pose", "subject": "Corin", "change": "kneels",
                 "event_id": 7})

    def test_a_wrong_id_does_not_acquit(self):
        sd = {"poses": {"Maren": {"posture": "kneeling", "from_event": 2}}}
        assert not director._evidence_present(
            sd, {"category": "pose", "subject": "Nobody", "change": "x",
                 "event_id": 7})

    def test_ids_are_found_at_every_channel_shape(self):
        """A delegated channel is a record dict, a list of ops, or a dict of
        lists. Provenance has to be read out of all three or it works on
        poses and silently not on contacts."""
        assert director._cited_event_ids(
            {"poses": {"Maren": {"from_event": 1}}}) == {1}
        assert director._cited_event_ids(
            {"contact_ops": [{"op": "add", "from_event": 2}]}) == {2}
        assert director._cited_event_ids(
            {"conditions": {"Maren": [{"kind": "hurt", "from_event": 3}]}}) == {3}


class TestAnEncodedClaimNeedsSomethingEncoded:
    """`encoded` from a hand whose channels are all empty is not an answer.

    The shared specialist core defines the verdict as "you put it in your
    channels this beat", and warns that "answering honestly is always cheaper
    than answering agreeably". A hand that returns every channel empty and
    still says `encoded` is self-contradictory, and it is the worst available
    answer: the reconciliation seam believes it, buys no repair, and the
    change is lost with no warning anywhere.

    Measured 2026-09-09 (`tools/false_encoded.py`). At the roles' default
    reasoning effort, 0 of 11 `encoded` claims wrote nothing. With
    `reasoning_effort=low` on the five specialists, 2 of 12 did -- both
    `director_objects`, both on a beat where a thing came into being or was
    broken (a hinge hammered apart; a notice nailed up). It returned
    `{"entities": {}}` beside `resolved_events: [{event_id: 1, status:
    "encoded"}]`.

    The guard is not about that lever. The claim is refutable from the
    RESPONSE ALONE -- no diff, no manifest, no scene -- so there is no reason
    to have ever believed it, at any effort level.

    `already_true` and `not_mine` are deliberately still honoured on an empty
    response: both MEAN "correctly wrote nothing".
    """

    def test_an_encoded_claim_with_content_is_kept(self):
        result = {"entities": {"hinge": {"name": "broken hinge"}},
                  "resolved_events": [{"event_id": 1, "status": "encoded"}]}
        assert director._resolved_event_verdicts(result, [1]) == [
            {"event_id": 1, "status": "encoded"}]

    def test_an_encoded_claim_with_every_channel_empty_is_dropped(self):
        result = {"entities": {}, "remove_entities": [], "inventory_ops": [],
                  "sensory_events": [],
                  "resolved_events": [{"event_id": 1, "status": "encoded"}],
                  "notes": []}
        assert director._resolved_event_verdicts(result, [1]) == []

    def test_already_true_survives_an_empty_response(self):
        """It is the verdict that MEANS the ledgers already carry it, so
        writing nothing is the correct behaviour, not a contradiction."""
        result = {"entities": {},
                  "resolved_events": [{"event_id": 1,
                                       "status": "already_true"}]}
        assert director._resolved_event_verdicts(result, [1]) == [
            {"event_id": 1, "status": "already_true"}]

    def test_not_mine_survives_an_empty_response(self):
        result = {"entities": {},
                  "resolved_events": [{"event_id": 1, "status": "not_mine",
                                       "reroute_to": "spatial"}]}
        assert director._resolved_event_verdicts(result, [1]) == [
            {"event_id": 1, "status": "not_mine", "reroute_to": "spatial"}]

    def test_bookkeeping_keys_do_not_count_as_content(self):
        """`notes` and `phase_sources` are the hand talking about its work,
        not the work. Counting them would make the guard inert exactly when a
        model pads its excuse."""
        result = {"entities": {}, "notes": ["could not name the thing"],
                  "phase_sources": {"entities.x": 1},
                  "resolved_events": [{"event_id": 1, "status": "encoded"}]}
        assert director._resolved_event_verdicts(result, [1]) == []

    def test_one_empty_claim_does_not_silence_a_sibling_that_worked(self):
        """The drop is per RESPONSE, and a response either wrote something or
        did not -- so this pins the whole-call semantics rather than letting a
        later reader assume it is per event."""
        result = {"poses": {"Corin": {"posture": "kneeling"}},
                  "resolved_events": [{"event_id": 1, "status": "encoded"},
                                      {"event_id": 2, "status": "encoded"}]}
        assert director._resolved_event_verdicts(result, [1, 2]) == [
            {"event_id": 1, "status": "encoded"},
            {"event_id": 2, "status": "encoded"}]


class TestANoteAloneStillDispatchesAHand:
    """`ledger_notes` stays a dispatch trigger. Design note section 3c-quater.

    Section 3c proposed deleting it and letting `changes_asserted` categories
    route everything. Measured 2026-09-09 with `tools/dispatch_survival.py`
    against the engine's own committed output: of the 13 entries the eight
    hands a categories-only dispatch would have skipped actually produced, 12
    were COMMITTED -- and 11 of 11 on record-shaped channels.

    The reason is structural, which is why this is a guard and not a note.
    `changes_asserted` counts CHANGES. A record-shaped ledger (`poses`,
    `overlays`, `conditions`, `attire`) carries the whole current state of a
    subject and is restated every beat, so the Director correctly files no
    manifest entry when nothing about it changed -- and the manifest therefore
    cannot be what dispatches the hand that keeps it. `body`, whose channels
    are ALL record-shaped, is the hand the manifest can least address and the
    one whose empty-call rate (76%) made it the target.
    """

    def test_every_channel_the_body_hand_keeps_is_record_shaped(self):
        """The premise of the rejection, pinned. If someone adds an
        event-shaped channel to `body` this stops being true, and the
        argument in section 3c-quater has to be re-read rather than
        re-cited."""
        from tools.narrow_interface_coverage import RECORD_SHAPED
        event_shaped = [c for c in director.SPECIALISTS["body"]["channels"]
                        if c not in RECORD_SHAPED]
        assert event_shaped == [], event_shaped


class TestTheManifestSpeaksTheNoteKeysVocabulary:
    """One vocabulary, two fields, one resolver.

    Measured 2026-09-09 over twelve live interpret beats on
    gemini-3.8-flash: the author filed a manifest on 8 of 12 and used four
    category words -- `body`, `objects`, `spatial`, `contact`. Three reached
    no channel, and `tools/dispatch_replay.py --filed-only` scored 8 false
    negatives, 100% of productive calls. Every ruling was correct; only the
    vocabulary missed, because `director_interpret.txt` asks for "one of the
    ledgers named above" and the only names above it are the five hands.

    These pin the resolver rather than the beat, so the guard survives the
    prompt being reworded -- which it is going to be.
    """

    def test_a_hand_named_category_is_carried_into_that_hands_payload(self):
        """Dispatch and the payload slice must agree. Routing the hand while
        slicing its manifest by the old narrow lookup would run a specialist
        and hand it an empty manifest -- a call paid for and told nothing."""
        view = {"manifest": [
            {"category": "objects", "event_id": 1, "subject": "the hinge",
             "change": "the hinge has come apart"},
            {"category": "body", "event_id": 2, "subject": "Corin",
             "change": "Corin has burned his palm"},
        ]}
        got = director._specialist_manifest_slice("objects", view)
        assert [i["event_id"] for i in got] == [1]
        assert [i["event_id"] for i in
                director._specialist_manifest_slice("body", view)] == [2]
        assert director._specialist_manifest_slice("social", view) == []

    # NOTE: no `unrouted_rulings` here, and that is about the REPORT's reach
    # rather than delivery's. `_unrouted_rulings` reads `ledger_notes` keys
    # and `spans`; this beat files its change the older way, as a
    # `changes_asserted` entry -- "the second is what the first becomes when
    # the migration finishes". DELIVERY covers both (`unnamed_work` reads
    # manifest and spans alike), which is the half the owner's ruling is
    # about; the span path's own report is pinned in
    # `TestASpanNamedForNobodyIsEverybodysToDecline`.


# ---------------------------------------------------------------------------
# Ownership, failure isolation, entitlement.
# ---------------------------------------------------------------------------


def test_specialist_role_is_separable_and_follows_default_when_unset(
        monkeypatch):
    """Measurement hook: `_log_usage` keys on the role string, so the
    specialist must call under its OWN role name.

    An unconfigured `director_body` follows `default`, like every other
    blank row. It used to inherit `director` -- defensible on paper (a
    specialist is a hand of the Director) and wrong in practice: a host who
    leaves the six blank is parking them on something cheap, and setting
    `director` to a writing model silently moved all six onto it. Separable
    spend does not require a hidden parent; it comes from the role string,
    which is unchanged either way. See `tests/test_provider_fallbacks.py`."""
    from llm import providers

    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "cheap", "model": "small"},
        "director": {"provider": "frontier", "model": "big"},
    })
    monkeypatch.setattr(providers, "provider",
                        lambda name: {"name": name, "kind": "openai",
                                      "base_url": "http://x", "api_key": ""})

    prov, model, cfg = providers.resolve_role("director_body")
    assert (prov["name"], model) == ("cheap", "small")
    # Explicit configuration still wins.
    monkeypatch.setattr(providers, "agent_models", lambda: {
        "default": {"provider": "cheap", "model": "small"},
        "director": {"provider": "frontier", "model": "big"},
        "director_body": {"provider": "own", "model": "lean"},
    })
    prov, model, cfg = providers.resolve_role("director_body")
    assert (prov["name"], model) == ("own", "lean")


# ---------------------------------------------------------------------------
# Detector parity: both paths must trip the same deterministic detectors.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Scope: the orchestrator measures how much of a job a specialist needs.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# The specialists are SHARED between interpret and resolve.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# The other specialists: ownership and entitlement, one test each.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Parallelism: canonical assembly, failure isolation, cancellation, silence.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# The prose author's OWN sheet is scoped (same mechanism, same rules).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# The delegation must not depend on the model's obedience (run 20).
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Reconciliation repair goes to the CHANNEL'S OWNER, not the prose author.
# ---------------------------------------------------------------------------
#
# The defect (chat 71 turn 10, measured live): an orchestrated resolve took
# 105.5s against the monolith's 14.2s on the same beat, and the single
# avoidable spend was the reconciliation seam's Tier-2 repair -- an EXTRA
# SEQUENTIAL call that re-ran the PROSE AUTHOR on the director role with the
# full-core repair sheet, to re-encode a change the body specialist owned.
# It then still shipped "state_diff still does not encode it after
# self-repair" warnings. Under orchestration the wrong repairer was being
# asked: the specialist that owns the omitted channel answers in ~1s with a
# 1-4k sheet, and is the authority the channel already belongs to. Detection
# is unchanged (the changes_asserted seam stays the one reconciliation
# mechanism); only the REPAIRER changes, and only on the orchestrated path.


def test_category_channel_map_reads_normalized_categories():
    """_manifest_items normalizes categories ('contact' -> 'contacts',
    'substance' -> 'substances', 'pose' -> 'poses') and every reader of
    _CATEGORY_CHANNELS looks up the normalized form -- but for two releases
    the map carried only the raw spellings, so a manifest entry asserting a
    contact, substance or pose change could never reach the scope backstop
    or its owning specialist, silently."""
    for raw, channel in (("contact", "contact_ops"),
                         ("substance", "substance_ops"),
                         ("pose", "poses"),
                         ("station", "stations"),
                         ("inventory_ops", "inventory_ops"),
                         ("clothing", "attire")):
        normalized = director._normalize_omission_category(raw)
        assert director._CATEGORY_CHANNELS.get(normalized) == channel, raw
    # And every channel the map names has an owner in the specialist table.
    for channel in set(director._CATEGORY_CHANNELS.values()):
        assert channel in director._CHANNEL_SPECIALISTS, channel


# ---------------------------------------------------------------------------
# Design note 21: the beat's changes are numbered, and the numbers round-trip.
# ---------------------------------------------------------------------------

def _two_event_resolve():
    """A beat asserting two changes in chronological order: a hand leaves a
    waist, then a coat comes off. Two entries, in that order -- which is
    what the manifest numbering is FOR."""
    return {
        "resolved_event": ("Mara's hand lifts from Bo's waist, and she "
                           "shrugs the wool coat off."),
        "summary": "Hand away, coat off.",
        "changes_asserted": [
            {"category": "contact", "subject": "prior hand-to-waist contact",
             "change": "ended", "actor": "Mara", "actor_part": "hand",
             "target": "Bo", "target_part": "waist"},
            {"category": "attire", "subject": "wool coat",
             "change": "The wool coat is off."},
        ],
        "state_diff": {},
    }


def test_the_engine_numbers_the_manifest_in_narrated_order(temp_db):
    """The ids are the ENGINE's, assigned 1..N in emission order, never the
    model's. A model-authored id could repeat, skip or reorder, and every
    downstream use assumes a dense sequence over exactly this manifest."""
    items = director._manifest_items(_two_event_resolve())
    assert [i["event_id"] for i in items] == [1, 2]
    # Chronology, not category order: the contact ended BEFORE the coat came
    # off, and that is the order the resolve wrote them in.
    assert items[0]["category"] == "contacts"
    assert items[1]["category"] == "attire"


def test_each_specialist_is_handed_only_its_own_numbered_events(temp_db):
    """The slice a specialist receives and the ids it is answerable for come
    from ONE filter -- two spellings would let a specialist be judged on an
    event it never saw."""
    view = {"manifest": director._manifest_items(_two_event_resolve())}
    body = director._specialist_manifest_slice("body", view)
    contact = director._specialist_manifest_slice("contact", view)
    assert [i["event_id"] for i in body] == [2]
    assert [i["event_id"] for i in contact] == [1]


def test_a_verdict_on_an_unhanded_event_is_discarded(temp_db):
    """A specialist cannot acquit an event it was never given. Without this,
    a model echoing the whole manifest back would silence every omission in
    the beat."""
    # The channel content is not what this test is about, but it has to be
    # here: an `encoded` verdict from a response that wrote NOTHING is dropped
    # on its own account (TestAnEncodedClaimNeedsSomethingEncoded), which would
    # make this pass for the wrong reason.
    result = {"poses": {"Corin": {"posture": "kneeling"}},
              "resolved_events": [
        {"event_id": 1, "status": "encoded"},      # granted
        {"event_id": 2, "status": "already_true"},  # NOT granted to this call
        {"event_id": 1, "status": "nonsense"},      # unrecognized verdict
    ]}
    assert director._resolved_event_verdicts(result, [1]) == [
        {"event_id": 1, "status": "encoded"}]


def test_a_failed_specialist_acquits_nothing(temp_db, monkeypatch):
    """Fail-open must not become fail-silent: a specialist whose call died
    leaves its events unaddressed, so the changes it was supposed to encode
    still escalate."""
    dispatch = {"body": {"run": True, "ran": False,
                         "events_resolved": [{"event_id": 1,
                                              "status": "encoded"}]}}
    assert director._index_addressed_events(dispatch) == {}


# ---------------------------------------------------------------------------
# already_true is checked against standing state (design note 21, residual 2
# closed): a defect detector, deliberately not a truth prover.
# ---------------------------------------------------------------------------
#
# The manifest's structure carries no DIRECTION -- whether a change puts the
# garment on or takes it off lives only in its prose, and prose matching is
# the boundary this design exists to get away from. Both end states are
# legitimate no-op targets, so an undirected "is it already so" check is
# vacuous. What IS decidable is whether standing state can support ANY
# definite claim about the subject: the live corruption that motivated this
# (chat 70/71, repaired via attire.release_removed_garments) was a garment
# marked `removed` while still resident in three regions -- a ledger a
# specialist could honestly read and answer `already_true` about a change
# standing state did NOT properly carry. Refusal turns that silence into a
# named defect; everything undecidable falls through to the existing trust.


def test_already_true_verifier_names_each_decidable_defect():
    """Unit coverage of the refusal classes, each a measured ledger-defect
    shape: removed-yet-resident attire; wearing/regions drift; a standing
    position naming a non-room (the category error every spatial query
    answers as unknown); a contained body carrying its own disagreeing
    position (derived-position violation)."""
    om_attire = {"category": "attire", "subject": "Mara"}
    ok, reason = director._verify_already_true(om_attire, {
        "attire": {"Mara": {"wearing": [], "regions": {"torso": {"garments": [
            {"name": "wool coat", "state": "removed"}]}}}}})
    assert not ok and "removed" in reason

    ok, reason = director._verify_already_true(om_attire, {
        "attire": {"Mara": {"wearing": ["wool coat"],
                            "regions": {"torso": {"garments": [
                                {"name": "silk scarf", "state": "worn"}]}}}}})
    assert not ok and "disagree" in reason

    ok, reason = director._verify_already_true(
        {"category": "positions", "subject": "Mara"},
        {"rooms": {"keeper_room": {}},
         "positions": {"Mara": "elevator_control_panel"}})
    assert not ok and "not a room" in reason

    ok, reason = director._verify_already_true(
        {"category": "inventory", "subject": "wool coat"},
        {"contained": {"wool coat": {"in": "Mara"}},
         "positions": {"wool coat": "lamp_room", "Mara": "keeper_room"}})
    assert not ok and "derived" in reason


def test_already_true_verifier_trusts_what_it_cannot_decide():
    """The fall-through side, deliberate rather than by omission: a coherent
    ledger earns the acquittal whichever direction the change went (direction
    is not in the manifest's structure); a legacy entry with underived
    regions is undecidable; contacts and conditions have no decidable
    refusal (either end state is a legitimate no-op); and a broken scene
    fails open."""
    # Coherent wardrobe: worn AND seated -- no refusal, whatever the change.
    ok, _ = director._verify_already_true(
        {"category": "attire", "subject": "Mara"},
        {"attire": {"Mara": {"wearing": ["wool coat"],
                             "regions": {"torso": {"garments": [
                                 {"name": "wool coat",
                                  "state": "worn"}]}}}}})
    assert ok
    # Legacy shape: wearing only, regions never derived -- undecidable.
    ok, _ = director._verify_already_true(
        {"category": "attire", "subject": "Mara"},
        {"attire": {"Mara": {"wearing": ["wool coat"]}}})
    assert ok
    # Contacts: presence and absence are both legitimate no-op end states.
    ok, _ = director._verify_already_true(
        {"category": "contacts", "subject": "contact_end",
         "actor": "Mara", "actor_part": "hand",
         "target": "Bo", "target_part": "waist"},
        {"contacts": []})
    assert ok
    # Conditions: no decidable refusal either.
    ok, _ = director._verify_already_true(
        {"category": "conditions", "subject": "Mara"}, {})
    assert ok
    # Fail open on garbage.
    ok, _ = director._verify_already_true(
        {"category": "attire", "subject": "Mara"},
        {"attire": {"Mara": "not-a-dict"}})
    assert ok


def test_channel_ownership_is_disjoint_within_a_span():
    """A span assembles complementary channels under one domain applier.

    Ownership does not prove that successive spans commute. The executable
    causal program orders those spans; test_causal_program drives the
    remove/recreate, repeated-write and cross-channel counterexamples.
    """
    from agents.director import (
        SPECIALISTS, _CHANNEL_SPECIALISTS, _DELEGATED_CHANNELS,
        _LIST_DELEGATED,
    )

    # Keyed end-state upserts: order across channels cannot matter.
    end_state = {
        "attire", "conditions", "vitals", "overlays", "entities",
        "containment", "scales", "positions", "rooms", "stations", "poses",
        "destruction", "location", "time", "weather",
    }
    # Op lists whose appliers read no other delegated channel's
    # mid-application state (commit-side ledgers of their own).
    independent_ops = {
        "cast_changes", "introductions", "remove_entities",
        "inventory_ops", "artifact_ops", "remove_rooms", "remove_adjacent",
        "crowd_ops", "courier_ops", "telling_ops",
        # An order lands on the REGISTRY, not the scene: it is routed
        # out of the diff before the merge and applied inside the
        # commit, so it reads no other channel's mid-application state.
        "charter_ops",
        "ratified_claims", "contradicted_claims",
        # Observer evidence is stage metadata applied later to independent
        # Charter minds; it reads no scene-diff channel while assembling.
        "public_evidence", "obligations",
        # `apply_comms_ops` records what the beat said and checks nothing
        # against the rooms: every prune is `normalize_scene_comms`, which runs
        # once rooms have settled. That split is deliberate and is what keeps
        # this channel out of the sequential set.
        "comms_ops",
        # `_record_sensory_events` files the beat's one-off signals under the
        # beat that made them, reading no channel mid-application: it checks
        # each event's room against the SETTLED scene, the same split
        # `comms_ops` keeps above. Nothing decays and nothing carries over,
        # so there is no evolving state for it to walk.
        "sensory_events",
        "following_ops", "claim_dispositions", "consequences",
    }
    # Op lists whose appliers walk evolving state sequentially. Two axes on
    # purpose: containment and scales APPLY as end-state upserts (so they
    # sit in end_state above) while still being part of what the
    # sequential appliers READ -- which is an ownership question, asserted
    # separately below. Contact actions ride standing contacts: the merge
    # applies contacts first so contact_ref pointers resolve, then the
    # actions, so they belong with the family of sequential channels.
    sequential_ops = {"contact_ops", "substance_ops", "contact_action_ops"}
    sequential_read_set = sequential_ops | {"containment", "scales"}

    # 1. One owner per channel -- no channel under two specialists.
    seen = {}
    for name, spec in SPECIALISTS.items():
        for channel in spec["channels"]:
            assert channel not in seen, (
                f"{channel} owned by both {seen[channel]} and {name}")
            seen[channel] = name

    # 2. Every delegated channel is classified EXACTLY once. A new channel
    #    failing here is the forcing function: decide which class it is in
    #    -- and if it is sequential-stateful, put it with its family's
    #    owner -- before shipping it.
    classified = end_state | independent_ops | sequential_ops
    for channel in _DELEGATED_CHANNELS:
        assert channel in classified, (
            f"unclassified delegated channel {channel!r}: decide whether "
            "its application is end-state, independent ops, or "
            "sequential-coupled before shipping it")
        assert (channel in end_state) + (channel in independent_ops) + (
            channel in sequential_ops) == 1, channel

    # 3. The sequential appliers AND everything they read share ONE owner,
    #    so within-beat chronology is one specialist's own list order.
    family_owners = {_CHANNEL_SPECIALISTS[c] for c in sequential_read_set
                     if c in _CHANNEL_SPECIALISTS}
    assert family_owners == {"contact"}, family_owners

    # 4. Shape agreement: the op classes are lists, the end states are not
    #    (destruction is the one dict-or-null exception, asserted as such).
    for channel in independent_ops | {"contact_ops", "substance_ops"}:
        if channel in _DELEGATED_CHANNELS:
            assert channel in _LIST_DELEGATED, channel
    for channel in end_state - {"destruction"}:
        assert channel not in _LIST_DELEGATED, channel


# ---------------------------------------------------------------------------
# Every delegated family must be REACHABLE by a category.
# ---------------------------------------------------------------------------

#: Legacy manifest categories may still use a family alias. Current causal
#: ledgers name exact channels, so every delegated channel is directly
#: reachable and this table is compatibility documentation only.
_UNREACHABLE_BY_DESIGN = {
    "remove_entities": "reached as 'entities'",
    "remove_rooms": "reached as 'rooms'",
    "remove_adjacent": "reached as 'adjacency'",
    "crowd_ops": "traffic ops surface, not a manifest category",
    "courier_ops": "traffic ops surface, not a manifest category",
    "telling_ops": "traffic ops surface, not a manifest category",
    # An order is a dispatch, not a change this beat's prose asserts: what
    # the manifest enumerates is what CHANGED, and an errand changes
    # nothing until the body has walked it, one room at a time, on the
    # beats after.
    "charter_ops": "traffic ops surface, not a manifest category",
    # Adjudications of a CARRIED claim, not changes the beat's prose
    # asserts: they answer "was this hearsay true?", which the manifest --
    # an enumeration of what this beat changed -- has nothing to say about.
    # They reach their owner through the claim lane, never the manifest.
    "ratified_claims": "claim adjudication, not a beat change",
    "contradicted_claims": "claim adjudication, not a beat change",
    "public_evidence": "observer metadata, not an objective beat change",
    # A ONE-BEAT SIGNAL IS NOT A PERSISTENT CHANGE, and the manifest says so
    # of itself: it enumerates "every PERSISTENT physical change your
    # resolved_event asserts as COMPLETED". A bang leaves nothing standing
    # to enumerate -- the beat number is its whole lifetime -- so a category
    # for it would file a thing that expires in a ledger built for things
    # that do not, and the omission detector would report it missing from
    # the next scene for ever. It reaches its hand the other way the
    # dispatch offers: a `ledger_notes` line keyed by the channel name,
    # which `note_key_targets` routes by channel exactly as it routes one
    # keyed by a hand.
    "sensory_events": "a one-beat signal, not a persistent change; reaches "
                      "the objects hand through a ledger note keyed by the "
                      "channel",
}


def test_every_delegated_family_is_reachable_by_a_category():
    """A channel no category can name is a change that lands NOWHERE: no
    specialist is handed it, so nobody can encode it, so the seam detects an
    omission on every beat containing it and buys a repair from a mind that
    never saw the event.

    Measured twice. contacts/substances/poses/stations were dead this way
    from 8.2 (the category map was keyed on raw spellings while every reader
    looked up the normalized form). `overlays` and `vitals` were dead the
    same way while the body specialist OWNED them -- which is what a live
    beat's 'slight quiver' and 'heavy heated breathing' fell through, at
    49.2s of repair for two events nobody could have encoded.

    Adding a delegated channel now costs a decision here: give it a
    category, or say in _UNREACHABLE_BY_DESIGN why it needs none.
    """
    reachable = set(director._DELEGATED_CHANNELS)
    for name, spec in director.SPECIALISTS.items():
        for channel in spec["channels"]:
            assert channel in reachable or channel in _UNREACHABLE_BY_DESIGN, (
                f"{name} owns {channel!r}, but no manifest category reaches "
                f"it -- a change categorized there would be handed to no "
                f"specialist and repaired by a mind that never saw it. Add a "
                f"category to _CATEGORY_CHANNELS or record why it needs none."
            )


def test_every_category_route_lands_on_a_real_owned_channel():
    """The other direction: a category mapping to a channel no specialist
    owns routes an event to nobody just as silently."""
    owners = {c for s in director.SPECIALISTS.values() for c in s["channels"]}
    for category, channel in director._CATEGORY_CHANNELS.items():
        assert channel in owners, (
            f"category {category!r} routes to {channel!r}, which no "
            f"specialist owns")


def test_every_alias_normalizes_onto_a_routed_category():
    """An alias is the Director's own vocabulary. One that normalizes to a
    category with no route is the same silent drop, arriving through a
    spelling instead of a channel."""
    core_owned = {"time", "transit", "other"}
    aliases = director._ling("_OMISSION_CATEGORY_ALIASES")
    for alias, normalized in aliases.items():
        assert (director.manifest_category_targets(normalized)
                or normalized in core_owned), (
            f"alias {alias!r} normalizes to {normalized!r}, which reaches "
            f"neither a specialist channel nor a core-owned category")


# ---------------------------------------------------------------------------
# The omitted-thought ledger: says what was left out, commits nothing.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# One real change is one numbered event; one garment is one record.
# ---------------------------------------------------------------------------

def _live_duplicating_resolve():
    """The live beat's exact manifest shape (chat 71, v26670): two garments
    removed, and the SAME two garments separately asserted as entities
    created on the floor -- which is what the commit seam does by itself."""
    return {
        "resolved_event": "Elyra strips the sash and shorts away.",
        "summary": "Undressed.",
        "changes_asserted": [
            {"category": "contact", "subject": "Elyra Voss",
             "change": "hand leaves Hinami stomach", "actor": "Elyra Voss",
             "actor_part": "hand", "target": "Hinami",
             "target_part": "stomach"},
            {"category": "attire", "subject": "Hinami",
             "change": "utility sash removed"},
            {"category": "attire", "subject": "Hinami",
             "change": "travel shorts removed"},
            {"category": "entities", "subject": "utility sash",
             "change": "created in room, placed on floor"},
            {"category": "entities", "subject": "travel shorts",
             "change": "created in room, placed on floor"},
        ],
        "state_diff": {},
    }


def test_a_derived_entity_event_folds_into_its_attire_event():
    """A garment coming off and the same garment appearing on the floor are
    one change described twice. Numbered separately they route to two
    owners, each of which faithfully authors its own record -- which is
    exactly how the live scene reached five entity records for two
    garments. Ids stay a dense sequence after the fold."""
    items = director._manifest_items(_live_duplicating_resolve())
    assert [i["category"] for i in items] == ["contacts", "attire", "attire"]
    assert [i["event_id"] for i in items] == [1, 2, 3]
    # The fold is remembered, not silently dropped.
    assert all("entities" in i.get("also_described_as", [])
               for i in items if i["category"] == "attire")


def test_positions_and_poses_are_not_derived_of_attire():
    """Three different facts about a body, not three descriptions of one --
    the fold must not reach them."""
    out = {"changes_asserted": [
        {"category": "attire", "subject": "Hinami",
         "change": "travel shorts removed"},
        {"category": "poses", "subject": "Hinami",
         "change": "legs lifted, knees parted"},
        {"category": "positions", "subject": "Hinami",
         "change": "moved onto the platform"},
    ]}
    items = director._manifest_items(out)
    assert [i["category"] for i in items] == ["attire", "poses", "positions"]
    assert [i["event_id"] for i in items] == [1, 2, 3]


def test_every_hand_can_name_a_worn_garment(temp_db):
    """A worn garment lives only in sc.attire, so a specialist that needed
    to name one could not -- and invented an entity instead (the live
    `hinami_shorts`, whose own note admitted it). Identity only: the name
    and whose body it is on, never the wardrobe's state."""
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["attire"] = {"Mara": {"wearing": ["wool coat", "boots"]}}
    ctx = _make_ctx(temp_db, scene=scene)
    view = {"source": "resolved_beat", "prose": "x", "dialogue": [],
            "player": "Mara", "cast": [], "declared_actions": [],
            "dice": [], "manifest": []}
    for name in ("contact", "objects"):
        payload = director._specialist_payload(name, ctx, scene, view, {})
        assert {"name": "wool coat", "worn_by": "Mara"} \
            in payload["worn_garments"], name
        # Identity only -- no wardrobe state crosses.
        assert all(set(g) == {"name", "worn_by"}
                   for g in payload["worn_garments"]), name


# ---------------------------------------------------------------------------
# A forwarding note beats the category map.
# ---------------------------------------------------------------------------


def test_an_address_on_anything_but_a_decline_is_ignored(temp_db):
    """Only a decline forwards. An `encoded` verdict carrying an address is
    a model contradicting itself, and the engine keeps the encoding."""
    # Carries channel content for the same reason as
    # test_a_verdict_on_an_unhanded_event_is_discarded: an empty response's
    # `encoded` is dropped on its own account, and this test is about the
    # ADDRESS, not the content.
    result = {"poses": {"Corin": {"posture": "kneeling"}},
              "resolved_events": [
        {"event_id": 1, "status": "encoded", "reroute_to": "spatial"}]}
    assert director._resolved_event_verdicts(result, [1]) == [
        {"event_id": 1, "status": "encoded"}]


def test_dialogue_reaches_only_the_hands_a_speech_act_can_write(temp_db):
    """Saying a thing is not a physical action.

    The beat's dialogue rode in the COMMON payload, so every hand got it
    whether or not any channel they own could be written by somebody talking.
    Three of the five cannot -- `body`, `contact` and `objects` own physical
    ledgers, and
    a transcript is material they can only echo, which is this fan-out's
    measured failure mode rather than a hypothetical one. Measured over chat
    78: 27% of the beat text every hand received.

    The three that DO keep it each have a named reason in the channel table:
    a name is given by being said (`introductions`), a line carried by a
    device IS the op (`comms_ops`), and a claim is made and disputed in
    speech (`telling_ops`, `ratified_claims`, `contradicted_claims`).
    """
    scene = json.loads(json.dumps(BASE_SCENE))
    ctx = _make_ctx(temp_db, scene=scene)
    view = {"source": "resolved_beat", "prose": "x",
            "dialogue": [{"speaker": "Mara", "exact_quote": "\"Hello.\""}],
            "player": "Mara", "cast": [], "declared_actions": [],
            "dice": [], "manifest": []}

    for name in ("social", "spatial"):
        payload = director._specialist_payload(name, ctx, scene, view, {})
        assert payload.get("dialogue_log"), name
    for name in ("body", "contact", "objects"):
        payload = director._specialist_payload(name, ctx, scene, view, {})
        assert "dialogue_log" not in payload, name
        # And the beat does NOT reach them by another door either. This used
        # to assert the opposite -- that the prose carried what speech made
        # happen -- which was the justification for withholding the
        # transcript. With the prose gone the reasoning inverts: these hands
        # get neither, because a spoken line is not something their channels
        # can encode, and what they must encode arrives as an instruction.
        assert "resolved_event" not in payload, name


def test_who_reads_dialogue_is_derived_from_the_channel_table():
    """Not a per-specialist list. A channel that moves between hands takes
    its answer with it, so this cannot drift out of agreement with
    `SPECIALISTS` the way a second copy of the rule would."""
    from agents.director import (
        SPECIALISTS, SPEECH_WRITTEN_CHANNELS, reads_dialogue)

    for name, spec in SPECIALISTS.items():
        expected = bool(set(spec["channels"]) & SPEECH_WRITTEN_CHANNELS)
        assert reads_dialogue(name) is expected, name
    # Every speech-written channel is owned by somebody, or the set has a
    # name in it that no longer exists.
    owned = {c for s in SPECIALISTS.values() for c in s["channels"]}
    assert SPEECH_WRITTEN_CHANNELS <= owned


# ---------------------------------------------------------------------------
# A channel that belongs to ONE stage.
#
# Measured, chat 98 turns 6, 26 and 30: the social specialist emitted
# `public_evidence` at `director_interpret`, whose granted scope was
# ['cast_changes', 'introductions', 'world_facts'] on two of them and
# ['introductions', 'world_facts'] on the third. Every notice said "Content
# was kept (fail-open); the scope gate under-granted and should be widened if
# this recurs", and every one of those three recorded steps carries
# `state_assertions: {}` -- nothing was kept. Both halves of the notice were
# wrong, and acting on the second half would have granted the channel at a
# stage that has not adjudicated anything yet.
# ---------------------------------------------------------------------------

def test_a_stage_only_channel_is_not_a_state_diff_field():
    """The structural fact underneath: at interpret a specialist's channels
    merge into `state_assertions`, which is a `StateDiff` -- and
    `public_evidence` is not one of its fields, so a value written there is
    dropped by `validated_player_state_assertions` a few lines later. That is
    why the fail-open kept nothing."""
    from llm.schemas import DirectorResolve, StateDiff, _fields
    from agents.director import CHANNEL_STAGES

    assert "public_evidence" not in set(_fields(StateDiff))
    assert "public_evidence" in set(_fields(DirectorResolve))
    for channel, stages in CHANNEL_STAGES.items():
        assert channel not in set(_fields(StateDiff)) or "interpret" in stages


def test_every_stage_only_channel_names_a_real_channel():
    """The table is level with the specialist registry, the way the three
    channel registries already are."""
    from agents.director import CHANNEL_STAGES, SPECIALISTS

    owned = {channel for spec in SPECIALISTS.values()
             for channel in spec["channels"]}
    for channel, stages in CHANNEL_STAGES.items():
        assert channel in owned, channel
        assert stages and set(stages) <= {"interpret", "resolve"}, channel


def test_an_existing_entity_interior_is_canonicalized_before_fanout():
    scene = {
        "rooms": {
            "alley": {"name": "Alley", "adjacent": []},
            "tardis_console": {
                "name": "TARDIS Console Room", "parent_entity": "tardis"},
        },
        "entities": {"tardis": {
            "name": "TARDIS", "interior_rooms": ["tardis_console"]}},
        "positions": {"tardis": "alley"},
    }
    out = {"ledgers": [{
        "chrono_id": 1, "item_id": 1, "object_name": "TARDIS",
        "source_entity_id": "persona:primary", "source_event_id": "raw",
        "authority_mode": "world_author", "kind": "action",
        "event": "enters the TARDIS", "movement": {
            "mover": "self", "to_room": "TARDIS", "arrives": True},
        "categories": ["rooms", "positions"],
    }]}
    director.normalize_causal_ledger(out)
    director._canonicalize_interior_movements(scene, out)
    assert out["ledgers"][0]["movement"]["to_room"] == "tardis_console"
    assert out["sequence"][0]["movement"]["to_room"] == "tardis_console"


def test_an_identity_id_is_canonicalized_before_spatial_fanout():
    scene = {
        "rooms": {"alley": {"name": "Alley", "adjacent": []}},
        "entities": {"tardis": {
            "name": "TARDIS", "interior_rooms": []}},
        "positions": {"tardis": "alley", "Hinami": "alley"},
    }
    out = {"ledgers": [{
        "source_entity_id": "persona:10",
        "movement": {"mover": "persona:10", "to_room": "TARDIS",
                     "arrives": True},
    }]}
    director._canonicalize_interior_movements(
        scene, out, {"persona:10": "Hinami"})
    assert out["ledgers"][0]["movement"] == {
        "mover": "Hinami", "to_room": "tardis", "arrives": True}


class TestTwoKnownNamesInOneStringAreTwoNames:
    """The sheets say to write a list. A model that reaches for a separator
    instead used to lose the whole span in silence: "body, objects" folds to
    no known category, routes to no hand, and the change the beat asserted
    reaches nobody.

    This is not the guessing `_note_key_forms` refuses. Nothing is inferred
    from wording -- the string is split on punctuation, and a part counts only
    when it IS a category the engine already routes, so this can recognise
    names the engine owns and can never invent a route.

    THE TEST IS `any`, NOT `all`, and that changed on the owner's objection:
    "the magic words that summon the specialists are right there! Is there
    really no way for code to recover them because it was formatted slightly
    wrong?" Under `all`, one invented word discarded every real name beside
    it, and the asymmetry was indefensible once written down -- identical
    content, one comma's difference:

        ['body', 'objects', 'geography']  ->  body, objects
        'body, objects, geography'        ->  NOTHING

    `any` is evidence rather than a guess: a string in which at least one part
    names a family the engine routes is a model writing NAMES; one in which no
    part does is a model writing PROSE. The prose case is unchanged and is
    pinned below.
    """

    def _cats(self, raw):
        out = director._span_items({"sequence": [
            {"type": "action", "attempt": "x", "category": raw, "note": "n"}]})
        return out[0].get("categories"), director.span_owners(out[0])

    def test_a_separator_a_model_reaches_for_is_two_names(self):
        for raw in ("body, objects", "body and objects", "body/objects",
                    "body; objects", "body|objects"):
            cats, owners = self._cats(raw)
            assert cats == ["body", "objects"], raw
            assert owners == ["body", "objects"], raw

    def test_three_of_them_are_three(self):
        cats, owners = self._cats("body, objects, spatial")
        assert cats == ["body", "objects", "spatial"]
        assert owners == ["body", "objects", "spatial"]

    def test_a_known_name_is_recovered_from_beside_an_unknown_one(self):
        """This asserted the opposite until the owner objected, and its stated
        reason was that echoing the whole string back is "clearer feedback
        than half a route". The ruling that overturns it: "a ledger not
        reaching a specialist is as good as that ledger not existing" -- so
        half a route DELIVERS a change where no route loses it, and the
        unknown half is still reported by name, which is the feedback the old
        rule was paying for.

        Routability, not foldability, still decides: `_normalize_omission_
        category` passes an unknown name straight through, so nothing here
        accepts a part merely because it is non-empty."""
        cats, owners = self._cats("body, geography")
        assert cats == ["body", "geography"]
        assert owners == ["body"]

    def test_the_list_and_the_comma_spellings_now_agree(self):
        """The asymmetry that made the case: same content, same answer,
        whatever punctuation the model reached for."""
        assert self._cats("body, objects, geography") == self._cats(
            ["body", "objects", "geography"])

    def test_free_prose_is_never_split_into_categories(self):
        """The failure the routability test exists to prevent. This string
        contains "and", so a looser rule would file two ledger families named
        after halves of a sentence."""
        cats, owners = self._cats(
            "the belt comes off and lands on the bench")
        assert cats == ["the belt comes off and lands on the bench"]
        assert owners == []

    def test_a_single_name_is_untouched(self):
        cats, owners = self._cats("body")
        assert cats == ["body"] and owners == ["body"]

    def test_a_real_list_is_still_the_preferred_shape(self):
        """The clause asks for this and the worked example shows it; the split
        above is the fallback, not the contract."""
        cats, owners = self._cats(["objects", "spatial"])
        assert cats == ["objects", "spatial"]
        assert owners == ["objects", "spatial"]


class TestAHandIsAnswerableForTheWorkItemsItGot:
    """`event_ids` is the grant a verdict is checked against, and it was built
    from the RETIRED channel.

    `_resolved_event_verdicts` discards any id outside the grant, so a grant
    built from `changes_asserted` alone -- a field neither sheet asks for, and
    which measured 0 entries on all 12 beats of every live run since it was
    retired -- is empty on every beat, and every verdict a hand returns is
    thrown away. `events_addressed` is then `{}`, and per-hand acquittal, the
    seam that keeps a half-settled span owed, cannot run at all.

    Measured 2026-09-10, the padlock beat: the Director filed ONE span
    categorized `["objects", "spatial"]`, both hands were handed it, `objects`
    answered `encoded` and `spatial` answered `not_mine` with a reason. Three
    correct structured facts, and that beat's orchestration record read
    `events_addressed: {}`.
    """

    VIEW = {"spans": [
        {"event_id": 1, "categories": ["objects", "spatial"],
         "category": "objects", "attempt": "padlock the forge door shut",
         "note": "the forge door is shut and padlocked"},
        {"event_id": 2, "categories": ["body"], "category": "body",
         "note": "the belt leaves her waist"},
    ]}

    def test_the_grant_is_the_hands_own_spans(self):
        granted = director._granted_event_ids("objects", self.VIEW)
        assert granted == [1]
        assert director._granted_event_ids("spatial", self.VIEW) == [1]
        assert director._granted_event_ids("body", self.VIEW) == [2]
        # A hand no span reached is answerable for nothing, which is a
        # different fact from a hand whose grant was never built.
        assert director._granted_event_ids("social", self.VIEW) == []

    def test_a_verdict_on_a_granted_span_survives(self):
        """The whole point: without the grant this returned {} and the hand's
        answer vanished."""
        kept = director._resolved_event_verdicts(
            {"entities": {"padlock": {"name": "padlock"}},
             "resolved_events": [{"event_id": 1, "status": "encoded"}]},
            director._granted_event_ids("objects", self.VIEW))
        assert kept and kept[0]["status"] == "encoded"

    def test_a_manifest_id_is_still_granted_beside_the_spans(self):
        """One id space, so this is a union and never a renumbering: spans
        take 1..N and the manifest continues past the ceiling."""
        view = dict(self.VIEW)
        view["manifest"] = [{"event_id": 3, "category": "objects",
                             "subject": "hinge", "change": "it came apart"}]
        assert director._granted_event_ids("objects", view) == [1, 3]

    def test_a_span_neither_owner_settles_stays_owed(self):
        """And the reason the grant has to be right: acquittal reads the index
        the grant produces, so an empty grant acquitted nothing AND owed
        nothing -- silence that looks exactly like a beat with no work."""
        dispatch = {
            "objects": {"ran": True, "events_resolved": [
                {"event_id": 1, "status": "encoded"}]},
            "spatial": {"ran": True, "events_resolved": [
                {"event_id": 1, "status": "not_mine"}]},
        }
        index = director._index_addressed_events(dispatch)
        assert set(index[1]["by_hand"]) == {"objects", "spatial"}
        out = {"orchestration": {"events_addressed": index}}
        omission = {"event_id": 1, "category": "objects",
                    "subject": "forge door", "change": "it is padlocked"}
        owed, acquitted, _refused = director._acquit_addressed_events(
            out, [omission], {})
        assert owed == [omission] and acquitted == []


class TestADialRefusesTheSpanAndTheRecordWithIt:
    """The owner's ruling, 2026-09-10: "Either it mints the window or door or
    it refuses the whole span depending on player authority level."

    The refuse arm did neither. `apply_player_authority` moves two labels --
    the claim's scope to `intent`, the element's commitment to `contestable` --
    and it runs AFTER the fan-out, so the hands have already written the
    record. Measured on one beat under both dials, everything else equal:

        world_author  downgrades=0  state_assertions {"rooms":{"bay":{"desc":"dark now"}}}
        actor_only    downgrades=1  state_assertions {"rooms":{"bay":{"desc":"dark now"}}}

    Byte-identical. Under hard mode the player's world assertion was relabelled
    an intention and the world kept the fact.
    """

    #: The player asserts a change to the world; the prose Director writes
    #: it, and the encoder files the room edit under the event.
    PROSE = "The lamp above the door goes out, and the bay goes dark."
    LAMP = encoder_event(
        "the lamp above the door goes out",
        transforms=[{"item": "bay", "patch": {"rooms": {
            "bay": {"name": "Bay", "desc": "dark now"}}}}])

    def _beat(self, temp_db, monkeypatch, mode):
        from story.scene import set_player_authority
        monkeypatch.setattr(director, "_agent_json", _fake_agent([], {
            "director_prose": {"prose": self.PROSE},
            "director_specialist": {"events": [self.LAMP]},
        }))
        ctx = _make_ctx(temp_db, player_input="the lamp goes out")
        set_player_authority(ctx.chat.id, mode)
        ctx.director_interpret = None
        return ctx, director.director_interpret(ctx, nonce=0)

    def test_world_author_is_untouched(self, temp_db, monkeypatch,
                                       prose_director):
        """The default, and the property that matters most to everyone who
        does not want hard mode: it grants everything, so there is nothing to
        void and an existing story means tomorrow what it meant yesterday."""
        _ctx, out = self._beat(temp_db, monkeypatch, "world_author")
        assert not out.get("authority_downgrades")
        assert not out.get("voided_spans")
        assert out["state_assertions"]["rooms"]["bay"]["desc"] == "dark now"

    #: THE PROSE DIRECTOR CANNOT REFUSE YET (UNBUILT_PIPELINE.md §1.1, the
    #: prose-only gaps). The causal author filed a world assertion as an
    #: `event` element, which is what claim extraction reads as beyond the
    #: player's own conduct; the encoder has no such field, so its row reads
    #: as the player's own act -- granted at every rung -- and no downgrade
    #: is recorded. And a prose record carries no `from_event`, so a void
    #: would drop nothing even if one were. Strict: the day either closes,
    #: these say so.
    _PROSE_CANNOT_REFUSE = pytest.mark.xfail(
        strict=True,
        reason="the prose Director files a player's world assertion as their "
               "own act, and its records cite no span (UNBUILT_PIPELINE §1.1)")

    @_PROSE_CANNOT_REFUSE
    def test_a_refused_span_takes_the_record_with_it(self, temp_db,
                                                     monkeypatch,
                                                     prose_director):
        for mode in ("explicit_outcomes", "actor_only"):
            _ctx, out = self._beat(temp_db, monkeypatch, mode)
            assert len(out["authority_downgrades"]) == 1, mode
            assert out["voided_spans"] == [
                {"event_id": 1, "dropped": ["rooms.bay"]}], mode
            assert out["state_assertions"].get("rooms") == {}, mode
            assert out["onset_state_assertions"].get("rooms") == {}, mode

    @_PROSE_CANNOT_REFUSE
    def test_the_refusal_is_reported_never_silent(self, temp_db, monkeypatch,
                                                  prose_director):
        """A refused assertion must not silently vanish -- the player wrote it
        for a reason. The downgrade already reaches the Director in the same
        beat; the DROPPED RECORD is a second fact and needs saying too, or the
        step shows a channel that is empty with no reason anywhere."""
        ctx, _out = self._beat(temp_db, monkeypatch, "actor_only")
        notes = [str(w) for w in ctx.warnings]
        assert any("PLAYER AUTHORITY" in n and "refused whole" in n
                   for n in notes), notes

    def test_a_span_no_record_cites_voids_nothing(self):
        """The bound on the guarantee, stated because it is real: `from_event`
        is how a record says which span it settles, so a hand that omits it
        leaves a record nothing can attribute. Same limit the deferred-phase
        floor has always had, and the reason provenance went ON the record."""
        assertions = {"rooms": {"bay": {"name": "Bay", "desc": "dark now"}}}
        dropped = director.void_span_records(assertions, [1])
        assert dropped == []
        assert assertions["rooms"]["bay"]["desc"] == "dark now"

    def test_every_owner_of_a_shared_span_loses_its_half(self):
        """WHOLE is the rule. A span may be owned by several hands, and
        voiding one hand's record while another's stands is exactly the
        half-settlement the ruling was given to end. They cite one id, so one
        pass reaches all of them."""
        assertions = {
            "entities": {"shutter": {"name": "shutter", "from_event": 1}},
            "rooms": {"forge": {"name": "Forge", "from_event": 1}},
            "poses": {"Corin": {"posture": "standing", "from_event": 2}},
        }
        dropped = director.void_span_records(assertions, [1])
        assert assertions["entities"] == {} and assertions["rooms"] == {}
        # A span nobody refused is untouched.
        assert set(assertions["poses"]) == {"Corin"}
        assert {path for path, _ in dropped} == {"entities.shutter",
                                                 "rooms.forge"}

    def test_the_join_is_position_to_span_id(self):
        """A downgrade names a sequence POSITION; a record cites a SPAN id.
        Both spaces are real and neither is the other -- the lesson of the
        beat where a hand cited the phase graph because the payload carried
        two fields called `event_id`."""
        out = {"sequence": [
            {"type": "speech", "text": "hello"},
            {"type": "action", "attempt": "x", "category": "body",
             "note": "n"},
            {"type": "event", "description": "the lamp goes out",
             "category": "spatial", "note": "m"},
        ]}
        # position 2 is the second SPAN (id 2), not the second element.
        assert director.voided_span_ids(
            out, [{"claim_id": "claim:2:event"}]) == [2]
        assert director.voided_span_ids(
            out, [{"claim_id": "claim:1:0"}]) == [1]
        # An element that became no span addressed no ledger, so nothing
        # cites it and there is nothing to void.
        assert director.voided_span_ids(
            out, [{"claim_id": "claim:0:0"}]) == []
        assert director.voided_span_ids(out, []) == []


class TestASpansRecordsArePairedByWhereTheyHappen:
    """The owner, 2026-09-10: "We need some sort of reconciliation code that
    pairs things together based on where they are supposed to happen."

    `span_records` says which records are one event's outcome; it cannot say
    which of them are the same THING within it, because the apron and the hook
    both cite the span that hung one on the other. Place answers that, and it
    is the right key because the engine ISSUES it -- a room id, a doorway's
    room pair. Names are the model's and drift; the folds in this tree all
    match on names because until the span id there was nothing else to match
    on, and one of them admits matching "coat" against "coat rack".

    A grouping, never a decision. Two lamps in a room are two lamps.
    """

    SCENE = {"positions": {"Corin": "forge", "padlock": "forge"}}
    DIFF = {
        "entities": {"padlock": {"name": "padlock", "from_event": 1}},
        "rooms": {
            "forge": {"name": "Forge", "adjacent": [
                {"to": "well", "barrier": "closed_door", "from_event": 1}]},
            "well": {"name": "Well", "adjacent": [
                {"to": "forge", "barrier": "closed_door", "from_event": 1}]},
        },
    }

    def test_one_doorway_is_one_place_not_two_edges(self):
        """Both mirrored edges of a doorway carry the same token, sorted, so
        the two sides of one way cannot read as two places."""
        places = director.span_pairings(self.DIFF, self.SCENE)[1]
        assert sorted(places) == ["room:forge", "way:forge|well"]
        assert len(places["way:forge|well"]) == 2

    def test_a_thing_in_a_room_meets_the_doorway_of_that_room(self):
        """The padlock stands in the forge and the door lies between the forge
        and the well, so exactly by place they never met. A way belongs to each
        room it joins, which costs no new vocabulary and is what lets the two
        halves of one act land together."""
        rooms = director.span_colocations(self.DIFF, self.SCENE)[1]
        assert set(rooms) == {"forge", "well"}
        assert [p for p, _c, _r in rooms["forge"]] == [
            "entities.padlock", "rooms.forge.adjacent[0]",
            "rooms.well.adjacent[0]"]
        # The padlock is not in the well, and does not appear there.
        assert "entities.padlock" not in [p for p, _c, _r in rooms["well"]]

    def test_a_record_the_engine_cannot_place_pairs_with_nothing(self):
        """Silence, never a guess. An unplaced entity has no room, and parking
        it under one would weld it to whatever else was there."""
        diff = {"entities": {"ghost": {"name": "ghost", "from_event": 1}}}
        assert director.span_pairings(diff, {"positions": {}}) == {}
        assert director.span_colocations(diff, {"positions": {}}) == {}

    def test_this_beats_move_wins_over_where_it_stood(self):
        """A subject the beat moved pairs where it now IS, so a record about
        the arrival does not group with the room it left."""
        sc = {"positions": {"Corin": "forge"}}
        diff = {"positions": {"Corin": "well"},
                "poses": {"Corin": {"posture": "kneeling", "from_event": 1}}}
        rooms = director.span_colocations(diff, sc)[1]
        assert set(rooms) == {"well"}

    def test_separate_spans_are_never_pooled(self):
        """The span bounds the question. Two acts in one room stay two acts,
        which is the half of the key that names are no help with at all."""
        sc = {"positions": {"lamp": "forge", "stool": "forge"}}
        diff = {"entities": {"lamp": {"name": "lamp", "from_event": 1},
                             "stool": {"name": "stool", "from_event": 2}}}
        grouped = director.span_colocations(diff, sc)
        assert [p for p, _c, _r in grouped[1]["forge"]] == ["entities.lamp"]
        assert [p for p, _c, _r in grouped[2]["forge"]] == ["entities.stool"]

    def test_the_room_record_itself_is_placed(self):
        diff = {"rooms": {"forge": {"name": "Forge", "desc": "dark",
                                    "from_event": 1}}}
        assert sorted(director.span_pairings(diff, {})[1]) == ["room:forge"]


class TestTheBeatNumbersTheThingsItTouches:
    """The owner, 2026-09-10: "the director main stage could also emit
    temporary item ids for the persons places or things mentioned in input
    that get attached to all ledgers that involve that item ... this id
    actually never gets exposed to the specialists ... it should allow the
    reconciliation of multiple interactions with a freshly minted object to be
    just that."

    THE GAP, and neither the span id nor place reaches it. A hand's payload is
    built from the scene AS IT STOOD BEFORE THE BEAT, and the hands run in
    parallel -- so a thing minted in span 1 exists for nobody, and every later
    interaction with it is an interaction with something the acting hand cannot
    see. Its only outcomes are to mint a second copy or decline. Only the
    Director can supply the identity, because only the Director reads the input
    and can say the console in the last clause is the console from the third.

    A NUMBER, and the model's own. The reasons a span id must be engine-issued
    -- dense, ordered, unique, because every downstream use assumes a dense
    sequence -- do not carry: a temp item id need only be CONSISTENT, repeats
    are the entire point, and skips and order mean nothing. It also removes
    what made a string unusable: across 34 measured Director calls the same
    model wrote `sword_belt` and `sword belt` for one object.

    Measured live on the first try (gemini-3.8-flash): "I tell Sera to wait
    here, then I step into the tardis, pull the door shut behind me, tell her
    she can't hear me now, and pull the levers on the console" numbered Sera 1
    across spans 1 AND 4, tardis 2 across spans 2 and 3, door 3, console 4,
    levers 5. And "I set the crate down by the forge door, open the crate, and
    take the mallet out of it" carried crate 1 through all three spans --
    including the one where the input says only "it".
    """

    def _spans(self, sequence):
        return director._span_items({"sequence": sequence})

    def test_the_numbers_are_kept_and_never_reach_a_hand(self):
        """The owner's constraint, enforced rather than asked for: they ride
        under a leading underscore, and `_specialist_payload` already strips
        every such key from a span. A number in a payload is a number the model
        will try to cite -- one spent 16,180 output tokens doing exactly
        that."""
        span, = self._spans([
            {"type": "action", "attempt": "I step into the tardis",
             "category": "spatial", "note": "inside",
             "items": [{"id": 2, "name": "tardis"}]}])
        assert span["_items"] == [{"id": 2, "name": "tardis"}]
        assert "items" not in span
        assert not [k for k in director._without_private_keys(span)
                    if str(k).startswith("_")]
        assert "_items" not in director._without_private_keys(span)

    def test_one_thing_across_several_spans_is_one_thing(self):
        """The case it exists for. Three interactions with a crate the beat
        itself minted, the last of them naming it only as "it"."""
        spans = self._spans([
            {"type": "action", "attempt": "I set the crate down",
             "category": "objects", "note": "a",
             "items": [{"id": 1, "name": "crate"}]},
            {"type": "action", "attempt": "open the crate",
             "category": "objects", "note": "b",
             "items": [{"id": 1, "name": "crate"}]},
            {"type": "action", "attempt": "take the mallet out of it",
             "category": "objects", "note": "c",
             "items": [{"id": 3, "name": "mallet"},
                       {"id": 1, "name": "crate"}]}])
        sd = {"entities": {
            "crate": {"name": "crate", "from_event": 1},
            "mallet": {"name": "mallet", "from_event": 3}}}
        items = director.beat_item_records(sd, spans)
        assert items[1]["name"] == "crate"
        assert items[1]["spans"] == [1, 2, 3]
        assert items[3]["spans"] == [3]

    def test_it_gathers_what_two_hands_wrote_that_could_not_see_each_other(
            self):
        """The TARDIS shape, from the live beat: `objects` minted
        `entities.tardis` and `spatial` minted `rooms.tardis_interior`, in
        parallel, each from a payload showing the scene before either existed.
        One thing, two records, and nothing joined them."""
        spans = self._spans([
            {"type": "action", "attempt": "I step into the tardis",
             "category": ["objects", "spatial"], "note": "inside",
             "items": [{"id": 2, "name": "tardis"}]}])
        sd = {"entities": {"tardis": {"name": "tardis", "from_event": 1}},
              "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                            "from_event": 1}}}
        paths = sorted({p for p, _c, _r
                        in director.beat_item_records(sd, spans)[2]["records"]})
        assert paths == ["entities.tardis", "rooms.tardis_interior"]

    def test_a_beat_that_numbers_nothing_costs_nothing(self):
        spans = self._spans([
            {"type": "action", "attempt": "I kneel", "category": "spatial",
             "note": "n"}])
        assert spans[0].get("_items") is None
        assert director.beat_item_records(
            {"poses": {"Corin": {"posture": "kneeling", "from_event": 1}}},
            spans) == {}

    def test_a_mention_with_no_number_says_nothing_and_is_dropped(self):
        """Tolerant about the shape a model reaches for -- a bare number is an
        id with no name -- but a mention carrying no number cannot say the one
        thing this exists to say."""
        span, = self._spans([
            {"type": "action", "attempt": "x", "category": "objects",
             "note": "n", "items": [{"id": 4, "name": "console"}, 5,
                                    "levers", {"name": "no number"}]}])
        assert span["_items"] == [{"id": 4, "name": "console"},
                                  {"id": 5, "name": ""}]


class TestWhichRecordOfAThingIsAllowedToExist:
    """The owner, 2026-09-10: "the temp id allows the reconciler to apply all
    transforms in chronological order to an existing object, the priority ...
    being 'Actually exists in the world even before this beat.' then 'Freshly
    minted by the most relevant authority.' And the chosen object must receive
    all transforms."

    ORDER is borrowed, not owned: the chronological id exists so that events
    resolved in parallel are reassembled in the beat's true order for
    PERCEPTION, which must deliver them to a mind in the order they happened.
    This is a second consumer of the same property. (The first is still
    unbuilt -- `perception.py` dedupes on the phase id and streams each actor's
    sequence by `enumerate`.)
    """

    OWNER = {channel: hand for hand, spec in director.SPECIALISTS.items()
             for channel in spec["channels"]}

    def _spans(self, *sequence):
        return director._span_items({"sequence": list(sequence)})

    def _span(self, category, item_id, name):
        return {"type": "action", "attempt": "x", "category": category,
                "note": "n", "items": [{"id": item_id, "name": name}]}

    def test_what_stood_before_the_beat_outranks_what_it_minted(self):
        """Rung one, and it is what stops a beat re-founding a crate it merely
        opened."""
        spans = self._spans(self._span("objects", 1, "crate"))
        sd = {"entities": {
            "crate": {"name": "crate", "from_event": 1},
            "wooden_crate": {"name": "wooden crate", "from_event": 1}}}
        sc = {"entities": {"crate": {"name": "crate"}}}
        got = director.item_survivors(sd, spans, sc, self.OWNER)[1]
        assert got["render_from"][0] == "entities.crate"
        assert got["reason"] == "standing"
        assert [p for p, _c, _r in got["duplicates"]] == ["entities.wooden_crate"]

    def test_otherwise_the_channels_own_hand_wins(self):
        """Rung two. The partition is disjoint, so "most relevant authority"
        is a lookup and never a judgement."""
        spans = self._spans(self._span(["objects", "spatial"], 2, "tardis"))
        sd = {"entities": {"tardis": {"name": "tardis", "from_event": 1}},
              "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                            "from_event": 1}}}
        got = director.item_survivors(sd, spans, {}, self.OWNER)[2]
        assert got["reason"] == "owning_hand"

    def test_a_duplicate_folds_and_a_pair_only_links(self):
        """The distinction the channel decides. `entities.tardis` and
        `rooms.tardis_interior` are one thing and two TRUE halves -- folding
        either into the other deletes the place the player is standing in --
        while two records in ONE channel are one hand's two attempts at one
        thing, because the partition is disjoint."""
        spans = self._spans(self._span(["objects", "spatial"], 2, "tardis"))
        sd = {"entities": {"tardis": {"name": "tardis", "from_event": 1},
                           "tardis_box": {"name": "blue box",
                                          "from_event": 1}},
              "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                            "from_event": 1}}}
        got = director.item_survivors(sd, spans, {}, self.OWNER)[2]
        assert [p for p, _c, _r in got["duplicates"]] == ["entities.tardis_box"]
        assert [p for p, _c, _r in got["other_facts"]] == ["rooms.tardis_interior"]

    def test_what_folds_arrives_in_chronological_order(self):
        """"in chronological order" is the owner's phrase and the span number
        is what carries it -- not the order a hand's call happened to return
        in, which the parallel fan-out makes meaningless."""
        spans = self._spans(
            self._span("objects", 1, "crate"),
            self._span("objects", 1, "crate"),
            self._span("objects", 1, "crate"))
        sd = {"entities": {
            "crate": {"name": "crate", "from_event": 1},
            "z_later": {"name": "crate", "from_event": 3},
            "a_middle": {"name": "crate", "from_event": 2}}}
        sc = {"entities": {"crate": {"name": "crate"}}}
        got = director.item_survivors(sd, spans, sc, self.OWNER)[1]
        # Alphabetically `a_middle` precedes `z_later`; chronologically it is
        # span 2 before span 3, and that is what decides.
        assert [p for p, _c, _r in got["duplicates"]] == [
            "entities.a_middle", "entities.z_later"]

    def test_one_record_is_not_a_reconciliation(self):
        spans = self._spans(self._span("objects", 1, "crate"))
        sd = {"entities": {"crate": {"name": "crate", "from_event": 1}}}
        assert director.item_survivors(sd, spans, {}, self.OWNER) == {}

    def test_a_beat_that_numbers_nothing_reconciles_nothing(self):
        spans = self._spans(
            {"type": "action", "attempt": "x", "category": "objects",
             "note": "n"})
        sd = {"entities": {"a": {"name": "a", "from_event": 1},
                           "b": {"name": "b", "from_event": 1}}}
        assert director.item_survivors(sd, spans, {}, self.OWNER) == {}


class TestTheCausalityRecompiler:
    """The owner's name for it, 2026-09-10: "basically we are making a
    causality recompiler after our director deciphers and resolves", serving
    the thesis "a system that can decipher any arbitrarily long series of
    events by a player or character and resolve it properly with proper
    respect to chronology and space. Even though its disecting and feeding it
    to paralel agents."

    A beat's diff is applied all at once, so every question about the beat is
    answered against the world as it stood AFTER everything in it happened. In
    a beat where a door shuts halfway through, that is the wrong world for both
    halves: the speech before it shut was audible and the speech after was not,
    and one world cannot say both.

    NOTHING NEW IS NEEDED FOR THE CONES. `world/spatial_fov` is pure, derived
    and never stored, and `spatial_rel` / `body_visibility` / `hear_level` take
    the SCENE as a parameter -- so handing them a different scene answers for
    that world, and the geometry is respected by construction rather than by a
    rule a caller has to remember.
    """

    SCENE = {
        "rooms": {
            "yard": {"name": "Yard", "adjacent": [
                {"to": "box", "barrier": "open_door", "name": "box door"}]},
            "box": {"name": "Box", "adjacent": [
                {"to": "yard", "barrier": "open_door", "name": "box door"}]},
        },
        "positions": {"Corin": "yard", "Sera": "yard"},
        "entities": {}, "contacts": [], "poses": {}, "stations": {},
        "contained": {},
    }
    DIFF = {
        # span 2: he steps inside. A position is `dict[str, str]` -- a bare
        # string with nowhere to carry a citation -- so its provenance rides
        # in the sidecar the sheets already ask for.
        "positions": {"Corin": "box"},
        "phase_sources": {"positions.Corin": 2},
        # span 3: the door is pulled shut, both sides, as the hands write it.
        "rooms": {
            "yard": {"adjacent": [{"to": "box", "barrier": "closed_door",
                                   "name": "box door", "from_event": 3}]},
            "box": {"adjacent": [{"to": "yard", "barrier": "closed_door",
                                  "name": "box door", "from_event": 3}]},
        },
    }

    def _worlds(self):
        from world.spatial import merge_scene_with_diff
        return director.beat_worlds(
            json.loads(json.dumps(self.SCENE)), self.DIFF,
            merge_scene_with_diff)

    def test_the_beat_yields_a_world_per_span_in_order(self):
        worlds = self._worlds()
        assert [span for span, _w in worlds] == [2, 3]
        before2, before3 = worlds[0][1], worlds[1][1]
        # The world BEFORE a span does not contain that span.
        assert before2["positions"]["Corin"] == "yard"
        assert before3["positions"]["Corin"] == "box"
        assert before3["rooms"]["yard"]["adjacent"][0]["barrier"] == "open_door"

    def test_the_same_question_gets_three_answers_from_one_beat(self):
        """The whole claim, measured. Today every event in this beat is judged
        against the last row, so the first two are unreachable."""
        from world.spatial import (merge_scene_with_diff, hear_level, room_of,
                                   spatial_rel)

        def heard(world):
            rel = spatial_rel(world, room_of(world, "Sera"),
                              room_of(world, "Corin"))
            return rel.get("same_room"), hear_level(rel, "normal")

        worlds = self._worlds()
        assert heard(worlds[0][1]) == (True, "full")        # same room
        assert heard(worlds[1][1]) == (False, "full")       # apart, door open
        final = merge_scene_with_diff(
            json.loads(json.dumps(self.SCENE)), self.DIFF)
        assert heard(final) == (False, "fragment")          # door shut

    def test_a_scalar_channel_is_placed_by_the_sidecar(self):
        """`positions` is `dict[str, str]`, so a body's position cannot carry
        `from_event` -- and a beat's movements are exactly what a replay must
        order. `phase_sources` is the sidecar built for that, already taught by
        the sheets and already read by `prune_blocked_phase_changes`."""
        slices, loose = director.span_slices(self.DIFF)
        assert slices[2] == {"positions": {"Corin": "box"}}
        assert "positions" not in loose

    def test_a_records_own_citation_outranks_the_sidecar(self):
        """The field the sheets now lead with, and the one a hand fills while
        composing the record itself. The sidecar is a second structure to
        remember, and measured 25% emission."""
        slices, _loose = director.span_slices({
            "poses": {"Corin": {"posture": "kneeling", "from_event": 5}},
            "phase_sources": {"poses.Corin": 9}})
        assert sorted(slices) == [5]

    def test_a_record_and_its_rows_go_to_their_own_spans(self):
        """`rooms.<id>` holds `name` beside an `adjacent` LIST whose rows cite
        their own spans. Filing the whole record in one bucket AND
        distributing its rows applies the same edge twice on replay."""
        slices, loose = director.span_slices({
            "rooms": {"forge": {"name": "Forge", "adjacent": [
                {"to": "well", "barrier": "closed_door", "from_event": 2}]}}})
        assert slices[2] == {"rooms": {"forge": {"adjacent": [
            {"to": "well", "barrier": "closed_door", "from_event": 2}]}}}
        assert loose == {"rooms": {"forge": {"name": "Forge"}}}

    def test_what_cites_nothing_lands_before_the_beat(self):
        """It belongs to no point in the order, and the two ends are not
        equal: applied first it is background the beat acts upon, applied last
        it would silently overwrite what the beat established."""
        from world.spatial import merge_scene_with_diff
        worlds = director.beat_worlds(
            json.loads(json.dumps(self.SCENE)),
            {"positions": {"Sera": "box"},
             "poses": {"Corin": {"posture": "kneeling", "from_event": 4}}},
            merge_scene_with_diff)
        assert [span for span, _w in worlds] == [4]
        assert worlds[0][1]["positions"]["Sera"] == "box"

    def test_every_sliced_record_is_a_collected_record(self):
        """`span_records` collects and `span_slices` reconstructs, so they
        cannot be one function -- and this pins them to each other rather than
        to shared code. The property is what matters: the two must agree about
        which shapes a channel takes."""
        slices, _loose = director.span_slices(self.DIFF)
        for span_id, sliced in slices.items():
            collected = {path for path, _c, _r
                         in director.span_records(self.DIFF).get(span_id, [])}
            for channel, content in sliced.items():
                if isinstance(content, dict):
                    for key in content:
                        assert any(p.startswith("%s.%s" % (channel, key))
                                   for p in collected) or not collected, (
                            span_id, channel, key)


class TestASpecialistReturnsTransformsNotRecords:
    """The owner, 2026-09-10: "what the specialists actually give us are
    transforms we can apply to objects, even if it's an object the specialists
    freshly minted", and "the chosen object must receive all transforms."

    That is the right abstraction for the fan-out. Identity is the Director's
    item number, order is the chronological span number, and a freshly minted
    object is one whose first transform happens to be its creation.
    """

    OWNER = {channel: hand for hand, spec in director.SPECIALISTS.items()
             for channel in spec["channels"]}

    def _spans(self, *ids):
        return director._span_items({"sequence": [
            {"type": "action", "attempt": "x", "category": "objects",
             "note": "n", "items": [{"id": i, "name": "crate"}]}
            for i in ids]})

    def _fold(self, sd, sc):
        spans = self._spans(1, 1)
        survivors = director.item_survivors(sd, spans, sc, self.OWNER)
        return director.apply_item_transforms(sd, survivors)

    def test_the_survivor_receives_the_transforms_and_the_duplicate_goes(self):
        sd = {"entities": {
            "crate": {"name": "crate", "from_event": 1},
            "wooden_crate": {"name": "wooden crate", "kind": "container",
                             "material": "oak", "aliases": ["box"],
                             "from_event": 2}}}
        applied = self._fold(sd, {"entities": {"crate": {"name": "crate"}}})
        assert list(sd["entities"]) == ["crate"]
        assert sd["entities"]["crate"]["kind"] == "container"
        assert sd["entities"]["crate"]["material"] == "oak"
        assert applied[0]["folded"] == ["entities.wooden_crate"]

    def test_the_latest_transform_sets_the_state(self):
        """A crate that stood before the beat and was opened during it must
        not keep the shut snapshot it stood as. Identity comes from the
        survivor; state comes from the most recent thing said about it."""
        sd = {"entities": {
            "crate": {"name": "crate", "state": {"open": False},
                      "from_event": 1},
            "wooden_crate": {"name": "wooden crate", "state": {"open": True},
                             "from_event": 2}}}
        self._fold(sd, {"entities": {"crate": {"name": "crate"}}})
        assert sd["entities"]["crate"]["state"] == {"open": True}

    def test_state_is_never_deep_merged(self):
        """The tree's own rule and its reason: state describes a single
        instant, so folding a stale snapshot into a fresh one is what
        manufactures the contradiction. The latest wins WHOLE."""
        sd = {"entities": {
            "crate": {"name": "crate", "state": {"open": False, "locked": True},
                      "from_event": 1},
            "crate_two": {"name": "crate", "state": {"open": True},
                          "from_event": 2}}}
        self._fold(sd, {"entities": {"crate": {"name": "crate"}}})
        assert sd["entities"]["crate"]["state"] == {"open": True}

    def test_a_duplicate_never_rewrites_what_the_survivor_already_says(self):
        """The conservative direction, deliberately: the survivor may be a
        thing that STOOD BEFORE THE BEAT whose fields are the world's existing
        truth, and a duplicate the beat minted must not rewrite it. A wrong
        adoption is reported and visible; a wrong duplicate is silent,
        permanent, and compounds every beat."""
        sd = {"entities": {
            "crate": {"name": "crate", "kind": "crate", "from_event": 1},
            "crate_two": {"name": "barrel", "kind": "barrel",
                          "from_event": 2}}}
        self._fold(sd, {"entities": {"crate": {"name": "crate"}}})
        assert sd["entities"]["crate"]["name"] == "crate"
        assert sd["entities"]["crate"]["kind"] == "crate"

    def test_a_pair_in_two_channels_is_never_folded(self):
        """`entities.tardis` and `rooms.tardis_interior` are one thing and two
        TRUE halves. Folding either into the other deletes the place the player
        is standing in, so `apply` touches only the `fold` side."""
        spans = director._span_items({"sequence": [
            {"type": "action", "attempt": "x", "category": ["objects",
                                                            "spatial"],
             "note": "n", "items": [{"id": 2, "name": "tardis"}]}]})
        sd = {"entities": {"tardis": {"name": "tardis", "from_event": 1}},
              "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                            "from_event": 1}}}
        survivors = director.item_survivors(sd, spans, {}, self.OWNER)
        director.apply_item_transforms(sd, survivors)
        assert "tardis_interior" in sd["rooms"]
        assert "tardis" in sd["entities"]

    def test_nothing_to_reconcile_changes_nothing(self):
        sd = {"entities": {"crate": {"name": "crate", "from_event": 1}}}
        before = json.dumps(sd, sort_keys=True)
        spans = self._spans(1)
        assert director.apply_item_transforms(
            sd, director.item_survivors(sd, spans, {}, self.OWNER)) == []
        assert json.dumps(sd, sort_keys=True) == before


class TestWhichHandRendersAThingTheBeatMinted:
    """The owner, 2026-09-10: "if the object is freshly minted potentially by
    multiple agents, we have to decide which is the highest authority for
    rendering that object, it might be case by case, but thankfully we only
    have 5 classess to work with." Then, on the TARDIS: "in that case interior
    and entity are two seperate facts about one object", and "neither should be
    discarded."

    THE GAP THIS CLOSED WAS REAL. The ladder's second rung is "the channel's
    own hand", and the partition is DISJOINT -- every record already sits in
    its own hand's channel -- so that rung cannot discriminate between two
    hands at all. Two mints of one thing tied there and fell through to a
    tiebreak that ordered them BY PATH: `entities.tardis` beat
    `rooms.tardis_interior` because "e" sorts before "r".
    """

    OWNER = {channel: hand for hand, spec in director.SPECIALISTS.items()
             for channel in spec["channels"]}

    def _tardis(self, sd):
        spans = director._span_items({"sequence": [
            {"type": "action", "attempt": "I step into the tardis",
             "category": ["objects", "spatial"], "note": "n",
             "items": [{"id": 2, "name": "tardis"}]}]})
        return director.item_survivors(sd, spans, {}, self.OWNER)[2]

    def test_the_table_is_ordered_and_total(self):
        for index, hand in enumerate(
                ("objects", "spatial", "body", "contact", "social")):
            assert director.mint_authority_rank(hand) == index, hand
        assert set(director.SPECIALISTS) == {
            "objects", "spatial", "body", "contact", "social"}, (
            "five classes -- if a sixth hand is registered the table needs a "
            "rung, and an unranked hand sorts last rather than raising")
        assert director.mint_authority_rank("nobody") == 5

    def test_authority_decides_and_path_order_does_not(self):
        """`attire` sorts before `entities`, so path order would hand the
        rendering record to the body hand."""
        got = self._tardis({
            "attire": {"tardis_cloth": {"subject": "Corin", "from_event": 1}},
            "entities": {"tardis": {"name": "tardis", "from_event": 1}},
            "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                          "from_event": 1}}})
        assert got["render_from"][0] == "entities.tardis"

    def test_neither_fact_is_discarded(self):
        """The owner's rule, stated twice and pinned here. An entity and its
        interior are two separate facts about one object; choosing which to
        render FROM is not a claim that the other is a lesser truth."""
        sd = {"entities": {"tardis": {"name": "tardis", "from_event": 1}},
              "rooms": {"tardis_interior": {"name": "TARDIS interior",
                                            "from_event": 1}}}
        got = self._tardis(sd)
        assert [p for p, _c, _r in got["other_facts"]] == [
            "rooms.tardis_interior"]
        assert got["duplicates"] == []
        director.apply_item_transforms(sd, {2: got})
        assert "tardis_interior" in sd["rooms"]
        assert "tardis" in sd["entities"]

    def test_a_standing_thing_still_outranks_authority(self):
        """The ladder's first rung is above the table: what the world already
        held is the thing, whichever hand wrote about it this beat."""
        spans = director._span_items({"sequence": [
            {"type": "action", "attempt": "x", "category": ["objects",
                                                            "spatial"],
             "note": "n", "items": [{"id": 2, "name": "hall"}]}]})
        sd = {"entities": {"lamp": {"name": "lamp", "from_event": 1}},
              "rooms": {"hall": {"name": "Hall", "from_event": 1}}}
        got = director.item_survivors(
            sd, spans, {"rooms": {"hall": {"name": "Hall"}}}, self.OWNER)[2]
        assert got["render_from"][0] == "rooms.hall"
        assert got["reason"] == "standing"


class TestAThingMintedInsideAPlaceTheBeatMade:
    """The owner's last class, 2026-09-10: "you enter a location and mint an
    object inside that location."

    Measured in the live TARDIS beat: "I step into the tardis ... and pull the
    levers on the console" minted `entities.console` with NO POSITION, and
    nothing could place it. `derive_minted_entity_placements` is subtractive by
    design and speaks from ledgers that already NAME the thing -- a contact, a
    transfer -- and the console has neither. The room it belongs in did not
    exist when the objects hand was handed its payload, so it could not have
    named it either.

    The evidence only the recompiler has is where the actor STOOD at that span.
    Nothing else in the engine knows: the hands see a scene that has not moved
    since before the beat, and the merged diff has forgotten the order.
    """

    SCENE = {"rooms": {"yard": {"name": "Yard", "adjacent": []}},
             "positions": {"Corin": "yard"}, "entities": {}, "contacts": [],
             "poses": {}, "stations": {}, "contained": {}}

    def _run(self, sd, sequence):
        from world.spatial import merge_scene_with_diff
        scene = json.loads(json.dumps(self.SCENE))
        spans = director._span_items({"sequence": sequence})
        worlds = director.beat_worlds(scene, sd, merge_scene_with_diff)
        final = merge_scene_with_diff(scene, sd)
        return director.span_mint_rooms(
            sd, spans, worlds, final, lambda span: "Corin"), final

    def test_a_thing_minted_after_a_move_is_where_the_actor_went(self):
        sd = {
            "rooms": {"box": {"name": "Box", "adjacent": [],
                              "from_event": 1}},
            "positions": {"Corin": "box"},
            "phase_sources": {"positions.Corin": 1},
            "entities": {"console": {"name": "console", "from_event": 2}},
        }
        rooms, final = self._run(sd, [
            {"type": "action", "attempt": "I step into the box",
             "category": "spatial", "note": "a"},
            {"type": "action", "attempt": "I pull the levers on the console",
             "category": "objects", "note": "b"}])
        assert (final.get("positions") or {}).get("console") is None, (
            "nothing else places it -- that is the gap")
        assert rooms == {"console": "box"}

    def test_the_world_the_span_LEAVES_decides_not_the_one_it_starts_in(self):
        """"I step into the box and drop my bag" is ONE span in which the
        actor moves and mints, so the world before it still has them
        outside."""
        sd = {
            "rooms": {"box": {"name": "Box", "adjacent": [],
                              "from_event": 1}},
            "positions": {"Corin": "box"},
            "phase_sources": {"positions.Corin": 1},
            "entities": {"bag": {"name": "bag", "from_event": 1}},
        }
        rooms, _final = self._run(sd, [
            {"type": "action", "attempt": "I step into the box and drop my bag",
             "category": ["spatial", "objects"], "note": "a"}])
        assert rooms == {"bag": "box"}

    def test_a_thing_someone_already_placed_is_left_alone(self):
        """An explicit write outranks a derivation -- the rule
        `derive_minted_entity_placements` already states, and this speaks only
        where nobody else did."""
        sd = {
            "rooms": {"box": {"name": "Box", "adjacent": [],
                              "from_event": 1}},
            "positions": {"Corin": "box", "console": "yard"},
            "phase_sources": {"positions.Corin": 1},
            "entities": {"console": {"name": "console", "from_event": 2}},
        }
        rooms, _final = self._run(sd, [
            {"type": "action", "attempt": "a", "category": "spatial",
             "note": "a"},
            {"type": "action", "attempt": "b", "category": "objects",
             "note": "b"}])
        assert rooms == {}

    def test_it_writes_nothing_itself(self):
        """Placement belongs to `world/spatial_containment`, whose four
        subtractive rules are the right ones. This supplies the evidence
        nothing else has and applies none of it.

        Snapshotted AFTER the replay, because `merge_scene_with_diff` writes
        back into the diff it is handed -- an orphan room gains a connecting
        edge -- so comparing across the whole helper would measure the merge
        rather than the function under test."""
        from world.spatial import merge_scene_with_diff
        sd = {
            "rooms": {"box": {"name": "Box", "adjacent": [],
                              "from_event": 1}},
            "positions": {"Corin": "box"},
            "phase_sources": {"positions.Corin": 1},
            "entities": {"console": {"name": "console", "from_event": 2}},
        }
        scene = json.loads(json.dumps(self.SCENE))
        spans = director._span_items({"sequence": [
            {"type": "action", "attempt": "a", "category": "spatial",
             "note": "a"},
            {"type": "action", "attempt": "b", "category": "objects",
             "note": "b"}]})
        worlds = director.beat_worlds(scene, sd, merge_scene_with_diff)
        final = merge_scene_with_diff(scene, sd)
        before = json.dumps(sd, sort_keys=True)
        got = director.span_mint_rooms(
            sd, spans, worlds, final, lambda span: "Corin")
        assert got == {"console": "box"}
        assert json.dumps(sd, sort_keys=True) == before

    def test_a_room_the_scene_does_not_hold_places_nothing(self):
        """Silence, never a guess: evidence that does not resolve against the
        world writes nothing, which is the first of the four rules."""
        sd = {"positions": {"Corin": "nowhere"},
              "phase_sources": {"positions.Corin": 1},
              "entities": {"console": {"name": "console", "from_event": 2}}}
        rooms, _final = self._run(sd, [
            {"type": "action", "attempt": "a", "category": "spatial",
             "note": "a"},
            {"type": "action", "attempt": "b", "category": "objects",
             "note": "b"}])
        assert rooms == {}


class TestAHandHandedOneSpanWroteItForThatSpan:
    """The dependency this removes: the recompiler's three-link case -- mint a
    room, walk into it, mint a thing inside it -- rests on the MOVEMENT being
    attributable, and movement is the one thing that structurally cannot carry
    its own provenance. `positions` is `dict[str, str]`, a bare string with
    nowhere to put a citation, so it fell back on `phase_sources`, which a hand
    fills BESIDE its work and which measured 25% emission.

    The rule that removes it needs no prose, no model and no guess: the
    dispatch already records which spans each hand was handed, and a hand
    handed exactly ONE span wrote every record for that span. There is nothing
    else those records could be about. Measured over the day's live runs, 28 of
    32 dispatched hands were handed exactly one span.
    """

    def _dispatch(self, *names):
        return {name: {"ran": True,
                       "channels": director.SPECIALISTS[name]["channels"]}
                for name in names}

    def _view(self, *sequence):
        return {"spans": director._span_items({"sequence": list(sequence)})}

    def test_a_movement_is_placed_in_the_beats_order_without_a_sidecar(self):
        view = self._view(
            {"type": "action", "attempt": "a crate stands here",
             "category": "objects", "note": "a"},
            {"type": "action", "attempt": "I step into the box",
             "category": "spatial", "note": "b"})
        sd = {"rooms": {"box": {"name": "Box", "from_event": 2}},
              "positions": {"Corin": "box"},
              "entities": {"crate": {"name": "crate", "from_event": 1}}}
        got = director.single_span_attributions(
            sd, self._dispatch("objects", "spatial"), view,
            director._specialist_span_slice)
        assert got["positions.Corin"] == 2

    def test_it_never_argues_with_a_record_that_already_cited(self):
        """An explicit write outranks a derivation -- the rule
        `derive_minted_entity_placements` states and this obeys."""
        view = self._view(
            {"type": "action", "attempt": "I step into the box",
             "category": "spatial", "note": "b"})
        sd = {"rooms": {"box": {"name": "Box", "from_event": 7}}}
        got = director.single_span_attributions(
            sd, self._dispatch("spatial"), view,
            director._specialist_span_slice)
        assert "rooms.box" not in got

    def test_it_never_argues_with_an_existing_sidecar_entry(self):
        view = self._view(
            {"type": "action", "attempt": "I step into the box",
             "category": "spatial", "note": "b"})
        sd = {"positions": {"Corin": "box"},
              "phase_sources": {"positions.Corin": 9}}
        got = director.single_span_attributions(
            sd, self._dispatch("spatial"), view,
            director._specialist_span_slice)
        assert "positions.Corin" not in got

    def test_two_spans_is_genuinely_ambiguous_and_says_nothing(self):
        """Silence, never a guess. The typed record's own `from_event` is the
        channel for that case, and a record carrying neither reaches the
        unattributed slice, which is the honest place for it."""
        view = self._view(
            {"type": "action", "attempt": "I step into the box",
             "category": "spatial", "note": "a"},
            {"type": "action", "attempt": "I kneel", "category": "spatial",
             "note": "b"})
        sd = {"positions": {"Corin": "box"}}
        assert director.single_span_attributions(
            sd, self._dispatch("spatial"), view,
            director._specialist_span_slice) == {}

    def test_a_hand_that_did_not_run_attributes_nothing(self):
        view = self._view(
            {"type": "action", "attempt": "I step into the box",
             "category": "spatial", "note": "b"})
        sd = {"positions": {"Corin": "box"}}
        dispatch = {"spatial": {"ran": False,
                                "channels": director.SPECIALISTS[
                                    "spatial"]["channels"]}}
        assert director.single_span_attributions(
            sd, dispatch, view, director._specialist_span_slice) == {}

    def test_only_the_hands_own_channels(self):
        """The partition is disjoint, and a hand cannot speak for a channel it
        does not own -- the merge would not even look for it."""
        view = self._view(
            {"type": "action", "attempt": "I step into the box",
             "category": "spatial", "note": "b"})
        sd = {"positions": {"Corin": "box"},
              "entities": {"crate": {"name": "crate"}}}
        got = director.single_span_attributions(
            sd, self._dispatch("spatial"), view,
            director._specialist_span_slice)
        assert "positions.Corin" in got
        assert "entities.crate" not in got

    def test_it_writes_nothing(self):
        view = self._view(
            {"type": "action", "attempt": "I step into the box",
             "category": "spatial", "note": "b"})
        sd = {"positions": {"Corin": "box"}}
        before = json.dumps(sd, sort_keys=True)
        director.single_span_attributions(
            sd, self._dispatch("spatial"), view,
            director._specialist_span_slice)
        assert json.dumps(sd, sort_keys=True) == before

    def test_the_whole_chain_resolves_once_the_move_is_attributed(self):
        """Mint a room, walk into it, mint a thing inside it -- and a thing set
        down BEFORE the move stays where it was set down."""
        from world.spatial import merge_scene_with_diff
        view = self._view(
            {"type": "action", "attempt": "a crate stands here",
             "category": "objects", "note": "a"},
            {"type": "action", "attempt": "I step into the box",
             "category": "spatial", "note": "b"})
        sd = {"rooms": {"box": {"name": "Box", "adjacent": [],
                                "from_event": 2}},
              "positions": {"Corin": "box"},
              "entities": {"crate": {"name": "crate", "from_event": 1}}}
        sd.setdefault("phase_sources", {}).update(
            director.single_span_attributions(
                sd, self._dispatch("objects", "spatial"), view,
                director._specialist_span_slice))
        scene = {"rooms": {"yard": {"name": "Yard", "adjacent": []}},
                 "positions": {"Corin": "yard"}, "entities": {},
                 "contacts": [], "poses": {}, "stations": {}, "contained": {}}
        worlds = director.beat_worlds(scene, sd, merge_scene_with_diff)
        final = merge_scene_with_diff(scene, sd)
        assert [(s, (w.get("positions") or {}).get("Corin"))
                for s, w in worlds] == [(1, "yard"), (2, "yard")]
        assert director.span_mint_rooms(
            sd, view["spans"], worlds, final,
            lambda span: "Corin") == {"crate": "yard"}


class TestThePlacementLadderPrefersTheOrderAwareAnswer:
    """`place_unplaced_mints` stood every orphan in ONE room -- where the beat
    is, which `_mint_fallback_room` answers as the room the player ARRIVED in.
    That is right whenever the mint is the last thing that matters and wrong
    whenever it is not.

    Measured: a crate set down in the yard BEFORE the player walked into the
    box is stood in the box by the fallback, because it has one room for the
    whole beat and cannot see when anything happened. The fallback is the
    recompiler's answer with the ORDER thrown away.
    """

    def _sd(self):
        return {"entities": {"crate": {"name": "crate", "kind": "crate"},
                             "console": {"name": "console",
                                         "kind": "fixture"}},
                "positions": {}}

    def _sc(self):
        return {"rooms": {"yard": {"name": "Yard", "adjacent": []},
                          "box": {"name": "Box", "adjacent": []}},
                "positions": {"Corin": "yard"}, "entities": {},
                "contacts": [], "poses": {}, "stations": {}, "contained": {}}

    def test_a_per_entity_room_wins_over_the_one_room_fallback(self):
        sc, sd = self._sc(), self._sd()
        placed = director.place_unplaced_mints(sc, sd, "box",
                                      rooms={"crate": "yard"})
        assert set(placed) == {"crate", "console"}
        assert sd["positions"]["crate"] == "yard", (
            "the crate was set down before the move")
        assert sd["positions"]["console"] == "box", (
            "the recompiler said nothing about it, so the fallback stands")

    def test_with_no_mapping_it_is_the_function_it_was(self):
        sc, sd = self._sc(), self._sd()
        placed = director.place_unplaced_mints(sc, sd, "box")
        assert set(placed) == {"crate", "console"}
        assert sd["positions"] == {"crate": "box", "console": "box"}

    def test_a_mapping_alone_places_where_the_beat_could_not_say(self):
        """The fallback declines where the beat names no single room the
        player is in, and inventing one is worse than leaving a thing nowhere.
        A per-entity answer is not an invention -- it is where the actor
        stood -- so it may speak when the fallback cannot."""
        sc, sd = self._sc(), self._sd()
        placed = director.place_unplaced_mints(sc, sd, "", rooms={"crate": "yard"})
        assert placed == ["crate"]
        assert sd["positions"] == {"crate": "yard"}

    def test_neither_places_nothing(self):
        sc, sd = self._sc(), self._sd()
        assert director.place_unplaced_mints(sc, sd, "") == []
        assert sd["positions"] == {}


class TestTheCutFallsOnTheEventThatMoved:
    """`beat_movement_cuts` had to infer which of a mover's actions did the
    moving and took the LAST one, because two snapshots cannot say. Its own
    docstring names the quantity it wanted: "recording the trajectory is what
    fixes it, and this is the quantity that trajectory would be read for."

    Measured against the function as it stood, the shape it gets wrong is the
    ordinary one -- and it is not the double move the docstring warned about:

        move, act, act   cuts at the LAST act
           0 step into the box   graded in yard
           1 pull levers         graded in YARD   <- he is in the box
           2 read dial           graded in box

    That is "step into the tardis, pull the levers on the console".
    """

    PREV = {"rooms": {"yard": {"name": "Yard", "adjacent": []},
                      "box": {"name": "Box", "adjacent": []}},
            "positions": {"Corin": "yard"}, "entities": {}, "contacts": [],
            "poses": {}, "stations": {}, "contained": {}}

    def _events(self, *ids):
        return [{"kind": "action", "actor": "Corin", "attempt": str(i),
                 "event": {"event_id": i}} for i in ids]

    def _where(self, cuts, count):
        from world.spatial import scene_as_of
        now = dict(self.PREV, positions={"Corin": "box"})
        return [(scene_as_of(self.PREV, now, cuts, index).get("positions")
                 or {}).get("Corin") for index in range(count)]

    def test_the_heuristic_misgrades_the_act_between_move_and_last(self):
        """Pinned so the improvement is legible and so a regression to it is
        caught. This is what `moved_at=None` still does, for a body the beat
        cannot speak for."""
        from world.spatial import beat_movement_cuts
        now = dict(self.PREV, positions={"Corin": "box"})
        events = self._events("e0", "e1", "e2")
        cuts = beat_movement_cuts(self.PREV, now, events)
        assert cuts == {"Corin": 2}
        assert self._where(cuts, 3) == ["yard", "yard", "box"]

    def test_the_trajectory_puts_him_where_he_went(self):
        """The move itself is seen from the room he is leaving, and everything
        after it from where he went. Measured by rendering the view: cutting ON
        the move hid the departure from the observer left behind."""
        from world.spatial import beat_movement_cuts
        now = dict(self.PREV, positions={"Corin": "box"})
        events = self._events("e0", "e1", "e2")
        cuts = beat_movement_cuts(self.PREV, now, events,
                                  moved_at={"Corin": "e0"})
        assert cuts == {"Corin": 1}
        assert self._where(cuts, 3) == ["yard", "box", "box"]

    def test_the_departure_is_seen_from_the_room_being_left(self):
        """The regression this correction exists for. With the cut ON the move
        the observer in the origin room lost it entirely -- he spoke and then
        vanished -- because `scene_as_of` grades the move event itself at the
        destination."""
        from world.spatial import beat_movement_cuts
        now = dict(self.PREV, positions={"Corin": "box"})
        for events, moved in ((self._events("m0"), "m0"),
                              (self._events("m0", "m1"), "m0"),
                              (self._events("m0", "m1", "m2"), "m0")):
            cuts = beat_movement_cuts(self.PREV, now, events,
                                      moved_at={"Corin": moved})
            where = self._where(cuts, len(events))
            assert where[0] == "yard", (len(events), where)
            assert all(room == "box" for room in where[1:]), where

    def test_the_heuristic_and_the_trajectory_agree_on_the_common_shape(self):
        """`say, move, say` -- the shape the heuristic was reasoned from. The
        move is the mover's only action, so the last-action guess and the
        trajectory name the same event, and the +1 puts the cut on the line
        spoken after he got there."""
        from world.spatial import beat_movement_cuts
        now = dict(self.PREV, positions={"Corin": "box"})
        events = [{"kind": "speech", "actor": "Corin",
                   "event": {"event_id": "s0"}},
                  {"kind": "action", "actor": "Corin", "attempt": "cross",
                   "event": {"event_id": "m1"}},
                  {"kind": "speech", "actor": "Corin",
                   "event": {"event_id": "s2"}}]
        assert beat_movement_cuts(self.PREV, now, events) == {"Corin": 1}
        assert beat_movement_cuts(
            self.PREV, now, events, moved_at={"Corin": "m1"}) == {"Corin": 2}
        assert self._where({"Corin": 2}, 3) == ["yard", "yard", "box"]

    def test_a_body_it_cannot_speak_for_keeps_the_heuristic(self):
        from world.spatial import beat_movement_cuts
        now = dict(self.PREV, positions={"Corin": "box"})
        events = self._events("e0", "e1", "e2")
        assert beat_movement_cuts(self.PREV, now, events,
                                  moved_at={"Someone": "e0"}) == {"Corin": 2}

    def test_an_id_the_stream_does_not_carry_changes_nothing(self):
        """Silence, never a guess: an attribution that resolves to no stream
        event leaves the body to the heuristic rather than to index zero."""
        from world.spatial import beat_movement_cuts
        now = dict(self.PREV, positions={"Corin": "box"})
        events = self._events("e0", "e1", "e2")
        assert beat_movement_cuts(self.PREV, now, events,
                                  moved_at={"Corin": "nope"}) == {"Corin": 2}

    def test_nobody_moved_is_still_no_cuts(self):
        from world.spatial import beat_movement_cuts
        assert beat_movement_cuts(self.PREV, dict(self.PREV),
                                  self._events("e0"),
                                  moved_at={"Corin": "e0"}) == {}


class TestWhichEventMovedThem:
    """The three hops that make the cut recoverable, all engine-issued ids and
    no prose: the span that carried the position change, the sequence position
    that span came from, and that element's phase id -- which is what the
    perception stream carries on every entry built from a declaration."""

    def _out(self):
        from agents.common import assign_event_ids, norm_sequence
        out = {"sequence": [
            {"type": "action", "attempt": "step into the box",
             "category": "spatial", "note": "a"},
            {"type": "action", "attempt": "pull the levers",
             "category": "objects", "note": "b"}]}
        norm_sequence(out)
        out["sequence"] = assign_event_ids(out["sequence"], "turn:1:player")
        return out

    def test_it_names_the_declared_event_that_moved_them(self):
        out = self._out()
        out["state_assertions"] = {"positions": {"Corin": "box"},
                                   "phase_sources": {"positions.Corin": 1}}
        assert director.mover_cut_events(out) == {
            "Corin": "turn:1:player:0:action"}

    def test_the_second_span_names_the_second_element(self):
        out = self._out()
        out["state_assertions"] = {"positions": {"Corin": "box"},
                                   "phase_sources": {"positions.Corin": 2}}
        assert director.mover_cut_events(out) == {
            "Corin": "turn:1:player:1:action"}

    def test_no_sidecar_says_nothing(self):
        out = self._out()
        out["state_assertions"] = {"positions": {"Corin": "box"}}
        assert director.mover_cut_events(out) == {}

    def test_a_declared_element_citing_its_raw_input_still_answers_its_own_id(self):
        """The ledger stamps the player's own elements with the raw input's
        id under `from_declaration` ("turn:1:primary:raw"), which no stream
        is keyed on; the element's own phase id is the cut. Measured (scratch
        play 2026-09-14, chat 4 turn 12): preferring the citation sent every
        player cut to the last-action heuristic and two bedside lines were
        graded from the scullery."""
        out = self._out()
        for element in out["sequence"]:
            element["from_declaration"] = "turn:1:primary:raw"
        out["state_assertions"] = {"positions": {"Corin": "box"},
                                   "phase_sources": {"positions.Corin": 1}}
        assert director.mover_cut_events(out) == {
            "Corin": "turn:1:player:0:action"}

    def test_only_position_paths(self):
        """A sidecar entry for another channel says nothing about where a body
        was standing."""
        out = self._out()
        out["state_assertions"] = {"phase_sources": {"poses.Corin": 1}}
        assert director.mover_cut_events(out) == {}

    def test_a_span_id_no_span_carries_says_nothing(self):
        out = self._out()
        out["state_assertions"] = {"phase_sources": {"positions.Corin": 9}}
        assert director.mover_cut_events(out) == {}


class TestACharactersMoveIsFoundThroughTheCitation:
    """A character DECLARES behaviour from private perception; the DIRECTOR
    categorizes. The character sheet never mentions `category` and should not
    -- asking a fictional mind which engine ledger its act belongs in would
    make it do the Director's bookkeeping and hand it channels it has no
    business knowing.

    So the character half was never a missing capability, it was a missing
    JOIN, and `from_declaration` supplies it: the author's element carries the
    category AND names the act that was declared. One rule serves both halves
    -- an element that cites a declaration answers with the cited id, one that
    does not answers with its own.
    """

    def test_a_characters_move_resolves_through_the_cited_declaration(self):
        res = {"sequence": [
            {"actor": "Mara", "attempt": "crosses to the store",
             "category": "spatial", "note": "a",
             "from_declaration": "turn:9:character:4:0:action"},
            {"actor": "Mara", "attempt": "sets the lantern down",
             "category": "objects", "note": "b",
             "from_declaration": "turn:9:character:4:1:action"}]}
        diff = {"positions": {"Mara": "store"},
                "phase_sources": {"positions.Mara": 1}}
        assert director.mover_cut_events(res, diff) == {
            "Mara": "turn:9:character:4:0:action"}

    def test_the_players_own_declaration_is_unchanged(self):
        """Interpret's elements carry their own phase ids and cite nothing,
        because interpret's sequence IS the player's declaration."""
        interp = {"sequence": [
            {"type": "action", "attempt": "I step into the box",
             "event_id": "turn:9:player:0:action",
             "category": "spatial", "note": "a"}],
            "state_assertions": {"positions": {"Corin": "box"},
                                 "phase_sources": {"positions.Corin": 1}}}
        assert director.mover_cut_events(interp) == {
            "Corin": "turn:9:player:0:action"}

    def test_a_citation_outranks_the_elements_own_id(self):
        """Where both exist the CITED one wins: the stream is built from
        declarations, so that is the id it is keyed on."""
        res = {"sequence": [
            {"actor": "Mara", "attempt": "crosses", "category": "spatial",
             "note": "a", "event_id": "authors-own",
             "from_declaration": "declared-one"}]}
        assert director.mover_cut_events(
            res, {"phase_sources": {"positions.Mara": 1}}) == {
                "Mara": "declared-one"}

    def test_an_element_citing_nothing_still_answers_with_its_own(self):
        res = {"sequence": [
            {"actor": "Mara", "attempt": "crosses", "category": "spatial",
             "note": "a", "event_id": "own-id"}]}
        assert director.mover_cut_events(
            res, {"phase_sources": {"positions.Mara": 1}}) == {
                "Mara": "own-id"}

    def test_the_character_sheet_never_asks_for_a_category(self):
        """Pinned because it is a DESIGN boundary and not an omission: the
        moment a character sheet asks for one, a mind is doing the Director's
        bookkeeping."""
        from llm.prompts import DEFAULT_PROMPTS, character_bare_module
        from agents.character_bare import modules_for
        sheet = DEFAULT_PROMPTS["character_bare"] + "\n".join(
            character_bare_module(name, "en") for name in (
                "their_silence", "answer_owed", "offers", "speech_budget", "crisis",
                "tell_variety", "tell_payoff", "repetition", "dispute", "drive_rupture",
                "drive_rupture_forced", "project_review", "still_waiting",
                "impossible_knowledge", "carried_reports", "ways_on"))
        assert modules_for  # every gated section is part of the sheet
        assert "category" not in sheet
        assert "from_declaration" not in sheet


class TestACategoryIsReadInWhateverShapeItArrived:
    """The owner: "surely there is a more loosey goosey way to ingest the
    categories."

    There was not, and the reason is that tolerance had been added TWICE in
    two places that never composed -- `_split_joined_categories` handled a
    delimited STRING, the call site handled a LIST, and once a value took the
    list branch no member was ever split. So the shapes that lost work were
    the MIXTURES. Measured on the long-beat run: 5 of 54 categories arrived as
    lists, so mixtures are not hypothetical.

    A shape the engine refuses to read is a span that routes to no hand, and a
    change nobody was handed is lost in SILENCE -- which is the failure this
    whole seam exists to prevent.
    """

    def _hands(self, category):
        out = {"sequence": [{"actor": "Corin", "attempt": "x", "note": "n",
                             "category": category}]}
        items = director._span_items(out)
        if not items:
            return []
        hands = []
        for name in items[0].get("categories") or []:
            for kind, hand in (manifest_category_targets(name) or []):
                if kind == "hand" and hand not in hands:
                    hands.append(hand)
        return hands

    def test_every_shape_a_model_reaches_for_names_the_same_two_hands(self):
        for shape in ("body, objects", "body and objects", "body; objects",
                      "body/objects", ["body", "objects"], ("body", "objects"),
                      ["BODY", " objects "]):
            assert self._hands(shape) == ["body", "objects"], shape

    def test_a_list_holding_one_delimited_string_used_to_route_nowhere(self):
        """The mixture the two tolerant paths could not see between them."""
        assert self._hands(["body, objects"]) == ["body", "objects"]

    def test_a_mixed_list_no_longer_drops_everything_after_the_first(self):
        assert self._hands(["body", "objects, spatial"]) == [
            "body", "objects", "spatial"]

    def test_a_mapping_answers_with_its_keys(self):
        """Worth accepting for a specific reason: a model asked for categories
        AND a note per category reaches for a mapping because `ledger_notes`
        in this very output is one, so the schema it is already writing
        suggests the shape."""
        assert self._hands({"body": "gloves off",
                            "objects": "gloves on the bench"}) == [
            "body", "objects"]

    def test_tolerance_is_not_credulity(self):
        """Widening the shapes must not widen the discard rule. A string is
        split only when EVERY part routes, so free prose reaches the unrouted
        report WHOLE rather than minced into categories nobody named."""
        prose = "the belt comes off and lands on the bench"
        assert director._category_names(prose) == [prose]
        assert director._category_names([prose]) == [prose]
        assert director._category_names({prose: 1}) == [prose]
        # NO PART of that names a family the engine routes, which is what
        # makes it prose rather than a list -- and the discriminator, so a
        # sentence is never minced into seven invented categories.
        assert len(director._category_names(prose)) == 1

    def test_a_known_name_is_recovered_from_a_partly_unknown_string(self):
        """The other side of the same discriminator, and the owner's point:
        "the magic words ... are right there". One part names a family the
        engine routes, so the string is a list of names; the known one is
        delivered and the unknown one is reported by itself."""
        assert director._category_names("body, and then something else") == [
            "body", "then something else"]

    def test_an_unknown_single_name_still_passes_through_to_be_reported(self):
        assert director._category_names("wardrobe") == ["wardrobe"]

    def test_nothing_named_is_still_nothing(self):
        for empty in ([], None, "", {}):
            out = {"sequence": [{"actor": "C", "attempt": "x",
                                 "category": empty}]}
            assert director._span_items(out) == []


def test_a_required_visible_interior_cannot_fail_open_into_narration():
    sc = {"rooms": {}, "entities": {"box": {
        "name": "Police Box", "aliases": ["TARDIS"],
        "interior_rooms": []}}}
    view = {"spans": [{
        "object_name": "TARDIS", "targets": ["Hinami", "box"],
        "categories": ["entities", "rooms"],
    }]}
    extras = {"entity_interiors": sc["entities"]}
    out = {"state_assertions": {"rooms": {}, "entities": {}}}
    with pytest.raises(RuntimeError, match="was not minted"):
        director._require_complete_entity_interiors(
            out, sc, view, extras, "interpret")

    out["state_assertions"]["rooms"]["box_inside"] = {
        "name": "Control Room", "parent_entity": "box"}
    director._require_complete_entity_interiors(
        out, sc, view, extras, "interpret")


def test_a_required_interior_failure_preserves_the_spatial_diagnostic():
    out = {
        "state_assertions": {"rooms": {}, "entities": {}},
        "orchestration": {"specialists": {"spatial": {
            "error": "results.0 did not create a parented room"}}},
    }
    sc = {"rooms": {}, "entities": {"box": {
        "name": "Police Box", "interior_rooms": []}}}
    with pytest.raises(RuntimeError, match="spatial failure: results.0"):
        director._require_complete_entity_interiors(
            out, sc, {"spans": [{
                "object_name": "Police Box", "categories": ["rooms"]}]},
            {"entity_interiors": sc["entities"]}, "interpret")


def test_resolve_accepts_the_interior_already_minted_at_onset():
    """Resolve need not mint interpret's room a second time, even if an old
    entity roster still says the holder has no interior rooms."""
    sc = {
        "rooms": {"box_inside": {
            "name": "Control Room", "parent_entity": "box"}},
        "entities": {"box": {
            "name": "Police Box", "aliases": ["TARDIS"],
            "interior_rooms": ["box_inside"]}},
    }
    stale_extras = {"entity_interiors": {"box": {
        "name": "Police Box", "aliases": ["TARDIS"],
        "interior_rooms": []}}}
    view = {"spans": [{
        "object_name": "TARDIS", "targets": ["box"],
        "categories": ["entities", "rooms"],
    }]}
    out = {"state_diff": {"rooms": {}, "entities": {}}}
    director._require_complete_entity_interiors(
        out, sc, view, stale_extras, "resolve")


def test_a_bystander_target_does_not_replace_the_existing_interior_holder():
    """Regression for `past Hinami ... peers into the TARDIS interior`."""
    sc = {
        "rooms": {"tardis_console": {
            "name": "TARDIS Console Room", "parent_entity": "box"}},
        "entities": {
            "Hinami": {"name": "Hinami", "interior_rooms": []},
            "box": {"name": "Police Box", "aliases": ["TARDIS"],
                    "interior_rooms": ["tardis_console"]},
        },
    }
    view = {"spans": [{
        "object_name": "Hinami", "targets": ["Hinami", "box"],
        "event": "leans past Hinami and peers into the TARDIS interior",
        "categories": ["poses", "rooms"],
    }]}
    excluded = director._bodies_without_interiors(sc, {"persona:10": "Hinami"})
    index = director.causal_world_index(
        sc, include_entity_interiors=True,
        exclude_entity_interiors=excluded)

    assert "Hinami" not in index["entities"]
    assert index["entities"]["box"]["interior_rooms"] == [
        "tardis_console"]
    director._require_complete_entity_interiors(
        {"state_diff": {"rooms": {}, "entities": {}}}, sc, view,
        {"entity_interiors": index["entities"]}, "resolve")


def test_a_new_entity_interior_reference_must_name_a_real_room():
    out = {"state_assertions": {"rooms": {}, "entities": {
        "box": {"name": "Police Box", "interior_rooms": ["missing"]},
    }}}
    with pytest.raises(RuntimeError, match="introduced room reference"):
        director._require_complete_entity_interiors(
            out, {"rooms": {}, "entities": {"box": {
                "name": "Police Box", "interior_rooms": []}}},
            {"spans": []}, {"entity_interiors": {}}, "interpret")


def test_the_sequence_normaliser_carries_the_item_lists():
    """Chat 12 turn 190: every interpret span reached the hands with
    `item_ids`/`item_names` gone, because `SPAN_FIELDS` named the singular
    pair only. The lists ride through like the pair does."""
    from agents.common import norm_sequence
    out = {"sequence": [{
        "chrono_id": 3, "item_id": 1, "item_ids": [1, 2, 3],
        "item_names": ["notebook", "pencil", "coat"],
        "object_name": "notebook", "actor": "persona:1",
        "source_entity_id": "persona:1", "type": "action",
        "attempt": "drops both into the coat", "categories": ["containment"],
    }]}
    norm_sequence(out)
    row = out["sequence"][0]
    assert row["item_ids"] == [1, 2, 3]
    assert row["item_names"] == ["notebook", "pencil", "coat"]
    assert row["item_id"] == 1 and row["chrono_id"] == 3


# ---------------------------------------------------------------------------
# The floors that judge the merged diff, end to end through the prose Director.
# ---------------------------------------------------------------------------

_TARDIS_CONSOLE = {
    "name": "TARDIS Console Room",
    "desc": "A many-sided chamber gathered around a time rotor.",
    "light": "bright", "size": "vast", "adjacent": [],
    "parent_entity": "tardis",
}


def _prose_beat(monkeypatch, prose, *events, calls=None):
    monkeypatch.setattr(director, "_agent_json", _fake_agent(
        calls if calls is not None else [], {
            "director_prose": {"prose": prose},
            "director_specialist": {"events": list(events)},
        }))


def test_the_encoder_proposes_and_the_movement_backstop_disposes(
        temp_db, monkeypatch, prose_director):
    """The movement backstop stays with the deterministic code downstream of
    the fold, judging the MERGED diff -- it cannot be seen from inside the
    encoder's answer. A legal move the encoder writes commits; a move into a
    room with no passable route is STRIPPED, with the backstop's warning. The
    encoder proposes; physics disposes."""
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["rooms"]["cliff_path"] = {"name": "Cliff Path", "adjacent": []}
    interp = _action_interp()
    interp["movement"] = {"to_room": "cliff_path", "mover": "self"}
    monkeypatch.setattr(director, "_agent_json", _fake_agent([], prose_answers({
        "resolved_event": "Mara crosses into the lamp room; the Stranger "
                          "makes for the cliff path.",
        "state_diff": {
            "positions": {"Mara": "lamp_room",           # legal: open adjacency
                          "The Stranger": "cliff_path"},  # illegal: no route
            "stations": {"Mara": {"at": None, "near": ["The Stranger"]}},
        }})))

    ctx = _make_ctx(temp_db, scene=scene, interp=interp)
    out = director.director_resolve(ctx, nonce=0)

    positions = out["state_diff"]["positions"]
    assert positions.get("Mara") == "lamp_room"
    assert "The Stranger" not in positions
    assert any("Blocked movement" in w for w in ctx.warnings)


def test_interpret_mints_an_entity_interior_before_perception(
        temp_db, monkeypatch, prose_director):
    """Stepping into a thing with no interior yet: the encoder names the
    entry and mints the place -- a room whose `parent_entity` is the thing --
    and the interior is whole before perception reads it. The move lands on
    the minted room, never on the thing's name."""
    scene = json.loads(json.dumps(BASE_SCENE))
    scene["rooms"]["far_archive"] = {"name": "Far Archive", "adjacent": []}
    scene["entities"] = {
        "tardis": {"name": "TARDIS", "kind": "vehicle"},
        "remote_box": {"name": "remote box"},
    }
    scene["positions"].update({
        "tardis": "keeper_room", "remote_box": "far_archive"})
    _prose_beat(monkeypatch, "The Stranger steps into the TARDIS.", encoder_event(
        "The Stranger steps into the TARDIS.",
        observable="steps inside", targets=["tardis"],
        movement={"mover": "self", "to_room": "TARDIS", "arrives": True},
        transforms=[
            {"item": "tardis_console",
             "patch": {"rooms": {"tardis_console": _TARDIS_CONSOLE}}},
            {"item": "The Stranger",
             "patch": {"positions": {"The Stranger": "tardis_console"}}},
        ]))

    ctx = _make_ctx(temp_db, scene=scene,
                    player_input="I step into the TARDIS.")
    ctx.director_interpret = None
    out = director.director_interpret(ctx, nonce=0)

    assert out["state_assertions"]["rooms"]["tardis_console"] \
        ["parent_entity"] == "tardis"
    assert out["state_assertions"]["positions"]["The Stranger"] == \
        "tardis_console"
    assert out["movement"]["to_room"] == "tardis_console"
    preview = director.preview_player_state_assertions(
        scene, out["state_assertions"])
    assert director.room_of(preview, "The Stranger") == "tardis_console"
    assert preview["rooms"]["tardis_console"]["desc"].startswith(
        "A many-sided chamber")


def test_interpret_mints_an_interior_when_opening_reveals_it(
        temp_db, monkeypatch, prose_director):
    """Visibility, not entry, is the first-mint boundary: doors pulled open
    reveal the interior, which is minted and seen from the room outside while
    nobody moves."""
    from world.spatial import merge_scene_with_diff, visible_adjacent_rooms

    scene = json.loads(json.dumps(BASE_SCENE))
    scene["entities"] = {"tardis": {
        "name": "TARDIS", "kind": "vehicle", "container": True,
        "interior_rooms": [], "state": {"hatch": "closed"},
    }}
    scene["positions"]["tardis"] = "keeper_room"
    _prose_beat(monkeypatch, "The Stranger pulls the TARDIS doors open.", encoder_event(
        "The Stranger pulls the TARDIS doors open.",
        observable="pulls the doors open", targets=["tardis"],
        transforms=[
            {"item": "tardis",
             "patch": {"entities": {"tardis": {"state": {"hatch": "open"}}}}},
            {"item": "tardis_console",
             "patch": {"rooms": {"tardis_console": _TARDIS_CONSOLE}}},
        ]))

    ctx = _make_ctx(temp_db, scene=scene,
                    player_input="I pull the TARDIS doors open.")
    ctx.director_interpret = None
    out = director.director_interpret(ctx, nonce=0)

    assertions = out["state_assertions"]
    assert assertions["rooms"]["tardis_console"]["parent_entity"] == "tardis"
    assert "The Stranger" not in (assertions.get("positions") or {})
    preview = merge_scene_with_diff(scene, assertions)
    assert preview["entities"]["tardis"]["interior_rooms"] == [
        "tardis_console"]
    assert preview["entities"]["tardis"]["state"]["hatch"] == "open"
    visible = visible_adjacent_rooms(preview, "keeper_room")
    assert "tardis_console" in {str(room.get("room_id")) for room in visible}


def test_resolve_mints_an_interior_when_a_character_opens_it(
        temp_db, monkeypatch, prose_director):
    """A character's own act uses the same reveal contract at resolve."""
    from world.spatial import merge_scene_with_diff, visible_adjacent_rooms

    scene = json.loads(json.dumps(BASE_SCENE))
    scene["entities"] = {"tardis": {
        "name": "TARDIS", "kind": "vehicle", "container": True,
        "interior_rooms": [], "state": {"hatch": "closed"},
    }}
    scene["positions"]["tardis"] = "keeper_room"
    ctx = _make_ctx(temp_db, scene=scene, interp=_speech_interp())
    char_id = int(ctx.cast[0]["id"])
    ctx.character_results[char_id] = {
        "name": "Mara",
        "sequence": [{
            "type": "action", "attempt": "opens the TARDIS doors",
            "observable": "pulls the doors open", "commitment": "asserted",
            "targets": ["tardis"], "visibility": "overt",
            "conceal_from": [],
        }],
    }
    _prose_beat(monkeypatch, "Mara pulls the TARDIS doors open.", encoder_event(
        "Mara pulls the TARDIS doors open.", source=f"character:{char_id}",
        observable="pulls the doors open", targets=["tardis"],
        transforms=[
            {"item": "tardis",
             "patch": {"entities": {"tardis": {"state": {"hatch": "open"}}}}},
            {"item": "tardis_console",
             "patch": {"rooms": {"tardis_console": _TARDIS_CONSOLE}}},
        ]))

    out = director.director_resolve(ctx, nonce=0)

    assert out["state_diff"]["rooms"]["tardis_console"]["parent_entity"] \
        == "tardis"
    assert "Mara" not in (out["state_diff"].get("positions") or {})
    preview = merge_scene_with_diff(scene, out["state_diff"])
    assert preview["entities"]["tardis"]["state"]["hatch"] == "open"
    assert "tardis_console" in {
        str(room.get("room_id"))
        for room in visible_adjacent_rooms(preview, "keeper_room")
    }


def test_a_channel_the_stage_cannot_carry_is_dropped_loudly(
        temp_db, monkeypatch, prose_director):
    """Chat 98 turn 26's shape, now the encoder's: `public_evidence` written at
    interpret, which cannot carry it at all. The fold SUBTRACTS it and says
    so -- even when its owner was granted nothing else this beat, which is
    the case that used to vanish without a word."""
    from llm import decisions

    monkeypatch.setattr(decisions, "OVERRIDE", lambda state, questions: {
        key: {"type": "noul", "noul": 0.0} for key in questions})
    _prose_beat(monkeypatch, "\"Quiet night,\" says the Stranger.", encoder_event(
        "Quiet night.", speech=True,
        transforms=[{"item": "the greeting", "patch": {"public_evidence": [
            {"source_id": "invented", "speech_act": "greeting"}]}}]))

    ctx = _make_ctx(temp_db, player_input="\"Quiet night.\"")
    ctx.director_interpret = None
    out = director.director_interpret(ctx, nonce=0)

    social = out["orchestration"]["specialists"]["social"]
    assert social["scope"] == []
    assert social.get("dropped_channels") == ["public_evidence"]
    assert "public_evidence" not in (out.get("state_assertions") or {})
    notes = [str(note) for note in ctx.engine_feedback]
    assert any("public_evidence" in note and "dropped" in note
               for note in notes), notes
