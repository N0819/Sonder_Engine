"""Regression tests for the interpret-side player-authority seam
(movement/space Phase 1, item 2) -- the structural twin of the resolve
reconciliation: deterministic omission detection of player declarations a
weak interpret dropped, one bounded self-repair, warn-only fallback that
forwards the verbatim clause to mapping as a generation request (never
fabricating a structured act). Plus its two enabling fixes:
_extract_authority_claims' raw_input fallback and norm_sequence's
first-class actor-less environmental events.
"""

import json
import time

from character_schema import default_character_data
from pipeline_context import ChatData, PipelineContext, TurnData


# ---- gap (A): _extract_authority_claims raw_input fallback ---------------

def test_authority_claims_fall_back_to_raw_input():
    from agents.common import _extract_authority_claims

    sequence = [{
        "type": "action", "attempt": "", "raw_text": "",
        "asserted_effects": [{"target_id": "door", "kind": "opened"}],
        "commitment": "asserted",
    }]
    claims = _extract_authority_claims(sequence, "I fling the door open")
    assert claims and claims[0]["source_text"] == "I fling the door open"


def test_authority_claims_classify_commitment_from_raw_input():
    from agents.common import _extract_authority_claims

    sequence = [{
        "type": "action", "attempt": "", "raw_text": "",
        "intended_effects": [{"target_id": "guard", "kind": "distracted"}],
    }]
    # "try to" in the raw input marks the attempt contestable even though
    # the element itself carries no classifiable text.
    claims = _extract_authority_claims(sequence, "I try to distract the guard")
    assert claims and claims[0]["commitment"] == "contestable"


# ---- gap (B): actor-less environmental events survive norm_sequence -----

def test_norm_sequence_keeps_environmental_events():
    from agents.common import norm_sequence

    out = {"sequence": [
        {"type": "event", "description": "the lights go out",
         "subject": "lights"},
        {"type": "action", "attempt": "grab the railing"},
    ]}
    norm_sequence(out)
    kinds = [e["type"] for e in out["sequence"]]
    assert "event" in kinds, "environmental events used to be dropped here"
    event = next(e for e in out["sequence"] if e["type"] == "event")
    assert event["description"] == "the lights go out"
    assert event["commitment"] == "asserted"


def test_environmental_event_mints_an_effect_claim():
    from agents.common import _extract_authority_claims, norm_sequence

    out = {"sequence": [
        {"type": "event", "description": "a monster enters the hall",
         "subject": "monster"},
    ]}
    norm_sequence(out)
    claims = _extract_authority_claims(out["sequence"], "A monster enters")
    assert claims and claims[0]["scope"] == "effect"
    assert claims[0]["commitment"] == "asserted"


# ---- the seam itself -----------------------------------------------------

def _make_ctx(temp_db, player_input):
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
    temp_db.wset(
        chat_id, "scene",
        {
            "location": "Outpost", "time": "night",
            "rooms": {
                "guard_post": {
                    "name": "Guard Post",
                    "adjacent": [{"to": "hallway", "barrier": "open",
                                  "distance": "near"}],
                },
                "hallway": {"name": "Hallway", "adjacent": []},
            },
            "positions": {"The Stranger": "guard_post", "Mara": "guard_post"},
            "entities": {}, "attire": {}, "overlays": {},
        },
    )
    cast = temp_db.q(
        "SELECT ch.*,cc.state AS cstate,cc.status FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
        (chat_id,),
    )
    turn_id = temp_db.qi(
        "INSERT INTO turns(chat_id,idx,player_input,created) VALUES(?,?,?,?)",
        (chat_id, 1, player_input, time.time()),
    )
    return PipelineContext(
        chat=ChatData(id=chat_id, name="Test", persona_id=None,
                      lorebook_id=None, scenario="", created=time.time()),
        turn=TurnData(id=turn_id, chat_id=chat_id, idx=1,
                      player_input=player_input, created=time.time()),
        cast=cast,
        input=player_input,
    )


# A weak-model interpretation of "I wave to Mara, then I duck into the
# armory and grab a rifle" that silently dropped the armory/rifle clause.
_WEAK_INTERPRET = {
    "kind": "action",
    "sequence": [
        {"type": "action", "attempt": "wave to Mara",
         "raw_text": "I wave to Mara"},
    ],
    "speech": None, "action": None, "movement": None,
    "location_query": None,
    "flow": {"reactors": [], "dialogue_mode": False, "needs_mapping": False,
             "mapping_request": "", "dice": [], "tom_triggers": [],
             "resolution_flags": {}, "generation_requests": [],
             "authority_claims": [], "fiction_frame": {}},
    "notes": "",
}

_REPAIR = {
    "sequence": [
        {"type": "action", "attempt": "duck into the armory",
         "raw_text": "duck into the armory", "commitment": "asserted"},
        {"type": "action", "attempt": "grab a rifle",
         "raw_text": "grab a rifle", "commitment": "asserted",
         "asserted_effects": [{"target_id": "rifle", "kind": "taken"}]},
    ],
    "movement": {"to_room": "armory", "why": "player declared entering",
                 "mover": "self"},
    "mapping_request": "Player enters the armory; generate its layout and "
                       "the grabbed rifle.",
    "generation_requests": [
        {"kind": "player_declaration", "subject": "the armory and a rifle",
         "constraints": [], "urgency": "now"},
    ],
    "dispositions": [],
    "notes": "",
}


def _run_interpret(temp_db, monkeypatch, interpret_out, repair_out=None,
                   repair_raises=False):
    import agents.director as director

    ctx = _make_ctx(
        temp_db, "I wave to Mara, then I duck into the armory and grab a rifle")
    calls = []

    def fake_agent_json(role, step_key, system, payload, **kwargs):
        calls.append(step_key)
        if step_key == "director_interpret":
            return json.loads(json.dumps(interpret_out))
        if step_key == "interpret_repair":
            if repair_raises:
                raise RuntimeError("repair model unavailable")
            return json.loads(json.dumps(repair_out or {}))
        raise AssertionError(f"unexpected step {step_key}")

    monkeypatch.setattr(director, "_agent_json", fake_agent_json)
    out = director.director_interpret(ctx, nonce=0)
    return ctx, out, calls


def test_dropped_declaration_is_detected_and_repaired(temp_db, monkeypatch):
    ctx, out, calls = _run_interpret(
        temp_db, monkeypatch, _WEAK_INTERPRET, repair_out=_REPAIR)

    assert "interpret_repair" in calls
    recon = out["interpret_reconciliation"]
    assert recon["uncovered"], "the armory/rifle clause must be detected"
    assert recon["repaired"]
    assert recon["unresolved"] == []

    attempts = [e.get("attempt") for e in out["sequence"]
                if e.get("type") == "action"]
    assert "duck into the armory" in attempts
    assert "grab a rifle" in attempts
    # Existing interpretation is never replaced -- additions come after.
    assert attempts[0] == "wave to Mara"

    # The repaired movement fills in and feeds the ordinary new-room
    # mapping trigger downstream.
    assert out["movement"]["to_room"] == "armory"
    fl = out["flow"]
    assert fl["needs_mapping"] is True
    assert fl["generation_requests"], "the captured declaration reaches mapping"
    # Authority claims are extracted AFTER the repair, so the asserted
    # rifle grab is covered by the resolve seam's player-claim check.
    assert any(c.get("subject_id") == "rifle"
               for c in fl["authority_claims"])


def test_covered_interpretation_makes_no_repair_call(temp_db, monkeypatch):
    covered = json.loads(json.dumps(_WEAK_INTERPRET))
    covered["sequence"] = [
        {"type": "action", "attempt": "wave to Mara",
         "raw_text": "I wave to Mara"},
        {"type": "action", "attempt": "duck into the armory",
         "raw_text": "duck into the armory"},
        {"type": "action", "attempt": "grab a rifle",
         "raw_text": "grab a rifle"},
    ]
    ctx, out, calls = _run_interpret(temp_db, monkeypatch, covered)

    assert calls == ["director_interpret"], \
        "no omission -> zero extra LLM spend on the common path"
    assert out["interpret_reconciliation"]["uncovered"] == []


def test_failed_repair_falls_back_to_verbatim_generation_request(
    temp_db, monkeypatch,
):
    """NEVER fabricate: with the repair unavailable, the seam must not
    invent a structured act -- it forwards the player's verbatim clause to
    mapping as a generation request and warns."""
    ctx, out, calls = _run_interpret(
        temp_db, monkeypatch, _WEAK_INTERPRET, repair_raises=True)

    recon = out["interpret_reconciliation"]
    assert recon["unresolved"], "clause stays flagged when repair fails"
    # No fabricated sequence element.
    attempts = [e.get("attempt") for e in out["sequence"]
                if e.get("type") == "action"]
    assert attempts == ["wave to Mara"]
    fl = out["flow"]
    synthesized = [g for g in fl["generation_requests"]
                   if g.get("kind") == "player_declaration"]
    assert synthesized, "verbatim clause forwarded to mapping"
    assert any("armory" in str(g.get("subject")) for g in synthesized)
    assert fl["needs_mapping"] is True
    assert any("PLAYER AUTHORITY" in w for w in ctx.warnings)


def test_generation_requests_reach_the_mapping_payload(temp_db, monkeypatch):
    """Item 2 gap (C): the revived generation_requests channel must
    actually arrive in mapping_stage's LLM payload."""
    import agents.mapping as mapping

    ctx, out, _ = _run_interpret(
        temp_db, monkeypatch, _WEAK_INTERPRET, repair_raises=True)
    ctx.director_interpret = out

    captured = {}

    def fake_mapping_json(role, step_key, system, payload, **kwargs):
        captured.update(payload)
        return {"relevant_lore": [], "staged_lore": [], "scene_patch": {},
                "relevant_books": []}

    monkeypatch.setattr(mapping, "_agent_json", fake_mapping_json)
    mapping.mapping_stage(ctx, nonce=0)

    assert captured.get("generation_requests"), \
        "captured declarations must be forwarded to mapping"
    assert any("armory" in str(g.get("subject"))
               for g in captured["generation_requests"])


def test_mapping_quick_escalates_on_generation_requests(temp_db, monkeypatch):
    import agents.mapping as mapping

    ctx = _make_ctx(temp_db, "look around")
    ctx.director_interpret = {
        "sequence": [], "movement": None, "location_query": None,
        "flow": {"mapping_request": "", "generation_requests": [
            {"kind": "player_declaration", "subject": "a rifle"}]},
    }
    called = {}
    monkeypatch.setattr(
        mapping, "mapping_stage",
        lambda c, n: called.setdefault("stage", True) or {"escalated": True})

    result = mapping.mapping_quick(ctx, nonce=0)
    assert called.get("stage"), \
        "cached recall cannot mint declared content; must escalate"
