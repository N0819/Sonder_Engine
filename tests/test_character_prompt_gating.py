"""The character contract is subtracted to the beat that actually happened.

`prompts.character_prompt` removes the paragraphs whose whole subject is a
payload key this beat does not carry. The properties worth pinning are not the
size it saves -- that moves with the story -- but the three that make the
saving safe: a beat carrying everything gets the document untouched, a gate can
never fire against a key that IS present, and the paragraphs that are an
INVITATION rather than an explanation are never gated at all.
"""

import json
import re

import pytest

from llm.prompts import CHARACTER_BLOCK_KEYS, DEFAULT_PROMPTS, character_prompt
from language_runtime import language_pack
from llm.schemas import validate_llm_output_strict

BASE = DEFAULT_PROMPTS["character"]

# Every gate satisfied, so nothing may be removed.
FULL = {
    "self": {
        "standing_contacts": [{"contact_ref": "contact:0"}],
        "speaking_now": {"articulation": "slurred"},
        "embodiment_capabilities": ["a"],
        "attire": "a coat",
        "decision_continuity": {"turn": 1, "chosen": "Find the key"},
        "earlier_this_beat": {
            "status": "proposed_before_resolution",
            "decision": {"chosen": "Ask where the key is"},
        },
        "following": {"target": "Hinami"},
        "project_review": {"why": "arrived"},
        "en_route": {"to": "the shrine"},
        "intentions": [{"id": "i1", "fading": 3}],
        "active_state": {"goal_reached": True, "goal_held": 9},
    },
    "memory": {
        "summary_citations": {"autobiographical_summary": {}},
        "earlier_in_my_life": [{"summary_id": "summary:firsthand:10"}],
        "surfaces_unbidden": {"memory_ref": "event:x"},
        "recalled_places": [{"name": "the bakery"}],
    },
    "perception": {
        "here_affords": ["rest"],
        "impossible_knowledge": [{"speaker": "the stranger",
                                  "line_ref": "current:1:0",
                                  "private_matter": "x"}],
        "sprint_reach": [{"rooms": 3}],
        "corridor_sight": [{"terminus": "dead_end"}],
        "spatial_frame": {
            "ground_fully_known": True,
            "ahead": [{"room": "the vault", "onward_exits_visible": 0,
                       "visibly_no_way_through": True, "been_there": True,
                       "circling_here": True}],
        },
    },
    # A FINISHED payload, which is what the gate reads -- so these carry the
    # names `agents.character.PAYLOAD_NAMES` projects them to, not the ones
    # the rest of the tree writes.
    "decision": {"they_said_nothing": True, "awaiting_your_answer": "?",
                 "comes_to_you": ["p"]},
    "active_hypotheses": [{"i_suspect": "x"}],
}

EMPTY = {"self": {}, "memory": {}, "perception": {}, "decision": {}}


def test_every_gate_still_points_at_a_real_paragraph():
    """The gate fails OPEN, so an orphaned marker costs nothing at runtime and
    is invisible -- which is exactly why it has to fail the suite instead. A
    prompt edit that renames a heading must be noticed here, not in a month of
    quietly shipping the paragraph it meant to gate."""
    lines = [line.strip() for line in BASE.split("\n")]
    for marker, _keys in CHARACTER_BLOCK_KEYS:
        assert any(line.startswith(marker) for line in lines), marker


def test_a_beat_that_carries_everything_gets_the_contract_untouched():
    assert character_prompt(FULL, base=BASE) == BASE


def test_a_beat_that_carries_nothing_drops_every_gated_paragraph():
    out = character_prompt(EMPTY, base=BASE)
    assert len(out) < len(BASE)
    for marker, _keys in CHARACTER_BLOCK_KEYS:
        assert not any(line.strip().startswith(marker)
                       for line in out.split("\n")), marker


@pytest.mark.parametrize("payload", [None, "", 7, []])
def test_a_payload_that_is_not_a_payload_changes_nothing(payload):
    assert character_prompt(payload, base=BASE) == BASE


def test_one_present_key_keeps_its_paragraph_and_only_its_paragraph():
    payload = {"self": {}, "memory": {}, "decision": {},
               "perception": {"sprint_reach": [{"rooms": 2}]}}
    out = character_prompt(payload, base=BASE)
    assert "RUNNING:" in out
    assert "Running is a GAIT," in out
    assert "ENDING CONTACT:" not in out


def test_a_paragraph_carrying_a_rule_beyond_its_heading_is_never_gated():
    """Gates were audited paragraph by paragraph, not by heading, and these two
    are why. `stops` ends on how to take a bearingless doorway AT A WALK, and
    "Running is an offer" ends on the rule that for a body whose drive is
    getting there, walking open ground is out of character. Both govern a beat
    with no run offer in it -- gate them on `sprint_reach` and the rule
    disappears exactly when it applies."""
    out = character_prompt(EMPTY, base=BASE)
    assert "`stops` is a fact about the passage" in out
    assert "Running is an offer and not an instruction" in out
    # Same shape: GOAL CURRENCY opens by explaining active_state.goal itself,
    # which is present on every beat whether or not it has spent its currency.
    assert "GOAL CURRENCY:" in out


def test_a_marker_stamped_on_any_exit_keeps_its_paragraph():
    """The spatial markers live on individual exits inside the frame's buckets,
    so presence is 'any exit in any bucket carries it', not a top-level key."""
    payload = {"self": {}, "memory": {}, "decision": {}, "perception": {
        "spatial_frame": {"left": [{"room": "a"},
                                   {"room": "b", "been_there": True}]}}}
    out = character_prompt(payload, base=BASE)
    assert "Your own route is marked too." in out
    assert "An exit may carry `onward_exits_visible`" not in out
    assert "`ground_fully_known`, on the frame itself" not in out


def test_a_stamped_zero_is_presence_not_absence():
    """`onward_exits_visible: 0` is the case that paragraph exists FOR -- nought
    other ways out is what a visible dead end is. A truthiness test read it as
    an absence and removed the explanation exactly when it was needed."""
    payload = {"self": {}, "memory": {}, "decision": {}, "perception": {
        "spatial_frame": {"ahead": [{"onward_exits_visible": 0}]}}}
    assert "An exit may carry `onward_exits_visible`" in character_prompt(
        payload, base=BASE)


def test_an_empty_container_is_absence_not_presence():
    """An empty list is a field with nothing in it, and a paragraph explaining
    how to read nothing is the thing this exists to remove."""
    out = character_prompt(
        {"self": {"standing_contacts": []}, "memory": {}, "perception": {},
         "decision": {}}, base=BASE)
    assert "ENDING CONTACT:" not in out


def test_the_paragraphs_that_are_invitations_are_never_gated():
    """The trap tools/fire_rates.py was written about: gate a mechanism on its
    own output and its fire rate is nailed at zero forever. `projects`,
    `belief_updates` and `association_updates` are things the model CREATES, so
    their instructions must survive a payload that holds none of them --
    0 of 14 live banks have ever held a project, and that is the argument for
    keeping the invitation, not for removing it."""
    out = character_prompt(EMPTY, base=BASE)
    for heading in ("PROJECTS:", "WANTS AND CHOICE:",
                    "SELF/WORLD BELIEF LEARNING:", "ASSOCIATIVE LEARNING:",
                    "READING A MEMORY DIFFERENTLY:", "WHEN TO PONDER:"):
        assert heading in out, heading
    gated = {marker for marker, _ in CHARACTER_BLOCK_KEYS}
    assert not (gated & {"PROJECTS:", "WANTS AND CHOICE:",
                         "SELF/WORLD BELIEF LEARNING:",
                         "ASSOCIATIVE LEARNING:"})


def test_the_firewall_paragraphs_are_never_gated():
    """What broke under payload compaction was a present/past discrimination,
    silently, while everything else looked fine. These paragraphs carry that
    discrimination and must survive every possible payload."""
    out = character_prompt(EMPTY, base=BASE)
    # Headings renamed 2026-08-29 when the agent was reframed into first
    # person; the paragraphs and the property are the same ones.
    # Renamed 2026-08-30 with their paragraphs: the evidence lanes became one
    # id rule when the citation arrays were retired, and SEQUENCES was reframed
    # from a form to return into the mechanism a body acts through.
    # Renamed 2026-09-13 in the miniaturized contract: HOW THIS GOES became
    # DELIBERATION and WANTS AND GOALS became WANTS AND CHOICE. Same
    # paragraphs, same property -- neither may be gated out of the prompt.
    for heading in ("WHAT YOU KNOW is", "MEMORY IS PAST:",
                    "EVIDENCE IS THE ID OF THE THING ITSELF.", "DELIBERATION:",
                    "SEQUENCES ARE HOW YOU ACT."):
        assert heading in out, heading


def test_character_contract_supplies_mechanisms_not_a_default_temperament():
    """Scope and urgency must not quietly author a cautious personality."""
    out = character_prompt(EMPTY, base=BASE)

    assert "CURRENT EVIDENCE, NOT DEFAULT TEMPERAMENT:" in out
    assert "This is an information rule only" in out
    # Was "creates no preference for caution" until MICRO-BEAT SCOPE was
    # renamed (2026-08-31). The property is the same one -- the scope rule
    # must not read as a temperament -- stated by the clause that replaced
    # the four disclaimers the old name needed.
    assert "Nothing here prefers a small move to a large one" in out
    assert "Do not seed caution, compromise, escalation, violence, mercy" in out
    assert "Urgency changes stakes and available time" in out
    assert "Urgency changes stakes and available time; it does not supply values" in out
    assert "Consider silence, a small response" not in out
    assert "It is a brake on unearned action" not in out
    assert "at least one response_candidate MUST pause" not in out
    assert "must be yielded to" not in out
    assert "at least one considered_response MUST address it" not in out


def test_surviving_text_keeps_its_authored_order_and_spacing():
    out = character_prompt(EMPTY, base=BASE)
    kept = [line for line in out.split("\n") if line.strip()]
    original = [line for line in BASE.split("\n") if line.strip()]
    assert kept == [line for line in original if line in kept]
    assert not re.search(r"\n{3,}", out)


@pytest.mark.parametrize("language", ["en", "ja"])
def test_hypotheses_explanation_reads_the_actual_top_level_payload(language):
    """The finished payload carries hypotheses beside self, not inside it."""
    card = language_pack(language).card("system_prompts")
    marker = next(marker for marker, paths in card["character_block_keys"]
                  if "active_hypotheses" in paths)
    assert marker in character_prompt(
        {"active_hypotheses": [{"i_suspect": "The offer is sincere"}]},
        language=language,
    )
    assert marker not in character_prompt(
        {"self": {"active_hypotheses": [{"i_suspect": "The offer is sincere"}]}},
        language=language,
    )


@pytest.mark.parametrize("language", ["en", "ja"])
@pytest.mark.parametrize("field,value", [
    ("decision_continuity", {"turn": 1, "chosen": "Open the door"}),
    ("earlier_this_beat", {"status": "proposed_before_resolution"}),
])
def test_private_continuity_instructions_follow_the_own_state_fields(
        language, field, value):
    card = language_pack(language).card("system_prompts")
    marker = next(marker for marker, paths in card["character_block_keys"]
                  if f"self.{field}" in paths)
    assert marker in character_prompt({"self": {field: value}}, language=language)
    assert marker not in character_prompt({field: value}, language=language)
    assert marker not in character_prompt({}, language=language)


@pytest.mark.parametrize("language", ["en", "ja"])
def test_character_output_example_matches_the_kernel_without_duplicate_affect(
        language):
    """The final copyable example must validate against the provider schema."""
    text = language_pack(language).card("system_prompts")["prompts"]["character"]
    line = next(line for line in text.splitlines()
                if '"state":{"appraisal":' in line)
    example, _ = json.JSONDecoder().raw_decode(line[line.index('{'):])
    report = validate_llm_output_strict("character_kernel", example)
    assert report.valid, report.errors

    assert set(example) == {
        "state", "sequence", "manifest", "updates", "effects", "interaction",
        "salience",
    }
    active = example["state"]["active"]
    assert "mood" not in active
    assert "baseline" not in active["affect"]
    assert set(active["affect"]) == {"surface", "undercurrent"}
    assert active["affect"]["undercurrent"] is None
    assert active["active_concerns"] == []
    assert report.output["state"]["decision"]["hinge"] == ""
    assert report.output["state"]["decision"]["uncertainty"] == ""
    assert set(example["updates"]["memory"]) == {"keep", "reinterpret", "effects"}

    # The worked belief revision must also satisfy the current strict row
    # contract; copying it should never turn a revision into a silent no-op.
    belief_line = next(line for line in text.splitlines()
                       if '{"operation":"revise"' in line)
    belief, _ = json.JSONDecoder().raw_decode(
        belief_line[belief_line.index('{"operation":"revise"'):])
    assert {"belief", "operation", "target_belief", "confidence", "evidence"} <= set(belief)
    assert belief["belief"] != belief["target_belief"]
    assert belief["target_belief"] and belief["evidence"]
    example["updates"]["beliefs"] = [belief]
    report = validate_llm_output_strict("character_kernel", example)
    assert report.valid, report.errors


def test_character_state_and_learning_instructions_match_their_commit_meaning():
    text = character_prompt(FULL, base=BASE)
    assert "propose the feelings you now carry, including feelings that persist" in text
    assert "not proof that the intended action succeeded" in text
    assert "`status:proposed_before_resolution`" in text
    assert "`self.active_state` holds settled emotion values" in text
    assert "physical facts come from `self.body_state` and current perception" in text
    assert "explicit `undercurrent:null` clears" in text
    assert "`[]` clears them" in text
    assert "Use `updates.memory.keep` rows" in text
    assert "`reinforce` acquires a belief" in text
    assert "copy the exact held claim into `target_belief`" in text
    assert "`belief` and `confidence` are the desired replacement and its confidence" in text
    assert "unadopted possibilities belong in appraisal or decision uncertainty" in text
    assert "Every update requires" in text and "nonempty grounded evidence" in text
    assert "`target_belief:''`" in text
    assert "target_belief?" not in text
    assert "at most 240 characters each" in text
    assert "`state` is transient" not in text


def test_terse_voice_obeys_the_explicit_line_budget_and_mouth_rules_stay_core():
    text = character_prompt(EMPTY, base=BASE)
    assert "terse voice must not be inflated within each line" in text
    assert "If speaking, meet `min_lines`" in text
    assert "unless impossible or a deliberate in-character refusal" in text
    assert "must not be inflated to reach a line floor" not in text
    assert "WHAT YOUR MOUTH IS DOING:" in text
    assert "SPEAKING WITH YOUR MOUTH ENGAGED:" not in text
    assert text.count("At most one per beat") == 1
