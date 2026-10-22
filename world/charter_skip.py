"""A registered mind lives through a declared time skip inside the town.

`docs/design/DESIGN_THE_CAST_ACROSS_A_SKIP.md` § 4.4 (a), and the timeskip
half of `docs/UNBUILT_LIVING_WORLD.md` § 1.99d ("seed it as Charter state, run
the institution forward with `simulate_bound=True`, and hand the accumulated
life back"). The skip stage (`agents/skip_lives.py`) asks each cast member
what it does over the span and resolves the answer to an ITINERARY of
absolute stretches; where the story has a town charter, that itinerary is
walked here, among the town's own people, and the mind gets back what it did,
whom it was among and where it ended.

THE BOUNDARY IS § 2 OF `DESIGN_OFFSCREEN_SUPERSEDED.md`, AND IT IS NOT
NEGOTIABLE: the charter owns WHERE a person is and WHAT THEY DID, never what a
registered mind KNOWS, WANTS or REMEMBERS. So the mind's body is lifted for
the span body-only (`charter_run.step`'s per-body ``simulate_bound``): it
walks, tires and stands where the town can see it, and holds no claim, mark or
feeling and acts on nobody. Its day is its own declaration wherever the
itinerary speaks -- the watch, the errands and the homecomings yield
(``itinerary``) -- and where the itinerary is silent the town's needs-driven
day runs it as it runs everyone.

A SCRATCH RUN, NEVER A WRITE. The town is stepped through the span on a copy
and the copy is dropped: nothing is saved, no `minds` row is written for the
mind, and a temporary enrolment exists only inside the copy. The town's own
people are advanced, stored and witnessed exactly once, by the out-of-band
`charter:<era>` job the commit schedules (`charter_runtime.
schedule_charter_ticks`), and that advance keeps its hands off the mind's own
body (`charter_model.authored_mind_bodies`) and places it where the commit put
it -- the far end returned here. So no body's hours are stepped twice into
what the story keeps.

INLINE, BECAUSE THE FAR END MUST EXIST BEFORE PERCEPTION. The skip stage sits
between `compile_world_context` and `perception_act`, and the beat that
follows is played from where each mind's day ended. Measured on copies of the
owner's largest registries, a 24-hour skip costs 1.4 s cold and 0.6 s warm on
chat 175 (three institutions, the largest registry by size) and 1.0 s on
chat 114 (four institutions, 66 bodies), against the five to twelve seconds
the skip question itself takes; so the run is done here rather than read from
a pre-run, and is bounded by the time-skip budget the town's own advance
already has (`CHARTER_BUDGET_SECONDS["time_skip"]`).

ONE TOWN FOR EVERY MIND, AND IT IS THE TOWN THE STORY KEEPS. The town is
stepped on a grid that depends on the story's day alone -- the parts of the
day, cut every `SKIP_WINDOW_HOURS` from where each began (`skip_windows`) --
from the town's own last instant, with a seed drawn from that instant and the
charter alone (`skip_seed`). So two minds asked about one skip are run through
one town (the baker one of them saw at the oven is at the oven for the
other), and the town's own advance after the commit, which steps a
time-skip beat on the same windows and seed (`charter_runtime.
advance_snapshot`'s ``context``), stores the day they lived: measured on
copies of the owner's chats 175 and 114, every resident where the minds' run
had them (21 of 21, 66 of 66), against 13 of 21 and 43 of 66 when that
advance drew its own equal windows and seed. The one shape it cannot match
is a mind whose OWN body stands a post (a featured resident): its day keeps
it off the bill, and the town's advance, holding that body where the commit
stood it, may staff it there (chat 115: 8 of 10).

WHAT COMES BACK, per the skip stage's fixed shapes (`agents/skip_lives.py`):
a LOG row per stretch -- and per silence the town filled -- carrying the
residents the mind stood among, each under the name THIS mind knows them by
(an unmet resident is a stranger's label, never a name: the `known` ledger
and the stranger label are perception's own), with only what a watcher sees
them do; and the far end, from where the run left the body. Weather and the
holding check are executor-independent and are the skip stage's to lay over
either executor's rows; other asked minds and the player are its too, since a
registered mind is never a charter resident.
"""

from __future__ import annotations

import copy
import time

from core.logging_utils import logger

#: The longest window the town is stepped in while a mind lives through it,
#: in hours. The parts of the day already cut the span (their boundaries are
#: where an itinerary's stretches begin and end), and no window runs past
#: this: co-presence is read at window edges, so this is also how coarse
#: "who was there" may be. At two hours a 24-hour skip on chat 114's four
#: institutions costs about a second; the town's ordinary advance steps four,
#: and steps a time-skip beat on these windows too (`skip_windows`).
SKIP_WINDOW_HOURS = 2.0

#: How far past a span's start a charter's own clock may already stand, in
#: seconds, and still be read as standing at it. A beat's clock is a sum of
#: floats; a charter further ahead than this has lived the span's opening
#: already and cannot be run back through it.
CLOCK_TOLERANCE_SECONDS = 1.0

#: How many residents one LOG row names. A whole skip spent in a full hall
#: would otherwise hand the memory writer a census; the most salient doings
#: are kept, the rest of the room is not listed.
SEEN_PER_ROW_CAP = 12

#: The key a temporarily enrolled mind's body takes in the scratch copy. It
#: never leaves the copy.
TEMPORARY_BODY_PREFIX = "skip_lives:"

#: Why a stretch the charter could not carry out failed, closed: no way at
#: all from where the body stood, a way held shut where it stood, or a way so
#: long the stretch was spent walking it.
FAILURE_REASONS = ("no_route", "shut_way", "too_far")

#: Which of a resident's doings one row keeps, of the two kinds it keeps
#: apart: what passed between them and the mind or others -- what was done
#: TO the mind first, then time spent together, then what passed between
#: others -- and, separately, how the mind found them: at work, about,
#: passing through, asleep. Kept apart because each says something the
#: other cannot: an encounter at the forge does not say the smith was
#: working, and "at work" does not say they spent the hour together.
_INTERACTION = ("toward_you", "company", "between")
_PRESENCE = ("at_work", "present", "passing", "asleep")

#: The act kinds a resident's turn toward the mind, or toward another, is
#: rendered by; any other kind reads as talk. Keyed by the substrate's own
#: act vocabulary (`charter_practice._AFFORDANCES`).
_TOWARD_YOU = {"tend": "skip_seen_tended_you",
               "accuse": "skip_seen_accused_you",
               "reconcile": "skip_seen_reconciled_you"}
_BETWEEN = {"tend": "skip_seen_tending",
            "accuse": "skip_seen_accusing",
            "reconcile": "skip_seen_reconciling"}


def live_in_charter(cid, scene, mind_name, itinerary, span):
    """Run ``mind_name``'s itinerary through the story's town charter.

    Returns ``(log, far_end)`` in the skip stage's LOG and far-end shapes,
    or None when no charter holds this story or this mind -- and then the
    skip stage's own executor runs the itinerary instead. A cast member
    with no charter body is enrolled for the span alone, and only when the
    charter holds a place its itinerary names; a charter whose own clock has
    already passed the span's start, or a span longer than one advance may
    carry (`MAX_CATCHUP_HOURS`), is None too.

    ``scene`` is the scene the span starts from; ``itinerary`` is a list of
    the stage's STRETCH rows; ``span`` is ``{"from_s", "until_s"}`` in story
    seconds. Nothing is written anywhere.
    """
    from world.charter_runtime import (CHARTER_BUDGET_SECONDS,
                                       MAX_CATCHUP_HOURS, cached_registry)

    span_from, span_until = _span_bounds(span)
    if span_from is None or span_until <= span_from:
        return None
    registry = cached_registry(cid)
    items = (registry or {}).get("items") or {}
    if not items:
        return None
    stretches = _stretches(itinerary, span_from, span_until)
    char_id = _char_id_of(cid, mind_name)
    found = _body_of_mind(registry, char_id, mind_name)
    if found is None:
        charter_key = _charter_naming(registry, stretches)
        if charter_key is None:
            return None
        body_key = "%s%s" % (TEMPORARY_BODY_PREFIX,
                             char_id if char_id is not None else mind_name)
    else:
        charter_key, body_key = found
    behind = 0.0
    for item in items.values():
        last = item.get("last_elapsed_seconds")
        if last is None:
            continue
        if float(last) > span_from + CLOCK_TOLERANCE_SECONDS:
            logger.info(
                "charter skip: chat=%s mind=%r -- a charter has already "
                "lived past the span's start; the stage's own executor "
                "runs it", cid, mind_name)
            return None
        behind = max(behind, span_from - float(last))
    if (behind + span_until - span_from) / 3600.0 > MAX_CATCHUP_HOURS:
        return None
    budget = CHARTER_BUDGET_SECONDS.get("time_skip")
    deadline = None if not budget else time.monotonic() + float(budget)
    run = _TownRun(cid, scene, registry, charter_key, body_key,
                   temporary=found is None, mind_name=mind_name,
                   char_id=char_id, stretches=stretches,
                   span=(span_from, span_until), deadline=deadline)
    run.live()
    return run.log(), run.far_end()


# ------------------------------------------------------------------ inputs

def _span_bounds(span):
    span = span if isinstance(span, dict) else {}
    try:
        return float(span.get("from_s")), float(span.get("until_s"))
    except (TypeError, ValueError):
        return None, None


def _stretches(itinerary, span_from, span_until):
    """The itinerary as ordered stretches clipped to the span, each keeping
    the stage's own fields. A stretch that clips to nothing is dropped; an
    overlap is resolved in favour of the earlier stretch, so every instant
    of the span has at most one declaration speaking for it."""
    rows = []
    for raw in itinerary or ():
        if not isinstance(raw, dict):
            continue
        try:
            start = max(span_from, float(raw.get("from_s")))
            end = min(span_until, float(raw.get("until_s")))
        except (TypeError, ValueError):
            continue
        if end <= start:
            continue
        row = dict(raw)
        row["from_s"], row["until_s"] = start, end
        row["room"] = str(raw.get("room") or "") or None
        row["away"] = str(raw.get("away") or "") or None
        row["asleep"] = bool(raw.get("asleep"))
        rows.append(row)
    rows.sort(key=lambda row: (row["from_s"], row["until_s"]))
    out = []
    for row in rows:
        if out and row["from_s"] < out[-1]["until_s"]:
            row = dict(row, from_s=out[-1]["until_s"])
            if row["until_s"] <= row["from_s"]:
                continue
        out.append(row)
    return out


def _char_id_of(cid, mind_name):
    """The registered character this canonical name is, in this chat, or
    None. Any status: a dormant cast member is asked at a skip too."""
    from core.db import q
    from story.character_schema import character_name_from_text

    wanted = str(mind_name or "").strip()
    if not wanted:
        return None
    rows = q("SELECT ch.id AS id, COALESCE(cc.sheet, ch.sheet) AS sheet "
             "FROM chat_chars cc JOIN characters ch ON ch.id = cc.char_id "
             "WHERE cc.chat_id=? ORDER BY ch.id", (cid,))
    folded = None
    for row in rows or ():
        name = str(character_name_from_text(row["sheet"]) or "").strip()
        if name == wanted:
            return int(row["id"])
        if folded is None and name.casefold() == wanted.casefold():
            folded = int(row["id"])
    return folded


def _body_of_mind(registry, char_id, mind_name):
    """``(charter_key, body_key)`` of the body this registered mind owns:
    bound to it (`bind_promoted_character`), else reserved for it by its
    seat token (`charter_model.mind_seed_char_id`). None when it has none.
    A binding is asked by character id; by its stored name only where the
    mind's id could not be read, since a binding stores the name it was
    bound under and nothing else identifies it then."""
    from world.charter_model import mind_seed_char_id

    reserved = None
    by_name = None
    wanted = str(mind_name or "").strip().casefold()
    for charter_key, item in sorted((registry.get("items") or {}).items()):
        state = item.get("state") or {}
        bodies = state.get("bodies") or {}
        for body_key, binding in sorted((state.get("bindings") or {}).items()):
            if body_key not in bodies or not isinstance(binding, dict):
                continue
            bound_to = binding.get("char_id")
            if char_id is not None and bound_to is not None \
                    and str(bound_to) == str(char_id):
                return str(charter_key), str(body_key)
            if by_name is None and wanted \
                    and str(binding.get("name") or "").strip().casefold() \
                    == wanted:
                by_name = (str(charter_key), str(body_key))
        if char_id is None or reserved is not None:
            continue
        for body_key, body in sorted(bodies.items()):
            seat = mind_seed_char_id((body or {}).get("resident_seed_id"))
            if seat is not None and seat == int(char_id):
                reserved = (str(charter_key), str(body_key))
                break
    if reserved is not None:
        return reserved
    return by_name if char_id is None else None


def _charter_places(state):
    """Every room an institution's people are found in: its work, its
    commons, their berths and wherever they stand now."""
    from world.charter_space import frequented_places
    places = set(frequented_places(state))
    for body in (state.get("bodies") or {}).values():
        for field in ("berth", "place"):
            room = str((body or {}).get(field) or "")
            if room:
                places.add(room)
    return places


def _charter_naming(registry, stretches):
    """The charter a body-less mind is enrolled in: the one holding the most
    of its itinerary's time among its own places, or None when none holds a
    place the itinerary names (the town has nobody where this mind will be)."""
    best = None
    for charter_key, item in sorted((registry.get("items") or {}).items()):
        places = _charter_places(item.get("state") or {})
        weight = sum(row["until_s"] - row["from_s"] for row in stretches
                     if row["room"] and row["room"] in places)
        if weight > 0.0 and (best is None or weight > best[0]):
            best = (weight, str(charter_key))
    return best[1] if best else None


def skip_windows(span_from, span_until, story_day):
    """The instants the town is stepped between across a time skip: the
    span's two ends, every part of the day beginning inside it, and between
    those a cut every `SKIP_WINDOW_HOURS` counted from where each part
    began, so no window is longer than that.

    Depends on nothing about the mind, which is what keeps one town for every
    mind asked; and nothing about where the span ENDS except its last cut,
    which is what lets the town's own advance after the commit
    (`charter_runtime.advance_snapshot`, a time-skip beat) step the same
    windows over a span that runs on past the skip by the beat's own few
    seconds -- so the town the story stores is the town the minds lived in.
    """
    from world.day_cycle import PHASES

    edges = {round(span_from, 6), round(span_until, 6)}
    if story_day is not None:
        anchor, length = story_day
        day = float(length) * 3600.0
        for _name, start, _end in PHASES:
            hour = (float(start) * float(length)) % float(length)
            offset = ((hour - float(anchor)) % float(length)) * 3600.0
            # The first instant at or after the span's start that is this
            # part of the day's beginning, then each day after it.
            at = offset + day * max(0, int((span_from - offset) // day))
            while at < span_from:
                at += day
            while at < span_until:
                edges.add(round(at, 6))
                at += day
    ordered = sorted(edges)
    out = [ordered[0]]
    longest = SKIP_WINDOW_HOURS * 3600.0
    for edge in ordered[1:]:
        start = out[-1]
        if edge <= start:
            continue
        cut = start + longest
        while cut < edge - 1e-6:
            out.append(round(cut, 6))
            cut += longest
        out.append(edge)
    return out


def skip_seed(cid, charter_key, span_from):
    """One institution's seed across a time skip: the story's, the
    charter's and the instant the skip began -- never the mind's, so every
    mind asked meets one town, and never the instant it ends, so the town's
    own advance after the commit, which runs on past the skip by the beat's
    own seconds, draws the same day."""
    from world.mechanics import stable_event_key
    return int(stable_event_key("charter_skip", cid, charter_key,
                                round(float(span_from), 3))[-8:], 16)


# --------------------------------------------------------------------- run

class _TownRun:
    """One mind's span through a scratch copy of the town."""

    def __init__(self, cid, scene, registry, charter_key, body_key, *,
                 temporary, mind_name, char_id, stretches, span, deadline):
        from core.db import active_frame_id
        from world.charter_runtime import _story_day

        self.cid = cid
        self.scene = scene if isinstance(scene, dict) else {}
        self.registry = registry
        self.charter_key = str(charter_key)
        self.body_key = str(body_key)
        self.temporary = bool(temporary)
        self.mind_name = str(mind_name or "")
        self.char_id = char_id
        self.stretches = stretches
        self.span_from, self.span_until = span
        self.deadline = deadline
        self.frame_id = active_frame_id.get()
        try:
            self.story_day = _story_day(cid, self.frame_id)
        except Exception as exc:
            logger.warning("charter skip: chat=%s story day unreadable "
                           "(%s: %s)", cid, type(exc).__name__, exc)
            self.story_day = None
        self.states = {}
        self.samples = []
        self.window_rows = []

    # ---- setting the copy up ------------------------------------------

    def _prepare(self):
        """Copy every institution, give each the scene's room graph and the
        story's hour as the town's own advance would, and stand every mind's
        body where the scene stands it."""
        from world.charter_runtime import (anchor_charter_day, charter_scene,
                                           sync_minds_to_scene)

        for key, item in sorted((self.registry.get("items") or {}).items()):
            state = copy.deepcopy(item.get("state") or {})
            if self.scene.get("rooms"):
                state["scene"] = charter_scene(self.cid, state, self.scene,
                                               self.frame_id)
                sync_minds_to_scene(state, self.scene, key)
            last = item.get("last_elapsed_seconds")
            last = self.span_from if last is None else float(last)
            anchor_charter_day(state, last, self.story_day)
            self.states[str(key)] = {
                "state": state, "last": last,
                "window": float(item.get("window_hours") or 4.0),
                "seed": skip_seed(self.cid, key, last)}

    def _enrol(self):
        """The mind's body in its charter: bound or reserved already, or a
        temporary body that exists only in this copy, bound to the mind so
        the window keeps its hands off its head as it does a bound one's."""
        from world.spatial import room_of

        state = self.states[self.charter_key]["state"]
        start = ""
        if self.scene.get("rooms"):
            try:
                start = str(room_of(self.scene, self.mind_name) or "")
            except Exception:
                start = ""
        if self.temporary:
            # WHERE IT SLEEPS IS ITS BERTH for the span: the room its own
            # day puts it to bed in, else where it stood when the span
            # began. The town walks a body home when nothing else claims
            # it, and the only home this mind has told the town of is that.
            berth = next((row["room"] for row in self.stretches
                          if row["asleep"] and row["room"]), "") or start
            state.setdefault("bodies", {})[self.body_key] = {
                "key": self.body_key, "name": self.mind_name,
                "place": start, "berth": berth, "available": True,
                "competence": {}, "home_post": ""}
            state.setdefault("bindings", {})[self.body_key] = {
                "char_id": self.char_id if self.char_id is not None else -1,
                "entity_id": "", "name": self.mind_name,
                "promoted_turn": None}
        body = state["bodies"].get(self.body_key)
        if body is None:
            return
        # The scene, not the town, stands this body now: a lease the scene
        # holds on it is the scene's, and the skip is the mind's own move.
        body.pop("leased", None)

    def _catch_up(self, grid_from):
        """FROM THE TOWN'S OWN LAST INSTANT, NOT THE SKIP'S FIRST. The town's
        advance after the commit steps a time-skip beat from where each
        charter last stood (`charter_runtime.advance_snapshot`), on the
        skip's windows and with a seed drawn from that instant, so this run
        does the same: the grid opens at the mind's charter's own last
        instant, and the seconds before the span are lived with every mind's
        body held where the scene stands it. Measured, chats 115 and 114:
        their charters stood 5 and 25 seconds behind the story's clock, and
        a grid opened at the skip's start instead drew another day -- 4 of 10
        and 56 of 66 residents where the stored town put them.

        A charter further behind than that one lives its gap first by its
        ordinary windows; it will not be stepped on the same windows as the
        town's own advance, and is the one case that does not match."""
        from world.charter_run import run

        for key, held in self.states.items():
            gap = (grid_from - held["last"]) / 3600.0
            if gap <= 0.0:
                continue
            held["state"], _events = run(
                held["state"], hours=gap, window=held["window"],
                seed=held["seed"], deadline=self.deadline)
            held["last"] = grid_from

    # ---- the span -------------------------------------------------------

    def live(self):
        from world.charter_run import step
        from world.charter_space import (frequented_places, people_neighbors,
                                         reach_map, refresh_reach)

        self._prepare()
        self._enrol()
        grid_from = min(self.span_from,
                        self.states[self.charter_key]["last"])
        self._catch_up(grid_from)
        edges = skip_windows(grid_from, self.span_until, self.story_day)
        graphs = {}
        for key, held in self.states.items():
            state = held["state"]
            scene = state.get("scene")
            places = frequented_places(state) if scene else ()
            neighbors = people_neighbors(scene) if scene else None
            paths = {}
            reach = reach_map(scene, places, state.get("bodies") or {},
                              cache=paths, neighbors=neighbors) \
                if scene else None
            graphs[key] = {"places": places, "neighbors": neighbors,
                           "paths": paths, "routes": {}, "reach": reach,
                           "where": {k: (b or {}).get("place")
                                     for k, b in (state.get("bodies") or {})
                                     .items()}}
        self.samples.append(dict(self._sample(), at=edges[0]))
        simulated = True
        for index in range(1, len(edges)):
            start, end = edges[index - 1], edges[index]
            # Before the span opens the mind is the scene's, not its own
            # day's: its body is held, as the town's own advance holds it.
            ours = end > self.span_from + CLOCK_TOLERANCE_SECONDS
            directive = self._directive(start, end) if ours else None
            self._arrive_or_leave(directive)
            if simulated and self.deadline is not None \
                    and time.monotonic() >= self.deadline:
                # OUT OF BUDGET: the rest of the span is the mind's own
                # declaration, unwitnessed. It stands where each stretch
                # said, and no resident is reported for those windows.
                simulated = False
                logger.warning(
                    "charter skip: chat=%s mind=%r -- time-skip budget "
                    "spent at %.0fs of %.0fs; the rest is unsimulated",
                    self.cid, self.mind_name, start - self.span_from,
                    self.span_until - self.span_from)
            acts = {}
            if simulated:
                for key, held in self.states.items():
                    graph = graphs[key]
                    state = held["state"]
                    scene = state.get("scene")
                    now = {k: (b or {}).get("place")
                           for k, b in (state.get("bodies") or {}).items()}
                    if scene and now != graph["where"]:
                        moved = {k for k, place in now.items()
                                 if graph["where"].get(k) != place}
                        graph["reach"] = refresh_reach(
                            graph["reach"], scene, graph["places"],
                            state.get("bodies") or {}, moved,
                            cache=graph["paths"],
                            neighbors=graph["neighbors"])
                        graph["where"] = now
                    # A charter whose own clock stands later than the grid's
                    # start lives only the part of a window after it.
                    begin = max(start, held["last"])
                    if end <= begin:
                        acts[key] = []
                        continue
                    mine = key == self.charter_key and ours
                    held["state"], _events = step(
                        state, hours=(end - begin) / 3600.0,
                        seed=held["seed"] + index - 1,
                        reach=graph["reach"],
                        paths=graph["paths"],
                        simulate_bound={self.body_key} if mine else False,
                        neighbors=graph["neighbors"],
                        routes=graph["routes"],
                        itinerary=({self.body_key: directive}
                                   if mine and directive is not None
                                   else None))
                    acts[key] = list(held["state"].get("window_acts") or ())
            else:
                self._stand_unsimulated(directive)
            sample = self._sample()
            sample["at"] = end
            sample["simulated"] = simulated
            sample["acts"] = acts
            self.samples.append(sample)
            self.window_rows.append({"start": start, "end": end,
                                     "directive": directive, "ours": ours})

    def _directive(self, start, end):
        """What the mind's own day says for this window: the stretch
        speaking at its middle, as the room it walks to (None to hold where
        it stands) and whether it sleeps; None where the itinerary is silent
        and the town runs the body."""
        middle = max((start + end) / 2.0, self.span_from)
        for row in self.stretches:
            if row["from_s"] <= middle < row["until_s"]:
                return {"room": row["room"], "asleep": row["asleep"],
                        "away": row["away"]}
        return None

    def _body(self):
        state = self.states[self.charter_key]["state"]
        return (state.get("bodies") or {}).get(self.body_key)

    def _arrive_or_leave(self, directive):
        """A stretch AWAY takes the body out of every room for the window
        -- off the map nobody here stands with it -- and a stretch naming a
        room after one brings it back there: there is no route from
        somewhere the world does not hold, so arrival costs no walk here."""
        body = self._body()
        if body is None or directive is None:
            return
        state = self.states[self.charter_key]["state"]
        place = str(body.get("place") or "")
        if directive.get("away"):
            if place:
                body = dict(body, place="")
                body.pop("walk", None)
                body.pop("station", None)
                state["bodies"][self.body_key] = body
            return
        room = str(directive.get("room") or "")
        if room and not place:
            body = dict(body, place=room)
            body.pop("walk", None)
            state["bodies"][self.body_key] = body

    def _stand_unsimulated(self, directive):
        body = self._body()
        if body is None or directive is None:
            return
        room = str(directive.get("room") or "")
        if room:
            state = self.states[self.charter_key]["state"]
            state["bodies"][self.body_key] = dict(body, place=room)

    def _sample(self):
        """Where every body of every institution stands at this instant,
        what it is doing there as a watcher would see it, and the mind's
        own body with the rows its life has added."""
        from world.charter_move import en_route
        from world.day_cycle import RESTING_PHASES, charter_phase

        out = {"bodies": {}, "mind": None}
        for key, held in self.states.items():
            state = held["state"]
            posts = state.get("posts") or {}
            on_post = {}
            for post_key, holder in (state.get("watch") or {}).items():
                place = str((posts.get(post_key) or {}).get("place") or "")
                if place:
                    on_post[str(holder)] = place
            phase = charter_phase(state, state.get("clock_hours"))
            resting = state.get("resting_phases")
            resting = RESTING_PHASES if resting is None else frozenset(
                str(name) for name in resting)
            for body_key, body in (state.get("bodies") or {}).items():
                body = body or {}
                place = str(body.get("place") or "")
                if key == self.charter_key and body_key == self.body_key:
                    rec = body.get("walk") if isinstance(body.get("walk"),
                                                         dict) else {}
                    out["mind"] = {
                        "place": place,
                        "walking_to": str(rec.get("target") or "")
                        if en_route(body) else "",
                        "held": bool(rec.get("held")),
                        "posted": on_post.get(body_key, ""),
                        "experiences": [
                            dict(row) for row in ((state.get("experiences")
                                                   or {}).get(body_key) or ())
                            if isinstance(row, dict)]}
                    continue
                if not place:
                    continue
                if on_post.get(body_key) == place:
                    doing = "at_work"
                elif en_route(body):
                    doing = "passing"
                elif phase in resting \
                        and place == str(body.get("berth") or ""):
                    doing = "asleep"
                else:
                    doing = "present"
                out["bodies"][(key, body_key)] = {"place": place,
                                                  "doing": doing}
        return out

    # ---- the hand-back ------------------------------------------------

    def _rows(self):
        """The span as LOG segments: every stretch, and every silence
        between them the town filled, in order."""
        segments = []
        cursor = self.span_from
        for row in self.stretches:
            if row["from_s"] > cursor:
                segments.append({"from_s": cursor, "until_s": row["from_s"],
                                 "stretch": None})
            segments.append({"from_s": row["from_s"],
                             "until_s": row["until_s"], "stretch": row})
            cursor = row["until_s"]
        if cursor < self.span_until:
            segments.append({"from_s": cursor, "until_s": self.span_until,
                             "stretch": None})
        return segments

    def log(self):
        labels = _Labels(self.cid, self.registry, self.mind_name, self.states)
        out = []
        for segment in self._rows():
            windows = [index for index, window in enumerate(self.window_rows)
                       if window["ours"] and segment["from_s"]
                       <= max((window["start"] + window["end"]) / 2.0,
                              self.span_from)
                       < segment["until_s"]]
            stretch = segment["stretch"]
            if stretch is None:
                out.append(self._silence_row(segment, windows, labels))
            else:
                out.append(self._stretch_row(stretch, windows, labels))
        return out

    def _stretch_row(self, stretch, windows, labels):
        reached, reason, last_place = False, None, None
        for index in windows:
            mind = self.samples[index + 1]["mind"] or {}
            last_place = mind.get("place") or ""
            if stretch["away"] or not stretch["room"]:
                reached = True
                continue
            if last_place == stretch["room"]:
                reached = True
            elif mind.get("held"):
                reason = "shut_way"
            elif mind.get("walking_to"):
                reason = reason or "too_far"
            elif _a_way_exists(self.states[self.charter_key]["state"]
                               .get("scene"), last_place, stretch["room"]):
                # The rooms join, and the way between them is held against
                # a person: a door fastened shut, a way sealed.
                reason = "shut_way"
            else:
                reason = "no_route"
        unrun = not windows or not all(
            self.samples[index + 1].get("simulated", True)
            for index in windows)
        if not windows:
            # A stretch shorter than the town's window speaks for no window
            # of its own: the body was not run through it, so it is the
            # mind's declaration, unwitnessed -- neither carried out nor
            # refused here.
            reached, reason = True, None
            last_place = stretch["room"] or ""
        room = None if stretch["away"] else (last_place or None)
        if reached:
            reason = None
        if not reached:
            outcome = "failed"
        elif stretch["asleep"]:
            outcome = "done"
        elif unrun or stretch["away"] or stretch.get("with") \
                or stretch.get("uses"):
            # Its success waits on somebody else, on a thing, or on a world
            # off the map nobody simulates: the world's to judge.
            outcome = "not_known"
        else:
            outcome = "done"
        seen = [] if stretch["asleep"] else self._seen(windows, labels)
        return {
            "from_s": stretch["from_s"], "until_s": stretch["until_s"],
            "room": room, "away": stretch["away"],
            "where_text": str(stretch.get("where_text") or ""),
            "doing": str(stretch.get("doing") or ""),
            "asleep": bool(stretch["asleep"]),
            "seen": seen, "weather": None,
            "outcome": outcome, "reason": reason if outcome == "failed"
            else None}

    def _silence_row(self, segment, windows, labels):
        """Where the itinerary said nothing and the town ran the body: what
        a watcher saw it do, in the engine's own words, from where it went."""
        from language_runtime import compositor_text

        if windows:
            first = self.samples[windows[0]]["mind"]
            last = self.samples[windows[-1] + 1]["mind"]
        else:
            # Too short to have a window of its own: it is where the body
            # stood when it began.
            first = last = next(
                (sample["mind"] for sample in reversed(self.samples)
                 if sample.get("at", self.span_from) <= segment["from_s"]),
                self.samples[0]["mind"])
        start_place = str((first or {}).get("place") or "")
        end_place = str((last or {}).get("place") or "")
        posted = next((self.samples[index + 1]["mind"].get("posted")
                       for index in windows
                       if (self.samples[index + 1]["mind"] or {})
                       .get("posted")), "")
        if not end_place:
            return {"from_s": segment["from_s"],
                    "until_s": segment["until_s"], "room": None,
                    "away": self._last_away(segment["from_s"]),
                    "where_text": self._last_away(segment["from_s"]) or "",
                    "doing": "", "asleep": False, "seen": [],
                    "weather": None, "outcome": "not_known", "reason": None}
        if posted:
            doing = compositor_text("skip_silence_worked",
                                    place=_room_name(self.scene, posted))
        elif end_place != start_place:
            doing = compositor_text("skip_silence_went",
                                    place=_room_name(self.scene, end_place))
        else:
            doing = compositor_text("skip_silence_stayed",
                                    place=_room_name(self.scene, end_place))
        return {"from_s": segment["from_s"], "until_s": segment["until_s"],
                "room": end_place, "away": None,
                "where_text": _room_name(self.scene, end_place),
                "doing": doing, "asleep": False,
                "seen": self._seen(windows, labels), "weather": None,
                "outcome": "done", "reason": None}

    def _last_away(self, before_s):
        label = None
        for row in self.stretches:
            if row["from_s"] < before_s and row["away"]:
                label = row["away"]
        return label

    def _seen(self, windows, labels):
        """The residents this mind stood among over these windows, under the
        name this mind knows them by: how it found each of them, and the
        most telling thing that passed, each at most once. Read at window
        edges: a resident is with the mind if both stood in one room at the
        window's start or at its end. Only the doing -- the town holds no
        reason for anybody's day, and none is invented here."""
        from language_runtime import compositor_text

        presence, interaction = {}, {}

        def note(ref, kind, other=None):
            table, order = ((interaction, _INTERACTION)
                            if kind in _INTERACTION else
                            (presence, _PRESENCE))
            rank = order.index(kind)
            held = table.get(ref)
            if held is None or rank < held[0]:
                table[ref] = (rank, kind, other)

        for index in windows:
            after = self.samples[index + 1]
            if not after.get("simulated", True):
                continue
            # The instant a row's first window opens is the moment the mind
            # turns from what it was doing before: who stood in the room it
            # is leaving belongs to the row before, unless it never left.
            edges = (self.samples[index], after)
            if index == windows[0] and str(
                    (self.samples[index]["mind"] or {}).get("place") or "") \
                    != str((after["mind"] or {}).get("place") or ""):
                edges = (after,)
            for sample in edges:
                mind = sample["mind"] or {}
                here = str(mind.get("place") or "")
                if not here:
                    continue
                for ref, seen in sample["bodies"].items():
                    if not labels.resident(ref) or seen["place"] != here:
                        continue
                    note(ref, seen["doing"])
            here = str((after["mind"] or {}).get("place") or "")
            for charter_key, rows in (after.get("acts") or {}).items():
                for act in rows:
                    if str(act.get("place") or "") != here or not here:
                        continue
                    actor = (str(charter_key), str(act.get("actor") or ""))
                    if not labels.resident(actor):
                        continue
                    other_key = str(act.get("other") or "")
                    if charter_key == self.charter_key \
                            and other_key == self.body_key:
                        note(actor, "toward_you", str(act.get("act") or ""))
                        continue
                    other = (str(charter_key), other_key)
                    if labels.resident(other):
                        note(actor, "between",
                             (str(act.get("act") or ""), other))
            before_ids = {str(row.get("id") or "") for row in
                          ((self.samples[index]["mind"] or {})
                           .get("experiences") or ())}
            for row in ((after["mind"] or {}).get("experiences") or ()):
                if str(row.get("id") or "") in before_ids \
                        or row.get("kind") != "encounter":
                    continue
                ref = (self.charter_key, str(row.get("other") or ""))
                if labels.resident(ref):
                    note(ref, "company")
        def phrase(kind, other):
            if kind == "toward_you":
                return compositor_text(_TOWARD_YOU.get(
                    other, "skip_seen_spoke_to_you"))
            if kind == "between":
                act, whom = other
                return compositor_text(_BETWEEN.get(
                    act, "skip_seen_talking_with"), other=labels.of(whom))
            return compositor_text("skip_seen_" + kind)

        def order(ref):
            # An interaction outranks any presence; then the label, so a
            # replay lists the room in one order.
            if ref in interaction:
                return (0, interaction[ref][0], labels.of(ref))
            return (1, presence[ref][0], labels.of(ref))

        out = []
        people = sorted(set(presence) | set(interaction), key=order)
        for ref in people[:SEEN_PER_ROW_CAP]:
            who = labels.of(ref)
            if ref in presence:
                _rank, kind, other = presence[ref]
                out.append({"who": who, "doing": phrase(kind, other)})
            if ref in interaction:
                _rank, kind, other = interaction[ref]
                out.append({"who": who, "doing": phrase(kind, other)})
        return out

    def far_end(self):
        """Where the run left the body, and whether it is asleep there."""
        body = self._body() or {}
        place = str(body.get("place") or "")
        last = self.stretches[-1] if self.stretches else None
        speaking = last if last is not None \
            and last["until_s"] >= self.span_until else None
        away = None
        if not place:
            away = (speaking or {}).get("away") \
                or self._last_away(self.span_until + 1.0)
        # A SLEEP DECLARED IS SLEPT, in the bed it named or, where the way
        # there failed, where the body lies: the stretch's row says it
        # failed to reach its room, and the mind is under all the same.
        asleep = bool(speaking and speaking["asleep"])
        since = None
        if asleep:
            since = speaking["from_s"]
            for row in reversed(self.stretches[:-1]):
                if row["asleep"] and row["until_s"] >= since \
                        and (row["room"] or None) == (speaking["room"]
                                                     or None) \
                        and (row["away"] or None) == (speaking["away"]
                                                     or None):
                    since = row["from_s"]
                else:
                    break
            since += self._walk_into(since)
            since = min(since, self.span_until)
        return {"room": place or None, "away": away if not place else None,
                "asleep": asleep, "asleep_since_s": since}

    def _walk_into(self, at_s):
        """The seconds the walk to the bed this sleep began in took from
        where the body stood when the sleep's stretch began: travel eats
        the start of the stretch it is travel to."""
        from world.charter_move import edge_seconds
        from world.charter_space import people_neighbors, walk_route

        index = next((i for i, window in enumerate(self.window_rows)
                      if window["start"] >= at_s), None)
        if index is None:
            return 0.0
        start = str((self.samples[index]["mind"] or {}).get("place") or "")
        end = str((self.samples[index + 1]["mind"] or {}).get("place") or "")
        scene = self.states[self.charter_key]["state"].get("scene")
        if not start or not end or start == end or not scene:
            return 0.0
        route = walk_route(scene, start, end,
                           limit=max(8, len(scene.get("rooms") or ())),
                           neighbors=people_neighbors(scene))
        if not route:
            return 0.0
        return float(sum(edge_seconds(scene, route[i], route[i + 1])
                         for i in range(len(route) - 1)))


# ------------------------------------------------------------------ names

class _Labels:
    """What THIS mind calls each resident: the display name where its own
    `known` ledger recognizes them (`agents.common._recognizes`, the
    predicate perception asks), and otherwise the stranger label perception
    gives an unmet charter body (`agents.common._unknown_actor_label` over
    the body's dealt surface and its institution's public noun). One identity
    floor, the view's own, so a skip's record cannot name somebody the mind's
    eyes on screen would not have."""

    def __init__(self, cid, registry, mind_name, states):
        from core.db import wget
        from world.charter_model import authored_mind_bodies
        from world.charter_runtime import identity_index

        self.registry = registry
        self.states = states
        self.index = identity_index(registry)
        self.known = [str(name) for name in
                      ((wget(cid, "known", {}) or {}).get(mind_name) or ())]
        self.minds = {}
        for key, held in states.items():
            self.minds[key] = authored_mind_bodies(held["state"])
        self.cache = {}

    def resident(self, ref):
        charter_key, body_key = ref
        held = self.states.get(charter_key)
        if held is None or not body_key:
            return False
        if body_key not in (held["state"].get("bodies") or {}):
            return False
        return body_key not in self.minds.get(charter_key, ())

    def of(self, ref):
        if ref in self.cache:
            return self.cache[ref]
        charter_key, body_key = ref
        label = self._name(charter_key, body_key) \
            or self._stranger(charter_key, body_key)
        self.cache[ref] = label
        return label

    def _name(self, charter_key, body_key):
        from agents.common import _recognizes

        try:
            display = str(self.index.display(charter_key)[body_key] or "")
            forms = [display] + [str(alias) for alias in
                                 (self.index.aliases(charter_key)[body_key]
                                  or ())]
        except Exception:
            return ""
        if not self.known:
            return ""
        for form in forms:
            if form and _recognizes(form, self.known):
                return display
        return ""

    def _stranger(self, charter_key, body_key):
        from agents.common import _unknown_actor_label
        from world.charter_crowd import member_noun
        from world.charter_surface import surface_of

        # THE TOWN AS IT STANDS, not as the run left it: a label is one
        # person's for the whole record, and the run's last window (who
        # happened to be on the bill when the span ended) is no reason for
        # the smith to be "the smith" in one record and a person in the next.
        state = ((self.registry.get("items") or {}).get(charter_key)
                 or {}).get("state") or {}
        if body_key not in (state.get("bodies") or {}):
            state = self.states[charter_key]["state"]
        try:
            surface = surface_of(state, body_key)
            noun = member_noun(state, body_key)
        except Exception:
            surface, noun = None, ""
        return _unknown_actor_label("", None, None, role=noun,
                                    surface=surface)


def _a_way_exists(scene, start, end):
    """Do these rooms join at all, whatever stands in the way? The graph a
    person walks (`charter_space.people_neighbors`) leaves out a way held
    shut; this one keeps every edge, so a stretch the first refused and this
    admits failed on a shut way rather than on no way."""
    rooms = (scene or {}).get("rooms") if isinstance(scene, dict) else None
    start, end = str(start or ""), str(end or "")
    if not isinstance(rooms, dict) or not start or not end \
            or start not in rooms or end not in rooms:
        return False
    frontier, seen = [start], {start}
    while frontier:
        here = frontier.pop()
        if here == end:
            return True
        for edge in (rooms.get(here) or {}).get("adjacent") or ():
            nxt = str((edge or {}).get("to") or "") \
                if isinstance(edge, dict) else ""
            if nxt and nxt in rooms and nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    return False


def _room_name(scene, room):
    record = ((scene or {}).get("rooms") or {}).get(str(room)) or {}
    return str(record.get("name") or room or "")


__all__ = ["CLOCK_TOLERANCE_SECONDS", "FAILURE_REASONS", "SEEN_PER_ROW_CAP",
           "SKIP_WINDOW_HOURS", "TEMPORARY_BODY_PREFIX", "live_in_charter",
           "skip_seed", "skip_windows"]
