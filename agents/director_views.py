"""Read-only views and payload projections for the Director stages.

The per-beat views a stage puts in a payload -- crowds, couriers, posted
notices, carried reports, unratified hearsay, round conduct, extension
payload dispatch, opening pose seeds -- plus the two post-hoc output
audits (_audit_fact_adjudications, _report_observer_epithets) and the
authorial-channel floor (_route_authorial_npc_beat).

Import direction: nothing outside `agents/director*.py` may import an
`agents/director_*` submodule, and no `director_*` module may import
`agents.director` (that is the cycle the facade exists to prevent).
"""

import copy
import json
import re

from story.character_schema import (
    _UNSPACED_SCRIPT,
    character_appearance,
    character_name,
    persona_appearance,
)
from story.scene import persona_of
# One lexicon of forms of address, not two. `world.background_claims` already
# owns what counts as one, because its matching side has to know that "Worf"
# and "Lieutenant Worf" are one referent; the assertion side below has to agree
# with it or a legitimately authored form reads as an invention in one module
# and as a known variant in the other.
from world.background_claims import is_title_only

from .common import (
    _NAME_TOKEN_RE,
    _dict,
    _ling,
    _name_token_floor,
    _sync_sequence_mirrors,
    _unknown_actor_label,
    authored_other_subject,
    character_scene_keys,
)

def _cast_match_forms(cast):
    """Two views of the cast's identifying text, both casefolded: by id (for
    subject detection) and by display name (for target binding)."""
    by_id, by_name = {}, {}
    for row in cast or []:
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        name = character_name(sheet)
        if not name:
            continue
        forms = [str(k).casefold() for k in character_scene_keys(sheet)
                 if str(k or "").strip()]
        if not forms:
            forms = [name.casefold()]
        by_id[row["id"]] = forms
        by_name[name] = forms
    return by_id, by_name



def _route_authorial_npc_beat(ctx, out, actor_forms=()):
    """Authorial-channel floor (P3): when the PLAYER authors another character's
    INTERIOR cognition or AUTONOMOUS response -- a beat whose subject is a
    sheeted cast member and whose outcome is theirs alone to have ('Dr. Moon
    remembers she has her smartphone', 'the strain finally pushes Dr. Moon over
    the edge') -- that is the player puppeting a mind the character owns.
    Reroute it from a fait-accompli pc_action into an OFFER handed to that
    character's own agent (out['authorial_offers'], surfaced in character_step),
    and drop it from the resolved sequence so the Director never enacts it as
    objective truth. Any OBJECT the same input introduces (the phone exists)
    still rides the normal world/generation path.

    Cognition was the original scope, and it left the twin case open: an
    involuntary bodily outcome authored for a character is puppeting by the
    same argument, and because such an element stayed in the PLAYER's sequence
    it inherited the player as its actor -- perception prepends the actor label
    to the `observable` surface, so the outcome was delivered to every observer,
    and to the narrator, as something the PLAYER underwent.

    Subject detection is common.authored_other_subject; 'I remember Dr. Moon's
    face' (the player's own recall about a character) and 'stabs Sarah' (the
    player acting ON someone) are both left alone."""
    cast_forms, _ = _cast_match_forms(ctx.cast)
    if not cast_forms:
        return
    offers = out.setdefault("authorial_offers", [])
    kept = []
    changed = False
    for e in (out.get("sequence") or []):
        subject_cid = authored_other_subject(e, cast_forms, actor_forms)
        if subject_cid is not None:
            att = str(e.get("attempt") or "")
            offers.append({
                "subject_id": subject_cid,
                "proposition": att,
                "source": "player",
            })
            ctx.add_warning(
                "director_interpret: player-authored NPC cognition or response "
                f"rerouted to an offer for cast {subject_cid} ({att!r})")
            changed = True
            continue  # drop the puppeted beat from the resolved sequence
        kept.append(e)
    if changed:
        out["sequence"] = kept
        # Re-derive the scalar mirrors (action/actions/speech) after dropping an
        # element. Runs on the already-normalized sequence (norm_sequence first).
        _sync_sequence_mirrors(out)


def _opening_pose_snapshots(out):
    """Explicit opening poses plus legacy entity_states.posture seeds."""
    poses = copy.deepcopy(
        out.get("poses") if isinstance(out.get("poses"), dict) else {})
    for subject, state in (out.get("entity_states") or {}).items():
        if subject in poses or not isinstance(state, dict):
            continue
        posture = str(state.get("posture") or "").strip()
        if posture:
            poses[subject] = {"posture": posture}
    return poses


def _extension_director_payload(ctx, payload, *, phase):
    """Hand an assembled Director payload to installed extensions, or leave it.

    Lazy-imported and total, the same discipline as the character and narration
    routing seams and for the same reason: this runs inside the turn's wall
    clock, so a broken extension must cost the beat nothing. With nothing
    installed -- the overwhelmingly common case -- this is one attribute lookup.
    """
    try:
        import extension_runtime

        return extension_runtime.dispatch_director_payload(
            ctx, payload, phase=phase)
    except Exception:
        return payload


# WHAT THE DIRECTOR NEEDS FROM AN INTERACTION ROUND, AND WHAT IT MUST NOT HAVE.
#
# A round carried each character's ENTIRE decision output -- measured on chat
# 67 turn 48, 10,791 chars for a single round, of which the conduct is ~2,400:
# appraisal 1,981, active_state 1,105, response_candidates 1,029,
# mind_model_updates 768, plus every memory/evidence/belief internal and the
# per-mind `delivered_views`.
#
# The size is the smaller problem. `response_candidates` is what a character
# WEIGHED AND DID NOT DO, and CLAUDE.md draws the line this crosses: the
# Director owns objective causality and does not own character psychology. A
# stage adjudicating what happened should not be reading what was nearly said.
#
# So the round is projected to conduct: who spoke, in what order, and what they
# did. That is what ordering a beat needs, and it is what `dialogue_order` and
# the speech-authority guards are checked against.
_ROUND_CONDUCT_KEYS = ("sequence", "speech", "speech_volume", "action",
                       "actions", "material_effects", "interaction", "name")


def _round_conduct(rounds):
    """Interaction/reaction rounds reduced to what was said and done.

    The two loops spell the actor differently -- the interaction loop records
    `speaker` (agents/loops.py), the reaction loop records `reactor` -- and
    reading only `speaker` delivered every reaction round here as
    `speaker: null`: speech and actions with nobody attached to them. Found by
    reading the payloads of a real-model playthrough, where three reactions in
    one resolve carried a full sequence and an `event_id` naming the
    character, and no name. This stage adjudicates contested physical
    reactions off exactly this list, so it was being asked to decide who did
    what to whom with the who removed.

    Folded here because this is the one place the two spellings meet. A guard
    each loop had to remember is the guard this project's history says gets
    forgotten.
    """
    out = []
    for entry in rounds or []:
        if not isinstance(entry, dict):
            continue
        result = entry.get("result")
        result = result if isinstance(result, dict) else {}
        conduct = {k: result[k] for k in _ROUND_CONDUCT_KEYS
                   if result.get(k) not in (None, "", [], {})}
        out.append({"round": entry.get("round"),
                    "speaker": entry.get("speaker") or entry.get("reactor"),
                    "result": conduct})
    return out


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

def _unratified_background_claims(chat_id, turn_idx):
    """Still-live hearsay from background presences, for the Director to settle.

    Best-effort: a failure here must never cost the turn its resolution, so it
    degrades to no claims rather than raising.
    """
    try:
        from world.background_claims import unratified_claims
        return unratified_claims(chat_id, turn_idx)
    except Exception:
        return []


def _report_observer_epithets(ctx, out, sc, p_name):
    """Report an OBSERVER-RELATIVE epithet used in the objective record.

    `_unknown_actor_label` builds a descriptor from a body's appearance FOR
    OBSERVERS WHO DO NOT KNOW THEM. A character using it in its own
    declaration is the firewall working. The Director using it is not: it is
    omniscient, it knows the name, and the objective account is the one
    representation from which every observer's own wording is derived.

    Observed live (three-model playthrough, 2026-08-12): `resolved_event` read
    "Bryn turns toward the young smith's apprentice standing at the group's
    edge" -- of the PLAYER, whose name the same paragraph had already used --
    and `intended_target` on both of Bryn's lines read "young smith's
    apprentice" rather than "Corin". The prose consequence is fixed
    downstream, deterministically, by the composer's identity floor
    (`common.self_reference_forms`); this is the feedback that lets the
    Director stop producing it, and it also names the STRUCTURED cost, which
    no downstream floor covers: `intended_target` is matched against canonical
    names, so a line addressed by epithet is addressed to nobody.

    Report-only. It never rewrites the account -- resolved_event and the words
    of dialogue_log are not this seam's to edit -- and it stays quiet unless
    the epithet is unambiguous: a descriptor two bodies in the scene share is
    skipped, because then it may honestly be describing someone unregistered.
    """
    bodies = []
    for row in (ctx.cast or []):
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        name = character_name(sheet)
        if name:
            bodies.append((name, character_appearance(sheet),
                           character_scene_keys(sheet)[1:]))
    pers = persona_of(ctx.chat)
    if isinstance(pers, dict) and p_name:
        bodies.append((p_name,
                       pers.get("appearance") or persona_appearance(pers),
                       (pers.get("identity") or {}).get("aliases") or []))
    labels = {}
    for name, appearance, aliases in bodies:
        label = str(_unknown_actor_label(name, appearance, aliases) or "")
        if label:
            labels.setdefault(label.casefold(), []).append(name)
    prose = str(out.get("resolved_event") or "")
    targets = [str((d or {}).get("intended_target") or "")
               for d in (out.get("dialogue_log") or []) if isinstance(d, dict)]
    for label_cf, owners in labels.items():
        if len(owners) != 1:
            continue                  # ambiguous descriptor: not ours to claim
        name = owners[0]
        in_prose = label_cf in prose.casefold()
        in_target = any(label_cf in t.casefold() or t.casefold() in label_cf
                        for t in targets if t.strip())
        if not (in_prose or in_target):
            continue
        where = " and ".join(
            [w for w, hit in (("resolved_event", in_prose),
                              ("intended_target", in_target)) if hit])
        note = (
            f"objective record: {name} was referred to in {where} as "
            f"{label_cf!r}, which is the appearance label perception mints "
            "for observers who have NOT recognized them. The objective "
            "account is omniscient -- name them canonically and let "
            "perception decide what each observer may call them, or a line "
            "addressed to them is addressed to no one the engine can match.")
        ctx.tell_director(note)
        ctx.add_warning(note)


def _report_unowned_address_forms(ctx, out, p_name):
    """Report a form of address the objective record attaches to a person that
    no card carries.

    A card's typed identity is exactly {uid, name, aliases, pronouns}. Every
    other authored attribute of a person -- what they are addressed as besides
    their name, how old they are, what kind of being they are, who they are to
    someone else -- exists only as free prose, and prose is not comparable to
    an assertion, so no stage can contradict one. That is why the defence a
    personal attribute gets is a function of whether the engine OWNS it as a
    typed field rather than of how much it matters: the two owned ones are both
    defended (an unearned name trips the composer's identity floor, a pronoun
    has `_check_pronoun_fidelity`) and everything else is uncontestable.

    Measured, chat 95 turn 1 (2026-08-28). A character agent that had not
    recognized the persona's body -- it called her "the compact woman standing
    behind the command chair", and its payload carried her authored form of
    address ZERO times -- declared the speech "Lieutenant Commander." The very
    next call, this stage's prose author, promoted that mistake into the
    omniscient third person: "Lieutenant Commander Sabine Oyelaran folds the
    five subspace metric traces onto a single overlay at the science station."
    Its own payload had carried the authored form twice, so this was never
    information starvation. From the following call on the invented form was in
    every specialist payload (51 of the 294 captured payloads, against 82
    carrying the authored one), and it committed into events rows, into another
    mind's autobiographical memory and into checkpoints -- after which it
    re-enters every mind through memory and every payload through the
    transcript. 133 warnings were raised across those 16 turns and not one
    concerned it.

    The seed of such an assertion is a mind being legitimately mistaken, which
    is fiction working: deception, dramatic irony and a mind acting on a false
    belief all need the mistake to be possible. So dialogue is not scanned. The
    failure is only ever the omniscient account ADOPTING a mistaken form of
    address as objective third-person fact -- the objective record is the one
    representation every observer's wording is derived from, so an assertion
    does not have to be true to become the shared past, it only has to survive
    to commit.

    Report-only, for the same reason `_report_observer_epithets` above is:
    `resolved_event` and the words of `dialogue_log` are not this seam's to
    edit. It is a report of an assertion the engine cannot source, not a claim
    that the engine knows the right answer -- it has no field to hold one.

    MEASURED BEFORE SHIPPING, because a false positive here would accuse an
    author of inventing what they wrote. Replayed over every stored
    `director_resolve` variant carrying prose in the development database
    (2,737, across 75 chats): 72 forms of address stand attached to a
    canonically named body, 67 of them are sourced to that person's card and
    pass, 5 are reported, and all 5 are the chat 95 defect above. Nothing else
    fires -- including the 52 in the one other chat whose fiction is thick with
    them, every one authored.

    Deliberately narrow, in three ways that each cost a real hit:
      * only whitespace may stand between the form and the name -- reading
        across a full stop turned "...admiration for her mother. The Doctor
        leans one hip..." into an invented form on every beat that used it;
      * a person whose own identity.name already carries a form of address is
        skipped entirely. That is the storage half of the same gap
        (docs/UNBUILT.md 1.84d, "a character has nowhere to carry a rank, so
        the rank goes in the name") and when the name holds one, an
        abbreviation written out in full in the prose is indistinguishable
        from a second, invented form: 24 hits in one chat of the replay, all
        one card;
      * a name token two bodies share is dropped, as in
        `_check_pronoun_fidelity` -- it no longer names one of them.

    A form of address is recognized by POSITION -- it precedes the name -- out
    of a lexicon that is English (`world.background_claims`'). So this is quiet
    for a language that marks address with a suffix rather than a prefix, and
    quiet where the lexicon does not reach. Same posture as the pronoun check
    toward a paradigm it cannot be certain about: silence, not a guess.
    """
    # The person's own card, as authored text. Free prose is the only place a
    # card can put this today, so prose IS a channel: what gets reported is a
    # form with no channel at all, not every form the typed identity omits.
    cards = {}
    for row in (ctx.cast or []):
        try:
            sheet = json.loads(row["sheet"])
        except Exception:
            continue
        name = character_name(sheet)
        if name:
            cards[name] = str(row["sheet"] or "")
    pers = persona_of(ctx.chat)
    if isinstance(pers, dict) and p_name:
        cards[p_name] = json.dumps(pers, ensure_ascii=False)

    ambiguous = _ling("_AMBIGUOUS_NAME_WORDS")
    owner = {}
    for name in cards:
        tokens = _NAME_TOKEN_RE.findall(name)
        if not tokens or is_title_only(tokens[0]):
            continue
        for token in tokens:
            if len(token) < _name_token_floor(token):
                continue
            # The capital is what separates a name part from an ordinary word
            # beside it -- in a script that HAS capitals. Same reasoning as
            # `_check_pronoun_fidelity`.
            if not _UNSPACED_SCRIPT.match(token[:1]) and not token[:1].isupper():
                continue
            if is_title_only(token) or token.lower() in ambiguous:
                continue
            if token in owner and owner[token] != name:
                owner[token] = None
            elif token not in owner:
                owner[token] = name
    owner = {t: n for t, n in owner.items() if n}
    if not owner:
        return

    scan = _ling("_NARRATION_QUOTE_RE").sub(" ", str(out.get("resolved_event") or ""))
    words = list(_NAME_TOKEN_RE.finditer(scan))
    reported = set()
    for i, match in enumerate(words):
        name = owner.get(match.group(0))
        if not name:
            continue
        run, j = [], i
        while j >= 1 and is_title_only(words[j - 1].group(0)):
            if scan[words[j - 1].end():words[j].start()].strip():
                break
            run.insert(0, words[j - 1].group(0))
            j -= 1
        if not run:
            continue
        form = " ".join(run)
        key = (form.casefold(), name)
        if key in reported:
            continue
        # Word-bounded rather than \b: the boundary has to hold against the
        # punctuation and quoting a card's prose is full of, and the form is an
        # alphabetic phrase by construction.
        if re.search(rf"(?<![A-Za-z]){re.escape(form)}(?![A-Za-z])",
                     cards.get(name) or "", re.IGNORECASE):
            continue
        reported.add(key)
        note = (
            f"objective record: resolved_event wrote {name} with the form "
            f"of address {form!r}, and nothing authored on this person carries "
            "it -- not identity.name, not aliases, not the card's own prose. A card's typed identity is only {uid, name, aliases, "
            "pronouns}, so a form of address asserted here is a person-"
            "attribute the engine owns no field for and therefore cannot "
            "contradict, and the objective account is the one representation "
            "every observer's wording is derived from: it becomes the shared "
            "past whether or not it is true. A character being mistaken out "
            "loud is fiction working and is not this -- in the omniscient "
            "sentences, name them canonically or use a form the card carries.")
        ctx.tell_director(note)
        ctx.add_warning(note)


def _crowds_view(chat_id, scene, turn_idx=None):
    """Crowds the party could act on, by room, with the id ops require.

    Not room-scoped to one observer the way perception is: the Director owns
    objective causality and moves crowds around the map, so it needs the ones
    in reach rather than the ones a single body can see. What it must NOT get
    is anything that would let it narrate them into a room nobody is near --
    which is why this is bounded to the rooms in the current scene.
    """
    from world import crowds as crowds_model
    from core.db import wget

    rooms = (scene or {}).get("rooms") or {}
    out = []
    for crowd in wget(chat_id, crowds_model.CROWDS_WORLD_KEY, []) or []:
        if not isinstance(crowd, dict):
            continue
        room = str(crowd.get("room_uid") or "")
        if room not in rooms:
            continue
        size = (rooms.get(room) or {}).get("size")
        out.append({
            "crowd_id": crowd.get("uid"),
            "room": room,
            "band": crowd.get("band"),
            "composition": crowd.get("composition"),
            "mood": crowd.get("mood"),
            "heading": crowd.get("heading") or None,
            "density": crowds_model.density(crowd.get("band"), size),
            "emerged": list(crowd.get("emerged") or []),
            # The reports this crowd is repeating, WITH their ids. Same
            # defect as the crowd uid and the carried-report id, same cause:
            # the prompt says a crowd may pass its talk on through
            # telling_ops, and a Director never shown a world_event_id the
            # crowd holds could only ever have that op refused with "does
            # not carry that report". Found the same way -- by reading the
            # captured payload as the model.
            "talk": crowds_model.talk_view(crowd, cap=4),
        })
    # The derived charter crowds, same bound, same shape -- WITH their uids,
    # for the same reason the authored ones carry theirs: `emerge` requires a
    # crowd_id the Director has seen. `derived` marks the difference in law:
    # move/split/disperse/set on one of these would make crowd ops a second
    # writer on where charter bodies stand, so `apply_ops` refuses them and
    # emerge resolves at the commit seam instead. `who` may be left empty on
    # a derived crowd -- the engine picks by entanglement.
    from agents.common import charter_crowds_for_room, chatter_inputs

    # ``turn_idx`` ages the presentation-lapse subtraction (§C3) exactly as
    # the perception read does, so the Director is offered the same derived
    # rows the observer was shown -- two readers, one derivation.
    inputs = chatter_inputs(chat_id, scene, turn_idx=turn_idx)
    for room in sorted(rooms):
        size = (rooms.get(room) or {}).get("size")
        for crowd in charter_crowds_for_room(chat_id, scene, room, inputs):
            out.append({
                "crowd_id": crowd.get("uid"),
                "room": room,
                "band": crowd.get("band"),
                "composition": crowd.get("composition"),
                "mood": crowd.get("mood"),
                "heading": None,
                "density": crowds_model.density(crowd.get("band"), size),
                "emerged": [],
                "talk": [],
                "derived": True,
            })
    return out


def _couriers_view(chat_id, scene):
    """Live couriers the resolve could act on, with the id ops require.

    Bounded to the current scene's rooms like `_crowds_view`, and for the
    same reason. The Director owns objective causality, so it may see where
    a rider is and where he is bound -- but NOT what he carries: the ops
    never need the claim text, and a payload field nothing needs is a leak
    waiting for a prompt to quote it.
    """
    from story import couriers as couriers_model
    from core.db import wget

    rooms = (scene or {}).get("rooms") or {}
    out = []
    for courier in couriers_model.live_couriers(
            wget(chat_id, couriers_model.COURIERS_WORLD_KEY, []) or []):
        at = str(courier.get("at") or "")
        if at not in rooms:
            continue
        route = [str(r) for r in courier.get("route") or []]
        leg = max(0, int(courier.get("leg") or 0))
        out.append({
            "courier_id": courier.get("uid"),
            "what": couriers_model.courier_voice(courier),
            "at": at,
            "heading": route[leg + 1] if leg + 1 < len(route) else None,
            "destination": str(courier.get("destination") or ""),
            "addressee": str(courier.get("addressee") or ""),
            "sealed": bool(courier.get("sealed")),
            "status": str(courier.get("status") or ""),
        })
    return out


def _artifacts_view(chat_id, scene):
    """Posted notices the resolve could act on, with the id ops require.

    Bounded to the current scene's rooms like `_couriers_view`. Unlike a
    courier's satchel, the CLAIM rides here on purpose: a posted bill is
    legible in place, and the Director cannot resolve a beat where somebody
    reads it -- or narrate its wording into the prose -- without knowing
    what it says. The minted `text`, when the ceiling has worded it, is
    what the prose may quote; the claim is what a reader acquires.
    """
    from story import artifacts as artifacts_model

    rooms = (scene or {}).get("rooms") or {}
    out = []
    for artifact in artifacts_model.standing_artifacts(chat_id):
        if artifact.get("status") != artifacts_model.POSTED:
            continue
        room = str(artifact.get("room") or "")
        if room not in rooms:
            continue
        held = artifact.get("report") or {}
        out.append({
            "artifact_id": artifact.get("uid"),
            "what": artifacts_model.artifact_voice(artifact),
            "room": room,
            "claim": str(held.get("claim") or ""),
            "text": str(artifact.get("text") or ""),
        })
    return out


def _carried_reports_view(ctx):
    """Who is carrying what, as {who, world_event_id, gist, retellings}.

    The gist is the holder's OWN degraded wording, not the objective event, so
    handing this to the Director tells it what a character could say rather
    than what is true. It is an index for writing `telling_ops`, not evidence:
    the Director already owns objective causality and this adds nothing it did
    not have -- while a character reading it would be reading other minds.

    Routed through `carriers.carried_reports_view` -- the SAME enumeration
    acquisition and telling run on -- rather than any walk of this module's
    own. The first version walked `ctx.cast` asking for `state`, a key that
    does not hold the carrier ledger, and the view came back empty while two
    reports sat in the database. The second walked `active_cast`/`cstate`,
    which holds the ledger for exactly the carriers `_carriers` does NOT
    stop at: the player (whose reports live in a world key, no cast row)
    and dormant cast were both invisible, so the one participant likeliest
    to send news could acquire a surface and never have it named in a
    `telling_ops`/`courier_ops` (docs/UNBUILT.md 1.31). Three spellings of
    one walk; this is the last, because it is not a spelling.
    """
    from story.carriers import carried_reports_view
    from story.scene import get_scene

    return carried_reports_view(
        ctx.chat.id, ctx.turn.frame_id,
        get_scene(ctx.chat.id, ctx.chat), chat=ctx.chat)
