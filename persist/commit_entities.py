"""The world_entities projection of the scene commit, the awareness gate,
and disguise supersession.

Extracted verbatim from commit.py, which re-exports every name here.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import json
from core.db import q, transaction, wget
from story.character_schema import new_uid
from story.scene import get_scene, SINGULAR_BODY_CONDITIONS
from world.spatial import _merge_entity
from persist.commit_common import _canonical_anchor, _entity_alias_map

# ---- World entity commit ----

def _is_gated_awareness(cond):
    """Is this an awareness condition at a level that removes a mind from play?

    `dazed` is deliberately not gated -- a dazed mind is present but degraded --
    so it is not caught here either. See scene.NON_AWAKE_GATED. The family is
    `awareness_cond_level`'s: a kind spelled as the level word itself
    (`unconscious`, `asleep`) gates exactly as the canonical kind does,
    since the perception and planning readers now read it.
    """
    from story.scene import NON_AWAKE_GATED, awareness_cond_level
    level = awareness_cond_level(cond)
    if level is None:
        return False
    if not cond.get("active", True):
        return False
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

        # WHEN THIS CONDITION WAS LAST ASSERTED, on both clocks the engine
        # keeps. Nothing recorded it, which is why "has anybody mentioned
        # this in the last thirty turns" was an unanswerable question about
        # the 360 active, never-expiring rows in the author's corpus
        # (engine.db 2026-08-25, chat 88 the instance: ten rows, all active,
        # not one with an `expires_at`). The Director's `active_conditions`
        # view reads these stamps to show how long a row has stood
        # unmentioned. Pure functions of (clock, turn), so a rerolled turn
        # reproduces them byte-for-byte.
        _asserted_at = float(
            ((prepared or {}).get("clock")
             or wget(cid, "simulation_clock", {}) or {}
             ).get("elapsed_seconds") or 0.0)
        try:
            _asserted_turn = int(ctx.turn.idx)
        except (TypeError, ValueError, AttributeError):
            _asserted_turn = 0

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
                # A COPY, never the diff dict itself: `cond` is the stage
                # variant's stored record of what the model said, not a
                # scratchpad for the commit.
                payload = json.dumps(
                    {**cond, "last_asserted_at_seconds": _asserted_at,
                     "last_asserted_turn_idx": _asserted_turn},
                    ensure_ascii=False)
                if existing:
                    # THE SAME NOTHING-EVER-ENDS CLASS, on the UPDATE branch.
                    # The INSERT below has always read `expires_at_seconds`
                    # and `next_tick_seconds`; this named only subject_id,
                    # kind, payload and active, so a Director granting a
                    # standing condition an end on RE-EMISSION had that end
                    # silently discarded and the row stayed immortal.
                    # COALESCE, not a plain assignment: a re-emission that
                    # authors no timing keeps the row's own -- the guard
                    # subtracts, and a re-assertion is not a retraction.
                    c.execute(
                        """UPDATE world_conditions SET subject_id=?,kind=?,payload=?,active=?,
                        expires_at=COALESCE(?,expires_at),
                        next_tick=COALESCE(?,next_tick)
                        WHERE condition_id=? AND chat_id=?""",
                        (cond.get("subject_id", ""), cond.get("kind", ""),
                         payload, int(cond.get("active", 1)),
                         cond.get("expires_at_seconds"),
                         cond.get("next_tick_seconds"), cid_val, cid),
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
