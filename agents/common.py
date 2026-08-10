"""Shared coercion, validation, lore, sequence, and perception helpers."""

from __future__ import annotations

import hashlib
import json
import re

import attire as attire_model
import crowds as crowds_model
from character_schema import (
    character_appearance,
    character_knowledge_config,
    character_name,
    character_name_from_text,
    normalize_character_data,
    persona_name,
)
from db import get_setting, q, wget
from llm_quality import complete_validated_json
from memory import chat_lorebook_ids, chat_lorebook_weights
from providers import chat_complete
from scene import get_scene, persona_of, NON_AWAKE_GATED
from schemas import normalize_speech_volume
from spatial import (
    _body_interior_holder,
    ambient_scope,
    containment_conceals,
    entity_arc,
    has_visual,
    hear_level,
    hiding_holders_of,
    nearby_rooms,
    normalize_room_id,
    room_of,
    same_subject,
    visual_level_between,
)
from theory_of_mind import _TOM_CONFIDENCE_CAPS, cap_mind_model_updates

_REACTIVE_VERBS = {
    "attack", "stab", "shoot", "strike", "grab", "restrain",
    "shove", "throw", "charge", "lunge", "block", "steal",
    "cast", "shoot at", "fire at", "swing at",
}

_REACTIVE_STAGES = {
    "preparation", "approach", "contact", "sustained",
}

# Verbs whose act is INTERIOR -- it happens inside the actor's mind and has no
# outward manifestation a bystander could perceive. An observer cannot see
# someone "remember" or "decide"; surfacing such an act to another perceiver
# is a pure information-barrier leak (the actor's private cognition). Used by
# norm_sequence to default an action element's `observable` surface to "" (see
# observable_action_text) so the deterministic perception-delivery backstops
# never paste it into an observer's view. A mental act that DOES have an
# outward tell (eyes going distant, a whispered incantation) can still be
# delivered -- the director just authors an explicit `observable` for it,
# which overrides this default.
_MENTAL_VERBS = {
    "recall", "remember", "recollect", "consider", "think", "ponder",
    "reflect", "deliberate", "decide", "resolve", "realize", "realise",
    "understand", "know", "recognize", "recognise", "plan", "intend",
    "imagine", "visualize", "visualise", "concentrate", "focus", "sense",
    "feel", "believe", "assume", "wonder", "hope", "fear", "doubt",
}

# Outcomes only the person undergoing them may declare: interior volition
# (agreeing, submitting, giving in) and involuntary body events (fainting,
# panicking, knees buckling). AGENTS.md's AUTHORITY STOPS AT OTHER MINDS makes
# these the character's own to enact, so a player-authored element whose
# SUBJECT is a cast member and whose outcome is one of these is rerouted to
# that character as an OFFER rather than enacted as objective truth (see
# director._route_authorial_npc_beat). A player act that merely CAUSES such an
# outcome ('stabs Sarah') is untouched -- the player is the agent there, and
# the target's response is resolved through the reaction phase.
_AUTONOMY_VERBS = {
    "orgasm", "climax", "cum", "submit", "surrender", "yield", "relent",
    "succumb", "capitulate", "obey", "comply", "consent", "agree",
    "acquiesce", "relax", "calm", "panic", "faint", "swoon", "buckle",
    "forgive", "trust", "crave", "desire", "enjoy", "overwhelm",
}

_AUTONOMY_PHRASES = (
    "over the edge", "gives in", "give in", "lets go", "let go",
    "loses control", "lose control", "cannot hold", "can't hold",
    "cannot resist", "can't resist", "cannot help", "can't help",
    "falls in love", "changes her mind", "changes his mind",
    "changes their mind", "makes up her mind", "makes up his mind",
)

# Words that can OPEN a clause without being its verb. A player action element
# is authored verb-first by convention ('takes a deep breath...'), so an
# attempt opening with one of these is a noun/pronoun-led clause -- somebody
# or something OTHER than the declaring player is its subject.
_SUBJECT_LEADS = {
    "the", "a", "an", "this", "that", "these", "those", "his", "her",
    "their", "its", "my", "your", "our", "he", "she", "they", "it",
}


def _stem_token(tok):
    """Crude suffix stem for verb matching ('remembers' -> 'remember')."""
    for suf in ("ing", "es", "ed", "s"):
        if len(tok) > len(suf) + 2 and tok.endswith(suf):
            return tok[:-len(suf)]
    return tok


# Where one subject's predicate ends. Used to scope the autonomy test to the
# clause that actually belongs to the named character -- see
# _predicate_after_name.
_CLAUSE_BREAKS = re.compile(
    r"\b(?:and|but|as|while|then|so|because|before|after|until|when|though)\b"
    r"|[,;:—]")


def _predicate_after_name(text_cf, end):
    """The clause remainder belonging to a subject whose name ends at `end`.

    The autonomy vocabulary is deliberately made of ordinary words ('relax',
    'agree', 'enjoy'), so testing for them ANYWHERE in an attempt made any
    sentence containing one read as puppeting: 'Sarah steps back and I enjoy
    the view' rerouted the player's own step-back into an offer for Sarah, and
    'her grip doesn't yield as I push against Sarah' rerouted a push. Cutting
    at the first coordinator or clause break keeps the test on the predicate
    the character is actually the subject of -- 'steps back', not '...and I
    enjoy the view'."""
    tail = text_cf[end:].lstrip(" '’,")
    cut = _CLAUSE_BREAKS.search(tail)
    return tail[:cut.start()] if cut else tail


def _is_autonomous_response(verb, text):
    """True when the described outcome is a volitional or involuntary response
    that belongs to the person having it -- submitting, panicking, giving in.

    `text` must already be scoped to ONE subject's predicate (see
    _predicate_after_name); this scans all of it rather than only the leading
    token, because the construction that matters routinely buries the verb
    ('...pushes Dr. Moon over the edge')."""
    v = str(verb or "").strip().casefold()
    if v in _AUTONOMY_VERBS or _stem_token(v) in _AUTONOMY_VERBS:
        return True
    low = str(text or "").casefold()
    if any(phrase in low for phrase in _AUTONOMY_PHRASES):
        return True
    return any(
        tok in _AUTONOMY_VERBS or _stem_token(tok) in _AUTONOMY_VERBS
        for tok in re.findall(r"[a-z']+", low)
    )


def _is_mental_action(verb, attempt):
    """True when an action element is purely interior (no outward surface):
    its declared verb is a mental verb, or -- for a weak model that left verb
    unset -- its attempt LEADS with a mental verb ('remember the runes her
    mother taught her'). Conservative: only the leading token is checked, so a
    physical act that merely mentions thought later ('carve while recalling
    the shape') is NOT suppressed."""
    v = str(verb or "").strip().lower()
    if v in _MENTAL_VERBS or _stem_token(v) in _MENTAL_VERBS:
        return True
    head = re.split(r"[^\w]+", str(attempt or "").strip().lower(), maxsplit=1)
    lead = head[0] if head else ""
    return bool(lead) and (lead in _MENTAL_VERBS or _stem_token(lead) in _MENTAL_VERBS)


def observable_action_text(elem):
    """The outward, intent-free surface of an action element for delivery to
    OTHER perceivers -- what a bystander literally sees/hears, never the
    actor's purpose, magical intent, or private mental content.

    Prefers the director-authored `observable` surface. An explicit empty
    string means the act has no outward manifestation (a purely mental beat --
    recalling, deciding) and returns "" so the caller SKIPS it. Only when the
    element predates the field entirely (key absent -- e.g. an un-normalized
    character declaration) does it fall back to the raw `attempt`, preserving
    legacy delivery for paths norm_sequence does not touch."""
    obs = elem.get("observable")
    if obs is None:
        return str(elem.get("attempt") or "")
    return str(obs or "")

ATTEMPT_CUES = (
    "try", "attempt", "aim", "rush", "lunge", "swing at", "reach for",
    "move toward", "charge", "throw at", "shoot at", "fire at",
    "grab for", "lunge at", "dive for", "reach toward",
)

ASSERTION_SKIP_CUES = (
    "try", "attempt", "aim ", "try to", "attempt to",
)

def _dict(value):
    return value if isinstance(value, dict) else {}

def _list(value):
    return value if isinstance(value, list) else []

def _dict_list(value):
    return [item for item in _list(value) if isinstance(item, dict)]

def _text_piece(value) -> str:
    """Normalize heterogeneous values for retrieval queries."""
    if value is None or isinstance(value, bool):
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(
                value,
                ensure_ascii=False,
                sort_keys=True,
            )
        except (TypeError, ValueError):
            return ""
    return str(value).strip()

def _join_text(values) -> str:
    """Safely join retrieval-query components."""
    parts = [_text_piece(value) for value in values]
    return " ".join(part for part in parts if part)

def _assert_plan_materialized(turn_id, plan, ctx):
    """Verify that every planned step produced one active result."""
    expected = [key for key, _ in plan]

    rows = q(
        """
        SELECT
            s.key,
            COUNT(v.id) AS active_count
        FROM steps s
        LEFT JOIN variants v
          ON v.step_id=s.id
         AND v.active=1
        WHERE s.turn_id=?
        GROUP BY s.key
        """,
        (turn_id,),
    )

    active_counts = {
        row["key"]: int(row["active_count"])
        for row in rows
    }

    missing_context = [
        key
        for key in expected
        if key not in ctx
    ]

    invalid_results = [
        key
        for key in expected
        if active_counts.get(key, 0) != 1
    ]

    if missing_context or invalid_results:
        details = []

        if missing_context:
            details.append(
                "missing from context: "
                + ", ".join(missing_context)
            )

        if invalid_results:
            details.append(
                "without exactly one active variant: "
                + ", ".join(invalid_results)
            )

        raise RuntimeError(
            "Pipeline completion invariant failed; "
            + "; ".join(details)
        )

def _character_by_id(ctx, char_id):
    return next(row for row in ctx.cast if int(row["id"]) == int(char_id))

def _conceal_from_targets_observer(conceal_from, observer_id, observer_sheet):
    """True if any conceal_from entry names this observer -- matched by
    numeric id, string id, display name, uid, or alias. conceal_from is an
    absolute exclusion list authored against whatever identity handle the
    speaker knew, so a reader must resolve it against ALL of the observer's
    handles (same tolerance character_room/canonicalize_positions apply)."""
    if not conceal_from:
        return False
    id_forms = {str(observer_id).strip()}
    try:
        keys = {k.casefold() for k in character_scene_keys(observer_sheet)}
    except Exception:
        keys = set()
    for entry in conceal_from:
        if isinstance(entry, bool):
            continue
        if isinstance(entry, int):
            if str(entry) in id_forms:
                return True
            continue
        text = str(entry or "").strip()
        if not text:
            continue
        if text in id_forms or text.casefold() in keys:
            return True
    return False

def _concat_dedup(*value_lists):
    """Union-concatenate list-of-dicts update fields, preserving order and
    dropping exact duplicates (a re-emitted identical update across rounds)."""
    out, seen = [], set()
    for values in value_lists:
        for item in _list(values):
            try:
                key = json.dumps(item, sort_keys=True, ensure_ascii=False)
            except (TypeError, ValueError):
                key = repr(item)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
    return out

def _merge_character_results(existing, new):
    """Combine a character's earlier-round result with a later one instead of
    overwriting. A character who speaks in more than one micro-round would
    otherwise lose its round-0 sequence/mind_model_updates/etc. at commit,
    which reads ctx.character_results[id] as a single result. Latest scalar
    state (active_state, interaction, salience) wins; the accumulating list
    fields are unioned so no round's declared behavior or inference is lost."""
    if not isinstance(existing, dict):
        return new
    if not isinstance(new, dict):
        return existing
    merged = dict(new)
    merged["sequence"] = _list(existing.get("sequence")) + _list(new.get("sequence"))
    for field in (
        "mind_model_updates",
        "relationship_updates",
        "stance_updates",
        "inference_updates",
        "intent_ops",
        "belief_updates",
        "association_updates",
        "present_evidence_used",
        "memory_evidence_used",
        "observations_used",
        "remember_lines",
        "memory_disputes",
        "memory_effects",
        "contact_ops",
        "material_effects",
    ):
        combined = _concat_dedup(existing.get(field), new.get(field))
        if combined or field in existing or field in new:
            merged[field] = combined
    if not new.get("active_state") and existing.get("active_state"):
        merged["active_state"] = existing.get("active_state")
    if not new.get("ponder") and existing.get("ponder"):
        merged["ponder"] = existing.get("ponder")
    # No-op/null means preserve the prior micro-round's explicit decision;
    # start/stop are both truthy dicts and the later explicit one wins.
    if not new.get("follow_op") and existing.get("follow_op"):
        merged["follow_op"] = existing.get("follow_op")
    return merged

def _contextual_rooms(sc, cast, *extra_room_ids, hops=1):
    """The rooms dict to actually serialize into a stage's LLM payload:
    every occupied room (cast members' current rooms plus any extra room
    ids the caller supplies, e.g. the player's room) and their immediate
    neighbors, rather than the full scene.rooms dict. See
    spatial.nearby_rooms for why this exists. Callers must keep using the
    full, unfiltered scene for any deterministic spatial check.
    """
    centers = set()
    for row in cast:
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        r = room_of(sc, character_name(sheet))
        if r:
            centers.add(r)
    for extra in extra_room_ids:
        if extra:
            centers.add(extra)
    return nearby_rooms(sc, centers, hops=hops)

# Entity fields that exist so CODE can resolve a reference, not because an
# observer could perceive them. See _perceptible_entities.
_ENTITY_LOOKUP_ONLY_FIELDS = ("aliases",)


def _beneath_visible():
    """Whether what is under someone's clothing is spelled out at all.

    Off unless the host turns it on. What a card authors per region as
    `beneath` is explicit body description, and a default that starts
    narrating it the first time a coat comes off is not a default anyone
    chose. With this off the region still reports itself as bare -- the
    exposure is objective and the story needs it -- and the body's own
    appearance is what fills the rest, which is where it lived before regions
    existed.
    """
    return str(get_setting("attire_beneath") or "").strip().casefold() in (
        "1", "on", "true", "yes")


def attire_view(entry, body=""):
    """One body's clothing as a stage should see it.

    The flat `wearing`/`state` pair stays, because that is the shape the
    Director writes back in `attire:{name:{add,remove,...}}`. Alongside it goes
    one line per region, which is the only representation that can say a robe
    is open rather than merely present -- and the only one that can say a
    region is bare while the body is still dressed.
    """
    if not isinstance(entry, dict):
        return {}
    # Through `rederive_entry`, not straight off the stored dict. `wearing` and
    # `state` used to be passed through verbatim while only `regions` was
    # normalised, so this view could -- and did -- hand a character a coherent
    # region breakdown next to a flat list contradicting it. Live in chat 52:
    # the regions were clean and `wearing` still read
    # `[... 'corset', 'worn', 'skirt']`, with a phantom garment named after a
    # state, because every repair to the ledger's normalisation was bypassed
    # for exactly the two fields anyone reads first.
    #
    # A read path, so this presents the three representations agreeing without
    # writing anything back; commit still owns the stored shape.
    coherent = attire_model.rederive_entry(entry)
    regions = coherent.get("regions") or {}
    lines = attire_model.describe(
        regions, beneath_visible=_beneath_visible(), body=body)
    exposed = attire_model.exposed_regions(regions)
    partial = attire_model.partially_exposed_regions(regions)
    return {
        "wearing": coherent.get("wearing") or [],
        "state": coherent.get("state") or [],
        **({"regions": lines} if lines else {}),
        # Stated rather than left to be worked out from the lines above. What
        # a body shows is exactly this list -- a garment that is loosened or
        # hanging open is still ON, and a region nobody has mentioned is
        # unmodelled rather than bare, so neither appears here.
        **({"exposed": exposed} if exposed else {}),
        **({"partially_exposed": partial} if partial else {}),
    }


def scene_attire_view(sc):
    """`attire_view` across every body in the scene."""
    return {
        name: attire_view(entry)
        for name, entry in (sc.get("attire") or {}).items()
        if isinstance(entry, dict)
    }


# How much of a garment's appearance rides in a payload. The Director is the
# only path by which what a thing looks like reaches prose, so it gets enough
# to describe with; a character looking at their own clothes gets the same,
# because a body knows what it is wearing.
ATTIRE_LOOK_CHARS = 60


def compact_attire(entry, look=ATTIRE_LOOK_CHARS):
    """One body's clothing as a single line -- see `attire.compact_line`.

    Replaces the multi-field `attire_view` in PAYLOADS only. Measured on chat
    67: the view sent to the Director was 3,789 chars, this is 1,314 -- 65%,
    ~618 tokens off every resolve call. `attire_view` itself stays as it is for
    panels and anything that wants the structured shape.

    Rederived rather than read raw, for the reason `attire_view` gives: the
    stored `wearing`/`state` pair and `regions` could disagree, and this must
    render the reconciled truth. It is also what migrates a LEGACY body -- a
    story whose attire predates regions entirely -- into regions on read, so
    an old chat needs no backfill to be rendered by this.
    """
    if not isinstance(entry, dict):
        return ""
    regions = (attire_model.rederive_entry(entry) or {}).get("regions") or {}
    return attire_model.compact_line(
        regions, beneath_visible=_beneath_visible(), look=look)


def scene_compact_attire(sc, look=ATTIRE_LOOK_CHARS):
    """`compact_attire` across every body in the scene."""
    return {
        name: compact_attire(entry, look=look)
        for name, entry in (sc.get("attire") or {}).items()
        if isinstance(entry, dict)
    }


def region_visibility(sc, observer, body, entry=None):
    """Which of one body's regions THIS observer can see, and what conceals
    the rest -- concealment, applied to bodies instead of acts.

    Returns every region in `attire.REGIONS`, in anatomical order, in the
    vocabulary concealed action already uses:

        {"torso": {"visibility": "concealed", "by": {"garments": ["kimono"]}},
         "hands": {"visibility": "overt"},
         ...}

    `by` is a one-key dict naming the KIND of concealer alongside the
    concealers themselves, and the kinds are exactly the three the engine can
    already answer for:

      - `garments` -- what `attire.concealing_garments` says still covers the
        region. A garment that only attaches never appears here: a hair clip
        is present without covering.
      - `containment` -- the body is shut inside something the observer is
        outside (or the observer is shut inside something themselves), read
        through `hiding_holders_of`/`containment_conceals` so the parented
        interior-room form conceals exactly as the `contained` ledger form
        does.
      - `vantage` -- the observer's own position is what fails: the body is in
        their rear arc (`entity_arc`, the `behind_sources` rule -- no NEW
        visual detail from a blind spot), or `visual_level_between` answers
        `none`/`shapes` for darkness, barriers, or distance. At `shapes` a
        silhouette shows presence and outline, not what is worn or bare, so
        every region is concealed -- the same reading `_co_present_company`
        gives an unrecognised figure.

    DERIVED, NEVER STORED. `wearing`/`state`/`regions` are already three
    representations of one wardrobe and they drifted until `rederive_entry`
    existed; a stored per-region `visible` flag would be a fourth with the
    same failure mode and no new information. This is a pure read: the
    coverage half comes from the reconciled regions (which also migrates a
    legacy flat-list body on read), the observer half from the scene, and
    nothing is written anywhere.

    Per-observer on purpose -- the point of the transfer from `conceal_from`.
    Two observers of one body get different answers when one stands behind it,
    or outside the wardrobe it is hiding in. A body is never concealed from
    itself by containment or vantage (`same_subject`, not `==` -- a being
    routinely carries a display name and an entity id at once): a perceiver is
    never sealed from themselves and is never in their own blind spot. Their
    own garments still conceal their regions, because covered is covered.

    Safe-closed: an observer the scene cannot place sees nothing, which is the
    same answer every other spatial query gives for `unknown`.
    """
    sc = sc if isinstance(sc, dict) else {}
    if entry is None:
        ledger = sc.get("attire") or {}
        entry = ledger.get(body)
        if entry is None:
            key = str(body or "").strip().casefold()
            entry = next((value for name, value in ledger.items()
                          if str(name).strip().casefold() == key), None)
    regions = {}
    if isinstance(entry, dict):
        regions = (attire_model.rederive_entry(entry) or {}).get("regions") or {}
    cover = attire_model.concealing_garments(regions)

    body_level = None
    if not same_subject(sc, observer, body):
        level = visual_level_between(sc, observer, body)
        if level != "full":
            # Attribution only: whether sight fails is spatial's composed
            # answer (light, barriers, containment, crossing grace), never
            # re-derived here where a second copy of that policy would drift.
            if containment_conceals(sc, observer, body):
                holders = (hiding_holders_of(sc, body)
                           or hiding_holders_of(sc, observer))
                body_level = {"containment":
                              [str(holders[0])] if holders else []}
            else:
                body_level = {"vantage": ["seen only in silhouette"
                                          if level == "shapes"
                                          else "out of sight"]}
        elif entity_arc(sc, observer, body) == "rear":
            body_level = {"vantage": ["behind the observer"]}

    out = {}
    for region in attire_model.REGIONS:
        if body_level is not None:
            out[region] = {"visibility": "concealed", "by": dict(body_level)}
        elif region in cover:
            out[region] = {"visibility": "concealed",
                           "by": {"garments": list(cover[region])}}
        else:
            out[region] = {"visibility": "overt"}
    return out


def observer_body_regions(sc, observer, body_labels=None):
    """Observer-safe attire/body surfaces for a perception payload.

    ``body_labels`` maps canonical scene subjects to labels already safe for
    this observer (``you``, a recognized name, or an appearance-derived
    descriptor).  Canonical keys are never emitted.  Vantage/containment
    concealment removes a region entirely; garment concealment exposes only
    the garment surface, while an overt region may expose its authored
    ``beneath`` description when the host enabled that feature and a garment
    has actually been removed there.
    """
    sc = sc if isinstance(sc, dict) else {}
    labels = dict(body_labels or {str(observer): "you"})
    ledger = sc.get("attire") or {}
    results = []
    for body, label in labels.items():
        entry = ledger.get(body)
        if entry is None:
            folded = str(body or "").strip().casefold()
            entry = next((value for key, value in ledger.items()
                          if str(key).strip().casefold() == folded), None)
        if not isinstance(entry, dict):
            continue
        coherent = attire_model.rederive_entry(entry) or {}
        regions = coherent.get("regions") or {}
        surfaces = attire_model.perceptible_region_surfaces(
            regions, beneath_visible=_beneath_visible())
        visibility = region_visibility(sc, observer, body, entry=coherent)
        delivered = {}
        for region in attire_model.REGIONS:
            surface = surfaces.get(region)
            if not surface:
                continue
            verdict = visibility.get(region) or {}
            cause = verdict.get("by") or {}
            if verdict.get("visibility") == "concealed" \
                    and "garments" not in cause:
                continue
            delivered[region] = surface
        if delivered:
            results.append({"body": str(label or "someone"),
                            "regions": delivered})
    return results


CROWDS_KEY = crowds_model.CROWDS_WORLD_KEY


def crowds_for_room(cid, sc, room_id):
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
    """
    from db import wget

    if not room_id:
        return []
    room = ((sc or {}).get("rooms") or {}).get(room_id) or {}
    size = room.get("size")
    out = []
    for crowd in crowds_model.crowds_in_room(wget(cid, CROWDS_KEY, []) or [],
                                             room_id):
        out.append({
            "uid": crowd.get("uid"),
            "what": crowds_model.describe(crowd, size),
            "density": crowds_model.density(crowd.get("band"), size),
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
        })
    return out


def _perceptible_entities(sc, perceiver_names=None):
    """The entities dict to serialize into a PERCEPTION payload.

    Perception is handed the objective entity table so it can describe what
    is present -- but an entity carries two kinds of string. Its `name` and
    `description` are what an observer standing there could actually take
    in. Its `aliases` and its dict KEY are lookup handles, written for
    commit.track_background_presences and background._name_to_entity_id to
    match against, and an observer has no way to acquire that vocabulary.

    Handing both to the model let the vocabulary leak. Observed live
    (Elevator Adventure branch 41, turn 91): entity `tardis_001`, display
    name "Blue Police Box", aliases ["tardis", "box", "police box"]. Dr.
    Moon's own view came back "The TARDIS looms behind her, still wheezing
    as its temporal engines wind down" -- a word she has never heard, in
    the same sentence where the man himself was correctly anonymized as
    "the lean energetic man" (identities are scrubbed by
    _scrub_unknown_identities; object vocabulary was not).

    So the lookup handles do not go in: entities are keyed by display name
    where that is unambiguous, and aliases are dropped. A character who
    legitimately knows what the thing is knows it from their own sheet and
    memory -- which is where that knowledge belongs.

    `state` is the SECOND thing this table carries that an observer may have
    no channel to. The Director writes it as objective fact, in act-naming
    language -- `state.posture` and `state.proximity` spell out what a body
    is doing and where it is doing it. Observed live: a body shut inside a
    container had its every act written out in `state` while no perceiver in
    the call had any sight of it at all. That is the same shape as the alias
    leak above -- objective state handed over with an implicit instruction
    not to use it -- and the same argument applies: when NOBODY in this call
    can perceive the entity, none of them has a legitimate use for what it is
    doing, so it does not go in.

    `perceiver_names` is who the payload is being built for. Concealment is
    decided by containment only (spatial.containment_conceals): an entity in
    the open is unaffected, so this is inert for the ordinary scene and bites
    exactly on the enclosed case that motivated it. The entity still appears
    -- only `state` is withheld -- because presence may reach the perceiver
    through contact or sound even when nothing else does. Omitted (the
    default) keeps the whole table, which is right for callers that have no
    perceiver set to gate against.
    """
    entities = (sc or {}).get("entities") or {}
    if not isinstance(entities, dict):
        return entities

    names = [str(n).strip() for n in (perceiver_names or []) if str(n or "").strip()]
    _inhabited_by_a_perceiver = {
        holder for holder in (_body_interior_holder(sc, n) for n in names)
        if holder
    }

    def _state_reaches_anyone(ent_name):
        if not names or not ent_name:
            return True
        return any(not containment_conceals(sc, observer, ent_name)
                   for observer in names)

    by_name = {}
    for eid, ent in entities.items():
        if isinstance(ent, dict):
            name = str(ent.get("name") or "").strip()
            if name:
                by_name.setdefault(name.casefold(), []).append(eid)

    projected = {}
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            projected[eid] = ent
            continue
        name = str(ent.get("name") or "").strip()
        # Keep the id when the name is missing or shared, so two entities
        # never collapse into one payload entry.
        key = name if name and len(by_name.get(name.casefold(), ())) == 1 \
            else eid
        drop = set(_ENTITY_LOOKUP_ONLY_FIELDS)
        if not _state_reaches_anyone(name or eid):
            drop.add("state")
        if eid in _inhabited_by_a_perceiver:
            # YOU CANNOT SEE THE OUTSIDE OF WHAT YOU ARE STANDING INSIDE.
            # `description` is an entity's EXTERIOR -- what a body in the room
            # around it takes in. Handed to its own occupant it reads as a
            # thing across the way. Live (chat 58, t38): the player stood in
            # the TARDIS console room and her view had "a blue police box --
            # its paint darkened by rain -- settles with a heavy thud on the
            # cobbles", which is the box she was standing in, landing, seen
            # from inside itself.
            #
            # The entity itself STAYS -- the room's own `parent_entity`
            # already tells the reader what they are inside, and presence is
            # not the leak. Only the outward appearance goes. (`state` is
            # separately withheld here by the containment gate above, which
            # predates this and is not changed by it.)
            drop.add("description")
        projected[key] = {k: v for k, v in ent.items() if k not in drop}
    return projected


def _char_known_tags(sheet):
    config = character_knowledge_config(sheet)
    tags = [tag for tag in ("common", "scholarly", "esoteric") if config.get(tag)]
    return tags, config.get("excluded_titles") or []

def _character_display_name(row):
    return character_name_from_text(row["sheet"])

def _normalize_scene_patch(value):
    patch = dict(value or {})
    for key in ("rooms", "entities", "positions", "stations"):
        if not isinstance(patch.get(key), dict):
            patch[key] = {}
    for key in ("remove_entities", "remove_rooms", "remove_adjacent"):
        if not isinstance(patch.get(key), list):
            patch[key] = []
    return patch

def _sequence_has_content(result):
    return any(
        (event.get("text") if event.get("type") == "speech"
         else event.get("attempt"))
        for event in (result.get("sequence") or [])
        if isinstance(event, dict)
    )

def _asks_player(result, chat, cast=None):
    player_name = persona_name(persona_of(chat))
    interaction = _dict(result.get("interaction"))
    addresses = {
        str(v).casefold()
        for v in _list(interaction.get("addresses"))
    }
    aliases = {"player", "the player", "you", player_name.casefold()}
    if addresses & aliases:
        return True
    # The trailing-"?" fallback (a speech line ending in "?" is treated as a
    # question awaiting the player) must fire ONLY when the speaker didn't
    # aim the line at a specific cast member. An NPC asking ANOTHER NPC a
    # question ("Reya, are you sure?") is not awaiting the player, and using
    # "?" alone to end the loop there strands an NPC<->NPC exchange as if the
    # player had been addressed. So: if `addresses` names a registered cast
    # member (and not the player, handled above), never apply the fallback.
    cast_names = set()
    for row in (cast or []):
        try:
            cast_names.add(character_name_from_text(row["sheet"]).casefold())
        except Exception:
            continue
    if addresses & cast_names:
        return False
    for event in _dict_list(result.get("sequence")):
        if event.get("type") != "speech":
            continue
        text = str(event.get("text") or "").strip()
        if text.endswith("?"):
            return True
    return False

def _next_speaker_candidates(ctx, last_actor_id, perceived_by, already_spoke):
    candidates = []
    for row in ctx.cast:
        char_id = int(row["id"])
        if char_id == last_actor_id or char_id not in perceived_by:
            continue
        result = _dict(ctx.character_results.get(char_id))
        interaction = _dict(result.get("interaction"))
        priority = float(interaction.get("urgency", 0.0))
        if char_id not in already_spoke:
            priority += 0.2
        candidates.append((priority, char_id))
    candidates.sort(reverse=True)
    return [char_id for _, char_id in candidates]

def _element_effect_text(elem):
    """Every effect `kind` an action element declares, joined for text tests."""
    effects = list(_list(elem.get("intended_effects"))) + list(
        _list(elem.get("asserted_effects")))
    return " ".join(
        str(eff.get("kind") or "") for eff in effects if isinstance(eff, dict))


def authored_other_subject(elem, name_forms, actor_forms=()):
    """The cast id whose OWN cognition, volition, or involuntary response a
    player-authored action element declares -- or None when the element is the
    player's own act.

    `name_forms` maps cast id -> casefolded name/alias forms identifying that
    character; `actor_forms` are the declaring player's own forms.

    Two shapes are caught, both requiring another mind to be the SUBJECT of an
    interior or autonomous outcome:
      1. the element OPENS with a cast member's name ('Dr. Moon remembers she
         has her phone', 'Dr. Moon gives in');
      2. a noun/pronoun-led clause names exactly one cast member as the
         experiencer of such an outcome ('the strain finally pushes Dr. Moon
         over the edge') -- the same puppeting written indirectly, which the
         leading-subject rule alone misses.

    A verb-led attempt is the player's own predicate by the sequence
    convention, and an attempt the player leads by name is theirs, so neither
    is rerouted -- 'stabs Sarah' stays the player's act and Sarah's response
    is resolved through the reaction phase. A physical NPC beat with no
    interior or autonomous outcome ('Dr. Moon steps back') is likewise left
    for the world/perception path.

    The autonomy test is applied to the clause the named character is the
    SUBJECT of, never to the whole attempt -- dropping a player-declared act
    because a later clause happens to contain an ordinary word like 'enjoy'
    would violate the Director's own floor against silently replacing the
    player's declared action (AGENTS.md)."""
    if not isinstance(elem, dict) or elem.get("type") != "action":
        return None
    att = str(elem.get("attempt") or "").strip()
    low = att.casefold()
    if not low:
        return None

    def _predicate_is_autonomous(predicate):
        return (_is_mental_action(None, predicate)
                or _is_autonomous_response(None, predicate))

    # Shape 1: the attempt OPENS with a cast member's name, so the declared
    # verb and the clause that follows are both that character's predicate.
    for cid, forms in (name_forms or {}).items():
        for form in forms:
            if not any(low.startswith(form + suf) for suf in (" ", "'", "’")):
                continue
            if (_is_mental_action(elem.get("verb"), "")
                    or _is_autonomous_response(
                        elem.get("verb"), _element_effect_text(elem))
                    or _predicate_is_autonomous(
                        _predicate_after_name(low, len(form)))):
                return cid
            return None

    # Shape 2: a noun/pronoun-led clause names exactly one cast member as the
    # experiencer. The declared verb belongs to the leading noun here, not to
    # the character, so ONLY the clause following their name can qualify --
    # otherwise 'I remember Dr. Moon's face' (verb: remember) would reroute the
    # player's own recall into an offer for Dr. Moon.
    lead_tokens = re.split(r"[^\w']+", low, maxsplit=1)
    lead = lead_tokens[0] if lead_tokens else ""
    if lead in {str(f).casefold() for f in (actor_forms or ())}:
        return None
    if lead not in _SUBJECT_LEADS:
        return None
    named = []
    for cid, forms in (name_forms or {}).items():
        for form in forms:
            hit = re.search(rf"\b{re.escape(form)}\b", low)
            if hit:
                named.append((cid, hit.end()))
                break
    if len(named) != 1:
        return None
    cid, name_end = named[0]
    return cid if _predicate_is_autonomous(
        _predicate_after_name(low, name_end)) else None


def bind_sequence_targets(sequence, target_forms):
    """Fill an action element's EMPTY `targets` with the display names of the
    cast members its own text names.

    The director routinely emits an act that plainly lands on a character with
    `targets: []` -- and every downstream seam that asks "does this land on
    another body?" (the reaction-phase gate, claim subject binding, perception's
    targeted-observer check) reads `targets`, so an unbound act is invisible to
    all of them. Binding is by NAME because `ActionElement.targets` is typed as
    display names and perception matches them casefolded. Only ever ADDS a
    binding the text already supports; an element the director bound itself is
    left untouched.

    Deliberately does NOT mirror the name onto effects that left `target_id`
    null. A mention is evidence the act CONCERNS that character, which is all
    `targets` claims; an effect's `target_id` is the stronger claim that the
    outcome LANDS on them, and inferring it from the same mention manufactured
    authority claims the director never authored ('dodge away from Sarah' does
    not put an effect on Sarah). `_extract_authority_claims` reads the same
    name evidence through its own `target_forms` guard instead."""
    bound = 0
    for elem in _dict_list(sequence):
        if elem.get("type") != "action" or elem.get("targets"):
            continue
        haystack = f"{elem.get('attempt') or ''} {_element_effect_text(elem)}".casefold()
        if not haystack.strip():
            continue
        names = []
        for display, forms in (target_forms or {}).items():
            if any(re.search(rf"\b{re.escape(form)}\b", haystack)
                   for form in forms):
                names.append(display)
        if not names:
            continue
        elem["targets"] = names
        bound += 1
    return bound


def _requires_reaction_phase(event, valid_actor_ids, actor_names):
    """True when a contestable act lands on another character and asserts an
    outcome on them -- the case the reaction phase exists to adjudicate.

    The gate used to demand a verb from a small combat whitelist, so only
    violence could earn a reaction: any other contestable outcome asserted on a
    character's body (a grip they might break, an intimate act, a persuasion
    landing) was resolved with no chance for that character to contest it
    physically. Contestability plus a bound target plus a declared effect is
    the real condition; the whitelist and the multi-stage cues now only widen
    it, catching acts that declare no effect of their own."""
    if not isinstance(event, dict):
        return False
    if event.get("type") != "action":
        return False
    if event.get("commitment") != "contestable":
        return False

    targets_actor = False
    for target in event.get("targets") or []:
        if isinstance(target, int) and target in valid_actor_ids:
            targets_actor = True
            break
        text = str(target).strip().casefold()
        if text.isdigit() and int(text) in valid_actor_ids:
            targets_actor = True
            break
        if text in actor_names:
            targets_actor = True
            break

    if not targets_actor:
        return False

    verb = str(event.get("verb") or "").casefold()
    attempt = str(event.get("attempt") or "").casefold()
    stage = str(event.get("stage") or "immediate")

    return bool(
        event.get("intended_effects")
        or event.get("asserted_effects")
        or verb in _REACTIVE_VERBS
        or any(term in attempt for term in _REACTIVE_VERBS)
        or stage in _REACTIVE_STAGES
    )

def _requires_director_resolution(result):
    """Does this declaration need the Director before anyone can answer it.

    It ends the BEAT in `interaction_loop`, so the bar is "nobody can
    sensibly respond until the world says what happened" -- not "this act
    involves another person".

    HAVING A TARGET IS NOT THAT BAR, and treating it as one is what made
    conversation impossible. In a conversation every piece of ordinary body
    language is aimed at whoever you are talking to: a nod, a glance, an ear
    turning. Live, chat 38 t144-t147 -- the player deliberately stayed silent
    for four turns to let two characters talk -- and all four ended after a
    single exchange on acts like "offering a small nod of acknowledgment to
    Tamamo", "shifts gaze fully to the Doctor" and "remains motionless with
    steady gaze on Tamamo". Nobody can contest a nod. Corpus-wide, 1002 of
    1439 character-declared actions were asserted, immediate, and targeted --
    70% of every act a character takes was ending the beat.

    `commitment` is the Director's OWN answer to this question and it
    discriminates cleanly: `contestable` reads "Tightens grip on the caught
    prey's shoulder, wrenching upward", "Closes the 1.5-meter gap in two quick
    steps"; `asserted` reads "nods once slowly". Only 82 of those 1439 are
    contestable. The conflict-verb list stays as a backstop under a
    mislabelled commitment, and covers movement (`leave`/`enter`), which needs
    resolution however confidently it is declared.
    """
    actions = [
        e for e in _dict_list(result.get("sequence"))
        if e.get("type") == "action"
    ]
    for action in actions:
        text = str(action.get("attempt") or "").casefold()
        if action.get("visibility") == "concealed":
            return True
        if action.get("commitment") == "contestable":
            return True
        conflict_terms = (
            "attack", "grab", "restrain", "steal", "break", "force",
            "cast", "shoot", "stab", "strike", "move into", "leave", "enter",
        )
        if any(term in text for term in conflict_terms):
            return True
    return False

def _classify_action_commitment(raw_text):
    """Classify an action as asserted or contestable."""
    text = (raw_text or "").casefold().strip()
    if not text:
        return "contestable"
    if any(cue in text for cue in ATTEMPT_CUES):
        return "contestable"
    return "asserted"

def _normalize_effect(effect):
    """Coerce a string or partial dict into a full effect dict."""
    if isinstance(effect, str):
        return {"target_id": None, "kind": effect, "details": {}}
    if isinstance(effect, dict):
        return effect
    if effect is None:
        return None
    return {"target_id": None, "kind": str(effect), "details": {}}

def _named_cast_subject(text, target_forms):
    """The single cast display name `text` names, or None when it names none
    or more than one (an ambiguous subject is worse than an absent one)."""
    low = str(text or "").casefold()
    if not low.strip():
        return None
    hits = [
        display for display, forms in (target_forms or {}).items()
        if any(re.search(rf"\b{re.escape(form)}\b", low) for form in forms)
    ]
    return hits[0] if len(hits) == 1 else None


def _extract_authority_claims(sequence, raw_input, actor_name=None,
                              target_forms=None):
    """Extract authority claims from the interpreted sequence.

    raw_input is the player's own declaration and serves as the FALLBACK
    text everywhere an element carries no raw_text/attempt of its own --
    both for commitment classification and for the claim's source_text.
    (It used to be accepted and ignored, so an element the model emitted
    without raw_text produced empty-source claims classified against "".)

    actor_name, when given, is the declaring actor (the player). A
    self-directed action effect -- one whose own target_id is empty AND
    whose parent action names no explicit targets -- is about the actor's
    OWN body (a wave, going rigid, a pleading look), so its subject is the
    actor. Without this those claims carried subject_id=None and tripped
    the resolve reconciliation's 'no resolvable subject' note every beat.
    Scoped deliberately narrow: a transitive effect (the action DOES name
    targets, so a null effect target is a dropped reference, not the self)
    and the actor-less `event` branch (a player-authored WORLD assertion
    like "two guards appear") are left for the director to adjudicate --
    resolving them to the player would silently hand the player authorship
    of world facts.

    target_forms (cast display name -> casefolded match forms) closes the
    hole that fallback opened: when the model leaves BOTH targets and
    target_id empty on an act whose text is plainly about another character,
    "no targets" is not evidence of self-direction, and stamping the player
    as subject hands them authorship of that character's body. Naming the
    cast member the text does is strictly better than either wrong answer --
    the resolve seam can then actually check the claim's coverage."""
    fallback_text = str(raw_input or "")
    claims = []
    for i, event in enumerate(sequence or []):
        if event.get("type") == "event":
            # Actor-less environmental assertion ("the lights go out",
            # "a monster enters") -- a player world assertion under the
            # authority contract: it becomes true, so it is minted as an
            # asserted-effect claim the resolve seam's player-claim
            # coverage check can then hold the diff to.
            description = str(event.get("description") or "").strip()
            if not description:
                continue
            claims.append({
                "claim_id": f"claim:{i}:event",
                "scope": "effect",
                "subject_id": str(event.get("subject") or "") or None,
                "predicate": description,
                "value": None,
                "commitment": "asserted",
                "source_text": event.get("raw_text") or description
                or fallback_text,
            })
            continue
        if event.get("type") != "action":
            continue
        commitment = event.get("commitment")
        if commitment is None:
            commitment = _classify_action_commitment(
                event.get("raw_text") or event.get("attempt")
                or fallback_text)
        event["commitment"] = commitment
        # A null effect target is the actor's own body only when the action
        # named no targets at all; if it did, the null is a dropped reference.
        self_subject = actor_name if not (event.get("targets") or []) else None
        if self_subject and target_forms:
            # ...and only when the act is not plainly about someone else.
            named = _named_cast_subject(
                f"{event.get('attempt') or ''} {_element_effect_text(event)}",
                target_forms)
            if named:
                self_subject = named
        if commitment == "asserted":
            for effect_index, effect in enumerate(
                event.get("asserted_effects") or []
            ):
                eff = _normalize_effect(effect)
                if eff is None:
                    continue
                claims.append({
                    "claim_id": f"claim:{i}:effect:{effect_index}",
                    "scope": "effect",
                    "subject_id": eff.get("target_id") or self_subject,
                    "predicate": eff.get("kind", ""),
                    "value": eff.get("details"),
                    "commitment": "asserted",
                    "source_text": event.get("raw_text")
                    or event.get("attempt") or fallback_text,
                })
        else:
            for effect_index, effect in enumerate(
                event.get("intended_effects") or []
            ):
                eff = _normalize_effect(effect)
                if eff is None:
                    continue
                claims.append({
                    "claim_id": f"claim:{i}:intent:{effect_index}",
                    "scope": "intent",
                    "subject_id": eff.get("target_id") or self_subject,
                    "predicate": eff.get("kind", ""),
                    "value": eff.get("details"),
                    "commitment": "contestable",
                    "source_text": event.get("raw_text")
                    or event.get("attempt") or fallback_text,
                })
    return claims

def _agent_json(
    role,
    step_key,
    system,
    payload,
    *,
    temperature=None,
    max_tokens=None,   # the configured ceiling; see complete_validated_json
    sampler=None,
):
    """The STRICT validated-JSON path every state-mutating pipeline stage
    must use for its primary LLM call. complete_validated_json parses
    strictly, runs schemas.validate_llm_output_strict (Pydantic schema +
    semantic checks for step_key), attempts one temperature-0 repair, then
    walks the role's remaining model candidates -- and RAISES if nothing
    validates, so a hopelessly malformed output surfaces as a normal
    rerunnable step error instead of committing junk. The follow-up
    schemas.validate_llm_output calls some stages make on this function's
    return value are warning-only re-normalization of already-validated
    output, NOT the guard -- do not downgrade a stage to jparse or a bare
    chat_complete for output that reaches commit.py.
    """
    return complete_validated_json(
        role=role,
        step_key=step_key,
        system=system,
        payload=payload,
        temperature=temperature,
        max_tokens=max_tokens,
        sampler=sampler,
        repair_attempts=1,
    )

def jparse(text, fallback_key="text", required=False):
    t = re.sub(r"^```[a-zA-Z]*\n?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    try:
        repaired = re.sub(r',\s*([}\]])', r'\1', t)
        return json.loads(repaired)
    except Exception:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        block = m.group(0)
        try:
            return json.loads(block)
        except Exception:
            pass
        try:
            repaired = re.sub(r',\s*([}\]])', r'\1', block)
            return json.loads(repaired)
        except Exception:
            pass
    if required:
        raise RuntimeError(
            f"LLM returned unparseable JSON (first 200 chars): {(text or '')[:200]}")
    return {fallback_key: text}

def _books(ctx, refresh=False):
    if refresh or ctx.get("_books") is None:
        ctx["_books"] = chat_lorebook_ids(ctx.chat.id)
    return ctx["_books"]

def _book_weights(ctx, refresh=False):
    if refresh or ctx.get("_book_weights") is None:
        ctx["_book_weights"] = chat_lorebook_weights(ctx.chat.id)
    return ctx["_book_weights"]

def lore_for(ctx):
    entries = ((ctx.get("mapping_stage") or ctx.get("mapping_quick") or {})
               .get("relevant_lore") or [])
    allowed = ("id", "entry_uid", "book_id", "keys", "content", "category", "locked")
    return [{k: e.get(k) for k in allowed if k in e}
            for e in entries if isinstance(e, dict)]

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

def _room_notes_from_lore(room_id, ctx, scene=None):
    if not room_id:
        return ""
    sc = scene if scene is not None else get_scene(ctx.chat.id, ctx.chat)
    rdata = (sc.get("rooms") or {}).get(room_id)
    if rdata and rdata.get("notes"):
        return rdata["notes"]
    # Coarse scope-by-nesting-depth: for a sealed nested observer, an entry
    # whose keys ALSO name an ancestor-scope room/location carries ambient
    # information they cannot perceive right now -- skip it.
    blocked = _ambient_blocked_slugs(sc, room_id)
    staged = ((ctx.get("mapping_stage") or {}).get("staged_lore") or []) + \
             ((ctx.get("mapping_quick") or {}).get("staged_lore") or [])
    room_norm = room_id.lower().replace("_", " ")
    for entry in staged:
        _k = entry.get("keys")
        keys = (" ".join(map(str, _k)) if isinstance(_k, list) else str(_k or "")).lower()
        content = entry.get("content") or ""
        if (room_norm in keys or room_id.lower() in keys) and content:
            if blocked and _keys_reference_blocked(keys, blocked):
                continue
            return content[:600]
    for entry in lore_for(ctx):
        _k = entry.get("keys")
        keys = (" ".join(map(str, _k)) if isinstance(_k, list) else str(_k or "")).lower()
        content = entry.get("content") or ""
        if (room_norm in keys or room_id.lower() in keys) and content:
            if blocked and _keys_reference_blocked(keys, blocked):
                continue
            return content[:600]
    return ""

# A stage direction written INSIDE a speech element: "*leans in* Sit down."
# Bounded and single-line on purpose: an unpaired asterisk in ordinary prose
# must not swallow the rest of the line looking for its partner.
_STAGE_DIRECTION_RE = re.compile(r"\*([^*\n]{1,400}?)\*")

# Function words carry no evidence that two descriptions name the same act --
# "on her" appears in every second stage direction -- so they are excluded
# before the overlap in _dedupe_promoted_actions is measured.
_OVERLAP_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "so", "as", "if", "then",
    "in", "into", "on", "onto", "at", "to", "toward", "towards", "from",
    "of", "off", "out", "up", "down", "over", "under", "with", "without",
    "against", "across", "through", "between", "around", "back",
    "her", "his", "their", "its", "my", "your", "our", "him", "she", "he",
    "they", "them", "it", "you", "i", "we", "us", "me",
    "is", "are", "was", "were", "be", "been", "being", "one", "that", "this",
    "while", "still", "just", "now", "very", "own", "for", "by",
})


def split_stage_directions(text):
    """Speech text -> (the words actually spoken, the conduct written into it).

    A character model trained on chat roleplay writes conduct inside the line
    it speaks -- "*leans in and sets a hand flat on her shoulder* You will want
    to sit down" -- instead of emitting the {type:'action'} element the
    sequence contract already provides beside it. Nothing forces this; one live
    beat declared a proper action element AND smuggled a second act into the
    speech in the same breath.

    The engine had no opinion about the contents of `text`, so everything in it
    was treated as SOUND. A body movement then went through the whole
    audibility apparatus -- distance, muffling, enclosure, deafness -- and a
    listener who could hear but not see was told about it in so many words:
    `You hear Reya say: "*leans in...*"`. That is a channel violation. Not a
    knowledge one -- the person being touched would feel it -- but the flow is
    wrong, and a wrong flow is an engine failure, never a model's, so the floor
    here is deterministic rather than a request in the prompt.

    Measured before the fix (chat 62, 12 turns): 52% of that chat's speech
    elements carried one, against 0.9% across the rest of the corpus. It grew
    turn over turn because the span was stored in the speaker's own episodic
    memory as words she SAID and read back to her on the next beat, and it was
    also the cause of a second symptom -- the Director, a different model,
    re-rendered the stage direction as prose, which no longer matched the
    declaration, so the verbatim-speech guard dropped the line as invented on
    7 of 12 turns against 7 of 1,715 turns corpus-wide.

    A ONE-WORD span is markdown emphasis, not a stage direction ("what does it
    *feel* like") -- the asterisks come off and the word stays spoken.

    `tone` was considered as the home for the vocal-manner spans (a laugh, a
    drop in register) and rejected. `_inject_dialogue` renders tone only when
    the listener can SEE the speaker, so an audible laugh parked there is lost
    in the dark -- exactly the same class of bug one layer down. Every span
    becomes conduct instead, and perception delivers it by whatever channel the
    act actually engages, which is perception's job and not this function's.
    """
    raw = str(text or "")
    if "*" not in raw:
        return raw, []
    spans = []

    def _take(match):
        body = " ".join(match.group(1).split())
        if not body:
            return ""
        if len(body.split()) == 1:
            # Emphasis on a single spoken word. It stays in the line.
            return body
        spans.append(body)
        return ""

    spoken = _STAGE_DIRECTION_RE.sub(_take, raw)
    # Collapse the whitespace and orphaned punctuation the excision leaves
    # behind, so "*leans in* You will..." does not become " You will...".
    spoken = re.sub(r"\s{2,}", " ", spoken).strip()
    spoken = re.sub(r"^[,;:.\-—\s]+", "", spoken).strip()
    return spoken, spans


def _promoted_stage_action(span, speech_elem):
    """One excised stage direction, as the action element it should have been.

    It inherits the speech element's concealment: a stage direction inside a
    whispered aside was hidden by the words around it, and must not become
    overt conduct just because it moved onto its own channel. `observable` goes
    through the same mental-verb check `norm_sequence` applies to any other
    action, so "*thinks better of it*" resolves to an imperceptible beat rather
    than a visible one.
    """
    observable = "" if _is_mental_action("", span) else span
    return {
        "type": "action",
        "attempt": span,
        "observable": observable,
        "visibility": ("concealed"
                       if speech_elem.get("visibility") == "concealed"
                       else "overt"),
        "conceal_from": list(speech_elem.get("conceal_from") or []),
        "targets": [],
        "commitment": _classify_action_commitment(span),
        "verb": "",
        "stage": "immediate",
        "intended_effects": [],
        "asserted_effects": [],
        "_promoted": True,
    }


def _dedupe_promoted_actions(clean):
    """Drop a promoted action the character ALSO declared properly.

    The live failure mode narrated one act twice in a single paragraph: once
    through a real action element and once through the copy smuggled into the
    speech. The two spellings are almost never identical -- "sets a hand on her
    shoulder" against "sets a hand FLAT on her shoulder" -- so the comparison is
    content-word overlap rather than containment, measured against the SHORTER
    of the two so a long elaboration still matches the short declaration it
    elaborates.

    Deliberately not fuzzier than that. A false match silently drops conduct
    the character declared, which is the failure this whole path exists to
    prevent; a false miss only costs a duplicated beat the narrator can merge.
    """
    def _content(text):
        words = re.sub(r"[^\w\s]", " ", str(text or "")).lower().split()
        return {w for w in words if w not in _OVERLAP_STOPWORDS}

    declared = [_content(e.get("observable") or e.get("attempt"))
                for e in clean
                if e.get("type") == "action" and not e.get("_promoted")]
    declared = [d for d in declared if len(d) >= 3]
    kept = []
    for e in clean:
        if e.get("type") == "action" and e.get("_promoted"):
            mine = _content(e.get("attempt"))
            if len(mine) >= 3 and any(
                    len(mine & d) / min(len(mine), len(d)) >= 0.8
                    for d in declared):
                continue
        kept.append(e)
    return kept


# Words a sentence leans on rather than lands on. An interruption arrives where
# the speaker drew breath, and the breath is taken just before one of these or
# just after a comma -- not at an arbitrary word count.
_BREATH_CONJUNCTIONS = frozenset({
    "and", "but", "or", "so", "because", "which", "that", "if", "when",
    "while", "though", "although", "since", "as", "then", "yet", "before",
    "after", "unless", "until", "whether",
})

# Below this, a line has nothing to cut. "Wait." interrupted is still "Wait."
# -- truncating it produces "Wait.—", which reads as a typo, and fictionally
# there is no room to get inside a one-word line anyway.
_MIN_INTERRUPTIBLE_WORDS = 5


def cut_short_speech(text, ratio=0.6):
    """A spoken line as it lands when somebody cuts in, or None to leave it.

    Returning None rather than a shortened string is the important half: a
    short line, or one the speaker already trailed off, is delivered WHOLE and
    the interrupting beat simply follows it. Forcing a cut on everything is
    what makes an interruption mechanic read as a bug.

    Where the cut falls was chosen by reading the output rather than by
    picking a number. A flat halfway cut lands mid-phrase ("the shipment
    left—"); stopping at a breath point lands where a person actually gets cut
    off ("the shipment left on Tuesday—"). So: keep whole sentences, cut the
    final one near `ratio`, and slide that cut to the nearest comma or
    conjunction within a couple of words.

    The em dash replaces whatever punctuation it lands on, because "to do,—"
    and "hearth.—" are both wrong and the dash is doing that job now.
    """
    body = " ".join(str(text or "").split())
    if not body:
        return None
    # Already trailed off -- the writer has done this themselves.
    if body.endswith(("—", "–", "-", "...", "…")):
        return None
    if len(body.split()) < _MIN_INTERRUPTIBLE_WORDS:
        return None

    sentences = re.split(r"(?<=[.!?])\s+", body)
    head, tail = sentences[:-1], sentences[-1]
    words = tail.split()
    if len(words) < 3 and head:
        kept = words
    else:
        target = max(1, int(len(words) * ratio))
        keep = target
        for index in range(max(1, target - 2), min(len(words), target + 3)):
            if words[index - 1].endswith(","):
                keep = index
                break
            if words[index].lower().strip(",;:") in _BREATH_CONJUNCTIONS:
                keep = index
                break
            if words[index - 1].lower().strip(",;:") in _BREATH_CONJUNCTIONS:
                keep = max(1, index - 1)
                break
        kept = words[:keep]
    joined = " ".join(head + [" ".join(kept)]) if head else " ".join(kept)
    return re.sub(r"[.,;:!?\s—–-]+$", "", joined) + "—"


def norm_sequence(out, warn=None):
    seq = out.get("sequence")
    if not isinstance(seq, list) or not seq:
        seq = []
        if out.get("speech"):
            seq.append({
                "type": "speech",
                "text": out["speech"],
                "volume": normalize_speech_volume(
                    out.get("speech_volume")
                ),
            })
    acts = out.get("actions")
    if not isinstance(acts, list):
        acts = [out["action"]] if out.get("action") else []
    for a in acts:
        if isinstance(a, dict):
            seq.append({"type": "action", **a})
    clean = []
    for e in seq:
        if not isinstance(e, dict):
            continue
        t = e.get("type") or (
            "speech" if (e.get("text") or e.get("speech")) else "action"
        )
        if t == "speech":
            txt = e.get("text") or e.get("speech")
            if txt:
                # Conduct written into the spoken line comes out FIRST and
                # becomes its own action, placed immediately before the speech
                # it was buried in. See split_stage_directions: leaving it in
                # `text` routes a body movement down the acoustic channel.
                txt, _stage_spans = split_stage_directions(str(txt))
                for _span in _stage_spans:
                    clean.append(_promoted_stage_action(_span, e))
                    if warn:
                        warn("moved a stage direction out of spoken text into "
                             "its own action: '%s'" % _span[:80])
            if txt:
                # Carry the speech element's OWN concealment through
                # normalization. Dropping it here (as we used to) meant a
                # line the director explicitly marked visibility:'concealed'
                # was re-emitted as overt, so perception_act's onset delivery
                # -- which reads visibility/conceal_from straight off these
                # normalized speech elements -- leaked the private words to
                # every in-range perceiver, including whoever it was
                # concealed from. See tests/test_speech_concealment.py.
                clean.append({
                    "type": "speech",
                    "text": str(txt),
                    "volume": normalize_speech_volume(e.get("volume")),
                    "tone": e.get("tone", ""),
                    # Who this lands on top of, if the character declared it as
                    # cutting somebody off. Resolved deterministically in the
                    # interaction loop against who has actually spoken this
                    # beat -- a name here is a claim, not an outcome.
                    "interrupts": str(e.get("interrupts") or "").strip(),
                    "visibility": "concealed" if e.get("visibility") == "concealed" else "overt",
                    "conceal_from": e.get("conceal_from") or [],
                    # raw (pre-normalization) signals, consumed by the
                    # concealment backstop below and stripped before return.
                    "_raw_vis": e.get("visibility"),
                    "_raw_vol": e.get("volume"),
                })
        elif t == "ponder":
            # Private cognitive action. It never enters the public sequence,
            # Director resolution, perception, or narration. Commit stores one
            # bounded query for the next character turn.
            query = " ".join(str(e.get("query") or "").split())[:240]
            why = " ".join(str(e.get("why") or "").split())[:240]
            if query and why:
                out["ponder"] = {
                    "type": "ponder", "query": query, "why": why}
        elif t in ("event", "environment", "environmental", "world"):
            # Actor-less environmental event ("the lights go out", "a
            # monster enters") declared by the player. These used to be
            # silently DROPPED here (only speech/action survived), so a
            # player world assertion never reached the resolve at all.
            # First-class representation, canonical type "event".
            description = (e.get("description") or e.get("text")
                           or e.get("attempt"))
            if description:
                raw_asserted = e.get("asserted_effects") or []
                asserted_effects = [
                    _normalize_effect(eff)
                    for eff in raw_asserted
                    if _normalize_effect(eff) is not None
                ]
                clean.append({
                    "type": "event",
                    "description": str(description),
                    "subject": str(e.get("subject") or ""),
                    "raw_text": e.get("raw_text") or "",
                    "visibility": "concealed"
                    if e.get("visibility") == "concealed" else "overt",
                    "conceal_from": e.get("conceal_from") or [],
                    "commitment": e.get("commitment") or "asserted",
                    "asserted_effects": asserted_effects,
                })
        else:
            att = e.get("attempt")
            if att:
                tg = e.get("targets") or e.get("target") or []
                if not isinstance(tg, list):
                    tg = [tg]
                commitment = e.get("commitment")
                if commitment is None:
                    commitment = _classify_action_commitment(
                        e.get("raw_text") or att
                    )
                raw_intended = e.get("intended_effects") or []
                raw_asserted = e.get("asserted_effects") or []
                intended_effects = [
                    _normalize_effect(eff)
                    for eff in raw_intended
                    if _normalize_effect(eff) is not None
                ]
                asserted_effects = [
                    _normalize_effect(eff)
                    for eff in raw_asserted
                    if _normalize_effect(eff) is not None
                ]
                # The intent-free OUTWARD surface handed to other perceivers
                # (see observable_action_text). `attempt` is the actor's own
                # framing and routinely embeds purpose/magic-intent ("scratch
                # runes of slow and soften", "channel divine heritage") or
                # pure cognition ("remember the rune crafting") -- copying it
                # into an observer's view leaks meaning the perception filter
                # exists to strip. Prefer the director-authored `observable`;
                # default a mental act to "" (imperceptible -> skipped) and a
                # physical act with no authored surface to `attempt` (no
                # delivery regression for un-migrated / plain physical acts).
                observable = e.get("observable")
                if observable is None:
                    observable = "" if _is_mental_action(
                        e.get("verb"), att) else att
                clean.append({
                    "type": "action",
                    "attempt": att,
                    "observable": str(observable),
                    # A blow, a hand over a mouth, a grab -- conduct cuts a line
                    # off exactly as a louder voice does.
                    "interrupts": str(e.get("interrupts") or "").strip(),
                    "visibility": e.get("visibility", "overt"),
                    "conceal_from": e.get("conceal_from") or [],
                    "targets": tg,
                    "commitment": commitment,
                    "verb": e.get("verb", ""),
                    "stage": e.get("stage", "immediate"),
                    "intended_effects": intended_effects,
                    "asserted_effects": asserted_effects,
                })
    # A promoted stage direction the character also declared as a real action
    # is the same act twice, and the narrator rendered both.
    clean = _dedupe_promoted_actions(clean)
    # Deterministic concealment backstop (leak-safe). A hushed or unmarked
    # line co-declared with a concealed action is almost always the private
    # communication itself; weak models routinely mark the ACTION concealed
    # (e.g. "open a private channel", "whisper an aside") but leave the SPEECH
    # overt, which would leak the words to everyone in range. So: for every
    # speech element that is not EXPLICITLY public, propagate the union of all
    # concealed actions' conceal_from onto it. "Explicitly public" = the model
    # set an explicit overt visibility, or an explicit loud/shout volume. We
    # never override a speech the model already marked concealed, and we
    # subtract the concealing actions' own targets so the intended addressee
    # is never made deaf. Over-concealment only costs marginal eavesdroppers
    # (the addressee still hears); a leak is irreversible.
    concealed_from_union, conceal_targets = [], []
    for e in clean:
        if e["type"] == "action" and e.get("visibility") == "concealed":
            for cf in e.get("conceal_from") or []:
                if cf not in concealed_from_union:
                    concealed_from_union.append(cf)
            for tg in e.get("targets") or []:
                if tg not in conceal_targets:
                    conceal_targets.append(tg)
    propagate = [cf for cf in concealed_from_union if cf not in conceal_targets]
    if propagate:
        for e in clean:
            if e["type"] != "speech" or e.get("visibility") == "concealed":
                continue
            explicitly_public = (e.get("_raw_vis") == "overt") or (e.get("_raw_vol") in ("loud", "shout"))
            if explicitly_public:
                continue
            e["visibility"] = "concealed"
            e["conceal_from"] = list(propagate)
    for e in clean:
        e.pop("_raw_vis", None)
        e.pop("_raw_vol", None)
        e.pop("_promoted", None)

    out["sequence"] = clean
    return _sync_sequence_mirrors(out)

def _sync_sequence_mirrors(out):
    """Recompute the legacy scalar mirrors (speech/speech_volume/action/
    actions) from out['sequence']. Factored out of norm_sequence so the
    interpret-reconciliation seam can re-sync after additively appending
    repaired elements WITHOUT re-running norm_sequence on the whole output
    (which would re-append out['actions'] and duplicate every action)."""
    clean = out.get("sequence") or []
    sp = [e for e in clean if e.get("type") == "speech"]
    ac = [e for e in clean if e.get("type") == "action"]
    out["speech"] = sp[0]["text"] if sp else None
    out["speech_volume"] = (
        sp[0]["volume"] if sp else out.get("speech_volume", "normal")
    )
    out["action"] = (
        {
            "attempt": ac[0]["attempt"],
            "visibility": ac[0]["visibility"],
            "conceal_from": ac[0]["conceal_from"],
            "targets": ac[0]["targets"],
            "commitment": ac[0].get("commitment", "contestable"),
        }
        if ac
        else None
    )
    out["actions"] = ac
    return out

def assign_event_ids(sequence, prefix):
    result = []
    for index, raw in enumerate(sequence or []):
        event = dict(raw)
        event.setdefault("event_id", f"{prefix}:{index}:{event.get('type', 'event')}")
        result.append(event)
    return result

def _stable_event_key(*parts):
    raw = "\x1f".join(str(part or "") for part in parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]
    return f"event:{digest}"

def _lore_fingerprint(entry):
    keys = re.sub(r"\s+", " ", str(entry.get("keys") or "").strip().casefold())
    content = re.sub(r"\s+", " ", str(entry.get("content") or "").strip().casefold())
    digest = hashlib.sha256(f"{keys}\x1f{content}".encode("utf-8")).hexdigest()
    return f"content:{digest}"

def _append_once(view, text, marker=None):
    text = str(text or "").strip()
    if not text:
        return view
    view = str(view or "").strip()
    marker = str(marker or text).strip()
    if marker and marker.casefold() in view.casefold():
        return view
    return f"{view} {text}".strip()

# Rank/title/honorific tokens dropped before comparing names, plus single-letter
# middle initials. So "Commander Riker" and "Cmdr. Riker" reduce to {riker}.
_NAME_TITLE_TOKENS = {
    "commander", "cmdr", "captain", "capt", "lieutenant", "lt", "ensign",
    "doctor", "dr", "mr", "mrs", "ms", "miss", "lord", "lady", "sir", "chief",
    "admiral", "general", "sergeant", "sgt", "colonel", "col", "major",
    "professor", "prof", "the", "a", "an",
}


def _significant_name_tokens(name):
    """Lower-cased identifying tokens of a name -- titles, ranks and single
    initials removed. 'Commander Riker' -> {'riker'}."""
    out = set()
    for tok in re.findall(r"[A-Za-z']+", str(name or "")):
        low = tok.strip(".'").casefold()
        if len(low) < 3 or low in _NAME_TITLE_TOKENS:
            continue
        out.add(low)
    return out


def _recognizes(name, recognized):
    """Whether an observer who recognizes the `recognized` name forms also
    recognizes `name`, allowing a rank/title VARIANT of a known person
    (P7 / v3 V3: a background presence voiced as 'Commander Riker' was
    anonymized to 'the unfamiliar person' though the observer knew 'William T.
    Riker').

    Deliberately tight to protect the information barrier: a variant is
    recognized ONLY if every one of its significant tokens is contained in a
    single known name. That admits 'Commander Riker' against 'William T. Riker'
    but still anonymizes 'Commander Sato' (no shared token) AND 'Thomas Riker'
    (shares a surname but 'Thomas' is not known) -- a same-surname stranger
    stays a stranger.

    Lives here (not in agents/perception.py) so the narrator payload builders
    resolve speaker displays with the SAME recognition rule perception used to
    build the view -- role modules never import each other."""
    if name in recognized:
        return True
    tokens = _significant_name_tokens(name)
    if not tokens:
        return False
    for known_name in recognized:
        known_tokens = _significant_name_tokens(known_name)
        if known_tokens and tokens <= known_tokens:
            return True
    return False


def _identity_token_set(actor_name, aliases=None):
    """Casefolded word tokens of an actor's name and aliases -- the tokens
    that must never surface to an observer who does not recognize them."""
    tokens = set()
    for form in [actor_name] + list(aliases or []):
        for tok in re.split(r"[^\w]+", str(form or "")):
            if tok:
                tokens.add(tok.casefold())
    return tokens

def observer_label_fn(chat, observer_name, cast):
    """`name -> what THIS observer may call them`, for any payload that names
    a body outside perception's own scrubbing.

    Perception decides identity per observer and renders prose accordingly.
    Everything else that hands a character a NAME has to make the same
    decision, and until now nothing did -- so a structured field could hand
    over an identity the prose beside it was carefully withholding. Observed
    live: `perception.spatial_frame.ahead_entity` came from `scene.positions`,
    which is keyed by canonical name, and told a character who she was looking
    at. She had asked twice, in dialogue, and been refused both times; six
    beats later she used the surname aloud.

    Same rule as `agents/perception.py`'s own gate, from the same `known` map
    and through the same `_unknown_actor_label`, so this is one identity floor
    rather than a second one that can drift from it.
    """
    known = set((wget(chat["id"], "known", {}) or {}).get(observer_name) or [])
    sheets = {}
    for row in (cast or []):
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        name = character_name(sheet)
        if name:
            sheets[name] = sheet
    persona = persona_of(chat)
    p_name = persona_name(persona)
    if p_name:
        sheets.setdefault(p_name, persona)

    def label(name):
        text = str(name or "").strip()
        if not text or text == observer_name or text in known:
            return text
        sheet = sheets.get(text)
        if sheet is None:
            # Not a body this function knows about -- an entity id, a prop, a
            # room. Nothing to gate, and inventing a description for a lamp
            # would be worse than leaving it.
            return text
        return _unknown_actor_label(
            text, character_appearance(sheet), character_scene_keys(sheet)[1:])

    return label


def observer_name_scrub(chat, observer_name, cast):
    """`text -> the same text with unrecognized bodies renamed`, for a payload
    that hands a character PROSE somebody else wrote.

    `observer_label_fn` above gates a field that holds ONE name. This gates a
    field that holds a paragraph, and it exists because `world_knowledge` did
    not have either: lore entries are objective world record, they are written
    during play by the mapping stage, and that stage writes canonical names
    into their prose. Any character whose lore filter admitted the entry then
    read the name, met or not.

    Observed live (chat 38, t140): Tamamo had met the Doctor for the first
    time one beat earlier. Her `known` ledger was empty, her view called him
    "the lean energetic man", `ahead_entity` called him "the lean energetic
    man", her memories and her micro-perception all agreed -- and a lore entry
    in her payload opened "As The Doctor and Hinami walk deeper into the Deck
    14 corridor". She addressed him as "Doctor" in the same beat, and wrote
    "the lean energetic man now identified as Doctor" into her own concerns.
    Across the stored corpus, 65 lore entries in 22 chats name a cast member;
    16 of those were written during play.

    Whole-word only, and aliases too, because the entry that leaked used the
    plain registered name and a substring rule would maul any word containing
    it. Quoted spans are NOT exempt the way perception exempts them: a lore
    entry is not a transcript, and prose that quotes somebody naming a person
    is still telling the reader who they are.
    """
    label = observer_label_fn(chat, observer_name, cast)
    known = set((wget(chat["id"], "known", {}) or {}).get(observer_name) or [])
    sheets = []
    for row in (cast or []):
        try:
            sheets.append(json.loads(row["sheet"]))
        except Exception:
            continue
    # The player is a body in the room like any other, and lore written during
    # play names them more often than it names anyone else. Same source as
    # observer_label_fn's, so the two cannot disagree about who is gated.
    persona = persona_of(chat)
    if isinstance(persona, dict):
        sheets.append(persona)
    subjects = []
    for sheet in sheets:
        name = character_name(sheet)
        if not name or name == observer_name or name in known:
            continue
        forms = {name} | {
            str(alias) for alias in (character_scene_keys(sheet)[1:] or [])
            if str(alias or "").strip()
        }
        replacement = label(name)
        if replacement == name:
            continue
        for form in forms:
            subjects.append((form, replacement))
    # Longest first: "The Doctor" must win over a bare "Doctor" alias, or the
    # longer form is left half-rewritten.
    subjects.sort(key=lambda pair: -len(pair[0]))

    def scrub(text):
        if not isinstance(text, str) or not text or not subjects:
            return text
        for form, replacement in subjects:
            text = re.sub(rf"\b{re.escape(form)}\b", replacement, text)
        return text

    return scrub


def scrub_names_deep(value, scrub):
    """Apply a text scrub to every string in a nested payload value.

    Lore arrives as a list of dicts whose `content`, `title` and `keys` are all
    prose a mind will read; walking the structure keeps the caller from having
    to know which of them the current schema happens to use.
    """
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, list):
        return [scrub_names_deep(item, scrub) for item in value]
    if isinstance(value, tuple):
        return tuple(scrub_names_deep(item, scrub) for item in value)
    if isinstance(value, dict):
        return {key: scrub_names_deep(item, scrub) for key, item in value.items()}
    return value


def _unknown_actor_label(actor_name, appearance_text=None, aliases=None):
    # Every unrecognized actor used to render as the exact same generic
    # "the unfamiliar person" -- two strangers in one scene (or the same
    # stranger across a perceiver's dialogue and action lines) were
    # indistinguishable in both prose and any memory recorded from it.
    # Derive a short, stable descriptor from the actor's own appearance
    # summary instead. This is deliberately a short label for repeat/
    # inline reference, not a substitute for the full appearance
    # description a caller surfaces separately on first mention.
    #
    # The label is what a NON-recognizing observer refers to the actor by,
    # and appearance summaries routinely LEAD with the canonical name
    # ("Hinami, a fox-eared young woman..."), so the actor's own name/alias
    # tokens are dropped before the descriptor is built -- otherwise the
    # label itself was a deterministic identity leak walking straight past
    # the knows_identity gate it exists to serve.
    if appearance_text:
        name_tokens = _identity_token_set(actor_name, aliases)
        cleaned = re.sub(
            r"^(a|an|the)\s+", "", appearance_text.strip(), flags=re.I,
        ).replace(",", "")
        words = [w for w in cleaned.split()
                 if re.sub(r"[^\w]", "", w).casefold() not in name_tokens]
        # Dropping a leading name can expose the article that followed it
        # ("Hinami, a fox-eared..." -> "a fox-eared..."); re-strip it.
        while words and words[0].lower() in ("a", "an", "the"):
            words = words[1:]
        # A LINKING PARTICIPLE introduces a phrase, and the 5-word cap cuts
        # that phrase off part-way: appearance summaries overwhelmingly read
        # "<body> appearing in her early twenties" or "<body> wearing a
        # patched flight jacket", which cap to "...woman appearing" and
        # "...smuggler wearing a patched" -- both promising a clause neither
        # delivers. Truncating AT the participle rather than trimming it off
        # the end is what fixes the second case, where the participle is not
        # the last word. Only verbs that introduce a following phrase are
        # listed; a bare -ing rule would eat real nouns ("the figure in
        # mourning"). Applied before the cap so the kept words are the
        # distinguishing head of the description rather than its filler.
        _LINKING_PARTICIPLES = {
            "appearing", "wearing", "dressed", "clad", "wrapped", "standing",
            "sitting", "holding", "carrying", "looking", "seeming", "aged",
        }
        for _i, _w in enumerate(words):
            if _i and re.sub(r"[^\w]", "", _w).casefold() in _LINKING_PARTICIPLES:
                words = words[:_i]
                break
        words = words[:5]
        # The cap can still slice mid-phrase and leave a dangling function
        # word ("...five-foot-seven-inches with a"), which reads as broken
        # prose when this label is injected inline. Trim any trailing
        # article/preposition/conjunction/possessive so the label ends on a
        # content word.
        _DANGLING = {"a", "an", "the", "with", "of", "and", "or", "in", "on",
                     "at", "to", "for", "from", "by", "her", "his", "their",
                     "its", "as"}
        while words and words[-1].lower() in _DANGLING:
            words = words[:-1]
        if words:
            return "the " + " ".join(words).rstrip(".;:").lower()
    return "the unfamiliar person"

def _delivery_ok(relation, scene, observer_name, source_name, channel,
                 volume="normal", proximity=None, behind_sources=None,
                 awareness=None):
    """Can this observer receive this source through this channel?

    Cross-seam pattern 3: the deterministic delivery paths each grew their own
    partial gate, so every one of them skipped a rule the perception model path
    honours -- the micro-loop skipped containment and graded sight, the outcome
    action backstop skipped the rear arc, the background channel skipped
    station. This is the one predicate all of them call, so a rule added here
    reaches every deterministic delivery site at once.

    `relation` is the caller's own `spatial_rel` result (built from ROOM ids,
    which only the caller can resolve uid/alias-tolerantly). Everything else is
    derived here:

    - **awareness** -- a non-awake mind receives nothing.
    - **containment** -- a sealed enclosure blocks sight AND sound, in both
      directions (`containment_conceals` is symmetric).
    - **hearing** -- `hear_level` including the `proximity` downgrade, so a
      muttered aside does not carry to an arbitrarily large room.
    - **sight/action** -- `has_visual` plus the rear-arc blind spot. An action
      is visible or it is nothing.
    """
    if awareness is not None and awareness in NON_AWAKE_GATED:
        return False
    if observer_name == source_name:
        return True
    if containment_conceals(scene, observer_name, source_name):
        return False

    if channel == "hearing":
        return hear_level(relation, volume, proximity=proximity) != "none"

    if behind_sources and source_name in behind_sources:
        return False
    if entity_arc(scene, observer_name, source_name) == "rear":
        return False
    return bool(has_visual(relation))

def _strip_identity_tokens(text, forms):
    """Remove an actor's name/alias forms from engine-supplied prose (an
    appearance summary, an overlay) before it is surfaced to an observer
    who does not recognize that actor. appearance_of()/persona summaries
    routinely lead with the canonical name, so pasting them verbatim into
    a stranger's view via _inject_visible_actor leaked identity entirely
    deterministically, independent of anything the model wrote."""
    out = str(text or "")
    for form in forms or []:
        form = str(form or "").strip()
        if not form:
            continue
        out = re.sub(
            r"(?<!\w)" + re.escape(form) + r"(?:['’]s)?(?!\w)",
            "", out, flags=re.I,
        )
    out = re.sub(r"\s{2,}", " ", out)
    out = re.sub(r"\s+([,;.!?])", r"\1", out)
    out = re.sub(r"([,;])(\s*[,;])+", r"\1", out)
    return out.strip().lstrip(",;: ").strip()

# Single-token names that are also everyday English words ("Rose walks in"
# vs "the rose garden"). For these, only the exact capitalized form is
# scrubbed, so ordinary lowercase prose is never mangled.
_COMMON_WORD_NAMES = frozenset({
    "amber", "angel", "art", "ash", "autumn", "bear", "bill", "blue",
    # `data` is here on the engine's own evidence, not on principle: chat 22
    # carries a character named Data, and every line about sensor data is a
    # line that would otherwise introduce him.
    "brook", "buck", "chase", "clay", "colt", "daisy", "data", "dawn", "dean",
    "drew", "duke", "earl", "faith", "fern", "fox", "ginger", "glen",
    "grace", "hazel", "heath", "holly", "hope", "hunter", "iris", "ivy",
    "jack", "jade", "jasmine", "joy", "june", "king", "lane", "lily",
    "major", "mark", "may", "melody", "misty", "olive", "pearl", "rain",
    "raven", "red", "reed", "robin", "rose", "ruby", "rusty", "sandy",
    "sky", "star", "storm", "summer", "sunny", "violet", "will", "wolf",
    "wren",
})

# Mirrors _protected_view_quotes' quoted-span shape: a name inside a quote
# is sensory signal the observer legitimately heard (an introduction, a
# name called aloud) and must survive the identity scrub verbatim.
#
# Single-quoted dialogue must be protected too -- the perception model
# routinely renders speech as '...' rather than "...", and the double-quote-
# only form let a name spoken aloud this beat (a self-introduction like
# 'I-I'm Hinami') get scrubbed straight out of what the hearer legitimately
# heard. The single-quote alternative is apostrophe-aware: the opening quote
# must not follow a word char or another quote (so contraction/possessive
# apostrophes -- She's, Hinami's -- never open a span), and an internal '
# counts as content only when a word char follows it (I'm, don't), so the
# span still closes at the real terminating quote.
_QUOTED_SPAN_RE = re.compile(
    r'(["“][^"“”]+["”]'
    r"|(?<![\w'’])'(?:[^']|'(?=\w))*?'(?![\w])"
    r")"
)

def _scrub_unknown_identities(view, *, allowed_forms, unknown_sources):
    """Deterministic identity floor for perception view prose.

    The knows_identity/_unknown_actor_label gate used to be enforced only
    inside the deterministic injection helpers -- the perception LLM's own
    free-text prose was never checked, so a model that wrote a stranger's
    canonical name into a view walked straight past the gate (and no
    prompt paragraph even defined knows_identity, so this was not limited
    to weak models). This pass runs LAST on every view: each unknown
    source's name/alias forms are replaced, outside quoted spans only,
    with that source's unknown-actor descriptor.

    unknown_sources: [{name, appearance, aliases}] the observer does NOT
    recognize. allowed_forms: names the observer legitimately commands
    (their own name/aliases plus their recognized set) -- any colliding
    form is skipped rather than scrubbed.

    Returns (scrubbed_view, leaked_names) so callers can surface a
    warning; a silent leak was exactly how the original bug hid.
    """
    text = str(view or "")
    if not text or not unknown_sources:
        return view, []
    allowed = {str(f or "").strip().casefold()
               for f in (allowed_forms or []) if str(f or "").strip()}
    segments = _QUOTED_SPAN_RE.split(text)
    leaked = []
    for src in unknown_sources:
        name = str(src.get("name") or "").strip()
        if not name or name.casefold() in allowed:
            continue
        label = _unknown_actor_label(
            name, src.get("appearance"), aliases=src.get("aliases"))
        fired = False
        for form in [name] + [str(a or "").strip()
                              for a in (src.get("aliases") or [])]:
            if not form or form.casefold() in allowed:
                continue
            if len(form) < 3 and len(form.split()) == 1:
                continue  # too short to match without false positives
            if len(form.split()) == 1 and form.casefold() in _COMMON_WORD_NAMES:
                # common-word guard: exact capitalized form only
                pat = re.compile(
                    r"(?<!\w)" + re.escape(form[:1].upper() + form[1:])
                    + r"(?!\w)")
            else:
                pat = re.compile(
                    r"(?<!\w)" + re.escape(form) + r"(?!\w)", re.IGNORECASE)
            for i in range(0, len(segments), 2):  # even = outside quotes
                if segments[i] and pat.search(segments[i]):
                    segments[i] = pat.sub(label, segments[i])
                    fired = True
        if fired:
            leaked.append(name)
    if not leaked:
        return view, []
    return "".join(segments), leaked

def _contains_quote(view, quote):
    body = _quote_body(quote)
    normalized_view = re.sub(r"\s+", " ", str(view or "").casefold())
    normalized_body = re.sub(r"\s+", " ", body.casefold()).rstrip(".,!?…;:")
    if not normalized_body:
        return False
    # A dialogue tag changes terminal punctuation mechanically: the logged
    # line ``Lie back.`` becomes ``"Lie back," she says``.  That is the same
    # delivered quote, and treating it as absent appends a duplicate exact-line
    # injection.  Internal punctuation remains significant; only the terminal
    # mark is ignored, with a word boundary so ``back`` cannot match
    # ``backwards``.
    return re.search(
        r"(?<!\w)%s(?=$|[^\w])" % re.escape(normalized_body),
        normalized_view,
    ) is not None

def normalize_character_refs(values, cast):
    valid_ids = {int(row["id"]) for row in cast}
    names = {}
    for row in cast:
        try:
            sheet = json.loads(row["sheet"])
            name = character_name(sheet)
        except Exception:
            name = ""
        if name:
            names[name.casefold()] = int(row["id"])
    result = []
    for value in values or []:
        resolved = None
        if isinstance(value, int) and value in valid_ids:
            resolved = value
        elif isinstance(value, str):
            text = value.strip()
            if text.isdigit() and int(text) in valid_ids:
                resolved = int(text)
            else:
                resolved = names.get(text.casefold())
        if resolved is not None and resolved not in result:
            result.append(resolved)
    return result

def character_scene_keys(sheet):
    """Every key a scene might legitimately use to store this character's
    entity/position. The intended convention keys positions by the display
    NAME, but the director sometimes keys by identity.uid (or an alias) -- so
    readers must try all of them. Name first (the intended key), then uid,
    then aliases; de-duplicated case-insensitively, display form preserved."""
    ident = normalize_character_data(sheet).get("identity", {})
    candidates = [ident.get("name"), ident.get("uid")]
    candidates.extend(ident.get("aliases") or [])
    seen, keys = set(), []
    for cand in candidates:
        text = str(cand or "").strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            keys.append(text)
    return keys

def character_room(sc, sheet):
    """Resolve a cast character's room from the scene, tolerating scenes that
    key the entity by identity.uid or an alias rather than the display name.
    Perception was previously blind to a character whose position was stored
    under its uid (e.g. `tenth_doctor` for "The Doctor"), placing them in "an
    unspecified area" and leaking a false empty view."""
    for key in character_scene_keys(sheet):
        room = room_of(sc, key)
        if room:
            return room
    return None

def cast_room(sc, name, cast):
    """Room of a named speaker/actor, mapping the bare name through the cast so
    a character stored under its uid/alias still resolves (the name-string
    counterpart to character_room)."""
    room = room_of(sc, name)
    if room:
        return room
    target = str(name or "").strip().lower()
    if not target:
        return None
    for row in cast or []:
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        if target in {key.lower() for key in character_scene_keys(sheet)}:
            return character_room(sc, sheet)
    return entity_room_by_name(sc, target)


def entity_room_by_name(sc, name):
    """Room of an UNREGISTERED scene presence, resolved from its NAME.

    `canonicalize_positions` rewrites only keys that identify a cast character
    or the player, and says so: "unregistered background presences are left
    untouched". Correct -- they are not cast -- but nothing mapped the name
    back the other way, so a presence placed under its entity uid was
    unreachable by name from the moment it was placed. Every reader that asks
    where a background speaker is got None, and `spatial_rel(None, room)`
    answers "remote, no known spatial channel".

    Measured live (chat 58, t23): a Dalek standing in the player's own alley
    with its gun-stick trained on her chest sat in `positions` under
    `40af0ac4bf2644a1`. `cast_room(sc, "A Dalek", cast)` returned None, so
    perception's hearing gate classified it as remote and dropped its line for
    every observer, and the view rendered it as "something" and "the source"
    rather than the machine she had just thrown a rock at. Corpus-wide, 47 of
    78 background lines never reached a single view.

    Name before aliases, so an alias can never outrank a real name. A name
    matching more than one entity resolves to NOBODY: two Daleks in a room are
    exactly the case this must not guess between, and a wrong room is worse
    than the None every one of them used to get.
    """
    target = str(name or "").strip().lower()
    entities = (sc or {}).get("entities")
    if not target or not isinstance(entities, dict):
        return None
    positions = (sc or {}).get("positions")
    positions = positions if isinstance(positions, dict) else {}
    pos_ci = {str(k).strip().lower(): v for k, v in positions.items()}

    def _match(by_alias):
        hits = []
        for eid, ent in entities.items():
            if not isinstance(ent, dict):
                continue
            if by_alias:
                forms = {str(a).strip().lower() for a in (ent.get("aliases") or [])}
            else:
                forms = {str(ent.get("name") or "").strip().lower()}
            if target in forms - {""}:
                hits.append(eid)
        return hits[0] if len(hits) == 1 else None

    eid = _match(False) or _match(True)
    if not eid:
        return None
    # The uid is the position key in practice; an entity may also carry its own
    # `room`, which is authoritative only when no position exists for it.
    room = pos_ci.get(str(eid).strip().lower())
    if room is None:
        room = pos_ci.get(target)
    if room is None:
        ent = entities.get(eid) or {}
        room = ent.get("room")
    return room or None

def canonicalize_positions(positions, cast, player_name=None):
    """Rewrite any positions key that identifies a registered cast character
    (or the player) to that person's display name -- the positions-key
    convention every reader (perception, commit, spatial) expects. Recognized
    key forms per person: identity.uid, display name (exact or alphanumeric-
    normalized), AND the director's `character:<id>` scheme (from the cast
    payload's integer ids). Non-person keys (objects, unregistered background
    presences) are left untouched. Deliberately does NOT match on aliases.

    Recognizing `character:<id>` and the player is load-bearing: the director
    model keys the SAME person by different schemes across a turn (Data as
    `character:29` here, `Lt. Commander Data` there), and without collapsing
    them to one canonical key the person acquired TWO position entries in
    conflicting rooms -- observed live, Data was simultaneously on the bridge
    (`character:29`) and in a corridor (`Lt. Commander Data`), so name-lookup
    resolved him to the corridor and perception rendered his bridge station as
    empty. Collapsing to a single key makes a later move update the one entry."""
    if not isinstance(positions, dict):
        return {}
    if not cast and not player_name:
        return positions
    keymap = {}

    def _register(forms, canon):
        for key in forms:
            text = str(key or "").strip()
            if not text:
                continue
            keymap.setdefault(text.lower(), canon)
            norm = re.sub(r"[^a-z0-9]", "", text.lower())
            if norm:
                keymap.setdefault(norm, canon)

    for row in (cast or []):
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        ident = normalize_character_data(sheet).get("identity", {})
        name = ident.get("name") or character_name(sheet)
        forms = [ident.get("uid"), name]
        try:
            rid = row["id"]
        except Exception:
            rid = None
        if rid is not None:
            forms.append(f"character:{rid}")
        _register(forms, name)
    if player_name:
        _register([player_name, "character:player"], player_name)

    result = {}
    for key, room in positions.items():
        text = str(key or "").strip()
        canon = keymap.get(text.lower()) \
            or keymap.get(re.sub(r"[^a-z0-9]", "", text.lower()))
        result[canon or key] = room
    return result

def _append_micro_view(base_view, additions):
    parts = [str(base_view or "").strip()]
    parts.extend(str(item).strip() for item in additions if str(item or "").strip())
    return "\n\n".join(part for part in parts if part)

def _normalize_character_output(out):
    if not out.get("mind_model_updates") and out.get("inference_updates"):
        converted = []
        for update in out["inference_updates"]:
            converted.append({
                "about_entity": str(update.get("about") or "unknown"),
                "kind": "goal",
                "claim": str(update.get("conclusion") or ""),
                "confidence": float(update.get("confidence", 0.5)),
                "evidence": [{"event_id": "", "fact": str(update.get("basis") or "")}],
                "alternatives": [],
            })
        out["mind_model_updates"] = converted
    return out

# Narration ABOUT an utterance, as opposed to the utterance. A player writes
# their own beat in second person ("you gently take her by the wrist"), so a speech
# text carrying `you`/`your` outside its quotes is prose the interpreter lifted
# whole rather than the line the player spoke. Attribution verbs are kept
# deliberately narrow -- `say`/`said` and friends, never `tell`/`told` -- so an
# ordinary spoken line that happens to quote someone ('He told me "get out" and
# I left.') is not mistaken for narration and gutted.
_SPEECH_NARRATION_RE = re.compile(
    r"(?<![\w'])(?:you|your|yours"
    r"|says?|said|saying|replie[sd]|reply|answers?|answered"
    r"|mutters?|muttered|whispers?|whispered|murmurs?|murmured"
    r"|adds?|added|calls?|called|shouts?|shouted)(?![\w'])",
    re.I,
)


def repair_narrated_speech(text):
    """Reduce a speech text that swallowed its own narration to the words said.

    Observed live: `director_interpret` returned the player's ENTIRE raw input
    as a single speech element, stage directions included --

        '"Wait" You say it flatly, without turning around. "I am not going."'

    -- and perception injected it faithfully as dialogue. Two failures follow
    at once: the narration is delivered as spoken words, and because the lifted
    prose is in second person, the "You" now points at the LISTENER, who is
    told they said it.

    Fires only when the text holds at least one quoted span AND the residue
    outside those spans reads as narration (>=2 words, carrying a second-person
    pronoun or a speech-attribution verb). A wholly unquoted line -- the normal
    shape -- is returned untouched, as is a line that is nothing but its quote.
    Returns the input unchanged when it declines to act, so callers may assign
    the result unconditionally.
    """
    raw = str(text or "")
    if not raw.strip():
        return text
    segments = _QUOTED_SPAN_RE.split(raw)
    # split() alternates residue/span/residue...; odd indices are the spans.
    spans = [s for i, s in enumerate(segments) if i % 2 == 1]
    if not spans:
        return text
    residue = " ".join(s for i, s in enumerate(segments) if i % 2 == 0)
    if len(residue.split()) < 2 or not _SPEECH_NARRATION_RE.search(residue):
        return text
    bodies = [b for b in (_quote_body(s) for s in spans) if b]
    if not bodies:
        return text
    spoken = ""
    for body in bodies:
        if spoken and spoken[-1] not in ".!?,;:-—":
            spoken += "."
        spoken = f"{spoken} {body}" if spoken else body
    return spoken


def repair_narrated_speech_elements(out):
    """Apply `repair_narrated_speech` to one interpret result in place.

    Covers both representations -- the `sequence` speech elements and the flat
    `speech` mirror -- because downstream stages read whichever is present.
    Returns the list of (before, after) pairs it changed, for warning.
    """
    changed = []
    if not isinstance(out, dict):
        return changed
    for element in (out.get("sequence") or []):
        if not isinstance(element, dict) or element.get("type") != "speech":
            continue
        before = element.get("text")
        after = repair_narrated_speech(before)
        if after != before:
            element["text"] = after
            changed.append((before, after))
    before = out.get("speech")
    if before:
        after = repair_narrated_speech(before)
        if after != before:
            out["speech"] = after
            if not any(b == before for b, _ in changed):
                changed.append((before, after))
    return changed


def player_speech_lines(interp):
    lines = [e.get("text") for e in (interp.get("sequence") or [])
             if e.get("type") == "speech" and e.get("text")]
    if not lines and interp.get("speech"):
        lines = [interp["speech"]]
    return lines


# Physical verbs a resolved_event uses when it gives someone an ACT. Kept to
# unambiguous bodily/manipulative verbs: the check exists to catch the player
# being handed conduct they never declared, not to police prose.
# Verb STEMS a resolved_event uses when it gives someone an ACT, matched with
# ordinary English inflection (-s/-es/-ed/-ing) so "straightens", "shifting"
# and "reached" all count. Kept to unambiguous bodily/manipulative verbs: this
# exists to catch the player being handed conduct they never declared, not to
# police prose.
_PLAYER_ACT_STEMS = (
    "take", "took", "grab", "lift", "raise", "lower", "drink", "drank", "sip",
    "eat", "ate", "swallow", "nod", "shrug", "smile", "step", "walk", "move",
    "turn", "stand", "stood", "straighten", "rise", "rose", "sit", "sat",
    "kneel", "crouch", "lean", "shift", "reach", "push", "pull", "open",
    "close", "hand", "press", "grip", "hold", "held", "accept", "follow",
    "drop", "place", "put", "set", "wipe", "brush", "tighten", "loosen",
    "cross", "tilt", "lift", "swing", "climb", "duck", "slide", "settle",
)
_PLAYER_ACT_VERBS = "|".join(
    rf"{stem}(?:e?s|ed|ing|d)?" for stem in _PLAYER_ACT_STEMS
)



# Leading words that are not the name itself. Splitting a name on whitespace
# and taking token 0 matched "The" for a player called "The Stranger", which
# then matched almost every sentence in the beat.
_NAME_LEADERS = {"the", "a", "an", "dr", "dr.", "mr", "mr.", "mrs", "mrs.",
                 "ms", "ms.", "miss", "lord", "lady", "sir", "captain", "cmdr",
                 "cmdr.", "commander", "doctor", "lt", "lt.", "sgt", "sgt."}


def _player_name_forms(player_name):
    """Sentence-opening forms that identify the player: the full name, plus any
    single word of it substantial enough to stand alone."""
    name = str(player_name or "").strip()
    if not name:
        return []
    forms = [name]
    for word in re.split(r"[\s,]+", name):
        clean = word.strip()
        if (len(clean) >= 3 and clean[:1].isupper()
                and clean.casefold() not in _NAME_LEADERS):
            forms.append(clean)
    # Longest first so "The Stranger" is preferred over "Stranger".
    return sorted(set(forms), key=len, reverse=True)


def _player_subject_sentences(prose, player_name):
    """Sentences of `prose` whose grammatical subject is plainly the player --
    the sentence OPENS with their name (optionally possessive). Deliberately
    narrow: a pronoun subject ("She lifts it") could refer to any character in
    the beat, and guessing would make this cry wolf on ordinary narration."""
    forms = _player_name_forms(player_name)
    if not prose or not forms:
        return []
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", prose):
        stripped = sentence.strip()
        for form in forms:
            if re.match(rf"^{re.escape(form)}(?:'s)?\b", stripped):
                out.append(stripped)
                break
    return out


# A sentence whose subject is a bare pronoun, optionally after a short leading
# adverbial ("After a moment, he lowers the device"). Bounded so it cannot
# reach past a genuine subject into a subordinate clause.
_SUBJECT_PRONOUN_RE = re.compile(r"^(?:[^,]{0,40},\s*)?(?:he|she|they)\b", re.I)

_SUBJECT_OPENERS = {}


def _subject_opener(form):
    """Does a sentence OPEN with this name, as subject or possessive?

    Tolerates a LEADING ARTICLE, because the article belongs to the prose and
    not to the name. A body registered as "A Dalek" is written "The Dalek" the
    moment it stops being new, and the article is the only difference -- the
    same trap `docs/UNBUILT.md` §1.17 documents for presence identity. Without
    this every subject-anchored guard silently missed such a body: live
    (chat 58, t28) the Dalek's own view read "The Dalek's visual sensors pick
    up...", "The Dalek hears...", "The Dalek's own base grinds forward" --
    third person about its own perceiver, straight past `_strip_self_narration`,
    whose forms were "A Dalek" and "Dalek" and neither of which opens that
    sentence.

    ONLY the three articles. A TITLE is frequently the only thing telling two
    bodies apart ("the guard" is not "the captain"), so `_NAME_LEADERS` stays
    out of this deliberately -- the same line §1.17 draws.

    The name itself keeps its case sensitivity: a capitalised form matches
    case-sensitively as before, so an ordinary noun that happens to spell a
    name does not bind.
    """
    pat = _SUBJECT_OPENERS.get(form)
    if pat is None:
        pat = re.compile(
            rf"^(?:[Tt]he\s+|[Aa]n?\s+)?{re.escape(form)}(?:'s|’s)?\b",
            re.I if form[:1].islower() else 0)
        _SUBJECT_OPENERS[form] = pat
    return pat


def _sentence_subjects(prose, names, split=None):
    """Each sentence of `prose` paired with the name that is plainly its subject.

    `_player_subject_sentences` deliberately refuses to resolve pronouns, on
    the ground that "She lifts it" could be anyone in the beat. That is true of
    a pronoun read in ISOLATION and false of one read in sequence: prose
    establishes a subject by name and then continues it, which is why the
    live miss (chat 56 t1391) slipped through -- the Director named the Doctor
    once, then wrote four more sentences about him as "he", and a check that
    only reads sentence-opening names saw only the one legitimate sentence.

    So: track the most recently NAMED subject and let a pronoun-subject
    sentence continue it. A new named subject takes over, which is what keeps
    this honest -- "The Doctor draws it. Hinami flinches. She says nothing."
    binds the pronoun to Hinami, not to the Doctor. Where no name has been
    established yet, the pronoun binds to nobody rather than to a guess.

    Yields (sentence, subject_name_or_None) in order.

    `split` overrides the sentence splitter for callers that need a different
    one -- perception's tolerates a closing quote between the terminal
    punctuation and the space, and losing that would silently make a whole
    passage one "sentence" again.
    """
    current = None
    pieces = (split.split(prose or "") if split is not None
              else re.split(r"(?<=[.!?])\s+", prose or ""))
    for sentence in pieces:
        stripped = sentence.strip()
        if not stripped:
            continue
        matched = None
        for cand in (names or []):
            for form in _player_name_forms(cand):
                if _subject_opener(form).match(stripped):
                    matched = cand
                    break
            if matched:
                break
        if matched:
            current = matched
            yield stripped, matched
        elif _SUBJECT_PRONOUN_RE.match(stripped):
            yield stripped, current
        else:
            yield stripped, None


# A conjunct that introduces its OWN subject is not the tracked body's doing.
_NEW_SUBJECT_RE = re.compile(
    r"^(?:he|she|they|it|who|which|that|i|we|you)\b", re.I)


def _predicate_heads(tail, window):
    """The head words of each conjunct of a predicate.

    One subject governs several verbs -- "takes a half-step closer, hands open
    at his sides, and speaks in a low, steady voice" is one body doing two
    things -- so a window measured from the NAME sees only the first verb and
    the second escapes. That is exactly how the live case slipped past: the
    attribution verb sat twelve words past the subject, and the window is
    three. Measuring the window from each conjunct instead keeps the check on
    what this body is DOING (rather than any word anywhere in a long sentence)
    while letting it reach the later verbs of a compound predicate.

    Conjuncts that introduce their own subject are dropped: in "The Doctor
    lowers the device, and she says nothing" the saying is hers.

    Returns (head, clause) pairs -- the head for verb matching, the whole
    clause for tests that read wider than the verb (see `_PROXIMITY_RE`).
    """
    heads = []
    for part in re.split(r",|\band\b|\bthen\b|;", tail or "", flags=re.I):
        part = part.strip()
        if not part or _NEW_SUBJECT_RE.match(part):
            continue
        heads.append(
            (" ".join(re.findall(r"[A-Za-z']+", part)[:window]), part))
    return heads


def _strip_subject(sentence, name):
    """A sentence's predicate: everything past its subject, whether that
    subject was written as the name or as a pronoun continuing it."""
    for form in _player_name_forms(name):
        match = re.match(rf"^{re.escape(form)}(?:'s)?\b", sentence)
        if match:
            return sentence[match.end():]
    match = _SUBJECT_PRONOUN_RE.match(sentence)
    return sentence[match.end():] if match else ""


# Speech verbs, as the stem-plus-inflection pattern `_PLAYER_ACT_VERBS` uses.
# Only verbs that ASSERT an utterance: "considers", "hesitates", "looks" are
# not speech, and a character who declared silence is entitled to all of them.
_ATTRIBUTION_STEMS = (
    "say", "speak", "reply", "respond", "answer", "add", "offer", "remark",
    "observe", "note", "comment", "continue", "go on", "put in", "interject",
    "interrupt", "counter", "retort", "insist", "repeat", "explain", "admit",
    "confess", "agree", "protest", "object", "ask", "inquire", "wonder aloud",
    "murmur", "mutter", "mumble", "whisper", "breathe", "hiss", "growl",
    "purr", "drawl", "call", "shout", "yell", "cry", "exclaim", "declare",
    "announce", "state", "tell", "greet", "chuckle out", "manage",
)
# NOTE the distinct name: `_SPEECH_VERBS` further down is a different thing
# (a literal tuple used for dialogue-cue detection). Two symbols of that name
# in one module is exactly the duplicate `make structure` fails on.
def _inflect(stem):
    """A stem as a regex matching its inflections.

    English inflects a phrasal verb on its HEAD, not its tail: "puts in", not
    "put ins". Appending the suffix group to the whole escaped stem silently
    produced a pattern that could never match the form people actually write,
    which is worse than not listing the verb at all -- it reads as covered.
    """
    head, _, rest = str(stem).partition(" ")
    pattern = rf"{re.escape(head)}(?:e?s|ed|ing|d)?"
    return rf"{pattern}\s+{re.escape(rest)}" if rest else pattern


_ATTRIBUTION_VERBS = "|".join(_inflect(stem) for stem in _ATTRIBUTION_STEMS)

# How far past the name to look for the verb. Same window the player check
# uses, and for the same reason: the act must be what this body is DOING, not
# a word appearing anywhere in a long sentence.
_SPEECH_VERB_WINDOW = 3


def _check_character_speech_authority(resolved_event, silent_names,
                                      other_names=()):
    """Speech a resolved_event gives a character who declared none this beat.

    The mirror of `_check_player_act_authority`, and the boundary it defends is
    the same one from the other side. Live, alpha 6.0.2: a character agent
    declared silence -- empty sequence, `stop_reason: "natural silence"`, no
    dialogue_log entry -- and the resolved_event said "<the character> adds a
    further comment" anyway. Perception rendered a speech event with no
    content; the narrator, having nothing to quote, dressed the absence as
    inaudibility. It read as a muffling bug and was a fabrication.

    A character owns their own speech exactly as the player owns theirs, and
    until now only the player had a guard. Nothing objected when the Director
    authored conduct for a mind that owns it.

    Scoped like its sibling, to the unambiguous case: the character was ASKED
    this beat and declared NO speech at all, so any utterance attributed to
    them is invented by construction. Sentence subject must be the name
    itself -- a pronoun subject could be anyone in the beat, and guessing
    would make this cry wolf on ordinary narration.

    `silent_names` is who declared nothing; a character who spoke is not
    checked, because separating an elaborated line from an added one needs
    more than a verb list.

    Subject resolution is pronoun-continuation-aware (`_sentence_subjects`)
    and the verb window is measured per conjunct (`_predicate_heads`). Both
    were added after chat 56 t1391, where the guard was armed and silent: the
    Director wrote the fabrication as "He takes a half-step closer, hands open
    at his sides, and speaks in a low, steady voice", which the original
    name-anchored, three-words-from-the-name check could not see at all.
    """
    warnings = []
    all_names = list(silent_names or []) + list(other_names or [])
    for sentence, subject in _sentence_subjects(resolved_event, all_names):
        if subject is None or subject not in (silent_names or []):
            continue
        # A quoted span is `_check_prose_quote_authority`'s business, not
        # this one: what this catches is the contentless attribution a quote
        # check cannot see -- "X adds a comment" quotes nothing, so nothing
        # downstream can tell it was invented.
        without_quotes = re.sub(r'"[^"]*"|“[^”]*”', " ", sentence)
        tail = _strip_subject(without_quotes, subject)
        for head, _clause in _predicate_heads(tail, _SPEECH_VERB_WINDOW):
            if re.search(rf"\b(?:{_ATTRIBUTION_VERBS})\b", head, re.I):
                warnings.append(
                    "Speech attributed to a character who declared none "
                    f"(character-speech authority): {subject}: "
                    f"{sentence[:120]!r}"
                )
                break
    return warnings


# Verbs that change where a body IS or how far it is from someone else. The
# Director may render a declared act richly; it may not relocate a character
# who declared no movement, because distance is load-bearing -- it decides
# what perception delivers, what contact is possible, and (chat 56 t1391) it
# can directly reverse the intent the character declared, which was to scan
# her "without crowding her".
_LOCOMOTION_STEMS = (
    "step", "walk", "stride", "move", "approach", "advance", "close",
    "cross", "back", "retreat", "withdraw", "edge", "inch", "sidle",
    "lean", "kneel", "crouch", "climb", "duck", "slide", "settle",
    "follow", "enter", "leave", "come", "came", "go", "went", "reach",
    "closes the distance", "draw closer", "draw nearer",
)
_LOCOMOTION_VERBS = "|".join(_inflect(stem) for stem in _LOCOMOTION_STEMS)

# Movement is not always written as a locomotion VERB. The live case wrote it
# as a verb plus a distance noun -- "takes a half-step closer" -- whose head
# verb is "take", which is no more locomotive than taking a screwdriver. What
# marks it as movement is the distance word, so read the clause for one.
_PROXIMITY_RE = re.compile(
    r"\b(?:closer|nearer|half[-\s]?step|a\s+step|steps?\s+"
    r"(?:closer|nearer|back|away|toward|towards|forward)"
    r"|closes?\s+the\s+distance|within\s+(?:arm|reach))\b", re.I)


def _check_character_act_authority(resolved_event, declared_actions, name,
                                   other_names=()):
    """Physical acts a resolved_event gives a CHARACTER they did not declare.

    The third side of the same boundary `_check_player_act_authority` and
    `_check_character_speech_authority` defend, and the one nothing guarded:
    act authority was enforced for the player only, so a character could be
    handed conduct freely. Live, chat 56 t1391: the Doctor declared a scan
    "from several feet away", "while staying at distance", and the resolve had
    him take "a half-step closer". The narrator dropped it, so it was invisible
    in play -- and it still committed as his own episodic memory of what he did.

    Two scopes, because the two cases admit different certainty:

    * The character declared NO action at all. Silence about conduct is a
      declaration, so any act is invented by construction -- the full act-verb
      list applies, exactly as for the player.

    * The character declared actions, none of them locomotive. Elaborating a
      declared act is the Director's job and is NOT flagged; separating
      elaboration from addition in general needs more than a verb list, so
      this narrows to the one addition that is unambiguous and consequential:
      MOVEMENT. A character who declared no movement was not moved.
    """
    if not name:
        return []
    declared_text = " ".join(
        f"{a.get('attempt', '')} {a.get('observable', '')}"
        for a in (declared_actions or []) if isinstance(a, dict)
    )
    if declared_actions:
        # Already moving under their own declaration: the Director may render
        # that movement however it likes.
        if re.search(rf"\b(?:{_LOCOMOTION_VERBS})\b", declared_text, re.I):
            return []
        verbs, kind, proximity = (
            _LOCOMOTION_VERBS, "undeclared movement", True)
    else:
        verbs, kind, proximity = _PLAYER_ACT_VERBS, "act not declared", False

    warnings = []
    all_names = [name] + [n for n in (other_names or []) if n != name]
    for sentence, subject in _sentence_subjects(resolved_event, all_names):
        if subject != name:
            continue
        without_quotes = re.sub(r'"[^"]*"|“[^”]*”', " ", sentence)
        tail = _strip_subject(without_quotes, subject)
        for head, clause in _predicate_heads(tail, 3):
            if re.search(rf"\b(?:{verbs})\b", head, re.I) or (
                    proximity and _PROXIMITY_RE.search(clause)):
                warnings.append(
                    f"Character {kind} this beat (character-act authority): "
                    f"{name}: {sentence[:120]!r}"
                )
                break
    return warnings


# Quoted spans, in every style the resolve model actually produces. The single
# -quote form must not mistake an apostrophe for a delimiter, so a quote may
# only OPEN where no letter precedes it and CLOSE where no letter follows --
# which leaves "You're" intact inside the span.
_PROSE_QUOTE_RES = (
    re.compile(r'"([^"]+)"'),
    re.compile(r"“([^”]+)”"),
    re.compile(r"‘([^’]+)’"),
    re.compile(r"(?<![A-Za-z])'((?:[^']|'(?=[A-Za-z]))+)'(?![A-Za-z])"),
)

# Below this, a quoted span is a label or a scare quote rather than an
# utterance -- a readout reading "STABLE", the word "safe".
_PROSE_QUOTE_MIN_WORDS = 3


def _check_prose_quote_authority(resolved_event, allowed_bodies):
    """Spoken lines in resolved_event PROSE that nobody declared.

    The dialogue_log backstop (director.py) drops a director-invented line for
    a registered character by comparing its `exact_quote` against that
    character's own declaration. It is a good guard and it was inert in chat 56
    t1391, because `dialogue_log` was EMPTY: the invented line existed only in
    the resolved_event prose. The speech check meanwhile strips quoted spans on
    the stated assumption that the dialogue path covers them. Each guard
    assumed the other held the ground, and a quote in prose with no log entry
    fell between them.

    This closes it from the other side, and needs no subject resolution to do
    it: a line nobody declared is invented no matter WHO the prose says said
    it. `allowed_bodies` is every quote body that was legitimately declared
    this beat -- by the player, by any character, or by an unsheeted background
    presence the Director is licensed to voice.
    """
    warnings = []
    seen = set()
    for pattern in _PROSE_QUOTE_RES:
        for span in pattern.findall(resolved_event or ""):
            body = _quote_body(span)
            if not body or body in seen:
                continue
            seen.add(body)
            if len(re.findall(r"[A-Za-z']+", body)) < _PROSE_QUOTE_MIN_WORDS:
                continue
            if body in allowed_bodies:
                continue
            warnings.append(
                "Spoken line in resolved_event that nobody declared "
                f"(prose-quote authority): {body[:120]!r}"
            )
    return warnings


# Determiners that make a reference DEFINITE. "That explains the strange
# coins" refers to HER coins, a thing in the world; "local trade runs on
# copper and silver coins" is knowledge about coins in general. The definite
# article is what turns a generality into a claim of acquaintance, so it is
# what gates the single-word match below.
_DEFINITE_DETS = ("the", "this", "that", "these", "those",
                  "your", "her", "his", "their", "its", "my", "our")


# WHAT THE DIRECTOR MAY STILL SPEAK FOR.
#
# Measured 2026-08-08 across the whole corpus: background lines authored in
# `director_resolve` run a MEDIAN OF 8 WORDS against the sheeted cast's 16, and
# 27% of them are four words or fewer against the cast's 13% -- "Dragon
# Kingdom...", "Kadomon.", "Sorry-sorry-". 2,042 of the 2,240 background lines
# in the corpus came from the Director; the stage built to voice extras
# produced 200, because `pick_background_reactors` is a BACKSTOP that stands
# down whenever the Director already spoke for someone.
#
# So the model adjudicating physics, dialogue order, state diffs and time in
# one pass was also writing every extra's dialogue, as filler, with no
# perception object for the speaker. That is one cause with two symptoms: the
# flatness above, and the Kadoman leak that `_check_presence_knowledge_channel`
# exists to catch.
#
# These kinds keep the Director's voice because a full character call would buy
# nothing: their speech is formulaic or barely linguistic -- a beast's snarl, a
# swarm, a drone's stock phrase. Anything PERSON-shaped is routed to the
# background stage, which gives it its own call, its own perception object and
# its own recognition of the room. The list is deliberately narrow: routing a
# borderline speaker costs one call and gets a better line, while keeping one
# costs the defect this whole change exists to remove.
_DIRECTOR_VOICEABLE_KINDS = frozenset({
    "creature", "monster", "beast", "animal", "mount", "swarm",
    "undead", "zombie", "revenant", "drone", "automaton", "construct",
    "golem",
})


def director_may_voice(speaker, scene, presence_rec=None):
    """Whether the Director may author this background speaker's dialogue.

    Kind is read from the scene entity, then from the presence record's own
    sketch. An UNKNOWN kind routes to the background stage -- the conservative
    direction, because the failure it avoids (a person voiced as filler) is the
    one that was actually measured, and the cost of being wrong is one model
    call rather than a flat line and a possible leak.
    """
    name = str(speaker or "").strip()
    if not name:
        return False
    ents = (scene or {}).get("entities") or {}
    ent = ents.get(name)
    if not isinstance(ent, dict):
        lowered = name.casefold()
        ent = next((v for k, v in ents.items()
                    if isinstance(v, dict)
                    and (str(k).casefold() == lowered
                         or str(v.get("name") or "").casefold() == lowered)), None)
    kind = str((ent or {}).get("kind") or "").strip().casefold()
    if not kind:
        kind = str(((presence_rec or {}).get("sketch") or {}).get("kind")
                   or "").strip().casefold()
    return kind in _DIRECTOR_VOICEABLE_KINDS


def _check_presence_knowledge_channel(speaker, quote, sc, presence_rec,
                                      heard_text):
    """Scene-entity references in a Director-voiced presence line that the
    presence has no perceptual channel to.

    The Director is entitled to omniscience -- it owns objective causality --
    and the resolve prompt licenses it to voice unsheeted background
    presences. Nothing sat between those two facts: the voicing was authored
    from the omniscient working state with no perception object for the
    speaker. Chat 65 t2148 is the measured case -- Kadoman, a presence minted
    at turn 9 in eastern_market, referring to "the strange coins and notes"
    shown once at turn 4 in fountain_plaza and pocketed since.

    Deterministic floor, subtractive on purpose: it tests REFERENCES the
    engine can resolve (scene entities by name or alias), never meaning. A
    multi-word phrase matches bare; a single-word alias matches only under a
    definite/possessive determiner, because "the strange coins" claims
    acquaintance while "gold coins" is generic knowledge -- a presence must
    keep every true general thing it can say about its own world (the
    copper-and-silver rule), and a presence with no channel must be free to
    be ignorant in front of the player.

    The channel test is current-scene only (presences are stateless): an
    entity offers a channel when it is placed in the presence's own room and
    not shut inside anything (`hiding_holders_of`, both containment forms).
    An unplaced entity offers no provable channel -- in the measured corpus
    the unplaced entities are precisely the pocketed belongings, while room
    furniture lives in room `anchors`, which this never reads. ``heard_text``
    is what legitimately names things into the presence's beat: everything
    spoken aloud this beat by others, plus the presence's own record and
    characterization. Returns warning strings; empty means no leak.
    """
    q = " %s " % re.sub(r"\s+", " ", str(quote or "")).casefold()
    if not q.strip():
        return []
    entities = (sc or {}).get("entities") or {}
    positions = (sc or {}).get("positions") or {}
    speaker_cf = str(speaker or "").strip().casefold()
    heard_cf = str(heard_text or "").casefold()

    p_room = room_of(sc, speaker)
    if not p_room:
        by_name = {str((e or {}).get("name") or "").strip().casefold(): eid
                   for eid, e in entities.items() if isinstance(e, dict)}
        eid = by_name.get(speaker_cf)
        if eid:
            p_room = positions.get(eid) or room_of(sc, eid)
    if not p_room:
        p_room = ((presence_rec or {}).get("sketch") or {}).get("station_room")

    warnings = []
    for eid, edef in entities.items():
        if not isinstance(edef, dict):
            continue
        name = str(edef.get("name") or "").strip()
        name_cf = name.casefold()
        if name_cf and name_cf == speaker_cf:
            continue  # a presence may always speak of itself
        phrases = {p for p in
                   ({name} | {str(a).strip()
                              for a in (edef.get("aliases") or [])})
                   if p and len(p) >= 3}
        if not phrases:
            continue
        if any(p.casefold() in heard_cf for p in phrases):
            continue  # named aloud in the presence's beat, or its own record
        e_room = (positions.get(eid) or room_of(sc, eid)
                  or (room_of(sc, name) if name else None))
        concealed = bool(hiding_holders_of(sc, eid)) or (
            bool(name) and bool(hiding_holders_of(sc, name)))
        if p_room and e_room == p_room and not concealed:
            continue  # placed here, in the open: a channel exists
        hit = None
        for p in sorted(phrases, key=len, reverse=True):
            pcf = p.casefold()
            if len(p.split()) >= 2:
                if re.search(r"(?<!\w)%s(?!\w)" % re.escape(pcf), q):
                    hit = p
                    break
            elif re.search(
                    r"(?<!\w)(?:%s)\s+(?:[\w'-]+\s+){0,2}%s(?!\w)"
                    % ("|".join(_DEFINITE_DETS), re.escape(pcf)), q):
                hit = p
                break
        if hit:
            where = "unplaced" if not e_room else e_room
            warnings.append(
                f"Background presence {speaker!r} references {hit!r} "
                f"({name or eid}: {where}"
                + (", concealed" if concealed else "")
                + f") with no perceptual channel from "
                + (repr(p_room) if p_room else "an unknown room")
                + " (presence-knowledge channel)."
            )
    return warnings


# Interior states a resolved_event may not assert about the PLAYER. Nouns and
# adjectives that name what is INSIDE a mind, as against the surface a body
# shows: "trembling", "wide eyes", "a shrill cry" are observable and always
# allowed; "terror", "panic", "she realises" are not.
_INTERIOR_STATES = (
    "terror", "terrified", "panic", "panicked", "fear", "afraid", "frightened",
    "dread", "horror", "horrified", "anguish", "despair", "grief", "sorrow",
    "misery", "miserable", "shame", "ashamed", "humiliation", "humiliated",
    "guilt", "regret", "remorse", "rage", "fury", "furious", "resentment",
    "bitterness", "envy", "jealousy", "loneliness", "longing", "yearning",
    "desire", "arousal", "lust", "joy", "elation", "delight", "relief",
    "relieved", "contentment", "gratitude", "hope", "anxiety", "anxious",
    "unease", "uneasy", "embarrassment", "embarrassed", "confusion",
    "confused", "curiosity", "curious", "trust", "distrust", "affection",
)

# Verbs that report a mind's own operation rather than its body's motion.
_INTERIOR_VERBS = (
    "realise", "realize", "understand", "know", "believe", "doubt", "wonder",
    "want", "wish", "hope", "fear", "decide", "intend", "remember", "recall",
    "feel", "sense", "notice that", "recognise", "recognize", "regret",
)

# Words that assert an interior state is TRUE, which no observer may know.
_INTERIOR_CERTAINTY = ("genuine", "real", "true", "unmistakable", "obvious",
                       "clearly", "plainly", "evident", "undisguised")


def _check_player_interiority_authority(resolved_event, player_name,
                                        declared_text="", other_names=()):
    """Interior states a resolved_event asserts about the PLAYER.

    The mirror of `_check_player_act_authority` for feeling rather than doing,
    and the same boundary. The Director owns objective causality; it does not
    own what is inside the protagonist. It may report every observable the
    body shows -- trembling, wide eyes, a shrill cry -- and must stop there,
    because naming the state behind them decides for the player what their
    character feels.

    Live, alpha 6.3, chat 52 turn 19: the player typed only "W-what did you do
    to me!?" and the resolve wrote "the shrill, PANICKED cry" and "she takes in
    the GENUINE TERROR in those wide eyes". Perception then copied both into
    another character's view, so an invented interior state became something a
    second mind had observed as fact.

    Exempt: anything the player themselves wrote. If they declared the fear,
    it is theirs to declare -- this catches what arrives from nowhere.
    `_INTERIOR_CERTAINTY` is flagged only ALONGSIDE an interior word, because
    "genuine" is unremarkable on its own and damning next to "terror".

    A sentence counts as being about the player when it NAMES them (they may be
    its object -- "she takes in the genuine terror in those wide eyes" is about
    the player from another body's side) or when subject tracking resolves it
    to them. The second was added after chat 56 ("Run!") t6: against a player
    who declared only "You imitate them slightly and shudder", the resolve
    wrote "She looks at him, still shaky, but the terror in her eyes has begun
    to recede" -- deciding the player's emotional arc for them. The name-only
    test could not see a pronoun subject, so nothing fired, and perception
    copied the sentence into the player's OWN view.
    """
    if not resolved_event or not player_name:
        return []
    declared = str(declared_text or "").casefold()
    all_names = [player_name] + [
        n for n in (other_names or []) if n and n != player_name]
    warnings = []
    for body, subject in _sentence_subjects(resolved_event, all_names):
        if not body:
            continue
        low = body.casefold()
        if subject != player_name and not _mentions_player(low, player_name):
            continue
        hits = [w for w in _INTERIOR_STATES
                if re.search(rf"\b{re.escape(w)}\b", low)
                and not re.search(rf"\b{re.escape(w)}\b", declared)]
        hits += [v for v in _INTERIOR_VERBS
                 if re.search(rf"\b{re.escape(v)}(?:s|es|d|ed|ing)?\b", low)
                 and not re.search(rf"\b{re.escape(v)}", declared)]
        if not hits:
            continue
        certainty = [c for c in _INTERIOR_CERTAINTY
                     if re.search(rf"\b{re.escape(c)}\b", low)]
        warnings.append(
            "Player interior state not declared this beat "
            "(player-interiority authority): "
            f"{sorted(set(hits))[:3]}"
            + (f" asserted as {certainty[0]!r}" if certainty else "")
            + f": {body[:120]!r}")
    return warnings


def _mentions_player(low_sentence, player_name):
    """Whether a sentence is ABOUT the player -- their name, or a possessive
    reaching for them. Pronouns are not guessed at: "her terror" in a
    two-woman scene could be either of them, and a guess here would flag
    ordinary NPC description."""
    for form in _player_name_forms(player_name):
        if re.search(rf"\b{re.escape(form.casefold())}\b", low_sentence):
            return True
    return False


# Verbs that put a body in contact with something outside itself.
# Deliberately excludes verbs that read as manipulation but usually are not:
# "catch" ("her hair catching the warm light"), "draw" ("draws a breath"),
# "find" ("finds the words"). The list must earn its flags -- an act guard
# that fires on scenery is one a maintainer learns to ignore.
_MANIPULATION_STEMS = (
    "grip", "grab", "take", "took", "hold", "held", "pull", "push", "press",
    "lift", "open", "close", "drop", "place", "put", "set", "hand", "accept",
    "drink", "eat", "clutch", "seize", "tug", "twist", "touch", "grasp",
    "wrap", "pick", "pocket", "snatch", "shove", "haul",
)
_MANIPULATION_VERBS = "|".join(_inflect(stem) for stem in _MANIPULATION_STEMS)

# The player's own body is not a new object. An act on it re-describes what
# they are doing with themselves, which is elaboration however it is worded --
# "pushes herself upright" for a declared "slowly stands up".
_OWN_BODY_NOUNS = frozenset("""
hand hands finger fingers fist fists arm arms elbow elbows chest head hair
face eye eyes ear ears tail tails mouth lips lip throat neck shoulder shoulders
back knee knees leg legs foot feet body breath breaths weight skin palm palms
cheek cheeks jaw brow chin waist hip hips heart lungs ribs stomach nose tongue
herself himself themselves itself myself yourself ourselves
""".split())

# The DIRECT object a verb takes -- the noun it acts ON, with no preposition
# in between. "grip the edge" is taking hold of the world; "pressed flat
# AGAINST the cold metal" is a body bracing itself, and reading that as
# seizing the metal is how a guard starts crying wolf on ordinary prose.
# The captured group is the whole noun phrase after the article; the HEAD noun
# is its last word, so "the warm light" reads as "light" rather than "warm".
_DIRECT_OBJECT_RE = re.compile(
    r"^(?:\s+(?!(?:against|on|onto|at|to|from|with|beneath|under|over|into|"
    r"in|toward|towards|across|by|around|through|near|beside|behind)\b)"
    r"[A-Za-z']+){0,2}\s+(?:the|a|an)"
    # Stop the noun phrase at a preposition or conjunction, or "the edge of
    # the console" reads its head noun as "the".
    r"((?:\s+(?!(?:of|in|on|at|to|from|with|for|as|and|but|by|into|onto)\b)"
    r"[A-Za-z']+){1,3})", re.I)


def _undeclared_world_object(clause, declared_low):
    """The world object a clause has the player take hold of, when the player's
    own declaration never mentions it. None when the clause touches only their
    own body, reaches for nothing, or names something they already declared."""
    for match in re.finditer(rf"\b(?:{_MANIPULATION_VERBS})\b", clause, re.I):
        obj = _DIRECT_OBJECT_RE.match(clause[match.end():])
        if not obj:
            continue
        phrase = obj.group(1).split()
        noun = phrase[-1].casefold()
        # A phrase headed by the player's own body is elaboration whatever
        # sits in front of it: "the edge of the console" is the console.
        if noun in _OWN_BODY_NOUNS or any(
                w.casefold() in _OWN_BODY_NOUNS for w in phrase):
            continue
        if re.search(rf"\b{re.escape(noun)}", declared_low):
            continue
        return noun
    return None


def _check_player_act_authority(resolved_event, declared_actions, player_name,
                                other_names=(), declared_text=""):
    """Physical acts a resolved_event gives the PLAYER that they did not declare
    (live: Elevator Adventure t63 -- the player said only "Let's get going?" and
    the Director had them take a bottle, drink from it and nod; t59 -- the player
    ASKED "I hope you don't mind if I lean on you" and the Director performed the
    leaning for them).

    Adding detail to a declared act is legitimate and is NOT flagged -- the
    Director is supposed to render an act richly. What this catches is an act
    appearing from nowhere, which then replays when the player declares it a
    beat later, so the same moment happens twice and the scene falls out of
    order.

    Two scopes, as for characters (`_check_character_act_authority`) -- but the
    second is drawn differently, because a character's latitude is not the
    player's. The Director may elaborate a character freely and is narrowed
    only on MOVEMENT; the player owns all of their conduct, so the question
    here is not "what kind of act" but "is this act the one they declared".

    * The player declared NO action this beat: any act is invented by
      construction, and the full verb list applies. Unchanged.

    * The player declared actions: rendering those richly is the Director's
      job and stays untouched however it is worded -- "pushes herself upright"
      elaborates a declared "slowly stands up" and shares not one word with it,
      so no vocabulary test can separate the two. What CAN be separated is
      WHAT the act touches. Elaboration re-describes the player's own body;
      fabrication reaches out and takes hold of the world. So this narrows to
      the one addition that is both unambiguous and consequential: the player
      given a grip on a world object their declaration never mentions.

      Live, chat 56 ("Run!") t10: the player typed `"Heh? What are we doing
      what's going on?" You look genuinely confused.` and the resolve wrote
      "her hands coming up to grip the edge of the console, fingers finding a
      lever as if to steady herself". Perception copied it into the player's
      OWN view as "I grip the console edge", the narrator rendered it as fact,
      and the player's very next input was "Which lever?!" -- the fabricated
      act replayed a beat later, which is the exact failure this guard was
      written to stop. The old blanket `if declared_actions: return []` let it
      through, and this player narrated a gesture on every single beat, so the
      guard was disarmed for the entire story.
    """
    if not player_name:
        return []
    declared_low = None
    if declared_actions:
        declared_low = " ".join(
            f"{a.get('attempt', '')} {a.get('observable', '')}"
            for a in declared_actions if isinstance(a, dict)
        ).casefold() + " " + str(declared_text or "").casefold()
    warnings = []
    all_names = [player_name] + [
        n for n in (other_names or []) if n and n != player_name]
    for sentence, subject in _sentence_subjects(resolved_event, all_names):
        if subject != player_name:
            continue
        # Speech attribution ("Hinami says, ...") is not a physical act; the
        # quote itself is guarded separately by the dialogue_log check and by
        # `_check_prose_quote_authority`.
        without_quotes = re.sub(r'"[^"]*"|“[^“”]*”', " ", sentence)
        tail = _strip_subject(without_quotes, subject)
        # Per conjunct, not three words from the subject: one subject governs
        # several verbs, and a window measured from the name sees only the
        # first (see `_predicate_heads`).
        for head, clause in _predicate_heads(tail, 3):
            if declared_low is None:
                if not re.search(rf"\b(?:{_PLAYER_ACT_VERBS})\b", head, re.I):
                    continue
                detail = ""
            else:
                noun = _undeclared_world_object(clause, declared_low)
                if not noun:
                    continue
                detail = f" (undeclared hold on {noun!r})"
            warnings.append(
                "Player act not declared this beat (player-act authority)"
                f"{detail}: {sentence[:120]!r}"
            )
            break
    return warnings


# Both quote-span shapes below are constants, hoisted to module level like the
# other hot-path patterns in this file (_QUOTED_SPAN_RE etc.) -- each was being
# re-compiled on every narrator validation pass. The capper keeps the
# surrounding marks (it rewrites spans); the fidelity check needs only the
# body, and tolerates shorter lines.
_QUOTE_SPAN_RE = re.compile(r'(["“])([^"“”]{6,})(["”])')
_QUOTE_BODY_RE = re.compile(r'["“]([^"“”]{4,})["”]')


def _cap_repeated_quotes(prose, view, exclude_bodies=()):
    """Cap each spoken line's occurrences in the prose at how many times it
    actually appears in the authoritative source (the view). (Fable A1 / backlog
    P3.) `_dedupe_view_sentences` deliberately exempts quotes so an intentional
    repeat survives, which let a line the narrator both SUMMARIZED and quoted
    verbatim render twice (impostor t9: the last-stand speech; t5: Lady Thorne's
    kitchen-door line, verbatim, twice). A quote appearing more often than the
    source authorized is an artifact; drop the surplus occurrences, keep the
    first. The player's own lines are handled by the echo strip and excluded.
    """
    if not prose:
        return prose
    excluded = {re.sub(r"\s+", " ", str(b).casefold()) for b in (exclude_bodies or [])}
    quote_re = _QUOTE_SPAN_RE
    source_text = re.sub(r"\s+", " ", str(view or "").casefold())
    # Source count per body: how many times the view presents that exact line.
    source_counts = {}
    for m in quote_re.finditer(str(view or "")):
        body = re.sub(r"\s+", " ", m.group(2).strip().casefold())
        if body:
            source_counts[body] = source_counts.get(body, 0) + 1

    seen = {}
    out_parts = []
    last = 0
    for m in quote_re.finditer(prose):
        body = re.sub(r"\s+", " ", m.group(2).strip().casefold())
        if not body or body in excluded:
            continue
        cap = source_counts.get(body, 1)
        seen[body] = seen.get(body, 0) + 1
        if seen[body] > cap:
            # Surplus occurrence: excise this quoted span (keep the text
            # around it; the dangling-verb heal below tidies "he says ,").
            out_parts.append(prose[last:m.start()])
            last = m.end()
    if not out_parts:
        return prose
    out_parts.append(prose[last:])
    result = "".join(out_parts)
    result = _DANGLING_SPEECH_VERB_RE.sub(lambda mm: f"{mm.group(1)} it.", result)
    result = _DANGLING_SPEECH_COLON_RE.sub(_heal_dangling_colon, result)
    result = _collapse_empty_quote_debris(result)
    return re.sub(r"\s{2,}", " ", result).strip()


def _quote_body(quote):
    return (quote or "").strip().strip('"' + "'" + "\u201c\u201d\u2018\u2019")

# What survives muffling: stressed, longer words. Function words are the first
# thing lost, which is why an overheard fragment is a scatter of nouns and verbs
# rather than a summary.
_MUFFLE_KEEP_MIN = 4
_MUFFLE_MAX_WORDS = 3


def _muffled_fragment(body):
    """A partial transcript of what actually carried, not a description of it.

    This used to render "...something about <three middle words>...", which
    narrates the ACT of half-hearing instead of delivering the percept: the view
    said the perceiver heard something about a thing rather than letting them
    hear the pieces. It also read badly in prose and gave the narrator a stock
    phrase to echo.

    Each surviving word is emitted as its own ellipsis-separated chunk, and only
    ever verbatim -- `_scrub_invented_dialogue` validates a muffled line by
    checking every chunk against the lines actually spoken, so a chunk stitched
    across punctuation ("ledger, sink" -> "ledger sink") would fail that
    check and get the whole line dropped.
    """
    words = [w.strip(".,;:!?\"'\u201c\u201d\u2018\u2019") for w in (body or "").split()]
    kept = [w for w in words if len(w) >= _MUFFLE_KEEP_MIN]
    if not kept:
        return "...something indistinct..."
    if len(kept) > _MUFFLE_MAX_WORDS:
        # The longest carry best; original order is preserved so the fragment
        # still tracks the shape of the sentence.
        strongest = set(sorted(kept, key=len, reverse=True)[:_MUFFLE_MAX_WORDS])
        seen, kept2 = set(), []
        for w in kept:
            if w in strongest and w not in seen:
                seen.add(w)
                kept2.append(w)
        kept = kept2
    return "..." + "... ".join(kept) + "..."


def _inject_dialogue(view, display, quote, level, volume, can_see,
                    conducted=False, tone=""):
    if level == "none":
        return view
    body = _quote_body(quote)
    if not body or _contains_quote(view, body):
        return view
    if level == "fragment":
        return _append_once(
            view, f"A muffled voice: {_muffled_fragment(body)}")
    if conducted:
        # Heard from inside the speaker: the mass around the listener is the
        # medium, so it arrives low and close rather than across a distance.
        return _append_once(
            view,
            f"{display}'s voice carries through everything around you, "
            f'low and close: "{body}"')
    # Two forms of the same verb, because the two frames below take different
    # ones. "You hear X" is a bare-infinitive construction -- "you hear her
    # SAY", never "you hear her says" -- and this wrote the inflected form into
    # both, so every view of a speaker the perceiver could not see carried
    # broken English: 226 occurrences across 71 turns of the live corpus, all
    # of them in exactly the situations this engine cares most about (a voice
    # through a door, in the dark, from inside an enclosure).
    if volume == "shout":
        verb, bare = "shouts", "shout"
    elif volume in ("whisper", "mutter"):
        verb, bare = "says under their breath", "say under their breath"
    else:
        verb, bare = "says", "say"
    manner = ""
    tone = str(tone or "").strip()
    if tone and can_see:
        if re.search(r"\b(smirk|smile|grin|expression|look|gesture)\b", tone, re.I):
            article = "" if re.match(r"^(?:a|an|the)\b", tone, re.I) else "a "
            manner = f" with {article}{tone}"
        else:
            manner = f" with {tone} in their voice"
    if can_see:
        add = f'{display} {verb}{manner}: "{body}"'
    else:
        add = f'You hear {display} {bare}: "{body}"'
    return _append_once(view, add)

_OBSERVED_STOPWORDS = frozenset({
    "the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "at", "with",
    "her", "his", "their", "its", "she", "he", "they", "it", "him", "them",
    "as", "into", "toward", "towards", "across", "for", "from", "by", "up",
    "down", "over", "under", "then", "while", "is", "are", "was", "were", "be",
    "been", "this", "that", "these", "those", "your", "you", "herself",
    "himself", "themselves", "itself", "slightly", "slowly", "again",
    # Same category as the prepositions already above -- function words, not
    # distinctive content. Counting "against"/"beside" as evidence that two
    # descriptions are the same beat inflated overlap on unrelated actions
    # that merely happened near the same wall.
    "against", "beside", "behind", "near", "through", "around", "before",
    "between", "onto", "off", "out", "back", "away", "past", "along",
})


def _content_tokens(text):
    """Distinctive (stopword-stripped, crudely stemmed) word tokens of a phrase
    -- the basis for 'has this beat already been narrated?' overlap."""
    toks = []
    for raw in re.split(r"[^\w]+", str(text or "").lower()):
        if not raw or raw in _OBSERVED_STOPWORDS:
            continue
        for suf in ("ing", "ed", "es", "s"):
            if len(raw) > len(suf) + 2 and raw.endswith(suf):
                raw = raw[:-len(suf)]
                break
        toks.append(raw)
    return toks


def _self_second_person(text, forms):
    """Rewrite a PERCEIVER's own name/alias forms inside engine-supplied prose
    into second person, before that prose is injected into their own view.

    Every perception view is written from its perceiver's own vantage ("You
    are in the lobby..."), but the deterministic action backstop appends an
    actor's `observable` surface verbatim -- and those surfaces are authored
    in third person by the acting agent, naming everyone else by name. So
    Dr. Moon's "steps briskly from the barricade toward Hinami" landed in
    HINAMI'S OWN view, producing the same beat twice in two different persons
    ("...beside your shoulder. Dr. Moon steps briskly ... toward Hinami...")
    and handing the narrator a player_view that names the player in the third
    person -- the exact thing its PERSON DISCIPLINE rule forbids.

    Scope is deliberately narrow and deterministic: only the perceiver's own
    explicit name/alias tokens are rewritten (possessive -> "your", every
    other form -> "you"), never pronouns. A third-person pronoun later in the
    same clause that referred to the perceiver ("...beside her shoulder") is
    left alone -- resolving that anaphora needs a referent the engine cannot
    determine when the actor shares the perceiver's pronouns, and a wrong
    guess would be worse than a mildly loose one. Quoted spans survive
    verbatim: a name spoken aloud is sensory signal, and dialogue fidelity
    forbids rewriting it.
    """
    text = str(text or "")
    if not text:
        return text
    patterns = []
    for form in forms or []:
        form = str(form or "").strip()
        if not form:
            continue
        # Ordinary-English single-token names ("Rose", "Hope") are matched
        # case-sensitively, exactly as the identity scrub does, so common
        # lowercase prose is never rewritten into second person.
        flags = 0 if form.casefold() in _COMMON_WORD_NAMES else re.I
        patterns.append(re.compile(
            r"(?<!\w)" + re.escape(form) + r"(['’]s)?(?!\w)", flags))
    if not patterns:
        return text
    segments = _QUOTED_SPAN_RE.split(text)
    for i in range(0, len(segments), 2):  # even indices = unquoted prose
        before = segments[i]
        after = before
        for pattern in patterns:
            after = pattern.sub(_self_pronoun_sub, after)
        # A name in SUBJECT position leaves the verb inflected for third
        # person singular ("Hinami is caught" -> "You is caught"), which
        # would reach the player as visibly broken prose. Only run the
        # repair on segments this pass actually rewrote.
        segments[i] = _fix_you_agreement(after) if after != before else before
    return "".join(segments)


# Third-person-singular forms that must agree with an inserted "you".
_YOU_AGREEMENT = {
    "is": "are", "was": "were", "has": "have", "does": "do",
    "isn't": "aren't", "wasn't": "weren't", "hasn't": "haven't",
    "doesn't": "don't", "isn’t": "aren’t", "wasn’t": "weren’t",
    "hasn’t": "haven’t", "doesn’t": "don’t",
}

# Words that can follow a subject, end in -s, and are NOT verbs -- the guard
# on the regular-verb rule below, which otherwise strips a meaningful "s"
# ("You always" -> "You alway"). Deliberately a closed list: a missed entry
# costs one dropped letter, while dropping the rule entirely costs "You steps".
_NON_VERB_S_WORDS = frozenset({
    "afterwards", "always", "anyways", "backwards", "besides", "downwards",
    "forwards", "nevertheless", "onwards", "perhaps", "sideways", "sometimes",
    "thus", "towards", "unless", "upwards", "yes",
})

_YOU_VERB_RE = re.compile(r"(?<!\w)([Yy]ou)(\s+)([A-Za-z’']+)")

# Stems that take -es rather than a bare -s ("catch/catches", "push/pushes",
# "fix/fixes", "go/goes", "pass/passes"); everything else drops a single -s.
# "ss" not "s": a stem ending in ONE s is rare ("bus"), while "loses",
# "raises", "closes" are common and keep their stem-final e.
_ES_STEM_ENDINGS = ("ss", "x", "z", "ch", "sh", "o")


def _base_from_third_person_s(word):
    """Undo third-person-singular -s/-es/-ies on a regular present verb, or
    return None when the word is not one."""
    low = word.lower()
    if (low in _NON_VERB_S_WORDS or len(low) <= 3 or not low.endswith("s")
            or low.endswith(("ss", "us", "is", "as", "'s", "’s"))):
        return None
    if low.endswith("ies") and len(low) > 4:      # carries -> carry
        return word[:-3] + "y"
    if low.endswith("es") and low[:-2].endswith(_ES_STEM_ENDINGS):
        return word[:-2]                          # catches -> catch
    return word[:-1]                              # steps -> step


def _fix_you_agreement(text):
    """Re-inflect the verb after a "you" that replaced a third-person subject.

    Handles the irregular copulas/auxiliaries by table and regular present-
    tense verbs by undoing the third-person-singular -s. "you is/was/has/does
    <x>" and "you <verb>s" are never grammatical English, so this is safe to
    run over prose that already contained a legitimate "you".
    """
    def _sub(m):
        you, gap, word = m.group(1), m.group(2), m.group(3)
        fixed = _YOU_AGREEMENT.get(word.lower())
        if fixed is None:
            fixed = _base_from_third_person_s(word)
        if fixed is None:
            return m.group(0)
        if word[:1].isupper():
            fixed = fixed[:1].upper() + fixed[1:]
        return f"{you}{gap}{fixed}"

    return _YOU_VERB_RE.sub(_sub, str(text or ""))


def _self_pronoun_sub(m):
    """Replacement callback for _self_second_person: possessive -> your,
    anything else -> you, capitalized when it opens a sentence."""
    word = "your" if m.group(1) else "you"
    before = m.string[:m.start()].rstrip()
    if not before or before[-1] in ".!?\n":
        word = word.capitalize()
    return word


def _observable_predicate(display, surface):
    """Compose one clean delivered sentence from an actor `display` label and an
    intent-free `observable` surface, without the double-subject run-ons the
    alpha3.1.2 full-sentence observable produced ('Dr. Moon Dr. Moon tilts...',
    'Dr. Moon The flashlight beam moves...'). Strip a leading occurrence of the
    actor's own name tokens (so an actor-led surface becomes a predicate); then
    if the surface still opens with its OWN capitalized subject (an independent
    clause like 'The flashlight beam moves...'), keep it verbatim as its own
    sentence -- prepending display would double the subject; otherwise it is a
    predicate and takes the display prefix."""
    surface = str(surface or "").strip()
    if not surface:
        return None
    disp_tokens = _identity_token_set(display)
    words = surface.split()
    # Peel leading actor-name tokens / a leading pronoun off the surface.
    while words and (words[0].strip(".,;:'").casefold() in disp_tokens
                     or words[0].casefold() in ("she", "he", "they", "it")):
        words = words[1:]
    stripped = " ".join(words).strip()
    if not stripped:
        return f"{display}."
    first = stripped.split(maxsplit=1)[0]
    # Independent subject clause (starts with a capitalized non-actor word that
    # isn't a normal sentence-initial cap): render as its own sentence.
    independent = first[:1].isupper() and first.casefold() not in disp_tokens
    if independent:
        return stripped if stripped.endswith((".", "!", "?")) else stripped + "."
    body = stripped[0].lower() + stripped[1:]
    return f"{display} {body}."


def _action_already_rendered(view, display, surface):
    """True when the view already narrates this action (so the deterministic
    backstop should stay silent). Upgrades the old exact-substring test to
    content-token overlap, which catches the LLM's paraphrase of the same
    beat. Biases toward silence: since alpha3.1.2 duplication is the common,
    player-visible failure and a missed injection the rare one."""
    surf = set(_content_tokens(surface))
    if not surf:
        return False
    view_text = str(view or "")
    disp_tokens = _identity_token_set(display)
    for sent in re.split(r"(?<=[.!?])\s+", view_text):
        raw = set(re.split(r"[^\w]+", sent.lower()))
        stoks = set(_content_tokens(sent))
        overlap = surf & stoks
        if not overlap:
            continue
        if len(overlap) / len(surf) >= 0.6:
            return True
        if (disp_tokens & raw) and len(overlap) >= 2:
            return True
    # WHOLE-VIEW pass. The per-sentence loop above misses two common shapes:
    # the perception LLM spreads ONE beat over several sentences ("Dr. Moon is
    # right in front of you, having crossed quickly. Her arm is under yours,
    # bracing you against the wall."), and the sentence splitter itself breaks
    # on the abbreviation in a name like "Dr. Moon" -- which strands the actor
    # token in one fragment and the action tokens in the next, disarming the
    # disp_tokens rule exactly where it was needed. Live consequence (chat 27
    # turn 54): the beat was appended a SECOND time at the end of the view,
    # AFTER the dialogue, so the narrator rendered Dr. Moon crossing to brace
    # the player, then speaking, then crossing to brace them again.
    #
    # Requires the view to NAME this actor and to share strictly more
    # distinctive tokens than the per-sentence rule asks for: the whole view
    # is a far larger surface for coincidental matches than one sentence.
    raw_all = set(re.split(r"[^\w]+", view_text.lower()))
    whole_overlap = surf & set(_content_tokens(view_text))
    if (disp_tokens & raw_all) and len(whole_overlap) >= 3:
        return True
    return False


def _inject_action(view, display, attempt, can_see, event_id=None, delivered=None,
                   self_forms=None):
    """Append one actor's observable action to a perceiver's view.

    `self_forms` are the RECEIVING perceiver's own name/alias forms. They are
    rewritten to second person BEFORE the duplicate check, so the check scores
    the same person the LLM's own prose used ("...beside your shoulder") rather
    than the acting agent's third-person surface -- which is why the duplicate
    slipped through as well as the person mismatch. See _self_second_person.
    """
    if not attempt or not can_see:
        return view
    if delivered is not None and event_id:
        if event_id in delivered:
            return view
        delivered.add(event_id)
    if self_forms:
        attempt = _self_second_person(attempt, self_forms)
    if _action_already_rendered(view, display, attempt):
        return view
    sentence = _observable_predicate(display, attempt)
    if not sentence:
        return view
    return _append_once(view, sentence, marker=sentence)

# `appearance_of` builds a STRUCTURED summary for payload fields -- labelled
# segments joined by semicolons -- which is right for a field a model reads and
# wrong for prose. It was being pasted verbatim into perception views, so every
# view of every turn in a 47-turn chat read:
#
#     "You see A tall figure in a grey travelling coat, hood raised.;
#      clothing state: soaked through, ..."
#
# -- a capital mid-sentence, a full stop before a semicolon, and the field
# labels themselves narrated. Normalizing at the PASTE POINT rather than at the
# five construction sites keeps one mechanism and leaves the payload form,
# which is correct, alone.
_APPEARANCE_LABELS = (
    ("; wearing:", ", wearing"),
    ("; clothing state:", ","),
    ("; currently:", ","),
)


def _appearance_as_prose(appearance):
    """A structured appearance summary rendered as something a view can hold."""
    text = str(appearance or "").strip()
    if not text:
        return ""
    for label, replacement in _APPEARANCE_LABELS:
        text = text.replace(label, replacement)
    # The base appearance is authored as its own sentence; its terminal stop
    # and leading capital both fight the clause it is now part of.
    text = re.sub(r"\.\s*(?=,)", "", text)
    text = text.rstrip(" .")
    if text[:1].isupper() and re.match(r"^(a|an|the)\b", text, re.I):
        text = text[:1].lower() + text[1:]
    return re.sub(r"\s{2,}", " ", text).strip(" ,")


def _inject_visible_actor(
    view,
    *,
    display,
    appearance,
    relation,
):
    if not has_visual(relation):
        return view

    text = str(view or "").strip()

    contradiction_patterns = (
        r"\bno visual sign of the speaker is visible\b",
        r"\bno clear figure visible\b",
        r"\bthe speaker is not visible\b",
        r"\bcannot see (?:them|the speaker|anyone)\b",
    )

    for pattern in contradiction_patterns:
        text = re.sub(
            pattern,
            "",
            text,
            flags=re.I,
        )

    text = re.sub(r"\s{2,}", " ", text).strip()

    if appearance:
        prose = _appearance_as_prose(appearance)
        # The perception model may already have rendered the same visible
        # body in natural prose. Exact-marker dedupe cannot recognize a
        # paraphrase, which produced a second mechanical "You see ..." tail
        # on the live chat-38 view. Use the same conservative content-overlap
        # test as action injection before adding the deterministic floor.
        if prose and _action_already_rendered(text, display, prose):
            return text
        return _append_once(
            text,
            f"You see {prose}.",
            # Marker stays the RAW form: it is what a previous injection would
            # have left behind, and dedupe must catch those too.
            marker=prose or appearance,
        )

    return _append_once(
        text,
        f"You see {display}.",
        marker=display,
    )

def _normalise_views(raw_views, perceivers):
    if not isinstance(raw_views, dict):
        raw_views = {}
    # Casefolded map of the literal perceiver ids themselves ("player",
    # "extra:<id>", numeric ids) onto their canonical spelling -- a model
    # returning "Player" or "Extra:12" must fold onto the exact key every
    # consumer reads (views.get("player") etc.) instead of being dropped.
    id_by_fold = {str(p["id"]).casefold(): str(p["id"]) for p in perceivers}
    name_to_id = {}
    for p in perceivers:
        name_to_id[p["name"]] = str(p["id"])
        name_to_id[p["name"].lower()] = str(p["id"])
    clean = {}
    for k, v in raw_views.items():
        sk = str(k).strip()
        if sk.lower() == "player" and "player" not in id_by_fold:
            continue
        canonical_id = id_by_fold.get(sk.casefold())
        if canonical_id is not None:
            sk = canonical_id
        elif not sk.isdigit():
            sk = name_to_id.get(sk) or name_to_id.get(sk.lower()) or sk
        if isinstance(v, str):
            v = v.strip()
            if not v:
                v = None
        clean[sk] = v
    return clean

def _compose_residue_view(level, *, targeted=False, loud_event=False, pain=False):
    """The content-free perception RESIDUE for a non-awake mind (asleep /
    sedated / unconscious). An unconscious mind integrates no channel into
    scene, identity, or words -- so this NEVER carries speech content, a name, a
    visual scene, or a spatial fact. It delivers only interoception (pain, being
    moved) and the direction-less trace of the strongest stimuli (a loud event
    as a wordless intrusion). Deterministic and template-built: the perception
    LLM is never asked for a non-awake view (it would leak with the full payload
    in hand), so this IS the whole output. The fragments become, verbatim, that
    mind's fragmentary memory of the beat (commit mints episodic memory from the
    view), which is exactly the vague recovered impression waking should give."""
    lead = {
        "unconscious": "Darkness.",
        "sedated": "A thick, floating dark.",
        "asleep": "You are under, below waking.",
    }.get(level, "Darkness.")
    frag = []
    if pain:
        frag.append("a dull pain, far off, in a body you can't quite feel")
    if targeted:
        frag.append("something shifts you; the world tilts without a direction")
    if loud_event:
        frag.append("a sound, huge and wordless, reaches down and is gone")
    if not frag:
        closing = {"unconscious": " Nothing reaches you.",
                   "sedated": " Nothing holds shape.",
                   "asleep": ""}.get(level, "")
        return (lead + closing).strip()
    body = "; ".join(frag[:2])
    return f"{lead} {body[0].upper()}{body[1:]}."


def _ensure_environment(view, perceiver, display, rel, vis, action_desc):
    if view:
        return view
    parts = [f"You are in {perceiver.get('room_name')}."]
    if perceiver.get("room_notes"):
        parts.append(perceiver["room_notes"])
    # `same_room` is true for a body sealed inside something standing in the
    # room -- a carried body's position derives to its carrier's. Announcing
    # it as "here with you" and pasting its observable is the same bypass the
    # injection sites had; `concealed` is absent (falsy) for every rel that
    # never went through containment, so open scenes are unchanged.
    if rel.get("same_room") and not rel.get("concealed"):
        parts.append(f"{display} is here with you.")
        if action_desc:
            # action_desc is now an intent-free `observable` surface (predicate
            # or independent clause); compose it cleanly rather than gluing it
            # after "attempts to" (which double-verbs "attempts to tilts...").
            sentence = _observable_predicate(display, action_desc)
            if sentence:
                parts.append(sentence)
    elif vis:
        parts.append(f"You can see {display} nearby.")
    return " ".join(parts)

def _fallback_perception_views(perceivers, dlog, resolved_event=None, known=None):
    views = {}
    for p in perceivers:
        pid = str(p["id"])
        p_room = p.get("room")
        parts = []
        rname = p.get("room_name")
        rnotes = p.get("room_notes")
        if rname and rname != "None":
            parts.append(f"You are in {rname}.")
        if rnotes:
            parts.append(rnotes)
        for d in dlog:
            spk_room = d.get("speaker_room")
            if spk_room and p_room and spk_room == p_room:
                speaker = d.get("speaker", "?")
                # Same recognition gate as the main injection paths: a
                # speaker this perceiver has never been introduced to must
                # not be named by the no-LLM fallback either (the quote
                # itself is legitimately heard and stays verbatim).
                if known is not None and speaker != p.get("name") \
                        and speaker not in (known.get(p.get("name")) or []):
                    speaker = _unknown_actor_label(speaker)
                parts.append(f'{speaker} says: {d["exact_quote"]}')
        views[pid] = " ".join(parts) if parts else None
    return views

# A speech verb left dangling by the echo strip ("you say.", "I ask,") is healed
# to "<verb> it." The lookahead is SENTENCE-end only ([.!?] or end of string):
# a verb followed by a comma that CONTINUES the sentence ("he says, quiet and
# gentle, 'Ellie'") is a normal attribution around a quote that survived, not a
# dangling verb -- healing it produced "he says it., quiet and gentle," in live
# NPC dialogue whenever the same beat also stripped a player echo (v4).
_DANGLING_SPEECH_VERB_RE = re.compile(
    r"\b(say|says|said|ask|asks|asked|tell|tells|told|call|calls|called|"
    r"shout|shouts|shouted|murmur|murmurs|murmured|whisper|whispers|whispered|"
    r"reply|replies|replied|answer|answers|answered)\b,?\s*(?=[.!?]|$)",
    re.IGNORECASE,
)

# A quote can also be introduced by an attributive CLAUSE ending in a colon
# ("...and when I speak again it's quieter, almost gentle:"). Stripping the
# player's echoed quote leaves the colon dangling against the next sentence
# (live: v3 t7 "...almost gentle: Vorne swallows once..."). Drop the orphaned
# lead-in back to the preceding clause/sentence boundary -- but only a clause
# that actually carries a speech cue, so a legitimate non-speech colon (a
# list, a ratio, a time) is never eaten. The colon match also consumes an
# orphaned period the strip may have left ("gentle: .").
_SPEECH_CUE = (
    r"say|says|said|speak|speaks|spoke|speaking|add|adds|added|ask|asks|asked|"
    r"tell|tells|told|reply|replies|replied|answer|answers|answered|voice|"
    r"voices|voiced|murmur|murmurs|murmured|whisper|whispers|whispered|"
    r"continue|continues|continued|offer|offers|offered"
)
# The lead-in TEXT is kept -- only the dangling colon (and any orphaned period
# the strip left) is converted to a full stop, so nothing legitimate can be
# eaten. Requiring a speech cue in the same clause keeps this off a real
# non-speech colon (a list, a ratio, a time). `[^.!?:]*` cannot cross a
# sentence boundary, so the cue and the colon are always in one clause.
_DANGLING_SPEECH_COLON_RE = re.compile(
    r"(\b(?:" + _SPEECH_CUE + r")\b[^.!?:]*):\s*\.?\s*(?=[A-Z]|$)",
    re.IGNORECASE,
)


def _heal_dangling_colon(m):
    return m.group(1) + ". "

def _protected_view_quotes(view, player_lines=None):
    """Quoted spans in a perceiver's view that belong to a NON-player speaker
    -- the exact lines DIALOGUE FIDELITY requires the narrator to keep
    verbatim. Excludes the player's own declared lines (those are the ones
    the echo strip is meant to remove). Fed to _strip_player_echo so it never
    corrupts a legitimately-quoted NPC line while stripping a player echo."""
    excluded = {
        re.sub(r"\s+", " ", _quote_body(line).casefold())
        for line in (player_lines or [])
        if _quote_body(line)
    }
    quotes = []
    for match in re.finditer(r'["“]([^"“”]{1,})["”]', str(view or "")):
        body = _quote_body(match.group(1))
        if not body:
            continue
        if re.sub(r"\s+", " ", body.casefold()) in excluded:
            continue
        quotes.append(body)
    return quotes

def _strip_player_echo(prose, lines, protect_quotes=None):
    if not prose:
        return prose
    # DIALOGUE FIDELITY vs PLAYER ECHO: the echo strip removes the player's
    # OWN declared lines from prose, but it must never reach inside a span the
    # narrator legitimately quoted from a NON-player speaker (an NPC line the
    # fidelity check just required verbatim). When a player line coincides
    # with, or is a substring of, an NPC's quoted line, blind stripping would
    # corrupt that protected quote. Mask the NPC-attributed quoted spans out
    # of reach for the duration of the strip, then restore them intact.
    masks = []
    for quote in (protect_quotes or []):
        body = _quote_body(quote)
        if not body:
            continue
        forms = ['"%s"' % body, "“%s”" % body]
        if len(body) >= 8:
            forms.append(body)
        for form in forms:
            start = 0
            while True:
                pos = prose.find(form, start)
                if pos == -1:
                    break
                token = "\x00%d\x00" % len(masks)
                masks.append((token, form))
                prose = prose[:pos] + token + prose[pos + len(form):]
                start = pos + len(token)
    for speech in (lines or []):
        body = (speech or "").strip().strip('"' + "'" + "\u201c\u201d\u2018\u2019")
        if not body:
            continue
        # Quoted forms are delimited by quote marks, so stripping them is
        # safe at any length. The bare (unquoted) form is only stripped for
        # longer lines, since a short bare substring (e.g. "no") risks
        # corrupting unrelated words ("know", "not"). Without this split,
        # short player lines (e.g. "Stop!", "Wait!") were never stripped at
        # all and echoed verbatim in narrator prose.
        quoted_forms = ('"%s"' % body, "\u201c%s\u201d" % body)
        matched = any(q in prose for q in quoted_forms)
        if len(body) >= 8 and body in prose:
            matched = True
        if not matched:
            continue
        for quoted in quoted_forms:
            prose = prose.replace(quoted, "")
        if len(body) >= 8:
            prose = prose.replace(body, "")
        # Stripping the quote can leave a dangling speech verb ("you say,",
        # "I ask,", "Alex says.") with nothing after it -- the subject varies
        # with narration_person (first/second/third), so match on the verb
        # rather than assuming "you".
        prose = _DANGLING_SPEECH_VERB_RE.sub(lambda m: f"{m.group(1)} it.", prose)
        prose = _DANGLING_SPEECH_COLON_RE.sub(_heal_dangling_colon, prose)
    for token, form in masks:
        prose = prose.replace(token, form)
    prose = _collapse_empty_quote_debris(prose)
    return re.sub(r"\s{2,}", " ", prose).strip()


# An empty quote pair -- '' "" “” -- left where a stripped player line used to
# sit (Fable review, DW t12: "I can't hold her eyes. ''"). Collapse the orphan
# and heal the punctuation/space it leaves. Only a genuinely EMPTY pair is
# touched, so real quoted dialogue is never harmed.
_EMPTY_QUOTE_RE = re.compile(r"""\s*(?:''|""|“”|‘’|"\s*"|'\s*')\s*""")


def _collapse_empty_quote_debris(prose):
    if not prose:
        return prose
    out = _EMPTY_QUOTE_RE.sub(" ", prose)
    # A lead-in left dangling against the removed quote ("She said, .", "then, .")
    out = re.sub(r"[,:]\s*\.", ".", out)
    out = re.sub(r"\s+([.,!?;])", r"\1", out)
    return out

def _phrase_ngrams(text, n):
    """Lower-cased n-word phrases of `text`, punctuation-stripped."""
    words = re.findall(r"[a-z']+", str(text or "").lower())
    return [" ".join(words[i:i + n]) for i in range(len(words) - n + 1)]


# Content words whose repetition is a genuine tic; function-word runs ("in the
# middle of") are not. A phrase must carry at least one of these to be flagged.
_TIC_STOPWORDS = frozenset(
    "the a an and or but of to in on at by for with from as is are was were be "
    "been it its his her their my your our i he she they we you him them me "
    "that this these those there here then when once again still not no".split())


def _overused_phrases(recent_prose, current_prose="", n=3, min_hits=2, cap=12):
    """The narrator's own recurring set-dressing tics (Fable A4): short phrases
    that recur across recent turns' prose -- "the clock ticks", "thumps her tail
    once", "the fire settles". Fed back to the narrator as a ban list so it
    varies them, and used by the repetition check below.

    A phrase counts once per prose block it appears in (so a within-block
    repeat isn't inflated), must contain a content word, and must recur in at
    least `min_hits` blocks including the current draft when supplied.
    """
    blocks = [p for p in list(recent_prose or []) + [current_prose] if p]
    if len(blocks) < min_hits:
        return []
    counts = {}
    for block in blocks:
        for phrase in set(_phrase_ngrams(block, n)):
            words = phrase.split()
            if all(w in _TIC_STOPWORDS for w in words):
                continue
            counts[phrase] = counts.get(phrase, 0) + 1
    # Prefer the longest/most-specific phrases; drop a phrase fully contained
    # in a longer flagged one so "clock ticks" and "the clock ticks" don't both
    # list.
    hits = sorted((p for p, c in counts.items() if c >= min_hits),
                  key=len, reverse=True)
    kept = []
    for phrase in hits:
        if not any(phrase in longer for longer in kept):
            kept.append(phrase)
    return kept[:cap]


def _word_shingles(text, n=6):
    words = re.findall(r"[a-z0-9']+", str(text or "").lower())
    return {
        " ".join(words[i:i + n])
        for i in range(len(words) - n + 1)
    }

def _already_established_phrases(view, recent_prose, limit=12):
    """Deterministic overlap between THIS turn's raw view and the narrator's
    own recent prose. perception_act/perception_outcome re-describe the full
    room every turn by design (they're a stateless sensory filter with no
    memory of prior turns) -- but that means the narrator's job of "don't
    re-catalog what's unchanged" requires knowing what it already said. Doing
    that by having the model compare two blobs of prose itself is unreliable;
    this hands it a concrete, computed list instead.
    """
    view_shingles = _word_shingles(str(view or ""))
    if not view_shingles:
        return []
    hits = set()
    for prev in recent_prose or []:
        hits |= (view_shingles & _word_shingles(prev))
    return sorted(hits)[:limit]

# Within-view dedupe (W12): the same sentence rendered twice in ONE turn's
# view/prose ("Picard turns his head slightly toward Troi" appearing twice in
# a single beat). Splitting is a plain sentence-boundary regex; a quote whose
# body contains sentence punctuation mis-splits into fragments, but every such
# fragment carries a quote character and is therefore exempt from dropping
# (below), so mis-splits can only UNDER-dedupe, never eat real content.
_SPEECH_VERBS = (
    "say", "says", "said", "saying", "whisper", "whispers", "whispered",
    "whispering", "mutter", "mutters", "muttered", "muttering", "murmur",
    "murmurs", "murmured", "murmuring", "manage", "managed",
    "manages", "breathe", "breathes", "breathed", "gasp", "gasps", "gasped",
    "gasping", "croak", "croaks", "croaked", "rasp", "rasps", "rasped",
    "reply", "replies", "replied", "replying", "answer", "answers",
    "answered", "answering", "hiss", "hisses", "hissed",
    "stammer", "stammers", "stammered", "whimper", "whimpers", "whimpered",
    "choke", "chokes", "force", "forces", "add", "adds", "added", "plead",
    "pleads", "pleaded", "pleading", "beg", "begs", "begged", "begging",
    "cry", "cries", "call", "calls", "called", "get out", "let out",
    "shout", "shouts", "shouted", "shouting", "scream", "screams",
    "screamed", "screaming", "yell", "yells", "yelled", "yelling",
    "ask", "asks", "asked", "asking", "respond", "responds", "responded",
    "sob", "sobs", "sobbed", "sobbing", "snap", "snaps", "snapped",
    "growl", "growls", "growled", "blurt", "blurts", "blurted",
    "exclaim", "exclaims", "exclaimed", "repeat", "repeats", "repeated",
    "insist", "insists", "insisted", "demand", "demands", "demanded",
    "announce", "announces", "announced", "declare", "declares", "declared",
    "wail", "wails", "wailed", "moan", "moans", "moaned",
    "intone", "intones", "intoned", "utter", "utters", "uttered",
    "speak", "speaks", "spoke", "speaking", "tell", "tells", "told",
)
_SPEECH_VERB_RE = re.compile(
    r"\b(?:" + "|".join(re.escape(v) for v in _SPEECH_VERBS) + r")\b", re.I)
# Attribution cue for the dialogue-fidelity floor: a speech verb, or a bare
# voice noun ("A muffled voice: ..."). Deliberately excludes reading verbs
# (reads, is written/painted/carved, displays) so quoted ENVIRONMENTAL text --
# signage, labels, screens -- is never mistaken for dialogue.
_DIALOGUE_CUE_RE = re.compile(
    _SPEECH_VERB_RE.pattern + r"|\bvoices?\b", re.I)
_YOU_RE = re.compile(r"\byou\b|\byour\b", re.I)
_NPC_PRONOUN_RE = re.compile(r"\bshe\b|\bhe\b|\bthey\b|\bher\b|\bhim\b|\bhis\b", re.I)


def _scrub_invented_dialogue(view, spoken_bodies, *, cast_names=(), mode="all"):
    """DIALOGUE-FIDELITY FLOOR at the perception layer: drop any quoted line
    of a perceiver view that is presented as SPEECH but whose body is not in
    the set of lines actually spoken this beat (declared player/character
    speech + dialogue_log). The perception LLM sometimes invents a fresh
    utterance -- often a memory/backstory callback rendered as if freshly
    spoken (live t42: a fabricated player line about "trapped under the
    rubble" injected into Dr. Moon's view) -- which then propagates into
    other minds' character context and durable memory. No stage may author
    words a speaker did not say.

    Kept untouched:
    - any quote whose body matches a spoken line GENEROUSLY (case/whitespace
      normalized; substring either direction, so a distant perceiver's
      legitimate muffled FRAGMENT of a real line survives; an ellipsis-split
      quote survives when every fragment is verbatim from one spoken line);
    - environmental quoted text (mode="all"): signage, labels, screens --
      recognized by the ABSENCE of a speech-attribution cue around the quote
      ("reads"/"is painted" are not speech verbs);
    - quotes with no player attribution (mode="player": only a quote whose
      nearest speaker cue is 'you'/'your' is in scope -- the original
      player-view-only scrub semantics).

    Removal is clause surgery: the quote plus its immediate attribution
    clause (before it, and after it for a trailing '"...," she says.'),
    never the surrounding prose. Returns (scrubbed_view, dropped)."""
    if not view:
        return view, []
    legit = []
    for b in spoken_bodies:
        nb = re.sub(r"\s+", " ", (_quote_body(b) or "")).casefold().strip()
        if nb:
            legit.append(nb)

    def _matches_spoken(raw_body):
        body = re.sub(r"\s+", " ", (_quote_body(raw_body) or "")).casefold().strip()
        if not body or not re.search(r"\w", body):
            return True  # empty / pure punctuation: nothing was authored
        if any(body == L or body in L or L in body for L in legit):
            return True
        core = body.strip(" .…—–-")
        if core and any(core in L for L in legit):
            return True
        # Muffled/partial rendering: an ellipsis-chunked quote is legitimate
        # when EVERY chunk is a verbatim piece of some actually-spoken line.
        chunks = []
        for c in re.split(r"\.{2,}|…", body):
            c = c.strip(" ,;:—–-.!?")
            if c.startswith("something about "):
                c = c[len("something about "):]
            if len(c) >= 3:
                chunks.append(c)
        return bool(chunks) and all(any(c in L for L in legit) for c in chunks)

    name_re = re.compile(
        "|".join(r"\b" + re.escape(str(n).lower()) + r"\b" for n in cast_names if n),
        re.I) if cast_names else None

    # Quoted spans (a body may itself contain '...'/'!' -- so we cannot split
    # into sentences first; we work over the whole view). Clause boundaries are
    # sentence terminators OUTSIDE any quote, plus the END of each quoted span
    # (a new clause almost always begins after a quoted line).
    quote_spans = [(m.start(), m.end(), m.group(1))
                   for m in re.finditer(r'["“]([^"”]*)["”]', view)]
    boundaries = {0}
    inside = False
    for i, ch in enumerate(view):
        if ch in '"“”':
            inside = not inside
        elif ch in ".!?…" and not inside:
            boundaries.add(i + 1)
    for _s, qe, _b in quote_spans:
        boundaries.add(qe)
    boundaries = sorted(boundaries)
    quote_starts = [qs for qs, _qe, _b in quote_spans]

    def _clause_start(pos):
        b = 0
        for bp in boundaries:
            if bp <= pos:
                b = bp
            else:
                break
        while b < len(view) and view[b] in " \n\t":
            b += 1
        return b

    def _tail_stop(pos):
        # The attribution tail of a quote runs to the next sentence boundary,
        # but never INTO a following quote -- a legit quote after 'she says,
        # and X replies,' must survive the surgery.
        stop = len(view)
        for bp in boundaries:
            if bp > pos:
                stop = bp
                break
        for q2 in quote_starts:
            if pos < q2 < stop:
                stop = q2
                break
        return stop

    removals, dropped = [], []
    for qs, qe, raw_body in quote_spans:
        if _matches_spoken(raw_body):
            continue
        if mode == "player":
            # Original player-view semantics: only a quote whose NEAREST
            # speaker cue before it is the player ('you'/'your', closer than
            # any NPC pronoun/cast name) is in scope.
            prefix = view[:qs]
            you = max((mm.start() for mm in _YOU_RE.finditer(prefix)), default=-1)
            npc = max((mm.start() for mm in _NPC_PRONOUN_RE.finditer(prefix)), default=-1)
            if name_re:
                npc = max([npc] + [mm.start() for mm in name_re.finditer(prefix)])
            if you < 0 or you <= npc:
                continue
            start, end = _clause_start(qs), qe
        else:
            cstart = _clause_start(qs)
            pre_attr = bool(_DIALOGUE_CUE_RE.search(view[cstart:qs]))
            tstop = _tail_stop(qe)
            tail = view[qe:tstop]
            tail_lead = tail.lstrip()
            # A trailing attribution ('"...," she says.') continues the same
            # sentence, so it starts lowercase or with a dash -- an uppercase
            # tail is a NEW sentence and out of scope.
            tail_attr = bool(tail_lead) and (
                tail_lead[0].islower() or tail_lead[0] in ",—–-") \
                and bool(_DIALOGUE_CUE_RE.search(tail))
            if not pre_attr and not tail_attr:
                continue  # no speech attribution: environmental text (signage)
            start = cstart if pre_attr else qs
            end = tstop if tail_attr else qe
        while end < len(view) and view[end] in " \n\t":
            end += 1
        removals.append((start, end))
        dropped.append(view[start:qe].strip())

    if not removals:
        return view, []
    out = view
    for start, end in sorted(removals, reverse=True):
        out = out[:start] + out[end:]
    return re.sub(r"\s{2,}", " ", out).strip(), dropped


def _scrub_undeclared_player_speech(view, declared_bodies, protected_bodies=(),
                                    cast_names=()):
    """PLAYER-SPEECH AUTHORITY at the perception layer: drop any sentence of the
    PLAYER's own view that quotes a player-attributed line the player did NOT
    declare this beat (live: the turn-39 fragment "The same..." resurfaced as
    "Same... the one who... did this... before." in a later turn's view).
    Thin wrapper over _scrub_invented_dialogue's player mode; NPC lines the
    player legitimately heard ride in as protected_bodies. Returns
    (scrubbed_view, dropped_sentences)."""
    return _scrub_invented_dialogue(
        view, list(declared_bodies) + list(protected_bodies),
        cast_names=cast_names, mode="player")


_VIEW_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])(\s+)")
# Double-quote characters only: curly/straight single quotes double as
# apostrophes in ordinary prose and cannot mark dialogue reliably.
_VIEW_QUOTE_CHARS = ('"', "“", "”")
_VIEW_DEDUPE_MIN_WORDS = 5

_VIEW_QUOTED_SPAN_RE = re.compile(
    r'["“][^"“”]*["”]'          # "..." / “...”
    r"|(?<!\w)'[^']{3,}?'(?!\w)"  # '...' , not an apostrophe
)
_VIEW_MASK = "\x00Q%d\x00"


def _mask_quoted_spans(text):
    """Replace each quoted span with a single opaque token.

    The token carries no whitespace and no terminal punctuation, so a sentence
    splitter cannot cut a quotation into pieces -- which is the whole point.
    Returns (masked_text, spans) for `_unmask_quoted_spans`.
    """
    spans = []

    def _swap(match):
        spans.append(match.group(0))
        return _VIEW_MASK % (len(spans) - 1)

    return _VIEW_QUOTED_SPAN_RE.sub(_swap, text), spans


def _unmask_quoted_spans(text, spans):
    for i, span in enumerate(spans):
        text = text.replace(_VIEW_MASK % i, span)
    return text


def _dedupe_view_sentences(text):
    """Drop a sentence that repeats an EARLIER sentence of the same text
    verbatim (case/whitespace/terminal-punctuation-insensitive), keeping the
    first occurrence. Deterministic and deliberately conservative:

    - sentences containing quoted dialogue are never dropped -- quotes must
      survive verbatim (dialogue fidelity), and a character repeating a line
      on purpose is legitimate;
    - short sentences (< 5 words) are never dropped -- intentional beats
      ("No. No.") and terse stage directions must survive;
    - only exact normalized repeats go; paraphrase is out of scope.

    QUOTED SPANS ARE MASKED BEFORE SPLITTING, because that first rule was
    defeated by the splitter for years. The check is per-SENTENCE ("does this
    fragment contain a quote character"), and a spoken line containing its own
    terminal punctuation is cut into several fragments -- only the two on the
    ends keep a quote mark, and every fragment between them is judged naked and
    dropped if it echoes anything earlier in the view.

    Live (chat 58, t30). The player answered a direct question with "Seven? I
    think? There might have been more... they began to spread out..." -- four
    terminators, so four fragments. This runs LAST in `perception_act`, after
    the deterministic delivery, and ate the interior of the quotation:

        Hinami says: "Seven? I think? There might have been more... they began
                      to spread out..."
        ->  Hinami says: "Seven? I think? they began to spread out..."

    The character then answered as though the line had never been said, asking
    the question that had just been answered. Perception_act is the view a
    character DECIDES from, so unlike a narrator-side drop this is invisible in
    play -- it surfaces only as a non-sequitur that reads like a model failure.

    Returns the text unchanged (same object) when nothing repeats.
    """
    text = str(text or "")
    if not text.strip():
        return text
    masked, spans = _mask_quoted_spans(text)
    pieces = _VIEW_SENTENCE_SPLIT_RE.split(masked)
    seen = set()
    kept = []
    dropped = False
    # pieces alternates [sentence, separator, sentence, separator, ...];
    # each sentence is kept/dropped together with ITS OWN trailing
    # separator, so removing a duplicate leaves the surrounding
    # whitespace/paragraph structure intact.
    for i in range(0, len(pieces), 2):
        sent = pieces[i]
        sep = pieces[i + 1] if i + 1 < len(pieces) else ""
        key = re.sub(r"\s+", " ", sent).strip().strip(".!?…").casefold()
        droppable = (
            len(key.split()) >= _VIEW_DEDUPE_MIN_WORDS
            # A masked span means this sentence carries a quotation. The raw
            # check stays alongside it for an UNTERMINATED quote, which the
            # span regex cannot match and which must still be protected.
            and "\x00" not in sent
            and not any(qc in sent for qc in _VIEW_QUOTE_CHARS)
        )
        if droppable:
            if key in seen:
                dropped = True
                continue
            seen.add(key)
        kept.append(sent)
        kept.append(sep)
    if not dropped:
        return text
    return _unmask_quoted_spans("".join(kept).rstrip(), spans)

_NARRATION_QUOTE_RE = re.compile(r'["“][^"“”]*["”]')
#: A doubled opening mark makes the paired pattern match an EMPTY span and
#: desynchronise every quote after it on the line -- observed live. Folded to
#: one mark before pairing rather than special-cased afterwards.
_NARRATION_DOUBLED_QUOTE_RE = re.compile(r'["“]{2,}')
#: An opening mark with no partner, running to end of line. Applied only after
#: the paired passes, so it can only ever catch what is genuinely unclosed.
_NARRATION_DANGLING_QUOTE_RE = re.compile(r'["“][^"“”]*$', re.MULTILINE)
_NARRATION_SQUOTE_RE = re.compile(r"(?<!\w)'[^']{3,}?'(?!\w)")
_FIRST_PERSON_RE = re.compile(
    r"\b(i|i'm|i've|i'll|i'd|me|my|mine|myself"
    r"|we|we're|we've|we'll|we'd|us|our|ours|ourselves)\b", re.IGNORECASE)
_SECOND_PERSON_RE = re.compile(
    r"\b(you|you're|you've|you'll|you'd|your|yours|yourself)\b", re.IGNORECASE)
# Third-person player evidence comes almost entirely from the player's NAME
# used as a proper noun; pronouns are inherently ambiguous ("her"/"him"/
# "them" nearly always refer to OTHER people in the scene). We therefore
# count only subjective-form player pronouns and never object/possessive
# ones -- and even those only survive as a tiebreak once hysteresis in
# _resolve_narration_person guards against a lone token flipping the whole
# campaign's established person.
_THIRD_SUBJECT_PRONOUNS = frozenset({"he", "she", "they"})

def _narration_person_counts(raw_input, player_name=None, player_pronouns=None):
    """Weighted first/second/third-person evidence from the player's own
    phrasing this turn, after stripping quoted dialogue (a "you" inside a
    spoken line addresses another character, not the player's narrating
    voice). Precision fixes over a naive word count:

    - Player-name parts are matched CASE-SENSITIVELY as proper nouns, so a
      character named "Will"/"Mark"/"Grace"/"Rose" no longer collects
      spurious third-person hits from the ordinary words "will"/"mark"/etc.
    - Only subjective-form player pronouns (he/she/they) are counted, and
      each distinct pronoun string is counted once -- so an object/possessive
      pronoun referring to someone else ("I gave her the key") and duplicate
      dict values (obj == poss == "her") no longer masquerade as the player
      being narrated in third person.
    """
    narrative = _NARRATION_DOUBLED_QUOTE_RE.sub('"', str(raw_input or ""))
    narrative = _NARRATION_QUOTE_RE.sub(" ", narrative)
    narrative = _NARRATION_SQUOTE_RE.sub(" ", narrative)
    # Whatever quote mark is left opened dialogue that never closed, so the
    # rest of the line is dialogue too. Folded here rather than guarded at the
    # call sites, because a guard that must be remembered will be forgotten and
    # this one was: the paired pattern needs a closing mark, so an unterminated
    # quote let every "I" and "my" inside the speech vote on how the NARRATION
    # should read. Rare and decisive -- 11 of 2163 live player turns change
    # verdict, and one of them latched a whole story into first person.
    narrative = _NARRATION_DANGLING_QUOTE_RE.sub(" ", narrative)
    counts = {
        "first": len(_FIRST_PERSON_RE.findall(narrative)),
        "second": len(_SECOND_PERSON_RE.findall(narrative)),
        "third": 0,
    }
    for part in re.findall(r"[A-Za-z']+", str(player_name or "")):
        # Case-sensitive, and only for parts written as a proper noun; a
        # lowercase name can't be told apart from the common word it collides
        # with, so we decline to guess and let the fallback hold.
        if len(part) >= 3 and part[:1].isupper():
            counts["third"] += len(re.findall(rf"\b{re.escape(part)}\b", narrative))
    seen_pronouns = set()
    for pron in (player_pronouns or {}).values():
        pron = str(pron or "").strip().lower()
        if pron in _THIRD_SUBJECT_PRONOUNS and pron not in seen_pronouns:
            seen_pronouns.add(pron)
            counts["third"] += len(re.findall(rf"\b{re.escape(pron)}\b", narrative, re.IGNORECASE))
    return counts

def _detect_narration_person(raw_input, player_name=None, player_pronouns=None):
    """Guess which grammatical person the PLAYER used to phrase their own
    input this turn -- 'first' ("I open the door"), 'second' ("You open the
    door"), 'third' ("Alex opens the door") -- so the narrator can match it
    instead of always defaulting to 'you'. Whichever person has strictly more
    evidence (see _narration_person_counts) than every other wins. Ties or
    zero matches (e.g. a turn that's pure dialogue with no narrative frame)
    return None -- ambiguous, caller should fall back to whatever was already
    established.
    """
    counts = _narration_person_counts(raw_input, player_name, player_pronouns)
    best = max(counts, key=counts.get)
    if counts[best] == 0:
        return None
    others = [v for k, v in counts.items() if k != best]
    if others and counts[best] <= max(others):
        return None
    return best

# Third-person paradigms screened by _check_pronoun_fidelity. Only these three
# closed sets are checked: a character whose declared pronouns fall outside the
# table (neopronouns, mixed sets like she/them) is skipped entirely rather than
# guessed at -- the check exists to catch UNAMBIGUOUS flips, so anything it
# can't be certain about is not its business.
_PRONOUN_GROUPS = {
    "he": ("he", "him", "his", "himself"),
    "she": ("she", "her", "hers", "herself"),
    "they": ("they", "them", "their", "theirs", "themselves", "themself"),
}
_PRONOUN_TO_GROUP = {w: g for g, ws in _PRONOUN_GROUPS.items() for w in ws}

# Splits a sentence into clauses. A pronoun is only scored against a name in
# the SAME clause, which is what keeps "Vorne glanced at the ensign; her hands
# shook" (referent is the ensign, not Vorne) out of the check.
_CLAUSE_SPLIT = re.compile(
    r"[,;:()\[\]—–]|\s+(?:and|but|while|as|when|then|though|although"
    r"|so|yet|because|before|after|until|which|who|whose|that)\s+",
    re.I,
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Names that are also ordinary capitalized English words. A cast member called
# one of these can't be told apart from the common word, so we decline to score
# their clauses rather than burn a rewrite on "Will you hand him the padd".
_AMBIGUOUS_NAME_WORDS = {
    "will", "may", "art", "grace", "hope", "rose", "mark", "bill", "dawn",
    "sky", "rain", "storm", "ray", "faith", "joy", "sun", "star",
}


def _pronoun_group(pronouns):
    """The closed paradigm a declared pronoun set belongs to, or None when the
    declared forms are absent, unknown, or disagree with each other."""
    if not isinstance(pronouns, dict):
        return None
    groups = set()
    for key in ("subject", "object", "possessive"):
        word = str(pronouns.get(key) or "").strip().lower()
        if not word:
            continue
        group = _PRONOUN_TO_GROUP.get(word)
        if group is None:
            return None
        groups.add(group)
    return groups.pop() if len(groups) == 1 else None


def _check_pronoun_fidelity(prose, cast_pronouns):
    """Third-person pronoun flips the narrator prose commits against a cast
    member's canonical pronouns (W6).

    The PRONOUN CONSISTENCY prompt rule reduces but does not enforce this --
    a he/him character still picked up a "her" in live play. Deliberately
    narrow: a clause must OPEN with exactly one known cast name and then use a
    pronoun from a different paradigm, so the named subject is the only
    possible referent. Anything looser (a second name in the clause, a bare
    pronoun in a following sentence, an unnamed role noun) is left alone --
    a false positive costs a needless full narrator rewrite.
    """
    if not prose or not isinstance(cast_pronouns, dict):
        return []

    # name token -> (canonical name, group). Good prose drops to a surname or
    # first name alone after the first mention, so each word of a multi-word
    # name is a referent in its own right. A token two cast members share is
    # dropped: it no longer identifies one of them.
    token_owner = {}
    for name, pronouns in cast_pronouns.items():
        group = _pronoun_group(pronouns)
        canonical = str(name or "").strip()
        if not group or not canonical:
            continue
        for token in re.findall(r"[A-Za-z']+", canonical):
            if len(token) < 3 or not token[:1].isupper():
                continue
            if token.lower() in _AMBIGUOUS_NAME_WORDS:
                continue
            if token in token_owner and token_owner[token][0] != canonical:
                token_owner[token] = None
            elif token not in token_owner:
                token_owner[token] = (canonical, group)
    token_owner = {t: v for t, v in token_owner.items() if v}
    if not token_owner:
        return []

    # A pronoun inside quoted dialogue belongs to the speaker talking about
    # whoever they mean -- often someone the clause never names -- so it can't
    # be scored against the clause's named subject.
    scan = re.sub(r'"[^"]*"|“[^“”]*”', " ", prose)

    warnings = []
    flagged = set()
    for sentence in _SENTENCE_SPLIT.split(scan):
        for clause in _CLAUSE_SPLIT.split(sentence):
            words = re.findall(r"[A-Za-z']+", clause)
            if len(words) < 2:
                continue
            present = {token_owner[w] for w in words if w in token_owner}
            if len(present) != 1:
                continue
            canonical, group = next(iter(present))
            # The name must OPEN the clause: only then is it unambiguously the
            # subject the following pronoun refers back to.
            head = next(i for i, w in enumerate(words) if w in token_owner)
            if head > 1:
                continue
            for word in words[head + 1:]:
                other = _PRONOUN_TO_GROUP.get(word.lower())
                # A stray "they" is routinely a group ("Vorne watched them
                # scatter"), so only a GENDERED singular counts as a flip.
                if not other or other == group or other == "they":
                    continue
                key = (canonical, word.lower())
                if key in flagged:
                    break
                flagged.add(key)
                expected = "/".join(_PRONOUN_GROUPS[group][:3])
                warnings.append(
                    f"Pronoun mismatch for '{canonical}' (canonical {expected}): "
                    f"prose renders '{word}'"
                )
                break
    return warnings


def _check_player_person(prose, player_name, narration_person, player_aliases=None):
    """Deterministic backstop for the narrator's PERSON DISCIPLINE rule.

    When narration_person is 'second' or 'first', the player character is
    'you'/'I' -- naming them is, in the prompt's own words, a hard error. The
    rule was prompt-only, so a player_view that named the player (see
    _self_second_person for how the engine itself used to do that) produced
    prose mixing persons for one character with nothing to catch it, and the
    competing PROPER NOUN FIDELITY instruction actively pushed the model to
    copy the name through.

    Name-based only, and outside quoted spans: a character ADDRESSING the
    player by name aloud is legitimate dialogue that must survive verbatim,
    and a third-person descriptor ('the traveller') cannot be distinguished
    from a reference to someone else without resolving it -- so this scores
    the one signal that is unambiguous.
    """
    person = str(narration_person or "").strip().lower()
    if person not in ("second", "first"):
        return []
    text = str(prose or "")
    if not text:
        return []
    segments = _QUOTED_SPAN_RE.split(text)
    hits = []
    for form in [player_name, *(player_aliases or [])]:
        form = str(form or "").strip()
        if not form:
            continue
        flags = 0 if form.casefold() in _COMMON_WORD_NAMES else re.I
        pattern = re.compile(
            r"(?<!\w)" + re.escape(form) + r"(?:['’]s)?(?!\w)", flags)
        for i in range(0, len(segments), 2):  # even indices = unquoted prose
            if pattern.search(segments[i]):
                hits.append(form)
                break
    if not hits:
        return []
    pronoun = "you/your" if person == "second" else "I/me/my"
    return [
        "Player named in third person: narration_person is "
        f"'{person}', so the player character is {pronoun} and must never be "
        f"named in the prose -- found {', '.join(sorted(set(hits)))} outside "
        "quoted dialogue. Rewrite those references in the correct person, "
        "keeping every quoted line verbatim."
    ]


def _flexible_quote_re(body, flags=re.I):
    """Regex matching a quote body verbatim but whitespace-flexible (the
    narrator may re-wrap lines) and terminal-punctuation-tolerant (English
    convention turns a line's final period into a comma before a trailing
    attribution: '"...," she says')."""
    body = re.sub(r"\s+", " ", str(body or "").strip())
    body = body.rstrip(".,!?…;: ")
    if not body:
        return None
    return re.compile(
        r"(?<!\w)" + r"\s+".join(re.escape(w) for w in body.split(" "))
        + r"(?!\w)", flags)


def _check_event_order(prose, event_order):
    """F1 (A1 ordering half): a quoted line must not render before the event
    it answers. event_order is the pipeline's own numbered causal record of
    this beat (player declaration first, then reaction/interaction rounds in
    call order, then parallel character declarations, then background
    reactions -- see agents/narration.py's _ordered_beat_events).

    Deterministic and conservative: only events whose quote appears VERBATIM
    in the prose are scored (DIALOGUE FIDELITY guarantees NPC lines do; the
    player's own echo-stripped lines simply won't match and are skipped), and
    only a strict position inversion between two located quotes fires."""
    if not prose or not event_order:
        return []
    located = []
    for ev in event_order:
        if not isinstance(ev, dict) or ev.get("kind") != "speech":
            continue
        body = _quote_body(str(ev.get("quote") or ""))
        if len(body) < 4:
            continue
        pat = _flexible_quote_re(body)
        m = pat.search(prose) if pat else None
        if m:
            located.append((m.start(), ev))
    warnings = []
    for (pos_a, ev_a), (pos_b, ev_b) in zip(located, located[1:]):
        if pos_b < pos_a:
            warnings.append(
                "Dialogue rendered out of order: "
                f"{ev_b.get('actor')}'s line "
                f"\"{_quote_body(ev_b.get('quote'))[:60]}\" appears in the "
                "prose BEFORE the earlier event it follows/answers "
                f"({ev_a.get('actor')}: "
                f"\"{_quote_body(ev_a.get('quote'))[:60]}\"). Render events "
                "in event_order's numbered order."
            )
    return warnings


# _NARR_LOWERING and _NARR_RAISING are deliberately TIGHTER than a natural
# reading of "goes down" / "goes up": only verbs naming a deliberate directed
# movement, plus the unambiguous adverbs. Bare "up"/"down" ("heat scorching up
# your neck"), "rise"/"rose" (a chest rises; rose-gold motes) and "sink"/"drop"
# all appear constantly in ordinary prose, and every one of them would turn
# this into a false-positive generator that spends a rewrite on correct pages.
_NARR_LOWERING = re.compile(
    r"\b(?:lower(?:s|ed|ing)?|descend(?:s|ed|ing)?|downwards?)\b", re.I)
_NARR_RAISING = re.compile(
    r"\b(?:lift(?:s|ed|ing)?|rais(?:e|es|ed|ing)|hoist(?:s|ed|ing)?|"
    r"upwards?)\b", re.I)


def _check_action_direction(prose, event_order):
    """F5: an ACT listed in event_order, rendered in the wrong direction or
    dropped from the page entirely.

    An act is prose, not a quote, so unlike DIALOGUE FIDELITY there is no
    verbatim string to search for, and demanding a vocabulary match would
    force stilted wording ("the floor rising to meet him" is a correct
    rendering of a descent). Two findings, at different confidence:

    - REVERSED (enforceable): the act names exactly one direction and the
      prose names only the other. Judged without interpretation. From play:
      the Director resolved one character carrying another downward and the
      page rendered a lift.
    - MISSING (warning only): the act names a direction and the prose names
      neither. Legitimate prose can carry a descent with no directional verb
      at all, so this stays visible in fidelity_warnings for review rather
      than buying a rewrite it might not deserve.
    """
    if not prose or not event_order:
        return []
    p_low = bool(_NARR_LOWERING.search(prose))
    p_high = bool(_NARR_RAISING.search(prose))
    warnings = []
    for ev in event_order:
        if not isinstance(ev, dict) or ev.get("kind") != "action":
            continue
        act = str(ev.get("action") or "")
        a_low = bool(_NARR_LOWERING.search(act))
        a_high = bool(_NARR_RAISING.search(act))
        if a_low == a_high:
            continue                # the act says both directions, or neither
        said = "downward" if a_low else "upward"
        if (a_low and p_high and not p_low) or (a_high and p_low and not p_high):
            warnings.append(
                "Physical direction reversed: event_order has "
                f"{ev.get('actor')} moving {said} "
                f"(\"{act[:60]}\") but the prose renders the opposite. "
                "Render the act in the direction the record gives."
            )
        elif not p_low and not p_high:
            warnings.append(
                "Physical act from event_order may be missing in narrator "
                f"prose: {ev.get('actor')} moving {said} "
                f"(\"{act[:60]}\")."
            )
    return warnings


def _actor_reference_patterns(display):
    """Compiled patterns that count as a prose reference to one actor.

    A canonical proper name yields one case-sensitive pattern per usable name
    token (surname or first name alone is a normal reference). A descriptor
    label ('the unfamiliar woman', 'a woman in a gray uniform') yields one
    case-insensitive pattern for its content phrase minus the article."""
    display = str(display or "").strip()
    if not display:
        return []
    head = display.split()[0]
    if head.lower() in ("the", "a", "an") or not display[:1].isupper():
        phrase = re.sub(r"^(?:the|a|an)\s+", "", display, flags=re.I).strip()
        if len(phrase) < 4:
            return []
        return [re.compile(
            r"(?<!\w)" + r"\s+".join(re.escape(w) for w in phrase.split())
            + r"(?!\w)", re.I)]
    pats = []
    for tok in re.findall(r"[A-Za-z']+", display):
        if len(tok) < 3 or not tok[:1].isupper():
            continue
        if tok.lower() in _AMBIGUOUS_NAME_WORDS:
            continue
        pats.append(re.compile(
            r"(?<!\w)" + re.escape(tok) + r"(?:['’]s)?(?!\w)"))
    return pats


def _check_quote_attribution(prose, event_order, actor_pronouns=None):
    """F4: a quoted line's nearest preceding actor reference must resolve to
    its actual speaker (prose convention assigns an unattributed quote to the
    nearest prior actor -- Enterprise t4 rendered Vorne's line right after
    'The unfamiliar woman pulls her hands back...', silently reassigning a
    tracked mind's speech to an anonymous body).

    Conservative by design -- it only fires when it POSITIVELY finds a
    different speaker's reference closer than the true speaker's:
    - a trailing attribution naming the true speaker clears the quote;
    - no locatable actor reference at all -> no call;
    - an intervening third-person pronoun whose gender differs from the
      nearest candidate's declared pronouns -> ambiguous, no call."""
    events = [ev for ev in (event_order or [])
              if isinstance(ev, dict) and ev.get("kind") == "speech"
              and ev.get("quote") and ev.get("actor")]
    if not prose or not events:
        return []
    # Reference patterns per distinct actor; a pattern text shared by two
    # actors identifies neither and is dropped.
    actors = list(dict.fromkeys(str(ev["actor"]) for ev in events))
    raw = {a: _actor_reference_patterns(a) for a in actors}
    owner = {}
    for a, pats in raw.items():
        for p in pats:
            owner.setdefault(p.pattern, set()).add(a)
    pat_map = {
        a: [p for p in pats if len(owner.get(p.pattern, ())) == 1]
        for a, pats in raw.items()
    }

    def _group_of(actor):
        return _pronoun_group((actor_pronouns or {}).get(actor))

    warnings = []
    flagged = set()
    for ev in events:
        expected = str(ev["actor"])
        body = _quote_body(str(ev.get("quote") or ""))
        if len(body) < 4 or body in flagged:
            continue
        qpat = _flexible_quote_re(body)
        m = qpat.search(prose) if qpat else None
        if not m:
            continue
        start, end = m.span()
        # Trailing attribution: same sentence right after the quote.
        tail = prose[end:end + 120]
        stop = re.search(r"[.!?\n]", tail)
        tail_seg = tail[:stop.end()] if stop else tail
        if any(p.search(tail_seg) for p in pat_map.get(expected, [])):
            continue
        # Leading scan: nearest actor reference between the previous quote
        # (or paragraph start) and this quote. The current quote's own
        # OPENING delimiter sits just before `start` and must not truncate
        # the context it opens.
        prefix = prose[:start].rstrip()
        while prefix and prefix[-1] in '"“':
            prefix = prefix[:-1]
        cut = max(prefix.rfind("\n"),
                  max((prefix.rfind(qc) for qc in ('"', "”", "“")), default=-1))
        prefix = prefix[cut + 1:]
        best = None  # (pos, actor)
        for actor, pats in pat_map.items():
            for p in pats:
                for mm in p.finditer(prefix):
                    if best is None or mm.start() > best[0]:
                        best = (mm.start(), actor)
        if best is None or best[1] == expected:
            continue
        # A gendered pronoun AFTER the nearest (wrong) candidate that does not
        # match that candidate's own declared pronouns re-points the reader
        # elsewhere ("Vorne nods. She says...") -- ambiguous, decline to call.
        between = prefix[best[0]:]
        cand_group = _group_of(best[1])
        ambiguous = False
        for pm in re.finditer(r"\b(he|she|they)\b", between, re.I):
            pg = _PRONOUN_TO_GROUP.get(pm.group(1).lower())
            if cand_group and pg and pg != cand_group:
                ambiguous = True
                break
        if ambiguous:
            continue
        flagged.add(body)
        warnings.append(
            f"Quote attributed to wrong speaker: \"{body[:60]}\" is spoken "
            f"by {expected}, but the nearest preceding actor reference in "
            f"the prose is {best[1]} and no attribution names {expected}. "
            "Make the true speaker the quote's clear owner."
        )
    return warnings


# Perception/gesture verbs that make a following room mention a LOOK, not a
# placement ("glances at the corridor"); they must not trip the position check.
_LOOK_VERB_RE = re.compile(
    r"\b(?:glance[sd]?|glancing|look(?:s|ed|ing)?|stare[sd]?|staring|"
    r"gaze[sd]?|gazing|point(?:s|ed|ing)?|gesture[sd]?|gesturing|"
    r"nod(?:s|ded|ding)?|turn(?:s|ed|ing)?|face[sd]?|facing|"
    r"toward[s]?)\s*$", re.I)


def _check_position_fidelity(prose, position_facts, room_names):
    """F2: a character narrated at a room that differs from their committed
    position, with no movement event this beat, is a continuity break (DW t6:
    the Doctor mid-road; t7 renders him back in the TARDIS doorway).

    position_facts: [{name, room_id, moved}] -- display name, the room the
    scene commits them to THIS beat, and whether this beat's diff moved them.
    room_names: {room_id: display_name} for the rooms in play.

    Narrow: only a placement preposition (in/inside/within/into/at/back in)
    directly ahead of another room's display name, in a sentence whose nearest
    preceding actor reference is the unmoved character, fires."""
    if not prose or not position_facts:
        return []
    usable_rooms = {}
    for rid, rname in (room_names or {}).items():
        rname = str(rname or "").strip()
        if len(rname) < 4 or rname.lower() in ("room", "area", "here"):
            continue
        usable_rooms[rid] = rname
    warnings = []
    for fact in position_facts:
        if not isinstance(fact, dict) or fact.get("moved"):
            continue
        name = str(fact.get("name") or "").strip()
        own_room = fact.get("room_id")
        pats = _actor_reference_patterns(name)
        if not name or not own_room or not pats:
            continue
        own_name = str(usable_rooms.get(own_room) or "").lower()
        for sentence in _SENTENCE_SPLIT.split(prose):
            # Quoted speech is a speaker's claim, not narration.
            scan = re.sub(r'"[^"]*"|“[^“”]*”', " ", sentence)
            best = max((mm.start() for p in pats for mm in p.finditer(scan)),
                       default=-1)
            if best < 0:
                continue
            for rid, rname in usable_rooms.items():
                if rid == own_room:
                    continue
                low = rname.lower()
                # A room whose name contains (or is contained by) the
                # character's own room's name cannot be told apart reliably.
                if own_name and (low in own_name or own_name in low):
                    continue
                place = re.compile(
                    r"\b(?:back\s+)?(?:in|inside|within|into|at)\s+"
                    r"(?:the\s+)?(?:\w+[ -]){0,2}?" + re.escape(rname)
                    + r"\b", re.I)
                pm = place.search(scan, best)
                if not pm:
                    continue
                if _LOOK_VERB_RE.search(scan[:pm.start()]):
                    continue
                warnings.append(
                    f"Character placed in wrong room: '{name}' is narrated "
                    f"in '{rname}' but this beat's committed position is "
                    f"'{usable_rooms.get(own_room, own_room)}' and no "
                    "movement occurred for them this beat. Keep them where "
                    "the scene puts them."
                )
                break
            else:
                continue
            break
    return warnings


_PORTAL_OPEN_RE = r"(?:open|ajar|wide[- ]open)"
_PORTAL_SHUT_RE = r"(?:shut|closed|sealed|locked)"


def _check_portal_fidelity(prose, portal_states):
    """F3: named portal state in prose must match the committed scene (DW t9
    shuts the double doors; t12 renders 'through the open doors' with no
    open event). portal_states: {display_name: 'open'|'shut'} for portals the
    player can currently see (built in agents/narration.py)."""
    if not prose or not portal_states:
        return []
    scan = re.sub(r'"[^"]*"|“[^“”]*”', " ", prose)
    warnings = []
    for name, state in portal_states.items():
        name = str(name or "").strip()
        state = str(state or "").strip().lower()
        if len(name) < 4 or state not in ("open", "shut"):
            continue
        wrong = _PORTAL_SHUT_RE if state == "open" else _PORTAL_OPEN_RE
        name_pat = r"\s+".join(re.escape(w) for w in name.split())
        asserted = (
            # "the open doors" / "still-sealed hatch"
            re.search(r"\b" + wrong + r"(?:\s+\w+)?\s+" + name_pat + r"\b",
                      scan, re.I)
            # "the doors ... stand open" (same clause)
            or re.search(r"\b" + name_pat + r"\b[^.!?\n,;]{0,60}?\b" + wrong
                         + r"\b", scan, re.I)
        )
        if asserted:
            opposite = "shut" if state == "open" else "open"
            warnings.append(
                f"Portal state contradicts the scene: '{name}' is committed "
                f"{state} this beat, but the prose renders it {opposite}. "
                "Match the committed portal state exactly."
            )
    return warnings


# The player's own interiority, in the second person the narrator writes in.
# "you feel", "your terror", "terror grips you" -- the same boundary
# `_check_player_interiority_authority` defends on the Director's side, at the
# last stage before the reader.
_YOU_INTERIOR = re.compile(
    r"\byou(?:r)?\s+(?:own\s+)?(?:" + "|".join(
        re.escape(w) for w in _INTERIOR_STATES) + r")\b"
    r"|\byou\s+(?:feel|felt|realise|realised|realize|realized|know|knew|"
    r"want|wanted|wish|wished|hope|hoped|fear|feared|understand|understood|"
    r"remember|remembered|decide|decided|sense|sensed)\b"
    r"|\b(?:" + "|".join(re.escape(w) for w in _INTERIOR_STATES) +
    r")\s+(?:grips|grip|floods|flood|washes|wash|rises|rise|takes|take|"
    r"fills|fill|seizes|seize|surges|surge)\s+(?:through\s+)?you\b"
    # A named interior state anywhere in a clause that also reaches for the
    # player. The three patterns above all require the state to sit directly
    # beside "you"/"your" or to govern it through a short verb list, and prose
    # does not oblige: chat 56 ("Run!") t6 rendered the Director's invented
    # "the terror in her eyes has begun to recede" as "The terror that had
    # been living wide-open in YOUR eyes pulls back to something smaller",
    # where "your" attaches to "eyes" and the verb is "pulls back". One word
    # out of reach of every branch, and the guard was silent.
    r"|\b(?:the|that|this|a|an)\s+(?:"
    + "|".join(re.escape(w) for w in _INTERIOR_STATES)
    + r")\b(?=[^.!?]{0,60}\byou(?:r)?\b)",
    re.I)


def _check_player_interiority_prose(prose, view=""):
    """Interior states the NARRATOR asserts about the player.

    The narrator renders the player-facing slice; it does not get to tell the
    player what their character feels. It may render every observable the view
    delivered -- a shaking hand, a held breath, a step back -- and stop there.

    Anything already in the VIEW is exempt: perception is the narrator's
    source of truth, so a feeling that reached it legitimately (the player
    declared it, or a character's own delivered cue carried it) may be
    rendered. This catches what the narrator adds on its own.

    Second person, because that is what the narrator writes in: the Director's
    counterpart matches the player's NAME and would never fire here.
    """
    prose = str(prose or "")
    if not prose:
        return []
    source = str(view or "").casefold()
    warnings = []
    for match in _YOU_INTERIOR.finditer(prose):
        phrase = match.group(0)
        # Present in the view already -> the narrator is rendering, not adding.
        if phrase.casefold() in source:
            continue
        sentence = prose[max(0, match.start() - 60):match.end() + 60]
        warnings.append(
            "Narrator asserted the player's interior state "
            f"(player-interiority fidelity): {phrase!r} in {sentence.strip()[:120]!r}")
    return warnings


def _check_narrator_fidelity(out, view, recent_prose=None, exclude_quotes=None,
                             cast_pronouns=None, player_name=None,
                             narration_person=None, player_aliases=None,
                             event_order=None, position_facts=None,
                             room_names=None, portal_states=None):
    warnings = []
    view_text = str(view or "")
    prose = out.get("prose") or ""
    warnings.extend(_check_player_interiority_prose(prose, view_text))
    view_names = set(re.findall(
        r"\b[A-Z][a-z]+(?:\s+(?:of\s+)?(?:the\s+)?[A-Z][a-z]+)+\b", view_text))
    for name in view_names:
        if name.lower() in prose.lower():
            continue
        # Good prose refers to people by surname or first name alone after
        # the first mention ("Voss", "Tommy") rather than repeating a full
        # multi-word name every time; that is not a fidelity violation.
        # Only flag names where NONE of their words appear anywhere.
        name_words = [w for w in name.split() if len(w) >= 3]
        if name_words and not any(w.lower() in prose.lower() for w in name_words):
            warnings.append(f"Proper noun from view missing in narrator prose: '{name}'")

    # recent_prose_for_rhythm is supplied to the narrator as a STYLE
    # reference, but nothing stops the model from reusing its content
    # instead -- especially when the current view covers similar ground
    # (same room, same people) to a recent turn. Two or more shared
    # six-word runs between this turn's prose and a recent turn's prose
    # essentially can't happen by coincidence; it means this turn's beats
    # were recycled rather than drawn from the current view.
    current_shingles = _word_shingles(prose)
    if current_shingles:
        for prev_prose in (recent_prose or []):
            overlap = current_shingles & _word_shingles(prev_prose)
            if len(overlap) >= 2:
                sample = next(iter(overlap))
                warnings.append(
                    "Narrator prose appears to reuse a previous turn's "
                    "content instead of describing this turn's view "
                    f"(shared phrase: '{sample}...')."
                )
                break

    # Any quoted line in the view is dialogue that reached the player at
    # full or fragment clarity (muffled hits render as unquoted "...something
    # about X..." text and are exempt). DIALOGUE FIDELITY requires every such
    # line to survive verbatim -- if the narrator drops, truncates, or
    # paraphrases a quote, the exact substring will no longer be found.
    # EXCEPT the player's own declared lines: PLAYER ECHO RULE requires those
    # to be *excluded*, the exact opposite requirement, so they must never be
    # scored against this check -- otherwise the two rules contradict each
    # other and the retry loop would be pushing the model to violate one to
    # satisfy the other.
    excluded_bodies = {
        re.sub(r"\s+", " ", _quote_body(q).casefold()).rstrip(".,!?…;:")
        for q in (exclude_quotes or []) if _quote_body(q)
    }
    quote_pattern = _QUOTE_BODY_RE
    normalized_prose = re.sub(r"\s+", " ", prose.casefold())
    for match in quote_pattern.finditer(view_text):
        quote = re.sub(r"\s+", " ", match.group(1).strip())
        if not quote:
            continue
        if quote.casefold().rstrip(".,!?…;:") in excluded_bodies:
            continue
        if not _contains_quote(normalized_prose, quote):
            warnings.append(
                f"Dialogue from view missing or altered in narrator prose: \"{quote[:80]}\""
            )

    # ONE PAIR OF QUOTES, ONE MOUTH.
    #
    # The check above asks whether each line SURVIVED. It cannot ask whether
    # the line ended up in the right person's mouth, and both questions have
    # the same answer when two speakers' lines are welded into a single
    # quoted span: every body is present verbatim, so dialogue fidelity
    # passes while the reader is told the wrong character said half of it.
    #
    # Live (chat 38, t140): Tamamo's "Be at ease, both of you." and the
    # Doctor's "Tamamo. A pleasure." rendered as the single span
    # "Be at ease, both of you. Tamamo. A pleasure.", closed by "The Doctor's
    # voice carries clean across the clearing". The view had them correctly
    # separated, one attributed clause each. Also chat 38 t39, where the whole
    # of Guinan's line was absorbed into the Doctor's.
    #
    # `event_order` is the right source rather than the raw dialogue log: it
    # is already gated to lines that reached the player's view, so a line the
    # player never heard cannot raise a warning about prose that rightly
    # omits it. Bodies under 15 characters are ignored -- a short line can sit
    # inside a longer one by coincidence, and being wrong here costs a
    # rewrite.
    speech_events = []
    for event in (event_order or []):
        if not isinstance(event, dict) or event.get("kind") != "speech":
            continue
        actor = str(event.get("actor") or "").strip()
        spoken = re.sub(r"\s+", " ", _quote_body(event.get("quote"))).casefold()
        if actor and len(spoken) >= 15:
            speech_events.append((actor, spoken))
    for match in _QUOTE_BODY_RE.finditer(prose):
        span = re.sub(r"\s+", " ", match.group(1)).casefold()
        actors = {actor for actor, spoken in speech_events if spoken in span}
        if len(actors) >= 2:
            warnings.append(
                "Merged dialogue from different speakers in one quoted span "
                f"({', '.join(sorted(actors))}): \"{match.group(1)[:80]}\""
            )

    warnings.extend(_check_pronoun_fidelity(prose, cast_pronouns))
    warnings.extend(_check_player_person(
        prose, player_name, narration_person, player_aliases))

    # F1-F4 world/ordering fidelity (all deterministic; each has its own
    # enforceable prefix in agents/narration.py so a violation buys exactly
    # one correction rewrite).
    warnings.extend(_check_event_order(prose, event_order))
    warnings.extend(_check_quote_attribution(
        prose, event_order, actor_pronouns=cast_pronouns))
    warnings.extend(_check_position_fidelity(
        prose, position_facts, room_names))
    warnings.extend(_check_portal_fidelity(prose, portal_states))
    warnings.extend(_check_action_direction(prose, event_order))

    return warnings

def _llm_resolve_player_room(sc, pers, cast, interp, player_input):
    positions = sc.get("positions") or {}
    if not positions:
        return None
    char_names = []
    for c in (cast or []):
        try:
            char_names.append(character_name_from_text(c["sheet"]))
        except Exception:
            pass
    payload = {
        "player": {"name": pers.get("name") or persona_name(pers), "appearance": pers.get("appearance"),
                   "senses": pers.get("senses", "")},
        "npc_names": char_names, "position_keys": list(positions.keys()),
        "positions": positions, "rooms": sc.get("rooms", {}),
        "player_input": player_input or "",
        "movement": (interp or {}).get("movement") or {},
        "private_thought": (interp or {}).get("private_thought") or ""
    }
    sys = (
        "You are a position resolver. Given a player persona, a list of NPC character names, "
        "and a set of position keys, identify which position key corresponds to the PLAYER "
        "character. Output STRICT JSON {\"key\": \"<one of the position_keys>\"} or "
        "{\"key\": null} if no match."
    )
    try:
        out = jparse(chat_complete("utility", sys, json.dumps(payload, ensure_ascii=False),
                                   temperature=0.0, max_tokens=1000))
        key = out.get("key") if isinstance(out, dict) else None
        if key and key in positions:
            return positions[key]
    except Exception:
        pass
    return None

def _resolve_player_room(sc, pers, interp, cast, player_input=None):
    # Canonical, committed position always wins over a declared movement
    # target: a `movement.to_room` is only a request for director_resolve
    # to validate (it may be blocked — see director.py's passable-route
    # check). Trusting it here would show the player as already having
    # arrived — during perception_act, before the move is even resolved,
    # or in perception_outcome, even when director_resolve rejected it.
    p_room = room_of(sc, pers.get("name") or persona_name(pers))
    if p_room:
        return p_room
    mv = interp.get("movement") if interp else None
    if isinstance(mv, dict) and mv.get("to_room"):
        return mv["to_room"]
    char_names = set()
    for c in (cast or []):
        try:
            char_names.add(character_name_from_text(c["sheet"]).lower().strip())
        except Exception:
            pass
    candidates = [v for k, v in (sc.get("positions") or {}).items()
                  if k.lower().strip() not in char_names]
    if len(candidates) == 1:
        return candidates[0]
    if sc.get("positions"):
        llm_room = _llm_resolve_player_room(sc, pers, cast, interp, player_input)
        if llm_room:
            return llm_room
    return None
