# spatial_identity.py
"""What a name in a scene refers to: ledger lookup, entity resolution, subject
canonicalisation, and room-id normalisation."""

import re
from collections import defaultdict
from typing import Optional


def room_of(scene: dict, name: str) -> Optional[str]:
    positions = scene.get("positions") or {}
    if name in positions:
        return positions[name]
    lname = (name or "").lower().strip()
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


def _position_of(scene: dict, name: str):
    """Where `name` is, resolved through entity identity rather than spelling.

    `positions` is keyed by whatever the writer used -- a cast member's display
    name, an entity id, an alias -- and the same being routinely appears under
    two of them at once: a character present as cast AND as a scene entity with
    its own id. `room_of` tolerates case and punctuation but not a different
    NAME for the same thing, so a containment record naming the entity id found
    nothing in a positions map keyed by the display name.

    Measured live: a body enclosed inside another was left at the literal
    string `"elyndra_succubus"` as its room -- an entity id sitting where a room
    id belongs, matching no room in the scene. `derive_contained_positions`
    could not resolve the carrier, so it did what it does when it cannot: it
    skipped, silently, and the body stayed nowhere for the rest of the story.
    Every spatial query then answered "unknown", which is the safe-closed
    default, so the failure looked exactly like distance.
    """
    direct = room_of(scene, name)
    if direct is not None:
        return direct
    entity = _entity_named(scene, name)
    if not entity:
        return None
    for label in (entity.get("name"), *(entity.get("aliases") or [])):
        if not label:
            continue
        found = room_of(scene, str(label))
        if found is not None:
            return found
    return None


def _entity_named(scene: dict, name: str) -> dict:
    """The entity record `name` refers to by id, name or alias. {} on a miss."""
    target = str(name or "").strip().casefold()
    for eid, entity in (scene.get("entities") or {}).items():
        if not isinstance(entity, dict):
            continue
        labels = [eid, entity.get("name"), *(entity.get("aliases") or [])]
        if any(str(label or "").strip().casefold() == target for label in labels):
            return entity
    return {}


# Every scene ledger keyed by WHO rather than by what. `stations[x]["at"]` is
# deliberately absent: it names an anchor, which is a place in a room, not a
# subject. `positions` VALUES are rooms for the same reason.
_SUBJECT_KEYED = ("positions", "scales", "attire", "stations", "poses",
                  "contained", "following")


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
        for alias_folded, alias_hits in by_alias.items():
            if len(alias_hits) == 1 and alias_hits[0][0] == eid \
                    and alias_folded not in by_name:
                out[alias_folded] = name
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
    contacts = scene.get("contacts")
    if isinstance(contacts, list):
        for contact in contacts:
            for field in ("actor", "target"):
                fold_field(contact, field, f"contacts.{field}")
    substances = scene.get("substances")
    if isinstance(substances, list):
        for record in substances:
            for field in ("source", "target"):
                fold_field(record, field, f"substances.{field}")
    return folded


def is_derived_room_name(room_id, name) -> bool:
    """Is `name` just the room id spelled out -- the placeholder the
    staged-lore materializers in commit.py and agents/director.py use when a
    room has to exist before anyone has named it? Such a name must never
    displace an authored one (see _merge_room)."""
    text = str(name or "").strip()
    return bool(text) and text == str(room_id or "").replace("_", " ").title()


def normalize_room_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
