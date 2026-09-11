"""The detection substrate the Director's two reconciliation seams stand on.

Declaration coverage (the interpret seam's lexical-coverage detectors),
diff normalisation and placeholder stripping, subject matching and
identity forms, the category-aware evidence classes, and the numbered
`changes_asserted` manifest. One module by KIND, not by reuse: the two
seams are structural twins that share only `_norm_subject` in code. The
seams themselves -- `_reconcile_interpretation`, `_reconcile_resolution`
and its 54-line block comment -- stay in `agents/director.py`.

Import direction: nothing outside `agents/director*.py` may import an
`agents/director_*` submodule, and no `director_*` module may import
`agents.director` (that is the cycle the facade exists to prevent).
"""

import copy
import json
import re

from llm import schemas
from story.character_schema import (fold_identity_key,
                                    normalized_character_of_row)
from world.spatial import (_merge_entity, _merge_room, resolve_placement_target,
                           room_of)

# `director_scopes` owns the ownership table and imports no
# sibling, so this direction adds no cycle.
from .director_scopes import manifest_category_targets
from .common import (
    downgraded_sequence_indices,
    prune_blocked_phase_changes,
    _contextual_rooms,
    _dict,
    _dict_list,
    _list,
    character_scene_keys,
)
from .director_lingua import _ling

# ---------------------------------------------------------------------------
# Interpret reconciliation: the structural TWIN of the resolve seam below,
# run right after director_interpret's LLM call. Where the resolve seam
# catches prose-vs-diff omissions, this one catches INPUT-vs-interpretation
# omissions: a player-declared place/object/event present in the raw input
# but absent from interpret's sequence/movement/mapping channels is a
# dropped declaration -- under the PLAYER AUTHORITY CONTRACT it silently
# never happened, before resolution even began.
#
# Detection is deliberately NOT keyword/verb enumeration of world content
# (the same unwinnable treadmill the resolve seam rejects): it is pure
# LEXICAL COVERAGE -- the raw input is split into declaration units
# (quoted spans + narrative clauses) and each unit's significant tokens
# are checked against every channel that actually carries a declaration
# forward (sequence, movement, mapping_request, location_query,
# generation_requests, private_thought). A unit most of whose tokens
# appear nowhere is a drop, whatever its subject matter.
#
# Disposition mirrors the resolve seam's conservatism: one bounded
# self-repair BY THE DIRECTOR ITSELF (additive only -- existing elements
# and a declared movement are never replaced), deterministic re-check, and
# for anything still uncovered a warn-only fallback that forwards the
# player's VERBATIM clause to mapping as a generation_request (bounded
# additive elaboration: the player owns existence + stated specifics, the
# engine owns only the unstated) -- this engine never fabricates a
# structured act from a heuristic.
# ---------------------------------------------------------------------------



_RECONCILE_INTERPRET_MAX_UNITS = 4
_INTERPRET_COVERAGE_MIN = 0.5

def _decl_tokens(text):
    """Significant tokens of one declaration unit: casefolded alphanumeric
    words, length >= 3, stopwords removed. No domain keyword lists -- pure
    lexical coverage is the anti-treadmill property this seam is built on."""
    tokens = set()
    for tok in re.findall(r"[a-z0-9']+", str(text or "").casefold()):
        tok = tok.strip("'")
        if len(tok) >= 3 and tok not in _ling("_DECL_STOPWORDS"):
            tokens.add(tok)
    return tokens

def _declaration_units(raw_input):
    """Split raw player input into declaration units: quoted spans (each a
    speech declaration) plus narrative clauses split on sentence boundaries
    and coordination. Units with fewer than two significant tokens are
    skipped -- too little signal to judge coverage without false positives
    (the conservative floor)."""
    text = str(raw_input or "")
    units = [m.group(1).strip() for m in _ling("_QUOTED_UNIT_RE").finditer(text)]
    narrative = _ling("_QUOTED_UNIT_RE").sub(" ", text)
    for clause in _ling("_CLAUSE_SPLIT_RE").split(narrative):
        clause = clause.strip(" ,")
        if clause:
            units.append(clause)
    return [u for u in units if len(_decl_tokens(u)) >= 2]

def _interpret_coverage_corpus(out):
    """Token set of every channel that actually carries a declaration
    forward into the turn. Deliberately NOT `notes` -- prose parked in
    notes never enters causality, which is exactly the drop being
    detected."""
    flow = _dict(out.get("flow"))
    pieces = []
    for e in out.get("sequence") or []:
        if not isinstance(e, dict):
            continue
        # `tone` and `observable` are not decorative side channels: they are
        # where interpret carries the player's authored delivery and visible
        # gesture forward.  Omitting them from coverage made reconciliation
        # "repair" a declaration that was already fully represented.  Live
        # (chat 38, turn 125), genuine awe and a teasing smirk were present in
        # the two speech tones and the turn between them was present in the
        # action observable, yet the uncovered-clause check appended a fourth
        # action containing the entire narrative bridge.  Perception then had
        # two competing versions of the same chronology.
        for field in ("text", "attempt", "raw_text", "description",
                      "observable", "tone", "subject", "verb", "act",
                      "content", "topic"):
            pieces.append(e.get(field))
        pieces.extend(str(t) for t in (e.get("targets") or []))
        pieces.extend(str(t) for t in (e.get("participants") or []))
        effects = _list(e.get("intended_effects")) + \
            _list(e.get("asserted_effects"))
        for eff in effects:
            if isinstance(eff, dict):
                pieces.append(eff.get("kind"))
                pieces.append(eff.get("target_id"))
                try:
                    pieces.append(json.dumps(eff.get("details") or {},
                                             ensure_ascii=False))
                except (TypeError, ValueError):
                    pass
    mv = out.get("movement")
    if isinstance(mv, dict):
        pieces.append(str(mv.get("to_room") or "").replace("_", " "))
        pieces.append(mv.get("why"))
        pieces.append(str(mv.get("mover") or "").replace("_", " "))
    pieces.append(out.get("private_thought"))
    pieces.append(out.get("location_query"))
    pieces.append(flow.get("mapping_request"))
    for gr in _dict_list(flow.get("generation_requests")):
        pieces.append(gr.get("kind"))
        pieces.append(gr.get("subject"))
        pieces.extend(str(c) for c in (gr.get("constraints") or []))
        pieces.append(str(gr.get("location_id") or "").replace("_", " "))
    tokens = set()
    for piece in pieces:
        tokens |= _decl_tokens(piece)
    return tokens

def _unit_covered(unit, corpus, prefixes):
    """Coverage test for one declaration unit: at least half its
    significant tokens appear in the corpus (exact, or by shared 4-char
    prefix -- crude stemming so 'ducks'/'ducking' covers 'duck')."""
    tokens = _decl_tokens(unit)
    if not tokens:
        return True
    hits = sum(
        1 for t in tokens
        if t in corpus or (len(t) >= 4 and t[:4] in prefixes)
    )
    return hits / len(tokens) >= _INTERPRET_COVERAGE_MIN

def _uncovered_declarations(raw_input, out):
    """Deterministic omission detection: declaration units of the raw input
    whose significant tokens are mostly absent from every channel of the
    interpretation. Capped -- a fully off-the-rails interpretation is
    better re-run than repaired unit by unit."""
    corpus = _interpret_coverage_corpus(out)
    prefixes = {c[:4] for c in corpus if len(c) >= 4}
    uncovered = [
        u for u in _declaration_units(raw_input)
        if not _unit_covered(u, corpus, prefixes)
    ]
    return uncovered[:_RECONCILE_INTERPRET_MAX_UNITS]

def _output_field_names():
    """Every top-level key the Director's own output shapes declare.

    SOURCED FROM THE SCHEMAS, never hand-listed: the whole failure being
    guarded is a model nesting one of these keys inside `rooms`, so a list
    that can drift out of step with the real shape would go stale exactly
    when a new field started leaking.
    """
    models = [getattr(schemas, "StateDiff", None)]
    # Every Director-side stage, INCLUDING the specialists -- `resolved_events`
    # is a specialist echo field and was one of the two that actually leaked.
    models += [cls for key, cls in (getattr(schemas, "SCHEMA_MAP", {}) or {}
                                    ).items() if key.startswith("director_")]
    names = set()
    for cls in models:
        names.update(str(f).casefold() for f in schemas._fields(cls))
    # Container names that ARE legitimate diff keys are not room ids either,
    # but they are already handled above; what matters here is that a room
    # can never be called one of these.
    return frozenset(names)


_OUTPUT_FIELD_NAMES = _output_field_names()


def _normalize_diff_shape(sd):
    """Coerce a state_diff (from the main resolve output or a repair delta)
    to the canonical container shapes every downstream reader assumes.
    Safety net for the LLM returning a string/list where an object belongs."""
    if not isinstance(sd, dict):
        sd = {}
    # DERIVED FROM THE SCHEMA, like the two reader tables below. This was a
    # hand list of 11 dict channels and 15 list channels against a 37-field
    # StateDiff, so `sensory_events`, `comms_ops`, `courier_ops`,
    # `artifact_ops`, `charter_ops`, `ratified_claims`, `contradicted_claims`
    # and `movement_refused` reached every downstream reader in whatever
    # shape the model sent -- and `_merge_repair_into_diff` below indexed
    # `sd[field]` for channels this never created.
    for k in _diff_dict_channels():
        if not isinstance(sd.get(k), dict):
            sd[k] = {}
    for k in _diff_list_channels():
        if not isinstance(sd.get(k), list):
            sd[k] = []
    # A SCHEMA FIELD NAME IS NOT A ROOM. Live, chat 72 turn 44: `rooms` came
    # back carrying `resolved_events` and `notes` alongside two real rooms,
    # and the coercion above dutifully made each a room dict. That story's
    # map now has a blank-named room called `resolved_events` adjacent to
    # the hotel lobby, and every route query walks through it.
    #
    # These are not typos, they are keys from the output shape the model was
    # just asked to produce -- an ordinary nesting slip, and one the engine
    # can recognise for certain: no fiction names a room after a JSON key.
    # Whole-id match only, so a genuine `notes_office` survives. Rooms are
    # the only container this applies to; elsewhere the key is a body or an
    # object name where a collision means nothing.
    rooms = sd.get("rooms")
    if isinstance(rooms, dict):
        for _key in [k for k in rooms if str(k).strip().casefold()
                     in _OUTPUT_FIELD_NAMES]:
            rooms.pop(_key, None)
    # A PROVENANCE ID OF ZERO IS NOT PROVENANCE. `from_event` is declared on
    # every typed delegated record so validation cannot strip it (typed models
    # drop what they do not declare), which means an unset one serialises as
    # `from_event: 0` on EVERY record in the diff -- and the diff is what gets
    # stored, archived and checkpointed. That is the same noise
    # `_manifest_items` refuses when it adds an endpoint key "only when the
    # model actually supplied them, rather than four empty strings appearing
    # on every item".
    #
    # Non-zero ids survive untouched, so reconciliation still reads them; a
    # record that answered no numbered work item comes out looking exactly as
    # it did before the field existed.
    _drop_zero_provenance(sd)
    sd.setdefault("time", None)
    return sd


def _without_provenance(value, depth=0):
    """A copy of a channel value with every `from_event` removed.

    For COMPARING two spellings of the same content. A hand stamps the chunk
    it resolved and the stage author never does, so an author and a hand that
    emitted the identical record differ by construction once provenance
    exists -- and the orchestration backstop, which asks whether the author
    put CONTENT somewhere it was told not to, would report that as a
    mis-emission on every beat.
    """
    if depth > 4:
        return value
    if isinstance(value, dict):
        return {k: _without_provenance(v, depth + 1)
                for k, v in value.items() if k != "from_event"}
    if isinstance(value, list):
        return [_without_provenance(v, depth + 1) for v in value]
    return value


def _drop_zero_provenance(value, depth=0):
    """Remove `from_event: 0` wherever it appears in a diff."""
    if depth > 4:
        return
    if isinstance(value, dict):
        if value.get("from_event") in (0, "0", None) and "from_event" in value:
            value.pop("from_event", None)
        for inner in list(value.values()):
            _drop_zero_provenance(inner, depth + 1)
    elif isinstance(value, list):
        for inner in value:
            _drop_zero_provenance(inner, depth + 1)


def _is_blank_placeholder(entry):
    """True when a diff entry encodes nothing at all -- every field an empty
    string/list/dict or zero (e.g. {"name":"","desc":"","adjacent":[],
    "notes":""}, observed live as an elevator room's entire 'change'). Such
    an entry commits as if the change were handled while changing nothing:
    pure noise, and a cheap deterministic divergence signal."""
    if not isinstance(entry, dict):
        return False
    for value in entry.values():
        if isinstance(value, (dict, list)):
            if value:
                return False
        elif isinstance(value, bool):
            if value:
                return False
        elif isinstance(value, (int, float)):
            if value:
                return False
        elif str(value or "").strip():
            return False
    return True

def _strip_blank_diff_placeholders(sd):
    """Remove empty-placeholder entries from the diff's keyed containers and
    return one structural divergence signal per stripped key. Runs on both
    the original diff and any repair delta (a repair may not reintroduce
    noise). conditions values are lists of condition dicts; a key whose list
    is empty or all-blank is the same noise in that shape."""
    signals = []

    def flag(category, subject, field):
        signals.append({
            "category": category, "subject": str(subject),
            "change": (f"state_diff.{field}[{subject!r}] was an empty "
                       "placeholder encoding no change at all"),
            "evidence": "", "source": "structural",
        })

    for field, category in (("rooms", "rooms"), ("entities", "entities"),
                            ("attire", "attire"), ("poses", "poses")):
        table = sd.get(field)
        if not isinstance(table, dict):
            continue
        for key in [k for k, v in table.items() if _is_blank_placeholder(v)]:
            table.pop(key)
            flag(category, key, field)

    conditions = sd.get("conditions")
    if isinstance(conditions, dict):
        for key in list(conditions.keys()):
            value = conditions[key]
            entries = value if isinstance(value, list) else [value]
            if all(_is_blank_placeholder(e) or e is None for e in entries):
                conditions.pop(key)
                flag("conditions", key, "conditions")

    positions = sd.get("positions")
    if isinstance(positions, dict):
        for key in [k for k, v in positions.items()
                    if not str(v or "").strip()]:
            positions.pop(key)
            flag("positions", key, "positions")

    return signals

# ---------------------------------------------------------------------------
# THE STATEDIFF CHANNEL TABLES
#
# The two readers that ask a question ABOUT a whole diff -- the tripwire's
# "did this diff encode anything" (`_diff_is_substantive`, below) and the
# subject containment check (`_omission_subject_encoded`) -- each restated a
# SUBSET of StateDiff by hand, and each had drifted from it. Measured against
# the 37-channel schema: the tripwire counted 16, so a beat encoded only in
# `containment`, `stations`, `scales` or `vitals` read as encoding nothing at
# all and bought the deep audit the tripwire exists to buy; and the
# containment check, whose docstring promises ANY diff field, walked 13, so a
# player-asserted effect landing in `overlays`, `stations`, `containment`,
# `vitals` or `scales` was judged UNENCODED and bought the Director a repair
# call for a beat it had already encoded correctly. Both drifts fail toward
# spending a model call on a diff that was fine.
#
# So the SCHEMA is the enumeration and these tables record only what is not
# ordinary. Every StateDiff channel must appear in exactly one of them, which
# `tests/test_director_diff_channels.py` asserts channel by channel: when the
# schema grows one, that test fails and the author classifies it. A hand-kept
# list that has to track a schema is only ever as current as the guard that
# fails when the schema moves.
# ---------------------------------------------------------------------------


def _state_diff_channels():
    """Every declared StateDiff channel, on either Pydantic major."""
    return frozenset(schemas._fields(schemas.StateDiff) or {})


def _diff_dict_channels():
    """The keyed-table channels, from the schema (`schemas.dict_shaped_fields`)."""
    return frozenset(schemas.dict_shaped_fields(schemas.StateDiff))


def _diff_list_channels():
    """The list channels, from the schema (`schemas.list_shaped_fields`)."""
    return frozenset(schemas.list_shaped_fields(schemas.StateDiff))


#: Keyed channels a repair may only ADD to, never overwrite: the original
#: diff's positions carry the deterministically validated player move
#: (passable-route check) and must stand; poses and stations are partial
#: per-entity updates that must never be filled out with defaults that
#: clobber the standing roster (AGENTS.md's stations row).
_REPAIR_ADD_ONLY = frozenset({"positions", "poses", "stations"})


# Channels a diff can carry while having encoded no change of this beat's own.
# The reason is the load-bearing part: each is bookkeeping ABOUT a change, a
# change scheduled for some OTHER beat, or a channel present on nearly every
# diff -- and a channel present on nearly every diff cannot separate a diff
# that encoded the beat from one that did not, which is the only question the
# tripwire asks.
_NON_SUBSTANTIVE_CHANNELS = {
    "phase_sources": "provenance for another channel's value, stripped by the "
                     "causal floor before merge; the change is in the channel "
                     "it points at",
    "time": "every beat advances the clock, so its presence separates nothing",
    "weather": "the sky drifts on its own clock (weather.advance_weather); "
               "ambient dressing is no evidence the beat's own act landed",
    "following_ops": "projected deterministically from the interpretation and "
                     "the character decisions -- the resolve does not author "
                     "it, so it cannot show that the resolve encoded anything",
    "world_facts": "a lore sentence records what the world IS, not what this "
                   "beat DID",
    "introductions": "a name learned; whatever physical act carried it is in "
                     "the counted channels",
    "ratified_claims": "a verdict on an EARLIER beat's hearsay",
    "contradicted_claims": "the same verdict, negated",
    "claim_dispositions": "an adjudication of a player claim, present whenever "
                          "the player claimed anything; what it licensed is "
                          "encoded in the counted channels",
    "consequences": "explicitly NOT this beat's outcome -- a fuse fired when "
                    "the clock reaches it (the schema's own comment says so)",
}

_SUBSTANTIVE_CHANNELS = frozenset(
    _state_diff_channels() - set(_NON_SUBSTANTIVE_CHANNELS))


# WHERE A SUBJECT'S IDENTITY CAN SIT, per channel. Identity keys only: a prose
# field (`consequences.what`, an op's `detail` or `reason`, a world_fact
# sentence) is deliberately not searched, because this check's answer decides
# whether the Director is asked to repair, and a subject that merely appears
# as a substring of prose would acquit the omission the check exists to find.

# Dict channels, keyed BY the subject. The tuple is the identity keys inside
# the value, which may be a dict or (conditions) a list of them.
_SUBJECT_KEYED_CHANNELS = {
    "positions": (),
    "rooms": ("name",),
    "entities": ("name", "aliases"),
    "attire": (),
    # `relative_to` stays out: it names the body a pose is MEASURED against,
    # and the entry says nothing about that body's own state.
    "poses": (),
    "stations": (),
    "scales": (),
    # Containment is a two-body fact, like a contact, so the holder counts as
    # much as the contained (contact_ops has always counted its target).
    "containment": ("in",),
    "vitals": (),
    "overlays": (),
    # The key IS the condition_id, which the entries repeat.
    "conditions": ("subject_id", "condition_id"),
}

# Channels whose VALUE is the subject: a list of ids, or the one bare string.
_SUBJECT_VALUE_CHANNELS = frozenset({
    "remove_entities", "remove_rooms", "location",
})

# Op channels -- a list of records, or the single dict `destruction` arrives
# as -- and the keys in a record that name a body, an object, a room, or a
# thing the engine minted an id for.
_SUBJECT_OP_CHANNELS = {
    "remove_adjacent": ("room", "to"),
    # Engine-authored (the movement backstop): the body whose declared walk
    # was refused, and the room it did not reach.
    "movement_refused": ("subject", "to_room"),
    "inventory_ops": ("object_id", "from_id", "to_id"),
    "contact_ops": ("actor", "target"),
    "contact_action_ops": ("actor", "action"),
    "substance_ops": ("source", "target", "substance"),
    "following_ops": ("follower", "target"),
    "cast_changes": ("who",),
    "introductions": ("who", "learns"),
    "comms_ops": ("id", "name", "rooms", "carriers"),
    "crowd_ops": ("crowd_id", "who", "room"),
    "telling_ops": ("speaker", "listener"),
    "courier_ops": ("courier_id", "sender", "addressee", "listener", "by",
                    "from_room", "to_room"),
    "artifact_ops": ("artifact_id", "poster", "room", "reader", "by"),
    "consequences": ("where", "originator"),
    "destruction": ("effect_id", "target_id", "affected_locations"),
    # A one-beat signal: the room it happened in, and the thing that made
    # it. `detail` is what the noise was LIKE and names nothing, so it is
    # not read here.
    "sensory_events": ("room", "source"),
    "charter_ops": ("body", "to"),
}

# A manifest subject that names the CHANNEL rather than a body ("contacts",
# "substance"): any record in that channel is the encoding. Carried over from
# the hand-written version, which checked these same three inline.
_CHANNEL_WORD_SUBJECTS = {
    "contact_ops": ("contact", "contacts"),
    "contact_action_ops": ("contactaction", "contactactions", "contacteffect"),
    "substance_ops": ("substance", "substances", "material"),
}

# The rest: channels holding no world identity at all, and why not.
_SUBJECTLESS_CHANNELS = {
    "phase_sources": "keys are '<channel>.<subject>' provenance strings; the "
                     "subject they name is already read in that channel",
    "time": "a clock reading",
    "weather": "one sky over the whole scene, keyed by nothing",
    "world_facts": "prose, or {fact, source} around prose -- see the "
                   "identity-only rule above",
    "ratified_claims": "claim references, in the claims namespace rather than "
                       "the world's",
    "contradicted_claims": "the same claim references, rejected instead of "
                           "ratified",
    "claim_dispositions": "keyed by claim_id, and a verdict is not an "
                          "encoding: believing one here would acquit exactly "
                          "the omission this check exists to find",
}


def _channel_records(value):
    """The records an op-shaped channel carries: a list of dicts, or the
    single dict `destruction` arrives as."""
    if isinstance(value, dict):
        return [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [v for v in value if isinstance(v, dict)]


def _hits_identity(record, keys, hits):
    """Does any of `keys` on this record name the subject? A key's value may
    be a string or a list of them (`entities.aliases`, `comms_ops.rooms`)."""
    for key in keys:
        value = record.get(key)
        if isinstance(value, (list, tuple, set)):
            if any(isinstance(v, str) and hits(v) for v in value):
                return True
        elif isinstance(value, str) and hits(value):
            return True
    return False


def _diff_is_substantive(sd):
    """True when the diff asserts any physical change at all (post-strip).

    Every StateDiff channel counts except the ones `_NON_SUBSTANTIVE_CHANNELS`
    names and says why -- derived, so a channel the schema grows counts by
    default instead of silently reading as nothing encoded."""
    return any(sd.get(key) for key in _SUBSTANTIVE_CHANNELS)

def _beat_has_physical_activity(interp, char_actions, dice):
    """Deterministic gate input: did anyone attempt a physical act this
    beat? Structural only (sequence element types, movement, dice) -- no
    prose keyword matching."""
    mv = interp.get("movement")
    if isinstance(mv, dict) and mv.get("to_room"):
        return True
    if dice or char_actions:
        return True
    sequences = [interp.get("sequence") or []]
    for entry in (interp.get("other_players") or {}).values():
        if isinstance(entry, dict):
            sequences.append(entry.get("sequence") or [])
    for seq in sequences:
        for e in seq:
            if isinstance(e, dict) and e.get("type") == "action" \
                    and e.get("attempt"):
                return True
    return False

def _reconcile_scene_slice(sc, cast, p_room, sd):
    """Compact prior-scene payload for the audit/repair calls: occupied and
    diff-touched rooms plus immediate neighbors (same trimming rationale as
    _contextual_rooms everywhere else), full positions/entities."""
    extra = [p_room] + list((sd.get("rooms") or {}).keys())
    return {
        "rooms": _contextual_rooms(sc, cast, *extra),
        "positions": sc.get("positions") or {},
        "entities": sc.get("entities") or {},
        "poses": sc.get("poses") or {},
        "substances": sc.get("substances") or [],
    }

def _merge_repair_into_diff(sd, patch):
    """Additively merge the Director's correction delta into the original
    state_diff. Conservative contract: a repair may ADD or refine encodings
    but can never silently delete what the original diff already asserted.
    Rooms merge edge-aware (spatial._merge_room, upsert by 'to'); the other
    keyed containers upsert per key, except positions which are add-only --
    the original diff's positions include the deterministically validated
    player move (passable-route check) and must stand. List categories
    union with dedup; time fills only if the original had none."""
    for room_id, incoming in (patch.get("rooms") or {}).items():
        if not isinstance(incoming, dict):
            continue
        existing = sd["rooms"].get(room_id)
        sd["rooms"][room_id] = (
            _merge_room(existing, incoming, room_id)
            if isinstance(existing, dict) else incoming
        )
    # Entities merge field-aware for the same reason rooms merge edge-aware:
    # both sides here are partial, so an absent field is silence rather than
    # an erasure (see spatial._merge_entity).
    for key, incoming in (patch.get("entities") or {}).items():
        existing = sd["entities"].get(key)
        sd["entities"][key] = (
            _merge_entity(key, existing, incoming)
            if isinstance(existing, dict) and isinstance(incoming, dict)
            else incoming
        )
    for key, incoming in (patch.get("conditions") or {}).items():
        incoming_list = incoming if isinstance(incoming, list) else [incoming]
        incoming_list = [c for c in incoming_list if isinstance(c, dict)]
        existing = sd["conditions"].get(key)
        if isinstance(existing, list):
            existing.extend(c for c in incoming_list if c not in existing)
        else:
            sd["conditions"][key] = incoming_list
    # EVERY OTHER CHANNEL, FROM THE SCHEMA. This was a hand list: rooms,
    # entities, attire, overlays, conditions, positions, poses, stations,
    # ten list fields and time -- so a specialist repair that encoded the
    # omission in `scales`, `containment`, `vitals`, `destruction`,
    # `artifact_ops`, `sensory_events`, `comms_ops`, `crowd_ops`,
    # `courier_ops`, `telling_ops`, `charter_ops`, `public_evidence`,
    # `ratified_claims` or `contradicted_claims` never reached `sd`: the
    # record said repaired, the re-check found nothing, and the beat shipped
    # a staleness warning for a repair that was made and thrown away. Dict
    # channels upsert per key (add-only where the original must stand);
    # list channels union with dedup; the scalar leaves fill only a hole.
    special = {"rooms", "entities", "conditions"}
    for field in sorted(_diff_dict_channels() - special):
        incoming = patch.get(field)
        if not isinstance(incoming, dict):
            continue
        target = sd.setdefault(field, {})
        if not isinstance(target, dict):
            target = sd[field] = {}
        for key, value in incoming.items():
            if field in _REPAIR_ADD_ONLY:
                target.setdefault(key, value)
            else:
                target[key] = value
    for field in sorted(_diff_list_channels()):
        incoming = patch.get(field)
        if not isinstance(incoming, list):
            continue
        target = sd.setdefault(field, [])
        if not isinstance(target, list):
            target = sd[field] = []
        for item in incoming:
            if item not in target:
                target.append(item)
    for field in sorted(_state_diff_channels()
                        - _diff_dict_channels() - _diff_list_channels()):
        incoming = patch.get(field)
        if incoming is None:
            continue
        if isinstance(incoming, dict) and isinstance(sd.get(field), dict):
            for key, value in incoming.items():     # destruction: two partials
                sd[field].setdefault(key, value)
        elif sd.get(field) is None:
            sd[field] = incoming
    return sd

def _norm_subject(value):
    """Casefolded comparison key for a claim subject -- the engine's one name
    fold (B34), so a non-Latin subject does not squash to the empty string."""
    return fold_identity_key(value)

def _claim_subject_in_world(subject, forms, sc):
    """Does the WORLD already know this claim's subject?

    True when `_subject_match_forms` found more than the bare string it was
    handed -- the subject matched a cast member's scene keys or an entity's
    ids and aliases -- or when the subject names a room in the scene.

    ONE OF THE TWO CHANNELS `_claim_subject_is_referrable` accepts, split out
    because the two answer different questions and only this one may bound a
    REFUSAL. "The player typed the word" qualifies a subject for coverage
    checking; it cannot establish that the subject is a THING, because every
    noun in a narrated sentence satisfies it. What the world already holds a
    record for is a thing, and that is what this asks.
    """
    normalized = _norm_subject(subject)
    if not normalized:
        return False
    if len(forms or []) > 1:
        return True
    rooms = ((sc or {}).get("rooms") or {})
    room_forms = set(rooms)
    for rid, room in rooms.items():
        if isinstance(room, dict) and room.get("name"):
            room_forms.add(str(room["name"]))
    return any(_norm_subject(r) == normalized for r in room_forms)


def _claim_subject_is_referrable(subject, forms, sc, player_input):
    """Can anyone point at what this claim is about?

    Two independent channels, either of which qualifies (see the block
    comment at the call site for the live case that made this necessary):

      * THE WORLD KNOWS IT -- `_claim_subject_in_world`, above.
      * THE PLAYER SAID IT -- the subject's words appear in what the player
        typed. This is the channel that keeps "I shatter the vault door" a
        real claim about a door no scene contains yet, which is exactly
        what player authority exists to do.

    Normalized to letters and digits on both sides, so `vault_door` matches
    "the vault door" and casing and punctuation cannot decide it. Fails
    open: anything this cannot evaluate is referrable, because refusing a
    claim is the direction that costs the player their authority.

    THE SECOND CHANNEL IS WIDE ON PURPOSE and cannot be narrowed here: it
    passes for every noun the player's own sentence contains, which is the
    price of never silently dropping an asserted effect. What it must NOT do
    is decide, further downstream, that the subject is a physical object --
    that judgment belongs to the repair, bounded by the first channel alone
    (`director_reconcile._verify_no_referent`).
    """
    normalized = _norm_subject(subject)
    if not normalized:
        return False
    if _claim_subject_in_world(subject, forms, sc):
        return True
    return normalized in _norm_subject(player_input)


def _subject_match_forms(subject, cast, sc):
    """Every identity form an omission subject may legitimately appear under
    in the diff: the subject itself, plus -- when it names a registered cast
    member -- all of that character's scene keys (name/uid/aliases via
    character_scene_keys), plus -- when it names a known scene entity -- that
    entity's id, name, and aliases. Closes the aliasing hole where a repair
    encodes under 'tenth_doctor' what the manifest called 'The Doctor'."""
    subject = str(subject or "").strip()
    forms = {subject} if subject else set()
    subject_cf = subject.casefold()
    if not subject_cf:
        return []
    for row in cast or []:
        # C14: memoised on the row's sheet TEXT; None is the same "no card to
        # read" answer the parse failure gave.
        sheet = normalized_character_of_row(row)
        if sheet is None:
            continue
        keys = character_scene_keys(sheet)
        if subject_cf in {k.casefold() for k in keys}:
            forms.update(keys)
    for eid, ent in ((sc or {}).get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        names = {str(eid)} | {str(ent.get("name") or "")} \
            | {str(a) for a in (ent.get("aliases") or [])}
        names = {n for n in names if n.strip()}
        if subject_cf in {n.casefold() for n in names}:
            forms.update(names)
    return [f for f in forms if f.strip()]

def _make_subject_hit(subject, forms=None):
    """A predicate testing whether a diff value references the subject under
    any of its identity forms (normalized, substring-tolerant so 'elevator'
    matches 'elevator_interior' -- but only for forms long enough not to
    false-match short generic fragments like 'hall' in 'smokehallway')."""
    targets = {_norm_subject(f) for f in ([subject] + list(forms or []))}
    targets = {t for t in targets if t}

    def hits(value):
        norm = _norm_subject(value)
        if not norm:
            return False
        for target in targets:
            if norm == target:
                return True
            shorter, longer = sorted((norm, target), key=len)
            if len(shorter) >= 5 and shorter in longer:
                return True
        return False

    return hits if targets else (lambda value: False)

def _room_anchor_hit(room_record, hits):
    """Does this room record name the subject among its ANCHORS?

    A DOORWAY'S IDENTITY IN THE `rooms` CHANNEL IS AN ANCHOR KEY. A room
    record is keyed by the room and named for the room; the fixture the
    beat is about -- the door, the hatch, the grille -- is one of its
    `anchors`, and a reader that stops at the room's id and name cannot see
    it. Both evidence readers need this and both were written without it,
    two months and one measured defect apart, which is why it is a function
    and not a loop in either of them.
    """
    anchors = room_record.get("anchors") \
        if isinstance(room_record, dict) else None
    if not isinstance(anchors, dict):
        return False
    for anchor_id, anchor in anchors.items():
        if hits(anchor_id):
            return True
        if isinstance(anchor, dict) and hits(anchor.get("desc")):
            return True
    return False


def _omission_subject_encoded(sd, subject, forms=None):
    """Deterministic containment check: does ANY diff field reference this
    subject (under any identity form)? Intentionally shallow -- it verifies
    the diff addressed the subject at all, not that the encoding is
    semantically right; the Director owns the semantics. Category-agnostic
    fallback; _evidence_present is the category-aware form.

    ANY means every StateDiff channel: the tables above say where an identity
    can sit in each one, and name the seven that hold none. A channel this
    does not walk is a channel in which a CORRECT encoding reads as an
    omission, and the answer here is what decides whether the Director is
    asked to repair a beat that was already right."""
    hits = _make_subject_hit(subject, forms)
    normalized = _norm_subject(subject)

    for field, value_keys in _SUBJECT_KEYED_CHANNELS.items():
        table = sd.get(field)
        if not isinstance(table, dict):
            continue
        for key, value in table.items():
            if hits(key):
                return True
            if value_keys and any(_hits_identity(record, value_keys, hits)
                                  for record in _channel_records(value)):
                return True
    # A DOORWAY'S IDENTITY IN THE `rooms` CHANNEL IS AN ANCHOR KEY, and the
    # walk above reads room ids and a room's `name` and stops. So a door
    # opened correctly -- the barrier moved on the edge and the doorway
    # redescribed as an anchor of the room -- read as an omission, and the
    # reconciliation asked for a repair of a beat that was already right.
    #
    # Measured (chat 117, turn 21): the player hauled a bulkhead fully open;
    # the objects hand declined it as the spatial hand's ("opening a door
    # between rooms is an edge barrier change belonging to spatial"), the
    # engine rerouted it, and spatial encoded
    # `rooms.sub5a_service_spine.adjacent[].barrier = open_door` with the
    # doorway under `anchors.plant_room_bulkhead_door`. The world was right
    # -- both sides open, sight `full` -- and the beat still reported the
    # change unencoded. This is the docstring's own named failure: "a
    # channel this does not walk is a channel in which a CORRECT encoding
    # reads as an omission".
    rooms = sd.get("rooms")
    if isinstance(rooms, dict) and any(
            _room_anchor_hit(record, hits) for record in rooms.values()):
        return True
    for field in _SUBJECT_VALUE_CHANNELS:
        value = sd.get(field)
        for item in ([value] if isinstance(value, str) else (value or [])):
            if hits(item):
                return True
    for field, keys in _SUBJECT_OP_CHANNELS.items():
        records = _channel_records(sd.get(field))
        if any(_hits_identity(record, keys, hits) for record in records):
            return True
        if records and normalized in _CHANNEL_WORD_SUBJECTS.get(field, ()):
            return True
    return False

# Category synonyms a model may plausibly write in a manifest entry, folded
# onto the canonical evidence-class names.

def _normalize_omission_category(category):
    cat = str(category or "").strip().casefold()
    return _ling("_OMISSION_CATEGORY_ALIASES").get(cat, cat) or "other"

def _entity_state_has_transit(entity_def):
    state = entity_def.get("state") if isinstance(entity_def, dict) else None
    return isinstance(state, dict) and ("transit" in state or "link" in state)

def _subject_is_somewhere(sd, scene, subject, hits, forms=None):
    """Does this beat leave the subject anywhere a mind could reach it?

    A THING THAT EXISTS AND IS NOWHERE IS NOT AN ENCODED CHANGE. `entities`
    carries no location -- an entity's room is `scene["positions"][id]` and
    nothing else -- so a mint on its own says a noun now exists and says
    nothing about where. Two evidence classes were acquitting placements on
    exactly that: measured, a diff carrying `entities: {x: {...}}` plus an
    `inventory_ops` entry naming x, with `positions` empty, reported ENCODED
    under both `entities` and `inventory` while `room_of` answered None. The
    detector that exists to catch an unencoded change was blind to this one,
    and the two categories a placement is naturally filed under were the two
    that acquitted it.

    Located means any of: this beat placed it, this beat put it in something,
    a transfer op named a destination that RESOLVES (the same resolver the
    merge derivation uses, so the classifier and the writer cannot disagree),
    the standing scene already places it, or it is one of the things that has
    no room by construction -- a bodiless voice, a portal spanning two rooms,
    or an entity this beat removed outright.
    """
    for key in (sd.get("positions") or {}):
        if hits(key):
            return True
    for key, record in (sd.get("containment") or {}).items():
        if hits(key) and record:
            return True
    for item in (sd.get("remove_entities") or []):
        if hits(item):
            return True
    for eid, ed in (sd.get("entities") or {}).items():
        if not (hits(eid) or (isinstance(ed, dict) and (
                hits(ed.get("name"))
                or any(hits(a) for a in (ed.get("aliases") or []))))):
            continue
        if isinstance(ed, dict) and (ed.get("ubiquitous")
                                     or _entity_state_has_transit(ed)):
            return True
    for op in (sd.get("inventory_ops") or []):
        if not isinstance(op, dict) or not hits(op.get("object_id")):
            continue
        if resolve_placement_target(scene or {}, op.get("to_id"))[0]:
            return True
    for form in [subject] + list(forms or []):
        if str(form or "").strip() and room_of(scene or {}, str(form)) is not None:
            return True
    return False


def _record_place(path, channel, record, sd, sc):
    """WHERE this record happens, as a token, or None when the engine cannot
    say.

    Stated per channel from what the engine issues, never from prose:

      * an edge is the doorway it describes -- `way:<a>|<b>`, sorted, so the
        two mirrored edges of one doorway produce ONE token;
      * a room record is that room;
      * anything keyed by a subject the scene places -- an entity, a body -- is
        the room it stands in;
      * everything else is None, and pairs with nothing.

    The scene is read for placement rather than the diff, then the diff over
    it, so a subject this beat moved pairs where it now IS.
    """
    from world.spatial import passage_id_for

    parts = str(path or "").split(".")
    if channel == "rooms" and len(parts) >= 3 and "adjacent" in parts[2]:
        target = str((record or {}).get("to") or "").strip()
        if len(parts) >= 2 and target:
            return "way:" + passage_id_for(parts[1], target)
    if channel == "rooms" and len(parts) == 2:
        return "room:" + parts[1]
    if len(parts) >= 2:
        subject = parts[1].split("[")[0]
        for source in ((sd or {}).get("positions"),
                       (sc or {}).get("positions")):
            if isinstance(source, dict):
                room = source.get(subject)
                if isinstance(room, str) and room.strip():
                    return "room:" + room.strip()
        if channel == "positions" and isinstance(record, str) \
                and record.strip():
            return "room:" + record.strip()
    return None


def span_pairings(sd, sc=None):
    """Each span's records, grouped by the place they happen.

    `{span_id: {place_token: [(path, channel, record), ...]}}`, and a record
    the engine cannot place is left out rather than parked under a guess.

    This is the join the folds in this tree never had. Every one of them
    matches on a name, an alias or a head noun -- `resolve_garment('coat',
    ['coat rack'])` matches on the head noun, as its own comment admits --
    because until the span id existed there was nothing else to match on.
    Span plus place is two engine-issued facts, and it narrows an identity
    question from the whole scene to one event in one place.
    """
    out = {}
    for span_id, rows in span_records(sd).items():
        placed = {}
        for path, channel, record in rows:
            token = _record_place(path, channel, record, sd, sc)
            if token:
                placed.setdefault(token, []).append((path, channel, record))
        if placed:
            out[span_id] = placed
    return out


#: Which hand owns each delegated channel, for the "most relevant authority"
#: rung. Filled from `director_scopes` by the caller rather than imported, so
#: this module keeps no second opinion about the partition.
#: What a record says a thing IS, as opposed to how it stands right now. Kept
#: in step with `world.spatial_merge._ENTITY_STRUCTURAL_FIELDS`, which is the
#: same question one layer down; a field this list lacks is one a fold can
#: silently drop.
_DURABLE_RECORD_FIELDS = (
    "kind", "subtype", "name", "description", "aliases", "interior_rooms",
    "portable", "container", "ubiquitous", "parent_entity", "interior_spec",
    "enclosure", "light_source", "light_shape", "light_height",
    "material", "scent", "sound", "reliable", "worn_by", "garment",
)


def apply_item_transforms(sd, survivors):
    """Fold each numbered thing's duplicates onto the record allowed to exist.

    Mutates `sd`: the survivor gains every durable field its duplicates
    carried and it lacked, in chronological order, and the duplicates are
    removed from their channel so no second record of one thing survives the
    beat.

    Returns `[{item, keep, folded, gained}]` -- one row per thing actually
    reconciled, for the report. Nothing is silent: every fold in this tree is
    reported, and the stated reason is that *"the Director asked for a referent
    it did not have, and next beat it should know the answer was 'the ledger
    has it'."*

    `state` is never merged (see the module note): the survivor's own stands.
    """
    applied = []
    for item, entry in sorted((survivors or {}).items()):
        keep_path, keep_channel, keep_record = entry.get("render_from")
        folds = entry.get("duplicates") or []
        if not folds or not isinstance(keep_record, dict):
            continue
        gained, dropped = [], []
        latest_state = None
        for path, channel, record in folds:
            if not isinstance(record, dict) or channel != keep_channel:
                continue
            for field in _DURABLE_RECORD_FIELDS:
                if keep_record.get(field) not in (None, "", [], {}):
                    continue
                value = record.get(field)
                if value in (None, "", [], {}):
                    continue
                keep_record[field] = value
                gained.append(field)
            # STATE COMES FROM THE LATEST TRANSFORM, whole. The folds arrive in
            # chronological order, so the last one holding a state is the most
            # recent thing said about how this object stands -- and a crate
            # that was opened this beat must not keep the shut snapshot it
            # stood as. Never deep-merged, for the reason the tree already
            # gives: state describes a single instant, so folding a stale
            # snapshot into a fresh one manufactures the contradiction.
            if isinstance(record.get("state"), dict) and record["state"]:
                latest_state = record["state"]
            if _drop_record_at(sd, path):
                dropped.append(path)
        if latest_state is not None:
            keep_record["state"] = latest_state
            gained.append("state")
        if gained or dropped:
            applied.append({"item": item, "keep": keep_path,
                            "folded": dropped, "gained": sorted(set(gained))})
    return applied


def _drop_record_at(sd, path):
    """Remove one record from the merged diff by its dotted path.

    Returns whether anything was removed. A path this cannot resolve is left
    alone rather than guessed at -- the walk that produced it and the walk that
    undoes it must agree, and where they do not the honest outcome is a
    duplicate that survives and is reported, never a neighbour deleted.
    """
    parts = str(path or "").split(".")
    if len(parts) < 2:
        return False
    channel = (sd or {}).get(parts[0])
    key = parts[1]
    if key.endswith("]") and "[" in key:
        name, _, index = key.partition("[")
        rows = channel.get(name) if isinstance(channel, dict) else None
        if isinstance(channel, list) and not name:
            rows = channel
        try:
            position = int(index.rstrip("]"))
        except ValueError:
            return False
        if isinstance(rows, list) and 0 <= position < len(rows):
            rows.pop(position)
            return True
        return False
    if isinstance(channel, dict) and key in channel:
        channel.pop(key)
        return True
    return False


# ---------------------------------------------------------------------------
# THE CAUSALITY RECOMPILER
#
# The owner's name for it, 2026-09-10: "basically we are making a causality
# recompiler after our director deciphers and resolves", serving the thesis
# "a system that can decipher any arbitrarily long series of events by a
# player or character and resolve it properly with proper respect to
# chronology and space. Even though its disecting and feeding it to paralel
# agents."
#
# The Director DECIPHERS the input into numbered spans; the five hands RESOLVE
# them in parallel, each blind to the others and to a scene that has not moved
# since before the beat; this puts the beat back together.
#
# Everything below reads only identifiers the engine or the Director ISSUED.
# Nothing reads prose, which is what makes the whole of it answerable without
# a model -- and it is why the ids exist at all:
#
#   WHEN   the chronological span number     `_span_items`
#   WHOM   the record's subject, its key under the channel
#   WHERE  a room or a doorway               `_record_place`
#   WHICH  the Director's item number        `_beat_item_refs`
#
#   span_records        which records are one EVENT's outcome
#   span_pairings       which are in one PLACE; span_colocations, by room
#   beat_item_records   which are one THING, across spans
#   item_survivors      which record an object is rendered FROM, and what
#                       else is true of it
#   apply_item_transforms  the chosen record receives every transform, in
#                       chronological order
#   span_slices         the beat cut into its spans
#   beat_worlds         the world as it stood BEFORE each span, which is what
#                       lets a pure FOV layer answer about the world an
#                       observer was standing in rather than the one the beat
#                       left behind
#   beat_ledger         all of it as one flat, queryable table
#
# What it deliberately does not do is DECIDE an identity. It bounds the
# question -- one event, one place, one number -- and the folds that decide
# are per-pair and belong to whoever owns those two channels. The measured
# cost of treating a grouping as a decision is in this tree already: an alias
# overlap folded some boards into a satchel, and a story's containment ledger
# sat empty for twenty beats.
# ---------------------------------------------------------------------------


def declared_elements(interp, declarations):
    """`{phase_event_id: element}` for every act anyone DECLARED this beat.

    The player's own sequence and each character's, in one index. These are the
    elements `norm_sequence` built and `assign_event_ids` stamped, so they
    carry `observable` -- the intent-free outward surface an onlooker is
    entitled to -- rather than anybody's later description of them.
    """
    index = {}
    groups = [(interp or {}).get("sequence") or []]
    for declaration in (declarations or []):
        if isinstance(declaration, dict):
            groups.append(declaration.get("sequence") or [])
    for group in groups:
        for element in group:
            if not isinstance(element, dict):
                continue
            key = str(element.get("event_id") or "").strip()
            if key and key not in index:
                index[key] = element
    return index


def beat_timeline(resolved, interp, declarations):
    """The beat as one ordered list, each entry paired with what was declared.

    `[{"order", "actor", "element", "declared", "category", "note"}]` in the
    author's order -- which is the beat's chronology, because the sheet asks
    for "one element for EVERYTHING that happened, in the order it happened".

    `declared` is the element the author CITED (`from_declaration`), or None
    for something nobody declared: a consequence, a thing the world did back.
    A reader that renders to an onlooker takes the surface from `declared`
    where there is one, and only falls to the author's own words where nothing
    was declared -- which is the whole point of the citation, and the reason
    this returns the pair rather than a merged row.
    """
    index = declared_elements(interp, declarations)
    timeline = []
    for order, element in enumerate((resolved or {}).get("sequence") or []):
        if not isinstance(element, dict):
            continue
        cited = str(element.get("from_declaration") or "").strip()
        timeline.append({
            "order": order,
            "actor": str(element.get("actor") or ""),
            "element": element,
            "declared": index.get(cited),
            "category": element.get("category"),
            "note": element.get("note"),
        })
    return timeline


def mover_cut_events(out, diff=None):
    """`{body: phase_event_id}` -- the declared event that moved each body.

    `out` is the output whose `sequence` the perception stream was built from
    (the player's declaration); `diff` the beat's own diff, defaulting to
    `out["state_assertions"]`, whose `phase_sources` says which span carried
    each position change.

    Feeds `world.spatial.beat_movement_cuts(..., moved_at=...)`, which grades
    every event against where bodies were WHEN IT HAPPENED. A body this cannot
    speak for is left to that function's own heuristic, unchanged.
    """
    if not isinstance(out, dict):
        return {}
    if diff is None:
        diff = out.get("state_assertions")
    sources = (diff or {}).get("phase_sources") \
        if isinstance(diff, dict) else None
    if not isinstance(sources, dict) or not sources:
        return {}

    position_of = {}
    for span in _span_items(out):
        try:
            span_id = int(span.get("event_id") or 0)
        except (TypeError, ValueError):
            continue
        where = span.get("_from_position")
        if span_id > 0 and isinstance(where, int):
            position_of[span_id] = where

    sequence = [element for element in (out.get("sequence") or [])
                if isinstance(element, dict)]
    cuts = {}
    for path, source in sources.items():
        channel, _dot, subject = str(path or "").partition(".")
        if channel != "positions" or not subject:
            continue
        try:
            span_id = int(source)
        except (TypeError, ValueError):
            continue
        where = position_of.get(span_id)
        if where is None or not (0 <= where < len(sequence)):
            continue
        phase_id = str(sequence[where].get("event_id") or "").strip()
        if phase_id:
            cuts[subject] = phase_id
    return cuts


def single_span_attributions(sd, dispatch, view, span_slice_of):
    """`{path: span_id}` for records a hand handed ONE span left uncited.

    `span_slice_of(name, view)` is the caller's slicer
    (`_specialist_span_slice`), passed in so this module keeps no second
    opinion about which spans a hand received.

    Returns sidecar additions in `phase_sources`' own spelling
    (`"<channel>.<key>"`, `"<channel>.<index>"` for a list), which is what
    `span_slices` and `prune_blocked_phase_changes` both already read. Writes
    nothing: the caller merges them, so a beat can see what was derived.

    This is what lets a MOVEMENT be placed in the beat's order. `positions` is
    `dict[str, str]` and a body's position is a bare string with nowhere to
    carry a citation, so without this the recompiler's three-link case --
    mint a room, walk into it, mint a thing inside it -- depends on a hand
    having remembered a sidecar it fills at a measured 25%.
    """
    additions = {}
    existing = set((sd or {}).get("phase_sources") or {})
    for name, state in (dispatch or {}).items():
        if not (state or {}).get("ran"):
            continue
        spans = span_slice_of(name, view or {})
        if len(spans) != 1:
            continue
        try:
            span_id = int(spans[0].get("event_id") or 0)
        except (TypeError, ValueError):
            continue
        if span_id <= 0:
            continue
        for channel in (state.get("channels") or ()):
            content = (sd or {}).get(channel)
            if isinstance(content, dict):
                for key, value in content.items():
                    path = "%s.%s" % (channel, key)
                    if path in existing or _cites_a_span(value):
                        continue
                    additions[path] = span_id
            elif isinstance(content, list):
                for index, value in enumerate(content):
                    path = "%s.%s" % (channel, index)
                    if path in existing or _cites_a_span(value):
                        continue
                    additions[path] = span_id
    return additions


def _cites_a_span(record):
    """Does this record already say which span it settles?"""
    if not isinstance(record, dict):
        return False
    raw = record.get("from_event")
    return (not isinstance(raw, bool) and isinstance(raw, (int, float))
            and int(raw) > 0)


def span_mint_rooms(sd, spans, worlds, final_world, actor_of=None):
    """Where a thing minted by a span was, from where its actor stood.

    `worlds` is `beat_worlds`' output and `final_world` the scene the whole
    beat leaves. `actor_of(span)` names the body whose act the span was; a span
    naming none falls to the beat's own actor, which the caller supplies by
    closing over it.

    Returns `{entity_key: room_id}` for mints this can speak for, and writes
    NOTHING -- placement is `world/spatial_containment`'s, and its rule that an
    explicit write outranks a derivation is the right one. This only supplies
    the evidence nothing else has: the world moved DURING the beat, and the
    hand that minted the thing was looking at the world as it stood before it.
    """
    minted = {key for key, value in ((sd or {}).get("entities") or {}).items()
              if isinstance(value, dict)}
    if not minted:
        return {}
    placed = (sd or {}).get("positions") or {}
    # The world each span LEAVES: the next span's `before`, and the beat's
    # final scene for the last of them.
    leaves, order = {}, [span for span, _w in (worlds or [])]
    for index, (span_id, _before) in enumerate(worlds or []):
        leaves[span_id] = (worlds[index + 1][1]
                           if index + 1 < len(worlds) else final_world)

    rooms = {}
    for span in (spans or []):
        if not isinstance(span, dict):
            continue
        try:
            span_id = int(span.get("event_id") or 0)
        except (TypeError, ValueError):
            continue
        world = leaves.get(span_id)
        if not world:
            continue
        actor = str((actor_of(span) if actor_of else span.get("actor")) or "")
        if not actor:
            continue
        room = ((world.get("positions") or {}).get(actor) or "").strip()
        if not room or room not in (world.get("rooms") or {}):
            continue
        for key, record in ((sd or {}).get("entities") or {}).items():
            if not isinstance(record, dict) or key in placed or key in rooms:
                continue
            try:
                cited = int(record.get("from_event") or 0)
            except (TypeError, ValueError):
                cited = 0
            if cited == span_id:
                rooms[key] = room
    return rooms


#: WHICH HAND IS THE AUTHORITY for a thing minted more than once in one beat,
#: highest first. Ordered by how much of a thing's OWN identity the hand's
#: channels carry, as against facts ABOUT a thing that already has one:
#: `entities` IS a thing's identity record and `rooms` is a place's, while
#: `attire` names a garment as worn, contact names relations between things
#: that already have records, and social names what minds hold true about them.
#:
#: It exists because the ladder's "the channel's own hand" rung cannot
#: discriminate -- the partition is disjoint, so every record is already in its
#: own hand's channel -- and without this the tiebreak ordered two mints of one
#: thing BY PATH, which let "entities" beat "rooms" on the letter e.
#:
#: A table the engine owns and can enumerate, which is what makes it a schema
#: rather than a vocabulary guess (CLAUDE.md's distinction). Case by case is
#: still open: a beat that mints a PLACE should rank `spatial` first, and this
#: does not yet ask what kind of thing it is -- it is written down so that
#: question has ONE place to be answered when it has been measured.
_MINT_AUTHORITY = ("objects", "spatial", "body", "contact", "social")


def mint_authority_rank(hand):
    """How authoritative this hand's mint is, lower being higher authority."""
    name = str(hand or "")
    return (_MINT_AUTHORITY.index(name) if name in _MINT_AUTHORITY
            else len(_MINT_AUTHORITY))


def item_survivors(sd, spans, sc=None, channel_owner=None):
    """For each numbered thing: which record survives, and what folds onto it.

    Returns
    `{item_id: {"name", "render_from", "duplicates", "other_facts", "reason"}}`.

      * `render_from` -- the record the object is rendered and referenced FROM,
        chosen by the ladder and then by `_MINT_AUTHORITY`. It is not a claim
        that the others are lesser truths.
      * `duplicates` -- records in the SAME channel, chronologically. The only
        group that folds: the partition is disjoint, so these are one hand's
        two attempts at one thing, and the chosen record receives their
        transforms.
      * `other_facts` -- the object's other true records, in other channels.
        An entity and its interior are TWO SEPARATE FACTS ABOUT ONE OBJECT and
        NEITHER IS DISCARDED. Which field joins them is per-pair knowledge, so
        they are named and never merged here.
      * `reason` -- which rung of the ladder chose it.

    Only things with more than one record are returned; one record is not a
    reconciliation.
    """
    owner_of = dict(channel_owner or {})
    standing = set()
    for key in ("entities", "rooms", "positions"):
        source = (sc or {}).get(key)
        if isinstance(source, dict):
            standing.update(str(name) for name in source)

    def rung(row):
        path, channel, _record = row
        subject = str(path).split(".")[1].split("[")[0] \
            if "." in str(path) else ""
        if subject and subject in standing:
            return 0                      # stood before this beat
        if owner_of.get(str(channel)):
            return 1                      # the channel's own hand minted it
        return 2                          # everything else

    def order(row):
        path, _channel, record = row
        try:
            when = int((record or {}).get("from_event") or 0)
        except (TypeError, ValueError):
            when = 0
        return (when, str(path))

    def authority(row):
        """The hand's rank, then the beat's order, then the path.

        Rank FIRST: two hands minting one thing is the case this decides, and
        ordering them by when they happened to be written would let the beat's
        phrasing pick which record is the thing.
        """
        _path, channel, _record = row
        return (mint_authority_rank(owner_of.get(str(channel))),) + order(row)

    out = {}
    for item, entry in beat_item_records(sd, spans, sc).items():
        rows = list(entry.get("records") or [])
        if len(rows) < 2:
            continue
        ranked = sorted(rows, key=lambda row: (rung(row),) + authority(row))
        keep = ranked[0]
        rest = sorted(ranked[1:], key=order)
        out[item] = {
            "name": entry.get("name") or "",
            "render_from": keep,
            "duplicates": [row for row in rest if row[1] == keep[1]],
            "other_facts": [row for row in rest if row[1] != keep[1]],
            "reason": ("standing", "owning_hand", "first_written")[rung(keep)],
        }
    return out


def beat_item_records(sd, spans, sc=None):
    """`{item_id: {name, spans, records}}` -- the beat's numbered things.

    `records` is every record any hand wrote for any span that named the item,
    which is why this can see what no single hand could: a thing minted in one
    span and acted on in another, by a different hand, from a payload that
    showed the scene as it stood BEFORE either.

    `name` is the first non-empty name the Director gave the number, kept for
    matching a record to the thing; the NUMBER is the identity, because across
    34 measured Director calls the same model wrote `sword_belt` and `sword
    belt` for one object.

    A span carrying no `_items` contributes nothing -- the ordinary case, and
    the reason this costs nothing on a beat that mints no new thing.
    """
    by_span = span_records(sd)
    items = {}
    for span in (spans or []):
        if not isinstance(span, dict):
            continue
        try:
            span_id = int(span.get("event_id") or 0)
        except (TypeError, ValueError):
            continue
        for ref in span.get("_items") or []:
            if not isinstance(ref, dict):
                continue
            number = ref.get("id")
            if not isinstance(number, int) or number <= 0:
                continue
            entry = items.setdefault(
                number, {"name": "", "spans": [], "records": []})
            if not entry["name"] and str(ref.get("name") or "").strip():
                entry["name"] = str(ref["name"]).strip()
            if span_id and span_id not in entry["spans"]:
                entry["spans"].append(span_id)
                entry["records"].extend(by_span.get(span_id) or [])
    return items


def span_colocations(sd, sc=None):
    """Each span's records grouped by the ROOM they happen in or border.

    `{span_id: {room_id: [(path, channel, record), ...]}}`. A way belongs to
    both rooms it joins, because a doorway is in each of them -- which is what
    lets the thing standing in a room meet the doorway it was fitted to.

    The coarser sibling of `span_pairings`, and the one a reconciler wants: a
    padlock in the forge and the forge door are one event in one place, and
    until the span id and this grouping existed there was no way to ask that
    question except by matching their names.
    """
    grouped = {}
    for span_id, places in span_pairings(sd, sc).items():
        rooms = {}
        for token, rows in places.items():
            if token.startswith("room:"):
                rooms.setdefault(token[5:], []).extend(rows)
            elif token.startswith("way:"):
                for room in token[4:].split("|"):
                    if room:
                        rooms.setdefault(room, []).extend(rows)
        if rooms:
            grouped[span_id] = rooms
    return grouped


def span_result_findings(sd, spans, dispatch, owners_of):
    """What does not add up about each span's assembled result.

    `spans` is this stage's work items, `dispatch` the per-hand record carrying
    `events_resolved`, and `owners_of` the callable that says which hands own a
    span (`span_owners` -- passed in rather than imported, because
    `director_scopes` owns that table and this module must not grow a second
    opinion about it).

    Returns a list of `{event_id, kind, hand, detail}`, most specific first.
    Empty is the ordinary beat.
    """
    by_span = span_records(sd)
    channel_owner = {}
    for hand, state in (dispatch or {}).items():
        for channel in (state or {}).get("channels") or ():
            channel_owner[str(channel)] = hand

    findings = []
    for span in (spans or []):
        if not isinstance(span, dict):
            continue
        try:
            span_id = int(span.get("event_id") or 0)
        except (TypeError, ValueError):
            continue
        if span_id <= 0:
            continue
        owners = [hand for hand in (owners_of(span) or [])]
        rows = by_span.get(span_id) or []
        wrote = {}
        for _path, channel, _record in rows:
            hand = channel_owner.get(str(channel))
            wrote.setdefault(hand, []).append(_path)

        for hand, paths in wrote.items():
            if hand is None:
                findings.append({
                    "event_id": span_id, "kind": "unowned_channel",
                    "hand": None, "detail": sorted(paths)[:4]})
            elif hand not in owners:
                findings.append({
                    "event_id": span_id, "kind": "written_by_non_owner",
                    "hand": hand, "detail": sorted(paths)[:4]})

        for hand in owners:
            state = (dispatch or {}).get(hand) or {}
            if not state.get("ran"):
                continue
            verdict = ""
            for row in state.get("events_resolved") or []:
                if isinstance(row, dict) and row.get("event_id") == span_id:
                    verdict = str(row.get("status") or "")
            if verdict in ("encoded",) and hand not in wrote:
                findings.append({
                    "event_id": span_id, "kind": "settled_and_silent",
                    "hand": hand, "detail": verdict})
            elif not verdict and hand not in wrote:
                findings.append({
                    "event_id": span_id, "kind": "owned_and_untouched",
                    "hand": hand, "detail": ""})
    return findings


def beat_worlds(sc, sd, apply_diff):
    """The scene as it stood BEFORE each span, in the beat's own order.

    `apply_diff(scene, diff) -> scene` is passed in rather than imported --
    `world.spatial.merge_scene_with_diff` is the caller's to supply, and this
    module must not grow an opinion about how a diff lands.

    Returns `[(span_id, scene_before_it)]`, ascending. The scene handed back
    for span k has every earlier span applied and NOT span k itself, which is
    the world an observer was standing in when span k happened -- so
    `body_visibility(scene, ...)` at that point answers about the world as it
    was, not as the beat left it.

    The unattributed slice is folded in before the first span (see the module
    note) and is never a span of its own: it happened at no point in the order.
    """
    slices, loose = span_slices(sd)
    world = apply_diff(sc or {}, loose) if loose else copy.deepcopy(sc or {})
    worlds = []
    for span_id in sorted(slices):
        worlds.append((span_id, world))
        world = apply_diff(world, slices[span_id])
    return worlds


def beat_ledger(sd, spans=None, sc=None):
    """The beat as a flat, queryable table -- one row per record.

    `[{when, whom, where, channel, path, item, record}]`, sorted by `when`
    then `path` so the order is the beat's own and never a hand's return
    order.

      * `when`  -- the span number, or 0 for a record citing none.
      * `whom`  -- the subject the record is keyed under (`poses.Corin` ->
                   "Corin"), which is what a channel's key MEANS in every
                   delegated channel.
      * `where` -- the place token, or None where the engine cannot say.
      * `item`  -- the Director's number for the thing, when the span that
                   produced this record named exactly one; several numbered
                   things in one span leave it None rather than guessing
                   which record is which.

    Nothing here is read out of prose. Every field is something the engine or
    the Director issued as an identifier, which is what makes the question
    answerable without a model.
    """
    by_span_items = {}
    for span in (spans or []):
        if not isinstance(span, dict):
            continue
        try:
            span_id = int(span.get("event_id") or 0)
        except (TypeError, ValueError):
            continue
        refs = [ref for ref in (span.get("_items") or [])
                if isinstance(ref, dict) and isinstance(ref.get("id"), int)]
        if span_id and len(refs) == 1:
            by_span_items[span_id] = refs[0]["id"]

    rows = []
    for span_id, records in span_records(sd).items():
        for path, channel, record in records:
            parts = str(path).split(".")
            subject = parts[1].split("[")[0] if len(parts) > 1 else ""
            rows.append({
                "when": span_id,
                "whom": subject,
                "where": _record_place(path, channel, record, sd, sc),
                "channel": channel,
                "path": path,
                "item": by_span_items.get(span_id),
                "record": record,
            })
    return sorted(rows, key=lambda row: (row["when"], row["path"]))


def span_slices(sd):
    """`({span_id: diff}, unattributed_diff)` -- the beat, cut into its spans.

    Each diff carries only records citing that span, in its channel's own
    shape, so it can be applied to a scene exactly as the whole diff would be.
    `unattributed` holds what cited nothing: it belongs to no point in the
    beat's order, and a caller that needs a total world must decide which end
    it lands at.

    Applied in span order, the slices reconstruct the beat -- which is what
    makes "the world as it stood at span k" a thing the engine can produce
    without asking anyone.
    """
    def cited(record):
        if not isinstance(record, dict):
            return 0
        raw = record.get("from_event")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            return 0
        return int(raw) if int(raw) > 0 else 0

    # THE SIDECAR, for records that cannot carry a citation of their own.
    # `positions` is `dict[str, str]`, so a body's position is a bare string
    # with nowhere to put one -- and a beat's movements are exactly what a
    # replay must order, because whether a mind heard a line turns on which
    # room the speaker was in AT THAT MOMENT.
    sidecar = {}
    for path, source in ((sd or {}).get("phase_sources") or {}).items():
        try:
            number = int(source)
        except (TypeError, ValueError):
            continue
        if number > 0:
            sidecar[str(path)] = number

    slices, loose = {}, {}

    def bucket(span_id):
        return slices.setdefault(span_id, {}) if span_id else loose

    for channel, content in (sd or {}).items():
        if channel in ("phase_sources", "resolved_events", "notes"):
            continue
        if isinstance(content, list):
            for index, record in enumerate(content):
                where = cited(record) or sidecar.get(
                    "%s.%s" % (channel, index), 0)
                bucket(where).setdefault(channel, []).append(record)
        elif isinstance(content, dict):
            for key, value in content.items():
                if isinstance(value, list):
                    # A dict of lists: `rooms.<id>.adjacent` is the shape this
                    # is for, so the containing record is carried along with
                    # whichever of its rows cite the span.
                    for row in value:
                        where = bucket(cited(row)).setdefault(channel, {})
                        where.setdefault(key, []).append(row)
                elif isinstance(value, dict):
                    span_id = cited(value) or sidecar.get(
                        "%s.%s" % (channel, key), 0)
                    # SPLIT, NEVER DUPLICATE. `rooms.<id>` holds `name` and
                    # `desc` beside an `adjacent` LIST whose rows cite their
                    # own spans. Filing the whole record in one bucket AND
                    # distributing its rows applies the same edge twice when
                    # the slices are replayed in order.
                    fields = {k: v for k, v in value.items()
                              if not isinstance(v, list)}
                    rowsets = {k: v for k, v in value.items()
                               if isinstance(v, list)}
                    if fields or not rowsets:
                        bucket(span_id).setdefault(
                            channel, {})[key] = fields or value
                    for field, rows in rowsets.items():
                        for row in rows:
                            row_span = cited(row) or span_id
                            holder = bucket(row_span).setdefault(
                                channel, {}).setdefault(key, {})
                            if isinstance(holder, dict):
                                holder.setdefault(field, []).append(row)
                else:
                    # A scalar: its own record cannot cite anything, so the
                    # sidecar is the only thing that can place it in the beat.
                    bucket(sidecar.get("%s.%s" % (channel, key), 0)).setdefault(
                        channel, {})[key] = value
    return slices, loose


def span_records(sd):
    """THE SPAN'S RESULT: every record citing each span, with where it lives.

    Returns `{span_id: [(path, channel, record), ...]}`, path being the dotted
    route into the merged diff (`entities.padlock`, `rooms.forge.adjacent[0]`)
    and channel the delegated channel it sits in -- which is what says WHICH
    HAND wrote it, since the channel partition is disjoint.

    A span routed to several hands is settled in several channels, and until
    this existed the halves were only ever reachable one channel at a time. So
    the folds this codebase has accumulated are all per-PAIR and all match on
    names, aliases and head nouns; none of them could ask the question the id
    makes exact -- *which records are this one event's outcome*.

    Walks the three shapes a delegated channel takes, and no deeper (`depth >
    3`): a record dict keyed by subject, a list of ops, and a dict of lists.

    IT IDENTIFIES THE EVENT AND NOT THE OBJECT, which is the whole of what it
    can promise. The apron and the hook both cite the span that hung one on the
    other. Grouping by id bounds an identity question to one event's records
    instead of the whole scene; deciding it is still the caller's, and the
    over-merges this tree has measured are all decisions, never groupings.
    """
    found = {}

    def walk(value, channel, path, depth=0):
        if depth > 3:
            return
        if isinstance(value, dict):
            raw = value.get("from_event")
            if isinstance(raw, (int, float)) and not isinstance(raw, bool) \
                    and int(raw) > 0:
                found.setdefault(int(raw), []).append((path, channel, value))
            for key, inner in value.items():
                if key == "from_event":
                    continue
                walk(inner, channel, f"{path}.{key}" if path else str(key),
                     depth + 1)
        elif isinstance(value, list):
            for index, inner in enumerate(value):
                walk(inner, channel, f"{path}[{index}]", depth + 1)

    for channel, content in (sd or {}).items():
        if channel in ("phase_sources", "resolved_events", "notes"):
            continue
        walk(content, channel, str(channel))
    return found


def _cited_event_ids(sd):
    """Every chunk id the diff's own records claim to be resolving.

    A projection of `span_records`, not a second walker: two walkers over one
    field are how the two of them come to disagree about which shapes a channel
    takes, and this file already carries three notes about that failure.

    This is the id half of `DESIGN_SPECIALIST_CONTRACT.md` section 4b. A hand
    that names the chunk it resolved makes reconciliation an exact lookup;
    everything below this still runs unchanged for records that name nothing,
    which is every record written before the field existed and every standing
    record refreshed on its own account.
    """
    return set(span_records(sd))


def _evidence_present(sd, omission, forms=None, *, scene=None):
    """CATEGORY-AWARE evidence check: is the omission's subject touched in
    the RIGHT dimension of the diff, not merely mentioned somewhere? This is
    what closes the partial-encoding trap -- a room whose desc was updated
    but whose narrated adjacency change was dropped passes bare containment
    yet fails the 'adjacency' evidence class. Unknown/other categories fall
    back to the shallow containment check.

    `scene` is the beat's ONSET scene, and only the two location-bearing
    classes read it (see `_subject_is_somewhere`). Omitted, those two keep
    their old, looser answer -- so a caller that has no scene degrades to the
    behaviour it had rather than to a wrong one."""
    # THE ID WINS WHEN THERE IS ONE. A record that names the chunk it
    # resolves has settled the question by construction, and no comparison of
    # two spellings of the same change can improve on it. Measured
    # 2026-09-09 (`tools/echo_derivable.py`): the text-based check below
    # disagrees with the hands' own verdicts on 29.8% of 329 events, which is
    # the distance between a conservative verifier and an oracle. An id has no
    # such distance.
    #
    # Additive on purpose: a record naming nothing falls through to exactly
    # the check that ran before, so this is safe to land ahead of the
    # `sequence` migration rather than with it.
    try:
        wanted = int(omission.get("event_id") or 0)
    except (TypeError, ValueError):
        wanted = 0
    if wanted and wanted in _cited_event_ids(sd):
        return True

    category = _normalize_omission_category(omission.get("category"))
    subject = omission.get("subject")
    hits = _make_subject_hit(subject, forms)

    def room_hit_with_adjacency():
        # THE SUBJECT OF AN ADJACENCY CHANGE IS USUALLY THE DOORWAY, NOT THE
        # ROOM, and a doorway's identity in this channel is an anchor key
        # (`_room_anchor_hit`). Without that arm the three ways a manifest
        # spells this beat -- `door`, `barrier`, `portal`, which the aliases
        # fold onto `adjacency` and `transit` -- all reported a perfectly
        # encoded door as unencoded, because they looked for a ROOM called
        # "fire_egress_door" and there is never one.
        #
        # Measured twice, both in chat 117 and both the same shape. Turn 21
        # was fixed in `_omission_subject_encoded` alone; turn 44 came back
        # through the category-aware reader, which is the one the manifest
        # path actually uses: the objects hand declined the door as
        # spatial's, spatial encoded
        # `rooms.upper_service_core_riser_9.adjacent[].barrier = open_door`
        # with the door under `anchors.fire_egress_door`, and the beat still
        # warned that objective state might be stale. It was not; the reader
        # was.
        #
        # Still ANDed with `adjacent`, which is what keeps it evidence: the
        # room's edges changed this beat AND it holds a fixture the subject
        # names. A room merely redescribed does not acquit an edge claim.
        #
        # AND THE FIXTURE IS LOOKED FOR IN THE SCENE, not only in the diff.
        # A door that is merely OPENED OR SHUT changes the edge and nothing
        # about the doorway itself, so a correct beat restates no anchors --
        # and this arm, reading anchors out of the diff alone, could never
        # find the fixture that names the subject. Third time in this chat
        # (turn 21, turn 44, turn 110): spatial encoded
        # `rooms.upper_service_core_riser_20.adjacent[].barrier =
        # closed_door` on both sides, the door stood in the scene's
        # `anchors.fire_door`, and the beat still warned that objective state
        # might be stale after buying a self-repair retry. The edges are
        # still what makes it evidence; the scene only answers WHICH DOORWAY
        # this room has, which is not a fact this beat had any reason to
        # rewrite.
        scene_rooms = (scene or {}).get("rooms") or {}
        for key, rd in (sd.get("rooms") or {}).items():
            if not isinstance(rd, dict) or not rd.get("adjacent"):
                continue
            if hits(key) or hits(rd.get("name")) or _room_anchor_hit(rd, hits):
                return True
            if _room_anchor_hit(scene_rooms.get(key), hits):
                return True
        return False

    def removal_edge_hit():
        for edge in (sd.get("remove_adjacent") or []):
            if isinstance(edge, dict) and (hits(edge.get("room"))
                                           or hits(edge.get("to"))):
                return True
        return False

    def entity_transit_hit():
        for eid, ed in (sd.get("entities") or {}).items():
            named = hits(eid) or (isinstance(ed, dict) and (
                hits(ed.get("name"))
                or any(hits(a) for a in (ed.get("aliases") or []))))
            if named and _entity_state_has_transit(ed):
                return True
        return False

    if category == "time":
        return sd.get("time") is not None
    if category == "stations":
        # Sixteen resolves across the database asserted a station change in
        # changes_asserted and encoded it nowhere, and the shallow containment
        # fallback marked every one of them covered. Moving to a different
        # ROOM counts too: that is a position change, and it carries the
        # within-room one with it.
        return any(hits(k) for k in (sd.get("stations") or {})) \
            or any(hits(k) for k in (sd.get("positions") or {}))
    if category == "poses":
        return any(hits(k) for k in (sd.get("poses") or {}))
    if category == "scales":
        # THE PARTIAL-ENCODING TRAP, for the magnitude channel. Both this
        # category and `containment` were reachable -- the aliases fold
        # size/scale and contained/container/enclosure onto them, and
        # `_CATEGORY_CHANNELS` routes both to the contact specialist -- yet
        # neither had an evidence class, so both fell through to the shallow
        # containment check, whose fields are rooms/entities/attire/positions/
        # poses and the op lists and which reads neither `scales` nor
        # `containment`. Measured: a manifest item asserting a size change,
        # with `sd.scales` empty and the same body present in `sd.poses`, was
        # reported ENCODED. A body being re-posed is not a record of how big
        # it now is.
        return any(hits(k) for k in (sd.get("scales") or {}))
    if category == "containment":
        # A RELEASE COUNTS, exactly as an ending condition does: the channel
        # spells "out of the pocket" as a null value under the subject's own
        # key, so the key IS the encoding. The holder's name counts too --
        # the manifest subject is as often the container as the contained.
        for subject, record in (sd.get("containment") or {}).items():
            if hits(subject):
                return True
            if isinstance(record, dict) and hits(record.get("in")):
                return True
        return False
    if category in ("adjacency", "transit"):
        if room_hit_with_adjacency() or removal_edge_hit() \
                or entity_transit_hit():
            return True
        if category == "transit":
            # An arrival encodes as the entity's own position change.
            return any(hits(k) for k in (sd.get("positions") or {}))
        return False
    if category == "rooms":
        for key, rd in (sd.get("rooms") or {}).items():
            if hits(key) or (isinstance(rd, dict) and hits(rd.get("name"))) \
                    or _room_anchor_hit(rd, hits):
                return True
        return any(hits(r) for r in (sd.get("remove_rooms") or []))
    if category == "positions":
        if any(hits(k) for k in (sd.get("positions") or {})):
            return True
        # A within-room placement is a change the model files under
        # 'positions' ("dropped from the platform edge to the stone floor")
        # while the diff legitimately encodes it as a STATION -- the room is
        # unchanged, so sd.positions is rightly silent. Live case: chat 71
        # turn 2354 v26634 carried stations {"lightweight travel jacket":
        # {at: null}} plus an inventory transfer and the entity's own state,
        # and this class reported the jacket unencoded anyway, which fed a
        # false repair and a false staleness warning. The mirror of the
        # stations class above accepting a positions hit.
        if any(hits(k) for k in (sd.get("stations") or {})):
            return True
        return any(isinstance(c, dict) and hits(c.get("who"))
                   for c in (sd.get("cast_changes") or []))
    if category == "entities":
        named = False
        for eid, ed in (sd.get("entities") or {}).items():
            if hits(eid) or (isinstance(ed, dict) and (
                    hits(ed.get("name"))
                    or any(hits(a) for a in (ed.get("aliases") or [])))):
                named = True
                break
        if not named:
            return any(hits(e) for e in (sd.get("remove_entities") or []))
        # A MINT IS NOT A PLACEMENT. The channel says a noun exists; where it
        # is lives in `positions`, which this channel's owner cannot write.
        return True if scene is None \
            else _subject_is_somewhere(sd, scene, subject, hits, forms)
    if category == "conditions":
        # Any conditions entry for the subject counts, INCLUDING an ending
        # one (active:0 / expires_at set) -- 'the fire burns out' is encoded
        # by expiry, not by neglect.
        for key, cond_value in (sd.get("conditions") or {}).items():
            cond_list = cond_value if isinstance(cond_value, list) else [cond_value]
            if hits(key):
                return True
            for c in cond_list:
                if isinstance(c, dict) and (hits(c.get("subject_id"))
                                            or hits(c.get("condition_id"))):
                    return True
        return False
    if category == "attire":
        # The channel is keyed by WEARER; the manifest subject is worded
        # freely and is at least as often the GARMENT ("lightweight travel
        # jacket" -- chat 71 turn 2354 v26625, where attire.Hinami.remove
        # carried exactly that garment and this class reported it unencoded,
        # because it read only the wearer keys). Both spellings of the same
        # change must count, so the garment handles inside each wearer's
        # entry are checked too.
        for wearer, entry in (sd.get("attire") or {}).items():
            if hits(wearer):
                return True
            if not isinstance(entry, dict):
                continue
            for field in ("add", "remove"):
                for garment in entry.get(field) or []:
                    if isinstance(garment, dict):
                        garment = garment.get("name") \
                            or garment.get("garment")
                    if hits(garment):
                        return True
            for garment in list(entry.get("conditions") or {}) \
                    + list(entry.get("coverage") or {}):
                if hits(garment):
                    return True
        return False
    if category == "contacts":
        manifest_actor = str(omission.get("actor") or "").strip()
        manifest_actor_part = str(omission.get("actor_part") or "").strip()
        manifest_target = str(omission.get("target") or "").strip()
        manifest_target_part = str(omission.get("target_part") or "").strip()
        has_manifest_endpoints = bool(manifest_actor and manifest_target)
        change = str(omission.get("change") or "").casefold()
        subject_is_ledger = _norm_subject(subject) in ("contact", "contacts")

        def endpoint_matches(op):
            """Does this op encode this exact manifested contact relation?

            New outputs carry structured endpoints. Saved/weak outputs may not;
            for those, require at least one op-specific part/manner phrase in the
            manifest prose whenever the op supplies one. That conservative
            fallback may request an idempotent repair for an underspecified
            manifest, but it cannot let an unrelated contact silently stand in
            for the asserted one.
            """
            if has_manifest_endpoints:
                if not (_make_subject_hit(manifest_actor)(op.get("actor"))
                        and _make_subject_hit(manifest_target)(op.get("target"))):
                    return False
                if manifest_actor_part and _norm_subject(
                        manifest_actor_part) != _norm_subject(op.get("actor_part")):
                    return False
                if manifest_target_part:
                    part = _norm_subject(manifest_target_part)
                    # A 'cross' op relocates a standing endpoint: the ENDED
                    # contact lives in crossed_target_part, the new one in
                    # target_part, and one op encodes both halves of the
                    # transition -- the repair sheet itself prescribes it.
                    # Comparing manifests against target_part alone made the
                    # ended half uncoverable by the very op that ends it
                    # (chat 71 turn 2354 v26643).
                    if part != _norm_subject(op.get("target_part")) \
                            and part != _norm_subject(
                                op.get("crossed_target_part")):
                        return False
                return True

            if subject_is_ledger:
                return True
            discriminators = [
                str(op.get(field) or "").strip().casefold()
                for field in ("actor_part", "target_part", "manner")
                if str(op.get(field) or "").strip()
            ]
            if not discriminators:
                return True
            return any(re.search(r"\b%s\b" % re.escape(term), change)
                       for term in discriminators)

        for op in (sd.get("contact_ops") or []):
            if not isinstance(op, dict):
                continue
            # The subject gate exists for manifests with NO structured
            # endpoints, where the free-text subject is all there is to
            # anchor on. When the manifest carries endpoints, they ARE the
            # subject and endpoint_matches is the whole (stricter) test --
            # demanding the free-text subject ALSO name a participant made
            # coverage depend on wording: 'Elyra hand on Hinami stomach
            # ends' passed while 'contact_end' and 'prior hand-to-stomach
            # contact' failed against the identical ops, reroll to reroll
            # on one live beat (chat 71 turn 2354).
            if (subject_is_ledger or has_manifest_endpoints
                    or hits(op.get("actor")) or hits(op.get("target"))) \
                    and endpoint_matches(op):
                return True
        return False
    if category in ("contact_action", "contact_actions"):
        manifested_actor = str(omission.get("actor") or subject or "").strip()
        manifested_action = str(omission.get("action") or "").strip()
        manifested_ref = omission.get("contact_ref")
        for op in (sd.get("contact_action_ops") or []):
            if not isinstance(op, dict):
                continue
            if manifested_actor and not _make_subject_hit(
                    manifested_actor)(op.get("actor")):
                continue
            if manifested_action and _norm_subject(
                    manifested_action) != _norm_subject(op.get("action")):
                continue
            if manifested_ref:
                op_ref = op.get("contact_ref") or op.get("contact_id")
                if isinstance(manifested_ref, dict):
                    if not isinstance(op_ref, dict):
                        continue
                    fields = ("actor", "actor_part", "target", "target_part")
                    if any(_norm_subject(manifested_ref.get(field)) !=
                           _norm_subject(op_ref.get(field)) for field in fields):
                        continue
                elif _norm_subject(manifested_ref) != _norm_subject(op_ref):
                    continue
            return True
        return False
    if category == "substances":
        manifested_substance = str(omission.get("substance") or "").strip()
        manifested_placement = str(omission.get("placement") or "").strip()
        manifested_target = str(omission.get("target") or "").strip()
        manifested_interior = str(
            omission.get("target_interior") or "").strip()
        subject_is_ledger = _norm_subject(subject) in (
            "substance", "substances", "material")
        for op in (sd.get("substance_ops") or []):
            if not isinstance(op, dict):
                continue
            if not (subject_is_ledger or hits(op.get("source"))
                    or hits(op.get("target")) or hits(op.get("substance"))):
                continue
            if manifested_substance and _norm_subject(
                    manifested_substance) != _norm_subject(op.get("substance")):
                continue
            if manifested_target and not _make_subject_hit(
                    manifested_target)(op.get("target")):
                continue
            if manifested_placement and _norm_subject(
                    manifested_placement) != _norm_subject(op.get("placement")):
                continue
            if manifested_interior and _norm_subject(
                    manifested_interior) != _norm_subject(
                        op.get("target_interior")):
                continue
            return True
        return False
    if category == "inventory":
        named = any(
            isinstance(op, dict) and (hits(op.get("object_id"))
                                      or hits(op.get("from_id"))
                                      or hits(op.get("to_id")))
            for op in (sd.get("inventory_ops") or [])
        )
        if not named:
            return False
        # An op whose destination resolves to nothing moved nothing: the
        # merge derivation refuses it and the thing stays exactly where it
        # was, which for a thing minted this beat is nowhere at all.
        return True if scene is None \
            else _subject_is_somewhere(sd, scene, subject, hits, forms)
    if category == "cast_changes":
        if any(isinstance(c, dict) and hits(c.get("who"))
               for c in (sd.get("cast_changes") or [])):
            return True
        return any(hits(k) for k in (sd.get("positions") or {}))
    return _omission_subject_encoded(sd, subject, forms)

# Kept for its importers. It clamped `_manifest_items` to the first eight
# entries, which bounded what was DISPATCHED and CHECKED rather than what was
# repaired; the clamp is gone (see `_manifest_items`). The one deep audit and
# one self-repair per director_resolve execution are bounded by the seam's
# own control flow, not by this number.
_RECONCILE_MAX_MANIFEST_ITEMS = 8


def _beat_item_refs(listed):
    """`items` as `[{"id": int, "name": str}]`, or [].

    The Director's own numbers, kept only where a number is actually there.
    Tolerant about the shape a model reaches for -- a bare number is an id with
    no name, a bare string is a name with no number and is dropped, because a
    mention that is not numbered says nothing this exists to say.
    """
    rows = []
    for entry in (listed if isinstance(listed, (list, tuple)) else []):
        if isinstance(entry, dict):
            raw, name = entry.get("id"), entry.get("name")
        elif isinstance(entry, (int, float)) and not isinstance(entry, bool):
            raw, name = entry, ""
        else:
            continue
        try:
            number = int(raw)
        except (TypeError, ValueError):
            continue
        if number <= 0:
            continue
        row = {"id": number, "name": str(name or "").strip()}
        if row not in rows:
            rows.append(row)
    return rows


def _span_items(out):
    """The beat's DISSECTED CHUNKS, numbered by the engine.

    `sequence` is the Director's decomposition of the player's (or a
    character's) input into typed spans, and it has always been the right
    dissection -- what it lacked was a category saying which ledger family the
    span belongs to, an id, and the Director's note on how it should resolve.
    Those three make a chunk a WORK ITEM
    (`DESIGN_SPECIALIST_CONTRACT.md` section 4a).

    Numbered HERE, by the engine, in declared order -- the same rule and the
    same reason as `_manifest_items`: an id the model authored could repeat,
    skip or reorder, and every downstream use assumes a dense sequence. A
    chunk keeps whatever id it is given for the whole beat, which is what
    `from_event` on a record cites.

    Only chunks the Director CATEGORIZED become work items. A span with no
    category is still a perfectly good sequence element -- perception, the
    narrator and the floors all read it -- it simply addresses no ledger, and
    a speech act that changes nothing in the world is the ordinary case.
    """
    items = []
    for position, element in enumerate(out.get("sequence") or []):
        if not isinstance(element, dict):
            continue
        # THE RAW VALUE DECIDES, not the normalized one.
        # `_normalize_omission_category` folds a missing category onto
        # 'other', which is correct when classifying an omission the engine
        # already knows is real, and wrong here: it made every uncategorized
        # span -- a question asked, a look given -- into a work item, and so
        # would have dispatched a hand for every line of dialogue.
        raw = element.get("category")
        # ONE SPAN MAY NAME SEVERAL LEDGERS. A belt pulled off and dropped on
        # a bench is one act of the player's and two records -- the wardrobe's
        # and the object's -- so the span carries both and each hand settles
        # its own part (`DESIGN_SPECIALIST_CONTRACT.md`; per-hand acquittal in
        # `_index_addressed_events`). A string stays a string's worth of work.
        names = (raw if isinstance(raw, (list, tuple))
                 else _split_joined_categories(raw))
        categories = []
        for name in names:
            if not str(name or "").strip():
                continue
            folded = _normalize_omission_category(name)
            if folded and folded not in categories:
                categories.append(folded)
        if not categories:
            continue
        item = dict(element)
        item["categories"] = categories
        # `category` keeps the first, so a reader written before spans could
        # name two still sees the string it expects rather than a list.
        item["category"] = categories[0]
        item["event_id"] = len(items) + 1
        # WHERE IT CAME FROM, for the engine only. Player authority is settled
        # against the sequence POSITION (`claim:<index>:...`) and voiding a
        # span needs the other direction. Deriving it by re-walking the same
        # category filter somewhere else is how the filter gets two spellings,
        # which is the failure this file already carries three notes about.
        # Stripped before any payload (`_specialist_payload`): a leading
        # underscore marks a key no model ever sees.
        item["_from_position"] = position
        # THE BEAT'S OWN ITEM NUMBERS, moved out of sight. The hands must never
        # see them (the owner's constraint): they are bookkeeping for the
        # reconciler, and a number in a payload is a number the model will try
        # to cite. `_specialist_payload` strips every leading-underscore key
        # from a span, so renaming it here is the whole of the enforcement.
        listed = item.pop("items", None)
        numbered = _beat_item_refs(listed)
        if numbered:
            item["_items"] = numbered
        items.append(item)
    return items


def _split_joined_categories(raw):
    """`"objects, spatial"` as the two names it is -- or as one, untouched.

    A model told to name two families in one string field reaches for a
    separator, and the joined string folds to no known category: the span
    routes to no hand and the change is lost in silence. Splitting is safe
    here and only here, because the result is DISCARDED unless every part is
    a category the engine already ROUTES -- so a string carrying one
    unfamiliar name reaches `_unrouted_rulings` whole, echoed back to the
    Director as the thing it actually wrote, to be reported rather than
    guessed at. That is the rule `_note_key_forms` states for the sibling
    channel, and routability rather than foldability is the test because the
    fold passes an unknown name through unchanged.

    Written as a delimiter class rather than a comma alone: the separator a
    model reaches for is whichever one it reaches for, and every one of them
    is punctuation no category contains.
    """
    text = str(raw or "").strip()
    if not text:
        return [raw]
    parts = [part.strip() for part in re.split(r"[,;/|]|\band\b", text)]
    parts = [part for part in parts if part]
    if len(parts) < 2:
        return [raw]
    # EVERY part must ROUTE, not merely fold. `_normalize_omission_category`
    # passes an unknown name straight through, so a truthiness test here
    # split free prose into "categories": "the belt comes off and lands on
    # the bench" is not two ledger families, and reporting it as two is worse
    # noise than reporting it as one unknown name.
    if all(manifest_category_targets(_normalize_omission_category(part))
           for part in parts):
        return parts
    # One name the engine does not know makes the whole string one unknown
    # name, which is the honest thing for the unrouted report to receive.
    return [raw]


def voided_span_ids(out, downgrades):
    """The spans the player's authority did not cover, by their own ids.

    A downgrade names a sequence POSITION (`claim:<index>:...`); a record cites
    a SPAN id (`from_event`). This is the join between them, and it exists
    because the two id spaces are both real and neither is the other -- the
    lesson of the beat where a hand cited the phase graph because the payload
    carried two fields called `event_id`.

    An element that became no span contributes nothing: it addressed no ledger,
    so no record cites it and there is nothing to void.
    """
    positions = downgraded_sequence_indices(downgrades)
    if not positions:
        return []
    return [int(span["event_id"]) for span in _span_items(out)
            if span.get("_from_position") in positions
            and span.get("event_id")]


def void_span_records(assertions, span_ids):
    """Drop every record citing one of these spans, whichever hand wrote it.

    WHOLE, which is the owner's rule: a span may have several owners
    (`span_owners`) and voiding one hand's half while another's stands is the
    state the rule was given to end. Every owner's record cites the same span
    id, so one pass reaches all of them.

    The walker is `prune_blocked_phase_changes` unchanged -- it already drops a
    record whose cited event is dead, it already reads `from_event`, and the
    deferred-phase floor calls it the same way a few lines from the caller. A
    second walker would be a second answer to "is this record's event void".

    Returns the (path, span_id) pairs dropped, for the record that tells the
    Director what the dial refused.
    """
    if not span_ids or not isinstance(assertions, dict):
        return []
    return prune_blocked_phase_changes(
        assertions,
        [{"event_id": int(span_id), "status": "blocked"}
         for span_id in span_ids])


def _span_id_ceiling(out):
    """The highest id the chunks used, so the manifest can continue past it.

    ONE ID SPACE PER BEAT. During the migration a beat can carry both
    `sequence` chunks and a `changes_asserted` manifest, and a record's
    `from_event` names one number -- so the two lists cannot both start at 1
    or the id is ambiguous about which it points into. Chunks take 1..N and
    the manifest continues at N+1. When `changes_asserted` goes this returns
    0 for every beat and the numbering is simply 1..N.
    """
    return len(_span_items(out))


def _manifest_items(out, cast=None, scene=None):
    """director_resolve's own changes_asserted manifest, normalized to the
    seam's omission shape (source 'manifest').

    `cast`/`scene` are the beat's own register of WHO IS A BODY, read only by
    the fold below (A41): without them it cannot tell a wearer from a
    garment, so it drops no handle and folds exactly as it did before.

    Numbered here, by the ENGINE, in the order the resolve emitted them --
    which is the order it narrated them, so the ids are the beat's own
    chronology (design note 21). The model is never asked for the number:
    an id it authored could repeat, skip, or reorder, and every downstream
    use assumes the ids are a dense sequence over exactly this manifest.
    Numbering runs BEFORE the length clamp so an id always indexes the item
    a specialist was actually handed.
    """
    items = []
    raw = out.get("changes_asserted")
    for item in (raw if isinstance(raw, list) else []):
        if not isinstance(item, dict):
            continue
        change = str(item.get("change") or "").strip()
        if not change:
            continue
        normalized = {
            "category": _normalize_omission_category(item.get("category")),
            "subject": str(item.get("subject") or "").strip(),
            "change": change, "evidence": "", "source": "manifest",
            # CONTINUES PAST THE SPANS, see `_span_id_ceiling`: one id space
            # per beat, so a record's `from_event` is never ambiguous about
            # which list it points into.
            "event_id": _span_id_ceiling(out) + len(items) + 1,
        }
        # Preserve the historical public manifest shape for every non-contact
        # change; endpoint keys exist only when the model actually supplied
        # them, rather than four empty strings appearing on every item.
        #
        # `note` RIDES WITH THEM, and it is the reason this list is a list: the
        # normalized dict above is built key by key, so a field absent from it
        # is silently dropped here rather than at any boundary that would say
        # so. The Director wrote the instruction, `_specialist_manifest_slice`
        # would have carried it, and the hand would never have seen it --
        # caught 2026-09-09 only because the guard test hand-built its view and
        # bypassed this function, which is the shape of a test proving a stub.
        for field in ("actor", "actor_part", "target", "target_part",
                      "substance", "placement", "target_interior", "note"):
            value = str(item.get(field) or "").strip()
            if value:
                normalized[field] = value
        items.append(normalized)
    # RENUMBERED WITH THE SAME OFFSET. The fold closes gaps left by merged
    # entries and used to restart at 1, which silently undid the chunk offset
    # above -- ids have to be dense AND in the beat's one id space.
    items = _fold_derived_manifest_events(items, cast, scene,
                                          start=_span_id_ceiling(out) + 1)
    # NO CLAMP. Until 2026-09-07 this returned the first eight: items 9+
    # were dispatched to no hand, sliced into no specialist view and
    # checked against no evidence, so a busy beat's later changes were the
    # ones that went unencoded and unnoticed. The constant below justified
    # bounding REPAIR CALLS, which is a different quantity and is bounded
    # where the calls are made.
    return items


#: Categories whose entry may be the ENGINE'S OWN consequence of an attire
#: removal rather than a second change. A garment coming off is one event;
#: the object on the floor is what `commit._mint_shed_garments` does about
#: it, not a separate thing that happened.
_DERIVED_OF_ATTIRE = frozenset({"entities", "inventory"})


def _subject_is_registered_body(subject, cast, scene):
    """Does this manifest subject name a BODY the engine already has on file?

    The engine's own vocabulary for a body, in the two registers a beat keeps
    bodies in, because a registered character and a named background presence
    are both wearers:

      * a registered cast member, matched over the same
        `character_scene_keys` set `_subject_match_forms` resolves an
        omission subject through -- so a uid or an alias answers here
        too (a `character:<row id>` spelling is not in that set and folds
        exactly as head folded it);
      * a scene key carrying one of the three ledgers only a body carries.
        That test is `world.spatial`'s `_is_body_entity` and
        `world.comfort._is_body`, both measured across every scene on disk:
        a lift car, a ship and a crate have no attire, no scales and no
        vitals, and every body scored true on attire.

    Written for the fold below (review 2026-09-07 A41), where "does this
    handle name the wearer or the garment" is the entire question and string
    identity with the sibling entry had been standing in for the answer.
    """
    key = _norm_subject(subject)
    if not key:
        return False
    for row in cast or []:
        sheet = normalized_character_of_row(row)
        if sheet is None:
            continue
        if any(_norm_subject(k) == key for k in character_scene_keys(sheet)):
            return True
    for ledger in ("attire", "scales", "vitals"):
        table = (scene or {}).get(ledger)
        if not isinstance(table, dict):
            continue
        if any(_norm_subject(k) == key for k in table):
            return True
    return False


def _fold_derived_manifest_events(items, cast=None, scene=None, start=1):
    """One real-world change is ONE numbered event.

    The manifest may truthfully describe a single change twice -- "the sash
    is removed" (attire) and "the sash is created on the floor" (entities)
    are both true of one act. Numbered separately, they are routed to two
    different owners, and each faithfully authors its own record of the
    same garment. Measured live: five entity records for two garments, one
    beat after the previous duplication was repaired.

    So a derived entry folds into the attire event it follows from: one id,
    one owner, both categories remembered. Deterministic and engine-side,
    never a prompt rule -- the prompt half asks for one event per change,
    but a manifest is model-authored and this is the floor under it.

    Conservative by construction: only entities/inventory entries, only
    where `attire.resolve_garment` says the subject names the same garment
    as an attire entry in the SAME beat. Positions/stations/poses are
    deliberately not in this family -- those are three different facts
    about a body, not three descriptions of one.
    """
    from story.attire import resolve_garment

    attire_items = [i for i in items if i["category"] == "attire"]
    if not attire_items:
        return items
    folded = []
    for item in items:
        if item["category"] not in _DERIVED_OF_ATTIRE:
            folded.append(item)
            continue
        handles = [str(item.get("subject") or ""),
                   str(item.get("target") or "")]
        handles = [h for h in handles if h.strip()]
        parent = None
        for candidate in attire_items:
            subject = str(candidate.get("subject") or "")
            change = str(candidate.get("change") or "")
            # A BODY IS NOT A GARMENT (review 2026-09-07 A41). An attire
            # manifest entry is usually keyed by the WEARER -- that is the
            # key `_evidence_present` looks `state_diff.attire` up under --
            # so a handle that merely repeats such an entry's subject names
            # the body, and proves nothing about which garment moved.
            # Dropping it is what stops "Hinami picks up the brass lantern"
            # from folding into "Hinami removes her cloak": the lantern was
            # losing its event id, so it reached no hand, was checked
            # against no evidence, and left the manifest entirely.
            #
            # ONLY WHERE THE SUBJECT IS A BODY, and that is a question for
            # the register, never for string identity with the sibling
            # entry. The model also files an attire entry keyed by the
            # GARMENT ("silk robe / unbelted and drawn off Hinami"), and
            # there the subject is the very thing the entities entry
            # describes: measured, dropping a handle by string identity
            # alone turned {attire 'utility sash' removed from Hinami} +
            # {entities 'utility sash' created on the floor} back into two
            # events -- the duplication this fold exists to end.
            if _subject_is_registered_body(subject, cast, scene):
                subject_key = _norm_subject(subject)
                garment_handles = [h for h in handles
                                   if _norm_subject(h) != subject_key]
            else:
                garment_handles = list(handles)
            if not garment_handles:
                continue
            if any(resolve_garment(h, [subject]) for h in garment_handles):
                parent = candidate
                break
            # The attire entry usually names the wearer as subject and the
            # garment inside `change` ("utility sash removed"), which is the
            # shape the live beat produced. THE PROOF IS STILL THE RESOLVER:
            # this branch was `handle in change` prose containment, which any
            # shared substring satisfied. The head-noun tier is off because
            # it resolves any word standing alone in the phrase, which is a
            # second way a body's own name qualified as a garment.
            if change and any(
                    resolve_garment(h, [change], allow_head_noun=False)
                    for h in garment_handles):
                parent = candidate
                break
        if parent is None:
            folded.append(item)
            continue
        also = parent.setdefault("also_described_as", [])
        if item["category"] not in also:
            also.append(item["category"])
    for index, item in enumerate(folded):
        item["event_id"] = start + index
    return folded
