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
    for k in ("rooms", "entities", "positions", "overlays", "attire", "orientation"):
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


# ---- Physical disguise (appearance concealment) ----
# A `physical_disguise` condition (written by director_resolve, persisted in
# world_conditions) conceals a subject's real APPEARANCE from observers who
# don't already know the truth. Nothing consumed it before -- perception kept
# rendering the true appearance, so a concealed feature was still perceived
# (a kitsune's hidden fox ears shown to a guard she is passing herself off to).
# These helpers are the consumer. The disguise conceals appearance only, never
# capability (concealed fox ears still hear) -- perception must preserve the
# subject's real senses.

def active_disguises(chat_id):
    """Active physical_disguise conditions for `chat_id`, keyed by casefolded
    subject name. Each value: {subject, description, presented_appearance,
    concealed_terms, known_to}. Legacy conditions carry only a freeform
    `description`; newer ones (see the director prompt) also carry a positive
    `presented_appearance` (what an unaware observer sees), `concealed_terms`
    (feature words to keep out of unaware views / to tripwire on), and
    `known_to` (observers who legitimately know the real form)."""
    out = {}
    for row in q(
        "SELECT subject_id, payload FROM world_conditions WHERE chat_id=? "
        "AND kind='physical_disguise' AND active=1", (chat_id,),
    ):
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            payload = {}
        subject = str(payload.get("subject_id") or row["subject_id"] or "").strip()
        if not subject:
            continue
        state = payload.get("state") or {}
        pick = lambda k: state.get(k) or payload.get(k)
        out[subject.casefold()] = {
            "subject": subject,
            "description": str(pick("description") or "").strip(),
            "presented_appearance": str(pick("presented_appearance") or "").strip(),
            "concealed_terms": [str(t).strip() for t in (pick("concealed_terms") or [])
                                if str(t).strip()],
            "known_to": [str(n).strip() for n in (pick("known_to") or []) if str(n).strip()],
        }
    return out


def disguised_visible_appearance(true_appearance, disguise):
    """What is VISIBLY perceived of a disguised subject -- by every observer,
    including one who knows the truth (a concealed feature is not seen even by
    someone who knows it's there). Prefers the director-authored positive
    `presented_appearance`. Falls back to stripping `concealed_terms` from the
    true appearance when they're provided; and, when neither is available
    (legacy conditions), returns a deliberately generic label rather than the
    true appearance -- an information barrier must fail toward concealment, so
    a leaky-but-detailed description is never the fallback."""
    presented = (disguise or {}).get("presented_appearance")
    if presented:
        return presented
    terms = (disguise or {}).get("concealed_terms") or []
    if terms and true_appearance:
        scrubbed = true_appearance
        matched = False
        for t in terms:
            scrubbed, n = re.subn(rf"\b{re.escape(t)}\b", "", scrubbed, flags=re.IGNORECASE)
            matched = matched or bool(n)
        # Collapse the punctuation/space debris a removal leaves behind.
        scrubbed = re.sub(r"\s*[;,]\s*(?=[;,])", "", scrubbed)
        scrubbed = re.sub(r"\s{2,}", " ", scrubbed).strip(" ;,")
        # If no term actually matched the text (e.g. "tail" vs "tails"),
        # scrubbed is the unmodified TRUE appearance -- returning it would
        # leak the concealed form. Fail toward concealment instead.
        if matched and scrubbed:
            return scrubbed
    return "a person whose appearance is unremarkable"


def disguise_known_to(disguise, subject_name, known_map):
    """Casefolded names that legitimately KNOW the concealed truth: the subject
    themselves, anyone the director listed in the condition's `known_to`, and --
    only as a backstop for legacy conditions with no explicit list -- observers
    who already know the subject's identity (`known` map), a reasonable proxy
    for 'was present for / close enough to know the real form'. Everyone else
    is unaware and perceives only the disguised outward form."""
    who = {str(subject_name or "").casefold()}
    listed = (disguise or {}).get("known_to") or []
    for n in listed:
        who.add(str(n).strip().casefold())
    if not listed:
        subj_cf = str(subject_name or "").casefold()
        for observer, knows in (known_map or {}).items():
            if any(subj_cf == str(k).casefold() for k in (knows or [])):
                who.add(str(observer).casefold())
    return who

# --- Consciousness / awareness (world_conditions kind 'awareness') ----------
# A director-authored condition, read at perception and planning time exactly
# like physical_disguise above. It gates the RECEIVER (an unconscious mind
# integrates no channel into scene/identity/words), where disguise/senses gate
# CHANNELS. Absent condition => awake (fail-open): the vast majority of turns
# carry no awareness condition, so their behavior is byte-identical to before.

# Ordered fully-present -> absent. "awake" is the implicit default.
AWARENESS_LEVELS = ("awake", "dazed", "asleep", "sedated", "unconscious")
# Levels at which a mind no longer integrates sensory input and takes no
# in-character action -- perception delivers only a content-free residue and
# the planner runs no character step. "dazed" is NOT gated: a dazed mind is
# present but degraded (rendered via the existing periphery rules).
NON_AWAKE_GATED = frozenset({"asleep", "sedated", "unconscious"})


def _normalize_awareness_level(raw):
    """Casefold a level string to the enum. Unknown/garbage degrades to the
    MILDEST gate ('dazed') rather than vanishing; empty/awake -> 'awake'."""
    level = str(raw or "").strip().casefold()
    if level == "" or level == "awake":
        return "awake"
    if level not in AWARENESS_LEVELS:
        return "dazed"
    return level


def awareness_map(chat_id):
    """Active `awareness` conditions for chat_id, keyed by casefolded subject
    name -> {subject, level, cause, rousable_by}. Mirrors active_disguises.
    Only non-awake subjects appear; everyone else is awake by absence."""
    out = {}
    for row in q(
        "SELECT subject_id, payload FROM world_conditions WHERE chat_id=? "
        "AND kind='awareness' AND active=1", (chat_id,),
    ):
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            payload = {}
        subject = str(payload.get("subject_id") or row["subject_id"] or "").strip()
        if not subject:
            continue
        state = payload.get("state") or {}
        level = _normalize_awareness_level(state.get("level") or payload.get("level"))
        if level == "awake":
            continue
        out[subject.casefold()] = {
            "subject": subject,
            "level": level,
            "cause": str(state.get("cause") or payload.get("cause") or "").strip(),
            "rousable_by": str(state.get("rousable_by") or "").strip(),
        }
    return out


def apply_awareness_diff(amap, diff):
    """Overlay a not-yet-committed state_diff's awareness conditions onto a
    committed awareness_map, so a knockout resolved THIS beat gates the outcome
    view of the same beat (perception_outcome runs pre-commit). Returns a copy;
    deactivation / waking this beat removes the subject."""
    out = dict(amap or {})
    for _cid, cond_list in ((diff or {}).get("conditions") or {}).items():
        if not isinstance(cond_list, list):
            cond_list = [cond_list]
        for cond in cond_list:
            if not isinstance(cond, dict) or cond.get("kind") != "awareness":
                continue
            subj = str(cond.get("subject_id") or "").strip()
            if not subj:
                continue
            key = subj.casefold()
            state = cond.get("state") or {}
            level = _normalize_awareness_level(state.get("level"))
            if not int(cond.get("active", 1)) or level == "awake":
                out.pop(key, None)  # woke / condition ended this beat
                continue
            out[key] = {"subject": subj, "level": level,
                        "cause": str(state.get("cause") or "").strip(),
                        "rousable_by": str(state.get("rousable_by") or "").strip()}
    return out


def awareness_of(chat_id_or_map, name):
    """Awareness level of `name` -- 'awake' when no active gating condition
    exists (fail-open). Accepts a chat_id (queries) or a prebuilt awareness_map
    (avoids re-querying per perceiver)."""
    amap = chat_id_or_map if isinstance(chat_id_or_map, dict) else awareness_map(chat_id_or_map)
    entry = amap.get(str(name or "").casefold())
    return entry["level"] if entry else "awake"


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
        # Guarded like recent_events above -- one corrupt events row must
        # not wedge every subsequent director_interpret/mapping stage.
        try:
            ev = json.loads(r["ev"]) if r["ev"] else {}
        except (TypeError, ValueError):
            ev = {}
        if not isinstance(ev, dict):
            ev = {}
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
    # persona_of returns the normalized native shape (identity.name /
    # competence.abilities nested) -- flat persona.get("name"/"abilities")
    # always returned ""/[] here (see _player_aliases below for the same
    # trap), so the player's real name never matched and their ability
    # pool was always empty. Also drop the empty string so a blank actor
    # name can't false-match as the player.
    alias = persona_name(persona).lower().strip()
    player_aliases = {a for a in (alias, "player", "the player", "you", "pc") if a}
    pools = []
    if actor_name in player_aliases:
        pools.append(persona_abilities(persona))
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

def background_config(chat_id):
    """Config for the background_react stage. `max_reactors` bounds how many
    unregistered presences may voice a single beat (default 1 -- the historical
    single-winner behavior; raise to stage ensemble beats). Hard-capped at 3 in
    background_react: past that, a crowd is better represented as one chorus
    presence than as several individually-voiced extras.
    """
    config = {"max_reactors": 1}
    stored = wget(chat_id, "background_config", None) or {}
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
                out.append({"about": persona_name(pers),
                            "content": e["content"],
                            "source": "something you privately know about them"})
    return out