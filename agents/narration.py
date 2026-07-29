"""Player-facing narration agent."""

from __future__ import annotations

import contextvars
import json
from concurrent.futures import ThreadPoolExecutor

from db import get_setting, q, wget, wset
from prompts import get_prompt
from scene import (
    NON_AWAKE_GATED,
    apply_awareness_diff,
    awareness_map,
    awareness_of,
    persona_of,
    get_scene,
)
import os
import re

from spatial import (
    containment_conceals,
    entity_arc,
    has_visual,
    room_of,
    spatial_digest,
    spatial_facts,
    spatial_rel,
    visible_adjacent_rooms,
    visual_level_between,
)


def _spatial_facts_field(scene, observer):
    """Env-gated (SPATIAL_SCAFFOLD=1) deterministic ground-truth spatial facts
    for the narrator. Off by default -> {} (no payload change, baseline
    behavior). On -> {'spatial_facts': [...]} the narrator is told not to
    contradict. Sources are everyone co-located with the observer."""
    if not os.environ.get("SPATIAL_SCAFFOLD"):
        return {}
    o_room = room_of(scene, observer)
    positions = scene.get("positions") or {}
    names = [n for n, r in positions.items() if r == o_room and n != observer]
    facts = spatial_facts(scene, observer, names)
    return {"spatial_facts": facts} if facts else {}
from schemas import validate_llm_output

from character_schema import character_appearance, character_name

from .common import (
    _agent_json,
    _already_established_phrases,
    _cap_repeated_quotes,
    _overused_phrases,
    _check_narrator_fidelity,
    _dedupe_view_sentences,
    _narration_person_counts,
    _protected_view_quotes,
    _quote_body,
    _recognizes,
    _strip_identity_tokens,
    _strip_player_echo,
    _unknown_actor_label,
    cast_room,
    character_scene_keys,
    observable_action_text,
    player_speech_lines,
)

def _resolve_narration_person(chat_id, raw_input, player_name, player_pronouns,
                              key="narration_person", pending=None):
    """Which grammatical person renders the player character this turn.
    Detection is per-turn (a player can switch style mid-campaign), but a
    turn with no clear signal -- pure dialogue with no narrative frame, e.g.
    just a quoted line -- falls back to whatever was last established rather
    than snapping back to a default and creating whiplash mid-scene.

    Once a person is established, flipping it requires a DECISIVE signal (the
    winner leading the runner-up by >= 2), not just a bare majority. This is
    the hysteresis that stops a single stray token -- one unquoted "you"
    addressed to an NPC, one sentence-initial name that doubles as a verb --
    from silently switching the whole campaign's narration voice, which is
    exactly the flakiness heuristic person-detection is prone to. `key` lets
    additional human players each keep their own established convention.

    `pending`: when a dict is supplied, the newly established/overridden
    person is RECORDED there ({key: person}) instead of written durably --
    the narrator stages stash it on their returned step content so that
    commit.py (the sole persistence boundary) applies the wset at commit
    time; model-era output stays provisional until then. Without `pending`
    the write happens immediately (direct/legacy callers).
    """
    def _record(value):
        if pending is None:
            wset(chat_id, key, value)
        else:
            pending[key] = value

    counts = _narration_person_counts(raw_input, player_name, player_pronouns)
    best = max(counts, key=counts.get)
    top = counts[best]
    runner = max((v for k, v in counts.items() if k != best), default=0)
    detected = best if (top > 0 and top > runner) else None
    stored = wget(chat_id, key, None)

    if detected is None:
        return stored or "second"
    if stored is None or detected == stored:
        if detected != stored:
            _record(detected)
        return detected
    # Established, and this turn disagrees: only override on a decisive lead.
    if top - runner >= 2:
        _record(detected)
        return detected
    return stored

# Only dropped/altered dialogue is worth the cost of an automatic rewrite --
# it's an ABSOLUTE-tier violation (a player-visible line silently vanishing
# or changing), and forcing a second full narrator call on every occurrence
# doubles that stage's latency. Content-reuse is a softer quality issue (the
# model recycled prior prose instead of describing this turn) that doesn't
# warrant paying that cost automatically; it stays visible via
# fidelity_warnings for manual review instead. Missing-proper-noun warnings
# were never in this list -- that check has real false positives (e.g. a
# location's own name appearing in scenario/lore text the player would never
# actually say aloud).
_ENFORCEABLE_PREFIXES = (
    "Dialogue from view missing or altered",
    # A cast member's pronouns flipping mid-scene is the same tier of failure
    # as a dropped line -- the reader sees a character silently change -- and
    # the check that raises it (agents/common.py's _check_pronoun_fidelity)
    # only fires on unambiguous flips, so it is cheap enough to enforce.
    "Pronoun mismatch for",
    # PERSON DISCIPLINE is called an ABSOLUTE, hard error by the narrator
    # prompt itself, and the check that raises it (agents/common.py's
    # _check_player_person) only fires on the player's literal name outside
    # quoted dialogue -- unambiguous enough to spend a rewrite on.
    "Player named in third person",
    # F1: a response rendered before its stimulus breaks causality on the
    # page; the check (_check_event_order) fires only on a strict verbatim
    # position inversion between two located quotes.
    "Dialogue rendered out of order",
    # F4: a tracked mind's line reading as an anonymous body's is silent
    # misattribution; the check (_check_quote_attribution) fires only when a
    # DIFFERENT speaker's reference is positively nearest.
    "Quote attributed to wrong speaker",
    # F2: an unmoved character re-located by prose alone is a continuity
    # break the reader sees (_check_position_fidelity).
    "Character placed in wrong room",
    # F3: a shut portal rendered open (or vice versa) contradicts committed
    # world state (_check_portal_fidelity).
    "Portal state contradicts the scene",
)

# Deterministic craft screen: AI-tell phrases the PROSE CRAFT prompt bans. A
# draft containing any triggers ONE rewrite naming them (reusing the correction
# loop). Conservative -- only clear tells, to avoid false positives on ordinary
# prose. Dialogue is exempt (quotes are fixed); we scan the whole draft but the
# patterns don't match normal speech.
_CRAFT_TELLS = [
    (r"\bshift(?:s|ed|ing)?\s+(?:her|his|their|my|its)\s+weight\b", "shifts weight"),
    (r"\beyes?\s+flick(?:s|ed|ing)?\b", "eyes flick"),
    (r"\btake[sn]?\s+the\s+(?:\w+\s+){1,2}in\b(?!\s+(?:his|her|their|both|one|two)\s+hands?)",
     "'take the room in' (filtering)"),
    (r"\btak(?:e|es|ing)\s+in\s+the\s+\w+\b", "'take in the room' (filtering)"),
    (r"\bI'?m\s+aware\s+of\b", "'I'm aware of' (filtering)"),
    (r"\bwash(?:es|ed)?\s+over\s+(?:me|you|him|her|them|us)\b", "washes over (emotion)"),
    (r"\bhang(?:s|ing|ed)?\s+in\s+the\s+air\b|\bhung\s+in\s+the\s+air\b", "hangs in the air"),
    (r"\bmiddle\s+distance\b", "middle distance"),
    (r"\bfull\s+height\b", "full height"),
    (r"\bclose\s+air\b", "the close air"),
    (r"\b(?:deliberate|deliberately|unhurried|unhurriedly|pointedly|casually)\b",
     "adverb tell (deliberate/unhurried/pointedly/casually)"),
    (r"\bslow\s+and\s+steady\b", "slow and steady"),
    (r"\b(?:muted|soft|softly|dim|dimly|faint|faintly|diffused|warm|low)\s+"
     r"(?:\w+\s+){0,2}(?:glow|glimmer|gleam|light|murmur|hum|clink|drone)\b",
     "generic muted/dim + light/sound"),
]


def _craft_tells(prose: str) -> list:
    """Banned AI tells present in a narrator draft (deduped, ordered). Quoted
    dialogue is masked before scanning -- quotes are fixed (reproduced verbatim),
    so a tell inside a spoken line is not the narrator's prose and could never be
    rewritten away, which would burn a pointless retry every turn."""
    if not prose:
        return []
    # Mask curly-quoted dialogue too -- models routinely emit it, and every
    # other dialogue regex in the pipeline (agents/common.py) accepts it; a
    # tell inside curly quotes would otherwise burn unwinnable retries.
    scan = re.sub(r'"[^"]*"|“[^“”]*”', " ", prose)
    found = []
    for pat, label in _CRAFT_TELLS:
        if re.search(pat, scan, re.I):
            found.append(label)
    return list(dict.fromkeys(found))

def _cast_pronouns(cast):
    """Authoritative pronouns per cast member, so the narrator renders each
    named character in third person with their GIVEN pronouns instead of
    guessing from the name (which flipped Vorne he/she across beats). W6.
    Also the reference the deterministic pronoun-fidelity check scores against
    (agents/common.py's _check_pronoun_fidelity)."""
    out = {}
    for row in (cast or []):
        try:
            ident = (json.loads(row["sheet"]).get("identity") or {})
        except Exception:
            continue
        name = str(ident.get("name") or "").strip()
        pronouns = ident.get("pronouns") or {}
        clean = {k: pronouns[k] for k in ("subject", "object", "possessive")
                 if isinstance(pronouns, dict) and pronouns.get(k)}
        if name and clean:
            out[name] = clean
    return out


def _speaker_display(name, recognized, appearance=None, aliases=None):
    """How the narrator payload refers to one speaker: the canonical name when
    the player recognizes them (rank/title variants included -- same
    _recognizes rule perception used to build the view), else the same
    appearance-derived anonymous label perception injects, so the binding
    never leaks an identity past the view's own gate."""
    if _recognizes(name, recognized):
        return name
    stripped = _strip_identity_tokens(appearance, [name, *(aliases or [])]) \
        or None
    return _unknown_actor_label(name, stripped, aliases)


def _ordered_beat_events(ctx, p_name, view, recognized, cast_info):
    """F1/F4: the pipeline's own numbered causal record of this beat, built
    from step order + the loop call sequences (stimulus -> response pairs):
    player declaration first, then reaction rounds, then interaction rounds in
    call order, then parallel character declarations, then background
    reactions. Info-barrier: an NPC line enters ONLY if its quote actually
    reached the player's view; speakers render under the same display
    (name or anonymous label) the view used."""
    raw = []
    di = ctx.get("director_interpret") or {}
    for e in (di.get("sequence") or []):
        if not isinstance(e, dict):
            continue
        if e.get("type") == "speech" and e.get("text"):
            raw.append((p_name, "speech", e["text"]))
        elif e.get("type") == "action":
            surface = observable_action_text(e)
            if surface:
                raw.append((p_name, "action", surface))

    def _seq_speech(name, seq):
        for e in seq or []:
            if isinstance(e, dict) and e.get("type") == "speech" \
                    and e.get("text"):
                raw.append((name, "speech", e["text"]))

    covered = set()
    for r in (ctx.reaction_loop or {}).get("rounds") or []:
        _seq_speech(r.get("reactor"), (r.get("result") or {}).get("sequence"))
        try:
            covered.add(int(r.get("reactor_id")))
        except (TypeError, ValueError):
            pass
    for r in (ctx.interaction_loop or {}).get("rounds") or []:
        _seq_speech(r.get("speaker"), (r.get("result") or {}).get("sequence"))
        try:
            covered.add(int(r.get("speaker_id")))
        except (TypeError, ValueError):
            pass
    for c in ctx.cast:
        try:
            cid = int(c["id"])
        except (TypeError, ValueError):
            continue
        if cid in covered:
            continue
        d = ctx.character_results.get(c["id"]) \
            or ctx.character_results.get(cid)
        if not isinstance(d, dict):
            continue
        name = d.get("name")
        _seq_speech(name, d.get("sequence"))
        if not (d.get("sequence")) and d.get("speech"):
            raw.append((name, "speech", d["speech"]))
    br = ctx.get("background_react") or {}
    reactions = br.get("reactions")
    if reactions is None:
        reactions = ([br] if br.get("fired") and br.get("dialogue_log_entry")
                     else [])
    for r in reactions:
        entry = (r or {}).get("dialogue_log_entry") or {}
        if entry.get("exact_quote") and entry.get("speaker"):
            raw.append((entry["speaker"], "speech", entry["exact_quote"]))

    view_norm = re.sub(r"\s+", " ", str(view or "")).casefold()
    events = []
    for name, kind, text in raw:
        if not name:
            continue
        if kind == "speech" and name != p_name:
            body = re.sub(r"\s+", " ", _quote_body(text)).casefold()
            if not body or body not in view_norm:
                continue  # the player never received this line
        info = cast_info.get(name) or {}
        display = name if name == p_name else _speaker_display(
            name, recognized, info.get("appearance"), info.get("aliases"))
        ev = {"n": len(events) + 1, "actor": display, "kind": kind}
        if kind == "speech":
            ev["quote"] = text
        else:
            ev["action"] = text
        events.append(ev)
    return events


def _player_sees_character(scene, p_name, p_room, name, now_room):
    """S3-A4: can the player actually SEE this co-present character this beat.

    Co-location is not perception. A character standing in the player's
    pitch-dark room, sealed inside a closed container, or in the player's rear
    blind spot is not seen, and the audit's case was exactly that: an entrant
    into the player's pitch-dark room arriving in the narrator payload as an
    enforced fact.

    Body-level (`visual_level_between`) whenever BOTH bodies are literally in
    `scene.positions`, so a carried light counts: standing in a lamp's pool in
    an otherwise dark room IS seen. When either is not (the player's room came
    from `ctx['_player_room']`, or the character is stored under a uid/alias
    key `cast_room` resolved) fall back to the room-level answer rather than
    denying outright -- over-denial here would drop a plainly visible
    co-present character out of ordinary narration, which is the failure mode
    this gate must not create.
    """
    if not name or not p_room:
        return False
    if containment_conceals(scene, p_name, name):
        return False
    # None = no facing/bearing basis, which fails open per entity_arc's own
    # contract; only a positive 'rear' is a blind spot.
    if entity_arc(scene, p_name, name) == "rear":
        return False
    if room_of(scene, p_name) and room_of(scene, name):
        return visual_level_between(scene, p_name, name) != "none"
    return has_visual(spatial_rel(scene, p_room, now_room or p_room))


def _position_delta_payload(ctx, chat, p_name, p_room, recognized, cast_info):
    """F2: each co-present cast member's position delta this beat
    (prev committed room -> this beat's room, plus a moved flag). Returns
    (payload_view, check_facts, room_display_names). Scoped to characters the
    player can place: co-present now AND actually perceptible (see
    `_player_sees_character`)."""
    prev_sc = get_scene(chat["id"], chat)
    sc = ctx.get("outcome_scene") or prev_sc
    rooms = sc.get("rooms") or {}
    room_names = {
        rid: str((r or {}).get("name") or rid.replace("_", " ").title())
        for rid, r in rooms.items() if isinstance(r, dict) or r is None
    }
    payload, facts = {}, []
    for name, info in cast_info.items():
        prev_room = cast_room(prev_sc, name, ctx.cast)
        now_room = cast_room(sc, name, ctx.cast)
        if not now_room:
            continue
        # S3-A4: only include characters currently IN the player's room.
        # Previously, a character who LEFT (prev_room == p_room but now_room
        # != p_room) was included with their destination room name, leaking
        # spatial info the player hasn't perceived. The player can only
        # place someone who is still co-present -- a character who left is
        # gone, and their destination is not the player's to know.
        if not p_room or now_room != p_room:
            continue
        # S3-A4 (second half): co-location alone was the whole gate, so a
        # character who ENTERED the player's pitch-dark room still arrived
        # here with moved=True. The narrator prompt's POSITION CONTINUITY
        # rule then invites rendering them and _check_narrator_fidelity
        # ENFORCES prose agreement, turning an unperceived body into a
        # required sentence.
        if not _player_sees_character(sc, p_name, p_room, name, now_room):
            continue
        moved = (prev_room is None) or (prev_room != now_room)
        # Where they came FROM is a separate perception from the fact that
        # they are here now: seeing someone walk in tells you nothing about
        # the room behind the door. Name the origin only when the player can
        # see into it (barrier + light, via has_visual). Otherwise the entry
        # still ships -- the player sees the arrival -- with no origin.
        prev_display = None
        if moved and prev_room and has_visual(
                spatial_rel(sc, p_room, prev_room)):
            prev_display = room_names.get(prev_room, prev_room)
        display = _speaker_display(
            name, recognized, info.get("appearance"), info.get("aliases"))
        payload[display] = {
            "room": room_names.get(now_room, now_room),
            "prev_room": prev_display,
            "moved": moved,
        }
        facts.append({"name": display, "room_id": now_room, "moved": moved})
    return payload, facts, room_names


def _visible_portal_states(scene, room_id, visible_rooms=None):
    """F3: committed open/shut state of every door/portal the player can
    currently see, keyed by display name -- portal-link entities touching the
    player's room, door-like entities in it, transit hatches of an enclosure
    the player is in or beside, and this room's door adjacency barriers. A
    generic 'doors' entry is added only when every visible door-state
    agrees, so 'through the open doors' is checkable without a named
    entity (the DW t12 case).

    S3-A5: ``visible_rooms`` (the player's room plus any visible adjacent
    rooms) gates which portal states are included.  A portal/door in a
    room the player cannot see is withheld -- the player has not
    perceived it and must not be told its state.  When ``visible_rooms``
    is None (backwards-compatible callers) the behaviour is unchanged
    (only the player's own room is considered)."""
    if not room_id or not isinstance(scene, dict):
        return {}
    # Build the set of rooms whose portal states the player may perceive.
    # When visible_rooms is None (backwards-compatible callers), only the
    # player's own room is considered and adjacency barriers are NOT
    # filtered (preserving the original behavior).
    _filter_adjacent = visible_rooms is not None
    if visible_rooms is None:
        visible_rooms = {room_id}
    else:
        visible_rooms = set(visible_rooms) | {room_id}
    out = {}
    entities = scene.get("entities") or {}
    positions = scene.get("positions") or {}
    rooms = scene.get("rooms") or {}
    interior_owner = {
        rid: (r or {}).get("parent_entity")
        for rid, r in rooms.items() if isinstance(r, dict)
    }
    for eid, ent in entities.items():
        if not isinstance(ent, dict):
            continue
        name = str(ent.get("name") or eid).strip()
        state = ent.get("state") if isinstance(ent.get("state"), dict) else {}
        link = state.get("link")
        if isinstance(link, dict) and room_id in (link.get("rooms") or []):
            # S3-A5: a portal-link that also touches a room the player
            # cannot see still leaks state through the visible end.
            # Only include if every room the portal connects is visible.
            # Backwards-compatible callers (visible_rooms=None) skip this
            # check (original behavior).
            if _filter_adjacent:
                portal_rooms = set(link.get("rooms") or [])
                if portal_rooms and not portal_rooms.issubset(visible_rooms):
                    continue
            out[name] = ("open" if str(link.get("phase") or "").lower()
                         == "open" else "shut")
            continue
        ent_room = positions.get(eid) or positions.get(name)
        transit = state.get("transit")
        if isinstance(transit, dict) and transit.get("hatch"):
            if ent_room == room_id or interior_owner.get(room_id) == eid:
                hatch = str(transit.get("hatch") or "").lower()
                out[f"{name} hatch"] = "open" if hatch == "open" else "shut"
            continue
        blob = (str(ent.get("kind") or "") + " " + name).lower()
        # S3-A5: only include door-like entities positioned in a visible room.
        # Backwards-compatible callers (visible_rooms=None) use the original
        # behavior (ent_room == room_id only).
        ent_room_check = ent_room in visible_rooms if _filter_adjacent else ent_room == room_id
        if ent_room_check and any(
                w in blob for w in ("door", "gate", "hatch", "portal",
                                    "shutter")):
            val = state.get("open")
            if isinstance(val, bool):
                out[name] = "open" if val else "shut"
            else:
                sval = str(state.get("door") or state.get("status")
                           or state.get("position") or "").lower()
                if sval in ("open", "ajar"):
                    out[name] = "open"
                elif sval in ("closed", "shut", "sealed", "locked"):
                    out[name] = "shut"
    edge_states = set()
    for edge in (rooms.get(room_id) or {}).get("adjacent") or []:
        if not isinstance(edge, dict):
            continue
        barrier = str(edge.get("barrier") or "")
        if barrier not in ("closed_door", "open_door"):
            continue
        to = edge.get("to")
        # S3-A5: only filter by visible_rooms when explicitly provided.
        # Backwards-compatible callers (visible_rooms=None) get the
        # original behavior: all adjacency barriers in the player's room.
        if _filter_adjacent and to and to not in visible_rooms:
            continue
        to_name = str(((rooms.get(to) or {}).get("name")) or to or "").strip()
        state = "shut" if barrier == "closed_door" else "open"
        if to_name:
            out.setdefault(f"door to {to_name}", state)
        edge_states.add(state)
    all_states = set(out.values()) | edge_states
    if len(all_states) == 1 and (out or edge_states):
        out.setdefault("doors", next(iter(all_states)))
    return out


def _generate_narration(payload, view, prev, p_lines, correction_notes=None,
                        fidelity_facts=None):
    call_payload = dict(payload)
    if correction_notes:
        call_payload["correction_notes"] = correction_notes
    out = _agent_json(
        "narrator",
        "narrator",
        get_prompt("narrator"),
        call_payload,
        max_tokens=None,   # the configured ceiling; see complete_validated_json
    )
    # Warning-only re-normalization; strict schema+semantic validation
    # (with repair/fallback/raise) already ran inside _agent_json.
    out, warnings = validate_llm_output("narrator", out)
    out.setdefault("prose", out.get("text", ""))
    out.setdefault("new_specifics", [])
    # The player's own declared lines must NOT count toward DIALOGUE
    # FIDELITY -- PLAYER ECHO RULE requires the opposite of them (excluded,
    # not present), so scoring them here would make the two rules fight and
    # push the retry loop toward violating the echo rule to "fix" a false
    # positive.
    facts = fidelity_facts or {}
    fidelity_warnings = _check_narrator_fidelity(
        out, view, recent_prose=prev, exclude_quotes=p_lines,
        cast_pronouns=call_payload.get("cast_pronouns"),
        player_name=call_payload.get("player_name"),
        narration_person=call_payload.get("narration_person"),
        event_order=facts.get("event_order"),
        position_facts=facts.get("position_facts"),
        room_names=facts.get("room_names"),
        portal_states=facts.get("portal_states"))
    return out, warnings, fidelity_warnings

def narrator(ctx, nonce):
    chat = ctx.chat
    pers = persona_of(chat)
    est = ctx.get("director_establish") or {}
    if est:
        view = (ctx.get("perception_establish", {}).get("views") or {}).get("player") \
            or "You register your immediate surroundings."
    else:
        view = (ctx.get("perception_outcome", {}).get("views") or {}).get("player") \
            or "Nothing in particular reaches you this beat."
    # Frame-filtered: t.idx is GLOBAL play order shared by every frame,
    # so without this an OTHER concurrently-played frame's prior prose
    # would leak into this frame's own rhythm/repetition context.
    rows = q("SELECT v.content FROM turns t "
             "JOIN steps s ON s.turn_id=t.id AND s.key='narrator' "
             "JOIN variants v ON v.step_id=s.id AND v.active=1 "
             "WHERE t.chat_id=? AND t.idx<? AND t.frame_id IS ? ORDER BY t.idx DESC LIMIT 4",
             (chat["id"], ctx.turn["idx"], ctx.turn["frame_id"]))
    prev = [json.loads(r["content"]).get("prose", "") for r in reversed(rows)]
    di = ctx.get("director_interpret") or {}
    p_lines = player_speech_lines(di)

    player_declared = {
        "sequence": di.get("sequence") or [],
        "speech": di.get("speech"),
        "action": (di.get("action") or {}).get("attempt"),
        "private_thought": di.get("private_thought"),
        "raw_input": ctx.input or "",
    }

    # (x or {}) rather than .get(key, {}): a hand-edited sheet with an
    # explicit "identity": null defeats the .get default and would crash
    # the narrator stage every turn.
    player_name = (pers.get("identity") or {}).get("name") or "Player" if isinstance(pers, dict) else "Player"
    player_pronouns = (pers.get("identity") or {}).get("pronouns", {}) if isinstance(pers, dict) else {}
    # Durable persistence of a newly detected person is deferred to commit
    # (commit.py's commit_narration_person) via this pending sink -- the
    # narrator stage itself must not write world state before the commit
    # boundary validates the turn.
    pending_person_writes = {}
    narration_person = _resolve_narration_person(
        chat["id"], ctx.input or "", player_name, player_pronouns,
        pending=pending_person_writes)

    cast_pronouns = _cast_pronouns(ctx.cast)

    # Consciousness gate: when the player is non-awake, their `player_view` is
    # already the deterministic residue (perception_outcome). Do NOT also hand
    # the narrator the room's spatial frame/facts -- passing scene layout with
    # an instruction to render only a residue is exactly the "objective state +
    # instruction to ignore it" pattern the engine forbids. Gate the payload,
    # not the prose: the narrator renders an honest fade-out from the residue.
    _res_diff = (ctx.get("director_resolve") or {}).get("state_diff") or {}
    player_awareness = awareness_of(
        apply_awareness_diff(awareness_map(chat["id"]), _res_diff), player_name)
    _scene_for_frame = ctx.get("outcome_scene") or get_scene(chat["id"], chat)
    _spatial_fields = ({} if player_awareness in NON_AWAKE_GATED else {
        "spatial_frame": spatial_digest(_scene_for_frame, player_name),
        **_spatial_facts_field(_scene_for_frame, player_name),
    })

    # F1-F4 world-fidelity payload: the pipeline's own ordered event record,
    # co-present position deltas, and visible portal states -- plus the same
    # structures as check inputs for the deterministic backstops in
    # _check_narrator_fidelity. Normal turns only (an opening turn has no
    # prior beat to delta against and no loop order), and gated with the
    # spatial fields on consciousness: a non-awake mind gets no scene.
    _world_fields, _fidelity_facts = {}, {}
    if not est and player_awareness not in NON_AWAKE_GATED:
        known_map = wget(chat["id"], "known", {}) or {}
        recognized = set(known_map.get(player_name) or [])
        cast_info = {}
        for _row in ctx.cast:
            try:
                _sh = json.loads(_row["sheet"])
            except Exception:
                continue
            cast_info[character_name(_sh)] = {
                "appearance": character_appearance(_sh),
                "aliases": character_scene_keys(_sh)[1:],
            }
        p_room = ctx.get("_player_room") or room_of(_scene_for_frame, player_name)
        event_order = _ordered_beat_events(
            ctx, player_name, view, recognized, cast_info)
        pos_payload, pos_facts, room_names = _position_delta_payload(
            ctx, chat, player_name, p_room, recognized, cast_info)
        # S3-A5: pass visible rooms so portal states for unseen rooms are
        # withheld from the narrator payload. visible_adjacent_rooms returns
        # room RECORDS ({room_id, room_name, barrier, description}), not ids
        # -- set() over them raised TypeError: unhashable type: 'dict' and
        # crashed the narrator on every awake, non-establishment turn whose
        # room had a sight-permitting adjacency. Same unpacking as
        # perception.py's _observer_scene_payload.
        _visible = {
            str(r["room_id"]) for r in visible_adjacent_rooms(_scene_for_frame, p_room)
            if isinstance(r, dict) and r.get("room_id")
        } | ({p_room} if p_room else set())
        portal_states = _visible_portal_states(_scene_for_frame, p_room, _visible)
        if event_order:
            _world_fields["event_order"] = event_order
        if pos_payload:
            _world_fields["co_present_positions"] = pos_payload
        if portal_states:
            _world_fields["portal_states"] = portal_states
        _fidelity_facts = {
            "event_order": event_order,
            "position_facts": pos_facts,
            "room_names": room_names,
            "portal_states": portal_states,
        }

    payload = {
        "player_view": view,
        "player_declared": player_declared,
        "cast_pronouns": cast_pronouns,
        "do_not_quote_verbatim": p_lines,
        "scene_opening": bool(est),
        "player_awareness": player_awareness,
        "private_voice_setting": (
            (pers.get("narration") or {}).get("voice_setting", "")
            if isinstance(pers, dict) else ""
        ),
        "narration_person": narration_person,
        "player_name": player_name,
        "player_pronouns": player_pronouns,
        # perception_outcome stashes this turn's post-move, orientation-refreshed
        # scene; fall back to the committed KV on the opening turn (establish),
        # where no movement has happened and orientation is fresh anyway. Using
        # the committed scene here would describe the space with LAST beat's
        # facing on movement beats (commit runs after this stage).
        **_spatial_fields,
        **_world_fields,
        "recent_prose_for_rhythm": prev,
        "already_established_phrases": _already_established_phrases(view, prev),
        "overused_phrases": _overused_phrases(prev),
        "exemplars": json.loads(get_setting("exemplars") or "[]"),
        "variant_seed": nonce,
    }
    out, warnings, fidelity_warnings = _generate_narration(
        payload, view, prev, p_lines, fidelity_facts=_fidelity_facts)

    enforceable = [w for w in fidelity_warnings if w.startswith(_ENFORCEABLE_PREFIXES)]
    if enforceable:
        correction = ("Your previous draft for THIS turn had these problems -- "
                      "rewrite fixing them, without introducing new ones: "
                      + " | ".join(enforceable))
        out, warnings, fidelity_warnings = _generate_narration(
            payload, view, prev, p_lines, correction_notes=correction,
            fidelity_facts=_fidelity_facts)

    # Craft screen: while the accepted draft carries banned AI tells, spend a
    # rewrite naming them (bounded to 2). Keep a rewrite ONLY if it preserves
    # dialogue fidelity AND strictly reduces the tell count -- prose quality
    # never costs a dropped line, and we never accept a lateral swap that just
    # trades one tell for another.
    best_tells = _craft_tells(out.get("prose", ""))
    _retry_cap = 0 if os.environ.get("NARRATOR_CRAFT_RETRY") == "0" else 2
    craft_attempts = 0
    while best_tells and craft_attempts < _retry_cap:
        craft_attempts += 1
        craft_note = ("Your previous draft for THIS turn used banned AI tells / weak "
                      "phrasing -- rewrite the PROSE to remove every one, keeping all "
                      "dialogue verbatim and every fact intact: " + "; ".join(best_tells))
        r_out, r_warnings, r_fid = _generate_narration(
            payload, view, prev, p_lines, correction_notes=craft_note,
            fidelity_facts=_fidelity_facts)
        r_enforceable = [w for w in r_fid if w.startswith(_ENFORCEABLE_PREFIXES)]
        r_tells = _craft_tells(r_out.get("prose", ""))
        if not r_enforceable and len(r_tells) < len(best_tells):
            out, warnings, fidelity_warnings = r_out, r_warnings, r_fid
            best_tells = r_tells
        else:
            break

    ctx.warnings.extend(warnings)
    if fidelity_warnings:
        ctx.warnings.extend(fidelity_warnings)
        # ctx.warnings is accumulated pipeline-wide but never surfaced
        # anywhere (not streamed, not persisted, not logged) -- see
        # AGENTS.md's safe-change workflow: attach directly to this
        # step's own saved output so a content-fidelity failure is at
        # least visible in the step/variant inspector instead of
        # vanishing silently.
        out["fidelity_warnings"] = fidelity_warnings

    if pending_person_writes:
        out["narration_person_writes"] = pending_person_writes
    # Within-view dedupe (W12): a duplicated beat -- the same sentence
    # rendered twice in one turn's prose -- is dropped deterministically.
    # Quoted dialogue and short sentences are exempt (see the helper).
    out["prose"] = _cap_repeated_quotes(
        _dedupe_view_sentences(_strip_player_echo(
            out.get("prose", ""), p_lines,
            protect_quotes=_protected_view_quotes(view, p_lines),
        )),
        view, exclude_bodies=p_lines)
    return out

def narrator_extra(ctx, nonce):
    """Renders one prose view per additional human player declaring in this
    beat (ctx.extra_players), mirroring narrator() above but keyed by
    persona_id rather than hardcoded to the single primary player. A
    deliberately separate function rather than a refactor of narrator()
    itself -- narrator() is exercised by every existing single-player chat,
    and this only ever runs when ctx.extra_players is non-empty, so it
    can't regress anything by construction.
    """
    if not ctx.extra_players:
        return {}

    chat = ctx.chat
    est = ctx.get("director_establish") or {}
    outcome_views = (ctx.get("perception_outcome", {}) or {}).get("views") or {}
    establish_views = (ctx.get("perception_establish", {}) or {}).get("views") or {}
    di = ctx.get("director_interpret") or {}
    other_players = di.get("other_players") or {}

    # Frame-filtered -- see the matching comment in narrator() above.
    rows = q("SELECT v.content FROM turns t "
             "JOIN steps s ON s.turn_id=t.id AND s.key='narrator_extra' "
             "JOIN variants v ON v.step_id=s.id AND v.active=1 "
             "WHERE t.chat_id=? AND t.idx<? AND t.frame_id IS ? ORDER BY t.idx DESC LIMIT 4",
             (chat["id"], ctx.turn["idx"], ctx.turn["frame_id"]))
    per_persona_prev = [json.loads(r["content"]) for r in reversed(rows)]

    def render_one(extra):
        pid = extra["persona_id"]
        pid_key = str(pid)
        entry = other_players.get(pid_key) or {}
        p_lines = player_speech_lines(entry)

        view = (establish_views.get(f"extra:{pid_key}") if est else
                outcome_views.get(f"extra:{pid_key}")) \
            or "Nothing in particular reaches you this beat."

        prev = [d.get(pid_key, {}).get("prose", "") for d in per_persona_prev]

        player_declared = {
            "sequence": entry.get("sequence") or [],
            "speech": entry.get("speech"),
            "action": (entry.get("action") or {}).get("attempt"),
            "private_thought": entry.get("private_thought"),
            "raw_input": extra.get("input") or "",
        }

        # Deferred to commit exactly like narrator() above -- each pending
        # write rides this persona's own returned entry.
        pending_person_writes = {}
        narration_person = _resolve_narration_person(
            chat["id"], extra.get("input") or "", extra.get("name"),
            extra.get("pronouns") or {}, key=f"narration_person:extra:{pid}",
            pending=pending_person_writes)

        payload = {
            "player_view": view,
            "player_declared": player_declared,
            "cast_pronouns": _cast_pronouns(ctx.cast),
            "do_not_quote_verbatim": p_lines,
            "scene_opening": bool(est),
            "private_voice_setting": "",
            "narration_person": narration_person,
            "player_name": extra.get("name") or "Player",
            "player_pronouns": extra.get("pronouns") or {},
            "spatial_frame": spatial_digest(
                ctx.get("outcome_scene") or get_scene(chat["id"], chat),
                extra.get("name") or ""),
            "recent_prose_for_rhythm": prev,
            "already_established_phrases": _already_established_phrases(view, prev),
            "overused_phrases": _overused_phrases(prev),
            "exemplars": json.loads(get_setting("exemplars") or "[]"),
            "variant_seed": nonce,
        }
        out, warnings, fidelity_warnings = _generate_narration(payload, view, prev, p_lines)

        enforceable = [w for w in fidelity_warnings if w.startswith(_ENFORCEABLE_PREFIXES)]
        if enforceable:
            correction = ("Your previous draft for THIS turn had these problems -- "
                          "rewrite fixing them, without introducing new ones: "
                          + " | ".join(enforceable))
            out, warnings, fidelity_warnings = _generate_narration(
                payload, view, prev, p_lines, correction_notes=correction)

        if fidelity_warnings:
            out["fidelity_warnings"] = fidelity_warnings

        if pending_person_writes:
            out["narration_person_writes"] = pending_person_writes
        # Within-view dedupe (W12) -- see the matching comment in narrator().
        out["prose"] = _cap_repeated_quotes(
            _dedupe_view_sentences(_strip_player_echo(
                out.get("prose", ""), p_lines,
                protect_quotes=_protected_view_quotes(view, p_lines),
            )),
            view, exclude_bodies=p_lines)
        return pid_key, out, warnings, fidelity_warnings

    # Each extra player's narration only reads data already computed before
    # this step runs (director_interpret/perception_outcome) and never reads
    # another extra player's own output -- genuinely independent work, same
    # as the mapping+perception_act pairing elsewhere in the pipeline. Each
    # render_one only READS its own distinct per-persona world key
    # (narration_person:extra:<pid>); the corresponding write is recorded on
    # that persona's returned entry and applied at commit, so concurrent
    # execution is safe;
    # ctx.warnings mutation is deferred to the main thread below rather than
    # done inside each worker, avoiding any concurrent-list-mutation risk.
    #
    # context.run(...) below is load-bearing, not decoration:
    # ThreadPoolExecutor workers do NOT inherit the submitting thread's
    # contextvars the way agents/runtime.py's own bespoke thread-spawning
    # helpers (_stream_one/_stream_parallel) do -- those explicitly
    # contextvars.copy_context() before starting each thread. Without this,
    # providers.cancel_event/token_sink (set by the step-level worker
    # thread that's currently running this whole narrator_extra call)
    # would read back as their thread-default None inside render_one,
    # silently making an in-flight abort unable to interrupt these calls
    # and dropping their streamed tokens from the event bus.
    # A fresh copy per job, not one copy shared across jobs -- a single
    # Context object cannot be entered by more than one thread at once
    # (contextvars.Context.run raises RuntimeError if already running
    # elsewhere), and these jobs run concurrently on the pool.
    jobs = [
        (lambda extra=extra, cv=contextvars.copy_context(): cv.run(render_one, extra))
        for extra in ctx.extra_players
    ]
    results = {}
    with ThreadPoolExecutor(max_workers=max(1, len(ctx.extra_players))) as pool:
        for pid_key, out, warnings, fidelity_warnings in pool.map(lambda f: f(), jobs):
            ctx.warnings.extend(warnings)
            if fidelity_warnings:
                ctx.warnings.extend(fidelity_warnings)
            results[pid_key] = out

    return results
