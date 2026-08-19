"""Waking: the exit side of the consciousness gate.

`test_awareness.py` covers the gate working. `test_awareness_player_floor.py`
covers the gate being imposed on nothing. This covers the gate never coming
off, which is what the author actually hit in play.

The corpus, measured read-only against the author's live engine.db (1483
director resolve/establish variants, 44 chats):

* 24 `awareness` conditions were ever emitted. NOT ONE carried `active: 0`.
  The Director has never once ended an awareness condition in real play.
* The only four that ever stopped gating were born with `expires_at_seconds`
  and were closed by mechanics.py's deterministic clock expiry. Every
  condition without that field is still active, up to 75 turns later.
* The reported incident, chat 40 "Hmmm ⎇0": turn 9 the player declared going
  to sleep (a legitimate onset), turn 10 declared "You eventually wake when
  morning comes", turn 11 "You open your eyes and look around". Both resolves
  returned `state_diff.conditions == {}`. Turn 10's own `changes_asserted`
  said "conditions / Hinami / transitions from asleep to awake"; the Tier-1
  manifest check caught the omission; the Tier-2 self-repair answered
  `already_encoded`, citing `entities.hinami.state.posture =
  "awake_stirring_in_nest"` — a field nothing reads for awareness. The
  repair's word was taken and the condition stayed on.

Two causes, both covered here: the resolve payload never told the Director
anyone was under or under which condition_id, and nothing deterministic
enforced the exit.
"""

from __future__ import annotations

import json
import time

import pytest

from agents.director import (
    _NATURAL_SLEEP_SECONDS,
    _already_ended,
    _awareness_exits,
    _awareness_view,
    _rouse_attempts,
    _sleep_elapsed,
)
from language_runtime import english_linguistic
from story.scene import NON_AWAKE_GATED, apply_awareness_diff, awareness_of

PLAYER = "Hinami"
SLEEPER = "Tamamo"


def _record(level="asleep", subject=PLAYER, cond_id="c1", started=0.0):
    return {
        "condition_id": cond_id,
        "subject": subject,
        "level": level,
        "cause": "",
        "rousable_by": "",
        "started_at_seconds": started,
        "payload": {"condition_id": cond_id, "subject_id": subject,
                    "kind": "awareness", "severity": "normal",
                    "started_at_seconds": started,
                    "state": {"level": level, "cause": "the warm nest"}},
    }


def _exits(records, player_input, *, interp=None, char_actions=None,
           resolved_event="", clock=None, sd_time=None, player=PLAYER):
    return _awareness_exits(
        1, records, player, player_input, interp or {}, char_actions or {},
        resolved_event, clock or {"elapsed_seconds": 0.0}, sd_time)


# --- the live beat ---------------------------------------------------------

class TestTheLiveBeat:
    """Chat 40 turns 10 and 11, verbatim, against a live `hinami_asleep`."""

    LIVE = [_record(cond_id="hinami_asleep", started=300.0)]

    @pytest.mark.parametrize("declaration", [
        "You eventually wake when morning comes.",
        "You open your eyes and look around.",
    ])
    def test_the_player_wakes(self, declaration):
        endings, warnings = _exits(self.LIVE, declaration)
        assert "hinami_asleep" in endings
        assert endings["hinami_asleep"][0]["active"] == 0
        assert warnings

    def test_the_ending_reuses_the_condition_id(self):
        # commit UPDATEs world_conditions by condition_id; a fresh id INSERTs a
        # second row and closes nothing.
        ending = _exits(self.LIVE, "You sit up.")[0]["hinami_asleep"][0]
        assert ending["condition_id"] == "hinami_asleep"
        assert ending["kind"] == "awareness"
        assert ending["subject_id"] == PLAYER

    def test_the_ending_wakes_them_in_the_same_beat(self):
        # apply_awareness_diff runs pre-commit, so perception_outcome sees the
        # newly woken mind on the beat it wakes.
        under = apply_awareness_diff(
            {}, {"conditions": {"hinami_asleep": [self.LIVE[0]["payload"]]}})
        assert awareness_of(under, PLAYER) in NON_AWAKE_GATED
        endings = _exits(self.LIVE, "You open your eyes.")[0]
        assert awareness_of(
            apply_awareness_diff(under, {"conditions": endings}), PLAYER) == "awake"

    def test_the_original_onset_beat_is_still_respected(self):
        # Turn 9's input. A player who says they are going to sleep stays under.
        assert _exits(self.LIVE, "\"Mmmm thank you kaa sama.\" You slowly let "
                                 "yourself fall asleep.")[0] == {}


# --- rule 1: the player's own declaration ----------------------------------

class TestThePlayerCanAlwaysActTowardWaking:
    @pytest.mark.parametrize("declaration", [
        "You wake.",
        "You try to sit up.",
        "You stir and reach for her hand.",
        "\"Kaa Sama?\" you murmur.",
        "You get up and walk to the door.",
        "It is morning.",
    ])
    def test_any_declaration_ends_the_gate(self, declaration):
        assert _exits([_record()], declaration)[0]

    @pytest.mark.parametrize("level", sorted(NON_AWAKE_GATED))
    def test_at_every_gated_level(self, level):
        # Deliberately not level-scoped. The Director keeps every other lever --
        # it may narrate the attempt failing, or impose the condition again with
        # a stated cause -- but it may not hold a gate the player has no way out
        # of, because the player owns the declaration of their own conduct.
        assert _exits([_record(level=level)], "You try to move.")[0]

    @pytest.mark.parametrize("declaration", [
        "You slowly let yourself fall asleep.",
        "You sleep through the night.",
        "You dream of the sea.",
        "You stay under.",
        "You keep sleeping, undisturbed.",
        "She shifts against you without waking you.",
    ])
    def test_a_request_to_stay_under_is_honoured(self, declaration):
        assert _exits([_record()], declaration)[0] == {}

    def test_an_empty_turn_does_not_wake_them(self):
        assert _exits([_record()], "")[0] == {}
        assert _exits([_record()], "   ")[0] == {}

    def test_dazed_is_not_gated_so_nothing_is_ended(self):
        assert _exits([_record(level="dazed")], "You shake your head.")[0] == {}

    def test_an_npc_does_not_wake_on_the_players_declaration(self):
        # A sleeping mind never decides to wake, and the player is not the one
        # deciding for it either. Only the rouse and clock rules touch an NPC.
        assert _exits([_record(subject=SLEEPER)], "You watch her sleep.")[0] == {}

    def test_every_row_on_the_player_is_ended_not_just_one(self):
        # Live shape: chat 23 carries two `unconscious` rows and one `dazed` on
        # the same person. awareness_map collapses them to one; ending only that
        # one leaves the subject gated by the survivors.
        records = [_record(level="unconscious", cond_id="a"),
                   _record(level="unconscious", cond_id="b"),
                   _record(level="dazed", cond_id="c")]
        endings = _exits(records, "You push yourself upright.")[0]
        assert set(endings) == {"a", "b"}   # 'dazed' does not gate

    def test_no_persona_name_means_no_player_rule(self):
        assert _exits([_record()], "You wake.", player="")[0] == {}


# --- rule 2: somebody deliberately rousing them ----------------------------

class TestBeingWokenBySomebodyElse:
    @pytest.mark.parametrize("attempt", [
        "shakes Tamamo by the shoulder",
        "wakes Tamamo",
        "nudges Tamamo awake",
        "shoves Tamamo hard",
        "splashes water over Tamamo",
        "hauls Tamamo upright",
        "slaps Tamamo lightly on the cheek",
    ])
    def test_a_declared_rouse_wakes_a_sleeper(self, attempt):
        endings, warnings = _exits(
            [_record(subject=SLEEPER)], "",
            char_actions={"Kaede": [{"attempt": attempt}]})
        assert "c1" in endings
        assert any("Ended awareness 'asleep'" in w for w in warnings)

    def test_a_kana_named_sleeper_can_be_roused(self):
        """The shared attribution idiom matched names with \\b, and a kana
        name has no word boundary against the particle that follows it --
        so in a Japanese story the rouse cue fired and could never be
        pinned to its sleeper, and the deterministic rouse exit was dead
        for every kana-named mind. The release scan hit the identical
        class; both now go through `name_boundary_pattern`."""
        from language_runtime import language_scope

        with language_scope("ja"):
            endings, _ = _exits(
                [_record(subject="タマモ")], "",
                char_actions={"カエデ": [{"attempt": "タマモを揺さぶる"}]})
        assert "c1" in endings

    def test_a_rouse_in_the_players_own_sequence_counts(self):
        endings, _ = _exits(
            [_record(subject=SLEEPER)], "You shake her awake.",
            interp={"sequence": [{"type": "action",
                                  "attempt": "shakes Tamamo awake"}]})
        assert "c1" in endings

    def test_a_rouse_only_narrated_still_counts(self):
        # A Director that wrote the shake into prose but encoded nothing is the
        # exact failure being floored.
        endings, _ = _exits(
            [_record(subject=SLEEPER)], "",
            resolved_event="Kaede shakes Tamamo by the shoulder, insistent.")
        assert "c1" in endings

    @pytest.mark.parametrize("level", ["sedated", "unconscious"])
    def test_the_sedated_and_unconscious_do_not_sit_up(self, level):
        endings, warnings = _exits(
            [_record(level=level, subject=SLEEPER)], "",
            char_actions={"Kaede": [{"attempt": "shakes Tamamo by the shoulder"}]})
        assert endings == {}
        assert any("do not wake from being shaken" in w for w in warnings)
        assert any("as a fact" in w for w in warnings)

    def test_an_unrelated_shake_does_not_wake_anyone(self):
        assert _exits(
            [_record(subject=SLEEPER)], "",
            resolved_event="Kaede shakes the rain off her coat. "
                           "Tamamo has not moved since dusk.")[0] == {}

    def test_attribution_picks_the_body_actually_touched(self):
        # The nearest same-clause name, so a co-mentioned bystander is not
        # woken by someone else's shoulder.
        roused = _rouse_attempts(
            {}, {}, "Kaede shakes Tamamo awake while Hinami watches.",
            [SLEEPER, PLAYER])
        assert roused == {SLEEPER}

    def test_a_rouse_wakes_its_object_not_its_actor(self):
        # A rouse cue is TRANSITIVE, unlike the unconsciousness cue: the body
        # being woken FOLLOWS the verb and the nearest preceding name is the
        # waker. With two sleepers named in one clause, plain nearest-name would
        # wake the wrong one.
        assert _rouse_attempts(
            {}, {}, "Tamamo shakes Hinami awake.", [SLEEPER, PLAYER]) == {PLAYER}

    def test_the_passive_form_still_attributes(self):
        assert _rouse_attempts(
            {}, {}, "Tamamo is shaken awake by the alarm.",
            [SLEEPER, PLAYER]) == {SLEEPER}


# --- rule 3: the clock -----------------------------------------------------

class TestTheNightEnding:
    def test_a_full_sleep_ends_by_itself(self):
        endings, warnings = _exits(
            [_record(subject=SLEEPER, started=300.0)], "",
            sd_time={"start_seconds": 300, "duration_seconds": 28800,
                     "end_seconds": 29100})
        assert "c1" in endings
        assert any("full sleep" in w for w in warnings)

    def test_a_nap_does_not(self):
        assert _exits(
            [_record(subject=SLEEPER, started=300.0)], "",
            sd_time={"start_seconds": 300, "duration_seconds": 600,
                     "end_seconds": 900})[0] == {}

    @pytest.mark.parametrize("level", ["sedated", "unconscious"])
    def test_only_ordinary_sleep_ends_on_the_clock(self, level):
        # A sedative wearing off is dosage and unconsciousness resolving is
        # medicine. Both are the Director's, which the payload now equips.
        assert _exits(
            [_record(level=level, subject=SLEEPER, started=0.0)], "",
            sd_time={"end_seconds": _NATURAL_SLEEP_SECONDS * 3})[0] == {}

    def test_the_clock_falls_back_to_the_simulation_clock(self):
        endings, _ = _exits(
            [_record(subject=SLEEPER, started=0.0)], "",
            clock={"elapsed_seconds": _NATURAL_SLEEP_SECONDS + 1})
        assert "c1" in endings

    def test_a_nonsense_start_time_is_treated_as_unknown(self):
        # started_at_seconds is model-authored. A span running backwards must
        # not be read as a very long sleep.
        assert _sleep_elapsed(_record(started=9_000_000.0), {}, {"end_seconds": 10}) is None


# --- what the Director is told --------------------------------------------

class TestTheDirectorIsToldThereIsSomeoneUnder:
    def test_the_view_names_the_id_and_the_pressure(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Hmmm", "", time.time()))
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
            "started_at,expires_at,next_tick,payload,active) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("hinami_asleep", chat_id, PLAYER, "awareness", 300.0, None, None,
             json.dumps({"condition_id": "hinami_asleep", "subject_id": PLAYER,
                         "kind": "awareness", "started_at_seconds": 300,
                         "state": {"level": "asleep", "cause": "the warm nest"}}),
             1))

        view = _awareness_view(
            chat_id, {"elapsed_seconds": 300.0}, {},
            {"Kaede": [{"attempt": "shakes Hinami by the shoulder"}]})

        assert len(view) == 1
        entry = view[0]
        assert entry["condition_id"] == "hinami_asleep"
        assert entry["gates_this_mind"] is True
        assert entry["someone_is_trying_to_wake_them"] is True
        assert entry["natural_wake_due"] is False

    def test_no_conditions_means_an_empty_block(self, temp_db):
        chat_id = temp_db.qi(
            "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
            ("Quiet", "", time.time()))
        assert _awareness_view(chat_id, {}, {}, {}) == []


# --- the seam --------------------------------------------------------------

class TestAtTheReconciliationSeam:
    """Through `_reconcile_resolution`'s Tier-0 floor, which is where the
    ending has to land for the diff that reaches commit."""

    def _ctx(self, temp_db, player_input):
        from core.pipeline_context import ChatData, PipelineContext, TurnData

        persona = temp_db.qi(
            "INSERT INTO personas(name,sheet) VALUES(?,?)",
            (PLAYER, json.dumps({"identity": {"name": PLAYER}})))
        cid = temp_db.qi(
            "INSERT INTO chats(name,persona_id,scenario,created) VALUES(?,?,?,?)",
            ("Hmmm", persona, "", time.time()))
        turn_id = temp_db.qi(
            "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
            (cid, 10, player_input, time.time()))
        temp_db.qi(
            "INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,"
            "started_at,expires_at,next_tick,payload,active) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            ("hinami_asleep", cid, PLAYER, "awareness", 300.0, None, None,
             json.dumps({"condition_id": "hinami_asleep", "subject_id": PLAYER,
                         "kind": "awareness", "started_at_seconds": 300,
                         "state": {"level": "asleep", "cause": "the warm nest"}}),
             1))
        return PipelineContext(
            chat=ChatData(id=cid, name="Hmmm", persona_id=persona,
                          lorebook_id=None, scenario="", created=time.time()),
            turn=TurnData(id=turn_id, chat_id=cid, idx=10,
                          player_input=player_input, created=time.time(),
                          frame_id=None),
            cast=[], input=player_input,
        )

    def _out(self, conditions=None):
        return {
            "resolved_event": "Morning light filters into the roost. Hinami "
                              "stirs in the nest, eyes opening.",
            "dialogue_log": [],
            "state_diff": {"conditions": dict(conditions or {})},
        }

    def test_the_wake_reaches_the_committed_diff(self, temp_db):
        from agents.director import _reconcile_resolution

        ctx = self._ctx(temp_db, "You eventually wake when morning comes.")
        out = self._out()
        _reconcile_resolution(ctx, out, {}, {}, {}, [], [PLAYER])

        ending = out["state_diff"]["conditions"]["hinami_asleep"][0]
        assert ending["active"] == 0
        assert any("Ended awareness" in w for w in ctx.warnings)

    def test_a_re_assertion_of_the_sleep_does_not_survive(self, temp_db):
        # The failure that keeps a gate on: the Director writes the same id
        # again, still active, and the player never gets out.
        from agents.director import _reconcile_resolution

        ctx = self._ctx(temp_db, "You sit up and look around.")
        out = self._out({"hinami_asleep": [{
            "condition_id": "hinami_asleep", "subject_id": PLAYER,
            "kind": "awareness", "state": {"level": "asleep"}}]})
        _reconcile_resolution(ctx, out, {}, {}, {}, [], [PLAYER])

        assert _already_ended(out["state_diff"]["conditions"]["hinami_asleep"])

    def test_the_directors_own_ending_is_left_alone(self, temp_db):
        from agents.director import _reconcile_resolution

        ctx = self._ctx(temp_db, "You wake.")
        authored = {"hinami_asleep": [{
            "condition_id": "hinami_asleep", "subject_id": PLAYER,
            "kind": "awareness", "active": 0,
            "state": {"level": "asleep", "cause": "morning"}}]}
        out = self._out(authored)
        _reconcile_resolution(ctx, out, {}, {}, {}, [], [PLAYER])

        assert out["state_diff"]["conditions"]["hinami_asleep"] == authored["hinami_asleep"]

    def test_a_refused_rouse_is_visible_on_the_step(self, temp_db):
        # ctx.warnings is accumulated pipeline-wide and never shown, and a
        # refused rouse writes no diff at all -- so without this the whole
        # event is invisible.
        from agents.director import _reconcile_resolution

        ctx = self._ctx(temp_db, "")
        temp_db.q("UPDATE world_conditions SET payload=? WHERE chat_id=?",
                  (json.dumps({"condition_id": "hinami_asleep",
                               "subject_id": PLAYER, "kind": "awareness",
                               "state": {"level": "sedated"}}), ctx.chat.id))
        out = self._out()
        out["resolved_event"] = "Kaede shakes Hinami by the shoulder."
        _reconcile_resolution(ctx, out, {}, {}, {}, [], [PLAYER])

        assert out["state_diff"]["conditions"] == {}
        assert any("do not wake" in w for w in out["awareness_warnings"])

    def test_a_chat_with_nobody_under_is_untouched(self, temp_db):
        from agents.director import _reconcile_resolution

        ctx = self._ctx(temp_db, "You walk to the door.")
        temp_db.q("DELETE FROM world_conditions")
        out = self._out()
        _reconcile_resolution(ctx, out, {}, {}, {}, [], [PLAYER])

        assert out["state_diff"]["conditions"] == {}


# --- commit: an ending must not open a condition ---------------------------

def test_an_ending_for_an_unknown_id_inserts_inactive(temp_db):
    """commit's INSERT hardcoded active=1, so an ending naming an id no row
    carries yet was persisted as ACTIVE -- the act of waking someone put them
    under."""
    import time as _time

    from persist.commit import commit_world_entities
    from core.pipeline_context import ChatData, PipelineContext, TurnData

    cid = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Wake", "", _time.time()))
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (cid, 1, "", _time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=cid, name="Wake", persona_id=None, lorebook_id=None,
                      scenario="", created=_time.time()),
        turn=TurnData(id=turn_id, chat_id=cid, idx=1, player_input="",
                      created=_time.time(), frame_id=None),
        cast=[], input="")
    ctx.director_resolve = {"state_diff": {"conditions": {"nope": [{
        "condition_id": "nope", "subject_id": PLAYER, "kind": "awareness",
        "active": 0, "state": {"level": "asleep"}}]}}}

    commit_world_entities(ctx, "n1")

    row = temp_db.q("SELECT active FROM world_conditions WHERE chat_id=?",
                    (cid,), one=True)
    assert row["active"] == 0


# --- the stay-under vocabulary --------------------------------------------

class TestStayUnderCues:
    """The ENGLISH cue, fetched as such.

    It used to be imported as `director._STAY_UNDER_CUE`, a module constant
    resolved at import under whatever language was current then -- so a test
    written to guard a story-language vocabulary was pinned to one language
    without saying which. Every runtime read goes through `_ling(...)` under
    the story's own language context; the constants were alive only as these
    fixtures, and are gone. The Japanese cues have their own guard in
    `tests/test_language_packs.py`, with Japanese fixtures, because English
    sentences cannot test a Japanese regex.
    """

    CUE = english_linguistic("agents.director", "_STAY_UNDER_CUE")

    @pytest.mark.parametrize("text", [
        "falls asleep", "she sleeps", "still sleeping", "dreaming of home",
        "stays under", "keeps sleeping", "remains unconscious", "snoring",
        "does not wake", "without waking", "drifts off",
    ])
    def test_recognized(self, text):
        assert self.CUE.search(text)

    @pytest.mark.parametrize("text", [
        "you wake", "you open your eyes", "you sit up", "morning comes",
        "you reach for her hand", "sleepless", "a heavy sleeper",
    ])
    def test_not_a_request_to_stay_under(self, text):
        assert not self.CUE.search(text)
