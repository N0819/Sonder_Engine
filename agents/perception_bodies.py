"""A body's outward form: the turn's disguise and transformation reads (and
their caches), what a disguise conceals and its tripwire terms, authored
extra parts, card scents and body descriptions, attire and appearance-ledger
deltas, the observer's own body state, and the bare-region detail parser
(with the dead model-path fidelity floor beside it).

Carved verbatim from `agents/perception.py` on 2026-11-01;
`agents/perception.py` is now a facade that re-exports every name defined
here (docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import re
from language_runtime import (
    LanguagePackError,
    compositor_text,
    compositor_value,
)
from story.character_schema import (
    character_name,
    character_visible_body,
    persona_name,
    persona_visible_body,
)
from story import attire as attire_model
from story.scene import (
    SINGULAR_BODY_CONDITIONS,
    active_disguises,
    active_transformations,
    conceal_disguised_parts,
    transformed_parts,
    transformed_true_appearance,
    disguise_known_to,
    disguised_visible_appearance,
    persona_of,
    scent_of,
    sheet_state,
    visible_body_text,
)
from world.spatial import _entity_named, same_subject
from .common import _append_once, scene_extra_parts


_BODY_DETAIL_GENERIC = frozenset({
    "above", "bare", "below", "between", "body", "exposed", "full", "inner",
    "outer", "skin", "soft", "their", "there", "these", "they", "thigh",
    "thighs", "this", "those", "very", "warm", "with", "within", "your",
})

_SELF_EXPOSED_REGION_CUES = {
    "torso": (
        re.compile(
            r"\byour\b[^.!?\n]{0,28}\b(?:bare|exposed|naked)\b"
            r"[^.!?\n]{0,18}\b(?:chest|breasts?|stomach|abdomen|belly|"
            r"midriff|ribs?|torso)\b", re.I),
        re.compile(
            r"\b(?:chest|breasts?|stomach|abdomen|belly|midriff|ribs?|torso)\b"
            r"[^.!?\n]{0,18}\b(?:bare|exposed|naked)\b", re.I),
    ),
    "groin": (
        re.compile(
            r"\byou\b[^.!?\n]{0,55}\b(?:part|spread|open)\w*\b"
            r"[^.!?\n]{0,35}\b(?:legs|thighs)\b", re.I),
        re.compile(r"\bbetween your\b[^.!?\n]{0,24}\b(?:legs|thighs)\b", re.I),
        re.compile(
            r"\byour\b[^.!?\n]{0,28}\b(?:bare|exposed|naked)\b"
            r"[^.!?\n]{0,18}\b(?:groin|crotch|genitals?|vulva|penis|cock)\b",
            re.I),
    ),
}

_OTHER_EXPOSED_REGION_CUES = {
    "torso": (
        re.compile(
            r"\b(?:her|his|their)\b[^.!?\n]{0,28}\b(?:bare|exposed|naked)\b"
            r"[^.!?\n]{0,18}\b(?:chest|breasts?|stomach|abdomen|belly|"
            r"midriff|ribs?|torso)\b", re.I),
        re.compile(
            r"\b(?:bare|exposed|naked)\b[^.!?\n]{0,18}"
            r"\b(?:chest|breasts?|stomach|abdomen|belly|midriff|ribs?|torso)\b",
            re.I),
    ),
    "groin": (
        re.compile(
            r"\b(?:she|he|they)\b[^.!?\n]{0,55}\b(?:part|spread|open)\w*\b"
            r"[^.!?\n]{0,35}\b(?:her|his|their)?\s*(?:legs|thighs)\b", re.I),
        re.compile(
            r"\b(?:part|spread|open)\w*\b[^.!?\n]{0,35}"
            r"\b(?:her|his|their)\s+(?:legs|thighs)\b", re.I),
        re.compile(
            r"\bbetween (?:her|his|their)\b[^.!?\n]{0,24}\b(?:legs|thighs)\b",
            re.I),
        re.compile(
            r"\b(?:her|his|their)\b[^.!?\n]{0,28}\b(?:bare|exposed|naked)\b"
            r"[^.!?\n]{0,18}\b(?:groin|crotch|genitals?|vulva|penis|cock)\b",
            re.I),
    ),
}


def _bare_body_details(region, surface):
    """Authored bare-surface details carried by one observer-safe region.

    The body-region projection is deliberately prose-shaped for the perception
    model.  This parser reads only the two shapes that projection itself emits:
    a fully bare region (``bare — detail``) or a partially bare zone
    (``midriff: bare — detail``).  Covered-zone and garment descriptions never
    match, so this floor cannot turn a covered chest into anatomy.
    """
    text = str(surface or "").strip()
    if not text:
        return []
    out = []
    for match in re.finditer(
            r"(?:^|;\s*)([a-z_ ]+):\s*bare\s+—\s+(.+?)"
            r"(?=;\s*[a-z_ ]+:|$)", text, re.I | re.S):
        detail = match.group(2).strip()
        if detail:
            out.append((match.group(1).strip().replace("_", " "), detail))
    if out:
        return out
    match = re.match(
        r"^bare\s+—\s+(.+?)(?=;\s*[^;]+\[worn at, covers nothing\]|$)",
        text, re.I | re.S)
    if match and match.group(1).strip():
        return [(str(region or "body region").replace("_", " "),
                 match.group(1).strip())]
    return []


def _authored_detail_already_present(view, detail):
    """Whether the view retained enough distinctive authored wording."""
    view_tokens = set(re.findall(r"[a-z0-9]+", str(view or "").casefold()))
    detail_tokens = []
    for token in re.findall(r"[a-z0-9]+", str(detail or "").casefold()):
        if len(token) >= 4 and token not in _BODY_DETAIL_GENERIC:
            detail_tokens.append(token)
    distinctive = list(dict.fromkeys(detail_tokens))
    if not distinctive:
        return True
    # Two retained concrete traits are enough: prose may legitimately rephrase
    # or compress the card description. One generic region word ("stomach")
    # is not enough, which is exactly the live omission this floor catches.
    required = 1 if len(distinctive) == 1 else 2
    return len(view_tokens.intersection(distinctive)) >= required


def _self_body_detail(detail):
    """An authored third-person body description in a second-person view."""
    text = str(detail or "")
    replacements = (
        (r"\bherself\b", "yourself"), (r"\bHerself\b", "Yourself"),
        (r"\bhers\b", "yours"), (r"\bHers\b", "Yours"),
        (r"\bher\b", "your"), (r"\bHer\b", "Your"),
        (r"\bshe\b", "you"), (r"\bShe\b", "You"),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text)
    return text


def _deliver_foreground_body_details(view, body_regions):
    """Restore authored anatomy the perception model generalized away.

    This is a fidelity floor, not an anatomy dump.  The model first decides
    what the observer notices.  Only when its own view foregrounds an exposed
    surface (for example ``your bare stomach`` or ``you part your legs``) does
    this append the observer-safe authored detail for that region.  The input
    has already crossed garment, darkness, containment, vantage, and identity
    gates in ``observer_body_regions``.
    """
    original = str(view or "")
    additions = []
    rows = [row for row in (body_regions or []) if isinstance(row, dict)]
    paragraphs = [p for p in re.split(r"\n\s*\n", original) if p.strip()]
    for row in rows:
        label = str(row.get("body") or "someone").strip()
        self_view = label.casefold() == "you"
        if self_view:
            relevant_text = original
            cue_map = _SELF_EXPOSED_REGION_CUES
        else:
            relevant_text = "\n".join(
                p for p in paragraphs if label.casefold() in p.casefold())
            cue_map = _OTHER_EXPOSED_REGION_CUES
        if not relevant_text:
            continue
        for region, surface in (row.get("regions") or {}).items():
            patterns = cue_map.get(str(region).casefold()) or ()
            if not patterns or not any(p.search(relevant_text) for p in patterns):
                continue
            for place, detail in _bare_body_details(region, surface):
                if _authored_detail_already_present(original, detail):
                    continue
                rendered = _self_body_detail(detail) if self_view else detail
                subject = (f"Your exposed {place} is visible"
                           if self_view else f"{label}'s exposed {place} is visible")
                addition = f"{subject}: {rendered}".strip()
                if addition[-1:] not in ".!?":
                    addition += "."
                additions.append(addition)
    if not additions:
        return original, []
    return _append_once(original, " ".join(additions)), additions


#: THE TWO STANDING BODY-CONDITION MAPS, READ ONCE PER TURN (review
#: 2026-09-07 C13). Each is one SELECT over `world_conditions` plus a JSON
#: parse per row, and each was re-derived PER BODY PER STAGE: the disguise
#: context reads both for the player and again for every cast member, the
#: tripwire terms read both once more, `_body_descriptions` reads both again
#: for each of the same bodies, and the extra-parts cache reads both on its
#: first miss -- ~4N+6 queries a stage on a cast of N. Counted on a fixture
#: that asks for all four per body: 14 reads at N=1, 75 at N=12, 243 at
#: N=40, against 2 after the memo. A read costs 32.5us and 28.1us against
#: chat 114 on the bench copy, which carries no `world_conditions` rows at
#: all so pays only the round trip, and 65-70us against a fixture with rows
#: to parse.
#:
#: THE MAP IS FIXED FOR THE LENGTH OF A TURN, which is why one read serves
#: every stage. Every engine writer of `world_conditions` is in the commit
#: path (`commit_entities`, `commit_mechanics`) or in a checkpoint restore,
#: and `_run_pipeline` runs its restores before the first step -- so no
#: stage's read can straddle a write. `drop_body_condition_caches` is the
#: seam for the one place that could, and runtime calls it there.
#:
#: On the PipelineContext, never on a module global: a turn builds a fresh
#: ctx, so nothing here survives into the next turn or another chat. The
#: `_composer_extra_parts_cache` precedent, one derivation earlier -- and
#: that cache is a product of these two, so it is dropped with them.
_DISGUISES_CACHE = "_active_disguises_cache"
_TRANSFORMATIONS_CACHE = "_active_transformations_cache"


def _turn_disguises(ctx):
    """Active physical disguises by casefolded subject, once per turn (C13)."""
    cached = ctx.get(_DISGUISES_CACHE)
    if cached is None:
        cached = active_disguises(ctx.chat["id"])
        ctx[_DISGUISES_CACHE] = cached
    return cached


def _turn_transformations(ctx):
    """Active physical transformations by casefolded subject, once per turn."""
    cached = ctx.get(_TRANSFORMATIONS_CACHE)
    if cached is None:
        cached = active_transformations(ctx.chat["id"])
        ctx[_TRANSFORMATIONS_CACHE] = cached
    return cached


def drop_body_condition_caches(ctx):
    """Forget this turn's condition reads and everything derived from them.

    A checkpoint restore rewrites `world_conditions` wholesale mid-run, and
    it also re-reads the cast -- so the extra-parts cache, which is built
    from the cast AND from these two maps, goes with them. Called from
    `runtime._restore_and_refresh`, which is the only place inside a turn
    that changes either input.
    """
    for key in (_DISGUISES_CACHE, _TRANSFORMATIONS_CACHE,
                "_composer_extra_parts_cache"):
        ctx._extra.pop(key, None)


def _subject_disguise_context(ctx, subject_name, true_appearance, known_map):
    """Resolve a subject's active physical_disguise into perception inputs.

    Returns (visible_appearance, disguise_active, known_to_or_None,
    conceals_identity):
    - visible_appearance: what EVERY observer visually perceives -- the
      disguised outward form when a disguise is active (a concealed feature is
      not seen even by someone who knows it is there), else the true
      appearance unchanged.
    - disguise_active: True when a disguise is in force, None when not. It
      used to be a PAYLOAD -- second-person instruction to the perception model
      ("Every observer VISUALLY perceives only outward_visible_appearance")
      plus the `concealed_truth` itself, so an observer in known_to could be
      given the truth as KNOWLEDGE rather than as vision. There is no
      perception model, and the block reached no consumer: it is a flag now,
      and the wording it carried was prompt text with nowhere to be a prompt.
      None rather than False for the absent case, because that is the answer
      every caller and test already reads.
    - known_to: casefolded names that legitimately know the truth, or None.
      LIVE, and the reason the knowledge layer is not entirely gone: it feeds
      `scene.disguise_breaks_recognition`, so a body's acquaintances still
      recognise them through a disguise that conceals identity.
    - conceals_identity: whether this disguise covers what a body is
      RECOGNISED by (a face, a build, a voice) as opposed to a feature it
      merely hides. False for a glamour over fox ears: the face is still
      the face, so anyone who knows her still knows her -- wearing
      unfamiliar ears. See `scene.disguise_breaks_recognition`.

    Feeding the disguised appearance is the primary, fail-safe fix: the view
    is composed FROM the disguised form, so a concealed feature cannot be
    rendered as seen by anybody.

    RESIDUAL, and it is a SUBTRACTION rather than a leak: an observer in
    known_to no longer receives the concealed truth anywhere. They recognise
    the body, and they are not told what is under the disguise. Restoring it
    means putting the truth in the CHARACTER payload -- knowledge is not
    perception, and the percept IR is deliberately about what a channel
    delivered -- which is a design decision beyond removing the dead block.
    """
    # A TRANSFORMATION RESOLVES FIRST, AND IS NOT A DISGUISE. It changes the
    # body's TRUE appearance -- there is no concealed truth, nobody sees
    # through it, and no observer is granted knowledge of an older shape. So
    # it lands here, before the concealment layer, and a body that is merely
    # transformed returns with no disguise payload and no known_to at all.
    key = str(subject_name or "").casefold()
    transformation = _turn_transformations(ctx).get(key)
    true_appearance = transformed_true_appearance(
        true_appearance, transformation)

    disguise = _turn_disguises(ctx).get(key)
    if transformation and disguise:
        # ONE OUTWARD FORM, AND THE TRANSFORMATION IS IT. The two kinds are a
        # singular GROUP (`scene.SINGULAR_BODY_CONDITIONS`), enforced at the
        # write -- but a branch copies conditions wholesale without a write,
        # and rows minted before the rule was written are still out there.
        # Live (chat 74): "you allow your glamour to come undone" minted a
        # `physical_transformation` BESIDE three active disguises instead of
        # ending them, so a body that had just revealed its true form went on
        # presenting the false one. The observer watched the ears rise and
        # then saw human ears again on the very next beat.
        #
        # The transformation wins because it is a statement about the BODY,
        # while a disguise is a statement about what is shown of it -- and a
        # body cannot be concealing a form it no longer has.
        disguise = None
    if not disguise:
        return true_appearance, None, None, False
    known_to = disguise_known_to(disguise, subject_name, known_map)
    visible = disguised_visible_appearance(true_appearance, disguise)
    return visible, True, known_to, bool(disguise.get(
        "conceals_identity"))


def _subject_concealed_terms(ctx, subject_name):
    """Tripwire terms for a body, through the SAME precedence the concealment
    layer uses.

    Read straight from `active_disguises` this was a second source of truth,
    and the two disagreed exactly when it mattered. `_subject_disguise_context`
    drops the disguise when the body is TRANSFORMED -- so it returns
    `known_to=None` -- while the terms came back from the dead disguise anyway.
    The tripwire then held concealed features with nobody marked as knowing
    them, so EVERY observer read as unaware and an aware one got flagged.

    Live (chat 74): Hinami's `glamour_dropped` transformation correctly
    overrode three stale disguise rows, and `perception_outcome` still warned
    that 'fox ears' had leaked to The Doctor -- who is in `known_to`, and who
    by then was looking at ears that were genuinely there. The view was right;
    the warning was noise, and noise on a firewall tripwire is expensive
    because it trains a reader to ignore it.

    A transformed body conceals nothing: it is not hiding a feature, it HAS
    the feature. So there is nothing to tripwire on.
    """
    key = str(subject_name or "").casefold()
    if _turn_transformations(ctx).get(key):
        return []
    return [t for t in ((_turn_disguises(ctx).get(key) or {})
                        .get("concealed_terms") or []) if t]


def _composer_extra_parts(ctx, p_name):
    """Authored structured body parts (tails, wings, horns) by display name.

    Card-read, so a cast with none yields {} and nothing downstream changes.
    The composer's body-region projection is the only consumer now that the
    model payload is gone: the feature reaches a mind through
    `observer_body_regions`, exactly the seam it always used.

    Cached per turn -- three orchestrators ask for it and it is a sheet read
    per cast member.
    """
    cached = ctx.get("_composer_extra_parts_cache")
    if cached is None:
        cached = scene_extra_parts(ctx.cast, persona_of(ctx.chat), p_name)
        # A DISGUISE HIDES THE PARTS TOO, and this is the only place that can
        # make it so. `disguised_visible_appearance` rewrites the appearance
        # SUMMARY; authored extra parts are a separate typed ledger the
        # composer renders straight from structured data, so a glamoured
        # kitsune kept six tails and two fox ears in every view while her
        # summary read "ordinary human ears" (reported live, chat 72).
        # Filtering at this seam rather than at the percept build keeps it
        # ahead of every consumer and out of reach of display-label
        # ambiguity -- these keys are true body names, the percept rows are
        # observer-facing labels and two bodies can share one.
        # TRUTH FIRST, THEN CONCEALMENT. A transformation changes what the
        # body IS -- its list replaces the card's outright, which is what
        # lets it ADD a part no card declares. A disguise then hides what
        # that body currently has. The order is the whole model: you can
        # glamour a transformed body, and the glamour hides the fox's tail
        # rather than the woman's.
        shifted = _turn_transformations(ctx)
        if shifted:
            cached = {
                name: transformed_parts(
                    parts, shifted.get(str(name or "").casefold()))
                for name, parts in (cached or {}).items()
            }
            # A body the card never gave parts to can be given them here.
            for key, form in shifted.items():
                if form.get("parts") and not any(
                        str(n).casefold() == key for n in cached):
                    cached[form.get("subject") or key] = form["parts"]
        cached = conceal_disguised_parts(cached, _turn_disguises(ctx))
        ctx["_composer_extra_parts_cache"] = cached
    return cached


def _body_scents(ctx):
    """{name: standing card scent} for the player and every cast body.

    Read from the cards once per stage rather than threaded through the five
    places a body record is built, so the standing smell has one spelling and
    cannot be present in one stage's view and absent from the next -- which
    is how `entity_state` came to fire on the opening turn only.
    """
    out = {}
    pers = persona_of(ctx.chat)
    if isinstance(pers, dict):
        name = pers.get("name") or persona_name(pers)
        scent = scent_of(pers)
        if name and scent:
            out[str(name)] = scent
    for c in ctx.cast or []:
        sh, _, _ = sheet_state(c)
        name = character_name(sh)
        scent = scent_of(sh)
        if name and scent:
            out[name] = scent
    return out


def _body_descriptions(ctx, sc):
    """{name: the standing body description this body's clothing still shows}
    for the player and every cast body.

    Read from the cards once per stage exactly like `_body_scents`, and for
    the same reason: a standing body fact threaded through the places a body
    record is built ends up present in one stage's view and absent from the
    next.

    A body whose outward form is NOT its own card's is absent from this map
    entirely. A disguise decides what every observer sees, and a
    transformation decides what the body IS -- in both cases the card's own
    face is precisely the thing that is not on show, and delivering it beside
    the form that replaced it would hand every observer the truth the
    condition exists to withhold. The subtraction is the safe direction: a
    body drops back to the description it had before this delivered anything.
    """
    out = {}

    def _own_form(name):
        key = str(name or "").casefold()
        return not (_turn_disguises(ctx).get(key)
                    or _turn_transformations(ctx).get(key))

    pers = persona_of(ctx.chat)
    if isinstance(pers, dict):
        name = str(pers.get("name") or persona_name(pers) or "")
        if name and _own_form(name):
            text = visible_body_text(persona_visible_body(pers), name, sc)
            if text:
                out[name] = text
    for c in ctx.cast or []:
        sh, _, _ = sheet_state(c)
        name = character_name(sh)
        if not name or not _own_form(name):
            continue
        text = visible_body_text(character_visible_body(sh), name, sc)
        if text:
            out[name] = text
    return out


def _own_body_state(sc, name):
    """This observer's own posture, activity and held items, from the scene.

    `body_state_percept` is interoception -- channel "interoception", source
    label "you" -- and it could only ever fire from
    `director_establish.entity_states`, which exists on the opening turn and
    nowhere else. So a mind knew what was in its own hands on turn 0 and
    never again, in an engine whose composer header says exactly why that
    costs something: "a character agent is a stateless LLM call; if it is not
    in context, the mind does not have it".

    The durable home for the same three facts is the scene entity's `state`,
    which `_PROTECTED_STATE_KEYS` already reserves as structural for
    "perception's own deterministic backstop". Posture is the one of the
    three with a second and better home -- `scene.poses`, which
    `pose_percepts` renders with the sight grade and always delivers for the
    observer themselves -- so it is read from here only when the pose ledger
    is silent, rather than said twice.
    """
    state = (_entity_named(sc, name) or {}).get("state")
    if not isinstance(state, dict):
        return {}
    out = {}
    activity = str(state.get("activity") or "").strip()
    if activity:
        out["activity"] = activity
    held = [str(item).strip() for item in (state.get("held_items") or [])
            if str(item or "").strip()]
    if held:
        out["held_items"] = held
    posture = str(state.get("posture") or "").strip()
    if posture and not any(
            same_subject(sc, key, name)
            and str((value or {}).get("posture") or "").strip()
            for key, value in ((sc.get("poses") or {}).items()
                               if isinstance(sc.get("poses"), dict) else ())):
        out["posture"] = posture
    return out


def _attire_items(scene, name):
    """One body's worn items, as a normalised set, or None when unknown."""
    # `entry_for`: a case-variant key read as "unknown" on one side of a
    # before/after pair, so a garment change went unnoticed (2026-09-07 B5).
    row = attire_model.entry_for((scene or {}).get("attire"), name)
    if not row:
        return None
    worn = row.get("wearing")
    if not isinstance(worn, list):
        return None
    return {str(i).strip().casefold() for i in worn if str(i or "").strip()}


def _attire_diff_moves_clothing(entry):
    """Did this attire diff entry move a GARMENT, or only annotate?

    The channel's own vocabulary answers it: `add`, `remove` and `replace`
    are the operations that change what a body wears; `state` is a note
    beside them. Measured over the 384 attire entries in every stored
    `director_resolve` diff, only 46 (12.0%) carry any of the three. 233
    (60.7%) carry `state` alone and 105 are wholly empty -- so seven of
    every eight attire diffs that re-earned a full appearance description
    moved no clothing at all.

    And the `state` notes are mostly not clothing either: "standing in
    genkan threshold", "nine tails fanned behind her", "fox ears visible",
    "facing Tamamo in the doorway". That is pose and posture written into
    the attire ledger, which is the same habit that leaves it holding
    contradictory `bare at the` notes. This function does not try to fix
    that -- it only declines to treat it as a change of dress.
    """
    if not isinstance(entry, dict):
        return True          # unreadable: fail toward describing
    if entry.get("replace"):
        return True
    for field in ("add", "remove"):
        if any(str(item or "").strip() for item in (entry.get(field) or ())):
            return True
    return False


def _outward_form_transitions(diff):
    """The bodies whose OUTWARD FORM changed state THIS BEAT, read from the
    beat's own condition channel.

    A STANDING DISGUISE IS NOT A CHANGE (review 2026-09-07 A37). The line
    this replaces was `if p_disguise: appearance_changed.add(p_name)` --
    true on every beat a disguise was ACTIVE, not on the beat it went up or
    came down. The view survived it (`render_view` asks this observer's own
    ledger before it asks `force`, and a byte-identical description
    suppresses), but the memory renderer has no such ledger to consult:
    `_render_episode_english` counts a forced appearance as changed
    whatever `prev_described` holds, so every NPC in the room minted one
    identical episode per beat for as long as the mask stayed on.

    The transition is the condition ROW, and the beat's diff is where it is
    legible: `world_conditions` is written by the commit, which runs after
    this stage, so the table still holds yesterday's answer here. Both
    directions count -- a row that arrives active is a mask going up, one
    that arrives inactive is a mask coming down, and both are things a
    watcher sees. Both KINDS count too (`scene.SINGULAR_BODY_CONDITIONS`):
    a transformation is a statement about the body and a disguise about
    what is shown of it, and either one moves what an observer is looking
    at. The subjects are returned as the diff spells them; the caller
    matches them to bodies through `same_subject`.
    """
    out = set()
    conditions = (diff or {}).get("conditions")
    if not isinstance(conditions, dict):
        return out
    for rows in conditions.values():
        for row in (rows if isinstance(rows, list) else [rows]):
            if not isinstance(row, dict):
                continue
            if str(row.get("kind") or "").strip().casefold() \
                    not in SINGULAR_BODY_CONDITIONS:
                continue
            subject = str(row.get("subject_id") or row.get("subject")
                          or "").strip()
            if subject:
                out.add(subject)
    return out


def _attire_changed_semantically(prev_scene, scene, name):
    """Did this body's clothing ACTUALLY change, or was it merely re-stated?

    `appearance_changed` fires on the presence of a diff KEY, not on a
    difference: a Director that re-states standing attire re-earns a full
    appearance description that changed nothing. Measured before this gate,
    on the beats whose perception step carries a composer ledger, an
    appearance or attire phrase already delivered the previous beat was
    re-delivered on 19 of 183 of them (10.4%) -- and re-stated attire is the
    same root as the ledger's known habit of accruing contradictory `bare
    at the` notes.

    Unknown on either side is treated as CHANGED: a body whose attire this
    scene does not record cannot be shown to be unchanged, and the direction
    to fail in is delivering the description.
    """
    before, after = (_attire_items(prev_scene, name),
                     _attire_items(scene, name))
    if before is None or after is None:
        return True
    return before != after


def _attire_delta_text(prev_scene, scene, name, language=None):
    """What changed about what this body wears, as the story's own prose.

    Returns "" when nothing readable changed -- the caller then falls back
    to the full description, which is what a scale, overlay or wholesale
    rewrite needs.
    """
    before, after = (_attire_items(prev_scene, name),
                     _attire_items(scene, name))
    if before is None or after is None:
        return ""
    gained = sorted(after - before)
    lost = sorted(before - after)
    if not gained and not lost:
        return ""
    try:
        join = compositor_value("attire_delta_join", language)
    except LanguagePackError:
        join = ", "
    parts = []
    if gained:
        parts.append(compositor_text("attire_gained", language,
                                     items=join.join(gained)))
    if lost:
        parts.append(compositor_text("attire_lost", language,
                                     items=join.join(lost)))
    return join.join(parts)


def _appearance_ledger_value(scene, field, subject):
    """The value one visible-form ledger holds for ``subject``.

    Director channels may address a registered body by its scene key, display
    name, or an alias. Appearance admission must answer whether the resulting
    visible state actually changed, not whether the diff happened to contain a
    key. A restated overlay/scale otherwise re-describes the entire person and
    seeds the narrator with the same card prose every turn.
    """
    values = (scene or {}).get(field) or {}
    wanted = str(subject or "").strip().casefold()
    for key, value in values.items():
        if str(key).strip().casefold() == wanted \
                or same_subject(scene, key, subject):
            return value
    return None


def _appearance_ledger_changed(prev_scene, scene, field, subject):
    return (_appearance_ledger_value(prev_scene, field, subject)
            != _appearance_ledger_value(scene, field, subject))
