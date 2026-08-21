"""The mutable clothing ledger: authored notes, shed/worn garment entities,
and the validated attire diff applied to a scene copy.

Extracted verbatim from commit.py, which re-exports every name here. The
deferred function-body imports (agents.common, attire, scene) are the
existing cycle-breakers and stay deferred.
See docs/experiments/AUDIT_COMMIT.md for the split record.
"""

import json, re
from story import attire as attire_model
# Canonical in `story.attire`, which is a leaf module three separate callers
# can reach. Re-exported here under both names because `persist/commit.py`'s
# facade imports them from this module and every `from commit import X` in the
# tree resolves through it.
from story.attire import _NON_ATTIRE_TERMS, sanitize_attire_items
from persist.commit_common import _player_name_or_none

def _unstated(value):
    """Nothing said, as opposed to something said that is falsey.

    `attaches: False` and `state: "worn"` are statements about a garment; a
    missing key, `None` and an empty string/list/dict are not. The difference
    decides whether a merge may fill a field in.
    """
    return value is None or value == "" or value == [] or value == {}


def _merge_attire_regions(target, record):
    """Fold one attire record's `regions` into another's, garment by garment.

    `regions` is the authoring surface: a garment's `state`, `condition`,
    `covered_zones` and the region it was actually PLACED on live only here,
    while `wearing` is a list of names. Merging the two flat lists and
    dropping this left the ledger self-consistent and amnesiac --
    `attire.rederive_entry` rebuilds `regions` from the merged `wearing`
    through the cue tables, so a loosened, wine-stained, hand-placed kimono
    returned as a pristine torso-anchored one. It reads as lossless because
    the invariant it restores (all three representations agreeing) really is
    restored.

    Same rule as the flat lists, one level deeper: whichever record holds the
    fact keeps it. A garment the survivor already carries stays the survivor's
    -- the fold heals a save, it does not adjudicate between two statements --
    and only the fields it leaves UNSAID are filled in from the folded copy.
    Garments are matched with `resolve_garment`, without the head-noun tier: a
    caller that merges two garments into one has to be stricter than one
    routing a note, because merging "silk robe" into "cotton robe" destroys a
    garment.
    """
    from story.attire import resolve_garment

    source = record.get("regions")
    if not isinstance(source, dict):
        return
    merged = target.get("regions")
    if not isinstance(merged, dict):
        merged = {}
    for region, entry in source.items():
        if not isinstance(entry, dict):
            continue
        kept = merged.get(region)
        if not isinstance(kept, dict):
            # A region only the folded record spoke about.
            merged[region] = entry
            continue
        garments = kept.get("garments")
        if not isinstance(garments, list):
            garments = []
        kept["garments"] = garments
        worn = [g["name"] for g in garments
                if isinstance(g, dict) and g.get("name")]
        for garment in entry.get("garments") or []:
            if not isinstance(garment, dict) or not garment.get("name"):
                continue
            match = resolve_garment(garment["name"], worn,
                                    allow_head_noun=False)
            if match is None:
                garments.append(garment)
                worn.append(garment["name"])
                continue
            survivor = next(
                g for g in garments
                if isinstance(g, dict) and g.get("name") == match)
            for field, value in garment.items():
                if field != "name" and _unstated(survivor.get(field)):
                    survivor[field] = value
        for field in ("beneath", "beneath_zones", "uncovered"):
            if _unstated(kept.get(field)) and not _unstated(entry.get(field)):
                kept[field] = entry[field]
        merged[region] = kept
    if merged:
        target["regions"] = merged


def _heal_attire_identity_keys(sc, cast, player_name=None):
    """Collapse scene.attire onto one key per character, and return the
    function that canonicalizes an incoming key.

    A character legitimately answers to several scene keys -- display name,
    identity.uid, aliases (agents.common.character_scene_keys) -- and the
    Director keys attire with whichever it reaches for. Positions survived
    that because readers try every key (character_room) and duplicates get
    collapsed (spatial._dedup_duplicate_position_keys); attire got neither,
    and every reader (scene.appearance_of, agents/character.py) looks under
    the display NAME alone. Observed live (Elevator Adventure branch 41):
    Dr. Moon held two records -- `char_f0ef86a7...` with her lab coat,
    shirt, trousers and loafers, and `Dr. Moon` with `wearing: []` -- so
    she rendered as wearing nothing while her clothing STATE still read
    "lab coat ripped at the hem".

    Merging (rather than preferring one) is what makes this heal an
    existing save: whichever record holds the clothes keeps them.
    """
    from agents.common import cast_spelling_policy

    # ONE POLICY, shared with `common.canonicalize_positions`. This function
    # and that one were two hand-rolled tables of the same rule that disagreed
    # about aliases, and the disagreement was a live defect: in chat 82 this
    # side folded "Dr. Sarah Moon" onto the sheet's "Sarah Moon" and positions
    # did not, so one woman was keyed two ways across the ledgers describing
    # her. Attire keys BODIES only, so matching aliases here is safe and is
    # what heals the split; positions keys objects too and passes
    # `aliases=False`. The Yuki guard -- a real name outranks somebody else's
    # alias for it, measured when Yuki's wardrobe collapsed onto another
    # woman -- now lives in the shared policy, where both callers get it.
    # The PLAYER is a body with a wardrobe like any other, and omitting them
    # here is what let one split in two. `canonicalize_positions` has always
    # passed the player name; this side did not, so a persona keyed by the
    # scene's entity id ("hinami") never folded onto the persona's own
    # spelling ("Hinami") and both records stayed live, drifting apart.
    # Measured in chat 77: `hinami.state` read "bare at the head" while
    # `Hinami.state` held a full displaced wardrobe, for one woman.
    # This is the same two-callers-disagree defect the docstring above
    # records from chat 82, in the one axis that fix did not cover.
    canonical, _forms = cast_spelling_policy(cast, player_name)

    attire = sc.get("attire")
    if isinstance(attire, dict):
        for key in [k for k in attire if canonical(k) != k]:
            record = attire.pop(key)
            if not isinstance(record, dict):
                continue
            target = attire.setdefault(canonical(key),
                                       {"wearing": [], "state": []})
            if not isinstance(target, dict):
                continue
            for field in ("wearing", "state"):
                merged = list(target.get(field) or [])
                for item in record.get(field) or []:
                    if item not in merged:
                        merged.append(item)
                target[field] = merged
            _merge_attire_regions(target, record)

    return canonical


def _beat_voices(ctx, res):
    """Every text this beat was acted in, EXCEPT the player's own input.

    What each character declared, plus the Director's resolved prose. The
    player's input is passed separately by the caller, because first person is
    only a reliable subject there -- "I rip my coat off" names its subject
    nowhere else in the sentence.

    Used only to decide how FAST an undressing the fiction has already asked
    for happens -- never who may know what -- so reading across all of it
    carries no information-firewall cost.
    """
    texts = []
    if isinstance(res, dict):
        texts.append(str(res.get("resolved_event") or ""))
    for result in (getattr(ctx, "character_results", None) or {}).values():
        if not isinstance(result, dict):
            continue
        for key in ("action", "speech"):
            texts.append(str(result.get(key) or ""))
        for element in result.get("sequence") or []:
            if isinstance(element, dict):
                for key in ("action", "speech", "text"):
                    texts.append(str(element.get(key) or ""))
    return [t for t in texts if t.strip()]


# How long a comma-led head may be and still read as a garment's name rather
# than as the first clause of a sentence about one.
_NOTE_NAME_HEAD = 40


def _garment_named_in(text, name):
    """Does this beat's prose actually mention the garment a note is minting?

    Matched on the head noun rather than the whole phrase: a note introduces
    "linen shift" and the prose says "the hem of your shift". Any word of the
    name that is long enough to be the garment itself counts, so a two-word
    name matches on either.
    """
    body = str(text or "").casefold()
    if not body:
        return False
    for word in re.findall(r"[a-z]+", str(name or "").casefold()):
        if len(word) >= 4 and re.search(rf"\b{re.escape(word)}s?\b", body):
            return True
    return False


def interpret_attire_notes(diff, worn, entry=None, prose=None):
    """Read an attire diff's free-form notes as the change they describe.

    `StateDiff.attire` had an untyped inner dict, and the commit loop below
    reads exactly `wearing`/`add`/`remove`/`replace`/`state`/`conditions`.
    Every other shape validated cleanly and then fell through the loop doing
    nothing at all. Two of the six attire diffs in the measured story were
    silent no-ops:

        {"Elyndra": {"robe": "sheer, parted"}}
        {"Hinami": {"shift": "linen shift, hem rucked up where her hand..."}}

    The second is why that story's narration could say "the hem of your shift"
    and "the waistband of your shorts" in one paragraph: the shift the prose
    had been describing since beat 0 never reached the ledger, which still held
    the travel clothes seeded off her card.

    Three readings, in order of how much they assume:

      1. the handle names a garment she is wearing -> what just happened to it,
      2. it names the wardrobe as a whole -> prose the body keeps, unless it
         says in as many words that nothing changed,
      3. it names a garment the ledger has never heard of -> she is wearing it
         now. The one-rung rule and the region tables then apply to it like
         anything else, and the Director sees it next beat to correct.

    Returns the diff with the notes folded into the fields the loop reads.
    `entry` is the body's live ledger entry, mutated only for reading 2.
    """
    diff = dict(diff or {})
    notes = diff.pop("notes", None)
    if not isinstance(notes, dict) or not notes:
        return diff
    marks = dict(diff.get("conditions") or {})
    notes_read = diff.setdefault("_notes_read", [])
    for handle, text in notes.items():
        text = str(text or "").strip()
        if not text or attire_model.is_no_change_note(text):
            continue
        garment = attire_model.resolve_garment(handle, worn)
        if garment is not None:
            marks.setdefault(garment, text)
        elif str(handle).casefold() in attire_model._GENERIC_WARDROBE_KEYS:
            if isinstance(entry, dict):
                entry["state"] = list(entry.get("state") or []) + [text]
        else:
            name, mark = attire_model.split_garment_name(text)
            # A note names the garment and then says what happened to it, and
            # the clause that follows is nearly always comma-led: "linen
            # shift, hem rucked up where her hand slipped beneath". Without
            # this the whole sentence becomes the garment's NAME, which is
            # also its matching key -- so the next beat's "shift" would not
            # find it and the fork would start all over again.
            if "," in name:
                head, _, rest = name.partition(",")
                if head.strip() and len(head.strip()) <= _NOTE_NAME_HEAD:
                    name, mark = head.strip(), (rest.strip() or mark)
            if attire_model.resolve_garment(name, worn) is not None:
                marks.setdefault(handle, text)
                continue
            # A note whose text is just a STATE is not naming a garment, it is
            # naming what happened to the handle. Reading it as reading 3 minted
            # a garment called "removed" -- literally, `{"name": "removed",
            # "state": "worn"}` on Hinami's torso -- and another called "worn"
            # on Elyndra's, each sitting in the ledger alongside the real
            # clothes and appearing in the `wearing` list the character reads.
            # A body wearing "removed" cannot reason about being dressed.
            #
            # `{"sandals": "removed"}` means the sandals came off, even when the
            # handle failed to resolve against the wardrobe; route it to the
            # field that says so rather than inventing a body part's worth of
            # new clothing named after a participle.
            if attire_model.is_bare_garment_state(name):
                if attire_model.is_removal_state(name):
                    diff.setdefault("remove", []).append(handle)
                    notes_read.append(
                        f"attire: read your note on {handle!r} as taking it off.")
                else:
                    diff.setdefault("add", []).append(handle)
                    marks.setdefault(handle, name)
                    notes_read.append(
                        f"attire: read your note on {handle!r} as putting it on.")
                continue
            # A note may only INTRODUCE a garment the beat's prose actually
            # mentions. Reading 3 exists for the case where the narration has
            # been describing a shift since beat 0 while the ledger still holds
            # the travel clothes off her card -- there, the prose says "shift"
            # and the note is catching the ledger up. It cannot otherwise tell
            # that from the Director simply imagining clothing, and the
            # difference is not structural: "linen shift, hem rucked up" and
            # "corset, unlaced and hanging open" are the same shape.
            #
            # What separates them is whether the story ever said it. Measured
            # on chat 52: a `corset` and a `skirt` reached Elyndra's ledger and
            # neither word appears in ANY of the 23 turns of narration. She was
            # carrying two garments the fiction had never mentioned, on top of
            # the four her card authors.
            #
            # `prose` omitted means no gate, so every existing caller and the
            # rerun path behave exactly as before.
            if prose is not None and not _garment_named_in(prose, name):
                notes_read.append(
                    f"attire: ignored your note on {handle!r} -- it would have "
                    f"put {name!r} on them, and this beat's prose never "
                    "mentions it. Use `add` if they really are wearing it.")
                continue
            diff.setdefault("add", []).append(name)
            if mark:
                marks.setdefault(name, mark)
            notes_read.append(
                f"attire: read your note on {handle!r} as putting {name!r} on "
                "them, since they were not wearing it.")
    if marks:
        diff["conditions"] = marks
    return diff


def _fold_duplicate_shed_garments(sc, diff=None, ctx=None):
    """Collapse several records of ONE shed garment into one. Idempotent.

    Adopt-or-mint stops new duplicates; it does not reach the ones already
    standing, because it only runs on a garment removed THIS beat. A scene
    that accumulated them keeps them forever otherwise -- chat 71 carried
    five records for two garments, minted across two stages and the commit
    seam, and every later beat would read all five.

    Conservative: same owner, all clothing, all shed, and
    `attire.resolve_garment` agreeing the names are the same garment. The
    survivor is the one that knows where it is (a positioned record is the
    thing on the floor); the others' condition and description are kept if
    the survivor has none. Two genuinely identical garments shed by one
    body in one scene would fold -- accepted deliberately, because the
    alternative is a permanent contradiction that compounds, and every fold
    is reported rather than silent.
    """
    from story.attire import resolve_garment

    if not isinstance(sc, dict):
        return
    entities = sc.get("entities")
    if not isinstance(entities, dict):
        return
    positions = sc.get("positions") or {}
    projected = diff.get("entities") if isinstance(diff, dict) else None

    groups = []
    for eid, entity in entities.items():
        state = entity.get("state") if isinstance(entity, dict) else None
        if not isinstance(state, dict) or not state.get("clothing") \
                or not state.get("shed"):
            continue
        owner = str(state.get("worn_by") or "").strip().casefold()
        name = str(entity.get("name") or "").strip()
        if not name:
            continue
        for group in groups:
            # An UNOWNED record joins an owned one: the model's own records
            # routinely carry no worn_by while the commit seam's mint does,
            # which is exactly the live shape (travel_shorts beside
            # travel_shorts_hinami). Two records naming DIFFERENT owners
            # never fold -- those are two bodies' garments.
            if group["owner"] and owner and group["owner"] != owner:
                continue
            if (resolve_garment(name, [group["name"]])
                    or resolve_garment(group["name"], [name])):
                group["ids"].append(eid)
                group["owner"] = group["owner"] or owner
                break
        else:
            groups.append({"owner": owner, "name": name, "ids": [eid]})

    for group in groups:
        if len(group["ids"]) < 2:
            continue
        keep = next((i for i in group["ids"] if positions.get(i)),
                    group["ids"][0])
        survivor = entities[keep]
        for eid in group["ids"]:
            if eid == keep:
                continue
            loser = entities.get(eid) or {}
            lost_state = loser.get("state") or {}
            s_state = survivor.setdefault("state", {})
            if lost_state.get("condition") and not s_state.get("condition"):
                s_state["condition"] = lost_state["condition"]
            if loser.get("description") and not survivor.get("description"):
                survivor["description"] = loser["description"]
            for alias in [loser.get("name")] + list(loser.get("aliases") or []):
                aliases = survivor.setdefault("aliases", [])
                if alias and isinstance(aliases, list) and alias not in aliases:
                    aliases.append(str(alias))
            entities.pop(eid, None)
            positions.pop(eid, None)
            if isinstance(projected, dict):
                projected.pop(eid, None)
        note = (
            f"objective state: {len(group['ids'])} entity records described "
            f"one shed garment ({group['name']!r}); they were folded into "
            f"{keep!r}. A garment that comes off is one object in the world.")
        if ctx is not None:
            ctx.tell_director(note)
            ctx.add_warning(note)


def _fold_worn_garment_entities(sc, diff, ctx=None):
    """WHILE IT IS WORN, THE ATTIRE LEDGER OWNS THE GARMENT.

    The mirror of adopt-or-mint. A specialist that needs to name a worn
    garment -- to wet it, to touch it -- cannot find one in `entities`,
    because a worn garment lives only in `sc.attire`. Measured live: the
    objects specialist minted `hinami_shorts` with `worn_by: Hinami` and
    `condition: damp` for exactly that reason, and its own note admitted
    it ("Created entity ... as it was not present in the provided
    entities"). That record then stood beside the attire ledger claiming
    the shorts were still worn while the ledger correctly had the body
    bare.

    So an entity claiming to be worn by a body whose attire ledger already
    carries that garment is folded away: its condition, the one thing it
    knows that the ledger might not, is written onto the garment in the
    ledger, and the duplicate record is dropped. Reported through
    tell_director every time -- the Director asked for a referent it did
    not have, and next beat it should know the answer was "the ledger has
    it".

    Layer 2 (the referent index) removes the pressure that creates these.
    This is the floor that holds whether or not a model cooperates.
    """
    from story.attire import resolve_garment

    if not isinstance(sc, dict):
        return
    entities = sc.get("entities")
    if not isinstance(entities, dict):
        return
    attire = sc.get("attire") or {}
    projected = diff.get("entities") if isinstance(diff, dict) else None
    for eid in list(entities):
        entity = entities.get(eid)
        if not _is_clothing_entity(entity):
            continue
        state = entity.get("state") or {}
        owner = str(state.get("worn_by") or "").strip()
        if not owner or state.get("shed"):
            continue          # shed records are the floor object; leave them
        entry = attire.get(owner)
        if not isinstance(entry, dict):
            continue
        worn = [str(n) for n in (entry.get("wearing") or []) if str(n).strip()]
        name = str(entity.get("name") or "").strip()
        if not name or not worn:
            continue
        match = resolve_garment(name, worn)
        if not match:
            continue
        condition = str(state.get("condition") or "").strip()
        if condition:
            _set_worn_garment_condition(entry, match, condition)
        entities.pop(eid, None)
        if isinstance(projected, dict):
            projected.pop(eid, None)
        (sc.get("positions") or {}).pop(eid, None)
        note = (
            f"objective state: an entity record {eid!r} claimed to be "
            f"{owner}'s worn {name!r}; while a garment is WORN the attire "
            f"ledger owns it, so the record was folded into "
            f"attire.{owner}'s {match!r}"
            + (f" (condition {condition!r} kept)" if condition else "")
            + ". Name a worn garment from the attire ledger rather than "
              "creating an object for it.")
        if ctx is not None:
            ctx.tell_director(note)
            ctx.add_warning(note)


def _set_worn_garment_condition(entry, garment_name, condition):
    """Put a condition on the named garment inside one attire entry."""
    for region in (entry.get("regions") or {}).values():
        if not isinstance(region, dict):
            continue
        for garment in (region.get("garments") or []):
            if isinstance(garment, dict) and \
                    str(garment.get("name") or "") == garment_name:
                garment["condition"] = condition


def _is_clothing_entity(entity):
    state = entity.get("state") if isinstance(entity, dict) else None
    return isinstance(state, dict) and bool(state.get("clothing"))


def _adopt_shed_record(entities, projected, owner, garment):
    """The id of an EXISTING record for this garment, or None to mint.

    Deliberately conservative: only clothing-flagged records, only those
    either unowned or owned by this same body, and only where
    `attire.resolve_garment` -- the engine's one garment-naming authority,
    already tuned against live wardrobes -- says the names are the same
    garment. Two records that both match fold to the first in scan order,
    which is deterministic because `entities` preserves insertion order.

    A wrong adoption is reported and visible; a wrong duplicate is silent
    and permanent, and compounds every beat. That asymmetry is why this
    resolves rather than requiring an exact key match.
    """
    from story.attire import resolve_garment

    name = str(garment)
    candidates = []
    for eid, entity in entities.items():
        if not _is_clothing_entity(entity):
            continue
        state = entity.get("state") or {}
        worn_by = str(state.get("worn_by") or "").strip()
        if worn_by and worn_by.casefold() != str(owner).casefold():
            continue
        handles = [str(entity.get("name") or "")]
        handles += [str(a) for a in (entity.get("aliases") or [])]
        handles = [h for h in handles if h.strip()]
        if not handles:
            continue
        if resolve_garment(name, handles) or any(
                resolve_garment(h, [name]) for h in handles):
            candidates.append(eid)
    return candidates[0] if candidates else None


def _stamp_shed(entity, garment, owner, condition):
    """Make an adopted record say what a minted one would have said."""
    if not isinstance(entity, dict):
        return
    state = entity.setdefault("state", {})
    state["clothing"] = True
    state["shed"] = True
    state.setdefault("worn_by", str(owner))
    if condition:
        state["condition"] = condition
    if not str(entity.get("name") or "").strip():
        entity["name"] = str(garment)
    entity.setdefault("kind", "object")
    entity.setdefault("portable", True)
    aliases = entity.setdefault("aliases", [])
    if isinstance(aliases, list) and str(garment) not in aliases:
        aliases.append(str(garment))


def _mint_shed_garments(sc, shed, diff=None):
    """A garment that has come off becomes a thing in the room.

    Clothes that vanish when removed cannot be picked up, taken, hidden or
    found again, and the story loses the shirt it just spent a beat on. Minted
    as an ordinary portable object, so everything that already works on objects
    -- being carried, being put inside a wardrobe or a chest, being seen --
    works on it with no further machinery. Placed where its wearer is standing;
    where it goes next is the story's business.

    Written into the beat's `diff` as well as the scene. `world_entities` is a
    DERIVED projection built from that diff, not from the scene blob, so an
    entity minted only here would live in the runtime scene and be absent from
    the normalized table -- the one divergence Phase 3a exists to prevent.
    """
    if not shed or not isinstance(sc, dict):
        return
    entities = sc.setdefault("entities", {})
    positions = sc.setdefault("positions", {})
    projected = diff.setdefault("entities", {}) if isinstance(diff, dict) else None
    for owner, garment, *rest in shed:
        condition = (rest[0] if rest else "") or ""
        key = re.sub(r"[^a-z0-9]+", "_", str(garment).casefold()).strip("_")
        if not key:
            continue
        key = "%s_%s" % (key, re.sub(r"[^a-z0-9]+", "_",
                                     str(owner).casefold()).strip("_"))[:60]
        if key in entities:
            continue
        # ADOPT BEFORE MINTING. The private "<garment>_<owner>" key above is
        # the only thing this seam ever checked, so a record the MODEL wrote
        # for the same garment -- under any other id -- was a sibling, not a
        # collision. Measured live (chat 71, one beat after the jacket
        # repair): five entity records for two garments, one of them still
        # carrying worn_by with no shed flag while the attire ledger
        # correctly showed the body bare. The garment is the same thing in
        # the fiction; it gets one record.
        adopted = _adopt_shed_record(entities, projected, owner, garment)
        if adopted:
            _stamp_shed(entities[adopted], garment, owner, condition)
            if projected is not None and adopted in projected:
                _stamp_shed(projected[adopted], garment, owner, condition)
            where = positions.get(owner)
            if where and not positions.get(adopted):
                positions[adopted] = where
            continue
        entities[key] = {
            "name": str(garment),
            "kind": "object",
            # What happened to it while it was being worn travels with it. A
            # shirt someone spilled wine down is a wine-stained shirt on the
            # floor, not a clean one -- the stain belongs to the garment.
            "description": "%s, taken off%s" % (
                str(garment), " — %s" % condition if condition else ""),
            "aliases": [str(garment)],
            "portable": True,
            "container": False,
            "interior_rooms": [],
            "state": {"clothing": True, "worn_by": str(owner), "shed": True,
                      **({"condition": condition} if condition else {})},
        }
        if projected is not None:
            projected.setdefault(key, entities[key])
        where = positions.get(owner)
        if where:
            positions[key] = where


def _overlay_texts_by_subject(diff):
    """{casefolded subject: {casefolded overlay description}} for THIS diff.

    `overlays` is where the Director says what a BODY currently looks like
    this beat. A garment `condition` says what a GARMENT looks like. They are
    two channels about two different things, and one string cannot be a true
    answer in both.
    """
    out = {}
    for rows in (diff.get("overlays") or {}).values():
        for row in (rows if isinstance(rows, list) else [rows]):
            if not isinstance(row, dict):
                continue
            subject = str(row.get("subject") or "").strip().casefold()
            text = str(row.get("description") or "").strip().casefold()
            if subject and text:
                out.setdefault(subject, set()).add(text)
    return out


def _drop_overlay_conditions(marks, name, overlay_texts, ctx, report):
    """Strip garment conditions that are this body's own overlay, verbatim.

    Live, chat 82 t1. The body specialist emitted, for one body:

        "attire": {"Hinami": {"conditions": {
            "lightweight travel jacket":
                "golden fox ears drooping limply atop copper-gold hair",
            "fitted tank top": "unfocused amber eyes blink open slowly"}}}

    and emitted both strings into `overlays` for the same body in the same
    beat, where they belong. The garment copies committed, so every observer's
    attire row rendered "lightweight travel jacket (golden fox ears drooping
    limply atop copper-gold hair)" and the ledger panel showed the same. Same
    class as the three contradictory `bare at the` notes: the symptom is in
    the ledger, the origin is `state_diff.attire`.

    NOT a judgment about what a condition may say -- "soaked through" is a
    true thing to write about a coat and about the body in it, and this would
    never see it, because it only fires when the SAME beat filed the SAME
    string to both channels. That is a contradiction the engine can read
    without understanding either sentence: one fact, two answers, and the
    channel that says what a body looks like is the one that was right.
    """
    if not marks or not overlay_texts:
        return marks
    own = overlay_texts.get(str(name or "").strip().casefold()) or set()
    if not own:
        return marks
    kept = {}
    for garment, text in marks.items():
        if str(text or "").strip().casefold() in own:
            if report:
                ctx.tell_director(
                    f"attire: dropped your condition on {garment!r} -- it is "
                    f"word for word {name}'s own body overlay this beat, and "
                    "a condition describes the GARMENT (torn, soaked, "
                    "unfastened), never the body wearing it.")
                ctx.add_warning(
                    f"attire: {name}'s overlay {str(text)[:60]!r} was also "
                    f"filed as a condition on {garment!r}; kept the overlay")
            continue
        kept[garment] = text
    return kept


def apply_attire_diff(sc, diff, ctx, res=None, *, report=True):
    """Apply one validated attire diff to a scene copy.

    This is the single attire projection used by both the pre-commit outcome
    preview and durable scene preparation.  Keeping it here prevents
    perception from approximating commit's alias resolution, decisive-removal
    rule, region derivation, and shed-object minting with a second spelling.
    ``sc`` and ``diff`` are caller-owned copies in the perception path.
    """
    if not isinstance(sc, dict) or not isinstance(diff, dict):
        return sc
    res = res or {}
    for recovered in attire_model.recover_shed_entity_changes(sc, diff):
        if recovered.get("position"):
            sc.setdefault("positions", {})[recovered["entity_id"]] = (
                recovered["position"])
        if report and recovered.get("garment"):
            ctx.tell_director(
                "attire: read explicitly shed clothing entity "
                f"{recovered['entity_id']!r} as removing "
                f"{recovered['garment']!r} from {recovered['owner']!r}.")

    att = sc.setdefault("attire", {})
    _overlay_by_subject = _overlay_texts_by_subject(diff)
    canonical_attire_key = _heal_attire_identity_keys(
        sc, ctx.cast, _player_name_or_none(ctx))
    # WHOSE clothes this beat tore off, not merely whether somebody's did —
    # and whose undressing the prose leaves still IN PROGRESS. The two
    # readings share one attribution ladder (attire._attributed_targets) and
    # drive the inverted clamp: a resolved removal lands unless the body is
    # in the process set, and `decisive` still lifts everything.
    _attire_wardrobe = {
        _name: attire_model.flat_wearing(attire_model.normalize_regions(_entry))
        for _name, _entry in att.items() if isinstance(_entry, dict)}
    _decisive_names = attire_model.decisive_targets(
        getattr(ctx.turn, "player_input", "") or "",
        _beat_voices(ctx, res),
        _attire_wardrobe,
        player_name=_player_name_or_none(ctx),
    )
    _process_names = attire_model.process_targets(
        getattr(ctx.turn, "player_input", "") or "",
        _beat_voices(ctx, res),
        _attire_wardrobe,
        player_name=_player_name_or_none(ctx),
    )
    _shed = []
    _gained = set()
    for name, d in (diff.get("attire") or {}).items():
        name = canonical_attire_key(name)
        if not isinstance(d, dict):
            continue
        d = attire_model.coerce_diff_shape(d)
        cur = att.setdefault(name, {"wearing": [], "state": []})
        cur.setdefault("wearing", [])
        cur.setdefault("state", [])

        d = interpret_attire_notes(
            d, attire_model.flat_wearing(attire_model.normalize_regions(cur)),
            cur, prose=str(res.get("resolved_event") or ""))
        for _read in d.pop("_notes_read", None) or []:
            if report:
                ctx.tell_director(_read)

        # THE WRITE GATE. A change to what a body wears is licensed by the
        # beat's own words naming the garment, and by nothing else. Scoped to
        # the three channels that can UNDRESS somebody -- `add` only ever puts
        # clothing on, so an ungated one cannot expose a body and gating it
        # would refuse the first dressing of a body whose arrival is the beat.
        #
        # Every other axis here already reads the prose (`_PROCESS`,
        # `_DECISIVE`, `removal_directed_at`); the write itself read nothing,
        # so a `remove` or a `coverage` block landed whether or not a word of
        # the beat concerned clothing. Chat 78: nine turns, no garment named in
        # any of them, the wardrobe rewritten twice -- t7 restated the whole
        # thing into `coverage` as "covers nothing", t8 removed two garments
        # nobody touched, and the two together put the body's `beneath` prose
        # on the page under garments that were still on.
        #
        # Failure direction is the module's own: a real change refused costs
        # one beat and a notice telling the Director to restate it in prose,
        # while a phantom one destroys ledger state, mints a floor object and
        # never re-derives.
        _worn_now = attire_model.flat_wearing(
            attire_model.normalize_regions(cur))
        _licence = ([getattr(ctx.turn, "player_input", "") or ""]
                    + list(_beat_voices(ctx, res)))
        for _channel in ("remove", "coverage", "placement"):
            _entries = d.get(_channel)
            if not _entries:
                continue
            _as_list = isinstance(_entries, list)
            _handles = list(_entries) if _as_list else list(_entries.keys())
            _names = {}
            for _h in _handles:
                _names[id(_h)] = (_h if isinstance(_h, str)
                                  else str((_h or {}).get("name") or ""))
            # Only handles that would actually change something are gated. One
            # naming nothing this body wears is already answered further down
            # -- resolved, refused and reported as the no-op it is -- and
            # taking it here would replace a precise diagnosis with a vaguer
            # one.
            _live = [h for h in _handles if _names[id(h)]
                     and attire_model.resolve_garment(
                         _names[id(h)], _worn_now)]
            _named = set(attire_model.garments_named_in(
                _licence, [_names[id(h)] for h in _live], _worn_now))
            _kept = [h for h in _handles
                     if h not in _live or _names[id(h)] in _named]
            if len(_kept) == len(_handles):
                continue
            _dropped = sorted({_names[id(h)] for h in _handles
                               if _names[id(h)] not in _named and _names[id(h)]})
            d[_channel] = (_kept if _as_list
                           else {k: v for k, v in _entries.items()
                                 if k in _named})
            ctx.add_warning(
                "attire: dropped an unsupported %s for %s (%s) -- no word of "
                "this beat names the garment" % (
                    _channel, name, ", ".join(_dropped)))
            if report:
                ctx.tell_director(
                    "attire: dropped the %s of %s for %s. Nothing in this "
                    "beat's words -- the player's input, your resolved prose, "
                    "or what anyone declared -- names that garment, and a "
                    "wardrobe changes only where the beat says it does. The "
                    "`attire` block in your payload is the CURRENT state of "
                    "the wardrobe, not a form to fill in: when clothing did "
                    "not change, leave the channel empty. If it did change, "
                    "say so in the prose and restate it next beat." % (
                        _channel, ", ".join(repr(x) for x in _dropped), name))
        if d.get("wearing") is not None and not any(
                d.get(k) for k in ("add", "remove", "replace")):
            cur["wearing"] = sanitize_attire_items(list(d.get("wearing") or []))
            if d.get("state") is not None:
                cur["state"] = (d["state"] if isinstance(d["state"], list)
                                else [d["state"]])
            if isinstance(d.get("regions"), dict) and d["regions"]:
                cur["regions"] = attire_model.normalize_regions(
                    {"wearing": cur["wearing"], "regions": d["regions"]})
        else:
            previous_names = list(cur["wearing"])
            if isinstance(d.get("replace"), list):
                replaced = []
                for handle in d["replace"]:
                    text = str(handle or "").strip()
                    canonical = attire_model.resolve_garment(
                        text, previous_names) or text
                    if canonical and canonical not in replaced:
                        replaced.append(canonical)
                cur["wearing"] = sanitize_attire_items(replaced)
            for handle in d.get("add") or []:
                text = str(handle or "").strip()
                canonical = attire_model.resolve_garment(
                    text, cur["wearing"]) or text
                if canonical and canonical not in cur["wearing"]:
                    cur["wearing"].append(canonical)
            cur["wearing"] = sanitize_attire_items(cur["wearing"])
            for handle in d.get("remove") or []:
                canonical = attire_model.resolve_garment(
                    handle, cur["wearing"])
                if canonical in cur["wearing"]:
                    cur["wearing"].remove(canonical)
                elif report:
                    # A `remove` naming nothing this body wears is a no-op --
                    # the resolver already refused the handle, so nothing was
                    # ever going to come off -- and it was a SILENT one, which
                    # let the emitter keep believing the ledger held garments
                    # it did not. Measured (chat 76, turn 57): the body
                    # specialist re-removed the "utility sash with pouches"
                    # taken off the beat before, and removed a "nightwear
                    # garment" this branch never added (the name is a parent
                    # branch's ledger bleeding into context). Surfaced on both
                    # channels, dropped rather than guessed: a legitimate
                    # alias resolves through `resolve_garment`'s tiers above
                    # and never reaches this branch, while forcing an
                    # unresolved handle through would remove a coin-flip
                    # garment. Wrongly keeping a garment on is recoverable
                    # next beat; wrongly removing one is not.
                    ctx.tell_director(
                        f"attire: `remove` named {handle!r} for {name}, but "
                        "nothing they are currently wearing answers to it "
                        f"(worn: {', '.join(cur['wearing']) or 'nothing'}). "
                        "Dropped as a no-op -- a garment already off the "
                        "body, or never on it, has no removal to apply. If a "
                        "worn garment was meant, name it as the ledger does.")
                    ctx.add_warning(
                        f"attire: dropped no-op removal of {handle!r} for "
                        f"{name} (not currently worn)")
            if d.get("state") is not None:
                cur["state"] = (d["state"] if isinstance(d["state"], list)
                                else [d["state"]])

        _before = attire_model.normalize_regions(cur)
        _marks = d.get("conditions")
        if isinstance(_marks, dict):
            _marks = _drop_overlay_conditions(
                _marks, name, _overlay_by_subject, ctx, report)
        # THE STEAL GUARD (design note 17 §3): a coverage entry that empties
        # every region a garment covers, named by a removal-directed decisive
        # phrase in this beat's words, is the removal it plainly was — filed
        # on the displacement axis. Escalated through the normal remove path
        # so the ladder (lifted by the same decisive act) and the shed-object
        # minting both apply. An ambiguous phrase keeps its displacement
        # reading: wrongly holding a garment on the body is recoverable next
        # beat, wrongly removing it is not.
        _coverage = (d.get("coverage")
                     if isinstance(d.get("coverage"), dict) else {})
        if _coverage:
            # NOT gated on `name in _decisive_names` any more. The escalation
            # test that matters is `removal_directed_at` -- whether THIS beat's
            # words describe taking the garment off -- and it is inside
            # `coverage_removal_escalations` already. The extra gate meant that
            # on a beat where nobody did anything decisive the whole block was
            # skipped, so a total emptying was neither escalated NOR examined:
            # it fell straight through to `apply_coverage_changes` and stripped
            # the wardrobe. Measured in chat 77 turn 8, where the beat was two
            # people talking and both of them came out bare.
            _beat_texts = ([getattr(ctx.turn, "player_input", "") or ""]
                           + list(_beat_voices(ctx, res)))
            _coverage = dict(_coverage)
            _escalate = set(attire_model.coverage_removal_escalations(
                _beat_texts, _coverage, _before))
            for _handle in _escalate:
                _coverage.pop(_handle, None)
                _canonical = attire_model.resolve_garment(
                    _handle, cur["wearing"])
                if _canonical in cur["wearing"]:
                    cur["wearing"].remove(_canonical)
                if report:
                    ctx.tell_director(
                        f"attire: read the coverage claim on {_handle!r} as "
                        "the decisive removal this beat's words describe -- "
                        "a garment taken off the body is `remove`, not a "
                        "coverage change.")
            # A claim that would leave this body covered NOWHERE, on a beat
            # whose words removed nothing, is refused whole. Displacing one
            # garment off everything it covers is ordinary -- trousers at the
            # ankles are worn and cover nothing, and the ladder completes from
            # there in one rung. Displacing a body's ENTIRE wardrobe at once is
            # not: nobody undresses completely by displacement, and the shape
            # is what a restatement of the wardrobe looks like when the regions
            # go in the keys and the zones, which are the payload, are left
            # empty. Chat 77 turn 8: two people talking, six garments and five
            # garments to "displaced off", both narrated bare for two beats,
            # every record still `worn`, and not one warning in thirteen turns.
            # Refusing is the recoverable direction -- a garment wrongly held
            # on the body is fixed next beat; one wrongly taken off is not.
            if _coverage and attire_model.coverage_would_bare_the_body(
                    _before, _coverage):
                ctx.add_warning(
                    f"attire: refused a coverage claim that would have left "
                    f"{name} covered nowhere, on a beat whose words remove "
                    "nothing. Coverage is partial displacement; taking a "
                    "garment off is `remove`.")
                if report:
                    ctx.tell_director(
                        f"attire: ignored the coverage block for {name}; it "
                        "displaced every garment off every region at once, "
                        "which reads as a restatement of the wardrobe rather "
                        "than a change to it. `coverage` carries the zones a "
                        "garment STILL covers -- to take one off, use "
                        "`remove`.")
                _coverage = {}
        _wanted_before = list(cur["wearing"])
        _after = attire_model.apply_flat_change(
            _before, cur["wearing"], decisive=name in _decisive_names,
            conditions=_marks if isinstance(_marks, dict) else None,
            process=name in _process_names,
            # Where this beat says the garment went, when that is not where
            # its name implies. The region tables cover the ordinary case and
            # nothing beyond it, and the space beyond it has no bottom --
            # underwear on the head, a belt across the chest, a shirt worn as
            # trousers. Whoever put it on says where.
            placement=d.get("placement"))
        _after, _coverage_notes = attire_model.apply_coverage_changes(
            _after, _coverage)
        if report:
            for _coverage_note in _coverage_notes:
                ctx.tell_director(_coverage_note)
            # A removal the ladder held is said out loud (design note 17 §4):
            # the fiction may already believe the garment off, and a silent
            # clamp is how chat 68 stranded a tank top at `loosened` with no
            # later beat ever re-proposing it.
            for _held_name, _held_state in attire_model.removals_held(
                    _before, _after, _wanted_before):
                ctx.tell_director(
                    f"attire: the removal of {name}'s {_held_name!r} was "
                    f"held at {_held_state!r} because this beat's prose "
                    "reads as still in progress. When the act completes, "
                    "propose `remove` again with completed prose.")
                ctx.add_warning(
                    f"attire: removal of {name}'s {_held_name!r} held at "
                    f"{_held_state!r} (beat reads as in progress)")
            # A condition describing the garment ON a body is dropped when it
            # leaves one (design note 17 §6), and said out loud for the same
            # reason the clamp is: a stale "hanging off her shoulder" on a
            # garment lying on the floor had the Director remove the same
            # jacket twice and the narrator narrate it a third time.
            for _gone_name, _gone_cond in attire_model.worn_conditions_dropped(
                    _before, _after):
                ctx.tell_director(
                    f"attire: {name}'s {_gone_name!r} left the body, so its "
                    f"condition {_gone_cond!r} was dropped — it described the "
                    "garment's relationship to a body it is no longer on. "
                    "Any lasting damage belongs on the shed object.")
            # Displacement or rung words written ONLY as condition prose move
            # nothing (design note 17 §4) -- the chat 70 jacket and chat 68
            # t7 defects. Detected, never executed: the feedback names the
            # channel that does move state.
            _cov_handles = {
                (attire_model.resolve_garment(h, _wanted_before) or str(h))
                .casefold() for h in _coverage}
            for _handle, _text in ((_marks or {}).items()
                                   if isinstance(_marks, dict) else []):
                _resolved = (attire_model.resolve_garment(
                    _handle, _wanted_before) or str(_handle)).casefold()
                _rung_word = attire_model.rung_language(_text)
                if _rung_word:
                    ctx.tell_director(
                        f"attire: the condition on {name}'s {_handle!r} "
                        f"contains the ladder word {_rung_word!r}, which "
                        "moves nothing there. The ladder moves through "
                        "`remove`/a decisive act; a condition is what "
                        "happened to the fabric.")
                    ctx.add_warning(
                        f"attire: rung word {_rung_word!r} written into "
                        f"{name}'s condition prose")
                if (attire_model.displacement_language(_text)
                        and _resolved not in _cov_handles):
                    ctx.tell_director(
                        f"attire: the condition on {name}'s {_handle!r} "
                        "describes a coverage change the ledger cannot read "
                        "from prose. If the garment is displaced, also write "
                        "attire." + str(name) + ".coverage = "
                        "{" + repr(str(_handle)) + ": {<region>: [zones "
                        "still covered] or [] for none}}.")
                    ctx.add_warning(
                        f"attire: displacement described only in prose for "
                        f"{name}'s {_handle!r}; coverage unchanged")
        cur["regions"] = _after
        cur["wearing"] = attire_model.flat_wearing(_after)
        # A GARMENT WHOSE COVERAGE NOTHING KNEW, said out loud. `region_of`
        # never fails -- it falls to the torso -- and the fallback was silent,
        # so a qipao, a thawb, a sari or a nagajuban the cue tables have not
        # learnt sits on the torso alone and the body reports legs and groin
        # bare while wearing one. `guessed_spans` has been able to spot that
        # since it was written and had no production caller: its own docstring
        # described this hand-off in the present tense while the loop stayed
        # open. Measured while open: 110 of 560 live worn garment records
        # carry a guessed span, twenty of them a full-length under-kimono.
        #
        # Told to the DIRECTOR rather than repaired here, because repairing it
        # needs the fiction: the cue tables are the thing that does not know,
        # so a second deterministic guess would be the same guess. The
        # Director can answer with `coverage`, and authored coverage is never
        # re-guessed, so this cannot nag about a choice somebody has made.
        if report:
            for _guessed in attire_model.guessed_spans(_after):
                ctx.tell_director(
                    f"attire: nothing knows what {name}'s {_guessed!r} "
                    "covers, so it is on the torso by default. If it covers "
                    "more, say so once: attire." + str(name) + ".coverage = "
                    "{" + repr(str(_guessed)) + ": {<region>: []}}.")
        # A derived-shaped note is always ours to rebuild, current or not --
        # the same rule `rederive_entry` applies on every read path
        # (`attire.is_derived_state_note`; chat 52 carried three stale notes
        # at once and earned it). This seam used to keep a weaker hand-rolled
        # form: a stale "bare at the ..." was dropped only when the old
        # string was a SUBSTRING of the new note, i.e. only when the bare set
        # grew by appending regions in the same order. The moment a garment
        # re-covered a region, containment failed and the stale note survived
        # as though authored. Measured (chat 76, turns 57/59/60): the STORED
        # ledger held "bare at the head, arms", "bare at the head, torso,
        # arms, waist, groin, legs" and "bare at the head, arms, waist,
        # groin, legs" at once -- every reader healed the contradiction
        # through `rederive_entry` on the way out, while the stored shape,
        # which the attire panel, exports and checkpoints read raw, kept all
        # three. Rebuilt unconditionally, not gated on `_notes` being
        # non-empty: a body dressed again derives NO notes, and that is
        # exactly the beat the last "bare at the" note must leave on.
        # Authored prose survives -- keeping it is the point of `state`
        # being a list.
        _notes = attire_model.flat_state(_after)
        _authored = [
            n for n in (cur.get("state") or [])
            if isinstance(n, str) and n.strip() and n not in _notes
            and not attire_model.is_derived_state_note(n)
        ]
        cur["state"] = _notes + _authored
        _had = {g["name"].casefold()
                for entry in _before.values()
                for g in (entry.get("garments") or [])
                if g.get("state") != "removed"}
        for _entry in _after.values():
            for _g in _entry.get("garments") or []:
                if (_g.get("state") != "removed"
                        and _g["name"].casefold() not in _had):
                    _gained.add(_g["name"].casefold())
        for _region, _garment in attire_model.newly_removed(_before, _after):
            _shed.append((name, _garment,
                          attire_model.condition_of(_after, _garment)))

    _fold_worn_garment_entities(sc, diff, ctx)
    _mint_shed_garments(
        sc, [s for s in _shed if s[1].casefold() not in _gained], diff)
    # Heals scenes that accumulated duplicates BEFORE adopt-or-mint
    # existed, and is idempotent, so it costs nothing on a clean scene.
    _fold_duplicate_shed_garments(sc, diff, ctx)
    # A REMOVED GARMENT IS AN OBJECT IN THE WORLD, NOT A FACT ABOUT A BODY.
    # It kept a seat in its former wearer's regions -- `state: "removed"`,
    # under `torso`/`waist`/`arms` -- and every relation that seat carried was
    # a relation to a body it had left. The floor object above is the garment
    # now; two records of one thing is how they disagree.
    #
    # Measured live (chat 70): the jacket sat `removed` across three of
    # Hinami's regions while lying on the stone in another room, so the
    # Director removed it a second time and the narrator narrated it a third.
    #
    # AFTER the mint, never before: `newly_removed` reads the transition out
    # of these very entries, so pruning earlier would mean nothing ever
    # reached the floor. Once the object exists, the seat is a duplicate --
    # and the region is simply uncovered, free to be filled by any attire,
    # makeshift or otherwise.
    for _name, _entry in (sc.get("attire") or {}).items():
        if isinstance(_entry, dict):
            attire_model.release_removed_garments(_entry)
    return sc
