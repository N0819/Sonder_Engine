# scene.py
"""Scene management with entity awareness, genre config, and world state."""

import json, re, random
from core.db import active_frame_id, q, qi, wget, wset
from world.spatial import room_of, spatial_rel

_UNSET = object()

from story.character_schema import (
    EXTRA_PART_ASPECTS,
    _extra_part_placement,
    cast_entity_id,
    character_abilities,
    character_appearance,
    character_extra_parts,
    character_initial_outfit,
    character_initial_active_state,
    character_initial_stance,
    character_name,
    character_name_from_text,
    character_opening_context,
    character_private_history,
    character_public_history,
    character_scent,
    character_senses,
    normalize_persona_data,
    persona_abilities,
    persona_appearance,
    persona_initial_outfit,
    persona_name,
    persona_private_history,
    persona_public_history,
    persona_scent,
    persona_senses,
    persona_voice_setting,
    senses_as_text,
)

import re as _re

from story import attire as attire_model
# The third copy of this pair lived here until 2026-08-18, and it had already
# drifted in spelling if not in behaviour: the same eight-word set and the same
# loop, written out again. `story/attire.py` owns both (audit STORY-F11), and
# re-exporting from here keeps `scene.sanitize_attire_items` importable for the
# callers that know it by that name.
from story.attire import _NON_ATTIRE_TERMS, sanitize_attire_items  # noqa: F401


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
    `active_cast`. This answers only "is this a person the story knows
    about", which is what name resolution, the recognition map and the
    anti-furniture guard actually need.

    Frame-scoped for the same reason `active_cast` is, and by the same
    means: a frame is an ERA, and existence is one of the things that
    genuinely differs between them -- somebody written out of the era being
    played is not someone that era knows about, however alive the base row
    says they are. `frame_id=None` (present) reads `chat_chars` directly; a
    real frame LEFT JOINs `chat_char_frames` and prefers its override, so an
    era nobody has touched still starts from the character's ordinary
    baseline. The status and the state must come from the SAME row, or a
    caller gets one era's roster carrying another era's private state.
    """
    placeholders = ",".join("?" * len(DEPARTED_STATUSES))
    if frame_id is None:
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
    return q(
        "SELECT ch.id,ch.name,COALESCE(cc.sheet,ch.sheet) AS sheet,"
        "ch.source,ch.created,ch.resource_uid,"
        "COALESCE(ccf.state, cc.state) AS cstate, "
        "COALESCE(ccf.status, cc.status) AS status "
        "FROM chat_chars cc "
        "JOIN characters ch ON ch.id=cc.char_id "
        "LEFT JOIN chat_char_frames ccf "
        "  ON ccf.chat_id=cc.chat_id AND ccf.char_id=cc.char_id AND ccf.frame_id=? "
        f"WHERE cc.chat_id=? AND COALESCE(ccf.status, cc.status) NOT IN ({placeholders}) "
        "ORDER BY ch.id",
        (frame_id, chat_id, *DEPARTED_STATUSES),
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


#: The two states `chat_chars.status` has, and the only two an attached
#: character can be in: in the live scene, or out of it. `offscreen.py` reads
#: `dormant` as the away roster, so these are not labels -- they decide which
#: simulation a mind is in.
CAST_STATUS_PRESENT = "active"
CAST_STATUS_ABSENT = "dormant"

#: What the Director may write in `state_diff.cast_changes[].status`, mapped
#: to those two. PROTOCOL tokens, not prose: the social specialist is asked
#: for these words in English whatever language the story is in, the same way
#: it is asked for `barrier:'open'|'closed_door'`.
#:
#: The synonyms are here because the field is a free string on an untyped
#: entry, and a model handed one reaches for the natural word -- `schemas.py`'s
#: own worked example writes `"departed"`. The engine used to test
#: `stt in ("active", "dormant")` and drop everything else without a word,
#: which left the character `active` in the roster while three other readers
#: of the same entry treated them as gone.
_CAST_CHANGE_STATUS = {
    "active": CAST_STATUS_PRESENT,
    "arrived": CAST_STATUS_PRESENT,
    "arrives": CAST_STATUS_PRESENT,
    "arriving": CAST_STATUS_PRESENT,
    "present": CAST_STATUS_PRESENT,
    "returned": CAST_STATUS_PRESENT,
    "rejoined": CAST_STATUS_PRESENT,
    "joined": CAST_STATUS_PRESENT,
    "dormant": CAST_STATUS_ABSENT,
    "departed": CAST_STATUS_ABSENT,
    "departs": CAST_STATUS_ABSENT,
    "departing": CAST_STATUS_ABSENT,
    "left": CAST_STATUS_ABSENT,
    "leaves": CAST_STATUS_ABSENT,
    "leaving": CAST_STATUS_ABSENT,
    "exited": CAST_STATUS_ABSENT,
    "gone": CAST_STATUS_ABSENT,
    "away": CAST_STATUS_ABSENT,
    "offscreen": CAST_STATUS_ABSENT,
    "inactive": CAST_STATUS_ABSENT,
}


def cast_change_status(value):
    """One `cast_changes` status word -> `active`, `dormant`, or None.

    None means UNRECOGNIZED, and every caller must say so rather than pick a
    default: the two answers send a mind into different simulations, and a
    silent guess is how a character stays in the roster after walking out.
    """
    return _CAST_CHANGE_STATUS.get(str(value or "").strip().casefold())


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
    # A field name can never key an entity or stand in a room. A stored scene
    # can carry such keys from before schemas' hoist covered the specialist
    # path (chat 80: six "entities" keyed remove_entities/inventory_ops/...,
    # each a copy of the Interview Chair); the merge heals the durable blob on
    # the next commit (spatial.merge_scene_with_diff), and this keeps every
    # reader between now and then from treating the debris as furniture.
    try:
        from llm.schemas import NON_ENTITY_FIELD_KEYS
        for ledger in ("entities", "positions"):
            for bad in [k for k in sc[ledger] if k in NON_ENTITY_FIELD_KEYS]:
                sc[ledger].pop(bad, None)
    except Exception:
        pass
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


#: HOW A BODY'S STANDING CONDITION ROWS ARE WALKED, for every reader that
#: collapses `world_conditions` to one answer per subject. Rows accumulate --
#: the Director mints a fresh condition_id per reroll, a branch copies rows
#: wholesale, a restore rewrites them -- so several are routinely active on
#: one body, and whichever the scan reaches last decides what everyone sees.
#: The order must therefore be the STORY's, not the table's: `rowid` is
#: insertion order, which a branch copy and a re-emission both scramble.
#: Stated once because two readers of one table with two tie-breaks is a
#: guarantee they will one day disagree about the same person -- which they
#: did: `active_disguises` ordered by the clock and `awareness_conditions` by
#: rowid.
_CONDITION_ORDER = "ORDER BY started_at ASC, rowid ASC"

def active_disguises(chat_id):
    """Active physical_disguise conditions for `chat_id`, keyed by casefolded
    subject name. Each value: {subject, description, presented_appearance,
    concealed_terms, known_to}. Legacy conditions carry only a freeform
    `description`; newer ones (see the director prompt) also carry a positive
    `presented_appearance` (what an unaware observer sees), `concealed_terms`
    (feature words to keep out of unaware views / to tripwire on), and
    `known_to` (observers who legitimately know the real form).

    ONE SUBJECT, ONE DISGUISE, AND THE NEWEST WINS. Several active rows for
    the same body is not hypothetical -- measured live, chat 72 carried three,
    the Director having minted a fresh condition_id per reroll instead of
    superseding. Keying by subject means one of them silently decides what
    every observer sees, and with no ORDER BY that was whichever the scan
    happened to reach last: the glamour appeared to work for a turn and then
    stop, because a different row won. Ordering makes the winner the most
    recently started one, which is the only answer that matches what a reader
    just watched happen."""
    out = {}
    for row in q(
        "SELECT subject_id, payload FROM world_conditions WHERE chat_id=? "
        "AND kind='physical_disguise' AND active=1 "
        f"{_CONDITION_ORDER}", (chat_id,),
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
        # KNOWLEDGE ACCUMULATES ACROSS ROWS; APPEARANCE DOES NOT.
        #
        # The newest row decides what is presented -- there is one outward
        # form -- but "who has been told the truth" is not a property of a
        # row, it is a fact about people, and a superseded row does not
        # un-tell them. The write-side rule now inherits it forward, and this
        # is the same rule for rows that predate it or arrived some other way.
        #
        # BRANCHING IS HOW THEY ARRIVE. `_supersede_singular_conditions` runs
        # at the WRITE, and a branch copies rows wholesale without one --
        # measured live: chat 72 carried two rows started at the same clock
        # second, and its descendants 73 and 74 inherited both, re-keyed.
        # Equal `started_at` makes the ORDER BY a coin flip resolved by
        # rowid, and the row that won carried `known_to: []` while every
        # other row on that body named The Doctor. The one character who had
        # been told was the only one fooled, for the rest of the story.
        prior = out.get(subject.casefold()) or {}
        carried = list(prior.get("known_to") or [])
        for who in (pick("known_to") or []):
            text = str(who).strip()
            if text and text not in carried:
                carried.append(text)
        out[subject.casefold()] = {
            "subject": subject,
            "description": str(pick("description") or "").strip(),
            "presented_appearance": str(pick("presented_appearance") or "").strip(),
            "concealed_terms": [str(t).strip() for t in (pick("concealed_terms") or [])
                                if str(t).strip()],
            "known_to": carried,
            # Does this disguise cover what a body is RECOGNISED by -- a
            # face, a build, a voice -- or only a feature it hides? A glamour
            # over fox ears is the second, and someone who knows her still
            # knows her. Typed and defaulting to False, because the
            # alternative (every disguise is a perfect identity mask) makes a
            # mind conclude less than its senses support.
            "conceals_identity": bool(pick("conceals_identity")),
            # The one channel that may SHOW an authored extra part through a
            # disguise, and the seam an additive transformation would use to
            # grant a part no card declares. Typed on purpose: the prose
            # fields can only conceal, because a sentence saying "no tails
            # are visible" mentions tails and a text match cannot tell the
            # difference (measured live -- it put six of them back).
            "visible_parts": [
                str((e or {}).get("kind") if isinstance(e, dict) else e).strip()
                for e in (pick("visible_parts") or [])
                if str((e or {}).get("kind") if isinstance(e, dict) else e).strip()
            ],
        }
    return out


#: Conditions of which a body may have exactly one. A disguise is one outward
#: form; a transformation is one body. Enforced at the write (`commit.py`
#: `_supersede_singular_conditions`) rather than requested of the Director,
#: which minted a fresh condition_id per reroll and left three live at once.
SINGULAR_BODY_CONDITIONS = ("physical_disguise", "physical_transformation")


def normalize_transformed_parts(parts):
    """A transformation's parts, coerced onto the same menus a card's are.

    `at` must be an `attire.REGIONS` key and `aspect` one of
    `EXTRA_PART_ASPECTS`, because `agents.common.extra_part_phrase` renders
    them as "emerges from the {aspect} of the {at}" and every visibility
    verdict is keyed by region. A CARD's parts are coerced on the way in
    (`character_schema._normalize_extra_parts`); a transformation's are model
    free text and nothing coerced them, so both fields arrived as prose:

        {"kind": "fox ears", "at": "top of the head",
         "aspect": "fluffy, pointed, golden"}
        -> "emerge from the fluffy, pointed, golden of the top of the head"

    THE OFF-MENU TEXT IS SALVAGED, NOT DISCARDED, and that is the difference
    from the card path. An author who miskeys a card can see it in the editor
    and fix it; a transformation's stray text is the only description of that
    anatomy in existence, and it is exactly the material detail worth
    delivering ("fluffy, pointed, golden"). `extra_part_phrase` already
    renders a `description`, so there is a correct slot standing empty. A
    fragment the canonical fields already say is dropped, so "top of the head"
    does not survive alongside at=head/aspect=top.

    Healed on READ rather than migrated, on the `attire.rederive_entry`
    precedent: stored conditions repair lazily instead of rewriting stories
    mid-play.
    """
    out = []
    for part in (parts or []):
        if not isinstance(part, dict):
            continue
        kind = " ".join(str(part.get("kind") or "").split())
        if not kind:
            continue
        guess_at, guess_aspect = _extra_part_placement(kind)
        stray = []

        at = str(part.get("at") or "").strip().casefold()
        if at not in attire_model.REGIONS:
            if at:
                stray.append(at)
            at = guess_at
        aspect = str(part.get("aspect") or "").strip().casefold()
        if aspect not in EXTRA_PART_ASPECTS:
            if aspect:
                stray.append(aspect)
            aspect = guess_aspect

        description = " ".join(str(part.get("description") or "").split())
        if stray:
            canon = {at, aspect, "the", "of", "a", "an"}
            keep = [s for s in stray
                    if set(s.replace(",", " ").split()) - canon]
            if keep:
                description = "; ".join(filter(None, [description] + keep))
        fixed = dict(part, kind=kind, at=at, aspect=aspect)
        if description:
            fixed["description"] = description
        out.append(fixed)
    return out


def active_transformations(chat_id):
    """Active `physical_transformation` conditions, keyed by casefolded subject.

    A TRANSFORMATION IS NOT A DISGUISE, and the difference is not cosmetic. A
    disguise is a lie with a truth behind it -- hence `concealed_truth`,
    `known_to`, and a fallback that fails toward concealment. A transformation
    has no truth behind it: the body IS the new thing, nobody sees through it,
    and someone who knew you yesterday does not perceive your old shape today.
    Modelling one as the other would invent a hidden fact where none exists
    and hand other minds a `known_to` slot to be granted access to it.

    So this replaces rather than conceals. `appearance` becomes the body's
    true visible description; `parts` becomes its authored extra parts
    outright, which is what lets a transformation ADD (grow wings) where a
    disguise can only subtract.

    Each value: {subject, form, appearance, parts, reversible, reversal,
    caused_by}. `reversible` defaults TRUE -- the ordinary case is a shape you
    can drop -- and a fiction that wants a one-way door has to say so, because
    trapping somebody by omission is the failure nobody can undo.
    """
    out = {}
    for row in q(
        "SELECT subject_id, payload FROM world_conditions WHERE chat_id=? "
        "AND kind='physical_transformation' AND active=1 "
        "ORDER BY started_at ASC, rowid ASC", (chat_id,),
    ):
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            payload = {}
        subject = str(payload.get("subject_id") or row["subject_id"] or "").strip()
        if not subject:
            continue
        state = _condition_state(payload)
        pick = lambda k: state.get(k) if state.get(k) is not None else payload.get(k)
        # `parts is None` means "unchanged" and `[]` means "none" -- see
        # transformed_parts. Normalising must preserve that distinction, so a
        # missing list stays missing rather than becoming an empty one.
        _raw_parts = pick("parts")
        parts = (None if _raw_parts is None
                 else normalize_transformed_parts(_raw_parts))
        out[subject.casefold()] = {
            "subject": subject,
            "form": str(pick("form") or "").strip(),
            "appearance": str(pick("appearance") or "").strip(),
            "parts": parts,
            # Absent means reversible. Only an explicit false is a one-way
            # door, so a Director that forgets the field cannot strand anyone.
            "reversible": pick("reversible") is not False,
            "reversal": str(pick("reversal") or "").strip(),
            "caused_by": str(pick("caused_by") or "").strip(),
        }
    return out


def transformed_sheet(sheet, transformation):
    """The card as the body currently IS, for the mind that lives in it.

    A MIND MUST NOT KEEP THE BODY IT NO LONGER HAS. Every character payload is
    built from the card -- senses, abilities, embodiment capabilities, extra
    parts -- and the card is authored and immutable. So without this, turning
    somebody into a fox changes what observers see and leaves the fox
    convinced it still has hands, declaring accordingly, and the Director
    refusing it every beat.

    This is the same shape `scene.attire` already has against `initial_outfit`:
    the card is what was authored, the overlay is what is true now, and the
    mind learns its new shape through its own interoception rather than by
    reading world state. The gap stays intact -- nothing here tells the body
    who transformed it or that a transformation is what happened.

    Returns the sheet unchanged when there is no transformation, and a shallow
    copy otherwise: the caller's card is a cached read shared with other
    stages, so mutating it in place would transform everybody's view of it.
    """
    if not transformation:
        return sheet
    if not isinstance(sheet, dict):
        return sheet
    out = dict(sheet)
    body = dict(out.get("embodiment") or {})

    appearance = (transformation.get("appearance")
                  or transformation.get("form"))
    if appearance:
        visible = dict(body.get("visible") or {})
        visible["summary"] = appearance
        body["visible"] = visible

    if transformation.get("parts") is not None:
        body["extra_parts"] = transformation.get("parts") or []

    out["embodiment"] = body
    return out


def transformed_true_appearance(true_appearance, transformation):
    """The body's REAL visible description, after any transformation.

    Replaces rather than edits: a body that is now a fox is not a woman with
    fox words removed. Falls back to `form` when no appearance prose was
    written, and to the card when neither is -- an empty transformation must
    not blank a body out of the world."""
    if not transformation:
        return true_appearance
    return (transformation.get("appearance")
            or transformation.get("form")
            or true_appearance)


def transformed_parts(authored_parts, transformation):
    """The extra parts this body HAS, after any transformation.

    The transformation's list is authoritative and total, which is what makes
    it additive AND subtractive in one field: a fox has one tail and no hands
    whatever the card said. An empty list is a body with no extra parts, and
    that is a real answer -- so `parts` absent (None) means "unchanged",
    `parts: []` means "none". Those are different, and collapsing them would
    make it impossible to transform INTO something plain."""
    if not transformation or transformation.get("parts") is None:
        return authored_parts
    return transformation.get("parts") or []


#: How a sentence says absence. Lifted from `conceal_disguised_parts`'s own
#: comment, which enumerated them to explain why a negation could not be read
#: as permission -- the same list, now used to stop the negation reaching an
#: observer at all.
_ABSENCE = re.compile(
    r"\b(?:no|not|none|nothing|neither|nor|never|without|absent|lacks?|"
    r"lacking|hidden|concealed|invisible|missing|free\s+of|devoid)\b",
    re.IGNORECASE)


def _positive_presented_appearance(presented, concealed_terms):
    """A presented appearance may only say what IS seen.

    "…; no tails are visible" is not a description, it is a DISCLOSURE. An
    observer who has never seen a kitsune does not perceive an absence of
    tails -- they perceive a woman -- and stating the absence hands them the
    category the disguise exists to keep. Reported live (chat 74): the Doctor,
    who is not told, received "normal human ears visible on the sides of her
    head; no tails are visible" and thereby learned that tails were a thing
    anyone might have.

    `conceal_disguised_parts` already met this exact sentence from the other
    side -- a negation was reading as a mention and granting the parts back --
    and fixed the mechanical half. This is the epistemic half.

    Only clauses that BOTH negate and name something concealed are dropped.
    The positive half of the same sentence is what the observer legitimately
    sees and must survive: "an ordinary traveller with normal human ears"
    stays, and only the denial after the semicolon goes. Dropping every clause
    that mentions a concealed noun would delete the disguise itself, since a
    glamour over fox ears is precisely a description of ears.
    """
    text = str(presented or "").strip()
    if not text:
        return ""
    tokens = set()
    for term in (concealed_terms or []):
        tokens |= _part_tokens(term)
    if not tokens:
        return text
    kept, seps, dropped = [], [], False
    for match in re.finditer(r"\s*([^;.!?]+)([;.!?]*)", text):
        clause = match.group(1).strip()
        if not clause:
            continue
        if _ABSENCE.search(clause) and (_part_tokens(clause) & tokens):
            dropped = True
            continue
        kept.append(clause)
        seps.append(match.group(2))
    if not dropped:
        # Nothing to remove, so nothing to rewrite. The field is
        # director-authored prose and a caller that asked for it should get
        # exactly what was written, down to the terminal punctuation.
        return text
    if not kept:
        # Every clause was a denial. Nothing is left that says what the
        # observer SEES, so fall through to the scrub and then the generic
        # label -- an information barrier fails toward concealment.
        return ""
    # Rejoin with the punctuation the sentence actually used. Splitting on the
    # separators and joining with a space welded two clauses into one
    # ungrammatical run ("...top of her head her appearance is...").
    joiner = ". " if all(s.startswith(".") for s in seps[:-1] or ["."]) else "; "
    out = joiner.join(kept).strip(" ;,")
    if out and not out.endswith((".", "!", "?")):
        out += "."
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
    terms = (disguise or {}).get("concealed_terms") or []
    presented = _positive_presented_appearance(
        (disguise or {}).get("presented_appearance"), terms)
    if presented:
        return presented
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
        # A scrub that leaves a fragment is not a description. Removing "six
        # golden tails" from "A woman with six golden tails" leaves "A woman
        # with", which reads as damage rather than as concealment -- and is
        # now reachable, because a presented appearance made entirely of
        # denials falls through to here. Require something that can end a
        # sentence.
        if matched and scrubbed and not re.search(
                r"\b(?:with|and|or|of|in|on|at|from|by|the|a|an|her|his|"
                r"their|its)$", scrubbed, re.IGNORECASE):
            return scrubbed
    return "a person whose appearance is unremarkable"


def _part_tokens(text):
    """Lowercased word set folded to ONE canonical form each, so "tails" and
    "tail" produce the same token and either can be compared against either.

    Canonical rather than "both forms": adding the singular beside the plural
    made the fold one-directional -- {tails, tail} is not a subset of {tail},
    so a part named "tails" failed to match a grant written "tail" while the
    reverse matched. Whether a stripped word is a real singular does not
    matter ("glass" -> "glas") as long as both sides are stripped the same
    way, which is the whole trick."""
    out = set()
    for word in re.findall(r"[a-z]+", str(text or "").casefold()):
        out.add(word[:-1] if len(word) > 3 and word.endswith("s") else word)
    return out


def conceal_disguised_parts(parts_by_name, disguises):
    """Drop authored extra parts a disguise hides, per body.

    THE APPEARANCE SUMMARY WAS NEVER THE ONLY PLACE A BODY IS DESCRIBED.
    `disguised_visible_appearance` rewrites one string, but authored extra
    parts are a separate typed ledger rendered straight from structured data
    by the composer -- so a glamoured kitsune kept six tails and two fox ears
    in every observer's view while her summary said "ordinary human ears".
    Reported live (chat 72).

    PROSE MAY ONLY CONCEAL; ONLY A TYPED FIELD MAY GRANT. The first version
    kept a part whose name appeared in `presented_appearance`, on the theory
    that a disguise naming wings is a disguise showing wings. Measured live
    one turn later: the Director wrote "...; no tails are visible", the word
    `tails` was present, and six tails came back. A negation reads as a
    mention, and so do "without", "hidden", "no longer" and every other way a
    sentence can say absence -- the Director's own instruction forbids
    mentioning the concealed feature at all (prompts.py) and it mentioned it
    anyway, which is exactly the cooperation a deterministic floor may not
    depend on.

    So under a disguise every authored part is concealed, and a part is shown
    only when the condition carries it in `visible_parts` -- a typed list, no
    parsing, nothing to negate. That is also the seam an ADDITIVE
    transformation wants: a body that grows wings it was never authored with
    is the same mechanism read the other way.

    Over-concealing costs a detail. Leaking costs the disguise.
    """
    if not parts_by_name or not disguises:
        return parts_by_name
    out = {}
    for name, parts in (parts_by_name or {}).items():
        disguise = disguises.get(str(name or "").casefold())
        if not disguise:
            out[name] = parts
            continue
        granted = set()
        for entry in (disguise.get("visible_parts") or []):
            granted |= _part_tokens(
                entry.get("kind") if isinstance(entry, dict) else entry)
        kept = [
            part for part in (parts or [])
            if granted and _part_tokens((part or {}).get("kind")) <= granted
        ]
        if kept:
            out[name] = kept
    return out


def disguise_breaks_recognition(known_to, observer_name, conceals_identity):
    """Can this observer still connect this body to the name they know?

    A DISGUISE CONCEALS FEATURES; IDENTITY IS A SEPARATE FACT. The rule used
    to be that any active disguise severed the name for anyone not in
    `known_to`, however well they knew the person -- which makes every
    disguise a perfect identity mask and is wrong about most of them. A
    glamour over fox ears does not touch the face, so someone who knows her
    still knows her, wearing unfamiliar ears; a full mask is a different
    claim, and now has to make it.

    Reported live (chat 74), where the old rule produced a view that
    contradicted itself inside one paragraph: her NAME three times from the
    proximity and pose lines, and a stranger's descriptor once from the
    appearance line. The disguise leaked the identity and showed the false
    body -- the worst of both.

    Defaulting to recognition surviving is the direction the firewall's own
    statement points: inference is the product, and a guard must not make a
    mind conclude less than its senses support. The cost is that a disguise
    which genuinely should hide who you are must say so; the benefit is that
    it can, and can be told apart from one that never meant to.
    """
    if known_to is None:                       # no disguise on this body
        return False
    if str(observer_name or "").casefold() in (known_to or ()):
        return False                           # told the truth: they know
    if conceals_identity is None:
        # A disguise is active and the caller did not say which kind. That is
        # never a disguise's own answer -- `_subject_disguise_context` returns
        # a real bool for every active one -- so it means the body record was
        # built without the flag, and the two halves of one fact came apart.
        #
        # Fail CLOSED, alone among this function's defaults. Everywhere else
        # here the default is recognition surviving, because a guard must not
        # make a mind conclude less than its senses support. This branch is
        # not about senses: it is the engine failing to state its own rule,
        # and a leak is an engine failure, never a model's. The cost of
        # guessing wrong here is a name withheld for a beat; the cost of the
        # other guess is a concealed identity handed to everyone who ever met
        # the wearer, which is what `_composer_outcome` did for as long as it
        # dropped this flag.
        return True
    return bool(conceals_identity)


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
    """Casefold a level string to the enum. Unknown/garbage degrades to
    'dazed' rather than vanishing; empty/awake -> 'awake'.

    'dazed' IS NOT A GATE, and this said "the mildest gate", which is the one
    reading that makes the fall-through look conservative. `NON_AWAKE_GATED`
    is asleep/sedated/unconscious; a level this enum cannot read therefore
    produces a mind that perceives normally and runs a full character step.
    That is the right direction -- a gated mind runs no character step at all,
    so a word nobody recognises must not be able to silence somebody -- but it
    is fail-OPEN, and stating it as a gate is how a later reader "restores"
    one that never existed.
    """
    level = str(raw or "").strip().casefold()
    if level == "" or level == "awake":
        return "awake"
    if level not in AWARENESS_LEVELS:
        return "dazed"
    return level


#: Kinds where the model filed the LEVEL in the kind slot -- the same
#: spelling-drift class as `physical_restraint` vs `restraint`. Measured
#: live: 9 active rows carry a kind of `unconscious` (6), `asleep` (1),
#: `sleep` (1) or `consciousness` (1) with an EMPTY state, and chats 24/25
#: hold `unconscious` rows on subjects with no canonical awareness row at
#: all. Reading `unconscious` off the kind is not an inference -- the word
#: names exactly one level -- but a word that merely ORBITS the topic stays
#: unread: `consciousness` names the faculty, not a state of it (the live
#: row records a body coming to), and `preparing_for_sleep` is a body still
#: awake arranging a futon. Hence the matching is WHOLE-KIND (separators
#: normalised), never word-splitting, which would read
#: `preparing_for_sleep` as `sleep` and gate an awake mind.
_AWARENESS_KIND_LEVELS = {
    "awareness": "",            # canonical: the level lives in state
    "unconscious": "unconscious",
    "knocked out": "unconscious",
    "passed out": "unconscious",
    "out cold": "unconscious",
    "asleep": "asleep",
    "sleep": "asleep",
    "sleeping": "asleep",
    "sedated": "sedated",
    "sedation": "sedated",
    "dazed": "dazed",
    "stunned": "dazed",
}


def awareness_kind_level(kind):
    """The awareness level a condition KIND itself asserts.

    None: not an awareness-family kind at all. "": the canonical
    `awareness` kind, whose level lives in state. Otherwise the level word
    the model filed the condition under."""
    token = " ".join(
        w for w in _re.split(r"[^a-z0-9]+", str(kind or "").casefold()) if w)
    return _AWARENESS_KIND_LEVELS.get(token)


def _awareness_level_from(kind_level, *raw_levels):
    """One level from a family row: an explicit state/payload `level` wins
    (it is the more deliberate assertion), and only silence falls back to
    the level the kind word asserts."""
    for raw in raw_levels:
        if str(raw or "").strip():
            return _normalize_awareness_level(raw)
    return kind_level or "awake"


def awareness_cond_level(cond):
    """The level a diff conditions entry asserts, or None when the entry is
    not awareness-family. The one reader of a not-yet-committed condition's
    level, so the kind-word fallback cannot fork between the floors."""
    if not isinstance(cond, dict):
        return None
    kind_level = awareness_kind_level(cond.get("kind"))
    if kind_level is None:
        return None
    state = _condition_state(cond)
    return _awareness_level_from(kind_level, state.get("level"),
                                 cond.get("level"))


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
        "SELECT condition_id, subject_id, kind, payload, started_at "
        f"FROM world_conditions WHERE chat_id=? AND active=1 {_CONDITION_ORDER}",
        (chat_id,),
    ):
        kind_level = awareness_kind_level(row["kind"])
        if kind_level is None:
            continue
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
        level = _awareness_level_from(kind_level, state.get("level"),
                                      payload.get("level"))
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
    # ORDERED BY THE CLOCK THE RECORDS THEMSELVES PUBLISH. A payload's
    # `started_at_seconds` is the simulation clock and the column is the wall
    # clock they were written at; they disagree in live data (chat 23 holds
    # 180 against 130 on one row), so sorting on one while reporting the other
    # is two answers to when this started. Stable, so the SQL clause above
    # still breaks a tie.
    rows.sort(key=lambda r: r["started_at_seconds"])
    return rows


def _awareness_depth(level):
    """How far under a level is, on `AWARENESS_LEVELS`' own ordering."""
    try:
        return AWARENESS_LEVELS.index(level)
    except ValueError:
        return AWARENESS_LEVELS.index("dazed")


def awareness_map(chat_id):
    """Active `awareness` conditions for chat_id, keyed by casefolded subject
    name -> {subject, level, cause, rousable_by, condition_id}. Mirrors
    active_disguises. Only non-awake subjects appear; everyone else is awake by
    absence. `awareness_conditions` is the un-collapsed view, and the ending
    floor needs it: waking somebody deactivates every row, not this one.

    SEVERAL ROWS, ONE BODY, AND THE STORY'S ORDER DECIDES. The newest wins,
    because coming round is a real transition and the row that records it is
    the later one. Where two rows share a clock reading -- which is how a
    branch copy delivers them, the same shape `active_disguises` documents --
    nothing in the data says which came after, and the two answers are not
    equivalent: the deeper level gates the mind and the milder one hands it
    full perception, since `dazed` is not in `NON_AWAKE_GATED`. So a tie falls
    to the deeper level rather than to a rowid, and a body the story put under
    is never read as present by an accident of insertion order."""
    out = {}
    rank = {}
    for record in awareness_conditions(chat_id):
        key = record["subject"].casefold()
        order = (record["started_at_seconds"], _awareness_depth(record["level"]))
        if key in out and order <= rank[key]:
            continue
        rank[key] = order
        out[key] = {
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
            level = awareness_cond_level(cond)
            if level is None:
                continue
            subj = str(cond.get("subject_id") or "").strip()
            if not subj:
                continue
            key = subj.casefold()
            state = _condition_state(cond)
            if not int(cond.get("active", 1)) or level == "awake":
                out.pop(key, None)  # woke / condition ended this beat
                continue
            out[key] = {"subject": subj, "level": level,
                        "cause": str(state.get("cause") or "").strip(),
                        "rousable_by": str(state.get("rousable_by") or "").strip(),
                        # THE SAME SHAPE `awareness_map` PRODUCES, including
                        # the id an ending must re-emit: commit UPDATEs on
                        # `condition_id`, and a fresh one opens a second row
                        # instead of closing the first. A caller cannot be
                        # expected to know which of the two producers built
                        # the record it is holding.
                        "condition_id": str(cond.get("condition_id") or _cid)}
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
# Rungs that hold a body with nobody attending them: a knot stays tied and a
# casket stays shut when whoever closed it walks away. `held` is the live
# grip of another body and cannot outlive it; `pinned` is EITHER -- a body
# bearing down or a fallen mass -- so which it is is decided per record: a
# `pinned` that names a holder is a live hold, one that names none is
# standing weight. Whether a record blocks self-relocation is therefore not
# the rung alone: standing records always do, holds only while the named
# holder is co-present and conscious (the director floor's question, since it
# needs the scene), and a hold that names no holder never does -- measured
# live, the holderless "held" rows are embraces whose own descriptions say
# "not a binding restraint" and a body gripping a lever, not captives.
STANDING_RESTRAINTS = frozenset({"bound", "encased"})


#: The words a model writes when it means one of the four rungs. No prompt
#: publishes `RESTRAINT_LEVELS` -- the body specialist is handed a
#: parenthetical of examples, not a `level in {...}` clause of the kind
#: awareness gets one paragraph later -- and two of those very examples
#: ("grappled", "held hostage") were unreadable, so both landed on the
#: mildest rung. AGENTS.md states the rule for this shape in the weather
#: vocabulary: extend the synonyms rather than widen the enum, because a
#: silent fall to the default inverts the meaning of the beat.
#:
#: The distinction each rung names, so a new word can be placed without
#: guessing: `held` is a body holding a body, `bound` is a binding that
#: holds without anyone attending it, `pinned` is a body or a mass holding
#: another against something, `encased` is being closed inside.
_RESTRAINT_SYNONYMS = (
    ("encased", ("encased", "encase", "entombed", "entomb", "sealed", "seal",
                 "cocooned", "cocoon", "engulfed", "engulf", "swallowed",
                 "swallow", "buried", "bury", "enclosed", "walled")),
    ("pinned", ("pinned", "pin", "grappled", "grapple", "straddled",
                "straddle", "immobilised", "immobilized", "immobile",
                "trapped", "trap", "crushed", "crush", "wedged", "stuck",
                "weighed down", "held down")),
    ("bound", ("bound", "bind", "tied", "tie", "roped", "rope", "shackled",
               "shackle", "manacled", "manacle", "handcuffed", "cuffed",
               "cuff", "chained", "chain", "fettered", "fetter", "trussed",
               "truss", "strapped", "restrained", "restraint", "leashed",
               "netted")),
    ("held", ("held", "hold", "grabbed", "grab", "grasped", "grasp",
              "gripped", "grip", "clutched", "clutch", "clamped", "clamp",
              "hostage", "carried")),
)


def _normalize_restraint_level(raw):
    """One of `RESTRAINT_LEVELS`, from whatever the model actually wrote.

    Read DEEPEST-FIRST, because these arrive as phrases as often as tokens
    ("bound hand and foot", "held down against the flagstones") and a phrase
    naming two rungs means the stronger one: someone held down and bound is
    bound. Unknown wording is guessed at `held`, which claims least --
    including EMPTY wording: the live corpus holds a restraint row whose
    whole state is the string "active" (chat 44), and now that the rung
    decides whether a body can move with nobody holding it, handing the
    strongest reading (`bound`, immobilising forever) to the weakest
    evidence would jail a body on a record that says nothing.
    """
    level = str(raw or "").strip().casefold()
    if not level:
        return "held"
    if level in RESTRAINT_LEVELS:
        return level
    # `wrist_and_ankle_restraints_on_metal_chair` is a sentence a model wrote
    # in the only punctuation a token field invites. An underscore is a WORD
    # character to a regex, so word-boundary cues read the whole thing as one
    # unknown word unless the separators become separators.
    level = _re.sub(r"[^a-z0-9]+", " ", level).strip()
    for rung, cues in _RESTRAINT_SYNONYMS:
        for cue in cues:
            if _re.search(r"\b%ss?\b" % _re.escape(cue), level):
                return rung
    return "held"


#: Where the rung is written. `level` is what the schema asks for and what no
#: live row carries; `restraint_type` ("metal_cuffs", "chair_restraints") and
#: `type` ("grip", "held_in_embrace") are what beats actually use.
_RESTRAINT_LEVEL_FIELDS = ("level", "restraint_type", "type")

#: Where the holder is written. Live rows say `restrained_by: "Dr. Moon"`,
#: `blocked_by: "The Doctor"` and `enveloped_by: "Elyndra's entrance"` where
#: the schema would say `by`. Only holder-shaped names: `binding_to` and
#: `anchor` name what a binding is FASTENED to, which is standing hardware,
#: never a grip that a departure or a knockout could break.
_RESTRAINT_BY_FIELDS = ("by", "restrained_by", "held_by", "blocked_by",
                        "pinned_by", "enveloped_by")


#: The kinds a beat actually files a restraint under. `world_conditions.kind`
#: is free model text -- until the RESTRAINT block landed in the body
#: specialist's sheet, no prompt published a vocabulary for it, and what the
#: specialist was told was the phrase "physical restraint (bound, held
#: hostage, grappled, pinned)", from which `physical_restraint` is the
#: obvious token and the one that matches the engine's own
#: `physical_disguise` / `physical_transformation` besides. This reader asked
#: for `restraint`, which across the whole live corpus no beat has ever
#: written: 21 active rows say `physical_restraint` and 3 say `restrained`,
#: over fifteen chats, and the floor that stops a bound body walking out had
#: therefore never once fired.
#:
#: A FAMILY OF SPELLINGS, NOT ANYTHING WITH A BODY IN IT: containment and
#: contact are their own systems with their own consequences, and reading one
#: as a restraint would immobilise a body nothing is holding. `grip` stays
#: out for the measured reason that the live `grip` row is the subject doing
#: the gripping.
_RESTRAINT_KIND_WORDS = frozenset({
    "restraint", "restraints", "restrained", "restraining", "bound",
    "binding", "bindings",
})


def _is_restraint_kind(kind):
    """Is this condition kind one of the ways a restraint gets recorded?"""
    words = _re.split(r"[^a-z0-9]+", str(kind or "").casefold())
    return any(word in _RESTRAINT_KIND_WORDS for word in words)


def _restraint_field(state, payload, fields):
    for field in fields:
        raw = state.get(field) if isinstance(state, dict) else None
        if raw is None and isinstance(payload, dict):
            raw = payload.get(field)
        if str(raw or "").strip():
            return str(raw).strip()
    return ""


def _restraint_record(cond, condition_id, fallback_subject="",
                      row_started=None):
    """One restraint as a RELATION: who is held, at which rung, by whom,
    under which condition_id an ending must be re-emitted. None when the
    payload names no subject."""
    state = _condition_state(cond)
    subject = str((cond.get("subject_id") if isinstance(cond, dict) else "")
                  or fallback_subject or "").strip()
    if not subject:
        return None
    raw_level = _restraint_field(state, cond, _RESTRAINT_LEVEL_FIELDS)
    level = _normalize_restraint_level(raw_level)
    by = _restraint_field(state, cond, _RESTRAINT_BY_FIELDS)
    try:
        started = float(cond.get("started_at_seconds")
                        if cond.get("started_at_seconds") is not None
                        else row_started or 0.0)
    except (TypeError, ValueError):
        started = 0.0
    return {
        "condition_id": str(condition_id),
        "subject": subject,
        "level": level,
        "by": by,
        "means": str(state.get("means") or "").strip() or raw_level,
        "escapable_by": str(state.get("escapable_by") or "").strip(),
        # Does this record hold with nobody attending it? `bound`/`encased`
        # always; `pinned` only when it names no holder (a mass, not a body).
        "standing": (level in STANDING_RESTRAINTS
                     or (level == "pinned" and not by)),
        "started_at_seconds": started,
        "payload": cond if isinstance(cond, dict) else {},
    }


def restraint_conditions(chat_id):
    """EVERY active restraint condition row, uncollapsed, in the story's order.

    Mirrors `awareness_conditions`, and for the same reason: one body
    routinely carries several active rows at once (live chat 80 holds six
    redescriptions of the same cuffs), and RELEASING them means deactivating
    each by its own `condition_id` -- a caller holding only a collapsed map
    cannot end anything.
    """
    rows = []
    for row in q(
        "SELECT condition_id, subject_id, kind, payload, started_at "
        "FROM world_conditions WHERE chat_id=? "
        f"AND active=1 {_CONDITION_ORDER}", (chat_id,),
    ):
        if not _is_restraint_kind(row["kind"]):
            continue
        try:
            payload = json.loads(row["payload"])
        except (TypeError, ValueError):
            payload = {}
        if not isinstance(payload, dict):
            payload = {}
        record = _restraint_record(payload, row["condition_id"],
                                   fallback_subject=row["subject_id"],
                                   row_started=row["started_at"])
        if record:
            rows.append(record)
    # The clock the records themselves publish, exactly as
    # `awareness_conditions` sorts (the SQL clause above breaks ties).
    rows.sort(key=lambda r: r["started_at_seconds"])
    return rows


def apply_restraint_records_diff(records, diff):
    """Overlay a not-yet-committed diff's restraint conditions, so a binding
    applied THIS beat is in force for the same beat's resolution and a
    release this beat frees the body the same beat. Keyed by condition_id:
    a re-emission replaces its own record and an ending (falsy `active`)
    removes it, leaving the subject's OTHER records standing."""
    out = list(records or [])
    for _cid, cond_list in ((diff or {}).get("conditions") or {}).items():
        if not isinstance(cond_list, list):
            cond_list = [cond_list]
        for cond in cond_list:
            if not isinstance(cond, dict) or not _is_restraint_kind(
                    cond.get("kind")):
                continue
            cond_id = str(cond.get("condition_id") or _cid)
            out = [r for r in out if r["condition_id"] != cond_id]
            try:
                if not int(cond.get("active", 1)):
                    continue                # released this beat
            except (TypeError, ValueError):
                pass
            record = _restraint_record(cond, cond_id)
            if record:
                out.append(record)
    return out


def _restraint_depth(record):
    """How much a record claims: standing beats live, then the ladder, then
    recency -- so a vague late redescription cannot mask the cuffs."""
    try:
        rung = RESTRAINT_LEVELS.index(record["level"])
    except ValueError:
        rung = 0
    return (1 if record.get("standing") else 0, rung,
            record.get("started_at_seconds") or 0.0)


def restraint_map(chat_id_or_records):
    """Collapsed view: casefolded subject -> the STRONGEST active record.

    Restraints are additive facts, not exclusive states like awareness
    levels -- a body can be gripped AND cuffed, and each is separately true
    -- so the collapse takes the record that claims most rather than the
    newest. Only restrained subjects appear; everyone else is free by
    absence, so a chat that never restrains anyone is untouched.
    """
    records = (chat_id_or_records if isinstance(chat_id_or_records, list)
               else restraint_conditions(chat_id_or_records))
    out = {}
    for record in records:
        key = record["subject"].casefold()
        if key not in out or _restraint_depth(record) > _restraint_depth(out[key]):
            out[key] = record
    return out


def restraint_of(chat_id_or_records, name):
    """The strongest restraint record for `name`, or None when free
    (fail-open). Accepts a chat_id (queries), a record list, or a prebuilt
    restraint_map."""
    source = chat_id_or_records
    rmap = source if isinstance(source, dict) else restraint_map(source)
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

def scent_of(sheet):
    """What this body standingly smells of, whichever kind of card it is.

    The sibling of `senses_of` and `abilities_of`: a caller holding a sheet of
    unknown kind asks here. "" means the card says nothing, which is silence
    rather than an odourless body -- an authoring gap must never mint a
    percept.
    """
    if "psychology" in sheet or "core" in sheet:
        return character_scent(sheet)
    if "narration" in sheet:
        return persona_scent(sheet)
    return str(sheet.get("scent") or "").strip()

def name_of(sheet):
    if "psychology" in sheet or "core" in sheet:
        return character_name(sheet)
    return persona_name(sheet)

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
# That enum and `docs/design/OFFSCREEN_LIFE_DESIGN.md` have specified this ladder
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
#   reactive         The above, plus firing a bounded, already-adjudicated
#                    stage from a typed character-owned plan when its time or
#                    event trigger lands. No model call and no new invention.
#   stochastic       The above, plus seeded ticks for dormant actors at a
#                    frame-scoped world epoch, bounded by
#                    `max_offscreen_actors` and written
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
#                    Permission AND behaviour, since the full rung landed
#                    (`offscreen.schedule_agent_ticks`): an explicitly
#                    opted-in dormant character with a private reason gets
#                    one reduced turn per world epoch -- ONE character call
#                    over the fail-closed `offscreen.agent_context`, ONE
#                    Director adjudication, one atomic landing. The
#                    knowledge firewall that `docs/design/OFFSCREEN_LIFE_DESIGN.md`
#                    decision 2 insists on is structural, not prompted: a
#                    ticking character advances on ITS OWN knowledge --
#                    sheet, memories, beliefs, plans, carried reports --
#                    never the player's location or recent actions, or the
#                    result is the spookily prescient antagonist this
#                    architecture exists to avoid. Only the Director half of
#                    the tick may declare a consequence, and it lands
#                    through the same validator every other fuse passes.
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
    "reactive": "…plus firing authored plan stages on typed triggers",
    "stochastic": "…plus seeded ticks for dormant actors at world epochs",
    "character_agent": "…plus opted-in characters advancing their own plans",
}

# Which rungs actually do something today, for the UI to mark. Kept beside the
# ladder rather than in the UI so an unbuilt rung cannot quietly start reading
# as built when it ships and nobody updates the menu. `character_agent` landed
# with `offscreen.schedule_agent_ticks`: one reduced, Director-adjudicated
# off-screen turn per world epoch for opted-in dormant minds with a private
# reason to act.
OFFSCREEN_LIFE_BUILT = frozenset({
    "inert", "deterministic", "reactive", "stochastic", "character_agent",
})


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
    """The per-beat budget an autonomy rung buys.

    Two numbers, not four. This used to carry `max_director_calls` and
    `max_perception_calls` as well, from a design where the interaction loop
    called both per micro-round. Neither survived: the Director is now a PLAN
    stage (`director_interpret`/`director_resolve`), so how many times it runs
    is decided by `agents/runtime.build_plan` and not by a dial, and
    perception is deterministic -- there is no `perception` model role at all,
    so a budget on perception CALLS bounds nothing that costs anything. They
    were still derived per rung and persisted by the dialogue route, which is
    the worst arrangement available: a maintained ladder of four numbers of
    which two were decoration (AUDIT_MINDS finding 9).
    """
    try:
        value = max(0, min(100, int(autonomy)))
    except Exception:
        value = 50
    presets = [
        (0, {"max_micro_rounds": 1, "max_character_calls": 1}),
        (25, {"max_micro_rounds": 2, "max_character_calls": 3}),
        (50, {"max_micro_rounds": 4, "max_character_calls": 6}),
        (75, {"max_micro_rounds": 7, "max_character_calls": 10}),
        (100, {"max_micro_rounds": 12, "max_character_calls": 18}),
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

#: What each mode grants the player, as the ladder `Design.md` states it. The
#: default is today's behaviour, so an existing story's meaning does not change
#: under it: nothing is enforced until a host chooses to enforce something.
PLAYER_AUTHORITY_MODES = ("actor_only", "explicit_outcomes", "world_author")
DEFAULT_PLAYER_AUTHORITY = "world_author"

#: Which claim kinds each mode GRANTS as already-true. Everything a mode does
#: not grant survives as a declaration the Director adjudicates -- it is never
#: deleted, because deleting player text is the one thing this engine's
#: authority contract has never done and hard mode must not become the
#: exception (`Design.md`, hard mode, design note 1).
#:
#:   own_body   -- an asserted effect on the player's own body. Granted by
#:                 every mode: "attempts, speech, and immediate bodily
#:                 conduct" is the floor, not a grant.
#:   own_effect -- a completed effect the player declares their own action had
#:                 on something else ("I pick the lock and it opens").
#:   world      -- an actor-less assertion about the world ("two guards come
#:                 around the corner"), which is authorship rather than
#:                 conduct.
PLAYER_AUTHORITY_GRANTS = {
    "actor_only": frozenset({"own_body"}),
    "explicit_outcomes": frozenset({"own_body", "own_effect"}),
    "world_author": frozenset({"own_body", "own_effect", "world"}),
}


def normalize_player_authority(value):
    mode = str(value or "").strip().lower()
    return mode if mode in PLAYER_AUTHORITY_MODES else DEFAULT_PLAYER_AUTHORITY


def player_authority(chat_id):
    """This story's player-authority mode and the record of it changing.

    Per chat rather than global, and the change history is stored WITH it,
    because changing the mode mid-story changes what the earlier turns meant --
    a beat where the player asserted a world fact and got it reads as a bug
    once the story is in `actor_only`, and the only thing that can explain it
    is knowing when the dial moved.

    Returns `{"mode": ..., "changes": [{"turn_idx": n, "mode": ...}, ...]}`.
    """
    stored = wget(chat_id, "player_authority", None)
    if isinstance(stored, str):          # tolerated shorthand
        stored = {"mode": stored}
    if not isinstance(stored, dict):
        stored = {}
    changes = [
        {"turn_idx": item.get("turn_idx"),
         "mode": normalize_player_authority(item.get("mode"))}
        for item in (stored.get("changes") or []) if isinstance(item, dict)
    ]
    return {"mode": normalize_player_authority(stored.get("mode")),
            "changes": changes}


def set_player_authority(chat_id, mode, *, turn_idx=None):
    """Choose this story's mode, appending to the change record.

    Idempotent: re-selecting the current mode records nothing, so a host panel
    that saves on every render cannot turn the history into noise.
    """
    mode = normalize_player_authority(mode)
    current = player_authority(chat_id)
    if mode == current["mode"] and (current["changes"] or mode ==
                                    DEFAULT_PLAYER_AUTHORITY):
        return current
    changes = current["changes"] + [{"turn_idx": turn_idx, "mode": mode}]
    wset(chat_id, "player_authority", {"mode": mode, "changes": changes[-40:]})
    return player_authority(chat_id)


def background_config(chat_id):
    """Config for the background_react stage. `max_reactors` bounds how many
    unregistered presences may voice a single beat (default 1 -- the historical
    single-winner behavior; raise to stage ensemble beats). Hard-capped at 3 in
    background_react: past that, a crowd is better represented as one chorus
    presence than as several individually-voiced extras.

    `scene_life` selects the scene-manager path (docs/design/BACKGROUND_LIFE_DESIGN.md
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
    from persist.commit import (BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD,
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
        extra_parts = character_extra_parts(sheet)
        result.append({
            "id": int(row["id"]),
            "entity_id": cast_entity_id(sheet, row["id"]),
            "name": character_name(sheet),
            "aliases": identity.get("aliases") or [],
            "appearance": character_appearance(sheet),
            # Authored structured extra body parts. Key absent for the
            # ordinary body so existing payloads are byte-identical.
            **({"extra_parts": extra_parts} if extra_parts else {}),
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
