"""The prepared post-turn scene: book anchoring, ground/weather advance,
the pure pre-lock build, and the scene commit domain.

Extracted verbatim from commit.py, which re-exports every name here. The
deferred function-body imports (scene, weather, gaps, living_world) are
the existing cycle-breakers and stay deferred.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import copy
from core.db import q, qi, transaction, wget, wset
from mind.memory import add_lorebook_link
from story.character_schema import character_name_from_text, persona_name
from world.weather import advance_weather, normalize_weather
from world.spatial import (contradictory_sight_edges, guessed_room_sizes,
                           merge_scene_with_diff)
from world.spatial_frames import (_cast_changes_leaving, infer_companion_carry,
                            infer_vehicle_zones,
                            infer_came_from, infer_focus, infer_facing,
                            infer_threshold_crossings)
from persist.commit_common import _monotonic_elapsed, _player_name_or_none
from persist.commit_destruction import (_apply_destruction,
                                _finalize_destruction_news,
                                _prepare_destruction)
from persist.commit_room_registry import (_apply_room_registry,
                                  _prepare_room_registry,
                                  _refresh_relocated_location,
                                  dedup_minted_rooms, prune_dangling_exits)
from persist.commit_attire import apply_attire_diff

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
    departed = _cast_changes_leaving(diff.get("cast_changes"))
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


def _advance_ground(cid, sc):
    """What the sky has left on each room's floor, after this beat.

    Deterministic and idempotent, like the weather drift it follows: same
    scene, same result, so a reroll does not re-mud a yard. Written to its own
    scene key rather than into `overlays`, which the Director authors -- engine
    bookkeeping and authored world-state should not be able to overwrite each
    other. Both the acoustic and the visual cache keys read it, so a yard that
    has turned to mud sounds and looks like one.
    """
    from story.scene import weather_severity
    from world.weather import ground_after, room_exposure, weather_for_room

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

    # THE CAST SHEET DECIDES A CAST BODY'S CANONICAL SPELLING, and the merge
    # fold that makes every ledger agree is cast-free by design -- it folds
    # onto the scene ENTITY's own `name`. So the entity record is reconciled
    # against the cast on both sides of the merge, here, where the cast is in
    # scope: the standing scene (which heals a save written before this rule
    # and is why no migration is needed) and this beat's diff (so a body the
    # Director just minted under an honorific is spelled the sheet's way from
    # its first beat). Idempotent, and it must stay so -- a checkpoint restore
    # replays it. Argument: `docs/design/DESIGN_SUBJECT_SPELLING_AUTHORITY.md`.
    from agents.common import reconcile_cast_entity_names

    for _scope in (prev_scene, diff):
        for _eid, _old, _new in reconcile_cast_entity_names(
                _scope, ctx.cast, player_name=_player_name_or_none(ctx)):
            ctx.add_warning(
                f"identity: scene entity {_eid!r} was named {_old!r}; the cast "
                f"sheet spells that character {_new!r}, so the ledgers are "
                f"keyed {_new!r} and {_old!r} is kept as an alias.")

    _contact_report = []
    _substance_report = []
    # WHO IS ASLEEP, from the ledger that actually answers that question.
    # `merge_scene_with_diff` used to read it off `contained[...]["mode"]`,
    # which is a containment vocabulary (carried/held/pocket/enclosed) and has
    # never carried an awareness value -- so the sleep-recovery branch in
    # `world/survival.py` was unreachable and a character who slept eight hours
    # on a surface that affords no rest DRAINED stamina (UNBUILT §1.3: "nobody
    # has ever recovered stamina by sleeping"). Computed here rather than
    # inside the merge because awareness lives in `story/`, and `world/`
    # importing up into `story/` would deepen an existing package cycle.
    #
    # `asleep` ONLY, and the exclusions are a decision rather than an
    # oversight: `dazed` is awake; `sedated` and `unconscious` are states
    # something else PUT a body into, and letting them restore stamina would
    # make drugging or concussing someone a way to rest them -- an incentive
    # that would propagate into how the Director resolves violence. A body
    # under-recovering is fixed by the next beat; a perverse incentive is not.
    from story.scene import awareness_map

    _sleeping = {
        _subject for _subject, _level in (awareness_map(cid) or {}).items()
        if _level == "asleep"
    }
    sc = merge_scene_with_diff(
        prev_scene, diff, contact_report=_contact_report,
        substance_report=_substance_report.append,
        sleeping=_sleeping)
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
            # A named overlay is a mutable temporary fact (flush, soot,
            # swelling), not an append-only event. Replace its earlier value
            # in place so a changing description does not accumulate six
            # contradictory copies and re-earn the body's full appearance on
            # every beat. Bare prose overlays retain legacy exact-dedupe
            # behaviour because they carry no safe identity to replace by.
            if isinstance(it, dict) and str(it.get("name") or "").strip():
                handle = str(it["name"]).strip().casefold()
                cur = [old for old in cur
                       if not (isinstance(old, dict)
                               and str(old.get("name") or "").strip().casefold()
                               == handle)]
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
                from story.scene import persona_of
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
        # `severity` is the story's authored ceiling. Passed here and nowhere
        # else on purpose: the drift is the only thing that moves a sky the
        # story did not ask to move, so it is the only thing a ceiling on how
        # hard it may come down can honestly bind. A Director who declares a
        # downpour has said what the beat is, and is not capped.
        from story.scene import weather_severity
        sc["weather"] = advance_weather(
            sc.get("weather"), elapsed, seed="chat:%s" % cid,
            cold=normalize_weather(sc.get("weather")).get("temperature") == "freezing",
            severity=weather_severity(cid))

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

    # A planned neighbour becomes a real, prose-free scene stub before the
    # dangling-edge guard runs. The registry continues to own the rest of the
    # town; mapping resolves only the room the story actually reaches.
    _frontier_mutations = []
    try:
        from world.structure import (
            materialize_planned_fringe, prepare_frontier_expansion)
        sc, _frontier_mutations = prepare_frontier_expansion(cid, sc)
        sc, _planned_added = materialize_planned_fringe(cid, sc)
    except Exception as _planned_exc:  # diagnostics, never a story blocker
        ctx.warnings.append(
            f"planned-room fringe could not be materialized: {_planned_exc}")

    for _msg in prune_dangling_exits(sc):
        ctx.warnings.append(_msg)

    # G6: size stopped being flavour when perception started reading it.
    # `proximity_rel` needs it to say two people are `across` a room, and
    # S2a caps sight at `shapes` in a large room with no placement -- so a
    # room nobody sized is a perception grade the engine chose for itself.
    # It chooses silently, on 45% of live rooms. Say so on the beat the room
    # becomes shared -- once, not every beat the scene stays in it.
    # A one-way window declared from BOTH sides is a contradiction: the value
    # is declared in the direction it LOOKS, so two of them cancel and nothing
    # says which was meant. Sight subtracts in both directions
    # (`mutual_one_way_window` carries the argument), which costs the watching
    # side a view it should have had -- so the report is not decoration, it is
    # the only channel that produces the RIGHT answer instead of a guess. It
    # speaks to the developer and to the Director, whose next beat can name
    # the blind side and give both directions back.
    # `sight_contradictions_told` marks a chat that has already heard about
    # its standing pairs. Without it a scene contradictory since before this
    # check existed compares equal to its own previous beat every turn and is
    # never reported at all -- silently walled, with nothing saying why.
    _told = wget(cid, "sight_contradictions_told", False)
    _contradictions = contradictory_sight_edges(
        sc, prev_scene if _told else None)
    if _contradictions:
        _notices = wget(cid, "engine_notices", []) or []
        for _pair in _contradictions:
            _msg = (
                f"{_pair['names'][0]!r} and {_pair['names'][1]!r} each declare "
                "a one_way_window into the other. A one-way window is "
                "declared in the direction it LOOKS, so two of them "
                "contradict each other and nothing says which way was meant "
                "-- neither room can see the other until this is resolved. "
                "Redeclare the edge from the watching side only, with `wall` "
                "on the blind side.")
            ctx.warnings.append(_msg)
            _notices.append(_msg)
        wset(cid, "engine_notices", _notices)
    if not _told:
        wset(cid, "sight_contradictions_told", True)

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
        "frontier_mutations": _frontier_mutations,
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
        if prepared.get("frontier_mutations"):
            from world.structure import apply_frontier_mutations
            apply_frontier_mutations(
                ctx.chat.id, ctx.turn.id, prepared["frontier_mutations"])
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
        from world.gaps import LAST_SEEN_KEY, last_seen_update
        from story.scene import persona_of
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
