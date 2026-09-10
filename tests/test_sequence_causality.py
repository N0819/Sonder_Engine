from agents.common import (
    assign_event_ids,
    communication_surface,
    norm_sequence,
    prune_blocked_phase_changes,
    resolve_action_referents,
    sequence_event_allowed,
    sequence_onset_elements,
    settle_sequence_dispositions,
)
from world.spatial import merge_scene_with_diff
from llm.schemas import StateDiff
from agents import composer
from agents.perception import _outcome_event_stream


def _scene():
    return {
        "rooms": {"bay": {"name": "Bay", "adjacent": []}},
        "positions": {"Dana": "bay", "Reya": "bay"},
        "entities": {}, "contacts": [], "poses": {}, "stations": {},
    }


def test_described_communication_survives_as_indirect_speech():
    out = {"sequence": [{
        "type": "communication", "act": "ask",
        "content": "where it hurts and whether Reya can move her toes",
        "targets": ["Reya"],
    }]}
    norm_sequence(out)
    assert out["sequence"] == [{
        "type": "communication", "act": "ask",
        "content": "where it hurts and whether Reya can move her toes",
        "targets": ["Reya"], "volume": "normal", "tone": "",
        "visibility": "overt", "conceal_from": [], "phase_id": "",
        "phase": "atomic", "depends_on": [], "participants": [],
    }]
    assert communication_surface(out["sequence"][0]) == (
        "asks where it hurts and whether Reya can move her toes")


def test_described_communication_uses_hearing_without_quote_invention():
    entry = {
        "type": "communication", "speaker": "Dana", "act": "explain",
        "content": "that the east route is blocked", "volume": "normal",
        "visibility": "overt", "targets": ["Reya"],
    }
    full = composer.communication_percept(
        entry, {"same_room": True, "barrier": "open"}, "Reya",
        display="Dana", can_see=True, order_key=0)
    assert full is not None
    rendered = composer.render_view([full], mode="character").text
    assert rendered == "Dana explains that the east route is blocked."
    assert '"' not in rendered

    partial = composer.communication_percept(
        entry, {"same_room": True, "source_enclosed": True}, "Reya",
        display="Dana", can_see=False, order_key=0)
    assert partial is not None
    assert "east route" not in composer.render_view(
        [partial], mode="character").text


def test_only_independent_phases_reach_reaction_onset():
    sequence = [
        {"event_id": "signal", "type": "action", "phase": "onset"},
        {"event_id": "dip", "type": "action", "phase": "continuation",
         "depends_on": ["signal"]},
        {"event_id": "line", "type": "speech", "text": "Ready?"},
    ]
    assert [row["event_id"] for row in sequence_onset_elements(sequence)] == [
        "signal", "line"]


def test_outcome_stream_places_reaction_between_onset_and_continuation():
    class Ctx(dict):
        __getattr__ = dict.__getitem__

    ctx = Ctx(
        extra_players=[], cast=[], character_results={}, reaction_results={},
        reaction_loop={"rounds": [{
            "reactor": "Reya", "reactor_id": 7,
            "result": {"sequence": [{
                "type": "action", "event_id": "brace",
                "observable": "braces her feet", "visibility": "overt",
            }]},
        }]},
        interaction_loop={"rounds": []},
    )
    interp = {"sequence": [
        {"type": "action", "event_id": "signal", "phase_id": "signal",
         "phase": "onset", "commitment": "asserted",
         "observable": "signals the dip", "visibility": "overt"},
        {"type": "action", "event_id": "return", "phase_id": "return",
         "phase": "completion", "depends_on": ["signal"],
         "commitment": "asserted", "observable": "returns Reya upright",
         "visibility": "overt"},
    ]}
    stream = _outcome_event_stream(
        ctx, _scene(), interp, {}, "Dana", [], [])
    assert [event.get("attempt") for event in stream] == [
        "signals the dip", "braces her feet", "returns Reya upright"]


def test_failed_contestable_phase_blocks_its_dependents():
    sequence = [
        {"event_id": "turn:4:player:0:action", "phase_id": "take_weight",
         "type": "action", "commitment": "contestable"},
        {"event_id": "turn:4:player:1:action", "phase_id": "release",
         "type": "action", "commitment": "asserted",
         "depends_on": ["take_weight"]},
    ]
    resolved = {"claim_dispositions": [{
        "claim_id": "claim:0:intent:0", "status": "deferred",
        "realized_event_ids": [],
    }]}
    verdicts = settle_sequence_dispositions(sequence, resolved, _scene())
    assert [row["status"] for row in verdicts] == ["attempted", "blocked"]
    resolved["sequence_dispositions"] = verdicts
    assert not sequence_event_allowed(sequence[1], resolved)


def test_missing_participant_blocks_phase_without_guessing_from_targets():
    sequence = [{
        "event_id": "transfer", "phase_id": "transfer", "type": "action",
        "commitment": "asserted", "participants": ["waiting responder"],
    }]
    verdict = settle_sequence_dispositions(sequence, {}, _scene())[0]
    assert verdict["status"] == "blocked"
    assert "waiting responder" in verdict["reason"]


def test_required_contact_must_stand_for_dependent_phase():
    selector = {"actor": "Dana", "actor_part": "hand",
                "target": "Reya", "target_part": "shoulder"}
    event = {"event_id": "lift", "type": "action",
             "commitment": "asserted", "requires_contacts": [selector]}
    assert settle_sequence_dispositions([event], {}, _scene())[0][
        "status"] == "blocked"
    scene = _scene()
    scene["contacts"] = [{**selector, "manner": "brace",
                           "relation": "surface", "motion": "settled"}]
    assert settle_sequence_dispositions([event], {}, scene)[0][
        "status"] == "executed"


def test_blocked_phase_prunes_only_explicitly_sourced_changes():
    diff = {
        "contact_ops": [
            {"op": "add", "source_event_id": "blocked"},
            {"op": "remove", "source_event_id": "allowed"},
        ],
        "poses": {
            "Reya": {"posture": "standing", "source_event_id": "blocked"},
            "Dana": {"posture": "standing"},
        },
        "positions": {"Dana": "bay", "Reya": "east_exit"},
        "phase_sources": {"positions.Reya": "blocked"},
    }
    dropped = prune_blocked_phase_changes(diff, [
        {"event_id": "blocked", "status": "blocked"},
        {"event_id": "allowed", "status": "executed"},
    ])
    assert diff["contact_ops"] == [{"op": "remove"}]
    assert set(diff["poses"]) == {"Dana"}
    assert diff["positions"] == {"Dana": "bay"}
    assert "phase_sources" not in diff
    assert {path for path, _ in dropped} == {
        "contact_ops", "poses.Reya", "positions.Reya"}


def test_phase_source_tags_survive_schema_until_causal_floor_consumes_them():
    diff = StateDiff(
        positions={"Reya": "east_exit"},
        phase_sources={"positions.Reya": "transfer",
                       "poses.Reya": "transfer"},
        poses={"Reya": {"posture": "standing"}},
    ).dict(exclude_unset=True)
    assert diff["phase_sources"] == {
        "positions.Reya": "transfer", "poses.Reya": "transfer"}
    prune_blocked_phase_changes(
        diff, [{"event_id": "transfer", "status": "blocked"}])
    assert diff["positions"] == {}
    assert diff["poses"] == {}
    assert "phase_sources" not in diff


def test_blocked_phase_prunes_a_record_citing_from_event():
    """`from_event` replaced `source_event_id` on the sheets and this floor
    still read only the old spelling, so a blocked phase's changes survived
    exactly to the degree a hand got provenance RIGHT. The two are read
    together, and `from_event` -- a declared field of the record, cited by the
    evidence seam and resolved by `story/attire.py` -- is left on the record
    rather than stripped the way the compatibility input is.

    Integer ids, because that is what the engine assigns: the floor compares
    as text so a span numbered 3 and a citation of 3 are the same event."""
    diff = {
        "attire": [
            {"subject": "Reya", "op": "remove", "item": "belt", "from_event": 3},
            {"subject": "Reya", "op": "wear", "item": "cloak", "from_event": 4},
        ],
        "poses": {
            "Reya": {"posture": "kneeling", "from_event": 3},
            "Dana": {"posture": "standing", "from_event": 4},
        },
    }
    dropped = prune_blocked_phase_changes(diff, [
        {"event_id": 3, "status": "blocked"},
        {"event_id": 4, "status": "executed"},
    ])
    assert [r["item"] for r in diff["attire"]] == ["cloak"]
    assert set(diff["poses"]) == {"Dana"}
    assert {path for path, _ in dropped} == {"attire", "poses.Reya"}
    # Kept records keep their citation; only the compatibility input is cut.
    assert diff["attire"][0]["from_event"] == 4
    assert diff["poses"]["Dana"]["from_event"] == 4


def test_a_zero_citation_is_no_citation_not_event_zero():
    """`from_event: 0` is the typed default, so every record in a diff carries
    it until normalization strips it. Reading zero as an event id would let a
    disposition numbered 0 delete a whole beat."""
    diff = {"poses": {"Reya": {"posture": "standing", "from_event": 0}}}
    dropped = prune_blocked_phase_changes(
        diff, [{"event_id": 0, "status": "blocked"}])
    assert diff["poses"] == {"Reya": {"posture": "standing", "from_event": 0}}
    assert dropped == []


def test_a_blocked_row_with_no_id_takes_nothing_with_it():
    """The floor's own promise: "untagged output is left alone; this floor
    never guesses which change a prose sentence meant." It was false for one
    input -- a blocked disposition whose `event_id` was missing joined the
    blocked set as the empty string, which is also what an untagged record
    cites, so a single such row deleted every untagged record in the diff."""
    diff = {
        "positions": {"Dana": "bay"},
        "attire": [{"subject": "Dana", "op": "wear", "item": "cloak"}],
    }
    dropped = prune_blocked_phase_changes(diff, [
        {"status": "blocked"},
        {"event_id": "", "status": "blocked"},
    ])
    assert diff["positions"] == {"Dana": "bay"}
    assert len(diff["attire"]) == 1
    assert dropped == []


def test_contact_release_invalidates_only_contact_bound_pose_relation():
    scene = _scene()
    scene["contacts"] = [{
        "actor": "Dana", "actor_part": "arm", "target": "Reya",
        "target_part": "back", "manner": "support",
        "relation": "surface", "motion": "settled",
    }]
    scene["poses"] = {
        "Reya": {"posture": "standing", "support": "Dana",
                 "relative_to": "Dana", "relation": "supported against",
                 "constraint": "held"},
        "Dana": {"posture": "standing", "relative_to": "Reya",
                 "relation": "facing"},
    }
    merged = merge_scene_with_diff(scene, {"contact_ops": [{
        "op": "remove", "actor": "Dana", "target": "Reya"}]})
    assert merged["poses"]["Reya"] == {
        "posture": "standing", "support": "", "relative_to": "",
        "relation": "", "constraint": "", "detail": "",
    }
    assert merged["poses"]["Dana"]["relation"] == "facing"


def test_typed_referents_disambiguate_same_pronoun_action():
    event = {"referents": [
        {"text": "her", "entity": "Mara", "role": "target_possessive",
         "occurrence": 1},
        {"text": "her", "entity": "Iris", "role": "actor_possessive",
         "occurrence": 2},
    ]}
    assert resolve_action_referents(
        "takes her hand with her left hand", event) == (
        "takes Mara's hand with Iris' left hand")
    assert resolve_action_referents(
        "takes her hand with her left hand", event,
        {"Mara": "you", "Iris": "Iris"}) == (
        "takes your hand with Iris' left hand")


class TestNormalizationKeepsTheSpansOwnFields:
    """`norm_sequence` rebuilds every element from a fixed key list, and the
    list never learned about `category` or `note` -- so the Director wrote
    three work items, three hands were dispatched, and every one of them was
    handed nothing.

    Measured live (`tools/interpret_beats.py`, beat 1, gemini-3.8-flash): the
    objects hand, given no work item, invented ids off `phase_id` and spent
    110s and 19,704 output tokens re-deriving the beat, then failed validation,
    then failed its repair. Two of the beat's six calls went on an identifier
    the engine had already assigned.

    Pinned at the FUNCTION, not at the view: the view is built from whatever
    this returns, so a test that hand-builds a view proves nothing about the
    path that lost them (the same mistake was made once already this week).
    """

    def _out(self, **element):
        base = {"type": "action", "attempt": "pull off my sword belt",
                "observable": "pulls off a sword belt"}
        base.update(element)
        return {"sequence": [base]}

    def test_a_category_and_a_note_survive(self):
        out = self._out(category="body", note="remove sword belt from worn gear")
        norm_sequence(out)
        span = out["sequence"][0]
        assert span["category"] == "body"
        assert span["note"] == "remove sword belt from worn gear"

    def test_a_list_of_categories_survives_unfolded(self):
        """Normalizing the value is `_span_items`' job. Folding it here too
        would put the vocabulary in two places, free to disagree."""
        out = self._out(category=["objects", "spatial"], note="onto the bench")
        norm_sequence(out)
        assert out["sequence"][0]["category"] == ["objects", "spatial"]

    def test_an_uncategorized_element_gains_no_category(self):
        """The common case, and the one the sheet calls common: an attempt
        whose outcome is contestable changes no ledger and names no family."""
        out = self._out()
        norm_sequence(out)
        assert "category" not in out["sequence"][0]
        assert "note" not in out["sequence"][0]

    def test_the_beats_item_numbers_survive_too(self):
        """Third field this key list has eaten in one day. `category` and
        `note` went first, and no work item reached any hand at all until that
        was found; `items` went the same way and the beat's item index came
        back empty on live output.

        `SPAN_FIELDS` is the single point of failure for anything the Director
        writes onto a sequence element, and a field added anywhere else without
        being added there is dropped between the model and every reader."""
        out = self._out(category="objects", note="set it down",
                        items=[{"id": 1, "name": "crate"}])
        norm_sequence(out)
        assert out["sequence"][0]["items"] == [{"id": 1, "name": "crate"}]

    def test_a_speech_span_keeps_its_own_ruling(self):
        out = {"sequence": [{"type": "speech", "text": "The reeve has it.",
                             "category": "social",
                             "note": "the reeve holding the ledger is public"}]}
        norm_sequence(out)
        span = out["sequence"][0]
        assert span["type"] == "speech"
        assert span["category"] == "social"

    def test_a_promoted_stage_direction_inherits_nothing(self):
        """A direction pulled out of spoken text is an act the Director never
        categorized. Giving it the speech's category would hand a hand a span
        nobody wrote -- and the engine would then hold that span open."""
        out = {"sequence": [{
            "type": "speech",
            "text": "*stands up* The reeve has it.",
            "category": "social", "note": "the claim is public"}]}
        norm_sequence(out)
        promoted = [e for e in out["sequence"] if e["type"] == "action"]
        speech = [e for e in out["sequence"] if e["type"] == "speech"]
        assert promoted and speech
        assert "category" not in promoted[0]
        assert speech[0]["category"] == "social"

    def test_the_whole_chain_still_numbers_them(self):
        """Through normalization AND `assign_event_ids`, which stamps a
        string id in a different id space. The two coexist: the span's number
        is the engine's chronology and the phase id is the causal graph's."""
        from agents import director
        out = {"sequence": [
            {"type": "action", "attempt": "pull off my sword belt",
             "category": "body", "note": "remove sword belt from worn gear"},
            {"type": "action", "attempt": "drop it on the bench",
             "category": "objects", "note": "move the belt onto the bench"},
        ]}
        norm_sequence(out)
        out["sequence"] = assign_event_ids(out["sequence"], "turn:1:p")
        spans = director._span_items(out)
        assert [s["event_id"] for s in spans] == [1, 2]
        assert [director.span_owners(s) for s in spans] == \
            [["body"], ["objects"]]
