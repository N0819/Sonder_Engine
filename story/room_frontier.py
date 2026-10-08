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

A SHORTFALL IS SOMETHING MISSING, NEVER SOMETHING FINISHED. The measure
counted only the plan's prose-free stubs as rooms ahead and only unrendered
person plans as people, so the more of the world the story had made real the
shorter the frontier read. Measured on the Brackwater run (chat 166,
2026-10-07): 21 fill jobs, 371 model calls, 9.5M prompt tokens, and 17 of
the 21 had no open need -- they ran on a "shortfall" of three things, none
of them missing. At the tide chapel every room within two hops had been
furnished, so nothing was a stub and the frontier read two rooms short; on
the Grebe under way the boat's deck was joined to nothing (the vessel stood
in no room, the run's F92), so no room was in reach at all and it read two
short again; and
in a town whose five charters held 45 named people it read one person short
because only one authored plan was still unmet. The Room answered "nothing
to build" to the same question again and again, and nothing any of those
fills made reached a page or a mind. So:

* every room within reach that the world HOLDS -- furnished or planned --
  is ready ahead; only a reachable id nothing holds is a gap;
* with no way out of the player's room at all there is no "ahead" to
  prepare, and no room shortfall: what the story reaches next from there is
  a planning need when it reaches for it (the Grebe's was, need
  `transit_destination_unplanned`, filed the beat the boat left);
* a person ready ahead is an unrendered person plan OR a named body on an
  institution's books that the story has not got on stage -- the charter is
  the offscreen simulator and holds its people ready by construction.

THE FILL ASKS A QUESTION ONCE (`fill_signature`, `fill_due`): what a fill
would answer is the open needs, the player's room, the frontier's real
shortfall and the grants it may answer under. A fill that ran against an
unchanged question is not asked it again until a back-off has run, doubling
for each answer that landed nothing, so an open need keeps being re-asked --
less often the longer the Room has nothing for it, never not at all.
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
#: Rooms wanted within that depth that the world holds -- furnished or
#: planned, since a furnished room is the most prepared a room can be. Below
#: it the frontier is short of rooms, unless the player's room has no way out
#: at all (see the module docstring).
FRONTIER_ROOMS_MIN = 2
#: People wanted ready ahead: authored person plans nobody has rendered yet,
#: plus the named, living bodies of the frame's charters that are neither on
#: stage nor an authored person's own (`_bodies_ahead`). Below it the frontier
#: is short of people.
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
#: before it is asked again. It doubles for each consecutive answer that
#: landed nothing (`fill_wait_beats`).
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
    one kind of room within reach that is genuinely MISSING. Everything else
    reachable is ready: a stub is a room the Director furnishes on entry and
    a furnished room is already there."""
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
    # READY IS WHAT THE WORLD HOLDS, not what it has yet to furnish: every
    # reachable room but an exit into nothing. No reachable room at all is
    # not a shortfall -- there is no way out to prepare along (the module
    # docstring has the Grebe), so the count is withheld and says why.
    ready = len(reachable) - len(unheld)
    rooms_short = (max(0, FRONTIER_ROOMS_MIN - ready) if reachable else 0)
    unmeasured = ("" if reachable else
                  "no way out of the player's room" if start else
                  "the player stands in no room")
    plans = [p for p in planned_entities(cid, frame_id).values()
             if not p.get("rendered") and p.get("name")]
    identities = [p["name"] for p in plans if p["kind"] == "person"]
    bodies = _bodies_ahead(cid, frame_id)
    # THE OTHER TWO THIRDS OF `PLAN_KINDS`. `identities_ahead` measures whether
    # enough PEOPLE stand ahead of the story, and that is the right measure --
    # `identities_short` counts only persons (plans and charter bodies). But the
    # report was also the one standing place an unrendered plan surfaced at
    # all, so a thing or a creature the Room had filed was in no read it has:
    # not here, not in `inspect_rooms` (which listed bodies only), and not in
    # the reply payload, which carries no scene. Reported beside the count
    # rather than inside it -- a filed prop is not a populated frontier.
    things = [{"uid": p["uid"], "name": p["name"], "kind": p["kind"],
               "where": (p.get("brief") or {}).get("where") or ""}
              for p in plans if p["kind"] != "person"]
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
        # ahead. Informative; the shortfall counts every room held.
        "rooms_ahead": stubs,
        "rooms_short": rooms_short,
        **({"rooms_unheld": unheld} if unheld else {}),
        **({"rooms_unmeasured": unmeasured} if unmeasured else {}),
        "identities_ahead": identities,
        # Counts per charter, not names: a town is dozens of people, and
        # their names are `inspect_reserved_identities`' to list.
        "bodies_ahead": bodies,
        "identities_short": max(0, FRONTIER_IDENTITIES_MIN - len(identities)
                                - sum(bodies.values())),
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
    """One fill landed: counted against the hour's budget."""
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


def fills_this_hour(cid, frame_id, turn_idx=None):
    """How many fills landed within the last story hour -- by the clock's
    elapsed seconds when the story keeps one, else within the last
    `HOUR_AS_TURNS_FALLBACK` beats."""
    row = _row(cid, frame_id)
    fills = [f for f in (row.get("fills") or []) if isinstance(f, dict)]
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

def fill_signature(report, mandate_uids=()):
    """WHAT A FILL WOULD ANSWER, as one short hash: the open needs, the room
    the player stands in, the frontier's shortfall, and the grants it would
    answer under (a new grant is a new question -- the fill that could not
    build without it can now). Nothing else in the report moves it: which
    stubs or which plans stand ahead does not change whether anything is
    MISSING, and a signature that moved with them re-asked a question whose
    answer had not changed (the plan list moved when Abel Gale was rendered,
    and nothing the fill could answer had)."""
    parts = {
        "needs": sorted(str(u) for u in (report.get("open_need_uids") or ())),
        "room": str(report.get("player_room") or ""),
        "rooms_short": int(report.get("rooms_short") or 0),
        "identities_short": int(report.get("identities_short") or 0),
        "mandates": sorted(str(u) for u in (mandate_uids or ())),
    }
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
