"""The deterministic perception composer: percept selection and rendering.

Two layers with a typed seam (design_notes/03-composer-design.md, 00-PLAN.md
Phase 2):

**Layer A -- percept builders (`build_*_percepts`). The information
boundary.** Pure functions of (scene + typed events + known/awareness) that
return an ordered ``list[Percept]``. Every admission decision happens here,
on structured data, before any prose exists: delivery gates, hear/sight/scent
levels, containment, rear-arc, concealment, recognition labels. Nothing
outside a Percept ever reaches the renderer, and no Percept field carries a
fact the observer has no channel to -- that property is unit-tested on the IR
itself (tests/test_composer.py), not asserted by regex over prose.

**Layer B -- rendering (`render_view` / `render_episode`).** Decision-free
realisation from percepts. The signature takes percepts and mode parameters,
nothing else -- no scene, no DB -- so a rendering path structurally cannot ADD
information (design_notes/03 section 5.3). The sentence grammar reuses the
renderers already in production: `_inject_dialogue`'s dialogue grammar,
`_observable_predicate`, `contact_sensation`/`substance_event_clause` clauses
(delivered as data on the percept), and `_compose_residue_view`.

Three render modes over one percept list, because the view has three
consumers with different needs:

- ``character`` -- full standing state every beat. A character agent is a
  stateless LLM call; if it is not in context, the mind does not have it.
- ``player`` -- delta only: what CHANGED, plus this beat's events. Standing
  state is re-rendered only when its content changed (the dedupe key hashes
  the content) or on an explicit look/examine intent (``full_render=True``).
- ``memory`` -- `render_episode`: the salient delta, minted from the IR in
  first person, with typed entities. A percept list that is all unchanged
  standing state is a NON-EVENT and returns "" -- nothing is minted (the
  "You are in an unspecified area." pathology, 812 corpus rows, dies here).

Deliberately NO lexical-variation machinery (note 03 section 2.6's leverage
ranking was measured wrong): plain templates plus discourse rules. Repetition
is solved by change-tracking, not synonyms.

Module discipline: imports `agents/common.py`, `spatial.py`, `scene.py` only
-- never another role module. `agents/perception.py` orchestrates: it builds
the inputs (it owns the spatial relation maps and the stage contracts) and
calls down into this module, exactly as it calls into `common`.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from spatial import (
    _clean_pose,
    entity_arc,
    entity_side,
    hear_level,
    proximity_rel,
    same_subject,
    visual_level_between,
)

from .common import (
    _appearance_as_prose,
    _base_from_third_person_s,
    _compose_residue_view,
    _identity_token_set,
    _inject_dialogue,
    _muffled_fragment,
    _observable_predicate,
    _quote_body,
    _recognizes,
    _self_second_person,
    _unknown_actor_label,
    _QUOTED_SPAN_RE,
)


# --------------------------------------------------------------------------
# The IR
# --------------------------------------------------------------------------

PERCEPT_KINDS = (
    "environment", "presence", "appearance", "act", "speech", "sensation",
    "substance", "body_region", "body_state", "crossing", "residue",
    "ambient",
)

CHANNELS = ("sight", "hearing", "touch", "interoception", "smell", "mixed")


@dataclass(frozen=True)
class Percept:
    """One admitted percept. `source_label` is ALREADY recognition/disguise
    gated -- a canonical name only ever appears here when the observer has
    earned it. `data` carries only surfaces the observer has a channel to,
    at the admitted fidelity (a fragment percept holds the fragment, never
    the full quote body)."""
    kind: str
    channel: str
    source_label: str = ""
    fidelity: str = "full"          # full|degraded|fragment|trace
    data: dict = field(default_factory=dict)
    salience: float = 0.4
    suddenness: float = 0.1
    order_key: int | None = None    # declared/beat order; None = standing state
    dedupe_key: str = ""


def _short_hash(*parts):
    joined = "\x1f".join(str(p or "") for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]


def body_key(name):
    """Opaque, stable per-body ledger key. Canonical names never ride a
    Percept -- not even as bookkeeping -- so the IR invariant ("no field
    carries a fact the observer has no channel to") is checkable by simple
    string containment over the whole record."""
    return _short_hash("body", str(name or "").strip().casefold())


# --------------------------------------------------------------------------
# Referring expressions
# --------------------------------------------------------------------------

_LABEL_DANGLING = {
    "a", "an", "the", "with", "of", "and", "or", "in", "on", "at", "to",
    "for", "from", "by", "her", "his", "their", "its", "as",
}


def _descriptor_words(name, appearance, aliases=None):
    """The full name-stripped content word list of an appearance summary --
    the raw material a stranger label is cut from."""
    text = _appearance_as_prose(appearance)
    if not text:
        return []
    name_tokens = _identity_token_set(name, aliases)
    cleaned = re.sub(r"^(a|an|the)\s+", "", text.strip(), flags=re.I)
    cleaned = cleaned.replace(",", " ").replace(";", " ")
    words = [w for w in cleaned.split()
             if re.sub(r"[^\w]", "", w).casefold() not in name_tokens]
    while words and words[0].lower() in ("a", "an", "the"):
        words = words[1:]
    return words


def _label_from_words(words, cap):
    """Cut a label at `cap` words, dropping a trailing function word.

    KNOWN WART, and left alone on purpose: the cap can still land on a
    dangling adjective — "a tall woman in a long grey coat" gives "the tall
    woman in a long" at five words. Two smarter rules were tried and both
    made it worse. Walking the cut back past the last connective produced
    labels SHORTER than the base ("the person" from "the person of
    unremarkable appearance"), which then collided, which drove
    `assign_stranger_labels` up through cap 8/10/14 into run-ons like "the
    person of unremarkable appearance wearing wrinkled lab coat station
    jumpsuit comm badge rumpled tired" — measured across 83 views on the
    corpus, so decidedly worse than the wart.

    Cutting a noun phrase correctly needs to know where the noun is, and
    nothing here does. The real fix is to cut on the appearance summary's
    own comma-separated clauses instead of a flat word count, which is a
    change to `_descriptor_words` and the collision escalation together,
    not to this line.
    """
    take = list(words[:cap])
    while take and take[-1].lower() in _LABEL_DANGLING:
        take = take[:-1]
    if not take:
        return ""
    return "the " + " ".join(take).rstrip(".;:").lower()


def assign_stranger_labels(bodies):
    """name -> distinguishing label, chosen jointly against the others present.

    `bodies` is ``[(name, appearance, aliases)]`` for every co-present body
    the observer does NOT recognize. Starts from `_unknown_actor_label`'s
    short form; when two strangers collide on it, the colliding parties'
    labels are widened word by word from their own appearance summaries until
    they differ ("the fox woman with six tails" instead of "the fox woman
    (2)"). Only when the appearances genuinely cannot distinguish them does
    the numeric suffix survive as the last resort.
    """
    labels = {}
    for name, appearance, aliases in bodies:
        labels[str(name)] = _unknown_actor_label(name, appearance, aliases)
    words = {str(name): _descriptor_words(name, appearance, aliases)
             for name, appearance, aliases in bodies}
    for cap in (6, 8, 10, 14):
        collided = _collided_names(labels)
        if not collided:
            return labels
        for name in collided:
            wide = _label_from_words(words.get(name) or [], cap)
            if wide:
                labels[name] = wide
    collided = _collided_names(labels)
    if collided:
        seen = {}
        for name, label in labels.items():
            if label in seen:
                seen[label] += 1
                labels[name] = f"{label} ({seen[label]})"
            else:
                seen[label] = 1
    return labels


def _collided_names(labels):
    by_label = {}
    for name, label in labels.items():
        by_label.setdefault(label, []).append(name)
    out = []
    for label, names in by_label.items():
        if len(names) > 1:
            out.extend(names)
    return out


def observer_display_map(scene, observer_name, co_present, known):
    """canonical name -> what THIS observer may call them, for every
    co-present body. Recognition through the `known` ledger; a stranger gets
    a distinguishing appearance descriptor; a disguised body whose truth this
    observer is not in `known_to` for is treated as unrecognized however well
    the observer knows the name."""
    recognized = set((known or {}).get(observer_name) or [])
    strangers = []
    out = {}
    for body in co_present or []:
        name = str(body.get("name") or "")
        if not name or name == observer_name:
            continue
        known_to = body.get("disguise_known_to")
        undisguised_to_me = (
            known_to is None
            or str(observer_name).casefold() in known_to)
        if undisguised_to_me and _recognizes(name, recognized):
            out[name] = name
        else:
            strangers.append(
                (name, body.get("appearance"), body.get("aliases") or []))
    out.update(assign_stranger_labels(strangers))
    return out


# --------------------------------------------------------------------------
# Layer A -- shared admission helpers
# --------------------------------------------------------------------------

def concealed_from_observer(entry, observer_name, observer_id=None):
    """Is this concealed event element withheld from this observer?

    An empty conceal_from means hidden from every non-actor; a populated list
    is an explicit excluded audience. (The onset/outcome model paths apply
    the same rule through perception's `_concealed_from_perceiver`.)"""
    if entry.get("visibility") != "concealed":
        return False
    refs = {
        str(value).strip().casefold()
        for value in (entry.get("conceal_from") or [])
        if str(value or "").strip()
    }
    if not refs:
        return True
    return bool(
        "*" in refs
        or str(observer_name or "").casefold() in refs
        or str(observer_id or "").casefold() in refs
        or f"character:{observer_id}".casefold() in refs
    )


def line_hear_level(entry, rel, observer_name, proximity=None):
    """Audibility of one dialogue entry to an observer.

    Ordinary spatial hearing (`hear_level`) decides first -- including the
    `proximity` downgrade. Pass only a MEASURED tier
    (`spatial.measured_proximity_rel`): "near" is mostly a default, and a
    default must not silence a conversation.

    Hearing only ever gets OVERRIDDEN in one direction -- a line it would
    DROP is rescued to 'full' when the line is a TRANSMISSION addressed to
    THIS observer (explicit medium:'comm', or a by-name spoken-volume
    exchange across a barrier). An enclosure is never shape-rescued: being
    named by a voice beyond the mass around you creates no channel through
    it. The comm path carries only the VOICE; the caller sets can_see
    separately."""
    base = hear_level(rel, entry.get("volume", "normal"), proximity=proximity)
    if base != "none":
        return base
    if not _addresses(entry.get("intended_target"), observer_name):
        return base
    if str(entry.get("medium") or "").lower() == "comm":
        return "full"
    if rel.get("enclosed_from_source") or rel.get("source_enclosed"):
        return base
    if str(entry.get("volume", "normal")).lower() in ("normal", "loud", "shout"):
        return "full"
    return base


def _addresses(intended_target, observer_name):
    if not intended_target or not observer_name:
        return False
    targets = intended_target if isinstance(intended_target, (list, tuple)) \
        else [intended_target]
    on = str(observer_name).casefold()
    return any(str(t).casefold() == on for t in targets)


_SUDDEN_VERBS = frozenset({
    "lunge", "leap", "slam", "snap", "erupt", "explode", "scream", "shatter",
    "fall", "collapse", "strike", "hit", "shoot", "fire", "grab", "seize",
    "run", "sprint", "bolt", "dash", "charge", "throw", "jerk",
})


def _surface_suddenness(surface):
    words = str(surface or "").casefold().split()
    if not words:
        return 0.1
    first = re.sub(r"[^\w]", "", words[0]).rstrip("s")
    return 0.6 if first in _SUDDEN_VERBS else 0.1


# --------------------------------------------------------------------------
# Layer A -- standing-state percepts
# --------------------------------------------------------------------------

def environment_percept(room_id, room_name, room_notes="", light=""):
    """The room as standing state -- or None when the observer has no
    resolvable room. A mind in unloaded space perceives NOTHING here; the
    old path fabricated "You are in an unspecified area." for it, which
    became 812 identical memory rows (97.3% collision). No room, no
    percept, no view sentence, no episode."""
    if not room_id or not str(room_name or "").strip() \
            or str(room_name).strip().casefold() == "an unspecified area":
        return None
    light = str(light or "")
    return Percept(
        kind="environment", channel="sight",
        data={"room_id": room_id, "room_name": room_name,
              "room_notes": room_notes or "", "light": light},
        salience=0.2,
        dedupe_key="env:" + _short_hash(room_id, room_name, room_notes, light),
    )


# A body seen only as shapes gets a fixed label, because there is nothing
# distinguishing to say about it -- that is the honest rendering of
# `shapes`. But three of them in one room rendered as the same sentence
# three times: referentially indistinguishable AND reading as a stutter
# (282 views in the corpus replay). The plural is kept beside the singular
# so the two can never drift apart.
DIM_FIGURE = "an indistinct figure"
DIM_FIGURES = "indistinct figures"


def presence_percepts(scene, observer_name, co_present, display_map):
    """Presence -- a tier, a side, an arc -- for every co-present body the
    observer can SEE. Subtracts: a body `visual_level_between` answers "none"
    for (unlit, concealed by containment, behind a barrier) does not arrive;
    a body in the observer's rear arc gives no new visual detail and is not
    admitted (sound still rides the event channels); a body seen only as
    shapes is a bare figure."""
    out = []
    for body in co_present or []:
        name = str(body.get("name") or "")
        if not name or name == observer_name:
            continue
        level = visual_level_between(scene, observer_name, name)
        if level == "none":
            continue
        tier = proximity_rel(scene, observer_name, name)
        if tier is None:
            continue                       # co-located only
        arc = entity_arc(scene, observer_name, name)
        if arc == "rear":
            continue                       # no new visual detail from behind
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
            label = display or "the unfamiliar person"
        else:
            label = display if display == name else DIM_FIGURE
        side = entity_side(scene, observer_name, name)
        out.append(Percept(
            kind="presence", channel="sight",
            source_label=label,
            fidelity="full" if level == "full" else "degraded",
            data={"tier": tier, "side": side, "arc": arc, "sight": level},
            salience=0.35,
            dedupe_key="presence:" + _short_hash(name, tier, arc, level),
        ))
    return out


_COUNT_NAMES = {1: "a", 2: "two", 3: "three", 4: "four", 5: "five",
                6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten"}


def body_part_percepts(rows):
    """Authored extra body parts -- tails, wings, horns -- already gated.

    Input is `observer_body_regions`' `part_data`: the parts this observer
    may see, with the same vantage/containment/garment decision the phrase
    list was built from. Structured rather than pre-phrased, because the
    composer renders to a reader now and "tail x6 — emerge from the back of
    the waist" is payload grammar.
    """
    out = []
    for label, part in rows or []:
        kind = " ".join(str(part.get("kind") or "").split())
        if not kind:
            continue
        try:
            count = max(1, int(part.get("count", 1)))
        except (TypeError, ValueError):
            count = 1
        out.append(Percept(
            kind="body_part", channel="sight",
            source_label=str(label or "someone"),
            data={"part": kind, "count": count,
                  "at": str(part.get("at") or "torso"),
                  "aspect": str(part.get("aspect") or "back"),
                  "description": " ".join(
                      str(part.get("description") or "").split()),
                  "tucked": bool(part.get("tucked")),
                  "directed_at_self": str(label) == "you"},
            salience=0.3,
            dedupe_key="part:" + _short_hash(
                label, kind, count, part.get("at"), part.get("aspect"),
                part.get("description"), part.get("tucked")),
        ))
    return out


def pose_percepts(scene, observer_name, co_present, display_map):
    """How bodies are arranged: posture, what holds them up, who they are
    against, what pins them.

    Poses were already Director-declared (`state_diff.poses`), already
    normalized (`normalize_scene_poses`) and already living in the scene
    blob beside stations and facing. The only missing hop was this one --
    nothing composed them into a view, so 75 turns of authored arrangement
    reached no mind at all.

    THE GRADE FOLLOWS THE SIGHT, because posture is the one body fact a
    silhouette genuinely does carry: you can see that someone is kneeling
    across a dim room without seeing anything else about them. So a body at
    `shapes` yields posture and nothing else -- no support, no relation, no
    constraint, no authored detail -- and a body at `full` yields the lot.
    Subtractive either way: the fields simply do not become percepts.

    The observer's OWN pose is interoception and always arrives. A body in
    the rear arc does not, matching `presence_percepts` -- you do not see
    how someone behind you is sitting.
    """
    out = []
    for name, raw in ((scene or {}).get("poses") or {}).items():
        pose = _clean_pose(raw)
        if pose is None:
            continue
        is_self = same_subject(scene, name, observer_name)
        if is_self:
            level, label = "full", "you"
        else:
            if not any(same_subject(scene, name, body.get("name"))
                       for body in co_present or []):
                continue
            # A POSE IS NEVER MORE REACHABLE THAN A PRESENCE. Caught by a
            # pose-bearing drive scenario, not by the corpus: Kai stood in
            # the yard, Reya knelt in the forge behind a closed door, and
            # his view read "Reya is kneeling on the anvil block". Presence
            # had already declined to mention her -- `proximity_rel`
            # answers None across rooms -- while this gate checked only
            # sight and arc, so a body he was not even told was there
            # arrived with her posture, her support and her breathing.
            #
            # Same rule as `presence_percepts`, and for the same reason: how
            # a body is held is finer-grained than the fact of it, so it
            # cannot outrun it.
            if proximity_rel(scene, observer_name, name) is None:
                continue
            level = visual_level_between(scene, observer_name, name)
            if level == "none":
                continue
            if entity_arc(scene, observer_name, name) == "rear":
                continue
            label = display_map.get(name) or "someone"
        data = {"posture": pose["posture"]}
        if level == "full":
            for f in ("support", "relation", "constraint", "detail"):
                data[f] = pose[f]
            other = pose["relative_to"]
            if other:
                data["relative_to"] = (
                    "you" if same_subject(scene, other, observer_name)
                    else display_map.get(other) or "someone")
        if not any(data.values()):
            continue
        out.append(Percept(
            kind="pose",
            channel="interoception" if is_self else "sight",
            source_label=label,
            fidelity="full" if level == "full" else "degraded",
            data={**data, "directed_at_self": is_self},
            salience=0.3,
            dedupe_key="pose:" + _short_hash(
                name, *(str(data.get(f) or "") for f in _POSE_RENDER_FIELDS)),
        ))
    return out


_POSE_RENDER_FIELDS = ("posture", "support", "relative_to", "relation",
                       "constraint", "detail")


def appearance_percept(source_name, label, description, *, force=False):
    """The FULL authored appearance -- discovery/structural-change data, first
    mention only (the render ledger gates re-emission; ``force=True`` marks a
    structural change this beat, which re-earns the description).
    `description` must already be identity-safe for this observer
    (name-stripped when the observer does not recognize the body). The
    canonical name is folded into an opaque `body_key` for the ledger; it
    never rides the percept."""
    return Percept(
        kind="appearance", channel="sight", source_label=label,
        data={"source_key": body_key(source_name),
              "description": description, "force": bool(force)},
        salience=0.5,
        dedupe_key="described:" + _short_hash(source_name, description),
    )


def body_state_percept(entity_state):
    state = {k: entity_state.get(k) for k in ("posture", "activity", "held_items")
             if entity_state.get(k)}
    if not state:
        return None
    return Percept(
        kind="body_state", channel="interoception", source_label="you",
        data=state, salience=0.3,
        dedupe_key="state:" + _short_hash(
            state.get("posture"), state.get("activity"),
            ",".join(state.get("held_items") or [])),
    )


def contact_percepts(contacts_with_sensation):
    """Standing contact sensations. Input: [(contact_record, sensation_clause)]
    where the clause came from `spatial.contact_sensation(you=observer)` --
    empty for a contact the observer is only watching, so a non-party
    contributes nothing here by construction."""
    out = []
    for contact, clause in contacts_with_sensation or []:
        clause = str(clause or "").strip()
        if not clause:
            continue
        out.append(Percept(
            kind="sensation", channel="touch", source_label="you",
            data={"clause": clause, "directed_at_self": True},
            salience=0.45,
            dedupe_key="contact:" + _short_hash(
                contact.get("actor"), contact.get("actor_part"),
                contact.get("target"), contact.get("target_part"),
                contact.get("manner")),
        ))
    return out


def body_region_percepts(bare_details):
    """Authored bare-surface anatomy, already observer-gated upstream
    (`observer_body_regions` + `_bare_body_details`). Input:
    [(body_label, place, detail)] where body_label is 'you' or an
    observer-safe label."""
    out = []
    for body_label, place, detail in bare_details or []:
        out.append(Percept(
            kind="body_region", channel="sight",
            source_label=str(body_label or "someone"),
            data={"place": place, "detail": detail},
            salience=0.3,
            dedupe_key="region:" + _short_hash(body_label, place, detail),
        ))
    return out


def ambient_percepts(sensory_events, observer_room):
    """Authored opening sensory events, filtered by room scope. An event
    naming a room is admitted only to observers in that room; a roomless
    event is scene ambience."""
    out = []
    for idx, event in enumerate(sensory_events or []):
        if not isinstance(event, dict):
            continue
        room = str(event.get("room") or event.get("room_id") or "")
        if room and observer_room and room != str(observer_room):
            continue
        desc = str(event.get("desc") or event.get("description")
                   or event.get("text") or "").strip()
        if not desc:
            continue
        channel = str(event.get("channel") or "mixed").casefold()
        if channel not in CHANNELS:
            channel = "mixed"
        out.append(Percept(
            kind="ambient", channel=channel, data={"desc": desc},
            salience=0.4,
            dedupe_key="ambient:" + _short_hash(desc),
        ))
    return out


def residue_percepts(level, *, targeted=False, loud_event=False, pain=False):
    """A non-awake mind gets the residue and nothing else."""
    return [Percept(
        kind="residue", channel="interoception", source_label="you",
        fidelity="trace",
        data={"level": level, "targeted": bool(targeted),
              "loud_event": bool(loud_event), "pain": bool(pain),
              "directed_at_self": True},
        salience=0.2,
        dedupe_key="residue:" + _short_hash(level, targeted, loud_event, pain),
    )]


# --------------------------------------------------------------------------
# Layer A -- event percepts
# --------------------------------------------------------------------------

def speech_percept(entry, rel, observer_name, *, display, can_see,
                   proximity=None, order_key=0, observer_id=None):
    """Admit one spoken line for one observer, or None.

    Gates, in order: concealment (absolute exclusion, never a volume),
    audibility (`line_hear_level`, including the comm/addressed rescue).
    The data carries the FIDELITY-DEGRADED surface: a fragment percept holds
    only the muffled fragment the renderer may emit, never the full body --
    so downstream consumers (memory included) structurally cannot outrun the
    view."""
    if concealed_from_observer(entry, observer_name, observer_id):
        return None
    body = _quote_body(entry.get("exact_quote") or entry.get("text"))
    if not body:
        return None
    volume = str(entry.get("volume") or "normal")
    level = line_hear_level(entry, rel, observer_name, proximity=proximity)
    if level == "none" and rel.get("open_group_continuity") \
            and volume.casefold() in ("normal", "loud", "shout"):
        # Compatibility floor for a rerolled checkpoint predating the
        # near-group position repair (mirrors `_inject_onset_speech`). It
        # grants hearing only; sight and every other channel still ride the
        # relation's real spatial fields.
        level = "full"
    if level == "none":
        return None
    data = {
        "level": level,
        "volume": volume,
        "can_see": bool(can_see),
        "conducted": bool(rel.get("inside_source")),
        "tone": str(entry.get("tone") or ""),
        "articulation": str(entry.get("articulation") or ""),
        "directed_at_self": _addresses(
            entry.get("intended_target"), observer_name),
    }
    if level == "fragment":
        data["fragment"] = _muffled_fragment(body)
        fidelity = "fragment"
    else:
        data["body"] = body
        fidelity = "full"
    return Percept(
        kind="speech", channel="hearing", source_label=display,
        fidelity=fidelity, data=data,
        salience=0.75 if volume in ("loud", "shout") else 0.7,
        suddenness=0.5 if volume in ("loud", "shout") else 0.1,
        order_key=order_key,
        dedupe_key="speech:" + _short_hash(entry.get("speaker"), body),
    )


def act_percept(scene, event, observer_name, actor_name, rel, *,
                display, can_see, self_forms=None, order_key=0,
                observer_id=None, surface=None):
    """Admit one action element's observable surface for one observer, or
    None. Gates: concealment, rear arc, sight (an action is visible or it is
    nothing -- a touch-only source contributes sensation percepts instead,
    never an event surface)."""
    if concealed_from_observer(event, observer_name, observer_id):
        return None
    if surface is None:
        from .common import observable_action_text
        surface = observable_action_text(event)
    surface = str(surface or "").strip()
    if not surface:
        return None                       # a mental beat is imperceptible
    if entity_arc(scene, observer_name, actor_name) == "rear":
        return None
    if not can_see:
        return None
    if self_forms:
        surface = _self_second_person(surface, self_forms)
    return Percept(
        kind="act", channel="sight", source_label=display,
        data={"surface": surface,
              "directed_at_self": bool(
                  re.search(r"\byou\b|\byour\b", surface, re.I))},
        salience=0.65,
        suddenness=_surface_suddenness(surface),
        order_key=order_key,
        dedupe_key="act:" + _short_hash(
            event.get("event_id") or "", actor_name, surface),
    )


def substance_percept(event, clause, order_key=0):
    """This beat's substance ADD delta, for a party to it. `clause` came from
    `spatial.substance_event_clause(you=observer)` -- empty for anyone who is
    not a party, so admission is inherited from the clause builder."""
    clause = str(clause or "").strip()
    if not clause:
        return None
    return Percept(
        kind="substance", channel="touch", source_label="you",
        data={"clause": clause, "directed_at_self": True},
        salience=0.55,
        order_key=order_key,
        dedupe_key="substance:" + _short_hash(
            event.get("substance"), event.get("target"),
            event.get("placement"), clause),
    )


# A crossing is not just another event in the queue -- it BOUNDS the beat
# for that body. You cannot hear someone speak before they walk in, and
# their footsteps out do not precede their last word. The outcome stage
# builds its order keys from one running counter over dialogue, then acts,
# then movement, so a body who arrived and spoke rendered as "X says ... X
# comes in." (measured in the corpus replay's prose sample). Arrivals and
# departures therefore sit in bands outside the counter's range rather than
# competing inside it.
_ARRIVAL_BAND = -1_000_000
_DEPARTURE_BAND = 1_000_000


def crossing_percept(mover_name, label, direction, order_key=0):
    """A body entering or leaving the observer's room this beat, already
    channel-gated by the caller (seen at either end of the beat). The
    mover's canonical name is hashed into the dedupe key only.

    `order_key` orders crossings AMONG THEMSELVES; which side of the beat
    they land on is decided here, from the direction (see the band comment
    above), so no caller has to remember to do it."""
    band = _ARRIVAL_BAND if direction == "arrived" else _DEPARTURE_BAND
    return Percept(
        kind="crossing", channel="sight", source_label=label,
        data={"direction": direction},
        salience=0.6, suddenness=0.4,
        order_key=band + order_key,
        dedupe_key="crossing:" + _short_hash(mover_name, direction),
    )


# --------------------------------------------------------------------------
# Layer B -- rendering
# --------------------------------------------------------------------------

_STANDING_ORDER = {
    # Pose sits right after presence: who is here, then how they are
    # arranged. Before appearance, because how a body is held is a fact
    # about this beat and its authored description is a fact about the body.
    "environment": 0, "presence": 1, "pose": 2, "appearance": 3,
    "body_state": 4, "sensation": 5, "body_part": 6, "body_region": 7,
    "ambient": 8,
}

_TIER_PHRASES = {
    "within_reach": "within arm's reach",
    "near": "close by",
    "across": "across the room",
}


# A placeholder holding the position the presence group will occupy, so
# the group can be rendered once the whole set is known without losing
# where it belongs in the discourse order. Identity comparison only.
_PRESENCE_SLOT = ("presence-slot", None)


@dataclass
class RenderedView:
    text: str
    spans: list                 # [(Percept, sentence)]
    standing_keys: set          # dedupe keys of ALL standing percepts seen
    described: set              # source names whose full appearance rendered


def _cap(sentence):
    sentence = str(sentence or "").strip()
    return sentence[:1].upper() + sentence[1:] if sentence else sentence


_COUNT_WORDS = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six",
                7: "Seven", 8: "Eight", 9: "Nine"}


def _presence_clause(p):
    """One body's presence as a bare clause -- no capital, no full stop, so
    it can stand alone or be joined with others."""
    tier = _TIER_PHRASES.get(str(p.data.get("tier")), "here")
    side = p.data.get("side")
    side_clause = f" on your {side}" if side in ("left", "right") else ""
    return f"{p.source_label} is {tier}{side_clause}"


def _join_clauses(clauses):
    if len(clauses) == 1:
        return clauses[0]
    if len(clauses) == 2:
        return f"{clauses[0]} and {clauses[1]}"
    return ", ".join(clauses[:-1]) + f", and {clauses[-1]}"


def _render_presence_group(percepts):
    """Every co-present body the observer can see, as ONE sentence.

    Three things happen here, and all three are why the corpus replay
    called the composed prose staccato:

    * A room with four people in it produced four sentences of identical
      shape. They are one observation -- who is here -- and they read as
      one sentence.
    * Two bodies seen only as shapes produced the same sentence twice.
      Counted, they become "Two indistinct figures are close by", which is
      both shorter and more accurate about what the observer can tell.
    * FIDELITY IS NEVER MIXED. A `degraded` body folded into a `full`
      body's sentence would read as clearly perceived, which is the
      information boundary laundered by a prose choice. So the group
      splits by fidelity first and each half gets its own sentence -- the
      same rule `observations_from_render` applies when it merges atoms.

    Returns [(representative percept, sentence)], at most one per fidelity.
    """
    out = []
    for fidelity in ("full", "degraded"):
        group = [p for p in percepts if p.fidelity == fidelity]
        if not group:
            continue
        clauses, counts = [], {}
        for p in group:
            clause = _presence_clause(p)
            if clause in counts:
                counts[clause] += 1
            else:
                counts[clause] = 1
                clauses.append(clause)
        rendered = []
        for clause in clauses:
            n = counts[clause]
            if n > 1 and clause.startswith(DIM_FIGURE + " "):
                word = _COUNT_WORDS.get(n, str(n))
                rendered.append(
                    f"{word.casefold()} {DIM_FIGURES}"
                    + clause[len(DIM_FIGURE):].replace(" is ", " are ", 1))
            else:
                rendered.append(clause)
        out.append((group[0], _cap(_join_clauses(rendered)) + "."))
    return out


def _render_body_part(p):
    """"Six tails emerge from the back of her waist" -- not "tail x6"."""
    count, kind = p.data["count"], p.data["part"]
    you = p.source_label == "you"
    word = _COUNT_NAMES.get(count, str(count))
    subject = f"{word} {kind}" if count == 1 else f"{word} {kind}s"
    verb = "emerges" if count == 1 else "emerge"
    aspect, at = p.data["aspect"], p.data["at"]
    whose = "your" if you else f"{p.source_label}'s"
    if aspect == "sides":
        where = f"across both sides of {whose} {at}"
    elif aspect in ("left", "right"):
        where = f"from the {aspect} side of {whose} {at}"
    else:
        where = f"from the {aspect} of {whose} {at}"
    sentence = f"{_cap(subject)} {verb} {where}"
    if p.data.get("description"):
        sentence += f", {p.data['description'].rstrip('.')}"
    if p.data.get("tucked"):
        sentence += ", currently beneath clothing"
    return sentence + "."


def _render_pose(p, *, past=False):
    """One body's arrangement as a sentence.

    Built as clauses so a pose with only a posture (a body seen as shapes)
    reads as naturally as one carrying support, relation and constraint --
    the degraded case is a shorter sentence, not a sentence with holes in
    it.

    `past` is for the episode renderer, and the tense is chosen HERE rather
    than patched afterwards: a memory saying "I am kneeling" is a claim
    about now, and regex-ing tense out of finished prose would also reach
    into the authored `detail` text, which is not ours to rewrite.
    """
    you = p.source_label == "you"
    if you:
        subject = "I was" if past else "You are"
    else:
        subject = f"{_cap(p.source_label)} {'was' if past else 'is'}"
    parts = [str(p.data.get("posture") or "").strip()]
    support = str(p.data.get("support") or "").strip()
    if support:
        parts.append(support if support.split()[:1] and support.split()[0] in
                     _POSE_PREPOSITIONS else f"on {support}")
    other = str(p.data.get("relative_to") or "").strip()
    if other:
        relation = str(p.data.get("relation") or "").strip()
        parts.append(f"{relation} {other}" if relation else f"against {other}")
    clause = " ".join(x for x in parts if x).strip()
    if not clause:
        return ""
    sentence = f"{subject} {clause}"
    constraint = str(p.data.get("constraint") or "").strip()
    if constraint:
        sentence += f", {constraint}"
    detail = str(p.data.get("detail") or "").strip()
    if detail:
        sentence += f" — {detail.rstrip('.')}"
    return sentence.rstrip(".") + "."


_POSE_PREPOSITIONS = frozenset({
    "on", "in", "against", "under", "beneath", "over", "across", "atop",
    "beside", "behind", "before", "between", "inside", "onto", "upon",
})


def _render_standing(p):
    if p.kind == "environment":
        parts = []
        if p.data.get("room_name"):
            parts.append(f"You are in {p.data['room_name']}.")
        if p.data.get("room_notes"):
            notes = str(p.data["room_notes"]).strip()
            if notes and notes[-1:] not in ".!?":
                notes += "."
            parts.append(notes)
        light = str(p.data.get("light") or "").casefold()
        if light in ("dim", "low"):
            parts.append("The light is dim.")
        elif light in ("dark", "none", "pitch_black", "black"):
            parts.append("It is dark here.")
        return " ".join(parts)
    if p.kind == "presence":
        return _cap(_presence_clause(p)) + "."
    if p.kind == "appearance":
        desc = _appearance_as_prose(p.data.get("description"))
        return f"You see {desc}." if desc else ""
    if p.kind == "pose":
        return _render_pose(p)
    if p.kind == "body_part":
        return _render_body_part(p)
    if p.kind == "body_state":
        parts = []
        if p.data.get("posture"):
            parts.append(f"You are {p.data['posture']}.")
        if p.data.get("activity"):
            parts.append(f"You are {p.data['activity']}.")
        if p.data.get("held_items"):
            parts.append("You hold: " + ", ".join(p.data["held_items"]) + ".")
        return " ".join(parts)
    if p.kind == "sensation":
        clause = str(p.data.get("clause") or "").strip()
        return _cap(clause) + "." if clause else ""
    if p.kind == "body_region":
        place = str(p.data.get("place") or "").strip()
        detail = str(p.data.get("detail") or "").strip()
        if not place or not detail:
            return ""
        if detail[-1:] not in ".!?":
            detail += "."
        subject = ("Your exposed " + place if p.source_label == "you"
                   else f"{_cap(p.source_label)}'s exposed {place}")
        return f"{subject} is visible: {detail}"
    if p.kind == "ambient":
        desc = str(p.data.get("desc") or "").strip()
        if desc and desc[-1:] not in ".!?":
            desc += "."
        return desc
    return ""


def _render_event(p):
    if p.kind == "speech":
        body = p.data.get("body") or ""
        # `_inject_dialogue` into an empty document is the production grammar
        # (bare-infinitive heard form, conducted, articulation) emitting into
        # nothing -- no duplicate detection against model prose needed.
        if p.fidelity == "fragment":
            return f"A muffled voice: {p.data.get('fragment', '')}"
        return _inject_dialogue(
            "", p.source_label, f'"{body}"', p.data.get("level", "full"),
            p.data.get("volume", "normal"), p.data.get("can_see", False),
            conducted=p.data.get("conducted", False),
            tone=p.data.get("tone", ""),
            articulation=p.data.get("articulation", ""))
    if p.kind == "act":
        return _observable_predicate(
            p.source_label, p.data.get("surface")) or ""
    if p.kind == "crossing":
        if p.data.get("direction") == "arrived":
            return f"{_cap(p.source_label)} comes in."
        return f"{_cap(p.source_label)} leaves."
    if p.kind == "substance":
        clause = str(p.data.get("clause") or "").strip()
        return _cap(clause) + "." if clause else ""
    return ""


def render_view(percepts, *, mode="character", prev_standing=frozenset(),
                prev_described=frozenset(), full_render=False):
    """Decision-free realisation of one observer's percepts.

    ``mode='character'`` renders the full standing state every beat;
    ``mode='player'`` renders only standing state whose content changed
    (dedupe key not in ``prev_standing``) unless ``full_render`` re-renders
    everything (explicit look/examine intent). Events always render, in
    declared order -- chronology is authoritative. The full appearance
    description is FIRST MENTION ONLY in every mode (``prev_described``);
    a look intent re-earns it.

    Returns a RenderedView; ``text`` may be "" ("nothing reached this mind"
    -- the caller stores None, as today).
    """
    percepts = list(percepts or [])
    residue = [p for p in percepts if p.kind == "residue"]
    if residue:
        p = residue[0]
        text = _compose_residue_view(
            p.data.get("level"), targeted=p.data.get("targeted", False),
            loud_event=p.data.get("loud_event", False),
            pain=p.data.get("pain", False))
        return RenderedView(text=text, spans=[(p, text)],
                            standing_keys={p.dedupe_key},
                            described=set(prev_described))

    standing = sorted(
        [p for p in percepts if p.order_key is None],
        key=lambda p: _STANDING_ORDER.get(p.kind, 9))
    events = sorted(
        [p for p in percepts if p.order_key is not None],
        key=lambda p: p.order_key)

    delta = (mode == "player") and not full_render
    described = set(prev_described)
    standing_keys = set()
    seen_dedupe = set()

    standing_spans = []
    presence_group = []
    for p in standing:
        standing_keys.add(p.dedupe_key)
        if p.dedupe_key in seen_dedupe:
            continue
        seen_dedupe.add(p.dedupe_key)
        if p.kind == "appearance":
            source_key = str(p.data.get("source_key") or "")
            if source_key in described and not p.data.get("force") \
                    and not full_render:
                continue
        elif delta and p.dedupe_key in prev_standing:
            continue
        # Presence is ONE observation -- who is here -- however many bodies
        # it covers, so it is held back and rendered as a group. Everything
        # else renders where it stands. `standing` is already sorted by
        # _STANDING_ORDER, so re-inserting the group at the first presence
        # position keeps the discourse order intact.
        if p.kind == "presence":
            presence_group.append(p)
            if len(presence_group) == 1:
                standing_spans.append(_PRESENCE_SLOT)
            continue
        sentence = _render_standing(p)
        if not sentence:
            continue
        if p.kind == "appearance":
            described.add(str(p.data.get("source_key") or ""))
        standing_spans.append((p, sentence))
    if _PRESENCE_SLOT in standing_spans:
        at = standing_spans.index(_PRESENCE_SLOT)
        standing_spans[at:at + 1] = _render_presence_group(presence_group)

    event_spans = []
    for p in events:
        if p.dedupe_key in seen_dedupe:
            continue
        seen_dedupe.add(p.dedupe_key)
        sentence = _render_event(p)
        if sentence:
            event_spans.append((p, _cap(sentence)))

    # Discourse rule: a sudden event chain leads; otherwise standing state
    # anchors the view and the beat follows.
    sudden = any(p.suddenness >= 0.6 for p, _ in event_spans)
    spans = (event_spans + standing_spans) if sudden \
        else (standing_spans + event_spans)
    text = " ".join(sentence for _, sentence in spans).strip()
    return RenderedView(text=text, spans=spans,
                        standing_keys=standing_keys, described=described)


# --------------------------------------------------------------------------
# Layer B -- the episode renderer (memory mode)
# --------------------------------------------------------------------------

_YOU_TO_ME = (
    (re.compile(r"\byou are\b"), "I am"), (re.compile(r"\bYou are\b"), "I am"),
    (re.compile(r"\byou were\b"), "I was"), (re.compile(r"\bYou were\b"), "I was"),
    (re.compile(r"\byou have\b"), "I have"), (re.compile(r"\bYou have\b"), "I have"),
    (re.compile(r"\byourself\b"), "myself"), (re.compile(r"\bYourself\b"), "Myself"),
    (re.compile(r"\byours\b"), "mine"), (re.compile(r"\bYours\b"), "Mine"),
    (re.compile(r"\byour\b"), "my"), (re.compile(r"\bYour\b"), "My"),
    (re.compile(r"\byou\b"), "me"), (re.compile(r"\bYou\b"), "I"),
)


def _first_person(text):
    """Second person -> first person, outside quoted spans (a quoted 'you'
    is what was said and stays verbatim)."""
    segments = _QUOTED_SPAN_RE.split(str(text or ""))
    for i in range(0, len(segments), 2):
        seg = segments[i]
        for pattern, replacement in _YOU_TO_ME:
            seg = pattern.sub(replacement, seg)
        segments[i] = seg
    return "".join(segments)


_GENERIC_LABELS = frozenset({
    "a voice", "the unfamiliar person", "an indistinct figure", "you", "",
})


def _episode_sentence(p):
    if p.kind == "speech":
        if p.fidelity == "fragment":
            return f"I heard a muffled voice: {p.data.get('fragment', '')}"
        body = p.data.get("body") or ""
        if p.data.get("conducted"):
            return (f"{_cap(p.source_label)}'s voice carried through "
                    f'everything around me: "{body}"')
        verb = "say" if p.data.get("can_see") else "say"
        return f'I heard {p.source_label} {verb}: "{body}"'
    if p.kind == "act":
        surface = _first_person(str(p.data.get("surface") or "").strip())
        words = surface.split()
        if words:
            base = _base_from_third_person_s(words[0])
            if base:
                rest = " ".join(words[1:]).rstrip(".")
                return (f"I saw {p.source_label} {base}"
                        + (f" {rest}." if rest else "."))
        sentence = _observable_predicate(p.source_label, surface)
        return sentence or ""
    if p.kind == "crossing":
        if p.data.get("direction") == "arrived":
            return f"{_cap(p.source_label)} came in."
        return f"{_cap(p.source_label)} left."
    if p.kind == "substance":
        clause = _first_person(str(p.data.get("clause") or "").strip())
        return _cap(clause) + "." if clause else ""
    if p.kind == "environment":
        name = p.data.get("room_name")
        return f"I was in {name}." if name else ""
    if p.kind == "pose":
        return _render_pose(p, past=True)
    if p.kind == "sensation":
        clause = _first_person(str(p.data.get("clause") or "").strip())
        return _cap(clause) + "." if clause else ""
    if p.kind == "appearance":
        desc = _appearance_as_prose(p.data.get("description"))
        return f"I saw {desc}." if desc else ""
    if p.kind == "residue":
        return _compose_residue_view(
            p.data.get("level"), targeted=p.data.get("targeted", False),
            loud_event=p.data.get("loud_event", False),
            pain=p.data.get("pain", False))
    return ""


def render_episode(percepts, *, prev_standing=frozenset(),
                   prev_described=frozenset()):
    """Mint one first-person episode from the IR -- the salient delta.

    Consumes the SAME fidelity-degraded surfaces the view renderer consumes
    (a fragment percept carries only its fragment), so the episode can never
    outrun the view -- rule 03 section 5.2, subset-checked in tests.

    Returns ``(content, gist, entities)``. A percept list holding no events
    and no CHANGED standing state is a non-event: content is "" and nothing
    should be minted (the caller writes no row; the turn index still records
    the beat).
    """
    percepts = list(percepts or [])
    residue = [p for p in percepts if p.kind == "residue"]
    if residue:
        sentence = _episode_sentence(residue[0])
        return sentence, sentence, []

    events = sorted(
        [p for p in percepts if p.order_key is not None],
        key=lambda p: p.order_key)
    changed = []
    for p in percepts:
        if p.order_key is not None:
            continue
        if p.kind == "appearance":
            if p.data.get("force") \
                    or str(p.data.get("source_key") or "") not in prev_described:
                changed.append(p)
        elif p.kind in ("environment", "sensation", "pose") \
                and p.dedupe_key not in prev_standing:
            # A pose that CHANGED is a real memory -- somebody knelt, or was
            # pinned. An unchanged one is furniture and the dedupe key keeps
            # it out, which is the same rule the room already lives under.
            changed.append(p)

    if not events and not changed:
        return "", "", []

    # Event-bearing content LEADS; changed standing state trails, with any
    # room change last of all. This ordering is LOAD-BEARING for retrieval:
    # embedding models systematically over-weight a text's first sentence
    # (~15% beginning-to-end similarity falloff, consistent across
    # positional-encoding families -- Lee, Goel & Ramchandran, "Quantifying
    # Positional Biases in Text Embedding Models", arXiv:2412.15241), so an
    # episode that opens with scene-setting embeds as its room, not its
    # event. When the only change IS the room, the movement is the event
    # and may lead.
    if events:
        ordering = (events
                    + [c for c in changed if c.kind != "environment"]
                    + [c for c in changed if c.kind == "environment"])
    else:
        ordering = changed

    sentences = []
    entities = []
    best = None
    for p in ordering:
        sentence = _episode_sentence(p)
        if not sentence:
            continue
        sentences.append((p, sentence))
        label = str(p.source_label or "")
        if label.casefold() not in _GENERIC_LABELS and label not in entities:
            entities.append(label)
        if best is None or p.salience > best[0].salience:
            best = (p, sentence)

    seen = set()
    ordered = []
    for p, sentence in sentences:
        if sentence in seen:
            continue
        seen.add(sentence)
        ordered.append(sentence)
    content = " ".join(ordered).strip()
    gist = best[1] if best else (ordered[0] if ordered else "")
    return content, gist[:240], entities[:16]


# --------------------------------------------------------------------------
# Observations -- projected from the IR, never regex-classified from prose
# --------------------------------------------------------------------------

_FIDELITY_AMBIGUITY = {"full": 0.15, "degraded": 0.5, "fragment": 0.7,
                       "trace": 0.8}

_MAX_OBSERVATION_ATOMS = 8


def observations_from_render(pid, rendered):
    """Project one rendered view into structured observations.

    channel/suddenness/intensity/directed_at_self are KNOWN from the IR, not
    cue-guessed. The invariant that survives from the prose-derivation era:
    each observation's ``observed.text`` is a rendered sentence span, so the
    second representation still cannot exceed the first -- both derive from
    the same gated IR, and the text is byte-for-byte part of the view.
    """
    pid = str(pid)
    atoms = []
    for p, sentence in rendered.spans:
        ambiguity = _FIDELITY_AMBIGUITY.get(p.fidelity, 0.15)
        atoms.append({
            "percept": p,
            "channel": p.channel if p.channel in CHANNELS else "mixed",
            "text": sentence,
            "intensity": min(1.0, 0.35 + 0.4 * p.salience),
            "suddenness": p.suddenness,
            "ambiguity": ambiguity,
            "directed_at_self": bool(
                p.data.get("directed_at_self")
                or p.channel == "interoception"),
        })
    # Merge consecutive atoms ONLY when their whole delivery verdict matches:
    # channel AND fidelity class AND self-direction. Aggregation keyed on
    # anything less can launder an information boundary -- a degraded atom
    # folded into a full one would read as clearly perceived. When the cap
    # later forces a merge across verdicts, the group degrades to the WEAKEST
    # verdict present (max ambiguity, channel -> mixed), never the strongest.
    merged = []
    for atom in atoms:
        same_verdict = (
            merged
            and merged[-1]["channel"] == atom["channel"]
            and (merged[-1]["ambiguity"] >= 0.5) == (atom["ambiguity"] >= 0.5)
            and merged[-1]["directed_at_self"] == atom["directed_at_self"]
            and len(merged[-1]["parts"]) < 3)
        if same_verdict:
            last = merged[-1]
            last["parts"].append(atom["text"])
            last["intensity"] = max(last["intensity"], atom["intensity"])
            last["suddenness"] = max(last["suddenness"], atom["suddenness"])
            last["ambiguity"] = max(last["ambiguity"], atom["ambiguity"])
        else:
            merged.append({**atom, "parts": [atom["text"]]})
    while len(merged) > _MAX_OBSERVATION_ATOMS:
        idx = min(range(len(merged)),
                  key=lambda i: len(" ".join(merged[i]["parts"])))
        into = idx - 1 if idx else 1
        target, source = sorted((into, idx))
        if merged[target]["channel"] != merged[source]["channel"]:
            merged[target]["channel"] = "mixed"
        merged[target]["parts"].extend(merged[source]["parts"])
        merged[target]["ambiguity"] = max(
            merged[target]["ambiguity"], merged[source]["ambiguity"])
        merged[target]["directed_at_self"] = (
            merged[target]["directed_at_self"]
            or merged[source]["directed_at_self"])
        merged.pop(source)
    out = []
    for index, atom in enumerate(merged):
        out.append({
            "observation_id": f"current:{pid}:{index}",
            "perceiver_id": pid,
            "source_atom_id": "current",
            "channel": atom["channel"],
            "fidelity": "ambiguous" if atom["ambiguity"] >= 0.5 else "rendered",
            "observed": {"text": " ".join(atom["parts"])},
            "intensity": atom["intensity"],
            "suddenness": atom["suddenness"],
            "ambiguity": atom["ambiguity"],
            "directed_at_self": atom["directed_at_self"],
        })
    return out
