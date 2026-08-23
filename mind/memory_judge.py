"""One reading pass over what a recall actually returned.

Two questions this engine has tried to answer with statistics, and could not,
because both are about what the rows SAY and a statistic can only see their
scores:

**Does any of this bear on the moment at all?** `recall_confidence` answers
this as an NQC/WIG-shape z-score against the bank's own score distribution.
Measured against 470 positive and 30 negative LongMemEval probes, it fires
**0 of 30** times on questions whose answers are absent by construction, and
recalibrating cannot fix it: positives climb 1.9x across a bank-size sweep and
negatives 2.2x, so the gap stays at roughly one sigma at every scale and never
widens. A query whose answer is absent still retrieves topically related rows
and still produces a peaked distribution. **Presence and absence have the same
shape** (UNBUILT 1.76).

**Do any two of these disagree?** Deterministic detection was built for this
and measured not to work. Against the 18 known superseded pairs in the
synthetic worlds, a real contradiction scores similarity 0.477 median while
unrelated pairs reach 0.602 at p95 -- so no floor catches supersession without
firing on a fifth of everything -- and entity overlap runs backwards: a belief
and its refutation share a named person **0.0%** of the time against 16.6% for
random pairs, because the refutation characteristically comes from a different
mouth. Elias says the chapel is unreachable; JUNE saw his lights there. The
different source is what makes it a refutation (UNBUILT 2.24).

The reason generalises, and it is why both live here now: **contradiction and
relevance are semantic relations, and every signal available to a scorer is a
topical one.** Two rows can be about one subject without disagreeing, and can
disagree while sharing almost no surface. Nothing short of reading them can
tell the difference. So this reads them.

WHAT THIS MAY AND MAY NOT DO
----------------------------

It may say two memories do not sit together. It may **not** say which one is
true. Nothing outside a mind is entitled to decide which of that mind's
memories to believe -- the firewall's rule is that a guard SUBTRACTS, and the
one thing that must never be built here is a detector that hands a character a
conclusion instead of an occasion. The prompt forbids it in those words and
`_clean_tension` drops any tension that names only one memory, because a
"tension" with one side is a verdict wearing the word.

It is also, deliberately, not a mind. It reads one character's own recalled
rows and the moment they were recalled for -- material that character already
holds, delivered to it seconds later in the same payload -- so it crosses no
information boundary that recall itself does not already cross. It has no
memory of its own, no state, and its output is thrown away after one beat.

FAILING OPEN
------------

Every failure path returns the empty verdict, which adds no keys to the
payload and leaves the beat exactly as it was before this existed. A judge
that cannot be reached must cost a character nothing, because the alternative
-- a mind told "nothing comes back clearly" by a timeout -- is the engine
lying to it about its own memory.
"""

from __future__ import annotations

import json
import re

from core.db import q, qi
from core.logging_utils import logger
from llm.prompts import get_prompt
from llm.providers import RetryConfig, chat_complete

#: Below this many recalled rows there is not enough to review: a tension
#: needs two rows to sit between, and "nothing here bears on the moment" is
#: not a judgement worth a call when almost nothing came back to judge.
_MIN_ROWS = 3

#: The moment is the character's whole current view, which runs a median
#: ~1,015 characters. Truncated rather than sent whole because the question
#: here is what the beat is ABOUT, and the tail of a long view is scene
#: dressing.
_MOMENT_CHARS = 1200

#: One row's prose. `details` is the full content and `gist` its compression;
#: both go, because a contradiction can live in either and this is the only
#: pass that reads them.
_ROW_CHARS = 420

#: A beat that produces more than this many tensions has not found
#: contradictions, it has found a model in a mood. The cap is an occasion
#: budget, not a claim about how many disagreements a bank can hold.
_MAX_TENSIONS = 2

#: The answer is a handful of ids and at most two short phrases, so this
#: budget is not for the ANSWER -- it is for whatever the host has put on the
#: `utility` row, and a reasoning model spends its allowance on the trace
#: before it writes a character of content. Measured while building this: at
#: 700 tokens SIX calls in a row came back "returned reasoning but no answer
#: (2912 chars of trace, content empty)", and at 6000, five of thirty-six
#: still did. The lane failed open every time, which is correct and is exactly
#: why nobody would have noticed -- a feature that is silently absent and one
#: that is working look identical when the failure mode is "do nothing". This
#: pass runs out of band, so there is no player waiting to be charged for the
#: headroom.
_MAX_TOKENS = 16000

#: A patient retry, for the same reason. `requests` raises `RemoteDisconnected`
#: as a `ConnectionError`, which the default policy already treats as
#: retryable -- so the eleven dropped calls in the same run were not a
#: classification failure, they exhausted three attempts. Nobody is waiting on
#: this lane, and a beat that finds nothing because a socket closed is an
#: occasion a mind never gets, so it is worth waiting minutes for. The turn
#: path keeps the default; only this lane is allowed to be slow.
_PATIENT = RetryConfig(max_retries=6, base_delay=2.0, max_delay=60.0)

_EMPTY = {"available": False, "bears": None, "tensions": []}


def _row_for_review(mem):
    return {
        "memory_ref": str(mem.get("memory_ref") or ""),
        "when": str(mem.get("when") or ""),
        "how_i_know": str(mem.get("epistemic_origin") or ""),
        "memory": " ".join(
            str(mem.get("details") or mem.get("gist") or "").split()
        )[:_ROW_CHARS],
    }


def _parse(raw):
    """The consolidator's own tolerance, for the same reason it has it."""
    try:
        return json.loads(raw)
    except Exception:
        match = re.search(r"\{.*\}", raw or "", re.S)
        if not match:
            return None
        try:
            return json.loads(re.sub(r",\s*([}\]])", r"\1", match.group(0)))
        except Exception:
            return None


def _clean_tension(item, known):
    """A tension names TWO rows this recall actually delivered, or it is not
    one.

    Both halves are refusals rather than tidying. A tension with one side is a
    verdict about a single memory, which is the one thing this pass may not
    produce; a tension naming a `memory_ref` that was not in the payload is a
    citation to something the mind was not handed, which is how a model's
    invention would enter a character's head wearing an engine's voice.
    """
    if not isinstance(item, dict):
        return None
    refs = [str(r).strip() for r in (item.get("memories") or [])
            if str(r or "").strip() in known]
    refs = list(dict.fromkeys(refs))
    if len(refs) < 2:
        return None
    about = " ".join(str(item.get("they_disagree_about") or "").split())[:200]
    if not about:
        return None
    return {"memories": refs[:2], "they_disagree_about": about}


def review_recall(char_name, moment, rows, *, language=None):
    """Read `rows` against `moment` and report relevance and tension.

    Returns `{"available": bool, "bears": [refs] | None, "tensions": [...]}`.
    `available` is False whenever the review did not happen or could not be
    read, and every caller must treat that as "no information", never as
    "nothing bears on this".
    """
    rows = [r for r in (rows or []) if str(r.get("memory_ref") or "").strip()]
    moment = " ".join(str(moment or "").split())[:_MOMENT_CHARS]
    if len(rows) < _MIN_ROWS or not moment:
        return dict(_EMPTY)
    payload = {
        "character": str(char_name or ""),
        "the_moment": moment,
        "what_came_back": [_row_for_review(r) for r in rows],
    }
    try:
        raw = chat_complete("utility", get_prompt("recall_review", language),
                            json.dumps(payload, ensure_ascii=False),
                            temperature=0.0, max_tokens=_MAX_TOKENS,
                            retry_config=_PATIENT)
    except Exception as exc:
        # Not a warning on the turn: a review that did not happen has taken
        # nothing away from the beat, and a per-beat log line for a
        # misconfigured optional lane is noise a host cannot act on twice.
        logger.info("memory: recall review unavailable (%s)", exc)
        return dict(_EMPTY)
    parsed = _parse(raw)
    if not isinstance(parsed, dict):
        logger.info("memory: recall review returned unreadable output")
        return dict(_EMPTY)
    known = {str(r.get("memory_ref") or "") for r in rows}
    bears = [str(r).strip() for r in (parsed.get("bears_on_this_moment") or [])
             if str(r).strip() in known]
    tensions = []
    for item in (parsed.get("tensions") or []):
        got = _clean_tension(item, known)
        if got and got not in tensions:
            tensions.append(got)
        if len(tensions) >= _MAX_TENSIONS:
            break
    return {"available": True, "bears": list(dict.fromkeys(bears)),
            "tensions": tensions}


# ---- The occasion, found at mint and offered later ----
#
# WHY MINT RATHER THAN RECALL, measured. The reading pass costs 114 seconds on
# a 24-row payload against this install's `utility` model, and 16 of 36
# benchmark calls never returned at all (11 dropped connections, 5 with the
# reply eaten by a reasoning trace). In band, in front of a player, that is
# not a tax on the character stage -- it is a different product, and it would
# make a firewall-adjacent behaviour depend on which model a host happened to
# choose. UNBUILT 2.24 named the alternative before any of this was built:
# "the beat that FORMS the refutation is the beat where a mind has both in
# view, and that is where the occasion is cheapest to notice."
#
# So it runs after commit, on the same terms as autobiographical
# consolidation: the turn's facts are already durable, nothing here is a turn
# fact, and a failure is logged and forgotten rather than raised.
#
# WHAT IT IS WORTH, on the six synthetic worlds, scored only on cases where
# retrieval delivered both planted rows and the call actually ran (n=18):
#
#     a belief that turned out unfounded   11/13 named the planted pair (85%)
#     the world simply changed              1/5  named the planted pair (20%)
#     tensions invented from nothing        0/36
#
# That +65 discrimination gap is wider than any CHARACTER model measured the
# same day -- glm-5p2-fast +46, grok-4.3 +1, deepseek-v4-pro -20 -- and the
# reviewer here IS deepseek, the model that scores -20 as a character. The
# framing does the work, not the weights.

#: How long an unoffered occasion stays worth offering. A contradiction found
#: four hundred beats ago and never once surfaced has been overtaken by the
#: story; re-offering it forever is the "haunting" `contrast_memory` refuses
#: to become.
_TENSION_TTL_BEATS = 40

#: A mind carries a handful of live occasions, not a docket.
_MAX_PENDING_TENSIONS = 3

_TENSION_KEY = "memory_tensions"


def pending_subject(state, current_turn_idx):
    """The subject of the oldest live occasion, or "".

    THE PAIR IS NOT RETURNED, and that is the whole correction. Handing a mind
    "memory A and memory B disagree about X" was built, measured, and is
    worse than saying nothing: on a neutral beat with both rows already in the
    payload, minds disputed 16/16 unprompted and 13/16 when told. It is the
    third measured instance of an invitation to notice making a mind notice
    less -- the synthetic bank's led arm scored 4/6 against an unled 6/6 on
    the same axis.

    What DOES work is co-presence, and it is the whole of it: on an unaimed
    beat, ordinary recall put both halves of a contradiction in front of a
    mind **0 times in 18**. Never, not rarely. That is what
    `record_dispute` firing once in 9,608 live memories has been measuring.

    So the subject is used to RETRIEVE, and the mind finds whatever it finds.
    It is handed rows, never a verdict -- which is also the only version of
    this that respects the rule that nothing outside a mind may decide which
    of its memories to believe.
    """
    live = pending_tensions(state, current_turn_idx)
    return live[0]["they_disagree_about"] if live else ""


def pending_tensions(state, current_turn_idx):
    """Live occasions from `chat_chars.state`, oldest first.

    Pure and defensive: this reads a blob written by a background job into a
    column six other writers also touch, so anything unreadable is treated as
    nothing rather than raised at a character mid-beat.
    """
    items = (state or {}).get(_TENSION_KEY)
    if not isinstance(items, list):
        return []
    out = []
    for item in items:
        if not isinstance(item, dict):
            continue
        refs = [str(r) for r in (item.get("memories") or []) if str(r).strip()]
        about = str(item.get("they_disagree_about") or "").strip()
        if len(refs) < 2 or not about:
            continue
        try:
            found = int(item.get("turn_idx"))
        except (TypeError, ValueError):
            continue
        if current_turn_idx is not None and \
                current_turn_idx - found > _TENSION_TTL_BEATS:
            continue
        out.append({"memories": refs[:2], "they_disagree_about": about,
                    "turn_idx": found})
    return out[-_MAX_PENDING_TENSIONS:]


def _store_tensions(chat_id, char_id, frame_id, tensions):
    """Write ONLY this key, with `json_set`.

    Read-modify-write from a background thread would race the next beat's
    commit, which rewrites the same column with the character's psychology,
    stress, beliefs and unbidden ledger in it. Last writer wins on a whole
    blob, so the loser is a turn's worth of primary state -- for the sake of
    an annotation that is reconstructible by re-running this job. A targeted
    update cannot lose anything but itself.
    """
    payload = json.dumps(tensions, ensure_ascii=False)
    if frame_id is None:
        qi("UPDATE chat_chars SET state=json_set(COALESCE(state,'{}'),'$.%s',"
           "json(?)) WHERE chat_id=? AND char_id=?" % _TENSION_KEY,
           (payload, chat_id, char_id))
        return
    qi("UPDATE chat_char_frames SET state=json_set(COALESCE(state,'{}'),"
       "'$.%s',json(?)) WHERE chat_id=? AND char_id=? AND frame_id=?"
       % _TENSION_KEY, (payload, chat_id, char_id, frame_id))


def _existing_tensions(chat_id, char_id, frame_id, current_turn_idx):
    if frame_id is None:
        row = q("SELECT state FROM chat_chars WHERE chat_id=? AND char_id=?",
                (chat_id, char_id), one=True)
    else:
        row = q("SELECT state FROM chat_char_frames WHERE chat_id=? AND "
                "char_id=? AND frame_id=?", (chat_id, char_id, frame_id),
                one=True)
    if not row:
        return None
    try:
        state = json.loads(row["state"] or "{}")
    except (TypeError, ValueError):
        state = {}
    return pending_tensions(state, current_turn_idx)


def review_minted_memories(chat_id, char_id, char_name, minted, *,
                           current_turn_idx, frame_id=None, k=None):
    """Look for a contradiction between what this mind just recorded and what
    it already held, and leave any it finds where a later beat will offer it.

    `minted` is this beat's new rows for this character. Nothing minted means
    nothing new can have contradicted anything, so there is nothing to ask.

    The mind's OWN rows on both sides, so no boundary is crossed that recall
    does not already cross: the new memories are its own, and the retrieved
    ones are what `search_memories` would hand it anyway.

    Returns the number of occasions stored. Never raises -- a background pass
    that breaks a later turn is worse than one that finds nothing.
    """
    # The facade, not the sibling: `tools/project_check.py` enforces it,
    # and deferred so `mind.memory` can finish importing this module.
    from mind.memory import _RECALL_LIMIT, search_memories

    # `core.db.q` returns sqlite3.Row. Search results are dicts. This boundary
    # accepts both; calling `.get` on the former made every real background
    # review fail while dict-only tests stayed green.
    fresh = []
    for memory in minted or ():
        try:
            memory = dict(memory)
        except (TypeError, ValueError):
            continue
        if str(memory.get("event_key") or "").strip():
            fresh.append(memory)
    if not fresh:
        return 0
    query = " ".join(
        " ".join(str(m.get("gist") or m.get("content") or "").split())
        for m in fresh)[:_MOMENT_CHARS]
    if not query.strip():
        return 0
    try:
        held = search_memories(
            chat_id, char_id, query, k=int(k or _RECALL_LIMIT),
            include_archived=True, current_turn_idx=current_turn_idx,
            chronological=True)
    except Exception as exc:
        logger.info("memory: tension pass could not retrieve (%s)", exc)
        return 0
    seen, rows = set(), []
    for mem in (*fresh, *held):
        ref = str(mem.get("event_key") or "").strip()
        if not ref or ref in seen:
            continue
        seen.add(ref)
        rows.append({
            "memory_ref": ref,
            "when": "about %s beats ago" % max(
                0, (current_turn_idx or 0) - int(mem.get("turn_idx") or 0)),
            "epistemic_origin": str(mem.get("provenance") or ""),
            "gist": mem.get("gist") or "",
            "details": mem.get("content") or "",
        })
    verdict = review_recall(char_name, query, rows)
    if not verdict.get("available") or not verdict.get("tensions"):
        return 0
    # Merged with what is already pending rather than replacing it: two beats
    # can each find a real occasion, and the second must not silently erase
    # the first before any mind has been handed it.
    keep = _existing_tensions(chat_id, char_id, frame_id, current_turn_idx)
    if keep is None:
        return 0
    known = {tuple(sorted(t["memories"])) for t in keep}
    added = 0
    for tension in verdict["tensions"]:
        key = tuple(sorted(tension["memories"]))
        if key in known:
            continue
        known.add(key)
        keep.append({**tension, "turn_idx": current_turn_idx})
        added += 1
    if not added:
        return 0
    _store_tensions(chat_id, char_id, frame_id,
                    keep[-_MAX_PENDING_TENSIONS:])
    return added
