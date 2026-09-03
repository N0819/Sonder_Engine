"""The story bible: the Writers' Room's narrative memory, folded from the
thread, typed state first, particulars always.

WHY IT EXISTS (plan § 6 item 7, measured 2026-09-03): the Story Planner
reads the last thirty lines of the room thread and nothing older. Its typed
state -- mandates, packages, status, needs -- IS a compaction of intent,
but only of the part that has a typed home. What rolled off the window was
exactly what a writer regrets losing: what the player asked for and in
what words, what the room promised, what it planted meaning to pay off,
what it decided against and why. The bible holds that, and only that.

THREE RULES.

* TYPED STATE FIRST. Anything that can be a mandate, a package truth,
  question or clock, a planning need or a lore entry goes THERE; the bible
  holds a pointer. Every entry carries `source` refs (message ids, a package
  uid, a lore id, a mandate, a need, a proposal, a turn) and code REFUSES an
  entry with no source or one that names something that does not exist.
* SECTIONS, NOT A SUMMARY. `wants` (what the player asked for, in their
  words, and their hard nos; a reversal keeps both lines, the old one marked
  superseded), `promises` (what the room said it would do and has not),
  `setups` (planted and unpaid, with where the evidence lives; an unpaid
  setup never falls off), `open_loops` (questions the story raised and what
  would answer them), `paid` (payoffs landed, one line each), `decided`
  (decisions and rejected alternatives with the reason), `voice` (genre,
  tone, the creativity dial as the player stated it).
* PARTICULARS, NOT GISTS. An entry is a sentence with names, turns, room ids
  and the player's phrase. Same rule as character memory: detailed and
  personal, never a mood.

WHEN IT FOLDS. Out of band (`core/jobs.py`, keyed `room_bible`), never in
a reply's wall clock: when the thread holds `BIBLE_FOLD_BATCH` lines older
than the Planner's window that no fold has read, one bounded model call on
the Planner's role (`prompts/bible_fold`) is asked what in those lines a
writer would regret forgetting, under the section schema. A publish or a
resolve adds its line deterministically, with no call. A line leaves the
Planner's window only after the fold (`agents/story_planner._conversation`
shows every unfolded line up to a hard cap).

AUTHOR MEMORY, NEVER MIND MEMORY. The bible is served to the Planner and
the Dramaturge in their system block and to no mind; it is not a channel.
The row rides the frame-scoped `room_bible` world key.
"""

from __future__ import annotations

import hashlib
import json
import time

from core.db import q, wget_for_frame, wset_for_frame

BIBLE_KEY = "room_bible"
BIBLE_SECTIONS = ("wants", "promises", "setups", "open_loops", "paid",
                  "decided", "voice")
#: Entries kept per section; past it the oldest entry that is not an unpaid
#: setup falls off. Unpaid setups are never dropped by the cap.
BIBLE_ENTRIES_PER_SECTION = 24
#: One entry's sentence.
BIBLE_ENTRY_CHARS = 400
#: The rendered block shown in the agents' system prompt.
BIBLE_CHARS_SHOWN = 6000
#: Unfolded lines beyond the Planner's window before a fold is queued.
BIBLE_FOLD_BATCH = 12
#: Lines one fold reads at most (a long-neglected thread folds in passes).
BIBLE_FOLD_LINES = 40
#: The fold call's output budget. One number across the room (2026-09-04).
BIBLE_FOLD_MAX_TOKENS = 20_000
#: The job key (`core/jobs.py`), deduped per chat.
BIBLE_JOB_KEY = "room_bible"
#: The fold runs on the Planner's role.
BIBLE_ROLE = "story_planner"


def _text(value, limit=BIBLE_ENTRY_CHARS):
    return " ".join(str(value or "").split())[:limit]


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

def source_exists(cid, frame_id, ref):
    """Whether a source ref names something the story holds. Refs:
    ``msg:<id>`` (a room line), ``turn:<idx>`` (a beat), ``lore:<id>``,
    ``plot:...`` (a package uid), ``mandate_...``, ``need_...``,
    ``prop_...``. Anything else is not a source."""
    ref = str(ref or "").strip()
    if not ref:
        return False
    try:
        if ref.startswith("msg:"):
            return q("SELECT 1 FROM room_messages WHERE id=? AND chat_id=?",
                     (int(ref[4:]), int(cid)), one=True) is not None
        if ref.startswith("turn:"):
            return q("SELECT 1 FROM turns WHERE chat_id=? AND idx=?",
                     (int(cid), int(ref[5:])), one=True) is not None
        if ref.startswith("lore:"):
            return q("SELECT 1 FROM lore_entries WHERE id=?", (int(ref[5:]),),
                     one=True) is not None
        if ref.startswith("plot:"):
            from story.plot_packages import packages
            return ref in packages(cid, frame_id)
        if ref.startswith("mandate_"):
            from story.room_conversation import mandates
            return any(m["uid"] == ref for m in mandates(cid, frame_id))
        if ref.startswith("need_"):
            from world.planning_needs import planning_needs
            return any(n["uid"] == ref for n in planning_needs(cid, frame_id))
        if ref.startswith("prop_"):
            from story.room_proposals import get_proposal
            return get_proposal(cid, frame_id, ref) is not None
    except (TypeError, ValueError):
        return False
    return False


# ---------------------------------------------------------------------------
# The row
# ---------------------------------------------------------------------------

def _normalize_entry(entry):
    entry = entry if isinstance(entry, dict) else {}
    text = _text(entry.get("text"))
    sources = [str(s) for s in (entry.get("source") or []) if str(s or "").strip()]
    return {
        "uid": str(entry.get("uid") or "") or _entry_uid(entry.get("section"), text),
        "section": str(entry.get("section") or ""),
        "text": text,
        "source": sources[:8],
        "since_turn": int(entry.get("since_turn") or 0),
        "filed_at": float(entry.get("filed_at") or 0.0),
        "paid": bool(entry.get("paid")),
        "superseded_by": (str(entry["superseded_by"])
                          if entry.get("superseded_by") else None),
    }


def _entry_uid(section, text):
    material = "%s|%s" % (section, _text(text).casefold())
    return "bib_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:10]


def _row(cid, frame_id):
    stored = wget_for_frame(cid, BIBLE_KEY, frame_id, {}) or {}
    if not isinstance(stored, dict):
        stored = {}
    sections = {}
    raw = stored.get("sections") if isinstance(stored.get("sections"), dict) else {}
    for name in BIBLE_SECTIONS:
        entries = []
        for e in raw.get(name) or []:
            n = _normalize_entry(e)
            if n["text"] and n["source"]:
                n["section"] = name
                entries.append(n)
        sections[name] = entries
    return {"sections": sections,
            "folded_through": int(stored.get("folded_through") or 0),
            "folds": int(stored.get("folds") or 0),
            "updated_turn": int(stored.get("updated_turn") or 0)}


def _save(cid, frame_id, row):
    wset_for_frame(cid, BIBLE_KEY, row, frame_id)
    return row


def bible(cid, frame_id=None):
    return _row(cid, frame_id)


def entries(cid, frame_id=None, section=None):
    row = _row(cid, frame_id)
    if section:
        return list(row["sections"].get(section) or [])
    return [e for name in BIBLE_SECTIONS for e in row["sections"][name]]


def _evict(section_entries):
    """Past the cap, drop the oldest entry that is not an unpaid setup."""
    while len(section_entries) > BIBLE_ENTRIES_PER_SECTION:
        victim = None
        for e in section_entries:
            if e["section"] == "setups" and not e["paid"]:
                continue
            victim = e
            break
        if victim is None:
            break
        section_entries.remove(victim)


def add_entry(cid, frame_id, section, text, sources, *, since_turn=0,
              supersedes=None, paid=False):
    """One particular sentence into one section, with its sources. Refuses
    an unknown section, an empty sentence, no source, or a source the story
    does not hold (an entry nobody can trace is an entry nobody can trust).
    The same sentence in the same section is one entry. ``supersedes``
    marks an earlier entry of the section superseded and KEEPS it (a
    reversal keeps both lines). Returns ``(entry, fresh)``."""
    if section not in BIBLE_SECTIONS:
        raise ValueError("no such bible section %r; the sections are %s"
                         % (section, ", ".join(BIBLE_SECTIONS)))
    text = _text(text)
    if not text:
        raise ValueError("a bible entry is a sentence")
    refs = [str(s).strip() for s in (sources if isinstance(sources, (list, tuple))
                                     else [sources]) if str(s or "").strip()]
    if not refs:
        raise ValueError("a bible entry names its source")
    missing = [r for r in refs if not source_exists(cid, frame_id, r)]
    if missing:
        raise ValueError("a bible entry's source must exist; %s does not"
                         % ", ".join(missing[:3]))
    row = _row(cid, frame_id)
    bucket = row["sections"][section]
    uid = _entry_uid(section, text)
    for e in bucket:
        if e["uid"] == uid:
            return dict(e), False
    entry = _normalize_entry({
        "uid": uid, "section": section, "text": text, "source": refs,
        "since_turn": since_turn, "filed_at": time.time(), "paid": paid})
    if supersedes:
        for e in bucket:
            if e["uid"] == str(supersedes):
                e["superseded_by"] = uid
    bucket.append(entry)
    _evict(bucket)
    row["updated_turn"] = max(row["updated_turn"], int(since_turn or 0))
    _save(cid, frame_id, row)
    return dict(entry), True


def mark_paid(cid, frame_id, setup_uid, text, sources, *, turn_idx=0):
    """A planted setup paid off: the setup is marked, and one `paid` line is
    added with the payoff's sources. Returns the paid entry, or None for an
    unknown setup."""
    row = _row(cid, frame_id)
    found = None
    for e in row["sections"]["setups"]:
        if e["uid"] == str(setup_uid):
            e["paid"] = True
            found = e
    if found is None:
        return None
    _save(cid, frame_id, row)
    entry, _fresh = add_entry(cid, frame_id, "paid", text, sources,
                              since_turn=turn_idx, paid=True)
    return entry


def note_publish(cid, frame_id, *, package_uid, title, turn_idx):
    """Deterministic, no call: a published package is a decision the room
    made. Fail-open when the package cannot be found (nothing to cite)."""
    try:
        return add_entry(cid, frame_id, "decided",
                         "The room published '%s' at beat %d."
                         % (_text(title, 160), int(turn_idx or 0)),
                         [package_uid], since_turn=turn_idx)[0]
    except ValueError:
        return None


def note_resolve(cid, frame_id, *, package_uid, title, turn_idx):
    """Deterministic: a resolved package is a payoff landed."""
    try:
        return add_entry(cid, frame_id, "paid",
                         "'%s' resolved at beat %d." % (_text(title, 160),
                                                        int(turn_idx or 0)),
                         [package_uid], since_turn=turn_idx, paid=True)[0]
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# What the agents are shown
# ---------------------------------------------------------------------------

def render_block(cid, frame_id=None, limit=BIBLE_CHARS_SHOWN):
    """The bible as a system-block section, within ``limit`` characters:
    unpaid setups first (they never leave), then every section newest
    first. Empty string when the bible is empty."""
    row = _row(cid, frame_id)
    lines = []
    total = 0

    def put(line):
        nonlocal total
        if total + len(line) + 1 > limit:
            return False
        lines.append(line)
        total += len(line) + 1
        return True

    put("STORY BIBLE. The room's own memory of this story: what the player "
        "asked for in their words, what the room promised and planted, what "
        "it decided against and why. Typed state (mandates, packages, needs, "
        "lore) is cited by id, never repeated here. Serve it to no mind.")
    unpaid = [e for e in row["sections"]["setups"] if not e["paid"]]
    if unpaid:
        put("setups, unpaid:")
        for e in reversed(unpaid):
            if not put("  - [beat %d] %s (%s)" % (e["since_turn"], e["text"],
                                                  ", ".join(e["source"]))):
                break
    for name in BIBLE_SECTIONS:
        bucket = [e for e in row["sections"][name]
                  if not (name == "setups" and not e["paid"])]
        if not bucket:
            continue
        if not put("%s:" % name):
            break
        for e in reversed(bucket):
            mark = " [superseded]" if e["superseded_by"] else ""
            if not put("  - [beat %d]%s %s (%s)" % (e["since_turn"], mark,
                                                    e["text"], ", ".join(e["source"]))):
                break
    if len(lines) <= 1:
        return ""
    return "\n\n" + "\n".join(lines)


# ---------------------------------------------------------------------------
# The fold
# ---------------------------------------------------------------------------

def unfolded_messages(cid, frame_id, *, window):
    """Thread lines no fold has read, oldest first, EXCLUDING the newest
    ``window`` lines (those are still the Planner's live context)."""
    from story import room_conversation as room
    row = _row(cid, frame_id)
    clause, args = room._frame_clause(frame_id)
    rows = q(f"SELECT * FROM room_messages WHERE chat_id=? AND {clause} "
             "AND id>? ORDER BY id", (int(cid), *args, row["folded_through"]))
    rows = [room._row(r) for r in rows]
    if window and len(rows) > window:
        return rows[:-window]
    return []


def pending_fold_count(cid, frame_id, *, window):
    return len(unfolded_messages(cid, frame_id, window=window))


def _call(system, payload):
    from agents.common import jparse
    from llm import providers
    raw = providers.chat_complete(
        BIBLE_ROLE, system, json.dumps(payload, ensure_ascii=False),
        json_mode=True, max_tokens=BIBLE_FOLD_MAX_TOKENS)
    out = jparse(raw)
    return out if isinstance(out, dict) else {}


def fold(cid, frame_id=None, *, window, turn_idx=None):
    """One fold: the oldest unfolded batch is shown to the model with the
    bible as it stands, and what comes back is filed through `add_entry`
    -- so an entry with no source, or a source that does not exist, is
    refused here too and counted. `folded_through` advances past the batch
    whether or not the model kept anything: a batch nobody could fold is
    a batch the story walked away from. Returns a report."""
    from llm.prompts import get_prompt
    batch = unfolded_messages(cid, frame_id, window=window)[:BIBLE_FOLD_LINES]
    if not batch:
        return {"folded": 0, "kept": 0, "refused": 0}
    row = _row(cid, frame_id)
    payload = {
        "sections": list(BIBLE_SECTIONS),
        "bible": {name: [{"uid": e["uid"], "text": e["text"], "paid": e["paid"]}
                         for e in row["sections"][name]]
                  for name in BIBLE_SECTIONS},
        "lines": [{"ref": "msg:%d" % m["id"], "role": m["role"],
                   "beat": m["turn_idx"], "text": m["text"][:1200]}
                  for m in batch],
    }
    out = _call(get_prompt("bible_fold"), payload)
    kept, refused, notes = 0, 0, []
    for raw in out.get("entries") if isinstance(out.get("entries"), list) else []:
        if not isinstance(raw, dict):
            continue
        try:
            if raw.get("pays"):
                entry = mark_paid(cid, frame_id, raw["pays"], raw.get("text"),
                                  raw.get("source") or [],
                                  turn_idx=raw.get("since_turn") or turn_idx or 0)
                if entry is None:
                    raise ValueError("pays names a setup the bible does not hold")
                kept += 1
                continue
            _entry, fresh = add_entry(
                cid, frame_id, str(raw.get("section") or ""), raw.get("text"),
                raw.get("source") or [],
                since_turn=raw.get("since_turn") or turn_idx or 0,
                supersedes=raw.get("supersedes"))
            kept += 1 if fresh else 0
        except ValueError as exc:
            refused += 1
            notes.append(str(exc)[:200])
    row = _row(cid, frame_id)
    row["folded_through"] = max(row["folded_through"], max(m["id"] for m in batch))
    row["folds"] += 1
    if turn_idx is not None:
        row["updated_turn"] = max(row["updated_turn"], int(turn_idx))
    _save(cid, frame_id, row)
    return {"folded": len(batch), "kept": kept, "refused": refused,
            "notes": notes[:6]}


def schedule_fold(cid, frame_id, *, window, base_turn=None):
    """Queue a fold out of band when a batch is waiting. Returns the job,
    or None when there is nothing to fold."""
    from core import jobs
    if pending_fold_count(cid, frame_id, window=window) < BIBLE_FOLD_BATCH:
        return None

    def _run(job):
        return fold(cid, frame_id, window=window, turn_idx=base_turn)

    return jobs.submit(cid, BIBLE_JOB_KEY, _run, base_turn=base_turn)
