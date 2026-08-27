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

import json
import re

from llm import schemas
from world.spatial import (_merge_entity, _merge_room, resolve_placement_target,
                           room_of)

from .common import (
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
    for k in ("positions", "stations", "poses", "rooms", "entities", "overlays", "attire",
              "conditions", "scales", "containment", "vitals"):
        if not isinstance(sd.get(k), dict):
            sd[k] = {}
    for k in ("cast_changes", "world_facts", "introductions", "following_ops",
              "remove_entities", "remove_rooms", "remove_adjacent",
              "inventory_ops", "contact_ops", "contact_action_ops", "substance_ops", "claim_dispositions",
              "consequences", "offscreen_plan_ops", "crowd_ops",
              "telling_ops"):
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
    sd.setdefault("time", None)
    return sd


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

def _diff_is_substantive(sd):
    """True when the diff asserts any physical change at all (post-strip)."""
    for key in ("rooms", "entities", "conditions", "attire", "overlays",
                "positions", "poses", "remove_entities", "remove_rooms",
                "remove_adjacent", "inventory_ops", "contact_ops",
                "contact_action_ops", "substance_ops", "cast_changes"):
        if sd.get(key):
            return True
    return False

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
    for field in ("attire", "overlays"):
        for key, incoming in (patch.get(field) or {}).items():
            sd[field][key] = incoming
    for key, incoming in (patch.get("conditions") or {}).items():
        incoming_list = incoming if isinstance(incoming, list) else [incoming]
        incoming_list = [c for c in incoming_list if isinstance(c, dict)]
        existing = sd["conditions"].get(key)
        if isinstance(existing, list):
            existing.extend(c for c in incoming_list if c not in existing)
        else:
            sd["conditions"][key] = incoming_list
    for key, room in (patch.get("positions") or {}).items():
        sd["positions"].setdefault(key, room)
    for key, pose in (patch.get("poses") or {}).items():
        sd["poses"].setdefault(key, pose)
    # Stations add-only for the positions/poses reason: the original diff's
    # stations stand, and a partial per-entity update must never be filled
    # out with defaults that clobber the standing roster (see AGENTS.md's
    # stations row). Before this, a repair delta's stations were silently
    # dropped on the floor.
    for key, station in (patch.get("stations") or {}).items():
        sd.setdefault("stations", {}).setdefault(key, station)
    for field in ("remove_entities", "remove_rooms", "remove_adjacent",
                  "inventory_ops", "contact_ops", "contact_action_ops",
                  "substance_ops", "cast_changes", "world_facts",
                  "introductions"):
        for item in (patch.get(field) or []):
            if item not in sd[field]:
                sd[field].append(item)
    if sd.get("time") is None and patch.get("time") is not None:
        sd["time"] = patch["time"]
    return sd

def _norm_subject(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())

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
        try:
            keys = character_scene_keys(json.loads(row["sheet"]))
        except Exception:
            continue
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

def _omission_subject_encoded(sd, subject, forms=None):
    """Deterministic containment check: does ANY diff field reference this
    subject (under any identity form)? Intentionally shallow -- it verifies
    the diff addressed the subject at all, not that the encoding is
    semantically right; the Director owns the semantics. Category-agnostic
    fallback; _evidence_present is the category-aware form."""
    hits = _make_subject_hit(subject, forms)

    for field in ("rooms", "entities", "attire", "positions", "poses"):
        for key, value in (sd.get(field) or {}).items():
            if hits(key):
                return True
            if isinstance(value, dict) and hits(value.get("name")):
                return True
    for cond_value in (sd.get("conditions") or {}).values():
        cond_list = cond_value if isinstance(cond_value, list) else [cond_value]
        for c in cond_list:
            if isinstance(c, dict) and (hits(c.get("subject_id"))
                                        or hits(c.get("condition_id"))):
                return True
    for item in (sd.get("remove_entities") or []) + (sd.get("remove_rooms") or []):
        if hits(item):
            return True
    for edge in (sd.get("remove_adjacent") or []):
        if isinstance(edge, dict) and (hits(edge.get("room"))
                                       or hits(edge.get("to"))):
            return True
    for chg in (sd.get("cast_changes") or []):
        if isinstance(chg, dict) and hits(chg.get("who")):
            return True
    for op in (sd.get("inventory_ops") or []):
        if isinstance(op, dict) and (hits(op.get("object_id"))
                                     or hits(op.get("from_id"))
                                     or hits(op.get("to_id"))):
            return True
    for op in (sd.get("contact_ops") or []):
        if not isinstance(op, dict):
            continue
        if hits(op.get("actor")) or hits(op.get("target")):
            return True
        if _norm_subject(subject) in ("contact", "contacts"):
            return True
    for op in (sd.get("contact_action_ops") or []):
        if not isinstance(op, dict):
            continue
        if hits(op.get("actor")) or hits(op.get("action")):
            return True
        if _norm_subject(subject) in (
                "contactaction", "contactactions", "contacteffect"):
            return True
    for op in (sd.get("substance_ops") or []):
        if not isinstance(op, dict):
            continue
        if (hits(op.get("source")) or hits(op.get("target"))
                or hits(op.get("substance"))):
            return True
        if _norm_subject(subject) in ("substance", "substances", "material"):
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
    category = _normalize_omission_category(omission.get("category"))
    subject = omission.get("subject")
    hits = _make_subject_hit(subject, forms)

    def room_hit_with_adjacency():
        for key, rd in (sd.get("rooms") or {}).items():
            if (hits(key) or (isinstance(rd, dict) and hits(rd.get("name")))) \
                    and isinstance(rd, dict) and rd.get("adjacent"):
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
            if hits(key) or (isinstance(rd, dict) and hits(rd.get("name"))):
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

# At most one deep audit + one self-repair per director_resolve execution.
# A rerun of the stage naturally re-runs the seam once -- there is no
# cross-turn or cross-variant accumulation to double-charge.
_RECONCILE_MAX_MANIFEST_ITEMS = 8


def _manifest_items(out):
    """director_resolve's own changes_asserted manifest, normalized to the
    seam's omission shape (source 'manifest').

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
            "event_id": len(items) + 1,
        }
        # Preserve the historical public manifest shape for every non-contact
        # change; endpoint keys exist only when the model actually supplied
        # them, rather than four empty strings appearing on every item.
        for field in ("actor", "actor_part", "target", "target_part",
                      "substance", "placement", "target_interior"):
            value = str(item.get(field) or "").strip()
            if value:
                normalized[field] = value
        items.append(normalized)
    items = _fold_derived_manifest_events(items)
    return items[:_RECONCILE_MAX_MANIFEST_ITEMS]


#: Categories whose entry may be the ENGINE'S OWN consequence of an attire
#: removal rather than a second change. A garment coming off is one event;
#: the object on the floor is what `commit._mint_shed_garments` does about
#: it, not a separate thing that happened.
_DERIVED_OF_ATTIRE = frozenset({"entities", "inventory"})


def _fold_derived_manifest_events(items):
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
            names = [str(candidate.get("subject") or ""),
                     str(candidate.get("change") or "")]
            if any(resolve_garment(h, [names[0]]) for h in handles if h):
                parent = candidate
                break
            # The attire entry often names the WEARER as subject and the
            # garment inside `change` ("utility sash removed"), which is
            # the shape the live beat produced.
            if any(h and h.casefold() in names[1].casefold() for h in handles):
                parent = candidate
                break
        if parent is None:
            folded.append(item)
            continue
        also = parent.setdefault("also_described_as", [])
        if item["category"] not in also:
            also.append(item["category"])
    for index, item in enumerate(folded):
        item["event_id"] = index + 1
    return folded
