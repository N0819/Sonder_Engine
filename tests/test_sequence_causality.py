from agents.common import (
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
