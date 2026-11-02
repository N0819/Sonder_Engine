"""A player-authored world assertion is adjudicated, or flagged as not.

The Enterprise-D audit's "tolerates unbacked claims" failure: a player's
actor-less `event` authority claim ("the crew on deck 12 are dead") that the
beat leaves without a `fact_adjudications` verdict is flagged; the player's
own on-page act is authority-contract territory and needs none.

Moved here unchanged on 2026-11-01 from `tests/test_director_obligations.py`
(its "W2" group), which retired with the obligations ledger it was named for
-- these tests never touched that ledger. `docs/UNBUILT_PIPELINE.md` § 1.1
item 7 cites the strict xfail below.
"""

import json
import time

import pytest

import agents.director as director
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data
from tests.director_fakes import prose_resolve_agent


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


def _make_ctx(temp_db, *, turn_idx=1, authority_claims=None):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()),
    )
    sheet = default_character_data("Mara")
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


def _prose(ctx, monkeypatch, output, calls=None):
    monkeypatch.setattr(director, "_agent_json",
                        prose_resolve_agent(output, calls=calls))
    return director.director_resolve(ctx, nonce=0)


_EVENT_CLAIM = {
    "claim_id": "claim:0:event", "scope": "effect", "subject_id": None,
    "predicate": "the crew on deck 12 are dead", "value": None,
    "commitment": "asserted",
    "source_text": "the crew on deck 12 are dead",
}


def test_unadjudicated_event_claim_warns(temp_db, prose_director, monkeypatch):
    """Ported 2026-09-27. On the prose path nothing writes
    `fact_adjudications`, so this fires on EVERY beat that carries a
    player-asserted event (UNBUILT_PIPELINE §1.1); the xfail below pins the
    other half.
    """
    ctx = _make_ctx(temp_db, authority_claims=[dict(_EVENT_CLAIM)])
    _prose(ctx, monkeypatch, {})

    assert any("Unadjudicated player-asserted fact" in w for w in ctx.warnings)


@pytest.mark.xfail(
    strict=True,
    reason="`fact_adjudications` was the causal Director's own field; the prose "
           "Director writes prose, nothing records a verdict, and so every beat "
           "that carries a player-asserted event warns (UNBUILT_PIPELINE §1.1)")
def test_adjudicated_event_claim_passes(temp_db, prose_director, monkeypatch):
    """A beat whose prose lands the claim is not an unadjudicated one. Held as
    a strict xfail since 2026-09-27: the verdict was the causal Director's
    `fact_adjudications`, and the prose path records none.
    """
    ctx = _make_ctx(temp_db, authority_claims=[dict(_EVENT_CLAIM)])
    _prose(ctx, monkeypatch,
           {"resolved_event": "Mara confirms the deaths on deck 12."})

    assert not [w for w in ctx.warnings if "Unadjudicated" in w]


def test_non_event_claims_need_no_adjudication(temp_db, prose_director, monkeypatch):
    """Ported 2026-09-27 to the prose Director."""
    # The player's own on-page act (an effect claim) is authority-contract
    # territory, covered by claim_dispositions -- no adjudication warning.
    ctx = _make_ctx(temp_db, authority_claims=[{
        "claim_id": "claim:0:effect:0", "scope": "effect",
        "subject_id": "Mara", "predicate": "grabbed_arm", "value": None,
        "commitment": "asserted", "source_text": "I grab Mara's arm",
    }])
    _prose(ctx, monkeypatch, {})

    assert not [w for w in ctx.warnings if "Unadjudicated" in w]
