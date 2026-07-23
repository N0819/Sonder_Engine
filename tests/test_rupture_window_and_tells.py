"""W6/W7 interior-depth regressions: rupture windows that re-open while
strain stays at rupture level, the crisis flag that surfaces extreme strain
as visible breaking, and the recent-tell ledger that stops a character from
reaching for the same physical cue every beat.

Commit side (prepare_memory_commit): an expired rupture window must EXTEND
-- not quietly close with a strain discount -- while drive_strain stays >=
affect.RUPTURE_STRAIN_MIN, and each beat's manifest cues must accrue onto
cstate's recent_tells ledger (capped). Agent side (character_step): the
payload carries self.crisis at CRISIS_STRAIN_MIN, self.recent_tells from
the ledger, and the in-window rupture prompt with its worked example.
"""

import json
import time

import affect
from character_schema import default_character_data
from commit import RECENT_TELLS_CAP, prepare_memory_commit
from pipeline_context import ChatData, PipelineContext, TurnData


def _story(temp_db, cstate, *, name="Advocate Vorne"):
    """One chat + one active character whose chat_chars.state is `cstate`."""
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    sheet = default_character_data(name)
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time(),
         sheet["identity"]["uid"]),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", json.dumps(cstate)),
    )
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    return chat_id, char_id, cast


def _commit_ctx(chat_id, char_id, cast, turn_idx, own_result):
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_idx + 1, chat_id=chat_id, idx=turn_idx,
                      player_input="...", created=time.time()),
        cast=cast, input="...",
        director_resolve={"resolved_event": "The hearing continues.",
                          "dialogue_log": []},
    )
    ctx.character_results = {char_id: own_result}
    return ctx


def _committed_state(out, char_id):
    for _, ccid, st_json in out["state_updates"]:
        if ccid == char_id:
            return json.loads(st_json)
    raise AssertionError("no state update for character")


# ---- W6: the rupture window re-opens while strain stays at rupture level ----

def test_expired_rupture_window_extends_while_strain_high(temp_db):
    chat_id, char_id, cast = _story(temp_db, {
        "interior": {
            "drive_strain": 0.9,
            "strain_turn": 9,
            "drive_rupture": {"turn": 5, "why": "the court executed the clerk",
                              "direction": "contradiction", "window_expires": 7},
        },
    })
    # turn 10: the window (expires 7) has lapsed, but strain is still far
    # above the rupture floor -- the crisis is unresolved.
    ctx = _commit_ctx(chat_id, char_id, cast, 10,
                      {"active_state": {"mood": "grim", "goal": ""}})
    st = _committed_state(prepare_memory_commit(ctx), char_id)

    interior = st["interior"]
    rupture = interior.get("drive_rupture")
    assert rupture is not None, "window must re-open, not quietly close"
    assert rupture["window_expires"] == 13          # extended past this turn
    assert rupture["why"] == "the court executed the clerk"
    # strain decayed slightly but was NOT halved by the weathered discount
    assert interior["drive_strain"] >= affect.RUPTURE_STRAIN_MIN
    assert any("window extended" in w for w in ctx.warnings)


def test_rupture_window_force_closes_after_max_open_turns(temp_db):
    # W1: a window that keeps re-extending while the model never shifts used to
    # sit open forever (23-turn Vorne limbo). Once it has been open
    # RUPTURE_MAX_OPEN turns it must force-close even though strain is still high
    # -- deferral under maximal pressure resolves AS reaffirmation.
    opened = 2
    chat_id, char_id, cast = _story(temp_db, {
        "interior": {
            "drive_strain": 0.95,
            "strain_turn": opened + 7,
            "drive_rupture": {"turn": opened, "opened_turn": opened,
                              "why": "the court executed the clerk",
                              "direction": "contradiction", "window_expires": 9},
        },
    })
    # turn 10: window (expires 9) lapsed AND it has been open 8 turns (>= MAX).
    ctx = _commit_ctx(chat_id, char_id, cast, 10,
                      {"active_state": {"mood": "grim", "goal": ""}})
    st = _committed_state(prepare_memory_commit(ctx), char_id)

    interior = st["interior"]
    assert "drive_rupture" not in interior, "limbo must not persist past the cap"
    # strain paid down below the rupture floor so it cannot immediately re-open
    assert interior["drive_strain"] < affect.RUPTURE_STRAIN_MIN
    assert any("force-closed" in w for w in ctx.warnings)


def test_expired_rupture_window_closes_once_strain_drops(temp_db):
    chat_id, char_id, cast = _story(temp_db, {
        "interior": {
            "drive_strain": 0.3,
            "strain_turn": 9,
            "drive_rupture": {"turn": 5, "why": "the court executed the clerk",
                              "direction": "contradiction", "window_expires": 7},
        },
    })
    ctx = _commit_ctx(chat_id, char_id, cast, 10,
                      {"active_state": {"mood": "calm", "goal": ""}})
    st = _committed_state(prepare_memory_commit(ctx), char_id)

    interior = st["interior"]
    assert "drive_rupture" not in interior          # weathered: truly closed
    assert interior["drive_strain"] < 0.3           # and the strain discounted


# ---- W7: recent-tell ledger accrual on cstate ----

def test_manifest_cues_accrue_to_recent_tells_and_cap(temp_db):
    chat_id, char_id, cast = _story(temp_db, {
        "recent_tells": ["a", "b", "c", "d", "e"],
    })
    ctx = _commit_ctx(chat_id, char_id, cast, 4, {
        # no active_state: the ledger must accrue independently of the
        # interior-depth block
        "manifest": {"surface_demeanor": "even",
                     "tells": [{"cue": "jaw tightens", "channel": "face",
                                "subtlety": 0.5, "betrays": "undercurrent"},
                               {"cue": "glance at the door", "channel": "eyes",
                                "subtlety": 0.4, "betrays": "suppressed_want"},
                               {"cue": "", "channel": "voice"},
                               "junk"]},
    })
    st = _committed_state(prepare_memory_commit(ctx), char_id)

    assert st["recent_tells"] == [
        "b", "c", "d", "e", "jaw tightens", "glance at the door"]
    assert len(st["recent_tells"]) == RECENT_TELLS_CAP


def test_no_tells_leaves_ledger_untouched(temp_db):
    chat_id, char_id, cast = _story(temp_db, {"recent_tells": ["a"]})
    ctx = _commit_ctx(chat_id, char_id, cast, 4,
                      {"active_state": {"mood": "calm", "goal": ""}})
    st = _committed_state(prepare_memory_commit(ctx), char_id)
    assert st["recent_tells"] == ["a"]


# ---- Character payload: crisis flag, recent tells, rupture prompt ----

def _run_character_step(temp_db, monkeypatch, cstate, turn_idx=1):
    import agents.character as character_module

    chat_id, char_id, cast = _story(temp_db, cstate)
    temp_db.wset(chat_id, "scene", {
        "location": "Hearing Chamber", "time": "day",
        "rooms": {"chamber": {"name": "Chamber", "adjacent": []}},
        "positions": {"Advocate Vorne": "chamber"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "well?", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="well?", created=time.time()),
        cast=cast, input="well?",
    )
    ctx.director_interpret = {"flow": {"reactors": [char_id], "tom_triggers": []}}

    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["system"] = system
        captured["payload"] = payload
        return {"sequence": []}

    monkeypatch.setattr(character_module, "_agent_json", fake_agent_json)
    character_module.character_step(ctx, char_id, nonce=0)
    return captured


def test_crisis_flag_fed_at_extreme_strain(temp_db, monkeypatch):
    captured = _run_character_step(
        temp_db, monkeypatch, {"interior": {"drive_strain": 0.85}})
    assert captured["payload"]["self"]["crisis"] is True
    assert "CRISIS" in captured["system"]
    assert "subtlety <= 0.4" in captured["system"]


def test_no_crisis_flag_below_threshold(temp_db, monkeypatch):
    captured = _run_character_step(
        temp_db, monkeypatch, {"interior": {"drive_strain": 0.5}})
    assert "crisis" not in captured["payload"]["self"]
    assert "CRISIS" not in captured["system"]


def test_recent_tells_fed_with_variety_rule(temp_db, monkeypatch):
    captured = _run_character_step(
        temp_db, monkeypatch,
        {"recent_tells": ["jaw tightens", "glance at the door"]})
    assert captured["payload"]["self"]["recent_tells"] == [
        "jaw tightens", "glance at the door"]
    assert "TELL VARIETY" in captured["system"]
    # empty ledger: no flag in payload, no prompt bloat
    captured = _run_character_step(temp_db, monkeypatch, {})
    assert "recent_tells" not in captured["payload"]["self"]
    assert "TELL VARIETY" not in captured["system"]


def test_open_rupture_window_prompts_with_worked_example(temp_db, monkeypatch):
    captured = _run_character_step(temp_db, monkeypatch, {
        "interior": {"drive_rupture": {
            "turn": 1, "why": "the court executed the clerk",
            "direction": "contradiction", "window_expires": 3}},
    }, turn_idx=1)
    assert captured["payload"]["self"]["rupture"]["why"] == (
        "the court executed the clerk")
    system = captured["system"]
    assert "DRIVE RUPTURE" in system
    assert "ALREADY changed you" in system
    assert "WORKED EXAMPLE" in system
    assert "drive_shift" in system
    # freshly opened (turns_open 0): optional, not yet forced
    assert captured["payload"]["self"]["rupture"]["forced"] is False
    assert "FORCED RESOLUTION" not in system


def test_rupture_prompt_escalates_to_forced_after_several_beats(temp_db, monkeypatch):
    # W1 agent side: once the window has been open RUPTURE_FORCE_AFTER turns the
    # optional "you MAY shift" becomes a FORCED resolution -- passive calm is no
    # longer offered, so the model can no longer quietly decline every beat.
    captured = _run_character_step(temp_db, monkeypatch, {
        "interior": {"drive_rupture": {
            "turn": 1, "opened_turn": 1, "why": "the court executed the clerk",
            "direction": "contradiction", "window_expires": 8}},
    }, turn_idx=5)  # opened at 1, now turn 5 -> open 4 beats (>= RUPTURE_FORCE_AFTER)
    assert captured["payload"]["self"]["rupture"]["forced"] is True
    system = captured["system"]
    assert "FORCED RESOLUTION" in system
    assert "NOT an available option" in system
