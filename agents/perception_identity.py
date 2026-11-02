"""Who and what an observer may name: the identity roster and the chat's
identity space, worn roles and charter titles, recognition and attributed
labels, stranger labels and self-forms, presence bodies laid on the stage
scene, co-present company, body-vs-thing tests, known places and far
regions, and the present-tense label function other stages read.

Carved verbatim from `agents/perception.py` on 2026-11-01;
`agents/perception.py` is now a facade that re-exports every name defined
here (docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

from language_runtime import LanguagePackError, compositor_text
from story.character_schema import (
    character_appearance,
    character_name,
    normalized_character_of_row,
)
from core.db import q, wget
from story.scene import (
    appearance_of,
    disguise_breaks_recognition,
    persona_of,
    sheet_state,
)
from world.spatial import (
    ambient_scope,
    _entity_named,
    entity_arc,
    entity_side,
    sighted_level,
    visual_level_between,
    proximity_rel,
    room_of,
)
from . import composer
from .common import (
    self_reference_forms,
    _appearance_as_prose,
    presence_figures_for_room,
    _recognizes,
    _strip_identity_tokens,
    _unknown_actor_label,
    character_scene_keys,
)

from agents.perception_common import described_by
from agents.perception_bodies import _subject_disguise_context


def _ambient_location_for(sc, room_id):
    """Per-perceiver ambient/location scoping by nesting depth (item 5,
    coarse): the outermost place whose ambience legitimately reaches this
    room. Open to the world -> the scene's location as usual. Sealed
    inside a nested interior (a vehicle mid-transit, a closed elevator)
    -> only the enclosure itself; the outer location's name/ambience must
    not color that perceiver's view. Derived from scene containment
    (spatial.ambient_scope) only -- never from lorebook links."""
    if not room_id:
        return sc.get("location")
    _, open_to_world = ambient_scope(sc, room_id)
    if open_to_world:
        return sc.get("location")
    room = (sc.get("rooms") or {}).get(room_id) or {}
    eid = room.get("parent_entity")
    ent = (sc.get("entities") or {}).get(eid) if eid else None
    label = ((ent or {}).get("name") if isinstance(ent, dict) else None) \
        or eid or room.get("name") or room_id
    return (f"inside {label} (sealed interior -- the outer location's "
            "ambience does not reach here)")

def _identity_roster(p_name, p_appearance, cast, scene=None, bodies=(),
                     titles_of=None):
    """Every identity in play this beat, with the forms (name + uid/aliases)
    and appearance the identity scrub needs: the player plus each cast
    member, and -- given the scene -- every other BODY it stands as an
    entity. Callers extend it with extra players / background speakers.

    A person the scene stands is somebody whose name an observer may not
    have. Only the cast was listed, so a charter body's name written into
    the observer's OWN pose ("head turned toward Master Kenelmund") passed
    the last scrub and was filed to memory by a woman who never learned it
    (playerless Aldermill round 4, 2026-09-23, t22)."""
    roster = [{"name": p_name, "appearance": p_appearance, "aliases": []}]
    for c in cast:
        sh, _, _ = sheet_state(c)
        keys = character_scene_keys(sh)
        roster.append({
            "name": character_name(sh),
            "appearance": character_appearance(sh),
            "aliases": keys[1:],
        })
    listed = {str(r["name"] or "").casefold() for r in roster}
    if isinstance(scene, dict):
        from world.spatial import _is_body_entity
        for eid, ent in sorted((scene.get("entities") or {}).items()):
            if not isinstance(ent, dict) or not _is_body_entity(scene, eid, ent):
                continue
            name = str(ent.get("name") or eid).strip()
            if not name or name.casefold() in listed:
                continue
            listed.add(name.casefold())
            roster.append({
                "name": name, "appearance": ent.get("appearance"),
                "aliases": [a for a in (ent.get("aliases") or []) if a],
                **_worn_identity(name, bodies, scene, titles_of)})
    # AND EVERY BODY THIS BEAT LAID IN VIEW. A charter body the scene does
    # not stand is laid for the stage alone, so it is in no ledger the lines
    # above read -- and a given name the encoder wrote into the observer's
    # own pose ("watching Kenricer's back") reached her view and her memory
    # (playerless Aldermill round 5, 2026-09-23, idx 23).
    for body in bodies or ():
        name = str((body or {}).get("name") or "").strip()
        if not name or name.casefold() in listed:
            continue
        listed.add(name.casefold())
        roster.append({
            "name": name, "appearance": body.get("appearance"),
            "aliases": [a for a in (body.get("aliases") or []) if a],
            **_worn_role(name, bodies)})
    return roster


def _charter_titles_of(ctx, sc):
    """`entity -> [titles]` over the stage's charters (`charter_titles`), or
    None outside a stage that can read them."""
    from agents.common import charter_titles, chatter_inputs
    try:
        charters = chatter_inputs(ctx.chat.id, sc, turn_idx=ctx.turn.idx).get(
            "charters") or []
    except Exception:
        return None
    by_key = {str(c.get("key") or ""): c for c in charters if isinstance(c, dict)}

    def titles_of(ent):
        ref = (ent or {}).get("charter_ref") if isinstance(ent, dict) else None
        if not isinstance(ref, dict):
            return []
        return charter_titles(by_key.get(str(ref.get("charter") or "")),
                              ref.get("body"))
    return titles_of


def _worn_identity(name, bodies, scene=None, titles_of=None):
    """What a body WEARS in its name rather than is called by: `_worn_role`
    for a laid body, and for one the scene stands, the titles its charter
    styles people with (`_charter_titles_of`). A BODY THE SCENE STANDS IS NO
    LAID BODY: the leased sluice wardens were entities, so "Sluice" stayed a
    part of their names (playerless Aldermill round 9, 2026-09-23).

    ONE READER FOR EVERY ROSTER. The outcome composer builds its own roster
    by hand, and it never asked `_worn_role` -- round 8's exemption held in
    the act views and failed in every outcome view, which is where the
    room names were rewritten."""
    worn = _worn_role(name, bodies)
    if "titles" in worn or titles_of is None or not isinstance(scene, dict):
        return worn
    folded = str(name or "").strip().casefold()
    for ent in (scene.get("entities") or {}).values():
        if isinstance(ent, dict) and str(ent.get("name") or "").strip().casefold() == folded:
            titles = titles_of(ent)
            if titles:
                worn["titles"] = " ".join(titles)
            break
    return worn


def _worn_role(name, bodies):
    """`{role, noun, titles}` of the laid body called `name`, for the scrub:
    a role or a title worn in a name is not identity
    (`_scrub_unknown_identities`)."""
    for body in bodies or ():
        if str((body or {}).get("name") or "").strip().casefold() == name.casefold():
            out = {k: str(body.get(k) or "") for k in ("role", "noun")
                   if str(body.get(k) or "").strip()}
            titles = [str(t) for t in (body.get("titles") or []) if str(t or "").strip()]
            if titles:
                out["titles"] = " ".join(titles)
            return out
    return {}


def _character_known_places(row):
    """{room id: the name this mind knows it by} -- the far layer's ruling
    3, a far place named only once the mind knows it (`world/landscape`).
    Its place graph's nodes, the rooms it walked or looked into, by the
    name it learned each under (`commit_place_graph.update_place_graph`
    rewrites a name only when the mind stands in or sees the room again);
    and the rooms it has stood in, by their name now ("")."""
    from story.scene import cast_state
    state = cast_state(row) or {}
    graph = state.get("place_graph") if isinstance(state.get("place_graph"), dict) else {}
    out = {}
    for rid, node in (graph.get("nodes") or {}).items():
        if isinstance(node, dict):
            out[str(rid)] = str(node.get("name") or "").strip()
    for rid in state.get("visited_rooms") or ():
        out.setdefault(str(rid), "")
    return out


def _player_known_places(ctx):
    """{room id: ""} -- the rooms the player has stood in, by their name now:
    the `subject_last_seen` stamps the commit writes every beat, where the
    player's own room is stamped under its own key (`world.gaps`). Only
    those keys: the ledger shares its namespace with every subject the
    player saw, so a key counts when its stamp's room IS the key."""
    from world.gaps import LAST_SEEN_KEY
    ledger = wget(ctx.chat.id, LAST_SEEN_KEY, {}) or {}
    return {str(key): "" for key, stamp in ledger.items()
            if isinstance(stamp, dict) and str(stamp.get("room") or "") == str(key)}


def _far_regions(ctx):
    """The frame's region registry (`world.regions.region_registry`,
    planted structures included), {region id: {name, far_look, ...}}, for
    the far layer (`world/landscape`): a region's `far_look` is how a place
    of it with none of its own reads at the outline, and a region's `name`
    is one a look may not carry. Read once per stage; a world with no
    regions gets {} and the far layer reads as before.

    A FAILED READ FAILS CLOSED (review 2026-10-08, R2-3): it is logged and
    handed on as `landscape.REGIONS_UNREAD`, which withholds every far look
    of the view -- read as "no regions", the floor knew no region's name to
    withhold, and a look naming the town was said to a stranger. Never a
    failed view: the places read by their ground."""
    from world.landscape import REGIONS_UNREAD
    try:
        from world.regions import region_registry
        return region_registry(ctx.chat.id, getattr(ctx.turn, "frame_id", None))
    except Exception as exc:
        from core.logging_utils import logger
        logger.warning("perception: the region registry is unavailable, so no far "
                       "look is said this stage: %s", exc)
        return REGIONS_UNREAD


def _presence_bodies(ctx, sc, rooms, chatter):
    """The unregistered bodies standing in the rooms this stage composes for,
    in the co-present body shape, PLACED on the stage's own scene.

    Presence is what a view is composed from, and this stage's roster was
    the cast and the players -- so a body the simulation puts in the room
    with you was in nobody's view unless it happened to speak this beat.
    `common.presence_figures_for_room` decides WHO (the ledger's people
    standing here, plus the charter bodies no derived crowd carries); this
    decides only that they are bodies like any other, which is the whole
    correction.

    THE SCENE COPY, NEVER THE STORE. `get_scene` hands every caller a fresh
    parse and nothing here is persisted: the position exists for the length
    of this stage because `visual_level_between`, `entity_arc` and
    `proximity_rel` all begin by asking the scene where a body is, and a
    body the scene places nowhere is failed CLOSED by every one of them
    (`spatial_identity.room_of`'s own note). Written only where `room_of`
    has no answer already -- a presence the Director minted as a scene
    entity is placed, and re-keying it under its display name would put one
    being in the room twice. The registry stays the single source of truth
    for where a charter body IS; `presence_room` is the resolver both this
    and the voice gate read, so a person cannot be in one room for being
    seen and another for being spoken to.

    The firewall reading is that this ADDS nothing an observer did not have
    a channel to. Every one of these bodies goes through the same
    subtractions a cast body does -- unlit, contained, behind a barrier or
    in the rear arc and it never becomes a percept -- and
    `observer_display_map` hands back a descriptor, not a name, to anyone
    who has not met them. What changes is that the guards get to run at all.
    """
    rows, seen = [], set()
    # The observed rooms AND the rooms `room_field` lays beyond their open
    # doorways: a body standing in the next room is in the observer's line
    # exactly as a cast member there is, and is graded by the same doorway
    # cone (`presence_percepts`' "beyond" tier). Nothing further is laid.
    from world.charter_place import lay_charter_bodies, rooms_in_frame
    placements, keys = {}, {}
    for room in rooms_in_frame(sc, rooms):
        for row in presence_figures_for_room(
                ctx.chat.id, sc, room, chatter,
                turn_idx=ctx.turn.idx,
                frame_id=getattr(ctx.turn, "frame_id", None)):
            name = str(row.get("name") or "")
            if not name or name.casefold() in seen:
                continue
            seen.add(name.casefold())
            placed = row.get("placement") if isinstance(
                row.get("placement"), dict) else None
            if placed and not room_of(sc, name):
                # AT ITS CELL, not merely in its room: the positions row,
                # the station and the facing `world.charter_place` derived,
                # laid on this stage's copy under the record's own name so
                # `visual_level_between`, `body_visibility`, `light_at` and
                # the sound field read it as they read a cast body's.
                placements[placed["uid"]] = placed
                keys[placed["uid"]] = name
            elif not room_of(sc, name):
                sc.setdefault("positions", {})[name] = row["room"]
            rows.append({
                "name": name, "room": row["room"],
                "appearance": row.get("appearance") or "",
                # The public noun the body's own institution gives it, carried
                # beside the summary rather than folded into it: a minted
                # display name puts the same noun in front of the personal
                # name, and without this the identity strip deletes the
                # description whole (`common._unknown_actor_label`).
                "role": row.get("role") or "",
                **({"noun": row["noun"]} if row.get("noun") else {}),
                **({"titles": list(row["titles"])} if row.get("titles") else {}),
                "aliases": [],
                # Its dealt surface, when the registry has one, so the
                # display map can compose a silhouette at dim light and a
                # face at full (`composer.observer_display_map`).
                **({"surface": row["surface"]}
                   if isinstance(row.get("surface"), dict) else {}),
                # An unregistered body wears no disguise ledger: there is no
                # card to conceal and no `known_to` list to consult, so both
                # halves are stated rather than left absent (an absent
                # `disguise_conceals_identity` reads as "does not conceal",
                # which is true here and must stay true by construction).
                "disguise_known_to": [],
                "disguise_conceals_identity": False,
            })
    if placements:
        lay_charter_bodies(sc, placements, keys=keys)
    # And the people this beat brought in, by the one reader the voices'
    # figures use (`common.beat_people_rows`): a person the scene stands is a
    # body in the view, never "There is Abel Gale here."
    try:
        from .common import beat_people_rows
        for row in beat_people_rows(ctx, sc, rooms, seen):
            rows.append({**row, "role": "", "disguise_known_to": [],
                         "disguise_conceals_identity": False})
    except Exception as exc:
        if hasattr(ctx, "add_warning"):
            ctx.add_warning(f"the beat's own people not laid as bodies: {exc}")
    return rows


def _charter_place_before(ctx, scene, name):
    """The room the charter held `name` in before this beat's commit, or None.

    For a body the scene stands with a `charter_ref`: the registry is still
    the pre-beat one while perception runs (the lease writes it back at
    commit), so its `place` is where the body stood when the beat began."""
    from world.spatial import _unique_entity_keyed
    _, ent = _unique_entity_keyed(scene or {}, name)
    ref = (ent or {}).get("charter_ref") if isinstance(ent, dict) else None
    if not isinstance(ref, dict) or not ref.get("charter") or not ref.get("body"):
        return None
    try:
        from world.charter_runtime import registry_for
        registry = registry_for(ctx.chat.id, getattr(ctx.turn, "frame_id", None))
    except Exception:
        return None
    body = (((((registry or {}).get("items") or {}).get(str(ref["charter"])) or {})
             .get("state") or {}).get("bodies") or {}).get(str(ref["body"]))
    place = str((body or {}).get("place") or "").strip() if isinstance(body, dict) else ""
    return place or None


def _co_present_company(scene, observer_name, bodies, known):
    """proximity_to_sources / behind_sources entries for the bodies simply
    STANDING with an observer at the top of the beat.

    The action-onset pass runs BEFORE the interaction loop, so
    `ctx.character_results` is empty and no cast member qualifies as a
    source the way the outcome pass admits them ("did their character step
    produce something"). The only channels that could carry a co-present
    body into a pass-1 payload were therefore the acting player (the
    `*_to_actor` fields), the observer's single `orientation.focus` slot,
    and the contact/scale/containment ledgers -- so two recognised
    characters standing in one lit room did not appear in each other's
    action-onset payloads at all. Because focus is ONE slot, the failure
    looked intermittent and one-directional (chat 63, reported three
    times: Tamamo, focused on the Doctor, sometimes saw him; he, focused
    on a doorway, never saw her).

    Delivered through the two fields the perception prompt already
    describes for co-located people, and as PRESENCE -- a tier, a side, an
    arc -- never anything act-shaped: the contacts ledger already taught
    this module that a bare relation record reads as an event and gets
    narrated as one.

    A roster is also a brand-new channel handing a mind other bodies, and
    the pass-1 output scrub floors only the PLAYER's identity -- so the
    identity floor is applied INPUT-side, per observer, before the payload
    exists:

    - a body `visual_level_between` answers "none" for (unlit, concealed
      by containment, behind a barrier) does not arrive at all;
    - a recognised body arrives under its name, carrying `sight` so a
      "shapes" sighting degrades honestly rather than growing a face;
    - an unrecognised body seen in full arrives as its unknown-actor
      descriptor, built from its disguise-adjusted VISIBLE appearance;
    - an unrecognised body seen only as shapes is a bare figure: its
      appearance summary describes what full sight would show, and a
      silhouette shows none of it;
    - a disguised body whose truth this observer is not in `known_to` for
      is never connected to its name, however well the observer knows
      the name -- that connection is the thing the disguise conceals.

    Every one of those five is `composer.observer_display_map`'s rule, and
    the labels are now READ from it rather than restated here. They were
    restated, and the restatement was the correct half of a pair that
    disagreed: one body could be a silhouette in this payload and an
    appearance epithet in the composed view of the same beat. A second copy
    of a naming rule is a classifier waiting to drift, exactly as the
    admission comment in `presence_percepts` says of a second copy of an
    admission rule. What stays local is the DEDUPE: this field is a dict
    keyed by label, and two bodies the observer genuinely cannot tell apart
    share one label by design, so they need distinct keys to both survive.
    """
    display = composer.observer_display_map(scene, observer_name, bodies, known)
    prox, behind = {}, []
    for body in bodies:
        name = body.get("name")
        if not name or name == observer_name:
            continue
        level = visual_level_between(scene, observer_name, name)
        if level == "none":
            continue
        tier = proximity_rel(scene, observer_name, name)
        if tier is None:
            continue            # co-located only, like the field it feeds
        label = display.get(name)
        if not label:
            continue
        stem, n = label, 2
        while label in prox:    # two strangers can share a descriptor
            label, n = f"{stem} ({n})", n + 1
        entry = {
            "tier": tier,
            "side": entity_side(scene, observer_name, name),
            "arc": entity_arc(scene, observer_name, name),
            "sight": level,
        }
        prox[label] = entry
        if entry["arc"] == "rear":
            behind.append(label)
    return prox, behind


def identity_bearing_sources(sources, scene=None):
    """The act sources that carry an IDENTITY an observer may or may not
    have earned -- every one but a crowd's chorus, and, given the scene,
    every one the scene shows is a thing or a place.

    A chorus is the crowd answering as one, named by its composition
    (`background._chorus_entry`: "cousins and mistress"). Filed into the
    identity roster, that composition was scrubbed from every view of an
    observer who "did not recognise" it, and the scrub's per-word forms
    took the word "and" with it: "a chapel of dark slate the unfamiliar
    person granite" (scratch play 2026-09-14, chat 7 turn 3). A crowd has
    no name to withhold; its act is delivered like any other and its
    composition is prose.

    A THING HAS NO ACQUAINTANCE TO EARN EITHER. Recognition is a fact about
    bodies; a boat's name is the world's name for it, and the view already
    says it wherever it names a room ("the deck of the Grebe"). Filed as an
    identity because it was a beat's source, the boat was scrubbed to the
    person fallback in the player's view and memory -- "You are in the deck
    of the unfamiliar person", "You feel the unfamiliar person's thwart"
    (scratch story 166, turn 4597). `_source_is_a_body` decides, and it is
    conservative in the direction the firewall needs: a source the scene
    cannot show to be a thing or a room still bears an identity.
    """
    return [s for s in (sources or ()) if isinstance(s, dict)
            and not s.get("chorus")
            and (scene is None or _source_is_a_body(scene, s.get("name")))]


def _source_is_a_body(sc, name):
    """Is a beat's source somebody, rather than a place or a thing? A room
    the scene holds (by id or by its name) is a place; an entity the
    engine's own test calls inert is a thing (`_mover_is_a_body`); anything
    else -- a cast member, a presence, a name the scene has no record of --
    is a body, so a miss here keeps an identity rather than dropping one."""
    text = str(name or "").strip()
    if not text:
        return False
    rooms = (sc or {}).get("rooms") or {}
    if isinstance(rooms, dict) and (text in rooms or any(
            isinstance(room, dict)
            and str(room.get("name") or "").strip().casefold() == text.casefold()
            for room in rooms.values())):
        return False
    return _mover_is_a_body(sc, text)


def _thing_label(sc, name):
    """What a thing that acts is called: its own name, as the scene holds
    it -- never a person's label, which is what the act renderer gave the
    Grebe when the tide rocked it ("The unfamiliar person rocks once")."""
    from world.spatial import _entity_named
    entity = _entity_named(sc, name) or {}
    return str(entity.get("name") or name or "").strip()


def _composer_unknown_sources(name, known, roster, bodies_by_name=None):
    """(recognized, unknown) for one observer: the bodies whose canonical
    forms may stand in this observer's view, and the roster entries whose
    forms must be scrubbed from it.

    A DISGUISE THAT CONCEALS IDENTITY MAKES AN ACQUAINTANCE A STRANGER FOR
    THIS BEAT. `observer_display_map` has said so since the disguise seam
    was built; this pair, which every act surface and authored line is
    scrubbed against, read the bare `known` ledger alone -- so the same view
    called a masked body a stranger in its presence line and named it in
    the act it performed. When the caller can supply the beat's body
    records (`bodies_by_name`, carrying `disguise_known_to` and
    `disguise_conceals_identity`), a hidden body leaves `recognized` and
    joins `unknown`; without them the ledger alone decides, as before.
    """
    recognized = set(known.get(name) or [])
    records = bodies_by_name or {}

    def _hidden(body):
        record = records.get(body) or {}
        return disguise_breaks_recognition(
            record.get("disguise_known_to"), name,
            record.get("disguise_conceals_identity"))

    hidden = {s["name"] for s in roster if s["name"] != name and _hidden(s["name"])}
    if hidden:
        recognized = {form for form in recognized
                      if not any(_recognizes(body, {form}) for body in hidden)}
    return recognized, [
        s for s in roster
        if s["name"] != name
        and (s["name"] in hidden or not _recognizes(s["name"], recognized))
    ]


def _unseen_voice_label():
    """What a speaker the listener can neither see nor recognise is called:
    the channel's own word for a body it cannot place, in the story's
    language (`unseen_voice_label`) -- never a name. It was the English
    literal "a voice" in every pack, so a Japanese view read 「…」とa voice
    が言うのが聞こえる (DESIGN_SOUND_FIELD § 12, wave A)."""
    try:
        return compositor_text("unseen_voice_label")
    except LanguagePackError:
        return "a voice"


def _attributed_label(body, observer, *, recognized, display_map,
                      bodies_by_name, can_see, unseen, appearances,
                      cast_aliases):
    """ONE LABEL PER (OBSERVER, BODY) PER BEAT, whichever branch asks.

    The outcome pass attributed speech, communication and acts by testing
    the `known` ledger FIRST and consulting the disguise-aware display map
    only for strangers, so an acquaintance not in `disguise_known_to`
    received the canonical name for everything the masked body said and
    did while the same view described it as a stranger. The act stage
    read the map first. This is the one order for all of them:

    * recognised, and no identity-concealing disguise -- the name, seen or
      not (a known voice is knowledge the observer already holds);
    * otherwise seen -- the display map's label (the jointly assigned
      stranger descriptor or silhouette), or the appearance-derived
      fallback when the body was outside the map's roster;
    * otherwise -- `unseen`, the channel's own word for a body it cannot
      place ("a voice").
    """
    record = (bodies_by_name or {}).get(body) or {}
    hidden = disguise_breaks_recognition(
        record.get("disguise_known_to"), observer,
        record.get("disguise_conceals_identity"))
    if not hidden and _recognizes(body, recognized):
        return body
    if not can_see:
        return unseen
    return display_map.get(body) or _unknown_actor_label(
        body, _strip_identity_tokens(
            appearances.get(body),
            [body, *(cast_aliases.get(body) or [])]))


def _joint_stranger_labels(bodies):
    """The label every body would get if nobody recognized anybody -- the
    superset of the epithets this beat can put into circulation.

    A per-observer display map deliberately leaves the observer OUT of its own
    map, so it can never say what the rest of the room is calling that
    observer. This assignment includes everyone, so `_composer_self_forms`
    below can hand a mind the widened or ordinal-distinguished form of its own
    epithet as well as the base one. It decides nothing about admission: it is
    only ever read to rewrite a body's own epithet into "you"."""
    return composer.assign_stranger_labels([
        (b.get("name"), b.get("appearance"), b.get("aliases") or [],
         str(b.get("role") or ""))
        for b in bodies or [] if b.get("name")
    ])


def _composer_self_forms(name, base_forms, body, joint_labels, display_map):
    """One observer's complete self-reference forms: their names, plus the
    epithets the engine minted FOR them (`common.self_reference_forms`).

    Engine-supplied prose reaches a view written in the third person about
    everyone in it, and `_self_second_person` turns the receiving mind's own
    handles into "you". It only ever knew names, so a beat that referred to a
    body by the descriptor OTHER minds use for it walked straight past --
    which is how a player read "the sword at the apprentice's hip" in his own
    view, about his own sword.

    `display_map` is what this observer calls everyone ELSE, and is passed as
    the collision guard: a form this observer is already using for another
    body is never claimed as self-reference."""
    forms = list(base_forms or [name])
    if not body:
        # No body record for this perceiver this beat (an observer in another
        # room, an extra player who is not in the roster). Minting an epithet
        # from nothing yields `_unknown_actor_label`'s universal fallback,
        # which every appearance-less body shares -- and a form shared with a
        # body outside this observer's display map is one the collision guard
        # below cannot see. Decline instead.
        return forms
    epithets = self_reference_forms(
        name,
        (body or {}).get("appearance"),
        (body or {}).get("aliases") or [],
        labels=[(joint_labels or {}).get(name)],
        avoid=list((display_map or {}).values()),
    )
    seen = {str(f).casefold() for f in forms}
    for form in epithets:
        if form.casefold() not in seen:
            seen.add(form.casefold())
            forms.append(form)
    return forms


def _composer_identity_space(ctx, p_name, p_appearance):
    """Every name this chat can leak -- not just the ones on stage tonight.

    `_identity_roster` is built from `ctx.cast`, and `active_cast` filters
    to `status='active'`. So a character who left the scene, went dormant or
    died is OFF the roster while their name stays written into room notes,
    authored overlays and ambient prose. The corpus replay measured the
    consequence: 69 surviving identity leaks in composed views, dominated by
    `room_notes` naming an off-roster character, with no tripwire coverage
    at all -- a player view carried a never-met character's name out of a
    room note and nothing warned, because the roster the tripwire checks
    against had never heard of her either.

    Recognition still decides. A name in here is scrubbed only for an
    observer who has not earned it; someone who knows Hinami keeps reading
    "Hinami", and someone who does not reads the fox-eared woman with six
    tails. The space is who COULD be leaked, not who must be hidden.

    Cached per turn: it is three cheap reads and it is asked for once per
    observer per stage.
    """
    cache_key = "_composer_identity_space_cache"
    cached = ctx.get(cache_key)
    if cached is not None:
        return cached
    space = _identity_roster(p_name, p_appearance, ctx.cast)
    seen = {str(s["name"]).casefold() for s in space if s.get("name")}
    rows = q(
        "SELECT COALESCE(cc.sheet, ch.sheet) AS sheet FROM chat_chars cc "
        "JOIN characters ch ON ch.id = cc.char_id WHERE cc.chat_id=?",
        (ctx.chat.id,),
    )
    for row in rows:
        # Name, scene keys and appearance were three normalizations of the
        # same card; the memo makes them one per distinct sheet text (C14).
        sheet = normalized_character_of_row(row)
        if sheet is None:
            continue
        name = character_name(sheet)
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        keys = character_scene_keys(sheet)
        space.append({"name": name,
                      "appearance": character_appearance(sheet),
                      "aliases": keys[1:]})
    for extra in (ctx.extra_players or []):
        name = str((extra or {}).get("name") or "").strip()
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        space.append({"name": name,
                      "appearance": (extra or {}).get("appearance") or "",
                      "aliases": []})
    # AN OBJECT'S NAME IS NOT AN IDENTITY. `background_presences` answers
    # "might this thing act?", and its kind filter is deliberately generous
    # both ways so a sentient robot tagged `device` is never dropped. This
    # space answers a different question -- whose name must be withheld from
    # somebody who has not met them -- and the generous answer is wrong for
    # it: a body in the room can read "Scranton Reality Anchors" off the wall,
    # and doing so tells it nothing about a person.
    #
    # Measured live, chat 82 t1. That array, the PA panel and the elevator car
    # were all tracked presences, so the scrub rewrote the cell's own room
    # note into "the unfamiliar person powered on and functional" -- and the
    # guard who actually spoke that beat got the same label, because every
    # presence with no appearance falls to the same fallback. `commit`'s
    # speech gate already refuses these three by name (its docstring records
    # this exact array interrogating a restrained player twice); it is the
    # same question, so it is the same answer, read from the same function.
    from persist.commit import presence_has_an_identity, presence_name_items

    _scene_now = wget(ctx.chat.id, "scene", {}) or {}
    for name, rec in presence_name_items(
            wget(ctx.chat.id, "background_presences", {}) or {}):
        name = str(name or "").strip()
        if not name or name.casefold() in seen:
            continue
        if not presence_has_an_identity(_scene_now, name, rec):
            continue
        seen.add(name.casefold())
        sketch = (rec or {}).get("sketch") if isinstance(rec, dict) else {}
        space.append({
            "name": name,
            "appearance": str((sketch or {}).get("appearance") or ""),
            "aliases": [],
        })
    ctx[cache_key] = space
    return space


def _mover_is_a_body(sc, mover):
    """Does this `positions` key name somebody, or something.

    A crossing percept says "a figure" about whatever it is handed, and
    `state_diff.positions` is not a roster of people -- AGENTS.md's
    body-enclosure row: it "legitimately keys objects and unregistered
    presences by entity id" beside cast bodies keyed by display name. So a
    crate carried from one room to the next arrived in every view at either
    end as a person walking in.

    The engine already answers this question once, in
    `commit_background._is_inert_presence_candidate` -- an inert `kind`, or
    portable and neither animate-kinded nor wearing anything -- and it is
    conservative in the direction this needs. It calls something a thing
    only when that is demonstrable, so an undressed unregistered presence
    stays a body, and a mover with no entity record at all (every cast
    member) is a body without being asked.
    """
    from persist.commit import _is_inert_presence_candidate
    entity = _entity_named(sc, mover)
    if not entity:
        return True
    return not _is_inert_presence_candidate(sc, mover, entity)


def present_label_fn(ctx, observer_key, observer_name, scene, senses=None):
    """`name -> what a present-tense field may call this body`, for one
    observer: by the rule the composed view names bodies by, for the bodies
    the view did not show this beat as much as for those it did
    (formerly UNBUILT_PIPELINE §1.176).

    A NAME only if this observer knows it AND no disguise hides who the body
    is (`scene.disguise_breaks_recognition`, as `composer.observer_display_map`
    asks). An APPEARANCE only of the body's outward form -- a disguise's, not
    the card's -- and only if the body is seen now, or this observer's view
    once described it (`described_by`): a descriptor learned at a sighting is
    knowledge the mind keeps; one minted for a body nobody ever saw is a
    leak. Otherwise the unfamiliar person. Short of full sight the view's own
    silhouette (`common.observer_view_label_fn`).

    Live in three fields beside a view that said otherwise (review of the
    re-applied leak fixes, 2026-10-05): a stranger's hand on a shoulder in a
    dark cellar was "the tall fox-eared woman's hand" to the narrator's touch
    line and the character's own contact list, and her real name when she
    was an acquaintance in a disguise that hides who she is; a focus on a
    stranger nobody could see named her the same way.
    """
    from story.character_schema import character_name, persona_appearance, persona_name
    from .common import (_recognizes, character_scene_keys, normalized_character_of_row,
                         observer_view_label_fn)

    chat = {"id": ctx.chat.id, "persona_id": getattr(ctx.chat, "persona_id", None)}
    view_label = observer_view_label_fn(chat, observer_name, ctx.cast, scene, senses)
    known_map = wget(ctx.chat.id, "known", {}) or {}
    described, learned = described_by(ctx, observer_key)
    bodies = {}
    for row in ctx.cast or ():
        sheet = normalized_character_of_row(row)
        name = character_name(sheet) if sheet else ""
        if name:
            bodies[name] = (character_appearance(sheet), character_scene_keys(sheet)[1:])
    pers = persona_of(ctx.chat)
    p_name = (pers.get("name") or persona_name(pers)) if isinstance(pers, dict) else ""
    if p_name:
        bodies.setdefault(p_name, (pers.get("appearance") or persona_appearance(pers),
                                   list((pers.get("identity") or {}).get("aliases") or [])))
    # A second human is a body like any other (review, 2026-10-05: an
    # unrecognised seat passed through as if it were a thing).
    for extra in getattr(ctx, "extra_players", None) or ():
        e_name = str((extra or {}).get("name") or "").strip()
        sheet = (extra or {}).get("persona") or {}
        if e_name:
            bodies.setdefault(e_name, (
                extra.get("appearance") or (persona_appearance(sheet) if sheet else ""),
                list(((sheet.get("identity") or {}) if isinstance(sheet, dict) else {}
                      ).get("aliases") or [])))
    outward_cache = {}

    def outward(name):
        """(the label of the body's outward form when a disguise is in force,
        whether that disguise hides who it is from this observer)"""
        if name not in outward_cache:
            label, hides = None, False
            if name in bodies:
                true_app, aliases = bodies[name]
                true_app = _appearance_as_prose(appearance_of(name, true_app, scene))
                visible, active, known_to, conceals = _subject_disguise_context(
                    ctx, name, true_app, known_map)
                if active:
                    hides = disguise_breaks_recognition(known_to, observer_name, conceals)
                    label = _unknown_actor_label(name, visible, aliases)
            outward_cache[name] = (label, hides)
        return outward_cache[name]

    from .common import _uncarded_person
    recognized = set(known_map.get(observer_name) or [])
    presences = {str((rec or {}).get("name") or key).strip().casefold()
                 for key, rec in ((wget(ctx.chat.id, "background_presences", {}) or {}).items()
                                  if isinstance(wget(ctx.chat.id, "background_presences", {}), dict)
                                  else ())
                 if isinstance(rec, dict)}

    def _is_body(text):
        return (text in bodies or text.casefold() in presences
                or (isinstance(scene, dict) and _uncarded_person(scene, text) is not None))

    def _stranger(text, out):
        """What a stranger is called by sight: the floor's descriptor, or for
        a body it passes through unchanged (a co-player's seat, a presence
        with no record) one composed from its own look, else the unfamiliar
        person."""
        if out != text:
            return out
        look, aliases = bodies.get(text, (None, []))
        if look:
            return _unknown_actor_label(text, look, aliases)
        return composer._unfamiliar_person()

    def label(name):
        text = str(name or "").strip()
        out = view_label(name)
        if not text or text == observer_name or not isinstance(scene, dict):
            return out
        if not _is_body(text):
            return out                      # a thing, left as it is
        disguised_label, hides = outward(text)
        in_scene = bool(room_of(scene, observer_name)) and bool(room_of(scene, text))
        # KNOWN means this observer's own ledger says so -- never "the floor
        # handed the name back": it hands back a seat or a presence it has
        # no record for, and a stranger's name went to the page (review
        # round 3, 2026-10-05). A disguise hides a known body wherever it can
        # be perceived at all -- seen, heard through a door, felt in the dark
        # -- and nowhere else: one in no room of this scene is a reference,
        # not a sighting, and keeps its name (review round 4, 2026-10-05).
        if _recognizes(text, recognized) and (not hides or not in_scene):
            return text
        out = _stranger(text, out) if out == text else out
        if not in_scene:
            # A body in no room of this scene: a reference, not a sighting --
            # the floor's stranger, never a name this observer does not hold.
            return out
        # IN THE BLIND SPOT a body is unseen: no NEW visual detail of a body
        # behind you (`entity_arc`, the cut the view's own presence lines
        # make) -- what this mind learned of it before, or nobody. A character
        # was handed how the player creeping up behind it looked (review
        # round 4, 2026-10-05). One rule with the memory's who-was-there tag
        # (`world.spatial.sighted_level`).
        level = sighted_level(scene, observer_name, text, senses)
        if level == "full":
            return disguised_label or out
        if level == "none":
            key = composer.body_key(text)
            if key in learned:
                return learned[key]         # the form this mind learned
            if described is not None and key in described and not disguised_label:
                return out                  # an older ledger: the form never changed
            return composer._unfamiliar_person()
        # Short of full sight: the view's silhouette -- never a name, and
        # never a face composed for a body the floor passed through.
        view = view_label(name)
        return view if view != text else composer._dim_figure()

    return label
