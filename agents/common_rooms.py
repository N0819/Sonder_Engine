"""What a room holds for a perceiver: crowds and derived charter crowds,
chatter and its per-stage fetch, couriers and posted notices, the room's own
prose, the Director's lore slice and the payload room set.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from world import crowds as crowds_model
from story.character_schema import character_name, normalized_character_of_row
from core.db import wget
from mind.memory import chat_lorebook_ids, chat_lorebook_weights
from story.provenance_text import strip_engine_provenance
from story.scene import get_scene
from world.spatial import (
    ambient_scope,
    effective_room_size,
    nearby_rooms,
    normalize_room_id,
    room_of,
)

from agents.common_names import split_sentences

def _contextual_rooms(sc, cast, *extra_room_ids, hops=1):
    """The rooms dict to actually serialize into a stage's LLM payload:
    every occupied room (cast members' current rooms plus any extra room
    ids the caller supplies, e.g. the player's room) and their immediate
    neighbors, rather than the full scene.rooms dict. See
    spatial.nearby_rooms for why this exists. Callers must keep using the
    full, unfiltered scene for any deterministic spatial check.
    """
    centers = set()
    names = []
    for row in cast:
        # The stored sheet TEXT is the key, so normalization is paid once per
        # distinct card per process rather than once per reader (C14). None
        # still means "this row is not cast", as the parse failure did.
        sheet = normalized_character_of_row(row)
        if sheet is None:
            continue
        name = character_name(sheet)
        r = room_of(sc, name)
        if r:
            centers.add(r)
            # The names go with the rooms: a cast member CARRYING a handset is
            # on a channel that names no room, so the far end is reachable
            # only when the question is asked as them.
            if name:
                names.append(name)
    for extra in extra_room_ids:
        if extra:
            centers.add(extra)
    # THE COMPOSITION IS `spatial.attended_rooms`, and it is shared on purpose.
    # A live channel's far end is a room this beat attends to -- everything
    # that decides who may act reads where bodies STAND, so a person on the
    # other end of a radio was outside every payload -- and a body's inside
    # goes where the body goes. The WALK under it differs from the causality
    # bubble's since 2026-10-13: a payload walks `hops` plain doorways, the
    # bubble the story's `bubble_radius` in rooms walked and the whole of the
    # building the party stands in (`spatial_bubbles.bubble_reach`, the
    # building since 2026-10-20). What keeps the two from disagreeing
    # where it matters is that every cast member's own room is a centre here:
    # a body inside the bubble's range is never missing from a payload, though
    # the rooms between it and the player need not be in one.
    try:
        from world.spatial import attended_rooms
        return attended_rooms(sc, centers, hops=hops, names=names)
    except Exception:
        return nearby_rooms(sc, centers, hops=hops)


CROWDS_KEY = crowds_model.CROWDS_WORLD_KEY


def crowds_for_room(cid, sc, room_id, inputs=None):
    """What crowds an observer in this room registers, already described.

    A crowd is a thing in a room, so it is delivered per observer and scoped to
    the room they are standing in -- never as a scene-wide list, which would
    hand someone in a back office the state of the square outside.

    It deliberately does NOT go through the managed-presence path. A crowd that
    consumed one of the six `max_managed` slots would have solved nothing,
    which is the whole reason the object exists.

    Density is computed here rather than read, because it is a function of the
    band and the ROOM and the crowd may have walked into a different one since
    it was minted.

    TWO SPECIES SHARE THIS VIEW SHAPE (DESIGN_BACKGROUND_PRESENTATION §B1):
    the authored ledger rows above, and derived charter crowds
    (`charter_crowds_for_room`), appended below under the same fields so the
    composer and every payload read both identically. A derived row differs
    where the derivation says it must: no drift (charter bodies move
    individually on their own errands), no `emerged` list (an emerged body's
    presence record IS the record and membership excludes it at the next
    read), no `talk` (the charter's talk is the chatter seam's, delivered
    beside this view, never twice). ``inputs`` is `chatter_inputs`' shared
    fetch, exactly as `chatter_for_room` takes it.
    """
    if not room_id:
        return []
    # `effective_room_size`, not the raw authored string: an unsized "Great
    # Hall" is `large` for proximity grading and was `medium` here, so
    # `density("a throng", ...)` returned PACKED under one and CRUSH under the
    # other -- and CRUSH is what `terrain` turns into a `membrane` you cannot
    # see across and what `drift` turns into CARRY. One question, one answer.
    size = effective_room_size(sc or {}, room_id)
    out = []
    standing = _standing(inputs, "crowds",
                         lambda: wget(cid, CROWDS_KEY, []) or [])
    for crowd in crowds_model.crowds_in_room(standing, room_id):
        out.append({
            "uid": crowd.get("uid"),
            "what": crowds_model.describe(crowd, size),
            "density": crowds_model.density(crowd.get("band"), size),
            # WHAT A CHANGE IS MEASURED AGAINST, published beside the
            # sentence composed from it. `composer.room_content_percepts`
            # hashed `what` and nothing else, so every re-rendering of an
            # unchanged crowd read as an event and reached the narrator as an
            # obligation (chat 95: seven `changed` verdicts in sixteen turns
            # on a crowd whose band never moved). An authored crowd's
            # composition IS state -- it is a stored field, and it changes
            # only when `crowds.apply_ops` writes it, which is an event.
            "state": (crowds_model.normalize_band(crowd.get("band")),
                      str(crowd.get("composition") or ""),
                      crowds_model.density(crowd.get("band"), size),
                      str(crowd.get("mood") or "")),
            "heading": crowd.get("heading") or None,
            # A crowd is terrain, so the observer is told what kind. `open`
            # is ground with people on it; `membrane` is the barrier word
            # spatial.py already uses for a thing you push through and cannot
            # see across, which is what standing in a packed crowd is.
            "terrain": crowds_model.terrain(crowd.get("band"), size),
            # The press's OFFER, never its verdict: {toward, strength}. The
            # Director decides whether it lands, and if it does it is an
            # arrival that goes through the commit path like any other move.
            "drift": crowds_model.drift(crowd, size),
            # Who is already standing out of it. Delivered so the Director
            # voices the rope-seller it emerged last beat instead of emerging
            # a second one, and so the crowd is not asked to produce a person
            # who is already in front of the player.
            "emerged": list(crowd.get("emerged") or []),
            # What the murmur is ABOUT, when the crowd holds anything --
            # attributed as talk, never to a name. Own-room only by
            # construction: every caller passes the observer's own room, so
            # a crowd seen across an open doorway is a shape and a sound,
            # never words (the zero-content assertion stays zero-content).
            # This is perception of ambient speech, the design's first
            # legitimate door; the durable carried-report copy still moves
            # only through an explicit telling op.
            "talk": crowds_model.talk_view(crowd),
        })
    for crowd in charter_crowds_for_room(cid, sc, room_id, inputs):
        out.append({
            "uid": crowd.get("uid"),
            "what": crowds_model.describe(crowd, size),
            # Density, terrain and drift are the same physics for both
            # species: a press of simulated people is exactly as much a
            # membrane as a press of authored ones. Drift is None by
            # construction (a derived crowd has no heading), spelled through
            # the same function so there is one answer to what drift is.
            "density": crowds_model.density(crowd.get("band"), size),
            # The derived species' state carries no composition, and the
            # reason is not the species: `charter_crowd.composition_of` is
            # recomputed at every read as the top two of a tally over a
            # membership that moves individually by design, so it reorders
            # without the crowd changing. Measured, chat 95: five spellings
            # of one unchanged fact over sixteen turns ("a dozen or so
            # captains and commanders", "...commanders and lieutenant
            # commanders", "...lieutenant commanders and commanders"), and a
            # sorted set of the nouns still flips four times. The band is the
            # coarse summary of that same membership and it is what carries a
            # real change here -- `crowd_for` already says so ("the
            # membership count dies here: it met the band vocabulary").
            "state": (crowds_model.normalize_band(crowd.get("band")),
                      crowds_model.density(crowd.get("band"), size),
                      str(crowd.get("mood") or "")),
            "heading": None,
            "terrain": crowds_model.terrain(crowd.get("band"), size),
            "drift": crowds_model.drift(crowd, size),
            "emerged": [],
            "talk": [],
            # Recognisable twice over -- the uid prefix is the enforcement
            # (`crowds.apply_ops` refuses these), the flag is the courtesy.
            "derived": True,
        })
    return out


def chatter_inputs(cid, sc, turn_idx=None):
    """Everything ambient chatter reads, fetched once per perception stage —
    and, since Part B, everything the derived charter crowd reads too
    (`charter_crowds_for_room` shares this fetch under its own memo), so a
    stage pays the registry deepcopy once however many seams consume it.

    `charter_runtime.registry_for` normalizes the whole registry (measured
    21.8ms with its deepcopy on one 40-body charter), so a per-perceiver
    fetch would multiply that by the cast; the stage fetches once, every
    `chatter_for_room` call reuses the slices, and a per-room memo makes the
    co-located cast free. Presence records are read here too, and carry two
    different claims that must not collapse into one (Part C's §C3 split):
    `known_bodies` is RECOGNITION — a charter body somebody has met is
    somebody chatter attribution may name (§A2c), and a name once learned is
    never unlearned — while `presented_bodies` is PRESENTATION — the bodies
    a record still presents individually this beat, which lapses after
    `charter_crowd.PRESENTED_IDLE_BEATS` idle beats so the body returns to
    the derived crowd's ground. ``turn_idx`` is what ages the second set; a
    caller without one gets the conservative no-lapse read.
    """
    from world.charter_crowd import presented
    from world.charter_runtime import cached_registry

    # Through `cached_registry`, NOT `registry_for(cid)`: the registry key
    # is frame-scoped and `registry_for`'s default pins the PRESENT era
    # explicitly, while every sibling read on this seam (`crowds`,
    # `background_presences`) follows the pipeline's ambient active frame —
    # a flashback's observer must hear the flashback's charters. The cached
    # object is shared and read-only; this function only slices it.
    try:
        registry = cached_registry(cid)
    except Exception:
        registry = {"items": {}}
    known_refs = {}
    presented_refs = {}
    for rec in (wget(cid, "background_presences", {}) or {}).values():
        if not isinstance(rec, dict):
            continue
        live = turn_idx is None or presented(rec, turn_idx)
        for ref in rec.get("charter_refs") or []:
            if isinstance(ref, dict):
                known_refs.setdefault(
                    str(ref.get("charter") or ""), set()).add(
                    str(ref.get("body") or ""))
                if live:
                    presented_refs.setdefault(
                        str(ref.get("charter") or ""), set()).add(
                        str(ref.get("body") or ""))
    charters = []
    for key, item in sorted((registry.get("items") or {}).items()):
        state = (item or {}).get("state") or {}
        charters.append({
            "key": str(key),
            "bodies": state.get("bodies") or {},
            "watch": state.get("watch") or {},
            "posts": state.get("posts") or {},
            "naming": state.get("naming"),
            "figures": state.get("figures") or {},
            "window_acts": state.get("window_acts") or [],
            "clock_hours": float(state.get("clock_hours") or 0.0),
            "known_bodies": frozenset(known_refs.get(str(key), ())),
            "presented_bodies": frozenset(presented_refs.get(str(key), ())),
            # The two slices the derived crowd adds to chatter's read
            # (`charter_crowds_for_room` shares this fetch): who is bound to
            # a registered character, and what everyone is carrying.
            "bindings": frozenset(
                str(k) for k in (state.get("bindings") or {})),
            "feel": state.get("feel") or {},
            # What the charter's bodies ARE when they are not people: the
            # stranger label reads it (`presence_figures_for_room`).
            "creature": state.get("creature"),
        })
    # `standing` is the stage's slot for the OTHER per-room ledgers -- crowds,
    # couriers, posted notices (see `_standing`). Empty and filled on first
    # use, so a stage that reads none of them pays for none.
    return {"charters": charters, "memo": {}, "standing": {}}


def _standing(inputs, key, fetch):
    """One standing ledger, fetched at most once for the stage.

    Crowds, couriers and posted notices are objective per-ROOM facts read per
    PERCEIVER, so each row was fetched and parsed once per body in the scene:
    measured for review 2026-09-07 C20, 20 world reads for six perceivers
    where five answer the whole stage. What a room holds is the same fact for
    everyone standing in it -- the per-observer subtraction happens downstream
    in the composer -- so the shared object here is the parsed LEDGER, never a
    composed view, and every reader still slices it by its own room.

    A caller outside a perception stage (a panel, a test) brings no `inputs`
    and pays for its own read, exactly as before.
    """
    standing = (inputs or {}).get("standing") if isinstance(inputs, dict) \
        else None
    if not isinstance(standing, dict):
        return fetch()
    if key not in standing:
        standing[key] = fetch()
    return standing[key]


def charter_ground_for_room(cid, sc, room_id, inputs=None, *, turn_idx=None):
    """WHO IS GROUND IN THIS ROOM, asked once and answered once.

    ``{"crowds": [row, ...], "carried": {(charter key, body key), ...},
    "names": {display name casefolded, ...}}``, memoized per room on the
    stage's shared ``inputs``.

    DESIGN_BACKGROUND_PRESENTATION B2 states ONE subtraction: a charter body
    is ground -- carried by the derived crowd -- exactly when nothing this
    beat presents it individually. Both presentations are cut from that one
    answer, so the crowd is `carried` and the figures are `present -
    carried` by construction. They used to be two reads of the same slices
    (`charter_crowds_for_room` called `members_of` inside `crowd_for`, and
    `presence_figures_for_room` called it again over its own `inputs`), and
    two reads drift: measured live 2026-09-05 in one caravanserai run, in
    both directions -- turn 3's common room carried the band line "a handful
    serving hands and wardens" AND eleven individual figure labels, and turn
    12's courtyard delivered its seven bodies as a band and as nobody.
    **A body is presented once per view.** The answer is per (room, stage),
    so two observers looking at different rooms may legitimately differ;
    inside one view it cannot.

    `carried` ignores `CO_LOCATED_CAP` deliberately, as the figure loop
    always did: the cap decides how many crowds a room's view has space to
    DESCRIBE, never whether an institution's people are ground.

    ``names`` is the second identity space a view actually has -- the
    display names the derived records and the ledger rows are keyed by. A
    presence record whose `charter_refs` were never written names a body the
    crowd is carrying, and a ref-only test cannot see that; the name test
    can, so the same person cannot arrive as figure and as ground for want
    of a link nobody stored.
    """
    from world import charter_crowd

    if not room_id:
        return {"crowds": [], "carried": set(), "names": set()}
    inputs = (inputs if isinstance(inputs, dict)
              else chatter_inputs(cid, sc, turn_idx=turn_idx))
    memo = inputs.setdefault("ground_memo", {})
    room = str(room_id)
    if room in memo:
        return memo[room]
    rows, carried, names = [], set(), set()
    # A BODY THE SCENE PRESENTS IS NOT GROUND. `members_of` subtracts what
    # the background-presence ledger says is presented, and the COMMIT
    # writes that ledger -- so a body the Director bound to an entity THIS
    # beat (`charter_ref`, the identity floor's binding) was presented by the
    # scene and carried by its crowd at once. Chat 167 turn 4616: the
    # opening bound the landlord, and the view held "the middle-aged square
    # landlord ... is close by" beside "a handful of landlords and potmen".
    bound = _scene_bound_charter_bodies(sc)
    for charter in inputs.get("charters") or []:
        key = str(charter.get("key") or "")
        members = [member for member in charter_crowd.members_of(charter, room)
                   if (key, str(member)) not in bound]
        # A CROWD STILL HAS A FACE. One member per co-located institution is
        # fronted out of the band and falls through to
        # `presence_figures_for_room` as an individual figure, which is what
        # gives an observer standing in a busy room somebody to address and
        # the voice gate somebody to answer with. The subtraction stays ONE
        # subtraction -- `carried` is the band's membership and the figures
        # are its complement, exactly as before; the face has simply moved
        # from the first set to the second, and `crowd_for` is told so it
        # describes the bodies it actually carries.
        face = charter_crowd.crowd_face(charter, members,
                                        charter.get("feel") or {})
        crowd = charter_crowd.crowd_for(cid, charter, room, members,
                                        fronted=face)
        if crowd is None:
            continue
        rows.append(crowd)
        held = [member for member in members if str(member) != str(face)]
        carried.update((key, member) for member in held)
        names.update(_charter_body_display_names(charter, held))
    ground = {"crowds": rows[:charter_crowd.CO_LOCATED_CAP],
              "carried": carried, "names": names}
    memo[room] = ground
    return ground


def _scene_bound_charter_bodies(sc):
    """``{(charter key, body key)}`` every scene entity is bound to by its
    ``charter_ref`` -- the bodies the scene itself presents as individuals."""
    bound = set()
    for entity in ((sc or {}).get("entities") or {}).values():
        ref = entity.get("charter_ref") if isinstance(entity, dict) else None
        if isinstance(ref, dict) and ref.get("charter") and ref.get("body"):
            bound.add((str(ref["charter"]), str(ref["body"])))
    return bound


def _charter_body_display_names(charter, members):
    """The display names one charter's bodies are known by -- the same
    `charter_identity.display_name` every derived presence record and every
    figure row is keyed under, so the two spellings cannot differ."""
    from world.charter_identity import display_name

    roles = {}
    for post, holder in (charter.get("watch") or {}).items():
        roles.setdefault(str(holder), []).append(str(post))
    bodies = charter.get("bodies") or {}
    out = set()
    for key in members:
        body = bodies.get(key)
        if not isinstance(body, dict):
            continue
        for spelling in (display_name(body, roles.get(str(key)) or (),
                                      charter.get("naming")),
                         body.get("name")):
            text = str(spelling or "").strip().casefold()
            if text:
                out.add(text)
    return out


def charter_crowds_for_room(cid, sc, room_id, inputs=None, *, turn_idx=None):
    """The derived charter crowds standing in one room: stored-shape rows,
    computed from the registry and NEVER persisted.

    DESIGN_BACKGROUND_PRESENTATION Part B: the registry bodies whose place
    is this room, minus everyone individually presented (bound bodies,
    bodies with a live presence record), projected through
    `world.charter_crowd.crowd_for`. Derived at every read, so it cannot
    drift from where `charter_move.errands` actually walked people -- the
    second-source-of-truth scar `world/crowds.py` is written after.

    The crowd half of `charter_ground_for_room`, which is where the one
    subtraction lives now; the figures are the same answer's complement.

    Shares `chatter_inputs`' once-per-stage registry fetch and adds a
    per-room memo, exactly as `chatter_for_room` does; `persist/commit.py`
    calls this too, to resolve an `emerge` against the same rows perception
    showed, because with nothing stored the only way two readers agree is
    to be the same reader.
    """
    return [dict(row) for row in charter_ground_for_room(
        cid, sc, room_id, inputs, turn_idx=turn_idx)["crowds"]]


def attending_this_room(sc, observer, room_id):
    """Is this observer's attention ON this room rather than out of it.

    THE DISTINCTION `subject_label` WAS ALWAYS MAKING AND COULD NOT READ: a
    bystander catches that something happened; somebody listening on purpose
    catches what about. `orientation[name].focus` is the engine's own record
    of attention (`spatial_frames.infer_focus`), so this asks it rather than
    inventing a second notion of attending.

    Attention is ON the room when its focus names something IN the room -- a
    body standing here, one of the room's own fixtures, or, for an `edge`,
    the room on the far side of the doorway being watched.

    AN EDGE FOCUS ATTENDS WHAT IT POINTS INTO. The first cut read one as the
    bystander case -- "a body watching the street is not listening to the
    bar" -- which is true about the bar and wrong about the street, and the
    street is the half somebody watching a doorway is there for. Measured
    (Aldermill, fourth run, 2026-09-19): Sal Weatherby sat in the taproom with
    `focus {"kind": "edge", "ref": "wheel_bushel_kitchen"}` -- watching the
    kitchen, which is the whole of what she went in to do -- and took the
    bystander grade for both rooms. Topics overheard across 39 beats: zero.

    The invariant is untouched either way: perception asks this only for
    rooms the observer's hearing already reaches, so the grade decides how
    much of an audible fragment is legible and never which rooms are audible.

    Absent focus is absent attention, which keeps every story that never
    wrote an orientation record exactly where it was.
    """
    if not observer or not room_id:
        return False
    sc = sc if isinstance(sc, dict) else {}
    focus = ((sc.get("orientation") or {}).get(str(observer)) or {}).get("focus")
    if not isinstance(focus, dict):
        return False
    ref, kind = str(focus.get("ref") or ""), str(focus.get("kind") or "")
    if not ref:
        return False
    if kind == "target":
        return str((sc.get("positions") or {}).get(ref) or "") == str(room_id)
    if kind == "anchor":
        from world.spatial import effective_anchors
        return ref in (effective_anchors(sc, str(room_id)) or {})
    if kind == "edge":
        return ref == str(room_id)
    return False


def chatter_for_room(cid, sc, room_id, inputs=None, *, attending=False):
    """What an observer in this room hears of the crowd's talk: a hum band
    as ground, and at most one overheard fragment as figure.

    DESIGN_BACKGROUND_PRESENTATION Part A, delivered exactly where the crowd
    view is (`crowds_for_room`) and for the same reason: every caller passes
    the observer's own room, so admission is decided at the seam that
    already decides what a bystander takes in, and
    `composer.observations_from_render` then makes character receipt
    legitimate with no second representation. The fragment is the TRIPLE —
    speaker/act/other/subject labels — never the substrate's template line;
    the engine holds no sentence content, so none can cross.

    Deterministic and seeded from persisted state only (chat, room, each
    charter's own clock), so a replay renders the identical murmur.
    """
    from world import charter_chatter

    if not room_id:
        return []
    inputs = inputs if isinstance(inputs, dict) else chatter_inputs(cid, sc)
    memo = inputs.setdefault("memo", {})
    # KEYED BY THE GRADE TOO. The murmur is a property of the room; how much
    # of its topic is legible is a property of the observer, so two bodies in
    # one room with different attention get different answers and must not
    # share a cached one.
    room = str(room_id)
    memo_key = (room, bool(attending))
    if memo_key in memo:
        return [dict(e) for e in memo[memo_key]]

    size = effective_room_size(sc or {}, room)
    crowds = crowds_model.crowds_in_room(wget(cid, CROWDS_KEY, []) or [],
                                         room)
    # BOTH species feed the band floor and the density inversion (§A2a's
    # "graded against the crowd band already present", §A2d's table): a
    # derived charter crowd IS a crowd standing in the room, and in a
    # charter-only story the authored ledger is empty — reading it alone
    # left a derived throng with no hum floor and a derived crush still
    # admitting ordinary fragments, so degradation did not invert for the
    # exact species the design is about. One memoized read on the fetch
    # this function already shares with `charter_crowds_for_room`.
    standing = crowds + charter_crowds_for_room(cid, sc, room, inputs)
    band_rank = max((crowds_model.band_rank(c.get("band"))
                     for c in standing), default=0)
    severity = {crowds_model.LOOSE: 0, crowds_model.PACKED: 1,
                crowds_model.CRUSH: 2}
    density = crowds_model.LOOSE
    for crowd in standing:
        packed = crowds_model.density(crowd.get("band"), size)
        if severity[packed] > severity[density]:
            density = packed

    # The beat's entanglement set: whoever the scene itself places in this
    # room, plus anyone stepped out of a crowd here. The one fragment worth
    # hearing is the crowd talking about *you*.
    notable = {str(name) for name, where in
               ((sc or {}).get("positions") or {}).items()
               if str(where or "") == room}
    for crowd in crowds:
        notable.update(str(n) for n in (crowd.get("emerged") or []))

    rows = []
    for charter in inputs.get("charters") or []:
        bodies = charter["bodies"]
        figures = charter["figures"]

        def _name(key, charter=charter, bodies=bodies, figures=figures):
            key = str(key or "")
            if key in figures:
                return key
            body = bodies.get(key)
            return str((body or {}).get("name") or "") if body else ""

        for act in charter_chatter.acts_in_room(charter["window_acts"],
                                                room):
            rows.append({**act, "charter": charter,
                         "other_name": _name(act.get("other")),
                         "subject_name": _name(act.get("subject"))})

    hum = charter_chatter.hum_rank(len(rows), band_rank, density)
    seed_material = "chatter|%s|%s|%s" % (
        cid, room, "|".join("%s@%0.4f" % (c["key"], c["clock_hours"])
                            for c in inputs.get("charters") or []))
    out = []
    phrase = charter_chatter.hum_phrase(hum)
    if phrase:
        out.append({"kind": "hum", "uid": "hum:%s" % room, "what": phrase,
                    "band": charter_chatter.HUM_BANDS[hum]})

    picked = charter_chatter.overheard_fragment(
        rows, notable=notable, density=density, seed_material=seed_material)
    if picked is not None:
        charter = picked["charter"]
        # Both forms per participant, the ANONYMOUS one as the label this
        # room-level entry carries: the fragment is memoized per room and
        # read by every mind in it, and a name is licensed per observer
        # (`charter_chatter.participant_forms`, and `relabel_fragment` where
        # the observer is). A reader that never relabels reads a stranger.
        speaker = charter_chatter.participant_forms(
            picked.get("actor"), place=room, bodies=charter["bodies"],
            watch=charter["watch"], posts=charter["posts"],
            naming=charter["naming"], figures=charter["figures"],
            known_bodies=charter["known_bodies"])
        other = charter_chatter.participant_forms(
            picked.get("other"), place=room, bodies=charter["bodies"],
            watch=charter["watch"], posts=charter["posts"],
            naming=charter["naming"], figures=charter["figures"],
            known_bodies=charter["known_bodies"])
        subject = charter_chatter.subject_label(
            picked.get("subject"), bodies=charter["bodies"],
            figures=charter["figures"], naming=charter["naming"],
            attending=bool(attending))
        fragment = {"speaker_label": speaker["anon"], "act": picked.get("act"),
                    "other_label": other["anon"], "subject_label": subject,
                    "speaker_name": speaker["name"],
                    "speaker_anon": speaker["anon"],
                    "other_name": other["name"], "other_anon": other["anon"]}
        out.append({"kind": "fragment",
                    "uid": charter_chatter.fragment_key(picked),
                    "what": charter_chatter.fragment_phrase(fragment),
                    **fragment})
    memo[memo_key] = out
    return [dict(e) for e in out]


def couriers_for_room(cid, sc, room_id, inputs=None):
    """What couriers an observer in this room registers, already described.

    The perception half of the interception seam: a courier the player could
    never SEE is a courier the player could never stop, and the design's
    verbs -- intercept, follow, question, outrun, silence -- all begin with a
    body in a room noticing another body in it. Scoped to the observer's own
    room like `crowds_for_room`, and for the same reason.

    What crosses is what a bystander could take in: the figure, which door he
    makes for, whether he is waiting. NEVER the message -- a satchel does not
    broadcast its contents, and the report itself moves only through delivery,
    questioning, or seizure, all of which are commit-validated ops.

    ``inputs`` is `chatter_inputs`' shared fetch, as `crowds_for_room` takes
    it: the standing ledger is one read for the stage, not one per perceiver.
    """
    from story import couriers as couriers_model

    if not room_id:
        return []
    standing = _standing(
        inputs, "couriers",
        lambda: wget(cid, couriers_model.COURIERS_WORLD_KEY, []) or [])
    out = []
    for courier in couriers_model.couriers_in_room(standing, room_id):
        route = [str(r) for r in courier.get("route") or []]
        leg = max(0, int(courier.get("leg") or 0))
        heading = route[leg + 1] if leg + 1 < len(route) else None
        out.append({
            "courier_id": courier.get("uid"),
            "what": couriers_model.courier_voice(courier),
            "heading": heading,
            # Standing at his destination with the message undelivered: a
            # man waiting at a gate, which a beat may greet, rob or watch.
            "waiting": courier.get("status") == couriers_model.ARRIVED,
        })
    for courier in couriers_model.passed_through(standing, room_id):
        route = [str(r) for r in courier.get("route") or []]
        # The door he went out by: the room after THIS one on his route,
        # which is what an observer who watched him cross actually saw.
        try:
            heading = route[route.index(str(room_id)) + 1]
        except (ValueError, IndexError):
            heading = None
        out.append({
            "courier_id": courier.get("uid"),
            "what": "%s, passing through without stopping"
                    % couriers_model.courier_voice(courier),
            "heading": heading,
            "waiting": False,
        })
    return out


def artifacts_for_room(cid, sc, room_id, inputs=None):
    """What posted notices an observer in this room registers.

    The perception half of the reading seam, `couriers_for_room`'s twin: a
    bill nobody can see is a bill nobody can read OR tear down, and both of
    those are commit-validated ops that need the `artifact_id` shown here.

    What crosses is what a glance takes in: that a notice hangs there, and
    what kind of thing it looks like. NEVER the claim and never the wording
    -- from across a square a bill is paper, and its content moves only
    through the explicit `read`, which is what keeps walking past a wall
    from broadcasting it into every mind in the room. A torn-down bill
    shows nothing at all; that silence is the feature.

    ``inputs`` as in `couriers_for_room`: the stage's shared fetch.
    """
    from story import artifacts as artifacts_model

    if not room_id:
        return []
    standing = _standing(inputs, "artifacts",
                         lambda: artifacts_model.standing_artifacts(cid))
    return [{
        "artifact_id": artifact.get("uid"),
        "what": artifacts_model.artifact_voice(artifact),
    } for artifact in artifacts_model.posted_in_room(standing, room_id)]

def _books(ctx, refresh=False):
    if refresh or ctx.get("_books") is None:
        ctx["_books"] = chat_lorebook_ids(ctx.chat.id)
    return ctx["_books"]

def _book_weights(ctx, refresh=False):
    if refresh or ctx.get("_book_weights") is None:
        ctx["_book_weights"] = chat_lorebook_weights(ctx.chat.id)
    return ctx["_book_weights"]

def lore_for(ctx):
    """The Director's lore slice: the beat's relevant entries, then the
    RULEBOOK rows the compiler rendered from typed data (`agents.mapping.
    rulebook_rows`) in the same row shape, marked `source: engine:rulebook`
    and carrying no id -- they are not entries and never enter the cache."""
    world = ctx.world_context()
    entries = world.get("relevant_lore") or []
    allowed = ("id", "entry_uid", "book_id", "keys", "content", "category",
               "locked", "overlay", "source")
    out = [{k: e.get(k) for k in allowed if k in e}
           for e in entries if isinstance(e, dict)]
    for row in world.get("rulebook") or []:
        if not isinstance(row, dict) or not row.get("text"):
            continue
        out.append({"keys": str(row.get("subject") or ""),
                    "content": str(row["text"]), "category": "mechanic",
                    "locked": True, "source": "engine:rulebook"})
    return out

def _ambient_blocked_slugs(sc, room_id):
    """Item-5 coarse nesting filter: None when the observer's room is open
    to the world (nothing to filter); otherwise the normalized ids/names of
    every room OUTSIDE their ambient scope plus the scene's location label.
    Staged lore keyed to any of those is ancestor-scoped information that
    must not reach a sealed nested observer (the port must not leak into a
    sealed elevator). Reads only scene containment (rooms/entities/derived
    dock edges) -- NEVER lorebook links: currently_within is retrieval
    bookkeeping, not perception authorization."""
    scope, open_to_world = ambient_scope(sc, room_id)
    if open_to_world:
        return None
    blocked = set()
    for rid, room in (sc.get("rooms") or {}).items():
        if rid in scope:
            continue
        slug = normalize_room_id(str(rid))
        if slug:
            blocked.add(slug)
        if isinstance(room, dict) and room.get("name"):
            slug = normalize_room_id(str(room["name"]))
            if slug:
                blocked.add(slug)
    location_slug = normalize_room_id(str(sc.get("location") or ""))
    if location_slug:
        blocked.add(location_slug)
    return blocked

def _keys_reference_blocked(keys, blocked):
    """True when any comma-separated key token names an out-of-scope room
    or the outer location (normalized, substring-tolerant for slugs long
    enough not to false-match)."""
    for token in str(keys or "").split(","):
        slug = normalize_room_id(token)
        if not slug:
            continue
        if slug in blocked:
            return True
        for b in blocked:
            if len(b) >= 5 and (b in slug or slug in b):
                return True
    return False

def _room_notes_for_view(rdata, room_id, ctx, scene=None):
    """The room's description as a MIND receives it.

    One spelling of `(the scene's own notes) or (the lore layer's)`, which six
    perceiver payloads in `agents/perception` had written out by hand -- so a
    rule taught to one of them was taught to none of the others. The rule is
    that engine bookkeeping is not world text: both sources can carry a note
    the engine wrote about its own retrieval, and neither may deliver it. See
    `story/provenance_text`.
    """
    prose = room_prose(rdata)
    if prose:
        return prose
    return _room_notes_from_lore(room_id, ctx, scene)


def room_prose(rdata):
    """The room's description as a MIND receives it, from the record alone.

    ONE SPELLING of "its `notes`, else its `desc`, else its `description`",
    for every reader that has the room record in hand. `_room_notes_for_view`
    delivers it for the room a body stands in; `perception._visible_openings`
    delivers it for a lit room seen through an open boundary -- and until
    2026-09-14 that second reader took `notes` alone, so a room the spatial
    hand had just minted with a `desc` and no `notes` arrived through the
    doorway as a bare name. Measured on chat 123 turn 9: the TARDIS door
    opened on a "vast, impossibly proportioned chamber" the hand had written
    forty words for, and the player was told "Through the third open doorway
    is TARDIS Interior." and nothing else.

    Every return runs through `strip_engine_provenance` for the reason
    `_room_notes_from_lore` gives: a description the engine wrote for a room
    it had no canon for may carry the reason it was written.
    """
    if not isinstance(rdata, dict):
        return ""
    for field in ("notes", "desc", "description"):
        text = rdata.get(field)
        if text:
            return whole_sentences(strip_engine_provenance(str(text)),
                                   ROOM_PROSE_CHARS)
    return ""


#: The most of a room's description a view carries, in characters. Named,
#: per ask-before-limiting: 60 of the 681 described rooms on the 2026-10-07
#: scratch db (8.8%) run longer, the longest 1,348.
ROOM_PROSE_CHARS = 600


def whole_sentences(text, limit):
    """`text` cut to the whole sentences that fit in `limit` characters --
    never mid-word, and never less than the first sentence, which is kept
    whole however long it is. A bare slice cut the landing stage's 655
    characters at 600 and the view read "and the open fen stretc." (scratch
    story 166, turn 4597); `_end_sentence` then gave the stump a full stop.
    Sentences are the language pack's (`split_sentences`)."""
    text = str(text or "")
    if len(text) <= limit:
        return text
    kept, pos = 0, 0
    for piece in split_sentences(text):
        piece = str(piece or "").strip()
        if not piece:
            continue
        at = text.find(piece, pos)
        if at < 0:
            break
        end = at + len(piece)
        if end > limit and kept:
            break
        kept = pos = end
        if end > limit:
            break
    return text[:kept].rstrip() if kept else text


def _room_notes_from_lore(room_id, ctx, scene=None):
    """The room's description as PROSE, for delivery to a mind -- from the
    SCENE, which is the record of a room.

    The name is historical: until 2026-09-03 this fell through to the lore
    layer, where every described room had been filed as a `layout` entry --
    a second representation of the scene kept so a model stage could
    retrieve it. That filing is retired (`persist/commit_mapping`), so the
    room's own `notes`, else its `desc`/`description`, is the whole answer;
    a room the scene does not describe has no notes, and nobody invents any.

    Every return runs through `strip_engine_provenance`: a description the
    engine wrote for a room it had no canon for may carry the reason it was
    written, and that reason is bookkeeping, not a fact about the room. See
    `story/provenance_text` for the measurement.
    """
    if not room_id:
        return ""
    sc = scene if scene is not None else get_scene(ctx.chat.id, ctx.chat)
    return room_prose((sc.get("rooms") or {}).get(room_id))
