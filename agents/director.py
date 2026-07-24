"""Director agents for scene establishment, player interpretation, and resolution."""

from __future__ import annotations

import json
import random
import re

from character_schema import (
    character_abilities,
    character_appearance,
    character_name,
    character_public_history,
    persona_abilities,
    persona_appearance,
    persona_name,
    persona_public_history,
)
from db import get_setting, wget
from memory import lorebook_manifest
from paradox import paradox_visible_to
from prompts import get_prompt
from scene import (
    _ability_mod,
    appearance_of,
    cast_scene_context,
    director_context,
    fiction_model,
    get_scene,
    is_player_speaker,
    persona_of,
    sanitize_attire_items,
    senses_of,
    sheet_state,
    simulation_clock,
    style_guide,
)
from providers import Aborted
from schemas import validate_llm_output
from spatial import (
    _merge_room,
    merge_scene_with_diff,
    passable_route_exists,
    room_of,
    spatial_rel,
)

from .common import (
    _agent_json,
    _contextual_rooms,
    _dict,
    _dict_list,
    _extract_authority_claims,
    _is_mental_action,
    _list,
    _normalize_scene_patch,
    _check_player_act_authority,
    _quote_body,
    _requires_reaction_phase,
    _resolve_player_room,
    _sync_sequence_mirrors,
    assign_event_ids,
    canonicalize_positions,
    character_room,
    character_scene_keys,
    lore_for,
    norm_sequence,
    normalize_character_refs,
    player_speech_lines,
)

def _route_authorial_npc_cognition(ctx, out):
    """Authorial-channel floor (P3): when the PLAYER authors another character's
    INTERIOR cognition -- a mental-verb beat whose grammatical SUBJECT is a
    sheeted cast member ('Dr. Moon remembers she has her smartphone') -- that is
    the player puppeting a mind the character alone owns. Reroute it from a
    fait-accompli pc_action into an OFFER handed to that character's own agent
    (out['authorial_offers'], surfaced in character_step), and drop it from the
    resolved sequence so the Director never enacts the cognition as objective
    truth. Any OBJECT the same input introduces (the phone exists) still rides
    the normal world/generation path -- only the interior state is rerouted.

    High precision: requires the cast name to be the LEADING subject AND the act
    to be mental, so 'I remember Dr. Moon's face' (player's own recall about an
    NPC) is untouched -- its subject is the player, not the NPC."""
    cast = ctx.cast or []
    if not cast:
        return
    name_to_id = {}
    for c in cast:
        try:
            nm = character_name(json.loads(c["sheet"]))
        except Exception:
            continue
        if nm:
            name_to_id[nm.casefold()] = c["id"]
    if not name_to_id:
        return
    offers = out.setdefault("authorial_offers", [])
    kept = []
    changed = False
    for e in (out.get("sequence") or []):
        if e.get("type") != "action":
            kept.append(e)
            continue
        att = str(e.get("attempt") or "")
        low = att.casefold()
        subject_cid = None
        for nm_cf, cid in name_to_id.items():
            if low.startswith(nm_cf + " ") or low.startswith(nm_cf + "'"):
                remainder = att[len(nm_cf):].strip(" '’")
                if _is_mental_action(e.get("verb"), remainder):
                    subject_cid = cid
                break
        if subject_cid is not None:
            offers.append({
                "subject_id": subject_cid,
                "proposition": att,
                "source": "player",
            })
            ctx.add_warning(
                "director_interpret: player-authored NPC cognition rerouted to "
                f"an offer for cast {subject_cid} ({att!r})")
            changed = True
            continue  # drop the puppeted cognition from the resolved sequence
        kept.append(e)
    if changed:
        out["sequence"] = kept
        # Re-derive the scalar mirrors (action/actions/speech) after dropping an
        # element. Runs on the already-normalized sequence (norm_sequence first).
        _sync_sequence_mirrors(out)


def director_establish(ctx, nonce):
    chat = ctx.chat
    pers = persona_of(chat)
    mapping = ctx.mapping_stage or ctx.mapping_quick or {}
    fm = fiction_model(chat.id)

    cast = cast_scene_context(ctx.cast)

    payload = {
        "scenario": chat.get("scenario"),
        **({"style_guide": style_guide(chat["id"])}
           if style_guide(chat["id"]) else {}),
        "player": {
            "name": pers.get("name") or persona_name(pers),
            "appearance": persona_appearance(pers),
            "senses": senses_of(pers),
            "abilities": persona_abilities(pers),
            "public_history": persona_public_history(pers),
        },
        "present_characters": cast,
        "relevant_lore": lore_for(ctx),
        "mapping_scene_proposal": _normalize_scene_patch(mapping.get("scene_patch")),
        "fiction_model": fm,
        "player_seed": ctx.get("input") or "",
        "variant_seed": nonce,
    }

    out = _agent_json(
        "director",
        "director_establish",
        get_prompt("director_establish"),
        payload,
        temperature=0.7,
        max_tokens=16000,
    )
    # Warning-only re-normalization; strict schema+semantic validation
    # (with repair/fallback/raise) already ran inside _agent_json.
    out, warnings = validate_llm_output("director_establish", out)
    ctx.warnings.extend(warnings)

    attire = out.get("attire") or {}
    for entity, state in attire.items():
        if not isinstance(state, dict):
            continue
        state["wearing"] = sanitize_attire_items(state.get("wearing"))

    out.setdefault("entities", {})
    out.setdefault("sensory_events", [])
    out.setdefault("fiction_frame", {})
    out.setdefault("simulation_clock", {"elapsed_seconds": 0.0, "display": "now"})

    out["state_diff"] = {
        "rooms": out.get("rooms") if isinstance(out.get("rooms"), dict) else {},
        "entities": out.get("entities") if isinstance(out.get("entities"), dict) else {},
        # Key positions by the registered character name (the convention every
        # reader uses), even when the model keyed a cast member by identity.uid,
        # a 'character:<id>' scheme, or a snake-case variant of the player name.
        "positions": canonicalize_positions(
            out.get("positions") if isinstance(out.get("positions"), dict) else {},
            ctx.cast, player_name=(pers.get("name") or persona_name(pers))),
        "remove_entities": [],
        "remove_rooms": [],
        "attire": out.get("attire") if isinstance(out.get("attire"), dict) else {},
        "world_facts": out.get("world_facts") if isinstance(out.get("world_facts"), list) else [],
        "time": None,
    }
    out["resolved_event"] = out.get("scene_description", "")
    out["summary"] = "Scene established: " + (out.get("location") or "")
    out["dialogue_log"] = []
    return out

def director_interpret(ctx, nonce):
    chat = ctx.chat
    sc = get_scene(chat["id"], chat)
    pers = persona_of(chat)
    p_room = ctx.get("_player_room")
    if p_room is None:
        p_room = _resolve_player_room(sc, pers, None, ctx.cast, ctx.get("input"))
        ctx["_player_room"] = p_room

    cast_info = []
    for c in ctx.cast:
        sh, _, _ = sheet_state(c)
        cast_info.append({
            "id": c["id"],
            "name": character_name(sh),
            "room": room_of(sc, character_name(sh)),
            "appearance": appearance_of(character_name(sh),
                                        character_appearance(sh), sc),
            "abilities": character_abilities(sh),
        })

    raw_shadow = wget(chat["id"], "shadow_profile", "") or ""
    raw_intents = wget(chat["id"], "standing_intentions", []) or []
    fm = fiction_model(chat["id"])
    clock = simulation_clock(chat["id"])

    # Authored future events the player scheduled on a prior beat and that are
    # due NOW (P4). Delivered with a resolve-now contract; commit_authored_events
    # re-queues any the resolution fails to enact rather than dropping them.
    from authored_events import due_authored_events
    _due_authored = due_authored_events(chat["id"], ctx.turn.idx)

    world_books = [
        {"name": m["name"], "type": m["type"], "summary": (m["summary"] or "")[:240],
         "scope_world_id": m.get("scope_world_id"),
         "scope_location_id": m.get("scope_location_id"),
         "parent_id": m.get("parent_id")}
        for m in lorebook_manifest(chat["id"])["books"]
    ]

    payload = {
        "scene": {
            "location": sc.get("location"),
            "time": sc.get("time"),
            "rooms": _contextual_rooms(sc, ctx.cast, p_room),
            "entities": sc.get("entities"),
            "positions": sc.get("positions"),
        },
        "simulation_clock": clock,
        "paradox": paradox_visible_to(chat["id"], ctx.turn.frame_id),
        "fiction_model": fm,
        "director_recent_messages": director_context(chat["id"], 5),
        "player": {
            "name": pers.get("name") or persona_name(pers),
            "room": p_room,
            "appearance": appearance_of(
                pers.get("name") or persona_name(pers),
                pers.get("appearance") or persona_appearance(pers), sc),
            "abilities": persona_abilities(pers),
            "public_shadow_profile": raw_shadow[:1200],
        },
        "present_characters": cast_info,
        "world_books": world_books,
        "standing_intentions": raw_intents[:12],
        "pending": wget(chat["id"], "pending", []),
        # Future beats the PLAYER scheduled earlier ("the elevator crashes next
        # turn") that are due NOW: resolve them as occurring this beat, folded
        # in with whatever the player declares this turn.
        "due_authored_events": [e["summary"] for e in _due_authored],
        # Mechanical notices from the previous commit's transit sweep (e.g.
        # a timed arrival that completed) -- facts the engine already made
        # true, for the director to acknowledge rather than re-invent.
        "engine_notices": wget(chat["id"], "engine_notices", []),
        "player_raw_input": ctx.input,
        # Idle attached players (connected, but declared nothing this beat)
        # are deliberately excluded here -- there's nothing to interpret
        # for them. They still get their own perceiver/narrated view of
        # the beat via perception_outcome/narrator_extra; they just don't
        # need the director's attention.
        "other_players": [
            {"persona_id": p["persona_id"], "name": p["name"], "raw_input": p["input"]}
            for p in ctx.extra_players if not p.get("idle")
        ],
        "variant_seed": nonce,
    }

    out = _agent_json(
        "director",
        "director_interpret",
        get_prompt("director_interpret"),
        payload,
        max_tokens=16000,
    )

    # Warning-only re-normalization; strict validation already ran inside
    # _agent_json (see director_establish above).
    out, warnings = validate_llm_output("director_interpret", out)
    ctx.warnings.extend(warnings)

    norm_sequence(out)
    _route_authorial_npc_cognition(ctx, out)
    out["sequence"] = assign_event_ids(
        out.get("sequence"), f"turn:{ctx.turn.id}:player")

    other_players = out.get("other_players")
    if not isinstance(other_players, dict):
        other_players = {}
        out["other_players"] = other_players
    for extra in ctx.extra_players:
        pid = str(extra["persona_id"])
        entry = other_players.get(pid)
        if not isinstance(entry, dict):
            entry = {}
            other_players[pid] = entry
        norm_sequence(entry)
        entry["sequence"] = assign_event_ids(
            entry.get("sequence"), f"turn:{ctx.turn.id}:extra:{pid}")

    fl = out.get("flow")
    if not isinstance(fl, dict):
        fl = {}
        out["flow"] = fl

    reactors = fl.get("reactors")
    if not isinstance(reactors, list):
        reactors = []
    tom_triggers = fl.get("tom_triggers")
    if not isinstance(tom_triggers, list):
        tom_triggers = []

    fl["reactors"] = normalize_character_refs(
        reactors + _list(fl.get("reactor_refs")), ctx.cast)
    fl["tom_triggers"] = normalize_character_refs(
        tom_triggers + _list(fl.get("tom_trigger_refs")), ctx.cast)
    fl.pop("reactor_refs", None)
    fl.pop("tom_trigger_refs", None)

    if not fl["reactors"]:
        for c in ctx.cast:
            sh = json.loads(c["sheet"])
            c_room = character_room(sc, sh)
            rel = spatial_rel(sc, p_room, c_room)
            barrier = rel.get("barrier")
            if rel.get("same_room") or barrier in ("open", "open_door",
                                                    "closed_door", "wall"):
                fl["reactors"].append(c["id"])

    fl.setdefault("dialogue_mode", False)
    fl.setdefault("needs_mapping", False)
    if not isinstance(fl.get("dice"), list):
        fl["dice"] = []
    fl.setdefault("mapping_request", "")
    if not isinstance(fl.get("resolution_flags"), dict):
        fl["resolution_flags"] = {}
    if not isinstance(fl.get("generation_requests"), list):
        fl["generation_requests"] = []
    if not isinstance(fl.get("authority_claims"), list):
        fl["authority_claims"] = []
    if not isinstance(fl.get("fiction_frame"), dict):
        fl["fiction_frame"] = {}

    out.setdefault("private_thought", None)
    out.setdefault("movement", None)
    out.setdefault("location_query", None)
    if isinstance(out.get("movement"), dict):
        out["movement"].setdefault("mover", "self")

    # Interpret reconciliation seam (the structural twin of the resolve
    # seam below): deterministic omission detection of player declarations
    # the interpretation dropped, one bounded self-repair, warn-only
    # fallback. Runs BEFORE claims extraction / contested detection /
    # mapping triggers so every downstream deterministic pass sees the
    # repaired sequence.
    _reconcile_interpretation(ctx, out, sc)

    # Any generation request (model-authored, repaired, or synthesized by
    # the seam) needs the full mapping stage to elaborate it.
    if fl.get("generation_requests"):
        fl["needs_mapping"] = True

    # Extract authority claims from the sequence. The player is the declaring
    # actor, so a self-directed effect (no target) resolves to them -- see
    # _extract_authority_claims; this stops the resolve reconciliation flagging
    # the player's own body actions (wave, go rigid) as 'no resolvable subject'.
    fl["authority_claims"] = _extract_authority_claims(
        out.get("sequence"), ctx.input,
        actor_name=(pers.get("name") or persona_name(pers)))

    # Detect contested actions
    seq = out.get("sequence")
    if not isinstance(seq, list):
        seq = []
    action_texts = " ".join(
        str(e.get("attempt") or "").casefold()
        for e in seq
        if isinstance(e, dict) and e.get("type") == "action"
    )
    valid_actor_ids = {
        int(row["id"])
        for row in ctx.cast
    }

    actor_names = {
        character_name(
            json.loads(row["sheet"])
        ).casefold()
        for row in ctx.cast
    }

    has_reactable_target = any(
        _requires_reaction_phase(
            event,
            valid_actor_ids,
            actor_names,
        )
        for event in seq
    )

    if has_reactable_target:
        fl["resolution_flags"]["contested"] = True
        fl["resolution_flags"]["possible_reactors"] = [
            int(rid)
            for rid in fl["reactors"]
            if str(rid).isdigit()
            and int(rid) in valid_actor_ids
        ]
    else:
        fl["resolution_flags"]["contested"] = False
        fl["resolution_flags"]["possible_reactors"] = []
    lq = out.get("location_query")
    if isinstance(lq, str) and lq.strip():
        fl["needs_mapping"] = True
        mr = fl.get("mapping_request") or ""
        fl["mapping_request"] = (mr + f" Location/system query: {lq.strip()}").strip()
    else:
        out["location_query"] = None

    existing_rooms = set((sc.get("rooms") or {}).keys())
    mv = out.get("movement")
    if isinstance(mv, dict) and mv.get("to_room"):
        if mv["to_room"] not in existing_rooms:
            fl["needs_mapping"] = True
            mr = fl.get("mapping_request") or ""
            extra = (f" Player movement targets new room '{mv['to_room']}' "
                     f"not in scene — generate room description.")
            fl["mapping_request"] = (mr + " " + extra).strip()

    if not (isinstance(mv, dict) and mv.get("to_room")):
        movement_cues = (
            "enter", "step inside", "peer inside", "look inside",
            "go inside", "walk into", "cross threshold",
            "through the door", "step through", "go through",
            "boards", "climbs inside",
        )
        if any(cue in action_texts for cue in movement_cues):
            fl["needs_mapping"] = True
            mr = fl.get("mapping_request") or ""
            extra = (" Player action implies entering/approaching a contained "
                     "space — infer the destination room and generate its description.")
            fl["mapping_request"] = (mr + " " + extra).strip()

    # Broadened world-state mutation detection
    if not fl.get("needs_mapping"):
        input_text = str(ctx.input or "").casefold()
        mutation_text = f"{input_text} {action_texts}"
        mutation_cues = (
            "appears", "materializes", "arrives", "summons", "creates",
            "builds", "opens a portal", "reveals a door", "discovers a room",
            "puts down", "picks up", "hands ", "places ",
            "destroys", "breaks", "collapses", "vanishes", "disappears",
        )
        if any(cue in mutation_text for cue in mutation_cues):
            fl["needs_mapping"] = True
            existing_request = fl.get("mapping_request") or ""
            fl["mapping_request"] = (
                existing_request
                + " Inspect the declaration for new, moved, transferred, "
                  "transformed, opened, destroyed, or contained scene entities "
                  "and propose the minimum scene graph patch."
            ).strip()

    if wget(chat["id"], "pending", []):
        fl["needs_mapping"] = True

    # Carry the due authored events onto the output so director_resolve can
    # enact them, and force mapping when one is due (a scheduled world beat --
    # a crash, an arrival -- may reshape the scene graph).
    out["due_authored_events"] = [e["summary"] for e in _due_authored]
    if _due_authored:
        fl["needs_mapping"] = True

    # Do NOT set ctx["_player_room"] to the declared movement target here.
    # A movement declaration is only a request for director_resolve to
    # validate (it can be blocked by the passable-route check). ctx
    # already holds the player's actual pre-turn room from the resolution
    # above; perception_act (the action-onset pass) must keep using that,
    # not a not-yet-resolved destination — otherwise onset perception
    # treats the player as having already arrived before anyone (the
    # player included) has moved.

    return out

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

_DECL_STOPWORDS = frozenset("""
a an the and or but nor then i i'm i'll i've you you're he she it it's we
they my your his her its our their me him them us who whom whose which
what how why this that these those there here to of in on at by for with
from as is are was were be been being am do does did done have has had
having will would can could shall should may might must not no yes if so
too also just very quite about around while when where over under out up
down off into onto again once still now then before after behind toward
towards through between against along away back get gets got go goes
going gone come comes came take takes took make makes made turn turns
turned start starts started begin begins began try tries tried trying
attempt attempts keep keeps kept let lets say says said tell tells told
ask asks asked look looks looked see sees saw put puts one two moment
little bit around some any all both each other another same own than
""".split())

_QUOTED_UNIT_RE = re.compile(r'["“]([^"“”]{4,})["”]')
_CLAUSE_SPLIT_RE = re.compile(
    r"[.;!?\n]+|,\s+(?:and|then|but)\s+|\s+(?:and\s+then|then)\s+|\s+and\s+"
)

_RECONCILE_INTERPRET_MAX_UNITS = 4
_INTERPRET_COVERAGE_MIN = 0.5

def _decl_tokens(text):
    """Significant tokens of one declaration unit: casefolded alphanumeric
    words, length >= 3, stopwords removed. No domain keyword lists -- pure
    lexical coverage is the anti-treadmill property this seam is built on."""
    tokens = set()
    for tok in re.findall(r"[a-z0-9']+", str(text or "").casefold()):
        tok = tok.strip("'")
        if len(tok) >= 3 and tok not in _DECL_STOPWORDS:
            tokens.add(tok)
    return tokens

def _declaration_units(raw_input):
    """Split raw player input into declaration units: quoted spans (each a
    speech declaration) plus narrative clauses split on sentence boundaries
    and coordination. Units with fewer than two significant tokens are
    skipped -- too little signal to judge coverage without false positives
    (the conservative floor)."""
    text = str(raw_input or "")
    units = [m.group(1).strip() for m in _QUOTED_UNIT_RE.finditer(text)]
    narrative = _QUOTED_UNIT_RE.sub(" ", text)
    for clause in _CLAUSE_SPLIT_RE.split(narrative):
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
        for field in ("text", "attempt", "raw_text", "description",
                      "subject", "verb"):
            pieces.append(e.get(field))
        pieces.extend(str(t) for t in (e.get("targets") or []))
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

def _reconcile_interpretation(ctx, out, sc):
    """The interpret-reconciliation seam (see the block comment above).
    Mutates `out` in place: repaired sequence elements are appended (never
    replacing what interpret already declared), a missing movement may be
    filled (never overwritten), mapping_request/generation_requests are
    extended. Records inspection metadata on out['interpret_reconciliation']
    and appends to ctx.warnings for anything still uncovered."""
    raw_input = str(ctx.get("input") or "")
    fl = _dict(out.get("flow"))
    recon = {"uncovered": [], "repaired": False, "dispositions": [],
             "unresolved": []}
    out["interpret_reconciliation"] = recon
    if not raw_input.strip():
        return

    uncovered = _uncovered_declarations(raw_input, out)
    if not uncovered:
        return
    recon["uncovered"] = list(uncovered)

    # ---- One bounded self-repair by the interpretation's own owner ------
    repair = None
    try:
        repair = _agent_json(
            "director", "interpret_repair",
            get_prompt("interpret_repair"),
            {
                "player_raw_input": raw_input,
                "current_interpretation": {
                    "sequence": out.get("sequence") or [],
                    "movement": out.get("movement"),
                    "mapping_request": fl.get("mapping_request") or "",
                    "location_query": out.get("location_query"),
                    "generation_requests":
                        _dict_list(fl.get("generation_requests")),
                },
                "dropped_declarations": uncovered,
                "existing_rooms": sorted((sc.get("rooms") or {}).keys()),
            },
            temperature=0.0, max_tokens=8000,
        )
    except Aborted:
        raise
    except Exception as exc:
        ctx.add_warning(f"Interpret reconciliation repair failed: {exc}")

    if not isinstance(fl.get("generation_requests"), list):
        fl["generation_requests"] = []

    if isinstance(repair, dict):
        additions = {
            "sequence": [e for e in (repair.get("sequence") or [])
                         if isinstance(e, dict)],
        }
        norm_sequence(additions)
        new_elems = assign_event_ids(
            additions["sequence"], f"turn:{ctx.turn.id}:repair")
        if new_elems:
            out["sequence"] = list(out.get("sequence") or []) + new_elems
            _sync_sequence_mirrors(out)
            recon["repaired"] = True
        rmv = repair.get("movement")
        already_moving = isinstance(out.get("movement"), dict) \
            and out["movement"].get("to_room")
        if isinstance(rmv, dict) and rmv.get("to_room") and not already_moving:
            out["movement"] = {
                "to_room": str(rmv["to_room"]),
                "why": str(rmv.get("why") or ""),
                "mover": str(rmv.get("mover") or "self"),
            }
            recon["repaired"] = True
        extra_request = str(repair.get("mapping_request") or "").strip()
        if extra_request:
            fl["mapping_request"] = (
                (fl.get("mapping_request") or "") + " " + extra_request
            ).strip()
        for gr in _dict_list(repair.get("generation_requests")):
            if gr not in fl["generation_requests"]:
                fl["generation_requests"].append(gr)
                recon["repaired"] = True
        recon["dispositions"] = _dict_list(repair.get("dispositions"))

    # The owner explicitly overruled the checker for these units -- believe
    # the rejection rather than warn on a model-vs-checker disagreement
    # (same conservatism as the resolve seam's manifest dispositions).
    already_covered = {
        _norm_subject(d.get("subject"))
        for d in recon["dispositions"]
        if str(d.get("status") or "").casefold() == "already_covered"
    }

    # ---- Deterministic re-check against the merged interpretation -------
    corpus = _interpret_coverage_corpus(out)
    prefixes = {c[:4] for c in corpus if len(c) >= 4}
    for unit in uncovered:
        if _norm_subject(unit) in already_covered:
            continue
        if _unit_covered(unit, corpus, prefixes):
            continue
        # Warn-only fallback: the minimal covering element is the player's
        # VERBATIM clause forwarded to mapping for bounded additive
        # elaboration -- never a fabricated structured act.
        fl["generation_requests"].append({
            "kind": "player_declaration",
            "subject": unit[:240],
            "constraints": [
                "player-declared: existence and stated specifics are fixed",
                "elaborate additively, scoped to the declaration only",
            ],
            "urgency": "now",
        })
        fl["needs_mapping"] = True
        recon["unresolved"].append(unit)
        ctx.add_warning(
            "PLAYER AUTHORITY: declared "
            f"{unit!r} was not captured by director_interpret even after "
            "self-repair; forwarded verbatim to mapping as a generation "
            "request (no structured act was fabricated)."
        )

# ---------------------------------------------------------------------------
# Resolve reconciliation: one general seam catching the recurring failure
# class where director_resolve's resolved_event PROSE asserts a persistent,
# physically consequential change (doors sealed, a passage collapsed, an
# object destroyed, someone restrained) that its structured state_diff
# OMITS -- so commit applies stale objective truth and perception, which
# renders from structured truth rather than prose, contradicts the story
# on the very next turn (live instance: an elevator narrated as sealed and
# descending while the room diff was a blank placeholder, leaving the
# doors objectively "held open" onto the smoke-filled corridor).
#
# Shape of the mechanism, deliberately NOT keyword/verb recognition of
# world events (an unwinnable enumeration treadmill). Three tiers, all
# DETECTION deterministic on the common path (no per-beat LLM call):
#   Tier 0 (deterministic, every beat, zero cost):
#     - blank all-empty placeholder diff entries are pure noise
#       masquerading as a handled change; strip and flag them in code;
#     - the legacy restraint/duress scan (folded in; used to be warn-only
#       and one-off);
#     - PLAYER-CLAIM COVERAGE: every asserted scope='effect' authority
#       claim with a resolvable subject must be encoded somewhere in the
#       diff -- structure minted by director_interpret in a DIFFERENT
#       call, so a resolve-side encoding drop is caught with no same-call
#       self-consistency bias. Null-subject claims degrade to a metadata
#       note, never a warning. The claim_dispositions contract (asserted
#       claims are never rejected/failed) is cross-checked too.
#   Tier 1 (near-zero cost, same call): director_resolve's own
#     changes_asserted manifest -- persistent changes its prose asserts,
#     beyond the player's claims -- checked against the diff with
#     CATEGORY-AWARE evidence classes (an 'adjacency' change needs an
#     adjacency-affecting entry, not merely the subject's name somewhere:
#     the partial-encoding trap that let the elevator through) and
#     ALIAS-AWARE subjects (name/uid/alias via character_scene_keys and
#     entity aliases).
#   Tier 2 (LLM, omission path only): bounded self-repair BY THE DIRECTOR
#     ITSELF (never an external critic writing state): one re-invocation
#     with the specific detected omissions called out, returning a
#     correction delta merged ADDITIVELY over the original diff and
#     re-checked deterministically. Disposition authority is tiered:
#     player-claim omissions are NON-REJECTABLE (honored only when
#     post-merge evidence actually exists) and always warn while
#     unencoded; structural signals warn if unrepaired; manifest
#     (emergent) omissions may be rejected by the owner. Anything still
#     unencoded falls back to ctx.warnings -- this engine never
#     fabricates objective state from a heuristic, because a wrongly
#     invented fact lingering is worse than a stale missing one.
# The standalone resolve_reconcile deep audit is retained behind the
# default-off 'resolve_deep_audit' setting ('1'/'always' = every physical
# beat; 'tripwire' = only when the silent-false-negative tripwire fires:
# successful dice or asserted effect-claims alongside an EMPTY manifest
# and an empty physical diff).
# ---------------------------------------------------------------------------

# Keep the keyword list small and specific so it does not fire on ordinary
# descriptive prose. This is a legacy high-precision detector for one known
# failure (a character held at gunpoint narrated but never written to
# state_diff.conditions); the general omission audit above it is what covers
# the open-ended class.
_RESTRAINT_KEYWORDS = (
    "held at", "pinned", "rifle to", "gunpoint", "restrained", "hostage",
    "grappled",
)

def _untracked_restraint_subjects(resolved_event, dialogue_log, conditions,
                                  tracked_names):
    """Named, tracked characters whose mention co-occurs with a restraint/
    duress keyword in resolved_event or a dialogue_log exact_quote, but who
    have no matching state_diff.conditions entry (matched by subject_id,
    casefolded). Sorted for deterministic output."""
    text_units = [str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict):
            quote = entry.get("exact_quote")
            if quote:
                text_units.append(str(quote))

    tracked_condition_subjects = set()
    for cond_value in (conditions or {}).values():
        cond_list = cond_value if isinstance(cond_value, list) else [cond_value]
        for c in cond_list:
            if isinstance(c, dict):
                tracked_condition_subjects.add(
                    str(c.get("subject_id") or "").casefold())

    flagged_names = set()
    for text in text_units:
        lower = text.casefold()
        if not any(keyword in lower for keyword in _RESTRAINT_KEYWORDS):
            continue
        for name in tracked_names:
            if name and name.casefold() in lower:
                flagged_names.add(name)

    return [name for name in sorted(flagged_names)
            if name.casefold() not in tracked_condition_subjects]

# Consciousness floor (awareness Phase 1). Observed live: an elevator crash
# resolved with the prose narrating the player "unconscious" and "knocked out"
# while state_diff.conditions was null -- so no `awareness` condition was born
# and perception kept handing the unconscious mind a full sighted view for
# turns. High-precision loss-of-consciousness cues, keyed on tracked names, and
# -- unlike the destruction tripwire -- this DOES feed the Tier-2 self-repair:
# an awareness condition is reversible and non-cascading, so a false positive
# costs one degraded beat while a miss is a multi-turn perception-barrier
# breach. HIGH-PRECISION via grammatical-subject attribution (like the
# destruction tripwire): a cue is pinned to the single nearest tracked name in
# the same clause, so a bystander merely co-mentioned with the fallen one ("Dr.
# Moon kneels beside the unconscious anomaly") is never flagged. It is the
# deterministic floor UNDER the broad semantic omission auditor, never the
# mechanism.
_UNCONSCIOUSNESS_CUE = re.compile(
    r"\b(?:"
    r"unconscious|out\s+cold|"
    r"knocked\s+(?:out|unconscious|senseless)|"
    r"blacks?\s+out|blacked\s+out|"
    r"passes?\s+out|passed\s+out|"
    r"faints|fainted|"
    r"loses\s+consciousness|lost\s+consciousness|"
    r"goes\s+limp|slumps?\s+unconscious|"
    r"sedated|put\s+under"
    r")\b"
)
# Titles whose trailing period is not a sentence break (so "Dr. Moon" is one
# clause, and "unconscious ... Dr. Moon" across a real "anomaly." break stays
# two clauses).
_TITLE_ABBREV = frozenset((
    "dr", "mr", "mrs", "ms", "prof", "st", "sr", "jr", "mt", "rev", "hon",
    "gen", "capt", "sgt", "lt", "col", "gov", "fr", "det", "sen", "rep",
))
_MAX_UNCONSCIOUSNESS_GAP = 5  # word tokens between a cue and its subject name


def _sentence_break_positions(low):
    """Offsets in casefolded `low` that terminate a sentence -- a '.', '!',
    '?' or newline -- excluding an abbreviation period (one preceded by a
    short title word in _TITLE_ABBREV). Used as clause barriers so a cue and
    a name on opposite sides of a real break are never paired."""
    breaks = []
    for m in re.finditer(r"[.!?]|\n", low):
        if low[m.start()] == ".":
            wm = re.search(r"([a-z]+)$", low[:m.start()])
            if wm and wm.group(1) in _TITLE_ABBREV:
                continue
        breaks.append(m.start())
    return breaks


def _untracked_unconsciousness_subjects(resolved_event, dialogue_log, conditions,
                                        tracked_names):
    """Named, tracked characters narrated as losing consciousness with no
    matching `awareness` condition in the diff. Each cue is attributed to a
    SINGLE subject -- the nearest tracked name in the same sentence within
    _MAX_UNCONSCIOUSNESS_GAP words -- so a bystander merely co-mentioned with
    the fallen one is never flagged. Presence check is specific to
    kind:'awareness'; an unrelated wound/restraint condition on the same
    subject must not suppress the awareness flag."""
    text_units = [str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict) and entry.get("exact_quote"):
            text_units.append(str(entry["exact_quote"]))

    aware_subjects = set()
    for cond_value in (conditions or {}).values():
        for c in (cond_value if isinstance(cond_value, list) else [cond_value]):
            if isinstance(c, dict) and c.get("kind") == "awareness":
                aware_subjects.add(str(c.get("subject_id") or "").casefold())

    name_res = [(name, re.compile(r"\b" + re.escape(name.casefold()) + r"(?:'s)?\b"))
                for name in tracked_names if name]

    flagged = set()
    for text in text_units:
        low = str(text).casefold()
        name_hits = [(m.start(), m.end(), name)
                     for name, rx in name_res for m in rx.finditer(low)]
        if not name_hits:
            continue
        breaks = _sentence_break_positions(low)
        for cm in _UNCONSCIOUSNESS_CUE.finditer(low):
            cs, ce = cm.start(), cm.end()
            best = None  # (word_gap, name) -- the closest same-clause subject
            for ns, ne, name in name_hits:
                if ne <= cs:            # name before the cue
                    lo, hi = ne, cs
                elif ns >= ce:          # name after the cue
                    lo, hi = ce, ns
                else:                   # overlaps the cue span; skip
                    continue
                if any(lo <= p < hi for p in breaks):
                    continue            # a sentence break separates them
                gap = len(re.findall(r"\w+", low[lo:hi]))
                if gap > _MAX_UNCONSCIOUSNESS_GAP:
                    continue
                if best is None or gap < best[0]:
                    best = (gap, name)
            if best is not None:
                flagged.add(best[1])
    return [n for n in sorted(flagged) if n.casefold() not in aware_subjects]

# Destruction tripwire (movement/space Phase 3b follow-up). Observed live:
# the resolved_event narrated a whole-town firestorm consuming a named
# region ward by ward, yet state_diff.destruction was null and remove_rooms
# empty -- so the Phase-3b cascade (which only realizes a DECLARED
# destruction) never fired and the town stayed objectively intact against
# the prose. Same design constraints as the restraint scan: deterministic,
# HIGH-PRECISION, and WARN-ONLY -- this engine never fabricates objective
# state from a heuristic, and a wrongly-invented razing (books retired,
# rooms gone, news minted) would be far worse than a stale-missing one, so
# this detector deliberately does NOT feed the Tier-2 self-repair path.
#
# Precision guard: a bare keyword scan ("the fire spread") or even
# sentence-level co-occurrence ("the letter was destroyed in the hall"
# flagging the hall) false-fires on ordinary flavor. Matching is keyed on
# ACTUAL known place names (scene rooms, the scene location, interior-
# bearing entities, live lorebook names) in destruction-shaped grammatical
# positions only:
#   subject-first:  "<name> ... was razed / burned down / in ruins"
#   verb-object:    "razed/consumed/destroyed (the) <name>"
#   of-phrase:      "ruins/ashes/nothing left of <name>"
_DESTRUCTION_TERMINAL_CUES = (
    r"(?:was |were |now )?(?:utterly |completely |entirely )?"
    r"(?:destroyed|razed|levell?ed|flattened|obliterated|annihilated|"
    r"incinerated|collapsed|burn(?:ed|t)\s+down|"
    r"burn(?:ed|t)\s+to\s+the\s+ground|"
    r"reduced\s+to\s+(?:ash|ashes|rubble|cinders)|"
    r"wiped\s+out|in\s+ruins|no\s+longer\s+stands|no\s+more|"
    r"consumed\s+by|engulfed\s+in\s+flames|swallowed\s+by|"
    r"lost\s+to\s+the\s+(?:flames|fire|sea))"
)
_DESTRUCTION_VERB_OBJECT = (
    r"(?:destroy(?:ed|s)|raz(?:ed|ing)|levell?(?:ed|ing)|consum(?:ed|ing)|"
    r"obliterat(?:ed|ing)|annihilat(?:ed|ing)|flatten(?:ed|ing)|"
    r"incinerat(?:ed|ing)|swallow(?:ed|ing)|engulf(?:ed|ing)|"
    r"wip(?:ed|ing)\s+out|burn(?:ed|t|ing)\s+down)"
)
_DESTRUCTION_OF_PHRASE = (
    r"(?:ruins?|ashes|remains|destruction|razing|loss|"
    r"nothing\s+(?:\w+\s+){0,2}?(?:left|remains|remained))\s+(?:\w+\s+){0,2}?of"
)

def _destruction_name_pattern(name_cf):
    """One compiled pattern per known place name covering the three
    destruction-shaped positions above. Bounded word-gaps, not free
    sentence co-occurrence."""
    name = re.escape(name_cf)
    return re.compile(
        rf"\b{name}(?:'s)?\b[,\s]+(?:\S+\s+){{0,4}}?{_DESTRUCTION_TERMINAL_CUES}"
        rf"|{_DESTRUCTION_VERB_OBJECT}\s+"
        rf"(?:the\s+|all\s+of\s+|the\s+whole\s+|the\s+entire\s+|most\s+of\s+)?"
        rf"{name}\b"
        rf"|{_DESTRUCTION_OF_PHRASE}\s+(?:the\s+)?{name}\b"
    )

def _narrated_destruction_subjects(resolved_event, dialogue_log, sd, sc,
                                   extra_names=()):
    """Named, KNOWN places (scene rooms, the scene location, interior-
    bearing entities, plus extra_names -- live lorebook names) that the
    prose asserts destroyed while the diff encodes neither
    state_diff.destruction nor a remove_rooms/remove_entities entry
    covering them. Sorted labels for deterministic output.

    Any declared destruction this beat suppresses the whole scan: scoping
    what the cascade covers is commit's job, not a text heuristic's.
    """
    destruction = sd.get("destruction")
    if isinstance(destruction, dict) and destruction.get("target_id"):
        return []

    candidates = {}

    def _add(label, room_ids=(), entity_ids=()):
        label = str(label or "").strip()
        if len(label) < 3:
            return
        key = label.casefold()
        cand = candidates.setdefault(key, {
            "label": label, "room_ids": set(), "entity_ids": set(),
            "pattern": _destruction_name_pattern(key),
        })
        # Prefer a display-cased label (room "name") over a lowercased
        # id-derived one for the same key -- it names the warning.
        if cand["label"].islower() and not label.islower():
            cand["label"] = label
        cand["room_ids"].update(room_ids)
        cand["entity_ids"].update(entity_ids)

    for rid, room in (sc.get("rooms") or {}).items():
        if not isinstance(room, dict):
            continue
        _add(str(rid).replace("_", " "), room_ids={str(rid)})
        _add(room.get("name"), room_ids={str(rid)})
    location = str(sc.get("location") or "").strip()
    if location:
        _add(location)
        _add(re.split(r"[,—]", location)[0])
    for eid, ent in (sc.get("entities") or {}).items():
        if not isinstance(ent, dict):
            continue
        kind = str(ent.get("kind") or "").casefold()
        if not (ent.get("interior_rooms")
                or kind in ("vehicle", "building", "structure")):
            continue
        _add(ent.get("name"), entity_ids={str(eid)})
        _add(str(eid).replace("_", " "), entity_ids={str(eid)})
        for alias in (ent.get("aliases") or []):
            _add(alias, entity_ids={str(eid)})
    for name in extra_names:
        _add(name)

    removed_rooms = {str(r) for r in (sd.get("remove_rooms") or [])}
    removed_entities = {str(e).casefold()
                        for e in (sd.get("remove_entities") or [])}

    text_units = [str(resolved_event or "")]
    for entry in (dialogue_log or []):
        if isinstance(entry, dict) and entry.get("exact_quote"):
            text_units.append(str(entry["exact_quote"]))

    flagged = {}
    for text in text_units:
        lower = text.casefold()
        for key, cand in candidates.items():
            if key in flagged:
                continue
            if not cand["pattern"].search(lower):
                continue
            if cand["room_ids"] & removed_rooms:
                continue
            if {e.casefold() for e in cand["entity_ids"]} & removed_entities:
                continue
            flagged[key] = cand["label"]
    return [flagged[key] for key in sorted(flagged)]

def _scan_for_untracked_restraint(resolved_event, dialogue_log, conditions,
                                   tracked_names):
    """Return warning strings for the subjects _untracked_restraint_subjects
    flags. Kept as a stable, directly-testable entry point; director_resolve
    now routes these through the reconciliation seam (which may repair the
    diff first) and emits this exact text only for what remains unencoded.
    """
    return [
        f"Possible untracked physical restraint/duress detected for "
        f"{name!r} (restraint/duress keyword found alongside their "
        "name in resolved_event or dialogue) but no matching "
        "state_diff.conditions entry was recorded this beat."
        for name in _untracked_restraint_subjects(
            resolved_event, dialogue_log, conditions, tracked_names)
    ]

def _normalize_diff_shape(sd):
    """Coerce a state_diff (from the main resolve output or a repair delta)
    to the canonical container shapes every downstream reader assumes.
    Safety net for the LLM returning a string/list where an object belongs."""
    if not isinstance(sd, dict):
        sd = {}
    for k in ("positions", "rooms", "entities", "overlays", "attire",
              "conditions"):
        if not isinstance(sd.get(k), dict):
            sd[k] = {}
    for k in ("cast_changes", "world_facts", "introductions",
              "remove_entities", "remove_rooms", "remove_adjacent",
              "inventory_ops", "claim_dispositions"):
        if not isinstance(sd.get(k), list):
            sd[k] = []
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
                            ("attire", "attire")):
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
                "positions", "remove_entities", "remove_rooms",
                "remove_adjacent", "inventory_ops", "cast_changes"):
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
            _merge_room(existing, incoming)
            if isinstance(existing, dict) else incoming
        )
    for field in ("entities", "attire", "overlays"):
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
    for field in ("remove_entities", "remove_rooms", "remove_adjacent",
                  "inventory_ops", "cast_changes", "world_facts",
                  "introductions"):
        for item in (patch.get(field) or []):
            if item not in sd[field]:
                sd[field].append(item)
    if sd.get("time") is None and patch.get("time") is not None:
        sd["time"] = patch["time"]
    return sd

def _norm_subject(value):
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())

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

    for field in ("rooms", "entities", "attire", "positions"):
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
    return False

# Category synonyms a model may plausibly write in a manifest entry, folded
# onto the canonical evidence-class names.
_OMISSION_CATEGORY_ALIASES = {
    "room": "rooms", "location": "rooms",
    "adjacent": "adjacency", "door": "adjacency", "passage": "adjacency",
    "barrier": "adjacency",
    "position": "positions", "movement": "positions",
    "entity": "entities", "object": "entities",
    "condition": "conditions", "status_effect": "conditions",
    "clothing": "attire", "outfit": "attire",
    "item": "inventory", "inventory_ops": "inventory",
    "cast": "cast_changes", "arrival": "cast_changes",
    "departure": "cast_changes",
    "vehicle": "transit", "portal": "transit", "link": "transit",
}

def _normalize_omission_category(category):
    cat = str(category or "").strip().casefold()
    return _OMISSION_CATEGORY_ALIASES.get(cat, cat) or "other"

def _entity_state_has_transit(entity_def):
    state = entity_def.get("state") if isinstance(entity_def, dict) else None
    return isinstance(state, dict) and ("transit" in state or "link" in state)

def _evidence_present(sd, omission, forms=None):
    """CATEGORY-AWARE evidence check: is the omission's subject touched in
    the RIGHT dimension of the diff, not merely mentioned somewhere? This is
    what closes the partial-encoding trap -- a room whose desc was updated
    but whose narrated adjacency change was dropped passes bare containment
    yet fails the 'adjacency' evidence class. Unknown/other categories fall
    back to the shallow containment check."""
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
        return any(isinstance(c, dict) and hits(c.get("who"))
                   for c in (sd.get("cast_changes") or []))
    if category == "entities":
        for eid, ed in (sd.get("entities") or {}).items():
            if hits(eid) or (isinstance(ed, dict) and (
                    hits(ed.get("name"))
                    or any(hits(a) for a in (ed.get("aliases") or [])))):
                return True
        return any(hits(e) for e in (sd.get("remove_entities") or []))
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
        return any(hits(k) for k in (sd.get("attire") or {}))
    if category == "inventory":
        return any(
            isinstance(op, dict) and (hits(op.get("object_id"))
                                      or hits(op.get("from_id"))
                                      or hits(op.get("to_id")))
            for op in (sd.get("inventory_ops") or [])
        )
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
_RECONCILE_MAX_AUDIT_OMISSIONS = 6
_RECONCILE_MIN_CONFIDENCE = 0.4

def _deep_audit_mode():
    """The default-off standalone resolve_reconcile audit: 'off' (default),
    'always' (every physical beat -- the pre-manifest behavior, kept as a
    belt-and-suspenders option), or 'tripwire' (only when the silent-false-
    negative tripwire fires)."""
    value = str(get_setting("resolve_deep_audit") or "").strip().casefold()
    if value in ("1", "always", "on", "true"):
        return "always"
    if value == "tripwire":
        return "tripwire"
    return "off"

def _manifest_items(out):
    """director_resolve's own changes_asserted manifest, normalized to the
    seam's omission shape (source 'manifest')."""
    items = []
    raw = out.get("changes_asserted")
    for item in (raw if isinstance(raw, list) else []):
        if not isinstance(item, dict):
            continue
        change = str(item.get("change") or "").strip()
        if not change:
            continue
        items.append({
            "category": _normalize_omission_category(item.get("category")),
            "subject": str(item.get("subject") or "").strip(),
            "change": change, "evidence": "", "source": "manifest",
        })
    return items[:_RECONCILE_MAX_MANIFEST_ITEMS]

def _player_claim_findings(out, sd, interp, cast, sc):
    """Tier 0 player-authority coverage: every asserted scope='effect'
    authority claim with a resolvable subject must be encoded SOMEWHERE in
    the diff (shallow containment -- the claim's free-text predicate cannot
    be mapped to one category deterministically). Returns (omissions,
    notes, contract_warnings): null-subject claims become metadata notes
    only; an asserted claim the resolve marked rejected/failed is a player-
    authority contract violation surfaced as a deterministic warning."""
    omissions, notes, contract_warnings = [], [], []
    claims = _dict_list(_dict(interp.get("flow")).get("authority_claims"))
    if not claims:
        return omissions, notes, contract_warnings

    statuses = {}
    for d in _dict_list(out.get("claim_dispositions")) + \
            _dict_list(sd.get("claim_dispositions")):
        cid = str(d.get("claim_id") or "")
        if cid:
            statuses[cid] = str(d.get("status") or "").strip().casefold()

    for claim in claims:
        if str(claim.get("scope") or "") != "effect":
            continue  # contestable intents are the director's to resolve
        status = statuses.get(str(claim.get("claim_id") or ""), "")
        if status in ("rejected", "failed"):
            contract_warnings.append(
                "PLAYER AUTHORITY: asserted claim "
                f"{claim.get('claim_id')!r} ({claim.get('predicate')!r} on "
                f"{claim.get('subject_id')!r}) was marked {status!r} -- "
                "asserted effects occur as declared and may not be rejected."
            )
        subject = str(claim.get("subject_id") or "").strip()
        if not subject:
            notes.append({
                "claim_id": claim.get("claim_id"),
                "predicate": claim.get("predicate"),
                "note": "no resolvable subject; coverage not checkable",
            })
            continue
        forms = _subject_match_forms(subject, cast, sc)
        if not _omission_subject_encoded(sd, subject, forms):
            omissions.append({
                "category": "other", "subject": subject,
                "change": (f"player-asserted completed effect "
                           f"{str(claim.get('predicate') or '')!r} on "
                           f"{subject}"),
                "evidence": str(claim.get("source_text") or ""),
                "source": "player_claim", "_forms": forms,
            })
    return omissions, notes, contract_warnings

def _deep_audit_omissions(ctx, out, sd, scene_slice, dlog_compact,
                          tracked_names, recon):
    """The retained standalone audit call (default off; see
    _deep_audit_mode). Emits omissions with source 'audit'."""
    try:
        audit = _agent_json(
            "director", "resolve_reconcile",
            get_prompt("resolve_reconcile"),
            {
                "resolved_event": out.get("resolved_event", ""),
                "dialogue_log": dlog_compact,
                "state_diff": sd,
                "prior_scene": scene_slice,
                "cast_names": tracked_names,
            },
            temperature=0.0, max_tokens=8000,
        )
    except Aborted:
        raise
    except Exception as exc:
        ctx.add_warning(f"Resolve reconciliation audit failed: {exc}")
        return []
    audit_omissions = []
    raw_omissions = audit.get("omissions")
    for om in (raw_omissions if isinstance(raw_omissions, list) else []):
        if not isinstance(om, dict) or not str(om.get("change") or "").strip():
            continue
        try:
            confidence = float(om.get("confidence", 0.5))
        except (TypeError, ValueError):
            confidence = 0.5
        entry = {
            "category": _normalize_omission_category(om.get("category")),
            "subject": str(om.get("subject") or ""),
            "change": str(om.get("change") or ""),
            "evidence": str(om.get("evidence") or ""),
            "confidence": confidence,
            "source": "audit",
        }
        if confidence < _RECONCILE_MIN_CONFIDENCE:
            # Low-confidence critic guesses are recorded for inspection but
            # never drive a repair or a warning -- the conservative floor.
            recon.setdefault("low_confidence", []).append(entry)
            continue
        audit_omissions.append(entry)
    return audit_omissions[:_RECONCILE_MAX_AUDIT_OMISSIONS]

def _public_omission(omission):
    return {k: v for k, v in omission.items() if not k.startswith("_")}

def _reconcile_resolution(ctx, out, sc, interp, char_actions, dice,
                          tracked_names):
    """The resolve-reconciliation seam (see the block comment above).
    Mutates out['state_diff'] in place (strip + merged repair delta only),
    records inspection metadata on out['reconciliation'], and appends to
    ctx.warnings for anything that remains unencoded. resolved_event and
    dialogue_log are never modified -- the prose is the account being
    reconciled against, not the thing under repair."""
    sd = _normalize_diff_shape(out.get("state_diff"))
    out["state_diff"] = sd
    resolved_event = out.get("resolved_event", "")
    dialogue_log = out.get("dialogue_log") or []

    # ---- Tier 0: deterministic floor -------------------------------------
    signals = _strip_blank_diff_placeholders(sd)
    for name in _untracked_restraint_subjects(
            resolved_event, dialogue_log, sd.get("conditions") or {},
            tracked_names):
        signals.append({
            "category": "conditions", "subject": name,
            "change": (f"{name} is under physical restraint/duress in the "
                       "prose but has no state_diff.conditions entry"),
            "evidence": "", "source": "restraint_scan",
        })
    for name in _untracked_unconsciousness_subjects(
            resolved_event, dialogue_log, sd.get("conditions") or {},
            tracked_names):
        signals.append({
            "category": "conditions", "subject": name,
            "change": (f"{name} is narrated as losing consciousness (knocked "
                       "out / unconscious / faints) but has no awareness "
                       "condition -- add a state_diff.conditions entry of "
                       "kind:'awareness' with state.level (unconscious|asleep|"
                       "sedated|dazed) for them"),
            "evidence": "", "source": "unconsciousness_scan",
        })

    claim_omissions, claim_notes, contract_warnings = _player_claim_findings(
        out, sd, interp, ctx.cast, sc)
    for warning in contract_warnings:
        ctx.add_warning(warning)

    # ---- Tier 1: the same-call manifest, checked deterministically -------
    manifest = _manifest_items(out)
    manifest_omissions = []
    for item in manifest:
        forms = _subject_match_forms(item["subject"], ctx.cast, sc)
        if not _evidence_present(sd, item, forms):
            manifest_omissions.append({**item, "_forms": forms})

    # Destruction tripwire (see _narrated_destruction_subjects): a named,
    # KNOWN place narrated as destroyed while the diff declares no
    # destruction and removes nothing. Deliberately warn-only and OUTSIDE
    # the Tier-2 repair routing -- a self-repair must never be talked into
    # fabricating a region cascade from a text heuristic.
    book_names = []
    try:
        book_names = [
            b.get("name") for b in lorebook_manifest(ctx.chat["id"])["books"]
            if b.get("name")
            and str(b.get("type") or "") in ("general", "world", "location",
                                             "vehicle")
        ]
    except Exception:
        pass  # candidate enrichment only; the scene-derived names still run
    destruction_flags = _narrated_destruction_subjects(
        resolved_event, dialogue_log, sd, sc, extra_names=book_names)
    for place in destruction_flags:
        ctx.add_warning(
            f"Possible unencoded destruction: resolved_event narrates the "
            f"destruction of {place!r} (a named, known place) but "
            "state_diff.destruction is null and remove_rooms/remove_entities "
            "do not cover it. The Phase-3b cascade only realizes a DECLARED "
            "destruction, so objective state still has this place fully "
            "intact while the prose claims otherwise."
        )

    recon = {
        "signals": [dict(s) for s in signals],
        "manifest": [dict(m) for m in manifest],
        "claim_notes": claim_notes,
        "destruction_scan": list(destruction_flags),
        "audited": False, "tripwire": False,
        "omissions": [], "repaired": False,
        "dispositions": [], "unresolved": [],
    }
    out["reconciliation"] = recon

    # Silent-false-negative tripwire: the beat provably did something
    # physical (successful dice, asserted effect-claims) yet the manifest
    # AND every physical diff category are empty. Metadata always; a deep
    # audit only when the operator opted in.
    claims = _dict_list(_dict(interp.get("flow")).get("authority_claims"))
    provably_physical = any(
        str(d.get("outcome") or "") == "success" for d in (dice or [])
    ) or any(str(c.get("scope") or "") == "effect" for c in claims)
    if provably_physical and not manifest and not _diff_is_substantive(sd):
        recon["tripwire"] = True

    deep_mode = _deep_audit_mode()
    run_deep = (
        deep_mode == "always"
        and (bool(signals) or _diff_is_substantive(sd)
             or _beat_has_physical_activity(interp, char_actions, dice))
    ) or (deep_mode == "tripwire" and recon["tripwire"])

    scene_slice = None
    dlog_compact = [
        {"speaker": d.get("speaker"), "exact_quote": d.get("exact_quote")}
        for d in dialogue_log[:20] if isinstance(d, dict)
    ]
    audit_omissions = []
    if run_deep:
        recon["audited"] = True
        scene_slice = _reconcile_scene_slice(
            sc, ctx.cast, ctx.get("_player_room"), sd)
        audit_omissions = _deep_audit_omissions(
            ctx, out, sd, scene_slice, dlog_compact, tracked_names, recon)

    omissions = signals + claim_omissions + manifest_omissions + audit_omissions
    recon["omissions"] = [_public_omission(o) for o in omissions]
    if not omissions:
        return

    # ---- Tier 2: bounded self-repair (the only common-path LLM spend,
    # and only on a real detected gap). One shot. -------------------------
    if scene_slice is None:
        scene_slice = _reconcile_scene_slice(
            sc, ctx.cast, ctx.get("_player_room"), sd)
    dispositions = []
    try:
        repair = _agent_json(
            "director", "resolve_repair",
            get_prompt("resolve_repair"),
            {
                "resolved_event": resolved_event,
                "dialogue_log": dlog_compact,
                "previous_state_diff": sd,
                "detected_omissions": [
                    {k: o.get(k) for k in ("category", "subject", "change",
                                           "evidence", "source")}
                    for o in omissions
                ],
                "non_rejectable_subjects": sorted({
                    o["subject"] for o in omissions
                    if o.get("source") == "player_claim" and o.get("subject")
                }),
                "prior_scene": scene_slice,
                "cast_names": tracked_names,
            },
            temperature=0.0,
        )
    except Aborted:
        raise
    except Exception as exc:
        ctx.add_warning(f"Resolve reconciliation repair failed: {exc}")
        repair = None

    if isinstance(repair, dict):
        patch = _normalize_diff_shape(repair.get("state_diff"))
        # A repair may not reintroduce the very noise this seam strips.
        _strip_blank_diff_placeholders(patch)
        patch["positions"] = canonicalize_positions(
            patch.get("positions") or {}, ctx.cast)
        _merge_repair_into_diff(sd, patch)
        dispositions = [d for d in (repair.get("dispositions") or [])
                        if isinstance(d, dict)]
        recon["repaired"] = True
        recon["dispositions"] = dispositions

    disp_by_subject = {
        _norm_subject(d.get("subject")): str(d.get("status") or "").casefold()
        for d in dispositions
    }

    for om in omissions:
        source = om.get("source")
        if source == "restraint_scan":
            continue  # re-checked precisely below, with the legacy wording
        forms = om.get("_forms") or _subject_match_forms(
            om.get("subject"), ctx.cast, sc)
        if source == "player_claim":
            encoded = _omission_subject_encoded(sd, om.get("subject"), forms)
        else:
            encoded = _evidence_present(sd, om, forms)
        if encoded:
            continue
        status = disp_by_subject.get(_norm_subject(om.get("subject")), "")
        if source == "player_claim":
            # NON-REJECTABLE: the player authority contract makes the effect
            # true; a disposition cannot argue it away -- only actual
            # post-merge evidence silences this warning.
            recon["unresolved"].append(
                {**_public_omission(om), "disposition": status or "none"})
            ctx.add_warning(
                "PLAYER AUTHORITY: "
                f"{om.get('change')} is not encoded in state_diff even "
                "after self-repair; objective state contradicts the "
                "player's asserted effect."
            )
            continue
        if source in ("manifest", "audit") and status in ("rejected",
                                                          "already_encoded"):
            # The owner overruled an emergent detection; conservatism says
            # believe the rejection rather than warn on a model-vs-model
            # disagreement.
            recon["unresolved"].append(
                {**_public_omission(om), "disposition": status})
            continue
        recon["unresolved"].append(
            {**_public_omission(om), "disposition": status or "none"})
        ctx.add_warning(
            "Resolve reconciliation: prose asserts "
            f"{om.get('change')!r} (subject {om.get('subject')!r}) but "
            "state_diff still does not encode it after self-repair; "
            "objective state may be stale."
        )

    # Restraint detector re-run against the FINAL merged diff: silent when
    # the repair encoded the condition, the exact legacy warning otherwise.
    for restraint_warning in _scan_for_untracked_restraint(
            resolved_event, dialogue_log, sd.get("conditions") or {},
            tracked_names):
        ctx.add_warning(restraint_warning)

def _resolve_movement_mover(sc, sd, mv, p_name):
    """Resolve movement.mover to the position subject the passable-route
    backstop should validate and write.

    Returns (subject_key, subject_room, mover_entity_id):
    - mover 'self'/empty/the player's own name -> (p_name, None, None);
      the caller resolves the player's room as before.
    - an entity id/name/alias found in the scene (or this beat's diff) ->
      (the positions key that entity is actually stored under, its current
      exterior room, its canonical entity id). Driving a vehicle moves the
      ENTITY's position; the player's body stays put.
    - anything unresolvable -> (None, None, None); the caller falls back
      to the player with a warning (the pre-mover behavior, safe default).
    """
    mover = str((mv or {}).get("mover") or "self").strip()
    if not mover or mover.casefold() in ("self", "player") \
            or mover.casefold() == str(p_name or "").casefold():
        return p_name, None, None
    entities = dict(sc.get("entities") or {})
    for eid, ent in (sd.get("entities") or {}).items():
        if isinstance(ent, dict):
            entities[eid] = ent
    positions = sc.get("positions") or {}
    mover_cf = mover.casefold()
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        forms = [str(eid), str(ent.get("name") or "")] + \
            [str(a) for a in (ent.get("aliases") or [])]
        forms = [f for f in forms if f.strip()]
        if mover_cf not in {f.casefold() for f in forms}:
            continue
        # Prefer the key the scene already stores this entity's position
        # under (id, name, or alias); default to the canonical id.
        key = next((f for f in forms if f in positions), str(eid))
        return key, positions.get(key), str(eid)
    return None, None, None

def _audit_fact_adjudications(ctx, out, interp):
    """Deterministic W2 backstop: every player-authored WORLD assertion --
    the actor-less `event` claims _extract_authority_claims mints (an
    offscreen death, 'two guards appear') -- must carry a
    fact_adjudications verdict (confirmed|contested|false) from the
    resolve, landing it on-page. The player's own on-page acts/effects are
    covered by claim_dispositions and need no adjudication; claims that
    only surface inside speech are prompt territory. Warn-only, matching
    the house pattern for prompt-compliance audits."""
    if not isinstance(out.get("fact_adjudications"), list):
        out["fact_adjudications"] = []
    adjudicated_ids = {
        str(fa.get("claim_id"))
        for fa in out["fact_adjudications"]
        if isinstance(fa, dict) and fa.get("claim_id")
    }
    claims = _dict(interp.get("flow")).get("authority_claims") or []
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id.endswith(":event"):
            continue
        if claim_id in adjudicated_ids:
            continue
        ctx.add_warning(
            f"Unadjudicated player-asserted fact {claim_id} "
            f"({str(claim.get('predicate') or claim.get('source_text') or '')[:80]!r}): "
            "director_resolve returned no fact_adjudications verdict "
            "(confirmed|contested|false) landing it on-page."
        )

def director_resolve(ctx, nonce):
    chat = ctx.chat
    interp = _dict(ctx.director_interpret)
    flow = _dict(interp.get("flow"))
    turn = ctx.turn
    pers = persona_of(chat)
    p_name = pers.get("name") or persona_name(pers)
    mapping = ctx.mapping_stage or ctx.mapping_quick or {}
    fm = fiction_model(chat["id"])
    clock = simulation_clock(chat["id"])

    dice = []
    for d in _dict_list(flow.get("dice")):
        seed = f"{chat['id']}:{turn['idx']}:{nonce}:{d.get('actor')}:{d.get('attempt')}"
        rng = random.Random(seed)
        roll = rng.randint(1, 20)
        mod = _ability_mod(d.get("actor"), d.get("ability"), ctx)
        dc = {"easy": 8, "medium": 12, "hard": 16, "extreme": 20}.get(
            str(d.get("difficulty", "medium")).lower(), 12)
        dice.append({
            **d, "seed": seed, "roll": roll, "modifier": mod,
            "dc": dc, "outcome": "success" if roll + mod >= dc else "failure",
            "margin": roll + mod - dc,
        })

    decls = []
    char_speech = {}
    char_actions = {}

    loop = ctx.interaction_loop or {}
    loop_declarations = loop.get("combined_declarations") or []

    # Include reaction results
    reaction_loop_result = ctx.reaction_loop or {}
    reaction_declarations = []
    for r_round in (reaction_loop_result.get("rounds") or []):
        rid = r_round.get("reactor_id")
        rname = r_round.get("reactor")
        rseq = (r_round.get("result") or {}).get("sequence") or []
        reaction_declarations.append({
            "char_id": rid, "name": rname, "sequence": rseq,
            "is_reaction": True,
            "speech": next((e.get("text") for e in rseq if e.get("type") == "speech"), None),
            "action": next((e for e in rseq if e.get("type") == "action"), None),
        })

    all_declarations = reaction_declarations + loop_declarations

    # Which character ids the reaction/interaction loops already speak for.
    # Any cast member with a character_results entry NOT covered here (a
    # parallel character:<id> step, including ones hydrated from an older
    # persisted plan shape) is merged below rather than silently dropped --
    # previously the mere presence of loop declarations made this function
    # ignore ctx.character_results entirely, so those characters' speech
    # never reached dialogue_log even though perception_outcome still
    # injected their actions.
    covered_ids = set()
    for declaration in all_declarations:
        try:
            covered_ids.add(int(declaration.get("char_id")))
        except (TypeError, ValueError):
            continue

    for declaration in all_declarations:
        char_id = declaration.get("char_id")
        name = declaration.get("name")
        sequence = declaration.get("sequence") or []
        decls.append({
            "char_id": char_id, "name": name, "sequence": sequence,
            "is_reaction": declaration.get("is_reaction", False),
            "speech": next((e.get("text") for e in sequence
                            if e.get("type") == "speech"), None),
            "action": next((e for e in sequence
                            if e.get("type") == "action"), None),
        })
        speeches = [{"text": e["text"], "volume": e.get("volume", "normal"),
                     "tone": e.get("tone", ""),
                     "visibility": e.get("visibility", "overt"),
                     "conceal_from": e.get("conceal_from") or []}
                    for e in sequence if e.get("type") == "speech" and e.get("text")]
        if speeches:
            char_speech.setdefault(name, []).extend(speeches)
        for event in sequence:
            if event.get("type") == "action" and event.get("attempt"):
                char_actions.setdefault(name, event)

    for c in ctx.cast:
        if int(c["id"]) in covered_ids:
            continue
        dk = ctx.character_results.get(c["id"])
        sh = json.loads(c["sheet"])
        cname = character_name(sh)
        if dk:
            decls.append({
                "char_id": c["id"],
                "name": dk.get("name") or cname,
                "sequence": dk.get("sequence") or [],
                "speech": dk.get("speech"), "action": dk.get("action"),
            })
            speeches = []
            for e in (dk.get("sequence") or []):
                if e.get("type") == "speech" and e.get("text"):
                    speeches.append({"text": e["text"],
                                     "volume": e.get("volume", "normal"),
                                     "tone": e.get("tone", ""),
                                     "visibility": e.get("visibility", "overt"),
                                     "conceal_from": e.get("conceal_from") or []})
            if not speeches and dk.get("speech"):
                speeches.append({"text": dk["speech"], "volume": "normal", "tone": "",
                                  "visibility": "overt", "conceal_from": []})
            if speeches:
                char_speech.setdefault(cname, []).extend(speeches)
            dk_act = dk.get("action") or {}
            if dk_act.get("attempt"):
                char_actions.setdefault(cname, dk_act)

    sc = get_scene(chat["id"], chat)
    raw_intents = wget(chat["id"], "standing_intentions", []) or []
    # Lazy import: commit.py owns the ledger's deterministic semantics
    # (OBLIGATION_OVERDUE_AGE, the commit-side re-deferral reminder); the
    # payload view is built there so the flag the prompt's hard rule keys
    # on and the flag commit warns on can never disagree.
    from commit import pending_obligation_view
    _mv_for_context = interp.get("movement")
    _mv_target = _mv_for_context.get("to_room") if isinstance(_mv_for_context, dict) else None

    # W5's light authority appraisal hint: each present person's evident
    # public role/standing (never private history), for the prompt's
    # AUTHORITY APPRAISAL rule -- an order across a standing gap is
    # contestable, not auto-executed.
    social_standing = {
        character_name(json.loads(c["sheet"])):
            (character_public_history(json.loads(c["sheet"])) or "")[:240]
        for c in ctx.cast
    }
    social_standing[p_name] = (persona_public_history(pers) or "")[:240]

    payload = {
        # Authored house style, for the prose and any world detail this stage
        # mints. director_interpret deliberately does NOT get it: that stage
        # reads what the player declared, and a style note there would bias
        # interpretation of the player's own words rather than shape new content.
        **({"style_guide": style_guide(chat["id"])}
           if style_guide(chat["id"]) else {}),
        "scene": {
            "location": sc.get("location"),
            # Filtered to nearby rooms for the payload only -- the
            # deterministic passable-route check below keeps using the
            # full, unfiltered `sc`.
            "rooms": _contextual_rooms(
                sc, ctx.cast, ctx.get("_player_room"), _mv_target,
            ),
            "entities": sc.get("entities"),
            "positions": sc.get("positions"),
            "attire": sc.get("attire"),
            "time": sc.get("time"),
        },
        "simulation_clock": clock,
        "paradox": paradox_visible_to(chat["id"], ctx.turn.frame_id),
        "fiction_model": fm,
        "fiction_frame": _dict(flow.get("fiction_frame")),
        "mapping_scene_proposal": _normalize_scene_patch(mapping.get("scene_patch")),
        "player_declaration": {
            "ABSOLUTE": True,
            "sequence": interp.get("sequence") or [],
            "speech": interp.get("speech"),
            "speech_volume": interp.get("speech_volume", "normal"),
            "action": interp.get("action"),
            "movement": interp.get("movement"),
            "abilities": persona_abilities(pers),
            "authority_claims": (interp.get("flow") or {}).get("authority_claims") or [],
        },
        "other_players_declarations": [
            {
                "persona_id": extra["persona_id"],
                "name": extra["name"],
                "ABSOLUTE": True,
                "sequence": (interp.get("other_players") or {}).get(str(extra["persona_id"]), {}).get("sequence") or [],
                "speech": (interp.get("other_players") or {}).get(str(extra["persona_id"]), {}).get("speech"),
                "action": (interp.get("other_players") or {}).get(str(extra["persona_id"]), {}).get("action"),
            }
            for extra in ctx.extra_players
        ],
        "character_declarations": decls,
        "character_abilities": {
            character_name(json.loads(c["sheet"])): character_abilities(json.loads(c["sheet"]))
            for c in ctx.cast
        },
        "dice_results_final": dice,
        "dialogue_mode": bool(flow.get("dialogue_mode", False)),
        "relevant_lore": lore_for(ctx),
        "standing_intentions": raw_intents[:12],
        "pending_obligations": pending_obligation_view(chat["id"], turn["idx"]),
        "social_standing": social_standing,
        # Player-authored future beats scheduled earlier and due NOW: enact them
        # as occurring this beat (see director_interpret). commit re-queues any
        # left unresolved rather than dropping them.
        "due_authored_events": (ctx.director_interpret or {}).get("due_authored_events") or [],
        # See director_interpret: already-completed mechanical transitions
        # (timed arrivals) the prose should acknowledge, not re-resolve.
        "engine_notices": wget(chat["id"], "engine_notices", []),
        "interaction_rounds": loop.get("rounds") or [],
        "reaction_rounds": (ctx.reaction_loop or {}).get("rounds") or [],
        "variant_seed": nonce,
    }

    out = _agent_json(
        "director",
        "director_resolve",
        get_prompt("director_resolve"),
        payload,
        temperature=0.5,
        max_tokens=16000,
    )

    # Warning-only re-normalization; strict validation already ran inside
    # _agent_json (see director_establish above).
    out, warnings = validate_llm_output("director_resolve", out)
    ctx.warnings.extend(warnings)

    # Safety net: LLM sometimes returns a string/list where an object belongs.
    sd = _normalize_diff_shape(out.get("state_diff"))
    # Same canonicalization as director_establish: fold any uid/normalized-name
    # position key for a cast member onto the registered name before it reaches
    # perception's mid-turn merge or the commit boundary.
    sd["positions"] = canonicalize_positions(sd["positions"], ctx.cast, player_name=p_name)
    out["state_diff"] = sd
    out["dice"] = dice if isinstance(dice, list) else []

    staged = ((ctx.get("mapping_stage") or {}).get("staged_lore") or []) + \
             ((ctx.get("mapping_quick") or {}).get("staged_lore") or [])
    mv = interp.get("movement")
    target_room = mv.get("to_room") if isinstance(mv, dict) else None

    # Who is actually relocating this beat (movement.mover): the player's
    # own body, or a vehicle the player is driving/piloting. Resolved once
    # here and used by both the staged-layout adjacency fallback and the
    # passable-route backstop below -- without it, "I drive the van onto
    # the ferry" was structurally identical to walking there and moved the
    # player's body instead of the van.
    move_subject = mover_room = mover_eid = None
    if isinstance(mv, dict) and mv.get("to_room"):
        move_subject, mover_room, mover_eid = _resolve_movement_mover(
            sc, sd, mv, p_name)
        if move_subject is None:
            ctx.warnings.append(
                f"movement.mover {mv.get('mover')!r} does not resolve to a "
                "known entity; treating the move as the player's own."
            )
            move_subject, mover_room, mover_eid = p_name, None, None
    subject_prev_room = mover_room if mover_eid else room_of(sc, p_name)

    for entry in staged:
        if entry.get("category") == "layout" and entry.get("content"):
            room_id = target_room or (entry.get("keys") or "").split(",")[0].strip().replace(" ", "_")
            if room_id and room_id not in sd["rooms"]:
                prev_room = subject_prev_room
                adj = []
                if prev_room:
                    adj.append({"to": prev_room, "barrier": "open", "distance": "near"})
                sd["rooms"][room_id] = {
                    "name": room_id.replace("_", " ").title(),
                    "desc": entry["content"], "adjacent": adj,
                    "notes": entry["content"][:500],
                }

    if isinstance(mv, dict) and mv.get("to_room"):
        # director_interpret derives `movement` purely from the LLM's
        # reading of the player's declared intent, with no adjacency
        # check. Without a deterministic backstop here, a misparsed
        # declaration can teleport the mover through a wall or into a
        # disconnected room. Only commit the move if a passable route
        # exists from the MOVER's current room (or that room is unknown,
        # in which case there is nothing to validate against).
        #
        # Validate against this beat's WOULD-BE merged scene, built the
        # same way commit builds it (merge_scene_with_diff deep-copies its
        # inputs -- nothing persisted is mutated). That merge recomputes
        # derived dock/portal edges, so a vehicle that docks THIS beat
        # already exposes its interior->destination doorway here and an
        # occupant can step out on the same beat it arrives -- previously
        # the dock edge only appeared at commit, AFTER this check, so the
        # same-beat deboard was wrongly blocked.
        route_scene = merge_scene_with_diff(sc, sd)
        known_rooms = route_scene["rooms"]
        prev_room = subject_prev_room
        blocked = contested = False
        rel = None
        if prev_room and mv["to_room"] != prev_room:
            rel = spatial_rel(route_scene, prev_room, mv["to_room"])
            if rel.get("barrier") == "separated":
                # Not directly adjacent. A multi-room walk whose every
                # doorway is ALREADY passable (open/open_door) is a
                # legitimate single-beat traversal, not a teleport --
                # observed live: a valid three-hop walk through open doors
                # was dropped while the narration described arriving. A
                # route that would require passing a still-closed door
                # does NOT count: the backstop cannot attribute the
                # contest to one specific door on a multi-hop path, so
                # such a move stays blocked until the door is opened (a
                # door the resolve opens this beat is already open in
                # route_scene and makes the route passable).
                blocked = not passable_route_exists(
                    route_scene, prev_room, mv["to_room"])
            else:
                # Directly adjacent: the single edge's barrier decides.
                blocked = rel.get("barrier") in ("wall", "unknown")
                # route_scene already carries this beat's diff, so a door
                # the resolve opened this beat reads open_door here.
                # Still-closed means the move is CONTESTED: crossing
                # requires an action whose outcome the resolve owns.
                contested = rel.get("barrier") == "closed_door"
        if blocked:
            ctx.warnings.append(
                f"Blocked movement: no passable route from '{prev_room}' to "
                f"'{mv['to_room']}' (barrier={rel.get('barrier')}); position unchanged."
            )
            # The resolve LLM may itself have asserted the impossible move;
            # a blocked route must strip it, not just warn.
            if sd["positions"].get(move_subject) == mv["to_room"]:
                sd["positions"].pop(move_subject)
        elif contested and sd["positions"].get(move_subject) != mv["to_room"]:
            # Don't force interpret's declared intent through a door that is
            # still closed after this beat's diff -- observed live as the
            # narration describing a bump against a sealed door while the
            # committed position walked through it. The resolve diff owns
            # contested outcomes; without its assertion, no move.
            ctx.warnings.append(
                f"Contested movement: barrier closed_door from '{prev_room}' "
                f"to '{mv['to_room']}' not opened this beat and the resolve "
                "diff did not assert the move; position unchanged."
            )
        else:
            sd["positions"][move_subject] = mv["to_room"]

        if mover_eid is not None:
            # Driver-conflation guard: a vehicle move relocates the ENTITY;
            # the player stays in its interior (carried implicitly -- the
            # interior rooms travel with the vehicle by identity, and the
            # dock edges recompute from the entity's new position at
            # merge). A resolve diff that ALSO moved the player's body to
            # the vehicle's destination while they sit inside it is the
            # exact conflation this field exists to prevent -- strip it.
            player_room_now = room_of(sc, p_name)
            interior = {
                rid for rid, room in known_rooms.items()
                if isinstance(room, dict)
                and room.get("parent_entity") == mover_eid
            }
            if sd["positions"].get(p_name) == mv["to_room"] \
                    and player_room_now in interior:
                sd["positions"].pop(p_name, None)
                ctx.warnings.append(
                    f"Vehicle movement (mover={mover_eid!r}): stripped a "
                    f"resolve-asserted move of {p_name!r} to "
                    f"'{mv['to_room']}' -- the player rides inside the "
                    "vehicle's interior; only the vehicle's position moves."
                )

    if not out.get("resolved_event"):
        parts = []
        p_action = interp.get("action") or {}
        if interp.get("speech"):
            parts.append(f"{p_name} speaks")
        if p_action.get("attempt"):
            parts.append(f"{p_name} attempts to {p_action['attempt']}")
        for cname in char_speech:
            parts.append(f"{cname} speaks")
        for cname, cact in char_actions.items():
            parts.append(f"{cname} attempts to {cact.get('attempt', '')}")
        for d in dice:
            parts.append(f"{d.get('actor', 'someone')} "
                         f"({d['roll']}+{d['modifier']} vs {d['dc']}: {d['outcome']})")
        out["resolved_event"] = ". ".join(parts) if parts else "Nothing notable occurs."

    if not out.get("summary"):
        out["summary"] = (out.get("resolved_event") or "")[:200]

    dlog = out.get("dialogue_log") or []

    # The prompt now explicitly invites the director to voice unsheeted
    # background presences (see prompts.py's DIALOGUE LOG instruction),
    # but that license is scoped to entities with no character sheet --
    # a REGISTERED cast member speaks only through their own character_
    # step declaration (char_speech, built above from actual character_
    # results/interaction_loop/reaction_loop output), never through the
    # director inventing additional lines for them. Drop any dialogue_log
    # entry attributed to a cast member whose exact_quote doesn't appear
    # in that character's own declared speech -- a deterministic backstop
    # regardless of how well the prompt's scoping is actually followed.
    cast_names_lower = {
        character_name(json.loads(c["sheet"])).casefold() for c in ctx.cast
    }
    char_speech_bodies = {
        cname.casefold(): {_quote_body(s["text"]) for s in speeches}
        for cname, speeches in char_speech.items()
    }
    # PLAYER-SPEECH AUTHORITY: the Director may never author the player's
    # words. The same backstop as the cast check below, applied to the player:
    # observed live (Elevator Adventure t42) the director took the player's
    # wordless cry "AaUaa!" and silently ADDED a second player line, an
    # invented refusal "Can't... not now...", to dialogue_log -- which then
    # propagated as canonical player speech through perception -> narrator ->
    # memory. Any player-attributed entry whose quote is not among the player's
    # OWN declared speech this beat is dropped.
    player_speech_bodies = {_quote_body(s) for s in player_speech_lines(interp)}

    # PLAYER-ACT AUTHORITY: the speech guard below covers the player's WORDS;
    # this covers their CONDUCT. Elaborating a declared act is legitimate and
    # is not flagged -- only an act appearing on a beat where the player
    # declared none, which is invented by construction and replays when they
    # actually declare it later (see _check_player_act_authority).
    _declared_player_actions = [
        e for e in (interp.get("sequence") or [])
        if isinstance(e, dict) and e.get("type") == "action"
        and (e.get("attempt") or e.get("observable"))
    ]
    for _w in _check_player_act_authority(
        out.get("resolved_event") or "",
        _declared_player_actions,
        persona_name(pers) if pers else "",
    ):
        ctx.add_warning(_w)
    checked_dlog = []
    for d in dlog:
        speaker = d.get("speaker") or ""
        speaker_cf = str(speaker).casefold()
        if speaker_cf in cast_names_lower:
            body = _quote_body(d.get("exact_quote", ""))
            if body not in char_speech_bodies.get(speaker_cf, set()):
                ctx.add_warning(
                    f"Dropped director-invented dialogue line for "
                    f"registered character {d.get('speaker')!r}: not "
                    "present in their own declared speech."
                )
                continue
        elif is_player_speaker(speaker, chat):
            body = _quote_body(d.get("exact_quote", ""))
            if body not in player_speech_bodies:
                ctx.add_warning(
                    f"Dropped director-invented dialogue line for the PLAYER "
                    f"{speaker!r}: not in the player's declared speech "
                    "(player-speech authority)."
                )
                continue
        checked_dlog.append(d)
    dlog = checked_dlog

    # Deterministic concealment backstop: the director model is asked to
    # carry visibility/conceal_from/volume onto each dialogue_log entry,
    # but that is prompt compliance and has proven unreliable elsewhere in
    # this engine (see spatial 'zone' tagging) -- and live play confirmed
    # it here too: a whisper declared on the original sequence element
    # came back as dialogue_log volume:'normal', which would have let
    # hear_level() carry a 200-meter-shaft whisper as if it were spoken at
    # normal volume. The true attributes of a line are whatever the
    # ORIGINAL speech declaration (player sequence, or a character's own
    # sequence) said -- always trust that over whatever the director
    # transcribed, keyed by (speaker, quote body) so a dropped/altered
    # dialogue_log tag can never leak concealed or quieted speech.
    speech_concealment = {}
    for e in (interp.get("sequence") or []):
        if e.get("type") == "speech" and e.get("text"):
            speech_concealment[(p_name.casefold(), _quote_body(e["text"]))] = (
                e.get("visibility", "overt"), e.get("conceal_from") or [],
                e.get("volume", "normal"))
    for cname, speeches in char_speech.items():
        for s in speeches:
            speech_concealment[(cname.casefold(), _quote_body(s["text"]))] = (
                s.get("visibility", "overt"), s.get("conceal_from") or [],
                s.get("volume", "normal"))

    existing_bodies = set()

    for d in dlog:
        d.setdefault("volume", "normal")
        d.setdefault("intended_target", None)
        d.setdefault("tone", "")
        if is_player_speaker(d.get("speaker", ""), chat):
            d["speaker"] = p_name
        body = _quote_body(d.get("exact_quote", ""))
        key = (str(d.get("speaker") or "").casefold(), body)
        if key in speech_concealment:
            d["visibility"], d["conceal_from"], d["volume"] = speech_concealment[key]
        else:
            d.setdefault("visibility", "overt")
            d.setdefault("conceal_from", [])
        if body:
            existing_bodies.add(body)

    for line in player_speech_lines(interp):
        body = _quote_body(line)
        if body and body not in existing_bodies:
            vis, cf, vol = speech_concealment.get(
                (p_name.casefold(), body), ("overt", [], interp.get("speech_volume", "normal")))
            dlog.append({"speaker": p_name, "exact_quote": line,
                         "volume": vol,
                         "intended_target": None, "tone": "",
                         "visibility": vis, "conceal_from": cf})
            existing_bodies.add(body)

    for cname, speeches in char_speech.items():
        for s in speeches:
            body = _quote_body(s["text"])
            if body and body not in existing_bodies:
                dlog.append({"speaker": cname, "exact_quote": s["text"],
                             "volume": s.get("volume", "normal"),
                             "intended_target": None, "tone": s.get("tone", ""),
                             "visibility": s.get("visibility", "overt"),
                             "conceal_from": s.get("conceal_from") or []})
                existing_bodies.add(body)

    for d in dlog:
        eq = d.get("exact_quote", "")
        if eq and not (eq.startswith('"') or eq.startswith("'")
                       or eq.startswith('\u201c') or eq.startswith('\u201d')):
            d["exact_quote"] = '"' + eq + '"'

    seen_quotes = {}
    deduped = []
    for d in dlog:
        key = (str(d.get("speaker") or "").lower().strip(),
               _quote_body(d.get("exact_quote", "")),
               str(d.get("intended_target") or "").lower().strip())
        if key in seen_quotes:
            old_idx = seen_quotes[key]
            old = deduped[old_idx]
            if not old.get("tone") and d.get("tone"):
                deduped[old_idx] = d
            continue
        seen_quotes[key] = len(deduped)
        deduped.append(d)

    out["dialogue_log"] = deduped

    tracked_names = [
        character_name(json.loads(c["sheet"])) for c in ctx.cast
    ] + [p_name]

    # W2 backstop: warn on any player-authored world assertion the resolve
    # left in assertion limbo (no confirmed/contested/false verdict).
    _audit_fact_adjudications(ctx, out, interp)

    # One general prose-vs-diff reconciliation pass (subsumes the old
    # warn-only restraint backstop): deterministic placeholder floor,
    # gated omission audit, bounded Director self-repair, warnings for
    # whatever remains unencoded. See the seam's block comment above.
    _reconcile_resolution(ctx, out, sc, interp, char_actions, dice,
                          tracked_names)

    return out
