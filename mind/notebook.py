"""The character's notebook: one view over what it keeps.

The owner, 2026-09-27: "I needs stable core where a characters keeps track
of what it thinks about things and other people and how it thinks they
think"; "there should be a general note taking system for things the llm
wishes to keep track of"; and "making sure the llm still has acces to what
it needs without letting it baloon".

Two stores, one view, no copies:

- What the character THINKS -- of people, of places and things, of what
  someone else thinks -- is the mind-model core (`mind.theory_of_mind`):
  per subject and kind, with a ceiling, a fade and rivals that explain each
  other away. Each note there has a stable id (`note_id`), and the character
  strikes, revises or adds by it.
- What the character wants to KEEP TRACK OF -- a fact, a reminder -- is the
  reminder list here (`state["notebook"]`), kept until struck. Good memory
  is the goal, never realistic forgetting (the owner, 2026-09-26): past
  `REMINDERS_KEPT` the oldest untouched go, and nothing else removes one.

THE STORE KEEPS EVERYTHING; THE VIEW IS BOUNDED AND CHOSEN FOR THE MOMENT.
`view` shows, first, every note about who and what is in play -- the people
present, the room, anyone or anything named in what just reached the mind,
in its own running note or in what it tried to recall -- then the strongest
and most recently touched of the rest, at most `PER_SUBJECT_SHOWN` about any
one subject, and fewer the more the body has the mind (absorption, as the
held-hypotheses sheet already narrows). What is not shown is one `ponder`
away: a recall that names someone or something brings its notes back.

Pure: no database, no model. The knobs below are the owner's.
"""

from __future__ import annotations

import hashlib
import re

from mind import theory_of_mind as tom

#: How many notes about people and things the view shows when the mind is
#: free, and how few when the body has it entirely (absorption 1.0).
NOTES_SHOWN = 16
NOTES_SHOWN_ABSORBED = 6
#: At most this many notes about any one person or thing in the view, so one
#: obsession cannot crowd out everyone else.
PER_SUBJECT_SHOWN = 3
#: How many reminders are kept (past it the oldest untouched go), and how
#: many the view shows.
REMINDERS_KEPT = 100
REMINDERS_SHOWN = 6
#: How many concerns the view shows (the engine keeps them; a concern ends
#: when what would settle it happens, or the character lets it go).
CONCERNS_SHOWN = 6
#: A reminder untouched for this many beats leaves the view unless what it is
#: about is in play; it is still kept, and a recall naming it brings it back.
REMINDER_STALE_TURNS = 40
#: A note formed, changed or borne out within this many beats counts as fresh
#: -- the view keeps what the mind is working on.
RECENT_TURNS = 3
#: What the character's own sureness means as confidence (then capped by the
#: note's kind), and the words the view shows a confidence as.
SURE_CONFIDENCE = {"certain": 0.9, "likely": 0.65, "guess": 0.4}
SURE_WORDS = ((0.75, "certain"), (0.5, "likely"), (0.25, "guess"), (0.0, "doubtful"))
#: Where a nudge moves a held note (by the kind's plasticity) when what just
#: happened bore it out, cast doubt on it, or told against it.
NUDGE_TOWARD = {"bore_out": 0.85, "doubted": 0.3, "contradicted": 0.1}
#: A shown note below this confidence is not shown (the store prunes below
#: its own floor at commit).
SHOWN_FLOOR = 0.05
NOTE_CHARS = 300
ABOUT_CHARS = 120

#: How the view scores a note: a subject in play outranks everything, a note
#: naming someone in play comes next, a freshly touched note next, and
#: confidence orders the rest.
_IN_PLAY = 2.0
_NAMES_IN_PLAY = 1.5
_FRESH = 1.0


def _text(value, n=NOTE_CHARS):
    text = " ".join(str(value or "").split())
    return text if len(text) <= n else text[:n] + "..."


def sure_word(confidence):
    value = float(confidence or 0.0)
    return next(word for floor, word in SURE_WORDS if value >= floor)


def shown_count(absorption):
    try:
        a = max(0.0, min(1.0, float(absorption or 0.0)))
    except (TypeError, ValueError):
        a = 0.0
    return int(round(NOTES_SHOWN - (NOTES_SHOWN - NOTES_SHOWN_ABSORBED) * a))


def _named_in(name, texts):
    """Whether `name` stands as a whole name in any of `texts` (any script)."""
    name = str(name or "").strip()
    if not name:
        return False
    # Deferred: `story` imports `mind`, and a module-level import here would
    # close an eager package cycle (as in `theory_of_mind.rekey_place_claims`).
    from story.character_schema import name_boundary_pattern
    pattern = re.compile(name_boundary_pattern(name), re.I)
    return any(pattern.search(str(t or "")) for t in texts)


def in_play(subject, present, texts):
    return str(subject or "").casefold() in present or _named_in(subject, texts)


named_in = _named_in


def concern_id(text):
    """A concern's handle: concerns are the engine's plain strings
    (`active_state.active_concerns`), so the id is derived from the words."""
    norm = " ".join(str(text or "").split()).casefold()
    return "c" + hashlib.sha1(norm.encode("utf-8")).hexdigest()[:5]


def view(state, turn_idx, *, present=(), texts=(), absorption=0.0, elapsed_seconds=None,
         concerns=(), projects=()):
    """The notebook as the character reads it this beat, in four sections --
    each left out when empty:

    - `on_your_mind`: its concerns, each carrying what would settle it in its
      own words (`concerns`: the engine's strings);
    - `what_you_are_about`: its projects, each with what would finish it
      (`until`) and `on_trial` while still on probation (`projects`: the live
      ledger);
    - `people_and_things`: what it thinks of people and things, and what it
      thinks they think, grouped by subject with those in play first
      (`sure`: how sure, in a word);
    - `to_keep`: its reminders.

    `present`: the people here and the room's name. `texts`: what just
    reached the mind, its own running note, and what it is trying to recall.
    Every entry carries the `id` the character strikes and changes."""
    state = state or {}
    out = {}
    minding = [{"id": concern_id(c), "note": _text(c)}
               for c in list(concerns or [])[:CONCERNS_SHOWN] if str(c or "").strip()]
    if minding:
        out["on_your_mind"] = minding
    about = [{"id": str(p.get("id") or ""), "note": _text(p.get("project")),
              **({"until": _text(p["satisfied_when"])} if str(p.get("satisfied_when") or "").strip() else {}),
              **({"on_trial": True} if p.get("probation") else {})}
             for p in projects or [] if isinstance(p, dict) and str(p.get("project") or "").strip()]
    if about:
        out["what_you_are_about"] = about
    notes = _people_and_things(state, turn_idx, present, texts, absorption, elapsed_seconds)
    if notes:
        out["people_and_things"] = notes
    present_cf = {str(p).casefold() for p in present if str(p or "").strip()}
    keep = _reminders_shown(state, turn_idx, present_cf, [t for t in texts if str(t or "").strip()])
    if keep:
        out["to_keep"] = keep
    return out


def entries(notebook_view):
    """`{id: (section, entry)}` over a view -- how a reply's ids are routed."""
    return {e["id"]: (section, e) for section, rows in (notebook_view or {}).items()
            for e in rows or [] if isinstance(e, dict) and e.get("id")}


def _people_and_things(state, turn_idx, present, texts, absorption, elapsed_seconds):
    present_cf = {str(p).casefold() for p in present if str(p or "").strip()}
    texts = [t for t in texts if str(t or "").strip()]
    named = [p for p in present if str(p or "").strip()]
    scored = []
    for about, model in (state.get("mind_models") or {}).items():
        subject_live = in_play(about, present_cf, texts)
        for hyp in (model or {}).get("hypotheses") or []:
            if not isinstance(hyp, dict) or not str(hyp.get("claim") or "").strip():
                continue
            live = tom._live_confidence(hyp, turn_idx, elapsed_seconds)
            if live < SHOWN_FLOOR:
                continue
            fresh = (turn_idx is not None and hyp.get("last_updated_turn") is not None
                     and int(turn_idx) - int(hyp["last_updated_turn"]) <= RECENT_TURNS)
            score = live + (_IN_PLAY if subject_live else 0.0) + (_FRESH if fresh else 0.0)
            if not subject_live and named and _named_in_any(hyp.get("claim"), named):
                score += _NAMES_IN_PLAY
            scored.append((score, str(about), hyp, live))
    scored.sort(key=lambda row: (-row[0], row[1]))
    per_subject, chosen = {}, []
    for score, about, hyp, live in scored:
        if len(chosen) >= shown_count(absorption):
            break
        if per_subject.get(about, 0) >= PER_SUBJECT_SHOWN:
            continue
        per_subject[about] = per_subject.get(about, 0) + 1
        chosen.append((about, hyp, live))
    order = list(dict.fromkeys(about for about, _hyp, _live in chosen))
    return [{"id": tom.note_id(about, hyp), "about": about, "note": _text(hyp.get("claim")),
             "sure": sure_word(live), "kind": tom._kind_or_default(hyp.get("kind"))}
            for subject in order for about, hyp, live in chosen if about == subject]


def for_payload(notebook_view):
    """The view as the character reads it: a note's `kind` is the engine's
    filing (its ceiling and fade), not something the character reasons with."""
    return {section: [{k: v for k, v in e.items() if k != "kind"} for e in rows]
            for section, rows in (notebook_view or {}).items()}


def _named_in_any(text, names):
    return any(_named_in(name, [text]) for name in names)


def _reminders_shown(state, turn_idx, present_cf, texts):
    rows = []
    for r in state.get("notebook") or []:
        if not isinstance(r, dict) or not str(r.get("note") or "").strip():
            continue
        live = bool(r.get("about")) and in_play(r["about"], present_cf, texts)
        age = (int(turn_idx) - int(r.get("last_turn") or 0)) if turn_idx is not None else 0
        if not live and age > REMINDER_STALE_TURNS:
            continue
        rows.append((0 if live else 1, -int(r.get("last_turn") or 0), r))
    rows.sort(key=lambda row: row[:2])
    return [{"id": r["id"], **({"about": r["about"]} if r.get("about") else {}), "note": _text(r["note"])}
            for _live, _age, r in rows[:REMINDERS_SHOWN]]


def apply_notebook_ops(state, ops, turn_idx):
    """The reminder list, after this beat's adds, changes and strikes.

    `ops`: `[{op: add, about, note} | {op: change, id, note} | {op: strike,
    id}]`. A reminder's id is `r<n>`, never reused. Past `REMINDERS_KEPT`
    the oldest untouched go."""
    book = [dict(r) for r in (state.get("notebook") or []) if isinstance(r, dict)]
    seq = int(state.get("notebook_seq") or 0)
    for op in ops or []:
        if not isinstance(op, dict):
            continue
        kind = str(op.get("op") or "")
        ref = str(op.get("id") or "")
        note = _text(op.get("note"))
        if kind == "add" and note:
            seq += 1
            book.append({"id": f"r{seq}", "about": _text(op.get("about"), ABOUT_CHARS), "note": note,
                         "turn": turn_idx, "last_turn": turn_idx})
        elif kind == "change" and note:
            for r in book:
                if r.get("id") == ref:
                    r["note"], r["last_turn"] = note, turn_idx
        elif kind == "strike":
            book = [r for r in book if r.get("id") != ref]
    if len(book) > REMINDERS_KEPT:
        keep = sorted(book, key=lambda r: int(r.get("last_turn") or 0))[-REMINDERS_KEPT:]
        book = [r for r in book if r in keep]
    state["notebook"] = book
    state["notebook_seq"] = seq
    return state


def find_reminder(state, ref):
    return next((r for r in (state or {}).get("notebook") or []
                 if isinstance(r, dict) and r.get("id") == str(ref or "")), None)
