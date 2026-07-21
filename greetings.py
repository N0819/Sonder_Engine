"""Greeting-seeded openings: ingest-time greeting interpretation and a
"Start story now" launch. See docs/GREETING_IMPORT_DESIGN.md.

`greeting_interpret` is to a character-card greeting what `director_interpret`
is to player input -- one bounded parse of freeform opening prose into
structured establishment scaffolding -- but run per-card and cached. The
greeting prose itself is always preserved verbatim; the extraction is scaffolding
UNDER it, most importantly the character's PRIVATE knowledge, which routes to
character memory and is never shown to the player.
"""
from __future__ import annotations

import json
import time

import db
from character_schema import (
    character_name, character_appearance, character_public_history, persona_name,
)
from llm_quality import complete_validated_json
from prompts import get_prompt
from memory import add_memory
from agents.runtime import _run_pipeline
from agents.storage import active_content

EXTRACTOR_VERSION = 1
PLAYER_TOKEN = "{{PLAYER}}"


def extract_greeting(sheet: dict, greeting_prose: str) -> dict:
    """One bounded ingest-time call: greeting prose -> establishment seeds.
    Persona-neutral: the {{PLAYER}} token is left symbolic."""
    payload = {
        "character_name": character_name(sheet),
        "character_appearance": character_appearance(sheet),
        "character_public_history": character_public_history(sheet),
        "greeting_prose": greeting_prose,
        "player_token": PLAYER_TOKEN,
    }
    out = complete_validated_json(
        role="greeting_interpret",
        step_key="greeting_interpret",
        system=get_prompt("greeting_interpret"),
        payload=payload,
        temperature=0.2,
    )
    # Deterministic information-boundary guard (never trust the model to tag it
    # right): a "secret" seed that names the player is not actually asymmetric,
    # so it can't be routed as private-from-the-player.
    for seed in out.get("knowledge_seeds") or []:
        if PLAYER_TOKEN in str(seed.get("content", "")):
            seed["revealed_in_prose"] = True
    return out


def _greeting_record(sheet: dict, index: int):
    opening = sheet.get("opening") or {}
    greetings = opening.get("greetings") or []
    if greetings:
        return greetings[max(0, min(index, len(greetings) - 1))]
    fm = opening.get("first_message") or ""
    return {"prose": fm, "extraction": None} if fm else None


def _override_narrator(tid: int, prose: str) -> None:
    """Replace turn 0's narrator prose with the verbatim greeting (a new active
    variant -- mirrors edit_prose). The establishment ran to produce a valid,
    committed turn; this only changes how the opening reads to the player, so no
    step is marked stale."""
    step = db.q("SELECT * FROM steps WHERE turn_id=? AND key='narrator'", (tid,), one=True)
    if not step:
        return
    content = active_content(tid, "narrator") or {}
    content["prose"] = prose
    db.qi("UPDATE variants SET active=0 WHERE step_id=?", (step["id"],))
    db.qi("INSERT INTO variants(step_id,content,created,active) VALUES(?,?,?,1)",
          (step["id"], json.dumps(content, ensure_ascii=False), time.time()))


def start_story(char_id: int, persona_id: int, greeting_index: int = 0) -> tuple[int, int]:
    """'Start story now': create a chat seeded from a character's greeting.
    The greeting is shown verbatim; its private knowledge routes to the
    character. Returns (chat_id, turn_id)."""
    ch = db.q("SELECT * FROM characters WHERE id=?", (char_id,), one=True)
    per = db.q("SELECT * FROM personas WHERE id=?", (persona_id,), one=True)
    if not ch:
        raise ValueError(f"character {char_id} not found")
    if not per:
        raise ValueError(f"persona {persona_id} not found")
    sheet = json.loads(ch["sheet"])
    psheet = json.loads(per["sheet"])
    p_name = persona_name(psheet)
    c_name = character_name(sheet)

    rec = _greeting_record(sheet, greeting_index)
    if not rec or not str(rec.get("prose") or "").strip():
        raise ValueError("character has no greeting to start from")
    prose_tok = rec.get("prose") or ""
    extraction = rec.get("extraction") or extract_greeting(sheet, prose_tok)

    def sub(s):  # deterministic {{PLAYER}} -> persona name
        return str(s or "").replace(PLAYER_TOKEN, p_name)

    prose_final = sub(prose_tok)

    # chat + cast. Scenario = the full (substituted) greeting so establishment
    # builds the scene from the author's opening; recognition is mutual because
    # the greeting is written TO the player.
    cid = db.qi("INSERT INTO chats(name,scenario,created) VALUES(?,?,?)",
                (f"{c_name} — {p_name}", prose_final, time.time()))
    db.qi("UPDATE chats SET persona_id=? WHERE id=?", (persona_id, cid))
    db.qi("INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?, 'active')", (cid, char_id))
    db.wset(cid, "known", {c_name: [p_name], p_name: [c_name]})
    db.wset(cid, "fiction_model", {"genre": {"primary": "as written in the card"},
                                   "ontology": {}, "causal_regimes": [],
                                   "scale_rules": {}, "abstraction_rules": {}})
    db.wset(cid, "simulation_clock", {"elapsed_seconds": 0.0,
                                      "display": sub(extraction.get("time") or "now"),
                                      "time_scale": "scene"})

    # Route the character's private knowledge to character memory. Memories are
    # per-character and never enter the player's perception, so an
    # unrevealed-in-prose seed is knowledge the character has and the player
    # does not -- the whole point of the extraction.
    for seed in extraction.get("knowledge_seeds") or []:
        content = sub(seed.get("content") or "").strip()
        if not content:
            continue
        try:
            add_memory(cid, char_id, None, "episode", "remembered",
                       float(seed.get("salience", 0.6) or 0.6), content, turn_idx=0)
        except Exception:
            pass  # a bad seed must not abort the launch

    # Turn 0: run establishment (valid, committed), then show the greeting verbatim.
    tid = db.qi("INSERT INTO turns(chat_id,idx,player_input,created,frame_id) VALUES(?,?,?,?,?)",
                (cid, 0, "", time.time(), None))
    list(_run_pipeline(cid, tid))
    _override_narrator(tid, prose_final)
    return cid, tid
