"""Character decision agent."""

from __future__ import annotations

import json
from collections import deque

from affect import (CRISIS_STRAIN_MIN, INTENT_DORMANT_AFTER,
                    RUPTURE_FORCE_AFTER, ground_tells)
from db import q, wget
from character_schema import (
    character_abilities,
    character_curiosity,
    character_interoception,
    character_name,
    character_projects,
    character_psychology,
    character_standing_intentions,
    effective_drive,
    character_public_history,
    character_sampler,
    character_senses,
    character_temperature,
    character_tier,
    character_voice,
    senses_as_text,
)
from frames import is_recognized_in_frame
from memory import (
    build_character_memory_context,
    knowledge_for_character,
    relationships_for_payload,
)
from prompts import get_prompt
from scene import (
    NON_AWAKE_GATED,
    all_cast_name_to_id,
    awareness_of,
    dialogue_budget,
    get_scene,
    persona_of,
    private_knowledge_for,
    sheet_state,
)
from schemas import validate_llm_output
from spatial import (corridor_sightlines, room_of, spatial_digest,
                     sprint_reach, visible_adjacent_rooms)
from survival import vitals_of
from psychology_runtime import cognitive_absorption
from theory_of_mind import mind_models_for_payload, sheet_capacity

from .common import (
    _agent_json,
    _books,
    _char_known_tags,
    _dict,
    _list,
    _normalize_character_output,
    assign_event_ids,
    cap_mind_model_updates,
    character_room,
    norm_sequence,
)

def _merge_standing_intentions(authored, emergent):
    """Merge a character's authored standing intentions with the emergent ones
    formed at runtime. Authored intentions are always present (the character's
    defining goals), but an emergent intention whose text closely restates an
    authored one SUPERSEDES it -- the emergent copy carries live progress/status
    (including a `blocked`/nonviable state), so a goal the world has closed does
    not reappear as freshly-active. De-dup is by casefolded intent text."""
    emergent = [i for i in (emergent or []) if isinstance(i, dict)]
    seen = {str(i.get("intent") or "").strip().casefold() for i in emergent}
    kept_authored = [
        a for a in (authored or [])
        if isinstance(a, dict)
        and str(a.get("intent") or "").strip().casefold() not in seen
    ]
    return kept_authored + emergent


def _recent_self_lines(chat_id, char_name, current_turn_idx, n_turns=3, cap=4,
                       frame_id=None):
    """The character's own most-recent spoken lines, verbatim, oldest->newest,
    from the last few committed turns' director_resolve dialogue_log.

    Without this the character agent only ever sees the CURRENT beat plus its
    static sheet, so a character in a standing situation (an escort repeating
    'keep moving' at a checkpoint that will not clear) re-derives the same line
    turn after turn -- verbatim repetition reads as a broken machine. Feeding
    its own recent lines lets it notice the refrain and vary or escalate
    (through specificity/consequence, per the character prompt), never as an
    emotional-volume spike."""
    if current_turn_idx is None:
        return []
    rows = q(
        "SELECT t.idx AS idx, v.content AS content FROM turns t "
        "JOIN steps s ON s.turn_id=t.id AND s.key='director_resolve' "
        "JOIN variants v ON v.step_id=s.id AND v.active=1 "
        "WHERE t.chat_id=? AND t.idx < ? AND t.frame_id IS ? "
        "ORDER BY t.idx DESC LIMIT ?",
        (chat_id, current_turn_idx, frame_id, n_turns),
    )
    cf = str(char_name or "").casefold()
    lines = []
    for r in rows:
        try:
            dr = json.loads(r["content"])
        except (TypeError, ValueError):
            continue
        for d in (dr.get("dialogue_log") or []):
            if str(d.get("speaker") or "").casefold() == cf:
                quote = str(d.get("exact_quote") or "").strip()
                if quote:
                    lines.append({"turn": r["idx"], "said": quote})
    lines.sort(key=lambda x: x["turn"])
    return lines[-cap:]


def _known_pronouns(cast, persona, recognized, exclude=None):
    """Canonical pronouns for the people this character ALREADY KNOWS, so a
    speaker refers to others correctly instead of guessing from a name (W6 --
    Crusher said "her discovery" about a he/him character).

    Info barrier: `recognized` is the character's own relationship/mind-model
    key set, which the caller has already frame-filtered by recognition. A
    stranger in the room is deliberately absent -- you don't know an
    unfamiliar person's pronouns, and handing them over would leak identity
    the character never legitimately acquired.
    """
    sheets = []
    for row in (cast or []):
        try:
            sheets.append((json.loads(row["sheet"]).get("identity") or {}))
        except Exception:
            continue
    if isinstance(persona, dict):
        sheets.append(persona.get("identity") or {})
    out = {}
    skip = {str(n or "").strip().casefold() for n in (exclude or [])}
    known = {str(n or "").strip().casefold() for n in (recognized or [])}
    for ident in sheets:
        name = str(ident.get("name") or "").strip()
        folded = name.casefold()
        if not name or folded in skip or folded not in known:
            continue
        pronouns = ident.get("pronouns") or {}
        clean = {k: pronouns[k] for k in ("subject", "object", "possessive")
                 if isinstance(pronouns, dict) and pronouns.get(k)}
        if clean:
            out[name] = clean
    return out


# How far back "recently" reaches. Twelve beats is long enough to contain a
# couple of honest there-and-back trips through a hub, short enough that a
# genuine lock shows inside it.
LOOP_WINDOW = 12
# A pocket is measured as a RATIO, not a room count. A fixed count of four was
# tried first and immediately missed the real thing: a lock observed live
# widened from three rooms to five as he wandered a little further each cycle,
# and five rooms over twelve beats -- every room walked twice over -- is no
# less stuck than three. Half the window is the threshold because a character
# genuinely covering ground has a ratio near 1.0, so this cannot fire on
# exploration however fast it moves.
LOOP_DENSITY = 0.5


# The verdicts, most decisive first. A character was being handed eight
# separate facts per doorway and left to aggregate them into a decision --
# work the deterministic layer can already do, and do reliably. This is the
# same principle as re-deriving perception's structured observations from the
# scrubbed prose rather than trusting the model to have agreed with itself:
# where the engine knows the answer, it should say the answer.
#
# The raw markers stay underneath. This adds a reading, it does not replace
# the evidence, and a model that wants to disagree with the reading still has
# everything it needs to.
_VERDICTS = (
    ("visibly_no_way_through", "closed",
     "you can see from here it has no other way out"),
    # Split out below in _verdict when the chamber is also UNTRIED. What a
    # room LEADS TO and what is IN it are different questions, and `closed`
    # only ever answered the first.

    ("no_route_onward", "no way through",
     "you went in and had to come straight back, more than once"),
    ("no_new_ground_that_way", "spent",
     "every door you have seen down that way is one you have taken"),
    ("circling_here", "circling",
     "you have been going round these same few rooms"),
    ("untried", "UNTRIED",
     "you have never been through this doorway"),
    ("worked_before", "proven",
     "that way once took you somewhere you meant to get to"),
    ("been_there", "known",
     "you have been through here before"),
)
# Ordering only. `untried` leads and the discouraging verdicts trail, but
# `proven` deliberately sits just behind `untried` rather than ahead of it:
# choosing between a way that worked and a way not yet tried is what
# curiosity is FOR, and hard-coding it here would quietly settle a question
# the character is supposed to answer.
# `unentered` sits just behind `known`: a cul-de-sac you have never looked
# inside is worse than a route (it goes nowhere) and better than ground you
# have already covered (it might hold what you are looking for).
_APPEAL_ORDER = ("UNTRIED", "proven", "unentered", "known", "circling",
                 "spent", "no way through", "closed")
# The verdicts that argue AGAINST taking an exit. For these the supporting
# counters are redundant with the verdict itself and are dropped, so that a
# discouraged door never outweighs the encouraged one beside it.
# `unentered` is deliberately absent: its supporting markers are the only
# evidence the character has about a room they have never been in.
_DISCOURAGING = frozenset({"circling", "spent", "no way through", "closed"})


def _verdict(entry, frontier_hops=None):
    """One reading of an exit, added alongside its evidence.

    `frontier_hops` grades the `known` verdict: how many rooms down that way
    the nearest door seen-but-never-taken stands, measured over the
    character's OWN place graph. The open problem it answers was observed at
    the start of every repeat maze run: each neighbouring exit `known`, none
    untried, none proven -- the verdicts had nothing to say and the character
    thrashed (north, back, north, back). Local history cannot answer "which
    known exit leads TOWARD ground I have not explored"; the graph can, and
    where the engine knows the answer it should say the answer. Folded into
    the verdict STRING and the ordering only, never a key of its own: the
    salience inversion (the right door as the lightest entry) was fixed once
    and must not be re-created by decoration.
    """
    for key, label, because in _VERDICTS:
        if not entry.get(key):
            continue
        # A cul-de-sac you have NEVER been inside is not a spent one. `closed`
        # is a fact about where a room LEADS; it says nothing about what is
        # in it, and it was masking `untried` entirely because it sits first
        # in the precedence.
        #
        # Measured in maze arm A11 run 3. The shrine -- the thing he is in
        # the maze to reach -- is a cul-de-sac. He walked sixteen optimal
        # moves to its doorway, SAW it ("a grey-slate room with a toppled
        # bench and a still water basin, which is a shrine"), read the
        # verdict "closed -- you can see from here it has no other way out",
        # concluded "it's a dead end, so that would be a waste of time", and
        # turned around. Chamber 0603 was never entered in any run of the
        # arm. Every arrival is a cul-de-sac: you go to the shrine, the
        # bedroom, the vault BECAUSE of what is in it, not to pass through.
        if key == "visibly_no_way_through" and entry.get("untried"):
            label = "unentered"
            because = ("it has no other way out, but you have never been "
                       "inside it -- what is IN a room is a different "
                       "question from what it leads to, and things worth "
                       "reaching are usually not thoroughfares")
        detail = because
        if label == "circling" and entry.get("entered_recently"):
            detail = (f"you have been in there {entry['entered_recently']} "
                      "times in your last dozen paces")
        # The distance rides ANY verdict that has one, not only `known`.
        # Restricting it to `known` suppressed it exactly where it mattered
        # most: measured in maze arm A11, a character stood with both exits
        # discouraging -- one `spent`, one `circling` -- while the `circling`
        # one led to the ONLY frontier left in the maze, nine rooms off. He
        # was told both were bad and given no way to tell them apart, so he
        # paced the pocket. The verdict describes his history; the distance
        # describes his prospects, and a room he has circled through can
        # still be the way out.
        if isinstance(frontier_hops, int) and frontier_hops >= 1:
            if frontier_hops == 1:
                detail += ("; the room through it still has a door you have "
                           "never taken")
            else:
                detail += ("; the nearest door you have never taken lies "
                           f"about {frontier_hops} rooms down that way")
        entry["verdict"] = f"{label} — {detail}"
        if label in _DISCOURAGING:
            # These numbers all say the same thing as the verdict, and
            # together they were three times the text of the untried door
            # beside them. The verdict carries the reading; the rest were
            # crowding out the answer. Applies to every discouraging verdict,
            # not only circling -- scoped to circling alone at first, which
            # left a `no way through` exit carrying eight keys against an
            # untried one carrying four, the same imbalance one label over.
            for redundant in ("times_entered", "turned_back_here",
                              "last_seen_beats_ago"):
                entry.pop(redundant, None)
        break
    return entry


def _appeal(entry):
    # Non-dict junk is passed through untouched elsewhere, so it must sort
    # too. It trails, and `sorted` being stable keeps whatever order it
    # arrived in.
    if not isinstance(entry, dict):
        return len(_APPEAL_ORDER)
    label = str(entry.get("verdict") or "").split(" — ")[0]
    try:
        return _APPEAL_ORDER.index(label)
    except ValueError:
        return len(_APPEAL_ORDER)


def _frontier_hops(first_step, here_rid, adj, walked, closed):
    """How many rooms down that way the nearest door seen-but-never-taken
    stands: BFS over the character's own knowledge (adjacency they recorded by
    standing in rooms, walkedness from their durable graph, chambers they saw
    were closed). Returns None when everything seen down that branch is spent,
    and 0 when the branch is live but unmeasurable (a room stood in whose
    exits were never recorded -- pre-graph saves).

    Replaces a boolean. The boolean answered "is there ANY route left untried
    that way" and went mute at the start of every repeat run, when every
    neighbouring exit was known and almost every branch still held frontier
    somewhere: all True is no answer. Distance is the discriminating fact a
    person who walked the ground actually has -- "the unexplored part is off
    that way, not far" -- and it crosses no boundary, being computed entirely
    from where they stood and what they saw from there.
    """
    if first_step not in walked:
        return 0
    if first_step not in adj:
        return 0
    seen = {here_rid, first_step}
    queue = deque([(first_step, 1)])
    while queue:
        cur, depth = queue.popleft()
        for nxt in adj.get(cur, ()):
            if nxt in seen:
                continue
            seen.add(nxt)
            if nxt not in walked:
                if nxt not in closed:
                    return depth      # a door seen and never taken
                continue
            queue.append((nxt, depth + 1))
    return None


def _intent_is_live(intent, now_turn):
    """Whether an active intention still speaks for what the character wants.

    `status == "active"` is not enough on its own. Intentions outlive their
    usefulness by design -- they are spent by the world rather than closed by
    a decision -- so a character carries rows that were true fifty beats ago
    and are merely not yet swept. That is harmless for motivation, where a
    dormant row simply loses, and harmful here, because naming a chamber is
    all it takes to redirect every routed move.

    Measured in A13 run 4: `i3`, "Explore connectivity from Chamber 0504 via
    western passage", sat active at progress 0.2 long after the exploration
    it described was over, while the character's own goal named the shrine.
    Stalled and blocked rows are excluded for the same reason -- an intention
    the world has already refused is the worst possible thing to steer by.
    """
    if intent.get("stalled_turn") or intent.get("blocked_turn"):
        return False
    if not isinstance(now_turn, int):
        return True
    try:
        last = int(intent.get("last_progress_turn"))
    except (TypeError, ValueError):
        return True
    return (now_turn - last) <= _INTENT_STALE_TURNS


# How many turns an intention may go without progress and still be trusted to
# name a destination. Deliberately generous: this gate exists to drop rows the
# character has plainly moved on from, not to second-guess a long patient aim.
_INTENT_STALE_TURNS = 40


def _destination_from_goals(stored_state, place_graph, here_rid=None,
                            now_turn=None):
    """The room this character's own goals NAME, resolved against his own map.

    Measured need (A12, run 4): a courier with a re-armed commission and a
    place graph holding a complete, optimal 28-room route to the shrine spent
    five beats standing still working out which way he already knew to go --
    r0003 entered three times, a northward step into a wall -- because every
    affordance answers "where have I not been" and none answers "how do I
    reach the room I already want". His own proven route read back to him as
    "spent Chamber 0003".

    The legitimacy gate is double: the destination must be named by HIS OWN
    authored text, and he must own a place-graph node for it. Sources are
    active_state.goal first, then active intentions by priority, then held
    projects (interior.projects) as the durable fallback --
    goal-first is not a stylistic choice: in the live failure no active
    intention named a chamber at all except a stale one at progress 1.0
    naming "Chamber 0401" (actively wrong), while his self-authored goal
    named "Chamber 0603" from the first pacing beat (right, and current).
    Resolution is exact node-NAME matching against his own nodes -- both
    vocabularies closed, so this is identifier recognition, not reading
    prose. Within a text the last-named room wins: "from the gate to the
    shrine" is going TO the shrine. Returns {"rid", "name"} or None, and
    None means silence -- no route is ever computed to a room he has not
    both wanted and walked.
    """
    nodes = (place_graph or {}).get("nodes")
    nodes = nodes if isinstance(nodes, dict) else {}
    named = {}
    for rid, rec in nodes.items():
        if not isinstance(rec, dict):
            continue
        name = str(rec.get("name") or "").strip()
        if name:
            named.setdefault(name.casefold(), (str(rid), name))
    if not named:
        return None
    st = stored_state if isinstance(stored_state, dict) else {}
    texts = []
    goal = str(((st.get("active_state") or {}).get("goal")) or "").strip()
    if goal:
        texts.append(goal)
    intents = [i for i in ((st.get("interior") or {}).get("intentions") or [])
               if isinstance(i, dict) and i.get("status") == "active"
               and _intent_is_live(i, now_turn)]

    def _prio(intent):
        try:
            return -float(intent.get("priority") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    texts.extend(str(i.get("intent") or "") for i in sorted(intents, key=_prio))
    # PROJECTS last: the durable fallback. This is the measured hole the
    # project tier closes on the routing side -- when the beat goal names
    # nothing and every intention naming the aim has been satisfied once,
    # decayed dormant, or died with its tactic, a standing commitment that
    # names a room ("every run ends at the shrine in Chamber 0603") still
    # routes. Behind goal and intentions on purpose: a project is what he is
    # about, not necessarily where he is going THIS beat.
    texts.extend(
        str(p.get("project") or "")
        for p in ((st.get("interior") or {}).get("projects") or [])
        if isinstance(p, dict))
    for text in texts:
        folded = text.casefold()
        best = None
        for key, resolved in named.items():
            pos = folded.rfind(key)
            if pos >= 0 and (best is None or pos > best[0]):
                best = (pos, resolved)
        if best:
            rid, name = best[1]
            # A route to the room you are standing in is not information, and
            # claiming the slot with it silences the destination that would
            # have been. Characters phrase goals as the next step far more
            # often than as the aim -- "Run east to Chamber 0004 to progress
            # toward the shrine" names only the waypoint, because the shrine
            # is not a chamber NAME -- so the nearest text wins the match and
            # the real destination never gets looked for. Skipping to the
            # next text is what lets the standing intention be heard.
            if here_rid is not None and str(rid) == str(here_rid):
                continue
            return {"rid": rid, "name": name}
    return None


def _taken_adjacency(g_edges):
    """Doorways this character has actually TAKEN, as an undirected map.

    Stricter than plain adjacency on purpose: adjacency includes doors merely
    seen from rooms stood in, which is enough to know a frontier exists and
    not enough to promise a way through. A route offered toward a goal is a
    promise his feet made.

    Shared by the exit annotator and the run offers so the two cannot drift.
    A run judged against a different graph than the exits beside it would
    give the character two irreconcilable answers inside one payload.
    """
    taken, disproven = {}, []
    for a, side in (g_edges or {}).items():
        if not isinstance(side, dict):
            continue
        for b, rec in side.items():
            if not isinstance(rec, dict):
                continue
            if rec.get("disproven"):
                disproven.append((str(a), str(b)))
                continue
            if not rec.get("taken"):
                continue
            taken.setdefault(str(a), set()).add(str(b))
            taken.setdefault(str(b), set()).add(str(a))
    # A doorway disproven from either side is disproven, and the recording
    # is one-sided as often as not.
    for a, b in disproven:
        taken.get(a, set()).discard(b)
        taken.get(b, set()).discard(a)
    return taken


def _hops_to(rid, dest_rid, taken_adj):
    """Rooms from here to there over ground he has walked. 0 standing in it,
    None when no remembered route runs there at all.

    Same firewall as `_toward_hops`: his own graph, never the scene.
    """
    if rid == dest_rid:
        return 0
    seen = {rid}
    queue = deque([(rid, 0)])
    while queue:
        cur, depth = queue.popleft()
        for nxt in taken_adj.get(cur, ()):
            if nxt in seen:
                continue
            if nxt == dest_rid:
                return depth + 1
            seen.add(nxt)
            queue.append((nxt, depth + 1))
    return None


def _toward_hops(first_step, here_rid, taken_adj, dest_rid):
    """Rooms along this character's OWN walked ground from an exit to the
    destination his goals name: BFS over doorways he has actually taken
    (never merely seen -- a door seen from across a room is known to exist,
    not known to pass), minus the disproven. Returns the room count entering
    the destination, 1 when the exit IS it, None when no remembered route
    runs that way.

    Deliberately never reads the scene. If his map is wrong, the route is
    wrong in exactly the way his map is wrong -- a corridor bricked up since
    he walked it still routes, and he finds out with his feet. That is the
    property the maze-expansion arm measures, and consulting the true graph
    here would both leak unearned map and erase the measurement.
    """
    if first_step == dest_rid:
        return 1
    if first_step not in taken_adj:
        return None
    seen = {here_rid, first_step}
    queue = deque([(first_step, 1)])
    while queue:
        cur, depth = queue.popleft()
        for nxt in taken_adj.get(cur, ()):
            if nxt in seen:
                continue
            if nxt == dest_rid:
                return depth + 1
            seen.add(nxt)
            queue.append((nxt, depth + 1))
    return None


# An active intention idle for two-thirds of the dormancy fuse is surfaced
# as `fading` in the payload. Decay itself is right -- an aim yielding
# nothing for thirty turns should lose its grip -- but until now it was
# silent bookkeeping: the status flipped in commit and the character
# discovered, beats later, that they no longer wanted something. A courier
# walked sixteen optimal rooms to the shrine's threshold and turned away
# because the goal underneath had been spent by a sweep he was never party
# to (A11/A12). Surfacing the burning fuse lets the giving-up happen BY the
# character -- renew by acting, revise, or abandon with a stated reason --
# with the sweep remaining only as the backstop for an unanswered question.
_FADING_AFTER = (INTENT_DORMANT_AFTER * 2) // 3


def _annotate_fading(intentions, now_turn):
    """Mark each active intention that is near the dormancy sweep with how
    many beats it has yielded nothing. Read-side only, non-mutating: the
    stored rows and the sweep in affect.apply_intent_ops are untouched, so
    this adds a legible question, not a new lifecycle."""
    if not isinstance(now_turn, int):
        return intentions
    out = []
    for intent in intentions or []:
        if not isinstance(intent, dict):
            out.append(intent)
            continue
        intent = dict(intent)
        if intent.get("status") == "active":
            try:
                idle = now_turn - int(intent.get("last_progress_turn"))
            except (TypeError, ValueError):
                idle = None
            if idle is not None and idle >= _FADING_AFTER:
                intent["fading"] = idle
        out.append(intent)
    return out


# Beats a held project may go unserved before the payload says so. Above
# the fading threshold's granularity on purpose being a different clock:
# eight beats is long enough for a scene to legitimately demand other
# things (a project can REST), short enough to catch the measured mid-run
# drift (A15 run 5: visibly adrift by beat 10, twenty beats before anything
# could have said so). The marker only ever grows in wording, never in
# mechanism -- a project must not decay, and never-noticing is the failure
# mode this closes.
_ADRIFT_AFTER = 8


def _annotate_project_drift(projects, now_turn):
    """Mark each held project with how many beats since anything the
    character did served it -- commit's last_served_turn ledger read back.
    The gap between HOLDING a project and SERVING it was invisible: pa1 sat
    in the payload as a static string while the top want served the drive,
    and nothing anywhere marked the distance between the two. Read-side and
    non-mutating, exactly like _annotate_fading: a fact the character can
    notice, never a mechanism that acts. A project with no ledger entry yet
    (authored, pre-first-commit) is silent -- absent means cannot tell."""
    if not isinstance(now_turn, int):
        return projects
    out = []
    for p in projects or []:
        if not isinstance(p, dict):
            out.append(p)
            continue
        p = dict(p)
        try:
            idle = now_turn - int(p.get("last_served_turn"))
        except (TypeError, ValueError):
            idle = None
        if idle is not None and idle >= _ADRIFT_AFTER:
            p["adrift"] = idle
        out.append(p)
    return out


def _en_route(stored_state, here_rid, destination):
    """The journey he is already on, read back to him: the room his own
    goals name, how many rooms of his own walked ground remain to it, and
    whether the last room he stood in was nearer or farther than this one.

    Measured need (A14, post-completeness-fix): with routing, verdicts and
    run offers all naming his destination, a character 9 rooms from the
    chamber he had himself chosen closed to 7 and gave it all back -- trail
    9 9 7 8 9, four beats, net zero. The previous goal TEXT is already in
    the payload (self.active_state.goal), but a nine-room journey still
    needs the same intent to win the beat auction nine independent times,
    and incumbency carried no weight because it was nowhere stated as a
    STATUS: not how far in he was, not that the last beat closed distance.
    This states it. A fact, never a leash: continuation stays the model's
    decision, and the prompt frames leaving a journey as the deliberate
    act.

    Derived entirely at payload time: the destination is the one
    _destination_from_goals already resolved from his OWN previous goal and
    live intentions, and the distance runs over doorways his feet actually
    took (_hops_to on _taken_adjacency -- the same graph the exit verdicts
    and run offers are judged against, so the payload cannot argue with
    itself, and the same firewall: his map, never the scene). Nothing
    persists, so nothing needs cancel machinery -- every ending the journey
    can have is a change in the derivation itself next beat: arriving
    empties the destination, renaming the aim moves it, a disproven doorway
    breaks the remembered way into silence.

    Silence also under two rooms out: a neighbouring destination is already
    fully carried by its exit's "through here is X itself" verdict, and a
    character crossing a house to answer a door does not need a status line
    about the hallway.
    """
    if not (isinstance(destination, dict) and destination.get("rid")
            and here_rid):
        return None
    dest_rid = str(destination["rid"])
    here = str(here_rid)
    st = stored_state if isinstance(stored_state, dict) else {}
    graph = st.get("place_graph")
    graph = graph if isinstance(graph, dict) else {}
    taken = _taken_adjacency(graph.get("edges") or {})
    left = _hops_to(here, dest_rid, taken)
    if left is None or left < 2:
        return None
    out = {"to": str(destination.get("name") or dest_rid),
           "rooms_left": left}
    # The last DIFFERENT room stood in, off his own route window. By room
    # rather than by beat, because a run crosses several rooms in one beat
    # and dwelling crosses none; the SIGN is the fact that matters -- nine
    # rooms walked and given back is not nine rooms walked. Neither key
    # when the distance held or the window cannot say: absent means cannot
    # tell, never "no progress".
    prev = None
    for r in reversed(st.get("visited_rooms") or []):
        if isinstance(r, str) and r and r != here:
            prev = r
            break
    if prev:
        was = _hops_to(prev, dest_rid, taken)
        if was is not None:
            if left < was:
                out["closer_than_last_room"] = True
            elif left > was:
                out["further_than_last_room"] = True
    return out


def _annotate_known_exits(digest, scene, visited_rooms, known_exits=None,
                          here_rid=None, routes_that_worked=None,
                          known_dead_ends=None, place_graph=None,
                          destination=None):
    """Mark each exit with whether this character has been through it.

    `spatial_digest` renders an exit as {room, barrier} -- identical whether
    the character arrived through that doorway a beat ago or has never taken
    it. With nothing to separate them, preferring the unexplored exit is not a
    choice the payload makes available, and the result reads as backtracking.

    `visited_rooms` is the character's OWN route (commit records it from their
    committed position), so this adds no knowledge they did not earn by
    walking. `last_seen_beats_ago` is ordinal, not a turn count: how far back
    in their own route it was, which is the form a person actually has.

    `no_route_onward` marks an exit they entered and always had to reverse out
    of -- the thing `been_there` cannot say, and the thing that actually stops
    a repeated wrong turn. It is about DOORWAYS, not worth: somewhere they
    chose to linger is never marked, because that is a destination rather than
    a wrong turn.
    """
    if not isinstance(digest, dict):
        return digest
    rooms = (scene or {}).get("rooms") or {}
    name_to_id = {}
    for rid, room in rooms.items():
        display = str((room or {}).get("name") or rid)
        name_to_id.setdefault(display, rid)
    # What can be SEEN through each doorway right now, as against what has been
    # walked. A chamber with no other way out is visible as such from the
    # threshold; making a character enter it to find out is not caution, it is
    # a missing sense.
    seen_onward, seen_bearings = {}, {}
    if here_rid:
        try:
            from spatial import visible_adjacent_rooms
            for item in visible_adjacent_rooms(scene, here_rid) or []:
                if isinstance(item, dict) and "onward_exits" in item:
                    rid_seen = str(item.get("room_id"))
                    seen_onward[rid_seen] = item["onward_exits"]
                    # WHICH way on, not merely how many. The digest buckets
                    # exits egocentrically (ahead/behind/left), so a count
                    # sitting on the "behind" bucket carries no heading of its
                    # own and gets read as "on in the direction I was already
                    # facing" -- which is how a runner came to hunt a westward
                    # exit, four times, out of a chamber whose only other way
                    # out went north.
                    if item.get("onward_bearings"):
                        seen_bearings[rid_seen] = item["onward_bearings"]
        except Exception:
            seen_onward, seen_bearings = {}, {}
    worked = routes_that_worked if isinstance(routes_that_worked, dict) else {}
    route = [r for r in (visited_rooms or []) if isinstance(r, str)]
    counts = {}
    for rid in route:
        counts[rid] = counts.get(rid, 0) + 1
    # HOW RECENTLY, not merely how often. `times_entered` is a lifetime tally,
    # and a lifetime tally cannot tell "four times over eighty beats" from
    # "four times in the last twelve" -- which are the difference between a
    # thoroughfare and a loop you are stuck in.
    #
    # Observed live: on his second attempt at the same maze a character locked
    # into a period-four cycle, 0001 -> 0002 -> 0001 -> 0000, three times
    # exactly. He was not blind to the way out -- he GENERATED "south into
    # 0100" as a candidate, that being real new ground, and rejected it with
    # `norm_conflict: conflicts with association that east from blue-tile
    # reset leads toward 0507`. A route learned on the previous run was
    # outranking the evidence in front of him, and nothing in the payload said
    # that route had just failed three times running.
    #
    # This is the missing fact, and it is his own route, so it crosses no
    # boundary: a person who has walked the same three rooms four times in a
    # dozen paces knows it without being told.
    recent = route[-LOOP_WINDOW:]
    recent_counts = {}
    for rid in recent:
        recent_counts[rid] = recent_counts.get(rid, 0) + 1
    # A pocket is a handful of rooms that have absorbed a long stretch of the
    # route. Deliberately conservative: it needs a nearly-full window AND
    # genuinely few rooms, so that ordinary back-and-forth through a hub does
    # not read as being stuck.
    # BEATS SINCE NEW GROUND is the honest measure, and the density test above
    # is only a fast path for tight locks. Counting distinct rooms in a window
    # fails on the shape that matters most: an out-and-back along a corridor
    # fills the window with distinct rooms while making no progress at all.
    #
    # Observed live, twice, each time one level larger than the test written
    # for the last one. A fixed four-room threshold missed a lock that widened
    # to five. The ratio that replaced it went silent at a seven-room corridor
    # walked end to end -- 0001/0101/0201/0202/0203/0204/0104, ten beats, not
    # one room he had not already seen. The loop got worse and the warning
    # stopped. Room counts measure the wrong thing; what a lost person
    # actually notices is that nothing has been new for a while.
    since_new = 0
    seen_so_far = set()
    for i, rid in enumerate(route):
        if rid not in seen_so_far:
            seen_so_far.add(rid)
            since_new = 0
        else:
            since_new += 1
    circling = set()
    if since_new and (since_new >= LOOP_WINDOW or (
            len(recent) >= LOOP_WINDOW
            and len(set(recent)) <= LOOP_DENSITY * len(recent))):
        # `since_new` being zero means the last step found somewhere new --
        # the loop is already breaking, so this has nothing left to say.
        # Eleven of the last twelve beats can still be a tight cycle at that
        # moment, and the density test alone would go on calling it circling
        # while he was walking out of it. A signal that argues against the
        # move it wanted is worse than no signal.
        circling = set(recent)
    # Which rooms, in this character's OWN experience, they walked into and had
    # to walk straight back out of.
    #
    # `been_there` alone does not stop anyone re-entering a dead end -- and it
    # did not: observed live, a character was told been_there/times_entered=9
    # for a one-exit chamber and walked back into it six times, because knowing
    # you have been somewhere is not knowing it led nowhere. That is the
    # difference between visit history and route knowledge, and only the second
    # is any use for navigating.
    #
    # Derived purely from their own route: entered, and the next room was the
    # one they had just come from. No oracle knowledge of the maze -- this is
    # exactly what a person remembers about a wrong turn.
    returns, onward, dwelt = {}, {}, set()
    for i, rid in enumerate(route):
        if i + 1 < len(route) and route[i + 1] == rid:
            # Stayed put here for a beat. A place someone CHOSE to remain in
            # was a destination, not a wrong turn -- see below.
            dwelt.add(rid)
        if i == 0 or i + 1 >= len(route):
            continue
        if route[i + 1] == route[i - 1]:
            returns[rid] = returns.get(rid, 0) + 1
        elif route[i + 1] != rid:
            onward[rid] = onward.get(rid, 0) + 1

    # Exits seen from rooms actually stood in, recorded at commit. The FRONTIER
    # is a door seen but never walked through -- and it is the only thing that
    # separates "that way is exhausted" from "that way is where I came from".
    #
    # A first attempt used only walked adjacency, which collapses the whole
    # visited region into one blob: every exit came back "nothing new that way",
    # including the way out. A signal that fires on everything is worse than
    # none, because it argues against the correct move as loudly as the wrong
    # one.
    #
    # The single-room dead end is the easy case, caught by no_route_onward. What
    # actually traps is a dead-end CORRIDOR -- observed live, a character
    # bounced between two pass-through rooms for ten beats, since each was a
    # legitimate onward move and the exhausted thing was the whole branch.
    known_exits = {
        str(k): [str(x) for x in v]
        for k, v in (known_exits or {}).items() if isinstance(v, list)
    }
    # The character's own knowledge, three readings of it. Adjacency merges
    # the legacy known_exits ledger (directed, as recorded from rooms stood
    # in) with the durable place_graph's edges (undirected -- a doorway works
    # both ways -- minus the disproven, which present perception has shown
    # absent; a disproven edge also retracts any stale legacy copy).
    # Walkedness comes from the graph rather than the recency window, because
    # a room walked seventy beats ago has rolled off `visited_rooms` and was
    # reading as untried -- forgetting must never make stale ground look
    # promising.
    adj = {k: set(v) for k, v in known_exits.items()}
    graph = place_graph if isinstance(place_graph, dict) else {}
    g_nodes = graph.get("nodes")
    g_nodes = g_nodes if isinstance(g_nodes, dict) else {}
    g_edges = graph.get("edges")
    g_edges = g_edges if isinstance(g_edges, dict) else {}
    disproven = []
    for a, side in g_edges.items():
        if not isinstance(side, dict):
            continue
        for b, rec in side.items():
            if isinstance(rec, dict) and rec.get("disproven"):
                disproven.append((str(a), str(b)))
                continue
            adj.setdefault(str(a), set()).add(str(b))
            adj.setdefault(str(b), set()).add(str(a))
    for a, b in disproven:
        adj.get(a, set()).discard(b)
        adj.get(b, set()).discard(a)
    walked = set(route) | set(known_exits) | {
        str(r) for r, n in g_nodes.items()
        if isinstance(n, dict) and n.get("basis") == "walked"}
    # Doorways actually TAKEN, for routing toward a named destination.
    taken_adj = _taken_adjacency(g_edges)
    for a, b in disproven:
        taken_adj.get(a, set()).discard(b)
        taken_adj.get(b, set()).discard(a)
    dest_rid, dest_name = None, ""
    if isinstance(destination, dict) and destination.get("rid"):
        dest_rid = str(destination["rid"])
        dest_name = str(destination.get("name") or dest_rid)
        if dest_rid == str(here_rid or ""):
            # Standing in it. Nothing to route.
            dest_rid = None

    # Chambers he has SEEN into and found closed. An untrodden cul-de-sac is
    # a door not taken, but it is not a route, and counting it as frontier
    # kept a whole branch reading as live forever: observed live, a character
    # spent twenty-four beats in a six-room lobe whose only way out was back
    # the way he came, and it never registered as exhausted because one
    # visibly-closed chamber in it was still untrodden. He could see it was
    # closed from the doorway. That was simply never written down.
    dead_ends = {str(r) for r in (known_dead_ends or []) if r} | {
        str(r) for r, n in g_nodes.items()
        if isinstance(n, dict) and n.get("closed")}
    # THE GLOBAL FACT the per-branch markers cannot state: does ANY doorway
    # anywhere in his own map still lead to ground he has not walked?
    # `no_new_ground_that_way` is a comparative claim -- "this branch is
    # exhausted" is only information while some other branch is not -- and
    # when the whole map is walked it degrades into the same discouragement
    # on every exit, everywhere, forever. Measured live (Orrin, shrine-maze,
    # turn 228): 49 chambers all walked, a 0.95 belief in his own state that
    # "there is no unexplored ground left in this maze", and both exits of
    # his room reading "spent -- every door you have seen down that way is
    # one you have taken" with beats_since_new_ground at 26 and climbing.
    # Every direction read as failure, nothing said the map was COMPLETE, and
    # a mind in failure reaches for the thing that would fix it: his beliefs
    # from turns 215-219 invented "unexplored eastern corridor" out of a
    # sightline that "bends out of sight", and his goals chased it. The
    # payload made a finished maze illegible as anything but a maze where
    # every choice is wrong.
    frontier_anywhere = any(
        n not in walked and n not in dead_ends
        for side in adj.values() for n in side)
    # A door in THIS room he has never taken counts as frontier too: on a
    # first beat somewhere new the commit-recorded adjacency has not caught
    # up yet, and completeness must never be claimed across an untried door.
    untried_here = False
    for edges in digest.values():
        if not isinstance(edges, list):
            continue
        for e in edges:
            if not isinstance(e, dict):
                continue
            _rid = name_to_id.get(str(e.get("room") or ""))
            if not (_rid and (_rid in counts or _rid in walked)):
                untried_here = True
    # A POSITIVE claim, never an absence: it needs recorded adjacency to
    # stand on (a bare route window says nothing about doors), and one
    # untried door anywhere defeats it. Everything below that softens a
    # discouraging signal is gated on this, not on frontier_anywhere alone,
    # because "I cannot tell whether new ground exists" must never read as
    # "none exists".
    fully_known = bool(adj) and bool(walked) \
        and not frontier_anywhere and not untried_here
    out = {}
    all_marked = []
    for bucket, edges in digest.items():
        if not isinstance(edges, list):
            out[bucket] = edges
            continue
        marked = []
        for edge in edges:
            if not isinstance(edge, dict):
                marked.append((edge, None, None))
                continue
            rid = name_to_id.get(str(edge.get("room") or ""))
            entry = dict(edge)
            hops, toward = None, None
            if rid and here_rid and dest_rid:
                toward = _toward_hops(rid, str(here_rid), taken_adj, dest_rid)
            if rid in seen_onward:
                # Absent means "cannot tell from here" -- never "none".
                entry["onward_exits_visible"] = seen_onward[rid]
                if rid in seen_bearings:
                    entry["onward_bearings"] = seen_bearings[rid]
                if seen_onward[rid] == 0:
                    entry["visibly_no_way_through"] = True
            if rid and worked.get(rid):
                # The counterweight. Every other marker here says where they
                # have BEEN; this is the only one that says something WORKED,
                # and without it a proven route reads as merely old.
                entry["worked_before"] = worked[rid]
            if rid and (rid in counts or rid in walked):
                # Been-there is a LIFETIME fact read from the durable graph,
                # not the recency window: a room walked seventy beats ago has
                # rolled off `visited_rooms`, and reading it as `untried`
                # would send the character back over old ground as though it
                # were discovery. The window-scoped counters below are simply
                # absent for it -- absent means "cannot tell", never "none".
                entry["been_there"] = True
                if rid in counts:
                    entry["times_entered"] = counts[rid]
                if recent_counts.get(rid, 0) > 1:
                    # The one number that separates a thoroughfare from a
                    # loop. Only emitted above 1, because "you were there
                    # once recently" is just where you came from.
                    entry["entered_recently"] = recent_counts[rid]
                if rid in circling:
                    entry["circling_here"] = True
                if returns.get(rid):
                    # The FACT: they went in and came straight back out, N
                    # times. Always reported, because it is simply what
                    # happened.
                    entry["turned_back_here"] = returns[rid]
                    # The INFERENCE, named for what it actually is: no route
                    # ONWARD. Not "leads nowhere" -- a tavern is a room you
                    # enter and leave by the same door, and a marker calling it
                    # a dead end tells a character to avoid the place they were
                    # going. This says only that it is not a way THROUGH: a
                    # fact about doorways, saying nothing about whether it is
                    # worth being in.
                    #
                    # Held to two reversals with no onward move, and never
                    # applied to somewhere they chose to REMAIN: dwelling is
                    # what going somewhere on purpose looks like, as against
                    # passing through and finding a wall.
                    if (returns[rid] >= 2 and not onward.get(rid)
                            and rid not in dwelt):
                        entry["no_route_onward"] = True
                if here_rid:
                    hops = _frontier_hops(rid, here_rid, adj, walked,
                                          dead_ends)
                    # `spent` only while it discriminates: with no frontier
                    # left ANYWHERE the marker is true of every exit at once,
                    # which brands familiarity as failure -- for a maze
                    # finished, or simply for a character who lives here and
                    # has walked their whole home. The completeness fact
                    # rides `ground_fully_known` below instead.
                    if hops is None and not fully_known:
                        entry["no_new_ground_that_way"] = True
                for back, seen in enumerate(reversed(route), 1):
                    if seen == rid:
                        entry["last_seen_beats_ago"] = back
                        break
            else:
                entry["been_there"] = False
                # POSITIVELY marked, because the frontier was the one thing
                # here described only by an absence. Measured at the moment a
                # character failed to take it: the door he should have used
                # carried three keys and 64 characters, `been_there: false`
                # among them, while the door he kept taking instead carried
                # eight keys and 179. Every good thing about the right answer
                # was the lack of something, so it was the lightest item in
                # the payload -- and it was chosen against, nineteen beats
                # running. Salience follows weight, and ours pointed the
                # wrong way.
                entry["untried"] = True
            entry = _verdict(entry, frontier_hops=hops)
            # The destination reading rides the verdict STRING and the
            # ordering only, exactly as the frontier distance does -- a key
            # of its own would put weight back on the entries that should
            # carry the least, which is the failure _annotate_known_exits
            # exists to not repeat. The raw markers stay underneath as the
            # evidence a character needs to disagree with the reading.
            if toward is not None and isinstance(entry, dict) \
                    and entry.get("verdict"):
                if toward == 1:
                    entry["verdict"] += (
                        f"; through here is {dest_name} itself -- the room "
                        "your goal names")
                else:
                    entry["verdict"] += (
                        f"; your own remembered ground runs from here to "
                        f"{dest_name}, about {toward} rooms along this way")
            marked.append((entry, hops, toward))
        # Untried first, and among `known` exits the one with NEARER new
        # ground first. Position IS salience and it costs nothing; leaving
        # the order to however the digest happened to build it was spending
        # that for no reason. Stable within each group, so a bucket's own
        # ordering still shows through. The distance rides the sort key and
        # the verdict string only -- adding it as a per-exit key would put
        # weight back on the entries that should carry the least.
        def _rank(trio):
            entry, hops, toward = trio
            appeal = _appeal(entry)
            near_dest = 10 ** 6
            if isinstance(entry, dict) and isinstance(toward, int):
                # An exit on the remembered way to the room his goals name
                # must not be buried under its own discouragement:
                # spent/circling/closed all answer "anything NEW that way?",
                # which is not the question a named destination asks.
                # Measured in A12 run 4: every step of his optimal route
                # read `known`/`spent` BECAUSE he had walked it, which is
                # exactly why it was the route. Clamped to `known`, never
                # lifted above untried/proven -- goal against curiosity
                # stays the character's call, as the appeal order promises.
                appeal = min(appeal, _APPEAL_ORDER.index("known"))
                near_dest = toward
            near = 10 ** 6
            if isinstance(entry, dict) and isinstance(hops, int) \
                    and hops >= 1 \
                    and str(entry.get("verdict") or "").startswith("known"):
                near = hops
            return (appeal, near_dest, near)
        out[bucket] = sorted(marked, key=_rank)
        all_marked.extend(out[bucket])

    # THE ONLY WAY ON. When every doorway here argues against itself and
    # exactly one of them still leads to unexplored ground, say so outright.
    #
    # This is where the loop detector turned against the character. Measured
    # in A11: standing in a pocket, one exit `spent` and one `circling`, and
    # the `circling` one was the sole route to the only frontier left in the
    # maze. Both read as "do not go here", so he paced -- and every beat of
    # pacing made the circling verdict truer. A signal that fires because the
    # character is stuck, and then prevents them leaving, is worse than no
    # signal.
    #
    # Deterministic and narrow on purpose: it fires only when nothing
    # encouraging remains AND the choice is unambiguous. With two live
    # branches the character is choosing, not trapped, and choosing is theirs.
    live = [trio for trio in all_marked
            if isinstance(trio[1], int) and trio[1] >= 0]
    if live and len(live) == 1 and all(
            _appeal(e) >= _APPEAL_ORDER.index("circling")
            for e, _, _ in all_marked if isinstance(e, dict)):
        entry, hops, _toward = live[0]
        entry["only_way_onward"] = True
        entry["verdict"] = (
            str(entry.get("verdict") or "") +
            "; even so it is the ONLY way you know of that still leads to "
            "ground you have not walked -- going back through here is not "
            "circling, it is the way out")
    for bucket in list(out):
        if isinstance(out[bucket], list):
            out[bucket] = [trio[0] for trio in out[bucket]]
    # The completeness fact, stated once and positively. Every marker above
    # answers "where have I not been", and when the answer is NOWHERE the
    # absence of that statement was the bug: forty-nine local "nothing new
    # that way"s never sum, in a model's reading, to "there is nothing new
    # ANYWHERE" -- they sum to "I am in the wrong part of the maze". Only
    # claimed off his own recorded adjacency (`adj` non-empty), never off a
    # bare route window, and never across an untried door in this room.
    # Rooms seen-closed but never entered do NOT break completeness: they
    # carry `unentered` where they stand, and what is IN them is a different
    # question from where anything leads.
    if fully_known:
        out["ground_fully_known"] = True
    # Whole-route, not per-exit: how long since anywhere was new. The per-exit
    # markers say something about each doorway; this says something about the
    # walk. Only reported once it is worth noticing, since a couple of beats
    # retracing your steps is ordinary movement, not being lost -- and never
    # on a POSITIVELY complete map: there the counter can never reset again,
    # so it would brand every future beat as failure, including every step of
    # a proven route walked on purpose.
    if since_new >= LOOP_WINDOW // 2 and not fully_known:
        out["beats_since_new_ground"] = since_new
    return out


def _run_end_note(end_rid, nodes, closed_rids):
    """What the character already knows about the chamber a run finishes in.

    The exits digest carries a verdict for every doorway; the run offers
    carried nothing but a room NAME, so the same chamber could read as
    discouraging when walked to and as a bare destination when run to. The
    decision is made where the offer is, so what the character knows has to
    be stated there too.

    Split exactly as `_verdict` splits `closed` from `unentered`, and for the
    same measured reason: the shrine is a cul-de-sac. A run that finishes in
    a dead end the character has SEARCHED buys nothing, but a run finishing
    in one they have never been inside may be the whole point of the maze --
    A11 run 3 lost the shrine to precisely that conflation, the character
    reading "no other way out" off the thing he was sent to reach and
    turning around at its doorway. So `visits` decides the wording, and a
    never-entered cul-de-sac is never discouraged.

    Returns "" when there is nothing the character knows to say, which keeps
    the key absent from the offer rather than present and empty -- an
    encouraged run stays as short to read as it was before.
    """
    node = nodes.get(end_rid)
    node = node if isinstance(node, dict) else {}
    if not (node.get("closed") or end_rid in closed_rids):
        return ""
    if int(node.get("visits") or 0) > 0:
        return ("a dead end you have already been inside -- its only way out "
                "is the doorway you would go in by")
    return ("no other way out of it, but you have never been inside -- what "
            "is IN a room is a different question from what it leads to")


def sprint_offers(scene, room_id, stored_state, destination=None):
    """The RUNNING offers actually worth handing a deciding mind.

    Two gates on the raw `spatial.sprint_reach`, each preventing an observed
    failure:

    * Knowledge. Decision-bounded reach follows a corridor round its bends,
      and objectively that is the Director's resolve ceiling -- but handed
      raw to a character it would report the winding geometry of passages
      they have never walked, unearned map smuggled in as an affordance
      (the exact structured-representation leak the perception layer exists
      to prevent). The gate is the engine's own remembered-ground idiom
      (commit.record_spatial_experience): durable place-graph nodes plus the
      visited-rooms recency window. A body's offered reach GROWS as it
      learns the ground, which is also what is true of real runners.
    * Worth. A 1-room "run" is a step with a different verb, and listing it
      taught the model that runs are trivial: measured live (A11), 72 of 96
      passages offered exactly one room, and the character read offer after
      offer as "only 1 room, walking is fine" -- then never ran at all. An
      adjacent visible room needs no affordance entry to be sprinted into;
      only reach a walk cannot match is worth an entry.

    An omitted passage is still runnable -- open-endedly, "run until
    something stops me" -- and resolves against the Director's objective
    ceiling. The prompt says so.

    The offer names WHERE THE RUN ENDS, never the rooms along the way.
    Structural, not cosmetic: the first shape listed `path`, and the
    smallest-plausible directive did to it exactly what a minimizer does to
    a divisible quantity -- measured in A12, the character read a 3-room
    reach, reasoned "the smallest plausible next behavior might be just the
    first step", took the first room off the path list, and declared a
    1-room "run". Prompt text arguing that the whole reach is one behaviour
    was read and lost. So the offer no longer presents anything to split:
    `run_ends_at` names the terminal room, and declaring less than the
    reach now requires inventing an intermediate stop the offer never
    mentioned. Nothing epistemic is lost -- every room on a gated path was
    already the character's, by sight or by feet; the Director's objective
    reach keeps the full path for resolution and commit.
    """
    st = stored_state if isinstance(stored_state, dict) else {}
    graph = st.get("place_graph") or {}
    nodes = graph.get("nodes") if isinstance(graph, dict) else None
    nodes = nodes if isinstance(nodes, dict) else {}
    remembered = set(nodes) | {
        r for r in (st.get("visited_rooms") or []) if isinstance(r, str)}
    closed_rids = {r for r in (st.get("known_dead_ends") or [])
                   if isinstance(r, str)}
    rooms = (scene or {}).get("rooms") or {}
    # What the run does to the distance he still has to cover. Measured in
    # A13 run 4: the exits carried "your remembered ground runs from here to
    # Chamber 0603, about 26 rooms along this way" on the correct one-room
    # step, and the run offers carried nothing at all -- so the choice he
    # actually faced was a 1-room step that mentioned his destination against
    # a 3-room `full_reach` run that did not. For a character whose sheet
    # says running the proved line is the finish, that is not close. He took
    # the run; it ended four rooms further out. Every affordance was locally
    # correct and none of them talked to each other.
    dest_rid = dest_name = None
    here_hops = None
    taken_adj = {}
    if isinstance(destination, dict) and destination.get("rid"):
        dest_rid = str(destination["rid"])
        dest_name = str(destination.get("name") or dest_rid)
        taken_adj = _taken_adjacency(
            graph.get("edges") if isinstance(graph, dict) else {})
        here_hops = _hops_to(str(room_id), dest_rid, taken_adj)
    out = []
    for offer in sprint_reach(scene, room_id, known_rooms=remembered):
        if int(offer.get("rooms") or 0) < 2:
            continue
        end = str((offer.get("path") or [""])[-1])
        entry = {
            "bearing": offer.get("bearing"),
            "run_ends_at": str((rooms.get(end) or {}).get("name") or end),
            "rooms": offer.get("rooms"),
            "stops": offer.get("stops"),
        }
        notes = []
        note = _run_end_note(end, nodes, closed_rids)
        if note:
            notes.append(note)
        if here_hops is not None:
            end_hops = _hops_to(end, dest_rid, taken_adj)
            if end_hops is not None and end_hops != here_hops:
                gap = end_hops - here_hops
                notes.append(
                    f"it ends {gap} rooms further from {dest_name} than you "
                    f"stand now" if gap > 0 else
                    f"it ends {-gap} rooms closer to {dest_name}")
        if notes:
            entry["ends_in"] = "; ".join(notes)
        out.append(entry)
    return out


def character_step(ctx, cid, nonce):
    chat = ctx.chat
    row = next((c for c in ctx.cast if c["id"] == cid), None)
    if row is None:
        # Cast member was dismissed between plan construction and execution;
        # skip this character step gracefully rather than crashing with
        # StopIteration.
        return None
    sh, active, stance = sheet_state(row)
    sc = get_scene(chat["id"], chat)

    # Consciousness gate (choke point): an unconscious/asleep/sedated mind does
    # not deliberate or act. The planner and both loops already drop non-awake
    # reactors; this guard protects rerun/resume paths that hydrate a stale plan
    # and makes the invariant hold no matter who calls character_step. No LLM
    # call, no manifest (which perception would otherwise deliver as tells).
    if awareness_of(chat["id"], character_name(sh)) in NON_AWAKE_GATED:
        return {"sequence": [], "speech": None, "action": None, "actions": [],
                "manifest": {}, "mind_model_updates": [],
                "_awareness_gated": True}

    interaction_views = ctx.get("interaction_views", {}) or {}
    reaction_views = ctx.get("reaction_views", {}) or {}
    view = reaction_views.get(cid) or interaction_views.get(cid)
    if view is None:
        view = ((ctx.get("perception_act", {}).get("views") or {}).get(str(cid)))
    base_observations = (
        (ctx.get("perception_act", {}).get("observations") or {}).get(str(cid))
        or []
    )
    base_view = ((ctx.get("perception_act", {}).get("views") or {}).get(str(cid)))
    # Interaction/reaction micro-views are already filtered for this mind but
    # do not pass through the full perception stage. Never reuse stale base
    # metadata for a changed view; project only the permitted text itself.
    if view and view != base_view:
        observations = [{
            "observation_id": f"current:{cid}:micro",
            "perceiver_id": str(cid),
            "source_atom_id": "current",
            "channel": "mixed",
            "fidelity": "rendered",
            "observed": {"text": str(view)},
            "intensity": 0.5,
            "suddenness": 0.1,
            "ambiguity": 0.3,
            "directed_at_self": False,
        }]
    else:
        observations = base_observations

    # Resolved before the memory context, not after: where the character is
    # standing is a retrieval cue, and the recall is built here.
    char_room = character_room(sc, sh)
    memory_context = build_character_memory_context(
        chat_id=chat.id, char_id=cid,
        current_turn_idx=ctx.turn.idx,
        current_view=view or "",
        active_state=active,
        here=(sc.get("rooms") or {}).get(char_room, {}).get("name") or char_room,
        # Rooms currently in sight are cues too. Recalling what happened where
        # you STAND tells you where you are; recalling it about a room you can
        # SEE tells you whether to go there -- which is the decision actually
        # being made.
        in_sight=[
            str(item.get("room_name") or item.get("room_id"))
            for item in (visible_adjacent_rooms(sc, char_room) or [])
            if isinstance(item, dict)
        ] if char_room else None,
    )
    known_tags, excl_titles = _char_known_tags(sh)
    knowledge = knowledge_for_character(_books(ctx), char_room, known_tags, excl_titles)
    stored_state = json.loads(row["cstate"] or "{}")

    _interp = _dict(ctx.director_interpret)
    _flow = _dict(_interp.get("flow"))
    _tom = _list(_flow.get("tom_triggers"))

    relationships = relationships_for_payload(chat.id, cid)
    _sim_clock = wget(
        chat.id, "simulation_clock",
        {"elapsed_seconds": 0.0, "display": "now"},
    )
    mind_models = mind_models_for_payload(
        stored_state.get("mind_models") or {}, ctx.turn.idx,
        elapsed_seconds=(_sim_clock or {}).get("elapsed_seconds"),
    )
    # How much of this mind its own body currently has. Own interoceptive state
    # only -- another character's pain is never an input to this character's
    # cognition (see AGENTS.md's own-body isolation rule).
    absorption = cognitive_absorption(
        (active or {}).get("hedonic"), (active or {}).get("stress"))
    # The stable sheet is SELECTED at commit (where the reconciled beliefs and
    # the settled end-of-beat body state both exist) and simply read here, so
    # what the character holds in mind this turn is what they came out of the
    # last beat holding.
    active_hypotheses = list(stored_state.get("active_hypotheses") or [])[
        :sheet_capacity(absorption)]
    frame_id = ctx.turn.frame_id
    if frame_id is not None:
        # A frame's own state-swap already starts blank the first time
        # it's visited, but nonexistent_cast is the deterministic
        # backstop regardless of how relationship/mind-model data got
        # there -- e.g. a character not yet born must never appear known
        # to a native here even if something upstream got it wrong.
        #
        # all_cast_name_to_id (NOT ctx.cast, which is active-only) --
        # a DORMANT cast member must be checked against nonexistent_cast
        # exactly like an active one. Building this from ctx.cast alone
        # made a dormant not-yet-existing character fall through to the
        # -1 fallback below, which reads as "recognized" (-1 is never in
        # a frame's nonexistent_cast list), silently defeating the mask
        # for exactly the case it exists to catch. A name that isn't ANY
        # cast member at all (a background presence, an unsheeted NPC)
        # correctly keeps that same -1/"recognized" fallback -- this
        # mask only ever applies to declared cast members.
        name_to_id = all_cast_name_to_id(chat.id)
        relationships = {
            name: rel for name, rel in relationships.items()
            if is_recognized_in_frame(name_to_id.get(name, -1), frame_id)
        }
        mind_models = {
            name: mm for name, mm in mind_models.items()
            if is_recognized_in_frame(name_to_id.get(name, -1), frame_id)
        }

    _interior = stored_state.get("interior") or {}
    _psych = character_psychology(sh)
    # Tier-1: show the EFFECTIVE (possibly rupture-shifted) drive, read-only.
    _psych["drive"] = effective_drive(_psych, _interior)
    # A drive rupture is proposable ONLY inside its open window (see commit's
    # detect_drive_rupture) -- the base contract never documents drive_shift, so
    # the model cannot flip-flop it; it appears here only when the engine opened
    # the window this beat or in the two beats after.
    _rupture = _interior.get("drive_rupture")
    _window_open = bool(isinstance(_rupture, dict)
                        and ctx.turn.idx <= int(_rupture.get("window_expires") or -1))
    # How long the window has been open. Once it has stayed open
    # RUPTURE_FORCE_AFTER turns, the optional "you MAY shift" becomes a FORCED
    # resolution (below) -- the fix for a rupture that the engine keeps holding
    # open while the model quietly declines it every beat (the 23-turn limbo).
    _rupture_turns_open = (
        ctx.turn.idx - int(_rupture.get("opened_turn") or _rupture.get("turn") or ctx.turn.idx)
        if isinstance(_rupture, dict) else 0)
    _rupture_forced = _window_open and _rupture_turns_open >= RUPTURE_FORCE_AFTER
    # Crisis: strain at visible-breaking level. Even before any drive_shift,
    # the flag (plus the CRISIS prompt block below) forces the manifest/tells
    # to show the character cracking instead of playing untouched calm.
    try:
        _strain = float(_interior.get("drive_strain") or 0.0)
    except (TypeError, ValueError):
        _strain = 0.0
    _crisis = _strain >= CRISIS_STRAIN_MIN
    # Recent-tell ledger (written by commit): physical cues already shown,
    # fed back so the model does not reuse the same gesture every beat.
    _recent_tells = [str(t) for t in (stored_state.get("recent_tells") or [])
                     if str(t).strip()]
    # Tell-ground ledger (F6, written by commit): each recent cue with the
    # private ground it betrayed, fed back so a planted tell can be PAID OFF
    # in a later beat -- the ground surfacing in behavior or speech -- instead
    # of dangling forever as fake significance. Private context only; the
    # grounds never reach observers.
    _tell_grounds = [
        {"cue": str(g.get("cue") or ""), "because": str(g.get("because") or "")}
        for g in (stored_state.get("tell_grounds") or [])
        if isinstance(g, dict) and str(g.get("cue") or "").strip()
    ]
    # Resolved once and shared: the exits and the run offers must be judged
    # against the SAME destination, or the payload argues with itself.
    _goal_destination = _destination_from_goals(
        stored_state, stored_state.get("place_graph") or {},
        here_rid=char_room, now_turn=getattr(ctx, "turn_idx", None))
    _self = {
        "entity_id": f"character:{cid}",
        "name": character_name(sh),
        "public_history": character_public_history(sh),
        "psychology": _psych,
        "stance": stance,
        # How readily this mind leaves a known-good way for an untried one.
        # Explicit because the balance was previously implicit -- an artefact of
        # which navigational markers existed, not an authored trait.
        "curiosity": character_curiosity(sh),
        "active_state": active,
        "voice": character_voice(sh),
        "senses": senses_as_text(character_senses(sh)),
        "sense_profile": character_senses(sh),
        "interoception": character_interoception(sh),
        "abilities": character_abilities(sh),
        "attire": sc.get("attire", {}).get(character_name(sh)),
        "recent_self_lines": _recent_self_lines(
            chat.id, character_name(sh), ctx.turn.idx,
            frame_id=ctx.turn.frame_id),
        # Tier-2 goal hierarchy: the character's AUTHORED standing intentions
        # (its defining goals, always present so it acts proactively) merged
        # with EMERGENT intentions formed at runtime via intent_ops. An emergent
        # intention that restates an authored one wins (it carries live
        # progress/status). Read-only context for deriving this beat's wants.
        "intentions": _annotate_fading(
            _merge_standing_intentions(
                character_standing_intentions(sh),
                _interior.get("intentions") or []),
            ctx.turn.idx),
        # PROJECTS (Tier 1.5): at most two standing commitments -- what this
        # character is ABOUT right now. The live ledger once commit has
        # seeded it; the authored card list only on beats before the first
        # commit, and never once any live or former project exists, so a
        # project given up with a stated reason does not read as held again.
        "projects": _annotate_project_drift(
            (_interior.get("projects")
             if (_interior.get("projects")
                 or _interior.get("former_projects"))
             else character_projects(sh)) or [],
            ctx.turn.idx),
        # What was given up or finished, with the stated reason --
        # continuity, like former_drives, not obligation.
        "former_projects": _interior.get("former_projects") or [],
        # Former drives (scars) give continuity to a character who has changed.
        "former_drives": _interior.get("former_drives") or [],
        "learned_beliefs": _interior.get("beliefs") or [],
        "learned_associations": _interior.get("associations") or [],
    }
    _body_state = vitals_of(sc, character_name(sh))
    if _body_state:
        # Own-body interoception only. Other characters' vitals never enter
        # this payload; their outward signs must cross perception normally.
        _self["body_state"] = _body_state
    if _window_open:
        _self["rupture"] = {"why": _rupture.get("why"), "direction": _rupture.get("direction"),
                            "forced": _rupture_forced}
    if _crisis:
        _self["crisis"] = True
    if _recent_tells:
        _self["recent_tells"] = _recent_tells
    if _tell_grounds:
        _self["tell_grounds"] = _tell_grounds
    # The journey already underway, as a stated status -- see _en_route.
    # Same destination the exit verdicts and run offers are judged against.
    _underway = _en_route(stored_state, char_room, _goal_destination)
    if _underway:
        _self["en_route"] = _underway
    # A boundary passed at last commit (arrival where a project points, a
    # task closing, the scene or frame changing -- affect.project_boundary).
    # Shown for the one beat after it fired: the moment to re-ask what each
    # held project means for what happens next. An invitation, never a
    # mechanism -- no op is ever applied by the engine.
    _preview = _interior.get("project_review")
    if isinstance(_preview, dict) and _self.get("projects"):
        try:
            _fresh = ctx.turn.idx <= int(_preview.get("turn")) + 1
        except (TypeError, ValueError):
            _fresh = False
        if _fresh:
            _self["project_review"] = {
                "why": str(_preview.get("why") or "")}
    payload = {
        "self": _self,
        "perception": {
            "view": view or "You register nothing new this beat.",
            "observations": observations,
            # This character's OWN egocentric exits (ahead/behind/left/right of
            # the way THEY face) -- grounding for their movement/positioning
            # choices, not a script to narrate. Empty when they have no
            # established orientation.
            "spatial_frame": _annotate_known_exits(
                spatial_digest(sc, character_name(sh)), sc,
                stored_state.get("visited_rooms") or [],
                known_exits=stored_state.get("known_exits") or {},
                here_rid=char_room,
                routes_that_worked=stored_state.get("routes_that_worked") or {},
                known_dead_ends=stored_state.get("known_dead_ends") or [],
                place_graph=stored_state.get("place_graph") or {},
                # The room his own goal text names, if he owns a node for
                # it -- see _destination_from_goals for the double gate.
                destination=_goal_destination),
            # Where they are, named. The digest lists what leads OUT of a room
            # without ever naming the room itself, so a character had to
            # re-derive their own location from the view's prose every beat.
            "current_room": (sc.get("rooms") or {}).get(
                character_room(sc, sh), {}).get("name") or "",
            # Looking straight down each passage: whether it ends, opens out or
            # bends, and roughly how far off. Coarse on purpose -- "some way
            # north the passage comes to an end" is the percept, not a room
            # count -- and it stops at corners, so it is sight rather than a
            # map.
            "corridor_sight": corridor_sightlines(sc, char_room),
            # How far a RUN gets down each passage, and what stops it.
            # Knowledge-gated and pruned to the offers worth having -- see
            # sprint_offers. An offer, not an instruction: a body that can
            # run is not a body that must.
            # The destination rides here too, so a run that carries him AWAY
            # from where he is going says so. Without it the exits named his
            # goal and the runs did not, and the loudest option was the one
            # with the least context.
            "sprint_reach": sprint_offers(sc, char_room, stored_state,
                                          destination=_goal_destination),
        },
        "memory": memory_context,
        "relationships": relationships,
        "mind_models": mind_models,
        # The stable hypothesis sheet: the few open questions this mind is
        # actively holding, each keyed "i_suspect" so the field itself carries
        # the epistemic status. mind_models above is the full ledger; this is
        # what is actually in mind, and its size shrinks with absorption.
        "active_hypotheses": active_hypotheses,
        "known_pronouns": _known_pronouns(
            ctx.cast, persona_of(chat),
            set(relationships) | set(mind_models),
            exclude=[character_name(sh)]),
        "private_knowledge": private_knowledge_for(chat, character_name(sh), ctx.turn.frame_id),
        "world_knowledge": knowledge,
        "decision": {
            "deep_tom_requested": cid in _tom,
            "dialogue_mode": bool(_flow.get("dialogue_mode", False)),
            "speech_budget": dialogue_budget(chat, ctx.turn, cid, nonce),
        },
        "simulation_clock": _sim_clock,
        "variant_seed": nonce,
    }

    # Authorial offers (P3): propositions the PLAYER authored about THIS
    # character's interior/behavior, rerouted here instead of being enacted as
    # truth (see director._route_authorial_npc_beat). The character decides
    # in-character how (or whether) each lands -- its agency is preserved.
    _offers = [o.get("proposition") for o in
               ((ctx.get("director_interpret") or {}).get("authorial_offers") or [])
               if o.get("subject_id") == cid and o.get("proposition")]
    if _offers:
        payload["decision"]["authorial_offers"] = _offers

    role = {"bg": "character_bg", "mid": "character_mid",
            "major": "character_major"}.get(character_tier(sh), "character_mid")

    _cprompt = get_prompt("character").replace("{name}", character_name(sh))
    if _window_open:
        # The base contract never documents drive_shift; the instruction to emit
        # one exists ONLY inside an engine-opened rupture window, so a drive can
        # never flip-flop turn to turn.
        _cprompt += (
            "\n\nDRIVE RUPTURE (window OPEN this beat): a shattering, drive-level "
            "event has cracked what you live for (see self.rupture.why). This event "
            "has ALREADY changed you -- the only question is how the change surfaces. "
            "Denial is a phase, not a stable end: even if you cling to the old drive, "
            "show the crack in your behavior NOW (a ritual performed wrong, a "
            "signature line that dies mid-sentence, a rule reached for and found "
            "hollow). And if your core is genuinely remade, emit drive_shift "
            "{essence, expression, taboo, because}: essence = the new deepest thing "
            "you live for, expression = how it shows, taboo = what you now cannot "
            "do; `because` must name the rupture event. WORKED EXAMPLE: a magistrate "
            "whose drive was 'the law is the only shelter' watches the court execute "
            "the clerk she vouched for. She emits drive_shift {\"essence\": "
            "\"protect the person in front of me, not the rule\", \"expression\": "
            "\"quietly bends procedure to shield people\", \"taboo\": \"never again "
            "hand someone over to process\", \"because\": \"the court executed the "
            "clerk I vouched for\"} -- and her sequence THIS beat already shows it: "
            "she pockets the arrest warrant instead of filing it. A shift is rare "
            "and irreversible -- do not shift for a survivable wound; but do not "
            "play untouched calm either. NEVER announce the change in dialogue; it "
            "shows only in what you do and come to want.")
        if _rupture_forced:
            _cprompt += (
                "\n\nRUPTURE -- FORCED RESOLUTION: this window has now stayed open "
                "several beats and you have kept deferring. Deferral is over. THIS "
                "beat you must LAND it, one way or the other, visibly on the page -- "
                "passive, untouched, wait-and-see calm is NOT an available option "
                "anymore; the strain has been on you far too long for that. Choose "
                "exactly one and enact it in your sequence this beat: (A) emit "
                "drive_shift {essence, expression, taboo, because} AND let your "
                "action/speech this beat already do the new thing -- not a promise "
                "to change, the change itself; or (B) if your core genuinely holds, "
                "stop merely enduring and REAFFIRM it in a concrete, costly act your "
                "pre-rupture self would recognize as doubling down -- a line said, a "
                "hand that acts, a refusal made real. Do not simply describe the "
                "strain again. Resolve it.")
    if _crisis:
        _cprompt += (
            "\n\nCRISIS (self.crisis -- your drive is under extreme strain): what "
            "you live for is under sustained assault and your composure is FAILING. "
            "Your manifest must show it: surface_demeanor cracks at the seams, and "
            "your tells escalate from subtle to VISIBLE (subtlety <= 0.4) -- a "
            "voice that breaks mid-sentence, a hand that will not stay still, a "
            "pause held one beat too long. You need not change what you live for, "
            "but you can no longer look untouched. Do NOT announce the strain in "
            "dialogue; it leaks through the body.")
    if _recent_tells:
        _cprompt += (
            "\n\nTELL VARIETY: self.recent_tells lists the physical cues you have "
            "already shown in recent beats. Do NOT reuse any of them -- or a "
            "near-identical variant -- as this beat's tell; find a DIFFERENT "
            "channel or gesture. A body under the same pressure finds new ways to "
            "betray it: vary the channel (face|eyes|voice|hands|posture|breath) "
            "and the cue itself.")
    if _tell_grounds:
        _cprompt += (
            "\n\nTELL PAYOFF: self.tell_grounds lists physical cues you have "
            "recently shown and, for each, the private ground it betrayed "
            "(`because`). These are debts the story has planted: when the scene "
            "gives a natural opening, let a ground SURFACE -- in what you do, "
            "choose, or say -- so an observant witness's banked suspicion can pay "
            "off. Never contradict a ground already shown, and never announce it "
            "as exposition; it emerges through behavior.")
    out = _agent_json(
        role,
        "character",
        _cprompt,
        payload,
        temperature=character_temperature(sh),
        sampler=character_sampler(sh) or None,
    )

    # Warning-only re-normalization; strict schema+semantic validation
    # (with repair/fallback/raise) already ran inside _agent_json -- a
    # mind_model_updates entry that fails CharacterOutput validation can
    # never reach the cap/commit path below.
    out, warnings = validate_llm_output("character", out)
    ctx.warnings.extend(warnings)

    out = _normalize_character_output(out)
    # F6: every manifest tell gets a stored ground (`because`) -- supplied by
    # the model or derived deterministically from the tell's own `betrays`
    # pointer -- so a planted anomaly always has a referent a later beat can
    # pay off. The ground stays private (perception delivers only the cue).
    if out.get("manifest"):
        out["manifest"], _tell_warnings = ground_tells(
            out.get("manifest"), out.get("active_state"))
        for _w in _tell_warnings:
            ctx.add_warning(f"character {character_name(sh)}: {_w}")
    out["mind_model_updates"] = cap_mind_model_updates(
        out.get("mind_model_updates") or [], absorption=absorption)
    norm_sequence(out)
    out["sequence"] = assign_event_ids(
        out.get("sequence"), f"turn:{ctx.turn.id}:character:{cid}")
    out["name"] = character_name(sh)
    out["char_id"] = cid
    return out
