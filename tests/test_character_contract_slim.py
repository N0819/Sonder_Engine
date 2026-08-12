"""The slimmed character output contract loses no committed state.

The 2026-08-11 character-agent audit (design_notes/09-character-agent-audit.md,
docs/UNBUILT.md §6.9) measured, on 401 recent-era stored calls:

- the template's ten stress/hedonic fields were emitted on 71% of calls at a
  mean 78 tokens, while commit reads exactly two of them -- `hedonic.released`
  and `stress.coping_mode` -- and recomputes everything else wholesale
  (psychology_runtime.resolve_stress / resolve_hedonic);
- `active_state.goal` was overwritten with `wants[enacted].want` on 99.0% of
  calls, and the emitted string matched that want only 16.2% of the time.

So the template stopped asking for the recomputed fields.  These tests pin
the two claims that made that safe:

1. the discarded numbers CANNOT move committed state -- a legacy result
   carrying wild stress/hedonic numbers and a slim result carrying only the
   two consumed fields commit byte-identical character state;
2. the two consumed fields still flow, and the goal slot is derived from the
   enacted want -- falling back through a legacy emitted goal to the PREVIOUS
   goal, never to empty, on the ~1% of beats whose wants are malformed
   (blanking the slot there silently killed a standing aim: routing, tenure
   and the unbidden ledger all read it).
"""

from __future__ import annotations

import copy
import json
import time

import commit
from character_schema import default_character_data
from commit import prepare_memory_commit
from pipeline_context import ChatData, PipelineContext, TurnData


def _story(temp_db, cstate=None, *, name="Vorne"):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", 0.0))
    sheet = default_character_data(name)
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time(),
         sheet["identity"]["uid"]))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", json.dumps(cstate or {})))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    return chat_id, char_id, cast


def _capture_batch(monkeypatch):
    captured = {}

    def fake_batch(memories):
        captured["memories"] = memories
        return {"prepared": [], "embedded": None}  # skip real embedding

    monkeypatch.setattr(commit, "prepare_memories_batch", fake_batch)
    return captured


def _commit_state(temp_db, own_result, *, cstate=None):
    chat_id, char_id, cast = _story(temp_db, cstate)
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=7, chat_id=chat_id, idx=3, player_input="hold",
                      created=time.time()),
        cast=cast, input="hold",
        director_resolve={"resolved_event": "The gate holds.",
                          "dialogue_log": []})
    ctx.character_results = {char_id: copy.deepcopy(own_result)}
    out = prepare_memory_commit(ctx)
    return next(s for _, ccid, s in out["state_updates"] if ccid == char_id)


_SLIM_RESULT = {
    "salience": 0.6,
    "sequence": [{"type": "speech", "text": "Hold the line."}],
    "appraisal": {
        "goal_impacts": [{"serves": "situational", "impact": 0.4,
                          "certainty": 0.8, "agency": "self",
                          "why": "the gate held",
                          "evidence": [{"event_id": "current:1:0",
                                        "fact": "held"}]}],
        "novelty": 0.3, "controllability": 0.6, "coping_potential": 0.7,
        "norm_compatibility": 0.2, "self_congruence": 0.4,
        "intrinsic_pleasantness": 0.1,
    },
    "active_state": {
        "mood": "steady",
        "wants": [{"want": "keep the gate held", "urgency": 0.7,
                   "serves": "situational"}],
        "enacted_want": 0,
        "stress": {"coping_mode": "problem_solving"},
        "hedonic": {"released": False},
    },
}


def test_stress_hedonic_numbers_cannot_move_committed_state(
        temp_db, monkeypatch):
    """A legacy full-shape emission with wild numbers and the slim two-field
    emission commit BYTE-IDENTICAL state: the numbers were dice-class
    transcription, discarded by construction."""
    _capture_batch(monkeypatch)
    legacy = copy.deepcopy(_SLIM_RESULT)
    legacy["active_state"]["stress"] = {
        "activation": 0.93, "load": 0.81,
        "coping_mode": "problem_solving", "overloaded": True}
    legacy["active_state"]["hedonic"] = {
        "pain": 0.66, "pleasure": 0.44, "source": "an invented number",
        "released": False}
    state_legacy = _commit_state(temp_db, legacy)
    state_slim = _commit_state(temp_db, _SLIM_RESULT)
    assert state_legacy == state_slim

    committed = json.loads(state_slim)["active_state"]
    # The one stress field that is consumed still flows...
    assert committed["stress"]["coping_mode"] == "problem_solving"
    # ...and the wild numbers provably did not: the runtime recomputed them.
    assert committed["stress"]["activation"] != 0.93
    assert committed["hedonic"]["pain"] != 0.66


def test_released_is_still_the_characters_own_discharge(temp_db, monkeypatch):
    """`hedonic.released` stays consumed: with a standing charge, declaring
    the release discharges it and staying silent keeps it -- the field is
    signal, not wrapper, which is why the slim template kept it."""
    _capture_batch(monkeypatch)
    prior = {"active_state": {"mood": "wound tight",
                              "hedonic": {"pain": 0.0, "pleasure": 0.4,
                                          "charge": 0.6, "source": "held"}}}
    held = copy.deepcopy(_SLIM_RESULT)
    state_held = json.loads(_commit_state(temp_db, held, cstate=prior))
    released = copy.deepcopy(_SLIM_RESULT)
    released["active_state"]["hedonic"] = {"released": True}
    state_released = json.loads(
        _commit_state(temp_db, released, cstate=prior))
    charge_held = state_held["active_state"]["hedonic"]["charge"]
    charge_released = state_released["active_state"]["hedonic"]["charge"]
    assert charge_released < charge_held


def test_goal_slot_is_the_enacted_wants_text(temp_db, monkeypatch):
    """No emitted goal at all: the slot is the enacted want's own words."""
    _capture_batch(monkeypatch)
    state = json.loads(_commit_state(temp_db, _SLIM_RESULT))
    assert state["active_state"]["goal"] == "keep the gate held"


def test_malformed_wants_keep_the_previous_goal_not_empty(
        temp_db, monkeypatch):
    """The 1% branch: wants unreadable and no emitted goal must KEEP the
    standing aim. Blanking it was a latent defect -- goal routing
    (_destination_from_goals), tenure (goal_slot_currency) and the unbidden
    ledger all read this slot, and "" is a decision the character never
    made."""
    _capture_batch(monkeypatch)
    prior = {"active_state": {"mood": "set", "goal": "find the shrine"}}
    broken = copy.deepcopy(_SLIM_RESULT)
    broken["active_state"]["wants"] = "not a list"
    broken["active_state"].pop("enacted_want", None)
    state = json.loads(_commit_state(temp_db, broken, cstate=prior))
    assert state["active_state"]["goal"] == "find the shrine"


def test_legacy_emitted_goal_still_wins_over_the_previous_goal(
        temp_db, monkeypatch):
    """A provider still emitting the legacy field keeps its say on the
    malformed-wants branch: this beat's own declaration outranks last
    beat's."""
    _capture_batch(monkeypatch)
    prior = {"active_state": {"mood": "set", "goal": "find the shrine"}}
    legacy = copy.deepcopy(_SLIM_RESULT)
    legacy["active_state"]["wants"] = []
    legacy["active_state"]["goal"] = "bar the east door"
    state = json.loads(_commit_state(temp_db, legacy, cstate=prior))
    assert state["active_state"]["goal"] == "bar the east door"
