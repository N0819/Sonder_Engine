"""Speaking turns and the page.

Every fixture in this file is a VERBATIM shape pulled out of a stored live
run (chat 98, the 40-turn bridge run recorded 2026-08-28), not a shape the
author of the fix invented. Two guards in this repo have shipped inert
because a fixture agreed with the mistake it was written to catch; the
answer, recorded in the run's own defect register, is to pin the SHAPE
against real data.
"""
import json

import pytest

from agents import composer
from agents.common import fuse_speech_run


def _speech(text, **over):
    """One speech element exactly as `norm_sequence` emits it. The key set is
    copied from chat 98 turn 29's stored `interaction_loop`."""
    element = {
        "type": "speech", "text": text, "volume": "normal", "tone": "",
        "interrupts": "", "visibility": "overt", "conceal_from": [],
        "targets": [], "phase_id": "", "phase": "atomic",
        "depends_on": [], "participants": [],
    }
    element.update(over)
    return element


#: Jean-Luc Picard's round 3, chat 98 turn 29, byte for byte off the stored
#: variant. Three speech elements, no conduct between them, three different
#: tones -- and on the page they became three quoted lines set back to back.
TURN_29_ROUND_3 = [
    _speech("Acknowledged, Commander Data. The agreement between methods "
            "is noted.", tone="measured formal",
            event_id="turn:3058:character:74:0:speech"),
    _speech("The sudden activation after a clean survey eleven years prior "
            "suggests an event of artificial initiation.", tone="precise",
            event_id="turn:3058:character:74:1:speech"),
    _speech("What does this timing imply regarding possible triggers or "
            "purpose?", tone="inquisitive",
            event_id="turn:3058:character:74:2:speech"),
]

#: One round's `delivered_views` entry for one observer, from the same stored
#: turn. It is a LIST of rendered lines, which is the shape the outcome
#: composer was handing to a one-line percept builder.
TURN_29_DELIVERED = [
    'the bald compact upright fifty-six-year-old human says: '
    '"Acknowledged, Lieutenant."',
    'the bald compact upright fifty-six-year-old human says: '
    '"The sudden appearance after a clean survey eleven years prior is noted."',
    'the bald compact upright fifty-six-year-old human says: '
    '"Commander Data, evaluate what this timing implies for an artificial '
    'construction or activation event."',
]


class TestOneMouthOneUtterance:
    def test_a_recorded_three_line_run_becomes_one_delivery(self):
        out = {"sequence": [dict(e) for e in TURN_29_ROUND_3]}
        warnings = []
        fuse_speech_run(out, warn=warnings.append)
        assert len(out["sequence"]) == 1
        assert out["sequence"][0]["text"] == (
            "Acknowledged, Commander Data. The agreement between methods is "
            "noted. The sudden activation after a clean survey eleven years "
            "prior suggests an event of artificial initiation. What does this "
            "timing imply regarding possible triggers or purpose?")
        assert warnings and "separate beats of talk" in warnings[0]

    def test_no_word_is_invented_or_dropped(self):
        out = {"sequence": [dict(e) for e in TURN_29_ROUND_3]}
        fuse_speech_run(out)
        fused = out["sequence"][0]["text"]
        for element in TURN_29_ROUND_3:
            assert element["text"] in fused

    def test_a_run_that_changed_register_keeps_no_single_tone(self):
        """No one adverbial is true of a delivery that shifted register."""
        out = {"sequence": [dict(e) for e in TURN_29_ROUND_3]}
        fuse_speech_run(out)
        assert out["sequence"][0]["tone"] == ""

    def test_a_run_that_kept_one_tone_keeps_it(self):
        out = {"sequence": [_speech("One.", tone="measured"),
                            _speech("Two.", tone="measured")]}
        fuse_speech_run(out)
        assert out["sequence"][0]["tone"] == "measured"

    def test_conduct_between_two_lines_keeps_them_two(self):
        """A line delivered between other conduct is a separate beat of talk
        -- which is what the speech budget asks for and must survive."""
        out = {"sequence": [
            _speech("One."),
            {"type": "action", "attempt": "turns toward the console",
             "observable": "turns toward the console", "visibility": "overt",
             "conceal_from": [], "targets": [], "phase": "atomic",
             "phase_id": "", "depends_on": [], "participants": []},
            _speech("Two."),
        ]}
        fuse_speech_run(out)
        kinds = [e["type"] for e in out["sequence"]]
        assert kinds == ["speech", "action", "speech"]

    @pytest.mark.parametrize("differing", [
        {"volume": "whisper"},
        {"visibility": "concealed", "conceal_from": ["someone"]},
        {"targets": ["someone"]},
        {"phase": "staged", "phase_id": "ph1"},
    ])
    def test_a_different_delivery_is_a_different_delivery(self, differing):
        out = {"sequence": [_speech("One."), _speech("Two.", **differing)]}
        fuse_speech_run(out)
        assert len(out["sequence"]) == 2

    def test_a_line_that_cuts_in_keeps_its_boundary(self):
        out = {"sequence": [_speech("One."),
                            _speech("Two.", interrupts="someone")]}
        fuse_speech_run(out)
        assert len(out["sequence"]) == 2

    def test_the_scalar_mirror_carries_the_whole_utterance(self):
        """`result['speech']` is read as "what they said". Before the fuse it
        held only the FIRST atom of a multi-line round, which is how an audit
        of chat 98 came within one step of reporting the Director as the
        author of a captain's dialogue."""
        out = {"sequence": [dict(e) for e in TURN_29_ROUND_3]}
        fuse_speech_run(out)
        assert out["speech"] == out["sequence"][0]["text"]

    def test_two_separate_runs_each_fuse(self):
        out = {"sequence": [
            _speech("One."), _speech("Two."),
            {"type": "action", "attempt": "a", "observable": "a",
             "visibility": "overt", "conceal_from": [], "targets": []},
            _speech("Three."), _speech("Four."),
        ]}
        fuse_speech_run(out)
        assert [e.get("text") for e in out["sequence"]] == [
            "One. Two.", None, "Three. Four."]

    def test_it_is_idempotent(self):
        out = {"sequence": [dict(e) for e in TURN_29_ROUND_3]}
        fuse_speech_run(out)
        once = json.dumps(out["sequence"])
        fuse_speech_run(out)
        assert json.dumps(out["sequence"]) == once

    def test_a_single_line_round_is_untouched(self):
        out = {"sequence": [_speech("Only this.")]}
        warnings = []
        fuse_speech_run(out, warn=warnings.append)
        assert len(out["sequence"]) == 1 and not warnings

    def test_the_character_stage_runs_it(self):
        """A guard nothing calls is a guard that does not exist -- this repo
        has shipped two. Pin the wiring, not just the function."""
        import inspect
        from agents import character
        source = inspect.getsource(character.character_step)
        assert "fuse_speech_run" in source


class TestAMicroRoundDeliversLines:
    def test_the_recorded_list_shape_makes_one_percept_per_line(self):
        percepts = composer.micro_round_percepts(TURN_29_DELIVERED)
        assert len(percepts) == 3
        assert [p.data["desc"] for p in percepts] == [
            " ".join(line.split()) for line in TURN_29_DELIVERED]

    def test_no_python_repr_reaches_the_view(self):
        """Measured on chat 98: 68 of 142 stored character views carried a
        `['...']` span, on 24 of the 38 turns."""
        percepts = composer.micro_round_percepts(TURN_29_DELIVERED)
        for percept in percepts:
            assert "['" not in percept.data["desc"]
            assert '", "' not in percept.data["desc"]

    def test_each_delivered_line_dedupes_on_itself(self):
        percepts = composer.micro_round_percepts(TURN_29_DELIVERED)
        assert len({p.dedupe_key for p in percepts}) == 3

    def test_a_bare_string_is_one_delivery(self):
        assert len(composer.micro_round_percepts("He nods once.")) == 1

    def test_nothing_delivered_is_no_percepts(self):
        assert composer.micro_round_percepts(None) == []
        assert composer.micro_round_percepts([]) == []
        assert composer.micro_round_percepts(["", "   "]) == []

    def test_the_outcome_composer_uses_it(self):
        import inspect
        from agents import perception
        source = inspect.getsource(perception)
        assert "micro_round_percepts(additions)" in source
        assert "micro_round_percept(additions)" not in source


class TestTheNarratorIsToldWhatThePlayerWears:
    def test_the_payload_carries_the_players_own_ledger(self):
        """The narrator sheet already forbids extending "what anyone wears".
        It was never handed the record, so it wrote one: chat 98 t27 put "her
        uniform sleeve" on a body whose ledger read combadge + civilian
        clothing."""
        import inspect
        from agents import narration
        source = inspect.getsource(narration.narrator)
        assert "player_attire" in source
        assert "compact_attire" in source

    def test_the_sheet_tells_the_model_the_ledger_owns_it(self):
        from llm.prompts import DEFAULT_PROMPTS
        sheet = DEFAULT_PROMPTS["narrator"]
        assert "player_attire" in sheet
