"""The place as standing sensory state: the room, where light and sound fall,
authored and distant sounds, scent, a walk underway, the weather by
sight/skin/ear, thunder, and felt shakes.

Carved verbatim from `agents/composer.py` on 2026-11-01;
`agents/composer.py` is now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import logging
from story.provenance_text import strip_engine_provenance
from world.spatial import _sense_channel
logger = logging.getLogger("agents.composer")

from agents.composer_common import (
    CHANNELS,
    Percept,
    _cap,
    _en,
    _join_clauses,
    _noun_phrase,
    _safe_renderer,
    _strip_sentence_ends,
    _subject_prefix,
    _t,
    standing_key,
)
from agents.composer_standing import WEATHER_SOUND_TAG, WIND_SOUND_TAG


# --------------------------------------------------------------------------
# Layer A -- standing-state percepts
# --------------------------------------------------------------------------

#: The two fields' closed vocabularies, as the composer knows them: a shape
#: row whose level is not one of these is dropped, so no other word can
#: reach a template. Light's is `spatial_light.LIGHT_LEVELS`; sound's is
#: `spatial_sound_field.NOISE_WORDS`, both spelled here rather than imported
#: because the composer reads no scene module.
LIGHT_SHAPE_LEVELS = ("bright", "lit", "dim", "dark")
SOUND_SHAPE_LEVELS = ("drowned", "din", "quiet")


def _clean_shape(shape, levels):
    """A field shape as the templates will read it, or None. Groups keep
    only levels in the closed set and non-empty descriptions; `sources`
    and `openings` are labels the observer already has; `self` is one of
    the levels or None. Nothing numeric survives -- there is nothing
    numeric to keep."""
    if not isinstance(shape, dict):
        return None
    groups = []
    for group in shape.get("groups") or ():
        if not isinstance(group, dict):
            continue
        level = str(group.get("level") or "")
        items = [str(i).strip() for i in (group.get("items") or ())
                 if str(i or "").strip()]
        if level in levels and items:
            groups.append({"level": level, "items": items})
    sources = [str(s).strip() for s in (shape.get("sources") or ())
               if str(s or "").strip()]
    openings = [str(o).strip() for o in (shape.get("openings") or ())
                if str(o or "").strip()]
    # What a coned source in view is pointed at (D5). Descriptions of
    # anchors the field has already graded, in the order the field put them
    # -- nearest the beam first -- so ordering is data and not a rendering
    # choice. Empty for a field with no aimed source, and for `sound_shape`,
    # which has no cone at all.
    aimed = [str(a).strip() for a in (shape.get("aimed") or ())
             if str(a or "").strip()]
    self_word = shape.get("self")
    self_word = self_word if self_word in levels else None
    # AN EVEN ROOM'S ONE WORD (`spatial_sound_field.sound_fill`, § 17): a
    # steady sound filling the room at one level, named by its sources.
    even = shape.get("even")
    even = even if even in levels and (sources or openings) else None
    if not groups and self_word is None and even is None:
        return None
    return {"groups": groups, "sources": sources, "openings": openings,
            "self": self_word,
            # No beam, no key (D5): every reader takes absence as "nothing aimed".
            **({"aimed": aimed} if aimed else {}),
            # No even word, no key: an uneven shape hashes as it always did.
            **({"even": even} if even else {})}


def _shape_signature(shape):
    if not shape:
        return ""
    aimed = [a for a in (shape.get("aimed") or ()) if a]
    return "|".join(
        ["%s=%s" % (g["level"], ",".join(g["items"])) for g in shape["groups"]]
        + ["from=" + ",".join(shape["sources"] + shape["openings"]),
           "self=%s" % (shape["self"] or "")]
        # SWINGING THE BEAM IS NEWS. The signature is the dedupe key of both
        # the `environment` percept and the `soundscape` percept: leave the
        # aim out of it and a lamp moved from one thing to another leaves
        # the room `unchanged`, so the sentence naming the new thing is
        # suppressed as furniture (D5).
        #
        # APPENDED, AND ONLY WHEN THERE IS A BEAM. An `aimed=` segment
        # emitted unconditionally rewrites the stored key of every shape
        # that never had a beam -- measured on a beam-less sound shape,
        # `din=a generator|from=a generator|self=din` became
        # `din=a generator|from=a generator|aimed=|self=din` -- so every
        # room description and every soundscape in every live chat would
        # re-announce itself as news on the first beat after this landed.
        # A shape with no beam hashes byte for byte to what it hashed
        # before.
        + (["aimed=" + ",".join(aimed)] if aimed else [])
        # ...and the even room's word the same way (§ 17): appended only
        # when there is one, so every uneven shape keeps its stored key, and
        # a room that fills up to one word or falls to another is `changed`.
        + (["even=" + str(shape["even"])] if shape.get("even") else []))


def environment_percept(room_id, room_name, room_notes="", light="",
                        features=None, openings=None, light_shape=None):
    """The room as standing state -- or None when the observer has no
    resolvable room. A mind in unloaded space perceives NOTHING here; the
    old path fabricated "You are in an unspecified area." for it, which
    became 812 identical memory rows (97.3% collision). No room, no
    percept, no view sentence, no episode.

    `light_shape` is where the light FALLS, for a room the light field
    finds uneven (`world.spatial_light_field.light_shape`): visible anchors
    grouped by the four light words, the sources or openings the light comes
    from, and the observer's own standing. Absent -- an even room, no
    geometry, no station -- the percept and its sentence are byte-identical
    to what they always were. Present, the renderer says where the light
    falls INSTEAD of the flat `light_dim`/`light_dark` sentence, which spoke
    for the whole room.

    `features` is what THIS observer's eyes reach of the room's furniture
    (`world.spatial_fov.feature_visibility`, already subtracted by cone and
    line): rows of {desc, tier, side, peripheral}, near to far. Absent or
    empty, the percept is byte-identical to the one it always was -- a room
    with no geometry authored on its anchors composes exactly as before.

    `openings` is the room's BOUNDARY, on the same terms: rows of
    {desc, room_name, room_notes, dark, features} for every way out this
    observer can see, each carrying what sight reaches past it and nothing
    more (`_render_openings`, and `perception._visible_openings` for the
    admission). A boundary belongs to the room's standing state exactly as
    its furniture does, which is why it rides this percept rather than
    becoming a kind of its own -- and why it joins the dedupe signature
    below, so a door that opens is a room that CHANGED for this observer and
    a door that stays shut is furniture.
    """
    if not room_id or not str(room_name or "").strip() \
            or str(room_name).strip().casefold() == "an unspecified area":
        return None
    rows = []
    for row in features or ():
        if not isinstance(row, dict) or not str(row.get("desc") or "").strip():
            continue
        rows.append({
            "desc": str(row.get("desc")).strip(),
            "tier": str(row.get("tier") or ""),
            "side": row.get("side") if row.get("side") in ("left", "right")
            else None,
            "peripheral": bool(row.get("peripheral")),
        })
    # THE DELIVERY FLOOR for engine provenance. Room notes are the one field in
    # a view whose text the ENGINE may have written about itself -- a
    # synthesised description can carry the reason it was synthesised, and that
    # reason is bookkeeping, not a property of the room. Measured live (chat 95
    # beat 7): "You are in Harbour Office. generated because no candidate
    # described this location." reached a character agent as world text. The
    # signal is kept where provenance belongs (story/provenance_text); what a
    # mind receives is the place. Stripped HERE, at percept construction, so
    # the render and `observations_from_render` cannot disagree about it.
    room_notes = strip_engine_provenance(room_notes)
    light = str(light or "")
    # Provenance stripped on the far side of a threshold for the same reason
    # it is stripped for the room underfoot, and in the same place: a
    # synthesised description can carry the reason it was synthesised, and
    # that reason is bookkeeping rather than a property of the room.
    ways = []
    for way in openings or ():
        if not isinstance(way, dict) or not str(way.get("desc") or "").strip():
            continue
        way = dict(way)
        way["room_notes"] = strip_engine_provenance(way.get("room_notes"))
        ways.append(way)
    data = {"room_id": room_id, "room_name": room_name,
            "room_notes": room_notes or "", "light": light}
    if rows:
        data["features"] = rows
    if ways:
        data["openings"] = ways
    shape = _clean_shape(light_shape, LIGHT_SHAPE_LEVELS)
    if shape:
        data["light_shape"] = shape
    # The visible set is part of the CONTENT: turning to face the hearth
    # changes what this observer has of the room, and the ledger must read
    # that as the room changed for them, not as the same fact said again.
    feature_sig = "|".join(
        f"{r['desc']}:{r['tier']}:{r['side'] or ''}:{int(r['peripheral'])}"
        for r in rows)
    opening_sig = "|".join(
        "%s>%s:%d:%s" % (w["desc"], w.get("room_name") or "",
                         int(bool(w.get("dark"))),
                         ",".join(str((f or {}).get("desc") or "")
                                  for f in (w.get("features") or ())))
        for w in ways)
    return Percept(
        kind="environment", channel="sight",
        data=data,
        salience=0.2,
        dedupe_key=standing_key(
            "env", (room_id,),
            (room_name, room_notes, light)
            + ((feature_sig,) if rows else ())
            + ((opening_sig,) if ways else ())
            + ((_shape_signature(shape),) if shape else ())),
    )


def soundscape_percept(shape, room_id):
    """Where the sound is, as one standing HEARING percept -- or None when
    the sound field found the room even, or has nothing to say
    (`world.spatial_sound_field.sound_shape`). An `ambient` kind, because
    that is what it is: a standing feature of the room and not a body, an
    event or a sensation on this body. The dedupe key carries the shape, so
    a generator that starts or a door that opens is a room that CHANGED for
    this observer and an unchanged din is furniture."""
    shape = _clean_shape(shape, SOUND_SHAPE_LEVELS)
    if not shape or not room_id:
        return None
    return Percept(
        kind="ambient", channel="hearing",
        data={"soundscape": shape},
        salience=0.3,
        dedupe_key=standing_key("soundscape", (room_id,),
                                (_shape_signature(shape),)),
    )


def sound_ceased_percept(room_id, *, still_sounding=False):
    """The room's sound STOPPING, as one standing hearing percept.

    SILENCE WHERE THERE WAS SOUND (review 2026-09-07 D3). A room the sound
    field grades unevenly composes a `soundscape_percept`; the beat its one
    source stops, the field goes even and the percept is simply not built --
    so the observer's ledger holds a key nothing renews and nothing anywhere
    says the humming stopped. Measured in the descent run: the PLAYER wrote
    "nothing hummed" themselves, because the page never did. A multi-source
    room is already covered -- one source of several stopping moves the
    shape, which moves the content hash, which is `changed` -- and this is
    the single-source case that hash cannot see, because the key it needs to
    compare against is the one that vanished.

    THE SAME SUBJECT AS THE SOUND IT ENDS, deliberately: `standing_key`
    hashes subject and content apart, so this key threads the room's sound
    ledger rather than opening a second one. The sound coming back is
    `changed` against this, the silence continuing is `unchanged` (said
    once, not every beat), and an observer who was never delivered the sound
    gets `first` -- which `unheard_ceasing` drops, because a silence is only
    news to an ear that had the noise.

    `still_sounding` is the room that went quiet with its source still going
    (`spatial_sound_field.room_still_sounding`): the noise DIED DOWN, which is
    not the noise stopping -- a TARDIS rotor whose din "gentled into a hum"
    in flight was told to the page as a stop (chat 157 turn 4482). Same
    subject, its own content, so the hum stopping later is news again.
    """
    if not room_id:
        return None
    data = {"ceased": True}
    if still_sounding:
        data["subsided"] = True
    return Percept(
        kind="ambient", channel="hearing",
        data=data,
        salience=0.4,
        dedupe_key=standing_key("soundscape", (room_id,),
                                ("subsided" if still_sounding else "ceased",)),
    )


def _shape_clauses(shape, prefix, levels):
    return [_en(prefix + level,
                items=_join_clauses([_noun_phrase(i) for i in group["items"]]))
            for group in shape["groups"] for level in (group["level"],)
            if level in levels]


def aim_worth_naming(shape):
    """The beam's anchors, when saying them adds something -- else [].

    WHERE THE BEAM LANDS (D5). A sentence separate from the room's grading,
    because it answers a different question: the grading says how much light
    is where, and this says what the light is being POINTED at -- the thing
    a reader looks at first and the page never named (chat 117 beats 59-62,
    five beats of an aimed hand lamp).

    It speaks only where it names a set THE GRADING DID NOT ALREADY NAME BY
    ITSELF. Two ways it fails to: a beam covering every anchor in view has
    singled nothing out, and a beam whose anchors are exactly the brightest
    group is the sentence before it in other words ("The light from the hand
    lamp falls on a stack of crates. The beam is on a stack of crates.").
    Where a second source does the grading -- an overhead strip lighting the
    room while the hand lamp picks one thing out of it -- the two sets
    differ and the aim is the news of the beat.

    Here rather than in either renderer because it is a decision about the
    aim's information content, not about a language: two copies of it would
    be two answers to "is this worth a sentence", free to drift, and every
    pack's adapter is a second renderer by construction.
    """
    shape = _clean_shape(shape, LIGHT_SHAPE_LEVELS)
    if not shape:
        return []
    aimed = shape.get("aimed") or []
    graded = {item for group in shape["groups"] for item in group["items"]}
    brightest = set(shape["groups"][0]["items"]) if shape["groups"] else set()
    if not aimed or len(set(aimed)) >= len(graded) or set(aimed) == brightest:
        return []
    return list(aimed)


def render_light_shape(shape):
    """The light's shape as one or two English sentences, from templates over
    the closed set alone: the origin (the sources in view and the openings
    the light comes through, or 'the light' when neither is in view), the
    visible anchors grouped bright to dark, what a coned source in view is
    pointed at, and where the observer stands. No number, cell or sector
    reaches the page -- the shape carries none."""
    shape = _clean_shape(shape, LIGHT_SHAPE_LEVELS)
    if not shape:
        return ""
    parts = []
    clauses = _shape_clauses(shape, "light_at_", LIGHT_SHAPE_LEVELS)
    if clauses:
        # The sources are entity NAMES and the openings authored descs;
        # neither carries the pack's determiner ("The light from brass hand
        # lamp and the opening..." -- F52's last unfixed line, run
        # 2026-09-05C `solitude` turn 5).
        froms = [_noun_phrase(f) for f in shape["sources"] + shape["openings"]]
        origin = (_en("light_origin", items=_join_clauses(froms)) if froms
                  else _en("light_origin_none"))
        parts.append(_cap(_en("light_shape", origin=origin,
                              clauses=_join_clauses(clauses))))
    # WHERE THE BEAM LANDS (D5). A separate sentence from the room's
    # grading, because it answers a different question: the grading says how
    # much light is where, and this says what the light is being POINTED at
    # -- the thing a reader looks at first and the page never named (chat
    # 117 beats 59-62, five beats of an aimed hand lamp).
    #
    aimed = aim_worth_naming(shape)
    if aimed:
        parts.append(_cap(_en("light_aimed", items=_join_clauses(
            [_noun_phrase(a) for a in aimed]))))
    if shape["self"]:
        parts.append(_en("light_self_" + shape["self"]))
    return " ".join(parts)


def render_sound_shape(shape):
    """The sound's shape, the same way: the origin (entities heard in this
    room, and 'beyond <opening>' for one heard through a doorway), the
    visible anchors grouped loud to quiet, and where the observer stands."""
    shape = _clean_shape(shape, SOUND_SHAPE_LEVELS)
    if not shape:
        return ""
    parts = []
    froms = [_noun_phrase(s) for s in shape["sources"]] + [
        _en("sound_beyond_opening", opening=_noun_phrase(o))
        for o in shape["openings"]]
    origin = (_en("sound_origin", items=_join_clauses(froms)) if froms
              else _en("sound_origin_none"))
    if shape.get("even"):
        # A STEADY SOUND FILLING THE ROOM AT ONE WORD (§ 17): there is no
        # "where" to grade, so the sentence says what is heard, all through
        # the room, at the one level the room carries.
        return _cap(_en("sound_even_" + shape["even"], origin=origin))
    clauses = _shape_clauses(shape, "sound_at_", SOUND_SHAPE_LEVELS)
    if clauses:
        parts.append(_cap(_en("sound_shape", origin=origin,
                              clauses=_join_clauses(clauses))))
    if shape["self"]:
        parts.append(_en("sound_self_" + shape["self"]))
    return " ".join(parts)


def field_shape_sentence(kind, shape, *, language=None):
    """One field shape (`light` or `sound`) as the story language's
    sentence -- the seam the Director's sight digest reads, so the Director
    is handed exactly the sentence the observer's view carries and nothing
    the view does not. The pack's adapter renders it when it can; English
    otherwise, as `render_view` falls back."""
    if not shape:
        return ""
    selected = _safe_renderer(language)
    if selected is not None and hasattr(selected, "field_shape_sentence"):
        try:
            return str(selected.field_shape_sentence(kind, shape) or "")
        except Exception:
            logger.exception("language renderer failed; using English wording")
    return render_light_shape(shape) if kind == "light" else render_sound_shape(shape)


#: Engine sense channel (world.spatial's vocabulary) -> percept channel.
#: The two names for the olfactory channel are a genuine split rather than a
#: synonym: `world/spatial_senses.py` grades a `scent`, and a percept rides
#: the `smell` a mind receives.
_ENGINE_CHANNEL_PERCEPT = {"sight": "sight", "hearing": "hearing",
                           "scent": "smell"}


def _ambient_channel(event):
    """Which channel an authored sensory event rides.

    THE PROMPT AND THE READER NAMED DIFFERENT FIELDS. `director_establish`
    asks for `sensory_events:[{kind,description,source_room,...}]` in both
    packs; this function read `channel` alone, so all 199 stored events in the
    live corpus fell to `mixed` and the smell channel had no producer at all.
    `channel` still wins where something emits it -- the reader's own spelling
    is not withdrawn -- and `kind` is read because that is what is written.

    A word this engine has no channel for stays `mixed`. A fiction may invent
    a sense (`spiritual_pressure` is a real stored row) and inventing one must
    cost the event nothing.
    """
    for field in ("channel", "kind", "sense"):
        raw = str(event.get(field) or "").strip()
        if not raw:
            continue
        if raw.casefold() in CHANNELS:
            return raw.casefold()
        mapped = _ENGINE_CHANNEL_PERCEPT.get(_sense_channel(raw) or "")
        if mapped:
            return mapped
    return "mixed"


def ambient_percepts(sensory_events, observer_room, *, order_key=None,
                     after=None):
    """Authored opening sensory events, filtered by room scope. An event
    naming a room is admitted only to observers in that room; a roomless
    event is scene ambience.

    `after` (wave B2, one of `spatial_sound_field.SOUND_AFTER_WORDS`) says
    the sound reached this observer that long after the SIGHT of what made
    it -- a source seen far off -- and the sentence says so; the caller
    orders it after the act it saw (`perception`'s outcome pass).

    `order_key` decides which HALF of the view these land in, and the
    caller decides because the two callers mean different things. The
    establish stage's authored ambience is scene-setting -- the air of a
    place, true before the beat and after it -- and belongs in standing
    state, which is what an absent key gives it (`render_view` splits on
    `order_key is None`). A BEAT'S OWN SOUND EVENT IS NOT THAT.

    `spatial_sound_field`'s own note on the channel is explicit: "a noise
    is a thing that happened in this window and never a standing fact",
    and the record is beat-scoped so hard that "the beat number IS the
    lifetime". Minted without a key anyway, every such sound landed in
    `present_scene`, which the narrator sheet says in as many words
    "carries no obligation" -- so the loudest thing in a beat was as
    optional as the colour of the floor.

    Measured live, chat 117 turn 65. A carbonic stalker moved in the room
    the cast were kneeling in; perception delivered its voice correctly --
    "a slow, rhythmic siphon-vent hiss and the soft drag of leathery
    footfalls, nearer with every hunted breath" -- as `standing: True`, so
    it never entered the numbered deliveries, and the prose recorded that
    nothing was moving.
    """
    out = []
    for idx, event in enumerate(sensory_events or []):
        if not isinstance(event, dict):
            continue
        room = str(event.get("room") or event.get("room_id")
                   or event.get("source_room") or "")
        # FAIL CLOSED on the one input the scope cannot judge. An observer
        # with NO room passed `room and observer_room and ...` and was handed
        # every room's sounds -- a cast member attached but not placed heard
        # the hiss behind the vault door (audit agents_composer F3,
        # 2026-11-01) -- while `environment_percept` gives the same mind
        # nothing. A roomless event is scene ambience and reaches everyone.
        if room and room != str(observer_room or ""):
            continue
        # `detail` FIRST, because it is the canonical key and the other
        # three are not. `spatial_sound_field.normalize_sensory_event` holds
        # the shape -- "{kind, room, level | db, source, detail} -- the
        # note's shape, and a closed set of keys" -- and it FOLDS `desc` and
        # `description` INTO `detail` on the way in. So every stored event
        # carries its text under `detail` and this reader checked three
        # spellings that normalisation had already removed.
        #
        # Its own warning, one module over, is what happened here read from
        # the other end: "a hand that writes prose into a key nobody reads
        # writes it into nothing." The writer was canonical; the READER
        # drifted.
        #
        # Measured live, chat 117 turn 65. A carbonic stalker followed the
        # cast through a jammed pressure door and stood in the room with
        # them, and the beat's own scene carried its voice --
        # {"kind": "sound", "room": <their room>, "level": "loud",
        # "detail": "a slow, rhythmic siphon-vent hiss and the soft drag of
        # leathery footfalls, nearer with every hunted breath"}. The player
        # received no hearing percept at all. Sight was legitimately dark;
        # this was the channel that should have carried it, and it dropped
        # the event for having its text in the one field the format
        # guarantees.
        desc = str(event.get("detail") or event.get("desc")
                   or event.get("description") or event.get("text")
                   or "").strip()
        if not desc:
            continue
        channel = _ambient_channel(event)
        if event.get("echo") and channel != "sight":
            # The story's own echo clause, after the story's own stops: the
            # English one was appended in every pack -- 「鐘の音が鳴り響く。,
            # and the place gives it back」 (audit agents_composer F9).
            desc = _strip_sentence_ends(desc) + _t("sound_echo")
        if after in ("moment", "seconds") and channel != "sight":
            from language_runtime import compositor_text
            desc = compositor_text("sound_after_sight_" + after,
                                   desc=desc.rstrip(".!?。"))
        out.append(Percept(
            kind="ambient", channel=channel, data={"desc": desc},
            salience=0.4,
            **({"order_key": order_key + idx} if order_key is not None else {}),
            dedupe_key=standing_key("ambient", (desc,), (desc,)),
        ))
    return out


#: What a distant sound is allowed to be. `distant_sounds` returns
#: `{kind, level, db, character, bearing}` and only three of those reach a
#: percept: the margin over this listener's own noise floor, the DIRECTION it
#: arrived from, and what it sounded LIKE. No room, no name, no words -- and
#: the subtraction is done by naming what is kept rather than by dropping
#: what is not, so a field added upstream cannot ride in behind it
#: (DESIGN_SOUND_DECIBELS.md § 3).
DISTANT_SOUND_LEVELS = ("faint", "plain", "overwhelming")


def distant_sound_percepts(records):
    """Sounds from beyond the near field, as percepts.

    A bang two rooms away is a HEARING percept like any other: it goes in
    the same list, through the same renderer and the same dedupe, so nothing
    downstream has to know the far field exists. What makes it different is
    what it may say, and that is decided here -- a bearing and a character,
    never a sentence and never a place.

    A record the far field could give no bearing for is DROPPED. The three
    templates all say which way the sound came from, and a distant noise
    with no direction is a fact this observer has no frame for; silence is
    the honest rendering of that, and it subtracts.
    """
    out = []
    for record in records or ():
        if not isinstance(record, dict):
            continue
        level = str(record.get("level") or "")
        if level not in DISTANT_SOUND_LEVELS:
            continue
        bearing = record.get("bearing")
        where = " ".join(str((bearing or {}).get("phrase") or "").split())
        if not where:
            continue
        character = " ".join(str(record.get("character") or "").split())
        out.append(Percept(
            kind="ambient", channel="hearing",
            data={"distant": {"level": level, "where": where,
                              "character": character}},
            salience=0.45,
            # A sound is over when the beat is, so the key carries the beat's
            # own content: the same bang louder, or from another quarter, is
            # news again rather than the same standing fact.
            dedupe_key=standing_key("distant_sound", (where,),
                                    (level, character)),
        ))
    return out


def render_distant_sound(distant, *, episode=False):
    """One distant sound as the reader meets it: how loud against this
    room's own quiet, which way, and what it sounded like.

    `episode` is the memory's wording of a sound with no character of its
    own: "a sound you cannot place" puts its subject inside a relative
    clause, which the second-to-first swap cannot see is a subject, so the
    pack carries the first person ("a sound I cannot place")."""
    distant = distant if isinstance(distant, dict) else {}
    level = str(distant.get("level") or "")
    where = str(distant.get("where") or "")
    if level not in DISTANT_SOUND_LEVELS or not where:
        return ""
    character = (str(distant.get("character") or "").strip()
                 or _en("sound_distant_character_none"
                        + ("_episode" if episode else "")))
    return _cap(_en("sound_distant_" + level, where=where,
                    character=character))


#: A scent that arrives without its source. `muffled` is the graded rung
#: `scent_level` has always returned and nothing downstream could act on.
_SCENT_FIDELITY = {"full": "full", "muffled": "degraded"}


def scent_percepts(sources):
    """Standing smells reaching one observer, already graded by the caller.

    Input: ``[{"key", "label", "scent", "level", "attributed"}]`` -- `level`
    is `scent_level`'s own verdict after the observer's card acuity, and
    `attributed` says whether this observer has a SECOND channel to the
    source (they can see the body the smell belongs to).

    THE GRADE IS ACTED ON, NOT RECORDED. A muffled scent is delivered
    unattributed, because what a half-open door withholds is not the smell --
    the material still crosses -- it is which body the smell belongs to. That
    is a real subtraction and a structural one: no string is mangled, a field
    is withheld. It also settles the disguise question in the only direction
    the firewall's own statement points. A scent percept carries a MATERIAL,
    never a NAME: the label is whatever this observer's display map already
    earned for that body, so a disguise that conceals identity yields the
    stranger's descriptor here exactly as it does for presence and pose. A
    mind may then conclude from its own memories that this is the smell of
    someone it knows -- inference is the product, and that inference is
    defeasible, since two bodies can wear one perfume.

    `key` is folded into the dedupe key only; canonical names never ride a
    Percept.
    """
    out = []
    for source in sources or []:
        if not isinstance(source, dict):
            continue
        scent = " ".join(str(source.get("scent") or "").split())[:160]
        level = str(source.get("level") or "none")
        fidelity = _SCENT_FIDELITY.get(level)
        if not scent or fidelity is None:
            continue
        attributed = bool(source.get("attributed")) and level == "full"
        label = str(source.get("label") or "").strip() if attributed else ""
        out.append(Percept(
            kind="scent", channel="smell",
            source_label=label if attributed else "",
            fidelity=fidelity,
            data={"scent": scent, "level": level,
                  "attributed": bool(label)},
            salience=0.35,
            # THE LABEL IS NOT HASHED. It says whose smell this is, which is
            # a fact about this observer's recognition of the source and not
            # about the smell: learning whose a fact is is not a change to
            # the fact. Measured, chat 95 turn 9 -- a body the player had
            # been smelling for nine beats was recognised, the label went
            # from a stranger descriptor to a name, the authored scent string
            # was byte-identical, and the moved key re-declared the smell as
            # this beat's news. `level` stays: a smell that arrives muffled
            # is delivered differently, which is a change in the percept
            # rather than in the reader of it. New tag, so an old ledger's
            # label-hashed key degrades to first sight instead of to
            # `changed` (`standing_verdicts`).
            dedupe_key=standing_key(
                "scent_state", (source.get("key"),), (scent, level)),
        ))
    return out


def walk_underway_percepts(walk):
    """A walk this body declared and has not finished: where it has got to
    and where it is still going, in the pack's words (`perception.
    _walk_underway`). One line, the walker's own knowledge of its body."""
    from language_runtime import compositor_text
    if not isinstance(walk, dict) or not walk.get("to"):
        return []
    text = compositor_text("walk_underway", to=walk["to"], at=walk.get("at") or "")
    return [Percept(kind="ambient", channel="interoception", data={"desc": text},
                    dedupe_key=standing_key("walk_underway", (walk["to"],), (walk.get("at") or "",)))]


def weather_percepts(reach):
    """What the sky is doing, to a body that can tell -- sight and skin.

    `reach` is one `world.weather.weather_for_room(scene, room, subject)`
    answer, which had ALREADY decided every question this needs and was read by
    nobody with a mind. Measured 2026-09-20: `composer.py` contained the word
    "weather" zero times, `perception.py` once in a comment, and
    `agents/character.py` and `agents/common.py` not at all. The record carries
    sky, precipitation, intensity, wind and temperature; the Director gets it,
    `spatial_light` dims a room with it, `spatial_sound_field` adds it to the
    noise floor and `dressing/ambience` paints it. A character standing in a
    freezing thundersnow gale was told that the room was dim and that it was
    loud. Nobody was ever told it was snowing.

    TWO PERCEPTS, BECAUSE THE CHANNELS FAIL SEPARATELY -- the seam's own words:
    "a cellar under a downpour sees nothing, feels nothing and may still HEAR
    it". Sight carries what the sky is doing and is bounded by
    `weather_visible`/`visible_reach`, so from under cover the view says the
    weather is beyond it rather than on it. Skin carries what is actually
    touching this body: `falls_on_you` and `wind_reaches`, plus the temperature
    of the air a body standing in it is breathing. Hearing is NOT here --
    `spatial_sound_field` already folds rain and wind into the soundscape, and a
    second voice for one fact could only disagree with the first -- save the
    one sound of the sky no field holds: its thunder, told after its flash
    (`_storm_percepts`, wave B2).

    Names are reproduced, never interpreted: `sky`, `precipitation`, `wind` and
    `temperature` are authored free text this engine does not own, so they are
    spliced as written. Nothing numeric reaches the page -- an intensity word, a
    `visible_reach` fraction and a `gain` are the engine's bookkeeping, and a
    bystander has no access to any of them.
    """
    reach = reach if isinstance(reach, dict) else {}
    if not reach:
        return []
    out = []
    # WHAT IS FALLING, at the strength the engine holds a word for. `intensity`
    # is a closed engine vocabulary (light|moderate|heavy) rather than a number,
    # and the difference between light and heavy snow is the whole of what a body
    # standing in it has to say about it. Skipped when there is nothing falling
    # for it to qualify.
    falling = ""
    if str(reach.get("precipitation") or "").strip():
        _fall = str(reach["precipitation"]).strip()
        _how = str(reach.get("intensity") or "").strip()
        # MODERATE IS THE UNMARKED CASE AND IS NOT RENDERED. `normalize_weather`
        # returns `intensity: "moderate"` for a precipitation nobody graded, so
        # putting the word on the page states a thing no author said -- the same
        # rule that keeps a derived default out of every other view. Light and
        # heavy are marked, and both are what a body would actually remark on.
        falling = _noun_phrase(
            _en("weather_falling", intensity=_how, what=_fall)
            if _how in ("light", "heavy") else _fall)
    sky = str(reach.get("sky") or "").strip()
    wind = str(reach.get("wind") or "").strip()
    temperature = str(reach.get("temperature") or "").strip()
    # --- What the eyes have. Bounded by the seam, never re-decided here.
    if reach.get("weather_visible"):
        what = falling or (_noun_phrase(sky) if sky else "")
        if what:
            if float(reach.get("visible_reach") or 0.0) < 1.0:
                desc = _cap(_en("weather_beyond", what=what))
            elif falling and sky:
                desc = _cap(_en("weather_overhead", what=what, sky=sky))
            else:
                desc = _cap(_en("weather_overhead_plain", what=what))
            out.append(Percept(
                kind="ambient", channel="sight", data={"desc": desc},
                salience=0.4,
                # The STATE, never the sentence: a sky that holds re-renders as
                # furniture and a sky that turns is news, which is the rule
                # `room_content_percepts` states for this whole family.
                dedupe_key=standing_key(
                    "weather_sight", ("sky",),
                    (sky, str(reach.get("precipitation") or ""),
                     str(reach.get("intensity") or ""),
                     "%.2f" % float(reach.get("visible_reach") or 0.0))),
            ))
    # --- What the skin has. Only what is touching THIS body.
    clauses = []
    if reach.get("falls_on_you") and falling:
        clauses.append(_cap(_en("weather_on_you", what=falling)))
    if reach.get("wind_reaches") and wind:
        clauses.append(_en("weather_wind", wind=wind))
    if temperature and reach.get("exposure") in ("open", "sheltered"):
        clauses.append(_en("weather_air", temperature=temperature))
    for clause in clauses:
        out.append(Percept(
            kind="sensation", channel="touch", source_label="you",
            data={"clause": clause, "directed_at_self": True},
            salience=0.45,
            dedupe_key=standing_key("weather_touch", ("sky",), (clause,)),
        ))
    out.extend(_storm_percepts(reach, sky))
    return out


def _storm_percepts(reach, sky):
    """A SKY THAT FLASHES, AND ITS THUNDER (wave B2, DESIGN_SOUND_FIELD.md
    § 14.3). The `electrical` axis put a flash and a clap into a room for
    the ambience and the screen and into no mind's view at all. Sight
    carries the flash where the sky's weather is in view
    (`weather_visible`); hearing carries the thunder where it reaches
    (`weather.thunder_heard`, the one rule the sound bed reads too). A body
    that has both is told them in the order they arrive: a strike comes
    down from a cloud base a kilometre or two up (`LIGHTNING_M`), so the
    thunder follows the flash by seconds (`sound_after_sight`). Standing:
    said when the storm begins, and again when what this body has of it
    changes."""
    from language_runtime import compositor_text, compositor_value
    from world.spatial import LIGHTNING_M, sound_after_sight
    from world.weather import has_lightning, thunder_heard
    flash = has_lightning(reach) and bool(reach.get("weather_visible"))
    thunder = thunder_heard(reach)
    out = []
    state = (sky, flash, thunder)
    if flash:
        out.append(Percept(
            kind="ambient", channel="sight",
            data={"desc": compositor_text("weather_lightning", sky=sky)
                  if sky else compositor_text("weather_lightning_plain")},
            salience=0.45,
            dedupe_key=standing_key("weather_flash", ("sky",), state)))
    if thunder is not None:
        if flash:
            after = dict(compositor_value("after_sight_words")).get(
                sound_after_sight(LIGHTNING_M) or "seconds", "")
            desc = compositor_text("weather_thunder_after", after=after)
        else:
            desc = compositor_text("weather_thunder_" + (thunder or "open"))
        out.append(Percept(
            kind="ambient", channel="hearing", data={"desc": desc},
            salience=0.45,
            dedupe_key=standing_key("weather_thunder", ("sky",), state)))
    return out


def _weather_sound_heard(reach):
    """`(what, template)` for the precipitation this room hears, or
    `("", "")`: the fall's own name (free text, spliced as written, with
    its intensity where the sky marked one), and the sentence that fits how
    it arrives -- under the sky, on the cover over you, through the walls
    muffled or faint (`weather_for_room`'s `exposure` and `muffling`)."""
    if not reach.get("audible"):
        return "", ""
    what = str(reach.get("precipitation") or "").strip()
    if not what or what.casefold() == "none":
        return "", ""
    how = str(reach.get("intensity") or "").strip()
    exposure = str(reach.get("exposure") or "")
    muffling = str(reach.get("muffling") or "")
    if exposure == "open":
        template = "weather_sound_open"
    elif exposure == "sheltered":
        template = "weather_sound_sheltered"
    else:
        template = "weather_sound_faint" if muffling == "faint" \
            else "weather_sound_muffled"
    # MODERATE IS THE UNMARKED CASE, as in `weather_percepts`; and a name
    # that already carries its intensity word (a record stored before the
    # axes were split: "light snow" at `light`) is not marked twice --
    # measured "the light light snow" on the betrayal story's yard.
    named = _t("weather_falling", intensity=how, what=what) \
        if how in ("light", "heavy") and not what.casefold().startswith(how) \
        else what
    return _noun_phrase(named), template


def _was_hearing(prev_standing, tag, room_id):
    """Was this observer being delivered THIS room's sound under `tag`
    (`WEATHER_SOUND_TAG`, `WIND_SOUND_TAG`) last beat -- the same subject
    test `perception._was_hearing_this_room` makes of the soundscape: the
    key hashes the room as its subject, so a body that walked out of
    earshot holds another room's key and notices no stopping here."""
    if not prev_standing or not room_id:
        return False
    want = standing_key(tag, (room_id,), ("",)).rsplit(":", 1)[0]
    return any(_subject_prefix(key) == want for key in prev_standing)


def weather_sound_percepts(reach, room_id, *, prev_standing=frozenset(),
                           before=None):
    """THE WEATHER'S SOUND, as standing hearing percepts (DESIGN_SOUND_FIELD
    § 17, round 2 lane C): what this body hears of the sky from where it
    stands -- the precipitation that reaches the room (`weather_for_room`'s
    `audible`, at its `muffling`) and a wind at the ear (`wind_reaches`) --
    as two sounds, each keyed like the room's soundscape by its own state
    under the ROOM as subject (`HABITUATING_SOUND_TAGS`): told when it
    starts and when it changes, faded between (`habituated`), and its
    STOPPING told once, by what this observer's own ledger held
    (`prev_standing`, the `ceased` key under the same subject), never to an
    ear that never had it and never to one that walked out of earshot. A
    newcomer hears the room as it is.

    `before` is the room's reach as it stood last beat where the caller has
    it (the outcome pass hands `prev_scene`'s), so the stopping can name
    what fell; without it the record's own name stands -- a sky keeps its
    fall's name through a dry spell (`weather.advance_weather`) -- and
    failing both, the sentence names the class ("the weather").

    TELLING ONLY. The weather's level in the field's floor
    (`spatial_sound_field.WEATHER_NOISE`) is untouched: the owner's rain
    ruling -- rain never masks a line -- stands. Indoors the sound is what
    reaches the room, by the same audibility the sound bed reads
    (`weather_words(scoped, "sound")`), so the page and the ambience cannot
    disagree about whether a cellar hears the storm.
    """
    reach = reach if isinstance(reach, dict) else {}
    before = before if isinstance(before, dict) else {}
    out = []
    if not room_id:
        return out
    what, template = _weather_sound_heard(reach)
    if what:
        out.append(Percept(
            kind="ambient", channel="hearing",
            data={"desc": _cap(_t(template, what=what))},
            salience=0.35,
            dedupe_key=standing_key(
                WEATHER_SOUND_TAG, (room_id,),
                (str(reach.get("precipitation") or ""),
                 str(reach.get("intensity") or ""),
                 str(reach.get("muffling") or ""),
                 str(reach.get("exposure") or "")))))
    elif _was_hearing(prev_standing, WEATHER_SOUND_TAG, room_id):
        # THE RAIN HAS STOPPED -- or no longer reaches this room, which
        # is the honest sentence through a wall. Named from what WAS heard
        # where the caller can say, else from the record's own name.
        name = ""
        for record in (before, reach):
            candidate = str(record.get("precipitation") or "").strip()
            if candidate and candidate.casefold() != "none":
                name = candidate
                break
        if not name:
            desc = _t("weather_sound_ceased_plain")
        elif str(reach.get("exposure") or "") == "enclosed":
            desc = _t("weather_sound_ceased_beyond", what=_noun_phrase(name))
        else:
            desc = _t("weather_sound_ceased", what=_noun_phrase(name))
        out.append(Percept(
            kind="ambient", channel="hearing",
            data={"ceased": True, "desc": _cap(desc)},
            salience=0.4,
            dedupe_key=standing_key(WEATHER_SOUND_TAG, (room_id,),
                                    ("ceased",))))
    wind = str(reach.get("wind") or "").strip()
    if reach.get("wind_reaches") and wind:
        out.append(Percept(
            kind="ambient", channel="hearing",
            data={"desc": _cap(_t("wind_sound", wind=wind))},
            salience=0.35,
            dedupe_key=standing_key(WIND_SOUND_TAG, (room_id,), (wind,))))
    elif _was_hearing(prev_standing, WIND_SOUND_TAG, room_id):
        out.append(Percept(
            kind="ambient", channel="hearing",
            data={"ceased": True, "desc": _cap(_t("wind_sound_ceased"))},
            salience=0.4,
            dedupe_key=standing_key(WIND_SOUND_TAG, (room_id,),
                                    ("ceased",))))
    return out


#: How far a felt shake stands out of a view, by how hard it is felt
#: (`spatial_sound_field.FELT_LEVELS`): a faint tremor is under a room's own
#: salience, a jolt over a pose's.
_FELT_SALIENCE = {"tremor": 0.4, "shudder": 0.55, "jolt": 0.7}


def felt_percepts(rows, *, ground=False, beat=None):
    """WHAT SHOOK THE FLOOR UNDER THIS BODY (`spatial_sound_field.
    felt_vibrations`), on the TOUCH channel: at most one blow -- the beat's
    hardest -- and one steady trembling, each said by how hard it is felt
    and through what the body stands on (`ground` under the sky with no
    floor of its own, else the floor), in the story's own words. Nothing
    else: no source, no direction, no sound -- a body that cannot hear is
    told exactly this.

    A blow is the beat's, so its key carries the beat (`beat`) and it is
    news each time it happens; a steady trembling is standing, said when it
    begins and again only when it changes."""
    from language_runtime import compositor_text, compositor_value
    under = dict(compositor_value("felt_under")).get(
        "ground" if ground else "floor", "")
    out, taken = [], set()
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        word = str(row.get("felt") or "")
        if word not in _FELT_SALIENCE:
            continue
        standing = bool(row.get("standing"))
        if standing in taken:
            continue                    # one blow, one trembling: the hardest
        taken.add(standing)
        clause = compositor_text(("felt_steady_" if standing else "felt_blow_")
                                 + word, under=under)
        out.append(Percept(
            kind="sensation", channel="touch", source_label="you",
            data={"clause": clause, "directed_at_self": True, "felt": word},
            salience=_FELT_SALIENCE[word],
            dedupe_key=standing_key(
                "felt", (row.get("key"),) if standing
                else (row.get("key"), beat), (word, standing))))
    return out
