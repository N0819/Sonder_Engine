"""The prepared frontier: how much world stands ready ahead of the player,
measured, and the identity-fill ledger the budget is counted against.

v2 § 3.2-3.3: the Story Planner keeps a SMALL frontier ahead of likely
movement -- rooms planned along the exits the player can reach, and
identities reserved for the people the story will meet -- so arrival can be
immediate and grounded. It is never a claim about where the player will go:
an unprepared direction is an ordinary miss, answered by a planning need.

Everything here is deterministic reading. It counts; it does not author.
What is short becomes a task for the Planner's fill job
(`agents/story_planner.py`), which authors through a package under the
identity-fill mandate and records each fill here so the per-story-hour
ceiling can be counted. The row rides the frame-scoped `room_frontier`
world key.

THE FRONTIER IS WHAT THE PLAN HOLDS AHEAD, SO A DEVELOPED AREA IS SHORT OF
IT. Rooms ahead are the plan's stubs within reach -- planned rooms nobody
has furnished yet -- and people ahead are authored person plans nobody has
rendered yet. As the story furnishes the rooms around the player and meets
the people planned for it, the frontier reads shorter, and that is the
Room's prompt to plan what lies beyond: the world keeps moving ahead of the
player on the Room's own initiative, not only when a beat reaches for
something no plan holds. Owner ruling, 2026-10-08, on learning how far the
morning's measure (next paragraph) had narrowed the Room: "I just hope we
didn't lobotomize it and remove the world's ability to be proactive" --
restore planting ahead, on the back-off.

For one morning (40586278) the measure read the other way. On the
Brackwater run (chat 166, 2026-10-07) 17 of 21 fill jobs had no open need,
and the Room answered "nothing to build" to the same unchanged question
again and again, so every room the world held was counted as ready and a
charter's off-stage bodies as people ready ahead. That removed the cost by
removing the initiative: replayed on the run's checkpoints the frontier read
short at no beat, and a developed area never asked the Room for anything
again. The cost is held by asking a question once instead (below), and by
the Room's card saying that planting ahead is the fill's standing work and
that building nothing is still a complete answer. What that morning got
right stays:

* a reachable id that neither the scene nor the plan holds -- an exit into
  nothing -- is missing NOW, whatever else stands ahead, and the shortfall
  counts it (`rooms_unheld`);
* with no way out of the player's room at all there is no "ahead" to plan
  along and no room shortfall (`rooms_unmeasured`): on the Grebe under way
  the boat's deck was joined to nothing (the vessel stood in no room, the
  run's F92), and rooms planted beside a vessel in no room were nonsense.
  What the story reached next from there was a planning need the beat it
  reached for it (`transit_destination_unplanned`, filed when the boat
  left);
* a charter's named, living, off-stage bodies are REPORTED (`bodies_ahead`)
  for the Room to weigh -- a town that already holds the people a story
  would meet may need nobody new -- and never subtracted from the people
  short: an institution's people are the offscreen simulator's, and a
  person the Room plans is one the story needs that no institution holds.

THE FILL ASKS A QUESTION ONCE (`fill_signature`, `fill_due`): what a fill
would answer is the open needs, the frontier's shortfall, the grants it may
answer under, and the player's room while a need is open. Planting ahead is
frontier-wide -- what is short is a count, and a question with no need open
is the same question wherever the player walks. A fill that ran against an
unchanged question is not asked it again until a back-off has run, doubling
for each answer that landed nothing, so an open need -- and a frontier the
Room could plant -- keeps being re-asked: less often the longer the Room has
nothing for it, never not at all.

LOCAL EVENTS THE PLANTING SKETCH FILES ARE PACED HERE TOO
(`LOCAL_EVENT_BEATS`, `record_sketched_event`, `sketched_event_wait`): the
row remembers the last one, and the next waits this frame's beats out.
"""

from __future__ import annotations

import hashlib
import json
import time

from core.db import q, transaction, wget_for_frame, wset_for_frame

#: The world key. Frame-scoped (core/db.FRAME_SCOPED_WORLD_KEYS).
FRONTIER_KEY = "room_frontier"

#: How far ahead of the player the frontier is counted, in room hops over
#: passable edges and the plan's topology.
FRONTIER_DEPTH_HOPS = 2
#: Planned rooms nobody has furnished yet (the plan's stubs) wanted within
#: that depth. Below it the frontier is short of rooms and the Room is asked
#: to plan beyond the developed area -- unless the player's room has no way
#: out at all -- and an exit into nothing within reach is short on top of it
#: (`_rooms_short`). Two, the value the measure had from v2 § 3.2 until
#: 2026-10-08 and restored with it. Replayed on the Brackwater checkpoints
#: (chat 166) it reads short only where the area around the player had been
#: furnished -- beats 6-11 at the tide chapel (one stub in reach, then none)
#: and 13-14 on the Grebe in the down channel -- and never in the planned
#: town, which held eight to twenty-one stubs within two hops.
FRONTIER_ROOMS_MIN = 2
#: Authored person plans nobody has rendered yet, anywhere in the frame,
#: wanted ready ahead. Below it the frontier is short of people. A charter's
#: off-stage bodies are reported beside the count (`bodies_ahead`) and never
#: subtracted from it. Two, the value it always had: the people a story is
#: about to meet, beside the institutions' own.
FRONTIER_IDENTITIES_MIN = 2
#: Fill records kept on the row; older ones fall off.
FILLS_KEPT = 48
#: One story hour, in the clock's seconds, for the per-hour budget.
STORY_HOUR_SECONDS = 3600.0
#: When the story has no clock yet, a fill "hour" is this many beats.
HOUR_AS_TURNS_FALLBACK = 8
#: THE FILL'S BACK-OFF, in beats: how long a fill waits before it is asked
#: AGAIN against a question that has not changed since it last answered,
#: counted from the beat the answer came. The old trigger re-asked at the
#: very next commit, and on the Brackwater run a fill was in flight at every
#: kept commit from turn 6 to turn 30. Two beats: a fill there took a median
#: of about 7 minutes (0.3 to 29) and a beat about 10, so an unchanged
#: question waits some twenty minutes of play, two or three fills' length,
#: before it is asked again -- after an answer that landed something, and
#: after the first that landed nothing -- and it doubles for each further
#: consecutive empty answer (`fill_wait_beats`).
FILL_RETRY_BEATS = 2
#: ...up to this many beats, and no further: the ceiling is what keeps an
#: open planning need re-asked for as long as it stays open (an unanswered
#: need is a defect, owner 2026-09-19) instead of backing off for good.
FILL_RETRY_BEATS_CAP = 16
#: Questions the fill memo remembers (one row per signature, newest last);
#: past it the oldest question is forgotten and would be asked fresh.
#: Sixteen is more distinct questions than the measured run asked in thirty
#: beats even under the wider signature the first proposal used (nine, the
#: stub and plan lists included), so the cap trims a long story's tail and
#: not a live question.
FILL_MEMO_KEPT = 16
#: LOCAL EVENTS ARE PACED: at most one local event the planting sketch files
#: (`story/room_sketch.py`) per this many of this frame's beats. The owner
#: asked for the Room to plan events locally "to some level to keep things
#: interesting if allowed" (2026-10-08) and, of the conversation threads the
#: day before, that chatter not be overdone; eight is two beats slower than
#: the Dramaturge's own pacing (`mandates.BEATS_PER_PROPOSAL`, 6), so a
#: sketched circumstance never arrives more often than a story direction is
#: suggested. On the Brackwater run's pace (about ten minutes a beat) that is
#: at most one sketched event in some eighty minutes of play. Only events the
#: sketch files count: the full Planner's own local drama is its judgement
#: under the grants, as before.
LOCAL_EVENT_BEATS = 8


def _row(cid, frame_id):
    stored = wget_for_frame(cid, FRONTIER_KEY, frame_id, {}) or {}
    return stored if isinstance(stored, dict) else {}


def _save(cid, frame_id, row):
    wset_for_frame(cid, FRONTIER_KEY, row, frame_id)


def _update(cid, frame_id, change):
    """Read, change and write the row as ONE act under the write lock.

    Four writers share this row from four threads -- the commit tail's
    measure, the fill job, the Dramaturge pass and the panel's reply all
    record here -- and each saved what it had read a moment earlier, so a
    write that landed between another writer's read and its save was erased
    by construction. The Brackwater run's row did lose writes: four fill
    publications survived to the end and two fill records did, and
    checkpoint 10 holds F04's published package with neither its fill nor
    its spend record. Some of that is checkpoint restores (a reroll rolls
    this row back with the beat, F31) and the rest could not be attributed
    from the stored rows; the shared read-to-write window is the loss this
    closes, now that the fill's memo rides the row too. ``change(row)``
    mutates the row in place; the row is returned as written."""
    with transaction():
        row = _row(cid, frame_id)
        change(row)
        _save(cid, frame_id, row)
    return row


def _player_room(cid, scene):
    """The room the player STANDS IN -- whatever holds it. A room carrying
    `parent_entity` is where the world put the player's body, and it is the
    same room `room_slice.room_index` lists with its holder; the two reads
    must name one room or the Planner plans against a phantom (chat 115:
    the frontier said `room_elevator_interior`, the room tool listed no
    such room, and a second lift car was planned beside the one the cast
    was riding)."""
    from core.db import q
    from story.character_schema import persona_name
    from story.scene import persona_of
    from world.spatial import room_of
    chat = q("SELECT * FROM chats WHERE id=?", (cid,), one=True)
    if not chat:
        return None
    name = persona_name(persona_of(dict(chat)))
    positions = scene.get("positions") or {}
    room = positions.get(name) or room_of(scene, name)
    return str(room) if room else None


def rooms_ahead(cid, scene, start, depth=FRONTIER_DEPTH_HOPS, contained=None):
    """Room ids within ``depth`` hops of ``start`` over passable edges plus
    the plan's topology, and which of them are still the plan's unfurnished
    stubs. Returns ``(reachable, stubs)``.

    The graph and the count are `room_slice.room_hops`, the same ones the
    room index reports, so the frontier and the tool agree hop for hop. A
    start that is the inside of a body counts OUT through the room its
    holder stands in (one hop); no other inside is ahead of the player or a
    frontier gap, because where the world puts a body is the Director's and
    transient (owner ruling, 2026-09-03) -- so contained rooms are counted
    through and never listed.

    ONE READ EACH. The containment map and the plan's topology are what the
    graph is built from and what the stub test asks; both were made here and
    again inside `room_graph` (C21). ``contained`` lets the caller that
    already holds the map hand it in."""
    reachable, stubs, _unheld = _rooms_within(cid, scene, start, depth,
                                              contained)
    return reachable, stubs


def _rooms_within(cid, scene, start, depth=FRONTIER_DEPTH_HOPS, contained=None):
    """`rooms_ahead`'s walk, with the third answer the shortfall needs:
    ``(reachable, stubs, unheld)``, where ``unheld`` is every reachable id
    that neither the scene nor the plan holds -- an exit into nothing, the
    one kind of room within reach that is missing now. The rest of reach is
    the plan's stubs, which stand ahead (the Director furnishes one on
    entry), and the furnished rooms, which are the area the story has
    already developed."""
    from story.room_slice import containment, room_graph, room_hops
    from world.structure import is_planned_stub, planned_topology

    if not start:
        return [], [], []
    contained = containment(scene) if contained is None else contained
    topology = planned_topology(cid)
    hops = room_hops(cid, scene, [str(start)],
                     graph=room_graph(cid, scene, contained=contained,
                                      planned=topology))
    rooms = scene.get("rooms") or {}
    contained = set(contained)
    planned = set(topology)
    reachable = sorted(rid for rid, n in hops.items()
                       if 0 < n <= max(0, int(depth)) and rid not in contained)
    stubs = [rid for rid in reachable
             if (rid in rooms and is_planned_stub(scene, rid))
             or (rid not in rooms and rid in planned)]
    unheld = [rid for rid in reachable if rid not in rooms and rid not in planned]
    return reachable, stubs, unheld


def _bodies_ahead(cid, frame_id):
    """``{charter_key: n}``: the people each charter holds ready that the
    story has not got on stage -- named, living, not departed, not on loan
    to a scene (`leased`), and not an authored person's own body (that
    person is the cast's, `charter_model.body_of_an_authored_mind`). Each
    test is one the charter already makes -- `charter_harm.is_gone`, the
    `departed` and `leased` flags `charter_place` reads, and
    `body_of_an_authored_mind`; nothing new decides who counts.

    `plot_packages.reserved_identities` reads the same registry for a
    different question -- which NAMES are taken, the dead's included -- so
    its list is not this count. The read is the SHARED registry
    (`charter_runtime.registry_for`): the commit tail's
    `schedule_charter_ticks` reads it a moment later, so measuring the
    frontier first moves that parse rather than adding one (226 ms cold on
    Brackwater's 3.2 MB registry, 0.1 ms warm). A registry that cannot be
    read counts nobody rather than failing the report."""
    try:
        from world.charter_harm import is_gone
        from world.charter_model import body_of_an_authored_mind
        from world.charter_runtime import registry_for
        registry = registry_for(cid, frame_id)
    except Exception:
        return {}
    out = {}
    for key, item in sorted((registry.get("items") or {}).items()):
        state = (item or {}).get("state") or {}
        n = 0
        for body_key, body in ((state.get("bodies") or {}).items()):
            if not isinstance(body, dict) or not str(body.get("name") or "").strip():
                continue
            if is_gone(body) or body.get("departed") or body.get("leased"):
                continue
            if body_of_an_authored_mind(state, body_key, body):
                continue
            n += 1
        if n:
            out[str(key)] = n
    return out


def _actor_rooms(cid, scene, contained):
    """The rooms the story's people stand in -- the player and every
    attached cast member, by their `positions` rows -- each the room a body
    inside another stands in where that is where it is held. The minds a far
    line is told to; a charter's off-stage bodies perceive nothing."""
    from core.db import q
    from story.room_slice import holder_room
    rows = q("SELECT c.name FROM chat_chars cc JOIN characters c ON c.id=cc.char_id "
             "WHERE cc.chat_id=?", (cid,))
    names = [str(r["name"]) for r in rows if r["name"]]
    rooms = (scene or {}).get("rooms") or {}
    positions = (scene or {}).get("positions") or {}
    folded = {str(k).strip().casefold(): str(v) for k, v in positions.items() if v}
    out = []
    player = _player_room(cid, scene)
    for room in [player] + [positions.get(n) or folded.get(n.strip().casefold())
                            for n in names]:
        room = str(room or "")
        if room in contained:
            room = str(holder_room(scene, contained[room]) or "")
        if room and room in rooms and room not in out:
            out.append(room)
    return out


def looks_wanted(cid, frame_id, scene, contained=None):
    """THE PLACES A FAR EYE NEAR THE STORY READS BY THEIR GROUND
    (`landscape.standing_looks_wanted`, 2026-10-09): the standing places and
    parts of the map within the far layer's reach of where the player and
    the cast stand that no far look describes and the Room may give one --
    ``{"places": [{room, ground, hops, members?}], "regions": [{region,
    hops, rooms}]}``, nearest first, or None when there are none. A pure
    read, counted beside the shortfall: it is what the fill gives looks to,
    under the same back-off as planting (`fill_signature`). A registry that
    cannot be read offers no region, as the far layer reads none."""
    from story.room_slice import containment
    from world.landscape import REGIONS_UNREAD, standing_looks_wanted
    contained = containment(scene) if contained is None else contained
    starts = _actor_rooms(cid, scene, contained)
    if not starts:
        return None
    try:
        from world.regions import region_registry
        regions = region_registry(cid, frame_id)
    except Exception:
        regions = REGIONS_UNREAD
    wanted = standing_looks_wanted(scene, starts, regions=regions)
    return wanted if wanted["places"] or wanted["regions"] else None


def _rooms_short(reachable, stubs, unheld):
    """How many rooms the frontier is short of: the planned rooms it wants
    ahead and does not have (`FRONTIER_ROOMS_MIN` less the stubs within
    reach), or the exits into nothing within reach if those are more -- an
    exit into nothing is missing now, however much the plan holds beyond
    the other ways out. No reachable room at all is no shortfall: there is
    no way out to plan along (the module docstring has the Grebe)."""
    if not reachable:
        return 0
    return max(0, FRONTIER_ROOMS_MIN - len(stubs), len(unheld))


def frontier_report(cid, frame_id=None, scene=None):
    """Measure the frontier: what stands ahead, what is short, what is
    open. Pure read; nothing is written."""
    from story.scene import get_scene
    from world.planned_entities import planned_entities
    from world.planning_needs import open_planning_needs
    if scene is None:
        from story.room_slice import read_scene
        scene = read_scene(cid, frame_id) or {}
    from story.room_slice import containment
    start = _player_room(cid, scene)
    contained = containment(scene)
    reachable, stubs, unheld = _rooms_within(cid, scene, start,
                                             contained=contained)
    holder = contained.get(start) if start else None
    # WHAT STANDS AHEAD IS WHAT THE PLAN HOLDS AND NOBODY HAS FURNISHED: a
    # furnished room within reach is ground the story already has, and a
    # developed area is exactly where the Room is asked to plan beyond it
    # (owner ruling, 2026-10-08). Withheld, and saying why, when there is no
    # way out of the player's room to plan along.
    rooms_short = _rooms_short(reachable, stubs, unheld)
    stub_set, unheld_set = set(stubs), set(unheld)
    developed = [rid for rid in reachable
                 if rid not in stub_set and rid not in unheld_set]
    unmeasured = ("" if reachable else
                  "no way out of the player's room" if start else
                  "the player stands in no room")
    plans = [p for p in planned_entities(cid, frame_id).values()
             if not p.get("rendered") and p.get("name")]
    identities = [p["name"] for p in plans if p["kind"] == "person"]
    bodies = _bodies_ahead(cid, frame_id)
    # THE OTHER TWO THIRDS OF `PLAN_KINDS`. `identities_ahead` measures whether
    # enough PEOPLE stand ahead of the story, and that is the right measure --
    # `identities_short` counts only authored person plans, with a charter's
    # bodies beside it as `bodies_ahead`. But the report was also the one
    # standing place an unrendered plan surfaced at
    # all, so a thing or a creature the Room had filed was in no read it has:
    # not here, not in `inspect_rooms` (which listed bodies only), and not in
    # the reply payload, which carries no scene. Reported beside the count
    # rather than inside it -- a filed prop is not a populated frontier.
    things = [{"uid": p["uid"], "name": p["name"], "kind": p["kind"],
               "where": (p.get("brief") or {}).get("where") or ""}
              for p in plans if p["kind"] != "person"]
    looks = looks_wanted(cid, frame_id, scene, contained)
    needs = open_planning_needs(cid, frame_id)
    by_kind = {}
    by_reason = {}
    for need in needs:
        by_kind[need["kind"]] = by_kind.get(need["kind"], 0) + 1
        by_reason[need["reason"]] = by_reason.get(need["reason"], 0) + 1
    return {
        "player_room": start,
        # The body the player's room is the inside of, when it is one: the
        # room stays the room they stand in, and this says what holds it.
        "player_holder": holder,
        "depth_hops": FRONTIER_DEPTH_HOPS,
        "reachable": reachable,
        # The plan's prose-free stubs among them -- what the plan holds open
        # ahead, and what the room shortfall counts.
        "rooms_ahead": stubs,
        # The furnished rooms among them -- the area the story has already
        # developed, which a fill short of rooms plans beyond.
        "rooms_developed": developed,
        "rooms_short": rooms_short,
        **({"rooms_unheld": unheld} if unheld else {}),
        **({"rooms_unmeasured": unmeasured} if unmeasured else {}),
        "identities_ahead": identities,
        # Counts per charter, not names: a town is dozens of people, and
        # their names are `inspect_reserved_identities`' to list. What the
        # Room weighs when people are short; never subtracted from it.
        "bodies_ahead": bodies,
        "identities_short": max(0, FRONTIER_IDENTITIES_MIN - len(identities)),
        "things_ahead": things,
        "open_needs": by_kind,
        # AND WHY EACH ONE IS OPEN. `kind` is three values against five
        # reasons, so a count by kind alone reads as a pile of props: 8 of
        # the 9 needs open on the owner's live stories (2026-09-06) are
        # `setting_fact`, filed as `thing` because that is the fallback and
        # carrying a whole sentence as their subject. `inspect_needs` and
        # the fill job always saw the reason; the report the Room reads
        # first did not.
        "open_needs_by_reason": by_reason,
        "open_need_uids": [n["uid"] for n in needs],
        # The standing places a far eye near the story reads by their ground
        # alone, and the parts of the map that would describe them, nearest
        # first (`looks_wanted`): what a fill gives far looks to. Present
        # only when there are some.
        **({"looks_wanted": looks} if looks else {}),
    }


def record_measure(cid, frame_id, report, turn_idx=None):
    def _apply(row):
        row["measured_turn"] = turn_idx
        row["rooms_short"] = report.get("rooms_short", 0)
        row["identities_short"] = report.get("identities_short", 0)
        row["open_needs"] = dict(report.get("open_needs") or {})
    return _update(cid, frame_id, _apply)


def _clock_seconds(cid, frame_id):
    clock = wget_for_frame(cid, "simulation_clock", frame_id, {}) or {}
    value = clock.get("elapsed_seconds") if isinstance(clock, dict) else None
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def record_fill(cid, frame_id, *, turn_idx, package_uid="", needs=()):
    """One fill landed: counted against the hour's line. ``needs`` are the
    needs it ANSWERED -- the ones a package it published answers or closes
    (`plot_packages.operation_needs`, read by
    `agents/story_planner.run_fill`), never the ones it merely carried -- and
    a record naming any is one `fills_this_hour(needs_only=True)` counts."""
    entry = {"turn": int(turn_idx or 0),
             "elapsed_seconds": _clock_seconds(cid, frame_id),
             "at": time.time(), "package": str(package_uid or ""),
             "needs": [str(n) for n in needs][:8]}

    def _apply(row):
        fills = [f for f in (row.get("fills") or []) if isinstance(f, dict)]
        fills.append(entry)
        row["fills"] = fills[-FILLS_KEPT:]
    return _update(cid, frame_id, _apply)


#: Spend records kept on the row (one per Planner or Dramaturge pass);
#: older ones fall off.
SPEND_KEPT = 96


def record_spend(cid, frame_id, *, turn_idx, calls, who="planner"):
    """One pass's tool calls, counted against the hour's spend
    (`mandates.spend_limits`). Zero-call passes are not recorded."""
    calls = int(calls or 0)
    if calls <= 0:
        return _row(cid, frame_id)
    entry = {"turn": int(turn_idx or 0),
             "elapsed_seconds": _clock_seconds(cid, frame_id),
             "at": time.time(), "calls": calls, "who": str(who)[:24]}

    def _apply(row):
        spend = [s for s in (row.get("spend") or []) if isinstance(s, dict)]
        spend.append(entry)
        row["spend"] = spend[-SPEND_KEPT:]
    return _update(cid, frame_id, _apply)


def spend_this_hour(cid, frame_id, turn_idx=None):
    """Tool calls made within the last story hour, on the same clock the
    fill budget uses."""
    row = _row(cid, frame_id)
    spend = [s for s in (row.get("spend") or []) if isinstance(s, dict)]
    now = _clock_seconds(cid, frame_id)
    if now is not None:
        return sum(int(s.get("calls") or 0) for s in spend
                   if s.get("elapsed_seconds") is not None
                   and now - float(s["elapsed_seconds"]) < STORY_HOUR_SECONDS)
    turn = int(turn_idx or 0)
    return sum(int(s.get("calls") or 0) for s in spend
               if turn - int(s.get("turn") or 0) < HOUR_AS_TURNS_FALLBACK)


def fills_this_hour(cid, frame_id, turn_idx=None, *, needs_only=False):
    """How many fills landed within the last story hour -- by the clock's
    elapsed seconds when the story keeps one, else within the last
    `HOUR_AS_TURNS_FALLBACK` beats.

    THE TWO COUNTS THE FILL LINE IS HELD TO (`mandates.FILLS_PER_STORY_HOUR`,
    N). A number the player states is the total: the caller counts every
    fill that landed for planting and needs alike (owner, 2026-10-08:
    "Your number is the total"; `mandates.fill_limit_stated`). With the
    engine's default, a fill that plants ahead is held to N counting every
    fill that landed, and a fill asked about an open need to N counting
    only the fills that answered needs (``needs_only``: a fill's record
    names the needs a package it published answered or closed,
    `record_fill`). A fill that carried a need and published only planting
    answered none, and is counted on the planting line alone: counted as a
    need's fill, four planting fills that each declined a standing need
    spent the needs' line too, and a need filed after them waited out the
    whole story hour (review 2026-10-08, R2-2). Replayed on the Brackwater
    checkpoints with every answer publishing, one count shared by both let
    four planting fills at beats 6-11 spend the default four, and the run's
    one need -- open from beat 16 to 23, in a run whose clock never passed
    1,705 story seconds -- would never have been asked (an unanswered need
    is a defect, owner 2026-09-19). Only a fill that LANDED is counted: an
    answer that built nothing is held by its question's back-off
    (`fill_due`), never by this count."""
    row = _row(cid, frame_id)
    fills = [f for f in (row.get("fills") or []) if isinstance(f, dict)
             and (f.get("needs") or not needs_only)]
    now = _clock_seconds(cid, frame_id)
    if now is not None:
        return sum(1 for f in fills
                   if f.get("elapsed_seconds") is not None
                   and now - float(f["elapsed_seconds"]) < STORY_HOUR_SECONDS)
    turn = int(turn_idx or 0)
    return sum(1 for f in fills
               if turn - int(f.get("turn") or 0) < HOUR_AS_TURNS_FALLBACK)


# ---------------------------------------------------------------------------
# The fill memo: a question is asked once, then backs off
# ---------------------------------------------------------------------------

def fill_signature(report, mandate_uids=(), looks=False):
    """WHAT A FILL WOULD ANSWER, as one short hash: the open needs, the
    frontier's shortfall, the grants it would answer under (a new grant is a
    new question -- the fill that could not build without it can now), and
    the room the player stands in WHILE A NEED IS OPEN: a need is answered
    where the story reached for it, so a step moves that answer. Nothing
    else in the report moves it: which stubs or which plans stand ahead does
    not change how short the frontier is, and a signature that moved with
    them re-asked a question whose answer had not changed (the plan list
    moved when Abel Gale was rendered, and nothing the fill could answer
    had). A room furnished, a plan met or a plan published moves the
    shortfall, and that is a new question.

    PLANTING AHEAD IS FRONTIER-WIDE, so a question with no need open is the
    same question wherever the player walks. Keyed on the room, it was a new
    question at every step, and the back-off never engaged for a player who
    kept moving: an answer that lands nothing counts against no hourly line
    (`fills_this_hour` counts landed fills), so the review's probes
    (2026-10-08) asked 7 fills in 8 beats on one unchanged people-only
    question, and -- with the room kept while rooms were short -- 6 in 7
    beats for a player walking a developed area (R2-1), `fills_this_hour` at
    0 throughout. Empty answers are held by this back-off and the chat's one
    fill in flight, and otherwise only by a `calls_per_hour` spend where a
    grant names one (none by default, `mandates.CALLS_PER_STORY_HOUR`). The
    cost of the rule: a player who walks from one developed area to another
    as short waits out the back-off before the Room plants beyond the
    second (at most `FILL_RETRY_BEATS_CAP` beats)."""
    needs = sorted(str(u) for u in (report.get("open_need_uids") or ()))
    rooms_short = int(report.get("rooms_short") or 0)
    parts = {
        "needs": needs,
        "room": str(report.get("player_room") or "") if needs else "",
        "rooms_short": rooms_short,
        "identities_short": int(report.get("identities_short") or 0),
        "mandates": sorted(str(u) for u in (mandate_uids or ())),
    }
    # WHETHER THE FILL GIVES PLACES NEAR THE STORY THEIR FAR LOOKS (``looks``:
    # the frontier wants some, `looks_wanted`, and the grants let the Room
    # write them), as a yes and never as a list (2026-10-09): the places a
    # far eye reaches change with every step, and a list in the question
    # re-asked it at every step whatever the answer was -- the R2-1 lesson
    # above. So looks ride planting's back-off: a pass that lands looks is
    # asked again after `FILL_RETRY_BEATS`, and one that lands nothing waits
    # longer each time. Absent while none is asked for, so a story with
    # nothing to look at, or no grant to write a look, keeps the question it
    # had.
    if looks:
        parts["looks"] = True
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:16]


def fill_wait_beats(misses):
    """Beats a fill waits before re-asking an unchanged question:
    `FILL_RETRY_BEATS` after an answer that landed something or after the
    first that landed nothing, doubling for each further empty answer, never
    past `FILL_RETRY_BEATS_CAP`."""
    misses = max(0, int(misses or 0))
    return min(FILL_RETRY_BEATS_CAP,
               FILL_RETRY_BEATS * (2 ** max(0, misses - 1)))


def _memo(row):
    return [m for m in (row.get("fill_memo") or [])
            if isinstance(m, dict) and m.get("sig")]


def record_fill_asked(cid, frame_id, signature, *, turn_idx, published):
    """A fill answered ``signature`` at beat ``turn_idx``. ``published``
    resets the run of empty answers; an answer that landed nothing extends
    it, and the next re-ask waits longer (`fill_wait_beats`)."""
    signature = str(signature or "")
    if not signature:
        return _row(cid, frame_id)

    def _apply(row):
        memo = _memo(row)
        prior = next((m for m in memo if m["sig"] == signature), {})
        misses = 0 if published else int(prior.get("misses") or 0) + 1
        memo = [m for m in memo if m["sig"] != signature]
        memo.append({"sig": signature, "turn": int(turn_idx or 0),
                     "misses": misses, "at": time.time()})
        row["fill_memo"] = memo[-FILL_MEMO_KEPT:]
    return _update(cid, frame_id, _apply)


def frame_turn_idx(cid, frame_id):
    """The newest beat THIS frame has played -- the stamp a fill's answer is
    filed at. Turn rows are numbered across the whole chat, and a live
    causality bubble inserts its own beats into that numbering, so the
    chat-wide newest (`room_conversation.current_turn_idx`) can be a
    bubble's row sitting above the player's own beat; filed there, the
    player's next commit read its own earlier beat as a rewind and asked an
    unchanged question again at once (review, 2026-10-08)."""
    row = q("SELECT MAX(idx) AS m FROM turns WHERE chat_id=? AND frame_id IS ?",
            (int(cid), frame_id), one=True)
    return int(row["m"]) if row and row["m"] is not None else 0


def _other_frames_beats(cid, frame_id, after, upto):
    """How many of the chat's turn rows in ``(after, upto]`` belong to some
    OTHER frame -- the beats a live bubble played inside this frame's
    window, which are not this frame's beats to count."""
    row = q("SELECT COUNT(*) AS n FROM turns WHERE chat_id=? AND idx>? "
            "AND idx<=? AND frame_id IS NOT ?",
            (int(cid), int(after), int(upto), frame_id), one=True)
    return int(row["n"] or 0) if row else 0


def fill_due(cid, frame_id, signature, turn_idx):
    """Whether a fill against ``signature`` is due at beat ``turn_idx``:
    never asked, asked in a timeline the story has since rewound out of, or
    asked at least `fill_wait_beats` beats ago. Returns ``(due, why)``;
    ``why`` names the beat it was last answered and the wait, for the log
    line that says why a commit queued nothing."""
    from core.jobs import story_rewound_past
    memo = {m["sig"]: m for m in _memo(_row(cid, frame_id))}
    prior = memo.get(str(signature or ""))
    if prior is None or turn_idx is None:
        return True, ""
    asked = int(prior.get("turn") or 0)
    if story_rewound_past(asked, turn_idx):
        return True, ""
    wait = fill_wait_beats(prior.get("misses"))
    # This frame's beats since the answer: a bubble's rows interleaved in
    # the chat-wide numbering would otherwise shorten every wait.
    beats = int(turn_idx) - asked - _other_frames_beats(
        cid, frame_id, asked, turn_idx)
    if beats >= wait:
        return True, ""
    return False, ("answered at beat %d with %d empty in a row; next ask at "
                   "beat %d" % (asked, int(prior.get("misses") or 0),
                                asked + wait))


# ---------------------------------------------------------------------------
# Local events the planting sketch files: paced
# ---------------------------------------------------------------------------

def record_sketched_event(cid, frame_id, *, turn_idx, package_uid="", op=""):
    """The planting sketch filed a local event at beat ``turn_idx``: the
    next one waits `LOCAL_EVENT_BEATS` of this frame's beats
    (`sketched_event_wait`). The row rolls back with a reroll like the rest
    of the Room's state, so a rewound event is not counted."""
    entry = {"turn": int(turn_idx or 0), "package": str(package_uid or ""),
             "op": str(op or "")[:40], "at": time.time()}

    def _apply(row):
        row["sketched_event"] = entry
    return _update(cid, frame_id, _apply)


def sketched_event_wait(cid, frame_id, turn_idx):
    """Beats left before the planting sketch may file another local event:
    0 when it may now -- none filed yet, one filed in a timeline the story
    has since rewound out of, or `LOCAL_EVENT_BEATS` of this frame's beats
    gone since the last (a live bubble's rows in the chat-wide numbering are
    not this frame's beats, as for `fill_due`)."""
    from core.jobs import story_rewound_past
    last = _row(cid, frame_id).get("sketched_event")
    if not isinstance(last, dict) or turn_idx is None:
        return 0
    filed = int(last.get("turn") or 0)
    if story_rewound_past(filed, turn_idx):
        return 0
    beats = int(turn_idx) - filed - _other_frames_beats(
        cid, frame_id, filed, turn_idx)
    return max(0, LOCAL_EVENT_BEATS - beats)
