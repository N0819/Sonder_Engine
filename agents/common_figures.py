"""Who stands where this beat: charter and presence figures, the beat's own
people, creature stances, planned and reserved figures, dwellings, the
player's room ladder and resolver, and the beat's aperture.

Carved verbatim from `agents/common.py` on 2026-11-01; `agents/common.py` is
now a facade that re-exports every name defined here
(docs/design/DESIGN_MODULE_LAYOUT.md).
"""

from __future__ import annotations

import json
from story.character_schema import character_name_from_text, persona_name
from core.db import wget
from core.pipeline_context import note_step_warning
from llm.providers import chat_complete
from llm.prompts import get_prompt
from story.scene import persona_of
from world.spatial import (
    earshot_rooms,
    visible_adjacent_rooms,
    room_of,
    scene_names_body,
)

from agents.common_base import _text
from agents.common_llm import jparse
from agents.common_rooms import charter_ground_for_room, chatter_inputs


def charter_titles(charter, body_key=None):
    """Every title `charter` styles its people with -- its ranks' and its
    posts', and the body's own authored one -- which a minted name puts in
    front of the personal name. A word the name shares with the town, never
    a spelling of the body: scrubbed as a name part, the post "Sluice Warden"
    gave "Sluice", and the room "Mill Race and Sluice" read "Mill Race and
    the weathered heavyset journeyman ..." for every body in it, 75 times over
    11 beats (playerless Aldermill round 9, 2026-09-23) -- the class "Flume"
    (round 7) and "Reeve" (round 8) were each fixed by the word. `charter` is
    the flattened record `chatter_inputs` carries."""
    from world.charter_identity import normalize_naming_profile
    charter = charter if isinstance(charter, dict) else {}
    titles = normalize_naming_profile(charter.get("naming"))["titles"]
    own = ((charter.get("bodies") or {}).get(str(body_key)) or {}).get("title") \
        if body_key else None
    out = []
    for title in [own, *(titles.get("ranks") or {}).values(),
                  *(titles.get("posts") or {}).values()]:
        title = " ".join(str(title or "").split())
        if title and title not in out:
            out.append(title)
    return out


def presence_figures_for_room(cid, sc, room_id, inputs=None, *,
                              turn_idx=None, frame_id=None):
    """The unregistered bodies standing in this room that no crowd carries.

    DESIGN_BACKGROUND_PRESENTATION B2 has two clauses and only one of them
    was ever built. The clause that was: "a charter body is ground (in the
    crowd) exactly when nothing this beat presents it individually" --
    `charter_crowd.members_of` SUBTRACTS bound bodies and bodies with a live
    presence record. The clause that was not: "below the floor of the
    smallest band, members present as individual ambient figures through the
    existing overlay path", and, implicitly, that the bodies the first
    clause subtracts are presented SOMEWHERE. They were not. Perception
    builds every observer's co-present body list out of the cast and the
    players, so a body the crowd let go of entered no view at all.

    Measured live 2026-08-28, chat 98 turns 10-13: five crew whose charter
    `place` was the player's lounge read as "a handful lieutenant commanders
    and ensigns" until each acquired a presence record, at which point
    `crowds_for_room` returned `[]` and the room held nobody in any view --
    while `background_presence_records` still returned all five. A
    subtraction whose matching addition does not exist does not move a
    person from one presentation to another; it deletes them.

    Two species, one shape, exactly complementary to `crowds_for_room`:

    * every durable `background_presences` record `presence_room` puts in
      this room -- the same resolver the voice gate and the background stage
      use, so a presence is not in one room for being seen and another for
      being spoken to. `presence_has_an_identity` is the personhood floor,
      borrowed rather than restated: it is already the predicate that
      decides a tracked name is a person's to withhold, and a ceiling-
      mounted suppression fixture with an accrued record is not somebody
      standing there (chat 82 t1, where one rendered as "the unfamiliar
      person" in the room's own description);
    * every charter body derived at this place whose institution holds too
      few here to be a crowd, PLUS the one body each crowd fronts
      (`charter_crowd.crowd_face`). At or above `CHARTER_CROWD_FLOOR` the
      crowd is the presentation of the REST and no body arrives twice --
      including when `charter_crowds_for_room`'s `CO_LOCATED_CAP` drops that
      crowd from the view, because the cap decides how many crowds a room
      shows, never whether an institution's people are ground. The face is
      there because a room full of people that presents none of them cannot
      be spoken to, and the busier it was the worse that got.

    The bound is the room and nothing else: at most
    ``CHARTER_CROWD_FLOOR - 1`` bodies per co-located institution (two, with
    today's floor of three), plus the ledger rows already standing here --
    the same ledger `_composer_identity_space` and the Director's
    `addressable_presences` read whole. Callers scope the ROOMS
    (perception passes the rooms its perceivers stand in), which is what
    keeps a 300-body institution from deriving 300 figures for a back
    office.

    Rows are the co-present body shape: ``name``, ``room``, ``appearance``,
    ``role`` -- the last being the institution's own public noun for the
    body, kept beside the summary because a minted display name carries it
    in front of the personal name and the identity strip would otherwise
    subtract the whole description (`_unknown_actor_label`).
    ``inputs`` is `chatter_inputs`' shared per-stage fetch, memoized per room
    exactly as `charter_crowds_for_room` and `chatter_for_room` are.
    """
    from persist.commit import (presence_has_an_identity, presence_name_items,
                                presence_room)
    from world import charter_crowd

    if not room_id:
        return []
    inputs = (inputs if isinstance(inputs, dict)
              else chatter_inputs(cid, sc, turn_idx=turn_idx))
    memo = inputs.setdefault("figure_memo", {})
    room = str(room_id)
    if room in memo:
        return [dict(row) for row in memo[room]]

    # One ledger read per stage, not per room -- the same discipline
    # `chatter_inputs` applies to the registry.
    ledger = inputs.get("presence_ledger")
    if ledger is None:
        ledger = inputs["presence_ledger"] = (
            wget(cid, "background_presences", {}) or {})

    # Whom the derived crowds carry -- FIRST, because it decides both loops
    # below, and ASKED OF THE ONE READER (`charter_ground_for_room`) rather
    # than recomputed here. This used to run `members_of` a second time over
    # its own `inputs`, and a second answer is an answer that can differ:
    # the crowd and the figures then disagreed about who is ground, in both
    # directions, in one live run (PB4). A record whose presentation has
    # LAPSED (§C3's idle beats) puts its body back in the crowd, and that
    # body must not then arrive here as well: the ledger row still exists,
    # and its history is exactly what lapsing declines to delete.
    ground = charter_ground_for_room(cid, sc, room, inputs, turn_idx=turn_idx)
    carried = ground["carried"]
    carried_names = ground["names"]
    by_key = {str(charter.get("key") or ""): charter
              for charter in inputs.get("charters") or []}

    def _refs_of(record):
        return {(str(r.get("charter") or ""), str(r.get("body") or ""))
                for r in ((record or {}).get("charter_refs") or [])
                if isinstance(r, dict)}

    def _noun_for(refs):
        """What the body IS, on the same terms the crowd's composition says
        it -- a rank or a duty is worn, and an observer in the room reads it
        off the same band these people are members of. Computed only for the
        bodies actually emitted, so a plaza's crowd costs nothing here.

        A CREATURE IS NOT A PERSON WITH NO POST. Its charter holds no posts
        for `member_noun` to read, so the label fell through to the person
        fallback: the well-house thing reached the player at arm's length as
        "the unfamiliar person" (scratch play 2026-09-14, chat 4 turn 9).
        Its own authored `noun` is the word, and a creature that authored
        none is the compositor's unnamed shape -- less, never a face."""
        return _creature_noun_for(refs) or next(
            (noun for noun in (charter_crowd.member_noun(
                by_key.get(charter_key) or {}, body_key)
                for charter_key, body_key in sorted(refs)) if noun), "")

    def _titles_for(refs):
        """The titles a minted name may wear (`charter_titles`)."""
        out = []
        for charter_key, body_key in sorted(refs):
            for title in charter_titles(by_key.get(charter_key), body_key):
                if title not in out:
                    out.append(title)
        return out

    def _creature_noun_for(refs):
        """The word for a creature body, or "" for a person's."""
        from world.charter_creature import normalize_creature
        for charter_key, _body_key in sorted(refs):
            creature = normalize_creature(
                (by_key.get(charter_key) or {}).get("creature"))
            if creature:
                return creature.get("noun") or _text("creature_noun")
        return ""

    def _surface_for(refs):
        """What the body LOOKS like (`world.charter_surface.surface_of`):
        the surface generation dealt it, or the same one dealt now for a
        registry from before the field existed. The stranger label every
        observer builds is cut from this, at the light they see it in."""
        from world.charter_surface import surface_has_content, surface_of
        for charter_key, body_key in sorted(refs):
            charter = by_key.get(charter_key)
            if not charter or body_key not in (charter.get("bodies") or {}):
                continue
            surface = surface_of(charter, body_key)
            if surface_has_content(surface):
                return surface
        return None

    # WHERE IN THE ROOM each body stands (`world.charter_place`): derived
    # from the same slices the crowd reads, once per room per stage, and
    # carried on the row as ``placement`` so the perception stage can lay
    # the body at its cell on its own scene copy. Never persisted.
    placement_memo = inputs.setdefault("placement_memo", {})
    if room not in placement_memo:
        try:
            from world.charter_place import placements_from_slices
            placement_memo[room] = placements_from_slices(
                inputs.get("charters") or [], sc, frame_rooms={room})
        except Exception:
            placement_memo[room] = {}
    placements = placement_memo[room]

    def _placement_for(refs):
        from world.charter_place import placement_uid
        for charter_key, body_key in sorted(refs):
            placed = placements.get(placement_uid(charter_key, body_key))
            if placed:
                return placed
        return None

    def _charter_place(refs):
        """Where the charter holds this body now, or ""."""
        for charter_key, body_key in sorted(refs):
            body = ((by_key.get(charter_key) or {}).get("bodies") or {}).get(body_key)
            place = str((body or {}).get("place") or "") if isinstance(body, dict) else ""
            if place:
                return place
        return ""

    rows, seen, seen_refs = [], set(), set()
    for name, rec in presence_name_items(ledger):
        name = str(name or "").strip()
        if not name or name.casefold() in seen:
            continue
        # A RECORD BACKED BY A CHARTER BODY STANDS WHERE THE CHARTER HOLDS IT
        # unless the scene stands it. `presence_room`'s last rung is the room
        # the record was introduced in -- right for a presence nobody
        # simulates, and a frozen copy of a fact the charter owns for one it
        # does. Read that way, a mill hand the charter had walked to the
        # forecourt stayed at the weir in every view, was voiced there, acted
        # there, and could not be stood because the charter placed him
        # nowhere near it: one body in two rooms for nine beats (playerless
        # Aldermill round 5, 2026-09-23).
        where = presence_room(sc, name, dict(rec or {}, sketch={}))
        if not where:
            where = _charter_place(_refs_of(rec)) or presence_room(sc, name, rec)
        if where != room:
            continue
        if not presence_has_an_identity(sc, name, rec):
            continue
        refs = _refs_of(rec)
        # GROUND BY EITHER NAME THE VIEW HAS FOR IT. A ref says this record
        # is that body; the display name says the same thing, and a record
        # whose refs were never written has only the second. Without it one
        # person arrives as figure and as ground in one paragraph for want
        # of a link nobody stored.
        if (refs & carried) or name.casefold() in carried_names:
            continue
        seen.add(name.casefold())
        seen_refs |= refs
        surface = _surface_for(refs)
        sketch = (rec or {}).get("sketch") or {}
        look = str(sketch.get("appearance") or "") or _noun_for(refs)
        if not look and not refs:
            # A PERSON NO CHARTER STANDS BEHIND -- a Writers'-Room plan, a
            # Director mint -- keeps the look its scene entity carries. The
            # record filed for it holds that look only as `role_hint`
            # (`commit_background`), and this row read `appearance` and the
            # charter's noun alone, so from the beat after the record was
            # filed the body stood in the view faceless: scratch story 166
            # turn 4593, the bell keeper the Room planned ("an old man in a
            # tarred coat ...") spoke and acted as "the unfamiliar person",
            # while the beat path that knew his look deferred to this row.
            bound = ((sc or {}).get("entities") or {}).get(
                str((rec or {}).get("entity_id") or name))
            look = (str((bound or {}).get("description") or "")
                    if isinstance(bound, dict) else "") or str(
                        sketch.get("role_hint") or "")
        row = {
            "name": name, "room": room,
            "appearance": look,
            "role": _noun_for(refs),
        }
        creature_noun = _creature_noun_for(refs)
        if creature_noun:
            row["noun"] = creature_noun
        titles = _titles_for(refs)
        if titles:
            row["titles"] = titles
        if surface:
            from world.charter_surface import appearance_text
            row["surface"] = surface
            if not str(((rec or {}).get("sketch") or {}).get("appearance")
                       or ""):
                row["appearance"] = appearance_text(
                    surface, noun=_noun_for(refs))
        placed = _placement_for(refs)
        if placed:
            row["placement"] = dict(placed)
        rows.append(row)

    try:
        from world.charter_runtime import background_presence_records
        derived = background_presence_records(
            cid, places={room}, frame_id=frame_id)
    except Exception:
        derived = {}
    for name, record in sorted(derived.items()):
        refs = _refs_of(record)
        if (str(name).casefold() in seen or (refs & seen_refs)
                or (refs & carried)
                or str(name).casefold() in carried_names):
            continue
        seen.add(str(name).casefold())
        sketch = (record or {}).get("sketch") or {}
        row = {"name": str(name), "room": room,
               "appearance": str(sketch.get("appearance") or "")
               or _noun_for(refs),
               "role": _noun_for(refs)}
        titles = _titles_for(refs)
        if titles:
            row["titles"] = titles
        if isinstance(sketch.get("surface"), dict):
            row["surface"] = dict(sketch["surface"])
        placed = _placement_for(refs)
        if placed:
            row["placement"] = dict(placed)
        rows.append(row)
    memo[room] = rows
    return [dict(row) for row in rows]


def charter_view_for_rooms(cid, sc, rooms, frame_id=None):
    """``(viewed_scene, [positions key, ...])``: the scene with every
    unpromoted charter body standing in ``rooms`` -- and in the rooms
    `room_field` lays beyond their doorways -- placed at its cell
    (`world.charter_place.scene_with_charter_bodies`), plus the keys those
    rows are filed under. A shallow copy; the stored scene is untouched.

    What `director_resolve`'s movement floor judges a townsperson's move
    from: `_unreachable_position_writes` reads a mover's origin off the
    scene, and a body the scene did not stand was never route-checked at all.
    Fail-open: a story with no charter, or a registry that cannot be read,
    hands back the scene it was given and no keys.
    """
    try:
        from world.charter_place import (charter_placements, rooms_in_frame,
                                         scene_with_charter_bodies)
        from world.charter_runtime import registry_for
        frame = rooms_in_frame(sc, rooms)
        if not frame:
            return sc, []
        placements = charter_placements(
            registry_for(cid, frame_id), sc, frame_rooms=frame)
    except Exception:
        return sc, []
    if not placements:
        return sc, []
    viewed = scene_with_charter_bodies(sc, placements)
    return viewed, [p["key"] for p in placements.values()]


def lay_charter_figures(ctx, sc, rooms):
    """Stand the charter's bodies in ``rooms`` on ``sc`` -- the stage's OWN
    copy, never the store -- and return the rows laid.

    The resolve scene is assembled from the committed scene plus the beat's
    asserted state, and the committed scene holds no charter body: a charter
    body is a derived placement (`charter_place`), which perception lays
    onto its own read every beat and the Director never saw. So the hands
    resolved targets against a room that, to them, held one body -- measured
    (scratch play 2026-09-14, chat 4 turns 9-11): a creature stood one pace
    from the player for three beats and no position, station, contact or
    pose could be written for it, because to the spatial and contact hands
    it did not exist. Same rows and same laying as perception
    (`presence_figures_for_room` + `lay_charter_bodies`); a body the scene
    already stands is left alone. What the Director then writes for one of
    these keys is routed back to the registry at commit
    (`charter_runtime.route_scene_placements`), never stored on the scene.
    """
    from world.charter_place import lay_charter_bodies, rooms_in_frame
    chat = ctx.chat
    cid = chat["id"] if isinstance(chat, dict) else chat.id
    turn_idx = getattr(ctx.turn, "idx", None)
    frame_id = getattr(ctx.turn, "frame_id", None)
    inputs = chatter_inputs(cid, sc, turn_idx=turn_idx)
    rows, seen, placements, keys = [], set(), {}, {}
    for room in rooms_in_frame(sc, rooms):
        for row in presence_figures_for_room(
                cid, sc, room, inputs, turn_idx=turn_idx, frame_id=frame_id):
            name = str(row.get("name") or "")
            if not name or name.casefold() in seen:
                continue
            seen.add(name.casefold())
            placed = row.get("placement") if isinstance(
                row.get("placement"), dict) else None
            if placed and not room_of(sc, name):
                placements[placed["uid"]] = placed
                keys[placed["uid"]] = name
            elif not room_of(sc, name):
                sc.setdefault("positions", {})[name] = row["room"]
            rows.append({"name": name, "room": row["room"],
                         "role": row.get("role") or "",
                         "appearance": row.get("appearance") or "",
                         # The permanent identity, so the voice can find the
                         # body's ledger record however the record is named.
                         **({"charter": placed["charter"],
                             "body": placed["body"]}
                            if placed and placed.get("charter")
                            and placed.get("body") else {})})
    if placements:
        lay_charter_bodies(sc, placements, keys=keys)
    try:
        rows.extend(dict(row, role="")
                    for row in beat_people_rows(ctx, sc, rooms, seen))
    except Exception as exc:
        if hasattr(ctx, "add_warning"):
            ctx.add_warning(f"the beat's own people not laid as figures: {exc}")
    return rows


def beat_people_rows(ctx, sc, rooms, seen):
    """A PERSON THE BEAT MINTED STANDS HERE TOO: ``[{name, room, appearance,
    entity_id, aliases}]`` for the scene's people in ``rooms`` (and the rooms
    laid beyond their doorways) that no presence record or charter body
    covers yet. ``seen`` is the caller's casefolded names, and is extended.

    The presence ledger and the charters are both written at commit, so a
    body this beat brought in was on the stage and in nobody's list of who
    was there: the man the player walked up to by the fire and called "Mr
    Petch" (scratch story 165, turn 4581) heard himself asked for the guild's
    books and the innkeeper answered for him; and a planned man the floor
    stood because the player spoke to him reached the player's own view as
    "There is Abel Gale here." -- a thing, by name (turn 4582). Read by the
    rule commit files a presence by (`scene_person_entities`), off the
    stage's own scene, which already holds the beat's assertions; ONE reader
    for the voices' figures (`lay_charter_figures`) and perception's bodies
    (`perception._presence_bodies`), so who is present cannot differ between
    being spoken to and being seen. A mint bound to a charter body is that
    body's row, laid by the caller."""
    from llm.schemas import _ANIMATE_ENTITY_KINDS
    from persist.commit import (_registered_name_roster, presence_record_for,
                                scene_person_entities)
    from world.charter_place import rooms_in_frame
    roster = {n.casefold() for n in _registered_name_roster(
        ctx.chat, getattr(ctx, "cast", None) or [])}
    roster |= {str(e.get("name") or "").casefold()
               for e in (getattr(ctx, "extra_players", None) or ())}
    in_view = {str(r) for r in rooms_in_frame(sc, rooms)}
    ledger = wget(ctx.chat.id, "background_presences", {}) or {}
    entities = (sc or {}).get("entities") or {}
    rows = []
    for name, person in sorted(scene_person_entities(sc, roster).items()):
        if (name.casefold() in seen
                or person["entity_id"].casefold() in seen
                or person["charter_ref"] or person["room"] not in in_view):
            continue
        # SOMEBODY BY KIND, AND NOT THE LEDGER'S ALREADY. `scene_person_
        # entities` answers "could this speak?", on purpose broad enough to
        # keep a sentient robot trackable; whether it is a PERSON is the
        # presence ledger's verdict (`presence_has_an_identity`), and a body
        # the ledger already judged is `presence_figures_for_room`'s to admit
        # or refuse -- a suppression fixture with a record is a thing, not
        # "the unfamiliar person" (chat 82). Before any record exists, only an
        # explicitly animate kind is laid as a body.
        kind = str((entities.get(person["entity_id"]) or {}).get("kind")
                   or "").strip().casefold()
        if kind not in _ANIMATE_ENTITY_KINDS:
            continue
        if presence_record_for(ledger, name, sc)[1] is not None:
            continue
        seen.add(name.casefold())
        rows.append({"name": name, "room": person["room"],
                     "appearance": person["description"],
                     "entity_id": person["entity_id"],
                     "aliases": list(person["aliases"])})
    return rows


def _creature_stance(cid, charter_key, frame_id=None):
    """What a charter body IS, where its charter says it is a creature:
    ``{hunts, hunger, senses, prey, opens_doors}`` -- or ``{}`` for the
    overwhelming majority of bodies, which are people.

    Read off the charter's own `creature` block and its hunger upkeep, so
    the Director is told the same facts the offscreen simulation acts on
    and the two cannot disagree about what the thing wants. Fail-open: a
    story with no charter, or a body whose charter carries no creature
    block, adds nothing and leaves the payload byte-identical.
    """
    charter_key = str(charter_key or "")
    if not charter_key:
        return {}
    try:
        from world.charter_creature import normalize_creature
        from world.charter_runtime import registry_for
        registry = registry_for(cid, frame_id) or {}
        state = ((registry.get("items") or {}).get(charter_key) or {}
                 ).get("state") or {}
        creature = normalize_creature(state.get("creature"))
        if not creature:
            return {}
        hunger = (state.get("upkeeps") or {}).get("hunger") or {}
        senses = creature.get("senses") or {}
        out = {
            "hunts": [str(p) for p in (creature.get("prey") or ())],
            "senses": {k: senses.get(k) for k in ("hearing", "scent", "sight")
                       if k in senses},
            "opens_doors": bool(creature.get("can_open_doors")),
        }
        # HOW IT SOUNDS DOING EACH THING -- the same table the offscreen
        # noise channel and the onscreen voice read (`creature.voice`), so
        # a hand that writes a sensory event for a creature's act writes it
        # at the creature's own rung rather than guessing one (2026-09-14:
        # the objects hand wrote "faint" for a dragging thing by luck; the
        # reactor had left `activity` empty).
        voice = {k: {"level": str(v.get("level") or ""),
                     "sound": str(v.get("sound") or "")}
                 for k, v in (creature.get("voice") or {}).items()
                 if isinstance(v, dict) and v.get("level")}
        if voice:
            out["voice"] = voice
        rule = str(((state.get("law") or {}).get("purpose")) or "").strip()
        if rule:
            out["rule"] = rule
        level = hunger.get("level")
        floor = hunger.get("floor")
        if level is not None:
            out["hunger"] = round(float(level), 3)
        if floor is not None:
            out["hunger_floor"] = round(float(floor), 3)
        return out
    except Exception:
        return {}


def present_charter_figures(cid, sc, rooms, frame_id=None):
    """Every unpromoted charter body standing in `rooms`, with the post it
    holds -- the DIRECTOR's view of who is already here.

    `presence_figures_for_room` is the PERCEPTION view and subtracts the
    bodies a derived crowd carries, because a room's crowd is their
    presentation there. The Director is not a perceiver: it owns what
    exists, and what it needs to know before minting "the innkeeper" is
    that three innkeepers hold that post in this room whether a crowd
    presents them or not. Measured, Harrowmere: ten Director-minted people
    over forty turns, eight of them a second copy of a charter post-holder
    standing in the room -- a clerk beside three clerks, an innkeeper
    beside three, a reeve minted under the ledgered reeve's own name --
    because the resolve payload showed the durable presence ledger (who
    has EARNED a record) and never the derived bodies (who is HERE).

    Rows: ``name`` (the display name every other seam speaks), ``room``,
    ``role`` (the institution's public noun for the post held, or "" for
    a member holding no post this window), ``posts`` (the post ids on
    watch), ``charter`` and ``body`` (the permanent identity a binding
    keys on). Posted bodies first, then members, then by name, so a capped
    payload keeps the people a role could be mistaken for.
    """
    from world import charter_crowd
    from world.planned_entities import body_plan_uid

    places = {str(r) for r in (rooms or ()) if str(r or "")}
    if not places:
        return []
    try:
        from world.charter_runtime import background_presence_records
        derived = background_presence_records(
            cid, places=places, frame_id=frame_id)
    except Exception:
        return []
    # Where each stands within its room (`world.charter_place`), so the
    # objects and social hands can reason about who is beside what. The
    # Director owns what exists, so it is shown the placement whole; an
    # observer never receives it as a label.
    placements = {}
    try:
        from world.charter_place import charter_placements
        from world.charter_runtime import registry_for
        if isinstance(sc, dict) and sc.get("rooms"):
            placements = charter_placements(
                registry_for(cid, frame_id), sc, frame_rooms=places)
    except Exception:
        placements = {}
    rows = []
    for name, record in derived.items():
        refs = [r for r in (record.get("charter_refs") or [])
                if isinstance(r, dict)]
        ref = refs[0] if refs else {}
        hint = str(((record or {}).get("sketch") or {}).get("role_hint") or "")
        posts = ([] if hint.startswith("member of ")
                 else [p.strip() for p in hint.split(",") if p.strip()])
        role = ""
        for post in posts:
            role = charter_crowd._role_noun(post)
            if role:
                break
        rows.append({
            "name": str(name),
            "room": str(((record or {}).get("sketch") or {})
                        .get("station_room") or ""),
            "role": role,
            "posts": posts,
            "charter": str(ref.get("charter") or ""),
            "body": str(ref.get("body") or ""),
            # Where this body sleeps (`charter_dwellings` says which rooms
            # that makes private).
            "home": str(((record or {}).get("sketch") or {})
                        .get("home_room") or ""),
            # What this body looks like at full sight (`charter_surface`):
            # the Director owns what exists and renders it, so it is shown
            # the whole surface rather than a graded label.
            "look": str(((record or {}).get("sketch") or {})
                        .get("appearance") or ""),
            # A charter body IS a plan the charter simulates: the uid the
            # Director's render settles through, in the same field an
            # authored plan carries (`world.planned_entities`).
            "plan": body_plan_uid(ref.get("charter"), ref.get("body"))
            if ref.get("charter") and ref.get("body") else "",
        })
        # A PREDATOR IS NOT A PERSON WHO ANSWERS ORDERS. Every row above
        # describes a body the way a townsperson is described -- a name, a
        # post, a look -- and `figure_answers` adds what it would grant if
        # asked. For a thing that hunts, that frame is not merely thin, it
        # is WRONG in a specific and expensive way: it presents a hunter as
        # a compliant stranger, and the hand reading it treats one as the
        # other.
        #
        # Measured live, chat 117 turn 61. A carbonic stalker stood in the
        # room with the cast for three beats. The Director knew: its row
        # carried the name, the room, the station, the facing, and
        # `same_room_as_player: true`. What the row ALSO carried was
        # `role: ""` and `answers: ["order: answered as a request,
        # granted", "request: granted", "bargain: accepted"]`. Nothing said
        # predator, hungry, deaf, or that the two people beside it were its
        # declared prey -- so it was written as a person standing quietly in
        # a corridor, which is what a person standing quietly in a corridor
        # would do.
        #
        # The charter already holds all of it. Handed over whole, because
        # the Director owns what exists and this is what exists.
        stance = _creature_stance(cid, ref.get("charter"), frame_id=frame_id)
        if stance:
            rows[-1]["creature"] = stance
        placed = placements.get("charter:%s:%s" % (
            ref.get("charter"), ref.get("body")))
        if placed:
            rows[-1]["station"] = dict(placed.get("station") or {})
            rows[-1]["facing"] = placed.get("facing") or ""
    rows.sort(key=lambda r: (0 if r["posts"] else 1, r["name"].casefold()))
    return rows


def planned_figures_in_view(cid, rooms, frame_id=None):
    """The authored plans standing in `rooms` that no render has settled
    (`world.planned_entities.plans_in_view`), in the same row shape as
    `present_charter_figures`, so the Director's payload and the identity
    floor read charter bodies and authored plans as one list. Empty for a
    story that authored none."""
    try:
        from world.planned_entities import plans_in_view
        return plans_in_view(cid, rooms, frame_id=frame_id)
    except Exception:
        return []


def reserved_plan_figures(cid, frame_id=None, exclude_rooms=()):
    """Every unrendered authored plan wherever it stands, flagged
    ``reserved`` (`world.planned_entities.reserved_plans`): a mint naming
    one by name or alias is a render of it in any room."""
    try:
        from world.planned_entities import reserved_plans
        return reserved_plans(cid, frame_id=frame_id,
                              exclude_rooms=exclude_rooms)
    except Exception:
        return []


def reserved_charter_bodies(cid, frame_id=None, exclude_rooms=()):
    """Every charter body standing OUTSIDE the beat's aperture, as a
    ``reserved`` person figure: a mint naming one is that body, whatever
    room the mint stands in, never a second record of it.

    ONE ENTITY PER CHARTER BODY (the owner, 2026-09-23). The in-view half
    already held (`figures_in_view`, commit 4063a37e); the out-of-view half
    did not. Measured on chat 153 turn 8: a hand reported the storekeeper
    `no_referent`, `mint_unreferenced_things` minted him as a scene
    `fixture` on the beach, and from then on every move for his name landed
    on the fixture while the charter body kept simulating in the store --
    one man in two rooms for eighteen turns. Rows carry the body's own plan
    uid (`body_plan_uid`), so a bound render settles exactly like an
    in-view figure's."""
    try:
        from world.charter_runtime import charter_speaker_records
        from world.planned_entities import body_plan_uid
    except Exception:
        return []
    skip = {str(r) for r in (exclude_rooms or ()) if str(r or "")}
    out = []
    try:
        records = charter_speaker_records(cid, frame_id)
    except Exception:
        return []
    for rec in records:
        room = str(rec.get("place") or "")
        if room and room in skip:
            continue  # in view: `figures_in_view` offers it with its room
        out.append({
            "name": rec.get("name"),
            "aliases": list(rec.get("aliases") or ()),
            "charter": rec.get("charter"),
            "body": rec.get("body"),
            "plan": body_plan_uid(rec.get("charter"), rec.get("body")),
            "kind": "person",
            "room": room,
            "reserved": True,
        })
    return out


def dwellings_in_reach(cid, rooms, frame_id=None):
    """`charter_dwellings` for the Director's payload: the rooms in reach
    that are somebody's home, who lives there and who is in. Empty for a
    story with no charter, so an ordinary payload is unchanged."""
    try:
        from world.charter_runtime import charter_dwellings
        return charter_dwellings(cid, rooms, frame_id=frame_id)
    except Exception:
        return []

def _llm_resolve_player_room(sc, pers, cast, interp, player_input):
    positions = sc.get("positions") or {}
    if not positions:
        return None
    char_names = []
    for c in (cast or []):
        try:
            char_names.append(character_name_from_text(c["sheet"]))
        except Exception:
            pass
    # The question is which BODY here is the player, so the keys offered are
    # the scene's bodies. Offering every placed thing asked the model to
    # decide whether a stove might be the player, and a key it picked that
    # named one would have been accepted -- `key in positions` cannot tell
    # the difference.
    bodies = {k: v for k, v in positions.items() if scene_names_body(sc, k)}
    offered = bodies or positions
    payload = {
        "player": {"name": pers.get("name") or persona_name(pers), "appearance": pers.get("appearance"),
                   "senses": pers.get("senses", "")},
        "npc_names": char_names, "position_keys": list(offered.keys()),
        "positions": offered, "rooms": sc.get("rooms", {}),
        "player_input": player_input or "",
        "movement": (interp or {}).get("movement") or {},
        "private_thought": (interp or {}).get("private_thought") or ""
    }
    try:
        out = jparse(chat_complete("utility", get_prompt("position_resolver"),
                                   json.dumps(payload, ensure_ascii=False),
                                   temperature=0.0, max_tokens=1000))
    except Exception as exc:
        # A provider failure and "the model found no match" used to be the
        # same answer here: both returned None, and the caller reported the
        # player's room as unresolved. They are different facts, and only one
        # of them is a system fault -- so the fault says so. The value is
        # still checked against `positions` before use, so this stays a
        # warning rather than a raise.
        note_step_warning(
            "position_resolver call failed (%s: %s); the player's room falls "
            "back to the committed position"
            % (type(exc).__name__, str(exc)[:120]))
        return None
    key = out.get("key") if isinstance(out, dict) else None
    if key and key in offered:
        return offered[key]
    return None

def _resolve_player_room(sc, pers, interp, cast, player_input=None):
    # Canonical, committed position always wins over a declared movement
    # target: a `movement.to_room` is only a request for director_resolve
    # to validate (it may be blocked — see director.py's passable-route
    # check). Trusting it here would show the player as already having
    # arrived — during perception_act, before the move is even resolved,
    # or in perception_outcome, even when director_resolve rejected it.
    p_room = room_of(sc, pers.get("name") or persona_name(pers))
    if p_room:
        return p_room
    mv = interp.get("movement") if interp else None
    if isinstance(mv, dict) and mv.get("to_room"):
        return mv["to_room"]
    char_names = set()
    for c in (cast or []):
        try:
            char_names.add(character_name_from_text(c["sheet"]).lower().strip())
        except Exception:
            pass
    # POSITIONS IS NOT A BODY ROSTER (review 2026-09-07 A56, third site --
    # `story/room_slice` and `web/world_routes` were the first two). Every
    # placed thing stood in this list as a place the player might be, so a
    # stove in one room and a moored boat in another made two candidates out
    # of a scene holding exactly one person, and the resolver fell through to
    # a model call to choose between them. Measured on the stored scenes
    # 2026-09-08: six of twelve went from two-or-more candidates to one, and
    # that call is 21-43s of a turn's wall clock.
    #
    # The two that remain are the ones the resolver exists for -- chat 117 and
    # 122 really do stand bodies in two and three rooms -- so this narrows the
    # question rather than answering it.
    # NOR IS A BODY WHOSE IDENTITY THE SCENE ALREADY RECORDS. A charter body
    # the scene stands carries its `charter_ref` -- it is a townsperson, known
    # by the charter that simulates it, and never the player. Counting it put
    # a playerless frame's absent persona wherever the one townsperson on
    # screen stood, and with two of them in two rooms bought a model call on
    # both perception stages to choose (playerless Aldermill round 5,
    # 2026-09-23: 35 calls, 196s, none of them in the round before the scene
    # began standing charter bodies).
    charter_bound = set()
    for eid, ent in (sc.get("entities") or {}).items():
        if isinstance(ent, dict) and isinstance(ent.get("charter_ref"), dict):
            charter_bound.add(str(eid).lower().strip())
            if ent.get("name"):
                charter_bound.add(str(ent["name"]).lower().strip())
    placed = [(k, v) for k, v in (sc.get("positions") or {}).items()
              if k.lower().strip() not in char_names
              and k.lower().strip() not in charter_bound]
    candidates = [v for k, v in placed if scene_names_body(sc, k)]
    # Never ADD a call: a scene that stands no non-cast body anywhere has not
    # placed the player either, and the unfiltered list is the guess this has
    # always made there.
    if not candidates:
        candidates = [v for _, v in placed]
    # ONE ROOM NAMED TWICE IS ONE ANSWER, not a choice: two things standing
    # in the same room were two candidates, and the tie bought a model call
    # (a tub and a paddle, playerless Aldermill round 7, 2026-09-23).
    candidates = list(dict.fromkeys(candidates))
    if len(candidates) == 1:
        return candidates[0]
    # ASK ONLY WHERE THERE IS SOMETHING TO CHOOSE BETWEEN. The gate was "does
    # the scene place anything at all", which is true of every scene, so a
    # frame standing nothing but its own cast -- every beat of a causality
    # bubble, and every playerless story -- bought a model call per perception
    # stage to look for a body that is not in it (Aldermill 2026-09-19: 120
    # calls, 274s, 185,618 input tokens over 60 beats, every answer empty).
    #
    # Not only waste. `_llm_resolve_player_room` offers the scene's BODIES as
    # the keys, and a cast body is a body, so the one thing between the
    # question and the answer "Emory Vane" was the model declining to pick.
    # An empty candidate list is not an ambiguity for a model to settle; it
    # is the scene saying the player is not standing here.
    if candidates:
        llm_room = _llm_resolve_player_room(sc, pers, cast, interp, player_input)
        if llm_room:
            return llm_room
    return None


def _frame_has_no_player(ctx):
    """Is this beat played in a frame no human plays in (a causality
    bubble)? False wherever it cannot tell, so a story keeps its resolver."""
    try:
        from world.spatial_frames import is_bubble_frame
        frame_id = getattr(ctx.turn, "frame_id", None)
        return frame_id is not None and is_bubble_frame(ctx.chat.id, frame_id)
    except Exception:
        return False


def player_room_in(sc, ctx, pers=None, interp=None, player_name=None,
                   resolve=True):
    """The player's room IN THE SCENE THIS STAGE BUILDS ITS VIEWS FROM.

    THE ONE ORDERING, and it lives here because every stage that asks the
    question has to get the same answer: the scene, then the cached answer,
    then the resolver.

    The scene wins whenever it places the body, because presence and channel
    have to be two readings of one world. `perception_act` resolved the room
    against the scene as stored and then merged the player's own asserted
    state onto a copy fourteen lines later, so every
    `spatial_rel_between(..., target_room=p_room)` after that graded the
    player from the room she had left while the same scene said she was
    somewhere else -- one observer's view carrying her presence in the new
    room and her lines delivered as co-present in the old one, which is a
    channel nobody had.

    The cached `ctx["_player_room"]` is a fallback rather than the first
    answer, for the same reason: it was written before this beat's assertions
    reached the scene. It still stands in where the scene tracks no position
    for the player at all, and the resolver -- which may cost a model call --
    is asked only when neither has an answer. The cache is refreshed on the
    way out, so the stages after this one read the same room these views were
    built from.

    Review 2026-09-07 finding B36 is why the ladder is a function rather than
    a habit: five readers spelled it five ways -- `background_react` read the
    scene by spelling and then a `scene["player_room"]` key nothing in the
    engine writes; `dressing/backdrops._room_of_player` did the same for the
    image and sound routes, so the room a player stood in under her entity id
    was neither drawn nor sounded; `director_interpret` read the cache and
    then the resolver with no scene read at all; the narrator read the cache
    and then the scene (the exact inversion this docstring argues against);
    and `perception_establish` named the resolver directly -- the mildest of
    the five, since the resolver's own first rung is the scene, so what that
    stage ANSWERS did not change, only where it is spelled.
    `resolve=False` truncates the ladder for a stage that may not spend a
    model call, or that has no cache to reach at all; it never reorders it.

    One reader stays off the ladder on purpose: `director_resolve` reads
    `ctx["_player_room"]` directly, because it is the stage that DECIDES the
    room and needs the answer the beat arrived with. Its reasoning is written
    where it reads it (`director._reconcile_resolution`).
    """
    if pers is None:
        pers = persona_of(ctx.chat)
    name = player_name or (pers.get("name") or persona_name(pers)
                           if isinstance(pers, dict) else None)
    room = room_of(sc, name) if name else None
    if not room:
        room = ctx.get("_player_room")
    if not room and resolve and _frame_has_no_player(ctx):
        # A CAUSALITY BUBBLE HAS NO PLAYER TO FIND. It is the frame no human
        # plays in (`spatial_frames.is_bubble_frame`), so the scene placing
        # no player is the scene saying so, not a gap for a model to fill.
        # Resolved anyway, the two props Emory carried were two candidate
        # rooms and the model was offered every body: eleven calls, 48.8 s,
        # the absent player stood beside the miller for nine beats
        # (playerless Aldermill round 7, 2026-09-23).
        return None
    if not room and resolve:
        room = _resolve_player_room(sc, pers, interp, ctx.cast,
                                    ctx.get("input"))
        # A DECLARATION IS EVIDENCE OF INTENT BEFORE RESOLVE AND OF NOTHING
        # AFTER (review 2026-09-07 A83). The resolver's second rung answers
        # with this beat's own `movement.to_room` when the scene places the
        # body nowhere at all -- and that answer belongs to the stage that
        # asked for it (`perception_act` composes the onset from where the
        # player says she is going) and to no stage after it. Caching it
        # turned it into a fact: `perception_outcome` reads the cache when
        # the scene still tracks no position, and so does the narrator, so
        # a destination `director_resolve` had refused -- the refusal is
        # recorded, `state_diff.movement_refused` -- came back as the room
        # she was standing in for the rest of the turn. Returned, never
        # stored: the stages after this one re-derive from the scene, which
        # is where a move that actually happened lands.
        # LIKE COMPARED WITH LIKE: the rung above returns `mv["to_room"]`
        # exactly as the model wrote it, padding included, so a stripped
        # declaration measured against an unstripped answer would let a
        # to_room with surrounding whitespace through the mismatch and back
        # into the cache.
        movement = interp.get("movement") if isinstance(interp, dict) else None
        declared = str((movement.get("to_room") or "")
                       if isinstance(movement, dict) else "").strip()
        if declared and str(room or "").strip() == declared:
            return room
    if room:
        ctx["_player_room"] = room
    return room


def rooms_in_view(ctx, sc, player_room, destination=None):
    """The rooms THIS BEAT is about: the player's room, the rooms within the
    player's perceptual reach -- one hop of light-gated sight and the sound
    walk's two-hop earshot -- and the room a declared move targets.

    ONE DERIVATION, memoised on the context. Review 2026-09-07 finding C18:
    two stages needed the same aperture and neither asked the other. The
    world-context compiler walked the first `RULEBOOK_ROOMS_CAP` = 24 keys of
    `scene["rooms"]` in DICT ORDER for the rulebook's creatures and posts --
    a set that is at once too wide (a town four rooms away) and too narrow
    (on a plan with more than 24 rooms it can omit the room the player is
    standing in, which is the one room the rulebook exists to describe) --
    while `director_resolve` derived this set properly and walked
    `present_charter_figures` over it a second time. The cap is gone; the
    aperture is derived here, once, and both stages read it.

    Keyed by ``(player_room, destination)`` rather than cached bare, because
    the room the beat is about is not fixed for the whole beat: the compiler
    runs BESIDE `perception_act` (`runtime.build_plan`), which previews the
    player's own state assertions and may move her before resolve reads
    `ctx["_player_room"]`. Each caller passes the room it is entitled to --
    the compiler its own scene read, resolve the room the beat arrived with
    -- and a key that has not moved is derived once for both. The scene graph
    itself does not change within a beat (nothing writes `world.scene` until
    commit), so it is not part of the key.

    Objective, not perceptual: this is which rooms the beat touches, never
    what any observer may see of them, so sharing it across stages carries no
    information through a channel nobody had.

    THE SCENE IS THE ONE THE BEAT OPENED WITH -- what `story.scene.get_scene`
    returns, which nothing writes until commit. Four other sites derive the
    same SHAPE over a different world and are deliberately not callers here:
    `background._background_react`, `background.managed_presences`,
    `commit_background.descriptor_bindings` and
    `commit_background.pick_background_reactors` all ask "here plus
    ambient scope" of `beat_scene` -- the scene the beat LEAVES -- so an
    answer memoised from the opening scene would be the wrong world under a
    key that could not tell.
    """
    # WHO THE BEAT IS ABOUT. The player, where the player stands in THIS
    # scene; otherwise the people the scene does hold. A causality bubble's
    # beat runs in a frame whose scene places only its own characters, and
    # the player is nowhere in it -- so an aperture keyed on the player was
    # EMPTY there (nobody laid, nobody voiced: a character listening in a
    # taproom for five beats heard nothing), or keyed on whatever room a
    # resolver guessed for the absent player (a chorus of stable-yard
    # ostlers answering her through the taproom door). Measured on the
    # playerless Aldermill runs, 2026-09-23, both contracts.
    centers = tuple(_aperture_centers(ctx, sc, player_room))
    key = (str(player_room or ""), str(destination or ""))
    cached = ctx.get("_rooms_in_view_cache")
    if (isinstance(cached, tuple) and cached and cached[0] == key
            and (len(cached) < 3 or cached[2] == centers)):
        return set(cached[1])
    rooms = set()
    for center in centers:
        rooms.add(str(center))
        # THE PERCEPTUAL REACH, never a connectivity closure (the owner,
        # 2026-09-23: sight plus earshot). This was the whole
        # `ambient_scope` component, which in an open-plan settlement is the
        # map: measured on chat 153 turn 20, 23 rooms from inside a TARDIS
        # whose doors opened on a beach -- the harbour pier three hops off,
        # clinic interiors six -- so a shopkeeper nobody could see or hear
        # was voiced, resolved and leased (and every charter body in town
        # frozen out of the off-screen simulator), while perception itself
        # reported his line "reached no view". Now: the rooms one hop of
        # light-gated sight reaches (`visible_adjacent_rooms`), and the rooms
        # a raised voice reaches within the sound walk's own two-hop bound
        # (`earshot_rooms`), so a shouter just out of sight can still be
        # voiced. `ambient_scope` keeps its own readers, whose question is
        # the partition.
        try:
            rooms.update(str(v.get("room_id")) for v in
                         visible_adjacent_rooms(sc, str(center)) or ()
                         if isinstance(v, dict) and v.get("room_id"))
        except Exception:
            pass
        try:
            rooms.update(str(r) for r in earshot_rooms(sc, str(center)) if r)
        except Exception:
            pass
    if destination:
        rooms.add(str(destination))
    ctx["_rooms_in_view_cache"] = (key, frozenset(rooms), centers)
    return set(rooms)


def _aperture_centers(ctx, sc, player_room):
    """The rooms the beat is about: the player's, when the player stands in
    this scene; otherwise every room a cast member stands in. A room a
    resolver GUESSED for a player the scene does not place is never one."""
    positions = (sc or {}).get("positions") or {}
    try:
        pers = persona_of(ctx.chat) or {}
        p_name = pers.get("name") or persona_name(pers)
    except Exception:
        p_name = ""
    if player_room and (not p_name or room_of(sc, p_name)):
        return [str(player_room)]
    rooms = []
    for row in getattr(ctx, "cast", None) or ():
        try:
            name = character_name_from_text(row["sheet"])
        except Exception:
            continue
        room = room_of(sc, name) if name else None
        if room and str(room) not in rooms:
            rooms.append(str(room))
    # Overridden only by the scene's OWN cast: with none of them placed there
    # is nobody else the beat could be about, and the player's room stands.
    if not rooms and player_room:
        rooms = [str(player_room)]
    return sorted(rooms)


def figures_in_view(ctx, sc, rooms, frame_id=None):
    """`present_charter_figures` over the beat's aperture, walked ONCE.

    The second half of review 2026-09-07 finding C18. With the aperture
    settled above, the world-context compiler (for the rulebook's creatures
    and posts) and `director_resolve` (for the figures its hands are shown)
    ask the same question of the same rooms in the same beat, and each paid
    a full walk of the charter for it. Measured on the bench copy of chat
    114 (4 charters, 66 bodies, 22 charter places): the walk is 8.1 ms over
    3 rooms and 14.9 ms over 22, against 0.04-0.76 ms to hand back a copy of
    the answer -- 20x to 201x.

    Keyed by the rooms, the frame, and the charter row's own read token
    (`core.db.world_read_token`, which is what `charter_runtime`'s registry
    cache validates itself with), so a beat that WRITES the registry walks
    again rather than serving what stood there before. A copy is returned
    because the rows are the caller's to hold; the memo keeps its own.

    Same scene rule as `rooms_in_view`: the beat's opening scene, not a
    `beat_scene`.
    """
    from copy import deepcopy

    places = frozenset(str(r) for r in (rooms or ()) if str(r or ""))
    if not places:
        return []
    token = None
    try:
        from core.db import active_frame_id, world_read_token
        from world.charter_runtime import CHARTERS_KEY
        _frame = active_frame_id.set(frame_id)
        try:
            token = world_read_token(ctx.chat["id"], CHARTERS_KEY)
        finally:
            active_frame_id.reset(_frame)
    except Exception:
        token = None
    key = (places, frame_id, token)
    cached = ctx.get("_figures_in_view_cache")
    if isinstance(cached, tuple) and cached and cached[0] == key \
            and token is not None:
        return deepcopy(cached[1])
    rows = present_charter_figures(
        ctx.chat["id"], sc, places, frame_id=frame_id)
    ctx["_figures_in_view_cache"] = (key, rows)
    return deepcopy(rows)
