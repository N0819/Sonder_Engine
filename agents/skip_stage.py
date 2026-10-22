"""The skip stage: the cast live through a stretch the writer passes over.

`docs/design/DESIGN_THE_CAST_ACROSS_A_SKIP.md`. When the players' input
passes over time -- the interpret stage's kept skip, `director_prose.
the_input_set_the_time`, at least `skip_itinerary.SKIP_LIVED_SECONDS` long --
this stage runs between `compile_world_context` and `perception_act`:

  a. **Ask.** Every registered cast member of the frame -- active (asleep
     ones included) and dormant with no bubble of its own -- is asked what it
     does for the duration, one call each, in parallel, on its own tier role.
     The payload is its ordinary character payload, built by the same builder
     a beat's `character_step` uses (`character_step(skip=...)`), plus a
     `skip` block, its offers under the stretch's end (`skip_block`); the
     card is `prompts/character_skip.txt`. The player is
     never asked: the account is theirs. A body the story holds sedated or
     unconscious is not asked either -- it can declare nothing, and its
     waking is the Director's.
  b. **Resolve.** The answer becomes absolute stretches over the span, its
     places resolved exactly, then by ONE decision-model request per mind,
     then as off-map labels (`world/skip_itinerary.py`). An answer that fails
     or says nothing is the DEFAULT DAY: silence is sleep.
  c. **Execute.** Inside the town's charter where one holds this body
     (`world/charter_skip.live_in_charter`), with what only this stage knows
     laid over its rows -- the weather, the holding check, a sleep's true
     start (`skip_itinerary.lay_over`, `carry_sleep`) -- and otherwise by the
     mind's own executor, in pure code (`skip_itinerary.live_through`): over
     the ways a body walks, never a frontier stub's join and never across
     water (`skip_itinerary.Ways`, the stub joins read from the registry by
     `frontier_stubs`), back onto the map by where it left it, and on with a
     vessel already under way (`skip_itinerary.journeys`), a stretch spent
     on its way being the ride itself (`skip_itinerary.rides`); both write
     one outcome rule and one reason vocabulary, and a stretch's `uses` are
     met by what the mind carries, what is within its reach where the
     stretch finds it, and what it can walk to and back for inside the
     stretch (`skip_itinerary.Reach`, its names resolved in `resolve_mind`)
     -- only a thing a body can carry is ever missing, a fixture, a store
     or a vessel being used where it stands -- and what is not fails it
     only where the decision model says it cannot be done without
     (`judge_what_was_missing`, one decision request per mind). A STRETCH
     FAILS ONLY ON POSITIVE EVIDENCE: a false failure becomes what the mind
     remembers and says, so no answer from the decision model ever invents
     one.
     Company with the other asked minds and the player is shared afterwards,
     per observer (`share_company`).
  d. **The far end.** Each mind ends where its last stretch left it -- a move
     of its own declaration. One whose day ends somewhere the world does not
     hold is AWAY there: dormant, with a typed whereabouts that keeps the room
     it left the map by (`left_from`; after a ride, where the journey brought
     it). One asleep at the
     far end is asleep from when that sleep began. The rest of the beat reads
     all of it as an ONSET PREVIEW (`FarEnd`, read through `story.scene`'s
     `get_scene` and `awareness_conditions` while a stage after this one
     runs), and the commit writes it (`persist/commit_skip.py`, and the base
     of `commit_scene_state.compose_beat_scene`).
  e. **The far-end payload.** Each asked mind's character call in this beat
     carries its own log as `the_stretch_just_passed` (`stretch_for_payload`).
  f. **What its own work changed.** Each mind's `done` rows on the map are
     told to the encoder once, and what it types for the things the mind
     had to hand is settled in time order across minds under the beat's own
     floors (`agents/skip_work.py`, `minds[*].worked`); the far end lays it
     before it places the minds (`FarEnd`).

The step's output is provisional like every stage's; its shape is fixed by
the build spec, because the out-of-band memory job reads `minds[*].log` and
`span` from the committed step.
"""

from __future__ import annotations

import contextlib
import copy
import json
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

from core.db import q, wget
from world import charter_skip
from world import skip_itinerary as itin

#: The plan step's key. A published name: an extension anchors on step keys.
STEP_KEY = "skip_lives"

#: The world key holding where each away cast member is: `{mind name:
#: {kind, label, since_s, turn_idx, char_id}}`, frame-scoped like every live
#: world record, so it rides the whole-`world` checkpoint, archive and branch
#: path with no code of its own (`docs/guides/DATABASE.md`). Read only for a
#: dormant mind; an active one stands where the scene puts it.
WHEREABOUTS_KEY = "whereabouts"

#: The one kind of whereabouts a skip writes: a place the mind named that the
#: world does not hold. Typed, so a later writer can say something else.
WHEREABOUTS_OFF_MAP = "off_map"

#: How many of its own log rows a mind's far-end call carries, nearest the
#: far end first kept: a week of routine is fifty rows, and the payload is
#: paid on every call of the beat. Named per the owner's rule on caps.
SKIP_PAYLOAD_ROWS = 48

#: How many minds are asked at once. Each ask is one model call and its
#: answer; the stage waits as long as the slowest. Named per the owner's
#: rule on caps.
SKIP_ASK_WORKERS = 8

#: The reasoning effort the skip question is asked at, overriding the mind's
#: role setting for this one call (`providers.chat_complete`'s
#: `reasoning_effort`). A day's schedule is a listing of what the mind does,
#: written from its own payload, not a deliberation, and a thinking model
#: bills its thinking as output. Measured 2026-10-22, the keeper's real skip
#: question on glm-5.2 (the lighthouse's capture 158, the shipped card):
#: the role's own effort 12,117 output tokens, 45 s, about 8.5 cents; "low"
#: 5,400, 21 s; "off" 2,153, 10 s, about 1.5 cents -- the three answers
#: equally in character and equally shaped (eight routine stretches, five to
#: seven plans; "he will not condemn what he has not examined"). None leaves
#: the role's setting in charge. Named per the owner's rule on caps; the
#: owner asked for the skip's cost to come down (2026-10-22).
SKIP_QUESTION_REASONING = "off"

#: How much of a planned room's own `purpose` rides beside its name when the
#: decision model is asked which room a mind's words mean: "bedroom" names
#: "Elias's Room" only to a reader told it is one of the tower's bedrooms.
#: Named per the owner's rule on caps.
SKIP_PLACE_OPTION_CHARS = 120

#: A posture a sleeper lies in at the far end: its pose is the skip's, not
#: the one it last stood in. Protocol tokens of the pose ledger.
_ASLEEP_POSE = {"posture": "lying", "support": "", "relative_to": "",
                "relation": "", "constraint": "", "detail": ""}


# --------------------------------------------------------------------------
# When the stage runs, and over what
# --------------------------------------------------------------------------

def kept_skip(interp):
    """The time block the players' input passed over and the ladder kept,
    or None (`director_prose.the_input_set_the_time`)."""
    from agents.director_prose import the_input_set_the_time
    return the_input_set_the_time(interp if isinstance(interp, dict) else {})


def skip_lives_planned(interp, offscreen=False):
    """Is the skip stage in this beat's plan? Read from the STORED interpret
    output alone, so a resume, a rerun and a replay rebuild the same plan: the
    input kept a skip at least `SKIP_LIVED_SECONDS` long. Never in a bubble's
    own beat -- its frame keeps its own clock."""
    if offscreen:
        return False
    from world.mechanics import skip_seconds
    block = kept_skip(interp)
    return block is not None and skip_seconds(block) >= itin.SKIP_LIVED_SECONDS


def _skip_chrono(interp):
    """The chrono id of the first step whose patch passes over time, or None."""
    steps = ((interp.get("state_assertions") or {}).get("causal_steps") or []) \
        if isinstance(interp, dict) else []
    for step in steps:
        patch = (step or {}).get("patch") if isinstance(step, dict) else None
        if isinstance(patch, dict) and isinstance(patch.get("time"), dict):
            try:
                return int(step.get("chrono_id"))
            except (TypeError, ValueError):
                return None
    return None


def _seconds_before_skip(interp):
    """Story seconds the input's own steps took BEFORE the stretch it passes
    over: the steps priced at interpret (a contestable one is the resolve's to
    price) whose chrono comes before the skip's."""
    chrono = _skip_chrono(interp)
    if chrono is None:
        return 0.0
    total = 0.0
    for row in (interp.get("causal_ledger") or []):
        if not isinstance(row, dict) or str(row.get("commitment") or "").casefold() == "contestable":
            continue
        try:
            if int(row.get("chrono_id")) >= chrono:
                continue
            seconds = row.get("seconds")
            if isinstance(seconds, (int, float)) and not isinstance(seconds, bool):
                total += max(0.0, float(seconds))
        except (TypeError, ValueError):
            continue
    return total


def beat_span(chat_id, interp, clock=None):
    """The stretch the cast live through, as an `itin.Span`: from where the
    clock stands when the input's account reaches its skip, for as long as
    the skip lasts (`world.mechanics.skip_seconds`, the length interpret
    solved). The hour of the story's day is the clock's own reading
    (`day_cycle.clock_hour`, as `director_prose.stage_start_hour` reads it)."""
    from story.scene import simulation_clock, style_guide
    from world.day_cycle import clock_hour
    from world.mechanics import clock_elapsed, skip_seconds
    clock = clock if isinstance(clock, dict) else simulation_clock(chat_id)
    elapsed = clock_elapsed(clock)
    before = _seconds_before_skip(interp)
    lasts = skip_seconds(kept_skip(interp))
    hour, length = clock_hour(clock, style_guide(chat_id))
    hour0 = None if hour is None else hour + before / 3600.0
    return itin.Span(elapsed + before, elapsed + before + lasts, hour0, length)


def span_of_output(chat_id, output):
    """The Span a stored step output covers, its day placed from the stored
    clock (which the beat has not moved yet): the step keeps the bare
    seconds the build spec fixes, and the hour is read again, the same way."""
    from story.scene import simulation_clock, style_guide
    from world.day_cycle import clock_hour
    from world.mechanics import clock_elapsed
    span = (output or {}).get("span") or {}
    try:
        start = float(span.get("from_s"))
        end = float(span.get("until_s"))
    except (TypeError, ValueError):
        return None
    clock = simulation_clock(chat_id)
    hour, length = clock_hour(clock, style_guide(chat_id))
    hour0 = None if hour is None else hour + (start - clock_elapsed(clock)) / 3600.0
    return itin.Span(start, end, hour0, length)


# --------------------------------------------------------------------------
# Who is asked
# --------------------------------------------------------------------------

def _row_name(row):
    from story.character_schema import character_name_from_text
    try:
        return character_name_from_text(row["sheet"]) or ""
    except Exception:
        return ""


def _bubble_cast_ids(chat_id, frame_id):
    """Cast ids active in a live spatial frame other than this one: their
    frame keeps its own clock, and they are not asked."""
    rows = q("SELECT ccf.char_id, ccf.frame_id FROM chat_char_frames ccf "
             "JOIN frames f ON f.id=ccf.frame_id "
             "WHERE ccf.chat_id=? AND ccf.status='active' AND f.kind='spatial' "
             "AND f.merged_turn_idx IS NULL", (chat_id,))
    return {int(r["char_id"]) for r in rows if r["frame_id"] != frame_id}


def asked_rows(chat_id, frame_id, cast_rows):
    """`[row]` -- every mind this skip asks, as cast rows (`status` kept):
    the frame's active cast and its dormant cast with no bubble of their own,
    less any body the story holds sedated or unconscious. Sorted by id."""
    from story.scene import awareness_of, awareness_map, extant_cast
    out = {int(r["id"]): dict(r) for r in cast_rows or ()}
    bubbles = _bubble_cast_ids(chat_id, frame_id)
    for row in extant_cast(chat_id, frame_id):
        cid = int(row["id"])
        if cid in out or cid in bubbles:
            continue
        if str(row["status"] or "") == "dormant":
            out[cid] = dict(row)
    amap = awareness_map(chat_id)
    asked = []
    for cid in sorted(out):
        level = awareness_of(amap, _row_name(out[cid]))
        if level in ("sedated", "unconscious"):
            continue
        asked.append(out[cid])
    return asked


# --------------------------------------------------------------------------
# The question
# --------------------------------------------------------------------------

def last_view(ctx, cid):
    """`(view, observations)`: what last reached this mind -- its view at
    the close of the previous beat in this frame (`perception_outcome`), the
    world as the stretch begins. `(None, [])` when it was not there."""
    from persist.steps import active_content
    try:
        row = q("SELECT id FROM turns WHERE chat_id=? AND idx<? AND frame_id IS ? "
                "ORDER BY idx DESC LIMIT 1",
                (ctx.chat.id, ctx.turn.idx, ctx.turn.frame_id), one=True)
        outcome = active_content(row["id"], "perception_outcome") if row else None
    except Exception:
        outcome = None
    if not isinstance(outcome, dict):
        return None, []
    view = (outcome.get("views") or {}).get(str(cid))
    observations = (outcome.get("observations") or {}).get(str(cid)) or []
    return (view or None), list(observations)


def _offers_for(interp, cid):
    """The propositions the account offered THIS mind
    (`director_interpret.authorial_offers`, `{subject_id, proposition}`):
    the account's framing of another mind is an offer, never authorship."""
    return [str(o.get("proposition")) for o in ((interp or {}).get("authorial_offers") or [])
            if isinstance(o, dict) and o.get("subject_id") == cid
            and str(o.get("proposition") or "").strip()]


def skip_block(span, *, asleep_now, where_you_are, offers):
    """The `skip` block of the question, in the mind's own terms: how long
    the stretch lasts (whole days and hours), the part of the day it begins
    in, the day (0 is today) and part of the day it ends at -- the engine's
    own `{days, until_phase}` vocabulary -- the parts of the day an answer
    may name (`day_cycle.PHASE_NAMES`, protocol tokens), whether the mind is
    asleep as it begins, where it is, and what the account offers it.

    AN OFFER IS FOR WHEN THE STRETCH ENDS, so it sits under `until`. The
    account's events happen at the far end, the moment the story takes up
    again, and what it offers a mind is for that moment: taken up, it is
    where the stretch leaves the mind (`at_the_end`, laid over the span's
    last moments by `skip_itinerary.expand_itinerary`). Measured on the
    lighthouse replayed a second time (chat 3 turn 26, 2026-10-21): offered
    "comes down the tower stair into the kitchen with a mug of tea and sits
    at the kitchen table across from Rhona Carrick" beside the stretch's
    start, the keeper took it up as his plan's first stretch, morning to
    midday, and was up in the lamp room on the night watch when the story
    took up again."""
    from world.day_cycle import PHASE_NAMES
    until = dict(span.until_words() or {})
    until["offers"] = list(offers or [])
    block = {"length": span.length_words(),
             "now": span.phase_at(span.from_s) or "",
             "until": until,
             "parts_of_day": list(PHASE_NAMES),
             "asleep_now": bool(asleep_now),
             "where_you_are": where_you_are or ""}
    return block


def skip_card(name, language=None):
    """The question's card (`prompts/character_skip.txt`, en and ja)."""
    from llm.prompts import get_prompt
    return get_prompt("character_skip", language=language).replace("{name}", name)


def ask(ctx, row, span, nonce=0):
    """`(answer, error)`: one mind's answer to the skip question, or None
    with what went wrong. The payload is its ordinary character payload
    (`character_step(skip=...)`), plus the `skip` block."""
    from agents.character import character_step
    from agents.character_bare import reading_order, without_engine_numbers
    from agents.character_evidence import compact_character_evidence
    from story.scene import awareness_of, awareness_map
    cid = int(row["id"])
    name = _row_name(row)
    view, observations = last_view(ctx, cid)
    try:
        built = character_step(ctx, cid, nonce, skip={
            "row": row, "view": view, "observations": observations})
    except Exception as exc:  # noqa: BLE001 -- the default day answers instead
        return None, f"payload not built ({type(exc).__name__}: {str(exc)[:160]})"
    if not isinstance(built, dict) or not isinstance(built.get("payload"), dict):
        return None, "payload not built"
    payload = built["payload"]
    where, _away = _standing_place(ctx.chat.id, name, row)
    scene = _stored_scene(ctx.chat.id)
    place_name = _away or ((scene.get("rooms") or {}).get(where) or {}).get("name") or where or ""
    payload["skip"] = skip_block(
        span, asleep_now=awareness_of(awareness_map(ctx.chat.id), name) == "asleep",
        where_you_are=place_name, offers=_offers_for(ctx.director_interpret, cid))
    wire, _handles = compact_character_evidence(payload)
    wire = without_engine_numbers(reading_order(wire))
    try:
        answer = _agent_json(built["role"], "character_skip", skip_card(name, ctx.language),
                             wire, temperature=built.get("temperature"),
                             sampler=built.get("sampler"),
                             reasoning_effort=SKIP_QUESTION_REASONING)
    except Exception as exc:  # noqa: BLE001 -- the default day answers instead
        return None, f"no answer ({type(exc).__name__}: {str(exc)[:160]})"
    return (answer if isinstance(answer, dict) else None), None


def _agent_json(*args, **kwargs):
    """The validated-JSON seam every stage's model call goes through, read
    at call time so a test stubs this module's own name."""
    from agents.common import _agent_json as call
    return call(*args, **kwargs)


# --------------------------------------------------------------------------
# Places, things and where a mind stands
# --------------------------------------------------------------------------

def _stored_scene(chat_id):
    return wget(chat_id, "scene", {}) or {}


def _whereabouts(chat_id):
    value = wget(chat_id, WHEREABOUTS_KEY, {}) or {}
    return value if isinstance(value, dict) else {}


def _fold(text):
    return " ".join(str(text or "").split()).casefold()


def _position_of(scene, name):
    positions = scene.get("positions") or {}
    for key, room in positions.items():
        if _fold(key) == _fold(name):
            return room
    return None


def _standing_place(chat_id, name, row):
    """`(room, away)` -- where the mind stands as the stretch begins: an
    active mind where the scene puts it; a dormant one at its whereabouts
    when it has one, else where the scene last put it, else nowhere."""
    scene = _stored_scene(chat_id)
    room = _position_of(scene, name)
    if str((row or {}).get("status") or "") == "dormant":
        record = next((v for k, v in _whereabouts(chat_id).items()
                       if _fold(k) == _fold(name) and isinstance(v, dict)), None)
        if record and str(record.get("label") or "").strip():
            return None, str(record["label"]).strip()
    if room and room in (scene.get("rooms") or {}):
        return room, None
    return None, None


def _left_the_map_from(chat_id, name):
    """The room an away mind left the map by, as its whereabouts keep it
    (`left_from`), when the world still holds it: where it comes back by
    (`skip_itinerary.live_through`'s `start_exit`). None where nothing kept
    one -- a whereabouts written before the record carried it."""
    scene = _stored_scene(chat_id)
    record = next((v for k, v in _whereabouts(chat_id).items()
                   if _fold(k) == _fold(name) and isinstance(v, dict)), None)
    room = str((record or {}).get("left_from") or "").strip()
    return room if room and room in (scene.get("rooms") or {}) else None


def known_places(scene, state, here=None):
    """`{room_id: name}` -- the places this mind knows, as its own words are
    resolved against them: the rooms its own map holds (`place_graph`,
    written only from where it stood and what it saw), and the rooms of the
    building it stands in as the stretch begins (`spatial.
    rooms_under_one_roof`) -- a body knows the house it is in. Only rooms the
    world holds now: a place it remembers that is gone is no place to put it."""
    from world.spatial import rooms_under_one_roof
    rooms = scene.get("rooms") or {}
    out = {}
    nodes = ((state or {}).get("place_graph") or {}).get("nodes") or {}
    for rid, record in nodes.items():
        if str(rid) in rooms:
            out[str(rid)] = str((rooms[str(rid)] or {}).get("name")
                                or (record or {}).get("name") or rid)
    if here and here in rooms:
        for rid, room in rooms_under_one_roof(scene, [here]).items():
            out.setdefault(str(rid), str((room or {}).get("name") or rid))
        out.setdefault(str(here), str((rooms[here] or {}).get("name") or here))
    return out


def place_options(scene, known):
    """`{room_id: option text}` for the decision model: each known room by
    its name, and a planned room's own `purpose` beside it, cut to
    `SKIP_PLACE_OPTION_CHARS` -- what the room is FOR is how a mind's own
    word for it ("bedroom", "the harbour") is read against a name."""
    rooms = scene.get("rooms") or {}
    out = {}
    for rid, name in known.items():
        purpose = " ".join(str((rooms.get(rid) or {}).get("purpose") or "").split())
        if purpose:
            cut = purpose[:SKIP_PLACE_OPTION_CHARS]
            if len(purpose) > SKIP_PLACE_OPTION_CHARS:
                cut = cut.rsplit(" ", 1)[0]
            out[rid] = "%s (%s)" % (name, cut.rstrip(" ,;:."))
        else:
            out[rid] = name
    return out


def held_things(scene, name):
    """`{key: label}` -- what this mind has on it: the things the scene
    holds inside it (`contained`) by their names, and what it wears, line by
    line (`attire.wearing`), which is where a pocket's contents are written."""
    out = {}
    entities = scene.get("entities") or {}
    for thing, record in (scene.get("contained") or {}).items():
        if isinstance(record, dict) and _fold(record.get("in")) == _fold(name):
            label = (entities.get(thing) or {}).get("name") if isinstance(entities.get(thing), dict) else None
            out[str(thing)] = str(label or thing)
    attire = scene.get("attire") or {}
    entry = next((v for k, v in attire.items() if _fold(k) == _fold(name)), None)
    for n, item in enumerate((entry or {}).get("wearing") or [] if isinstance(entry, dict) else []):
        text = item if isinstance(item, str) else (item or {}).get("item") if isinstance(item, dict) else ""
        if str(text or "").strip():
            out[f"worn:{n}"] = str(text)
    return out


def resolve_mind(name, stretches, scene, state, here, held, language=None,
                 *, under_way=None, ways=None):
    """`(stretches, holding, record)`: the mind's stretches with their
    places resolved, its holding check (`skip_itinerary.Holding`: called as
    `missing_from(uses, room, away, t) -> [words]`, what a stretch uses that
    is out of the mind's reach where the stretch finds it, `Reach.missing`;
    its `fetch(words, room, away, t, until) -> (got, seconds)`, what of that
    it fetches inside the stretch over `ways`, `Reach.fetch`), and what was
    asked. Exact first, then ONE decision-model request for everything exact
    left -- places and things together, a thing over what the mind has on it
    (`held`) and the things and fixtures of the world it may mean (`Reach.
    options`) -- and what neither answers is an off-map label, or words that
    name no thing the world holds (never missing: `Reach`). A place the
    request asked about and got no answer for is a label marked `unplaced`
    (`skip_itinerary.unanswered_places`), on which no crossing ever fails:
    no answer never invents a failure. `under_way` is
    `skip_itinerary.journeys`: a vessel under way stands where its journey
    has brought it."""
    from llm import decisions
    texts = []
    for item in stretches:
        text = item.get("where_text") or ""
        if text and text not in texts:
            texts.append(text)
    known = known_places(scene, state, here)
    # ...and every room the world holds that the mind names by its whole
    # name (`skip_itinerary.rooms_named_in`): naming it is knowing it.
    for rid, room_name in itin.rooms_named_in(texts, scene.get("rooms") or {}).items():
        known.setdefault(rid, room_name)
    resolved = {}
    unresolved = []
    for text in texts:
        rid = itin.resolve_exact(text, known)
        if rid:
            resolved[text] = rid
        else:
            unresolved.append(text)
    reach = itin.Reach(scene, name, carried=held, journeys=under_way, ways=ways)
    things = []
    for item in stretches:
        for thing in item.get("uses") or ():
            if thing not in things:
                things.append(thing)
    named = {thing: reach.named(thing) for thing in things}
    unnamed = [thing for thing in things if not named[thing]]
    first = [room for room in [here, *resolved.values()] if room]
    offered = reach.options(first=first, known=sorted(known))
    options = place_options(scene, known)
    questions = {**itin.place_questions(name, unresolved, options, language),
                 **itin.thing_questions(name, unnamed, offered, language)}
    record = {"known": sorted(known), "exact": dict(resolved), "asked": len(questions)}
    answers = {}
    if questions:
        state_for_jev = {"mind": name, "stands_in": known.get(here, here or ""),
                         "stretches": [{"where": i.get("where_text"), "doing": i.get("doing")}
                                       for i in stretches[:40]]}
        try:
            answers = decisions.decide(state_for_jev, questions)
        except Exception as exc:  # noqa: BLE001 -- unanswered is off the map
            record["jev_failed"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    resolved.update(itin.read_place_answers(answers, unresolved, options))
    unplaced = itin.unanswered_places(answers, unresolved, questions) - set(resolved)
    for thing, key in itin.read_thing_picks(answers, unnamed, offered).items():
        named[thing] = {key}
    record["resolved"] = dict(resolved)
    if unplaced:
        record["unplaced"] = sorted(unplaced)
    record["things"] = {thing: sorted(keys) for thing, keys in named.items()}
    return (itin.place_stretches(stretches, resolved, unplaced),
            itin.Holding(reach, named), record)


def judge_what_was_missing(name, log, language=None):
    """`record`: ONE decision-model request for this mind over every row of
    its log a thing not to hand failed (`skip_itinerary.short_of`): can it do
    what the row says without what was missing
    (`skip_itinerary.without_questions`)? A row the model says can be done
    without them is told as far as it went (`skip_itinerary.judge_without`:
    `not_known`, `missing` kept), and so is a row it gives no answer for --
    the request failed, or never went: NO ANSWER NEVER INVENTS A FAILURE.
    Only the model's own no keeps a row failed. Nothing is asked for a mind
    with no such row. In place on `log`; the record says what was asked,
    what it changed and what went unanswered."""
    from llm import decisions
    rows = itin.short_of(log)
    if not rows:
        return {}
    questions = itin.without_questions(name, log, language)
    state = {"mind": name,
             "stretches": [{"where": log[i].get("where_text") or log[i].get("away") or "",
                            "doing": log[i].get("doing") or "",
                            "missing": list(log[i].get("missing") or ())}
                           for i in rows]}
    record = {"asked": len(questions)}
    answers = {}
    if questions:
        try:
            answers = decisions.decide(state, questions) or {}
        except Exception as exc:  # noqa: BLE001 -- unanswered: told as far as it went
            record["jev_failed"] = f"{type(exc).__name__}: {str(exc)[:120]}"
    unanswered = [i for i in rows if not itin.answered(answers.get(f"without:{i}"))]
    record["without"] = itin.judge_without(log, answers)
    if unanswered:
        record["unanswered"] = unanswered
    return record


def frontier_stubs(chat_id):
    """`{stub room id: holder room id}` -- every space the plan holds open
    (`structure.mint_frontier`'s `provisional` stub, by its `frontier_of`
    room): the joins `skip_itinerary.Ways` does not walk. Read from the
    shared registry parse; empty where it cannot be read."""
    try:
        from world.structure import registry_rows
        rows = registry_rows(chat_id)
    except Exception:  # noqa: BLE001 -- no registry, no frontier
        return {}
    out = {}
    for uid, entry in (rows or {}).items():
        spec = (entry or {}).get("planned")
        if not isinstance(spec, dict) or not spec.get("provisional"):
            continue
        origin = spec.get("frontier_of")
        holder = str(origin.get("room") or "").strip() if isinstance(origin, dict) else ""
        if holder:
            out[str(uid)] = holder
    return out


# --------------------------------------------------------------------------
# The stage
# --------------------------------------------------------------------------

def _stored_sleep(chat_id, name):
    """When this mind's current sleep began, if it is asleep now."""
    from story.scene import awareness_conditions
    starts = [r.get("started_at_seconds") for r in awareness_conditions(chat_id)
              if r.get("level") == "asleep" and _fold(r.get("subject")) == _fold(name)]
    starts = [float(s) for s in starts if isinstance(s, (int, float))]
    return min(starts) if starts else None


def _player_name(chat):
    from story.character_schema import persona_name
    from story.scene import persona_of
    try:
        return persona_name(persona_of(chat)) or ""
    except Exception:
        return ""


def player_span_place(interp, player_name, scene):
    """Where the account places the player THROUGH the stretch, or None: a
    position its typed events give the player at or before the step that
    passes over the time. A position given after it is the far end's, and a
    player the account does not place is placed nowhere -- the engine never
    assumes where a player spent the hours."""
    chrono = _skip_chrono(interp)
    if chrono is None or not player_name:
        return None
    place = None
    for step in ((interp.get("state_assertions") or {}).get("causal_steps") or []):
        try:
            if int(step.get("chrono_id")) > chrono:
                continue
        except (TypeError, ValueError):
            continue
        positions = ((step.get("patch") or {}).get("positions") or {})
        for key, room in positions.items():
            if _fold(key) == _fold(player_name) and room in (scene.get("rooms") or {}):
                place = room
    return place


def skip_lives(ctx, nonce):
    """The stage (see the module docstring). Returns the build spec's shape:
    `{"span": {from_s, until_s}, "minds": {name: {source, answer, itinerary,
    log, far_end}}}`."""
    from story.scene import extant_cast, style_guide, weather_severity
    from world.mechanics import clock_elapsed
    from story.scene import simulation_clock
    chat_id = ctx.chat.id
    interp = ctx.director_interpret if isinstance(ctx.director_interpret, dict) else {}
    span = beat_span(chat_id, interp)
    out = {"span": span.as_dict(), "minds": {}}
    if not skip_lives_planned(interp):
        return out
    scene = _stored_scene(chat_id)
    rows = asked_rows(chat_id, ctx.turn.frame_id, ctx.cast)
    if not rows:
        return out
    # a. ASK, in parallel, each in a copy of this step's context so its
    # provider calls are filed under this step.
    answers, errors = {}, {}
    workers = max(1, min(SKIP_ASK_WORKERS, len(rows)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {int(r["id"]): pool.submit(copy_context().run, ask, ctx, r, span, nonce)
                   for r in rows}
        for cid, future in futures.items():
            try:
                answers[cid], errors[cid] = future.result()
            except Exception as exc:  # noqa: BLE001 -- the default day answers
                answers[cid], errors[cid] = None, f"{type(exc).__name__}: {exc}"
    skies = itin.Skies(scene, span, seed="chat:%s" % chat_id,
                       severity=weather_severity(chat_id),
                       written_at=clock_elapsed(simulation_clock(chat_id)))
    # The ways a body walks, and the journeys the world has under way: one
    # world for every mind asked.
    ways = itin.Ways(scene, joins=itin.frontier_joins(frontier_stubs(chat_id)))
    under_way = itin.journeys(scene, span.from_s)
    logs, minds, named = {}, {}, {}
    for row in rows:
        cid = int(row["id"])
        name = _row_name(row)
        if not name:
            continue
        answer = answers.get(cid)
        if errors.get(cid):
            ctx.add_warning(f"skip: {name} was not asked ({errors[cid]}); "
                            "the default day stands for them")
        stretches = itin.expand_itinerary(answer, span)
        source = "asked" if stretches else "default"
        if not stretches:
            if answer is not None and not errors.get(cid):
                ctx.add_warning(f"skip: {name}'s answer said nothing an itinerary "
                                "can be built from; the default day stands for them")
            stretches = itin.default_day(span)
        state = _cast_state(row)
        here, away = _standing_place(chat_id, name, row)
        left_by = _left_the_map_from(chat_id, name) if away else None
        try:
            stretches, holding, record = resolve_mind(
                name, stretches, scene, state, here, held_things(scene, name),
                ctx.language, under_way=under_way, ways=ways)
        except Exception as exc:  # noqa: BLE001 -- one mind, not the beat
            ctx.add_warning(f"skip: {name}'s places could not be read "
                            f"({type(exc).__name__}: {str(exc)[:120]}); the "
                            "default day stands for them, where they stand")
            source, answer = "default", answer if isinstance(answer, dict) else None
            stretches = itin.place_stretches(itin.default_day(span), {})
            holding, record = None, {"failed": str(exc)[:120]}
        # A thing the mind can walk to and back for inside a stretch is to
        # hand (`Reach.fetch`), in either executor.
        fetch_from = holding.fetch if holding is not None else None
        # ...and what its stretches use, as the resolution named it: among
        # the things its own work may change (`skip_work.to_hand`).
        named[name] = dict(holding.named) if holding is not None else {}
        if hasattr(ctx, "note_decision"):
            ctx.note_decision("skip_places", name, source,
                              json.dumps(record, ensure_ascii=False)[:400])
        itinerary = [itin.as_stretch(s) for s in stretches]
        asleep_since = _stored_sleep(chat_id, name)
        # The town first, where it holds this body: None is no charter, no
        # body or place of its, a charter already past the span's start, or a
        # span longer than one advance carries -- and a run that breaks is
        # one mind's failure, said, never the beat's.
        try:
            result = charter_skip.live_in_charter(chat_id, scene, name,
                                                  itinerary, out["span"])
        except Exception as exc:  # noqa: BLE001 -- the mind's own runs it
            ctx.add_warning(f"skip: the charter could not run {name} "
                            f"({type(exc).__name__}: {str(exc)[:120]}); "
                            "their own executor runs the stretch")
            result = None
        if result is not None:
            log, far_end = result
            log = itin.lay_over(log, stretches, missing_from=holding,
                                fetch_from=fetch_from, skies=skies)
            far_end = itin.carry_sleep(far_end, span.from_s, asleep_since)
        else:
            log, far_end = itin.live_through(
                stretches, scene=scene, start_room=here, start_away=away,
                start_exit=left_by, asleep_since=asleep_since,
                missing_from=holding, fetch_from=fetch_from, skies=skies, ways=ways,
                journey=itin.journey_under_way(scene, here, under_way, ways))
        log = itin.place_words(log, scene)
        # A thing not to hand fails a stretch only where the stretch cannot
        # be done without it: one request for this mind, either executor's.
        # No answer never invents a failure: a row nothing judged is told
        # as far as it went.
        try:
            judged = judge_what_was_missing(name, log, ctx.language)
        except Exception as exc:  # noqa: BLE001 -- one mind, not the beat
            ctx.add_warning(f"skip: what {name} went without could not be judged "
                            f"({type(exc).__name__}: {str(exc)[:120]}); those "
                            "stretches are told as far as they went")
            judged = {"failed": str(exc)[:120]}
            with contextlib.suppress(Exception):
                judged["without"] = itin.judge_without(log, {})
        if judged and hasattr(ctx, "note_decision"):
            ctx.note_decision("skip_without", name,
                              "unanswered" if (judged.get("jev_failed") or judged.get("failed"))
                              else "asked",
                              json.dumps(judged, ensure_ascii=False)[:400])
        # Where a day that ends off the map left it, kept on its whereabouts:
        # the next skip brings it back by there (`persist/commit_skip.py`).
        # The mind's own executor says where its walk left the map -- after
        # a ride, where the journey brought it, which no row of the log
        # stands in (`skip_itinerary.live_through`); the town's rows say it
        # themselves.
        far_end = dict(far_end, left_from=(
            (far_end.get("left_from") or itin.left_the_map_from(log, here, left_by))
            if far_end.get("away") and not far_end.get("room") else None))
        logs[name] = log
        minds[name] = {"source": source,
                       "answer": answer if isinstance(answer, dict) else None,
                       "itinerary": itinerary, "log": log, "far_end": far_end}
    # The player, where the account places them through the stretch: the one
    # body nobody asked, present only where the account puts it.
    p_name = _player_name(ctx.chat)
    p_room = player_span_place(interp, p_name, scene)
    if p_room:
        logs[p_name] = [{"from_s": span.from_s, "until_s": span.until_s,
                         "room": p_room, "away": None, "where_text": "",
                         "doing": "", "asleep": False, "seen": [],
                         "weather": None, "outcome": itin.OUTCOME_DONE,
                         "reason": None}]
    _share(ctx, logs, rows, scene)
    out["minds"] = minds
    # WHAT EACH MIND'S OWN WORK CHANGED: its `done` rows on the map, told to
    # the encoder once per mind and settled in time order against the stored
    # world (`agents/skip_work.py`); the far end lays what passed (`FarEnd`).
    # A mind with no such row is asked nothing, and one whose work cannot be
    # typed leaves the things as the stretch found them -- said, never the
    # beat's failure.
    from agents import skip_work
    from llm.providers import Aborted
    try:
        skip_work.type_the_work(
            ctx, minds, scene,
            {_fold(_row_name(r)): int(r["id"]) for r in rows if _row_name(r)},
            named=named, nonce=nonce)
    except Aborted:
        raise
    except Exception as exc:  # noqa: BLE001 -- the far end stands without it
        ctx.add_warning(f"skip: what the minds' own work changed was not typed "
                        f"({type(exc).__name__}: {str(exc)[:160]}); the things "
                        "stand as the stretch found them")
        for mind in minds.values():
            mind["worked"] = None
    return out


def _cast_state(row):
    try:
        raw = row["cstate"]
    except (KeyError, IndexError, TypeError):
        raw = None
    try:
        value = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except (TypeError, ValueError):
        value = {}
    return value if isinstance(value, dict) else {}


def _share(ctx, logs, rows, scene):
    """Company across every asked mind's log (and the player's, where the
    account places them), each observer's names and its identity floor its
    own."""
    from agents.common import observer_label_fn, observer_name_scrub, scrub_names_deep
    chat = {"id": ctx.chat.id, "persona_id": getattr(ctx.chat, "persona_id", None)}
    labels, scrubs = {}, {}

    def label_for(observer, other):
        if observer not in labels:
            labels[observer] = observer_label_fn(chat, observer, rows, scene)
        try:
            return str(labels[observer](other) or other)
        except Exception:  # noqa: BLE001 -- a stranger is the unnamed person
            return other

    def scrub(observer, text):
        if observer not in scrubs:
            scrubs[observer] = observer_name_scrub(chat, observer, rows)
        try:
            return scrub_names_deep(text, scrubs[observer])
        except Exception:  # noqa: BLE001
            return text

    itin.share_company(logs, label_for, scrub)


# --------------------------------------------------------------------------
# The far end, as an onset preview and for the commit
# --------------------------------------------------------------------------

class FarEnd:
    """The skip's far end over the stored world: read by `story.scene`'s
    `get_scene` and `awareness_conditions` while a stage after this one runs
    (`core.pipeline_context.beat_onset`), by the planner's gates, and by the
    commit. Computed once against the stored scene and kept: every reader
    of the beat sees the same far end.

    What it changes, per asked mind: placed where its last stretch left it
    (seated one pace inside the door it came by), or out of the scene when
    that place is off the map; its pose (a sleeper lies down), its follow,
    its holds on others and theirs on it, its being carried, and its facing
    are the skip's, not the ones it had when the stretch began. Its
    awareness: a sleep that ran on unbroken keeps its row; one it woke from
    ends; one it fell into starts when it began. And the THINGS its own work
    changed -- what its `done` rows on the map did to the things it had to
    hand, as the stage settled them (`minds[*].worked`, `agents/skip_work.py`)
    -- laid first, every mind's in time order, so the minds are placed among
    the things as their days left them."""

    def __init__(self, chat_id, output, turn_id=None):
        self.chat_id = chat_id
        self.output = output if isinstance(output, dict) else {}
        self.turn_id = turn_id
        self._delta = None

    @property
    def minds(self):
        minds = self.output.get("minds")
        return minds if isinstance(minds, dict) else {}

    # -- the scene -----------------------------------------------------------

    def _things(self, stored):
        """What the minds' own work changed in the things they worked on
        (`skip_work.things_at_far_end`), computed once like the placements:
        {} when no mind's work changed anything -- or when it cannot be
        laid, which leaves the things as the stretch found them and the far
        end standing without them."""
        try:
            from agents import skip_work
            return skip_work.things_at_far_end(stored, self.minds)
        except Exception:  # noqa: BLE001 -- the placements stand without it
            from core.logging_utils import logger
            logger.exception("the skip's work could not be laid on chat %s", self.chat_id)
            return {}

    def _compute(self, stored):
        from agents import skip_work
        from world.spatial import inside_the_door, landing_cell
        rooms = stored.get("rooms") or {}
        things = self._things(stored)
        work = skip_work.lay_things(copy.deepcopy(stored), things)
        place, away, cells = {}, set(), {}
        for name in sorted(self.minds):
            far = (self.minds[name] or {}).get("far_end") or {}
            room = far.get("room")
            if room and room in rooms:
                place[name] = room
                if _position_of(stored, name) != room:
                    came = None
                    for row in reversed((self.minds[name] or {}).get("log") or []):
                        if row.get("room") and row.get("room") != room:
                            came = row["room"]
                            break
                    try:
                        cell = landing_cell(work, room,
                                            inside_the_door(work, room, came), name)
                        cells[name] = [int(cell[0]), int(cell[1])]
                        work.setdefault("positions", {})[name] = room
                        work.setdefault("stations", {})[name] = {
                            "at": None, "near": [], "cell": cells[name]}
                    except Exception:  # noqa: BLE001 -- placed, not seated
                        pass
            elif far.get("away"):
                away.add(name)
        asleep = {name for name in self.minds
                  if ((self.minds[name] or {}).get("far_end") or {}).get("asleep")}
        self._delta = {"place": place, "away": away, "cells": cells, "asleep": asleep,
                       "things": things}
        return self._delta

    def apply_scene(self, chat_id, sc):
        """The far end laid onto a scene read from the store, in place: the
        things the minds' work changed, then the minds."""
        if chat_id != self.chat_id or not isinstance(sc, dict) or not self.minds:
            return sc
        delta = self._delta or self._compute(copy.deepcopy(sc))
        if delta.get("things"):
            from agents import skip_work
            skip_work.lay_things(sc, delta["things"])
        positions = sc.setdefault("positions", {})
        for name in sorted(self.minds):
            key = next((k for k in positions if _fold(k) == _fold(name)), name)
            moved = (name in delta["away"]
                     or (name in delta["place"] and positions.get(key) != delta["place"][name]))
            for ledger in ("poses", "following"):
                held = sc.get(ledger)
                if isinstance(held, dict):
                    for k in [k for k in held if _fold(k) == _fold(name)]:
                        held.pop(k, None)
            if isinstance(sc.get("contacts"), list):
                sc["contacts"] = [c for c in sc["contacts"] if not (
                    isinstance(c, dict) and _fold(name) in (_fold(c.get("actor")),
                                                           _fold(c.get("target"))))]
            if moved:
                for ledger in ("stations", "orientation", "contained"):
                    held = sc.get(ledger)
                    if isinstance(held, dict):
                        for k in [k for k in held if _fold(k) == _fold(name)]:
                            held.pop(k, None)
            if name in delta["away"]:
                positions.pop(key, None)
                continue
            if name in delta["place"]:
                if key != name:
                    positions.pop(key, None)
                positions[name] = delta["place"][name]
                if name in delta["cells"]:
                    sc.setdefault("stations", {})[name] = {
                        "at": None, "near": [], "cell": list(delta["cells"][name])}
            if name in delta["asleep"]:
                sc.setdefault("poses", {})[name] = dict(_ASLEEP_POSE)
        return sc

    # -- awareness -----------------------------------------------------------

    def condition_id(self, name):
        return "skip:%s:%s:asleep" % (self.turn_id if self.turn_id is not None else "beat",
                                      "_".join(_fold(name).split()))

    def awareness_changes(self, stored_rows):
        """`(ended, started)`: the stored awareness records the far end ends
        (each an `awareness_conditions` record), and the conditions it starts
        (each in the diff's `conditions` shape)."""
        ended, started = [], []
        for name in sorted(self.minds):
            far = (self.minds[name] or {}).get("far_end") or {}
            mine = [r for r in stored_rows or ()
                    if r.get("level") == "asleep" and _fold(r.get("subject")) == _fold(name)]
            since = far.get("asleep_since_s")
            kept = bool(far.get("asleep")) and any(
                isinstance(since, (int, float))
                and abs(float(r.get("started_at_seconds") or 0.0) - float(since)) < 1e-3
                for r in mine)
            if kept:
                continue
            ended.extend(mine)
            if far.get("asleep") and isinstance(since, (int, float)):
                started.append({
                    "condition_id": self.condition_id(name), "subject_id": name,
                    "kind": "awareness",
                    "state": {"level": "asleep", "cause": _sleep_cause(self.minds[name]),
                              "rousable_by": ""},
                    "started_at_seconds": float(since), "active": 1,
                    "source": STEP_KEY})
        return ended, started

    def overlay_awareness(self, chat_id, rows):
        """`awareness_conditions` as the far end has it."""
        if chat_id != self.chat_id or not self.minds:
            return rows
        ended, started = self.awareness_changes(rows)
        gone = {r.get("condition_id") for r in ended}
        out = [r for r in rows if r.get("condition_id") not in gone]
        for cond in started:
            out.append({"condition_id": cond["condition_id"], "subject": cond["subject_id"],
                        "level": "asleep", "cause": cond["state"]["cause"],
                        "rousable_by": "", "started_at_seconds": cond["started_at_seconds"],
                        "payload": dict(cond)})
        out.sort(key=lambda r: r["started_at_seconds"])
        return out

    def awareness_level(self, name):
        """The far end's word on a mind's awareness: "asleep", "awake", or
        None for a mind the skip did not carry."""
        for key, mind in self.minds.items():
            if _fold(key) == _fold(name):
                return "asleep" if ((mind or {}).get("far_end") or {}).get("asleep") else "awake"
        return None


def _sleep_cause(mind):
    """What put a mind under at the far end, in its own words: the doing of
    the sleep it ended in, or the plain fact of sleep."""
    log = (mind or {}).get("log") or []
    for row in reversed(log):
        if not row.get("asleep"):
            break
        if str(row.get("doing") or "").strip():
            return str(row["doing"])[:200]
    return "sleep"


def far_end_for(ctx):
    """The beat's `FarEnd`, made once from its skip step, or None."""
    output = ctx.get(STEP_KEY) if hasattr(ctx, "get") else None
    if not isinstance(output, dict) or not output.get("minds"):
        return None
    held = ctx._extra.get("_skip_far_end") if hasattr(ctx, "_extra") else None
    if isinstance(held, FarEnd) and held.output is output:
        return held
    far = FarEnd(ctx.chat.id, output, getattr(getattr(ctx, "turn", None), "id", None))
    if hasattr(ctx, "_extra"):
        ctx._extra["_skip_far_end"] = far
    return far


@contextlib.contextmanager
def onset_preview(far):
    """Every read of the stored scene and awareness inside this block sees
    the far end (`core.pipeline_context.beat_onset`)."""
    from core.pipeline_context import beat_onset
    if far is None:
        yield
        return
    token = beat_onset.set(far)
    try:
        yield
    finally:
        beat_onset.reset(token)


def far_end_scene(ctx, scene):
    """`scene` -- a scene read from the store -- with the beat's far end
    laid on it; unchanged when the beat has no skip."""
    far = far_end_for(ctx)
    return far.apply_scene(ctx.chat.id, scene) if far is not None else scene


# --------------------------------------------------------------------------
# The rest of the beat: its cast, its reactors, a mind's own payload
# --------------------------------------------------------------------------

def cast_at_far_end(chat_id, frame_id, cast_rows, output):
    """The beat's cast with every DORMANT mind the far end places in a room
    of this frame's world added, as an active row: it is back, and the beat
    plays with it there. An away mind stays in the rows; the scene places it
    nowhere, so no gate admits it."""
    minds = (output or {}).get("minds") if isinstance(output, dict) else None
    if not isinstance(minds, dict) or not minds:
        return list(cast_rows or [])
    from story.scene import extant_cast
    have = {int(r["id"]) for r in cast_rows or ()}
    rooms = (_stored_scene(chat_id).get("rooms") or {})
    out = list(cast_rows or [])
    for row in extant_cast(chat_id, frame_id):
        if int(row["id"]) in have:
            continue
        name = _row_name(row)
        far = next(((m or {}).get("far_end") or {} for k, m in minds.items()
                    if _fold(k) == _fold(name)), None)
        if far and far.get("room") in rooms:
            out.append(dict(row, status="active"))
    return out


def widen_reactors_to_skip_far_end(chat_id, cast_rows, reactors, output, interp):
    """`reactors` plus every asked mind the far end leaves, awake, in the
    room the beat opens on for the player -- the beat is played with it
    there, and the interpret, which chose the reactors before the stretch,
    never saw it arrive (`widen_reactors_to_rejoined`'s case, for a skip).
    A mind the far end takes elsewhere stays the Director's to name."""
    minds = (output or {}).get("minds") if isinstance(output, dict) else None
    if not isinstance(minds, dict) or not minds:
        return list(reactors)
    from agents.common import _present_cast_bodies
    from story.scene import get_scene, persona_of
    from story.character_schema import persona_name
    chat = q("SELECT * FROM chats WHERE id=?", (chat_id,), one=True)
    p_name = persona_name(persona_of(dict(chat))) if chat else ""
    scene = get_scene(chat_id)
    onset = ((interp or {}).get("onset_state_assertions")
             if (interp or {}).get("onset_state_assertions") is not None
             else (interp or {}).get("state_assertions")) or {}
    p_room = next((room for key, room in ((onset.get("positions") or {}).items())
                   if _fold(key) == _fold(p_name)), None) or _position_of(scene, p_name)
    if not p_room:
        return list(reactors)
    out = list(reactors)
    for body in _present_cast_bodies(scene, cast_rows):
        far = next(((m or {}).get("far_end") or {} for k, m in minds.items()
                    if _fold(k) == _fold(body["name"])), None)
        if far and body["room"] == p_room and not far.get("asleep") \
                and body["id"] not in out:
            out.append(body["id"])
    return out


def stretch_for_payload(ctx, name):
    """This mind's own log, in its own terms, for its far-end call --
    `[{day, from, until, where, doing, asleep, seen, weather, outcome,
    reason, meant, missing}]` (`reason` and `meant` only on a row that
    failed, `missing` on any row that went without things not to hand), the
    last `SKIP_PAYLOAD_ROWS` -- or None when the beat carried it through no
    skip. Its own and nobody else's: the rows are its log, and `seen` is
    already what it saw, named as it knows them."""
    output = ctx.get(STEP_KEY) if hasattr(ctx, "get") else None
    minds = (output or {}).get("minds") if isinstance(output, dict) else None
    if not isinstance(minds, dict):
        return None
    mind = next((m for k, m in minds.items() if _fold(k) == _fold(name)), None)
    log = (mind or {}).get("log") or []
    if not log:
        return None
    span = span_of_output(ctx.chat.id, output)
    rooms = _stored_scene(ctx.chat.id).get("rooms") or {}
    from world.spatial import room_display_name
    rows = []
    for row in log[-SKIP_PAYLOAD_ROWS:]:
        where = (row.get("away")
                 or (room_display_name(rooms.get(row["room"]), row["room"])
                     if row.get("room") else "")
                 or row.get("where_text") or "")
        entry = {"day": span.day_of(row["from_s"]) if span else 0,
                 "from": (span.phase_at(row["from_s"]) if span else None) or "",
                 "until": (span.phase_at(row["until_s"]) if span else None) or "",
                 "where": where, "doing": row.get("doing") or "",
                 "asleep": bool(row.get("asleep")),
                 "seen": [dict(s) for s in row.get("seen") or ()],
                 "weather": row.get("weather") or "",
                 "outcome": row.get("outcome") or itin.OUTCOME_DONE}
        if row.get("reason"):
            # What failed, as the row says it (`skip_itinerary._row`): where
            # it meant to be, in its own words, for a way it never made.
            entry["reason"] = row["reason"]
            if row.get("meant"):
                entry["meant"] = str(row["meant"])
        if row.get("missing"):
            # What was not to hand, as it named them: on a row it failed,
            # and on a row that went as far as it could without them
            # (`skip_itinerary.judge_without`).
            entry["missing"] = [str(thing) for thing in row["missing"]]
        rows.append(entry)
    return rows


def rehydrate(ctx, output):
    """What a stored skip step leaves on the context when a later stage
    reruns: the cast at the far end."""
    if not isinstance(output, dict) or not output.get("minds"):
        return
    ctx.cast = cast_at_far_end(ctx.chat.id, ctx.turn.frame_id, ctx.cast, output)
