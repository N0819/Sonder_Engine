"""The character contract is subtracted to the beat that actually happened.

`prompts.character_prompt` removes the paragraphs whose whole subject is a
payload key this beat does not carry. The properties worth pinning are not the
size it saves -- that moves with the story -- but the three that make the
saving safe: a beat carrying everything gets the document untouched, a gate can
never fire against a key that IS present, and the paragraphs that are an
INVITATION rather than an explanation are never gated at all.
"""

import re

import pytest

from llm.prompts import CHARACTER_BLOCK_KEYS, DEFAULT_PROMPTS, character_prompt

BASE = DEFAULT_PROMPTS["character"]

# Every gate satisfied, so nothing may be removed.
FULL = {
    "self": {
        "standing_contacts": [{"contact_ref": "contact:0"}],
        "speaking_now": {"articulation": "slurred"},
        "embodiment_capabilities": ["a"],
        "attire": "a coat",
        "active_hypotheses": [{"i_suspect": "x"}],
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
        "sprint_reach": [{"rooms": 3}],
        "corridor_sight": [{"terminus": "dead_end"}],
        "spatial_frame": {
            "ground_fully_known": True,
            "ahead": [{"room": "the vault", "onward_exits_visible": 0,
                       "visibly_no_way_through": True, "been_there": True,
                       "circling_here": True}],
        },
    },
    "decision": {"player_said_nothing": True, "awaiting_your_answer": "?",
                 "authorial_offers": ["p"]},
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
    for heading in ("PROJECTS:", "WANTS AND GOALS:",
                    "SELF/WORLD BELIEF LEARNING:", "ASSOCIATIVE LEARNING:",
                    "READING A MEMORY DIFFERENTLY:", "WHEN TO PONDER:"):
        assert heading in out, heading
    gated = {marker for marker, _ in CHARACTER_BLOCK_KEYS}
    assert not (gated & {"PROJECTS:", "WANTS AND GOALS:",
                         "SELF/WORLD BELIEF LEARNING:",
                         "ASSOCIATIVE LEARNING:"})


def test_the_firewall_paragraphs_are_never_gated():
    """What broke under payload compaction was a present/past discrimination,
    silently, while everything else looked fine. These paragraphs carry that
    discrimination and must survive every possible payload."""
    out = character_prompt(EMPTY, base=BASE)
    for heading in ("EPISTEMIC FIREWALL:", "MEMORY IS PAST:",
                    "EVIDENCE HAS TWO LANES.", "DECISION PROCEDURE:",
                    "SEQUENCES:"):
        assert heading in out, heading


def test_surviving_text_keeps_its_authored_order_and_spacing():
    out = character_prompt(EMPTY, base=BASE)
    kept = [line for line in out.split("\n") if line.strip()]
    original = [line for line in BASE.split("\n") if line.strip()]
    assert kept == [line for line in original if line in kept]
    assert not re.search(r"\n{3,}", out)
