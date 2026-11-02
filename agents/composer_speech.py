"""A line as one observer receives it: concealment, addressee, the hearing gate
with its rescues, voice/tone/register, own-name catch, silence and described
communication.

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import dataclasses
import re
from core.pipeline_context import note_step_decision
from language_runtime import linguistic
from world.spatial import (
    hear_level,
    spoken_to,
    hearing_reason,
    voice_carries,
    into_another_ear,
    sense_acuity_offset,
)
from .common import (
    self_name_forms,
    _identity_token_set,
    _muffle_tokens,
    _muffled_fragment,
    _quote_body,
)

from agents.composer_common import (
    Percept,
    _ENGLISH_COMPOSITOR,
    _lower_lead,
    _pack_words,
    _sense_graded,
    _short_hash,
    _strip_sentence_ends,
    body_key,
    standing_key,
)


# --------------------------------------------------------------------------
# Layer A -- shared admission helpers
# --------------------------------------------------------------------------

def concealed_from_observer(entry, observer_name, observer_id=None):
    """Is this concealed event element withheld from this observer?

    An empty conceal_from means hidden from every non-actor; a populated list
    is an explicit excluded audience. This is now the only reading of that
    rule: the second copy lived on the retired onset/outcome prose paths and
    went with them."""
    if entry.get("visibility") != "concealed":
        return False
    refs = {
        str(value).strip().casefold()
        for value in (entry.get("conceal_from") or [])
        if str(value or "").strip()
    }
    if not refs:
        return True
    return bool(
        "*" in refs
        or str(observer_name or "").casefold() in refs
        or str(observer_id or "").casefold() in refs
        or f"character:{observer_id}".casefold() in refs
    )


def _line_refs(entry):
    """Every handle a line names its addressee by: its `intended_target`
    (one, or a list) and its `targets`."""
    refs = entry.get("intended_target")
    refs = list(refs) if isinstance(refs, (list, tuple)) else [refs]
    refs.extend(entry.get("targets") or [])
    return [str(ref).strip() for ref in refs
            if ref is not None and not isinstance(ref, bool)
            and str(ref).strip()]


def line_addressed(entry, observer_name, observer_id=None):
    """Is this observer the body a line is spoken TO -- its
    `intended_target`, or one of its `targets` -- by name, or by the
    engine's own handle for them (`character:<id>`)? Typed data only, like
    every admission here; a caller that resolves identity against the scene
    (aliases, entity ids) passes its own answer as `addressed`.

    What the ear rung is decided by (`spatial_senses.EAR_VOLUME`), and it
    fails toward no: a line breathed into an ear goes to nobody this cannot
    show is that ear's owner.

    Three answers, not two (`spatial_senses.spoken_to`): None where the line
    names NOBODY -- its addressee field absent or left empty -- which is
    unknown, never "spoken to somebody else": no bystander rule caps it,
    and the ear rung still refuses it."""
    forms = {str(observer_name or "").strip().casefold()}
    if observer_id is not None and str(observer_id).strip():
        forms |= {str(observer_id).strip().casefold(),
                  f"character:{str(observer_id).strip()}".casefold()}
    forms.discard("")
    refs = _line_refs(entry)
    return spoken_to(any(ref.casefold() in forms for ref in refs), bool(refs))


def line_hear_level(entry, rel, observer_name, proximity=None,
                    senses=None, seen=False, *, addressed=None):
    """Audibility of one dialogue entry to an observer.

    A LINE BREATHED INTO ANOTHER BODY'S EAR decides first, and it decides
    `none` (`spatial_senses.into_another_ear`): no path carries the ear
    rung to anybody but its addressee -- not the air, not the live channel
    below, not the rescue of a line named across a barrier. `addressed` is
    whether this observer is the line's addressee; None reads the line's
    own targets (`line_addressed`).

    Ordinary spatial hearing (`hear_level`) decides next -- including the
    `proximity` downgrade. Pass only a MEASURED tier
    (`spatial.measured_proximity_rel`): "near" is mostly a default, and a
    default must not silence a conversation.

    Hearing only ever gets OVERRIDDEN in one direction -- a line it would
    DROP is rescued to 'full' when the line is a TRANSMISSION addressed to
    THIS observer (explicit medium:'comm', or a by-name spoken-volume
    exchange across a barrier). An enclosure is never shape-rescued: being
    named by a voice beyond the mass around you creates no channel through
    it. The comm path carries only the VOICE; the caller sets can_see
    separately.

    `seen`: the observer sees the speaker's face, which is worth several
    decibels where noise is what decides (`hear_level`).

    WHO THE LINE WAS SPOKEN TO is the hearing rule's question too: in a din
    a bystander beyond conversational reach catches pieces of a far table's
    talk, and the one it was said to follows it. A line that names nobody
    -- no addressee field, or one left empty, as 31% of recorded lines are
    -- is unknown (None): the ear rung refuses it to everyone, the din caps
    nothing (`spatial_senses.spoken_to`)."""
    if addressed is None and isinstance(entry, dict):
        addressed = line_addressed(entry, observer_name)
    if into_another_ear(entry.get("volume", "normal"), addressed,
                        entry.get("level_db")):
        return "none"
    # A live channel between speaker and observer -- a PA, an intercom, a
    # radio, a phone -- decides FIRST, before the wall gets a say.
    #
    # It was ordered after the spatial read and that was wrong in a way only
    # play could show: an interview room whose two-way mirror the Director
    # encoded as `membrane` muffles an ordinary voice to a `fragment`, and a
    # fragment is not "none", so the early return took it and the live PA
    # standing between those two rooms was never consulted. The scene had the
    # equipment, the equipment was switched on, and the reader got a muffled
    # voice through the glass.
    #
    # The rule the ordering encodes: a speaker reproduces the voice, so what
    # the wall would have done to it does not matter. Muffling is a property
    # of the path the channel replaces. A channel only ever RAISES what
    # arrives, and where none applies this falls through to the ordinary
    # spatial read unchanged.
    #
    # Read off the RELATION, never out of the scene: this module decides
    # admission on typed data alone, and a rendering path that could consult
    # the world could add to it. It rescues regardless of who the line NAMES,
    # which is the whole difference between a channel and the addressed rescue
    # below -- a voice on a speaker is heard by whoever is in front of the
    # speaker. `spatial.comms_link` has already decided direction, liveness,
    # and who is on the channel.
    if isinstance(rel.get("comm_channel"), dict):
        return "full"
    _unimpaired = hear_level(rel, entry.get("volume", "normal"),
                             proximity=proximity,
                             level_db=entry.get("level_db"), seen=seen,
                             addressed=addressed)
    base = _sense_graded(_unimpaired, "hearing", senses)
    # AN IMPAIRED EAR IS NOT AN UNREACHABLE ONE. `full` is the top of the
    # hearing ladder, so a -1 acuity took every `full` to `fragment`
    # unconditionally: a hard-of-hearing body never made out a sentence
    # again, at any volume, at any distance, including one shouted into it
    # at arm's length -- and no speaker could do anything about it, which is
    # what makes it a defect rather than a disability. Measured (rush, PR5).
    #
    # So the shift yields where the world is already compensating for it, on
    # the two terms the world has: a MEASURED intimacy, or a raised voice.
    # Exactly the exception design note 18 makes for dim sight, and for the
    # same reason -- a grade is a description of the channel, and a channel
    # at its own ceiling is not describing an impairment any more. Every
    # other level still shifts, so the card is not being ignored.
    # ...but ONLY where the card is a shift. An ABSENT channel is a cut, not
    # a degree (`sense_acuity_offset` answers None for it), and no volume and
    # no distance compensates for an ear that is not there. Caught by this
    # function's own test on the first run, which is the whole argument for
    # writing the complement down.
    if base != "full" and _unimpaired == "full" \
            and sense_acuity_offset(senses, "hearing") is not None and (
            str(proximity or "") == "within_reach"
            or str(entry.get("volume", "normal")).lower() in ("loud", "shout")):
        base = "full"
    if base != "none":
        return base
    if not _addresses(entry.get("intended_target"), observer_name):
        return base
    if str(entry.get("medium") or "").lower() == "comm":
        return "full"
    if rel.get("enclosed_from_source") or rel.get("source_enclosed"):
        return base
    # ATTENTION DOES NOT BEAT AIR THAT IS WORKING. The shape floor exists
    # because a Director often omits `medium`, and a by-name line to a party
    # OUT OF EARSHOT is then still a transmission -- a combadge hail from a
    # planet surface, which nothing but a device could carry. That case is
    # earned and stays. What was never evidence for it is a party in the same
    # BUILDING: two independent runs measured the difference -- a shout three
    # rooms up a stone tower delivered verbatim on four beats (lighthouse,
    # PA4), and a line from two closed doors and a room away delivered
    # complete in a view whose two UNADDRESSED voices were correctly
    # fragments (the Cold Season Ball, PX6). Sound reached both places; being
    # named is not a second, better path through the same doors.
    #
    # The two are told apart by whether the AIR HAS AN ANSWER for this pair.
    # `stamp_sound_relation` stamps `air` where the two rooms are one,
    # neighbours, or joined by any chain of edges; a pair with no acoustic
    # relationship at all -- another world, a ship in orbit -- carries none.
    # Where the air has an answer, it is the answer. Where it has none, a
    # line that arrives by name arrives by a device.
    #
    # A scene with no geometry stamps nothing and is unchanged, which is the
    # same fail-open direction this rescue has always had.
    if rel.get("air"):
        return base
    if str(entry.get("volume", "normal")).lower() in ("normal", "loud", "shout"):
        # ...and it is not the one grade a sense card cannot dull. It ran
        # after `_sense_graded` and returned a bare "full", so one view could
        # carry a fragmented sentence into a poor ear at arm's reach beside a
        # verbatim shout from two rooms below (rush, PR5).
        return _sense_graded("full", "hearing", senses)
    return base


def _addresses(intended_target, observer_name):
    """True when a dialogue line's intended_target names this observer. The
    target may be a single name or a list; comparison is casefolded. Used to
    route a comm-channel transmission to the party it was addressed to, across
    a physical barrier (see the medium:'comm' handling in perception_outcome).

    One definition. `perception.py` carried a byte-identical twin that no
    production path called and one test imported, so the tested copy and the
    running copy were different objects free to drift apart.
    """
    if not intended_target or not observer_name:
        return False
    targets = intended_target if isinstance(intended_target, (list, tuple)) \
        else [intended_target]
    on = str(observer_name).casefold()
    return any(str(t).casefold() == on for t in targets)


# --------------------------------------------------------------------------
# Layer A -- event percepts
# --------------------------------------------------------------------------

#: How much one comma-separated part of a manner may hold and still sit inside
#: the manner slot ("in a {tone} voice", 「{tone}を声ににじませ」): an
#: adjective with its adverb and a conjunction ("and highly articulate") --
#: three words in a spaced script, ten characters in an unspaced one -- never
#: a clause.
_MANNER_PART_WORDS = 3
_MANNER_PART_CHARS_UNSPACED = 10


def _fits_the_manner_slot(manner):
    from story.character_schema import _UNSPACED_SCRIPT
    for part in re.split(r"[,、，;；]", str(manner or "")):
        part = part.strip()
        if not part:
            continue
        if " " not in part and _UNSPACED_SCRIPT.search(part):
            if len(part) > _MANNER_PART_CHARS_UNSPACED:
                return False
        elif len(part.split()) > _MANNER_PART_WORDS:
            return False
    return True


def _voice_fields(register, tone, established, can_say=True):
    """The manner a line renders, and what is said of the voice apart from it.

    A VOICE THAT IS A CLAUSE IS ITS OWN SENTENCE. The slot is "in a {tone}
    voice", and a sheet's register -- or a line's own tone -- can be a
    clause: "says in a bright, informal, theatrical, and highly articulate,
    shifting into grave authority without warning voice" (Kirinoura, scratch
    chat 167, 2026-10-05). A register that does not fit
    (`_fits_the_manner_slot`) is `said_apart`, after the line, whole, by
    every pack's `voice_register`."""
    first = bool(register and not established)
    out = {"manner": register if first else tone}
    if first:
        out["voice_first"] = True
        # A REGISTER describes a voice, always; a line's own tone stays in
        # its slot, as it always has -- classifying tones as conduct or voice
        # in two scripts cost more than the one sentence it fixed (review
        # rounds 1-3, 2026-10-05).
        # Said apart only where the slot itself would say it -- a line SEEN
        # and not conducted (`_inject_dialogue` drops the manner otherwise):
        # an unseen line carried no register, and a long one said apart
        # reached a listener in the dark (review round 4, 2026-10-05).
        if not _fits_the_manner_slot(register) and can_say:
            out["said_apart"] = _lower_lead(_strip_sentence_ends(register))
            out["manner"] = ""
    return out


def _can_say_the_voice(p):
    """Whether this line's render says the voice: a full line, said apart
    after it, or in the manner slot of a line seen and not conducted. A
    fragment, an unseen line and a conducted one carry no manner -- a voice
    established on one of them was never said and filed as known all the
    same (review, 2026-10-05). A stranger's voice heard and not seen is
    said after whatever of it arrived (`voice_apart`, § 12 of the sound
    note), so that says it too."""
    d = p.data or {}
    if d.get("voice_apart") and p.fidelity in ("full", "fragment", "voice"):
        return True
    if p.fidelity != "full":
        return False
    if d.get("said_apart"):
        return True
    return bool(d.get("can_see")) and not d.get("conducted")


def _one_voice_each(percepts):
    """`percepts` with each voice established once, in their own order: the
    earliest line a speaker says among them establishes it, and every later
    line from them renders only its own tone. `speech_percept` asks the
    ledger of earlier BEATS, so three lines in one beat each said the voice
    again."""
    percepts = list(percepts or ())
    first = {}
    for i, p in enumerate(percepts):
        d = p.data or {}
        if p.kind == "speech" and d.get("voice_first") and d.get("voice_key") \
                and _can_say_the_voice(p):
            rank = (p.order_key is None, p.order_key or 0, i)
            if d["voice_key"] not in first or rank < first[d["voice_key"]][0]:
                first[d["voice_key"]] = (rank, i)
    keep = {i for _rank, i in first.values()}
    out = []
    for i, p in enumerate(percepts):
        d = p.data or {}
        if p.kind == "speech" and d.get("voice_first") and d.get("voice_key") \
                and d["voice_key"] in first and i not in keep:
            data = {k: v for k, v in d.items()
                    if k not in ("voice_first", "said_apart", "manner",
                                 "voice_apart")}
            data.update(_voice_fields("", data.get("tone", ""), True))
            p = dataclasses.replace(p, data=data)
        out.append(p)
    return out


def speech_percept(entry, rel, observer_name, *, display, can_see,
                   proximity=None, order_key=0, observer_id=None,
                   senses=None, voice="", prev_standing=None, bearing="",
                   addressed=None, name_forms=(), voice_sound=""):
    """Admit one spoken line for one observer, or None.

    A VOICE IS ESTABLISHED ONCE (D2; Wood -- theatre gives a vocal quality
    once). `voice` is the speaker's own register from their sheet
    (`social.voice.register`). The FIRST line this observer hears from that
    body renders the register as its manner and files a `voice:<body>` key
    in the observer's standing ledger; every later line renders a manner
    only where the line's own `tone` names a departure. The declared `tone`
    stays in `data["tone"]` regardless -- what renders is `data["manner"]`.
    `voice_sound` is the card's `embodiment.voice` -- what the voice carries
    to a stranger's ear -- said once, after the line, to a listener who
    hears the body and cannot see it (`voice_apart`), ahead of the register
    (DESIGN_SOUND_FIELD § 18); a seen speaker keeps the register's slot.
    Measured before this: "in a flat, hushed monotone voice, she said" on
    63-98 of 79 lines in one story and 6 of 7 on the descent copy, because a
    speaker's ordinary voice was re-declared as tone on every line and the
    view had no notion of a voice already known. Tone strings are never
    compared: the ledger decides, not the wording.

    Gates, in order: concealment (absolute exclusion, never a volume),
    audibility (`line_hear_level`, including the comm/addressed rescue, and
    the ear rung, which reaches only the line's addressee: `addressed`, or
    the line's own targets when None -- `line_addressed`).
    The data carries the FIDELITY-DEGRADED surface: a fragment percept holds
    only the muffled fragment the renderer may emit, never the full body --
    so downstream consumers (memory included) structurally cannot outrun the
    view."""
    if concealed_from_observer(entry, observer_name, observer_id):
        return None
    body = _quote_body(entry.get("exact_quote") or entry.get("text"))
    if not body:
        return None
    volume = str(entry.get("volume") or "normal")
    # WHICH RELATION DECIDED, AND WHY. `act_percept` records every refusal
    # and delivery; this function recorded nothing, and the cost was
    # measured: a shout three rooms up a stone tower arrived verbatim on four
    # beats while every deterministic reader replayed on the committed scene
    # answered `fragment` or `none`, and nothing persisted which of the two
    # rescues had fired (lighthouse, 2026-09-05, PA4 -- docs/UNBUILT.md
    # § 1.121). Two paths can promote an unheard line to a full verbatim
    # quotation and they have different premises, so an attribution has to
    # say which one. Same shape as `act_percept`: no-op when debug capture is
    # off, one ContextVar read.
    _who = "%s -> %s" % (str(entry.get("speaker") or "?"), observer_name)
    if addressed is None:
        addressed = line_addressed(entry, observer_name, observer_id)
    _spatial = line_hear_level(entry, rel, observer_name, proximity=proximity,
                               senses=senses, seen=bool(can_see),
                               addressed=addressed)
    level = _spatial
    _how = "spatial"
    if isinstance(rel.get("comm_channel"), dict) and level != "none":
        _how = "comm channel"
    elif level == "full" and _sense_graded(
            hear_level(rel, volume, proximity=proximity,
                       level_db=entry.get("level_db"), seen=bool(can_see),
                       addressed=addressed),
            "hearing", senses) == "none":
        # `line_hear_level` already applied the addressed rescue; naming it
        # here is a report of what happened inside it, not a second copy of
        # the rule.
        _how = "addressed rescue (named across a barrier)"
    if level == "none" and rel.get("open_group_continuity") \
            and volume.casefold() in ("normal", "loud", "shout"):
        # Compatibility floor for a rerolled checkpoint predating the
        # near-group position repair. It grants hearing only; sight and every
        # other channel still ride the relation's real spatial fields. (The
        # onset prose path carried the twin of this rescue and has since been
        # deleted, so this is the only copy.)
        level = "full"
        _how = "open-group continuity floor (pre-repair checkpoint)"
    # WHY, in the hearing rule's own words, where a line is short of whole
    # (`spatial_senses.hearing_reason`): appended, so a reader of the older
    # notes -- `tools/speech_replay.py` parses the prefix -- reads them alike.
    _why = hearing_reason(rel, volume, proximity=proximity,
                          level_db=entry.get("level_db"),
                          seen=bool(can_see),
                          addressed=addressed) if level != "full" else ""
    if _why == "into_another_ear" and not _line_refs(entry):
        # A line breathed into an ear that names NO ear reaches nobody at
        # all -- its own listener included -- and says so here, so the
        # missing target is found where the line went missing.
        _why = "ear_names_no_one"
    # THE VOICE, WHERE NONE OF ITS WORDS ARRIVE (DESIGN_SOUND_FIELD § 12).
    # A listener hears THAT someone spoke, how loudly and in what tone some
    # ten decibels under the last word they could have caught: raised
    # voices through a wall, a laugh through a door, a far table's talk in a
    # tavern's din (`spatial_senses.voice_carries`). Words and names are not
    # carried by it: the percept holds no body and no fragment, and its
    # label is a name only where the listener knows the voice.
    _voice_only = (level == "none"
                   and sense_acuity_offset(senses, "hearing") is not None
                   and voice_carries(rel, volume, proximity=proximity,
                                     level_db=entry.get("level_db"),
                                     seen=bool(can_see),
                                     addressed=addressed))
    note_step_decision(
        "speech_percept", _who,
        "refused" if level == "none" and not _voice_only else "delivered",
        "%s via %s; volume %s, barrier %s, tier %s%s" % (
            "voice" if _voice_only else level, _how, volume,
            str(rel.get("barrier") or "none"),
            str(proximity or rel.get("tier") or "unmeasured"),
            ("; " + _why) if _why else ""))
    if level == "trace":
        # DETECTED, AND NOTHING MORE (`spatial_senses.HEARING_LEVELS`): the
        # rung a sense card reaches from `none` or falls to from `fragment`
        # carries no words and no identity. It fell through to the full
        # branch below, so an extraordinary ear behind a wall was handed the
        # line verbatim under "the unfamiliar person" -- the wiretap the
        # rung exists to refuse.
        return _trace_percept(entry, bearing=bearing, order_key=order_key)
    if level == "none" and not _voice_only:
        # SEEN SPEAKING, UNHEARD. A line the noise takes whole is still an
        # act the eyes have: a body within reach turns its head to yours
        # and its mouth moves. Refusing the WORDS is the firewall doing its
        # job; refusing that anything was said at all is a wrong scene.
        # Measured (scratch play 2026-09-14, chat 2 turns 2-3): on a deck
        # a "loud" engine graded drowned, a woman sat against a man's
        # sleeve and spoke at his ear, twice, and his view carried nothing
        # -- so his mind answered as if she had never spoken, and the
        # narrator wrote "He gave no reply". Delivered as the fragment
        # percept with the pack's indistinct marker and no words, so
        # `_scrub_invented_dialogue` has nothing to check and nothing can
        # leak: what reaches the observer is only that speech happened.
        if can_see and str(proximity or rel.get("tier") or "") in (
                "within_reach", "near"):
            note_step_decision(
                "speech_percept", _who, "delivered",
                "seen speaking, unheard: the words did not carry but the "
                "speaker is in sight within reach")
            return Percept(
                kind="speech", channel="sight", source_label=display,
                fidelity="fragment",
                data={"level": "none", "volume": volume, "can_see": True,
                      "attributed": bool(str(display or "").strip()),
                      "fragment": _muffled_fragment(""),
                      "tone": "", "manner": "",
                      # No word arrived, so neither did whom the line was
                      # for (`_said_to_you`).
                      "directed_at_self": False},
                salience=0.5, order_key=order_key)
        return None
    channel = rel.get("comm_channel")
    tone = str(entry.get("tone") or "").strip()
    affect = typed_affect(entry)
    # A register is AUTHORED sheet text and arrives as a sentence ("Clinical,
    # deadpan, and strictly monotone.") where a tone is a phrase; splice it
    # as the manner slot expects, or the page reads "in a Clinical, deadpan,
    # and strictly monotone voice" (descent copy, beat 119).
    register = _lower_lead(_strip_sentence_ends(voice))
    # The voice's SOUND (`embodiment.voice`), said whole after a line heard
    # unseen -- never spliced into the manner slot, which is the register's.
    sound = _lower_lead(_strip_sentence_ends(voice_sound))
    # Keyed on the sheet's OWN text, not the spliced rendering: the key names
    # the voice, and a change to how the manner is worded must not make a
    # known voice new again (measured: one renderer change between two
    # beats re-established Sarah's voice on the descent copy, beat 120).
    # The sound is part of the key only where a card has one, so a card
    # without it keys exactly as it did before the field existed.
    voice_key = standing_key(
        "voice", (body_key(str(entry.get("speaker") or "")),),
        (str(voice or "").strip(),)
        + ((str(voice_sound or "").strip(),) if sound else ())) \
        if register or sound else ""
    established = bool(voice_key) and voice_key in (prev_standing or ())
    data = {
        "level": level,
        "volume": volume,
        "can_see": bool(can_see),
        "conducted": bool(rel.get("inside_source")),
        "tone": tone,
        **_voice_fields(register, tone, established,
                        can_say=bool(can_see) and not rel.get("inside_source")),
        **({"voice_key": voice_key} if voice_key else {}),
        "articulation": str(entry.get("articulation") or ""),
        "directed_at_self": _addresses(
            entry.get("intended_target"), observer_name),
    }
    _speaker = str(entry.get("speaker") or "").strip()
    _label = str(display or "").strip()
    _knows_the_voice = bool(
        _speaker and _label.casefold() == _speaker.casefold())
    # A STRANGER'S VOICE IS DESCRIBED BY WHAT A VOICE CARRIES (§ 12): a
    # listener who cannot see the speaker and does not know the voice is
    # given the card's own account of the voice's sound (`embodiment.voice`,
    # § 18: what a body is recognised by when it speaks unseen) and, where
    # the card has none, the speaker's register -- "low contralto, warm and
    # unhurried" -- said once after the line, as a seen line says it in its
    # manner slot; never a name (`_voice_sound_heard_unseen`,
    # `_register_heard_unseen`). Over a live channel too, and through a
    # body's mass the voice is the mass's, so not there.
    _unseen_register = _voice_sound_heard_unseen(sound, _speaker) \
        or _register_heard_unseen(register, _speaker)
    if voice_key and not established and not can_see \
            and not _knows_the_voice and not rel.get("inside_source") \
            and _unseen_register:
        data["voice_apart"] = _unseen_register
    if level == "none":
        # The voice only: whose it is where it is known or seen, how loud
        # (`volume`), the feeling it carries (`_voice_feeling`) -- no words.
        data["level"] = "voice"
        data["attributed"] = bool(_label) and (bool(can_see)
                                               or _knows_the_voice)
        data.update(_voice_feeling(affect, tone, body))
        data.pop("manner", None)
        fidelity = "voice"
    elif level == "fragment":
        data["fragment"] = _muffled_fragment(body)
        data.update(_voice_feeling(affect, tone, body))
        # WHO SPOKE IS SIGHT'S ANSWER, NOT HEARING'S. A line degraded by
        # distance or noise loses its WORDS, never its speaker, when the
        # observer can see who spoke: hearing less of a sentence is not the
        # same as not knowing who said it, and the two are separate channels.
        # Live (PD3), turn 20: Sable's view rendered her own employer, three
        # paces in front of her in daylight and described in full by the same
        # view, as "A muffled voice: ...milestone... ferryman... business...".
        # A percept whose source is stripped does not stay stripped -- the
        # mind fills it, the narrator sited it at a gatehouse, and the
        # invention was filed as memory. Anonymity is for a speaker the
        # observer cannot place.
        # A VOICE YOU KNOW IDENTIFIES ITS OWNER, SEEN OR NOT. This gated
        # attribution on SIGHT, so a line from a body standing behind you --
        # or across a dark room, or through a door -- arrived anonymous
        # however well you know them, which is not how ears work. Recognition
        # is the question, and `display` already answers it: this label comes
        # from `observer_display_map`, which returns a recognised body's OWN
        # NAME and a stranger a descriptor, and which applies
        # `disguise_breaks_recognition` on the way -- so a disguise that means
        # to conceal who someone is takes their voice with it, and one that
        # only hides features does not.
        #
        # RESIDUAL, registered rather than invented: a voice-only disguise --
        # ordinary appearance, deliberately altered voice -- has no field to
        # be authored in. It is a real thing a body does and the engine
        # cannot yet say it.
        data["attributed"] = bool(_label) and (bool(can_see)
                                               or _knows_the_voice)
        fidelity = "fragment"
    else:
        data["body"] = body
        fidelity = "full"
    # YOUR OWN NAME CATCHES YOUR EAR (DESIGN_SOUND_FIELD § 13, wave B1). One's
    # own name is detected at lower signal levels than other words, and out
    # of a din or a conversation one is not following -- the cocktail-party
    # effect (Moray 1959; Wood & Cowan 1995). So where this listener has
    # only pieces of a line, or its voice without words, and the line holds
    # a name others call them by (`name_forms`, `own_name_forms`), they know
    # their name was said: the percept carries THAT, never which form of
    # it, never another word of the line, never who. A line whose voice
    # did not reach them at all carries no name either.
    if fidelity in ("fragment", "voice") and name_forms \
            and own_name_said(body, name_forms):
        data["own_name"] = True
    data["directed_at_self"] = _said_to_you(
        fidelity, data["directed_at_self"], data.get("own_name"))
    # WHICH channel carried it, when one did. Not decoration: a voice arriving
    # over a speaker is a different fact from a voice arriving from a body in
    # the room, and a mind handed the second when the first is true has been
    # told the speaker is present. The renderer says so and the observation
    # carries it, so nothing downstream can quietly lose the distinction.
    if isinstance(channel, dict) and not rel.get("same_room"):
        data["via"] = str(channel.get("name") or channel.get("id") or "")
        data["via_channel"] = str(channel.get("id") or "")
    # WHERE AN UNSEEN VOICE CAME FROM, in the listener's own frame (the
    # caller's `sound_bearing` phrase, which names no room and no body). The
    # same fact a route is: a voice through the doorway on your right and a
    # voice in the room with you are different things, and a view that drops
    # it has told the reader the speaker is standing here. Found in play on
    # 2026-10-06 (scratch story 165, turn 4581): the market's reeve answered a
    # shout through the inn's door, the view said only "You hear a voice
    # say", and the narrator put him "on the far side of the room" -- where
    # the player turned to question nobody.
    if bearing and "via" not in data:
        data["bearing"] = str(bearing)
    return Percept(
        kind="speech", channel="hearing", source_label=display,
        fidelity=fidelity, data=data,
        salience=(0.75 if volume in ("loud", "shout") else 0.7)
        if fidelity != "voice" else 0.5,
        suddenness=0.5 if volume in ("loud", "shout") else 0.1,
        order_key=order_key,
        # ONE VOICE, ONE SENTENCE: a speaker whose words did not carry is
        # heard as a voice once a beat, however many lines they said.
        dedupe_key=("speech-voice:" + _short_hash(entry.get("speaker"))
                    if fidelity == "voice"
                    else "speech:" + _short_hash(entry.get("speaker"), body)),
    )


def _said_to_you(fidelity, addressed_to_you, own_name=False):
    """Whether a heard line's evidence row may say it concerned the listener.

    THE PAGE DECIDES, NOT THE LINE'S ADDRESSEE. `observations_from_render`
    copies this flag into the row the character payload and the narrator
    packet carry, and it was set from `intended_target` at every fidelity:
    a gaoler's "Tomorrow you hang." through a door rendered `A voice -- the
    words do not carry.` for the prisoner and for the cook alike, and the
    prisoner's row alone said `directed_at_self: true` (audit
    agents_composer F1, 2026-11-01) -- the second representation carrying a
    fact the first cannot. Whom a line is FOR rides on its words; a listener
    holding all of them (`full`) has it, one holding pieces or the voice
    alone does not. The one self-directed fact such a page does say is the
    listener's own name caught in it (`own_name`, "You catch your name in
    it."), so below `full` the flag says that and nothing about the
    addressee."""
    if fidelity == "full":
        return bool(addressed_to_you)
    return bool(own_name)


def _trace_percept(entry, *, bearing="", order_key=0):
    """A voice DETECTED and no more (`spatial_senses.HEARING_LEVELS`'
    `trace`): no words, no speaker, no tone -- direction at best. What the
    interaction loop already renders as `loop_faint_sound`, as a view
    percept."""
    return Percept(
        kind="speech", channel="hearing", source_label="",
        fidelity="trace",
        data={"level": "trace", "bearing": str(bearing or ""),
              "directed_at_self": False},
        salience=0.3, order_key=order_key,
        dedupe_key="speech-trace:" + _short_hash(entry.get("speaker")))


def typed_affect(entry):
    """The `VOCAL_AFFECTS` member a dialogue entry carries in `vocal_affect`,
    or "" (a record carrying none -- every line recorded before the field,
    and any value outside the set)."""
    from llm.schemas import normalize_vocal_affect
    return normalize_vocal_affect((entry or {}).get("vocal_affect"))


def _voice_feeling(affect, tone, words):
    """What a voice carries of its feeling where its words do not all come
    through, as percept data: the TYPED affect where the record has one
    (`vocal_affect`, DESIGN_SOUND_FIELD § 15 -- a closed set the engine
    owns, rendered through each pack's `vocal_affects`), else the one-word
    tone floor over the line's free-text `tone` (`_carried_tone`), so a line
    recorded before the field renders exactly as it did. `neutral` is an
    affect: the prose gave the voice no feeling, and the free text behind it
    is not read."""
    if affect:
        return {"vocal_affect": affect}
    return {"tone_heard": _carried_tone(tone, words)}


def _affect_word(data):
    """The English pack's word for a percept's typed affect, or "" -- an enum
    key mapped through the pack, never printed raw; a pack may leave a member
    unsaid (`neutral`)."""
    affect = str((data or {}).get("vocal_affect") or "").strip()
    if not affect:
        return ""
    return str((_ENGLISH_COMPOSITOR.get("vocal_affects") or {}).get(affect) or "")


def _feeling_heard(data):
    """The tone word a renderer says after a line heard in pieces or as a
    voice alone: the typed affect's word, else the carried tone."""
    if (data or {}).get("vocal_affect"):
        return _affect_word(data)
    return str((data or {}).get("tone_heard") or "").strip()


#: Where a tone's first part ends: a clause separator in a spaced or an
#: unspaced script. Structure, not words.
_TONE_PART_END = re.compile(r"\s+-{1,2}\s+|[,;:()/—–、，；：（]")
#: What no voice quality contains: a digit, a quotation mark.
_TONE_NOT_A_QUALITY = re.compile(r"[0-9\"“”「」『』]")


def _carried_tone(tone, words):
    """The part of a line's declared `tone` an ear takes in with the voice
    when its words do not come through, or "".

    TONE IS A CHANNEL; WORDS AND NAMES ARE NOT (the firewall's half of § 12).
    A tone is free prose the speaker's own model wrote -- "furious", "warm,
    unhurried, with a small genuine laugh at the clay figure", "leaning
    forward slightly", "brisk, reassuring, the mechanic reporting" -- and
    what crosses a wall with a voice is its colour, never what it was about.
    So only the tone's first part is carried, and only when it is shaped
    like a voice quality: ONE word in a spaced script ("furious", "warm",
    "low" -- a phrase is where what the voice did ends and what the body
    did, "murmured against skin", or what the line was, "whispered
    command", begins), short enough for the manner slot in an unspaced one
    (`_fits_the_manner_slot`); no digit or quotation, no capital after its
    first letter (a name), not a conduct the pack's tone reader already
    calls one (`tone_behavior_words`, what the eye takes in), and no word
    of the line itself. Anything else is withheld whole: a tone lost is a
    sentence shorter, a tone that leaks carries the words the wall kept.
    Deterministic and subtractive; a guard, listed for the owner."""
    from story.character_schema import _UNSPACED_SCRIPT
    raw = _strip_sentence_ends(
        _TONE_PART_END.split(str(tone or "").strip(), 1)[0].strip())
    if not raw or not _fits_the_manner_slot(raw) \
            or _TONE_NOT_A_QUALITY.search(raw) \
            or any(ch.isupper() for ch in raw[1:]) \
            or (not _UNSPACED_SCRIPT.search(raw) and len(raw.split()) != 1):
        return ""
    head = _lower_lead(raw)
    tokens = _tone_words(head)
    if tokens & _pack_words("tone_behavior_words"):
        return ""
    if tokens & _tone_words(words):
        return ""
    return head


def _register_heard_unseen(register, speaker):
    """The speaker's register as it may be said to a listener who can
    neither see them nor knows their voice, or "".

    Review round 4 (2026-10-05) refused every register to a listener in the
    dark, for two reasons that stay true: sheet text can NAME the body it
    belongs to, and a register that is a clause is prose about anything.
    So only a register shaped like a voice quality -- every part of it fits
    the manner slot (`_fits_the_manner_slot`), as "low contralto, warm and
    unhurried" does and "the voice of someone who has smoked for years"
    does not -- holding no word of the speaker's own name
    (`common._identity_token_set`). Anything else is withheld whole: the
    listener has "a voice", as before."""
    register = str(register or "").strip()
    if not register or not _fits_the_manner_slot(register):
        return ""
    return "" if _names_the_speaker(register, speaker) else register


def _voice_sound_heard_unseen(sound, speaker):
    """The card's account of the voice's sound (`embodiment.voice`) as it
    may be said to a listener who can neither see the speaker nor knows
    the voice, or "".

    The NAME GUARD is the register's (`_names_the_speaker`): sheet text can
    name the body it belongs to, and a name is the one thing a voice in the
    dark must not hand over -- that is the firewall's floor, so it stays
    code. The register's SHAPE floor (`_fits_the_manner_slot`) is not
    applied: that floor exists because a register is authored for the
    manner slot and a clause there is prose about anything, where this
    field is authored FOR this sentence -- "The voice is {sound}." -- and a
    sound like "a woman's, past fifty, with the clipped vowels of the
    coast" is exactly what it is for, and four words to a part. A guard
    that fires on the field's own valid output is cut before it is built
    (the owner, 2026-09-06)."""
    sound = str(sound or "").strip()
    if not sound or _names_the_speaker(sound, speaker):
        return ""
    return sound


def _names_the_speaker(text, speaker):
    """Does this sheet text hold a word of the speaker's own name
    (`common._identity_token_set`)? Review round 4's first reason
    (2026-10-05), shared by every account of a voice said in the dark."""
    from story.character_schema import _UNSPACED_SCRIPT
    folded = str(text or "").casefold()
    for token in _identity_token_set(speaker):
        if len(token) >= (1 if _UNSPACED_SCRIPT.search(token) else 3) \
                and token in folded:
            return True
    return False


def own_name_forms(name, aliases=()):
    """THE NAMES OTHERS CALL THIS BODY BY, for `speech_percept`'s own-name
    rescue: its name; the name without a leading article ("The Doctor" is
    called "Doctor"); every word of the name substantial enough to be called
    alone -- a given name, a surname (`common.self_name_forms`, the rule the
    views already use for a body's own name); and its card's aliases.

    Never an engine handle -- a uid, a `character:<id>` -- and never a
    descriptor the engine coined ("the apprentice"): those are not what a
    voice across a room says. A Latin form under three letters is dropped,
    as name-learning drops it (`commit_common._address_forms`): "Al" is
    inside too much English to be a name heard through a wall."""
    from story.character_schema import _UNSPACED_SCRIPT
    base = [str(name or "").strip()]
    base += [str(a or "").strip() for a in (aliases or ())]
    forms = []
    for form in self_name_forms(base[0], [b for b in base if b]):
        forms.append(form)
        for article in ("the ", "a ", "an "):
            if form.casefold().startswith(article) and len(form) > len(article):
                forms.append(form[len(article):].strip())
    out, seen = [], set()
    for form in forms:
        text = str(form or "").strip()
        if not text or text.casefold() in seen:
            continue
        if any(ch in text for ch in "_:/") or any(ch.isdigit() for ch in text):
            continue
        if not _UNSPACED_SCRIPT.search(text) and len(text) < 3:
            continue
        seen.add(text.casefold())
        out.append(text)
    return out


def own_name_said(text, forms) -> bool:
    """Is one of `forms` spoken in `text`, as a whole name? The name-learning
    reader's own rule (`commit_common._form_in`): a name boundary in
    whatever script the name is written, case-insensitive for a distinctive
    name and case-SENSITIVE for one that is also an ordinary word (the
    pack's `_COMMON_WORD_NAMES`: "Will", "Hope", "Data")."""
    from story.character_schema import name_boundary_regex
    body = str(text or "")
    if not body:
        return False
    common_word_names = linguistic("agents.common", "_COMMON_WORD_NAMES")
    for form in forms or ():
        form = str(form or "").strip()
        if not form:
            continue
        flags = 0 if form.casefold() in common_word_names else re.I
        if name_boundary_regex(form, flags).search(body):
            return True
    return False


def _names_kept(percepts):
    """ONE VOICE A BEAT, AND THE NAME IN IT KEPT. Every voice-only line of
    one speaker shares a dedupe key (`speech-voice:`), and the renderers say
    the first; a name caught in a later line of the same speaker would be
    lost with it. So the earliest of each such group carries the group's
    `own_name`. A copy, never the caller's percept."""
    percepts = list(percepts or ())
    named = {p.dedupe_key for p in percepts
             if p.kind == "speech" and p.fidelity == "voice"
             and (p.data or {}).get("own_name")}
    if not named:
        return percepts
    out, done = [], set()
    ranked = sorted(range(len(percepts)), key=lambda i: (
        percepts[i].order_key is None, percepts[i].order_key or 0, i))
    first = {}
    for i in ranked:
        p = percepts[i]
        if p.kind == "speech" and p.fidelity == "voice" \
                and p.dedupe_key in named and p.dedupe_key not in first:
            first[p.dedupe_key] = i
    for i, p in enumerate(percepts):
        if first.get(p.dedupe_key) == i and p.dedupe_key not in done:
            done.add(p.dedupe_key)
            if not (p.data or {}).get("own_name"):
                # The name caught is the group's one self-directed fact
                # (`_said_to_you`), so the row that says it says that too.
                p = dataclasses.replace(p, data={**(p.data or {}),
                                                 "own_name": True,
                                                 "directed_at_self": True})
        out.append(p)
    return out


def _tone_words(text):
    """The content words of a phrase, casefolded, for `_carried_tone`'s
    no-word-of-the-line test: letter runs of four or more in a spaced
    script (so "ledger-obsessed" holds "ledger"), every content run in an
    unspaced one (`common._muffle_tokens`' own reading of such a script)."""
    from story.character_schema import _UNSPACED_SCRIPT
    text = str(text or "")
    if _UNSPACED_SCRIPT.search(text):
        runs, _keep = _muffle_tokens(text)
        return {r.casefold() for r in runs if r}
    return {w.casefold() for w in re.findall(r"[^\W\d_]+", text)
            if len(w) >= 4}


def silence_percept(display, *, order_key=0):
    """THE UNANSWERED ADDRESS, as a fact (D6, review 2026-09-07).

    A line spoken to somebody who says nothing back is an event: it is the
    whole of subtext, and every stage the engine has was silent about it,
    so the page either invented "no answer came" about a body that had in
    fact answered elsewhere, or -- more often -- let the beat pass as though
    the addressee had not been spoken to. It has no percept anywhere because
    perception is built out of what ARRIVED, and nothing arrives.

    It states the fact and never the reason. "T says nothing" is what the
    addresser has: they spoke to T, T could hear it, and no voice of T's
    reached them. Whether T refused, was thinking, did not care or answered
    somebody else is not in this percept and must not be read out of it --
    that is exactly the inference the beat is FOR.

    It is a hearing percept because it is a fact about the hearing channel:
    it belongs to the person who was listening for an answer, and the caller
    (`perception._outcome_event_stream`) mints one only into the view of the
    observer who did the addressing.
    """
    label = str(display or "").strip()
    if not label:
        return None
    return Percept(
        kind="speech", channel="hearing", source_label=label,
        fidelity="silence", data={"silence": True},
        salience=0.5, order_key=order_key,
        dedupe_key="speech:silence:" + _short_hash(label, str(order_key)),
    )


def communication_percept(entry, rel, observer_name, *, display, can_see,
                           proximity=None, order_key=0, observer_id=None,
                           senses=None, addressed=None):
    """Admit described communication without manufacturing a quotation.
    The ear rung reaches only its addressee here too (`line_hear_level`)."""
    if concealed_from_observer(entry, observer_name, observer_id):
        return None
    from .common import communication_surface
    surface = communication_surface(entry)
    if not surface:
        return None
    volume = str(entry.get("volume") or "normal")
    if addressed is None:
        addressed = line_addressed(entry, observer_name, observer_id)
    level = line_hear_level(entry, rel, observer_name, proximity=proximity,
                            senses=senses, seen=bool(can_see),
                            addressed=addressed)
    if level == "none":
        return None
    if level == "trace":
        # Detected and nothing more: not even who (`_trace_percept`).
        return _trace_percept(entry, order_key=order_key)
    # Partial hearing cannot deliver a proposition whose words were never
    # specified.  It carries only that communication occurred.
    data = {
        "surface": surface if level == "full" else "speaks indistinctly",
        "level": level, "volume": volume, "can_see": bool(can_see),
        # Whom it was for rides on what was heard (`_said_to_you`): "speaks
        # indistinctly" says nothing of it.
        "directed_at_self": _said_to_you(
            "full" if level == "full" else "fragment",
            any(_addresses(target, observer_name)
                for target in entry.get("targets") or [])),
    }
    channel = rel.get("comm_channel")
    if isinstance(channel, dict) and not rel.get("same_room"):
        data["via"] = str(channel.get("name") or channel.get("id") or "")
    return Percept(
        kind="communication", channel="hearing", source_label=display,
        fidelity="full" if level == "full" else "fragment", data=data,
        salience=0.7, order_key=order_key,
        dedupe_key="communication:" + _short_hash(
            entry.get("speaker"), entry.get("act"), entry.get("content")),
    )
