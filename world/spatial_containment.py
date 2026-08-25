# spatial_containment.py
"""Relative scale and enclosure: how big a body is, what encloses it, what that
hides, and what a size change breaks."""

from world.spatial_identity import _ci_get, _entity_named, room_of, same_subject
from world.spatial_identity import _unique_entity_keyed
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
    wanted = None
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
        wanted = station.casefold()
        break
    if not wanted:
        return None
    rooms = (scene or {}).get("rooms") or {}
    for rid in interior_ids:
        room = rooms.get(rid) or {}
        if str(rid).strip().casefold() == wanted:
            return rid
        if str(room.get("name") or "").strip().casefold() == wanted:
            return rid
    return None


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
    remember to say so. TOPOLOGY is authored content and stays where authored
    content belongs -- the spatial specialist's `rooms` channel. So a holder
    with NO interior rooms is left exactly as it was, ledger record intact:
    that is the whole migration story for every scene already on disk, and
    the reason nothing here changes behaviour until an interior exists.

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

