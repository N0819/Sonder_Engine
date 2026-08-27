# spatial_merge.py
"""The deterministic scene merge: room/entity field merging, follow ops,
structural repair, and merge_scene_with_diff."""

import copy
import re
from typing import Optional

from llm.schemas import NON_ENTITY_FIELD_KEYS, is_derived_entity_name
from world.spatial_orientation import (normalize_bearing, normalize_scene_bearings,
                                 opposite_bearing)

from world.spatial_barriers import (_PASSABLE_BARRIERS, normalize_barrier,
                              normalize_scene_barriers)
from world.spatial_contact_migration import contacts_from_entity_state
from world.spatial_contacts import (apply_contact_ops,
                              contacts_across_enclosure,
                              contacts_broken_by_scale_change,
                              normalize_scene_contacts)
from world.spatial_containment import (
    _clean_containment,
    advance_room_transits,
    clamp_scale,
    containment_broken_by_scale_change,
    derive_containment_from_contacts,
    derive_contained_positions,
    derive_inventory_placements,
    derive_minted_entity_placements,
    materialize_enclosure_interiors,
    materialize_named_stations,
    replace_engine_minted_interiors,
    normalize_scene_containment,
    place_enclosed_bodies,
    release_declared_departures,
    normalize_scene_scales,
)
from world.spatial_geometry import (apply_pose_diff, derive_scene_stations,
                              poses_broken_by_scale_change,
                              invalidate_contact_bound_poses,
                              normalize_scene_poses, normalize_scene_stations)
from world.spatial_identity import (_ci_get, _entity_named, room_of,
                              is_derived_room_name, normalize_scene_subjects)
from world.spatial_senses import apply_comms_ops, normalize_scene_comms
from world.spatial_substance import apply_substance_ops, apply_contact_action_ops
from world.spatial_routing import stamp_sight_direction
from world.spatial_transit import (apply_transit_dock_edges,
                                  infer_body_enclosures,
                                  sync_entity_interior_rooms)


def repair_entity_positions(scene: dict) -> list:
    """A position naming an ENTITY rather than a room is a category error.

    `positions` maps a body to a ROOM. The Director periodically writes an
    entity id there instead -- "she is in Elyndra" is a true sentence and an
    invalid position -- and nothing rejected it, because every spatial query
    resolves an unknown room to the safe-closed default rather than raising.

    Measured live (chat 60): a body enclosed inside another sat at the literal
    string `"elyndra_succubus"` for the rest of the story, a room that does not
    exist. The relation to the body around her came back

        {"same_room": false, "barrier": "separated", "distance": "far"}

    -- the same answer the engine gave for a window across the room. Nothing
    was broken loudly. She was simply nowhere, and every channel read as
    distance, which is exactly what being nowhere looks like from inside a
    ranking function.

    The repair is the reading the Director meant: put the body in the entity's
    own room and record a station AT that entity, which is the engine's
    existing vocabulary for being at a thing rather than in it. Containment is
    NOT inferred here -- `derive_contained_positions` has already run and owns
    that case, and inventing an enclosure from a mistyped position would turn a
    typo into a firewall change. Returns what it repaired, for warnings.
    """
    positions = scene.get("positions")
    rooms = scene.get("rooms") or {}
    if not isinstance(positions, dict) or not isinstance(rooms, dict):
        return []
    repaired = []
    for name, where in list(positions.items()):
        key = str(where or "").strip()
        if not key or key in rooms or _ci_get(rooms, key) is not None:
            continue
        entity = _entity_named(scene, key)
        if not entity:
            continue
        room = room_of(scene, key)
        if room is None or room == key:
            continue
        positions[name] = room
        stations = scene.setdefault("stations", {})
        if isinstance(stations, dict):
            slot = stations.get(name)
            if not isinstance(slot, dict):
                slot = {"at": None, "near": []}
                stations[name] = slot
            if not slot.get("at"):
                slot["at"] = key
        repaired.append((name, key, room))
    return repaired


def prune_bodiless_positions(scene: dict) -> list:
    """Drop `positions` entries belonging to a bodiless voice.

    A ship's computer, a station PA and a public-address system are not
    standing anywhere -- `scene.is_ubiquitous_entity` calls giving one a room
    a category error, and the Director prompt tells it to declare such a thing
    with NO position. It still happens: measured live, one was created with a
    room in the same breath as a description reading "a voice-activated system
    with no physical body", trailed the player for five beats, and was then
    stranded in the room it was last voiced in for eighty more.

    A stale entry like that is not inert. Every reader that asks where the
    speaker is gets an answer, and the answer is wrong -- the delivery rescue
    in perception is the one that matters, and it is now asked of the entity
    rather than of the position, but nothing was removing the record itself
    and there is no way for an author to. So merge hygiene removes it, the
    same way position changes prune an impossible contact.

    Returns the names dropped, for the caller to report; mutates in place.
    """
    positions = scene.get("positions")
    entities = scene.get("entities")
    if not isinstance(positions, dict) or not isinstance(entities, dict):
        return []
    try:  # lazy: scene.py imports THIS module, so the edge only goes one way
        from story.scene import ubiquitous_speaker_names
        bodiless = ubiquitous_speaker_names(scene)
    except Exception:
        return []
    if not bodiless:
        return []
    dropped = [key for key in list(positions)
               if str(key).strip().casefold() in bodiless]
    for key in dropped:
        positions.pop(key, None)
    return dropped


def _merge_room(existing: dict, incoming: dict, room_id=None) -> dict:
    """Merge an incoming room redeclaration into an already-known room.

    A director/mapping model redeclaring a room to add or change one
    adjacency edge has no reliable way to also echo back every other edge
    it didn't touch. Replacing the whole room (the old behavior) silently
    drops every edge the model didn't re-mention -- observed live when
    generating a west wing connection wiped out an existing corridor's
    links to the entrance hall and stairwell. Adjacency is merged by
    upserting on `to`: an incoming edge with the same target updates it
    (so barrier/distance changes still work), edges not mentioned survive.
    Explicit removal goes through `remove_adjacent`, not silence.
    """
    merged_room = dict(existing)

    for field in ("name", "desc", "notes", "parent_entity"):
        if not incoming.get(field):
            continue
        if field == "name" and existing.get("name") \
                and is_derived_room_name(room_id, incoming[field]):
            continue  # an id slug never overwrites a name someone authored
        merged_room[field] = incoming[field]

    existing_edges = {
        edge.get("to"): dict(edge)
        for edge in (existing.get("adjacent") or [])
        if isinstance(edge, dict) and edge.get("to")
    }

    # Edge FIELDS get the same silence-vs-erasure doctrine the edges
    # themselves already have. A model re-mentioning a doorway ("r0503
    # connects to r0603, open") has no reliable way to also echo back the
    # bearing it never thinks about, and wholesale replacement here was
    # erasing authored `dir`s every time -- measured live (maze arm): 18 of
    # 98 edge-sides stripped bare, including the shrine's ONLY approach,
    # after which every declared "run east" through them failed and
    # sprint_reach stopped offering the passage at all. An absent field is
    # silence; a value (barrier changes, a re-bearing) still lands.
    for edge in (incoming.get("adjacent") or []):
        if isinstance(edge, dict) and edge.get("to"):
            prior = existing_edges.get(edge["to"])
            if prior:
                spoken = {k: v for k, v in edge.items()
                          if v is not None and v != ""}
                existing_edges[edge["to"]] = {**prior, **spoken}
            else:
                existing_edges[edge["to"]] = dict(edge)

    merged_room["adjacent"] = list(existing_edges.values())

    for key, value in incoming.items():
        if key in ("name", "desc", "notes", "parent_entity", "adjacent"):
            continue
        # An empty container is indistinguishable from "the model did not
        # mention this", so it cannot be read as an erasure -- the doctrine
        # `_ENTITY_DEFAULT_FIELDS` already applies to entities, and the same
        # trap on rooms costs more: blanking `anchors` takes every station
        # hanging off them with it, silently, on any beat that re-echoes the
        # room. Emptying one goes through an explicit write, not a default.
        if key in _ROOM_SILENT_WHEN_EMPTY and not value:
            continue
        merged_room[key] = value

    return merged_room


# Room fields whose empty value means "unmentioned" rather than "cleared".
_ROOM_SILENT_WHEN_EMPTY = frozenset({"anchors", "size", "zone", "light",
                                     "exposure", "transit_seconds"})

# Every SceneEntityDef field whose schema default is indistinguishable from
# "the model did not mention this". A diff carrying one of these cannot be
# read as an erasure -- see _merge_entity.
_ENTITY_DEFAULT_FIELDS = {
    "kind": "object",
    "description": "",
    "aliases": [],
    "portable": False,
    "container": False,
    "interior_rooms": [],
    "ubiquitous": False,
    # Absent from this map, these two could only ever be set at CREATION: the
    # merge below copies listed fields and leaves everything else at whatever
    # the existing record held, so a Director declaring `enclosure` on an
    # entity it had already introduced was silently dropped every time. That
    # made both fields unfixable in flight -- an interior authored see-through
    # stayed see-through for the rest of the story, and a lamp that came back
    # without its emission could never get it back. None is the right default
    # here precisely because it is what "not declared" already looks like, so
    # silence still reads as silence.
    "enclosure": None,
    "light_source": None,
    # Listed for the same reason as the two above, and pre-emptively: a
    # `scent` outside this map is copied verbatim by the tail loop below, so
    # the None validation fills in for every beat that does not re-declare it
    # would overwrite a standing smell rather than read as silence.
    "scent": None,
}


#: Entity `state` keys that name exertion OF THE MOMENT rather than a
#: configuration -- true for exactly one beat unless the next beat says so
#: again. They EXPIRE on the next merge instead of surviving it.
#:
#: `state` is deliberately open free text and the standing doctrine
#: (`_ENTITY_DEFAULT_FIELDS`, `_merge_entity`) is that silence is never an
#: erasure -- which is right for a held wrench or a transit phase, and
#: exactly wrong for a breath: an omitted momentary key survived FOREVER,
#: and the stale copy is not merely bad prose -- entity state feeds
#: `composer.body_state_percept`, the subject's OWN interoception (source
#: "you"), so each later model call receives the beat-old value as current
#: evidence: a read-back loop, measured at 2,074 byte-identical unchanged
#: runs with `"breath": "caught"` and
#: `"voice_quality": "held_breath_steadying"` stuck verbatim
#: (docs/UNBUILT.md 1.10).
#:
#: Membership is deliberately narrow and evidence-based: a key belongs here
#: only when a beat-old value of it is ALREADY FALSE by being beat-old, and
#: only when nothing downstream reads it as standing state. `posture` and
#: `held_items` stay durable -- sitting stays sitting and a hand keeps what
#: it holds until something says otherwise (the attire doctrine).
#: `activity` is the sharpest remaining read-back key and is NOT here,
#: because the engine currently reads it as load-bearing standing state
#: (movement/portals/perception backstops; pinned by
#: tests/test_body_position.py's never-touched parametrization) -- expiring
#: it means first deciding those readers' contract, which is the
#: reconciliation problem the S3-A8 detector watches, not an expiry rule to
#: slip in beside it.
_TRANSIENT_ENTITY_STATE_KEYS = frozenset({
    "breath", "breathing", "voice_quality", "expression", "gaze",
})

#: The same membership rule stated as a SHAPE rather than a list, because a
#: momentary key is minted freely: `state` is open free text, so a fixed
#: allowlist can only ever name the momentary keys some story already wrote.
#: A name ending in one of these says the value is a PROCESS or a READING --
#: what a body or a part is doing or registering this instant -- and a
#: process is false the moment the beat that held it ends.
#:
#: `_register` is deliberately NOT here: a compound like a till, a ledger or
#: a shift `x_register` is a THING, not a reading, and the family therefore
#: fails open. That is the correct direction to fail: a momentary key that
#: lingers is stale prose the next beat overwrites, while a configuration
#: key wrongly called momentary silently DELETES authored state.
_TRANSIENT_ENTITY_STATE_SUFFIXES = ("_action", "_motion", "_sensation")


def _is_transient_state_key(key) -> bool:
    """Whether one entity-`state` key names a momentary process or reading.

    Calibration, re-measured over all 77 stored scene blobs on 2026-08-25:
    the predicate captures 31 of 1,270 stored key-occurrences under nine
    distinct names -- `gaze` 10, `expression` 10, `voice_quality` 2,
    `breath` 2, and 7 more across five process-suffix keys -- and none of
    the other 370 distinct keys, every one of which is a configuration:
    `power_state`, `lock_status`, `held_items`, `posture`. Twenty-seven of
    those occurrences were newly reachable. The live case is chat 88, where
    a process key set at turn 56 was still standing at turn 67.
    """
    folded = str(key or "").strip().casefold()
    return (folded in _TRANSIENT_ENTITY_STATE_KEYS
            or folded.endswith(_TRANSIENT_ENTITY_STATE_SUFFIXES))


def _merge_entity(entity_id, existing: dict, incoming: dict) -> dict:
    """Merge an incoming entity redeclaration into an already-known entity.

    The exact sibling of _merge_room, and for the same reason: a Director
    updating one entity's pose has no way to echo back the description,
    aliases and interior rooms it did not touch. `entities.update(diff)`
    replaced the whole record instead -- and because validation fills every
    absent field with a schema default first, the replacement looked
    complete. Observed live (Elevator Adventure branch 41) on a pose-only
    diff: "Blue Police Box" (kind vehicle, container, interior_rooms
    ["tardis_interior_001"]) became "Tardis 001", kind object, no interior;
    the registered character "The Doctor" became an object named "The
    Doctor 10". Both then read back corrupted on every later turn.

    So a schema DEFAULT is treated as silence, never as an erasure, and a
    name the validator derived from the key cannot displace a real one.
    Deliberate changes still land: any non-default value wins, and
    genuinely clearing a field goes through remove_entities, not silence.
    """
    merged = dict(existing)

    incoming_name = str(incoming.get("name") or "").strip()
    existing_name = str(existing.get("name") or "").strip()
    if incoming_name and not (
        existing_name
        and is_derived_entity_name(entity_id, incoming_name,
                                   incoming.get("kind"))
    ):
        merged["name"] = incoming_name

    for field, default in _ENTITY_DEFAULT_FIELDS.items():
        if field not in incoming:
            continue
        value = incoming[field]
        if value == default and existing.get(field, default) != default:
            continue  # silence, not an erasure
        merged[field] = value

    # `state` is the live, per-beat half of an entity and is the field a
    # partial diff most often carries alone: merge key-wise so a pose
    # update keeps the transit//link state the same entity depends on.
    incoming_state = incoming.get("state")
    if isinstance(incoming_state, dict):
        state = dict(existing.get("state") or {})
        state.update(incoming_state)
        merged["state"] = state
    elif "state" in incoming:
        merged["state"] = incoming_state

    for key, value in incoming.items():
        if key == "name" or key == "state" or key in _ENTITY_DEFAULT_FIELDS:
            continue
        merged[key] = value

    return merged


def _entity_state_by_alias(entities) -> dict:
    """{folded id/name/alias: that entity's state dict}, for one entity map.

    The same alias folding `_expire_transient_entity_state` matches
    assertions by, hoisted so the prior scene and the incoming diff are read
    through one spelling rule.

    Two records that share an id, name or alias are merged under it, so a
    scene still carrying an id-keyed AND a name-keyed copy of one body makes
    one comparand out of both -- the same duplicate-key hazard
    `_dedup_duplicate_entity_keys` exists to heal, and it runs on `merged`
    rather than on the pre-diff `scene` read here. Merging is the safe
    direction: the comparand can only ever say a value was already standing,
    and the cost of that is a momentary key expiring a beat early.
    """
    out: dict[str, dict] = {}
    for eid, ent in (entities if isinstance(entities, dict) else {}).items():
        if not isinstance(ent, dict):
            continue
        state = ent.get("state")
        if not isinstance(state, dict):
            continue
        for alias in (eid, ent.get("name"), *(ent.get("aliases") or [])):
            alias = str(alias or "").strip().casefold()
            if alias:
                out.setdefault(alias, {}).update(state)
    return out


def _folded_aliases(entity_key, entity) -> list:
    """One entity's id, display name and aliases, casefolded and non-empty."""
    return [a for a in (str(x or "").strip().casefold() for x in
                        (entity_key, (entity or {}).get("name"),
                         *((entity or {}).get("aliases") or []))) if a]


def _expire_transient_entity_state(entities, incoming_entities,
                                   prior_entities=None, expired=None):
    """Drop momentary state keys the incoming diff did not re-assert with a
    changed value; return the echo memory the next merge needs.

    The counterpart of `_merge_entity`'s key-wise state merge: everything
    durable keeps the silence-is-not-erasure doctrine, and the keys
    `_is_transient_state_key` recognises live for exactly the beat that
    asserted them. Runs over EVERY merged entity, not only the ones this diff
    mentions -- an entity the diff is silent about is precisely the one
    whose "running" has gone stale.

    ECHO IS SILENCE. A byte-identical re-emission of a momentary value that
    was ALREADY ASSERTED is the model copying its payload back, not a fresh
    assertion, so it does not count as one. Without that, expiry is
    defeated by the cheapest possible model behaviour: chat 88 turns 53-67,
    where the hand owning `entities` re-emitted the whole state blob
    verbatim nearly every beat and `throat_action` set at turn 56 was still
    standing at turn 67, thirteen beats after the act it named.

    ALREADY ASSERTED, not already STANDING -- and the difference is the
    whole reason this function carries memory. Comparing only against the
    value standing in the scene made the rule oscillate rather than
    subtract: expiry deletes exactly the value it compared to, so the next
    identical echo found nothing standing, re-established the key, and the
    echo after that expired it again. Measured on that form, one diff
    merged six times running gave gaze downcast / gone / downcast / gone /
    downcast / gone -- a momentary key blinking forever, on precisely the
    verbatim-re-emission input the rule was built for. So a value suppressed
    as an echo is remembered (`expired`, returned for the caller to carry on
    the scene) and every later echo of it is silence too.

    The memory lives only as long as the echo run does. A beat that says
    nothing about the key releases it, and the next write of that value is a
    fresh assertion again -- suppression is a reading of THIS payload, never
    a standing ban on a word. An entity the diff drops keeps its memory for
    one more beat and loses it on the next merge, since the rebuild below
    only records bodies still in the scene.

    It is the doctrinal sibling of `_merge_entity`'s "a schema DEFAULT is
    silence", but the analogy is weaker than it looks and is not what
    carries the rule: a default is UNCHOSEN, while an echo was emitted, and
    a model faithfully restating a momentary fact that genuinely has not
    changed is punished by this -- the key stays expired for as long as the
    restatement keeps arriving word for word. That cost is accepted for the
    momentary vocabulary only, where byte-identical across two beats is
    stale by construction, and where a genuinely continuing dynamic has its
    own channel that persists through silence by contract
    (`contact_action_ops`). The measured 13-beat carry is the evidence; the
    analogy is only an echo of it.

    Assertion is matched by id, name and aliases, folded, because a diff may
    key an entity by any of them (`_dedup_duplicate_entity_keys` exists for
    the same reason). Mutates `entities` in place.
    """
    incoming = incoming_entities if isinstance(incoming_entities, dict) else {}
    standing = _entity_state_by_alias(prior_entities)
    remembered = {
        str(alias or "").strip().casefold(): values
        for alias, values in (expired if isinstance(expired, dict)
                              else {}).items()
        if isinstance(values, dict) and str(alias or "").strip()
    }
    asserted: dict[str, set] = {}
    echoed: dict[str, dict] = {}
    for iid, ient in incoming.items():
        if not isinstance(ient, dict):
            continue
        istate = ient.get("state")
        aliases = _folded_aliases(iid, ient)
        keys, echo = set(), {}
        if isinstance(istate, dict):
            for key, value in istate.items():
                # Non-transient keys need no assertion bookkeeping at all --
                # they are never expired -- so only the momentary ones are
                # tested against what this body last had asserted of it:
                # the value standing in the scene, or the one an earlier
                # beat of this same echo run already spent.
                if _is_transient_state_key(key) and any(
                        (key in standing.get(alias, {})
                         and standing[alias][key] == value)
                        or (key in remembered.get(alias, {})
                            and remembered[alias][key] == value)
                        for alias in aliases):
                    echo[key] = value
                    continue
                keys.add(key)
        for alias in aliases:
            asserted.setdefault(alias, set()).update(keys)
            echoed.setdefault(alias, {}).update(echo)
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        state = ent.get("state")
        if not isinstance(state, dict):
            continue
        kept: set = set()
        for alias in _folded_aliases(eid, ent):
            kept |= asserted.get(alias, set())
        for key in [k for k in state
                    if _is_transient_state_key(k) and k not in kept]:
            state.pop(key, None)
    out: dict[str, dict] = {}
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        aliases = _folded_aliases(eid, ent)
        live = ent.get("state") if isinstance(ent.get("state"), dict) else {}
        spent = {}
        for alias in aliases:
            spent.update(echoed.get(alias, {}))
        spent = {k: v for k, v in spent.items()
                 if _is_transient_state_key(k) and k not in live}
        for alias in aliases if spent else ():
            out.setdefault(alias, {}).update(spent)
    return out


def _dedupe_adjacent(edges):
    """Collapse adjacency edges that target the same room, keeping the LAST
    occurrence for each target (matching _merge_room's upsert-by-'to').

    _merge_room already dedupes, but ONLY for a room present in the incoming
    diff. A room the model doesn't re-declare this turn is carried through the
    merge verbatim, so a duplicate 'to' edge introduced once -- e.g. when
    rename-remapping rewrites two edges onto the same target -- otherwise
    persists frozen across every subsequent turn. That leaves a room
    simultaneously walled off from AND open-doored to the same neighbor
    (barrier 'wall' and 'open_door' at once), which makes perception's spatial
    cues incoherent. Deduping every room on every merge heals it. First-seen
    'to' order is preserved; malformed edges (no 'to') pass through untouched."""
    seen, order, extras = {}, [], []
    for edge in edges or []:
        if isinstance(edge, dict) and edge.get("to"):
            if edge["to"] not in seen:
                order.append(edge["to"])
            seen[edge["to"]] = edge  # last wins, matching _merge_room
        else:
            extras.append(edge)
    return [seen[t] for t in order] + extras


def _dedup_duplicate_position_keys(positions, entities, incoming_positions=None):
    """Collapse a position keyed under BOTH an entity's id and its display name
    to one key. Only a genuine duplicate is touched; a lone id-keyed position
    (an object with no name twin) is left alone. When both keys are present the
    FRESH write wins -- the one in this diff's incoming positions -- else the
    display-name key (the convention `room_of` and every character use).
    """
    if not isinstance(positions, dict) or not isinstance(entities, dict):
        return positions
    incoming = incoming_positions if isinstance(incoming_positions, dict) else {}
    for eid, ent in list(entities.items()):
        name = (ent.get("name") or "").strip() if isinstance(ent, dict) else ""
        if not name or name == eid:
            continue
        if eid in positions and name in positions:
            # Prefer whichever key this diff just wrote; default to the name.
            if eid in incoming and name not in incoming:
                positions[name] = positions.pop(eid)
            else:
                positions.pop(eid, None)
    return positions


# Durable structural facts about an entity, as opposed to `state`, which is a
# snapshot of right now. When two records for one entity are collapsed these
# survive from whichever record has them; `state` never merges (see below).
_ENTITY_STRUCTURAL_FIELDS = (
    "kind", "subtype", "name", "description", "aliases", "interior_rooms",
    "portable", "container", "ubiquitous", "parent_entity",
    # The card's authored inside. Durable by the same test as `interior_rooms`
    # beside it, and it has to be listed here or a collapse of an id-keyed and
    # a name-keyed record for one holder -- the shape this corpus produces
    # routinely -- drops the topology silently.
    "interior_spec",
    # What the thing is made of and what it gives off are as durable as what
    # it is -- and were being lost whenever two records for one entity
    # collapsed, which is the other half of the same gap.
    "enclosure", "light_source",
)


def _materialize_interior_places(merged):
    """Mint the interior a standing `mode: interior` record over a body
    entails, then re-derive the three facts that depend on it.

    Runs immediately before every `place_enclosed_bodies` call, because that
    conversion needs the rooms to exist in the SAME merge. The three
    re-derivations are the ones that stand between a minted room and a correct
    one, in the order the merge already runs them: the room's `parent_entity`
    claim becomes the holder's `interior_rooms` index, the index makes the
    body's way in default to `membrane`, and the dock rewrite turns that into
    the actual doorway. Skipping them would leave the occupant behind a
    doorway that does not exist yet -- and `is_sealed_in`, reading the same
    edges at the end of this merge, would start an air countdown on a body
    with a way out.

    All three are documented idempotent, so re-running them mid-merge costs a
    pass and changes nothing when nothing was minted.

    TWO PRODUCERS, ONE SET OF RE-DERIVATIONS. The mint serves a holder with no
    interior at all; `replace_engine_minted_interiors` serves the one that
    already stands on the engine's own unmodified stub, which is what every
    live story needing a chain actually carries (chats 90 and 91, measured
    2026-08-25). Both must be followed by the three passes below -- an early
    return on an empty MINT would skip the dock rewrite after a replacement,
    leaving the occupant behind a doorway that names a room just retired.
    """
    minted = bool(materialize_enclosure_interiors(merged))
    replaced = bool(replace_engine_minted_interiors(merged))
    if not minted and not replaced:
        return False
    sync_entity_interior_rooms(merged)
    infer_body_enclosures(merged)
    apply_transit_dock_edges(merged)
    return True


def _dedup_duplicate_entity_keys(entities, incoming_entities=None):
    """Collapse an entity recorded under BOTH its id and its display name.

    The third instance of one bug. A character legitimately answers to several
    scene keys -- display name, identity.uid, aliases (see
    agents.common.character_scene_keys) -- and the Director keys with whichever
    it reaches for. `positions` survived that because readers try every key and
    duplicates collapse (_dedup_duplicate_position_keys); `attire` was healed
    after a character rendered as wearing nothing while her clothing state still
    described her coat (commit._heal_attire_identity_keys). `entities` had
    neither, and it is the record that says what each body is doing and what it
    is in contact with.

    Observed live: one character held two entity records -- `char_9f13c0a4...`
    frozen at the beat it was created, and `Bramwell` written every beat
    since. Both claimed to describe her, so "who is in contact with whom" had
    two contradictory answers at once, one of them arbitrarily old, and every
    reader that walks entities saw the same person twice.

    Unlike attire, `state` is NOT merged: a wardrobe accumulates, but contact
    and posture describe a single instant, so folding a stale snapshot into a
    fresh one is what manufactures the contradiction. The fresh record's state
    wins whole. Only the structural fields above are rescued from the loser, so
    collapsing can never drop a vehicle's interior_rooms or an entity's aliases.
    """
    if not isinstance(entities, dict):
        return entities
    incoming = incoming_entities if isinstance(incoming_entities, dict) else {}

    for eid, ent in list(entities.items()):
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or "").strip()
        if not name or name == eid or name not in entities:
            continue
        twin = entities.get(name)
        if not isinstance(twin, dict) or twin is ent:
            continue

        # The display name is the surviving KEY either way (the convention every
        # reader uses); which record's content survives depends on which one
        # this diff just wrote.
        if eid in incoming and name not in incoming:
            winner, loser = ent, twin
        else:
            winner, loser = twin, ent

        merged = dict(winner)
        for field in _ENTITY_STRUCTURAL_FIELDS:
            if field not in merged or merged.get(field) in (None, "", [], {}):
                if loser.get(field) not in (None, "", [], {}):
                    merged[field] = loser[field]
        merged["name"] = name

        entities[name] = merged
        entities.pop(eid, None)

    return entities


def _shield_standing_bearings(prior_rooms, incoming_rooms):
    """Refuse a ONE-SIDED re-bearing of a doorway both sides already agree on.

    A doorway whose two declared sides carry opposite-consistent bearings is
    a standing agreement -- usually authored world geometry. A model
    re-declaring one room routinely emits a wrong `dir` for an edge it is
    only mentioning in passing, and letting that single claim through
    destroys the agreement twice over: normalize_scene_bearings sees the
    contradiction and drops BOTH sides ("dropped rather than guessed"), and
    its reciprocal inference then faithfully rebuilds whatever wrong bearing
    gets asserted next. Measured live (maze arm): five doorway pairs carried
    internally-consistent bearings that were geometrically FALSE, and a
    runner was walked north on a declared "west" -- model noise laundered
    into scene truth by the engine's own repair machinery.

    So: an incoming `dir` that contradicts a standing opposite-consistent
    pair is stripped (the edge itself still merges -- barrier and distance
    changes land) unless the SAME diff re-declares the reciprocal side with
    the matching opposite. Changing settled geometry takes a two-sided
    declaration; a one-sided one falls back to the incumbent. Returns a
    sanitized copy; never mutates the caller's diff.
    """
    if not isinstance(incoming_rooms, dict) or not isinstance(
            prior_rooms, dict):
        return incoming_rooms

    def _edge_dir(rooms, room_id, to_id):
        room = rooms.get(room_id)
        if not isinstance(room, dict):
            return None
        for e in room.get("adjacent") or []:
            if isinstance(e, dict) and str(e.get("to")) == str(to_id):
                return normalize_bearing(e.get("dir"))
        return None

    out = {}
    for room_id, room in incoming_rooms.items():
        if not isinstance(room, dict) or not room.get("adjacent"):
            out[room_id] = room
            continue
        edges = []
        touched = False
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                edges.append(edge)
                continue
            new_dir = normalize_bearing(edge.get("dir"))
            to_id = edge["to"]
            if new_dir:
                fwd = _edge_dir(prior_rooms, room_id, to_id)
                back = _edge_dir(prior_rooms, to_id, room_id)
                standing = (fwd and back
                            and opposite_bearing(fwd) == back)
                if standing and new_dir != fwd:
                    recip = _edge_dir(incoming_rooms, to_id, room_id)
                    if recip != opposite_bearing(new_dir):
                        edge = {k: v for k, v in edge.items() if k != "dir"}
                        touched = True
            edges.append(edge)
        out[room_id] = {**room, "adjacent": edges} if touched else room
    return out


def _shield_standing_passage(prior_rooms, incoming_rooms, add_warning=None):
    """Refuse a ONE-SIDED sealing of a doorway that is standing open.

    The mirror of `_shield_standing_bearings`, and it exists because the same
    thing happened to `barrier` that had already happened to `dir`. Live, chat
    63 turn 165, across five consecutive rerolls: `mapping_stage` authored the
    stair between the shrine's two floors as `open_shoji` every single time,
    and `director_resolve` then re-declared the RETURN edge alone as `wall` --
    leaving one direction passable, the other sealed, and no route between a
    hall and its own upstairs.

    A barrier is a property of the doorway, not of the side you stand on. So a
    one-sided downgrade from passable to `wall` falls back to the incumbent
    unless the SAME diff seals the reciprocal side too. Sealing a passage takes
    a two-sided declaration; everything else about the edge still merges, and a
    room the diff opens UP is never blocked -- this only refuses the close.
    """
    if not isinstance(incoming_rooms, dict) or not isinstance(prior_rooms, dict):
        return incoming_rooms

    def _edge_barrier(rooms, room_id, to_id):
        room = rooms.get(room_id)
        if not isinstance(room, dict):
            return None
        for e in room.get("adjacent") or []:
            if isinstance(e, dict) and str(e.get("to")) == str(to_id):
                return normalize_barrier(e.get("barrier"))
        return None

    out = {}
    for room_id, room in incoming_rooms.items():
        if not isinstance(room, dict) or not room.get("adjacent"):
            out[room_id] = room
            continue
        edges = []
        touched = False
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                edges.append(edge)
                continue
            to_id = edge["to"]
            new_barrier = normalize_barrier(edge.get("barrier"))
            if new_barrier == "wall":
                fwd = _edge_barrier(prior_rooms, room_id, to_id)
                back = _edge_barrier(prior_rooms, to_id, room_id)
                standing = (fwd in _PASSABLE_BARRIERS
                            or back in _PASSABLE_BARRIERS)
                recip = _edge_barrier(incoming_rooms, to_id, room_id)
                if standing and recip != "wall":
                    edge = {k: v for k, v in edge.items() if k != "barrier"}
                    touched = True
                    if add_warning:
                        add_warning(
                            "kept the passage %s -> %s open: it was sealed "
                            "from one side only, and the other side still "
                            "reads %r" % (room_id, to_id,
                                          recip or fwd or back))
            edges.append(edge)
        out[room_id] = {**room, "adjacent": edges} if touched else room
    return out


def _shield_minted_edges(prior_rooms, incoming_rooms, add_warning=None):
    """Care at the MINTING of an edge, to match the care taken merging one.

    The upsert-with-silence doctrine above is scrupulous about not ERASING an
    edge's fields, and that scruple was entirely absent from creating one: a
    previously unseen edge was accepted verbatim, so a model asserting an
    adjacency invented a doorway with no check at all -- measured as
    `r0204 <-> r0303`, a diagonal in a grid maze that is impossible by
    construction, standing in the world model for hundreds of turns and
    walked as a real doorway (docs/UNBUILT.md 1.2). One check is decidable
    everywhere and lands here; a NEW edge is one with no standing declaration
    in either direction, so a re-declaration of a known doorway from its
    other side is untouched.

    RECIPROCITY OF UNSEALING. `_shield_standing_passage` above establishes
    that sealing a passage takes a two-sided declaration. The same holds in
    reverse, through a hole it could not see: with only `B -> A: wall`
    standing, a model minting a fresh `A -> B: open` created passage through
    the wall one-sidedly, because the walks are undirected and cross an edge
    either side declares. So a new PASSABLE edge whose standing reciprocal
    reads `wall` is refused unless the same diff re-declares that reciprocal
    as passable too. Scoped to `wall` exactly as the sealing shield is: a
    standing `closed_door` reciprocal stays one-sidedly openable (opening a
    door is an ordinary act, declared from whichever side the actor stands),
    and a standing `window`/`one_way_window` reciprocal is left to the basis
    work this deliberately does not attempt.

    What this does NOT check, on the record. GEOMETRY: the model has no
    coordinates, so a general scene cannot say what a grid maze could.
    BASIS: whether anything witnessed, walked or authored the doorway --
    that needs a stated basis on the edge itself, a schema-and-prompt change
    across the mapping and spatial specialists. And EXISTENCE of the target
    room: a dangling edge is a tolerated forward reference in this engine
    (`neighbor_map`'s walks tolerate it by design, and the west-wing live
    flow pinned at tests/test_spatial.py's redeclaration test mints the
    corridor's edge before the room), so refusing it would break a real
    mapping flow -- an existence rule has to wait for room-and-edge minting
    to become atomic. Refusing to guess any of the three is why this shield
    is small. Returns a sanitized copy; never mutates the caller's diff.
    """
    if not isinstance(incoming_rooms, dict) or not isinstance(
            prior_rooms, dict):
        return incoming_rooms

    def _edge_barrier(rooms, room_id, to_id):
        room = rooms.get(room_id)
        if not isinstance(room, dict):
            return None
        for e in room.get("adjacent") or []:
            if isinstance(e, dict) and str(e.get("to")) == str(to_id):
                return normalize_barrier(e.get("barrier"))
        return None

    out = {}
    for room_id, room in incoming_rooms.items():
        if not isinstance(room, dict) or not room.get("adjacent"):
            out[room_id] = room
            continue
        edges = []
        touched = False
        for edge in room.get("adjacent") or []:
            if not isinstance(edge, dict) or not edge.get("to"):
                edges.append(edge)
                continue
            to_id = str(edge["to"])
            if _edge_barrier(prior_rooms, room_id, to_id) is not None:
                # A re-declaration of an edge this side already holds:
                # upsert territory, ruled by the shields above.
                edges.append(edge)
                continue
            back = _edge_barrier(prior_rooms, to_id, room_id)
            if back is None:
                # A brand-new PAIR: no declaration stands in either
                # direction, so there is nothing here to contradict -- this
                # is the case that wants a BASIS, deliberately not guessed
                # (see the docstring).
                edges.append(edge)
                continue
            # The pair is known from the OTHER side only, and this diff is
            # minting the near side.
            recip = _edge_barrier(incoming_rooms, to_id, room_id)
            if back == "wall" \
                    and normalize_barrier(edge.get("barrier")) \
                    in _PASSABLE_BARRIERS \
                    and recip not in _PASSABLE_BARRIERS:
                touched = True
                if add_warning:
                    add_warning(
                        "refused a new passable edge %s -> %s: the standing "
                        "reciprocal reads wall, and unsealing a passage "
                        "takes a two-sided declaration" % (room_id, to_id))
                continue
            edges.append(edge)
        out[room_id] = {**room, "adjacent": edges} if touched else room
    return out


def connect_orphan_new_rooms(scene: dict, prev_scene: dict) -> list:
    """A room created this turn must be reachable from somewhere.

    Adjacency resolves BOTH ways, so a room with an empty `adjacent` is fine as
    long as something points AT it -- which is why `alley_room` works while
    carrying no edges of its own. The failure is the stronger one: a room no
    edge reaches in EITHER direction. `spatial_rel` answers `separated`/`far`
    for every pair involving it, so it is an island, and the only thing its
    occupants can perceive is whatever happens to be standing in it with them.

    Live (chat 58): `northern_plaza` was minted with `adjacent: []` and nothing
    pointing at it. The player stepped out of the TARDIS into a described city
    plaza -- shuttered buildings, dripping awnings, an alley the Dalek was
    grinding out of -- and her view could only offer her the police box she had
    just left, because the dock edge was the single edge the map admitted.

    Applied ONLY to rooms that are new in this merge, and only at the moment
    they are created, because that is the one point where the engine still has
    the context to place them: where the bodies were standing immediately
    before. After the fact there is nothing left to infer from, which is why
    this cannot be a periodic repair pass.

    Interiors are skipped: a `parent_entity` room's doorway is DERIVED by
    `apply_transit_dock_edges` (which runs straight after this), and a sealed
    or in-transit hull is severed from the world on purpose.

    Mutates `scene` in place. Returns [(room_id, attached_to), ...].
    """
    rooms = scene.get("rooms")
    if not isinstance(rooms, dict) or len(rooms) < 2:
        return []
    known = set((prev_scene or {}).get("rooms") or {})
    fresh = [rid for rid in rooms if rid not in known]
    if not fresh:
        return []

    reached = set()
    for rid, room in rooms.items():
        for edge in (room.get("adjacent") or []):
            if isinstance(edge, dict) and edge.get("to"):
                reached.add(str(edge["to"]))
                reached.add(str(rid))

    # Where the bodies were standing BEFORE this turn's diff -- the scene's
    # centre of gravity, and the only honest guess available.
    counts = {}
    for room_id in ((prev_scene or {}).get("positions") or {}).values():
        if room_id and room_id in rooms:
            counts[room_id] = counts.get(room_id, 0) + 1
    attached = []
    for rid in fresh:
        room = rooms[rid]
        if not isinstance(room, dict) or room.get("parent_entity"):
            continue
        if rid in reached:
            continue
        anchor = max((r for r in counts if r != rid),
                     key=counts.get, default=None)
        if anchor is None:
            anchor = next((r for r in rooms if r != rid), None)
        if not anchor:
            continue
        room.setdefault("adjacent", []).append(
            {"to": anchor, "barrier": "open", "distance": "near"})
        reached.add(rid)
        reached.add(anchor)
        attached.append((rid, anchor))
    return attached


def _position_key(scene: dict, name) -> Optional[str]:
    """Canonical existing position key for an actor label, case-insensitive."""
    label = str(name or "").strip()
    if not label:
        return None
    positions = scene.get("positions") or {}
    if label in positions:
        return label
    folded = label.casefold()
    return next(
        (key for key in positions
         if str(key).strip().casefold() == folded),
        None,
    )


def apply_following_ops(scene: dict, operations) -> dict:
    """Apply voluntary durable follower -> target relations to ``scene``.

    Following records intention and ordinary travel affiliation; it never
    changes a position here. Movement follow-through is deliberately owned by
    the Director, where pace, barriers, and actor decisions are available.
    This function only maintains the durable ledger used equally by mid-turn
    perception merges, commit, checkpoints, branches, and rerolls.
    """
    following = scene.get("following")
    if not isinstance(following, dict):
        following = scene["following"] = {}

    for raw in operations or []:
        if not isinstance(raw, dict):
            continue
        op = str(raw.get("op") or "").strip().casefold()
        follower = _position_key(scene, raw.get("follower"))
        if follower is None:
            continue
        if op == "stop":
            for key in list(following):
                if str(key).strip().casefold() == follower.casefold():
                    following.pop(key, None)
            continue
        if op != "start":
            continue
        target = _position_key(scene, raw.get("target"))
        if target is None or target.casefold() == follower.casefold():
            continue

        # A follows B follows A is not travel; it is an ownerless cycle. Longer
        # cycles are rejected on the same terms. Case-tolerant because older
        # scenes can carry human-authored labels.
        cursor = target
        visited = {follower.casefold()}
        cyclic = False
        while cursor:
            folded = cursor.casefold()
            if folded in visited:
                cyclic = True
                break
            visited.add(folded)
            rec = next(
                (value for key, value in following.items()
                 if str(key).strip().casefold() == folded
                 and isinstance(value, dict)),
                None,
            )
            cursor = _position_key(scene, (rec or {}).get("target"))
        if cyclic:
            continue

        # Replace a case-variant/old target in place; one body follows at most
        # one target at a time.
        for key in list(following):
            if str(key).strip().casefold() == follower.casefold():
                following.pop(key, None)
        following[follower] = {
            "target": target,
            "since_turn": raw.get("turn"),
            "reason": str(raw.get("reason") or "").strip(),
        }

    # A departed/deleted actor cannot remain in the travel ledger. Separation
    # alone does NOT clear it: a follower left behind by a sprint may still be
    # trying to catch up and decides that on their next beat.
    positioned = {
        str(key).strip().casefold() for key in (scene.get("positions") or {})
    }
    for follower, rec in list(following.items()):
        target = str((rec or {}).get("target") or "").strip().casefold() \
            if isinstance(rec, dict) else ""
        if str(follower).strip().casefold() not in positioned \
                or target not in positioned:
            following.pop(follower, None)
    return scene


def merge_scene_with_diff(
    scene: dict,
    diff: dict | None,
    *,
    contact_report=None,
    substance_report=None,
    sleeping=(),
    clock_seconds=None,
    crossing_report=None,
) -> dict:
    """`clock_seconds` is where the STORY clock stands at the end of this
    beat, and it is what lets a passage carry its occupants onward (see
    `advance_room_transits`). None is a hard no-op for that pass: a caller
    merging for a purpose other than living a beat -- a paradox probe, a
    Director preview, a migration re-merge -- gets exactly the scene this
    function produced before crossings existed. `crossing_report` collects
    Director-facing notes about what a passage did, and what it could not do
    for want of a fact only the Director can supply."""
    diff = diff or {}
    # A scene is a nested mutable structure.  A shallow copy allowed
    # downstream normalization and deterministic backstops (zone stamping,
    # adjacency edits, overlays, attire) to mutate the caller's supposedly
    # pre-diff scene through shared child dictionaries/lists.  That made
    # before/after comparisons order-dependent and could contaminate rollback
    # preparation.  Scene merges are correctness boundaries, so pay the small
    # cost of a real copy here.
    merged = copy.deepcopy(scene)

    merged["rooms"] = dict(merged.get("rooms") or {})
    merged["entities"] = dict(merged.get("entities") or {})
    merged["positions"] = dict(merged.get("positions") or {})

    _prior_rooms = (merged["rooms"]
                    if isinstance(merged.get("rooms"), dict) else {})
    incoming_rooms = _shield_standing_bearings(
        _prior_rooms, diff.get("rooms") or {})
    incoming_rooms = _shield_standing_passage(
        _prior_rooms, incoming_rooms)
    incoming_rooms = _shield_minted_edges(
        _prior_rooms, incoming_rooms)
    incoming_entities = diff.get("entities") or {}
    incoming_positions = diff.get("positions") or {}
    incoming_stations = diff.get("stations") or {}
    incoming_poses = diff.get("poses") or {}

    if isinstance(incoming_rooms, dict):
        for room_id, incoming_room in incoming_rooms.items():
            if not isinstance(incoming_room, dict):
                continue
            existing_room = merged["rooms"].get(room_id)
            merged["rooms"][room_id] = (
                _merge_room(existing_room, incoming_room, room_id)
                if isinstance(existing_room, dict)
                else incoming_room
            )

    if isinstance(incoming_entities, dict):
        for entity_id, incoming_entity in incoming_entities.items():
            existing_entity = merged["entities"].get(entity_id)
            merged["entities"][entity_id] = (
                _merge_entity(entity_id, existing_entity, incoming_entity)
                if isinstance(existing_entity, dict)
                and isinstance(incoming_entity, dict)
                else incoming_entity
            )

    # An entity keyed by its id in one beat and by its display name in the next
    # leaves TWO records for one body -- each with its own posture and contact,
    # one of them frozen at whatever beat it was last written. Collapse before
    # anything reads them (positions dedup below reads entities, and every
    # perception/narration reader walks this dict).
    _dedup_duplicate_entity_keys(merged["entities"], incoming_entities)

    # A FIELD NAME can never key an entity. A sibling field written one
    # nesting level too deep (or its validation debris) arrives in the
    # entities map keyed `remove_entities`, `notes`, ... -- chat 80's scene
    # carried six such "entities", each a verbatim copy of the Interview
    # Chair. The hoist in schemas.preprocess_llm_output now stops new ones at
    # validation; this floor refuses whatever still arrives AND heals a scene
    # already carrying them, since the merged blob is what commits -- the
    # same heal-on-load shape commit._fold_duplicate_presences uses, so a
    # live story needs no migration.
    for _bad in [k for k in merged["entities"] if k in NON_ENTITY_FIELD_KEYS]:
        merged["entities"].pop(_bad, None)

    # Momentary state expires unless this diff re-asserted it WITH A CHANGED
    # VALUE -- the one deliberate exception to key-wise state merging; see
    # `_TRANSIENT_ENTITY_STATE_KEYS` for the read-back loop it closes. The
    # pre-diff entity map is the echo comparand, and reading it here is safe
    # because `merged = copy.deepcopy(scene)` above leaves the input pristine.
    #
    # `expired_entity_state` is the second half of that comparand: the
    # momentary values THIS body already spent, without which a repeated
    # verbatim echo makes the key blink present/absent forever instead of
    # expiring once. It is written back only while an echo run is live -- a
    # scene whose bodies stop echoing carries no such key at all, which is
    # every one of the 77 stored blobs measured 2026-08-25. Carried inside
    # the scene blob because the merge is a pure function with nowhere else
    # to keep it; it holds nothing durable, nothing an id can dangle from,
    # and nothing a reader of the world needs, so archive, checkpoint and
    # branch carry it the way they carry the rest of the blob.
    _echo_memory = _expire_transient_entity_state(
        merged["entities"], incoming_entities,
        prior_entities=(scene or {}).get("entities") or {},
        expired=(scene or {}).get("expired_entity_state") or {})
    if _echo_memory:
        merged["expired_entity_state"] = _echo_memory
    else:
        merged.pop("expired_entity_state", None)

    if isinstance(incoming_positions, dict):
        merged["positions"].update(incoming_positions)
    # The same refusal for the position ledger: a field name is not a body,
    # so it cannot stand in a room. After the update so an incoming key is
    # refused too, before the dedup below reads the ledger.
    for _bad in [k for k in merged["positions"] if k in NON_ENTITY_FIELD_KEYS]:
        merged["positions"].pop(_bad, None)
    # DW-4: an entity can end up in `positions` under BOTH its id key and its
    # display-name key -- e.g. an auto-created backstory person seeded with an
    # id-keyed position (`karen_marsh`) while director_resolve moves it by name
    # (`Karen Marsh`). The blind update() above then leaves BOTH, so the entity
    # is co-present in two rooms and perception's co-present set is corrupted.
    # Collapse only a genuine id+name DUPLICATE -- a lone id-keyed object
    # position (tardis, a dropped item) has no name-key twin and is untouched.
    _dedup_duplicate_position_keys(
        merged["positions"], merged["entities"], incoming_positions)

    # A DECLARED POSITION IS A DECLARED ACT. Once a body that has taken
    # another body inside is a PLACE, two derivations stand between a
    # declared exit and the scene -- the carry derivation below, and the
    # loop `derive_containment_from_contacts` closes with
    # `place_enclosed_bodies` further down, which mints a record off the
    # surviving interior contact and reads the body straight back in.
    # Measured: without this, a diff moving an occupant to the exterior room
    # came back with them inside again, every beat, forever. Runs BEFORE this
    # beat's own containment and contact declarations, so a beat that
    # re-asserts the enclosure keeps it and only the STANDING ledger yields;
    # scoped to a holder that HAS interior rooms, so the carry form (a body
    # cannot walk out of a pocket) is untouched.
    release_declared_departures(merged, incoming_positions)

    # Stations (within-room position) are a sibling of positions, merged per
    # entity so a diff touching only `at` keeps the entity's `near` list, and
    # vice versa. Hygiene (phantom-anchor blanking, non-colocated pruning,
    # symmetrization) runs below via normalize_scene_stations.
    if isinstance(incoming_stations, dict) and incoming_stations:
        merged["stations"] = dict(merged.get("stations") or {})
        for name, st in incoming_stations.items():
            if isinstance(st, dict):
                cur = dict(merged["stations"].get(name) or {})
                cur.update(st)
                merged["stations"][name] = cur
    apply_pose_diff(merged, incoming_poses)

    for removal in diff.get("remove_adjacent") or []:
        if not isinstance(removal, dict):
            continue
        room = merged["rooms"].get(removal.get("room"))
        target = removal.get("to")
        if not isinstance(room, dict) or not target:
            continue
        room["adjacent"] = [
            edge for edge in (room.get("adjacent") or [])
            if not (isinstance(edge, dict) and edge.get("to") == target)
        ]

    for entity_id in diff.get("remove_entities") or []:
        entity = merged["entities"].pop(entity_id, None)

        if not entity:
            continue

        names = {
            entity_id,
            str(entity.get("name") or ""),
            *(entity.get("aliases") or []),
        }

        for name in names:
            if name:
                merged["positions"].pop(name, None)
        folded_names = {str(name).strip().casefold() for name in names if name}
        merged["poses"] = {
            name: pose for name, pose in (merged.get("poses") or {}).items()
            if str(name).strip().casefold() not in folded_names
        }
        for pose in (merged.get("poses") or {}).values():
            if isinstance(pose, dict) and str(
                    pose.get("relative_to") or "").strip().casefold() in folded_names:
                pose["relative_to"] = ""
                pose["relation"] = ""
                pose["constraint"] = ""
        merged["substances"] = [
            record for record in (merged.get("substances") or [])
            if not isinstance(record, dict)
            or str(record.get("target") or "").strip().casefold()
            not in folded_names
        ]
        # A body that has left the scene is crossing nothing.
        if isinstance(merged.get("room_since"), dict):
            merged["room_since"] = {
                name: stamp
                for name, stamp in merged["room_since"].items()
                if str(name).strip().casefold() not in folded_names
            }
            if not merged["room_since"]:
                merged.pop("room_since", None)

    occupied_rooms = set(merged["positions"].values())

    for room_id in diff.get("remove_rooms") or []:
        if room_id in occupied_rooms:
            continue
        merged["rooms"].pop(room_id, None)
        merged["substances"] = [
            record for record in (merged.get("substances") or [])
            if not isinstance(record, dict)
            or str(record.get("target") or "") != str(room_id)
        ]

    # A room that names a parent entity IS that entity's interior, in both of
    # the places the engine writes that fact down. Runs first of the three,
    # because the enclosure default below reads the index this maintains and
    # would otherwise leave a declared body interior see-through. Body-scoped,
    # like that default: the index also gates a Director specialist and
    # protects rooms from pruning, so deriving it for the vehicles and lift
    # cars nobody had indexed would be a silent behaviour change in 13 of the
    # author's chats rather than the repair it looks like.
    sync_entity_interior_rooms(merged)
    # A body's interior is opaque whether or not anyone declared it so. Runs
    # BEFORE the dock-edge rewrite, which reads `enclosure` to pick the
    # doorway's barrier.
    infer_body_enclosures(merged)

    # Derived dock/portal edges are a function of the merged scene, not an
    # authored fact -- recompute them here so every consumer of a merge
    # (commit preparation, perception's mid-turn merges) sees the same
    # correct doorways. Runs before barrier normalization, which then
    # canonicalizes whatever the rewrite emitted.
    # A room minted this turn that no edge reaches is an island: every pair
    # involving it answers `separated`/`far`, so its occupants can perceive
    # nothing but each other. Runs BEFORE the dock rewrite, which owns
    # interiors and is left to derive those on its own.
    connect_orphan_new_rooms(merged, scene)

    apply_transit_dock_edges(merged)

    # Collapse duplicate same-target adjacency edges across EVERY room, not
    # just the ones re-declared this turn -- otherwise a duplicate frozen into
    # an untouched room (a neighbor that is both walled and open-doored) leaks
    # incoherent spatial cues into perception forever. See _dedupe_adjacent.
    for room in merged["rooms"].values():
        if isinstance(room, dict) and room.get("adjacent"):
            room["adjacent"] = _dedupe_adjacent(room["adjacent"])

    normalize_scene_barriers(merged)
    # Optional compass bearings on edges: canonicalize each `dir` and reconcile
    # reciprocals so either room can derive a consistent left/right. Runs after
    # dedupe (so only surviving edges are reconciled) and barrier normalization.
    normalize_scene_bearings(merged)
    # Station hygiene moved to the end of the merge, beside contact hygiene:
    # it has to run after `derive_contained_positions`, or a carried body keeps
    # the anchor it was standing at while its carrier walks off with it.
    # Body position tracking: apply this beat's contact ops, then prune every
    # contact that positions no longer permit. Runs LAST, after positions are
    # final, which is what makes walking away end a hold with nothing for the
    # Director to remember.
    # Lift any contact the Director wrote into an entity's own state (the shape
    # that predates contacts, and the one a model still reaches for) before the
    # ops, so both paths land in one place and one truth survives.
    contacts_from_entity_state(merged)
    # The key always exists after a merge, empty or not: a reader that has to
    # ask whether contact tracking is "on" for this scene is a reader that will
    # eventually forget to.
    merged.setdefault("contacts", [])
    merged.setdefault("contact_actions", [])

    # Scale FIRST, and the contacts it invalidates with it -- before this
    # beat's contact ops, not after. A size change cancels the holds that were
    # standing when it happened; the Director is then expected to re-establish
    # whatever the new geometry allows IN THE SAME BEAT, and those ops must
    # survive. Cancelling after them would wipe exactly the correct behaviour.
    incoming_scales = diff.get("scales")
    previous_scales = dict(merged.get("scales") or {})
    if isinstance(incoming_scales, dict) and incoming_scales:
        scales = dict(previous_scales)
        for name, raw in incoming_scales.items():
            label = str(name or "").strip()
            if not label:
                continue
            factor = clamp_scale(raw)
            # An explicit 1.0 (or an unusable value) means "back to normal";
            # normalize_scene_scales drops it, which is the same thing.
            scales[label] = factor if factor is not None else 1.0
        merged["scales"] = scales
    merged.setdefault("scales", {})
    normalize_scene_scales(merged)
    # The return value is for callers/tests; nothing is stashed in the scene,
    # which is saved verbatim and must not accumulate scratch keys.
    contacts_broken_by_scale_change(merged, previous_scales)
    # ...and the pose relations that were true at the old geometry, for the
    # same reason and by the same measure. THIS BEAT'S incoming poses are
    # exempt: `apply_pose_diff` has already run, so a Director re-declaring
    # the arrangement the new size permits must survive its own beat --
    # the ordering the contact cancellation avoids by running before this
    # beat's ops.
    poses_broken_by_scale_change(merged, previous_scales, diff.get("poses"))

    # Containment. Declared as {subject: {"in": holder, "mode": ...}}, with a
    # null/empty value releasing -- the same shape positions uses, because a
    # body is in exactly one container at a time.
    merged.setdefault("contained", {})
    # A size change releases containment for the same reason it breaks a hold:
    # someone restored to full height is not still in the coat pocket. Runs
    # BEFORE this beat's own containment declarations, so a Director that
    # re-declares the arrangement as the thing it now is keeps it -- the same
    # ordering the contact cancellation needs, and for the same reason.
    containment_broken_by_scale_change(merged, previous_scales)
    incoming_contained = diff.get("containment")
    if isinstance(incoming_contained, dict):
        for subject, raw in incoming_contained.items():
            label = str(subject or "").strip()
            if not label:
                continue
            record = _clean_containment(raw, label) if raw else None
            if record is None:
                # Released: out of the pocket, off the shoulder, out of the jar.
                for key in [k for k in merged["contained"]
                            if str(k).strip().casefold() == label.casefold()]:
                    merged["contained"].pop(key, None)
            else:
                merged["contained"][label] = record
    # One spelling per being, BEFORE anything resolves a subject against
    # another ledger. A containment record naming an entity id and a positions
    # map keyed by the display name are the same fact written twice, and every
    # lookup between them fails silently until they agree.
    # A one-way window's direction is written DOWN while it is still
    # knowable, so the next beat's ordinary both-sides redeclaration agrees
    # with it instead of cancelling it (`stamp_sight_direction`).
    stamp_sight_direction(merged)
    normalize_scene_subjects(merged)
    # A THING THAT WAS MOVED IS SOMEWHERE. The hand that mints objects owns
    # `entities` and cannot write `positions` at all, so what it knows about
    # where a thing ended up is written into `inventory_ops` -- a ledger that
    # had no reader anywhere in persist/ or world/ until this call. Derived
    # here, AFTER subject canonicalisation so the endpoints resolve against one
    # spelling per being, and BEFORE containment hygiene so a carrier relation
    # this derives satisfies the same cycle/known-container rules a declared
    # one does and reaches `derive_contained_positions` below like any other.
    # Yields to any position or containment this beat's diff declared by name.
    derive_inventory_placements(
        merged, diff.get("inventory_ops"),
        declared=(set(incoming_positions or {})
                  | set(diff.get("containment") or {})))
    # ...AND A THING THAT WAS NEVER MOVED IS SOMEWHERE TOO. The transfer
    # ledger answers only for a beat that wrote one; the larger class is a
    # thing minted with no transfer at all, which the same ownership split
    # leaves with no room forever (measured: every minted entity of the
    # audited 15-beat run, and of the two runs before it, committed with
    # `room: None`). Placed from who handled it and where it was set down --
    # the ledgers the hands that own THOSE channels did fill. Runs
    # immediately after the transfer derivation and yields to it, and to the
    # same `declared` subtraction: an explicit write outranks both.
    derive_minted_entity_placements(
        merged, diff.get("entities"),
        contact_ops=diff.get("contact_ops"),
        inventory_ops=diff.get("inventory_ops"),
        declared=(set(incoming_positions or {})
                  | set(diff.get("containment") or {})))
    normalize_scene_containment(merged)
    # ...and a body that has taken another one inside HAS an inside, whether or
    # not any model remembered to author it. The floor mints one room from the
    # record itself; the holder's card mints the stations it declares. Runs
    # before the conversion below, which does nothing for a holder with no
    # interior rooms -- which was every holder on disk.
    _materialize_interior_places(merged)
    # A BODY THAT HAS TAKEN ANOTHER BODY INSIDE IS A PLACE, so an occupant of
    # one stands in a room rather than deriving their holder's. Runs BEFORE
    # the derivation below, which would otherwise drag them straight back out
    # to the holder's own exterior room -- the measured chat 88 state, where
    # both bodies shared one room for fifteen consecutive audited turns. What
    # reaches this line now always HAS rooms, because the mint above put them
    # there: re-merging all 80 of the author's stored scene rows with an empty
    # diff gives a byte-identical result to main for 76 of them, and the four
    # that differ -- chats 86, 87, 88, 89 -- are this defect healing.
    place_enclosed_bodies(merged)
    # Derived LAST among position writes: whatever else this beat did to
    # positions, a carried body ends up where its carrier is.
    derive_contained_positions(merged)
    # ...and a position that names an ENTITY rather than a room is repaired
    # after that, so a real containment record always wins over the guess.
    repair_entity_positions(merged)
    # A bodiless voice is not standing anywhere; a position on one is a
    # category error that no author can currently delete by hand.
    prune_bodiless_positions(merged)

    # Durable travel affiliation. This changes only the relation ledger;
    # position follow-through already ran at Director resolution so perception
    # and commit merge the exact same destinations.
    apply_following_ops(merged, diff.get("following_ops"))

    # Non-discrete matter is located while onset contact still stands.  That
    # ordering is causal: a release can occur through an interior relation and
    # the bodies can withdraw later in the same beat.  Deriving after contact
    # removals would erase the route that established the destination.
    apply_substance_ops(merged, diff.get("substance_ops"),
                        report=substance_report)

    _contacts_before_ops = copy.deepcopy(merged.get("contacts") or [])
    apply_contact_ops(merged, diff.get("contact_ops"),
                      report=contact_report)
    # BEFORE contact hygiene, and that is the whole of it. A beat that names
    # a region of an enclosure its inside has no room for has DECLARED a
    # station, and `_restation_interior_contact` -- one line below, inside
    # `normalize_scene_contacts` -- re-derives `target_interior` from the
    # room the occupant currently stands in. So the newly named region
    # survives for exactly the span between these two calls, and a `cross`
    # op naming anything the world does not already contain was erased here
    # every beat, silently. Chat 89 turn 62 emitted a crossing into the
    # station its occupant was already in for that reason.
    materialize_named_stations(
        merged, prior_positions=(scene or {}).get("positions"))
    normalize_scene_contacts(merged)

    # Contact actions ride standing contacts: apply AFTER contacts are settled
    # so the contact_ref pointers have something to point at, and BEFORE stations
    # are derived (a held hand is not derived from an action).
    apply_contact_action_ops(merged, diff.get("contact_action_ops"))

    # AFTER contacts are settled, and it has to be this way round. Contact
    # normalisation reads `contained` to decide which side of an interior
    # relation encloses the other (`_contained_inversion`), so containment is
    # normalised first at the top of this merge; deriving the other direction
    # here rather than there is what keeps that from being a cycle. The gap
    # this fills is a beat that expressed an enclosure ONLY as a contact --
    # containment then stayed empty and every sight gate answered from it.
    if derive_containment_from_contacts(merged):
        # Re-run the hygiene the new records have to satisfy (a container that
        # has left the scene, a cycle), then put the enclosed body where its
        # container is -- both already ran, above, before these existed.
        normalize_scene_containment(merged)
        # NOT OPTIONAL, and the measurement is why. A scene whose only
        # enclosure evidence is a standing interior CONTACT stores
        # `contained: {}` and mints its record right here -- chats 86 and 87,
        # both of them, measured 2026-08-25. A producer at the first call site
        # alone leaves those stories a beat behind the fact they already
        # stated.
        _materialize_interior_places(merged)
        place_enclosed_bodies(merged)
        derive_contained_positions(merged)

    # Contact and containment are two ledgers describing one arrangement, and
    # this is the first point at which both are final -- containment can still
    # be MINTED from contact just above. A named part reaching a body across
    # an enclosure is the contact ledger contradicting the containment one,
    # and containment is the authoritative side (the ground
    # `_contained_inversion` already defers on), so contact yields.
    contacts_across_enclosure(merged, report=contact_report)

    # TIME INSIDE A PLACE, and this slot is chosen against the real ordering
    # rather than for convenience. Contact and containment are BOTH final by
    # here -- `derive_containment_from_contacts` can still mint a record just
    # above, and re-runs the placement passes inside its own branch -- so this
    # reads settled positions and may legitimately rewrite the settled
    # contact. And it is BEFORE station hygiene, so `derive_scene_stations`
    # and `normalize_scene_stations` below prune a carried body's stale
    # in-room anchor in the SAME merge; a mover written from outside this
    # function would keep an anchor pinned to the room it left.
    advance_room_transits(merged, clock_seconds, report=crossing_report)

    # Within-room position, last of all. Contact is settled by now, and contact
    # is what the derivation reads: a hand on the quilt is a body at the bed.
    # Then the same hygiene as before -- prune a stale anchor (which auto-heals
    # a room move), drop non-co-located `near` links, symmetrize what survives.
    derive_scene_stations(merged, diff.get("stations"), diff.get("contact_ops"))
    merged.setdefault("stations", {})
    normalize_scene_stations(merged)
    invalidate_contact_bound_poses(merged, _contacts_before_ops)
    normalize_scene_poses(merged)

    # Channels, after rooms have settled: a channel names rooms, so it can only
    # be pruned once this beat's room retirements are known.
    apply_comms_ops(merged, diff.get("comms_ops"))
    normalize_scene_comms(merged)

    # Bodily condition, last: air depends on whether the doorway ended the beat
    # sealed, which the dock-edge rewrite above has only just settled. Entirely
    # skipped unless something has written a vitals table -- absence is the
    # off switch, so a story without survival tracking never touches this.
    incoming_vitals = diff.get("vitals")
    if incoming_vitals or merged.get("vitals"):
        from world.survival import apply_vitals_diff, tick_vitals
        apply_vitals_diff(merged, incoming_vitals)
        # LAZY on purpose: world/mechanics imports the world.spatial facade
        # this module sits behind, so a module-scope import would cycle at
        # interpreter start. Same reason as the survival import above.
        from world.mechanics import time_diff_duration
        # One reader owns what a time block can say (chat 88 turns 61/64/66:
        # three spellings of the same claim, three callers reading three
        # different subsets of it). Here that means duration_seconds, else
        # the span between a parseable start and end.
        elapsed = time_diff_duration(diff.get("time"))
        # WHO IS ASLEEP comes from the caller (`sleeping=`), because the
        # answer lives in the conditions ledger's awareness levels
        # (story/scene.AWARENESS_LEVELS via awareness_map) -- a layer above
        # this package, which world/ must not reach up into. The old sole
        # source below read `contained[*].mode == "asleep"`, but `mode` is a
        # CONTAINMENT vocabulary (carried/held/pocket/enclosed), never an
        # awareness level, so the set was always effectively empty and
        # nobody has ever recovered stamina by sleeping (docs/UNBUILT.md
        # 1.3). The containment reading is kept only as a union: it cannot
        # subtract, and an accidental "asleep" spelling someone stored there
        # keeps what little it had.
        tick_vitals(
            merged, elapsed,
            asleep=(set(str(n) for n in (sleeping or ()))
                    | {n for n, r in (merged.get("contained") or {}).items()
                       if isinstance(r, dict) and r.get("mode") == "asleep"}),
        )

    return merged
