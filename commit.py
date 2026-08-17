"""Atomic world-state commit with mutation validation."""

import contextvars
import copy
import json, re, threading, time, weakref
from concurrent.futures import ThreadPoolExecutor
from db import q, qi, qtx, transaction, wget, wset, get_setting
from memory import (
    add_memories_batch, prepare_memories_batch, delete_turn_memories, search_lore, add_lore,
    record_dispute, raise_importance,
    update_lore, LORE_CATEGORIES, LOREBOOK_TYPES,
    chat_lorebook_ids, chat_lorebook_weights, lorebook_manifest, dump_chat_memories,
    ensure_chat_canon_book,
    add_lorebook_link, lorebook_descendants,
    restore_chat_memories, dump_lorebook, restore_lorebook,
    knowledge_for_character, get_relationships,
    save_relationships, update_relationships_from_inference,
    apply_relationship_updates, maybe_consolidate_character_memory,
    reconcile_inference_confidence, _is_empty_view,
)
from providers import embed_texts
from prompts import get_prompt
import affect
import psychology_runtime
from character_schema import (_UNSPACED_SCRIPT, character_name,
                              fold_identity_key,
                              character_name_from_text,
                              new_uid, character_psychology,
                              character_interoception,
                              character_initial_outfit,
                              character_initial_active_state, effective_drive,
                              character_standing_intentions,
                              character_projects,
                              normalize_character_data, persona_name,
                              character_appearance as _char_appearance)
from frames import is_recognized_in_frame
import attire as attire_model
from scene import (set_char_state, set_char_status, seed_initial_attire,
                   get_scene, SINGULAR_BODY_CONDITIONS,
)
from mechanics import mechanics_sweep, news_latency_seconds, stable_event_key
from weather import advance_weather, normalize_weather
from spatial import (merge_scene_with_diff, _merge_entity, room_of,
                     normalize_room_id, spatial_rel, hear_level,
                     normalize_barrier, normalize_bearing, opposite_bearing,
                     passable_path, rooms_adjacent, visible_adjacent_rooms,
                     guessed_room_sizes, _is_body_entity)
from theory_of_mind import (apply_mind_model_updates, rekey_place_claims,
                            select_active_hypotheses, sheet_capacity)
from survival import vitals_of
from comfort import comfort_level
from paradox import check_and_apply_paradox
from spatial_frames import detect_and_reconcile as detect_and_reconcile_spatial
from spatial_frames import (infer_companion_carry, infer_vehicle_zones,
                            infer_came_from, infer_focus, infer_facing,
                            infer_threshold_crossings)

# How much of a body's own route it carries. Bounded because it rides
# chat_chars.state, and because a route from four hundred beats ago is not
# something anyone recalls as a route.
VISITED_ROOMS_CAP = 60

# How far back a satisfied intention credits the route, and how much weight one
# room can accrue. Bounded because a goal closed after forty beats says little
# about the room walked through on beat one, and because a route that worked
# ten times should not become impossible to abandon when the world changes.
ROUTE_CREDIT_WINDOW = 25
ROUTE_CREDIT_CAP = 5

# How many places one mind's durable map may hold. Unlike VISITED_ROOMS_CAP
# this is not a recency window -- the graph is the thing that must survive a
# long walk -- but it is still a MEMORY, and an unbounded one would grow with
# every campaign forever. Eviction is by (last_turn, visits): the places
# forgotten first are the ones least revisited and longest unseen, which is
# forgetting, and forgetting is the point.
PLACE_GRAPH_NODE_CAP = 400


def update_place_graph(graph, scene, here_rid, turn_idx, came_from=None,
                       visible=None):
    """Fold one committed beat of standing in a room into this character's
    durable place graph ({"nodes": {rid: ...}, "edges": {rid: {rid: ...}}} on
    chat_chars.state.place_graph).

    Firewall discipline, in order of temptation:

    * Nodes/edges come ONLY from (a) the room the character is standing in --
      its doorways are perceivable from inside, whichever side declared the
      edge; (b) the step they just took (`came_from`, guarded by
      rooms_adjacent so a teleport/carry mints no walked edge); (c) the
      `visible` list, which is `visible_adjacent_rooms` output for a room
      they actually stood in. A room seen through a doorway contributes its
      NAME and its visible closedness and nothing else: `_onward_exits`
      returns counts and bearings, never destinations, so the neighbour's own
      doorways are structurally unavailable here -- do not "fix" that by
      reading scene["rooms"][neighbour]["adjacent"], which would quietly turn
      the remembered map into the objective one.
    * The standing room is also the ONLY place objective state may correct
      the graph: a remembered doorway of THIS room that present perception
      shows absent or walled is stamped `disproven` (both directions, since a
      doorway is one doorway). A room absent from the scene entirely -- moved
      on from, retired, destroyed -- keeps its nodes and edges untouched: the
      character learns a place is gone by standing where it was, not by the
      registry telling their memory.
    * Nothing here reads another character's state, and nothing writes
      anything the character did not walk, see, or step through.

    `basis` is "walked" (stood there) or "seen" (looked into it); "told" is
    an accepted value for a future testimony-derived writer, but no code path
    writes it yet -- there is currently no deterministic source for it.
    Mutates and returns the normalized graph.
    """
    graph = graph if isinstance(graph, dict) else {}
    nodes = graph.get("nodes")
    nodes = nodes if isinstance(nodes, dict) else {}
    edges = graph.get("edges")
    edges = edges if isinstance(edges, dict) else {}
    graph = {"nodes": nodes, "edges": edges}
    if not here_rid:
        return graph
    here_rid = str(here_rid)
    turn_idx = int(turn_idx or 0)
    rooms = (scene or {}).get("rooms") or {}

    def _node(rid, name=None, basis="seen"):
        rec = nodes.get(rid)
        if not isinstance(rec, dict):
            rec = {"basis": basis, "visits": 0, "first_turn": turn_idx}
            nodes[rid] = rec
        if basis == "walked":
            rec["basis"] = "walked"          # never downgraded
        rec.setdefault("basis", basis)
        if name:
            rec["name"] = str(name)
        rec["last_turn"] = turn_idx
        return rec

    def _confirm(a, b, bearing=None, taken=False):
        side = edges.get(a)
        if not isinstance(side, dict):
            side = {}
            edges[a] = side
        rec = side.get(b)
        if not isinstance(rec, dict):
            rec = {}
            side[b] = rec
        rec.pop("disproven", None)
        rec["last_confirmed"] = turn_idx
        if bearing:
            rec["bearing"] = bearing
        if taken:
            rec["taken"] = True
            rec["basis"] = "walked"
        else:
            rec.setdefault("basis", "seen")
        return rec

    here_room = rooms.get(here_rid) or {}
    here_node = _node(here_rid, name=here_room.get("name"), basis="walked")
    if came_from or not here_node.get("visits"):
        here_node["visits"] = int(here_node.get("visits") or 0) + 1

    # Every doorway of the standing room, from either side's declaration. A
    # wall is visible adjacency but not a doorway, so it earns no edge.
    doorways = {}
    for e in here_room.get("adjacent") or []:
        if isinstance(e, dict) and e.get("to") \
                and normalize_barrier(e.get("barrier")) != "wall":
            doorways.setdefault(str(e["to"]), normalize_bearing(e.get("dir")))
    for oid, other in rooms.items():
        oid = str(oid)
        if oid == here_rid or oid in doorways or not isinstance(other, dict):
            continue
        for e in other.get("adjacent") or []:
            if isinstance(e, dict) and str(e.get("to")) == here_rid \
                    and normalize_barrier(e.get("barrier")) != "wall":
                doorways.setdefault(
                    oid, opposite_bearing(normalize_bearing(e.get("dir"))))
                break
    for to_rid, bearing in doorways.items():
        _confirm(here_rid, to_rid, bearing=bearing)
        far = (edges.get(to_rid) or {}).get(here_rid)
        if isinstance(far, dict):
            far.pop("disproven", None)

    # Contradiction correction -- standing room only. A doorway remembered
    # here that present perception does not show is disproven, both ways.
    for to_rid, rec in list((edges.get(here_rid) or {}).items()):
        if to_rid in doorways or not isinstance(rec, dict):
            continue
        rec["disproven"] = turn_idx
        far = (edges.get(to_rid) or {}).get(here_rid)
        if isinstance(far, dict):
            far["disproven"] = turn_idx

    if came_from and str(came_from) != here_rid \
            and rooms_adjacent(scene, came_from, here_rid):
        _confirm(str(came_from), here_rid, taken=True)

    for item in visible or []:
        if not isinstance(item, dict):
            continue
        rid_seen = str(item.get("room_id") or "")
        if not rid_seen or rid_seen == here_rid:
            continue
        rec = _node(rid_seen, name=item.get("room_name"), basis="seen")
        onward = item.get("onward_exits")
        if onward == 0:
            rec["closed"] = True
        elif isinstance(onward, int) and onward > 0:
            rec.pop("closed", None)
        _confirm(here_rid, rid_seen, bearing=doorways.get(rid_seen))

    overflow = len(nodes) - PLACE_GRAPH_NODE_CAP
    if overflow > 0:
        order = sorted(
            (rid for rid in nodes if rid != here_rid),
            key=lambda rid: (
                int((nodes[rid] or {}).get("last_turn") or 0)
                if isinstance(nodes[rid], dict) else 0,
                int((nodes[rid] or {}).get("visits") or 0)
                if isinstance(nodes[rid], dict) else 0))
        evicted = set(order[:overflow])
        for rid in evicted:
            nodes.pop(rid, None)
            edges.pop(rid, None)
        for side in edges.values():
            if isinstance(side, dict):
                for gone in [b for b in side if b in evicted]:
                    side.pop(gone, None)
    return graph


def record_spatial_experience(st, sc, here_room, turn_idx):
    """Everything one committed beat of standing somewhere earns a character:
    the route window, the exits of rooms stood in, visibly-closed chambers,
    and the durable place graph. Mutates and returns `st`.

    `visited_rooms` stays a bounded RECENCY window (the loop detectors need
    it), but it is no longer allowed to bound knowledge: `known_exits` used
    to be pruned to rooms still inside the window, which erased spatial
    knowledge past VISITED_ROOMS_CAP -- and worse than erased it, since
    _frontier_beyond read a room with no recorded exits as "never stood
    there, everything past it is potentially new". Forgetting made stale
    ground look PROMISING, on maze runs that sit exactly on the cap.
    Durability now belongs to place_graph, and the legacy keys follow its
    memory (bounded by the same eviction) rather than the window's.

    Persistence decision (docs/guides/DATABASE.md checklist): all of this rides the
    chat_chars.state JSON blob, which checkpoints snapshot/restore whole
    (checkpoints.snapshot_state/restore), chat_archive exports/imports
    verbatim, and the branch path copies row-for-row -- so no schema, remap,
    or archive change is needed. Room ids are frame-scoped scene rids, which
    those paths preserve as-is.
    """
    if not here_room:
        return st
    visited = [
        r for r in (st.get("visited_rooms") or [])
        if isinstance(r, str) and r
    ]
    came_from = visited[-1] if visited else None
    if came_from == here_room:
        came_from = None
    else:
        # A body that RAN crossed several rooms this beat, and has been in
        # every one of them. Recording only where they stopped would leave
        # holes in their map exactly where their feet went, and worse than
        # holes: the place graph would mint no walked edge at all (came_from
        # is not adjacent), so a corridor they had sprinted end to end would
        # keep reading as untrodden and pull them back down it.
        #
        # Reconstructed rather than trusted from the Director: the rooms
        # between are a deterministic fact about the scene, and asking a model
        # to list them is asking it to be right about geometry -- which is the
        # thing it is measurably worst at (see A11's bearing errors).
        #
        # A move with NO passable route is a teleport, a carry, or a vehicle,
        # and mints nothing: the character learns a place by being carried
        # through it about as well as a parcel does.
        crossed = passable_path(sc, came_from, here_room) if came_from else []
        for room in (crossed[:-1] if crossed else []):
            if room and (not visited or visited[-1] != room):
                visited.append(room)
        visited.append(here_room)
        if crossed and len(crossed) > 1:
            came_from = crossed[-2]
    st["visited_rooms"] = visited[-VISITED_ROOMS_CAP:]
    # The exits visible FROM a room they actually stood in. Not oracle
    # knowledge: standing in a room is how you see its doorways.
    known = st.get("known_exits")
    if not isinstance(known, dict):
        known = {}
    room = (sc.get("rooms") or {}).get(here_room) or {}
    known[here_room] = sorted({
        str(e.get("to")) for e in (room.get("adjacent") or [])
        if isinstance(e, dict) and e.get("to")
    })
    # Which of those neighbours he could SEE were closed -- the same fact
    # visible_adjacent_rooms reports live, written down so the frontier test
    # can tell "a door I have not taken" from "a route I have not taken".
    try:
        visible = visible_adjacent_rooms(sc, here_room) or []
    except Exception:
        visible = []
    dead = st.get("known_dead_ends")
    dead = set(dead) if isinstance(dead, list) else set()
    for item in visible:
        if isinstance(item, dict) and item.get("onward_exits") == 0:
            dead.add(str(item.get("room_id")))
    st["known_dead_ends"] = sorted(dead)
    st["place_graph"] = update_place_graph(
        st.get("place_graph"), sc, here_room, turn_idx,
        came_from=came_from, visible=visible)
    # Legacy keys bounded by the graph's memory, not the recency window.
    remembered = set(st["place_graph"]["nodes"]) | set(st["visited_rooms"])
    st["known_exits"] = {k: v for k, v in known.items() if k in remembered}
    st["known_dead_ends"] = [r for r in st["known_dead_ends"]
                             if r in remembered]
    return st

_COMMIT_LOCKS = weakref.WeakValueDictionary()
_COMMIT_LOCKS_GUARD = threading.Lock()

def _commit_lock(turn_id):
    with _COMMIT_LOCKS_GUARD:
        return _COMMIT_LOCKS.setdefault(turn_id, threading.Lock())

def _keys_str(value):
    if isinstance(value, (list, tuple, set)):
        return ", ".join(str(v) for v in value if v is not None)
    return str(value or "")

# Deterministic event/memory ids live in mechanics.py now (the sweep needs
# them without importing commit); kept under the old private name for the
# many call sites and tests that use it.
_stable_event_key = stable_event_key

def _clamp(value, lo=0.0, hi=1.0):
    try:
        return max(lo, min(hi, float(value)))
    except Exception:
        return lo

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
        if any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in _NON_ATTIRE_TERMS):
            continue
        if text not in result:
            result.append(text)
    return result

def _normalize_character_output(out):
    if not out.get("mind_model_updates") and out.get("inference_updates"):
        converted = []
        for update in out["inference_updates"]:
            converted.append({
                "about_entity": str(update.get("about") or "unknown"),
                "kind": "goal",
                "claim": str(update.get("conclusion") or ""),
                "confidence": float(update.get("confidence", 0.5)),
                "evidence": [{"event_id": "", "fact": str(update.get("basis") or "")}],
                "alternatives": [],
            })
        out["mind_model_updates"] = converted
    return out

# ---- Scene commit with entity-aware merge ----

def _anchor_current_room(sc, entity_id):
    """The anchor entity's current exterior room, tolerating positions
    keyed by entity id, display name, or alias (the same read tolerance
    spatial._entity_exterior_room applies)."""
    positions = sc.get("positions") or {}
    if entity_id in positions:
        return positions[entity_id]
    ent = (sc.get("entities") or {}).get(entity_id)
    if isinstance(ent, dict):
        for cand in [ent.get("name"), *(ent.get("aliases") or [])]:
            cand = str(cand or "").strip()
            if cand and cand in positions:
                return positions[cand]
    return None


def sync_anchored_books(cid, sc):
    """A vehicle-class (or any anchor_entity_id-flagged) lorebook tracks
    its anchor entity's current room via a 'currently_within' lorebook
    link -- presence ("is at"), rewritten from scene positions at every
    commit. parent_id is canonical containment ("belongs to") and is
    NEVER mutated here: the old behavior reparented the book to follow
    the vehicle, collapsing the two relations into one and destroying
    the authored hierarchy every time the vehicle docked somewhere new.

    The link targets the book of wherever the anchor currently is:
    - the room is another anchored entity's interior (a van aboard a
      ferry) -> that entity's own anchored book, giving the true nesting
      chain the monitoring walk (memory.monitoring_subtree) reads;
    - otherwise the location book whose scope_location_id matches the
      room.
    follow_for_retrieval stays on (default weight) so docked-location
    lore remains reachable through the vehicle book via
    resolve_lorebook_graph. The link is retrieval bookkeeping ONLY --
    it must never be read as perception authorization; what an observer
    aboard actually perceives stays with the epistemic/spatial layer.
    """
    anchored = q(
        "SELECT id, anchor_entity_id, parent_id FROM lorebooks "
        "WHERE chat_id=? AND anchor_entity_id IS NOT NULL",
        (cid,),
    )
    if not anchored:
        return
    book_by_anchor = {b["anchor_entity_id"]: b["id"] for b in anchored}
    rooms = sc.get("rooms") or {}
    for book in anchored:
        room = _anchor_current_room(sc, book["anchor_entity_id"])
        if not room:
            # No recorded position -> nothing to derive from; leave the
            # last known presence link standing (mirrors the old
            # missing-position behavior).
            continue
        room_def = rooms.get(room)
        parent_entity = room_def.get("parent_entity") \
            if isinstance(room_def, dict) else None
        target_id = None
        if parent_entity and parent_entity != book["anchor_entity_id"]:
            target_id = book_by_anchor.get(parent_entity)
        if target_id is None:
            target = q(
                "SELECT id FROM lorebooks WHERE chat_id=? AND "
                "scope_location_id=? ORDER BY id LIMIT 1",
                (cid, room), one=True,
            )
            target_id = target["id"] if target else None
        if target_id == book["id"]:
            target_id = None
        current = q(
            "SELECT id, target_book_id FROM lorebook_links "
            "WHERE source_book_id=? AND relation_type='currently_within'",
            (book["id"],),
        )
        for link in current:
            if link["target_book_id"] != target_id:
                qi("DELETE FROM lorebook_links WHERE id=?", (link["id"],))
        if target_id is not None \
                and not any(l["target_book_id"] == target_id for l in current):
            try:
                add_lorebook_link(book["id"], target_id, "currently_within")
            except ValueError:
                pass

def _guard_occupied_mover_removal(prev_scene, diff, doomed=None):
    """Deterministic refusal: removing an entity whose parent_entity-linked
    interior rooms still hold occupants, without the same beat repositioning
    every occupant (state_diff.positions, to a room OUTSIDE the doomed
    interior) or recording their departure (cast_changes), would leave
    people positioned inside rooms of a container that no longer exists.
    Raising here fails commit preparation, so the whole turn rolls back per
    the existing atomicity contract -- the same conservatism as
    merge_scene_with_diff's occupied-room removal refusal, made loud
    because losing PEOPLE is worse than losing a room.

    `doomed` ({label: room_id set}) generalizes the guard to BOOK scope
    for destruction: every room registered to a destroyed book is doomed
    alongside the entity's own interiors, and a stranded occupant in ANY
    of them fails the whole commit -> rollback. Since Phase 3b the doomed
    set may span a whole multi-book cascade; an occupant that is ITSELF
    being removed this beat (a doomed vehicle inside a doomed region) is
    not stranded -- it ceases to exist with its container, and its own
    interior rooms carry their own doom entry below, so the people inside
    IT are still guarded."""
    removals = [str(e) for e in (diff.get("remove_entities") or []) if e]
    if not removals and not doomed:
        return
    removal_set = set(removals)
    rooms = prev_scene.get("rooms") or {}
    positions = prev_scene.get("positions") or {}
    diff_positions = {
        str(k).casefold(): v for k, v in (diff.get("positions") or {}).items()
    }
    departed = {
        str(c.get("who") or "").casefold()
        for c in (diff.get("cast_changes") or []) if isinstance(c, dict)
    }
    doom_map = {}
    for eid in removals:
        interior = {rid for rid, r in rooms.items()
                    if isinstance(r, dict) and r.get("parent_entity") == eid}
        if interior:
            doom_map[eid] = interior
    for label, extra in (doomed or {}).items():
        doom_map[label] = doom_map.get(label, set()) | {
            str(r) for r in extra if str(r) in rooms}
    for eid, interior in doom_map.items():
        stranded = []
        for name, room in positions.items():
            if room not in interior or str(name) == eid:
                continue
            if str(name) in removal_set:
                continue  # removed/destroyed itself this beat (see above)
            cf = str(name).casefold()
            new_room = diff_positions.get(cf)
            if new_room is not None and new_room not in interior:
                continue
            if cf in departed:
                continue
            stranded.append(name)
        if stranded:
            raise RuntimeError(
                f"removal/destruction would strand occupant(s) {stranded!r} "
                f"inside removed {eid!r}'s doomed room(s); "
                "reposition them via state_diff.positions or record their "
                "departure in cast_changes in the same beat"
            )

# ---- Destruction: single-book (Phase 2) + multi-book cascades (3b) ----
#
# The DIRECTOR resolves the causal destructive event by declaring it in
# state_diff.destruction (the revived DestructionEffect shape) -- code
# never originates a destruction, it only realizes a declared one
# deterministically. scale 'vehicle'/'building' dooms the target's ONE
# anchored/scoped book; scale 'region' (Phase 3b) dooms a multi-book
# CASCADE enumerated from the lorebook tree (_destruction_cascade below).
# Either way the doomed books and their registered rooms are retired
# (retire-not-delete: the ruin's history stays retrievable), the live
# rooms/entities drop through the ordinary diff machinery, a stranded
# occupant ANYWHERE in the doomed set fails the whole commit (guard
# above), and awareness propagates only through latency-gated
# `news_arrival` scheduled events that the mechanics sweep fires against
# the minting frame's clock -- latency declared by the Director, or
# derived from the audience's distance in the book graph (near regions
# hear sooner; mechanics.news_latency_seconds).

def _destruction_book(cid, target):
    """The live ROOT book destruction of `target` starts from: its
    anchored vehicle book, else the book scoped to it as a location."""
    row = q(
        "SELECT id, name FROM lorebooks WHERE chat_id=? AND "
        "anchor_entity_id=? AND retired_turn_id IS NULL ORDER BY id LIMIT 1",
        (cid, target), one=True,
    )
    if row:
        return row
    return q(
        "SELECT id, name FROM lorebooks WHERE chat_id=? AND "
        "scope_location_id IN (?, ?) AND retired_turn_id IS NULL "
        "ORDER BY id LIMIT 1",
        (cid, target, normalize_room_id(target)), one=True,
    )


def _chat_book_graph(cid):
    """This chat's whole lorebook graph in one read: rows by id,
    undirected edges (parent_id containment + currently_within presence),
    and the directed currently_within list (cascade enumeration needs the
    direction; the news-distance walk does not). Pure reads -- runs in
    commit preparation."""
    books = {
        row["id"]: dict(row)
        for row in q(
            "SELECT id, name, parent_id, anchor_entity_id, "
            "scope_location_id, retired_turn_id FROM lorebooks "
            "WHERE chat_id=?", (cid,))
    }
    edges = {bid: set() for bid in books}
    for bid, row in books.items():
        pid = row["parent_id"]
        if pid in edges:
            edges[bid].add(pid)
            edges[pid].add(bid)
    within = []
    for link in q(
        "SELECT source_book_id AS s, target_book_id AS t "
        "FROM lorebook_links WHERE relation_type='currently_within' "
        "ORDER BY id",
    ):
        if link["s"] in edges and link["t"] in edges:
            edges[link["s"]].add(link["t"])
            edges[link["t"]].add(link["s"])
            within.append((link["s"], link["t"]))
    return books, edges, within


def _book_distances(root_id, edges):
    """BFS hop distances from the destruction root over the undirected
    book graph -- the deterministic 'how far away is that audience'
    measure derived news latency uses (Phase 3b)."""
    if root_id not in edges:
        return {}
    distances = {root_id: 0}
    frontier = [root_id]
    while frontier:
        nxt = []
        for bid in frontier:
            for neighbor in sorted(edges[bid]):
                if neighbor not in distances:
                    distances[neighbor] = distances[bid] + 1
                    nxt.append(neighbor)
        frontier = nxt
    return distances


def _audience_book_id(audience, books):
    """Deterministically match a declared news audience to a lorebook --
    by name, scope_location_id, or anchor_entity_id, exact or slugified;
    lowest book id wins. None when nothing matches (the caller falls back
    to the flat unreachable-latency default)."""
    keys = {audience.casefold(), normalize_room_id(audience)} - {""}
    if not keys:
        return None
    for bid in sorted(books):
        row = books[bid]
        candidates = set()
        for value in (row.get("name"), row.get("scope_location_id"),
                      row.get("anchor_entity_id")):
            value = str(value or "").strip()
            if value:
                candidates.add(value.casefold())
                candidates.add(normalize_room_id(value))
        if keys & candidates:
            return bid
    return None


def _destruction_cascade(cid, root_book_id, prev_scene, books, within):
    """Phase 3b: enumerate the multi-book cascade a region destruction
    dooms -- a deterministic function of (committed state, declared root),
    never model output. Two edge kinds, mirroring monitoring_subtree:

    - parent_id descendants of the root (canonical containment): every
      child book falls with its region, rooms or no rooms;
    - inbound currently_within members (live presence), to a fixpoint,
      but only when the member's anchor entity is PHYSICALLY positioned
      inside an already-doomed room -- the ferry docked in the burning
      harbor goes down with it (and the van aboard the ferry with the
      ferry), while a ship whose stale link says 'within' but whose
      anchor is not actually in a doomed room is spared.

    Returns {"book_ids": sorted live cascaded books, "anchors": their
    anchor entity ids, "registered": live registry room_uids owned by any
    cascaded book (the whole registries -- rooms live only in a sibling
    frame's scene included, because the books are gone everywhere)}."""
    prev_rooms = prev_scene.get("rooms") or {}
    positions = {
        str(k): str(v)
        for k, v in (prev_scene.get("positions") or {}).items()
    }
    rooms_by_book = {}
    for row in q(
        "SELECT room_uid, owning_book_id FROM room_registry "
        "WHERE chat_id=? AND retired_turn_id IS NULL ORDER BY room_uid",
        (cid,),
    ):
        rooms_by_book.setdefault(row["owning_book_id"], []).append(
            row["room_uid"])

    def subtree(book_id):
        return {b for b in lorebook_descendants(book_id) if b in books}

    cascade = subtree(root_book_id)
    while True:
        anchors = {books[b]["anchor_entity_id"] for b in cascade
                   if books[b]["anchor_entity_id"]}
        doomed_live = {
            rid for b in cascade for rid in rooms_by_book.get(b, ())
            if rid in prev_rooms
        } | {
            str(rid) for rid, room in prev_rooms.items()
            if isinstance(room, dict)
            and room.get("parent_entity") in anchors
        }
        grew = False
        for source, target_book in within:
            if target_book not in cascade or source in cascade:
                continue
            anchor = books[source]["anchor_entity_id"]
            if anchor and positions.get(str(anchor)) in doomed_live:
                cascade |= subtree(source)
                grew = True
        if not grew:
            break

    return {
        "book_ids": sorted(
            b for b in cascade if books[b]["retired_turn_id"] is None),
        "anchors": anchors,
        "registered": sorted({
            rid for b in cascade for rid in rooms_by_book.get(b, ())
        }),
    }


def _prepare_destruction(cid, prev_scene, diff, add_warning=None):
    """Validate the Director's state_diff.destruction declaration and fold
    its mechanical consequences into the (already deep-copied) diff:
    remove every doomed entity and room. Pure reads; returns the plan
    commit_scene applies durably, or None. Ledger-not-cage does NOT apply
    here -- an invalid declaration is dropped with a warning rather than
    guessed at, because destruction is irreversible.

    scale 'vehicle'/'building' dooms the target's ONE book (Phase 2);
    scale 'region' dooms the deterministic multi-book cascade enumerated
    by _destruction_cascade above (Phase 3b)."""
    decl = diff.get("destruction")
    if not isinstance(decl, dict):
        return None

    def warn(message):
        if add_warning:
            add_warning(message)

    target = str(decl.get("target_id") or "").strip()
    if not target:
        warn("destruction declaration dropped: no target_id")
        return None
    scale = str(decl.get("scale") or "").strip().casefold()
    if scale not in ("vehicle", "building", "region"):
        warn(
            f"destruction of {target!r} dropped: scale {scale!r} is not a "
            "single vehicle/building or a multi-book region"
        )
        return None
    kind = str(decl.get("kind") or "destroyed").strip() or "destroyed"

    books, edges, within = _chat_book_graph(cid)
    root = _destruction_book(cid, target)
    prev_rooms = prev_scene.get("rooms") or {}

    if scale == "region":
        if not root:
            warn(
                f"destruction of region {target!r} dropped: no live "
                "lorebook is anchored or scoped to it, so the cascade "
                "cannot be enumerated"
            )
            return None
        cascade = _destruction_cascade(
            cid, root["id"], prev_scene, books, within)
        book_ids = cascade["book_ids"]
        doomed_entities = sorted(
            {str(a) for a in cascade["anchors"]} | {target})
        registered = cascade["registered"]
        doomed_set = set(doomed_entities)
        entity_rooms = {
            rid for rid, r in prev_rooms.items()
            if isinstance(r, dict)
            and r.get("parent_entity") in doomed_set}
    else:
        book_ids = [root["id"]] if root else []
        doomed_entities = [target]
        registered = []
        if root:
            registered = [
                r["room_uid"] for r in q(
                    "SELECT room_uid FROM room_registry WHERE chat_id=? AND "
                    "owning_book_id=? AND retired_turn_id IS NULL",
                    (cid, root["id"]),
                )
            ]
        entity_rooms = {rid for rid, r in prev_rooms.items()
                        if isinstance(r, dict)
                        and r.get("parent_entity") == target}

    doomed_live = set(entity_rooms) \
        | {r for r in registered if r in prev_rooms}
    # Retirement covers the doomed books' whole registries, including
    # rooms that live only in a sibling frame's scene -- the books are
    # gone everywhere.
    retire_rooms = sorted(set(registered) | {
        rid for rid in entity_rooms
        if q("SELECT 1 FROM room_registry WHERE chat_id=? AND room_uid=?",
             (cid, rid), one=True)
    })

    entities = prev_scene.get("entities") or {}
    label = target
    ent = entities.get(target)
    if isinstance(ent, dict) and ent.get("name"):
        label = str(ent["name"])
    elif root:
        label = root["name"]

    # Fold the mechanical consequences into the diff: the ordinary diff
    # machinery (merge_scene_with_diff) is what actually drops the live
    # entities/rooms -- destruction adds no second removal path.
    removals = diff.setdefault("remove_entities", [])
    for eid in doomed_entities:
        if eid in entities and eid not in removals:
            removals.append(eid)
    room_removals = diff.setdefault("remove_rooms", [])
    for rid in sorted(doomed_live):
        if rid not in room_removals:
            room_removals.append(rid)

    # Occupants who escape the doomed rooms by DEPARTING (cast_changes,
    # the guard's second legal exit) rather than repositioning keep a
    # stale positions entry that merge_scene_with_diff's occupied-room
    # refusal would trip over, silently keeping a doomed room live in
    # the scene while its registry row retires. Vacate them here (the
    # guard has already proven every doomed-room occupant repositioned
    # or departed); prepare_scene_commit pops these positions and the
    # remaining doomed rooms right after the merge.
    diff_positions = {
        str(k).casefold(): str(v)
        for k, v in (diff.get("positions") or {}).items()
    }
    departed = {
        str(c.get("who") or "").casefold()
        for c in (diff.get("cast_changes") or []) if isinstance(c, dict)
    }
    vacated = sorted(
        str(name)
        for name, room in (prev_scene.get("positions") or {}).items()
        if str(room) in doomed_live
        and str(name).casefold() in departed
        and diff_positions.get(str(name).casefold()) is None
    )

    distances = _book_distances(root["id"], edges) if root else {}
    news = []
    for item in decl.get("news") or []:
        if not isinstance(item, dict):
            continue
        audience = str(item.get("audience") or "").strip()
        if not audience:
            continue
        try:
            latency = max(0.0, float(item["latency_seconds"]))
        except (KeyError, TypeError, ValueError):
            # No declared latency: derive it from the audience's hop
            # distance to the root in the book graph (Phase 3b) -- near
            # regions hear sooner, distant later, unmatched a flat day.
            audience_book = _audience_book_id(audience, books)
            latency = news_latency_seconds(
                distances.get(audience_book)
                if audience_book is not None else None)
        summary = str(item.get("summary") or "").strip() \
            or f"{label} has been {kind}"
        news.append({"audience": audience, "latency_seconds": latency,
                     "summary": summary})

    return {
        "target": target, "scale": scale, "kind": kind, "label": label,
        "book_ids": book_ids,
        "doomed_rooms": sorted(doomed_live),
        "doomed_entities": list(doomed_entities),
        "retire_rooms": retire_rooms,
        "vacated": vacated,
        "news": news,
    }


def _finalize_destruction_news(destruction, cid, frame_id, turn, elapsed):
    """Mint the news_arrival scheduled-event rows: one per audience scope,
    due_at = the minting frame's sim clock + declared latency, stable
    event ids so a rerun cannot double-schedule. Same frame-gating payload
    convention as transit_arrival (the sweep never fires one against
    another frame's clock)."""
    rows = []
    for item in destruction["news"]:
        event_id = _stable_event_key(
            "news_arrival", cid, frame_id, destruction["target"], turn.id,
            item["audience"])
        rows.append({
            "event_id": event_id, "chat_id": cid,
            "due_at": elapsed + item["latency_seconds"],
            "kind": "news_arrival", "location_id": None,
            "payload": json.dumps({
                "frame_id": frame_id,
                "audience": item["audience"],
                "summary": item["summary"],
                "target_id": destruction["target"],
                "destruction_kind": destruction["kind"],
                "provenance": "told",
            }, ensure_ascii=False),
            "seed": f"news:{cid}:{turn.idx}", "status": "pending",
        })
    destruction["news_rows"] = rows


def _apply_destruction(cid, turn_id, destruction):
    """Durable half, inside commit_scene's transaction: retire every
    doomed book (one for vehicle/building scale, the whole cascade for
    region scale) and their registered rooms atomically with the scene
    write, mint the news events, and stage engine notices (appended --
    the transit sweep already wrote this beat's list in the domain before
    this one). All-or-nothing with the rest of the turn: any domain
    failure rolls the entire outer transaction back."""
    book_ids = destruction.get("book_ids") or []
    for book_id in book_ids:
        qi("UPDATE lorebooks SET retired_turn_id=? "
           "WHERE id=? AND chat_id=? AND retired_turn_id IS NULL",
           (turn_id, book_id, cid))
    for rid in destruction.get("retire_rooms") or []:
        qi("UPDATE room_registry SET retired_turn_id=? "
           "WHERE chat_id=? AND room_uid=? AND retired_turn_id IS NULL",
           (turn_id, cid, rid))
    for row in destruction.get("news_rows") or []:
        qi(
            "INSERT OR REPLACE INTO scheduled_events"
            "(event_id,chat_id,due_at,kind,location_id,payload,seed,status)"
            " VALUES(?,?,?,?,?,?,?,?)",
            (row["event_id"], row["chat_id"], row["due_at"], row["kind"],
             row["location_id"], row["payload"], row["seed"], row["status"]),
        )
    notices = wget(cid, "engine_notices", []) or []
    retired = len(destruction.get("retire_rooms") or [])
    notices.append(
        f"{destruction['label']} has been {destruction['kind']}; "
        f"its records ({retired} registered room(s)"
        + (f", {len(book_ids)} lorebook(s)" if book_ids else "")
        + ") are retired history now."
    )
    wset(cid, "engine_notices", notices)


# ---- Room registry (normalized) + commit-side structural dedup ----
#
# Two live failure classes share one root: nothing at commit time knew which
# rooms an owner (a vehicle, the current location) ALREADY has. (1) Two
# structurally identical vehicles minting the same interior key ("deck_3")
# silently merged one ship's deck into the other's. (2) The same owner's
# room re-minted under a fresh key ("deck_three" for an existing "Deck 3")
# created a live duplicate that only the advisory remove_rooms self-heal
# might later clean up. The registry is the normalized `room_registry`
# table (Phase 2; it supersedes Phase 1's derived lore_entries encoding):
# one row per room ever minted, keyed (chat_id, room_uid), scoped to its
# owning vehicle/location book. It is the sole cross-frame ledger of room
# IDENTITY, dedup, and retirement (Phase 3a) -- the frame-scoped scene JSON
# is the sole authority for LIVE rooms/positions, and the registry is a
# deterministic projection of every scene write: commit_scene maintains it
# in the same commit domain, and the manual world editor reconciles it via
# sync_room_registry_with_scene below. Removal
# RETIRES a row (retired_turn_id = the removing turn) instead of deleting
# it, so a destroyed ship's decks remain retrievable history. Ledger,
# never a cage: a colliding mint is REDIRECTED or REKEYED, never rejected
# (invention is always allowed, duplication is not).

def _anchored_book_ids(cid):
    return {
        row["anchor_entity_id"]: row["id"]
        for row in q(
            "SELECT id, anchor_entity_id FROM lorebooks "
            "WHERE chat_id=? AND anchor_entity_id IS NOT NULL",
            (cid,),
        )
    }

def _room_display_slug(room_id, room_def):
    name = ""
    if isinstance(room_def, dict):
        name = str(room_def.get("name") or "")
    return normalize_room_id(name or str(room_id))

def _registry_alias_index(cid, book_id):
    """{normalized name/alias: room_uid} for every LIVE room registered
    under one owning book -- read from the room_registry table. Retired
    rows are excluded on purpose: dedup must never redirect a new mint
    onto a destroyed room's identity (a rebuilt deck is a new room; the
    ruin keeps its own retired row)."""
    index = {}
    for row in q(
        "SELECT room_uid, name, aliases FROM room_registry "
        "WHERE chat_id=? AND owning_book_id=? AND retired_turn_id IS NULL",
        (cid, book_id),
    ):
        try:
            aliases = json.loads(row["aliases"] or "[]")
        except Exception:
            aliases = []
        for alias in [row["name"], *aliases]:
            slug = normalize_room_id(str(alias or ""))
            if slug:
                index.setdefault(slug, row["room_uid"])
        index.setdefault(normalize_room_id(row["room_uid"]), row["room_uid"])
    return index

def _apply_room_renames(diff, renames):
    """Rewrite every reference to a renamed/redirected room key inside the
    diff: the rooms table itself, adjacency 'to' edges, positions, room
    removals, entity interior_rooms, and transit destinations."""
    rooms = diff.get("rooms")
    if isinstance(rooms, dict):
        for old, new in renames.items():
            if old not in rooms:
                continue
            moved = rooms.pop(old)
            existing = rooms.get(new)
            if isinstance(existing, dict) and isinstance(moved, dict):
                merged = dict(existing)
                for key, value in moved.items():
                    if value or key not in merged:
                        merged[key] = value
                rooms[new] = merged
            else:
                rooms[new] = moved
        for room in rooms.values():
            if not isinstance(room, dict):
                continue
            for edge in room.get("adjacent") or []:
                if isinstance(edge, dict) and edge.get("to") in renames:
                    edge["to"] = renames[edge["to"]]
    positions = diff.get("positions")
    if isinstance(positions, dict):
        for name, room in list(positions.items()):
            if room in renames:
                positions[name] = renames[room]
    if isinstance(diff.get("remove_rooms"), list):
        diff["remove_rooms"] = [
            renames.get(r, r) for r in diff["remove_rooms"]
        ]
    for edge in diff.get("remove_adjacent") or []:
        if isinstance(edge, dict):
            if edge.get("room") in renames:
                edge["room"] = renames[edge["room"]]
            if edge.get("to") in renames:
                edge["to"] = renames[edge["to"]]
    for ent in (diff.get("entities") or {}).values():
        if not isinstance(ent, dict):
            continue
        if isinstance(ent.get("interior_rooms"), list):
            ent["interior_rooms"] = [
                renames.get(r, r) for r in ent["interior_rooms"]
            ]
        state = ent.get("state")
        transit = state.get("transit") if isinstance(state, dict) else None
        if isinstance(transit, dict):
            for field in ("destination_room", "route_room"):
                if transit.get(field) in renames:
                    transit[field] = renames[transit[field]]

def normalize_offscreen_events(events):
    """Coerce a beat's off-screen ticks to one shape: [{actor, tick}].

    `MappingCommitOut.offscreen_events` is typed `list[dict]` with no inner
    model, so the model invented a shape per call and the stored logs prove it:
    across eight live chats the same field holds `{actor, tick}`, `{event}`,
    `{who, event}` and `{description}`. Nothing read the log, so nothing
    noticed — and the first reader would have had to handle all four, or
    silently miss three.

    An actor is optional and stays empty when the tick names none: inventing
    one would be worse than admitting the tick is about the world rather than
    about a person.
    """
    if not isinstance(events, list):
        return []
    out = []
    for entry in events:
        if isinstance(entry, str):
            text, actor = entry, ""
        elif isinstance(entry, dict):
            text = next(
                (str(entry[k]) for k in ("tick", "event", "description",
                                         "text", "summary")
                 if entry.get(k)), "")
            actor = next(
                (str(entry[k]) for k in ("actor", "who", "name", "character")
                 if entry.get(k)), "")
        else:
            continue
        text = " ".join(text.split())
        if not text:
            continue
        out.append({"actor": actor.strip(), "tick": text[:600]})
    return out


def dedup_minted_rooms(cid, prev_scene, diff, add_warning=None):
    """Structural dup prevention at creation time. For each room key the
    diff mints, check the CURRENT CONTAINMENT SCOPE (rooms sharing the same
    parent_entity owner -- None = the open location -- plus the owning
    book's registry aliases) before accepting it:

    - same key, DIFFERENT declared owner than the existing room (the
      two-ship 'deck_3' class): the incoming room is a new room of ITS
      owner colliding on a flat key -- REKEY it to an owner-scoped id;
    - new key whose name/alias collides with an existing room of the SAME
      scope (a re-mint of 'Deck 3' as 'deck_three'): REDIRECT the diff onto
      the existing id instead of minting a duplicate.

    Mutates `diff` in place (rewriting the room key and every reference:
    positions, adjacency, interiors, transit) and returns {old: new}.
    Never rejects a genuinely new room -- ledger, not cage. The advisory
    remove_rooms self-heal in prepare_scene_commit stays as the backstop
    for duplicates that predate this check.
    """
    rooms = diff.get("rooms")
    if not isinstance(rooms, dict) or not rooms:
        return {}
    prev_rooms = prev_scene.get("rooms") or {}
    anchor_books = _anchored_book_ids(cid)
    registry_cache = {}
    renames = {}
    taken = set(prev_rooms) | set(rooms)

    def unique_key(base):
        candidate = base
        suffix = 2
        while candidate in taken:
            candidate = f"{base}_{suffix}"
            suffix += 1
        taken.add(candidate)
        return candidate

    for rid in list(rooms.keys()):
        rdef = rooms[rid]
        if not isinstance(rdef, dict):
            continue
        incoming_owner = rdef.get("parent_entity")
        existing = prev_rooms.get(rid)
        if isinstance(existing, dict):
            existing_owner = existing.get("parent_entity")
            if incoming_owner and existing_owner \
                    and incoming_owner != existing_owner:
                new_id = unique_key(
                    normalize_room_id(f"{incoming_owner}_{rid}"))
                renames[rid] = new_id
                if add_warning:
                    add_warning(
                        f"Room key collision: '{rid}' already belongs to "
                        f"{existing_owner!r}; the new room declared for "
                        f"{incoming_owner!r} was rekeyed to '{new_id}'."
                    )
            continue
        # Brand-new key: name/alias dedup within the same containment scope.
        slug = _room_display_slug(rid, rdef)
        rid_slug = normalize_room_id(rid)
        match = None
        for prev_id, prev_def in prev_rooms.items():
            if not isinstance(prev_def, dict):
                continue
            if prev_def.get("parent_entity") != incoming_owner:
                continue
            if _room_display_slug(prev_id, prev_def) == slug \
                    or normalize_room_id(prev_id) in (slug, rid_slug):
                match = prev_id
                break
        if match is None and incoming_owner in anchor_books:
            book_id = anchor_books[incoming_owner]
            if book_id not in registry_cache:
                registry_cache[book_id] = _registry_alias_index(cid, book_id)
            registered = registry_cache[book_id].get(slug) \
                or registry_cache[book_id].get(rid_slug)
            if registered and registered in prev_rooms:
                match = registered
        if match and match != rid:
            renames[rid] = match
            if add_warning:
                add_warning(
                    f"Duplicate room mint: '{rid}' matches existing room "
                    f"'{match}' in the same scope; redirected instead of "
                    "minting a duplicate."
                )

    if renames:
        _apply_room_renames(diff, renames)
    return renames

def _prepare_room_registry(cid, canon_book_id, prev_scene, sc):
    """Build this commit's room_registry mutations -- pure reads only, so
    it runs in preparation, before the write lock. Each live room registers
    under its owning book: parent_entity rooms under the entity's anchored
    book; open-location rooms under the book whose scope_location_id
    matches the location (falling back to chat canon).

    Retire-not-delete: a room that was live in THIS frame's pre-turn scene
    but is absent from the post-merge scene lost its live existence this
    beat (diff remove_rooms, the mapping remove_rooms self-heal, or
    destruction) -- its registry row is marked retired, never deleted.
    Diffing prev vs post scene (rather than registry vs scene) is what
    keeps this frame-safe: rooms living only in a SIBLING frame's scene
    are simply never mentioned, so their rows are left untouched."""
    rooms = sc.get("rooms") or {}
    anchor_books = _anchored_book_ids(cid)
    location_slug = normalize_room_id(str(sc.get("location") or ""))
    location_book = None
    if location_slug:
        # retired_turn_id filter: rooms minted after a region's
        # destruction must not register under the dead book -- they fall
        # back to chat canon (the ruin's registry is closed history).
        row = q(
            "SELECT id FROM lorebooks WHERE chat_id=? AND "
            "scope_location_id=? AND retired_turn_id IS NULL "
            "ORDER BY id LIMIT 1",
            (cid, location_slug), one=True,
        )
        location_book = row["id"] if row else None
    default_book = location_book or canon_book_id

    existing = {
        row["room_uid"]: row
        for row in q("SELECT * FROM room_registry WHERE chat_id=?", (cid,))
    }

    upserts = []
    for rid, rdef in rooms.items():
        if not isinstance(rdef, dict):
            continue
        rid = str(rid)
        owner = rdef.get("parent_entity")
        book_id = anchor_books.get(owner) if owner else default_book
        if not book_id:
            continue
        name = str(rdef.get("name") or rid)
        row = existing.get(rid)
        # Aliases ACCUMULATE across renames (old names kept, new appended):
        # identity is the registry's whole job, so a room re-minted under a
        # name it carried three beats ago must still dedup onto its row.
        prior = []
        if row is not None:
            try:
                prior = list(json.loads(row["aliases"] or "[]"))
            except Exception:
                prior = []
        aliases = list(dict.fromkeys(
            [*prior, name, rid.replace("_", " ")]))
        if row is not None \
                and row["owning_book_id"] == book_id \
                and row["parent_entity"] == owner \
                and row["name"] == name \
                and row["aliases"] == json.dumps(aliases) \
                and row["retired_turn_id"] is None:
            continue  # already registered, identical, live
        upserts.append({
            "room_uid": rid, "owning_book_id": book_id,
            "parent_entity": owner, "name": name, "aliases": aliases,
        })

    prev_rooms = {str(r) for r in (prev_scene.get("rooms") or {})}
    retire = sorted(
        rid for rid in prev_rooms - {str(r) for r in rooms}
        if rid in existing and existing[rid]["retired_turn_id"] is None
    )
    return {"upserts": upserts, "retire": retire}


def _apply_room_registry(cid, turn_id, registry):
    """Write the prepared registry mutations (inside commit_scene's
    transaction). Upsert revives a retired row when the same key is
    genuinely re-minted live -- same key in the same chat is the same
    identity; the registry records that it exists again."""
    for rid in registry.get("retire") or []:
        qi(
            "UPDATE room_registry SET retired_turn_id=? "
            "WHERE chat_id=? AND room_uid=? AND retired_turn_id IS NULL",
            (turn_id, cid, rid),
        )
    for row in registry.get("upserts") or []:
        qi(
            "INSERT INTO room_registry"
            "(chat_id,room_uid,owning_book_id,parent_entity,name,aliases,"
            "payload,created_turn_id,retired_turn_id) "
            "VALUES(?,?,?,?,?,?,?,?,NULL) "
            "ON CONFLICT(chat_id,room_uid) DO UPDATE SET "
            "owning_book_id=excluded.owning_book_id,"
            "parent_entity=excluded.parent_entity,"
            "name=excluded.name,"
            "aliases=excluded.aliases,"
            "retired_turn_id=NULL",
            (cid, row["room_uid"], row["owning_book_id"],
             row["parent_entity"], row["name"], json.dumps(row["aliases"]),
             "{}", turn_id),
        )

def sync_room_registry_with_scene(cid, canon_book_id, prev_scene, scene):
    """Reconcile the room_registry projection with a scene blob replaced
    OUTSIDE commit_scene (the manual world editor in app.py's world_put --
    the one scene writer that historically bypassed the registry, leaving
    hand-added rooms unregistered until the next commit and hand-removed
    rooms live in the registry forever). Same prepare/apply pair the commit
    domain uses, so the projection semantics cannot fork.

    Rooms that lost live existence are retired stamped with the chat's
    latest turn (a manual edit has no turn of its own); with no turns yet
    there is nothing meaningful to retire against and the retire pass is a
    no-op, while registration still proceeds."""
    registry = _prepare_room_registry(cid, canon_book_id, prev_scene, scene)
    latest = q("SELECT id FROM turns WHERE chat_id=? ORDER BY idx DESC LIMIT 1",
               (cid,), one=True)
    if latest is None:
        registry["retire"] = []
    _apply_room_registry(cid, latest["id"] if latest else None, registry)
    return registry


def _refresh_relocated_location(sc, prev_scene, diff, ctx):
    """Refresh scene.location when the player has CHANGED rooms this turn. See
    the DW-1 call site in prepare_scene_commit.

    Originally scoped to relocations into a NEWLY-MINTED room (DW-1: mapping
    coins a fresh destination and the label still names the old place). But a
    move into a room that ALREADY EXISTED needs the same refresh -- beaming
    back aboard from a planet surface (TR-3) left the label reading 'Sigma
    Draconis VII -- Surface' while every position was in the ship's transporter
    room. The trigger is therefore the player's room changing, not the room
    being new.
    """
    try:
        from scene import persona_of
        player_name = persona_name(persona_of(ctx.chat))
    except Exception:
        return
    player_room = _room_of(sc, player_name)
    if not player_room:
        return
    if player_room == _room_of(prev_scene, player_name):
        return  # no move -- label stays put
    rooms = sc.get("rooms") or {}
    cur_loc = str(sc.get("location") or "").strip()
    # Refresh only when the label is actually stale for the destination:
    #   - the destination room is BRAND NEW to the scene (DW-1: mapping minted
    #     it and the label still names the old place), or
    #   - the current label still names a SPECIFIC room the player has now LEFT
    #     (TR-3: 'Sigma Draconis VII -- Surface' while aboard the ship).
    # A venue-level label that matches no room (e.g. 'The Old Anchor' with rooms
    # 'Bar'/'Kitchen') is deliberately left alone on an in-venue room move.
    new_room = player_room not in (prev_scene.get("rooms") or {})
    names_left_room = any(
        cur_loc and cur_loc == str((r or {}).get("name") or "").strip()
        and rid != player_room
        for rid, r in rooms.items())
    if not (new_room or names_left_room):
        return
    # Prefer a location the Director named this turn, else the destination's name.
    new_loc = str(diff.get("location") or "").strip() \
        or str((rooms.get(player_room) or {}).get("name") or "").strip()
    if new_loc and new_loc != cur_loc:
        sc["location"] = new_loc
    # scene.description is the label's prose sibling and was only ever written
    # from director_establish -- i.e. once, on the opening turn, and then never
    # again. Live (Elevator Adventure branch 41) it still described the surface
    # elevator bay 92 turns later, with the party in a sub-basement chamber.
    # Nothing reads it back today, so this is a latent staleness rather than an
    # observed leak, but it is exactly what DW-1 fixed for `location` and the
    # same trigger applies.
    new_desc = str(diff.get("description") or "").strip() \
        or str((rooms.get(player_room) or {}).get("desc") or "").strip()
    if new_desc:
        sc["description"] = new_desc


def prune_dangling_exits(sc):
    """Drop room exits whose target room does not exist. Returns warnings.

    The merge already drops edges pointing at rooms it just REMOVED, but never
    checked that an edge's target exists in the first place, so a model naming
    a room it never defined committed a permanent broken exit. Found live in
    "The Doctor — Hinami": the janitor closet carried an exit to
    `enterprise_corridor` while only `enterprise_corridor_deck10` and
    `_deck14` existed.

    A dangling exit is not cosmetic. spatial.py treats `adjacent` as the
    authority on what leaves a room, so the exit is offered to the Director and
    the narrator as real, movement through it resolves against a room with no
    description or position, and pathing counts a neighbour that cannot be
    reached. Dropping is the conservative repair: the edge described a place
    the world never had.
    """
    warnings = []
    rooms = sc.get("rooms")
    if not isinstance(rooms, dict):
        return warnings
    for rid, room in rooms.items():
        if not isinstance(room, dict) or not isinstance(room.get("adjacent"), list):
            continue
        kept, dropped = [], []
        for edge in room["adjacent"]:
            if not isinstance(edge, dict):
                continue
            target = edge.get("to")
            if target in rooms:
                kept.append(edge)
            else:
                dropped.append(str(target))
        if dropped:
            room["adjacent"] = kept
            warnings.append(
                "scene: dropped exit(s) from %s to undefined room(s) %s"
                % (rid, ", ".join(sorted(set(dropped)))))
    return warnings


def _heal_attire_identity_keys(sc, cast):
    """Collapse scene.attire onto one key per character, and return the
    function that canonicalizes an incoming key.

    A character legitimately answers to several scene keys -- display name,
    identity.uid, aliases (agents.common.character_scene_keys) -- and the
    Director keys attire with whichever it reaches for. Positions survived
    that because readers try every key (character_room) and duplicates get
    collapsed (spatial._dedup_duplicate_position_keys); attire got neither,
    and every reader (scene.appearance_of, agents/character.py) looks under
    the display NAME alone. Observed live (Elevator Adventure branch 41):
    Dr. Moon held two records -- `char_f0ef86a7...` with her lab coat,
    shirt, trousers and loafers, and `Dr. Moon` with `wearing: []` -- so
    she rendered as wearing nothing while her clothing STATE still read
    "lab coat ripped at the hem".

    Merging (rather than preferring one) is what makes this heal an
    existing save: whichever record holds the clothes keeps them.
    """
    from agents.common import character_scene_keys

    alias_to_canonical = {}
    # A name somebody actually GOES BY, as opposed to also answers to. One
    # character's alias is another's name often enough in fiction -- a nickname,
    # a family name, a title -- and folding on it merges two bodies. Measured:
    # with a character named Yuki and a second whose aliases include "Yuki",
    # this collapsed Yuki's wardrobe onto the other woman, who was wearing
    # nothing and acquired a yukata; Yuki's own record disappeared.
    own_names = set()
    for row in cast or []:
        try:
            keys = character_scene_keys(json.loads(row["sheet"]))
        except Exception:
            continue
        if keys:
            own_names.add(keys[0].casefold())

    for row in cast or []:
        try:
            keys = character_scene_keys(json.loads(row["sheet"]))
        except Exception:
            continue
        if not keys:
            continue
        for key in keys[1:]:
            folded = key.casefold()
            # A registered name always outranks somebody else's alias for it.
            if folded in own_names and folded != keys[0].casefold():
                continue
            alias_to_canonical[folded] = keys[0]

    def canonical(name):
        return alias_to_canonical.get(str(name or "").strip().casefold(), name)

    attire = sc.get("attire")
    if isinstance(attire, dict):
        for key in [k for k in attire if canonical(k) != k]:
            record = attire.pop(key)
            if not isinstance(record, dict):
                continue
            target = attire.setdefault(canonical(key),
                                       {"wearing": [], "state": []})
            if not isinstance(target, dict):
                continue
            for field in ("wearing", "state"):
                merged = list(target.get(field) or [])
                for item in record.get(field) or []:
                    if item not in merged:
                        merged.append(item)
                target[field] = merged

    return canonical


def _player_name_or_none(ctx):
    """The player's own name, or None if it cannot be resolved."""
    try:
        from scene import persona_of
        return persona_name(persona_of(ctx.chat)) or None
    except Exception:
        return None


def _beat_voices(ctx, res):
    """Every text this beat was acted in, EXCEPT the player's own input.

    What each character declared, plus the Director's resolved prose. The
    player's input is passed separately by the caller, because first person is
    only a reliable subject there -- "I rip my coat off" names its subject
    nowhere else in the sentence.

    Used only to decide how FAST an undressing the fiction has already asked
    for happens -- never who may know what -- so reading across all of it
    carries no information-firewall cost.
    """
    texts = []
    if isinstance(res, dict):
        texts.append(str(res.get("resolved_event") or ""))
    for result in (getattr(ctx, "character_results", None) or {}).values():
        if not isinstance(result, dict):
            continue
        for key in ("action", "speech"):
            texts.append(str(result.get(key) or ""))
        for element in result.get("sequence") or []:
            if isinstance(element, dict):
                for key in ("action", "speech", "text"):
                    texts.append(str(element.get(key) or ""))
    return [t for t in texts if t.strip()]


# How long a comma-led head may be and still read as a garment's name rather
# than as the first clause of a sentence about one.
_NOTE_NAME_HEAD = 40


def _garment_named_in(text, name):
    """Does this beat's prose actually mention the garment a note is minting?

    Matched on the head noun rather than the whole phrase: a note introduces
    "linen shift" and the prose says "the hem of your shift". Any word of the
    name that is long enough to be the garment itself counts, so a two-word
    name matches on either.
    """
    body = str(text or "").casefold()
    if not body:
        return False
    for word in re.findall(r"[a-z]+", str(name or "").casefold()):
        if len(word) >= 4 and re.search(rf"\b{re.escape(word)}s?\b", body):
            return True
    return False


def interpret_attire_notes(diff, worn, entry=None, prose=None):
    """Read an attire diff's free-form notes as the change they describe.

    `StateDiff.attire` had an untyped inner dict, and the commit loop below
    reads exactly `wearing`/`add`/`remove`/`replace`/`state`/`conditions`.
    Every other shape validated cleanly and then fell through the loop doing
    nothing at all. Two of the six attire diffs in the measured story were
    silent no-ops:

        {"Elyndra": {"robe": "sheer, parted"}}
        {"Hinami": {"shift": "linen shift, hem rucked up where her hand..."}}

    The second is why that story's narration could say "the hem of your shift"
    and "the waistband of your shorts" in one paragraph: the shift the prose
    had been describing since beat 0 never reached the ledger, which still held
    the travel clothes seeded off her card.

    Three readings, in order of how much they assume:

      1. the handle names a garment she is wearing -> what just happened to it,
      2. it names the wardrobe as a whole -> prose the body keeps, unless it
         says in as many words that nothing changed,
      3. it names a garment the ledger has never heard of -> she is wearing it
         now. The one-rung rule and the region tables then apply to it like
         anything else, and the Director sees it next beat to correct.

    Returns the diff with the notes folded into the fields the loop reads.
    `entry` is the body's live ledger entry, mutated only for reading 2.
    """
    diff = dict(diff or {})
    notes = diff.pop("notes", None)
    if not isinstance(notes, dict) or not notes:
        return diff
    marks = dict(diff.get("conditions") or {})
    notes_read = diff.setdefault("_notes_read", [])
    for handle, text in notes.items():
        text = str(text or "").strip()
        if not text or attire_model.is_no_change_note(text):
            continue
        garment = attire_model.resolve_garment(handle, worn)
        if garment is not None:
            marks.setdefault(garment, text)
        elif str(handle).casefold() in attire_model._GENERIC_WARDROBE_KEYS:
            if isinstance(entry, dict):
                entry["state"] = list(entry.get("state") or []) + [text]
        else:
            name, mark = attire_model.split_garment_name(text)
            # A note names the garment and then says what happened to it, and
            # the clause that follows is nearly always comma-led: "linen
            # shift, hem rucked up where her hand slipped beneath". Without
            # this the whole sentence becomes the garment's NAME, which is
            # also its matching key -- so the next beat's "shift" would not
            # find it and the fork would start all over again.
            if "," in name:
                head, _, rest = name.partition(",")
                if head.strip() and len(head.strip()) <= _NOTE_NAME_HEAD:
                    name, mark = head.strip(), (rest.strip() or mark)
            if attire_model.resolve_garment(name, worn) is not None:
                marks.setdefault(handle, text)
                continue
            # A note whose text is just a STATE is not naming a garment, it is
            # naming what happened to the handle. Reading it as reading 3 minted
            # a garment called "removed" -- literally, `{"name": "removed",
            # "state": "worn"}` on Hinami's torso -- and another called "worn"
            # on Elyndra's, each sitting in the ledger alongside the real
            # clothes and appearing in the `wearing` list the character reads.
            # A body wearing "removed" cannot reason about being dressed.
            #
            # `{"sandals": "removed"}` means the sandals came off, even when the
            # handle failed to resolve against the wardrobe; route it to the
            # field that says so rather than inventing a body part's worth of
            # new clothing named after a participle.
            if attire_model.is_bare_garment_state(name):
                if attire_model.is_removal_state(name):
                    diff.setdefault("remove", []).append(handle)
                    notes_read.append(
                        f"attire: read your note on {handle!r} as taking it off.")
                else:
                    diff.setdefault("add", []).append(handle)
                    marks.setdefault(handle, name)
                    notes_read.append(
                        f"attire: read your note on {handle!r} as putting it on.")
                continue
            # A note may only INTRODUCE a garment the beat's prose actually
            # mentions. Reading 3 exists for the case where the narration has
            # been describing a shift since beat 0 while the ledger still holds
            # the travel clothes off her card -- there, the prose says "shift"
            # and the note is catching the ledger up. It cannot otherwise tell
            # that from the Director simply imagining clothing, and the
            # difference is not structural: "linen shift, hem rucked up" and
            # "corset, unlaced and hanging open" are the same shape.
            #
            # What separates them is whether the story ever said it. Measured
            # on chat 52: a `corset` and a `skirt` reached Elyndra's ledger and
            # neither word appears in ANY of the 23 turns of narration. She was
            # carrying two garments the fiction had never mentioned, on top of
            # the four her card authors.
            #
            # `prose` omitted means no gate, so every existing caller and the
            # rerun path behave exactly as before.
            if prose is not None and not _garment_named_in(prose, name):
                notes_read.append(
                    f"attire: ignored your note on {handle!r} -- it would have "
                    f"put {name!r} on them, and this beat's prose never "
                    "mentions it. Use `add` if they really are wearing it.")
                continue
            diff.setdefault("add", []).append(name)
            if mark:
                marks.setdefault(name, mark)
            notes_read.append(
                f"attire: read your note on {handle!r} as putting {name!r} on "
                "them, since they were not wearing it.")
    if marks:
        diff["conditions"] = marks
    return diff


def _fold_duplicate_shed_garments(sc, diff=None, ctx=None):
    """Collapse several records of ONE shed garment into one. Idempotent.

    Adopt-or-mint stops new duplicates; it does not reach the ones already
    standing, because it only runs on a garment removed THIS beat. A scene
    that accumulated them keeps them forever otherwise -- chat 71 carried
    five records for two garments, minted across two stages and the commit
    seam, and every later beat would read all five.

    Conservative: same owner, all clothing, all shed, and
    `attire.resolve_garment` agreeing the names are the same garment. The
    survivor is the one that knows where it is (a positioned record is the
    thing on the floor); the others' condition and description are kept if
    the survivor has none. Two genuinely identical garments shed by one
    body in one scene would fold -- accepted deliberately, because the
    alternative is a permanent contradiction that compounds, and every fold
    is reported rather than silent.
    """
    from attire import resolve_garment

    if not isinstance(sc, dict):
        return
    entities = sc.get("entities")
    if not isinstance(entities, dict):
        return
    positions = sc.get("positions") or {}
    projected = diff.get("entities") if isinstance(diff, dict) else None

    groups = []
    for eid, entity in entities.items():
        state = entity.get("state") if isinstance(entity, dict) else None
        if not isinstance(state, dict) or not state.get("clothing") \
                or not state.get("shed"):
            continue
        owner = str(state.get("worn_by") or "").strip().casefold()
        name = str(entity.get("name") or "").strip()
        if not name:
            continue
        for group in groups:
            # An UNOWNED record joins an owned one: the model's own records
            # routinely carry no worn_by while the commit seam's mint does,
            # which is exactly the live shape (travel_shorts beside
            # travel_shorts_hinami). Two records naming DIFFERENT owners
            # never fold -- those are two bodies' garments.
            if group["owner"] and owner and group["owner"] != owner:
                continue
            if (resolve_garment(name, [group["name"]])
                    or resolve_garment(group["name"], [name])):
                group["ids"].append(eid)
                group["owner"] = group["owner"] or owner
                break
        else:
            groups.append({"owner": owner, "name": name, "ids": [eid]})

    for group in groups:
        if len(group["ids"]) < 2:
            continue
        keep = next((i for i in group["ids"] if positions.get(i)),
                    group["ids"][0])
        survivor = entities[keep]
        for eid in group["ids"]:
            if eid == keep:
                continue
            loser = entities.get(eid) or {}
            lost_state = loser.get("state") or {}
            s_state = survivor.setdefault("state", {})
            if lost_state.get("condition") and not s_state.get("condition"):
                s_state["condition"] = lost_state["condition"]
            if loser.get("description") and not survivor.get("description"):
                survivor["description"] = loser["description"]
            for alias in [loser.get("name")] + list(loser.get("aliases") or []):
                aliases = survivor.setdefault("aliases", [])
                if alias and isinstance(aliases, list) and alias not in aliases:
                    aliases.append(str(alias))
            entities.pop(eid, None)
            positions.pop(eid, None)
            if isinstance(projected, dict):
                projected.pop(eid, None)
        note = (
            f"objective state: {len(group['ids'])} entity records described "
            f"one shed garment ({group['name']!r}); they were folded into "
            f"{keep!r}. A garment that comes off is one object in the world.")
        if ctx is not None:
            ctx.tell_director(note)
            ctx.add_warning(note)


def _fold_worn_garment_entities(sc, diff, ctx=None):
    """WHILE IT IS WORN, THE ATTIRE LEDGER OWNS THE GARMENT.

    The mirror of adopt-or-mint. A specialist that needs to name a worn
    garment -- to wet it, to touch it -- cannot find one in `entities`,
    because a worn garment lives only in `sc.attire`. Measured live: the
    objects specialist minted `hinami_shorts` with `worn_by: Hinami` and
    `condition: damp` for exactly that reason, and its own note admitted
    it ("Created entity ... as it was not present in the provided
    entities"). That record then stood beside the attire ledger claiming
    the shorts were still worn while the ledger correctly had the body
    bare.

    So an entity claiming to be worn by a body whose attire ledger already
    carries that garment is folded away: its condition, the one thing it
    knows that the ledger might not, is written onto the garment in the
    ledger, and the duplicate record is dropped. Reported through
    tell_director every time -- the Director asked for a referent it did
    not have, and next beat it should know the answer was "the ledger has
    it".

    Layer 2 (the referent index) removes the pressure that creates these.
    This is the floor that holds whether or not a model cooperates.
    """
    from attire import resolve_garment

    if not isinstance(sc, dict):
        return
    entities = sc.get("entities")
    if not isinstance(entities, dict):
        return
    attire = sc.get("attire") or {}
    projected = diff.get("entities") if isinstance(diff, dict) else None
    for eid in list(entities):
        entity = entities.get(eid)
        if not _is_clothing_entity(entity):
            continue
        state = entity.get("state") or {}
        owner = str(state.get("worn_by") or "").strip()
        if not owner or state.get("shed"):
            continue          # shed records are the floor object; leave them
        entry = attire.get(owner)
        if not isinstance(entry, dict):
            continue
        worn = [str(n) for n in (entry.get("wearing") or []) if str(n).strip()]
        name = str(entity.get("name") or "").strip()
        if not name or not worn:
            continue
        match = resolve_garment(name, worn)
        if not match:
            continue
        condition = str(state.get("condition") or "").strip()
        if condition:
            _set_worn_garment_condition(entry, match, condition)
        entities.pop(eid, None)
        if isinstance(projected, dict):
            projected.pop(eid, None)
        (sc.get("positions") or {}).pop(eid, None)
        note = (
            f"objective state: an entity record {eid!r} claimed to be "
            f"{owner}'s worn {name!r}; while a garment is WORN the attire "
            f"ledger owns it, so the record was folded into "
            f"attire.{owner}'s {match!r}"
            + (f" (condition {condition!r} kept)" if condition else "")
            + ". Name a worn garment from the attire ledger rather than "
              "creating an object for it.")
        if ctx is not None:
            ctx.tell_director(note)
            ctx.add_warning(note)


def _set_worn_garment_condition(entry, garment_name, condition):
    """Put a condition on the named garment inside one attire entry."""
    for region in (entry.get("regions") or {}).values():
        if not isinstance(region, dict):
            continue
        for garment in (region.get("garments") or []):
            if isinstance(garment, dict) and \
                    str(garment.get("name") or "") == garment_name:
                garment["condition"] = condition


def _is_clothing_entity(entity):
    state = entity.get("state") if isinstance(entity, dict) else None
    return isinstance(state, dict) and bool(state.get("clothing"))


def _adopt_shed_record(entities, projected, owner, garment):
    """The id of an EXISTING record for this garment, or None to mint.

    Deliberately conservative: only clothing-flagged records, only those
    either unowned or owned by this same body, and only where
    `attire.resolve_garment` -- the engine's one garment-naming authority,
    already tuned against live wardrobes -- says the names are the same
    garment. Two records that both match fold to the first in scan order,
    which is deterministic because `entities` preserves insertion order.

    A wrong adoption is reported and visible; a wrong duplicate is silent
    and permanent, and compounds every beat. That asymmetry is why this
    resolves rather than requiring an exact key match.
    """
    from attire import resolve_garment

    name = str(garment)
    candidates = []
    for eid, entity in entities.items():
        if not _is_clothing_entity(entity):
            continue
        state = entity.get("state") or {}
        worn_by = str(state.get("worn_by") or "").strip()
        if worn_by and worn_by.casefold() != str(owner).casefold():
            continue
        handles = [str(entity.get("name") or "")]
        handles += [str(a) for a in (entity.get("aliases") or [])]
        handles = [h for h in handles if h.strip()]
        if not handles:
            continue
        if resolve_garment(name, handles) or any(
                resolve_garment(h, [name]) for h in handles):
            candidates.append(eid)
    return candidates[0] if candidates else None


def _stamp_shed(entity, garment, owner, condition):
    """Make an adopted record say what a minted one would have said."""
    if not isinstance(entity, dict):
        return
    state = entity.setdefault("state", {})
    state["clothing"] = True
    state["shed"] = True
    state.setdefault("worn_by", str(owner))
    if condition:
        state["condition"] = condition
    if not str(entity.get("name") or "").strip():
        entity["name"] = str(garment)
    entity.setdefault("kind", "object")
    entity.setdefault("portable", True)
    aliases = entity.setdefault("aliases", [])
    if isinstance(aliases, list) and str(garment) not in aliases:
        aliases.append(str(garment))


def _mint_shed_garments(sc, shed, diff=None):
    """A garment that has come off becomes a thing in the room.

    Clothes that vanish when removed cannot be picked up, taken, hidden or
    found again, and the story loses the shirt it just spent a beat on. Minted
    as an ordinary portable object, so everything that already works on objects
    -- being carried, being put inside a wardrobe or a chest, being seen --
    works on it with no further machinery. Placed where its wearer is standing;
    where it goes next is the story's business.

    Written into the beat's `diff` as well as the scene. `world_entities` is a
    DERIVED projection built from that diff, not from the scene blob, so an
    entity minted only here would live in the runtime scene and be absent from
    the normalized table -- the one divergence Phase 3a exists to prevent.
    """
    if not shed or not isinstance(sc, dict):
        return
    entities = sc.setdefault("entities", {})
    positions = sc.setdefault("positions", {})
    projected = diff.setdefault("entities", {}) if isinstance(diff, dict) else None
    for owner, garment, *rest in shed:
        condition = (rest[0] if rest else "") or ""
        key = re.sub(r"[^a-z0-9]+", "_", str(garment).casefold()).strip("_")
        if not key:
            continue
        key = "%s_%s" % (key, re.sub(r"[^a-z0-9]+", "_",
                                     str(owner).casefold()).strip("_"))[:60]
        if key in entities:
            continue
        # ADOPT BEFORE MINTING. The private "<garment>_<owner>" key above is
        # the only thing this seam ever checked, so a record the MODEL wrote
        # for the same garment -- under any other id -- was a sibling, not a
        # collision. Measured live (chat 71, one beat after the jacket
        # repair): five entity records for two garments, one of them still
        # carrying worn_by with no shed flag while the attire ledger
        # correctly showed the body bare. The garment is the same thing in
        # the fiction; it gets one record.
        adopted = _adopt_shed_record(entities, projected, owner, garment)
        if adopted:
            _stamp_shed(entities[adopted], garment, owner, condition)
            if projected is not None and adopted in projected:
                _stamp_shed(projected[adopted], garment, owner, condition)
            where = positions.get(owner)
            if where and not positions.get(adopted):
                positions[adopted] = where
            continue
        entities[key] = {
            "name": str(garment),
            "kind": "object",
            # What happened to it while it was being worn travels with it. A
            # shirt someone spilled wine down is a wine-stained shirt on the
            # floor, not a clean one -- the stain belongs to the garment.
            "description": "%s, taken off%s" % (
                str(garment), " — %s" % condition if condition else ""),
            "aliases": [str(garment)],
            "portable": True,
            "container": False,
            "interior_rooms": [],
            "state": {"clothing": True, "worn_by": str(owner), "shed": True,
                      **({"condition": condition} if condition else {})},
        }
        if projected is not None:
            projected.setdefault(key, entities[key])
        where = positions.get(owner)
        if where:
            positions[key] = where


def _advance_ground(cid, sc):
    """What the sky has left on each room's floor, after this beat.

    Deterministic and idempotent, like the weather drift it follows: same
    scene, same result, so a reroll does not re-mud a yard. Written to its own
    scene key rather than into `overlays`, which the Director authors -- engine
    bookkeeping and authored world-state should not be able to overwrite each
    other. Both the acoustic and the visual cache keys read it, so a yard that
    has turned to mud sounds and looks like one.
    """
    from scene import weather_severity
    from weather import ground_after, room_exposure, weather_for_room

    if not isinstance(sc, dict):
        return
    rooms = sc.get("rooms") or {}
    if not rooms:
        return
    severity = weather_severity(cid)
    previous = sc.get("ground") if isinstance(sc.get("ground"), dict) else {}
    ground = {}
    for room_id in rooms:
        state = ground_after(
            previous.get(room_id), weather_for_room(sc, room_id), severity,
            exposed=room_exposure(sc, room_id) == "open")
        if state:
            ground[room_id] = state
    if ground:
        sc["ground"] = ground
    else:
        sc.pop("ground", None)


def apply_attire_diff(sc, diff, ctx, res=None, *, report=True):
    """Apply one validated attire diff to a scene copy.

    This is the single attire projection used by both the pre-commit outcome
    preview and durable scene preparation.  Keeping it here prevents
    perception from approximating commit's alias resolution, decisive-removal
    rule, region derivation, and shed-object minting with a second spelling.
    ``sc`` and ``diff`` are caller-owned copies in the perception path.
    """
    if not isinstance(sc, dict) or not isinstance(diff, dict):
        return sc
    res = res or {}
    for recovered in attire_model.recover_shed_entity_changes(sc, diff):
        if recovered.get("position"):
            sc.setdefault("positions", {})[recovered["entity_id"]] = (
                recovered["position"])
        if report and recovered.get("garment"):
            ctx.tell_director(
                "attire: read explicitly shed clothing entity "
                f"{recovered['entity_id']!r} as removing "
                f"{recovered['garment']!r} from {recovered['owner']!r}.")

    att = sc.setdefault("attire", {})
    canonical_attire_key = _heal_attire_identity_keys(sc, ctx.cast)
    # WHOSE clothes this beat tore off, not merely whether somebody's did —
    # and whose undressing the prose leaves still IN PROGRESS. The two
    # readings share one attribution ladder (attire._attributed_targets) and
    # drive the inverted clamp: a resolved removal lands unless the body is
    # in the process set, and `decisive` still lifts everything.
    _attire_wardrobe = {
        _name: attire_model.flat_wearing(attire_model.normalize_regions(_entry))
        for _name, _entry in att.items() if isinstance(_entry, dict)}
    _decisive_names = attire_model.decisive_targets(
        getattr(ctx.turn, "player_input", "") or "",
        _beat_voices(ctx, res),
        _attire_wardrobe,
        player_name=_player_name_or_none(ctx),
    )
    _process_names = attire_model.process_targets(
        getattr(ctx.turn, "player_input", "") or "",
        _beat_voices(ctx, res),
        _attire_wardrobe,
        player_name=_player_name_or_none(ctx),
    )
    _shed = []
    _gained = set()
    for name, d in (diff.get("attire") or {}).items():
        name = canonical_attire_key(name)
        if not isinstance(d, dict):
            continue
        d = attire_model.coerce_diff_shape(d)
        cur = att.setdefault(name, {"wearing": [], "state": []})
        cur.setdefault("wearing", [])
        cur.setdefault("state", [])

        d = interpret_attire_notes(
            d, attire_model.flat_wearing(attire_model.normalize_regions(cur)),
            cur, prose=str(res.get("resolved_event") or ""))
        for _read in d.pop("_notes_read", None) or []:
            if report:
                ctx.tell_director(_read)
        if d.get("wearing") is not None and not any(
                d.get(k) for k in ("add", "remove", "replace")):
            cur["wearing"] = sanitize_attire_items(list(d.get("wearing") or []))
            if d.get("state") is not None:
                cur["state"] = (d["state"] if isinstance(d["state"], list)
                                else [d["state"]])
            if isinstance(d.get("regions"), dict) and d["regions"]:
                cur["regions"] = attire_model.normalize_regions(
                    {"wearing": cur["wearing"], "regions": d["regions"]})
        else:
            previous_names = list(cur["wearing"])
            if isinstance(d.get("replace"), list):
                replaced = []
                for handle in d["replace"]:
                    text = str(handle or "").strip()
                    canonical = attire_model.resolve_garment(
                        text, previous_names) or text
                    if canonical and canonical not in replaced:
                        replaced.append(canonical)
                cur["wearing"] = sanitize_attire_items(replaced)
            for handle in d.get("add") or []:
                text = str(handle or "").strip()
                canonical = attire_model.resolve_garment(
                    text, cur["wearing"]) or text
                if canonical and canonical not in cur["wearing"]:
                    cur["wearing"].append(canonical)
            cur["wearing"] = sanitize_attire_items(cur["wearing"])
            for handle in d.get("remove") or []:
                canonical = attire_model.resolve_garment(
                    handle, cur["wearing"])
                if canonical in cur["wearing"]:
                    cur["wearing"].remove(canonical)
                elif report:
                    # A `remove` naming nothing this body wears is a no-op --
                    # the resolver already refused the handle, so nothing was
                    # ever going to come off -- and it was a SILENT one, which
                    # let the emitter keep believing the ledger held garments
                    # it did not. Measured (chat 76, turn 57): the body
                    # specialist re-removed the "utility sash with pouches"
                    # taken off the beat before, and removed a "nightwear
                    # garment" this branch never added (the name is a parent
                    # branch's ledger bleeding into context). Surfaced on both
                    # channels, dropped rather than guessed: a legitimate
                    # alias resolves through `resolve_garment`'s tiers above
                    # and never reaches this branch, while forcing an
                    # unresolved handle through would remove a coin-flip
                    # garment. Wrongly keeping a garment on is recoverable
                    # next beat; wrongly removing one is not.
                    ctx.tell_director(
                        f"attire: `remove` named {handle!r} for {name}, but "
                        "nothing they are currently wearing answers to it "
                        f"(worn: {', '.join(cur['wearing']) or 'nothing'}). "
                        "Dropped as a no-op -- a garment already off the "
                        "body, or never on it, has no removal to apply. If a "
                        "worn garment was meant, name it as the ledger does.")
                    ctx.add_warning(
                        f"attire: dropped no-op removal of {handle!r} for "
                        f"{name} (not currently worn)")
            if d.get("state") is not None:
                cur["state"] = (d["state"] if isinstance(d["state"], list)
                                else [d["state"]])

        _before = attire_model.normalize_regions(cur)
        _marks = d.get("conditions")
        # THE STEAL GUARD (design note 17 §3): a coverage entry that empties
        # every region a garment covers, named by a removal-directed decisive
        # phrase in this beat's words, is the removal it plainly was — filed
        # on the displacement axis. Escalated through the normal remove path
        # so the ladder (lifted by the same decisive act) and the shed-object
        # minting both apply. An ambiguous phrase keeps its displacement
        # reading: wrongly holding a garment on the body is recoverable next
        # beat, wrongly removing it is not.
        _coverage = (d.get("coverage")
                     if isinstance(d.get("coverage"), dict) else {})
        if _coverage and name in _decisive_names:
            _beat_texts = ([getattr(ctx.turn, "player_input", "") or ""]
                           + list(_beat_voices(ctx, res)))
            _coverage = dict(_coverage)
            for _handle in attire_model.coverage_removal_escalations(
                    _beat_texts, _coverage, _before):
                _coverage.pop(_handle, None)
                _canonical = attire_model.resolve_garment(
                    _handle, cur["wearing"])
                if _canonical in cur["wearing"]:
                    cur["wearing"].remove(_canonical)
                if report:
                    ctx.tell_director(
                        f"attire: read the coverage claim on {_handle!r} as "
                        "the decisive removal this beat's words describe -- "
                        "a garment taken off the body is `remove`, not a "
                        "coverage change.")
        _wanted_before = list(cur["wearing"])
        _after = attire_model.apply_flat_change(
            _before, cur["wearing"], decisive=name in _decisive_names,
            conditions=_marks if isinstance(_marks, dict) else None,
            process=name in _process_names,
            # Where this beat says the garment went, when that is not where
            # its name implies. The region tables cover the ordinary case and
            # nothing beyond it, and the space beyond it has no bottom --
            # underwear on the head, a belt across the chest, a shirt worn as
            # trousers. Whoever put it on says where.
            placement=d.get("placement"))
        _after, _coverage_notes = attire_model.apply_coverage_changes(
            _after, _coverage)
        if report:
            for _coverage_note in _coverage_notes:
                ctx.tell_director(_coverage_note)
            # A removal the ladder held is said out loud (design note 17 §4):
            # the fiction may already believe the garment off, and a silent
            # clamp is how chat 68 stranded a tank top at `loosened` with no
            # later beat ever re-proposing it.
            for _held_name, _held_state in attire_model.removals_held(
                    _before, _after, _wanted_before):
                ctx.tell_director(
                    f"attire: the removal of {name}'s {_held_name!r} was "
                    f"held at {_held_state!r} because this beat's prose "
                    "reads as still in progress. When the act completes, "
                    "propose `remove` again with completed prose.")
                ctx.add_warning(
                    f"attire: removal of {name}'s {_held_name!r} held at "
                    f"{_held_state!r} (beat reads as in progress)")
            # A condition describing the garment ON a body is dropped when it
            # leaves one (design note 17 §6), and said out loud for the same
            # reason the clamp is: a stale "hanging off her shoulder" on a
            # garment lying on the floor had the Director remove the same
            # jacket twice and the narrator narrate it a third time.
            for _gone_name, _gone_cond in attire_model.worn_conditions_dropped(
                    _before, _after):
                ctx.tell_director(
                    f"attire: {name}'s {_gone_name!r} left the body, so its "
                    f"condition {_gone_cond!r} was dropped — it described the "
                    "garment's relationship to a body it is no longer on. "
                    "Any lasting damage belongs on the shed object.")
            # Displacement or rung words written ONLY as condition prose move
            # nothing (design note 17 §4) -- the chat 70 jacket and chat 68
            # t7 defects. Detected, never executed: the feedback names the
            # channel that does move state.
            _cov_handles = {
                (attire_model.resolve_garment(h, _wanted_before) or str(h))
                .casefold() for h in _coverage}
            for _handle, _text in ((_marks or {}).items()
                                   if isinstance(_marks, dict) else []):
                _resolved = (attire_model.resolve_garment(
                    _handle, _wanted_before) or str(_handle)).casefold()
                _rung_word = attire_model.rung_language(_text)
                if _rung_word:
                    ctx.tell_director(
                        f"attire: the condition on {name}'s {_handle!r} "
                        f"contains the ladder word {_rung_word!r}, which "
                        "moves nothing there. The ladder moves through "
                        "`remove`/a decisive act; a condition is what "
                        "happened to the fabric.")
                    ctx.add_warning(
                        f"attire: rung word {_rung_word!r} written into "
                        f"{name}'s condition prose")
                if (attire_model.displacement_language(_text)
                        and _resolved not in _cov_handles):
                    ctx.tell_director(
                        f"attire: the condition on {name}'s {_handle!r} "
                        "describes a coverage change the ledger cannot read "
                        "from prose. If the garment is displaced, also write "
                        "attire." + str(name) + ".coverage = "
                        "{" + repr(str(_handle)) + ": {<region>: [zones "
                        "still covered] or [] for none}}.")
                    ctx.add_warning(
                        f"attire: displacement described only in prose for "
                        f"{name}'s {_handle!r}; coverage unchanged")
        cur["regions"] = _after
        cur["wearing"] = attire_model.flat_wearing(_after)
        # A derived-shaped note is always ours to rebuild, current or not --
        # the same rule `rederive_entry` applies on every read path
        # (`attire.is_derived_state_note`; chat 52 carried three stale notes
        # at once and earned it). This seam used to keep a weaker hand-rolled
        # form: a stale "bare at the ..." was dropped only when the old
        # string was a SUBSTRING of the new note, i.e. only when the bare set
        # grew by appending regions in the same order. The moment a garment
        # re-covered a region, containment failed and the stale note survived
        # as though authored. Measured (chat 76, turns 57/59/60): the STORED
        # ledger held "bare at the head, arms", "bare at the head, torso,
        # arms, waist, groin, legs" and "bare at the head, arms, waist,
        # groin, legs" at once -- every reader healed the contradiction
        # through `rederive_entry` on the way out, while the stored shape,
        # which the attire panel, exports and checkpoints read raw, kept all
        # three. Rebuilt unconditionally, not gated on `_notes` being
        # non-empty: a body dressed again derives NO notes, and that is
        # exactly the beat the last "bare at the" note must leave on.
        # Authored prose survives -- keeping it is the point of `state`
        # being a list.
        _notes = attire_model.flat_state(_after)
        _authored = [
            n for n in (cur.get("state") or [])
            if isinstance(n, str) and n.strip() and n not in _notes
            and not attire_model.is_derived_state_note(n)
        ]
        cur["state"] = _notes + _authored
        _had = {g["name"].casefold()
                for entry in _before.values()
                for g in (entry.get("garments") or [])
                if g.get("state") != "removed"}
        for _entry in _after.values():
            for _g in _entry.get("garments") or []:
                if (_g.get("state") != "removed"
                        and _g["name"].casefold() not in _had):
                    _gained.add(_g["name"].casefold())
        for _region, _garment in attire_model.newly_removed(_before, _after):
            _shed.append((name, _garment,
                          attire_model.condition_of(_after, _garment)))

    _fold_worn_garment_entities(sc, diff, ctx)
    _mint_shed_garments(
        sc, [s for s in _shed if s[1].casefold() not in _gained], diff)
    # Heals scenes that accumulated duplicates BEFORE adopt-or-mint
    # existed, and is idempotent, so it costs nothing on a clean scene.
    _fold_duplicate_shed_garments(sc, diff, ctx)
    # A REMOVED GARMENT IS AN OBJECT IN THE WORLD, NOT A FACT ABOUT A BODY.
    # It kept a seat in its former wearer's regions -- `state: "removed"`,
    # under `torso`/`waist`/`arms` -- and every relation that seat carried was
    # a relation to a body it had left. The floor object above is the garment
    # now; two records of one thing is how they disagree.
    #
    # Measured live (chat 70): the jacket sat `removed` across three of
    # Hinami's regions while lying on the stone in another room, so the
    # Director removed it a second time and the narrator narrated it a third.
    #
    # AFTER the mint, never before: `newly_removed` reads the transition out
    # of these very entries, so pruning earlier would mean nothing ever
    # reached the floor. Once the object exists, the seat is a duplicate --
    # and the region is simply uncovered, free to be filled by any attire,
    # makeshift or otherwise.
    for _name, _entry in (sc.get("attire") or {}).items():
        if isinstance(_entry, dict):
            attire_model.release_removed_garments(_entry)
    return sc


def _monotonic_elapsed(prev_clock, time_diff):
    """The story clock this beat's time diff yields. TIME DOES NOT RUN
    BACKWARDS.

    `end_seconds` is an absolute position on the story clock, and a model
    that emits `start_seconds: 0` every beat -- an easy and entirely natural
    reading of a field named "start" -- resets the world to the length of its
    own beat, over and over. Measured on a fifty-beat quest with several
    explicit hour-long skips: the clock finished at 30.0 seconds while its
    own display read "an hour and a half", and everything windowed on seconds
    went quiet with it -- routine residue never fired once, because the gap
    between a room's last sighting and now was always zero.

    The duration is still honoured when the absolute position is nonsense: a
    beat that took an hour advances the clock by an hour rather than being
    discarded, because the elapsed time is the part the fiction actually
    asserted.

    ONE helper on purpose: `prepare_memory_commit` reads the same diff to
    stamp affect/strain/belief windows, and reading the raw field there let
    a backwards beat window this beat's psychology on a clock the scene
    commit had already refused. Returns ``(elapsed_seconds, backwards)``
    where ``backwards`` is None or ``(claimed, was)`` for the caller's
    warning.
    """
    was = float((prev_clock or {}).get("elapsed_seconds", 0.0) or 0.0)
    td = time_diff if isinstance(time_diff, dict) else {}
    try:
        claimed = float(td.get("end_seconds", was))
    except (TypeError, ValueError):
        claimed = was
    if claimed < was:
        try:
            duration = max(0.0, float(td.get("duration_seconds", 0.0) or 0.0))
        except (TypeError, ValueError):
            duration = 0.0
        return was + duration, (claimed, was)
    return claimed, None


def prepare_scene_commit(ctx):
    """Build the exact post-turn scene without mutating durable state.

    Keeping scene preparation pure lets the top-level commit prepare memory
    embeddings and other slow derived work before SQLite's outer write
    transaction begins.  It also gives every later commit domain one stable
    post-diff scene instead of independently reconstructing it.
    """
    chat = ctx.chat
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    # Deep-copied before the dedup pass below rewrites room keys: the
    # resolve step/variant holding this diff was already persisted, and
    # mutating the shared dict would desync it from what was saved.
    diff = copy.deepcopy(res.get("state_diff") or {})
    prev_scene = wget(cid, "scene", {}) or {}
    # Carried beside prev_scene for the off-screen epoch. Once the scene
    # domain writes the new clock, a later commit domain cannot recover which
    # coarse time boundary THIS beat crossed. Keep the exact pre-turn value in
    # the prepared bundle instead of opening a second clock authority.
    prev_clock = copy.deepcopy(wget(
        cid, "simulation_clock", {"elapsed_seconds": 0.0, "display": "now"}
    ) or {"elapsed_seconds": 0.0, "display": "now"})
    destruction = _prepare_destruction(
        cid, prev_scene, diff, add_warning=ctx.add_warning)
    room_renames = dedup_minted_rooms(
        cid, prev_scene, diff, add_warning=ctx.add_warning)
    _guard_occupied_mover_removal(
        prev_scene, diff,
        doomed={destruction["target"]: destruction["doomed_rooms"]}
        if destruction else None)

    # Fold mapping's advisory MAP DETAIL (within-room `anchors`, `size`, and
    # compass `dir`/`vertical` on edges) into the Director's causal diff BEFORE
    # the merge -- so it passes through the merge's bearing reciprocity and
    # station-anchor normalization like any authored room, and a station keyed
    # to a mapping-authored anchor is not stranded by normalize_scene_stations
    # running on an anchorless room. Confirmed live: every model authored
    # anchors in scene_patch, but the Director drops them when echoing rooms
    # (like it drops remove_rooms below). Fill ONLY fields the Director's room
    # LACKS (it wins if it echoed them); apply room_renames so a rekeyed minted
    # room keeps its detail; never CREATE a room the Director itself didn't.
    _mapping_patch = ((ctx.mapping_stage or {}).get("scene_patch")
                      or (ctx.mapping_quick or {}).get("scene_patch") or {})
    _diff_rooms = diff.get("rooms")
    if isinstance(_diff_rooms, dict):
        for _rid, _mroom in (_mapping_patch.get("rooms") or {}).items():
            _droom = _diff_rooms.get(room_renames.get(_rid, _rid))
            if not isinstance(_droom, dict) or not isinstance(_mroom, dict):
                continue
            for _f in ("anchors", "size"):
                if _mroom.get(_f) and not _droom.get(_f):
                    _droom[_f] = _mroom[_f]
            _medges = {e.get("to"): e for e in (_mroom.get("adjacent") or [])
                       if isinstance(e, dict) and e.get("to")}
            for _edge in (_droom.get("adjacent") or []):
                _me = _medges.get(_edge.get("to")) if isinstance(_edge, dict) else None
                for _k in ("dir", "vertical"):
                    if _me and _me.get(_k) and not _edge.get(_k):
                        _edge[_k] = _me[_k]

    # Mapping's within-room placements, folded the same way and for the same
    # reason: it is the layout authority, so it is usually the first stage that
    # knows the room has a bed for anyone to be on. Per NAME, and only where
    # the Director said nothing about that body -- the Director owns causality
    # and wins wherever the two speak about the same person.
    _mstations = _mapping_patch.get("stations")
    if isinstance(_mstations, dict) and _mstations:
        _stations = diff.setdefault("stations", {})
        if isinstance(_stations, dict):
            for _who, _st in _mstations.items():
                if isinstance(_st, dict):
                    _stations.setdefault(_who, _st)

    _contact_report = []
    _substance_report = []
    sc = merge_scene_with_diff(
        prev_scene, diff, contact_report=_contact_report,
        substance_report=_substance_report.append)
    # Tell the Director how its contact ops were read -- a re-description taken
    # as the same limb moving, a part refused as not being one, an envelopment
    # folded onto the enclosed side. Corrections it can only make if it knows
    # the reading happened.
    #
    # THESE ARE SENTENCES, AND THIS LOOP USED TO UNPACK THEM AS PAIRS.
    # `apply_contact_ops` composes each report as a finished string -- it knows
    # what it re-read and why, and phrasing it there keeps the explanation next
    # to the decision. This consumer still destructured `(was, now)` and rebuilt
    # a message from the halves, which had stopped being the shape years of
    # reports ago.
    #
    # It did not fail loudly or always. A report of any length but two raised
    # "too many values to unpack (expected 2)" out of `_prepare_turn_commit`,
    # killing the whole beat -- and reported live as an intermittent
    # "Commit preparation failed" that a reroll of director_resolve cleared,
    # because a different beat writes different contact ops and most beats
    # write a report at all. A two-character report would have unpacked
    # silently into its own letters, which is the worse half of the same bug.
    for _note in _contact_report:
        ctx.tell_director(str(_note))
    for _note in _substance_report:
        ctx.add_warning(f"substance: {_note}")
    if destruction:
        # Guard-approved departures (cast_changes) left stale positions
        # that merge's occupied-room refusal honored; vacate them and
        # drop the doomed rooms they kept alive (see the vacated note in
        # _prepare_destruction). The guard has already proven every
        # doomed-room occupant repositioned or departed, so this pop can
        # never lose a person.
        for name in destruction.get("vacated") or []:
            (sc.get("positions") or {}).pop(name, None)
        for rid in destruction.get("doomed_rooms") or []:
            (sc.get("rooms") or {}).pop(rid, None)

    staged = (
        (ctx.mapping_stage or {}).get("staged_lore") or []
    ) + (
        (ctx.mapping_quick or {}).get("staged_lore") or []
    )
    interp = ctx.director_interpret or {}
    mv = interp.get("movement")
    target_room = mv.get("to_room") if isinstance(mv, dict) else None
    target_room = room_renames.get(target_room, target_room)

    if target_room and target_room not in sc.get("rooms", {}):
        # A DECLARED DESTINATION ALWAYS EXISTS. Going somewhere is the
        # strongest possible assertion that it is there -- stronger than
        # naming it, which is why this is keyed on movement rather than on
        # mention: a character can talk about Gallifrey all day without the
        # engine minting it, but the moment a body walks toward a place, the
        # place has to be somewhere for them to arrive.
        #
        # This used to happen ONLY as a side effect of lore staging: the room
        # was created if this turn's mapping happened to stage a `layout`
        # entry, and otherwise not at all. So a destination existed or not
        # depending on whether the lore layer had something to say about it,
        # and a mover could be sent to a room that was never created. Live
        # (chat 58): t25's movement targeted `alley_mouth`, an ANCHOR inside
        # `street_outside` rather than a room; nothing staged layout lore for
        # it, so nothing was made.
        _desc = next((entry["content"] for entry in staged
                      if entry.get("category") == "layout"
                      and entry.get("content")), "")
        # Somewhere to come back from. A room with no edges is unreachable
        # from every other room in the scene -- perception then treats it as
        # `separated`/`far`, which is how an interior falls out of the world.
        _origin = None
        _p_name = _player_name_or_none(ctx)
        _mover = str((mv or {}).get("mover") or "self").strip()
        _who = _p_name if _mover in ("", "self") else _mover
        for _key in (_who, _p_name):
            if not _key:
                continue
            _origin = (prev_scene.get("positions") or {}).get(_key)
            if _origin:
                break
        if not _origin:
            # The mover could not be named (no persona resolved, an unnamed
            # mover). Fall back to where the bodies actually were, because the
            # one outcome this must never produce is the disconnected room it
            # exists to prevent -- an unreachable destination is worse than an
            # edge drawn from the busiest room in the scene.
            _counts = {}
            for _room in (prev_scene.get("positions") or {}).values():
                if _room:
                    _counts[_room] = _counts.get(_room, 0) + 1
            _origin = max(_counts, key=_counts.get) if _counts else None
        sc.setdefault("rooms", {})[target_room] = {
            "name": target_room.replace("_", " ").title(),
            "desc": _desc,
            "adjacent": ([{"to": _origin, "barrier": "open",
                           "distance": "near"}]
                         if _origin and _origin in sc.get("rooms", {})
                         and _origin != target_room else []),
            "notes": _desc[:500],
        }

    # Mapping's scene_patch is advisory -- the Director is expected to fold
    # it into state_diff -- but models reliably echo room CREATIONS while
    # dropping remove_rooms cleanup (observed live: mapping proposed
    # remove_rooms for a duplicate room on two consecutive turns and the
    # resolve diff carried neither, so the stray room persisted forever).
    # Room removal is map curation, not causality, so the mapping agent's
    # removals apply deterministically here -- conservatively: never a room
    # this turn's diff (re)asserts, never an occupied room, never an entity
    # interior, never a room any transit state still targets.
    mapping_patch = ((ctx.mapping_stage or {}).get("scene_patch")
                     or (ctx.mapping_quick or {}).get("scene_patch") or {})
    proposed_removals = [str(r) for r in (mapping_patch.get("remove_rooms")
                                          or []) if r]
    if proposed_removals:
        rooms = sc.get("rooms") or {}
        protected = set((diff.get("rooms") or {}).keys())
        protected.update(str(v) for v in (sc.get("positions") or {}).values())
        if target_room:
            protected.add(str(target_room))
        for ent in (sc.get("entities") or {}).values():
            if not isinstance(ent, dict):
                continue
            protected.update(str(r) for r in (ent.get("interior_rooms") or []))
            state = ent.get("state")
            transit = state.get("transit") if isinstance(state, dict) else None
            if isinstance(transit, dict):
                protected.add(str(transit.get("destination_room") or ""))
                protected.add(str(transit.get("route_room") or ""))
        removed = set()
        for rid in proposed_removals:
            room = rooms.get(rid)
            if rid in protected or not isinstance(room, dict) \
                    or room.get("parent_entity"):
                continue
            rooms.pop(rid)
            removed.add(rid)
        for room in rooms.values():
            if removed and isinstance(room, dict) and room.get("adjacent"):
                room["adjacent"] = [
                    e for e in room["adjacent"]
                    if not (isinstance(e, dict) and e.get("to") in removed)
                ]

    for k, v in (diff.get("overlays") or {}).items():
        cur = sc.setdefault("overlays", {}).setdefault(k, [])
        for it in (v if isinstance(v, list) else [v]):
            if it not in cur:
                cur.append(it)
        sc["overlays"][k] = cur[-6:]

    # An approach in flight. `MovementDecl.arrives=false` means the mover is
    # closing on somewhere and does not get there this beat; recording it is
    # what lets the NEXT declaration toward the same place arrive (see
    # agents/director._guard_approach_is_not_arrival). Without the record the
    # feature has no memory and an approach can never complete -- the engine
    # answers "you get closer" for as long as the player keeps asking.
    _mv = (ctx.director_interpret or {}).get("movement")
    if isinstance(_mv, dict) and _mv.get("to_room"):
        _who = _mv.get("mover") or "self"
        if _who == "self":
            try:
                from scene import persona_of
                _who = persona_name(persona_of(ctx.chat)) or "self"
            except Exception:
                _who = "self"
        # Keyed PER MOVER. One record for the whole scene meant two people
        # walking at once overwrote each other: multiplayer is supported, and
        # Ana heading for the tower never arrived because Bo was heading for
        # the gate. A skiff and its passenger can both be under way too.
        _pending = sc.setdefault("approach", {})
        if not isinstance(_pending, dict) or "who" in _pending:
            # The scene-global shape this replaced. Carry a live record over
            # rather than dropping the walker mid-stride.
            _old = _pending if isinstance(_pending, dict) else {}
            _pending = sc["approach"] = (
                {_old["who"]: {"to_room": _old.get("to_room"),
                               "turn": _old.get("turn")}}
                if _old.get("who") and _old.get("to_room") else {})
        if _mv.get("arrives", True):
            # Arrived, or was refused. Either way this mover is no longer
            # closing on anywhere.
            _pending.pop(_who, None)
        else:
            _pending[_who] = {"to_room": _mv["to_room"],
                              "turn": getattr(ctx.turn, "idx", None)}
        if not _pending:
            sc.pop("approach", None)
    # A BEAT THAT SAYS NOTHING ABOUT MOVEMENT NO LONGER ENDS THE WALK.
    #
    # It used to: "the walker stopped to do something else, and picking the
    # thread back up is a fresh declaration". That made travel survive only
    # by being re-declared every beat -- the sentence nobody wants to keep
    # writing -- and it is wrong about the commonest thing in fiction, which
    # is people talking while they walk. Live, chat 72: a beat spent grabbing
    # someone by the shoulders was read as abandoning a walk to the hotel
    # that was plainly still under way.
    #
    # Silence continues (agents/director._travel_continues advances the leg
    # and every movement backstop judges it). What retires a record is the
    # walk actually ENDING: arriving, or an interruption the Director
    # asserted. Both come back on `res["travel"]`, so the ledger and the
    # committed position are written from one answer and cannot disagree.
    _travel = res.get("travel") if isinstance(res, dict) else None
    if isinstance(sc.get("approach"), dict) and isinstance(_travel, dict):
        _pending = sc["approach"]
        if "who" in _pending:
            _old = _pending
            _pending = sc["approach"] = (
                {_old["who"]: {"to_room": _old.get("to_room"),
                               "turn": _old.get("turn")}}
                if _old.get("who") and _old.get("to_room") else {})
        _done = {str(n) for n in (_travel.get("arrived") or [])}
        _done |= {str(e.get("subject")) for e in (_travel.get("interrupted") or [])
                  if isinstance(e, dict) and e.get("subject")}
        for _name in _done:
            _pending.pop(_name, None)
        # Beats already spent on a long edge are carried on the record, so a
        # hike does not restart every time the walkers stop to talk.
        for _entry in (_travel.get("held") or []):
            if not isinstance(_entry, dict) or not _entry.get("edge_beats"):
                continue
            _leg = _pending.get(str(_entry.get("subject")))
            if isinstance(_leg, dict):
                _leg["edge_beats"] = int(_entry["edge_beats"])
        for _entry in (_travel.get("advanced") or []):
            _leg = _pending.get(str((_entry or {}).get("subject")))
            if isinstance(_leg, dict):
                _leg.pop("edge_beats", None)   # a new edge starts fresh
        if not _pending:
            sc.pop("approach", None)

    apply_attire_diff(sc, diff, ctx, res)

    est = ctx.director_establish
    if est:
        sc["location"] = est.get("location", sc.get("location"))
        sc["time"] = est.get("time", sc.get("time"))
        sc["description"] = est.get("scene_description", sc.get("description"))
        # An omitted sky means NO SKY, never a default one. The prompt tells
        # the Director to leave weather out where it is meaningless -- deep
        # space, a sealed habitat, an interior-only story -- and defaulting to
        # "fair" here would overrule that and give a starship weather to drift.
        # A story with no weather stays weatherless until a beat says otherwise,
        # and the drift below only ever moves a sky that already exists.
        opening_weather = normalize_weather(est.get("weather"))
        if opening_weather:
            sc["weather"] = opening_weather
    else:
        # DW-1: on a NORMAL turn scene.location was never refreshed, so after a
        # relocation to a genuinely new place (time travel, a new city) the
        # top-level label stayed stale and leaked the departed location's name
        # into perception/narration ("opens onto Bute Street" after landing in
        # 2003 Bethnal Green). Update it when the party has moved to a room
        # that did not exist before this turn: prefer a location the Director
        # named in the diff, else fall back to the new room's own name -- both
        # beat a stale, wrong label. Same-place moves (the room already
        # existed) leave the label untouched.
        _refresh_relocated_location(sc, prev_scene, diff, ctx)

    clock = None
    if diff.get("time"):
        td = diff["time"]
        if isinstance(td, dict):
            clock = copy.deepcopy(prev_clock)
            claimed, backwards = _monotonic_elapsed(prev_clock, td)
            if backwards is not None:
                ctx.add_warning(
                    "state_diff.time.end_seconds ran backwards (%.0f < %.0f); "
                    "advanced by its own duration instead" % backwards)
            clock["elapsed_seconds"] = claimed
            if td.get("display_advance"):
                clock["display"] = td["display_advance"]
            sc["time"] = td.get("display_advance", sc.get("time"))
        elif isinstance(td, str):
            sc["time"] = td

    # Weather. The Director's own change wins outright; otherwise the sky
    # drifts on the simulation clock, deterministically and idempotently, so a
    # reroll of this turn produces the same weather rather than a new one. AFTER
    # the clock block above, which is what supplies the elapsed time to drift
    # against.
    #
    # Written OVER the sky the scene already has, not in place of it. A
    # declaration is a beat reporting what it noticed, not a complete restatement
    # of the weather -- so a field it left out, or wrote in a word outside the
    # vocabulary, keeps what was blowing. Replacing wholesale meant a Director
    # who said "blizzard, heavy snow, severe, gale-force, sub-zero" -- every term
    # a synonym this vocabulary could not read -- cleared the sky it was trying
    # to describe. See `_SYNONYMS` in weather.py.
    declared = normalize_weather(diff.get("weather"), sc.get("weather"))
    if declared:
        sc["weather"] = declared
    elif sc.get("weather"):
        # Only a scene that HAS weather drifts. An earlier draft drifted
        # whenever no opening ran, which quietly gave every pre-existing chat a
        # sky on its next beat -- including the ones the prompt tells the
        # Director to leave weatherless (deep space, a sealed interior). A
        # story acquires weather when its fiction says so, never by default.
        elapsed = float((clock or wget(cid, "simulation_clock", {}) or {})
                        .get("elapsed_seconds") or 0.0)
        sc["weather"] = advance_weather(
            sc.get("weather"), elapsed, seed="chat:%s" % cid,
            cold=normalize_weather(sc.get("weather")).get("temperature") == "freezing")

    _advance_ground(cid, sc)

    infer_vehicle_zones(cid, ctx.turn.frame_id, prev_scene, sc)
    _carry_names = [character_name_from_text(c["sheet"]) for c in ctx.cast]
    infer_companion_carry(
        cid, ctx.turn.frame_id, prev_scene, sc,
        _carry_names,
        diff.get("cast_changes") or [],
    )
    # Per-character orientation (came_from + focus + facing), read by
    # egocentric_frame. Runs AFTER companion-carry so a carried companion's
    # inferred new position is already in sc when its came_from is computed;
    # infer_focus runs after infer_came_from (which clears focus on a
    # disorienting jump); infer_facing runs LAST -- it reads the freshly-set
    # came_from and focus to derive the compass heading left/right depends on.
    infer_came_from(cid, ctx.turn.frame_id, prev_scene, sc, _carry_names)
    # Reads the same before/after positions as came_from, and for the same
    # reason: a step through an OPAQUE boundary must be watchable from the room
    # behind for a beat or two instead of the body vanishing the instant its
    # position field changes.
    infer_threshold_crossings(cid, ctx.turn.frame_id, prev_scene, sc,
                              _carry_names)
    infer_focus(cid, ctx.turn.frame_id, prev_scene, sc,
                ctx.get("director_resolve") or {}, _carry_names)
    infer_facing(cid, ctx.turn.frame_id, prev_scene, sc, _carry_names)

    if destruction:
        base_clock = clock or wget(
            cid, "simulation_clock", {"elapsed_seconds": 0.0}) or {}
        _finalize_destruction_news(
            destruction, cid, ctx.turn.frame_id, ctx.turn,
            float(base_clock.get("elapsed_seconds") or 0.0))

    for _msg in prune_dangling_exits(sc):
        ctx.warnings.append(_msg)

    # G6: size stopped being flavour when perception started reading it.
    # `proximity_rel` needs it to say two people are `across` a room, and
    # S2a caps sight at `shapes` in a large room with no placement -- so a
    # room nobody sized is a perception grade the engine chose for itself.
    # It chooses silently, on 45% of live rooms. Say so on the beat the room
    # becomes shared -- once, not every beat the scene stays in it.
    for _room in guessed_room_sizes(sc, prev_scene):
        ctx.warnings.append(
            f"Room {_room['name']!r} holds {_room['occupants']} and has no "
            f"authored size; perception is grading it {_room['derived']!r} "
            + ("from a keyword in its own description"
               if _room["by_keyword"] else "by default")
            + f". Author scene_patch.rooms.{_room['room']}.size to set it.")

    return {
        "scene": sc, "clock": clock,
        # The post-dedup, post-destruction diff -- the SAME truth the merged
        # scene was built from. commit_world_entities derives the normalized
        # entity rows from this copy (never the raw step diff), so a room
        # rekeyed by dedup_minted_rooms or an entity removed by a
        # destruction declaration can't leave the world_entities projection
        # disagreeing with the scene blob (Phase 3a: one source of truth,
        # normalized tables are derived projections of it).
        "diff": diff,
        # The world as it stood before any of this beat committed. Carried
        # because the domains below run after commit_scene has already
        # persisted `sc`, so they cannot re-read "before" for themselves --
        # see _subjects_that_moved, which silently found nobody moving until
        # it was given this.
        "prev_scene": prev_scene,
        "prev_clock": prev_clock,
        "room_registry": _prepare_room_registry(
            cid, chat.lorebook_id, prev_scene, sc),
        "destruction": destruction,
    }


def commit_scene(ctx, nonce, *, prepared=None):
    prepared = prepared or prepare_scene_commit(ctx)
    sc = prepared["scene"]
    registry = prepared.get("room_registry") or {}
    with transaction():
        if prepared.get("clock") is not None:
            wset(ctx.chat.id, "simulation_clock", prepared["clock"])
        wset(ctx.chat.id, "scene", sc)
        sync_anchored_books(ctx.chat.id, sc)
        # Dual-write the room registry beside the scene blob, inside the
        # same commit domain (see the registry block comment): identity/
        # retirement bookkeeping, never a second authority over live rooms.
        _apply_room_registry(ctx.chat.id, ctx.turn.id, registry)
        if prepared.get("destruction"):
            _apply_destruction(
                ctx.chat.id, ctx.turn.id, prepared["destruction"])
        _record_subject_last_seen(ctx, sc, prepared.get("clock"))
    return sc


def _record_subject_last_seen(ctx, sc, clock):
    """Stamp everyone co-present with the player this beat, by subject id.

    The one new piece of state the lazy gap rung requires (proposal section
    1.2 step 2): nothing recorded last-seen before this, so re-contact had no
    since-turn to ask `gaps.gap_for` about. Merge, never replace -- a subject
    elsewhere this beat keeps their older stamp, that being the whole point.
    Failure is contained: a broken sighting ledger must not roll back a
    turn's scene commit, but it must not vanish either.
    """
    try:
        from gaps import LAST_SEEN_KEY, last_seen_update
        from scene import persona_of
        elapsed = float((clock or wget(ctx.chat.id, "simulation_clock", {}) or {})
                        .get("elapsed_seconds") or 0.0)
        updates = last_seen_update(
            sc, ctx.cast, persona_name(persona_of(ctx.chat)),
            ctx.turn.idx, elapsed)
        if updates:
            ledger = wget(ctx.chat.id, LAST_SEEN_KEY, {}) or {}
            ledger.update(updates)
            wset(ctx.chat.id, LAST_SEEN_KEY, ledger)
    except Exception as exc:
        ctx.add_warning(f"subject_last_seen not recorded: {exc}")

# ---- Mechanics sweep: timed arrivals, expiry, news, engine notices ----

def commit_transit_sweep(ctx, nonce, *, prepared=None):
    """Commit-domain wrapper around mechanics.mechanics_sweep, run FIRST
    among commit_all's domains -- the sweep mutates the PREPARED scene, and
    commit_scene (which runs after it) is what persists those effects.

    The ordered passes themselves -- (a) fire due scheduled events for THIS
    frame (transit arrivals + news arrivals), (b) schedule new arrivals,
    (c) condition expiry, (d) dock-edge recompute, (e) vehicle-zone/
    companion-carry inference -- live in mechanics.py (see its module
    docstring for the contract). This wrapper only feeds it the database
    rows and applies the event_ops it returns: all writes run inside the
    caller's transaction (nested transaction() is a savepoint), and
    checkpoint restore snapshots scheduled_events/world_conditions whole,
    so a rerolled turn reproduces the exact pending/fired state.
    """
    cid = ctx.chat.id
    frame_id = ctx.turn.frame_id
    prepared = prepared or prepare_scene_commit(ctx)
    sc = prepared["scene"]
    clock = prepared.get("clock") or wget(cid, "simulation_clock", {}) or {}
    res = ctx.director_resolve or ctx.director_establish or {}
    diff = res.get("state_diff") or {}
    cast_names = [character_name_from_text(c["sheet"]) for c in ctx.cast]

    # The player's room in the PREPARED scene -- after this beat's movement
    # merged -- so a consequence landing exactly where the party now stands
    # is a walk-in (notice) and one anywhere else stays unencountered state.
    # Read for the presence gate only; nothing about the fuse's content or
    # priority may depend on the player (living_world's header contract).
    _player_room = None
    try:
        from scene import persona_of
        _player_room = _room_of(sc, persona_name(persona_of(ctx.chat)))
    except Exception:
        pass

    with transaction():
        pending = [dict(r) for r in q(
            "SELECT * FROM scheduled_events WHERE chat_id=? AND "
            "status='pending' AND kind IN "
            "('transit_arrival','news_arrival','consequence') "
            "ORDER BY due_at",
            (cid,),
        )]
        conditions = [dict(r) for r in q(
            "SELECT condition_id, expires_at FROM world_conditions "
            "WHERE chat_id=? AND active=1",
            (cid,),
        )]
        prev_scene = wget(cid, "scene", {}) or {}

        _, event_ops, notices = mechanics_sweep(
            sc, clock, frame_id, pending,
            conditions=conditions, prev_scene=prev_scene, chat_id=cid,
            turn_id=ctx.turn.id, turn_idx=ctx.turn.idx,
            cast_names=cast_names,
            cast_changes=diff.get("cast_changes") or [],
            player_room=_player_room,
        )

        kind_by_id = {row["event_id"]: row["kind"] for row in pending}
        row_by_id = {row["event_id"]: row for row in pending}
        fired = scheduled = expired = news_fired = consequences_fired = 0
        fired_consequence_rows = []
        fired_events = []
        for op in event_ops:
            if op[0] == "status":
                _, event_id, status = op
                # chat_id in the WHERE: event ids are per-chat since the
                # (chat_id, event_id) repartition -- a same-install import
                # keeps the source chat's ids verbatim, so an unscoped
                # update would flip BOTH chats' rows.
                qtx("UPDATE scheduled_events SET status=? "
                    "WHERE chat_id=? AND event_id=?",
                    (status, cid, event_id))
                if status == "fired":
                    if event_id in row_by_id:
                        fired_events.append({
                            "event_id": event_id,
                            "kind": row_by_id[event_id]["kind"],
                            "location_id": row_by_id[event_id]["location_id"],
                            "occurred_at": row_by_id[event_id]["due_at"],
                            "payload": row_by_id[event_id]["payload"],
                            "seed": row_by_id[event_id]["seed"],
                        })
                    if kind_by_id.get(event_id) == "news_arrival":
                        news_fired += 1
                    elif kind_by_id.get(event_id) == "consequence":
                        consequences_fired += 1
                        if event_id in row_by_id:
                            fired_consequence_rows.append(row_by_id[event_id])
                    else:
                        fired += 1
            elif op[0] == "schedule":
                row = op[1]
                qtx(
                    "INSERT OR REPLACE INTO scheduled_events"
                    "(event_id,chat_id,due_at,kind,location_id,payload,seed,"
                    "status) VALUES(?,?,?,?,?,?,?,?)",
                    (row["event_id"], row["chat_id"], row["due_at"],
                     row["kind"], row["location_id"], row["payload"],
                     row["seed"], row["status"]),
                )
                scheduled += 1
            elif op[0] == "expire_condition":
                qtx("UPDATE world_conditions SET active=0 "
                    "WHERE chat_id=? AND condition_id=?", (cid, op[1]))
                expired += 1

        # Living world, approach B: mint this resolution's declared fuses.
        # Gated by the chat's setting (the mint is the feature's surface);
        # FIRING above is not gated -- rows exist only if minting was on,
        # and a story that turns the setting off keeps the consequences it
        # already caused, the way it keeps its scheduled arrivals.
        consequences_minted = 0
        try:
            from living_world import (living_world_allows,
                                      living_world_config,
                                      mint_consequences,
                                      record_obligations)
            _declared_fuses = diff.get("consequences") or []
            if living_world_allows(living_world_config(cid),
                                   "scheduled_consequence", "floor"):
                mint_rows, mint_warnings = mint_consequences(
                    cid, sc, frame_id, ctx.turn.id, ctx.turn.idx,
                    float((clock or {}).get("elapsed_seconds") or 0.0),
                    _declared_fuses,
                    player_room=_player_room)
                for row in mint_rows:
                    qtx(
                        "INSERT OR REPLACE INTO scheduled_events"
                        "(event_id,chat_id,due_at,kind,location_id,payload,"
                        "seed,status) VALUES(?,?,?,?,?,?,?,?)",
                        (row["event_id"], row["chat_id"], row["due_at"],
                         row["kind"], row["location_id"], row["payload"],
                         row["seed"], row["status"]),
                    )
                    consequences_minted += 1
                for warning in mint_warnings:
                    ctx.add_warning(f"consequence not minted: {warning}")
            elif _declared_fuses:
                # A silently swallowed declaration would look like a quiet
                # world; the ledger's whole failure history is mechanisms
                # that never fired and nothing saying so.
                ctx.add_warning(
                    f"{len(_declared_fuses)} declared consequence(s) "
                    "dropped: the scheduled-consequence setting is off "
                    "for this chat")
            # Approach D's feed: a fuse fired at an ungenerated place is
            # history that place now owes. Recorded regardless of the D
            # setting -- layer-1 truth accumulates; settings gate surfaces
            # (the honour seam in mapping), never truth.
            if fired_consequence_rows:
                record_obligations(cid, fired_consequence_rows)
        except Exception as exc:
            ctx.add_warning(f"living-world consequences not committed: {exc}")

        # What the deterministic layer made of this beat's output, in the
        # Director's own terms. Carried on the same channel as the mechanical
        # notices because it is the same kind of message: here is what
        # actually happened, as against what you asked for.
        notices = list(notices) + list(getattr(ctx, "engine_feedback", []) or [])
        wset(cid, "engine_notices", notices)

    return {"fired": fired, "scheduled": scheduled, "expired": expired,
            "news_fired": news_fired,
            "consequences_fired": consequences_fired,
            "consequences_minted": consequences_minted,
            "fired_events": fired_events, "notices": notices}


def commit_world_event_spine(ctx, transit_result):
    """Promote fired mechanics rows into checkpointed objective history.

    ``scheduled_events`` answers what is still due; ``world_events`` answers
    what objectively happened. This seam is deliberately downstream of the
    mechanics adjudication and cannot invent an event. Stable ids make a
    repeated landing harmless, while the containing turn transaction and the
    table's checkpoint/branch/archive plumbing make reroll authoritative.
    """
    rows = []
    for fired in (transit_result or {}).get("fired_events") or []:
        if not isinstance(fired, dict) or not fired.get("event_id"):
            continue
        raw_payload = fired.get("payload")
        try:
            payload = json.loads(raw_payload or "{}") \
                if isinstance(raw_payload, str) else copy.deepcopy(raw_payload or {})
        except (json.JSONDecodeError, TypeError):
            payload = {"detail": str(raw_payload or "")[:500]}
        if not isinstance(payload, dict):
            payload = {"detail": payload}
        payload["source_event_id"] = str(fired["event_id"])
        world_event_id = stable_event_key(
            "world_event", ctx.chat.id, ctx.turn.frame_id, fired["event_id"])
        if q("SELECT 1 FROM world_events WHERE chat_id=? AND event_id=?",
             (ctx.chat.id, world_event_id), one=True):
            continue
        qtx(
            "INSERT OR IGNORE INTO world_events("
            "event_id,chat_id,turn_id,frame_id,occurred_at,duration_seconds,"
            "kind,location_id,payload,seed,committed) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (world_event_id, ctx.chat.id, ctx.turn.id, ctx.turn.frame_id,
             float(fired.get("occurred_at") or 0.0), 0.0,
             str(fired.get("kind") or "event"), fired.get("location_id"),
             json.dumps(payload, ensure_ascii=False), fired.get("seed"),
             time.time()),
        )
        rows.append({
            "event_id": world_event_id,
            "source_event_id": str(fired["event_id"]),
            "kind": str(fired.get("kind") or "event"),
            "location_id": fired.get("location_id"),
        })
    return {"offered": len((transit_result or {}).get("fired_events") or []),
            "written": len(rows), "events": rows}


def commit_information_carriers(ctx, prepared_scene, world_event_result):
    """Acquire/move character-owned public reports after memory state lands,
    then copy any that were actually passed on this beat.

    Tellings run AFTER acquisition, so a witness can pass on what they saw in
    the same beat they saw it -- which is what someone running in to say what
    just happened actually is. They run inside the same domain because a
    telling that landed while the acquisition it copied from rolled back would
    be a mind holding a report of an event that never happened.
    """
    from carriers import advance_carriers, apply_tellings

    scene = (prepared_scene or {}).get("scene") or {}
    result = advance_carriers(ctx, scene, world_event_result)

    resolved = ctx.director_resolve or ctx.director_establish or {}
    ops = (resolved.get("state_diff") or {}).get("telling_ops") or []
    if not isinstance(ops, list):
        ops = []
    courier_ops = (resolved.get("state_diff") or {}).get("courier_ops") or []
    if not isinstance(courier_ops, list):
        courier_ops = []
    artifact_ops = (resolved.get("state_diff") or {}).get("artifact_ops") or []
    if not isinstance(artifact_ops, list):
        artifact_ops = []
    if not result.get("enabled"):
        if ops:
            ctx.add_warning(
                "discarded %d telling(s): the rumor-ledger floor is off"
                % len(ops))
        if courier_ops:
            ctx.add_warning(
                "discarded %d courier op(s): the rumor-ledger floor is off"
                % len(courier_ops))
        if artifact_ops:
            ctx.add_warning(
                "discarded %d artifact op(s): the rumor-ledger floor is off"
                % len(artifact_ops))
        result["told"] = 0
        return result

    # What degradation is allowed to redact. The engine names its own cast and
    # rooms rather than letting a detector guess which words are people: a
    # wrong guess silently rewrites a claim into something false, and this is
    # the one module whose entire correctness argument is that it cannot
    # invent.
    names = list(_registered_name_roster(ctx.chat, ctx.cast))
    places = [str(r.get("name") or rid)
              for rid, r in (scene.get("rooms") or {}).items()
              if isinstance(r, dict)]
    places += list((scene.get("rooms") or {}).keys())

    told, rejected = apply_tellings(ctx, scene, ops, names=names,
                                    places=places)
    for reason in rejected:
        ctx.add_warning("telling refused: %s" % reason)
    result["told"] = told
    result["tellings_offered"] = len(ops)
    result["tellings_refused"] = len(rejected)

    # Couriers ride in the same domain and transaction: a dispatch copies a
    # report a mind holds NOW, so it must roll back with the acquisition it
    # copied from, exactly as tellings must. The sweep runs even on beats
    # with no ops -- the road moves whether or not anyone declares anything.
    from couriers import run_couriers

    courier_metrics, courier_rejected = run_couriers(
        ctx, scene, courier_ops, names=names, places=places)
    for reason in courier_rejected:
        ctx.add_warning("courier op refused: %s" % reason)
    result.update(courier_metrics)

    # Artifacts last, in the same domain and transaction: a bill posted from
    # a report acquired this beat must roll back with the acquisition it
    # copied, exactly as a dispatch must -- and running after the courier
    # sweep means a caravan reads the wall as it stood when the beat began,
    # never a bill nailed up later in the same instant.
    from artifacts import run_artifacts

    artifact_metrics, artifact_rejected = run_artifacts(
        ctx, scene, artifact_ops)
    for reason in artifact_rejected:
        ctx.add_warning("artifact op refused: %s" % reason)
    result.update(artifact_metrics)
    return result

# ---- Cast changes ----

def commit_cast_changes(ctx, nonce):
    chat = ctx.chat
    cid = chat.id
    res = ctx.director_resolve or {}
    diff = res.get("state_diff") or {}
    name2id = {
        character_name_from_text(r["sheet"]).lower(): r["id"]
        for r in q(
            "SELECT ch.id,COALESCE(cc.sheet,ch.sheet) AS sheet "
            "FROM chat_chars cc "
            "JOIN characters ch ON ch.id=cc.char_id WHERE cc.chat_id=?",
            (cid,),
        )
    }
    frame_id = ctx.turn.frame_id
    with transaction():
        for chg in (diff.get("cast_changes") or []):
            who = str(chg.get("who") or "").lower().strip()
            stt = chg.get("status")
            if stt in ("active", "dormant") and who in name2id:
                set_char_status(cid, name2id[who], stt, frame_id=frame_id)

# ---- World entity commit ----

def _is_gated_awareness(cond):
    """Is this an awareness condition at a level that removes a mind from play?

    `dazed` is deliberately not gated -- a dazed mind is present but degraded --
    so it is not caught here either. See scene.NON_AWAKE_GATED.
    """
    from scene import NON_AWAKE_GATED, _normalize_awareness_level
    if str(cond.get("kind") or "") != "awareness":
        return False
    if not cond.get("active", True):
        return False
    state = cond.get("state") if isinstance(cond.get("state"), dict) else {}
    level = _normalize_awareness_level(state.get("level"))
    return level in NON_AWAKE_GATED


def _subjects_that_moved(ctx, diff, prev_scene=None):
    """Who crossed into a different room this beat, by name.

    Read from the diff's own positions against the scene as it stood BEFORE
    this beat committed, so a position re-asserted unchanged is not mistaken
    for a move -- §1.14 records that resolve asserts positions with no declared
    movement, and treating those as movement would make this guard fire on
    people standing still.

    `prev_scene` is not an optimization. commit_scene runs BEFORE
    commit_world_entities inside one transaction, so by the time this guard
    runs, `get_scene` already returns the post-move positions and every
    comparison reads equal -- the guard found nobody moving, ever, and was a
    no-op in production while its tests passed against a hand-fed scene.
    prepare_scene_commit reads the world once before any of that and hands the
    genuine pre-beat blob down. The query fallback is for direct callers that
    never prepared a scene commit, where nothing has been written yet.
    """
    moved = set()
    positions = diff.get("positions")
    if not isinstance(positions, dict) or not positions:
        return moved
    if isinstance(prev_scene, dict):
        before = prev_scene.get("positions") or {}
    else:
        try:
            before = (get_scene(ctx.chat.id) or {}).get("positions") or {}
        except Exception:  # noqa: BLE001 - no scene is not a movement claim
            return moved
    for subject, room in positions.items():
        if not room:
            continue
        was = before.get(subject)
        if was and str(was) != str(room):
            moved.add(str(subject))
    return moved


def _subjects_targeted_by_an_action(ctx):
    """Who had an action aimed at them this beat.

    The exemption that keeps the guard honest: being drugged, clubbed or
    carried to a bed is somebody ELSE's act naming you as its target, and it
    legitimately produces a gated state on a subject who was moving a moment
    earlier.
    """
    targeted = set()
    interpret = ctx.director_interpret or {}
    for action in (interpret.get("actions") or []):
        if not isinstance(action, dict):
            continue
        for target in (action.get("targets") or []):
            if isinstance(target, str) and target.strip():
                targeted.add(target.strip())
            elif isinstance(target, dict):
                name = target.get("name") or target.get("id")
                if name:
                    targeted.add(str(name))
    return targeted


def _supersede_disguises(cursor, chat_id, cond, written_id):
    """One active disguise OR transformation per body, enforced at the write.

    Both are singular by nature -- a body presents one outward form and IS one
    thing -- but
    nothing made that true, and the Director minted a fresh `condition_id` per
    reroll instead of reusing one. Measured live (chat 72): three active rows
    on one subject, each with different `presented_appearance` prose, and
    whichever the scan reached decided what every observer saw. The glamour
    appeared to work and then stop between turns.

    Two rules, and the second is the one that matters for play:

      * a NEW disguise supersedes every other active one on that body, so the
        most recent declaration is the only one in force;
      * an ENDING ends them ALL, not just the id it names. "You allow your
        glamour to come undone" is a statement about the body, and the
        Director cannot name ids it has never been shown -- so ending one row
        would silently promote the next and leave the glamour half-standing.

    ACROSS THE WHOLE GROUP, not within one kind. The scoping used to be
    `AND kind=?`, which made a body singular in its disguises and separately
    singular in its transformations -- and therefore able to be both at once.
    Live (chat 74): "you allow your glamour to come undone" minted
    `physical_transformation:Hinami:glamour_dropped` BESIDE three active
    disguises instead of ending them, so a body that had just revealed its
    true form went on presenting the false one to every observer for the rest
    of the story. Both kinds answer the same question -- what outward form
    does this body present -- and two answers is one too many.

    KNOWN_TO IS INHERITED. A superseding row that omits the field is not
    saying "nobody knows any more", it is saying nothing, and the two were
    indistinguishable: chat 74's winning row carried `known_to: []` while
    every other row on that body named The Doctor, so the one character who
    had been told was the only one fooled. The same trap `capacity` documents
    -- an empty value must not mean both "authored as empty" and "never
    filled in". A disguise ENDING clears it honestly; only a live one
    inherits.

    Case-insensitive on subject because `subject_id` is a model-written name.
    """
    kind = str(cond.get("kind") or "")
    if kind not in SINGULAR_BODY_CONDITIONS:
        return
    subject = str(cond.get("subject_id") or "").strip()
    if not subject:
        return
    group = list(SINGULAR_BODY_CONDITIONS)
    marks = ",".join("?" * len(group))
    if int(cond.get("active", 1)):
        # Read before the UPDATE, since it is what makes them unreadable.
        # Guarded on the cursor's own capability rather than assumed: the
        # rule's unit tests drive it with a recording stub that has no
        # fetch, and inheritance is an enrichment -- worth skipping, never
        # worth crashing the commit over.
        superseded = []
        if hasattr(cursor, "fetchall"):
            cursor.execute(
                f"SELECT payload FROM world_conditions WHERE chat_id=? "
                f"AND kind IN ({marks}) AND active=1 "
                f"AND condition_id<>? AND lower(subject_id)=lower(?)",
                (chat_id, *group, written_id, subject))
            superseded = list(cursor.fetchall() or [])
        cursor.execute(
            f"UPDATE world_conditions SET active=0 WHERE chat_id=? "
            f"AND kind IN ({marks}) AND active=1 "
            f"AND condition_id<>? AND lower(subject_id)=lower(?)",
            (chat_id, *group, written_id, subject))
        _inherit_known_to(cursor, chat_id, written_id, superseded)
    else:
        cursor.execute(
            f"UPDATE world_conditions SET active=0 WHERE chat_id=? "
            f"AND kind IN ({marks}) AND lower(subject_id)=lower(?)",
            (chat_id, *group, subject))


def _inherit_known_to(cursor, chat_id, written_id, superseded_rows):
    """Carry `known_to` onto a superseding row that did not restate it.

    Only ADDS, and only when the new row is silent: a row that names its own
    audience is authoritative, including when it deliberately names a smaller
    one. Someone who was told the truth does not un-learn it because the
    subject adjusted their glamour.
    """
    if not superseded_rows or not hasattr(cursor, "fetchone"):
        return
    cursor.execute(
        "SELECT payload FROM world_conditions WHERE chat_id=? "
        "AND condition_id=?", (chat_id, written_id))
    row = cursor.fetchone()
    if not row:
        return
    try:
        payload = json.loads(row[0] if not isinstance(row, dict)
                             else row["payload"])
    except Exception:
        return
    state = payload.get("state")
    if not isinstance(state, dict) or state.get("known_to"):
        return
    inherited = []
    for old in superseded_rows or []:
        try:
            prior = json.loads(old[0] if not isinstance(old, dict)
                               else old["payload"])
        except Exception:
            continue
        for who in ((prior.get("state") or {}).get("known_to") or []):
            text = str(who or "").strip()
            if text and text not in inherited:
                inherited.append(text)
    if not inherited:
        return
    state["known_to"] = inherited
    cursor.execute(
        "UPDATE world_conditions SET payload=? WHERE chat_id=? "
        "AND condition_id=?", (json.dumps(payload), chat_id, written_id))


def commit_world_entities(ctx, nonce, *, prepared=None):
    """Commit world entities, conditions (and legacy placement cleanup).

    The normalized world_entities rows are a DERIVED projection of the
    scene commit: when the caller passes prepare_scene_commit's result
    (commit_all always does), the set of entities to write comes from its
    post-dedup/post-destruction diff, so the projection cannot disagree with
    the blob about a rekeyed room or a destroyed entity. The raw step diff
    remains the fallback for direct callers that never prepared a scene
    commit.

    WHICH entities a beat touched is the diff's to say; WHAT they now are is
    the merged scene's, and taking the second from the diff too is how this
    projection drifted. The diff is the truth the blob was merged FROM, and
    `spatial._merge_entity` sits in between: it reads a schema default as
    silence and refuses a name `_fill_entity_names` derived from the dict key.
    Writing the raw diff here skipped all of that, so a pose-only beat left
    the blob saying "Blue Police Box"/vehicle and the row saying "Tardis
    001"/object -- the same defect tests/test_scene_entity_merge.py was
    written for, repaired in the blob and left standing in its projection.
    Measured on the author's live engine.db: of 480 rows, 15 were named
    literally "Object" (12 of them with a real name -- Hinami, The TARDIS,
    A Dalek -- sitting in the blob beside them), 19 disagreed with the blob
    about `name` and 24 about `kind`, including a TARDIS demoted to `object`,
    which is the field the vehicle-lorebook branch below keys on.

    A name-only guard here would have been a second copy of a policy that
    already exists, and would have had to be extended by hand for every
    field the merge learns next; the derived-name refusal is deliberately
    NOT restated. Direct callers, having no merged scene, run the same
    `_merge_entity` against the row they are about to overwrite, so there is
    one rule ("the row is the merged entity") with one implementation.
    """
    chat = ctx.chat
    cid = chat.id
    if prepared is not None and isinstance(prepared.get("diff"), dict):
        diff = prepared["diff"]
    else:
        res = ctx.director_resolve or ctx.director_establish or {}
        diff = res.get("state_diff") or {}
    turn_id = ctx.turn.id

    # S3-A8 is the STALE-POSTURE symptom, not a concealment leak: the resolve
    # payload hands the model the complete pre-beat `scene.entities`, so a free-
    # text `posture`/`description` clause gets copied forward verbatim even when
    # this beat's own prose contradicts it, and `_PROTECTED_STATE_KEYS` then
    # shields it from normalization so the stale clause wins downstream.
    #
    # An earlier attempt at this finding read it as a leak and skipped any
    # entity whose JSON contained a concealed actor's name as a SUBSTRING
    # (so an actor named Al matched "small"), dropping the update permanently
    # with nothing to re-apply it. That silently diverged `world_entities` from
    # the `world.scene` blob it is a projection of -- durable corruption traded
    # for a leak that was never the finding. Detect and report the copy-forward
    # instead; the entity still commits, because a stale clause is a narration
    # problem and a missing row is a world-model problem.
    # From preparation when there is one: commit_scene has already persisted
    # this beat's blob by the time this runs, so re-reading the world here
    # returns the POST-merge entities and "prior" would be comparing the new
    # state against itself. Same hazard as _subjects_that_moved below, same
    # source. The query stays for direct callers, where nothing is written yet.
    _prior_scene = prepared.get("prev_scene") if isinstance(prepared, dict) else None
    if not isinstance(_prior_scene, dict):
        _prior_scene = wget(cid, "scene", {}) or {}
    _prior_entities = _prior_scene.get("entities") or {}
    _beat_prose = str(
        (ctx.director_resolve or ctx.director_establish or {}).get(
            "resolved_event") or "").casefold()

    # The merged entities this beat produced -- the values the row projects.
    # Read from preparation, never re-read from the world: commit_scene has
    # already persisted the blob by now, which would work by accident here
    # and is the same trap _prior_scene above documents.
    _merged_entities = (prepared.get("scene") or {}).get("entities") \
        if isinstance(prepared, dict) else None
    if not isinstance(_merged_entities, dict):
        _merged_entities = {}

    def _projected(entity_id, entity_def, prior_payload):
        """What world_entities should now hold for this entity.

        The merged blob when there is one. Otherwise the same merge, run
        against the row about to be overwritten -- a direct caller must not
        be the way back into wholesale replacement. An id absent from the
        merged entities is not an error: _dedup_duplicate_entity_keys folds
        an entity keyed by id in one beat and by display name in the next,
        and the fold's own key is the one that survives.
        """
        merged = _merged_entities.get(entity_id)
        if isinstance(merged, dict):
            return merged
        if isinstance(prior_payload, dict) and isinstance(entity_def, dict):
            return _merge_entity(entity_id, prior_payload, entity_def)
        return entity_def

    def _copied_forward_unchanged(entity_id, entity_def):
        prior = _prior_entities.get(entity_id)
        if not isinstance(prior, dict) or not isinstance(entity_def, dict):
            return False
        name = str(entity_def.get("name") or "").casefold()
        if not name or name not in _beat_prose:
            return False
        prior_state = prior.get("state") if isinstance(prior.get("state"), dict) else {}
        new_state = entity_def.get("state") if isinstance(entity_def.get("state"), dict) else {}
        return any(
            key in prior_state and key in new_state
            and prior_state[key] == new_state[key]
            and str(new_state[key] or "").strip()
            for key in ("posture", "description")
        )

    with transaction() as c:
        for entity_id, entity_def in (diff.get("entities") or {}).items():
            if not isinstance(entity_def, dict):
                continue
            if _copied_forward_unchanged(entity_id, entity_def):
                ctx.add_warning(
                    f"entity {entity_id}: this beat's prose names it, but its "
                    f"posture/description came through byte-identical to the "
                    f"pre-beat blob -- possible stale clause (S3-A8)")
            existing = q("SELECT payload FROM world_entities WHERE entity_id=? AND chat_id=?",
                         (entity_id, cid), one=True)
            prior_payload = None
            if existing:
                try:
                    prior_payload = json.loads(existing["payload"] or "null")
                except (TypeError, ValueError):
                    # An unreadable payload is not an argument for erasing the
                    # record it belongs to: fall through to the raw diff, which
                    # is what this line did for every row before the merge.
                    prior_payload = None
            row_def = _projected(entity_id, entity_def, prior_payload)
            payload = json.dumps(row_def, ensure_ascii=False)
            if existing:
                c.execute(
                    "UPDATE world_entities SET kind=?,subtype=?,name=?,payload=? "
                    "WHERE entity_id=? AND chat_id=?",
                    (row_def.get("kind", "object"),
                     row_def.get("subtype", ""),
                     row_def.get("name", ""),
                     payload, entity_id, cid),
                )
            else:
                c.execute(
                    """INSERT INTO world_entities(entity_id,chat_id,kind,subtype,name,payload,created_turn_id)
                    VALUES(?,?,?,?,?,?,?)""",
                    (entity_id, cid, row_def.get("kind", "object"),
                     row_def.get("subtype", ""), row_def.get("name", ""),
                     payload, turn_id),
                )
                # Deterministic vehicle-lorebook creation -- an entity
                # with interior_rooms is an enterable mobile place (a
                # ship, a TARDIS), exactly what LOREBOOK_TYPES' "vehicle"
                # book type exists for. Found live: the model reliably
                # marks these entities kind="vehicle" with interior_rooms
                # but never proposes a lorebook for them on its own, so
                # everything about them piled up as flat entries in the
                # single chat-wide canon book instead of its own book.
                # Created here (deterministically, not model-proposed) so
                # it works at zero model compliance; sync_anchored_books
                # (called at the end of commit_scene, which runs before
                # this domain) then keeps it following the entity as it
                # moves, and commit_mapping's lorebook_manifest already
                # shows it to the model this same turn, so entries route
                # into it instead of canon without any extra plumbing.
                # Read from the projected record for the same reason the row
                # is: a beat that omits `kind` gets `object` back from the
                # validator, and a vehicle that arrives demoted never gets
                # its book at all.
                if row_def.get("kind") == "vehicle" and row_def.get("interior_rooms"):
                    # Canonical-anchor comparison, not raw id equality: a
                    # re-coined alias id for an existing vehicle
                    # ('tamsin_ferry_entity' vs 'ferry_tamsin') must find
                    # that vehicle's existing book, not mint a second one.
                    alias_map = _entity_alias_map(cid)
                    canon = _canonical_anchor(entity_id, alias_map)
                    has_book = any(
                        _canonical_anchor(r["anchor_entity_id"], alias_map)
                        == canon
                        for r in c.execute(
                            "SELECT anchor_entity_id FROM lorebooks "
                            "WHERE chat_id=? AND anchor_entity_id IS NOT NULL",
                            (cid,),
                        ).fetchall()
                    )
                    if not has_book:
                        c.execute(
                            "INSERT INTO lorebooks(name,chat_id,book_type,summary,parent_id,"
                            "anchor_entity_id,resource_uid) VALUES(?,?,?,?,?,?,?)",
                            (
                                row_def.get("name") or entity_id, cid, "vehicle",
                                f"Everything concerning {row_def.get('name') or entity_id}.",
                                chat.lorebook_id, entity_id, new_uid("book"),
                            ),
                        )

        for entity_id in (diff.get("remove_entities") or []):
            c.execute("DELETE FROM world_entities WHERE entity_id=? AND chat_id=?",
                      (entity_id, cid))
            c.execute("DELETE FROM world_placements WHERE subject_id=? AND chat_id=?",
                      (entity_id, cid))

        # A MIND THAT WALKED OUT OF THE ROOM DID NOT FALL ASLEEP IN IT.
        #
        # `director_resolve` may assert an `awareness` condition, and a gated
        # level (asleep/sedated/unconscious) removes the subject from
        # perception entirely and stops their character step running. Live
        # failure: the player typed `"Doctor. I'm going to rest for today..."
        # You slowly stand. ... "Anyways... good night." You walk towards the
        # shoji leading to the upstairs opening it.` -- three lines of SPEECH
        # about a plan, and three narrated acts: stand, yawn, walk.
        #
        # `director_interpret` read it correctly and extracted only the acts.
        # Resolve then minted `{"level": "asleep", "cause": "natural fatigue
        # after meal, declared intent to rest and sleep"}` -- its own cause
        # naming the speech it inferred from -- and the player was gated out of
        # their own story while their character was mid-stride.
        #
        # A stated plan is dialogue. Going under is an act. The prompt already
        # says exactly that ("goes genuinely under", a player assertion is a
        # "completed-fact claim"), which is the point: it is instruction where
        # structure is wanted, and the instruction lost.
        #
        # The check is a CONTRADICTION, not a reading of intent -- no verb list
        # to maintain and nothing to interpret. You cannot cross a threshold and
        # be unconscious in the same beat. Being carried or dragged is not
        # caught by this: that is somebody else's action naming you as its
        # target, and a targeted subject is exempt below.
        moved_this_beat = _subjects_that_moved(
            ctx, diff,
            prev_scene=(prepared or {}).get("prev_scene"))
        targeted_this_beat = _subjects_targeted_by_an_action(ctx)

        for cond_id, cond_list in (diff.get("conditions") or {}).items():
            if not isinstance(cond_list, list):
                cond_list = [cond_list]
            for cond in cond_list:
                if not isinstance(cond, dict):
                    continue
                if _is_gated_awareness(cond):
                    subject = str(cond.get("subject_id") or "")
                    if (subject in moved_this_beat
                            and subject not in targeted_this_beat):
                        # Dropped, and SAID -- a condition that silently
                        # vanishes is the mirror of one that silently lands.
                        ctx.warnings.append(
                            "dropped an %s condition on %r: they moved rooms "
                            "this beat and no action targeted them, so the "
                            "state rests on what they SAID rather than on "
                            "anything they did" % (
                                (cond.get("state") or {}).get("level")
                                or "awareness", subject))
                        continue
                cid_val = cond.get("condition_id") or cond_id
                existing = q("SELECT condition_id FROM world_conditions "
                             "WHERE condition_id=? AND chat_id=?",
                             (cid_val, cid), one=True)
                payload = json.dumps(cond, ensure_ascii=False)
                if existing:
                    c.execute(
                        """UPDATE world_conditions SET subject_id=?,kind=?,payload=?,active=?
                        WHERE condition_id=? AND chat_id=?""",
                        (cond.get("subject_id", ""), cond.get("kind", ""),
                         payload, int(cond.get("active", 1)), cid_val, cid),
                    )
                else:
                    c.execute(
                        """INSERT INTO world_conditions(condition_id,chat_id,subject_id,kind,
                        started_at,expires_at,next_tick,payload,active) VALUES(?,?,?,?,?,?,?,?,?)""",
                        (cid_val, cid, cond.get("subject_id", ""), cond.get("kind", ""),
                         cond.get("started_at_seconds", 0.0),
                         cond.get("expires_at_seconds"),
                         cond.get("next_tick_seconds"),
                         # The row's own `active`, not a hardcoded 1. An
                         # ENDING that names an id no row carries yet (a
                         # Director closing a condition under a rekeyed id, an
                         # imported chat) was being inserted as ACTIVE, so the
                         # act of waking someone put them under.
                         payload, int(cond.get("active", 1))),
                    )
                # One body presents one outward form. Enforced here
                # rather than requested, because the Director cannot name
                # condition ids it has never been shown -- see the helper.
                _supersede_disguises(c, cid, cond, cid_val)

    return {"entities_committed": len(diff.get("entities") or {}),
            "entities_removed": len(diff.get("remove_entities") or [])}

# ---- Mapping commit ----

_ADDRESS_ARTICLES = ("the ", "a ", "an ")


def _form_in(form, body):
    """Is this address form spoken in this line?

    Case-insensitive for a distinctive name, case-SENSITIVE for a form that is
    also an ordinary English word -- the same posture, and the same word list,
    that `_scrub_unknown_identities` already uses. Live in this database: a
    Starfleet cast contains `Data`, and matching that case-insensitively would
    have every line mentioning sensor data introduce a man.
    """
    from character_schema import name_boundary_regex
    from language_runtime import linguistic
    common_word_names = linguistic("agents.common", "_COMMON_WORD_NAMES")
    flags = 0 if form.casefold() in common_word_names else re.I
    # A name boundary, not \b: `\bヒナミ\b` never matches `ヒナミさん`, so
    # every Japanese address form read as unspoken.
    return bool(name_boundary_regex(form, flags).search(body))


def _address_forms(roster):
    """The ways a roster name is actually SAID, keyed by the roster name.

    A name is stored as a display string -- `The Doctor`, `Cmdr. Vale`,
    `Jean-Luc Picard` -- and nobody speaks in display strings. They say
    "Doctor", "Vale", "Picard". Requiring the exact stored string meant the
    ordinary way of addressing somebody taught nobody anything.

    Measured on chat 63: 552 dialogue lines, 33 of them say "Doctor" and the
    roster holds "The Doctor". The engine's own data shows the same split from
    the other side -- chat 22's recognition map holds `Data` and `Lt.
    Commander Data`, `Deanna Troi` and `Counselor Troi`, as separate people
    who do not know each other.

    A form that two roster members share is DROPPED rather than guessed: two
    Picards in a room means "Picard" identifies nobody, and inventing an edge
    is worse than missing one, because a wrong edge cannot be told from a
    right one afterwards.
    """
    candidates = {}
    for name in roster:
        full = str(name or "").strip()
        if not full:
            continue
        forms = {full}
        folded = full.casefold()
        for article in _ADDRESS_ARTICLES:
            if folded.startswith(article):
                forms.add(full[len(article):].strip())
        tokens = [t for t in re.split(r"\s+", full) if t]
        if len(tokens) > 1:
            # The last token: a surname, or the noun under a title.
            forms.add(tokens[-1].strip(".,"))
        # The 3-character floor exists to stop short LATIN fragments from
        # matching ordinary words. A short CJK name is an ordinary name, and
        # dropping it meant a whole cast could not be addressed by name.
        candidates[full] = {
            f for f in forms
            if len(f) >= 3 or _UNSPACED_SCRIPT.match(f[:1] or "")}

    # Ambiguity: a form claimed by two names identifies neither.
    seen = {}
    for name, forms in candidates.items():
        for form in forms:
            seen.setdefault(form.casefold(), set()).add(name)
    return {name: {f for f in forms if len(seen[f.casefold()]) == 1}
            for name, forms in candidates.items()}


def _names_heard_in(quote, hearer_name, roster, scene, hearer_room):
    """Roster names spoken inside one line, of somebody standing right there.

    THE GAP THIS CLOSES. `known` gates every identity the engine will let a
    mind use -- perception scrubs an unearned name out of a view, memory stores
    "a voice" instead of a speaker, and the narrator will not name a person to
    somebody who has not met them. It was written in exactly two places:
    `greetings.py` seeds the one greeting character against the player, and
    `commit` seeds everyone when a background presence is PROMOTED. Nothing
    recorded a name learned in play, so a character attached the ordinary way
    never entered the map and nobody ever learned anybody by being told.

    Measured over the corpus before this: 19 of 42 played stories held fewer
    recognitions than a fully-acquainted cast. Chat 59 -- 162 turns, two cast,
    a mother and her daughter -- held ONE directed pair, so every beat scrubbed
    both names out of both views. The failure that surfaces is not a missing
    name but a wrong one: a view with one surviving name and one anonymous body
    invites the model to join them, and the Doctor answered a question the
    player asked as though Tamamo had asked it.

    THE RULE. A name is learned when it is SPOKEN in your hearing and the
    person it names is in the room with you. That is the ordinary way people
    learn names, it needs no model call, and it rides a channel the firewall
    already governs -- the caller passes only lines this hearer's own view
    received.

    Two refusals, both of which keep this from becoming a leak:

      * The named person must be PRESENT and in the hearer's room. Hearing
        about somebody absent teaches you a name, not a face, and letting it
        through would license recognising a stranger who walks in later.
      * Your own name teaches you nothing, and a speaker who says a name
        already knew it.
    """
    body = str(quote or "")
    if not body:
        return []
    forms = _address_forms(roster)
    learned = []
    for name in roster:
        candidate = str(name or "").strip()
        if not candidate or candidate == hearer_name:
            continue
        if not any(_form_in(form, body) for form in forms.get(candidate, ())):
            continue
        # Present, and here. `_room_of` resolves through the scene's own
        # subject identity, so a body recorded under an entity id still
        # matches the display name the line used.
        named_room = _room_of(scene, candidate) if scene else None
        if not named_room or (hearer_room and named_room != hearer_room):
            continue
        learned.append(candidate)
    return learned


def _known_name_roster(chat, cast):
    """Exact display names perception.py's recognition check requires:
    known[perceiver_name] must contain the OTHER actor's exact name string
    for `actor_name in recognized_sources` to ever match. The persona/player
    name and every cast member's character_name() output are the only
    strings that check will ever compare against.

    PRESENCE, NOT EXISTENCE, and deliberately so. `_registered_name_roster`
    below answers the other question. They are two functions rather than one
    function with a flag because a flag has a default and a default is a thing
    to forget -- and the short, obvious name belongs to the narrow one, so the
    lazy call is the safe call.

    This one is safe to ENUMERATE. The wide one is not: `promote_background_
    character` iterates a roster straight into the `known` recognition map,
    and nothing downstream ever re-checks that write.
    """
    from scene import persona_of
    pers = persona_of(chat)
    roster = []
    if isinstance(pers, dict):
        name = pers.get("identity", {}).get("name")
        if name:
            roster.append(name)
    for row in cast:
        roster.append(character_name_from_text(row["sheet"]))
    return roster


def _registered_name_roster(chat, cast):
    """Everyone the STORY knows about, present or not -- the existence answer.

    MEMBERSHIP ONLY. Test strings against it; never iterate it into anything a
    model reads or a table stores. Six of the eight roster call sites only ask
    "is this string somebody?", and for those, widening is either harmless or
    an outright repair -- every exclusion guard gets stronger, including the
    one that stops a registered character being handed to the background
    manager as furniture.

    Why it exists: `chat_chars.status` was answering three questions at once --
    does this person exist, are they in the scene, should we spend a model call
    on them. Reading the presence answer as the existence answer meant a
    dormant character could be named by nobody. Measured on chat 34: one turn
    emitted four `ok` introductions and exactly one survived, the only pair
    where both names were active.
    """
    from scene import extant_cast
    roster = list(_known_name_roster(chat, cast))
    try:
        chat_id = chat["id"]
    except (TypeError, KeyError, IndexError):
        return roster
    for row in extant_cast(chat_id) or []:
        name = character_name_from_text(row["sheet"])
        if name and name not in roster:
            roster.append(name)
    return roster

def _resolve_roster_name(value, roster):
    """mapping_commit's prompt allows 'who'/'learns' to be 'a name or brief
    descriptor' -- free text like 'Dana Osei -- supply pilot, claims three
    days of unanswered radio contact' has been observed live, instead of the
    bare exact name perception.py's recognition check requires. Resolve to
    the roster's canonical spelling (exact match, or the value containing a
    roster name as a substring); if it doesn't resolve to anyone in the
    roster, drop it rather than write a value that can never match and would
    permanently leave that perceiver unable to recognize anyone.
    """
    text = str(value or "").strip()
    if not text:
        return None
    for name in roster:
        if text.casefold() == name.casefold():
            return name
    for name in roster:
        if name.casefold() in text.casefold():
            return name
    return None

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
        from scene import promotion_config
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


def _resolve_presence_name(name, presences, scene=None):
    """The key `name` should be filed under, given what is already tracked.

    First-seen spelling wins, so an established presence keeps the name every
    other record already refers to it by rather than being renamed by whichever
    determiner the model reached for this beat.
    """
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
    """Merge presences that were split by an article before they were resolved
    on write. Runs on load, so a story already carrying the split heals on its
    next turn instead of needing a migration.

    The earliest first_turn wins the name -- that is the spelling the rest of
    the story has been using.
    """
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
            other = presences.pop(other_name)
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
    from schemas import _ANIMATE_ENTITY_KINDS
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
        from background_claims import prepare_canon

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
    # A bodiless voice (ship AI, station PA) is voiced by the Director and has
    # no room. Tracking one as a background presence pinned it to whatever room
    # it was positioned in and made it a promotion candidate -- observed live
    # with the Enterprise computer sitting in Ten Forward.
    try:
        from scene import ubiquitous_speaker_names, is_ubiquitous_entity
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
            room = positions.get(name)
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
        _name = str(_placed or "").strip()
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
    from background_claims import record_claims, settle_claims
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
    presences = wget(cid, "background_presences", {})

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
    presences = wget(chat_id, "background_presences", {})
    limits = promotion_thresholds(chat_id)
    out = []
    for name, record in presences.items():
        promotable = (
            len(record.get("dialogue_turns") or []) >= limits["dialogue"]
            or len(record.get("mention_turns") or []) >= limits["mention"]
        )
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
    from scene import persona_of

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
    from importers import draft_promoted_character
    from scene import persona_of

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
    from scene import dialogue_config

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

# Filler tokens ignored when reducing an entity id / display name to its
# canonical token key ("ferry_tamsin" vs "tamsin_ferry_entity" must meet).
_GENERIC_ID_TOKENS = {"the", "a", "an", "entity", "obj", "object"}


def _canonical_token_key(text):
    tokens = [t for t in normalize_room_id(str(text or "")).split("_")
              if t and t not in _GENERIC_ID_TOKENS]
    return "_".join(sorted(tokens))


def _entity_alias_map(cid):
    """{normalized alias/name/id (slug AND sorted-token key): canonical
    entity_id} for this chat's live entities, from world_entities plus the
    current scene -- so a book proposal anchored to an ALIAS of a vehicle
    ('tamsin_ferry_entity' for 'ferry_tamsin') resolves to the same
    canonical entity as the book that already tracks it."""
    amap = {}

    def register(names, own_id):
        keys = []
        for value in names:
            value = str(value or "").strip()
            if not value:
                continue
            for key in (normalize_room_id(value),
                        _canonical_token_key(value)):
                if key and key not in keys:
                    keys.append(key)
        # Union semantics: if ANY of this entity's keys already resolves
        # to an earlier entity, this row is (for dedup purposes) another
        # spelling of THAT entity -- its own id inherits that canonical
        # rather than becoming its own. Row order is the deterministic
        # tiebreak (world_entities first, insertion order).
        canonical = next((amap[k] for k in keys if k in amap), own_id)
        for key in keys:
            amap.setdefault(key, canonical)

    for row in q(
        "SELECT entity_id, name, payload FROM world_entities "
        "WHERE chat_id=? AND retired_turn_id IS NULL",
        (cid,),
    ):
        try:
            payload = json.loads(row["payload"] or "{}")
        except Exception:
            payload = {}
        register([row["entity_id"], row["name"],
                  *(payload.get("aliases") or [])], row["entity_id"])
    scene = wget(cid, "scene", {}) or {}
    for eid, ent in (scene.get("entities") or {}).items():
        if isinstance(ent, dict):
            register([eid, ent.get("name"), *(ent.get("aliases") or [])],
                     str(eid))
    return amap


def _canonical_anchor(anchor, alias_map):
    if not anchor:
        return None
    return alias_map.get(normalize_room_id(anchor)) \
        or alias_map.get(_canonical_token_key(anchor)) \
        or anchor


def _apply_mapping_book_ops(cid, lb, book_ops):
    """Deterministically validates and creates the child lorebooks
    mapping_commit proposed this turn (schemas.py's BookOp, prompts.py's
    BOOK CREATION rule) -- the model proposes a subject and a place in
    the tree, this function is what actually decides whether that's
    trustworthy enough to write, mirroring how every other model
    proposal in this codebase (state_diff, lore_ops themselves) is
    validated deterministically rather than applied on the model's say.
    Returns {temp_id: real_book_id} so lore_ops filed against a book
    that didn't have a database id a moment ago can still resolve it.
    """
    temp_map = {}
    if not book_ops:
        return temp_map

    existing = {
        row["id"]: row
        for row in q("SELECT * FROM lorebooks WHERE chat_id=?", (cid,))
    }
    created = 0
    alias_map = None  # built lazily -- most turns propose no books
    for op in book_ops:
        if not isinstance(op, dict) or op.get("op") != "create":
            continue
        if created >= 3:
            # Cap per turn -- a single beat introducing dozens of new
            # subjects at once is almost always a validation failure
            # upstream, not a genuine worldbuilding moment; the rest
            # fall back to the canon book via the caller's normal
            # target_book_id resolution, not lost.
            continue
        name = str(op.get("name") or "").strip()
        if not name:
            continue
        book_type = op.get("book_type") if op.get("book_type") in LOREBOOK_TYPES else "general"
        anchor = str(op.get("anchor_entity_id") or "").strip() or None
        scope_loc = str(op.get("scope_location_id") or "").strip() or None
        # Anchor-alias + normalized-name dedup: comparing raw anchor ids
        # let two DIFFERENT entity-id aliases of ONE vehicle
        # ('ferry_tamsin' vs 'tamsin_ferry_entity') mint two books for the
        # same ship. Resolve both sides to a canonical entity first, and
        # compare names by slug so punctuation/case drift can't fork a
        # book either. One vehicle -> one book.
        if alias_map is None:
            alias_map = _entity_alias_map(cid)
        canon_anchor = _canonical_anchor(anchor, alias_map)
        name_slug = normalize_room_id(name)

        dup = next((
            row for row in existing.values()
            if normalize_room_id(row["name"]) == name_slug
            or (canon_anchor and _canonical_anchor(
                row["anchor_entity_id"], alias_map) == canon_anchor)
            or (scope_loc and row["book_type"] == book_type and row["scope_location_id"] == scope_loc)
        ), None)
        if dup:
            if op.get("temp_id"):
                temp_map[op["temp_id"]] = dup["id"]
            continue

        raw_parent = op.get("parent_id")
        if isinstance(raw_parent, str):
            # A same-turn temp handle, or an existing book's id spelled as
            # text. `parent_id` is declared `Union[int, str]` for exactly
            # that reason, and which of the two survives validation now
            # depends on the Pydantic major: 1.x tried `int` first and
            # coerced `"77"` to 77, 2.x's smart union keeps the string. So a
            # digit string has to be read as the id it is, or the book
            # silently reparents to canon root on 2.x -- the same op, filed
            # somewhere else, with nothing logged. Matches how lore_ops
            # already resolves `book_id` below.
            parent_id = temp_map.get(raw_parent) or (
                int(raw_parent) if raw_parent.isdigit() else None
            )
        else:
            parent_id = raw_parent
        if not isinstance(parent_id, int) or parent_id not in existing:
            parent_id = lb  # keeps the tree rooted under canon -- never an unreachable orphan

        inheritance_mode = op.get("inheritance_mode") if op.get("inheritance_mode") in (
            "inherit", "isolated") else "inherit"
        new_id = qi(
            "INSERT INTO lorebooks(name,chat_id,book_type,summary,parent_id,"
            "inheritance_mode,scope_world_id,scope_location_id,anchor_entity_id,resource_uid) "
            "VALUES(?,?,?,?,?,?,?,?,?,?)",
            (
                name, cid, book_type, str(op.get("summary") or "")[:500], parent_id,
                inheritance_mode,
                str(op.get("scope_world_id") or "").strip() or None,
                # Store the CANONICAL entity id (not the model's alias
                # spelling) so sync_anchored_books and future dedup all
                # agree on which entity this book tracks.
                scope_loc, canon_anchor, new_uid("book"),
            ),
        )
        created += 1
        existing[new_id] = {
            "id": new_id, "name": name, "book_type": book_type,
            "anchor_entity_id": canon_anchor, "scope_location_id": scope_loc,
        }
        if op.get("temp_id"):
            temp_map[op["temp_id"]] = new_id
    return temp_map

def prepare_mapping_commit(ctx):
    """Resolve and embed mapping operations without mutating durable state.

    Mapping commit may require a long LLM round-trip and one or more remote
    embedding calls.  Preparing those decisions before the outer turn
    transaction prevents network latency from holding SQLite's write lock and
    lets commit_all apply every durable domain atomically.
    """
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    diff = res.get("state_diff") or {}
    book_ids = chat_lorebook_ids(cid)
    # Narration is a rendering layer, not a source of objective truth.
    # `new_specifics` is an audit field for unsupported details the narrator
    # accidentally introduced; never launder those details into canon through
    # the privileged mapping agent.
    narrator_specificity_flags = (ctx.narrator or {}).get("new_specifics") or []
    if narrator_specificity_flags:
        ctx.add_warning(
            "Narrator-originated specifics were excluded from canon: "
            + "; ".join(map(str, narrator_specificity_flags[:8]))
        )
    specifics = []
    staged = (ctx.mapping_stage or {}).get("staged_lore") or []
    world_facts = diff.get("world_facts") or []
    introductions = diff.get("introductions") or []
    seed = f"tick:{cid}:{turn.idx}"

    if not (staged or world_facts or introductions):
        return {
            "skipped": True,
            "mout": {"skipped": "nothing new to commit"},
            "ops": [],
            "book_ops": [],
            "book_ids": book_ids,
            "seed": seed,
        }

    lore_ctx = search_lore(
        chat_lorebook_weights(cid),
        " ".join(map(str, specifics)) or res.get("summary", ""), k=10,
    )
    raw_shadow = wget(cid, "shadow_profile", "") or ""
    raw_intents = wget(cid, "standing_intentions", []) or []
    # Off-screen ticks no longer ride this call AT ALL. The dormant cast is
    # not offered to the model at any level: the stochastic rung is a seeded
    # draw in `offscreen.stochastic_ticks` (free, replayable), taken at
    # commit_mapping, and the model-priced rung above it is the out-of-band
    # profile summary. Asking a lore validator to also author offscreen life
    # was an unadjudicated authoring channel wearing a payload field -- and
    # the seed it was shown seeded nothing, since no RNG ever consumed it.
    payload = {
        "proposed_specifics": specifics,
        "narrator_specificity_audit": narrator_specificity_flags,
        "staged_lore_to_confirm": staged,
        "world_facts": world_facts,
        "existing_lore": lore_ctx,
        "lorebook_manifest": lorebook_manifest(cid),
        "resolved_summary": res.get("summary") or (res.get("resolved_event") or "")[:400],
        "player_public_behavior": {
            "speech": (ctx.director_interpret or {}).get("speech"),
            "visible_action": ((ctx.director_interpret or {}).get("action") or {}).get("attempt"),
        },
        "current_shadow_profile": raw_shadow[:1200],
        # `scene_changed` stays truthful about the scene; it is a fact about
        # the world, not a gate on anything.
        "scene_changed": bool(ctx.director_establish),
        "standing_intentions": raw_intents[:12],
        "beat_introductions": diff.get("introductions") or [],
        "beat_dialogue_log": res.get("dialogue_log") or [],
        "beat_resolved_event": res.get("resolved_event") or "",
    }
    try:
        from llm_quality import complete_validated_json

        mout = complete_validated_json(
            role="mapping",
            step_key="mapping_commit",
            system=get_prompt("mapping_commit"),
            payload=payload,
            temperature=0.0,
            repair_attempts=1,
        )
    except Exception as e:
        ctx.add_warning(f"mapping_commit failed: {e}")
        mout = {
            "validated": [],
            "lore_ops": [],
            "coherence_notes": [f"mapping commit failed: {e}"],
        }

    validated_list = mout.get("validated") if isinstance(mout.get("validated"), list) else []
    ok_facts = [v for v in validated_list if isinstance(v, dict) and v.get("ok")]
    ops = mout.get("lore_ops") if isinstance(mout.get("lore_ops"), list) else []
    ops = [dict(o) for o in ops if isinstance(o, dict) and o.get("content")]
    book_ops = mout.get("book_ops") if isinstance(mout.get("book_ops"), list) else []
    book_ops = [dict(o) for o in book_ops if isinstance(o, dict)]

    if not ops:
        ops = _generate_fallback_ops(
            ok_facts, staged, world_facts, existing_lore=lore_ctx,
        )
    for o in ops:
        if "keys" in o:
            o["keys"] = _keys_str(o["keys"])

    # Lore embeddings are independent of final routing/book IDs. Compute them
    # in one batch now rather than one remote call per operation while the
    # database transaction is open.
    if ops:
        vectors = embed_texts([
            (str(o.get("keys") or "") + " " + str(o.get("content") or "")).strip()
            for o in ops
        ])
        if len(vectors) != len(ops):
            raise RuntimeError("Lore embedding provider returned an unexpected vector count")
        for op, vector in zip(ops, vectors):
            op["_embedding"] = vector

    return {
        "skipped": False,
        "mout": mout,
        "ops": ops,
        "book_ops": book_ops,
        "book_ids": book_ids,
        "seed": seed,
    }


def commit_mapping(ctx, nonce, *, prepared=None):
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    prepared = prepared or prepare_mapping_commit(ctx)
    mout = prepared["mout"]
    book_ids = prepared["book_ids"]
    seed = prepared["seed"]

    if prepared.get("skipped"):
        wset(cid, "lore_cache", _lore_for(ctx)[:12])
        mstep = ctx.mapping_stage or ctx.mapping_quick or {}
        if not mstep.get("cached") and isinstance(mstep.get("relevant_books"), list):
            wset(cid, "active_books", mstep["relevant_books"])
        return {
            "mout": mout,
            "applied": {"created": 0, "updated": 0},
            "book_ids": book_ids,
            "seed": seed,
        }

    ops = prepared["ops"]
    book_ops = prepared["book_ops"]
    applied = {"created": 0, "updated": 0}
    lb = chat.lorebook_id
    if (ops or book_ops) and not lb:
        # One spelling of "the chat's canon book", shared with the other writer
        # that can mint it first (background_claims.write_canon).
        lb = ensure_chat_canon_book(cid)

    temp_book_map = _apply_mapping_book_ops(cid, lb, book_ops)
    valid_books = set(chat_lorebook_ids(cid))
    with transaction() as c:
        for o in ops:
            cat = o.get("category") if o.get("category") in LORE_CATEGORIES else "other"
            kloc = (
                json.dumps(o.get("knowledge_locations") or [])
                if o.get("knowledge_locations") else None
            )
            raw_book_id = o.get("book_id")
            if isinstance(raw_book_id, str):
                raw_book_id = temp_book_map.get(raw_book_id) or (
                    int(raw_book_id) if raw_book_id.isdigit() else None
                )
            target_book_id = raw_book_id or lb
            if target_book_id not in valid_books:
                target_book_id = lb

            if o.get("op") == "update" and o.get("id"):
                row = q("SELECT * FROM lore_entries WHERE id=?", (o["id"],), one=True)
                if row and row["lorebook_id"] in valid_books and not row["canon_locked"]:
                    update_lore(
                        o["id"], o.get("keys", row["keys"]), o["content"], cat,
                        title=o.get("title"), knowledge_tag=o.get("knowledge_tag"),
                        knowledge_range=o.get("knowledge_range"),
                        knowledge_locations=kloc,
                        embedding=o.get("_embedding"),
                    )
                    applied["updated"] += 1
                    continue
            add_lore(
                target_book_id, o.get("keys", ""), o["content"],
                turn_added=turn.idx, category=cat, title=o.get("title"),
                knowledge_tag=o.get("knowledge_tag"),
                knowledge_range=o.get("knowledge_range"),
                knowledge_locations=kloc,
                embedding=o.get("_embedding"),
            )
            applied["created"] += 1
        if lb:
            c.execute(
                "UPDATE lore_entries SET canon_locked=1 "
                "WHERE lorebook_id=? AND turn_added IS NOT NULL AND turn_added<=?",
                (lb, turn.idx - 20),
            )

    wset(cid, "lore_cache", _lore_for(ctx)[:12])
    mstep = ctx.mapping_stage or ctx.mapping_quick or {}
    if not mstep.get("cached") and isinstance(mstep.get("relevant_books"), list):
        wset(cid, "active_books", mstep["relevant_books"])
    if mout.get("shadow_profile"):
        sp = mout["shadow_profile"]
        if isinstance(sp, str) and len(sp) > 2000:
            sp = sp[:2000]
        wset(cid, "shadow_profile", sp)
    if mout.get("standing_intentions"):
        si = mout["standing_intentions"]
        if isinstance(si, list) and len(si) > 20:
            si = si[-20:]
        wset(cid, "standing_intentions", si)
    _volunteered = normalize_offscreen_events(mout.get("offscreen_events"))
    if _volunteered:
        # Nothing asks the model for ticks any more, so anything here is a
        # field nobody requested -- refused on the write path regardless of
        # the chat's level, because a model-authored tick is an
        # unadjudicated authoring channel whatever the setting says.
        ctx.add_warning(
            f"discarded {len(_volunteered)} model-volunteered off-screen "
            "tick(s): ticks are drawn seeded, not authored")
    known = wget(cid, "known", {})
    # WIDE for resolution: an introduction naming an offscreen person is still
    # a sentence about a real person, and dropping it silently is the defect.
    # The EDGE it would write is gated separately, below.
    roster = _registered_name_roster(chat, ctx.cast)
    name_to_id = {character_name_from_text(r["sheet"]): r["id"] for r in ctx.cast}
    for vi in (mout.get("validated_introductions") or []):
        if not isinstance(vi, dict) or not vi.get("ok"):
            continue
        who = _resolve_roster_name(vi.get("who"), roster)
        learns = _resolve_roster_name(
            vi.get("corrected_learns") or vi.get("learns"), roster,
        )
        if not (who and learns):
            continue
        # TWO REQUIREMENTS, KEPT SEPARATE. The roster above answers "is this a
        # person the story knows about", which is what resolving a name needs.
        # An introduction needs more: somebody has to have been THERE to be
        # introduced. Now that the roster includes offscreen characters, a
        # single check would let the model write an introduction between two
        # people who were both absent -- trading a missed edge for an invented
        # one, which is worse, because a wrong edge is indistinguishable from a
        # right one afterwards and nothing downstream can catch it.
        from scene import persona_of as _persona_of
        present = {character_name_from_text(r["sheet"]) for r in ctx.cast}
        player = (persona_name(_persona_of(chat)) or "").strip()
        if player:
            present.add(player)
        # BOTH parties. `learns` had a frame gate and `who` had none, and that
        # gate SKIPS rather than blocks for anyone outside `ctx.cast` -- which
        # is exactly the set the wider roster has just admitted. Hanging the
        # requirement off an id lookup would open it for them instead of
        # closing it, so this is a positive test against who was on stage.
        if who not in present or learns not in present:
            continue
        learns_id = name_to_id.get(learns)
        if learns_id is not None and not is_recognized_in_frame(learns_id, turn.frame_id):
            continue
        known.setdefault(who, [])
        if learns not in known[who]:
            known[who].append(learns)
    wset(cid, "known", known)
    return {"mout": mout, "applied": applied, "book_ids": book_ids, "seed": seed}

# ---- Obligation ledger ----
#
# The world-KV `pending_obligations` ledger tracks open narrative debts --
# demands, promises, announced actions, unanswered questions -- registered by
# director_resolve's `obligations` ops and applied here deterministically
# (mirroring the standing_intentions machinery). Each entry:
# {id, who, what, kind, opened_turn}. director_resolve's payload surfaces
# pending_obligation_view, whose must_discharge_this_beat flag plus the
# prompt's hard rule forbid re-deferring an obligation past its window.

OBLIGATION_OVERDUE_AGE = 2   # beats after which an open obligation must discharge
OBLIGATION_CAP = 12

def pending_obligation_view(chat_id, turn_idx):
    """Payload-ready view of the obligation ledger: each entry with its
    deterministically computed age and must-discharge flag."""
    view = []
    for entry in (wget(chat_id, "pending_obligations", []) or [])[:OBLIGATION_CAP]:
        if not isinstance(entry, dict):
            continue
        try:
            age = max(0, int(turn_idx) - int(entry.get("opened_turn", turn_idx)))
        except (TypeError, ValueError):
            age = 0
        view.append({
            "id": entry.get("id"),
            "who": entry.get("who"),
            "what": entry.get("what"),
            "kind": entry.get("kind", "demand"),
            "age_beats": age,
            "must_discharge_this_beat": age >= OBLIGATION_OVERDUE_AGE,
        })
    return view

def _find_obligation(ledger, op):
    """Index of the ledger entry an op targets: exact id first, then a
    fuzzy same-debtor/overlapping-text fallback (models routinely echo the
    text but not the id)."""
    oid = str(op.get("id") or "").strip()
    if oid:
        for i, entry in enumerate(ledger):
            if str(entry.get("id") or "") == oid:
                return i
    who = _normalized_fact(op.get("who"))
    what = _normalized_fact(op.get("what"))
    if not what:
        return None
    for i, entry in enumerate(ledger):
        entry_who = _normalized_fact(entry.get("who"))
        entry_what = _normalized_fact(entry.get("what"))
        if who and entry_who and who != entry_who:
            continue
        if entry_what and (what in entry_what or entry_what in what):
            return i
    return None

def commit_obligations(ctx, nonce):
    """Apply director_resolve's obligation ops to the pending_obligations
    ledger. Deterministic: open appends (deduped -- re-demanding an open
    debt is not a second debt), discharge/refuse removes. The commit-side
    reminder: any entry still open past OBLIGATION_OVERDUE_AGE after this
    beat's ops was re-deferred against the prompt's hard rule -- warn, and
    leave it flagged for the next beat's payload."""
    cid = ctx.chat.id
    turn = ctx.turn
    res = ctx.director_resolve or {}
    ops = res.get("obligations") if isinstance(res.get("obligations"), list) else []
    ledger = [
        dict(entry)
        for entry in (wget(cid, "pending_obligations", []) or [])
        if isinstance(entry, dict) and entry.get("what")
    ]

    opened = discharged = 0
    for op in ops:
        if not isinstance(op, dict):
            continue
        op_kind = str(op.get("op") or "").strip().lower()
        if op_kind == "open":
            what = str(op.get("what") or "").strip()
            if not what or _find_obligation(ledger, op) is not None:
                continue
            ledger.append({
                "id": f"obl:{turn.idx}:{opened}",
                "who": str(op.get("who") or "").strip(),
                "what": what,
                "kind": str(op.get("kind") or "demand").strip() or "demand",
                "opened_turn": turn.idx,
            })
            opened += 1
        elif op_kind in ("discharge", "refuse"):
            idx = _find_obligation(ledger, op)
            if idx is None:
                ctx.add_warning(
                    f"obligation {op_kind} matched no open ledger entry: "
                    f"{(op.get('id') or op.get('what') or '')!r}"
                )
                continue
            ledger.pop(idx)
            discharged += 1

    overdue = []
    for entry in ledger:
        try:
            age = turn.idx - int(entry.get("opened_turn", turn.idx))
        except (TypeError, ValueError):
            age = 0
        if age >= OBLIGATION_OVERDUE_AGE:
            overdue.append(entry)
            ctx.add_warning(
                f"Obligation re-deferred past its window: {entry.get('who')!r} "
                f"still owes {entry.get('what')!r} (opened turn "
                f"{entry.get('opened_turn')}, age {age} beats). It MUST be "
                "discharged or explicitly refused on-page next beat."
            )

    if len(ledger) > OBLIGATION_CAP:
        ledger = ledger[-OBLIGATION_CAP:]
    wset(cid, "pending_obligations", ledger)
    return {"opened": opened, "discharged": discharged,
            "open": len(ledger), "overdue": len(overdue)}

# ---- World pressure (F5 -- THE WORLD ACTS) ----

# Consecutive beats a pressure may sit HELD (explicitly or by silence) before
# it is flagged must_tick_this_beat in the resolve payload -- the DW-2
# "significance floor" pointed at ongoing processes: the world must either
# escalate or its stillness must be a repeated, visible choice, never a
# default. 2 held beats -> the 3rd beat's payload demands a tick.
WORLD_PRESSURE_STALL_AGE = 2
WORLD_PRESSURE_CAP = 8


def world_pressure_view(chat_id, turn_idx):
    """Payload-ready view of the world-pressure ledger: each open ongoing
    process (a scan in progress, an alerted authority, a spreading fire, an
    artifact probed and not yet answering) with its escalation level, how
    long it has sat unticked, and the deterministic must-tick flag."""
    view = []
    for entry in (wget(chat_id, "world_pressures", []) or [])[:WORLD_PRESSURE_CAP]:
        if not isinstance(entry, dict):
            continue
        try:
            held = max(0, int(entry.get("held_streak", 0)))
        except (TypeError, ValueError):
            held = 0
        view.append({
            "id": entry.get("id"),
            "subject": entry.get("subject"),
            "note": entry.get("note"),
            "level": entry.get("level", 0),
            "beats_since_tick": held,
            "must_tick_this_beat": held >= WORLD_PRESSURE_STALL_AGE,
        })
    return view


def _find_pressure(ledger, op):
    """Index of the ledger entry an op targets: exact id first, then a fuzzy
    overlapping-subject fallback (models routinely echo the subject but not
    the id) -- the same convention as _find_obligation."""
    oid = str(op.get("id") or "").strip()
    if oid:
        for i, entry in enumerate(ledger):
            if str(entry.get("id") or "") == oid:
                return i
    subject = _normalized_fact(op.get("subject"))
    if not subject:
        return None
    for i, entry in enumerate(ledger):
        entry_subject = _normalized_fact(entry.get("subject"))
        if entry_subject and (subject in entry_subject
                              or entry_subject in subject):
            return i
    return None


def commit_world_pressure(ctx, nonce):
    """Apply this beat's world-pressure ops to the world-KV world_pressures
    ledger. Deterministic semantics:

    - open: registers an ongoing off-character process with threat/escalation
      potential (deduped by subject). Sources: director_resolve ops every
      normal beat, plus director_establish's openers on the opening turn.
    - tick: the process escalated ON-PAGE this beat -- level += 1, the
      held-streak resets.
    - hold: an explicit, deliberate no-advance -- the streak still grows, so
      a pressure cannot be held forever without tripping the must-tick flag,
      but no warning: holding is a legitimate choice when made visibly.
    - resolve: the process ended; the entry leaves the ledger.
    - SILENCE (an open entry no op mentions): treated as an implicit hold
      AND warned -- the exact failure mode this ledger exists for (the
      Enterprise Array: an actively scanned alien artifact produced zero
      world response across 12 beats because nothing forced the Director to
      even decline to act).

    After ops, any entry whose held-streak has reached
    WORLD_PRESSURE_STALL_AGE is warned as stalled; the next beat's payload
    flags it must_tick_this_beat and agents/director.py enforces that flag
    with a bounded correction retry."""
    cid = ctx.chat.id
    turn = ctx.turn
    res = ctx.director_resolve or {}
    ops = list(res.get("world_pressure") or []) \
        if isinstance(res.get("world_pressure"), list) else []
    if turn.idx == 0:
        est = ctx.director_establish or {}
        est_ops = est.get("world_pressure")
        if isinstance(est_ops, list):
            # Establishment may only OPEN pressures -- there is no prior beat
            # to tick or hold against.
            ops = [op for op in est_ops if isinstance(op, dict)
                   and str(op.get("op") or "open").lower() == "open"] + ops

    ledger = [
        dict(entry)
        for entry in (wget(cid, "world_pressures", []) or [])
        if isinstance(entry, dict) and entry.get("subject")
    ]

    opened = ticked = held = resolved = 0
    addressed = set()
    for op in ops:
        if not isinstance(op, dict):
            continue
        op_kind = str(op.get("op") or "").strip().lower()
        if op_kind == "open":
            subject = str(op.get("subject") or "").strip()
            if not subject or _find_pressure(ledger, op) is not None:
                continue
            ledger.append({
                "id": f"wp:{turn.idx}:{opened}",
                "subject": subject,
                "note": str(op.get("note") or "").strip(),
                "level": 0,
                "opened_turn": turn.idx,
                "last_tick_turn": turn.idx,
                "held_streak": 0,
            })
            opened += 1
        elif op_kind in ("tick", "hold", "resolve"):
            idx = _find_pressure(ledger, op)
            if idx is None:
                ctx.add_warning(
                    f"world_pressure {op_kind} matched no open ledger entry: "
                    f"{(op.get('id') or op.get('subject') or '')!r}"
                )
                continue
            entry = ledger[idx]
            addressed.add(id(entry))
            if op_kind == "tick":
                entry["level"] = int(entry.get("level") or 0) + 1
                entry["last_tick_turn"] = turn.idx
                entry["held_streak"] = 0
                if str(op.get("note") or "").strip():
                    entry["note"] = str(op.get("note")).strip()
                ticked += 1
            elif op_kind == "hold":
                entry["held_streak"] = int(entry.get("held_streak") or 0) + 1
                held += 1
            else:
                ledger.pop(idx)
                resolved += 1

    unaddressed = 0
    stalled = 0
    for entry in ledger:
        if id(entry) in addressed or entry.get("opened_turn") == turn.idx:
            continue
        # Silence is a choice, but never a silent one.
        entry["held_streak"] = int(entry.get("held_streak") or 0) + 1
        unaddressed += 1
        ctx.add_warning(
            f"World pressure unaddressed: {entry.get('subject')!r} "
            f"(id {entry.get('id')}) got neither tick nor hold this beat; "
            "recorded as an implicit hold."
        )
    for entry in ledger:
        if int(entry.get("held_streak") or 0) >= WORLD_PRESSURE_STALL_AGE:
            stalled += 1
            ctx.add_warning(
                f"World pressure stalled: {entry.get('subject')!r} has gone "
                f"{entry.get('held_streak')} beats without advancing. It is "
                "flagged must_tick_this_beat for the next resolve."
            )

    if len(ledger) > WORLD_PRESSURE_CAP:
        ledger = ledger[-WORLD_PRESSURE_CAP:]
    wset(cid, "world_pressures", ledger)
    return {"opened": opened, "ticked": ticked, "held": held,
            "resolved": resolved, "unaddressed": unaddressed,
            "stalled": stalled, "open": len(ledger)}

# ---- Memory commit ----

# How many of a character's most recent physical tells (manifest cues) are
# kept on cstate as the anti-repetition ledger fed back into the character
# payload (see agents/character.py's TELL VARIETY block).
RECENT_TELLS_CAP = 6

def _durable_dialogue_category(text):
    lowered = (text or "").lower()
    if any(w in lowered for w in ("promise", "i swear", "i vow", "you have my word",
                                   "i'll return", "i will return")):
        return "promise"
    if any(w in lowered for w in ("my name is", "call me", "i confess", "the truth is",
                                   "i killed", "i betrayed", "i love you", "i hate you",
                                   "i'll kill", "i will kill")):
        return "dialogue"
    return None

def _cited_memory_ids(own_result):
    """Memory ids this mind used as EVIDENCE for a belief it formed this beat.

    Consequence, not popularity. Retrieval on its own never moves importance:
    a memory that gets recalled would then rank higher and get recalled more,
    which is a feedback loop wearing the word. Even citation is downstream of
    retrieval, so the loop is closed structurally instead of hoped away --
    `raise_importance` is called with `only_unrevised=True`, so a given memory
    can be lifted by citation exactly once, ever. The signal is "this turned
    out to be load-bearing at least once", which is boolean by nature.

    Bare `observations_used` deliberately does not count. Citing a memory while
    describing the beat is not the same as building a belief on it, and the
    weaker signal is the one that fires on almost every turn.

    Returns `event_key`s, because that is what a character actually cites. The
    first version of this required a numeric memory ROW id and was therefore
    dead on arrival -- across a 10-turn live run it matched nothing, while the
    handles the characters really wrote were `current`, `current:39:4`,
    `turn:2:character:39:0:action` and `event:<hash>`. The last of those IS the
    memory's `event_key` (`_stable_event_key`), and all five distinct ones
    emitted in that run resolved to a real row. The format was there the whole
    time; the reader was looking for one nothing produces.

    THE SAME MISTAKE, ONE LAYER UP. Having fixed the id format, this still read
    a single field, and measured over the beats that could have supplied any of
    them (`tools/fire_rates.py`):

        mind_model_updates evidence citing a stored memory     6 of 83
        belief_updates evidence citing a stored memory         1 of 83
        memory_effects, disposition `integrated`              74 of 83

    Importance has been revised on 9 of 6,460 memories, and that is why: the
    one signal being read is the rarest thing a character emits, while the
    field that says exactly what this function is looking for -- the character
    stating that a recalled memory changed their recognition, appraisal, choice
    or speech -- fires on 89% of eligible beats and was never consulted.

    `memory_effects` is a STRONGER consequence signal than citation, not a
    weaker one. Its prompt says in as many words: do not emit one merely
    because a row was present. `resisted` and `dismissed` do not count -- a
    memory the character pushed away did influence the beat, but recording that
    as "turned out to matter" would make importance a measure of salience-at-
    recall rather than of consequence. `only_unrevised=True` still holds the
    ceiling at one lift per memory for its whole life, so widening the inputs
    widens the population that can be lifted once, never the amount.

    `belief_updates` is included because the docstring's first line has always
    claimed it: a belief formed on a memory is the paradigm case. It contributes
    almost nothing at present, which is a fact about how models cite, not a
    reason to keep reading the wrong field.
    """
    if not isinstance(own_result, dict):
        return []
    out = set()
    for field in ("mind_model_updates", "belief_updates"):
        for update in own_result.get(field) or []:
            if not isinstance(update, dict):
                continue
            for ref in update.get("evidence") or []:
                if not isinstance(ref, dict):
                    continue
                raw = str(ref.get("event_id") or "").strip()
                # "current" and the turn:/character: handles name this beat or
                # an act within it, not a stored memory.
                if raw.startswith("event:"):
                    out.add(raw)
    for effect in own_result.get("memory_effects") or []:
        if not isinstance(effect, dict):
            continue
        if str(effect.get("disposition") or "").strip() != "integrated":
            continue
        raw = str(effect.get("memory_ref") or "").strip()
        if raw.startswith("event:"):
            out.add(raw)
    return sorted(out)


def _marked_for_memory(own_result, qbody):
    """Did this character ask to keep this line (CharacterOutput.remember_lines)?

    Matched on the quote body, loosely in both directions: a model asked to
    echo a quote will trim or extend it by a word, and rejecting the mark over
    that would make the feature depend on transcription rather than intent.
    Loose matching is safe HERE and would not be elsewhere -- the caller has
    already proved this quote was said this beat and reached this observer, so
    the only thing being decided is whether a line the character definitely
    heard is also one they keep.
    """
    body = " ".join(str(qbody or "").split()).casefold()
    if not body or not isinstance(own_result, dict):
        return None
    for mark in own_result.get("remember_lines") or []:
        if not isinstance(mark, dict):
            continue
        want = " ".join(str(mark.get("quote") or "").split()).casefold()
        want = _quote_body(want)
        if not want:
            continue
        if want == body or want in body or body in want:
            return mark
    return None


def _quote_body(quote):
    return (quote or "").strip().strip('"' + "'" + "\u201c\u201d\u2018\u2019")

def _room_of(scene, name):
    positions = scene.get("positions") or {}
    if name in positions:
        return positions[name]
    lname = (name or "").lower().strip()
    for k, v in positions.items():
        if k.lower().strip() == lname:
            return v
    # Script-aware: the old ASCII fold erased every non-Latin name to "",
    # so this fallback could never match one.
    norm = fold_identity_key(lname)
    if norm:
        for k, v in positions.items():
            if fold_identity_key(k) == norm:
                return v
    return None

def _is_player(speaker, chat):
    from agents import is_player_speaker
    return is_player_speaker(speaker, chat)

def _salience_of(text):
    s = 0.45 + min(len(text or ""), 400) / 1600.0
    for w in ("attack", "blood", "secret", "betray", "kiss", "dead",
              "weapon", "threat", "love", "steal", "scream", "knife",
              "confess", "liar", "promise"):
        if w in (text or "").lower():
            s += 0.08
    return round(min(s, 0.95), 3)


def _own_sequence_memory(seq):
    """Render a no-view fallback as grammatical, chronological first person.

    The witnessed perception view is the normal episode and already contains
    the resolved conduct.  This formatter is only for a character who acted
    but received no usable view; it must preserve order without the old
    ``I chose to attempted`` construction or a gist cut midway through an act.
    """
    clauses = []
    for event in (seq or []):
        if not isinstance(event, dict):
            continue
        if event.get("type") == "speech" and str(event.get("text") or "").strip():
            spoken = str(event["text"]).strip()
            clauses.append(
                f"I said {spoken!r}" + ("" if spoken[-1] in ".!?" else "."))
        elif event.get("type") == "action" and str(event.get("attempt") or "").strip():
            clauses.append(f"I tried to {str(event['attempt']).strip().rstrip('.')}.")
    if not clauses:
        return "", ""
    content = " Then ".join(clauses)
    gist_parts = []
    for clause in clauses:
        candidate = " Then ".join(gist_parts + [clause])
        if len(candidate) > 240:
            break
        gist_parts.append(clause)
    gist = " Then ".join(gist_parts) if gist_parts else clauses[0][:239].rstrip() + "…"
    return content, gist

def prepare_memory_commit(ctx, *, scene=None):
    """Build and embed all per-character memory mutations without writes."""
    chat = ctx.chat
    turn = ctx.turn
    cid = chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    # Build a fresh list -- never mutate res["dialogue_log"], since the
    # director_resolve step/variant was already persisted before
    # background_react ran (see agents/perception.py's merge comment). The
    # deterministic backstop line is merged only for rendering there; fold
    # it into the persisted event record here too, so hearers mint dialogue
    # memories of it and it reaches _promotion_evidence.
    dlog = list(res.get("dialogue_log") or [])
    for _r in _background_fired_reactions(ctx.get("background_react")):
        dlog.append({**_r["dialogue_log_entry"], "source": "background_react"})
    views = (
        (ctx.perception_outcome or {}).get("views")
        or (ctx.perception_establish or {}).get("views")
        or {}
    )
    # IR-minted episodes (deterministic composer, PERCEPTION_NO_LLM): when
    # perception composed the views, it also minted each character's episode
    # directly from the percept IR -- first person, event-bearing content
    # first, typed entities -- instead of the second-person view prose. A
    # composed "" is a NON-EVENT (all standing state, nothing changed) and
    # mints nothing; absent keys fall back to the view exactly as before.
    _composed_episodes = (ctx.perception_outcome or {}).get("episodes")
    if not isinstance(_composed_episodes, dict):
        _composed_episodes = None
    _composed_episode_meta = (
        (ctx.perception_outcome or {}).get("episode_meta") or {}
        if _composed_episodes is not None else {}
    )
    est = ctx.director_establish
    sc = scene if scene is not None else (wget(cid, "scene", {}) or {})
    pending_memories = []
    state_updates = []
    # Names learned by hearing them said, accumulated per hearer and applied
    # by commit_memories inside the transaction -- this function runs BEFORE
    # the write lock and must not write. See _names_heard_in.
    _name_roster = _known_name_roster(chat, ctx.cast)
    _names_learned = {}
    relationship_ops = []
    belief_reconciles = []
    memory_disputes = []
    importance_bumps = []
    _clock = wget(
        cid, "simulation_clock",
        {"elapsed_seconds": 0.0, "display": "now"},
    ) or {}
    _time_diff = ((res.get("state_diff") or {}).get("time")
                  if isinstance(res.get("state_diff"), dict) else None)
    if isinstance(_time_diff, dict):
        # The same monotonic read as the scene commit's, from the same
        # helper. This site read the raw `end_seconds` for two releases
        # after the clock itself was guarded, so a backwards beat stamped
        # affect decay, strain windows and belief provenance with a clock
        # the scene commit had just refused to store.
        _clock_seconds, _ = _monotonic_elapsed(_clock, _time_diff)
    else:
        _clock_seconds = float(_clock.get("elapsed_seconds") or 0.0)

    # Loop-invariant inputs to the place-claim rekey below, hoisted: the scene
    # rooms, the cast roster, and the persona do not change while this loop
    # runs, but they were being rebuilt (a full room walk plus a name
    # resolution per cast member) inside EVERY iteration that carried
    # mind_model_updates -- O(cast^2) name derivations on a full table.
    from scene import persona_of as _persona_of
    _rekey_place_names = [
        str((room or {}).get("name") or rid)
        for rid, room in (sc.get("rooms") or {}).items()
    ]
    _rekey_protected = [character_name_from_text(_r["sheet"])
                        for _r in ctx.cast]
    _rekey_protected.append(persona_name(_persona_of(chat)))

    for char_row in ctx.cast:
        ccid = char_row["id"]
        sh = json.loads(char_row["sheet"])
        st = json.loads(char_row["cstate"] or "{}")
        v = views.get(str(ccid))
        episode_content = ""
        _episode_entities = []
        _episode_gist = ""
        # Side records (durable quotes) are emitted after the coherent episode
        # row so storage order mirrors their role: event first, annotations
        # second.  They remain separately retrievable by provenance.
        side_memories = []
        cname = character_name(sh)
        char_room = _room_of(sc, cname)
        room_data = (sc.get("rooms") or {}).get(char_room, {})
        room_name = room_data.get("name") or char_room or ""
        # BOTH LOOPS, MERGED. The interaction loop merges its rounds into
        # `ctx.character_results`; the reaction loop writes to
        # `ctx.reaction_results` and nothing here ever read it, so everything
        # a REACTING mind worked out was dropped -- silently, because the
        # appliers below were handed empty lists and had nothing to warn
        # about.
        #
        # Measured across the 82 stored reaction beats in the corpus: every
        # single one carried interior content that never committed -- 159
        # mind_model_updates, 93 relationship_updates, 20 belief_updates, 18
        # remember_lines, 12 association_updates, and the only three project
        # adoptions the engine has ever produced (chats 70/71/72, one beat
        # across three branches: the Doctor committing to reach a shrine).
        # A reaction is the beat with the most immediate pressure on a
        # character, and they were forming theories about people and marking
        # things worth remembering into nothing.
        #
        # MERGED rather than chosen between, because a character can both
        # react and act in one beat, and the same union `_merge_character_
        # results` already performs across micro-rounds is the right one
        # here: accumulating lists combine, latest scalar state wins.
        from agents.common import _merge_character_results
        own_result = _merge_character_results(
            ctx.reaction_results.get(ccid),
            ctx.character_results.get(ccid)) or {}
        own_result = _normalize_character_output(own_result)
        # Place claims are re-keyed onto their place ONCE, up here, before
        # ANYTHING reads mind_model_updates. The inference memory minted for a
        # claim (below) and the hypothesis it is merged under (further down,
        # via apply_mind_model_updates) must share one subject key: minting
        # from the raw updates while merging the rekeyed ones stamped the
        # memory's entities[0] with a subject that never exists in
        # mind_models, so reconcile_inference_confidence could never find the
        # live hypothesis and demoted the row as abandoned from the start.
        _mm_updates = own_result.get("mind_model_updates") or []
        if _mm_updates:
            _mm_updates = rekey_place_claims(
                _mm_updates, _rekey_place_names, protected=_rekey_protected)
        active_state = own_result.get("active_state") or {}
        mood = str(active_state.get("mood") or "")
        # The character's blended surface affect this beat carries the numeric
        # valence/arousal that go with the `mood` label; without this the
        # emotional_context text was stored but valence/arousal stayed at their
        # 0.0 default on every memory (the memory editor showed them as always
        # zero). Mirror the label onto the numeric axes for this beat's memories.
        # THE MOOD THIS MEMORY WAS FORMED IN -- the character's RESOLVED affect,
        # not the self-report they opened the beat with.
        #
        # `resolve_affect` is what turns a model's proposed mood into the one
        # the character actually holds: decayed toward baseline, moved by this
        # beat's appraisal, and cross-checked against the label. It runs at the
        # psychology commit, ~500 lines below this one, so a memory minted here
        # can never see it -- it took the raw proposal instead.
        #
        # Measured across the same characters: the raw self-report averages
        # +0.773 with 0% negative, while their resolved affect averages +0.467
        # with 22% negative. The two disagree by +0.31, and only one of them is
        # a mood. Stored memories inherited the saturated one: newer stories
        # sat at a median valence of +0.85 with 4 negatives in 3,162 rows,
        # which is not an emotional axis, it is a constant -- and it silently
        # disables everything downstream that reads affect.
        #
        # The stored value is last beat's resolution, i.e. the mood the
        # character carried INTO this event. That is what encoding-time affect
        # should be: how you felt while it was happening, before the beat's own
        # appraisal moved you. The self-report is kept as the fallback for a
        # character with no resolved affect yet (their first beat).
        _surface = (((st.get("active_state") or {}).get("affect") or {})
                    .get("surface") or {})
        if not _surface:
            _surface = (active_state.get("affect") or {}).get("surface") or {}
        try:
            _mem_valence = float(_surface.get("valence") or 0.0)
            _mem_arousal = float(_surface.get("arousal") or 0.0)
        except (TypeError, ValueError):
            _mem_valence, _mem_arousal = 0.0, 0.0
        # Fallback for legacy/no-psychology turns: after equals before.  The
        # resolved appraisal below replaces these when it exists.
        _encoding_valence, _encoding_arousal = _mem_valence, _mem_arousal
        # --- Unbidden-recall ledger: the character stage proposed this beat's
        # probe on its step output (deterministic trigger state, and whether a
        # contrasting memory was surfaced); commit is the only writer of the
        # durable ledger, exactly like recent_tells. Placed BEFORE any st
        # mutation below so the previous beat's goal is still readable for
        # the same-beat "did it help" check. Nothing here ever mints a memory
        # row: a surfaced memory is context handed to the character, and only
        # what the character then DOES (speech, mind-model claims) is
        # canonical.
        _probe = own_result.get("unbidden_probe")
        if isinstance(_probe, dict):
            _led = dict(st.get("unbidden") or {})
            _probe_ref = str(_probe.get("memory_ref") or "")
            _effectful = any(
                isinstance(e, dict)
                and str(e.get("memory_ref") or "") == _probe_ref
                and str(e.get("disposition") or "").casefold()
                    not in {"", "dismissed", "ignored", "none"}
                and bool(str(e.get("changed") or "").strip())
                for e in (own_result.get("memory_effects") or []))
            _goal_before = str(((st.get("active_state") or {}).get("goal"))
                               or "")
            # The RAW emitted goal was read here to ask "did the goal move off
            # its snapshot" -- the third reader of that field the 2026-08-11
            # audit missed. The template no longer asks for it, so derive the
            # same text the psychology commit below will keep (the enacted
            # want's), with the legacy field as fallback; both sides of the
            # comparison (this and the `pending` snapshot) go through the one
            # derivation, so "moved" keeps meaning what it meant.
            from agents.common import declared_goal as _declared_goal
            _goal_now = _declared_goal(own_result)
            _pending = (_led.get("pending")
                        if isinstance(_led.get("pending"), dict) else None)
            if _pending is not None and turn.idx > int(_pending.get("turn")
                                                       or -1):
                # The beat AFTER an injection: it helped if the stuckness
                # cleared or the goal moved off its snapshot.
                _helped = (not _probe.get("stuck")
                           or _goal_now != str(_pending.get("goal") or ""))
                _outs = [o for o in (_led.get("outcomes") or [])
                         if isinstance(o, dict)]
                _outs = (_outs + [{"turn": turn.idx,
                                   "helped": bool(_helped)}])[-4:]
                _led["outcomes"] = _outs
                if (len(_outs) >= 2 and not _outs[-1]["helped"]
                        and not _outs[-2]["helped"]):
                    # Two consecutive injections that moved nothing: the
                    # character is stuck for a reason contrast cannot reach.
                    # Suppressed until the trigger is observed fully clear.
                    _led["suppressed"] = True
                _led.pop("pending", None)
            if not _probe.get("stuck"):
                _led["clear_seen"] = True
                _led["suppressed"] = False
            if _probe.get("fired") and _probe.get("memory_id") is not None:
                try:
                    _mid = int(_probe["memory_id"])
                except (TypeError, ValueError):
                    _mid = None
                if _mid is not None:
                    _led["last_turn"] = turn.idx
                    _led["last_trigger"] = str(_probe.get("trigger") or "")
                    _rids = [i for i in (_led.get("recent_ids") or [])
                             if isinstance(i, int) and i != _mid]
                    _led["recent_ids"] = (_rids + [_mid])[-8:]
                    _led["clear_seen"] = False
                    if _effectful or (_goal_now and _goal_now != _goal_before):
                        # Helped on the injection beat itself.
                        _led["outcomes"] = ([
                            o for o in (_led.get("outcomes") or [])
                            if isinstance(o, dict)]
                            + [{"turn": turn.idx, "helped": True}])[-4:]
                    else:
                        _led["pending"] = {
                            "turn": turn.idx, "goal": _goal_now,
                            **({"memory_ref": _probe_ref}
                               if _probe_ref else {})}
            _led["repeat_flag"] = bool(_probe.get("repeat_survived"))
            st["unbidden"] = _led
        if est and not v:
            room_label = char_room or "the scene"
            room_data2 = (sc.get("rooms") or {}).get(room_label, {})
            room_name2 = room_data2.get("name") or room_label
            room_desc = room_data2.get("desc") or room_data2.get("notes") or ""
            v = f"The scene opens. You are in {room_name2}." + (
                f" {room_desc}" if room_desc else ""
            )
        if v:
            # F2/P1: dialogue memory recognition gate. The speaker's
            # canonical name was stored regardless of whether the hearer
            # recognizes them, leaking identity into memory. Check the
            # hearer's known map -- if the speaker isn't recognized, store
            # an appearance-based label or "a voice" instead, and drop
            # intended_target (which also names the speaker).
            _known_map = wget(cid, "known", {}) or {}
            _hearer_known = set(_known_map.get(cname) or [])
            for d in dlog:
                spk = d.get("speaker", "")
                # The player used to be rewritten to the literal "the player"
                # here and then EXEMPTED from the recognition gate below, so a
                # character's own memory read `the player said "My Name is
                # Hinami." to Dr. Moon` -- the engine's out-of-fiction word for
                # the protagonist, inside a fictional mind, in the very memory
                # where they learned her name. 68 rows across the live corpus.
                # The player is a body in the room like any other: pass the
                # persona's real name in and let the gate decide, exactly as it
                # does for every character.
                _spk_is_player = _is_player(spk, chat)
                if _spk_is_player:
                    from scene import persona_of
                    spk = persona_name(persona_of(ctx.chat)) or spk
                if spk == cname:
                    continue
                # Recognition gate: the canonical name only if the hearer knows
                # the speaker. The label comes from _unknown_actor_label, the
                # same helper every perception path uses, rather than a second
                # hand-rolled copy of it -- the copy truncated at a fixed 60
                # characters and cut mid-word, and two implementations of the
                # identity floor drift apart exactly where it matters.
                if spk not in _hearer_known:
                    from agents.common import (
                        _unknown_actor_label, character_scene_keys)
                    if _spk_is_player:
                        from scene import persona_of
                        _spk_sheet = persona_of(ctx.chat)
                    else:
                        _spk_sheet = next(
                            (sheet for sheet in
                             (json.loads(_cr["sheet"]) for _cr in ctx.cast)
                             if character_name(sheet) == spk),
                            None)
                    spk_label = _unknown_actor_label(
                        spk,
                        _char_appearance(_spk_sheet) if _spk_sheet else None,
                        character_scene_keys(_spk_sheet)[1:] if _spk_sheet else None,
                    )
                    # This memory is HEARD. When there is no appearance to
                    # describe, _unknown_actor_label falls back to "the
                    # unfamiliar person" -- which claims the hearer saw a body.
                    # What they have is a voice.
                    if spk_label == "the unfamiliar person":
                        spk_label = "a voice"
                    tgt = None  # drop intended_target -- it names the speaker
                else:
                    spk_label = spk
                    tgt = d.get("intended_target")
                quote = d.get("exact_quote", "")
                qbody = _quote_body(quote)
                if qbody and (quote in v or qbody in v):
                    # This line reached THIS hearer's view -- the audibility
                    # question is already answered above, so a name inside it
                    # is a name they heard. See _names_heard_in.
                    for _learned in _names_heard_in(
                            qbody, cname, _name_roster, sc, char_room):
                        if _learned not in _hearer_known:
                            _hearer_known.add(_learned)
                            _names_learned.setdefault(cname, []).append(_learned)
                    category = _durable_dialogue_category(qbody)
                    memory_mark = _marked_for_memory(own_result, qbody)
                    # This mind asked to keep the line. The phrase list is a
                    # floor of what ANYONE would remember; what a particular
                    # character finds durable is a fact about that character,
                    # so their own declaration is allowed to add to it -- never
                    # to remove, since the floor exists for the model that
                    # declares nothing. Bounded by everything above: the quote
                    # must have been said this beat and must have reached THIS
                    # observer's view, so a mark can only preserve something
                    # already heard.
                    if not category and memory_mark:
                        category = "dialogue"
                    if category:
                        side_memories.append({
                            "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                            "turn_idx": turn.idx, "kind": "dialogue", "category": category,
                            "provenance": "heard",
                            "salience": 0.9 if category == "promise" else 0.82,
                            "content": f"{spk_label} said {quote}" + (f" to {tgt}" if tgt else ""),
                            "gist": f"{spk_label}: {qbody}", "key_phrases": [qbody, spk_label],
                            "entities": [spk_label], "location": room_name,
                            "emotional_context": " — ".join(
                                p for p in (
                                    mood,
                                    ("kept because " + str(
                                        memory_mark.get("why") or "").strip())
                                    if memory_mark and str(
                                        memory_mark.get("why") or "").strip()
                                    else "",
                                ) if p),
                            "valence": _mem_valence, "arousal": _mem_arousal,
                            "event_key": _stable_event_key(
                                turn.id, ccid, "dialogue", d.get("speaker"),
                                qbody, d.get("intended_target"),
                            ),
                        })
            episode_content = v
            # IR-minted episode (see the top of this function): the composer
            # already rendered this mind's episode from the same gated,
            # fidelity-degraded percepts its view rendered -- never richer --
            # with typed entities instead of names scraped back out of prose
            # (memory.py's `_extract_entities` fallback).
            if _composed_episodes is not None and str(ccid) in _composed_episodes:
                episode_content = str(_composed_episodes.get(str(ccid)) or "")
                _meta = _composed_episode_meta.get(str(ccid)) or {}
                _episode_entities = [
                    str(e) for e in (_meta.get("entities") or [])
                    if str(e or "").strip()]
                _episode_gist = str(_meta.get("gist") or "").strip()
            # A view that says only "you are somewhere unspecified" is the
            # ABSENCE of an event, and an absence is not an episode. Minted
            # anyway, it becomes a retrievable memory carrying no information:
            # measured live, 356 rows across five stories -- 7.3% of the whole
            # bank, and a THIRD of one story's -- were the single sentence
            # "You are in an unspecified area.", all at salience 0.47, all
            # identical, all eligible to be handed to a character instead of
            # something that happened.
            #
            # It arises legitimately (an NPC off in unloaded space) and
            # illegitimately (`character_room`'s docstring calls the same
            # phrase "leaking a false empty view" from a position it could not
            # resolve). The cause does not change the remedy: either way there
            # is nothing to remember, so nothing is written. The turn still
            # happened and the turn index still records it. The composer
            # generalizes this floor upstream: a percept list that is all
            # unchanged standing state renders an EMPTY episode, so the
            # marker check below is the backstop, not the mechanism.
            if _is_empty_view(episode_content):
                episode_content = ""
        if episode_content:
            _episode_row = {
                "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                "turn_idx": turn.idx, "kind": "episodic", "category": "episode",
                "provenance": "witnessed", "salience": _salience_of(episode_content),
                "content": episode_content, "location": room_name,
                "emotional_context": mood,
                "valence": _mem_valence, "arousal": _mem_arousal,
                "event_key": _stable_event_key(turn.id, ccid, "episode"),
            }
            if _episode_entities:
                _episode_row["entities"] = _episode_entities
            if _episode_gist:
                _episode_row["gist"] = _episode_gist
            pending_memories.append(_episode_row)
        pending_memories.extend(side_memories)
        if own_result:
            # Ponder is a private, deliberate retrieval request for the NEXT
            # character turn. The character stage removed it from the public
            # sequence, so it never becomes a world action. Consume an older
            # pending query only when this mind actually produced a committed
            # result, then optionally stage one new bounded query.
            _pending_ponder = (st.get("memory_ponder")
                               if isinstance(st.get("memory_ponder"), dict)
                               else {})
            try:
                _ponder_due = int(_pending_ponder.get("set_turn")) < turn.idx
            except (TypeError, ValueError):
                _ponder_due = False
            if _ponder_due:
                st.pop("memory_ponder", None)
            _new_ponder = (own_result.get("ponder")
                           if isinstance(own_result.get("ponder"), dict)
                           else {})
            _ponder_query = " ".join(
                str(_new_ponder.get("query") or "").split())[:240]
            _ponder_why = " ".join(
                str(_new_ponder.get("why") or "").split())[:240]
            if _ponder_query and _ponder_why:
                st["memory_ponder"] = {
                    "query": _ponder_query,
                    "why": _ponder_why,
                    "set_turn": turn.idx,
                }
                # Telemetry only, never a gate: a useful answer is allowed to
                # raise a new deliberate question immediately.
                st["last_ponder_turn"] = turn.idx
            seq = own_result.get("sequence") or []
            own_salience = float(own_result.get("salience", 0.0))
            should_store_own_acts = bool(seq) and (
                own_salience >= 0.7
                or any(event.get("type") == "speech" for event in seq)
            )
            # The observer-specific view is already the coherent, resolved
            # first-person episode.  Storing the declaration again beside it
            # split one beat into competing fragments (and often replayed an
            # attempted act as though it were a second event).  Keep a self
            # row only as the no-view fallback.
            if should_store_own_acts and not episode_content:
                self_content, self_gist = _own_sequence_memory(seq)
                pending_memories.append({
                    "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                    "turn_idx": turn.idx, "kind": "episodic", "category": "self",
                    "provenance": "remembered", "salience": max(0.5, own_salience),
                    "content": self_content,
                    "gist": self_gist,
                    "location": room_name, "emotional_context": mood,
                    "valence": _mem_valence, "arousal": _mem_arousal,
                    "event_key": _stable_event_key(turn.id, ccid, "own_acts"),
                })
            # The REKEYED updates (see the top of this loop body), so the
            # memory row's subject matches the key the hypothesis will live
            # under in mind_models.
            for update in _mm_updates:
                confidence = _clamp(update.get("confidence", 0.5))
                evidence = "; ".join(
                    str(item.get("fact") or "").strip()
                    for item in update.get("evidence") or []
                    if isinstance(item, dict)
                    and str(item.get("fact") or "").strip()
                )
                about = str(update.get("about_entity") or "").strip()
                claim = str(update.get("claim") or "").strip().rstrip(".")
                prefix = "" if claim.casefold().startswith(
                    about.casefold() + " ") else (f"About {about}: " if about else "")
                inference_content = f"{prefix}{claim}."
                if evidence:
                    inference_content += f" Evidence: {evidence}"
                pending_memories.append({
                    "chat_id": cid, "char_id": ccid, "turn_id": turn.id,
                    "turn_idx": turn.idx, "kind": "inference", "category": "inference",
                    "provenance": "inferred", "salience": 0.45 + 0.3 * confidence,
                    "confidence": confidence,
                    "content": inference_content,
                    "gist": claim if len(claim) <= 240 else claim[:239].rsplit(" ", 1)[0] + "…",
                    "entities": [about] if about else [],
                    "location": room_name, "emotional_context": mood,
                    "event_key": _stable_event_key(
                        turn.id, ccid, "mind_model", update.get("about_entity"),
                        update.get("kind"), update.get("claim"),
                    ),
                })
            # --- Interior depth: deterministic floors over the model's proposed
            # active_state (goals + blended affect). All fields are optional;
            # absent ones degrade to the legacy {mood,goal}. affect.py is pure;
            # this is the single write point where the floors apply.
            if own_result.get("active_state") is not None:
                asv = own_result.get("active_state")
                if not isinstance(asv, dict):
                    asv = {"mood": str(asv), "goal": ""}
                prev_as = st.get("active_state") if isinstance(st.get("active_state"), dict) else {}
                interior = st.get("interior") if isinstance(st.get("interior"), dict) else {}
                intentions = interior.get("intentions") or []
                # How much this mind holds at once: the authored rung, narrowed
                # by one at the top of the absorption range. Read off the body
                # the character came INTO this beat with, because that is the
                # state they decided it in -- the settled figure below governs
                # the next beat, and using it here would apply a consequence of
                # the beat to the deliberation that produced it.
                _want_cap, _intent_cap = affect.capacity_caps(
                    character_psychology(sh).get("capacity"),
                    psychology_runtime.cognitive_absorption(
                        prev_as.get("hedonic"), prev_as.get("stress")))
                # Seed the character's AUTHORED standing intentions (from the
                # card's initial_state.goals) into the live list, so the model
                # can progress/close them via intent_ops and they persist and
                # evolve. Dedup by text against the CURRENT list (including any
                # already-abandoned/blocked copy), so a goal the character has
                # set aside never re-seeds. Mirrors the read-side merge in
                # agents/character._merge_standing_intentions.
                _seen_intent = {str(i.get("intent") or "").strip().casefold()
                                for i in intentions if isinstance(i, dict)}
                for _a in character_standing_intentions(sh):
                    if str(_a.get("intent") or "").strip().casefold() not in _seen_intent:
                        intentions = intentions + [_a]
                # PROJECTS (Tier 1.5): durable-but-not-eternal commitments,
                # capped at two -- see affect.apply_project_ops and
                # docs/design/DESIGN_LONG_TERM_GOALS.md. Authored ones seed from
                # the card exactly as standing intentions do, deduped
                # against live AND former so a project the character gave
                # up (with a stated reason) never silently re-seeds over
                # that decision. NOTE: _interior_out below is rebuilt from
                # scratch each beat, so both ledgers must be carried
                # through it explicitly or a beat would erase them.
                projects = [dict(p) for p in (interior.get("projects") or [])
                            if isinstance(p, dict)]
                former_projects = [
                    dict(p) for p in (interior.get("former_projects") or [])
                    if isinstance(p, dict)]
                # Deduped on ID as well as text. Text alone is not enough:
                # a project's wording can legitimately CHANGE after adoption
                # -- the maze harness appends the goal room's name the beat
                # the character first stands in it, which is the moment that
                # identifier becomes legitimately his -- and a text-keyed
                # check then stops recognising the authored source and seeds
                # a second copy of the same project. Measured live: `pa1`
                # held twice, one project occupying both slots, which defeats
                # the cap that is the entire point of the tier.
                _seen_proj = {
                    str(p.get("project") or "").strip().casefold()
                    for p in projects + former_projects}
                _seen_pids = {str(p.get("id") or "")
                              for p in projects + former_projects}
                for _p in character_projects(sh):
                    if len(projects) >= affect.PROJECT_CAP:
                        break
                    if str(_p.get("id") or "") in _seen_pids:
                        continue
                    if str(_p.get("project") or "").strip().casefold() \
                            not in _seen_proj:
                        # Seeding counts as service: the drift clock starts
                        # at the seeding beat, never at authored turn 0.
                        projects = projects + [
                            dict(_p, last_served_turn=turn.idx)]
                projects, former_projects, _pwarn = affect.apply_project_ops(
                    projects, former_projects,
                    own_result.get("project_ops") or [], turn.idx)
                for w in _pwarn:
                    ctx.add_warning(f"{cname}: project -- {w}")
                _project_ids = {str(p.get("id") or "") for p in projects}
                # Probationary vs established, as the character SAW them at
                # the start of this beat (pre-settlement, like valid_ids
                # for intentions): a probationary project weighs at
                # intention level until service establishes it.
                _probation_ids = {str(p.get("id") or "") for p in projects
                                  if p.get("probation")}
                _established_ids = _project_ids - _probation_ids
                drive = (character_psychology(sh) or {}).get("drive") or {}

                # this beat's evidence pool: resolved event + spoken lines, for
                # gating intention satisfy/abandon (light floor: cited + present).
                _ev_text = (res.get("resolved_event") or "") + " " + " ".join(
                    str(d.get("exact_quote") or "") for d in dlog)

                def _evidence_ok(op, _t=_ev_text):
                    ev = op.get("evidence") or []
                    if not ev:
                        return False
                    return any(str(e) and str(e) in _t for e in ev) or bool(op.get("why"))

                _before_status = {
                    str(i.get("id")): i.get("status")
                    for i in intentions if isinstance(i, dict)
                }
                intentions, _iwarn = affect.apply_intent_ops(
                    intentions, own_result.get("intent_ops") or [], turn.idx,
                    _evidence_ok, intent_cap=_intent_cap)
                # OUTCOME FEEDBACK. Everything else in this engine revises a
                # belief by CONTRADICTION -- another claim -- never by whether
                # acting on it worked. So a character who concludes something,
                # acts, and is wrong sees that belief decay from disuse at
                # exactly the rate a correct one would, and a route that
                # demonstrably reached a goal accumulates no weight against the
                # novelty of one that has not been tried.
                #
                # An intention reaching `satisfied` is the one success signal
                # the engine can observe without trusting a bare self-report:
                # apply_intent_ops gates satisfy behind _evidence_ok, so it
                # needs on-screen cause. When one closes, the rooms walked
                # while pursuing it are credited -- their own route, no oracle
                # knowledge of whether it was the BEST way, only that it was a
                # way that worked.
                _satisfied = [
                    i for i in intentions
                    if isinstance(i, dict) and i.get("status") == "satisfied"
                    and _before_status.get(str(i.get("id"))) != "satisfied"
                ]
                if _satisfied:
                    _worked = st.get("routes_that_worked")
                    if not isinstance(_worked, dict):
                        _worked = {}
                    _since = max(
                        0, len(st.get("visited_rooms") or [])
                        - ROUTE_CREDIT_WINDOW)
                    for _r in set((st.get("visited_rooms") or [])[_since:]):
                        _worked[_r] = min(
                            ROUTE_CREDIT_CAP, int(_worked.get(_r, 0)) + 1)
                    st["routes_that_worked"] = _worked
                for w in _iwarn:
                    ctx.add_warning(f"{cname}: intention -- {w}")
                _steering = affect.steering_intent_ids(intentions, turn.idx)
                # A known id is not automatically a current purpose. Dormant,
                # blocked, satisfied and abandoned intentions remain in the
                # ledger for continuity, but cannot legitimize a fresh want by
                # appearing in `serves`. `_steering` deliberately includes an
                # intention closed THIS beat (last_progress_turn == turn.idx),
                # so a payoff is not demoted because of state the character
                # could not have seen when deciding. A goal already spent at
                # the START of the beat is absent and normalizes to situational.

                def _priority(serves, _ids=_steering, _intents=intentions,
                              _projs=projects, _pids=_established_ids,
                              _probs=_probation_ids):
                    # Models emit serves as "intention:<id-or-text>" or
                    # "project:<id-or-text>"; resolve to the bare id so a
                    # goal-serving impact scores at its tier's priority, not
                    # the situational default. An ESTABLISHED project weighs
                    # at DRIVE priority (1.0) -- the 1.0-vs-0.8 loss is the
                    # measured failure the project tier exists to close; a
                    # probationary one at intention priority (0.8) -- drive
                    # weight is earned by service, never by adoption.
                    serves = affect.normalize_serves(serves, _intents, _projs)
                    return affect.serves_priority(str(serves), _ids, _pids,
                                                  _probs)

                wants, enacted, suppressed = affect.normalize_wants(
                    asv.get("wants") or [], _steering | _project_ids,
                    want_cap=_want_cap)

                appraisal_input = dict(own_result.get("appraisal") or {})
                # Past experience may change familiarity, expectation and
                # perceived coping resources. It may also produce a mild body
                # echo or prime threat detection, but may not manufacture
                # current pain/pleasure, a present threat, or a goal event.
                # Apply every contribution only through the separately
                # grounded memory_modulation lane.
                _mod = appraisal_input.get("memory_modulation")
                _memory_echo = {}
                if isinstance(_mod, dict) and _mod.get("evidence"):
                    try:
                        _familiarity = max(
                            0.0, min(1.0, float(_mod.get("familiarity") or 0.0)))
                        _coping_effect = max(
                            -1.0, min(1.0, float(
                                _mod.get("coping_effect") or 0.0)))
                        _somatic_echo = max(
                            -1.0, min(1.0, float(
                                _mod.get("somatic_echo") or 0.0)))
                        _threat_bias = max(
                            0.0, min(1.0, float(
                                _mod.get("threat_bias") or 0.0)))
                    except (TypeError, ValueError):
                        (_familiarity, _coping_effect,
                         _somatic_echo, _threat_bias) = 0.0, 0.0, 0.0, 0.0
                    appraisal_input["novelty"] = max(
                        0.0, min(1.0,
                                 float(appraisal_input.get("novelty") or 0.0)
                                 * (1.0 - 0.35 * _familiarity)))
                    appraisal_input["coping_potential"] = max(
                        0.0, min(1.0,
                                 float(appraisal_input.get(
                                     "coping_potential") or 0.5)
                                 + 0.25 * _coping_effect))
                    # The model reports a normalized tendency; the engine
                    # decides how much reaches live state. One recalled beat
                    # can move either axis by at most 0.2, and the result stays
                    # explicitly labelled remembered_past.
                    _memory_echo = {
                        "somatic": round(0.2 * _somatic_echo, 4),
                        "threat_bias": round(0.2 * _threat_bias, 4),
                        "why": str(_mod.get("why") or "")[:240],
                        "source_refs": [
                            str(e.get("event_id") or "")
                            for e in (_mod.get("evidence") or [])
                            if isinstance(e, dict) and e.get("event_id")
                        ],
                        "temporal_source": "remembered_past",
                    }
                    appraisal_input["memory_echo"] = _memory_echo
                proposed_hedonic = (
                    asv.get("hedonic") if isinstance(asv.get("hedonic"), dict)
                    else {}
                )
                # The appetite this body carried INTO the beat, so appraisal can
                # tell a goal that completed from a drive that is being fed --
                # a confirmed win on an unreleased drive is not a reason to
                # stand down. Read before resolve_hedonic recomputes it, and
                # zeroed the moment the character declares the release, which
                # is the beat satisfaction becomes true.
                _prev_hedonic = (prev_as.get("hedonic")
                                 if isinstance(prev_as.get("hedonic"), dict)
                                 else {})
                _unresolved_drive = (
                    0.0 if bool(proposed_hedonic.get("released"))
                    else _prev_hedonic.get("charge") or 0.0
                )
                appraisal_out = affect.appraise(
                    appraisal_input.get("goal_impacts") or [], _priority,
                    dimensions=appraisal_input,
                    unresolved_drive=_unresolved_drive,
                )
                prev_affect = prev_as.get("affect") if isinstance(prev_as, dict) else None
                baseline = ((prev_affect or {}).get("baseline")
                            or character_initial_active_state(sh)["affect"]["baseline"])
                turns_since = max(1, turn.idx - int(prev_as.get("affect_turn") or (turn.idx - 1)))
                elapsed_units = psychology_runtime.elapsed_psych_units(
                    prev_as.get("affect_seconds"), _clock_seconds, turns_since)
                # Surface habituation (affect.py's _HABITUATION_* block):
                # default off, the shipped behaviour byte-for-byte. Switched
                # per install by the `affect_habituation` setting, read here
                # because affect.py deliberately imports no db. The release
                # flag is the character's own declared hedonic discharge --
                # the same one resolve_hedonic below receives -- which is
                # what lets a climax land uncompressed while the plateau
                # before it settles.
                _habituate = str(
                    get_setting("affect_habituation") or ""
                ).strip().casefold() in ("1", "on", "true")
                new_affect = affect.resolve_affect(
                    prev_affect, appraisal_out, baseline, elapsed_units,
                    proposed=asv.get("affect") or asv.get("mood"),
                    habituate=_habituate,
                    released=bool(proposed_hedonic.get("released")))
                _encoded_surface = new_affect.get("surface") or {}
                _encoding_valence = float(
                    _encoded_surface.get("valence") or 0.0)
                _encoding_arousal = float(
                    _encoded_surface.get("arousal") or 0.0)
                body_state = vitals_of(sc, cname)
                # World-side comfort, from the settled scene: what this body
                # is verifiably against (station/contact/posture, closed
                # vocabulary). Feeds the pleasure LEVEL floor only -- by
                # construction it never reaches the charge term, because a
                # warm bench is a resolved state, not an unresolved drive.
                _comfort, _comfort_src = comfort_level(sc, cname)
                new_hedonic = psychology_runtime.resolve_hedonic(
                    prev_as.get("hedonic"), appraisal_out,
                    character_interoception(sh), body_state, elapsed_units,
                    # Discharging an accumulated drive is the character's own
                    # event to have, so the declaration is theirs; how it built
                    # up in the first place stays the runtime's.
                    released=bool(proposed_hedonic.get("released")),
                    ambient_comfort=_comfort, comfort_source=_comfort_src,
                )
                proposed_stress = (
                    asv.get("stress") if isinstance(asv.get("stress"), dict) else {}
                )
                new_stress = psychology_runtime.resolve_stress(
                    prev_as.get("stress"), appraisal_out,
                    (character_psychology(sh) or {}).get("stress_profile") or {},
                    new_hedonic, elapsed_units,
                    proposed_mode=proposed_stress.get("coping_mode"),
                )

                # Leak tripwire: this character's OWN speech must not state a
                # suppressed want / the undercurrent / an unenacted intention.
                own_speech = [str(d.get("exact_quote") or "") for d in dlog
                              if d.get("speaker") == cname]
                for w in affect.leak_scan(own_speech, wants,
                                          new_affect.get("undercurrent"), intentions):
                    ctx.add_warning(f"{cname}: interior leak -- {w}")

                surface = new_affect.get("surface") or {}
                # The goal slot IS the enacted want's text -- measured on 401
                # recent-era calls: this branch took the want on 99.0% of
                # them, and the emitted goal string it used to fall back on
                # matched that want only 16.2% of the time, so the template
                # stopped asking for it. The fallback chain ends at the
                # PREVIOUS goal, never at empty: a beat with malformed wants
                # is the 1% case, and blanking the slot there silently killed
                # a standing aim -- goal routing, tenure and the unbidden
                # ledger all read this slot, and "" is a decision the
                # character never made. A legacy provider still emitting
                # asv.goal keeps its say first.
                enacted_goal = (wants[enacted]["want"]
                                if (wants and enacted is not None
                                    and 0 <= enacted < len(wants))
                                else asv.get("goal")
                                or prev_as.get("goal") or "")
                st["active_state"] = {
                    "mood": surface.get("label") or str(asv.get("mood") or ""),
                    "goal": str(enacted_goal or ""),
                    # canonical valence/arousal, projected to the flat legacy keys.
                    "valence": float(surface.get("valence") or 0.0),
                    "arousal": float(surface.get("arousal") or 0.0),
                    "affect": new_affect,
                    "wants": wants,
                    "enacted_want": enacted,
                    "suppressed_want": suppressed,
                    "affect_turn": turn.idx,
                    "affect_seconds": _clock_seconds,
                    "stress": new_stress,
                    "hedonic": new_hedonic,
                    # One-beat, source-labelled state. Deliberately separate
                    # from hedonic pain/pleasure and from current observations.
                    "memory_echo": _memory_echo,
                    "active_concerns": (
                        asv.get("active_concerns")
                        or prev_as.get("active_concerns")
                        or character_initial_active_state(sh).get("active_concerns")
                        or []
                    ),
                }
                # --- Project service ledger + boundary review (Tier 1.5).
                # A held project stopped failing by being outranked and
                # started failing by being FORGOTTEN (A15 run 5: pa1 held at
                # weight 1.0, twenty beats in, nothing emitted serving it).
                # Two deterministic facts close that gap: last_served_turn
                # per project (read back as `adrift` in the payload), and a
                # one-beat review flag when a boundary the engine can
                # actually see has passed. Facts only -- nothing here writes
                # a want or applies an op.
                from agents.common import character_room as _char_room_of
                _named_rooms = {}
                for _nrid, _nrec in (((st.get("place_graph") or {})
                                      .get("nodes")) or {}).items():
                    if isinstance(_nrec, dict):
                        _nname = str(_nrec.get("name") or "").strip()
                        if _nname:
                            _named_rooms.setdefault(_nname.casefold(),
                                                    str(_nrid))
                # Beat-goal slot currency: the slot is rewritten every
                # commit from the enacted want, but the CLAIM inside it is
                # whatever the model re-emits, and nothing above counts its
                # tenure or notices its named room has been reached. Stamp
                # both facts here (goal_since / goal_room /
                # goal_room_reached); agents/character reads them back as
                # `goal_held` / `goal_reached` and stops ROUTING on a spent
                # claim -- see affect.goal_slot_currency.
                st["active_state"].update(affect.goal_slot_currency(
                    prev_as, str(enacted_goal or ""), _named_rooms,
                    _char_room_of(sc, sh), turn.idx))
                for _p in projects:
                    # One-shot backfill for projects that predate the ledger
                    # (a live pa1 exists): grace from here, never instantly
                    # adrift on the deploy beat. NOT setdefault -- the live
                    # pa1 was measured carrying an explicit
                    # last_served_turn: null, which setdefault preserves,
                    # leaving the ledger dead and the drift marker silent
                    # forever.
                    try:
                        int(_p.get("last_served_turn"))
                    except (TypeError, ValueError):
                        _p["last_served_turn"] = turn.idx
                _impact_serves = [
                    affect.normalize_serves(
                        str((gi or {}).get("serves") or ""),
                        intentions, projects)
                    for gi in (appraisal_input.get("goal_impacts") or [])
                    if isinstance(gi, dict)]
                for _pid in affect.projects_served_this_beat(
                        projects, wants, str(enacted_goal or ""),
                        _impact_serves, _named_rooms):
                    for _p in projects:
                        if str(_p.get("id") or "") == _pid:
                            _p["last_served_turn"] = turn.idx
                            # Distinct serving beats, for establishment:
                            # probation is left by service, never survival.
                            _p["served_beats"] = 1 + int(
                                _p.get("served_beats") or 0)
                # Probation settles AFTER this beat's service counted:
                # runtime adoptions establish once lived into (drive weight
                # from the NEXT beat) or lapse quietly once unserved past
                # the fuse. Authored/harness projects carry no probation
                # flag and pass through untouched.
                projects, former_projects, _probw = affect.settle_probation(
                    projects, former_projects, turn.idx)
                for w in _probw:
                    ctx.add_warning(f"{cname}: project -- {w}")
                # Boundary detection runs BEFORE record_spatial_experience
                # (below, line ~4100), so st["visited_rooms"] still ends at
                # the previous position while sc already holds the new one
                # -- which is exactly the arrival comparison needed.
                _prev_room = next(
                    (str(r) for r in reversed(st.get("visited_rooms") or [])
                     if isinstance(r, str) and r), None)
                _scene_marker = (interior.get("scene_marker")
                                 if isinstance(interior.get("scene_marker"),
                                               dict) else None)
                _loc_now = str(sc.get("location") or "")
                _review_why = affect.project_boundary(
                    projects, intentions, _before_status,
                    _char_room_of(sc, sh), _prev_room, _scene_marker,
                    _loc_now, turn.frame_id, _named_rooms)
                # --- Drive rupture (Tier 1): a deterministic strain ledger and
                # two-key gate that can, rarely and earned, crack the core drive.
                def _serves_of(i):
                    return (str(wants[i].get("serves") or "")
                            if (isinstance(wants, list) and isinstance(i, int)
                                and 0 <= i < len(wants)) else "")
                strain = float(interior.get("drive_strain") or 0.0)
                strain_log = list(interior.get("strain_log") or [])
                _strain_turns = max(1, turn.idx - int(interior.get("strain_turn") or (turn.idx - 1)))
                _strain_elapsed = psychology_runtime.elapsed_psych_units(
                    interior.get("strain_seconds"), _clock_seconds, _strain_turns)
                strain, _slog = affect.update_drive_strain(
                    strain, strain_log, appraisal_out,
                    _serves_of(enacted), _serves_of(suppressed), _strain_elapsed)
                if _slog:
                    _slog["turn"] = turn.idx
                    strain_log = (strain_log + [_slog])[-12:]
                cur_drive = effective_drive(character_psychology(sh), interior)
                former = list(interior.get("former_drives") or [])
                last_shift = interior.get("last_shift_turn")
                override = interior.get("drive_override") if isinstance(interior.get("drive_override"), dict) else None
                rupture = interior.get("drive_rupture") if isinstance(interior.get("drive_rupture"), dict) else None
                window_open = bool(rupture and turn.idx <= int(rupture.get("window_expires") or -1))
                if not window_open:
                    _det = affect.detect_drive_rupture(strain, appraisal_out, turn.idx, last_shift)
                    if _det:
                        rupture = {"turn": turn.idx, "opened_turn": turn.idx,
                                   "why": _det.get("why"),
                                   "direction": _det.get("direction"), "window_expires": turn.idx + 3}
                        ctx.add_warning(f"{cname}: DRIVE RUPTURE window opened -- {_det.get('why')}")
                elif own_result.get("drive_shift"):
                    _norm, _kind, _vw = affect.validate_drive_shift(
                        own_result.get("drive_shift"), cur_drive, former, rupture)
                    for w in _vw:
                        ctx.add_warning(f"{cname}: drive_shift -- {w}")
                    if _norm and _kind == "break":
                        _rw = str(rupture.get("why") or "")
                        former = (former + [affect.former_drive_entry(cur_drive, turn.idx, _rw)])[-5:]
                        override = {**_norm, "since_turn": turn.idx, "by_event": _rw}
                        strain, last_shift, rupture = 0.0, turn.idx, None
                        ctx.add_warning(f"{cname}: DRIVE SHIFTED -> {_norm.get('essence')}")
                        pending_memories.append({
                            "chat_id": cid, "char_id": ccid, "turn_id": turn.id, "turn_idx": turn.idx,
                            "kind": "episode", "category": "self", "provenance": "remembered", "salience": 1.0,
                            "content": (f"Something in me broke when {_rw}. What I lived for -- "
                                        f"{cur_drive.get('essence')} -- no longer holds me. Now I live for: "
                                        f"{_norm.get('essence')}."),
                            "gist": f"drive shift -> {_norm.get('essence')}"[:240],
                            "entities": [cname], "location": room_name,
                            "emotional_context": surface.get("label") or "",
                            "event_key": _stable_event_key(turn.id, ccid, "drive_shift", cname,
                                                           _norm.get("essence"), ""),
                        })
                    elif _norm and _kind == "bend":
                        override = {**_norm, "since_turn": turn.idx, "by_event": str(rupture.get("why") or "")}
                        strain, last_shift, rupture = strain * 0.5, (turn.idx - 30), None
                if rupture and turn.idx > int(rupture.get("window_expires") or -1):
                    _opened_turn = int(rupture.get("opened_turn") or rupture.get("turn") or turn.idx)
                    _turns_open = turn.idx - _opened_turn
                    if strain >= affect.RUPTURE_STRAIN_MIN \
                            and _turns_open < affect.RUPTURE_MAX_OPEN:
                        # Strain still at rupture level and the hard cap not yet
                        # reached: the crisis is unresolved, so the window RE-OPENS
                        # (extends) instead of quietly closing -- denial is a phase,
                        # not an exit. (agents/character.py escalates the prompt to a
                        # FORCED resolution once the window has been open
                        # RUPTURE_FORCE_AFTER turns, so this extension is not the
                        # unpressured "you MAY" it used to be.)
                        rupture = {**rupture, "window_expires": turn.idx + 3}
                        ctx.add_warning(
                            f"{cname}: drive-rupture window extended -- "
                            f"strain {strain:.2f} still at rupture level")
                    else:
                        # Force-close: either strain finally decayed below the floor,
                        # OR the window has been open RUPTURE_MAX_OPEN turns with no
                        # shift. A model that will not shift within the forced window
                        # has, in effect, reaffirmed the drive under maximal pressure
                        # -- so resolve the crisis (pay strain down below the floor)
                        # rather than leaving the character in a permanent, never-
                        # resolving limbo (the 23-turn Vorne case).
                        if strain >= affect.RUPTURE_STRAIN_MIN:
                            strain = affect.RUPTURE_STRAIN_MIN * 0.75
                            ctx.add_warning(
                                f"{cname}: drive-rupture force-closed after "
                                f"{_turns_open} turns unresolved -- drive reaffirmed "
                                f"under pressure, strain paid down")
                        else:
                            strain = strain * 0.5   # weathered the crisis, no shift
                        rupture = None
                _interior_out = {
                    "intentions": intentions,
                    # Both project ledgers, every beat: this dict is rebuilt
                    # from scratch, and a key not carried here is a key
                    # silently erased.
                    "projects": projects,
                    "former_projects": former_projects,
                    # Where and in which frame this beat committed -- what
                    # project_boundary compares against next beat. Written
                    # unconditionally so a project adopted later still meets
                    # a fresh marker.
                    "scene_marker": {"location": _loc_now,
                                     "frame": str(turn.frame_id or "")},
                    "drive_strain": round(float(strain), 4),
                    "strain_log": strain_log,
                    "former_drives": former,
                    "last_shift_turn": last_shift,
                    "strain_turn": turn.idx,
                    "strain_seconds": _clock_seconds,
                    "beliefs": psychology_runtime.apply_belief_updates(
                        interior.get("beliefs"), character_psychology(sh),
                        own_result.get("belief_updates") or [], turn.idx,
                        _clock_seconds,
                    ),
                    "associations": psychology_runtime.apply_association_updates(
                        interior.get("associations"), character_psychology(sh),
                        own_result.get("association_updates") or [], turn.idx,
                        _clock_seconds,
                    ),
                }
                if rupture is not None:
                    _interior_out["drive_rupture"] = rupture
                if override is not None:
                    _interior_out["drive_override"] = override
                if _review_why:
                    # One-beat flag: _interior_out is rebuilt each commit,
                    # so this clears itself unless a new boundary fires.
                    _interior_out["project_review"] = {
                        "turn": turn.idx, "why": _review_why}
                st["interior"] = _interior_out
            # --- Recent-tell ledger: the last few physical cues this
            # character has shown, kept on cstate and fed back into the
            # next character payload (self.recent_tells) so the model
            # stops reaching for the same gesture every beat.
            _tells = [t for t in ((own_result.get("manifest") or {}).get("tells") or [])
                      if isinstance(t, dict)]
            _cues = [str(t.get("cue") or "").strip() for t in _tells]
            _cues = [c for c in _cues if c]
            if _cues:
                _prev_cues = [str(c) for c in (st.get("recent_tells") or [])
                              if str(c).strip()]
                st["recent_tells"] = (_prev_cues + _cues)[-RECENT_TELLS_CAP:]
            # --- Tell-ground ledger (F6): each shown cue with the private
            # ground it betrayed (`because`, grounded at the character stage
            # by affect.ground_tells), kept on cstate and fed back as
            # self.tell_grounds so a later beat can pay the tell off. Same
            # cap as the cue ledger; grounds never leave the character's own
            # private context.
            _grounds = [
                {"cue": str(t.get("cue") or "").strip(),
                 "because": str(t.get("because") or "").strip(),
                 "turn": turn.idx}
                for t in _tells
                if str(t.get("cue") or "").strip()
                and str(t.get("because") or "").strip()
            ]
            if _grounds:
                _prev_grounds = [
                    g for g in (st.get("tell_grounds") or [])
                    if isinstance(g, dict) and str(g.get("cue") or "").strip()
                ]
                st["tell_grounds"] = (_prev_grounds + _grounds)[-RECENT_TELLS_CAP:]
            stance = st.get("stance") or sh.get("stance") or {"axes": {}}
            for u in own_result.get("stance_updates") or []:
                ax = u.get("axis")
                if not ax:
                    continue
                try:
                    stance.setdefault("axes", {})
                    # P9: the schema clamps each DELTA, but the running total
                    # was unbounded -- a character nudged the same direction
                    # every beat walked past the [-1, 1] the axes are read as
                    # (character_schema seeds them from baseline_stances in
                    # that range), and every consumer downstream then compared
                    # against a scale the value had left. Clamped here because
                    # this is the only place the accumulation happens; a reroll
                    # re-applying a delta is P2's problem, not this one.
                    stance["axes"][ax] = round(
                        max(-1.0, min(1.0,
                            float(stance["axes"].get(ax, 0))
                            + float(u.get("delta", 0)))),
                        3,
                    )
                    stance.setdefault("log", []).append({
                        "turn": turn.idx, "axis": ax,
                        "delta": u.get("delta"), "trigger": u.get("trigger"),
                    })
                except Exception:
                    pass
            st["stance"] = stance
            # Rooms this body has actually walked through, the exits of rooms
            # stood in, visibly-closed chambers, and the durable place graph
            # -- everything a beat of standing somewhere earns, recorded in
            # one place (see record_spatial_experience). Their OWN traversal
            # history and sight, so it crosses no information boundary.
            # Lazy, like the other agents.common uses in this module: importing
            # it at module scope would close an import cycle.
            from agents.common import character_room as _character_room
            record_spatial_experience(
                st, sc, _character_room(sc, sh), turn.idx)
            # Place purpose, witnessed basis: their OWN vitals rising across
            # consecutive commits settled in this room (they ate here; they
            # rested here), or their body verifiably lying on a soft support
            # (comfort.rest_affording -- the seam comfort.py left for exactly
            # this writer). Runs after record_spatial_experience so the
            # standing room's node exists. Never the event row.
            import place_purpose
            place_purpose.witness_affords(st, sc, cname, turn.idx)
            # _mm_updates was rekeyed once at the top of this loop body (a
            # claim about a PLACE is re-keyed onto that place before it is
            # merged, because hypotheses group by (about_entity, kind) and
            # explain each other away within a group -- correct for a mind,
            # backwards for space; people stay protected). The SAME rekeyed
            # list minted this turn's inference memories above, so memory
            # subject and hypothesis key cannot drift apart.
            # Absorption is read off the state we just settled, so it reflects
            # the body at the END of the beat -- the state the character
            # actually comes out of it in, which is what governs what they can
            # still hold in mind going into the next one.
            _settled = st.get("active_state") or {}
            _absorption = psychology_runtime.cognitive_absorption(
                _settled.get("hedonic"), _settled.get("stress"))
            st = apply_mind_model_updates(
                st, _mm_updates, turn.idx, elapsed_seconds=_clock_seconds,
                absorption=_absorption,
            )
            # Place purpose, told basis: stated-fact place beliefs (already
            # re-keyed onto place names above) mirrored onto this character's
            # OWN place-graph nodes, and every existing told entry's sureness
            # re-asked from belief_credence -- the node entry is a read-model
            # of the belief, and a belief explained away must stop steering
            # (docs/design/DESIGN_PLACE_PURPOSE.md, mandatory drift rule). Runs
            # AFTER the merge so it reads reconciled beliefs, mirroring how
            # reconcile_inference_confidence treats memories.
            place_purpose.mirror_told_affords(st, turn.idx, _clock_seconds)
            # Re-selected on every beat this character acted in, not only when
            # `_mm_updates` is non-empty: capacity tracks the BODY, so someone
            # merely in more pain than last beat holds fewer open questions
            # even though they concluded nothing new.
            _sheet, _sheet_keys = select_active_hypotheses(
                st.get("mind_models") or {},
                st.get("active_hypothesis_keys"),
                sheet_capacity(_absorption),
                turn.idx,
                elapsed_seconds=_clock_seconds,
                absorption=_absorption,
            )
            st["active_hypotheses"] = _sheet
            st["active_hypothesis_keys"] = _sheet_keys
            if _mm_updates:
                # Only characters whose beliefs actually moved this turn are
                # reconciled: the reconcile scans that character's whole
                # inference bank, and a belief cannot be abandoned on a turn
                # nothing was claimed about it.
                belief_reconciles.append(
                    (cid, ccid, st, _clock_seconds))
            explicit_updates = own_result.get("relationship_updates") or []
            if explicit_updates:
                relationship_ops.append(("explicit", ccid, explicit_updates))
            elif own_result.get("inference_updates"):
                relationship_ops.append(
                    ("inference", ccid, own_result.get("inference_updates") or [])
                )
            # This mind re-read one of its own memories. Deferred to the write
            # phase with everything else: prepare_memory_commit is pure.
            for _d in own_result.get("memory_disputes") or []:
                if isinstance(_d, dict):
                    memory_disputes.append(
                        (cid, ccid, str(_d.get("gist") or ""),
                         str(_d.get("now_reads") or ""), turn.idx,
                         str(_d.get("memory_ref") or "")))
            # Consequence, not popularity: a memory the character cited as
            # EVIDENCE for a belief they formed this beat turned out to be
            # load-bearing. Retrieval alone never moves importance -- that
            # would make often-recalled memories more recallable, which is a
            # feedback loop wearing the word.
            _cited = _cited_memory_ids(own_result)
            if _cited:
                importance_bumps.append((ccid, _cited))
        # Every memory minted for this mind on this beat records both the
        # affect carried into the event (valence/arousal) and the resolved
        # affect after appraisal (encoding_*).  Assign here, after every
        # possible append including inference memories.
        for _memory in pending_memories:
            if _memory.get("char_id") == ccid:
                _memory["encoding_valence"] = _encoding_valence
                _memory["encoding_arousal"] = _encoding_arousal
        state_updates.append((cid, ccid, json.dumps(st)))

    event_content = json.dumps({
        "turn": turn.idx,
        "summary": res.get("summary") or "",
        "event": res.get("resolved_event") or "",
        "dialogue_log": dlog,
    })
    memory_batch = prepare_memories_batch(pending_memories)
    # A missing or failing embeddings provider silently downgrades every
    # vector to the local character-trigram hash, which then scores as a
    # fuzzy-lexical signal forever (an audit of a live corpus found 100% of
    # rows on the fallback with nothing anywhere saying so). The batch already
    # records the downgrade; surface it where every other turn anomaly goes.
    _embedded = memory_batch.get("embedded")
    if _embedded is not None and getattr(_embedded, "fallback", False):
        ctx.add_warning(
            "memory embeddings fell back to local hashing "
            f"({getattr(_embedded, 'error', '') or 'no embeddings provider'});"
            " semantic recall is degraded until an embeddings provider is "
            "configured")
    return {
        "memory_batch": memory_batch,
        "names_learned": _names_learned,
        "state_updates": state_updates,
        "relationship_ops": relationship_ops,
        "belief_reconciles": belief_reconciles,
        "memory_disputes": memory_disputes,
        "importance_bumps": importance_bumps,
        "event_content": event_content,
    }


def _consolidate_committed_memories(ctx):
    """Update derived autobiographical summaries after the atomic commit.

    Summaries are reconstructible caches, not primary turn facts.  Keeping
    their LLM calls outside the transaction avoids deadlocks and ensures a
    consolidation failure can never roll back an otherwise valid turn.

    This is the DIRECT, blocking form -- commit_memories' standalone path
    and tests use it. The live turn pipeline no longer does: consolidation
    is a background summarisation job, and running it on the `utility` role
    inside the player's wait was measured at 29.5s of a 45.8s commit stage
    (chat 71 turn 10, the first beat to reach the consolidation cadence).
    `schedule_memory_consolidation` below is the out-of-band twin the commit
    tail actually calls.
    """
    cid = ctx.chat.id
    turn = ctx.turn
    notes = []

    def _consolidate_one(char_row):
        try:
            result = maybe_consolidate_character_memory(
                cid, char_row["id"], turn.idx, frame_id=turn.frame_id,
            )
            if result:
                return (
                    f"{character_name_from_text(char_row['sheet'])}: "
                    "autobiographical summary updated"
                )
        except Exception as exc:
            ctx.add_warning(
                f"Memory consolidation failed for character {char_row['id']}: {exc}"
            )
        return None

    if ctx.cast:
        # A bare pool worker starts from an EMPTY context, so the story
        # language was lost and `memory_consolidate` resolved to English --
        # writing English autobiography into a Japanese story's memory bank.
        # `agents/narration.py` and `agents/director.py` copy the context for
        # exactly this reason; this pool was missed.
        parent = contextvars.copy_context()

        def _consolidate_in_context(char_row):
            return parent.run(_consolidate_one, char_row)

        with ThreadPoolExecutor(max_workers=len(ctx.cast)) as pool:
            for note in pool.map(_consolidate_in_context, ctx.cast):
                if note:
                    notes.append(note)
    return notes


MEMORY_CONSOLIDATION_JOB_KEY = "memory_consolidation"


def schedule_memory_consolidation(ctx):
    """Queue this turn's autobiographical consolidation out of band.

    Returns the Job, or None when there is no cast or one is already in
    flight for this chat. Called from the commit tail AFTER the turn's
    facts are durable, on the same terms as the offscreen ticks beside it:
    a summary is a reconstructible cache derived from committed rows, so
    nothing about correctness changes -- only who waits for it. Measured
    cost of waiting: the first consolidation of a live chat took 29.5s
    (27.4s of it one `utility`-role LLM call) inside the commit stage's
    wall clock.

    The job snapshots the scalars it needs (ids, names, turn, frame) so it
    never touches ctx after the turn returns. Sequential per character with
    a cancellation check between -- abandonable at every unit boundary --
    and a failure for one character is logged and skipped, never raised:
    background work cannot break a turn, and the cadence check re-offers
    the window on a later beat. Deduped on the chat by jobs.submit: a
    consolidation still running when the next beat commits simply keeps
    running, and that beat schedules nothing (maybe_consolidate re-reads
    the cursor, so nothing is lost -- only deferred). Checkpoint restore
    cancels the in-flight job cooperatively (see checkpoints.py) so a
    rolled-back turn does not land a summary computed from rows that no
    longer exist; the residual window -- a restore arriving mid-LLM-call --
    is recorded in docs/UNBUILT.md.
    """
    import jobs

    cid = ctx.chat.id
    turn_idx = ctx.turn.idx
    frame_id = ctx.turn.frame_id
    members = [
        {"id": row["id"],
         "name": character_name_from_text(row["sheet"])}
        for row in (ctx.cast or [])
    ]
    if not members:
        return None

    def _produce(job):
        # Fresh thread, fresh contextvars: pin the scheduling turn's frame
        # for every frame-scoped read/write below (the offscreen tick
        # producers set the precedent, and the reason -- a nested frame's
        # consolidation landing in the present frame -- is the same).
        from db import active_frame_id
        from logging_utils import logger
        token = active_frame_id.set(frame_id)
        try:
            notes = []
            for member in members:
                if job.cancelled.is_set():
                    break
                try:
                    result = maybe_consolidate_character_memory(
                        cid, member["id"], turn_idx, frame_id=frame_id,
                    )
                    if result:
                        notes.append(f"{member['name']}: autobiographical "
                                     "summary updated")
                except Exception as exc:
                    # Silence toward the turn, a trace toward the operator:
                    # the cadence re-offers this window next beat.
                    logger.info(
                        "memory consolidation failed out of band: chat=%s "
                        "char=%s error=%s", cid, member["id"],
                        str(exc)[:300])
            return notes
        finally:
            active_frame_id.reset(token)

    return jobs.submit(cid, MEMORY_CONSOLIDATION_JOB_KEY, _produce,
                       base_turn=turn_idx)


def commit_memories(ctx, nonce, *, prepared=None, consolidate=True):
    prepared = prepared or prepare_memory_commit(ctx)
    turn = ctx.turn
    cid = ctx.chat.id

    with transaction():
        # A name heard this beat, of somebody standing in the room. Applied
        # here rather than in prepare, which runs outside the write lock;
        # merged rather than assigned, because `validated_introductions` may
        # have written the same map earlier in this turn and an explicit
        # introduction must not be lost to an overwrite.
        _learned = prepared.get("names_learned") or {}
        if _learned:
            _known = wget(cid, "known", {}) or {}
            for _hearer, _names in _learned.items():
                _known.setdefault(_hearer, [])
                for _name in _names:
                    if _name not in _known[_hearer]:
                        _known[_hearer].append(_name)
            wset(cid, "known", _known)
        delete_turn_memories(turn.id)
        memory_ids = add_memories_batch(
            prepared_batch=prepared["memory_batch"],
        )
        for kind, char_id, updates in prepared["relationship_ops"]:
            if kind == "explicit":
                # The frame goes with it: a branch that never had the argument
                # must not inherit the reason it happened.
                apply_relationship_updates(cid, char_id, turn.idx, updates,
                                           frame_id=ctx.turn.frame_id)
            else:
                update_relationships_from_inference(
                    cid, char_id, turn.idx, updates,
                )
        for chat_id, char_id, state_json in prepared["state_updates"]:
            set_char_state(
                chat_id, char_id, state_json, frame_id=turn.frame_id,
            )
        # After the batch insert AND after the state write, so this turn's own
        # freshly-minted inference rows are re-weighted by the same reconciled
        # mind_models everything else now reads -- a claim minted at the
        # model's declared confidence and then blended/suppressed by
        # apply_mind_model_updates would otherwise sit in the bank at the
        # pre-blend number forever.
        for chat_id, char_id, char_state, clock_seconds in prepared.get(
                "belief_reconciles") or []:
            reconcile_inference_confidence(
                chat_id, char_id, char_state, turn.idx,
                elapsed_seconds=clock_seconds,
            )
        # A mind re-reading one of its own memories. Scoped to that character's
        # own rows inside record_dispute, so this can never reach across the
        # firewall however the model phrased the gist.
        for chat_id, char_id, _gist, _reading, _tidx, _ref in prepared.get(
                "memory_disputes") or []:
            try:
                record_dispute(chat_id, char_id, _gist, _reading, _tidx,
                               memory_ref=_ref)
            except Exception as exc:
                ctx.add_warning(f"memory dispute not recorded: {exc}")
        # Memories that turned out to be load-bearing for a belief. Once each,
        # ever (`only_unrevised`), which is what keeps this a consequence
        # rather than a popularity loop -- see _cited_memory_ids.
        for char_id, ids in prepared.get("importance_bumps") or []:
            try:
                raise_importance(cid, char_id, event_keys=ids,
                                 only_unrevised=True)
            except Exception as exc:
                ctx.add_warning(f"memory importance not updated: {exc}")
        qi(
            """INSERT INTO events(chat_id,turn_id,content) VALUES(?,?,?)
            ON CONFLICT(chat_id,turn_id) WHERE turn_id IS NOT NULL
            DO UPDATE SET content=excluded.content""",
            (cid, turn.id, prepared["event_content"]),
        )

    committed = [f"memory:{mid}" for mid in memory_ids]
    if consolidate:
        committed.extend(_consolidate_committed_memories(ctx))
    return {"committed": committed}

# ---- Narration-person commit ----

_NARRATION_PERSONS = ("first", "second", "third")

def commit_narration_person(ctx, nonce):
    """Apply the narration-person detections the narrator stages recorded on
    their returned step content (`narration_person_writes`) but deliberately
    did not persist themselves -- commit.py is the sole persistence boundary,
    and the narrator previously did a durable wset mid-pipeline, before the
    turn was validated/committed (so an aborted or rolled-back turn had
    already flipped the campaign's narration voice). Deterministically
    validated: only `narration_person*` keys with a known person value are
    written, since step content is inspectable and manually editable.
    """
    cid = ctx.chat.id
    applied = 0
    sources = []
    if isinstance(ctx.narrator, dict):
        sources.append(ctx.narrator)
    extra = ctx.get("narrator_extra") or {}
    if isinstance(extra, dict):
        sources.extend(v for v in extra.values() if isinstance(v, dict))
    with transaction():
        for out in sources:
            writes = out.get("narration_person_writes")
            if not isinstance(writes, dict):
                continue
            for key, value in writes.items():
                if (isinstance(key, str) and key.startswith("narration_person")
                        and value in _NARRATION_PERSONS):
                    wset(cid, key, value)
                    applied += 1
    return {"applied": applied}

# ---- Top-level atomic commit ----

def commit_authored_events(ctx, nonce):
    """P4: resolve this beat's DUE authored (player-scheduled) future events
    against the resolved prose (fire / bounded re-queue / stale), then mint any
    NEW ones the Director captured this turn from a future-tense player
    assertion (flow.scheduled_assertions). Runs inside the turn transaction so a
    rollback un-does both -- a rerun re-mints with stable ids (no double
    schedule) and re-resolves idempotently."""
    from authored_events import mint_authored_events, resolve_authored_events
    cid = ctx.chat.id
    res = ctx.director_resolve or ctx.director_establish or {}
    fired, requeued, dropped = resolve_authored_events(
        cid, ctx.turn.idx, str(res.get("resolved_event") or ""))
    if requeued:
        ctx.add_warning(
            f"{requeued} authored future-event(s) not enacted this beat; "
            "re-queued to next turn rather than dropped")
    if dropped:
        ctx.add_warning(
            f"{dropped} authored future-event(s) went unresolved past the "
            "re-queue limit and were marked stale")
    interp = ctx.director_interpret or {}
    minted = mint_authored_events(
        cid, ctx.turn.idx, (interp.get("flow") or {}).get("scheduled_assertions"))
    return {"fired": fired, "requeued": requeued, "dropped": dropped,
            "minted": minted}


def commit_offscreen_epoch(ctx, prepared_scene, transit_result):
    """Advance the shared off-screen epoch inside the turn transaction.

    Kept as a named commit domain instead of an inline import so the generated
    code map, failure warning, and pipeline trace all expose this persistence
    boundary. The implementation is pure/deterministic plus world-KV writes;
    model-priced work remains at the post-commit tail.
    """
    from offscreen import advance_epoch

    return advance_epoch(ctx, prepared_scene, transit_result)


def commit_offscreen_plans(ctx, prepared_scene):
    """Apply Director-adjudicated, character-grounded reactive plan ops."""
    from offscreen import apply_plan_ops

    clock = (prepared_scene.get("clock")
             or wget(ctx.chat.id, "simulation_clock", {}) or {})
    return apply_plan_ops(ctx, prepared_scene.get("scene") or {}, clock)


def commit_crowds(ctx, prepared_scene):
    """Apply Director crowd ops, then move every crowd that has somewhere to be.

    Deliberately NOT gated behind a living-world setting. A crowd is on-screen
    atmosphere in the room the player is standing in, not off-screen
    simulation, and it only ever exists because the Director declared it this
    beat -- the off switch is a model that writes no ops. Gating it would make
    the feature invisible in most chats, which is the failure mode this
    project keeps rediscovering: a mechanism assumed live that has never run.

    Two steps in one domain because they must not be separable, and the ORDER
    is the whole mechanic: last beat's flow is spent FIRST, then this beat's
    declaration is applied.

    The other order is the obvious one and it is dead. Applying ops and then
    advancing spends a heading inside the commit that declared it, so the crowd
    arrives before anyone sees it leave -- and `crowds_for_room` therefore
    reports `drift: None` on every turn that will ever be perceived. The whole
    terrain layer is unreachable: the Director is told to resolve a press it
    can never be shown. Caught by `tools/crowd_drive.py` on its first run, and
    it is the same shape as every other zero this project has dug up -- a
    mechanism that reads correct at every line and cannot fire.

    So a heading lives for exactly one beat of perception. The Director
    declares that the market is flowing toward the gate; the player's next
    breath is spent inside a crowd that is going somewhere, with a drift offer
    the Director can honour; and the beat after that, it has gone. `move` stays
    available for a relocation declared outright.
    """
    import crowds as crowds_model
    from spatial import passable_neighbors

    cid = ctx.chat.id
    scene = prepared_scene.get("scene") or {}
    resolved = ctx.director_resolve or ctx.director_establish or {}
    # Establish authors the opening scene and has no `state_diff`, so its
    # crowd ops sit at the top level. Reading only one of the two shapes made
    # an opening beat unable to put anybody in the square.
    raw_ops = ((resolved.get("state_diff") or {}).get("crowd_ops")
               or resolved.get("crowd_ops") or [])
    if not isinstance(raw_ops, list):
        raw_ops = []
    ops = [op.dict() if hasattr(op, "dict") else op for op in raw_ops]

    # The two facts emergence is adjudicated against, both deterministic. Who
    # the story already knows -- a crowd produces strangers, never cast -- and
    # who has spoken this beat, because a line attributed to someone is the
    # durable record that makes their emergence one-way.
    roster = _registered_name_roster(ctx.chat, ctx.cast)
    spoken = {str(line.get("speaker") or "")
              for line in (resolved.get("dialogue_log") or [])
              if isinstance(line, dict)}

    before = wget(cid, crowds_model.CROWDS_WORLD_KEY, []) or []
    rooms = list((scene.get("rooms") or {}).keys())
    turn = int(getattr(ctx.turn, "id", 0) or 0)

    # Counted before `advance_crowds`, which spends every heading it honours
    # and leaves nothing to count afterwards. This is the denominator for "a
    # crowd moved on the graph": a crowd standing still with nowhere to be was
    # never a chance to move, and measuring moves against every standing crowd
    # made a working mechanism read as stuck -- 0/78 over a fifty-one beat
    # story in which no heading was ever declared. Measuring against every row
    # in the table rather than against the opportunities a mechanism had is
    # the exact mistake that has cost this project the most.
    headed = sum(1 for crowd in before
                 if isinstance(crowd, dict) and crowd.get("heading")
                 and str(crowd.get("heading")) != str(crowd.get("room_uid")))

    standing, moves = crowds_model.advance_crowds(
        before, passable_neighbors(scene))
    standing, rejected = crowds_model.apply_ops(
        standing, ops, chat_id=cid, turn=turn, known_rooms=rooms,
        roster=roster, spoken=spoken)

    for reason in rejected:
        ctx.add_warning("crowd op rejected: %s" % reason)
    if standing != before:
        wset(cid, crowds_model.CROWDS_WORLD_KEY, standing)
    return {"offered": len(ops), "standing": len(standing),
            "headed": headed,
            "moved": len(moves), "rejected": len(rejected)}


def commit_all(ctx, nonce):
    """Commit one turn exactly once and atomically.

    Expensive or failure-prone preparation (LLM validation and embeddings)
    happens before SQLite's write transaction.  Every durable mutation then
    runs under one outer transaction; a failure in any domain rolls back all
    earlier domains from the same turn.
    """
    lock = _commit_lock(ctx.turn.id)
    with lock:
        return _commit_all_locked(ctx, nonce)


def _prepare_turn_commit(ctx):
    """Prepare slow commit inputs without holding SQLite's write lock."""
    try:
        scene = prepare_scene_commit(ctx)
        mapping = prepare_mapping_commit(ctx)
        memories = prepare_memory_commit(ctx, scene=scene["scene"])
        claims = prepare_background_claims(ctx)
        return {"scene": scene, "mapping": mapping, "memories": memories,
                "claims": claims}
    except Exception as exc:
        ctx.add_warning(f"commit preparation failed: {exc}")
        raise RuntimeError(f"Commit preparation failed: {exc}") from exc


def _commit_domain(ctx, results, name, operation):
    """Run one durable domain and preserve its name on rollback errors."""
    try:
        results[name] = operation()
    except Exception as exc:
        ctx.add_warning(f"commit_{name} failed; turn rolled back: {exc}")
        raise RuntimeError(f"{name}: {exc}") from exc


def _commit_all_locked(ctx, nonce):
    import extension_runtime as _extensions_module

    prepared = _prepare_turn_commit(ctx)
    results = {}

    try:
        with transaction():
            # Transit sweep first: it mutates the prepared scene (timed
            # arrivals, engine notices) that the scene domain then persists.
            _commit_domain(
                ctx, results, "transit",
                lambda: commit_transit_sweep(
                    ctx, nonce, prepared=prepared["scene"]),
            )
            _commit_domain(
                ctx, results, "world_events",
                lambda: commit_world_event_spine(
                    ctx, results.get("transit") or {}),
            )
            _commit_domain(
                ctx, results, "scene",
                lambda: commit_scene(ctx, nonce, prepared=prepared["scene"]),
            )
            _commit_domain(
                ctx, results, "entities",
                lambda: commit_world_entities(
                    ctx, nonce, prepared=prepared["scene"]),
            )
            _commit_domain(
                ctx, results, "cast",
                lambda: commit_cast_changes(ctx, nonce),
            )
            # These checks intentionally run after scene/entity/cast writes so
            # they inspect this turn's projected world, while still remaining
            # inside the same rollback boundary.
            _commit_domain(
                ctx, results, "paradox",
                lambda: check_and_apply_paradox(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "spatial",
                lambda: detect_and_reconcile_spatial(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "mapping",
                lambda: commit_mapping(ctx, nonce, prepared=prepared["mapping"]),
            )
            _commit_domain(
                ctx, results, "offscreen_plans",
                lambda: commit_offscreen_plans(ctx, prepared["scene"]),
            )
            # After the scene domain, because a crowd op naming a room the
            # same beat created must find that room in the projected world
            # rather than the one the turn started in.
            _commit_domain(
                ctx, results, "crowds",
                lambda: commit_crowds(ctx, prepared["scene"]),
            )
            # A first-class frame-scoped epoch, after mapping so a freshly
            # validated standing intention can participate, but independent of
            # mapping's skip path. `director_establish` is an opening-stage
            # result, not a scene-boundary event; leaving ticks in
            # commit_mapping made the documented mechanism fire once per chat.
            _commit_domain(
                ctx, results, "offscreen_epoch",
                lambda: commit_offscreen_epoch(
                    ctx, prepared["scene"], results.get("transit") or {}),
            )
            _commit_domain(
                ctx, results, "memories",
                lambda: commit_memories(
                    ctx, nonce, prepared=prepared["memories"], consolidate=False,
                ),
            )
            _commit_domain(
                ctx, results, "information_carriers",
                lambda: commit_information_carriers(
                    ctx, prepared["scene"], results.get("world_events") or {}),
            )
            _commit_domain(
                ctx, results, "background_presences",
                lambda: track_background_presences(
                    ctx, nonce, prepared=prepared["claims"]),
            )
            _commit_domain(
                ctx, results, "narration_person",
                lambda: commit_narration_person(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "obligations",
                lambda: commit_obligations(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "world_pressure",
                lambda: commit_world_pressure(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "authored_events",
                lambda: commit_authored_events(ctx, nonce),
            )
            _commit_domain(
                ctx, results, "pending",
                lambda: wset(ctx.chat.id, "pending", []),
            )
            # Extension commit domains run LAST inside the transaction, after
            # every engine domain has landed: an extension computing from the
            # turn's own durable writes must be able to read them. Their
            # failures are contained by the registration's own `on_error` --
            # "warn" (the default) keeps the promise that a broken extension
            # never costs a turn, "fail" is an extension saying its state being
            # wrong is worse than the beat being lost.
            _extensions_module.run_commit_domains(ctx, results)
    except Exception as exc:
        raise RuntimeError(
            f"Commit failed and was rolled back: {exc}"
        ) from exc

    # Autobiographical summaries are derived, reconstructible caches and may
    # invoke an LLM. They therefore run OUT OF BAND, beside the offscreen
    # ticks below: measured live (chat 71 turn 10), the first consolidation
    # was 29.5s of a 45.8s commit stage -- a background summarisation job on
    # the `utility` role, inside the player's wait. A failure is a warning,
    # never a rollback, and never silence.
    try:
        job = schedule_memory_consolidation(ctx)
        results["memory_consolidation"] = job.as_dict() if job else None
    except Exception as exc:
        ctx.add_warning(f"memory consolidation scheduling failed: {exc}")
        results["memory_consolidation"] = {"error": str(exc)}

    # Autonomous background->cast promotion likewise runs after the primary
    # transaction: it mints a sheet with an LLM call and is additive and
    # forward-only (the new character becomes step-eligible next turn), so a
    # failure is a warning, never a turn rollback.
    try:
        results["promotions"] = auto_promote_background_characters(ctx)
    except Exception as exc:
        ctx.add_warning(f"auto-promotion failed: {exc}")
        results["promotions"] = {"promoted": [], "error": str(exc)}

    # Out-of-band offscreen ticks start HERE, after the turn's facts are
    # durable, and run in parallel with whatever the player does next. A
    # turn starting never cancels one: cancelling on turn-start would make
    # the world's progress depend on player idleness, which inverts the
    # feature (amendments section 4). Arrival is safe because every tick
    # write is provisional (section 5). Failure is a warning, never a
    # rollback -- and never silence.
    try:
        import offscreen as _offscreen

        job = _offscreen.schedule_profile_ticks(
            ctx, results.get("offscreen_epoch") or {})
        results["offscreen_ticks"] = job.as_dict() if job else None
    except Exception as exc:
        ctx.add_warning(f"offscreen tick scheduling failed: {exc}")
        results["offscreen_ticks"] = {"error": str(exc)}

    # The paid `character_agent` rung rides the same epoch, on the same
    # terms: out of band, epoch/base-turn-guarded at landing, never
    # cancelled by a turn starting, and a failure is a warning.
    try:
        import offscreen as _offscreen

        job = _offscreen.schedule_agent_ticks(
            ctx, results.get("offscreen_epoch") or {})
        results["offscreen_agent"] = job.as_dict() if job else None
    except Exception as exc:
        ctx.add_warning(f"offscreen agent scheduling failed: {exc}")
        results["offscreen_agent"] = {"error": str(exc)}

    # The rumor ledger's ceiling: authored wording for freshly posted
    # notices, on the same terms as every other out-of-band spend -- after
    # the turn's facts are durable, gated on the ceiling setting, and landed
    # only if the bill still stands when the job returns. The floor never
    # waits on this and never needs it.
    try:
        import artifacts as _artifacts

        job = _artifacts.schedule_artifact_wording(ctx)
        results["artifact_wording"] = job.as_dict() if job else None
    except Exception as exc:
        ctx.add_warning(f"artifact wording scheduling failed: {exc}")
        results["artifact_wording"] = {"error": str(exc)}

    # Installed extensions observe the turn HERE, on the same terms as every
    # other hook in this tail: after the turn's facts are durable, so an
    # extension's own write can never be the thing left standing when a domain
    # failure rolls the turn back. It is also the only place an extension may
    # write per-turn state at all (extension_runtime/api.py's commit scope).
    # A failure is a warning, never a rollback -- and never silence.
    try:
        import extension_runtime as _extensions

        results["extensions"] = _extensions.dispatch_turn_committed(ctx)
        # Attribution for the routing seam. An extension that rewrote what a
        # mind was given names itself HERE, on the durable turn, so a character
        # who knows something they should not is one read from their author
        # rather than looking like an engine defect.
        _routing = _extensions.routing_notes(ctx)
        if _routing:
            results["extensions"]["routing"] = _routing
    except Exception as exc:
        ctx.add_warning(f"extension turn hooks failed: {exc}")
        results["extensions"] = {"error": str(exc)}

    # Approach A's floor is computed on the Director payload path, which no
    # commit domain ever sees -- so without this echo the one mechanism whose
    # whole failure history is "nobody could tell it never fired" would stay
    # unmeasurable by tools/fire_rates.py forever. Present only on beats
    # whose resolve stage actually ran with a declared movement (a rerun
    # replayed from storage carries no stash), so absence reads as
    # `no chances`, never as 0%.
    _residue_report = ctx.get("_destination_residue_report")
    if isinstance(_residue_report, dict):
        results["routine_residue"] = dict(_residue_report)

    return {
        "summary": (
            f"Committed turn {ctx.turn.idx}: "
            f"{len(results.get('memories', {}).get('committed', []))} "
            "memory writes"
        ),
        "errors": [],
        "results": results,
    }

# ---- Fallback helpers ----

def _lore_for(ctx):
    return (ctx.mapping_stage or ctx.mapping_quick or {}).get("relevant_lore") or []

def _normalized_fact(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()

def _fact_is_covered(fact, existing_lore):
    normalized = _normalized_fact(fact)
    if not normalized:
        return True
    fact_tokens = set(normalized.split())
    for entry in existing_lore or []:
        candidate = _normalized_fact(entry.get("content") or "")
        if not candidate:
            continue
        if normalized in candidate or candidate in normalized:
            return True
        candidate_tokens = set(candidate.split())
        union = fact_tokens | candidate_tokens
        if union:
            similarity = len(fact_tokens & candidate_tokens) / len(union)
            if similarity >= 0.72:
                return True
    return False

def _generate_fallback_ops(ok_facts, staged, world_facts, existing_lore=None):
    existing_lore = existing_lore or []
    ops = []
    for fact in ok_facts:
        text = str(fact.get("fact") or "")
        if text and not _fact_is_covered(text, existing_lore):
            ops.append({"op": "create", "keys": "", "content": text, "category": "event", "book_id": None})
    for entry in staged:
        content = str(entry.get("content") or "")
        if not content or _fact_is_covered(content, existing_lore):
            continue
        ops.append({
            "op": "create", "keys": entry.get("keys", ""), "content": content,
            "category": entry.get("category", "other"), "title": entry.get("title"),
            "knowledge_tag": entry.get("knowledge_tag"),
            "knowledge_range": entry.get("knowledge_range"),
            "knowledge_locations": entry.get("knowledge_locations"),
            "book_id": entry.get("book_id"),
        })
    for world_fact in world_facts:
        if isinstance(world_fact, dict):
            text = str(world_fact.get("fact") or "")
            source_kind = (world_fact.get("source") or {}).get("kind")
        else:
            text = str(world_fact)
            source_kind = None
        if source_kind == "lore":
            continue
        if text and not _fact_is_covered(text, existing_lore):
            ops.append({"op": "create", "keys": "", "content": text, "category": "other", "book_id": None})
    return [o for o in ops if o.get("content")]
