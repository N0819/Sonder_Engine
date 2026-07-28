"""Character decision agent."""

from __future__ import annotations

import json

from affect import CRISIS_STRAIN_MIN, RUPTURE_FORCE_AFTER, ground_tells
from db import q, wget
from character_schema import (
    character_abilities,
    character_curiosity,
    character_interoception,
    character_name,
    character_psychology,
    character_standing_intentions,
    effective_drive,
    character_public_history,
    character_sampler,
    character_senses,
    character_temperature,
    character_tier,
    character_voice,
    senses_as_text,
)
from frames import is_recognized_in_frame
from memory import (
    build_character_memory_context,
    knowledge_for_character,
    relationships_for_payload,
)
from prompts import get_prompt
from scene import (
    NON_AWAKE_GATED,
    all_cast_name_to_id,
    awareness_of,
    dialogue_budget,
    get_scene,
    persona_of,
    private_knowledge_for,
    sheet_state,
)
from schemas import validate_llm_output
from spatial import (corridor_sightlines, room_of, spatial_digest,
                     visible_adjacent_rooms)
from survival import vitals_of
from psychology_runtime import cognitive_absorption
from theory_of_mind import mind_models_for_payload, sheet_capacity

from .common import (
    _agent_json,
    _books,
    _char_known_tags,
    _dict,
    _list,
    _normalize_character_output,
    assign_event_ids,
    cap_mind_model_updates,
    character_room,
    norm_sequence,
)

def _merge_standing_intentions(authored, emergent):
    """Merge a character's authored standing intentions with the emergent ones
    formed at runtime. Authored intentions are always present (the character's
    defining goals), but an emergent intention whose text closely restates an
    authored one SUPERSEDES it -- the emergent copy carries live progress/status
    (including a `blocked`/nonviable state), so a goal the world has closed does
    not reappear as freshly-active. De-dup is by casefolded intent text."""
    emergent = [i for i in (emergent or []) if isinstance(i, dict)]
    seen = {str(i.get("intent") or "").strip().casefold() for i in emergent}
    kept_authored = [
        a for a in (authored or [])
        if isinstance(a, dict)
        and str(a.get("intent") or "").strip().casefold() not in seen
    ]
    return kept_authored + emergent


def _recent_self_lines(chat_id, char_name, current_turn_idx, n_turns=3, cap=4,
                       frame_id=None):
    """The character's own most-recent spoken lines, verbatim, oldest->newest,
    from the last few committed turns' director_resolve dialogue_log.

    Without this the character agent only ever sees the CURRENT beat plus its
    static sheet, so a character in a standing situation (an escort repeating
    'keep moving' at a checkpoint that will not clear) re-derives the same line
    turn after turn -- verbatim repetition reads as a broken machine. Feeding
    its own recent lines lets it notice the refrain and vary or escalate
    (through specificity/consequence, per the character prompt), never as an
    emotional-volume spike."""
    if current_turn_idx is None:
        return []
    rows = q(
        "SELECT t.idx AS idx, v.content AS content FROM turns t "
        "JOIN steps s ON s.turn_id=t.id AND s.key='director_resolve' "
        "JOIN variants v ON v.step_id=s.id AND v.active=1 "
        "WHERE t.chat_id=? AND t.idx < ? AND t.frame_id IS ? "
        "ORDER BY t.idx DESC LIMIT ?",
        (chat_id, current_turn_idx, frame_id, n_turns),
    )
    cf = str(char_name or "").casefold()
    lines = []
    for r in rows:
        try:
            dr = json.loads(r["content"])
        except (TypeError, ValueError):
            continue
        for d in (dr.get("dialogue_log") or []):
            if str(d.get("speaker") or "").casefold() == cf:
                quote = str(d.get("exact_quote") or "").strip()
                if quote:
                    lines.append({"turn": r["idx"], "said": quote})
    lines.sort(key=lambda x: x["turn"])
    return lines[-cap:]


def _known_pronouns(cast, persona, recognized, exclude=None):
    """Canonical pronouns for the people this character ALREADY KNOWS, so a
    speaker refers to others correctly instead of guessing from a name (W6 --
    Crusher said "her discovery" about a he/him character).

    Info barrier: `recognized` is the character's own relationship/mind-model
    key set, which the caller has already frame-filtered by recognition. A
    stranger in the room is deliberately absent -- you don't know an
    unfamiliar person's pronouns, and handing them over would leak identity
    the character never legitimately acquired.
    """
    sheets = []
    for row in (cast or []):
        try:
            sheets.append((json.loads(row["sheet"]).get("identity") or {}))
        except Exception:
            continue
    if isinstance(persona, dict):
        sheets.append(persona.get("identity") or {})
    out = {}
    skip = {str(n or "").strip().casefold() for n in (exclude or [])}
    known = {str(n or "").strip().casefold() for n in (recognized or [])}
    for ident in sheets:
        name = str(ident.get("name") or "").strip()
        folded = name.casefold()
        if not name or folded in skip or folded not in known:
            continue
        pronouns = ident.get("pronouns") or {}
        clean = {k: pronouns[k] for k in ("subject", "object", "possessive")
                 if isinstance(pronouns, dict) and pronouns.get(k)}
        if clean:
            out[name] = clean
    return out


# How far back "recently" reaches, and how few rooms count as a pocket.
# Twelve beats is long enough to contain a couple of honest there-and-back
# trips through a hub and short enough that a genuine lock shows inside it;
# four rooms is a corridor stub or a small ring, not a region.
LOOP_WINDOW = 12
LOOP_POCKET = 4


def _annotate_known_exits(digest, scene, visited_rooms, known_exits=None,
                          here_rid=None, routes_that_worked=None):
    """Mark each exit with whether this character has been through it.

    `spatial_digest` renders an exit as {room, barrier} -- identical whether
    the character arrived through that doorway a beat ago or has never taken
    it. With nothing to separate them, preferring the unexplored exit is not a
    choice the payload makes available, and the result reads as backtracking.

    `visited_rooms` is the character's OWN route (commit records it from their
    committed position), so this adds no knowledge they did not earn by
    walking. `last_seen_beats_ago` is ordinal, not a turn count: how far back
    in their own route it was, which is the form a person actually has.

    `no_route_onward` marks an exit they entered and always had to reverse out
    of -- the thing `been_there` cannot say, and the thing that actually stops
    a repeated wrong turn. It is about DOORWAYS, not worth: somewhere they
    chose to linger is never marked, because that is a destination rather than
    a wrong turn.
    """
    if not isinstance(digest, dict):
        return digest
    rooms = (scene or {}).get("rooms") or {}
    name_to_id = {}
    for rid, room in rooms.items():
        display = str((room or {}).get("name") or rid)
        name_to_id.setdefault(display, rid)
    # What can be SEEN through each doorway right now, as against what has been
    # walked. A chamber with no other way out is visible as such from the
    # threshold; making a character enter it to find out is not caution, it is
    # a missing sense.
    seen_onward, seen_bearings = {}, {}
    if here_rid:
        try:
            from spatial import visible_adjacent_rooms
            for item in visible_adjacent_rooms(scene, here_rid) or []:
                if isinstance(item, dict) and "onward_exits" in item:
                    rid_seen = str(item.get("room_id"))
                    seen_onward[rid_seen] = item["onward_exits"]
                    # WHICH way on, not merely how many. The digest buckets
                    # exits egocentrically (ahead/behind/left), so a count
                    # sitting on the "behind" bucket carries no heading of its
                    # own and gets read as "on in the direction I was already
                    # facing" -- which is how a runner came to hunt a westward
                    # exit, four times, out of a chamber whose only other way
                    # out went north.
                    if item.get("onward_bearings"):
                        seen_bearings[rid_seen] = item["onward_bearings"]
        except Exception:
            seen_onward, seen_bearings = {}, {}
    worked = routes_that_worked if isinstance(routes_that_worked, dict) else {}
    route = [r for r in (visited_rooms or []) if isinstance(r, str)]
    counts = {}
    for rid in route:
        counts[rid] = counts.get(rid, 0) + 1
    # HOW RECENTLY, not merely how often. `times_entered` is a lifetime tally,
    # and a lifetime tally cannot tell "four times over eighty beats" from
    # "four times in the last twelve" -- which are the difference between a
    # thoroughfare and a loop you are stuck in.
    #
    # Observed live: on his second attempt at the same maze a character locked
    # into a period-four cycle, 0001 -> 0002 -> 0001 -> 0000, three times
    # exactly. He was not blind to the way out -- he GENERATED "south into
    # 0100" as a candidate, that being real new ground, and rejected it with
    # `norm_conflict: conflicts with association that east from blue-tile
    # reset leads toward 0507`. A route learned on the previous run was
    # outranking the evidence in front of him, and nothing in the payload said
    # that route had just failed three times running.
    #
    # This is the missing fact, and it is his own route, so it crosses no
    # boundary: a person who has walked the same three rooms four times in a
    # dozen paces knows it without being told.
    recent = route[-LOOP_WINDOW:]
    recent_counts = {}
    for rid in recent:
        recent_counts[rid] = recent_counts.get(rid, 0) + 1
    # A pocket is a handful of rooms that have absorbed a long stretch of the
    # route. Deliberately conservative: it needs a nearly-full window AND
    # genuinely few rooms, so that ordinary back-and-forth through a hub does
    # not read as being stuck.
    circling = set()
    if len(recent) >= LOOP_WINDOW and len(set(recent)) <= LOOP_POCKET:
        circling = set(recent)
    # Which rooms, in this character's OWN experience, they walked into and had
    # to walk straight back out of.
    #
    # `been_there` alone does not stop anyone re-entering a dead end -- and it
    # did not: observed live, a character was told been_there/times_entered=9
    # for a one-exit chamber and walked back into it six times, because knowing
    # you have been somewhere is not knowing it led nowhere. That is the
    # difference between visit history and route knowledge, and only the second
    # is any use for navigating.
    #
    # Derived purely from their own route: entered, and the next room was the
    # one they had just come from. No oracle knowledge of the maze -- this is
    # exactly what a person remembers about a wrong turn.
    returns, onward, dwelt = {}, {}, set()
    for i, rid in enumerate(route):
        if i + 1 < len(route) and route[i + 1] == rid:
            # Stayed put here for a beat. A place someone CHOSE to remain in
            # was a destination, not a wrong turn -- see below.
            dwelt.add(rid)
        if i == 0 or i + 1 >= len(route):
            continue
        if route[i + 1] == route[i - 1]:
            returns[rid] = returns.get(rid, 0) + 1
        elif route[i + 1] != rid:
            onward[rid] = onward.get(rid, 0) + 1

    # Exits seen from rooms actually stood in, recorded at commit. The FRONTIER
    # is a door seen but never walked through -- and it is the only thing that
    # separates "that way is exhausted" from "that way is where I came from".
    #
    # A first attempt used only walked adjacency, which collapses the whole
    # visited region into one blob: every exit came back "nothing new that way",
    # including the way out. A signal that fires on everything is worse than
    # none, because it argues against the correct move as loudly as the wrong
    # one.
    #
    # The single-room dead end is the easy case, caught by no_route_onward. What
    # actually traps is a dead-end CORRIDOR -- observed live, a character
    # bounced between two pass-through rooms for ten beats, since each was a
    # legitimate onward move and the exhausted thing was the whole branch.
    known_exits = {
        k: set(v) for k, v in (known_exits or {}).items() if isinstance(v, list)
    }
    visited = set(route)

    def _frontier_beyond(first_step, here_rid):
        """Is there any door left untried down that way."""
        if first_step not in known_exits:
            # Never stood there, so its doors are unknown: everything past it
            # is potentially new.
            return True
        stack, seen_here = [first_step], {here_rid, first_step}
        while stack:
            cur = stack.pop()
            for nxt in known_exits.get(cur, ()):
                if nxt not in visited:
                    return True          # a door seen and never taken
                if nxt not in seen_here and nxt in known_exits:
                    seen_here.add(nxt)
                    stack.append(nxt)
        return False
    out = {}
    for bucket, edges in digest.items():
        if not isinstance(edges, list):
            out[bucket] = edges
            continue
        marked = []
        for edge in edges:
            if not isinstance(edge, dict):
                marked.append(edge)
                continue
            rid = name_to_id.get(str(edge.get("room") or ""))
            entry = dict(edge)
            if rid in seen_onward:
                # Absent means "cannot tell from here" -- never "none".
                entry["onward_exits_visible"] = seen_onward[rid]
                if rid in seen_bearings:
                    entry["onward_bearings"] = seen_bearings[rid]
                if seen_onward[rid] == 0:
                    entry["visibly_no_way_through"] = True
            if rid and worked.get(rid):
                # The counterweight. Every other marker here says where they
                # have BEEN; this is the only one that says something WORKED,
                # and without it a proven route reads as merely old.
                entry["worked_before"] = worked[rid]
            if rid and rid in counts:
                entry["been_there"] = True
                entry["times_entered"] = counts[rid]
                if recent_counts.get(rid, 0) > 1:
                    # The one number that separates a thoroughfare from a
                    # loop. Only emitted above 1, because "you were there
                    # once recently" is just where you came from.
                    entry["entered_recently"] = recent_counts[rid]
                if rid in circling:
                    entry["circling_here"] = True
                if returns.get(rid):
                    # The FACT: they went in and came straight back out, N
                    # times. Always reported, because it is simply what
                    # happened.
                    entry["turned_back_here"] = returns[rid]
                    # The INFERENCE, named for what it actually is: no route
                    # ONWARD. Not "leads nowhere" -- a tavern is a room you
                    # enter and leave by the same door, and a marker calling it
                    # a dead end tells a character to avoid the place they were
                    # going. This says only that it is not a way THROUGH: a
                    # fact about doorways, saying nothing about whether it is
                    # worth being in.
                    #
                    # Held to two reversals with no onward move, and never
                    # applied to somewhere they chose to REMAIN: dwelling is
                    # what going somewhere on purpose looks like, as against
                    # passing through and finding a wall.
                    if (returns[rid] >= 2 and not onward.get(rid)
                            and rid not in dwelt):
                        entry["no_route_onward"] = True
                if here_rid and not _frontier_beyond(rid, here_rid):
                    entry["no_new_ground_that_way"] = True
                for back, seen in enumerate(reversed(route), 1):
                    if seen == rid:
                        entry["last_seen_beats_ago"] = back
                        break
            else:
                entry["been_there"] = False
            marked.append(entry)
        out[bucket] = marked
    return out


def character_step(ctx, cid, nonce):
    chat = ctx.chat
    row = next((c for c in ctx.cast if c["id"] == cid), None)
    if row is None:
        # Cast member was dismissed between plan construction and execution;
        # skip this character step gracefully rather than crashing with
        # StopIteration.
        return None
    sh, active, stance = sheet_state(row)
    sc = get_scene(chat["id"], chat)

    # Consciousness gate (choke point): an unconscious/asleep/sedated mind does
    # not deliberate or act. The planner and both loops already drop non-awake
    # reactors; this guard protects rerun/resume paths that hydrate a stale plan
    # and makes the invariant hold no matter who calls character_step. No LLM
    # call, no manifest (which perception would otherwise deliver as tells).
    if awareness_of(chat["id"], character_name(sh)) in NON_AWAKE_GATED:
        return {"sequence": [], "speech": None, "action": None, "actions": [],
                "manifest": {}, "mind_model_updates": [],
                "_awareness_gated": True}

    interaction_views = ctx.get("interaction_views", {}) or {}
    reaction_views = ctx.get("reaction_views", {}) or {}
    view = reaction_views.get(cid) or interaction_views.get(cid)
    if view is None:
        view = ((ctx.get("perception_act", {}).get("views") or {}).get(str(cid)))
    base_observations = (
        (ctx.get("perception_act", {}).get("observations") or {}).get(str(cid))
        or []
    )
    base_view = ((ctx.get("perception_act", {}).get("views") or {}).get(str(cid)))
    # Interaction/reaction micro-views are already filtered for this mind but
    # do not pass through the full perception stage. Never reuse stale base
    # metadata for a changed view; project only the permitted text itself.
    if view and view != base_view:
        observations = [{
            "observation_id": f"current:{cid}:micro",
            "perceiver_id": str(cid),
            "source_atom_id": "current",
            "channel": "mixed",
            "fidelity": "rendered",
            "observed": {"text": str(view)},
            "intensity": 0.5,
            "suddenness": 0.1,
            "ambiguity": 0.3,
            "directed_at_self": False,
        }]
    else:
        observations = base_observations

    # Resolved before the memory context, not after: where the character is
    # standing is a retrieval cue, and the recall is built here.
    char_room = character_room(sc, sh)
    memory_context = build_character_memory_context(
        chat_id=chat.id, char_id=cid,
        current_turn_idx=ctx.turn.idx,
        current_view=view or "",
        active_state=active,
        here=(sc.get("rooms") or {}).get(char_room, {}).get("name") or char_room,
        # Rooms currently in sight are cues too. Recalling what happened where
        # you STAND tells you where you are; recalling it about a room you can
        # SEE tells you whether to go there -- which is the decision actually
        # being made.
        in_sight=[
            str(item.get("room_name") or item.get("room_id"))
            for item in (visible_adjacent_rooms(sc, char_room) or [])
            if isinstance(item, dict)
        ] if char_room else None,
    )
    known_tags, excl_titles = _char_known_tags(sh)
    knowledge = knowledge_for_character(_books(ctx), char_room, known_tags, excl_titles)
    stored_state = json.loads(row["cstate"] or "{}")

    _interp = _dict(ctx.director_interpret)
    _flow = _dict(_interp.get("flow"))
    _tom = _list(_flow.get("tom_triggers"))

    relationships = relationships_for_payload(chat.id, cid)
    _sim_clock = wget(
        chat.id, "simulation_clock",
        {"elapsed_seconds": 0.0, "display": "now"},
    )
    mind_models = mind_models_for_payload(
        stored_state.get("mind_models") or {}, ctx.turn.idx,
        elapsed_seconds=(_sim_clock or {}).get("elapsed_seconds"),
    )
    # How much of this mind its own body currently has. Own interoceptive state
    # only -- another character's pain is never an input to this character's
    # cognition (see AGENTS.md's own-body isolation rule).
    absorption = cognitive_absorption(
        (active or {}).get("hedonic"), (active or {}).get("stress"))
    # The stable sheet is SELECTED at commit (where the reconciled beliefs and
    # the settled end-of-beat body state both exist) and simply read here, so
    # what the character holds in mind this turn is what they came out of the
    # last beat holding.
    active_hypotheses = list(stored_state.get("active_hypotheses") or [])[
        :sheet_capacity(absorption)]
    frame_id = ctx.turn.frame_id
    if frame_id is not None:
        # A frame's own state-swap already starts blank the first time
        # it's visited, but nonexistent_cast is the deterministic
        # backstop regardless of how relationship/mind-model data got
        # there -- e.g. a character not yet born must never appear known
        # to a native here even if something upstream got it wrong.
        #
        # all_cast_name_to_id (NOT ctx.cast, which is active-only) --
        # a DORMANT cast member must be checked against nonexistent_cast
        # exactly like an active one. Building this from ctx.cast alone
        # made a dormant not-yet-existing character fall through to the
        # -1 fallback below, which reads as "recognized" (-1 is never in
        # a frame's nonexistent_cast list), silently defeating the mask
        # for exactly the case it exists to catch. A name that isn't ANY
        # cast member at all (a background presence, an unsheeted NPC)
        # correctly keeps that same -1/"recognized" fallback -- this
        # mask only ever applies to declared cast members.
        name_to_id = all_cast_name_to_id(chat.id)
        relationships = {
            name: rel for name, rel in relationships.items()
            if is_recognized_in_frame(name_to_id.get(name, -1), frame_id)
        }
        mind_models = {
            name: mm for name, mm in mind_models.items()
            if is_recognized_in_frame(name_to_id.get(name, -1), frame_id)
        }

    _interior = stored_state.get("interior") or {}
    _psych = character_psychology(sh)
    # Tier-1: show the EFFECTIVE (possibly rupture-shifted) drive, read-only.
    _psych["drive"] = effective_drive(_psych, _interior)
    # A drive rupture is proposable ONLY inside its open window (see commit's
    # detect_drive_rupture) -- the base contract never documents drive_shift, so
    # the model cannot flip-flop it; it appears here only when the engine opened
    # the window this beat or in the two beats after.
    _rupture = _interior.get("drive_rupture")
    _window_open = bool(isinstance(_rupture, dict)
                        and ctx.turn.idx <= int(_rupture.get("window_expires") or -1))
    # How long the window has been open. Once it has stayed open
    # RUPTURE_FORCE_AFTER turns, the optional "you MAY shift" becomes a FORCED
    # resolution (below) -- the fix for a rupture that the engine keeps holding
    # open while the model quietly declines it every beat (the 23-turn limbo).
    _rupture_turns_open = (
        ctx.turn.idx - int(_rupture.get("opened_turn") or _rupture.get("turn") or ctx.turn.idx)
        if isinstance(_rupture, dict) else 0)
    _rupture_forced = _window_open and _rupture_turns_open >= RUPTURE_FORCE_AFTER
    # Crisis: strain at visible-breaking level. Even before any drive_shift,
    # the flag (plus the CRISIS prompt block below) forces the manifest/tells
    # to show the character cracking instead of playing untouched calm.
    try:
        _strain = float(_interior.get("drive_strain") or 0.0)
    except (TypeError, ValueError):
        _strain = 0.0
    _crisis = _strain >= CRISIS_STRAIN_MIN
    # Recent-tell ledger (written by commit): physical cues already shown,
    # fed back so the model does not reuse the same gesture every beat.
    _recent_tells = [str(t) for t in (stored_state.get("recent_tells") or [])
                     if str(t).strip()]
    # Tell-ground ledger (F6, written by commit): each recent cue with the
    # private ground it betrayed, fed back so a planted tell can be PAID OFF
    # in a later beat -- the ground surfacing in behavior or speech -- instead
    # of dangling forever as fake significance. Private context only; the
    # grounds never reach observers.
    _tell_grounds = [
        {"cue": str(g.get("cue") or ""), "because": str(g.get("because") or "")}
        for g in (stored_state.get("tell_grounds") or [])
        if isinstance(g, dict) and str(g.get("cue") or "").strip()
    ]
    _self = {
        "entity_id": f"character:{cid}",
        "name": character_name(sh),
        "public_history": character_public_history(sh),
        "psychology": _psych,
        "stance": stance,
        # How readily this mind leaves a known-good way for an untried one.
        # Explicit because the balance was previously implicit -- an artefact of
        # which navigational markers existed, not an authored trait.
        "curiosity": character_curiosity(sh),
        "active_state": active,
        "voice": character_voice(sh),
        "senses": senses_as_text(character_senses(sh)),
        "sense_profile": character_senses(sh),
        "interoception": character_interoception(sh),
        "abilities": character_abilities(sh),
        "attire": sc.get("attire", {}).get(character_name(sh)),
        "recent_self_lines": _recent_self_lines(
            chat.id, character_name(sh), ctx.turn.idx,
            frame_id=ctx.turn.frame_id),
        # Tier-2 goal hierarchy: the character's AUTHORED standing intentions
        # (its defining goals, always present so it acts proactively) merged
        # with EMERGENT intentions formed at runtime via intent_ops. An emergent
        # intention that restates an authored one wins (it carries live
        # progress/status). Read-only context for deriving this beat's wants.
        "intentions": _merge_standing_intentions(
            character_standing_intentions(sh), _interior.get("intentions") or []),
        # Former drives (scars) give continuity to a character who has changed.
        "former_drives": _interior.get("former_drives") or [],
        "learned_beliefs": _interior.get("beliefs") or [],
        "learned_associations": _interior.get("associations") or [],
    }
    _body_state = vitals_of(sc, character_name(sh))
    if _body_state:
        # Own-body interoception only. Other characters' vitals never enter
        # this payload; their outward signs must cross perception normally.
        _self["body_state"] = _body_state
    if _window_open:
        _self["rupture"] = {"why": _rupture.get("why"), "direction": _rupture.get("direction"),
                            "forced": _rupture_forced}
    if _crisis:
        _self["crisis"] = True
    if _recent_tells:
        _self["recent_tells"] = _recent_tells
    if _tell_grounds:
        _self["tell_grounds"] = _tell_grounds
    payload = {
        "self": _self,
        "perception": {
            "view": view or "You register nothing new this beat.",
            "observations": observations,
            # This character's OWN egocentric exits (ahead/behind/left/right of
            # the way THEY face) -- grounding for their movement/positioning
            # choices, not a script to narrate. Empty when they have no
            # established orientation.
            "spatial_frame": _annotate_known_exits(
                spatial_digest(sc, character_name(sh)), sc,
                stored_state.get("visited_rooms") or [],
                known_exits=stored_state.get("known_exits") or {},
                here_rid=char_room,
                routes_that_worked=stored_state.get("routes_that_worked") or {}),
            # Where they are, named. The digest lists what leads OUT of a room
            # without ever naming the room itself, so a character had to
            # re-derive their own location from the view's prose every beat.
            "current_room": (sc.get("rooms") or {}).get(
                character_room(sc, sh), {}).get("name") or "",
            # Looking straight down each passage: whether it ends, opens out or
            # bends, and roughly how far off. Coarse on purpose -- "some way
            # north the passage comes to an end" is the percept, not a room
            # count -- and it stops at corners, so it is sight rather than a
            # map.
            "corridor_sight": corridor_sightlines(sc, char_room),
        },
        "memory": memory_context,
        "relationships": relationships,
        "mind_models": mind_models,
        # The stable hypothesis sheet: the few open questions this mind is
        # actively holding, each keyed "i_suspect" so the field itself carries
        # the epistemic status. mind_models above is the full ledger; this is
        # what is actually in mind, and its size shrinks with absorption.
        "active_hypotheses": active_hypotheses,
        "known_pronouns": _known_pronouns(
            ctx.cast, persona_of(chat),
            set(relationships) | set(mind_models),
            exclude=[character_name(sh)]),
        "private_knowledge": private_knowledge_for(chat, character_name(sh), ctx.turn.frame_id),
        "world_knowledge": knowledge,
        "decision": {
            "deep_tom_requested": cid in _tom,
            "dialogue_mode": bool(_flow.get("dialogue_mode", False)),
            "speech_budget": dialogue_budget(chat, ctx.turn, cid, nonce),
        },
        "simulation_clock": _sim_clock,
        "variant_seed": nonce,
    }

    # Authorial offers (P3): propositions the PLAYER authored about THIS
    # character's interior/behavior, rerouted here instead of being enacted as
    # truth (see director._route_authorial_npc_beat). The character decides
    # in-character how (or whether) each lands -- its agency is preserved.
    _offers = [o.get("proposition") for o in
               ((ctx.get("director_interpret") or {}).get("authorial_offers") or [])
               if o.get("subject_id") == cid and o.get("proposition")]
    if _offers:
        payload["decision"]["authorial_offers"] = _offers

    role = {"bg": "character_bg", "mid": "character_mid",
            "major": "character_major"}.get(character_tier(sh), "character_mid")

    _cprompt = get_prompt("character").replace("{name}", character_name(sh))
    if _window_open:
        # The base contract never documents drive_shift; the instruction to emit
        # one exists ONLY inside an engine-opened rupture window, so a drive can
        # never flip-flop turn to turn.
        _cprompt += (
            "\n\nDRIVE RUPTURE (window OPEN this beat): a shattering, drive-level "
            "event has cracked what you live for (see self.rupture.why). This event "
            "has ALREADY changed you -- the only question is how the change surfaces. "
            "Denial is a phase, not a stable end: even if you cling to the old drive, "
            "show the crack in your behavior NOW (a ritual performed wrong, a "
            "signature line that dies mid-sentence, a rule reached for and found "
            "hollow). And if your core is genuinely remade, emit drive_shift "
            "{essence, expression, taboo, because}: essence = the new deepest thing "
            "you live for, expression = how it shows, taboo = what you now cannot "
            "do; `because` must name the rupture event. WORKED EXAMPLE: a magistrate "
            "whose drive was 'the law is the only shelter' watches the court execute "
            "the clerk she vouched for. She emits drive_shift {\"essence\": "
            "\"protect the person in front of me, not the rule\", \"expression\": "
            "\"quietly bends procedure to shield people\", \"taboo\": \"never again "
            "hand someone over to process\", \"because\": \"the court executed the "
            "clerk I vouched for\"} -- and her sequence THIS beat already shows it: "
            "she pockets the arrest warrant instead of filing it. A shift is rare "
            "and irreversible -- do not shift for a survivable wound; but do not "
            "play untouched calm either. NEVER announce the change in dialogue; it "
            "shows only in what you do and come to want.")
        if _rupture_forced:
            _cprompt += (
                "\n\nRUPTURE -- FORCED RESOLUTION: this window has now stayed open "
                "several beats and you have kept deferring. Deferral is over. THIS "
                "beat you must LAND it, one way or the other, visibly on the page -- "
                "passive, untouched, wait-and-see calm is NOT an available option "
                "anymore; the strain has been on you far too long for that. Choose "
                "exactly one and enact it in your sequence this beat: (A) emit "
                "drive_shift {essence, expression, taboo, because} AND let your "
                "action/speech this beat already do the new thing -- not a promise "
                "to change, the change itself; or (B) if your core genuinely holds, "
                "stop merely enduring and REAFFIRM it in a concrete, costly act your "
                "pre-rupture self would recognize as doubling down -- a line said, a "
                "hand that acts, a refusal made real. Do not simply describe the "
                "strain again. Resolve it.")
    if _crisis:
        _cprompt += (
            "\n\nCRISIS (self.crisis -- your drive is under extreme strain): what "
            "you live for is under sustained assault and your composure is FAILING. "
            "Your manifest must show it: surface_demeanor cracks at the seams, and "
            "your tells escalate from subtle to VISIBLE (subtlety <= 0.4) -- a "
            "voice that breaks mid-sentence, a hand that will not stay still, a "
            "pause held one beat too long. You need not change what you live for, "
            "but you can no longer look untouched. Do NOT announce the strain in "
            "dialogue; it leaks through the body.")
    if _recent_tells:
        _cprompt += (
            "\n\nTELL VARIETY: self.recent_tells lists the physical cues you have "
            "already shown in recent beats. Do NOT reuse any of them -- or a "
            "near-identical variant -- as this beat's tell; find a DIFFERENT "
            "channel or gesture. A body under the same pressure finds new ways to "
            "betray it: vary the channel (face|eyes|voice|hands|posture|breath) "
            "and the cue itself.")
    if _tell_grounds:
        _cprompt += (
            "\n\nTELL PAYOFF: self.tell_grounds lists physical cues you have "
            "recently shown and, for each, the private ground it betrayed "
            "(`because`). These are debts the story has planted: when the scene "
            "gives a natural opening, let a ground SURFACE -- in what you do, "
            "choose, or say -- so an observant witness's banked suspicion can pay "
            "off. Never contradict a ground already shown, and never announce it "
            "as exposition; it emerges through behavior.")
    out = _agent_json(
        role,
        "character",
        _cprompt,
        payload,
        temperature=character_temperature(sh),
        sampler=character_sampler(sh) or None,
    )

    # Warning-only re-normalization; strict schema+semantic validation
    # (with repair/fallback/raise) already ran inside _agent_json -- a
    # mind_model_updates entry that fails CharacterOutput validation can
    # never reach the cap/commit path below.
    out, warnings = validate_llm_output("character", out)
    ctx.warnings.extend(warnings)

    out = _normalize_character_output(out)
    # F6: every manifest tell gets a stored ground (`because`) -- supplied by
    # the model or derived deterministically from the tell's own `betrays`
    # pointer -- so a planted anomaly always has a referent a later beat can
    # pay off. The ground stays private (perception delivers only the cue).
    if out.get("manifest"):
        out["manifest"], _tell_warnings = ground_tells(
            out.get("manifest"), out.get("active_state"))
        for _w in _tell_warnings:
            ctx.add_warning(f"character {character_name(sh)}: {_w}")
    out["mind_model_updates"] = cap_mind_model_updates(
        out.get("mind_model_updates") or [], absorption=absorption)
    norm_sequence(out)
    out["sequence"] = assign_event_ids(
        out.get("sequence"), f"turn:{ctx.turn.id}:character:{cid}")
    out["name"] = character_name(sh)
    out["char_id"] = cid
    return out
