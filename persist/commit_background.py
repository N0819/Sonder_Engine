"""Unregistered background presences: identity folding, per-beat tracking,
the deterministic reactor gate, and promotion to cast.

Extracted verbatim from commit.py, which re-exports every name here. The
deferred function-body imports (scene, schemas, importers,
background_claims) are the existing cycle-breakers and stay deferred.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import json, re, time
from core.db import q, qi, wget, wset, get_setting
from mind.memory import add_memories_batch
from story.character_schema import (character_name, character_initial_outfit,
                              normalize_character_data, persona_name)
from story.scene import seed_initial_attire
from world.spatial import room_of, spatial_rel, hear_level, _is_body_entity
from persist.commit_common import (_known_name_roster, _player_name_or_none,
                           _registered_name_roster, _room_of)


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


def _presence_scene_entity(scene, name):
    """The scene entity a presence name denotes -- by entity id or display
    name -- as (entity_id, entity_def), or (None, None) when the name has no
    entity record at all (a presence tracked from a dialogue speaker or a
    bare positions key)."""
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

    eid, ent = _presence_scene_entity(scene, name)
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
    for field in ("dialogue_turns", "mention_turns", "addressed_turns"):
        merged = set(target.get(field) or []) | set(other.get(field) or [])
        if merged:
            target[field] = sorted(merged)
    target["first_turn"] = min(target.get("first_turn", 0),
                               other.get("first_turn", 0))
    target["last_turn"] = max(target.get("last_turn", 0),
                              other.get("last_turn", 0))
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


def _resolve_presence_name(name, presences, scene=None):
    """The key `name` should be filed under, given what is already tracked.

    First-seen spelling wins, so an established presence keeps the name every
    other record already refers to it by rather than being renamed by whichever
    determiner the model reached for this beat.
    """
    name = _canonical_presence_name(name, scene)
    identity = _presence_identity(name)
    if not identity:
        return name
    if _bodies_answering_to(identity, scene) > 1:
        return name          # more than one such body; the article may be doing work
    for existing in presences:
        if _presence_identity(existing) == identity:
            return existing
    return name


def _fold_duplicate_presences(presences, scene=None):
    """Merge presences that were split -- by an article, or by being tracked
    under both an entity id and its display name -- before they were resolved
    on write. Runs on load, so a story already carrying the split heals on its
    next turn instead of needing a migration.

    The id fold runs first and is unconditional: an entity id denotes exactly
    one entity, so unlike the article fold there is no crowd ambiguity to
    respect, and the display name always wins the key -- the id was never a
    name (chat 80: "cfc004eb2c174286" tracked beside "Scranton Reality
    Anchors", "ab1299cb69244904" beside "Guard 1", "eef58c8d667f414f" beside
    "Guard 2" -- every presence doubled, each twin with half the history).

    For the article fold, the earliest first_turn wins the name -- that is
    the spelling the rest of the story has been using.
    """
    for key in list(presences):
        canon = _canonical_presence_name(key, scene)
        if canon == key:
            continue
        other = presences.pop(key)
        if canon in presences:
            _merge_presence_record(presences[canon], other)
        else:
            presences[canon] = other
    by_identity = {}
    for name in list(presences):
        by_identity.setdefault(_presence_identity(name), []).append(name)
    for identity, names in by_identity.items():
        if len(names) < 2:
            continue
        if _bodies_answering_to(identity, scene) > 1:
            continue         # genuinely a crowd; see _bodies_answering_to
        names.sort(key=lambda n: (presences[n].get("first_turn", 0), n))
        keeper, rest = names[0], names[1:]
        target = presences[keeper]
        for other_name in rest:
            _merge_presence_record(target, presences.pop(other_name))
    return presences


def _background_name_mentioned(name, text):
    """resolved_event prose almost never repeats someone's full tracked
    name after their first introduction -- "Crusher" carries a scene once
    "Dr. Crusher" has been established -- so a plain substring check
    against the full name would undercount real mentions. Fall back to
    any significant word of the name (title words and short filler
    stripped) appearing at a word boundary."""
    text_cf = text.casefold()
    name_cf = name.casefold()
    if re.search(rf"\b{re.escape(name_cf)}\b", text_cf):
        return True
    words = [w.strip(".,;:").casefold() for w in name.split()]
    significant = [
        w for w in words
        if w and w not in _BACKGROUND_NAME_TITLE_WORDS and len(w) >= 3
    ]
    return any(
        re.search(rf"\b{re.escape(w)}\b", text_cf) for w in significant
    )

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
        if not target or not _background_name_mentioned(presence_name, target):
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

    for d in (res.get("dialogue_log") or []):
        speaker = str(d.get("speaker") or "").strip()
        speaker = entity_id_to_name.get(speaker, speaker)
        if speaker.casefold() in _ubiquitous:
            continue
        if speaker and not name_in_roster(speaker, roster):
            candidates.add(speaker)
            dialogue_speakers.add(speaker.casefold())

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
            sk = sketches.setdefault(name, {})
            desc = str(entity_def.get("description") or "").strip()
            if desc:
                sk["role_hint"] = desc[:160]
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
        br_name = str((_r.get("dialogue_log_entry") or {}).get("speaker") or "").strip()
        br_name = entity_id_to_name.get(br_name, br_name)
        if br_name and not name_in_roster(br_name, roster):
            candidates.add(br_name)
            dialogue_speakers.add(br_name.casefold())

    live_scene = wget(cid, "scene", {}) or {}
    presences = _fold_duplicate_presences(
        wget(cid, "background_presences", {}), live_scene)
    for name in candidates:
        # `A Dalek`, `Dalek` and `The Dalek` are one creature WHEN THE ROOM
        # HOLDS ONE DALEK -- the scene decides that, not the string. Resolve to
        # the name already tracked before creating anything, or the ledger
        # grows a fresh presence every time the prose changes its determiner.
        key = _resolve_presence_name(name, presences, live_scene)
        record = presences.setdefault(key, {
            "first_turn": turn_idx, "last_turn": turn_idx,
            "dialogue_turns": [], "mention_turns": [],
        })
        record["last_turn"] = turn_idx
        if name.casefold() in dialogue_speakers:
            if turn_idx not in record["dialogue_turns"]:
                record["dialogue_turns"].append(turn_idx)
        sk = sketches.get(name)
        if sk:
            # Director restated this presence's own description/position ->
            # objective self-knowledge wins; overwrite the prior sketch.
            record.setdefault("sketch", {}).update(sk)

    # Scene-manager bookkeeping (docs/design/BACKGROUND_LIFE_DESIGN.md §3.8, §3.11).
    _persist_blurbs(br, presences)
    _append_manager_conduct(br, presences, turn_idx)

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
    for name, record in presences.items():
        if name in candidates:
            continue
        if _background_name_mentioned(name, resolved_event):
            record["last_turn"] = turn_idx
            if turn_idx not in record["mention_turns"]:
                record["mention_turns"].append(turn_idx)

    # Owed-reply bookkeeping: a registered character (or the player) addressed
    # this presence this beat, but the single-winner gate spent the beat on
    # someone else -- persist a one-beat-grace debt so they can answer next
    # turn (the "if not during the turn, next turn" case). Discharged when the
    # presence is picked (answered, or its silence WAS the answer) and swept
    # when stale, so a reply never surfaces turns later.
    selected_names = {str(n).casefold() for n in ((ctx.get("background_react") or {}).get("selected") or [])}
    if not selected_names:  # legacy single-entry shape
        _sel = str((ctx.get("background_react") or {}).get("name") or "").strip().casefold()
        if _sel:
            selected_names = {_sel}
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
    addressed_refs = _flow_addressed_refs(ctx)
    player_input = str(getattr(ctx.turn, "player_input", "") or "")
    sc = wget(cid, "scene", {}) or {}
    for name, record in presences.items():
        addressed = (_presence_in_addressed_refs(name, addressed_refs)
                     or _background_name_mentioned(name, player_input))
        pr = record.get("pending_reply")
        if isinstance(pr, dict) and turn_idx > (pr.get("expires_turn")
                                                if pr.get("expires_turn") is not None else -1):
            record.pop("pending_reply", None)
        if name.casefold() in selected_names:
            record.pop("pending_reply", None)  # the moment was theirs; discharged
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
        if addressed:
            turns = record.setdefault("addressed_turns", [])
            if turn_idx not in turns:
                turns.append(turn_idx)
                record["last_turn"] = turn_idx

    wset(cid, "background_presences", presences)
    return {"tracked": len(presences)}

BACKGROUND_RECENT_TAIL = 4

def _persist_blurbs(br, presences):
    """Write minted blurbs (§3.8). FROZEN: a blurb is written once and never
    rewritten -- immutability is the feature, and it is the anchor against the
    self-feeding drift §3.11 describes."""
    for name, blurb in ((br or {}).get("blurbs") or {}).items():
        rec = presences.get(name)
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
        rec = presences.get(name)
        if rec is None:
            continue
        entry = r.get("dialogue_log_entry") or {}
        parts = []
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

def _flow_addressed_refs(ctx):
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


def _presence_in_addressed_refs(name, refs):
    return any(
        name.casefold() == ref.casefold()
        or _background_name_mentioned(name, ref)
        for ref in refs
    )


def _at_post_within_earshot(sc, station_room, player_room):
    """Is a presence standing where they work, close enough to answer?

    AT POST USED TO MEAN `station_room == player_room`, and that one `==` is
    the whole of what the owner called a hole in the architecture: "they
    should be able to respond from adjacent rooms".

    Perception already models this properly -- `hear_level` is barrier- and
    material-aware, an open doorway carries a voice and a shut one does not,
    and `agents/background._beat_for_presence` runs exactly that check before
    handing a presence a single word of the beat. So the engine granted the
    clerk in the back office the hearing and withheld the agency: he could
    hear the bell and could never be chosen to answer it.

    The models kept trying to route around it, which is how it was found.
    Chat 72 turn 45: the Director walked a night clerk INTO the lobby so he
    could speak. Turn 47: the spatial specialist put another at the doorway
    "near" the guests, and that teleported the player into the back office.
    Both are a mind reaching for a thing the engine had no representation of.

    AUDIBILITY IS THE TEST, NOT ADJACENCY, and the bar is a line heard in
    FULL. That bar is the engine's own, already set: `_character_address_of`
    requires `full` to count a line as addressed to somebody, and
    `_beat_for_presence` was fixed to match it after a half-heard line let a
    presence quote back verbatim what it had only caught a fragment of --
    two paths reading the same level differently IS the bug there.
    Consistency matters more here than physics, and it lands the right way
    round anyway: at-post is the WEAKEST claim any presence has on a beat
    (the standing invitation of working where you stand), so a muffled
    thump through a shut door must not summon a body. Where the beat
    genuinely warrants one, the stronger signals -- named in the prose,
    addressed by the player, owed a reply -- fire regardless of the room.

    Same room still qualifies trivially, and an unknown station qualifies
    for nothing: not knowing where somebody stands is a reason to deliver
    nothing, which is the rule the perception side already follows.
    """
    player_room = str(player_room or "")
    if not station_room or not player_room:
        return False
    if str(station_room) == player_room:
        return True
    try:
        return hear_level(
            spatial_rel(sc, str(station_room), player_room), "normal"
        ) == "full"
    except Exception:
        # Fail CLOSED. Everywhere else in this engine an unreadable fact
        # grants the block; here granting means putting words in a mouth
        # that may have no channel to the beat, so silence is the safe
        # direction and the presence simply waits for a clearer signal.
        return False


def pick_background_reactor(ctx, dr_output):
    """Single-winner convenience wrapper over pick_background_reactors: the
    top-ranked qualifying background presence, or None. Preserves the original
    gate contract for the common (max_reactors == 1) case and all callers/tests
    that expect one name.
    """
    picks = pick_background_reactors(ctx, dr_output, cap=1)
    return picks[0] if picks else None


def pick_background_reactors(ctx, dr_output, cap=1):
    """Deterministic gate for the background_react stage: pick up to `cap`
    named, unregistered background presences to give an independent
    reaction this beat, when this beat has salience for them but the
    director's own resolved_event/dialogue_log authorship (see prompts.py's
    DIALOGUE LOG background-entity license) gave them nothing anyway. Each
    returned presence qualifies INDEPENDENTLY (addressed / character-addressed
    / owed / mentioned / has history) -- the list is never padded to `cap`.

    This mirrors infer_vehicle_zones' role in spatial_frames.py: a prompt
    clause exists and is sometimes followed, but live play showed it fails
    reliably enough under sustained narrative pressure (a background
    presence given direct orders, addressed by name, present at a caught
    theft and an alarm, still rendered as "motionless" for 25+ turns) that
    a deterministic backstop is needed rather than further prompt tuning
    alone -- the same lesson this codebase has already learned for zone
    tagging and speech concealment.

    Returns [] when no candidate qualifies (the common case -- most turns
    have no salient, un-voiced background presence at all). cap defaults to 1,
    reproducing the historical single-winner behavior exactly -- with one
    exception: a presence the director's flow.addressed_to named (a direct
    player address, see _flow_addressed_refs) is FORCED into the picks,
    bypassing `cap` if necessary, so a directly-addressed background NPC
    always gets to answer with its own line instead of being displaced by a
    merely-standing presence or a foreground character's interception.
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

    resolved_event = str(dr_output.get("resolved_event") or "")
    player_input = str(ctx.get("input") or "")
    turn_idx = ctx.turn.idx
    sc = wget(cid, "scene", {}) or {}
    # Read through the duplicate fold: the ledger is healed at commit, but
    # this gate runs BEFORE commit, so a story already carrying an id-keyed
    # twin (chat 80) must not be able to dispatch the twin one last time.
    presences = _fold_duplicate_presences(
        wget(cid, "background_presences", {}) or {}, sc)

    addressed_refs = _flow_addressed_refs(ctx)

    # Where the player is standing, for the at-post test below.
    _pname = _player_name_or_none(ctx)
    player_room = room_of(sc, _pname) if _pname else ""
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
        if name.casefold() not in {n.casefold() for n in ranked}:
            ranked[name] = {}

    candidates = []
    forced = 0
    for name, record in ranked.items():
        cf = name.casefold()
        if cf in roster or cf in voiced_this_beat:
            continue
        # The director's own flow plan named this presence as the player's
        # addressee -- the strongest possible salience signal, and one the
        # raw-text checks below can miss entirely (an address by role or
        # epithet never mentions the tracked name).
        flow_addressed = _presence_in_addressed_refs(name, addressed_refs)
        # The Director wrote a line for this presence and the engine removed
        # it so this stage could do the job properly. Salience is not in
        # question -- the Director already judged them worth speaking for --
        # so this qualifies and forces exactly like a flow address. Without
        # it the salience tests below could reject a presence whose line was
        # just deleted, turning clunky dialogue into silence.
        routed = name in forced_routed
        addressed = _background_name_mentioned(name, player_input)
        # A registered character (or the player) who spoke directly TO this
        # presence this beat -- read-only here; the owed-reply debt is written
        # at commit (track_background_presences), never in this pre-commit gate.
        station_room = (record.get("sketch") or {}).get("station_room")
        char_addr = _character_address_of(dr_output, name, roster, sc, station_room)
        owed = _valid_pending_reply(record, turn_idx)
        mentioned = _background_name_mentioned(name, resolved_event)
        dialogue_turns = record.get("dialogue_turns") or []
        # AT THEIR POST. The rule that separates a FIXTURE from an emergence:
        # a fixture may be re-met, an emergence may not. A presence whose
        # station room is the room the player is standing in is at their post
        # -- the barkeep behind the bar, the vendor at the stall -- and a
        # tavern whose barkeep is only offered when the Director happens to
        # mention him is a tavern with nobody behind the bar on every quiet
        # visit. Measured: 8 of 52 live presences carry a station_room, and
        # nothing re-offered any of them on return.
        #
        # Ranked LAST of the qualifying signals on purpose. Standing where you
        # work is the weakest possible claim on a beat -- far weaker than being
        # addressed -- and `cap` still bounds how many are picked, so a busy
        # room does not become a chorus.
        at_post = bool(station_room) and _at_post_within_earshot(
            sc, station_room, player_room)
        if not (flow_addressed or routed or addressed or char_addr or owed
                or mentioned or dialogue_turns or at_post):
            continue
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
        if flow_addressed or routed:
            forced += 1
        priority = (bool(flow_addressed or routed), bool(addressed),
                    bool(char_addr),
                    bool(owed), bool(mentioned), len(dialogue_turns),
                    record.get("last_turn") or -1)
        candidates.append((priority, name))

    if not candidates:
        return []
    candidates.sort(reverse=True)
    # Every flow-addressed presence sorts first (top priority bit) and must
    # answer THIS beat: widen the cap to fit them all, then fill any slots
    # left up to `cap` with the normally-ranked candidates.
    slots = max(forced, max(0, int(cap)))
    return [name for _, name in candidates[:slots]]

def promotable_background_presences(chat_id):
    sc = wget(chat_id, "scene", {}) or {}
    presences = _fold_duplicate_presences(
        wget(chat_id, "background_presences", {}) or {}, sc)
    limits = promotion_thresholds(chat_id)
    out = []
    for name, record in presences.items():
        promotable = (
            len(record.get("dialogue_turns") or []) >= limits["dialogue"]
            or len(record.get("mention_turns") or []) >= limits["mention"]
        )
        # Promotion mints a MIND, and a thing cannot hold one -- however much
        # history its record accrued before the speech gate existed (chat
        # 75's utility sash spoke on three turns; chat 80's PA-class fixtures
        # are one dialogue line away from the same flag). "undecided" stays
        # promotable on purpose: a "dalek war machine" the player keeps
        # engaging deserves the offer, and the auto-promotion sweep already
        # demands deliberate addressed_turns on top of this flag.
        if promotable and _presence_speech_verdict(sc, name, record) == "thing":
            promotable = False
        out.append({
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


def promote_background_character(cid, name, sheet=None, memory_seeds=None):
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

    if sheet is None:
        draft = draft_promoted_character(cid, name)
        sheet = draft["sheet"]
        if memory_seeds is None:
            memory_seeds = draft["memory_seeds"]

    sheet = normalize_character_data(sheet)
    memory_seeds = [str(m) for m in (memory_seeds or []) if str(m).strip()]
    _refuse_name_collision(cid, character_name(sheet))

    char_id = qi(
        "INSERT INTO characters(name,sheet,source,created) VALUES(?,?,?,?)",
        (
            character_name(sheet), json.dumps(sheet, ensure_ascii=False),
            json.dumps({"format": "promoted", "chat_id": cid}, ensure_ascii=False),
            time.time(),
        ),
    )
    qi(
        "INSERT INTO chat_chars(chat_id,char_id,status) VALUES(?,?,'active')",
        (cid, char_id),
    )

    chat_row = dict(q("SELECT * FROM chats WHERE id=?", (cid,), one=True))
    sc = wget(cid, "scene", None)
    if isinstance(sc, dict):
        positions = sc.setdefault("positions", {})
        if character_name(sheet) not in positions:
            player_name = persona_name(persona_of(chat_row))
            positions[character_name(sheet)] = positions.get(player_name)
        seed_initial_attire(
            sc, character_name(sheet), character_initial_outfit(sheet))
        wset(cid, "scene", sc)

    # Seed mutual recognition with the player and with every other
    # already-registered cast member -- she's been part of the scene the
    # whole time, so treating her as a stranger to everyone else present
    # would be as wrong as it was to treat her as a stranger to the player.
    cast_rows = q(
        "SELECT COALESCE(cc.sheet,ch.sheet) AS sheet "
        "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
        "WHERE cc.chat_id=? AND cc.status='active' AND ch.id!=?",
        (cid, char_id),
    )
    roster = _known_name_roster(chat_row, cast_rows)
    known = wget(cid, "known", {})
    her_name = character_name(sheet)
    known.setdefault(her_name, [])
    for other in roster:
        if other not in known[her_name]:
            known[her_name].append(other)
        known.setdefault(other, [])
        if her_name not in known[other]:
            known[other].append(her_name)
    wset(cid, "known", known)

    if memory_seeds:
        add_memories_batch([
            {
                "chat_id": cid, "char_id": char_id, "turn_id": None,
                "kind": "episode", "provenance": "witnessed", "salience": 0.6,
                "content": seed, "turn_idx": None,
                "event_key": f"promotion:{cid}:{char_id}:{i}",
            }
            for i, seed in enumerate(memory_seeds)
        ])

    presences = wget(cid, "background_presences", {})
    # Every spelling of them, not just the one promotion was called with: a
    # leftover `The Dalek` after `A Dalek` is promoted would go on being
    # tracked as an unregistered passer-by while the same body now has a
    # character sheet, and could be selected to react against itself.
    identity = _presence_identity(name)
    for tracked in [n for n in presences if _presence_identity(n) == identity]:
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
    AUTO_PROMOTE_DIALOGUE_THRESHOLD dialogue turns AND present/addressed
    THIS beat. Promotion used to be UI-only (app.py's draft/confirm
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
        r["name"] for r in promotable_background_presences(cid) if r["promotable"]
    }
    # How many turns of DELIBERATE interaction earn a sheet. Zero means never,
    # which is what the dialogue menu's own control offers as its low end -- a
    # host who wants extras to stay extras should not have to remember to watch
    # them.
    _addressed_min = _promote_after_addressed(cid)
    if _addressed_min <= 0:
        return {"promoted": []}
    selected = {
        str(n).casefold()
        for n in ((ctx.get("background_react") or {}).get("selected") or [])
    }
    addressed_refs = _flow_addressed_refs(ctx)

    candidates = []
    for name, record in presences.items():
        if name not in promotable:
            continue
        dialogue_turns = record.get("dialogue_turns") or []
        # The gate that matters: turns the player or a real character
        # deliberately turned toward this person. Counting the turns they
        # merely SPOKE promoted extras for holding conversations with each
        # other, which is what background life is FOR.
        if len(record.get("addressed_turns") or []) < _addressed_min:
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
            (len(dialogue_turns), record.get("last_turn") or -1, name))

    if not candidates:
        return {"promoted": []}
    candidates.sort(reverse=True)
    name = candidates[0][-1]
    char_id = promote_background_character(cid, name)
    return {"promoted": [{"name": name, "char_id": char_id}]}
