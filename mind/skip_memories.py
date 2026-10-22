"""A mind's memories of a time skip, written after the beat that passed over it.

THE ASK (the owner, 2026-10-21): "... we can after the fact run a memory
generator based on their declared actions or charter hand off." The skip stage
(`skip_lives`) asks each cast member what it does over a skip, runs the answer
as an itinerary and leaves, per mind, its own LOG: where it was, what it did,
what it saw of whoever shared its place, the weather, and whether it came off.
This module turns that log into the mind's memories, out of band after the
commit (`persist/commit_memory_write.schedule_skip_memories`), so the far end
of the skip never waits for the writer; the far end's own character call
carries the log as payload that beat (`the_stretch_just_passed`).

THE FOUR RULES (`docs/design/DESIGN_OFFSCREEN_SUPERSEDED.md` § 3c, the owner's
dormancy ruling of 2026-09-17), and where each is kept:
  * THE LOG IS HERS. The writer is handed ONE mind's own log, card and memory
    -- never another mind's plan or log, the account beyond what reached it,
    or the Director's prose. `writer_payload` takes exactly those inputs
    (`WRITER_PAYLOAD_KEYS`) and `record_rows` reads a LOG row through an
    allowlist (`LOG_FIELDS`, `SEEN_FIELDS`): a field it does not name never
    reaches the call, whatever a later stage adds to the row.
  * THE CHARTER GAINS NO MIND. The rows are the character tier's, on the
    mind's own ledger; nothing is stored in charter `minds`.
  * BOUNDED BY THE GAP, NOT BY THE BEATS. One memory per
    `SKIP_HOURS_PER_MEMORY` lived hours, at least one, at most
    `SKIP_MEMORIES_MAX` (`memory_count`) -- a ceiling the writer is asked up
    to, never a quota to fill.
  * PROVENANCE IS `witnessed`. The mind was there. The origin travels on the
    row's `event_key` (`SKIP_ORIGIN_PREFIX`), never as a fifth provenance.

THE RECORD SAYS HOW IT WENT. A LOG row's `doing` is what the mind set
about, and its `outcome` a code; the record hands the writer the first as
`set_about` and the second IN WORDS as well (`how_it_went`, the pack's
templates): what did not come off and why, that the mind did it but does not
know what came of it, or that it did it and the record holds no more. A code alone was
read as success -- the lighthouse replayed 2026-10-21 (chat 3, turn 25): the
boatman's `failed`/`not_held` post-office stretch came back "So I did ...
into the box", where the probe's record, which said it in words, got the
loss written.

THE CHECK. The probe's writer invented (`DESIGN_THE_CAST_ACROSS_A_SKIP.md`
§ 2.2: 8 of 15 memories on the first card; 3-4 of 15, all mild, for the cheap
model on the tight one), and one broad "find the inventions" question to a
model flagged none of the inventions in two sets and flagged facts the record
gives in a third. So the check is narrow things:
  * a deterministic FLOOR for the most damaging kind -- a number, a clock time
    or a count a memory states that neither the record, `memory` nor the card
    holds (`unsupported_numbers`). A number is a CLOSED FORM: digits, and the
    pack's own number words composed by the pack's own grammar
    (`linguistics.mind.skip_memories`), never a list of ways to say one;
  * one decision-model question of each kind per memory
    (`SKIP_MEMORY_QUESTIONS`, `SKIP_MEMORY_CHECKS`): does anyone besides
    {name} speak or act beyond what the record's `with` shows; does it tell
    any row past its `how_it_went` -- what did not come off as done, or how
    any doing turned out; does it give a detail of the time before that
    neither `memory` nor the card holds -- each localized to its sentences
    by the same question asked of each.
A flagged memory is rewritten once, its flags named; if it still fails, its
flagged sentences go, and a memory with nothing left goes with them.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context

from core.db import q, transaction, wget
from core.logging_utils import logger
from language_runtime import apply_prompt_policy, current_language_id, linguistic
from llm import decisions
from llm.prompts import get_prompt, get_prompt_body, jev_question
from llm.providers import chat_complete
from mind.memory import (MemoryClock, RECENT_TURNS, _with_reading,
                         add_memories_batch, build_character_memory_context,
                         delete_memory, dump_chat_memories,
                         memory_bank_cache, prepare_memories_batch,
                         recent_memory_buffer)

#: The step whose COMMITTED output this reads: its active variant, as the
#: build spec fixes its shape (`{"span": {from_s, until_s}, "minds": {name:
#: {source, answer, itinerary, log, far_end}}}`).
SKIP_LIVES_STEP = "skip_lives"

#: HOW MANY MEMORIES A SKIP EARNS: one per this many LIVED hours -- the span,
#: sleep included -- at least `SKIP_MEMORIES_MIN`, at most `SKIP_MEMORIES_MAX`.
#: The owner's defaults (build spec, owner question 3); a week reaches the cap.
#: The writer is asked for UP TO this many: § 3c wants "a handful of rows
#: proportional to what actually happened, not to how long it took", and a
#: quota is how a writer is made to invent an occasion to fill it.
SKIP_HOURS_PER_MEMORY = 12
SKIP_MEMORIES_MIN = 1
SKIP_MEMORIES_MAX = 8

#: The writer's model row (`llm/providers.ROLES`); unset, it follows `default`.
SKIP_MEMORY_ROLE = "skip_memory"

#: The writer's output budget, the probe's (`skip_probe/mint2.py`): eight
#: memories of 180 words are under 2,000 tokens of answer, and the rest is room
#: for a reasoning model's trace, which the seam counts against the same cap.
SKIP_MEMORY_MAX_TOKENS = 12000

#: How many times one mind's writer is asked before its skip goes without
#: memories: an answer holding no usable memory is asked for once more.
SKIP_MEMORY_ATTEMPTS = 2

#: At or above this yes-probability the decision model's answer flags a
#: memory, or a sentence of one: the engine's default for a yes/no question
#: (`agents/director_prose.DEFAULT_THRESHOLD`).
SKIP_MEMORY_JEV_THRESHOLD = 0.5

#: How much of the job's summary line reaches the log: a skip asks the whole
#: cast, and each mind's summary -- status, the decision model's state, the
#: flags by kind -- runs to about two hundred characters.
SKIP_MEMORY_LOG_CHARS = 2400

#: How many minds' memories are written at once. A skip asks the whole cast;
#: one after another, six writers with their rewrites run past a minute and a
#: half, inside which the next beat may well start. In parallel they take as
#: long as the slowest.
SKIP_MEMORY_WORKERS = 4

#: A skip memory's salience: the floor plus the span times the stronger of its
#: arousal and the size of its valence, up to the ceiling. Set on the turn
#: memories' own band (`persist/commit_memory._salience_of`: 0.45 plus length,
#: at most 0.95), from the writer's own reading of the occasion: the probe's
#: lost letter (valence -0.85, arousal 0.8) lands at 0.79, a quiet run of
#: routine (0.1, 0.2) at 0.53.
SKIP_MEMORY_SALIENCE_FLOOR = 0.45
SKIP_MEMORY_SALIENCE_SPAN = 0.4
SKIP_MEMORY_SALIENCE_CEILING = 0.95

#: THE ORIGIN MARK. A skip memory's `event_key` is `skip:{turn_id}:{mind}:{n}`,
#: and the prefix is the mark: `event_key` is the one field every reader of a
#: row already carries verbatim -- checkpoint dump and restore, archive export
#: and import, branch clone, a citation's handle -- so the mark survives each of
#: them with no new column and no fifth provenance (§ 3c: "inventing one would
#: be a fifth value for every reader of that column to learn"). It never
#: reaches a mind: a character is handed a short handle in place of any key
#: (`agents/character_evidence.compact_character_evidence`).
SKIP_ORIGIN_PREFIX = "skip:"

#: EVERYTHING THE WRITER IS HANDED, AND NOTHING ELSE: the mind's card, its
#: memory from before the stretch, its own record of the stretch, and the
#: stretch itself. Built as a structure rather than filtered from a bigger one
#: -- the shape `world/offscreen.agent_context` set -- so a key nobody named
#: cannot ride in.
WRITER_PAYLOAD_KEYS = ("who", "memory", "record", "span")

#: The LOG row fields the record is built from (the build spec's LOG shape).
#: A row is read through this list and nothing else: another mind's plan or
#: its `why` is never on a mind's LOG row, and were a later stage to put one
#: there, this is where it would stop. `missing` (the things a `not_held`
#: stretch used that were neither on the mind nor within reach, in its own
#: words) and `meant` (where a stretch that never got there was going) are
#: the executor's, on a failed row; a log written before them reads without.
LOG_FIELDS = ("from_s", "until_s", "room", "away", "where_text", "doing",
              "asleep", "seen", "weather", "outcome", "reason", "missing",
              "meant")
#: Of what a mind saw of another, only who it knows them as and what they
#: were seen doing -- the other's `doing`, never their `why`.
SEEN_FIELDS = ("who", "doing")
#: A stretch's outcome, the LOG's closed set; anything else reads as the
#: world's to judge.
OUTCOMES = ("done", "failed", "not_known")

#: HOW A STRETCH WENT, IN WORDS: the pack's template (`compositor.templates`)
#: for each outcome, and for each reason a stretch fails, so the record says
#: what did not come off where it held only a code. The live case (the
#: lighthouse replayed 2026-10-21, chat 3 turn 25): the boatman's post-office
#: stretch reached the writer as `failed`/`not_held` and came back "So I did
#: ... into the box", in a world where the letter never left the rock; the
#: probe's record had said it in words ("it did not come off: the letter was
#: not in your pocket") and its writer wrote the loss. The reasons are the
#: executors' protocol tokens (`world/skip_itinerary.FAILURE_REASONS`), each
#: with two templates: its words, and its words naming what failed -- the
#: `missing` things for `not_held`, the place `meant` for a way that failed
#: -- used when the row names it. A reason with no words of its own reads as
#: the plain failure.
RECORD_WORDS = {
    "done": "skip_record_done",
    "not_known": "skip_record_not_known",
    "failed": "skip_record_failed",
    "list_separator": "skip_record_list_separator",
}
FAILURE_WORDS = {
    "not_held": ("skip_record_not_held", "skip_record_not_held_named"),
    "no_route": ("skip_record_no_route", "skip_record_no_route_named"),
    "shut_way": ("skip_record_shut_way", "skip_record_shut_way_named"),
    "too_far": ("skip_record_too_far", "skip_record_too_far_named"),
    "no_crossing": ("skip_record_no_crossing", "skip_record_no_crossing_named"),
}

#: What of the mind's card the writer reads: who it is, what drives it, how it
#: speaks, and its own past as the card tells it -- the voice, and the past
#: `memory` may not carry ("The past is what `memory` and `who` hold").
CARD_FIELDS = ("name", "psychology", "voice", "public_history",
               "private_history")

#: Keys of a memory packet that name rows or windows for the host -- handles,
#: never anything the mind remembers. Taken out of the writer's copy: a mind's
#: own character call never sees them either (it is handed short handles).
_PACKET_HANDLES = ("_internal", "memory_ref", "summary_id", "result_refs")

#: Closing marks a sentence may end inside of: quotes and brackets of either
#: script. Punctuation, not vocabulary.
_CLOSERS = "\"'”’)]」』»"


# ---------------------------------------------------------------------------
# The count and the step output.
# ---------------------------------------------------------------------------

def lived_hours(span):
    """The span's length in hours, 0.0 for one that cannot be read."""
    span = span if isinstance(span, dict) else {}
    try:
        seconds = float(span.get("until_s")) - float(span.get("from_s"))
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, seconds) / 3600.0


def memory_count(span):
    """How many memories a span earns: one per `SKIP_HOURS_PER_MEMORY` lived
    hours, at least `SKIP_MEMORIES_MIN`, at most `SKIP_MEMORIES_MAX`. A
    whole stretch of hours earns its memory: 23 hours is one, 24 is two.
    The clock prices a span to a tenth of a second
    (`day_cycle.SPAN_RESOLUTION_SECONDS`), so a sum landing a hair short of a
    whole hour is read as reaching it."""
    from world.day_cycle import SPAN_RESOLUTION_SECONDS
    hours = lived_hours(span) + SPAN_RESOLUTION_SECONDS / 3600.0
    return max(SKIP_MEMORIES_MIN,
               min(SKIP_MEMORIES_MAX, int(hours // SKIP_HOURS_PER_MEMORY)))


def minds_to_remember(output):
    """`[(mind name, its step entry)]` for every mind the step lived a stretch
    for -- a log with at least one row. Empty for no output, no minds, or a
    step that ran with none."""
    if not isinstance(output, dict):
        return []
    minds = output.get("minds")
    if not isinstance(minds, dict):
        return []
    out = []
    for name, entry in minds.items():
        if not str(name or "").strip() or not isinstance(entry, dict):
            continue
        log = entry.get("log")
        if isinstance(log, list) and any(isinstance(row, dict) for row in log):
            out.append((str(name), entry))
    return out


def committed_output(turn_id):
    """`(variant id, content)` of the skip step's ACTIVE variant for this
    turn, or None when the turn ran no such step."""
    from persist.steps import ENGINE_NOTES_KEY
    row = q("SELECT v.id AS vid, v.content AS content FROM steps s "
            "JOIN variants v ON v.step_id=s.id AND v.active=1 "
            "WHERE s.turn_id=? AND s.key=? ORDER BY s.ord, s.id LIMIT 1",
            (turn_id, SKIP_LIVES_STEP), one=True)
    if not row:
        return None
    try:
        content = json.loads(row["content"])
    except (TypeError, ValueError):
        return None
    if isinstance(content, dict):
        content = {k: v for k, v in content.items() if k != ENGINE_NOTES_KEY}
    return row["vid"], content


def still_committed(turn_id, turn_idx, variant_id):
    """Whether the beat the job read still stands as it was read: the turn is
    there at its index, its commit has not been taken back (`commit_seq`,
    cleared by a restore), and the skip step's active variant is the one the
    job wrote from. Asked inside the write's own transaction, so a reroll that
    lands between the read and the write leaves this job writing nothing."""
    row = q("SELECT t.idx AS idx, t.commit_seq AS seq, v.id AS vid "
            "FROM turns t JOIN steps s ON s.turn_id=t.id AND s.key=? "
            "JOIN variants v ON v.step_id=s.id AND v.active=1 WHERE t.id=?",
            (SKIP_LIVES_STEP, turn_id), one=True)
    return bool(row and row["seq"] is not None and row["idx"] == turn_idx
                and row["vid"] == variant_id)


# ---------------------------------------------------------------------------
# The record: the mind's own log, in its own terms.
# ---------------------------------------------------------------------------

def day_reader(chat_id):
    """`(anchor_hour, day_length)` for the story's clock, as every reader of
    a part of the day takes it (`world.day_cycle.clock_anchor`); the anchor is
    None when the story has never said what time it is."""
    from story.scene import simulation_clock, style_guide
    from world.day_cycle import clock_anchor
    clock = simulation_clock(chat_id)
    return clock_anchor(clock if isinstance(clock, dict) else {},
                        style_guide(chat_id))


def _seconds(value, default=None):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _day_number(seconds, anchor, length):
    """Which of the story's days a clock reading falls in. A day turns where
    its night ends (`day_cycle.DAY_TURNS_AT`): the small hours belong to the
    day before them, as "that night" does."""
    from world.day_cycle import DAY_TURNS_AT
    return math.floor((float(anchor) + float(seconds) / 3600.0) / float(length)
                      - DAY_TURNS_AT)


def _part_of_day(seconds, anchor, length):
    from world.day_cycle import hour_of_day, phase_of_hour
    return phase_of_hour(hour_of_day(seconds, anchor, length), length)


def when_of(from_s, until_s, span_from, anchor, length):
    """A stretch's `when` in the mind's own terms: the day, counted from 0 for
    the day the span began, and the parts of the day it ran from and until
    (`day_cycle.PHASES`, the engine's protocol names). With no anchor the
    story has no parts of the day to name, and the day is counted in whole
    days of the story's length from the span's start."""
    until_s = from_s if until_s is None else until_s
    if anchor is None:
        whole = max(1e-9, float(length)) * 3600.0
        return {"day": int(max(0.0, from_s - span_from) // whole)}
    day = _day_number(from_s, anchor, length) - _day_number(span_from, anchor, length)
    return {"day": max(0, day),
            "from": _part_of_day(from_s, anchor, length),
            "until": _part_of_day(until_s, anchor, length)}


def span_view(span, anchor, length):
    """The span as the writer reads it: its length in hours and, where the
    clock can say, the day and part of the day at each end."""
    span = span if isinstance(span, dict) else {}
    out = {"hours": round(lived_hours(span), 1)}
    start = _seconds(span.get("from_s"))
    end = _seconds(span.get("until_s"), start)
    if anchor is not None and start is not None:
        out["from"] = {"day": 0, "part": _part_of_day(start, anchor, length)}
        out["until"] = {
            "day": max(0, _day_number(end, anchor, length)
                       - _day_number(start, anchor, length)),
            "part": _part_of_day(end, anchor, length)}
    return out


def _text(value):
    return " ".join(str(value or "").split())


def _route_failures():
    """The reasons a stretch never got where it meant to be: its row's
    `room` is where the mind stood -- or as far along the way as it got --
    and the place it was going is `meant`, or, on a log written before that
    field, its own `where_text`. The executor's own set (`world/
    skip_itinerary.ROUTE_REASONS`), and its three way-reasons where it names
    none."""
    from world import skip_itinerary as itin
    return tuple(getattr(itin, "ROUTE_REASONS", None)
                 or (itin.REASON_NO_ROUTE, itin.REASON_SHUT_WAY, itin.REASON_TOO_FAR))


def _things(value):
    """`missing` as the mind's own words, in order, each once."""
    out = []
    for item in value if isinstance(value, (list, tuple)) else ([value] if value else []):
        text = _text(item)
        if text and text not in out:
            out.append(text)
    return out


def listed(items, language=None):
    """Words named one after another by the pack's own list: its `join`
    (`compositor.join`, "{first} and {last}" / ", and {last}") and its
    separator (`skip_record_list_separator`)."""
    from language_runtime import compositor_text, compositor_value
    items = [str(item) for item in items if str(item or "").strip()]
    if len(items) <= 1:
        return "".join(items)
    join = compositor_value("join", language)
    if len(items) == 2:
        return str(join["two"]).format(first=items[0], last=items[1])
    separator = compositor_text(RECORD_WORDS["list_separator"], language)
    return separator.join(items[:-1]) + str(join["many"]).format(last=items[-1])


def how_it_went(name, outcome, reason=None, *, missing=(), meant="", language=None):
    """THE OUTCOME IN WORDS (`RECORD_WORDS`, `FAILURE_WORDS`: the pack's
    templates): `done` says the mind did it and the record holds no more of
    how it turned out; `not_known` that the mind did it but does not know
    what came of it; `failed` that it did not come off and why -- for `not_held` the things
    that were not to hand, for a way that failed the place it was going
    (`meant`). "" where the pack has no words for it."""
    from language_runtime import LanguagePackError, compositor_text
    if outcome == "done":
        key = RECORD_WORDS["done"]
    elif outcome != "failed":
        key = RECORD_WORDS["not_known"]
    elif reason in FAILURE_WORDS:
        plain, named = FAILURE_WORDS[reason]
        key = named if (missing if reason == "not_held" else meant) else plain
    else:
        key = RECORD_WORDS["failed"]
    try:
        return compositor_text(key, language, name=name,
                               missing=listed(missing, language), meant=meant)
    except LanguagePackError as exc:
        logger.info("skip memory: no words for %s (%s)", key, str(exc)[:200])
        return ""


def record_rows(log, *, span_from, anchor, length, name="", room_names=None,
                language=None):
    """The writer's `record`: one row per stretch of THIS mind's LOG, read
    through `LOG_FIELDS` alone. `n` is the stretch's place in the log, which
    is how a memory names the rows it is made from (`rows`) and so how it is
    dated. A row carries only what it has: no empty `with`, no `weather` the
    log did not record.

    WHAT IT SET ABOUT, AND HOW IT WENT. A row's `doing` is the mind's own
    declaration -- what it set about -- so the record calls it `set_about`,
    never `did`: a stretch that failed was not done. `how_it_went` says the
    outcome in the pack's words (`how_it_went`, which needs the mind's
    `name`; a caller that gives none gets the codes alone), and the bare
    `reason` code goes no further. Where a stretch never got where it was
    going, `where` is where the mind stood, by its room's name
    (`room_names`), and the words name the place it meant: the row's own
    words for a place it never reached are not where it was."""
    from world.spatial import room_display_name
    route_failures = _route_failures()
    room_names = room_names or {}
    out = []
    for n, raw in enumerate(log if isinstance(log, list) else []):
        if not isinstance(raw, dict):
            continue
        entry = {key: raw.get(key) for key in LOG_FIELDS}
        start = _seconds(entry["from_s"], span_from)
        row = {"n": n,
               "when": when_of(start, _seconds(entry["until_s"], start),
                               span_from, anchor, length)}
        outcome = entry["outcome"] if entry["outcome"] in OUTCOMES else "not_known"
        reason = _text(entry["reason"]) if outcome == "failed" else ""
        where = _text(entry["where_text"]) or _text(entry["away"])
        meant = ""
        if reason in route_failures:
            # A row that carries `meant` says where the body was in its
            # `where_text`; one written before the field holds the place it
            # meant there.
            meant = _text(entry["meant"] if "meant" in raw else entry["where_text"])
            room = _text(entry["room"])
            where = (_text(room_names.get(room)) or room_display_name(None, room)
                     if room else _text(entry["away"]))
            if meant and meant.casefold() == where.casefold():
                meant = ""
        if where:
            row["where"] = where
        set_about = _text(entry["doing"])
        if set_about:
            row["set_about"] = set_about
        if entry["asleep"] in (True, 1):
            row["asleep"] = True
        seen = []
        for other in entry["seen"] if isinstance(entry["seen"], list) else []:
            if not isinstance(other, dict):
                continue
            other = {key: _text(other.get(key)) for key in SEEN_FIELDS}
            if other["who"]:
                seen.append({key: other[key] for key in SEEN_FIELDS if other[key]})
        if seen:
            row["with"] = seen
        weather = _text(entry["weather"])
        if weather:
            row["weather"] = weather
        row["outcome"] = outcome
        if name:
            words = how_it_went(name, outcome, reason or None,
                                missing=_things(entry["missing"]), meant=meant,
                                language=language)
            if words:
                row["how_it_went"] = words
        out.append(row)
    return out


def record_text(record):
    """The record as plain text: the moment recall is asked about, the way a
    character call's view is (`build_character_memory_context`)."""
    lines = []
    for row in record or []:
        parts = [row.get("where") or "", row.get("set_about") or ""]
        for other in row.get("with") or []:
            parts.append(" ".join(v for v in (other.get("who"), other.get("doing")) if v))
        if row.get("weather"):
            parts.append(row["weather"])
        lines.append(" -- ".join(p for p in parts if p))
    return "\n".join(line for line in lines if line)


# ---------------------------------------------------------------------------
# The card and the memory, the mind's own.
# ---------------------------------------------------------------------------

def card_of(sheet):
    """`who`: the mind's card as the writer reads it (`CARD_FIELDS`)."""
    from story.character_schema import (character_name,
                                        character_private_history,
                                        character_psychology,
                                        character_public_history,
                                        character_voice)
    sheet = sheet if isinstance(sheet, dict) else {}
    who = {
        "name": character_name(sheet),
        "psychology": character_psychology(sheet),
        "voice": character_voice(sheet),
        "public_history": character_public_history(sheet),
        "private_history": [
            _text(entry.get("content")) for entry in character_private_history(sheet)
            if isinstance(entry, dict) and _text(entry.get("content"))],
    }
    return {key: who[key] for key in CARD_FIELDS if who[key] not in ("", [], {}, None)}


def _person(sheet):
    """`{name, drive, values}`: the mind the decision model picks recalled
    memories FOR, read from the card the way the character call reads it."""
    from story.character_schema import character_name, character_psychology
    psychology = character_psychology(sheet if isinstance(sheet, dict) else {})
    drive = psychology.get("drive")
    drive = _text(drive.get("essence")) if isinstance(drive, dict) else _text(drive)
    values = psychology.get("values")
    values = list(values) if isinstance(values, (list, tuple)) else ([values] if values else [])
    return {"name": character_name(sheet if isinstance(sheet, dict) else {}),
            "drive": drive, "values": values}


def _without_handles(value):
    """A memory packet with every host handle taken out (`_PACKET_HANDLES`)."""
    if isinstance(value, dict):
        return {key: _without_handles(item) for key, item in value.items()
                if key not in _PACKET_HANDLES}
    if isinstance(value, list):
        return [_without_handles(item) for item in value]
    return value


def memory_packet(chat_id, char_id, turn_idx, sheet, active_state, record, *,
                  language=None):
    """`(memory, which)`: what the mind remembers from BEFORE the skip beat.

    "full": the packet its own character call would be handed at that beat
    (`build_character_memory_context` at `turn_idx`, so nothing the beat
    itself committed -- the far end included -- and nothing after it), the
    record standing in for the view as the moment recall is asked about.
    "recent": where that cannot be built out of band (an embeddings or
    decision provider that fails it), the recent window alone, every row of
    `RECENT_TURNS` turns, as the character call's own recent lane reads it.
    Either way, the mind's own rows only: both are read through
    `visible_memory_rows`, the recall firewall."""
    try:
        packet = build_character_memory_context(
            chat_id, char_id, turn_idx, record_text(record), active_state or {},
            bank=memory_bank_cache(), person=_person(sheet), language=language)
        return _without_handles(packet), "full"
    except Exception as exc:  # noqa: BLE001 -- the recent window stands in
        logger.info("skip memory: full packet not built for char %s (%s); "
                    "the recent window stands in", char_id, str(exc)[:200])
    rows = recent_memory_buffer(chat_id, char_id, turn_idx, turns=RECENT_TURNS,
                                limit=None)
    clock = MemoryClock(chat_id, char_id, turn_idx)
    return _without_handles(
        {"recent_memories": [_with_reading(m, clock) for m in rows]}), "recent"


def writer_payload(who, memory, record, span):
    """The writer's whole input (`WRITER_PAYLOAD_KEYS`), and its only door."""
    return {"who": who, "memory": memory, "record": record, "span": span}


# ---------------------------------------------------------------------------
# The writer.
# ---------------------------------------------------------------------------

def writer_system(name, count, language=None, *, rewrite=False):
    """The writer's card (`prompts.skip_memory`), its name and count filled;
    with `rewrite`, the rewrite pass (`prompts.skip_memory_rewrite`) under it,
    one sheet with one policy."""
    if rewrite:
        lang = current_language_id.get() if language is None else language
        text = apply_prompt_policy(
            get_prompt_body("skip_memory", lang).rstrip() + "\n\n"
            + get_prompt_body("skip_memory_rewrite", lang), lang, "skip_memory")
    else:
        text = get_prompt("skip_memory", language)
    return text.replace("{count}", str(int(count))).replace("{name}", str(name))


def _clamp(value, lo, hi, default=0.0):
    number = _seconds(value, default)
    return max(lo, min(hi, number))


def _index(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def episodes_of(raw):
    """The usable memories in one writer answer, in its order. A memory with
    no text is not one; every other field is read leniently and clamped."""
    from llm.llm_quality import strict_json_parse
    parsed = None
    try:
        parsed = strict_json_parse(raw)
    except Exception:  # noqa: BLE001 -- the span salvage below, then nothing
        match = re.search(r"\{.*\}", str(raw or ""), re.S)
        if match:
            try:
                parsed = json.loads(re.sub(r",\s*([}\]])", r"\1", match.group(0)))
            except (TypeError, ValueError):
                parsed = None
    found = parsed.get("episodes") if isinstance(parsed, dict) else None
    out = []
    for entry in found if isinstance(found, list) else []:
        if not isinstance(entry, dict):
            continue
        memory = _text(entry.get("memory"))
        if not memory:
            continue
        rows = entry.get("rows")
        out.append({
            "index": _index(entry.get("index")),
            "rows": [i for i in (_index(r) for r in (rows if isinstance(rows, list) else []))
                     if i is not None],
            "when": _text(entry.get("when")),
            "where": _text(entry.get("where")),
            "memory": memory,
            "consequence": _text(entry.get("consequence")),
            "valence": _clamp(entry.get("valence"), -1.0, 1.0),
            "arousal": _clamp(entry.get("arousal"), 0.0, 1.0),
        })
    return out


def write_episodes(name, count, payload, *, language=None):
    """The writer's memories for one mind, at most `count`: one call, asked
    once more (`SKIP_MEMORY_ATTEMPTS`) when its answer holds none."""
    system = writer_system(name, count, language)
    user = json.dumps(payload, ensure_ascii=False)
    for _attempt in range(SKIP_MEMORY_ATTEMPTS):
        raw = chat_complete(SKIP_MEMORY_ROLE, system, user, json_mode=True,
                            max_tokens=SKIP_MEMORY_MAX_TOKENS)
        found = episodes_of(raw)
        if found:
            return found[:max(0, int(count))]
    return []


def rewrite_episodes(name, count, payload, flagged, *, language=None):
    """ONE rewrite call for every flagged memory of one mind. `flagged` is
    `{index: (episode, flags)}`; the answer is `{index: [candidates]}`, every
    memory the writer returned under that index, in its order -- a writer may
    answer one index twice, and each is a candidate rather than an error."""
    work = [{"index": index, "episode": _as_written(episode),
             "flags": [_flag_for_writer(flag) for flag in flags]}
            for index, (episode, flags) in sorted(flagged.items())]
    user = json.dumps({**payload, "rewrite": work}, ensure_ascii=False)
    raw = chat_complete(SKIP_MEMORY_ROLE, writer_system(name, count, language, rewrite=True),
                        user, json_mode=True, max_tokens=SKIP_MEMORY_MAX_TOKENS)
    out = {}
    order = iter(sorted(flagged))
    for episode in episodes_of(raw):
        # BY KEY, and by place only for an answer that gave none: the n-th
        # unkeyed memory is the n-th one asked for.
        index = episode["index"] if episode["index"] is not None else next(order, None)
        if index in flagged:
            out.setdefault(index, []).append(episode)
    return out


def _as_written(episode):
    return {key: episode[key] for key in ("rows", "when", "where", "memory",
                                          "consequence", "valence", "arousal")}


def _flag_for_writer(flag):
    """A flag as the rewrite card names it: `kind`, and `said` and `in`
    where it has them."""
    return {key: flag[key] for key in ("kind", "said", "in") if flag.get(key)}


# ---------------------------------------------------------------------------
# The floor: numbers, a closed form.
# ---------------------------------------------------------------------------

#: A clock reading written with a colon: hours and minutes.
_CLOCK = re.compile(r"(?<![\d:.])(\d{1,2}):(\d{2})(?![\d:])")
#: A numeral: digits, thousands grouped by commas, a decimal part.
_NUMERAL = re.compile(r"(?<![\d.,])\d+(?:,\d{3})*(?:\.\d+)?(?![\d])")


def _reading(value):
    value = float(value)
    return ("n", int(value) if value.is_integer() else round(value, 6))


def _digit_mentions(text):
    """`[(said, readings)]` for every numeral in `text`. A colon reading is a
    time; a bare three- or four-digit run that is a valid hour and minute is
    ALSO read as one ("0315" is quarter past three, and 315)."""
    text = unicodedata.normalize("NFKC", str(text or ""))
    out, taken = [], []
    for match in _CLOCK.finditer(text):
        hour, minute = int(match.group(1)), int(match.group(2))
        if hour < 24 and minute < 60:
            out.append((match.group(0), {("t", hour * 60 + minute)}))
            taken.append(match.span())
    for match in _NUMERAL.finditer(text):
        if any(a <= match.start() < b for a, b in taken):
            continue
        said = match.group(0)
        readings = {_reading(said.replace(",", ""))}
        if said.isdigit() and len(said) in (3, 4):
            hour, minute = int(said[:-2]), int(said[-2:])
            if hour < 24 and minute < 60:
                readings.add(("t", hour * 60 + minute))
        out.append((said, readings))
    return out


def _number_grammar(language=None):
    words = {str(w).casefold(): float(v)
             for w, v in linguistic("mind.skip_memories", "_NUMBER_WORDS", language)}
    scales = {str(w).casefold(): (float(v), str(k))
              for w, v, k in linguistic("mind.skip_memories", "_NUMBER_SCALES", language)}
    run = linguistic("mind.skip_memories", "_NUMBER_RUN", language)
    token = re.compile("|".join(re.escape(w) for w in sorted(
        list(words) + list(scales), key=len, reverse=True)), re.I)
    return words, scales, run, token


def _compose(tokens, words, scales):
    """The numbers one run of number words says, in order, as
    `(value, has_unit, opens_on_a_big_scale)`. One grammar for every pack:
    a unit adds to the group it is in (twenty-six; 二, 十, 六); a small scale
    multiplies the group before it (three HUNDRED; 二 十); a big scale closes
    everything before it into one multiple (two THOUSAND; 一 万). A unit that
    cannot follow the one before it -- two units, or a unit after a group
    that is not a whole ten -- starts a new number: two-three is two numbers,
    never five."""
    out = []
    total = section = number = 0.0
    has_unit = opens_big = False
    started = False

    def close():
        nonlocal total, section, number, has_unit, opens_big, started
        if started:
            out.append((total + section + number, has_unit, opens_big))
        total = section = number = 0.0
        has_unit = opens_big = started = False

    for token in tokens:
        if token in words:
            unit = words[token]
            if started and number and not (number >= 20 and number % 10 == 0 and unit < 10):
                close()
            number += unit
            has_unit = True
        else:
            value, kind = scales[token]
            if not started and kind == "big":
                opens_big = True
            if kind == "big":
                total += max(section + number, 1.0) * value
                section = number = 0.0
            else:
                section += max(number, 1.0) * value
                number = 0.0
        started = True
    close()
    return out


def _word_mentions(text, language=None):
    """`[(said, value, is_a_figure)]` for every run of number words. A run is
    a FIGURE -- what the floor holds a memory to -- when it says a unit (a
    bare magnitude, "a hundred" or 百, is an order of size said in passing),
    does not open on a big scale (万一 is "in case", never ten thousand and
    one), and comes to 2 or more ("one" is as often the indefinite as a
    count)."""
    words, scales, run, token = _number_grammar(language)
    out = []
    for match in run.finditer(str(text or "")):
        said = match.group(0)
        tokens = [t.casefold() for t in token.findall(said)]
        for value, has_unit, opens_big in _compose(tokens, words, scales):
            out.append((said, value, has_unit and not opens_big and value >= 2))
    return out


def number_support(value, language=None):
    """Every reading of every number a source holds: the record, `memory`,
    the card, the span. Generous on purpose -- a source's every number word,
    the hour and minute of every time -- because support only ever widens
    what a memory may say. A record row's own place (`n`) is not a number
    the mind was given."""
    readings = set()

    def walk(item, key=None):
        if isinstance(item, dict):
            for k, v in item.items():
                walk(v, k)
        elif isinstance(item, list):
            for v in item:
                walk(v, key)
        elif isinstance(item, bool) or item is None:
            return
        elif isinstance(item, (int, float)):
            if key != "n" and math.isfinite(float(item)):
                readings.add(_reading(item))
        else:
            text = str(item)
            for _said, found in _digit_mentions(text):
                readings.update(found)
                for kind, value in list(found):
                    if kind == "t":
                        hour, minute = divmod(value, 60)
                        readings.update({("n", hour), ("n", hour % 12 or 12),
                                         ("n", minute)})
            for _said, number, _figure in _word_mentions(text, language):
                readings.add(_reading(number))
    walk(value)
    return readings


def sentences(text, language=None):
    """The sentences of `text`, each with its own closing mark. A spaced
    script's stop ends a sentence only before a space or the end, and never
    after one of the pack's abbreviations ("Dr."); an unspaced script's stop
    ends it where it stands. The stops and the abbreviations are the pack's
    (`story.scene._SENTENCE_ENDS`, `agents.common._SENTENCE_ABBREVIATIONS`)."""
    text = str(text or "").strip()
    if not text:
        return []
    ends = str(linguistic("story.scene", "_SENTENCE_ENDS", language))
    abbreviations = {str(a).casefold() for a in linguistic(
        "agents.common", "_SENTENCE_ABBREVIATIONS", language)}
    spaced = "".join(ch for ch in ends if ord(ch) < 128)
    unspaced = "".join(ch for ch in ends if ord(ch) >= 128)
    closers = "[" + re.escape(_CLOSERS) + "]*"
    alternatives = []
    if spaced:
        alternatives.append("[" + re.escape(spaced) + "]+" + closers + r"(?=\s|$)")
    if unspaced:
        alternatives.append("[" + re.escape(unspaced) + "]+" + closers)
    if not alternatives:
        return [text]
    pieces, start = [], 0
    for match in re.finditer("|".join(alternatives), text):
        pieces.append(text[start:match.end()].strip())
        start = match.end()
    pieces.append(text[start:].strip())
    out, held = [], False
    for piece in (p for p in pieces if p):
        if held:
            out[-1] = out[-1] + " " + piece
        else:
            out.append(piece)
        # A piece ending on an abbreviation's stop ("Dr.") runs on into the next.
        last = piece.split()[-1].strip(_CLOSERS)
        held = last.endswith(".") and last[:-1].casefold() in abbreviations
    return out


def unsupported_numbers(text, support, language=None):
    """THE FLOOR: `[{"said", "in"}]` for every figure `text` states that no
    reading in `support` holds -- a numeral, a clock time or a counted number
    word -- with the sentence it stands in. A numeral is supported when any
    of its readings is held, so "0315" is held by a record saying 3:15 and by
    one saying 0315, and a time by its own hour and minute alone, never by
    its hour."""
    out = []
    for sentence in sentences(text, language):
        for said, readings in _digit_mentions(sentence):
            if not readings & support:
                out.append({"said": said, "in": sentence})
        for said, value, figure in _word_mentions(sentence, language):
            if figure and _reading(value) not in support:
                out.append({"said": said, "in": sentence})
    return out


# ---------------------------------------------------------------------------
# The decision model: narrow questions, one of each kind per memory.
# ---------------------------------------------------------------------------

#: THE MODEL'S QUESTIONS. Each kind is one narrow question asked of every
#: memory, and the same question asked of each of its sentences to say where
#: (`jev_questions`, the pack's): `(memory question, sentence question, key
#: prefix of a sentence's answer)`. Narrow on purpose: the probe's one broad
#: "find the inventions" flagged none of them in two sets
#: (`DESIGN_THE_CAST_ACROSS_A_SKIP.md` § 2.2). The design's three (§ 4.6):
#:   * `others` -- someone besides the mind speaks or acts beyond what the
#:     record's `with` shows of them. The record shows another person ONLY
#:     there: someone named in the mind's own `set_about` is part of what it
#:     meant to do (the live miss: the yard man "looked at it" in a memory
#:     whose row's own plan wrote "stands over him while he looks at it");
#:   * `outcome` -- the memory tells a row past its `how_it_went`: what did
#:     not come off told as done, or how ANY doing turned out -- every row,
#:     keyed to the words and never to the `failed`/`not_known` codes, since
#:     the `done` words hold nothing of how a doing turned out either (the
#:     coordinator's ruling on the live measurement). A doing told as done is
#:     not a result. The live case: the boatman's failed post-office stretch
#:     written "So I did ... into the box"; the keeper's rotation test given a
#:     drift, a clean mesh, and a night the clockwork "held" past `done` rows;
#:   * `past` -- a detail of the time before the stretch that neither the
#:     mind's memory nor its card holds.
SKIP_MEMORY_QUESTIONS = {
    "others": ("skip_memory_others", "skip_memory_sentence", "s"),
    "outcome": ("skip_memory_outcome", "skip_memory_outcome_sentence", "o"),
    "past": ("skip_memory_past", "skip_memory_past_sentence", "p"),
}

#: WHICH OF THEM ARE ASKED, in this order. Named so the owner can drop one:
#: a kind left out is simply not asked, and its flags never raised. `past`
#: reads the mind's whole memory packet beside the record (`past_state`), so
#: it is the one a live false-positive rate would cut first.
SKIP_MEMORY_CHECKS = ("others", "outcome", "past")

#: The questions that read the mind's past -- its card and its memory, beside
#: the record. The others read the record and the memory being checked alone,
#: so a past `memory` holds never reads to them as something the stretch
#: showed.
_READS_THE_PAST = ("past",)


def _yes(answer):
    return decisions.probability(answer) >= SKIP_MEMORY_JEV_THRESHOLD


def _jev_state(name, record, text):
    return {"name": name, "record": record, "memory": text}


def past_state(name, record, text, before):
    """The `past` question's state: the record and the memory being checked,
    and what the writer had of the time before -- the mind's card (`who`) and
    its memory packet (`remembered`). The mind's own, as the writer's
    payload is; nothing else."""
    before = before if isinstance(before, dict) else {}
    return {"name": name, "who": before.get("who") or {},
            "remembered": before.get("remembered") or {},
            "record": record, "memory": text}


def ask_model(name, record, text, pieces, *, before=None, language=None):
    """`(verdicts, placed)`: for each asked kind (`SKIP_MEMORY_CHECKS`), True
    or False -- None where it could not be asked, which fails open: the floor
    still stands -- and the `pieces` (sentences of `text`) its sentence
    question places it in. A kind's memory question and its sentence
    questions go out in ONE request per state: the decision model answers
    every question of a request on its own, so nothing is lost by asking the
    sentences beside the memory, and a sentence's yes is read only where the
    memory's was."""
    kinds = [kind for kind in SKIP_MEMORY_CHECKS if kind in SKIP_MEMORY_QUESTIONS]
    verdicts, placed = {}, {}
    requests = []
    plain = [kind for kind in kinds if kind not in _READS_THE_PAST]
    if plain:
        requests.append((_jev_state(name, record, text), plain))
    past = [kind for kind in kinds if kind in _READS_THE_PAST]
    if past:
        if before is None:
            verdicts.update({kind: None for kind in past})
        else:
            requests.append((past_state(name, record, text, before), past))
    for state, group in requests:
        questions = {}
        for kind in group:
            whole_key, sentence_key, prefix = SKIP_MEMORY_QUESTIONS[kind]
            whole = jev_question(whole_key, language, name=name)
            if not whole:
                verdicts[kind] = None
                continue
            questions[kind] = {"type": "noul", "instructions": whole}
            for i, piece in enumerate(pieces):
                one = jev_question(sentence_key, language, name=name, sentence=piece)
                if one:
                    questions[f"{prefix}{i}"] = {"type": "noul", "instructions": one}
        if not questions:
            continue
        try:
            answers = decisions.decide(state, questions)
        except Exception as exc:  # noqa: BLE001 -- unasked, never a lost memory
            logger.info("skip memory: decision model not asked (%s)", str(exc)[:200])
            answers = {}
        for kind in group:
            if kind not in questions:
                continue
            if kind not in answers:
                verdicts[kind] = None
                continue
            verdicts[kind] = _yes(answers[kind])
            prefix = SKIP_MEMORY_QUESTIONS[kind][2]
            placed[kind] = [piece for i, piece in enumerate(pieces)
                            if _yes(answers.get(f"{prefix}{i}"))]
    return verdicts, placed


# ---------------------------------------------------------------------------
# The check, the rewrite and the drop.
# ---------------------------------------------------------------------------

def _whole(episode):
    return " ".join(p for p in (episode["memory"], episode["consequence"]) if p)


def flags_of(name, record, episode, support, *, before=None, language=None):
    """`(flags, unasked)`: what one memory went past -- `number` flags from
    the floor, and a flag of each kind the decision model said yes to
    (`SKIP_MEMORY_CHECKS`: `others`, `outcome`, `past`), each naming the
    sentence it stands in where one could be named -- and the kinds that
    could not be asked. `before` is what the writer had of the time before
    the stretch (`who`, `remembered`), which only `past` reads."""
    flags = []
    for part in ("memory", "consequence"):
        for found in unsupported_numbers(episode[part], support, language):
            flags.append({"kind": "number", "said": found["said"],
                          "in": found["in"], "part": part})
    parts = [(part, piece) for part in ("memory", "consequence")
             for piece in sentences(episode[part], language)]
    verdicts, placed = ask_model(name, record, _whole(episode),
                                 [piece for _part, piece in parts],
                                 before=before, language=language)
    for kind in SKIP_MEMORY_CHECKS:
        if not verdicts.get(kind):
            continue
        found = set(placed.get(kind) or ())
        named = [{"kind": kind, "in": piece, "part": part}
                 for part, piece in parts if piece in found]
        flags.extend(named or [{"kind": kind}])
    return flags, [kind for kind in SKIP_MEMORY_CHECKS if verdicts.get(kind) is None]


def drop_flagged(episode, flags, language=None):
    """The memory with every flagged sentence taken out, or None when nothing
    of its own text is left. A flag that names no sentence takes nothing: the
    model said the memory went past the record and could not say where, and
    the floor does not guess."""
    kept = dict(episode)
    for part in ("memory", "consequence"):
        doomed = {flag["in"] for flag in flags
                  if flag.get("part") == part and flag.get("in")}
        if not doomed:
            continue
        text = episode[part]
        pieces = [piece for piece in sentences(text, language) if piece not in doomed]
        joiner = " " if re.search(r"\s", text) else ""
        kept[part] = joiner.join(pieces).strip()
    return kept if kept["memory"] else None


def check_and_mend(name, count, payload, episodes, *, language=None):
    """The two-part check over one mind's memories -- the floor and the
    decision model's questions -- the rewrite of the flagged, and the drop of
    what still fails. Returns `(memories, report)`; the memories keep their
    order, minus any with nothing left. `report["jev"]` is "unavailable" when
    any question could not be asked of any memory, and `unanswered` names
    those kinds."""
    support = number_support({key: payload[key] for key in ("who", "memory", "record", "span")},
                             language)
    record = payload["record"]
    before = {"who": payload["who"], "remembered": payload["memory"]}
    report = {"flagged": {}, "rewritten": [], "dropped_sentences": {},
              "dropped": [], "unlocalized": [], "jev": "asked", "unanswered": []}
    checked = []
    for i, episode in enumerate(episodes):
        flags, unasked = flags_of(name, record, episode, support, before=before,
                                  language=language)
        if unasked:
            report["jev"] = "unavailable"
            report["unanswered"] = sorted(set(report["unanswered"]) | set(unasked))
        checked.append((episode, flags))
    flagged = {i: (episode, flags) for i, (episode, flags) in enumerate(checked) if flags}
    report["flagged"] = {i: [_flag_for_writer(f) for f in flags]
                         for i, (_e, flags) in flagged.items()}
    if not flagged:
        return [episode for episode, _flags in checked], report
    try:
        candidates = rewrite_episodes(name, count, payload, flagged, language=language)
    except Exception as exc:  # noqa: BLE001 -- the drop below still runs
        logger.info("skip memory: rewrite failed for %s (%s)", name, str(exc)[:200])
        candidates = {}
    out = []
    for i, (episode, flags) in enumerate(checked):
        if not flags:
            out.append(episode)
            continue
        best = None
        for candidate in candidates.get(i, []):
            again, _unasked = flags_of(name, record, candidate, support,
                                       before=before, language=language)
            if not again:
                best = (candidate, [])
                break
            if best is None:
                best = (candidate, again)
        if best is None:
            best = (episode, flags)
        else:
            report["rewritten"].append(i)
        chosen, still = best
        if still:
            if any(f["kind"] in SKIP_MEMORY_QUESTIONS and not f.get("in") for f in still):
                report["unlocalized"].append(i)
            gone = sorted({f["in"] for f in still if f.get("in")})
            if gone:
                report["dropped_sentences"][i] = gone
            chosen = drop_flagged(chosen, still, language)
            if chosen is None:
                report["dropped"].append(i)
                continue
        out.append(chosen)
    return out, report


# ---------------------------------------------------------------------------
# The rows.
# ---------------------------------------------------------------------------

def skip_event_key(turn_id, name, n):
    """`skip:{turn_id}:{mind}:{n}` -- the build spec's stable key."""
    return f"{SKIP_ORIGIN_PREFIX}{turn_id}:{name}:{int(n)}"


def is_skip_memory(row):
    """Whether a memory row was written for a skip (`SKIP_ORIGIN_PREFIX`)."""
    try:
        key = row["event_key"]
    except (KeyError, IndexError, TypeError):
        key = getattr(row, "event_key", "")
    return str(key or "").startswith(SKIP_ORIGIN_PREFIX)


def salience_of(episode):
    strength = max(float(episode.get("arousal") or 0.0),
                   abs(float(episode.get("valence") or 0.0)))
    return round(min(SKIP_MEMORY_SALIENCE_CEILING,
                     SKIP_MEMORY_SALIENCE_FLOOR + SKIP_MEMORY_SALIENCE_SPAN * strength), 3)


def occasion_seconds(episode, log, span, position, total):
    """WHEN A MEMORY WAS FORMED, on the story clock: the end of the last
    stretch it is made from (`rows`) -- a memory is kept once its occasion is
    over -- inside the span. A memory naming no stretch of the log takes its
    place in order across the span, as the n-th of `total` occasions."""
    span = span if isinstance(span, dict) else {}
    start = _seconds(span.get("from_s"), 0.0)
    end = _seconds(span.get("until_s"), start)
    ends = []
    for n in episode.get("rows") or []:
        if isinstance(n, int) and 0 <= n < len(log) and isinstance(log[n], dict):
            first = _seconds(log[n].get("from_s"), start)
            ends.append(_seconds(log[n].get("until_s"), first))
    if ends:
        at = max(ends)
    else:
        at = start + (end - start) * (position + 1) / max(1, total)
    return max(start, min(end, at))


def _location(episode, log, room_names):
    """Where the memory happened, as the engine names the place: the room of
    the last stretch it is made from, by the room's name, or the place the
    mind was away at; the writer's own `where` when the log names neither."""
    for n in reversed(episode.get("rows") or []):
        if isinstance(n, int) and 0 <= n < len(log) and isinstance(log[n], dict):
            room = str(log[n].get("room") or "").strip()
            if room:
                return str(room_names.get(room) or room)
            away = _text(log[n].get("away")) or _text(log[n].get("where_text"))
            if away:
                return away
    return episode.get("where") or ""


def _about(episode, log, known):
    """Who the memory had in it, by the engine's names: the people its own
    stretches saw whom this mind knows by name (`memories.about`, host-only;
    a stranger's label is nobody's name)."""
    names = []
    for n in episode.get("rows") or []:
        if isinstance(n, int) and 0 <= n < len(log) and isinstance(log[n], dict):
            for other in log[n].get("seen") or []:
                who = _text(other.get("who")) if isinstance(other, dict) else ""
                if who and who.casefold() in known and who not in names:
                    names.append(who)
    return names


def rows_for(chat_id, char_id, name, turn, episodes, log, span, *,
             room_names=None, known=(), language=None):
    """The memory rows for one mind's checked memories, in order, keyed
    `skip:{turn_id}:{mind}:{n}`: episodic, `witnessed`, at the skip beat's
    index and frame, each dated at its own occasion within the span."""
    label = str((linguistic("mind.skip_memories", "_SKIP_MEMORY_LABELS", language)
                 or {}).get("afterwards") or "").strip()
    known = {str(k).casefold() for k in known or ()}
    rows = []
    for n, episode in enumerate(episodes):
        content = episode["memory"]
        if episode.get("consequence"):
            content = " ".join(p for p in (content, label, episode["consequence"]) if p)
        rows.append({
            "chat_id": chat_id, "char_id": char_id,
            "turn_id": turn["id"], "turn_idx": turn["idx"],
            "frame_id": turn["frame_id"],
            "kind": "episodic", "category": "episode", "provenance": "witnessed",
            "salience": salience_of(episode), "content": content,
            "location": _location(episode, log, room_names or {}),
            "valence": episode["valence"], "arousal": episode["arousal"],
            "encoding_valence": episode["valence"],
            "encoding_arousal": episode["arousal"],
            "confidence": 1.0,
            "event_key": skip_event_key(turn["id"], name, n),
            "encoded_at_seconds": occasion_seconds(episode, log, span, n, len(episodes)),
            "about": _about(episode, log, known),
        })
    return rows


def _skip_rows_of(chat_id, char_id, turn_id):
    return q("SELECT id FROM memories WHERE chat_id=? AND char_id=? AND turn_id=? "
             "AND event_key LIKE ?", (chat_id, char_id, turn_id,
                                      SKIP_ORIGIN_PREFIX + "%"))


def write_rows(chat_id, char_id, turn, variant_id, rows, *, job=None):
    """Write one mind's rows: embedded first, outside the write lock, then in
    ONE transaction that asks whether the job was stopped and whether the beat
    still stands as read (`still_committed`), takes out this mind's earlier
    rows for the beat -- a rerun replaces, never duplicates -- writes these,
    and carries them into every checkpoint taken after the beat
    (`persist.checkpoints.carry_memories_forward`). Returns how many it wrote,
    or the reason it wrote none."""
    from core import jobs
    from persist.checkpoints import carry_memories_forward

    prepared = prepare_memories_batch(rows) if rows else {"prepared": [], "embedded": None}
    with transaction():
        if jobs.is_cancelled(job):
            return "cancelled"
        if not still_committed(turn["id"], turn["idx"], variant_id):
            return "superseded"
        for row in _skip_rows_of(chat_id, char_id, turn["id"]):
            delete_memory(row["id"])
        written = add_memories_batch(prepared_batch=prepared) if rows else []

        def mine(entry):
            return (entry.get("char_id") == char_id and entry.get("turn_id") == turn["id"]
                    and str(entry.get("event_key") or "").startswith(SKIP_ORIGIN_PREFIX))

        # Only when the next beat has begun: the dump reads the whole bank,
        # and this transaction holds the write lock.
        if q("SELECT 1 FROM checkpoints WHERE chat_id=? AND turn_idx>? LIMIT 1",
             (chat_id, turn["idx"]), one=True):
            entries = [m for m in dump_chat_memories(chat_id, inline_vectors=False)
                       if mine(m)]
            carry_memories_forward(chat_id, turn["idx"], mine, entries)
    return len(written)


# ---------------------------------------------------------------------------
# The job.
# ---------------------------------------------------------------------------

def _cast_row(chat_id, char_id, frame_id):
    """One cast row, dormant ones included -- a skip asks the away cast too --
    with the frame's own state where the frame has one (`active_cast`'s
    rule)."""
    return q("SELECT ch.id, ch.name, COALESCE(cc.sheet, ch.sheet) AS sheet, "
             "COALESCE(ccf.state, cc.state) AS cstate "
             "FROM chat_chars cc JOIN characters ch ON ch.id=cc.char_id "
             "LEFT JOIN chat_char_frames ccf ON ccf.chat_id=cc.chat_id "
             "AND ccf.char_id=cc.char_id AND ccf.frame_id IS ? "
             "WHERE cc.chat_id=? AND cc.char_id=?",
             (frame_id, chat_id, char_id), one=True)


def remember_one(chat_id, turn, variant_id, name, entry, span, *, char_id,
                 count, anchor, length, room_names, known, job=None,
                 language=None):
    """One mind's whole pass: its record, card and memory; the writer; the
    check, the rewrite and the drop; the rows. Returns what it did."""
    from core import jobs
    from story.scene import sheet_state

    row = _cast_row(chat_id, char_id, turn["frame_id"])
    if row is None:
        return {"status": "not in the cast"}
    sheet, active, _stance = sheet_state(row)
    log = [r for r in entry.get("log") or []] if isinstance(entry.get("log"), list) else []
    record = record_rows(log, span_from=_seconds(span.get("from_s"), 0.0),
                         anchor=anchor, length=length, name=name,
                         room_names=room_names, language=language)
    memory, which = memory_packet(chat_id, char_id, turn["idx"], sheet, active,
                                  record, language=language)
    payload = writer_payload(card_of(sheet), memory, record,
                             span_view(span, anchor, length))
    if jobs.is_cancelled(job):
        return {"status": "cancelled", "packet": which}
    episodes = write_episodes(name, count, payload, language=language)
    if not episodes:
        return {"status": "the writer returned no memory", "packet": which}
    kept, report = check_and_mend(name, count, payload, episodes, language=language)
    rows = rows_for(chat_id, char_id, name, turn, kept, log, span,
                    room_names=room_names, known=known, language=language)
    written = write_rows(chat_id, char_id, turn, variant_id, rows, job=job)
    return {"status": "written" if isinstance(written, int) else written,
            "written": written if isinstance(written, int) else 0,
            "asked": len(episodes), "packet": which, **report}


def run_skip_memories(chat_id, turn_id, *, job=None, language=None,
                      workers=SKIP_MEMORY_WORKERS):
    """THE JOB: every mind's memories of the skip the beat `turn_id` passed
    over, from its committed `skip_lives` output. Returns `{mind: what was
    done}`; a failure for one mind is recorded on it and never stops another.

    A job a restore SPARES (`core.jobs.cancel_from`: the rewind kept this
    beat) goes on writing: everything it reads is the kept beat's own output
    and the bank from before it, and nothing else will write these rows -- the
    key is per beat, so no later commit joins this job. A job a restore
    STOPS writes nothing more (`write_rows` asks inside its transaction)."""
    from story.scene import all_cast_name_to_id

    turn = q("SELECT id, idx, frame_id FROM turns WHERE id=? AND chat_id=?",
             (turn_id, chat_id), one=True)
    if not turn:
        return {}
    turn = {"id": turn["id"], "idx": turn["idx"], "frame_id": turn["frame_id"]}
    got = committed_output(turn_id)
    if not got:
        return {}
    variant_id, output = got
    minds = minds_to_remember(output)
    if not minds:
        return {}
    span = output.get("span") if isinstance(output.get("span"), dict) else {}
    count = memory_count(span)
    anchor, length = day_reader(chat_id)
    cast = all_cast_name_to_id(chat_id)
    scene = wget(chat_id, "scene", {}) or {}
    from world.spatial import room_display_name
    room_names = {str(rid): room_display_name(room, rid)
                  for rid, room in (scene.get("rooms") or {}).items()
                  if isinstance(room, dict)}
    known_map = wget(chat_id, "known", {}) or {}

    def one(name, entry):
        char_id = cast.get(name)
        if char_id is None:
            return {"status": "not in the cast"}
        try:
            return remember_one(
                chat_id, turn, variant_id, name, entry, span, char_id=char_id,
                count=count, anchor=anchor, length=length, room_names=room_names,
                known=known_map.get(name) or [], job=job, language=language)
        except Exception as exc:  # noqa: BLE001 -- one mind never stops another
            logger.info("skip memory failed out of band: chat=%s turn=%s mind=%s "
                        "error=%s", chat_id, turn_id, name, str(exc)[:300])
            return {"status": "failed", "error": "%s: %s" % (type(exc).__name__,
                                                             str(exc)[:300])}

    results = {}
    with ThreadPoolExecutor(max_workers=max(1, min(int(workers), len(minds)))) as pool:
        futures = [(name, pool.submit(copy_context().run, one, name, entry))
                   for name, entry in minds]
        for name, future in futures:
            results[name] = future.result()
    logger.info("skip memories: chat=%s turn=%s %s", chat_id, turn_id, json.dumps(
        {name: summary_of(r) for name, r in results.items()},
        ensure_ascii=False, default=str)[:SKIP_MEMORY_LOG_CHARS])
    return results


def summary_of(result):
    """What one mind's pass leaves in the log line: what was written, whether
    the decision model was asked (`jev`, and the kinds it could not be asked),
    the flags raised by kind, the memories rewritten and dropped, and how many
    sentences went -- so a live run says whether its check ran and what it
    caught."""
    out = {k: v for k, v in (result or {}).items()
           if k in ("status", "written", "asked", "packet", "jev", "unanswered",
                    "rewritten", "dropped")}
    kinds = {}
    for flags in ((result or {}).get("flagged") or {}).values():
        for flag in flags:
            kinds[flag.get("kind")] = kinds.get(flag.get("kind"), 0) + 1
    if kinds:
        out["flags"] = kinds
    dropped = (result or {}).get("dropped_sentences") or {}
    if dropped:
        out["dropped_sentences"] = sum(len(v) for v in dropped.values())
    return out


__all__ = [
    "CARD_FIELDS", "FAILURE_WORDS", "LOG_FIELDS", "OUTCOMES", "RECORD_WORDS",
    "SEEN_FIELDS", "SKIP_HOURS_PER_MEMORY", "SKIP_LIVES_STEP",
    "SKIP_MEMORIES_MAX", "SKIP_MEMORIES_MIN", "SKIP_MEMORY_ATTEMPTS",
    "SKIP_MEMORY_CHECKS", "SKIP_MEMORY_JEV_THRESHOLD", "SKIP_MEMORY_LOG_CHARS",
    "SKIP_MEMORY_MAX_TOKENS", "SKIP_MEMORY_QUESTIONS", "SKIP_MEMORY_ROLE",
    "SKIP_MEMORY_SALIENCE_CEILING", "SKIP_MEMORY_SALIENCE_FLOOR",
    "SKIP_MEMORY_SALIENCE_SPAN", "SKIP_MEMORY_WORKERS", "SKIP_ORIGIN_PREFIX",
    "WRITER_PAYLOAD_KEYS", "ask_model", "card_of", "check_and_mend",
    "committed_output", "day_reader", "drop_flagged", "episodes_of",
    "flags_of", "how_it_went", "is_skip_memory", "listed", "lived_hours",
    "memory_count", "memory_packet", "minds_to_remember", "number_support",
    "occasion_seconds", "past_state", "record_rows", "record_text",
    "remember_one", "rewrite_episodes", "rows_for", "run_skip_memories",
    "salience_of", "sentences", "skip_event_key", "span_view",
    "still_committed", "summary_of", "unsupported_numbers", "when_of",
    "write_episodes", "write_rows", "writer_payload", "writer_system",
]
