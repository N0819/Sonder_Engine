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
  noticed changes without invented occurrence times. An explicit look/examine intent
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
from collections.abc import Mapping
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
    _anchor_room_of,
    _is_body_entity,
    body_cell,
    body_visibility,
    contact_thing_label,
    effective_anchors,
    effective_station,
    entity_arc,
    entity_side,
    hear_level,
    spoken_to,
    hearing_reason,
    voice_carries,
    held_beam_falls_on,
    into_another_ear,
    movement_heard_at_ear,
    _sense_channel,
    sense_adjusted,
    proximity_rel,
    room_of,
    same_subject,
    sense_acuity_offset,
    sound_bearing,
    size_relation,
    visual_level_between,
)

from .common import (
    _appearance_as_prose,
    self_name_forms,
    name_occurrence_pattern,
    _base_from_third_person_s,
    _compose_residue_view,
    _identity_token_set,
    _inject_dialogue,
    _muffle_tokens,
    _muffled_fragment,
    _observable_predicate,
    _quote_body,
    _recognizes,
    _fix_you_agreement,
    _self_second_person,
    _unknown_actor_label,
    stranger_label_ladder,
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
    "communication", "cue", "demeanor",
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


def _t(key, **values):
    """One template from the ACTIVE story pack, English where the pack has
    no entry. For the text the composer builds BEFORE the language adapter
    sees it -- a pose referent, a spliced noun -- because that text is data
    the adapter renders verbatim, so an English article minted here reaches
    a Japanese page as "the 砂浜" (chat 122 on a copy, 2026-09-07)."""
    try:
        templates = _compositor("templates")
    except Exception:
        templates = _EN_TEMPLATES
    # `compositor_value` hands back a read-only mapping proxy, not a dict.
    template = templates.get(key) if isinstance(templates, Mapping) else None
    if template is None:
        template = _EN_TEMPLATES[key]
    return str(template).format(**values)


def _pack_words(name):
    """A determiner table from the ACTIVE pack, empty where it has none, so a
    language that takes no article leaves every branch a no-op in fact and
    not only in the docstring."""
    try:
        return frozenset(str(w).casefold() for w in (_compositor(name) or ()))
    except Exception:
        return frozenset()


def _lower_lead(text):
    """Sentence case off an authored phrase about to be spliced mid-sentence:
    the first letter is lowered when it is the ONLY capital in its word, so
    an acronym or a capitalised name inside the phrase keeps its case. A
    one-letter first word is that case too -- the article of "A woman's,
    past fifty" (a card's `embodiment.voice`, 2026-10-20) is lowered, where
    the test on the second character alone kept it, and the page read "The
    voice is A woman's"; an initial with its stop ("A. Smith") is not."""
    text = str(text or "").strip()
    if len(text) > 1 and text[0].isupper() and (
            text[1].islower()
            or (text[1] == " " and len(text) > 2 and text[2].islower())):
        return text[0].lower() + text[1:]
    return text


def _strip_sentence_ends(text):
    """Take the terminal stops off a phrase about to be spliced into a
    sentence -- the pack's stops, not the ASCII full stop alone. A Japanese
    presented appearance ends in 。 and was rendered inside its own label:
    "見知らぬごく普通の人間の若い女性。は手の届く距離にいる" (chat 122 on a
    copy, 2026-09-07)."""
    text = str(text or "").strip()
    try:
        ends = str(_ling("_SENTENCE_ENDS") or ".!?")
    except Exception:
        ends = ".!?"
    return text.rstrip(ends + ";:,、；：").rstrip()


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

    No `blocked_by` here: every builder in this module grades a level that
    came back from `visual_level_between`, which was handed the senses and
    has already spent what the place did (A87) -- the dark has lifted by the
    time the level arrives. The one reader that
    grades a ROOM-level `sight_level` and needs the cause is
    `agents.common._delivery_ok`, and it calls `sense_adjusted` directly.
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


def assign_stranger_labels(bodies):
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
        base, wider = stranger_label_ladder(
            name, appearance, aliases, role=role, head_noun=noun or None)
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


def _line_refs(entry):
    """Every handle a line names its addressee by: its `intended_target`
    (one, or a list) and its `targets`."""
    refs = entry.get("intended_target")
    refs = list(refs) if isinstance(refs, (list, tuple)) else [refs]
    refs.extend(entry.get("targets") or [])
    return [str(ref).strip() for ref in refs
            if ref is not None and not isinstance(ref, bool)
            and str(ref).strip()]


def line_addressed(entry, observer_name, observer_id=None):
    """Is this observer the body a line is spoken TO -- its
    `intended_target`, or one of its `targets` -- by name, or by the
    engine's own handle for them (`character:<id>`)? Typed data only, like
    every admission here; a caller that resolves identity against the scene
    (aliases, entity ids) passes its own answer as `addressed`.

    What the ear rung is decided by (`spatial_senses.EAR_VOLUME`), and it
    fails toward no: a line breathed into an ear goes to nobody this cannot
    show is that ear's owner.

    Three answers, not two (`spatial_senses.spoken_to`): None where the line
    names NOBODY -- its addressee field absent or left empty -- which is
    unknown, never "spoken to somebody else": no bystander rule caps it,
    and the ear rung still refuses it."""
    forms = {str(observer_name or "").strip().casefold()}
    if observer_id is not None and str(observer_id).strip():
        forms |= {str(observer_id).strip().casefold(),
                  f"character:{str(observer_id).strip()}".casefold()}
    forms.discard("")
    refs = _line_refs(entry)
    return spoken_to(any(ref.casefold() in forms for ref in refs), bool(refs))


def line_hear_level(entry, rel, observer_name, proximity=None,
                    senses=None, seen=False, *, addressed=None):
    """Audibility of one dialogue entry to an observer.

    A LINE BREATHED INTO ANOTHER BODY'S EAR decides first, and it decides
    `none` (`spatial_senses.into_another_ear`): no path carries the ear
    rung to anybody but its addressee -- not the air, not the live channel
    below, not the rescue of a line named across a barrier. `addressed` is
    whether this observer is the line's addressee; None reads the line's
    own targets (`line_addressed`).

    Ordinary spatial hearing (`hear_level`) decides next -- including the
    `proximity` downgrade. Pass only a MEASURED tier
    (`spatial.measured_proximity_rel`): "near" is mostly a default, and a
    default must not silence a conversation.

    Hearing only ever gets OVERRIDDEN in one direction -- a line it would
    DROP is rescued to 'full' when the line is a TRANSMISSION addressed to
    THIS observer (explicit medium:'comm', or a by-name spoken-volume
    exchange across a barrier). An enclosure is never shape-rescued: being
    named by a voice beyond the mass around you creates no channel through
    it. The comm path carries only the VOICE; the caller sets can_see
    separately.

    `seen`: the observer sees the speaker's face, which is worth several
    decibels where noise is what decides (`hear_level`).

    WHO THE LINE WAS SPOKEN TO is the hearing rule's question too: in a din
    a bystander beyond conversational reach catches pieces of a far table's
    talk, and the one it was said to follows it. A line that names nobody
    -- no addressee field, or one left empty, as 31% of recorded lines are
    -- is unknown (None): the ear rung refuses it to everyone, the din caps
    nothing (`spatial_senses.spoken_to`)."""
    if addressed is None and isinstance(entry, dict):
        addressed = line_addressed(entry, observer_name)
    if into_another_ear(entry.get("volume", "normal"), addressed,
                        entry.get("level_db")):
        return "none"
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
    _unimpaired = hear_level(rel, entry.get("volume", "normal"),
                             proximity=proximity,
                             level_db=entry.get("level_db"), seen=seen,
                             addressed=addressed)
    base = _sense_graded(_unimpaired, "hearing", senses)
    # AN IMPAIRED EAR IS NOT AN UNREACHABLE ONE. `full` is the top of the
    # hearing ladder, so a -1 acuity took every `full` to `fragment`
    # unconditionally: a hard-of-hearing body never made out a sentence
    # again, at any volume, at any distance, including one shouted into it
    # at arm's length -- and no speaker could do anything about it, which is
    # what makes it a defect rather than a disability. Measured (rush, PR5).
    #
    # So the shift yields where the world is already compensating for it, on
    # the two terms the world has: a MEASURED intimacy, or a raised voice.
    # Exactly the exception design note 18 makes for dim sight, and for the
    # same reason -- a grade is a description of the channel, and a channel
    # at its own ceiling is not describing an impairment any more. Every
    # other level still shifts, so the card is not being ignored.
    # ...but ONLY where the card is a shift. An ABSENT channel is a cut, not
    # a degree (`sense_acuity_offset` answers None for it), and no volume and
    # no distance compensates for an ear that is not there. Caught by this
    # function's own test on the first run, which is the whole argument for
    # writing the complement down.
    if base != "full" and _unimpaired == "full" \
            and sense_acuity_offset(senses, "hearing") is not None and (
            str(proximity or "") == "within_reach"
            or str(entry.get("volume", "normal")).lower() in ("loud", "shout")):
        base = "full"
    if base != "none":
        return base
    if not _addresses(entry.get("intended_target"), observer_name):
        return base
    if str(entry.get("medium") or "").lower() == "comm":
        return "full"
    if rel.get("enclosed_from_source") or rel.get("source_enclosed"):
        return base
    # ATTENTION DOES NOT BEAT AIR THAT IS WORKING. The shape floor exists
    # because a Director often omits `medium`, and a by-name line to a party
    # OUT OF EARSHOT is then still a transmission -- a combadge hail from a
    # planet surface, which nothing but a device could carry. That case is
    # earned and stays. What was never evidence for it is a party in the same
    # BUILDING: two independent runs measured the difference -- a shout three
    # rooms up a stone tower delivered verbatim on four beats (lighthouse,
    # PA4), and a line from two closed doors and a room away delivered
    # complete in a view whose two UNADDRESSED voices were correctly
    # fragments (the Cold Season Ball, PX6). Sound reached both places; being
    # named is not a second, better path through the same doors.
    #
    # The two are told apart by whether the AIR HAS AN ANSWER for this pair.
    # `stamp_sound_relation` stamps `air` where the two rooms are one,
    # neighbours, or joined by any chain of edges; a pair with no acoustic
    # relationship at all -- another world, a ship in orbit -- carries none.
    # Where the air has an answer, it is the answer. Where it has none, a
    # line that arrives by name arrives by a device.
    #
    # A scene with no geometry stamps nothing and is unchanged, which is the
    # same fail-open direction this rescue has always had.
    if rel.get("air"):
        return base
    if str(entry.get("volume", "normal")).lower() in ("normal", "loud", "shout"):
        # ...and it is not the one grade a sense card cannot dull. It ran
        # after `_sense_graded` and returned a bare "full", so one view could
        # carry a fragmented sentence into a poor ear at arm's reach beside a
        # verbatim shout from two rooms below (rush, PR5).
        return _sense_graded("full", "hearing", senses)
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

#: The two fields' closed vocabularies, as the composer knows them: a shape
#: row whose level is not one of these is dropped, so no other word can
#: reach a template. Light's is `spatial_light.LIGHT_LEVELS`; sound's is
#: `spatial_sound_field.NOISE_WORDS`, both spelled here rather than imported
#: because the composer reads no scene module.
LIGHT_SHAPE_LEVELS = ("bright", "lit", "dim", "dark")
SOUND_SHAPE_LEVELS = ("drowned", "din", "quiet")


def _clean_shape(shape, levels):
    """A field shape as the templates will read it, or None. Groups keep
    only levels in the closed set and non-empty descriptions; `sources`
    and `openings` are labels the observer already has; `self` is one of
    the levels or None. Nothing numeric survives -- there is nothing
    numeric to keep."""
    if not isinstance(shape, dict):
        return None
    groups = []
    for group in shape.get("groups") or ():
        if not isinstance(group, dict):
            continue
        level = str(group.get("level") or "")
        items = [str(i).strip() for i in (group.get("items") or ())
                 if str(i or "").strip()]
        if level in levels and items:
            groups.append({"level": level, "items": items})
    sources = [str(s).strip() for s in (shape.get("sources") or ())
               if str(s or "").strip()]
    openings = [str(o).strip() for o in (shape.get("openings") or ())
                if str(o or "").strip()]
    # What a coned source in view is pointed at (D5). Descriptions of
    # anchors the field has already graded, in the order the field put them
    # -- nearest the beam first -- so ordering is data and not a rendering
    # choice. Empty for a field with no aimed source, and for `sound_shape`,
    # which has no cone at all.
    aimed = [str(a).strip() for a in (shape.get("aimed") or ())
             if str(a or "").strip()]
    self_word = shape.get("self")
    self_word = self_word if self_word in levels else None
    # AN EVEN ROOM'S ONE WORD (`spatial_sound_field.sound_fill`, § 17): a
    # steady sound filling the room at one level, named by its sources.
    even = shape.get("even")
    even = even if even in levels and (sources or openings) else None
    if not groups and self_word is None and even is None:
        return None
    return {"groups": groups, "sources": sources, "openings": openings,
            "self": self_word,
            # No beam, no key (D5): every reader takes absence as "nothing aimed".
            **({"aimed": aimed} if aimed else {}),
            # No even word, no key: an uneven shape hashes as it always did.
            **({"even": even} if even else {})}


def _shape_signature(shape):
    if not shape:
        return ""
    aimed = [a for a in (shape.get("aimed") or ()) if a]
    return "|".join(
        ["%s=%s" % (g["level"], ",".join(g["items"])) for g in shape["groups"]]
        + ["from=" + ",".join(shape["sources"] + shape["openings"]),
           "self=%s" % (shape["self"] or "")]
        # SWINGING THE BEAM IS NEWS. The signature is the dedupe key of both
        # the `environment` percept and the `soundscape` percept: leave the
        # aim out of it and a lamp moved from one thing to another leaves
        # the room `unchanged`, so the sentence naming the new thing is
        # suppressed as furniture (D5).
        #
        # APPENDED, AND ONLY WHEN THERE IS A BEAM. An `aimed=` segment
        # emitted unconditionally rewrites the stored key of every shape
        # that never had a beam -- measured on a beam-less sound shape,
        # `din=a generator|from=a generator|self=din` became
        # `din=a generator|from=a generator|aimed=|self=din` -- so every
        # room description and every soundscape in every live chat would
        # re-announce itself as news on the first beat after this landed.
        # A shape with no beam hashes byte for byte to what it hashed
        # before.
        + (["aimed=" + ",".join(aimed)] if aimed else [])
        # ...and the even room's word the same way (§ 17): appended only
        # when there is one, so every uneven shape keeps its stored key, and
        # a room that fills up to one word or falls to another is `changed`.
        + (["even=" + str(shape["even"])] if shape.get("even") else []))


def environment_percept(room_id, room_name, room_notes="", light="",
                        features=None, openings=None, light_shape=None):
    """The room as standing state -- or None when the observer has no
    resolvable room. A mind in unloaded space perceives NOTHING here; the
    old path fabricated "You are in an unspecified area." for it, which
    became 812 identical memory rows (97.3% collision). No room, no
    percept, no view sentence, no episode.

    `light_shape` is where the light FALLS, for a room the light field
    finds uneven (`world.spatial_light_field.light_shape`): visible anchors
    grouped by the four light words, the sources or openings the light comes
    from, and the observer's own standing. Absent -- an even room, no
    geometry, no station -- the percept and its sentence are byte-identical
    to what they always were. Present, the renderer says where the light
    falls INSTEAD of the flat `light_dim`/`light_dark` sentence, which spoke
    for the whole room.

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
    shape = _clean_shape(light_shape, LIGHT_SHAPE_LEVELS)
    if shape:
        data["light_shape"] = shape
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
            + ((opening_sig,) if ways else ())
            + ((_shape_signature(shape),) if shape else ())),
    )


def soundscape_percept(shape, room_id):
    """Where the sound is, as one standing HEARING percept -- or None when
    the sound field found the room even, or has nothing to say
    (`world.spatial_sound_field.sound_shape`). An `ambient` kind, because
    that is what it is: a standing feature of the room and not a body, an
    event or a sensation on this body. The dedupe key carries the shape, so
    a generator that starts or a door that opens is a room that CHANGED for
    this observer and an unchanged din is furniture."""
    shape = _clean_shape(shape, SOUND_SHAPE_LEVELS)
    if not shape or not room_id:
        return None
    return Percept(
        kind="ambient", channel="hearing",
        data={"soundscape": shape},
        salience=0.3,
        dedupe_key=standing_key("soundscape", (room_id,),
                                (_shape_signature(shape),)),
    )


def sound_ceased_percept(room_id, *, still_sounding=False):
    """The room's sound STOPPING, as one standing hearing percept.

    SILENCE WHERE THERE WAS SOUND (review 2026-09-07 D3). A room the sound
    field grades unevenly composes a `soundscape_percept`; the beat its one
    source stops, the field goes even and the percept is simply not built --
    so the observer's ledger holds a key nothing renews and nothing anywhere
    says the humming stopped. Measured in the descent run: the PLAYER wrote
    "nothing hummed" themselves, because the page never did. A multi-source
    room is already covered -- one source of several stopping moves the
    shape, which moves the content hash, which is `changed` -- and this is
    the single-source case that hash cannot see, because the key it needs to
    compare against is the one that vanished.

    THE SAME SUBJECT AS THE SOUND IT ENDS, deliberately: `standing_key`
    hashes subject and content apart, so this key threads the room's sound
    ledger rather than opening a second one. The sound coming back is
    `changed` against this, the silence continuing is `unchanged` (said
    once, not every beat), and an observer who was never delivered the sound
    gets `first` -- which `unheard_ceasing` drops, because a silence is only
    news to an ear that had the noise.

    `still_sounding` is the room that went quiet with its source still going
    (`spatial_sound_field.room_still_sounding`): the noise DIED DOWN, which is
    not the noise stopping -- a TARDIS rotor whose din "gentled into a hum"
    in flight was told to the page as a stop (chat 157 turn 4482). Same
    subject, its own content, so the hum stopping later is news again.
    """
    if not room_id:
        return None
    data = {"ceased": True}
    if still_sounding:
        data["subsided"] = True
    return Percept(
        kind="ambient", channel="hearing",
        data=data,
        salience=0.4,
        dedupe_key=standing_key("soundscape", (room_id,),
                                ("subsided" if still_sounding else "ceased",)),
    )


def _shape_clauses(shape, prefix, levels):
    return [_en(prefix + level,
                items=_join_clauses([_noun_phrase(i) for i in group["items"]]))
            for group in shape["groups"] for level in (group["level"],)
            if level in levels]


def aim_worth_naming(shape):
    """The beam's anchors, when saying them adds something -- else [].

    WHERE THE BEAM LANDS (D5). A sentence separate from the room's grading,
    because it answers a different question: the grading says how much light
    is where, and this says what the light is being POINTED at -- the thing
    a reader looks at first and the page never named (chat 117 beats 59-62,
    five beats of an aimed hand lamp).

    It speaks only where it names a set THE GRADING DID NOT ALREADY NAME BY
    ITSELF. Two ways it fails to: a beam covering every anchor in view has
    singled nothing out, and a beam whose anchors are exactly the brightest
    group is the sentence before it in other words ("The light from the hand
    lamp falls on a stack of crates. The beam is on a stack of crates.").
    Where a second source does the grading -- an overhead strip lighting the
    room while the hand lamp picks one thing out of it -- the two sets
    differ and the aim is the news of the beat.

    Here rather than in either renderer because it is a decision about the
    aim's information content, not about a language: two copies of it would
    be two answers to "is this worth a sentence", free to drift, and every
    pack's adapter is a second renderer by construction.
    """
    shape = _clean_shape(shape, LIGHT_SHAPE_LEVELS)
    if not shape:
        return []
    aimed = shape.get("aimed") or []
    graded = {item for group in shape["groups"] for item in group["items"]}
    brightest = set(shape["groups"][0]["items"]) if shape["groups"] else set()
    if not aimed or len(set(aimed)) >= len(graded) or set(aimed) == brightest:
        return []
    return list(aimed)


def render_light_shape(shape):
    """The light's shape as one or two English sentences, from templates over
    the closed set alone: the origin (the sources in view and the openings
    the light comes through, or 'the light' when neither is in view), the
    visible anchors grouped bright to dark, what a coned source in view is
    pointed at, and where the observer stands. No number, cell or sector
    reaches the page -- the shape carries none."""
    shape = _clean_shape(shape, LIGHT_SHAPE_LEVELS)
    if not shape:
        return ""
    parts = []
    clauses = _shape_clauses(shape, "light_at_", LIGHT_SHAPE_LEVELS)
    if clauses:
        # The sources are entity NAMES and the openings authored descs;
        # neither carries the pack's determiner ("The light from brass hand
        # lamp and the opening..." -- F52's last unfixed line, run
        # 2026-09-05C `solitude` turn 5).
        froms = [_noun_phrase(f) for f in shape["sources"] + shape["openings"]]
        origin = (_en("light_origin", items=_join_clauses(froms)) if froms
                  else _en("light_origin_none"))
        parts.append(_cap(_en("light_shape", origin=origin,
                              clauses=_join_clauses(clauses))))
    # WHERE THE BEAM LANDS (D5). A separate sentence from the room's
    # grading, because it answers a different question: the grading says how
    # much light is where, and this says what the light is being POINTED at
    # -- the thing a reader looks at first and the page never named (chat
    # 117 beats 59-62, five beats of an aimed hand lamp).
    #
    aimed = aim_worth_naming(shape)
    if aimed:
        parts.append(_cap(_en("light_aimed", items=_join_clauses(
            [_noun_phrase(a) for a in aimed]))))
    if shape["self"]:
        parts.append(_en("light_self_" + shape["self"]))
    return " ".join(parts)


def render_sound_shape(shape):
    """The sound's shape, the same way: the origin (entities heard in this
    room, and 'beyond <opening>' for one heard through a doorway), the
    visible anchors grouped loud to quiet, and where the observer stands."""
    shape = _clean_shape(shape, SOUND_SHAPE_LEVELS)
    if not shape:
        return ""
    parts = []
    froms = [_noun_phrase(s) for s in shape["sources"]] + [
        _en("sound_beyond_opening", opening=_noun_phrase(o))
        for o in shape["openings"]]
    origin = (_en("sound_origin", items=_join_clauses(froms)) if froms
              else _en("sound_origin_none"))
    if shape.get("even"):
        # A STEADY SOUND FILLING THE ROOM AT ONE WORD (§ 17): there is no
        # "where" to grade, so the sentence says what is heard, all through
        # the room, at the one level the room carries.
        return _cap(_en("sound_even_" + shape["even"], origin=origin))
    clauses = _shape_clauses(shape, "sound_at_", SOUND_SHAPE_LEVELS)
    if clauses:
        parts.append(_cap(_en("sound_shape", origin=origin,
                              clauses=_join_clauses(clauses))))
    if shape["self"]:
        parts.append(_en("sound_self_" + shape["self"]))
    return " ".join(parts)


def field_shape_sentence(kind, shape, *, language=None):
    """One field shape (`light` or `sound`) as the story language's
    sentence -- the seam the Director's sight digest reads, so the Director
    is handed exactly the sentence the observer's view carries and nothing
    the view does not. The pack's adapter renders it when it can; English
    otherwise, as `render_view` falls back."""
    if not shape:
        return ""
    selected = _safe_renderer(language)
    if selected is not None and hasattr(selected, "field_shape_sentence"):
        try:
            return str(selected.field_shape_sentence(kind, shape) or "")
        except Exception:
            logger.exception("language renderer failed; using English wording")
    return render_light_shape(shape) if kind == "light" else render_sound_shape(shape)


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

    A POSE IS NOT EVIDENCE OF A BODY, though, and that signal alone was
    minting people. `scene.poses` is keyed by whatever the Director gave a
    posture to, and a Director legitimately gives one to a thing: a survey
    staff planted upright, a canteen slung, a notebook pocketed. Each of
    those became "someone" in the composed view of a story whose cast was one
    woman alone in a dead town -- fourteen of twenty beats, three of them in
    the same paragraph -- while the mallet, the one possession that never
    received a posture, rendered correctly by its own name in the same view.
    So the scene is asked to vouch for a THING first, exactly as
    `contact_sensation`'s docstring tells a caller holding an identity floor
    to, and as `narration._partner_label` already does. That answer is
    affirmative in both directions and outranks the person-shaped default;
    silence leaves the default standing, which is what keeps a body the
    observer cannot place from being named.
    """
    for body in co_present or []:
        if same_subject(scene, text, str(body.get("name") or "")):
            return True
    if contact_thing_label(scene, text):
        return False
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


#: An engine identifier as it appears inside authored prose: a run of word
#: characters carrying an underscore. English prose has none, so the shape is
#: decidable rather than guessed -- this is a closed vocabulary the ENGINE
#: owns (room uids, entity ids, anchor ids all mint this way), not an attempt
#: to anticipate how a sentence will be phrased.
_ID_SHAPED = re.compile(r"(?<![\w])[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+(?![\w])")


def _display_for_id(scene, token):
    """The story's own name for an engine id, or "" when it names nothing.

    Rooms, then entities, then anchors -- the three ledgers whose keys are
    minted with underscores and therefore the three that can leak one.
    """
    rooms = (scene or {}).get("rooms") or {}
    room = rooms.get(token)
    if isinstance(room, dict) and str(room.get("name") or "").strip():
        return str(room["name"]).strip()
    named = str((_entity_named(scene, token) or {}).get("name") or "").strip()
    if named:
        return named
    for room in rooms.values():
        anchors = room.get("anchors") if isinstance(room, dict) else None
        if isinstance(anchors, dict) and isinstance(anchors.get(token), dict):
            desc = str(anchors[token].get("desc") or "").strip()
            if desc:
                return desc
    return ""


def _no_engine_ids(scene, text):
    """Authored prose with every engine identifier taken out of it.

    THE CLASS: an id is a handle the engine holds, never a word of the story.
    `_pose_referent` already refuses one where a REFERENT is resolved (step
    5), and the same string walked straight onto the page through the free
    prose beside it -- run 2026-09-05C `solitude` turn 1 (PS2): "poised at
    the brow with one foot on the top step down toward upper_terrace_rim,
    survey staff planted in a rut."

    An id that names a record renders as that record's own name, which
    discloses nothing the id did not already carry -- the reader could read
    `upper_terrace_rim` perfectly well.

    An id that names NOTHING takes its whole clause with it, not just the
    token: a clause reaching for a record the scene does not hold says
    nothing, and excising the word alone leaves the reach behind it ("one
    foot on the step down toward."). The unit is the clause the author's own
    punctuation marks, so no list of prepositions has to be right -- and
    where that is the only clause the field simply does not become a
    percept, which is the subtraction the rest of this module makes
    everywhere else.
    """
    text = str(text or "").strip()
    if not text or "_" not in text:
        return text

    def swap(match):
        # \x00 marks a token that named nothing; the clause holding it goes.
        return _display_for_id(scene, match.group(0)) or "\x00"
    parts = re.split(r"\s*([,;])\s*", text)
    kept = []                       # [(clause, the separator that followed)]
    for index in range(0, len(parts), 2):
        clause = _ID_SHAPED.sub(swap, parts[index]).strip()
        if not clause or "\x00" in clause:
            continue
        kept.append((clause,
                     parts[index + 1] if index + 1 < len(parts) else ""))
    out = "".join(
        clause + ((separator or ",") + " " if position < len(kept) - 1 else "")
        for position, (clause, separator) in enumerate(kept))
    return " ".join(out.split())


def _spliced_fragment(text):
    """Authored text made fit to follow a verb, without deciding its shape.

    `_noun_phrase` is for a NOUN phrase and supplies an article where none
    stands, which is right for "sand shelf" and wrong for an adjectival
    demeanor ("calm, attentive" became "the calm, attentive"). This does
    the two subtractions that hold for any spliced fragment and nothing
    more: the terminal stop goes, and a leading article written in sentence
    case is lowercased, so "A wet, nervous young man on a bench." follows
    "seems" as "a wet, nervous young man on a bench".
    """
    text = " ".join(str(text or "").split())
    while text and text[-1] in ".!?":
        text = text[:-1].rstrip()
    if not text:
        return ""
    first, _, rest = text.partition(" ")
    if first.casefold() in _pack_words("pose_bare_determiners") \
            and first[:1].isupper():
        text = first.casefold() + (" " + rest if rest else "")
    return text


def _bare_words(text):
    """`text` folded for comparing two names of one thing: its leading
    article off, its case and spacing ignored."""
    words = str(text or "").split()
    articles = {str(a).casefold() for a in _compositor("articles")}
    if words and words[0].casefold() in articles:
        words = words[1:]
    return " ".join(words).casefold()


def _noun_phrase(text):
    """One authored description, made fit to SPLICE into a sentence.

    THE CLASS. Anchor descriptions, edge names and light-source labels are
    authored free text and arrive in three shapes at once: a bare noun
    ("cistern intake passage"), a phrase carrying its own determiner ("the
    middle shelf"), and a full capitalised SENTENCE ("Salt-rimed limestone
    kerbstones dividing the crystallisation pans."). The composer splices all
    three into the middle of ITS OWN sentences -- a feature list, a way out,
    where the light falls -- and only the second survives that intact.

    Measured, run 2026-09-05C `solitude` (PS9). Turn 4: "You can see
    Salt-rimed limestone kerbstones dividing the rectangular crystallisation
    pans. within arm's reach, The open stone lip of the middle shelf ...
    across the room." Turn 5: "...thins to half-light at The low
    cut-limestone arch ... and The massive limestone revetment wall at the
    far northeast end of the dry basin.." -- two full stops. Turn 20: "There
    is broad salt-crusted stone steps."

    Three subtractions, each decidable from the pack's own tables and none of
    them guessing at English:

      * a TERMINAL STOP goes. A phrase inside a list is not a sentence, and
        the stop that belongs is the one the enclosing template supplies.
      * a LEADING ARTICLE is lowercased. The pack names its own articles, so
        a capital on one of them is sentence case and can never be a name.
        Nothing else is lowered: "Salt-rimed" may be a proper name and this
        layer has no way to know, so it keeps its capital and its meaning.
      * a phrase carrying NO determiner takes the pack's, exactly as
        `_pose_referent` gives one to a bare noun. This is F52's unfixed last
        line ("from hand torch"), and it was live in three sentence families
        at once.

    English wording, like the rest of the reference renderer: a pack with no
    articles and no determiners (`ja`) leaves every branch a no-op.
    """
    text = _strip_sentence_ends(" ".join(str(text or "").split()))
    if not text:
        return ""
    words = text.split()
    first = words[0].casefold().strip(",.;:")
    if first in _pack_words("articles"):
        words[0] = words[0][:1].lower() + words[0][1:]
        return " ".join(words)
    # A support is authored free-text and often arrives with its own
    # preposition already on it ("on the sill"); `_render_pose` detects that
    # and declines to add a second one. Prefixing a determiner here would
    # slip underneath that check and produce "on the on the sill".
    if (words[0][:1].isupper()
            or first in _pack_words("pose_bare_determiners")
            or first in _pack_words("pose_prepositions")):
        return " ".join(words)
    return _t("pose_entity", name=" ".join(words))


def _sound_bearing_phrase(scene, observer, source) -> str:
    """Where a heard movement came from, in the observer's own frame, or "".

    `spatial.sound_bearing` answers with the egocentric sector and never
    guesses; its own contract is that the record carries no room id and no
    room name, so a bearing discloses nothing a body's ears did not.
    """
    try:
        rec = sound_bearing(scene, observer, source)
    except Exception:
        return ""
    if not isinstance(rec, dict):
        return ""
    return str(rec.get("phrase") or rec.get("sector") or "").strip()


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
      5. a room's own FIXTURE -> the noun its anchor id was minted from,
         through the same splice as a bare noun ("the access door"). A
         station, a pose and a contact all name fixtures by anchor id, and
         the id is the Director's own noun with underscores in it; the desc
         beside it is a whole authored sentence and reads wrong as a
         possessive ("You feel A heavy steel door seated in a reinforced
         frame's lever handle"). Resolved through `_anchor_room_of`, the
         one resolver the contact ledger already trusts for the question
         "which room is this fixture in". Measured on the descent copy
         (chat 117, beats 115-117): "You feel something's steel plate
         against your right palm", "something's lever handle" -- three beats
         of a player touching a door the room declared, delivered as an
         unnameable thing because step 6 below dropped the id first.
      6. an id-shaped token matching no record -> DROPPED. `anchor_device`
         (the entity's id is `scranton_anchor`) names nothing, and putting it
         on the page shows the reader engine plumbing.
      7. anything else -> the bare noun as written. It matches no record in
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
            return _t("pose_part_self", part=part)
        return _t("pose_part_other", label=whose, part=part)
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
        # An entity may be NAMED with its determiner -- "The TARDIS", "the
        # Nostromo" -- and the pack's template supplies one of its own, so
        # the page read "facing the The TARDIS" (chat 114 on a copy,
        # 2026-09-05, turn 2). The same determiner list the bare-noun path
        # below consults decides it: a name that already opens with one is
        # rendered as it is written.
        first = named.split()[0].casefold().strip(",.")
        if first in _pack_words("pose_bare_determiners"):
            return named
        return _t("pose_entity", name=named)
    _fixture_room = _anchor_room_of(scene, text, prefer=room_of(scene, observer_name))
    if _fixture_room:
        # AN EDGE'S DOORWAY IS NOT A MINTED NOUN. Its id is `door:<room id>`
        # (`spatial_geometry.door_anchor_id`), and splicing it rendered
        # "against the door:mill race" into seven views and five memories of
        # one run (playerless Aldermill round 4, 2026-09-23). The implicit
        # anchor carries its own description -- the edge's name, or what the
        # boundary looks like -- and that is what the page says.
        if text.casefold().startswith("door:"):
            record = (effective_anchors(scene, _fixture_room) or {}).get(text)
            desc = str((record or {}).get("desc") or "").strip() \
                if isinstance(record, dict) else ""
            return desc or None
        return _noun_phrase(text.replace("_", " "))
    if "_" in text and not text.strip().count(" "):
        return None
    # A bare noun the Director wrote. It still reads better with the article
    # the pack supplies -- "at desk" is the awkwardness this whole repair was
    # reported for -- but only where it does not already carry a determiner
    # of its own ("the far wall", "her shoulder") and is not a proper name,
    # which a capital marks and which "the Marcus" would ruin. The determiner
    # list is language DATA and lives in the compositor card, empty for a
    # language that takes no article at all. One rule, shared with every
    # other place an authored description is spliced into a sentence.
    return _noun_phrase(text)


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


def _pose_owner_second_person(text, pronouns, other_forms=(), *,
                              person="second"):
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

    ``person="first"`` is the same rewrite into the owner's OWN first person,
    for the episode (`_said_as_mine`): the third person still says which role
    each pronoun had -- "she" the subject, "her" the object or the possessive
    -- and English's second person no longer does, so "as she turns her
    attention" is "as I turn my attention" here, where the swap of "as you
    turn your attention" could only guess (chat 152 turn 14 filed "as me
    turn my attention").
    """
    first = person == "first"
    text = str(text or "")
    if not text or not isinstance(pronouns, dict):
        return text
    subject = str(pronouns.get("subject") or "").strip()
    obj = str(pronouns.get("object") or "").strip()
    possessive = str(pronouns.get("possessive") or "").strip()
    if not any((subject, obj, possessive)):
        return text

    # A NAME'S OCCURRENCE INCLUDES THE TITLE THAT LEADS IT, here as well: the
    # cutoff marks where another body's name begins, and "Lord Edmund" begins
    # at "Lord". Cutting one word later left the title inside the span being
    # rewritten for somebody else.
    other_patterns = []
    for form in sorted({str(f or "").strip() for f in other_forms if str(f or "").strip()},
                       key=len, reverse=True):
        other_patterns.append(name_occurrence_pattern(form, flags=re.I))

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
                replacement = "myself" if first else "yourself"
            elif ((low == possessive.casefold()
                   and low != obj.casefold()) or
                  (low == possessive.casefold() == obj.casefold()
                   and _reads_as_possessive(prefix[match.end():]))):
                replacement = "my" if first else "your"
            elif not first:
                replacement = "you"
            elif low == subject.casefold() and (
                    low != obj.casefold()
                    or _reads_as_subject(prefix[match.end():])):
                # The subject's own case -- or, for a pronoun spelled alike
                # in both ("it"), the verb that agrees with it.
                return "I"
            else:
                replacement = "me"
            return replacement.capitalize() if word[:1].isupper() else replacement

        rewritten = pronoun_re.sub(replace, prefix)
        return (_fix_i_agreement(rewritten) if first
                else _fix_you_agreement(rewritten)) + suffix

    quoted = linguistic("agents.common", "_QUOTED_SPAN_RE").split(text)
    for index in range(0, len(quoted), 2):
        pieces = re.split(r"([,;—])", quoted[index])
        for piece_index in range(0, len(pieces), 2):
            pieces[piece_index] = rewrite_fragment(pieces[piece_index])
        quoted[index] = "".join(pieces)
    return "".join(quoted)


def _action_target_second_person(text, target_forms, target_pronouns,
                                 other_forms=(), *, owner="your"):
    """Repair target-owned body pronouns after an explicit target name.

    `owner` is the word the owned body part takes: the observer's "your" in
    the view, its own "my" in the episode's first person (`act_percept`).

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

    # The explicit form of this observer that licenses the repair is a whole
    # NAME occurrence, title and article included -- "facing Lord Edmund
    # Harrowgate" names him once, at "Lord", not at "Edmund" with a stray
    # honorific in front (manor run 2026-09-05, PC8).
    target_re = name_occurrence_pattern(forms, flags=re.I)
    other_patterns = [
        name_occurrence_pattern(form, flags=re.I)
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
            suffix = owned_body_re.sub(owner, owned) + remainder
            sentences[sentence_index] = prefix + suffix
        quoted[index] = "".join(sentences)
    return "".join(quoted)


# --------------------------------------------------------------------------
# The first person of an authored line, where the rewrite knows the role
# --------------------------------------------------------------------------

def _reads_as_subject(tail) -> bool:
    """Does the word after a name or pronoun agree with it as its SUBJECT?

    The same judgment `common._fix_you_agreement` acts on when it re-inflects
    the verb after a "you" that replaced a third-person subject: the next
    word is a third-person-singular form -- an auxiliary in the pack's
    agreement table, or a regular present verb's -s. A name followed by
    anything else (a noun phrase, a preposition, the end) is not the subject
    of that word."""
    match = re.match(r"\s+([A-Za-z][\w'’-]*)", str(tail or ""))
    if not match:
        return False
    word = match.group(1)
    return (word.casefold() in linguistic("agents.common", "_YOU_AGREEMENT")
            or _base_from_third_person_s(word) is not None)


def _fix_i_agreement(text):
    """Re-inflect the verb after an "I" that replaced a third-person subject
    -- the first-person twin of `common._fix_you_agreement`, and read from
    it rather than from a table of its own: the second person's form of the
    verb ("is" -> "are"), turned by the swap's own be row ("you are" -> "I
    am"). "I is", "I isn't" and "I turns" are never English, so this is as
    safe over prose that already held an "I" as its twin is."""
    def _sub(m):
        i, gap, word = m.group(1), m.group(2), m.group(3)
        second = linguistic(
            "agents.common", "_YOU_AGREEMENT").get(word.casefold())
        if second is None:
            base = _base_from_third_person_s(word)
            if base is None:
                return m.group(0)
            fixed = base
        else:
            turned = _first_person("you " + second)
            fixed = turned.split(" ", 1)[1] if " " in turned else second
        if word[:1].isupper():
            fixed = fixed[:1].upper() + fixed[1:]
        return f"{i}{gap}{fixed}"

    return re.sub(r"(?<![\w'’])(I)(\s+)([A-Za-z’']+)", _sub,
                  str(text or ""))


def _self_first_person(text, forms):
    """`common._self_second_person` into the perceiver's OWN first person,
    for the episode: a possessive name is "my", a name its next word agrees
    with as subject is "I" (the verb re-inflected for it), any other name is
    "me" -- the judgment the second-person rewrite makes when it re-inflects
    the verb after its "you", made here while the name still says which.

    Measured: "turns from the crag toward the tie-up where Pell stands" was
    rewritten "where you stand" for Pell and remembered "where me stand"
    (the lighthouse probe, 2026-10-20, chat 2 row 37)."""
    text = str(text or "")
    if not text:
        return text
    patterns = []
    for form in sorted({str(f or "").strip() for f in (forms or [])
                        if str(f or "").strip()}, key=len, reverse=True):
        flags = 0 if form.casefold() in linguistic(
            "agents.common", "_COMMON_WORD_NAMES") else re.I
        patterns.append(name_occurrence_pattern(form, flags=flags))
    if not patterns:
        return text

    def _sub(m):
        before = m.string[:m.start()].rstrip()
        opens = not before or before[-1] in ".!?\n"
        if m.group(1):
            return "My" if opens else "my"
        # A name between two verbs is the first one's object: English puts
        # the object straight after its verb. Without this, "hands Pell
        # letters" -- which the view's own agreement repair already reads as
        # "hands you letter" -- came back "hands I letter".
        prior = re.search(r"([A-Za-z][\w'’-]*)$", before)
        after_a_verb = bool(prior) and (
            prior.group(1).casefold() in linguistic(
                "agents.common", "_YOU_AGREEMENT")
            or _base_from_third_person_s(prior.group(1)) is not None)
        if not after_a_verb and _reads_as_subject(m.string[m.end():]):
            return "I"
        return "Me" if opens else "me"

    segments = linguistic("agents.common", "_QUOTED_SPAN_RE").split(text)
    for i in range(0, len(segments), 2):
        before = segments[i]
        after = before
        for pattern in patterns:
            after = pattern.sub(_sub, after)
        segments[i] = _fix_i_agreement(after) if after != before else before
    return "".join(segments)


#: One word of the person -- a pronoun of the first or the second person,
#: with its contracted auxiliary and the be form that agrees with it -- for
#: `_same_but_for_person`, which compares two renderings of one line with
#: the person taken out.
_PERSON_WORDS_RE = re.compile(
    r"(?<![\w'’])(?:I|me|my|mine|myself|you|your|yours|yourself)"
    r"(?:['’](?:m|re|ve|ll|d))?"
    r"(?:\s+(?:am|are|was|were)(?:n['’]t)?(?:\s+not)?)?"
    r"(?![\w'’])", re.I)


def _same_but_for_person(mine, view):
    """Do two renderings of one line say the same thing, the person aside?

    THE EPISODE NEVER OUTRUNS THE VIEW (rule 03 § 5.2): a first person
    carried beside a view's text is that text in another person or nothing.
    Quoted spans must match exactly; outside them every word of the person
    is set aside and the rest must match."""
    def _flat(text):
        segments = linguistic(
            "agents.common", "_QUOTED_SPAN_RE").split(str(text or ""))
        for i in range(0, len(segments), 2):
            segments[i] = _PERSON_WORDS_RE.sub("\x00", segments[i])
        return " ".join("".join(segments).split())
    return bool(str(mine or "").strip()) and _flat(mine) == _flat(view)


def _said_as_mine(data, field):
    """A percept's text `field` in the episode's first person.

    The rewrite that put the observer's own name or pronouns into the
    second person also wrote them into the first (`<field>_mine`), where the
    third person still said which role each had; that rendering is kept when
    it says what the view said, person aside, and the swap turns whatever
    the rewrite did not write. Otherwise the swap reads the view's text."""
    data = data or {}
    text = str(data.get(field) or "").strip()
    mine = str(data.get(field + "_mine") or "").strip()
    if mine and _same_but_for_person(mine, text):
        return _first_person(mine)
    return _first_person(text)


def _mine_if_it_matters(mine, view):
    """The first-person rendering worth carrying beside `view`: only one that
    passes `_same_but_for_person` and differs from what the swap would make
    of the view -- every other line is the swap's, and carries nothing."""
    mine, view = str(mine or "").strip(), str(view or "").strip()
    if not mine or mine == view or not _same_but_for_person(mine, view):
        return ""
    return mine if _first_person(mine) != _first_person(view) else ""


# --------------------------------------------------------------------------
# A mind's own act, in its own first person, as its attempt
# --------------------------------------------------------------------------

#: The third person's personal pronouns, one set to each subject -- the
#: closed paradigm, a schema rather than a guess at phrasing. `it` is not
#: here: in an act it is the thing handled ("tucks it"), and a doer who is
#: an "it" is not turned (`own_attempt`).
_THIRD_PERSON_SETS = (
    frozenset(("he", "him", "his", "himself")),
    frozenset(("she", "her", "hers", "herself")),
    frozenset(("they", "them", "their", "theirs", "themselves")),
)

#: Every personal pronoun that stands as a verb's object or as its object's
#: owner, in each person -- the same paradigm, read from the verb's side.
_OBJECT_PRONOUNS = frozenset((
    "me", "my", "myself", "you", "your", "yourself", "him", "his", "himself",
    "her", "hers", "herself", "it", "its", "itself", "us", "our", "ourselves",
    "them", "their", "themselves"))

#: The words that join one verb phrase of the doer's to the next where the
#: pack's coordinators (`referring.coordinator`: "and", "or") do not: the
#: sequencer and the contrasting conjunctions -- a closed grammatical class,
#: as the pronouns are. Every other breath word the pack holds
#: (`_BREATH_CONJUNCTIONS`) subordinates: it opens a clause of its own subject.
_SEQUENCERS = frozenset(("then", "but", "yet"))

_WORD_TOKEN = re.compile(r"[A-Za-z][A-Za-z'’-]*")


def _opens_an_object(words, i, reach=3):
    """Is the word at `i` followed by an object -- a pronoun, a determiner, a
    number or a name -- straight away, or after the prepositions and
    particles the pack owns (`referring.phrase_openers`)? What only a verb or
    a preposition is followed by, never a noun ending a phrase."""
    from language_runtime import referring
    dets = set(referring.articles()) | {
        str(w).casefold()
        for w in linguistic("agents.common", "_DEFINITE_DETS")}
    openers = referring.phrase_openers()
    k = i + 1
    while k < len(words) and k <= i + reach:
        word = words[k]
        if not _WORD_TOKEN.fullmatch(word):
            return False
        low = word.casefold()
        if (low in _OBJECT_PRONOUNS or low in dets or referring.is_number(word)
                or (word[:1].isupper() and word[1:2].islower())):
            return True
        if low not in openers:
            return False
        k += 1
    return False


def _participle(word):
    """A word shaped like a participle -- the head of an absolute phrase
    ("hands clasped behind back", "eyes following the bow")."""
    low = str(word or "").casefold()
    return len(low) > 4 and low.endswith(("ing", "ed"))


def _pronoun_forms(pronouns):
    """Every form of one pronoun set, casefolded: the card's subject, object
    and possessive, and the paradigm's set its subject heads."""
    if not isinstance(pronouns, dict):
        return frozenset()
    forms = {str(pronouns.get(role) or "").strip().casefold()
             for role in ("subject", "object", "possessive")}
    forms.discard("")
    for paradigm in _THIRD_PERSON_SETS:
        if str(pronouns.get("subject") or "").strip().casefold() in paradigm:
            forms |= paradigm
    return frozenset(forms)


def _verbs_in_base(act):
    """A predicate written as a watcher sees it -- third person, its subject
    left out ("takes the letter and tucks it into the pocket") -- with every
    verb of its own doer's coordinated verb phrases in the base form ("take
    the letter and tuck it into the pocket"), or "" where that cannot be done
    exactly. ONE RULE for every frame that puts a predicate after its doer in
    the base form: the mind's own attempt ("I tried to ...", `own_attempt`)
    and the act it watched ("I saw Rhona Carrick ...", `_episode_sentence`).

    Read only from the closed classes the engine owns: the first word is the
    verb (a third-person form is turned to its base; a base form stays where
    its object follows it; a body noun or an auxiliary there is not turned);
    only the first sentence is the predicate's; a later third-person form
    opens a verb phrase of the same doer where a coordinator, a sequencer or
    a comma stands before it -- never inside a clause a subordinating or
    relative word, or a dash, opened for its own subject -- and is turned
    where its object follows it, or a coordinator stands before it with a
    word of its phrase after it or with the end of a verb phrase before the
    coordinator (the doer's own verb, an object pronoun, a particle: "held
    out and waits"); a body noun, a list of the body's parts, a plural ending
    a list and an absolute phrase's head are left as nouns, and anything
    uncertain is not turned at all. Quoted spans stay as said.
    """
    from language_runtime import referring
    act = str(act or "").strip().rstrip(".").strip()
    if not act or referring.unspaced(act):
        return ""
    breath = {str(w).casefold()
              for w in linguistic("agents.common", "_BREATH_CONJUNCTIONS")}
    body = {str(w).casefold()
            for w in linguistic("agents.common", "_OWN_BODY_NOUNS")}
    agreement = linguistic("agents.common", "_YOU_AGREEMENT")
    quoted = linguistic("agents.common", "_QUOTED_SPAN_RE")
    # ONLY THE FIRST SENTENCE IS THE ATTEMPT'S. "I tried to" governs the
    # sentence it opens; a later one stands as the act wrote it -- the owner's
    # bank, row 22342: "Lowers to one knee before the table. Takes Hinami's
    # nearest foot ... Lifts it slightly and presses", whose later sentences
    # open with their own verbs. Sentences by the engine's own splitter (a
    # title's period is not a full stop), over the text with its quotations
    # masked so a quoted full stop ends nothing.
    from .common import split_sentences
    masked = quoted.sub(lambda m: "x" * len(m.group(0)), act)
    parts = split_sentences(masked)
    cut = len(act)
    if len(parts) > 1 and parts[1]:
        cut = masked.find(parts[1], max(0, len(parts[0]) - 1))
        cut = len(act) if cut < 0 else cut
    act, rest = act[:cut], act[cut:]
    segments = quoted.split(act)
    if not segments[0].strip():
        return ""                       # opens with a quotation: no verb first
    # The words that end a verb phrase and never a noun phrase, before a
    # coordinator: a particle or a preposition the engine owns (a preposition
    # needs its object, so one standing before "and" is a particle) -- the
    # pack's phrase openers and the prepositions of `_OBJECT_PRONOUN_FOLLOWERS`,
    # less the subordinating words and the participles among them: a
    # participle ends a phrase inside a noun's as readily ("a man sitting and
    # others standing").
    particles = {
        w for w in set(referring.phrase_openers()) | _OBJECT_PRONOUN_FOLLOWERS
        if w not in breath and not _participle(w)}
    first, foreign, subordinate = True, False, False
    for s in range(0, len(segments), 2):
        tokens = re.split(r"(\s+|[,;—–])", segments[s])
        at = [k for k, t in enumerate(tokens) if t and not t.isspace()]
        words = [tokens[k] for k in at]
        verbs = set()                   # where the doer's own verbs stand
        for i, word in enumerate(words):
            if not _WORD_TOKEN.fullmatch(word):
                continue
            if first:
                first = False
                if word.casefold() in agreement:
                    return ""
                if word.casefold() in body and not _opens_an_object(
                        words, i, reach=1):
                    return ""           # a clause's subject: "hips lock forward"
                base = _base_from_third_person_s(word)
                if base is not None:
                    tokens[at[i]] = base
                elif not _opens_an_object(words, i):
                    return ""
                verbs.add(i)
                continue
            base = _base_from_third_person_s(word)
            low = word.casefold()
            prior = words[i - 1].casefold() if i else ""
            joins = referring.coordinator(low) or low in _SEQUENCERS
            if prior in (",", ";", "—", "–"):
                subordinate = False             # a clause stop ends one
            if prior in (";", "—", "–"):
                # A SPAN AFTER A DASH OR A SEMICOLON that opens with no verb of
                # the doer's is a clause of its own subject -- "intensify the
                # rhythm -- tongue presses deeper ..., then withdraws" (the
                # owner's bank, row 23519): "withdraws" is the tongue's.
                foreign = not ((base is not None and word[:1].islower())
                               or joins)
            if low in breath and not joins:
                # A SUBORDINATING OR RELATIVE WORD opens a clause of its own
                # subject that runs to the next stop: "as my own release breaks
                # and soaks through" (the owner's bank, row 28256), "before
                # things get warm" (row 25673), "all that lies between them" --
                # none of its verbs is the doer's.
                subordinate = True
                continue
            if base is None or not word[:1].islower() or subordinate:
                continue
            after_breath = referring.coordinator(prior) or prior in _SEQUENCERS
            after_stop = prior in (",", ";", "—", "–")
            if not (after_breath or after_stop):
                continue
            if low in agreement:
                return ""
            if low in body:
                # A BODY NOUN IS A VERB ONLY WITH ITS OBJECT STRAIGHT AFTER IT
                # ("eyes the door"): a phrase after it follows a noun as
                # readily -- "draw her torso and shoulders into the passage".
                nxt = words[i + 1].casefold() if i + 1 < len(words) else ""
                if _opens_an_object(words, i, reach=1):
                    tokens[at[i]] = base
                    verbs.add(i)
                elif nxt in referring.phrase_openers():
                    return ""
                continue                        # a noun: "hands and knees"
            if foreign:
                return ""                       # whose verb, nobody can say
            if (referring.coordinator(prior) and i >= 2
                    and words[i - 2].casefold() in body
                    and not _opens_an_object(words, i, reach=1)):
                # A LIST OF THE BODY'S PARTS: after "feet and", "calves
                # against the folds" is one more part (the owner's bank, row
                # 26690, filed "feet and calve").
                continue
            if _opens_an_object(words, i):
                tokens[at[i]] = base
                verbs.add(i)
            elif after_breath:
                # A verb by its place and form -- but after "and"/"or" only
                # with a word of its own phrase after it, or where what stands
                # before the coordinator ends a VERB phrase: a plural noun ends
                # its own coordination as readily ("brushing grit from coat
                # and trousers.", "gauges and keys,", the owner's bank rows
                # 27836 and 28637), where a verb before a stop is intransitive.
                # What stands before "and" settles it: the doer's own verb
                # ("pause and sighs."), an object pronoun ("turns to her and
                # waits"), or a particle ("keeps the letter held out and
                # waits.", the lighthouse probe, chat 2 row 40); a noun there
                # ("cheeks and ears", "corners and shadows") leaves it a noun.
                # After a sequencer ("then", "but") a noun phrase is not
                # coordinated, so the verb stands there whatever follows it.
                nxt = words[i + 1] if i + 1 < len(words) else ""
                left = words[i - 2] if i >= 2 else ""
                ends_a_verb = (i - 2 in verbs
                               or left.casefold() in _OBJECT_PRONOUNS
                               or left.casefold() in particles)
                if referring.coordinator(prior) and not ends_a_verb and (
                        not _WORD_TOKEN.fullmatch(nxt) or _participle(nxt)):
                    return ""
                tokens[at[i]] = base
                verbs.add(i)
            elif i + 1 < len(words) and _participle(words[i + 1]):
                continue                        # an absolute phrase's head
            else:
                return ""
        segments[s] = "".join(tokens)
    return "".join(segments) + rest


def own_attempt(act, *, self_forms=(), pronouns=None, pronouns_mine=False,
                keep_pronouns=False):
    """A mind's own act, written as a watcher sees it ("takes the letter and
    tucks it into his pocket"), as the predicate of its own attempt in its own
    first person ("take the letter and tuck it into my pocket") -- or "" where
    the turn cannot be made exactly, and the caller keeps the act as written.

    A MIND'S OWN ACT IS REMEMBERED IN ITS OWN FIRST PERSON, AS ITS ATTEMPT,
    WITH GRAMMAR THAT HOLDS. The memory files what the mind TRIED beside what
    it perceived come of it (`commit_memory._own_sequence_memory`); the bare
    contract's act written as a watcher sees it was filed with the doer's own
    name and as done -- "Pell Hardacre takes the sealed letter from Rhona
    Carrick's hand and tucks it into the inside pocket of the oilskin
    jacket." -- when the world had refused the take (the lighthouse probe,
    2026-10-20, chat 2 row 40), and two story days later his memory of the
    skip believed he had pocketed it.

    Turned exactly or not at all, and read only from the closed classes the
    engine owns: the act's first word is its verb (a third-person form is
    turned to its base; a base form stays where its object follows it); a
    later third-person form opens a verb phrase of the same doer where a
    coordinator, a sequencer or a comma stands before it -- never inside a
    clause a subordinating or relative word opened ("as my own release breaks
    and soaks through", "all that lies between them") -- and is turned
    where its object follows it, or where a coordinator stands before it and
    it is not a body noun ("hands and knees"; a body noun is a verb only with
    its object straight after it, "eyes the door"); after a comma it is left
    as the head of an absolute phrase where a participle follows it ("hands
    clasped behind back"), and anything else there is not turned at all; a
    span after a dash or a semicolon that opens with no verb of the doer's is
    a clause of its own subject ("-- tongue presses deeper, then withdraws"),
    and a verb phrase in it is not the doer's to turn. The
    doer's own pronouns turn with the doer, and only where nobody else
    present could be meant by them (`pronouns_mine`, the caller's reading of
    the scene): two women in one room, and "slides both hands from her inner
    thighs" is the other woman's. Where they cannot turn, the act is not
    turned -- unless `keep_pronouns`, for a line that already stood in the
    first person with them as written ("I tried to shift her posture"), which
    keeps them so and turns the rest. Quoted spans are what was said and stay.
    """
    text = _verbs_in_base(act)
    if not text:
        return ""
    # The doer's own pronouns, and nobody else's.
    def _seen(t):
        outside = " ".join(
            linguistic("agents.common", "_QUOTED_SPAN_RE").split(t)[0::2])
        return {w.casefold() for w in _WORD_TOKEN.findall(outside)}

    seen = _seen(text)
    own = _pronoun_forms(pronouns)
    unsure = (bool(seen & own) if own
              else any(seen & paradigm for paradigm in _THIRD_PERSON_SETS))
    if unsure and own and pronouns_mine and "they" not in own:
        turned = _pose_owner_second_person(text, pronouns, (), person="first")
        if not _seen(turned) & own:             # none left unturned ("hers")
            text, unsure = turned, False
    if unsure and not keep_pronouns:
        return ""                               # whose, nobody can say
    if self_forms:
        text = _self_first_person(text, self_forms)
    text = text.strip()
    head = text.split(" ", 1)[0]
    if not (head.isupper() and len(head) > 1):
        text = text[:1].lower() + text[1:]
    return text


def pose_percepts(scene, observer_name, co_present, display_map,
                  senses=None, *, self_forms=(), self_pronouns=None,
                  scrub=None):
    """How bodies are arranged: posture, what holds them up, who they are
    against, what pins them.

    `scrub` is the observer's identity floor for the pose's free text
    (posture, constraint, detail), handed in by perception so this stays a
    leaf: a pose is written once, by the Director, in true names, and served
    to every mind that sees the body -- its owner included. Without it the
    detail "Kneeling over Hinami ..., left palm resting on the warmth of
    Hinami's lower ribs" read to Vexara, who had never learned the name,
    beside the structured half of the same line that called her "the young
    woman" (the owner's chat 120, every beat, under both contracts; the
    tripwire repaired it after the fact).

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
                visual_level_between(scene, observer_name, name, senses),
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
        # AN ENGINE ID IS NOT A WORD OF THE STORY, in the free prose beside a
        # referent as much as in the referent itself (`_no_engine_ids`; PS2).
        pose = {f: (_no_engine_ids(scene, pose[f])
                    if f in _POSE_FREE_TEXT else pose[f])
                for f in pose}
        if scrub is not None:
            pose = {f: (scrub(pose[f]) if f in _POSE_FREE_TEXT and pose[f]
                        else pose[f])
                    for f in pose}
        data = {"posture": _self_second_person(
            pose["posture"], self_forms) if self_forms else pose["posture"]}
        # The observer's own first person of the same words, for its memory
        # (`_said_as_mine`): written while the third person still says which
        # role each of its names and pronouns had.
        mine = {"posture": _self_first_person(pose["posture"], self_forms)
                if self_forms else pose["posture"]}
        if level == "full":
            for f in ("support", "relation", "constraint", "detail"):
                data[f] = (_self_second_person(pose[f], self_forms)
                           if self_forms else pose[f])
                mine[f] = (_self_first_person(pose[f], self_forms)
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
                    mine[f] = _pose_owner_second_person(
                        mine.get(f), self_pronouns, other_forms,
                        person="first")
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
        firsts = {f + "_mine": m for f in ("posture", "relation",
                                           "constraint", "detail")
                  if (m := _mine_if_it_matters(mine.get(f), data.get(f)))}
        out.append(Percept(
            kind="pose",
            channel="interoception" if is_self else "sight",
            source_label=label,
            fidelity="full" if level == "full" else "degraded",
            data={**data, **firsts, "directed_at_self": is_self},
            salience=0.3,
            dedupe_key=standing_key(
                "pose", (body_key(name),),
                tuple(str(data.get(f) or "")
                      for f in (_OWN_POSE_KEY_FIELDS if is_self
                                else _POSE_RENDER_FIELDS))),
        ))
    return out


_POSE_RENDER_FIELDS = ("posture", "support", "relative_to", "relation",
                       "constraint", "detail")

#: The fields that CONSTITUTE the observer's own arrangement, for the dedupe
#: key alone. `detail` is left out for the same reason
#: `world.spatial_geometry._POSE_ARRANGEMENT_FIELDS` leaves it out: "it
#: qualifies an arrangement, it does not constitute one." Measured (chat
#: 117, 2026-09-07): the body hand re-words a player's `detail` nearly every
#: beat -- 67 of 89 consecutive pairs differed -- and with `detail` in the
#: key each re-wording hashed as a CHANGED pose, led the beat as a numbered
#: obligation the narrator sheet says must reach the page, and closed 51% of
#: those beats with the player being told his own posture back. Other
#: bodies keep the six-field key: THEIR detail is a seen fact ("fingers
#: hooked into his belt") and a real change.
_OWN_POSE_KEY_FIELDS = ("posture", "support", "relative_to", "relation",
                        "constraint")

#: The pose fields that are authored PROSE rather than a referent. `support`
#: and `relative_to` are referents and go through `_pose_referent`, which
#: already refuses an id (step 5); these three reach the page as written.
_POSE_FREE_TEXT = ("posture", "constraint", "detail")


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


def cue_percept(source_name, label, cue, *, order_key, can_see=True):
    """One physical tell that reached this observer -- a glance, a grip, a
    catch in the voice the character did not declare as an action (D1;
    Wood/Stanislavski: the actor's body). `cue` is the OBSERVABLE text
    alone: `_delivered_manifest` has already decided, per observer and per
    channel, which tells land, and neither the tell's `because` nor its
    `betrays` ever reaches a percept -- meaning stays with the mind that
    has it. Observations derive from the render, so a reader downstream
    cannot recover more than the page says. Review A36 measured the payload
    computed for 101 beats and read by nothing."""
    text = _strip_sentence_ends(cue)
    if not text or not label:
        return None
    return Percept(
        kind="cue", channel="sight" if can_see else "hearing",
        source_label=label, order_key=order_key,
        data={"cue": text, "body": body_key(source_name)},
        salience=0.55,
        dedupe_key=standing_key("cue", (body_key(source_name),), (text,)),
    )


def demeanor_percept(source_name, label, demeanor):
    """A body's surface demeanor as STANDING state: how it carries itself
    this beat, rendered while it holds and again only when it changes --
    the standing ledger's ordinary verdicts, so a calm that lasts ten beats
    costs one sentence (D1)."""
    text = _lower_lead(_strip_sentence_ends(demeanor))
    if not text or not label:
        return None
    return Percept(
        kind="demeanor", channel="sight", source_label=label,
        data={"demeanor": text, "body": body_key(source_name)},
        salience=0.45,
        dedupe_key=standing_key("demeanor", (body_key(source_name),), (text,)),
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


#: What a body knows of its own ears (DESIGN_SOUND_FIELD § 13): `ringing`
#: after a blast, while the shift is at least `spatial_listener.RINGING_DB`;
#: `recovered`, said once to an ear that was ringing the beat before.
EAR_STATES = ("ringing", "recovered")


def ear_percepts(shift_db, prev_standing=frozenset(), *, fresh=False):
    """A BODY KNOWS ITS OWN RINGING EARS (DESIGN_SOUND_FIELD § 13). After a
    blast past `spatial_listener.BLAST_DB` the ear is dulled and rings; the
    listener has that as interoception -- their own body's state, never
    another's (nobody else knows it unless they see it, and nothing here
    reaches any view but this body's own). `fresh` is a blast that reached
    them THIS beat, before the commit has written the shift; `shift_db` is
    the shift the scene holds.

    Standing, keyed by its state, so it is news when it starts and furniture
    while it lasts; and its FADING is said once, to an ear whose own ledger
    held the ringing (`prev_standing`), which is the class every steady
    sound's stopping is told by (`sound_ceased_percept`)."""
    from world.spatial import RINGING_DB
    ringing = standing_key("ears", ("self",), ("ringing",))
    try:
        shift = float(shift_db or 0.0)
    except (TypeError, ValueError):
        shift = 0.0
    if fresh or shift >= RINGING_DB:
        return [Percept(
            kind="sensation", channel="interoception", source_label="you",
            data={"ears": "ringing", "directed_at_self": True},
            salience=0.55, dedupe_key=ringing)]
    if ringing in (prev_standing or ()):
        return [Percept(
            kind="sensation", channel="interoception", source_label="you",
            data={"ears": "recovered", "directed_at_self": True},
            salience=0.4,
            dedupe_key=standing_key("ears", ("self",), ("recovered",)))]
    return []


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


def ambient_percepts(sensory_events, observer_room, *, order_key=None,
                     after=None):
    """Authored opening sensory events, filtered by room scope. An event
    naming a room is admitted only to observers in that room; a roomless
    event is scene ambience.

    `after` (wave B2, one of `spatial_sound_field.SOUND_AFTER_WORDS`) says
    the sound reached this observer that long after the SIGHT of what made
    it -- a source seen far off -- and the sentence says so; the caller
    orders it after the act it saw (`perception`'s outcome pass).

    `order_key` decides which HALF of the view these land in, and the
    caller decides because the two callers mean different things. The
    establish stage's authored ambience is scene-setting -- the air of a
    place, true before the beat and after it -- and belongs in standing
    state, which is what an absent key gives it (`render_view` splits on
    `order_key is None`). A BEAT'S OWN SOUND EVENT IS NOT THAT.

    `spatial_sound_field`'s own note on the channel is explicit: "a noise
    is a thing that happened in this window and never a standing fact",
    and the record is beat-scoped so hard that "the beat number IS the
    lifetime". Minted without a key anyway, every such sound landed in
    `present_scene`, which the narrator sheet says in as many words
    "carries no obligation" -- so the loudest thing in a beat was as
    optional as the colour of the floor.

    Measured live, chat 117 turn 65. A carbonic stalker moved in the room
    the cast were kneeling in; perception delivered its voice correctly --
    "a slow, rhythmic siphon-vent hiss and the soft drag of leathery
    footfalls, nearer with every hunted breath" -- as `standing: True`, so
    it never entered the numbered deliveries, and the prose recorded that
    nothing was moving.
    """
    out = []
    for idx, event in enumerate(sensory_events or []):
        if not isinstance(event, dict):
            continue
        room = str(event.get("room") or event.get("room_id")
                   or event.get("source_room") or "")
        if room and observer_room and room != str(observer_room):
            continue
        # `detail` FIRST, because it is the canonical key and the other
        # three are not. `spatial_sound_field.normalize_sensory_event` holds
        # the shape -- "{kind, room, level | db, source, detail} -- the
        # note's shape, and a closed set of keys" -- and it FOLDS `desc` and
        # `description` INTO `detail` on the way in. So every stored event
        # carries its text under `detail` and this reader checked three
        # spellings that normalisation had already removed.
        #
        # Its own warning, one module over, is what happened here read from
        # the other end: "a hand that writes prose into a key nobody reads
        # writes it into nothing." The writer was canonical; the READER
        # drifted.
        #
        # Measured live, chat 117 turn 65. A carbonic stalker followed the
        # cast through a jammed pressure door and stood in the room with
        # them, and the beat's own scene carried its voice --
        # {"kind": "sound", "room": <their room>, "level": "loud",
        # "detail": "a slow, rhythmic siphon-vent hiss and the soft drag of
        # leathery footfalls, nearer with every hunted breath"}. The player
        # received no hearing percept at all. Sight was legitimately dark;
        # this was the channel that should have carried it, and it dropped
        # the event for having its text in the one field the format
        # guarantees.
        desc = str(event.get("detail") or event.get("desc")
                   or event.get("description") or event.get("text")
                   or "").strip()
        if not desc:
            continue
        channel = _ambient_channel(event)
        if event.get("echo") and channel != "sight":
            desc = desc.rstrip(".") + _en("sound_echo")
        if after in ("moment", "seconds") and channel != "sight":
            from language_runtime import compositor_text
            desc = compositor_text("sound_after_sight_" + after,
                                   desc=desc.rstrip(".!?。"))
        out.append(Percept(
            kind="ambient", channel=channel, data={"desc": desc},
            salience=0.4,
            **({"order_key": order_key + idx} if order_key is not None else {}),
            dedupe_key=standing_key("ambient", (desc,), (desc,)),
        ))
    return out


#: What a distant sound is allowed to be. `distant_sounds` returns
#: `{kind, level, db, character, bearing}` and only three of those reach a
#: percept: the margin over this listener's own noise floor, the DIRECTION it
#: arrived from, and what it sounded LIKE. No room, no name, no words -- and
#: the subtraction is done by naming what is kept rather than by dropping
#: what is not, so a field added upstream cannot ride in behind it
#: (DESIGN_SOUND_DECIBELS.md § 3).
DISTANT_SOUND_LEVELS = ("faint", "plain", "overwhelming")


def distant_sound_percepts(records):
    """Sounds from beyond the near field, as percepts.

    A bang two rooms away is a HEARING percept like any other: it goes in
    the same list, through the same renderer and the same dedupe, so nothing
    downstream has to know the far field exists. What makes it different is
    what it may say, and that is decided here -- a bearing and a character,
    never a sentence and never a place.

    A record the far field could give no bearing for is DROPPED. The three
    templates all say which way the sound came from, and a distant noise
    with no direction is a fact this observer has no frame for; silence is
    the honest rendering of that, and it subtracts.
    """
    out = []
    for record in records or ():
        if not isinstance(record, dict):
            continue
        level = str(record.get("level") or "")
        if level not in DISTANT_SOUND_LEVELS:
            continue
        bearing = record.get("bearing")
        where = " ".join(str((bearing or {}).get("phrase") or "").split())
        if not where:
            continue
        character = " ".join(str(record.get("character") or "").split())
        out.append(Percept(
            kind="ambient", channel="hearing",
            data={"distant": {"level": level, "where": where,
                              "character": character}},
            salience=0.45,
            # A sound is over when the beat is, so the key carries the beat's
            # own content: the same bang louder, or from another quarter, is
            # news again rather than the same standing fact.
            dedupe_key=standing_key("distant_sound", (where,),
                                    (level, character)),
        ))
    return out


def render_distant_sound(distant, *, episode=False):
    """One distant sound as the reader meets it: how loud against this
    room's own quiet, which way, and what it sounded like.

    `episode` is the memory's wording of a sound with no character of its
    own: "a sound you cannot place" puts its subject inside a relative
    clause, which the second-to-first swap cannot see is a subject, so the
    pack carries the first person ("a sound I cannot place")."""
    distant = distant if isinstance(distant, dict) else {}
    level = str(distant.get("level") or "")
    where = str(distant.get("where") or "")
    if level not in DISTANT_SOUND_LEVELS or not where:
        return ""
    character = (str(distant.get("character") or "").strip()
                 or _en("sound_distant_character_none"
                        + ("_episode" if episode else "")))
    return _cap(_en("sound_distant_" + level, where=where,
                    character=character))


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


def walk_underway_percepts(walk):
    """A walk this body declared and has not finished: where it has got to
    and where it is still going, in the pack's words (`perception.
    _walk_underway`). One line, the walker's own knowledge of its body."""
    from language_runtime import compositor_text
    if not isinstance(walk, dict) or not walk.get("to"):
        return []
    text = compositor_text("walk_underway", to=walk["to"], at=walk.get("at") or "")
    return [Percept(kind="ambient", channel="interoception", data={"desc": text},
                    dedupe_key=standing_key("walk_underway", (walk["to"],), (walk.get("at") or "",)))]


def vista_percepts(seen, looked=()):
    """What stands on the horizon, to a body that can see it
    (`world.vistas.visible_vistas`): one line each, by compass bearing, in
    the pack's own words -- a skyline under a moon as a silhouette. A
    distant thing is seen and may be spoken of; nothing here makes it a
    thing a hand reaches (`world/vistas.py`).

    `looked` is `[(vista, clarity | "unseen")]` for the vistas this body's
    own act LOOKED AT this beat: what the look found is the beat's, so it is
    an EVENT, ordered first -- right after the body's own words -- never
    standing background the player tier's delta may suppress, and a look
    that finds nothing (fog, the dark, a ridge) says so. Live, Larch Hill
    (2026-10-04): Ren went to the north windows and looked at the range,
    the range sat in present_scene, and the page never said what she saw."""
    from language_runtime import compositor_text
    from world.spatial import _phrase_table
    compass = _phrase_table("compass_words")
    looked = list(looked or ())
    looked_ids = {v["id"] for v, _how in looked}
    out = []

    def line(vista, clarity, nearer=""):
        where = compass.get(vista["bearing"], vista["bearing"])
        if str(clarity).startswith("unseen"):
            # WHAT THE EYE MEETS INSTEAD, never a placeholder (owner,
            # 2026-10-07): the walls, the weather closing in, the dark, the
            # curve of the earth, nearer ground standing higher.
            why, _sep, air = str(clarity).partition(":")
            why = why[len("unseen_"):] if why.startswith("unseen_") else "nearer"
            return compositor_text("vista_unseen_" + why, compass=where,
                                   name=vista["name"], air=air_phrase(air))
        # Past a nearer one on the same bearing, a vista is "beyond" it, named
        # in the line itself -- a standing line is said alone on a later
        # beat, so it cannot lean on the line before it
        # (`_beside_on_one_bearing`).
        more = "_beyond" if nearer else ""
        if clarity == "silhouette":
            return compositor_text("vista_silhouette" + more, compass=where,
                                   name=vista["name"], nearer=nearer)
        if clarity == "lights":
            return compositor_text("vista_lit_night" + more, compass=where,
                                   name=vista["name"], nearer=nearer)
        desc = compositor_text("vista_desc_join", desc=vista["desc"]) if vista["desc"] else ""
        return compositor_text("vista_seen" + more, compass=where, name=vista["name"],
                               desc=desc, nearer=nearer)

    for vista, clarity in looked:
        # A LOOK IS THE VIEW'S NEWS, AND IT FILES WHAT IT SAW: the standing
        # line the look stands in for goes into the ledger with it, or the
        # next beat announced the same range again as if first seen
        # (`files_standing`, read by every pack's view as a voice key is).
        data = {"desc": line(vista, clarity)}
        if not str(clarity).startswith("unseen"):
            data["files_standing"] = standing_key("vista", (vista["id"],), (clarity,))
        out.append(Percept(
            kind="ambient", channel="sight", source_label=vista["name"],
            data=data, order_key=-1, salience=0.6,
            dedupe_key=standing_key("vista_look", (vista["id"],), (clarity,))))
    previous = None
    for vista, clarity in _beside_on_one_bearing(
            [(v, c) for v, c in (seen or ()) if v["id"] not in looked_ids]):
        nearer = ""
        if previous is not None and previous[0]["bearing"] == vista["bearing"] \
                and not str(previous[1]).startswith("unseen") \
                and not str(clarity).startswith("unseen") \
                and previous[0].get("distance_given") and vista.get("distance_given") \
                and float(previous[0]["distance_km"]) < float(vista["distance_km"]):
            nearer = previous[0]["name"]
        previous = (vista, clarity)
        # Under the room's own salience, as far places are: the horizon is
        # never a memory's gist over where the body stood.
        out.append(Percept(
            kind="ambient", channel="sight", source_label=vista["name"],
            data={"desc": line(vista, clarity, nearer)}, salience=0.15,
            dedupe_key=standing_key("vista", (vista["id"],), (clarity,))))
    return out


def _beside_on_one_bearing(seen):
    """`seen` with the vistas on one bearing side by side, nearest first, the
    bearings in the order they first appear. Three standing lines in a row
    each opened "To the south," (Kirinoura, scratch chat 167, 2026-10-05):
    the river, the fields across it, the hills that close the valley."""
    order = []
    for vista, _clarity in seen:
        if vista["bearing"] not in order:
            order.append(vista["bearing"])
    return sorted(seen, key=lambda vc: (order.index(vc[0]["bearing"]),
                                        float(vc[0].get("distance_km") or 0.0)))


#: FAR SIGHT: the standing lines about what is seen past the near field --
#: the horizon (`vista_percepts`) and the far places on the way to it
#: (`landscape_percepts`). Two rules read them by this tag and nothing else:
#: they are ADDED to a view and are never the whole of one (the roll-call
#: rule below and `perception`'s empty-view floor decide on the near spans,
#: so a first sighting never stands in for the room the narrator is handed),
#: and they are what English memory files of a view's far half
#: (`_files_as_memory`).
FAR_SIGHT_TAGS = frozenset(("vista", "landscape"))


def far_sight(percept):
    """Is this a standing line of far sight -- a vista or a far place?"""
    if percept.kind != "ambient" or percept.order_key is not None:
        return False
    return str(percept.dedupe_key or "").split(":", 1)[0] in FAR_SIGHT_TAGS


def near_text(rendered):
    """A rendered view's text without its far-sight spans -- what the
    roll-call rule and the empty-view floor ask about."""
    return " ".join(sentence for p, sentence in (rendered.spans or ())
                    if not far_sight(p)).strip()


def is_landscape(percept):
    return (percept.kind == "ambient"
            and isinstance((percept.data or {}).get("landscape"), dict))


#: What a far place's percept may carry and nothing more, so a field added
#: upstream cannot ride into a view (`DISTANT_SOUND_LEVELS`' precedent).
#: Room ids ride only inside hashes; a name only when the mind knows it.
LANDSCAPE_GROUNDS = ("open", "sheltered", "building")
LANDSCAPE_HEIGHTS = ("one", "two", "tall")
LANDSCAPE_GRAINS = ("mid", "outline")
LANDSCAPE_COVERS = ("building", "ground")


def air_phrase(word):
    """The pack's word for what the air holds (`vistas.VISIBILITY_KM`'s
    words: fog, mist, rain...), as it closes a view."""
    from world.spatial import _phrase_table
    table = _phrase_table("air_words")
    return str(table.get(str(word or ""), table.get("fog", word or "")))


def _far_line_text(line):
    """One far line in the ACTIVE pack's words: English's own renderer, or
    the pack's templates through the layout every pack shares."""
    from language_runtime import compositor_text, current_language_id
    from world.spatial import _phrase_table
    if str(current_language_id.get() or "en").startswith("en"):
        return render_landscape_line(line)
    return str(compose_landscape_line(
        line, compositor_text, compass_words=_phrase_table("compass_words")))


def landscape_look_percepts(findings):
    """What this body's own act LOOKED AT far off this beat
    (`world.landscape.looked_far`): an EVENT each, ordered first -- right
    after the body's own words, as a look at the horizon is
    (`vista_percepts`) -- never standing background a view's delta may
    suppress.

    A place seen is its own far line, named by the name the look used when
    the mind knows no other ("a two-storey building where the bell loft
    is"). A place hidden is what stands in the way: the roofs or the ground
    nearer in, the weather closing in, the dark, the walls or buildings
    round the looker. NEVER A PLACEHOLDER (owner, 2026-10-07: "nothing can
    be made out and similar place holders are quite frustrating"). Live
    case: scratch story 166 turn 4589, a look up at the bell loft from the
    low walk reached no view at all."""
    from language_runtime import compositor_text
    out = []
    for found in findings or ():
        if not isinstance(found, dict) or not found.get("room"):
            continue
        label = str(found.get("label") or "")
        place = found.get("place")
        if isinstance(place, dict):
            shown = dict(place, order=0)
            if label and not shown.get("name"):
                shown["name"] = label
            standing = landscape_percepts([shown])
            lines = landscape_lines(standing)
            if not lines:
                continue
            desc = _cap(_far_line_text(lines[0][1]))
            kind = "seen:" + str(place.get("shows") or "whole")
            data = {"desc": desc, "files_standing": standing[0].dedupe_key}
        else:
            cover = found.get("hidden_by") if isinstance(found.get("hidden_by"), dict) else {}
            kind = str(cover.get("kind") or "around")
            if kind not in ("building", "ground", "air", "dark", "walls", "around"):
                kind = "around"
            named = "_named" if kind in ("building", "ground") and cover.get("name") else ""
            desc = _cap(compositor_text("far_look_hidden_" + kind + named, label=label,
                                        cover=str(cover.get("name") or ""),
                                        air=air_phrase(cover.get("air"))))
            data = {"desc": desc}
        out.append(Percept(
            kind="ambient", channel="sight", source_label=label, data=data,
            order_key=-1, salience=0.6,
            dedupe_key=standing_key("far_look", (found["room"],), (kind,))))
    return out


def landscape_percepts(places):
    """The far places a body sees (`world.landscape.far_places`), one
    standing sight percept per PLACE.

    Keyed by the place and what is seen of it -- never by the way the eye
    reached it, its compass or the name -- so walking along a path does not
    re-announce, or re-file in memory, a place already seen, and learning a
    place's name is not news about it (the scent precedent). Salience under
    the room's own, so a far line never takes a memory's gist from where the
    body stood. Grouped back into lines by `landscape_lines`.

    A place's FAR LOOK (`world.landscape`: the planner's own field, admitted
    to this mind or "") rides as `look`, and joins the key only where there
    is one: a look rewritten -- the reeds burned, the quay flooded -- is
    news about the place, and a place that declares none keeps the key it
    always had."""
    from world.landscape import BIG_PER_PLACE, normalize_far_look
    out = []
    for place in places or ():
        if not isinstance(place, dict) or not place.get("room"):
            continue
        ground = place.get("ground")
        grain = place.get("grain")
        if ground not in LANDSCAPE_GROUNDS or grain not in LANDSCAPE_GRAINS:
            continue
        lead = place.get("lead") if isinstance(place.get("lead"), dict) else {}
        subject = place.get("key_room") or place["room"]
        data = {
            "line": _short_hash("landscape-line", place.get("line")),
            "order": int(place.get("order") or 0),
            "id": _short_hash("landscape-place", subject),
            "front": (_short_hash("landscape-place", place["front"])
                      if place.get("front") else ""),
            "lead": {"compass": str(lead.get("compass") or ""),
                     "via": str(lead.get("via") or ""),
                     "rise": str(lead.get("rise") or ""),
                     "via_id": (_short_hash("landscape-place", lead["via_room"])
                                if lead.get("via_room") else "")},
            "ground": ground,
            "breadth": "wide" if place.get("breadth") == "wide" else "",
            "name": str(place.get("name") or ""),
            "height": (place.get("height") if place.get("height") in LANDSCAPE_HEIGHTS
                       else ""),
            "lights": int(place.get("lights") or 0),
            "high": bool(place.get("high")),
            "dark": bool(place.get("dark")),
            "big": [str(t) for t in (place.get("big") or ()) if str(t).strip()][:BIG_PER_PLACE],
            "tier": "outline" if place.get("tier") == "outline" else "mid",
            "grain": grain,
            # Only its top shows, over the roofs or the ground nearer in.
            "over": (place.get("over") if place.get("shows") == "top"
                     and place.get("over") in LANDSCAPE_COVERS else ""),
            "look": normalize_far_look(place.get("look")),
        }
        signature = (data["grain"], data["ground"], data["breadth"], data["height"],
                     data["lights"], data["high"], data["dark"], len(data["big"]),
                     data["over"])
        if data["look"]:
            signature += (_short_hash("landscape-look", data["look"]),)
        out.append(Percept(
            kind="ambient", channel="sight", source_label=data["name"],
            data={"landscape": data}, salience=0.15,
            dedupe_key=standing_key("landscape", (subject,), signature)))
    return out


def _plain_ground(row):
    """What a row of bare ground IS, for the run that folds a line of it
    into one item: its kind and breadth, as it always was, so a far look
    never costs a mind a place the run said (`landscape.LOOKS_SPLIT_RUNS`,
    the owner's switch, off). With the switch on, a place's far look is part
    of what it is, and only places that read alike fold."""
    from world.landscape import LOOKS_SPLIT_RUNS
    g = row.get("ground")
    if (g is None or row.get("buildings") or g.get("name") or g.get("big")
            or g.get("lights") or g.get("dark")):
        return None
    if LOOKS_SPLIT_RUNS and g.get("look"):
        return ("look", g["look"])
    return ("plain", g.get("ground"), g.get("breadth"))


def landscape_lines(percepts):
    """[(representative percept, line)] -- the far places of one view laid
    out as lines, for EVERY language pack (`player_view_order`'s
    precedent): one line per way out, nearest first; ground in order along
    it, each with the buildings fronting it; the buildings fronting the way
    out itself said beside it; a run of plain unnamed ground of one kind said
    once ("stretching on"), by its nearest and farthest far looks where they
    have them (`_plain_ground`); at most `SEGMENTS_PER_LINE` rows, the
    nearest two and the farthest. The representative is the line's first
    place, the one an observation is filed against."""
    from world.landscape import SEGMENTS_PER_LINE
    groups, order = {}, []
    for p in percepts or ():
        data = (p.data or {}).get("landscape") if is_landscape(p) else None
        if not isinstance(data, dict):
            continue
        key = data.get("line")
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append((p, data))
    out = []
    for key in order:
        members = sorted(groups[key], key=lambda pd: pd[1].get("order", 0))
        percept_of = {id(d): p for p, d in members}
        rep, first = members[0]
        lead = first.get("lead") or {}
        grounds = [d for _p, d in members if d.get("ground") != "building"]
        buildings = [d for _p, d in members if d.get("ground") == "building"]
        ground_ids = {d.get("id") for d in grounds}
        beside = [b for b in buildings
                  if lead.get("via_id") and b.get("front") == lead.get("via_id")]
        rows = [{"ground": g, "buildings": [b for b in buildings
                                            if b.get("front") == g.get("id")],
                 "tier": g.get("tier"), "order": g.get("order", 0)} for g in grounds]
        rows += [{"ground": None, "buildings": [b], "tier": b.get("tier"),
                  "order": b.get("order", 0)} for b in buildings
                 if b not in beside and b.get("front") not in ground_ids]
        rows.sort(key=lambda r: r["order"])
        merged = []
        for row in rows:
            plain = _plain_ground(row)
            if plain and merged and merged[-1]["plain"] == plain:
                merged[-1]["run"] = True
                merged[-1]["also"].append(row["ground"])
                continue
            merged.append({**row, "plain": plain, "run": False, "also": []})
        if len(merged) > SEGMENTS_PER_LINE:
            merged = merged[:SEGMENTS_PER_LINE - 1] + merged[-1:]
        # WHAT THE LINE SAYS: every place it shows -- a run's places are said
        # as the run -- and the names among them, so memory files what the
        # view delivered and indexes what the line names (review 2026-10-05:
        # an episode re-laid from the changed places alone filed a place the
        # view had trimmed away).
        said = list(beside)
        for row in merged:
            said += ([row["ground"]] if row.get("ground") else []) + row["also"]
            said += row.get("buildings") or []
        out.append((rep, {
            "lead": lead, "beside": beside, "rows": merged,
            "shown": [percept_of[id(d)] for d in said if id(d) in percept_of],
            "names": [d["name"] for d in said if d.get("name")]}))
    return out


def compose_landscape_line(line, text, *, episode=False, thing=None,
                           compass_words=None):
    """One far line in a language's own words: `text(key, **values)` is the
    pack's template reader, `thing` how an authored desc is spliced into a
    list (English's `_noun_phrase`), `compass_words` the pack's compass. The
    layout is `landscape_lines`'; nothing here decides what is shown."""
    thing = thing or (lambda s: str(s).strip().rstrip(".。"))
    compass_words = compass_words or {}
    joiner = str(text("landscape_and"))
    sep = str(text("landscape_items"))
    # Every kind of building this line has said so far, in the words it said
    # it -- a look's phrase, a named or notable building's, and the plain
    # ones counted -- so a row whose buildings read as the ONE kind said
    # before is said as more of them (`building_parts`).
    said_kinds = set()

    def count_bucket(n):
        """The count words' bucket, as plain buildings are counted."""
        return "1" if n == 1 else "2" if n == 2 else "few" if n <= 5 else "many"

    def lights_word(d):
        if not d.get("lights"):
            return ""
        if d.get("high") and d["lights"] == 1:
            return text("landscape_light_high")
        return text("landscape_light_n") if d["lights"] > 1 else text("landscape_light_1")

    def building(d):
        whole = _building_whole(d)
        if whole and d.get("over"):
            # ONLY ITS TOP SHOWS, over what stands nearer -- the roofs or the
            # rise of the ground (`landscape._seen_part`).
            return text("landscape_top_over_" + d["over"], place=whole)
        return whole

    def _building_whole(d):
        lights = lights_word(d)
        # ITS FAR LOOK, where the planner wrote one, in place of the words
        # that say only that a building stands there (`world.landscape`) --
        # never when its mass is dark: then only its lights show, and a mind
        # that knows the place by name is told where they are, not what it
        # is built of (review 2026-10-08, F5).
        look = thing(d["look"]) if d.get("look") and not d.get("dark") else ""
        base = look or text("landscape_building_" + (d.get("height") or "one"))
        if d.get("name"):
            base = text("landscape_building_named", building=base, name=d["name"])
            # The light at the named building, never trailing its name: "a
            # building where The Mill is with a light" said the mill was.
            if lights:
                return text("landscape_lit_known", lights=lights, place=base)
            return base if not d.get("dark") else ""
        if d.get("dark"):
            return lights
        if lights and d.get("look"):
            # A look carries its own phrase ("hung with coils of rope"), so
            # what stands with it is set apart from it (`landscape_with_look`).
            return text("landscape_with_look", place=base, things=lights)
        return text("landscape_with_lights", place=base, lights=lights) if lights else base

    def building_parts(bs):
        """``(again, parts)``: a row's buildings as phrases. `again` is the
        back-reference, when there is one, which the caller says FIRST.

        A building with a look of its own, its mass in view, is said by it
        and never counted -- and buildings that read the same (the look,
        and whatever light or top shows with it) are said once with their
        count, so a row of alike houses is one phrase, never the same
        phrase over and over (review 2026-10-08, F6: four alike houses ran
        a line to 1,270 characters). With the owner's cap, the nearest that
        many phrases of a row are said and the rest of its buildings are
        said as if they had no look -- by their height, their lights and
        their top (review R2-8: counted as plain, a lit one lost its light).
        A building with no look is said or counted exactly as it was.

        MORE OF THEM, ONLY WHERE NOTHING ELSE CAN BE WHAT THEY ARE MORE OF
        (review R2-1). A row whose buildings read as the one kind of
        building this line has said so far is said as more of them, with
        their count ("two more such buildings"), and before anything else
        on the row: said after a new phrase it read as more of THAT -- "a
        tall brick warehouse with a hoist and more of the same" told the
        mind of warehouses that were tarred houses, in both packs. Where the
        line has said other kinds as well, the phrase is said again whole,
        since a back-reference would leave the mind to guess which kind."""
        from world.landscape import DESCRIBED_BUILDINGS_PER_ROW
        named = [b for b in bs if b.get("name")]
        looked = [b for b in bs if not b.get("name") and b.get("look") and not b.get("dark")]
        alike = {}
        for b in looked:
            alike.setdefault(str(building(b)), []).append(b)
        phrases = list(alike)
        cap = DESCRIBED_BUILDINGS_PER_ROW
        described = phrases if cap is None else phrases[:cap]
        unlooked = [b for b in bs if b not in named and b not in looked] + [
            dict(b, look="") for phrase in phrases[len(described):] for b in alike[phrase]]
        plain = [b for b in unlooked if (b.get("height") or "one") == "one"
                 and not b.get("lights") and not b.get("dark") and not b.get("over")]
        notable = [b for b in unlooked if b not in plain]
        before = set(said_kinds)
        again, parts = [], []
        for b in named + notable:
            phrase = str(building(b))
            if phrase:
                parts.append(phrase)
                said_kinds.add(phrase)
        for phrase in described:
            bucket = count_bucket(len(alike[phrase]))
            if before == {phrase}:
                again.append(text("landscape_again_" + bucket))
            elif bucket == "1":
                parts.append(phrase)
            else:
                parts.append(text("landscape_alike_" + bucket, look=phrase))
            said_kinds.add(phrase)
        if plain:
            parts.append(text("landscape_building_one") if len(plain) == 1
                         else text("landscape_buildings_" + count_bucket(len(plain))))
            said_kinds.add("\0plain")
        return ([str(x) for x in again if x], [str(x) for x in parts if x])

    def joined(parts):
        if len(parts) <= 1:
            return parts[0] if parts else ""
        return str(text("landscape_list")).join(parts[:-1]) + joiner + parts[-1]

    def buildings(bs):
        again, parts = building_parts(bs)
        return joined(again + parts)

    def ground(d, run=False, standing=(), also=()):
        # A RUN, said by its two ends: the nearest place's far look and the
        # farthest's, where they have them -- the places between are said by
        # the run, as they always were (`_plain_ground`).
        head = thing(d["look"]) if d.get("look") and not d.get("name") else ""
        tail = also[-1] if run and also else {}
        far = thing(tail["look"]) if tail.get("look") else ""
        if run and far and far != head:
            kind = text("landscape_sheltered" if d.get("ground") == "sheltered"
                        else "landscape_open")
            base = text("landscape_look_run_to" if head else "landscape_run_to",
                        place=head or kind, far=far)
        elif run and head:
            base = text("landscape_look_run", place=head)
        elif d.get("name"):
            base = d["name"]
        elif head:
            # How it reads from afar, where the world declares it.
            base = head
        elif d.get("ground") == "sheltered":
            base = text("landscape_sheltered")
        elif run:
            base = text("landscape_open_run")
        else:
            base = text("landscape_open_wide" if d.get("breadth") == "wide"
                        else "landscape_open")
        lights = lights_word(d)
        if d.get("dark"):
            return text("landscape_lit_known", lights=lights, place=base) if d.get("name") else lights
        # What stands on it -- its big things, then its buildings -- is ONE
        # list after "with", so nothing in it can read as standing on the
        # last noun of another (review: "an oak, and on it two buildings").
        # More of the buildings said before leads it, so nothing new on the
        # row can be what they are more of (`building_parts`).
        again, bparts = building_parts(standing)
        things = again + [thing(t) for t in d.get("big") or () if thing(t)]
        bs = joined(bparts)
        things += ([bs] if bs else []) + ([lights] if lights else [])
        if not things:
            return base
        # A look is a phrase of its own and often ends in one ("lined with
        # stalls"), so the list after it is set apart rather than read as
        # part of it: "lined with stalls, with a narrow office" -- never
        # "lined with stalls with a narrow office".
        key = "landscape_with_look" if (d.get("look") and not d.get("name")) else "landscape_with"
        return text(key, place=base, things=joiner.join(things))

    def row_phrase(row):
        if row.get("ground") is None:
            return buildings(row.get("buildings") or ())
        return ground(row["ground"], run=row.get("run"), standing=row.get("buildings") or (),
                      also=row.get("also") or ())

    lead = line.get("lead") or {}
    compass = compass_words.get(lead.get("compass") or "", "") if lead.get("compass") else ""
    rows = line.get("rows") or []
    suffix = "_episode" if episode else ""
    beside = buildings(line.get("beside") or ())
    via = lead.get("via") or ""
    # What fronts an UNNAMED way out is simply the line's first item, so the
    # connectors are given after it takes its place (it was spliced in front
    # of a first item that kept no "then": "a building, open ground").
    phrases = ([(beside, "mid")] if beside and not via else []) + [
        (row_phrase(row), row.get("tier")) for row in rows]
    items, far_said = [], False
    for phrase, tier in phrases:
        if not phrase:
            continue
        outline = tier == "outline"
        if not items:
            items.append(phrase)
            far_said = outline           # the lead says it (`_outline` leads)
        elif outline and not far_said:
            items.append(text("landscape_far", item=phrase))
            far_said = True
        else:
            items.append(text("landscape_then", item=phrase))
    if beside and via:
        if items:
            key = "landscape_line_beside" if compass else "landscape_line_beside_bare"
            return text(key + suffix, compass=compass, beside=beside, via=via,
                        items=sep.join(str(i) for i in items))
        key = "landscape_beside_only" if compass else "landscape_beside_only_bare"
        return text(key + suffix, compass=compass, beside=beside, via=via)
    first_far = bool(rows) and rows[0].get("tier") == "outline" and not beside
    if not items:
        return ""
    far = "_outline" if first_far else ""
    if lead.get("rise") == "below":
        # A memory is the mind's own: "below me", never "below you".
        lead_text = (text("landscape_lead_compass_below" + suffix, compass=compass) if compass
                     else text("landscape_lead_below" + suffix))
    elif via:
        lead_text = (text("landscape_lead_compass_via" + far, compass=compass, via=via) if compass
                     else text("landscape_lead_via" + far, via=via))
    elif compass:
        lead_text = text("landscape_lead_compass" + far, compass=compass)
    else:
        lead_text = text("landscape_lead_outline" if first_far else "landscape_lead_mid")
    return text("landscape_line" + suffix, lead=lead_text,
                items=sep.join(str(i) for i in items))


def render_landscape_line(line, episode=False):
    """A far line in English (`compose_landscape_line`), with the English
    pack's own compass whatever language scope the caller is in."""
    return _cap(str(compose_landscape_line(
        line, _en, episode=episode, thing=_noun_phrase,
        compass_words=dict(_ENGLISH_COMPOSITOR.get("compass_words") or {}))))


def weather_percepts(reach):
    """What the sky is doing, to a body that can tell -- sight and skin.

    `reach` is one `world.weather.weather_for_room(scene, room, subject)`
    answer, which had ALREADY decided every question this needs and was read by
    nobody with a mind. Measured 2026-09-20: `composer.py` contained the word
    "weather" zero times, `perception.py` once in a comment, and
    `agents/character.py` and `agents/common.py` not at all. The record carries
    sky, precipitation, intensity, wind and temperature; the Director gets it,
    `spatial_light` dims a room with it, `spatial_sound_field` adds it to the
    noise floor and `dressing/ambience` paints it. A character standing in a
    freezing thundersnow gale was told that the room was dim and that it was
    loud. Nobody was ever told it was snowing.

    TWO PERCEPTS, BECAUSE THE CHANNELS FAIL SEPARATELY -- the seam's own words:
    "a cellar under a downpour sees nothing, feels nothing and may still HEAR
    it". Sight carries what the sky is doing and is bounded by
    `weather_visible`/`visible_reach`, so from under cover the view says the
    weather is beyond it rather than on it. Skin carries what is actually
    touching this body: `falls_on_you` and `wind_reaches`, plus the temperature
    of the air a body standing in it is breathing. Hearing is NOT here --
    `spatial_sound_field` already folds rain and wind into the soundscape, and a
    second voice for one fact could only disagree with the first -- save the
    one sound of the sky no field holds: its thunder, told after its flash
    (`_storm_percepts`, wave B2).

    Names are reproduced, never interpreted: `sky`, `precipitation`, `wind` and
    `temperature` are authored free text this engine does not own, so they are
    spliced as written. Nothing numeric reaches the page -- an intensity word, a
    `visible_reach` fraction and a `gain` are the engine's bookkeeping, and a
    bystander has no access to any of them.
    """
    reach = reach if isinstance(reach, dict) else {}
    if not reach:
        return []
    out = []
    # WHAT IS FALLING, at the strength the engine holds a word for. `intensity`
    # is a closed engine vocabulary (light|moderate|heavy) rather than a number,
    # and the difference between light and heavy snow is the whole of what a body
    # standing in it has to say about it. Skipped when there is nothing falling
    # for it to qualify.
    falling = ""
    if str(reach.get("precipitation") or "").strip():
        _fall = str(reach["precipitation"]).strip()
        _how = str(reach.get("intensity") or "").strip()
        # MODERATE IS THE UNMARKED CASE AND IS NOT RENDERED. `normalize_weather`
        # returns `intensity: "moderate"` for a precipitation nobody graded, so
        # putting the word on the page states a thing no author said -- the same
        # rule that keeps a derived default out of every other view. Light and
        # heavy are marked, and both are what a body would actually remark on.
        falling = _noun_phrase(
            _en("weather_falling", intensity=_how, what=_fall)
            if _how in ("light", "heavy") else _fall)
    sky = str(reach.get("sky") or "").strip()
    wind = str(reach.get("wind") or "").strip()
    temperature = str(reach.get("temperature") or "").strip()
    # --- What the eyes have. Bounded by the seam, never re-decided here.
    if reach.get("weather_visible"):
        what = falling or (_noun_phrase(sky) if sky else "")
        if what:
            if float(reach.get("visible_reach") or 0.0) < 1.0:
                desc = _cap(_en("weather_beyond", what=what))
            elif falling and sky:
                desc = _cap(_en("weather_overhead", what=what, sky=sky))
            else:
                desc = _cap(_en("weather_overhead_plain", what=what))
            out.append(Percept(
                kind="ambient", channel="sight", data={"desc": desc},
                salience=0.4,
                # The STATE, never the sentence: a sky that holds re-renders as
                # furniture and a sky that turns is news, which is the rule
                # `room_content_percepts` states for this whole family.
                dedupe_key=standing_key(
                    "weather_sight", ("sky",),
                    (sky, str(reach.get("precipitation") or ""),
                     str(reach.get("intensity") or ""),
                     "%.2f" % float(reach.get("visible_reach") or 0.0))),
            ))
    # --- What the skin has. Only what is touching THIS body.
    clauses = []
    if reach.get("falls_on_you") and falling:
        clauses.append(_cap(_en("weather_on_you", what=falling)))
    if reach.get("wind_reaches") and wind:
        clauses.append(_en("weather_wind", wind=wind))
    if temperature and reach.get("exposure") in ("open", "sheltered"):
        clauses.append(_en("weather_air", temperature=temperature))
    for clause in clauses:
        out.append(Percept(
            kind="sensation", channel="touch", source_label="you",
            data={"clause": clause, "directed_at_self": True},
            salience=0.45,
            dedupe_key=standing_key("weather_touch", ("sky",), (clause,)),
        ))
    out.extend(_storm_percepts(reach, sky))
    return out


def _storm_percepts(reach, sky):
    """A SKY THAT FLASHES, AND ITS THUNDER (wave B2, DESIGN_SOUND_FIELD.md
    § 14.3). The `electrical` axis put a flash and a clap into a room for
    the ambience and the screen and into no mind's view at all. Sight
    carries the flash where the sky's weather is in view
    (`weather_visible`); hearing carries the thunder where it reaches
    (`weather.thunder_heard`, the one rule the sound bed reads too). A body
    that has both is told them in the order they arrive: a strike comes
    down from a cloud base a kilometre or two up (`LIGHTNING_M`), so the
    thunder follows the flash by seconds (`sound_after_sight`). Standing:
    said when the storm begins, and again when what this body has of it
    changes."""
    from language_runtime import compositor_text, compositor_value
    from world.spatial import LIGHTNING_M, sound_after_sight
    from world.weather import has_lightning, thunder_heard
    flash = has_lightning(reach) and bool(reach.get("weather_visible"))
    thunder = thunder_heard(reach)
    out = []
    state = (sky, flash, thunder)
    if flash:
        out.append(Percept(
            kind="ambient", channel="sight",
            data={"desc": compositor_text("weather_lightning", sky=sky)
                  if sky else compositor_text("weather_lightning_plain")},
            salience=0.45,
            dedupe_key=standing_key("weather_flash", ("sky",), state)))
    if thunder is not None:
        if flash:
            after = dict(compositor_value("after_sight_words")).get(
                sound_after_sight(LIGHTNING_M) or "seconds", "")
            desc = compositor_text("weather_thunder_after", after=after)
        else:
            desc = compositor_text("weather_thunder_" + (thunder or "open"))
        out.append(Percept(
            kind="ambient", channel="hearing", data={"desc": desc},
            salience=0.45,
            dedupe_key=standing_key("weather_thunder", ("sky",), state)))
    return out


def _weather_sound_heard(reach):
    """`(what, template)` for the precipitation this room hears, or
    `("", "")`: the fall's own name (free text, spliced as written, with
    its intensity where the sky marked one), and the sentence that fits how
    it arrives -- under the sky, on the cover over you, through the walls
    muffled or faint (`weather_for_room`'s `exposure` and `muffling`)."""
    if not reach.get("audible"):
        return "", ""
    what = str(reach.get("precipitation") or "").strip()
    if not what or what.casefold() == "none":
        return "", ""
    how = str(reach.get("intensity") or "").strip()
    exposure = str(reach.get("exposure") or "")
    muffling = str(reach.get("muffling") or "")
    if exposure == "open":
        template = "weather_sound_open"
    elif exposure == "sheltered":
        template = "weather_sound_sheltered"
    else:
        template = "weather_sound_faint" if muffling == "faint" \
            else "weather_sound_muffled"
    # MODERATE IS THE UNMARKED CASE, as in `weather_percepts`; and a name
    # that already carries its intensity word (a record stored before the
    # axes were split: "light snow" at `light`) is not marked twice --
    # measured "the light light snow" on the betrayal story's yard.
    named = _t("weather_falling", intensity=how, what=what) \
        if how in ("light", "heavy") and not what.casefold().startswith(how) \
        else what
    return _noun_phrase(named), template


def _was_hearing(prev_standing, tag, room_id):
    """Was this observer being delivered THIS room's sound under `tag`
    (`WEATHER_SOUND_TAG`, `WIND_SOUND_TAG`) last beat -- the same subject
    test `perception._was_hearing_this_room` makes of the soundscape: the
    key hashes the room as its subject, so a body that walked out of
    earshot holds another room's key and notices no stopping here."""
    if not prev_standing or not room_id:
        return False
    want = standing_key(tag, (room_id,), ("",)).rsplit(":", 1)[0]
    return any(_subject_prefix(key) == want for key in prev_standing)


def weather_sound_percepts(reach, room_id, *, prev_standing=frozenset(),
                           before=None):
    """THE WEATHER'S SOUND, as standing hearing percepts (DESIGN_SOUND_FIELD
    § 17, round 2 lane C): what this body hears of the sky from where it
    stands -- the precipitation that reaches the room (`weather_for_room`'s
    `audible`, at its `muffling`) and a wind at the ear (`wind_reaches`) --
    as two sounds, each keyed like the room's soundscape by its own state
    under the ROOM as subject (`HABITUATING_SOUND_TAGS`): told when it
    starts and when it changes, faded between (`habituated`), and its
    STOPPING told once, by what this observer's own ledger held
    (`prev_standing`, the `ceased` key under the same subject), never to an
    ear that never had it and never to one that walked out of earshot. A
    newcomer hears the room as it is.

    `before` is the room's reach as it stood last beat where the caller has
    it (the outcome pass hands `prev_scene`'s), so the stopping can name
    what fell; without it the record's own name stands -- a sky keeps its
    fall's name through a dry spell (`weather.advance_weather`) -- and
    failing both, the sentence names the class ("the weather").

    TELLING ONLY. The weather's level in the field's floor
    (`spatial_sound_field.WEATHER_NOISE`) is untouched: the owner's rain
    ruling -- rain never masks a line -- stands. Indoors the sound is what
    reaches the room, by the same audibility the sound bed reads
    (`weather_words(scoped, "sound")`), so the page and the ambience cannot
    disagree about whether a cellar hears the storm.
    """
    reach = reach if isinstance(reach, dict) else {}
    before = before if isinstance(before, dict) else {}
    out = []
    if not room_id:
        return out
    what, template = _weather_sound_heard(reach)
    if what:
        out.append(Percept(
            kind="ambient", channel="hearing",
            data={"desc": _cap(_t(template, what=what))},
            salience=0.35,
            dedupe_key=standing_key(
                WEATHER_SOUND_TAG, (room_id,),
                (str(reach.get("precipitation") or ""),
                 str(reach.get("intensity") or ""),
                 str(reach.get("muffling") or ""),
                 str(reach.get("exposure") or "")))))
    elif _was_hearing(prev_standing, WEATHER_SOUND_TAG, room_id):
        # THE RAIN HAS STOPPED -- or no longer reaches this room, which
        # is the honest sentence through a wall. Named from what WAS heard
        # where the caller can say, else from the record's own name.
        name = ""
        for record in (before, reach):
            candidate = str(record.get("precipitation") or "").strip()
            if candidate and candidate.casefold() != "none":
                name = candidate
                break
        if not name:
            desc = _t("weather_sound_ceased_plain")
        elif str(reach.get("exposure") or "") == "enclosed":
            desc = _t("weather_sound_ceased_beyond", what=_noun_phrase(name))
        else:
            desc = _t("weather_sound_ceased", what=_noun_phrase(name))
        out.append(Percept(
            kind="ambient", channel="hearing",
            data={"ceased": True, "desc": _cap(desc)},
            salience=0.4,
            dedupe_key=standing_key(WEATHER_SOUND_TAG, (room_id,),
                                    ("ceased",))))
    wind = str(reach.get("wind") or "").strip()
    if reach.get("wind_reaches") and wind:
        out.append(Percept(
            kind="ambient", channel="hearing",
            data={"desc": _cap(_t("wind_sound", wind=wind))},
            salience=0.35,
            dedupe_key=standing_key(WIND_SOUND_TAG, (room_id,), (wind,))))
    elif _was_hearing(prev_standing, WIND_SOUND_TAG, room_id):
        out.append(Percept(
            kind="ambient", channel="hearing",
            data={"ceased": True, "desc": _cap(_t("wind_sound_ceased"))},
            salience=0.4,
            dedupe_key=standing_key(WIND_SOUND_TAG, (room_id,),
                                    ("ceased",))))
    return out


#: How far a felt shake stands out of a view, by how hard it is felt
#: (`spatial_sound_field.FELT_LEVELS`): a faint tremor is under a room's own
#: salience, a jolt over a pose's.
_FELT_SALIENCE = {"tremor": 0.4, "shudder": 0.55, "jolt": 0.7}


def felt_percepts(rows, *, ground=False, beat=None):
    """WHAT SHOOK THE FLOOR UNDER THIS BODY (`spatial_sound_field.
    felt_vibrations`), on the TOUCH channel: at most one blow -- the beat's
    hardest -- and one steady trembling, each said by how hard it is felt
    and through what the body stands on (`ground` under the sky with no
    floor of its own, else the floor), in the story's own words. Nothing
    else: no source, no direction, no sound -- a body that cannot hear is
    told exactly this.

    A blow is the beat's, so its key carries the beat (`beat`) and it is
    news each time it happens; a steady trembling is standing, said when it
    begins and again only when it changes."""
    from language_runtime import compositor_text, compositor_value
    under = dict(compositor_value("felt_under")).get(
        "ground" if ground else "floor", "")
    out, taken = [], set()
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        word = str(row.get("felt") or "")
        if word not in _FELT_SALIENCE:
            continue
        standing = bool(row.get("standing"))
        if standing in taken:
            continue                    # one blow, one trembling: the hardest
        taken.add(standing)
        clause = compositor_text(("felt_steady_" if standing else "felt_blow_")
                                 + word, under=under)
        out.append(Percept(
            kind="sensation", channel="touch", source_label="you",
            data={"clause": clause, "directed_at_self": True, "felt": word},
            salience=_FELT_SALIENCE[word],
            dedupe_key=standing_key(
                "felt", (row.get("key"),) if standing
                else (row.get("key"), beat), (word, standing))))
    return out


def thing_clause(desc, place=""):
    """One THING standing in the room, as a clause a bystander would say.

    The fourth member of `room_content_percepts`' family and the one its own
    docstring forgot: a crowd, a courier, a posted notice -- and a thing
    somebody set down. Measured 2026-09-20 (two_lives v13, chat frame 2): Sal
    Weatherby laid a copper coin on the taproom counter on beat 8, the commit
    recorded it correctly (`stations: {copper_coin: {at: oak_bar_counter}}`,
    `contained` empty), and the coin appeared in 0 of her 24 composed views.
    On beat 10 her own view named the HOST's coin pouch and not her coin, so
    she drew a second coin from her pocket and paid again. Nothing was wrong
    with the world's record and nothing was wrong with her; she was never told.

    There was no sight path from `scene.entities` to any view at all:
    `feature_visibility` answers for "every ANCHOR of the observer's room",
    and perception's only walk over scene entities on the view path is the
    SCENT loop, gated on `entity.scent`. A thing reached a mind only through
    a channel that owned it for some other reason -- attire, a pose, a
    contact, a smell, or being authored furniture. Nothing said "that is
    lying there".

    `place` is the authored description of the anchor it stands at, already
    admitted by the caller; empty for a thing the room holds without placing,
    which names the thing and CLAIMS NO DISTANCE -- the same subtraction
    `_feature_items(placed=False)` makes for furniture seen through a doorway,
    for the same reason: the distance vocabulary is measured within one room
    and spending it where nothing measured states a distance nobody has.
    """
    desc = _noun_phrase(desc)
    if not desc:
        return ""
    place = _noun_phrase(place)
    return (_en("thing_placed", desc=desc, place=place) if place
            else _en("thing_here", desc=desc))


def thing_in_hand_clause(desc, mode=""):
    """A thing the OBSERVER holds or carries, said as theirs.

    Not `thing_clause`'s "There is ... here": a thing in somebody's hands is
    not lying in the room, and Emory read "There is the tallow tub here" in
    seventeen views while the commit held the tub in his grip (playerless
    Aldermill round 7, 2026-09-23). `held` is in hand; anything else a body
    openly bears is carried."""
    desc = _noun_phrase(desc)
    if not desc:
        return ""
    return _en("thing_held_by_you" if str(mode or "").strip().casefold() == "held"
               else "thing_carried_by_you", desc=desc)


#: State keys another renderer already voices, or that are structure rather
#: than a fact a body can read off a thing. `transit`/`hatch` and their
#: fields render through the doorway the engine derives from them
#: (`common` "the open doors" / "still-sealed hatch"); `posture`, `activity`
#: and `held_items` are a BODY's and `body_state_percept` owns them; the
#: rest are bookkeeping the objects hand writes for the engine, not for an
#: eye. Kept as the complement of what is readable rather than a list of
#: what is: anything the hand writes that is not one of these is a fact the
#: thing shows, whatever the thing turns out to be. `clothing`, `worn_by`,
#: `shed` and `garment` are the engine's own shed-garment record
#: (`commit_attire`, `spatial_containment`): the garment is already its label,
#: and whose it was is not written on it -- rendered, a body reading a shed
#: tank top was told "clothing: yes; worn by: Hinami; shed: yes; garment:
#: fitted tank top" (chat 137 replay, 2026-09-23), and a stranger would learn
#: the owner's name off the cloth. `speed` is a vessel's own pace, which the
#: engine times its journeys by (`spatial_transit.vessel_speed`, 2026-10-21):
#: read off a craft lying at its mooring it would state a motion it is not
#: making ("speed: value 7, unit kn"), and what checking a craft finds -- its
#: engine, its sails, its condition -- is in its own words in the rest of its
#: state.
_UNREADABLE_STATE_KEYS = frozenset({
    "transit", "link", "phase", "hatch", "destination_room", "route_room",
    "eta_seconds", "posture", "activity", "held_items", "zone", "description",
    "proximity", "target", "targets", "kind", "name", "lit", "running",
    "pointed_at", "clothing", "worn_by", "shed", "garment", "speed",
})


def _reading_value(value):
    if isinstance(value, dict):
        parts = [f"{_reading_label(k)} {_reading_value(v)}"
                 for k, v in value.items() if _reading_value(v)]
        return ", ".join(parts)
    if isinstance(value, (list, tuple)):
        return ", ".join(s for s in (_reading_value(v) for v in value) if s)
    if isinstance(value, bool):
        return "yes" if value else "no"
    return " ".join(str(value if value is not None else "").split())


def _reading_label(key):
    return " ".join(str(key or "").replace("_", " ").split())


def thing_reading_text(state):
    """What a thing's own record says about it, as one clinical clause list.

    A THING EXAMINED TELLS YOU WHAT IT IS LIKE. The objects hand writes a
    thing's readings, its harm and its workings into `state` -- the prompt
    has required it since the detail clause, and nothing on the view path
    ever read the dict back: `_visible_things` renders a thing by its
    description and uses `state` only as a placement key. Measured, chat
    152 turns 4337-4338: the Doctor ran his hands over the console for two
    beats "checking what the scar cost her" and was told nothing, because
    the console had no record and, had it one, no renderer would have
    voiced it. The owner's 2026-09-19 ruling names this class -- an
    unanswered read is a bug, and the acceptance bar is that a thing
    examined closely tells you what it is like.

    Free-form on purpose. The keys are the hand's, so a console, a hull, a
    winch and a wound in a wall each carry whatever they have; this layer
    humanises a key, flattens a nested value and joins with semicolons, and
    never decides which keys matter. Empty when the record is silent.
    """
    if not isinstance(state, dict):
        return ""
    clauses = []
    for key, value in state.items():
        label = _reading_label(key)
        if not label or str(key) in _UNREADABLE_STATE_KEYS:
            continue
        text = _reading_value(value)
        if not text:
            continue
        clauses.append(f"{label}: {text}")
    return "; ".join(clauses)


def thing_reading_percepts(rows):
    """Standing readings off things this observer is reading, as
    ``[(label, readings, uid, channel[, asked])]`` -- admission already
    decided by `perception._things_read_by` (hands on it, or standing at its
    own station with light to see by), so a non-reader contributes nothing
    here by construction. ``asked`` marks a thing this observer's own act
    looked at or took into its hands this beat (`asked_this_beat`).

    `ambient`, like the rest of `room_content_percepts`' family: a standing
    fact of the room, re-rendered when it CHANGES and furniture when it does
    not -- the dedupe key is the reading itself, never the sentence."""
    out = []
    for row in rows or []:
        label, readings, uid, channel = row[:4]
        asked = bool(row[4]) if len(row) > 4 else False
        readings = str(readings or "").strip()
        label = _noun_phrase(label)
        if not readings or not label:
            continue
        template = ("thing_reads_touch" if channel == "touch"
                    else "thing_reads_sight")
        desc = _cap(_t(template, label=label, readings=readings))
        # A reading that already ends its sentence keeps its own stop and
        # the template's is dropped ("Tide: ebb, falling.." -- Saltmarsh
        # Crossing's loading slip, 2026-10-11; "。。" in Japanese alike).
        ends = linguistic("agents.common", "_SENTENCE_END_CHARS")
        if len(desc) > 1 and desc[-1] in ends and desc[-2] in ends:
            desc = desc[:-1]
        data = {"desc": desc}
        if asked:
            data["asked"] = True
        out.append(Percept(
            kind="ambient", channel=channel,
            data=data,
            salience=0.5,
            dedupe_key=standing_key("reading", (uid,), (readings,)),
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
            #
            # A THING IN THE OBSERVER'S OWN KEEPING IS TOLD AGAIN WHEREVER IT
            # IS CARRIED. Its row names the room it is kept in (`kept_in`,
            # `perception._visible_things`), and that room is part of WHICH
            # standing fact this is: the plate in a hand in the kitchen and
            # the plate in that hand on the landing are facts of two rooms,
            # as the kitchen's table and the landing's rail are. Keyed on the
            # thing alone it read `unchanged` across every move, and a delta
            # view dropped it for the whole walk: chat 177 told the player
            # "You are holding an empty small plate." and "You are carrying
            # the mug." on turn 12 and never again through turn 21, up the
            # stairs and into the second room, and the next beat gave the
            # dishes a floor and a bed to lie on. A room it has not been kept
            # in is a subject this observer has not held -- first sight, so it
            # is re-told as background beside the rest of the room, never as
            # an event (`leads_the_beat`); within one room it stays furniture,
            # and a change of grip there still re-renders as a change.
            kept_in = str(entry.get("kept_in") or "").strip()
            subject = (key, kept_in) if kept_in else (key,)
            state = entry.get("state")
            if isinstance(state, (list, tuple)) and any(
                    str(v or "").strip() for v in state):
                dedupe = standing_key("content_state", subject,
                                      tuple(str(v or "") for v in state))
            else:
                dedupe = standing_key("content", subject, (desc,))
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


def residue_percepts(level, *, targeted=False, loud_event=False, pain=False,
                     woke=""):
    """A non-awake mind gets the residue and nothing else -- and a sleeper a
    sound woke this beat gets only what woke them (`woke`, one of
    `spatial_listener.WAKING_SOUNDS`; DESIGN_SOUND_FIELD § 13)."""
    data = {"level": level, "targeted": bool(targeted),
            "loud_event": bool(loud_event), "pain": bool(pain),
            "directed_at_self": True}
    if woke:
        data["woke"] = str(woke)
    return [Percept(
        kind="residue", channel="interoception", source_label="you",
        fidelity="trace",
        data=data,
        salience=0.2 if not woke else 0.6,
        dedupe_key=standing_key("residue", (level,),
                                (targeted, loud_event, pain)
                                + ((str(woke),) if woke else ())),
    )]


# --------------------------------------------------------------------------
# Layer A -- event percepts
# --------------------------------------------------------------------------

#: How much one comma-separated part of a manner may hold and still sit inside
#: the manner slot ("in a {tone} voice", 「{tone}を声ににじませ」): an
#: adjective with its adverb and a conjunction ("and highly articulate") --
#: three words in a spaced script, ten characters in an unspaced one -- never
#: a clause.
_MANNER_PART_WORDS = 3
_MANNER_PART_CHARS_UNSPACED = 10


def _fits_the_manner_slot(manner):
    from story.character_schema import _UNSPACED_SCRIPT
    for part in re.split(r"[,、，;；]", str(manner or "")):
        part = part.strip()
        if not part:
            continue
        if " " not in part and _UNSPACED_SCRIPT.search(part):
            if len(part) > _MANNER_PART_CHARS_UNSPACED:
                return False
        elif len(part.split()) > _MANNER_PART_WORDS:
            return False
    return True


def _voice_fields(register, tone, established, can_say=True):
    """The manner a line renders, and what is said of the voice apart from it.

    A VOICE THAT IS A CLAUSE IS ITS OWN SENTENCE. The slot is "in a {tone}
    voice", and a sheet's register -- or a line's own tone -- can be a
    clause: "says in a bright, informal, theatrical, and highly articulate,
    shifting into grave authority without warning voice" (Kirinoura, scratch
    chat 167, 2026-10-05). A register that does not fit
    (`_fits_the_manner_slot`) is `said_apart`, after the line, whole, by
    every pack's `voice_register`."""
    first = bool(register and not established)
    out = {"manner": register if first else tone}
    if first:
        out["voice_first"] = True
        # A REGISTER describes a voice, always; a line's own tone stays in
        # its slot, as it always has -- classifying tones as conduct or voice
        # in two scripts cost more than the one sentence it fixed (review
        # rounds 1-3, 2026-10-05).
        # Said apart only where the slot itself would say it -- a line SEEN
        # and not conducted (`_inject_dialogue` drops the manner otherwise):
        # an unseen line carried no register, and a long one said apart
        # reached a listener in the dark (review round 4, 2026-10-05).
        if not _fits_the_manner_slot(register) and can_say:
            out["said_apart"] = _lower_lead(_strip_sentence_ends(register))
            out["manner"] = ""
    return out


def _can_say_the_voice(p):
    """Whether this line's render says the voice: a full line, said apart
    after it, or in the manner slot of a line seen and not conducted. A
    fragment, an unseen line and a conducted one carry no manner -- a voice
    established on one of them was never said and filed as known all the
    same (review, 2026-10-05). A stranger's voice heard and not seen is
    said after whatever of it arrived (`voice_apart`, § 12 of the sound
    note), so that says it too."""
    d = p.data or {}
    if d.get("voice_apart") and p.fidelity in ("full", "fragment", "voice"):
        return True
    if p.fidelity != "full":
        return False
    if d.get("said_apart"):
        return True
    return bool(d.get("can_see")) and not d.get("conducted")


def _one_voice_each(percepts):
    """`percepts` with each voice established once, in their own order: the
    earliest line a speaker says among them establishes it, and every later
    line from them renders only its own tone. `speech_percept` asks the
    ledger of earlier BEATS, so three lines in one beat each said the voice
    again."""
    percepts = list(percepts or ())
    first = {}
    for i, p in enumerate(percepts):
        d = p.data or {}
        if p.kind == "speech" and d.get("voice_first") and d.get("voice_key") \
                and _can_say_the_voice(p):
            rank = (p.order_key is None, p.order_key or 0, i)
            if d["voice_key"] not in first or rank < first[d["voice_key"]][0]:
                first[d["voice_key"]] = (rank, i)
    keep = {i for _rank, i in first.values()}
    out = []
    for i, p in enumerate(percepts):
        d = p.data or {}
        if p.kind == "speech" and d.get("voice_first") and d.get("voice_key") \
                and d["voice_key"] in first and i not in keep:
            data = {k: v for k, v in d.items()
                    if k not in ("voice_first", "said_apart", "manner",
                                 "voice_apart")}
            data.update(_voice_fields("", data.get("tone", ""), True))
            p = dataclasses.replace(p, data=data)
        out.append(p)
    return out


def speech_percept(entry, rel, observer_name, *, display, can_see,
                   proximity=None, order_key=0, observer_id=None,
                   senses=None, voice="", prev_standing=None, bearing="",
                   addressed=None, name_forms=(), voice_sound=""):
    """Admit one spoken line for one observer, or None.

    A VOICE IS ESTABLISHED ONCE (D2; Wood -- theatre gives a vocal quality
    once). `voice` is the speaker's own register from their sheet
    (`social.voice.register`). The FIRST line this observer hears from that
    body renders the register as its manner and files a `voice:<body>` key
    in the observer's standing ledger; every later line renders a manner
    only where the line's own `tone` names a departure. The declared `tone`
    stays in `data["tone"]` regardless -- what renders is `data["manner"]`.
    `voice_sound` is the card's `embodiment.voice` -- what the voice carries
    to a stranger's ear -- said once, after the line, to a listener who
    hears the body and cannot see it (`voice_apart`), ahead of the register
    (DESIGN_SOUND_FIELD § 18); a seen speaker keeps the register's slot.
    Measured before this: "in a flat, hushed monotone voice, she said" on
    63-98 of 79 lines in one story and 6 of 7 on the descent copy, because a
    speaker's ordinary voice was re-declared as tone on every line and the
    view had no notion of a voice already known. Tone strings are never
    compared: the ledger decides, not the wording.

    Gates, in order: concealment (absolute exclusion, never a volume),
    audibility (`line_hear_level`, including the comm/addressed rescue, and
    the ear rung, which reaches only the line's addressee: `addressed`, or
    the line's own targets when None -- `line_addressed`).
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
    # WHICH RELATION DECIDED, AND WHY. `act_percept` records every refusal
    # and delivery; this function recorded nothing, and the cost was
    # measured: a shout three rooms up a stone tower arrived verbatim on four
    # beats while every deterministic reader replayed on the committed scene
    # answered `fragment` or `none`, and nothing persisted which of the two
    # rescues had fired (lighthouse, 2026-09-05, PA4 -- docs/UNBUILT.md
    # § 1.121). Two paths can promote an unheard line to a full verbatim
    # quotation and they have different premises, so an attribution has to
    # say which one. Same shape as `act_percept`: no-op when debug capture is
    # off, one ContextVar read.
    _who = "%s -> %s" % (str(entry.get("speaker") or "?"), observer_name)
    if addressed is None:
        addressed = line_addressed(entry, observer_name, observer_id)
    _spatial = line_hear_level(entry, rel, observer_name, proximity=proximity,
                               senses=senses, seen=bool(can_see),
                               addressed=addressed)
    level = _spatial
    _how = "spatial"
    if isinstance(rel.get("comm_channel"), dict) and level != "none":
        _how = "comm channel"
    elif level == "full" and _sense_graded(
            hear_level(rel, volume, proximity=proximity,
                       level_db=entry.get("level_db"), seen=bool(can_see),
                       addressed=addressed),
            "hearing", senses) == "none":
        # `line_hear_level` already applied the addressed rescue; naming it
        # here is a report of what happened inside it, not a second copy of
        # the rule.
        _how = "addressed rescue (named across a barrier)"
    if level == "none" and rel.get("open_group_continuity") \
            and volume.casefold() in ("normal", "loud", "shout"):
        # Compatibility floor for a rerolled checkpoint predating the
        # near-group position repair. It grants hearing only; sight and every
        # other channel still ride the relation's real spatial fields. (The
        # onset prose path carried the twin of this rescue and has since been
        # deleted, so this is the only copy.)
        level = "full"
        _how = "open-group continuity floor (pre-repair checkpoint)"
    # WHY, in the hearing rule's own words, where a line is short of whole
    # (`spatial_senses.hearing_reason`): appended, so a reader of the older
    # notes -- `tools/speech_replay.py` parses the prefix -- reads them alike.
    _why = hearing_reason(rel, volume, proximity=proximity,
                          level_db=entry.get("level_db"),
                          seen=bool(can_see),
                          addressed=addressed) if level != "full" else ""
    if _why == "into_another_ear" and not _line_refs(entry):
        # A line breathed into an ear that names NO ear reaches nobody at
        # all -- its own listener included -- and says so here, so the
        # missing target is found where the line went missing.
        _why = "ear_names_no_one"
    # THE VOICE, WHERE NONE OF ITS WORDS ARRIVE (DESIGN_SOUND_FIELD § 12).
    # A listener hears THAT someone spoke, how loudly and in what tone some
    # ten decibels under the last word they could have caught: raised
    # voices through a wall, a laugh through a door, a far table's talk in a
    # tavern's din (`spatial_senses.voice_carries`). Words and names are not
    # carried by it: the percept holds no body and no fragment, and its
    # label is a name only where the listener knows the voice.
    _voice_only = (level == "none"
                   and sense_acuity_offset(senses, "hearing") is not None
                   and voice_carries(rel, volume, proximity=proximity,
                                     level_db=entry.get("level_db"),
                                     seen=bool(can_see),
                                     addressed=addressed))
    note_step_decision(
        "speech_percept", _who,
        "refused" if level == "none" and not _voice_only else "delivered",
        "%s via %s; volume %s, barrier %s, tier %s%s" % (
            "voice" if _voice_only else level, _how, volume,
            str(rel.get("barrier") or "none"),
            str(proximity or rel.get("tier") or "unmeasured"),
            ("; " + _why) if _why else ""))
    if level == "trace":
        # DETECTED, AND NOTHING MORE (`spatial_senses.HEARING_LEVELS`): the
        # rung a sense card reaches from `none` or falls to from `fragment`
        # carries no words and no identity. It fell through to the full
        # branch below, so an extraordinary ear behind a wall was handed the
        # line verbatim under "the unfamiliar person" -- the wiretap the
        # rung exists to refuse.
        return _trace_percept(entry, bearing=bearing, order_key=order_key)
    if level == "none" and not _voice_only:
        # SEEN SPEAKING, UNHEARD. A line the noise takes whole is still an
        # act the eyes have: a body within reach turns its head to yours
        # and its mouth moves. Refusing the WORDS is the firewall doing its
        # job; refusing that anything was said at all is a wrong scene.
        # Measured (scratch play 2026-09-14, chat 2 turns 2-3): on a deck
        # a "loud" engine graded drowned, a woman sat against a man's
        # sleeve and spoke at his ear, twice, and his view carried nothing
        # -- so his mind answered as if she had never spoken, and the
        # narrator wrote "He gave no reply". Delivered as the fragment
        # percept with the pack's indistinct marker and no words, so
        # `_scrub_invented_dialogue` has nothing to check and nothing can
        # leak: what reaches the observer is only that speech happened.
        if can_see and str(proximity or rel.get("tier") or "") in (
                "within_reach", "near"):
            note_step_decision(
                "speech_percept", _who, "delivered",
                "seen speaking, unheard: the words did not carry but the "
                "speaker is in sight within reach")
            return Percept(
                kind="speech", channel="sight", source_label=display,
                fidelity="fragment",
                data={"level": "none", "volume": volume, "can_see": True,
                      "attributed": bool(str(display or "").strip()),
                      "fragment": _muffled_fragment(""),
                      "tone": "", "manner": "",
                      "directed_at_self": _addresses(
                          entry.get("intended_target"), observer_name)},
                salience=0.5, order_key=order_key)
        return None
    channel = rel.get("comm_channel")
    tone = str(entry.get("tone") or "").strip()
    affect = typed_affect(entry)
    # A register is AUTHORED sheet text and arrives as a sentence ("Clinical,
    # deadpan, and strictly monotone.") where a tone is a phrase; splice it
    # as the manner slot expects, or the page reads "in a Clinical, deadpan,
    # and strictly monotone voice" (descent copy, beat 119).
    register = _lower_lead(_strip_sentence_ends(voice))
    # The voice's SOUND (`embodiment.voice`), said whole after a line heard
    # unseen -- never spliced into the manner slot, which is the register's.
    sound = _lower_lead(_strip_sentence_ends(voice_sound))
    # Keyed on the sheet's OWN text, not the spliced rendering: the key names
    # the voice, and a change to how the manner is worded must not make a
    # known voice new again (measured: one renderer change between two
    # beats re-established Sarah's voice on the descent copy, beat 120).
    # The sound is part of the key only where a card has one, so a card
    # without it keys exactly as it did before the field existed.
    voice_key = standing_key(
        "voice", (body_key(str(entry.get("speaker") or "")),),
        (str(voice or "").strip(),)
        + ((str(voice_sound or "").strip(),) if sound else ())) \
        if register or sound else ""
    established = bool(voice_key) and voice_key in (prev_standing or ())
    data = {
        "level": level,
        "volume": volume,
        "can_see": bool(can_see),
        "conducted": bool(rel.get("inside_source")),
        "tone": tone,
        **_voice_fields(register, tone, established,
                        can_say=bool(can_see) and not rel.get("inside_source")),
        **({"voice_key": voice_key} if voice_key else {}),
        "articulation": str(entry.get("articulation") or ""),
        "directed_at_self": _addresses(
            entry.get("intended_target"), observer_name),
    }
    _speaker = str(entry.get("speaker") or "").strip()
    _label = str(display or "").strip()
    _knows_the_voice = bool(
        _speaker and _label.casefold() == _speaker.casefold())
    # A STRANGER'S VOICE IS DESCRIBED BY WHAT A VOICE CARRIES (§ 12): a
    # listener who cannot see the speaker and does not know the voice is
    # given the card's own account of the voice's sound (`embodiment.voice`,
    # § 18: what a body is recognised by when it speaks unseen) and, where
    # the card has none, the speaker's register -- "low contralto, warm and
    # unhurried" -- said once after the line, as a seen line says it in its
    # manner slot; never a name (`_voice_sound_heard_unseen`,
    # `_register_heard_unseen`). Over a live channel too, and through a
    # body's mass the voice is the mass's, so not there.
    _unseen_register = _voice_sound_heard_unseen(sound, _speaker) \
        or _register_heard_unseen(register, _speaker)
    if voice_key and not established and not can_see \
            and not _knows_the_voice and not rel.get("inside_source") \
            and _unseen_register:
        data["voice_apart"] = _unseen_register
    if level == "none":
        # The voice only: whose it is where it is known or seen, how loud
        # (`volume`), the feeling it carries (`_voice_feeling`) -- no words.
        data["level"] = "voice"
        data["attributed"] = bool(_label) and (bool(can_see)
                                               or _knows_the_voice)
        data.update(_voice_feeling(affect, tone, body))
        data.pop("manner", None)
        fidelity = "voice"
    elif level == "fragment":
        data["fragment"] = _muffled_fragment(body)
        data.update(_voice_feeling(affect, tone, body))
        # WHO SPOKE IS SIGHT'S ANSWER, NOT HEARING'S. A line degraded by
        # distance or noise loses its WORDS, never its speaker, when the
        # observer can see who spoke: hearing less of a sentence is not the
        # same as not knowing who said it, and the two are separate channels.
        # Live (PD3), turn 20: Sable's view rendered her own employer, three
        # paces in front of her in daylight and described in full by the same
        # view, as "A muffled voice: ...milestone... ferryman... business...".
        # A percept whose source is stripped does not stay stripped -- the
        # mind fills it, the narrator sited it at a gatehouse, and the
        # invention was filed as memory. Anonymity is for a speaker the
        # observer cannot place.
        # A VOICE YOU KNOW IDENTIFIES ITS OWNER, SEEN OR NOT. This gated
        # attribution on SIGHT, so a line from a body standing behind you --
        # or across a dark room, or through a door -- arrived anonymous
        # however well you know them, which is not how ears work. Recognition
        # is the question, and `display` already answers it: this label comes
        # from `observer_display_map`, which returns a recognised body's OWN
        # NAME and a stranger a descriptor, and which applies
        # `disguise_breaks_recognition` on the way -- so a disguise that means
        # to conceal who someone is takes their voice with it, and one that
        # only hides features does not.
        #
        # RESIDUAL, registered rather than invented: a voice-only disguise --
        # ordinary appearance, deliberately altered voice -- has no field to
        # be authored in. It is a real thing a body does and the engine
        # cannot yet say it.
        data["attributed"] = bool(_label) and (bool(can_see)
                                               or _knows_the_voice)
        fidelity = "fragment"
    else:
        data["body"] = body
        fidelity = "full"
    # YOUR OWN NAME CATCHES YOUR EAR (DESIGN_SOUND_FIELD § 13, wave B1). One's
    # own name is detected at lower signal levels than other words, and out
    # of a din or a conversation one is not following -- the cocktail-party
    # effect (Moray 1959; Wood & Cowan 1995). So where this listener has
    # only pieces of a line, or its voice without words, and the line holds
    # a name others call them by (`name_forms`, `own_name_forms`), they know
    # their name was said: the percept carries THAT, never which form of
    # it, never another word of the line, never who. A line whose voice
    # did not reach them at all carries no name either.
    if fidelity in ("fragment", "voice") and name_forms \
            and own_name_said(body, name_forms):
        data["own_name"] = True
    # WHICH channel carried it, when one did. Not decoration: a voice arriving
    # over a speaker is a different fact from a voice arriving from a body in
    # the room, and a mind handed the second when the first is true has been
    # told the speaker is present. The renderer says so and the observation
    # carries it, so nothing downstream can quietly lose the distinction.
    if isinstance(channel, dict) and not rel.get("same_room"):
        data["via"] = str(channel.get("name") or channel.get("id") or "")
        data["via_channel"] = str(channel.get("id") or "")
    # WHERE AN UNSEEN VOICE CAME FROM, in the listener's own frame (the
    # caller's `sound_bearing` phrase, which names no room and no body). The
    # same fact a route is: a voice through the doorway on your right and a
    # voice in the room with you are different things, and a view that drops
    # it has told the reader the speaker is standing here. Found in play on
    # 2026-10-06 (scratch story 165, turn 4581): the market's reeve answered a
    # shout through the inn's door, the view said only "You hear a voice
    # say", and the narrator put him "on the far side of the room" -- where
    # the player turned to question nobody.
    if bearing and "via" not in data:
        data["bearing"] = str(bearing)
    return Percept(
        kind="speech", channel="hearing", source_label=display,
        fidelity=fidelity, data=data,
        salience=(0.75 if volume in ("loud", "shout") else 0.7)
        if fidelity != "voice" else 0.5,
        suddenness=0.5 if volume in ("loud", "shout") else 0.1,
        order_key=order_key,
        # ONE VOICE, ONE SENTENCE: a speaker whose words did not carry is
        # heard as a voice once a beat, however many lines they said.
        dedupe_key=("speech-voice:" + _short_hash(entry.get("speaker"))
                    if fidelity == "voice"
                    else "speech:" + _short_hash(entry.get("speaker"), body)),
    )


def _trace_percept(entry, *, bearing="", order_key=0):
    """A voice DETECTED and no more (`spatial_senses.HEARING_LEVELS`'
    `trace`): no words, no speaker, no tone -- direction at best. What the
    interaction loop already renders as `loop_faint_sound`, as a view
    percept."""
    return Percept(
        kind="speech", channel="hearing", source_label="",
        fidelity="trace",
        data={"level": "trace", "bearing": str(bearing or ""),
              "directed_at_self": False},
        salience=0.3, order_key=order_key,
        dedupe_key="speech-trace:" + _short_hash(entry.get("speaker")))


def typed_affect(entry):
    """The `VOCAL_AFFECTS` member a dialogue entry carries in `vocal_affect`,
    or "" (a record carrying none -- every line recorded before the field,
    and any value outside the set)."""
    from llm.schemas import normalize_vocal_affect
    return normalize_vocal_affect((entry or {}).get("vocal_affect"))


def _voice_feeling(affect, tone, words):
    """What a voice carries of its feeling where its words do not all come
    through, as percept data: the TYPED affect where the record has one
    (`vocal_affect`, DESIGN_SOUND_FIELD § 15 -- a closed set the engine
    owns, rendered through each pack's `vocal_affects`), else the one-word
    tone floor over the line's free-text `tone` (`_carried_tone`), so a line
    recorded before the field renders exactly as it did. `neutral` is an
    affect: the prose gave the voice no feeling, and the free text behind it
    is not read."""
    if affect:
        return {"vocal_affect": affect}
    return {"tone_heard": _carried_tone(tone, words)}


def _affect_word(data):
    """The English pack's word for a percept's typed affect, or "" -- an enum
    key mapped through the pack, never printed raw; a pack may leave a member
    unsaid (`neutral`)."""
    affect = str((data or {}).get("vocal_affect") or "").strip()
    if not affect:
        return ""
    return str((_ENGLISH_COMPOSITOR.get("vocal_affects") or {}).get(affect) or "")


def _feeling_heard(data):
    """The tone word a renderer says after a line heard in pieces or as a
    voice alone: the typed affect's word, else the carried tone."""
    if (data or {}).get("vocal_affect"):
        return _affect_word(data)
    return str((data or {}).get("tone_heard") or "").strip()


#: Where a tone's first part ends: a clause separator in a spaced or an
#: unspaced script. Structure, not words.
_TONE_PART_END = re.compile(r"\s+-{1,2}\s+|[,;:()/—–、，；：（]")
#: What no voice quality contains: a digit, a quotation mark.
_TONE_NOT_A_QUALITY = re.compile(r"[0-9\"“”「」『』]")


def _carried_tone(tone, words):
    """The part of a line's declared `tone` an ear takes in with the voice
    when its words do not come through, or "".

    TONE IS A CHANNEL; WORDS AND NAMES ARE NOT (the firewall's half of § 12).
    A tone is free prose the speaker's own model wrote -- "furious", "warm,
    unhurried, with a small genuine laugh at the clay figure", "leaning
    forward slightly", "brisk, reassuring, the mechanic reporting" -- and
    what crosses a wall with a voice is its colour, never what it was about.
    So only the tone's first part is carried, and only when it is shaped
    like a voice quality: ONE word in a spaced script ("furious", "warm",
    "low" -- a phrase is where what the voice did ends and what the body
    did, "murmured against skin", or what the line was, "whispered
    command", begins), short enough for the manner slot in an unspaced one
    (`_fits_the_manner_slot`); no digit or quotation, no capital after its
    first letter (a name), not a conduct the pack's tone reader already
    calls one (`tone_behavior_words`, what the eye takes in), and no word
    of the line itself. Anything else is withheld whole: a tone lost is a
    sentence shorter, a tone that leaks carries the words the wall kept.
    Deterministic and subtractive; a guard, listed for the owner."""
    from story.character_schema import _UNSPACED_SCRIPT
    raw = _strip_sentence_ends(
        _TONE_PART_END.split(str(tone or "").strip(), 1)[0].strip())
    if not raw or not _fits_the_manner_slot(raw) \
            or _TONE_NOT_A_QUALITY.search(raw) \
            or any(ch.isupper() for ch in raw[1:]) \
            or (not _UNSPACED_SCRIPT.search(raw) and len(raw.split()) != 1):
        return ""
    head = _lower_lead(raw)
    tokens = _tone_words(head)
    if tokens & _pack_words("tone_behavior_words"):
        return ""
    if tokens & _tone_words(words):
        return ""
    return head


def _register_heard_unseen(register, speaker):
    """The speaker's register as it may be said to a listener who can
    neither see them nor knows their voice, or "".

    Review round 4 (2026-10-05) refused every register to a listener in the
    dark, for two reasons that stay true: sheet text can NAME the body it
    belongs to, and a register that is a clause is prose about anything.
    So only a register shaped like a voice quality -- every part of it fits
    the manner slot (`_fits_the_manner_slot`), as "low contralto, warm and
    unhurried" does and "the voice of someone who has smoked for years"
    does not -- holding no word of the speaker's own name
    (`common._identity_token_set`). Anything else is withheld whole: the
    listener has "a voice", as before."""
    register = str(register or "").strip()
    if not register or not _fits_the_manner_slot(register):
        return ""
    return "" if _names_the_speaker(register, speaker) else register


def _voice_sound_heard_unseen(sound, speaker):
    """The card's account of the voice's sound (`embodiment.voice`) as it
    may be said to a listener who can neither see the speaker nor knows
    the voice, or "".

    The NAME GUARD is the register's (`_names_the_speaker`): sheet text can
    name the body it belongs to, and a name is the one thing a voice in the
    dark must not hand over -- that is the firewall's floor, so it stays
    code. The register's SHAPE floor (`_fits_the_manner_slot`) is not
    applied: that floor exists because a register is authored for the
    manner slot and a clause there is prose about anything, where this
    field is authored FOR this sentence -- "The voice is {sound}." -- and a
    sound like "a woman's, past fifty, with the clipped vowels of the
    coast" is exactly what it is for, and four words to a part. A guard
    that fires on the field's own valid output is cut before it is built
    (the owner, 2026-09-06)."""
    sound = str(sound or "").strip()
    if not sound or _names_the_speaker(sound, speaker):
        return ""
    return sound


def _names_the_speaker(text, speaker):
    """Does this sheet text hold a word of the speaker's own name
    (`common._identity_token_set`)? Review round 4's first reason
    (2026-10-05), shared by every account of a voice said in the dark."""
    from story.character_schema import _UNSPACED_SCRIPT
    folded = str(text or "").casefold()
    for token in _identity_token_set(speaker):
        if len(token) >= (1 if _UNSPACED_SCRIPT.search(token) else 3) \
                and token in folded:
            return True
    return False


def own_name_forms(name, aliases=()):
    """THE NAMES OTHERS CALL THIS BODY BY, for `speech_percept`'s own-name
    rescue: its name; the name without a leading article ("The Doctor" is
    called "Doctor"); every word of the name substantial enough to be called
    alone -- a given name, a surname (`common.self_name_forms`, the rule the
    views already use for a body's own name); and its card's aliases.

    Never an engine handle -- a uid, a `character:<id>` -- and never a
    descriptor the engine coined ("the apprentice"): those are not what a
    voice across a room says. A Latin form under three letters is dropped,
    as name-learning drops it (`commit_common._address_forms`): "Al" is
    inside too much English to be a name heard through a wall."""
    from story.character_schema import _UNSPACED_SCRIPT
    base = [str(name or "").strip()]
    base += [str(a or "").strip() for a in (aliases or ())]
    forms = []
    for form in self_name_forms(base[0], [b for b in base if b]):
        forms.append(form)
        for article in ("the ", "a ", "an "):
            if form.casefold().startswith(article) and len(form) > len(article):
                forms.append(form[len(article):].strip())
    out, seen = [], set()
    for form in forms:
        text = str(form or "").strip()
        if not text or text.casefold() in seen:
            continue
        if any(ch in text for ch in "_:/") or any(ch.isdigit() for ch in text):
            continue
        if not _UNSPACED_SCRIPT.search(text) and len(text) < 3:
            continue
        seen.add(text.casefold())
        out.append(text)
    return out


def own_name_said(text, forms) -> bool:
    """Is one of `forms` spoken in `text`, as a whole name? The name-learning
    reader's own rule (`commit_common._form_in`): a name boundary in
    whatever script the name is written, case-insensitive for a distinctive
    name and case-SENSITIVE for one that is also an ordinary word (the
    pack's `_COMMON_WORD_NAMES`: "Will", "Hope", "Data")."""
    from story.character_schema import name_boundary_regex
    body = str(text or "")
    if not body:
        return False
    common_word_names = linguistic("agents.common", "_COMMON_WORD_NAMES")
    for form in forms or ():
        form = str(form or "").strip()
        if not form:
            continue
        flags = 0 if form.casefold() in common_word_names else re.I
        if name_boundary_regex(form, flags).search(body):
            return True
    return False


def _names_kept(percepts):
    """ONE VOICE A BEAT, AND THE NAME IN IT KEPT. Every voice-only line of
    one speaker shares a dedupe key (`speech-voice:`), and the renderers say
    the first; a name caught in a later line of the same speaker would be
    lost with it. So the earliest of each such group carries the group's
    `own_name`. A copy, never the caller's percept."""
    percepts = list(percepts or ())
    named = {p.dedupe_key for p in percepts
             if p.kind == "speech" and p.fidelity == "voice"
             and (p.data or {}).get("own_name")}
    if not named:
        return percepts
    out, done = [], set()
    ranked = sorted(range(len(percepts)), key=lambda i: (
        percepts[i].order_key is None, percepts[i].order_key or 0, i))
    first = {}
    for i in ranked:
        p = percepts[i]
        if p.kind == "speech" and p.fidelity == "voice" \
                and p.dedupe_key in named and p.dedupe_key not in first:
            first[p.dedupe_key] = i
    for i, p in enumerate(percepts):
        if first.get(p.dedupe_key) == i and p.dedupe_key not in done:
            done.add(p.dedupe_key)
            if not (p.data or {}).get("own_name"):
                p = dataclasses.replace(p, data={**(p.data or {}),
                                                 "own_name": True})
        out.append(p)
    return out


def _tone_words(text):
    """The content words of a phrase, casefolded, for `_carried_tone`'s
    no-word-of-the-line test: letter runs of four or more in a spaced
    script (so "ledger-obsessed" holds "ledger"), every content run in an
    unspaced one (`common._muffle_tokens`' own reading of such a script)."""
    from story.character_schema import _UNSPACED_SCRIPT
    text = str(text or "")
    if _UNSPACED_SCRIPT.search(text):
        runs, _keep = _muffle_tokens(text)
        return {r.casefold() for r in runs if r}
    return {w.casefold() for w in re.findall(r"[^\W\d_]+", text)
            if len(w) >= 4}


def silence_percept(display, *, order_key=0):
    """THE UNANSWERED ADDRESS, as a fact (D6, review 2026-09-07).

    A line spoken to somebody who says nothing back is an event: it is the
    whole of subtext, and every stage the engine has was silent about it,
    so the page either invented "no answer came" about a body that had in
    fact answered elsewhere, or -- more often -- let the beat pass as though
    the addressee had not been spoken to. It has no percept anywhere because
    perception is built out of what ARRIVED, and nothing arrives.

    It states the fact and never the reason. "T says nothing" is what the
    addresser has: they spoke to T, T could hear it, and no voice of T's
    reached them. Whether T refused, was thinking, did not care or answered
    somebody else is not in this percept and must not be read out of it --
    that is exactly the inference the beat is FOR.

    It is a hearing percept because it is a fact about the hearing channel:
    it belongs to the person who was listening for an answer, and the caller
    (`perception._outcome_event_stream`) mints one only into the view of the
    observer who did the addressing.
    """
    label = str(display or "").strip()
    if not label:
        return None
    return Percept(
        kind="speech", channel="hearing", source_label=label,
        fidelity="silence", data={"silence": True},
        salience=0.5, order_key=order_key,
        dedupe_key="speech:silence:" + _short_hash(label, str(order_key)),
    )


def communication_percept(entry, rel, observer_name, *, display, can_see,
                           proximity=None, order_key=0, observer_id=None,
                           senses=None, addressed=None):
    """Admit described communication without manufacturing a quotation.
    The ear rung reaches only its addressee here too (`line_hear_level`)."""
    if concealed_from_observer(entry, observer_name, observer_id):
        return None
    from .common import communication_surface
    surface = communication_surface(entry)
    if not surface:
        return None
    volume = str(entry.get("volume") or "normal")
    if addressed is None:
        addressed = line_addressed(entry, observer_name, observer_id)
    level = line_hear_level(entry, rel, observer_name, proximity=proximity,
                            senses=senses, seen=bool(can_see),
                            addressed=addressed)
    if level == "none":
        return None
    if level == "trace":
        # Detected and nothing more: not even who (`_trace_percept`).
        return _trace_percept(entry, order_key=order_key)
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


def _peel_own_name(surface, actor_name):
    """An act's surface with its actor's own leading name words removed.

    Whoever renders the act names the actor -- by the observer's label for
    it -- so a surface that opens with the actor's own name carries a second
    subject, and for a stranger that subject is a name no channel delivered.
    The renderer peels only the words of the LABEL, which for a stranger is
    a descriptor, so "Godidric plants his boots" read as an independent
    sentence and reached a mind that had never learned the name (playerless
    Aldermill round 3, 2026-09-23, t13 and t23: a charter voice writes its
    act about itself in the third person). A possessive is not peeled -- the
    predicate after it has its own subject ("Godidric's hands grip") -- and a
    surface that is nothing but the name is left alone."""
    if not surface or not actor_name:
        return surface
    own = {w.casefold() for w in str(actor_name).split() if w}
    words = surface.split()
    peeled = 0
    while peeled < len(words):
        word = words[peeled].strip(".,;:").casefold()
        if word not in own:
            break
        peeled += 1
    if not peeled or peeled == len(words):
        return surface
    return " ".join(words[peeled:])


def act_percept(scene, event, observer_name, actor_name, rel, *,
                display, can_see, self_forms=None, self_pronouns=None,
                other_forms=None,
                order_key=0,
                observer_id=None, surface=None, sight="full",
                sound=None, gait=None, own_sound=False):
    """Admit one action element's observable surface for one observer, or
    None. Gates: concealment, rear arc, sight (an action is visible or it is
    nothing -- a touch-only source contributes sensation percepts instead,
    never an event surface).

    `sight` is the GRADE, not a second boolean: "full" admits the observable
    surface, "shapes" admits a motion percept that names no object and no
    detail, "none" refuses. Every grader upstream already answers in those
    three words and this channel used to spend the answer as true/false --
    live (PC1), a shape-in-a-doorway budget bought "opens a black notebook on
    her knee" through a locked door, in the same beat the dialogue gate
    honoured the same wall.

    What reaches the rear arc is a SOUND, and three arguments say what it
    is: `sound` is the observer's sound field for `scene` (None where the
    room carries no geometry), `gait` the actor's gait where the beat walked
    them (`TREAD_GAITS`; a walk otherwise), and `own_sound` whether the act
    filed a sound event of its own this beat.
    """
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
    surface = _peel_own_name(str(surface or "").strip(), actor_name)
    if not surface:
        note_step_decision("act_percept", _who, "refused",
                           "no observable surface -- a mental beat")
        return None                       # a mental beat is imperceptible
    if entity_arc(scene, observer_name, actor_name) == "rear":
        # WHAT IS BEHIND YOU IS NOT SEEN, AND IT IS STILL HEARD. `entity_arc`
        # has always promised exactly this -- "no new visual detail from
        # them ... though sound still carries" -- and nothing carried it,
        # because an act reached an observer on the SIGHT channel alone. So
        # five bodies at one anchor split into the two facing the actor, who
        # got the beat, and three facing away, who acted as if it had not
        # happened (multitude, 2026-09-05, PM5).
        #
        # What crosses is that SOMETHING MOVED, and where -- never who, and
        # never what they were doing. A footstep does not carry an identity
        # and a hand's shape does not carry at all, so the surface is
        # dropped whole and the label with it; `sound_bearing` supplies the
        # observer's own egocentric sector where the geometry supports one
        # and nothing when it does not, and it is firewall-clean by
        # construction (it names no room and no body).
        #
        # ...AND ONLY WHERE ITS SOUND REACHES THE EAR (2026-10-21). An act
        # that filed a sound event of its own is heard AS THAT SOUND -- the
        # beat's sound channel tells it -- and is not told a second time as
        # movement. Any other act sounds no louder than the body's own tread
        # (`movement_heard_at_ear`), graded against the noise at this
        # observer's ear: heard a few paces off in a quiet room, not in a
        # crowd's din. Measured on the tavern probe (2026-10-20, chat 2 idx
        # 3-5): a barman's rag along his own bar, his steps round to a
        # barrel and a woman lifting her cup reached three listeners in a
        # 68 dB taproom as "Something moves ..." seven times in three beats,
        # where a walk's tread arrives at 28-32 dB. Without a field (a room
        # with no geometry) the percept stands as it was -- but for a gait
        # that makes no tread where it walks, which is heard nowhere.
        if own_sound:
            note_step_decision("act_percept", _who, "refused",
                               "actor is in the observer's rear arc, and "
                               "the act filed its own sound -- it is told "
                               "as that sound, not twice")
            return None
        if movement_heard_at_ear(scene, observer_name, sound, actor_name,
                                 gait=gait or "walk") == "none":
            note_step_decision("act_percept", _who, "refused",
                               "actor is in the observer's rear arc, and a "
                               "body's movement makes no sound that carries "
                               "over the noise at the observer's ear")
            return None
        note_step_decision("act_percept", _who, "delivered",
                           "actor is in the observer's rear arc -- heard, "
                           "not seen, and not identified")
        return Percept(
            kind="act", channel="hearing", source_label="",
            fidelity="shapes",
            data={"motion": True, "unseen": True,
                  **({"bearing": _bearing}
                     if (_bearing := _sound_bearing_phrase(
                         scene, observer_name, actor_name)) else {})},
            salience=0.4, suddenness=0.3, order_key=order_key,
            # ONE "SOMETHING MOVES" PER BODY PER BEAT: three unseen acts by
            # one body behind you are one fact, not three lines (Hollin
            # Mill turn 11, 2026-09-15, "Something moves behind you." x3).
            dedupe_key="act-heard:" + _short_hash(actor_name))
    if not can_see or sight == "none":
        note_step_decision("act_percept", _who, "refused",
                           "observer cannot see (sight gate)")
        return None
    if sight == "shapes":
        # A body moving, and nothing about what it is doing. The label is
        # whatever identity the caller already earned -- who this is was
        # decided upstream and is not this grade's question.
        #
        # WHERE it moves is the observer's to have when the body stands in a
        # DIFFERENT room. The unseen sibling above already carries its
        # bearing; this branch carried nothing, so a figure seen through an
        # open doorway arrived as a placeless "moves, too little of it to
        # make out" and the narrator put it in the observer's own room.
        # Measured (chat 151 turns 9-10, 2026-09-21): Gushiga Toriki standing
        # on the Moonlit Beach, rendered as "whatever else is in here with
        # you" inside the TARDIS console room. Naming the room opens no
        # channel -- it is the room the observer is already looking into, and
        # `_visible_room_label` is this module's existing answer for a body
        # seen from another one.
        note_step_decision("act_percept", _who, "delivered",
                           "shapes only -- motion without conduct")
        _act_room = ("" if room_of(scene, actor_name)
                     == room_of(scene, observer_name)
                     else _visible_room_label(scene, actor_name))
        return Percept(
            kind="act", channel="sight", source_label=display,
            fidelity="shapes",
            data={"motion": True,
                  **({"room": _act_room} if _act_room else {})},
            salience=0.5, suddenness=0.2, order_key=order_key,
            dedupe_key="act-shapes:" + _short_hash(
                event.get("event_id") or "", actor_name))
    note_step_decision("act_percept", _who, "delivered", surface[:120])
    targets_self = any(
        same_subject(scene, target, observer_name)
        or str(target or "").strip().casefold() in {
            str(form or "").strip().casefold() for form in self_forms or ()}
        for target in event.get("targets") or ())
    # THE SAME REWRITE INTO THE OBSERVER'S OWN FIRST PERSON, for its memory
    # of the beat (`_said_as_mine`): the third person still says whether the
    # observer's name is the subject of its clause, and the second person
    # does not.
    mine = surface
    if targets_self and self_forms and self_pronouns:
        surface = _action_target_second_person(
            surface, self_forms, self_pronouns, other_forms)
        mine = _action_target_second_person(
            mine, self_forms, self_pronouns, other_forms, owner="my")
    if self_forms:
        surface = _self_second_person(surface, self_forms)
        mine = _self_first_person(mine, self_forms)
    mine = _mine_if_it_matters(mine, surface) if self_forms else ""
    return Percept(
        kind="act", channel="sight", source_label=display,
        data={"surface": surface,
              **({"surface_mine": mine} if mine else {}),
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
    # How a body CARRIES itself this beat -- its surface demeanor -- sits
    # with the body's arrangement and description, before the observer's
    # own state (D1).
    "demeanor": 4,
    "body_state": 5, "sensation": 6, "body_part": 7, "body_region": 8,
    # The air of the place, after the bodies in it and after what is on them.
    "ambient": 9, "scent": 10,
}

#: Standing kinds that DESCRIBE a body's own surface rather than report its
#: situation. Deliberately excludes `pose` and `environment`: where a body is
#: and how it is arranged CHANGE, and are the two things a mind cannot read
#: off its own card.
_OWN_BODY_DESCRIPTION_KINDS = frozenset(("body_part", "body_region"))

# Standing kinds exempt from the player tier's unchanged-state suppression.
# EMPTY ON PURPOSE since 2026-09-07. It held `sensation` from 2026-08-24 on
# the argument that an unchanged contact "is present bodily input on every
# beat it remains true" and so must never be deduped. Measured over the
# owner's corpus that argument produced the single worst tic on the page:
# 649 of 1,500 player-view "You feel ..." sentences (43.3%) byte-identical to
# the previous beat's, and in one 70-beat stretch of chat 117 a hand that
# never left a belt was announced on 40 beats -- with a template that ends
# "continuous while the contact holds", i.e. the engine stating the fact is
# unchanged in the same breath as re-delivering it. A body adapts: a constant
# pressure stops being news. The memory rule below already says so (an
# unchanged sensation mints no episode); the view now agrees with it.
#
# What survives, and why nothing is lost: a NEW contact still leads the beat
# (`_FIRST_SIGHT_LEADS` carries `sensation`), a contact whose parts or manner
# change gets a new key and renders as changed, character mode is untouched
# (its `delta` is always False -- a stateless mind is re-told everything),
# and the "empty delta -> full render" fallback in perception still
# re-delivers the sensation on a beat where nothing else happened. The name
# is kept so the seam stays visible at its one read site.
ACTIVE_STANDING_KINDS = frozenset()


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
_LANDSCAPE_SLOT = ("landscape-slot", None)


#: The five verdicts a standing percept can carry for ONE observer.
#: `unchanged` -- this observer's own previous ledger holds this exact key.
#: `changed`   -- it holds this subject under different content.
#: `first`     -- it holds nothing about this subject at all.
#: `reearn`    -- first sight again: a body met before, being re-delivered.
#: `ceased`    -- a standing sound this observer was being delivered, and
#:               this beat there is none of it (D3).
STANDING_VERDICTS = ("unchanged", "changed", "first", "reearn", "ceased")


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
        # A SILENCE IS ONLY NEWS TO AN EAR THAT HAD THE NOISE (D3). The
        # percept says a standing sound is gone; whether this observer was
        # ever delivered it is the ledger's question, and the answer is the
        # same subject test every other verdict here uses. No prior sound,
        # no `ceased` -- `first`, which `unheard_ceasing` drops rather than
        # rendering "it has stopped" about a noise nobody was told about.
        if (p.data or {}).get("ceased"):
            out[p.dedupe_key] = ("ceased" if prefix and prefix in subjects
                                 else "first")
            continue
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


def asked_this_beat(percept):
    """Did this observer's own act ask for this standing percept this beat:
    a thing it looked at, or took into its hands (`thing_reading_percepts`).

    AN ACT THAT ASKS IS ANSWERED, unchanged or not. A reading is standing
    state, so a delta view said it once and dropped it as furniture after --
    right for a panel a body happens to stand beside, and the opposite of
    right for a slip it holds up to the window and reads line by line.
    Measured, Saltmarsh Crossing (2026-10-11, scratch chat 170): the slip's
    lines reached the player's view on idx 22, when she stood at the desk it
    lay on, and when she took it in her hands on idx 24 and read it, her
    view held nothing of it and the page answered nothing. Re-delivering it
    tells this mind only what it was already told, so the firewall is not
    in question; both renderers read this, and `leads_the_beat` puts it in
    the beat, where the act that asked is."""
    return bool((getattr(percept, "data", None) or {}).get("asked"))


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
    if verdict in ("changed", "ceased") or asked_this_beat(percept):
        return True
    if percept.kind == "appearance" and appearance_delta(percept):
        return True
    # A STEADY SOUND THAT STARTS WHERE THE OBSERVER ALREADY STOOD is news
    # (DESIGN_SOUND_FIELD § 13): the room they were in has begun to sound.
    # One they walk into is the room as it is -- background, as before.
    if verdict == "first" and steady_sound(percept) \
            and not (percept.data or {}).get("ceased") \
            and _was_in_its_room(percept, prev_standing):
        return True
    return verdict == "first" and percept.kind in _FIRST_SIGHT_LEADS


#: THE STEADY SOUNDS A MIND GETS USED TO (DESIGN_SOUND_FIELD § 13, wave
#: B1): the room's soundscape -- where the noise is and what makes it -- and
#: a crowd's hum, standing hearing percepts keyed by the sound's own state,
#: so a sound that changes is a new key and a sound that stops is
#: `sound_ceased_percept`. Not a beat's own sounds (`ambient`, an event's
#: line) or a far one (`distant_sound`): those are news each time they
#: happen. Not a crowd's overheard fragment (`chatter`): its words change
#: under one key.
#: Since round 2 (§ 17) the WEATHER'S sound is one of them: what a body
#: hears of the sky from its room (`weather_sound_percepts`, the
#: precipitation and the wind as two sounds), told when it starts, faded
#: between, its stopping told once -- "the rain has stopped".
WEATHER_SOUND_TAG = "weather_sound"
WIND_SOUND_TAG = "wind_sound"
HABITUATING_SOUND_TAGS = ("soundscape", "hum", WEATHER_SOUND_TAG,
                          WIND_SOUND_TAG)


def steady_sound(percept) -> bool:
    """Is this a steady sound's standing percept (`HABITUATING_SOUND_TAGS`)?"""
    return (getattr(percept, "order_key", None) is None
            and getattr(percept, "kind", "") == "ambient"
            and getattr(percept, "channel", "") == "hearing"
            and str(getattr(percept, "dedupe_key", "") or "").split(":", 1)[0]
            in HABITUATING_SOUND_TAGS)


def view_verdicts(standing, prev_standing=frozenset(),
                  prev_described=frozenset(), *, player=False):
    """The verdicts a view renders by: every standing percept's on the player
    tier, as ever, and on the character tier a STEADY SOUND's
    (`steady_sound`) -- getting used to a sound, and noticing it stop, are
    facts about what THIS mind was hearing, whichever tier it is on. Shared
    by both renderers: which percepts a view carries is decided once."""
    if player:
        return standing_verdicts(standing, prev_standing, prev_described)
    return standing_verdicts([p for p in standing or () if steady_sound(p)],
                             prev_standing, prev_described)


def habituated(percept, verdict, *, full_render=False) -> bool:
    """GETTING USED TO A SOUND (DESIGN_SOUND_FIELD § 13). A steady sound this
    observer was already hearing, unchanged, fades from attention: it is
    told when it starts, when it changes and when it stops
    (`sound_ceased_percept`, once), and in between it is out of the view --
    on the character tier too, which otherwise re-tells everything every
    beat, so a generator a mind has stood beside for an hour was announced
    to it hourly. An explicit look (`full_render`) asks for the room back;
    a mind that walks in hears the room as it is (its ledger does not hold
    the sound, so the verdict is `first`)."""
    return (not full_render and verdict == "unchanged"
            and steady_sound(percept) and not asked_this_beat(percept))


def _was_in_its_room(percept, prev_standing) -> bool:
    """Was this observer in the room this percept's sound fills, last beat?
    The soundscape's subject is the room (`soundscape_percept`), and so is
    the room description's (`environment_percept`): the observer's own
    ledger holding the room's `env` subject is the answer."""
    subject = _subject_prefix(getattr(percept, "dedupe_key", ""))
    if not subject or not prev_standing:
        return False
    want = "env:" + subject.split(":", 1)[1]
    return any(_subject_prefix(key) == want for key in prev_standing)


def unheard_ceasing(percept, verdict):
    """Whether this percept claims a sound stopped that this observer was
    never delivered (D3) -- in which case it renders nothing at all.

    Both renderers ask, because the answer is an information decision and
    not a wording one. Two ways it is True. The observer's ledger holds no
    sound for this room, so `standing_verdicts` said `first` and there is no
    silence for them to notice; or nothing computed a verdict at all -- the
    character tier renders the full standing state every beat and has no
    ledger to diff against, and a room's own sound is not a thing that
    happens to a mind that was never following it.
    """
    return bool((getattr(percept, "data", None) or {}).get("ceased")) \
        and verdict != "ceased"


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
    # WHAT EACH STANDING KEY WAS FOR THIS OBSERVER THIS BEAT, as
    # {dedupe_key: verdict} over `STANDING_VERDICTS`. Empty outside the
    # player tier, which is the only one that diffs against a ledger at all.
    #
    # It is carried OUT of the render because the view is not the only thing
    # downstream re-delivers a standing fact to (B28): the narrator's sensory
    # manifest re-derives the same standing contacts from the scene, and with
    # no verdict to read it shipped every one of them as though it had just
    # happened -- measured chat 117, a hand that never left a belt announced
    # on 40 of 70 beats, in the same beats the view had correctly gone quiet.
    # One observer, one ledger, one answer: whoever re-delivers reads it.
    verdicts: dict = field(default_factory=dict)


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


def _presence_clause(p, *, brief=False, fresh=False):
    """One body's presence as a bare clause -- no capital, no full stop, so
    it can stand alone or be joined with others.

    `brief` is the same fact at reduced cost, for a body whose presence has
    not changed since this observer's last view: who they are and where, and
    none of the qualifying clauses that were already delivered. See
    `_render_presence_group` for why an unchanged body is still named.

    `fresh` is its complement and the reason it exists: a body this observer
    did NOT hold last view and holds now. A CHANGE IN WHAT IS PRESENT MUST
    NOT READ AS FURNITURE. The engine already knew this was the beat's news
    -- `leads_the_beat` puts a first-sight presence in the beat half, so it
    reaches the narrator as a numbered `current_events` entry under the one
    rule in that sheet that is absolute -- and the SENTENCE still said "the
    compact wiry figure is close by on your right", which is the same
    grammar as "Sarah Moon is within arm's reach". Sitting between two
    standing-description entries, an arrival phrased as a location was
    indistinguishable from scenery, and the narrator dropped it.

    Measured live (chat 117 turn 58): a carbonic stalker that had been
    hunting the cast for thirty beats walked into the room they were
    standing in, reached both views, was entry 4 of the player's
    `current_events`, and did not reach the page at all. The player was not
    told a thing was beside them.

    "is now" against `presence_unchanged`'s "is still": the pair is the
    whole distinction, and it claims only what the observer has. It does not
    say the body came IN -- an observer may be meeting it because it moved,
    because they turned, or because a light reached it -- only that it is
    there and was not. You may not know what has arrived; you know that
    something has.
    """
    room = str(p.data.get("room") or "")
    tier = (_en("presence_in_room", room=room) if room
            else _TIER_PHRASES.get(str(p.data.get("tier")),
                                   _TIER_PHRASES["default"]))
    if brief:
        where = _strip_sentence_ends(p.data.get("at"))
        return _en("presence_unchanged", label=p.source_label,
                   where=_en("presence_at_bare", at=where) if where else tier)
    side = p.data.get("side")
    side_clause = _en("side", side=side) if side in ("left", "right") else ""
    # Relative magnitude qualifies every other clause in the view -- what can
    # be reached, held, or resolved at all -- so it rides the STANDING
    # presence sentence rather than waiting for an act to make it visible. An
    # unknown or absent label costs wording and never the beat.
    size = _SIZE_PHRASES.get(str(p.data.get("size") or ""), "")
    size_clause = f", {size}" if size else ""
    # Where they are standing, when the scene knows and they are in this
    # room. It rides the tier rather than replacing it: "close by" is how
    # far, "at the hearth" is where, and a reader wants both.
    at = _strip_sentence_ends(p.data.get("at"))
    at_clause = _en("presence_at", at=at) if at else ""
    # Seen over something: name what, and how much of them shows. Plain
    # words -- "behind the counter, from the waist up" -- never a fraction.
    behind = str(p.data.get("behind") or "").strip()
    cover_clause = ""
    if behind:
        cover_clause = _en("presence_behind", behind=behind)
        shows = str(p.data.get("shows") or "").strip()
        if shows:
            cover_clause += _en("presence_shows", shows=shows)
    # The observer's own beam is on this body (D5). A fact about where the
    # observer is POINTING, which is theirs by construction, and it rides
    # the presence sentence the way the tier and the cover clause do.
    beam_clause = _en("presence_in_beam") if p.data.get("in_beam") else ""
    where = (f"{tier}{at_clause}{side_clause}{size_clause}"
             f"{cover_clause}{beam_clause}")
    if fresh:
        return _en("presence_fresh", label=p.source_label, where=where)
    return f"{p.source_label} is {where}"


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

    `percepts` is a list of (percept, brief) pairs. A SENTENCE THAT
    ENUMERATES WHO IS PRESENT MUST ENUMERATE EVERYONE PRESENT. The player
    view leads with what changed and suppresses standing state this observer
    already holds, which is right for a room, a smell or a pose and wrong for
    this one clause, because presence is delivered in the grammar of a closed
    conjunctive list -- and a reader cannot tell a delta from a roll-call
    when both read "A is here, B is here, and C is here."

    Measured, run 2026-09-05C `multitude` turn 1 (PM6): six bodies in the
    hall, and the player's outcome view read "Maren Vaunt is within arm's
    reach on your left, Ilsabet Roon is across the room on your left, Corin
    Ashe is across the room on your left, and Devereux Hallam is within arm's
    reach." Four names, an `and` before the last, and no Tobin Slake -- who
    was standing at the doors and was the only person in the room who did
    nothing that beat. The narrator then named exactly those four. Recurred
    on turns 4, 7, 8 and 9.

    So an unchanged body is still named, at reduced cost (`brief`): its label
    and where it is, without the tier, side, size and cover clauses it was
    already given. The delta survives as EMPHASIS -- what moved is spelled in
    full and leads the sentence -- rather than as an omission that reads as
    an absence.

    The order is NEAR TO FAR (D4, review 2026-09-07). A list of bodies is
    blocking, and blocking is what the page was missing: the sentence
    enumerated in scene-dict order, so the narrator received no arrangement
    at all and supplied one -- a body standing at the other door was put "on
    my right" (UNBUILT 1.149). Ordering withholds nothing; every body the
    observer can see is still in the same sentence with the same words.
    `presence_percepts` ALREADY SORTED THEM -- the rule lives in the IR so
    every pack's renderer inherits it -- and the sort below is a no-op for
    anything that came from there, kept because this function also renders
    percepts a caller built by hand.

    Three more things happen here, and all three are why the corpus replay
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
    pairs = [(p, False, False) if isinstance(p, Percept)
             else (p[0], bool(p[1]), bool(p[2]) if len(p) > 2 else False)
             for p in percepts or ()]
    out = []
    for fidelity in ("full", "degraded"):
        # What CHANGED is spelled in full and comes first; what merely
        # persists closes the sentence. Stable within each half.
        group = [row for row in pairs if row[0].fidelity == fidelity]
        # NEAR TO FAR (D4). A no-op on a list from `presence_percepts`,
        # which minted the order; it re-states it for hand-built percepts.
        # Stable, and inside each half of the delta split below, so the
        # emphasis rule keeps its say: what changed is still spelled in
        # full and still leads. A room the geometry cannot measure gives
        # every body the same key and the order is untouched.
        group = sorted(group, key=lambda row: _presence_sort_key(row[0]))
        group = [x for x in group if not x[1]] + [x for x in group if x[1]]
        if not group:
            continue
        clauses, counts = [], {}
        for p, brief, fresh in group:
            clause = _presence_clause(p, brief=brief, fresh=fresh)
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
        out.append((group[0][0], _cap(_join_clauses(rendered)) + "."))
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
        # remembered as ``my heels`` -- and the owner's "as you turn" as "as
        # I turn", from the rewrite that still knew "she" was the subject.
        return _said_as_mine(p.data, field) if past else text

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
# The article and bare-determiner tables are read from the ACTIVE pack at use
# time (`_pack_words`), because the text they shape is data the language
# adapter renders verbatim; only the English renderer's own clause assembly
# above still reads the English card.


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
        # An authored desc is a NOUN PHRASE here, whatever it was written as
        # (`_noun_phrase`): this list is the inside of one sentence.
        desc = _noun_phrase((row or {}).get("desc"))
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


def _render_openings(openings, here=""):
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
    # TWO BOUNDARIES ARE NEVER ONE SENTENCE TWICE. A way out with no authored
    # name falls back to its barrier's generic phrasing, so a room with two of
    # them rendered "The doorway is shut. The doorway is shut." (run
    # 2026-09-05C `masque`, turn 15, PX20) -- referentially indistinguishable
    # and reading as a stutter. Describing the second one by where it goes is
    # exactly what a blind boundary may not do, so the distinguisher is the
    # one `assign_stranger_labels` already uses for bodies whose appearance
    # cannot tell them apart: an ordinal, which distinguishes by NOTHING the
    # observer has not already got -- they can see two doorways, and counting
    # them adds no attribute and no identity.
    rows = []
    for opening in openings or ():
        desc = _noun_phrase((opening or {}).get("desc"))
        if desc:
            rows.append((opening, desc))
    total, so_far = {}, {}
    for _opening, desc in rows:
        total[desc] = total.get(desc, 0) + 1
    parts = []
    for opening, desc in rows:
        if total[desc] > 1:
            so_far[desc] = so_far.get(desc, 0) + 1
            if so_far[desc] > 1:
                desc = _ordinal_label(desc, so_far[desc])
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
        if opening.get("way") == "overlook" and opening.get("vertical") in ("up", "down"):
            parts.append(_cap(_en("opening_seen_above" if opening["vertical"] == "up"
                                  else "opening_seen_below", opening=desc, room=room)))
        elif _bare_words(desc) in (_bare_words(room), _bare_words(here)) and desc:
            # A way named for a room it joins identifies no boundary: "Through
            # the long stone stair is the long stone stair" (Kirinoura, scratch
            # chat 167, 2026-10-05), and from the stair's far side "Through
            # the terrace is the long stone stair". The way goes on from HERE
            # to the room -- worded true of any destination, a place as much
            # as a passage (review, 2026-10-05: 97 of 398 named edges in the
            # owner's scenes carry their destination's name, most of them
            # places).
            parts.append(_cap(_en(
                {"up": "opening_onward_up", "down": "opening_onward_down"}.get(
                    opening.get("vertical"), "opening_onward"), room=room)))
        else:
            parts.append(_cap(_en("opening_seen", opening=desc, room=room)))
        notes = str(opening.get("room_notes") or "").strip()
        if notes:
            parts.append(notes if notes[-1:] in ".!?" else notes + ".")
        items = _feature_items(opening.get("features"), placed=False)
        if items:
            parts.append(_en("opening_features", items=_join_clauses(items)))
    return " ".join(parts)


def _end_sentence(text):
    """`text` ending a sentence: its own terminal stop kept, one added only
    where it has none. A clause the pack writes as a whole sentence ("The
    air is mild.") was given a second one by the sensation renderer, in
    every outdoor view and memory ("The air is mild..", seen 2026-10-05)."""
    text = str(text or "").rstrip()
    return text if (not text or text[-1] in ".!?\u3002") else text + "."


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
        ways = _render_openings(p.data.get("openings"), here=p.data.get("room_name") or "")
        if ways:
            parts.append(ways)
        # WHERE THE LIGHT FALLS, when the field found the room uneven; else
        # the flat sentence, exactly as before (the shape is only ever
        # present when there is more to say than one word for the room).
        shaped = render_light_shape(p.data.get("light_shape"))
        if shaped:
            parts.append(shaped)
        else:
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
    if p.kind == "demeanor":
        # Spliced like every other authored description (`_noun_phrase`):
        # a character writes its demeanor as a sentence, and the raw form
        # rendered "An indistinct figure seems A wet, nervous young man on a
        # bench, ...." (scratch play 2026-09-14, chat 2 turn 1).
        text = _spliced_fragment(str(p.data.get("demeanor") or ""))
        return _en("demeanor", label=_cap(p.source_label), demeanor=text) \
            if text else ""
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
        if p.data.get("ears") in EAR_STATES:
            return _en("ears_" + p.data["ears"])
        clause = str(p.data.get("clause") or "").strip()
        return _end_sentence(_cap(clause)) if clause else ""
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
        return _render_ambient(p)
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


VOICE_KEY_PREFIX = "voice:"


def carried_voices(prev_standing):
    """The voice keys an observer's previous view filed -- the one family of
    standing key that persists without being re-earned each beat."""
    return {str(k) for k in (prev_standing or ())
            if str(k).startswith(VOICE_KEY_PREFIX)}


def _render_ambient(p, *, episode=False):
    """An ambient percept's sentence, standing or ordered alike -- in the
    episode's own words where a typed renderer carries them (`episode`)."""
    if p.data.get("landscape"):
        lines = landscape_lines([p])
        return render_landscape_line(lines[0][1]) if lines else ""
    if p.data.get("ceased"):
        # A stopping that names what stopped carries its own sentence
        # (`weather_sound_percepts`: "The rain has stopped."); the room's
        # soundscape keeps the pack's generic one.
        own = str(p.data.get("desc") or "").strip()
        if own:
            return own if own[-1:] in ".!?" else own + "."
        return _en("sound_subsided" if p.data.get("subsided")
                   else "sound_ceased")
    if p.data.get("soundscape"):
        return render_sound_shape(p.data.get("soundscape"))
    if p.data.get("distant"):
        return render_distant_sound(p.data["distant"], episode=episode)
    desc = str(p.data.get("desc") or "").strip()
    if desc and desc[-1:] not in ".!?":
        desc += "."
    return desc


def _en_voice_line(p):
    """A voice whose words did not carry (`fidelity == "voice"`): whose it
    is where the listener knows or sees the speaker, how loud, and from
    where -- "Mara's voice, raised, beyond the wall -- the words do not
    carry." Never a word of the line."""
    d = p.data or {}
    loudness = {"loud": _en("speech_voice_raised"),
                "shout": _en("speech_voice_shouting")}.get(
        str(d.get("volume") or "").casefold(), "")
    bearing = str(d.get("bearing") or "")
    where = _en("speech_voice_where", where=bearing) if bearing else ""
    if d.get("attributed") and str(p.source_label or "").strip():
        return _en("speech_voice", label=_cap(p.source_label),
                   loudness=loudness, where=where)
    return _en("speech_voice_unknown", loudness=loudness, where=where)


def _heard_after(p, line, *, ended=False):
    """What follows a line where the listener did not have all of it: the
    tone its voice carried (`tone_heard`, for a fragment or a voice alone),
    and a stranger's voice said once (`voice_apart`) -- in that order,
    each its own sentence."""
    if not line:
        return line
    d = p.data or {}
    extra = []
    tone = _feeling_heard(d)
    if tone and p.fidelity in ("fragment", "voice"):
        extra.append(_en("speech_voice_tone", tone=tone))
    if d.get("own_name") and p.fidelity in ("fragment", "voice"):
        extra.append(_en("speech_own_name"))
    if d.get("voice_apart"):
        extra.append(_en("voice_register", register=d["voice_apart"]))
    if not extra:
        return line
    head = _end_sentence(line) if ended or p.fidelity != "full" \
        else line.rstrip()
    return head + " " + " ".join(extra)


def _render_event(p):
    if p.kind == "speech":
        # An answer that did not come (D6). Before the fragment branch,
        # because there is no fragment and no body to render: the percept
        # carries no words by construction.
        if p.fidelity == "silence":
            return _en("speech_silence", label=_cap(p.source_label))
        # Detected, and nothing more: no words, no speaker, no tone.
        if p.fidelity == "trace":
            bearing = str(p.data.get("bearing") or "")
            return (_en("speech_trace_placed", where=bearing) if bearing
                    else _en("speech_trace"))
        # The voice, without its words (§ 12 of the sound note).
        if p.fidelity == "voice":
            return _heard_after(p, _en_voice_line(p))
        body = p.data.get("body") or ""
        via = str(p.data.get("via") or "")
        # `_inject_dialogue` into an empty document is the production grammar
        # (bare-infinitive heard form, conducted, articulation) emitting into
        # nothing -- no duplicate detection against model prose needed.
        if p.fidelity == "fragment":
            line = _en(
                "muffled_attributed" if p.data.get("attributed") else "muffled",
                label=_cap(p.source_label),
                fragment=p.data.get("fragment", ""))
        else:
            line = _inject_dialogue(
                "", p.source_label, f'"{body}"', p.data.get("level", "full"),
                p.data.get("volume", "normal"), p.data.get("can_see", False),
                conducted=p.data.get("conducted", False),
                tone=p.data.get("manner", p.data.get("tone", "")),
                articulation=p.data.get("articulation", ""))
        # The route is part of what was perceived, not a flourish. A voice on a
        # speaker and a voice at your shoulder are different facts, and the
        # view is where a reader learns which one this was -- drop it here and
        # the whole channel reads as somebody standing in the room.
        bearing = str(p.data.get("bearing") or "")
        if via and line:
            line = _en("speech_via", sentence=line.rstrip("."), via=via)
        elif bearing and line:
            line = _en("speech_from", sentence=line.rstrip("."), where=bearing)
        # A voice too long for the manner slot, said once after the line
        # (`_voice_fields`).
        if line and p.fidelity != "fragment" and p.data.get("said_apart"):
            # A route clause ends without a stop; a line ends on its quote.
            line = (_end_sentence(line) if via or bearing else line.rstrip()) \
                + " " + _en("voice_register", register=p.data["said_apart"])
        return _heard_after(p, line, ended=bool(via or bearing))
    if p.kind == "communication":
        line = _observable_predicate(
            p.source_label, p.data.get("surface")) or ""
        via = str(p.data.get("via") or "")
        return (_en("speech_via", sentence=line.rstrip("."), via=via)
                if via and line else line)
    if p.kind == "act":
        if p.data.get("unseen"):
            bearing = str(p.data.get("bearing") or "").strip()
            return (_en("act_heard_placed", where=bearing) if bearing
                    else _en("act_heard"))
        if p.fidelity == "shapes":
            room = str(p.data.get("room") or "")
            if room:
                return _en("act_shapes_placed", label=_cap(p.source_label),
                           where=_en("presence_in_room", room=room))
            return _en("act_shapes", label=_cap(p.source_label))
        return _observable_predicate(
            p.source_label, p.data.get("surface")) or ""
    if p.kind == "cue":
        cue = str(p.data.get("cue") or "").strip()
        return _en("cue", label=_cap(p.source_label), cue=cue) if cue else ""
    if p.kind == "crossing":
        if p.data.get("direction") == "arrived":
            return _en("arrived", label=_cap(p.source_label))
        return _en("departed", label=_cap(p.source_label))
    if p.kind == "substance":
        clause = str(p.data.get("clause") or "").strip()
        return _end_sentence(_cap(clause)) if clause else ""
    # AN AMBIENT PERCEPT WITH AN ORDER IS A THING THAT HAPPENED THIS BEAT --
    # a beat's own sound event (`ambient_percepts(order_key=...)`), what a
    # look at the horizon found (`vista_percepts`). This renderer had no
    # branch for it, so in English every one rendered to nothing and was
    # dropped, while the Japanese adapter rendered it: measured 2026-10-04,
    # chat 117's siphon-vent hiss (the case the ordered key was minted for)
    # composed to '' in both the player's and a character's view.
    if p.kind == "ambient":
        return _render_ambient(p)
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
    which is how the background is asked for on purpose. An unchanged
    sensation is standing state like any other on the player tier: it led
    the beat when it began, it renders again when its parts or manner
    change, and between those it is context the reader already holds
    (`ACTIVE_STANDING_KINDS`, and the measurement beside it).

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
            pain=p.data.get("pain", False), woke=p.data.get("woke", ""))
        rest = [q for q in percepts if q.kind != "residue"]
        if p.data.get("woke") and rest:
            # A SLEEPER A SOUND WOKE PERCEIVES THE REST OF THE BEAT
            # (DESIGN_SOUND_FIELD § 17): what woke them leads, as the
            # residue tells it, and the remainder follows as an awake mind's
            # view. What the remainder holds was decided by the caller
            # (`perception._composer_outcome_views`, from the waking moment
            # on); this only orders it. The woke sentence is the beat's
            # (`as_beat`), and the ledger files the room they woke in.
            after = _render_view_english(
                rest, mode=mode, prev_standing=prev_standing,
                prev_described=prev_described, full_render=full_render)
            return RenderedView(
                text=(text + " " + after.text).strip(),
                spans=[(as_beat(p), text)] + list(after.spans),
                standing_keys=set(after.standing_keys),
                described=after.described, verdicts=dict(after.verdicts))
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
    # A VOICE ONCE KNOWN STAYS KNOWN. The ledger is rolled forward a turn at
    # a time and a standing key survives only while something re-files it;
    # a voice key was re-filed only on a beat the speaker spoke, so one
    # silent beat made their next line a first hearing again (descent copy,
    # beats 120-121). Carried forward unconditionally, like a description
    # already delivered: knowing how somebody sounds does not lapse.
    standing_keys = carried_voices(prev_standing)
    seen_dedupe = set()
    verdicts = view_verdicts(standing, prev_standing, prev_described,
                             player=player)
    # Presence is ONE observation -- who is here -- so the whole group takes
    # one side of the partition, decided before the loop reaches the first
    # of them: if any body in it is new or has moved tier, who is here is
    # this beat's news.
    # A BODY YOU CANNOT NAME IS NEVER BACKGROUND. `leads_the_beat` asks
    # what CHANGED, which is the right question for a room, a smell or a
    # pose, and the wrong one for a stranger standing still: nothing about
    # them changes, so who is here stops being the beat's news and the
    # sentence naming them becomes standing description -- which the
    # narrator sheet says in as many words "carries no obligation".
    #
    # Measured live, chat 117 turns 58 and 59. A carbonic stalker walked
    # into the room the cast were standing in and did not reach the page.
    # On the arrival beat the sentence read as furniture; on the NEXT beat
    # it was furniture, because the thing had the decency to hold still. Two
    # beats with a hunter at arm's reach and a player who was never told.
    #
    # A person does not stop noticing a stranger they cannot name in a dark
    # corridor, and the engine already knows which bodies those are. Bounded
    # by measurement rather than by hope: across the author's 3771 composed
    # beats an unrecognised body is co-present on 235 (6.2%), never more
    # than two at once -- crowds are the crowd system's and never arrive
    # here as company rows. So this is rare, and every instance of it is the
    # case worth spending a sentence on.
    _stranger_present = any(
        p.kind == "presence" and not (p.data or {}).get("known", True)
        for p in standing)
    presence_leads = player and (_stranger_present or any(
        leads_the_beat(p, verdicts.get(p.dedupe_key, "first"), prev_standing)
        for p in standing if p.kind == "presence"))
    # The far places are one view of one landscape, said as lines rather
    # than a sentence each (`landscape_lines`), so like the roll-call they
    # take one half of the partition: the beat's, when any place in them is
    # this beat's news.
    landscape_group = []
    landscape_leads = player and any(
        leads_the_beat(p, verdicts.get(p.dedupe_key, "first"), prev_standing)
        for p in standing
        if is_landscape(p) and not (delta and p.dedupe_key in prev_standing))

    standing_spans = []         # the background half in player mode
    beat_spans = []             # player mode only
    presence_group = []
    for p in standing:
        standing_keys.add(p.dedupe_key)
        if p.dedupe_key in seen_dedupe:
            continue
        seen_dedupe.add(p.dedupe_key)
        verdict = verdicts.get(p.dedupe_key, "first")
        # A silence is only news to an ear that had the noise (D3). The key
        # is already filed above, so the sound coming back next beat still
        # reads as a change against it.
        if unheard_ceasing(p, verdict):
            continue
        # ...and a steady sound it has been hearing, unchanged, has faded
        # from its attention (`habituated`) -- on either tier.
        if habituated(p, verdict, full_render=full_render):
            continue
        leads = player and leads_the_beat(p, verdict, prev_standing)
        if is_landscape(p):
            if delta and p.dedupe_key in prev_standing:
                continue
            landscape_group.append(p)
            if len(landscape_group) == 1:
                (beat_spans if landscape_leads else standing_spans).append(
                    _LANDSCAPE_SLOT)
            continue
        if p.kind == "presence":
            # NEVER SUPPRESSED, only shortened. A body that stands still is
            # still in the room, and the sentence that says who is here is
            # the one clause in this view whose grammar claims to be
            # exhaustive (`_render_presence_group`, PM6).
            #
            # `standing` is already sorted by _STANDING_ORDER, so
            # re-inserting the presence group at the first presence position
            # keeps the discourse order of whichever half it belongs to
            # intact.
            # (percept, brief, fresh). `brief` is a presence this observer
            # already held unchanged; `fresh` its complement -- a BODY they
            # did not hold at all and hold now, which only a ledger can tell
            # from an opening view where everyone is new and nobody arrived.
            #
            # Compared on `_subject_prefix`, never on the whole key: a
            # dedupe key carries the presence's STATE as well as its
            # subject, so a body that merely crossed the room has a key the
            # ledger has not seen and is not new. Caught by
            # `test_a_body_that_stood_still_is_still_in_the_room`, which
            # read "Maren Vaunt is now within arm's reach" for a woman who
            # had been in the room the whole time.
            _subject = _subject_prefix(p.dedupe_key)
            _held = {_subject_prefix(k) for k in (prev_standing or ())}
            _held.discard(None)
            presence_group.append(
                (p, delta and p.dedupe_key in prev_standing,
                 bool(delta and prev_standing and _subject
                      and _subject not in _held)))
            if len(presence_group) == 1:
                (beat_spans if presence_leads else standing_spans).append(
                    _PRESENCE_SLOT)
            continue
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
              and p.kind not in ACTIVE_STANDING_KINDS
              and not asked_this_beat(p)):
            continue
        elif (not full_render and p.dedupe_key in prev_standing
                and _is_own_body_description(p)):
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
        if _LANDSCAPE_SLOT in half:
            at = half.index(_LANDSCAPE_SLOT)
            group = [(as_beat(rep) if half is beat_spans else rep, sentence)
                     for rep, line in landscape_lines(landscape_group)
                     for sentence in [render_landscape_line(line)] if sentence]
            half[at:at + 1] = group

    event_spans = []
    for p in events:
        if p.dedupe_key in seen_dedupe:
            continue
        seen_dedupe.add(p.dedupe_key)
        sentence = _render_event(p)
        if sentence:
            event_spans.append((p, _cap(sentence)))
            # A voice SAID is a voice established for this observer -- never
            # one only heard round a corner, whose register no line has said
            # yet (review round 5, 2026-10-05).
            if p.data.get("voice_key") and _can_say_the_voice(p):
                standing_keys.add(str(p.data["voice_key"]))
            # A look at a standing thing files the thing (`vista_percepts`).
            if p.data.get("files_standing"):
                standing_keys.add(str(p.data["files_standing"]))

    if player:
        # The ordering rule itself lives in `player_view_order`, which every
        # pack calls, so the reference renderer cannot drift from one.
        spans = player_view_order(event_spans + beat_spans + standing_spans)
        # A ROLL-CALL IS ADDED TO A VIEW; IT IS NEVER THE WHOLE OF ONE. The
        # brief clause above exists so the presence sentence stays honest
        # about who is in the room, not so it can be a beat's entire content
        # -- a beat whose only content is that nobody moved has told this
        # mind nothing, and the empty view is exactly what
        # `perception._composer_render_observer`'s floor reads before asking
        # for the background instead (chat 98 turns 13, 15, 16, 20, 21, 36).
        # ...unless one of the people in the room cannot be NAMED. "Nobody
        # moved" is nothing to report about company this observer knows, and
        # is the whole of the report when a stranger is standing there: the
        # beat where a hunter holds still at arm's reach is exactly the beat
        # the player most needs, and it is the one this rule was emptying
        # (chat 117 turn 59, the beat after it walked in).
        # Decided on the NEAR spans: a far line beside an unchanged roll-call
        # is added to the view, never the whole of it -- kept, so the floor
        # (which also asks the near spans) re-renders the room around it.
        near_spans = [(p, s) for p, s in spans if not far_sight(p)]
        if (delta and near_spans and not _stranger_present
                and all(row[1] for row in presence_group)
                and all(p.kind == "presence" for p, _s in near_spans)):
            spans = [(p, s) for p, s in spans if far_sight(p)]
    else:
        # Discourse rule: a sudden event chain leads; otherwise standing state
        # anchors the view and the beat follows.
        sudden = any(p.suddenness >= 0.6 for p, _ in event_spans)
        spans = (event_spans + standing_spans) if sudden \
            else (standing_spans + event_spans)
    text = " ".join(sentence for _, sentence in spans).strip()
    # The ledger's verdicts are the player tier's, as before: a character's
    # steady-sound verdicts decide its view and are not filed.
    return RenderedView(text=text, spans=spans,
                        standing_keys=standing_keys, described=described,
                        verdicts=dict(verdicts) if player else {})


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
    # THE VERDICT IS THE ENGINE'S, NOT THE PACK'S. Computed here rather than
    # inside a renderer so both language paths carry the same answer: a pack
    # that never heard of the field cannot leave a downstream re-delivery
    # (see `RenderedView.verdicts`) with nothing to read.
    def _stamp(out):
        if mode == "player" and not out.verdicts:
            out.verdicts = standing_verdicts(
                [p for p in percepts or [] if p.order_key is None],
                prev_standing, prev_described)
        return out

    percepts = _names_kept(_one_voice_each(percepts))
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
            return _stamp(out)
        except Exception:
            # A view is what an observer perceives at all. A malformed pack
            # must cost wording, never the whole beat, so fall through to the
            # in-module reference renderer rather than killing the turn.
            logger.exception("language renderer failed; using English wording")
    return _stamp(_render_view_english(
        percepts, mode=mode, prev_standing=prev_standing,
        prev_described=prev_described, full_render=full_render))


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
    is what was said and stays verbatim).

    A MEMORY'S FIRST PERSON FOLLOWS THE WORDS' GRAMMATICAL ROLES. English
    spells the second person's subject and object alike, so the pack's rules
    (`second_to_first`) read the role from what the text itself marks, and
    from nothing else -- no list of verbs or prepositions: a "you" after the
    punctuation that opens a clause is its subject ("Through the walls, I can
    hear ..."), as are the contracted forms and the be row ("you're", "you
    aren't"); every other "you" is an object ("me") -- the first word of the
    text included, because the swap is applied to fragments as well as to
    sentences and a pose's referent alone ("you", the sentence's "astride
    you") is an object, while every rewrite capitalises the "You" that opens
    a sentence. The possessive, independent and reflexive forms keep their
    own. Measured: the rule that made every lowercase "you"
    "me" filed "Through the walls, me can hear the heavy rain, muffled." in
    the lighthouse probe's memories (2026-10-20, chat 2 rows 46 and 50);
    twelve rows across the three probe stories carried such a "me".

    What the text cannot mark -- a subject inside a relative or subordinate
    clause -- is given its first person where the role is known: an engine
    template's own episode wording (`render_distant_sound`, the residue's
    `pain_episode`), or the first person an authored line was rewritten into
    beside its second person (`_said_as_mine`). Japanese marks the role with
    a particle, so its rules map the pronoun alone."""
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
        if p.fidelity == "silence":
            return _en("episode_speech_silence", label=p.source_label)
        if p.fidelity == "trace":
            return _en("episode_speech_trace")
        if p.fidelity == "voice":
            # The voice is the whole of what arrived, so it is what is kept:
            # whose (where known or seen), how loud, the tone it carried.
            d = p.data or {}
            loudness = {"loud": _en("speech_voice_raised"),
                        "shout": _en("speech_voice_shouting")}.get(
                str(d.get("volume") or "").casefold(), "")
            line = (_en("episode_speech_voice", label=p.source_label,
                        loudness=loudness)
                    if d.get("attributed") and str(p.source_label or "").strip()
                    else _en("episode_speech_voice_unknown", loudness=loudness))
            tone = _feeling_heard(d)
            return line + (" " + _en("episode_speech_voice_tone", tone=tone)
                           if tone else "") + (
                " " + _en("episode_speech_own_name")
                if d.get("own_name") else "")
        via = str(p.data.get("via") or "")
        if p.fidelity == "fragment":
            attributed = bool(p.data.get("attributed"))
            key = ("episode_muffled_attributed_via" if attributed and via
                   else "episode_muffled_via" if via
                   else "episode_muffled_attributed" if attributed
                   else "episode_muffled")
            return _en(key, via=via, label=p.source_label,
                       fragment=p.data.get("fragment", "")) + (
                " " + _en("episode_speech_own_name")
                if p.data.get("own_name") else "")
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
        if p.fidelity == "shapes":
            room = str(p.data.get("room") or "")
            if room:
                return _en("episode_act_shapes_placed",
                           label=_cap(p.source_label),
                           where=_en("presence_in_room", room=room))
            return _en("episode_act_shapes", label=_cap(p.source_label))
        surface = _said_as_mine(p.data, "surface")
        words = surface.split()
        if words:
            base = _base_from_third_person_s(words[0])
            if base:
                # EVERY VERB OF THE ACTOR'S OWN PHRASES after "I saw X" takes
                # the base form, by the one rule the mind's own attempt is
                # turned by (`_verbs_in_base`): only the first verb was, and the
                # lighthouse probe's keeper filed "I saw Rhona Carrick dig into
                # her jacket and brings out a sealed letter" (2026-10-20, chat 2
                # row 40). Where the rule cannot turn the phrase exactly, the
                # first verb alone is turned, as before.
                turned = _verbs_in_base(surface).split()
                if turned:
                    head = turned[0]
                    action = (head if head.isupper() and len(head) > 1
                              else head[:1].lower() + head[1:])
                    rest = " ".join(turned[1:]).rstrip(".")
                else:
                    action, rest = base, " ".join(words[1:]).rstrip(".")
                ending = f" {rest}." if rest else "."
                return _en(
                    "episode_act", label=p.source_label,
                    action=action, ending=ending)
        sentence = _observable_predicate(p.source_label, surface)
        return sentence or ""
    if p.kind == "cue":
        cue = str(p.data.get("cue") or "").strip()
        return _en("episode_cue", label=p.source_label, cue=cue) if cue else ""
    if p.kind == "crossing":
        if p.data.get("direction") == "arrived":
            return _en("episode_arrived", label=_cap(p.source_label))
        return _en("episode_departed", label=_cap(p.source_label))
    if p.kind == "substance":
        clause = _first_person(str(p.data.get("clause") or "").strip())
        return _end_sentence(_cap(clause)) if clause else ""
    if p.kind == "environment":
        name = p.data.get("room_name")
        return _en("episode_room", room=name) if name else ""
    if p.kind == "pose":
        return _render_pose(p, past=True)
    if p.kind == "sensation":
        if p.data.get("ears") in EAR_STATES:
            return _en("episode_ears_" + p.data["ears"])
        clause = _first_person(str(p.data.get("clause") or "").strip())
        return _end_sentence(_cap(clause)) if clause else ""
    if p.kind == "appearance":
        desc = _appearance_as_prose(p.data.get("description"))
        return _en("episode_appearance", description=desc) if desc else ""
    if p.kind == "scent":
        return _render_scent(p, episode=True)
    if p.kind == "residue":
        # A MEMORY IS THE MIND'S OWN, ASLEEP AS AWAKE: the residue is turned
        # into the first person like every other line of an episode. It was
        # turned only when a waking had more of the beat after it, so the
        # farmhouse probe's sleeper filed "You are under, below waking." five
        # beats running (2026-10-20, chat 2).
        return _first_person(_compose_residue_view(
            p.data.get("level"), targeted=p.data.get("targeted", False),
            loud_event=p.data.get("loud_event", False),
            pain=p.data.get("pain", False), woke=p.data.get("woke", ""),
            episode=True))
    if p.kind == "ambient":
        # What was seen far off and what was heard this beat: a vista line,
        # what a look at one found, a beat's own sound. The view rendered
        # them and memory did not -- the class 43946e73 fixed in
        # `_render_event`, one renderer over (UNBUILT_CHARACTERS §1.178).
        if p.data.get("landscape"):
            lines = landscape_lines([p])
            return render_landscape_line(lines[0][1], episode=True) if lines else ""
        return _first_person(_render_ambient(p, episode=True))
    return ""


#: The standing kinds an episode keeps when they are NEW OR CHANGED, plus far
#: sight (`far_sight`): a room, a sensation, a pose, a scent -- and what
#: stands on the horizon or far off, which is where a place sits in a mind's
#: memory of it. Every other standing line is the room's furniture.
_EPISODE_STANDING_KINDS = ("environment", "sensation", "pose", "scent")
#: A beat's own sound, as the outcome stage mints it: STANDING, keyed by
#: what it says (`ambient_percepts`, `distant_sound_percepts`), so new only
#: on the beat it is heard -- English filed it nowhere (review 2026-10-05).
#: AND A STEADY SOUND'S START AND STOP (DESIGN_SOUND_FIELD § 17, round 2):
#: the room's soundscape, a crowd's hum and the weather's sound
#: (`HABITUATING_SOUND_TAGS`) are keyed by the sound's own state, so they
#: are new on the beat they begin, on a beat they change, and on the beat
#: they stop (`sound_ceased_percept`'s key) -- and on no other: a sound
#: heard every beat is filed once, while the view, which has habituated,
#: says nothing (the owner, 2026-09-26: memory is the priority; "the
#: generator stopped some time in the night" must be recallable).
_EPISODE_SOUND_TAGS = ("ambient", "distant_sound", *HABITUATING_SOUND_TAGS)


def _files_as_memory(p):
    """Does English memory keep this standing percept when it is new or
    changed (appearance has its own ledger and is decided apart)?"""
    if p.kind in _EPISODE_STANDING_KINDS or far_sight(p):
        return True
    return (p.kind == "ambient"
            and str(p.dedupe_key or "").split(":", 1)[0] in _EPISODE_SOUND_TAGS)


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
        rest = [p for p in percepts if p.kind != "residue"]
        if (residue[0].data or {}).get("woke") and rest:
            # THE WOKEN MIND REMEMBERS THE REST OF THE BEAT (§ 17): the
            # waking as the residue tells it, in the first person, then
            # what it perceived from that moment on, filed as any awake
            # mind's episode is. (`_episode_sentence` has already put the
            # residue into the first person.)
            woke = sentence
            content, gist, entities = _render_episode_english(
                rest, prev_standing=prev_standing,
                prev_described=prev_described)
            if content:
                return (woke + " " + content).strip(), gist or woke, entities
            return woke, woke, []
        return sentence, sentence, []

    events = sorted(
        [p for p in percepts if p.order_key is not None],
        key=lambda p: p.order_key)
    # A SILENCE IS ONLY A MEMORY TO AN EAR THAT HAD THE NOISE (D3, § 17):
    # the same verdicts the view renders by, so a stopping this mind's own
    # ledger never earned is filed nowhere.
    verdicts = standing_verdicts(
        [p for p in percepts if p.order_key is None],
        prev_standing, prev_described)
    changed = []
    for p in percepts:
        if p.order_key is not None or is_landscape(p):
            continue
        if p.kind == "appearance":
            if p.data.get("force") \
                    or str(p.data.get("source_key") or "") not in prev_described:
                changed.append(p)
        elif unheard_ceasing(p, verdicts.get(p.dedupe_key, "first")):
            continue
        elif _files_as_memory(p) and p.dedupe_key not in prev_standing:
            # A pose that CHANGED is a real memory -- somebody knelt, or was
            # pinned. An unchanged one is furniture and the dedupe key keeps
            # it out, which is the same rule the room already lives under.
            # A scent lives under it for the same reason and earns its place
            # for a stronger one: a smell is among the most retrievable
            # things a mind stores, and the dedupe key already moves when the
            # grade does, so walking into range of one is the change.
            changed.append(p)

    # FAR PLACES are laid out from every far percept, exactly as the view
    # lays them out, and a line is filed when a place it SHOWS is new or
    # changed -- re-laid from the changed places alone, an episode filed a
    # place the view had trimmed away (review 2026-10-05).
    far_lines = []
    for rep, line in landscape_lines([p for p in percepts if is_landscape(p)]):
        if any(q.dedupe_key not in prev_standing for q in line["shown"]):
            sentence = _cap(render_landscape_line(line, episode=True))
            if sentence:
                far_lines.append((rep, sentence, line["names"]))

    if not events and not changed and not far_lines:
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
    # FAR SIGHT TRAILS EVERYTHING, near to far -- the far places, then the
    # horizon -- and is a memory's gist only when it is all the memory holds:
    # it is where the place sat in view, never what happened (review
    # 2026-10-05: a town's lights at dusk took the gist from the question
    # put to the mind that beat).
    near = [c for c in changed if not far_sight(c)]
    horizon = [c for c in changed if far_sight(c)]
    if events:
        ordering = (events
                    + [c for c in near if c.kind != "environment"]
                    + [c for c in near if c.kind == "environment"])
    else:
        ordering = near

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
    far = []
    for rep, sentence, names in far_lines:
        far.append((rep, sentence))
        for name in names:
            if name.casefold() not in _GENERIC_LABELS and name not in entities:
                entities.append(name)
    for p in horizon:
        sentence = _episode_sentence(p)
        if sentence:
            far.append((p, sentence))
            label = str(p.source_label or "")
            if label.casefold() not in _GENERIC_LABELS and label not in entities:
                entities.append(label)
    sentences += far
    if best is None and far:
        best = far[0]

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


def episode_signature(p):
    """What a percept says in an episode, as a signature two stages can compare
    (the English sentence, whatever the story's language: it is never shown).
    The act stage and the outcome mint one act under different event ids, so
    its `dedupe_key` differs between them while what it says does not
    (`perception.perception_outcome`, 2026-09-30)."""
    if p.kind == "ambient":
        # An act re-minted under a new event id is what this exists for; an
        # ambient line is keyed by what it says already, and a look at a
        # vista said the standing line's words and was dropped as a repeat
        # of it -- in no memory at all (review 2026-10-05).
        return ""
    try:
        return " ".join(str(_episode_sentence(p) or "").split()).casefold()
    except Exception:  # noqa: BLE001 -- a percept no sentence covers has no signature
        return ""


def render_episode(percepts, *, prev_standing=frozenset(),
                   prev_described=frozenset(), language=None, renderer=None):
    """Mint a memory episode through the selected deterministic adapter."""
    percepts = _names_kept(_one_voice_each(percepts))
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
                       "trace": 0.8,
                       # A voice whose words did not carry (§ 12 of the sound
                       # note): fewer of them than a fragment.
                       "voice": 0.75,
                       # A body moving, too little of it to make out: as
                       # ambiguous as a degraded presence, never "rendered"
                       # (it had no entry, and every motion-only act -- a
                       # body still crossing a shut door -- was filed into
                       # memory at the 0.15 of a full sighting).
                       "shapes": 0.5}

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
    """Project each admitted rendered span into its own evidence row.

    A delivery boundary is part of the evidence: merging two actions can
    attach the second actor's conduct to the first, and merging quotes makes
    a narrator read two deliveries as one. There is no row-count cap here.
    Each sentence remains byte-for-byte within the observer's rendered view.
    """
    pid = str(pid)
    out = []
    for index, (percept, sentence) in enumerate(rendered.spans):
        ambiguity = _FIDELITY_AMBIGUITY.get(percept.fidelity, 0.15)
        phase = ("event" if percept.order_key is not None else
                 "change" if percept.data.get("force") or
                 percept.data.get("beat") else "state")
        # A presence sentence can enumerate several bodies. Its first
        # percept is a rendering representative, not the actor of the group.
        actor = percept.source_label if percept.kind != "presence" else ""
        out.append(compact_observation({
            "observation_id": f"current:{pid}:{index}",
            "perceiver_id": pid,
            "source_atom_id": "current",
            "channel": percept.channel,
            "fidelity": "ambiguous" if ambiguity >= 0.5 else "rendered",
            "observed": {"text": sentence},
            **({"actor": actor} if actor else {}),
            "kind": percept.kind,
            "phase": phase,
            **({"order": percept.order_key}
               if percept.order_key is not None else {}),
            "intensity": min(1.0, 0.35 + 0.4 * percept.salience),
            "suddenness": percept.suddenness,
            "ambiguity": ambiguity,
            "directed_at_self": bool(
                percept.data.get("directed_at_self")
                or percept.channel == "interoception"),
            # Retained for archived consumers and the memory boundary.
            "standing": phase == "state",
        }))
    return out


def perception_packet(observations, *, fallback_view=None):
    """Partition already admitted evidence for a character or narrator.

    No scene, identity lookup, prose classifier or model participates here.
    Witnessed events retain delivery order. A noticed change has no inferred
    occurrence time. Standing rows for the same labelled subject are adjacent;
    their exact wording, fidelity and citation ids are preserved.

    Archived observations lacking a phase retain the old standing verdict.
    A string-only archived view remains unstructured context; we cannot
    recover individual events or their times by reading its prose.
    """
    packet = {"events": [], "changes_noticed": [], "current_state": []}
    sections = {"event": "events", "change": "changes_noticed",
                "state": "current_state", "context": "unstructured_context"}
    for observation in observations or ():
        if not isinstance(observation, dict):
            continue
        observed = observation.get("observed")
        if not isinstance(observed, dict) or not str(observed.get("text") or "").strip():
            continue
        if (fallback_view is not None
                and str(observed["text"]).strip() not in str(fallback_view or "")):
            # Some archived observations precede the final view repair.
            # They may not restore wording that the admitted view removed.
            continue
        phase = observation.get("phase")
        row = dict(observation)
        if phase not in sections:
            phase = "state" if observation.get("standing") else "event"
            # Older repairs scrubbed the delivered text without repairing
            # actor metadata. That label cannot newly identify a safe voice
            # on archive replay. Keep the admitted wording; modern rows have
            # an explicit phase and pass the shared actor identity repair.
            row.pop("actor", None)
        packet.setdefault(sections[phase], []).append(row)
    # Source order keys are local to an onset or micro-round. The model
    # sees one accumulated delivery stream, so its ordinal must not restart
    # each time a different speaker takes a turn. Stored rows stay intact.
    for order, event in enumerate(packet["events"], 1):
        event["order"] = order
    # Older views can contain safe sentences whose merged observation was
    # removed by a later identity repair. Preserve any uncovered wording,
    # but never infer events from it. Consume each exact span once so two
    # identical delivered lines still require two matching rows.
    remaining = [str(fallback_view or "")]
    for rows in packet.values():
        for row in rows:
            text = str(row["observed"]["text"])
            for index, fragment in enumerate(remaining):
                at = fragment.find(text)
                if at >= 0:
                    remaining[index:index + 1] = [fragment[:at], fragment[at + len(text):]]
                    break
    context = "\n".join(fragment.strip() for fragment in remaining if fragment.strip())
    if context:
        packet.setdefault("unstructured_context", []).append(
            {"channel": "mixed", "phase": "context", "observed": {"text": context}})
    groups = {}
    for index, row in enumerate(packet["current_state"]):
        actor = str(row.get("actor") or "").strip()
        key = ("actor", actor) if actor else ("unattributed", index)
        groups.setdefault(key, []).append(row)
    packet["current_state"] = [row for group in groups.values() for row in group]
    return packet
