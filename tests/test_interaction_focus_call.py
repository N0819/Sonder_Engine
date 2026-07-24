"""Regression test for V1 (enterprise_d_v3 findings): a beat must not end with
its own focus character unsimulated.

Live symptom, turn 8 of the v3 run. The player pressed Dr. Vorne — the episode's
drive-rupture subject — on the one question aimed at his drive. The Director
flagged him in `flow.tom_triggers`, and Picard's generated line explicitly
handed him the floor ("Doctor, I would hear your answer as well"). The
interaction loop then stopped with `awaiting player response` after ONE call,
with 5 of 6 permitted calls unused, and Vorne's agent never ran. The narrator
rendered "He does not speak" as a characterful refusal that no agent had chosen.

The cost is not only dramatic: drive strain accrues from appraisal
`goal_impacts`, which exist only for characters that actually ran. Skipping the
focus character on exactly the beats aimed at his drive pinned his strain at 0.0
and made a rupture unreachable regardless of the accrual arithmetic.
"""

from __future__ import annotations

import json

import agents.loops as loops
from character_schema import default_character_data


class _Chat:
    id = 1


class _Turn:
    idx = 5
    frame_id = None


class _Ctx:
    """Minimal stand-in for PipelineContext covering what interaction_loop reads."""

    def __init__(self, reactors, tom_triggers):
        self.chat = _Chat()
        self.turn = _Turn()
        self.cast = [
            {"id": cid, "sheet": json.dumps(default_character_data(f"Char{cid}")),
             "state": "{}", "active": 1, "stance": "{}"}
            for cid in reactors
        ]
        self.director_interpret = {
            "flow": {
                "reactors": reactors,
                "tom_triggers": tom_triggers,
                "dialogue_mode": True,
            }
        }
        self.perception_act = {"views": {}}
        self.reaction_results = {}
        self.reaction_loop = {}
        self.character_results = {}
        self.warnings = []
        self._extra = {}

    def get(self, key, default=None):
        return getattr(self, key, default) or default


def _install(monkeypatch, calls_log, asks_player_ids):
    """Every character 'speaks'; those in asks_player_ids end on a question to
    the player, which is what normally stops the beat."""
    monkeypatch.setattr(loops, "dialogue_config", lambda cid: {
        "max_micro_rounds": 4,
        "max_character_calls": 6,
        "stop_on_question_to_player": True,
        "allow_npc_to_npc_dialogue": True,
        "max_speakers_per_round": 1,
    })
    monkeypatch.setattr(loops, "get_scene", lambda *a, **kw: {})
    monkeypatch.setattr(loops, "normalize_character_refs",
                        lambda refs, cast: [int(r) for r in refs if str(r).isdigit()
                                            or isinstance(r, int)])
    monkeypatch.setattr(loops, "_drop_non_awake", lambda ctx, ids: ids)
    monkeypatch.setattr(loops, "_requires_director_resolution", lambda r: False)
    monkeypatch.setattr(loops, "_sequence_has_content", lambda r: True)
    monkeypatch.setattr(loops, "_merge_character_results",
                        lambda prev, new: new)
    # Returns (delivered_views, perceived_by); the real one needs full sheets.
    monkeypatch.setattr(loops, "deterministic_micro_perception",
                        lambda ctx, actor_id, actor_result, scene: ({}, set()))
    monkeypatch.setattr(loops, "_asks_player",
                        lambda result, chat, cast: result["cid"] in asks_player_ids)

    def fake_character_step(ctx, cid, nonce):
        calls_log.append(cid)
        return {"cid": cid, "sequence": [{"type": "speech", "line": f"{cid} speaks"}]}

    monkeypatch.setattr(loops, "character_step", fake_character_step)


def test_focus_character_answers_before_the_beat_yields(monkeypatch):
    """Picard (26) speaks first and turns to the player; Vorne (27) is the
    flagged focus and must still get his call."""
    calls = []
    _install(monkeypatch, calls, asks_player_ids={26})
    ctx = _Ctx(reactors=[26, 27, 28], tom_triggers=[27])

    out = loops.interaction_loop(ctx, nonce=0)

    assert 27 in calls, (
        "focus character never ran; beat ended with the mind it was about "
        f"unsimulated (calls={calls}, stop={out.get('stop_reason')!r})")
    assert calls.index(26) < calls.index(27)


def test_focus_character_is_deferred_to_only_once(monkeypatch):
    """If the focus character ALSO turns to the player, the beat ends — the
    guard must not let the loop hold itself open."""
    calls = []
    _install(monkeypatch, calls, asks_player_ids={26, 27})
    ctx = _Ctx(reactors=[26, 27, 28], tom_triggers=[27])

    out = loops.interaction_loop(ctx, nonce=0)

    assert calls == [26, 27]
    assert out["stop_reason"] == "awaiting player response"


def test_unflagged_beat_still_yields_immediately(monkeypatch):
    """No tom_triggers -> the original stop behaviour is untouched."""
    calls = []
    _install(monkeypatch, calls, asks_player_ids={26})
    ctx = _Ctx(reactors=[26, 27, 28], tom_triggers=[])

    out = loops.interaction_loop(ctx, nonce=0)

    assert calls == [26]
    assert out["stop_reason"] == "awaiting player response"


def test_focus_character_who_already_spoke_is_not_recalled(monkeypatch):
    """The guard is for a focus character who never ran, not a second helping."""
    calls = []
    _install(monkeypatch, calls, asks_player_ids={27})
    ctx = _Ctx(reactors=[27, 26], tom_triggers=[27])

    out = loops.interaction_loop(ctx, nonce=0)

    assert calls == [27]
    assert out["stop_reason"] == "awaiting player response"
