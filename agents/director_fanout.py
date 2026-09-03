"""The Director fan-out's deterministic frame: views, payloads, assembly, backstop.

Concurrency choice (`fanout_is_parallel`), the per-stage beat views each
specialist reads, scoped payload assembly, manifest slicing, channel
merge normalisation, the event-verdict echo, and the orchestration scope
backstop. The fan-out call itself (`_run_specialists`) and the repair
pass (`_specialist_repairs`) are model-calling and stay in
`agents/director.py`.

Import direction: nothing outside `agents/director*.py` may import an
`agents/director_*` submodule, and no `director_*` module may import
`agents.director` (that is the cycle the facade exists to prevent).
"""

from story.character_schema import character_name_from_text
from core.db import get_setting, wget
from world.survival import survival_enabled, vitals_of
from world.spatial import (contact_action_ledger_index, contact_id,
                           substance_ledger_index)

from .common import (communication_surface, observable_action_text,
                     scene_compact_attire)
from .director_evidence import _manifest_items
from .director_scopes import (
    SPECIALISTS,
    reads_dialogue,
    _CATEGORY_CHANNELS,
    _DELEGATED_CHANNELS,
    _LIST_DELEGATED,
    _PROSE_DUTY_SHIPPED,
    _STRUCTURAL_CHANNEL_FACTS,
    _note_key_forms,
)

def fanout_is_parallel():
    """Whether the Director's specialists run at once (default) or in turn.

    PARALLEL IS THE DEFAULT and is what the fan-out is for: the specialists
    are handed disjoint channels of the same finished beat, so they have
    nothing to say to each other and the beat's cost is its slowest hand
    rather than the sum of them.

    Sequential exists because concurrency is not free everywhere -- a
    provider with a one-request-at-a-time key, a rate limit measured in
    concurrent connections, a local runtime serving one model on one GPU.
    Under those, parallel dispatch does not go faster and can fail. It is
    NOT a fallback to the monolith: the same specialists run with the same
    scopes, assembled in the same canonical order, and a beat still
    dispatches a mean 1.75 of 6 hands carrying 1-4k sheets. Sequential
    fan-out is expected to beat the single ~21k-token sheet it replaced;
    parallel simply beats it by more.
    """
    value = str(get_setting("director_fanout_mode") or "").strip().casefold()
    return value not in ("sequential", "serial", "one_at_a_time")


def _normalized_ledger_notes(out):
    """The Director's rulings, blank lines dropped.

    Shared by BOTH beat views on purpose. `director_interpret` is a structural
    mirror of `director_resolve` -- same fan-out, same six hands -- and the
    ruling channel was added to the resolve half only, so the interpret half
    ran its specialists with nothing to transcribe. A copy of this dict
    comprehension in each view is how that happens again.
    """
    return {
        str(k): str(v).strip()
        for k, v in ((out or {}).get("ledger_notes") or {}).items()
        if isinstance(v, str) and str(v).strip()
    }


def _resolve_beat_view(out, decls, char_actions, dice, p_name, interp):
    """The finished beat as every resolve-side specialist reads it."""
    ledger_notes = _normalized_ledger_notes(out)
    declared = {}
    for name, acts in (char_actions or {}).items():
        attempts = [str(a.get("attempt") or "") for a in acts
                    if isinstance(a, dict) and a.get("attempt")]
        if attempts:
            declared[name] = attempts
    player_attempts = [
        str(e.get("attempt") or "")
        for e in (interp.get("sequence") or [])
        if isinstance(e, dict) and e.get("type") == "action"
        and e.get("attempt")
    ]
    if player_attempts:
        declared[p_name] = player_attempts
    public_sources = []

    def speech_body(value):
        return str(value or "").strip().strip('"\'“”').strip().casefold()

    final_by_declaration = {}
    for line in out.get("dialogue_log") or []:
        if not isinstance(line, dict):
            continue
        key = (str(line.get("speaker") or "").strip().casefold(),
               speech_body(line.get("exact_quote")))
        final_by_declaration.setdefault(key, line)

    # Declarations are the authority for who spoke and for the exact words.
    # The prose author can omit a dialogue_log row; a later deterministic
    # backstop restores it, so sourcing evidence from the draft log here would
    # make the one omitted line Charter can never remember.  The draft is used
    # only to recover its addressee/medium when it did preserve them.
    speech_groups = [(str(p_name), interp.get("sequence") or [])]
    speech_groups.extend(
        (str(d.get("name") or ""), d.get("sequence") or [])
        for d in decls if str(d.get("name") or "").strip())
    for actor, sequence in speech_groups:
        ordinal = 0
        for spoken in sequence:
            if not isinstance(spoken, dict):
                continue
            if spoken.get("type") == "communication":
                surface = communication_surface(spoken)
                if surface:
                    public_sources.append({
                        "source_id": f"communication:{actor}:{ordinal}",
                        "kind": "communication", "actor": actor,
                        "surface": surface,
                        "target": str((spoken.get("targets") or [""])[0] or ""),
                        "volume": str(spoken.get("volume") or "normal"),
                        "tone": str(spoken.get("tone") or ""),
                        "visibility": str(spoken.get("visibility") or "overt"),
                        "conceal_from": list(spoken.get("conceal_from") or []),
                        "speech_acts": [{
                            "kind": str(spoken.get("act") or "other"),
                            "content": str(spoken.get("content") or ""),
                        }],
                    })
                    ordinal += 1
                continue
            if spoken.get("type") != "speech" \
                    or not str(spoken.get("text") or "").strip():
                continue
            quote = str(spoken["text"]).strip()
            final = final_by_declaration.get(
                (actor.casefold(), speech_body(quote))) or {}
            public_sources.append({
                "source_id": f"speech:{actor}:{ordinal}", "kind": "speech",
                "actor": actor, "exact_quote": quote,
                "target": str(final.get("intended_target") or "").strip(),
                "volume": str(spoken.get("volume") or "normal"),
                "tone": str(spoken.get("tone") or ""),
                "visibility": str(spoken.get("visibility") or "overt"),
                "conceal_from": list(spoken.get("conceal_from") or []),
                **({"medium": str(final.get("medium"))}
                   if final.get("medium") else {}),
            })
            ordinal += 1

    action_groups = [(str(p_name), interp.get("sequence") or [])]
    action_groups.extend(
        (str(actor), actions) for actor, actions in (char_actions or {}).items())
    for actor, actions in action_groups:
        ordinal = 0
        for action in actions or []:
            if not isinstance(action, dict) or action.get("type") != "action":
                continue
            # New normalized declarations always carry `observable`.  An old
            # unnormalised action with only `attempt` can contain private
            # purpose; it is safer to omit than to hand that purpose to a
            # bystander as an outward fact.
            if "observable" not in action:
                continue
            surface = observable_action_text(action).strip()
            if not surface:
                continue
            public_sources.append({
                "source_id": f"action:{actor}:{ordinal}", "kind": "action",
                "actor": actor, "surface": surface,
                "target": str((action.get("targets") or [""])[0] or ""),
                "visibility": str(action.get("visibility") or "overt"),
                "conceal_from": list(action.get("conceal_from") or []),
                # It is a witnessed declaration of conduct, not a claim that
                # every intended effect succeeded.
                "status": "attempted",
            })
            ordinal += 1

    return {
        "source": "resolved_beat",
        "prose": out.get("resolved_event") or "",
        "ledger_notes": ledger_notes,
        "dialogue": [
            {"speaker": d.get("speaker"), "exact_quote": d.get("exact_quote")}
            for d in (out.get("dialogue_log") or [])[:20]
            if isinstance(d, dict)
        ],
        "manifest": _manifest_items(out),
        "declared_actions": declared,
        "dice": dice if isinstance(dice, list) else [],
        "player": p_name,
        "cast": [str(d.get("name") or "") for d in decls if d.get("name")],
        "public_sources": public_sources[:20],
    }


def _interpret_beat_view(ctx, out, p_name):
    """The player's declaration as every interpret-side specialist reads
    it: the structured sequence (each element the player's own declared
    span), speech and movement -- NEVER `ctx.input` or `private_thought`,
    which can carry a private thought only the interpreting Director is
    entitled to read (the X19 lesson)."""
    sequence = []
    for element in (out.get("sequence") or []):
        if not isinstance(element, dict):
            continue
        sequence.append({
            k: element.get(k)
            for k in ("type", "text", "attempt", "raw_text", "commitment",
                      "act", "content", "phase_id", "phase", "depends_on",
                      "participants", "requires_contacts", "referents",
                      "targets", "asserted_effects", "intended_effects",
                      "volume")
            if element.get(k) is not None
        })
    declared = {}
    attempts = [str(e.get("attempt") or "") for e in sequence
                if e.get("type") == "action" and e.get("attempt")]
    if attempts:
        declared[p_name] = attempts
    return {
        "source": "player_declaration",
        # Same key the resolve view uses, so `_note_for` routes an
        # interpret-side ruling with no change of its own.
        "ledger_notes": _normalized_ledger_notes(out),
        "declaration": {
            "sequence": sequence,
            "speech": out.get("speech"),
            "movement": out.get("movement"),
        },
        "manifest": [],
        "declared_actions": declared,
        "dice": [],
        "player": p_name,
        "cast": [character_name_from_text(c["sheet"]) for c in ctx.cast],
    }


def _specialist_manifest_slice(name, view):
    """The numbered manifest entries in one specialist's categories.

    One definition, read twice: once to build the payload the specialist is
    given, once to record which ids it was HANDED (design note 21). Two
    spellings of this filter would mean a specialist could be judged on an
    event it never received.
    """
    channels = SPECIALISTS[name]["channels"]
    return [
        item for item in (view.get("manifest") or [])
        if _CATEGORY_CHANNELS.get(item.get("category")) in channels
    ]



def _note_for(notes, name):
    """This hand's ruling, however the Director spelled the ledger.

    Measured across seven beats on gemini-3.6-flash: 8 of 11 notes were keyed
    by CHANNEL (`positions`, `conditions`, `overlays`, `entities`) and 1 by
    specialist name, so a lookup by hand alone would have dropped nearly three
    quarters of the Director's rulings. Two more arrived as `pose` and
    `transit`; `pose` is `poses` with a letter missing -- a correct ruling
    about the very ledger whose staleness motivated this channel, lost to a
    plural.
    """
    if not notes:
        return None
    lowered = {}
    for key, value in notes.items():
        if not isinstance(value, str) or not value.strip():
            continue
        for form in _note_key_forms(key):
            lowered.setdefault(form, value.strip())
    for candidate in (name,) + tuple(SPECIALISTS[name].get("channels") or ()):
        for form in _note_key_forms(candidate):
            if form in lowered:
                return lowered[form]
    return None

def _specialist_payload(name, ctx, sc, view, extras):
    """One specialist's scoped payload -- its written entitlement, applied
    to whichever stage's beat view it was handed. Shared part: the beat
    (prose+dialogue at resolve, the declaration at interpret), declared
    action attempts, final dice, the beat's manifest entries in this
    specialist's categories, and the roster. Per-specialist part: its OWN
    ledgers, and a minimal name index where its subjects need naming. What
    is absent is the entitlement's other half: no room graph, no lore, no
    minds, no world machinery, never the raw player input, and never
    another specialist's ledgers."""
    spec = SPECIALISTS[name]
    payload = {
        "source": view["source"],
        "player": view["player"],
        "cast": view["cast"],
        "declared_actions": view["declared_actions"],
        "dice_results_final": view["dice"],
        "variant_seed": extras.get("nonce"),
    }
    if view["source"] == "resolved_beat":
        payload["resolved_event"] = view["prose"]
        # The Director's ruling for THIS hand's channels, when it made one.
        # Scoped like every other slice: a specialist sees its own note and
        # no one else's, so this carries authority without carrying another
        # hand's ledger. Absent when the beat settled nothing here.
        # Keyed by SPECIALIST or by any CHANNEL that specialist owns. Measured
        # 2026-09-01: gemini-3.6-flash returned {"contact": ..., "vitals": ...}
        # -- `contact` is a hand and `vitals` is one of `body`'s channels, and
        # the Director was right both times. Insisting on the hand's name
        # would have silently dropped a correct ruling, which is the failure
        # this whole channel exists to prevent.
        notes = view.get("ledger_notes") or {}
        note = _note_for(notes, name)
        if isinstance(note, str) and note.strip():
            payload["director_note"] = note.strip()
        # Dialogue only to the hands that own a channel a speech act can
        # write (`director_scopes.reads_dialogue`). Saying a thing is not a
        # physical action, so for `body`, `contact` and `objects` the
        # transcript is material they cannot act on and can only echo -- and
        # echoing the payload into the diff is this fan-out's measured
        # failure mode. Measured over chat 78: 27% of the beat text every
        # hand received, ~68 tokens a beat, on sheets whose correct answer
        # was `{}`. The prose still carries what happened, including what
        # speech made happen.
        if reads_dialogue(name):
            payload["dialogue_log"] = view["dialogue"]
    else:
        payload["player_declaration"] = view["declaration"]
    manifest = _specialist_manifest_slice(name, view)
    if manifest:
        payload["changes_asserted"] = manifest

    rooms_index = {
        rid: str((room or {}).get("name") or rid)
        for rid, room in (sc.get("rooms") or {}).items()
    }
    # WORN GARMENTS, NAMEABLE BY EVERY HAND. Identity only -- the name and
    # whose body it is on -- never the wardrobe's state, coverage or
    # condition, which stay the body specialist's.
    #
    # A worn garment exists only inside sc.attire, so a specialist that
    # needed to name one could not: the contact specialist's live note says
    # it could not encode dampness on the shorts because "objects not in
    # entity_names", and the objects specialist minted a duplicate object for
    # the same reason and said so. A hand that cannot name a thing invents
    # one, and the invention becomes a second record of a garment that
    # already existed.
    #
    # This widens who can be NAMED, not what is KNOWN -- the same category
    # as `rooms` and `entity_names`, which every relevant specialist
    # already carries. It is not another specialist's ledger: no state
    # crosses, and the firewall's subject is minds, which this does not
    # touch.
    worn_index = [
        {"name": str(garment), "worn_by": str(who)}
        for who, entry in (sc.get("attire") or {}).items()
        if isinstance(entry, dict)
        for garment in (entry.get("wearing") or [])
        if str(garment).strip()
    ]
    if name == "body":
        payload.update({
            "attire": scene_compact_attire(sc),
            # The index its own sheet sends it to: "take the name from an
            # index the payload already carries (cast, entity_names, the room
            # index, worn_garments)". Every specialist that might mention a
            # garment in passing had it; the one whose channels ARE the
            # wardrobe did not, so the only garment names in its payload lived
            # inside the compact attire line -- delimiter-packed, with each
            # description truncated at ATTIRE_LOOK_CHARS. Chat 78 t7: it read
            # across the `=` and emitted a coverage entry for "modern
            # open-front jacket", the first 58 characters of the travel
            # jacket's description, which is a garment no ledger has ever had.
            "worn_garments": worn_index,
            "overlays": sc.get("overlays") or {},
            "active_awareness": extras.get("active_awareness"),
            "active_restraints": extras.get("active_restraints"),
            # `director_scopes` gives the `conditions` channel to
            # this hand, so it is the one that must re-assert a row
            # that still holds or end one that has ended -- and the
            # only one entitled to the ledger.
            "active_conditions": extras.get("active_conditions"),
            "simulation_clock": extras.get("clock"),
            "rooms": rooms_index,
        })
        if extras.get("body_parts"):
            payload["body_parts"] = extras["body_parts"]
        if survival_enabled(ctx.chat["id"]):
            names = [view["player"]] + list(view["cast"])
            payload["vitals"] = {
                n: vitals_of(sc, n) for n in names if n
            }
    elif name == "social":
        from persist.commit import presence_name_items
        # The specialist sees NAMES: the ledger keys on minted uids, and a
        # model payload never carries one.
        payload["background_presences"] = sorted(
            n for n, _r in presence_name_items(
                wget(ctx.chat["id"], "background_presences", {}) or {}))
        if view.get("public_sources"):
            payload["public_sources"] = list(view.get("public_sources") or [])
        # The traffic ledgers, exactly as the retired offscreen hand
        # received them (built precisely so a Director could name the uids
        # its ops require): crowds and couriers in reach, who carries which
        # report, the standing hearsay, and a room index for the rooms an
        # op names. A crowd is a charter projection and a courier a body on
        # a route, so charter SIMULATES both; the ops are this hand's.
        payload.update({
            "crowds": extras.get("crowds") or [],
            "couriers": extras.get("couriers") or [],
            "carried_reports": extras.get("carried_reports") or [],
            "unratified_claims": extras.get("unratified_claims") or [],
            "rooms": rooms_index,
        })
    elif name == "contact":
        raw_contacts = (extras.get("contacts")
                        if extras.get("contacts") is not None
                        else (sc.get("contacts") or []))
        payload.update({
            "contacts": [
                {**row, "contact_id": contact_id(row)}
                for row in raw_contacts if isinstance(row, dict)
            ],
            "contained": sc.get("contained") or {},
            "scales": sc.get("scales") or {},
            "rooms": rooms_index,
            "entity_names": {
                eid: str((e or {}).get("name") or eid)
                for eid, e in (sc.get("entities") or {}).items()
            },
            "worn_garments": worn_index,
            # THIS HAND'S OWN TWO LEDGERS, handed back with the ids its
            # documented ops address. It alone owns `substance_ops` and
            # `contact_action_ops`, and it had never seen either ledger: its
            # sheet says "Use {op:'remove',substance_id} when a known record
            # is drained, washed away..." while no substance_id had ever
            # reached it, so the op could not be written. Measured
            # corpus-wide before this: 38 adds against 5 removes and zero
            # removes after turn 38 of the reference story, which
            # DESIGN_MATERIAL_MODEL.md §1 reads as prompt efficacy rather
            # than a missing mechanism -- untestable until the ids arrive.
            # The effect ledger is the same story: with nothing to name,
            # `change` was unreachable and a reworded `add` was the only
            # move, which is how one dynamic came to stand as three rows.
            #
            # This widens what the OWNER can ADDRESS, not what any mind
            # knows: Director payloads are objective-causality surfaces, no
            # cognition payload changes, and no other hand gains the keys.
            "substances": substance_ledger_index(sc),
            "contact_actions": contact_action_ledger_index(sc),
        })
        if extras.get("body_parts"):
            payload["body_parts"] = extras["body_parts"]
        if extras.get("contact_endings") is not None:
            payload["character_contact_endings"] = extras["contact_endings"]
        if extras.get("material_effects") is not None:
            payload["character_material_effects"] = extras["material_effects"]
    elif name == "objects":
        payload.update({
            "entities": sc.get("entities") or {},
            "rooms": rooms_index,
            "notices": extras.get("notices") or [],
            "worn_garments": worn_index,
        })
        # The doors this beat reached for that no plan holds: the compiler's
        # needs. This hand renders the surface -- a stub with the exits the
        # beat perceived -- and never a plan.
        if extras.get("planning_needs"):
            payload["planning_needs"] = extras["planning_needs"]
        if extras.get("present_figures"):
            # WHO IS ALREADY STANDING HERE, for the one hand that mints
            # people. Derived, not the durable ledger: a charter body
            # holding a post in this room whether or not it has earned a
            # presence record (`agents.common.present_charter_figures`).
            # Absent when nobody is, so an ordinary scene's payload is
            # unchanged.
            payload["present_figures"] = [
                {"name": f.get("name"), "role": f.get("role"),
                 "room": f.get("room"),
                 **({"look": f["look"]} if f.get("look") else {}),
                 # The plan uid a render settles through, and for an
                 # authored plan (`world.planned_entities`) its kind and
                 # brief: what it is for, what is true of it.
                 **({"plan": f["plan"]} if f.get("plan") else {}),
                 **({"kind": f["kind"]}
                    if str(f.get("kind") or "person") != "person" else {}),
                 **({"brief": f["brief"]} if f.get("brief") else {})}
                for f in extras["present_figures"] if not f.get("reserved")]
    elif name == "spatial":
        # The one specialist entitled to the full graph: it is the graph's
        # keeper. Everything else here is the geography's own ledgers plus
        # each declared mover's heading -- never lore, minds, or bodies.
        payload.update({
            "rooms": sc.get("rooms") or {},
            "positions": sc.get("positions") or {},
            "stations": sc.get("stations") or {},
            "poses": sc.get("poses") or {},
            "contained": sc.get("contained") or {},
            # THE VOICE LEDGER, WITH THE IDS ITS OPS ADDRESS. The same
            # omission the substances and contact-effect ledgers had above,
            # and the same fix: this hand alone owns `comms_ops`
            # (`director_scopes.SPECIALISTS["spatial"]["channels"]`), its own
            # chunk documents `set` as "a COMPLETE replacement snapshot" of
            # one channel and `open`/`close`/`remove` as edits addressed by
            # `id` -- and no id had ever reached it. Every maintenance op was
            # therefore written against a GUESSED key, and
            # `spatial_senses.apply_comms_ops` (world/spatial_senses.py:249)
            # fails silently in three different directions on a wrong one:
            # `remove` pops nothing, `open`/`close` find no `existing` dict
            # and flip nothing, and a re-`set` installs a SECOND channel
            # beside the one it meant to replace. A smashed radio then keeps
            # carrying voices through walls for the rest of the story,
            # because perception reads `scene["comms"]` and nothing else.
            #
            # Rows rather than the stored table, because `comms_ops` is a
            # LIST whose entries carry `id` -- the ledger comes back in the
            # shape the op is written in, as `substances` and
            # `contact_actions` do. Sorted so the payload is stable between
            # beats that changed nothing.
            #
            # Widens what the OWNER can ADDRESS, not what any mind knows:
            # this is the geography's own ledger on an objective-causality
            # surface, no cognition payload changes, no other hand gains it.
            "comms": [
                {"id": str(channel_id), **channel}
                for channel_id, channel in sorted(
                    (sc.get("comms") or {}).items(),
                    key=lambda kv: str(kv[0]))
                if isinstance(channel, dict)
            ],
            "movement": extras.get("movement"),
            "movers": extras.get("movers") or {},
            # The geometry's sight digest -- who sees whom, who is within
            # reach, what cover stands between -- computed from the ledgers
            # this hand writes (stations, poses, facing) so it can see what
            # its own entries come to. Objective causality, not a mind.
            "sightlines": extras.get("sightlines"),
        })
        # The doors this beat reached for that no plan holds: the compiler's
        # needs. This hand renders the surface -- a stub with the exits the
        # beat perceived -- and never a plan.
        if extras.get("planning_needs"):
            payload["planning_needs"] = extras["planning_needs"]
        # The plan's seed for the stubs in reach: this hand furnishes them
        # (rooms chunk, A ROOM YOU ARE HANDED AS PLANNED). Author knowledge
        # on an objective-causality surface; no mind receives it.
        if extras.get("planned_rooms"):
            payload["planned_rooms"] = extras["planned_rooms"]
    return payload


def _stage_container(out, stage, channel):
    """Where a channel lives in this stage's output: the resolve diff, or
    interpret's state_assertions -- except interpret's contact channel,
    which the interpret contract spells `contact_assertions` (the same ops,
    validated by `_validated_player_contact_assertions` downstream exactly
    as a model-authored copy would be)."""
    if stage == "resolve" and channel == "public_evidence":
        return out, "public_evidence"
    if stage == "interpret" and channel == "contact_ops":
        return out, "contact_assertions"
    key = "state_diff" if stage == "resolve" else "state_assertions"
    container = out.get(key)
    if not isinstance(container, dict):
        container = {}
        out[key] = container
    return container, channel


def _normalized_channel_value(channel, value):
    if channel == "destruction":
        return value if isinstance(value, dict) and value else None
    if channel in _LIST_DELEGATED:
        return value if isinstance(value, list) else []
    return value if isinstance(value, dict) else {}


#: The verdicts a specialist may return on a numbered event. Anything else
#: -- a blank, a synonym, a sentence -- is dropped rather than guessed at:
#: an unrecognized verdict must read as "this event was not addressed", the
#: same as silence, because the whole point of the echo is that only a
#: DELIBERATE answer counts as one.
_EVENT_VERDICTS = frozenset({"encoded", "already_true", "not_mine"})


def _resolved_event_verdicts(result, granted_ids):
    """One specialist's resolved_events, kept only where they answer an
    event this call was actually handed.

    An id outside `granted_ids` is discarded: a specialist cannot acquit an
    event it never saw, and a model that echoes the whole manifest back
    would otherwise silence every omission in the beat. Last verdict wins
    on a duplicated id -- deterministic, and the shape is already degenerate.
    """
    granted = {int(i) for i in granted_ids}
    verdicts = {}
    for entry in (result.get("resolved_events") or []):
        if not isinstance(entry, dict):
            continue
        try:
            event_id = int(entry.get("event_id") or 0)
        except (TypeError, ValueError):
            continue
        status = str(entry.get("status") or "").strip().casefold()
        if event_id in granted and status in _EVENT_VERDICTS:
            record = {"status": status}
            # An address is only meaningful ON a decline, and only when it
            # names a hand that exists. Anything else is dropped rather
            # than carried into routing as a half-fact.
            target = str(entry.get("reroute_to") or "").strip().casefold()
            if status == "not_mine" and target in SPECIALISTS:
                record["reroute_to"] = target
            verdicts[event_id] = record
    return [{"event_id": eid, **verdicts[eid]}
            for eid in sorted(verdicts)]


def _index_addressed_events(dispatch):
    """event_id -> {owner, status}, across every specialist that ran.

    The beat-wide answer to "was this event addressed by the mind that owns
    it?". Only a specialist that RAN contributes: a failed call leaves its
    events unaddressed, which is what keeps a fail-open failure from
    silently acquitting the changes it was supposed to encode.
    """
    index = {}
    for name, state in (dispatch or {}).items():
        if not isinstance(state, dict) or not state.get("ran"):
            continue
        for entry in (state.get("events_resolved") or []):
            index[int(entry["event_id"])] = {
                "owner": name, "status": entry["status"],
                **({"reroute_to": entry["reroute_to"]}
                   if entry.get("reroute_to") else {})}
    return index


def _author_emitted_channels(out, stage):
    """The delegated channels the STAGE AUTHOR itself put content in.

    Read once, before any specialist merges, and kept on the orchestration
    record as `author_emitted`, because it is the only thing the scope
    backstop's channel half is about: the author's lean sheet says to leave
    every delegated channel empty, so author content in a channel no served
    hand owns is the mis-emission worth reporting. Everything else that
    can stand in a delegated channel at the end of the beat is legitimate
    and was being mistaken for it once dispatch stopped running every hand
    on every physical beat -- the engine's own seams (`_ground_public_evidence`
    mints `public_evidence` from the beat's source list on every beat with a
    line or an act; the movement backstop writes a declared, unblocked move
    into `positions` itself), and an owner's repair call landing in a
    channel its hand was not dispatched for. Under the gate-keyed dispatch
    the social and spatial hands ran on exactly those beats, so the
    confusion never surfaced; under the ruling-keyed one it fired on a
    quiet line of dialogue and on a plain walk through an open door.
    """
    emitted = []
    for channel in _DELEGATED_CHANNELS:
        container, key = _stage_container(out, stage, channel)
        if container.get(key):
            emitted.append(channel)
    return emitted


def _structurally_absent_channels(specialists):
    """Channels that cannot be served in this story whatever the beat holds."""
    facts = {}
    for state in (specialists or {}).values():
        if isinstance(state, dict) and isinstance(state.get("facts"), dict):
            facts = state["facts"]
            break
    return {channel for channel, fact in _STRUCTURAL_CHANNEL_FACTS.items()
            if fact in facts and not facts.get(fact)}


def _orchestration_scope_backstop(ctx, out, stage):
    """`changes_asserted` reconciliation pointed at the SCOPE.

    Runs LAST, on the final reconciled output, and only on the orchestrated
    path. One check covers both an unserved hand and a wrongly omitted
    chunk, because both are the same fact: a channel was not in any SERVED
    scope (granted to a specialist that ran) and content for it shipped
    anyway -- a manifest entry in that channel's category, or channel
    content in the final output (the stage model's own, or the repair
    seam's). Every such channel is REPORTED through `tell_director` and
    never dropped: fail-open means the unowned content stands and the
    existing deterministic seams keep judging it.

    Since dispatch keyed on the Director's ruling, an unserved CHANNEL has
    one ordinary cause: the ruling never reached its hand -- no
    `ledger_notes` line and no `changes_asserted` entry in its categories
    -- and the author encoded the change itself anyway (`author_emitted`
    is the snapshot that tells the author's content from an engine seam's
    or a repair's), or a hand that was addressed failed. A manifest entry
    always addresses its hand, so the manifest half of this check now
    fires only for a failed call or a ledger the story does not keep. An
    unserved PROSE DUTY is still a gate prediction that the beat proved
    wrong.

    The record also carries the per-beat scope measurement the experiment
    is judged by: granted vs served vs produced, where over-grant is only
    cost and under-grant is the dangerous direction this backstop exists
    to catch."""
    record = out.get("orchestration") or {}
    if not record.get("enabled"):
        return
    specialists = record.get("specialists") or {}
    granted, served = set(), set()
    failed = []
    for name, state in specialists.items():
        scope = set(state.get("scope") or ())
        granted |= scope
        if state.get("run") and state.get("ran"):
            served |= scope
        elif state.get("run"):
            failed.append(name)
    produced = []
    flags = []
    # Only the AUTHOR's own content in an unserved channel is a flag; an
    # engine seam's write or an owner's repair is not (see
    # `_author_emitted_channels`). A record without the snapshot -- there
    # is none on the live path -- falls back to flagging everything.
    emitted = record.get("author_emitted")
    for channel in _DELEGATED_CHANNELS:
        container, key = _stage_container(out, stage, channel)
        if container.get(key):
            produced.append(channel)
            if channel not in served \
                    and (emitted is None or channel in emitted):
                flags.append(f"{key} carries content for {channel!r}")
    if stage == "resolve":
        # A channel can be unserved for two different reasons, and only one
        # of them is a gate mispredict. "No work in it THIS BEAT" is a
        # prediction, and a manifest item naming it is evidence the
        # prediction was wrong. "This story has no such ledger AT ALL" is
        # not a prediction -- a story with survival off has no vitals to
        # change, ever -- so a manifest item naming it says the Director
        # mis-categorised, not that the gate misfired.
        #
        # Measured live (chat 71, survival off): the resolve filed a
        # climax's spent-ness under `vitals` because 8.2.2 told it to take
        # the CLOSEST category and never omit, and the backstop announced
        # "the scope gate mispredicted" about a channel that shipped
        # nothing and could never have shipped anything. A warning that
        # fires when nothing is wrong is how a reader learns to skip
        # warnings, so this one is told apart from the real thing and sent
        # to the Director as the categorisation note it actually is.
        structural = _structurally_absent_channels(specialists)
        for item in _manifest_items(out):
            channel = _CATEGORY_CHANNELS.get(item.get("category"))
            if not channel or channel in served:
                continue
            subject = item.get("subject") or "an unnamed subject"
            if channel in structural:
                ctx.tell_director(
                    f"categorisation: a {item['category']} change was "
                    f"asserted for {subject!r}, but this story keeps no "
                    f"{channel} ledger, so nothing can record it. File a "
                    f"change like this under the closest category this "
                    f"story DOES keep, or leave it to the prose.")
                continue
            flags.append(
                f"the prose asserts a {item['category']} change for "
                f"{subject!r} ({channel} was not in any served scope)")
    # The prose half, same mechanism: the beat's final output shows a duty
    # whose prose-author block was not loaded. Only on records that carry a
    # prose scope (the orchestrated resolve; interpret's sheet is not yet
    # leaned), and only for the chunks whose gate is a prediction
    # (_PROSE_DUTY_SHIPPED). Reported, never dropped: the model did the
    # duty anyway, so the flag is gate-misprediction evidence, not a loss.
    prose = record.get("prose_scope")
    if stage == "resolve" and isinstance(prose, dict):
        prose_granted = set(prose.get("granted") or ())
        final_diff = out.get("state_diff")
        final_diff = final_diff if isinstance(final_diff, dict) else {}
        for name, probe in _PROSE_DUTY_SHIPPED.items():
            if name in prose_granted:
                continue
            try:
                evidence = probe(out, final_diff)
            except Exception:
                evidence = None
            if evidence:
                flags.append(
                    f"{evidence}, and the prose author's {name!r} duty "
                    "block was not loaded (widen its gate if this recurs)")
    record["scope_report"] = {
        "granted": sorted(granted),
        "served": sorted(served),
        "produced": sorted(produced),
    }
    if not flags:
        return
    # A FAILED specialist is not a mispredicted gate. Its scope was granted
    # correctly and simply went unserved, so the author's own content
    # standing in that channel is fail-open working exactly as designed --
    # blaming the gate for it sends the next reader to widen a gate that
    # was already right. Measured live: a contact call died on a provider
    # returning reasoning with no answer, and the backstop reported "the
    # scope gate mispredicted" for a channel the gate had granted.
    if failed:
        note = (
            "orchestration: "
            + ", ".join(failed) + " specialist call(s) failed, so their "
            "granted scope went unserved and the stage model's own content "
            "stands there (fail-open, working as designed) -- "
            + "; ".join(flags)
            + ". Nothing was dropped and the reconciliation seam stands. "
            "The gate is not implicated; the CALL failed.")
        ctx.tell_director(note)
        ctx.add_warning(note)
        return
    note = (
        "orchestration scope: content shipped for channels or prose duties "
        "outside any served scope -- "
        + "; ".join(flags)
        + ". Nothing was dropped (fail-open); the stage model's encoding "
        "and the reconciliation seam stand. A channel here means the "
        "Director's ruling never reached the hand that owns it (no "
        "ledger_notes line and no changes_asserted entry in its categories) "
        "and the author encoded the change itself; a prose duty here means "
        "its gate mispredicted."
    )
    record["gate_flags"] = flags
    ctx.tell_director(note)
    ctx.add_warning(note)
