"""Unregistered background presences: identity folding, per-beat tracking,
the deterministic reactor gate, and promotion to cast.

Extracted verbatim from commit.py, which re-exports every name here. The
deferred function-body imports (scene, schemas, importers,
background_claims) are the existing cycle-breakers and stay deferred.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import copy, hashlib, json, re, time, uuid
from core.db import q, qi, wget, wset, get_setting
from mind.memory import add_memories_batch
from story.character_schema import (character_name, character_initial_outfit,
                              character_initial_active_state,
                              normalize_character_data, persona_name)
from story.scene import seed_initial_attire
from world.spatial import room_of, spatial_rel, hear_level, _is_body_entity
from persist.commit_common import (_player_name_or_none,
                                   _registered_name_roster, _room_of,
                                   recognition_roster, seed_mutual_recognition)


# ---- Background-presence tracking (promotion candidates) ----

# Defaults, not fixed law. How many lines a bystander must speak before the
# engine offers to give them a mind is an authorial pacing choice: a talky
# tavern wants a high bar, a two-hander wants a low one. Overridable per chat
# via the `promotion_thresholds` world key (see scene.promotion_config).
BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD = 2
BACKGROUND_PROMOTION_MENTION_THRESHOLD = 4


def promotion_thresholds(chat_id):
    """Per-chat promotion thresholds, falling back to the module defaults."""
    try:
        from story.scene import promotion_config
        return promotion_config(chat_id)
    except Exception:
        return {
            "dialogue": BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD,
            "mention": BACKGROUND_PROMOTION_MENTION_THRESHOLD,
            "auto_dialogue": AUTO_PROMOTE_DIALOGUE_THRESHOLD,
        }

_BACKGROUND_NAME_TITLE_WORDS = {
    "dr", "mr", "mrs", "ms", "the", "a", "an", "captain", "commander",
    "lieutenant", "sir", "madam", "professor", "doctor",
}

# Ranks and honorifics the Director routinely prefixes to a name that the
# roster stores bare ("Jean-Luc Picard" vs "Captain Jean-Luc Picard"). Kept
# SEPARATE from _BACKGROUND_NAME_TITLE_WORDS above, which feeds
# _background_name_mentioned's significant-word matching -- widening that set
# would silently make mention-detection stricter for short names.
_NAME_TITLE_PREFIXES = frozenset({
    "dr", "mr", "mrs", "ms", "mister", "madam", "madame", "sir", "lord",
    "lady", "master", "professor", "doctor", "captain", "commander",
    "cmdr", "lieutenant", "lt", "ensign", "chief", "admiral", "general",
    "colonel", "major", "sergeant", "corporal", "private", "father",
    "mother", "sister", "brother", "reverend", "king", "queen", "prince",
    "princess", "the", "a", "an",
})


def strip_name_titles(name):
    """A display name with leading ranks/honorifics removed.

    The Director writes "Captain Jean-Luc Picard" where the cast roster holds
    "Jean-Luc Picard", and "Lieutenant Worf" where a later line just says
    "Worf". Exact-casefold comparison misses both, which in the Enterprise run
    tracked a REGISTERED character as a background presence and handed him to
    the stateless scene manager as furniture.
    """
    words = str(name or "").strip().split()
    while words and words[0].strip(".,").casefold() in _NAME_TITLE_PREFIXES:
        words = words[1:]
    return " ".join(words).strip() or str(name or "").strip()


def name_in_roster(name, roster):
    """True when `name` denotes someone already registered (cast, persona,
    extra player), comparing bare and title-stripped forms in both directions.
    `roster` is a set of casefolded names."""
    cf = str(name or "").strip().casefold()
    if not cf:
        return False
    if cf in roster:
        return True
    bare = strip_name_titles(name).casefold()
    if bare and bare in roster:
        return True
    return any(bare and bare == strip_name_titles(r).casefold() for r in roster)


_PRESENCE_ARTICLES = ("a ", "an ", "the ")


def _presence_identity(name):
    """What makes two background names the SAME presence.

    The ledger is keyed by whatever string the prose used, and the prose does
    not hold a determiner steady: chat 57 accumulated `A Dalek`, `Dalek` and
    `The Dalek` as three separate presences for the one Dalek standing in the
    one room. Each carried its own dialogue history, so the same creature had
    three partial memories of itself and none of them knew what the others
    said; `max_managed` counted all three against a cap of six; and promotion
    thresholds were measured against a third of the evidence.

    Articles only, deliberately. Titles are NOT stripped here -- `strip_name_titles`
    exists for roster matching, where "Dr. Crusher" and "Crusher" are one
    person, but among unregistered background figures a title is often the only
    thing telling two of them apart ("the guard" and "the captain" are not one
    presence). An article never distinguishes anybody.
    """
    cf = " ".join(str(name or "").split()).casefold()
    for article in _PRESENCE_ARTICLES:
        if cf.startswith(article):
            cf = cf[len(article):].strip()
            break
    return cf


# ---- Presence identity: durable uid keys ----
#
# The ledger keys each record on a minted `uid`, never on a name. A name is an
# ATTRIBUTE (`record["name"]`, with former spellings in `aka`), so a rename is
# a field update rather than a new person, two people who share a name stay two
# records, and an id stored where a name should be cannot be confused with one.
# Models will speak names forever, so name-to-record resolution
# (`presence_record_for`) is permanent infrastructure, not migration scaffolding.

PRESENCE_UID_PREFIX = "p_"
_PRESENCE_UID_RE = re.compile(r"p_[0-9a-f]{16}")
# An id-shaped string is not a name (one live ledger stored three raw entity
# ids in its name fields). Mirrors llm/schemas._OPAQUE_ID.
_OPAQUE_NAME_RE = re.compile(r"(?:[0-9a-f]{12,}|[0-9]{6,})", re.I)


def _mint_presence_uid(seed=None):
    """A fresh presence uid. With `seed`, DETERMINISTIC: the same binding
    always mints the same uid, so a pre-commit reader (the reactor gate) and
    the commit writer agree on a record's key before anything is persisted,
    and two legacy records that prove the same binding converge on one key --
    which is how the load-time migration merges exactly what id agreement
    proves and nothing else."""
    if seed is not None:
        digest = hashlib.sha1(str(seed).encode("utf-8")).hexdigest()
        return PRESENCE_UID_PREFIX + digest[:16]
    return PRESENCE_UID_PREFIX + uuid.uuid4().hex[:16]


def is_presence_uid(value):
    """Does this string have the shape of a minted presence key?"""
    return bool(_PRESENCE_UID_RE.fullmatch(str(value or "")))


def presence_display_name(key, record=None):
    """The name a tracked presence answers to. The ledger keys on a minted
    uid and the name is an attribute; a legacy record not yet migrated is
    keyed BY its name, so the key doubles as the fallback."""
    if isinstance(record, dict):
        name = str(record.get("name") or "").strip()
        if name:
            return name
    key = str(key or "").strip()
    return "" if is_presence_uid(key) else key


def presence_name_items(presences):
    """(display name, record) pairs for iteration. Every reader that used to
    read the dict key as the name reads this instead; a legacy name-keyed
    ledger passes through unchanged."""
    out = []
    for key, record in (presences or {}).items():
        record = record if isinstance(record, dict) else {}
        name = presence_display_name(key, record)
        if name:
            out.append((name, record))
    return out


def presence_is_unnamed(key, record=None):
    """True when this presence has no real name to be known by: none at all,
    or an id-shaped string standing where a name should (a live ledger
    tracked `a23653c914bf40a8` and two siblings as 'names'). Such a record is
    still a person the engine keeps -- but nothing may treat the string AS a
    name: promotion must not mint a sheet under it, and any naming surface
    should treat the presence as awaiting one."""
    name = presence_display_name(key, record)
    if not name:
        return True
    return bool(_OPAQUE_NAME_RE.fullmatch(re.sub(r"[\s_\-]+", "", name)))


def _charter_uid_seed(record):
    """The deterministic uid seed a charter-bound record keys on: the charter
    body key is permanent identity (AGENTS.md's charter section), so it
    outranks every other binding."""
    for ref in ((record or {}).get("charter_refs") or []):
        if isinstance(ref, dict) and ref.get("charter") and ref.get("body"):
            return "charter:%s:%s" % (ref["charter"], ref["body"])
    return None


def _entity_key_for_name(name, scene):
    """The scene-entity KEY this name is a respelling of, or None.
    Underscore-as-space equivalence on the KEY only ('station engineer'
    names the entity keyed `station_engineer`) -- the same doctrine the
    tracker's inert-verdict index applies to entity keys; display names get
    identity matching (`_entity_uid_answering_to`) instead."""
    folded = re.sub(r"[\s_]+", " ", str(name or "")).strip().casefold()
    if not folded:
        return None
    for eid, ent in ((scene or {}).get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        if re.sub(r"[\s_]+", " ", str(eid)).strip().casefold() == folded:
            return str(eid)
    return None


def _bodies_answering_to(identity, scene):
    """How many entities in the scene answer to this identity.

    The scene is the authority on how many bodies exist -- names are not.
    "A Dalek" and "The Dalek" are the same creature when the room holds one
    Dalek and two different ones when it holds two, and nothing in the strings
    themselves can tell those apart. That ambiguity is a real property of a
    generic name, not a bug in the matching: a fiction with three Daleks needs
    three names, and until it has them the engine should not guess.

    So merging is gated on the scene showing at most ONE such body. With two,
    the separate ledgers are left alone -- an over-merge silently welds two
    characters into one, which is worse than a split that a name would fix.
    """
    identity = str(identity or "")
    if not identity:
        return 0
    seen = 0
    for entity in ((scene or {}).get("entities") or {}).values():
        if not isinstance(entity, dict):
            continue
        if _presence_identity(entity.get("name")) == identity:
            seen += 1
    return seen


def _entity_uid_answering_to(name, entity_names_by_id):
    """The ONE entity id this name denotes, or None.

    `entity_names_by_id` is {entity_id: display_name}. Matching is by
    `_presence_identity` (articles ignored, titles kept), and the answer is
    an id only when EXACTLY one body answers -- the same crowd guard
    `_bodies_answering_to` applies to merging: with two Daleks in the room
    the name binds to neither, because guessing welds two characters into
    one. This binding is what lets a presence survive its body being
    RENAMED: "the guard" and "Mara" share no string identity, but a record
    bound to the guard's entity id follows that id to whatever the scene
    now calls it (docs/UNBUILT.md 1.17's fragmentation half)."""
    identity = _presence_identity(name)
    if not identity:
        return None
    matches = [
        eid for eid, nm in (entity_names_by_id or {}).items()
        if _presence_identity(nm) == identity
    ]
    return str(matches[0]) if len(matches) == 1 else None


def _scene_entity_names_by_id(scene):
    """{entity_id: display_name} for every named scene entity."""
    return {
        str(eid): str(ent.get("name") or "").strip()
        for eid, ent in ((scene or {}).get("entities") or {}).items()
        if isinstance(ent, dict) and str(ent.get("name") or "").strip()
    }


def _presence_names(name_or_key, record):
    """Every spelling this record has answered to: its current display name
    plus the former names `aka` carries. Prose does not switch spellings
    overnight -- "the guard" in a later resolved_event still means Mara -- so
    mention and addressed matching must hear the old names too."""
    names = []
    display = presence_display_name(name_or_key, record)
    if display:
        names.append(display)
    for alias in ((record or {}).get("aka") or []):
        alias = str(alias or "").strip()
        if alias and alias not in names:
            names.append(alias)
    return names


def _canonical_presence_name(name, scene):
    """The display-name spelling of a name that is really an entity ID.

    A scene entity carries two spellings of one identity: the opaque id
    keying `scene.entities`/`scene.positions` ("cfc004eb2c174286") and the
    human display name in its def ("Scranton Reality Anchors"). The dialogue-
    speaker harvest has folded ids to names for a while, but the positions
    harvest did not, so one body tracked through both fields became TWO
    presences -- chat 80 held six entries for three things, and each id-keyed
    twin accrued its own dialogue history and its own separately-minted
    personality. One being, one name: anything about to become a presence key
    resolves through here first.
    """
    raw = str(name or "").strip()
    if not raw:
        return raw
    ent = ((scene or {}).get("entities") or {}).get(raw)
    if isinstance(ent, dict):
        display = str(ent.get("name") or "").strip()
        if display and display.casefold() != raw.casefold():
            return display
    return raw


def _presence_scene_entity(scene, name, record=None):
    """The scene entity a presence name denotes -- by entity id or display
    name -- as (entity_id, entity_def), or (None, None) when the name has no
    entity record at all (a presence tracked from a dialogue speaker or a
    bare positions key). With `record`, its stored `entity_id` binding
    outranks every string comparison: an id denotes exactly one body, it
    survives a rename, and it cannot be fooled by a second entity sharing
    the display name."""
    bound = str((record or {}).get("entity_id") or "").strip()
    if bound:
        ent = ((scene or {}).get("entities") or {}).get(bound)
        if isinstance(ent, dict):
            return bound, ent
    cf = str(name or "").strip().casefold()
    if not cf:
        return None, None
    for eid, ent in ((scene or {}).get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        if (str(eid).strip().casefold() == cf
                or str(ent.get("name") or "").strip().casefold() == cf):
            return eid, ent
    return None, None


def presence_room(scene, name, record=None):
    """Where a tracked presence is STANDING: its own scene position, its
    entity id's position, or -- only when the scene places it nowhere -- the
    room its sketch was harvested in.

    One answer, because there were two. The scene-manager path resolved the
    live position; the per-presence path and this module's gate read
    `sketch.station_room`, which is where the presence stood when it was
    INTRODUCED (`track_background_presences` harvests it once). So a presence
    who had since walked out was gated, addressed and fed its beat at a room
    it had left, while the other path, on the same beat, used the room it was
    in. Nothing reconciled them, and neither is wrong-looking on its own.
    """
    scene = scene or {}
    room = room_of(scene, name)
    if room:
        return room
    eid, _ent = _presence_scene_entity(scene, name, record)
    if eid:
        room = (scene.get("positions") or {}).get(eid) or room_of(scene, eid)
        if room:
            return room
    return ((record or {}).get("sketch") or {}).get("station_room")


def presence_has_an_identity(scene, name, record=None):
    """Is this presence's NAME somebody's to withhold?

    The identity floor exists because a stranger's name is theirs to give. An
    object has no such claim: a body in the room can read "Scranton Reality
    Anchors" off the wall, and doing so tells it nothing about a person. So
    the floor asks personhood before it protects a name -- and where the
    answer is `undecided` it asks for CONDUCT, which is this engine's standard
    of proof everywhere else.

    THE NOUN CANNOT SETTLE IT, and both live examples prove it: `device` and
    `dalek war machine` land in `undecided` together, one a suppression
    fixture and one a body whose name absolutely is an identity. Measured
    across the corpus: 16 presences resolve `undecided` -- 14 machines
    (device, transit_car, body_interior) and 2 Daleks -- and the Daleks are
    the only two that have ever SPOKEN (2 and 10 dialogue turns against 0 for
    every machine). Something that has taken a turn at speech is acting as a
    person whatever noun the model reached for.

    Deliberately NOT the same reading as `presence_personhood`'s speech gate,
    which keeps `undecided` mute unless the Director routes it explicitly. The
    two gates ask different questions of one verdict: may this thing act (be
    conservative, silence is cheap) versus is this name protected (be
    conservative the other way, a wrongly-protected name renders a machine as
    "the unfamiliar person" in the room's own description).

    The gap left open: a genuine person who has never spoken AND whose kind is
    neither animate nor inert. Narrow -- an unregistered body has no entity
    record at all, which already answers "person" -- and the cost is one name
    reaching an observer through the same room note that describes the room.
    The real answer is `blurb_mint`'s `nature` field, which settles this per
    presence and today only runs under `scene_life: ambient|full`; see
    `docs/UNBUILT.md` 1.71.
    """
    verdict = presence_personhood(scene, name, record)
    if verdict == "person":
        return True
    if verdict == "thing":
        return False
    return bool((record or {}).get("dialogue_turns"))


def presence_personhood(scene, name, record=None):
    """What a tracked presence DENOTES: "person", "thing" or "undecided".

    Public because two different gates need the same answer and used to have
    only one of them. This one decides whether a presence may SPEAK; the
    identity floor (`perception._composer_identity_space`) decides whether its
    name must be concealed from someone who has not met it, and an object's
    name is nobody's to withhold -- a body in the room can read "Scranton
    Reality Anchors" off the wall, and doing so tells it nothing about a
    person. Answering that question from `background_presences` alone put
    machines into the identity space, where every one of them rendered as
    "the unfamiliar person" (chat 82 t1: the room note "Scranton Reality
    Anchors powered on and functional" reached the player as "the unfamiliar
    person powered on and functional", sharing a label with the guard who was
    actually speaking).
    """
    return _presence_speech_verdict(scene, name, record)


def _presence_speech_verdict(scene, name, record=None):
    """May this presence hold a background SPEAKING turn?

    A background reaction is a person's -- the whole stage exists to make
    extras feel like people (docs/design/BACKGROUND_LIFE_DESIGN.md), and the
    director_resolve prompt is explicit that bodiless voices are the
    Director's to speak and "never get a character step". Yet the gate never
    once asked what a tracked name DENOTES: it read only the ledger, so any
    record with history qualified. Chat 80 turns 3 and 7: the Scranton
    Reality Anchors -- kind "device", a ceiling-mounted suppression fixture
    -- were picked at their "post" in the interview cell and interrogated the
    restrained player twice, rendered as "the unfamiliar person" because a
    device has no name anyone knows.

    The scene is the authority on what a name denotes, and it answers in
    three grades:

    - "person": no entity record at all (provenance is already person-shaped
      -- a dialogue speaker or a placed body, like chat 72's night clerk), an
      animate kind (schemas._ANIMATE_ENTITY_KINDS, whole or word-wise so
      "security guard" counts), or no kind to judge.
    - "thing": a bodiless voice (scene.is_ubiquitous_entity -- the Director's
      own mouth) or a thing (_is_inert_presence_candidate -- chat 75's shed
      utility sash got three turns of housekeeper dialogue through exactly
      this hole). Never speaks through this stage.
    - "undecided": a kind neither animate nor inert. Deliberately possible:
      the kind string cannot lexically separate a suppression device from a
      "dalek war machine" (live kinds include both), so where the record
      cannot decide, personhood is the Director's call -- only its explicit
      judgments this beat (routed_to_background, flow.addressed_to) may give
      such a presence a voice. Ambient salience (at post, mentioned, its own
      accrued backstop lines) never does.
    """
    # THE FROZEN ANSWER OUTRANKS EVERY GUESS BELOW. `blurb_mint` visits each
    # newly tracked presence once, with its place, the Director's description
    # and the genre in front of it, and now answers what the thing IS
    # (schemas.PRESENCE_NATURES). That is a judgement about this presence in
    # this story; everything after it is inference from a noun the model chose
    # in passing. An unanswered `nature` is deliberately NOT a yes -- reading
    # an unasked question as "person" is the whole defect this closes -- so a
    # blank falls through to the graded guesses.
    nature = str((record or {}).get("nature") or "").strip().casefold()
    if nature == "person":
        return "person"
    if nature in ("thing", "voice"):
        return "thing"

    eid, ent = _presence_scene_entity(scene, name, record)
    if ent is None:
        return "person"
    try:
        from story.scene import is_ubiquitous_entity
        if is_ubiquitous_entity(ent):
            return "thing"
    except Exception:
        pass
    if _is_inert_presence_candidate(scene, eid, ent):
        return "thing"
    kind = str(ent.get("kind") or "").strip().casefold()
    if not kind:
        return "person"
    from llm.schemas import _ANIMATE_ENTITY_KINDS
    if kind in _ANIMATE_ENTITY_KINDS:
        return "person"
    if any(w in _ANIMATE_ENTITY_KINDS for w in re.split(r"[^a-z0-9]+", kind)):
        return "person"
    return "undecided"


def _merge_presence_record(target, other):
    """Fold one presence record into another, in place. The target keeps its
    own blurb (blurbs are frozen -- the anchor against self-feeding drift)
    and its own sketch entries; histories union; the recent-conduct tail
    interleaves by turn and keeps the cap."""
    for field in ("dialogue_turns", "mention_turns", "addressed_turns",
                  "engaged_turns"):
        merged = set(target.get(field) or []) | set(other.get(field) or [])
        if merged:
            target[field] = sorted(merged)
    if other.get("first_turn") is not None:
        target["first_turn"] = min(
            target.get("first_turn", other["first_turn"]),
            other["first_turn"])
    if other.get("last_turn") is not None:
        target["last_turn"] = max(
            target.get("last_turn", other["last_turn"]),
            other["last_turn"])
    # A sketch the duplicate carried is still objective description of
    # the same body; keep anything the keeper is missing.
    for key, value in (other.get("sketch") or {}).items():
        target.setdefault("sketch", {}).setdefault(key, value)
    if other.get("pending_reply") and not target.get("pending_reply"):
        target["pending_reply"] = other["pending_reply"]
    if other.get("blurb") and not target.get("blurb"):
        target["blurb"] = other["blurb"]
    tail = list(target.get("recent") or []) + list(other.get("recent") or [])
    if tail:
        tail.sort(key=lambda r: (r or {}).get("turn") or 0)
        target["recent"] = tail[-BACKGROUND_RECENT_TAIL:]
    # An id denotes exactly one body: whichever side knows it, keep it.
    if other.get("entity_id") and not target.get("entity_id"):
        target["entity_id"] = other["entity_id"]
    if other.get("nature") and not target.get("nature"):
        target["nature"] = other["nature"]
    for ref in (other.get("charter_refs") or []):
        if ref not in target.setdefault("charter_refs", []):
            target["charter_refs"].append(copy.deepcopy(ref))
    for alias in (other.get("aka") or []):
        if alias not in target.setdefault("aka", []):
            target["aka"].append(alias)
    # The absorbed record's own spellings and keys stay resolvable: its name
    # becomes an alias, and its uid (plus any it had absorbed in turn) joins
    # `former_uids` so a stale reference -- a promotable row held open in a
    # UI, a reader mid-beat -- still finds the merged record.
    other_name = str(other.get("name") or "").strip()
    target_name = str(target.get("name") or "").strip()
    if other_name and other_name != target_name:
        if other_name not in target.setdefault("aka", []):
            target["aka"].append(other_name)
    for former in [other.get("uid")] + list(other.get("former_uids") or []):
        former = str(former or "")
        if (former and former != target.get("uid")
                and former not in target.setdefault("former_uids", [])):
            target["former_uids"].append(former)
    if not target.get("former_uids", True):
        del target["former_uids"]


def _presence_lookup(presences, ref, scene=None):
    """Resolve `ref` -- a model-authored name, a presence uid, a former uid,
    or a scene entity id -- to ``(key, record, status)``.

    `status` is "hit", "miss", or "ambiguous". Ambiguity is its own answer,
    distinct from a miss, because the two demand opposite reactions: a miss
    may mint, while two records answering to one name must REFUSE to guess --
    picking one hands a person somebody else's history, and minting a third
    invents a stranger (`room_of`'s refuse-to-pick precedent).
    """
    presences = presences or {}
    ref = str(ref or "").strip()
    if not ref:
        return None, None, "miss"
    record = presences.get(ref)
    if record is not None:
        return ref, record, "hit"
    for key, rec in presences.items():
        if isinstance(rec, dict) and ref in (rec.get("former_uids") or ()):
            return key, rec, "hit"
    # A scene entity id: a stored binding, or the raw key models sometimes
    # write where a name belongs. An id denotes exactly one body, so a single
    # binding match settles it.
    entity_matches = [
        (key, rec) for key, rec in presences.items()
        if isinstance(rec, dict) and str(rec.get("entity_id") or "") == ref
    ]
    if len(entity_matches) == 1:
        return entity_matches[0][0], entity_matches[0][1], "hit"
    name = _canonical_presence_name(ref, scene)
    identity = _presence_identity(name)
    if not identity:
        return None, None, "miss"
    exact, folded = [], []
    for key, rec in presences.items():
        names = _presence_names(key, rec if isinstance(rec, dict) else None)
        if any(str(n).casefold() == name.casefold() for n in names):
            exact.append((key, rec))
        elif any(_presence_identity(n) == identity for n in names):
            folded.append((key, rec))
    if len(exact) == 1:
        return exact[0][0], exact[0][1], "hit"
    if len(exact) > 1:
        return None, None, "ambiguous"
    if folded and _bodies_answering_to(identity, scene) > 1:
        return None, None, "miss"   # a crowd; the article may be doing work
    if len(folded) == 1:
        return folded[0][0], folded[0][1], "hit"
    if len(folded) > 1:
        return None, None, "ambiguous"
    # No string identity matches -- but the BODY might already be tracked
    # under a former name (an entity renamed "the guard" -> "Mara" shares no
    # identity across the rename). When this name denotes exactly one scene
    # entity and some record is bound to that entity's id, that record is it.
    eid = (_entity_key_for_name(name, scene)
           or _entity_uid_answering_to(name, _scene_entity_names_by_id(scene)))
    if eid:
        for key, rec in presences.items():
            if (isinstance(rec, dict)
                    and str(rec.get("entity_id") or "") == eid):
                return key, rec, "hit"
    return None, None, "miss"


def presence_record_for(presences, ref, scene=None):
    """``(key, record)`` for the tracked presence `ref` denotes, else
    ``(None, None)`` -- including when two tracked records answer to one name,
    because two people can share a name now and guessing between them would
    hand one person the other's history. Callers already treat a missing
    record as "untracked", which is exactly the right reading of a refusal.
    This seam is permanent, not transitional: models speak names, the ledger
    keys on uids, and this is the one function that connects them."""
    key, record, status = _presence_lookup(presences, ref, scene)
    if status != "hit":
        return None, None
    return key, record


def _resolve_or_mint_presence(name, presences, scene=None, entity_id=None):
    """The uid key `name` should be filed under, minting the record slot when
    nothing tracked answers to it. THE MINT IS A WRITE: a uid is minted once
    and every later spelling resolves to it, which is what makes "a name,
    once minted, is permanent" enforceable rather than requested. With
    `entity_id`, the binding outranks every string test -- an id denotes
    exactly one body -- and the uid is deterministic in it. Returns None when
    two tracked records answer to the name and nothing this beat tells them
    apart: refusing to guess neither merges strangers nor mints a third.
    """
    name = _canonical_presence_name(name, scene)
    if entity_id:
        entity_id = str(entity_id)
        for key, rec in (presences or {}).items():
            if (isinstance(rec, dict)
                    and str(rec.get("entity_id") or "") == entity_id):
                return key
        # A record tracked from a nameless channel (a dialogue speaker, a
        # bare positions key) has no binding yet; an unambiguous name match
        # connects them once, and the binding does the work thereafter. A
        # name match already bound to a DIFFERENT body falls through to the
        # mint: same name, two bodies, two records -- the point of the key.
        key, rec, status = _presence_lookup(presences, name, scene)
        if (status == "hit" and isinstance(rec, dict)
                and not rec.get("entity_id")):
            rec["entity_id"] = entity_id
            return key
        key = _mint_presence_uid("entity:%s" % entity_id)
        record = presences.setdefault(key, {})
        record["uid"] = key
        record.setdefault("entity_id", entity_id)
        if not str(record.get("name") or "").strip():
            record["name"] = name
        return key
    key, _record, status = _presence_lookup(presences, name, scene)
    if status == "hit":
        return key
    if status == "ambiguous":
        return None
    eid = (_entity_key_for_name(name, scene)
           or _entity_uid_answering_to(name, _scene_entity_names_by_id(scene)))
    if eid:
        return _resolve_or_mint_presence(name, presences, scene,
                                         entity_id=eid)
    key = _mint_presence_uid()
    presences[key] = {"uid": key, "name": name}
    return key


def _fold_duplicate_presences(presences, scene=None):
    """Migrate a legacy name-keyed ledger onto uid keys, and merge records
    that are provably one body. Runs on load, so every existing story
    converts on its next read instead of needing a SQL migration --
    `background_presences` is a frame-scoped world key riding the whole-
    `world` carriage, and heal-on-load has been this fold's contract all
    along. Idempotent: a migrated ledger passes through with only the
    provable merges re-checked.

    THE MIGRATION IS TIERED, and every uid it mints is deterministic, so
    repeated un-persisted loads agree with each other and with the commit
    that finally writes the result:

      1. a record carrying a charter binding keys on it (a charter body key
         is permanent identity);
      2. a record that provably binds to ONE scene entity keys on the entity
         id -- including a name that is the entity KEY under underscore-as-
         space equivalence, which is how two spellings of one person merge on
         ID AGREEMENT (both bind to the same body) rather than on string
         similarity;
      3. everything else mints fresh from its own legacy key, which merges
         nothing and risks nothing.

    Ambiguity refuses to merge, unchanged (docs/UNBUILT.md 1.17's settled
    rule): an over-merge welds two characters into one and a split is the
    recoverable direction. Two records with DIFFERENT entity bindings never
    merge however exactly their names collide -- that pair staying two
    records is the point of the uid key.
    """
    presences = presences if isinstance(presences, dict) else {}
    for key in list(presences):
        if not isinstance(presences[key], dict):
            presences[key] = {}
    entity_names = _scene_entity_names_by_id(scene)

    # Legacy article/id-display fold, among name-keyed records only (these
    # keys ARE names; chat 80's "cfc004eb2c174286" tracked beside "Scranton
    # Reality Anchors" is the id-display case, chat 57's three Daleks the
    # article case).
    for key in list(presences):
        if is_presence_uid(key):
            continue
        canon = _canonical_presence_name(key, scene)
        if canon == key:
            continue
        other = presences.pop(key)
        if canon in presences:
            _merge_presence_record(presences[canon], other)
        else:
            presences[canon] = other

    # Re-key every legacy record onto its minted uid (the tiers above).
    for key in list(presences):
        record = presences[key]
        if is_presence_uid(key) and str(record.get("uid") or "") == key:
            continue
        record = presences.pop(key)
        name = presence_display_name(key, record) or str(key)
        if not str(record.get("entity_id") or "").strip():
            eid = (_entity_key_for_name(name, scene)
                   or _entity_uid_answering_to(name, entity_names))
            if eid:
                record["entity_id"] = eid
        seed = _charter_uid_seed(record)
        if seed is None and record.get("entity_id"):
            seed = "entity:%s" % record["entity_id"]
        if seed is None:
            seed = "legacy:%s" % name
        new_key = _mint_presence_uid(seed)
        record["uid"] = new_key
        record.setdefault("name", name)
        if new_key in presences:
            # Id agreement: two legacy spellings proved the same binding
            # (e.g. a bare positions key and the display name of one body).
            _merge_presence_record(presences[new_key], record)
        else:
            presences[new_key] = record

    # Bind: an unbound record whose name the scene answers UNAMBIGUOUSLY
    # (exactly one body with that identity -- the crowd guard) is stamped
    # with that body's id. The binding is what survives a rename.
    for key, record in presences.items():
        if record.get("entity_id"):
            continue
        eid = _entity_uid_answering_to(
            presence_display_name(key, record), entity_names)
        if eid:
            record["entity_id"] = eid

    # Entity fold: records sharing an entity_id merge unconditionally,
    # because an id denotes exactly one body. The earliest record keeps the
    # key (its uid is what anything holding a reference knows); the body's
    # CURRENT display name wins the `name` attribute, so a record bound
    # while the body was still "the guard" follows it to "Mara" -- history,
    # sketch, blurb and promotion progress intact, former spellings in
    # `aka`. A placeholder the validator derived from the key, or an
    # id-shaped string, is not adopted as a name: a rename is a fact about
    # the fiction, not about the serializer.
    by_entity = {}
    for key, record in presences.items():
        if record.get("entity_id"):
            by_entity.setdefault(str(record["entity_id"]), []).append(key)
    for eid, keys in by_entity.items():
        keys.sort(key=lambda k: (presences[k].get("first_turn", 0), k))
        target = presences[keys[0]]
        for other_key in keys[1:]:
            _merge_presence_record(target, presences.pop(other_key))
        live_name = str(entity_names.get(eid) or "").strip()
        current = str(target.get("name") or "").strip()
        if live_name and live_name != current:
            from llm.schemas import is_derived_entity_name
            if not is_derived_entity_name(eid, live_name):
                if current and current not in target.setdefault("aka", []):
                    target["aka"].append(current)
                target["name"] = live_name
        if target.get("aka"):
            target["aka"] = [a for a in target["aka"]
                             if a != str(target.get("name") or "")]
            if not target["aka"]:
                del target["aka"]

    # Identity fold, for splits that predate the uid key: records answering
    # to one identity merge only when nothing proves them distinct -- no
    # crowd of such bodies in the scene, and no CONFLICTING entity bindings.
    by_identity = {}
    for key, record in presences.items():
        identity = _presence_identity(presence_display_name(key, record))
        if identity:
            by_identity.setdefault(identity, []).append(key)
    for identity, keys in by_identity.items():
        if len(keys) < 2:
            continue
        if _bodies_answering_to(identity, scene) > 1:
            continue         # genuinely a crowd; see _bodies_answering_to
        bindings = {str(presences[k].get("entity_id") or "")
                    for k in keys} - {""}
        if len(bindings) > 1:
            continue         # two proven bodies share the name; keep both
        keys.sort(key=lambda k: (presences[k].get("first_turn", 0), k))
        target = presences[keys[0]]
        for other_key in keys[1:]:
            _merge_presence_record(target, presences.pop(other_key))
    return presences


def with_charter_presences(cid, presences, scene=None, *, places=None,
                           names=None, frame_id=None, turn_idx=None):
    """Overlay derived Charter bodies onto a background-presence ledger.

    The caller gets a copy.  Merely noticing a Charter worker must not write
    a second identity store; ordinary presence tracking persists the record
    only after the person actually participates in a beat.
    """
    merged = copy.deepcopy(presences or {})
    try:
        from world.charter_runtime import background_presence_records
        derived = background_presence_records(
            cid, places=places, names=names, frame_id=frame_id)
    except Exception:
        return merged
    for name, record in derived.items():
        if turn_idx is not None:
            record = copy.deepcopy(record)
            record["first_turn"] = int(turn_idx)
            record["last_turn"] = int(turn_idx)
        refs = [r for r in (record.get("charter_refs") or [])
                if isinstance(r, dict)]
        key = None
        # The charter body key is permanent identity: a record already
        # carrying this ref is this person, whatever it is currently named.
        for existing_key, existing in merged.items():
            if isinstance(existing, dict) and any(
                    r in (existing.get("charter_refs") or []) for r in refs):
                key = existing_key
                break
        if key is None:
            key, _rec, status = _presence_lookup(merged, name, scene)
            if status == "ambiguous":
                continue    # two tracked records answer; refuse to guess
        if key is None:
            seed = _charter_uid_seed(record) or ("legacy:%s" % name)
            fresh = copy.deepcopy(record)
            key = _mint_presence_uid(seed)
            fresh["uid"] = key
            fresh.setdefault("name", str(name))
            merged[key] = fresh
        else:
            _merge_presence_record(merged[key], record)
            # A spelling that differs only by case is the same name, and
            # the charter's is the healed one (`charter_identity.
            # display_name`): a ledger written before a lower-case mash
            # was repaired keeps presenting it otherwise.
            stored = str(merged[key].get("name") or "")
            if stored != str(name) and stored.casefold() == str(name).casefold():
                merged[key]["name"] = str(name)
    return merged


def emerge_from_charter_crowd(cid, scene, charter_key, place, *, who="",
                              present=(), frame_id=None, turn_idx=None):
    """One body steps out of a derived charter crowd: its presence record
    becomes durable. Returns ``(display_name, reason)``.

    DESIGN_BACKGROUND_PRESENTATION §B3: mechanically, emergence IS the
    existing overlay -- `with_charter_presences` resolves the picked body
    into the presence ledger identity-carefully, and the derived crowd
    excludes it from membership on the next read because the presence record
    is the record. No ``emerged`` list is stored, and the crowd's band does
    not move (a band is coarse precisely so nothing does arithmetic on it).

    Charter never stopped simulating this body, so nothing else changes: the
    same person, with the same ties, marks and diary, is simply presented
    individually from here -- and IS there next visit, which is the point
    (the §3a "an emergence may not be re-met" rule is superseded for
    charter-backed crowds; see DESIGN_CROWDS.md's amendment).
    """
    from world.charter_runtime import charter_emergence_pick

    display, reason = charter_emergence_pick(
        cid, charter_key, place, who=who, present=present, frame_id=frame_id,
        turn_idx=turn_idx)
    if not display:
        return "", reason
    presences = wget(cid, "background_presences", {}) or {}
    merged = with_charter_presences(
        cid, presences, scene, names=[display], frame_id=frame_id,
        turn_idx=turn_idx)
    if merged == presences:
        return "", ("no presence record could be derived for %r" % display)
    wset(cid, "background_presences", merged)
    return display, ""


def absorb_into_charter_crowd(cid, who, *, spoken=(), frame_id=None):
    """A charter body loses its individual presentation, and NOTHING else.
    Returns ``(handled, reason)``; ``(False, "")`` means "not a charter
    person -- not this seam's op".

    There is no state transition here to get wrong, because the body never
    had a separate simulation to lose: Charter simulates every unbound body
    every window whether or not anyone is looking (§1.99d's whole argument).
    Crowd membership is a lens, so absorption is only the presence record --
    the one thing that presented the body individually -- being removed.

    The one-way rule survives with its original test: "does anything durable
    now name them". A record carrying dialogue, addressed or mention turns
    is a record the story still points at (a line spoken, an address aimed,
    a transcript that referred to them), and deleting it would delete a
    person; the refusal is the same shape as `crowds.absorb`'s. Only a
    record whose turn lists are all empty -- a pure emergence overlay nobody
    engaged -- may go back to ground.
    """
    from world.charter_runtime import _body_refs, registry_for

    name = " ".join(str(who or "").split())
    if not name:
        return False, ""
    registry = registry_for(cid, frame_id)
    refs = [{"charter": ck, "body": bk}
            for ck, bk in _body_refs(registry, name=name)]
    if not refs:
        return False, ""
    if name.casefold() in {str(n or "").casefold() for n in (spoken or ())}:
        return True, ("%s has spoken; the story has a record of them and "
                      "they cannot go back into the crowd" % name)
    presences = wget(cid, "background_presences", {}) or {}
    keys = [key for key, rec in presences.items()
            if isinstance(rec, dict)
            and any(r in (rec.get("charter_refs") or []) for r in refs)]
    if not keys:
        # Never individually presented: the overlay record was simply never
        # persisted, which is what absorption of a never-engaged body IS.
        return True, ""
    for key in keys:
        rec = presences[key]
        if any(rec.get(field) for field in
               ("dialogue_turns", "addressed_turns", "mention_turns")):
            return True, ("%s has a durable record and cannot be deleted "
                          "back into the mass" % name)
    for key in keys:
        presences.pop(key, None)
    wset(cid, "background_presences", presences)
    return True, ""


def overt_declaration(ctx):
    """The player's declared beat with concealed content removed, as
    ``(elements, raw_text)``.

    ONE answer to "what of this declaration may a bystander be told about, or
    be judged against", read by both halves of the background stage: the
    payload builder in `agents/background.py`, which gates these elements
    further by the channel that reaches each presence, and
    `pick_background_reactors` below, which decides who gets a beat at all.

    The two halves used to disagree. The payload was fixed to strip concealed
    elements and the private thought; the gate went on reading `ctx.input`
    whole, which is the raw text the player typed, whispers included. A
    declaration that named a presence WHILE concealing therefore still made
    that presence qualify as addressed, get picked, and react to words nobody
    delivered -- the exact failure `_filtered_player_declaration`'s own
    docstring records as fixed, still live one module over because the gate is
    a different function in a different package. Having one function say what
    is overt is the only arrangement in which they cannot drift apart again.

    An unstructured declaration cannot be filtered element by element, so a
    private thought (the one signal available that something was withheld)
    withholds the whole of it.
    """
    interp = ctx.get("director_interpret") or {}
    seq = [e for e in (interp.get("sequence") or []) if isinstance(e, dict)]
    if seq:
        return [e for e in seq if e.get("visibility") != "concealed"], ""
    if interp.get("private_thought"):
        return [], ""
    return [], str(ctx.get("input") or "")


def overt_declaration_text(ctx):
    """`overt_declaration` flattened for deterministic name matching. Engine
    side only -- it carries an act's raw `attempt`, which is the actor's
    purpose and is never delivered to anyone."""
    elements, raw = overt_declaration(ctx)
    parts = [raw]
    for element in elements:
        if element.get("type") == "speech":
            parts.append(str(element.get("text") or ""))
        elif element.get("type") == "communication":
            parts.append(str(element.get("content") or ""))
        else:
            parts.append(str(element.get("observable")
                             or element.get("attempt") or ""))
    return " ".join(p for p in parts if p).strip()


def _background_name_mentioned(name, text, shared=()):
    """resolved_event prose almost never repeats someone's full tracked
    name after their first introduction -- "Crusher" carries a scene once
    "Dr. Crusher" has been established -- so a plain substring check
    against the full name would undercount real mentions. Fall back to
    any significant word of the name (title words and short filler
    stripped) appearing at a word boundary.

    `shared` is the set of words this name holds IN COMMON with other
    tracked names (`_shared_name_words`): a word every holder of a post
    carries is the post's name, not anyone's, and a full-name match is the
    only way such a word reaches this person."""
    text_cf = text.casefold()
    name_cf = name.casefold()
    if re.search(rf"\b{re.escape(name_cf)}\b", text_cf):
        return True
    words = [w.strip(".,;:").casefold() for w in name.split()]
    significant = [
        w for w in words
        if w and w not in _BACKGROUND_NAME_TITLE_WORDS and len(w) >= 3
        and w not in shared
    ]
    return any(
        re.search(rf"\b{re.escape(w)}\b", text_cf) for w in significant
    )


def _shared_name_words(names):
    """The significant words two or more distinct tracked names share.

    A WORD SHARED BY EVERY HOLDER OF A POST IS THE POST'S NAME. Three reeves
    are "Reeve <given> <family>" and the loose matcher read the word
    "reeve" in the player's declaration as a mention of each: measured on
    Harrowmere, every reeve accrued an `addressed_turns` entry on eight
    beats the player spoke to one of them, and on turn 33 "ask Nookfeller"
    qualified the other reeve beside him, with the pick then decided by a
    string sort. The engine cannot list the world's titles (the corpus
    already holds reeve, trader, clerk, innkeeper, and every story adds
    one), but it can see which words its own tracked names have in common,
    and that set is exactly the title vocabulary of THIS story. A word
    unique to one name -- "nookfeller" -- still reaches its owner alone.
    """
    seen = {}
    for name in names or ():
        key = str(name or "").strip().casefold()
        if not key:
            continue
        words = {w.strip(".,;:").casefold() for w in key.split()}
        for word in words:
            if word and word not in _BACKGROUND_NAME_TITLE_WORDS \
                    and len(word) >= 3:
                seen.setdefault(word, set()).add(key)
    return {word for word, owners in seen.items() if len(owners) > 1}


def _background_name_named_exactly(name, text):
    """The full tracked name at a word boundary -- the PRECISE grade of an
    address, as opposed to `_background_name_mentioned`'s significant-word
    fallback. The two grades exist because the fallback is deliberately
    fuzzy ("Crusher" carries a scene once "Dr. Crusher" is established), and
    fuzzy must never FORCE: measured on the Part C bench, six tracked
    "Regular N" records against the input "Regular 2, what do I owe you?"
    all matched on the shared word "regular", and an addressee guarantee
    keyed to that match widened one address into six voice calls."""
    return bool(re.search(rf"\b{re.escape(str(name).casefold())}\b",
                          str(text).casefold()))


def _character_address_of(dr_output, presence_name, roster, scene=None,
                          station_room=None):
    """Return the last hearable dialogue_log entry in which a roster speaker
    (a registered character or the player) aimed a line at this background
    presence, or None -- so a character speaking directly TO an extra can
    trigger that extra's reaction, which resolved_event-prose salience alone
    misses (a character's line rarely names its target in the prose).

    Fail-closed on concealment (metadata that rides every entry -- denying on
    it leaks nothing): a line marked visibility=concealed, or concealed FROM
    this presence, never triggers -- the same rule perception.py applies to
    the hear-level backstop. Audibility is enforced only when provable: with a
    known station_room and a resolvable speaker room, the line must be fully
    hearable (a fragment cannot be coherently replied to). When room data is
    absent (best-effort, unlike the always-present concealment flags) the
    address is allowed through on the same co-presence assumption
    background_react already makes about resolved_event -- the check
    self-tightens as sketch coverage grows.
    """
    found = None
    for d in (dr_output.get("dialogue_log") or []):
        speaker = str(d.get("speaker") or "").strip()
        if not speaker or speaker.casefold() not in roster:
            continue
        target = str(d.get("intended_target") or "").strip()
        # PRECISE match: `intended_target` is a structured field naming ONE
        # addressee, not prose. The significant-word fallback here read
        # "Trader Tate" as an address of every one of a market's 44
        # "Trader *" bodies through the shared cohort word (chat 95 turn
        # 3043: one sleeve-grab became a 44-strong forced chorus). The
        # conceal_from check below deliberately KEEPS the loose matcher --
        # concealment fails closed, and wide denial leaks nothing.
        if not target or not _presence_addressed_match(presence_name, target):
            continue
        if str(d.get("visibility") or "").casefold() == "concealed":
            continue
        if any(_background_name_mentioned(presence_name, str(c))
               for c in (d.get("conceal_from") or [])):
            continue
        if station_room and scene:
            sp_room = _room_of(scene, speaker)
            if sp_room:
                rel = spatial_rel(scene, sp_room, station_room)
                if hear_level(rel, d.get("volume") or "normal") != "full":
                    continue
        found = d  # last hearable address wins
    return found


def authored_mind_rooms(scene, roster):
    """Where the authored minds are standing, for the channel test below.

    MEMBERSHIP against the roster, never an enumeration of it: the scene's
    own `positions` is the source, so a registered mind who is not in the
    scene contributes nothing and an entity that is not a mind is skipped.
    """
    rooms = set()
    for who, where in ((scene or {}).get("positions") or {}).items():
        if str(who or "").casefold() in roster and str(where or ""):
            rooms.add(str(where))
    return rooms


def demand_reaches(scene, here, authored_rooms, *, aimed=False):
    """Is there a CHANNEL between where this presence stands and where an
    authored mind stands?

    A DEBT DOES NOT CROSS A DOORWAY. `aimed` says whether somebody turned
    toward the other THIS beat or last window -- the player's words naming
    this person, exactly or by a word of their name, or this body's own act
    toward an authored mind (§C1.3, which is the body aiming). An aimed
    demand travels on the hearing channel below -- calling "Clerk?" to
    someone in the next room is ordinary (chat 72's night clerk, one open
    doorway from the bell), and the channel test is deliberately not a
    radius. A reply OWED from an earlier beat is not aimed by anyone now:
    the player asked, walked away, and the debt discharges where they meet
    again, not through the open door the hearing channel grades as full
    hearing at any distance (`hear_level`: barrier open_door, volume normal
    -> full -- the right answer for whether a line can be made out, the
    wrong one for whether anyone is still waiting on it). Measured,
    Harrowmere turn 16: the miller, owed a reply from the mill, answered a
    player who was by then knocking on a door in another lane.

    The word-of-a-name case has a rule of its own, in `pick_voice_demand`:
    a name that merely occurs in a line aimed at somebody ELSE is a subject,
    and once the beat has a precise addressee it is not voiced at all
    (Harrowmere turn 2: the trader was asked, and two reeves in the hall
    next door answered on the word "reeve").

    Co-presence is not a TRIGGER -- §C2 settled that, and it stays settled.
    It is a FILTER. A demand from an authored mind reaches a person through
    a channel or it does not reach them, and what a slot buys is a line
    spoken INTO THIS BEAT: if no authored mind is there to receive it, the
    call is spent on an exchange that cannot happen. The triggers that fail
    this way are the CARRIED ones -- an owed reply and an act from a
    previous beat are debts, and a debt was discharging from anywhere in the
    world.

    The bar is the one this module already applies twice to the same
    question (`_character_address_of`, and the player-precise reply debt in
    `track_background_presences`): the words must arrive in FULL, because a
    fragment cannot be coherently replied to. Either direction counts -- the
    demand travelling to them and their answer travelling back are one
    channel seen from two ends, and `hear_level` is deliberately asymmetric
    about containment, so requiring both would silence a body speaking out
    of the thing it is inside.

    Fail-open for an UNPLACED presence, and only that one. `here` empty --
    a presence the scene stands nowhere -- returns True, so a body with no
    position is never silenced by a check about position, and the guard
    self-tightens as coverage grows.

    A room the scene does not contain is a DIFFERENT case and fails CLOSED:
    `spatial_rel` reads an unknown room id as separated, `hear_level` grades
    that `none`, and the presence is filtered. That is the right direction --
    a channel the scene cannot demonstrate is not a channel -- but it is the
    opposite of what this paragraph said until 2026-08-29, and two authority
    documents repeated the claim. Measured: `demand_reaches` with a room
    name absent from the scene returns False; with `here=""` it returns True.

    Measured, chat 98 turn 36 (2026-08-25): a body whose place was the
    engineering deck held the only selection slot on 17 of 40 turns -- 14 of
    them consecutive, including beats where the player was two decks away
    addressing five other presences standing at her own table. It qualified
    on `acting` every time, and every one of the 32 voice calls spent on it
    returned nothing, correctly, because it could not hear her. Across the
    whole run, every pick that ever produced a line was in the player's own
    room.
    """
    if not here or not authored_rooms:
        return True
    if not aimed:
        return str(here) in {str(r) for r in authored_rooms if r}
    for room in authored_rooms:
        if not room:
            continue
        if hear_level(spatial_rel(scene, room, here), "normal") == "full":
            return True
        if hear_level(spatial_rel(scene, here, room), "normal") == "full":
            return True
    return False


def _valid_pending_reply(record, turn_idx):
    """The presence's owed reply if it has not yet expired, else None."""
    pr = record.get("pending_reply")
    if not isinstance(pr, dict):
        return None
    if turn_idx > (pr.get("expires_turn") if pr.get("expires_turn") is not None else -1):
        return None
    return pr


def _background_fired_reactions(br):
    """Normalize a background_react result into a list of fired reaction dicts
    ({name, dialogue_log_entry, action}) -- tolerating both the ensemble
    (`reactions` list) shape and the legacy single-entry shape."""
    if not isinstance(br, dict):
        return []
    reactions = br.get("reactions")
    if reactions:
        return [r for r in reactions
                if isinstance(r, dict) and r.get("dialogue_log_entry")]
    if br.get("fired") and br.get("dialogue_log_entry"):
        return [{"name": br.get("name"),
                 "dialogue_log_entry": br["dialogue_log_entry"],
                 "action": br.get("action", "")}]
    return []


# Entity kinds that are clearly NOT agents. Everything else with a name is
# treated as a potential background presence (see track_background_presences).
# Deny-list rather than allow-list because the model's `kind` string is
# freeform: a novel agent kind (monster, creature, robot, drone, spirit, ...)
# must not fall through, whereas a mistracked object is harmless -- it never
# qualifies to react. Ambiguous kinds ("machine", "device") are deliberately
# NOT listed, so a sentient robot tagged that way is still tracked.
#
# schemas._ANIMATE_ENTITY_KINDS asks a neighbouring question -- must this thing
# occupy a room -- and deliberately answers it with an ALLOW-list instead. The
# asymmetry is the point: over-including here costs a tracked object that never
# reacts, over-including there aborts an opening.
_INERT_ENTITY_KINDS = frozenset({
    "object", "item", "fixture", "furniture", "furnishing", "appliance",
    "vehicle", "structure", "building", "terrain", "feature", "landmark",
    "door", "gate", "barrier", "wall", "container", "tool", "weapon",
    "armor", "clothing", "prop", "scenery", "decoration", "plant", "tree",
    "food", "drink", "substance", "material", "resource", "location",
    "room", "area", "zone", "region", "sign", "document", "book", "note",
    "panel", "console", "terminal", "screen", "light", "effect", "hazard",
    "trap", "corpse", "remains",
})


def _is_inert_presence_candidate(scene, eid, ent) -> bool:
    """Is this a thing, rather than somebody who could speak?

    Three tests, because no one of them holds alone.

    The deny-list above is matched against a FREEFORM model string, and the
    model does not write category words -- it writes compound nouns. Measured
    across chats 74-76, the four objects tracked as presences were tagged
    `device`, `key card`, `currency pouch` and `object`; only the last was on
    any list. Nor can the list simply be extended to cover them, because its
    two most useful generic words ("machine", "device") are left off ON PURPOSE
    so a sentient robot tagged that way stays trackable. A word list cannot
    separate a sonic screwdriver from a drone.

    `portable` can, because it is structural rather than lexical: it means an
    actor may pick this up and carry it. Across 65 scenes on disk it marks 174
    entities and only two of them are people.

    But it cannot stand alone, because THIS ENGINE LETS PEOPLE BE POCKETED, in
    two different ways that fail differently:

    - A shrunken character is portable and is the resized one, so she carries a
      `scales` entry -- and `_is_body_entity` reads `scales`. Live in chat 41.
    - A baseline character pocketed by a GIANT is portable and is NOT the
      resized one, so there is no `scales` entry to find. She is caught only by
      the other half of that predicate, `attire`, which holds only while she is
      dressed. Measured, `_is_body_entity` scores 23 of 88 animate entities as
      things -- `night clerk` among them -- so it is far too porous to gate on
      by itself.

    Hence the third term: an explicitly animate `kind` is never inert, using
    the allow-list schemas already maintains for a neighbouring question. It is
    conservative by construction, which is what makes it safe to trust here.

    Residual, stated rather than papered over: a carried, undressed,
    baseline-sized body whose kind is not on the animate list still reads as a
    thing. It costs nothing observable -- a presence that SPEAKS is harvested
    from `dialogue_log` above without ever reaching this gate, so the only
    figure lost is one that is silent, unregistered and never acted.
    """
    if not isinstance(ent, dict):
        return False
    kind = str(ent.get("kind") or "").strip().casefold()
    if kind in _INERT_ENTITY_KINDS:
        return True
    if not ent.get("portable"):
        return False
    from llm.schemas import _ANIMATE_ENTITY_KINDS
    return (kind not in _ANIMATE_ENTITY_KINDS
            and not _is_body_entity(scene, eid, ent))


def prepare_background_claims(ctx):
    """Embeddings for the canon rows a ratified background claim will become.

    A ratified claim now lands in `lore_entries`, and embedding a lore entry is
    a provider round-trip. It is decided here, before the outer transaction, on
    exactly the inputs `settle_claims` will re-decide on inside it. Best-effort:
    a failure costs the entries their prepared vector, never the turn.
    """
    res = ctx.director_resolve or ctx.director_establish or {}
    sd = res.get("state_diff") or {}
    try:
        from world.background_claims import prepare_canon

        return {"canon_embeddings": prepare_canon(
            ctx.chat.id, ctx.turn.idx,
            (ctx.get("background_react") or {}).get("claims"),
            str(res.get("resolved_event") or ""),
            ratified_refs=(sd.get("ratified_claims") or []),
            contradicted_refs=(sd.get("contradicted_claims") or []),
        )}
    except Exception as exc:
        ctx.add_warning(f"background-claim canon preparation failed: {exc}")
        return {"canon_embeddings": {}}


def _mint_missing_presence_names(cid, presences, scene, reserved=()):
    """Give every tracked PERSON the story keeps but has not named one
    permanent name from the story's own naming law (`story/naming.py`).

    THE MINT IS A WRITE, NOT A RENDERING: the name is minted here, in the
    one writer that persists the ledger, stored on the record, and read
    thereafter by every payload that speaks it. Nothing re-mints while
    ``record["name"]`` holds a real name, and the candidate is deterministic
    in (chat, presence uid), so a rolled-back commit replayed lands the same
    name for the same person. A REPLACEMENT is therefore not a rename: a new
    body resolves to a new record (new uid), draws a new name, and the old
    record keeps its own -- which is the continuity a prompt-level "please
    reuse the name" cannot guarantee (measured precedent for the class this
    forbids: chat 10 held `station engineer` and `station_engineer` as two
    records for one person, a role re-acquiring an identity every time the
    engine reached for the field).

    Scope is exactly `presence_is_unnamed` -- no name at all, or an
    id-shaped string standing where a name should (chat 67 tracked three raw
    hex ids as "names") -- gated on the speech verdict's "person" bar: a
    name is a person's to carry, and a device or an undecided presence stays
    unnamed until the story (or `blurb_mint`'s frozen `nature`) settles what
    it is. A presence the story named by ROLE ("the barkeep") keeps that
    name: renaming it would be the engine reaching for the field again,
    the exact act permanence forbids.

    A story with no naming law mints nothing -- no default table exists
    anywhere in the generator -- and the unnamed presence stays listed,
    tracked and awaiting a name (docs/UNBUILT.md 1.18 keeps the residuals).
    """
    unnamed = [
        key for key, record in (presences or {}).items()
        if isinstance(record, dict)
        and presence_is_unnamed(key, record)
        and _presence_speech_verdict(
            scene, presence_display_name(key, record), record) == "person"
    ]
    if not unnamed:
        return {}
    from story.naming import (
        minted_presence_name, story_identity_reservation, story_naming_lanes)

    lanes, _source = story_naming_lanes(cid)
    if not lanes:
        return {}
    # The no-fly list, in two halves. `used` is every spelling already in
    # play that this ledger knows about -- the caller's roster and each
    # tracked presence's own spellings. `reservation` is who is REGISTERED,
    # read by `story_identity_reservation` from the same two wells
    # `_refuse_name_collision` trusts (`characters.name` and the persona) and
    # by the same function the Charter body mint reads, so the two minting
    # paths ask one question. It is the stronger half: under a law that
    # addresses people by one element ("{rank} {family}"), a name nobody has
    # written out yet still arrives as a registered mind's address. Two
    # people may share a name in the fiction; the GENERATOR never introduces
    # that collision itself.
    used = {str(n or "").strip().casefold() for n in reserved}
    for key, record in presences.items():
        for n in _presence_names(key, record if isinstance(record, dict)
                                 else None):
            used.add(str(n).casefold())
    used.discard("")
    reservation = story_identity_reservation(cid, lanes, extra=reserved)
    minted = {}
    for key in sorted(unnamed):
        record = presences[key]
        name = minted_presence_name(cid, key, used, lanes=lanes,
                                    reservation=reservation)
        if not name:
            continue
        former = presence_display_name(key, record)
        if former and former.casefold() != name.casefold():
            # An id-shaped string was never a name, but a debt or a prose
            # tail may still reference it; keeping it in `aka` keeps every
            # pre-mint spelling resolving through presence_record_for.
            aka = record.setdefault("aka", [])
            if former not in aka:
                aka.append(former)
        record["name"] = name
        used.add(name.casefold())
        minted[key] = name
    return minted


def track_background_presences(ctx, nonce, *, prepared=None):
    """Deterministic, LLM-free tracking of named entities the director
    keeps writing into resolved_event/dialogue_log who are NOT a
    registered cast member, a persona, or an extra player -- e.g. a
    ship's doctor the director has kept consistently present and active
    across many turns despite her having no character sheet, no
    character_step call, and no memory. This never invents a candidate
    from free prose (no NER over resolved_event) -- only from the same
    structured fields commit already trusts: dialogue_log speakers,
    state_diff.entities with any non-inert kind (see _INERT_ENTITY_KINDS --
    agents named by the model, whatever kind string it used), director_establish's
    top-level entities on the opening turn, and the deterministic
    background_react backstop's own authored line. Once a name is a
    tracked candidate, later resolved_event mentions of that exact name
    are counted (case-insensitive substring) so passing-mention
    frequency can also cross the promotion threshold, without ever
    discovering a new name that way. For structured person/npc defs it
    also harvests a small `sketch` ({role_hint, station_room}) from the
    director's own description/position -- self-knowledge the background
    reactor can be voiced with, never perceived-world state. Purely
    additive bookkeeping for the UI to surface promotion suggestions
    from -- writes nothing into `characters` or `chat_chars` itself.
    """
    chat = ctx.chat
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    is_opening = not ctx.director_resolve  # res fell back to director_establish
    turn_idx = ctx.turn.idx

    roster = {n.casefold() for n in _registered_name_roster(chat, ctx.cast)}
    roster |= {(e.get("name") or "").casefold() for e in (ctx.extra_players or [])}

    candidates = set()
    dialogue_speakers = set()  # names that spoke a dialogue_log line this beat
    sketches = {}              # name -> {role_hint, station_room} from structured defs
    candidate_ids = {}         # name -> {entity ids the beat proved for it}:
                               # the durable key the harvests used to resolve
                               # into names and throw away
    renders = []               # [{charter, body, render}] for bound mints

    # Scene entities are keyed by an opaque id ("char_guard_alpha") but carry
    # a human display name ("Security Guard Alpha"). The director normally
    # voices a background entity by its display name, but sometimes slips and
    # writes the raw entity id into dialogue_log.speaker. Tracked verbatim,
    # that id becomes a SECOND, duplicate presence alongside the real one --
    # fragmenting the figure's dialogue/mention history and, worse, orphaning
    # its owed-reply debt onto the ghost id (observed live: a guard challenges
    # the player under its id, then never gets to answer, because the debt is
    # keyed to the id while the reactor gate ranks the display name). Fold an
    # id-shaped speaker back to its display name before it is ever tracked.
    _scene_now = wget(cid, "scene", {}) or {}
    entity_id_to_name = {
        eid: str((edef or {}).get("name") or "").strip()
        for eid, edef in (_scene_now.get("entities") or {}).items()
        if isinstance(edef, dict) and str((edef or {}).get("name") or "").strip()
    }
    # An entity MINTED THIS BEAT is not in the stored scene yet (the merge
    # commits later in this same turn), so fold its id from the beat's own
    # entity defs too -- otherwise a positions key naming a just-minted body
    # escapes the fold on exactly its first appearance, which is when the
    # duplicate is created. Chat 80 turn 0: the establish placed every body
    # by entity id, and each id became a second presence beside the
    # display-name record harvested from the same entity defs.
    _beat_entity_maps = [((res.get("state_diff") or {}).get("entities") or {})]
    if is_opening:
        _beat_entity_maps.append(res.get("entities") or {})
    for _ents in _beat_entity_maps:
        for _eid, _edef in _ents.items():
            if isinstance(_edef, dict):
                _nm = str(_edef.get("name") or "").strip()
                if _nm:
                    entity_id_to_name.setdefault(str(_eid), _nm)
    # A bodiless voice (ship AI, station PA) is voiced by the Director and has
    # no room. Tracking one as a background presence pinned it to whatever room
    # it was positioned in and made it a promotion candidate -- observed live
    # with the Enterprise computer sitting in Ten Forward.
    try:
        from story.scene import ubiquitous_speaker_names, is_ubiquitous_entity
        _ubiquitous = ubiquitous_speaker_names(_scene_now)
    except Exception:
        _ubiquitous, is_ubiquitous_entity = frozenset(), (lambda e: False)

    # Speakers whose line this beat AIMED at an authored mind -- the fact the
    # §C1.3 "acting" trigger needs next beat, written as `engaged_turns`
    # below. Recorded here because the target is on the entry and the entry
    # does not survive into the record: `dialogue_turns` proves a presence
    # spoke, to anyone, and cannot say the exchange had an authored mind in
    # it.
    engaged_speakers = set()

    def _aimed_at_authored(entry):
        target = str((entry or {}).get("intended_target") or "").strip()
        return bool(target) and name_in_roster(target, roster)

    for d in (res.get("dialogue_log") or []):
        raw_speaker = str(d.get("speaker") or "").strip()
        speaker = entity_id_to_name.get(raw_speaker, raw_speaker)
        if speaker.casefold() in _ubiquitous:
            continue
        if speaker and not name_in_roster(speaker, roster):
            candidates.add(speaker)
            dialogue_speakers.add(speaker.casefold())
            if _aimed_at_authored(d):
                engaged_speakers.add(speaker.casefold())
            if raw_speaker in entity_id_to_name:
                candidate_ids.setdefault(speaker, set()).add(raw_speaker)

    # Structured person/npc entity defs: state_diff.entities on a normal
    # turn, plus director_establish's TOP-LEVEL entities/positions on the
    # opening turn (DirectorEstablish carries them at top level, not inside
    # a state_diff -- so a location-implied presence established at idx 0
    # was previously never tracked until the director happened to restate
    # them). Same no-NER rule: only these already-trusted structured fields.
    diff = res.get("state_diff") or {}
    entity_sources = [((diff.get("entities") or {}), (diff.get("positions") or {}))]
    if is_opening:
        entity_sources.append(((res.get("entities") or {}), (res.get("positions") or {})))
    for entities, positions in entity_sources:
        for entity_id, entity_def in entities.items():
            if not isinstance(entity_def, dict):
                continue
            # Track any named entity that is not CLEARLY inert. `kind` is a
            # freeform model string with no controlled vocabulary, so an
            # allowlist ("person"/"npc") silently dropped every other agent
            # the model names -- player-declared guards (kind:"actor"),
            # monsters, creatures, robots, spirits, drones -- leaving them
            # captured in the scene but tracked by neither the cast nor the
            # background-presence system: declared, then inert. Enumerating
            # agent kinds is an unwinnable treadmill; instead exclude the
            # clearly non-agent kinds and default to inclusion.
            #
            # The trade that justified defaulting to inclusion -- "a rare
            # mistracked object never reacts anyway" -- was FALSE. The gate
            # lets a presence react once it is voiced, and this path can voice
            # one: chat 75 gave a shed utility sash three turns of dialogue as
            # a hotel housekeeper. So the exclusion has to actually work on a
            # freeform kind string, which is what _is_inert_presence_candidate
            # adds; the deny-list alone caught one of those four objects.
            kind = str(entity_def.get("kind") or "").strip().casefold()
            if not kind or _is_inert_presence_candidate(
                    _scene_now, entity_id, entity_def):
                continue
            name = str(entity_def.get("name") or "").strip()
            if not name or name_in_roster(name, roster):
                continue
            if is_ubiquitous_entity(entity_def) or name.casefold() in _ubiquitous:
                continue
            candidates.add(name)
            candidate_ids.setdefault(name, set()).add(str(entity_id))
            sk = sketches.setdefault(name, {})
            desc = str(entity_def.get("description") or "").strip()
            if desc:
                sk["role_hint"] = desc[:160]
            # A mint the Director's floor bound to a charter body carries
            # that body's permanent identity (`_bind_minted_entities_to_
            # present_figures`); the record keys on it from its first beat,
            # so the derived overlay and this ledger agree who this is.
            _cref = entity_def.get("charter_ref")
            if (isinstance(_cref, dict) and _cref.get("charter")
                    and _cref.get("body")):
                sk["_charter_ref"] = {"charter": str(_cref["charter"]),
                                      "body": str(_cref["body"])}
                # The Director's render of the body it bound to: settled
                # onto that body's surface once, below, so the same
                # townsperson looks the same next visit.
                if desc:
                    sk["_render"] = desc
            # Positions are usually keyed by the entity ID, not the display
            # name this sketch is filed under. Looking up the name alone left
            # the station on the floor -- and the positions harvest below then
            # tracked the id as a SECOND presence just to hold it, which is
            # how chat 80's guards each split into a name-keyed record with a
            # role_hint and an id-keyed record with a station_room.
            room = positions.get(name) or positions.get(str(entity_id))
            if room:
                sk["station_room"] = str(room)

    # A BODY THE BEAT PLACED IN A ROOM, named nowhere else.
    #
    # Live, chat 72 turn 47. The player had been ringing a hotel bell for
    # four beats; the Director finally brought somebody, and he arrived in
    # `cast_changes` ("young man", arrived) and `positions` ("Sleepy Hotel
    # Clerk") and in nothing else. Neither is harvested above, so he became a
    # name in the position ledger with no presence record, no perception
    # object and no way to ever be picked to act. That story's tracked
    # presences afterwards held exactly one thing, and it was a screwdriver.
    #
    # `positions` obeys this function's own rule -- a structured field commit
    # already trusts, never NER over prose -- and is a stronger signal than
    # most, being the ledger the engine PLACES BODIES with. Anything placed
    # in a room is in the scene by construction.
    #
    # Keyed on the positions name rather than on `cast_changes.who`, because
    # `who` is a description the model wrote ("young man") while the
    # positions key is the identity every other system keys on. Turn 47
    # carried both for one figure; tracking the description too would mint a
    # second presence nothing could ever match to the first.
    _diff_positions = (diff.get("positions") or {})
    # KEYED BY BOTH ID AND DISPLAY NAME, because the caller below looks this up
    # with a `positions` key -- and `positions` is keyed by entity ID while an
    # entity def carries a separate human `name`. Keyed by name alone, the
    # lookup missed for every entity whose id is not byte-identical to its
    # name, which is nearly all of them: `utility_sash_with_pouches_hinami`
    # against "utility sash with pouches hinami" is underscores against spaces.
    # A miss returns None, None is not in _INERT_ENTITY_KINDS, and the guard
    # below defaults to inclusion -- so the inert-kind rule never fired on this
    # path at all.
    #
    # Live, chat 75 turns 57-60. Hinami took off a utility sash and set it on
    # the bed; the beat placed it in the room, this path admitted it as a
    # background presence, and the reactor gate then gave it a housekeeper
    # persona and three turns of dialogue -- "Everything good in here?" -- with
    # a `tell` of "tugs at the sash at her hip", the entity's own name folded
    # back into a mannerism. The player, believing a hotel employee had walked
    # in on her, asked the intruders to leave. Four of that story's six tracked
    # presences were inanimate: a sash, a key card, a leather pouch and a sonic
    # screwdriver.
    #
    # The comment above ("a mistracked object never reacts anyway") was the
    # load-bearing assumption, and it was false: the gate lets a presence react
    # once it is voiced, and a presence this path admits can be voiced.
    # Verdict, not kind: the test is no longer a single word lookup, so resolve
    # it once per entity here and index the ANSWER by both keys.
    _inert_by_key = {}
    for _eid, _edef in (list((diff.get("entities") or {}).items())
                        + list((_scene_now.get("entities") or {}).items())):
        if not isinstance(_edef, dict):
            continue
        _verdict = _is_inert_presence_candidate(_scene_now, _eid, _edef)
        for _key in (_eid, _edef.get("name")):
            _key = str(_key or "").strip().casefold()
            if _key:
                _inert_by_key.setdefault(_key, _verdict)
    for _placed in _diff_positions:
        # The same id-to-display-name fold the dialogue-speaker harvest has
        # always applied. `positions` legitimately keys bodies by entity id,
        # so tracking the key verbatim minted an id-keyed twin beside the
        # display-name presence -- chat 80 held six presences for three
        # things, and the twin "cfc004eb2c174286" accrued its own dialogue
        # history and blurb while "Scranton Reality Anchors" accrued the
        # mentions.
        _name = entity_id_to_name.get(str(_placed or "").strip(),
                                      str(_placed or "").strip())
        if not _name or name_in_roster(_name, roster):
            continue
        if _name.casefold() in _ubiquitous:
            continue
        # The same rule the entity harvest applies: exclude the clearly inert,
        # default to inclusion for everything else. A bare name with no entity
        # def at all stays agent-shaped by default -- there is nothing to judge
        # it on, and a name the beat PLACED IN A ROOM is in the scene by
        # construction (that is how the chat 72 night clerk was recovered).
        if _inert_by_key.get(_name.casefold()):
            continue
        candidates.add(_name)
        if str(_placed or "").strip() in entity_id_to_name:
            candidate_ids.setdefault(_name, set()).add(
                str(_placed or "").strip())
        sk = sketches.setdefault(_name, {})
        sk.setdefault("station_room", str(_diff_positions[_placed]))

    # The deterministic backstop (background_react) authored one or more lines
    # this beat for the gate-picked presence(s): persist each as a real
    # dialogue turn so the same figure accrues toward promotion and reads as
    # continuous, rather than being invisible to bookkeeping (it is otherwise
    # merged only for rendering, in agents/perception.py). Each speaker was
    # force-set to its gate-picked name in background_react.
    br = ctx.get("background_react") or {}
    for _r in _background_fired_reactions(br):
        br_raw = str((_r.get("dialogue_log_entry") or {}).get("speaker") or "").strip()
        br_name = entity_id_to_name.get(br_raw, br_raw)
        if br_name and not name_in_roster(br_name, roster):
            candidates.add(br_name)
            dialogue_speakers.add(br_name.casefold())
            if _aimed_at_authored(_r.get("dialogue_log_entry")):
                engaged_speakers.add(br_name.casefold())
            if br_raw in entity_id_to_name:
                candidate_ids.setdefault(br_name, set()).add(br_raw)

    live_scene = wget(cid, "scene", {}) or {}
    presences = _fold_duplicate_presences(
        wget(cid, "background_presences", {}), live_scene)
    # Who was already in the ledger before the overlay. A record that was
    # durable last beat stays durable.
    _before = set(presences)
    _selected_for_charter = {
        str(n).strip() for n in (br.get("selected") or ()) if str(n).strip()
    }
    presences = with_charter_presences(
        cid, presences, live_scene,
        names=(set(candidates) | _selected_for_charter),
        frame_id=ctx.turn.frame_id, turn_idx=turn_idx)
    touched = set()
    for name in sorted(candidates):
        # `A Dalek`, `Dalek` and `The Dalek` are one creature WHEN THE ROOM
        # HOLDS ONE DALEK -- the scene decides that, not the string. Resolve
        # to the record already tracked before creating anything, or the
        # ledger grows a fresh presence every time the prose changes its
        # determiner. A candidate the beat PROVED an entity id for resolves
        # by that binding -- which is what lets two bodies sharing a display
        # name stay two records instead of silently merging.
        keys = []
        for _eid in sorted(candidate_ids.get(name) or ()):
            keys.append(_resolve_or_mint_presence(
                name, presences, live_scene, entity_id=_eid))
        if not keys:
            key = _resolve_or_mint_presence(name, presences, live_scene)
            if key is None:
                # Two tracked records answer to this name and nothing this
                # beat tells them apart. Attributing to either hands one
                # person the other's history; minting a third invents a
                # stranger. Refuse to guess -- the conduct stays in the
                # objective record, unattributed.
                ctx.add_warning(
                    "Background presence %r not attributed: two tracked "
                    "presences answer to that name and nothing this beat "
                    "tells them apart." % name)
                continue
            keys.append(key)
        for key in keys:
            record = presences[key]
            record.setdefault("uid", key)
            record.setdefault("first_turn", turn_idx)
            record.setdefault("dialogue_turns", [])
            record.setdefault("mention_turns", [])
            record["last_turn"] = turn_idx
            # Bind the record to its scene body while the name still answers
            # unambiguously (entity_id_to_name already includes entities
            # minted this very beat). The binding is what survives a RENAME:
            # once the body is called something else, no string comparison
            # can connect the spellings, but the id still does.
            if not record.get("entity_id"):
                _eid = _entity_uid_answering_to(name, entity_id_to_name)
                if _eid:
                    record["entity_id"] = _eid
            if name.casefold() in dialogue_speakers:
                if turn_idx not in record["dialogue_turns"]:
                    record["dialogue_turns"].append(turn_idx)
            if name.casefold() in engaged_speakers:
                # The §C1.3 "acting" fact: this beat's line was aimed at an
                # authored mind, so next beat's demand gate re-offers this
                # presence without any tenure list -- the exchange itself is
                # what persists.
                _engaged = record.setdefault("engaged_turns", [])
                if turn_idx not in _engaged:
                    _engaged.append(turn_idx)
            sk = sketches.get(name)
            if sk:
                sk = dict(sk)
                _cref = sk.pop("_charter_ref", None)
                _render = sk.pop("_render", None)
                if _cref and _cref not in record.setdefault("charter_refs", []):
                    record["charter_refs"].append(dict(_cref))
                if _cref and _render:
                    renders.append({"charter": _cref["charter"],
                                    "body": _cref["body"],
                                    "render": _render})
                # Director restated this presence's own description/position
                # -> objective self-knowledge wins; overwrite the prior sketch.
                if sk:
                    record.setdefault("sketch", {}).update(sk)
            touched.add(key)

    # RENDER-ON-VIEW SETTLES. A mint the floor bound to a charter body is
    # the Director's high-fidelity render of that body; it lands on the
    # body's surface once (`charter_runtime.settle_rendered_surfaces`) and a
    # later render may add to it but never contradict a dealt axis -- the
    # refusal is a warning, and the entity keeps its description either way.
    if renders:
        try:
            from world.charter_runtime import settle_rendered_surfaces
            for rec in settle_rendered_surfaces(
                    cid, renders, frame_id=ctx.turn.frame_id):
                if rec.get("refused"):
                    ctx.add_warning(
                        "render of %s (%s) not settled: it contradicts the "
                        "body's dealt %s" % (rec["body"], rec["charter"],
                                             rec["refused"]))
        except Exception as exc:
            ctx.add_warning(f"rendered surface not settled: {exc}")

    # Scene-manager bookkeeping (docs/design/BACKGROUND_LIFE_DESIGN.md §3.8, §3.11).
    _persist_blurbs(br, presences)
    _append_manager_conduct(br, presences, turn_idx)

    charter_conduct = []
    for reaction in _background_fired_reactions_any(br):
        conduct = reaction.get("charter_act")
        if not isinstance(conduct, dict):
            continue
        reaction_name = str(reaction.get("name") or "").strip()
        _ckey, record = presence_record_for(
            presences, reaction_name, live_scene)
        record = record or {}
        if not record.get("charter_refs"):
            continue
        try:
            from world.charter_runtime import apply_presence_conduct
            result = apply_presence_conduct(
                cid, reaction_name, conduct, record=record,
                frame_id=ctx.turn.frame_id,
                allowed=reaction.get("charter_offers") or (),
                place=reaction.get("room") or "")
            if result:
                charter_conduct.append(result)
                if result.get("refused"):
                    ctx.add_warning(
                        "Charter refused %s's %s toward %s: %s" % (
                            reaction_name, conduct.get("act"),
                            conduct.get("other"), result["refused"]))
        except Exception as exc:
            ctx.add_warning(f"Charter conduct skipped for {reaction_name}: {exc}")

    # Lore a background presence asserted this beat enters as a CLAIM, never as
    # fact -- the Director ratifies it, contradicts it, or lets it expire
    # (background_claims.py). Same treatment the Player Authority Contract
    # already gives a player's claim about another character.
    from world.background_claims import record_claims, settle_claims
    _sd = res.get("state_diff") or {}
    record_claims(cid, turn_idx, (br or {}).get("claims"))
    # A ratification WRITES the claim into the chat's canon lorebook, so its
    # embedding is prepared outside this transaction (prepare_background_claims)
    # rather than paid for under the write lock.
    settle_claims(cid, turn_idx, str(res.get("resolved_event") or ""),
                  ratified_refs=(_sd.get("ratified_claims") or []),
                  contradicted_refs=(_sd.get("contradicted_claims") or []),
                  canon_embeddings=(prepared or {}).get("canon_embeddings"))

    resolved_event = str(res.get("resolved_event") or "")
    # The story's title vocabulary, derived from its own tracked names: a
    # word every holder of a post shares names the post, and a mention of
    # it is not a mention of each of them (`_shared_name_words`).
    shared_words = _shared_name_words(
        n for k, r in presences.items() for n in _presence_names(k, r))
    for key, record in presences.items():
        if key in touched:
            continue
        # Former spellings count too: after a rename the prose keeps saying
        # "the guard" for a while, and it still means her.
        if any(_background_name_mentioned(n, resolved_event,
                                          shared=shared_words)
               for n in _presence_names(key, record)):
            record["last_turn"] = turn_idx
            if turn_idx not in record.setdefault("mention_turns", []):
                record["mention_turns"].append(turn_idx)

    # Owed-reply bookkeeping: a registered character (or the player) addressed
    # this presence this beat and it has not ANSWERED -- persist a one-beat-
    # grace debt so they can answer next turn (the "if not during the turn,
    # next turn" case), swept when stale so a reply never surfaces turns
    # later.
    #
    # DISCHARGED ON FIRED CONDUCT, NOT ON SELECTION. Selection only proves
    # the gate spent a call, and the call can come back `reacts: false`:
    # measured, chat 95 turns 3031/3032/3041, the addressed cord-seller was
    # selected three times, shown `addressed_by: null` each time (the relay
    # defect fixed in agents/background._react_one), declined in 31 tokens
    # each time -- and selection-keyed discharge then erased the very debt
    # that would have re-asked him. A debt is paid by a line or a visible
    # act; a declined call leaves it standing until its own expiry.
    answered_names = {
        str(_r.get("name") or "").strip().casefold()
        for _r in _background_fired_reactions_any(
            ctx.get("background_react") or {})
        if str(_r.get("name") or "").strip()}
    # A chorused addressee's moment was answered TOGETHER (§C3): the crowd
    # entry names them so their reply debts discharge here exactly as a
    # fired presence's would -- they are deliberately NOT individual
    # reactions, because the chorus's whole point is that these bodies stay
    # ground.
    for _r in _background_fired_reactions_any(
            ctx.get("background_react") or {}):
        if _r.get("chorus"):
            answered_names |= {str(n).casefold()
                               for n in (_r.get("addressed") or [])}
    # DELIBERATE interaction, counted separately from everything else. The
    # other two counters record what a presence DID -- `dialogue_turns` that
    # they spoke (to anyone, including ambient chatter with the player nowhere
    # in it) and `mention_turns` that the narration named them. Neither says
    # the story turned toward this person on purpose, which is the only thing
    # that should ever earn a passer-by a character sheet.
    #
    # Three things count, all of them someone choosing this presence:
    # the director marking them as the player's addressee, the player naming
    # them in their own input, and a registered character aiming a line at
    # them. The signal for the first already existed and was used only as a
    # same-beat liveness bit; nothing accumulated it.
    _bindings = descriptor_bindings(ctx, res)
    addressed_refs = [_bindings.get(r, r)
                      for r in _addressed_ref_strings(ctx, res)]
    # A description address is a BINDING (descriptor_bindings): persist the
    # player's own phrase on the bound body, so the fact the bind minted
    # exists -- the next "the man with the braided cords" resolves by
    # retrieval instead of a second seeded pick over a cohort that may have
    # shifted underneath it.
    for _ref, _bound in _bindings.items():
        for _key, _record in presences.items():
            if presence_display_name(_key, _record) != _bound:
                continue
            _sk = _record.setdefault("sketch", {})
            _stored = _sk.setdefault("descriptors", [])
            _norm = _normalized_descriptor(_ref)
            if _norm and not any(_normalized_descriptor(s) == _norm
                                 for s in _stored):
                _stored.append(" ".join(str(_ref).split()))
            break
    # NOT `ctx.turn.player_input`, which is the raw text the player typed.
    # See `overt_declaration`: the pre-commit gate was routed through it and
    # this writer -- one function over, on the same beat, from the same
    # declaration -- was not. A concealed line naming a presence therefore
    # accrued them a DURABLE addressed debt for words nobody delivered, which
    # outlives the beat and is the counter that earns a passer-by a sheet.
    player_input = overt_declaration_text(ctx)
    sc = wget(cid, "scene", {}) or {}
    _p_name = _player_name_or_none(ctx)
    _p_room = str(room_of(sc, _p_name) or "") if _p_name else ""
    for key, record in presences.items():
        name = presence_display_name(key, record)
        if not name:
            continue
        addressed = any(
            _presence_in_addressed_refs(n, addressed_refs)
            or _background_name_mentioned(n, player_input,
                                          shared=shared_words)
            for n in _presence_names(key, record)
        )
        pr = record.get("pending_reply")
        if isinstance(pr, dict) and turn_idx > (pr.get("expires_turn")
                                                if pr.get("expires_turn") is not None else -1):
            record.pop("pending_reply", None)
        if name.casefold() in answered_names:
            record.pop("pending_reply", None)  # answered, by word or by act
        else:
            entry = _character_address_of(
                res, name, roster, sc, (record.get("sketch") or {}).get("station_room"))
            if entry:
                addressed = True
                record["pending_reply"] = {
                    "from": entry.get("speaker"), "quote": entry.get("exact_quote", ""),
                    "tone": entry.get("tone", ""), "turn": turn_idx,
                    "expires_turn": turn_idx + 2,
                }
            else:
                # The PLAYER's precise address (a flow ref -- description
                # bindings included -- or the exact tracked name in the overt
                # declaration) writes the same debt a character's aimed line
                # does. It could not before: the only writer above needs a
                # dialogue_log `intended_target`, which no prompt instructs
                # and which measured null on every one of 189 reads (chat 95
                # turn 3041), so a player address that went unanswered simply
                # evaporated. PRECISE only -- a loose significant-word
                # mention must not accrue a stranger a two-beat debt that
                # spends gate slots -- and only when the words reach them in
                # FULL, same audibility bar as _character_address_of.
                _player_precise = any(
                    _presence_in_addressed_refs(n, addressed_refs)
                    or _background_name_named_exactly(n, player_input)
                    for n in _presence_names(key, record))
                if _player_precise and player_input and _p_name:
                    _here = presence_room(sc, name, record)
                    _hearable = True
                    if _here and _p_room:
                        _hearable = hear_level(
                            spatial_rel(sc, _p_room, _here),
                            "normal") == "full"
                    if _hearable:
                        addressed = True
                        record["pending_reply"] = {
                            "from": _p_name, "quote": player_input,
                            "tone": "", "turn": turn_idx,
                            "expires_turn": turn_idx + 2,
                        }
        if addressed:
            turns = record.setdefault("addressed_turns", [])
            if turn_idx not in turns:
                turns.append(turn_idx)
                record["last_turn"] = turn_idx

    # A tracked person the story has not named draws one permanent name from
    # the story's own naming law -- written here, in the ledger's one writer,
    # so the mint survives the model's next paraphrase (J2a: the mint is a
    # write, not a rendering).
    named = _mint_missing_presence_names(cid, presences, live_scene,
                                         reserved=roster)

    # EVERY BACKGROUND PERSON IS A CHARTER BODY, from here on. Measured across
    # the corpus before this: 84 tracked presences with no charter body against
    # 14 with one, so 86% of the people a story populates itself with reached
    # none of the memory, familiarity, ties or history-reading volition built
    # for exactly them -- they were a name in a dict, keyed by DISPLAY NAME,
    # which two people in one story may share. A body gives them one identity
    # space, a past that accumulates, and the single promotion path every other
    # body already uses. Failure is not fatal: a story with no registry keeps
    # the ledger it had.
    try:
        from world.charter_runtime import ensure_ambient_bodies
        _wanted = []
        for key, record in presences.items():
            if record.get("charter_refs"):
                continue
            _name = presence_display_name(key, record)
            if not _name:
                continue
            # A BODY IS A PERSON. `_presence_speech_verdict` already answers
            # this for the adjacent question -- may this presence hold a
            # speaking turn -- and the answer is the same one: a ceiling-
            # mounted suppression fixture is not somebody who can stand a
            # watch, form an acquaintance or be promoted. Minting one a body
            # made an unpromotable device promotable, because a charter body
            # IS a person and nothing downstream asks twice.
            if _presence_speech_verdict(live_scene, _name, record) != "person":
                continue
            _wanted.append({
                "name": _name,
                "place": str(presence_room(live_scene, _name, record) or ""),
            })
        for _name, _ref in (ensure_ambient_bodies(
                cid, _wanted, frame_id=ctx.turn.frame_id) or {}).items():
            for key, record in presences.items():
                if presence_display_name(key, record) != _name:
                    continue
                refs = [r for r in (record.get("charter_refs") or [])
                        if isinstance(r, dict)]
                if _ref not in refs:
                    refs.append(_ref)
                record["charter_refs"] = refs
    except Exception as exc:  # a ledger without bodies is still a ledger
        ctx.add_warning(f"charter body mint skipped: {exc}")

    # THE OVERLAY IS AN APERTURE, NOT A LEDGER ENTRY. `with_charter_presences`
    # says so itself -- "merely noticing a Charter worker must not write a
    # second identity store; ordinary presence tracking persists the record
    # only after the person actually participates in a beat" -- and this, its
    # caller, persisted the merged copy wholesale. Harmless while a story had
    # fourteen charter bodies; measured on a generated market town of three
    # hundred it wrote 284 permanent records for people the story had never
    # used, every one of them re-derivable from the registry on demand.
    #
    # A record EARNS its place by participating: it spoke, it was addressed,
    # it was mentioned, it is owed a reply, or it was already in the ledger
    # before this beat. Everything else stays an aperture and is re-derived
    # next turn from the charter it came from.
    _earned = {}
    for key, record in presences.items():
        if not isinstance(record, dict):
            continue
        # Already durable, harvested from the Director's own structured
        # fields this beat (`touched`), or not charter-derived at all.
        if (key in _before or key in touched
                or not record.get("charter_refs")):
            _earned[key] = record
            continue
        if any(record.get(field) for field in
               ("dialogue_turns", "addressed_turns", "mention_turns",
                "pending_reply")):
            _earned[key] = record
    presences = _earned
    proposed = _propose_promotions(ctx, presences, sc)
    wset(cid, "background_presences", presences)
    return {"tracked": len(presences),
            "promotion_proposed": proposed,
            "named": named,
            "charter_conduct": charter_conduct}

BACKGROUND_RECENT_TAIL = 4


def commit_charter_observations(ctx, prepared_scene):
    """Persist this beat's observer-scoped player/major-character evidence,
    and let the bodies standing beside a figure see it.

    ``director_resolve.public_evidence`` has already been grounded against
    exact declarations/dialogue.  This commit domain does no interpretation;
    it only asks the Charter runtime which unpromoted bodies could see/hear
    each source and writes those bodies' private claims.

    ``prepared_scene`` is `prepare_scene_commit`'s envelope, whose ``scene``
    is the post-turn scene -- the same shape `commit_information_carriers`
    unwraps. THIS DOMAIN DID NOT UNWRAP IT. The envelope went to
    `room_of(scene, actor)` as if it were the scene, no actor ever had a
    room, and every body failed reception: measured on the Harrowmere
    playtest, ``acquired: 0`` on all forty turns against 109-345
    opportunities each, with the player speaking to the reeve in the
    reeve's own hall. A bare scene dict is still accepted for callers that
    hold one.
    """
    scene = prepared_scene if isinstance(prepared_scene, dict) else {}
    if isinstance(scene.get("scene"), dict) and "rooms" not in scene:
        scene = scene["scene"]
    from agents.common import scene_figures
    from world.charter_runtime import (ingest_public_evidence,
                                       sight_figures_in_scene)

    figures = scene_figures(ctx.chat, ctx.cast, scene)
    # Standing in the room is the channel a stranger is noticed by. Runs
    # whether or not the beat produced evidence: a player who walks in and
    # says nothing has still been seen.
    sighted = sight_figures_in_scene(
        ctx.chat.id, figures, frame_id=ctx.turn.frame_id)
    resolved = ctx.get("director_resolve") or {}
    evidence = resolved.get("public_evidence") or []
    # The beat's transfer ops ride along for the one figure act that is
    # not speech: a thing handed to a body. The actors are everyone the
    # story knows by name -- membership only, never iterated into a payload.
    inventory_ops = (resolved.get("state_diff") or {}).get("inventory_ops") \
        or []
    if not evidence and not inventory_ops:
        return {"sources": 0, "opportunities": 0, "acquired": 0,
                "sighted": int(sighted.get("sighted") or 0)}
    result = ingest_public_evidence(
        ctx.chat.id, evidence, scene or {}, turn_id=ctx.turn.id,
        frame_id=ctx.turn.frame_id,
        labels={f["key"]: f["label"] for f in figures},
        inventory_ops=inventory_ops,
        figures=list(_registered_name_roster(ctx.chat, ctx.cast)))
    for actor in result.get("unplaced") or ():
        ctx.add_warning(
            "charter observations: the scene places %r nowhere, so no body "
            "could receive what they said or did" % actor)
    for record in result.get("figure_acts") or ():
        if record.get("refused"):
            ctx.add_warning(
                "Charter refused %s's %s toward %s: %s%s" % (
                    record.get("actor"), record.get("act"),
                    record.get("other"), record["refused"],
                    (" (%s)" % record["reason"]) if record.get("reason")
                    else ""))
    result["sighted"] = int(sighted.get("sighted") or 0)
    return result

def _persist_blurbs(br, presences):
    """Write minted blurbs (§3.8). FROZEN: a blurb is written once and never
    rewritten -- immutability is the feature, and it is the anchor against the
    self-feeding drift §3.11 describes."""
    for name, blurb in ((br or {}).get("blurbs") or {}).items():
        _key, rec = presence_record_for(presences, name)
        if rec is None or rec.get("blurb") or not isinstance(blurb, dict):
            continue
        if any(str(v or "").strip() for v in blurb.values()):
            rec["blurb"] = blurb

def _append_manager_conduct(br, presences, turn_idx):
    """Route each attributed entry to its OWN presence's record (§3.11).

    This is a routing operation, not an authoring one: the model emitted
    structurally attributed entries and deterministic code files each under the
    name it carries, so no shared-context prose is ever written to storage and
    §3.2's write-unbatched rule holds.
    """
    for r in _background_fired_reactions_any(br):
        name = str(r.get("name") or "").strip()
        _key, rec = presence_record_for(presences, name)
        if rec is None:
            continue
        entry = r.get("dialogue_log_entry") or {}
        parts = []
        heard = r.get("heard_address") or {}
        if heard.get("exact_quote"):
            speaker = str(heard.get("speaker") or "someone").strip()
            parts.append('heard %s say "%s"' % (
                speaker, str(heard["exact_quote"]).strip()))
        if entry.get("exact_quote"):
            parts.append('said "%s"' % str(entry["exact_quote"]).strip())
        if r.get("action"):
            parts.append(str(r["action"]).strip())
        if not parts:
            continue
        tail = rec.setdefault("recent", [])
        tail.append({"turn": turn_idx, "text": "; ".join(parts)})
        del tail[:-BACKGROUND_RECENT_TAIL]

def _background_fired_reactions_any(br):
    """Like _background_fired_reactions but also yields action-only entries --
    the scene manager may have someone act without speaking, and that conduct
    still belongs in their profile."""
    if not isinstance(br, dict):
        return []
    reactions = br.get("reactions")
    if reactions:
        return [r for r in reactions if isinstance(r, dict)
                and (r.get("dialogue_log_entry") or r.get("action"))]
    return _background_fired_reactions(br)

def _raw_flow_addressed_refs(ctx):
    """Raw flow.addressed_to entries as the director emitted them, preserved
    as flow.addressed_to_refs in schemas.py before int coercion. The string
    entries are the only way the director can mark an UNREGISTERED background
    presence (which has no character id) as the player's addressee; int-like
    refs are registered-character ids and are ignored here (agents/loops.py
    resolves those against the cast)."""
    interp = ctx.get("director_interpret") or {}
    flow = interp.get("flow") if isinstance(interp, dict) else None
    if not isinstance(flow, dict):
        return []
    refs = []
    for ref in (flow.get("addressed_to_refs") or []):
        if isinstance(ref, str):
            text = ref.strip()
            if text and not text.isdigit():
                refs.append(text)
    return refs


def _unresolved_address_fallback(ctx):
    """Addressee names for an address the interpret model MARKED but could
    not spell -- the deterministic floor under the ADDRESSEE PRIORITY prompt
    clause, in the same spirit as the gate itself (a prompt instruction
    alone left a presence "motionless" for 25+ turns).

    Measured, chat 95 turn 3042 (grok-4.3), with the description-address
    clause already in the prompt: the model wrote flow.addressed_to=[0] --
    no character id 0 exists -- while its own sequence carried
    targets=["Trader Tate"] on the sleeve-grip and its notes said in words
    "Trader Tate is the only present named character being addressed". The
    structured reading existed; only the channel entry was garbage.

    Fires ONLY when every part of the marked address is unusable: no name
    string, and no int that resolves to a registered cast member (a real
    cast addressee means the address was resolved and there is nothing to
    repair). An EMPTY addressed_to stays empty -- the prompt licenses that
    for a genuinely ambiguous address, and this floor must not turn every
    beat into one with an addressee. Names come from the same place every
    other harvest here trusts: the interpret sequence's own structured
    fields, never free prose -- speech-element targets first, then the
    targets of overt actions declared beside speech (taking someone by the
    sleeve while asking them a question aims the question). No speech in
    the overt declaration, no address: words are what an address is made
    of."""
    interp = ctx.get("director_interpret") or {}
    flow = interp.get("flow") if isinstance(interp, dict) else None
    if not isinstance(flow, dict):
        return []
    raw = list(flow.get("addressed_to_refs") or [])
    if not raw:
        raw = list(flow.get("addressed_to") or [])
    entries = [r for r in raw if isinstance(r, (int, str))]
    if not entries:
        return []
    if any(isinstance(r, str) and r.strip() and not r.strip().isdigit()
           for r in entries):
        return []  # a usable string exists; the binder handles it directly
    cast_ids = set()
    for row in (ctx.cast or []):
        try:
            cast_ids.add(int(row["id"]))
        except Exception:
            continue
    ints = set()
    for r in entries:
        try:
            ints.add(int(str(r).strip()))
        except Exception:
            continue
    if ints & cast_ids:
        return []  # resolved to a registered character; loops.py's job
    elements = [e for e in (interp.get("sequence") or [])
                if isinstance(e, dict) and e.get("visibility") != "concealed"]
    if not any(e.get("type") == "speech" for e in elements):
        return []
    names, seen = [], set()
    def _take(pool):
        for n in pool or []:
            text = str(n or "").strip()
            if text and text.casefold() not in seen:
                seen.add(text.casefold())
                names.append(text)
    for e in elements:
        if e.get("type") == "speech":
            _take(e.get("targets"))
    if not names:
        for e in elements:
            if e.get("type") == "action":
                _take(e.get("targets"))
    return names


def _player_intended_targets(ctx, dr_output=None):
    """Whom the PLAYER's own lines were aimed at, as the resolve stage
    recorded it -- the third source of the address channel.

    `dialogue_log[].intended_target` is a structured field the Director
    fills for every line it logs, the player's included, and it is the one
    place a resolve-time judgment about the player's addressee survives
    when interpret marked no address at all. Measured, Harrowmere turn 2:
    the player walked to a market stall and asked the trader what they
    sold; interpret wrote `addressed_to: []`, resolve wrote
    `intended_target: "market trader"`, and with the flow channel empty the
    demand gate never saw an addressee -- two reeves in the hall next door
    were picked on the word "reeve" instead, the trader stayed silent, and
    the narrator invented the trader's answer.

    Only the player's own lines, and only when they are the player's: a
    line the Director logged for somebody else names that speaker's
    addressee, not the player's. The Director's OTHER judgments about
    addressees already reach the gate (`_character_address_of` reads every
    speaker's `intended_target` against a presence's exact name); this
    hands the same field to the DESCRIPTION binder, so "market trader" can
    bind to one body the way a flow ref would.
    """
    dr = dr_output if dr_output is not None else (
        ctx.get("director_resolve") or {})
    if not isinstance(dr, dict):
        return []
    p_name = _player_name_or_none(ctx)
    if not p_name:
        return []
    out, seen = [], set()
    for d in (dr.get("dialogue_log") or []):
        if not isinstance(d, dict):
            continue
        if str(d.get("speaker") or "").strip().casefold() != p_name.casefold():
            continue
        target = " ".join(str(d.get("intended_target") or "").split())
        if not target or target.casefold() in seen:
            continue
        seen.add(target.casefold())
        out.append(target)
    return out


def _communication_targets(ctx):
    """Whom the player's INDIRECT speech was aimed at, as interpret
    recorded it -- the fourth source of the address channel.

    A `communication` element is an address by construction: it carries an
    act and a target and nothing else ("asks Nookfeller whether the clerk
    found anything"). It writes no dialogue_log line, so the resolve
    stage's `intended_target` (`_player_intended_targets`) never exists
    for it, and interpret marked no `addressed_to` because the prompt
    licenses an empty channel for an ambiguous address. Measured,
    Harrowmere turn 33: the sequence held `targets: ["Reeve Halinham
    Nookfeller"]`, both address channels were empty, and the demand gate
    fell through to the loose word match, which qualified the other reeve
    too. Overt elements only, the player's own sequence only.
    """
    interp = ctx.get("director_interpret") or {}
    if not isinstance(interp, dict):
        return []
    out, seen = [], set()
    for element in (interp.get("sequence") or []):
        if not isinstance(element, dict):
            continue
        if element.get("type") != "communication":
            continue
        if element.get("visibility") == "concealed":
            continue
        for target in (element.get("targets") or []):
            text = " ".join(str(target or "").split())
            if text and text.casefold() not in seen:
                seen.add(text.casefold())
                out.append(text)
    return out


def _addressed_ref_strings(ctx, dr_output=None):
    """The address channel's usable strings: the director's own refs when it
    spelled any, else the structured-fallback names for an address it marked
    but could not spell, else whom the resolve stage says the player's own
    lines were aimed at (`_player_intended_targets`), else whom the
    player's indirect speech was aimed at (`_communication_targets`)."""
    refs = _raw_flow_addressed_refs(ctx)
    if refs:
        return refs
    refs = _unresolved_address_fallback(ctx)
    if refs:
        return refs
    refs = _player_intended_targets(ctx, dr_output)
    if refs:
        return refs
    return _communication_targets(ctx)


def _normalized_descriptor(text):
    """One canonical spelling for a visible-description address, so the same
    phrase binds to the same body at the gate, at commit, and on a later
    beat: casefolded, whitespace-collapsed, leading article dropped."""
    words = str(text or "").casefold().split()
    if words and words[0] in ("the", "a", "an", "that", "this"):
        words = words[1:]
    return " ".join(words)


def descriptor_bindings(ctx, dr_output=None):
    """{addressed_to string: bound presence display name} for every flow
    ref that names NOBODY -- no registered character, no extra player, no
    tracked or charter-derived presence.

    A player in a crowd of strangers addresses by what they can SEE -- "the
    man with the braided cords", "the woman behind the stall" -- because
    nobody has told them a name. Measured (chat 95, turns 3031-3041): the
    address died at interpret on every one of those beats while 44
    addressable bodies stood in the player's room, and it HAD to -- a
    charter body record carries name/competence/place/post/rank and a
    presence row name/room/co-presence, so no store anywhere records who
    sells cords, and a description is unresolvable by any reader from any
    store in principle.

    Resolution therefore cannot be retrieval; it is a BINDING that mints
    the fact -- the reverse of director_views' appearance-label mechanism.
    The Director owns what exists, so the described addressee is bound to
    one co-present body and the binding is canon from that beat on
    (track_background_presences persists the phrase into the bound body's
    sketch, turning the NEXT use of it into retrieval). Deterministic given
    the model's string: an exact or mentioned name is kept as itself, a
    stored earlier binding wins, else a seeded pick over the sorted
    co-present cohort -- never bare random. Firewall-clean: the player
    still never receives the name (narration renders unrecognised people
    through appearance labels); the binding publishes only what any
    onlooker in the room already sees.
    """
    refs = _addressed_ref_strings(ctx, dr_output)
    if not refs:
        return {}
    chat = ctx.chat
    cid = chat.id
    roster = {n.casefold() for n in _registered_name_roster(chat, ctx.cast)}
    roster |= {str((e.get("name") or "")).casefold()
               for e in (ctx.extra_players or [])}
    sc = wget(cid, "scene", {}) or {}
    presences = _fold_duplicate_presences(
        wget(cid, "background_presences", {}) or {}, sc)
    _pname = _player_name_or_none(ctx)
    p_room = str(room_of(sc, _pname) or "") if _pname else ""
    if p_room:
        # Same aperture as the demand gate: the player's room plus ambient
        # scope, so any name the Director could have been shown is known
        # here and cannot be mistaken for a description of somebody else.
        _places = {p_room}
        try:
            from world.spatial import ambient_scope
            _nearby, _ = ambient_scope(sc, p_room)
            _places.update(str(r) for r in (_nearby or ()) if r)
        except Exception:
            pass
        presences = with_charter_presences(
            cid, presences, sc, places=_places,
            frame_id=getattr(getattr(ctx, "turn", None), "frame_id", None))
    known = presence_name_items(presences)
    bindings = {}
    for ref in refs:
        cf = ref.casefold()
        if cf in roster or any(_presence_addressed_match(r, ref)
                               for r in roster):
            continue  # a cast/extra-player name is loops.py's, never bound
        matched = sorted({name.casefold(): name for name, _rec in known
                          if _presence_addressed_match(name, ref)}.values())
        if len(matched) == 1:
            # The ref names exactly one person; canonicalize a partial to
            # the display name so downstream matching is pure equality.
            if matched[0].casefold() != cf:
                bindings[ref] = matched[0]
            continue
        # Zero matches is a description; two or more is a partial that
        # singles nobody out ("the trader", in a square of traders). A
        # reference names a person only if it names ONE person -- both
        # cases resolve the same way, by binding.
        if not p_room:
            continue  # a description is of somebody SEEN; no vantage, no bind
        descriptor = _normalized_descriptor(ref)
        if not descriptor:
            continue
        # The described addressee is somebody the player can see: a
        # person-shaped body standing in the player's own room.
        cohort = sorted(
            (name, rec) for name, rec in known
            if name.casefold() not in roster
            and str(presence_room(sc, name, rec) or "") == p_room
            and _presence_speech_verdict(sc, name, rec) == "person")
        if not cohort:
            continue
        bound = ""
        for name, rec in cohort:
            stored = ((rec.get("sketch") or {}).get("descriptors") or [])
            if any(_normalized_descriptor(s) == descriptor for s in stored):
                bound = name  # the fact already exists; retrieval
                break
        if not bound:
            digest = hashlib.sha256(
                ("%s:%s" % (cid, descriptor)).encode("utf-8")).hexdigest()
            bound = cohort[int(digest, 16) % len(cohort)][0]
        bindings[ref] = bound
    return bindings


def _flow_addressed_refs(ctx, dr_output=None):
    """flow.addressed_to strings with every description address resolved to
    the body it binds to (descriptor_bindings above), so every consumer of
    the addressed class -- the demand gate, owed-reply bookkeeping, auto
    promotion, the scene manager -- hears an address-by-description exactly
    as it hears an address-by-name. `dr_output` is this beat's resolve
    output where the caller holds it before `ctx` does."""
    bindings = descriptor_bindings(ctx, dr_output)
    return [bindings.get(ref, ref)
            for ref in _addressed_ref_strings(ctx, dr_output)]


def _presence_addressed_match(name, ref):
    """PRECISE two-way match between one tracked name and one structured
    flow.addressed_to ref: equality, the whole name inside the ref
    ("Captain Trader Tate" names Trader Tate), or the whole title-stripped
    ref inside the name ("Tate" names Trader Tate). Deliberately NOT
    `_background_name_mentioned`: that fallback exists for PROSE, where
    "Crusher" carries a scene, and applied to this structured channel a
    single shared word matched everybody who shares it -- six "Regular N"
    records against "Regular 2" on the Part C bench, and every one of a
    market town's 44 "Trader *" bodies against any single trader ref, each
    match a FORCED pick."""
    name_cf = str(name or "").strip().casefold()
    ref_cf = str(ref or "").strip().casefold()
    if not name_cf or not ref_cf:
        return False
    if name_cf == ref_cf:
        return True
    if re.search(rf"\b{re.escape(name_cf)}\b", ref_cf):
        return True
    stripped = _normalized_descriptor(strip_name_titles(ref))
    return bool(stripped
                and re.search(rf"\b{re.escape(stripped)}\b", name_cf))


def _presence_in_addressed_refs(name, refs):
    """Is this presence named by the (already bound) addressed refs? Safe to
    keep partial-name containment here because `_flow_addressed_refs` has
    already canonicalized every ref: a unique partial became the display
    name, and an ambiguous or descriptive ref was bound to exactly one
    body (descriptor_bindings), so nothing reaching this test can fan out
    across a cohort."""
    return any(_presence_addressed_match(name, ref) for ref in refs)


def emerged_this_beat(ctx, dr_output, sc):
    """Display names stepping out of a crowd on THIS beat's ops (§C1.4).

    Emergence is a demand signal by definition -- someone wanted this person
    -- and it must count on the beat the Director declared it, not one beat
    late: the op itself is only APPLIED at commit (`commit_crowds`), after
    the background stage has already run, so the pre-commit gate reads the
    provisional ops the same way it already reads the provisional
    `dialogue_log`. A charter emerge is resolved read-only through the same
    pick commit will run (`charter_emergence_pick` is deterministic over
    persisted state, so the two reads agree unless this very beat's diff
    moves somebody -- in which case commit's answer stands and the voice
    simply went to the runner-up); an authored-crowd emerge names its person
    in ``who`` outright.
    """
    raw_ops = ((dr_output.get("state_diff") or {}).get("crowd_ops")
               or dr_output.get("crowd_ops") or [])
    if not isinstance(raw_ops, list):
        return set()
    from world import crowds as crowds_model

    names = set()
    derived_index = None
    for raw in raw_ops:
        op = raw.dict() if hasattr(raw, "dict") else (raw or {})
        if not isinstance(op, dict):
            continue
        if str(op.get("op") or "").strip().casefold() != crowds_model.OP_EMERGE:
            continue
        uid = str(op.get("crowd_id") or "").strip()
        who = " ".join(str(op.get("who") or "").split())
        if not crowds_model.is_charter_crowd_uid(uid):
            if who:
                names.add(who)
            continue
        if derived_index is None:
            # Same derivation commit_crowds performs, for the same reason:
            # with nothing stored, agreeing means being the same reader.
            from agents.common import charter_crowds_for_room, chatter_inputs
            inputs = chatter_inputs(ctx.chat.id, sc, turn_idx=ctx.turn.idx)
            derived_index = {
                str(crowd.get("uid")): crowd
                for room in (sc.get("rooms") or {})
                for crowd in charter_crowds_for_room(
                    ctx.chat.id, sc, room, inputs)}
        crowd = derived_index.get(uid)
        if crowd is None:
            continue
        place = str(crowd.get("room_uid") or "")
        present = sorted(
            name for name, where in (sc.get("positions") or {}).items()
            if str(where or "") == place)
        try:
            from world.charter_runtime import charter_emergence_pick
            display, _reason = charter_emergence_pick(
                ctx.chat.id, crowd.get("charter_key"), place, who=who,
                present=present, frame_id=ctx.turn.frame_id,
                turn_idx=ctx.turn.idx)
        except Exception:
            display = ""
        if display:
            names.add(display)
    return names


def pick_background_reactor(ctx, dr_output):
    """Single-winner convenience wrapper over pick_background_reactors: the
    top-ranked qualifying background presence, or None. Preserves the original
    gate contract for the common (max_reactors == 1) case and all callers/tests
    that expect one name.
    """
    picks = pick_background_reactors(ctx, dr_output, cap=1)
    return picks[0] if picks else None


def pick_background_reactors(ctx, dr_output, cap=1):
    """Deterministic DEMAND gate for the background_react stage: pick the
    presences an authored mind's own conduct calls on this beat, up to a
    ceiling. Names-only compatibility wrapper over `pick_voice_demand`,
    which is the same gate with the metadata the chorus rule needs.

    DESIGN_BACKGROUND_PRESENTATION §C1: a presence qualifies when it was
    ADDRESSED by an authored mind (the player's overt declaration, a flow
    address, a character's aimed line -- or a Director hand-off, `routed`,
    which is the Director itself demanding the voice), when it is OWED a
    reply, when it ACTED toward an authored mind last beat, or when it
    EMERGED from a crowd this beat. The list is never padded to `cap`, and
    [] stays the common case.

    Co-presence, salience and recency are NOT triggers, and three signals
    this gate used to honour are gone with them: `mentioned` (named in the
    Director's own resolved_event -- the prose already showed them, and
    prose salience is a model's judgment, not a demand), bare
    `dialogue_turns` history (tenure -- an open exchange re-qualifies
    through addressed/owed instead, §C3), and `at_post` (the standing
    invitation of working where you stand -- co-presence in its politest
    clothes; its live evidence, the chat-72 night clerk, was ALWAYS carried
    by the stronger signals, `routed` and the player's own words, and the
    quiet-visit barkeep it re-offered is now the crowd/chatter tier's job,
    which renders the room alive for zero calls, §C2). The old
    at-post audibility bar survives where it always also lived:
    `_character_address_of` still requires a line heard in FULL.

    This gate remains the deterministic floor under a prompt clause
    (mirroring infer_vehicle_zones in spatial_frames.py): a presence given
    direct orders was still rendered "motionless" for 25+ turns before it
    existed. Demand-driven does not soften that floor -- every one of the
    measured failures it was built for (direct orders, a direct address, a
    routed line) is an ADDRESS, the trigger that now forces the pick.
    """
    return pick_voice_demand(ctx, dr_output, cap=cap)["picks"]


def addressed_rooms(ctx, dr_output, sc, player_room):
    """The rooms the PLAYER's own lines are aimed INTO this beat, other than
    the one they stand in.

    A LINE AIMED AT A DOOR IS AIMED AT WHOEVER IS INSIDE. The gate's address
    triggers all name a PERSON -- a flow ref, an exact name, an aimed
    dialogue entry -- and a body the story has never named cannot be
    addressed by any of them; so a player calling through a doorway to a
    house they have not entered addressed nobody, the beat's evidence
    reached every mind inside (Harrowmere replay 2026-09-03 turn 17: 26
    claims acquired) and no voice could answer, because a voice candidate
    had to stand in the player's own room. The room the line is aimed into
    is read from what the beat already says: the target of each player
    line (`dialogue_log.intended_target`, the resolve stage's speech
    `target`) resolved to a room -- a room id, a room's name, or the
    position the beat leaves that target in -- and, when the player spoke
    and no target resolved anywhere, the room a declared move has not
    reached (the threshold). Whether the words ARRIVE is still the hearing
    channel's question (`demand_reaches`, aimed): an open door carries
    them, a shut one grades them down, and nothing here widens that.
    Bodies standing in these rooms are candidates on the place-addressed
    trigger, which ranks between a precise address and a loose mention and
    never forces the slot -- a house is answered by one person.
    """
    from story.scene import is_player_speaker

    sc = sc or {}
    rooms_by_id = sc.get("rooms") or {}
    room_ids = {str(r) for r in rooms_by_id}
    by_name = {}
    for rid, rdata in rooms_by_id.items():
        if isinstance(rdata, dict) and str(rdata.get("name") or "").strip():
            by_name.setdefault(
                str(rdata["name"]).strip().casefold(), str(rid))
    positions = dict(sc.get("positions") or {})
    sd = (dr_output or {}).get("state_diff") or {}
    if isinstance(sd.get("positions"), dict):
        positions.update({str(k): str(v) for k, v in sd["positions"].items()
                          if str(v or "")})
    after = {**sc, "positions": positions}

    def _room_for(target):
        t = str(target or "").strip()
        if not t:
            return ""
        if t in room_ids:
            return t
        rid = by_name.get(t.casefold())
        if rid:
            return rid
        return str(room_of(after, t) or "")

    chat = ctx.chat
    targets, spoke = [], False
    for d in ((dr_output or {}).get("dialogue_log") or []):
        if not isinstance(d, dict):
            continue
        if not is_player_speaker(str(d.get("speaker") or ""), chat):
            continue
        spoke = True
        targets.append(d.get("intended_target"))
    for row in ((dr_output or {}).get("public_evidence") or []):
        if not isinstance(row, dict) or row.get("kind") != "speech":
            continue
        if not is_player_speaker(str(row.get("actor") or ""), chat):
            continue
        spoke = True
        targets.append(row.get("target"))
    here = str(player_room or "")
    out, resolved_any = set(), False
    for target in targets:
        for one in (target if isinstance(target, (list, tuple))
                    else [target]):
            room = _room_for(one)
            if not room:
                continue
            resolved_any = True
            if room != here:
                out.add(room)
    if spoke and not resolved_any:
        interp = ctx.get("director_interpret") or {}
        mv = interp.get("movement") if isinstance(interp, dict) else None
        if isinstance(mv, dict) and mv.get("to_room") \
                and str(mv.get("mover") or "self") == "self":
            to = str(mv["to_room"])
            p_name = _player_name_or_none(ctx) or ""
            if to in room_ids and to != here \
                    and str(positions.get(p_name) or "") != to:
                out.add(to)
    return out


def pick_voice_demand(ctx, dr_output, cap=1):
    """The demand gate with its working, for the chorus rule's reader.

    Returns ``{"picks": [names], "meta": {name: {"addressed", "refs",
    "room", "why"}}}``: `background_react` needs to know which picks are
    addressees and which charter bodies they are, because addressees alone
    exceeding the path's ceiling means the address was to a crowd and is
    answered as one through the derived crowd (§C3) -- a decision this gate
    cannot take alone, since the crowd object lives on the perception seam.
    ``why`` is the trigger set that qualified the pick and the channel it
    arrived on, so a pick is auditable from the step (Harrowmere replay
    2026-09-03 turn 23: a gate watchman answered a line spoken in the
    smithy, and the step could not say which trigger reached him).
    """
    chat = ctx.chat
    cid = chat.id

    roster = {n.casefold() for n in _registered_name_roster(chat, ctx.cast)}
    roster |= {(e.get("name") or "").casefold() for e in (ctx.extra_players or [])}

    voiced_this_beat = {
        str(d.get("speaker") or "").casefold()
        for d in (dr_output.get("dialogue_log") or [])
    }
    # Presences whose Director-authored line was REMOVED so this stage could
    # voice them instead (agents/director.py). They are salient by
    # construction -- the Director chose to speak for them -- so they are
    # forced past `cap` exactly as a directly-addressed presence is, and they
    # must never count as `voiced_this_beat`, which is the whole hand-off.
    forced_routed = [
        str(n).strip() for n in (dr_output.get("routed_to_background") or [])
        if str(n).strip() and str(n).strip().casefold() not in roster
    ]
    diff = dr_output.get("state_diff") or {}
    for entity_def in (diff.get("entities") or {}).values():
        if isinstance(entity_def, dict) and entity_def.get("name"):
            voiced_this_beat.add(str(entity_def["name"]).casefold())
    # LAST, so the hand-off outranks the entity-mint exclusion. Minting the
    # presence and giving up its words are the two halves of one design --
    # the Director owns what EXISTS and the background stage owns what it
    # SAYS -- so a routed name appearing in `state_diff.entities` is the
    # Director doing its job, never evidence the line is already handled.
    # Subtracting before the loop above put the two halves in a race the
    # mint won: chat 72 turn 45 minted `night_clerk` as a `character`
    # entity in the same beat its line was routed here, and the mint
    # re-excluded the presence its own routing had just handed over.
    voiced_this_beat -= {n.casefold() for n in forced_routed}

    # NOT `ctx.input`, which is the raw text the player typed. See
    # `overt_declaration`: a whispered name used to qualify its own presence.
    player_input = overt_declaration_text(ctx)
    turn_idx = ctx.turn.idx
    sc = wget(cid, "scene", {}) or {}
    # Read through the duplicate fold: the ledger is healed at commit, but
    # this gate runs BEFORE commit, so a story already carrying an id-keyed
    # twin (chat 80) must not be able to dispatch the twin one last time.
    presences = _fold_duplicate_presences(
        wget(cid, "background_presences", {}) or {}, sc)

    addressed_refs = _flow_addressed_refs(ctx, dr_output)

    # Where the player is standing, scoping which charter bodies overlay
    # into the candidate ledger at all.
    _pname = _player_name_or_none(ctx)
    player_room = room_of(sc, _pname) if _pname else ""
    charter_places = {str(player_room)} if player_room else set()
    if player_room:
        try:
            from world.spatial import ambient_scope
            nearby, _ = ambient_scope(sc, player_room)
            charter_places.update(str(p) for p in (nearby or ()) if p)
        except Exception:
            pass
    # The rooms the player's lines are aimed INTO (`addressed_rooms`): the
    # bodies standing there are candidates too, on the place-addressed
    # trigger below.
    aimed_rooms = addressed_rooms(ctx, dr_output, sc, player_room)
    charter_places.update(aimed_rooms)
    presences = with_charter_presences(
        cid, presences, sc, places=charter_places,
        frame_id=getattr(getattr(ctx, "turn", None), "frame_id", None))
    if forced_routed:
        presences = with_charter_presences(
            cid, presences, sc, names=forced_routed,
            frame_id=getattr(getattr(ctx, "turn", None), "frame_id", None))
    # A presence the Director MINTED THIS BEAT has no record yet -- and
    # never can at this point, because `track_background_presences` writes
    # it at commit, after this gate. Iterating `presences` alone therefore
    # made the forced hand-off unreachable for the one class of presence
    # that most needs it: the one who just arrived because the beat called
    # for someone to arrive.
    #
    # Live, chat 72 turn 45. The player rang a hotel bell and said outright
    # "someone should be staffing it, use logic and reasoning instead of
    # assuming no one is there". The Director agreed, minted a night clerk
    # and wrote him muttering "I'm coming, I'm coming". The ownership guard
    # correctly routed his line here -- he is person-shaped and deserves
    # his own call with his own perception object -- and this loop could
    # not see him, so the line was deleted and nothing replaced it. The
    # narrator's last sentence was "Somewhere beyond the desk, a door might
    # shift. Or not."
    #
    # A routed name with no record is seeded EMPTY, so nothing is invented:
    # every salience test below reads absent history as absent, and the
    # presence qualifies on `routed` alone -- which is the correct and only
    # claim, since the Director choosing to speak for someone IS the
    # salience finding.
    ranked = dict(presences)
    for name in forced_routed:
        if presence_record_for(ranked, name, sc)[1] is None:
            ranked[name] = {}

    # The two non-address triggers' shared inputs, computed once. `emerged`
    # reads this beat's provisional crowd ops; `acting`'s charter half reads
    # the last landed window through the registry. Both are deterministic
    # over persisted state plus this beat's own step outputs.
    emerged_names = emerged_this_beat(ctx, dr_output, sc)
    if emerged_names:
        # An emerging charter body may have no record yet (the op is applied
        # at commit, after this gate); derive one so the pick can voice the
        # person the Director just asked the crowd for.
        presences = with_charter_presences(
            cid, presences, sc, names=sorted(emerged_names),
            frame_id=getattr(getattr(ctx, "turn", None), "frame_id", None))
        ranked = dict(presences)
        for name in forced_routed:
            if presence_record_for(ranked, name, sc)[1] is None:
                ranked[name] = {}
    try:
        from world.charter_runtime import bodies_acting_toward_authored
        acting_charter = bodies_acting_toward_authored(
            cid, roster, frame_id=getattr(
                getattr(ctx, "turn", None), "frame_id", None))
    except Exception:
        acting_charter = set()

    # Where the beat's authored minds are standing, for the channel test on
    # each candidate below. Computed once: `positions` does not move inside
    # this loop.
    authored_rooms = authored_mind_rooms(sc, roster)
    # The words this story's tracked names hold in common -- its title
    # vocabulary, derived rather than listed (`_shared_name_words`).
    shared_words = _shared_name_words(
        presence_display_name(k, r) for k, r in ranked.items())

    candidates = []
    forced = 0
    for _rkey, record in ranked.items():
        name = presence_display_name(_rkey, record)
        if not name:
            continue
        cf = name.casefold()
        # `name_in_roster`, not bare equality. Measured chat 95 turn 17
        # (2026-08-28): a stored presence record spelled
        # `captain Jean-Luc Picard` failed `cf in roster` -- the roster holds
        # the bare `jean-luc picard` -- so the registered captain was selected
        # as a background presence, produced a stateless line through
        # `character_bg` while his OWN `character_major` call ran in the same
        # beat, and that line became the final sentence of the narrated prose.
        # No notice was raised. The right test was already in this module one
        # screen above, and its docstring was written for this exact failure;
        # the gate simply did not call it. Title-stripped both directions is
        # what closes it: a presence record carries whatever spelling the prose
        # used, and a roster carries the bare name.
        if name_in_roster(name, roster) or cf in voiced_this_beat:
            continue
        # THE ADDRESSED CLASS (§C1.1) -- four spellings of one trigger, an
        # authored mind (or the Director, for `routed`) turning toward this
        # person on purpose. The director's own flow plan naming this
        # presence as the player's addressee is one the raw-text check can
        # miss entirely (an address by role or epithet never mentions the
        # tracked name); `routed` is the Director writing a line for this
        # presence that the engine removed so this stage could do the job
        # properly -- the hand-off exists precisely so removing a line
        # cannot become silence.
        flow_addressed = _presence_in_addressed_refs(name, addressed_refs)
        routed = name in forced_routed
        # Two grades of a raw-text address. PRECISE (the full name, a flow
        # ref, a routed line, an aimed character line) is what the §C3
        # guarantee covers and what forces the pick; LOOSE (the significant-
        # word fallback) qualifies and ranks below it, because fuzzy must
        # never widen -- see `_background_name_named_exactly` for the
        # measured six-for-one failure that split them.
        addressed_exact = _background_name_named_exactly(name, player_input)
        addressed = addressed_exact or _background_name_mentioned(
            name, player_input, shared=shared_words)
        # Where they ARE, for anything about what reaches them.
        here = presence_room(sc, name, record)
        # A registered character (or the player) who spoke directly TO this
        # presence this beat -- read-only here; the owed-reply debt is written
        # at commit (track_background_presences), never in this pre-commit gate.
        char_addr = _character_address_of(dr_output, name, roster, sc, here)
        # OWED (§C1.2): an unexpired reply debt from a beat the gate spent
        # elsewhere. This is what keeps an open exchange re-triggering with
        # no tenure list anywhere.
        owed = _valid_pending_reply(record, turn_idx)
        # ACTING (§C1.3): this presence turned toward an authored mind last
        # beat -- a fired reaction aimed at one (`engaged_turns`, written at
        # commit), or a charter act whose `other` is a bound body or an
        # authored figure (last landed window; the same one-window lag every
        # window_acts reader tolerates).
        acting = ((turn_idx - 1) in (record.get("engaged_turns") or ())
                  or name in acting_charter)
        # EMERGED (§C1.4): stepping out of a crowd this beat is a demand by
        # definition -- someone wanted this person.
        emerged = name in emerged_names
        # PLACE-ADDRESSED: the player's line was aimed into the room this
        # body stands in (`addressed_rooms`) -- a call through a doorway to
        # whoever is inside. Ranks below a precise address and above a
        # loose mention; never forces the slot.
        place_addressed = bool(here) and str(here) in aimed_rooms
        addressed_precise = bool(flow_addressed or routed or addressed_exact
                                 or char_addr)
        addressed_any = bool(addressed_precise or addressed
                             or place_addressed)
        if not (addressed_any or owed or acting or emerged):
            continue
        # THE WORKING, for the step's audit: which triggers qualified this
        # candidate, then (below) the channel that carried the demand.
        why = [w for w, hit in (
            ("flow_addressed", flow_addressed), ("routed", routed),
            ("named_exactly", addressed_exact),
            ("character_address", bool(char_addr)),
            ("mentioned", addressed and not addressed_exact),
            ("place_addressed:%s" % here, place_addressed),
            ("owed", bool(owed)), ("acting", acting), ("emerged", emerged),
        ) if hit]
        # THE CHANNEL TEST (`demand_reaches`). A trigger says a demand was
        # RAISED; it does not say the demand arrived. Three of the spellings
        # above are the Director's own judgment for THIS beat -- it routed a
        # line here, it named this presence the player's addressee, it called
        # them out of a crowd -- and the Director owns what exists, so a
        # hand-off that becomes silence is precisely the failure this gate was
        # built to end; those are exempt. `char_addr` is exempt because it has
        # already passed this same bar, aimed more precisely, at its own
        # speaker's room. What is left claims something reached this person
        # without ever testing that it could: the player's raw words, and the
        # two carried debts. Filtering them here also makes the gate and the
        # debt WRITER agree -- `track_background_presences` has applied the
        # hearing bar to the player's precise address all along, so the gate
        # was spending slots on debts its own writer would have refused to
        # accrue.
        if not (routed or flow_addressed or emerged or char_addr):
            _aimed = bool(addressed or acting or place_addressed)
            if not demand_reaches(sc, here, authored_rooms, aimed=_aimed):
                continue
            why.append("channel:%s" % (
                "unplaced" if not here or not authored_rooms
                else ("hearing" if _aimed else "same_room")))
        else:
            why.append("channel:exempt")
        # Only a person may hold a background speaking turn. The ledger says
        # nothing about what a name DENOTES, so a device with an accrued
        # record qualified exactly like a barkeep: chat 80's ceiling-mounted
        # Scranton Reality Anchors (kind "device") were picked at their
        # "post" on turn 3 and again on turn 7 and interrogated the player.
        # A thing never speaks here; where the scene record cannot decide
        # (see _presence_speech_verdict), only the Director's own explicit
        # judgment this beat -- routing the line here, or naming this
        # presence the player's addressee -- can hand over a voice.
        verdict = _presence_speech_verdict(sc, name, record)
        if verdict == "thing":
            continue
        if verdict == "undecided" and not (routed or flow_addressed):
            continue
        if addressed_precise:
            # AN ADDRESSEE IS NEVER SILENTLY DROPPED (§C3): a named
            # counterpart failing to answer is the one visible failure mode,
            # so every PRECISE spelling of an address widens the slots --
            # the rule the flow-addressed and routed picks already had,
            # extended to the whole class. Overflow past the path's own
            # ceiling is the caller's chorus decision, not a drop.
            forced += 1
        # Overflow order (§C3): addressed > owed > acting > emerged, then
        # the B3 entanglement digest (patched in below, once, for charter
        # bodies only), then stably. Precise addresses outrank loose ones,
        # or a cap of one could hand the beat to a shared-word cousin of
        # the person actually named.
        # THE SAME BODY ANSWERS NEXT TIME. Among candidates the triggers
        # rank equally, the one who has already spoken in this story --
        # most recently first -- outranks one who never has: the reader
        # met a person, and a visit back to the room should find that
        # person, not whichever holder of the same post the tie-break
        # reached. Measured, Harrowmere turn 33: the reeve the player had
        # handed a letter to and the reeve who had never been spoken to
        # tied on every trigger bit and the string sort chose between
        # them. Sits below the four demand triggers (a debt or an act is a
        # stronger claim on the beat than familiarity) and above the
        # charter entanglement digest and recency of record.
        familiar = max(
            [int(t) for t in (record.get("dialogue_turns") or ())
             if isinstance(t, int)] or [-1])
        priority = [3 if addressed_precise
                    else (2 if place_addressed else (1 if addressed_any else 0)),
                    bool(owed), bool(acting),
                    bool(emerged), familiar, 0.0,
                    record.get("last_turn") or -1]
        candidates.append(
            {"priority": priority, "name": name, "record": record,
             "room": str(here or ""),
             "addressed": bool(addressed_precise),
             "why": why,
             # Qualified on the loose word-match ALONE: no precise address,
             # no debt, no act, no emergence, no place. See the subject
             # rule below.
             "loose_only": bool(addressed and not addressed_precise
                                and not place_addressed
                                and not (owed or acting or emerged)),
             # The PLAYER's own precise address specifically (a flow ref --
             # description bindings included -- or their exact name in the
             # declaration), so the stage downstream can hand the presence
             # the address it actually received. Deliberately excludes the
             # loose significant-word mention: fuzzy must never put words
             # in the player's mouth about who they turned toward.
             "player_addressed": bool(flow_addressed or addressed_exact),
             "refs": [r for r in (record.get("charter_refs") or [])
                      if isinstance(r, dict)]})

    if not candidates:
        return {"picks": [], "meta": {}}
    # A NAME IN A LINE AIMED AT SOMEONE ELSE IS A SUBJECT, NOT AN ADDRESSEE.
    # The loose word-match exists so "Crusher" can carry a scene once the
    # doctor has been established; it was never a finding that the speaker
    # turned toward that person. When this beat HAS a precise addressee --
    # a flow ref, an exact name, an aimed line, a routed hand-off -- every
    # candidate that qualified on the loose match alone was merely talked
    # ABOUT, and voicing them answers a question that was put to somebody
    # else. Measured, Harrowmere turn 4: the player asked the reeve's
    # clerk "which of you is the reeve?"; the clerk was the addressee, and
    # the reeve, picked on the word "reeve", answered "give it here" in the
    # same beat, so two people replied to one question and their answers
    # disagreed about whether the reeve was even in the building.
    if any(c["addressed"] for c in candidates):
        candidates = [c for c in candidates if not c["loose_only"]]
    if any(c["refs"] for c in candidates):
        # The B3 tie-break, computed against the authored minds standing in
        # the candidate's own room; one registry fetch for every candidate.
        try:
            from world.charter_runtime import (charter_entanglement_of,
                                               registry_for)
            registry = registry_for(
                cid, getattr(getattr(ctx, "turn", None), "frame_id", None))
            positions = (sc.get("positions") or {})
            for c in candidates:
                if not c["refs"]:
                    continue
                present = sorted(
                    n for n, where in positions.items()
                    if str(where or "") == c["room"]
                    and str(n).casefold() in roster)
                c["priority"][5] = round(charter_entanglement_of(
                    cid, c["refs"], present, registry=registry), 6)
        except Exception:
            pass
    # Case-blind on the name: a stored spelling's capitalisation is not a
    # fact about the person, and it once decided this sort ("Reeve H..."
    # against "Reeve f...", with the lower-case f sorting later and so
    # winning the reverse order).
    candidates.sort(key=lambda c: (c["priority"], c["name"].casefold()),
                    reverse=True)
    # Every addressee sorts first (top priority bit) and must answer THIS
    # beat: widen the cap to fit them all, then fill any slots left up to
    # `cap` with the remaining demand set.
    #
    # The stage downstream voices a presence BY NAME, so two records sharing
    # a display name collapse to one pick here: dispatching the same name
    # twice would voice one body with two turns.
    slots = max(forced, max(0, int(cap)))
    picks, meta, seen = [], {}, set()
    for c in candidates:
        if len(picks) >= slots:
            break
        if c["name"].casefold() in seen:
            continue
        seen.add(c["name"].casefold())
        picks.append(c["name"])
        meta[c["name"]] = {"addressed": c["addressed"], "refs": c["refs"],
                           "player_addressed": bool(c.get("player_addressed")),
                           "room": c["room"], "why": list(c.get("why") or [])}
    return {"picks": picks, "meta": meta}

def _propose_promotions(ctx, presences, scene):
    """A MIND IS EARNED, AND THE ENGINE SAYS WHEN. Deterministic, at commit,
    once per presence: the beat a tracked person's record first crosses
    the story's promotion threshold (`promotion_thresholds` -- dialogue
    turns at `BACKGROUND_PROMOTION_DIALOGUE_THRESHOLD`, mentions at
    `BACKGROUND_PROMOTION_MENTION_THRESHOLD`, both per-chat overridable)
    with a person's verdict and a real name, the record is stamped
    `promotion_proposed_turn` and the Director is told through the engine
    channel it reads next beat (`tell_director`), alongside a turn warning
    for the owner. The offer itself was always here (`promotable`, read by
    the presences panel and by auto-promotion); what was missing was the
    MOMENT, surfaced to the two readers who act on it. Measured, Harrowmere
    turns 5, 15 and 17: the Director, wanting to keep a person, wrote them
    into `cast_changes`, which names attached characters only, and the
    refusal said so and nothing more -- the Director had no other channel
    to reach for and no signal that the engine already held one. Returns
    the display names proposed this beat.
    """
    limits = promotion_thresholds(ctx.chat.id)
    turn_idx = ctx.turn.idx
    out = []
    for key, record in (presences or {}).items():
        if not isinstance(record, dict) or record.get(
                "promotion_proposed_turn") is not None:
            continue
        dialogue = len(record.get("dialogue_turns") or [])
        mentions = len(record.get("mention_turns") or [])
        if dialogue < limits["dialogue"] and mentions < limits["mention"]:
            continue
        name = presence_display_name(key, record)
        if presence_is_unnamed(key, record):
            continue
        if _presence_speech_verdict(scene, name, record) != "person":
            continue
        record["promotion_proposed_turn"] = turn_idx
        out.append(name)
        addressed = len(record.get("addressed_turns") or [])
        msg = ("%s has spoken on %d beat%s and been turned to on %d; the "
               "engine has proposed them for promotion to a character, "
               "which the owner confirms from the presences panel. Until "
               "then they stay a presence: voice them through the "
               "background stage, and never name them in cast_changes, "
               "which attaches nobody."
               % (name, dialogue, "" if dialogue == 1 else "s", addressed))
        ctx.tell_director(msg)
        ctx.add_warning("promotion proposed: " + msg)
    return out


def promotable_background_presences(chat_id):
    sc = wget(chat_id, "scene", {}) or {}
    presences = _fold_duplicate_presences(
        wget(chat_id, "background_presences", {}) or {}, sc)
    limits = promotion_thresholds(chat_id)
    out = []
    for key, record in presences.items():
        name = presence_display_name(key, record)
        promotable = (
            len(record.get("dialogue_turns") or []) >= limits["dialogue"]
            or len(record.get("mention_turns") or []) >= limits["mention"]
        )
        # Promotion mints a MIND -- a sheet, memories, a psychology -- and a
        # thing cannot hold one, however much history its record accrued
        # before the speech gate existed (chat 75's utility sash spoke on
        # three turns; chat 80's PA-class fixtures are one dialogue line away
        # from the same flag).
        #
        # THIS BAR IS HIGHER THAN THE SPEECH GATE'S, and deliberately so.
        # Letting a presence say one line is a smaller commitment than minting
        # a person out of it, so "undecided" is enough for the first and not
        # for the second. It used to demote only an outright "thing", which
        # left every presence the kind string cannot classify sitting in the
        # promotion list: chat 84 offered the Scranton Reality Anchor -- kind
        # "device", a bolted suppression fixture -- because "device" is off
        # the deny-list ON PURPOSE (so a sentient robot stays trackable) and
        # a fixture is not portable, so nothing else caught it either.
        #
        # An undecided presence is not refused, only not OFFERED: a "dalek war
        # machine" the player keeps engaging is still promotable by hand, and
        # that is the right place for a judgement no deterministic signal can
        # make. `nature` -- blurb_mint's frozen answer -- promotes it back to
        # "person" the moment anything actually asks the question.
        if promotable and _presence_speech_verdict(sc, name, record) != "person":
            promotable = False
        # A presence with no real name -- none at all, or an id-shaped string
        # standing where a name should (a live ledger tracked three raw hex
        # ids as "names") -- is still a person the engine keeps, but promotion
        # writes the name into a sheet's permanent identity, so an unnamed
        # presence is never OFFERED. It stays listed and becomes promotable
        # the moment the story names it.
        if promotable and presence_is_unnamed(key, record):
            promotable = False
        out.append({
            "id": key,
            "name": name,
            "first_turn": record.get("first_turn"),
            "last_turn": record.get("last_turn"),
            "dialogue_turns": record.get("dialogue_turns") or [],
            "mention_turns": record.get("mention_turns") or [],
            "promotable": promotable,
        })
    out.sort(key=lambda r: (-r["promotable"], -(r["last_turn"] or 0)))
    return out


def _refuse_name_collision(cid, new_name):
    """Refuse to mint a character whose in-story name is already taken.

    Names are IDENTITY here, not decoration: `scene.positions`, the active
    cast, addressing, perception routing and every psychology write are keyed
    on them. Two people called the same thing in one story is not a cosmetic
    duplicate -- it is one mind's state reachable under another's key, which is
    the exact failure the information firewall exists to prevent.

    The player's persona is the one that matters most and the one that was
    actually hit: a promoted market seller minted as "Hinami" alongside a
    player persona named Hinami would have shared her position entry outright
    (see the `positions` seed below).

    Raised rather than silently renamed. On the autonomous path this is caught
    upstream and becomes a turn warning, leaving the presence tracked and
    promotable once whatever caused the clash is resolved.
    """
    from story.scene import persona_of

    wanted = str(new_name or "").strip().casefold()
    if not wanted:
        raise ValueError("A promoted character needs a name.")
    chat_row = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    taken = {}
    player = persona_name(persona_of(dict(chat_row))) if chat_row else ""
    if player:
        taken[str(player).casefold()] = "the player's persona"
    for row in q(
            "SELECT ch.name AS name FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?", (cid,)):
        key = str(row["name"] or "").strip().casefold()
        if key:
            taken.setdefault(key, "a character already in this story")
    if wanted in taken:
        raise ValueError(
            "Refusing to promote %r: that name belongs to %s. Names are how "
            "this engine tells minds apart." % (new_name, taken[wanted]))


def promote_background_character(cid, name, sheet=None, memory_seeds=None,
                                 *, frame_id=None, promoted_turn=None):
    """Attach a tracked background presence as a real character: mint the
    characters/chat_chars rows, seed her scene position, mutual recognition
    with the player and every registered cast member, and any starter
    memories, then drop the presence record. Forward-only: past turns'
    steps/variants are untouched -- she becomes character_step-eligible
    starting next turn, the same as manually attaching any other character
    mid-chat.

    `sheet`/`memory_seeds` are the reviewed draft when called from the
    confirm-promotion route (app.py); when omitted (the autonomous path,
    see auto_promote_background_characters) a sheet is minted from the
    chat's own events record via importers.draft_promoted_character -- an
    LLM call, so this must never run inside the turn's commit transaction.
    Returns the new character id.
    """
    from story.importers import draft_promoted_character
    from story.scene import persona_of

    scene_for_identity = wget(cid, "scene", {}) or {}
    presences_for_identity = _fold_duplicate_presences(
        wget(cid, "background_presences", {}) or {}, scene_for_identity)
    # `name` may be the tracked record's uid (the promotion routes pass the
    # id) or a display name (older callers, hand promotion of an untracked
    # figure). Two tracked records answering to one display name REFUSE to
    # resolve -- promoting under an ambiguous name would seed one person's
    # sheet and first-person memories from the other's history, and that
    # weld is permanent (characters row, memories, relationships).
    presence_key, presence_record = presence_record_for(
        presences_for_identity, name, scene_for_identity)
    if presence_record is None and _presence_lookup(
            presences_for_identity, name,
            scene_for_identity)[2] == "ambiguous":
        raise ValueError(
            "Refusing to promote %r: more than one tracked presence answers "
            "to that name. Promote by presence id instead." % name)
    presence_record = presence_record or {}
    _display = presence_display_name(presence_key, presence_record)
    if _display:
        name = _display
    if presence_key is not None and presence_is_unnamed(
            presence_key, presence_record):
        raise ValueError(
            "Refusing to promote an unnamed presence: promotion writes the "
            "name into a permanent character identity, and this record has "
            "no real name yet.")
    from world.charter_runtime import promotion_bundle
    charter_bundle = promotion_bundle(
        cid, name, record=presence_record, frame_id=frame_id,
        promoted_turn=promoted_turn)

    if sheet is None:
        draft = draft_promoted_character(cid, name)
        sheet = draft["sheet"]
        if memory_seeds is None:
            memory_seeds = draft["memory_seeds"]

    sheet = copy.deepcopy(sheet)
    handoff = ((charter_bundle or {}).get("handoff") or {})
    if handoff:
        sheet.setdefault("embodiment", {}).setdefault(
            "interoception", {}).update(handoff.get("interoception") or {})
        sheet.setdefault("psychology", {}).setdefault(
            "stress_profile", {}).update(handoff.get("stress_profile") or {})
        sheet.setdefault("initial_state", {}).setdefault(
            "stress", {}).update(handoff.get("stress") or {})
        sheet.setdefault("initial_state", {}).setdefault(
            "hedonic", {}).update(handoff.get("hedonic") or {})
    sheet = normalize_character_data(sheet)
    memory_seeds = [str(m) for m in (memory_seeds or []) if str(m).strip()]
    _refuse_name_collision(cid, character_name(sheet))

    char_id = qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (
            character_name(sheet), json.dumps(sheet, ensure_ascii=False),
            json.dumps({
                "format": "promoted", "chat_id": cid,
                **({"charter": charter_bundle["charter"],
                    "charter_body": charter_bundle["body"]}
                   if charter_bundle else {}),
            }, ensure_ascii=False),
            time.time(),
        ),
    )
    initial_active = character_initial_active_state(sheet)
    _charter_color = ""
    if charter_bundle:
        from story.dialogue_colors import auto_dialogue_color, normalize_color
        _charter_color = normalize_color(
            charter_bundle.get("dialogue_color")) or auto_dialogue_color(
                charter_bundle.get("dialogue_color_seed"))
    qi(
        "INSERT INTO chat_chars(chat_id,char_id,status,state,dialogue_color) "
        "VALUES(?,?,'active',?,?)",
        (cid, char_id, json.dumps({
            "active_state": initial_active,
            **({"charter_origin": {
                "charter": charter_bundle["charter"],
                "body": charter_bundle["body"],
                "stood": handoff.get("stood") or {},
            }} if charter_bundle else {}),
            # The map a townsperson arrives with: the town's public rooms
            # and the routes this body walked, seeded once and thereafter
            # written only by `commit_place_graph.update_place_graph` --
            # the same graph any character builds, with a head start the
            # firewall permits because a life in a town is a channel to
            # its streets (`charter_promote.inherited_place_graph`).
            **({"place_graph": charter_bundle["place_graph"]}
               if charter_bundle and (charter_bundle.get("place_graph")
                                      or {}).get("nodes") else {}),
        }, ensure_ascii=False), _charter_color),
    )

    # Charter's evidence-backed local stances become the promoted mind's
    # ordinary relationship graph.  Copy the projection and append one
    # explanation row per non-zero axis; do not ask a model to reinterpret a
    # history the simulator already knows exactly.
    if handoff.get("social_judgments"):
        from mind.memory import (get_relationships, record_relationship_event,
                                 save_relationships)

        graph = get_relationships(cid, char_id, frame_id=frame_id)
        social_names = (charter_bundle or {}).get("social_names") or {}
        for stance in handoff.get("social_judgments") or ():
            if not isinstance(stance, dict):
                continue
            subject = str(stance.get("subject") or "")
            target = str(social_names.get(subject) or subject)
            if not target:
                continue
            values = {
                "trust": float(stance.get("trust") or 0.0),
                "emotional_valence": float(stance.get("warmth") or 0.0),
                "fear": float(stance.get("fear") or 0.0),
                "respect": float(stance.get("respect") or 0.0),
                "suspicion": float(stance.get("suspicion") or 0.0),
            }
            graph.update(target, **values, last_interaction_turn=(
                int(promoted_turn or 0)))
            triggers = [str(reason.get("evidence_id") or "")
                        for reason in stance.get("reasons") or ()
                        if isinstance(reason, dict)
                        and reason.get("evidence_id")]
            for axis, value in (
                    ("trust", values["trust"]),
                    ("warmth", values["emotional_valence"]),
                    ("fear", values["fear"]),
                    ("respect", values["respect"]),
                    ("suspicion", values["suspicion"])):
                if not value:
                    continue
                record_relationship_event(
                    cid, char_id, target, axis, value, triggers=triggers,
                    note="carried across Charter promotion",
                    provenance="charter", turn_idx=int(promoted_turn or 0),
                    frame_id=frame_id)
        save_relationships(cid, char_id, graph, frame_id=frame_id)

    # ACQUAINTANCE IS AN EDGE, NOT A SENTENCE. The block above is gated on
    # `social_judgments`, which measured ZERO holders across all four charters
    # of a real story -- so the only writer into the relationship graph never
    # ran, and a person who stood beside the same colleagues for 720 hours
    # arrived a stranger to every one of them in the one structure the
    # character pipeline actually consults. This runs on plain acquaintance,
    # which every body has. A judgment, where one exists, is written after and
    # wins: an opinion earned by evidence outranks the baseline familiarity
    # gives.
    if handoff.get("acquaintances"):
        from mind.memory import get_relationships, save_relationships

        graph = get_relationships(cid, char_id, frame_id=frame_id)
        social_names = (charter_bundle or {}).get("social_names") or {}
        judged = {str(social_names.get(str(stance.get("subject") or ""))
                      or stance.get("subject") or "")
                  for stance in (handoff.get("social_judgments") or ())
                  if isinstance(stance, dict)}
        for row in handoff.get("acquaintances") or ():
            if not isinstance(row, dict):
                continue
            body = str(row.get("body") or "")
            target = str(social_names.get(body) or row.get("name") or body)
            if not target or target in judged:
                continue
            familiarity = float(row.get("familiarity") or 0.0)
            # Regard is centred on 1.0 in Charter's own scale; either side of
            # it is thinking better or worse of somebody. Warmth carries that;
            # trust follows familiarity, discounted when the acquaintance is
            # secondhand, because knowing OF a person is not knowing them.
            standing = float(row.get("regard") or 1.0) - 1.0
            firsthand = bool(row.get("firsthand"))
            graph.update(
                target,
                trust=round(familiarity * (1.0 if firsthand else 0.4), 4),
                emotional_valence=round(standing, 4),
                last_interaction_turn=int(promoted_turn or 0))
        save_relationships(cid, char_id, graph, frame_id=frame_id)

    chat_row = dict(q("SELECT * FROM chats WHERE id=?", (cid,), one=True))
    if frame_id is None:
        sc = wget(cid, "scene", None)
    else:
        from core.db import wget_for_frame
        sc = wget_for_frame(cid, "scene", frame_id, None)
    if isinstance(sc, dict):
        positions = sc.setdefault("positions", {})
        if character_name(sheet) not in positions:
            player_name = persona_name(persona_of(chat_row))
            positions[character_name(sheet)] = (
                (charter_bundle or {}).get("place")
                or positions.get(player_name))
        # Survival remains opt-in.  If this scene already owns vitals, carry
        # the body's real depletion across; never create the subsystem here.
        if isinstance(sc.get("vitals"), dict) and handoff.get("body_state"):
            vitals = {
                key: handoff["body_state"][key]
                for key in ("stamina", "nourishment", "injury")
                if key in handoff["body_state"]
            }
            if vitals:
                sc["vitals"].setdefault(character_name(sheet), {}).update(vitals)
        seed_initial_attire(
            sc, character_name(sheet), character_initial_outfit(sheet))
        if frame_id is None:
            wset(cid, "scene", sc)
        else:
            from core.db import wset_for_frame
            wset_for_frame(cid, "scene", sc, frame_id)

    # Seed mutual recognition with the player and with every other
    # already-registered cast member -- she's been part of the scene the
    # whole time, so treating her as a stranger to everyone else present
    # would be as wrong as it was to treat her as a stranger to the player.
    # An authored answer with a stated reason, which is why this one is
    # unconditional where the other two attach paths take the caller's.
    seed_mutual_recognition(
        cid, character_name(sheet),
        recognition_roster(cid, chat_row, exclude_char_id=char_id))

    memory_rows = [
            {
                "chat_id": cid, "char_id": char_id, "turn_id": None,
                "kind": "episodic", "provenance": "witnessed", "salience": 0.6,
                "content": seed, "turn_idx": None,
                "frame_id": frame_id,
                "event_key": f"promotion:{cid}:{char_id}:{i}",
            }
            for i, seed in enumerate(memory_seeds)
        ]
    for memory in (handoff.get("memories") or []):
        # Charter handoff may carry chronology/participant metadata used by
        # the richer featured-resident compiler. The memory store accepts its
        # own vocabulary only; do not leak routing metadata through **kwargs.
        stored_memory = {
            key: copy.deepcopy(value) for key, value in memory.items()
            if key in {"kind", "category", "provenance", "salience",
                       "content", "gist", "key_phrases", "entities",
                       "location", "emotional_context", "valence",
                       "arousal", "encoding_valence", "encoding_arousal",
                       "confidence", "importance", "disputed"}
        }
        memory_rows.append({
            "chat_id": cid, "char_id": char_id, "turn_id": None,
            "turn_idx": promoted_turn, "frame_id": frame_id,
            **stored_memory,
            "event_key": "charter:%s:%s" % (
                charter_bundle["charter"], memory.get("event_key") or "memory"),
        })
    if memory_rows:
        add_memories_batch(memory_rows)

    # If the chat launched from a greeting that put this presence on the
    # page, the extraction retained her mind unclaimed -- a background
    # presence has no memory or psychology until this exact moment. Claim it
    # now, after recognition is seeded so the persona's name is a legitimate
    # handle. Local import: greetings imports agents.runtime, and this module
    # must stay importable inside the commit family.
    from story.greetings import claim_greeting_mind
    claim_greeting_mind(cid, char_id, name, sheet)

    if charter_bundle:
        from world.charter_runtime import bind_promoted_character
        bound = bind_promoted_character(
            cid, charter_bundle, char_id=char_id,
            name=character_name(sheet),
            entity_id=(sheet.get("identity") or {}).get("uid") or "",
            promoted_turn=promoted_turn,
            place=((sc or {}).get("positions") or {}).get(
                character_name(sheet), "") if isinstance(sc, dict) else "",
            frame_id=frame_id)
        if not bound:
            raise RuntimeError("Charter promotion binding could not be saved")

    presences = wget(cid, "background_presences", {})
    # Every spelling of them, not just the one promotion was called with: a
    # leftover `The Dalek` after `A Dalek` is promoted would go on being
    # tracked as an unregistered passer-by while the same body now has a
    # character sheet, and could be selected to react against itself.
    identity = _presence_identity(name)
    # ...and every spelling of the same BODY: a record bound to the promoted
    # presence's entity id, or one whose former names (`aka`) include it, is
    # the same person under a name the rename left behind. A record PROVEN to
    # be a different body -- bound to another entity -- survives however
    # exactly its name collides: two people may share a name now, and
    # promoting one must not delete the other.
    doomed_keys = set()
    doomed_entities = set()
    doomed_identities = {identity} if identity else set()
    if presence_key is not None:
        doomed_keys.add(presence_key)
        doomed_keys.update(
            str(f) for f in (presence_record.get("former_uids") or []))
        if presence_record.get("entity_id"):
            doomed_entities.add(str(presence_record["entity_id"]))
    for tracked, record in presences.items():
        if not isinstance(record, dict):
            continue
        spellings = {_presence_identity(n)
                     for n in _presence_names(tracked, record)} - {""}
        if not (doomed_identities & spellings) and tracked not in doomed_keys:
            continue
        eid = str(record.get("entity_id") or "")
        if (tracked not in doomed_keys and eid and doomed_entities
                and eid not in doomed_entities):
            continue        # same name, different proven body: keep them
        if eid:
            doomed_entities.add(eid)
        doomed_identities.update(spellings)
        doomed_keys.add(tracked)
    for tracked in list(presences):
        record = presences[tracked] if isinstance(presences[tracked], dict) else {}
        eid = str(record.get("entity_id") or "")
        spellings = {_presence_identity(n)
                     for n in _presence_names(tracked, record)} - {""}
        if tracked in doomed_keys or (eid and eid in doomed_entities):
            presences.pop(tracked, None)
        elif doomed_identities & spellings:
            if eid and doomed_entities and eid not in doomed_entities:
                continue    # proven different body
            presences.pop(tracked, None)
    wset(cid, "background_presences", presences)

    return char_id


# The autonomous path demands more accrued voice than the UI's "promotable"
# badge (dialogue threshold 2): auto-minting a full character is irreversible
# spend, so it waits for one more beat of demonstrated salience.
AUTO_PROMOTE_DIALOGUE_THRESHOLD = 3


def _promote_after_addressed(cid):
    """Turns of deliberate interaction before a presence is promoted.

    Lives in `dialogue_config` rather than beside the other promotion
    thresholds because it is the one a host actually tunes, and because that
    blob already has a route, an editor and a place in PRESERVED_SETTING_KEYS
    -- a promotion rule that silently rolled back with a reroll would be worse
    than no rule. 0 disables promotion entirely.
    """
    from story.scene import dialogue_config

    try:
        raw = (dialogue_config(cid) or {}).get("promote_after_addressed")
        return max(0, min(99, int(raw)))
    except (TypeError, ValueError):
        return 0


def _auto_promote_enabled():
    """Off unless the host has explicitly switched it on.

    Promotion is not a small event: it mints a character sheet with an LLM
    call, attaches a permanent cast member, seeds mutual recognition with
    everyone present and starts writing that mind's psychology every beat.
    Defaulting that ON meant a story could acquire cast the host never asked
    for, from a passer-by who happened to talk twice.
    """
    value = str(get_setting("auto_promote") or "").strip().casefold()
    return value in ("1", "on", "true", "yes")


def auto_promote_background_characters(ctx):
    """Commit-side sweep: autonomously promote the single most-deserving
    tracked background presence that has crossed the auto-threshold --
    promotable (see promotable_background_presences) AND at least
    `promotion_thresholds(cid)["auto_dialogue"]` dialogue turns AND at least
    `dialogue_config`'s `promote_after_addressed` addressed turns AND
    present/addressed THIS beat. Promotion used to be UI-only (app.py's draft/confirm
    routes were promotable_background_presences' sole callers), so a
    deserving presence could stay shallow forever in hands-off play.

    At most one promotion per beat: each mints a sheet with an LLM call,
    and any remaining qualifiers stay tracked and promote on a later beat.
    Runs AFTER the turn's primary transaction (see _commit_all_locked) --
    it is additive and forward-only, so a failure is a warning, never a
    rollback. Gated by setting('auto_promote'), which is OFF unless the host
    turns it on -- see `_auto_promote_enabled`.
    """
    if not _auto_promote_enabled():
        return {"promoted": []}
    cid = ctx.chat.id
    turn_idx = ctx.turn.idx
    presences = wget(cid, "background_presences", {}) or {}
    if not presences:
        return {"promoted": []}

    promotable = {
        r["id"] for r in promotable_background_presences(cid) if r["promotable"]
    }
    # How many turns of DELIBERATE interaction earn a sheet. Zero means never,
    # which is what the dialogue menu's own control offers as its low end -- a
    # host who wants extras to stay extras should not have to remember to watch
    # them.
    _addressed_min = _promote_after_addressed(cid)
    if _addressed_min <= 0:
        return {"promoted": []}
    # ...and how much VOICE she must have accrued. The other half of the gate,
    # and independently settable, because the two measure different things: a
    # prop can be talked at for six turns and answer twice.
    _dialogue_min = promotion_thresholds(cid)["auto_dialogue"]
    selected = {
        str(n).casefold()
        for n in ((ctx.get("background_react") or {}).get("selected") or [])
    }
    addressed_refs = _flow_addressed_refs(ctx)

    candidates = []
    # The promotable set carries migrated (uid) keys; read the raw ledger
    # through the same fold so a legacy bank's keys agree with it.
    presences = _fold_duplicate_presences(
        dict(presences), wget(cid, "scene", {}) or {})
    for key, record in presences.items():
        if key not in promotable:
            continue
        name = presence_display_name(key, record)
        dialogue_turns = record.get("dialogue_turns") or []
        # The gate that matters: turns the player or a real character
        # deliberately turned toward this person. Counting the turns they
        # merely SPOKE promoted extras for holding conversations with each
        # other, which is what background life is FOR.
        if len(record.get("addressed_turns") or []) < _addressed_min:
            continue
        # And the voice gate, which the UI's `promotable` badge sets lower --
        # auto-minting a sheet is irreversible spend, so the autonomous path
        # waits for more demonstrated salience than the offer does. It also
        # closes the mentions-only route: `promotable` is satisfied by
        # `mention_turns` ALONE, so without this a presence who has never once
        # spoken could be handed a mind.
        if len(dialogue_turns) < _dialogue_min:
            continue
        # "Present/addressed this beat": their record was touched this turn
        # (spoke / mentioned), the gate picked them, a character's address
        # left them an owed reply this turn, or the director's flow named
        # them as the player's addressee.
        active = (
            record.get("last_turn") == turn_idx
            or name.casefold() in selected
            or (record.get("pending_reply") or {}).get("turn") == turn_idx
            or _presence_in_addressed_refs(name, addressed_refs)
        )
        if not active:
            continue
        candidates.append(
            (len(dialogue_turns), record.get("last_turn") or -1, key, name))

    if not candidates:
        return {"promoted": []}
    candidates.sort(reverse=True)
    key, name = candidates[0][-2], candidates[0][-1]
    # Promote by the record's own id: a display name two records share
    # would refuse to resolve, and the id never does.
    char_id = promote_background_character(
        cid, key, frame_id=ctx.turn.frame_id,
        promoted_turn=ctx.turn.idx)
    return {"promoted": [{"id": key, "name": name, "char_id": char_id}]}
