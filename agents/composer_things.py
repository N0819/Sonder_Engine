"""Things in the room: a thing placed or in hand, a thing's readings,
crowds/couriers/notices, chatter, and the (production-dead) micro-round
delivery.

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from language_runtime import linguistic

from agents.composer_common import (
    Percept,
    _cap,
    _en,
    _noun_phrase,
    _t,
    standing_key,
)


def thing_clause(desc, place=""):
    """One THING standing in the room, as a clause a bystander would say.

    The fourth member of `room_content_percepts`' family and the one its own
    docstring forgot: a crowd, a courier, a posted notice -- and a thing
    somebody set down. Measured 2026-09-20 (two_lives v13, chat frame 2): Sal
    Weatherby laid a copper coin on the taproom counter on beat 8, the commit
    recorded it correctly (`stations: {copper_coin: {at: oak_bar_counter}}`,
    `contained` empty), and the coin appeared in 0 of her 24 composed views.
    On beat 10 her own view named the HOST's coin pouch and not her coin, so
    she drew a second coin from her pocket and paid again. Nothing was wrong
    with the world's record and nothing was wrong with her; she was never told.

    There was no sight path from `scene.entities` to any view at all:
    `feature_visibility` answers for "every ANCHOR of the observer's room",
    and perception's only walk over scene entities on the view path is the
    SCENT loop, gated on `entity.scent`. A thing reached a mind only through
    a channel that owned it for some other reason -- attire, a pose, a
    contact, a smell, or being authored furniture. Nothing said "that is
    lying there".

    `place` is the authored description of the anchor it stands at, already
    admitted by the caller; empty for a thing the room holds without placing,
    which names the thing and CLAIMS NO DISTANCE -- the same subtraction
    `_feature_items(placed=False)` makes for furniture seen through a doorway,
    for the same reason: the distance vocabulary is measured within one room
    and spending it where nothing measured states a distance nobody has.
    """
    desc = _noun_phrase(desc)
    if not desc:
        return ""
    place = _noun_phrase(place)
    return (_en("thing_placed", desc=desc, place=place) if place
            else _en("thing_here", desc=desc))


def thing_in_hand_clause(desc, mode=""):
    """A thing the OBSERVER holds or carries, said as theirs.

    Not `thing_clause`'s "There is ... here": a thing in somebody's hands is
    not lying in the room, and Emory read "There is the tallow tub here" in
    seventeen views while the commit held the tub in his grip (playerless
    Aldermill round 7, 2026-09-23). `held` is in hand; anything else a body
    openly bears is carried."""
    desc = _noun_phrase(desc)
    if not desc:
        return ""
    return _en("thing_held_by_you" if str(mode or "").strip().casefold() == "held"
               else "thing_carried_by_you", desc=desc)


#: State keys another renderer already voices, or that are structure rather
#: than a fact a body can read off a thing. `transit`/`hatch` and their
#: fields render through the doorway the engine derives from them
#: (`common` "the open doors" / "still-sealed hatch"); `posture`, `activity`
#: and `held_items` are a BODY's and `body_state_percept` owns them; the
#: rest are bookkeeping the objects hand writes for the engine, not for an
#: eye. Kept as the complement of what is readable rather than a list of
#: what is: anything the hand writes that is not one of these is a fact the
#: thing shows, whatever the thing turns out to be. `clothing`, `worn_by`,
#: `shed` and `garment` are the engine's own shed-garment record
#: (`commit_attire`, `spatial_containment`): the garment is already its label,
#: and whose it was is not written on it -- rendered, a body reading a shed
#: tank top was told "clothing: yes; worn by: Hinami; shed: yes; garment:
#: fitted tank top" (chat 137 replay, 2026-09-23), and a stranger would learn
#: the owner's name off the cloth. `speed` is a vessel's own pace, which the
#: engine times its journeys by (`spatial_transit.vessel_speed`, 2026-10-21):
#: read off a craft lying at its mooring it would state a motion it is not
#: making ("speed: value 7, unit kn"), and what checking a craft finds -- its
#: engine, its sails, its condition -- is in its own words in the rest of its
#: state.
_UNREADABLE_STATE_KEYS = frozenset({
    "transit", "link", "phase", "hatch", "destination_room", "route_room",
    "eta_seconds", "posture", "activity", "held_items", "zone", "description",
    "proximity", "target", "targets", "kind", "name", "lit", "running",
    "pointed_at", "clothing", "worn_by", "shed", "garment", "speed",
})


def _reading_value(value):
    if isinstance(value, dict):
        parts = [f"{_reading_label(k)} {_reading_value(v)}"
                 for k, v in value.items() if _reading_value(v)]
        return ", ".join(parts)
    if isinstance(value, (list, tuple)):
        return ", ".join(s for s in (_reading_value(v) for v in value) if s)
    if isinstance(value, bool):
        return "yes" if value else "no"
    return " ".join(str(value if value is not None else "").split())


def _reading_label(key):
    return " ".join(str(key or "").replace("_", " ").split())


def thing_reading_text(state):
    """What a thing's own record says about it, as one clinical clause list.

    A THING EXAMINED TELLS YOU WHAT IT IS LIKE. The objects hand writes a
    thing's readings, its harm and its workings into `state` -- the prompt
    has required it since the detail clause, and nothing on the view path
    ever read the dict back: `_visible_things` renders a thing by its
    description and uses `state` only as a placement key. Measured, chat
    152 turns 4337-4338: the Doctor ran his hands over the console for two
    beats "checking what the scar cost her" and was told nothing, because
    the console had no record and, had it one, no renderer would have
    voiced it. The owner's 2026-09-19 ruling names this class -- an
    unanswered read is a bug, and the acceptance bar is that a thing
    examined closely tells you what it is like.

    Free-form on purpose. The keys are the hand's, so a console, a hull, a
    winch and a wound in a wall each carry whatever they have; this layer
    humanises a key, flattens a nested value and joins with semicolons, and
    never decides which keys matter. Empty when the record is silent.
    """
    if not isinstance(state, dict):
        return ""
    clauses = []
    for key, value in state.items():
        label = _reading_label(key)
        if not label or str(key) in _UNREADABLE_STATE_KEYS:
            continue
        text = _reading_value(value)
        if not text:
            continue
        clauses.append(f"{label}: {text}")
    return "; ".join(clauses)


def thing_reading_percepts(rows):
    """Standing readings off things this observer is reading, as
    ``[(label, readings, uid, channel[, asked])]`` -- admission already
    decided by `perception._things_read_by` (hands on it, or standing at its
    own station with light to see by), so a non-reader contributes nothing
    here by construction. ``asked`` marks a thing this observer's own act
    looked at or took into its hands this beat (`asked_this_beat`).

    `ambient`, like the rest of `room_content_percepts`' family: a standing
    fact of the room, re-rendered when it CHANGES and furniture when it does
    not -- the dedupe key is the reading itself, never the sentence."""
    out = []
    for row in rows or []:
        label, readings, uid, channel = row[:4]
        asked = bool(row[4]) if len(row) > 4 else False
        readings = str(readings or "").strip()
        label = _noun_phrase(label)
        if not readings or not label:
            continue
        template = ("thing_reads_touch" if channel == "touch"
                    else "thing_reads_sight")
        desc = _cap(_t(template, label=label, readings=readings))
        # A reading that already ends its sentence keeps its own stop and
        # the template's is dropped ("Tide: ebb, falling.." -- Saltmarsh
        # Crossing's loading slip, 2026-10-11; "。。" in Japanese alike).
        ends = linguistic("agents.common", "_SENTENCE_END_CHARS")
        if len(desc) > 1 and desc[-1] in ends and desc[-2] in ends:
            desc = desc[:-1]
        data = {"desc": desc}
        if asked:
            data["asked"] = True
        out.append(Percept(
            kind="ambient", channel=channel,
            data=data,
            salience=0.5,
            dedupe_key=standing_key("reading", (uid,), (readings,)),
        ))
    return out


def room_content_percepts(*groups):
    """Standing things in the observer's room that are not bodies: a crowd, a
    courier waiting by a door, a notice nailed to a post.

    Three world subsystems (`world/crowds.py`, `story/couriers.py`,
    `story/artifacts.py`) each publish a reading seam that has ALREADY decided
    what a bystander in that room takes in -- the figure and which door he
    makes for, never the message; that a bill hangs there, never its wording.
    Room scope is likewise theirs: every caller passes the observer's own
    room, so nothing here re-decides admission. What was missing was a percept
    to put it in, so all three delivered to nobody.

    `ambient`, because that is what these are: a standing feature of the room
    rather than an event, a body, or a sensation on this body.
    """
    out = []
    for entries in groups:
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            desc = " ".join(str(entry.get("what") or "").split())
            if not desc:
                continue
            if desc[-1:] not in ".!?":
                desc += "."
            # Keyed on the subject's own uid where it has one, so a crowd that
            # thins from a crush to a press is a CHANGED percept and re-renders
            # in a delta view, while the same crowd unchanged stays furniture.
            key = str(entry.get("uid") or entry.get("artifact_id") or "")
            # AND KEYED ON THE STATE, NEVER ON THE SENTENCE COMPOSED FROM IT.
            # A stable subject paired with prose content is the one
            # combination in this family that manufactures a false `changed`:
            # every re-rendering of an unchanged fact reads as an event, and
            # `leads_the_beat` promotes an event into the beat half, where
            # `_render_observed_events` numbers it as an obligation the
            # narrator must write a sentence about. Measured, chat 95: one
            # crowd whose band never left "a dozen or so" for sixteen turns
            # recorded `changed` seven times, because `describe` composes a
            # top-two-of-tally over a membership that walks its errands --
            # five spellings of one unchanged fact.
            #
            # A seam that publishes no state (a courier, a posted notice) has
            # nothing else to be identified by and keeps the description as
            # its content; the tag differs so an old ledger's prose-hashed
            # key reads as a subject never held -- first sight, which
            # `leads_the_beat` refuses for an ambient -- rather than as a
            # claim that something moved (`standing_verdicts`' own
            # degradation rule).
            #
            # A THING IN THE OBSERVER'S OWN KEEPING IS TOLD AGAIN WHEREVER IT
            # IS CARRIED. Its row names the room it is kept in (`kept_in`,
            # `perception._visible_things`), and that room is part of WHICH
            # standing fact this is: the plate in a hand in the kitchen and
            # the plate in that hand on the landing are facts of two rooms,
            # as the kitchen's table and the landing's rail are. Keyed on the
            # thing alone it read `unchanged` across every move, and a delta
            # view dropped it for the whole walk: chat 177 told the player
            # "You are holding an empty small plate." and "You are carrying
            # the mug." on turn 12 and never again through turn 21, up the
            # stairs and into the second room, and the next beat gave the
            # dishes a floor and a bed to lie on. A room it has not been kept
            # in is a subject this observer has not held -- first sight, so it
            # is re-told as background beside the rest of the room, never as
            # an event (`leads_the_beat`); within one room it stays furniture,
            # and a change of grip there still re-renders as a change.
            kept_in = str(entry.get("kept_in") or "").strip()
            subject = (key, kept_in) if kept_in else (key,)
            state = entry.get("state")
            if isinstance(state, (list, tuple)) and any(
                    str(v or "").strip() for v in state):
                dedupe = standing_key("content_state", subject,
                                      tuple(str(v or "") for v in state))
            else:
                dedupe = standing_key("content", subject, (desc,))
            out.append(Percept(
                kind="ambient", channel="sight",
                data={"desc": desc},
                salience=0.35,
                dedupe_key=dedupe,
            ))
    return out


def chatter_percepts(entries):
    """The room's talk: a hum band as ground, at most one fragment as figure.

    Both arrive from `common.chatter_for_room`, which — like the three
    `room_content_percepts` seams — has ALREADY decided what a bystander in
    that room takes in: the hum is a band over the last window's charter
    acts, and the fragment is the who-asked-whom-about-whom triple with its
    labels already licensed by recognition. Nothing here re-decides
    admission; this is only the delivery.

    `hearing`, because that is the channel a murmur rides — prose has one
    channel, so anything rendered verbatim IS foreground, which is why the
    fragment count upstream is zero or one (the walla rule,
    DESIGN_BACKGROUND_PRESENTATION §A1). The structured triple rides `data`
    beside the composed clause so the projection stays auditable: the
    engine holds no sentence the crowd said, so none can be restated.

    Dedupe: the hum keys on its band, so an unchanged murmur is standing
    furniture and only a change in loudness re-renders; the fragment keys on
    the act's identity, so the same act never surfaces twice while its
    window stands.
    """
    out = []
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        desc = " ".join(str(entry.get("what") or "").split())
        if not desc:
            continue
        if desc[-1:] not in ".!?":
            desc += "."
        if entry.get("kind") == "fragment":
            data = {"desc": desc}
            for field in ("speaker_label", "act", "other_label",
                          "subject_label"):
                data[field] = str(entry.get(field) or "")
            key = str(entry.get("uid") or "")
            out.append(Percept(
                kind="ambient", channel="hearing", data=data,
                salience=0.45,
                dedupe_key=standing_key("chatter", (key,), (key,)),
            ))
        else:
            band = str(entry.get("band") or "")
            out.append(Percept(
                kind="ambient", channel="hearing",
                data={"desc": desc, "hum": band},
                salience=0.3,
                dedupe_key=standing_key("hum", (entry.get("uid"),),
                                        (band,)),
            ))
    return out


def micro_round_percept(text):
    """One interaction-loop micro-round delivery, as a percept.

    The micro loop renders its own prose and gated it with `_delivery_ok` when
    the round ran, so admission is decided upstream and nothing is re-decided
    here. What matters is that it goes in the SAME list as everything else:
    appended to the finished view instead, it arrived after the tripwires had
    run and its observation atom had to be hand-written -- the one atom in the
    payload whose channel, intensity and self-direction were asserted rather
    than derived, in a projection whose entire safety argument is that it is
    derived (`observations_from_render`).

    `mixed`, and said plainly: the loop hands over prose, not an IR, so the
    channel genuinely is not known. An honest "several, or unclear" beats a
    fabricated "sight". The residual that would fix it properly -- the micro
    loop emitting percepts of its own -- is design_notes/13-composer-build.md's,
    and lives in `agents/loops.py`.
    """
    text = " ".join(str(text or "").split())
    if not text:
        return None
    return Percept(
        kind="ambient", channel="mixed",
        data={"desc": text},
        salience=0.4,
        dedupe_key=standing_key("micro", (text,), (text,)),
    )


def micro_round_percepts(deliveries):
    """ONE PERCEPT PER DELIVERED LINE. `delivered_views[observer]` is a LIST.

    `micro_round_percept` above takes one line, and the outcome composer
    handed it the whole list. `str(["a", "b"])` does not fail -- it renders
    the Python repr -- so the bracket, the quotes and the comma went into the
    composed view verbatim, and from there into the observations projected
    off that view and into the episode minted from it. Measured over chat 98:
    68 of the 142 stored character views carry a `['...']` span, on 24 of the
    38 turns; the composer's own dialogue tripwire caught four of them and
    said so ("engine defect, view delivered as composed") while the view
    shipped anyway.

    The class is a shape mismatch at a seam, not a rendering bug, so it is
    fixed by naming the shape: a delivery is one line, a round delivers
    several, and the caller passes what it has. A bare string still works --
    it is one delivery.
    """
    if deliveries is None:
        return []
    if isinstance(deliveries, str):
        deliveries = [deliveries]
    out = []
    for line in deliveries:
        percept = micro_round_percept(line)
        if percept is not None:
            out.append(percept)
    return out
