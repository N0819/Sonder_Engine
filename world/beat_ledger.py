"""THE BEAT'S EVENTS, AS WORLD STATE.

The owner, on why a character's act was being handled twice: "shouldn't it go
character -> director -> recompiler -> world -> perception? Why would it be
rendered twice?" And then the rule that settles what belongs here: "just
because a majority of these are temporary actions and dialogues, does not mean
they shouldn't be rendered in the world. The world just renders them in the
order declared and what isn't permanent is gone after perception rolls."

So this is the world's record of WHAT HAPPENED THIS BEAT AND IN WHAT ORDER --
the chronology the causality recompiler reassembled after the Director
dissected the input and five hands resolved it in parallel. It is the missing
half of "perception should only be reading the world": a position, a pose, an
attire row all live in the scene and perception reads them there, but the
beat's own acts lived only in the declarations, so the one thing perception
could not read from the world was the beat.

NOTHING SWEEPS IT, AND THAT IS THE DESIGN. The record carries the beat that
wrote it and `beat_events` refuses any other beat's -- exactly as
`sensory_events` does in `world/spatial_sound_field.py`, and for the same
reason stated there: THE BEAT NUMBER IS THE LIFETIME. A sweep is a second
thing that has to run, on every path, forever, and the beat it fails to run on
is the beat that renders a stale event as though it had just happened. A
reader that must prove the beat matches cannot be wrong that way: a turn that
crashes, a resume, a reroll, a restored checkpoint and a branch all inherit a
record that answers `[]` the moment the beat number moves, which is what "gone
after perception rolls" means without anything doing the going.

WHY IT IS WRITTEN AT THE COMPOSITION AND NOT AT THE COMMIT. `sensory_events`
is recorded by `_record_sensory_events` during `commit_scene_state`, and the
commit runs AFTER the narrator -- which is why that record reads empty during
its own beat and stale a turn later, and is fine there, because its reader is
the next beat's sound field. This one's reader is perception, in this beat, so
it is written by `compose_beat_scene`: the one composition of "the scene this
beat produced", shared by `perception_outcome` and the commit, and composed
before either renders anything.
"""

#: Where the record lives on the scene.
BEAT_EVENTS_KEY = "beat_events"

# THERE IS NO CAP ON HOW MANY EVENTS A BEAT MAY HOLD, and that is a ruling
# rather than an oversight. The owner: "hypothetically the director should be
# able to hand and render quite an absurd amount of events per beat" -- which
# follows from the thesis the recompiler was built for, "a system that can
# decipher any arbitrarily long series of events by a player or character and
# resolve it properly with proper respect to chronology and space". Arbitrarily
# long and at-most-N cannot both be true.
#
# A cap of 64 stood here for one commit, defended as stopping a looping model
# from growing an unbounded blob inside a scene that is deep-copied several
# times a turn. THE PREMISE WAS FALSE: the author's whole `sequence` is already
# persisted at full length in the `director_resolve` variant row, and this
# record is a MIRROR of it. Capping the mirror prevented no blob -- it only let
# the world's record silently disagree with the Director's about what happened,
# which is the one thing a causality record may not do, and it did it by
# dropping the TAIL of a long beat, the half a reader is least likely to miss.
#
# What actually bounds this record is `EVENT_FIELDS`: every row is a strict
# projection onto eight short strings, so the cost is linear in a quantity the
# Director already decided and already stored.
#
# For scale, the long run's 11 stored beats: mean 4.9 elements, median 5,
# max 7.

#: The fields an event row carries, and nothing else reaches the scene. A
#: strict projection rather than a passthrough: the author's element holds
#: `attempt` -- the actor's own intent-bearing words -- and `observable` is the
#: intent-free outward form an onlooker is entitled to. Copying the element
#: wholesale would put the first into the world for every observer to read,
#: which is the exact leak the perception filter exists to prevent.
EVENT_FIELDS = ("order", "actor", "declared", "surface", "kind", "text",
                "category", "note")


def _clean_event(row):
    """One event row, projected onto `EVENT_FIELDS` with string values."""
    if not isinstance(row, dict):
        return None
    clean = {}
    for field in EVENT_FIELDS:
        value = row.get(field)
        if field == "order":
            try:
                clean["order"] = int(value)
            except (TypeError, ValueError):
                return None
            continue
        text = str(value or "").strip()
        if text:
            clean[field] = text
    return clean if clean.get("actor") or clean.get("surface") \
        or clean.get("text") else None


def record_beat_events(scene, turn_idx, events):
    """Write this beat's events onto `scene`, replacing any earlier beat's.

    An empty list is still a RECORD and still gets written: "this beat had no
    events" and "no beat has spoken" are different answers, and a scene that
    keeps the older beat's list would let the second be read as the first.
    A beat the caller cannot name writes nothing -- the record is worthless
    without the number that bounds it.

    EVERY event is kept. However many the Director handed over is how many
    happened, and a record that holds some of them is a record that is wrong
    about the beat.
    """
    if not isinstance(scene, dict) or turn_idx is None:
        return []
    try:
        beat = int(turn_idx)
    except (TypeError, ValueError):
        return []
    rows = []
    for row in (events if isinstance(events, list) else []):
        clean = _clean_event(row)
        if clean is not None:
            rows.append(clean)
    scene[BEAT_EVENTS_KEY] = {"beat": beat, "events": rows}
    return rows


def beat_events(scene, turn_idx):
    """This beat's events, and only this beat's.

    `[]` for any other beat, for a scene holding no record, and for a reader
    with no beat to ask about -- a chronology may only be believed on evidence
    that it is THIS beat's.
    """
    record = (scene or {}).get(BEAT_EVENTS_KEY)
    if not isinstance(record, dict) or turn_idx is None:
        return []
    try:
        beat = int(record.get("beat"))
        wanted = int(turn_idx)
    except (TypeError, ValueError):
        return []
    if beat != wanted:
        return []
    events = record.get("events")
    if not isinstance(events, list):
        return []
    return [e for e in events if isinstance(e, dict)]


def beat_event_order(scene, turn_idx):
    """`{declaration_event_id: order}` -- where in the beat each declared act
    happened, according to the world.

    This is the join perception makes. The stream it builds is keyed on the
    DECLARATIONS -- an act's `event_id` from `assign_event_ids` -- and the
    ledger's rows cite the declaration each describes, so the world can put a
    stream built out of several separate declarations into the one order the
    beat actually ran in. An act the ledger does not name is simply absent
    from the map, and its reader leaves such an entry where it already was.
    """
    order = {}
    for row in beat_events(scene, turn_idx):
        declared = str(row.get("declared") or "").strip()
        if declared and declared not in order:
            try:
                order[declared] = int(row.get("order"))
            except (TypeError, ValueError):
                continue
    return order
