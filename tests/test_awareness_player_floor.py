"""The other direction of the consciousness floor: a mind taken away on nothing.

`tests/test_awareness.py` covers the miss — a knockout the diff forgot, leaving
an unconscious character perceiving normally. This covers the false positive,
found in live play (chat 40 "Hmmm ⎇0", turn 8). The player wrote:

    "You breath softly as you close your eyes wrapping your arms around her as
     well as two of your tails that curl around her seemingly of their own will."

resting against another character, and the Director recorded `awareness` level
`asleep` on the PLAYER with cause "settling into rest and protective affection
after arrival". `asleep` is in NON_AWAKE_GATED, so the player's own next view
became "You are under, below waking." — the scene taken away for closing their
eyes in a cuddle, endable only by the Director choosing to end it.

The asymmetry that justifies a floor: for an NPC a spurious non-awake level
costs one beat of silence, but for the player it removes both their view of the
story and their next move — the Director overriding declared player conduct in
its strongest form. So the player alone is protected, only against levels that
gate, and only when nothing in the beat supports going under. Waking is never
touched.
"""

from __future__ import annotations

import pytest

from agents.director import (
    _awareness_support_in_beat,
    _unsupported_player_awareness,
)
from story.scene import NON_AWAKE_GATED, apply_awareness_diff, awareness_of

PLAYER = "Hinami"

# The live beat, verbatim.
LIVE_INPUT = (
    "You breath softly as you close your eyes wrapping your arms around her as "
    "well as two of your tails that curl around her seemingly of their own will."
)
LIVE_CONDITIONS = {
    "hinami_asleep": [{
        "condition_id": "hinami_asleep",
        "subject_id": "hinami",
        "kind": "awareness",
        "severity": "minor",
        "state": {
            "level": "asleep",
            "cause": "settling into rest and protective affection after arrival",
        },
    }],
}


def _awareness(level, subject=PLAYER, **extra):
    return {"c1": [{
        "condition_id": "c1", "subject_id": subject, "kind": "awareness",
        "state": {"level": level}, **extra,
    }]}


class TestTheLiveBeat:
    def test_the_players_sleep_is_dropped(self):
        unsupported = _unsupported_player_awareness(
            LIVE_CONDITIONS, PLAYER, LIVE_INPUT,
            "Hinami settles against Tamamo's side, breathing slow and even.",
            [],
        )
        assert unsupported == [("hinami_asleep", "asleep")]

    def test_the_subject_id_form_still_matches_the_persona_name(self):
        # The diff said "hinami"; the persona is "Hinami". Identity is compared
        # the way spatial.room_of compares names -- loosely -- or the guard
        # would never fire on real data.
        assert _unsupported_player_awareness(
            LIVE_CONDITIONS, "  HI-NAMI ", LIVE_INPUT, "", [],
        )

    def test_without_the_guard_the_player_would_be_gated(self):
        # What the fix prevents, stated in the terms perception reads.
        amap = apply_awareness_diff({}, {"conditions": LIVE_CONDITIONS})
        assert awareness_of(amap, PLAYER) in NON_AWAKE_GATED


class TestWhatStaysAllowed:
    def test_a_player_who_says_they_go_to_sleep(self):
        assert _unsupported_player_awareness(
            _awareness("asleep"), PLAYER,
            "You let yourself fall asleep against her.", "", [],
        ) == []

    def test_a_player_who_says_they_pass_out(self):
        assert _unsupported_player_awareness(
            _awareness("unconscious"), PLAYER,
            "You pass out from the pain.", "", [],
        ) == []

    @pytest.mark.parametrize("prose", [
        "The blow lands and Hinami is knocked out cold.",
        "Hinami slumps, unconscious, against the wall.",
        "The sedative takes hold; she is put under within seconds.",
        "The song pulls her down and she falls asleep mid-sentence.",
        "She drifts off before the sentence finishes.",
        "The tea was drugged.",
    ])
    def test_the_beat_doing_it_to_them(self, prose):
        # Support is read from anywhere in the beat, not subject-attributed:
        # this decides whether to KEEP the Director's judgement, so it errs
        # toward keeping.
        assert _unsupported_player_awareness(
            _awareness("unconscious"), PLAYER, "You step into the room.",
            prose, [],
        ) == []

    def test_support_can_come_from_spoken_dialogue(self):
        assert _unsupported_player_awareness(
            _awareness("asleep"), PLAYER, "You sit down.", "She sits.",
            [{"exact_quote": "Sleep now. I'll keep watch."}],
        ) == []

    def test_waking_is_never_touched(self):
        # An ending condition IS the player waking. Dropping it would strand
        # them under forever, which is worse than the bug being fixed.
        assert _unsupported_player_awareness(
            _awareness("asleep", active=0), PLAYER, "You open your eyes.",
            "", [],
        ) == []

    def test_dazed_is_not_gated_so_it_is_left_alone(self):
        assert _unsupported_player_awareness(
            _awareness("dazed"), PLAYER, "You shake your head.", "", [],
        ) == []

    def test_an_npc_is_the_directors_business(self):
        # A spurious non-awake NPC costs one beat of silence; the Director owns
        # objective causality and keeps it.
        assert _unsupported_player_awareness(
            _awareness("asleep", subject="Tamamo"), PLAYER,
            "You watch her settle.", "", [],
        ) == []

    def test_a_non_awareness_condition_is_untouched(self):
        conditions = {"c1": [{
            "condition_id": "c1", "subject_id": PLAYER, "kind": "wound",
            "state": {"level": "asleep"},
        }]}
        assert _unsupported_player_awareness(
            conditions, PLAYER, "You wince.", "", [],
        ) == []

    def test_no_persona_name_means_no_guard(self):
        assert _unsupported_player_awareness(
            _awareness("asleep"), "", LIVE_INPUT, "", [],
        ) == []


class TestRestingIsNotSleeping:
    @pytest.mark.parametrize("player_input", [
        "You close your eyes and lean against her.",
        "You lie down on the futon and pull the blanket up.",
        "You rest your head against her chest, quiet.",
        "You go quiet, warm and drowsy, and say nothing more.",
        "\"I'm tired, Kaa Sama...\" you murmur, settling in.",
        "You curl up and breathe slowly.",
    ])
    def test_ordinary_rest_supports_nothing(self, player_input):
        assert not _awareness_support_in_beat(player_input, "", [])
        assert _unsupported_player_awareness(
            _awareness("asleep"), PLAYER, player_input, "", [],
        )

    def test_a_heavy_sleeper_is_not_a_sleeping_person(self):
        # Live turn 7's input, which must not read as an assertion of sleep.
        assert not _awareness_support_in_beat(
            "\"It'll be Ok Kaa Sama... you were never a heavy sleeper anyway.\"",
            "", [],
        )

    def test_sleepy_and_sleepless_are_not_asleep(self):
        assert not _awareness_support_in_beat("You feel sleepy.", "", [])
        assert not _awareness_support_in_beat("A sleepless night.", "", [])


class TestTheOmissionScanStillCatchesMisses:
    """The floor in the other direction must keep working — and `passes?` never
    matched bare "pass", so second-person prose ("the blow makes you pass out")
    escaped it entirely."""

    @pytest.mark.parametrize("prose,expected", [
        ("The blow makes Hinami pass out.", ["Hinami"]),
        ("Hinami passes out.", ["Hinami"]),
        ("Hinami passed out on the floor.", ["Hinami"]),
        ("Hinami blacks out.", ["Hinami"]),
        ("Hinami black out.", ["Hinami"]),
        ("Hinami goes limp.", ["Hinami"]),
        ("Hinami went limp.", ["Hinami"]),
        ("Hinami knocked out by the fall.", ["Hinami"]),
        ("Hinami lose consciousness.", ["Hinami"]),
        ("Hinami settles in and rests.", []),
    ])
    def test_cues_are_attributed(self, prose, expected):
        from agents.director import _untracked_unconsciousness_subjects

        assert _untracked_unconsciousness_subjects(
            prose, [], {}, [PLAYER, "Tamamo"],
        ) == expected

    def test_a_recorded_condition_suppresses_the_flag(self):
        from agents.director import _untracked_unconsciousness_subjects

        assert _untracked_unconsciousness_subjects(
            "The blow makes Hinami pass out.", [], _awareness("unconscious"),
            [PLAYER],
        ) == []


class TestAtTheReconciliationSeam:
    """End-to-end through `_reconcile_resolution`'s Tier-0 floor, which is where
    the drop actually has to happen for the diff that reaches commit."""

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
            ("Hmmm", persona, "", time.time()),
        )
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) "
            "VALUES(?,?,?,?)",
            (cid, 8, player_input, time.time()),
        )

        ctx = PipelineContext(
            chat=ChatData(id=cid, name="Hmmm", persona_id=persona,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=cid, idx=8,
                          player_input=player_input, created=time.time(),
                          frame_id=None),
            cast=[], input=player_input,
        )
        out = {
            "resolved_event": "She settles against Tamamo, breathing slow.",
            "dialogue_log": [],
            "state_diff": {"conditions": conditions},
        }
        return ctx, out

    def test_the_spurious_condition_never_reaches_commit(self, temp_db):
        from agents.director import _reconcile_resolution

        ctx, out = self._ctx_and_out(temp_db, LIVE_INPUT, LIVE_CONDITIONS)
        _reconcile_resolution(ctx, out, {}, {}, {}, [], [PLAYER])

        assert out["state_diff"]["conditions"] == {}
        assert any("Dropped awareness" in w and PLAYER in w
                   for w in ctx.warnings)

    def test_a_supported_condition_survives_the_seam(self, temp_db):
        from agents.director import _reconcile_resolution

        ctx, out = self._ctx_and_out(
            temp_db, "You let yourself fall asleep against her.",
            _awareness("asleep"),
        )
        _reconcile_resolution(ctx, out, {}, {}, {}, [], [PLAYER])

        assert "c1" in out["state_diff"]["conditions"]


class TestSupportCues:
    @pytest.mark.parametrize("text", [
        "she is asleep", "he sleeps", "they were sleeping",
        "deep slumber", "she dozes", "he nodded off",
        "she drifts off", "he dropped off", "she goes to sleep",
        "he went to sleep", "knocked out", "out cold", "unconscious",
        "blacks out", "passed out", "she faints", "lost consciousness",
        "sedated", "put under", "drugged",
    ])
    def test_recognized(self, text):
        assert _awareness_support_in_beat("", text, [])

    @pytest.mark.parametrize("text", [
        "a heavy sleeper", "sleepy", "sleepless", "sleeve",
        "the sleeping car was full",  # 'sleeping' IS a cue; keep honest below
    ])
    def test_boundaries(self, text):
        # Only the last one is expected to match -- it is the deliberate cost of
        # reading support generously, and its consequence is merely keeping a
        # condition the Director already chose to write.
        expected = "sleeping" in text
        assert _awareness_support_in_beat("", text, []) is expected
