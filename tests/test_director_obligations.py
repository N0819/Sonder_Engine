"""Regression tests for the Director obligation ledger (W1), the
player-asserted-fact adjudication backstop (W2), and the authority-appraisal
payload hint (W5) -- the Enterprise-D audit's "the engine defers plot
forever / tolerates unbacked claims / obeys anyone's orders" failures.

W1: director_resolve registers demands/promises/announced actions as
`obligations` ops; commit.py's commit_obligations applies them
deterministically to the world-KV pending_obligations ledger, and
pending_obligation_view surfaces each entry's age with a
must_discharge_this_beat flag back into the resolve payload. An entry still
open past OBLIGATION_OVERDUE_AGE after a beat's ops is a re-deferral and
warns.

W2: a player-authored world assertion (an actor-less `event` authority
claim) left without a fact_adjudications verdict is flagged.

W5: the resolve payload carries a social_standing hint per present person.
"""

import json
import time

import commit
from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


def _simple_scene():
    return {
        "location": "Bridge",
        "time": "day",
        "rooms": {"bridge": {"name": "Bridge", "adjacent": []}},
        "positions": {"The Stranger": "bridge", "Mara": "bridge"},
        "entities": {},
        "attire": {},
        "overlays": {},
    }


def _make_ctx(temp_db, *, turn_idx=1, authority_claims=None,
              public_history=""):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )

    sheet = default_character_data("Mara")
    sheet["knowledge"]["public_history"] = public_history
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        ("Mara", json.dumps(sheet), "{}", time.time(), "char_mara"),
    )
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", "{}"),
    )

    temp_db.wset(chat_id, "scene", _simple_scene())

    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )

    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, turn_idx, "speak", time.time()),
    )

    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=turn_idx,
                      player_input="speak", created=time.time()),
        cast=cast,
        input="speak",
    )
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None, "movement": None,
        "flow": {"reactors": [], "authority_claims": authority_claims or [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    return ctx


def _run_resolve(ctx, monkeypatch, agent_out=None, captured=None):
    import agents.director as director

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        if captured is not None:
            captured.update(payload)
        return dict(agent_out or {})

    monkeypatch.setattr(director, "_agent_json", fake_agent_json)
    return director.director_resolve(ctx, nonce=0)


# ---- W1: obligation ledger ----

def test_open_op_appends_ledger_and_dedupes(temp_db, monkeypatch):
    ctx = _make_ctx(temp_db, turn_idx=3)
    op = {"op": "open", "who": "Mara", "what": "deliver the diagnostic report",
          "kind": "demand"}
    ctx.director_resolve = _run_resolve(
        ctx, monkeypatch, agent_out={"obligations": [op, dict(op)]})

    result = commit.commit_obligations(ctx, nonce=0)

    ledger = temp_db.wget(ctx.chat.id, "pending_obligations", [])
    assert result["opened"] == 1
    assert len(ledger) == 1
    assert ledger[0]["who"] == "Mara"
    assert ledger[0]["opened_turn"] == 3
    assert ledger[0]["id"]

    # Re-demanding the same open debt next turn is not a second debt.
    ctx.turn = TurnData(id=ctx.turn.id, chat_id=ctx.chat.id, idx=4,
                        player_input="speak", created=time.time())
    ctx.director_resolve = {"obligations": [dict(op)]}
    commit.commit_obligations(ctx, nonce=0)
    assert len(temp_db.wget(ctx.chat.id, "pending_obligations", [])) == 1


def test_discharge_removes_entry_by_id_and_fuzzy(temp_db):
    ctx = _make_ctx(temp_db, turn_idx=5)
    temp_db.wset(ctx.chat.id, "pending_obligations", [
        {"id": "obl:3:0", "who": "Mara", "what": "deliver the diagnostic report",
         "kind": "demand", "opened_turn": 4},
        {"id": "obl:4:0", "who": "Reya", "what": "answer where the key is",
         "kind": "question", "opened_turn": 4},
    ])
    ctx.director_resolve = {"obligations": [
        {"op": "discharge", "id": "obl:3:0"},
        # No id: fuzzy who+overlapping-text match must find Reya's entry.
        {"op": "refuse", "who": "Reya", "what": "answer where the key is hidden"},
    ]}

    result = commit.commit_obligations(ctx, nonce=0)

    assert result["discharged"] == 2
    assert temp_db.wget(ctx.chat.id, "pending_obligations", []) == []
    assert not ctx.warnings


def test_overdue_redeferral_warns_and_entry_survives(temp_db):
    ctx = _make_ctx(temp_db, turn_idx=6)
    temp_db.wset(ctx.chat.id, "pending_obligations", [
        {"id": "obl:3:0", "who": "Mara", "what": "deliver the diagnostic report",
         "kind": "demand", "opened_turn": 3},
    ])
    ctx.director_resolve = {"obligations": []}

    result = commit.commit_obligations(ctx, nonce=0)

    assert result["overdue"] == 1
    assert len(temp_db.wget(ctx.chat.id, "pending_obligations", [])) == 1
    assert any("re-deferred" in w for w in ctx.warnings)


def test_fresh_obligation_does_not_warn(temp_db):
    ctx = _make_ctx(temp_db, turn_idx=4)
    temp_db.wset(ctx.chat.id, "pending_obligations", [
        {"id": "obl:3:0", "who": "Mara", "what": "deliver the diagnostic report",
         "kind": "demand", "opened_turn": 3},
    ])
    ctx.director_resolve = {"obligations": []}

    result = commit.commit_obligations(ctx, nonce=0)

    assert result["overdue"] == 0
    assert not ctx.warnings


def test_resolve_payload_surfaces_overdue_flag(temp_db, monkeypatch):
    ctx = _make_ctx(temp_db, turn_idx=5)
    temp_db.wset(ctx.chat.id, "pending_obligations", [
        {"id": "obl:2:0", "who": "Mara", "what": "deliver the diagnostic report",
         "kind": "demand", "opened_turn": 2},
        {"id": "obl:4:0", "who": "Reya", "what": "answer the hail",
         "kind": "announced_action", "opened_turn": 4},
    ])

    captured = {}
    _run_resolve(ctx, monkeypatch, captured=captured)

    obls = {o["id"]: o for o in captured["pending_obligations"]}
    assert obls["obl:2:0"]["age_beats"] == 3
    assert obls["obl:2:0"]["must_discharge_this_beat"] is True
    assert obls["obl:4:0"]["age_beats"] == 1
    assert obls["obl:4:0"]["must_discharge_this_beat"] is False


# ---- W2: player-asserted fact adjudication ----

_EVENT_CLAIM = {
    "claim_id": "claim:0:event", "scope": "effect", "subject_id": None,
    "predicate": "the crew on deck 12 are dead", "value": None,
    "commitment": "asserted",
    "source_text": "the crew on deck 12 are dead",
}


def test_unadjudicated_event_claim_warns(temp_db, monkeypatch):
    ctx = _make_ctx(temp_db, authority_claims=[dict(_EVENT_CLAIM)])
    _run_resolve(ctx, monkeypatch, agent_out={})

    assert any("Unadjudicated player-asserted fact" in w for w in ctx.warnings)


def test_adjudicated_event_claim_passes(temp_db, monkeypatch):
    ctx = _make_ctx(temp_db, authority_claims=[dict(_EVENT_CLAIM)])
    out = _run_resolve(ctx, monkeypatch, agent_out={"fact_adjudications": [
        {"claim_id": "claim:0:event",
         "claim": "the crew on deck 12 are dead",
         "subject": "deck 12 crew", "verdict": "confirmed",
         "landing": "Mara confirms the deaths on-page"},
    ]})

    assert not [w for w in ctx.warnings if "Unadjudicated" in w]
    assert out["fact_adjudications"][0]["verdict"] == "confirmed"


def test_non_event_claims_need_no_adjudication(temp_db, monkeypatch):
    # The player's own on-page act (an effect claim) is authority-contract
    # territory, covered by claim_dispositions -- no adjudication warning.
    ctx = _make_ctx(temp_db, authority_claims=[{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": "Mara", "predicate": "grabbed_arm", "value": None,
        "commitment": "asserted", "source_text": "I grab Mara's arm",
    }])
    _run_resolve(ctx, monkeypatch, agent_out={})

    assert not [w for w in ctx.warnings if "Unadjudicated" in w]


# ---- W5: authority appraisal hint ----

def test_resolve_payload_carries_social_standing(temp_db, monkeypatch):
    ctx = _make_ctx(
        temp_db,
        public_history="Visiting ethics observer with no command authority.",
    )
    captured = {}
    _run_resolve(ctx, monkeypatch, captured=captured)

    standing = captured["social_standing"]
    assert standing["Mara"].startswith("Visiting ethics observer")
    # The player appears too (persona_public_history, possibly empty).
    assert "The Stranger" in standing
