"""The consciousness floor for the OTHER minds the engine runs.

`tests/test_awareness_player_floor.py` covers the player: a mind the diff took
away on nothing, guarded because a gate on the player removes their view and
their next move. This covers the same imposition against a CAST member, found
in live play (owner's scripted run, 2026-08-17, turn 13). The player wrote:

    "The hooded figure sags against the gate and slides down it, out cold.
     I kneel and check whether they are breathing."

and the Director's state_diff.conditions came back with TWO gated awareness
rows sharing the cause "collapse against gate": one on the hooded figure, who
did collapse, and one on Halden, the lift operator standing beside them, whom
nothing in the beat put under. Both committed active. A gated cast mind runs
no character step (agents/character.py's consciousness gate), and for
'unconscious' the deterministic exits never fire (a rouse only ends 'asleep',
the clock only ends 'asleep') -- so the spurious gate is not "one beat of
silence" but a mind removed from play until the Director volunteers an ending,
which across the author's whole corpus it has never once done.

Scope is minds the engine RUNS: the cast. A body with no run mind -- the
hooded figure itself, any background presence -- gets no floor: a condition on
it is descriptive state, not a switch, and its label has no canonical spelling
to attribute prose against. Support is read PER SUBJECT but generously: any
sleep/knockout cue sharing an unbroken sentence with the subject's name, in
the player's input, the resolved prose, or a spoken line. A bystander merely
co-mentioned with the fallen one ("Halden kneels beside the unconscious
figure") therefore stays the Director's call -- strictly looser than the
omission scan's nearest-name clause attribution, so the two floors can never
fight over the same subject.
"""

from __future__ import annotations

import pytest

from agents.director import _unsupported_character_awareness
from story.scene import NON_AWAKE_GATED, apply_awareness_diff, awareness_of

PLAYER = "Rin"
CAST = ["Halden"]

# The live beat, verbatim.
LIVE_INPUT = (
    "The hooded figure sags against the gate and slides down it, out cold. "
    "I kneel and check whether they are breathing."
)
LIVE_CONDITIONS = {
    "cond_awareness_001": [{
        "condition_id": "cond_awareness_001",
        "subject_id": "Halden",
        "kind": "awareness",
        "state": {"level": "unconscious", "cause": "collapse against gate"},
    }],
    "cond_unconscious_001": [{
        "condition_id": "cond_unconscious_001",
        "subject_id": "hooded_figure",
        "kind": "awareness",
        "state": {"level": "unconscious", "cause": "collapse against gate"},
    }],
}


def _awareness(level, subject="Halden", key="c1", **extra):
    return {key: [{
        "condition_id": key, "subject_id": subject, "kind": "awareness",
        "state": {"level": level}, **extra,
    }]}


def _floor(conditions, player_input="", resolved_event="", dialogue_log=(),
           cast=CAST, player=PLAYER, live_ids=frozenset()):
    return _unsupported_character_awareness(
        conditions, cast, player, player_input, resolved_event,
        list(dialogue_log), live_ids)


class TestTheLiveBeat:
    def test_the_bystanders_gate_is_dropped_and_the_fallen_ones_kept(self):
        assert _floor(LIVE_CONDITIONS, LIVE_INPUT) == [
            ("cond_awareness_001", "Halden", "unconscious")]

    def test_the_subject_id_form_still_matches_the_cast_name(self):
        # The diff may spell the subject "halden" against a cast "Halden";
        # identity is compared loosely, as the player floor compares it, or
        # the guard would never fire on real data.
        conditions = _awareness("unconscious", subject="  hal-den ")
        assert _floor(conditions, LIVE_INPUT)

    def test_without_the_guard_the_bystander_would_be_gated(self):
        # What the fix prevents, stated in the terms the character step reads.
        amap = apply_awareness_diff({}, {"conditions": LIVE_CONDITIONS})
        assert awareness_of(amap, "Halden") in NON_AWAKE_GATED


class TestWhatStaysAllowed:
    def test_the_beat_doing_it_to_them(self):
        assert _floor(
            _awareness("unconscious"),
            resolved_event="Halden takes the blow and slumps unconscious.",
        ) == []

    def test_a_bystander_co_mentioned_in_the_cue_sentence_is_kept(self):
        # Support is sentence co-occurrence, deliberately looser than the
        # omission scan's nearest-name attribution: this decides whether to
        # KEEP the Director's judgement, and ambiguous prose stays its call.
        assert _floor(
            _awareness("unconscious"),
            resolved_event="Halden kneels beside the unconscious figure.",
        ) == []

    def test_support_can_come_from_the_players_input(self):
        assert _floor(
            _awareness("asleep"),
            player_input="I sing until Halden drifts off in his chair.",
        ) == []

    def test_support_can_come_from_spoken_dialogue(self):
        assert _floor(
            _awareness("sedated"),
            dialogue_log=[{"exact_quote": "Halden's been sedated, look."}],
        ) == []

    def test_waking_is_never_touched(self):
        assert _floor(
            _awareness("unconscious", active=0),
            resolved_event="Halden stirs.",
        ) == []

    def test_dazed_is_not_gated_so_it_is_left_alone(self):
        assert _floor(_awareness("dazed")) == []

    def test_a_live_condition_reasserted_is_not_an_onset(self):
        # A mind already under says nothing about going under this beat, and
        # that silence is normal. Only a NEW gate needs the beat to own it.
        assert _floor(
            _awareness("unconscious"),
            resolved_event="Halden lies where he fell.",
            live_ids={"c1"},
        ) == []

    def test_the_player_belongs_to_the_player_floor(self):
        assert _floor(
            _awareness("asleep", subject=PLAYER), cast=[PLAYER] + CAST,
        ) == []

    def test_a_body_with_no_run_mind_is_the_directors_business(self):
        # "hooded_figure" is nobody in the cast: a condition on it is
        # descriptive state, not a switch on a mind the engine runs.
        assert _floor(
            _awareness("unconscious", subject="hooded_figure"),
        ) == []

    def test_a_non_awareness_condition_is_untouched(self):
        conditions = {"c1": [{
            "condition_id": "c1", "subject_id": "Halden", "kind": "wound",
            "state": {"level": "unconscious"},
        }]}
        assert _floor(conditions) == []


class TestSentencesAreTheBarrier:
    def test_a_cue_in_the_previous_sentence_is_no_support(self):
        assert _floor(
            _awareness("unconscious"),
            resolved_event="The stranger collapses, out cold. "
                           "Halden staggers back from the gate.",
        ) == [("c1", "Halden", "unconscious")]

    def test_a_full_width_terminator_is_a_barrier_too(self):
        # The pack-aware breaks the neighbouring scans use, not a new \b:
        # a kana name has no word boundary against the particle after it,
        # and 。 ends a sentence exactly as '.' does.
        conditions = {
            "t1": [{"condition_id": "t1", "subject_id": "タマモ",
                    "kind": "awareness", "state": {"level": "unconscious"}}],
            "h1": [{"condition_id": "h1", "subject_id": "ハルデン",
                    "kind": "awareness", "state": {"level": "unconscious"}}],
        }
        assert _floor(
            conditions,
            resolved_event="タマモは passes out。ハルデンは looks on.",
            cast=["タマモ", "ハルデン"],
        ) == [("h1", "ハルデン", "unconscious")]


class TestTheFloorsCannotFight:
    """Any subject the omission scan could flag is one this floor keeps: the
    scan needs a cue clause-attributed to the name within the token gap, and
    sentence co-occurrence is strictly weaker. So a drop here can never create
    the very omission the scan below it would then re-report."""

    @pytest.mark.parametrize("prose", [
        "The blow makes Halden pass out.",
        "Halden goes limp against the gate.",
        "Halden is knocked out cold.",
    ])
    def test_whatever_the_scan_attributes_the_floor_supports(self, prose):
        from agents.director import _untracked_unconsciousness_subjects

        assert _untracked_unconsciousness_subjects(
            prose, [], {}, CAST) == ["Halden"]
        assert _floor(_awareness("unconscious"), resolved_event=prose) == []


class TestAtTheReconciliationSeam:
    """End-to-end through `_reconcile_resolution`'s Tier-0 floor, which is
    where the drop actually has to happen for the diff that reaches commit."""

    def _ctx_and_out(self, temp_db, player_input, conditions):
        import json
        import time

        from core.pipeline_context import ChatData, PipelineContext, TurnData

        persona = temp_db.qi(
            "INSERT INTO personas(name,sheet) VALUES(?,?)",
            (PLAYER, json.dumps({"identity": {"name": PLAYER}})),
        )
        cid = temp_db.qi(
            "INSERT INTO chats(name,persona_id,scenario,created) "
            "VALUES(?,?,?,?)",
            ("Gate", persona, "", time.time()),
        )
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)",
            (cid, 13, player_input, time.time()),
        )

        ctx = PipelineContext(
            chat=ChatData(id=cid, name="Gate", persona_id=persona,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=cid, idx=13,
                          player_input=player_input, created=time.time(),
                          frame_id=None),
            cast=[], input=player_input,
        )
        out = {
            "resolved_event": ("The figure slides down the gate and lies "
                               "still. Halden hovers, uncertain."),
            "dialogue_log": [],
            "state_diff": {"conditions": conditions},
        }
        return ctx, out

    def test_the_spurious_condition_never_reaches_commit(self, temp_db):
        from agents.director import _reconcile_resolution

        ctx, out = self._ctx_and_out(
            temp_db, LIVE_INPUT, dict(LIVE_CONDITIONS))
        _reconcile_resolution(ctx, out, {}, {}, {}, [], ["Halden", PLAYER])

        conditions = out["state_diff"]["conditions"]
        assert "cond_awareness_001" not in conditions
        assert "cond_unconscious_001" in conditions
        assert any("Dropped awareness" in w and "Halden" in w
                   for w in ctx.warnings)

    def test_a_supported_condition_survives_the_seam(self, temp_db):
        from agents.director import _reconcile_resolution

        ctx, out = self._ctx_and_out(
            temp_db, "I catch Halden as he faints.",
            _awareness("unconscious"))
        _reconcile_resolution(ctx, out, {}, {}, {}, [], ["Halden", PLAYER])

        assert "c1" in out["state_diff"]["conditions"]
