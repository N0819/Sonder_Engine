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

- ``character`` -- full standing state every beat, including complete visible
  body and attire strings for every OTHER person. A character agent is a
  stateless LLM call; if it is not in context, the mind does not have it. The
  observer's own body/attire remains supplied by its updated card state.
- ``player`` -- LEADS WITH WHAT CHANGED. Standing state is the BACKGROUND of
  a percept, not its content: the view is this beat's events and the standing
  percepts that CHANGED for this observer first, then what is merely still
  true (first mentions, re-encounters, live sensations). Change is decided by
  `standing_verdicts` against this observer's own previous ledger -- never
  against the objective scene, which is the shape that leaks -- and the
  changed half is marked `beat`, so those percepts reach the narrator as
  numbered deliveries instead of wallpaper. An explicit look/examine intent
  (``full_render=True``) re-renders the whole standing state on purpose.
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

import dataclasses
import hashlib
import logging
import re
from dataclasses import dataclass, field

from core.pipeline_context import note_step_decision

from language_runtime import (
    LanguagePackError, current_language_id, language_pack, linguistic,
    renderer_for)

logger = logging.getLogger(__name__)
from story.scene import disguise_breaks_recognition
from story.provenance_text import strip_engine_provenance
from world.spatial import (
    _clean_pose,
    _entities_named,
    _entity_named,
    _is_body_entity,
    body_visibility,
    entity_arc,
    entity_side,
    hear_level,
    _sense_channel,
    sense_adjusted,
    proximity_rel,
    same_subject,
    size_relation,
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
    _fix_you_agreement,
    _self_second_person,
    _unknown_actor_label,
)


# --------------------------------------------------------------------------
# The IR
# --------------------------------------------------------------------------

# The complete vocabulary of admitted percepts, ENFORCED (see Percept below).
# It was read by nothing for long enough to go two kinds stale -- `pose` and
# `body_part` were minted by live builders and declared here by nobody, while
# `_STANDING_ORDER`, which IS read on every render, carried both. Two
# hand-maintained lists of one thing, and only the unread one was wrong.
PERCEPT_KINDS = (
    "environment", "presence", "pose", "appearance", "act", "speech",
    "communication",
    "sensation", "substance", "body_part", "body_region", "body_state",
    "crossing", "residue", "ambient", "scent",
)

CHANNELS = ("sight", "hearing", "touch", "interoception", "smell", "mixed")

# English is the reference adapter while Layer B is extracted card by card.
# Loading these transforms through the installed pack is intentional: the
# default language exercises the same pack discovery/validation path every
# future language uses, instead of leaving English as an untested special case.
_ENGLISH_COMPOSITOR = language_pack("en").card("compositor")


def _compositor(name):
    """One compositor value from the ACTIVE story pack, read at use time."""
    from language_runtime import compositor_value
    return compositor_value(name)
_EN_TEMPLATES = _ENGLISH_COMPOSITOR["templates"]


def _ling(name):
    return linguistic("agents.composer", name)

def _en(key, **values):
    return str(_EN_TEMPLATES[key]).format(**values)


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

    def __post_init__(self):
        """Refuse a kind or channel nobody declared.

        The declarations are only a vocabulary if something asks. Both are
        closed sets minted exclusively by the builders in this module, so an
        undeclared value is a programming error, not a story the engine has
        to survive -- and a kind no renderer branch matches renders as the
        empty string, which is the failure this raise replaces: silent,
        invisible in tests, and indistinguishable from a percept that was
        correctly withheld.
        """
        if self.kind not in PERCEPT_KINDS:
            raise ValueError(f"undeclared percept kind: {self.kind!r}")
        if self.channel not in CHANNELS:
            raise ValueError(f"undeclared percept channel: {self.channel!r}")


def _sense_graded(level, channel, senses):
    """Shift one admission grade by the observer's card senses.

    `spatial.sense_adjusted` is THE senses gate (G4), and for a long time the
    only deterministic delivery path that asked it was the interaction
    micro-loop. Every builder in this module graded on the world alone, so an
    authored-blind card saw the room in its onset view, its outcome view and
    its memory of the beat, and was correctly blind for the length of one
    micro-round in between.

    `None` and an ordinary card return the level unchanged, byte-identical to
    before; the one direction that adds is capped inside `sense_adjusted`
    itself. Kept as a named wrapper rather than a bare call so the gate has
    one spelling here and every builder that grades can be seen to use it.
    """
    return sense_adjusted(level, channel, senses) if senses else level


def _short_hash(*parts):
    joined = "\x1f".join(str(p or "") for p in parts)
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:10]


def body_key(name):
    """Opaque, stable per-body ledger key. Canonical names never ride a
    Percept -- not even as bookkeeping -- so the IR invariant ("no field
    carries a fact the observer has no channel to") is checkable by simple
    string containment over the whole record."""
    return _short_hash("body", str(name or "").strip().casefold())


def standing_key(tag, subject_parts, content_parts):
    """One standing percept's dedupe key, as ``<tag>:<subject>:<content>``.

    THE KEY HAS TO ANSWER TWO QUESTIONS, and one hash could only answer the
    first. A renderer holding this beat's percepts and the observer's own
    previous ledger must be able to tell "the same fact, said again" from
    "this fact about the same thing, different now" from "I have never been
    told about this thing at all" -- unchanged, changed, first sight. A
    single hash over subject AND content collapses the last two: a pose that
    moved and a body that just walked in produce the same verdict, "a key I
    have not seen", so nothing could lead with what CHANGED.

    Both halves are hashes, so the invariant `body_key` exists for holds
    unaltered: no canonical name rides a Percept, not even as bookkeeping,
    and the whole record stays checkable by string containment.
    """
    return (f"{tag}:{_short_hash(*subject_parts)}"
            f":{_short_hash(*content_parts)}")


def _subject_prefix(dedupe_key):
    """``<tag>:<subject>`` of a split standing key, or None for any other
    shape. Old ledgers hold single-hash keys and every one of them answers
    None here, which is what makes an upgraded chat read as first sight
    rather than as a changed anything -- fail toward re-describing, never
    toward claiming something moved."""
    parts = str(dedupe_key or "").split(":")
    if len(parts) != 3 or not all(parts):
        return None
    return f"{parts[0]}:{parts[1]}"


# --------------------------------------------------------------------------
# Referring expressions
# --------------------------------------------------------------------------

_LABEL_DANGLING = frozenset(_ENGLISH_COMPOSITOR["label_dangling"])


def _descriptor_words(name, appearance, aliases=None, role="", *,
                      surface=None):
    """The full name-stripped content word list of an appearance summary --
    the raw material a stranger label is cut from.

    `role` is exempt from the strip for the reason `_unknown_actor_label`
    gives at length: a rank or duty carried inside a minted display name is
    a public noun, not an identity token, and subtracting it deletes the
    description of a body the observer can plainly see.

    A structured `surface` supplies its own words in widening order
    (`charter_surface.surface_words`); nothing in them is a name."""
    if surface:
        from world.charter_surface import surface_words
        words = surface_words(surface, "full")
        if words:
            return words
    text = _appearance_as_prose(appearance)
    if not text:
        return []
    name_tokens = _identity_token_set(name, aliases)
    if role:
        name_tokens = name_tokens - _identity_token_set(role)
    cleaned = re.sub(r"^(a|an|the)\s+", "", text.strip(), flags=re.I)
    cleaned = cleaned.replace(",", " ").replace(";", " ")
    words = [w for w in cleaned.split()
             if re.sub(r"[^\w]", "", w).casefold() not in name_tokens]
    while words and words[0].lower() in ("a", "an", "the"):
        words = words[1:]
    return words


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
    text = str(text or "").strip().rstrip(".;:,")
    if not text:
        return ""
    articles = frozenset(str(a).casefold() for a in _compositor("articles"))
    ordinals = frozenset(str(w).casefold() for w in _ORDINAL_WORDS.values())
    parts = text.split()
    while parts and parts[0].casefold() in articles:
        parts = parts[1:]
    if len(parts) > 1 and parts[0].casefold() in ordinals:
        parts = parts[1:]
    return " ".join(parts).casefold()


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


#: Ordinal words for the last-resort distinguisher below. Stops at twelve
#: because past that the honest reading is "a crowd", and a numeral in the
#: middle of a sentence is still prose rather than an engine device.
_ORDINAL_WORDS = {
    int(number): str(word)
    for number, word in _ENGLISH_COMPOSITOR["ordinal_words"].items()
}


def _ordinal_word(n):
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
    if label.lower().startswith("the "):
        return f"the {word} {label[4:]}"
    if label.lower().startswith(("a ", "an ")):
        return f"the {word} {label.split(' ', 1)[1]}"
    return f"the {word} {label}"


def assign_stranger_labels(bodies):
    """name -> distinguishing label, chosen jointly against the others present.

    `bodies` is ``[(name, appearance, aliases)]`` -- or
    ``[(name, appearance, aliases, role)]`` -- for every co-present body the
    observer does NOT recognize. Starts from `_unknown_actor_label`'s
    short form; when two strangers collide on it, the colliding parties'
    labels are widened word by word from their own appearance summaries until
    they differ ("the fox woman with six tails" instead of "a second fox
    woman"). Only when the appearances genuinely cannot distinguish them does
    the ordinal distinguisher survive as the last resort (`_ordinal_label`).

    The optional fourth element is the body's public role noun, exempt from
    the identity strip (`_unknown_actor_label`). Two bodies of one rank still
    collide on it and are told apart by the ordinal, which is honest: an
    observer who can see two ensigns and tell them apart no other way has
    exactly that.
    """
    rows = [tuple(body) + (None,) * (5 - len(tuple(body))) for body in bodies]
    rows = [(name, appearance, aliases, role or "", surface)
            for name, appearance, aliases, role, surface in rows]
    labels = {}
    for name, appearance, aliases, role, surface in rows:
        labels[str(name)] = _unknown_actor_label(
            name, appearance, aliases, role=role, surface=surface)
    words = {str(name): _descriptor_words(name, appearance, aliases, role,
                                          surface=surface)
             for name, appearance, aliases, role, surface in rows}
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
                labels[name] = _ordinal_label(label, seen[label])
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
            visual_level_between(scene, observer_name, name), "sight", senses)
        if level == "full":
            strangers.append(
                (name, body.get("appearance"), body.get("aliases") or [],
                 str(body.get("role") or ""), body.get("surface")))
        elif level == "none":
            out[name] = _unfamiliar_person()
        else:
            silhouettes.append((name, body.get("surface"), level))
    out.update(assign_stranger_labels(strangers))
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


# --------------------------------------------------------------------------
# Layer A -- shared admission helpers
# --------------------------------------------------------------------------

def concealed_from_observer(entry, observer_name, observer_id=None):
    """Is this concealed event element withheld from this observer?

    An empty conceal_from means hidden from every non-actor; a populated list
    is an explicit excluded audience. This is now the only reading of that
    rule: the second copy lived on the retired onset/outcome prose paths and
    went with them."""
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


def line_hear_level(entry, rel, observer_name, proximity=None,
                    senses=None):
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
    # A live channel between speaker and observer -- a PA, an intercom, a
    # radio, a phone -- decides FIRST, before the wall gets a say.
    #
    # It was ordered after the spatial read and that was wrong in a way only
    # play could show: an interview room whose two-way mirror the Director
    # encoded as `membrane` muffles an ordinary voice to a `fragment`, and a
    # fragment is not "none", so the early return took it and the live PA
    # standing between those two rooms was never consulted. The scene had the
    # equipment, the equipment was switched on, and the reader got a muffled
    # voice through the glass.
    #
    # The rule the ordering encodes: a speaker reproduces the voice, so what
    # the wall would have done to it does not matter. Muffling is a property
    # of the path the channel replaces. A channel only ever RAISES what
    # arrives, and where none applies this falls through to the ordinary
    # spatial read unchanged.
    #
    # Read off the RELATION, never out of the scene: this module decides
    # admission on typed data alone, and a rendering path that could consult
    # the world could add to it. It rescues regardless of who the line NAMES,
    # which is the whole difference between a channel and the addressed rescue
    # below -- a voice on a speaker is heard by whoever is in front of the
    # speaker. `spatial.comms_link` has already decided direction, liveness,
    # and who is on the channel.
    if isinstance(rel.get("comm_channel"), dict):
        return "full"
    base = _sense_graded(
        hear_level(rel, entry.get("volume", "normal"), proximity=proximity),
        "hearing", senses)
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
    """True when a dialogue line's intended_target names this observer. The
    target may be a single name or a list; comparison is casefolded. Used to
    route a comm-channel transmission to the party it was addressed to, across
    a physical barrier (see the medium:'comm' handling in perception_outcome).

    One definition. `perception.py` carried a byte-identical twin that no
    production path called and one test imported, so the tested copy and the
    running copy were different objects free to drift apart.
    """
    if not intended_target or not observer_name:
        return False
    targets = intended_target if isinstance(intended_target, (list, tuple)) \
        else [intended_target]
    on = str(observer_name).casefold()
    return any(str(t).casefold() == on for t in targets)




def _surface_suddenness(surface):
    """How abruptly an act arrives, from its leading verb.

    Keyed on `split()[0]`, which is the whole clause in a language that does
    not space its words -- so `Percept.suddenness` was pinned at 0.1 for every
    Japanese act, flattening a salience signal the observer receives and
    killing the "a sudden chain leads" discourse rule outright.
    """
    text = str(surface or "").casefold().strip()
    if not text:
        return 0.1
    cues = _ling("_SUDDEN_VERBS")
    words = text.split()
    first = re.sub(r"[^\w]", "", words[0]).rstrip("s")
    if first in cues:
        return 0.6
    # No leading token to test: fall back to whether the clause OPENS with a
    # cue, which is the same question asked without assuming a space.
    if len(words) == 1 and any(text.startswith(str(cue)) for cue in cues):
        return 0.6
    return 0.1


# --------------------------------------------------------------------------
# Layer A -- standing-state percepts
# --------------------------------------------------------------------------

def environment_percept(room_id, room_name, room_notes="", light="",
                        features=None, openings=None):
    """The room as standing state -- or None when the observer has no
    resolvable room. A mind in unloaded space perceives NOTHING here; the
    old path fabricated "You are in an unspecified area." for it, which
    became 812 identical memory rows (97.3% collision). No room, no
    percept, no view sentence, no episode.

    `features` is what THIS observer's eyes reach of the room's furniture
    (`world.spatial_fov.feature_visibility`, already subtracted by cone and
    line): rows of {desc, tier, side, peripheral}, near to far. Absent or
    empty, the percept is byte-identical to the one it always was -- a room
    with no geometry authored on its anchors composes exactly as before.

    `openings` is the room's BOUNDARY, on the same terms: rows of
    {desc, room_name, room_notes, dark, features} for every way out this
    observer can see, each carrying what sight reaches past it and nothing
    more (`_render_openings`, and `perception._visible_openings` for the
    admission). A boundary belongs to the room's standing state exactly as
    its furniture does, which is why it rides this percept rather than
    becoming a kind of its own -- and why it joins the dedupe signature
    below, so a door that opens is a room that CHANGED for this observer and
    a door that stays shut is furniture.
    """
    if not room_id or not str(room_name or "").strip() \
            or str(room_name).strip().casefold() == "an unspecified area":
        return None
    rows = []
    for row in features or ():
        if not isinstance(row, dict) or not str(row.get("desc") or "").strip():
            continue
        rows.append({
            "desc": str(row.get("desc")).strip(),
            "tier": str(row.get("tier") or ""),
            "side": row.get("side") if row.get("side") in ("left", "right")
            else None,
            "peripheral": bool(row.get("peripheral")),
        })
    # THE DELIVERY FLOOR for engine provenance. Room notes are the one field in
    # a view whose text the ENGINE may have written about itself -- a
    # synthesised description can carry the reason it was synthesised, and that
    # reason is bookkeeping, not a property of the room. Measured live (chat 95
    # beat 7): "You are in Harbour Office. generated because no candidate
    # described this location." reached a character agent as world text. The
    # signal is kept where provenance belongs (story/provenance_text); what a
    # mind receives is the place. Stripped HERE, at percept construction, so
    # the render and `observations_from_render` cannot disagree about it.
    room_notes = strip_engine_provenance(room_notes)
    light = str(light or "")
    # Provenance stripped on the far side of a threshold for the same reason
    # it is stripped for the room underfoot, and in the same place: a
    # synthesised description can carry the reason it was synthesised, and
    # that reason is bookkeeping rather than a property of the room.
    ways = []
    for way in openings or ():
        if not isinstance(way, dict) or not str(way.get("desc") or "").strip():
            continue
        way = dict(way)
        way["room_notes"] = strip_engine_provenance(way.get("room_notes"))
        ways.append(way)
    data = {"room_id": room_id, "room_name": room_name,
            "room_notes": room_notes or "", "light": light}
    if rows:
        data["features"] = rows
    if ways:
        data["openings"] = ways
    # The visible set is part of the CONTENT: turning to face the hearth
    # changes what this observer has of the room, and the ledger must read
    # that as the room changed for them, not as the same fact said again.
    feature_sig = "|".join(
        f"{r['desc']}:{r['tier']}:{r['side'] or ''}:{int(r['peripheral'])}"
        for r in rows)
    opening_sig = "|".join(
        "%s>%s:%d:%s" % (w["desc"], w.get("room_name") or "",
                         int(bool(w.get("dark"))),
                         ",".join(str((f or {}).get("desc") or "")
                                  for f in (w.get("features") or ())))
        for w in ways)
    return Percept(
        kind="environment", channel="sight",
        data=data,
        salience=0.2,
        dedupe_key=standing_key(
            "env", (room_id,),
            (room_name, room_notes, light)
            + ((feature_sig,) if rows else ())
            + ((opening_sig,) if ways else ())),
    )


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
# named somebody. The English compat exports stay for tests and audits.
DIM_FIGURE = str(_ENGLISH_COMPOSITOR["dim_figure"])
DIM_FIGURES = str(_ENGLISH_COMPOSITOR["dim_figures"])


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
    from world.spatial import room_of

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
    arc already do."""
    out = []
    for body in co_present or []:
        name = str(body.get("name") or "")
        if not name or name == observer_name:
            continue
        level = _sense_graded(
            visual_level_between(scene, observer_name, name), "sight", senses)
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
            # and already applies the cross-room caps (the opening's view cone,
            # an authored far edge), so the only thing missing was somewhere to
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
        out.append(Percept(
            kind="presence", channel="sight",
            source_label=label,
            fidelity="full" if level == "full" else "degraded",
            data={"tier": tier, "side": side, "arc": arc, "sight": level,
                  "body": body_key(name),
                  **({"size": size} if size else {}),
                  **({"room": room} if room else {}),
                  **({"behind": behind, "shows": shows} if behind else {})},
            salience=0.35,
            dedupe_key=standing_key(
                "presence", (body_key(name),),
                (tier, arc, level, size or "")
                + ((behind, shows) if behind else ())),
        ))
    return out


_COUNT_NAMES = {
    int(number): str(word)
    for number, word in _ENGLISH_COMPOSITOR["count_names"].items()
}


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
            dedupe_key=standing_key(
                "part", (body_key(label), kind, part.get("at")),
                (count, part.get("aspect"), part.get("description"),
                 part.get("tucked"))),
        ))
    return out


def _names_a_body(scene, text, co_present):
    """Does this referent name a BODY, asked structurally rather than by word.

    `entities[*].kind` is free text a model writes: across the stories on disk
    it holds 'person', 'character', 'agent', 'npc', 'actor', 'kitsune',
    'succubus' and 'dalek war machine' beside 'object' and 'fixture', so any
    allowlist of person-kinds is really a list of the stories played so far
    and is wrong for the next one. The signals used instead hold whatever the
    story calls its people: a body is something the observer is co-present
    with, something the scene gives a POSE, or something the enclosure code
    already recognises as a body.
    """
    for body in co_present or []:
        if same_subject(scene, text, str(body.get("name") or "")):
            return True
    for posed in (scene.get("poses") or {}):
        if same_subject(scene, text, str(posed or "")):
            return True
    primary, aliased = _entities_named(scene, text)
    return any(_is_body_entity(scene, eid, entity)
               for eid, entity in (*primary, *aliased))


def _part_qualified(scene, text):
    """Split a part-qualified referent `<owner>.<part>` into its two halves.

    A support or relation referent may name a PART OF a body or entity rather
    than the whole of it -- `Mirelle Sulmirath.tongue`, `kestrel.hand`. The
    dotted token is the engine's compound register for that, and it must never
    reach the page: composed today, a pose read "lying on Mirelle
    Sulmirath.tongue on you" with the dot token verbatim, while its id-spelled
    twin `mirelle_sulmirath.hands` hit the id-shaped drop and was lost whole,
    taking owner and part with it.

    The OWNER half decides whether the referent may be named at all, so this
    only reports a split when the owner is a spelling the scene knows. A
    spelling the scene knows AS A WHOLE is never split, which is what keeps a
    body or entity whose own name carries a period intact. A dot in free text
    -- "St. Ives", a sentence end -- resolves to nothing and is left exactly
    as written.

    Returns `(owner, part)`, or `(None, "")` for anything that is not one.
    """
    text = str(text or "").strip()
    if "." not in text:
        return None, ""

    def _known(name):
        name = str(name or "").strip()
        if not name:
            return False
        if _entity_named(scene, name):
            return True
        return any(
            same_subject(scene, name, str(key or ""))
            for table in ("positions", "poses", "attire")
            for key in ((scene or {}).get(table) or {}))

    if _known(text):
        return None, ""
    owner, _dot, part = text.partition(".")
    owner, part = owner.strip(), part.strip().replace("_", " ")
    if not owner or not part or not _known(owner):
        return None, ""
    return owner, part


def _pose_referent(scene, observer_name, display_map, co_present, other,
                   *, is_self=False):
    """What a pose is arranged against, rendered as the KIND OF THING it is.

    Returns the text to render, or None to drop this referent -- and, where
    the caller is handling `relative_to`, its relation along with it.

    A POSE REFERENT IS NOT NECESSARILY A BODY. A body may be arranged against
    the observer, against another body, against a scene entity (furniture, a
    device, a fixture), or against a bare noun the Director wrote that names
    no record at all, and only the first two can be a PERSON. Every referent
    used to be resolved through `display_map` -- which holds co-present BODIES
    and nothing else -- with each miss taking the person-shaped default
    "someone". A desk, a bolted chair and a reality anchor were therefore each
    delivered as an unidentified person: "seated upright on desk at someone",
    "restrained in someone", "standing beside someone". Measured in chat 84,
    where all four poses in the scene did it in the same beat, and the last of
    them put a third body into a room the observer could see held exactly two
    guards.

    Order of certainty, and every miss SUBTRACTS:

      1. the observer -> "you"
      2. a body this observer has ALREADY BEEN GIVEN -> that body's own
         display label. This is the only place a person label may come from.
      3. any other body -> DROPPED, unless this is the observer's OWN pose.
         `observer_display_map` covers every co-present body, so a body
         absent from it is one this observer was not shown, and naming it in
         somebody else's pose would hand them a presence perception withheld.
         Their own pose is the exception and not a leak: a body you are
         arranged against is a body you are in CONTACT with, and contact is
         delivered by interoception whether or not you can see who it is.
         "pinned beneath someone" is the honest rendering of exactly that,
         and the identity stays unearned.
      4. a scene entity -> its own name, through the pack's own template so a
         language that takes no article does not get one.
      5. an id-shaped token matching no record -> DROPPED. `anchor_device`
         (the entity's id is `scranton_anchor`) names nothing, and putting it
         on the page shows the reader engine plumbing.
      6. anything else -> the bare noun as written. It matches no record in
         the scene, so it can disclose nothing the Director's own phrasing
         did not already carry.
    """
    text = str(other or "").strip()
    if not text:
        return None
    # A part is a referent like any other; only its OWNER decides whether it
    # may be named, so the part resolves through the owner by this same order
    # of certainty and can never outrank it.
    owner, part = _part_qualified(scene, text)
    if owner is not None:
        whose = _pose_referent(scene, observer_name, display_map, co_present,
                               owner, is_self=is_self)
        if not whose:
            # The firewall answer at step 3 is INHERITED, not re-decided: a
            # part of a body this observer was not shown drops exactly as the
            # body does.
            return None
        if whose == "you":
            return _en("pose_part_self", part=part)
        return _en("pose_part_other", label=whose, part=part)
    if same_subject(scene, text, observer_name):
        return "you"
    for name, label in (display_map or {}).items():
        if same_subject(scene, text, str(name or "")):
            return label
    if _names_a_body(scene, text, co_present):
        return "someone" if is_self else None
    entity = _entity_named(scene, text)
    named = str((entity or {}).get("name") or "").strip()
    if named:
        return _en("pose_entity", name=named)
    if "_" in text and not text.strip().count(" "):
        return None
    # A bare noun the Director wrote. It still reads better with the article
    # the pack supplies -- "at desk" is the awkwardness this whole repair was
    # reported for -- but only where it does not already carry a determiner
    # of its own ("the far wall", "her shoulder") and is not a proper name,
    # which a capital marks and which "the Marcus" would ruin. The determiner
    # list is language DATA and lives in the compositor card, empty for a
    # language that takes no article at all.
    first = text.split()[0].casefold().strip(",.")
    # A support is authored free-text and often arrives with its own
    # preposition already on it ("on the sill"); `_render_pose` detects that
    # and declines to add a second one. Prefixing an article here would slip
    # underneath that check and produce "on the on the sill".
    if (text.split()[0][:1].isupper()
            or first in _POSE_BARE_DETERMINERS
            or first in _POSE_PREPOSITIONS):
        return text
    return _en("pose_entity", name=text)


def _same_referent(scene, a, b):
    """Do two pose fields name one thing -- by spelling, or by resolving to
    the same scene entity."""
    a, b = str(a or "").strip(), str(b or "").strip()
    if not a or not b:
        return False
    # Two pose fields naming one body at two granularities -- the body in
    # `relative_to`, a place ON it in `support` -- are still ONE referent.
    # Comparing whole strings let both render, which is where the second
    # preposition came from ("on <body>.<part> on you"). Granularity is not
    # identity.
    a = _part_qualified(scene, a)[0] or a
    b = _part_qualified(scene, b)[0] or b
    if a.casefold() == b.casefold():
        return True
    ea, eb = _entity_named(scene, a), _entity_named(scene, b)
    na = str((ea or {}).get("name") or "").strip().casefold()
    nb = str((eb or {}).get("name") or "").strip().casefold()
    return bool(na) and na == nb


#: Words that may follow an OBJECT pronoun and never a possessive one. A
#: possessive is followed by the thing possessed -- a noun, or an adjective
#: on its way to one -- so a preposition or a conjunction after "her" settles
#: that "her" is the object. This is a closed class the engine owns rather
#: than an attempt to anticipate English (CLAUDE.md's carve-out), and the
#: genuinely ambiguous members are left OUT on purpose: "her back", "her
#: past" and "her present" are possessives as readily as adverbs, so none of
#: those three is here.
_OBJECT_PRONOUN_FOLLOWERS = frozenset((
    "at", "to", "into", "onto", "in", "on", "out", "from", "by", "with",
    "without", "for", "toward", "towards", "through", "across", "over",
    "under", "against", "behind", "before", "after", "beside", "between",
    "among", "up", "down", "off", "away", "along", "upon", "within",
    "beneath", "below", "above", "inside", "outside",
    "and", "or", "but", "so", "then", "while", "as", "when", "if",
    "because", "though", "although", "until", "since",
))


def _reads_as_possessive(tail) -> bool:
    """Is the pronoun just matched a possessive, judged by what follows it?

    The two readings are spelled the same for a great many bodies -- `her` is
    both -- so the fallback asked only whether ANY word followed, and a
    prepositional phrase after an object pronoun is a word. Measured live
    (chat 99): a stored pose detail reading `holding her at the back of the
    mouth` reached its owner's own view as `holding your at the back of the
    mouth`, which is not English and which named the wrong body besides.

    A possessive is followed by what is possessed. A preposition or a
    conjunction is neither, so it settles the reading the other way.
    """
    match = re.match(r"\s+([A-Za-z][\w'\u2019-]*)", str(tail or ""))
    if not match:
        return False        # end of fragment, or punctuation: object
    return match.group(1).casefold() not in _OBJECT_PRONOUN_FOLLOWERS


def _pose_owner_second_person(text, pronouns, other_forms=()):
    """Rewrite pronouns whose referent is known from a pose's ownership.

    A pose is stored under the body it describes.  Its ``posture``,
    ``constraint`` and ``detail`` therefore have an explicit grammatical
    owner even when a model writes them as third-person fragments.  That is a
    materially narrower case than arbitrary prose anaphora: within each
    comma/semicolon-delimited fragment, the owner's declared pronouns refer
    to the owner until another body is explicitly named.  After that name we
    leave matching pronouns alone rather than guessing which body they mean.

    This is what turns ``settled on her heels ... Mara`` into ``settled on
    your heels ... Mara`` without turning the later ``steady her`` (after
    Mara has been named) into ``steady you``. Quoted spans are untouched.
    """
    text = str(text or "")
    if not text or not isinstance(pronouns, dict):
        return text
    subject = str(pronouns.get("subject") or "").strip()
    obj = str(pronouns.get("object") or "").strip()
    possessive = str(pronouns.get("possessive") or "").strip()
    if not any((subject, obj, possessive)):
        return text

    other_patterns = []
    for form in sorted({str(f or "").strip() for f in other_forms if str(f or "").strip()},
                       key=len, reverse=True):
        other_patterns.append(re.compile(
            r"(?<!\w)" + re.escape(form) + r"(?:['’]s)?(?!\w)", re.I))

    reflexives = {
        "she": "herself", "he": "himself", "they": "themselves",
        "it": "itself",
    }
    reflexive = reflexives.get(subject.casefold(), "")
    forms = sorted({f.casefold() for f in (subject, obj, possessive, reflexive)
                    if f}, key=len, reverse=True)
    if not forms:
        return text
    pronoun_re = re.compile(
        r"(?<!\w)(" + "|".join(re.escape(f) for f in forms) + r")(?!\w)",
        re.I)

    def rewrite_fragment(fragment):
        cutoff = len(fragment)
        for pattern in other_patterns:
            match = pattern.search(fragment)
            if match:
                cutoff = min(cutoff, match.start())
        prefix, suffix = fragment[:cutoff], fragment[cutoff:]

        def replace(match):
            word = match.group(1)
            low = word.casefold()
            if reflexive and low == reflexive.casefold():
                replacement = "yourself"
            elif ((low == possessive.casefold()
                   and low != obj.casefold()) or
                  (low == possessive.casefold() == obj.casefold()
                   and _reads_as_possessive(prefix[match.end():]))):
                replacement = "your"
            else:
                replacement = "you"
            return replacement.capitalize() if word[:1].isupper() else replacement

        rewritten = pronoun_re.sub(replace, prefix)
        return _fix_you_agreement(rewritten) + suffix

    quoted = linguistic("agents.common", "_QUOTED_SPAN_RE").split(text)
    for index in range(0, len(quoted), 2):
        pieces = re.split(r"([,;—])", quoted[index])
        for piece_index in range(0, len(pieces), 2):
            pieces[piece_index] = rewrite_fragment(pieces[piece_index])
        quoted[index] = "".join(pieces)
    return "".join(quoted)


def _action_target_second_person(text, target_forms, target_pronouns,
                                 other_forms=()):
    """Repair target-owned body pronouns after an explicit target name.

    Character observables are predicates whose omitted subject is the actor.
    When actor and target share pronouns, models commonly write a target once
    and then fall back to an ambiguous possessive: ``from Mara's back down
    between her thighs``.  Merely replacing the exact name produces ``your
    back ... her thighs`` and hands the action to the wrong body.

    This deliberately does *less* than general anaphora resolution.  It runs
    only when the event structurally targets this observer, only after an
    explicit form of that observer in the same sentence, and only when the
    matching possessive owns a body noun, optionally through a small
    language-pack list of anatomical modifiers. Subject pronouns, ``her
    own``, objects, quoted speech, arbitrary possessions, and everything
    after another explicitly named body are untouched.
    """
    text = str(text or "")
    if not text or not isinstance(target_pronouns, dict):
        return text
    possessive = str(target_pronouns.get("possessive") or "").strip()
    forms = sorted({str(form or "").strip() for form in target_forms or ()
                    if str(form or "").strip()}, key=len, reverse=True)
    if not possessive or not forms:
        return text

    target_re = re.compile(
        r"(?<!\w)(?:" + "|".join(re.escape(form) for form in forms)
        + r")(?:['’]s)?(?!\w)", re.I)
    other_patterns = [
        re.compile(r"(?<!\w)" + re.escape(form) + r"(?:['’]s)?(?!\w)", re.I)
        for form in sorted({str(form or "").strip()
                            for form in other_forms or ()
                            if str(form or "").strip()}, key=len, reverse=True)
    ]
    body_nouns = sorted(linguistic(
        "agents.common", "_OWN_BODY_NOUNS"), key=len, reverse=True)
    modifiers = sorted(linguistic(
        "agents.common", "_BODY_OWNERSHIP_MODIFIERS"), key=len, reverse=True)
    modifier_part = ((r"(?:(?:" + "|".join(re.escape(word)
                                            for word in modifiers)
                      + r")\s+){0,2}") if modifiers else "")
    owned_body_re = re.compile(
        r"(?<!\w)" + re.escape(possessive)
        + r"(?=\s+(?!own\b)" + modifier_part + r"(?:"
        + "|".join(re.escape(noun) for noun in body_nouns)
        + r")\b)", re.I)

    quoted = linguistic("agents.common", "_QUOTED_SPAN_RE").split(text)
    for index in range(0, len(quoted), 2):
        sentences = re.split(r"([.!?]+\s*)", quoted[index])
        for sentence_index in range(0, len(sentences), 2):
            sentence = sentences[sentence_index]
            named = target_re.search(sentence)
            if not named:
                continue
            prefix, suffix = sentence[:named.end()], sentence[named.end():]
            cutoff = len(suffix)
            for pattern in other_patterns:
                match = pattern.search(suffix)
                if match:
                    cutoff = min(cutoff, match.start())
            owned, remainder = suffix[:cutoff], suffix[cutoff:]
            suffix = owned_body_re.sub("your", owned) + remainder
            sentences[sentence_index] = prefix + suffix
        quoted[index] = "".join(sentences)
    return "".join(quoted)


def pose_percepts(scene, observer_name, co_present, display_map,
                  senses=None, *, self_forms=(), self_pronouns=None):
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
            # A POSE NEEDS A WITHIN-ROOM TIER. Caught by a pose-bearing
            # drive scenario, not by the corpus: Kai stood in the yard, Reya
            # knelt in the forge behind a closed door, and his view read
            # "Reya is kneeling on the anvil block". Presence had already
            # declined to mention her -- `proximity_rel` answers None across
            # rooms -- while this gate checked only sight and arc, so a body
            # he was not even told was there arrived with her posture, her
            # support and her breathing.
            #
            # It was written as "a pose is never more reachable than a
            # presence", borrowing `presence_percepts`' gate. That is no
            # longer what either function does. Presence has since grown a
            # cross-room branch: where `proximity_rel` is None it does not
            # decline, it falls back to `tier="beyond"` plus the room label,
            # so an interviewer watching through observation glass is told
            # about the woman in the cell. Pose still declines there, and so
            # presence now outruns pose rather than the other way round.
            #
            # The subtraction is defensible on its own terms, which is why it
            # stays: a pose is rendered AGAINST the furniture and the bodies
            # around it ("kneeling on the anvil block", "leaning against
            # her"), and those referents belong to a room the observer is
            # not in. Seeing that someone across a barrier is kneeling is
            # not seeing what they are kneeling on. State it that way rather
            # than as a rule about presence, so the next body percept added
            # here inherits the reason and not a comparison that has flipped.
            if proximity_rel(scene, observer_name, name) is None:
                continue
            level = _sense_graded(
                visual_level_between(scene, observer_name, name),
                "sight", senses)
            if level == "none":
                continue
            if entity_arc(scene, observer_name, name) == "rear":
                continue
            label = display_map.get(name) or "someone"
        # Every exact handle for the receiving observer becomes second person
        # before it enters the IR.  This applies to OTHER bodies' details too:
        # ``Mara ... squeezing Rhea's hand`` in Rhea's own view must
        # read ``... squeezing your hand``.
        data = {"posture": _self_second_person(
            pose["posture"], self_forms) if self_forms else pose["posture"]}
        if level == "full":
            for f in ("support", "relation", "constraint", "detail"):
                data[f] = (_self_second_person(pose[f], self_forms)
                           if self_forms else pose[f])
            if is_self and self_pronouns:
                other_forms = []
                for body in co_present or []:
                    other = str(body.get("name") or "")
                    if not other or same_subject(scene, other, observer_name):
                        continue
                    other_forms.extend([
                        other, *(body.get("aliases") or []),
                        (display_map or {}).get(other),
                    ])
                for f in ("posture", "constraint", "detail"):
                    data[f] = _pose_owner_second_person(
                        data.get(f), self_pronouns, other_forms)
            # Support is a referent too, and took the same raw string onto
            # the page: "on chair_interview" is an entity id being read to
            # the player. Both fields go through the same resolver.
            data["support"] = _pose_referent(
                scene, observer_name, display_map, co_present,
                pose["support"], is_self=is_self) or ""
            other = str(pose["relative_to"] or "").strip()
            if other:
                ref = _pose_referent(
                    scene, observer_name, display_map, co_present, other,
                    is_self=is_self)
                if ref and _same_referent(scene, other, pose["support"]):
                    # ONE THING, NAMED TWICE. The body specialist fills
                    # `support` and `relative_to` with the same referent --
                    # three of chat 84's four poses did -- which read as "on
                    # desk at desk" the moment the referent stopped being a
                    # person. Keep the RELATION, which is the more specific
                    # of the two ("restrained in" against a bare "on"), and
                    # let it carry the referent by itself.
                    if str(data.get("relation") or "").strip():
                        # Relation wins the preposition, the PART wins the
                        # noun. The rule above keeps the relation because it
                        # is the more specific of two identical referents; a
                        # part-qualified support is the more specific NOUN,
                        # because it says where on the body the arrangement
                        # bears, which a bare owner cannot.
                        precise = ref
                        if (_part_qualified(scene, pose["support"])[0]
                                and not _part_qualified(scene, other)[0]):
                            precise = data["support"]
                        data["support"] = ""
                        data["relative_to"] = precise
                    else:
                        data["support"] = ref
                elif ref:
                    data["relative_to"] = ref
        if not any(data.values()):
            continue
        out.append(Percept(
            kind="pose",
            channel="interoception" if is_self else "sight",
            source_label=label,
            fidelity="full" if level == "full" else "degraded",
            data={**data, "directed_at_self": is_self},
            salience=0.3,
            dedupe_key=standing_key(
                "pose", (body_key(name),),
                tuple(str(data.get(f) or "")
                      for f in _POSE_RENDER_FIELDS)),
        ))
    return out


_POSE_RENDER_FIELDS = ("posture", "support", "relative_to", "relation",
                       "constraint", "detail")


def appearance_percept(source_name, label, description, *, force=False,
                       delta="", reearn=False):
    """The FULL authored appearance -- discovery/structural-change data, first
    mention only (the render ledger gates re-emission; ``force=True`` marks a
    structural change this beat, which re-earns the description).

    ``delta`` is what a change LOOKS LIKE from outside, and when it is
    present the renderer uses it INSTEAD of the full description. A garment
    coming off is an event; re-issuing the whole wardrobe is a ledger. The
    old behaviour put "wearing Ceremonial kimono, Nagajuban, Ornate gold
    obi, Zori, Tabi, bare at the head, hands" on the page because a change
    of any one item re-earned every item, and the narrator was then asked to
    render an inventory as something that happened. The full description
    stays available in the standing half of the view, where first-mention
    and dedupe already govern it.
    ``reearn=True`` re-delivers the description past the first-mention
    ledger WITHOUT claiming anything happened. The two are different jobs
    and `force` was doing both: a body you are meeting again is not a body
    that CHANGED, so its description is standing state that has become
    sayable again rather than an event the narrator owes the page. Without
    it, first-mention tracking is permanent -- a stranger described once on
    beat 3 is never described again in a two-hundred-beat story, however
    many times they leave and come back.

    `description` must already be identity-safe for this observer
    (name-stripped when the observer does not recognize the body). The
    canonical name is folded into an opaque `body_key` for the ledger; it
    never rides the percept."""
    return Percept(
        kind="appearance", channel="sight", source_label=label,
        data={"source_key": body_key(source_name),
              "description": description, "force": bool(force),
              **({"reearn": True} if reearn else {}),
              **({"delta": str(delta)} if str(delta or "").strip() else {})},
        salience=0.5,
        dedupe_key=standing_key("described", (body_key(source_name),),
                                (description,)),
    )


def body_state_percept(entity_state):
    state = {k: entity_state.get(k) for k in ("posture", "activity", "held_items")
             if entity_state.get(k)}
    if not state:
        return None
    return Percept(
        kind="body_state", channel="interoception", source_label="you",
        data=state, salience=0.3,
        dedupe_key=standing_key(
            "state", ("self",),
            (state.get("posture"), state.get("activity"),
             ",".join(state.get("held_items") or []))),
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
            dedupe_key=standing_key(
                "contact",
                (contact.get("actor"), contact.get("actor_part"),
                 contact.get("target"), contact.get("target_part")),
                (contact.get("manner"),)),
        ))
    return out


def contact_action_percepts(actions_with_sensation):
    """Standing contact-effect sensations as ``[(record, safe_clause)]``.

    Admission and observer-side phrasing happen upstream, exactly like
    ``contact_percepts``. The composer receives no scene and cannot widen the
    identity or tactile channel.
    """
    out = []
    for entry in actions_with_sensation or []:
        if not isinstance(entry, tuple) or len(entry) != 2:
            continue
        record, clause = entry
        if not isinstance(record, dict):
            continue
        clause = str(clause or "").strip()
        if not clause:
            continue
        out.append(Percept(
            kind="sensation", channel="touch", source_label="you",
            data={"clause": clause, "directed_at_self": True},
            salience=0.4,
            dedupe_key=standing_key(
                "contact_action",
                (record.get("contact_id"), record.get("action"),
                 record.get("actor")),
                (record.get("action_id"), record.get("intensity"),
                 record.get("rhythm"))),
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
            dedupe_key=standing_key(
                "region", (body_key(body_label), place), (detail,)),
        ))
    return out


#: Engine sense channel (world.spatial's vocabulary) -> percept channel.
#: The two names for the olfactory channel are a genuine split rather than a
#: synonym: `world/spatial_senses.py` grades a `scent`, and a percept rides
#: the `smell` a mind receives.
_ENGINE_CHANNEL_PERCEPT = {"sight": "sight", "hearing": "hearing",
                           "scent": "smell"}


def _ambient_channel(event):
    """Which channel an authored sensory event rides.

    THE PROMPT AND THE READER NAMED DIFFERENT FIELDS. `director_establish`
    asks for `sensory_events:[{kind,description,source_room,...}]` in both
    packs; this function read `channel` alone, so all 199 stored events in the
    live corpus fell to `mixed` and the smell channel had no producer at all.
    `channel` still wins where something emits it -- the reader's own spelling
    is not withdrawn -- and `kind` is read because that is what is written.

    A word this engine has no channel for stays `mixed`. A fiction may invent
    a sense (`spiritual_pressure` is a real stored row) and inventing one must
    cost the event nothing.
    """
    for field in ("channel", "kind", "sense"):
        raw = str(event.get(field) or "").strip()
        if not raw:
            continue
        if raw.casefold() in CHANNELS:
            return raw.casefold()
        mapped = _ENGINE_CHANNEL_PERCEPT.get(_sense_channel(raw) or "")
        if mapped:
            return mapped
    return "mixed"


def ambient_percepts(sensory_events, observer_room):
    """Authored opening sensory events, filtered by room scope. An event
    naming a room is admitted only to observers in that room; a roomless
    event is scene ambience."""
    out = []
    for idx, event in enumerate(sensory_events or []):
        if not isinstance(event, dict):
            continue
        room = str(event.get("room") or event.get("room_id")
                   or event.get("source_room") or "")
        if room and observer_room and room != str(observer_room):
            continue
        desc = str(event.get("desc") or event.get("description")
                   or event.get("text") or "").strip()
        if not desc:
            continue
        channel = _ambient_channel(event)
        out.append(Percept(
            kind="ambient", channel=channel, data={"desc": desc},
            salience=0.4,
            dedupe_key=standing_key("ambient", (desc,), (desc,)),
        ))
    return out


#: A scent that arrives without its source. `muffled` is the graded rung
#: `scent_level` has always returned and nothing downstream could act on.
_SCENT_FIDELITY = {"full": "full", "muffled": "degraded"}


def scent_percepts(sources):
    """Standing smells reaching one observer, already graded by the caller.

    Input: ``[{"key", "label", "scent", "level", "attributed"}]`` -- `level`
    is `scent_level`'s own verdict after the observer's card acuity, and
    `attributed` says whether this observer has a SECOND channel to the
    source (they can see the body the smell belongs to).

    THE GRADE IS ACTED ON, NOT RECORDED. A muffled scent is delivered
    unattributed, because what a half-open door withholds is not the smell --
    the material still crosses -- it is which body the smell belongs to. That
    is a real subtraction and a structural one: no string is mangled, a field
    is withheld. It also settles the disguise question in the only direction
    the firewall's own statement points. A scent percept carries a MATERIAL,
    never a NAME: the label is whatever this observer's display map already
    earned for that body, so a disguise that conceals identity yields the
    stranger's descriptor here exactly as it does for presence and pose. A
    mind may then conclude from its own memories that this is the smell of
    someone it knows -- inference is the product, and that inference is
    defeasible, since two bodies can wear one perfume.

    `key` is folded into the dedupe key only; canonical names never ride a
    Percept.
    """
    out = []
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        scent = " ".join(str(source.get("scent") or "").split())[:160]
        level = str(source.get("level") or "none")
        fidelity = _SCENT_FIDELITY.get(level)
        if not scent or fidelity is None:
            continue
        attributed = bool(source.get("attributed")) and level == "full"
        label = str(source.get("label") or "").strip() if attributed else ""
        out.append(Percept(
            kind="scent", channel="smell",
            source_label=label if attributed else "",
            fidelity=fidelity,
            data={"scent": scent, "level": level,
                  "attributed": bool(label)},
            salience=0.35,
            # THE LABEL IS NOT HASHED. It says whose smell this is, which is
            # a fact about this observer's recognition of the source and not
            # about the smell: learning whose a fact is is not a change to
            # the fact. Measured, chat 95 turn 9 -- a body the player had
            # been smelling for nine beats was recognised, the label went
            # from a stranger descriptor to a name, the authored scent string
            # was byte-identical, and the moved key re-declared the smell as
            # this beat's news. `level` stays: a smell that arrives muffled
            # is delivered differently, which is a change in the percept
            # rather than in the reader of it. New tag, so an old ledger's
            # label-hashed key degrades to first sight instead of to
            # `changed` (`standing_verdicts`).
            dedupe_key=standing_key(
                "scent_state", (source.get("key"),), (scent, level)),
        ))
    return out


def room_content_percepts(*groups):
    """Standing things in the observer's room that are not bodies: a crowd, a
    courier waiting by a door, a notice nailed to a post.

    Three world subsystems (`world/crowds.py`, `story/couriers.py`,
    `story/artifacts.py`) each publish a reading seam that has ALREADY decided
    what a bystander in that room takes in -- the figure and which door he
    makes for, never the message; that a bill hangs there, never its wording.
    Room scope is likewise theirs: every caller passes the observer's own
    room, so nothing here re-decides admission. What was missing was a percept
    to put it in, so all three delivered to nobody.

    `ambient`, because that is what these are: a standing feature of the room
    rather than an event, a body, or a sensation on this body.
    """
    out = []
    for entries in groups:
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            desc = " ".join(str(entry.get("what") or "").split())
            if not desc:
                continue
            if desc[-1:] not in ".!?":
                desc += "."
            # Keyed on the subject's own uid where it has one, so a crowd that
            # thins from a crush to a press is a CHANGED percept and re-renders
            # in a delta view, while the same crowd unchanged stays furniture.
            key = str(entry.get("uid") or entry.get("artifact_id") or "")
            # AND KEYED ON THE STATE, NEVER ON THE SENTENCE COMPOSED FROM IT.
            # A stable subject paired with prose content is the one
            # combination in this family that manufactures a false `changed`:
            # every re-rendering of an unchanged fact reads as an event, and
            # `leads_the_beat` promotes an event into the beat half, where
            # `_render_observed_events` numbers it as an obligation the
            # narrator must write a sentence about. Measured, chat 95: one
            # crowd whose band never left "a dozen or so" for sixteen turns
            # recorded `changed` seven times, because `describe` composes a
            # top-two-of-tally over a membership that walks its errands --
            # five spellings of one unchanged fact.
            #
            # A seam that publishes no state (a courier, a posted notice) has
            # nothing else to be identified by and keeps the description as
            # its content; the tag differs so an old ledger's prose-hashed
            # key reads as a subject never held -- first sight, which
            # `leads_the_beat` refuses for an ambient -- rather than as a
            # claim that something moved (`standing_verdicts`' own
            # degradation rule).
            state = entry.get("state")
            if isinstance(state, (list, tuple)) and any(
                    str(v or "").strip() for v in state):
                dedupe = standing_key("content_state", (key,),
                                      tuple(str(v or "") for v in state))
            else:
                dedupe = standing_key("content", (key,), (desc,))
            out.append(Percept(
                kind="ambient", channel="sight",
                data={"desc": desc},
                salience=0.35,
                dedupe_key=dedupe,
            ))
    return out


def chatter_percepts(entries):
    """The room's talk: a hum band as ground, at most one fragment as figure.

    Both arrive from `common.chatter_for_room`, which — like the three
    `room_content_percepts` seams — has ALREADY decided what a bystander in
    that room takes in: the hum is a band over the last window's charter
    acts, and the fragment is the who-asked-whom-about-whom triple with its
    labels already licensed by recognition. Nothing here re-decides
    admission; this is only the delivery.

    `hearing`, because that is the channel a murmur rides — prose has one
    channel, so anything rendered verbatim IS foreground, which is why the
    fragment count upstream is zero or one (the walla rule,
    DESIGN_BACKGROUND_PRESENTATION §A1). The structured triple rides `data`
    beside the composed clause so the projection stays auditable: the
    engine holds no sentence the crowd said, so none can be restated.

    Dedupe: the hum keys on its band, so an unchanged murmur is standing
    furniture and only a change in loudness re-renders; the fragment keys on
    the act's identity, so the same act never surfaces twice while its
    window stands.
    """
    out = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        desc = " ".join(str(entry.get("what") or "").split())
        if not desc:
            continue
        if desc[-1:] not in ".!?":
            desc += "."
        if entry.get("kind") == "fragment":
            data = {"desc": desc}
            for field in ("speaker_label", "act", "other_label",
                          "subject_label"):
                data[field] = str(entry.get(field) or "")
            key = str(entry.get("uid") or "")
            out.append(Percept(
                kind="ambient", channel="hearing", data=data,
                salience=0.45,
                dedupe_key=standing_key("chatter", (key,), (key,)),
            ))
        else:
            band = str(entry.get("band") or "")
            out.append(Percept(
                kind="ambient", channel="hearing",
                data={"desc": desc, "hum": band},
                salience=0.3,
                dedupe_key=standing_key("hum", (entry.get("uid"),),
                                        (band,)),
            ))
    return out


def micro_round_percept(text):
    """One interaction-loop micro-round delivery, as a percept.

    The micro loop renders its own prose and gated it with `_delivery_ok` when
    the round ran, so admission is decided upstream and nothing is re-decided
    here. What matters is that it goes in the SAME list as everything else:
    appended to the finished view instead, it arrived after the tripwires had
    run and its observation atom had to be hand-written -- the one atom in the
    payload whose channel, intensity and self-direction were asserted rather
    than derived, in a projection whose entire safety argument is that it is
    derived (`observations_from_render`).

    `mixed`, and said plainly: the loop hands over prose, not an IR, so the
    channel genuinely is not known. An honest "several, or unclear" beats a
    fabricated "sight". The residual that would fix it properly -- the micro
    loop emitting percepts of its own -- is design_notes/13-composer-build.md's,
    and lives in `agents/loops.py`.
    """
    text = " ".join(str(text or "").split())
    if not text:
        return None
    return Percept(
        kind="ambient", channel="mixed",
        data={"desc": text},
        salience=0.4,
        dedupe_key=standing_key("micro", (text,), (text,)),
    )


def micro_round_percepts(deliveries):
    """ONE PERCEPT PER DELIVERED LINE. `delivered_views[observer]` is a LIST.

    `micro_round_percept` above takes one line, and the outcome composer
    handed it the whole list. `str(["a", "b"])` does not fail -- it renders
    the Python repr -- so the bracket, the quotes and the comma went into the
    composed view verbatim, and from there into the observations projected
    off that view and into the episode minted from it. Measured over chat 98:
    68 of the 142 stored character views carry a `['...']` span, on 24 of the
    38 turns; the composer's own dialogue tripwire caught four of them and
    said so ("engine defect, view delivered as composed") while the view
    shipped anyway.

    The class is a shape mismatch at a seam, not a rendering bug, so it is
    fixed by naming the shape: a delivery is one line, a round delivers
    several, and the caller passes what it has. A bare string still works --
    it is one delivery.
    """
    if deliveries is None:
        return []
    if isinstance(deliveries, str):
        deliveries = [deliveries]
    out = []
    for line in deliveries:
        percept = micro_round_percept(line)
        if percept is not None:
            out.append(percept)
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
        dedupe_key=standing_key("residue", (level,),
                                (targeted, loud_event, pain)),
    )]


# --------------------------------------------------------------------------
# Layer A -- event percepts
# --------------------------------------------------------------------------

def speech_percept(entry, rel, observer_name, *, display, can_see,
                   proximity=None, order_key=0, observer_id=None,
                   senses=None):
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
    level = line_hear_level(entry, rel, observer_name, proximity=proximity,
                            senses=senses)
    if level == "none" and rel.get("open_group_continuity") \
            and volume.casefold() in ("normal", "loud", "shout"):
        # Compatibility floor for a rerolled checkpoint predating the
        # near-group position repair. It grants hearing only; sight and every
        # other channel still ride the relation's real spatial fields. (The
        # onset prose path carried the twin of this rescue and has since been
        # deleted, so this is the only copy.)
        level = "full"
    if level == "none":
        return None
    channel = rel.get("comm_channel")
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
    # WHICH channel carried it, when one did. Not decoration: a voice arriving
    # over a speaker is a different fact from a voice arriving from a body in
    # the room, and a mind handed the second when the first is true has been
    # told the speaker is present. The renderer says so and the observation
    # carries it, so nothing downstream can quietly lose the distinction.
    if isinstance(channel, dict) and not rel.get("same_room"):
        data["via"] = str(channel.get("name") or channel.get("id") or "")
        data["via_channel"] = str(channel.get("id") or "")
    return Percept(
        kind="speech", channel="hearing", source_label=display,
        fidelity=fidelity, data=data,
        salience=0.75 if volume in ("loud", "shout") else 0.7,
        suddenness=0.5 if volume in ("loud", "shout") else 0.1,
        order_key=order_key,
        dedupe_key="speech:" + _short_hash(entry.get("speaker"), body),
    )


def communication_percept(entry, rel, observer_name, *, display, can_see,
                           proximity=None, order_key=0, observer_id=None,
                           senses=None):
    """Admit described communication without manufacturing a quotation."""
    if concealed_from_observer(entry, observer_name, observer_id):
        return None
    from .common import communication_surface
    surface = communication_surface(entry)
    if not surface:
        return None
    volume = str(entry.get("volume") or "normal")
    level = line_hear_level(entry, rel, observer_name, proximity=proximity,
                            senses=senses)
    if level == "none":
        return None
    # Partial hearing cannot deliver a proposition whose words were never
    # specified.  It carries only that communication occurred.
    data = {
        "surface": surface if level == "full" else "speaks indistinctly",
        "level": level, "volume": volume, "can_see": bool(can_see),
        "directed_at_self": any(
            _addresses(target, observer_name)
            for target in entry.get("targets") or []),
    }
    channel = rel.get("comm_channel")
    if isinstance(channel, dict) and not rel.get("same_room"):
        data["via"] = str(channel.get("name") or channel.get("id") or "")
    return Percept(
        kind="communication", channel="hearing", source_label=display,
        fidelity="full" if level == "full" else "fragment", data=data,
        salience=0.7, order_key=order_key,
        dedupe_key="communication:" + _short_hash(
            entry.get("speaker"), entry.get("act"), entry.get("content")),
    )


def act_percept(scene, event, observer_name, actor_name, rel, *,
                display, can_see, self_forms=None, self_pronouns=None,
                other_forms=None,
                order_key=0,
                observer_id=None, surface=None):
    """Admit one action element's observable surface for one observer, or
    None. Gates: concealment, rear arc, sight (an action is visible or it is
    nothing -- a touch-only source contributes sensation percepts instead,
    never an event surface)."""
    # Each refusal below is recorded with the reason it refused. They all
    # return None, and from outside the four are indistinguishable from "the
    # actor did nothing" -- which is how a body stood exposed inside another
    # for four turns while this function behaved perfectly. No-op when debug
    # capture is off; one ContextVar read on the hot path.
    _who = "%s -> %s" % (actor_name, observer_name)
    if concealed_from_observer(event, observer_name, observer_id):
        note_step_decision("act_percept", _who, "refused",
                           "concealed from this observer")
        return None
    if surface is None:
        from .common import observable_action_text
        surface = observable_action_text(event)
    surface = str(surface or "").strip()
    if not surface:
        note_step_decision("act_percept", _who, "refused",
                           "no observable surface -- a mental beat")
        return None                       # a mental beat is imperceptible
    if entity_arc(scene, observer_name, actor_name) == "rear":
        note_step_decision("act_percept", _who, "refused",
                           "actor is in the observer's rear arc")
        return None
    if not can_see:
        note_step_decision("act_percept", _who, "refused",
                           "observer cannot see (sight gate)")
        return None
    note_step_decision("act_percept", _who, "delivered", surface[:120])
    targets_self = any(
        same_subject(scene, target, observer_name)
        or str(target or "").strip().casefold() in {
            str(form or "").strip().casefold() for form in self_forms or ()}
        for target in event.get("targets") or ())
    if targets_self and self_forms and self_pronouns:
        surface = _action_target_second_person(
            surface, self_forms, self_pronouns, other_forms)
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
    # The air of the place, after the bodies in it and after what is on them.
    "ambient": 8, "scent": 9,
}

#: Standing kinds that DESCRIBE a body's own surface rather than report its
#: situation. Deliberately excludes `pose` and `environment`: where a body is
#: and how it is arranged CHANGE, and are the two things a mind cannot read
#: off its own card.
_OWN_BODY_DESCRIPTION_KINDS = frozenset(("body_part", "body_region"))

# A sensation is standing only in the sense that it has no one-time event
# order.  It is not inert scenery: pressure, movement, heat, pain and an
# ongoing contact action are present bodily input on every beat they remain
# true.  Player-mode presentation compression must therefore never dedupe it.
# Memory keeps a separate rule below: an unchanged sensation by itself is not
# enough to mint a new autobiographical episode.
ACTIVE_STANDING_KINDS = frozenset(("sensation",))


def _is_own_body_description(p):
    """Is this standing percept the observer describing their OWN surface.

    Character mode re-renders the full standing state every beat, and the
    reason is sound: a character agent is a stateless LLM call, so what is
    not in context is not in the mind. That argument does not reach the
    observer's own anatomy, because the CARD is in that context on every one
    of those calls -- `embodiment.extra_parts` carries the same count, place
    and description the view renders, so the view is repeating what the
    prompt already said.

    In a measured 27-beat run, 43% of one character's perception payload
    described their own body: 13,298 characters of authored anatomy, 92%
    byte-identical to the previous beat. A stable horn description repeated
    every beat despite the same structured horn data already being on the
    character card.

    Suppression is by dedupe key, not by kind, so the mutable half re-earns
    itself for free: `tucked` is hashed into a body_part's key, so wings
    coming out from under a coat change the key and render. `full_render`
    (an explicit look) re-renders everything, which is how a mind examines
    itself on purpose.
    """
    return (p.source_label == "you"
            and p.kind in _OWN_BODY_DESCRIPTION_KINDS)


_TIER_PHRASES = dict(_ENGLISH_COMPOSITOR["tier_phrases"])
_SIZE_PHRASES = dict(_ENGLISH_COMPOSITOR["size_phrases"])


# A placeholder holding the position the presence group will occupy, so
# the group can be rendered once the whole set is known without losing
# where it belongs in the discourse order. Identity comparison only.
_PRESENCE_SLOT = ("presence-slot", None)


#: The four verdicts a standing percept can carry for ONE observer.
#: `unchanged` -- this observer's own previous ledger holds this exact key.
#: `changed`   -- it holds this subject under different content.
#: `first`     -- it holds nothing about this subject at all.
#: `reearn`    -- first sight again: a body met before, being re-delivered.
STANDING_VERDICTS = ("unchanged", "changed", "first", "reearn")


def standing_verdicts(percepts, prev_standing=frozenset(),
                      prev_described=frozenset()):
    """What each standing percept IS for this observer, as {dedupe_key: verdict}.

    THE DIFF OPERANDS ARE NOT TWO SCENES. They are this observer's admitted
    percepts for this beat and this observer's own ledger from the last one,
    and that is the whole firewall argument: a subject with no percept here
    produces no verdict and therefore no sentence, so a change in a room
    this mind cannot see is not withheld by a rule -- there is nothing for
    the rule to be about. A world diff is the shape that leaks; this is not
    one. The signature is Layer B's usual: percepts and mode state, no scene
    and no database, so the verdict cannot widen what the percepts already
    admitted.

    An EMPTY previous ledger means "no record", not "nothing was there" --
    the opening beat, a mind that just woke, a chat stored before the split
    key existed. Nothing can then read `changed`, because there is no
    subject to have been holding: the world arrives as background, never as
    a claim that any of it just moved. Old single-hash keys degrade the same
    way, by `_subject_prefix` answering None for them, so an upgraded chat
    costs one re-description per observer and never a false event.
    """
    prev_standing = frozenset(prev_standing or ())
    prev_described = frozenset(prev_described or ())
    subjects = {sp for sp in (_subject_prefix(k) for k in prev_standing) if sp}
    out = {}
    for p in percepts or []:
        if p.order_key is not None:
            continue
        if p.dedupe_key in prev_standing:
            out[p.dedupe_key] = "unchanged"
            continue
        prefix = _subject_prefix(p.dedupe_key)
        if prefix and prefix in subjects:
            out[p.dedupe_key] = "changed"
            continue
        if p.kind == "appearance" and (
                p.data.get("reearn")
                or str(p.data.get("source_key") or "") in prev_described):
            out[p.dedupe_key] = "reearn"
            continue
        out[p.dedupe_key] = "first"
    return out


#: Standing kinds whose arrival IS the beat. A body that was not there and
#: now is, and a sensation this body was not feeling and now feels, are both
#: events wearing a standing percept's shape; a room, a smell or an authored
#: description first perceived is the background arriving, not news.
_FIRST_SIGHT_LEADS = frozenset(("presence", "sensation"))


def _appearance_restates_label(percept):
    """Does this appearance percept say only what the observer's own label
    for the body already says.

    The presence line has already reported who is here, under this
    observer's label; an appearance summary identical to that label is the
    same fact a second time, and for a one-word summary it is ungrammatical
    besides. Measured, chat 98 turn 38: the player's ENTIRE view for the
    beat was "The lieutenant commander is close by. You see lieutenant
    commander." Compared on `_label_core`, which drops the article and the
    ordinal distinguisher, so the two spellings of one noun cannot slip past
    each other and the second of a pair is treated like the first.

    A percept this answers True for was still DELIVERED -- the observer has
    the description, it just cost no sentence -- so the caller records it in
    the first-mention ledger rather than leaving the body undescribed and
    re-describing it next beat.
    """
    if percept.kind != "appearance":
        return False
    desc = _appearance_as_prose((percept.data or {}).get("description"))
    if not desc:
        return False
    return _label_core(percept.source_label) == _label_core(desc)


def appearance_delta(percept):
    """The transition prose an appearance percept carries, or "".

    A delta is not `force`. `force` says an objective visible-form channel
    was written this beat, which is a fact about the Director and answers
    nothing about this observer. A delta is the DIFFERENCE between two
    states of dress, computed where the previous scene exists and attached
    only to an observer who held that body at full sight last beat
    (`perception._composer_standing_percepts`). It is therefore evidence
    that something moved for this observer, and it outranks a dedupe key
    that did not move -- an authored summary that never mentions clothing
    hashes the same whatever the body is wearing.
    """
    return str((percept.data or {}).get("delta") or "").strip()


def leads_the_beat(percept, verdict, prev_standing):
    """Does this standing percept belong in the BEAT half of a player view.

    `changed` always does -- something about a subject this observer already
    held is different now, which is the definition of the beat. `first` does
    only for the kinds above, and only against a ledger that exists: with no
    previous record every percept is a first sight, and a view that led with
    all of them would be claiming the whole world just happened.
    """
    if not prev_standing:
        return False
    if verdict == "changed":
        return True
    if percept.kind == "appearance" and appearance_delta(percept):
        return True
    return verdict == "first" and percept.kind in _FIRST_SIGHT_LEADS


def as_beat(percept):
    """The same percept, marked as this beat's content rather than its
    background. Read by `observations_from_render`, which is how a changed
    pose reaches the narrator's numbered deliveries instead of its
    wallpaper. Frozen instances, so this is a copy -- the caller's own
    percept list is untouched, and `_composer_company` still reads it."""
    return dataclasses.replace(
        percept, data={**(percept.data or {}), "beat": True})


def player_view_order(spans):
    """The order a player view's spans render in, for ANY language pack.

    Four ranks, and the sort is stable, so each pack keeps its own discourse
    order inside a rank: this beat's EVENTS in declared order, then the
    standing percepts `leads_the_beat` marked as this beat's news, then a
    changed room, then the background. The room goes last in the beat half
    for the same reason `_render_episode_english` puts it last -- scene
    setting read first swallows what happened.

    A pack must not spell this rule itself. `language_adapters/japanese.py`
    did, and its own partition emitted the changed standing percepts BEFORE
    the events because that was the order it happened to iterate in, so a
    Japanese player view opened on a pose while the English one opened on the
    act that moved it. Rank is read off what the percept already carries --
    `order_key` for an event, the `beat` mark `as_beat` stamps for the rest --
    so there is nothing here for a second renderer to re-derive.
    """
    def rank(span):
        percept = span[0]
        if percept.order_key is not None:
            return 0
        if not (percept.data or {}).get("beat"):
            return 3
        return 2 if percept.kind == "environment" else 1
    return sorted(spans, key=rank)


@dataclass
class RenderedView:
    text: str
    spans: list                 # [(Percept, sentence)]
    standing_keys: set          # dedupe keys of ALL standing percepts seen
    described: set              # source names whose full appearance rendered


#: Region and zone names that take a plural verb. An engine constant because
#: the NAMES are engine constants (`attire.REGIONS` plus the torso zones);
#: whether a LANGUAGE agrees in number is the pack's business, and a pack that
#: does not gives both `exposed_detail` templates the same string.
PLURAL_PLACES = frozenset({"arms", "hands", "legs", "feet"})


def _cap(sentence):
    sentence = str(sentence or "").strip()
    return sentence[:1].upper() + sentence[1:] if sentence else sentence


_COUNT_WORDS = {
    int(number): str(word)
    for number, word in _ENGLISH_COMPOSITOR["count_words"].items()
}


def _presence_clause(p):
    """One body's presence as a bare clause -- no capital, no full stop, so
    it can stand alone or be joined with others."""
    room = str(p.data.get("room") or "")
    tier = (_en("presence_in_room", room=room) if room
            else _TIER_PHRASES.get(str(p.data.get("tier")),
                                   _TIER_PHRASES["default"]))
    side = p.data.get("side")
    side_clause = _en("side", side=side) if side in ("left", "right") else ""
    # Relative magnitude qualifies every other clause in the view -- what can
    # be reached, held, or resolved at all -- so it rides the STANDING
    # presence sentence rather than waiting for an act to make it visible. An
    # unknown or absent label costs wording and never the beat.
    size = _SIZE_PHRASES.get(str(p.data.get("size") or ""), "")
    size_clause = f", {size}" if size else ""
    # Seen over something: name what, and how much of them shows. Plain
    # words -- "behind the counter, from the waist up" -- never a fraction.
    behind = str(p.data.get("behind") or "").strip()
    cover_clause = ""
    if behind:
        cover_clause = _en("presence_behind", behind=behind)
        shows = str(p.data.get("shows") or "").strip()
        if shows:
            cover_clause += _en("presence_shows", shows=shows)
    return f"{p.source_label} is {tier}{side_clause}{size_clause}{cover_clause}"


def _join_clauses(clauses):
    if len(clauses) == 1:
        return clauses[0]
    if len(clauses) == 2:
        return str(_ENGLISH_COMPOSITOR["join"]["two"]).format(
            first=clauses[0], last=clauses[1])
    return ", ".join(clauses[:-1]) + str(
        _ENGLISH_COMPOSITOR["join"]["many"]).format(last=clauses[-1])


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
            # Against the ACTIVE pack's label, not the English compat export.
            # Layer A mints this label through `_dim_figure()`, so comparing
            # it to `DIM_FIGURE` asks whether the story is in English -- and
            # where it is not, this `startswith` can never be true and the
            # rule silently does not run. What that costs is the COUNT:
            # identical clauses collapse either way, so an observer who can
            # plainly see two figures was told about one.
            #
            # The wording around the label stays English on purpose. This is
            # `_render_view_english`, the reference renderer a pack's own
            # adapter falls back to when it raises, and its contract is that
            # a malformed pack costs wording and never the beat. Losing a
            # fact the observer's own eyes have is not wording.
            singular, plural = _dim_figure(), _dim_figure(True)
            if n > 1 and clause.startswith(singular + " "):
                word = _COUNT_WORDS.get(n, str(n))
                rendered.append(
                    f"{word.casefold()} {plural}"
                    + clause[len(singular):].replace(" is ", " are ", 1))
            else:
                rendered.append(clause)
        out.append((group[0], _cap(_join_clauses(rendered)) + "."))
    return out



#: Articles and connectives a hand-authored `kind` may already carry. The
#: renderer supplies its own count word, so "a", "an", "the" and a leading
#: "and" would double up ("A and a long flexible tail...").
_LEADING_CONNECTIVES = tuple(_ENGLISH_COMPOSITOR["leading_connectives"])


def _strip_leading_connective(kind):
    text = " ".join(str(kind or "").split())
    lowered = text.casefold()
    for prefix in _LEADING_CONNECTIVES:
        if lowered.startswith(prefix):
            return text[len(prefix):]
    return text


def _render_body_part(p):
    """"Six tails emerge from the back of her waist" -- not "tail x6"."""
    count, kind = p.data["count"], p.data["part"]
    you = p.source_label == "you"
    word = _COUNT_NAMES.get(count, str(count))
    # A CARD'S `kind` IS AUTHORED, so it arrives however a human wrote it.
    # Measured live: "membranous bat-like wings" x2 rendered as "Two
    # membranous bat-like wingss", and "and a long flexible tail ending in
    # a spade" x1 as "A and a long flexible tail ...". The docstring's
    # example assumes a bare singular noun ("tail" -> "Six tails"); real
    # cards carry plurals and stray connectives, and a body's own anatomy
    # reading as gibberish in its owner's perception view is the loudest
    # possible way to look broken.
    kind = _strip_leading_connective(kind)
    plural = kind if kind.rstrip().endswith("s") else f"{kind}s"
    subject = f"{word} {kind}" if count == 1 else f"{word} {plural}"
    verb = "emerges" if count == 1 else "emerge"
    aspect, at = p.data["aspect"], p.data["at"]
    whose = "your" if you else f"{p.source_label}'s"
    if aspect == "sides":
        where = _en("body_part_where_sides", whose=whose, at=at)
    elif aspect in ("left", "right"):
        where = _en(
            "body_part_where_side", aspect=aspect, whose=whose, at=at)
    else:
        where = _en(
            "body_part_where_aspect", aspect=aspect, whose=whose, at=at)
    sentence = f"{_cap(subject)} {verb} {where}"
    if p.data.get("description"):
        sentence += f", {p.data['description'].rstrip('.')}"
    if p.data.get("tucked"):
        sentence += _en("body_part_tucked")
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
        subject = _en("pose_self_past" if past else "pose_self_present")
    else:
        subject = _en(
            "pose_other_past" if past else "pose_other_present",
            label=_cap(p.source_label))
    def value(field):
        text = str(p.data.get(field) or "").strip()
        # Episode prose is first person whether the pose belongs to the mind
        # or to somebody it watched.  Thus another body's ``astride you`` is
        # remembered as ``astride me``, while the owner's ``your heels`` is
        # remembered as ``my heels``.
        return _first_person(text) if past else text

    parts = [value("posture")]
    support = value("support")
    if support:
        parts.append(support if support.split()[:1] and support.split()[0] in
                     _POSE_PREPOSITIONS else _en("pose_support", support=support))
    other = value("relative_to")
    if other:
        relation = value("relation")
        parts.append(f"{relation} {other}" if relation
                     else _en("pose_relation", other=other))
    clause = " ".join(x for x in parts if x).strip()
    if not clause:
        return ""
    sentence = f"{subject} {clause}"
    constraint = value("constraint")
    if constraint:
        sentence += f", {constraint}"
    detail = value("detail")
    if detail:
        sentence += f" — {detail.rstrip('.')}"
    return sentence.rstrip(".") + "."


_POSE_PREPOSITIONS = frozenset(_ENGLISH_COMPOSITOR["pose_prepositions"])
_POSE_BARE_DETERMINERS = frozenset(
    _ENGLISH_COMPOSITOR.get("pose_bare_determiners") or ())


def _feature_items(rows, *, placed=True):
    """The furniture rows as rendered noun phrases, near to far.

    `placed` is False for furniture in ANOTHER room, seen through an opening.
    The whole distance vocabulary here -- close by, across the room, at the
    edge of sight -- is measured WITHIN one room, so spending it on the far
    side of a threshold states a distance nobody measured: "across the room"
    about a thing that is across a different room. The things are named and
    the distance is simply not claimed, which is what the observer actually
    has.
    """
    items = []
    for row in rows or ():
        desc = str((row or {}).get("desc") or "").strip()
        if not desc:
            continue
        if not placed:
            items.append(desc)
            continue
        if row.get("peripheral"):
            items.append(_en("feature_glimpse", desc=desc))
            continue
        tier = _TIER_PHRASES.get(str(row.get("tier") or ""), "")
        side = row.get("side")
        where = _en("side", side=side).strip() if side in ("left", "right") \
            else ""
        place = " ".join(part for part in (tier, where) if part)
        items.append(_en("feature_item", desc=desc, place=place).strip())
    return items


def _render_features(rows):
    """The furniture this observer's eyes reach, as one sentence a person
    would say -- near to far, each thing by where it lies. NEVER the grid:
    no cell, no fraction, no degree, no sector name reaches the page; a
    thing is close by, across the room, on your left, or at the edge of
    sight, which is the whole vocabulary a body has for it."""
    items = _feature_items(rows)
    if not items:
        return ""
    return _en("features", items=_join_clauses(items))


def _render_openings(openings):
    """Every boundary of this room the observer can see, and what sight
    reaches past it.

    THE CLASS: a way out is a fact about the room, and what an opening
    admits is a fact about the opening. The engine had neither. Door
    pseudo-anchors are minted for every edge (`spatial_geometry`) and then
    dropped from the furniture list as `implicit` on the stated grounds that
    "the exits digest already carries them" -- but that digest
    (`director._egocentric_exits`) is built for the Director and reaches no
    observer, so the doorway was minted and discarded and no view in this
    engine had ever named one. `presence_percepts` meanwhile grew a
    cross-room tier for BODIES, because an interviewer was receiving the cell
    and not the woman in it; the same subtraction was never lifted for the
    PLACE, so a mind could see a person through a door and never the room
    they stood in.

    SUBTRACTS IN THREE PLACES, and the order matters. A boundary the
    observer's own cone or line does not reach never arrives at all. A
    boundary sight does not cross (a shut door, a wall) arrives as itself and
    NAMES NOTHING BEYOND IT -- naming the room behind a closed door would be
    the leak this whole layer has to avoid. And a room beyond that is dark
    arrives as darkness, because you see what is lit.
    """
    parts = []
    for opening in openings or ():
        desc = str((opening or {}).get("desc") or "").strip()
        if not desc:
            continue
        state = str(opening.get("state") or "")
        room = str(opening.get("room_name") or "").strip()
        if state == "blind":
            parts.append(_cap(_en("opening_closed", opening=desc)))
            continue
        if state == "dark":
            parts.append(_cap(_en("opening_dark", opening=desc)))
            continue
        if state != "seen" or not room:
            parts.append(_cap(_en("opening_bare", opening=desc)))
            continue
        parts.append(_cap(_en("opening_seen", opening=desc, room=room)))
        notes = str(opening.get("room_notes") or "").strip()
        if notes:
            parts.append(notes if notes[-1:] in ".!?" else notes + ".")
        items = _feature_items(opening.get("features"), placed=False)
        if items:
            parts.append(_en("opening_features", items=_join_clauses(items)))
    return " ".join(parts)


def _render_standing(p):
    if p.kind == "environment":
        parts = []
        if p.data.get("room_name"):
            parts.append(_en("room", room=p.data["room_name"]))
        if p.data.get("room_notes"):
            notes = str(p.data["room_notes"]).strip()
            if notes and notes[-1:] not in ".!?":
                notes += "."
            parts.append(notes)
        sentence = _render_features(p.data.get("features"))
        if sentence:
            parts.append(sentence)
        ways = _render_openings(p.data.get("openings"))
        if ways:
            parts.append(ways)
        light = str(p.data.get("light") or "").casefold()
        if light in ("dim", "low"):
            parts.append(_en("light_dim"))
        elif light in ("dark", "none", "pitch_black", "black"):
            parts.append(_en("light_dark"))
        return " ".join(parts)
    if p.kind == "presence":
        return _cap(_presence_clause(p)) + "."
    if p.kind == "appearance":
        # A CHANGE RENDERS AS THE CHANGE. Only when there is nothing
        # readable to say about it does the full description stand in --
        # failing toward delivering more, because a change the observer can
        # see and the page does not mention is the worse error.
        change = str(p.data.get("delta") or "").strip()
        if change:
            # The LABEL, because a change needs a body to belong to: the
            # first cut of this rendered "You see no longer wearing haori."
            # -- the delta reads as a predicate and the appearance template
            # it borrowed supplies a subject that is the wrong one. The
            # label is this observer's own, so it carries the identity floor
            # (a stranger stays "the unfamiliar person") for free.
            return _cap(_en("appearance_change",
                            label=p.source_label or "someone", change=change))
        desc = _appearance_as_prose(p.data.get("description"))
        if _appearance_restates_label(p):
            return ""
        return _en("appearance", description=desc) if desc else ""
    if p.kind == "pose":
        return _render_pose(p)
    if p.kind == "body_part":
        return _render_body_part(p)
    if p.kind == "body_state":
        parts = []
        if p.data.get("posture"):
            parts.append(_en("posture", value=p.data["posture"]))
        if p.data.get("activity"):
            parts.append(_en("activity", value=p.data["activity"]))
        if p.data.get("held_items"):
            parts.append(_en("held", items=", ".join(p.data["held_items"])))
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
        subject = (_en("exposed_self", place=place)
                   if p.source_label == "you" else _en(
                       "exposed_other", label=_cap(p.source_label), place=place))
        # HALF THE PLACE NAMES ARE PLURAL. `place` is an engine constant -- a
        # member of `attire.REGIONS` or a torso zone -- so the agreement is
        # decidable here, and "Hinami's exposed feet is visible" was on the
        # page. Not a spelling rule: `feet` is plural and does not end in `s`,
        # which is precisely the case a spelling rule gets wrong.
        template = ("exposed_detail_plural"
                    if place.casefold() in PLURAL_PLACES else "exposed_detail")
        return _en(template, subject=subject, detail=detail)
    if p.kind == "ambient":
        desc = str(p.data.get("desc") or "").strip()
        if desc and desc[-1:] not in ".!?":
            desc += "."
        return desc
    if p.kind == "scent":
        return _render_scent(p)
    return ""


def _render_scent(p, *, episode=False):
    """Three shapes, chosen by what the observer actually has a channel to:
    the smell and whose it is, the smell alone, or the smell as a faint thing
    from somewhere beyond. The percept decides which; this only spells it."""
    prefix = "episode_" if episode else ""
    scent = str(p.data.get("scent") or "").strip()
    if not scent:
        return ""
    if p.data.get("level") == "muffled":
        return _en(prefix + "scent_faint", scent=scent)
    if p.data.get("attributed") and p.source_label:
        return _en(prefix + "scent_source",
                   label=_cap(p.source_label), scent=scent)
    return _en(prefix + "scent_air", scent=scent)


def _render_event(p):
    if p.kind == "speech":
        body = p.data.get("body") or ""
        via = str(p.data.get("via") or "")
        # `_inject_dialogue` into an empty document is the production grammar
        # (bare-infinitive heard form, conducted, articulation) emitting into
        # nothing -- no duplicate detection against model prose needed.
        if p.fidelity == "fragment":
            line = _en("muffled", fragment=p.data.get("fragment", ""))
        else:
            line = _inject_dialogue(
                "", p.source_label, f'"{body}"', p.data.get("level", "full"),
                p.data.get("volume", "normal"), p.data.get("can_see", False),
                conducted=p.data.get("conducted", False),
                tone=p.data.get("tone", ""),
                articulation=p.data.get("articulation", ""))
        # The route is part of what was perceived, not a flourish. A voice on a
        # speaker and a voice at your shoulder are different facts, and the
        # view is where a reader learns which one this was -- drop it here and
        # the whole channel reads as somebody standing in the room.
        if via and line:
            line = _en("speech_via", sentence=line.rstrip("."), via=via)
        return line
    if p.kind == "communication":
        line = _observable_predicate(
            p.source_label, p.data.get("surface")) or ""
        via = str(p.data.get("via") or "")
        return (_en("speech_via", sentence=line.rstrip("."), via=via)
                if via and line else line)
    if p.kind == "act":
        return _observable_predicate(
            p.source_label, p.data.get("surface")) or ""
    if p.kind == "crossing":
        if p.data.get("direction") == "arrived":
            return _en("arrived", label=_cap(p.source_label))
        return _en("departed", label=_cap(p.source_label))
    if p.kind == "substance":
        clause = str(p.data.get("clause") or "").strip()
        return _cap(clause) + "." if clause else ""
    return ""


def _render_view_english(percepts, *, mode="character",
                         prev_standing=frozenset(),
                         prev_described=frozenset(), full_render=False):
    """Decision-free realisation of one observer's percepts.

    ``mode='character'`` renders the full standing state every beat, including
    complete visible anatomy and attire for every OTHER person. The observer's
    own body description (`_is_own_body_description` -- anatomy and bare
    regions, never pose or place) is delta-suppressed because the updated card
    and self.attire already carry it into the same call.

    ``mode='player'`` LEADS WITH WHAT CHANGED. The view is two halves: the
    BEAT -- this beat's events in declared order, then the standing percepts
    `standing_verdicts` calls changed for THIS observer, with a changed room
    last -- and then the BACKGROUND: first mentions, re-encounters, and the
    sensations that are still true. What is continuously true is context;
    what is different since this observer last perceived it is the beat.
    ``full_render`` (an explicit look) re-renders the whole standing state,
    which is how the background is asked for on purpose. Active sensations
    are the standing exception in both modes: an unchanged contact is still
    being felt now, so it renders every beat -- in the background half.

    Events always render, in declared order -- chronology is authoritative.

    THE APPEARANCE BRANCH ASKS THE LEDGER BEFORE IT ASKS `force`. `force` is
    an objective judgement ("some visible-form channel moved this beat") and
    it was deciding a per-observer question. Measured live (chat 89, turns
    3-27): it fired on every single beat while the composed description
    stayed byte-identical, and the same 342-character card went to the
    narrator twenty-five times running. An overlay wiggle whose composed
    description hashes to the key this observer already holds is no change
    FOR THIS OBSERVER, and now suppresses; a description that actually moved
    renders as the change (the attire delta when there is one, the current
    description when there is not) and leads.

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

    player = mode == "player"
    delta = player and not full_render
    described = set(prev_described)
    standing_keys = set()
    seen_dedupe = set()
    verdicts = standing_verdicts(
        standing, prev_standing, prev_described) if player else {}
    # Presence is ONE observation -- who is here -- so the whole group takes
    # one side of the partition, decided before the loop reaches the first
    # of them: if any body in it is new or has moved tier, who is here is
    # this beat's news.
    presence_leads = player and any(
        leads_the_beat(p, verdicts.get(p.dedupe_key, "first"), prev_standing)
        for p in standing if p.kind == "presence")

    standing_spans = []         # the background half in player mode
    beat_spans = []             # player mode only
    presence_group = []
    for p in standing:
        standing_keys.add(p.dedupe_key)
        if p.dedupe_key in seen_dedupe:
            continue
        seen_dedupe.add(p.dedupe_key)
        verdict = verdicts.get(p.dedupe_key, "first")
        leads = player and leads_the_beat(p, verdict, prev_standing)
        if p.kind == "appearance":
            if (player and not full_render and verdict == "unchanged"
                    and not appearance_delta(p)):
                # Already delivered, byte for byte, to this observer. This
                # is the line `force` used to be able to walk past.
                continue
            if (player and not full_render and verdict == "reearn"
                    and not p.data.get("reearn")
                    and not p.data.get("force")):
                # The standing ledger says nothing about this body at all,
                # and the older first-mention ledger says it was described
                # once. Nothing here claims it moved, so it stays told.
                continue
        elif (delta and p.dedupe_key in prev_standing
              and p.kind not in ACTIVE_STANDING_KINDS):
            continue
        elif (not full_render and p.dedupe_key in prev_standing
                and _is_own_body_description(p)):
            continue
        # `standing` is already sorted by _STANDING_ORDER, so re-inserting
        # the presence group at the first presence position keeps the
        # discourse order of whichever half it belongs to intact.
        if p.kind == "presence":
            presence_group.append(p)
            if len(presence_group) == 1:
                (beat_spans if presence_leads else standing_spans).append(
                    _PRESENCE_SLOT)
            continue
        sentence = _render_standing(p)
        # A description the label already carried was delivered without
        # costing a sentence (`_appearance_restates_label`); leaving it out
        # of the ledger would re-offer it as a first mention every beat.
        if p.kind == "appearance" and (
                sentence or _appearance_restates_label(p)):
            described.add(str(p.data.get("source_key") or ""))
        if not sentence:
            continue
        if leads:
            beat_spans.append((as_beat(p), sentence))
        else:
            standing_spans.append((p, sentence))
    for half in (beat_spans, standing_spans):
        if _PRESENCE_SLOT in half:
            at = half.index(_PRESENCE_SLOT)
            group = _render_presence_group(presence_group)
            if half is beat_spans:
                group = [(as_beat(gp), sentence) for gp, sentence in group]
            half[at:at + 1] = group

    event_spans = []
    for p in events:
        if p.dedupe_key in seen_dedupe:
            continue
        seen_dedupe.add(p.dedupe_key)
        sentence = _render_event(p)
        if sentence:
            event_spans.append((p, _cap(sentence)))

    if player:
        # The ordering rule itself lives in `player_view_order`, which every
        # pack calls, so the reference renderer cannot drift from one.
        spans = player_view_order(event_spans + beat_spans + standing_spans)
    else:
        # Discourse rule: a sudden event chain leads; otherwise standing state
        # anchors the view and the beat follows.
        sudden = any(p.suddenness >= 0.6 for p, _ in event_spans)
        spans = (event_spans + standing_spans) if sudden \
            else (standing_spans + event_spans)
    text = " ".join(sentence for _, sentence in spans).strip()
    return RenderedView(text=text, spans=spans,
                        standing_keys=standing_keys, described=described)


def render_view(percepts, *, mode="character", prev_standing=frozenset(),
                prev_described=frozenset(), full_render=False,
                language=None, renderer=None):
    """Render through the story language's deterministic Layer-B adapter.

    Layer A's admitted ``Percept`` list is unchanged and remains the
    information boundary. A language adapter receives only that list and the
    ordinary render-mode state, so changing languages cannot grant it scene,
    database, or identity knowledge that the observer never earned.

    A QUIET BEAT STILL COMPOSES TO "" HERE, and that is the honest answer:
    this function renders a DELTA, and an empty delta means "nothing new",
    not "nothing reached this mind". The two are different states and only
    the stage that holds the observer decides which one the narrator is
    handed -- see `perception._composer_outcome`, which asks for the
    background on a player view the delta emptied rather than storing the
    None that `agents/narration.py` reads as a claim about the world.
    """
    selected = renderer if renderer is not None else _safe_renderer(language)
    if selected is not None:
        try:
            out = selected.render_view(
                percepts, mode=mode, prev_standing=prev_standing,
                prev_described=prev_described, full_render=full_render)
            # The tolerance below covered only a RAISE. An adapter that
            # returned successfully with a dict, a tuple or the bare text --
            # the shapes a pack gets wrong first -- went straight through,
            # and the caller read `.text`, `.standing_keys` and `.described`
            # off it one stage later, outside every guard. Checked here so a
            # malformed return costs the same as a malformed raise.
            if not isinstance(out, RenderedView):
                raise TypeError(
                    f"language renderer returned {type(out).__name__}, "
                    "not RenderedView")
            return out
        except Exception:
            # A view is what an observer perceives at all. A malformed pack
            # must cost wording, never the whole beat, so fall through to the
            # in-module reference renderer rather than killing the turn.
            logger.exception("language renderer failed; using English wording")
    return _render_view_english(
        percepts, mode=mode, prev_standing=prev_standing,
        prev_described=prev_described, full_render=full_render)


# --------------------------------------------------------------------------
# Layer B -- the episode renderer (memory mode)
# --------------------------------------------------------------------------

#: English compatibility view; the live table is read per-language below.
_YOU_TO_ME = tuple(
    (re.compile(pattern), replacement)
    for pattern, replacement in _ENGLISH_COMPOSITOR["second_to_first"]
)


def _second_to_first_rules():
    """The active pack's second->first person rewrites, compiled at use time.

    Bound from the English pack at import before, so the Japanese pack's
    あなた→私 rules were authored and dead: a first-person memory came out
    「あなたは立っている。」 sitting next to 「私は中庭にいた。」
    """
    from language_runtime import compositor_value
    return tuple((re.compile(pattern), replacement)
                 for pattern, replacement in compositor_value("second_to_first"))


def _first_person(text):
    """Second person -> first person, outside quoted spans (a quoted 'you'
    is what was said and stays verbatim)."""
    segments = linguistic(
        "agents.common", "_QUOTED_SPAN_RE").split(str(text or ""))
    rules = _second_to_first_rules()
    for i in range(0, len(segments), 2):
        seg = segments[i]
        for pattern, replacement in rules:
            seg = pattern.sub(replacement, seg)
        segments[i] = seg
    return "".join(segments)


_GENERIC_LABELS = frozenset(_ENGLISH_COMPOSITOR["generic_labels"])


def _episode_sentence(p):
    if p.kind == "speech":
        via = str(p.data.get("via") or "")
        if p.fidelity == "fragment":
            if via:
                return _en("episode_muffled_via", via=via,
                           fragment=p.data.get("fragment", ""))
            return _en(
                "episode_muffled", fragment=p.data.get("fragment", ""))
        body = p.data.get("body") or ""
        # The route rides into MEMORY too. A character who later recalls being
        # told something over a radio must not remember the speaker standing
        # there -- that is the same fact deleted one layer down, and memory is
        # where it would never be noticed.
        if via:
            return _en("episode_speech_via", via=via,
                       label=p.source_label, body=body)
        if p.data.get("conducted"):
            return _en(
                "episode_conducted", label=_cap(p.source_label), body=body)
        return _en("episode_speech", label=p.source_label, body=body)
    if p.kind == "act":
        surface = _first_person(str(p.data.get("surface") or "").strip())
        words = surface.split()
        if words:
            base = _base_from_third_person_s(words[0])
            if base:
                rest = " ".join(words[1:]).rstrip(".")
                ending = f" {rest}." if rest else "."
                return _en(
                    "episode_act", label=p.source_label,
                    action=base, ending=ending)
        sentence = _observable_predicate(p.source_label, surface)
        return sentence or ""
    if p.kind == "crossing":
        if p.data.get("direction") == "arrived":
            return _en("episode_arrived", label=_cap(p.source_label))
        return _en("episode_departed", label=_cap(p.source_label))
    if p.kind == "substance":
        clause = _first_person(str(p.data.get("clause") or "").strip())
        return _cap(clause) + "." if clause else ""
    if p.kind == "environment":
        name = p.data.get("room_name")
        return _en("episode_room", room=name) if name else ""
    if p.kind == "pose":
        return _render_pose(p, past=True)
    if p.kind == "sensation":
        clause = _first_person(str(p.data.get("clause") or "").strip())
        return _cap(clause) + "." if clause else ""
    if p.kind == "appearance":
        desc = _appearance_as_prose(p.data.get("description"))
        return _en("episode_appearance", description=desc) if desc else ""
    if p.kind == "scent":
        return _render_scent(p, episode=True)
    if p.kind == "residue":
        return _compose_residue_view(
            p.data.get("level"), targeted=p.data.get("targeted", False),
            loud_event=p.data.get("loud_event", False),
            pain=p.data.get("pain", False))
    return ""


def _render_episode_english(percepts, *, prev_standing=frozenset(),
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
        elif p.kind in ("environment", "sensation", "pose", "scent") \
                and p.dedupe_key not in prev_standing:
            # A pose that CHANGED is a real memory -- somebody knelt, or was
            # pinned. An unchanged one is furniture and the dedupe key keeps
            # it out, which is the same rule the room already lives under.
            # A scent lives under it for the same reason and earns its place
            # for a stronger one: a smell is among the most retrievable
            # things a mind stores, and the dedupe key already moves when the
            # grade does, so walking into range of one is the change.
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


def _safe_renderer(language):
    """The pack's adapter, or None to use the in-module English renderer.

    `renderer_for` raises when a pack names an adapter that is not available;
    that is a configuration fault, and it was reaching callers as a dead turn.

    `language=None` follows the story's contextvar. The default used to be the
    literal "en", so any caller that omitted the argument rendered English
    inside a Japanese turn and said nothing about it -- the same silent
    fallback this whole layer exists to avoid.
    """
    try:
        return renderer_for(
            current_language_id.get() if language is None else language)
    except LanguagePackError:
        logger.exception("no renderer for language %r; using English", language)
        return None


def render_episode(percepts, *, prev_standing=frozenset(),
                   prev_described=frozenset(), language=None, renderer=None):
    """Mint a memory episode through the selected deterministic adapter."""
    selected = renderer if renderer is not None else _safe_renderer(language)
    if selected is not None:
        try:
            return selected.render_episode(
                percepts, prev_standing=prev_standing,
                prev_described=prev_described)
        except Exception:
            logger.exception("language renderer failed; using English wording")
    return _render_episode_english(
        percepts, prev_standing=prev_standing,
        prev_described=prev_described)


# --------------------------------------------------------------------------
# Observations -- projected from the IR, never regex-classified from prose
# --------------------------------------------------------------------------

_FIDELITY_AMBIGUITY = {"full": 0.15, "degraded": 0.5, "fragment": 0.7,
                       "trace": 0.8}

_MAX_OBSERVATION_ATOMS = 8

# What an observation says when it has nothing to say: the advisory axes'
# resting values, and the two identity fields that repeat what the payload
# structure already states. Measured over the stored corpus (1,692
# observations, turn id >= 1932): `intensity` sat at its 0.35 base in 99% of
# rows, `suddenness` at 0.1 in 99%, `fidelity` at "rendered" in 99%,
# `ambiguity` at 0.15 in 89%, `source_atom_id` read "current" in 100%, and
# `perceiver_id` matched the perceiver already named by `observation_id` in
# 100% -- six near-constant fields beside every percept, ~356 tokens of
# wrapper per payload against ~188 tokens of text. The axes are advisory
# context for the model's appraisal (docs/guides/PIPELINE.md: no deterministic code
# consumes the numbers), so a resting default carries no information and is
# OMITTED: absent means the default, the same convention the character
# payload uses everywhere else ("absent means cannot tell", never "none").
# The 1-11% of non-default values keep their full signal, and the ids and
# text -- the citation namespace `_ground_observation_citations` grounds
# against, and the content itself -- are never trimmed. Observations stored
# before this change carry the full shape and read identically.
#
# THAT MEASUREMENT IS OF A DERIVATION THAT NO LONGER RUNS, and one of the six
# rows no longer holds. It was taken against the prose-cue derivation
# `perception._observations_from_clean_views` (since deleted), which computed
# `0.35 + 0.2 * cue_hits` and therefore sat on the base whenever no cue
# matched. `observations_from_render` computes `0.35 + 0.4 * salience`, and
# the lowest salience any builder in this module assigns is 0.2
# (`environment_percept`), so intensity is >= 0.43 on every atom the composer
# can produce. The field the note above says is dropped 99% of the time is
# now dropped 0% of the time.
#
# The entry stays regardless, because `OBSERVATION_DEFAULTS` is also the
# EXPANSION table: rows stored under the old derivation omitted intensity,
# and removing the key would read those rows as having no intensity rather
# than the base. `suddenness`, `fidelity`, `ambiguity`, `source_atom_id` and
# `perceiver_id` still compact as measured.
OBSERVATION_DEFAULTS = {
    "source_atom_id": "current",
    "fidelity": "rendered",
    "intensity": 0.35,
    "suddenness": 0.1,
    "ambiguity": 0.15,
    "directed_at_self": False,
}


def compact_observation(obs):
    """Drop wrapper fields holding their resting default (OBSERVATION_DEFAULTS
    above); `perceiver_id` is dropped when it repeats the perceiver already
    named by `observation_id`. `observation_id`, `observed` and `channel`
    always survive."""
    if not isinstance(obs, dict):
        return obs
    oid = str(obs.get("observation_id") or "")
    out = {}
    for key, value in obs.items():
        if key == "perceiver_id" and oid.startswith(f"current:{value}:"):
            continue
        default = OBSERVATION_DEFAULTS.get(key)
        if default is not None:
            if isinstance(default, float):
                try:
                    if abs(float(value) - default) < 1e-9:
                        continue
                except (TypeError, ValueError):
                    pass
            elif value == default or value is default:
                continue
        out[key] = value
    return out


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
            # WHOSE DELIVERY, and WHETHER IT HAPPENED. Both are known from the
            # IR and both were being thrown away here. `order_key is None` is
            # standing state (the room, a pose, an appearance); an int is this
            # beat's arrival order. `force` marks an appearance the engine has
            # judged CHANGED this beat -- a garment gone, a mask down, a
            # disguise dropped -- which is an event wearing a standing
            # percept's shape.
            "speaker": str(p.source_label or ""),
            "kind": p.kind,
            # A re-encounter is deliberately NOT excluded here: meeting
            # someone again is standing state that became sayable again,
            # not something that happened, so it stays reference and the
            # narrator owes it nothing. Only an actual change promotes a
            # standing percept to an obligation -- and `beat`, set by the
            # renderer from this observer's own ledger, is what says one
            # changed. `force` still counts because it is what a stage
            # without a ledger (an opening view) has instead; the renderer
            # never marks a percept it suppressed, so a forced-but-identical
            # appearance is no longer in `spans` to be asked.
            "standing": p.order_key is None and not p.data.get("force")
            and not p.data.get("beat"),
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
    #
    # A DELIVERY BOUNDARY IS SUCH A BOUNDARY, and three more keys keep it.
    # Two speakers welded into one entry is the exact shape the merged-speaker
    # check exists to catch, and this function was MINTING it: measured over
    # the 248 stored beats whose perception step carries a composer ledger --
    # the ones the live projection wrote -- 46 entries across 39 beats (15.7%)
    # carried two or more speakers' lines, every one of them `hearing`, which
    # is this loop's signature rather than the cap's (a cap merge marks the
    # channel `mixed`). The quotes inside stayed whole; what lied was the
    # entry boundary, against a sheet that tells the narrator each numbered
    # entry is a separate delivery.
    #
    # SAME SPEAKER, CONSECUTIVE SPEECH NO LONGER MERGES HERE. It is an
    # honest description of the atom count and a dishonest one of the
    # DELIVERY count: the joined parts render as a single numbered entry
    # containing two complete attribution-plus-quote spans, the sheet tells
    # the narrator each numbered entry is one delivery, and the model obeys
    # by writing one -- dropping the second attribution and welding the
    # quotes. Measured, chat 95 turns 2, 6 and 11: three welds on the page in
    # sixteen turns, three of three with a merged entry as their direct
    # antecedent. A rule the model is asked to follow downstream ("never weld
    # two entries' quotes into one quoted span") cannot fire against a weld
    # made upstream of it -- there is only one entry left to compare.
    #
    # What that spends is the atom cap, which is why the cap below now picks
    # its victim by what the weld COSTS rather than by size alone. Measured
    # over the 4,108 stored observer-beats in the bench corpus: 668 carry a
    # same-mouth weld and refusing it newly overflows the cap on 345, of
    # which 333 hold no standing entry for the cap to spend instead. So on a
    # genuinely crowded beat the cap re-forms exactly this group, and on
    # every beat under the cap the boundary survives.
    #
    # OBLIGATION IS A BOUNDARY TOO. A standing atom folded into an event one
    # (or the reverse) makes wallpaper indistinguishable from what happened,
    # which is exactly the distinction `_render_observed_events` now files on.
    def _may_merge(last, atom):
        if last["channel"] != atom["channel"]:
            return False
        if (last["ambiguity"] >= 0.5) != (atom["ambiguity"] >= 0.5):
            return False
        if last["directed_at_self"] != atom["directed_at_self"]:
            return False
        if last["standing"] != atom["standing"]:
            return False
        if len(last["parts"]) >= 3:
            return False
        if last["kind"] == "speech" or atom["kind"] == "speech":
            # A spoken line is a delivery, and a delivery is a boundary this
            # projection may not spend before the cap forces it to.
            return False
        return True

    merged = []
    for atom in atoms:
        same_verdict = bool(merged) and _may_merge(merged[-1], atom)
        if same_verdict:
            last = merged[-1]
            last["parts"].append(atom["text"])
            last["intensity"] = max(last["intensity"], atom["intensity"])
            last["suddenness"] = max(last["suddenness"], atom["suddenness"])
            last["ambiguity"] = max(last["ambiguity"], atom["ambiguity"])
        else:
            merged.append({**atom, "parts": [atom["text"]]})
    # THE CAP IS A LAST RESORT, AND IT PRICES THE PAIR IT IS ABOUT TO WELD.
    # It used to take the shortest group wherever it sat and fold it into
    # whichever neighbour happened to be there, so a forced merge could weld
    # two speakers by accident after the loop above had deliberately refused
    # to. Now the boundaries are ranked, cheapest spent first: wallpaper into
    # wallpaper costs a boundary nobody is scored on; one mouth's consecutive
    # lines cost an attribution; folding standing state into what happened
    # costs the obligation boundary `_render_observed_events` files on; and
    # welding two mouths costs the one the merged-speaker fidelity check
    # hunts, so it goes last. With the same-mouth merge refused above this
    # ordering is what keeps 333 crowded beats (of 4,108 measured) from
    # trading a dropped attribution for a misattributed line.
    def _same_mouth(a, b):
        return bool(a["speaker"]) and a["speaker"] == b["speaker"]

    # ONE MOUTH'S TWO QUOTED LINES ARE DEARER THAN A SILENT ATOM. The ranks
    # below used to price a same-mouth speech weld (then rank 1) BELOW every
    # other event pair, so the cap reached for it first -- and a group holding
    # two complete attribution-plus-quote spans is exactly the antecedent the
    # loop above refuses to mint, for the measured reason it states: the sheet
    # tells the narrator each numbered entry is one delivery, the model obeys,
    # and the two quotes come out welded. Measured, chat 98 turn 29: nine
    # atoms against a cap of eight, the cap folded Picard's first two lines
    # into one entry, and the page carried them back to back with no
    # attribution or beat between them -- the worst dialogue sample in the run.
    #
    # Folding a SILENT atom into a spoken one cannot produce that shape: the
    # group still holds one quote, so there is nothing to weld. It costs the
    # channel (the entry degrades to `mixed`) and the attribution, which the
    # loop below already spends on it. So the order is: wallpaper into
    # wallpaper, then two silent events, then a silent event into a spoken
    # one, then one mouth's two deliveries, then the obligation boundary, and
    # last the two-mouth weld the fidelity check hunts.
    def _pair_cost(i):
        a, b = merged[i], merged[i + 1]
        both_speech = a["kind"] == "speech" and b["kind"] == "speech"
        if both_speech and not _same_mouth(a, b):
            rank = 5
        elif a["standing"] != b["standing"]:
            rank = 4
        elif both_speech:
            rank = 3
        elif a["standing"]:
            rank = 0
        elif a["kind"] == "speech" or b["kind"] == "speech":
            rank = 2
        else:
            rank = 1
        return (rank, len(" ".join(a["parts"] + b["parts"])))

    while len(merged) > _MAX_OBSERVATION_ATOMS:
        target = min(range(len(merged) - 1), key=_pair_cost)
        source = target + 1
        if merged[target]["channel"] != merged[source]["channel"]:
            merged[target]["channel"] = "mixed"
        if (merged[target]["kind"] != merged[source]["kind"]
                or not _same_mouth(merged[target], merged[source])):
            # No longer one mouth's delivery, and it must not be read as one
            # by a later pass of this same loop.
            merged[target]["kind"] = ""
            merged[target]["speaker"] = ""
        # Obligation wins the merge. The target is the earlier group, so a
        # standing entry sitting in front of an event used to make the whole
        # welded group skippable -- the direction this file's own comment
        # calls the unsafe one ("replay can never make something skippable
        # that was not already").
        merged[target]["standing"] = (
            merged[target]["standing"] and merged[source]["standing"])
        merged[target]["parts"].extend(merged[source]["parts"])
        merged[target]["ambiguity"] = max(
            merged[target]["ambiguity"], merged[source]["ambiguity"])
        merged[target]["directed_at_self"] = (
            merged[target]["directed_at_self"]
            or merged[source]["directed_at_self"])
        merged.pop(source)
    out = []
    for index, atom in enumerate(merged):
        out.append(compact_observation({
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
            # Absent on a stored row written before this field existed, which
            # reads back as False -- obligation. That is today's behaviour and
            # it fails in the safe direction: replay can never make something
            # skippable that was not already.
            "standing": atom["standing"],
        }))
    return out
