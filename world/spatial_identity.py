# spatial_identity.py
"""What a name in a scene refers to: ledger lookup, entity resolution, subject
canonicalisation, and room-id normalisation."""

import re
from collections import defaultdict
from typing import Optional


def _positions_lookup(positions: dict, name: str, *, index=None):
    """Where `positions` puts this exact SPELLING, tolerating case, spacing and
    script. Never resolves one name into another -- that is `room_of`'s job,
    and keeping the two apart is what stops the identity pass from recursing
    through itself.

    `index` is `PositionsIndex(positions)` prepared once by a caller that
    asks this many times over one unchanged table; it answers identically and
    is the same three probes, done against a folded map instead of two linear
    scans per ask."""
    if name in positions:
        return positions[name]
    lname = (name or "").lower().strip()
    if index is not None:
        return index.lookup(lname)
    for k, v in positions.items():
        if k.lower().strip() == lname:
            return v
    # Script-aware: the old ASCII fold erased every non-Latin name to "",
    # so this fallback could never match one.
    from story.character_schema import fold_identity_key

    norm = fold_identity_key(lname)
    if norm:
        for k, v in positions.items():
            if fold_identity_key(k) == norm:
                return v
    return None


class PositionsIndex:
    """One folded read of a `positions` table, for a pass that asks it once
    per label per entity.

    A SWEEP HOLDS THE WHOLE ENTITY TABLE AGAINST THE WHOLE POSITIONS TABLE,
    and `_positions_lookup`'s tolerance is two linear scans -- one lowering
    every key, one folding every key through `fold_identity_key` -- paid
    again for every label of every entity. `room_of_record` walks three
    labels, so the emitter sweeps that run per field build re-fold the whole
    table three times per entity, and the full-miss path -- a carried or
    contained thing has no `positions` row at all -- is the common one.
    Measured during this review's B18 rework, 60 entities against 40
    positions: 20.6 ms per sweep unindexed, 0.86 ms indexed.

    The answer is the same one. The scans yielded the FIRST key that matched
    a lowered or folded form, so the map keeps the first and later
    collisions lose, exactly as before; the exact-spelling probe stays on
    the caller's side against the real dict, so it still wins first.
    """

    __slots__ = ("_lower", "_fold")

    def __init__(self, positions: dict):
        from story.character_schema import fold_identity_key

        self._lower = {}
        self._fold = {}
        # A malformed `positions` is nobody's placement, not a crash: the
        # `_ci_get` reads this replaced at the emitter sweeps answered None
        # for one, and a sweep must not be the thing that raises.
        if not isinstance(positions, dict):
            positions = {}
        for k, v in positions.items():
            lk = str(k).lower().strip()
            if lk not in self._lower:
                self._lower[lk] = v
            norm = fold_identity_key(str(k))
            if norm and norm not in self._fold:
                self._fold[norm] = v

    def lookup(self, lname: str):
        """The answer for an already-lowered spelling, or None."""
        if lname in self._lower:
            return self._lower[lname]
        from story.character_schema import fold_identity_key

        norm = fold_identity_key(lname)
        if norm and norm in self._fold:
            return self._fold[norm]
        return None


def room_of(scene: dict, name: str, *,
            identity: bool = True) -> Optional[str]:
    """Which room this being is in, resolved through entity identity rather
    than spelling. None when the scene does not place them.

    `positions` is keyed by whatever the writer used -- a cast member's display
    name, an entity id, an alias -- and the same being routinely appears under
    two of them at once: a character present as cast AND as a scene entity with
    its own id. Case and script folding is not enough for that; a different
    NAME for the same thing needs the entity record to join them.

    THIS IS THE ENGINE'S "WHERE IS X", and everything spatial is downstream of
    it: `visual_level_between`, `proximity_rel`, `entity_arc`, `entity_side`
    and `spatial_rel` all begin by asking it for two rooms. A miss is therefore
    not a small wrong answer -- it is `None` standing where a room belongs, and
    every one of those functions then fails CLOSED, which reads exactly like
    distance or a wall. Two measured consequences, both from one live scene
    (chat 82, "Sarah Moon -- Hinami attempt 2"):

    - a cast character whose scene entity carried her display name as an ALIAS
      ("Dr. Sarah Moon" entity, "Sarah Moon" sheet) had no room from her own
      name, so `visual_level_between` answered "none" for every body in the
      story and her perception view contained no one -- no presence, no pose,
      no appearance, no attire, and an empty `company` record. She was sitting
      at a window watching the person she could not see;
    - the same miss made every region of that person "concealed by vantage",
      which is how the attire ledger went unrendered while being perfectly
      correct.

    And one older, which is why the private `_position_of` this replaces
    existed at all: a body enclosed inside another was left at the literal
    string `"elyndra_succubus"` as its room -- an entity id sitting where a
    room id belongs, matching no room in the scene. `derive_contained_positions`
    could not resolve the carrier, so it did what it does when it cannot: it
    skipped, silently, and the body stayed nowhere for the rest of the story.
    That resolver was reachable only from containment; every other caller kept
    the narrow answer, which is the shape of gap this merge closes.

    `character_room` (agents.common) already walked a cast sheet's keys to
    dodge this for the ROOM alone; nothing dodged it for the relations, and the
    relations are what perception is made of. Resolving here fixes the class at
    the one function they all share instead of at each of them.

    AMBIGUITY RESOLVES TO NOTHING, the same rule `canonical_subject_map`
    states: two entities answering to one spelling are two beings, and picking
    whichever the dict happened to yield first would put one being's body in
    the other's room. Names beat aliases for the same reason a nickname must
    never outrank somebody's real name.

    `identity=False` asks the narrower question -- where does the scene put
    THIS SPELLING -- and exists for the callers that hold a better authority
    than the entity table. A registered cast member's own sheet is one: it
    lists every key that character legitimately answers to, and a stray entity
    row claiming the same display name must not outrank it. Those callers
    (`common.character_room`, `common.cast_room`) run every spelling they own
    through the narrow form FIRST and only then let identity resolution
    answer, so widening this function could not reorder them.
    """
    positions = scene.get("positions") or {}
    found = _positions_lookup(positions, name)
    if found is not None:
        return found
    if not identity:
        return None
    eid, entity = _unique_entity_keyed(scene, name)
    if not entity:
        return None
    return room_of_record(scene, eid, entity)


def room_of_record(scene: dict, eid, entity, *, index=None) -> Optional[str]:
    """`room_of`'s answer for a record the caller ALREADY HOLDS: where
    `positions` puts this entity under any spelling it owns.

    The id first: `positions` keys objects, fixtures and unregistered
    presences by entity id as a matter of course, and that key is the one a
    name-only walk could never reach. Then the name, then the aliases, each
    through `_positions_lookup`'s case/space/script tolerance.

    EVERY PASS THAT ITERATES `scene["entities"]` WANTS EXACTLY THIS and has
    the record in hand, so no name has to be re-resolved -- the transit
    dock-edge rewrite, the light and sound emitter sweeps, the vehicle
    gap-crossing stamp, the narrator's visible-portal sweep, the transit
    arrival scheduler, the shed-garment reclaim. Sharing the walk is the
    point (review 2026-09-07, B18): each of those sites had grown its own
    narrower copy -- `positions.get(eid)`, or that walked one further label
    -- and a lift car whose `positions` row was filed under `lift_car`
    against the id `Lift_Car` was nowhere to all of them at once: its
    interior's dock edge left unrewritten, a lit lamp lighting no room, a
    ferry arriving in no zone, a hatch the narrator never reported.

    Ambiguity is not this function's problem, because a record cannot be
    ambiguous: `room_of` resolves the NAME (and refuses a tie) before
    arriving here.

    `index` is a `PositionsIndex` over the same `positions`, for a sweep
    asking this once per entity; the answer does not depend on it.
    """
    positions = scene.get("positions") or {}
    record = entity if isinstance(entity, dict) else {}
    for label in (eid, record.get("name"), *(record.get("aliases") or [])):
        if not label:
            continue
        found = _positions_lookup(positions, str(label), index=index)
        if found is not None:
            return found
    return None


def _ci_get(mapping, name):
    """Case/whitespace-tolerant dict lookup, matching room_of's key tolerance,
    so an orientation/station keyed 'Hinami' still resolves for a caller passing
    'hinami'. Returns None on miss."""
    if not isinstance(mapping, dict) or not name:
        return None
    if name in mapping:
        return mapping[name]
    ln = str(name).lower().strip()
    for k, v in mapping.items():
        if str(k).lower().strip() == ln:
            return v
    return None


def same_subject(scene: dict, a: str, b: str) -> bool:
    """Do these two strings name the same being in this scene?

    The same character routinely appears under two spellings at once -- a cast
    display name and a scene entity id -- and a bare casefold comparison
    between them is False, which is how an enclosure came to be compared
    against its own occupant's holder and lose. Falls back to plain equality
    when neither string is a known entity, so this never invents a match.
    """
    left = str(a or "").strip().casefold()
    right = str(b or "").strip().casefold()
    if not left or not right:
        return False
    if left == right:
        return True
    for name, other in ((a, right), (b, left)):
        entity = _entity_named(scene, name)
        if not entity:
            continue
        labels = {str(label).strip().casefold()
                  for label in (entity.get("name"),
                                *(entity.get("aliases") or [])) if label}
        for eid, record in (scene.get("entities") or {}).items():
            if record is entity:
                labels.add(str(eid).strip().casefold())
        if other in labels:
            return True
    return False


def _entities_named(scene: dict, name: str):
    """([(id, entity)] matched by id-or-name, [(id, entity)] matched by alias).

    Two lists rather than one because the two answers are not equally strong:
    an entity's id and its name are what it IS, an alias is what it also
    answers to, and a reader that must not guess needs to know which kind of
    match it got.
    """
    target = str(name or "").strip().casefold()
    primary, aliased = [], []
    if not target:
        return primary, aliased
    for eid, entity in (scene.get("entities") or {}).items():
        if not isinstance(entity, dict):
            continue
        if str(eid or "").strip().casefold() == target \
                or str(entity.get("name") or "").strip().casefold() == target:
            primary.append((eid, entity))
        elif any(str(alias or "").strip().casefold() == target
                 for alias in entity.get("aliases") or []):
            aliased.append((eid, entity))
    return primary, aliased


def _entity_named(scene: dict, name: str) -> dict:
    """The entity record `name` refers to by id, name or alias. {} on a miss.
    First match wins; see `_unique_entity_keyed` for the strict form."""
    primary, aliased = _entities_named(scene, name)
    for _eid, entity in (*primary, *aliased):
        return entity
    return {}


def _unique_entity_keyed(scene: dict, name: str):
    """(id, entity) for the being `name` UNAMBIGUOUSLY refers to, else
    (None, {}).

    Names beat aliases, and a tie in either tier is a miss: folding two beings
    into one is strictly worse than leaving two spellings of one.
    """
    primary, aliased = _entities_named(scene, name)
    if len(primary) == 1:
        return primary[0]
    if not primary and len(aliased) == 1:
        return aliased[0]
    return None, {}


#: The scene ledgers only a BODY has a row in: what it wears, how big it is
#: against its own baseline, its air and injury, and what is drawn on it. The
#: other subject-keyed tables are deliberately NOT here -- a lamp has a
#: `position`, a pry bar has a `station`, a crate is `contained` and a cart
#: `following` -- which is the whole distinction `scene_names_body` exists to
#: draw. `poses` is not here either, by the composer's measured ruling (A POSE
#: IS NOT EVIDENCE OF A BODY, tests/test_composer_poses.py): a Director
#: legitimately gives a staff, a canteen or a desk a posture, and a ledger
#: that read one as proof of a person told a woman alone in a dead town she
#: was leaning on "someone" on fourteen of twenty beats.
#:
#: `spatial_transit._is_body_entity` reads two of these and is NOT a fifth
#: spelling of the question below: it asks whether an ENTITY RECORD in hand is
#: a body rather than a vehicle or a container, for the dock-edge split, and
#: the wardrobe-and-scale pair was measured exact for that against every scene
#: on disk. It is a tier of this ladder, not a rival to it.
_BODY_LEDGERS = ("attire", "scales", "vitals", "overlays")


def _keyed_body_ledger(scene: dict, keys) -> bool:
    """Does any spelling in `keys` hold a row in a body ledger?"""
    for source in _BODY_LEDGERS:
        table = (scene or {}).get(source)
        if not isinstance(table, dict):
            continue
        for key in keys:
            folded = str(key or "").strip().casefold()
            if folded and any(str(k).strip().casefold() == folded
                              for k in table):
                return True
    return False


def _body_kinds():
    """The kinds an ENTITY RECORD can carry that name a body (tier 2).

    `llm.schemas._ANIMATE_ENTITY_KINDS`, the engine's own animate vocabulary
    -- the closed set the schema owns and two other readers already asked.
    It began as `{"person", "creature"}` here, which was narrower than either
    of them: a `guard`, an `android`, a `ghost` and a `swarm` are all bodies
    to the schema and were things to this predicate, so the one predicate
    disagreed with the vocabulary it was meant to speak for (2026-09-08).
    Imported at call time: `world` may not import `llm` at module scope.
    """
    from llm.schemas import _ANIMATE_ENTITY_KINDS

    return _ANIMATE_ENTITY_KINDS


def scene_names_body(scene: dict, name: str) -> bool:
    """Is `name` a BODY of this scene, or a thing that merely stands in it?

    THE ONE BODY PREDICATE (review 2026-09-07 A56 and its rework). Four
    readers asked this question in four spellings and two of them gave
    OPPOSITE answers for the same subject, which is the
    two-representations-free-to-disagree class this review keeps closing:
    `spatial_contacts._endpoint_is_body` (the identity floor that decides
    between "someone" and "something"), `comfort._is_body` (is the thing I am
    leaning on a person), `mechanics._room_occupants` /
    `unanswered_hazard_subjects` (who a standing condition acts on), and
    `charter_predation._scene_figures_at` (who a creature may hunt), which
    answered it by SUBTRACTING entity membership.

    The ladder, in order, and every tier is AFFIRMATIVE -- it reads what the
    scene says rather than what it omits:

      1. A row in a body ledger (`_BODY_LEDGERS`), under the subject's own
         spelling or any spelling its entity record answers to. A body is the
         thing that wears something, has a size against its own baseline,
         carries air and injury, or is marked. Not a pose: a thing may be
         given one (see the tuple's note).
      2. Otherwise, an ENTITY RECORD is the scene saying what this is. One
         whose `kind` is in the engine's own animate vocabulary
         (`llm.schemas._ANIMATE_ENTITY_KINDS` -- person, creature, guard,
         android, ghost, swarm and the rest) is the scene naming a body;
         any other kind -- a lamp, a lift car, a celestial body, a stretch
         of terrain -- is not. Background people are placed exactly so, "as
         entities with kind 'person'" (director_establish).
      3. Otherwise, a subject the scene STANDS SOMEWHERE and records nothing
         else about is a body. A registered mind routinely has no entity
         record at all, and on the beat before it is dressed it has no ledger
         row either.

    WHICH WAY TIER 3 FALLS IS A DECISION, and it is the reportable direction.
    Measured on the bench copies (2026-09-08): chat 117's live scene holds 22
    position keys, 2 bodies and 20 things, and one of those things
    (`iron_bung`) carries no entity record, so tier 3 calls it a body -- the
    cost is the vitals sweep saying out loud, every beat a condition ticks,
    that no body of that name is in the ledger. The other direction costs
    silence: a person the scene records nothing of but where they stand would
    be dropped from a fire with no notice, which is the failure history
    `mechanics._tick_conditions` was written against ("a mechanism that
    silently never fires is this table's whole failure history"). A thing
    wrongly counted as a body is loud and repairable -- name it as an entity
    and the tier stops firing; a body wrongly counted as a thing is silent.

    A56's own measured cases are all tier 2 and all fixed by it: docked
    vehicles, the zones `spatial_frames.infer_vehicle_zones` derives, carts,
    boats, fixtures and tools carry entity records -- 19 of chat 117's 20
    non-bodies, and a condition standing over every room of that scene went
    from 22 subjects to 3.
    """
    if not isinstance(scene, dict):
        return False
    label = str(name or "").strip()
    if not label:
        return False
    eid, ent = _unique_entity_keyed(scene, label)
    keys = [label, eid]
    if isinstance(ent, dict):
        keys.append(ent.get("name"))
        keys.extend(ent.get("aliases") or [])
    if _keyed_body_ledger(scene, keys):
        return True
    if eid:
        kind = str((ent or {}).get("kind") or "").strip().casefold() \
            if isinstance(ent, dict) else ""
        return kind in _body_kinds()
    positions = scene.get("positions")
    if not isinstance(positions, dict):
        return False
    return _positions_lookup(positions, label) is not None


# Every scene ledger keyed by WHO rather than by what. `stations[x]["at"]` is
# deliberately absent: it names an anchor, which is a place in a room, not a
# subject. `positions` VALUES are rooms for the same reason.
_SUBJECT_KEYED = ("positions", "scales", "attire", "stations", "poses",
                  "contained", "following",
                  # Keyed by WHO like its six siblings, and missed by this
                  # tuple until 2026-08-19 -- so a body folded to one spelling
                  # everywhere else kept a second one here, and `entity_arc`
                  # and `entity_side` (which read it through `_ci_get`, case
                  # tolerant and nothing more) answered None for the observer
                  # under their own sheet name.
                  "orientation",
                  # The body ledgers, missed the same way until the review of
                  # 2026-09-07 (Section H residual on B4). `spatial_frames`
                  # has always partitioned a frame on these two BESIDE this
                  # tuple -- "`_SUBJECT_KEYED` plus the body ledgers keyed the
                  # same way" -- which is two lists of one thing, and the
                  # shorter one is the one the fold reads. So a woman held as
                  # `positions["Dr. Sarah Moon"]` and `vitals["Sarah Moon"]`
                  # folded everywhere except where her air and injury are
                  # written, and `survival.vitals_entry_key` was left picking
                  # between two rows for one body downstream of the fold that
                  # exists to leave one.
                  "vitals", "overlays")


def _live_subject_spellings(scene: dict) -> set:
    """Every string this scene currently uses to name a SUBJECT, casefolded.

    Keys of the subject-keyed ledgers, plus the subject-valued fields inside
    them. Not `stations[x]["at"]` (an anchor) and not `positions` values
    (rooms) -- naming a place is not naming somebody.
    """
    out = set()

    def add(value):
        text = str(value or "").strip()
        if text:
            out.add(text.casefold())

    for ledger in _SUBJECT_KEYED:
        table = (scene or {}).get(ledger)
        if isinstance(table, dict):
            for key in table:
                add(key)
    contained = (scene or {}).get("contained")
    if isinstance(contained, dict):
        for record in contained.values():
            if isinstance(record, dict):
                add(record.get("in"))
    following = (scene or {}).get("following")
    if isinstance(following, dict):
        for record in following.values():
            if isinstance(record, dict):
                add(record.get("target"))
    poses = (scene or {}).get("poses")
    if isinstance(poses, dict):
        for record in poses.values():
            if isinstance(record, dict):
                add(record.get("relative_to"))
    contacts = (scene or {}).get("contacts")
    if isinstance(contacts, list):
        for contact in contacts:
            if isinstance(contact, dict):
                add(contact.get("actor"))
                add(contact.get("target"))
    contact_actions = (scene or {}).get("contact_actions")
    if isinstance(contact_actions, list):
        for record in contact_actions:
            if isinstance(record, dict):
                add(record.get("actor"))
    substances = (scene or {}).get("substances")
    if isinstance(substances, list):
        for record in substances:
            if isinstance(record, dict):
                add(record.get("source"))
                add(record.get("target"))
    return out


def canonical_subject_map(scene: dict) -> dict:
    """Every spelling of every being in this scene, folded onto one name.

    A being routinely carries two names at once -- a cast display name and a
    scene entity id -- because a character can be registered cast AND present
    as a scene entity, with nothing joining the two records. The Director then
    writes whichever it reaches for, and both are correct.

    Canonical is the entity's own `name`, which for a mirrored cast member IS
    the display name every reader already expects, so this folds toward the
    convention rather than inventing one.

    AMBIGUITY RESOLVES TO NOTHING, exactly as `entity_room_by_name` decided
    before it: two entities named "A Dalek" are two Daleks, and folding both
    onto one key would merge two beings into one position. A name shared by
    more than one entity is left alone in every direction, and so is an alias
    that more than one entity claims. Names beat aliases, so a nickname can
    never outrank somebody's real name.
    """
    entities = (scene or {}).get("entities")
    if not isinstance(entities, dict):
        return {}
    by_name = defaultdict(list)
    by_alias = defaultdict(list)
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or "").strip()
        if not name:
            continue
        by_name[name.casefold()].append((eid, name))
        for alias in ent.get("aliases") or []:
            text = str(alias or "").strip()
            if text:
                by_alias[text.casefold()].append((eid, name))
    # ONLY where two spellings are genuinely in use at once. A lone entity-id
    # key is not ambiguous and must not be renamed: `positions` legitimately
    # keys objects, fixtures and unregistered presences by id, readers resolve
    # them that way, and rewriting those to display names breaks carried
    # lights, derived stations and destruction cascades -- measured, as eleven
    # failing tests, the first time this folded on identity alone. The defect
    # is TWO RECORDS FOR ONE BEING, so the fold only fires when the canonical
    # name is already live as a subject spelling somewhere in this scene.
    live = _live_subject_spellings(scene)
    out = {}
    for folded, hits in by_name.items():
        if len(hits) != 1:
            continue
        eid, name = hits[0]
        # The name must be live under a spelling that is NOT this entity's own
        # id, or an id differing from its name only by case ("tardis" for
        # "TARDIS", "torch" for "Torch") counts as its own evidence and folds
        # itself away -- which is how an object with a single id-keyed position
        # lost that position entirely.
        if name.casefold() == str(eid).strip().casefold():
            continue
        if name.casefold() not in live:
            continue
        out[str(eid).strip().casefold()] = name
    # THE ALIAS FOLD IS NOT THE ID FOLD, and nesting it inside made it
    # unreachable for the commonest shape there is. The guard above exists so
    # an entity whose id differs from its name only by case ("tardis" for
    # "TARDIS") does not fold its own key away -- a question about the ID. An
    # entity keyed by its own name hits that guard too, and took its ALIASES
    # down with it, so a body answering to two live spellings kept both. Chat
    # 82 held one woman as `attire["Sarah Moon"]` beside
    # `positions["Dr. Sarah Moon"]` for the whole scene because of this.
    #
    # Hoisted, with its own guards rather than the id one's: the alias must be
    # claimed by exactly one entity, must not be any entity's own NAME (a real
    # name outranks somebody else's nickname for it), and the canonical name
    # must still be live under some other spelling -- G3 intact, because this
    # folds spellings ONTO an id-key and never off one.
    for folded, hits in by_name.items():
        if len(hits) != 1:
            continue
        eid, name = hits[0]
        if name.casefold() not in live:
            continue
        for alias_folded, alias_hits in by_alias.items():
            if len(alias_hits) == 1 and alias_hits[0][0] == eid \
                    and alias_folded not in by_name \
                    and alias_folded != name.casefold():
                out.setdefault(alias_folded, name)
    # Never rewrite one being's name into another's.
    return {k: v for k, v in out.items()
            if k not in by_name or by_name[k][0][1] == v}


def canonical_subject(scene: dict, name: str) -> str:
    """One spelling for one being. Returns `name` unchanged when the scene has
    nothing better -- an unregistered presence keeps whatever it was called."""
    text = str(name or "").strip()
    if not text:
        return text
    return canonical_subject_map(scene).get(text.casefold(), text)


def normalize_scene_subjects(scene: dict) -> list:
    """Fold every subject-keyed ledger onto one spelling per being.

    `same_subject` closed five defects that were all the same `==`, and it is a
    FLOOR, not a fix: it only helps at comparison sites somebody remembered to
    route through it, and every new site is a fresh chance to write `==` again.
    A guard that has to be remembered is a guard that will be forgotten.

    So the data is made single-spelled instead. Run at merge, before position
    derivation, this leaves exactly one key per being in `positions`, `scales`,
    `attire`, `stations`, `poses`, `contained` (keys and `in`), `contacts`
    (actor/target), `substances` (source/target) and `following` -- after which `==` is correct again because
    there is nothing left for it to be wrong about.

    Two entries that fold together are a genuine conflict: the same being
    recorded twice, in two spellings, possibly in two rooms. The one already
    under the canonical spelling wins, because that is the key every reader
    has been resolving against and therefore the one the story has been
    running on. Returns what it folded, for warnings.
    """
    folded = []
    mapping = canonical_subject_map(scene)
    if not mapping:
        return folded

    def canon(value):
        text = str(value or "").strip()
        return mapping.get(text.casefold(), text)

    for ledger in _SUBJECT_KEYED:
        table = scene.get(ledger)
        if not isinstance(table, dict):
            continue
        rebuilt = {}
        for key, value in table.items():
            target = canon(key)
            if target != key:
                folded.append((ledger, str(key), target))
            # First writer of the canonical spelling keeps it. A later entry
            # arriving under an alias does not overwrite the record every
            # reader has been using.
            if target in rebuilt and target in table and target != key:
                continue
            rebuilt[target] = value
        scene[ledger] = rebuilt

    def fold_field(record, field, where):
        """Rewrite a subject-VALUED field, reporting it like a key fold --
        `contained.in` naming one spelling while `positions` uses another is
        the exact shape that started this, and it leaves no key to report."""
        if not isinstance(record, dict) or not record.get(field):
            return
        target = canon(record[field])
        if target != record[field]:
            folded.append((where, str(record[field]), target))
            record[field] = target

    def fold_part_owner(record, field, where):
        """Fold the OWNER half of a part-qualified value `<owner>.<part>`.

        One ledger field must hold ONE spelling of one body. A part-qualified
        value is folded by its owner, because only the owner half is a subject
        spelling. Measured: a pose record held `mirelle_sulmirath.hands` in
        `support` beside the already-folded `Mirelle Sulmirath` in
        `relative_to` -- one body under two spellings in one record.

        It is a separate helper rather than a `fold_field` call because
        `poses.support` also legitimately names a ROOM ANCHOR keyed by id, and
        `normalize_scene_poses` looks those ids up in the room's `anchors`.
        Folding a whole support value onto a display name would break that
        lookup -- the same hazard `canonical_subject_map` guards against.
        """
        if not isinstance(record, dict) or not record.get(field):
            return
        value = str(record[field])
        owner, dot, part = value.partition(".")
        if not dot or not owner.strip() or not part.strip():
            return
        target = canon(owner)
        if target == owner:
            return
        folded.append((where, value, f"{target}.{part}"))
        record[field] = f"{target}.{part}"

    contained = scene.get("contained")
    if isinstance(contained, dict):
        for record in contained.values():
            fold_field(record, "in", "contained.in")
    following = scene.get("following")
    if isinstance(following, dict):
        for record in following.values():
            fold_field(record, "target", "following.target")
    poses = scene.get("poses")
    if isinstance(poses, dict):
        for record in poses.values():
            fold_field(record, "relative_to", "poses.relative_to")
            # A relation referent may be part-qualified too, and `support` is
            # the field the fold never covered at all.
            fold_part_owner(record, "relative_to", "poses.relative_to")
            fold_part_owner(record, "support", "poses.support")
    contacts = scene.get("contacts")
    if isinstance(contacts, list):
        for contact in contacts:
            for field in ("actor", "target"):
                fold_field(contact, field, f"contacts.{field}")
    contact_actions = scene.get("contact_actions")
    if isinstance(contact_actions, list):
        for record in contact_actions:
            fold_field(record, "actor", "contact_actions.actor")
    substances = scene.get("substances")
    if isinstance(substances, list):
        for record in substances:
            for field in ("source", "target"):
                fold_field(record, field, f"substances.{field}")
    return folded


def derived_room_name(room_id) -> str:
    """The placeholder a room wears until someone names it: its id spelled
    out. ONE PRODUCER. Five sites each spelled `replace("_", " ").title()`
    for themselves (the staged-lore materializers in `commit_scene_state`,
    `director` and `common`, the narrator's room table, and the predicate
    below), and the six places perception falls back from a missing name
    applied no placeholder at all and handed the view the raw id -- measured
    on the descent copy (chat 117 beat 118): the spatial hand minted
    `sub_level_three_utility_core` with `name: ""`, and the player's view
    read "You are in sub_level_three_utility_core." An id is a handle the
    engine holds, never a word of the story; where the engine must show a
    room nobody has named, this is the one spelling it shows."""
    return str(room_id or "").replace("_", " ").title()


def room_display_name(room, room_id) -> str:
    """A room's authored name, else its placeholder; "" only when there is
    no room at all. The reader-side floor for every "You are in {room}"."""
    name = ""
    if isinstance(room, dict):
        name = str(room.get("name") or "").strip()
    return name or derived_room_name(room_id)


#: Set on a room whose name the ENGINE wrote because nobody had named it yet.
#: A FACT, not a guess: `is_derived_room_name` can only ask whether a name
#: looks like the id spelled out, and an authored name routinely does --
#: "Market Square" for `market_square`, "Crossroads" for `crossroads`,
#: "Spine" for `spine`. Every reader that must tell a placeholder from a name
#: somebody chose was therefore wrong about the commonest way a room is
#: named, which is what held D8 at the gate (review 2026-09-07, 2026-09-08).
#: A hyphen or an article saved a name by accident and nothing else did.
ROOM_NAME_DERIVED = "name_derived"


def room_name_is_placeholder(room, room_id) -> bool:
    """Is this room's name the engine's placeholder rather than a name?

    Asks the ROOM first, because since 2026-09-08 the mint says so outright;
    falls back to the spelling test for a scene written before that, where
    the guess is all there is. The fallback is why an authored name that IS
    the id spelled out still reads as a placeholder in an old scene, and the
    reason the mark exists is that it cannot in a new one.
    """
    if isinstance(room, dict):
        if room.get(ROOM_NAME_DERIVED):
            return True
        if ROOM_NAME_DERIVED in room:
            return False           # said outright: somebody named this
        return is_derived_room_name(room_id, room.get("name"))
    return False


def is_derived_room_name(room_id, name) -> bool:
    """Is `name` just the room id spelled out -- the placeholder
    `derived_room_name` gives a room that has to exist before anyone has
    named it? Such a name must never displace an authored one (see
    _merge_room)."""
    text = str(name or "").strip()
    return bool(text) and text == derived_room_name(room_id)


def normalize_room_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")


def room_spellings(room_id, room_def=None) -> tuple:
    """EVERY SPELLING ONE ROOM ANSWERS TO, folded, display name first.

    A room has two spellings: the id the engine keys it by and the name the
    story calls it. `normalize_room_id` folds both, and two spellings that
    fold the same are one room. ONE PRODUCER of that set, because four sites
    answered "does the world already hold this room?" three different ways
    (review 2026-09-07 B2): `classify_movement` and the Director's
    `needs_mapping` trigger compared the model's spelling to the scene keys
    EXACTLY, `_location_query_status` folded, and commit's mint dedup folded
    through its own private `_room_display_slug`. A Director that spells a
    held room its own way therefore drew a planning need and a second mint
    for a room already on the map.

    Name first: `spellings[0]` is the room's display slug, which is what a
    registry alias index and the plan's spelling table are keyed by.
    """
    out = []
    if isinstance(room_def, dict):
        name = normalize_room_id(str(room_def.get("name") or ""))
        if name:
            out.append(name)
    folded = normalize_room_id(str(room_id or ""))
    if folded and folded not in out:
        out.append(folded)
    return tuple(out)


def scene_room_id(scene, target) -> str:
    """The id of the scene room `target` names, or "" when the world holds
    none under that spelling.

    The one answer to "is this destination a room the scene already has?".
    An exact key wins outright; otherwise the fold decides
    (`room_spellings`). A spelling two rooms answer to names neither and
    resolves to "" -- the same refusal commit's mint dedup makes for a name
    two plans share.
    """
    target = str(target or "")
    rooms = scene.get("rooms") if isinstance(scene, dict) else None
    if not isinstance(rooms, dict) or not rooms:
        return ""
    if target in rooms:
        return target
    folded = normalize_room_id(target)
    if not folded:
        return ""
    hits = [str(rid) for rid, rdef in rooms.items()
            if folded in room_spellings(rid, rdef)]
    return hits[0] if len(hits) == 1 else ""
