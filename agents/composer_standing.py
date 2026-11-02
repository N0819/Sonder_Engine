"""The pack-independent half of Layer B: standing verdicts against the
observer's own ledger, what leads the beat, habituation and ceasing, beat
order, carried voices, and the observation rows projected from a rendered
view.

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import dataclasses

from agents.composer_common import _subject_prefix


#: The five verdicts a standing percept can carry for ONE observer.
#: `unchanged` -- this observer's own previous ledger holds this exact key.
#: `changed`   -- it holds this subject under different content.
#: `first`     -- it holds nothing about this subject at all.
#: `reearn`    -- first sight again: a body met before, being re-delivered.
#: `ceased`    -- a standing sound this observer was being delivered, and
#:               this beat there is none of it (D3).
STANDING_VERDICTS = ("unchanged", "changed", "first", "reearn", "ceased")


def standing_verdicts(percepts, prev_standing=frozenset(),
                      prev_described=frozenset()):
    """What each standing percept IS for this observer, as {dedupe_key: verdict}.

    THE DIFF OPERANDS ARE NOT TWO SCENES. They are this observer's admitted
    percepts for this beat and this observer's own ledger from the last one,
    and that is the whole firewall argument: a subject with no percept here
    produces no verdict and therefore no sentence, so a change in a room
    this mind cannot see is not withheld by a rule -- there is nothing for
    the rule to be about. A world diff is the shape that leaks; this is not
    one. The signature is Layer B's usual: percepts and mode state, no scene
    and no database, so the verdict cannot widen what the percepts already
    admitted.

    An EMPTY previous ledger means "no record", not "nothing was there" --
    the opening beat, a mind that just woke, a chat stored before the split
    key existed. Nothing can then read `changed`, because there is no
    subject to have been holding: the world arrives as background, never as
    a claim that any of it just moved. Old single-hash keys degrade the same
    way, by `_subject_prefix` answering None for them, so an upgraded chat
    costs one re-description per observer and never a false event.
    """
    prev_standing = frozenset(prev_standing or ())
    prev_described = frozenset(prev_described or ())
    subjects = {sp for sp in (_subject_prefix(k) for k in prev_standing) if sp}
    out = {}
    for p in percepts or []:
        if p.order_key is not None:
            continue
        if p.dedupe_key in prev_standing:
            out[p.dedupe_key] = "unchanged"
            continue
        prefix = _subject_prefix(p.dedupe_key)
        # A SILENCE IS ONLY NEWS TO AN EAR THAT HAD THE NOISE (D3). The
        # percept says a standing sound is gone; whether this observer was
        # ever delivered it is the ledger's question, and the answer is the
        # same subject test every other verdict here uses. No prior sound,
        # no `ceased` -- `first`, which `unheard_ceasing` drops rather than
        # rendering "it has stopped" about a noise nobody was told about.
        if (p.data or {}).get("ceased"):
            out[p.dedupe_key] = ("ceased" if prefix and prefix in subjects
                                 else "first")
            continue
        if prefix and prefix in subjects:
            out[p.dedupe_key] = "changed"
            continue
        if p.kind == "appearance" and (
                p.data.get("reearn")
                or str(p.data.get("source_key") or "") in prev_described):
            out[p.dedupe_key] = "reearn"
            continue
        out[p.dedupe_key] = "first"
    return out


#: Standing kinds whose arrival IS the beat. A body that was not there and
#: now is, and a sensation this body was not feeling and now feels, are both
#: events wearing a standing percept's shape; a room, a smell or an authored
#: description first perceived is the background arriving, not news.
_FIRST_SIGHT_LEADS = frozenset(("presence", "sensation"))


def appearance_delta(percept):
    """The transition prose an appearance percept carries, or "".

    A delta is not `force`. `force` says an objective visible-form channel
    was written this beat, which is a fact about the Director and answers
    nothing about this observer. A delta is the DIFFERENCE between two
    states of dress, computed where the previous scene exists and attached
    only to an observer who held that body at full sight last beat
    (`perception._composer_standing_percepts`). It is therefore evidence
    that something moved for this observer, and it outranks a dedupe key
    that did not move -- an authored summary that never mentions clothing
    hashes the same whatever the body is wearing.
    """
    return str((percept.data or {}).get("delta") or "").strip()


def asked_this_beat(percept):
    """Did this observer's own act ask for this standing percept this beat:
    a thing it looked at, or took into its hands (`thing_reading_percepts`).

    AN ACT THAT ASKS IS ANSWERED, unchanged or not. A reading is standing
    state, so a delta view said it once and dropped it as furniture after --
    right for a panel a body happens to stand beside, and the opposite of
    right for a slip it holds up to the window and reads line by line.
    Measured, Saltmarsh Crossing (2026-10-11, scratch chat 170): the slip's
    lines reached the player's view on idx 22, when she stood at the desk it
    lay on, and when she took it in her hands on idx 24 and read it, her
    view held nothing of it and the page answered nothing. Re-delivering it
    tells this mind only what it was already told, so the firewall is not
    in question; both renderers read this, and `leads_the_beat` puts it in
    the beat, where the act that asked is."""
    return bool((getattr(percept, "data", None) or {}).get("asked"))


def leads_the_beat(percept, verdict, prev_standing):
    """Does this standing percept belong in the BEAT half of a player view.

    `changed` always does -- something about a subject this observer already
    held is different now, which is the definition of the beat. `first` does
    only for the kinds above, and only against a ledger that exists: with no
    previous record every percept is a first sight, and a view that led with
    all of them would be claiming the whole world just happened.
    """
    if not prev_standing:
        return False
    if verdict in ("changed", "ceased") or asked_this_beat(percept):
        return True
    if percept.kind == "appearance" and appearance_delta(percept):
        return True
    # A STEADY SOUND THAT STARTS WHERE THE OBSERVER ALREADY STOOD is news
    # (DESIGN_SOUND_FIELD § 13): the room they were in has begun to sound.
    # One they walk into is the room as it is -- background, as before.
    if verdict == "first" and steady_sound(percept) \
            and not (percept.data or {}).get("ceased") \
            and _was_in_its_room(percept, prev_standing):
        return True
    return verdict == "first" and percept.kind in _FIRST_SIGHT_LEADS


#: THE STEADY SOUNDS A MIND GETS USED TO (DESIGN_SOUND_FIELD § 13, wave
#: B1): the room's soundscape -- where the noise is and what makes it -- and
#: a crowd's hum, standing hearing percepts keyed by the sound's own state,
#: so a sound that changes is a new key and a sound that stops is
#: `sound_ceased_percept`. Not a beat's own sounds (`ambient`, an event's
#: line) or a far one (`distant_sound`): those are news each time they
#: happen. Not a crowd's overheard fragment (`chatter`): its words change
#: under one key.
#: Since round 2 (§ 17) the WEATHER'S sound is one of them: what a body
#: hears of the sky from its room (`weather_sound_percepts`, the
#: precipitation and the wind as two sounds), told when it starts, faded
#: between, its stopping told once -- "the rain has stopped".
WEATHER_SOUND_TAG = "weather_sound"
WIND_SOUND_TAG = "wind_sound"
HABITUATING_SOUND_TAGS = ("soundscape", "hum", WEATHER_SOUND_TAG,
                          WIND_SOUND_TAG)


def steady_sound(percept) -> bool:
    """Is this a steady sound's standing percept (`HABITUATING_SOUND_TAGS`)?"""
    return (getattr(percept, "order_key", None) is None
            and getattr(percept, "kind", "") == "ambient"
            and getattr(percept, "channel", "") == "hearing"
            and str(getattr(percept, "dedupe_key", "") or "").split(":", 1)[0]
            in HABITUATING_SOUND_TAGS)


def view_verdicts(standing, prev_standing=frozenset(),
                  prev_described=frozenset(), *, player=False):
    """The verdicts a view renders by: every standing percept's on the player
    tier, as ever, and on the character tier a STEADY SOUND's
    (`steady_sound`) -- getting used to a sound, and noticing it stop, are
    facts about what THIS mind was hearing, whichever tier it is on. Shared
    by both renderers: which percepts a view carries is decided once."""
    if player:
        return standing_verdicts(standing, prev_standing, prev_described)
    return standing_verdicts([p for p in standing or () if steady_sound(p)],
                             prev_standing, prev_described)


def habituated(percept, verdict, *, full_render=False) -> bool:
    """GETTING USED TO A SOUND (DESIGN_SOUND_FIELD § 13). A steady sound this
    observer was already hearing, unchanged, fades from attention: it is
    told when it starts, when it changes and when it stops
    (`sound_ceased_percept`, once), and in between it is out of the view --
    on the character tier too, which otherwise re-tells everything every
    beat, so a generator a mind has stood beside for an hour was announced
    to it hourly. An explicit look (`full_render`) asks for the room back;
    a mind that walks in hears the room as it is (its ledger does not hold
    the sound, so the verdict is `first`)."""
    return (not full_render and verdict == "unchanged"
            and steady_sound(percept) and not asked_this_beat(percept))


def _was_in_its_room(percept, prev_standing) -> bool:
    """Was this observer in the room this percept's sound fills, last beat?
    The soundscape's subject is the room (`soundscape_percept`), and so is
    the room description's (`environment_percept`): the observer's own
    ledger holding the room's `env` subject is the answer."""
    subject = _subject_prefix(getattr(percept, "dedupe_key", ""))
    if not subject or not prev_standing:
        return False
    want = "env:" + subject.split(":", 1)[1]
    return any(_subject_prefix(key) == want for key in prev_standing)


def unheard_ceasing(percept, verdict):
    """Whether this percept claims a sound stopped that this observer was
    never delivered (D3) -- in which case it renders nothing at all.

    Both renderers ask, because the answer is an information decision and
    not a wording one. Two ways it is True. The observer's ledger holds no
    sound for this room, so `standing_verdicts` said `first` and there is no
    silence for them to notice; or nothing computed a verdict at all -- the
    character tier renders the full standing state every beat and has no
    ledger to diff against, and a room's own sound is not a thing that
    happens to a mind that was never following it.
    """
    return bool((getattr(percept, "data", None) or {}).get("ceased")) \
        and verdict != "ceased"


def as_beat(percept):
    """The same percept, marked as this beat's content rather than its
    background. Read by `observations_from_render`, which is how a changed
    pose reaches the narrator's numbered deliveries instead of its
    wallpaper. Frozen instances, so this is a copy -- the caller's own
    percept list is untouched, and `_composer_company` still reads it."""
    return dataclasses.replace(
        percept, data={**(percept.data or {}), "beat": True})


def player_view_order(spans):
    """The order a player view's spans render in, for ANY language pack.

    Four ranks, and the sort is stable, so each pack keeps its own discourse
    order inside a rank: this beat's EVENTS in declared order, then the
    standing percepts `leads_the_beat` marked as this beat's news, then a
    changed room, then the background. The room goes last in the beat half
    for the same reason `_render_episode_english` puts it last -- scene
    setting read first swallows what happened.

    A pack must not spell this rule itself. `language_adapters/japanese.py`
    did, and its own partition emitted the changed standing percepts BEFORE
    the events because that was the order it happened to iterate in, so a
    Japanese player view opened on a pose while the English one opened on the
    act that moved it. Rank is read off what the percept already carries --
    `order_key` for an event, the `beat` mark `as_beat` stamps for the rest --
    so there is nothing here for a second renderer to re-derive.
    """
    def rank(span):
        percept = span[0]
        if percept.order_key is not None:
            return 0
        if not (percept.data or {}).get("beat"):
            return 3
        return 2 if percept.kind == "environment" else 1
    return sorted(spans, key=rank)


VOICE_KEY_PREFIX = "voice:"


def carried_voices(prev_standing):
    """The voice keys an observer's previous view filed -- the one family of
    standing key that persists without being re-earned each beat."""
    return {str(k) for k in (prev_standing or ())
            if str(k).startswith(VOICE_KEY_PREFIX)}


# --------------------------------------------------------------------------
# Observations -- projected from the IR, never regex-classified from prose
# --------------------------------------------------------------------------

_FIDELITY_AMBIGUITY = {"full": 0.15, "degraded": 0.5, "fragment": 0.7,
                       "trace": 0.8,
                       # A voice whose words did not carry (§ 12 of the sound
                       # note): fewer of them than a fragment.
                       "voice": 0.75,
                       # A body moving, too little of it to make out: as
                       # ambiguous as a degraded presence, never "rendered"
                       # (it had no entry, and every motion-only act -- a
                       # body still crossing a shut door -- was filed into
                       # memory at the 0.15 of a full sighting).
                       "shapes": 0.5}

# What an observation says when it has nothing to say: the advisory axes'
# resting values, and the two identity fields that repeat what the payload
# structure already states. Measured over the stored corpus (1,692
# observations, turn id >= 1932): `intensity` sat at its 0.35 base in 99% of
# rows, `suddenness` at 0.1 in 99%, `fidelity` at "rendered" in 99%,
# `ambiguity` at 0.15 in 89%, `source_atom_id` read "current" in 100%, and
# `perceiver_id` matched the perceiver already named by `observation_id` in
# 100% -- six near-constant fields beside every percept, ~356 tokens of
# wrapper per payload against ~188 tokens of text. The axes are advisory
# context for the model's appraisal (docs/guides/PIPELINE.md: no deterministic code
# consumes the numbers), so a resting default carries no information and is
# OMITTED: absent means the default, the same convention the character
# payload uses everywhere else ("absent means cannot tell", never "none").
# The 1-11% of non-default values keep their full signal, and the ids and
# text -- the citation namespace `_ground_observation_citations` grounds
# against, and the content itself -- are never trimmed. Observations stored
# before this change carry the full shape and read identically.
#
# THAT MEASUREMENT IS OF A DERIVATION THAT NO LONGER RUNS, and one of the six
# rows no longer holds. It was taken against the prose-cue derivation
# `perception._observations_from_clean_views` (since deleted), which computed
# `0.35 + 0.2 * cue_hits` and therefore sat on the base whenever no cue
# matched. `observations_from_render` computes `0.35 + 0.4 * salience`, and
# the lowest salience any builder in this module assigns is 0.2
# (`environment_percept`), so intensity is >= 0.43 on every atom the composer
# can produce. The field the note above says is dropped 99% of the time is
# now dropped 0% of the time.
#
# The entry stays regardless, because `OBSERVATION_DEFAULTS` is also the
# EXPANSION table: rows stored under the old derivation omitted intensity,
# and removing the key would read those rows as having no intensity rather
# than the base. `suddenness`, `fidelity`, `ambiguity`, `source_atom_id` and
# `perceiver_id` still compact as measured.
OBSERVATION_DEFAULTS = {
    "source_atom_id": "current",
    "fidelity": "rendered",
    "intensity": 0.35,
    "suddenness": 0.1,
    "ambiguity": 0.15,
    "directed_at_self": False,
}


def compact_observation(obs):
    """Drop wrapper fields holding their resting default (OBSERVATION_DEFAULTS
    above); `perceiver_id` is dropped when it repeats the perceiver already
    named by `observation_id`. `observation_id`, `observed` and `channel`
    always survive."""
    if not isinstance(obs, dict):
        return obs
    oid = str(obs.get("observation_id") or "")
    out = {}
    for key, value in obs.items():
        if key == "perceiver_id" and oid.startswith(f"current:{value}:"):
            continue
        default = OBSERVATION_DEFAULTS.get(key)
        if default is not None:
            if isinstance(default, float):
                try:
                    if abs(float(value) - default) < 1e-9:
                        continue
                except (TypeError, ValueError):
                    pass
            elif value == default or value is default:
                continue
        out[key] = value
    return out


def observations_from_render(pid, rendered):
    """Project each admitted rendered span into its own evidence row.

    A delivery boundary is part of the evidence: merging two actions can
    attach the second actor's conduct to the first, and merging quotes makes
    a narrator read two deliveries as one. There is no row-count cap here.
    Each sentence remains byte-for-byte within the observer's rendered view.
    """
    pid = str(pid)
    out = []
    for index, (percept, sentence) in enumerate(rendered.spans):
        ambiguity = _FIDELITY_AMBIGUITY.get(percept.fidelity, 0.15)
        phase = ("event" if percept.order_key is not None else
                 "change" if percept.data.get("force") or
                 percept.data.get("beat") else "state")
        # A presence sentence can enumerate several bodies. Its first
        # percept is a rendering representative, not the actor of the group.
        actor = percept.source_label if percept.kind != "presence" else ""
        out.append(compact_observation({
            "observation_id": f"current:{pid}:{index}",
            "perceiver_id": pid,
            "source_atom_id": "current",
            "channel": percept.channel,
            "fidelity": "ambiguous" if ambiguity >= 0.5 else "rendered",
            "observed": {"text": sentence},
            **({"actor": actor} if actor else {}),
            "kind": percept.kind,
            "phase": phase,
            **({"order": percept.order_key}
               if percept.order_key is not None else {}),
            "intensity": min(1.0, 0.35 + 0.4 * percept.salience),
            "suddenness": percept.suddenness,
            "ambiguity": ambiguity,
            "directed_at_self": bool(
                percept.data.get("directed_at_self")
                or percept.channel == "interoception"),
            # Retained for archived consumers and the memory boundary.
            "standing": phase == "state",
        }))
    return out


def perception_packet(observations, *, fallback_view=None):
    """Partition already admitted evidence for a character or narrator.

    No scene, identity lookup, prose classifier or model participates here.
    Witnessed events retain delivery order. A noticed change has no inferred
    occurrence time. Standing rows for the same labelled subject are adjacent;
    their exact wording, fidelity and citation ids are preserved.

    Archived observations lacking a phase retain the old standing verdict.
    A string-only archived view remains unstructured context; we cannot
    recover individual events or their times by reading its prose.
    """
    packet = {"events": [], "changes_noticed": [], "current_state": []}
    sections = {"event": "events", "change": "changes_noticed",
                "state": "current_state", "context": "unstructured_context"}
    for observation in observations or ():
        if not isinstance(observation, dict):
            continue
        observed = observation.get("observed")
        if not isinstance(observed, dict) or not str(observed.get("text") or "").strip():
            continue
        if (fallback_view is not None
                and str(observed["text"]).strip() not in str(fallback_view or "")):
            # Some archived observations precede the final view repair.
            # They may not restore wording that the admitted view removed.
            continue
        phase = observation.get("phase")
        row = dict(observation)
        if phase not in sections:
            phase = "state" if observation.get("standing") else "event"
            # Older repairs scrubbed the delivered text without repairing
            # actor metadata. That label cannot newly identify a safe voice
            # on archive replay. Keep the admitted wording; modern rows have
            # an explicit phase and pass the shared actor identity repair.
            row.pop("actor", None)
        packet.setdefault(sections[phase], []).append(row)
    # Source order keys are local to an onset or micro-round. The model
    # sees one accumulated delivery stream, so its ordinal must not restart
    # each time a different speaker takes a turn. Stored rows stay intact.
    for order, event in enumerate(packet["events"], 1):
        event["order"] = order
    # Older views can contain safe sentences whose merged observation was
    # removed by a later identity repair. Preserve any uncovered wording,
    # but never infer events from it. Consume each exact span once so two
    # identical delivered lines still require two matching rows.
    remaining = [str(fallback_view or "")]
    for rows in packet.values():
        for row in rows:
            text = str(row["observed"]["text"])
            for index, fragment in enumerate(remaining):
                at = fragment.find(text)
                if at >= 0:
                    remaining[index:index + 1] = [fragment[:at], fragment[at + len(text):]]
                    break
    context = "\n".join(fragment.strip() for fragment in remaining if fragment.strip())
    if context:
        packet.setdefault("unstructured_context", []).append(
            {"channel": "mixed", "phase": "context", "observed": {"text": context}})
    groups = {}
    for index, row in enumerate(packet["current_state"]):
        actor = str(row.get("actor") or "").strip()
        key = ("actor", actor) if actor else ("unattributed", index)
        groups.setdefault(key, []).append(row)
    packet["current_state"] = [row for group in groups.values() for row in group]
    return packet
