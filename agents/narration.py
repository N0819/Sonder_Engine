"""Player-facing narration agent."""

from __future__ import annotations

import contextvars
import json
from concurrent.futures import ThreadPoolExecutor

from core.db import get_setting, q, wget, wset
from language_runtime import compositor_text, english_linguistic, linguistic
from llm.prompts import get_prompt, prompt_fragment
from story.scene import (
    NON_AWAKE_GATED,
    apply_awareness_diff,
    awareness_map,
    awareness_of,
    persona_of,
    get_scene,
)
import os
import re

from world.spatial import (
    containment_conceals,
    contact_sensation,
    effective_light,
    entity_arc,
    has_visual,
    hiding_holders_of,
    room_of,
    same_subject,
    spatial_digest,
    spatial_facts,
    spatial_rel,
    substances_for,
    visible_adjacent_rooms,
    visual_level_between,
)
from world.weather import weather_for_room, weather_words


def _ling(name):
    return linguistic("agents.narration", name)

# English compatibility view for tests/tooling; live checks use `_ling(...)`.
_ENFORCEABLE_PREFIXES = english_linguistic(
    "agents.narration", "_ENFORCEABLE_PREFIXES")

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
from llm.schemas import validate_llm_output

from story.character_schema import (
    character_appearance,
    character_name,
    persona_appearance,
)

from .common import (
    _agent_json,
    extra_parts_lines,
    scene_extra_parts,
    _already_established_phrases,
    _cap_repeated_quotes,
    _overused_phrases,
    _check_narrator_fidelity,
    _dedupe_view_sentences,
    _narration_person_counts,
    _protected_view_quotes,
    _quote_body,
    _recognizes,
    _self_second_person,
    self_name_forms,
    self_reference_forms,
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
    # Established, and this turn disagrees. The lead used to be measured
    # against the RUNNER-UP, which is the wrong opponent: it asked whether the
    # winner beat some third person nobody was arguing for, rather than whether
    # it beat the person actually stored. A turn reading {first: 0, second: 1}
    # against a stored `first` is unanimous disagreement, not a stray token,
    # and it scored a lead of 1 and changed nothing. Measured on the story that
    # reported this: 17 of 49 turns could not correct a wrong `first`.
    #
    # Compare against the incumbent. The lead of 2 is KEPT: dropping it for
    # "the stored person scored nothing this turn" was tried and is wrong,
    # because a single misparsed token looks exactly like unanimity. "Mark the
    # map, then rest" scores one third-person hit off the player's own name
    # used as a verb, with nothing on the other side -- indistinguishable by
    # counts from a genuine one-token switch, and flipping a whole campaign on
    # it is the failure this rule exists to prevent.
    #
    # Measured over 2212 live player turns: comparing against the incumbent
    # rather than the runner-up costs no extra mid-story changes at all, and
    # dropping the lead entirely costs two.
    stored_support = counts.get(stored, 0)
    if top - stored_support >= 2:
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

# Deterministic craft screen: AI-tell phrases the PROSE CRAFT prompt bans. A
# draft containing any triggers ONE rewrite naming them (reusing the correction
# loop). Conservative -- only clear tells, to avoid false positives on ordinary
# prose. Dialogue is exempt (quotes are fixed); we scan the whole draft but the
# patterns don't match normal speech.


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
    for pat, label in _ling("_CRAFT_TELLS"):
        if re.search(pat, scan, re.I):
            found.append(label)
    return list(dict.fromkeys(found))

def _authored_body_parts(ctx, persona, player_name):
    """{name: part lines} for every present body that AUTHORED extra parts.

    The same fact as `_cast_pronouns`, and the same failure it was built
    for: guessing flipped a character's pronouns across beats, and guessing
    here gave a body a part it does not have. Measured live -- the narration
    handed Elyra the player's six fox tails; her card declares no extra
    parts at all, so there was nothing in the narrator's payload that could
    have said otherwise. Perception and the Director have carried this index
    all along; only the stage that writes the prose was without it.

    Read live from the cards, like every other user of scene_extra_parts,
    and ABSENT when nobody declared any -- so an ordinary cast leaves the
    payload shape, and the provider's prefix cache, unchanged.
    """
    try:
        parts = scene_extra_parts(ctx.cast, persona, player_name)
    except Exception:
        return {}
    return {name: extra_parts_lines(p) for name, p in (parts or {}).items()
            if p}


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


def _standing_substance_clauses(scene, you):
    """Standing substances involving `you`, as cause-blind touch clauses.

    Mirrors `spatial.substance_event_clause`'s epistemic envelope exactly, so
    a standing re-delivery can never exceed what the onset beat delivered:
    the recipient side never names the source (an internal target knows the
    matter reached them, not who caused it), and the source side never names
    the destination (releasing is felt at your own body, where it landed is
    sight's problem). `detail` is model prose delivered once at onset and is
    deliberately not re-delivered -- every admission here subtracts.
    """
    clauses = []
    for record in substances_for(scene, you):
        substance = " ".join(str(record.get("substance") or "").split())[:160]
        if not substance:
            continue
        amount = " ".join(str(record.get("amount") or "").split())[:80]
        material = f"{amount} of {substance}" if amount else substance
        placement = str(record.get("placement") or "").strip().casefold()
        if same_subject(scene, record.get("target"), you):
            if placement == "interior":
                interior = " ".join(
                    str(record.get("target_interior") or "").split())[:160]
                clauses.append(
                    f"your {interior or 'interior'} still holds {material}")
            elif placement == "surface":
                part = " ".join(
                    str(record.get("target_part") or "").split())[:120]
                clauses.append(f"{material} on your {part or 'skin'}")
            else:
                clauses.append(f"{material} within what you contain")
        elif same_subject(scene, record.get("source"), you):
            part = " ".join(str(record.get("source_part") or "").split())[:120]
            clauses.append(f"{material} released from your {part or 'body'}")
    return clauses


#: Payload order for the manifest -- the fixed vocabulary of
#: `composer.CHANNELS` minus `mixed`, which appears only when a merged span
#: actually crossed channels (absent-when-empty, like the key itself).
_MANIFEST_CHANNELS = ("sight", "hearing", "touch", "smell", "interoception")


def _sensory_channels_manifest(scene, player_name, view, observations,
                               recognized, cast_info, p_room):
    """Per-sense delivery manifest for the narrator payload, or {}.

    THE DEFECT: percepts carry a real channel from every builder through
    `composer.observations_from_render`, and the tag was discarded one stage
    before the prose -- the narrator payload was a single blob, so a model
    obeying SCENE CRAFT's compression could not see that an entire sense went
    silent, and the composer's delta dedupe means beat two of a standing
    contact delivers no touch at all. Measured over 600 stored perception
    steps: sight 1089 spans against touch 94 and delivered smell ~0 after the
    opening turn.

    EVERY ENTRY IS A RE-DELIVERY, NEVER A WIDENING -- the firewall is a gap
    and guards subtract:
      * this-beat spans are admitted only when byte-contained in the player's
        own scrubbed view, so this second representation structurally cannot
        exceed the first (the same invariant `observations_from_render`
        keeps, re-checked here because observations are projected from the
        render BEFORE the tripwire scrub);
      * standing contacts: the player is a party (first-hand by definition),
        and the other party passes the same recognition floor the view used
        (`_speaker_display`), falling to "someone" for a spelling the floor
        cannot place;
      * standing substances: cause-blind both directions (see
        `_standing_substance_clauses`);
      * weather is exposure-gated by `weather_for_room` itself, per channel;
      * a player sealed inside an enclosure gets no manifest at all -- the
        room's air, light and weather are not theirs, and perception already
        owns that view.
    """
    if not isinstance(scene, dict) or not p_room:
        return {}
    if hiding_holders_of(scene, player_name):
        return {}

    view_text = str(view or "")
    by_channel = {}
    for obs in observations or []:
        if not isinstance(obs, dict):
            continue
        text = str(((obs.get("observed") or {}).get("text")) or "").strip()
        if not text or text not in view_text:
            continue
        channel = str(obs.get("channel") or "mixed")
        by_channel.setdefault(channel, []).append(text)

    def _partner_label(other):
        other = str(other)
        info = (cast_info or {}).get(other)
        if info is not None:
            return _speaker_display(other, recognized,
                                    info.get("appearance"),
                                    info.get("aliases"))
        if _recognizes(other, recognized or ()):
            return other
        return "someone"

    touch_standing = []
    for contact in (scene.get("contacts") or []):
        if not isinstance(contact, dict):
            continue
        clause = contact_sensation(contact, you=player_name, scene=scene,
                                   label_for=_partner_label)
        if clause:
            touch_standing.append(clause)
    touch_standing.extend(_standing_substance_clauses(scene, player_name))

    try:
        scoped = weather_for_room(scene, p_room) or {}
    except Exception:
        scoped = {}
    sight_standing = list(weather_words(scoped, "sight"))
    hearing_standing = list(weather_words(scoped, "sound"))
    if scoped.get("falls_on_you"):
        touch_standing.append("%s %s falling on you"
                              % (scoped["intensity"], scoped["precipitation"]))
    if scoped.get("wind_reaches"):
        touch_standing.append("%s on your skin" % scoped["wind"])

    light = effective_light(scene, p_room)
    sight_standing.append(f"light: {light}")

    if light == "dark":
        # Content wins over aperture: a filling light source or a percept
        # that legitimately rode sight this beat means SOMETHING is seen.
        sight_status = ("degraded", "almost no light reaches this room") \
            if by_channel.get("sight") else \
            ("silent", "no light reaches this room")
    elif light == "dim":
        sight_status = ("degraded", "dim light -- shapes, not detail")
    else:
        sight_status = ("live", "")

    touch_live = bool(touch_standing or by_channel.get("touch"))
    statuses = {
        "sight": sight_status,
        "hearing": ("live", ""),
        "touch": ("live", "") if touch_live else
                 ("silent", "nothing is in contact with your body this beat"),
        "smell": ("live", "open air; nothing ledgered rides this channel"
                  if not by_channel.get("smell") else ""),
        "interoception": ("live", "your own body, always"),
    }
    standing = {
        "sight": sight_standing,
        "hearing": hearing_standing,
        "touch": touch_standing,
    }
    manifest = {}
    for channel in _MANIFEST_CHANNELS:
        status, why = statuses[channel]
        entry = {"status": status}
        if why:
            entry["why"] = why
        if by_channel.get(channel):
            entry["this_beat"] = by_channel[channel]
        if standing.get(channel):
            entry["standing"] = standing[channel]
        manifest[channel] = entry
    if by_channel.get("mixed"):
        manifest["mixed"] = {"status": "live",
                             "this_beat": by_channel["mixed"]}
    return manifest


def _ordered_beat_events(ctx, p_name, view, recognized, cast_info,
                         scene=None, p_room=None, player_forms=()):
    """F1/F4: the pipeline's own numbered causal record of this beat, built
    from step order + the loop call sequences (stimulus -> response pairs):
    player declaration first, then reaction rounds, then interaction rounds in
    call order, then parallel character declarations, then background
    reactions. Info-barrier: an NPC line enters ONLY if its quote actually
    reached the player's view, and an NPC ACT only if it is overt and the
    player can perceive its actor; speakers render under the same display
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

    seen_cache = {}

    def _player_perceives(name):
        """Can the player place this actor's overt physical act this beat.

        The same gate `co_present_positions` already uses. An act is listed by
        its Director-authored `observable` surface -- the intent-free
        bystander view -- so listing one hands the narrator no more than the
        position payload it already holds for that character. Fails CLOSED
        (no scene, no player room, actor unseen): a thin beat is a worse page,
        a leaked act is a broken firewall.
        """
        if not name or not scene or not p_room:
            return False
        if name not in seen_cache:
            seen_cache[name] = _player_sees_character(
                scene, p_name, p_room, name, room_of(scene, name))
        return seen_cache[name]

    def _seq_events(name, seq):
        """Every outward element of one character's declared sequence, in the
        order they declared it.

        Speech was always collected here; an ACT was not, which left the
        record the narrator is told is "what actually happened this beat"
        speech-only for everyone except the player. A beat's one physical
        event -- a character moving the player's own body -- therefore reached
        the narrator as a single clause buried mid-paragraph in the view,
        competing with the room's furniture and carrying an `ambiguous`
        fidelity, and nothing anywhere required it to survive onto the page.
        Measured over three rerolls of the same turn, it did not survive any
        of them. Acts are rendered, not quoted, so they are listed for ORDER
        and COVERAGE and never for verbatim reproduction.
        """
        perceives = None
        for e in seq or []:
            if not isinstance(e, dict):
                continue
            if e.get("type") == "speech" and e.get("text"):
                raw.append((name, "speech", e["text"]))
            elif e.get("type") == "action":
                if str(e.get("visibility") or "overt").strip().lower() \
                        != "overt":
                    continue          # concealed: the player was not shown it
                surface = observable_action_text(e)
                if not surface:
                    continue          # purely mental beat, no outward surface
                if perceives is None:
                    perceives = _player_perceives(name)
                if perceives:
                    raw.append((name, "action", surface))

    covered = set()
    for r in (ctx.reaction_loop or {}).get("rounds") or []:
        _seq_events(r.get("reactor"), (r.get("result") or {}).get("sequence"))
        try:
            covered.add(int(r.get("reactor_id")))
        except (TypeError, ValueError):
            pass
    for r in (ctx.interaction_loop or {}).get("rounds") or []:
        _seq_events(r.get("speaker"), (r.get("result") or {}).get("sequence"))
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
        _seq_events(name, d.get("sequence"))
        if not (d.get("sequence")) and d.get("speech"):
            raw.append((name, "speech", d["speech"]))
    br = ctx.get("background_react") or {}
    reactions = br.get("reactions")
    if reactions is None:
        reactions = ([br] if br.get("fired") and br.get("dialogue_log_entry")
                     else [])
    for r in reactions:
        entry = (r or {}).get("dialogue_log_entry") or {}
        speaker = entry.get("speaker") or (r or {}).get("name")
        if entry.get("exact_quote") and entry.get("speaker"):
            raw.append((entry["speaker"], "speech", entry["exact_quote"]))
        # A background presence's ACT was collected nowhere. Its shape differs
        # from a character's declared sequence -- one prose string on the
        # reaction, no `observable`/`visibility` pair -- so the `_seq_events`
        # path above cannot see it, and the beat's one physical event from an
        # unregistered presence (a gun-stick holding its aim on the player's
        # chest) reached the narrator only inside the omniscient resolved_event
        # prose. background.py authors the act as the outward surface already;
        # the perceptibility gate is the same one the cast path uses.
        act = str((r or {}).get("action") or "").strip()
        if act and speaker and _player_perceives(speaker):
            raw.append((speaker, "action", act))

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
            # The same identity floor the composer puts under the player's
            # view, applied to the second copy of this beat's prose that
            # reaches the player. An act's `observable` surface is written in
            # the third person by whoever declared it, and it names the player
            # the way THAT mind refers to them -- by name, or by the epithet
            # the engine minted for a mind that has not recognized them
            # ("eyes settling on the sword at the apprentice's hip", observed
            # live). This is not narrator compensation: event_order is a
            # delivery of engine-written prose to the player, so it carries
            # the delivery floor rather than inheriting one.
            ev["action"] = _self_second_person(text, player_forms) \
                if player_forms else text
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


def _extension_narration_payload(ctx, payload, *, scope, player=""):
    """Hand the assembled narrator payload to installed extensions, or leave it.

    Lazy-imported and total, the same discipline as `character.py`'s routing
    seam and for the same reason: this runs inside the turn's wall clock, so a
    broken extension must cost the beat nothing. With nothing installed -- the
    overwhelmingly common case -- this is one attribute lookup.
    """
    try:
        import extension_runtime

        return extension_runtime.dispatch_narration_payload(
            ctx, payload, scope=scope, player=player)
    except Exception:
        return payload


def _generate_narration(payload, view, prev, p_lines, correction_notes=None,
                        fidelity_facts=None, language="en"):
    call_payload = dict(payload)
    if correction_notes:
        call_payload["correction_notes"] = correction_notes
    out = _agent_json(
        "narrator",
        "narrator",
        get_prompt("narrator", language),
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
            or compositor_text("narrator_immediate", ctx.language)
    else:
        view = (ctx.get("perception_outcome", {}).get("views") or {}).get("player") \
            or compositor_text("narrator_nothing", ctx.language)
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
        # Everything that means "the player" in engine-written prose: their
        # own name forms, and the epithets minted for the minds that have not
        # recognized them. `avoid` is every OTHER body's display in this
        # payload, so a descriptor two bodies share is never claimed as the
        # player's.
        _p_aliases = ((pers.get("identity") or {}).get("aliases") or []) \
            if isinstance(pers, dict) else []
        _other_displays = [
            _speaker_display(_n, recognized, _i.get("appearance"),
                             _i.get("aliases"))
            for _n, _i in cast_info.items() if _n != player_name
        ]
        player_forms = self_name_forms(
            player_name, [player_name, *_p_aliases]) + self_reference_forms(
                player_name,
                (pers.get("appearance") or persona_appearance(pers))
                if isinstance(pers, dict) else "",
                _p_aliases, avoid=_other_displays)
        event_order = _ordered_beat_events(
            ctx, player_name, view, recognized, cast_info,
            scene=_scene_for_frame, p_room=p_room,
            player_forms=player_forms)
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
        # Per-sense delivery manifest (additive, absent-when-empty like
        # authored_body_parts, so pre-change turns keep their payload shape
        # and reroll/replay stay safe). Built from the outcome observations'
        # own IR-derived channels plus the standing substrate; every
        # admission subtracts -- see _sensory_channels_manifest.
        _obs_map = (ctx.get("perception_outcome", {}) or {}).get(
            "observations") or {}
        _senses = _sensory_channels_manifest(
            _scene_for_frame, player_name, view,
            _obs_map.get("player") or [], recognized, cast_info, p_room)
        if _senses:
            _world_fields["sensory_channels"] = _senses
        _fidelity_facts = {
            "event_order": event_order,
            "position_facts": pos_facts,
            "room_names": room_names,
            "portal_states": portal_states,
        }

    _abp = _authored_body_parts(ctx, pers, player_name)
    payload = {
        "player_view": view,
        "player_declared": player_declared,
        "cast_pronouns": cast_pronouns,
        # A body's extra parts are AUTHORED, never inferred. Absent when
        # nobody declared any, so ordinary casts keep their payload shape.
        **({"authored_body_parts": _abp} if _abp else {}),

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
    # Once, here, rather than inside `_generate_narration`: that function is
    # re-entered for the fidelity correction and up to twice more for craft
    # rewrites, and a hook re-run per attempt could hand each attempt different
    # context -- so a correction pass would be narrating against a frame the
    # first pass never saw, and the retry loop would look like the defect.
    payload = _extension_narration_payload(ctx, payload, scope="narrator")
    out, warnings, fidelity_warnings = _generate_narration(
        payload, view, prev, p_lines, fidelity_facts=_fidelity_facts,
        language=ctx.language)

    enforceable = [w for w in fidelity_warnings if w.startswith(_ling("_ENFORCEABLE_PREFIXES"))]
    if enforceable:
        correction = prompt_fragment(
            "narrator_fidelity_correction", ctx.language).format(
                problems=" | ".join(enforceable))
        out, warnings, fidelity_warnings = _generate_narration(
            payload, view, prev, p_lines, correction_notes=correction,
            fidelity_facts=_fidelity_facts, language=ctx.language)

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
        craft_note = prompt_fragment(
            "narrator_craft_correction", ctx.language).format(
                problems="; ".join(best_tells))
        r_out, r_warnings, r_fid = _generate_narration(
            payload, view, prev, p_lines, correction_notes=craft_note,
            fidelity_facts=_fidelity_facts, language=ctx.language)
        r_enforceable = [w for w in r_fid if w.startswith(_ling("_ENFORCEABLE_PREFIXES"))]
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

        # THIS player's persona and THIS player's name. `player_name` was a
        # free variable here -- bound in `narrator`, never in `narrator_extra`
        # -- so every extra-player render raised NameError the moment a chat
        # had a second human in it. And the persona it reached for was the
        # chat's PRIMARY one, which would have filed the main player's
        # authored anatomy under the extra player's name: the same defect
        # `_authored_body_parts` exists to prevent, one player over.
        _abp2 = _authored_body_parts(
            ctx, extra.get("persona"), extra.get("name") or "Player")
        payload = {
            "player_view": view,
            "player_declared": player_declared,
            "cast_pronouns": _cast_pronouns(ctx.cast),
            **({"authored_body_parts": _abp2} if _abp2 else {}),
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
        payload = _extension_narration_payload(
            ctx, payload, scope="narrator_extra",
            player=extra.get("name") or "")
        out, warnings, fidelity_warnings = _generate_narration(
            payload, view, prev, p_lines, language=ctx.language)

        enforceable = [w for w in fidelity_warnings if w.startswith(_ling("_ENFORCEABLE_PREFIXES"))]
        if enforceable:
            correction = prompt_fragment(
                "narrator_fidelity_correction", ctx.language).format(
                    problems=" | ".join(enforceable))
            out, warnings, fidelity_warnings = _generate_narration(
                payload, view, prev, p_lines, correction_notes=correction,
                language=ctx.language)

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
