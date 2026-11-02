"""A memory recalled in a beat habituates once in that beat, however many
rounds the beat runs.

Habituation is the owner's "full for a few recalls, less after"
(`affect_mix.recall_lands`): each landing adds `HABITUATION_STEP`, rest
drains it. An interaction-loop beat runs the mind's call once per ROUND, and
every round handed the next its habits with no time passed
(`affect_pass.carried(..., earlier=...)`), so the second round landed a
second full step on the same memory -- the module's own rule is "one beat,
one moment" (review 2026-11-01, mind_affect_psychology F11, reproduced with
the real function: two rounds a beat dulled a memory to a fifth of its feeling
by the third beat, against the eighth with one).
"""

from __future__ import annotations

from mind import affect_mix, affect_pass

BASELINE = {"valence": 0.0, "arousal": 0.5}
MOMENT = {**affect_mix.looked(0.6, -0.5), "turn": 2, "key": "ferry:2", "at": 0.0}


def _context():
    return {"recent_memories": [{"event_key": "ferry:2", "details": "The ferry left without us.",
                                 "when": "about a minute ago"}],
            "_internal": {"feelings": {"ferry:2": {"record": {"moment": MOMENT}}}}}


def _round(earlier=None, active=None):
    return affect_pass.before_call("Ilse", {}, active or {}, BASELINE, 1.0,
                                   memory_context=_context(), earlier=earlier)


def _quiet(monkeypatch):
    monkeypatch.setattr(affect_pass.appraisal, "appraise",
                        lambda *a, **k: {"events": {}, "concerns": {}, "memories": {},
                                         "spectrums": {}, "moods": {}})


def test_a_second_round_of_one_beat_does_not_land_again(monkeypatch):
    _quiet(monkeypatch)
    first = _round()
    assert first.habits["ferry:2"]["h"] == affect_mix.HABITUATION_STEP
    second = _round(earlier=affect_pass.persisted(first))
    assert second.habits["ferry:2"]["h"] == affect_mix.HABITUATION_STEP


def test_the_next_beat_lands_again(monkeypatch):
    """Once per BEAT: the next beat's call (no `earlier`) is a new recall."""
    _quiet(monkeypatch)
    first = _round()
    kept = affect_pass.persisted(first)
    stored = {"mood_coords": kept["mood_coords"], "mood_habits": kept["mood_habits"],
              "mood_clock": kept["mood_clock"]}
    nxt = _round(active=stored)
    assert nxt.habits["ferry:2"]["h"] > affect_mix.HABITUATION_STEP
