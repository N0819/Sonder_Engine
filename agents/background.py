"""Lightweight, stateless reaction for named background presences.

A background presence (no character sheet, no chat_chars row, no
character_step, no persistent memory) is normally voiced only through the
director's own resolved_event/dialogue_log authorship -- a prompt clause
in prompts.py's director_resolve entry explicitly licenses this. Live play
showed that license goes unused often enough, under enough narrative
pressure, that a deterministic backstop is warranted: exactly the same
"prompt compliance alone is unreliable" lesson already learned for
spatial zone-tagging and speech concealment elsewhere in this codebase.

This stage is deliberately NOT a cheap character_step: no memory, no
mind-models, no relationships, no persistent psychology. It answers one
question for one beat only -- does this specific present bystander
plausibly react right now -- and is gated by a deterministic, LLM-free
check (commit.py's pick_background_reactor) so the common case (no
salient, un-voiced background presence this beat) costs nothing.

For cheap individuation the payload carries a `sketch` (role_hint,
station_room) that commit.track_background_presences harvested
deterministically from the director's own entity description/position
when this presence was introduced -- replayed self-description, not
remembered psychology. The backstop's authored line is folded back into
the committed event record (see commit.prepare_memory_commit /
track_background_presences) so a repeatedly-voiced presence accrues
toward promotion instead of being invisible to bookkeeping.

When a registered character (or the player) speaks directly to a
presence, the gate (commit.pick_background_reactor) can pick them to
answer -- this beat if the single slot is free, otherwise via a one-beat
`pending_reply` debt (commit.track_background_presences) so the answer
lands next turn instead of never. That owed reply is bounded,
single-slot, and deterministically expired -- conversational state, not
memory.
"""

from __future__ import annotations

import json
import logging
import re

from character_schema import (
    character_appearance,
    character_name,
    persona_appearance,
    persona_name,
)
from db import wget
from schemas import validate_llm_output
from prompts import get_prompt
from spatial import hear_level, spatial_rel_between

from commit import (
    name_in_roster,
    pick_background_reactors,
    _background_name_mentioned,
    _character_address_of,
    _known_name_roster,
    _registered_name_roster,
    _quote_body,
    _room_of,
    _valid_pending_reply,
)

from background_claims import (
    MAX_REF_WORDS,
    claimant_credence,
    is_title_only,
    novel_proper_nouns,
)

from scene import persona_of

from .common import _agent_json, _unknown_actor_label

_log = logging.getLogger(__name__)


def _filtered_player_declaration(ctx):
    """The player's beat as a background BYSTANDER may legitimately receive it:
    overt sequence elements only -- never a concealed line, never the private
    thought. background_react used to pass ctx.input raw, leaking whispered or
    silently-sent content (and any private thought the player typed) straight
    into an unregistered presence's payload; worse, a declaration that named
    the presence WHILE concealing made the deterministic gate more likely to
    pick them to react to words they never heard."""
    interp = ctx.get("director_interpret") or {}
    seq = [e for e in (interp.get("sequence") or []) if isinstance(e, dict)]
    if seq:
        parts = []
        for e in seq:
            if e.get("visibility") == "concealed":
                continue
            if e.get("type") == "speech" and e.get("text"):
                parts.append('"%s"' % e["text"])
            elif e.get("type") == "action" and e.get("attempt"):
                parts.append(str(e["attempt"]))
        return " ".join(parts).strip()
    # No structured sequence to filter against; the raw input may contain the
    # concealed words verbatim. Withhold it entirely whenever a private thought
    # exists (the one signal available here that something was withheld);
    # otherwise the declaration is public and safe to pass.
    if interp.get("private_thought"):
        return ""
    return ctx.input or ""


def _beat_for_presence(dr, sc, station_room, name, beat_room=None):
    """What the presence objectively perceives of the beat. Prefer the audible
    dialogue at its station room over the raw resolved_event: resolved_event is
    authored from the omniscient objective frame and can narrate content a
    bystander in one room never sensed. Concealed lines (globally, or concealed
    FROM this presence) are dropped, and any concealed quote body that bled into
    the objective prose is redacted as a backstop.

    ``beat_room`` is the room the beat resolved in (the player's room). The
    prose fallback at the bottom is only a bystander's view when the bystander
    is STANDING THERE: without the gate, a presence whose station was known but
    elsewhere received the omniscient frame precisely when the dialogue filter
    above had just delivered them nothing -- deterministically computed as out
    of earshot, then handed strictly more than an in-earshot presence."""
    resolved = str(dr.get("resolved_event") or "")
    audible = []
    for d in (dr.get("dialogue_log") or []):
        quote = str(d.get("exact_quote") or "").strip()
        if not quote:
            continue
        concealed = (
            str(d.get("visibility") or "").casefold() == "concealed"
            or any(_background_name_mentioned(name, str(c))
                   for c in (d.get("conceal_from") or []))
        )
        if concealed:
            body = _quote_body(quote)
            if body:
                resolved = resolved.replace(body, "")
            continue
        speaker = str(d.get("speaker") or "").strip()
        # X1: the hearing check used to run only `if station_room and sc`, so a
        # presence tracked from a dialogue_log speaker alone -- which has no
        # station room -- fell straight through it and received every audible
        # quote of the beat verbatim, then spoke a reply that became public
        # canon. Co-presence is not the default; not knowing where a presence
        # stands is a reason to deliver nothing, and the scene-manager path
        # already fails closed on exactly this uncertainty.
        if not sc or not station_room:
            continue
        sp_room = _room_of(sc, speaker)
        if not sp_room:
            continue
        # Body-to-body builder, so an enclosure around the speaker muffles the
        # line for a background ear exactly as it does for the cast (L2).
        level = hear_level(
            spatial_rel_between(sc, name, speaker,
                                observer_room=station_room,
                                target_room=sp_room),
            d.get("volume") or "normal",
        )
        if level == "none":
            continue
        if level != "full":
            # X2: a line dropped only at "none" meant `fragment` handed over the
            # whole exact_quote -- the presence "half-heard" it and could then
            # quote it back verbatim. commit._character_address_of already
            # requires "full" to count a line as addressed; these two paths
            # reading the same level differently is the bug.
            audible.append(
                "an indistinct exchange%s" % (f" from {speaker}" if speaker else ""))
            continue
        audible.append("%s: %s" % (speaker, quote) if speaker else quote)
    if audible:
        return " ".join(audible).strip()
    # No audible line: fall back to the beat's prose ONLY for a presence whose
    # station is known. Without a station there is no vantage from which any of
    # it was perceived, and resolved_event is the omniscient frame -- returning
    # it here would hand an unplaced presence MORE than the dialogue gate above
    # just withheld.
    if not station_room:
        return ""
    # And only for a presence standing in the room the beat resolved in. A
    # known station in ANOTHER room is a vantage on that other room, not on
    # this beat; chat 65's Vendor (fountain_plaza) received eastern_market
    # prose through exactly this fall-through. An unknown beat_room fails
    # closed for the same reason an unknown station does.
    if str(station_room) != str(beat_room or ""):
        return ""
    return re.sub(r"\s{2,}", " ", resolved).strip()


def _result(selected, reactions, mode="background_react", agent_calls=None):
    """Uniform stage output. `selected` is every presence the gate picked this
    beat (so commit can discharge their owed replies even if they stayed
    silent); `reactions` is the subset that actually spoke/acted. The legacy
    single-entry keys mirror reactions[0] for callers that predate the list."""
    first = reactions[0] if reactions else {}
    return {
        "fired": bool(reactions),
        "name": first.get("name") or (selected[0] if selected else None),
        "dialogue_log_entry": first.get("dialogue_log_entry"),
        "action": first.get("action", ""),
        "reactions": reactions,
        "selected": selected,
        # Provenance for the pipeline UI: which path ran and which sub-agents
        # it actually spent. The scene manager and the per-presence backstop
        # share a step key, so without this the technical log cannot tell a
        # one-call room from a one-presence reaction.
        "mode": mode,
        "agent_calls": agent_calls or [],
    }


def background_react(ctx, nonce):
    dr = ctx.get("director_resolve") or {}
    try:
        from scene import background_config
        cfg = background_config(ctx.chat.id)
    except Exception:
        cfg = {}
    level = str(cfg.get("scene_life") or "off").strip().casefold()
    if level in ("ambient", "full"):
        # Scene-manager path (docs/design/BACKGROUND_LIFE_DESIGN.md §3.10-§3.12). It
        # returns the SAME _result() shape as the per-presence path, so every
        # downstream merge (perception.py, narration.py, commit.py's
        # _background_fired_reactions) works unchanged.
        out = scene_life(ctx, nonce, level, cfg)
        if out["fired"] or level == "ambient":
            # At `ambient` a directed line is deliberately withheld from the
            # manager, so fall through to the per-presence path when the
            # manager stayed silent -- that is exactly the case background_react
            # already handles correctly.
            if out["fired"]:
                return out
        else:
            return out
    cap = int(cfg.get("max_reactors", 1) or 1)
    cap = max(1, min(3, cap))  # hard ceiling; beyond this a crowd is a chorus
    names = pick_background_reactors(ctx, dr, cap=cap)
    if not names:
        return _result([], [])

    roster = {n.casefold() for n in _registered_name_roster(ctx.chat, ctx.cast)}
    roster |= {(e.get("name") or "").casefold() for e in (ctx.extra_players or [])}
    sc = wget(ctx.chat.id, "scene", {}) or {}
    presences = wget(ctx.chat.id, "background_presences", {}) or {}

    # One independent reactive beat per gated presence. At cap == 1 this is a
    # single call (unchanged behavior). For cap > 1 each extra reacts to the
    # same beat blind to the others -- the prompt forbids them referencing one
    # another, so they cannot form a reply-chain; the accepted tradeoff vs. a
    # single batched call is N calls for possibly-similar reactions, cheaper to
    # reason about than micro-perceiving between them (which would rebuild
    # interaction_loop for minds that lack the state that loop exists to guard).
    reactions = []
    for name in names:
        # Per presence, not once for the batch: each one gets the cast under
        # its OWN recognition (see _present_others).
        present_others = _present_others(ctx, _presence_recognizes(ctx, name))
        entry = _react_one(ctx, dr, name, present_others, roster, sc,
                           presences.get(name) or {}, nonce)
        if entry:
            reactions.append(entry)
    return _result(names, reactions, mode="background_react",
                   agent_calls=["background_react"] * len(reactions))


# ---------------------------------------------------------------------------
# Scene manager (docs/design/BACKGROUND_LIFE_DESIGN.md §3.10-§3.12)
# ---------------------------------------------------------------------------

def _place_block(ctx, room_id):
    """Objective self-locating knowledge for the managed location (§3.7). Every
    field is something anyone standing in the room trivially has."""
    sc = wget(ctx.chat.id, "scene", {}) or {}
    room = ((sc.get("rooms") or {}).get(room_id) or {}) if room_id else {}
    block = {
        "room_id": room_id or "",
        "room_name": room.get("name") or room_id or "",
        "room_desc": (room.get("desc") or "")[:400],
        "location": sc.get("location") or "",
        "time": sc.get("time") or "",
    }
    try:
        from agents.perception import _ambient_location_for
        block["ambient_location"] = _ambient_location_for(sc, room_id) if room_id else ""
    except Exception:
        block["ambient_location"] = ""
    # GENERAL WORLD KNOWLEDGE. Neither background path carried any lore at all,
    # so an innkeeper in Lugunica could not be expected to know what Lugunica
    # trades in -- and that gap got worse the moment dialogue moved here from
    # the Director, which at least had the omniscient working state to draw on.
    #
    # This is the firewall being applied, not bypassed. The channel rule bars a
    # presence from facts that reached it through no channel; it has never
    # barred what everybody in the setting knows, and
    # `_check_presence_knowledge_channel` gates single-word matches on the
    # definite article precisely so "trade runs on copper and silver" survives
    # while "the strange coins" does not. Lore is the former.
    #
    # ROOM-SCOPED, via the same helper perception uses, which carries the
    # blocked-slug scoping for a sealed or nested observer. Handing over the
    # whole lorebook would be a real leak: books hold secrets, and an extra is
    # the last mind that should be told one.
    try:
        from agents.common import _room_notes_from_lore
        block["world_knowledge"] = (
            _room_notes_from_lore(room_id, ctx, sc) if room_id else "")[:600]
    except Exception:
        block["world_knowledge"] = ""
    try:
        from scene import fiction_model, style_guide
        block["genre"] = (fiction_model(ctx.chat.id).get("genre") or {}).get("primary") or ""
        sg = style_guide(ctx.chat.id) or {}
        block["style"] = {k: sg[k] for k in ("genre", "tone", "avoid") if sg.get(k)}
    except Exception:
        pass
    return block


def _name_to_entity_id(sc):
    """Display name -> scene entity id. Scene positions are keyed by the opaque
    entity id ("barkeep") while background presences are tracked by the display
    name ("The Barkeep"), so a direct _room_of(name) lookup misses almost every
    presence. commit.track_background_presences already folds the other
    direction for the same reason."""
    out = {}
    for eid, edef in ((sc.get("entities") or {}).items()):
        if not isinstance(edef, dict):
            continue
        nm = str(edef.get("name") or "").strip()
        if nm:
            out[nm.casefold()] = eid
    return out


def _presence_room(sc, name, rec, name_ids=None):
    """Best room for a tracked presence: its own position, its entity id's
    position, or the sketch's station room."""
    room = _room_of(sc, name)
    if room:
        return room
    ids = name_ids if name_ids is not None else _name_to_entity_id(sc)
    eid = ids.get(str(name).strip().casefold())
    if eid:
        room = (sc.get("positions") or {}).get(eid) or _room_of(sc, eid)
        if room:
            return room
    return (rec.get("sketch") or {}).get("station_room")


def _player_room(ctx, sc):
    try:
        from scene import persona_of, persona_name
        pers = persona_of(ctx.chat)
        pname = pers.get("name") or persona_name(pers) if isinstance(pers, dict) else None
        if pname:
            r = _room_of(sc, pname)
            if r:
                return r
    except Exception:
        pass
    return sc.get("player_room") or None


def managed_presences(ctx, cap):
    """The manager's roster: every tracked presence standing inside the
    player's ambient scope, most recently active first, capped.

    Deliberately NOT pick_background_reactors: that gate is salience-based
    (§2.1 -- every condition mirrors the player), which is exactly what makes
    extras feel reactive rather than alive. The manager is handed the room's
    populace and decides for itself who, if anyone, acts.
    """
    cid = ctx.chat.id
    sc = wget(cid, "scene", {}) or {}
    presences = wget(cid, "background_presences", {}) or {}
    if not presences:
        return [], None
    roster = {n.casefold() for n in _registered_name_roster(ctx.chat, ctx.cast)}
    roster |= {(e.get("name") or "").casefold() for e in (ctx.extra_players or [])}

    p_room = _player_room(ctx, sc)
    scope = None
    if p_room:
        try:
            from spatial import ambient_scope
            scope, _ = ambient_scope(sc, p_room)
            scope = set(scope or [])
        except Exception:
            scope = None

    name_ids = _name_to_entity_id(sc)
    out = []
    for name, rec in presences.items():
        # Title-aware: the Enterprise run tracked "Captain Jean-Luc Picard"
        # while the roster held "Jean-Luc Picard", so a REGISTERED character
        # with a sheet, memory and psychology was handed to the stateless
        # manager as furniture. The model declined to puppet him -- which is
        # exactly the "compliance holds until it doesn't" situation this
        # codebase keeps learning to make structural instead.
        if name_in_roster(name, roster):
            continue
        room = _presence_room(sc, name, rec, name_ids)
        if scope is not None and room and room not in scope:
            continue
        if scope is not None and not room:
            continue  # unplaced presence: cannot prove co-presence, leave out
        out.append((rec.get("last_turn") or -1, name, rec, room))
    out.sort(reverse=True)
    return out[:max(1, int(cap or 1))], p_room


def _audience_map(sc, entry, managed, level):
    """Deterministic per-presence perception annotation (§3.11 layer 2).

    Returns None when the event must not be ADMITTED to the manager's context
    at all (§3.11 layer 1 -- the hard guarantee): a globally concealed line, a
    line concealed from every managed presence, or -- at `ambient` -- any line
    directed at one managed presence, which is divergent content by definition
    and is left to the per-presence path instead.
    """
    if str(entry.get("visibility") or "").casefold() == "concealed":
        return None
    speaker = str(entry.get("speaker") or "").strip()
    sp_room = _room_of(sc, speaker)
    volume = entry.get("volume") or "normal"
    conceal = [str(c) for c in (entry.get("conceal_from") or [])]

    audience = {}
    for _, name, _rec, room in managed:
        if any(_background_name_mentioned(name, c) for c in conceal):
            audience[name] = "none"
            continue
        if sp_room and room:
            lvl = hear_level(
                spatial_rel_between(sc, name, speaker,
                                    observer_room=room, target_room=sp_room),
                volume)
        else:
            # FAIL CLOSED. This used to be `"full"` with a comment claiming it
            # matched `_beat_for_presence` -- which does the opposite: X1
            # holds that not knowing where a presence stands is a reason to
            # deliver NOTHING, and drops the line when speaker or station
            # cannot be placed. Co-presence is not the default; an
            # unplaceable speaker's line must not become every managed
            # presence's canon (register L8).
            lvl = "none"
        audience[name] = lvl
    if not any(v != "none" for v in audience.values()):
        return None
    if level == "ambient" and len(set(audience.values())) > 1:
        # Divergent perception is precisely what `ambient` refuses to hold.
        return None
    return audience


def _manager_events(ctx, dr, sc, managed, level):
    """Admitted events with per-presence audience tags. The hard filter runs
    here, before the model sees anything."""
    events = []
    for d in (dr.get("dialogue_log") or []):
        quote = str(d.get("exact_quote") or "").strip()
        if not quote:
            continue
        aud = _audience_map(sc, d, managed, level)
        if aud is None:
            continue
        events.append({
            "speaker": str(d.get("speaker") or "").strip(),
            "quote": quote,
            "volume": d.get("volume") or "normal",
            "intended_target": d.get("intended_target") or "",
            "tone": d.get("tone") or "",
            "audience": aud,
        })
    return events


def scene_life(ctx, nonce, level, cfg):
    """One batched call voicing a whole location's background populace."""
    dr = ctx.get("director_resolve") or ctx.get("director_establish") or {}
    cap = int(cfg.get("max_managed", 6) or 6)
    managed, p_room = managed_presences(ctx, cap)
    if not managed:
        return _result([], [])

    sc = wget(ctx.chat.id, "scene", {}) or {}
    names = [n for _, n, _r, _rm in managed]
    events = _manager_events(ctx, dr, sc, managed, level)

    place = _place_block(ctx, p_room)
    minted = _mint_blurbs(ctx, managed)

    cast = []
    for _, name, rec, room in managed:
        blurb = minted.get(name) or rec.get("blurb") or {}
        cast.append({
            "name": name,
            "blurb": {k: blurb.get(k, "") for k in ("manner", "trait", "tell", "look")},
            "role_hint": (rec.get("sketch") or {}).get("role_hint", ""),
            "room": room or "",
            "present_since_turn": rec.get("first_turn"),
            "recent": [r.get("text", "") for r in (rec.get("recent") or [])][-3:],
        })

    # The batched call is ONE shared context: whatever enters it reaches the
    # voicing of every managed presence at once, so the omniscient beat prose
    # is admitted only when it is uniformly perceivable -- every managed
    # presence standing in the room the beat resolved in. Anything less
    # (someone elsewhere in ambient scope, or no known player room) withholds
    # the prose entirely and leaves the per-presence audience tags on
    # `events` as the only channel; tagging prose per presence inside a
    # shared context would be an annotation, and §3.11 layer 1 demands
    # non-admission, not annotation. This is the field that nullified
    # _audience_map's work: the tags said "none" while the prose beside them
    # said everything.
    _prose_shared = bool(p_room) and all(
        room == p_room for _, _n, _r, room in managed)
    payload = {
        "place": place,
        "beat": {
            "resolved_event": _redacted_resolved_event(dr) if _prose_shared else "",
            "player_declaration": _filtered_player_declaration(ctx),
            "events": events,
            "present_characters": [
                p for p in _present_others(ctx, _presence_recognizes(ctx, *names))
                if p not in names],
        },
        "cast": cast,
        "variant_seed": nonce,
    }

    out = _agent_json("character_bg", "scene_life", get_prompt("scene_life"),
                      payload, temperature=0.85)
    out, warnings = validate_llm_output("scene_life", out)
    ctx.warnings.extend(warnings)

    # Deterministic post-validation (§3.11). Entries are dropped individually;
    # one malformed entry never fails the stage.
    allowed = {n.casefold(): n for n in names}
    withheld = _withheld_bodies(dr)
    known_names = _known_world_names(ctx, sc, names)
    rec_by_name = {n: r for _, n, r, _rm in managed}
    reactions, seen, claims = [], set(), []
    for e in (out.get("entries") or []):
        if not isinstance(e, dict):
            continue
        canon = allowed.get(str(e.get("name") or "").strip().casefold())
        if not canon or canon in seen:
            continue  # not a managed presence, or already acted this beat
        speech = e.get("speech") if isinstance(e.get("speech"), dict) else None
        action = str(e.get("action") or "").strip()
        quote = str((speech or {}).get("exact_quote") or "").strip()
        if not quote and not action:
            continue
        # The verbatim floor (§3.3.1): a line reproducing withheld content is
        # dropped BEFORE it can be rendered or appended to a profile.
        if quote and _reproduces_withheld(quote, withheld):
            ctx.warnings.append(
                "scene_life: dropped %s -- reproduced withheld content" % canon)
            continue
        seen.add(canon)
        # Lore this line invents is recorded as a CLAIM, never as fact -- the
        # Director ratifies, contradicts, or lets it expire (background_claims).
        refs = _claimed_refs(e, quote, known_names,
                             turn=getattr(getattr(ctx, "turn", None), "idx", None),
                             claimant=canon)
        if refs:
            claims.append({
                "claimant": canon, "text": quote or action, "refs": refs,
                "credence": claimant_credence(
                    (minted.get(canon) or (rec_by_name.get(canon) or {}).get("blurb"))),
            })
        entry = None
        if quote:
            entry = {
                "speaker": canon,
                "exact_quote": quote,
                "volume": (speech or {}).get("volume") or "normal",
                "intended_target": (speech or {}).get("intended_target") or None,
                "tone": (speech or {}).get("tone") or "",
                "visibility": "overt",
                "conceal_from": [],
            }
        reactions.append({"name": canon, "dialogue_log_entry": entry,
                          "action": action})
    # Downstream merge paths key off dialogue_log_entry; an action-only entry
    # still rides through as a reaction so commit/narration can use it.
    calls = ["scene_life"]
    if minted:
        calls.insert(0, "blurb_mint")
    res = _result(names, reactions, mode="scene_life:%s" % level,
                  agent_calls=calls)
    if minted:
        res["blurbs"] = minted  # persisted by commit.track_background_presences
    if claims:
        res["claims"] = claims  # recorded by commit; ratified by the Director
    return res


def _known_world_names(ctx, sc, managed_names):
    """Everything already named in play. A capitalized phrase outside this set
    is something a background presence has just invented."""
    known = set(managed_names)
    known |= {str((e or {}).get("name") or "")
              for e in (sc.get("entities") or {}).values() if isinstance(e, dict)}
    known |= {str((r or {}).get("name") or "")
              for r in (sc.get("rooms") or {}).values() if isinstance(r, dict)}
    known |= set((sc.get("rooms") or {}).keys())
    known |= set((sc.get("positions") or {}).keys())
    if sc.get("location"):
        known.add(str(sc["location"]))
    try:
        known |= set(_known_name_roster(ctx.chat, ctx.cast))
    except Exception:
        pass
    # Recognition-gated on purpose: _known_name_roster above already supplies
    # the canonical names, so what this adds is the appearance LABELS a
    # presence refers to strangers by. Those are descriptions of people
    # already in the room, not invented lore, and must not be scored as
    # claims.
    for p in _present_others(ctx):
        known.add(p)
    try:
        from db import wget as _wget
        for rec in (_wget(ctx.chat.id, "background_claims", {}) or {}).values():
            known |= {str(r) for r in (rec.get("refs") or [])}
    except Exception:
        pass
    return {k for k in known if k}


def _claimed_refs(entry, quote, known_names, turn=None, claimant=None):
    """What this entry introduced: the manager's own declaration, plus a
    deterministic novel-proper-noun scan as the backstop for what it failed to
    declare (the same belt-and-braces shape used everywhere else here)."""
    declared = [str(a).strip() for a in (entry.get("asserts") or [])
                if str(a).strip()]
    # Instrumentation for the never-fired claims lane stays in the LOGGER
    # only: the earlier file-probe wrote _probe_claimed_refs.jsonl into the
    # repository root on every run, tests included -- a module writing
    # untracked content-bearing files into the tree is not instrumentation,
    # it is debris (see docs/UNBUILT.md, claims-lane fire-rate entry).
    _log.info("claimed_refs: raw asserts=%r declared=%r", entry.get("asserts"), declared)
    detected = novel_proper_nouns(quote, known_names)
    _log.info("claimed_refs: detected=%r from quote=%r", detected, quote)
    known_cf = {k.casefold() for k in known_names}
    out = []
    for ref in declared + detected:
        # A ref is a RATIFICATION KEY, not a summary: it has to be short enough
        # to reappear in later prose. La Forge self-declared a whole sentence
        # in the Enterprise run, so when Picard acted on it ("isolate that
        # junction") nothing matched and a plainly-adopted claim stayed hearsay.
        if len(ref.split()) > MAX_REF_WORDS:
            ref = " ".join(ref.split()[:MAX_REF_WORDS])
        cf = ref.casefold()
        if not cf or cf in known_cf or is_title_only(ref):
            continue
        # Drop anything already covered by a ref we kept, in either direction --
        # the scan re-finds fragments of what the model already declared
        # ("Two D'deridex" inside "Two D'deridex-class warbirds at bearing …").
        if any(cf in o.casefold() or o.casefold() in cf for o in out):
            continue
        out.append(ref)
    return out


def _mint_blurbs(ctx, managed):
    """Batched calls giving a blurb to every managed presence that lacks one
    (§3.8), one call PER ROOM. Batching is safe here and follows from §3.2
    rather than excepting it: a blurb contains no perceptual content, so there
    is nothing to cross-contaminate. But the place block a blurb is minted
    AGAINST is that presence's own room, not the player's -- a blurb is
    frozen characterization, and chat 65's Vendor (fountain_plaza) carried a
    blurb minted from the eastern_market block for the rest of her existence.
    Returned to the caller and persisted by commit -- this stage writes
    nothing itself.
    """
    need = [(name, rec, room) for _, name, rec, room in managed
            if not rec.get("blurb")]
    if not need:
        return {}
    existing = []
    for _, name, rec, _room in managed:
        b = rec.get("blurb")
        if b:
            existing.append({"name": name, **{k: b.get(k, "")
                                              for k in ("manner", "trait")}})
    minted = {}
    rooms = []
    for _name, _rec, room in need:
        if room not in rooms:
            rooms.append(room)
    for room in rooms:
        batch = [(n, r) for n, r, rm in need if rm == room]
        payload = {
            "place": _place_block(ctx, room),
            "people": [
                {"name": name,
                 "known": (rec.get("sketch") or {}).get("role_hint", "")}
                for name, rec in batch
            ],
            "already_written": existing,
            "variant_seed": ctx.turn.idx,
        }
        try:
            out = _agent_json("character_bg", "blurb_mint",
                              get_prompt("blurb_mint"), payload,
                              temperature=0.9)
            out, warnings = validate_llm_output("blurb_mint", out)
            ctx.warnings.extend(warnings)
        except Exception as exc:  # a blurb is colour, never load-bearing
            ctx.warnings.append("blurb_mint failed: %s" % exc)
            continue
        wanted = {n.casefold(): n for n, _ in batch}
        for b in (out.get("blurbs") or []):
            if not isinstance(b, dict):
                continue
            canon = wanted.get(str(b.get("name") or "").strip().casefold())
            if not canon:
                continue
            minted[canon] = {k: str(b.get(k) or "").strip()[:160]
                             for k in ("manner", "trait", "tell", "look")}
    return minted


def _redacted_resolved_event(dr):
    """resolved_event with every concealed quote body stripped.

    Admission control (§3.11 layer 1) covered dialogue_log but NOT the
    Director's own prose, which is authored from the omniscient objective frame
    and can narrate a whispered line's content verbatim. The per-presence path
    has always guarded this (_beat_for_presence redacts the same bodies as a
    backstop); the manager path passed the prose raw, so a concealed line the
    Director restated in narration would have reached the manager's context
    despite never appearing in its dialogue_log. Found by live play, not by the
    tests -- they only exercised dialogue_log.
    """
    resolved = str(dr.get("resolved_event") or "")
    for d in (dr.get("dialogue_log") or []):
        if str(d.get("visibility") or "").casefold() != "concealed":
            continue
        body = _quote_body(str(d.get("exact_quote") or ""))
        if body:
            resolved = resolved.replace(body, "")
    return re.sub(r"\s{2,}", " ", resolved).strip()


def _withheld_bodies(dr):
    """Exact quote bodies the engine deliberately withheld this beat."""
    bodies = []
    for d in (dr.get("dialogue_log") or []):
        if str(d.get("visibility") or "").casefold() != "concealed":
            continue
        body = _quote_body(str(d.get("exact_quote") or ""))
        if body and len(body) >= 12:
            bodies.append(body.casefold())
    return bodies


def _reproduces_withheld(quote, withheld):
    q = _quote_body(quote).casefold()
    if not q:
        return False
    for body in withheld:
        if body in q or q in body:
            return True
        # A distinctive run of the withheld line surfacing verbatim.
        words = body.split()
        for i in range(0, max(0, len(words) - 5)):
            if " ".join(words[i:i + 6]) in q:
                return True
    return False


def _presence_recognizes(ctx, *presence_names):
    """Names EVERY one of these background presences may use canonically.

    The `known` world key is the engine's only per-mind recognition ledger,
    keyed by the recognizing mind's own name (commit seeds it on promotion;
    mapping's validated_introductions grows it). An unregistered presence
    normally has no entry, so this normally returns the empty set -- that is
    the intended answer, not a degradation: a bystander with no memory has no
    basis for anybody's name.

    Several presences share one payload on the scene_life path, so the
    intersection is what that payload may carry: a name only one of them
    knows would be handed to all of them, which is precisely the
    cross-contamination §3.2 forbids.
    """
    known = wget(ctx.chat.id, "known", {}) or {}
    sets = [{str(x) for x in (known.get(n) or [])} for n in presence_names]
    return set.intersection(*sets) if sets else set()


def _present_others(ctx, recognized=None):
    """Co-located character names for a background presence's payload, gated
    by what THAT presence recognizes.

    This used to gate on the PLAYER's `known` map, which answers the wrong
    question: a background presence is a separate mind, and every other gate
    in this file already treats it as one -- _beat_for_presence gates on its
    station room and hear_level, _audience_map matches conceal_from against
    its own name. Borrowing the player's acquaintances let a presence who has
    met nobody address the cast by name, and conversely hid a name from a
    presence who does know it. `recognized` is that presence's own set (see
    _presence_recognizes); the default of None means no vantage at all, so
    nothing is recognized.

    The justification for the old basis was that the presence's authored
    dialogue is read by the player. That is a property of the OUTPUT path,
    and it is handled there -- narration re-derives every speaker attribution
    through the player's own recognition gate (agents/narration.py's
    _speaker_display). It is also not weakened by this change: an
    unregistered presence's recognized set is in practice empty, i.e.
    strictly tighter than the player's map.

    An unrecognized character renders as their appearance-derived label,
    matching the recognition gate in
    agents/loops.py:deterministic_micro_perception. The label comes from
    agents/common.py's _unknown_actor_label, which is the canonical
    implementation -- it strips the actor's own name tokens out of the
    appearance summary (those summaries routinely lead with the name) and
    trims on a word boundary.
    """
    recognized = set(recognized or ())
    pers = persona_of(ctx.chat)
    p_name = persona_name(pers)
    # The player is subject to the same gate: a presence that has never been
    # introduced has no more claim on the protagonist's name than on anyone
    # else's.
    present_others = [p_name if p_name in recognized
                      else _unknown_actor_label(p_name, persona_appearance(pers))]
    for row in ctx.cast:
        sh = json.loads(row["sheet"])
        cname = character_name(sh)
        present_others.append(
            cname if cname in recognized
            else _unknown_actor_label(cname, character_appearance(sh)))
    return present_others


def _react_one(ctx, dr, name, present_others, roster, sc, rec, nonce):
    """One presence's single reactive beat, or None if it stays silent."""
    # Cheap individuation: replay the sketch harvested (deterministically, in
    # commit.track_background_presences) from the director's own entity
    # description/position when this presence was introduced.
    sketch = rec.get("sketch") or {}

    # If a registered character (or the player) spoke directly TO this presence
    # -- this beat, or last beat with the gate spent elsewhere -- surface that
    # line so the reaction can answer it. `beats_ago` marks fresh (0) vs owed
    # (1). The line already rendered; the reply is appended after it, no chain.
    addressed_by = None
    fresh = _character_address_of(dr, name, roster, sc, sketch.get("station_room"))
    if fresh:
        addressed_by = {"speaker": fresh.get("speaker"),
                        "exact_quote": fresh.get("exact_quote", ""),
                        "tone": fresh.get("tone", ""), "beats_ago": 0}
    else:
        pr = _valid_pending_reply(rec, ctx.turn.idx)
        if pr:
            addressed_by = {"speaker": pr.get("from"), "exact_quote": pr.get("quote", ""),
                            "tone": pr.get("tone", ""), "beats_ago": 1}

    payload = {
        # The per-presence path carried NO place block whatever -- not the
        # room, not the time, not the setting, not a word of lore. It knew its
        # own role_hint and the beat, and nothing about the world it stands in.
        "place": _place_block(ctx, sketch.get("station_room")
                              or _player_room(ctx, sc)),
        "entity": {
            "name": name,
            "role_hint": sketch.get("role_hint", ""),
            "station_room": sketch.get("station_room", ""),
        },
        "beat": {
            "resolved_event": _beat_for_presence(
                dr, sc, sketch.get("station_room"), name,
                beat_room=_player_room(ctx, sc)),
            "addressed_by": addressed_by,
            "player_declaration": _filtered_player_declaration(ctx),
            "present_others": [p for p in present_others if p != name],
        },
        "variant_seed": nonce,
    }

    out = _agent_json(
        "character_bg", "background_react", get_prompt("background_react"),
        payload, temperature=0.7,
    )
    # Warning-only re-normalization; strict schema validation (with
    # repair/fallback/raise) already ran inside _agent_json.
    out, warnings = validate_llm_output("background_react", out)
    ctx.warnings.extend(warnings)

    if not out.get("reacts") or not out.get("dialogue_log_entry"):
        return None
    entry = dict(out["dialogue_log_entry"])
    entry["speaker"] = name
    entry.setdefault("visibility", "overt")
    entry.setdefault("conceal_from", [])
    return {"name": name, "dialogue_log_entry": entry, "action": out.get("action", "")}
