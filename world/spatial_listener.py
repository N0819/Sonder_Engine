# spatial_listener.py
"""THE LISTENER'S STATE: what a body's own condition does to what reaches
its ears (`DESIGN_SOUND_FIELD.md` § 13, wave B1, 2026-10-20).

The hearing rule (§ 11) and wave A (§ 12) price the PATH between a speaker
and a listener. This module prices the one thing every path ends at -- the
listener's EAR -- from typed state only, never from prose:

  * an ear that is COVERED: a settled contact over both of the listener's
    ears (`ear_cover_db`);
  * the listener's OWN NOISE: a running thing in their own hands, at their
    own ear (`own_noise_db`);
  * an ear DULLED by a blast, recovering with the story clock
    (`HEARING_KEY`, `blast_shift_db`, `recovered_shift_db`);
  * a SLEEPER, and what wakes one (`WAKING_DB`, `wakes_sleeper`).

Each is a cap, and caps only ever subtract: a listener whose ear carries none
of them is graded byte for byte as before, because nothing here is stamped
on their relation (`stamp_listener_ear`).

The owner, 2026-10-20: "the system is failing to meet several real world
principles", and, on this list, "I guess go ahead". Every constant below
states the real-world figure it is taken from.
"""

from __future__ import annotations

import math
from typing import Optional

from world.spatial_sound_field import (
    AMBIENT_DB, AV_BENEFIT_DB, DIN_DB, SPEECH_DB, _ONE_PACE_LOSS_DB,
    _running, _voice_path_loss_db, db_of_power,
    lombard_level_db, normalize_sound_level, power_of_db, quantise_hearing_db,
    quantise_speech_db,
)


# ---------------------------------------------------------------------------
# The ear's own floor
# ---------------------------------------------------------------------------

#: WHERE A HEALTHY EAR IN PERFECT QUIET FOLLOWS A SENTENCE, in dB(A) at the
#: ear: the speech reception threshold of a normal listener sits at 0-10 dB
#: HL, and 0 dB HL for speech in a sound field is about 20 dB SPL, so a
#: sentence is followed from about 20-30 dB(A) and words are caught some
#: way under it. The middle, 25. Read only by an ear something has changed:
#: an uncovered, undulled ear in a lived-in room hears against the room's
#: own floor (`AMBIENT_DB`, 27 and up), which is above it, and that is why
#: the hearing rule never needed it. A covered ear takes the room's floor
#: down with the voice, and a dulled one raises this.
EAR_SPEECH_THRESHOLD_DB = 25.0

#: HANDS OVER BOTH EARS take 15-25 dB from what reaches them (the palms seal
#: the pinna imperfectly; measured hand-over-ear attenuation is about 15-25
#: dB across speech frequencies). The middle, 20.
EARS_COVERED_DB = 20.0

#: THE EAR CANAL STOPPED -- a finger or a plug in each ear -- takes 25-30
#: dB at speech frequencies (foam earplugs as worn, and a fingertip pressed
#: into the canal). The middle, 27.
EARS_STOPPED_DB = 27.0


# ---------------------------------------------------------------------------
# Covered ears, from the contact ledger
# ---------------------------------------------------------------------------

def _is_an_ear(part) -> bool:
    """Is this contact part an EAR -- the part kind `ear`, or a place on one
    that repeats its word ("ear canal", "both ears")? The structural rule of
    `spatial_contacts._same_appendage`, with ONE kind, not a vocabulary: the
    same reading `spatial_substance` makes of a mouth for a stifled line."""
    from world.spatial_contacts import _part_identity, _same_appendage
    kind, _instance = _part_identity(part)
    return bool(kind) and _same_appendage("ear", kind)


def _is_a_pair(part) -> bool:
    """Is the covering part a PAIR -- "hands", "palms", "fingers" -- that can
    be over both ears at once? A plural part, or no part at all (a thing
    pressed over the head: a pair of earmuffs needs no hand). One thumb on
    "ears" is a thumb on an ear's edge, never both ears sealed (chat 178
    turn 25: a thumb resting against the edge of a fox ear)."""
    from world.spatial_contacts import _part_is_plural
    words = str(part or "").strip().casefold().replace("_", " ") \
        .replace("-", " ").split()
    return not words or _part_is_plural(words[-1]) or "both" in words


def _ear_side(part) -> str:
    """Which ear a part names: `both` for a plural ("ears", "both ears"),
    the fiction's own lateral word ("left", "right") where it gave one, else
    `one` -- "her ear" is a definite description of one ear, never both."""
    from world.spatial_contacts import _part_identity, _part_is_plural
    text = str(part or "").strip().casefold()
    kind, instance = _part_identity(part)
    words = text.replace("_", " ").replace("-", " ").split()
    if (words and _part_is_plural(words[-1])) or "both" in words:
        return "both"
    return instance or "one"


def ear_cover_db(scene: dict, listener: str) -> float:
    """How many decibels what COVERS this listener's ears takes from
    everything that reaches them, or 0.0 for an open ear.

    TYPED STATE ONLY: a SETTLED contact in the scene's ledger whose target is
    this listener and whose target part is an ear -- the listener's own
    hands over their ears, or anybody else's. A contact INTO the ear
    (`relation: interior`: a finger or a plug in the canal) stops it
    (`EARS_STOPPED_DB`); one on its surface covers it (`EARS_COVERED_DB`).
    BOTH EARS, or nothing: one covered ear leaves the other hearing the room,
    and the head's shadow costs a sound from that side a few decibels at
    most -- a plural part ("ears"), or a left and a right. A moving contact
    -- a hand rubbing an ear -- seals nothing.

    WHAT IS NOT READ, and why. A hood, a helmet, earmuffs: the attire ledger
    knows a garment covers the `head`, never whether it covers the ears (a
    hat and a hood are one region), and a garment's NAME is prose -- reading
    "hood" out of it is the word list this engine refuses. Registered
    (§ 13 of the sound note)."""
    from world.spatial_contacts import (CONTACT_MOMENTARY_MANNERS,
                                        _contact_motion_from_text,
                                        _normalize_contact_motion)
    from world.spatial_identity import same_subject
    contacts = (scene or {}).get("contacts") if isinstance(scene, dict) else None
    if not listener or not isinstance(contacts, list):
        return 0.0
    covered = []
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        manner = str(contact.get("manner") or "").strip().casefold()
        # SETTLED, read the way the contact ledger reads a record saved
        # before `motion` existed (`_contact_motion_from_text`): a hand
        # circling an ear in a massage seals nothing (chat 44 turn 91), and
        # a brush of the lips is a moment, not a covering.
        motion = _normalize_contact_motion(contact.get("motion")) \
            or _contact_motion_from_text(manner, contact.get("detail"))
        if motion == "moving" or manner in CONTACT_MOMENTARY_MANNERS:
            continue
        target = str(contact.get("target") or "").strip()
        part = contact.get("target_part")
        if not target or not _is_an_ear(part):
            continue
        if not same_subject(scene, target, listener):
            continue
        stopped = str(contact.get("relation") or "").strip().casefold() \
            == "interior"
        side = _ear_side(part)
        if side == "both" and not _is_a_pair(contact.get("actor_part")):
            side = "one"            # one hand, one thumb: one ear at most
        covered.append((side, EARS_STOPPED_DB if stopped else EARS_COVERED_DB))
    both = [loss for side, loss in covered if side == "both"]
    if both:
        return max(both)
    # Each ear the fiction NAMED is one ear (its best covering); each "ear"
    # it did not name is one more. Two hands each on "an ear" are both
    # ears: a body has two, and the fiction put a hand on one twice.
    per_ear = {}
    unnamed = []
    for side, loss in covered:
        if side == "one":
            unnamed.append(loss)
        else:
            per_ear[side] = max(per_ear.get(side, 0.0), loss)
    ears = sorted(list(per_ear.values()) + unnamed, reverse=True)
    if len(ears) < 2:
        return 0.0
    # The weaker of the two coverings is what the pair lets through.
    return ears[1]


# ---------------------------------------------------------------------------
# The listener's own noise
# ---------------------------------------------------------------------------

def own_noise_db(scene: dict, listener: str, sound=None) -> Optional[float]:
    """The level at this listener's own ear of what THEY are sounding: a
    running thing (`sound_source`, `state.running`) in their own hands --
    its holder is the listener (`spatial_sound_field.sound_sources` places a
    held thing at its holder's own cell) -- or None.

    Counted ONLY WHERE IT IS A DIN AT THE EAR (`DIN_DB`, the noise words'
    own threshold): a ticking watch in a pocket is not self-masking; a drill,
    a hair-dryer or a vacuum cleaner in the hand is, and a voice from across
    the room is not followed over it until it stops. Real world: an operator
    hears others less over the machine in their own hands -- it stands at
    their ear, where the speaker, a few paces off, meets it some ten
    decibels down and raises their voice only that far.

    NOT READ, by ruling or for want of a typed fact: a one-beat sound the
    listener makes -- a hammer blow, a cough -- is a moment, not a floor (the
    owner, 2026-09-25: "sounds should be allowed to be transient mid beat",
    `SoundField.noise_at`); and the listener's own SPEECH, because a beat's
    lines take turns and nothing typed says two of them overlapped -- a
    listener reading their own line as masking every other line of the beat
    would never hear an answer."""
    if not listener or not isinstance(scene, dict):
        return None
    from world.spatial_identity import same_subject
    total = 0.0
    sources = getattr(sound, "_raw_sources", None)
    if sources is not None:
        # The beat's own sources, as the field placed them (a failing one
        # out on this beat already carries no power).
        for source in sources or ():
            if not isinstance(source, dict) or source.get("kind") != "entity":
                continue
            holder = str(source.get("holder") or "").strip()
            if holder and same_subject(scene, holder, listener):
                total += float(source.get("power") or 0.0)
    else:
        # No field (a scene without geometry): the running things in the
        # listener's own hands, at their level at the holder's cell. Read
        # straight off the scene -- this runs for every relation a reader
        # builds, so it never builds the whole source list.
        from world.spatial_containment import container_of
        from world.spatial_sound_field import SOUND_POWER
        entities = scene.get("entities")
        for eid, entity in (entities.items() if isinstance(entities, dict)
                            else ()):
            if not isinstance(entity, dict):
                continue
            level = normalize_sound_level(entity.get("sound_source"))
            if not level or not _running(entity):
                continue
            holder = container_of(scene, eid) or container_of(
                scene, str(entity.get("name") or eid))
            if holder and same_subject(scene, holder, listener):
                total += SOUND_POWER.get(level, 0.0)
    if total <= 0.0:
        return None
    level = db_of_power(total)
    return level if level >= DIN_DB - 1e-9 else None


# ---------------------------------------------------------------------------
# An ear dulled by a blast
# ---------------------------------------------------------------------------

#: Where a body's dulled hearing lives: a scene key, beside the body's other
#: live physical state (positions, contacts, vitals), so every reader that
#: grades what reaches an ear reads it off the scene it is handed.
#: `{name: {"shift_db", "shift0_db", "since_seconds", "exposure_db"}}` --
#: written by the commit alone (`persist.commit_scene_state`), from the
#: exposures the outcome view measured, and aged there by the clock.
HEARING_KEY = "dulled_hearing"

#: AN IMPULSE PAST ABOUT 120-140 dB AT THE EAR leaves a TEMPORARY THRESHOLD
#: SHIFT: a gunshot close by, an explosion, a blast in a confined space.
#: The ear is muffled for a while after and rings. 120, the lower end of the
#: range and the threshold of discomfort, read as the loudest sound at the
#: listener's ear this beat (an event or a standing source, through their
#: covering if any).
BLAST_DB = 120.0

#: How far the ear's threshold moves, in dB at speech frequencies: some 20
#: dB just past the blast threshold, a decibel more for each decibel over it,
#: to 40 -- unprotected impulse exposures of 140 dB and up measure TTS of
#: 20-40 dB and more; past 40 the damage is no longer temporary, which this
#: engine does not model.
DULLED_SHIFT_AT_BLAST_DB = 20.0
DULLED_SHIFT_MAX_DB = 40.0

#: HOW IT RECOVERS. A temporary threshold shift is measured two minutes
#: after exposure (TTS2) and falls LINEARLY WITH THE LOGARITHM OF THE TIME
#: SINCE (Ward, Glorig & Sklar 1959); a shift under 40 dB is gone within
#: about sixteen hours. So the shift is held whole for two minutes and is
#: gone at sixteen hours: some 45% of it remains after an hour, a ninth
#: after eight.
DULLED_HELD_SECONDS = 120.0
DULLED_RECOVERY_SECONDS = 16 * 3600.0

#: Under this many decibels of shift the record is dropped: the ear is back.
DULLED_GONE_DB = 1.0

#: THE EARS RING while the shift is at least this: tinnitus after a blast
#: accompanies the larger shifts and fades with them. Told to the listener
#: as their own body's state (interoception); nobody else knows it unless
#: they see it.
RINGING_DB = 10.0


def blast_shift_db(exposure_db) -> float:
    """The threshold shift an exposure at the ear leaves, or 0.0 under the
    blast threshold (`BLAST_DB`)."""
    try:
        exposure = float(exposure_db)
    except (TypeError, ValueError):
        return 0.0
    if exposure < BLAST_DB:
        return 0.0
    return min(DULLED_SHIFT_MAX_DB,
               DULLED_SHIFT_AT_BLAST_DB + (exposure - BLAST_DB))


def recovered_shift_db(shift0_db, elapsed_seconds) -> float:
    """What remains of a shift of `shift0_db` after `elapsed_seconds`: whole
    for `DULLED_HELD_SECONDS`, then falling linearly in the logarithm of the
    time to nothing at `DULLED_RECOVERY_SECONDS`."""
    try:
        shift0 = max(0.0, float(shift0_db))
        elapsed = max(0.0, float(elapsed_seconds))
    except (TypeError, ValueError):
        return 0.0
    if elapsed <= DULLED_HELD_SECONDS:
        return shift0
    if elapsed >= DULLED_RECOVERY_SECONDS:
        return 0.0
    span = math.log10(DULLED_RECOVERY_SECONDS / DULLED_HELD_SECONDS)
    done = math.log10(elapsed / DULLED_HELD_SECONDS) / span
    return shift0 * max(0.0, 1.0 - done)


def _hearing_record(scene, listener) -> Optional[dict]:
    ledger = (scene or {}).get(HEARING_KEY) if isinstance(scene, dict) else None
    if not isinstance(ledger, dict) or not listener:
        return None
    record = ledger.get(listener)
    if record is None:
        folded = str(listener).strip().casefold()
        record = next((rec for name, rec in ledger.items()
                       if str(name).strip().casefold() == folded), None)
    return record if isinstance(record, dict) else None


def dulled_shift_db(scene: dict, listener: str) -> float:
    """This listener's threshold shift as the scene holds it (the commit ages
    it with the clock every beat), or 0.0."""
    record = _hearing_record(scene, listener)
    if not record:
        return 0.0
    try:
        return max(0.0, float(record.get("shift_db") or 0.0))
    except (TypeError, ValueError):
        return 0.0


def next_hearing_ledger(ledger, exposures, now_seconds) -> dict:
    """The dulled-hearing ledger after a beat: every record aged to
    `now_seconds`, every exposure this beat (`{name: dB at the ear}`) laid
    on -- a fresh blast restarts the recovery from the larger of what
    remained and what it leaves -- and every ear that has recovered dropped.
    Pure; the commit stores what it returns."""
    out = {}
    try:
        now = float(now_seconds or 0.0)
    except (TypeError, ValueError):
        now = 0.0
    for name, record in (ledger or {}).items():
        if not isinstance(record, dict):
            continue
        try:
            since = float(record.get("since_seconds") or 0.0)
            shift0 = float(record.get("shift0_db") or record.get("shift_db")
                           or 0.0)
        except (TypeError, ValueError):
            continue
        shift = recovered_shift_db(shift0, now - since)
        if shift >= DULLED_GONE_DB:
            out[str(name)] = {**record, "shift_db": round(shift, 1)}
    for name, exposure in (exposures or {}).items():
        shift = blast_shift_db(exposure)
        if shift <= 0.0 or not str(name or "").strip():
            continue
        key = next((k for k in out if k.casefold() == str(name).casefold()),
                   str(name))
        remaining = float((out.get(key) or {}).get("shift_db") or 0.0)
        if shift < remaining:
            continue
        out[key] = {"shift_db": round(shift, 1), "shift0_db": round(shift, 1),
                    "since_seconds": now,
                    "exposure_db": round(float(exposure), 1)}
    return out


def blast_possible(scene: dict, events=()) -> bool:
    """Could anything this beat reach `BLAST_DB` at an ear at all: a one-beat
    sound or a running thing at that level or more at its own cell? The
    cheap test that keeps the ordinary beat from measuring any ear for it."""
    from world.spatial_sound_field import SOUND_DB, event_db
    for event in events or ():
        if isinstance(event, dict):
            try:
                if event_db(event) >= BLAST_DB:
                    return True
            except Exception:
                continue
    entities = (scene or {}).get("entities") if isinstance(scene, dict) else None
    for entity in (entities or {}).values() if isinstance(entities, dict) else ():
        if not isinstance(entity, dict) or not _running(entity):
            continue
        level = normalize_sound_level(entity.get("sound_source"))
        if level and SOUND_DB.get(level, 0.0) >= BLAST_DB:
            return True
    return False


def loudest_at_ear(sound, listener, *, room=None, distant=(),
                   scene=None) -> Optional[float]:
    """The loudest thing at this listener's ear this beat, in dB, through
    whatever covers it: every placed source on their field -- the beat's
    one-off sounds and everything running -- and any far sound the room
    graph brought in (`distant`, `spatial_sound_field.distant_sounds`
    records). None where the field cannot place them."""
    best = None
    if sound is not None and sound.locate(listener, room) is not None:
        for source in sound.sources:
            power = sound.signal_at(listener, source["id"], room=room)
            if power:
                level = db_of_power(power)
                best = level if best is None else max(best, level)
    for record in distant or ():
        try:
            level = float(record.get("db"))
        except (TypeError, ValueError, AttributeError):
            continue
        best = level if best is None else max(best, level)
    if best is None:
        return None
    if scene is None:
        scene = getattr(sound, "scene", None) or {}
    return best - ear_cover_db(scene, listener)


# ---------------------------------------------------------------------------
# The ear, as a cap on what a line delivers
# ---------------------------------------------------------------------------

def stamp_listener_ear(scene: dict, rel: dict, observer: str, *,
                       sound=None) -> dict:
    """What the hearing rule reads off the LISTENER, stamped on a
    body-to-body relation (`spatial_senses.spatial_rel_between`):
    `ear_cover_db`, `own_noise_db`, `dulled_db` -- each only where it is
    there. A relation whose listener's ear carries none of them is returned
    exactly as given."""
    if not isinstance(rel, dict) or not observer or not isinstance(scene, dict):
        return rel
    cover = ear_cover_db(scene, observer)
    if cover > 0.0:
        rel["ear_cover_db"] = cover
    own = own_noise_db(scene, observer, sound)
    if own is not None:
        rel["own_noise_db"] = own
    shift = dulled_shift_db(scene, observer)
    if shift > 0.0:
        rel["dulled_db"] = shift
    return rel


def ear_is_changed(rel) -> bool:
    """Does this relation's listener carry anything at the ear?"""
    return isinstance(rel, dict) and any(
        rel.get(key) for key in ("ear_cover_db", "own_noise_db", "dulled_db"))


def ear_noise_db(rel) -> float:
    """What a voice is heard AGAINST at this listener's ear, in dB: the
    room's quiet floor and the listener's own noise, both through whatever
    covers the ear, and the ear's own threshold raised by any shift -- the
    three summed as powers."""
    cover = float(rel.get("ear_cover_db") or 0.0)
    floor = float(rel["floor_db"]) if rel.get("floor_db") is not None \
        else AMBIENT_DB["enclosed"]
    parts = [floor - cover,
             EAR_SPEECH_THRESHOLD_DB + float(rel.get("dulled_db") or 0.0)]
    if rel.get("own_noise_db") is not None:
        parts.append(float(rel["own_noise_db"]) - cover)
    return db_of_power(sum(power_of_db(part) for part in parts))


def _speech_word(volume) -> str:
    word = str(volume or "normal").strip().casefold()
    return word if word in SPEECH_DB else "normal"


def voice_at_ear_db(rel: dict, volume, *, reach=None,
                    level_db=None) -> Optional[float]:
    """The level a line's voice reaches the listener's ear at, BEFORE the
    ear: the speaker's level, raised over what they speak against
    (`lombard_level_db`, where the relation knows it), less the hearing
    rule's own path -- rooms away the far field's loss, under the sky the
    open air's, otherwise its path classes (`_voice_path_loss_db`). None
    where no air carries a voice at all -- and for a voice through a body's
    mass (the conducted cases), which the hearing rule answers by its own
    table and no air budget prices."""
    if rel.get("inside_source") or rel.get("enclosed_from_source") \
            or rel.get("source_enclosed"):
        return None
    word = _speech_word(volume)
    level = float(level_db) if level_db is not None else SPEECH_DB[word]
    if level_db is None:
        speaker_noise = rel.get("speaker_masking_db")
        if speaker_noise is None:
            speaker_noise = rel.get("speaker_din_db")
        raised = lombard_level_db(word, power_of_db(speaker_noise)
                                  if speaker_noise is not None else None)
        if raised is not None:
            level = raised
    if rel.get("far_loss_db") is not None \
            and math.isinf(float(rel["far_loss_db"])):
        return None
    from world.spatial_barriers import normalize_barrier
    barrier = normalize_barrier(rel.get("barrier"))
    if rel.get("far_loss_db") is None and rel.get("open_air_loss_db") is None \
            and not rel.get("same_room") and (barrier == "unknown"
                                              or rel.get("distance") == "remote"):
        return None
    # ONE PATH, the masking budget's own (`_voice_path_loss_db`): rooms away
    # the far field's loss, under the sky the open air's, otherwise the
    # rule's path classes -- so whatever that path learns to charge, this
    # ear is charged it too.
    return level - _ONE_PACE_LOSS_DB - _voice_path_loss_db(rel, reach)


def ear_margin_db(rel: dict, volume, *, reach=None, level_db=None,
                  seen=False) -> Optional[float]:
    """How far over the listener's ear (`ear_noise_db`) a line's voice
    arrives, in dB, or None where the ear is unchanged or no air carries
    it. A watched face is worth `AV_BENEFIT_DB` here as wherever noise
    decides: a muffled or masked ear reads the lips as well."""
    if not ear_is_changed(rel):
        return None
    if rel.get("inside_source") or rel.get("enclosed_from_source") \
            or rel.get("source_enclosed"):
        return None
    voice = voice_at_ear_db(rel, volume, reach=reach, level_db=level_db)
    if voice is None:
        return None
    voice -= float(rel.get("ear_cover_db") or 0.0)
    if seen:
        voice += AV_BENEFIT_DB
    return voice - ear_noise_db(rel)


def ear_level(rel: dict, volume, *, reach=None, level_db=None,
              seen=False) -> str:
    """WHAT THE LISTENER'S EAR LEAVES OF A LINE: `full | fragment | none`, by
    the voice at their ear (`voice_at_ear_db`, through their covering)
    against what their ear hears it against (`ear_noise_db`), at the speech
    margins (`quantise_speech_db`). `full` where the ear is unchanged, and
    for the conducted cases, which keep their own answers -- a voice
    through a body's mass is not air an ear can be covered against."""
    from world.spatial_senses import UNVOICED_VOLUMES
    margin = ear_margin_db(rel, volume, reach=reach, level_db=level_db,
                           seen=seen)
    if margin is None:
        return "full"
    word = _speech_word(volume)
    noise = ear_noise_db(rel)
    return quantise_speech_db(noise + margin, noise,
                              voiced=word not in UNVOICED_VOLUMES)


def ear_reason(rel) -> str:
    """Which of the ear's three states decided, in `hearing_reason`'s words:
    the largest of what each adds over the room's own floor."""
    cover = float(rel.get("ear_cover_db") or 0.0)
    shift = float(rel.get("dulled_db") or 0.0)
    own = rel.get("own_noise_db")
    floor = float(rel["floor_db"]) if rel.get("floor_db") is not None \
        else AMBIENT_DB["enclosed"]
    weights = {"ears_covered": cover, "hearing_dulled": shift,
               "own_noise": (float(own) - floor) if own is not None else 0.0}
    return max(weights.items(), key=lambda item: item[1])[0]


def ear_adjusted_db(scene: dict, listener: str, signal_db: float,
                    noise_db: float) -> tuple:
    """A SOUND (not a line) at this listener's ear: `(signal, noise)` in dB
    after what covers the ear (both lowered by it) and the ear's own
    threshold, raised by any shift. Unchanged for an ear that carries
    neither. The listener's own noise is already in `noise_db` -- a held
    thing stands at their own cell on the field."""
    cover = ear_cover_db(scene, listener)
    shift = dulled_shift_db(scene, listener)
    if cover <= 0.0 and shift <= 0.0:
        return signal_db, noise_db
    noise = db_of_power(power_of_db(noise_db - cover)
                        + power_of_db(EAR_SPEECH_THRESHOLD_DB + shift))
    return signal_db - cover, noise


def heard_at_ear(scene: dict, listener: str, sound, source_id, *,
                 room=None) -> str:
    """`SoundField.level_of`, through the listener's ear (`ear_adjusted_db`):
    a covered or dulled ear misses a faint sound an open one catches."""
    signal = sound.signal_at(listener, source_id, room=room)
    noise = sound.noise_at(listener, exclude=(source_id,), room=room)
    if signal is None or noise is None:
        return "none"
    sig_db, noise_db = ear_adjusted_db(scene, listener, db_of_power(signal),
                                       db_of_power(noise))
    return quantise_hearing_db(sig_db, noise_db)


# ---------------------------------------------------------------------------
# A sleeper, and what wakes one
# ---------------------------------------------------------------------------

#: A SLEEPER IS WOKEN by an intrusive sound reaching their ear at about
#: 50-70 dB(A) (behavioural awakening in the laboratory and in the WHO's
#: night-noise review climbs steeply across that span; a smoke alarm must put
#: 75 dB(A) at the pillow to wake nearly every adult). The middle, 60: a
#: voice RAISED anywhere in the room wakes a sleeper, a normal one only at
#: the bedside, a conversation across the room never.
WAKING_DB = 60.0

#: ...and it must stand out of the room: what wakes is a sound loud OR
#: SUDDEN FOR THE ROOM, so it must clear the steady noise at the sleeper's
#: ear by this much (a sleeper on a ship's engine deck sleeps through what
#: would wake one in a quiet bedroom). Ten decibels, the emergence at which
#: an intermittent sound begins to disturb sleep.
WAKING_EMERGENCE_DB = 10.0

#: Only SLEEP is woken by sound. A sedated or unconscious body does not sit
#: up because something was loud -- that is dosage and medicine, the
#: Director's and the clock's (`director_floors._awareness_exits`' third
#: rule draws the same line).
SOUND_WAKES = ("asleep",)

#: What woke them, as the residue says it -- a closed set the engine owns:
#: their own NAME, a VOICE (normal or raised), a SHOUT, a NOISE (anything
#: else that sounded). Never words, never who.
WAKING_SOUNDS = ("name", "voice", "shout", "noise")


def wakes_sleeper(level_db, steady_db) -> bool:
    """Does a sound at `level_db` at a sleeper's ear wake them, over a steady
    `steady_db` there? At `WAKING_DB` and `WAKING_EMERGENCE_DB` over the
    steady noise, both."""
    if level_db is None:
        return False
    steady = float(steady_db) if steady_db is not None else float("-inf")
    return float(level_db) >= WAKING_DB - 1e-9 and \
        float(level_db) >= steady + WAKING_EMERGENCE_DB - 1e-9


def started_sources(prev_scene: dict, scene: dict) -> set:
    """Ids of the running sound sources this beat STARTED -- running now,
    not running (or not there) before. A sound that starts is sudden; one
    that was running when the sleeper went under is the room's own, and a
    sleeper sleeps through it."""
    def running(sc):
        out = set()
        for eid, entity in ((sc or {}).get("entities") or {}).items() \
                if isinstance((sc or {}).get("entities"), dict) else ():
            if isinstance(entity, dict) and \
                    normalize_sound_level(entity.get("sound_source")) and \
                    _running(entity):
                out.add(str(eid))
        return out
    return running(scene) - running(prev_scene)


__all__ = [
    "BLAST_DB", "blast_possible", "DULLED_GONE_DB", "DULLED_HELD_SECONDS",
    "DULLED_RECOVERY_SECONDS", "DULLED_SHIFT_AT_BLAST_DB",
    "DULLED_SHIFT_MAX_DB", "EAR_SPEECH_THRESHOLD_DB", "EARS_COVERED_DB",
    "EARS_STOPPED_DB", "HEARING_KEY", "RINGING_DB", "SOUND_WAKES",
    "WAKING_DB", "WAKING_EMERGENCE_DB", "WAKING_SOUNDS",
    "blast_shift_db", "dulled_shift_db", "ear_adjusted_db", "ear_cover_db",
    "ear_is_changed", "ear_level", "ear_margin_db", "ear_noise_db",
    "ear_reason", "heard_at_ear", "loudest_at_ear", "next_hearing_ledger",
    "own_noise_db", "recovered_shift_db", "stamp_listener_ear",
    "started_sources", "voice_at_ear_db", "wakes_sleeper",
]
