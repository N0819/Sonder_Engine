"""The registered cast inside the scene: identity keys, rooms, the cast
spelling policy, entity reconciliation and stamping, position
canonicalisation, and the exclusion-list reading by observer handles.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from story.character_schema import (
    character_body_interior,
    character_name,
    fold_identity_key,
    normalize_character_data,
    normalized_character_from_text,
    normalized_character_of_row,
)
from core.pipeline_context import note_step_warning
from world.spatial import normalize_room_id, room_of

def _conceal_from_targets_observer(conceal_from, observer_id, observer_sheet):
    """True if any conceal_from entry names this observer -- matched by
    numeric id, string id, display name, uid, or alias. conceal_from is an
    absolute exclusion list authored against whatever identity handle the
    speaker knew, so a reader must resolve it against ALL of the observer's
    handles (same tolerance character_room/canonicalize_positions apply).

    FAILS CLOSED. When the handles cannot be enumerated at all, every name,
    uid and alias form is gone and only the numeric-id form is left, so a
    name-authored exclusion matches nothing and this used to answer "not
    excluded" -- delivering the concealed line to the one mind it named. An
    exclusion the engine cannot resolve is not an exclusion that does not
    apply: unresolved, this guard cannot show the observer is NOT the
    excluded party, and withholding one line costs a delivery while
    delivering it costs the firewall. Reported rather than swallowed,
    because a subtraction nothing announces is the next invisible defect.

    The ENGINE'S OWN HANDLE, `character:<id>`, is one of the observer's
    handles too: the composer's twin of this test (`composer.
    concealed_from_observer`) has always read it, and this one did not, so
    an exclusion written only in it named nobody here. Measured on the
    scratch play db (chats 150-166): 39 resolve-stage entries were handles
    and no list held handles alone -- the floor held because the model also
    wrote names, which is the dependence it must not have."""
    if not conceal_from:
        return False
    id_forms = {str(observer_id).strip().casefold(),
                f"character:{str(observer_id).strip()}".casefold()}
    try:
        keys = {k.casefold() for k in character_scene_keys(observer_sheet)}
    except Exception as exc:
        note_step_warning(
            f"conceal_from could not be resolved against observer "
            f"{observer_id!r} ({type(exc).__name__}: {exc}); treating the "
            f"line as concealed from them.")
        return True
    for entry in conceal_from:
        if isinstance(entry, bool):
            continue
        if isinstance(entry, int):
            if str(entry) in id_forms:
                return True
            continue
        text = str(entry or "").strip()
        if not text:
            continue
        if text.casefold() in id_forms or text.casefold() in keys:
            return True
    return False

def normalize_character_refs(values, cast):
    """The cast ids a list of references names, in order, each once.

    A reference is a cast id (int or digit string), a sheet name, or THE
    ENGINE'S OWN IDENTITY HANDLE, `character:<id>` -- one of the two forms a
    prose-contract row carries a cast target in (most name the body; 10
    targets on the scratch play db's 90 prose-contract beats are handles).
    This read ids and names only, so a target in the engine's own spelling
    resolved to nobody: on the Brackwater beat (chat 166, turn idx 30) the
    player's act "steps aside so that brother and sister face each other"
    carried `targets: ["character:81", "character:83"]`, and the
    interaction loop's acted-upon ranking, which reads targets through
    here, found neither."""
    valid_ids = {int(row["id"]) for row in cast}
    names = {}
    for row in cast:
        sheet = normalized_character_of_row(row)
        name = character_name(sheet) if sheet is not None else ""
        if name:
            names[name.casefold()] = int(row["id"])
    result = []
    for value in values or []:
        resolved = None
        if isinstance(value, int) and value in valid_ids:
            resolved = value
        elif isinstance(value, str):
            text = value.strip()
            handle = (text[10:] if text[:10].casefold() == "character:"
                      else "")
            if text.isdigit() and int(text) in valid_ids:
                resolved = int(text)
            elif handle.isdigit() and int(handle) in valid_ids:
                resolved = int(handle)
            else:
                resolved = names.get(text.casefold())
        if resolved is not None and resolved not in result:
            result.append(resolved)
    return result

def character_scene_keys(sheet):
    """Every key a scene might legitimately use to store this character's
    entity/position. The intended convention keys positions by the display
    NAME, but the director sometimes keys by identity.uid (or an alias) -- so
    readers must try all of them. Name first (the intended key), then uid,
    then aliases; de-duplicated case-insensitively, display form preserved."""
    ident = normalize_character_data(sheet).get("identity", {})
    candidates = [ident.get("name"), ident.get("uid")]
    candidates.extend(ident.get("aliases") or [])
    seen, keys = set(), []
    for cand in candidates:
        text = str(cand or "").strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            keys.append(text)
    return keys

def character_room(sc, sheet):
    """Resolve a cast character's room from the scene, tolerating scenes that
    key the entity by identity.uid or an alias rather than the display name.
    Perception was previously blind to a character whose position was stored
    under its uid (e.g. `tenth_doctor` for "The Doctor"), placing them in "an
    unspecified area" and leaking a false empty view.

    TWO PASSES, and the order is the point. `room_of` now resolves a spelling
    through the scene's entity table as well, which is what a reader holding
    only a name needs -- but this reader holds a SHEET, and a sheet is the
    better authority: it enumerates every key this character answers to, where
    the entity table may hold a stray row claiming the same display name. So
    every one of the sheet's own keys is tried against the literal ledger
    first, and identity resolution only answers for keys that found nothing.
    """
    keys = character_scene_keys(sheet)
    for key in keys:
        room = room_of(sc, key, identity=False)
        if room:
            return room
    for key in keys:
        room = room_of(sc, key)
        if room:
            return room
    return None


def _present_cast_bodies(scene, cast):
    """Every cast member the SCENE places somewhere -- [{id, name, room}].

    Presence is a fact about the world, not a judgement about the beat, and
    four readers need the same answer. Two are in `perception_act`: who is
    standing here (for `_co_present_company`) and who therefore perceives
    what happens (the perceiver list). Two more NARROW the Director's pacing
    list to it -- `runtime.build_plan` and `loops._drop_absent` -- because a
    mind the scene places nowhere gets no view, and asking it to declare
    conduct is asking a person to act from a place they are not standing in.
    It lived in `perception.py` while only that stage read it; it is here now
    for the same reason `_drop_non_awake`'s inputs are.

    Measured, chat 95 (2026-08-28): `scene.positions` held no entry for two
    of the four registered cast all run, while `flow.reactors` named them on
    turns 4, 5, 8 and 14 -- 6 `character_major` calls at 13-22s each,
    deliberating from an empty perception base, in beats whose own
    `perception_act.views` listed observers `['75']` / `['74','75']`.

    The SHEET, not `sheet_state`. Presence asks what keys this body answers
    to and where the scene puts them; the mutable per-chat state -- mood,
    goal, stance -- says nothing about it, and reading the row through
    `sheet_state` made this refuse any cast row without a ``cstate`` column.
    That is not a hypothetical: `_drop_non_awake` beside it already reads
    ``c["sheet"]`` directly for exactly this reason, and four suites build
    reactor rows of `{id, sheet}` alone.
    """
    out = []
    for c in cast or []:
        # One normalization for the two reads below, keyed on the row's sheet
        # TEXT so the four readers a beat share it (C14). A row carrying an
        # already-parsed dict still normalizes here, once.
        sh = c["sheet"]
        sh = (normalized_character_from_text(sh) if isinstance(sh, str)
              else normalize_character_data(sh))
        name = character_name(sh)
        room = character_room(scene, sh)
        if name and room:
            out.append({"id": c["id"], "name": name, "room": room})
    return out


def cast_room(sc, name, cast):
    """Room of a named speaker/actor, mapping the bare name through the cast so
    a character stored under its uid/alias still resolves (the name-string
    counterpart to character_room).

    Same ordering as `character_room` and for the same reason: the literal
    ledger, then the cast, then identity -- a registered character outranks an
    entity row wearing their name."""
    room = room_of(sc, name, identity=False)
    if room:
        return room
    target = str(name or "").strip().lower()
    if not target:
        return None
    for row in cast or []:
        # `character_scene_keys` and `character_room` each normalize; one
        # memoised normalization now serves both (C14).
        sheet = normalized_character_of_row(row)
        if sheet is None:
            continue
        if target in {key.lower() for key in character_scene_keys(sheet)}:
            return character_room(sc, sheet)
    return entity_room_by_name(sc, target) or room_of(sc, name)


def entity_room_by_name(sc, name):
    """Room of an UNREGISTERED scene presence, resolved from its NAME.

    `canonicalize_positions` rewrites only keys that identify a cast character
    or the player, and says so: "unregistered background presences are left
    untouched". Correct -- they are not cast -- but nothing mapped the name
    back the other way, so a presence placed under its entity uid was
    unreachable by name from the moment it was placed. Every reader that asks
    where a background speaker is got None, and `spatial_rel(None, room)`
    answers "remote, no known spatial channel".

    Measured live (chat 58, t23): a Dalek standing in the player's own alley
    with its gun-stick trained on her chest sat in `positions` under
    `40af0ac4bf2644a1`. `cast_room(sc, "A Dalek", cast)` returned None, so
    perception's hearing gate classified it as remote and dropped its line for
    every observer, and the view rendered it as "something" and "the source"
    rather than the machine she had just thrown a rock at. Corpus-wide, 47 of
    78 background lines never reached a single view.

    Name before aliases, so an alias can never outrank a real name. A name
    matching more than one entity resolves to NOBODY: two Daleks in a room are
    exactly the case this must not guess between, and a wrong room is worse
    than the None every one of them used to get.
    """
    target = str(name or "").strip().lower()
    entities = (sc or {}).get("entities")
    if not target or not isinstance(entities, dict):
        return None
    positions = (sc or {}).get("positions")
    positions = positions if isinstance(positions, dict) else {}
    pos_ci = {str(k).strip().lower(): v for k, v in positions.items()}

    def _match(by_alias):
        hits = []
        for eid, ent in entities.items():
            if not isinstance(ent, dict):
                continue
            if by_alias:
                forms = {str(a).strip().lower() for a in (ent.get("aliases") or [])}
            else:
                forms = {str(ent.get("name") or "").strip().lower()}
            if target in forms - {""}:
                hits.append(eid)
        return hits[0] if len(hits) == 1 else None

    eid = _match(False) or _match(True)
    if not eid:
        return None
    # The uid is the position key in practice; an entity may also carry its own
    # `room`, which is authoritative only when no position exists for it.
    room = pos_ci.get(str(eid).strip().lower())
    if room is None:
        room = pos_ci.get(target)
    if room is None:
        ent = entities.get(eid) or {}
        room = ent.get("room")
    return room or None

def cast_spelling_policy(cast, player_name=None, *, aliases=True):
    """Which spelling each registered cast body answers to, and what it is.

    ONE POLICY, because the two hand-rolled copies of it disagreed and the
    disagreement is a live defect. `canonicalize_positions` matched a sheet
    name and uid and deliberately refused aliases; `_heal_attire_identity_keys`
    matched aliases too. So in chat 82 ("Sarah Moon -- Hinami attempt 2") the
    same body came out spelled two ways at once: `attire` folded
    "Dr. Sarah Moon" onto the sheet's "Sarah Moon" and `positions` did not,
    leaving one woman keyed two ways across the ledgers that describe her.

    `aliases` is the one setting, and the two callers genuinely differ on it.
    Attire is keyed by BODIES only, so an alias there can name nothing else
    and matching it heals a real split. `positions` keys objects, fixtures and
    unregistered presences beside people, where a generic alias ("The Oncoming
    Storm") could collide with a separate entity and move an object into a
    person -- so that caller passes `aliases=False`. The difference used to be
    two hand-rolled tables that disagreed by accident; it is now one table with
    the disagreement written down.

    Returns (canonical, forms) --
      `canonical(spelling)`: the sheet name this spelling belongs to, or the
        spelling unchanged when it belongs to nobody registered. Objects,
        fixtures and unregistered background presences are never touched:
        they are not cast, and rewriting them is what broke carried lights
        and destruction cascades the first time somebody folded on identity
        alone.
      `forms`: {casefolded spelling -> sheet name} for callers that need the
        table rather than the function.

    THE AUTHORITY IS THE SHEET, per `DESIGN_SUBJECT_SPELLING_AUTHORITY.md`.
    A sheet is authored, durable, and locked against rekeying; a scene entity
    record is minted by a model on turn 0 and is provisional until commit
    validates it. Letting a model's incidental honorific become a being's
    canonical name inverts the source-of-truth order.

    Two guards, both paid for:

    - A NAME OUTRANKS SOMEBODY ELSE'S ALIAS FOR IT. One character's alias is
      another's name often enough in fiction -- a nickname, a family name, a
      title. Measured: with a character named Yuki and a second whose aliases
      include "Yuki", folding on the alias collapsed Yuki's wardrobe onto the
      other woman, who was wearing nothing and acquired a yukata; Yuki's own
      record disappeared.
    - AMBIGUITY RESOLVES TO NOTHING. A spelling two cast members answer to is
      registered for neither. Folding two beings into one is strictly worse
      than leaving two spellings of one.
    """
    own_names, claims = set(), {}
    rows = []
    for row in cast or []:
        # Measured at seven-plus calls a turn, each normalizing every cast
        # sheet twice (identity, then `character_name`); the memo makes it one
        # per distinct card text for the whole process (C14).
        sheet = normalized_character_of_row(row)
        if sheet is None:
            continue
        ident = normalize_character_data(sheet).get("identity", {})
        name = str(ident.get("name") or character_name(sheet) or "").strip()
        if not name:
            continue
        try:
            rid = row["id"]
        except Exception:
            rid = None
        # The uid is an IDENTIFIER, not a name somebody else could also go by,
        # so it rides regardless of `aliases` -- reading it out of identity
        # rather than off `character_scene_keys`'s index 1, which is the uid
        # only when the sheet has one and the first alias when it does not.
        rows.append((name, str(ident.get("uid") or "").strip(),
                     [str(a or "").strip()
                      for a in (ident.get("aliases") or []) if str(a or "").strip()],
                     rid))
        own_names.add(name.casefold())

    def _claim(spelling, canon):
        text = str(spelling or "").strip()
        if not text:
            return
        folded = text.casefold()
        if claims.get(folded, canon) != canon:
            claims[folded] = None          # two beings: registered for neither
        else:
            claims[folded] = canon

    for canon, uid, alias_list, rid in rows:
        _claim(canon, canon)
        if uid:
            _claim(uid, canon)
        if rid is not None:
            _claim(f"character:{rid}", canon)
        for alias in (alias_list if aliases else []):
            if alias.casefold() in own_names \
                    and alias.casefold() != canon.casefold():
                continue               # a real name outranks an alias for it
            _claim(alias, canon)
    if player_name:
        _claim(player_name, player_name)
        _claim("character:player", player_name)

    forms = {k: v for k, v in claims.items() if v}
    # The alphanumeric fold `canonicalize_positions` has always applied, so
    # "Dr. Moon" still answers to a key written "drmoon". Second, so a literal
    # spelling always wins over a squashed one.
    squashed = {}
    for spelling, canon in forms.items():
        norm = fold_identity_key(spelling)
        if norm and norm not in forms:
            squashed.setdefault(norm, canon)

    def canonical(name):
        text = str(name or "").strip()
        if not text:
            return name
        folded = text.casefold()
        return (forms.get(folded)
                or squashed.get(fold_identity_key(folded))
                or name)

    return canonical, forms


def _cast_entity_claims(scene, cast, player_name=None):
    """({entity id -> the cast sheet name it IS}, forms), for the entities
    that unambiguously belong to exactly one registered character.

    ONE RESOLUTION, TWO WRITERS. `reconcile_cast_entity_names` renames what it
    finds; `stamp_authored_interiors` stamps the card's authored topology onto
    it. They ask the identical question -- which scene entity is this sheet's
    body -- and answering it twice is how two copies of one rule start to
    disagree, which is the defect `cast_spelling_policy` itself exists to have
    ended.

    TWO ENTITIES ANSWERING TO ONE CAST MEMBER CLAIM NEITHER. That is two
    records for one being -- a real defect, but a MERGE one
    (`_dedup_duplicate_entity_keys`); writing to both here would mint the
    duplicate the merge exists to collapse, and writing to one would pick a
    winner on nothing.
    """
    entities = (scene or {}).get("entities")
    if not isinstance(entities, dict):
        return {}, {}
    canonical, forms = cast_spelling_policy(cast, player_name)
    if not forms:
        return {}, {}
    registered = {str(v).casefold() for v in forms.values()}

    def belongs_to(entity, eid):
        """The cast member this entity IS, or None. Asked of a spelling it
        already answers to correctly as well as one it does not: an entity
        named right can still carry an alias that is somebody else's name."""
        for spelling in (eid, entity.get("name"),
                         *(entity.get("aliases") or [])):
            found = canonical(spelling)
            if str(found or "").strip().casefold() in registered:
                return found
        return None

    owned, claimed = {}, {}
    for eid, entity in entities.items():
        if not isinstance(entity, dict):
            continue
        canon = belongs_to(entity, eid)
        if not canon:
            continue
        owned[eid] = canon
        claimed.setdefault(canon, []).append(eid)
    return ({eid: canon for eid, canon in owned.items()
             if len(claimed.get(canon) or []) == 1}, forms)


def stamp_authored_interiors(scene, cast, player_name=None):
    """Put each cast card's authored inside on the scene entity that IS it.

    THE CARD IS NOT IN THE MERGE'S SCOPE. `materialize_enclosure_interiors`
    runs inside `merge_scene_with_diff`, which is handed a scene and a diff
    and has no cast, no sheets and no way to reach them -- so the topology an
    author declared has to be scene-resident before the merge reads it. This
    is the one seam that carries it across, and it runs at commit beside
    `reconcile_cast_entity_names`, on both the standing scene and this beat's
    diff, so a holder the Director just minted is stamped from its first beat.

    NEVER A RETRACTION, and never anything but this one key. An empty card
    section removes nothing -- clearing a sheet field is not a statement about
    a body already standing inside one -- and name, aliases, keys, rooms and
    positions are somebody else's to write. Idempotent, which is what lets a
    checkpoint restore replay it.

    Returns the entity ids it stamped, for the caller's report.
    """
    entities = (scene or {}).get("entities")
    if not isinstance(entities, dict):
        return []
    authored = {}
    for row in cast or []:
        # One normalization for the interior read and the name read (C14).
        sheet = normalized_character_of_row(row)
        if sheet is None:
            continue
        interior = character_body_interior(sheet)
        if not interior:
            continue
        name = str(normalize_character_data(sheet).get(
            "identity", {}).get("name") or "").strip()
        if name:
            authored[name.casefold()] = interior
    if not authored:
        return []
    claims, _forms = _cast_entity_claims(scene, cast, player_name)
    stamped = []
    for eid, canon in claims.items():
        interior = authored.get(str(canon).strip().casefold())
        if not interior:
            continue
        entity = entities[eid]
        if entity.get("interior_spec") == interior:
            continue
        entity["interior_spec"] = interior
        stamped.append(str(eid))
    return stamped


def reconcile_cast_entity_names(scene, cast, player_name=None):
    """Make `canonical_subject_map`'s assumption TRUE for cast-mirrored bodies.

    That function folds every spelling of a being onto the ENTITY's own
    `name`, on the stated ground that "for a mirrored cast member [it] IS the
    display name every reader already expects". Live in chat 82 it was not:
    the sheet said "Sarah Moon" and the Director minted the entity as
    "Dr. Sarah Moon", one of her aliases -- so the scene's idea of her
    canonical name pointed away from the one perception, character, narration
    and psychology all address her by.

    The fix is not a different fold direction. It is to reconcile the record
    the fold reads, at the seams that already hold the cast: an entity that
    unambiguously answers to exactly one registered character is renamed to
    that character's sheet name, and the spelling it loses is demoted to an
    ALIAS so prose and lookups written the old way still resolve.

    THE ENTITY KEY IS NEVER TOUCHED. Carried lights, derived stations and
    destruction cascades resolve by entity id, and renaming id-keyed rows is
    exactly what cost eleven tests the first time identity folding was tried
    (`spatial_identity.canonical_subject_map`'s G3 comment). Only `name` and
    `aliases` move.

    Idempotent, and it must stay so: it runs on the standing scene at every
    commit, which is what heals a save written before this rule existed, and
    a checkpoint restore replays it.

    Returns [(entity_id, old_name, new_name)] for warnings; empty when
    nothing needed saying, which is the common case.
    """
    entities = (scene or {}).get("entities")
    if not isinstance(entities, dict):
        return []
    claims, forms = _cast_entity_claims(scene, cast, player_name)
    renamed = []
    for eid, canon in claims.items():
        entity = entities[eid]
        old = str(entity.get("name") or "").strip()
        aliases = [str(a).strip() for a in (entity.get("aliases") or [])
                   if str(a or "").strip()]
        # An alias that belongs to ANOTHER cast member is not this body's to
        # answer to -- the Yuki guard, applied to the record rather than only
        # to the lookup, because the merge fold reads the record and has no
        # cast to consult. An alias nobody registered is left alone: it names
        # no other body, so it cannot steal one.
        aliases = [a for a in aliases
                   if forms.get(a.casefold(), canon) == canon]
        if old and old.casefold() != canon.casefold() \
                and old.casefold() not in {a.casefold() for a in aliases}:
            aliases.append(old)
        aliases = [a for a in aliases if a.casefold() != canon.casefold()]
        if entity.get("name") == canon and aliases == (entity.get("aliases")
                                                       or []):
            continue                                    # already reconciled
        entity["name"] = canon
        entity["aliases"] = aliases
        if old and old != canon:
            renamed.append((str(eid), old, canon))
    return renamed


def ensure_cast_entities(scene, cast, player_name=None):
    """Mint a scene entity for every registered cast body the scene STANDS
    somewhere and holds no record for. Returns [(entity_id, name)].

    A CAST MEMBER IS A BODY WHETHER OR NOT THE OPENING WROTE ONE. The
    establish is asked to mint the cast's entities and usually does; one
    that did not (scratch play 2026-09-14, chat 9, every cast member) left
    the captain and the companion as positions with no entity, and every
    resolver keyed on entities -- the movement mover first -- could not
    find them: his walk into the card room was read as hers. The
    positions table is where the engine already stands them; the record is
    minted from it, under the sheet's own spelling, and the reconcile that
    follows keeps it there. Idempotent.
    """
    if not isinstance(scene, dict):
        return []
    entities = scene.get("entities")
    if not isinstance(entities, dict):
        entities = scene["entities"] = {}
    positions = scene.get("positions") or {}
    if not isinstance(positions, dict) or not positions:
        return []
    canonical, forms = cast_spelling_policy(cast, player_name)
    if not forms:
        return []
    claims, _forms = _cast_entity_claims(scene, cast, player_name)
    held = {str(v).casefold() for v in claims.values()}
    minted = []
    for key in list(positions):
        canon = canonical(str(key))
        canon_cf = str(canon or "").strip().casefold()
        if not canon_cf or canon_cf not in {str(v).casefold() for v in forms.values()}:
            continue
        if canon_cf in held:
            continue
        eid = "char_" + normalize_room_id(str(canon))
        while eid in entities:
            eid += "_"
        entities[eid] = {"name": str(canon), "kind": "person", "from_event": 0,
                         "aliases": []}
        held.add(canon_cf)
        minted.append((eid, str(canon)))
    return minted


def canonicalize_positions(positions, cast, player_name=None):
    """Rewrite any positions key that identifies a registered cast character
    (or the player) to that person's display name -- the positions-key
    convention every reader (perception, commit, spatial) expects. Non-person
    keys (objects, unregistered background presences) are left untouched.

    Recognizing `character:<id>` and the player is load-bearing: the director
    model keys the SAME person by different schemes across a turn (Data as
    `character:29` here, `Lt. Commander Data` there), and without collapsing
    them to one canonical key the person acquired TWO position entries in
    conflicting rooms -- observed live, Data was simultaneously on the bridge
    (`character:29`) and in a corridor (`Lt. Commander Data`), so name-lookup
    resolved him to the corridor and perception rendered his bridge station as
    empty. Collapsing to a single key makes a later move update the one entry.

    ALIASES ARE STILL REFUSED HERE, and that is now a stated setting rather
    than a second table. `positions` keys objects and unregistered presences
    beside people, so a generic alias could name a genuinely separate entity
    and folding it would move an object into a person. `commit`'s attire heal
    accepts aliases because attire keys only bodies -- and the two disagreeing
    by accident is what left chat 82's Sarah Moon spelled "Sarah Moon" in
    `attire` and "Dr. Sarah Moon" in `positions` at the same time. The cure for
    that is `reconcile_cast_entity_names`, which fixes the ENTITY record so the
    merge fold spells every ledger the same way, not a wider match here.
    """
    if not isinstance(positions, dict):
        return {}
    if not cast and not player_name:
        return positions
    canonical, forms = cast_spelling_policy(cast, player_name, aliases=False)
    if not forms:
        return positions
    result = {}
    for key, room in positions.items():
        result[canonical(key)] = room
    return result

def drop_room_keyed_positions(positions, room_ids, warn=None):
    """Remove every `positions` entry whose KEY is a room.

    `positions` keys bodies, objects and presences and VALUES rooms; a room
    is where a thing is, never a thing placed somewhere. Measured on chat 137
    turn 52 (prose contract): `{"<stomach room>": "<stomach room>"}` passed
    every floor into the committed diff, where it would have seated a phantom
    body named after the room inside itself. No model can mean it, so it is
    dropped and reported, never repaired into a guess."""
    if not isinstance(positions, dict) or not room_ids:
        return positions
    rooms = {str(room) for room in room_ids}
    kept = {}
    for key, room in positions.items():
        if str(key) in rooms:
            if warn:
                warn(f"positions: {key!r} is a room, not a body; a room is "
                     "where a body is and is never placed itself -- the "
                     "entry was dropped")
            continue
        kept[key] = room
    return kept
