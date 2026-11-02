"""The encoder is shown each present person's standing; the Director is not.

The Enterprise-D audit's "obeys anyone's orders" failure: the resolve's one
encoder carries a `social_standing` hint per present person, from public
history only, so an order from someone with no standing reads as one; the
prose Director is not shown it.

Moved here on 2026-11-01 from `tests/test_director_obligations.py` (its "W5"
group), which retired with the obligations ledger it was named for. The test
is unchanged but for the ledger: its capture used to assert the Director was
not shown `pending_obligations` either, a key nothing builds any more
(`tests/test_the_obligations_ledger_is_gone.py`).
"""

import json
import time

import agents.director as director
from core.pipeline_context import ChatData, PipelineContext, TurnData
from story.character_schema import default_character_data
from tests.director_fakes import prose_resolve_agent


def _make_ctx(temp_db, *, public_history=""):
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
    temp_db.wset(chat_id, "scene", {
        "location": "Bridge",
        "time": "day",
        "rooms": {"bridge": {"name": "Bridge", "adjacent": []}},
        "positions": {"The Stranger": "bridge", "Mara": "bridge"},
        "entities": {},
        "attire": {},
        "overlays": {},
    })
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "speak", time.time()),
    )
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="speak", created=time.time()),
        cast=cast,
        input="speak",
    )
    ctx.director_interpret = {
        "sequence": [], "speech": None, "action": None, "movement": None,
        "flow": {"reactors": [], "authority_claims": [],
                 "resolution_flags": {}, "fiction_frame": {}},
    }
    return ctx


def test_resolve_payload_carries_social_standing(temp_db, prose_director, monkeypatch):
    """Ported 2026-09-27: the standing reaches the one encoder; the prose
    Director is not shown it.
    """
    ctx = _make_ctx(
        temp_db,
        public_history="Visiting ethics observer with no command authority.",
    )
    calls = []
    monkeypatch.setattr(director, "_agent_json", prose_resolve_agent(
        {"resolved_event": "Mara refuses the request."}, calls=calls))
    director.director_resolve(ctx, nonce=0)
    by_step = {}
    for key, payload in calls:
        by_step.setdefault(key, payload)
    assert "social_standing" not in by_step["director_prose"]

    standing = by_step["director_specialist"]["social_standing"]
    assert standing["Mara"].startswith("Visiting ethics observer")
    # The player appears too (persona_public_history, possibly empty).
    assert "The Stranger" in standing
