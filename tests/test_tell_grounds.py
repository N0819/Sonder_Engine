"""F6 (docs/FABLE_REVIEW_FOLLOWUPS.md): a planted tell must have a stored
referent. Impostor t2 planted 'a half-second longer than a servant's glance
should' with no ground anywhere -- in a mystery, readers bank every such
detail, so an untethered tell is fake significance.

Mechanism under test:
- affect.ground_tells: every manifest tell carries a non-empty `because`
  (the model's own, or derived deterministically from the tell's `betrays`
  pointer via active_state's suppressed want / undercurrent); a tell with no
  derivable ground warns.
- character_step applies it, so the step output itself is grounded.
- commit's prepare_memory_commit persists {cue, because, turn} onto
  cstate's tell_grounds ledger (capped), and character_step feeds the
  ledger back as self.tell_grounds with a TELL PAYOFF prompt block.
"""

import json
import time

from affect import ground_tells
from character_schema import default_character_data
from commit import RECENT_TELLS_CAP, prepare_memory_commit
from pipeline_context import ChatData, PipelineContext, TurnData


_STATE = {
    "affect": {
        "surface": {"label": "even", "valence": 0.0, "arousal": 0.2},
        "undercurrent": {"label": "dread of exposure", "valence": -0.6,
                         "arousal": 0.7},
        "baseline": {"valence": 0.0, "arousal": 0.2},
    },
    "wants": [
        {"want": "steer talk away from the household staff", "urgency": 0.8,
         "serves": "drive"},
        {"want": "keep the right hand unremarkable", "urgency": 0.9,
         "serves": "drive"},
    ],
    "enacted_want": 0,
    "suppressed_want": 1,
}


# ---- affect.ground_tells ----

def test_model_supplied_because_is_kept():
    manifest = {"tells": [{"cue": "hand lingers on the glass",
                           "betrays": "suppressed_want",
                           "because": "the right hand is the trained one"}]}
    out, warnings = ground_tells(manifest, _STATE)
    assert out["tells"][0]["because"] == "the right hand is the trained one"
    assert warnings == []


def test_missing_because_derives_from_suppressed_want():
    manifest = {"tells": [{"cue": "hand lingers on the glass",
                           "betrays": "suppressed_want"}]}
    out, warnings = ground_tells(manifest, _STATE)
    assert out["tells"][0]["because"] == "keep the right hand unremarkable"
    assert warnings == []


def test_missing_because_derives_from_undercurrent():
    manifest = {"tells": [{"cue": "a too-even voice",
                           "betrays": "undercurrent"}]}
    out, warnings = ground_tells(manifest, _STATE)
    assert out["tells"][0]["because"] == "dread of exposure"
    assert warnings == []


def test_no_derivable_ground_warns():
    manifest = {"tells": [{"cue": "jaw tightens"}]}
    out, warnings = ground_tells(manifest, {})
    assert "because" not in out["tells"][0]
    assert len(warnings) == 1 and "ungrounded tell" in warnings[0]


def test_junk_is_safe():
    assert ground_tells(None, None) == (None, [])
    assert ground_tells({"tells": "junk"}, {}) == ({"tells": "junk"}, [])
    manifest = {"tells": [
        "junk", {"cue": ""}, {"cue": "real", "betrays": "undercurrent"}]}
    out, _ = ground_tells(manifest, {"affect": {"undercurrent": "unease"},
                                     "suppressed_want": "not-an-index"})
    assert out["tells"][2]["because"] == "unease"


# ---- fixtures shared with the character/commit halves ----

def _story(temp_db, cstate, *, name="Sir Julian"):
    chat_id = temp_db.qi(
        "INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
        ("Test", "", time.time()))
    sheet = default_character_data(name)
    char_id = temp_db.qi(
        "INSERT INTO characters(name,sheet,source,created,resource_uid) "
        "VALUES(?,?,?,?,?)",
        (name, json.dumps(sheet), "{}", time.time(),
         sheet["identity"]["uid"]))
    temp_db.qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state) VALUES(?,?,?,?)",
        (chat_id, char_id, "active", json.dumps(cstate)))
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,))
    return chat_id, char_id, cast


# ---- character_step grounds its own output ----

def _run_character_step(temp_db, monkeypatch, cstate, agent_out):
    import agents.character as character_module

    chat_id, char_id, cast = _story(temp_db, cstate)
    temp_db.wset(chat_id, "scene", {
        "location": "Drawing Room", "time": "night",
        "rooms": {"drawing_room": {"name": "Drawing Room", "adjacent": []}},
        "positions": {"Sir Julian": "drawing_room"},
        "entities": {}, "attire": {}, "overlays": {},
    })
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, "a toast", time.time()))
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input="a toast", created=time.time()),
        cast=cast, input="a toast")
    ctx.director_interpret = {"flow": {"reactors": [char_id],
                                       "tom_triggers": []}}
    captured = {}

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        captured["system"] = system
        captured["payload"] = payload
        return dict(agent_out)

    monkeypatch.setattr(character_module, "_agent_json", fake_agent_json)
    out = character_module.character_step(ctx, char_id, nonce=0)
    return ctx, out, captured


def test_character_step_grounds_ungrounded_tell(temp_db, monkeypatch):
    ctx, out, _ = _run_character_step(temp_db, monkeypatch, {}, {
        "sequence": [],
        "active_state": _STATE,
        "manifest": {"surface_demeanor": "genial",
                     "tells": [{"cue": "hand lingers on the glass",
                                "channel": "hands", "subtlety": 0.7,
                                "betrays": "suppressed_want"}]},
    })
    tell = out["manifest"]["tells"][0]
    assert tell["because"] == "keep the right hand unremarkable"
    assert not any("ungrounded" in w for w in ctx.warnings)


def test_character_step_warns_on_underivable_ground(temp_db, monkeypatch):
    ctx, out, _ = _run_character_step(temp_db, monkeypatch, {}, {
        "sequence": [],
        "manifest": {"tells": [{"cue": "jaw tightens", "channel": "face"}]},
    })
    assert any("ungrounded tell" in w for w in ctx.warnings)


def test_tell_grounds_ledger_fed_back_with_payoff_rule(temp_db, monkeypatch):
    grounds = [{"cue": "hand lingers on the glass",
                "because": "the right hand is the trained one", "turn": 2}]
    _, _, captured = _run_character_step(
        temp_db, monkeypatch, {"tell_grounds": grounds}, {"sequence": []})
    assert captured["payload"]["self"]["tell_grounds"] == [
        {"cue": "hand lingers on the glass",
         "because": "the right hand is the trained one"}]
    assert "TELL PAYOFF" in captured["system"]
    # empty ledger: no payload key, no prompt bloat
    _, _, captured = _run_character_step(temp_db, monkeypatch, {},
                                         {"sequence": []})
    assert "tell_grounds" not in captured["payload"]["self"]
    assert "TELL PAYOFF" not in captured["system"]


# ---- commit persists the grounds ----

def test_commit_accrues_tell_grounds_capped(temp_db):
    prev = [{"cue": f"old {i}", "because": f"ground {i}", "turn": i}
            for i in range(RECENT_TELLS_CAP)]
    chat_id, char_id, cast = _story(temp_db, {"tell_grounds": prev})
    ctx = PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=9, chat_id=chat_id, idx=8, player_input="...",
                      created=time.time()),
        cast=cast, input="...",
        director_resolve={"resolved_event": "The toast is drunk.",
                          "dialogue_log": []})
    ctx.character_results = {char_id: {
        "manifest": {"tells": [
            {"cue": "hand lingers on the glass",
             "because": "the right hand is the trained one"},
            {"cue": "ungrounded cue with no because"},  # not persisted
        ]},
    }}
    out = prepare_memory_commit(ctx)
    st = next(json.loads(s) for _, ccid, s in out["state_updates"]
              if ccid == char_id)
    ledger = st["tell_grounds"]
    assert len(ledger) == RECENT_TELLS_CAP
    assert ledger[-1] == {"cue": "hand lingers on the glass",
                          "because": "the right hand is the trained one",
                          "turn": 8}
    assert all(g["because"] for g in ledger)
