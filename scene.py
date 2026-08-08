# scene.py
"""Scene management with entity awareness, genre config, and world state."""

import json, re, random
from db import active_frame_id, q, qi, wget, wset
from spatial import room_of, spatial_rel

_UNSET = object()

from character_schema import (
    cast_entity_id,
    character_abilities,
    character_appearance,
    character_initial_outfit,
    character_initial_active_state,
    character_initial_stance,
    character_name,
    character_name_from_text,
    character_opening_context,
    character_private_history,
    character_public_history,
    character_senses,
    normalize_persona_data,
    persona_abilities,
    persona_appearance,
    persona_initial_outfit,
    persona_name,
    persona_private_history,
    persona_public_history,
    persona_senses,
    persona_voice_setting,
    senses_as_text,
)

import re as _re

import attire as attire_model

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


def seed_initial_attire(scene, name, outfit):
    """Seed one body's authored starting clothes without resetting live state.

    This is where the card's two representations become one. Authored regions
    are taken as written; the flat `wearing` list is sorted into whatever
    regions they left unclaimed. The merge happens HERE rather than in the card
    so a cue-table guess is never written back to something an author reads as
    their own choice -- see `character_schema._normalize_initial_outfit`.
    """
    if not isinstance(scene, dict) or not str(name or "").strip():
        return False
    ledger = scene.setdefault("attire", {})
    if name in ledger:
        return False
    outfit = outfit if isinstance(outfit, dict) else {}
    wearing = sanitize_attire_items(outfit.get("wearing") or [])
    state = [
        str(item).strip() for item in (outfit.get("state") or [])
        if str(item or "").strip()
    ]
    entry = attire_model.authored_entry(wearing, state, outfit.get("regions"))
    if not any(entry.values()):
        return False
    ledger[name] = entry
    return True


def _seed_scene_initial_attire(chat_id, scene, chat=None):
    """Seed initial outfits exactly when a scene is first materialized."""
    chat_row = None
    if chat is not None:
        chat_row = {
            key: _chat_field(chat, key)
            for key in (
                "id", "name", "persona_id", "lorebook_id", "scenario",
                "created",
            )
        }
    if chat_row is None:
        row = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
        chat_row = dict(row) if row else {}

    persona = persona_of(chat_row)
    seed_initial_attire(
        scene, persona_name(persona), persona_initial_outfit(persona))
    for row in active_cast(chat_id):
        sheet = json.loads(row["sheet"])
        seed_initial_attire(
            scene, character_name(sheet), character_initial_outfit(sheet))
    for row in q(
        "SELECT p.sheet FROM chat_personas cp "
        "JOIN personas p ON p.id=cp.persona_id "
        "WHERE cp.chat_id=? AND cp.status='active'",
        (chat_id,),
    ):
        sheet = json.loads(row["sheet"] or "{}")
        seed_initial_attire(
            scene, persona_name(sheet), persona_initial_outfit(sheet))

# A character can be absent from a scene without ceasing to exist in the story,
# and `chat_chars.status` was answering both questions with one word. Three
# questions were being asked of it:
#
#   (a) does this person exist in this chat's world?   -- the roster question
#   (b) are they in the current scene?                  -- the perception question
#   (c) should the engine spend a model call on them?   -- the animation question
#
# `active_cast` answers (b) and (c) correctly and was being read as an answer
# to (a) as well. What that cost: a dormant character fell out of
# `_known_name_roster`, so an introduction naming them was silently dropped and
# the guard that stops a registered character being puppeted as background
# furniture stopped covering exactly the people most likely to be furniture.
# Measured on a live chat: four `ok` introductions emitted on one turn, one
# survived -- the only pair where both names were active.
#
# DEPARTED is the real answer to (a). Nothing writes it yet; `dormant` rows
# predate the distinction and are read as extant, which is the safe direction:
# a departed character wrongly nameable is a continuity oddity, a present
# character wrongly unnameable is the defect above.
DEPARTED_STATUSES = ("departed",)


def extant_cast(chat_id, frame_id=None):
    """Everyone this chat's world still contains, present or not.

    NOT the cast to animate and NOT the cast to place in a room -- that is
    `active_cast`, which is deliberately untouched. This answers only "is this
    a person the story knows about", which is what name resolution, the
    recognition map and the anti-furniture guard actually need.
    """
    placeholders = ",".join("?" * len(DEPARTED_STATUSES))
    return q(
        "SELECT ch.id,ch.name,COALESCE(cc.sheet,ch.sheet) AS sheet,"
        "ch.source,ch.created,ch.resource_uid,"
        "cc.state AS cstate,cc.status "
        "FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id "
        f"WHERE cc.chat_id=? AND cc.status NOT IN ({placeholders}) "
        "ORDER BY ch.id",
        (chat_id, *DEPARTED_STATUSES),
    )


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
            "SELECT ch.id,ch.name,COALESCE(cc.sheet,ch.sheet) AS sheet,"
            "ch.source,ch.created,ch.resource_uid,"
            "cc.state AS cstate,cc.status "
            "FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id "
            "WHERE cc.chat_id=? AND cc.status='active' ORDER BY ch.id",
            (chat_id,),
        )
    return q(
        "SELECT ch.id,ch.name,COALESCE(cc.sheet,ch.sheet) AS sheet,"
        "ch.source,ch.created,ch.resource_uid,"
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


def chat_character_sheet(chat_id, char_id):
    """The authored card effective in one story, or None if not attached."""
    row = q(
        "SELECT COALESCE(cc.sheet,ch.sheet) AS sheet "
        "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        "WHERE cc.chat_id=? AND cc.char_id=?",
        (chat_id, char_id), one=True,
    )
    if not row:
        return None
    try:
        return json.loads(row["sheet"] or "{}")
    except (TypeError, ValueError):
        return {}


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
        character_name_from_text(r["sheet"]): r["char_id"]
        for r in q(
            "SELECT ch.id AS char_id,COALESCE(cc.sheet,ch.sheet) AS sheet "
            "FROM chat_chars cc "
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

def _chat_field(chat, field):
    """One accessor for a chat passed as either a dict or a sqlite3.Row.

    Row has no .get, so `(chat or {}).get(field)` raised AttributeError on the
    no-scene path for every caller that passed the row straight from `q()` --
    which is what the app's own scene-reading routes do.
    """
    if chat is None:
        return None
    try:
        return chat[field]
    except (KeyError, IndexError, TypeError):
        return None


def get_scene(chat_id, chat=None):
    sc = wget(chat_id, "scene")
    created = not sc
    if not sc:
        sc = {
            "location": "an unspecified place",
            "time": "now",
            "description": _chat_field(chat, "scenario") or "",
            "rooms": {},
            "entities": {},
            "positions": {},
            "overlays": {},
            "attire": {},
        }
    for k in ("rooms", "entities", "positions", "overlays", "attire", "orientation"):
        sc.setdefault(k, {})
    # Body position tracking. A list, not a dict: a contact is a relation and is
    # stored once rather than on either body (spatial.normalize_scene_contacts).
    sc.setdefault("contacts", [])
    # Scale: {name: factor relative to that body's own baseline}. Absent or 1.0
    # is normal size, so a scene that never mentions size behaves as before.
    sc.setdefault("scales", {})
    # Containment: who is being carried by what. A contained body's position is
    # derived from its container's, so it cannot walk off on its own.
    sc.setdefault("contained", {})
    # `vitals` is deliberately NOT defaulted: its absence is what tells the
    # engine survival tracking is off for this story (survival.py).
    if created:
        _seed_scene_initial_attire(chat_id, sc, chat)
    return sc

def appearance_of(name, base, scene):
    ov = (scene.get("overlays") or {}).get(name) or []
    att = (scene.get("attire") or {}).get(name) or {}
    # Same reason as `agents.common.attire_view`: read the ledger through its
    # own normalisation rather than off the stored dict, or a stale or
    # malformed flat list reaches every observer of this body verbatim. This
    # is the string other characters are told, so a garment named "worn" here
    # is a garment they can see.
    if att:
        att = attire_model.rederive_entry(att)
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

def _condition_state(condition):
    """Return structured state, tolerating malformed legacy condition rows."""
    state = condition.get("state") if isinstance(condition, dict) else None
    return state if isinstance(state, dict) else {}

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
        state = _condition_state(payload)
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


def awareness_conditions(chat_id):
    """EVERY active non-awake `awareness` condition row, in id order.

    `awareness_map` below collapses these to one record per subject, which is
    right for asking "is this mind present?" and wrong for ENDING the state: a
    subject can carry several active rows at once (live: chat 23 'Elevator
    Adventure' holds two `unconscious` and one `dazed` on the same person), and
    waking them means deactivating all of them. A caller that ends only the one
    the map surfaced leaves the others in force. Each record carries its
    `condition_id` and raw `payload` so the ending can be re-emitted as the SAME
    condition (commit UPDATEs by condition_id; a fresh id would INSERT a second
    row instead of closing the first)."""
    rows = []
    for row in q(
        "SELECT condition_id, subject_id, payload, started_at FROM world_conditions "
        "WHERE chat_id=? AND kind='awareness' AND active=1 ORDER BY rowid",
        (chat_id,),
    ):
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        subject = str(payload.get("subject_id") or row["subject_id"] or "").strip()
        if not subject:
            continue
        state = _condition_state(payload)
        level = _normalize_awareness_level(state.get("level") or payload.get("level"))
        if level == "awake":
            continue
        try:
            started = float(payload.get("started_at_seconds")
                            if payload.get("started_at_seconds") is not None
                            else row["started_at"] or 0.0)
        except (TypeError, ValueError):
            started = 0.0
        rows.append({
            "condition_id": str(row["condition_id"]),
            "subject": subject,
            "level": level,
            "cause": str(state.get("cause") or payload.get("cause") or "").strip(),
            "rousable_by": str(state.get("rousable_by") or "").strip(),
            "started_at_seconds": started,
            "payload": payload,
        })
    return rows


def awareness_map(chat_id):
    """Active `awareness` conditions for chat_id, keyed by casefolded subject
    name -> {subject, level, cause, rousable_by, condition_id}. Mirrors
    active_disguises. Only non-awake subjects appear; everyone else is awake by
    absence. Several rows may name one subject; the last wins, unchanged --
    `awareness_conditions` is the un-collapsed view."""
    out = {}
    for record in awareness_conditions(chat_id):
        out[record["subject"].casefold()] = {
            "subject": record["subject"],
            "level": record["level"],
            "cause": record["cause"],
            "rousable_by": record["rousable_by"],
            "condition_id": record["condition_id"],
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
            state = _condition_state(cond)
            level = _normalize_awareness_level(state.get("level"))
            if not int(cond.get("active", 1)) or level == "awake":
                out.pop(key, None)  # woke / condition ended this beat
                continue
            out[key] = {"subject": subj, "level": level,
                        "cause": str(state.get("cause") or "").strip(),
                        "rousable_by": str(state.get("rousable_by") or "").strip()}
    return out


# --- Restraint (world_conditions kind 'restraint') --------------------------
# The tripwire that DETECTS un-recorded restraint in prose has existed since
# the omission audit (director._untracked_restraint_subjects). Nothing ever
# read the condition it asks for, so a character recorded as bound hand and
# foot could still walk across the room -- the state was written, believed by
# nobody, and enforced nowhere.
#
# Unlike awareness, restraint does NOT gate perception or speech: a bound
# person sees everything and can talk. What it gates is the body. So the
# enforcement is deliberately narrow and mechanical -- they cannot leave the
# room they are held in -- and everything subtler is handed to the Director as
# ground truth to resolve against.
RESTRAINT_LEVELS = ("held", "bound", "pinned", "encased")
# Levels at which a body cannot relocate itself. All of them: "held" is the
# mildest and still means someone else has you.
IMMOBILIZING_RESTRAINTS = frozenset(RESTRAINT_LEVELS)


def _normalize_restraint_level(raw):
    level = str(raw or "").strip().casefold()
    if not level:
        return "bound"
    if level in RESTRAINT_LEVELS:
        return level
    # Unknown wording degrades to the MILDEST real restraint rather than
    # vanishing, matching how awareness treats an unrecognized level.
    return "held"


def restraint_map(chat_id):
    """Active `restraint` conditions, keyed casefolded subject -> record.

    Mirrors awareness_map. Only restrained subjects appear; everyone else is
    free by absence, so a chat that never restrains anyone is untouched.
    """
    out = {}
    for row in q(
        "SELECT subject_id, payload FROM world_conditions WHERE chat_id=? "
        "AND kind='restraint' AND active=1", (chat_id,),
    ):
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            payload = {}
        state = _condition_state(payload)
        subject = str(payload.get("subject_id") or row["subject_id"] or "").strip()
        if not subject:
            continue
        out[subject.casefold()] = {
            "subject": subject,
            "level": _normalize_restraint_level(state.get("level")),
            "by": str(state.get("by") or "").strip(),
            "means": str(state.get("means") or "").strip(),
            "escapable_by": str(state.get("escapable_by") or "").strip(),
        }
    return out


def apply_restraint_diff(rmap, diff):
    """Overlay a not-yet-committed diff's restraint conditions, so a binding
    that happens THIS beat is in force for the same beat's resolution."""
    out = dict(rmap or {})
    for _cid, cond_list in ((diff or {}).get("conditions") or {}).items():
        if not isinstance(cond_list, list):
            cond_list = [cond_list]
        for cond in cond_list:
            if not isinstance(cond, dict) or cond.get("kind") != "restraint":
                continue
            subject = str(cond.get("subject_id") or "").strip()
            if not subject:
                continue
            key = subject.casefold()
            state = _condition_state(cond)
            if not int(cond.get("active", 1)):
                out.pop(key, None)          # released this beat
                continue
            out[key] = {
                "subject": subject,
                "level": _normalize_restraint_level(state.get("level")),
                "by": str(state.get("by") or "").strip(),
                "means": str(state.get("means") or "").strip(),
                "escapable_by": str(state.get("escapable_by") or "").strip(),
            }
    return out


def restraint_of(chat_id_or_map, name):
    """The restraint record for `name`, or None when free (fail-open)."""
    rmap = chat_id_or_map if isinstance(chat_id_or_map, dict) \
        else restraint_map(chat_id_or_map)
    return rmap.get(str(name or "").casefold())


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
    """Recent narrative beats for the mapping stages' lore query. Frame-
    filtered (via a join through events.turn_id -> turns.frame_id): a
    concurrently-played OTHER frame's beats must never leak into this
    frame's "what just happened" context -- that's an information-
    boundary leak across frames, not just noise. frame_id defaults to
    whatever frame the CURRENT pipeline run is in (see db.py's
    active_frame_id), matching every other frame-scoped default in this
    codebase; pass it explicitly only from outside a pipeline run.

    Concealment-scrubbed, because its callers are not entitled to the
    omniscient row (audit X18). Both of them -- mapping_stage and
    mapping_quick -- feed these strings straight into search_lore, and what
    that retrieval selects becomes a lore entry or a scene_patch room note
    served in every perceiver's payload. A concealed whisper steering that
    selection is the middle hop of the laundering chain, so it is redacted
    here rather than at the far end. Mapping is nobody's vantage, hence the
    None observer below: no mind, no entitlement.
    """
    return recent_events_for_observer(chat_id, None, n=n, frame_id=frame_id)


def _concealed_entries(dialogue_log, observer_cf):
    """The concealed dialogue entries `observer_cf` is not entitled to, in the
    shape `_redact_concealed_from_event` expects.

    `observer_cf` is a casefolded name, or None for a caller with no vantage at
    all (a routing stage, the mapping context) -- for which EVERY concealed
    entry counts, since a stage that is nobody has no claim on any of it.
    """
    out = []
    for d in (dialogue_log or []):
        if not isinstance(d, dict):
            continue
        if str(d.get("visibility") or "").casefold() != "concealed":
            continue
        cf = [str(c).casefold() for c in (d.get("conceal_from") or [])]
        if observer_cf is None or not cf or observer_cf in cf:
            out.append({
                "actor": d.get("speaker", ""),
                "attempt": d.get("exact_quote", ""),
                "conceal_from": d.get("conceal_from") or [],
            })
    return out


def _redact_for_observer(text, concealed):
    """Re-apply perception's concealed-action redaction to stored prose.

    Imported lazily because agents.perception imports this module. Fails
    CLOSED: if the redactor cannot run, the beat is withheld rather than
    replayed raw, since the entire premise of this path is that the stored
    text is omniscient.
    """
    try:
        from agents.perception import _redact_concealed_from_event
        return _redact_concealed_from_event(text, concealed)
    except Exception:
        return "[Some parts of the event are not perceptible to you.]"


def recent_events_for_observer(chat_id, observer_name, n=5, frame_id=_UNSET):
    """``recent_events`` narrowed to what one mind is entitled to (Pattern 4).

    The stored events row is omniscient: commit persists the resolved event
    together with the FULL dialogue_log, concealed entries included, because
    that row is the author/audit trail. Anything replaying it into a model
    context has to re-apply concealment first, which is what this does.

    ``observer_name`` is the mind the text is destined for; entries concealed
    from it, plus entries concealed from everyone (empty ``conceal_from``),
    are redacted out. Pass None for a stage that is nobody -- lore routing,
    retrieval queries -- and EVERY concealed entry is redacted: a stage with
    no vantage has no claim on concealed content, so the per-observer test
    would be answering the wrong question.

    Redaction is applied to the SUMMARY. The first version of this redacted
    ``payload["event"]`` and then returned ``payload["summary"] or
    event_text``; commit writes a summary on every real events row, so the
    redacted text was always thrown away and the function was a no-op in
    production. The summary is the Director's own prose written from the
    omniscient frame -- exactly as leaky as ``event`` -- so it gets exactly
    the same treatment. There is deliberately no ``event`` fallback: falling
    back would replace a dropped summary with MORE omniscient prose, and it
    would break the summary-only contract ``recent_events`` is tested
    against (a row with no usable summary is dropped, not backfilled).
    """
    fid = active_frame_id.get() if frame_id is _UNSET else frame_id
    rows = q(
        "SELECT e.content FROM events e "
        "LEFT JOIN turns t ON t.id=e.turn_id "
        "WHERE e.chat_id=? AND (e.turn_id IS NULL OR t.frame_id IS ?) "
        "ORDER BY e.id DESC LIMIT ?",
        (chat_id, fid, n),
    )
    observer_cf = str(observer_name).casefold() if observer_name else None
    results = []

    for row in reversed(rows):
        try:
            payload = json.loads(row["content"])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        summary = payload.get("summary")
        if not isinstance(summary, str):
            continue
        summary = summary.strip()
        if not summary:
            continue

        concealed_for_observer = _concealed_entries(
            payload.get("dialogue_log"), observer_cf)
        if concealed_for_observer:
            summary = _redact_for_observer(summary, concealed_for_observer).strip()
        if summary:
            results.append(summary)

    return results

def director_context(chat_id, n=5, frame_id=_UNSET, *, entitled=True):
    """Recent turns for the Director/mapping's own context. Frame-
    filtered exactly like recent_events above -- a concurrently-played
    OTHER frame's player declarations and resolved outcomes must never
    leak into this frame's Director, since he interprets/resolves
    causality partly from this history.

    `entitled` is the audit-X18 gate. The Director genuinely is entitled to
    the omniscient record -- it owns objective causality, and withholding a
    concealed act from it would make it resolve a beat it cannot see. Mapping
    is NOT: it reads the same history and emits lore entries and scene_patch
    room notes, and `room_notes` is served into every perceiver's payload. That
    is the laundering chain the audit traced -- concealed whisper -> resolved
    event -> events row -> next turn's mapping context -> lore/room note ->
    everyone -- with two model hops and, until now, no deterministic guard on
    the middle one.

    So an unentitled caller gets the concealment-scrubbed resolved text, and
    gets no `player_input` at all for a turn that carried concealed player
    speech: the raw declaration is the player's own words, which is precisely
    where the concealed line appears verbatim, unscrubbed by anything that
    happened downstream of it.
    """
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
        resolved = ev.get("summary") or ev.get("event", "")
        player_input = r["player_input"]
        if not entitled:
            concealed = _concealed_entries(ev.get("dialogue_log"), None)
            if concealed:
                resolved = _redact_for_observer(resolved, concealed)
                player_input = ""
        out.append({
            "turn": r["idx"],
            "player_input": player_input,
            "resolved": resolved,
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

# What the cast is allowed to do while nobody is looking, as a ceiling for the
# whole chat.
#
# The rungs are `schemas.BehaviorController`'s, unchanged and in its order.
# That enum and `docs/OFFSCREEN_LIFE_DESIGN.md` have specified this ladder
# since before anything read either -- the document's step 2 is "wire
# BehaviorController; nothing ticks yet, the ladder just becomes real and
# settable" -- so inventing a second, friendlier vocabulary here would have
# produced two spellings of one idea that diverge and then disagree. The enum
# is per-CHARACTER; this is the chat-level ceiling over it, which is why the
# same names are the right names.
#
# A CEILING, not an instruction. Nothing is obliged to act at any level; the
# level says what is permitted, and the engine still spends nothing on a beat
# that earns nothing. That is the architecture's cost thesis and this setting
# does not get to break it: cost scales with dramatic density, not story
# length, so turn 2000 in a quiet room must still cost what turn 2 cost.
#
# Ordered, so a level permits everything below it:
#
#   inert            Nothing happens off screen. A dormant character is exactly
#                    where you left them, and any gap is generated at
#                    re-contact or not at all. Free.
#   deterministic    Scheduled effects only -- timed arrivals, expiry, dock
#                    edges, news latency. This is `mechanics.py`: built, always
#                    running, and free. The rung names the floor.
#   reactive         The above, plus responding to triggers that fire, with no
#                    autonomous plan. NOT BUILT -- currently behaves as
#                    `deterministic`.
#   stochastic       The above, plus seeded ticks for dormant actors at scene
#                    boundaries, bounded by `max_offscreen_actors` and written
#                    to `offscreen_log`. One sentence each, no plan, no world
#                    writes, no memory.
#
#                    This is the DEFAULT because it is what the engine did
#                    unconditionally before the setting existed: turning a
#                    setting on must not silently change a running story.
#                    As of the background-life work it is the rung the design
#                    document actually specified: a seeded draw against
#                    standing intentions with NO model call
#                    (`offscreen.stochastic_ticks` — same seed, same ticks,
#                    replayable). The earlier shipped behaviour was a prose
#                    sketch riding the mapping_commit model call whose
#                    `tick_seed` no RNG ever consumed; that divergence was
#                    recorded in `docs/UNBUILT.md` §2.8 and is now closed.
#                    This level also permits the out-of-band PROFILE ticks
#                    (`offscreen.schedule_profile_ticks`): one bounded model
#                    call for the few subjects importance x distance scores
#                    medium, structurally unable to commit a consequence —
#                    the same contract this rung's model ticks always had,
#                    now bounded by spend instead of by cast size.
#   character_agent  The above, plus real agent ticks advancing a plan and
#                    writing consequences into the world record -- the villain
#                    with a clock you can fail to beat.
#
#                    **Permission, not behaviour.** Nothing ticks a plan today;
#                    the rung is the gate steps 3-4 of
#                    `docs/OFFSCREEN_LIFE_DESIGN.md` land behind, so that when
#                    they do land they are opt-in on a chat that already asked
#                    rather than a surprise in every running story. It
#                    currently behaves as `stochastic`. Do not add behaviour to
#                    it without the knowledge firewall that document's decision
#                    2 insists on: a ticking character advances on ITS OWN
#                    knowledge, never the player's location or recent actions,
#                    or the result is the spookily prescient antagonist this
#                    architecture exists to avoid.
#
# This ladder is the ONE authority ceiling for everything off screen, the
# living-world mechanisms included: `living_world.LIVING_WORLD_REQUIRES`
# maps each mechanism depth to the rung it spends at, and
# `living_world.effective_depth` clamps to it at read time — so `inert`
# genuinely means nothing happens, rather than "nothing except whatever a
# second dropdown separately permitted".
OFFSCREEN_LIFE_LADDER = (
    "inert", "deterministic", "reactive", "stochastic", "character_agent",
)

# The rung the engine behaved as before the setting existed.
OFFSCREEN_LIFE_DEFAULT = "stochastic"

OFFSCREEN_LIFE_DESCRIPTIONS = {
    "inert": "Nothing happens off screen",
    "deterministic": "Scheduled effects only — arrivals, expiry, news latency",
    "reactive": "…plus responding to triggers, no plans (not built yet)",
    "stochastic": "…plus seeded ticks for dormant actors at scene changes",
    "character_agent": "…plus characters advancing their own plans (not built yet)",
}

# Which rungs actually do something today, for the UI to mark. Kept beside the
# ladder rather than in the UI so an unbuilt rung cannot quietly start reading
# as built when it ships and nobody updates the menu.
OFFSCREEN_LIFE_BUILT = frozenset({"inert", "deterministic", "stochastic"})


def normalize_offscreen_life(value):
    """Coerce a stored or submitted level to a rung, defaulting to the default.

    Unknown values fall to the DEFAULT rather than to the floor. A typo must
    not silently turn a story's off-screen life off — that is the failure this
    codebase keeps meeting from the other direction, where a value an enum
    could not read fell to the mildest reading and inverted the setting.
    """
    level = str(value or "").strip().casefold()
    return level if level in OFFSCREEN_LIFE_LADDER else OFFSCREEN_LIFE_DEFAULT


DEFAULT_INTERACTION_CONFIG = {
    "style": "natural",
    "min_lines": 0,
    "max_lines": 4,
    "variance": 0.6,
    "autonomy": 50,
    "max_micro_rounds": 4,
    "max_character_calls": 6,
    "max_speakers_per_round": 1,
    # How many characters open the beat in one blind instant. ONE, so causality
    # builds as the loop runs: each character after the first decides in a room
    # where the previous one has already acted. Raise it for a beat aimed at
    # nobody in particular, where the room genuinely reacts as a room -- see
    # agents/loops.py § ONE AT A TIME.
    "initial_parallel_reactors": 1,
    # May reactors who cannot possibly perceive each other -- separate rooms,
    # no sight, nothing audible even at a shout -- share the opening instant?
    # The rule is right and the machinery is written and tested
    # (`agents/loops._isolated_wave`), but every reactor in a beat today is
    # somebody the player can hear, so this branch would never fire on a real
    # story and its first live run would be its first exercise. OFF until
    # there is offscreen life to run through it.
    "parallel_isolated_reactors": False,
    "max_director_calls": 4,
    "max_perception_calls": 4,
    "allow_npc_initiative": True,
    "allow_npc_to_npc_dialogue": True,
    "stop_on_player_address": True,
    "stop_on_question_to_player": True,
    "silence_ends_exchange": True,
    # Turns of DELIBERATE interaction -- the player addressing them, or a real
    # character aiming a line at them -- before a background extra is promoted
    # into a full character. 0 means never, and is the default: acquiring cast
    # is not something a story should do without being asked.
    "promote_after_addressed": 0,
    # How much life the cast is permitted OFF screen. See OFFSCREEN_LIFE_LADDER.
    "offscreen_life": OFFSCREEN_LIFE_DEFAULT,
    "max_offscreen_actors": 3,
}

def offscreen_life_allows(level, rung):
    """Does `level` permit what `rung` needs. Ordered comparison on the ladder."""
    level = normalize_offscreen_life(level)
    if rung not in OFFSCREEN_LIFE_LADDER:
        return False
    return OFFSCREEN_LIFE_LADDER.index(level) >= OFFSCREEN_LIFE_LADDER.index(rung)

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
    config["offscreen_life"] = normalize_offscreen_life(config.get("offscreen_life"))
    try:
        config["max_offscreen_actors"] = max(
            0, min(12, int(config.get("max_offscreen_actors", 3))))
    except (TypeError, ValueError):
        config["max_offscreen_actors"] = 3
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

    `scene_life` selects the scene-manager path (docs/BACKGROUND_LIFE_DESIGN.md
    §3.10) and is OFF by default -- this relaxes an information rule and its
    value is a matter of taste, so it is opt-in per chat:

      "off"     -- historical per-presence background_react only.
      "ambient" -- one batched manager call whose context holds ONLY what every
                   managed presence legitimately shares; a line directed at one
                   of them is withheld and falls through to background_react.
                   Cross-contamination is impossible, not mitigated.
      "full"    -- the manager also receives directed lines, tagged inline with
                   their audience. Buys single-beat coherence, accepts the
                   tagged-divergence risk.

    `max_managed` bounds how many presences one manager call may hold.
    """
    config = {"max_reactors": 1, "scene_life": "off", "max_managed": 6}
    stored = wget(chat_id, "background_config", None) or {}
    config.update(stored)
    return config

# Kinds that are a voice rather than a body, recognized even when the model
# forgets the explicit `ubiquitous` flag. Deliberately narrow: a mis-flagged
# ordinary NPC would become unpositionable and un-promotable, which is worse
# than a ship AI that stays room-bound.
UBIQUITOUS_KINDS = frozenset({
    "ship_ai", "shipai", "ship_computer", "station_ai", "station_computer",
    "computer", "ai", "system", "intercom", "pa_system", "announcer",
})


def is_ubiquitous_entity(entity):
    """True for a bodiless voice -- a ship's computer, a station AI, a PA.

    Such a thing has no room, and giving it one is a category error: the
    Enterprise computer is not "in Ten Forward", it is wherever the ship is.
    Live play produced exactly that (`computer`, kind=agent, positioned in
    `enterprise_ten_forward`), which pinned it to one room and made it a
    promotion candidate.
    """
    if not isinstance(entity, dict):
        return False
    if entity.get("ubiquitous"):
        return True
    return str(entity.get("kind") or "").strip().casefold() in UBIQUITOUS_KINDS


def ubiquitous_speaker_names(scene):
    """Casefolded display names (and ids) of every bodiless voice in the scene,
    for readers that must not treat them as room-bound speakers."""
    names = set()
    for eid, entity in ((scene or {}).get("entities") or {}).items():
        if not is_ubiquitous_entity(entity):
            continue
        names.add(str(eid).strip().casefold())
        display = str((entity or {}).get("name") or "").strip()
        if display:
            names.add(display.casefold())
    return names


def promotion_config(chat_id):
    """How much a background presence must do before the engine offers it a
    mind. Authorial pacing, not fixed law -- a crowded tavern wants a high bar,
    a two-hander wants a low one -- so it is settable per chat.

    `dialogue`      lines spoken before the UI offers promotion.
    `mention`       passing mentions that do the same.
    `auto_dialogue` lines before hands-off auto-promotion fires (gated
                    separately by the global `auto_promote` setting).
    """
    from commit import (BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD,
                        BACKGROUND_PROMOTION_MENTION_THRESHOLD,
                        AUTO_PROMOTE_DIALOGUE_THRESHOLD)
    config = {
        "dialogue": BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD,
        "mention": BACKGROUND_PROMOTION_MENTION_THRESHOLD,
        "auto_dialogue": AUTO_PROMOTE_DIALOGUE_THRESHOLD,
    }
    stored = wget(chat_id, "promotion_thresholds", None) or {}
    for key in config:
        try:
            value = int(stored[key])
        except (KeyError, TypeError, ValueError):
            continue
        config[key] = max(1, min(50, value))
    return config


def fiction_model(chat_id):
    return wget(chat_id, "fiction_model", None) or {
        "genre": {"primary": "unspecified"},
        "ontology": {},
        "causal_regimes": [],
        "scale_rules": {},
        "abstraction_rules": {},
    }

# Authored house style for anything the engine GENERATES. Distinct from
# fiction_model, which the engine derives for itself: this is the author's
# standing instruction, and nothing infers or overwrites it.
#
# It reaches the Director and the mapping agent only. Character agents are
# deliberately excluded -- a character's manner comes from their own authored
# voice and psychology, and piping a house style into their heads would make
# every mind in the world sound like the same narrator. Perception is excluded
# for the same reason it is excluded from everything else: it is a filter, not
# an author.
STYLE_GUIDE_FIELDS = ("genre", "tone", "director_notes", "mapping_notes", "avoid")
STYLE_GUIDE_LIMIT = 2000

# How far the sky is allowed to go, and how much of the world it may touch.
# A closed vocabulary rather than free text because it GATES behaviour rather
# than describing it -- the engine caps drift on it and the Director is told
# what it permits, so an unrecognised value has to become a known one.
#
#   calm          weather is scenery. Light at worst, and it leaves no mark on
#                 the world: no mud, no drifts, nothing underfoot.
#   seasonal      real weather, the full range of it, and ground that answers
#                 to it. Nothing here endangers anyone. THE DEFAULT.
#   harsh         weather you would not want to be caught out in: soaking,
#                 numbing, treacherous footing. Costly, not deadly.
#   catastrophic  weather may become the event. Floods, blizzards, things
#                 giving way. Opt-in, and never a default, because a story can
#                 be ruined by a sky that decided to.
WEATHER_SEVERITIES = ("calm", "seasonal", "harsh", "catastrophic")
DEFAULT_WEATHER_SEVERITY = "seasonal"

# Explicit "work it out yourself" values for genre. Pinning a genre is the new
# capability, but self-determination is the DEFAULT and stays first-class: the
# engine already infers a fiction_model from the scenario and lore, and an
# author who has not decided on a genre should not be forced to invent one.
# Normalizing these to an absent key means the payload simply carries no genre,
# which is exactly the pre-existing behaviour.
STYLE_GUIDE_AUTO = {"auto", "self determine", "self-determine", "selfdetermine",
                    "engine", "unspecified", "any", "default"}


def normalize_style_guide(raw):
    """A style guide from arbitrary input. Every field is optional free text;
    anything unrecognized is dropped and the whole thing degrades to {} rather
    than reaching a prompt malformed."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw or "{}")
        except Exception:
            return {}
    if not isinstance(raw, dict):
        return {}
    out = {}
    # Closed vocabulary, so it is normalized rather than trimmed: this one
    # gates engine behaviour instead of describing it, and an unrecognised
    # value has to become a known one rather than travel on as free text.
    severity = str(raw.get("weather_severity") or "").strip().casefold()
    if severity and severity != DEFAULT_WEATHER_SEVERITY:
        out["weather_severity"] = (severity if severity in WEATHER_SEVERITIES
                                   else DEFAULT_WEATHER_SEVERITY)
    for key in STYLE_GUIDE_FIELDS:
        value = raw.get(key)
        if value is None:
            continue
        text = " ".join(str(value).split()) if key in ("genre", "tone") \
            else str(value).strip()
        if not text:
            continue
        if key == "genre" and text.casefold() in STYLE_GUIDE_AUTO:
            continue  # self-determine: carry no genre at all
        out[key] = text[:STYLE_GUIDE_LIMIT]
    return out


def style_guide(chat_id):
    """The authored style guide, or {} when none is set. Read per turn so an
    edit applies to the next beat without a restart."""
    return normalize_style_guide(wget(chat_id, "style_guide", None) or {})


def weather_severity(chat_id):
    """How far this story's sky may go. See WEATHER_SEVERITIES."""
    value = (style_guide(chat_id) or {}).get("weather_severity")
    return value if value in WEATHER_SEVERITIES else DEFAULT_WEATHER_SEVERITY

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
    # `min_lines` rides along as itself. It used to be consumed here and
    # discarded: the only thing derived from it was `may_stay_silent`, a boolean
    # that a SINGLE line already satisfies, so an author setting min_lines 2
    # sent the character agent no number it could honour. Measured across the
    # author's live chats, line counts did not track the setting at all -- a
    # chat at min_lines 2 produced one line in 28 of 28 declarations while a
    # chat at min_lines 0 produced two or more in 43% of them.
    return {"style": style, "suggested_lines": target, "min_lines": lo,
            "hard_max": hi, "may_stay_silent": lo == 0}

def cast_scene_context(cast_rows):
    """Build scene-relevant character dossiers for mapping and director."""
    result = []
    for row in cast_rows:
        sheet = json.loads(row["sheet"])
        identity = sheet.get("identity") or {}
        result.append({
            "id": int(row["id"]),
            "entity_id": cast_entity_id(sheet, row["id"]),
            "name": character_name(sheet),
            "aliases": identity.get("aliases") or [],
            "appearance": character_appearance(sheet),
            "initial_outfit": character_initial_outfit(sheet),
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
        "SELECT COALESCE(cc.sheet,ch.sheet) AS sheet, "
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
