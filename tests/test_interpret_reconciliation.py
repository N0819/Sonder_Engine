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

import agents.director as director
from story.character_schema import default_character_data
from core.pipeline_context import ChatData, PipelineContext, TurnData
from tests.director_fakes import _fake_agent, _steps, encoder_event


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


# ---- self-directed effect resolves to the declaring actor ---------------

def test_self_directed_effect_resolves_to_actor():
    # A wave / going rigid: the action names no targets and the effect has no
    # target_id -> the subject is the player, not None (which tripped the
    # resolve reconciliation's 'no resolvable subject' note every beat).
    from agents.common import _extract_authority_claims

    sequence = [{
        "type": "action", "attempt": "give a little wave", "targets": [],
        "asserted_effects": [{"target_id": None, "kind": "The player waves."}],
        "commitment": "asserted",
    }]
    claims = _extract_authority_claims(sequence, "give a little wave",
                                       actor_name="Hinami")
    assert claims and claims[0]["subject_id"] == "Hinami"


def test_transitive_effect_not_hijacked_to_actor():
    # The action DOES name a target -> a null effect target is a dropped
    # reference, NOT the actor's own body. Must not resolve to the player,
    # or the player would silently author effects on other entities.
    from agents.common import _extract_authority_claims

    sequence = [{
        "type": "action", "attempt": "punch the guard", "targets": ["guard"],
        "asserted_effects": [{"target_id": None, "kind": "staggers"}],
        "commitment": "asserted",
    }]
    claims = _extract_authority_claims(sequence, "I punch the guard",
                                       actor_name="Hinami")
    assert claims and claims[0]["subject_id"] != "Hinami"


def test_world_event_assertion_not_hijacked_to_actor():
    # The actor-less `event` branch (a player-authored world fact) stays for
    # the director to adjudicate even when an actor_name is supplied.
    from agents.common import _extract_authority_claims

    sequence = [{"type": "event", "description": "two guards appear",
                 "subject": ""}]
    claims = _extract_authority_claims(sequence, "two guards appear",
                                       actor_name="Hinami")
    assert claims and claims[0]["subject_id"] != "Hinami"


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


INPUT = "I wave to Mara, then I duck into the armory and grab a rifle"

PROSE = {"prose": "You wave to Mara, then duck into the armory and grab a rifle."}

NO_EVENTS = {"events": [], "missing_tools": [], "missing_referents": [], "notes": []}


def _run(temp_db, monkeypatch, encoder=NO_EVENTS, repair=None):
    ctx = _make_ctx(temp_db, INPUT)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "director_prose": PROSE,
        "director_specialist": encoder,
        **({"interpret_repair": repair} if repair is not None else {}),
    }))
    out = director.director_interpret(ctx, nonce=0)
    return ctx, out, _steps(calls)


def _full_repair(**movement):
    repair = json.loads(json.dumps(_REPAIR))
    repair["sequence"] = [{"type": "action", "attempt": "wave to Mara",
                           "raw_text": "I wave to Mara", "commitment": "asserted"}] \
        + repair["sequence"]
    repair["movement"].update(movement)
    return repair


def test_dropped_declaration_is_detected_and_repaired(temp_db, prose_director, monkeypatch):
    """Ported 2026-09-27 to the prose Director, on an interpret whose encoder
    returned no events: the only interpret on which the repair runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3). The repair then carries every
    clause, so it holds the wave too.
    """
    ctx, out, steps = _run(temp_db, monkeypatch, repair=_full_repair())
    assert "interpret_repair" in steps
    recon = out["interpret_reconciliation"]
    assert recon["uncovered"]
    assert recon["repaired"]
    assert recon["unresolved"] == []
    attempts = [e.get("attempt") for e in out["sequence"] if e.get("type") == "action"]
    assert "duck into the armory" in attempts
    assert "grab a rifle" in attempts
    assert out["movement"]["to_room"] == "armory"
    fl = out["flow"]
    assert fl["needs_mapping"] is True
    assert fl["generation_requests"]
    assert any(c.get("subject_id") == "rifle" for c in fl["authority_claims"])


def test_the_repair_carries_arrives_through(temp_db, prose_director, monkeypatch):
    """A repaired movement is the ONLY movement on that beat, so dropping
    `arrives` from the rebuild silently upgraded every repaired approach to an
    arrival.

    The field defaults True and `_guard_approach_is_not_arrival` fires only on
    False (`mv.get("arrives", True)`), so the omission was invisible: a repair
    that correctly read "I head for the treeline" as arrives:false was
    rewritten into a body standing at the treeline. The repair SHEET already
    asked for the field; the seam's own dict literal threw it away.

    Ported 2026-09-27 to the prose Director, on an interpret whose encoder
    returned no events: the only interpret on which the repair runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3). The repair then carries every
    clause, so it holds the wave too.
    """
    ctx, out, steps = _run(temp_db, monkeypatch, repair=_full_repair(arrives=False))
    assert "interpret_repair" in steps
    assert out["movement"]["to_room"] == "armory"
    assert out["movement"]["arrives"] is False


def test_a_repair_that_says_nothing_about_arriving_still_arrives(temp_db, prose_director, monkeypatch):
    """The default is the pre-existing behaviour and must stay it: silence on
    the field is an arrival, not a stalled walk.

    Ported 2026-09-27 to the prose Director, on an interpret whose encoder
    returned no events: the only interpret on which the repair runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3). The repair then carries every
    clause, so it holds the wave too.
    """
    ctx, out, steps = _run(temp_db, monkeypatch, repair=_REPAIR)
    assert out["movement"]["arrives"] is True


def test_covered_interpretation_makes_no_repair_call(temp_db, prose_director, monkeypatch):
    """Ported 2026-09-27: the encoder's three events cover the three clauses.
    """
    encoder = {"events": [
        encoder_event("wave to Mara"),
        encoder_event("duck into the armory"),
        encoder_event("grab a rifle"),
    ], "missing_tools": [], "missing_referents": [], "notes": []}
    ctx, out, steps = _run(temp_db, monkeypatch, encoder=encoder)
    assert "interpret_repair" not in steps
    assert steps[0] == "director_prose"
    assert out["interpret_reconciliation"]["uncovered"] == []


def test_tone_and_observable_cover_authored_dialogue_progression():
    """Delivery and visible gesture are real declaration channels.

    Live (chat 38, turn 125), both were present in structured output, but the
    coverage corpus ignored them and appended the whole bridge as a redundant
    repair action. That gave perception two competing chronologies.
    """
    from agents.director import _uncovered_declarations

    raw = ('"It\'s really beautiful..." You say in genuine awe before '
           'turning back to him with a teasing smirk "So do you pick up '
           'girls and attempt to woo them?"')
    interpreted = {
        "sequence": [
            {"type": "speech", "text": "It's really beautiful...",
             "tone": "genuine awe"},
            {"type": "action", "attempt": "turn back toward him",
             "observable": "turns back toward him"},
            {"type": "speech",
             "text": "So do you pick up girls and attempt to woo them?",
             "tone": "teasing smirk"},
        ],
        "flow": {},
    }

    assert _uncovered_declarations(raw, interpreted) == []


def test_failed_repair_falls_back_to_verbatim_generation_request(temp_db, prose_director, monkeypatch):
    """NEVER fabricate: with the repair unavailable, the seam must not
    invent a structured act -- it forwards the player's verbatim clause to
    mapping as a generation request and warns.

    Ported 2026-09-27 to the prose Director, on an interpret whose encoder
    returned no events: the only interpret on which the repair runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3). The repair then carries every
    clause, so it holds the wave too.
    """
    ctx, out, steps = _run(temp_db, monkeypatch,
                           repair=RuntimeError("repair model unavailable"))
    recon = out["interpret_reconciliation"]
    assert recon["unresolved"]
    attempts = [e.get("attempt") for e in out["sequence"] if e.get("type") == "action"]
    assert attempts == []
    fl = out["flow"]
    synthesized = [g for g in fl["generation_requests"] if g.get("kind") == "player_declaration"]
    assert synthesized
    assert any("armory" in str(g.get("subject")) for g in synthesized)
    assert fl["needs_mapping"] is True
    assert any("PLAYER AUTHORITY" in w for w in ctx.warnings)


def test_generation_requests_become_planning_needs(temp_db, prose_director, monkeypatch):
    """Item 2 gap (C): the revived generation_requests channel must actually
    arrive somewhere. It used to arrive in the mapping model's payload; the
    world-context compiler records each one as a typed planning need.

    Ported 2026-09-27 to the prose Director, on an interpret whose encoder
    returned no events: the only interpret on which the repair runs
    (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3). The repair then carries every
    clause, so it holds the wave too.
    """
    import agents.mapping as mapping
    ctx, out, _ = _run(temp_db, monkeypatch,
                       repair=RuntimeError("repair model unavailable"))
    ctx.director_interpret = out
    monkeypatch.setattr(mapping, "search_lore", lambda *a, **k: [])
    compiled = mapping.compile_world_context(ctx, nonce=0)
    needs = compiled["planning_needs"]
    assert needs
    assert any(n["reason"] == "generation_request" and "armory" in n["subject"]
               for n in needs)


def test_a_generation_request_raises_a_need_without_any_movement(temp_db, monkeypatch):
    """Cached recall used to escalate to the full stage here; the compiler
    cannot mint declared content either, so the need is the record."""
    import agents.mapping as mapping

    ctx = _make_ctx(temp_db, "look around")
    ctx.director_interpret = {
        "sequence": [], "movement": None, "location_query": None,
        "flow": {"mapping_request": "", "generation_requests": [
            {"kind": "player_declaration", "subject": "a rifle"}]},
    }
    monkeypatch.setattr(mapping, "search_lore", lambda *a, **k: [])
    result = mapping.compile_world_context(ctx, nonce=0)
    assert [n["subject"] for n in result["planning_needs"]] == ["a rifle"]
    assert result["planning_needs"][0]["kind"] == "thing"
    assert result["planning_needs"][0]["surface"]["declared_kind"] == "player_declaration"
    assert result["staged_lore"] == [] and result["movement"]["status"] is None


def test_the_existing_interpretation_is_never_replaced(temp_db, monkeypatch):
    """The repair ADDS what the interpretation dropped and never rewrites what
    it already had: the wave the weak interpretation carried stays first.
    Called directly since 2026-09-27 -- on the prose path the repair runs only
    on an interpret whose encoder returned no events, where there is nothing
    existing to keep (`docs/UNBUILT_PIPELINE.md` § 1.1, item 3)."""
    from agents.common import norm_sequence

    ctx = _make_ctx(temp_db, INPUT)
    calls = []
    monkeypatch.setattr(director, "_agent_json", _fake_agent(calls, {
        "interpret_repair": _REPAIR}))
    out = json.loads(json.dumps(_WEAK_INTERPRET))
    norm_sequence(out)
    director._reconcile_interpretation(
        ctx, out, {"rooms": {"guard_post": {}, "hallway": {}}})
    recon = out["interpret_reconciliation"]
    assert "interpret_repair" in _steps(calls)
    assert recon["uncovered"] and recon["repaired"] and recon["unresolved"] == []
    attempts = [e.get("attempt") for e in out["sequence"] if e.get("type") == "action"]
    assert attempts[0] == "wave to Mara"
    assert "duck into the armory" in attempts and "grab a rifle" in attempts
    assert out["movement"]["to_room"] == "armory"

