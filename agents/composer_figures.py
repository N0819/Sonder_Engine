"""Who is here and what THIS observer calls them: referring expressions, the
stranger-label ladder, the sight-gated display map, dim figures, and the
near-to-far presence percepts.

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from story.scene import disguise_breaks_recognition
from world.spatial import (
    body_cell,
    body_visibility,
    effective_anchors,
    effective_station,
    entity_arc,
    entity_side,
    held_beam_falls_on,
    proximity_rel,
    room_of,
    size_relation,
    visual_level_between,
)
from .common import _recognizes, _unknown_actor_label, stranger_label_ladder
from language_runtime import current_language_id

from agents.composer_common import (
    Percept,
    _ENGLISH_COMPOSITOR,
    _compositor,
    _noun_phrase,
    _pack_words,
    _sense_graded,
    _strip_sentence_ends,
    _t,
    body_key,
    standing_key,
)


# --------------------------------------------------------------------------
# Referring expressions
# --------------------------------------------------------------------------

_LABEL_DANGLING = frozenset(_ENGLISH_COMPOSITOR["label_dangling"])


def _descriptor_words(surface):
    """The words a structured SURFACE's label widens through when two
    strangers collide on it (`charter_surface.surface_words`): words in
    axis order, none of them a name. [] for no surface, or one with
    nothing to show.

    A SUMMARY no longer widens this way. Its words came as a flat list in
    prose order and the collision ladder cut it at a count, which landed on
    anything ("the tall and predatory-graceful at top human", the owner's
    cards, 2026-10-20); a summary's label widens through the feature
    phrases the summary attached to its own noun instead
    (`common.stranger_label_ladder`)."""
    if not surface:
        return []
    from world.charter_surface import surface_words
    return surface_words(surface, "full") or []


def _label_core(text):
    """A referring expression with its leading article, its ordinal
    distinguisher and its trailing punctuation off, casefolded -- what two
    spellings of one noun have in common.

    The ordinal comes off because `_ordinal_label` inserts it to tell two
    bodies apart and adds no attribute doing so ("the second ensign" is an
    ensign); leaving it on made this comparison answer differently for the
    first of a group and the rest of it. The article list is language DATA
    (the compositor card), so a pack whose language takes no article
    compares the bare nouns."""
    text = _strip_sentence_ends(text)
    if not text:
        return ""
    # The ordinal comes off in the shape the ACTIVE pack writes it
    # (`_ordinal_label`'s template): "the second <label>", "2番目の<label>".
    for word in _active_ordinal_words().values():
        prefix = _t("ordinal_label", ordinal=word, label="").strip()
        if prefix and len(text) > len(prefix) \
                and text.casefold().startswith(prefix.casefold()):
            text = text[len(prefix):].strip()
            break
    articles = _pack_words("articles")
    ordinals = _ENGLISH_ORDINALS
    parts = text.split()
    while parts and parts[0].casefold() in articles:
        parts = parts[1:]
    if len(parts) > 1 and parts[0].casefold() in ordinals:
        parts = parts[1:]
    return " ".join(parts).casefold()


def _label_from_words(words, cap):
    """Cut a label at `cap` words, dropping a trailing function word.

    THE SURFACE LADDER ONLY. A structured surface's words come in widening
    order by axis (age, build, complexion, stature, marks, worn, hair,
    gait), so a count lands between axes often enough to read; a SUMMARY's
    words came in prose order, and a count landed on anything -- "the tall
    woman in a long" at five, "the tall and predatory-graceful at top
    human" at ten (the owner's cards, 2026-10-20). The wart this docstring
    carried for a year named the fix: cut on the summary's own clauses. That
    is `common.stranger_label_ladder` now, which widens a summary's label
    through the feature phrases the summary itself attached, and this
    function no longer sees a summary. Two earlier attempts to make THIS cut
    smarter both made it worse (a cut walked back past the last connective
    produced labels shorter than the base, which collided, which drove the
    caps into run-ons across 83 views), which is why the surface path keeps
    the plain count.
    """
    take = list(words[:cap])
    while take and take[-1].lower() in _LABEL_DANGLING:
        take = take[:-1]
    if not take:
        return ""
    return _t("unknown_actor",
              description=_strip_sentence_ends(" ".join(take)).lower())


#: Ordinal words for the last-resort distinguisher below. Stops at twelve
#: because past that the honest reading is "a crowd", and a numeral in the
#: middle of a sentence is still prose rather than an engine device.
_ORDINAL_WORDS = {
    int(number): str(word)
    for number, word in _ENGLISH_COMPOSITOR["ordinal_words"].items()
}


#: The English ordinal words, casefolded, for `_label_core` -- built once.
_ENGLISH_ORDINALS = frozenset(str(w).casefold() for w in _ORDINAL_WORDS.values())


def _active_ordinal_words():
    """The ACTIVE pack's ordinal words, English where it has none. Bound
    from the English card at import, a Japanese collision read
    "secondの見知らぬ人物" (2026-10-20)."""
    try:
        return {int(k): str(v) for k, v in dict(
            _compositor("ordinal_words")).items()}
    except Exception:
        return dict(_ORDINAL_WORDS)


def _ordinal_word(n):
    words = _active_ordinal_words()
    if n in words:
        return words[n]
    if n in _ORDINAL_WORDS:
        return _ORDINAL_WORDS[n]
    suffix = "th" if 10 <= (n % 100) <= 20 else \
        {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _ordinal_label(label, n):
    """"the person of unremarkable appearance" (2) -> "the second person of
    unremarkable appearance".

    The last-resort distinguisher between bodies whose own appearances cannot
    tell them apart. It was a bare index -- "the person of unremarkable
    appearance (2)" -- which is an ENGINE device, and Layer B renders prose:
    the string reached a player view verbatim and one narrator model copied it
    onto the page ("The person of unremarkable appearance (2) speaks in a
    flat, appraising voice"), while another paraphrased it away. Neither model
    misbehaved; the view contained it.

    An ordinal is the honest distinguisher because it distinguishes by NOTHING
    the observer has not already got: they can see three bodies, and counting
    them adds no attribute, no history and no identity. Position and posture
    read better in one sentence and are rejected for two reasons -- they
    change within the beat, so the same stranger would stop being the same
    stranger across sentences, and they are separately admitted percepts, so
    folding them into the referring expression would state them again in
    sentences whose channel never carried them.
    """
    label = str(label or "").strip()
    word = _ordinal_word(n)
    # The pack says how an ordinal sits on a label: English "the second
    # <label less its article>", Japanese "2番目の<label>". The English form
    # was hard-coded, so two identical Japanese strangers read "the 2番目
    # 見知らぬ人物" (2026-10-20).
    articles = sorted((str(a) for a in _compositor("articles")), key=len,
                      reverse=True)
    core = label
    for article in articles:
        if label.lower().startswith(article.lower() + " "):
            core = label[len(article) + 1:]
            break
    return _t("ordinal_label", ordinal=word, label=core)


def _ladder_of(scene, name, appearance, aliases, role, noun):
    """`common.stranger_label_ladder` for one stranger, once per read pass
    over `scene` (`world.scene_memo`): it depends only on the stranger and
    the active pack, and was recomputed for every observer at every call
    site -- ~3 ms a body, so a room of six mutual strangers paid it some
    thirty times a stage (audit agents_composer E1, 2026-11-01). Outside a
    pass, or with no scene, it runs as before. The ladder is read, never
    written, by its one caller."""
    def build():
        return stranger_label_ladder(
            name, appearance, aliases, role=role, head_noun=noun or None)
    if scene is None:
        return build()
    try:
        key = ("stranger_label_ladder", current_language_id.get(), str(name),
               str(appearance or ""), tuple(str(a) for a in aliases or ()),
               str(role or ""), str(noun or ""))
    except TypeError:
        return build()
    from world.scene_memo import scene_memo
    return scene_memo(scene, key, build)


def assign_stranger_labels(bodies, scene=None):
    """name -> distinguishing label, chosen jointly against the others present.

    `bodies` is ``[(name, appearance, aliases)]`` -- or
    ``[(name, appearance, aliases, role)]`` -- for every co-present body the
    observer does NOT recognize. Starts from `_unknown_actor_label`'s
    short form; when two strangers collide on it, the colliding parties'
    labels are widened from their own appearance summaries until they
    differ -- a summary by the feature phrases it attached to its noun
    (`common.stranger_label_ladder`: "the fox woman with six tails and
    amber eyes" instead of "a second fox woman"), a structured surface by
    its words in axis order (`SURFACE_WIDENING_CAPS`). Only when the
    appearances genuinely cannot distinguish them does the ordinal
    distinguisher survive as the last resort (`_ordinal_label`).

    The optional fourth element is the body's public role noun, exempt from
    the identity strip (`_unknown_actor_label`). Two bodies of one rank still
    collide on it and are told apart by the ordinal, which is honest: an
    observer who can see two ensigns and tell them apart no other way has
    exactly that.
    """
    rows = [tuple(body) + (None,) * (6 - len(tuple(body))) for body in bodies]
    # The optional sixth element is the body's head noun -- what a
    # stranger's eye calls a creature in place of "person" -- which closes
    # a cut description (`_unknown_actor_label`).
    rows = [(name, appearance, aliases, role or "", surface, noun or "")
            for name, appearance, aliases, role, surface, noun in rows]
    labels, ladders = {}, {}
    for name, appearance, aliases, role, surface, noun in rows:
        words = _descriptor_words(surface)
        if words:
            labels[str(name)] = _unknown_actor_label(
                name, appearance, aliases, role=role, surface=surface,
                head_noun=noun or None)
            ladders[str(name)] = [w for w in (
                _label_from_words(words, cap) for cap in SURFACE_WIDENING_CAPS)
                if w]
            continue
        # A SUMMARY WIDENS THROUGH ITS OWN CLAUSES. The label is a noun
        # phrase and the steps are the feature phrases the summary attached
        # to its noun, one at a time ("the fox woman with six tails" -> "...
        # and amber eyes"), so no step is ever a cut inside a phrase.
        base, wider = _ladder_of(scene, name, appearance, aliases, role, noun)
        labels[str(name)] = base
        ladders[str(name)] = wider
    for step in range(max((len(l) for l in ladders.values()), default=0)):
        collided = _collided_names(labels)
        if not collided:
            return labels
        for name in collided:
            ladder = ladders.get(name) or []
            if step < len(ladder):
                labels[name] = ladder[step]
    collided = _collided_names(labels)
    if collided:
        seen = {}
        for name, label in labels.items():
            if label in seen:
                seen[label] += 1
                labels[name] = _ordinal_label(label, seen[label])
            else:
                seen[label] = 1
    return labels


#: The word caps a structured SURFACE's label widens through on collision
#: (`_label_from_words`); a summary widens by clauses instead.
SURFACE_WIDENING_CAPS = (6, 8, 10, 14)


def _collided_names(labels):
    by_label = {}
    for name, label in labels.items():
        by_label.setdefault(label, []).append(name)
    out = []
    for label, names in by_label.items():
        if len(names) > 1:
            out.extend(names)
    return out


def observer_display_map(scene, observer_name, co_present, known,
                         senses=None):
    """canonical name -> what THIS observer may call them, for every
    co-present body. Recognition through the `known` ledger; a stranger gets
    a distinguishing appearance descriptor; a disguised body whose truth this
    observer is not in `known_to` for is treated as unrecognized however well
    the observer knows the name.

    A STRANGER'S DESCRIPTOR IS AN APPEARANCE FACT AND IS GATED ON SIGHT.
    This map is the single source every other builder in this module reads
    for what to call a body -- poses, acts, speech attribution, region
    labels, scent sources -- and it was the only one of the three renderers
    naming bodies that never consulted `visual_level_between`. The other two
    (`presence_percepts` here, `_co_present_company` in perception) both
    subtracted -- and the second of them now reads its labels from HERE
    rather than restating the rule, so there is one source and not three.
    This one expanded, so one body arrived in one composed view
    under two names at once: the silhouette the presence line admitted, and
    the build-and-age epithet every following clause used. Measured live: an
    observer read both, counted a person who was not there, and spent the
    beat looking for them. Counting one body twice is the mild reading; the
    firewall reading is that a descriptor cut from an appearance summary
    hands a silhouette-holder the build and the age a silhouette does not
    show.

    Three tiers, and the two degraded ones are deliberately different words:

    * `full` -- the appearance descriptor, jointly assigned against the
      other bodies seen in full (`assign_stranger_labels`).
    * anything else with a visual channel -- the fixed silhouette label. Two
      silhouettes deliberately COLLIDE on it: an observer who cannot tell
      them apart must not be handed a view that can, and the label is one of
      `generic_labels`, which is what keeps it out of memory as an entity.
      A body carrying a STRUCTURED surface (`world.charter_surface`) is the
      exception the structure earns: its silhouette tier -- stature, build,
      the outline of what is worn -- is what a silhouette genuinely shows,
      so the label is composed from that tier and nothing else, and two
      bodies whose silhouettes read the same still collide onto the fixed
      label. An appearance SUMMARY stays at the fixed label at this level,
      because unsorted prose cannot say which of its facts a silhouette
      carries.
    * `none` -- no visual channel at all, so not even a figure. The body is
      here through some other channel (a smell, a voice) and gets the
      appearance-free fallback the standing-percept builder already uses in
      the same position.

    `senses` is the observer's sense card, graded through `_sense_graded`
    exactly as `presence_percepts` grades it: an impaired eye that turns
    `full` into `shapes` must take the descriptor with it, or the split
    reopens one card down.
    """
    recognized = set((known or {}).get(observer_name) or [])
    strangers, silhouettes = [], []
    out = {}
    for body in co_present or []:
        name = str(body.get("name") or "")
        if not name or name == observer_name:
            continue
        hidden = disguise_breaks_recognition(
            body.get("disguise_known_to"), observer_name,
            body.get("disguise_conceals_identity"))
        if not hidden and _recognizes(name, recognized):
            # DEGRADED SIGHT COSTS DETAIL, NOT ACQUAINTANCE -- the same rule
            # `presence_percepts` states at length. A name is knowledge the
            # observer already holds; the dark takes the face, not the name.
            out[name] = name
            continue
        level = _sense_graded(
            visual_level_between(scene, observer_name, name, senses),
            "sight", senses)
        if level == "full":
            strangers.append(
                (name, body.get("appearance"), body.get("aliases") or [],
                 str(body.get("role") or ""), body.get("surface"),
                 str(body.get("noun") or "")))
        elif level == "none":
            out[name] = _unfamiliar_person()
        else:
            silhouettes.append((name, body.get("surface"), level))
    out.update(assign_stranger_labels(strangers, scene=scene))
    out.update(_silhouette_labels(silhouettes))
    return out


def _silhouette_labels(silhouettes):
    """name -> label for the bodies seen short of full sight. A structured
    surface yields its silhouette tier (`charter_surface.surface_label`);
    anything else, and any two silhouettes that read the same, is the fixed
    dim-figure label -- the honest rendering of "cannot tell them apart"."""
    from language_runtime import compositor_text
    from world.charter_surface import surface_label

    labels = {}
    for name, surface, level in silhouettes:
        described = surface_label(surface, level) if surface else ""
        labels[name] = (str(compositor_text("unknown_actor",
                                            description=described))
                        if described else _dim_figure())
    for name in _collided_names(labels):
        labels[name] = _dim_figure()
    return labels


# A body seen only as shapes gets a fixed label, because there is nothing
# distinguishing to say about it -- that is the honest rendering of
# `shapes`. But three of them in one room rendered as the same sentence
# three times: referentially indistinguishable AND reading as a stutter
# (282 views in the corpus replay). The plural is kept beside the singular
# so the two can never drift apart.
# Read at USE time, from the ACTIVE pack. Bound from the English pack at
# import before, so a Japanese reader in a dim room was told about "an
# indistinct figure" -- and `generic_labels` (which filters these out of
# memory entities) is per-pack, so the English form also got indexed as if it
# named somebody. The English compat export stays for tests and audits
# (`DIM_FIGURE`, read by three test files); its plural had no reader anywhere
# and went (audit agents_composer F11, 2026-11-01).
DIM_FIGURE = str(_ENGLISH_COMPOSITOR["dim_figure"])


def _dim_figure(plural=False):
    return str(_compositor("dim_figures" if plural else "dim_figure"))


def _unfamiliar_person():
    from language_runtime import compositor_text
    return str(compositor_text("unknown_actor_fallback"))


def _visible_room_label(scene, name):
    """The display name of the room a body is standing in, or "".

    Used only for a body seen from ANOTHER room, where "close by" and "across
    the room" are both false. Naming the room is the one distance phrasing that
    is true through a doorway, a grille and a pane of glass alike.
    """
    room_id = room_of(scene, name)
    if not room_id:
        return ""
    room = (scene.get("rooms") or {}).get(room_id)
    label = str((room or {}).get("name") or room_id).strip()
    return label


def _size_label(scene, observer_name, name):
    """How big that body is RELATIVE TO THIS ONE, as a closed engine token.

    Minted only from `size_relation`'s own predicates, extreme-first because
    the hand-held readings are a strict subset of the liftable ones. Returns
    None for every ordinary pair by construction -- all four predicates are
    false between 0.5x and 2.0x -- so a scene that never writes a `scales`
    entry composes byte-identically.

    A size STATEMENT starts at 2x while DETAIL stops resolving at 4x, and the
    two thresholds are deliberately different: between them the view says how
    big the other is and still delivers texture, because knowing someone is
    twice your size is not the same question as whether you can read their
    skin. Do not tidy them into agreement.
    """
    rel = size_relation(scene, observer_name, name)
    if rel["other_fits_in_actors_hand"]:
        return "palm_sized"
    if rel["fits_in_other_hand"]:
        return "hand_holds_you"
    if rel["can_lift_other"]:
        return "much_smaller"
    if rel["can_be_lifted_by_other"]:
        return "much_larger"
    return None


#: WHERE A BODY SORTS IN A ROLL-CALL, near to far. The tier is the coarse
#: answer and is always available; the cell distance separates two bodies
#: inside one tier. `beyond` is another room and closes the list.
#:
#: D4 (review 2026-09-07): the sentence that enumerates who is present listed
#: bodies in scene-dict order, so the narrator was handed "A at the far door,
#: B at your elbow, C across the hall" and invented its own arrangement --
#: measured, a body at the other door narrated "on my right" (UNBUILT 1.149).
#: This ORDERS and never withholds: every body the observer can see is still
#: named, in the same clause, with the same words.
_PRESENCE_DEPTH_TIERS = {"within_reach": 0, "near": 1, "across": 2,
                         "beyond": 3}


def _presence_depth(scene, observer_name, name):
    """How far this body is from the observer in CELLS, squared, or None
    when either body is unmeasured.

    Squared because the only thing it is ever compared to is another one of
    these -- it decides an order and never reaches a sentence, so a
    monotonic function of the distance is the distance. None sorts last
    within its tier (`_presence_sort_key`), which leaves an unmeasured pair
    exactly where the caller put it: a room with no geometry renders byte
    for byte what it rendered before.
    """
    here = body_cell(scene, observer_name)
    there = body_cell(scene, name)
    if here is None or there is None:
        return None
    return (there[0] - here[0]) ** 2 + (there[1] - here[1]) ** 2


def _presence_sort_key(percept):
    """(tier rank, cell distance) for one presence percept. Unknown tier and
    unmeasured distance both sort LAST, so nothing this cannot measure is
    moved past something it can."""
    data = percept.data or {}
    depth = data.get("depth")
    return (_PRESENCE_DEPTH_TIERS.get(str(data.get("tier") or ""), 9),
            float("inf") if depth is None else float(depth))


def presence_percepts(scene, observer_name, co_present, display_map,
                      senses=None):
    """Presence -- a tier, a side, an arc -- for every co-present body the
    observer can SEE. Subtracts: a body `visual_level_between` answers "none"
    for (unlit, concealed by containment, behind a barrier) does not arrive;
    a body in the observer's rear arc gives no new visual detail and is not
    admitted (sound still rides the event channels); a body seen only as
    shapes is a bare figure.

    Adds one thing, and it is the only addition here: RELATIVE MAGNITUDE. It
    is a standing presence fact the observer's own eyes have and no channel
    was delivering, so it rides the presence percept the way tier, side and
    arc already do.

    The list comes back NEAR TO FAR (D4, review 2026-09-07): tier rank
    first, measured cell distance inside a tier, stable everywhere it
    cannot measure. The order is minted here rather than in a renderer
    because a body's place in a roll-call is an arrangement, not a wording
    -- the same rule this module already states for `aim_worth_naming` and
    for where the halves of a description sit -- and because every pack's
    adapter is a second renderer by construction: the English one sorted
    its own groups and the ja one orders by list index, so a rule left in
    English reached one page of two (measured: EN "Aoi is within arm's
    reach and Ben is across the room.", JA far-first, same percepts)."""
    out = []
    for body in co_present or []:
        name = str(body.get("name") or "")
        if not name or name == observer_name:
            continue
        level = _sense_graded(
            visual_level_between(scene, observer_name, name, senses),
            "sight", senses)
        if level == "none":
            continue
        tier = proximity_rel(scene, observer_name, name)
        room = None
        if tier is None:
            # NOT "not present" -- `proximity_rel` measures WITHIN a room, so
            # None means "not in this one". A body the observer can plainly
            # see, through a window, a grille, a one-way mirror or an open
            # doorway, was dropped here for want of a within-room tier: the
            # engine handed the mind the adjacent ROOM and never anyone
            # standing in it. Live, an interviewer watching through
            # observation glass received the cell and not the woman in it.
            #
            # `visual_level_between` above has already decided this is visible
            # and already applies the cross-room cap (the opening's view
            # cone), so the only thing missing was somewhere to
            # put the distance. It goes in as the room they are in, which is
            # the true answer and the one that stays true whatever the barrier
            # is made of.
            room = _visible_room_label(scene, name)
            if not room:
                continue
            tier = "beyond"
        arc = entity_arc(scene, observer_name, name)
        if arc == "rear":
            continue                       # no new visual detail from behind
        # WHAT STANDS BETWEEN. `visual_level_between` above has already
        # refused a body the line does not reach at all (the FOV layer is
        # folded into that one sight decision, so no second copy of the
        # rule lives here). What survives is the PARTIAL case -- a body seen
        # over a counter from the waist up -- and a measured side where the
        # anchor-bearing approximation had none. Both subtract-or-qualify;
        # neither admits.
        fov = body_visibility(scene, observer_name, name)
        behind = fov.get("occluded_by") if fov.get("hidden_below") else None
        shows = fov.get("hidden_below")
        # DEGRADED SIGHT COSTS DETAIL, NOT ACQUAINTANCE. Knowing who has
        # been standing in the room with you is knowledge you already have;
        # the dim light takes their face, not their name. Rendering every
        # recognised body as "an indistinct figure" the moment a lamp gutters
        # would under-grant, and read as amnesia.
        #
        # An UNRECOGNISED body at `shapes` is the opposite case and gets the
        # fixed label rather than its appearance descriptor: the descriptor
        # is built from the appearance summary, and a silhouette cannot show
        # fox ears. `display_map` answers recognition by construction --
        # it maps a recognised body to its own name and a stranger to a
        # descriptor (`observer_display_map`).
        display = display_map.get(name)
        if level == "full":
            label = display or _unfamiliar_person()
        else:
            # The map already answers the degraded case by construction:
            # the name for a recognised body, a silhouette-tier descriptor
            # for a stranger with a structured surface, the fixed label
            # for everyone else (`observer_display_map`).
            label = display or _dim_figure()
        side = entity_side(scene, observer_name, name) or (
            fov.get("side") if fov.get("basis") == "line" else None)
        # `body` is the opaque per-body ledger key, carried so the
        # orchestrator can answer "whose presence did this observer's view
        # get composed about" from the percepts themselves rather than by
        # re-running the subtraction above -- a second copy of an admission
        # rule is a classifier waiting to drift. Opaque by `body_key`'s own
        # contract: a canonical name never rides a Percept, even as
        # bookkeeping.
        # A closed engine token carrying no canonical name, so `body_key`'s
        # IR invariant still holds. Absent rather than null when there is no
        # gap, so an unscaled scene's percept record is unchanged.
        size = _size_label(scene, observer_name, name)
        _depth = None if room else _presence_depth(scene, observer_name, name)
        # WHAT THE BEAM IS ON, when the beam is the observer's own (D5).
        # `light_shape` can name only the room's furniture; the case that
        # motivated the item was a hand lamp held on a body for five beats
        # (chat 117, 59-62) with nothing on the page but the lamp. Same-room
        # only, by the predicate's own contract.
        _beam = (not room) and held_beam_falls_on(scene, observer_name, name)
        # WHERE A BODY STANDS IS AS OBSERVABLE AS THAT IT IS STANDING.
        # The view named the OBSERVER'S own station and never anybody
        # else's: in a two-hander whose whole geometry is one room, Halla's
        # view read "You are standing beside the table ... Tobin Renn is
        # close by" for twenty-one turns while the scene held
        # `stations = {Halla: table, Tobin: hearth}`, and the narrator,
        # holding one anchor and needing two, put the man at the hearth
        # beside the table on the story's first page (the long quiet room,
        # 2026-09-05).
        #
        # Same room only, for the reason `pose_percepts` declines a pose
        # across a barrier: the anchor is a piece of furniture in a room the
        # observer is not in, and seeing that somebody beyond a doorway is
        # standing is not seeing what they are standing at. A `beyond` tier
        # already names their room, which is the distance that WAS measured.
        station = None
        if room is None:
            at = str((effective_station(scene, name) or {}).get("at") or "")
            here = room_of(scene, name)
            record = (effective_anchors(scene, here) or {}).get(at) \
                if (at and here) else None
            if record is not None:
                # Spliced like every other authored description
                # (`_noun_phrase`): this was the one reader that took the
                # desc raw, so a sentence-shaped anchor rendered "at A flat
                # stretch of dark, packed sand damp from the receding
                # surf.." -- sentence case and two stops (chat 123 turn 9).
                station = (_noun_phrase(str((record or {}).get("desc") or ""))
                           or at.replace("_", " "))
        out.append(Percept(
            kind="presence", channel="sight",
            source_label=label,
            fidelity="full" if level == "full" else "degraded",
            data={"tier": tier, "side": side, "arc": arc, "sight": level,
                  "body": body_key(name),
                  # ORDERING ONLY, never a sentence: how far off this body
                  # is in cells, so the roll-call reads near to far (D4).
                  # Absent when either body is unmeasured. Deliberately NOT
                  # in the dedupe key below -- a body that shuffled one cell
                  # has not changed for this observer, and hashing the
                  # distance would re-announce it every beat.
                  **({"depth": _depth} if _depth is not None else {}),
                  # WHETHER THIS OBSERVER CAN NAME THEM. `display_map`
                  # answers recognition by construction -- a recognised body
                  # maps to its own name, a stranger to a descriptor -- and
                  # perception's `company` block already reports the same
                  # comparison. Carried here so the view can decide whether
                  # a presence is background without re-deriving it.
                  "known": bool(display) and display == name,
                  **({"size": size} if size else {}),
                  **({"at": station} if station else {}),
                  **({"room": room} if room else {}),
                  **({"in_beam": True} if _beam else {}),
                  **({"behind": behind, "shows": shows} if behind else {})},
            salience=0.35,
            dedupe_key=standing_key(
                "presence", (body_key(name),),
                # SWINGING THE BEAM OFF A BODY IS NEWS, and onto one is
                # more so, so the aim is content and the presence reads
                # `changed` on the beat it moves (D5). APPENDED rather than
                # placed, like every optional part here: a body nobody is
                # pointing a lamp at hashes to exactly what it hashed to
                # before, so no live chat spends an upgrade beat
                # re-announcing everyone standing in it.
                (tier, arc, level, size or "")
                + (("beam",) if _beam else ())
                + ((station,) if station else ())
                + ((behind, shows) if behind else ())),
        ))
    # NEAR TO FAR (D4). Stable, so an unmeasured room -- every body sharing
    # one key -- comes back in exactly the order the caller gave it.
    return sorted(out, key=_presence_sort_key)
