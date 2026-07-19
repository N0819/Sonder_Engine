# scene.py
"""Scene management with entity awareness, genre config, and world state."""

import json, re, random
from db import active_frame_id, q, qi, wget, wset
from spatial import room_of, spatial_rel

_UNSET = object()

from character_schema import (
    character_abilities,
    character_appearance,
    character_initial_active_state,
    character_initial_stance,
    character_name,
    character_opening_context,
    character_private_history,
    character_public_history,
    character_senses,
    normalize_persona_data,
    persona_abilities,
    persona_appearance,
    persona_name,
    persona_private_history,
    persona_public_history,
    persona_senses,
    persona_voice_setting,
    senses_as_text,
)

import re as _re

_NON_ATTIRE_TERMS = {
    "chair", "cushion", "seat", "table", "cup", "mug", "glass",
    "bottle", "book", "weapon", "tool",
}

def sanitize_attire_items(items):
    result = []
    for item in items or []:
        text = str(item).strip()
        lowered = text.casefold()
        if not text:
            continue
        if any(_re.search(rf"\b{_re.escape(term)}\b", lowered) for term in _NON_ATTIRE_TERMS):
            continue
        if text not in result:
            result.append(text)
    return result

def active_cast(chat_id, frame_id=None):
    """frame_id=None (present) reads chat_chars directly, unchanged. A
    real frame LEFT JOINs chat_char_frames and prefers its override when
    one exists for a character -- a character genuinely can be
    simultaneously alive/active in one frame and dead/dormant in
    another; falling back to the base row when no override exists yet
    is what lets a never-touched frame start from a character's
    ordinary baseline instead of nothing."""
    if frame_id is None:
        return q(
            "SELECT ch.*, cc.state AS cstate, cc.status FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id "
            "WHERE cc.chat_id=? AND cc.status='active' ORDER BY ch.id",
            (chat_id,),
        )
    return q(
        "SELECT ch.*, "
        "COALESCE(ccf.state, cc.state) AS cstate, "
        "COALESCE(ccf.status, cc.status) AS status "
        "FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id "
        "LEFT JOIN chat_char_frames ccf "
        "  ON ccf.chat_id=cc.chat_id AND ccf.char_id=cc.char_id AND ccf.frame_id=? "
        "WHERE cc.chat_id=? AND COALESCE(ccf.status, cc.status)='active' "
        "ORDER BY ch.id",
        (frame_id, chat_id),
    )

def set_char_status(chat_id, char_id, status, frame_id=None):
    """Writes to the base chat_chars row when frame_id is None (present,
    unchanged behavior), else UPSERTs the frame-specific override row --
    a status change made while a turn is running in frame F must not
    leak into how the character appears in any other frame."""
    if frame_id is None:
        qi("UPDATE chat_chars SET status=? WHERE chat_id=? AND char_id=?",
           (status, chat_id, char_id))
        return
    qi(
        "INSERT INTO chat_char_frames(chat_id,char_id,frame_id,status,state) "
        "SELECT ?,?,?,?,state FROM chat_chars WHERE chat_id=? AND char_id=? "
        "ON CONFLICT(chat_id,char_id,frame_id) DO UPDATE SET status=excluded.status",
        (chat_id, char_id, frame_id, status, chat_id, char_id),
    )

def set_char_state(chat_id, char_id, state_json, frame_id=None):
    if frame_id is None:
        qi("UPDATE chat_chars SET state=? WHERE chat_id=? AND char_id=?",
           (state_json, chat_id, char_id))
        return
    qi(
        "INSERT INTO chat_char_frames(chat_id,char_id,frame_id,status,state) "
        "SELECT ?,?,?,status,? FROM chat_chars WHERE chat_id=? AND char_id=? "
        "ON CONFLICT(chat_id,char_id,frame_id) DO UPDATE SET state=excluded.state",
        (chat_id, char_id, frame_id, state_json, chat_id, char_id),
    )

def all_cast_name_to_id(chat_id):
    """{character_name: char_id} for EVERY character attached to this
    chat, active or dormant -- unlike active_cast, which intentionally
    excludes dormant rows. Needed wherever a lookup must not silently
    default to "unrecognized" (or worse, "recognized") just because a
    referenced character happens to be dormant right now -- e.g. the
    nonexistent_cast recognition backstop, which must correctly gate a
    dormant not-yet-existing character exactly like an active one."""
    return {
        character_name(json.loads(r["sheet"])): r["char_id"]
        for r in q(
            "SELECT ch.id AS char_id, ch.sheet FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (chat_id,),
        )
    }

def sheet_state(row):
    sheet = json.loads(row["sheet"])
    state = json.loads(row["cstate"] or "{}")
    active = state.get("active_state") or character_initial_active_state(sheet)
    if not isinstance(active, dict):
        active = {"mood": str(active), "goal": ""}
    stance = state.get("stance") or character_initial_stance(sheet)
    if not isinstance(stance, dict):
        stance = {"axes": {}}
    return sheet, active, stance

def persona_of(chat):
    if chat.get("persona_id"):
        row = q("SELECT * FROM personas WHERE id=?", (chat["persona_id"],), one=True)
        if row:
            return normalize_persona_data(json.loads(row["sheet"]))
    return normalize_persona_data({
        "name": "The Stranger",
        "appearance": "A person of unremarkable appearance.",
        "senses": "ordinary senses",
        "abilities": [],
        "public_history": "",
        "voice_setting": "",
        "private_history": [],
    })

def get_scene(chat_id, chat=None):
    sc = wget(chat_id, "scene")
    if not sc:
        sc = {
            "location": "an unspecified place",
            "time": "now",
            "description": (chat or {}).get("scenario") or "",
            "rooms": {},
            "entities": {},
            "positions": {},
            "overlays": {},
            "attire": {},
        }
    for k in ("rooms", "entities", "positions", "overlays", "attire"):
        sc.setdefault(k, {})
    return sc

def appearance_of(name, base, scene):
    ov = (scene.get("overlays") or {}).get(name) or []
    att = (scene.get("attire") or {}).get(name) or {}
    s = base or "no notable appearance recorded"
    if att.get("wearing"):
        s += "; wearing: " + ", ".join(map(str, att["wearing"]))
    if att.get("state"):
        s += "; clothing state: " + ", ".join(map(str, att["state"]))
    if ov:
        s += "; currently: " + "; ".join(map(str, ov))
    return s

def senses_of(sheet):
    if "psychology" in sheet or "core" in sheet:
        return senses_as_text(character_senses(sheet))
    if "narration" in sheet:
        return senses_as_text(persona_senses(sheet))
    return sheet.get("senses") or "ordinary senses"

def name_of(sheet):
    if "psychology" in sheet or "core" in sheet:
        return character_name(sheet)
    return persona_name(sheet)

def base_appearance_of(sheet):
    if "psychology" in sheet or "core" in sheet:
        return character_appearance(sheet)
    return persona_appearance(sheet)

def abilities_of(sheet):
    if "psychology" in sheet or "core" in sheet:
        return character_abilities(sheet)
    return persona_abilities(sheet)

def recent_events(chat_id, n=5, frame_id=_UNSET):
    """Recent narrative beats for the mapping stage's context. Frame-
    filtered (via a join through events.turn_id -> turns.frame_id): a
    concurrently-played OTHER frame's beats must never leak into this
    frame's "what just happened" context -- that's an information-
    boundary leak across frames, not just noise. frame_id defaults to
    whatever frame the CURRENT pipeline run is in (see db.py's
    active_frame_id), matching every other frame-scoped default in this
    codebase; pass it explicitly only from outside a pipeline run."""
    fid = active_frame_id.get() if frame_id is _UNSET else frame_id
    rows = q(
        "SELECT e.content FROM events e "
        "LEFT JOIN turns t ON t.id=e.turn_id "
        "WHERE e.chat_id=? AND (e.turn_id IS NULL OR t.frame_id IS ?) "
        "ORDER BY e.id DESC LIMIT ?",
        (chat_id, fid, n),
    )

    results = []

    for row in reversed(rows):
        try:
            payload = json.loads(row["content"])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue

        if not isinstance(payload, dict):
            continue

        summary = payload.get("summary")
        if isinstance(summary, str):
            summary = summary.strip()
            if summary:
                results.append(summary)

    return results

def director_context(chat_id, n=5, frame_id=_UNSET):
    """Recent turns for the Director/mapping's own context. Frame-
    filtered exactly like recent_events above -- a concurrently-played
    OTHER frame's player declarations and resolved outcomes must never
    leak into this frame's Director, since he interprets/resolves
    causality partly from this history."""
    fid = active_frame_id.get() if frame_id is _UNSET else frame_id
    rows = q(
        "SELECT t.idx,t.player_input,e.content AS ev FROM turns t "
        "LEFT JOIN events e ON e.turn_id=t.id "
        "WHERE t.chat_id=? AND t.frame_id IS ? ORDER BY t.idx DESC LIMIT ?",
        (chat_id, fid, n),
    )
    out = []
    for r in reversed(rows):
        ev = json.loads(r["ev"]) if r["ev"] else {}
        out.append({
            "turn": r["idx"],
            "player_input": r["player_input"],
            "resolved": ev.get("summary") or ev.get("event", ""),
        })
    return out

def salience_of(text):
    s = 0.45 + min(len(text or ""), 400) / 1600.0
    for w in ("attack", "blood", "secret", "betray", "kiss", "dead",
              "weapon", "threat", "love", "steal", "scream", "knife",
              "confess", "liar", "promise"):
        if w in (text or "").lower():
            s += 0.08
    return round(min(s, 0.95), 3)

def _ability_mod(actor, ability, ctx):
    levels = {"novice": 0, "competent": 2, "expert": 4, "master": 6}
    actor_name = str(actor or "").lower().strip()
    ability_name = str(ability or "").lower().strip()
    persona = persona_of(ctx.chat)
    player_aliases = {
        str(persona.get("name", "")).lower().strip(),
        "player", "the player", "you", "pc",
    }
    pools = []
    if actor_name in player_aliases:
        pools.append(persona.get("abilities", []))
    else:
        for row in ctx.cast:
            sheet = json.loads(row["sheet"])
            if name_of(sheet).lower().strip() == actor_name:
                pools.append(abilities_of(sheet))
                break
    for pool in pools:
        for candidate in pool:
            name = str(candidate.get("name", "")).lower().strip()
            if name and ability_name and (name in ability_name or ability_name in name):
                return levels.get(str(candidate.get("level", "")).lower(), 0)
    return 0

def _player_aliases(chat):
    pers = persona_of(chat)
    # persona_of returns the normalized native shape (identity.name nested),
    # not a flat "name" key -- pers.get("name", "") silently returned ""
    # for every real persona and only "worked" for persona_of's hardcoded
    # fallback dict (which happens to be flat), so a chat with a real
    # persona configured had no actual name in its own alias list.
    return [persona_name(pers), "the player", "player", "you", "the protagonist", "PC"]

def is_player_speaker(speaker, chat):
    aliases = [a.lower().strip() for a in _player_aliases(chat) if a]
    s = (speaker or "").lower().strip()
    if s in aliases:
        return True
    s_norm = re.sub(r"[^a-z0-9]", "", s)
    for a in aliases:
        a_norm = re.sub(r"[^a-z0-9]", "", a)
        if s_norm and a_norm and s_norm == a_norm:
            return True
    # A director/character model sometimes attributes a line to just the
    # player's first or last name instead of their full persona name
    # ("Alex" rather than "Alex Chen") -- match that at whole-word
    # boundaries only. The previous arbitrary substring check (s_norm in
    # a_norm or vice versa) misattributed any NPC whose name happened to
    # contain the player's name as a substring -- e.g. an NPC "Alexandra"
    # was silently treated as the player "Alex" speaking, which rewrites
    # her dialogue into the player's own line, drops it from every other
    # observer's view, and gets stored in NPC memories as something the
    # player said.
    if s_norm and len(s_norm) >= 4:
        for a in aliases:
            a_words = {
                re.sub(r"[^a-z0-9]", "", w)
                for w in a.split()
            }
            if s_norm in a_words:
                return True
    return False

DEFAULT_INTERACTION_CONFIG = {
    "style": "natural",
    "min_lines": 0,
    "max_lines": 4,
    "variance": 0.6,
    "autonomy": 50,
    "max_micro_rounds": 4,
    "max_character_calls": 6,
    "max_speakers_per_round": 1,
    "initial_parallel_reactors": 2,
    "max_director_calls": 4,
    "max_perception_calls": 4,
    "allow_npc_initiative": True,
    "allow_npc_to_npc_dialogue": True,
    "stop_on_player_address": True,
    "stop_on_question_to_player": True,
    "silence_ends_exchange": True,
}

DEFAULT_REACTION_CONFIG = {
    "enabled": True,
    "max_reactors": 6,
    "allow_emergency_reactions": True,
    "use_seeded_checks": True,
}

def interaction_limits(autonomy):
    try:
        value = max(0, min(100, int(autonomy)))
    except Exception:
        value = 50
    presets = [
        (0, {"max_micro_rounds": 1, "max_character_calls": 1,
             "max_director_calls": 1, "max_perception_calls": 1}),
        (25, {"max_micro_rounds": 2, "max_character_calls": 3,
              "max_director_calls": 2, "max_perception_calls": 2}),
        (50, {"max_micro_rounds": 4, "max_character_calls": 6,
              "max_director_calls": 4, "max_perception_calls": 4}),
        (75, {"max_micro_rounds": 7, "max_character_calls": 10,
              "max_director_calls": 7, "max_perception_calls": 7}),
        (100, {"max_micro_rounds": 12, "max_character_calls": 18,
               "max_director_calls": 12, "max_perception_calls": 12}),
    ]
    return min(presets, key=lambda item: abs(item[0] - value))[1]

def dialogue_config(chat_id):
    config = dict(DEFAULT_INTERACTION_CONFIG)
    stored = wget(chat_id, "dialogue_config", None) or {}
    config.update(stored)
    derived = interaction_limits(config.get("autonomy", 50))
    for key, value in derived.items():
        if key not in stored:
            config[key] = value
    return config

def reaction_config(chat_id):
    config = dict(DEFAULT_REACTION_CONFIG)
    stored = wget(chat_id, "reaction_config", None) or {}
    config.update(stored)
    return config

def fiction_model(chat_id):
    return wget(chat_id, "fiction_model", None) or {
        "genre": {"primary": "unspecified"},
        "ontology": {},
        "causal_regimes": [],
        "scale_rules": {},
        "abstraction_rules": {},
    }

def simulation_clock(chat_id):
    return wget(chat_id, "simulation_clock", None) or {
        "elapsed_seconds": 0.0,
        "display": "now",
        "time_scale": "scene",
    }

def dialogue_budget(chat, turn, cid, nonce):
    cfg = dialogue_config(chat["id"])
    lo = max(0, int(cfg.get("min_lines", 0)))
    hi = max(lo, int(cfg.get("max_lines", 4)))
    var = min(max(float(cfg.get("variance", 0.6)), 0.0), 1.0)
    style = cfg.get("style", "natural")
    rng = random.Random(f"dlg:{chat['id']}:{turn['idx']}:{cid}:{nonce}")
    if rng.random() < var:
        target = rng.randint(lo, hi)
    else:
        target = min(max(1, round((lo + hi) / 2)), hi)
    return {"style": style, "suggested_lines": target, "hard_max": hi, "may_stay_silent": lo == 0}

def cast_scene_context(cast_rows):
    """Build scene-relevant character dossiers for mapping and director."""
    result = []
    for row in cast_rows:
        sheet = json.loads(row["sheet"])
        identity = sheet.get("identity") or {}
        result.append({
            "id": int(row["id"]),
            "entity_id": identity.get("uid") or f"character:{int(row['id'])}",
            "name": character_name(sheet),
            "aliases": identity.get("aliases") or [],
            "appearance": character_appearance(sheet),
            "senses": senses_as_text(character_senses(sheet)),
            "abilities": character_abilities(sheet),
            "public_history": character_public_history(sheet),
            "opening_context": character_opening_context(sheet),
        })
    return result

def private_knowledge_for(chat, viewer_name, frame_id=None):
    vn = (viewer_name or "").lower().strip()
    out = []
    rows = q(
        "SELECT ch.sheet, "
        "COALESCE(ccf.state, cc.state) AS state "
        "FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id "
        "LEFT JOIN chat_char_frames ccf "
        "  ON ccf.chat_id=cc.chat_id AND ccf.char_id=cc.char_id AND ccf.frame_id IS ? "
        "WHERE cc.chat_id=?",
        (frame_id, chat["id"]),
    )
    for r in rows:
        sh = json.loads(r["sheet"])
        st = json.loads(r["state"] or "{}")
        entries = st.get("private_history")
        if entries is None:
            entries = character_private_history(sh)
        owner = character_name(sh)
        for e in entries:
            if not isinstance(e, dict) or not e.get("content"):
                continue
            kb = [str(x).lower().strip() for x in (e.get("known_by") or [])]
            if owner.lower() == vn:
                out.append({"about": e.get("about") or owner,
                            "content": e["content"],
                            "source": "your own private history"})
            elif vn in kb:
                out.append({"about": e.get("about") or owner,
                            "content": e["content"],
                            "source": f"private knowledge shared by {owner}"})
    pers = persona_of(chat)
    pents = wget(chat["id"], "persona_private_history", None)
    if pents is None:
        pents = persona_private_history(pers)
    for e in pents:
        if isinstance(e, dict) and e.get("content"):
            kb = [str(x).lower().strip() for x in (e.get("known_by") or [])]
            if vn in kb:
                out.append({"about": pers.get("name"),
                            "content": e["content"],
                            "source": "something you privately know about them"})
    return out