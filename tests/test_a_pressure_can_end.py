"""A world pressure the passage shows over is resolved (2026-10-02).

The prose Director only ever ticked a pressure the beat's events touched, so
a finished process stayed open, stalled, and was handed back to the Director
as a due process to advance. Chat 160: the elevator crashed on turn 11, its
power-instability pressure stayed open, and on turn 13 the Director re-told
the descent to tick it -- the wrecked car set under way with no route, its
door gone from the world.
"""

from types import SimpleNamespace

from llm import decisions
from agents.director_prose import pressures_ended

PRESSURES = [
    {"id": "wp:0:1", "subject": "elevator_power_instability", "note": "the car runs on failing power"},
    {"id": "wp:0:0", "subject": "euclid_breach_active", "note": "a tremor shakes the building"},
]


def _ctx():
    warnings = []
    return SimpleNamespace(language=None, add_warning=warnings.append, warnings=warnings)


def test_the_pressure_the_passage_ends_is_resolved_and_the_other_is_not(monkeypatch):
    asked = []

    def answer(state, questions):
        asked.append((state, questions))
        return {k: {"type": "noul", "noul": 0.93 if "elevator power" in q["instructions"] else 0.08}
                for k, q in questions.items()}

    monkeypatch.setattr(decisions, "OVERRIDE", answer)
    got = pressures_ended(_ctx(), "The car hits the bottom of the shaft and lies still.", PRESSURES)
    assert got == {"wp:0:1": 0.93}
    (state, questions), = asked
    assert state.startswith("PASSAGE:\n") and "ledger" not in state.lower()
    assert len(questions) == 2


def test_no_passage_or_no_model_ends_nothing(monkeypatch):
    assert pressures_ended(_ctx(), "", PRESSURES) == {}

    def boom(state, questions):
        raise decisions.DecisionError("down")

    monkeypatch.setattr(decisions, "OVERRIDE", boom)
    ctx = _ctx()
    assert pressures_ended(ctx, "The car hits the bottom.", PRESSURES) == {}
    assert ctx.warnings and "world pressure" in ctx.warnings[0]
