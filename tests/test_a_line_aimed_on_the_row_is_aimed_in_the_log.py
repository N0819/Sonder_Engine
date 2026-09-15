"""A dialogue_log line with no addressee takes the one its own speech span
names.

The Director transcribes a character's line into dialogue_log with
`intended_target` null unless it thought to write one, while its causal
ledger row for the same line names the target. The background gate reads
only the log, so a line spoken TO a figure reached it as aimed at nobody
and the figure was never asked to answer (scratch play 2026-09-14, chat 9
turn 19: "Lead on, my dear sir" to Josiah Crane, row target `josiah_crane`,
log target null).
"""
from agents.director import _addressees_from_speech_spans

SCENE = {"entities": {"josiah_crane": {"name": "Josiah Crane", "kind": "person"}}}
CAST = {11: "Captain Edmund Hale"}


def test_an_entity_id_on_the_row_becomes_the_name_the_gate_matches():
    dlog = [{"speaker": "Captain Edmund Hale",
             "exact_quote": '"Lead on, my dear sir—after you."',
             "intended_target": None}]
    spans = [{"type": "speech", "actor": "character:11",
              "text": "Lead on, my dear sir—after you.",
              "targets": ["josiah_crane"]}]
    _addressees_from_speech_spans(dlog, spans, SCENE, CAST, "Clara")
    assert dlog[0]["intended_target"] == "Josiah Crane"


def test_a_filled_target_stands_and_a_self_target_is_nobody():
    dlog = [{"speaker": "Captain Edmund Hale", "exact_quote": '"Quite."',
             "intended_target": "Lady Ashcombe"},
            {"speaker": "Clara", "exact_quote": '"Mr Crane?"',
             "intended_target": None}]
    spans = [{"type": "speech", "actor": "character:11", "text": "Quite.",
              "targets": ["josiah_crane"]},
             {"type": "speech", "actor": "persona:9", "text": "Mr Crane?",
              "targets": ["persona:9"]}]
    _addressees_from_speech_spans(dlog, spans, SCENE, CAST, "Clara")
    assert dlog[0]["intended_target"] == "Lady Ashcombe"
    assert dlog[1]["intended_target"] is None


def test_the_span_must_be_the_same_speakers_same_words():
    dlog = [{"speaker": "Captain Edmund Hale", "exact_quote": '"After you."',
             "intended_target": None}]
    spans = [{"type": "speech", "actor": "persona:9", "text": "After you.",
              "targets": ["josiah_crane"]},
             {"type": "speech", "actor": "character:11", "text": "Not this.",
              "targets": ["josiah_crane"]}]
    _addressees_from_speech_spans(dlog, spans, SCENE, CAST, "Clara")
    assert dlog[0]["intended_target"] is None
