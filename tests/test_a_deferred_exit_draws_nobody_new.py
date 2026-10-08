"""A deferred exit is still an exit.

Two of the interaction loop's early exits wait on somebody outside it: a line
turned to the PLAYER (`awaiting player response`) and an act the DIRECTOR must
resolve (`physical resolution required`). Both defer for the cast the beat
summoned (`_defer_to_unrun_reactor`) and for its focus, once
(`_defer_to_focus`), and both say what comes after: nobody new is drawn in,
and the beat ends when that cast has run.

Only a drained speaker who RE-triggered an exit was held to that. One who did
not fell through to the next-speaker draw, which brought back whoever had
perceived them -- usually the speaker still waiting on the player. Measured,
Brackwater (scratch play db, chat 166 turn idx 26): the brother asked the
player, the pilot was drained in and spoke to nobody, and the brother was
called a second time to ask the player again before the player had said a
word -- 1 of the 2,082 stored loops in which a line asked the player. The
deferral's own suites could not see it: their stand-ins perceive nobody, or
stub the draw out. These fixtures let everyone hear everyone, as one room
does, and keep the real draw.
"""

from __future__ import annotations

import inspect
import json

import agents.loops as loops
from story.character_schema import default_character_data


class _Chat:
    id = 1


class _Turn:
    idx = 26
    frame_id = None


class _Ctx:
    def __init__(self, reactors, cast=None, tom_triggers=()):
        self.chat = _Chat()
        self.turn = _Turn()
        self.cast = [
            {"id": cid, "sheet": json.dumps(default_character_data(f"Char{cid}")),
             "cstate": "{}", "active": 1, "stance": "{}"}
            for cid in (cast if cast is not None else reactors)
        ]
        self.director_interpret = {"flow": {
            "reactors": list(reactors), "tom_triggers": list(tom_triggers)}}
        self.perception_act = {"views": {}}
        self.reaction_results = {}
        self.reaction_loop = {}
        self.character_results = {}
        self.warnings = []
        self._extra = {}

    def get(self, key, default=None):
        return getattr(self, key, default) or default


def _install(monkeypatch, calls, *, asks_player=(), physical=()):
    """One room: every speaker is perceived by everybody else, and the
    next-speaker draw is the loop's own."""
    monkeypatch.setattr(loops, "dialogue_config", lambda cid: {
        "max_micro_rounds": 4, "max_character_calls": 6,
        "initial_parallel_reactors": 1, "stop_on_question_to_player": True,
        "allow_npc_to_npc_dialogue": True, "silence_ends_exchange": True,
    })
    monkeypatch.setattr(loops, "get_scene", lambda *a, **kw: {})
    monkeypatch.setattr(loops, "normalize_character_refs",
                        lambda refs, cast: [int(r) for r in refs
                                            if isinstance(r, int) or str(r).isdigit()])
    monkeypatch.setattr(loops, "_drop_non_awake", lambda ctx, ids: ids)
    monkeypatch.setattr(loops, "_drop_absent", lambda ctx, ids: ids)
    monkeypatch.setattr(loops, "_untargeted_order",
                        lambda ctx, ids, nonce: list(ids))
    monkeypatch.setattr(loops, "_merge_character_results",
                        lambda prev, new: new)
    monkeypatch.setattr(loops, "_requires_director_resolution",
                        lambda r: r["cid"] in physical and r["n"] == 1)
    monkeypatch.setattr(loops, "_asks_player",
                        lambda r, chat, cast: r["cid"] in asks_player)
    monkeypatch.setattr(
        loops, "deterministic_micro_perception",
        lambda ctx, actor_id, actor_result, scene, **kw: (
            {}, {row["id"] for row in ctx.cast if row["id"] != actor_id}))

    def step(ctx, cid, nonce):
        calls.append(cid)
        return {"cid": cid, "n": calls.count(cid),
                "sequence": [{"type": "speech", "text": f"{cid} speaks"}],
                "interaction": {"expects_response": True}}

    monkeypatch.setattr(loops, "character_step", step)


def test_the_asker_is_not_called_again_before_the_player_answers(monkeypatch):
    """The measured shape: the brother (83) asks the player, the pilot (81)
    is owed her first turn and takes it, and the beat stops there."""
    calls = []
    _install(monkeypatch, calls, asks_player={83})

    out = loops.interaction_loop(_Ctx(reactors=[83, 81]), nonce=0)

    assert calls == [83, 81], f"the asker was called again: {calls}"
    assert out["stop_reason"] == "awaiting player response"


def test_every_summoned_mind_still_has_its_first_turn(monkeypatch):
    calls = []
    _install(monkeypatch, calls, asks_player={1})

    out = loops.interaction_loop(_Ctx(reactors=[1, 2, 3]), nonce=0)

    assert calls == [1, 2, 3]
    assert out["stop_reason"] == "awaiting player response"


def test_a_pending_resolution_also_closes_the_beat_once_the_summoned_have_run(
        monkeypatch):
    calls = []
    _install(monkeypatch, calls, physical={1})

    out = loops.interaction_loop(_Ctx(reactors=[1, 2]), nonce=0)

    assert calls == [1, 2]
    assert out["stop_reason"] == "physical resolution required"


def test_the_focus_deferral_also_closes_the_beat(monkeypatch):
    """The focus is granted once, ahead of the exit; after it the exit
    stands, as it does for the summoned cast."""
    calls = []
    _install(monkeypatch, calls, asks_player={2})
    # The real draw's shape, in a fixed order: everyone who perceived the
    # speaker, those who already spoke included.
    monkeypatch.setattr(
        loops, "_next_speaker_candidates",
        lambda ctx, sid, perceived, spoke: [c for c in (2, 3, 1) if c != sid])

    out = loops.interaction_loop(
        _Ctx(reactors=[1], cast=[1, 2, 3], tom_triggers=[3]), nonce=0)

    assert calls == [1, 2, 3], calls
    assert out["stop_reason"] == "awaiting player response"


def test_with_nothing_owed_outside_the_loop_the_cast_may_go_on_talking(
        monkeypatch):
    """The rule closes a beat that is waiting on the player or the Director
    and no other: two people talking to each other still talk until the
    budget, a silence or a closed exchange ends it."""
    calls = []
    _install(monkeypatch, calls)

    out = loops.interaction_loop(_Ctx(reactors=[1, 2]), nonce=0)

    assert calls[:2] == [1, 2]
    assert len(calls) > 2, f"the exchange was cut short: {out['stop_reason']!r}"


def test_the_outside_exits_are_named_once():
    """The closed set the drain keys on is the loop's own stop reasons."""
    assert loops.EXITS_THAT_WAIT_OUTSIDE_THE_LOOP == {
        "awaiting player response", "physical resolution required"}
    source = inspect.getsource(loops.interaction_loop)
    for reason in loops.EXITS_THAT_WAIT_OUTSIDE_THE_LOOP:
        assert f'"{reason}"' in source
