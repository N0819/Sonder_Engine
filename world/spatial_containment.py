# spatial_containment.py
"""Relative scale and enclosure: how big a body is, what encloses it, what that
hides, and what a size change breaks."""

from world.spatial_barriers import (_PASSABLE_BARRIERS, neighbor_map,
                                    normalize_barrier)
from world.spatial_identity import _ci_get, _entity_named, room_of, same_subject
from world.spatial_identity import _unique_entity_keyed, normalize_room_id
from world.spatial_transit import (_interior_entry_room, _interior_rooms_of,
                                  _is_body_entity)


# Entity kinds that are never anywhere within a room, because they are things
# a body is at, holds, or rides. Every other kind -- including the free-text
# species names models write -- reads as a body.
_NEVER_STATIONED_KINDS = frozenset({
    "object", "item", "fixture", "furniture", "container", "portal", "tool",
    "structure", "vehicle", "decor", "decoration", "artifact", "feature",
    "technology", "bedding", "flora", "location", "group",
})


# ---------------------------------------------------------------------------
# SCALE -- how big each body currently is, relative to its own baseline.
#
# A shrink or a growth is live physical state, so it lives in the scene blob
# with positions, stations and contacts rather than in a condition row: the
# things that must react to it (what can be reached, lifted, held, or gripped
# at all) are scene-level questions, and keeping them in one place is what
# stops the two accounts drifting.
#
# Absent means 1.0, so a scene that never mentions size behaves exactly as
# before -- the same fail-open the awareness gate uses.
_MIN_SCALE = 0.001            # a body reduced past this is a speck, not a body
_MAX_SCALE = 1000.0
# A change smaller than this is a growth spurt, not a reconfiguration: it does
# not break holds. Beyond it, the geometry that made a contact true is gone.
_SCALE_CONTACT_BREAK = 1.25
_MAX_SCALES = 40

# One body fits in the other's hand below this ratio. ONE constant, because
# this boundary is stated in three places that must agree: the `tiny` size
# tier, `fits_in_other_hand`, and its mirror seen from the larger body -- which
# `size_facts` used to hardcode as `>= 6.7` while 1/0.15 is 6.67.
_HAND_HELD_RATIO = 0.15

# Ordered small -> large. The boundary is the RATIO to baseline, and the label
# is what a prompt and a narrator can actually use.
_SIZE_TIERS = (
    # 'tiny' shares its boundary with fits_in_other_hand below, so the label
    # and the capability agree: tiny IS "small enough to be held in a hand".
    (_HAND_HELD_RATIO, "tiny"),
    (0.5, "small"),
    (2.0, "comparable"),
    (20.0, "large"),
    (float("inf"), "huge"),
)


def clamp_scale(value):
    """A usable scale factor, or None when the value says nothing.

    Junk degrades to None (treated as baseline) rather than to a number, so a
    malformed declaration can never silently shrink someone.
    """
    try:
        factor = float(value)
    except (TypeError, ValueError):
        return None
    if factor != factor or factor in (float("inf"), float("-inf")):
        return None
    if factor <= 0:
        return None
    return max(_MIN_SCALE, min(factor, _MAX_SCALE))


def scale_of(scene: dict, name: str) -> float:
    """`name`'s current size relative to its own baseline. 1.0 when unstated."""
    scales = (scene or {}).get("scales") or {}
    if not isinstance(scales, dict):
        return 1.0
    return clamp_scale(_ci_get(scales, name)) or 1.0


def size_tier(factor) -> str:
    factor = clamp_scale(factor) or 1.0
    for bound, label in _SIZE_TIERS:
        if factor < bound:
            return label
    return "huge"


def normalize_scene_scales(scene: dict) -> dict:
    """Scale hygiene, run at merge.

    Clamps what is there and removes anything back at baseline, so "restored to
    normal" is expressed by setting 1.0 and leaves no residue behind.

    Deliberately NOT pruned by position, unlike contacts. A contact genuinely
    requires two bodies in one room; a size does not. Someone shrunk who steps
    offscreen for a scene is still shrunk when they return, and dropping the
    entry would silently restore them.
    """
    scales = scene.get("scales")
    if not isinstance(scales, dict):
        if scales is not None:
            scene["scales"] = {}
        return scene

    cleaned = {}
    for name, raw in scales.items():
        label = str(name or "").strip()
        if not label:
            continue
        factor = clamp_scale(raw)
        if factor is None or factor == 1.0:
            continue
        cleaned[label] = factor

    # Bounded so a runaway model cannot grow this without limit; a scene with
    # more than this many transformed bodies at once has other problems.
    if len(cleaned) > _MAX_SCALES:
        cleaned = dict(list(cleaned.items())[-_MAX_SCALES:])

    scene["scales"] = cleaned
    return scene


def scale_ratio(scene: dict, a: str, b: str) -> float:
    """How many times bigger `a` currently is than `b`."""
    other = scale_of(scene, b)
    return scale_of(scene, a) / other if other else 1.0


def size_relation(scene: dict, a: str, b: str) -> dict:
    """What `a`'s size permits against `b`, as deterministic ground truth.

    The Director owns whether an act succeeds; this only reports the geometry
    it should reason from, so "she is too small to reach the latch now" comes
    from a number rather than from vibes. Thresholds are deliberately coarse --
    fiction does not need a physics engine, it needs the difference between
    'comparable', 'can be picked up', and 'cannot be reached at all'.
    """
    ratio = scale_ratio(scene, a, b)
    return {
        "actor": a,
        "other": b,
        "ratio": round(ratio, 4),
        "actor_tier": size_tier(scale_of(scene, a)),
        "other_tier": size_tier(scale_of(scene, b)),
        # Lifting something roughly your own size is a feat; twice your size is
        # not happening without leverage the fiction has to supply.
        "can_lift_other": ratio >= 2.0,
        "can_be_lifted_by_other": ratio <= 0.5,
        # Small enough to be carried in one hand rather than hoisted, and the
        # SAME boundary seen from the other side. Both derived from one
        # constant: `size_facts` used to hardcode the inverse as `>= 6.7`
        # (1/0.15 is 6.67), so the two halves of one rule could drift apart.
        "fits_in_other_hand": ratio <= _HAND_HELD_RATIO,
        "other_fits_in_actors_hand": ratio >= 1 / _HAND_HELD_RATIO,
        # A body this much smaller cannot reach past the other's feet unaided,
        # nor act on anything at their head height.
        "can_reach_other_upper_body": ratio > 0.25,
        "can_be_stepped_over_by_other": ratio <= 0.34,
        # Fine work needs a hand roughly proportionate to what it works on. Too
        # large and a fingertip is broader than the thing being reached for, so
        # the act is not clumsy but impossible; too small and there is no
        # purchase. Precision is the first capability a size gap takes away,
        # well before reach or lifting.
        "can_do_fine_work_on_other": 0.25 <= ratio <= 4.0,
    }


def detail_resolves_between(scene: dict, observer: str, target: str) -> bool:
    """Can this observer resolve TEXTURE on that body, or only its form.

    ACUITY IS PROPORTIONALITY, not distance. A body far off its counterpart's
    scale reads as form and mass and never as texture -- the larger observer
    is above the detail, the smaller one is inside it, and neither is reading
    a REGION as a surface. Symmetric on purpose, which is why the band is
    taken from `can_do_fine_work_on_other` rather than a fresh constant: that
    band is already the engine's declared precision boundary, and the hand and
    the eye must not drift apart.

    True whenever nothing is off baseline, and a body is always proportionate
    to itself, so the self row can never be coarsened.
    """
    return bool(size_relation(scene, observer, target)["can_do_fine_work_on_other"])


def size_facts(scene: dict, observer: str, source_names) -> list:
    """Plain statements about relative size, for the observer's frame.

    Only emitted when someone is actually off-baseline: a scene of ordinary
    people generates nothing, exactly as before.
    """
    scales = scene.get("scales") or {}
    if not isinstance(scales, dict) or not scales:
        return []

    facts = []
    own = scale_of(scene, observer)
    if own != 1.0:
        facts.append(
            f"You are {size_tier(own)} right now — about "
            f"{_scale_phrase(own)} your normal size."
        )
    for name in source_names or []:
        if not name or name == observer:
            continue
        factor = scale_of(scene, name)
        if factor == 1.0 and own == 1.0:
            continue
        rel = size_relation(scene, observer, name)
        if 0.75 <= rel["ratio"] <= 1.34:
            continue  # near enough the same size to need no saying
        if rel["ratio"] < 1:
            clause = f"{name} towers over you"
            if rel["fits_in_other_hand"]:
                clause = f"{name} could close a hand around you"
            elif rel["can_be_lifted_by_other"]:
                clause = f"{name} could pick you up"
        else:
            clause = f"you tower over {name}"
            if rel["other_fits_in_actors_hand"]:
                clause = f"{name} could fit in your hand"
            elif rel["can_lift_other"]:
                clause = f"you could pick {name} up"
        facts.append(clause + ".")
    return facts


def _scale_phrase(factor):
    if factor >= 1:
        return f"{factor:g}x"
    return f"1/{round(1 / factor):g} of"


# ---------------------------------------------------------------------------
# CONTAINMENT -- being carried, pocketed, jarred, or ridden along.
#
# The sibling of scale, and the reason it exists: a body shrunk to a tenth and
# picked up is not merely "in contact with" the hand holding it. It has stopped
# being an independently positioned thing. Contact alone left the tiny person
# free to walk out of the room while sitting in someone's pocket, because
# nothing tied their position to their container's.
#
# So a contained body's position is DERIVED, every merge, from whatever holds
# it -- transitively, so a person in a jar in a satchel goes where the satchel
# goes. Getting out is an explicit act the Director declares by releasing the
# containment, exactly like letting go of a hold; it is never a side effect of
# writing a position, because "they walked away" and "the Director forgot they
# were in a pocket" produce the identical diff and only one of them is meant.
#
# Interior rooms remain the mechanism for large containers you stand INSIDE (a
# ship, a building). This is for the other direction: a container that carries
# you as cargo.
_MAX_CONTAINED = 40
CONTAINMENT_MODES = (
    "held", "carried", "pocket", "container", "riding", "mounted", "worn",
    # A body inside another body's own interior -- a mouth, a coil, a pouch.
    # Named rather than left to the unknown-reads-as-enclosed fallback so it
    # is a member of the vocabulary a reader can look up, and so the mode a
    # derivation writes is never mistaken for one a model reached outside the
    # list to invent.
    "interior",
)


def _clean_containment(raw, subject):
    if isinstance(raw, str):
        raw = {"in": raw}
    if not isinstance(raw, dict):
        return None
    holder = str(raw.get("in") or raw.get("container") or "").strip()
    if not holder or holder.casefold() == str(subject or "").strip().casefold():
        return None
    mode = str(raw.get("mode") or "").strip().casefold() or "carried"
    return {"in": holder, "mode": mode}


def container_of(scene: dict, name: str):
    """What is carrying `name`, or None."""
    contained = (scene or {}).get("contained") or {}
    if not isinstance(contained, dict):
        return None
    record = _ci_get(contained, name)
    if not isinstance(record, dict):
        return None
    return record.get("in") or None


def carrier_chain(scene: dict, name: str) -> list:
    """Every container above `name`, outermost last. Cycle-safe."""
    chain = []
    seen = {str(name or "").strip().casefold()}
    current = container_of(scene, name)
    while current:
        key = str(current).strip().casefold()
        if key in seen:
            break
        seen.add(key)
        chain.append(current)
        current = container_of(scene, current)
    return chain


def contents_of(scene: dict, container: str) -> list:
    """Everything `container` is directly carrying."""
    target = str(container or "").strip().casefold()
    if not target:
        return []
    contained = (scene or {}).get("contained") or {}
    if not isinstance(contained, dict):
        return []
    out = []
    for name, record in contained.items():
        if isinstance(record, dict) and \
                str(record.get("in") or "").strip().casefold() == target:
            out.append(name)
    return sorted(out)


# Being carried in the open and being carried INSIDE something are not the same
# fact, and nothing in the containment record distinguished them: a body in a
# pocket and a body in an open palm were equally visible to the room, because a
# carried body's position derives to its carrier's room and `same_room` answers
# sight before anything else gets a say. Interior rooms have had `enclosure` to
# settle this for a while; the carry path had no equivalent at all.
#
# These five are the documented ways a body is carried IN VIEW. Everything else
# -- the enclosed half of the vocabulary, or a mode the Director reached outside
# it to name -- puts the body inside something. Unknown reads as enclosed on
# purpose: the open cases are exactly this list, so a mode the engine cannot
# vouch for must not be the one that grants sight. Under-sharing is the safe
# failure for an engine whose whole promise is that nothing is known unless it
# was legitimately perceived. An ABSENT mode still defaults to "carried" in
# _clean_containment, so the ordinary carry keeps behaving exactly as before.
_OPEN_CONTAINMENT_MODES = frozenset({
    "held", "carried", "riding", "mounted", "worn",
})


def derive_containment_from_contacts(scene: dict) -> list:
    """A whole body inside another's interior IS containment. Record it.

    THE LEDGERS DISAGREED AND THE GATE READ THE EMPTY ONE. `contained` is what
    `containment_conceals` consults, and its rule is already exactly right --
    "something carried inside a body is not seen BY that body either... what
    it has instead of sight is touch". Nothing derived it from the contact
    ledger, so an enclosure the Director expressed as an interior CONTACT
    concealed nothing at all.

    Measured, chat 86 t49-t50: the contact specialist wrote
    `containment: {"Hinami": null}` -- explicitly releasing the record -- and
    expressed the same enclosure as `contact_ops` instead. From that beat the
    scene held a body at rest inside a mouth in one ledger and nobody inside
    anything in the other, and the enclosing body's view carried the enclosed
    one's full appearance region by region, down to "barely visible
    copper-gold hair on her shins". The touch channel beside it was correct
    and vivid throughout: the enclosure was modelled, just not for sight.

    THE WHOLE BODY, NOT A PART. A tongue against a torso inside a mouth is
    contact within an enclosure and says nothing about who is enclosed; a
    body with no part named, or the part `body` itself, is the enclosed
    party. That distinction is the whole rule, and it is the one that keeps a
    hand in a pocket from making its owner a pocket's contents.

    NEVER OVERRIDES AN EXISTING RECORD. Containment stays authoritative --
    `_contained_inversion` already defers to it on exactly that ground -- so
    this only fills a gap. A body the scene says is `held` in the open stays
    held and stays visible.

    Returns the subjects it recorded, for the caller's report.
    """
    contacts = (scene or {}).get("contacts")
    if not isinstance(contacts, list) or not contacts:
        return []
    contained = scene.setdefault("contained", {})
    if not isinstance(contained, dict):
        contained = scene["contained"] = {}
    minted = []
    for row in contacts:
        if not isinstance(row, dict):
            continue
        if str(row.get("relation") or "").strip().casefold() != "interior":
            continue
        if not str(row.get("target_interior") or "").strip():
            continue
        actor = str(row.get("actor") or "").strip()
        holder = str(row.get("target") or "").strip()
        if not actor or not holder:
            continue
        if actor.casefold() == holder.casefold():
            continue
        part = str(row.get("actor_part") or "").strip().casefold()
        enclosed, container = actor, holder
        if part and part not in _WHOLE_BODY_PARTS:
            # THE OTHER SPELLING, and it is the commoner one. The row above
            # says "this body, inside that one" and names the enclosed party
            # in the actor slot. This one says "my part touches your part, in
            # a cavity" -- `Mirelle.tongue -> Hinami.torso, interior, mouth`
            # -- and names NEITHER party as the enclosed one. `target_interior`
            # does not settle it either: in the first spelling the cavity
            # belongs to the target, in this one it belongs to the actor, and
            # the row carries nothing that says which.
            #
            # NOT SETTLED BY ANATOMY. `tongue` is not in
            # `_ENCLOSING_PART_CAVITY` and should not be added to it -- that
            # table is parts that ARE cavities, and a table of parts that
            # RESIDE in cavities would be default anatomy, which this engine
            # deliberately enumerates nowhere.
            #
            # NOT SETTLED BY A SCALE THRESHOLD EITHER, measured: the live
            # scene carries 0.25 for a body its own prose calls three inches
            # (~0.05), so `other_fits_in_actors_hand` is False for a body
            # being held in a palm. A threshold read off a wrong number is a
            # wrong answer with a confident shape.
            #
            # WHAT DOES SETTLE IT is the asymmetry, which survives the
            # magnitude being wrong: one of these bodies can lift the other
            # and cannot be lifted by it. That is the enclosing one, at 4x and
            # at 20x alike. Where the scene gives no asymmetry -- two
            # comparable bodies -- this abstains rather than guessing, and the
            # explicit spelling above remains the way to say it.
            enclosed, container = _enclosed_by_asymmetry(scene, actor, holder)
            if not enclosed:
                continue
        if _ci_get(contained, enclosed) is not None:
            continue
        contained[enclosed] = {"in": container, "mode": "interior"}
        minted.append(enclosed)
    return minted


def _enclosed_by_asymmetry(scene, a, b):
    """Which of two bodies an interior relation must enclose, or (None, None).

    Uses the engine's own size relation rather than a raw ratio: the question
    is not "how much smaller" but "can one of these lift the other and not the
    reverse", which stays true when the magnitude on the ledger is wrong.
    """
    forward = size_relation(scene, a, b)
    if forward.get("can_lift_other") and not forward.get("can_be_lifted_by_other"):
        return b, a
    if forward.get("can_be_lifted_by_other") and not forward.get("can_lift_other"):
        return a, b
    return None, None


#: The ways a contact names the WHOLE body rather than a part of it. An empty
#: `actor_part` is the same claim -- the enclosed side named no part because
#: there is no part to name.
_WHOLE_BODY_PARTS = frozenset({"body", "whole body", "self", "form"})


def containment_hides(mode) -> bool:
    """Does being carried this way put a body out of the room's sight."""
    return str(mode or "").strip().casefold() not in _OPEN_CONTAINMENT_MODES


def _body_interior_holder(scene: dict, name: str):
    """The body whose INSIDE `name` is currently standing in, if any.

    A scene can express one body being inside another two ways. The
    `contained` ledger is one: an explicit record that a body is held in
    something. The other is a room -- an interior space parented to a body,
    which the occupant simply has as their position, exactly like any other
    room.

    Only the ledger was ever consulted, so the room form concealed nothing.
    A body fully inside another read as an ordinary occupant of an ordinary
    adjacent room: `containment_conceals` returned False in both directions,
    which left the observer outside with a sight channel to them and left the
    body inside with no touch channel to the body around it -- seen when they
    should not be, and not felt when they should be.

    A parent that holds a POSITION is a body; a parent that does not is a bag,
    a ship, a jar -- already handled by `_is_carried_interior` for a different
    question (whether you take its inside in as ambience).

    BOTH FORMS ARE READ HERE, and for a long time only the room one was, which
    made `inside_source` dead for every enclosure the Director expressed as a
    ledger record -- which is how it expresses nearly all of them. The symptom
    was not subtle once measured: a body sealed inside another read

        {"same_room": false, "barrier": "separated", "distance": "far"}

    against the very body around it -- the same relation the engine returned
    for a window across the room. So the one voice they were physically
    closest to in the world arrived through a wall, and the enclosure they
    were inside smelled exactly as much as the window did.

    Concealment did work, because `_hiding_holders` reads the ledger. That is
    the shape of the defect: an enclosed body got every consequence of being
    sealed away and none of the compensations, because the two halves of one
    fact were answered by two functions and only one of them had been taught
    the common case.
    """
    rooms = (scene or {}).get("rooms") or {}
    positions = (scene or {}).get("positions") or {}
    room_id = _ci_get(positions, name)
    room = rooms.get(room_id) if room_id else None
    if isinstance(room, dict):
        parent = str(room.get("parent_entity") or "").strip()
        if (parent and room_of(scene, parent) is not None
                and parent.casefold() != str(name or "").strip().casefold()):
            return parent
    # The ledger form. `mode` decides: being carried in an open palm is not
    # being inside anything, and `containment_hides` is already the engine's
    # answer to which modes enclose.
    contained = (scene or {}).get("contained") or {}
    record = _ci_get(contained, name) if isinstance(contained, dict) else None
    if not isinstance(record, dict):
        return None
    holder = str(record.get("in") or "").strip()
    if not holder or not containment_hides(record.get("mode")):
        return None
    if holder.casefold() == str(name or "").strip().casefold():
        return None
    # A BODY, not a bag. `inside_source` means the enclosure is a MASS -- it
    # conducts sound and floods every other scent -- and a crate is neither.
    # Positive evidence required, via the discriminator the enclosure default
    # already uses (`_is_body_entity`: bodies wear things and have a size), so
    # an undeclared holder stays a container. Opaque is not soundproof, and a
    # box you can be heard through must not become one. An unplaced holder
    # names nothing the scene can reason about at all.
    entity = _entity_named(scene, holder)
    if str((entity or {}).get("kind") or "").strip().casefold() \
            in _NEVER_STATIONED_KINDS:
        return None
    if not _is_body_entity(scene, holder, entity):
        return None
    if room_of(scene, holder) is None:
        return None
    return holder


def _hiding_holders(scene: dict, name: str) -> list:
    """Holders that conceal `name`, innermost first. Cycle-safe."""
    contained = (scene or {}).get("contained") or {}
    if not isinstance(contained, dict):
        contained = {}
    out = []
    current = name
    seen = {str(name or "").strip().casefold()}
    while True:
        holder = None
        record = _ci_get(contained, current)
        if isinstance(record, dict) and record.get("in"):
            if not containment_hides(record.get("mode")):
                # Carried in the open: not a hiding holder, but keep walking
                # the chain -- its own holder may still be one.
                holder = record.get("in")
                key = str(holder).strip().casefold()
                if key in seen:
                    break
                seen.add(key)
                current = holder
                continue
            holder = record.get("in")
        else:
            holder = _body_interior_holder(scene, current)
        if not holder:
            break
        key = str(holder).strip().casefold()
        if key in seen:
            break
        seen.add(key)
        out.append(holder)
        current = holder
    return out


def hiding_holders_of(scene: dict, name: str) -> list:
    """Public form of `_hiding_holders` -- the enclosures around one body,
    innermost first, whether expressed as a `contained` record or as a
    body-parented interior room. Read it rather than `scene['contained']`
    directly, or the room form is invisible to the caller."""
    return list(_hiding_holders(scene, name))


def _innermost_hiding_holder(scene: dict, name: str):
    """The nearest enclosure `name` is shut inside, or None if in the open."""
    holders = _hiding_holders(scene, name)
    return str(holders[0]).strip().casefold() if holders else None


def _shares_enclosure(scene: dict, holder, target: str) -> bool:
    """Is `target` inside the same enclosure the perceiver is inside?

    Two bodies in one enclosure are simply in the same place -- nothing is
    between them and the wall around them is around them both.
    """
    if not holder:
        return False
    return same_subject(scene, _innermost_hiding_holder(scene, target) or "",
                        holder)


def containment_conceals(scene: dict, observer: str, target: str) -> bool:
    """Is sight between these two blocked by an enclosure around either.

    Sight needs both parties on the SAME side of every closed thing, so the
    test is that their nearest enclosure matches. Being shut inside something
    blocks the view out exactly as it blocks the view in -- a body in a closed
    bag can no more watch the room than the room can watch it, and that
    direction is the easier one to forget.

    The holder itself is not exempt. Something carried inside a body is not
    seen BY that body either: the holder is not inside its own enclosure, so
    the two do not match, and what it has instead of sight is touch. Two
    bodies inside the same enclosure do match, and see each other normally.
    """
    return (_innermost_hiding_holder(scene, observer)
            != _innermost_hiding_holder(scene, target))


def normalize_scene_containment(scene: dict) -> dict:
    """Containment hygiene, run at merge.

    Drops a record whose container has left the scene, and any record that
    would make a body contain itself directly or through a chain -- a cycle
    would otherwise make position derivation unresolvable.
    """
    contained = scene.get("contained")
    if not isinstance(contained, dict):
        if contained is not None:
            scene["contained"] = {}
        return scene

    positions = scene.get("positions") or {}
    entities = scene.get("entities") or {}

    # Who the scene knows about, folded once for the whole pass. This was
    # three probes per record -- a `_ci_get` over positions, a case-SENSITIVE
    # `holder not in entities`, and a case-insensitive repeat of that one
    # built by materialising a fresh `{k: 1 for k in entities}` dict every
    # time round the loop. The middle probe was subsumed by the third, and the
    # third's dict was thrown away unused; `_ci_get` itself is a linear scan,
    # so the per-record cost was O(records x scene).
    def _fold(key):
        return str(key).lower().strip()

    known = {_fold(k) for k in entities}
    # A position of None names no room -- which is not the same as being in
    # the scene, and `_ci_get(positions, holder) is None` did not count it.
    known.update(_fold(k) for k, v in positions.items() if v is not None)

    cleaned = {}
    for name, raw in contained.items():
        subject = str(name or "").strip()
        if not subject:
            continue
        record = _clean_containment(raw, subject)
        if record is None:
            continue
        # The container must be something the scene actually knows about.
        if _fold(record["in"]) not in known:
            continue
        cleaned[subject] = record

    scene["contained"] = dict(list(cleaned.items())[-_MAX_CONTAINED:])

    # Break cycles: walk each chain and drop the record that closes a loop.
    for subject in list(scene["contained"]):
        seen = {subject.strip().casefold()}
        current = scene["contained"][subject]["in"]
        while current:
            key = str(current).strip().casefold()
            if key in seen:
                scene["contained"].pop(subject, None)
                break
            seen.add(key)
            record = _ci_get(scene["contained"], current)
            current = record.get("in") if isinstance(record, dict) else None

    return scene


def derive_contained_positions(scene: dict) -> dict:
    """Put every contained body where its container is.

    This is what makes containment mean something: the position is not the
    contained body's to set. A tiny person in a pocket goes where the pocket
    goes and cannot be somewhere else, which is precisely what contact alone
    could not express.
    """
    contained = scene.get("contained")
    if not isinstance(contained, dict) or not contained:
        return scene
    positions = scene.get("positions")
    if not isinstance(positions, dict):
        return scene

    for subject in contained:
        room = None
        # Resolve against the OUTERMOST carrier, not the nearest one. An
        # intermediate container's own position is derived too, and may not
        # have been updated yet this pass -- reading it would hand the innermost
        # body a stale room while the satchel it is in has already moved.
        for holder in reversed(carrier_chain(scene, subject)):
            # Through entity identity, not spelling: a record naming the
            # carrier by entity id must still find a positions map keyed by
            # that entity's display name, or this silently skips and leaves
            # the contained body wherever it happened to be -- which, when the
            # Director wrote the carrier's id into `positions` as though it
            # were a room, is a room that does not exist.
            room = room_of(scene, holder)
            if room is not None:
                break
        if room is None:
            continue
        # Write under the key already in use, so this never mints a second
        # spelling of a name that positions already carries.
        _positions_write(positions, subject, room)
    return scene


def _positions_write(positions: dict, subject: str, room: str) -> None:
    """Set a position under the spelling `positions` already uses for this
    subject, minting the given one only when it holds none. The same rule
    `derive_contained_positions` follows, and for the same reason: a second
    spelling of one being is a ledger that disagrees with itself."""
    folded = str(subject or "").strip().casefold()
    for key in list(positions):
        if str(key).strip().casefold() == folded:
            positions[key] = room
            return
    positions[subject] = room


# ---------------------------------------------------------------------------
# PLACEMENT DERIVED FROM THE TRANSFER LEDGER.
#
# An entity's room is `scene["positions"][id]` and nothing else -- there is no
# `room` field on the entity record and no room column on its durable
# projection. So a thing is somewhere only if some hand wrote a position for
# it, and the hand that MINTS things cannot: `entities` belongs to the objects
# specialist, `positions` to the spatial specialist, the two run in parallel on
# disjoint scopes, and a `positions` key emitted by the objects specialist is
# dropped by validation before assembly ever sees it -- silently, with no
# `outside_scope` note.
#
# Measured over every active Director variant on disk: the single-hand
# `director_establish` places 96.5% of what it mints (278/288); the monolithic
# `director_resolve` placed 35.7% (752/2108); the orchestrated fan-out places
# 5.8% (85/1465), and 78 of those 85 are bodies that also carry an entity
# record. Genuine non-body objects placed by the fan-out across the whole live
# corpus: about seven. The split is structural, not a model failure.
#
# The evidence to place them was written anyway, by the right hand, on the
# right beat, into a channel with no reader. Two instrumented runs, 67 objects
# calls, zero `positions` keys emitted -- and placements like
#     {"op": "place", "object_id": "<a thing>", "from_id": "<a body>",
#      "to_id": "<a room>", "relation": "on"}
# sitting in `inventory_ops`, which nothing in persist/ or world/ consumed.
#
# This is the same move `derive_scene_stations` makes and states outright: the
# ledger the models DO maintain seeds the one they do not. It is a projection,
# never a decider -- it refuses everything it cannot resolve against the scene
# the merge already holds, so an unresolvable destination leaves the thing
# exactly as unplaced as it is today.


def resolve_placement_target(scene: dict, to_id):
    """What a transfer's destination refers to, resolved against the scene.

    Returns one of:
      ("room", room_id)   -- a place; the subject stands in it.
      ("carrier", holder) -- a BODY; the subject is carried, and where it then
                             is follows from where the holder is.
      ("anchor", key)     -- something else the scene already places; the
                             subject is in that thing's room, at it.
      (None, None)        -- nothing the scene can vouch for. REFUSED.

    The refusal is the point. A destination is variously a room id, a body's
    display name, a bare noun the fiction invented for a surface, or null, and
    writing an unresolvable token into `positions` is precisely the category
    error `repair_entity_positions` exists to clean up afterwards. Better to
    leave a thing unplaced than to place it nowhere-shaped.

    Body-ness is derived, never read off a label: `_is_body_entity` asks
    whether the thing wears something or has a size relative to its own
    baseline, because `kind` is free text a model writes (577 kinds outside
    the known set across the corpus, `character`, `succubus` and `furniture`
    among the most common).
    """
    text = str(to_id or "").strip()
    if not text:
        return (None, None)

    rooms = (scene or {}).get("rooms") or {}
    if isinstance(rooms, dict) and rooms:
        if text in rooms:
            return ("room", text)
        folded = text.casefold()
        for rid, room in rooms.items():
            if str(rid).strip().casefold() == folded:
                return ("room", rid)
            if isinstance(room, dict) and \
                    str(room.get("name") or "").strip().casefold() == folded:
                return ("room", rid)
        slug = normalize_room_id(text)
        if slug and slug in rooms:
            return ("room", slug)

    eid, entity = _unique_entity_keyed(scene, text)
    if eid:
        if _is_body_entity(scene, eid, entity):
            return ("carrier", eid)
        # A thing, not a body: the engine's vocabulary for being AT a thing
        # rather than inside it is a station, and the room is the thing's own.
        # A thing that is itself nowhere anchors nothing.
        return ("anchor", eid) if room_of(scene, eid) is not None \
            else (None, None)

    # A subject the scene places but keeps no entity record for -- a registered
    # cast member is the common case. Body evidence decides which of the two
    # remaining readings applies.
    if room_of(scene, text) is not None:
        if _is_body_entity(scene, text, None):
            return ("carrier", text)
        return ("anchor", text)
    return (None, None)


def _placement_subject_key(scene: dict, eid: str, entity) -> str:
    """The spelling the scene's ledgers already use for this entity, else its
    id.

    One being, one key. `positions` is keyed by whatever the writer reached
    for -- id, display name, alias -- and minting a second spelling here would
    put the same thing in two rooms at once, which is the exact defect
    `_dedup_duplicate_position_keys` exists to undo one layer up.
    """
    labels = [eid]
    if isinstance(entity, dict):
        labels.append(entity.get("name"))
        labels.extend(entity.get("aliases") or [])
    ledgers = [(scene or {}).get("positions"), (scene or {}).get("contained")]
    for label in labels:
        text = str(label or "").strip()
        if not text:
            continue
        for ledger in ledgers:
            if not isinstance(ledger, dict):
                continue
            for key in ledger:
                if str(key).strip().casefold() == text.casefold():
                    return key
    return eid


def derive_inventory_placements(scene: dict, inventory_ops,
                                *, declared=()) -> list:
    """Place what a transfer op moved, from the ledger the objects hand fills.

    THREE RULES, ALL SUBTRACTIVE:

    1. A destination that does not resolve against the scene writes nothing.
       `resolve_placement_target` is the whole of that judgment.
    2. A destination that resolves to a BODY writes a CARRIER RELATION, never
       a position. Reading "handed to someone" as "in that room" is the one
       real information expansion available here -- it would make a pocketed
       thing nameable by everyone standing nearby. The relation instead lets
       `derive_contained_positions` put it where the holder is while
       `hiding_holders_of` keeps it out of sight if the holder pocketed it.
       The op's own `relation` word becomes the containment mode verbatim and
       is normalized by `_clean_containment`, so the ledger keeps ONE default
       rather than growing a second, competing one; every mode outside
       `_OPEN_CONTAINMENT_MODES` conceals, which is the safe direction for a
       word the engine cannot vouch for.
    3. A null or blank endpoint is SILENCE, never an erasure -- the standing
       `_merge_entity` doctrine. Nothing is unplaced by this pass.

    The `op` verb is deliberately not read at all. Where a thing ENDED UP is
    the only question here, and a verb vocabulary would reject the words the
    fiction actually reaches for (465 barrier words and 577 entity kinds
    outside their known sets, measured, are what that costs).

    `declared` is the set of subject spellings a hand placed by name in this
    beat's own diff. An explicit write always outranks a derivation, which is
    also what keeps this from re-opening the ownership race the fan-out exists
    to prevent: the spatial specialist still owns `positions` and the contact
    specialist still owns `containment`; this speaks only where they did not.

    Returns [(subject, kind, destination)] for the caller's report; mutates.
    """
    if not isinstance(inventory_ops, list) or not inventory_ops:
        return []
    entities = (scene or {}).get("entities")
    if not isinstance(entities, dict) or not entities:
        return []
    positions = scene.get("positions")
    if not isinstance(positions, dict):
        positions = scene["positions"] = {}
    spoken_for = {str(name).strip().casefold()
                  for name in (declared or []) if str(name).strip()}

    placed = []
    for op in inventory_ops:
        if not isinstance(op, dict):
            continue
        eid, entity = _unique_entity_keyed(scene, op.get("object_id"))
        if not eid or not isinstance(entity, dict):
            continue          # not a thing this scene knows: place nothing
        if entity.get("ubiquitous"):
            continue          # a bodiless voice is nowhere by definition
        labels = {str(eid).strip().casefold(),
                  str(entity.get("name") or "").strip().casefold()}
        labels |= {str(a).strip().casefold()
                   for a in (entity.get("aliases") or [])}
        if labels & spoken_for:
            continue          # a hand placed it by name; the derivation yields
        kind, destination = resolve_placement_target(scene, op.get("to_id"))
        if not kind:
            continue
        subject = _placement_subject_key(scene, eid, entity)
        folded_subject = subject.strip().casefold()
        if kind == "carrier":
            if str(destination).strip().casefold() == folded_subject:
                continue
            record = _clean_containment(
                {"in": destination, "mode": op.get("relation")}, subject)
            if record is None:
                continue
            # An interior is a PLACE, with rooms minted for it and bodies
            # moved into it. A transfer op is evidence of carriage and never
            # of that, so the one mode that would trigger it is not derivable
            # here; the thing is inside something, and that is all this says.
            if record["mode"] == "interior":
                record["mode"] = "container"
            contained = scene.setdefault("contained", {})
            if not isinstance(contained, dict):
                continue
            for key in [k for k in contained
                        if str(k).strip().casefold() == folded_subject]:
                contained.pop(key, None)
            contained[subject] = record
        else:
            room = destination if kind == "room" \
                else room_of(scene, destination)
            if not room:
                continue
            # Set down: a thing that has reached a place is no longer being
            # carried, and leaving the record would drag it back to its old
            # holder's room on the next derivation.
            contained = scene.get("contained")
            if isinstance(contained, dict):
                for key in [k for k in contained
                            if str(k).strip().casefold() == folded_subject]:
                    contained.pop(key, None)
            _positions_write(positions, subject, room)
            # DELIBERATELY NO STATION. Being set down ON a thing is a within-
            # room fact, and `normalize_scene_stations` blanks any `at` that is
            # not one of the room's own declared anchors -- so a station
            # written here would be erased later in this same merge and read,
            # from every caller, as a field nothing honours. The room is what
            # this ledger can prove; `derive_scene_stations` owns the rest.
        placed.append((subject, kind, destination))
    return placed


def _declared_interior_region(scene: dict, occupant: str, holder: str) -> str:
    """The region of `holder` a standing interior CONTACT says `occupant` is
    in, or "". One definition, read by two callers.

    `_interior_station_hint` asks it to pick WHICH existing interior room the
    occupant lands in; `materialize_enclosure_interiors` asks it to NAME the
    room it is about to mint. Both are the same question -- which region of
    this body does the ledger already say the other one is inside -- and it
    had two answers only because the second caller did not exist yet.

    THE FIRST STANDING ROW WINS, as it did when this lived inside the hint:
    two interior rows naming different regions for one pair is the ledger
    disagreeing with itself, and no fact in the scene decides which is right,
    so the answer is the one the scene lists first.
    """
    for row in (scene or {}).get("contacts") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("relation") or "").strip().casefold() != "interior":
            continue
        station = str(row.get("target_interior") or "").strip()
        if not station:
            continue
        pair = {str(row.get("actor") or "").strip().casefold(),
                str(row.get("target") or "").strip().casefold()}
        if not ({str(occupant or "").strip().casefold(),
                 str(holder or "").strip().casefold()} <= pair):
            continue
        return station
    return ""


def _interior_station_hint(scene: dict, occupant: str, holder: str,
                           interior_ids: list):
    """The interior room a standing interior CONTACT already names, or None.

    An interior relation carries `target_interior` -- the region of the
    holder the contact is inside. Once that holder's inside is rooms, the
    region and the room are the same fact under two names, so the ledger the
    beat already wrote decides WHERE inside the occupant lands instead of the
    entry room. Matched on the room's key or its display name, casefolded:
    the name is what a model writes and the key is what the engine writes.

    THE FIRST STANDING ROW WINS, stated rather than left to list order. Two
    interior rows naming different stations for one pair is the ledger
    disagreeing with itself, and no fact in the scene decides which is right
    -- so the answer is the one the scene lists first, and it is an answer
    rather than an artefact of where in a list a row happened to land.
    Wherever no row resolves against a real room, the entry room answers.
    """
    region = _declared_interior_region(scene, occupant, holder)
    if not region:
        return None
    wanted = region.casefold()
    rooms = (scene or {}).get("rooms") or {}
    for rid in interior_ids:
        room = rooms.get(rid) or {}
        if str(rid).strip().casefold() == wanted:
            return rid
        if str(room.get("name") or "").strip().casefold() == wanted:
            return rid
    return None


# The card may author a body's inside as a chain of stations, outermost
# first. Eight is a cap rather than a shape: past it a "place" is a dungeon
# somebody wrote into an appearance field, and the room channel is where a
# dungeon belongs.
_MAX_INTERIOR_STATIONS = 8
# A room NAME is a handle prose says out loud, not a paragraph: a hundred-word
# name matches nothing when a beat names the region somebody is in, and reads
# as nothing. Both bounds are stated a second time on the card surface
# (`story/character_schema.INTERIOR_STATIONS_MAX` / `INTERIOR_NAME_MAX`), which
# is what an author is held to; these are the engine's own, for a spec that
# reached the scene by some route other than the card.
_MINTED_INTERIOR_NAME_MAX = 60


def _station_room_id(rooms: dict, eid: str, name: str):
    """A deterministic room id for one interior station of `eid`, or None.

    Derived from the holder's entity id, so it is chat-local and stable
    across merges -- re-running the mint on a scene that already has the room
    is impossible anyway (gate 5), and the collision loop is here for a room
    id some retired story shape left behind, not for this pass fighting
    itself.
    """
    slug = normalize_room_id(name)
    if not slug:
        return None
    base = "%s_%s" % (eid, slug)
    rid, n = base, 2
    while rid in (rooms or {}):
        rid = "%s_%d" % (base, n)
        n += 1
    return rid


def _mint_authored_interior(scene: dict, eid: str, spec) -> bool:
    """Mint the card-authored stations of `eid`, outermost first.

    A linear chain, because a linear chain is what the card declares: the
    first station carries the derived way in (`dock_exit`), each later one is
    joined to the one before it by the passage that station names, and the
    default passage is `membrane` -- the one barrier a body walks through and
    nothing sees through. A branching inside is not authored here; rooms merge
    by id, so the spatial specialist's `rooms` channel grafts one on.
    """
    if not isinstance(spec, (list, tuple)) or not spec:
        return False
    rooms = scene["rooms"]
    made = []
    for station in list(spec)[:_MAX_INTERIOR_STATIONS]:
        if isinstance(station, str):
            station = {"name": station}
        if not isinstance(station, dict):
            continue
        name = " ".join(str(station.get("name") or "").split())
        name = name[:_MINTED_INTERIOR_NAME_MAX].strip()
        if not name:
            continue
        rid = _station_room_id(rooms, eid, name)
        if not rid:
            continue
        # LAZY: `world.spatial_light` imports `world.spatial_geometry`, which
        # imports this module -- the cycle the package layout already has.
        from world.spatial_light import normalize_light
        raw_light = str(station.get("light") or "").strip()
        room = {
            "name": name,
            "desc": " ".join(str(station.get("desc") or "").split())[:400],
            # AN UNAUTHORED INSIDE IS DARK, and the alias table is why it has
            # to be said: `normalize_light("") == "lit"`, so absent light
            # means a body's inside renders as though someone had lit it.
            "light": normalize_light(raw_light) if raw_light else "dark",
            "parent_entity": eid,
            "adjacent": [],
        }
        # HOW LONG THIS STATION TAKES TO CROSS, when the card said. Absent
        # means the place imposes no time and holds its occupant, which is
        # every room's behaviour before this field existed.
        crossing = room_transit_seconds(station)
        if crossing is not None:
            room["transit_seconds"] = crossing
        if not made:
            # The way in is DERIVED, never authored: `apply_transit_dock_edges`
            # reads this marker to decide which station the doorway lands on.
            room["dock_exit"] = True
        rooms[rid] = room
        if made:
            unresolved = set()
            barrier = normalize_barrier(
                str(station.get("barrier") or "").strip() or "membrane",
                unresolved=unresolved)
            # A word the barrier vocabulary has not been taught normalizes to
            # `wall`, which would seal a passage the author wrote as a way
            # through. Inside a body the stated default answers instead.
            if unresolved:
                barrier = "membrane"
            rooms[made[-1]]["adjacent"].append({"to": rid, "barrier": barrier})
            room["adjacent"].append({"to": made[-1], "barrier": barrier})
        made.append(rid)
    return bool(made)


def _mint_minimal_interior(scene: dict, eid: str, occupant: str,
                           holder: str) -> bool:
    """Mint ONE room for a body that has taken another body inside.

    ONE ROOM, AND ONE IS THE ARGUMENT. The record already entails that an
    inside exists, whose it is, and that it is out of the surrounding room's
    sight. One room restates exactly that claim in place vocabulary and adds
    nothing. A second room would be invented anatomy: the engine has no fact
    from which to derive internal structure, so any multi-room default is a
    lie by construction.

    THE NAME COMES OUT OF THE LEDGER THE BEAT ALREADY WROTE. A standing
    interior contact names the region (`target_interior`); that region and
    this room are one fact under two names, so the engine invents no noun
    where the story supplied one -- and `_interior_station_hint` then resolves
    against the minted room by name on every later merge.
    """
    rooms = scene["rooms"]
    rid = _station_room_id(rooms, eid, "interior")
    if not rid:
        return False
    name = _declared_interior_region(scene, occupant, holder)
    name = " ".join(str(name).split())[:_MINTED_INTERIOR_NAME_MAX].strip()
    if not name:
        name = "Inside %s" % _display_name(scene, holder)
    rooms[rid] = {
        "name": name,
        # A PROSE-FREE STUB, the `world/structure.py` materialize_planned_fringe
        # precedent: a later Director declaration merges description onto it by
        # id, and every room-`desc` reader in the tree reads it as `or ""`.
        "desc": "",
        "light": "dark",
        "parent_entity": eid,
        "adjacent": [],
        "dock_exit": True,
    }
    return True


def materialize_enclosure_interiors(scene: dict) -> list:
    """A standing `mode: interior` record over a BODY is a place. Mint it.

    THE MISSING ON-RAMP. `place_enclosed_bodies` converts the ledger form of
    one body inside another into the place form -- but only for a holder that
    ALREADY has interior rooms, and the only thing that ever produced those
    was a clause in a prompt asking a model to author them. So the road had no
    entrance: measured read-only against the author's corpus 2026-08-25, two
    stored scenes (chats 88, 89) carry a `mode: interior` record whose holder
    has zero interior rooms, and two more (chats 86, 87) mint one on their
    very next merge from a standing interior contact. Four scenes, every one
    of them a body standing in its holder's own exterior room forever.

    EXISTENCE IS A DERIVATION, NOT AUTHORED CONTENT. The scene already states
    every fact the floor needs -- that the enclosure stands, whose inside it
    is, where that body is, and (for a body) that the way in is opaque -- so
    the room follows from the record the way the doorway already follows from
    the holder's state. `world/spatial_transit.py`'s own docstring rejected
    the alternative when `infer_body_enclosures` was written: relying on a
    model to remember a property every time is the wrong shape for this
    engine, and flesh is opaque whether or not anyone remembered to say so.

    FIVE GATES, EACH A SKIP:
    1. `mode: interior` exactly. `held`, `pocket`, `carried`, `container`,
       `riding`, `mounted` and `worn` are carriage -- cargo with no inside to
       stand in -- and stay the ledger's business.
    2. The holder resolves to exactly ONE scene entity. The room form is keyed
       by entity id, and folding two beings into one would build an inside for
       the wrong body.
    3. The holder is a BODY, AND THE REASON IS THE FIREWALL RATHER THAN
       TAXONOMY. `sync_entity_interior_rooms` and `infer_body_enclosures` are
       both body-scoped, so an interior minted for a non-body is never indexed
       and never defaulted opaque -- `apply_transit_dock_edges` then derives an
       `open_door`, and an occupant `containment_hides` was concealing becomes
       one visible from the room outside. That is information EXPANSION, which
       the firewall forbids. So the engine mints only where it can also
       guarantee the way in is not see-through. Serving a crate or a lift car
       the same way needs the non-body enclosure default first.
    4. The holder is somewhere. An interior that is nowhere has no exterior to
       travel with, and a ledger entry that at least says who holds whom is
       better than a room adrift.
    5. The holder has NO interior rooms yet. Scene topology beats the card and
       beats the floor, and this is also what makes the pass idempotent.

    Never writes `interior_rooms` and never writes `enclosure`: both are
    derived, by the two body-scoped passes that already own them.

    Returns the holder entity ids it minted for. Mutates; idempotent.
    """
    contained = (scene or {}).get("contained")
    if not isinstance(contained, dict) or not contained:
        return []
    rooms = scene.get("rooms")
    if not isinstance(rooms, dict):
        return []
    minted = []
    for subject in list(contained):
        record = contained.get(subject)
        if not isinstance(record, dict):
            continue
        if str(record.get("mode") or "").strip().casefold() != "interior":
            continue                                            # gate 1
        holder = str(record.get("in") or "").strip()
        if not holder:
            continue
        eid, entity = _unique_entity_keyed(scene, holder)
        if not eid:
            continue                                            # gate 2
        if not _is_body_entity(scene, eid, entity):
            continue                                            # gate 3
        if room_of(scene, holder) is None:
            continue                                            # gate 4
        if _interior_rooms_of(scene, eid):
            continue                                            # gate 5
        spec = entity.get("interior_spec") if isinstance(entity, dict) else None
        made = _mint_authored_interior(scene, eid, spec)
        if not made:
            made = _mint_minimal_interior(scene, eid, subject, holder)
        if made:
            minted.append(eid)
    return minted


#: Exactly the keys `_mint_minimal_interior` writes. The replacement below
#: compares the WHOLE key set against this rather than checking three fields,
#: and that is the difference between a safe pass and a destructive one:
#: measured read-only against the author's corpus 2026-08-25, chat 91's minted
#: stub carries `exposure: "enclosed"` and `size: "tight"` -- Director-declared
#: room facts (`spatial_merge._ROOM_SILENT_WHEN_EMPTY`) merged onto the stub
#: after it was minted. A field-by-field check passes that room and deletes
#: story fact; a key-set check refuses it.
_MINIMAL_INTERIOR_KEYS = frozenset(
    ("name", "desc", "light", "parent_entity", "adjacent", "dock_exit"))


def _is_engine_minted_stub(scene: dict, room_id: str) -> bool:
    """Is this room the engine's OWN unmodified one-room mint?

    The one state in which the card may beat the scene. Gate 5 of
    `materialize_enclosure_interiors` states the standing doctrine -- scene
    topology beats the card, which is also what makes the mint idempotent --
    and this is its single exception, on the ground that the exception loses
    nothing BY CONSTRUCTION. `_mint_minimal_interior` derives its room
    entirely from the enclosure record: one room, dark, prose-free, timeless,
    named out of the ledger the beat already wrote. A stub in exactly that
    state restates a fact the record still entails and carries nothing else,
    so an authored chain can replace it without deleting anything the story
    said.

    Anything the story has SINCE written on it is lived topology: a merged
    description, a crossing time, a declared exposure or size, a second room
    grown by `materialize_named_stations`. Those the card does not get to
    overwrite, and the whole-key-set test is what tells the two apart.
    """
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict):
        return False
    if set(room) != _MINIMAL_INTERIOR_KEYS:
        return False
    if not room.get("dock_exit"):
        return False
    if str(room.get("desc") or "").strip():
        return False
    if str(room.get("light") or "").strip().casefold() != "dark":
        return False
    return room_transit_seconds(room) is None


def replace_engine_minted_interiors(scene: dict) -> list:
    """Let a card's authored chain replace the engine's own one-room mint.

    THE SECOND HALF OF THE ON-RAMP. `materialize_enclosure_interiors` mints
    the authored chain when a holder has no interior rooms at all, and skips
    every holder that already has one (its gate 5). Every live story that
    needs a chain already carries the engine's own minimal mint, so an
    authored chain could never reach the stories it was written for --
    measured 2026-08-25 against the author's corpus: of the six scenes holding
    this arrangement, two (chats 90 and 91) already stand on a minted room.

    IT CANNOT LIVE INSIDE GATE 5, and the corpus is why. That function walks
    `scene["contained"]`, and `place_enclosed_bodies` POPS the containment
    record after the first placement -- chat 90 stores `contained: {}` with
    its occupant standing in the mint. A bypass inside the contained-walk
    would never fire for the very scenes it exists for. So this walks
    ENTITIES, and runs beside the mint rather than inside it.

    FOUR REFUSALS, EACH A SKIP:
    1. No authored spec, or the holder is not a body: nothing to replace it
       with, and the body scope is `materialize_enclosure_interiors` gate 3's
       firewall bound, unchanged.
    2. The interior is anything but exactly ONE room in the engine's own
       unmodified minted state (`_is_engine_minted_stub`). Scene topology
       beats the card everywhere else.
    3. The mint's name already matches the spec's sole station. That is the
       fixpoint guard: a one-station spec mints a room structurally identical
       to the stub, so without this the pass would replace its own output
       forever and two consecutive empty-diff merges would serialize one
       scene two different ways -- the exact non-fixpoint W8 measured.
    4. Somebody is STANDING in the mint and its name matches no authored
       station. The engine cannot map the lived position onto the chain, and
       the two available answers are both worse than doing nothing: dropping
       them in the entry station carries a body OUTWARD from where the story
       put it, and inventing a destination is anatomy nobody wrote. A mint
       left standing is strictly better than a body moved backwards.

    NOBODY CAN LAND IN NOWHERE, which is what fixes the order: mint the
    authored chain FIRST (`_station_room_id`'s collision loop keeps the new
    ids clear of the old room), and only once it exists relocate, retarget,
    and retire. A failure anywhere before that leaves the old room standing
    with its occupants in it.

    Returns the holder entity ids it replaced for. Mutates; idempotent.
    """
    entities = (scene or {}).get("entities")
    rooms = (scene or {}).get("rooms")
    positions = (scene or {}).get("positions")
    if not isinstance(entities, dict) or not isinstance(rooms, dict):
        return []
    if not isinstance(positions, dict):
        return []
    replaced = []
    for eid, entity in list(entities.items()):
        if not isinstance(entity, dict):
            continue
        spec = entity.get("interior_spec")
        if not isinstance(spec, (list, tuple)) or not spec:
            continue                                            # refusal 1
        if not _is_body_entity(scene, eid, entity):
            continue                                            # refusal 1
        existing = _interior_rooms_of(scene, eid)
        if len(existing) != 1:
            continue                                            # refusal 2
        old_id = existing[0]
        if not _is_engine_minted_stub(scene, old_id):
            continue                                            # refusal 2
        old_name = str((rooms.get(old_id) or {}).get("name") or "").strip()
        wanted = old_name.casefold()
        station_names = [
            " ".join(str((s or {}).get("name") if isinstance(s, dict) else s
                         or "").split())
            for s in spec]
        station_names = [n for n in station_names if n]
        if not station_names:
            continue
        if len(station_names) == 1 and station_names[0].casefold() == wanted:
            continue                                            # refusal 3
        occupants = [subject for subject, room in positions.items()
                     if room == old_id]
        if occupants and wanted not in {n.casefold() for n in station_names}:
            continue                                            # refusal 4

        if not _mint_authored_interior(scene, eid, spec):
            continue
        minted = [rid for rid in _interior_rooms_of(scene, eid)
                  if rid != old_id]
        if not minted:
            continue
        destination = next(
            (rid for rid in minted
             if str((rooms.get(rid) or {}).get("name") or "").strip()
             .casefold() == wanted), None)
        holder_name = _display_name(scene, eid)
        for subject in occupants:
            # Refusal 4 has already proven a destination exists whenever
            # anybody is standing here.
            _positions_write(positions, subject, destination)
            # The ledger follows the body, by the same rule the crossing
            # itself follows: a contact still naming the room behind them is
            # what `_interior_station_hint` would read to drag them back.
            retarget_interior_contacts(
                scene, subject, holder_name,
                str((rooms.get(destination) or {}).get("name") or ""))
        # Retire the stub LAST, and take its edges with it: the exterior
        # room's reverse dock edge outlives the room it points at otherwise.
        rooms.pop(old_id, None)
        for room in rooms.values():
            if not isinstance(room, dict):
                continue
            edges = room.get("adjacent")
            if isinstance(edges, list):
                room["adjacent"] = [
                    e for e in edges
                    if not (isinstance(e, dict) and e.get("to") == old_id)]
        # `sync_entity_interior_rooms` is ADD-ONLY by documented design, so
        # the pass that retires a room does its own removal from the index.
        listed = entity.get("interior_rooms")
        if isinstance(listed, list):
            entity["interior_rooms"] = [
                rid for rid in listed if str(rid) != str(old_id)]
        replaced.append(str(eid))
    return replaced


def place_enclosed_bodies(scene: dict) -> list:
    """A body that has taken another body INSIDE is a place. Put them in it.

    THE THIRD PATH, and the one nothing took. The engine has two accounts of
    one body being within another: a `contained` record (the ledger form --
    the occupant has no place of their own and derives their carrier's) and a
    room whose `parent_entity` is the holder (the place form -- the occupant
    stands somewhere, and that somewhere travels). Every consequence of the
    place form was already built and tested: the doorway is derived from the
    holder's own state, `membrane` is opaque in both states, ambient scope
    stops at the boundary, and the composer renders the inside like any room.
    Nothing converted the first into the second, so an interior a beat
    declared stayed a one-line ledger entry and the occupant's position was
    derived, every merge, to the holder's OWN room -- the two bodies standing
    in the same place, the inside not existing anywhere the engine could
    read it.

    Measured, chat 88 across fifteen consecutive audited turns: the holder
    carried `interior_rooms: []`, `scene.rooms` held one room with
    `adjacent: []`, `scene.positions` put both bodies in it, and the whole
    interior was free-text keys on the entity blob that no spatial query
    reads. The occupant's composed view was four sentences long, because
    there was no room to compose.

    THE CONVERSION IS DETERMINISTIC AND CONDITIONAL. Existence of the place
    is not a judgment: a record that says `mode: interior` plus a holder that
    HAS interior rooms is a body standing in one of them, and no model has to
    remember to say so. A holder with NO interior rooms is still left exactly
    as it was HERE -- but it no longer stays that way through the merge, and
    that sentence used to end with "which is the whole migration story for
    every scene already on disk". It was, and that was the defect: the only
    producer of interior rooms was a clause in a prompt, so this conversion
    had no on-ramp and fired in no story. `materialize_enclosure_interiors`
    runs immediately before every call to this one and mints the inside the
    record already entails, so what arrives here now HAS rooms.

    ONLY `mode: interior`. `held`, `pocket`, `carried`, `container`, `riding`
    are carriage -- cargo with no inside to stand in -- and stay the ledger's
    business. `interior` is the one mode `CONTAINMENT_MODES` documents as "a
    body inside another body's own interior".

    ONE TRUTH, NEVER TWO. Where the occupant is ALREADY standing in one of
    the holder's interior rooms, the record is redundant and is dropped
    without touching the position: a body cannot be both placed inside and
    carried by the same holder, and leaving both would let
    `derive_contained_positions` drag them back out to the holder's exterior
    room on the next merge.

    Returns the subjects it placed, for the caller's report. Idempotent:
    a second call finds no mode-interior record left to convert.
    """
    contained = (scene or {}).get("contained")
    if not isinstance(contained, dict) or not contained:
        return []
    positions = scene.get("positions")
    if not isinstance(positions, dict):
        return []
    placed = []
    for subject in list(contained):
        record = contained.get(subject)
        if not isinstance(record, dict):
            continue
        if str(record.get("mode") or "").strip().casefold() != "interior":
            continue
        holder = str(record.get("in") or "").strip()
        if not holder:
            continue
        # The room form is keyed by the entity ID, so an ambiguous holder is
        # no holder: folding two beings into one would place a body inside
        # the wrong one, which is strictly worse than leaving the ledger.
        eid, entity = _unique_entity_keyed(scene, holder)
        if not eid:
            continue
        interior_ids = _interior_rooms_of(scene, eid)
        if not interior_ids:
            continue           # no inside to stand in: nothing changes
        # A holder the scene does not place has no exterior for its interior
        # to travel with, and an interior that is nowhere is worse than a
        # ledger entry that at least says who is holding whom.
        if room_of(scene, holder) is None:
            continue
        here = room_of(scene, subject)
        if here in set(interior_ids):
            contained.pop(subject, None)
            continue
        destination = _interior_station_hint(
            scene, subject, holder, interior_ids)
        if destination is None:
            destination = _interior_entry_room(scene, eid, entity)
        if destination is None:
            continue
        _positions_write(positions, subject, destination)
        contained.pop(subject, None)
        placed.append(subject)
    return placed


# ---------------------------------------------------------------------------
# A PLACE MAY TAKE TIME TO CROSS, AND AN OCCUPANT CROSSES IT ON THE CLOCK.
#
# Advancing through a passage is a deterministic consequence of elapsed time,
# not a Director decision and not a player prompt. Measured read-only against
# the author's corpus 2026-08-25 at 49ea899: chat 89 entered a holder's
# interior at turn 54 and was still in the same station at turn 62 -- nine
# beats -- while the sibling chat 88, on identical entry, crossed three
# stations in four turns because its player happened to keep feeding beats the
# Director could read continuation into. That is luck, not mechanism.
#
# DERIVED AT MERGE, NOT SCHEDULED. Position inside a passage is a pure
# function of (entry stamp, simulation clock), recomputed here exactly the way
# `infer_body_enclosures`, `place_enclosed_bodies`, `derive_contained_positions`
# and `materialize_enclosure_interiors` already recompute their facts. Reroll,
# branch, checkpoint restore and replay are correct by construction, because
# all three inputs are already snapshotted together -- which a scheduled
# arrival event would have had to earn per kind, while also opening a second
# authority over `positions` outside the merge, where none of the station,
# pose and contact hygiene that hangs off a room ever re-runs.
#
# WHAT DECIDES A CONDUIT FROM A CHAMBER: THE MAGNITUDE IS THE DECLARATION.
# A room that declares `transit_seconds` is crossed in exactly that many story
# seconds, and dwelling past it is impossible by construction; a room that
# declares none holds its occupant until the story moves them. No `role` enum
# ships, and that is a judgement rather than an omission -- an enum saying
# "conduit" with no magnitude gives the crosser nothing to cross, which is a
# declared-and-unreferenced field wearing a syntax, and a threshold-derived
# split ("short means conduit") would have to invent a constant no fact
# supplies. Three precedents in this tree already decide the same way:
# `world.mechanics._tick_interval` makes a condition act SOLELY by carrying a
# parseable positive interval, `_schedule_new_arrivals` schedules SOLELY on a
# parseable positive eta, and news latency derives SOLELY when none is stated.
# A chamber is therefore a large magnitude or no magnitude at all: a place
# that kneads its occupant for hours authors 25200 and IS crossed, slowly.

# What an unauthored station costs to cross, while the ledger says a crossing
# is running. Ordinary beats measured 2026-08-25 are p25 10s / median 25s, so
# a minute is two to six beats of dwelling before the engine acts -- against
# the nine beats chat 89 spent in a place its own card measures in seconds.
#
# GATED ON THE LEDGER'S OWN CLAIM, NOT ON THE SHAPE OF THE CHAIN. The
# tempting structural rule -- "you do not live in the middle of a chain, so
# every non-terminal station marches" -- is wrong in the expensive direction,
# and the corpus says so: chat 88's standing interior contact reads
# `motion: "settled"` while chats 89 and 90 read `motion: "moving"`. Under the
# structural rule, the moment 88's Director grafts one more station its
# occupant is marched out of a place its card measures in HOURS, in sixty
# seconds -- the reported defect inverted at the same three orders of
# magnitude. The ledger already distinguishes them, per occupant, per beat, in
# the engine's own two-word vocabulary, so the ledger decides.
_UNSTATED_CROSSING_SECONDS = 60.0

# How many stations one merge may carry a body through. A long skip should
# still land somewhere reachable rather than teleport to the deep end of an
# arbitrarily long chain, and `_MAX_INTERIOR_STATIONS` is the chain's own
# ceiling, so this can never silently truncate a crossing that had somewhere
# left to go without the remainder being carried into the next beat.
_CROSSING_HOP_CAP = _MAX_INTERIOR_STATIONS


def room_transit_seconds(room):
    """How long this PLACE takes to cross, in story seconds, or None.

    A property of the place, in the scene's own room vocabulary, so one field
    serves a throat, a chute, a lift shaft, a mine gallery and a river reach
    alike. Positive and finite or it is not a magnitude: `_tick_interval`
    already states the doctrine this follows -- a field filled in with nothing
    is not a cadence -- and it was earned on 48 of 131 corpus rows spelling
    `0` where they meant "unset".
    """
    if not isinstance(room, dict):
        return None
    raw = room.get("transit_seconds")
    if raw is None or isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if value <= 0 or value != value or value in (float("inf"), float("-inf")):
        return None
    return value


def _onward_room(scene: dict, room_id: str):
    """The station one step DEEPER than this one, or None.

    ANATOMY-FREE BY CONSTRUCTION. The only order used is "strictly farther
    from the way in", and the way in is a marker the engine itself writes
    (`dock_exit`, via `_interior_entry_room`'s precedence) rather than a noun
    anyone authors. It reads identically for a throat chain, a chute, a duct,
    a lift shaft and a mine gallery.

    NONE MEANS THE ENGINE REFUSES TO MOVE ANYBODY, and every branch below is
    a case where no fact in the scene picks a destination:

    * a room with no `parent_entity` -- an exterior conduit has no derivable
      entry anchor, so there is no "deeper"; this landing's stated bound.
    * an interior whose entry room cannot be resolved.
    * the deep end: no strictly-deeper neighbour exists.
    * a BRANCH: two strictly-deeper neighbours, a grafted topology where the
      scene states no preference. Guessing one would be invention.
    * an impassable or shut boundary on the way. `closed_door` is not in
      `_PASSABLE_BARRIERS`, so a shut door in a lift shaft holds you, and the
      crossing resumes by itself on the beat something opens it.

    NEVER OUTWARD. Hops are strictly deeper, so leaving stays a declared act
    -- which `release_declared_departures` already honours -- and the walk is
    RESTRICTED to the holder's own interior set, which is what makes this pass
    unable to eject anyone: the exterior room on the far side of the way in is
    excluded by construction rather than by a check that could be forgotten.

    Re-derived from live topology every merge, so a Director graft or a
    barrier change is respected mid-crossing.

    Directed where the edge says so. A passage declared crossable one way
    only (`passage_from`) is refused against its direction here as everywhere
    else a body moves -- the valve case this used to name as a registered
    residual. It changes no answer for an ordinary interior, whose stations
    connect by `membrane` in both directions and name no direction at all.
    """
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(room_id)
    if not isinstance(room, dict):
        return None
    parent = str(room.get("parent_entity") or "").strip()
    if not parent:
        return None
    interior = _interior_rooms_of(scene, parent)
    if room_id not in set(interior):
        return None
    entry = _interior_entry_room(scene, parent)
    if entry is None:
        return None
    inside = set(interior)
    neighbors = neighbor_map(scene, barriers=_PASSABLE_BARRIERS,
                             directional=True)
    # Breadth-first from the way in, over passable edges, inside the holder.
    dist = {entry: 0}
    queue = [entry]
    while queue:
        current = queue.pop(0)
        for nxt in sorted(neighbors.get(current) or ()):
            if nxt in inside and nxt not in dist:
                dist[nxt] = dist[current] + 1
                queue.append(nxt)
    here = dist.get(room_id)
    if here is None:
        return None
    deeper = sorted(nxt for nxt in (neighbors.get(room_id) or ())
                    if nxt in inside and dist.get(nxt) == here + 1)
    return deeper[0] if len(deeper) == 1 else None


def _interior_contact_rows(scene: dict, occupant: str, holder: str) -> list:
    """Every standing interior contact row covering this pair, in scene order.

    The same pair test `_declared_interior_region` uses, returning the rows
    themselves because two callers here need to WRITE them.
    """
    want = {str(occupant or "").strip().casefold(),
            str(holder or "").strip().casefold()}
    out = []
    for row in (scene or {}).get("contacts") or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("relation") or "").strip().casefold() != "interior":
            continue
        pair = {str(row.get("actor") or "").strip().casefold(),
                str(row.get("target") or "").strip().casefold()}
        if want <= pair:
            out.append(row)
    return out


def _crossing_is_running(scene: dict, occupant: str, holder: str) -> bool:
    """Does the ledger say a crossing is IN PROGRESS for this pair?

    `settled|moving` is the contact vocabulary's own two words
    (`_normalize_contact_motion`), written per occupant per beat. THE FIRST
    STANDING ROW WINS, the rule `_declared_interior_region` already states for
    the same ledger and the same reason: two rows disagreeing about one pair
    is the ledger disagreeing with itself, and no fact in the scene breaks the
    tie, so the answer is the one the scene lists first.
    """
    for row in _interior_contact_rows(scene, occupant, holder):
        return str(row.get("motion") or "").strip().casefold() == "moving"
    return False


def _transit_bound(scene: dict, subject: str, room_id: str, holder: str):
    """How long `subject` may stay in `room_id` before the clock carries them
    onward, or None for a place that holds its occupant.

    Two sources, in this order:

    1. AN AUTHORED MAGNITUDE ON THE ROOM WINS ANYWHERE, whatever kind of
       enclosure it belongs to. The place said how long it takes to cross.
    2. Otherwise, a station inside a BODY'S interior is bounded ONLY while
       that occupant's own standing interior contact says the crossing is
       running. Body-scoped for the same firewall-grounded reason
       `materialize_enclosure_interiors` gate 3 and `sync_entity_interior_rooms`
       are: a lift car, a crate or a cargo hold moves nobody by default, and
       serving them needs the non-body enclosure default first.

    A holder never crosses its own interior: an enclosure standing inside
    itself is not a crossing, and reading the pair test against one being
    would answer yes for both slots of the row.
    """
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(room_id)
    authored = room_transit_seconds(room)
    if authored is not None:
        return authored
    if not holder or same_subject(scene, subject, holder):
        return None
    eid, entity = _unique_entity_keyed(scene, holder)
    if not eid or not _is_body_entity(scene, eid, entity):
        return None
    if not _crossing_is_running(scene, subject, holder):
        return None
    return _UNSTATED_CROSSING_SECONDS


def retarget_interior_contacts(scene: dict, occupant: str, holder: str,
                               station_name: str) -> bool:
    """Point this pair's standing interior contacts at the station the
    occupant has just been carried into.

    The region and the room are one fact under two names once a holder's
    inside is rooms (`_interior_station_hint` rests on exactly that), so a
    contact still naming the station behind them is a ledger that contradicts
    the position ledger -- and it is the one `_interior_station_hint` reads to
    decide where they land on the NEXT merge, which would drag them back.

    `target_part` is BLANKED, which is the cross op's own never-carry rule:
    omitting the new endpoint means no downstream point is currently touched,
    and the boundary just crossed must never be carried forward as one.
    """
    changed = False
    for row in _interior_contact_rows(scene, occupant, holder):
        if str(row.get("target_interior") or "").strip() != station_name:
            row["target_interior"] = station_name
            row["target_part"] = ""
            changed = True
    return changed


def settle_interior_motion(scene: dict, occupant: str, holder: str) -> bool:
    """Retire a crossing claim nothing is advancing. SUBTRACTION ONLY.

    A crossing the world cannot advance is not running, whatever the ledger
    says, and the ledger asserting one forever is what kept a Director
    re-declaring a crossing into the station its occupant was already in
    (chat 89 turn 62 emitted a crossing from a place into itself). This
    removes a claim; it never adds one, and it never touches a row that
    already says `settled`.
    """
    changed = False
    for row in _interior_contact_rows(scene, occupant, holder):
        if str(row.get("motion") or "").strip().casefold() == "moving":
            row["motion"] = "settled"
            changed = True
    return changed


def _holder_of_room(scene: dict, room_id: str) -> str:
    """The display name of the entity whose interior this room is, or ""."""
    room = ((scene or {}).get("rooms") or {}).get(room_id)
    if not isinstance(room, dict):
        return ""
    parent = str(room.get("parent_entity") or "").strip()
    if not parent:
        return ""
    return _display_name(scene, parent) or parent


def materialize_named_stations(scene: dict, prior_positions=None) -> list:
    """A standing interior contact naming a region the holder's inside has no
    room for is a station the story declared and the engine never built. Mint
    it.

    THE ON-RAMP, and without it the crossing above has no chain to run along
    in any live story. `place_enclosed_bodies` pops the containment record
    after the first placement, and `materialize_enclosure_interiors` mints
    only where there are NO interior rooms yet (its gate 5), so nothing in the
    tree ever converted a newly named region into a second station. Chat 88's
    three transitions in four turns went through the rooms channel by luck;
    every later beat that renamed the region moved nobody.

    PROGRESSION, NEVER ARRIVAL, and `prior_positions` is what tells them
    apart. A body ENTERING an enclosure names the region it arrives in, and
    that region is already answered twice over -- `_mint_minimal_interior`
    names the room it mints from it, and `_interior_station_hint` resolves it
    against an existing chain, falling back to the way in when it resolves to
    nothing. Minting there would build a second room for one arrival and put
    the entry room behind a body that never crossed it. So this fires only
    for a body that was ALREADY standing in one of this holder's interior
    rooms BEFORE this merge: the beat named somewhere further in, which is
    the one reading no existing pass answers. Without the prior ledger
    (a caller that has none) the pass is a no-op, because it cannot tell the
    two apart and arrival is the commoner case.

    THE STATION IS CHAINED TO WHERE THE OCCUPANT ALREADY STANDS, joined by
    `membrane` -- the one barrier a body passes through and nothing sees
    through, the same default `_mint_authored_interior` uses -- and the
    occupant is placed in it. That is the smallest claim the ledger entails:
    the beat said this body is now in a region of that holder which is not the
    region it was in, so the region is somewhere further along from there.

    FOUR GATES, EACH A SKIP:
    1. The holder resolves to exactly one entity, is a BODY, and already has
       interior rooms. No interior yet is `materialize_enclosure_interiors`'s
       job and it has already run; a non-body is the firewall bound its gate 3
       states.
    2. The occupant is standing in one of those interior rooms. A stray row
       about somebody outside the holder cannot mint anything.
    2b. The occupant was ALREADY in one of them before this merge -- see
       PROGRESSION above.
    3. The region matches no interior room by id or display name, casefolded.
       A region that resolves is the room they are already in.
    4. The holder is under `_MAX_INTERIOR_STATIONS` interior rooms. A Director
       that spells one region two ways cannot build a dungeon out of a
       renaming spree.
    5. Where the holder's inside is an AUTHORED chain, the occupant stands at
       its DEEP END. A declared chain is an ORDERED DOCUMENT, and a region it
       does not name has no position in it: mid-chain the engine cannot tell
       a region the occupant has already PASSED from one beyond the last
       station, and this pass only knows how to chain deeper, so it would put
       an outward region behind a body that has not reached it. At the deep
       end "deeper" is the only place a new station could go, which is why
       the on-ramp still grows a chain a story continues past its authored
       end -- and where nothing is authored, every gate above is unchanged,
       because a story-grown chain has no declared order to contradict.
       Measured on a scratch copy of the author's corpus 2026-08-25 with the
       card filled and saved: one branch's ledger names a region the authored
       chain omits, the occupant was placed at the entry station, and the
       next merge minted that region DEEPER than the entry and moved her
       outward into it, where she held for fourteen beats (t=22800.0). The
       skip leaves her where the chain put her, and `_restation_interior_
       contact` re-derives the ledger's region from the room she is in.

    Measured inert on all 78 stored scenes 2026-08-25: five standing interior
    contacts name a region with no matching room, and in every one of them the
    occupant is standing in the holder's EXTERIOR room, so gate 2 skips them
    all -- the merge's own mint names the same region from the same ledger one
    step earlier. The exposure is entirely forward.

    Returns the room ids minted. Mutates; idempotent.
    """
    rooms = (scene or {}).get("rooms")
    positions = (scene or {}).get("positions")
    if not isinstance(rooms, dict) or not isinstance(positions, dict):
        return []
    if not isinstance(prior_positions, dict) or not prior_positions:
        return []
    minted = []
    for row in list((scene or {}).get("contacts") or []):
        if not isinstance(row, dict):
            continue
        if str(row.get("relation") or "").strip().casefold() != "interior":
            continue
        region = " ".join(str(row.get("target_interior") or "").split())
        region = region[:_MINTED_INTERIOR_NAME_MAX].strip()
        if not region:
            continue
        holder = str(row.get("target") or "").strip()
        occupant = str(row.get("actor") or "").strip()
        if not holder or not occupant or same_subject(scene, occupant, holder):
            continue
        eid, entity = _unique_entity_keyed(scene, holder)
        if not eid or not _is_body_entity(scene, eid, entity):
            continue                                            # gate 1
        interior_ids = _interior_rooms_of(scene, eid)
        if not interior_ids:
            continue                                            # gate 1
        here = room_of(scene, occupant)
        if here not in set(interior_ids):
            continue                                            # gate 2
        if _ci_get(prior_positions, occupant) not in set(interior_ids):
            continue                                            # gate 2b
        wanted = region.casefold()
        if any(str(rid).strip().casefold() == wanted
               or str((rooms.get(rid) or {}).get("name") or "").strip()
               .casefold() == wanted for rid in interior_ids):
            continue                                            # gate 3
        if len(interior_ids) >= _MAX_INTERIOR_STATIONS:
            continue                                            # gate 4
        spec = entity.get("interior_spec") if isinstance(entity, dict) else None
        if (isinstance(spec, (list, tuple)) and spec
                and _onward_room(scene, here) is not None):
            continue                                            # gate 5
        rid = _station_room_id(rooms, eid, region)
        if not rid:
            continue
        rooms[rid] = {
            "name": region,
            # A PROSE-FREE STUB, the same `materialize_planned_fringe`
            # precedent `_mint_minimal_interior` cites: a later declaration
            # merges description onto it by id.
            "desc": "",
            "light": "dark",
            "parent_entity": eid,
            "adjacent": [{"to": here, "barrier": "membrane"}],
        }
        prior = rooms.get(here)
        if isinstance(prior, dict):
            prior.setdefault("adjacent", []).append(
                {"to": rid, "barrier": "membrane"})
        _positions_write(positions, occupant, rid)
        minted.append(rid)
    return minted


def advance_room_transits(scene: dict, now_seconds=None, report=None) -> list:
    """Carry every occupant of a timed passage onward on the clock.

    A HARD NO-OP WITHOUT A CLOCK. `now_seconds is None` means the caller is
    merging for some purpose other than living a beat -- a paradox probe, a
    Director preview, a migration re-merge -- and this pass must leave such a
    merge byte-identical to what it produced before this landing existed.

    THE STAMP IS THE STATE, and it is derived rather than declared:
    `scene["room_since"][subject] = {"room", "since"}` records where a body
    was when the clock last saw it here. It resets whenever the ledger's room
    differs from the stamped one, which is what makes a DECLARED position beat
    the derivation automatically -- a body the beat moved starts its new
    crossing from now -- and what backfills every enclosure that was entered
    before this landing existed, since the first clocked merge to see them
    stamps them.

    THE REMAINDER IS CARRIED, never discarded: `since` advances by the bound
    that was spent, not to `now`. A beat covering an hour therefore crosses as
    many stations as an hour buys, and the leftover seconds count toward the
    next one -- which a one-shot scheduled arrival could only have got by
    chaining events per hop.

    A BOUND REACHED WITH NOWHERE ONWARD REPORTS ONCE AND THEN SUBTRACTS. The
    engine will not invent a station to deliver anybody into: the world does
    not contain one, and minting a nameless room per expiry would be exactly
    the invented anatomy `_mint_minimal_interior` already refuses. What it
    does instead is say out loud which fact is missing, to the one party that
    can supply it, and retire the ledger's claim that a crossing is running --
    because a crossing nothing is advancing is not running. `told` on the
    stamp keeps every later beat quiet about the same standing situation.

    Returns the subjects moved. Mutates. Idempotent at a fixed clock.
    """
    if now_seconds is None:
        return []
    try:
        now = float(now_seconds)
    except (TypeError, ValueError):
        return []
    positions = (scene or {}).get("positions")
    rooms = (scene or {}).get("rooms")
    if not isinstance(positions, dict) or not isinstance(rooms, dict):
        return []
    notes = report if isinstance(report, list) else []
    stamps = (scene or {}).get("room_since")
    stamps = dict(stamps) if isinstance(stamps, dict) else {}
    moved = []

    for subject in list(positions):
        here = positions.get(subject)
        if not isinstance(here, str) or here not in rooms:
            continue
        holder = _holder_of_room(scene, here)
        bound = _transit_bound(scene, subject, here, holder)
        prior = stamps.get(subject)
        if not isinstance(prior, dict) or prior.get("room") != here:
            prior = {"room": here, "since": now}
        if bound is None:
            # Not a timed passage for this body. Keep the stamp only while it
            # says something -- a body standing in an ordinary room needs no
            # entry time recorded, and writing one for every position would
            # put the whole cast in the blob.
            stamps.pop(subject, None)
            continue
        stamps[subject] = prior
        try:
            since = float(prior.get("since"))
        except (TypeError, ValueError):
            since = now
            prior["since"] = now

        hops = 0
        while now - since >= bound and hops < _CROSSING_HOP_CAP:
            onward = _onward_room(scene, here)
            if onward is None:
                if not prior.get("told"):
                    prior["told"] = True
                    where = _display_name(scene, subject)
                    place = str((rooms.get(here) or {}).get("name") or here)
                    if holder:
                        notes.append(
                            "%s is past the crossing time of %s inside %s, "
                            "and that interior declares no station beyond it "
                            "-- the crossing has been recorded as ended "
                            "rather than advanced; declare the next station "
                            "if the passage continues"
                            % (where, place, holder))
                    else:
                        # The stated bound of this landing, said out loud
                        # rather than silently ignored: an authored crossing
                        # time on a room that is nobody's interior is READ
                        # and refused, because nothing outside an enclosure
                        # supplies a way in to measure "onward" from.
                        notes.append(
                            "%s declares a crossing time and the engine "
                            "cannot derive which way is onward outside an "
                            "enclosure -- %s was not moved" % (place, where))
                    if holder:
                        settle_interior_motion(scene, subject, holder)
                break
            _positions_write(positions, subject, onward)
            since += bound
            prior["room"] = onward
            prior["since"] = since
            prior.pop("told", None)
            station = str((rooms.get(onward) or {}).get("name") or onward)
            if holder:
                retarget_interior_contacts(scene, subject, holder, station)
            notes.append(
                "%s was carried onward into %s on the clock after %gs"
                % (_display_name(scene, subject), station, bound))
            moved.append(subject)
            here = onward
            holder = _holder_of_room(scene, here)
            bound = _transit_bound(scene, subject, here, holder)
            hops += 1
            if bound is None:
                stamps.pop(subject, None)
                break

    # Written only while a crossing is live, and popped when none is -- the
    # `expired_entity_state` pattern and its stated ruling: a scene that is
    # not mid-crossing carries no such key at all, which is every one of the
    # 78 stored blobs measured 2026-08-25.
    if stamps:
        scene["room_since"] = stamps
    else:
        scene.pop("room_since", None)
    return moved


def _interior_counterpart(row: dict, subject: str) -> str:
    """The OTHER party of an interior contact row, given one of them."""
    folded = str(subject or "").strip().casefold()
    actor = str(row.get("actor") or "").strip()
    target = str(row.get("target") or "").strip()
    if actor.casefold() == folded:
        return target
    if target.casefold() == folded:
        return actor
    return ""


def release_declared_departures(scene: dict, declared) -> list:
    """A body DECLARED into a room its holder's interior does not hold has
    left it. Release the ledgers that still say otherwise.

    A DECLARED POSITION IS A DECLARED ACT. `AGENTS.md` states the general
    prohibition -- the engine must not silently replace what the beat
    declared -- and once a body that takes another body inside is a PLACE,
    two derivations stand between a declared exit and the scene. The first
    is the carry derivation, which puts a contained body wherever its holder
    is. The second is new with the place form, and it closes a LOOP:
    `derive_containment_from_contacts` mints a fresh `mode: interior` record
    off any standing interior contact, and `place_enclosed_bodies` reads that
    record and puts the body back inside. Neither derivation is wrong on its
    own; together, with a declared position between them, they undo it every
    beat and the occupant can never leave.

    Measured in the worktree that first built the handoff, on that landing's
    own fixture: t0 placed the occupant at the interior entry room; a merge
    with `positions: {occupant: exterior}` came back with the occupant at the
    entry room again, and repeated forever. The only test for the exit used a
    contact-free scene -- exactly the case the same landing's contact hygiene
    makes rare, since keeping the interior contact alive across the boundary
    is the point of it.

    THE STALE LEDGER IS THE CONTACT, NOT THE POSITION, which is why this
    retires the interior row as well as the containment record. Dropping the
    record alone buys one beat: the row survives, mints again on the next
    merge, and the body is back inside.

    SCOPED TO THE PLACE FORM. A holder with no interior rooms is untouched --
    a body in a pocket cannot walk out of the pocket, and the carry ledger
    that says so is not this rule's business. Scoped to THIS BEAT'S declared
    positions, too, and it runs before the beat's own containment and contact
    declarations are applied: a beat that re-asserts the enclosure keeps it,
    and only the STANDING ledger yields.

    Returns the subjects released, for the caller's report. Mutates.
    """
    if not isinstance(declared, dict) or not declared:
        return []
    contained = (scene or {}).get("contained")
    contacts = (scene or {}).get("contacts")
    released = []
    for subject, destination in declared.items():
        label = str(subject or "").strip()
        dest = str(destination or "").strip()
        if not label or not dest:
            continue
        holders = []
        record = _ci_get(contained, label) if isinstance(contained, dict) \
            else None
        if isinstance(record, dict) and str(
                record.get("mode") or "").strip().casefold() == "interior":
            holders.append(str(record.get("in") or "").strip())
        if isinstance(contacts, list):
            for row in contacts:
                if not isinstance(row, dict):
                    continue
                if str(row.get("relation") or "").strip().casefold() \
                        != "interior":
                    continue
                holders.append(_interior_counterpart(row, label))
        left = False
        for holder in holders:
            if not holder:
                continue
            eid, _entity = _unique_entity_keyed(scene, holder)
            if not eid:
                continue
            interior = {str(rid) for rid in _interior_rooms_of(scene, eid)}
            # Not a place: the ledger form's own rules stand, unchanged.
            if not interior or dest in interior:
                continue
            left = True
            if isinstance(contained, dict):
                current = _ci_get(contained, label)
                if isinstance(current, dict) and same_subject(
                        scene, str(current.get("in") or ""), holder):
                    for key in [k for k in contained
                                if str(k).strip().casefold()
                                == label.casefold()]:
                        contained.pop(key, None)
            if isinstance(contacts, list):
                contacts = [
                    row for row in contacts
                    if not (isinstance(row, dict)
                            and str(row.get("relation") or "").strip()
                            .casefold() == "interior"
                            and same_subject(
                                scene,
                                _interior_counterpart(row, label) or "\x00",
                                holder))
                ]
                scene["contacts"] = contacts
        if left:
            released.append(label)
    return sorted(set(released))


def enclosure_joins_rooms(scene: dict, room_a, room_b,
                          name_a: str = "", name_b: str = "") -> bool:
    """Are these two parties in one place because one is INSIDE the other.

    Two rooms, and the bodies standing in them are as close as bodies get:
    one of the rooms is the other party's own interior. Room equality cannot
    see that -- it is the whole point of the place form that the inside is
    its own room -- so every rule written as "same room" reads a body inside
    another body as a body across the world from it.

    STRICTLY THE PAIR, never the neighbourhood. A third party in the room the
    holder is standing in is NOT joined to the occupant: they are outside an
    enclosure the occupant is inside, and reaching in is an interior relation
    of its own, not a surface hold. The firewall subtracts here, as everywhere.

    ANY HOLDER WHOSE INSIDE IS ROOMS, not only a body -- and the wider rule is
    the stated one because it is the true one. A passenger standing in a
    ship's hold with a hand on the bulkhead has a hand on the ship, and room
    equality cannot see that either. The rest of this landing is about bodies
    because a body is where the missing route showed up; this predicate is
    about the PLACE FORM, which vehicles and structures have had all along.
    Measured across the author's 77 stored scenes: widening the gate changes
    exactly ONE of them, chat 43, and its holder is a body -- a contact the
    old rule severed for standing in the holder's own interior now survives.
    Failing toward KEEPING a contact is the additive direction: a wrong answer
    here is a stale hold for the ageing rule to clear, never a leak.
    """
    rooms = (scene or {}).get("rooms") or {}
    if not isinstance(rooms, dict):
        return False
    for inner, outer_name in ((room_a, name_b), (room_b, name_a)):
        room = rooms.get(inner)
        if not isinstance(room, dict):
            continue
        parent = str(room.get("parent_entity") or "").strip()
        if not parent or not str(outer_name or "").strip():
            continue
        if same_subject(scene, parent, str(outer_name)):
            return True
    return False


def scale_changed_names(previous_scales, current_scales) -> set:
    """Whose size changed enough to break what was true at the old geometry.

    Returns folded names, so a caller compares against
    `str(x).strip().casefold()`.

    ONE implementation, because this is one rule with two consequences: a
    contact is released (`contacts_broken_by_scale_change`) and a containment
    is released (`containment_broken_by_scale_change`), and both must agree on
    what counts as a change. They were separate near-verbatim loops with
    cosmetically different zero-guards -- `min(was, current) <= 0` against
    `was <= 0 or current <= 0` -- which is exactly the arrangement where a
    later threshold change lands in one of them.

    Lives here rather than in a shared geometry module because
    `_SCALE_CONTACT_BREAK` and `clamp_scale` do, and `spatial_geometry`
    imports this module: the dependency only runs one way.
    """
    before = previous_scales if isinstance(previous_scales, dict) else {}
    now = current_scales if isinstance(current_scales, dict) else {}

    changed = set()
    for name in set(before) | set(now):
        was = clamp_scale(_ci_get(before, name)) or 1.0
        current = clamp_scale(_ci_get(now, name)) or 1.0
        if min(was, current) <= 0:
            continue
        if max(was, current) / min(was, current) >= _SCALE_CONTACT_BREAK:
            changed.add(str(name).strip().casefold())
    return changed


def containment_broken_by_scale_change(scene: dict, previous_scales) -> list:
    """Release anyone whose size change makes their container absurd.

    The counterpart of the contact rule, and the reason it matters: someone
    restored to full height while sitting in a coat pocket is not still in the
    coat pocket. The engine releases rather than guesses, and the Director
    re-declares the containment if it still holds.
    """
    contained = scene.get("contained")
    if not isinstance(contained, dict) or not contained:
        return []

    changed = scale_changed_names(previous_scales, scene.get("scales") or {})
    if not changed:
        return []

    released = []
    for subject in list(contained):
        record = contained.get(subject)
        holder = record.get("in") if isinstance(record, dict) else None
        if subject.strip().casefold() in changed or \
                str(holder or "").strip().casefold() in changed:
            contained.pop(subject, None)
            released.append(subject)
    return sorted(released)


def _display_name(scene: dict, name: str) -> str:
    """What the story calls this being, given any spelling of it. A scene
    entity id is an engine handle, and prose that hands one to a mind is
    naming something nobody in the fiction has ever heard."""
    entity = _entity_named(scene, name) or {}
    return str(entity.get("name") or name or "").strip()


def interior_occupants(scene: dict, holder: str) -> list:
    """Every BODY standing in a room this one is the `parent_entity` of,
    under the name the story calls it.

    The place-form counterpart of `contents_of`, which reads the carry ledger
    and therefore answers nothing once an enclosure has become a place. Both
    are the same question -- what is inside me -- asked of the two ledgers
    that can answer it.

    TWO THINGS `positions` HOLDS THAT THIS MUST NOT HAND TO A MIND. It is not
    a map of bodies: it legitimately keys objects, fixtures and unregistered
    presences, and it keys them BY ENTITY ID. So an occupant is resolved to
    its entity and named by `_display_name` -- an engine handle is not a name
    anybody in the fiction has heard -- and anything that is not a body is
    not an occupant. The enclosure vocabulary is body-scoped everywhere else
    it is asked (`infer_body_enclosures`, `_body_interior_holder`, the
    enclosure default itself); this was the one place it was not, and it
    answered a holder that a dropped lamp was somebody who goes where it
    goes. A non-body inside a place-form interior is in no view at all yet;
    that gap is on the register rather than papered over here.
    """
    eid, _entity = _unique_entity_keyed(scene, holder)
    if not eid:
        return []
    interior = set(_interior_rooms_of(scene, eid))
    if not interior:
        return []
    folded = {str(holder or "").strip().casefold(), str(eid).strip().casefold()}
    positions = (scene or {}).get("positions") or {}
    if not isinstance(positions, dict):
        return []
    out = set()
    for name, room in positions.items():
        if room not in interior:
            continue
        if str(name).strip().casefold() in folded:
            continue
        entity = _entity_named(scene, str(name)) or {}
        if not _is_body_entity(scene, str(name), entity):
            continue
        out.add(_display_name(scene, str(name)))
    return sorted(n for n in out if n)


def containment_facts(scene: dict, observer: str, source_names) -> list:
    """What the observer knows about being carried, or carrying.

    TWO LEDGERS, ONE QUESTION. Being inside something is expressed either as
    a carry record (the body has no place of its own) or as a room parented
    to the body around it (the body stands somewhere that travels). This read
    only the first, so the beat an enclosure became a PLACE was the beat the
    occupant stopped being told they were inside anything at all -- their own
    situation, deleted from their own view, which is the forbidden direction:
    a mind concluding LESS than it has a channel for. Both forms are stated
    here, and only one of them can be true of a given body at a time
    (`place_enclosed_bodies` drops the record when it writes the position).
    """
    facts = []
    holder = container_of(scene, observer)
    if holder:
        record = _ci_get(scene.get("contained") or {}, observer) or {}
        mode = record.get("mode") or "carried"
        facts.append(
            f"You are {mode} by {holder} — you go where {holder} goes, and "
            "cannot leave on your own until you are out."
        )
    else:
        # The place form. Named as a PLACE rather than as a mode, because
        # that is what it now is: the occupant has somewhere to be, ways on
        # from it, and a body around all of it that carries the whole thing.
        inside = _body_interior_holder(scene, observer)
        if inside:
            around = _display_name(scene, inside)
            room = ((scene.get("rooms") or {}).get(
                _ci_get(scene.get("positions") or {}, observer)) or {})
            where = str(room.get("name") or "").strip()
            facts.append(
                (f"You are inside {around}, in {where}. " if where
                 else f"You are inside {around}. ")
                + f"This place is {around}'s own interior — it goes where "
                f"{around} goes, and you cannot leave it on your own until "
                "you are out."
            )
    for name in interior_occupants(scene, observer):
        facts.append(
            f"{name} is inside you — in your own interior, and they go "
            "where you go."
        )
    visible = {str(n) for n in (source_names or []) if n} | {observer}
    for name in contents_of(scene, observer):
        record = _ci_get(scene.get("contained") or {}, name) or {}
        facts.append(f"{name} is {record.get('mode') or 'carried'} by you.")
    for name in visible:
        if name == observer:
            continue
        inner = [c for c in contents_of(scene, name) if c in visible]
        for c in inner:
            record = _ci_get(scene.get("contained") or {}, c) or {}
            facts.append(f"{c} is {record.get('mode') or 'carried'} by {name}.")
    return facts

