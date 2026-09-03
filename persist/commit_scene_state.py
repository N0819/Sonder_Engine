"""The prepared post-turn scene: book anchoring, ground/weather advance,
the pure pre-lock build, and the scene commit domain.

Extracted verbatim from commit.py, which re-exports every name here. The
deferred function-body imports (scene, weather, gaps, living_world) are
the existing cycle-breakers and stay deferred.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import copy
from core.db import q, qi, transaction, wget, wset
from core.pipeline_context import note_step_decision
from mind.memory import add_lorebook_link
from story.character_schema import character_name_from_text, persona_name
from story.provenance_text import strip_engine_provenance
from world.weather import advance_weather, normalize_weather
from world.spatial import (contradictory_sight_edges, guessed_room_sizes,
                           merge_scene_with_diff)
from world.spatial_frames import (_cast_changes_leaving, infer_companion_carry,
                            infer_vehicle_zones,
                            infer_came_from, infer_focus, infer_facing,
                            infer_threshold_crossings)
from persist.commit_common import _player_name_or_none
from persist.commit_destruction import (_apply_destruction,
                                _finalize_destruction_news,
                                _prepare_destruction)
from persist.commit_room_registry import (_apply_room_registry,
                                  _prepare_room_registry,
                                  _refresh_relocated_location,
                                  dedup_minted_rooms, prune_dangling_exits)
from persist.commit_attire import apply_attire_diff
from world.mechanics import (UNCLAIMED_BEAT_SECONDS, beat_end_elapsed,
                             clock_elapsed, normalize_time_of_day)

# ---- Scene commit with entity-aware merge ----

def _establish_time_of_day(est):
    """The opening's standing time of day, from the two places the establish
    stage puts it. ONE value, because the scene's label and the clock's label
    are the same statement and must not be able to disagree.

    THE CLOCK'S OWN LABEL WINS. Both keys are filled in 80 of 80 corpus
    openings, and where they disagree it is `time` that drifts off the
    question: it is the scene's label, so a model writes the SITUATION into
    it -- "Immediate aftermath of a containment breach", "Intake interview
    commencement", "now" -- while `simulation_clock.display` beside it holds
    "08:42:15 AM" and "09:42". 17 of the 80 split that way, every one of them
    with the readable answer on the clock. `display` is the field whose name
    says it is written to be READ AS A TIME (`llm/schemas.py`'s
    `GreetingExtraction.time` documents it as exactly that, and the greeting
    path already seeds it at launch), so it leads and `time` follows.

    Reading it here is also what retires the orphan: the schema has solicited
    that whole dict since long before this split, every opening filled it,
    and NOTHING anywhere read it.
    """
    est = est or {}
    clock = est.get("simulation_clock")
    if isinstance(clock, dict):
        label = normalize_time_of_day(clock.get("display"))
        if label:
            return label
    return normalize_time_of_day(est.get("time"))


def _advance_day_cycle(ctx, sc, clock, prev_clock, *, declared, opening):
    """Derive the hour and the phase of the day from the clock, and let the
    standing label follow them. Returns the clock to store (possibly the
    one it was handed, untouched).

    THE LABEL IS THE DIRECTOR'S UNTIL THE CLOCK LEAVES THE PHASE IT NAMES.
    An opening's "before dawn" stands verbatim while the hour is still in
    pre-dawn; when the clock crosses into dawn the label becomes "dawn",
    and from then on it is the phase table's word until a beat declares
    another. A declared label that names a phase the derived hour is NOT in
    re-anchors the clock to it (a Director saying "the next morning" has
    moved the day, in words rather than in seconds) and says so in a
    warning; one that names the phase the clock is already in changes
    nothing; one this engine cannot read at all -- a stardate carrying no
    clock reading -- stands untouched, because the cycle cannot say it is
    wrong. See `world/day_cycle.py`.

    FAIL OPEN, TWICE. A story whose opening named no readable time has no
    anchor, gets no phase, and keeps every reader's behaviour as it was; and
    the day length is the author's dial with a Terran default, so a story
    that never touched it runs a 24-hour day. A story written before the
    cycle existed anchors itself on its own standing label the first time a
    beat commits under it, at that beat's elapsed -- the label was standing
    at that hour by construction, so the bootstrap is exact.
    """
    from story.scene import style_guide
    from world.day_cycle import (
        anchor_from_hour, clock_anchor, hour_of_day, label_hour, label_phase,
        phase_of_hour)

    cid = ctx.chat.id
    style = style_guide(cid)
    record = clock if clock is not None else (prev_clock or {})
    elapsed = clock_elapsed(record)
    stored_anchor = record.get("anchor_hour") if isinstance(record, dict) \
        else None
    anchor, length = clock_anchor(record, style)
    standing = normalize_time_of_day(sc.get("time_of_day"))
    if opening:
        # The opening anchors the day: its label if readable, else the
        # author's `opening_hour`. `clock_anchor` already tried the
        # greeting-seeded display label; the opening's own word leads.
        hour = label_hour(opening, length)
        if hour is not None:
            anchor = anchor_from_hour(hour, elapsed, length)
    elif stored_anchor is None and anchor is None and standing:
        # A story that predates the cycle: its standing label was standing
        # at this elapsed, so it anchors exactly.
        hour = label_hour(standing, length)
        if hour is not None:
            anchor = anchor_from_hour(hour, elapsed, length)
    elif declared and anchor is not None:
        hour = label_hour(declared, length)
        if hour is not None:
            derived = phase_of_hour(hour_of_day(elapsed, anchor, length), length)
            named = label_phase(declared, length)
            if named != derived:
                ctx.add_warning(
                    "time of day re-anchored: the beat declared %r while the "
                    "clock stood in %s (hour %.1f of a %g-hour day); the "
                    "clock now reads %r" % (
                        declared, derived,
                        hour_of_day(elapsed, anchor, length), length,
                        declared))
                anchor = anchor_from_hour(hour, elapsed, length)
    if anchor is None:
        return clock
    hour = hour_of_day(elapsed, anchor, length)
    phase = phase_of_hour(hour, length)
    sc["day_phase"] = phase
    named = label_phase(standing, length) if standing else None
    if not standing or (named is not None and named != phase):
        sc["time_of_day"] = phase
    if clock is None:
        clock = copy.deepcopy(prev_clock or {})
    clock["anchor_hour"] = round(anchor, 4)
    clock["day_length_hours"] = length
    clock["hour_of_day"] = round(hour, 2)
    clock["phase"] = phase
    clock["display"] = sc.get("time_of_day") or ""
    return clock


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


#: Overlay-entry fields that can IDENTIFY the overlay: the handle a beat
#: addresses it by, and the reader-facing fact it states. `description` and
#: `desc` are one field under two stored spellings.
#:
#: `subject` is deliberately ABSENT. On the spelling chat 78 wrote, the map is
#: keyed by overlay name and `subject` names the BODY the overlay is about --
#: which is how `commit_attire._overlay_texts_by_subject` reads it. Three
#: distinct overlays there share one subject, so folding on it would delete
#: two authored appearance facts, the precise failure this rule exists to
#: prevent. `id` is absent for the same reason: on the one corpus entry
#: carrying it, it names the place the overlay is about.
_OVERLAY_HANDLE_FIELDS = ("name", "description", "desc")

#: Fields that are NOT a handle, so every other string value is one.
#:
#: Inverted 2026-09-01. The include-list above tried to anticipate the field
#: name a model would reach for, and live (chat 111 turn 54) the Director ended
#: an overlay correctly -- `{"text": "tears escape eyes", "active": false}` --
#: and the ending did nothing, because `text` was not on it. A record with no
#: handle matches nothing, so the removal was silent and the mark stood. That
#: is the enumeration failure CLAUDE.md names: a list that guesses at how
#: English will phrase something is always one spelling short.
#:
#: Stating the complement makes the closed set one the ENGINE owns. `subject`
#: names the BODY the overlay is about, not the overlay -- three distinct
#: overlays in chat 78 share one subject, so folding on it would delete two
#: authored appearance facts. `id`, on the one corpus entry carrying it, names
#: the place the overlay is about. The rest are the ending's own control
#: fields, which say whether the mark is there and never which mark it is.
_OVERLAY_NON_HANDLE_FIELDS = frozenset(
    ("subject", "id", "active", "present", "ended", "removed"))

#: How many overlay entries one body's ledger keeps. Ageing them is a
#: separate, unsolved problem (docs/UNBUILT.md 1.10): this cap is the only
#: thing that bounds an overlay's life, and nothing here expires one.
#:
#: Applied as `[-CAP:]`, so what it drops is the OLDEST mark -- and since
#: nothing else expires one, that eviction is the engine deciding a standing
#: appearance fact is over because a seventh arrived, not because any beat
#: said so. The NUMBER is the owner's call; every eviction is written to the
#: turn's decision log (`evicted_by_cap`), so a mark that stops being
#: rendered is distinguishable from one the Director ended with
#: `active: false` above.
_MAX_OVERLAY_ENTRIES = 6


def _overlay_handles(item) -> set:
    """The casefolded strings by which one overlay entry can be recognised.

    A record is known by its name and by the fact it states; a bare line of
    prose is known by itself. An entry carrying neither -- some future or
    malformed shape -- has NO handle and is therefore never matched against
    anything, which is what keeps this rule incapable of deleting a shape it
    does not understand.
    """
    if isinstance(item, dict):
        return {value for value in
                (str(item.get(field) or "").strip().casefold()
                 for field in _OVERLAY_HANDLE_FIELDS) if value}
    if isinstance(item, str):
        folded = item.strip().casefold()
        return {folded} if folded else set()
    return set()


def _overlay_label(item) -> str:
    """A short human handle for one overlay entry, for diagnostics only.

    Deliberately not `_overlay_handles`: that reads the three fields dedupe
    is willing to fold on, and an entry it cannot understand must stay
    unmatched there. A log line has the opposite duty -- an entry nobody
    understood is exactly the one a reader needs to see -- so this falls back
    to the raw repr rather than to nothing.
    """
    if isinstance(item, str):
        return item.strip()[:120]
    if isinstance(item, dict):
        parts = [str(item.get(field) or "").strip()
                 for field in ("name", "description", "desc", "text")]
        joined = " / ".join(part for part in parts if part)
        if joined:
            return joined[:120]
    return repr(item)[:120]


def _is_overlay_ending(item) -> bool:
    """Whether this entry says the mark is GONE rather than present.

    Overlays were the only body channel with no off-switch: attire changes,
    conditions and transformations close with `active: false`, vitals move
    both ways, and an overlay could only leave by being pushed out of the
    six-entry window by newer ones. Live (chat 111), a body's momentary
    climax -- "violent shuddering", "tears escape eyes", written on turn 34 --
    was still on the ledger at turn 52, because only three further overlays
    were ever written and the cap never reached it.

    Only a record can carry an ending: a bare line is the fact itself, and a
    line of prose has nowhere to put "not". Anything else is present.
    """
    if not isinstance(item, dict):
        return False
    for field in ("active", "present"):
        if field in item:
            return item.get(field) is False
    return bool(item.get("ended") is True or item.get("removed") is True)


def _overlay_ending_handles(item) -> set:
    """What an ENDING names, read wider than `_overlay_handles` reads a record.

    The two uses differ in who is speaking and what a miss costs. Dedupe folds
    entries on its own initiative, so an entry it cannot understand must be
    untouchable -- that floor is why `_overlay_handles` reads only the fields
    it knows, and it stays. An ending is the Director SAYING which mark is
    gone, so reading it narrowly does not fail safe: it fails silent, and the
    mark the beat said was over goes on standing.

    Live, chat 111 turn 54: `{"text": "tears escape eyes", "active": false}`
    -- correct use of the off-switch, on the day it shipped, and `text` was
    not among ("name", "description", "desc"), so the ending named nothing and
    removed nothing. Guessing the field a model will reach for is the
    enumeration this codebase keeps losing to; here the complement is
    available, because the fields that identify something OTHER than this mark
    are ones the engine defines.
    """
    if isinstance(item, str):
        return _overlay_handles(item)
    if not isinstance(item, dict):
        return set()
    return {text for text in
            (str(value).strip().casefold()
             for field, value in item.items()
             if isinstance(value, str)
             and str(field).strip().casefold()
             not in _OVERLAY_NON_HANDLE_FIELDS)
            if text}


def _dedupe_overlay_entries(entries) -> list:
    """Collapse one body's overlay list to one entry per named thing.

    The rule: entries sharing a handle are the SAME overlay, and the later
    account of it replaces the earlier -- except that a bare line restating
    a standing record is silence, because the record is the richer account
    of the identical fact and losing it to a fragment of itself would be a
    downgrade rather than an update.

    Identity is handle-set INTERSECTION, not equality: two entries are the
    same overlay when they share ANY handle, which is what lets a bare line
    meet the record that carries it as its name. The rule is therefore wider
    than "one entry per named thing" -- two records whose name and
    description sets merely cross (a record named for what another one
    describes) fold together too. That shape does not occur in the corpus,
    and narrowing it would cost the bare-line-meets-record case this exists
    for, so it is stated here rather than guarded against.

    Measured 2026-08-25 over all 77 stored scene blobs: this prunes 11 of 91
    overlay entries, every one a verified restatement (chats 78, 86, 87, 88),
    and touches none of them without a handle -- the corpus holds zero
    handle-less entries, so nothing was at risk there and nothing was lost.
    Because it runs over the whole map on every commit, a ledger that is
    already dirty heals on its next beat with no migration.
    """
    out: list = []
    for item in (entries if isinstance(entries, list) else [entries]):
        handles = _overlay_handles(item)
        if not handles:
            out.append(item)
            continue
        clashes = [i for i, old in enumerate(out)
                   if _overlay_handles(old) & handles]
        if not isinstance(item, dict) \
                and any(isinstance(out[i], dict) for i in clashes):
            continue
        for i in reversed(clashes):
            out.pop(i)
        out.append(item)
    return out


def _merge_overlays(sc, incoming) -> None:
    """Fold this beat's overlays into the scene's, then heal every body.

    An overlay is a mutable temporary fact about how a body looks, not an
    append-only event, and the channel accepts two representations of one
    fact: a bare line and a `{name, description}` record. Deduping each
    representation only against its own kind meant they never met -- chat 88
    turn 67 stood one overlay three times, as its bare name, as its bare
    description, and as the record carrying both, and every observer's
    appearance view rendered all three.

    The heal runs over the WHOLE map, not only the bodies this beat named,
    which is what lets an already-dirty ledger recover with no migration --
    and means an untouched body's entries are normalized in shape on every
    commit too (a lone bare line becomes a one-element list). That rewrite
    adds, reorders and rewords nothing; it only settles the container.

    An `overlays` key present but NULL is reset rather than read.
    `setdefault` hands back the stored None, so the heal below would raise
    inside the sole persistence boundary and roll the entire turn back --
    and it would do so on the EMPTY diff, the common case, because the heal
    no longer runs under the incoming loop. No in-tree writer produces that
    shape and none of the 77 stored blobs carries it (scanned 2026-08-25);
    the exposure is an archive or checkpoint written elsewhere.
    """
    overlays = sc.get("overlays")
    if not isinstance(overlays, dict):
        if overlays is not None:
            return
        overlays = sc["overlays"] = {}
    for key, value in (incoming if isinstance(incoming, dict) else {}).items():
        arriving = list(value if isinstance(value, list) else [value])
        # An ENDING is a statement that the mark is gone, not a new entry.
        # Spelled `active: false`, the same way a condition or a
        # transformation is ended, so a specialist learns one rule and not
        # two. Identity is the handle set the dedupe already uses, so an
        # ending reaches the standing entry whether it was written as a bare
        # line or as a record -- and reaches it without the Director having
        # to know an id it was never shown.
        endings = [item for item in arriving if _is_overlay_ending(item)]
        arriving = [item for item in arriving if not _is_overlay_ending(item)]
        standing = overlays.get(key)
        merged = (standing if isinstance(standing, list) else
                  ([] if standing is None else [standing])) + arriving
        # Endings apply LAST, so a beat that both restates and ends a mark
        # ends it: the ending is the beat's final word about that handle.
        for ending in endings:
            handles = _overlay_ending_handles(ending)
            if not handles:
                continue
            merged = [item for item in merged
                      if not (_overlay_handles(item) & handles)]
        overlays[key] = merged
    for key in list(overlays):
        deduped = _dedupe_overlay_entries(overlays[key])
        # Dropping the head of this list is not deduplication and not an
        # ending: it is the oldest mark on a body ceasing to exist because a
        # newer one arrived. Recorded per entry so a reader of the decision
        # log can tell it from the `active: false` path above, which is the
        # only other way an overlay leaves. See _MAX_OVERLAY_ENTRIES.
        for item in deduped[:-_MAX_OVERLAY_ENTRIES]:
            note_step_decision(
                "overlay_ledger", "%s: %s" % (key, _overlay_label(item)),
                "evicted_by_cap",
                "body carried %d overlays against cap %d; this was the "
                "oldest. No ending was written for it."
                % (len(deduped), _MAX_OVERLAY_ENTRIES))
        overlays[key] = deduped[-_MAX_OVERLAY_ENTRIES:]


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
    if not (prev_scene.get("rooms") or {}):
        # THE OPENING MERGES ONTO THE SCENE THE READERS SAW. `get_scene`
        # seeds a scene with no rooms from the planted skeleton, so mapping
        # and the Director opened inside the town -- and this merge started
        # from the stored `{}` instead, so the committed opening had the
        # Director's four rooms and none of the plan's exits (Harrowmere,
        # 2026-09-02). Seeding the base here is what makes planned adjacency
        # authority from turn 0: a diff may add exits to a planned room and
        # `protect_planned_edges` below puts back any it dropped. A story
        # with no plan seeds nothing and is exactly as it was; a story whose
        # scene already has rooms never reaches this branch. Seeded BEFORE
        # `dedup_minted_rooms`, so a room the Director mints under the
        # plan's name is redirected onto the planned id rather than minted
        # beside it.
        try:
            from story.scene import seed_scene_from_plan
            seed_scene_from_plan(cid, prev_scene)
        except Exception as _seed_exc:  # a scene that cannot read a plan is a scene
            ctx.add_warning(
                f"planned skeleton could not seed the opening: {_seed_exc}")
    # Carried beside prev_scene for the off-screen epoch. Once the scene
    # domain writes the new clock, a later commit domain cannot recover which
    # coarse time boundary THIS beat crossed. Keep the exact pre-turn value in
    # the prepared bundle instead of opening a second clock authority.
    # EMPTY display, not "now". This default is the exact thing chats 95 and
    # 96 read on every call to every role for 20 and 15 beats: a chat with no
    # clock row got the word "now", which reads as an answer and is not one.
    # A story that has not said what time it is says nothing.
    prev_clock = copy.deepcopy(wget(
        cid, "simulation_clock", {"elapsed_seconds": 0.0, "display": ""}
    ) or {"elapsed_seconds": 0.0, "display": ""})
    # THE BEAT'S END CLOCK, COMPUTED ONCE, HERE, BEFORE ANYTHING READS IT.
    # Four things downstream in this one function need it and used to get it
    # from three different places: the clock block below wrote it, the
    # weather drift re-read whatever the clock block happened to leave, the
    # transit sweep reads `prepared["clock"]`, and now the scene merge
    # carries an occupant across a passage on it. Computing it up here is
    # what lets the merge see the same number the commit stores.
    #
    # `floor=` is the resolved-beat test: an establish turn has no beat to
    # charge, and `world.mechanics.beat_end_elapsed` owns what the charge is
    # and when it applies.
    _td_block = diff.get("time") if isinstance(diff.get("time"), dict) else None
    (_beat_end, _clock_displaced, _clock_refused,
     _clock_floored) = beat_end_elapsed(
        clock_elapsed(prev_clock), _td_block,
        floor=bool(ctx.director_resolve))
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
    from agents.common import (reconcile_cast_entity_names,
                               stamp_authored_interiors)

    for _scope in (prev_scene, diff):
        for _eid, _old, _new in reconcile_cast_entity_names(
                _scope, ctx.cast, player_name=_player_name_or_none(ctx)):
            ctx.add_warning(
                f"identity: scene entity {_eid!r} was named {_old!r}; the cast "
                f"sheet spells that character {_new!r}, so the ledgers are "
                f"keyed {_new!r} and {_old!r} is kept as an alias.")
        # ...and the same body's authored INSIDE, on the same two scopes and
        # for the same reason: the merge builds a body's interior from the
        # scene alone and cannot reach a sheet, so the card's topology has to
        # be standing on the entity before `merge_scene_with_diff` below reads
        # it. Idempotent, like the reconcile above it.
        stamp_authored_interiors(
            _scope, ctx.cast, player_name=_player_name_or_none(ctx))

    _contact_report = []
    _substance_report = []
    # What a passage did to the bodies crossing it, and what it could not do.
    # Director-facing rather than a warning: every note it carries names a
    # fact the world is missing, which only the Director can supply.
    _crossing_report = []
    # What the transfer ledger did to the pose prose, and which handovers it
    # could not write down for want of an entity record. Director-facing for
    # the same reason as `_crossing_report`: every note names a fact only the
    # Director can supply, or a correction it can only make if it knows the
    # correction happened.
    _inventory_report = []
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
    # WHO THE TOWN STANDS HERE, for the transfer ledger. A handover's
    # destination resolves against the scene, and a Charter body standing
    # in the room has no scene record until something mints one -- so the
    # letter the reeve took (Harrowmere t5) stayed on the player for
    # thirty-five beats with no notice. The registry is the ledger that
    # stands those bodies; read from its cache, passed through so the thing
    # lands on the holder and follows them on every later merge.
    _carriers = {}
    try:
        from world.charter_runtime import charter_carriers

        _carriers = charter_carriers(
            cid, set(prev_scene.get("rooms") or {})
            | set(diff.get("rooms") or {}),
            frame_id=getattr(getattr(ctx, "turn", None), "frame_id", None))
    except Exception as exc:  # the scene must commit without the town
        ctx.add_warning("charter carriers unavailable to the merge: %s" % exc)
    sc = merge_scene_with_diff(
        prev_scene, diff, contact_report=_contact_report,
        substance_report=_substance_report.append,
        sleeping=_sleeping,
        clock_seconds=_beat_end, crossing_report=_crossing_report,
        inventory_report=_inventory_report, carriers=_carriers)
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
    for _note in _crossing_report:
        ctx.tell_director(str(_note))
    for _note in _inventory_report:
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
        # The room's DESCRIPTION, with the engine's own bookkeeping split off.
        # A `layout` entry staged for a room canon never described may carry
        # the reason it was staged, and this value becomes both `desc` and
        # `notes` -- the text every observer's view is built from. The
        # provenance is filed on the lore row's `source_notes`
        # (persist/commit_mapping), not into the room. See
        # story/provenance_text for the measurement.
        _desc = strip_engine_provenance(
            next((entry["content"] for entry in staged
                  if entry.get("category") == "layout"
                  and entry.get("content")), ""))
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
        # A PLANNED ROOM IS THE TOWN'S TOPOLOGY. Map curation may retire a
        # room the story minted and abandoned; it may not retire one the
        # plan gave every other planned room a way through.
        try:
            from world.structure import planned_room_ids
            protected.update(planned_room_ids(cid))
        except Exception:  # diagnostics only; the plan's absence is ordinary
            pass
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

    _merge_overlays(sc, diff.get("overlays") or {})

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

    # Present on every committed scene, so that "the story has not said" is a
    # value and not a missing key -- `scene.time` used to be absent on some
    # rows, present-and-empty on others, and present-and-holding-a-duration on
    # most, which is three different silences.
    sc.setdefault("time_of_day", "")

    est = ctx.director_establish
    _opening_time_of_day = ""
    if est:
        sc["location"] = est.get("location", sc.get("location"))
        # THE OPENING IS WHERE A STORY'S TIME OF DAY COMES FROM, and one value
        # feeds both homes it has (the scene label and the clock's label), so
        # they cannot disagree.
        # The greeting path seeds the clock's label from the greeting's own
        # extraction BEFORE turn 0 runs (`story/greetings.py`), so an opening
        # that names no time inherits the one the greeting already read out
        # of its own passage rather than starting the story blank.
        _opening_time_of_day = (_establish_time_of_day(est)
                                or normalize_time_of_day(
                                    prev_clock.get("display")))
        if _opening_time_of_day:
            sc["time_of_day"] = _opening_time_of_day
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
    # A BEAT THAT SAID NOTHING STILL HAPPENED, so the clock is built for a
    # silent resolved beat too -- `_clock_floored` is that beat, and writing
    # nothing there is the frozen clock this landing closes (chat 89 turns
    # 58-62: five resolved beats, empty player input, `simulation_clock`
    # standing at 1098.0 for nine turns).
    if _td_block is not None or _clock_floored:
        td = _td_block or {}
        clock = copy.deepcopy(prev_clock)
        # `beat_end_elapsed` owns what a time block can say, what a
        # silent beat costs, and what the stored clock keeps; this block
        # owns only what the world does about them. Read from the
        # quadruple computed once at the top of this function, so the
        # merge that carried bodies across passages, the weather drift,
        # the transit sweep and this write cannot land on four different
        # numbers for one beat.
        claimed, displaced, refused = (
            _beat_end, _clock_displaced, _clock_refused)
        if displaced is not None:
            # Two spellings of one refusal -- a position the engine did not
            # adopt -- worded apart because they read apart in a debug log.
            # The first is the reset-to-zero class; the second is a block
            # doing its arithmetic in a frame the engine never held (chat 95
            # second pass beat 2: end 20565 anchored at start 20520 against
            # a clock at 20.0 -- adopted verbatim, four people talking moved
            # the clock five and a half hours).
            if displaced[0] < displaced[1]:
                ctx.add_warning(
                    "state_diff.time claimed a clock position that ran "
                    "backwards (%.0f < %.0f); advanced by its own duration "
                    "instead" % displaced)
            else:
                ctx.add_warning(
                    "state_diff.time claimed a clock position anchored "
                    "away from the engine clock (claimed %.0f against "
                    "%.0f); advanced by its own span instead" % displaced)
        elif refused:
            # A refusal that says nothing is indistinguishable from a
            # beat that asserted no time, which is how the class this
            # commit closes stayed invisible for months. `refused` is
            # non-empty only when the block NAMED a time and the reader
            # could not act on it -- `{"start_seconds": 1200}` with no
            # end and no duration, `{"end_seconds": "soon"}`, a
            # position spelled in a key the vocabulary has no meaning
            # for. Keyed on whether the reader acted rather than on
            # whether the number moved: a beat that legitimately
            # re-asserts the clock's current position must not be
            # accused of saying nothing, and a beat that was silently
            # dropped must be reported even when every key it used was
            # one the prompts teach.
            #
            # WHAT HAPPENED INSTEAD IS NOW PART OF THE SENTENCE. A refusal
            # used to end "the clock did not advance", which was true and
            # was half the defect: the beat was dropped AND the world
            # froze. The reader is charged the floor now, so the warning
            # names the number that moved rather than reporting a stop.
            _tail = ("the beat was charged the unclaimed-beat floor of %gs "
                     "instead" % UNCLAIMED_BEAT_SECONDS) if _clock_floored \
                else "the clock did not advance"
            ctx.add_warning(
                "state_diff.time carried no clock position this engine "
                "could read (%s); %s" % (", ".join(refused), _tail))
        clock["elapsed_seconds"] = claimed
        # THE BEAT'S PASSAGE PHRASE IS NOT WRITTEN ANYWHERE, and its absence
        # here is the whole repair. `display_advance` ("moments later") used
        # to land on BOTH `simulation_clock.display` and `scene.time` from
        # this spot -- a per-beat statement about how far the beat moved,
        # written over a standing statement about where the world stands.
        # Non-empty, it overwrote the time of day; PRESENT AND EMPTY, it
        # erased it, which is a beat that owns no phrase deleting a fact it
        # never owned. Measured on the author's 81-chat corpus 2026-08-25: 63
        # openings named a readable time of day, 6 live scenes still held
        # one. The phrase reaches no reader in the tree and is not relocated
        # -- it stays the beat's own words on this resolve's persisted
        # variant, which is where a record belongs.

    # A time block that is a bare STRING is a scene label and nothing else:
    # it makes no clock claim, so it never reaches the reader above. EMPTY IS
    # NOT A CLEAR: a standing world property is not deleted by a beat that
    # said nothing about it, which is the erasure branch above in its other
    # spelling.
    _declared_time_of_day = normalize_time_of_day(diff.get("time"))
    if _declared_time_of_day:
        sc["time_of_day"] = _declared_time_of_day

    # `simulation_clock.display` IS THE TIME OF DAY'S LABEL -- its one
    # documented purpose (`llm/schemas.py`'s `GreetingExtraction.time`, which
    # seeds it at launch), and until now its only per-beat writer was the
    # passage-phrase branch above, so after beat 0 it could hold a duration
    # phrase or the `wget` default and nothing else. Chats 95/96 read "now"
    # on every call to every role for 20 and 15 beats: nothing per-beat ever
    # fired, and the opening's own clock was never committed at all.
    _time_of_day_label = _declared_time_of_day or _opening_time_of_day
    if _time_of_day_label:
        if clock is None:
            clock = copy.deepcopy(prev_clock)
        clock["display"] = _time_of_day_label
    elif clock is not None:
        # ONE STATEMENT, TWO HOMES, AND THEY MAY NOT DRIFT. The two used to
        # be able to disagree by construction -- an empty passage phrase
        # cleared the scene's label and deliberately left the clock's
        # standing -- and five corpus chats hold `scene.time` empty beside a
        # `display` of "moments later". A beat that writes a clock at all
        # restates the scene's own answer on it.
        clock["display"] = sc.get("time_of_day") or ""

    # THE DAY MOVES WITH THE CLOCK. Everything above keeps the label the
    # Director last declared; this is where the clock says what phase of the
    # day that label now stands in, and moves it on when the hours have.
    clock = _advance_day_cycle(
        ctx, sc, clock, prev_clock,
        declared=_declared_time_of_day, opening=_opening_time_of_day)

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
            materialize_planned_fringe, prepare_frontier_expansion,
            protect_planned_edges, settle_developed_stubs)
        # THE PLAN'S EXITS ARE PROTECTED. A developed room may add ways
        # through; the way the plan gave it comes back if the development
        # dropped it, because every other planned room counts on it.
        for _room, _to in protect_planned_edges(cid, sc):
            ctx.warnings.append(
                f"planned exit restored: {_room} -> {_to} (a developed room "
                "keeps every exit the plan gave it)")
        # And a stub that now has a description is a room: the flag and the
        # seed come off the live record, which the registry still keeps.
        settle_developed_stubs(sc)
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
